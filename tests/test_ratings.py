import pytest

from verdictforge.ratings import expected_score, initialize_ratings, update_ratings
from verdictforge.schemas import Judgment, RankingEntry


def make_judgment(order: list[str]) -> Judgment:
    return Judgment(
        rankings=[
            RankingEntry(model_id=model_id, rank=index + 1, score=90 - index * 10)
            for index, model_id in enumerate(order)
        ],
        reasoning="Ranked by quality.",
        judge_model="judge",
    )


def test_equal_ratings_have_even_expected_score() -> None:
    assert expected_score(1500, 1500) == pytest.approx(0.5)


def test_multiplayer_update_is_zero_sum() -> None:
    ratings = initialize_ratings(["a", "b", "c"])
    updated = update_ratings(ratings, make_judgment(["a", "b", "c"]))

    assert sum(item.rating for item in updated.values()) == pytest.approx(4500)
    assert updated["a"].rating == 1516
    assert updated["b"].rating == 1500
    assert updated["c"].rating == 1484
    assert updated["a"].wins == 1
    assert all(item.debates == 1 for item in updated.values())


def test_rating_update_does_not_mutate_input() -> None:
    ratings = initialize_ratings(["a", "b"])
    update_ratings(ratings, make_judgment(["b", "a"]))

    assert ratings["a"].rating == 1500
    assert ratings["b"].rating == 1500
