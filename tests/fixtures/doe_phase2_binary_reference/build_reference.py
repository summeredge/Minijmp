"""Build independent logistic/Wald and grouped-binomial reference values.

The hand cases use x @ beta, x @ V @ x.T and inverse-logit Wald bounds.
The optimizer example is analytic on [-1, 1]. Star98 is fitted with the
statsmodels grouped-binomial GLM API; no MiniJMP modules are imported.
"""
from hashlib import sha256
import json
import math
from pathlib import Path

import numpy as np
import scipy
import statsmodels.api as sm
from scipy.special import expit
from scipy.stats import norm


ROOT = Path(__file__).resolve().parent
LEVELS = {"90%": 0.90, "95%": 0.95, "99%": 0.99}
COVARIANCE = [
    [0.04, 0.008, -0.004, 0.002],
    [0.008, 0.0241, 0.0037, -0.0026],
    [-0.004, 0.0037, 0.0157, 0.0022],
    [0.002, -0.0026, 0.0022, 0.011125],
]
X0 = [1.0, 0.5, -0.25, 0.125]
MANUAL_INPUTS = {
    "rsm_linear": {"beta": [0.2, 1.0, -0.8, 0.4],
                   "covariance": COVARIANCE, "x0": X0},
    "negative_eta": {"beta": [-0.2, -0.8, 0.4, -0.3],
                     "covariance": COVARIANCE, "x0": X0},
    "near_one": {"beta": [5.0, 0.5, -0.4, 0.2],
                 "covariance": COVARIANCE, "x0": X0},
    "near_zero": {"beta": [-5.0, -0.5, 0.4, -0.2],
                  "covariance": COVARIANCE, "x0": X0},
}


def manual_case(inputs):
    beta = np.asarray(inputs["beta"], dtype=float)
    covariance = np.asarray(inputs["covariance"], dtype=float)
    x0 = np.asarray(inputs["x0"], dtype=float)
    eta = float(x0 @ beta)
    variance = float(x0 @ covariance @ x0.T)
    se_eta = math.sqrt(variance)
    probability = float(expit(eta))
    intervals = {}
    for label, confidence in LEVELS.items():
        z_two = float(norm.ppf((1 + confidence) / 2))
        z_one = float(norm.ppf(confidence))
        lower_two, upper_two = eta - z_two * se_eta, eta + z_two * se_eta
        lower_one, upper_one = eta - z_one * se_eta, eta + z_one * se_eta
        intervals[label] = {
            "two_sided": {
                "eta": [lower_two, upper_two],
                "probability": [float(expit(lower_two)), float(expit(upper_two))],
            },
            "one_sided_lower": {
                "eta_bound": lower_one,
                "probability_interval": [float(expit(lower_one)), 1.0],
            },
            "one_sided_upper": {
                "eta_bound": upper_one,
                "probability_interval": [0.0, float(expit(upper_one))],
            },
        }
    return {
        **inputs,
        "eta": eta,
        "probability": probability,
        "variance_eta": variance,
        "se_eta": se_eta,
        "delta_se_probability": probability * (1 - probability) * se_eta,
        "intervals": intervals,
    }


def grouped_glm():
    data = sm.datasets.star98.load_pandas().data
    predictors = ["LOWINC", "PTRATIO", "AVYRSEXP"]
    raw_x = data[predictors].to_numpy(dtype=float)
    design = np.column_stack((np.ones(len(data)), raw_x / 10.0))
    events = np.rint(data["NABOVE"].to_numpy(dtype=float)).astype(int)
    failures = np.rint(data["NBELOW"].to_numpy(dtype=float)).astype(int)
    trials = events + failures
    fitted = sm.GLM(
        np.column_stack((events, failures)), design,
        family=sm.families.Binomial(),
    ).fit(maxiter=200, tol=1e-10)
    return {
        "source": {
            "dataset": "statsmodels.datasets.star98",
            "description": "303 California unified school district grouped counts",
            "response": {"events": "NABOVE", "failures": "NBELOW"},
            "predictors": predictors,
            "design_transform": "[1, LOWINC/10, PTRATIO/10, AVYRSEXP/10]",
            "row_order": "dataset order, zero-based",
            "statsmodels_version": sm.__version__,
        },
        "design": design.tolist(),
        "events": events.tolist(),
        "trials": trials.tolist(),
        "expected": {
            "coefficients": np.asarray(fitted.params).tolist(),
            "covariance": np.asarray(fitted.cov_params()).tolist(),
            "probabilities": np.asarray(fitted.fittedvalues).tolist(),
        },
    }


def optimizer_example():
    eta = lambda x: 0.2 + x - x * x
    probability = lambda x: float(expit(eta(x)))
    candidates = []
    for x in (-1.0, 0.5, 1.0):
        candidates.append({"x": x, "eta": eta(x), "probability": probability(x)})

    target_probability = 0.57
    target_eta = math.log(target_probability / (1 - target_probability))
    target_discriminant = 1.8 - 4 * target_eta
    target_roots = [
        (1 - math.sqrt(target_discriminant)) / 2,
        (1 + math.sqrt(target_discriminant)) / 2,
    ]

    desirability_low, desirability_high, example_x = 0.4, 0.6, 0.0
    example_p = probability(example_x)
    raw = min(1.0, max(0.0, (example_p - desirability_low)
                              / (desirability_high - desirability_low)))
    plateau_eta = math.log(desirability_high / (1 - desirability_high))
    plateau_discriminant = 1.8 - 4 * plateau_eta
    plateau = [
        (1 - math.sqrt(plateau_discriminant)) / 2,
        (1 + math.sqrt(plateau_discriminant)) / 2,
    ]
    desirability_modes = {
        "maximize": {
            "probability": 0.55, "lower": 0.4, "target": 0.6,
            "weight": 2.0, "value": ((0.55 - 0.4) / (0.6 - 0.4)) ** 2,
        },
        "minimize": {
            "probability": 0.55, "target": 0.6, "upper": 0.8,
            "weight": 2.0, "value": 1.0,
        },
        "target_lower": {
            "probability": 0.4, "lower": 0.3, "target": 0.5,
            "upper": 0.8, "weight": 2.0,
            "value": ((0.4 - 0.3) / (0.5 - 0.3)) ** 2,
        },
        "target_upper": {
            "probability": 0.65, "lower": 0.3, "target": 0.5,
            "upper": 0.8, "weight": 2.0,
            "value": ((0.8 - 0.65) / (0.8 - 0.5)) ** 2,
        },
        "target_outside": {
            "probability": 0.2, "lower": 0.3, "target": 0.5,
            "upper": 0.8, "weight": 2.0, "value": 0.0,
        },
    }
    return {
        "domain": [-1.0, 1.0],
        "eta": "0.2 + x - x^2",
        "direct_extrema": {
            "candidates": candidates,
            "minimum": candidates[0],
            "maximum": candidates[1],
            "analytic_basis": "eta is concave; eta'=1-2x has the sole stationary point x=0.5",
        },
        "target_probability": {
            "probability": target_probability,
            "eta_target": target_eta,
            "roots": target_roots,
            "root_probabilities": [probability(x) for x in target_roots],
        },
        "desirability": {
            "definition": "D=(clip((p-lower)/(upper-lower), 0, 1))^weight",
            "lower": desirability_low,
            "upper": desirability_high,
            "example_x": example_x,
            "example_probability": example_p,
            "raw_desirability": raw,
            "weights": {str(weight): raw ** weight for weight in (0.5, 1, 2)},
            "maximum_platform": {
                "probability_threshold": desirability_high,
                "eta_threshold": plateau_eta,
                "interval": plateau,
                "maximum_desirability": 1.0,
            },
        },
        "desirability_modes": desirability_modes,
        "solver_note": "These are analytic references; a heuristic solver result is not a global-optimum proof.",
    }


def build():
    manual = {
        "confidence_levels": LEVELS,
        "method": {
            "coefficient_order": ["Intercept", "A", "B", "C"],
            "eta": "x0 @ beta",
            "variance_eta": "x0 @ covariance @ x0.T",
            "delta_se_probability": "p*(1-p)*SE_eta",
            "intervals": "symmetric Wald bounds on eta transformed by expit; one-sided intervals are [L,1] or [0,U]",
            "covariance_domain": "symmetric positive definite 4x4 matrix in the RSM linear case",
        },
        **{name: manual_case(inputs) for name, inputs in MANUAL_INPUTS.items()},
        "logit_representatives": {
            str(eta): float(expit(eta)) for eta in (-7.0, 0.0, 7.0)
        },
    }
    return {
        "schema_version": 1,
        "provenance": {
            "purpose": "independent binary probability and response-optimization oracle",
            "production_imports": [],
            "generator_libraries": {
                "statsmodels": sm.__version__,
                "numpy": np.__version__,
                "scipy": scipy.__version__,
            },
            "limits": [
                "Star98 regeneration depends on the statsmodels dataset resource and library version.",
                "Floating-point GLM values are frozen for the recorded versions; cross-version regeneration is not guaranteed byte-identical.",
                "The optimizer oracle covers only the stated one-factor quadratic and desirability definition.",
            ],
        },
        "manual": manual,
        "grouped_glm": grouped_glm(),
        "optimizer": optimizer_example(),
    }


def main():
    payload = (json.dumps(build(), ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
    (ROOT / "reference.json").write_bytes(payload)
    manifest = {
        "source": "build_reference.py; hand-specified Wald/optimizer cases and statsmodels Star98 GLM",
        "production_imports": [],
        "files": {
            "reference.json": {
                "bytes": len(payload),
                "sha256": sha256(payload).hexdigest(),
            }
        },
    }
    manifest_payload = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    (ROOT / "manifest.json").write_bytes(manifest_payload)
    print(manifest["files"]["reference.json"]["sha256"])


if __name__ == "__main__":
    main()
