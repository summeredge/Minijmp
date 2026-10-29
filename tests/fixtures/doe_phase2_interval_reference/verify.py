"""Independently verify the frozen rational RSM reference using Fraction."""
import hashlib
import json
import itertools
from fractions import Fraction as F
from math import isclose, sqrt
from pathlib import Path


ROOT = Path(__file__).resolve().parent
CRITICAL = {
    (0.90, "two_sided"): 2.3533634348018264,
    (0.90, "lower"): 1.6377443536962095,
    (0.90, "upper"): 1.6377443536962095,
    (0.95, "two_sided"): 3.182446305284263,
    (0.95, "lower"): 2.3533634348018264,
    (0.95, "upper"): 2.3533634348018264,
    (0.99, "two_sided"): 5.840909309733352,
    (0.99, "lower"): 4.540702858471383,
    (0.99, "upper"): 4.540702858471383,
}


def product(left, right):
    return sum((a*b for a, b in zip(left, right)), F(0))


def inverse(matrix):
    n = len(matrix)
    rows = [list(row) + [F(i == j) for j in range(n)]
            for i, row in enumerate(matrix)]
    for j in range(n):
        pivot = next(i for i in range(j, n) if rows[i][j])
        rows[j], rows[pivot] = rows[pivot], rows[j]
        divisor = rows[j][j]
        rows[j] = [value/divisor for value in rows[j]]
        for i in range(n):
            if i == j:
                continue
            multiplier = rows[i][j]
            rows[i] = [value-multiplier*base
                       for value, base in zip(rows[i], rows[j])]
    return [row[n:] for row in rows]


def close(actual, expected):
    return isclose(float(actual), float(expected), rel_tol=2e-13, abs_tol=2e-13)


def main():
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    raw = (ROOT / manifest["reference"]).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == manifest["sha256"]
    result = json.loads(raw)
    points = [(F(a), F(b)) for a, b in itertools.product((-1, 0, 1), repeat=2)]
    x = [[F(1), a, b, a*a, b*b, a*b] for a, b in points]
    xt = [list(column) for column in zip(*x)]
    xtx = [[product(row, column) for column in xt] for row in xt]
    inv = inverse(xtx)
    y = [F(10)+2*a-b+3*a*a+4*b*b+a*b+(a*a-F(2, 3))*b
         for a, b in points]
    xty = [product(column, y) for column in xt]
    beta = [product(row, xty) for row in inv]
    residuals = [observed-product(row, beta) for row, observed in zip(x, y)]
    sse = sum((value*value for value in residuals), F(0))
    n, p, df = len(x), len(x[0]), len(x)-len(x[0])
    mse = sse/df
    x0 = [F(1), F(1, 2), F(1, 4), F(1, 4), F(1, 16), F(1, 8)]
    h0 = product(x0, [product(row, x0) for row in inv])
    prediction = product(x0, beta)
    assert (result["n"], result["p"], result["df"], result["pure_error_df"]) == (
        n, p, df, 0)
    assert result["points"] == [[float(a), float(b)] for a, b in points]
    assert all(close(a, b) for a, b in zip(result["coefficients"], beta))
    assert close(result["sse"], sse) and close(result["mse"], mse)
    assert close(result["prediction"], prediction) and close(result["h0"], h0)
    se_fit, se_prediction = sqrt(float(mse*h0)), sqrt(float(mse*(1+h0)))
    assert close(result["se_fit"], se_fit)
    assert close(result["se_prediction"], se_prediction)

    for (confidence, side), critical in CRITICAL.items():
        intervals = result["intervals"][f"{confidence:.2f}"][side]
        assert close(intervals["critical_value"], critical)
        m_ci, m_pi = critical*se_fit, critical*se_prediction
        ci = ([float(prediction-m_ci), float(prediction+m_ci)]
              if side == "two_sided" else
              [float(prediction-m_ci), None] if side == "lower" else
              [None, float(prediction+m_ci)])
        pi = ([float(prediction-m_pi), float(prediction+m_pi)]
              if side == "two_sided" else
              [float(prediction-m_pi), None] if side == "lower" else
              [None, float(prediction+m_pi)])
        assert all(a is None and b is None or close(a, b)
                   for a, b in zip(intervals["ci"], ci))
        assert all(a is None and b is None or close(a, b)
                   for a, b in zip(intervals["pi"], pi))

    for index, (row, residual) in enumerate(zip(x, residuals)):
        h = product(row, [product(column, row) for column in inv])
        remainder = 1-h
        deleted_sse = sse-residual*residual/remainder
        deleted_mse = deleted_sse/(df-1)
        studentized = (float(residual)/sqrt(float(deleted_mse*remainder))
                       if deleted_mse > 0 else None)
        expected = {
            "leverage": float(h),
            "standardized_residual": float(residual)/sqrt(float(mse*remainder)),
            "deleted_residual": float(residual/remainder),
            "studentized_residual": studentized,
            "cooks_distance": float(residual*residual/(p*mse)*h/(remainder*remainder)),
            "dfits": (studentized*sqrt(float(h/remainder))
                     if studentized is not None else None),
        }
        actual = result["diagnostics"][index]
        assert actual["run_id"] == f"R{index+1:05d}"
        assert actual["run_order"] == index+1
        for key, value in expected.items():
            if value is None:
                assert actual[key] is None
            else:
                assert close(actual[key], value)
    assert all(interval["two_sided"]["ci"][1] - interval["two_sided"]["ci"][0]
               <= interval["two_sided"]["pi"][1] - interval["two_sided"]["pi"][0]
               for interval in result["intervals"].values())
    print("RSM reference: 9 interval tails/confidences and 9 diagnostic rows passed")


if __name__ == "__main__":
    main()
