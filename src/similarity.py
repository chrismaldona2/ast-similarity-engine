from collections.abc import Sequence
from typing import Literal

Metric = Literal["jaccard", "levenshtein"]
METRICS: tuple[Metric, ...] = ("jaccard", "levenshtein")

# Default parameters calibrated via lab/calibrate.py.
DEFAULT_NGRAM_SIZE = 3

THRESHOLDS: dict[Metric, float] = {
    "jaccard": 0.50,
    "levenshtein": 0.72,
}


def default_threshold(metric: Metric = "jaccard") -> float:
    """Return the calibrated default similarity threshold for the given metric."""
    if metric not in THRESHOLDS:
        raise ValueError(f"Unknown similarity metric: {metric!r}")
    return THRESHOLDS[metric]


def ngrams(tokens: Sequence[str], n: int = DEFAULT_NGRAM_SIZE) -> set[tuple[str, ...]]:
    """Return the set of contiguous n-grams from a token sequence.

    If the sequence is non-empty but shorter than n, the entire sequence
    is returned as a single tuple so short sequences can still be compared.
    """
    if n < 1:
        raise ValueError(f"n-gram size must be >= 1, got {n}")
    if not tokens:
        return set()
    if len(tokens) < n:
        return {tuple(tokens)}
    return {tuple(tokens[i : i + n]) for i in range(len(tokens) - n + 1)}


def jaccard_similarity(
    seq_a: Sequence[str],
    seq_b: Sequence[str],
    n: int = DEFAULT_NGRAM_SIZE,
) -> float:
    """Compute Jaccard similarity in [0.0, 1.0] between the n-gram sets of two sequences."""
    set_a = ngrams(seq_a, n=n)
    set_b = ngrams(seq_b, n=n)
    if not set_a and not set_b:
        return 1.0
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


def levenshtein_distance(seq_a: Sequence[str], seq_b: Sequence[str]) -> int:
    """Compute the token-level edit distance (insert, delete, substitute) between two sequences."""
    if len(seq_a) < len(seq_b):
        seq_a, seq_b = seq_b, seq_a

    if not seq_b:
        return len(seq_a)

    prev_row = list(range(len(seq_b) + 1))
    for i, token_a in enumerate(seq_a, start=1):
        curr_row = [i]
        for j, token_b in enumerate(seq_b, start=1):
            insert_cost = curr_row[j - 1] + 1
            delete_cost = prev_row[j] + 1
            replace_cost = prev_row[j - 1] + (0 if token_a == token_b else 1)
            curr_row.append(min(insert_cost, delete_cost, replace_cost))
        prev_row = curr_row

    return prev_row[-1]


def levenshtein_similarity(seq_a: Sequence[str], seq_b: Sequence[str]) -> float:
    """Compute normalized Levenshtein similarity in [0.0, 1.0]."""
    if not seq_a and not seq_b:
        return 1.0
    max_len = max(len(seq_a), len(seq_b))
    distance = levenshtein_distance(seq_a, seq_b)
    return 1.0 - (distance / max_len)


def compute_similarity(
    seq_a: Sequence[str],
    seq_b: Sequence[str],
    metric: Metric = "jaccard",
    n: int = DEFAULT_NGRAM_SIZE,
) -> float:
    """Dispatch similarity calculation to the selected metric ('jaccard' or 'levenshtein')."""
    if metric == "jaccard":
        return jaccard_similarity(seq_a, seq_b, n=n)
    if metric == "levenshtein":
        return levenshtein_similarity(seq_a, seq_b)
    raise ValueError(f"Unknown similarity metric: {metric!r}")