import json
import math
from pathlib import Path
from threading import Event
from types import SimpleNamespace

import numpy as np
import pytest

from doe_bbd import create_bbd
from doe_binary_analysis import analyze_binary_doe
from doe_core import DesignSpec, FactorSpec
from doe_custom import define_custom
from doe_optimize import optimize_binary_rsm
from test_doe_custom_rsm import columns as custom_columns
from test_doe_custom_rsm import factors as custom_factors
from test_doe_custom_rsm import reference_frame as custom_rsm_frame


REFERENCE = json.loads((Path(__file__).parent / "fixtures"
                        / "doe_phase2_binary_reference" / "reference.json").read_text(
                            encoding="utf-8"))["optimizer"]


def _binary_with_eta(analysis, intercept, linear, quadratic):
    changed = dict(analysis)
    coefficients = np.zeros_like(analysis["coefficients_array"], dtype=float)
    for name, value in (("截距", intercept), ("A", linear), ("A²", quadratic)):
        coefficients[analysis["column_names"].index(name)] = value
    changed["coefficients_array"] = coefficients
    return changed


def _reference_expit(eta):
    if eta >= 0:
        return 1 / (1 + math.exp(-eta))
    exp_eta = math.exp(eta)
    return exp_eta / (1 + exp_eta)


def _reference_desirability(goal, probability, lower, target, upper, weight):
    if goal == "maximize":
        if probability <= lower:
            return 0.0
        if probability >= target:
            return 1.0
        return ((probability - lower) / (target - lower)) ** weight
    if goal == "minimize":
        if probability <= target:
            return 1.0
        if probability >= upper:
            return 0.0
        return ((upper - probability) / (upper - target)) ** weight
    if probability <= lower or probability >= upper:
        return 0.0
    if probability <= target:
        return ((probability - lower) / (target - lower)) ** weight
    return ((upper - probability) / (upper - target)) ** weight


def _assert_probability_matches_model_row(analysis, result):
    model = analysis["detail"]["term_model"]
    eta = model.row(model.coded(result["settings"])) @ analysis["coefficients_array"]
    assert result["probability"] == pytest.approx(_reference_expit(float(eta)), abs=1e-14)


@pytest.fixture(scope="module")
def binary_quadratic():
    factors = tuple(FactorSpec(name, name, -1, 1) for name in "ABC")
    spec = DesignSpec("binary-optimize", factors, ("Events", "Trials"),
                      seed=37, design_type="box_behnken")
    frame, metadata = create_bbd(spec)
    frame["响应_Events"] = [
        8 + int(row["设定_A"] > 0) + int(row["设定_B"] > 0)
        for _, row in frame.iterrows()
    ]
    frame["响应_Trials"] = 20
    analysis = analyze_binary_doe(
        frame, metadata, "响应_Events", "响应_Trials", "rsm", model_order=2)
    coefficients = np.zeros(len(analysis["column_names"]))
    coefficients[analysis["column_names"].index("截距")] = 0.2
    coefficients[analysis["column_names"].index("A")] = 1.0
    coefficients[analysis["column_names"].index("A²")] = -1.0
    analysis["coefficients_array"] = coefficients
    return frame, analysis


@pytest.fixture(scope="module")
def binary_categorical():
    frame = custom_rsm_frame().drop(columns="X3")
    frame["C"] = ["低" if index % 2 else "高" for index in range(len(frame))]
    frame["Events"] = [5 + int(level == "高") + int(x1 > 0)
                       for level, x1 in zip(frame["C"], frame["X1"])]
    frame["Trials"] = 10
    factors = custom_factors()[:2] + (
        FactorSpec("C", "C", None, None, factor_type="categorical",
                   levels=("低", "高")),
    )
    column_map = custom_columns()
    column_map["factors"] = {name: name for name in ("X1", "X2", "C")}
    column_map["responses"] = {name: name for name in ("Events", "Trials")}
    frame, metadata, _ = define_custom(
        frame, design_type="custom_rsm", factors=factors,
        responses=("Events", "Trials"), column_map=column_map,
        model_terms=["X1", "X2", "C"], design_id="binary-category-optimize",
    )
    analysis = analyze_binary_doe(frame, metadata, "Events", "Trials", "rsm")
    coefficients = np.zeros(len(analysis["column_names"]))
    category_column = next(name for name in analysis["column_names"] if name.startswith("C["))
    coefficients[analysis["column_names"].index(category_column)] = 1.0
    analysis["coefficients_array"] = coefficients
    return frame, analysis


def test_binary_probability_extrema_match_independent_analytic_reference(binary_quadratic):
    _, analysis = binary_quadratic
    oracle = REFERENCE["direct_extrema"]
    result = optimize_binary_rsm(
        analysis, goal="maximize", criterion="probability", lower=0.0, target=0.6)
    assert result["settings"]["A"] == pytest.approx(oracle["maximum"]["x"], abs=2e-5)
    assert result["probability"] == pytest.approx(oracle["maximum"]["probability"], abs=1e-10)
    assert result["global_optimum_proven"] is False
    assert result["success"] is True
    assert "不证明连续域全局最优" in result["method"]
    model = analysis["detail"]["term_model"]
    expected_probability = 1 / (1 + np.exp(-(
        model.row(model.coded(result["settings"])) @ analysis["coefficients_array"])))
    assert result["probability"] == pytest.approx(expected_probability, abs=1e-14)

    minimum = optimize_binary_rsm(
        analysis, goal="minimize", criterion="probability", target=0.2, upper=0.8)
    assert minimum["settings"]["A"] == pytest.approx(oracle["minimum"]["x"], abs=2e-5)
    assert minimum["probability"] == pytest.approx(oracle["minimum"]["probability"], abs=1e-10)


def test_binary_target_uses_nearest_root_and_reports_unreachable(binary_quadratic):
    _, analysis = binary_quadratic
    oracle = REFERENCE["target_probability"]
    target = 0.57
    result = optimize_binary_rsm(
        analysis, goal="target", criterion="probability",
        lower=0.4, target=target, upper=0.8)
    expected = oracle["roots"][0]
    assert result["settings"]["A"] == pytest.approx(expected, abs=2e-5)
    assert result["target_reached"] is True
    assert result["objective_value"] == pytest.approx(
        (result["probability"] - target) ** 2, abs=1e-16)

    unreachable = optimize_binary_rsm(
        analysis, goal="target", criterion="probability",
        lower=0.9, target=0.99, upper=1.0)
    assert unreachable["probability"] == pytest.approx(0.610639233949222, abs=1e-8)
    assert unreachable["target_reached"] is False
    assert "不证明目标在域内不可达" in unreachable["target_status"]


@pytest.mark.parametrize(
    "goal,lower,target,upper,weight,probability,expected",
    [
        ("maximize", 0.4, 0.6, None, 2.0, 1 / (1 + np.exp(-0.2)),
         ((1 / (1 + np.exp(-0.2)) - 0.4) / 0.2) ** 2),
        ("minimize", None, 0.4, 0.7, 0.5, 1 / (1 + np.exp(-0.2)),
         ((0.7 - 1 / (1 + np.exp(-0.2))) / 0.3) ** 0.5),
        ("target", 0.4, 0.6, 0.7, 1.5, 1 / (1 + np.exp(-0.2)),
         ((1 / (1 + np.exp(-0.2)) - 0.4) / 0.2) ** 1.5),
    ],
)
def test_binary_desirability_modes_and_weight_with_fixed_factors(
        binary_quadratic, goal, lower, target, upper, weight, probability, expected):
    _, analysis = binary_quadratic
    result = optimize_binary_rsm(
        analysis, goal=goal, criterion="desirability", lower=lower,
        target=target, upper=upper, weight=weight,
        bounds={name: (0, 0) for name in "ABC"},
    )
    assert result["probability"] == pytest.approx(probability)
    assert result["desirability"] == pytest.approx(expected)
    assert result["objective_value"] == pytest.approx(expected)
    assert result["global_optimum_proven"] is True
    assert result["status"] == "exact_enumeration"


def test_binary_desirability_plateau_tie_prefers_nearest_domain_center(binary_quadratic):
    _, analysis = binary_quadratic
    result = optimize_binary_rsm(
        analysis, goal="maximize", criterion="desirability",
        lower=0.4, target=0.6, bounds={"A": (0.2, 0.8), "B": (0, 0), "C": (0, 0)},
    )
    assert result["desirability"] == 1.0
    assert result["settings"]["A"] == pytest.approx(0.5, abs=2e-5)


@pytest.mark.parametrize("goal,lower,target,upper", [
    ("maximize", 0.4, 0.6, None),
    ("minimize", None, 0.4, 0.7),
    ("target", 0.4, 0.57, 0.8),
])
def test_binary_desirability_search_uses_probability_gradient(
        binary_quadratic, goal, lower, target, upper):
    _, analysis = binary_quadratic
    result = optimize_binary_rsm(
        analysis, goal=goal, criterion="desirability", lower=lower,
        target=target, upper=upper, weight=1.5)
    if goal == "maximize":
        assert result["probability"] >= target - 1e-8
        lo, hi = REFERENCE["desirability"]["maximum_platform"]["interval"]
        assert lo - 1e-8 <= result["settings"]["A"] <= hi + 1e-8
    elif goal == "minimize":
        assert result["probability"] <= target + 1e-8
    else:
        assert abs(result["probability"] - target) <= 1e-8
    assert result["desirability"] == pytest.approx(1.0, abs=1e-10)
    assert result["solver_converged"] is True


def test_binary_target_desirability_escapes_zero_platform(binary_quadratic):
    _, base = binary_quadratic
    analysis = _binary_with_eta(base, 0.0, 20.0, 0.0)
    lower, target, upper, weight = 0.90, 0.95, 0.99, 1.5
    for coded_a in (-1.0, 0.0, 1.0):
        probability = _reference_expit(20 * coded_a)
        assert _reference_desirability(
            "target", probability, lower, target, upper, weight) == 0.0

    args = dict(goal="target", criterion="desirability", lower=lower,
                target=target, upper=upper, weight=weight)
    result = optimize_binary_rsm(analysis, **args)
    repeated = optimize_binary_rsm(analysis, **args)
    expected_x = math.log(target / (1 - target)) / 20
    expected_probability = _reference_expit(20 * expected_x)
    assert result["settings"]["A"] == pytest.approx(expected_x, abs=1e-6)
    assert result["probability"] == pytest.approx(expected_probability, abs=1e-8)
    assert result["desirability"] == pytest.approx(
        _reference_desirability("target", expected_probability,
                                lower, target, upper, weight), abs=1e-8)
    assert result["desirability"] == pytest.approx(1.0, abs=1e-8)
    assert result["target_reached"] is True
    assert result["global_optimum_proven"] is False
    assert result["settings"] == repeated["settings"]
    _assert_probability_matches_model_row(analysis, result)


def test_binary_maximize_desirability_escapes_zero_platform(binary_quadratic):
    _, base = binary_quadratic
    analysis = _binary_with_eta(base, -2.29, 54.0, -100.0)
    lower, target = 0.90, 0.95
    for coded_a in (-1.0, 0.0, 1.0):
        probability = _reference_expit(5 - 100 * (coded_a - 0.27) ** 2)
        assert probability < lower
        assert _reference_desirability(
            "maximize", probability, lower, target, None, 1.0) == 0.0

    result = optimize_binary_rsm(
        analysis, goal="maximize", criterion="desirability",
        lower=lower, target=target)
    target_eta = math.log(target / (1 - target))
    radius = math.sqrt((5 - target_eta) / 100)
    assert 0.27 - radius - 1e-6 <= result["settings"]["A"] <= 0.27 + radius + 1e-6
    assert result["probability"] >= target - 1e-8
    assert result["desirability"] == pytest.approx(1.0, abs=1e-8)
    assert result["target_reached"] is True
    assert result["global_optimum_proven"] is False
    _assert_probability_matches_model_row(analysis, result)


def test_binary_minimize_desirability_escapes_zero_platform(binary_quadratic):
    _, base = binary_quadratic
    analysis = _binary_with_eta(base, 2.29, -54.0, 100.0)
    target, upper = 0.05, 0.10
    for coded_a in (-1.0, 0.0, 1.0):
        probability = _reference_expit(-5 + 100 * (coded_a - 0.27) ** 2)
        assert probability > upper
        assert _reference_desirability(
            "minimize", probability, None, target, upper, 1.0) == 0.0

    result = optimize_binary_rsm(
        analysis, goal="minimize", criterion="desirability",
        target=target, upper=upper)
    target_eta = math.log(target / (1 - target))
    radius = math.sqrt((5 + target_eta) / 100)
    assert 0.27 - radius - 1e-6 <= result["settings"]["A"] <= 0.27 + radius + 1e-6
    assert result["probability"] <= target + 1e-8
    assert result["desirability"] == pytest.approx(1.0, abs=1e-8)
    assert result["target_reached"] is True
    assert result["global_optimum_proven"] is False
    _assert_probability_matches_model_row(analysis, result)


def test_binary_zero_platform_auxiliary_search_preserves_weight_and_status(
        binary_quadratic):
    _, base = binary_quadratic
    peak = math.log(0.93 / (1 - 0.93))
    analysis = _binary_with_eta(base, peak - 100 * 0.27 ** 2, 54.0, -100.0)
    lower, target = 0.90, 0.95
    for weight in (0.5, 2.0):
        result = optimize_binary_rsm(
            analysis, goal="maximize", criterion="desirability",
            lower=lower, target=target, weight=weight)
        assert result["settings"]["A"] == pytest.approx(0.27, abs=1e-5)
        assert result["probability"] == pytest.approx(0.93, abs=1e-8)
        assert result["desirability"] == pytest.approx(0.6 ** weight, abs=1e-8)
        assert result["solver_converged"] is True
        assert result["target_reached"] is False
        _assert_probability_matches_model_row(analysis, result)


def test_binary_desirability_zero_platform_reports_budget_exhaustion(
        binary_quadratic, monkeypatch):
    import doe_optimize

    _, base = binary_quadratic
    analysis = _binary_with_eta(base, 0.0, 20.0, 0.0)
    monkeypatch.setattr(doe_optimize, "_BINARY_EVALUATIONS_PER_START", 1)

    def exhaust_budget(objective, initial, **_kwargs):
        objective(np.asarray(initial, dtype=float))
        objective(np.asarray(initial, dtype=float))

    monkeypatch.setattr(doe_optimize, "minimize", exhaust_budget)
    result = optimize_binary_rsm(
        analysis, goal="target", criterion="desirability",
        lower=0.90, target=0.95, upper=0.99)
    assert result["candidate_found"] is True
    assert result["desirability"] == 0.0
    assert result["target_reached"] is False
    assert result["solver_converged"] is False
    assert result["success"] is False
    assert any("起点评价达到 1 次上限" in reason
               for reason in result["termination_counts"])
    assert "起点评价达到 1 次上限" in result["termination_reason"]
    _assert_probability_matches_model_row(analysis, result)


def test_binary_desirability_zero_platform_honors_cancellation(
        binary_quadratic, monkeypatch):
    import doe_optimize

    _, base = binary_quadratic
    analysis = _binary_with_eta(base, 0.0, 20.0, 0.0)
    cancel = Event()

    def cancel_in_auxiliary(objective, initial, **_kwargs):
        cancel.set()
        objective(np.asarray(initial, dtype=float))

    monkeypatch.setattr(doe_optimize, "minimize", cancel_in_auxiliary)
    with pytest.raises(InterruptedError, match="已取消"):
        optimize_binary_rsm(
            analysis, goal="target", criterion="desirability",
            lower=0.90, target=0.95, upper=0.99, cancel=cancel)


def test_binary_desirability_zero_platform_reports_unreachable_target(binary_quadratic):
    _, base = binary_quadratic
    analysis = _binary_with_eta(base, 0.2, 1.0, -1.0)
    maximum_probability = _reference_expit(0.45)
    assert maximum_probability < 0.80

    result = optimize_binary_rsm(
        analysis, goal="maximize", criterion="desirability",
        lower=0.80, target=0.90)
    assert result["settings"]["A"] == pytest.approx(0.0)
    assert result["probability"] == pytest.approx(_reference_expit(0.2), abs=1e-8)
    assert result["desirability"] == 0.0
    assert result["target_reached"] is False
    assert "不证明目标在域内不可达" in result["target_status"]
    assert result["solver_converged"] is True
    assert result["global_optimum_proven"] is False
    _assert_probability_matches_model_row(analysis, result)


def test_binary_optimizer_uses_physical_bounds_and_rejects_invalid_start(binary_quadratic):
    _, analysis = binary_quadratic
    result = optimize_binary_rsm(
        analysis, goal="maximize", criterion="probability", lower=0.4, target=0.6,
        bounds={"A": (0, 1), "B": (-0.25, 0.25), "C": (-1, 1)},
        start={"A": 0.25, "B": 0.1},
    )
    assert 0 <= result["settings"]["A"] <= 1
    assert result["settings"]["A"] == pytest.approx(0.5, abs=2e-5)
    assert result["coded_settings"]["A"] == pytest.approx(result["settings"]["A"])

    with pytest.raises(ValueError, match="起始值超出搜索范围"):
        optimize_binary_rsm(
            analysis, goal="maximize", criterion="probability", lower=0.4, target=0.6,
            bounds={"A": (0, 1)}, start={"A": -0.1})


def test_binary_optimizer_enumerates_allowed_category_levels(binary_categorical):
    _, analysis = binary_categorical
    args = dict(
        goal="maximize", criterion="probability", lower=0.0, target=0.8,
        bounds={"X1": (0, 0), "X2": (0, 0)},
    )
    result = optimize_binary_rsm(analysis, **args)
    assert result["settings"]["C"] == "高"
    assert result["category_combinations_evaluated"] == 2
    assert result["global_optimum_proven"] is True
    limited = optimize_binary_rsm(analysis, categories={"C": ["低"]}, **args)
    assert limited["settings"]["C"] == "低"
    assert limited["category_combinations_evaluated"] == 1


def test_binary_optimizer_rejects_category_search_over_budget(binary_categorical, monkeypatch):
    import doe_optimize

    _, analysis = binary_categorical
    monkeypatch.setattr(doe_optimize, "_BINARY_CATEGORY_COMBINATION_LIMIT", 1)
    with pytest.raises(ValueError, match="超过搜索预算"):
        optimize_binary_rsm(
            analysis, goal="maximize", criterion="probability", lower=0, target=0.8)


def test_binary_optimizer_keeps_best_point_when_start_budget_expires(
        binary_quadratic, monkeypatch):
    import doe_optimize

    _, analysis = binary_quadratic
    monkeypatch.setattr(doe_optimize, "_BINARY_EVALUATIONS_PER_START", 1)

    def spend_budget(objective, initial, **_kwargs):
        objective(np.asarray([0.5, 0.0, 0.0]))
        objective(np.asarray([0.0, 0.0, 0.0]))

    monkeypatch.setattr(doe_optimize, "minimize", spend_budget)
    result = optimize_binary_rsm(
        analysis, goal="maximize", criterion="probability", lower=0.0, target=0.6)
    assert result["settings"]["A"] == pytest.approx(0.5)
    assert result["probability"] == pytest.approx(
        REFERENCE["direct_extrema"]["maximum"]["probability"])
    assert result["candidate_found"] is True
    assert result["success"] is False
    assert result["status"] == "candidate_with_unconverged_starts"
    assert result["solver_converged"] is False


def test_binary_optimizer_ties_and_extreme_logits_are_deterministic(binary_quadratic):
    _, analysis = binary_quadratic
    flat = dict(analysis)
    flat["coefficients_array"] = np.zeros_like(analysis["coefficients_array"])
    args = dict(goal="maximize", criterion="probability", lower=0.0, target=0.8)
    first = optimize_binary_rsm(flat, **args)
    second = optimize_binary_rsm(flat, **args)
    assert first["settings"] == second["settings"]
    assert first["coded_settings"] == second["coded_settings"]
    assert first["settings"] == {"A": 0.0, "B": 0.0, "C": 0.0}

    for intercept, expected in ((-1000.0, 0.0), (1000.0, 1.0)):
        extreme = dict(flat)
        extreme["coefficients_array"] = np.zeros_like(flat["coefficients_array"])
        extreme["coefficients_array"][0] = intercept
        result = optimize_binary_rsm(extreme, **args)
        assert result["probability"] == expected
        assert np.isfinite(result["desirability"])


@pytest.mark.parametrize("kwargs,match", [
    ({"goal": "maximize", "criterion": "probability", "lower": 0.7, "target": 0.6}, "顺序"),
    ({"goal": "minimize", "criterion": "probability", "target": 0.4, "upper": 0.4}, "顺序"),
    ({"goal": "target", "criterion": "probability", "lower": 0.3,
      "target": 0.6, "upper": 0.5}, "顺序"),
    ({"goal": "maximize", "criterion": "desirability", "lower": 0, "target": 0.5,
      "weight": 0.05}, "weight"),
    ({"goal": "maximize", "criterion": "other", "lower": 0, "target": 0.5}, "criterion"),
])
def test_binary_optimizer_rejects_invalid_goals(binary_quadratic, kwargs, match):
    _, analysis = binary_quadratic
    with pytest.raises(ValueError, match=match):
        optimize_binary_rsm(analysis, **kwargs)


def test_binary_optimizer_rejects_malformed_fit_matrix(binary_quadratic):
    _, analysis = binary_quadratic
    malformed = dict(analysis)
    malformed["matrix"] = analysis["matrix"][:, :-1]
    with pytest.raises(ValueError, match="矩阵"):
        optimize_binary_rsm(
            malformed, goal="maximize", criterion="probability", lower=0, target=0.5)
    inconsistent = dict(analysis)
    inconsistent["matrix"] = analysis["matrix"].copy()
    inconsistent["matrix"][0, 0] += 0.1
    with pytest.raises(ValueError, match="拟合矩阵不一致"):
        optimize_binary_rsm(
            inconsistent, goal="maximize", criterion="probability", lower=0, target=0.5)


@pytest.mark.parametrize("blocks", [
    lambda count: [1, 2] * (count // 2) + ([1] if count % 2 else []),
    lambda count: [1] + [None] * (count - 1),
])
def test_binary_optimizer_rejects_multiple_or_incomplete_blocks(binary_quadratic, blocks):
    _, analysis = binary_quadratic
    blocked = dict(analysis)
    run_blocks = blocks(len(analysis["design"].runs))
    blocked["design"] = SimpleNamespace(
        spec=analysis["design"].spec,
        runs=tuple(SimpleNamespace(block=block) for block in run_blocks),
    )
    with pytest.raises(ValueError, match="区组"):
        optimize_binary_rsm(
            blocked, goal="maximize", criterion="probability", lower=0, target=0.5)


def test_binary_optimizer_rejects_bounds_outside_declared_domain(binary_quadratic):
    _, analysis = binary_quadratic
    with pytest.raises(ValueError, match="超出 DOE 声明域"):
        optimize_binary_rsm(
            analysis, goal="maximize", criterion="probability", lower=0, target=0.5,
            bounds={"A": (-1.1, 1)},
        )


def test_binary_optimizer_honors_pre_cancelled_event(binary_quadratic):
    _, analysis = binary_quadratic
    cancel = Event()
    cancel.set()
    with pytest.raises(InterruptedError, match="已取消"):
        optimize_binary_rsm(
            analysis, goal="maximize", criterion="probability", lower=0, target=0.5,
            cancel=cancel,
        )


def test_binary_optimizer_honors_cancellation_during_search(binary_quadratic, monkeypatch):
    import doe_optimize

    _, analysis = binary_quadratic
    cancel = Event()

    def cancel_in_solver(objective, initial, **_kwargs):
        cancel.set()
        objective(initial)

    monkeypatch.setattr(doe_optimize, "minimize", cancel_in_solver)
    with pytest.raises(InterruptedError, match="已取消"):
        optimize_binary_rsm(
            analysis, goal="maximize", criterion="probability", lower=0, target=0.5,
            cancel=cancel,
        )


def test_binary_optimizer_does_not_modify_source_responses(binary_quadratic):
    frame, analysis = binary_quadratic
    before = frame[["响应_Events", "响应_Trials"]].copy(deep=True)
    optimize_binary_rsm(
        analysis, goal="maximize", criterion="probability", lower=0.0, target=0.6,
        bounds={name: (0, 0) for name in "ABC"},
    )
    assert frame[["响应_Events", "响应_Trials"]].equals(before)
