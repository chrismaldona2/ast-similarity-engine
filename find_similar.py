import argparse
import logging
import sys
from pathlib import Path

from src.engine import (
    TargetError,
    build_index,
    find_similar,
    resolve_target,
    tokens_from_source,
)
from src.extractor import extract_functions
from src.serializer import DEFAULT_INDEX_VARS
from src.similarity import METRICS, default_threshold


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Find structurally similar Python functions via AST comparison."
    )
    parser.add_argument(
        "--dir",
        type=Path,
        default=Path("."),
        help="Root directory to scan for candidate functions (default: current dir).",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--function",
        "--funcion",
        dest="function",
        type=str,
        help="Target function inside the scanned directory (e.g., 'pkg/mod.py:my_func').",
    )
    group.add_argument(
        "--query-file",
        type=str,
        help="External Python file containing the reference function (or '-' for stdin).",
    )
    parser.add_argument(
        "--top-k",
        "--top",
        dest="top_k",
        type=int,
        default=5,
        help="Maximum number of results to display (default: 5).",
    )
    parser.add_argument(
        "--metric",
        type=str,
        choices=METRICS,
        default="jaccard",
        help="Similarity metric (default: jaccard).",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=None,
        help="Custom minimum similarity score [0.0 - 1.0] (default: calibrated per-metric).",
    )
    parser.add_argument(
        "--only-candidates",
        action="store_true",
        help="Show only results that meet the similarity threshold.",
    )
    parser.add_argument(
        "--index-vars",
        action=argparse.BooleanOptionalAction,
        default=DEFAULT_INDEX_VARS,
        help="Preserve variable identity mapping (e.g. VAR1 vs VAR2). Defaults to False to tolerate reordered lines.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    parser = build_parser()
    args = parser.parse_args(argv)

    root_dir = args.dir
    if not root_dir.is_dir():
        print(f"Error: Directory '{root_dir}' does not exist.", file=sys.stderr)
        return 1

    print(f"Scanning directory: {root_dir}", file=sys.stderr)
    print("Extracting functions... ", end="", flush=True, file=sys.stderr)
    functions = extract_functions(root_dir)
    print(f"Found {len(functions)}.", file=sys.stderr)

    if not functions:
        print("No Python functions found to compare against.", file=sys.stderr)
        return 1

    print(f"Building AST index (index_vars={args.index_vars})... ", end="", flush=True, file=sys.stderr)
    index = build_index(functions, index_vars=args.index_vars)
    print(f"Indexed {len(index)} functions.\n", file=sys.stderr)
    
    if not index:
        print("Error: No functions could be indexed successfully.", file=sys.stderr)
        return 1

    threshold = args.threshold if args.threshold is not None else default_threshold(args.metric)
    exclude_func = None

    try:
        if args.function:
            target_func = resolve_target(functions, args.function, root_dir=root_dir)
            entry = next((e for e in index if e.info is target_func), None)
            if entry is None:
                raise TargetError(f"Could not tokenize target function: {target_func.identifier}")
            target_tokens = entry.tokens
            exclude_func = target_func
            print(f"Target: {target_func.identifier} (Line {target_func.lineno})", file=sys.stderr)
        else:
            if args.query_file == "-":
                code = sys.stdin.read()
                print("Target: First function from <stdin>", file=sys.stderr)
            else:
                q_path = Path(args.query_file)
                if not q_path.is_file():
                    raise TargetError(f"Query file does not exist: {q_path}")
                try:
                    code = q_path.read_text(encoding="utf-8-sig")
                except (OSError, UnicodeError) as exc:
                    raise TargetError(f"Could not read query file {q_path}: {exc}") from exc
                print(f"Target: First function in {q_path}", file=sys.stderr)
            
            target_tokens = tokens_from_source(code, index_vars=args.index_vars)

        print(f"Metric: {args.metric} (Threshold >= {threshold:.2f})\n", file=sys.stderr)

        results = find_similar(
            target_tokens=target_tokens,
            index=index,
            metric=args.metric,
            top_k=args.top_k,
            threshold=threshold,
            exclude=exclude_func,
            only_candidates=args.only_candidates,
        )

    except (TargetError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if not results:
        print("No matches found.")
        return 0

    header = f"{'Rank':<5} | {'Score':<7} | {'Candidate?':<10} | {'Function (File:Name:Line)'}"
    print(header)
    print("-" * 85)

    for i, res in enumerate(results, start=1):
        pct = f"{res.score * 100:>5.1f}%"
        tag = "[YES]" if res.is_candidate else " -- "
        loc = f"{res.function.identifier}:{res.function.lineno}"
        print(f"{i:<5} | {pct:<7} | {tag:<10} | {loc}")

    return 0


if __name__ == "__main__":
    sys.exit(main())