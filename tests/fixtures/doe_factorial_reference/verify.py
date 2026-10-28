"""用平衡设计的独立对比/平方和分解核验 factorial 参考。"""
from collections import defaultdict
from fractions import Fraction
from hashlib import sha256
from itertools import product
import json
import math
from pathlib import Path

from scipy.stats import f


ROOT = Path(__file__).resolve().parent


def mean(values):
    return sum(values) / len(values)


def close(actual, expected):
    assert math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12), (actual, expected)


def derive_effect_structure(rows, factors):
    points = sorted(set(map(tuple, rows)))
    columns = {
        mask: tuple(math.prod(point[index] for index in range(len(factors))
                              if mask & (1 << index)) for point in points)
        for mask in range(1 << len(factors))
    }
    buckets = defaultdict(list)
    for mask, values in columns.items():
        first = values[0]
        buckets[tuple(first * value for value in values)].append((mask, first))
    key = lambda mask: (mask.bit_count(), tuple(
        index for index in range(len(factors)) if mask & (1 << index)))
    word = lambda mask: "".join(factors[index] for index in range(len(factors))
                                if mask & (1 << index))
    defining = ["I=" + ("-" if values[0] < 0 else "") + word(mask)
                for mask, values in sorted(columns.items(), key=lambda item: key(item[0]))
                if mask and len(set(values)) == 1]
    aliases = []
    for members in sorted(buckets.values(), key=lambda group: min(
            key(mask) for mask, _ in group)):
        masks = sorted((mask for mask, _ in members), key=key)
        if 0 not in masks:
            anchor = masks[0]
            for other in masks[1:]:
                sign = columns[anchor][0] * columns[other][0]
                aliases.append(f"{word(anchor)}={'-' if sign < 0 else ''}{word(other)}")

    effect_matrix = [[Fraction(math.prod(point[index] for index in range(len(factors))
                                 if mask & (1 << index)))
                      for mask in range(1 << len(factors))] for point in points]
    rank, column = 0, 0
    while rank < len(effect_matrix) and column < (1 << len(factors)):
        pivot = next((row for row in range(rank, len(effect_matrix))
                      if effect_matrix[row][column]), None)
        if pivot is None:
            column += 1
            continue
        effect_matrix[rank], effect_matrix[pivot] = (
            effect_matrix[pivot], effect_matrix[rank])
        scale = effect_matrix[rank][column]
        effect_matrix[rank] = [value / scale for value in effect_matrix[rank]]
        for row in range(len(effect_matrix)):
            if row != rank and effect_matrix[row][column]:
                scale = effect_matrix[row][column]
                effect_matrix[row] = [value - scale * pivot_value
                                       for value, pivot_value in zip(
                                           effect_matrix[row], effect_matrix[rank])]
        rank += 1
        column += 1
    return {"defining_relations": defining, "alias_groups": aliases,
            "resolution": min((len(item.split("=", 1)[1].lstrip("-"))
                                for item in defining), default=None),
            "model_rank": rank}


def verify():
    data_path = ROOT / "reference.json"
    reference = json.loads(data_path.read_text(encoding="utf-8"))
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    assert sha256(data_path.read_bytes()).hexdigest() == manifest["reference.json"]["sha256"]

    general = reference["general_full_factorial"]
    two_by_three = general["two_by_three"]
    rows = two_by_three["rows"]
    assert len(rows) == 12 and len({(r["A"], r["B"]) for r in rows}) == 6
    cells = defaultdict(list)
    for row in rows:
        cells[(row["A"], row["B"])].append(row["Y"])
    cell_means = {cell: mean(values) for cell, values in cells.items()}
    grand = mean([row["Y"] for row in rows])
    a_means = {a: mean([cell_means[(a, b)] for b in (100, 150, 200)])
               for a in ("low", "high")}
    b_means = {b: mean([cell_means[(a, b)] for a in ("low", "high")])
               for b in (100, 150, 200)}
    ss_a = 6 * sum((value - grand) ** 2 for value in a_means.values())
    ss_b = 4 * sum((value - grand) ** 2 for value in b_means.values())
    ss_ab = 2 * sum((cell_means[(a, b)] - a_means[a] - b_means[b] + grand) ** 2
                    for a in a_means for b in b_means)
    pure_sse = sum((value - cell_means[cell]) ** 2
                   for cell, values in cells.items() for value in values)
    expected = two_by_three["expected"]
    for name, actual in (("A", ss_a), ("B", ss_b), ("A:B", ss_ab)):
        close(actual, expected["full_model_ss"][name])
        df = expected["full_model_df"][name]
        close(actual / df / (pure_sse / 6), expected["full_model_f"][name])
    close(pure_sse, expected["full_model_ss"]["pure_error"])
    close(ss_ab + pure_sse, expected["additive_model"]["sse"])
    lof_f = (ss_ab / 2) / (pure_sse / 6)
    close(lof_f, expected["additive_model"]["lack_of_fit_f"])
    close(float(f.sf(lof_f, 2, 6)), expected["additive_model"]["lack_of_fit_p"])

    mixed = general["two_by_three_by_four"]
    assert len(mixed["rows"]) == 24
    assert len({(r["A"], r["B"], r["C"]) for r in mixed["rows"]}) == 24
    numeric = general["numeric_categorical"]
    assert all(type(row["T"]) is int for row in numeric["rows"])
    means = [mean([r["Y"] for r in numeric["rows"] if r["T"] == level])
             for level in numeric["levels"]]
    assert means == numeric["expected_cell_means"]
    assert [means[0], means[1] - means[0], means[2] - means[0]] == [10, 10, 40]
    assert numeric["categorical_df"] == len(numeric["levels"]) - 1 == 2

    for name, sign in (("D=ABC", 1), ("D=-ABC", -1)):
        design = reference["regular_fraction"][name]
        assert len(design["rows"]) == 8 and len({tuple(row) for row in design["rows"]}) == 8
        assert all(row[3] == sign * row[0] * row[1] * row[2] for row in design["rows"])
        assert design["defining_relation"] == f"I={'-' if sign < 0 else ''}ABCD"
        assert all(("=-" in alias) == (sign < 0) for alias in design["alias_groups"])
        actual_structure = derive_effect_structure(design["rows"], "ABCD")
        assert actual_structure["defining_relations"] == [design["defining_relation"]]
        assert actual_structure["alias_groups"] == design["alias_groups"]
        assert actual_structure["resolution"] == design["resolution"] == 4

    foldover = reference["foldover"]
    parent = [tuple(row) for row in reference["regular_fraction"]["D=ABC"]["rows"]]
    all_added = [tuple(row) for row in foldover["all_factors_added_rows"]]
    a_added = [tuple(row) for row in foldover["single_A_added_rows"]]
    all_flip = [tuple(-value for value in row) for row in parent]
    a_flip = [tuple(-value if index == 0 else value
                    for index, value in enumerate(row)) for row in parent]
    assert all_added == all_flip and a_added == a_flip
    parent_points = set(parent)
    all_points = set(parent + all_added)
    a_points = set(parent + a_added)
    assert foldover["all_factor_unique_points"] == len(all_points) == 8
    assert foldover["single_A_unique_points"] == len(a_points) == 16
    assert all_points == parent_points
    assert a_points == set(product((-1, 1), repeat=4))
    assert not foldover["all_factor_resolution_increases"]
    assert foldover["single_A_combined_full_factorial"]

    for mask in range(1 << 4):
        added = {tuple(-value if mask & (1 << index) else value
                       for index, value in enumerate(row)) for row in parent}
        combined = parent_points | added
        if mask.bit_count() % 2 == 0:
            assert added == parent_points and combined == parent_points
        else:
            assert not (added & parent_points)
            assert combined == set(product((-1, 1), repeat=4))

    for name, rows, expected in (
            ("source", parent, foldover["source_expected"]),
            ("all_factor", parent + all_added, foldover["all_factor_expected"]),
            ("single_A", parent + a_added, foldover["single_A_expected"])):
        actual = derive_effect_structure(rows, "ABCD")
        assert actual == expected, name
    assert foldover["source_expected"]["model_rank"] == 8
    assert foldover["all_factor_expected"]["model_rank"] == 8
    assert foldover["all_factor_expected"]["resolution"] == 4
    assert foldover["all_factor_expected"]["defining_relations"] == ["I=ABCD"]
    assert foldover["single_A_expected"]["model_rank"] == 16
    assert foldover["single_A_expected"]["resolution"] is None
    assert not foldover["single_A_expected"]["defining_relations"]

    block_ref = reference["block_factorial"]
    block_rows = block_ref["rows"]
    block_cells = defaultdict(list)
    block_groups = defaultdict(list)
    for row in block_rows:
        block_cells[(row["A"], row["B"])].append(row["Y"])
        block_groups[row["block"]].append(row["Y"])
    all_y = [row["Y"] for row in block_rows]
    grand = mean(all_y)
    treatment_means = {key: mean(values) for key, values in block_cells.items()}
    ss_block = 4 * sum((mean(values) - grand) ** 2 for values in block_groups.values())
    ss_treatment = 3 * sum((value - grand) ** 2 for value in treatment_means.values())
    sse = sum((row["Y"] - mean(block_groups[row["block"]])
               - treatment_means[(row["A"], row["B"])] + grand) ** 2
              for row in block_rows)
    close(ss_block, block_ref["expected"]["ss"]["block"])
    close(ss_treatment, 348)
    close(sse, block_ref["expected"]["ss"]["error"])
    close(sse / block_ref["expected"]["df"]["error"], 4 / 3)

    split = reference["split_plot"]
    split_rows = split["rows"]
    assert len(split_rows) == 12
    whole_plots = defaultdict(list)
    by_block = defaultdict(list)
    for row in split_rows:
        whole_plots[(row["block"], row["A"])].append(row)
        by_block[row["block"]].append(row)
    assert len(whole_plots) == 6 and all(len(values) == 2 for values in whole_plots.values())
    assert all({row["B"] for row in values} == {-1, 1}
               for values in whole_plots.values())
    assert all({row["A"] for row in values} == {-1, 1} for values in by_block.values())
    grand = mean([row["Y"] for row in split_rows])
    a_means = {a: mean([row["Y"] for row in split_rows if row["A"] == a])
               for a in (-1, 1)}
    b_means = {b: mean([row["Y"] for row in split_rows if row["B"] == b])
               for b in (-1, 1)}
    cells = {(a, b): mean([row["Y"] for row in split_rows
                           if row["A"] == a and row["B"] == b])
             for a in (-1, 1) for b in (-1, 1)}
    ss_a = 6 * sum((value - grand) ** 2 for value in a_means.values())
    ss_b = 6 * sum((value - grand) ** 2 for value in b_means.values())
    ss_ab = 3 * sum((cells[(a, b)] - a_means[a] - b_means[b] + grand) ** 2
                    for a in (-1, 1) for b in (-1, 1))
    block_means = {block: mean([row["Y"] for row in values])
                   for block, values in by_block.items()}
    wp_ss = 2 * sum((mean([row["Y"] for row in values])
                     - block_means[block] - a_means[a] + grand) ** 2
                    for (block, a), values in whole_plots.items())
    total_residual = sum((row["Y"] - block_means[row["block"]]
                          - cells[(row["A"], row["B"])] + grand) ** 2
                         for row in split_rows)
    subplot_ss = total_residual - wp_ss
    expected = split["expected"]
    assert expected["df"] == {"total": 11, "block": 2, "A": 1,
                              "whole_plot_error": 2, "B": 1, "A:B": 1,
                              "subplot_error": 4}
    for name, actual in (("A", ss_a), ("B", ss_b), ("A:B", ss_ab),
                         ("whole_plot_error", wp_ss), ("subplot_error", subplot_ss)):
        close(actual, expected["ss"][name])
    df_wp, df_sub = expected["df"]["whole_plot_error"], expected["df"]["subplot_error"]
    for name, ss, mse, denominator_df in (
            ("A", ss_a, wp_ss / df_wp, df_wp),
            ("B", ss_b, subplot_ss / df_sub, df_sub),
            ("A:B", ss_ab, subplot_ss / df_sub, df_sub)):
        statistic = (ss / 1) / mse
        close(statistic, expected["f"][name])
        close(float(f.sf(statistic, 1, denominator_df)), expected["p"][name])

    analytic = reference["analytic_two_level"]
    coefficients = {
        "intercept": mean([row["Y"] for row in analytic["rows"]]),
        "A": mean([row["A"] * row["Y"] for row in analytic["rows"]]),
        "B": mean([row["B"] * row["Y"] for row in analytic["rows"]]),
        "A:B": mean([row["A"] * row["B"] * row["Y"] for row in analytic["rows"]]),
    }
    assert coefficients == analytic["coefficients"]
    assert {name: 2 * value for name, value in coefficients.items() if name != "intercept"} == analytic["effects"]
    return True


if __name__ == "__main__":
    verify()
    print("factorial independent references verified")
