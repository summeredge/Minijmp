import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from doe_core import DesignSpec, FactorSpec, worksheet_metadata
from doe_general_factorial import create_general_factorial
from doe_variability import analyze_variability
from doe_splitplot import create_split_plot


REFERENCE = json.loads((Path(__file__).parent / "fixtures" / "doe_h_reference"
                        / "reference.json").read_text(encoding="utf-8"))


def _frame(points, measurements, response_names, *, blocks=None, run_ids=None):
    factors = (FactorSpec("A", "A", -1, 1), FactorSpec("B", "B", -1, 1))
    blocks = [None] * len(points) if blocks is None else list(blocks)
    run_ids = [f"R{i:03d}" for i in range(1, len(points) + 1)] if run_ids is None else run_ids
    rows = []
    for i, (point, values) in enumerate(zip(points, measurements)):
        rows.append({
            "运行ID": run_ids[i], "标准序": i + 1, "运行序": i + 1,
            "点类型": "factorial", "重复": 1, "区组": blocks[i],
            "设定_A": factors[0].from_coded(point[0]),
            "设定_B": factors[1].from_coded(point[1]),
            **{f"响应_{name}": value for name, value in zip(response_names, values)},
        })
    frame = pd.DataFrame(rows)
    frame.index = np.arange(20, 20 + len(frame))
    block_count = len(set(blocks)) if any(block is not None for block in blocks) else None
    spec = DesignSpec(
        "variability-test", factors, tuple(response_names), seed=13,
        design_type="two_level_full", block_count=block_count,
        randomization_unit="block" if block_count is not None else "run",
    )
    columns = {
        "run_id": "运行ID", "standard_order": "标准序", "run_order": "运行序",
        "point_type": "点类型", "replicate": "重复", "block": "区组",
        "factors": {factor.factor_id: f"设定_{factor.factor_id}" for factor in factors},
        "measured_levels": {},
        "responses": {name: f"响应_{name}" for name in response_names},
    }
    return frame, worksheet_metadata(frame, spec, columns)


def _assert_reference_fit(result, expected):
    fit = result["fit"]
    assert result["inference_status"] == "available"
    assert result["status_reasons"] == []
    np.testing.assert_allclose(
        [fit["intercept"], *fit["coefficients"].values()], expected["coefficients"],
        rtol=1e-12, atol=1e-12,
    )
    np.testing.assert_allclose(
        fit["fitted_log_sd"], expected["fitted_log_sd"], rtol=1e-12, atol=1e-12,
    )
    assert fit["sse"] == pytest.approx(expected["sse"], abs=1e-12)
    assert fit["df_error"] == expected["df_error"]
    assert fit["mse"] == pytest.approx(expected["mse"], abs=1e-12)
    for factor_id, reference_name in zip(("A", "B"), ("X1", "X2")):
        term = fit["terms"][factor_id]
        reference = expected["terms"][reference_name]
        assert term["effect_high_minus_low"] == pytest.approx(
            reference["effect_high_minus_low"], abs=1e-12)
        assert term["standard_error"] == pytest.approx(
            reference["standard_error"], abs=1e-12)
        assert term["adjusted_ss"] == pytest.approx(reference["adjusted_ss"], abs=1e-12)
        assert term["f"] == pytest.approx(reference["f"], abs=1e-12)
        assert term["p"] == pytest.approx(reference["p"], abs=1e-12)


def test_frozen_reference_same_run_measurement_columns_and_input_unchanged():
    reference = REFERENCE["variability"]
    response_names = ("Y1", "Y2", "Y3")
    rows = reference["repeats_across_columns"]
    frame, metadata = _frame(
        [row["point"] for row in rows], [row["measurements"] for row in rows],
        response_names, blocks=[1] * len(rows),
        run_ids=[row["run_id"] for row in rows],
    )
    before = frame.copy(deep=True)

    result = analyze_variability(frame, metadata, response_names, mode="within_run")

    pd.testing.assert_frame_equal(frame, before)
    expected = reference["expected"]
    np.testing.assert_allclose([row["mean"] for row in result["summaries"]], expected["mean"])
    np.testing.assert_allclose([row["sd"] for row in result["summaries"]], expected["sample_sd"])
    assert [row["n"] for row in result["summaries"]] == expected["n"]
    assert [row["missing"] for row in result["summaries"]] == [0] * 4
    assert [row["run_ids"] for row in result["summaries"]] == [[row["run_id"]] for row in rows]
    _assert_reference_fit(result, expected)


def test_frozen_reference_independent_runs_group_by_setting_and_block():
    reference = REFERENCE["variability"]
    rows = reference["replicates_down_rows"]
    frame, metadata = _frame(
        [row["point"] for row in rows], [[row["measurement"]] for row in rows],
        ("Y",), blocks=[row["block"] for row in rows],
        run_ids=[row["run_id"] for row in rows],
    )

    result = analyze_variability(frame, metadata, "Y", mode="independent_runs")

    expected = reference["expected"]
    np.testing.assert_allclose([row["mean"] for row in result["summaries"]], expected["mean"])
    np.testing.assert_allclose([row["sd"] for row in result["summaries"]], expected["sample_sd"])
    assert [row["n"] for row in result["summaries"]] == expected["n"]
    assert [row["missing"] for row in result["summaries"]] == [0] * 4
    assert [row["run_ids"] for row in result["summaries"]] == [
        [row["run_id"] for row in rows[i:i + 3]] for i in range(0, 12, 3)
    ]
    _assert_reference_fit(result, expected)


def test_two_level_general_full_factorial_categorical_factors_use_binary_contrasts():
    factors = (
        FactorSpec("A", "A", None, None, factor_type="categorical",
                   levels=("low", "high")),
        FactorSpec("B", "B", None, None, factor_type="categorical",
                   levels=(100, 200), level_type="numeric"),
    )
    response_names = ("Y1", "Y2", "Y3")
    spec = DesignSpec("categorical-variability", factors, response_names,
                      seed=23, design_type="general_full_factorial")
    frame, metadata = create_general_factorial(spec)
    assert set(metadata["column_map"]["responses"]) == set(response_names)
    measurements = []
    for _, row in frame.iterrows():
        a = -1 if row["设定_A"] == "low" else 1
        b = -1 if row["设定_B"] == 100 else 1
        sd = np.exp(0.5 + 0.2 * a + 0.3 * b + 0.1 * a * b)
        measurements.append([0, -sd, sd])
    for index, name in enumerate(response_names):
        frame[f"响应_{name}"] = [values[index] for values in measurements]

    result = analyze_variability(frame, metadata, response_names)

    assert result["inference_status"] == "available"
    assert result["fit"]["coefficients"] == pytest.approx({"A": 0.2, "B": 0.3})


def test_added_raw_response_column_after_metadata_is_rejected_by_restore():
    frame, metadata = _frame([(-1, -1)], [[0, -1, 1]], ("Y1", "Y2", "Y3"))
    frame["未映射响应"] = [10]

    with pytest.raises(ValueError, match="列名或列顺序已变化"):
        analyze_variability(frame, metadata, ("Y1", "Y2", "Y3"))


def test_edge_zero_sd_and_fewer_than_two_measurements_do_not_log():
    edges = REFERENCE["variability"]["edges"]
    frame, metadata = _frame([(-1, -1)], [edges["zero_variance"]], ("Y1", "Y2", "Y3"))
    zero = analyze_variability(frame, metadata, ("Y1", "Y2", "Y3"))
    assert zero["summaries"][0]["mean"] == 4
    assert zero["summaries"][0]["sd"] == 0
    assert zero["summaries"][0]["n"] == 3
    assert zero["inference_status"] == "zero_sd"
    assert zero["fit"] is None

    frame, metadata = _frame([(-1, -1)], [[edges["one_observation"][0]]], ("Y",))
    one = analyze_variability(frame, metadata, "Y")
    assert one["summaries"][0]["mean"] == 4
    assert one["summaries"][0]["sd"] is None
    assert one["summaries"][0]["n"] == 1
    assert one["inference_status"] == "insufficient_measurements"
    assert one["fit"] is None


def test_edge_missing_and_unequal_sample_sizes_keep_summaries_without_inference():
    edges = REFERENCE["variability"]["edges"]
    frame, metadata = _frame([(-1, -1)], [edges["missing_value"]], ("Y1", "Y2", "Y3"))
    missing = analyze_variability(frame, metadata, ("Y1", "Y2", "Y3"))
    summary = missing["summaries"][0]
    assert summary["mean"] == 3
    assert summary["sd"] == pytest.approx(np.sqrt(2))
    assert summary["n"] == 2 and summary["missing"] == 1
    assert missing["inference_status"] == "missing_measurements"
    assert missing["fit"] is None

    unequal = edges["unequal_group_sizes"]
    points, measurements = [], []
    for point, values in zip(((-1, -1), (1, -1)), unequal):
        points.extend([point] * len(values))
        measurements.extend([[value] for value in values])
    frame, metadata = _frame(points, measurements, ("Y",), blocks=[1] * len(points))
    result = analyze_variability(frame, metadata, "Y", mode="independent_runs")
    assert [row["n"] for row in result["summaries"]] == [3, 2]
    assert [row["missing"] for row in result["summaries"]] == [0, 0]
    assert [row["sd"] for row in result["summaries"]] == pytest.approx([1, np.sqrt(0.5)])
    assert result["inference_status"] == "unequal_sample_sizes"
    assert result["fit"] is None


def test_independent_repeats_stay_within_blocks_and_fit_block_effect():
    points, measurements, blocks = [], [], []
    design_points = REFERENCE["variability"]["design_points"]
    for block in (1, 2):
        for a, b in design_points:
            sd = np.exp(1 + 0.2 * a - 0.3 * b + 0.4 * (block - 1) + 0.1 * a * b)
            for value in (-sd, 0, sd):
                points.append((a, b))
                measurements.append([value])
                blocks.append(block)
    frame, metadata = _frame(points, measurements, ("Y",), blocks=blocks)

    result = analyze_variability(frame, metadata, "Y", mode="independent_runs")

    assert result["inference_status"] == "available"
    assert len(result["summaries"]) == 8
    assert {row["n"] for row in result["summaries"]} == {3}
    assert {row["block"] for row in result["summaries"]} == {1, 2}
    assert all(len(row["run_ids"]) == 3 for row in result["summaries"])
    fit = result["fit"]
    assert fit["rank"] == 4 and fit["df_error"] == 4
    assert fit["coefficients"]["A"] == pytest.approx(0.2)
    assert fit["coefficients"]["B"] == pytest.approx(-0.3)
    assert fit["block_reference"] == 1
    assert fit["block_effects"] == pytest.approx({1: 0, 2: 0.4})


def test_rank_deficient_fit_is_returned_without_unique_effects_or_inference():
    points = [(-1, -1), (-1, -1), (1, 1), (1, 1)]
    measurements = [[0, -1, 1], [0, -1, 1], [0, -2, 2], [0, -2, 2]]
    frame, metadata = _frame(points, measurements, ("Y1", "Y2", "Y3"))

    result = analyze_variability(frame, metadata, ("Y1", "Y2", "Y3"))

    assert result["inference_status"] == "rank_deficient"
    assert result["fit"]["rank"] == 2
    assert len(result["fit"]["fitted_log_sd"]) == 4
    assert result["fit"]["coefficients"] == {"A": None, "B": None}
    assert all(term["f"] is None and term["p"] is None
               for term in result["fit"]["terms"].values())


@pytest.mark.parametrize(
    ("points", "measurements", "expected_status", "expected_df"),
    [
        ([(-1, -1), (1, -1), (-1, 1)], [[0, -1, 1]] * 3, "saturated", 0),
        ([(-1, -1), (1, -1), (-1, 1), (1, 1)], [[0, -1, 1]] * 4,
         "zero_mse", 1),
    ],
)
def test_saturated_and_zero_mse_fits_do_not_report_f_or_p(
        points, measurements, expected_status, expected_df):
    frame, metadata = _frame(points, measurements, ("Y1", "Y2", "Y3"))

    result = analyze_variability(frame, metadata, ("Y1", "Y2", "Y3"))

    assert result["inference_status"] == expected_status
    assert result["fit"]["df_error"] == expected_df
    assert all(term["f"] is None and term["p"] is None
               for term in result["fit"]["terms"].values())


def test_small_nonzero_residual_variance_is_not_treated_as_zero_mse():
    points = REFERENCE["variability"]["design_points"]
    measurements = []
    for a, b in points:
        sd = np.exp(1e-7 * a * b)
        measurements.append([0, -sd, sd])
    frame, metadata = _frame(points, measurements, ("Y1", "Y2", "Y3"))

    result = analyze_variability(frame, metadata, ("Y1", "Y2", "Y3"))

    assert result["inference_status"] == "available"
    assert 0 < result["fit"]["mse"] < 1e-12


def test_rejects_split_plot_and_invalid_analysis_requests():
    hard = FactorSpec("A", "A", -1, 1, randomization_role="hard_to_change")
    easy = FactorSpec("B", "B", -1, 1, randomization_role="easy_to_change")
    spec = DesignSpec("split", (hard, easy), ("Y",), seed=3,
                      design_type="split_plot", block_count=2,
                      randomization_unit="whole_plot", error_structure="split_plot")
    frame, metadata = create_split_plot(spec)
    with pytest.raises(ValueError, match="不支持 Split-Plot"):
        analyze_variability(frame, metadata, "Y")

    frame, metadata = _frame([(-1, -1)], [[0, -1, 1]], ("Y1", "Y2", "Y3"))
    with pytest.raises(ValueError, match="响应不属于"):
        analyze_variability(frame, metadata, "missing")
    with pytest.raises(ValueError, match="只能选择一个"):
        analyze_variability(frame, metadata, ("Y1", "Y2"), mode="independent_runs")
    with pytest.raises(ValueError, match="mode 必须"):
        analyze_variability(frame, metadata, "Y1", mode="other")
