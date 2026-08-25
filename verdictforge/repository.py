"""Async SQLite persistence for debates and durable rating snapshots."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import UUID

import aiosqlite

from verdictforge.ratings import initialize_ratings
from verdictforge.schemas import (
    ArenaStats,
    DebateRecord,
    DebateSummary,
    PaginatedDebates,
    RatingSnapshot,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS debates (
    id TEXT PRIMARY KEY,
    question TEXT NOT NULL,
    mode TEXT NOT NULL,
    status TEXT NOT NULL,
    winner_model_id TEXT,
    record_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    completed_at TEXT,
    duration_ms INTEGER
);

CREATE INDEX IF NOT EXISTS idx_debates_created_at ON debates(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_debates_status ON debates(status);

CREATE TABLE IF NOT EXISTS ratings (
    model_id TEXT PRIMARY KEY,
    rating REAL NOT NULL,
    debates INTEGER NOT NULL DEFAULT 0,
    wins INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


class DebateRepository:
    """Small repository with one connection per operation and WAL concurrency."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self._initialized = False

    async def initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        async with self._connect() as database:
            await database.executescript(SCHEMA)
            await database.commit()
        self._initialized = True

    async def save_debate(self, debate: DebateRecord) -> None:
        winner = debate.judgment.rankings[0].model_id if debate.judgment else None
        async with self._connect() as database:
            await database.execute("BEGIN IMMEDIATE")
            await database.execute(
                """
                INSERT INTO debates (
                    id, question, mode, status, winner_model_id, record_json,
                    created_at, completed_at, duration_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    question = excluded.question,
                    mode = excluded.mode,
                    status = excluded.status,
                    winner_model_id = excluded.winner_model_id,
                    record_json = excluded.record_json,
                    completed_at = excluded.completed_at,
                    duration_ms = excluded.duration_ms
                """,
                (
                    str(debate.id),
                    debate.question,
                    debate.mode.value,
                    debate.status.value,
                    winner,
                    debate.model_dump_json(),
                    debate.created_at.isoformat(),
                    debate.completed_at.isoformat() if debate.completed_at else None,
                    debate.duration_ms,
                ),
            )
            for snapshot in debate.ratings:
                await database.execute(
                    """
                    INSERT INTO ratings (model_id, rating, debates, wins, updated_at)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(model_id) DO UPDATE SET
                        rating = excluded.rating,
                        debates = excluded.debates,
                        wins = excluded.wins,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (snapshot.model_id, snapshot.rating, snapshot.debates, snapshot.wins),
                )
            await database.commit()

    async def get_debate(self, debate_id: UUID) -> DebateRecord | None:
        async with self._connect() as database:
            cursor = await database.execute(
                "SELECT record_json FROM debates WHERE id = ?", (str(debate_id),)
            )
            row = await cursor.fetchone()
        return DebateRecord.model_validate_json(row[0]) if row else None

    async def list_debates(
        self,
        *,
        limit: int = 20,
        offset: int = 0,
        query: str | None = None,
    ) -> PaginatedDebates:
        where = "WHERE question LIKE ?" if query else ""
        parameters: tuple[object, ...] = (f"%{query}%",) if query else ()
        async with self._connect() as database:
            count_cursor = await database.execute(
                f"SELECT COUNT(*) FROM debates {where}",
                parameters,
            )
            total = (await count_cursor.fetchone())[0]
            cursor = await database.execute(
                f"""
                SELECT id, question, mode, status, winner_model_id, created_at, duration_ms
                FROM debates {where}
                ORDER BY created_at DESC LIMIT ? OFFSET ?
                """,
                (*parameters, limit, offset),
            )
            rows = await cursor.fetchall()

        items = [
            DebateSummary(
                id=row[0],
                question=row[1],
                mode=row[2],
                status=row[3],
                winner_model_id=row[4],
                created_at=row[5],
                duration_ms=row[6],
            )
            for row in rows
        ]
        return PaginatedDebates(items=items, total=total, limit=limit, offset=offset)

    async def load_ratings(self, model_ids: list[str]) -> dict[str, RatingSnapshot]:
        snapshots = initialize_ratings(model_ids)
        if not model_ids:
            return snapshots
        placeholders = ",".join("?" for _ in model_ids)
        async with self._connect() as database:
            cursor = await database.execute(
                f"""
                SELECT model_id, rating, debates, wins FROM ratings
                WHERE model_id IN ({placeholders})
                """,
                model_ids,
            )
            rows = await cursor.fetchall()
        for row in rows:
            snapshots[row[0]] = RatingSnapshot(
                model_id=row[0], rating=row[1], debates=row[2], wins=row[3]
            )
        return snapshots

    async def get_stats(self, model_ids: list[str]) -> ArenaStats:
        async with self._connect() as database:
            cursor = await database.execute(
                """
                SELECT
                    COUNT(*),
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END),
                    COALESCE(AVG(CASE WHEN duration_ms IS NOT NULL THEN duration_ms END), 0)
                FROM debates
                """
            )
            row = await cursor.fetchone()
        ratings = await self.load_ratings(model_ids)
        return ArenaStats(
            total_debates=row[0],
            completed_debates=row[1] or 0,
            average_duration_ms=round(row[2]),
            ratings=sorted(ratings.values(), key=lambda item: item.rating, reverse=True),
        )

    async def is_healthy(self) -> bool:
        try:
            async with self._connect() as database:
                cursor = await database.execute("SELECT 1")
                return (await cursor.fetchone())[0] == 1
        except aiosqlite.Error:
            return False

    @asynccontextmanager
    async def _connect(self) -> AsyncIterator[aiosqlite.Connection]:
        async with aiosqlite.connect(self.database_path, timeout=10) as connection:
            connection.row_factory = aiosqlite.Row
            await connection.execute("PRAGMA foreign_keys = ON")
            await connection.execute("PRAGMA journal_mode = WAL")
            await connection.execute("PRAGMA busy_timeout = 10000")
            yield connection
