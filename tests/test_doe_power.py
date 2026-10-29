import json
from itertools import product
from pathlib import Path

import numpy as np
import pytest

from doe_power import calculate_power


REFERENCE = json.loads(
    (Path(__file__).parent / "fixtures" / "doe_h_reference" / "reference.json")
    .read_text(encoding="utf-8")
)


def calculate(case, **mode):
    return calculate_power(
        case["design_points"], case["factor_names"], case["tested_factor"],
        case["effect_high_minus_low"], case["sigma"], case["alpha"], **mode,
    )


@pytest.mark.parametrize("case_name", [
    "two_level", "regular_fractional", "pb", "general_full_factorial",
])
def test_fixed_replicates_match_independent_power_reference(case_name):
    case = REFERENCE["power"][case_name]
    expected = case["fixed_replicates"]

    result = calculate(case, fixed_replicates=expected["replicates"])

    assert result["total_runs"] == expected["total_runs"]
    assert result["replicates"] == expected["replicates"]
    assert result["df"] == {
        "model": expected["df_model"],
        "test": expected["df_test"],
        "error": expected["df_error"],
    }
    assert result["power"] == pytest.approx(expected["power"], rel=1e-12)
    assert result["method"] == "非中心 F 检验（主效应 1 df）"
    assert result["assumptions"]


@pytest.mark.parametrize("case_name", [
    "two_level", "regular_fractional", "pb", "general_full_factorial",
])
def test_target_power_finds_minimum_integer_repeats(case_name):
    case = REFERENCE["power"][case_name]
    expected = case["minimum_replicates"]

    result = calculate(case, target_power=case["target_power"])

    assert result["replicates"] == expected["replicates"]
    assert result["total_runs"] == expected["total_runs"] <= case["run_limit"]
    assert result["df"] == {
        "model": expected["df_model"],
        "test": expected["df_test"],
        "error": expected["df_error"],
    }
    assert result["power"] == pytest.approx(expected["power"], rel=1e-12)
    assert result["power"] >= case["target_power"]

    previous_repeats = expected["replicates"] - 1
    if previous_repeats:
        previous = calculate(case, fixed_replicates=previous_repeats)
        assert previous["power"] == pytest.approx(
            case["previous_replicates_power"], rel=1e-12
        )
        assert previous["power"] < case["target_power"]
    else:
        assert case["previous_replicates_power"] is None


def test_fixed_replicate_power_is_symmetric_for_signed_effect():
    case = REFERENCE["power"]["two_level"]
    replicates = case["fixed_replicates"]["replicates"]
    positive = calculate_power(
        case["design_points"], case["factor_names"], case["tested_factor"],
        2, case["sigma"], case["alpha"], fixed_replicates=replicates,
    )
    negative = calculate_power(
        case["design_points"], case["factor_names"], case["tested_factor"],
        -2, case["sigma"], case["alpha"], fixed_replicates=replicates,
    )

    assert positive["power"] == pytest.approx(
        case["fixed_replicates"]["power"], rel=1e-12
    )
    assert negative["power"] == pytest.approx(positive["power"], rel=1e-14)
    assert negative["df"] == positive["df"]
    assert negative["total_runs"] == positive["total_runs"]


def test_target_power_minimum_repeats_is_symmetric_for_signed_effect():
    case = REFERENCE["power"]["two_level"]
    target = case["target_power"]
    positive = calculate_power(
        case["design_points"], case["factor_names"], case["tested_factor"],
        2, case["sigma"], case["alpha"], target_power=target,
    )
    negative = calculate_power(
        case["design_points"], case["factor_names"], case["tested_factor"],
        -2, case["sigma"], case["alpha"], target_power=target,
    )

    assert negative["replicates"] == positive["replicates"]
    assert negative["total_runs"] == positive["total_runs"]
    assert negative["df"] == positive["df"]
    assert negative["power"] == pytest.approx(positive["power"], rel=1e-14)
    assert negative["replicates"] == case["minimum_replicates"]["replicates"]
    assert negative["power"] == pytest.approx(
        case["minimum_replicates"]["power"], rel=1e-12
    )
    assert negative["power"] >= target
    previous = calculate_power(
        case["design_points"], case["factor_names"], case["tested_factor"],
        -2, case["sigma"], case["alpha"],
        fixed_replicates=negative["replicates"] - 1,
    )
    assert previous["power"] < target


def test_rejects_rank_deficient_and_zero_error_df_designs():
    edges = REFERENCE["power_edges"]
    nonestimable = np.asarray(edges["nonestimable"]["columns"], dtype=float)
    with pytest.raises(ValueError, match="不满秩"):
        calculate_power(nonestimable[:, 1:], edges["nonestimable"]["duplicate_factors"],
                        "A", 2, 1, 0.05, fixed_replicates=2)

    with pytest.raises(ValueError, match="误差自由度"):
        calculate_power([[-1], [1]], ["A"], "A", 2, 1, 0.05,
                        fixed_replicates=1)


def test_rejects_unattainable_target_within_fixture_run_limit():
    edge = REFERENCE["power_edges"]["run_limit_unattainable"]
    points = np.asarray(list(product((-1, 1), repeat=10)), dtype=float)

    with pytest.raises(ValueError, match="10,000"):
        calculate_power(
            points, [f"F{i}" for i in range(10)], "F0", edge["effect"],
            edge["sigma"], edge["alpha"], target_power=edge["target_power"],
        )


def test_accepts_exact_run_limit_and_rejects_one_above():
    points = [[-1, -1], [1, -1], [-1, 1], [1, 1]]
    result = calculate_power(points, ["A", "B"], "A", 2, 1, 0.05,
                             fixed_replicates=2500)
    assert result["total_runs"] == 10_000
    with pytest.raises(ValueError, match="10,000"):
        calculate_power(points, ["A", "B"], "A", 2, 1, 0.05,
                        fixed_replicates=2501)


@pytest.mark.parametrize("mode", [
    {},
    {"fixed_replicates": 2, "target_power": 0.8},
    {"fixed_replicates": 0},
    {"fixed_replicates": 1.5},
    {"fixed_replicates": True},
    {"target_power": 0},
    {"target_power": 1},
])
def test_rejects_invalid_replicate_modes(mode):
    with pytest.raises(ValueError):
        calculate_power([[-1], [1]], ["A"], "A", 2, 1, 0.05, **mode)


@pytest.mark.parametrize("args", [
    ([[0], [1]], ["A"], "A", 2, 1, 0.05),
    ([[-1], [1]], ["A", "A"], "A", 2, 1, 0.05),
    ([[-1], [1]], ["A"], "B", 2, 1, 0.05),
    ([[-1], [1]], ["A"], "A", 2, 0, 0.05),
    ([[-1], [1]], ["A"], "A", 0, 1, 0.05),
    ([[-1], [1]], ["A"], "A", 2, 1, 0),
    ([[-1], [1]], ["A"], "A", float("nan"), 1, 0.05),
    ([[-1], [1]], ["A"], "A", float("inf"), 1, 0.05),
    ([[-1], [1]], ["A"], "A", "invalid", 1, 0.05),
])
def test_rejects_invalid_design_and_scalar_boundaries(args):
    with pytest.raises(ValueError):
        calculate_power(*args, fixed_replicates=2)
