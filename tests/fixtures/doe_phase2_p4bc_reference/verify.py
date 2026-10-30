"""Verify frozen P4BC reference data independently; imports no project code."""
from __future__ import annotations

from collections import Counter, defaultdict
from fractions import Fraction
from hashlib import sha256
from itertools import combinations, product
import json
import math
from pathlib import Path


HERE = Path(__file__).resolve().parent
CATALOGUE_URL = (
    "https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-"
    "modeling/doe/supporting-topics/taguchi-designs/catalogue-of-taguchi-designs/"
)
SN_URL = (
    "https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-"
    "modeling/doe/how-to/taguchi/analyze-taguchi-design/methods-and-formulas/"
    "methods-and-formulas/"
)
EXPECTED_ARRAYS = {
    "L8(4^1 2^4)": ([4, 2, 2, 2, 2], list(range(1, 6)), [
        [1, 1, 1, 1, 1], [1, 2, 2, 2, 2], [2, 1, 1, 2, 2], [2, 2, 2, 1, 1],
        [3, 1, 2, 1, 2], [3, 2, 1, 2, 1], [4, 1, 2, 2, 1], [4, 2, 1, 1, 2],
    ]),
    "L16(4^1 2^12)": ([4] + [2] * 12, list(range(1, 14)), [
        [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
        [1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 2],
        [1, 2, 2, 2, 2, 1, 1, 1, 1, 2, 2, 2, 2],
        [1, 2, 2, 2, 2, 2, 2, 2, 2, 1, 1, 1, 1],
        [2, 1, 1, 2, 2, 1, 1, 2, 2, 1, 1, 2, 2],
        [2, 1, 1, 2, 2, 2, 2, 1, 1, 2, 2, 1, 1],
        [2, 2, 2, 1, 1, 1, 1, 2, 2, 2, 2, 1, 1],
        [2, 2, 2, 1, 1, 2, 2, 1, 1, 1, 1, 2, 2],
        [3, 1, 2, 1, 2, 1, 2, 1, 2, 1, 2, 1, 2],
        [3, 1, 2, 1, 2, 2, 1, 2, 1, 2, 1, 2, 1],
        [3, 2, 1, 2, 1, 1, 2, 1, 2, 2, 1, 2, 1],
        [3, 2, 1, 2, 1, 2, 1, 2, 1, 1, 2, 1, 2],
        [4, 1, 2, 2, 1, 1, 2, 2, 1, 1, 2, 2, 1],
        [4, 1, 2, 2, 1, 2, 1, 1, 2, 2, 1, 1, 2],
        [4, 2, 1, 1, 2, 1, 2, 2, 1, 2, 1, 1, 2],
        [4, 2, 1, 1, 2, 2, 1, 1, 2, 1, 2, 2, 1],
    ]),
    "L18(2^1 3^7)": ([2] + [3] * 7, [1, 2, 3, 4, 5, 6, 7, 9], [
        [1, 1, 1, 1, 1, 1, 1, 1], [1, 1, 2, 2, 2, 2, 2, 2],
        [1, 1, 3, 3, 3, 3, 3, 3], [1, 2, 1, 1, 2, 2, 3, 2],
        [1, 2, 2, 2, 3, 3, 1, 3], [1, 2, 3, 3, 1, 1, 2, 1],
        [1, 3, 1, 2, 1, 3, 2, 3], [1, 3, 2, 3, 2, 1, 3, 1],
        [1, 3, 3, 1, 3, 2, 1, 2], [2, 1, 1, 3, 3, 2, 2, 1],
        [2, 1, 2, 1, 1, 3, 3, 2], [2, 1, 3, 2, 2, 1, 1, 3],
        [2, 2, 1, 2, 3, 1, 3, 2], [2, 2, 2, 3, 1, 2, 1, 3],
        [2, 2, 3, 1, 2, 3, 2, 1], [2, 3, 1, 3, 2, 3, 1, 2],
        [2, 3, 2, 1, 3, 1, 2, 3], [2, 3, 3, 2, 1, 2, 3, 1],
    ]),
}
EXPECTED_UNBALANCED_L18 = [[3, 8], [4, 8], [5, 8], [6, 8], [7, 8]]
MODEL_TERMS = ["x1", "x2", "x3", "x1*x2", "x1*x3", "x2*x3",
               "x1*p1", "x2*p1", "x3*p1", "x1*p2", "x2*p2", "x3*p2",
               "x1*amount", "x2*amount", "x3*amount"]
MODEL_BETA = [10, 20, 30, 2, 3, 4, 1, 2, 3, 4, 5, 6, 7, 8, 9]


def close(actual: float, expected: float, tolerance: float = 2e-10) -> None:
    assert math.isclose(float(actual), float(expected), rel_tol=tolerance,
                        abs_tol=tolerance), (actual, expected)


def canonical_matrix_hash(array_id: str, levels: list[int], matrix: list[list[int]]) -> str:
    raw = json.dumps({"array_id": array_id, "levels": levels, "matrix": matrix},
                     sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return sha256(raw).hexdigest()


def check_arrays(reference: dict) -> None:
    arrays = reference["taguchi_arrays"]
    assert [item["array_id"] for item in arrays] == list(EXPECTED_ARRAYS)
    for item in arrays:
        expected_levels, expected_headers, expected_matrix = EXPECTED_ARRAYS[item["array_id"]]
        assert item["levels"] == expected_levels
        assert item["column_headers"] == expected_headers
        assert item["runs"] == len(expected_matrix)
        assert item["matrix"] == expected_matrix  # exact, row-by-row comparison
        assert all(len(row) == len(expected_levels) for row in item["matrix"])
        assert all(1 <= value <= expected_levels[col]
                   for row in item["matrix"] for col, value in enumerate(row))
        expected_column_counts = []
        for col, levels in enumerate(expected_levels):
            counts = [sum(row[col] == level for row in expected_matrix)
                      for level in range(1, levels + 1)]
            expected_column_counts.append({"position": col + 1,
                                           "official_header": expected_headers[col],
                                           "level_counts": counts,
                                           "balanced": len(set(counts)) == 1})
        assert item["column_counts"] == expected_column_counts
        pairs, unbalanced = [], []
        for first, second in combinations(range(len(expected_levels)), 2):
            counts = [[sum(row[first] == a and row[second] == b for row in expected_matrix)
                       for b in range(1, expected_levels[second] + 1)]
                      for a in range(1, expected_levels[first] + 1)]
            balanced = len({count for row in counts for count in row}) == 1
            pairs.append({"positions": [first + 1, second + 1],
                          "official_headers": [expected_headers[first], expected_headers[second]],
                          "counts": counts, "balanced": balanced})
            if not balanced:
                unbalanced.append([first + 1, second + 1])
        assert item["column_pairs"] == pairs
        assert item["unbalanced_position_pairs"] == unbalanced
        assert item["all_columns_marginally_balanced"] is all(
            column["balanced"] for column in expected_column_counts)
        assert item["all_column_pairs_balanced"] is (not unbalanced)
        if item["array_id"] in ("L8(4^1 2^4)", "L16(4^1 2^12)"):
            assert item["all_columns_marginally_balanced"]
            assert item["all_column_pairs_balanced"]
        assert item["matrix_sha256"] == canonical_matrix_hash(
            item["array_id"], item["levels"], item["matrix"])
    l18 = arrays[2]
    assert l18["column_headers"] == [1, 2, 3, 4, 5, 6, 7, 9]
    assert l18["unbalanced_position_pairs"] == EXPECTED_UNBALANCED_L18
    assert [[*pair["positions"]] for pair in l18["column_pairs"] if not pair["balanced"]] == EXPECTED_UNBALANCED_L18
    assert l18["column_pairs"][-1]["official_headers"] == [7, 9]

    examples = reference["level_mapping_examples"]
    assert examples["numeric"]["decoded"] == [examples["numeric"]["actual_levels"][1]]
    assert examples["text"]["decoded"] == [examples["text"]["actual_levels"][1]]
    for example in examples.values():
        assert len(example["codes"]) == len(example["actual_levels"])


def sample_variance(values: list[float]) -> float:
    mean = sum(values) / len(values)
    return sum((value - mean) ** 2 for value in values) / (len(values) - 1)


def sn_smaller(values: list[float]) -> float:
    return -10 * math.log10(sum(value * value for value in values) / len(values))


def sn_larger(values: list[float]) -> float:
    if any(value == 0 for value in values):
        raise ValueError("zero response")
    return -10 * math.log10(sum(1 / (value * value) for value in values) / len(values))


def check_sn(reference: dict) -> None:
    section = reference["static_signal_to_noise"]
    sample = section["sample_case"]
    values = sample["responses"]
    mean = sum(values) / len(values)
    variance = sample_variance(values)
    assert sample["n"] == len(values)
    close(sample["mean"], mean)
    close(sample["sample_variance_ddof_1"], variance)
    close(sample["sample_sd_ddof_1"], math.sqrt(variance))
    expected = {
        "smaller": sn_smaller(values),
        "larger": sn_larger(values),
        "nominal_I": 10 * math.log10(mean * mean / variance),
        "nominal_II": -10 * math.log10(variance),
        "adjusted_nominal_I": 10 * math.log10(
            (mean * mean - variance / len(values)) / variance),
    }
    for name, result in expected.items():
        close(sample["sn"][name], result)
    boundaries = section["zero_variance_boundaries"]
    constant = boundaries["responses"]
    assert sample_variance(constant) == 0
    assert boundaries["sample_variance_ddof_1"] == 0
    assert boundaries["smaller"]["status"] == "legal"
    assert boundaries["larger"]["status"] == "legal"
    close(boundaries["smaller"]["sn"], sn_smaller(constant))
    close(boundaries["larger"]["sn"], sn_larger(constant))
    for function in (lambda: 10 * math.log10(sum(constant) ** 2 / sample_variance(constant)),
                     lambda: -10 * math.log10(sample_variance(constant))):
        try:
            function()
        except (ValueError, ZeroDivisionError):
            pass
        else:
            raise AssertionError("nominal S/N must reject zero sample variance")
    assert boundaries["nominal_I_and_II"]["status"] == "rejected"
    assert boundaries["nominal_I_and_II"]["cases"] == {
        "nominal_I": "rejected_zero_sample_variance",
        "nominal_II": "rejected_zero_sample_variance",
    }
    assert boundaries["adjusted_nominal_I"] == {
        "status": "rejected", "case": "rejected_zero_sample_variance"}
    try:
        sn_larger(boundaries["larger_with_zero_response"]["responses"])
    except ValueError:
        pass
    else:
        raise AssertionError("larger-is-better must reject zero response")
    assert boundaries["larger_with_zero_response"]["status"] == "rejected_zero_response"
    negative = boundaries["larger_with_negative_responses"]
    assert negative["status"] == "legal"
    close(negative["sn"], sn_larger(negative["responses"]))


def check_noise_case(reference: dict) -> None:
    case = reference["noise_factor_case"]
    rows = case["records"]
    assert len(rows) == 48 == case["expected"]["runs"]
    assert len({row["run_id"] for row in rows}) == 48
    cells = defaultdict(list)
    controls = defaultdict(list)
    for row in rows:
        a, b = row["control_levels"]["A"], row["control_levels"]["B"]
        n1, n2 = row["noise_levels"]["N2"], row["noise_levels"]["N3"]
        assert row["control_id"] == f"CTRL-{a}{b}"
        assert row["noise_condition_id"] == f"NOISE-{(n1 - 1) * 3 + n2:02d}"
        assert row["condition_id"] == f"{row['control_id']}|{row['noise_condition_id']}"
        assert row["replicate_id"] == f"REP-{row['replicate']}"
        close(row["response"], 10 + 2*a + 3*b + 1.5*n1 + 0.75*n2 + 0.5*(row["replicate"] - 1.5))
        cells[(row["control_id"], row["noise_condition_id"])].append(row)
        controls[row["control_id"]].append(row["response"])
    assert len({key[1] for key in cells}) == 6
    assert len(cells) == 4 * 6 == case["expected"]["control_noise_condition_groups"]
    assert all(len(group) == 2 and {row["replicate"] for row in group} == {1, 2}
               for group in cells.values())
    assert all(len(values) == 12 for values in controls.values())
    frequencies = {
        "run_id": dict(sorted(Counter(row["run_id"] for row in rows).items())),
        "replicate_id": dict(sorted(Counter(row["replicate_id"] for row in rows).items())),
        "noise_condition_id": dict(sorted(Counter(row["noise_condition_id"] for row in rows).items())),
        "condition_id": dict(sorted(Counter(row["condition_id"] for row in rows).items())),
        "control_id": dict(sorted(Counter(row["control_id"] for row in rows).items())),
    }
    assert case["identity_frequencies"] == frequencies
    assert set(frequencies["run_id"].values()) == {1}
    assert frequencies["replicate_id"] == {"REP-1": 24, "REP-2": 24}
    assert set(frequencies["noise_condition_id"].values()) == {8}
    assert set(frequencies["condition_id"].values()) == {2}
    assert set(frequencies["control_id"].values()) == {12}

    condition_stats = {item["condition_id"]: item for item in case["condition_statistics"]}
    assert set(condition_stats) == {row["condition_id"] for row in rows}
    for key, group in cells.items():
        values = [row["response"] for row in group]
        item = condition_stats[f"{key[0]}|{key[1]}"]
        assert item["responses"] == values
        assert item["n_replicates"] == 2
        close(item["mean"], sum(values) / 2)
        close(item["range"], max(values) - min(values))
        close(item["sample_sd_ddof_1"], math.sqrt(sample_variance(values)))
        close(item["sn_smaller"], sn_smaller(values))
    summary = {item["control_id"]: item for item in case["control_statistics"]}
    assert set(summary) == set(controls)
    for control_id, values in controls.items():
        item = summary[control_id]
        condition_means = [
            sum(row["response"] for row in cells[(control_id, f"NOISE-{index:02d}")]) / 2
            for index in range(1, 7)
        ]
        assert item["responses"] == values
        assert item["observation_count"] == 12
        assert item["noise_condition_count"] == 6
        close(item["noise_condition_mean_range"], max(condition_means) - min(condition_means))
        close(item["mean"], sum(values) / 12)
        close(item["sample_sd_ddof_1"], math.sqrt(sample_variance(values)))
        close(item["sn_smaller"], sn_smaller(values))


def check_two_stage(reference: dict) -> None:
    section = reference["two_stage_selection"]
    combinations_data = section["all_combinations"]
    assert len(combinations_data) == 4
    sn_effects, mean_effects = section["level_effects"]["sn"], section["level_effects"]["mean"]
    sn_intercept, mean_intercept = section["intercepts"]["sn"], section["intercepts"]["mean"]
    sd = section["sd_reference"]
    observed_sd = sd["observed_by_combination"]
    for row in combinations_data:
        a, b = row["levels"]["A"], row["levels"]["B"]
        close(row["predicted_sn"], sn_intercept + sn_effects["A"][str(a)] + sn_effects["B"][str(b)])
        close(row["predicted_mean"], mean_intercept + mean_effects["A"][str(a)] + mean_effects["B"][str(b)])
        key = row["combination_id"]
        close(row["observed_sd"], observed_sd[key])
        predicted_sd = (sd["intercept"] + sd["level_effects"]["A"][str(a)]
                        + sd["level_effects"]["B"][str(b)])
        close(row["additive_predicted_sd"], predicted_sd)
        assert row["observed"] is (key != "A2B2")
        assert row["predicted_sd_status"] == ("unavailable_negative" if predicted_sd < 0 else "available")
        assert row["predicted_sd"] == (None if predicted_sd < 0 else predicted_sd)
    maximum = max(row["predicted_sn"] for row in combinations_data)
    selected = [row["combination_id"] for row in combinations_data if row["predicted_sn"] == maximum]
    assert section["sn_maximum"]["maximum_predicted_sn"] == maximum
    assert section["sn_maximum"]["selected"] == selected == ["A1B1"]
    target_stage = section["robust_then_target"]
    eligible = [row for row in combinations_data if row["predicted_sn"] >= target_stage["sn_threshold"]]
    distance = min(abs(row["predicted_mean"] - target_stage["target"]) for row in eligible)
    all_best = [row["combination_id"] for row in eligible
                if abs(row["predicted_mean"] - target_stage["target"]) == distance]
    assert target_stage["eligible"] == [row["combination_id"] for row in eligible]
    assert target_stage["minimum_absolute_target_distance"] == distance
    assert target_stage["selected_all_ties"] == all_best == ["A1B1", "A2B1"]
    confirmation = section["confirmation"]
    selected_confirmation = next(row for row in combinations_data
                                 if row["combination_id"] == confirmation["settings"])
    close(confirmation["predicted_mean"], selected_confirmation["predicted_mean"])
    close(confirmation["observed_minus_predicted"],
          confirmation["observed_mean"] - confirmation["predicted_mean"])
    assert (abs(confirmation["observed_mean"] - confirmation["target"])
            <= confirmation["target_tolerance"]) is confirmation["meets_target"]
    assert confirmation["writes_back_to_design"] is False
    unreachable = section["unreachable_threshold"]
    assert unreachable["sn_threshold"] > maximum
    assert unreachable["status"] == "rejected_no_candidate_no_fallback"
    budget = section["enumeration_budget"]
    count = math.prod(budget["requested_factor_levels"])
    assert count == budget["requested_combinations"] == 32768
    assert budget["maximum"] == 20000 and count > budget["maximum"]
    assert budget["status"] == "rejected_over_budget"


def frac(value: str | int) -> Fraction:
    return Fraction(value)


def check_mixture(reference: dict) -> None:
    section = reference["mixture_lattice_crosses"]
    lattice = [tuple(map(frac, point)) for point in section["simplex_lattice_degree_2"]]
    expected_lattice = {
        (Fraction(1), Fraction(0), Fraction(0)),
        (Fraction(0), Fraction(1), Fraction(0)),
        (Fraction(0), Fraction(0), Fraction(1)),
        (Fraction(1, 2), Fraction(1, 2), Fraction(0)),
        (Fraction(1, 2), Fraction(0), Fraction(1, 2)),
        (Fraction(0), Fraction(1, 2), Fraction(1, 2)),
    }
    assert len(lattice) == len(set(lattice)) == 6
    assert set(lattice) == expected_lattice
    expected_counts = {"C1": 24, "C2": 18, "C3": 48}
    for name, expected_count in expected_counts.items():
        design = section[name]
        rows = design["runs"]
        assert len(rows) == design["expected_runs"] == expected_count
        assert design["lattice_point_count"] == 6
        assert len({row["run_id"] for row in rows}) == expected_count
        expected_keys = set()
        for lattice_index, point in enumerate(lattice, 1):
            for combo in design["factor_combinations"]:
                process = tuple(sorted((key, combo[key]) for key in design["process_factor_levels"]))
                amount_key = combo.get("amount_level")
                expected_keys.add((f"L{lattice_index}", process, amount_key))
        actual_keys = set()
        for row in rows:
            proportions = tuple(map(frac, row["proportions"]))
            assert proportions in expected_lattice and sum(proportions) == 1
            assert row["total_amount"] > 0
            amounts = tuple(map(frac, row["actual_amounts"]))
            assert amounts == tuple(Fraction(row["total_amount"]) * value for value in proportions)
            process = tuple(sorted(row["process"].items()))
            amount_key = row.get("amount_level")
            actual_keys.add((row["lattice_point_id"], process, amount_key))
            assert row["lattice_point_id"] in {f"L{i}" for i in range(1, 7)}
            assert sum(amounts) == row["total_amount"]
        assert actual_keys == expected_keys
    assert len(section["C1"]["factor_combinations"]) == 4
    assert len(section["C2"]["factor_combinations"]) == 3
    assert len(section["C3"]["factor_combinations"]) == 8


def rank(matrix: list[list[float]]) -> int:
    rows = [[Fraction(str(value)) for value in row] for row in matrix]
    if not rows:
        return 0
    pivot_row = 0
    for col in range(len(rows[0])):
        pivot = next((i for i in range(pivot_row, len(rows)) if rows[i][col]), None)
        if pivot is None:
            continue
        rows[pivot_row], rows[pivot] = rows[pivot], rows[pivot_row]
        for i in range(pivot_row + 1, len(rows)):
            if rows[i][col]:
                ratio = rows[i][col] / rows[pivot_row][col]
                rows[i] = [a - ratio*b for a, b in zip(rows[i], rows[pivot_row])]
        pivot_row += 1
        if pivot_row == len(rows):
            break
    return pivot_row


def solve(matrix: list[list[float]], vector: list[float]) -> list[float]:
    augmented = [list(map(float, row)) + [float(value)] for row, value in zip(matrix, vector)]
    n = len(augmented)
    for col in range(n):
        pivot = max(range(col, n), key=lambda i: abs(augmented[i][col]))
        augmented[col], augmented[pivot] = augmented[pivot], augmented[col]
        divisor = augmented[col][col]
        assert abs(divisor) > 1e-14
        augmented[col] = [value / divisor for value in augmented[col]]
        for row in range(n):
            if row != col:
                scale = augmented[row][col]
                augmented[row] = [a - scale*b for a, b in zip(augmented[row], augmented[col])]
    return [augmented[i][-1] for i in range(n)]


def eigenvalues_symmetric(matrix: list[list[float]]) -> list[float]:
    a = [list(map(float, row)) for row in matrix]
    n = len(a)
    for _ in range(100 * n * n):
        p, q = max(((i, j) for i in range(n) for j in range(i + 1, n)),
                   key=lambda pair: abs(a[pair[0]][pair[1]]))
        off = a[p][q]
        if abs(off) < 1e-13:
            break
        tau = (a[q][q] - a[p][p]) / (2 * off)
        t = math.copysign(1.0, tau) / (abs(tau) + math.sqrt(1 + tau*tau))
        c, s = 1 / math.sqrt(1 + t*t), t / math.sqrt(1 + t*t)
        app, aqq = a[p][p], a[q][q]
        a[p][p], a[q][q], a[p][q], a[q][p] = app-t*off, aqq+t*off, 0.0, 0.0
        for k in range(n):
            if k != p and k != q:
                x, y = a[k][p], a[k][q]
                a[k][p] = a[p][k] = c*x-s*y
                a[k][q] = a[q][k] = s*x+c*y
    return [a[i][i] for i in range(n)]


def model_row(point: list[float], process: tuple[int, int], amount: float) -> list[float]:
    x1, x2, x3 = point
    p1, p2 = process
    return [x1, x2, x3, x1*x2, x1*x3, x2*x3,
            x1*p1, x2*p1, x3*p1, x1*p2, x2*p2, x3*p2,
            x1*amount, x2*amount, x3*amount]


def check_joint_model(reference: dict) -> None:
    model = reference["joint_mixture_process_amount_model"]
    assert model["terms"] == MODEL_TERMS
    assert model["known_beta"] == MODEL_BETA
    matrix, responses = model["matrix"], model["responses"]
    fitted, residuals, rows = model["fitted"], model["residuals"], model["rows"]
    assert len(matrix) == len(responses) == len(fitted) == len(residuals) == len(rows) == 72
    assert all(len(row) == 15 for row in matrix)
    assert len({row["run_id"] for row in rows}) == 72
    expected_grid = set()
    for mix_index in range(1, 7):
        for p1, p2 in product((-1, 1), repeat=2):
            for amount in (-1, 0, 1):
                expected_grid.add((mix_index, p1, p2, amount))
    actual_grid = set()
    points = [tuple(map(float, values)) for values in (
        (1, 0, 0), (0, 1, 0), (0, 0, 1), (.5, .5, 0), (.5, 0, .5), (0, .5, .5))]
    for index, info in enumerate(rows):
        key = (info["mixture_index"], *info["process_codes"], info["amount_code"])
        actual_grid.add(key)
        expected_row = model_row(points[info["mixture_index"] - 1],
                                 tuple(info["process_codes"]), info["amount_code"])
        for actual, wanted in zip(matrix[index], expected_row):
            close(actual, wanted)
        close(info["z1"], [0, -math.sqrt(1.5), 0, math.sqrt(1.5),
                            -math.sqrt(1.5), math.sqrt(1.5)][info["mixture_index"] - 1])
        expected_fit = sum(x*b for x, b in zip(expected_row, MODEL_BETA))
        expected_residual = 0.5 * info["z1"] * info["amount_code"]
        close(fitted[index], expected_fit)
        close(residuals[index], expected_residual)
        close(responses[index], expected_fit + expected_residual)
    assert actual_grid == expected_grid
    assert rank(matrix) == model["expected"]["rank"] == 15
    gram = [[sum(row[i] * row[j] for row in matrix) for j in range(15)] for i in range(15)]
    eigenvalues = eigenvalues_symmetric(gram)
    assert min(eigenvalues) > 0
    close(math.sqrt(max(eigenvalues) / min(eigenvalues)), model["expected"]["condition_number_2"])
    estimated = solve(gram, [sum(row[i]*y for row, y in zip(matrix, responses))
                             for i in range(15)])
    assert len(estimated) == 15
    for value, recorded, wanted in zip(estimated, model["estimated_beta"], MODEL_BETA):
        close(value, wanted)
        close(value, recorded)
    sse = sum(value*value for value in residuals)
    close(sse, model["expected"]["sse"])
    assert model["expected"]["n"] == 72
    assert model["expected"]["p"] == 15
    assert model["expected"]["residual_df"] == 57 == 72 - 15
    dots = [sum(row[j]*residual for row, residual in zip(matrix, residuals))
            for j in range(15)]
    assert len(dots) == len(model["expected"]["residual_dot_each_model_column"]) == 15
    for actual, stored in zip(dots, model["expected"]["residual_dot_each_model_column"]):
        close(actual, 0.0)
        close(actual, stored)
    no_noise = model["no_noise_case"]
    assert no_noise["responses"] == no_noise["fitted"] == model["fitted"]
    assert no_noise["estimated_beta"] == [float(value) for value in MODEL_BETA]
    assert no_noise["residual_df"] == 57
    assert no_noise["sse"] == 0
    prediction = model["expected"]["prediction"]
    point = [float(Fraction(value)) for value in prediction["input"]["proportions"]]
    process = tuple(prediction["input"]["process_codes"])
    row = model_row(point, process, prediction["input"]["amount_code"])
    assert len(row) == 15
    for actual, stored in zip(row, prediction["terms"]):
        close(actual, stored)
    close(sum(value*beta for value, beta in zip(row, MODEL_BETA)), prediction["value"])


def determinant3(matrix: list[list[Fraction]]) -> Fraction:
    a, b, c = matrix
    return a[0]*(b[1]*c[2]-b[2]*c[1]) - a[1]*(b[0]*c[2]-b[2]*c[0]) + a[2]*(b[0]*c[1]-b[1]*c[0])


def check_d_optimal(reference: dict) -> None:
    section = reference["d_optimal_replacement"]
    assert section["model_terms"] == ["x1", "x2", "x3"]
    assert section["selection_seed"] == 23
    locked = section["locked_rows"]
    parent = section["replaceable_parent"]
    assert [row["run_id"] for row in locked] == ["LOCK-A", "LOCK-B"]
    assert all(row["locked"] and row["measured_response"] is not None for row in locked)
    assert parent["locked"] is False and parent["measured_response"] is None
    fixed = [[Fraction(value) for value in row["point"]] for row in locked]
    parent_point = [Fraction(value) for value in parent["point"]]
    assert rank([[float(value) for value in row] for row in fixed + [parent_point]]) == 3
    before_det = determinant3(fixed + [parent_point]) ** 2
    assert Fraction(section["before"]["det_xtx"]) == before_det
    close(section["before"]["logdet_xtx"], math.log(float(before_det)))
    assert section["before"]["run_ids"] == ["LOCK-A", "LOCK-B", "PARENT-003"]
    values = {}
    for item in section["candidates"]:
        candidate = [Fraction(value) for value in item["point"]]
        assert sum(candidate) == 1 and all(0 <= value <= 1 for value in candidate)
        det = determinant3(fixed + [candidate]) ** 2
        assert item["det_xtx"] == (str(det.numerator) if det.denominator == 1
                                   else f"{det.numerator}/{det.denominator}")
        close(item["logdet_xtx"], math.log(float(det)))
        values[item["candidate_run_id"]] = det
    assert len(values) == section["enumerated_subsets"] == 4
    maximum = max(values.values())
    best = [candidate_id for candidate_id, det in values.items() if det == maximum]
    assert best == section["expected"]["unique_best_candidate"] == ["CAND-C"]
    assert section["after"]["selected_candidate_run_id"] == "CAND-C"
    assert section["after"]["global_optimum_proven"] is True
    assert section["after"]["evaluations"] == section["enumerated_subsets"]
    assert section["after"]["stop_reason"] == "exhaustive_candidate_subsets"
    assert section["after"]["run_ids"] == ["LOCK-A", "LOCK-B", "CAND-C"]
    assert section["same_seed_repeat"] == {
        "selection_seed": section["selection_seed"],
        "selected_candidate_run_id": section["after"]["selected_candidate_run_id"],
        "run_ids": section["after"]["run_ids"],
    }
    selected = next(item for item in section["candidates"]
                    if item["candidate_run_id"] == section["after"]["selected_candidate_run_id"])
    after_points = fixed + [[Fraction(value) for value in selected["point"]]]
    assert rank([[float(value) for value in row] for row in after_points]) == section["after"]["rank"] == 3
    assert Fraction(section["after"]["det_xtx"]) == maximum == 1
    assert Fraction(section["after"]["det_xtx"]) >= before_det
    close(section["after"]["logdet_xtx"], 0)
    assert section["protected_measured_rows_before_after"] == locked
    assert section["expected"]["locked_run_ids_preserved"] == [row["run_id"] for row in locked]
    assert section["expected"]["locked_responses_preserved"] == [row["measured_response"] for row in locked]


def check_invalid_boundaries(reference: dict) -> None:
    cases = {item["id"]: item for item in reference["invalid_boundaries"]}
    assert len(cases) == 11
    not_simplex = [Fraction(value) for value in cases["mixture_sum_not_one"]["input"]["proportions"]]
    assert sum(not_simplex) != 1
    for key in ("zero_total", "negative_total"):
        assert cases[key]["input"]["total_amount"] <= 0
        assert cases[key]["expected"] == "reject_nonpositive_total"
    deficient = cases["rank_deficiency"]["input"]["matrix"]
    assert rank(deficient) == 2
    assert cases["rank_deficiency"]["expected"] == "rank_2_reject_rank_3_required"
    for key in ("locked_row_replacement", "measured_row_replacement"):
        row = cases[key]["input"]
        assert row["locked"] or row["measured_response"] is not None
        assert cases[key]["expected"] == "reject_locked_or_measured"
    insufficient = cases["insufficient_candidates"]["input"]
    assert insufficient["candidate_count"] < insufficient["select"]
    budget = cases["selection_over_budget"]["input"]
    assert budget["combination_count"] == 32768 > budget["budget"] == 20000
    threshold = cases["unreachable_sn_threshold"]["input"]
    assert threshold["threshold"] > threshold["maximum_predicted_sn"]
    lineage = cases["lineage_mismatch"]["input"]
    assert lineage["expected_parent"] != lineage["candidate_parent"]
    identity = cases["run_id_mismatch"]["input"]
    assert identity["expected_run_id"] != identity["actual_run_id"]
    assert all(item["expected"] for item in cases.values())


def check_manifest(reference: dict) -> None:
    manifest_path = HERE / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["fixture_id"] == reference["fixture_id"]
    assert manifest["hashes_cover_complete_file_bytes"] is True
    for name in ("README.md", "reference.json", "build_reference.py", "verify.py"):
        payload = (HERE / name).read_bytes()
        recorded = manifest["files"][name]
        assert len(payload) == recorded["bytes"]
        assert sha256(payload).hexdigest() == recorded["sha256"]
    assert manifest["frozen_reference_sha256"] == manifest["files"]["reference.json"]["sha256"]
    assert manifest["generator_sha256"] == manifest["files"]["build_reference.py"]["sha256"]
    assert manifest["verifier_sha256"] == manifest["files"]["verify.py"]["sha256"]
    assert manifest["source"]["official_catalogue_url"] == CATALOGUE_URL
    assert manifest["source"]["official_sn_methods_url"] == SN_URL
    assert manifest["source"]["l18_position_8_official_header"] == 9
    assert manifest["source"]["l18_known_unbalanced_column_positions"] == EXPECTED_UNBALANCED_L18


def main() -> None:
    reference = json.loads((HERE / "reference.json").read_text(encoding="utf-8"))
    assert reference["fixture_id"] == "doe_phase2_p4bc_reference"
    check_arrays(reference)
    check_sn(reference)
    check_noise_case(reference)
    check_two_stage(reference)
    check_mixture(reference)
    check_joint_model(reference)
    check_d_optimal(reference)
    check_invalid_boundaries(reference)
    check_manifest(reference)
    print("P4BC reference verified: 3 arrays; 48 noise runs; 4 controls/6 noise conditions/24 condition groups; 90 mixture runs; 72x15 model; 4 D-opt candidates; 11 invalid boundaries")


if __name__ == "__main__":
    main()
