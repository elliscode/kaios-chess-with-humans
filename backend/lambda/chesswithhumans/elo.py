DEFAULT_ELO = 1200
K_FACTOR = 32


def expected_score(rating, opponent_rating):
    return 1 / (1 + 10 ** ((opponent_rating - rating) / 400))


def apply_result(rating_a, rating_b, score_a):
    # score_a: 1 for a win, 0 for a loss, 0.5 for a draw
    expected_a = expected_score(rating_a, rating_b)
    new_rating_a = round(rating_a + K_FACTOR * (score_a - expected_a))
    new_rating_b = round(rating_b + K_FACTOR * ((1 - score_a) - (1 - expected_a)))
    return new_rating_a, new_rating_b
