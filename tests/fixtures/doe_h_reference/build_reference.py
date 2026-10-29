"""Build independent, hand-specified DOE-H calculation references."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np
from scipy.special import expit
from scipy.stats import chi2, f, ncf, norm


ROOT = Path(__file__).resolve().parent
MAX_RUNS = 10_000


def _binary_case(name, points, columns, beta, trials, term_names):
    x = np.asarray(columns, dtype=float)
    beta = np.asarray(beta, dtype=float)
    p = expit(x @ beta)
    trials = np.asarray(trials, dtype=int)
    events = np.rint(trials * p).astype(int)
    assert np.allclose(events / trials, p, atol=1e-14)
    weight = trials * p * (1 - p)
    covariance = np.linalg.inv(x.T @ (weight[:, None] * x))
    se = np.sqrt(np.diag(covariance))

    def log_likelihood(probability):
        return float(np.sum(events * np.log(probability)
                            + (trials - events) * np.log1p(-probability)))

    fitted_ll = log_likelihood(p)
    null_p = events.sum() / trials.sum()
    lr = 2 * (fitted_ll - log_likelihood(np.full(len(events), null_p)))
    df = int(np.linalg.matrix_rank(x) - 1)
    return {
        "case": name,
        "design_points": points,
        "columns": columns,
        "term_names": term_names,
        "events": events.tolist(),
        "trials": trials.tolist(),
        "expected": {
            "coefficients": beta.tolist(),
            "standard_errors": se.tolist(),
            "wald_z": (beta / se).tolist(),
            "wald_p": (2 * norm.sf(np.abs(beta / se))).tolist(),
            "predicted_probability": p.tolist(),
            "model_df": df,
            "residual_df": len(events) - int(np.linalg.matrix_rank(x)),
            "log_likelihood_without_binomial_constant": fitted_ll,
            "null_probability": float(null_p),
            "model_lr_chi_square": float(lr),
            "model_lr_p": float(chi2.sf(lr, df)),
        },
    }


def _power_case(name, points, factor_names, tested_factor, effect, sigma,
                alpha, replicates, target_power):
    x0 = np.column_stack((np.ones(len(points)), np.asarray(points, dtype=float)))
    tested_column = factor_names.index(tested_factor) + 1
    inverse = np.linalg.inv(x0.T @ x0)
    rank = int(np.linalg.matrix_rank(x0))

    def calculate(repeat):
        df_error = len(points) * repeat - rank
        if df_error <= 0:
            return None
        beta = effect / 2
        noncentrality = beta**2 / (sigma**2 * inverse[tested_column, tested_column] / repeat)
        critical = f.ppf(1 - alpha, 1, df_error)
        power = ncf.sf(critical, 1, df_error, noncentrality)
        return {
            "replicates": repeat,
            "total_runs": len(points) * repeat,
            "df_model": rank - 1,
            "df_error": df_error,
            "df_test": 1,
            "noncentrality": float(noncentrality),
            "critical_f": float(critical),
            "power": float(power),
        }

    fixed = calculate(replicates)
    max_repeats = MAX_RUNS // len(points)
    minimum = None
    for repeat in range(1, max_repeats + 1):
        candidate = calculate(repeat)
        if candidate is not None and candidate["power"] >= target_power:
            minimum = candidate
            break
    assert fixed is not None and minimum is not None
    previous = calculate(minimum["replicates"] - 1)
    return {
        "case": name,
        "design_points": points,
        "factor_names": factor_names,
        "tested_factor": tested_factor,
        "effect_high_minus_low": effect,
        "sigma": sigma,
        "alpha": alpha,
        "fixed_replicates": fixed,
        "target_power": target_power,
        "minimum_replicates": minimum,
        "previous_replicates_power": None if previous is None else previous["power"],
        "run_limit": MAX_RUNS,
    }


def _pb12_three_factor_projection():
    residues = {1, 3, 4, 5, 9}

    def character(value):
        value %= 11
        return 0 if value == 0 else (1 if value in residues else -1)

    hadamard = [[1] * 12]
    for row in range(11):
        hadamard.append([1] + [character(row - column) - int(row == column)
                               for column in range(11)])
    points = [[row[1], row[2], row[3]] for row in hadamard]
    matrix = np.asarray(points, dtype=int)
    assert np.array_equal(matrix.T @ matrix, 12 * np.eye(3, dtype=int))
    assert np.all(matrix.sum(axis=0) == 0)
    return points


def build():
    log2 = math.log(2)
    dsd_points = [[-1, 0], [1, 0], [0, -1], [0, 1], [0, 0]]
    dsd_columns = [[1, a, b, a * a] for a, b in dsd_points]
    factorial_points = [[-1, -1], [1, -1], [-1, 1], [1, 1]]
    factorial_columns = [[1, a, b, a * b] for a, b in factorial_points]
    fractional_points = [[a, b, a * b] for a, b in factorial_points]
    fractional_columns = [[1, a, b, c] for a, b, c in fractional_points]
    pb_points = _pb12_three_factor_projection()
    pb_columns = [[1, a, b, c] for a, b, c in pb_points]
    gff_points = [[a, b] for a in (10, 20, 40) for b in (-1, 1)]
    gff_columns = []
    for a, b in gff_points:
        a20 = -1 if a == 10 else 1 if a == 20 else 0
        a40 = -1 if a == 10 else 1 if a == 40 else 0
        b_high = b
        gff_columns.append([1, a20, a40, b_high, a20 * b_high, a40 * b_high])

    bbd_points = []
    for first, second in ((0, 1), (0, 2), (1, 2)):
        for left, right in ((-1, -1), (-1, 1), (1, -1), (1, 1)):
            point = [0, 0, 0]
            point[first], point[second] = left, right
            bbd_points.append(point)
    bbd_points.extend([[0, 0, 0], [0, 0, 0]])
    bbd_columns = [[1, a, b, c, a * a, b * b, c * c,
                    a * b, a * c, b * c] for a, b, c in bbd_points]

    binary = {
        "dsd": _binary_case("2-factor DSD points; main effects and X1^2",
                            dsd_points, dsd_columns, [0, 0, 0, log2], [6] * 5,
                            ["Intercept", "X1", "X2", "X1^2"]),
        "factorial": _binary_case("2^2 factorial; main effects and interaction",
                                  factorial_points, factorial_columns,
                                  [0, log2, log2, 0], [10] * 4,
                                  ["Intercept", "A", "B", "A*B"]),
        "fractional_factorial": _binary_case(
            "2^(3-1) regular fraction; main effects reported as alias groups",
            fractional_points, fractional_columns, [0, log2, log2, log2], [9] * 4,
            ["Intercept", "A/BC", "B/AC", "C/AB"]),
        "plackett_burman": _binary_case(
            "12-run PB projection; main effects only", pb_points, pb_columns,
            [0, log2, 0, 0], [6] * 12, ["Intercept", "A", "B", "C"]),
        "general_full_factorial": _binary_case(
            "3x2 general full factorial; numeric A labels treated as categories",
            gff_points, gff_columns, [0, log2, -log2, log2, 0, 0], [30] * 6,
            ["Intercept", "A[20]", "A[40]", "B[high]", "A[20]*B", "A[40]*B"]),
        "rsm": _binary_case("3-factor Box-Behnken with two center runs; full quadratic",
                            bbd_points, bbd_columns,
                            [0, log2, 0, 0, log2, -log2, 0, 0, log2, 0], [90] * 14,
                            ["Intercept", "X1", "X2", "X3", "X1^2", "X2^2", "X3^2",
                             "X1*X2", "X1*X3", "X2*X3"]),
    }

    raw = [[0, -1, 1], [0, -2, 2], [0, -4, 4], [0, -16, 16]]
    var_points = [[-1, -1], [1, -1], [-1, 1], [1, 1]]
    var_matrix = np.column_stack((np.ones(4), var_points))
    means = [float(np.mean(row)) for row in raw]
    sds = [float(np.std(row, ddof=1)) for row in raw]
    log_sds = np.log(sds)
    beta = np.linalg.lstsq(var_matrix, log_sds, rcond=None)[0]
    fitted = var_matrix @ beta
    residual = log_sds - fitted
    df_error = len(raw) - int(np.linalg.matrix_rank(var_matrix))
    sse = float(residual @ residual)
    mse = sse / df_error
    var_terms = {}
    for column, name in ((1, "X1"), (2, "X2")):
        reduced = np.delete(var_matrix, column, axis=1)
        reduced_residual = log_sds - reduced @ np.linalg.lstsq(reduced, log_sds, rcond=None)[0]
        ss = float(reduced_residual @ reduced_residual - sse)
        se = float(math.sqrt(mse * np.linalg.inv(var_matrix.T @ var_matrix)[column, column]))
        statistic = float((beta[column] / se) ** 2)
        var_terms[name] = {
            "coefficient": float(beta[column]),
            "effect_high_minus_low": float(2 * beta[column]),
            "standard_error": se,
            "f": statistic,
            "df_numerator": 1,
            "df_error": df_error,
            "p": float(f.sf(statistic, 1, df_error)),
            "adjusted_ss": ss,
        }

    # Orthogonal 4-run PB main-effect matrix: intercept plus 3 mutually
    # orthogonal columns. One replicate is saturated; two provide error df.
    two_level_points = factorial_points
    fractional_power_points = [[a, b, a * b] for a, b in two_level_points]
    power = {
        "two_level": _power_case("2^2 full factorial", two_level_points,
                                 ["A", "B"], "A", 2, 1, 0.05, 2, 0.8),
        "regular_fractional": _power_case("2^(3-1) regular fraction",
                                           fractional_power_points, ["A", "B", "C"],
                                           "A", 2, 1, 0.05, 2, 0.8),
        "pb": _power_case("12-run PB projection with 3 factors", pb_points,
                          ["A", "B", "C"], "A", 2, 1, 0.05, 2, 0.8),
        "general_full_factorial": _power_case("2-level GFF with numeric labels",
                                              two_level_points, ["A", "B"], "A",
                                              2, 1, 0.05, 2, 0.8),
    }
    reference = {
        "schema_version": 1,
        "provenance": "Hand-specified matrices and independent likelihood, information-matrix, sample-SD, OLS, and noncentral-F calculations; no MiniJMP imports.",
        "binary": binary,
        "binary_edges": {
            "invalid_counts": [[-1, 10], [11, 10], [1.5, 10], [0, 0], [1, 2.5]],
            "all_failures": [[0, 10], [0, 10]],
            "all_successes": [[10, 10], [10, 10]],
            "complete_separation": {
                "x": [-1, 1, 0, 0, 0], "events": [0, 6, 0, 0, 0], "trials": [6] * 5,
            },
            "rank_deficient_dsd_interaction": {
                "points": dsd_points,
                "interaction_column": [a * b for a, b in dsd_points],
            },
        },
        "variability": {
            "design_points": var_points,
            "repeats_across_columns": [
                {"run_id": f"R{index + 1:02d}", "point": point, "measurements": values}
                for index, (point, values) in enumerate(zip(var_points, raw))],
            "replicates_down_rows": [
                {"run_id": f"R{index + 1:02d}-{rep + 1}", "point": point,
                 "block": 1, "measurement": value}
                for index, (point, values) in enumerate(zip(var_points, raw))
                for rep, value in enumerate(values)],
            "raw_repeated_values_by_setting": raw,
            "expected": {
                "mean": means,
                "sample_sd": sds,
                "n": [3] * 4,
                "log_sd": log_sds.tolist(),
                "coefficients": beta.tolist(),
                "effect_high_minus_low": [float(2 * beta[1]), float(2 * beta[2])],
                "fitted_log_sd": fitted.tolist(),
                "sse": sse,
                "df_error": df_error,
                "mse": mse,
                "terms": var_terms,
            },
            "edges": {
                "zero_variance": [4, 4, 4],
                "one_observation": [4],
                "missing_value": [2, None, 4],
                "unequal_group_sizes": [[0, 1, 2], [0, 1]],
            },
        },
        "power": power,
        "power_edges": {
            "zero_error_df": {"design": "12-run PB with 11 factors", "replicates": 1,
                              "df_error": 0},
            "nonestimable": {"columns": [[1, -1, -1], [1, 1, 1], [1, -1, -1], [1, 1, 1]],
                             "duplicate_factors": ["A", "B"]},
            "run_limit_unattainable": {"points": 1024, "limit": MAX_RUNS,
                                       "effect": 0.1, "sigma": 100, "alpha": 0.05,
                                       "target_power": 0.99},
        },
        "acceptance_cases": {
            "MTB-DOE-ACC-004": {"STD": "binary.dsd", "EDGE": "binary_edges"},
            "MTB-DOE-ACC-019": {
                "STD": ["binary.factorial", "binary.fractional_factorial",
                        "binary.plackett_burman", "binary.general_full_factorial"],
                "EDGE": "binary_edges",
            },
            "MTB-DOE-ACC-020": {"STD": "variability", "EDGE": "variability.edges"},
            "MTB-DOE-ACC-031": {"STD": "binary.rsm", "EDGE": "binary_edges"},
            "MTB-DOE-ACC-059": {
                "STD": ["power.two_level", "power.regular_fractional"],
                "EDGE": "power_edges",
            },
            "MTB-DOE-ACC-060": {"STD": "power.pb+general_full_factorial",
                                "EDGE": "power_edges"},
        },
    }
    return reference


def main():
    payload = json.dumps(build(), ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    (ROOT / "reference.json").write_bytes(payload.encode("utf-8"))
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    manifest = {
        "reference.json": {
            "sha256": digest,
            "source": "build_reference.py; NumPy/SciPy plus hand-specified designs",
            "production_imports": [],
        }
    }
    (ROOT / "manifest.json").write_bytes(
        (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(digest)


if __name__ == "__main__":
    main()
