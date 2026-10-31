import json
from pathlib import Path

import numpy as np
import pytest
from scipy.stats import norm

from doe_bbd import create_bbd
from doe_binary_analysis import (
    analyze_binary_doe, fit_grouped_binomial, predict_binary_probability,
)
from doe_core import DesignSpec, FactorSpec
from doe_custom import define_custom
from test_doe_custom_rsm import columns as custom_columns
from test_doe_custom_rsm import factors as custom_factors
from test_doe_custom_rsm import reference_frame as custom_rsm_frame


REFERENCE_DIR = (Path(__file__).parent / "fixtures" /
                 "doe_phase2_binary_reference")
REFERENCE = json.loads((REFERENCE_DIR / "reference.json").read_text(
    encoding="utf-8"))


@pytest.fixture(scope="module")
def rsm_result():
    factors = tuple(FactorSpec(name, name, -1, 1) for name in "ABC")
    spec = DesignSpec("binary-probability", factors, ("Events", "Trials"),
                      seed=37, design_type="box_behnken")
    frame, metadata = create_bbd(spec)
    frame["响应_Events"] = [
        8 + int(row["设定_A"] > 0) + int(row["设定_B"] > 0)
        for _, row in frame.iterrows()
    ]
    frame["响应_Trials"] = 20
    return analyze_binary_doe(
        frame, metadata, "响应_Events", "响应_Trials", "rsm", model_order=1)


def _manual_result(rsm_result, case_name="rsm_linear"):
    result = dict(rsm_result)
    manual = REFERENCE["manual"][case_name]
    result["coefficients_array"] = np.asarray(manual["beta"], dtype=float)
    result["covariance_array"] = np.asarray(manual["covariance"], dtype=float)
    return result, manual


@pytest.mark.parametrize("case_name", (
    "rsm_linear", "negative_eta", "near_zero", "near_one"))
@pytest.mark.parametrize("confidence", (0.90, 0.95, 0.99))
@pytest.mark.parametrize("side", ("two_sided", "one_sided_lower", "one_sided_upper"))
def test_binary_probability_wald_interval_matches_independent_reference(
        rsm_result, case_name, confidence, side):
    result, manual = _manual_result(rsm_result, case_name)
    settings = {"A": 0.5, "B": -0.25, "C": 0.125}
    production_side = {"one_sided_lower": "lower",
                       "one_sided_upper": "upper"}.get(side, side)
    prediction = predict_binary_probability(result, settings, confidence, production_side)
    expected = manual["intervals"][f"{confidence:.0%}"][side]

    np.testing.assert_allclose(
        result["detail"]["term_model"].row(result["detail"]["term_model"].coded(settings)),
        manual["x0"], rtol=0, atol=1e-14,
    )
    for name, value in (("eta_hat", manual["eta"]), ("se_eta", manual["se_eta"]),
                        ("p_hat", manual["probability"]),
                        ("se_p", manual["delta_se_probability"])):
        assert prediction[name] == pytest.approx(value, rel=1e-12, abs=1e-14)
    if side == "two_sided":
        expected_low, expected_high = expected["probability"]
    elif side == "one_sided_lower":
        expected_low, expected_high = expected["probability_interval"][0], None
    else:
        expected_low, expected_high = None, expected["probability_interval"][1]
    for name, value in (("ci_low", expected_low), ("ci_high", expected_high)):
        if value is None:
            assert prediction[name] is None
        else:
            assert prediction[name] == pytest.approx(value, rel=1e-12, abs=1e-14)
    assert prediction["confidence"] == confidence
    assert prediction["side"] == production_side
    assert prediction["model_snapshot"] == result["model_snapshot"]
    assert prediction["interval_status"] == "可用"
    assert "不是未来单次" in prediction["assumption"]


def test_binary_fit_covariance_matches_independent_grouped_glm_reference():
    case = REFERENCE["grouped_glm"]
    column_names = ["Intercept", *case["source"]["predictors"]]
    term_columns = {name: [index] for index, name in enumerate(column_names[1:], 1)}
    fitted = fit_grouped_binomial(
        case["design"], column_names, term_columns,
        case["events"], case["trials"],
    )
    expected = case["expected"]
    np.testing.assert_allclose(fitted["coefficients_array"], expected["coefficients"],
                               rtol=1e-10, atol=1e-12)
    np.testing.assert_allclose(fitted["covariance_array"], expected["covariance"],
                               rtol=1e-9, atol=1e-12)
    np.testing.assert_allclose(fitted["probabilities"], expected["probabilities"],
                               rtol=1e-10, atol=1e-12)


def test_binary_fit_uses_final_fisher_covariance_for_wald_inference():
    matrix = np.asarray([
        [1, -1, -1, 1], [1, 1, -1, -1],
        [1, -1, 1, -1], [1, 1, 1, 1],
    ], dtype=float)
    column_names = ["截距", "A", "B", "A*B"]
    fitted = fit_grouped_binomial(
        matrix, column_names, {"A": [1], "B": [2], "A*B": [3]},
        [2, 5, 5, 8], [10] * 4,
    )
    weights = 10 * fitted["probabilities"] * (1 - fitted["probabilities"])
    information = matrix.T @ (weights[:, None] * matrix)
    expected_covariance = np.linalg.solve(information, np.eye(4))
    expected_se = np.sqrt(np.diag(expected_covariance))
    expected_z = fitted["coefficients_array"] / expected_se

    np.testing.assert_allclose(fitted["covariance_array"], expected_covariance,
                               rtol=1e-12, atol=1e-14)
    np.testing.assert_allclose([row["se"] for row in fitted["coefficients"]],
                               expected_se, rtol=1e-12, atol=1e-14)
    np.testing.assert_allclose([row["z"] for row in fitted["coefficients"]],
                               expected_z, rtol=1e-12, atol=1e-14)
    np.testing.assert_allclose(
        [row["p"] for row in fitted["coefficients"]],
        2 * norm.sf(np.abs(expected_z)), rtol=1e-12, atol=1e-14,
    )


def test_rsm_prediction_interval_uses_final_fisher_covariance(rsm_result):
    matrix = np.asarray(rsm_result["matrix"], dtype=float)
    trials = np.asarray([row["trials"] for row in rsm_result["rows"]], dtype=float)
    probabilities = np.asarray(rsm_result["probabilities"], dtype=float)
    weights = trials * probabilities * (1 - probabilities)
    information = matrix.T @ (weights[:, None] * matrix)
    expected_covariance = np.linalg.solve(information, np.eye(matrix.shape[1]))
    np.testing.assert_allclose(rsm_result["covariance_array"], expected_covariance,
                               rtol=1e-12, atol=1e-14)

    settings = {"A": 0.5, "B": -0.25, "C": 0.125}
    model = rsm_result["detail"]["term_model"]
    x0 = model.row(model.coded(settings))
    eta = float(x0 @ rsm_result["coefficients_array"])
    se_eta = float(np.sqrt(x0 @ expected_covariance @ x0))
    critical = norm.ppf(0.975)
    prediction = predict_binary_probability(rsm_result, settings, confidence=0.95)
    assert prediction["se_eta"] == pytest.approx(se_eta, rel=1e-12, abs=1e-14)
    assert prediction["ci_low"] == pytest.approx(
        1 / (1 + np.exp(-(eta - critical * se_eta))), rel=1e-12, abs=1e-14)
    assert prediction["ci_high"] == pytest.approx(
        1 / (1 + np.exp(-(eta + critical * se_eta))), rel=1e-12, abs=1e-14)


def test_manual_logit_representatives_cover_probability_edges():
    values = REFERENCE["manual"]["logit_representatives"]
    assert 0 < values["-7.0"] < 0.001
    assert values["0.0"] == 0.5
    assert 0.999 < values["7.0"] < 1


def test_probability_interval_is_asymmetric_on_probability_scale(rsm_result):
    result, _ = _manual_result(rsm_result)
    prediction = predict_binary_probability(
        result, {"A": 0.5, "B": -0.25, "C": 0.125}, 0.95, "two_sided")
    assert not np.isclose(prediction["p_hat"] - prediction["ci_low"],
                          prediction["ci_high"] - prediction["p_hat"])


@pytest.mark.parametrize("intercept,probability", ((-1000.0, 0.0), (1000.0, 1.0)))
def test_saturated_probabilities_do_not_report_finite_wald_limits(
        rsm_result, intercept, probability):
    result = dict(rsm_result)
    result["coefficients_array"] = np.asarray([intercept, 0.0, 0.0, 0.0])
    result["covariance_array"] = np.eye(4)
    prediction = predict_binary_probability(
        result, {"A": 0.0, "B": 0.0, "C": 0.0}, 0.95)
    assert prediction["p_hat"] == probability
    assert prediction["ci_low"] is None and prediction["ci_high"] is None
    assert "饱和" in prediction["interval_status"]


@pytest.mark.parametrize("confidence,side", (
    (0, "two_sided"), (1, "two_sided"), (float("nan"), "two_sided"),
    (True, "two_sided"), (0.95, "both"),
))
def test_binary_probability_rejects_invalid_interval_options(
        rsm_result, confidence, side):
    with pytest.raises(ValueError, match="置信水平|区间方向"):
        predict_binary_probability(
            rsm_result, {"A": 0.0, "B": 0.0, "C": 0.0}, confidence, side)


@pytest.mark.parametrize("covariance", (
    np.eye(3), np.full((4, 4), np.nan),
    np.asarray([[1, 1, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1.]]),
    -np.eye(4),
))
def test_binary_probability_rejects_invalid_covariance(rsm_result, covariance):
    result = dict(rsm_result)
    result["covariance_array"] = covariance
    with pytest.raises(ValueError, match="维度|非有限|不对称|半正定"):
        predict_binary_probability(
            result, {"A": 0.0, "B": 0.0, "C": 0.0})


def test_tiny_negative_prediction_variance_is_rounded_only_within_tolerance(rsm_result):
    result = dict(rsm_result)
    result["coefficients_array"] = np.asarray([0.0, 0.0, 0.0, 0.0])
    result["covariance_array"] = np.diag([-1e-16, 0.0, 0.0, 0.0])
    prediction = predict_binary_probability(
        result, {"A": 0.0, "B": 0.0, "C": 0.0})
    assert prediction["se_eta"] == 0
    assert prediction["ci_low"] == prediction["ci_high"] == prediction["p_hat"] == 0.5


def test_binary_probability_rejects_factor_range_and_unfitted_terms(rsm_result):
    with pytest.raises(ValueError, match="超出 DOE 声明范围"):
        predict_binary_probability(
            rsm_result, {"A": 1.1, "B": 0.0, "C": 0.0})
    invalid = dict(rsm_result)
    invalid["column_names"] = ["截距", "wrong", "B", "C"]
    with pytest.raises(ValueError, match="维度不一致"):
        predict_binary_probability(
            invalid, {"A": 0.0, "B": 0.0, "C": 0.0})


def test_custom_rsm_probability_uses_declared_categorical_levels():
    frame = custom_rsm_frame().drop(columns="X3")
    frame["C"] = ["低" if index % 2 else "高" for index in range(len(frame))]
    frame["Events"] = [5 + int(value == "高") + int(x1 > 0)
                       for value, x1 in zip(frame["C"], frame["X1"])]
    frame["Trials"] = 10
    factors = custom_factors()[:2] + (
        FactorSpec("C", "C", None, None, factor_type="categorical",
                   levels=("低", "高")),
    )
    column_map = custom_columns()
    column_map["factors"] = {name: name for name in ("X1", "X2", "C")}
    column_map["responses"] = {"Events": "Events", "Trials": "Trials"}
    frame, metadata, _ = define_custom(
        frame, design_type="custom_rsm", factors=factors,
        responses=("Events", "Trials"), column_map=column_map,
        model_terms=["X1", "X2", "C"], design_id="binary-category-rsm",
    )
    result = analyze_binary_doe(frame, metadata, "Events", "Trials", "rsm")
    prediction = predict_binary_probability(
        result, {"X1": 0.25, "X2": -0.5, "C": "高"})
    expected_row = result["detail"]["term_model"].row(
        result["detail"]["term_model"].coded(
            {"X1": 0.25, "X2": -0.5, "C": "高"}))
    assert prediction["coded"]["C"] == "高"
    assert np.isclose(prediction["eta_hat"],
                      expected_row @ result["coefficients_array"])
    with pytest.raises(ValueError, match="水平不在已声明范围"):
        predict_binary_probability(
            result, {"X1": 0.25, "X2": -0.5, "C": "未知"})
