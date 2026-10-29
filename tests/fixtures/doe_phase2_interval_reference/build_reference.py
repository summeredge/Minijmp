"""Build a rational RSM interval and influence reference without MiniJMP imports."""
import hashlib
import itertools
import json
from fractions import Fraction as F
from math import sqrt
from pathlib import Path


ROOT = Path(__file__).resolve().parent
TERMS = ("Intercept", "A", "B", "A^2", "B^2", "A*B")
T_CRITICAL = {
    "0.90": {"two_sided": 2.3533634348018264,
             "lower": 1.6377443536962095, "upper": 1.6377443536962095},
    "0.95": {"two_sided": 3.182446305284263,
             "lower": 2.3533634348018264, "upper": 2.3533634348018264},
    "0.99": {"two_sided": 5.840909309733352,
             "lower": 4.540702858471383, "upper": 4.540702858471383},
}


def dot(left, right):
    return sum((a * b for a, b in zip(left, right)), F(0))


def transpose(matrix):
    return [list(column) for column in zip(*matrix)]


def inverse(matrix):
    size = len(matrix)
    work = [list(row) + [F(int(i == j)) for j in range(size)]
            for i, row in enumerate(matrix)]
    for column in range(size):
        pivot = next(index for index in range(column, size)
                     if work[index][column] != 0)
        work[column], work[pivot] = work[pivot], work[column]
        scale = work[column][column]
        work[column] = [value / scale for value in work[column]]
        for row in range(size):
            if row == column:
                continue
            scale = work[row][column]
            work[row] = [value - scale * pivot_value
                         for value, pivot_value in zip(work[row], work[column])]
    return [row[size:] for row in work]


def number(value):
    return float(value)


def calculate():
    points = [(F(a), F(b)) for a, b in itertools.product((-1, 0, 1), repeat=2)]
    x = [[F(1), a, b, a*a, b*b, a*b] for a, b in points]
    residuals = [(a*a - F(2, 3)) * b for a, b in points]
    beta = [F(10), F(2), F(-1), F(3), F(4), F(1)]
    y = [dot(row, beta) + residual for row, residual in zip(x, residuals)]
    xt = transpose(x)
    information = [[dot(row, column) for column in xt] for row in xt]
    covariance_unscaled = inverse(information)
    xty = [dot(column, y) for column in xt]
    fitted_beta = [dot(row, xty) for row in covariance_unscaled]
    residuals = [observed - dot(row, fitted_beta)
                 for row, observed in zip(x, y)]
    sse = sum((value*value for value in residuals), F(0))
    n, p = len(x), len(x[0])
    df = n - p
    mse = sse / df

    prediction_point = (F(1, 2), F(1, 4))
    x0 = [F(1), prediction_point[0], prediction_point[1],
          prediction_point[0]**2, prediction_point[1]**2,
          prediction_point[0]*prediction_point[1]]
    covariance_row = [dot(row, x0) for row in covariance_unscaled]
    h0 = dot(x0, covariance_row)
    prediction = dot(x0, fitted_beta)
    se_fit = sqrt(float(mse*h0))
    se_prediction = sqrt(float(mse*(1+h0)))
    intervals = {}
    for confidence, tails in T_CRITICAL.items():
        intervals[confidence] = {}
        for side, critical in tails.items():
            ci_margin, pi_margin = critical*se_fit, critical*se_prediction
            ci = ([number(prediction-ci_margin), number(prediction+ci_margin)]
                  if side == "two_sided" else
                  [number(prediction-ci_margin), None] if side == "lower" else
                  [None, number(prediction+ci_margin)])
            pi = ([number(prediction-pi_margin), number(prediction+pi_margin)]
                  if side == "two_sided" else
                  [number(prediction-pi_margin), None] if side == "lower" else
                  [None, number(prediction+pi_margin)])
            intervals[confidence][side] = {
                "critical_value": critical, "ci": ci, "pi": pi,
            }

    diagnostics = []
    for index, (point, row, residual) in enumerate(zip(points, x, residuals), 1):
        h = dot(row, [dot(column, row) for column in covariance_unscaled])
        remainder = 1 - h
        deleted = residual / remainder
        standardized = float(residual) / sqrt(float(mse*remainder))
        deleted_sse = sse - residual*residual/remainder
        deleted_mse = deleted_sse/(df-1)
        cook = float(residual*residual/(p*mse) * h/(remainder*remainder))
        studentized = (float(residual) / sqrt(float(deleted_mse*remainder))
                       if deleted_mse > 0 else None)
        dfits = (studentized*sqrt(float(h/remainder))
                 if studentized is not None else None)
        diagnostics.append({
            "run_id": f"R{index:05d}", "run_order": index,
            "standard_order": index, "A": number(point[0]), "B": number(point[1]),
            "response": number(y[index-1]), "residual": number(residual),
            "leverage": number(h), "standardized_residual": standardized,
            "deleted_residual": number(deleted),
            "studentized_residual": studentized, "cooks_distance": cook,
            "dfits": dfits,
            "note": "" if studentized is not None else
                    "删除后残差均方不为正；学生化残差和 DFITS 不适用",
        })

    return {
        "schema_version": 1,
        "terms": list(TERMS),
        "n": n, "p": p, "df": df, "pure_error_df": 0,
        "points": [[number(a), number(b)] for a, b in points],
        "responses": [number(value) for value in y],
        "coefficients": [number(value) for value in fitted_beta],
        "sse": number(sse), "mse": number(mse),
        "prediction_point": [number(value) for value in prediction_point],
        "prediction": number(prediction), "h0": number(h0),
        "se_fit": se_fit, "se_prediction": se_prediction,
        "intervals": intervals, "diagnostics": diagnostics,
    }


def main():
    payload = json.dumps(calculate(), ensure_ascii=False, indent=2) + "\n"
    reference = ROOT / "reference.json"
    reference.write_text(payload, encoding="utf-8")
    digest = hashlib.sha256(reference.read_bytes()).hexdigest()
    (ROOT / "manifest.json").write_text(json.dumps({
        "reference": "reference.json", "sha256": digest,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"reference bytes={reference.stat().st_size} sha256={digest}")


if __name__ == "__main__":
    main()
