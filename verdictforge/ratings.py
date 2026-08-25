"""Zero-sum multiplayer Elo ratings derived from complete debate rankings."""

from collections.abc import Mapping

from verdictforge.schemas import Judgment, RatingSnapshot

DEFAULT_RATING = 1500.0
K_FACTOR = 32.0


def expected_score(rating_a: float, rating_b: float) -> float:
    """Return A's expected score against B using the classic Elo curve."""

    return 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 400.0))


def update_ratings(
    current: Mapping[str, RatingSnapshot],
    judgment: Judgment,
    *,
    k_factor: float = K_FACTOR,
) -> dict[str, RatingSnapshot]:
    """Apply all pairwise outcomes from a ranking against one rating snapshot.

    Pairwise deltas are calculated from the same pre-debate ratings, so ordering
    the calculations cannot affect the result. Dividing K across opponents keeps
    a multi-model event comparable in magnitude to a head-to-head event.
    """

    ordered = sorted(judgment.rankings, key=lambda entry: entry.rank)
    if len(ordered) < 2:
        return dict(current)

    baseline = {
        entry.model_id: current.get(
            entry.model_id,
            RatingSnapshot(model_id=entry.model_id, rating=DEFAULT_RATING),
        )
        for entry in ordered
    }
    deltas = dict.fromkeys(baseline, 0.0)
    pair_k = k_factor / (len(ordered) - 1)

    for index, higher in enumerate(ordered):
        for lower in ordered[index + 1 :]:
            higher_rating = baseline[higher.model_id].rating
            lower_rating = baseline[lower.model_id].rating
            higher_delta = pair_k * (1.0 - expected_score(higher_rating, lower_rating))
            lower_delta = pair_k * (0.0 - expected_score(lower_rating, higher_rating))
            deltas[higher.model_id] += higher_delta
            deltas[lower.model_id] += lower_delta

    updated = dict(current)
    winner_id = ordered[0].model_id
    for model_id, previous in baseline.items():
        updated[model_id] = RatingSnapshot(
            model_id=model_id,
            rating=round(previous.rating + deltas[model_id], 1),
            debates=previous.debates + 1,
            wins=previous.wins + int(model_id == winner_id),
        )
    return updated


def initialize_ratings(model_ids: list[str]) -> dict[str, RatingSnapshot]:
    """Create stable starting ratings for newly configured models."""

    return {
        model_id: RatingSnapshot(model_id=model_id, rating=DEFAULT_RATING)
        for model_id in model_ids
    }
