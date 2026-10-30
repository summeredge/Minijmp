"""Build the frozen P4BC reference using only this fixture and Python stdlib."""
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
ROBUST_URL = (
    "https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-"
    "modeling/doe/supporting-topics/taguchi-designs/what-is-the-signal-to-noise-ratio/"
)

L8_ID = "L8(4^1 2^4)"
L8_LEVELS = [4, 2, 2, 2, 2]
L8 = [
    [1, 1, 1, 1, 1], [1, 2, 2, 2, 2],
    [2, 1, 1, 2, 2], [2, 2, 2, 1, 1],
    [3, 1, 2, 1, 2], [3, 2, 1, 2, 1],
    [4, 1, 2, 2, 1], [4, 2, 1, 1, 2],
]

# Row-for-row transcription of Minitab's L16 (2^12), (4^1) table.
L16_ID = "L16(4^1 2^12)"
L16_LEVELS = [4] + [2] * 12
L16 = [
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
]

# Independent copy of the frozen L18 CSV values; official headings are 1..7,9.
L18_ID = "L18(2^1 3^7)"
L18_LEVELS = [2] + [3] * 7
L18_HEADERS = [1, 2, 3, 4, 5, 6, 7, 9]
L18 = [
    [1, 1, 1, 1, 1, 1, 1, 1], [1, 1, 2, 2, 2, 2, 2, 2],
    [1, 1, 3, 3, 3, 3, 3, 3], [1, 2, 1, 1, 2, 2, 3, 2],
    [1, 2, 2, 2, 3, 3, 1, 3], [1, 2, 3, 3, 1, 1, 2, 1],
    [1, 3, 1, 2, 1, 3, 2, 3], [1, 3, 2, 3, 2, 1, 3, 1],
    [1, 3, 3, 1, 3, 2, 1, 2], [2, 1, 1, 3, 3, 2, 2, 1],
    [2, 1, 2, 1, 1, 3, 3, 2], [2, 1, 3, 2, 2, 1, 1, 3],
    [2, 2, 1, 2, 3, 1, 3, 2], [2, 2, 2, 3, 1, 2, 1, 3],
    [2, 2, 3, 1, 2, 3, 2, 1], [2, 3, 1, 3, 2, 3, 1, 2],
    [2, 3, 2, 1, 3, 1, 2, 3], [2, 3, 3, 2, 1, 2, 3, 1],
]


def rounded(value: float) -> float:
    return round(float(value), 12)


def fraction_text(value: Fraction) -> str:
    return str(value.numerator) if value.denominator == 1 else f"{value.numerator}/{value.denominator}"


def canonical_matrix_sha(array_id: str, levels: list[int], matrix: list[list[int]]) -> str:
    payload = json.dumps(
        {"array_id": array_id, "levels": levels, "matrix": matrix},
        sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")
    return sha256(payload).hexdigest()


def array_reference(array_id: str, levels: list[int], matrix: list[list[int]],
                    headers: list[int] | None = None) -> dict:
    headers = headers or list(range(1, len(levels) + 1))
    column_counts = []
    for position, level_count in enumerate(levels, 1):
        counts = [sum(row[position - 1] == level for row in matrix)
                  for level in range(1, level_count + 1)]
        column_counts.append({"position": position, "official_header": headers[position - 1],
                              "level_counts": counts, "balanced": len(set(counts)) == 1})
    pair_counts = []
    unbalanced_positions = []
    for first, second in combinations(range(len(levels)), 2):
        counts = [[sum(row[first] == a and row[second] == b for row in matrix)
                   for b in range(1, levels[second] + 1)]
                  for a in range(1, levels[first] + 1)]
        balanced = len({count for row in counts for count in row}) == 1
        pair_counts.append({
            "positions": [first + 1, second + 1],
            "official_headers": [headers[first], headers[second]],
            "counts": counts,
            "balanced": balanced,
        })
        if not balanced:
            unbalanced_positions.append([first + 1, second + 1])
    return {
        "array_id": array_id,
        "levels": levels,
        "runs": len(matrix),
        "column_headers": headers,
        "matrix": matrix,
        "column_counts": column_counts,
        "column_pairs": pair_counts,
        "all_columns_marginally_balanced": all(item["balanced"] for item in column_counts),
        "all_column_pairs_balanced": not unbalanced_positions,
        "unbalanced_position_pairs": unbalanced_positions,
        "matrix_sha256": canonical_matrix_sha(array_id, levels, matrix),
    }


def sn_smaller(values: list[float]) -> float:
    return -10 * math.log10(sum(value * value for value in values) / len(values))


def sn_larger(values: list[float]) -> float:
    if any(value == 0 for value in values):
        raise ValueError("larger-is-better requires nonzero responses")
    return -10 * math.log10(sum(1 / (value * value) for value in values) / len(values))


def sample_variance(values: list[float]) -> float:
    mean = sum(values) / len(values)
    return sum((value - mean) ** 2 for value in values) / (len(values) - 1)


def nominal_one(values: list[float]) -> float:
    variance = sample_variance(values)
    if variance == 0:
        raise ValueError("nominal-is-best requires nonzero sample variance")
    mean = sum(values) / len(values)
    return 10 * math.log10(mean * mean / variance)


def nominal_two(values: list[float]) -> float:
    variance = sample_variance(values)
    if variance == 0:
        raise ValueError("nominal-is-best requires nonzero sample variance")
    return -10 * math.log10(variance)


def adjusted_nominal_one(values: list[float]) -> float:
    variance = sample_variance(values)
    mean = sum(values) / len(values)
    numerator = mean * mean - variance / len(values)
    if variance == 0 or numerator <= 0:
        raise ValueError("adjusted nominal-is-best requires a positive formula domain")
    return 10 * math.log10(numerator / variance)


def taguchi_references() -> dict:
    values = [1.0, 2.0, 3.0]
    mean = sum(values) / len(values)
    variance = sample_variance(values)
    zero_values = [2.0, 2.0]
    zero_nominal = {}
    for name, function in (("nominal_I", nominal_one), ("nominal_II", nominal_two)):
        try:
            function(zero_values)
        except ValueError:
            zero_nominal[name] = "rejected_zero_sample_variance"
    try:
        adjusted_nominal_one(zero_values)
    except ValueError:
        zero_adjusted = "rejected_zero_sample_variance"
    return {
        "formulas": {
            "smaller": "-10*log10(mean(y^2))",
            "larger": "-10*log10(mean(1/y^2)); y!=0",
            "nominal_I": "10*log10(mean(y)^2/sample_variance(y, ddof=1))",
            "nominal_II": "-10*log10(sample_variance(y, ddof=1))",
            "adjusted_nominal_I": "10*log10((mean(y)^2-sample_variance(y,ddof=1)/n)/sample_variance(y,ddof=1))",
        },
        "sample_case": {
            "responses": values,
            "n": len(values),
            "mean": rounded(mean),
            "sample_variance_ddof_1": rounded(variance),
            "sample_sd_ddof_1": rounded(math.sqrt(variance)),
            "sn": {
                "smaller": rounded(sn_smaller(values)),
                "larger": rounded(sn_larger(values)),
                "nominal_I": rounded(nominal_one(values)),
                "nominal_II": rounded(nominal_two(values)),
                "adjusted_nominal_I": rounded(adjusted_nominal_one(values)),
            },
        },
        "zero_variance_boundaries": {
            "responses": zero_values,
            "sample_variance_ddof_1": 0,
            "smaller": {"status": "legal", "sn": rounded(sn_smaller(zero_values))},
            "larger": {"status": "legal", "sn": rounded(sn_larger(zero_values))},
            "nominal_I_and_II": {"status": "rejected", "cases": zero_nominal},
            "adjusted_nominal_I": {"status": "rejected", "case": zero_adjusted},
            "larger_with_zero_response": {
                "responses": [0.0, 2.0], "status": "rejected_zero_response",
            },
            "larger_with_negative_responses": {
                "responses": [-2.0, 2.0], "status": "legal",
                "sn": rounded(sn_larger([-2.0, 2.0])),
            },
        },
    }


def noise_case() -> dict:
    records = []
    controls = list(product((1, 2), repeat=2))
    noise_conditions = list(product((1, 2), (1, 2, 3)))
    for control_index, (a, b) in enumerate(controls, 1):
        control_id = f"CTRL-{a}{b}"
        for noise_index, (n1, n2) in enumerate(noise_conditions, 1):
            noise_id = f"NOISE-{noise_index:02d}"
            condition_id = f"{control_id}|{noise_id}"
            for replicate in (1, 2):
                response = 10 + 2 * a + 3 * b + 1.5 * n1 + 0.75 * n2 + 0.5 * (replicate - 1.5)
                records.append({
                    "run_id": f"TAG-{len(records) + 1:03d}",
                    "control_id": control_id,
                    "control_levels": {"A": a, "B": b},
                    "noise_condition_id": noise_id,
                    "noise_levels": {"N2": n1, "N3": n2},
                    "condition_id": condition_id,
                    "replicate_id": f"REP-{replicate}",
                    "replicate": replicate,
                    "response": rounded(response),
                })
    grouped_condition = defaultdict(list)
    grouped_control = defaultdict(list)
    for row in records:
        grouped_condition[row["condition_id"]].append(row["response"])
        grouped_control[row["control_id"]].append(row["response"])
    conditions = []
    for condition_id in sorted(grouped_condition):
        values = grouped_condition[condition_id]
        conditions.append({
            "condition_id": condition_id,
            "responses": values,
            "n_replicates": len(values),
            "mean": rounded(sum(values) / len(values)),
            "range": rounded(max(values) - min(values)),
            "sample_sd_ddof_1": rounded(math.sqrt(sample_variance(values))),
            "sn_smaller": rounded(sn_smaller(values)),
        })
    controls_summary = []
    for control_id in sorted(grouped_control):
        values = grouped_control[control_id]
        condition_means = [
            sum(grouped_condition[f"{control_id}|NOISE-{index:02d}"])
            / len(grouped_condition[f"{control_id}|NOISE-{index:02d}"])
            for index in range(1, len(noise_conditions) + 1)
        ]
        controls_summary.append({
            "control_id": control_id,
            "responses": values,
            "observation_count": len(values),
            "noise_condition_count": len(noise_conditions),
            "noise_condition_mean_range": rounded(max(condition_means) - min(condition_means)),
            "mean": rounded(sum(values) / len(values)),
            "sample_sd_ddof_1": rounded(math.sqrt(sample_variance(values))),
            "sn_smaller": rounded(sn_smaller(values)),
        })
    counts = {
        "run_id": dict(sorted(Counter(row["run_id"] for row in records).items())),
        "replicate_id": dict(sorted(Counter(row["replicate_id"] for row in records).items())),
        "noise_condition_id": dict(sorted(Counter(row["noise_condition_id"] for row in records).items())),
        "condition_id": dict(sorted(Counter(row["condition_id"] for row in records).items())),
        "control_id": dict(sorted(Counter(row["control_id"] for row in records).items())),
    }
    return {
        "controls": ["A", "B"],
        "noise_factors": {"N2": [1, 2], "N3": [1, 2, 3]},
        "replicates_per_noise_condition": 2,
        "records": records,
        "condition_statistics": conditions,
        "control_statistics": controls_summary,
        "identity_frequencies": counts,
        "expected": {
            "control_combinations": 4,
            "true_noise_conditions": 6,
            "control_noise_condition_groups": 24,
            "runs": 48,
            "observations_per_control": 12,
            "replicate_rows_per_control_condition": 2,
        },
    }


def additive_selection() -> dict:
    sn_effects = {"A": {1: 2.0, 2: -2.0}, "B": {1: 1.0, 2: -1.0}}
    mean_effects = {"A": {1: 10.0, 2: -10.0}, "B": {1: -5.0, 2: 5.0}}
    sd_observed = {(1, 1): 0.0, (1, 2): 0.0, (2, 1): 0.0, (2, 2): 100.0}
    sd_intercept = sum(sd_observed.values()) / len(sd_observed)
    sd_effects = {
        "A": {level: sum(value for (a, _), value in sd_observed.items() if a == level) / 2
              - sd_intercept for level in (1, 2)},
        "B": {level: sum(value for (_, b), value in sd_observed.items() if b == level) / 2
              - sd_intercept for level in (1, 2)},
    }
    combinations = []
    for a, b in product((1, 2), repeat=2):
        predicted_sd = sd_intercept + sd_effects["A"][a] + sd_effects["B"][b]
        identifier = f"A{a}B{b}"
        combinations.append({
            "combination_id": identifier,
            "levels": {"A": a, "B": b},
            "predicted_sn": rounded(20 + sn_effects["A"][a] + sn_effects["B"][b]),
            "predicted_mean": rounded(100 + mean_effects["A"][a] + mean_effects["B"][b]),
            "observed": identifier != "A2B2",
            "observed_sd": sd_observed[(a, b)],
            "additive_predicted_sd": rounded(predicted_sd),
            "predicted_sd": None if predicted_sd < 0 else rounded(predicted_sd),
            "predicted_sd_status": "unavailable_negative" if predicted_sd < 0 else "available",
        })
    max_sn = max(row["predicted_sn"] for row in combinations)
    threshold, target = 19.0, 95.0
    eligible = [row for row in combinations if row["predicted_sn"] >= threshold]
    best_distance = min(abs(row["predicted_mean"] - target) for row in eligible)
    selected = [row["combination_id"] for row in eligible
                if abs(row["predicted_mean"] - target) == best_distance]
    return {
        "level_effects": {"sn": sn_effects, "mean": mean_effects},
        "intercepts": {"sn": 20.0, "mean": 100.0},
        "sd_reference": {"observed_by_combination": {
                             f"A{a}B{b}": value for (a, b), value in sd_observed.items()},
                         "intercept": sd_intercept, "level_effects": sd_effects},
        "all_combinations": combinations,
        "sn_maximum": {
            "selected": [row["combination_id"] for row in combinations if row["predicted_sn"] == max_sn],
            "maximum_predicted_sn": max_sn,
        },
        "robust_then_target": {
            "sn_threshold": threshold,
            "target": target,
            "eligible": [row["combination_id"] for row in eligible],
            "minimum_absolute_target_distance": best_distance,
            "selected_all_ties": selected,
        },
        "confirmation": {
            "settings": "A1B1",
            "predicted_mean": 105.0,
            "observed_mean": 104.0,
            "observed_minus_predicted": -1.0,
            "target": target,
            "target_tolerance": 10.0,
            "meets_target": True,
            "writes_back_to_design": False,
        },
        "unreachable_threshold": {
            "sn_threshold": 24.0,
            "maximum_predicted_sn": max_sn,
            "status": "rejected_no_candidate_no_fallback",
        },
        "enumeration_budget": {
            "maximum": 20000,
            "requested_factor_levels": [2] * 15,
            "requested_combinations": 2 ** 15,
            "status": "rejected_over_budget",
        },
    }


def lattice_points() -> list[tuple[Fraction, ...]]:
    return [
        (Fraction(1), Fraction(0), Fraction(0)),
        (Fraction(0), Fraction(1), Fraction(0)),
        (Fraction(0), Fraction(0), Fraction(1)),
        (Fraction(1, 2), Fraction(1, 2), Fraction(0)),
        (Fraction(1, 2), Fraction(0), Fraction(1, 2)),
        (Fraction(0), Fraction(1, 2), Fraction(1, 2)),
    ]


def mixture_design(name: str, factor_combinations: list[dict], total_for,
                   process_factors: dict, amount_levels: list[int] | None) -> dict:
    points = lattice_points()
    rows = []
    for point_index, point in enumerate(points, 1):
        for factor_values in factor_combinations:
            total = total_for(factor_values)
            amounts = [Fraction(total) * value for value in point]
            row = {
                "run_id": f"{name}-{len(rows) + 1:03d}",
                "lattice_point_id": f"L{point_index}",
                "proportions": [fraction_text(value) for value in point],
                "total_amount": total,
                "actual_amounts": [fraction_text(value) for value in amounts],
                "process": {key: factor_values[key] for key in process_factors},
            }
            if amount_levels is not None:
                row["amount_level"] = factor_values["amount_level"]
            rows.append(row)
    return {
        "runs": rows,
        "factor_combinations": factor_combinations,
        "process_factor_levels": process_factors,
        "amount_levels": amount_levels,
        "lattice_point_count": len(points),
        "expected_runs": len(points) * len(factor_combinations),
    }


def mixture_references() -> dict:
    process2 = list(product((1, 2), repeat=2))
    c1 = mixture_design(
        "C1", [{"P1": p1, "P2": p2} for p1, p2 in process2],
        lambda _: 120, {"P1": [1, 2], "P2": [1, 2]}, None,
    )
    c2 = mixture_design(
        "C2", [{"amount_level": amount} for amount in (50, 100, 150)],
        lambda item: item["amount_level"], {}, [50, 100, 150],
    )
    c3 = mixture_design(
        "C3", [{"P1": p1, "P2": p2, "amount_level": amount}
               for p1, p2 in process2 for amount in (80, 120)],
        lambda item: item["amount_level"], {"P1": [1, 2], "P2": [1, 2]}, [80, 120],
    )
    return {"simplex_lattice_degree_2": [[fraction_text(v) for v in point]
                                         for point in lattice_points()],
            "C1": c1, "C2": c2, "C3": c3}


def matrix_rank(matrix: list[list[float]]) -> int:
    rows = [[Fraction(str(value)) for value in row] for row in matrix]
    if not rows:
        return 0
    pivot_row = 0
    for column in range(len(rows[0])):
        pivot = next((i for i in range(pivot_row, len(rows)) if rows[i][column]), None)
        if pivot is None:
            continue
        rows[pivot_row], rows[pivot] = rows[pivot], rows[pivot_row]
        for i in range(pivot_row + 1, len(rows)):
            if rows[i][column]:
                factor = rows[i][column] / rows[pivot_row][column]
                rows[i] = [left - factor * right for left, right in zip(rows[i], rows[pivot_row])]
        pivot_row += 1
        if pivot_row == len(rows):
            break
    return pivot_row


def solve(matrix: list[list[float]], vector: list[float]) -> list[float]:
    work = [list(map(float, row)) + [float(value)] for row, value in zip(matrix, vector)]
    size = len(work)
    for column in range(size):
        pivot = max(range(column, size), key=lambda row: abs(work[row][column]))
        work[column], work[pivot] = work[pivot], work[column]
        scale = work[column][column]
        if abs(scale) < 1e-14:
            raise ValueError("singular normal equations")
        work[column] = [value / scale for value in work[column]]
        for row in range(size):
            if row == column:
                continue
            scale = work[row][column]
            work[row] = [left - scale * right for left, right in zip(work[row], work[column])]
    return [work[row][-1] for row in range(size)]


def symmetric_eigenvalues(matrix: list[list[float]]) -> list[float]:
    work = [list(map(float, row)) for row in matrix]
    size = len(work)
    for _ in range(100 * size * size):
        p, q, largest = 0, 1, 0.0
        for i in range(size):
            for j in range(i + 1, size):
                if abs(work[i][j]) > largest:
                    p, q, largest = i, j, abs(work[i][j])
        if largest < 1e-13:
            break
        app, aqq, apq = work[p][p], work[q][q], work[p][q]
        tau = (aqq - app) / (2 * apq)
        tangent = (1.0 if tau >= 0 else -1.0) / (abs(tau) + math.sqrt(1 + tau * tau))
        cosine = 1 / math.sqrt(1 + tangent * tangent)
        sine = tangent * cosine
        work[p][p] = app - tangent * apq
        work[q][q] = aqq + tangent * apq
        work[p][q] = work[q][p] = 0.0
        for k in range(size):
            if k in (p, q):
                continue
            left, right = work[k][p], work[k][q]
            work[k][p] = work[p][k] = cosine * left - sine * right
            work[k][q] = work[q][k] = sine * left + cosine * right
    return [work[i][i] for i in range(size)]


def model_terms(point: list[float], process: tuple[int, int], amount: int) -> list[float]:
    x1, x2, x3 = point
    p1, p2 = process
    return [x1, x2, x3, x1*x2, x1*x3, x2*x3,
            x1*p1, x2*p1, x3*p1, x1*p2, x2*p2, x3*p2,
            x1*amount, x2*amount, x3*amount]


def joint_model() -> dict:
    terms = ["x1", "x2", "x3", "x1*x2", "x1*x3", "x2*x3",
             "x1*p1", "x2*p1", "x3*p1", "x1*p2", "x2*p2", "x3*p2",
             "x1*amount", "x2*amount", "x3*amount"]
    points = [[float(value) for value in point] for point in lattice_points()]
    z_scale = math.sqrt(1.5)
    z_by_point = [0.0, -z_scale, 0.0, z_scale, -z_scale, z_scale]
    beta = [10, 20, 30, 2, 3, 4, 1, 2, 3, 4, 5, 6, 7, 8, 9]
    matrix, responses, fitted, residuals, run_ids, row_info = [], [], [], [], [], []
    for point_index, point in enumerate(points):
        for process in product((-1, 1), repeat=2):
            for amount in (-1, 0, 1):
                row = model_terms(point, process, amount)
                fit = sum(value * coefficient for value, coefficient in zip(row, beta))
                residual = 0.5 * z_by_point[point_index] * amount
                matrix.append(row)
                fitted.append(fit)
                residuals.append(residual)
                responses.append(fit + residual)
                run_id = f"MODEL-{len(run_ids) + 1:03d}"
                run_ids.append(run_id)
                row_info.append({"run_id": run_id, "mixture_index": point_index + 1,
                                 "proportions": [rounded(v) for v in point],
                                 "process_codes": list(process), "amount_code": amount,
                                 "z1": rounded(z_by_point[point_index])})
    gram = [[sum(row[i] * row[j] for row in matrix) for j in range(len(terms))]
            for i in range(len(terms))]
    rhs = [sum(row[i] * value for row, value in zip(matrix, responses))
           for i in range(len(terms))]
    estimated_beta = solve(gram, rhs)
    eigenvalues = symmetric_eigenvalues(gram)
    condition_number = math.sqrt(max(eigenvalues) / min(eigenvalues))
    orthogonality = [sum(row[column] * residual for row, residual in zip(matrix, residuals))
                     for column in range(len(terms))]
    prediction_input = {"proportions": ["1/3", "1/3", "1/3"],
                        "process_codes": [-1, 1], "amount_code": 0.5}
    prediction_row = model_terms([1/3] * 3, (-1, 1), 0.5)
    return {
        "terms": terms,
        "matrix": [[rounded(value) for value in row] for row in matrix],
        "rows": row_info,
        "known_beta": beta,
        "estimated_beta": [rounded(value) for value in estimated_beta],
        "fitted": [rounded(value) for value in fitted],
        "responses": [rounded(value) for value in responses],
        "residuals": [rounded(value) for value in residuals],
        "expected": {
            "n": len(matrix),
            "p": len(terms),
            "rank": matrix_rank(matrix),
            "condition_number_2": rounded(condition_number),
            "sse": rounded(sum(value * value for value in residuals)),
            "residual_df": len(matrix) - len(terms),
            "residual_dot_each_model_column": [rounded(value) for value in orthogonality],
            "prediction": {"input": prediction_input,
                           "terms": [rounded(value) for value in prediction_row],
                           "value": rounded(sum(value * coefficient
                                                 for value, coefficient in zip(prediction_row, beta)))},
        },
        "no_noise_case": {"responses": [rounded(value) for value in fitted],
                          "fitted": [rounded(value) for value in fitted],
                          "estimated_beta": [rounded(value) for value in beta],
                          "sse": 0.0, "residual_df": len(matrix) - len(terms)},
    }


def determinant3(matrix: list[list[Fraction]]) -> Fraction:
    a, b, c = matrix
    return (a[0] * (b[1]*c[2] - b[2]*c[1])
            - a[1] * (b[0]*c[2] - b[2]*c[0])
            + a[2] * (b[0]*c[1] - b[1]*c[0]))


def d_optimal_replacement() -> dict:
    points = {
        "LOCK-A": [Fraction(1), Fraction(0), Fraction(0)],
        "LOCK-B": [Fraction(0), Fraction(1), Fraction(0)],
        "PARENT-003": [Fraction(9, 20), Fraction(9, 20), Fraction(1, 10)],
        "CAND-C": [Fraction(0), Fraction(0), Fraction(1)],
        "CAND-70": [Fraction(1, 10), Fraction(1, 5), Fraction(7, 10)],
        "CAND-60": [Fraction(1, 5), Fraction(1, 5), Fraction(3, 5)],
        "CAND-50": [Fraction(1, 4), Fraction(1, 4), Fraction(1, 2)],
    }
    fixed_ids = ["LOCK-A", "LOCK-B"]
    candidate_ids = ["CAND-C", "CAND-70", "CAND-60", "CAND-50"]
    candidates = []
    for candidate_id in candidate_ids:
        determinant = determinant3([points[key] for key in fixed_ids + [candidate_id]])
        information_determinant = determinant * determinant
        candidates.append({"candidate_run_id": candidate_id,
                           "point": [fraction_text(value) for value in points[candidate_id]],
                           "det_xtx": fraction_text(information_determinant),
                           "logdet_xtx": rounded(math.log(float(information_determinant)))})
    best_det = max(Fraction(item["det_xtx"]) for item in candidates)
    best_ids = [item["candidate_run_id"] for item in candidates
                if Fraction(item["det_xtx"]) == best_det]
    parent_det = determinant3([points[key] for key in fixed_ids + ["PARENT-003"]]) ** 2
    rows = [
        {"run_id": "LOCK-A", "point": ["1", "0", "0"], "locked": True,
         "measured_response": 11.0, "lineage_id": "BATCH-001"},
        {"run_id": "LOCK-B", "point": ["0", "1", "0"], "locked": True,
         "measured_response": 22.0, "lineage_id": "BATCH-001"},
        {"run_id": "PARENT-003", "point": ["9/20", "9/20", "1/10"], "locked": False,
         "measured_response": None, "lineage_id": "BATCH-001"},
    ]
    after = [rows[0], rows[1], {
        "run_id": best_ids[0], "point": [fraction_text(value) for value in points[best_ids[0]]],
        "locked": False, "measured_response": None, "lineage_id": "BATCH-002",
    }]
    return {
        "model_terms": ["x1", "x2", "x3"],
        "selection_seed": 23,
        "locked_rows": rows[:2],
        "replaceable_parent": rows[2],
        "candidates": candidates,
        "enumerated_subsets": len(candidate_ids),
        "before": {"run_ids": [row["run_id"] for row in rows],
                   "rank": 3, "det_xtx": fraction_text(parent_det),
                   "logdet_xtx": rounded(math.log(float(parent_det)))},
        "after": {"run_ids": [row["run_id"] for row in after],
                  "rank": 3, "det_xtx": fraction_text(best_det),
                  "logdet_xtx": rounded(math.log(float(best_det))),
                  "selected_candidate_run_id": best_ids[0],
                  "global_optimum_proven": True,
                  "evaluations": len(candidate_ids),
                  "stop_reason": "exhaustive_candidate_subsets"},
        "same_seed_repeat": {"selection_seed": 23,
                             "selected_candidate_run_id": best_ids[0],
                             "run_ids": [row["run_id"] for row in after]},
        "protected_measured_rows_before_after": rows[:2],
        "expected": {"unique_best_candidate": best_ids,
                     "locked_run_ids_preserved": ["LOCK-A", "LOCK-B"],
                     "locked_responses_preserved": [11.0, 22.0]},
    }


def invalid_boundaries() -> list[dict]:
    return [
        {"id": "mixture_sum_not_one", "input": {"proportions": ["1/2", "1/4", "1/5"]},
         "expected": "reject_proportions_sum"},
        {"id": "zero_total", "input": {"total_amount": 0}, "expected": "reject_nonpositive_total"},
        {"id": "negative_total", "input": {"total_amount": -1}, "expected": "reject_nonpositive_total"},
        {"id": "rank_deficiency", "input": {"matrix": [[1, 0, 0], [0, 1, 0], [0, 1, 0]]},
         "expected": "rank_2_reject_rank_3_required"},
        {"id": "locked_row_replacement", "input": {"run_id": "LOCK-A", "locked": True,
                                                       "measured_response": 11},
         "expected": "reject_locked_or_measured"},
        {"id": "measured_row_replacement", "input": {"run_id": "PARENT-MEASURED", "locked": False,
                                                         "measured_response": 9},
         "expected": "reject_locked_or_measured"},
        {"id": "insufficient_candidates", "input": {"select": 2, "candidate_count": 1},
         "expected": "reject_candidate_pool_too_small"},
        {"id": "selection_over_budget", "input": {"combination_count": 32768, "budget": 20000},
         "expected": "reject_over_budget"},
        {"id": "unreachable_sn_threshold", "input": {"threshold": 24, "maximum_predicted_sn": 23},
         "expected": "reject_without_fallback"},
        {"id": "lineage_mismatch", "input": {"expected_parent": "BATCH-001",
                                                "candidate_parent": "BATCH-OTHER"},
         "expected": "reject_identity_lineage_mismatch"},
        {"id": "run_id_mismatch", "input": {"expected_run_id": "CAND-C",
                                              "actual_run_id": "CAND-X"},
         "expected": "reject_identity_mismatch"},
    ]


def build_reference() -> dict:
    arrays = [array_reference(L8_ID, L8_LEVELS, L8),
              array_reference(L16_ID, L16_LEVELS, L16),
              array_reference(L18_ID, L18_LEVELS, L18, L18_HEADERS)]
    return {
        "fixture_id": "doe_phase2_p4bc_reference",
        "provenance": {
            "official_catalogue_url": CATALOGUE_URL,
            "sn_methods_url": SN_URL,
            "two_step_robustness_url": ROBUST_URL,
            "l18_independent_copy_from": "tests/fixtures/doe_taguchi_reference/l18_2_1_3_7.csv",
            "l16_transcription": "official L16 (2^12), (4^1), all 16 rows and 13 factor columns",
        },
        "taguchi_arrays": arrays,
        "level_mapping_examples": {
            "numeric": {"factor": "Temperature", "codes": [1, 2],
                        "actual_levels": [10.5, 20.5], "coded_row": [2], "decoded": [20.5]},
            "text": {"factor": "Material", "codes": [1, 2],
                     "actual_levels": ["低", "高"], "coded_row": [2], "decoded": ["高"]},
        },
        "static_signal_to_noise": taguchi_references(),
        "noise_factor_case": noise_case(),
        "two_stage_selection": additive_selection(),
        "mixture_lattice_crosses": mixture_references(),
        "joint_mixture_process_amount_model": joint_model(),
        "d_optimal_replacement": d_optimal_replacement(),
        "invalid_boundaries": invalid_boundaries(),
    }


def byte_hash(path: Path) -> dict:
    payload = path.read_bytes()
    return {"bytes": len(payload), "sha256": sha256(payload).hexdigest()}


def write_manifest() -> dict:
    paths = ["README.md", "reference.json", "build_reference.py", "verify.py"]
    files = {name: byte_hash(HERE / name) for name in paths}
    manifest = {
        "fixture_id": "doe_phase2_p4bc_reference",
        "hashes_cover_complete_file_bytes": True,
        "canonical_matrix_hash": "sha256(canonical JSON; sort_keys; compact separators; UTF-8)",
        "source": {
            "official_catalogue_url": CATALOGUE_URL,
            "official_sn_methods_url": SN_URL,
            "official_two_step_robustness_url": ROBUST_URL,
            "accessed": "2026-10-29",
            "l16_section": "L16 (2^12), (4^1), official table headings 1..13",
            "l18_section": "L18 (2^1), (3^7), official table headings 1..7,9",
            "l18_prior_frozen_csv": "tests/fixtures/doe_taguchi_reference/l18_2_1_3_7.csv",
            "l18_known_unbalanced_column_positions": [[3, 8], [4, 8], [5, 8], [6, 8], [7, 8]],
            "l18_position_8_official_header": 9,
        },
        "files": files,
        "frozen_reference_sha256": files["reference.json"]["sha256"],
        "generator_sha256": files["build_reference.py"]["sha256"],
        "verifier_sha256": files["verify.py"]["sha256"],
    }
    (HERE / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> None:
    payload = json.dumps(build_reference(), indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    (HERE / "reference.json").write_text(payload, encoding="utf-8")
    manifest = write_manifest()
    print(f"built reference.json sha256={manifest['frozen_reference_sha256']}")
    print("updated manifest.json byte hashes for README.md, reference.json, build_reference.py, verify.py")


if __name__ == "__main__":
    main()
