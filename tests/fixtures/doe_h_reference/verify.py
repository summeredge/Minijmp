"""Re-derive and verify the DOE-H reference without importing production code."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.special import expit, logit
from scipy.stats import chi2, f, ncf, norm


ROOT = Path(__file__).resolve().parent
ACC_IDS = (
    "MTB-DOE-ACC-004", "MTB-DOE-ACC-019", "MTB-DOE-ACC-020",
    "MTB-DOE-ACC-031", "MTB-DOE-ACC-059", "MTB-DOE-ACC-060",
)


def _close(actual, expected):
    assert np.allclose(actual, expected, rtol=1e-11, atol=1e-12), (actual, expected)


def _verify_binary(case):
    x = np.asarray(case["columns"], dtype=float)
    events = np.asarray(case["events"], dtype=float)
    trials = np.asarray(case["trials"], dtype=float)
    probability = events / trials
    beta = np.linalg.lstsq(x, logit(probability), rcond=None)[0]
    fitted = expit(x @ beta)
    _close(fitted, probability)
    _close(beta, case["expected"]["coefficients"])
    information = x.T @ ((trials * fitted * (1 - fitted))[:, None] * x)
    standard_error = np.sqrt(np.diag(np.linalg.inv(information)))
    _close(standard_error, case["expected"]["standard_errors"])
    _close(beta / standard_error, case["expected"]["wald_z"])
    _close(2 * norm.sf(np.abs(beta / standard_error)), case["expected"]["wald_p"])

    def ll(p):
        return float(np.sum(events * np.log(p) + (trials - events) * np.log1p(-p)))

    null_p = events.sum() / trials.sum()
    lr = 2 * (ll(fitted) - ll(np.full(len(events), null_p)))
    df = int(np.linalg.matrix_rank(x) - 1)
    expected = case["expected"]
    _close(fitted, expected["predicted_probability"])
    _close(lr, expected["model_lr_chi_square"])
    _close(chi2.sf(lr, df), expected["model_lr_p"])
    assert df == expected["model_df"]
    assert len(events) - np.linalg.matrix_rank(x) == expected["residual_df"]
    _close(ll(fitted), expected["log_likelihood_without_binomial_constant"])


def _verify_variability(case):
    points = np.asarray(case["design_points"], dtype=float)
    raw = case["raw_repeated_values_by_setting"]
    means = np.asarray([np.mean(values) for values in raw])
    sds = np.asarray([np.std(values, ddof=1) for values in raw])
    counts = np.asarray([len(values) for values in raw])
    y = np.log(sds)
    x = np.column_stack((np.ones(len(points)), points))
    beta = np.linalg.lstsq(x, y, rcond=None)[0]
    fitted = x @ beta
    residual = y - fitted
    df_error = len(y) - np.linalg.matrix_rank(x)
    mse = float(residual @ residual / df_error)
    expected = case["expected"]
    assert [row["measurements"] for row in case["repeats_across_columns"]] == raw
    assert [row["measurement"] for row in case["replicates_down_rows"]] == [
        value for group in raw for value in group]
    assert all(row["block"] == 1 for row in case["replicates_down_rows"])
    _close(means, expected["mean"])
    _close(sds, expected["sample_sd"])
    _close(counts, expected["n"])
    _close(y, expected["log_sd"])
    _close(beta, expected["coefficients"])
    _close(fitted, expected["fitted_log_sd"])
    _close(residual @ residual, expected["sse"])
    _close(mse, expected["mse"])
    assert df_error == expected["df_error"]
    for column, name in ((1, "X1"), (2, "X2")):
        reduced = np.delete(x, column, axis=1)
        reduced_residual = y - reduced @ np.linalg.lstsq(reduced, y, rcond=None)[0]
        adjusted_ss = float(reduced_residual @ reduced_residual - residual @ residual)
        covariance = mse * np.linalg.inv(x.T @ x)
        statistic = beta[column] ** 2 / covariance[column, column]
        expected_term = expected["terms"][name]
        _close(adjusted_ss, expected_term["adjusted_ss"])
        _close(statistic, expected_term["f"])
        _close(f.sf(statistic, 1, df_error), expected_term["p"])


def _verify_power(case):
    points = np.asarray(case["design_points"], dtype=float)
    x = np.column_stack((np.ones(len(points)), points))
    rank = np.linalg.matrix_rank(x)
    tested = case["factor_names"].index(case["tested_factor"]) + 1
    inverse = np.linalg.inv(x.T @ x)
    alpha = case["alpha"]
    effect = case["effect_high_minus_low"]
    sigma = case["sigma"]

    def calculate(replicates):
        df_error = len(points) * replicates - rank
        if df_error <= 0:
            return None
        ncp = (effect / 2) ** 2 / (sigma**2 * inverse[tested, tested] / replicates)
        critical = f.ppf(1 - alpha, 1, df_error)
        return {
            "replicates": replicates,
            "total_runs": len(points) * replicates,
            "df_model": int(rank - 1),
            "df_error": int(df_error),
            "df_test": 1,
            "noncentrality": float(ncp),
            "critical_f": float(critical),
            "power": float(ncf.sf(critical, 1, df_error, ncp)),
        }

    expected = case["fixed_replicates"]
    _close(calculate(expected["replicates"])["power"], expected["power"])
    _close(calculate(expected["replicates"])["noncentrality"], expected["noncentrality"])
    minimum = case["minimum_replicates"]
    _close(calculate(minimum["replicates"])["power"], minimum["power"])
    assert minimum["power"] >= case["target_power"]
    previous = calculate(minimum["replicates"] - 1)
    if previous is None:
        assert case["previous_replicates_power"] is None
    else:
        _close(previous["power"], case["previous_replicates_power"])
        assert previous["power"] < case["target_power"]
    assert minimum["total_runs"] <= case["run_limit"]


def verify():
    payload = (ROOT / "reference.json").read_bytes()
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    assert hashlib.sha256(payload).hexdigest() == manifest["reference.json"]["sha256"]
    reference = json.loads(payload.decode("utf-8"))
    assert all(not name.startswith(("doe_", "MiniJMP"))
               for name in manifest["reference.json"]["production_imports"])
    assert set(ACC_IDS) == set(reference["acceptance_cases"])
    assert all("STD" in reference["acceptance_cases"][acc]
               and "EDGE" in reference["acceptance_cases"][acc] for acc in ACC_IDS)
    for case in reference["binary"].values():
        _verify_binary(case)
    _verify_variability(reference["variability"])
    for case in reference["power"].values():
        _verify_power(case)

    edges = reference["binary_edges"]
    assert all(events < 0 or events > trials or not float(events).is_integer()
               or trials <= 0 or not float(trials).is_integer()
               for events, trials in edges["invalid_counts"])
    assert all(events == 0 for events, _ in edges["all_failures"])
    assert all(events == trials for events, trials in edges["all_successes"])
    separated = edges["complete_separation"]
    assert max(x for x, e, n in zip(separated["x"], separated["events"],
                                   separated["trials"]) if e == 0) < min(
        x for x, e, n in zip(separated["x"], separated["events"],
                             separated["trials"]) if e == n)
    assert set(edges["rank_deficient_dsd_interaction"]["interaction_column"]) == {0}
    var_edges = reference["variability"]["edges"]
    assert np.std(var_edges["zero_variance"], ddof=1) == 0
    assert len(var_edges["one_observation"]) == 1
    missing = [value for value in var_edges["missing_value"] if value is not None]
    assert len(missing) == 2 and np.isclose(np.std(missing, ddof=1), np.sqrt(2))
    assert len(var_edges["unequal_group_sizes"][0]) != len(var_edges["unequal_group_sizes"][1])
    assert reference["power_edges"]["zero_error_df"]["df_error"] == 0
    nonestimable = np.asarray(reference["power_edges"]["nonestimable"]["columns"], dtype=float)
    assert np.linalg.matrix_rank(nonestimable) < nonestimable.shape[1]
    limit_case = reference["power_edges"]["run_limit_unattainable"]
    max_repeat = limit_case["limit"] // limit_case["points"]
    assert max_repeat == 9
    df_error = limit_case["points"] * max_repeat - 11
    ncp = (limit_case["effect"] / 2) ** 2 / (
        limit_case["sigma"] ** 2 / limit_case["points"] / max_repeat)
    maximum_power = ncf.sf(f.ppf(1 - limit_case["alpha"], 1, df_error),
                           1, df_error, ncp)
    assert maximum_power < limit_case["target_power"]
    print("DOE-H independent references verified:", ", ".join(ACC_IDS))


if __name__ == "__main__":
    verify()
