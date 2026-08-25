import json

from verdictforge.config import Settings
from verdictforge.judging import BlindJudge
from verdictforge.providers import CompletionResult
from verdictforge.schemas import AnswerResult, AnswerStatus, Usage


class FakeJudgeProviders:
    def available_model_ids(self) -> list[str]:
        return ["judge"]

    async def complete(self, *args, **kwargs) -> CompletionResult:
        payload = {
            "rankings": [
                {
                    "candidate_id": "candidate-A",
                    "rank": 1,
                    "score": 92,
                    "strengths": ["Correct"],
                    "weaknesses": ["Brief"],
                    "verdict": "Best response.",
                },
                {
                    "candidate_id": "candidate-B",
                    "rank": 2,
                    "score": 79,
                    "strengths": ["Clear"],
                    "weaknesses": ["Incomplete"],
                    "verdict": "Useful but incomplete.",
                },
            ],
            "reasoning": "Candidate A is more accurate.",
        }
        return CompletionResult(json.dumps(payload), 10, Usage())


async def test_blind_judge_reveals_original_model_ids() -> None:
    settings = Settings(
        _env_file=None,
        judge_model_id="judge",
        groq_api_key=None,
        nvidia_api_key=None,
        nvidia_openai_api_key=None,
    )
    judge = BlindJudge(FakeJudgeProviders(), settings)
    answers = [
        AnswerResult(
            model_id=model_id,
            content="An answer",
            status=AnswerStatus.COMPLETED,
            latency_ms=1,
        )
        for model_id in ["model-one", "model-two"]
    ]

    judgment = await judge.evaluate("Which answer is best?", answers)

    assert {entry.model_id for entry in judgment.rankings} == {"model-one", "model-two"}
    assert judgment.judge_model == "judge"


def test_parser_rejects_missing_candidates() -> None:
    raw = json.dumps(
        {
            "rankings": [
                {
                    "candidate_id": "candidate-A",
                    "rank": 1,
                    "score": 90,
                    "strengths": ["Good"],
                    "weaknesses": ["None"],
                    "verdict": "Good.",
                },
                {
                    "candidate_id": "candidate-X",
                    "rank": 2,
                    "score": 80,
                    "strengths": ["Okay"],
                    "weaknesses": ["Missing detail"],
                    "verdict": "Okay.",
                },
            ],
            "reasoning": "Reason.",
        }
    )

    assert BlindJudge._parse(raw, {"candidate-A": "a", "candidate-B": "b"}) is None
