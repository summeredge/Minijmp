"""Verify the frozen Split-Plot reference with exact model-matrix projections."""
from copy import deepcopy
from fractions import Fraction
from itertools import combinations, product
import hashlib
import json
import math
from pathlib import Path

import scipy
from scipy.stats import f


HERE = Path(__file__).resolve().parent


def close(actual, expected, tolerance=2e-12):
    if actual is None or expected is None:
        assert actual is expected
    else:
        assert abs(float(actual) - float(expected)) <= tolerance * max(1, abs(float(expected)))


def factorial_terms(factors):
    return [item for order in range(1, len(factors) + 1)
            for item in combinations(factors, order)]


def rank_exact(matrix):
    work = [[Fraction(value) for value in row] for row in matrix]
    row_count, column_count = len(work), len(work[0])
    pivot_row = 0
    for column in range(column_count):
        pivot = next((row for row in range(pivot_row, row_count)
                      if work[row][column]), None)
        if pivot is None:
            continue
        work[pivot_row], work[pivot] = work[pivot], work[pivot_row]
        divisor = work[pivot_row][column]
        work[pivot_row] = [value / divisor for value in work[pivot_row]]
        for row in range(row_count):
            if row != pivot_row and work[row][column]:
                multiplier = work[row][column]
                work[row] = [left - multiplier * right
                             for left, right in zip(work[row], work[pivot_row])]
        pivot_row += 1
        if pivot_row == row_count:
            break
    return pivot_row


def solve_exact(matrix, values):
    size = len(matrix)
    work = [[Fraction(value) for value in row] + [Fraction(target)]
            for row, target in zip(matrix, values)]
    for column in range(size):
        pivot = next((row for row in range(column, size)
                      if work[row][column]), None)
        if pivot is None:
            raise ValueError("singular projection matrix")
        work[column], work[pivot] = work[pivot], work[column]
        divisor = work[column][column]
        work[column] = [value / divisor for value in work[column]]
        for row in range(size):
            if row != column and work[row][column]:
                multiplier = work[row][column]
                work[row] = [left - multiplier * right
                             for left, right in zip(work[row], work[column])]
    return [row[-1] for row in work]


def project(matrix, response):
    """Least-squares projection via the exact normal equations X'X beta = X'y."""
    columns = list(zip(*matrix))
    gram = [[sum((left * right for left, right in zip(a, b)), Fraction())
             for b in columns] for a in columns]
    rhs = [sum((value * y for value, y in zip(column, response)), Fraction())
           for column in columns]
    beta = solve_exact(gram, rhs)
    fitted = [sum((x * coefficient for x, coefficient in zip(row, beta)), Fraction())
              for row in matrix]
    residual = [y - fit for y, fit in zip(response, fitted)]
    return beta, fitted, residual


def model_matrix(rows, factors, blocks):
    terms = factorial_terms(factors)
    matrix = [[int(row["block"] == block) for block in blocks]
              + [coded(row, term) for term in terms] for row in rows]
    return matrix, terms


def coded(row, subset):
    value = 1
    for factor in subset:
        value *= row["levels"][factor]
    return value


def projection_case(case):
    """Compute SS as differences of independent model-space projections."""
    rows, factors = case["rows"], case["factors"]
    hard, easy = case["hard_factors"], case["easy_factors"]
    blocks = sorted({row["block"] for row in rows})
    terms = factorial_terms(factors)
    n, r = len(rows), len(blocks)
    hard_count, easy_count = 1 << len(hard), 1 << len(easy)
    y = [Fraction(row["y"]) for row in rows]
    grand = sum(y, Fraction()) / n
    block_columns = [[Fraction(row["block"] == block) for block in blocks]
                     for row in rows]
    term_columns = [[Fraction(coded(row, term)) for term in terms] for row in rows]
    full_matrix = [block + treatment for block, treatment in
                   zip(block_columns, term_columns)]
    model_rank = rank_exact(full_matrix)
    full_beta, _, full_residual = project(full_matrix, y)
    gram = [[sum((left * right for left, right in zip(a, b)), Fraction())
             for b in zip(*full_matrix)] for a in zip(*full_matrix)]
    assert all(gram[i][j] == 0 for i in range(len(gram))
               for j in range(len(gram)) if i != j)

    centered = [value - grand for value in y]
    _, block_fit, _ = project(block_columns, centered)
    ss_block = sum((value * value for value in block_fit), Fraction())
    ss_total = sum((value * value for value in centered), Fraction())
    ss_terms, coefficients = {}, {}
    for index, term in enumerate(terms):
        name = ":".join(term)
        coefficient = full_beta[len(blocks) + index]
        column_norm = sum((row[index] * row[index] for row in term_columns), Fraction())
        # The exact full-model columns are orthogonal, so deleting this column
        # increases residual SS by its one-column projection SS.
        ss_terms[term] = coefficient * coefficient * column_norm
        coefficients[term] = coefficient

    plot_members = {}
    for index, row in enumerate(rows):
        key = (row["block"], tuple(row["levels"][factor] for factor in hard))
        plot_members.setdefault(key, []).append(index)
    plot_keys = list(plot_members)
    plot_means = [sum((y[i] for i in plot_members[key]), Fraction()) / easy_count
                  for key in plot_keys]
    hard_terms = [term for term in terms if set(term) <= set(hard)]
    wp_matrix = []
    for block, levels in plot_keys:
        hard_row = {"levels": dict(zip(hard, levels))}
        wp_matrix.append([Fraction(block == selected) for selected in blocks]
                         + [Fraction(coded(hard_row, term)) for term in hard_terms])
    _, _, wp_residual = project(wp_matrix, plot_means)
    ss_wp = easy_count * sum((value * value for value in wp_residual), Fraction())
    wp_by_key = dict(zip(plot_keys, wp_residual))
    subplot_residual = []
    for index, row in enumerate(rows):
        key = (row["block"], tuple(row["levels"][factor] for factor in hard))
        subplot_residual.append(full_residual[index] - wp_by_key[key])
    ss_subplot = sum((value * value for value in subplot_residual), Fraction())

    df_total, df_block = n - 1, r - 1
    df_wp = (r - 1) * (hard_count - 1)
    df_sp = hard_count * (r - 1) * (easy_count - 1)
    assert df_total == (df_block + hard_count - 1 + df_wp
                        + hard_count * (easy_count - 1) + df_sp)
    partition = ss_block + sum(ss_terms.values(), Fraction()) + ss_wp + ss_subplot
    assert ss_total == partition, (
        case["case_id"], float(ss_total), float(ss_block),
        {":".join(term): float(value) for term, value in ss_terms.items()},
        float(ss_wp), float(ss_subplot), float(ss_total - partition))
    mse_wp = ss_wp / df_wp if df_wp else None
    mse_sp = ss_subplot / df_sp if df_sp else None

    term_results = {}
    for term in terms:
        name = ":".join(term)
        hard_only = set(term) <= set(hard)
        error_ss, error_df = (ss_wp, df_wp) if hard_only else (ss_subplot, df_sp)
        mse = mse_wp if hard_only else mse_sp
        term_ss = ss_terms[term]
        f_value = float(term_ss / mse) if mse is not None and mse > 0 else None
        term_results[name] = {
            "coefficient": float(coefficients[term]),
            "effect": float(2 * coefficients[term]),
            "ss": float(term_ss), "df": 1, "ms": float(term_ss),
            "error_stratum": "whole_plot_error" if hard_only else "subplot_error",
            "error_df": error_df, "f": f_value,
            "p": float(f.sf(f_value, 1, error_df)) if f_value is not None else None,
        }
    return {
        "summary": {
            "n": n, "blocks": r, "hard_factors": len(hard),
            "easy_factors": len(easy), "hard_combinations": hard_count,
            "subplots_per_whole_plot": easy_count, "whole_plots": len(plot_members),
            "df_total": df_total, "df_block": df_block,
            "df_hard_effects": hard_count - 1, "df_whole_plot_error": df_wp,
            "df_easy_terms": hard_count * (easy_count - 1),
            "df_subplot_error": df_sp, "model_rank": model_rank,
            "ss_total": float(ss_total), "ss_block": float(ss_block),
            "ss_whole_plot_error": float(ss_wp),
            "ss_subplot_error": float(ss_subplot),
            "ss_terms": {":".join(term): float(ss_terms[term]) for term in terms},
        },
        "terms": term_results,
    }


def validate_units(rows, factors, hard, easy, block_count):
    expected_n = block_count * (1 << (len(hard) + len(easy)))
    if len(rows) != expected_n:
        raise ValueError("run count")
    for field in ("run_id", "standard_order", "run_order", "subplot_id"):
        if len({row[field] for row in rows}) != expected_n:
            raise ValueError(field)
    if len({row["whole_plot_id"] for row in rows}) != block_count * (1 << len(hard)):
        raise ValueError("whole_plot_id")
    if {row["block"] for row in rows} != set(range(1, block_count + 1)):
        raise ValueError("block set")
    if sorted(row["run_order"] for row in rows) != list(range(1, expected_n + 1)):
        raise ValueError("run order")
    if sorted(row["standard_order"] for row in rows) != list(range(1, expected_n + 1)):
        raise ValueError("standard order")
    hard_combinations = list(product((-1, 1), repeat=len(hard)))
    easy_combinations = list(product((-1, 1), repeat=len(easy)))
    hard_order = {values: index for index, values in enumerate(hard_combinations, 1)}
    easy_order = {values: index for index, values in enumerate(easy_combinations, 1)}
    easy_per_block = len(hard_combinations) * len(easy_combinations)
    for row in rows:
        if row["y"] is None or not math.isfinite(float(row["y"])):
            raise ValueError("response")
        if set(row["levels"]) != set(factors) or any(
                row["levels"][factor] not in (-1, 1) for factor in factors):
            raise ValueError("factor level")
        hard_levels = tuple(row["levels"][factor] for factor in hard)
        easy_levels = tuple(row["levels"][factor] for factor in easy)
        hard_index, easy_index = hard_order[hard_levels], easy_order[easy_levels]
        expected_order = ((row["block"] - 1) * easy_per_block
                          + (hard_index - 1) * len(easy_combinations) + easy_index)
        if (row["standard_order"] != expected_order
                or row["run_order"] != expected_order
                or row["run_id"] != f"R{expected_order:05d}"
                or row["whole_plot_id"] != f"WP{row['block']:05d}H{hard_index}"
                or row["subplot_id"] != f"SP{row['block']:05d}H{hard_index}E{easy_index}"
                or row["whole_plot_order"] != hard_index
                or row["subplot_order"] != easy_index):
            raise ValueError("identity or nested order")

    plots = {}
    for row in rows:
        plots.setdefault(row["whole_plot_id"], []).append(row)
    hard_codes = set(product((-1, 1), repeat=len(hard)))
    easy_codes = set(product((-1, 1), repeat=len(easy)))
    for group in plots.values():
        if len(group) != len(easy_codes):
            raise ValueError("subplot count")
        if len({row["block"] for row in group}) != 1:
            raise ValueError("whole plot block")
        if len({tuple(row["levels"][factor] for factor in hard) for row in group}) != 1:
            raise ValueError("hard levels")
        if {tuple(row["levels"][factor] for factor in easy) for row in group} != easy_codes:
            raise ValueError("easy combinations")
        if len({row["whole_plot_order"] for row in group}) != 1:
            raise ValueError("whole plot order")
        if {row["subplot_order"] for row in group} != set(range(1, len(group) + 1)):
            raise ValueError("subplot order")
    for block in range(1, block_count + 1):
        block_rows = [row for row in rows if row["block"] == block]
        block_plots = [group[0] for group in plots.values() if group[0]["block"] == block]
        observed = {tuple(row["levels"][factor] for factor in hard)
                    for row in block_plots}
        if observed != hard_codes or len(block_plots) != len(hard_codes):
            raise ValueError("hard combinations")
        if {row["whole_plot_order"] for row in block_plots} != set(range(1, len(hard_codes) + 1)):
            raise ValueError("whole plot orders")
        if len(block_rows) != len(hard_codes) * len(easy_codes):
            raise ValueError("whole plot count")

    ordered = sorted(rows, key=lambda row: row["run_order"])
    seen_blocks, seen_plots = set(), set()
    current_block = current_plot = None
    for row in ordered:
        if row["block"] != current_block:
            if row["block"] in seen_blocks:
                raise ValueError("noncontiguous block")
            seen_blocks.add(row["block"])
            current_block, current_plot = row["block"], None
        if row["whole_plot_id"] != current_plot:
            if row["whole_plot_id"] in seen_plots:
                raise ValueError("noncontiguous whole plot")
            seen_plots.add(row["whole_plot_id"])
            current_plot = row["whole_plot_id"]

    matrix, _ = model_matrix(rows, factors, list(range(1, block_count + 1)))
    if rank_exact(matrix) != block_count + (1 << len(factors)) - 1:
        raise ValueError("model rank")


def validate_model_rank(rows, factors, block_count):
    matrix, _ = model_matrix(rows, factors, list(range(1, block_count + 1)))
    expected = block_count + (1 << len(factors)) - 1
    if rank_exact(matrix) != expected:
        raise ValueError("model rank")


def validate_spec_contract(spec):
    factors, hard, easy = (spec["factor_count"], spec["hard_count"],
                           spec["easy_count"])
    seed = spec["seed"]
    if (any(type(value) is not int for value in (factors, hard, easy, spec["blocks"]))
            or not 2 <= factors <= 6 or hard + easy != factors or not 1 <= hard <= 3
            or easy < 1 or spec["blocks"] < 2
            or isinstance(seed, bool) or not isinstance(seed, int)
            or spec["blocks"] * (1 << factors) > 10000):
        raise ValueError("invalid split-plot spec")


def verify_case(case):
    factors, hard, easy = case["factors"], case["hard_factors"], case["easy_factors"]
    validate_units(case["rows"], factors, hard, easy, case["block_count"])
    r = case["block_count"]
    h, e = 1 << len(hard), 1 << len(easy)
    assert len(case["rows"]) == r * h * e
    result = projection_case(case)
    expected = case["expected"]
    assert result["summary"].keys() == expected["summary"].keys()
    for key, actual in result["summary"].items():
        if isinstance(actual, dict):
            assert actual.keys() == expected["summary"][key].keys()
            for nested, value in actual.items():
                close(value, expected["summary"][key][nested])
        else:
            close(actual, expected["summary"][key])
    assert result["terms"].keys() == expected["terms"].keys()
    for term, actual in result["terms"].items():
        assert actual.keys() == expected["terms"][term].keys()
        for key, value in actual.items():
            saved = expected["terms"][term][key]
            if isinstance(value, str):
                assert value == saved
            else:
                close(value, saved)
    assert result["summary"]["model_rank"] == r + (1 << len(factors)) - 1


def corrupt(rows, operation):
    changed = deepcopy(rows)
    if operation == "remove_response":
        changed[0]["y"] = None
    elif operation == "nonfinite_response":
        changed[0]["y"] = float("inf")
    elif operation == "alias_factor":
        for row in changed:
            row["levels"]["C"] = row["levels"]["A"]
    elif operation == "remove_run":
        changed.pop()
    elif operation == "move_subplot":
        moved = changed[0]
        other = next(row for row in changed
                     if row["block"] == moved["block"]
                     and row["whole_plot_id"] != moved["whole_plot_id"])
        moved["whole_plot_id"] = other["whole_plot_id"]
    elif operation == "repeat_subplot_id":
        changed[-1]["subplot_id"] = changed[0]["subplot_id"]
    elif operation == "repeat_run_id":
        changed[-1]["run_id"] = changed[0]["run_id"]
    elif operation == "change_hard_level":
        first = changed[0]
        other = next(row for row in changed
                     if row["whole_plot_id"] == first["whole_plot_id"]
                     and row["run_id"] != first["run_id"])
        other["levels"]["A"] *= -1
    else:
        raise AssertionError(f"unknown boundary operation: {operation}")
    return changed


def main():
    reference_path = HERE / "reference.json"
    reference_bytes = reference_path.read_bytes()
    manifest = json.loads((HERE / "manifest.json").read_text(encoding="utf-8"))
    for name in ("reference.json", "build_reference.py", "verify.py"):
        digest = hashlib.sha256((HERE / name).read_bytes()).hexdigest()
        assert digest == manifest[name]["sha256"]
    reference = json.loads(reference_bytes)
    assert reference["production_imports"] == []
    for case in reference["cases"]:
        verify_case(case)

    legacy_path = HERE.parent / "doe_factorial_reference" / "reference.json"
    legacy_bytes = legacy_path.read_bytes()
    legacy = json.loads(legacy_bytes)["split_plot"]
    case1 = reference["cases"][0]
    legacy_sha = hashlib.sha256(legacy_bytes).hexdigest()
    assert case1["source"]["sha256"] == manifest["doe_factorial_reference"]["sha256"] == legacy_sha
    assert case1["source"]["expected"] == legacy["expected"]
    for term in ("A", "B", "A:B"):
        close(case1["expected"]["terms"][term]["ss"], legacy["expected"]["ss"][term])
        close(case1["expected"]["terms"][term]["f"], legacy["expected"]["f"][term])
        close(case1["expected"]["terms"][term]["p"], legacy["expected"]["p"][term])

    case2, case3, case4 = reference["cases"][1:4]
    assert case2["expected"]["summary"]["n"] == 24
    assert case2["expected"]["summary"]["whole_plots"] == 6
    assert set(case2["expected"]["terms"]) == {"A", "B", "C", "A:B", "A:C", "B:C", "A:B:C"}
    assert case3["expected"]["summary"]["n"] == 48
    assert case3["expected"]["summary"]["whole_plots"] == 12
    assert case3["expected"]["summary"]["df_whole_plot_error"] == 6
    assert case3["expected"]["summary"]["df_subplot_error"] == 24
    for term, row in case4["expected"]["terms"].items():
        expected_stratum = ("whole_plot_error" if set(term.split(":")) <= set(case4["hard_factors"])
                            else "subplot_error")
        assert row["error_stratum"] == expected_stratum

    case5 = reference["cases"][4]
    for row in case5["rows"]:
        a, b, c, d = (row["levels"][factor] for factor in ("A", "B", "C", "D"))
        expected_y = (50 + 3 * a - 2 * b + 4 * c + 5 * a * b - 3 * a * c
                      + 2 * b * c * d + row["whole_plot_error"]
                      + row["subplot_error"])
        assert row["y"] == expected_y

    case6 = reference["case6"]
    verify_case(case6["max_six_factor"])
    assert case6["max_six_factor"]["expected"]["summary"]["n"] == 128
    assert len(case6["max_six_factor"]["expected"]["terms"]) == 63
    zero_wp = case6["zero_whole_plot_error"]
    zero_sp = case6["zero_subplot_error"]
    verify_case(zero_wp)
    verify_case(zero_sp)
    assert zero_wp["expected"]["summary"]["ss_whole_plot_error"] == 0
    assert zero_wp["expected"]["summary"]["ss_subplot_error"] > 0
    assert zero_sp["expected"]["summary"]["ss_subplot_error"] == 0
    assert zero_sp["expected"]["summary"]["ss_whole_plot_error"] > 0
    for term, row in zero_wp["expected"]["terms"].items():
        if row["error_stratum"] == "whole_plot_error":
            assert row["f"] is row["p"] is None
        else:
            assert row["f"] is not None and row["p"] is not None
    for term, row in zero_sp["expected"]["terms"].items():
        if row["error_stratum"] == "subplot_error":
            assert row["f"] is row["p"] is None
        else:
            assert row["f"] is not None and row["p"] is not None

    base = case3
    for boundary in case6["rejections"]:
        damaged = corrupt(base["rows"], boundary["operation"])
        if boundary["operation"] == "alias_factor":
            with_rank = model_matrix(damaged, base["factors"],
                                     list(range(1, base["block_count"] + 1)))[0]
            assert rank_exact(with_rank) < base["block_count"] + (1 << len(base["factors"])) - 1
            try:
                validate_model_rank(damaged, base["factors"], base["block_count"])
            except ValueError as error:
                assert str(error) == "model rank"
            else:
                raise AssertionError("rank-deficient model rank check did not reject")
        try:
            validate_units(damaged, base["factors"], base["hard_factors"],
                           base["easy_factors"], base["block_count"])
        except (KeyError, TypeError, ValueError):
            pass
        else:
            raise AssertionError(f"boundary was accepted: {boundary['id']}")
        assert boundary["expected"].startswith("reject")

    for spec in case6["spec_rejections"]:
        try:
            validate_spec_contract(spec)
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid spec was accepted: {spec['id']}")

    assert manifest["scipy_version"] == scipy.__version__
    sha = hashlib.sha256(reference_bytes).hexdigest()
    print("P2-3 independent reference verified: Cases 1–6, matrix projections, "
          f"unit identities and rejection boundaries; SHA-256 {sha}")


if __name__ == "__main__":
    main()
