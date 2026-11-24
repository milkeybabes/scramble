"""Original 1981 Scramble ten-place score ranking.

Z80: $1346 GET_HIGH_SCORE_INDEX, $137F score insertion, $130E row
highlight. Only six decimal digits are stored per score (three BCD bytes).
There is no initials-entry screen in the original Konami program.
"""
from __future__ import annotations

RANKING_SIZE = 10
INITIAL_RANKING_SCORE = 10000
MAX_SCORE = 999999


def initial_ranking():
    return [INITIAL_RANKING_SCORE] * RANKING_SIZE


def validate_ranking(ranking):
    values = [int(s) for s in ranking]
    if (len(values) != RANKING_SIZE
            or any(s < 0 or s > MAX_SCORE for s in values)
            or values != sorted(values, reverse=True)):
        raise ValueError('High-score ranking must be ten descending six-digit scores')
    return values


def record_score(ranking, score):
    """Insert a completed player's score; return (new_rank, inserted).

    Original $135D-$137F: comparison begins with the highest BCD pair.
    If the score exactly matches an existing entry, return its index without
    shifting the table. A lower score scans down; a strictly higher score
    shifts that entry and everything below it one place to the right.

    The sentinel rank 10 indicates the score failed to reach the top ten.
    """
    current = validate_ranking(ranking)
    score = int(score)
    if not 0 <= score <= MAX_SCORE:
        raise ValueError('Score must be within the six-digit BCD range')
    for index, value in enumerate(current):
        if score == value:
            return index, False
        if score > value:
            current.insert(index, score)
            del current[RANKING_SIZE:]
            ranking[:] = current
            return index, True
    return RANKING_SIZE, False
