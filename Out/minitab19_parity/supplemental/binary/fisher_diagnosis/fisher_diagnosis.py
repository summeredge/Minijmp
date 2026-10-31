"""Offline final-Fisher check of the two archived binary DOE cases."""
import ast
import csv
import json
import math
from collections import Counter
from pathlib import Path
from statistics import NormalDist

import numpy as np
from scipy.special import expit

BASE = Path(__file__).resolve().parents[5] / "Out/minitab19_parity/supplemental/binary"
OUT = Path(__file__).with_name("fisher_diagnosis.csv")
CASES = {
    "BIN-FACTORIAL": ("bin_factorial_input.csv", ["截距", "A", "B", "A*B"]),
    "BIN-RSM": ("bin_rsm_input.csv", [
        "截距", "A", "B", "C", "A²", "B²", "C²", "A*B", "A*C", "B*C",
    ]),
}
FIELDS = [
    "case_id", "section", "term", "statistic", "minitab_reference_source",
    "minijmp_old_source", "old_status", "minijmp_old_value",
    "minitab_reference_value", "old_absolute_error", "old_relative_error",
    "minijmp_final_fisher_value", "minijmp_final_fisher_absolute_error",
    "minijmp_final_fisher_relative_error", "minijmp_final_fisher_status",
    "minitab_final_fisher_value", "minitab_final_fisher_absolute_error",
    "minitab_final_fisher_relative_error", "minitab_final_fisher_status",
    "absolute_tolerance", "relative_tolerance",
]


def key(row):
    return row["point_key"], int(row.get("occurrence", 1))


def xrow(case_id, settings):
    a, b = float(settings["A"]), float(settings["B"])
    if case_id == "BIN-FACTORIAL":
        return [1.0, a, b, a * b]
    c = float(settings["C"])
    return [1.0, a, b, c, a*a, b*b, c*c, a*b, a*c, b*c]


def fisher(x, n, p):
    info = x.T @ ((n * p * (1.0 - p))[:, None] * x)
    lower = np.linalg.cholesky(info)
    identity = np.eye(x.shape[1])
    covariance = np.linalg.solve(lower.T, np.linalg.solve(lower, identity))
    return covariance, info


def compare(value, target, atol, rtol):
    error = abs(value - target)
    relative = error / abs(target) if target else (0.0 if error == 0 else math.inf)
    # Existing comparisons pass when either stored tolerance is met.
    return ("PASS" if error <= atol or relative <= rtol else "FAIL", error, relative)


def wald_p(z):
    return math.erfc(abs(float(z)) / math.sqrt(2.0))

def metric(statistic, index, beta, se):
    z = beta / se
    if statistic in ('standard_error', 'minijmp_se_vs_fisher'):
        return float(se[index])
    if statistic == 'wald_z':
        return float(z[index])
    if statistic == 'wald_p':
        return wald_p(z[index])
    raise AssertionError(statistic)


def main():
    mini = json.loads((BASE / "minijmp_results.json").read_text(encoding="utf-8"))
    mt = json.loads((BASE / "minitab_results.json").read_text(encoding="utf-8"))
    with (BASE / "comparison.csv").open(
        newline="", encoding="utf-8-sig"
    ) as handle:
        comparisons = list(csv.DictReader(handle))
    failures = [r for r in comparisons if r["status"] == "FAIL"]
    expected = Counter({
        ("BIN-FACTORIAL", "coefficient", "standard_error"): 4,
        ("BIN-FACTORIAL", "independent_hessian", "minijmp_se_vs_fisher"): 4,
        ("BIN-FACTORIAL", "coefficient", "wald_z"): 2,
        ("BIN-FACTORIAL", "coefficient", "wald_p"): 2,
        ("BIN-RSM", "coefficient", "wald_z"): 4,
    })
    assert Counter((r["case_id"], r["section"], r["statistic"]) for r in failures) == expected

    results, report = {}, {}
    for case_id, (input_name, names) in CASES.items():
        with (BASE / input_name).open(newline="", encoding="utf-8-sig") as handle:
            inputs = sorted(csv.DictReader(handle), key=lambda r: int(r["standard_order"]))
        source = {key(r): r for r in inputs}
        mj_rows, mt_rows = mini[case_id]["rows"], mt[case_id]["design_rows"]
        mj, mti = {key(r): r for r in mj_rows}, {key(r): i for i, r in enumerate(mt_rows)}
        assert len(source) == len(inputs) == len(mj) == len(mti)
        assert set(source) == set(mj) == set(mti)
        assert mini[case_id]["column_names"] == names
        assert [r["term"] for r in mini[case_id]["coefficients"]] == names
        assert len(mt[case_id]["fits"]) == len(mt_rows)

        matrix, events, trials, p_mj, p_mt = [], [], [], [], []
        for row in inputs:
            k = key(row)
            expected_x = xrow(case_id, ast.literal_eval(row["settings"]))
            mrow, trow = mj[k], mt_rows[mti[k]]
            e, n = int(row["events"]), int(row["trials"])
            assert (mrow["events"], mrow["trials"]) == (e, n)
            assert (trow["events"], trow["trials"]) == (e, n)
            np.testing.assert_allclose(mrow["matrix"], expected_x, rtol=0, atol=0)
            if trow.get("matrix") is not None:
                np.testing.assert_allclose(trow["matrix"], expected_x, rtol=0, atol=0)
            assert abs(float(trow["fit"]) - float(mt[case_id]["fits"][mti[k]])) <= 2e-16
            matrix.append(expected_x)
            events.append(e)
            trials.append(n)
            p_mj.append(float(mrow["fit"]))
            p_mt.append(float(mt[case_id]["fits"][mti[k]]))

        x, n = np.asarray(matrix), np.asarray(trials, dtype=float)
        p_mj, p_mt = np.asarray(p_mj), np.asarray(p_mt)
        beta_mj = np.array([r["coefficient"] for r in mini[case_id]["coefficients"]])
        beta_mt = np.asarray(mt[case_id]["coefficients"], dtype=float)
        assert x.shape == (len(inputs), len(names))
        assert np.linalg.matrix_rank(x) == len(names)
        assert np.max(np.abs(expit(x @ beta_mj) - p_mj)) < 2e-14
        assert np.max(np.abs(expit(x @ beta_mt) - p_mt)) < 2e-14

        cov_mj, info_mj = fisher(x, n, p_mj)
        cov_mt, info_mt = fisher(x, n, p_mt)
        se_mj, se_mt = np.sqrt(np.diag(cov_mj)), np.sqrt(np.diag(cov_mt))
        z_mj, z_mt = beta_mj / se_mj, beta_mt / se_mt
        pval_mj = np.array([wald_p(z) for z in z_mj])
        pval_mt = np.array([wald_p(z) for z in z_mt])
        assert np.max(np.abs(info_mj @ cov_mj - np.eye(len(names)))) < 1e-12
        assert np.max(np.abs(info_mt @ cov_mt - np.eye(len(names)))) < 1e-12
        results[case_id] = (names, beta_mj, beta_mt, se_mj, se_mt, z_mj, z_mt, pval_mj, pval_mt)

        metric_pass, metric_fail, metric_error = Counter(), Counter(), Counter()
        for row in comparisons:
            if row["case_id"] != case_id or row["section"] != "coefficient":
                continue
            i, statistic = names.index(row["term"]), row["statistic"]
            value = {
                "estimate": beta_mj[i], "standard_error": se_mj[i],
                "wald_z": z_mj[i], "wald_p": pval_mj[i],
            }[statistic]
            status, error, _ = compare(
                float(value), float(row["minitab_value"]),
                float(row["absolute_tolerance"]), float(row["relative_tolerance"]),
            )
            metric_pass[statistic] += status == "PASS"
            metric_fail[statistic] += status == "FAIL"
            metric_error[statistic] = max(metric_error[statistic], error)

        prediction = []
        if "prediction_row" in mini[case_id]:
            fit = mini[case_id]["prediction"]
            x0 = np.asarray(mini[case_id]["prediction_row"])
            eta, se_eta = float(x0 @ beta_mj), math.sqrt(float(x0 @ cov_mj @ x0))
            critical = NormalDist().inv_cdf((1 + fit["confidence"]) / 2)
            values = {
                "eta_hat": eta, "se_eta": se_eta, "p_hat": float(expit(eta)),
                "ci_low": float(expit(eta - critical * se_eta)),
                "ci_high": float(expit(eta + critical * se_eta)),
            }
            for statistic, value in values.items():
                ref = next(r for r in comparisons if r["case_id"] == case_id
                           and r["section"] == "prediction" and r["statistic"] == statistic)
                status, error, relative = compare(
                    value, float(ref["minitab_value"]),
                    float(ref["absolute_tolerance"]), float(ref["relative_tolerance"]),
                )
                prediction.append((statistic, value, error, relative, status))
                assert status == "PASS"

        xpw_delta = None
        if mt[case_id].get("xpw_inverse") is not None:
            xpw_delta = float(np.max(np.abs(
                cov_mt - np.asarray(mt[case_id]["xpw_inverse"], dtype=float)
            )))
        prob_rows = [r for r in comparisons if r["case_id"] == case_id
                     and r["section"] == "run_statistics" and r["statistic"] == "probability"]
        assert all(r["status"] == "PASS" for r in prob_rows)
        report[case_id] = {
            "shape": list(x.shape), "rank": len(names), "columns": names,
            "max_p_reconstruction_error": [
                float(np.max(np.abs(expit(x @ beta_mj) - p_mj))),
                float(np.max(np.abs(expit(x @ beta_mt) - p_mt))),
            ],
            "max_source_p_difference": float(np.max(np.abs(p_mj - p_mt))),
            "condition_information": [
                float(np.linalg.cond(info_mj)), float(np.linalg.cond(info_mt)),
            ],
            "max_identity_residual": [
                float(np.max(np.abs(info_mj @ cov_mj - np.eye(len(names))))),
                float(np.max(np.abs(info_mt @ cov_mt - np.eye(len(names))))),
            ],
            "fisher_se_mj_p": se_mj.tolist(),
            "fisher_se_minitab_direct_p": se_mt.tolist(),
            "fisher_z_mj_p": z_mj.tolist(),
            "fisher_z_minitab_direct_p": z_mt.tolist(),
            "max_fisher_se_vs_minitab_direct_se": float(np.max(np.abs(
                se_mt - np.asarray(mt[case_id]["standard_errors"])
            ))),
            "max_fisher_cov_vs_minitab_xpw_inverse": xpw_delta,
            "coefficient_metric_pass": dict(metric_pass),
            "coefficient_metric_fail": dict(metric_fail),
            "coefficient_metric_max_abs_error": dict(metric_error),
            "unchanged_run_probability_passes": len(prob_rows),
            "prediction_checks": prediction,
        }

    rows = []
    for old in failures:
        case_id, stat = old["case_id"], old["statistic"]
        names, bm, bt, smj, smt, _, _, _, _ = results[case_id]
        i = names.index(old["term"])
        new_mj = metric(stat, i, bm, smj)
        new_mt = metric(stat, i, bt, smt)
        target = float(old["minitab_value"])
        atol, rtol = float(old["absolute_tolerance"]), float(old["relative_tolerance"])
        assert compare(float(old["minijmp_value"]), target, atol, rtol)[0] == old["status"]
        mj_status, mj_abs, mj_rel = compare(new_mj, target, atol, rtol)
        mt_status, mt_abs, mt_rel = compare(new_mt, target, atol, rtol)
        rows.append({
            "case_id": case_id, "section": old["section"], "term": old["term"],
            "statistic": stat, "minitab_reference_source": old["minitab_value_source"],
            "minijmp_old_source": old["minijmp_value_source"], "old_status": old["status"],
            "minijmp_old_value": old["minijmp_value"],
            "minitab_reference_value": old["minitab_value"],
            "old_absolute_error": old["absolute_error"],
            "old_relative_error": old["relative_error"],
            "minijmp_final_fisher_value": new_mj,
            "minijmp_final_fisher_absolute_error": mj_abs,
            "minijmp_final_fisher_relative_error": mj_rel,
            "minijmp_final_fisher_status": mj_status,
            "minitab_final_fisher_value": new_mt,
            "minitab_final_fisher_absolute_error": mt_abs,
            "minitab_final_fisher_relative_error": mt_rel,
            "minitab_final_fisher_status": mt_status,
            "absolute_tolerance": old["absolute_tolerance"],
            "relative_tolerance": old["relative_tolerance"],
        })

    assert len(rows) == 16
    expected_new = Counter({"PASS": 12, "FAIL": 4})
    assert Counter(r["minijmp_final_fisher_status"] for r in rows) == expected_new
    assert Counter(r["minitab_final_fisher_status"] for r in rows) == expected_new
    with OUT.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    with OUT.open(newline="", encoding="utf-8-sig") as handle:
        saved = list(csv.DictReader(handle))
    assert len(saved) == 16 and all(r["old_status"] == "FAIL" for r in saved)
    assert Counter(r["minijmp_final_fisher_status"] for r in saved) == expected_new
    print(json.dumps({
        "rows": len(saved),
        "final_fisher_status": dict(expected_new),
        "cases": report,
        "csv_self_check": "PASS",
    }, ensure_ascii=True, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()