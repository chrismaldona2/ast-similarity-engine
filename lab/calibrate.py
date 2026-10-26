import sys
from pathlib import Path

# Allow running directly as `python lab/calibrate.py` from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.serializer import function_tokens
from src.similarity import THRESHOLDS, jaccard_similarity, levenshtein_similarity
from tests.pairs import PAIRS, parse_fn


def run_calibration(index_vars: bool) -> None:
    mode = "index_vars=True (VAR1, VAR2...)" if index_vars else "index_vars=False (VAR)"
    j_thr = THRESHOLDS["jaccard"]
    l_thr = THRESHOLDS["levenshtein"]
    j_col = f"J3>={j_thr:.2f}"
    l_col = f"Lev>={l_thr:.2f}"

    print(f"\n=== Calibration Table [{mode}] ===")
    header = (
        f"{'Pair':<32} | {'Clone':<5} | {'J(n=2)':>6} | {'J(n=3)':>6} | "
        f"{'J(n=4)':>6} | {'Leven':>6} | {j_col:>8} | {l_col:>9}"
    )
    print(header)
    print("-" * len(header))

    pos_scores: list[tuple[float, float, float, float]] = []
    neg_scores: list[tuple[float, float, float, float]] = []

    for label, is_clone, code_a, code_b in PAIRS:
        fn_a = parse_fn(code_a)
        fn_b = parse_fn(code_b)
        tok_a = function_tokens(fn_a, index_vars=index_vars)
        tok_b = function_tokens(fn_b, index_vars=index_vars)

        j2 = jaccard_similarity(tok_a, tok_b, n=2)
        j3 = jaccard_similarity(tok_a, tok_b, n=3)
        j4 = jaccard_similarity(tok_a, tok_b, n=4)
        lev = levenshtein_similarity(tok_a, tok_b)

        row = (j2, j3, j4, lev)
        if is_clone:
            pos_scores.append(row)
        else:
            neg_scores.append(row)

        tag = "YES" if is_clone else "NO"
        j3_ok = "OK" if (j3 >= j_thr) == is_clone else "MISS"
        lev_ok = "OK" if (lev >= l_thr) == is_clone else "MISS"
        print(
            f"{label:<32} | {tag:<5} | {j2:6.3f} | {j3:6.3f} | "
            f"{j4:6.3f} | {lev:6.3f} | {j3_ok:>8} | {lev_ok:>9}"
        )

    print("-" * len(header))
    min_pos = [min(col) for col in zip(*pos_scores)]
    max_neg = [max(col) for col in zip(*neg_scores)]
    margins = [p - n for p, n in zip(min_pos, max_neg)]

    print(
        f"{'Min Clone (YES)':<32} | {'-':<5} | {min_pos[0]:6.3f} | {min_pos[1]:6.3f} | "
        f"{min_pos[2]:6.3f} | {min_pos[3]:6.3f} |"
    )
    print(
        f"{'Max Non-Clone (NO)':<32} | {'-':<5} | {max_neg[0]:6.3f} | {max_neg[1]:6.3f} | "
        f"{max_neg[2]:6.3f} | {max_neg[3]:6.3f} |"
    )
    print(
        f"{'Separation Margin (Min - Max)':<32} | {'-':<5} | {margins[0]:6.3f} | {margins[1]:6.3f} | "
        f"{margins[2]:6.3f} | {margins[3]:6.3f} |"
    )


if __name__ == "__main__":
    run_calibration(index_vars=True)
    run_calibration(index_vars=False)