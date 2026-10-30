import json
from fractions import Fraction
from itertools import combinations
from pathlib import Path

import numpy as np
import pytest

from doe_core import DesignSpec, FactorSpec, worksheet_metadata
from doe_splitplot import create_split_plot, validate_split_plot_design
from doe_splitplot_analysis import analyze_split_plot


REFERENCE = json.loads((Path(__file__).parent / "fixtures" / "doe_factorial_reference"
                        / "reference.json").read_text(encoding="utf-8"))["split_plot"]
PHASE2 = json.loads((Path(__file__).parent / "fixtures" / "doe_phase2_splitplot_reference"
                     / "reference.json").read_text(encoding="utf-8"))


def design():
    factors = (
        FactorSpec("A", "A", -1, 1, randomization_role="hard_to_change"),
        FactorSpec("B", "B", -1, 1, randomization_role="easy_to_change"),
    )
    return DesignSpec(
        "split-analysis", factors, ("Y",), seed=23, design_type="split_plot",
        block_count=3, randomization_unit="whole_plot", error_structure="split_plot",
    )


def reference_frame():
    spec = design()
    frame, metadata = create_split_plot(spec)
    factor_columns = metadata["column_map"]["factors"]
    responses = {(row["block"], row["A"], row["B"]): row["Y"]
                 for row in REFERENCE["rows"]}
    frame["响应_Y"] = [
        responses[(row["区组"],
                   int(spec.factors[0].to_coded(row[factor_columns["A"]])),
                   int(spec.factors[1].to_coded(row[factor_columns["B"]])))]
        for _, row in frame.iterrows()
    ]
    return frame, metadata


def frame_from_case(case):
    factors = tuple(FactorSpec(
        factor_id, factor_id, -1, 1,
        randomization_role=("hard_to_change" if factor_id in case["hard_factors"]
                            else "easy_to_change")) for factor_id in case["factors"])
    spec = DesignSpec(
        f"split-{case['case_id']}", factors, ("Y",), seed=29,
        design_type="split_plot", block_count=case["block_count"],
        construction_version=case.get("construction_version", "v2"),
        randomization_unit="whole_plot", error_structure="split_plot")
    frame, metadata = create_split_plot(spec)
    response_by_run = {row["run_id"]: row["y"] for row in case["rows"]}
    response_column = metadata["column_map"]["responses"]["Y"]
    run_column = metadata["column_map"]["run_id"]
    frame[response_column] = [response_by_run[run_id] for run_id in frame[run_column]]
    return frame, metadata


def assert_result_matches_case(result, case):
    expected = case["expected"]
    summary = expected["summary"]
    anova = {row["term"]: row for row in result["anova"]}
    assert result["n"] == summary["n"]
    assert result["rank"] == result["p"] == summary["model_rank"]
    assert result["df"] == (summary["df_whole_plot_error"]
                             + summary["df_subplot_error"])
    assert result["sst"] == pytest.approx(summary["ss_total"])
    assert anova["block"]["ss"] == pytest.approx(summary["ss_block"])
    assert anova["block"]["df"] == summary["df_block"]
    for name, values in expected["terms"].items():
        actual = anova[name]
        for key in ("coefficient", "effect", "ss", "ms", "f", "p"):
            if values[key] is None:
                assert actual[key] is None
            else:
                assert actual[key] == pytest.approx(values[key], rel=2e-11, abs=2e-12)
        assert actual["df"] == values["df"]
        assert actual["error_df"] == values["error_df"]
        assert actual["error_stratum"] == values["error_stratum"]
    for name, df_key, ss_key in (
            ("whole_plot_error", "df_whole_plot_error", "ss_whole_plot_error"),
            ("subplot_error", "df_subplot_error", "ss_subplot_error")):
        actual = anova[name]
        assert actual["df"] == summary[df_key]
        assert actual["ss"] == pytest.approx(summary[ss_key])
        if summary[df_key]:
            if summary[ss_key] == 0:
                assert actual["ms"] is None
            else:
                assert actual["ms"] == pytest.approx(summary[ss_key] / summary[df_key])
    assert sum(row["ss"] for row in anova.values()
               if row["term"] not in ("total", "block")) + anova["block"]["ss"] \
        == pytest.approx(result["sst"])


def test_anova_matches_independent_balanced_split_plot_reference():
    frame, metadata = reference_frame()
    result = analyze_split_plot(frame, metadata, "Y")
    expected = REFERENCE["expected"]
    anova = {row["term"]: row for row in result["anova"]}

    assert all({"term", "ss", "df", "ms", "f", "p", "error_stratum"} <= row.keys()
               for row in result["anova"])
    assert {name: anova[name]["df"] for name in expected["df"]} == expected["df"]
    for term in ("A", "B", "A:B"):
        assert anova[term]["ss"] == pytest.approx(expected["ss"][term])
        assert anova[term]["f"] == pytest.approx(expected["f"][term])
        assert anova[term]["p"] == pytest.approx(expected["p"][term])
    for term in ("whole_plot_error", "subplot_error"):
        assert anova[term]["ss"] == pytest.approx(expected["ss"][term])
    assert anova["A"]["error_stratum"] == "whole_plot_error"
    assert anova["B"]["error_stratum"] == anova["A:B"]["error_stratum"] == "subplot_error"
    assert anova["whole_plot_error"]["ms"] == pytest.approx(4)
    assert anova["subplot_error"]["ms"] == pytest.approx(14)
    assert result["n"] == 12
    assert len(result["fitted"]) == len(result["residuals"]) == 12
    assert np.isfinite(result["fitted"]).all()
    assert np.isfinite(result["residuals"]).all()
    assert result["status"]
    assert result["assumption"]


def test_categorical_contrasts_match_independent_stratified_projection():
    factors = (
        FactorSpec("A", "A", None, None, factor_type="categorical",
                   levels=("slow", "fast"), level_type="text",
                   randomization_role="hard_to_change"),
        FactorSpec("B", "B", -1, 1, randomization_role="hard_to_change"),
        FactorSpec("C", "C", None, None, factor_type="categorical",
                   levels=("off", "on"), level_type="text",
                   randomization_role="easy_to_change"),
        FactorSpec("D", "D", -1, 1, randomization_role="easy_to_change"),
    )
    spec = DesignSpec(
        "categorical-split", factors, ("Y",), seed=19, design_type="split_plot",
        block_count=2, construction_version="v3", randomization_unit="whole_plot",
        error_structure="split_plot")
    frame, metadata = create_split_plot(spec)
    columns = metadata["column_map"]

    def manual_code(factor, value):
        if factor.factor_type == "categorical":
            return -1 if value == factor.levels[0] else 1
        return -1 if value == factor.low else 1

    responses = []
    for _, row in frame.iterrows():
        a, b, c, d = (manual_code(factor, row[columns["factors"][factor.factor_id]])
                      for factor in factors)
        block_sign = -1 if row[columns["block"]] == 1 else 1
        responses.append(
            100 + 5 * block_sign + 3 * a - 2 * b + 4 * c + 5 * d + 2 * a * b
            - 3 * a * c + 2 * b * d + 4 * a * b * c * d
            + 2 * block_sign * a * b
            + block_sign * (1 + 2 * a + 3 * b + 4 * a * b) * (c + 2 * d + 3 * c * d))
    response_column = columns["responses"]["Y"]
    frame[response_column] = responses
    result = analyze_split_plot(frame, metadata, "Y")

    items = []
    for _, row in frame.iterrows():
        items.append({
            "block": int(row[columns["block"]]),
            "plot": row[columns["whole_plot_id"]],
            "codes": tuple(manual_code(
                factor, row[columns["factors"][factor.factor_id]]) for factor in factors),
            "y": Fraction(int(row[response_column])),
        })
    factor_ids = tuple(factor.factor_id for factor in factors)
    subsets = [subset for degree in range(1, len(factors) + 1)
               for subset in combinations(range(len(factors)), degree)]
    n = len(items)
    block_means = {
        block: sum((item["y"] for item in items if item["block"] == block), Fraction())
        / sum(item["block"] == block for item in items)
        for block in (1, 2)
    }
    grand = sum((item["y"] for item in items), Fraction()) / n
    coefficients = {
        subset: sum((item["y"] * _contrast_product(item["codes"], subset)
                     for item in items), Fraction()) / n
        for subset in subsets
    }
    term_ss = {subset: coefficients[subset] ** 2 * n for subset in subsets}
    block_ss = sum((sum(item["block"] == block for item in items)
                    * (block_means[block] - grand) ** 2 for block in (1, 2)), Fraction())
    full_residuals = []
    for item in items:
        fitted = block_means[item["block"]] + sum((
            coefficients[subset] * _contrast_product(item["codes"], subset)
            for subset in subsets), Fraction())
        full_residuals.append(item["y"] - fitted)

    plots = {}
    for index, item in enumerate(items):
        plots.setdefault(item["plot"], []).append(index)
    hard_indices = (0, 1)
    hard_subsets = [subset for subset in subsets if set(subset) <= set(hard_indices)]
    wp_residuals = [Fraction()] * n
    wp_ss = Fraction()
    for indices in plots.values():
        plot_items = [items[index] for index in indices]
        mean = sum((item["y"] for item in plot_items), Fraction()) / len(indices)
        first = plot_items[0]
        fitted = block_means[first["block"]] + sum((
            coefficients[subset] * _contrast_product(first["codes"], subset)
            for subset in hard_subsets), Fraction())
        residual = mean - fitted
        wp_ss += len(indices) * residual ** 2
        for index in indices:
            wp_residuals[index] = residual
    subplot_residuals = [residual - wp for residual, wp in zip(full_residuals, wp_residuals)]
    subplot_ss = sum((residual ** 2 for residual in subplot_residuals), Fraction())
    wp_df, subplot_df = 3, 12

    anova = {row["term"]: row for row in result["anova"]}
    treatment_names = {":".join(factor_ids[index] for index in subset)
                       for subset in subsets}
    assert {name for name in anova if name not in {
        "block", "whole_plot_error", "subplot_error", "total"}} == treatment_names
    assert result["rank"] == 2 + (1 << len(factors)) - 1
    assert anova["block"]["ss"] == pytest.approx(float(block_ss))
    assert result["error_strata"]["whole_plot_error"]["ss"] == pytest.approx(float(wp_ss))
    assert result["error_strata"]["whole_plot_error"]["df"] == wp_df
    assert result["error_strata"]["subplot_error"]["ss"] == pytest.approx(float(subplot_ss))
    assert result["error_strata"]["subplot_error"]["df"] == subplot_df
    assert np.asarray(result["whole_plot_residual_contribution"]) == pytest.approx(
        [float(value) for value in wp_residuals])
    assert np.asarray(result["subplot_residual_contribution"]) == pytest.approx(
        [float(value) for value in subplot_residuals])
    assert result["sst"] == pytest.approx(float(
        block_ss + sum(term_ss.values(), Fraction()) + wp_ss + subplot_ss))
    for subset in subsets:
        name = ":".join(factor_ids[index] for index in subset)
        row = anova[name]
        hard_only = set(subset) <= set(hard_indices)
        error_ss, error_df = (wp_ss, wp_df) if hard_only else (subplot_ss, subplot_df)
        assert row["coefficient"] == pytest.approx(float(coefficients[subset]))
        assert row["ss"] == pytest.approx(float(term_ss[subset]))
        assert row["df"] == 1
        assert row["error_stratum"] == (
            "whole_plot_error" if hard_only else "subplot_error")
        assert row["error_df"] == error_df
        assert row["f"] == pytest.approx(float(term_ss[subset] / (error_ss / error_df)))


def _contrast_product(codes, subset):
    value = 1
    for index in subset:
        value *= codes[index]
    return value


def test_analysis_rejects_missing_and_invalid_responses():
    frame, metadata = create_split_plot(design())
    with pytest.raises(ValueError, match="缺失"):
        analyze_split_plot(frame, metadata, "Y")
    with pytest.raises(ValueError, match="不属于"):
        analyze_split_plot(frame, metadata, "other")

    frame["响应_Y"] = ["invalid"] + [1.0] * (len(frame) - 1)
    with pytest.raises(ValueError):
        analyze_split_plot(frame, metadata, "Y")

    frame["响应_Y"] = [float("inf")] + [1.0] * (len(frame) - 1)
    with pytest.raises(ValueError, match="有限"):
        analyze_split_plot(frame, metadata, "Y")

    frame["响应_Y"] = [9007199254740993] * len(frame)
    with pytest.raises(ValueError, match="可表示"):
        analyze_split_plot(frame, metadata, "Y")


@pytest.mark.parametrize("case", [
    PHASE2["cases"][1], PHASE2["cases"][2], PHASE2["cases"][3],
    PHASE2["cases"][4], PHASE2["case6"]["max_six_factor"],
], ids=lambda case: case["case_id"])
def test_multifactor_stratified_anova_matches_independent_projection(case):
    frame, metadata = frame_from_case(case)
    result = analyze_split_plot(frame, metadata, "Y")
    assert_result_matches_case(result, case)
    assert result["status"]
    assert result["assumption"]
    assert len(result["fitted"]) == len(result["residuals"]) == len(frame)
    assert np.isfinite(result["fitted"]).all()
    assert np.isfinite(result["residuals"]).all()
    assert np.allclose(result["residuals"],
                       result["whole_plot_residual_contribution"]
                       + result["subplot_residual_contribution"], atol=1e-9)
    by_run = {row["run_id"]: row for row in case["rows"]}
    for index, run in enumerate(result["design"].runs):
        assert run.run_id in by_run
        assert result["residuals"][index] == pytest.approx(
            by_run[run.run_id]["y"] - result["fitted"][index])


@pytest.mark.parametrize("case", [
    PHASE2["case6"]["zero_whole_plot_error"],
    PHASE2["case6"]["zero_subplot_error"],
], ids=lambda case: case["case_id"])
def test_zero_error_stratum_disables_only_its_effect_tests(case):
    frame, metadata = frame_from_case(case)
    result = analyze_split_plot(frame, metadata, "Y")
    assert_result_matches_case(result, case)
    for row in result["anova"]:
        if row["term"] in ("block", "whole_plot_error", "subplot_error", "total"):
            continue
        if row["error_stratum"] == "whole_plot_error" and case["case_id"].endswith("wp-zero"):
            assert row["f"] is row["p"] is None
        elif row["error_stratum"] == "subplot_error" and case["case_id"].endswith("sp-zero"):
            assert row["f"] is row["p"] is None
        else:
            assert row["f"] is not None and row["p"] is not None


def test_analysis_is_translation_invariant_and_does_not_mutate_source():
    frame, metadata = frame_from_case(PHASE2["cases"][2])
    original = frame.copy(deep=True)
    first = analyze_split_plot(frame, metadata, "Y")
    shifted = frame.copy(deep=True)
    shifted["响应_Y"] = shifted["响应_Y"] + 1e14
    second = analyze_split_plot(shifted, metadata, "Y")
    assert frame.equals(original)
    first_rows = {row["term"]: row for row in first["anova"]}
    second_rows = {row["term"]: row for row in second["anova"]}
    for term, row in first_rows.items():
        for field in ("ss", "df", "ms", "f", "p"):
            if row[field] is not None:
                assert second_rows[term][field] == pytest.approx(row[field], rel=2e-9)
    assert np.allclose(second["fitted"] - first["fitted"], 1e14,
                       rtol=0, atol=0.1)
    assert np.allclose(second["residuals"], first["residuals"], atol=2e-8)


def test_inference_is_invariant_to_response_units():
    frame, metadata = frame_from_case(PHASE2["cases"][2])
    original = analyze_split_plot(frame, metadata, "Y")
    scaled = frame.copy(deep=True)
    scaled["响应_Y"] = scaled["响应_Y"] * 1e-8
    result = analyze_split_plot(scaled, metadata, "Y")
    assert result["status"] == original["status"]
    base_rows = {row["term"]: row for row in original["anova"]}
    scaled_rows = {row["term"]: row for row in result["anova"]}
    for term, row in base_rows.items():
        other = scaled_rows[term]
        if row["f"] is None:
            assert other["f"] is None
        else:
            assert other["f"] == pytest.approx(row["f"], rel=2e-10)
        if row["p"] is None:
            assert other["p"] is None
        else:
            assert other["p"] == pytest.approx(row["p"], rel=2e-10)
        if row["coefficient"] is not None:
            assert other["coefficient"] == pytest.approx(row["coefficient"] * 1e-8)
            assert other["ss"] == pytest.approx(row["ss"] * 1e-16, rel=2e-9, abs=1e-28)


def test_large_factor_effect_does_not_mask_real_error_variance():
    frame, metadata = frame_from_case(PHASE2["cases"][2])
    original = analyze_split_plot(frame, metadata, "Y")
    spec = DesignSpec.from_dict(metadata["design"])
    factor = next(item for item in spec.factors if item.factor_id == "A")
    column = metadata["column_map"]["factors"][factor.factor_id]
    frame["响应_Y"] += [1e14 * factor.to_coded(value) for value in frame[column]]

    result = analyze_split_plot(frame, metadata, "Y")
    for layer in ("whole_plot_error", "subplot_error"):
        assert result["error_strata"][layer]["available"]
        assert result["error_strata"][layer]["ss"] == pytest.approx(
            original["error_strata"][layer]["ss"], rel=2e-3, abs=0.25)


def test_six_factor_projection_preserves_error_ss_with_large_hard_effect():
    case = PHASE2["case6"]["max_six_factor"]
    frame, metadata = frame_from_case(case)
    spec = DesignSpec.from_dict(metadata["design"])
    factor = next(item for item in spec.factors
                  if item.factor_id == "A")
    column = metadata["column_map"]["factors"][factor.factor_id]
    frame["响应_Y"] += [1e15 * factor.to_coded(value) for value in frame[column]]

    result = analyze_split_plot(frame, metadata, "Y")
    summary = case["expected"]["summary"]
    for layer, expected_key in (("whole_plot_error", "ss_whole_plot_error"),
                                ("subplot_error", "ss_subplot_error")):
        error = result["error_strata"][layer]
        assert error["available"]
        assert error["ss"] == pytest.approx(summary[expected_key], rel=1e-10, abs=1e-9)


@pytest.mark.parametrize(("case_key", "zero_layer"), [
    ("zero_whole_plot_error", "whole_plot_error"),
    ("zero_subplot_error", "subplot_error"),
])
def test_zero_error_layer_stays_unavailable_with_large_hard_effect(case_key, zero_layer):
    frame, metadata = frame_from_case(PHASE2["case6"][case_key])
    spec = DesignSpec.from_dict(metadata["design"])
    factor = next(item for item in spec.factors
                  if item.randomization_role == "hard_to_change")
    column = metadata["column_map"]["factors"][factor.factor_id]
    frame["响应_Y"] += [1e14 * factor.to_coded(value) for value in frame[column]]

    result = analyze_split_plot(frame, metadata, "Y")
    assert not result["error_strata"][zero_layer]["available"]
    other_layer = "subplot_error" if zero_layer == "whole_plot_error" else "whole_plot_error"
    assert result["error_strata"][other_layer]["available"]


def test_rank_deficient_model_matrix_never_publishes_inference(monkeypatch):
    frame, metadata = frame_from_case(PHASE2["cases"][1])
    monkeypatch.setattr("doe_splitplot_analysis.np.linalg.matrix_rank", lambda _: 0)
    with pytest.raises(ValueError, match="模型矩阵秩亏"):
        analyze_split_plot(frame, metadata, "Y")


@pytest.mark.parametrize("corruption", ["subplot_id", "whole_plot_id", "hard_level"])
def test_structural_corruption_is_rejected_after_fingerprint_rebuild(corruption):
    case = PHASE2["cases"][2]
    frame, metadata = frame_from_case(case)
    spec = DesignSpec.from_dict(metadata["design"])
    columns = metadata["column_map"]
    if corruption == "subplot_id":
        frame.loc[1, columns["subplot_id"]] = frame.loc[0, columns["subplot_id"]]
    elif corruption == "whole_plot_id":
        other = next(index for index in frame.index[1:]
                     if frame.loc[index, columns["whole_plot_id"]]
                     != frame.loc[0, columns["whole_plot_id"]])
        frame.loc[0, columns["whole_plot_id"]] = frame.loc[other, columns["whole_plot_id"]]
    else:
        factor_column = columns["factors"]["A"]
        frame.loc[1, factor_column] = -frame.loc[1, factor_column]
    with pytest.raises(ValueError):
        refreshed = worksheet_metadata(frame, spec, columns)
        validate_split_plot_design(frame, refreshed)


def test_eight_factor_anova_matches_independent_stratified_projections():
    factors = (
        FactorSpec("A", "A", -1, 1, randomization_role="hard_to_change"),
        FactorSpec("B", "B", -1, 1, randomization_role="hard_to_change"),
        FactorSpec("C", "C", None, None, factor_type="categorical",
                   levels=("off", "on"), level_type="text",
                   randomization_role="easy_to_change"),
        *(FactorSpec(name, name, -1, 1, randomization_role="easy_to_change")
          for name in "DEFGH"),
    )
    spec = DesignSpec(
        "split-eight-factor", factors, ("Y",), seed=31, design_type="split_plot",
        block_count=2, construction_version="v3", randomization_unit="whole_plot",
        error_structure="split_plot")
    frame, metadata = create_split_plot(spec)
    columns = metadata["column_map"]

    coded_columns = []
    for factor in factors:
        actual = frame[columns["factors"][factor.factor_id]].to_numpy()
        levels = ((factor.low, factor.high) if factor.factor_type == "continuous"
                  else factor.levels)
        assert set(actual) == set(levels)
        coded_columns.append(np.where(actual == levels[0], -1.0, 1.0))
    coded = np.column_stack(coded_columns)
    blocks = frame[columns["block"]].to_numpy()
    block_levels = np.unique(blocks)
    assert len(block_levels) == 2
    block_sign = np.where(blocks == block_levels[0], -1, 1)
    a, b, c, d, e, f, g, h = coded.T
    response = (
        100 + 5 * block_sign + 3 * a - 2 * b + 4 * c + 5 * d + 2 * e - f + 3 * g - 4 * h
        + 2 * a * b - 3 * c * d + 2 * b * e * f + 4 * c * e * g * h
        + block_sign * (2 * a - b + 3 * a * b + c + 2 * d * e - f * g * h)
    )
    response_column = columns["responses"]["Y"]
    frame[response_column] = response
    y = frame[response_column].to_numpy(dtype=float)

    factor_ids = tuple(factor.factor_id for factor in factors)
    subsets = [subset for order in range(1, len(factors) + 1)
               for subset in combinations(range(len(factors)), order)]
    term_names = [":".join(factor_ids[index] for index in subset) for subset in subsets]
    terms = np.column_stack([
        np.prod(coded[:, subset], axis=1) for subset in subsets
    ])
    block_matrix = np.column_stack([blocks == block for block in block_levels]).astype(float)
    fixed_design = np.column_stack((block_matrix, terms))
    fixed_coefficients, _, fixed_rank, _ = np.linalg.lstsq(fixed_design, y, rcond=None)
    term_coefficients = fixed_coefficients[len(block_levels):]
    term_ss = term_coefficients ** 2 * len(y)
    grand_mean = y.mean()
    block_ss = sum(
        np.count_nonzero(blocks == block) * (y[blocks == block].mean() - grand_mean) ** 2
        for block in block_levels
    )

    run_plot_ids = frame[columns["whole_plot_id"]].to_numpy()
    plot_rows = {}
    for index, plot_id in enumerate(run_plot_ids):
        plot_rows.setdefault(plot_id, []).append(index)
    assert len(plot_rows) == 8
    assert {len(indices) for indices in plot_rows.values()} == {64}
    for factor in factors[:2]:
        values = frame[columns["factors"][factor.factor_id]].to_numpy()
        assert all(np.unique(values[indices]).size == 1 for indices in plot_rows.values())

    plot_ids = tuple(plot_rows)
    plot_means = np.asarray([y[plot_rows[plot_id]].mean() for plot_id in plot_ids])
    plot_blocks = np.asarray([blocks[plot_rows[plot_id][0]] for plot_id in plot_ids])
    plot_codes = np.asarray([coded[plot_rows[plot_id][0]] for plot_id in plot_ids])
    plot_block_matrix = np.column_stack([plot_blocks == block for block in block_levels])
    hard_subsets = [subset for subset in subsets if all(index < 2 for index in subset)]
    hard_terms = np.column_stack([
        np.prod(plot_codes[:, subset], axis=1) for subset in hard_subsets
    ])
    whole_plot_design = np.column_stack((plot_block_matrix, hard_terms))
    whole_plot_coefficients, _, whole_plot_rank, _ = np.linalg.lstsq(
        whole_plot_design, plot_means, rcond=None)
    whole_plot_residuals = plot_means - whole_plot_design @ whole_plot_coefficients
    plot_sizes = np.asarray([len(plot_rows[plot_id]) for plot_id in plot_ids])
    ss_whole_plot = float(np.sum(plot_sizes * whole_plot_residuals ** 2))
    df_whole_plot = len(plot_ids) - whole_plot_rank

    plot_indicators = np.column_stack([run_plot_ids == plot_id for plot_id in plot_ids])
    easy_term_indices = [index for index, subset in enumerate(subsets)
                         if any(factor_index >= 2 for factor_index in subset)]
    subplot_design = np.column_stack((plot_indicators, terms[:, easy_term_indices]))
    subplot_coefficients, _, subplot_rank, _ = np.linalg.lstsq(
        subplot_design, y, rcond=None)
    subplot_residuals = y - subplot_design @ subplot_coefficients
    ss_subplot = float(subplot_residuals @ subplot_residuals)
    df_subplot = len(y) - subplot_rank
    assert df_whole_plot == 3
    assert df_subplot == 252

    result = analyze_split_plot(frame, metadata, "Y")
    anova = {row["term"]: row for row in result["anova"]}
    assert set(anova) == set(term_names) | {
        "block", "whole_plot_error", "subplot_error", "total"}
    assert result["n"] == len(y) == 512
    assert result["rank"] == result["p"] == fixed_rank == len(block_levels) + len(subsets)
    assert result["df"] == df_whole_plot + df_subplot
    assert anova["block"]["df"] == len(block_levels) - 1
    assert anova["block"]["ss"] == pytest.approx(block_ss)
    assert anova["total"]["df"] == len(y) - 1
    assert result["sst"] == pytest.approx(np.sum((y - grand_mean) ** 2))
    assert result["sse"] == pytest.approx(ss_whole_plot + ss_subplot)

    strata = {
        "whole_plot_error": (ss_whole_plot, df_whole_plot),
        "subplot_error": (ss_subplot, df_subplot),
    }
    for name, (expected_ss, expected_df) in strata.items():
        assert result["error_strata"][name]["ss"] == pytest.approx(expected_ss)
        assert result["error_strata"][name]["df"] == expected_df
        assert result["error_strata"][name]["ms"] == pytest.approx(expected_ss / expected_df)
        assert anova[name]["ss"] == pytest.approx(expected_ss)
        assert anova[name]["df"] == expected_df

    assert block_ss + term_ss.sum() + ss_whole_plot + ss_subplot == pytest.approx(
        result["sst"])
    for index, (subset, name) in enumerate(zip(subsets, term_names)):
        whole_plot_term = all(factor_index < 2 for factor_index in subset)
        stratum = "whole_plot_error" if whole_plot_term else "subplot_error"
        error_ss, error_df = strata[stratum]
        row = anova[name]
        assert row["coefficient"] == pytest.approx(term_coefficients[index], abs=1e-10)
        assert row["effect"] == pytest.approx(2 * term_coefficients[index], abs=1e-10)
        assert row["ss"] == pytest.approx(term_ss[index], abs=1e-9)
        assert row["df"] == 1
        assert row["error_stratum"] == stratum
        assert row["error_df"] == error_df
        assert row["f"] == pytest.approx(term_ss[index] / (error_ss / error_df), abs=1e-9)
