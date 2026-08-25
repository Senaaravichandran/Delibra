from datetime import UTC, datetime

from verdictforge.repository import DebateRepository
from verdictforge.schemas import (
    DebateMode,
    DebateRecord,
    DebateStatus,
    Judgment,
    RankingEntry,
    RatingSnapshot,
)


async def test_repository_round_trip_and_stats(tmp_path) -> None:
    repository = DebateRepository(tmp_path / "arena.db")
    await repository.initialize()
    debate = DebateRecord(
        question="Persist this?",
        mode=DebateMode.DIRECT,
        status=DebateStatus.COMPLETED,
        judgment=Judgment(
            rankings=[
                RankingEntry(model_id="a", rank=1, score=90),
                RankingEntry(model_id="b", rank=2, score=80),
            ],
            reasoning="A wins.",
            judge_model="judge",
        ),
        ratings=[
            RatingSnapshot(model_id="a", rating=1516, debates=1, wins=1),
            RatingSnapshot(model_id="b", rating=1484, debates=1, wins=0),
        ],
        completed_at=datetime.now(UTC),
        duration_ms=1234,
    )

    await repository.save_debate(debate)
    loaded = await repository.get_debate(debate.id)
    page = await repository.list_debates(query="Persist")
    stats = await repository.get_stats(["a", "b"])

    assert loaded == debate
    assert page.total == 1 and page.items[0].winner_model_id == "a"
    assert stats.completed_debates == 1
    assert stats.average_duration_ms == 1234
    assert stats.ratings[0].model_id == "a"
