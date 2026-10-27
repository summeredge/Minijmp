import math

import numpy as np
import pytest

import doe_optimize
from doe_ccd import create_ccd
from doe_core import DesignSpec, FactorSpec
from doe_optimize import _candidate_rank, _model_value_gradient, optimize_rsm


def _design(response_names=("Y",), factors=None):
    factors = factors or (FactorSpec("A", "A", -1, 1), FactorSpec("B", "B", -1, 1))
    k = len(factors)
    spec = DesignSpec(
        "opt-ccd", factors, response_names, seed=23, design_type="central_composite",
        ccd_alpha=2 ** (k / 4), ccd_center_points=5, ccd_axial_points=2 * k,
    )
    return create_ccd(spec)


def _set_y(frame, functions):
    coded = frame[[f"编码_{factor}" for factor in "AB"]].to_numpy(dtype=float)
    a, b = coded.T
    for name, function in functions.items():
        frame[f"响应_{name}"] = function(a, b)
    return coded


def _objective(mode, low=-10, high=10, target=None, power_low=1, power_high=1, weight=1):
    return {
        "mode": mode, "low": low, "high": high, "target": target,
        "power_low": power_low, "power_high": power_high, "weight": weight,
    }


def test_two_factor_prediction_and_analytic_gradient_reference():
    coefficients = np.array([40, 3, -2, 5, -1.5, 4], dtype=float)
    a, b = 0.25, -0.4
    predicted, gradient = _model_value_gradient(coefficients, np.array([a, b]))
    reference = 40 + 3*a - 2*b + 4*a*b + 5*a*a - 1.5*b*b
    reference_gradient = np.array([3 + 4*b + 10*a, -2 + 4*a - 3*b])
    assert predicted == pytest.approx(reference, abs=1e-13)
    np.testing.assert_allclose(gradient, reference_gradient, rtol=0, atol=1e-13)


@pytest.mark.parametrize(
    "mode, polynomial, expected",
    [
        ("maximize", lambda a, b: 10 - (a - 0.2)**2 - 2*(b + 0.1)**2, (0.2, -0.1)),
        ("minimize", lambda a, b: (a - 0.3)**2 + 2*(b + 0.2)**2, (0.3, -0.2)),
    ],
)
def test_single_response_optimizes_prediction_even_on_desirability_plateau(
        mode, polynomial, expected):
    frame, metadata = _design()
    _set_y(frame, {"Y": polynomial})
    # d is constant at 1 throughout this response range; the raw objective must still move.
    config = _objective(mode, low=-100 if mode == "maximize" else 100,
                        high=-50 if mode == "maximize" else 200)
    result = optimize_rsm(frame, metadata, {"Y": config})
    assert result["success"] and result["status"] == "success"
    assert result["best"]["coded"]["A"] == pytest.approx(expected[0], abs=1e-6)
    assert result["best"]["coded"]["B"] == pytest.approx(expected[1], abs=1e-6)
    assert result["best"]["desirabilities"]["Y"] == 1
    assert result["best"]["objective_value"] == pytest.approx(
        result["best"]["predictions"]["Y"] * (1 if mode == "maximize" else -1))


@pytest.mark.parametrize("amplitude,threshold", [(1.0, 1e150), (1e-200, 1e-190)])
def test_single_response_search_is_not_scaled_by_desirability_thresholds(amplitude, threshold):
    frame, metadata = _design()
    _set_y(frame, {"Y": lambda a, b: amplitude * (10 - (a - .3)**2 - 2*(b + .4)**2)})
    result = optimize_rsm(
        frame, metadata,
        {"Y": _objective("maximize", low=-threshold, high=threshold)},
    )
    assert result["success"]
    assert result["best"]["coded"]["A"] == pytest.approx(.3, abs=1e-6)
    assert result["best"]["coded"]["B"] == pytest.approx(-.4, abs=1e-6)


def test_single_response_maximizes_to_a_box_boundary():
    frame, metadata = _design()
    _set_y(frame, {"Y": lambda a, b: a + 2*b})
    result = optimize_rsm(frame, metadata, {"Y": _objective("maximize", -100, -50)})
    assert result["success"]
    assert result["best"]["coded"]["A"] == pytest.approx(1, abs=1e-12)
    assert result["best"]["coded"]["B"] == 1.0
    assert result["best"]["predictions"]["Y"] == pytest.approx(3)


def test_saddle_and_flat_response_are_handled_deterministically():
    frame, metadata = _design()
    _set_y(frame, {"Y": lambda a, b: a*a - b*b})
    saddle = optimize_rsm(frame, metadata, {"Y": _objective("maximize")})
    assert saddle["success"]
    assert abs(saddle["best"]["coded"]["A"]) == pytest.approx(1, abs=1e-7)
    assert saddle["best"]["coded"]["B"] == pytest.approx(0, abs=1e-7)

    frame, metadata = _design()
    _set_y(frame, {"Y": lambda a, b: np.full_like(a, 7.0)})
    config = {"Y": _objective("maximize")}
    first = optimize_rsm(frame, metadata, config)
    second = optimize_rsm(frame, metadata, config)
    assert first["success"] and first["best"]["predictions"]["Y"] == pytest.approx(7)
    assert first["best"]["coded"] == second["best"]["coded"]


def test_fixed_factor_and_actual_levels_are_returned():
    factors = (FactorSpec("A", "温度", 10, 20), FactorSpec("B", "压力", 100, 200))
    frame, metadata = _design(factors=factors)
    _set_y(frame, {"Y": lambda a, b: 10 - (a - 0.2)**2 - (b + 0.1)**2})
    result = optimize_rsm(
        frame, metadata, {"Y": _objective("maximize", -100, -50)},
        {"B": (0.5, 0.5)},
    )
    assert result["success"] and result["best"]["feasible"]
    assert result["best"]["coded"]["A"] == pytest.approx(0.2, abs=1e-6)
    assert result["best"]["coded"]["B"] == 0.5
    assert float(result["best"]["factor_levels"]["A"]) == pytest.approx(16)
    assert float(result["best"]["factor_levels"]["B"]) == pytest.approx(175)


def test_decimal_fixed_level_rounds_to_binary64_with_doe_encoding_tolerance():
    factors = (FactorSpec("A", "温度", 0.1, 0.2), FactorSpec("B", "压力", -1, 1))
    frame, metadata = _design(factors=factors)
    _set_y(frame, {"Y": lambda a, b: a + b})
    code = float(factors[0].to_coded(0.15))
    result = optimize_rsm(
        frame, metadata, {"Y": _objective("maximize")},
        {"A": (code, code), "B": (0, 0)},
    )
    actual = result["best"]["factor_levels"]["A"]
    assert actual == float(actual)
    assert actual == pytest.approx(0.15, abs=1e-16)
    assert abs(float(factors[0].to_coded(actual)) - code) <= 1e-8
    assert result["best"]["factor_encoding_errors"]["A"] <= 1e-8


def test_target_equality_curve_is_found_away_from_the_center():
    frame, metadata = _design()
    _set_y(frame, {"Y": lambda a, b: a*a + b*b})
    result = optimize_rsm(
        frame, metadata,
        {"Y": _objective("target", low=-1, high=1, target=0.5)},
        {"A": (-0.75, 0.75), "B": (-0.75, 0.75)},
    )
    assert result["success"]
    assert result["best"]["predictions"]["Y"] == pytest.approx(0.5, abs=1e-7)
    assert any(item["feasible"] and abs(item["predictions"]["Y"] - 0.5) <= 1e-7
               for item in result["candidates"])
    assert result["global_optimum_guaranteed"] is False


def test_single_target_uses_normalized_squared_error_and_analytic_gradient(monkeypatch):
    frame, metadata = _design()
    _set_y(frame, {"Y": lambda a, b: a*a + 2*b})
    comparisons = []

    class Success:
        success = True
        nfev = 1

        def __init__(self, x):
            self.x = np.asarray(x)
            self.message = "test solver"

    def inspect_objective(function, start, **kwargs):
        assert kwargs["jac"] is True
        _, analytic = function(start)
        numeric = []
        for index in range(len(start)):
            plus, minus = np.asarray(start).copy(), np.asarray(start).copy()
            plus[index] += 1e-6
            minus[index] -= 1e-6
            numeric.append((function(plus)[0] - function(minus)[0]) / 2e-6)
        comparisons.append((analytic, numeric))
        return Success(start)

    monkeypatch.setattr(doe_optimize, "minimize", inspect_objective)
    optimize_rsm(
        frame, metadata,
        {"Y": _objective("target", low=-1, high=10, target=1.2,
                         power_low=4, power_high=1)},
        {"B": (0.25, 0.25)},
    )
    assert comparisons
    for analytic, numeric in comparisons:
        np.testing.assert_allclose(analytic, numeric, rtol=1e-6, atol=1e-7)


def test_unreachable_target_returns_best_feasible_candidate_and_error():
    frame, metadata = _design()
    _set_y(frame, {"Y": lambda a, b: a*a + b*b})
    result = optimize_rsm(
        frame, metadata,
        {"Y": _objective("target", low=-1, high=10, target=3,
                         power_low=4, power_high=1)},
    )
    assert not result["success"] and result["status"] == "infeasible"
    assert result["best"] is not None and result["best"]["feasible"]
    assert result["best"]["predictions"]["Y"] == pytest.approx(2, abs=1e-7)
    assert result["best"]["target_difference"] == pytest.approx(1, abs=1e-7)
    assert result["best"]["objective_value"] == pytest.approx(
        result["best"]["target_difference_normalized"]**2, abs=1e-12)
    assert result["candidates"]


def test_unreachable_target_ranking_uses_absolute_error_not_asymmetric_desirability():
    config = {"Y": _objective("target", low=-1, high=10, target=0,
                              power_low=5, power_high=1)}
    nearer = {
        "target_difference_normalized": 0.1,
        "composite_desirability": 0.9 ** 5,
    }
    farther = {
        "target_difference_normalized": 0.2,
        "composite_desirability": 0.98,
    }
    assert farther["composite_desirability"] > nearer["composite_desirability"]
    assert _candidate_rank(nearer, config) > _candidate_rank(farther, config)


@pytest.mark.parametrize(("prediction", "power", "base"), [
    (-0.3, 1, 0.7),
    (0.2, 10, 0.8),
])
def test_asymmetric_target_desirability_power_score_and_gradient_match_each_side(
        prediction, power, base):
    config = _objective("target", low=-1, high=1, target=0,
                        power_low=1, power_high=10)
    model = {"config": config,
             "normalized": {"low": -1, "high": 1, "target": 0}}
    raw, slope, selected_power = doe_optimize._raw_desirability(prediction, model)
    score, log_score, infeasible = doe_optimize._desirability_info(prediction, model)
    assert selected_power == power
    assert score == pytest.approx(base ** power)
    assert log_score == pytest.approx(power * math.log(base))
    assert not infeasible

    epsilon, step = 1e-12, 1e-6

    def continuous_objective(value):
        side_raw = value + 1 if value < 0 else 1 - value
        return -power * math.log(epsilon + side_raw)

    finite_difference = (continuous_objective(prediction + step)
                         - continuous_objective(prediction - step)) / (2 * step)
    analytic_gradient = -selected_power * slope / (epsilon + raw)
    assert analytic_gradient == pytest.approx(finite_difference, rel=1e-6, abs=1e-7)

    at_target, target_slope, _ = doe_optimize._raw_desirability(0, model)
    target_score = doe_optimize._desirability_info(0, model)
    assert at_target == 1 and target_slope == 0
    assert target_score[0] == 1 and not target_score[2]


def test_weighted_target_desirability_matches_independent_analytic_optimum():
    frame, metadata = _design(("Y1", "Y2"))
    _set_y(frame, {"Y1": lambda a, b: a, "Y2": lambda a, b: a})
    objectives = {
        "Y1": _objective("target", low=-1, target=0, high=1,
                         power_low=1, power_high=10, weight=1),
        "Y2": _objective("maximize", low=-1, high=1,
                         power_low=1, weight=12),
    }
    result = optimize_rsm(frame, metadata, objectives, {"B": (0, 0)})

    def reference(a):
        return math.exp((10 * math.log(1 - a)
                         + 12 * math.log((a + 1) / 2)) / 13)

    assert reference(0) == pytest.approx(0.527383, abs=1e-6)
    assert reference(1 / 11) == pytest.approx(0.531089, abs=1e-6)
    assert reference(11 / 13) == pytest.approx(0.220087, abs=1e-6)
    assert result["best"]["coded"]["A"] == pytest.approx(1 / 11, abs=1e-5)
    assert result["best"]["composite_desirability"] >= reference(1 / 11) - 1e-7


def test_weighted_geometric_mean_matches_manual_reference_and_weight_trend():
    frame, metadata = _design(("Y1", "Y2"))
    _set_y(frame, {"Y1": lambda a, b: 2*a, "Y2": lambda a, b: -2*a})
    objectives = {
        "Y1": _objective("maximize", low=-2, high=2, weight=1),
        "Y2": _objective("maximize", low=-2, high=2, weight=3),
    }
    result = optimize_rsm(frame, metadata, objectives)
    best = result["best"]
    assert best["coded"]["A"] == pytest.approx(-0.5, abs=1e-6)
    d1 = (best["predictions"]["Y1"] + 2) / 4
    d2 = (best["predictions"]["Y2"] + 2) / 4
    expected = (d1 * d2**3) ** 0.25
    assert best["desirabilities"] == pytest.approx({"Y1": d1, "Y2": d2})
    assert best["composite_desirability"] == pytest.approx(expected, abs=1e-10)
    assert best["objective_value"] == pytest.approx(expected, abs=1e-10)

    equal_weight = {name: dict(config, weight=1) for name, config in objectives.items()}
    heavier_second = {name: dict(config, weight=(4 if name == "Y2" else 1))
                      for name, config in objectives.items()}
    a_equal = optimize_rsm(frame, metadata, equal_weight)["best"]["coded"]["A"]
    a_heavy = optimize_rsm(frame, metadata, heavier_second)["best"]["coded"]["A"]
    assert a_equal == pytest.approx(0, abs=1e-6)
    assert a_heavy < a_equal


def test_maximize_minimize_and_target_powers_match_manual_desirabilities():
    frame, metadata = _design(("larger", "smaller", "target"))
    _set_y(frame, {
        "larger": lambda a, b: a,
        "smaller": lambda a, b: a,
        "target": lambda a, b: a,
    })
    objectives = {
        "larger": _objective("maximize", -1, 1, power_low=2, weight=1),
        "smaller": _objective("minimize", -1, 1, power_high=3, weight=2),
        "target": _objective("target", -1, 1, target=0, power_low=2,
                             power_high=3, weight=3),
    }
    result = optimize_rsm(frame, metadata, objectives, {"A": (0.25, 0.25), "B": (0, 0)})
    best = result["best"]
    expected = {
        "larger": ((0.25 + 1) / 2) ** 2,
        "smaller": ((1 - 0.25) / 2) ** 3,
        "target": ((1 - 0.25) / (1 - 0)) ** 3,
    }
    composite = math.exp(sum(
        objectives[name]["weight"] * math.log(value)
        for name, value in expected.items()
    ) / sum(config["weight"] for config in objectives.values()))
    assert best["desirabilities"] == pytest.approx(expected, abs=1e-12)
    assert best["composite_desirability"] == pytest.approx(composite, abs=1e-12)


def test_response_powers_and_zero_desirability_log_semantics():
    frame, metadata = _design(("Y1", "Y2"))
    _set_y(frame, {"Y1": lambda a, b: a, "Y2": lambda a, b: -a})
    shaped = {
        "Y1": _objective("maximize", low=-1, high=1, power_low=2),
        "Y2": _objective("maximize", low=-1, high=1),
    }
    shaped_result = optimize_rsm(frame, metadata, shaped)
    assert shaped_result["best"]["coded"]["A"] == pytest.approx(1/3, abs=1e-6)

    incompatible = {
        "Y1": _objective("maximize", low=0, high=1),
        "Y2": _objective("maximize", low=0, high=1),
    }
    zero = optimize_rsm(frame, metadata, incompatible)
    assert not zero["success"] and zero["status"] == "zero_desirability"
    assert zero["best"]["feasible"]
    assert zero["best"]["composite_desirability"] == 0
    assert zero["best"]["log_composite_desirability"] is None
    assert math.isfinite(zero["best"]["objective_value"])


def test_positive_but_unrepresentable_composite_is_reported_as_underflow():
    frame, metadata = _design(("Y1", "Y2"))
    _set_y(frame, {"Y1": lambda a, b: np.full_like(a, .5),
                   "Y2": lambda a, b: np.full_like(a, .5)})
    objectives = {
        name: _objective("maximize", 0, 1, power_low=1e300)
        for name in ("Y1", "Y2")
    }
    result = optimize_rsm(frame, metadata, objectives, {"A": (0, 0), "B": (0, 0)})
    assert not result["success"] and result["status"] == "numerical_underflow"
    assert result["best"]["composite_desirability"] == 0
    assert math.isfinite(result["best"]["log_composite_desirability"])


def test_desirability_has_exact_continuous_boundary_values():
    maximize = {"mode": "maximize", "power_low": 2, "power_high": 1}
    minimize = {"mode": "minimize", "power_low": 1, "power_high": 3}
    target = {"mode": "target", "power_low": 2, "power_high": 3, "target": 5}
    models = [
        {"config": maximize, "normalized": {"low": 0, "high": 10}},
        {"config": minimize, "normalized": {"low": 0, "high": 10}},
        {"config": target, "normalized": {"low": 0, "high": 10, "target": 5}},
    ]
    assert [doe_optimize._desirability_info(y, models[0])[0] for y in (0, 10)] == [0, 1]
    assert [doe_optimize._desirability_info(y, models[1])[0] for y in (0, 10)] == [1, 0]
    assert [doe_optimize._desirability_info(y, models[2])[0] for y in (0, 5, 10)] == [0, 1, 0]


def test_negative_large_scale_response_is_finite_and_single_d_zero_is_not_failure():
    frame, metadata = _design()
    _set_y(frame, {"Y": lambda a, b: -1e120 + 2e119*a})
    result = optimize_rsm(
        frame, metadata,
        {"Y": _objective("maximize", low=1e110, high=2e110)},
    )
    assert result["success"] and result["status"] == "success"
    assert result["best"]["coded"]["A"] == pytest.approx(1, abs=1e-7)
    assert result["best"]["predictions"]["Y"] == pytest.approx(-8e119, rel=1e-12)
    assert result["best"]["desirabilities"]["Y"] == 0
    assert result["best"]["composite_desirability"] == 0


@pytest.mark.parametrize(
    "bounds",
    [
        {"A": (0.5, -0.5)}, {"A": (-1.01, 0)}, {"A": (0, math.inf)},
        {"A": (0, float("nan"))}, {"unknown": (-1, 1)}, {"A": (True, 1)},
        {"A": (.5, np.nextafter(.5, 1.0))},
    ],
)
def test_bounds_must_be_finite_ordered_and_only_tighten(bounds):
    frame, metadata = _design()
    _set_y(frame, {"Y": lambda a, b: a + b})
    with pytest.raises(ValueError):
        optimize_rsm(frame, metadata, {"Y": _objective("maximize")}, bounds)


def test_complete_ccd_is_explicitly_validated_before_coefficients_are_used(monkeypatch):
    frame, metadata = _design()
    _set_y(frame, {"Y": lambda a, b: a + b})
    validator = doe_optimize.doe_ccd.validate_ccd
    calls = []

    def spy(design):
        calls.append(design)
        return validator(design)

    monkeypatch.setattr(doe_optimize.doe_ccd, "validate_ccd", spy)
    result = optimize_rsm(frame, metadata, {"Y": _objective("maximize")})
    assert len(calls) >= 2  # worksheet restoration and explicit optimization-entry validation
    assert {
        "success", "status", "method", "global_optimum_guaranteed", "snapshot_id",
        "best", "candidates", "models", "solver_evaluations",
        "evaluation_limit_per_start", "limitations",
    } <= result.keys()
    assert result["snapshot_id"] == doe_optimize._snapshot_id(frame, metadata)
    assert set(result["models"]["Y"]) == {"coefficients"}
    unchanged = optimize_rsm(frame, metadata, {"Y": _objective("maximize")})
    assert unchanged["snapshot_id"] == result["snapshot_id"]
    frame.loc[frame.index[0], "响应_Y"] += 0.5
    changed = optimize_rsm(frame, metadata, {"Y": _objective("maximize")})
    assert changed["snapshot_id"] != result["snapshot_id"]
    assert {"feasible", "coded", "factor_levels", "predictions", "desirabilities",
            "composite_desirability", "objective_value"} <= result["best"].keys()
    for candidate in result["candidates"]:
        if candidate["feasible"]:
            assert all(-1 <= value <= 1 for value in candidate["coded"].values())
        else:
            assert candidate["objective_value"] is None and candidate["status"]


def test_incomplete_ccd_is_rejected_before_optimization():
    frame, metadata = _design()
    _set_y(frame, {"Y": lambda a, b: a + b})
    bad_metadata = {
        **metadata,
        "design": {**metadata["design"], "ccd_axial_points": 3},
    }
    with pytest.raises(ValueError):
        optimize_rsm(frame, bad_metadata, {"Y": _objective("maximize")})


@pytest.mark.parametrize("config", [
    _objective("maximize", low=1, high=1),
    _objective("maximize", power_low=0),
    _objective("maximize", power_high=math.inf),
    _objective("maximize", weight=0),
    _objective("maximize", weight=math.nan),
    _objective("maximize", low=1, high=np.nextafter(1.0, math.inf)),
    _objective("target", low=0, high=1, target=0),
    _objective("target", low=0, high=1, target=1),
])
def test_invalid_objective_thresholds_powers_and_weights_are_rejected(config):
    frame, metadata = _design()
    _set_y(frame, {"Y": lambda a, b: a + b})
    with pytest.raises(ValueError):
        optimize_rsm(frame, metadata, {"Y": config})


@pytest.mark.parametrize("value", [np.nan, np.inf, -np.inf])
def test_nonfinite_response_values_are_rejected(value):
    frame, metadata = _design()
    _set_y(frame, {"Y": lambda a, b: a + b})
    frame.loc[frame.index[0], "响应_Y"] = value
    with pytest.raises(ValueError):
        optimize_rsm(frame, metadata, {"Y": _objective("maximize")})


def test_solver_failure_keeps_a_finite_bounds_feasible_candidate(monkeypatch):
    frame, metadata = _design()
    _set_y(frame, {"Y": lambda a, b: a + b})

    class Failed:
        success = False

        def __init__(self, x):
            self.x = np.asarray(x)

    monkeypatch.setattr(doe_optimize, "minimize",
                        lambda function, x0, **kwargs: Failed(x0))
    result = optimize_rsm(frame, metadata, {"Y": _objective("maximize")})
    assert not result["success"] and result["status"] == "solver_failure"
    assert result["best"] is not None and result["best"]["feasible"]
    assert all(math.isfinite(value) for value in result["best"]["predictions"].values())
    assert math.isfinite(result["best"]["objective_value"])


def test_function_evaluation_limit_is_reported_as_failure(monkeypatch):
    frame, metadata = _design()
    _set_y(frame, {"Y": lambda a, b: a + b})

    class Limited:
        success = False
        nfev = 1
        message = "evaluation limit"

        def __init__(self, x):
            self.x = np.asarray(x)

    monkeypatch.setattr(doe_optimize, "_MAX_EVALUATIONS_PER_START", 1)
    monkeypatch.setattr(doe_optimize, "minimize",
                        lambda function, x0, **kwargs: Limited(x0))
    result = optimize_rsm(frame, metadata, {"Y": _objective("maximize")})
    assert not result["success"] and result["status"] == "solver_failure"
    assert "评价上限" in result["reason"]
    assert result["solver_evaluations"] == result["evaluation_limit_per_start"] * 9
    assert result["best"]["feasible"]
    assert result["best"]["coded"] == {"A": 1.0, "B": 1.0}
    assert len(result["candidates"]) == 18
    assert all({"feasible", "coded", "objective_value", "status"} <= item.keys()
               for item in result["candidates"])

