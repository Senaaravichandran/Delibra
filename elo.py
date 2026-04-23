K = 32  # How fast ratings change. 32 = standard for chess.


def expected_score(rating_a, rating_b):
    """
    Probability that A beats B based on rating difference.
    """
    return 1 / (1 + 10 ** ((rating_b - rating_a) / 400))


def update_elo(winner_rating, loser_rating):
    """
    winner_rating = current ELO of winner
    loser_rating  = current ELO of loser

    Returns: (new_winner_rating, new_loser_rating)
    """
    expected_winner = expected_score(winner_rating, loser_rating)
    expected_loser  = expected_score(loser_rating, winner_rating)

    new_winner = winner_rating + K * (1 - expected_winner)
    new_loser  = loser_rating  + K * (0 - expected_loser)

    return round(new_winner, 1), round(new_loser, 1)


if __name__ == "__main__":
    gpt   = 1500
    llama = 1500

    # LLaMA wins!
    llama, gpt = update_elo(llama, gpt)
    print(f"LLaMA: {llama}, GPT: {gpt}")  # LLaMA: 1516.0, GPT: 1484.0