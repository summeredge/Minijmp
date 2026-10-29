"""Independently verify logistic/Wald, grouped-binomial and optimizer values.

Uses only this fixture, NumPy and SciPy; the GLM is refit by Newton scoring,
not by statsmodels or MiniJMP. Wald intervals are formed on eta and mapped
through the logistic link. The optimizer domain is exactly [-1, 1].
"""
from hashlib import sha256
import json
import math
from pathlib import Path
from statistics import NormalDist

import numpy as np


ROOT = Path(__file__).resolve().parent
CHECKS = 0
LEVELS = {"90%": 0.90, "95%": 0.95, "99%": 0.99}
COVARIANCE = [
    [0.04, 0.008, -0.004, 0.002],
    [0.008, 0.0241, 0.0037, -0.0026],
    [-0.004, 0.0037, 0.0157, 0.0022],
    [0.002, -0.0026, 0.0022, 0.011125],
]
X0 = [1.0, 0.5, -0.25, 0.125]
MANUAL_INPUTS = {
    "rsm_linear": [0.2, 1.0, -0.8, 0.4],
    "negative_eta": [-0.2, -0.8, 0.4, -0.3],
    "near_one": [5.0, 0.5, -0.4, 0.2],
    "near_zero": [-5.0, -0.5, 0.4, -0.2],
}


def check(condition, label):
    global CHECKS
    CHECKS += 1
    if not condition:
        raise AssertionError(label)


def equal(actual, expected, label):
    check(actual == expected, f"{label}: {actual!r} != {expected!r}")


def close(actual, expected, label, *, rtol=2e-12, atol=2e-14):
    global CHECKS
    left, right = np.asarray(actual, dtype=float), np.asarray(expected, dtype=float)
    if left.shape != right.shape:
        raise AssertionError(f"{label}: shape {left.shape} != {right.shape}")
    matches = np.isclose(left, right, rtol=rtol, atol=atol)
    CHECKS += max(1, left.size)
    if not np.all(matches):
        index = tuple(np.argwhere(~matches)[0]) if left.ndim else ()
        raise AssertionError(
            f"{label}{index}: {left[index]!r} != {right[index]!r}"
        )


def logistic(value):
    value = float(value)
    if value >= 0:
        return 1.0 / (1.0 + math.exp(-value))
    exp_value = math.exp(value)
    return exp_value / (1.0 + exp_value)


def logistic_array(values):
    values = np.asarray(values, dtype=float)
    result = np.empty_like(values)
    positive = values >= 0
    result[positive] = 1.0 / (1.0 + np.exp(-values[positive]))
    exp_values = np.exp(values[~positive])
    result[~positive] = exp_values / (1.0 + exp_values)
    return result


def verify_manual(data):
    normal = NormalDist()
    equal(data["confidence_levels"], LEVELS, "manual confidence levels")
    equal(data["method"]["coefficient_order"], ["Intercept", "A", "B", "C"],
          "RSM linear coefficient order")
    for name, beta_values in MANUAL_INPUTS.items():
        case = data[name]
        close(case["beta"], beta_values, f"{name} beta", rtol=0, atol=0)
        close(case["covariance"], COVARIANCE, f"{name} covariance", rtol=0, atol=0)
        close(case["x0"], X0, f"{name} x0", rtol=0, atol=0)
        beta = np.asarray(beta_values)
        covariance = np.asarray(COVARIANCE)
        x0 = np.asarray(X0)
        np.linalg.cholesky(covariance)
        check(True, f"{name} covariance positive definite")
        eta = float(x0 @ beta)
        probability = logistic(eta)
        variance = float(x0 @ covariance @ x0.T)
        se_eta = math.sqrt(variance)
        close(case["eta"], eta, f"{name} eta")
        close(case["probability"], probability, f"{name} probability")
        close(case["variance_eta"], variance, f"{name} variance")
        close(case["se_eta"], se_eta, f"{name} SE eta")
        close(case["delta_se_probability"], probability * (1 - probability) * se_eta,
              f"{name} delta SE probability")

        equal(set(case["intervals"]), set(LEVELS), f"{name} interval levels")
        for label, confidence in LEVELS.items():
            interval = case["intervals"][label]
            z_two = normal.inv_cdf((1 + confidence) / 2)
            z_one = normal.inv_cdf(confidence)
            lower_two, upper_two = eta - z_two * se_eta, eta + z_two * se_eta
            lower_one, upper_one = eta - z_one * se_eta, eta + z_one * se_eta
            close(interval["two_sided"]["eta"], [lower_two, upper_two],
                  f"{name} {label} two-sided eta")
            close(interval["two_sided"]["probability"],
                  [logistic(lower_two), logistic(upper_two)],
                  f"{name} {label} two-sided probability")
            close(interval["one_sided_lower"]["eta_bound"], lower_one,
                  f"{name} {label} lower eta bound")
            close(interval["one_sided_lower"]["probability_interval"],
                  [logistic(lower_one), 1.0], f"{name} {label} lower interval")
            close(interval["one_sided_upper"]["eta_bound"], upper_one,
                  f"{name} {label} upper eta bound")
            close(interval["one_sided_upper"]["probability_interval"],
                  [0.0, logistic(upper_one)], f"{name} {label} upper interval")

    representatives = data["logit_representatives"]
    for eta in (-7.0, 0.0, 7.0):
        close(representatives[str(eta)], logistic(eta), f"eta={eta} probability")
    p_low, p_mid, p_high = (representatives[str(value)] for value in (-7.0, 0.0, 7.0))
    check(0 < p_low < 0.001, "eta=-7 probability is near zero")
    check(p_mid == 0.5, "eta=0 probability is one half")
    check(0.999 < p_high < 1, "eta=7 probability is near one")
    lower, upper = data["rsm_linear"]["intervals"]["95%"]["two_sided"]["probability"]
    center = data["rsm_linear"]["probability"]
    check(not math.isclose(center - lower, upper - center, rel_tol=1e-5),
          "RSM transformed 95% interval is asymmetric")
    check(data["near_zero"]["probability"] < 0.01, "near-zero fitted probability")
    check(data["near_one"]["probability"] > 0.99, "near-one fitted probability")


def fit_grouped_binomial(design, events, trials):
    beta = np.zeros(design.shape[1])
    for _ in range(100):
        probability = logistic_array(design @ beta)
        weights = trials * probability * (1 - probability)
        information = design.T @ (weights[:, None] * design)
        score = design.T @ (events - trials * probability)
        step = np.linalg.solve(information, score)
        beta += step
        if np.max(np.abs(step)) < 1e-12:
            break
    else:
        raise AssertionError("independent grouped-binomial Newton fit did not converge")
    probability = logistic_array(design @ beta)
    weights = trials * probability * (1 - probability)
    covariance = np.linalg.inv(design.T @ (weights[:, None] * design))
    return beta, covariance, probability


def verify_grouped_glm(data):
    source = data["source"]
    equal(source["dataset"], "statsmodels.datasets.star98", "GLM source dataset")
    equal(source["predictors"], ["LOWINC", "PTRATIO", "AVYRSEXP"], "GLM predictors")
    design = np.asarray(data["design"], dtype=float)
    events = np.asarray(data["events"], dtype=int)
    trials = np.asarray(data["trials"], dtype=int)
    equal(design.shape, (303, 4), "GLM design shape")
    equal(events.shape, (303,), "GLM events shape")
    equal(trials.shape, (303,), "GLM trials shape")
    close(design[:, 0], np.ones(303), "GLM intercept")
    close(design[0], [1.0, 3.43973, 2.171025, 1.470646], "GLM first design row")
    equal(events[:5].tolist(), [452, 144, 337, 395, 8], "GLM first events")
    equal(trials[:5].tolist(), [807, 184, 571, 573, 65], "GLM first trials")
    check(bool(np.all(events >= 0) and np.all(events <= trials) and np.all(trials > 0)),
          "GLM grouped counts are valid")
    equal(int(np.linalg.matrix_rank(design)), 4, "GLM design full rank")

    coefficients, covariance, probabilities = fit_grouped_binomial(design, events, trials)
    expected = data["expected"]
    close(expected["coefficients"], coefficients,
          "GLM coefficients versus independent Newton fit", rtol=2e-8, atol=2e-10)
    close(expected["covariance"], covariance,
          "GLM covariance versus inverse observed information", rtol=2e-8, atol=2e-10)
    close(expected["probabilities"], probabilities,
          "GLM probabilities versus independent fit", rtol=2e-8, atol=2e-10)
    check(bool(np.all((probabilities > 0) & (probabilities < 1))),
          "GLM predicted probabilities are interior")


def eta(x):
    return 0.2 + x - x * x


def probability(x):
    return logistic(eta(x))


def verify_optimizer(data):
    equal(data["domain"], [-1.0, 1.0], "optimizer domain")
    expected_x = [-1.0, 0.5, 1.0]
    candidates = data["direct_extrema"]["candidates"]
    close([item["x"] for item in candidates], expected_x, "analytic candidates")
    for item in candidates:
        close(item["eta"], eta(item["x"]), f"candidate eta at {item['x']}")
        close(item["probability"], probability(item["x"]),
              f"candidate probability at {item['x']}")
    close(data["direct_extrema"]["minimum"]["x"], -1.0, "analytic minimum x")
    close(data["direct_extrema"]["maximum"]["x"], 0.5, "analytic maximum x")

    target = data["target_probability"]
    close(target["probability"], 0.57, "target probability")
    target_eta = math.log(0.57 / 0.43)
    discriminant = 1.8 - 4 * target_eta
    roots = [(1 - math.sqrt(discriminant)) / 2,
             (1 + math.sqrt(discriminant)) / 2]
    close(target["eta_target"], target_eta, "target eta")
    close(target["roots"], roots, "target roots")
    close(target["root_probabilities"], [0.57, 0.57], "target root probabilities")
    check(all(-1 <= root <= 1 for root in roots), "target roots lie in domain")

    desirability = data["desirability"]
    low, high, x = desirability["lower"], desirability["upper"], desirability["example_x"]
    p = probability(x)
    raw = min(1.0, max(0.0, (p - low) / (high - low)))
    close(desirability["example_probability"], p, "desirability example probability")
    close(desirability["raw_desirability"], raw, "raw desirability")
    for weight in (0.5, 1, 2):
        close(desirability["weights"][str(weight)], raw ** weight,
              f"desirability weight {weight}")

    plateau = desirability["maximum_platform"]
    threshold = high
    threshold_eta = math.log(threshold / (1 - threshold))
    discriminant = 1.8 - 4 * threshold_eta
    limits = [(1 - math.sqrt(discriminant)) / 2,
              (1 + math.sqrt(discriminant)) / 2]
    close(plateau["probability_threshold"], threshold, "plateau probability threshold")
    close(plateau["eta_threshold"], threshold_eta, "plateau eta threshold")
    close(plateau["interval"], limits, "maximum desirability interval")
    close(plateau["maximum_desirability"], 1.0, "maximum desirability")
    close([probability(bound) for bound in limits], [threshold, threshold],
          "plateau boundary probabilities")
    check(limits[0] < 0.5 < limits[1], "plateau contains quadratic vertex")
    modes = data["desirability_modes"]
    max_case = modes["maximize"]
    close(max_case["value"], ((max_case["probability"] - max_case["lower"])
                               / (max_case["target"] - max_case["lower"]))
          ** max_case["weight"], "maximize desirability formula")
    min_case = modes["minimize"]
    close(min_case["value"], 1.0 if min_case["probability"] <= min_case["target"]
          else ((min_case["upper"] - min_case["probability"])
                / (min_case["upper"] - min_case["target"])) ** min_case["weight"],
          "minimize desirability formula")
    for name in ("target_lower", "target_upper", "target_outside"):
        case = modes[name]
        if case["probability"] <= case["lower"] or case["probability"] >= case["upper"]:
            expected = 0.0
        elif case["probability"] <= case["target"]:
            expected = ((case["probability"] - case["lower"])
                        / (case["target"] - case["lower"])) ** case["weight"]
        else:
            expected = ((case["upper"] - case["probability"])
                        / (case["upper"] - case["target"])) ** case["weight"]
        close(case["value"], expected, f"{name} desirability formula")
    check(data["solver_note"].find("not a global-optimum proof") >= 0,
          "heuristic solver scope is stated")


def verify():
    reference_path = ROOT / "reference.json"
    payload = reference_path.read_bytes()
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    entry = manifest["files"]["reference.json"]
    digest = sha256(payload).hexdigest()
    equal(len(payload), entry["bytes"], "reference byte count")
    equal(digest, entry["sha256"], "reference SHA-256")
    data = json.loads(payload.decode("utf-8"))
    equal(data["schema_version"], 1, "schema version")
    verify_manual(data["manual"])
    verify_grouped_glm(data["grouped_glm"])
    verify_optimizer(data["optimizer"])
    return CHECKS, digest, len(data["grouped_glm"]["events"])


if __name__ == "__main__":
    count, digest, rows = verify()
    print(f"{count} independent checks passed; grouped GLM rows={rows}; SHA-256={digest}")
