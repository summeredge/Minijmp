"""独立地生成 factorial DOE 数学参考；仅用标准库与 SciPy，不导入生产模块。"""
from hashlib import sha256
from itertools import product
from fractions import Fraction
import json
import math
from pathlib import Path

from scipy.stats import f


ROOT = Path(__file__).resolve().parent


def mixed_radix_rows(levels):
    """首因子最快变化的完整笛卡尔积。"""
    rows = []
    for index in range(math.prod(map(len, levels))):
        row, quotient = [], index
        for values in levels:
            row.append(values[quotient % len(values)])
            quotient //= len(values)
        rows.append(row)
    return rows


def factorial_words(factor_count):
    return [tuple(1 if mask & (1 << i) else -1 for i in range(factor_count))
            for mask in range(1 << factor_count)]


def subset_name(mask, factor_count):
    return "".join(chr(65 + i) for i in range(factor_count) if mask & (1 << i)) or "I"


def fraction(sign):
    rows = []
    for a, b, c in factorial_words(3):
        rows.append([a, b, c, sign * a * b * c])
    structure = effect_matrix_structure(rows, "ABCD")
    return {"sign": sign, "rows": rows,
            "defining_relation": structure["defining_relations"][0],
            "resolution": structure["resolution"],
            "alias_groups": structure["alias_groups"]}


def effect_matrix_structure(rows, factors):
    rows = sorted(set(map(tuple, rows)))
    columns = {
        mask: tuple(math.prod(row[index] for index in range(len(factors))
                               if mask & (1 << index)) for row in rows)
        for mask in range(1 << len(factors))
    }
    groups = {}
    for mask, values in columns.items():
        sign = values[0]
        groups.setdefault(tuple(sign * value for value in values), []).append((mask, sign))
    mask_key = lambda mask: (mask.bit_count(), tuple(
        index for index in range(len(factors)) if mask & (1 << index)))
    term = lambda mask: "".join(factors[index] for index in range(len(factors))
                                if mask & (1 << index))
    defining = ["I=" + ("-" if values[0] < 0 else "") + term(mask)
                for mask, values in sorted(columns.items(), key=lambda item: mask_key(item[0]))
                if mask and len(set(values)) == 1]
    aliases = []
    for members in sorted(groups.values(), key=lambda group: min(
            mask_key(mask) for mask, _ in group)):
        masks = sorted((mask for mask, _ in members), key=mask_key)
        if 0 in masks:
            continue
        anchor = masks[0]
        aliases.extend(
            f"{term(anchor)}={'-' if columns[anchor][0] * columns[member][0] < 0 else ''}{term(member)}"
            for member in masks[1:])

    matrix = [[Fraction(math.prod(row[index] for index in range(len(factors))
                             if mask & (1 << index)))
               for mask in range(1 << len(factors))] for row in rows]
    rank, column = 0, 0
    while rank < len(matrix) and column < (1 << len(factors)):
        pivot = next((row for row in range(rank, len(matrix)) if matrix[row][column]), None)
        if pivot is None:
            column += 1
            continue
        matrix[rank], matrix[pivot] = matrix[pivot], matrix[rank]
        value = matrix[rank][column]
        matrix[rank] = [item / value for item in matrix[rank]]
        for row in range(len(matrix)):
            if row != rank and matrix[row][column]:
                multiplier = matrix[row][column]
                matrix[row] = [item - multiplier * pivot_item
                               for item, pivot_item in zip(matrix[row], matrix[rank])]
        rank += 1
        column += 1
    return {"defining_relations": defining, "alias_groups": aliases,
            "resolution": min((len(word.split("=", 1)[1].lstrip("-"))
                               for word in defining), default=None),
            "model_rank": rank}


def split_plot_reference():
    block_effect = (-1, 0, 1)
    whole_plot_error = (-1, 0, 1)
    block_by_subplot_error = (-2, 0, 2)
    block_whole_subplot_error = (1, -2, 1)
    rows = []
    for block, (b, wp_error, sub_error, interaction_error) in enumerate(zip(
            block_effect, whole_plot_error, block_by_subplot_error,
            block_whole_subplot_error), 1):
        for a, easy in product((-1, 1), repeat=2):
            y = (10 + 3*a + 2*easy + 4*a*easy + b + wp_error*a
                 + sub_error*easy + interaction_error*a*easy)
            rows.append({"block": block, "A": a, "B": easy, "Y": y})
    sumsq = lambda values: sum(value * value for value in values)
    wp_ss = 4 * sumsq(whole_plot_error)
    subplot_ss = 4 * (sumsq(block_by_subplot_error) +
                      sumsq(block_whole_subplot_error))
    expected = {
        "df": {"total": 11, "block": 2, "A": 1, "whole_plot_error": 2,
               "B": 1, "A:B": 1, "subplot_error": 4},
        "ss": {"A": 108, "whole_plot_error": wp_ss, "B": 48,
               "A:B": 192, "subplot_error": subplot_ss},
        "f": {"A": 108 / (wp_ss / 2), "B": 48 / (subplot_ss / 4),
              "A:B": 192 / (subplot_ss / 4)},
    }
    expected["p"] = {
        "A": float(f.sf(expected["f"]["A"], 1, 2)),
        "B": float(f.sf(expected["f"]["B"], 1, 4)),
        "A:B": float(f.sf(expected["f"]["A:B"], 1, 4)),
    }
    return {"rows": rows, "model": "block + A + B + A:B",
            "error_assumptions": "balanced randomized complete split plot; blocks fixed; independent whole plots; normal homoscedastic errors within each stratum",
            "expected": expected}


def blocked_factorial_reference():
    block_effects = (-1, 0, 1)
    block_interaction = (-1, 0, 1)
    rows = []
    for block, (b, q) in enumerate(zip(block_effects, block_interaction), 1):
        for a, x in product((-1, 1), repeat=2):
            y = 50 + 3*a - 2*x + 4*a*x + b + q*a*x
            rows.append({"block": block, "A": a, "B": x, "Y": y})
    error_ss = 4 * sum(value * value for value in block_interaction)
    error_df = (len(block_effects) - 1) * (4 - 1)
    terms = {"A": 108, "B": 48, "A:B": 192}
    expected = {"df": {"block": 2, "A": 1, "B": 1, "A:B": 1,
                        "error": error_df, "total": 11},
                "ss": {"block": 8, **terms, "error": error_ss},
                "f": {name: value / (error_ss / error_df)
                      for name, value in terms.items()}}
    expected["p"] = {name: float(f.sf(value, 1, error_df))
                      for name, value in expected["f"].items()}
    return {"rows": rows, "model": "block + A + B + A:B",
            "error_assumptions": "balanced randomized complete block; independent runs; normal homoscedastic errors",
            "expected": expected}


def build():
    levels_2x3 = [["low", "high"], [100, 150, 200]]
    general_2x3 = []
    for a_label, b_value in mixed_radix_rows(levels_2x3):
        a_effect = (-1, 1)[levels_2x3[0].index(a_label)]
        b_index = levels_2x3[1].index(b_value)
        b_effect = b_index - 1
        cell_mean = 10 + 2*a_effect + 3*b_effect + 4*a_effect*b_effect
        for replicate, noise in enumerate((-1, 1), 1):
            general_2x3.append({"A": a_label, "B": b_value,
                                "replicate": replicate, "Y": cell_mean + noise})

    levels_2x3x4 = [["off", "on"], [100, 150, 200], ["c1", "c2", "c3", "c4"]]
    general_2x3x4 = []
    for a, b, c in mixed_radix_rows(levels_2x3x4):
        i, j, k = (levels_2x3x4[n].index(value) for n, value in enumerate((a, b, c)))
        general_2x3x4.append({"A": a, "B": b, "C": c,
                              "Y": 10 + i + 2*j + 3*k + i*j + 2*i*k + j*k})

    pure_error_sse = 12
    additive_lack_of_fit_sse = 128
    general_2x3_expected = {
        "full_model_df": {"A": 1, "B": 2, "A:B": 2, "pure_error": 6},
        "full_model_ss": {"A": 48, "B": 72, "A:B": 128,
                           "pure_error": pure_error_sse},
        "full_model_f": {"A": 24, "B": 18, "A:B": 32},
        "additive_model": {"residual_df": 8, "sse": 140,
                            "pure_error_df": 6, "pure_error_sse": 12,
                            "lack_of_fit_df": 2,
                            "lack_of_fit_sse": additive_lack_of_fit_sse,
                            "lack_of_fit_f": 32,
                            "lack_of_fit_p": float(f.sf(32, 2, 6))},
    }
    numeric_means = [10, 20, 50]
    numeric_factor = [{"T": level, "replicate": replicate, "Y": mean + noise}
                      for level, mean in zip((100, 150, 200), numeric_means)
                      for replicate, noise in enumerate((-1, 0, 1), 1)]

    fractions = {"D=ABC": fraction(1), "D=-ABC": fraction(-1)}
    parent = fractions["D=ABC"]["rows"]
    fold_all = [[-value for value in row] for row in parent]
    fold_a = [[-row[0], *row[1:]] for row in parent]
    analytic = [{"A": a, "B": b, "Y": 50 + 3*a - 2*b + 4*a*b}
                for a, b in factorial_words(2)]
    return {
        "sources": {
            "general_full_factorial": "Minitab Support: Specify the factors for Create General Full Factorial Design; full Cartesian products and model contrasts independently constructed for this fixture.",
            "split_plot": "Minitab Support: Split-plot designs in design of experiments; split-plot error strata independently derived for the balanced 2x2, 3-block case.",
            "foldover": "Minitab Support: Fold design; sign/subgroup calculations independently derived over {-1,+1}.",
            "randomization": "Minitab Support: Randomize design; ordering reproducibility is implementation-specific and is tested as an invariant, not an exact vendor sequence.",
        },
        "general_full_factorial": {
            "two_by_three": {"levels": levels_2x3, "rows": general_2x3,
                              "expected": general_2x3_expected},
            "two_by_three_by_four": {"levels": levels_2x3x4,
                                     "rows": general_2x3x4},
            "numeric_categorical": {"levels": [100, 150, 200], "rows": numeric_factor,
                                    "expected_cell_means": numeric_means,
                                    "categorical_df": 2,
                                    "reference_coding_coefficients": [10, 10, 40]},
        },
        "regular_fraction": fractions,
        "foldover": {
            "parent": "D=ABC", "all_factors_added_rows": fold_all,
            "single_A_added_rows": fold_a,
            "all_factor_unique_points": len({tuple(row) for row in parent + fold_all}),
            "single_A_unique_points": len({tuple(row) for row in parent + fold_a}),
            "all_factor_resolution_increases": False,
            "single_A_combined_full_factorial": True,
            "source_expected": effect_matrix_structure(parent, "ABCD"),
            "all_factor_expected": effect_matrix_structure(parent + fold_all, "ABCD"),
            "single_A_expected": effect_matrix_structure(parent + fold_a, "ABCD"),
        },
        "block_factorial": blocked_factorial_reference(),
        "split_plot": split_plot_reference(),
        "analytic_two_level": {
            "rows": analytic,
            "coefficients": {"intercept": 50, "A": 3, "B": -2, "A:B": 4},
            "effects": {"A": 6, "B": -4, "A:B": 8},
        },
    }


def main():
    payload = json.dumps(build(), ensure_ascii=False, allow_nan=False,
                         sort_keys=True, indent=2) + "\n"
    path = ROOT / "reference.json"
    path.write_text(payload, encoding="utf-8", newline="\n")
    digest = sha256(path.read_bytes()).hexdigest()
    manifest = {"reference.json": {"sha256": digest,
                                   "source": "build_reference.py; standard-library Cartesian product and orthogonal contrast derivations",
                                   "production_imports": []}}
    (ROOT / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8", newline="\n")
    print(digest)


if __name__ == "__main__":
    main()
