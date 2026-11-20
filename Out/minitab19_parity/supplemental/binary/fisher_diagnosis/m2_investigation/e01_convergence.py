"""Run the two E01 BRSREG settings, or replay their captured evidence offline."""
import csv
import json
from pathlib import Path
import sys

import numpy as np
from scipy.special import expit

from investigate_m2 import (BINARY, FOCUS, OUT, TERMS, compare, information_for,
                           read_csv, solve_covariance, source_hashes)

sys.path.insert(0, str(BINARY))
from verify import MinitabSession, analysis_command, native_rows, run_worker

CASE = "BIN-RSM"
SETTINGS = ("1e-10", "1e-12")
NATIVE = OUT / "e01_native_convergence.json"


def capture(path):
    frozen = json.loads((BINARY / "minitab_results.json").read_text(encoding="utf-8"))[CASE]
    inputs = read_csv(BINARY / "bin_rsm_input.csv")
    for row in inputs:
        for name in ("events", "trials"):
            row[name] = int(row[name])
    before = source_hashes()
    session = MinitabSession()
    results = {}
    try:
        for index, tolerance in enumerate(SETTINGS):
            if index:
                session.new_project()
            session.execute(frozen["design_command"], f"E01 {tolerance} design")
            factors, rows = native_rows(session, tuple("ABC"), inputs)
            baseline = frozen["design_rows"]
            assert len(rows) == len(baseline) == 14
            assert all(all(row[k] == old[k] for k in row)
                       for row, old in zip(rows, baseline, strict=True))
            responses = {name: session.add_column(name, [row[name] for row in rows])
                         for name in ("events", "trials")}
            for name, column in responses.items():
                assert session.column_values(column) == [row[name] for row in rows]
            storage = {name: session.add_column(label) for name, label in
                       (("fits", "Fit"), ("coefficients", "Coef"), ("se", "SECoef"))}
            command = analysis_command(CASE, factors, responses, storage)
            assert command == frozen["analysis_command"]
            command = command.replace("CTOLERANCE 1e-10;", f"CTOLERANCE {tolerance};")
            output = session.execute(command, f"E01 {tolerance} fit")
            results[tolerance] = {
                "command": command, "output": output, "rows": rows,
                **{name: session.column_values(column) for name, column in storage.items()},
                "M1": session.read_matrix("M1"), "M2": session.read_matrix("M2"),
            }
            assert not str(session.app.LastError or "").strip()
    finally:
        session.release()
    assert before == source_hashes()
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump({"version": session.version, "app_path": session.app_path,
                   "process_path": session.process_path, "runs": results,
                   "commands_and_output": session.raw}, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def replay(path):
    native = json.loads(path.read_text(encoding="utf-8"))
    assert native["version"] == "19.1.0.1"
    frozen = json.loads((BINARY / "minitab_results.json").read_text(encoding="utf-8"))[CASE]
    repaired = {row["term"]: row for row in read_csv(OUT.parent / "repaired_comparison.csv")
                if row["case_id"] == CASE and row["statistic"] == "wald_z"}
    assert set(repaired) == set(FOCUS)
    aligned = read_csv(OUT / "aligned_rows.csv")
    order = [int(row["minitab_design_row"]) - 1 for row in aligned]
    states = read_csv(OUT / "irls_trace.csv")
    comparisons = []
    baseline = native["runs"][SETTINGS[0]]
    for tolerance in SETTINGS:
        run = native["runs"][tolerance]
        assert run["M1"] == frozen["matrix"]
        assert run["command"] == frozen["analysis_command"].replace(
            "CTOLERANCE 1e-10;", f"CTOLERANCE {tolerance};")
        for row, old in zip(run["rows"], frozen["design_rows"], strict=True):
            assert all(row[key] == old[key] for key in row)
        for name, frozen_name in (("coefficients", "coefficients"), ("fits", "fits"),
                                  ("se", "standard_errors"), ("M2", "xpw_inverse")):
            current = np.array(run[name])
            for reference, values in (("frozen", frozen[frozen_name]), ("new baseline", baseline[name])):
                comparisons.append({"tolerance": tolerance, "metric": f"max |{name} − {reference}|",
                                    "absolute_error": np.max(np.abs(current - values))})
        x = np.asarray(run["M1"])[order]
        n = np.array([run["rows"][i]["trials"] for i in order])
        p = np.array(run["fits"])[order]
        beta = np.array(run["coefficients"])
        se = np.array(run["se"])
        m2 = np.array(run["M2"])
        assert x.shape == (14, 10) and np.linalg.matrix_rank(x) == 10
        assert np.array_equal(np.sqrt(m2.diagonal()), se)
        np.testing.assert_allclose(expit(x @ beta), p, rtol=0, atol=1e-15)
        _, info, weighted = information_for(x, n, p)
        covariance = solve_covariance(info, weighted, "cholesky")
        delta = m2 - covariance
        print(tolerance, "max M2−V, A*C variance, A*C row max, inverse residual:",
              np.max(np.abs(delta)), delta[8, 8], np.max(np.abs(delta[8])),
              np.linalg.norm(info @ m2 - np.eye(10), ord=np.inf))
        for metric, value in (("max |M2−V|", np.max(np.abs(delta))),
                              ("|M2−V| at A*C variance", abs(delta[8, 8])),
                              ("max |M2−V| across A*C row and column",
                               max(np.max(np.abs(delta[8])), np.max(np.abs(delta[:, 8])))),
                              ("||I M2−identity||_inf", np.linalg.norm(info @ m2 - np.eye(10), ord=np.inf))):
            comparisons.append({"tolerance": tolerance, "metric": metric, "absolute_error": value})
        for row in states:
            weights = np.array(json.loads(row["probabilities_current"]))
            _, state_info, state_weighted = information_for(x, n, weights)
            state_cov = solve_covariance(state_info, state_weighted, "cholesky")
            comparisons.append({"tolerance": tolerance, "metric": "IRLS state",
                                "term": row["state"], "absolute_error": np.max(np.abs(m2-state_cov))})
        for j, term in enumerate(TERMS):
            if term not in FOCUS:
                continue
            z = beta[j] / se[j]
            local_z = float(repaired[term]["minijmp_value"])
            status, absolute, relative = compare(local_z, z, 1e-9, 1e-9)
            comparisons.append({"tolerance": tolerance, "metric": "Wald z", "term": term,
                                "minitab": z, "minijmp": local_z, "absolute_error": absolute,
                                "relative_error": relative, "status": status})
    fields = ("tolerance", "metric", "term", "minitab", "minijmp", "absolute_error",
              "relative_error", "status")
    return comparisons, fields


if __name__ == "__main__":
    import os
    if sys.argv[1:2] == ["--com-worker"]:
        capture(Path(os.environ["MINIJMP_E01_OUTPUT"]))
    elif sys.argv[1:2] == ["--capture"]:
        path = Path(sys.argv[2]).resolve()
        if path.exists():
            raise FileExistsError(path)
        os.environ["MINIJMP_E01_OUTPUT"] = str(path)
        run_worker(Path(__file__), "--com-worker")
    else:
        rows, fields = replay(NATIVE)
        with (OUT / "e01_comparison.csv").open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
