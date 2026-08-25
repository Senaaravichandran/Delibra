"""Application service coordinating arena, judge, ratings, and persistence."""

import asyncio
import logging
from datetime import UTC, datetime
from time import perf_counter
from uuid import UUID

from verdictforge.arena import ArenaError, DebateEngine
from verdictforge.judging import BlindJudge, JudgeError
from verdictforge.ratings import update_ratings
from verdictforge.repository import DebateRepository
from verdictforge.schemas import AnswerStatus, DebateRecord, DebateRequest, DebateStatus

logger = logging.getLogger(__name__)


class DebateService:
    """Owns debate lifecycle state and prevents concurrent rating write races."""

    def __init__(
        self,
        engine: DebateEngine,
        judge: BlindJudge,
        repository: DebateRepository,
    ) -> None:
        self.engine = engine
        self.judge = judge
        self.repository = repository
        self._rating_lock = asyncio.Lock()
        self._tasks: dict[UUID, asyncio.Task[None]] = {}

    async def start(self, request: DebateRequest) -> DebateRecord:
        selected = self.engine.select_models(request.model_ids)
        normalized = request.model_copy(update={"model_ids": selected})
        debate = DebateRecord(question=normalized.question, mode=normalized.mode)
        await self.repository.save_debate(debate)
        task = asyncio.create_task(self._run(debate, normalized), name=f"debate-{debate.id}")
        self._tasks[debate.id] = task
        task.add_done_callback(lambda _task: self._tasks.pop(debate.id, None))
        return debate

    async def _run(self, debate: DebateRecord, request: DebateRequest) -> None:
        started = perf_counter()
        debate.status = DebateStatus.RUNNING
        await self.repository.save_debate(debate)

        try:
            debate.answers = await self.engine.collect_answers(request)
            successful = [
                answer for answer in debate.answers if answer.status == AnswerStatus.COMPLETED
            ]
            if len(successful) < 2:
                raise ArenaError("Fewer than two models completed the debate.")

            debate.judgment = await self.judge.evaluate(debate.question, debate.answers)
            async with self._rating_lock:
                model_ids = list(self.engine.providers.catalog)
                current = await self.repository.load_ratings(model_ids)
                updated = update_ratings(current, debate.judgment)
                debate.ratings = sorted(
                    updated.values(), key=lambda item: item.rating, reverse=True
                )
                debate.status = (
                    DebateStatus.COMPLETED
                    if len(successful) == len(debate.answers)
                    else DebateStatus.PARTIAL
                )
                self._finish_timing(debate, started)
                await self.repository.save_debate(debate)
        except (ArenaError, JudgeError) as exc:
            logger.info("Debate %s ended safely: %s", debate.id, exc)
            debate.status = DebateStatus.FAILED
            debate.error = str(exc)
            self._finish_timing(debate, started)
            await self.repository.save_debate(debate)
        except Exception:
            logger.exception("Unexpected failure while running debate %s", debate.id)
            debate.status = DebateStatus.FAILED
            debate.error = "An unexpected server error interrupted this debate."
            self._finish_timing(debate, started)
            await self.repository.save_debate(debate)

    async def shutdown(self) -> None:
        """Cancel in-flight work cleanly during application shutdown."""

        tasks = list(self._tasks.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    @staticmethod
    def _finish_timing(debate: DebateRecord, started: float) -> None:
        debate.completed_at = datetime.now(UTC)
        debate.duration_ms = round((perf_counter() - started) * 1000)
