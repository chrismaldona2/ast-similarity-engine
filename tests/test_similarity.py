import ast
import pytest

from tests.pairs import PAIRS, parse_fn
from src.serializer import function_tokens
from src.similarity import (
    DEFAULT_INDEX_VARS,
    THRESHOLDS,
    compute_similarity,
    default_threshold,
    jaccard_similarity,
    levenshtein_distance,
    levenshtein_similarity,
    ngrams,
)


def _func(source: str) -> ast.FunctionDef:
    return ast.parse(source).body[0]


def test_ngrams_basic_and_short_sequences():
    tokens = ["A", "B", "C", "D"]
    assert ngrams(tokens, n=3) == {("A", "B", "C"), ("B", "C", "D")}
    assert ngrams(["A", "B"], n=3) == {("A", "B")}
    assert ngrams([], n=3) == set()

    with pytest.raises(ValueError):
        ngrams(tokens, n=0)


def test_jaccard_extremes():
    seq = ["FunctionDef:FUNC", "arguments", "Return", "Constant:LIT"]
    assert jaccard_similarity(seq, seq, n=3) == 1.0
    assert jaccard_similarity(seq, ["A", "B", "C", "D"], n=3) == 0.0
    assert jaccard_similarity([], [], n=3) == 1.0
    assert jaccard_similarity(seq, [], n=3) == 0.0


def test_jaccard_short_sequences():
    assert jaccard_similarity(["A", "B"], ["A", "B"], n=3) == 1.0
    assert jaccard_similarity(["A", "B"], ["A", "C"], n=3) == 0.0


def test_levenshtein_distance_and_similarity():
    a = ["A", "B", "C", "D"]
    b = ["A", "X", "C", "D"]  # 1 substitution out of 4 tokens
    assert levenshtein_distance(a, b) == 1
    assert levenshtein_similarity(a, b) == pytest.approx(0.75)

    assert levenshtein_similarity(a, a) == 1.0
    assert levenshtein_similarity([], []) == 1.0
    assert levenshtein_similarity(a, []) == 0.0
    assert levenshtein_similarity(["A", "B"], ["C", "D"]) == 0.0


def test_similarity_is_symmetric():
    a = ["A", "B", "C", "D", "E"]
    b = ["A", "B", "X", "D", "E", "F"]
    assert jaccard_similarity(a, b) == jaccard_similarity(b, a)
    assert levenshtein_similarity(a, b) == levenshtein_similarity(b, a)


def test_renamed_functions_have_maximum_similarity():
    fn_a = _func(
        "def first(a, b):\n"
        "    result = a + b\n"
        "    return result * 2\n"
    )
    fn_b = _func(
        "def second(x, y):\n"
        "    total = x + y\n"
        "    return total * 5\n"
    )
    tokens_a = function_tokens(fn_a, index_vars=DEFAULT_INDEX_VARS)
    tokens_b = function_tokens(fn_b, index_vars=DEFAULT_INDEX_VARS)

    assert jaccard_similarity(tokens_a, tokens_b) == 1.0
    assert levenshtein_similarity(tokens_a, tokens_b) == 1.0


def test_unindexed_vars_tolerate_block_reordering():
    # Demonstrates that with index_vars=False, reordering independent 
    # statements yields very high similarity in both metrics (> 0.80)
    fn_a = _func(
        "def first(items):\n"
        "    total = sum(items) + 1\n"
        "    count = len(items) * 2\n"
        "    return total / count\n"
    )
    fn_b = _func(
        "def second(items):\n"
        "    count = len(items) * 2\n"
        "    total = sum(items) + 1\n"
        "    return total / count\n"
    )
    seq_a = function_tokens(fn_a, index_vars=False)
    seq_b = function_tokens(fn_b, index_vars=False)

    jaccard = jaccard_similarity(seq_a, seq_b, n=3)
    lev = levenshtein_similarity(seq_a, seq_b)

    assert jaccard > 0.80
    assert lev > 0.80


def test_compute_similarity_dispatcher():
    seq = ["A", "B", "C"]
    assert compute_similarity(seq, seq, metric="jaccard") == 1.0
    assert compute_similarity(seq, seq, metric="levenshtein") == 1.0
    assert default_threshold("jaccard") == THRESHOLDS["jaccard"]
    assert default_threshold("levenshtein") == THRESHOLDS["levenshtein"]

    with pytest.raises(ValueError):
        compute_similarity(seq, seq, metric="cosine")  # type: ignore[arg-type]

    with pytest.raises(ValueError):
        default_threshold("cosine")  # type: ignore[arg-type]


def test_index_vars_false_loses_variable_identity_distinction():
    # Documented trade-off: with index_vars=False, 'a + a' and 'a + b' emit identical tokens
    fn_same = _func("def f(a, b):\n    return a + a\n")
    fn_diff = _func("def f(a, b):\n    return a + b\n")

    assert function_tokens(fn_same, index_vars=False) == function_tokens(
        fn_diff, index_vars=False
    )
    assert function_tokens(fn_same, index_vars=True) != function_tokens(
        fn_diff, index_vars=True
)


@pytest.mark.parametrize("metric", ["jaccard", "levenshtein"])
@pytest.mark.parametrize("label,is_clone,code_a,code_b", PAIRS)
def test_threshold_separates_clones_from_non_clones(
    metric, label, is_clone, code_a, code_b
):
    tok_a = function_tokens(parse_fn(code_a), index_vars=DEFAULT_INDEX_VARS)
    tok_b = function_tokens(parse_fn(code_b), index_vars=DEFAULT_INDEX_VARS)
    score = compute_similarity(tok_a, tok_b, metric=metric)
    assert (score >= THRESHOLDS[metric]) == is_clone, f"{label}: {score:.3f}"
    
    
