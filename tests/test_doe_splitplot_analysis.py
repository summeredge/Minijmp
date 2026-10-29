import json
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
