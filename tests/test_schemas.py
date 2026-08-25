import pytest
from pydantic import ValidationError

from verdictforge.schemas import DebateRequest, Judgment, RankingEntry


def test_debate_request_trims_question_and_deduplicates_models() -> None:
    request = DebateRequest(question="  Explain entropy.  ", model_ids=["a", "b", "a"])

    assert request.question == "Explain entropy."
    assert request.model_ids == ["a", "b"]


@pytest.mark.parametrize("model_ids", [["only-one"], ["a", "b", "c", "d", "e"]])
def test_debate_request_requires_two_to_four_models(model_ids: list[str]) -> None:
    with pytest.raises(ValidationError):
        DebateRequest(question="A valid question", model_ids=model_ids)


def test_judgment_sorts_entries_by_rank() -> None:
    judgment = Judgment(
        rankings=[
            RankingEntry(model_id="second", rank=2, score=70),
            RankingEntry(model_id="first", rank=1, score=90),
        ],
        reasoning="The first answer is more accurate.",
        judge_model="judge",
    )

    assert [entry.model_id for entry in judgment.rankings] == ["first", "second"]


def test_judgment_rejects_duplicate_ranks() -> None:
    with pytest.raises(ValidationError):
        Judgment(
            rankings=[
                RankingEntry(model_id="a", rank=1, score=90),
                RankingEntry(model_id="b", rank=1, score=80),
            ],
            reasoning="Invalid tie.",
            judge_model="judge",
        )
