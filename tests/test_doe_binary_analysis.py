import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from doe_binary_analysis import (
    analyze_binary_doe, fit_grouped_binomial, response_surface_probability_grid,
)
from doe_bbd import create_bbd
from doe_core import DesignSpec, FactorSpec
from doe_dsd import create_dsd
from doe_factorial import create_factorial
from doe_fractional import create_fractional
from doe_general_factorial import create_general_factorial
from doe_pb import create_pb

from test_doe_bbd import spec as bbd_spec
from test_doe_custom_rsm import TERMS, columns as custom_columns, factors as custom_factors
from test_doe_custom_rsm import reference_frame as custom_rsm_frame
from test_doe_dsd import dsd_spec
from test_doe_pb import pb_spec
from doe_custom import define_custom


REFERENCE = json.loads(
    (Path(__file__).parent / "fixtures" / "doe_h_reference" / "reference.json")
    .read_text(encoding="utf-8")
)


@pytest.mark.parametrize("case_name", list(REFERENCE["binary"]))
def test_grouped_logit_matches_independent_doe_reference(case_name):
    case = REFERENCE["binary"][case_name]
    expected = case["expected"]
    term_columns = {name: [index] for index, name in enumerate(case["term_names"][1:], 1)}

    result = fit_grouped_binomial(
        case["columns"], case["term_names"], term_columns,
        case["events"], case["trials"],
    )

    np.testing.assert_allclose(
        [row["coefficient"] for row in result["coefficients"]],
        expected["coefficients"], rtol=1e-10, atol=1e-11,
    )
    np.testing.assert_allclose(
        [row["se"] for row in result["coefficients"]],
        expected["standard_errors"], rtol=1e-6, atol=1e-9,
    )
    np.testing.assert_allclose(
        [row["z"] for row in result["coefficients"]],
        expected["wald_z"], rtol=1e-6, atol=1e-9,
    )
    np.testing.assert_allclose(
        [row["p"] for row in result["coefficients"]],
        expected["wald_p"], rtol=1e-5, atol=1e-9,
    )
    np.testing.assert_allclose(
        result["probabilities"], expected["predicted_probability"],
        rtol=1e-10, atol=1e-11,
    )
    assert result["model_df"] == expected["model_df"]
    assert result["residual_df"] == expected["residual_df"]
    assert result["model_lr"] == pytest.approx(expected["model_lr_chi_square"], rel=1e-9)
    assert result["model_p"] == pytest.approx(expected["model_lr_p"], rel=1e-8)
    assert all(row["status"] == "可用" for row in result["terms"])
    assert all(0 <= row["predicted_probability"] <= 1 for row in result["rows"])


def test_rejects_invalid_counts_all_events_and_complete_separation():
    with pytest.raises(ValueError, match="事件数"):
        fit_grouped_binomial([[1]], ["截距"], {}, [-1], [10])
    with pytest.raises(ValueError, match="试验数"):
        fit_grouped_binomial([[1]], ["截距"], {}, [0], [0])
    with pytest.raises(ValueError, match="大于试验数"):
        fit_grouped_binomial([[1]], ["截距"], {}, [2], [1])
    with pytest.raises(ValueError, match="整数计数"):
        fit_grouped_binomial([[1]], ["截距"], {}, [1.5], [10])

    for events, trials in (([0, 0], [10, 10]), ([10, 10], [10, 10])):
        with pytest.raises(ValueError, match="全部试验"):
            fit_grouped_binomial([[1], [1]], ["截距"], {}, events, trials)

    edge = REFERENCE["binary_edges"]["complete_separation"]
    matrix = np.column_stack((np.ones(len(edge["x"])), edge["x"]))
    with pytest.raises(ValueError, match="分离|未收敛|边界"):
        fit_grouped_binomial(matrix, ["截距", "X1"], {"X1": [1]},
                             edge["events"], edge["trials"])


def test_materially_negative_model_likelihood_ratio_is_unavailable(monkeypatch):
    fits = iter((type("Fit", (), {"llf": -10.1, "fittedvalues": [0.5, 0.5]})(),
                 type("Fit", (), {"llf": -10.0, "fittedvalues": [0.5, 0.5]})()))
    monkeypatch.setattr("doe_binary_analysis._fit_glm", lambda *_args: next(fits))

    with pytest.raises(ValueError, match="似然比较数值不稳定"):
        fit_grouped_binomial(np.ones((2, 1)), ["截距"], {}, [1, 1], [2, 2])


def test_rank_deficiency_identifies_nonestimable_dsd_term():
    edge = REFERENCE["binary_edges"]["rank_deficient_dsd_interaction"]
    points = np.asarray(edge["points"], dtype=float)
    matrix = np.column_stack((np.ones(len(points)), points,
                              edge["interaction_column"]))
    with pytest.raises(ValueError, match=r"秩亏.*X1\*X2"):
        fit_grouped_binomial(
            matrix, ["截距", "X1", "X2", "X1*X2"],
            {"X1": [1], "X2": [2], "X1*X2": [3]},
            [4, 4, 3, 3, 3], [6] * 5,
        )


def _counts_for_frame(frame, fn):
    events, trials = [], []
    for _, row in frame.iterrows():
        event, total = fn(row)
        events.append(event)
        trials.append(total)
    frame["响应_Events"] = pd.Series(events, dtype="Int64")
    frame["响应_Trials"] = pd.Series(trials, dtype="Int64")
    return frame


def _betas(result):
    return [row["coefficient"] for row in result["coefficients"]]


def test_two_level_full_binary_analysis_uses_design_run_mapping():
    spec = DesignSpec(
        "binary-full", (FactorSpec("A", "A", -1, 1), FactorSpec("B", "B", -1, 1)),
        ("Events", "Trials"), seed=11, design_type="two_level_full",
    )
    frame, metadata = create_factorial(spec)
    frame = _counts_for_frame(frame, lambda row: (
        2 if row["设定_A"] == -1 and row["设定_B"] == -1 else
        8 if row["设定_A"] == 1 and row["设定_B"] == 1 else 5, 10))
    frame.index = [0] * len(frame)

    result = analyze_binary_doe(
        frame, metadata, "响应_Events", "响应_Trials", "factorial", model_order=2)

    np.testing.assert_allclose(_betas(result), REFERENCE["binary"]["factorial"][
        "expected"]["coefficients"], rtol=1e-10, atol=1e-11)
    assert [row["run_id"] for row in result["rows"]] == frame["运行ID"].tolist()
    assert result["model_df"] == 3 and result["residual_df"] == 0
    assert result["deviance_p"] is None


def test_dsd_binary_analysis_accepts_selected_hierarchical_square_terms():
    spec = replace(dsd_spec("dsd2", 2), response_names=("Events", "Trials"))
    frame, metadata = create_dsd(spec)
    low, high = spec.factors[0].low, spec.factors[0].high
    frame = _counts_for_frame(frame, lambda row: (
        4 if row["设定_F1"] in (low, high) else 3, 6))

    result = analyze_binary_doe(
        frame, metadata, "响应_Events", "响应_Trials", "screening",
        selected_terms=[("F1",), ("F2",), ("F1", "F1")])

    np.testing.assert_allclose(_betas(result), REFERENCE["binary"]["dsd"][
        "expected"]["coefficients"], rtol=1e-9, atol=1e-10)
    assert result["model_df"] == 3
    with pytest.raises(ValueError, match="必须包含对应主效应"):
        analyze_binary_doe(
            frame, metadata, "响应_Events", "响应_Trials", "screening",
            selected_terms=[("F1", "F2")])


def test_fractional_binary_coefficients_are_labeled_as_alias_groups():
    factors = tuple(FactorSpec(name, name, -1, 1) for name in "ABC")
    spec = DesignSpec("half", factors, ("Events", "Trials"), seed=17,
                      generators=("C=AB",), design_type="two_level_fractional")
    frame, metadata = create_fractional(spec)
    frame = _counts_for_frame(frame, lambda row: (
        8 if all(row[f"设定_{name}"] == 1 for name in "ABC") else 3, 9))

    result = analyze_binary_doe(
        frame, metadata, "响应_Events", "响应_Trials", "factorial", model_order=1)

    expected = REFERENCE["binary"]["fractional_factorial"]["expected"]
    np.testing.assert_allclose(_betas(result), expected["coefficients"], rtol=1e-9, atol=1e-10)
    assert [row["term"] for row in result["coefficients"]] == [
        "截距", "A = B*C", "B = A*C", "C = A*B"]
    assert "完整别名组" in result["assumption"]


def test_pb_binary_analysis_uses_verified_pb_rows_and_only_main_effects():
    spec = replace(pb_spec(12, factors=3), response_names=("Events", "Trials"))
    frame, metadata = create_pb(spec, 12)
    frame = _counts_for_frame(frame, lambda row: (
        4 if row["设定_F1"] == 1 else 2, 6))

    result = analyze_binary_doe(
        frame, metadata, "响应_Events", "响应_Trials", "factorial", model_order=1)

    np.testing.assert_allclose(_betas(result), REFERENCE["binary"]["plackett_burman"][
        "expected"]["coefficients"], rtol=1e-9, atol=1e-10)
    assert result["rank"] == 4 and result["residual_df"] == 8
    assert "未拟合交互混杂" in result["assumption"]


def test_general_factorial_binary_keeps_numeric_levels_categorical():
    factors = (
        FactorSpec("A", "A", None, None, factor_type="categorical",
                   levels=(10, 20, 40), level_type="numeric"),
        FactorSpec("B", "B", None, None, factor_type="categorical",
                   levels=(-1, 1), level_type="numeric"),
    )
    spec = DesignSpec("gff", factors, ("Events", "Trials"), seed=3,
                      design_type="general_full_factorial")
    frame, metadata = create_general_factorial(spec)
    reference = REFERENCE["binary"]["general_full_factorial"]
    events_by_point = dict(zip(map(tuple, reference["design_points"]),
                               reference["events"]))
    frame = _counts_for_frame(frame, lambda row: (
        events_by_point[(row["设定_A"], row["设定_B"])], 30))

    result = analyze_binary_doe(
        frame, metadata, "响应_Events", "响应_Trials", "factorial", model_order=2)

    np.testing.assert_allclose(_betas(result), reference["expected"]["coefficients"],
                               rtol=1e-9, atol=1e-10)
    assert result["model_df"] == 5 and result["residual_df"] == 0


def test_rsm_binary_probability_grid_uses_bbd_quadratic_model():
    spec = replace(bbd_spec(3, centers=2), response_names=("Events", "Trials"))
    frame, metadata = create_bbd(spec)
    reference = REFERENCE["binary"]["rsm"]
    events_by_point = dict(zip(map(tuple, reference["design_points"]), reference["events"]))
    frame = _counts_for_frame(frame, lambda row: (
        events_by_point[tuple(row[f"设定_{name}"] for name in "ABC")], 90))

    result = analyze_binary_doe(
        frame, metadata, "响应_Events", "响应_Trials", "rsm", model_order=2)
    x_grid, y_grid, probability = response_surface_probability_grid(result, "A", "B", points=7)
    np.testing.assert_allclose(_betas(result), reference["expected"]["coefficients"],
                               rtol=1e-8, atol=1e-9)
    assert probability.shape == (7, 7)
    assert np.isfinite(probability).all() and np.all((probability >= 0) & (probability <= 1))


def test_custom_rsm_binary_uses_declared_schema_v5_terms():
    frame = custom_rsm_frame()
    frame["Events"] = pd.Series([5] * len(frame), dtype="Int64")
    frame["Trials"] = pd.Series([10] * len(frame), dtype="Int64")
    response_map = custom_columns()
    response_map["responses"] = {"Events": "Events", "Trials": "Trials"}
    frame, metadata, _ = define_custom(
        frame, design_type="custom_rsm", factors=custom_factors(),
        responses=("Events", "Trials"), column_map=response_map,
        model_terms=TERMS, design_id="binary-custom-rsm",
    )

    result = analyze_binary_doe(
        frame, metadata, "Events", "Trials", "rsm", model_order=2)

    assert result["design"].spec.schema_version == 5
    assert result["rank"] == 10
    np.testing.assert_allclose(_betas(result), np.zeros(10), atol=1e-8)
    assert result["residual_df"] > 0


def test_binary_analysis_requires_declared_count_response_columns():
    spec = DesignSpec(
        "binary-full", (FactorSpec("A", "A", -1, 1), FactorSpec("B", "B", -1, 1)),
        ("Events",), seed=11, design_type="two_level_full",
    )
    frame, metadata = create_factorial(spec)
    with pytest.raises(ValueError, match="已声明并映射的响应列"):
        analyze_binary_doe(frame, metadata, "设定_A", "响应_Events", "factorial")
