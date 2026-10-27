import pytest
import math

from src.engine import (
    TargetError,
    build_index,
    find_similar,
    resolve_target,
    tokens_from_source,
)
from src.extractor import extract_functions_from_source

SOURCE = """
def add_all(items):
    total = 0
    for x in items:
        total = total + x
    return total

def sum_values(values):
    acc = 0
    for v in values:
        acc = acc + v
    return acc

def greet(name):
    return "hi " + name

class Cart:
    def add(self, item):
        self.items.append(item)
"""

AMBIGUOUS = "if X:\n    def f(a):\n        return a\nelse:\n    def f(a):\n        return -a\n"


def _functions(source=SOURCE, path="pkg/mod.py"):
    return extract_functions_from_source(source, path)


def test_resolve_target_by_name_qualified_name_and_suffix():
    funcs = _functions()
    assert resolve_target(funcs, "pkg/mod.py:add_all").name == "add_all"
    assert resolve_target(funcs, "mod.py:add_all").name == "add_all"
    assert resolve_target(funcs, "pkg/mod.py:Cart.add").qualified_name == "Cart.add"
    assert resolve_target(funcs, "pkg/mod.py:add").qualified_name == "Cart.add"


def test_resolve_target_errors():
    funcs = _functions()
    with pytest.raises(TargetError, match="not found"):
        resolve_target(funcs, "pkg/mod.py:missing")
    with pytest.raises(TargetError, match="Invalid"):
        resolve_target(funcs, "no_colon_here")


def test_resolve_target_ambiguous_needs_lineno():
    funcs = _functions(AMBIGUOUS, "m.py")
    with pytest.raises(TargetError, match="ambiguous"):
        resolve_target(funcs, "m.py:f")
    assert resolve_target(funcs, "m.py:f:5").lineno == 5


def test_find_similar_ranks_excludes_self_and_flags_candidates():
    funcs = _functions()
    index = build_index(funcs)
    target = resolve_target(funcs, "pkg/mod.py:add_all")
    target_tokens = next(e.tokens for e in index if e.info is target)

    results = find_similar(target_tokens, index, top_k=10, exclude=target)

    assert all(r.function is not target for r in results)
    assert results[0].function.name == "sum_values"
    assert results[0].score == 1.0 and results[0].is_candidate
    assert [r.score for r in results] == sorted((r.score for r in results), reverse=True)
    greet = next(r for r in results if r.function.name == "greet")
    assert not greet.is_candidate


def test_find_similar_top_k_and_only_candidates():
    funcs = _functions()
    index = build_index(funcs)
    tokens = tokens_from_source("def f(a):\n    t = 0\n    for i in a:\n        t = t + i\n    return t\n")

    assert len(find_similar(tokens, index, top_k=2)) == 2
    only = find_similar(tokens, index, top_k=10, only_candidates=True)
    assert only and all(r.is_candidate for r in only)
    with pytest.raises(ValueError):
        find_similar(tokens, index, top_k=0)


def test_tokens_from_source_errors():
    with pytest.raises(TargetError, match="syntax"):
        tokens_from_source("def broken(:\n    pass\n")
    with pytest.raises(TargetError, match="function"):
        tokens_from_source("x = 1\n")
        
        
def test_resolve_target_strips_root_prefix():
    funcs = _functions(path="mod.py")
    assert resolve_target(funcs, "pkg/mod.py:add_all", root_dir="pkg").name == "add_all"
    with pytest.raises(TargetError, match="not found"):
        resolve_target(funcs, "pkg/mod.py:add_all")


def test_build_index_skips_functions_that_fail(monkeypatch):
    import src.engine as engine
    real = engine.function_tokens

    def flaky(node, index_vars):
        if node.name == "greet":
            raise RuntimeError("boom")
        return real(node, index_vars=index_vars)

    monkeypatch.setattr(engine, "function_tokens", flaky)
    names = {e.info.name for e in engine.build_index(_functions())}
    assert "greet" not in names and "add_all" in names


def test_find_similar_rejects_invalid_thresholds_and_n():
    with pytest.raises(ValueError, match="finite number between 0.0 and 1.0"):
        find_similar((), [], threshold=-0.1)
    with pytest.raises(ValueError, match="finite number between 0.0 and 1.0"):
        find_similar((), [], threshold=1.1)
    with pytest.raises(ValueError, match="finite number between 0.0 and 1.0"):
        find_similar((), [], threshold=math.nan)
        
    for invalid_n in (0, -1):
        with pytest.raises(ValueError, match="must be >= 1"):
            find_similar((), [], metric="jaccard", n=invalid_n)