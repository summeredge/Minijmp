"""独立核验 Taguchi 参考矩阵与手算数值；不导入任何生产 Taguchi 模块。"""
import csv
import hashlib
import json
import math
from itertools import combinations, product
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent / "fixtures" / "doe_taguchi_reference"
MANIFEST = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
CASES = json.loads((ROOT / "cases.json").read_text(encoding="utf-8"))


def matrix_sha(array_id, levels, matrix):
    payload = {"array_id": array_id, "levels": levels, "matrix": matrix}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def read_matrix(case):
    path = ROOT / case["path"]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == case["matrix_sha256"]
    with path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.reader(stream))
    assert rows[0][0] == "standard_order"
    assert [int(row[0]) for row in rows[1:]] == list(range(1, case["runs"] + 1))
    return [[int(value) for value in row[1:]] for row in rows[1:]]


def test_manifest_is_complete_and_self_consistent():
    assert len(MANIFEST["fixtures"]) == 6
    assert len({case["id"] for case in MANIFEST["fixtures"]}) == 6
    for case in MANIFEST["fixtures"]:
        assert matrix_sha(case["array_id"], case["levels"], read_matrix(case)) == case["sha256"]


@pytest.mark.parametrize("case", MANIFEST["fixtures"], ids=lambda case: case["id"])
def test_reference_matrix_balance_and_pairs(case):
    matrix = read_matrix(case)
    levels = case["levels"]
    runs = case["runs"]
    assert len(matrix) == runs and all(len(row) == len(levels) for row in matrix)
    for column, count in enumerate(levels):
        values = [row[column] for row in matrix]
        assert set(values) == set(range(1, count + 1))
        assert {values.count(level) for level in values} == {runs // count}
    documented = {tuple(pair) for pair in
                  MANIFEST["documented_unbalanced_pairs"].get(case["id"], [])}
    observed = set()
    for first, second in combinations(range(len(levels)), 2):
        counts = {}
        for row in matrix:
            counts[(row[first], row[second])] = counts.get(
                (row[first], row[second]), 0) + 1
        expected = runs // (levels[first] * levels[second])
        balanced = (len(counts) == levels[first] * levels[second]
                    and set(counts.values()) == {expected})
        if not balanced:
            observed.add((first + 1, second + 1))
    assert observed == documented


def test_standard_first_rows_are_fixed():
    l4 = read_matrix(next(case for case in MANIFEST["fixtures"] if case["id"] == "l4_2_3"))
    assert l4 == [[1, 1, 1], [1, 2, 2], [2, 1, 2], [2, 2, 1]]
    l18 = read_matrix(next(case for case in MANIFEST["fixtures"] if case["id"] == "l18_2_1_3_7"))
    assert l18[0] == [1] * 8 and l18[9] == [2, 1, 1, 3, 3, 2, 2, 1]


@pytest.mark.parametrize("case", MANIFEST["fixtures"], ids=lambda case: case["id"])
def test_every_column_pair_count_matches_the_fixed_reference(case):
    """逐对列组合频数固定；不只检查均衡/不均衡的布尔结论。"""
    expected = CASES["pair_counts"][case["id"]]
    matrix = read_matrix(case)
    levels = case["levels"]
    actual = {}
    for first, second in combinations(range(len(levels)), 2):
        counts = {}
        for row in matrix:
            key = f"{row[first]}{row[second]}"
            counts[key] = counts.get(key, 0) + 1
        actual[f"{first + 1}-{second + 1}"] = counts
    assert actual == expected
    for first, second in combinations(range(len(levels)), 2):
        counts = expected[f"{first + 1}-{second + 1}"]
        assert len(counts) == levels[first] * levels[second]
        assert sum(counts.values()) == case["runs"]


def _sn(values, kind, adjusted=False):
    n = len(values)
    mean = sum(values) / n
    variance = sum((value - mean) ** 2 for value in values) / (n - 1)
    if kind == "smaller":
        return -10 * math.log10(sum(value ** 2 for value in values) / n)
    if kind == "larger":
        return -10 * math.log10(sum(1 / value ** 2 for value in values) / n)
    if kind == "nominal_ii":
        return -10 * math.log10(variance)
    numerator = mean ** 2 - variance / n if adjusted else mean ** 2
    return 10 * math.log10(numerator / variance)


def test_static_sn_four_formulas_match_hand_calculation():
    case = CASES["sn_two_observations"]
    values = case["response"]
    for kind in ("smaller", "larger", "nominal", "nominal_ii"):
        assert _sn(values, kind) == pytest.approx(case["expected"][kind], abs=1e-12)
    assert _sn(values, "nominal", True) == pytest.approx(
        case["expected"]["nominal_adjusted"], abs=1e-12)


def _fit(signal, response, reference=None):
    n = len(signal)
    if reference is None:
        mean_x, mean_y = sum(signal) / n, sum(response) / n
        slope = (sum((x - mean_x) * (y - mean_y) for x, y in zip(signal, response))
                 / sum((x - mean_x) ** 2 for x in signal))
        intercept = mean_y - slope * mean_x
        df = n - 2
    else:
        ref_x, ref_y = reference
        slope = (sum((x - ref_x) * (y - ref_y) for x, y in zip(signal, response))
                 / sum((x - ref_x) ** 2 for x in signal))
        intercept = ref_y - slope * ref_x
        df = n - 1
    fitted = [intercept + slope * x for x in signal]
    residuals = [y - f for y, f in zip(response, fitted)]
    sse = sum(value ** 2 for value in residuals)
    return {"slope": slope, "intercept": intercept, "sse": sse, "df": df,
            "mse": sse / df, "fitted": fitted, "residuals": residuals}


@pytest.mark.parametrize("name", ["dynamic_free_intercept", "dynamic_reference_point"])
def test_dynamic_regression_and_sn_match_closed_form(name):
    case = CASES[name]
    fit = _fit(case["signal"], case["response"], case["reference"])
    for key in ("slope", "intercept", "sse", "mse"):
        assert fit[key] == pytest.approx(case["expected"][key], abs=1e-12)
    assert fit["df"] == case["expected"]["df"]
    for actual, expected in zip(fit["residuals"], case["expected"]["residuals"]):
        assert actual == pytest.approx(expected, abs=1e-12)
    sn = 10 * math.log10(fit["slope"] ** 2 / fit["mse"])
    assert sn == pytest.approx(case["expected"]["sn"], abs=1e-12)
    if "sn_adjusted" in case["expected"]:
        r = sum((x - case["reference"][0]) ** 2 for x in case["signal"])
        assert r == pytest.approx(case["expected"]["r"])
        assert 10 * math.log10(fit["slope"] ** 2 / fit["mse"] - 1 / r) == pytest.approx(
            case["expected"]["sn_adjusted"], abs=1e-12)


def test_noise_robustness_statistics():
    values = CASES["noise_robustness"]["values"]
    expected = CASES["noise_robustness"]["expected"]
    mean = sum(values) / len(values)
    sd = math.sqrt(sum((value - mean) ** 2 for value in values) / (len(values) - 1))
    assert mean == pytest.approx(expected["mean"])
    assert sd == pytest.approx(expected["sd"])
    assert _sn(values, "smaller") == pytest.approx(expected["sn_smaller"])


def test_additive_prediction_does_not_double_count_grand_mean():
    case = CASES["best_prediction"]
    means = case["combination_means"]
    grand = sum(sum(values) / len(values) for values in means.values()) / len(means)
    assert grand == pytest.approx(case["expected"]["grand_mean"])
    best = case["expected"]["best"]
    predicted = grand + sum(
        values[best[factor] - 1] - grand for factor, values in means.items())
    assert predicted == pytest.approx(case["expected"]["predicted_mean"])
    assert predicted != sum(sum(values) / len(values) for values in means.values())
    assert set(best) == set(means)


def test_target_mean_best_levels_and_prediction():
    case = CASES["best_settings"]["target_mean"]
    means = case["factor_level_means"]
    target = case["target"]
    grand = sum(sum(values) / len(values) for values in means.values()) / len(means)
    assert grand == pytest.approx(case["expected"]["grand_mean"])
    factors = list(means)
    candidates = []
    for indexes in product(*(range(len(means[factor])) for factor in factors)):
        predicted = grand + sum(
            means[factor][index] - grand
            for factor, index in zip(factors, indexes))
        candidates.append((abs(predicted - target), indexes, predicted))
    distance, indexes, predicted = min(candidates)
    assert distance == pytest.approx(0.0, abs=1e-12)
    assert tuple(index + 1 for index in indexes) == (3, 1, 1)
    assert predicted == pytest.approx(19.0, abs=1e-12)

    # The old independent-level pick in the frozen case is a counterexample:
    # it predicts 17 although the complete additive search reaches the target.
    old = case["expected"]["best_levels"]
    old_prediction = grand + sum(
        means[factor][level - 1] - grand
        for factor, level in zip(factors, old))
    assert old == [2, 2, 2]
    assert old_prediction == pytest.approx(17.0)
    assert abs(old_prediction - target) > distance


def test_l4_target_mean_counterexample_closed_form():
    """Independent L4 oracle: 14/26 marginal means produce 8,20,20,32."""
    grand = 20.0
    factor_means = {"A": (14.0, 26.0), "B": (14.0, 26.0)}
    candidates = []
    for first, second in product((0, 1), repeat=2):
        predicted = grand + (factor_means["A"][first] - grand) + (
            factor_means["B"][second] - grand)
        candidates.append(((first + 1, second + 1), predicted))
    assert candidates == [
        ((1, 1), 8.0), ((1, 2), 20.0),
        ((2, 1), 20.0), ((2, 2), 32.0)]
    assert [settings for settings, value in candidates if value == grand] == [
        (1, 2), (2, 1)]


def test_tied_levels_are_listed_and_choice_is_deterministic():
    case = CASES["best_settings"]["tie_break"]
    values = case["factor_level_means"]["A"]
    target = case["target"]
    pick = min(values, key=lambda value: abs(value - target))
    tied = [index + 1 for index, value in enumerate(values) if value == pick]
    assert tied == case["expected"]["tied_levels_A"]
    assert tied[0] == case["expected"]["chosen_level_A"]


def test_confirmation_difference_and_tolerance():
    case = CASES["best_settings"]["confirmation"]
    difference = case["observed"] - case["predicted_mean"]
    assert difference == pytest.approx(case["expected"]["difference"], abs=1e-9)
    meets = abs(case["observed"] - case["target"]) <= case["tolerance"]
    assert meets is case["expected"]["meets_target"]
