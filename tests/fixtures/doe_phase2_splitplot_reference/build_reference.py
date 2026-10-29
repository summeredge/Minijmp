"""Build an exact-rational Split-Plot reference without MiniJMP imports."""
from fractions import Fraction
from itertools import combinations, product
import hashlib
import json
from pathlib import Path

import scipy
from scipy.stats import f


ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
LEGACY_PATH = ROOT / "tests" / "fixtures" / "doe_factorial_reference" / "reference.json"


def terms(factors):
    return [subset for size in range(1, len(factors) + 1)
            for subset in combinations(factors, size)]


def contrast(row, term):
    value = 1
    for factor in term:
        value *= row["levels"][factor]
    return value


def analyze(rows, factors, hard_factors):
    """Exact orthogonal contrasts plus nested whole-plot residual projections."""
    easy_factors = tuple(factor for factor in factors if factor not in hard_factors)
    block_count = len({row["block"] for row in rows})
    hard_count, easy_count = 2 ** len(hard_factors), 2 ** len(easy_factors)
    n = len(rows)
    y = [Fraction(row["y"]) for row in rows]
    grand = sum(y, Fraction()) / n
    by_block = {block: [index for index, row in enumerate(rows)
                        if row["block"] == block]
                for block in sorted({row["block"] for row in rows})}
    block_means = {block: sum((y[index] for index in indices), Fraction()) / len(indices)
                   for block, indices in by_block.items()}
    ss_block = hard_count * easy_count * sum(
        ((mean - grand) ** 2 for mean in block_means.values()), Fraction())

    subsets = terms(factors)
    coefficients = {
        subset: sum((y[index] * contrast(rows[index], subset)
                     for index in range(n)), Fraction()) / n
        for subset in subsets
    }
    ss_terms = {subset: n * coefficients[subset] ** 2 for subset in subsets}

    by_plot = {}
    for index, row in enumerate(rows):
        key = (row["block"], tuple(row["levels"][factor]
                                   for factor in hard_factors))
        by_plot.setdefault(key, []).append(index)
    wp_residual = {}
    for key, indices in by_plot.items():
        block, hard_levels = key
        mean = sum((y[index] for index in indices), Fraction()) / len(indices)
        fixed = block_means[block]
        for subset, coefficient in coefficients.items():
            if set(subset) <= set(hard_factors):
                level_row = {"levels": dict(zip(hard_factors, hard_levels))}
                fixed += coefficient * contrast(level_row, subset)
        wp_residual[key] = mean - fixed
    ss_wp = easy_count * sum((value ** 2 for value in wp_residual.values()), Fraction())

    residual = []
    for index, row in enumerate(rows):
        fixed = block_means[row["block"]]
        for subset, coefficient in coefficients.items():
            fixed += coefficient * contrast(row, subset)
        plot_key = (row["block"], tuple(row["levels"][factor]
                                        for factor in hard_factors))
        residual.append(y[index] - fixed - wp_residual[plot_key])
    ss_subplot = sum((value ** 2 for value in residual), Fraction())
    ss_total = sum(((value - grand) ** 2 for value in y), Fraction())
    if ss_total != ss_block + sum(ss_terms.values(), Fraction()) + ss_wp + ss_subplot:
        raise AssertionError("exact SS partition does not close")

    df_total = n - 1
    df_block = block_count - 1
    df_wp = (block_count - 1) * (hard_count - 1)
    df_subplot = hard_count * (block_count - 1) * (easy_count - 1)
    if df_total != (df_block + hard_count - 1 + df_wp
                    + hard_count * (easy_count - 1) + df_subplot):
        raise AssertionError("df partition does not close")
    wp_mse = ss_wp / df_wp if df_wp else None
    subplot_mse = ss_subplot / df_subplot if df_subplot else None

    item_results = {}
    for subset in subsets:
        name = ":".join(subset)
        hard_only = set(subset) <= set(hard_factors)
        error_ss, error_df = ((ss_wp, df_wp) if hard_only
                              else (ss_subplot, df_subplot))
        mse = wp_mse if hard_only else subplot_mse
        ss = ss_terms[subset]
        f_value = float(ss / mse) if mse is not None and mse > 0 else None
        item_results[name] = {
            "coefficient": float(coefficients[subset]),
            "effect": float(2 * coefficients[subset]),
            "ss": float(ss), "df": 1, "ms": float(ss),
            "error_stratum": "whole_plot_error" if hard_only else "subplot_error",
            "error_df": error_df,
            "f": f_value,
            "p": float(f.sf(f_value, 1, error_df)) if f_value is not None else None,
        }
    return {
        "summary": {
            "n": n, "blocks": block_count, "hard_factors": len(hard_factors),
            "easy_factors": len(easy_factors), "hard_combinations": hard_count,
            "subplots_per_whole_plot": easy_count, "whole_plots": len(by_plot),
            "df_total": df_total, "df_block": df_block,
            "df_hard_effects": hard_count - 1, "df_whole_plot_error": df_wp,
            "df_easy_terms": hard_count * (easy_count - 1),
            "df_subplot_error": df_subplot,
            "model_rank": block_count + 2 ** len(factors) - 1,
            "ss_total": float(ss_total), "ss_block": float(ss_block),
            "ss_whole_plot_error": float(ss_wp),
            "ss_subplot_error": float(ss_subplot),
            "ss_terms": {":".join(term): float(ss_terms[term]) for term in subsets},
        },
        "terms": item_results,
    }


def full_factorial_rows(factors, hard_factors, block_count):
    hard_product = tuple(hard_factors)
    easy_factors = tuple(factor for factor in factors if factor not in hard_factors)
    rows = []
    for block_index in range(block_count):
        block_code = 2 * block_index - (block_count - 1)
        for levels in product((-1, 1), repeat=len(factors)):
            setting = dict(zip(factors, levels))
            hard_interaction = 1
            for factor in hard_product:
                hard_interaction *= setting[factor]
            easy_error = sum((index + 1) * setting[factor]
                             for index, factor in enumerate(easy_factors))
            all_interaction = 1
            for value in levels:
                all_interaction *= value
            y_value = 40 + 2 * block_code + block_code * hard_interaction
            for index, subset in enumerate(terms(factors)):
                coefficient = (index % 4 + 1) * (-1 if index % 2 else 1)
                y_value += coefficient * contrast({"levels": setting}, subset)
            y_value += block_code * (easy_error + all_interaction)
            rows.append({"block": block_index + 1, "levels": setting, "y": y_value})
    return rows


def case(case_id, label, factors, hard_factors, block_count, rows, source=None):
    hard_factors = tuple(hard_factors)
    easy_factors = tuple(factor for factor in factors if factor not in hard_factors)
    hard_order = {values: index for index, values in enumerate(
        product((-1, 1), repeat=len(hard_factors)), 1)}
    easy_order = {values: index for index, values in enumerate(
        product((-1, 1), repeat=len(easy_factors)), 1)}
    for index, row in enumerate(rows, 1):
        hard_values = tuple(row["levels"][factor] for factor in hard_factors)
        easy_values = tuple(row["levels"][factor] for factor in easy_factors)
        whole_plot_order = hard_order[hard_values]
        subplot_order = easy_order[easy_values]
        row.update({
            "run_id": f"R{index:05d}", "standard_order": index,
            "run_order": index, "replicate": 1,
            "whole_plot_id": f"WP{row['block']:05d}H{whole_plot_order}",
            "subplot_id": (f"SP{row['block']:05d}H{whole_plot_order}"
                           f"E{subplot_order}"),
            "whole_plot_order": whole_plot_order,
            "subplot_order": subplot_order,
        })
    return {"case_id": case_id, "label": label, "factors": list(factors),
            "hard_factors": list(hard_factors), "easy_factors": [
                factor for factor in factors if factor not in hard_factors],
            "construction_version": "v1" if case_id == "case1" else "v2",
            "block_count": block_count, "rows": rows,
            "expected": analyze(rows, factors, hard_factors), "source": source}


def case_five_rows():
    factors = ("A", "B", "C", "D")
    rows = []
    for block_index, block_code in enumerate((-1, 0, 1), 1):
        for values in product((-1, 1), repeat=4):
            a, b, c, d = values
            wp_error = block_code * a * b
            sp_error = block_code * (c + 2 * d + a * c * d + b * c)
            y_value = (50 + 3 * a - 2 * b + 4 * c + 5 * a * b
                       - 3 * a * c + 2 * b * c * d + wp_error + sp_error)
            rows.append({"block": block_index,
                         "levels": dict(zip(factors, values)), "y": y_value,
                         "whole_plot_error": wp_error,
                         "subplot_error": sp_error})
    return rows


def boundary_case(case_id, label, rows):
    result = case(case_id, label, ("A", "B", "C", "D"), ("A", "B"), 3, rows)
    result["available"] = {
        "whole_plot_error": result["expected"]["summary"]["ss_whole_plot_error"] > 0,
        "subplot_error": result["expected"]["summary"]["ss_subplot_error"] > 0,
    }
    return result


def main():
    legacy_raw = LEGACY_PATH.read_bytes()
    legacy = json.loads(legacy_raw)["split_plot"]
    legacy_rows = [{"block": row["block"],
                    "levels": {"A": row["A"], "B": row["B"]},
                    "y": row["Y"]} for row in legacy["rows"]]
    cases = [case("case1", "原 D 工作包 2×2、3 blocks", ("A", "B"), ("A",), 3,
                  legacy_rows, {"fixture": "doe_factorial_reference/reference.json",
                                "sha256": hashlib.sha256(legacy_raw).hexdigest(),
                                "expected": legacy["expected"]})]
    cases.append(case("case2", "1 hard + 2 easy、3 blocks",
                      ("A", "B", "C"), ("A",), 3,
                      full_factorial_rows(("A", "B", "C"), ("A",), 3)))
    cases.append(case("case3", "2 hard + 2 easy、3 blocks",
                      ("A", "B", "C", "D"), ("A", "B"), 3,
                      full_factorial_rows(("A", "B", "C", "D"), ("A", "B"), 3)))
    cases.append(case("case4", "3 hard + 1 easy、2 blocks",
                      ("A", "B", "C", "D"), ("A", "B", "C"), 2,
                      full_factorial_rows(("A", "B", "C", "D"), ("A", "B", "C"), 2)))
    cases.append(case("case5", "规定响应解析构造与两层误差",
                      ("A", "B", "C", "D"), ("A", "B"), 3,
                      case_five_rows()))

    base = full_factorial_rows(("A", "B", "C", "D"), ("A", "B"), 3)
    zero_wp = []
    zero_sp = []
    for row in base:
        block_code = 2 * (row["block"] - 1) - 2
        a, b, c, d = (row["levels"][factor] for factor in ("A", "B", "C", "D"))
        fixed = 40 + 2 * block_code
        for index, subset in enumerate(terms(("A", "B", "C", "D"))):
            coefficient = (index % 4 + 1) * (-1 if index % 2 else 1)
            fixed += coefficient * contrast(row, subset)
        wp_error = block_code * a * b
        zero_wp.append({"block": row["block"], "levels": row["levels"],
                        "y": fixed + block_code * (c + 2 * d + a * c * d + b * c)})
        zero_sp.append({"block": row["block"], "levels": row["levels"],
                        "y": fixed + wp_error})
    case6 = {
        "case_id": "case6", "label": "误差层和输入边界",
        "max_six_factor": case(
            "case6-max", "6 因子、3 hard + 3 easy、2 blocks",
            ("A", "B", "C", "D", "E", "F"), ("A", "B", "C"), 2,
            full_factorial_rows(("A", "B", "C", "D", "E", "F"),
                                ("A", "B", "C"), 2)),
        "zero_whole_plot_error": boundary_case(
            "case6-wp-zero", "整区误差为零", zero_wp),
        "zero_subplot_error": boundary_case(
            "case6-sp-zero", "子区误差为零", zero_sp),
        "rejections": [
            {"id": "missing_response", "operation": "remove_response",
             "expected": "reject missing response"},
            {"id": "nonfinite_response", "operation": "nonfinite_response",
             "expected": "reject nonfinite response"},
            {"id": "rank_deficient_factor_matrix", "operation": "alias_factor",
             "expected": "reject rank-deficient design; no F/p"},
            {"id": "missing_easy_combination", "operation": "remove_run",
             "expected": "reject incomplete subplot set; no F/p"},
            {"id": "whole_plot_identity_damaged", "operation": "move_subplot",
             "expected": "reject damaged whole-plot identity; no F/p"},
            {"id": "subplot_id_repeated", "operation": "repeat_subplot_id",
             "expected": "reject duplicate subplot identity; no F/p"},
            {"id": "run_id_repeated", "operation": "repeat_run_id",
             "expected": "reject duplicate run identity; no F/p"},
            {"id": "hard_level_changes_within_whole_plot", "operation": "change_hard_level",
             "expected": "reject varying hard level; no F/p"},
        ],
        "spec_rejections": [
            {"id": "one_factor", "factor_count": 1, "hard_count": 1,
             "easy_count": 0, "blocks": 3, "seed": 1},
            {"id": "seven_factors", "factor_count": 7, "hard_count": 3,
             "easy_count": 4, "blocks": 2, "seed": 1},
            {"id": "no_hard_factor", "factor_count": 2, "hard_count": 0,
             "easy_count": 2, "blocks": 3, "seed": 1},
            {"id": "four_hard_factors", "factor_count": 6, "hard_count": 4,
             "easy_count": 2, "blocks": 2, "seed": 1},
            {"id": "no_easy_factor", "factor_count": 2, "hard_count": 2,
             "easy_count": 0, "blocks": 3, "seed": 1},
            {"id": "one_block", "factor_count": 2, "hard_count": 1,
             "easy_count": 1, "blocks": 1, "seed": 1},
            {"id": "over_run_budget", "factor_count": 6, "hard_count": 3,
             "easy_count": 3, "blocks": 157, "seed": 1},
            {"id": "boolean_seed", "factor_count": 2, "hard_count": 1,
             "easy_count": 1, "blocks": 3, "seed": True},
            {"id": "fractional_seed", "factor_count": 2, "hard_count": 1,
             "easy_count": 1, "blocks": 3, "seed": 1.5},
            {"id": "fractional_factor_count", "factor_count": 2.5, "hard_count": 1,
             "easy_count": 1.5, "blocks": 3, "seed": 1},
            {"id": "fractional_hard_count", "factor_count": 2, "hard_count": 1.5,
             "easy_count": 0.5, "blocks": 3, "seed": 1},
            {"id": "fractional_block_count", "factor_count": 2, "hard_count": 1,
             "easy_count": 1, "blocks": 2.5, "seed": 1},
        ],
    }
    payload = {
        "method": "balanced two-level split-plot; fixed blocks; orthogonal factorial contrasts",
        "numeric_method": "Fraction exact sums of squares and nested projections; SciPy F survival function",
        "production_imports": [],
        "cases": cases,
        "case6": case6,
    }
    encoded = (json.dumps(payload, ensure_ascii=False, allow_nan=False,
                          indent=2, sort_keys=True) + "\n").encode("utf-8")
    (HERE / "reference.json").write_bytes(encoded)
    manifest = {
        "reference.json": {"sha256": hashlib.sha256(encoded).hexdigest(),
                           "source": "build_reference.py; exact rational contrasts and projections",
                           "production_imports": []},
        "build_reference.py": {"sha256": hashlib.sha256(HERE.joinpath(
            "build_reference.py").read_bytes()).hexdigest()},
        "verify.py": {"sha256": hashlib.sha256(HERE.joinpath("verify.py").read_bytes()).hexdigest()},
        "doe_factorial_reference": {"sha256": hashlib.sha256(legacy_raw).hexdigest()},
        "scipy_version": scipy.__version__,
    }
    manifest_encoded = (json.dumps(manifest, ensure_ascii=False, indent=2,
                                   sort_keys=True) + "\n").encode("utf-8")
    (HERE / "manifest.json").write_bytes(manifest_encoded)


if __name__ == "__main__":
    main()
