import logging
import math
import textwrap
from dataclasses import dataclass
from pathlib import Path

from src.extractor import extract_functions_from_source
from src.models import FunctionInfo
from src.serializer import function_tokens
from src.similarity import (
    DEFAULT_INDEX_VARS,
    DEFAULT_NGRAM_SIZE,
    METRICS,
    Metric,
    compute_similarity,
    default_threshold,
)

logger = logging.getLogger(__name__)


class TargetError(ValueError):
    """The target function could not be resolved or parsed."""


@dataclass(frozen=True)
class IndexedFunction:
    info: FunctionInfo
    tokens: tuple[str, ...]


@dataclass(frozen=True)
class SearchResult:
    function: FunctionInfo
    score: float
    metric: Metric
    is_candidate: bool


def build_index(
    functions: list[FunctionInfo], index_vars: bool = DEFAULT_INDEX_VARS
) -> list[IndexedFunction]:
    """Normalize and serialize every function once, ignoring unparseable edge cases."""
    index: list[IndexedFunction] = []
    for f in functions:
        try:
            tokens = function_tokens(f.node, index_vars=index_vars)
            index.append(IndexedFunction(f, tuple(tokens)))
        except Exception as exc:
            logger.warning("Skipping %s due to serialization error: %s", f.identifier, exc)
    return index


def _same_file(file_path: str, wanted: str) -> bool:
    """Match a stored path against an exact or suffix path specification."""
    stored = file_path.replace("\\", "/").removeprefix("./")
    requested = wanted.replace("\\", "/").removeprefix("./")
    return stored == requested or stored.endswith("/" + requested)


def resolve_target(
    functions: list[FunctionInfo], spec: str, root_dir: str | Path | None = None
) -> FunctionInfo:
    """Resolve 'file.py:name' or 'file.py:name:lineno' to a single FunctionInfo."""
    spec = spec.replace("\\", "/").removeprefix("./")
    
    if root_dir is not None:
        for base in {Path(root_dir).as_posix(), Path(root_dir).resolve().as_posix()}:
            prefix = base.rstrip("/") + "/"
            if spec.startswith(prefix):
                spec = spec[len(prefix):]
                break

    parts = spec.split(":")
    lineno = int(parts.pop()) if len(parts) >= 3 and parts[-1].isdigit() else None
    if len(parts) < 2 or not parts[0] or not parts[-1]:
        raise TargetError(f"Invalid target {spec!r}; expected 'file.py:name'")

    name = parts[-1]
    file_part = ":".join(parts[:-1]).removeprefix("./")

    in_file = [f for f in functions if _same_file(f.file_path, file_part)]
    
    candidates = [f for f in in_file if f.qualified_name == name] or [
        f for f in in_file if f.name == name
    ]
    if lineno is not None:
        candidates = [f for f in candidates if f.lineno == lineno]

    if not candidates:
        raise TargetError(f"Function not found: {spec!r}")
    if len(candidates) > 1:
        options = ", ".join(f"{f.identifier}:{f.lineno}" for f in candidates)
        raise TargetError(f"Target {spec!r} is ambiguous; use one of: {options}")
    return candidates[0]


def tokens_from_source(
    code: str, index_vars: bool = DEFAULT_INDEX_VARS
) -> tuple[str, ...]:
    """Parse and tokenize the first function found in raw source code."""
    try:
        found = extract_functions_from_source(textwrap.dedent(code))
    except SyntaxError as exc:
        raise TargetError(f"Pasted code has a syntax error: {exc.msg}") from exc
    if not found:
        raise TargetError("Pasted code does not contain any function definition")
    try:
        return tuple(function_tokens(found[0].node, index_vars=index_vars))
    except RecursionError as exc:
        raise TargetError("Target function is too deeply nested to analyze") from exc
    except Exception as exc:
        raise TargetError(f"Could not tokenize target function: {exc}") from exc


def find_similar(
    target_tokens: tuple[str, ...],
    index: list[IndexedFunction],
    *,
    metric: Metric = "jaccard",
    top_k: int = 5,
    n: int = DEFAULT_NGRAM_SIZE,
    threshold: float | None = None,
    exclude: FunctionInfo | None = None,
    only_candidates: bool = False,
) -> list[SearchResult]:
    """Rank indexed functions by similarity to the target tokens (best first)."""
    if top_k < 1:
        raise ValueError(f"top_k must be >= 1, got {top_k}")
    if metric not in METRICS:
        raise ValueError(f"Unknown similarity metric: {metric!r}")
    if metric == "jaccard":
        if not isinstance(n, int) or isinstance(n, bool) or n < 1:
            raise ValueError(f"n must be a positive integer for Jaccard, got {n!r}")
    
    limit = default_threshold(metric) if threshold is None else threshold
    if not math.isfinite(limit) or not (0.0 <= limit <= 1.0):
        raise ValueError(f"Threshold must be a finite number between 0.0 and 1.0, got {limit}")

    results: list[SearchResult] = []
    for entry in index:
        if exclude is not None and entry.info is exclude:
            continue
        score = compute_similarity(target_tokens, entry.tokens, metric=metric, n=n)
        results.append(SearchResult(entry.info, score, metric, score >= limit))

    if only_candidates:
        results = [r for r in results if r.is_candidate]
    
    results.sort(key=lambda r: (-r.score, r.function.identifier, r.function.lineno))
    return results[:top_k]