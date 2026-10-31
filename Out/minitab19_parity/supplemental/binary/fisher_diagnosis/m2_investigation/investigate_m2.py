"""Rebuild BIN-RSM Fisher matrices from frozen exports; never invokes Minitab."""
import ast
import csv
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.special import expit


ROOT = Path(__file__).resolve().parents[6]
BINARY = ROOT / "Out/minitab19_parity/supplemental/binary"
DIAG = BINARY / "fisher_diagnosis"
OUT = Path(__file__).resolve().parent
TERMS = ("截距", "A", "B", "C", "A²", "B²", "C²", "A*B", "A*C", "B*C")
FOCUS = ("A", "A²", "B²", "A*C")
SOURCE_PATHS = (
    "Out/minitab19_parity/supplemental/binary/bin_rsm_input.csv",
    "Out/minitab19_parity/supplemental/binary/minitab_results.json",
    "Out/minitab19_parity/supplemental/binary/minijmp_results.json",
    "Out/minitab19_parity/supplemental/binary/comparison.csv",
    "Out/minitab19_parity/supplemental/binary/session_commands.txt",
    "Out/minitab19_parity/supplemental/binary/minitab_raw.txt",
    "Out/minitab19_parity/supplemental/binary/verify.py",
    "Out/minitab19_parity/supplemental/binary/acceptance.md",
    "Out/minitab19_parity/supplemental/binary/fisher_diagnosis/fisher_diagnosis.csv",
    "Out/minitab19_parity/supplemental/binary/fisher_diagnosis/fisher_diagnosis.py",
    "Out/minitab19_parity/supplemental/binary/fisher_diagnosis/acceptance.md",
    "Out/minitab19_parity/supplemental/binary/fisher_diagnosis/repair_acceptance.md",
    "Out/minitab19_parity/supplemental/binary/fisher_diagnosis/repaired_comparison.csv",
    "Out/minitab19_parity/supplemental/binary/fisher_diagnosis/repaired_comparison.py",
    "Out/minitab19_parity/supplemental/supplemental_summary.csv",
    "Out/minitab19_parity/supplemental/supplemental_acceptance.md",
)


def key(row):
    return row["point_key"], int(row.get("occurrence", 1))


def read_csv(path):
    with path.open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def write_csv(path, rows, fields):
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def x_from_settings(settings):
    a, b, c = (float(settings[name]) for name in ("A", "B", "C"))
    return np.array((1, a, b, c, a*a, b*b, c*c, a*b, a*c, b*c), dtype=float)


def information_for(x, trials, probabilities):
    weights = trials * probabilities * (1.0 - probabilities)
    info = x.T @ (weights[:, None] * x)
    weighted_x = np.sqrt(weights)[:, None] * x
    return weights, info, weighted_x


def solve_covariance(info, weighted_x, method):
    identity = np.eye(info.shape[0])
    if method == "cholesky":
        lower = np.linalg.cholesky(info)
        return np.linalg.solve(lower.T, np.linalg.solve(lower, identity))
    if method == "solve":
        return np.linalg.solve(info, identity)
    if method == "qr":
        _, upper = np.linalg.qr(weighted_x, mode="reduced")
        return np.linalg.solve(upper, np.linalg.solve(upper.T, identity))
    if method == "svd":
        _, singular_values, right = np.linalg.svd(weighted_x, full_matrices=False)
        return (right.T * (1.0 / singular_values**2)) @ right
    raise AssertionError(method)


def compare(value, reference, atol, rtol):
    value, reference = float(value), float(reference)
    error = abs(value - reference)
    relative = error / abs(reference) if reference != 0 else (0.0 if error == 0 else float("inf"))
    return ("PASS" if error <= atol or relative <= rtol else "FAIL"), error, relative


def source_hashes():
    return {
        rel: hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()
        for rel in SOURCE_PATHS
    }


def json_vector(values):
    return json.dumps([float(value) for value in values], separators=(",", ":"), allow_nan=False)


def f(value):
    return format(float(value), ".17g")


def main():
    hashes_before = source_hashes()
    mini = json.loads((BINARY / "minijmp_results.json").read_text(encoding="utf-8"))["BIN-RSM"]
    mt = json.loads((BINARY / "minitab_results.json").read_text(encoding="utf-8"))["BIN-RSM"]
    inputs = read_csv(BINARY / "bin_rsm_input.csv")
    original = read_csv(BINARY / "comparison.csv")
    repaired = read_csv(DIAG / "repaired_comparison.csv")
    session_command = " ".join((BINARY / "session_commands.txt").read_text(encoding="utf-8").split())
    expected_terms = "TERMS C5 C6 C7 C5*C5 C6*C6 C7*C7 C5*C6 C5*C7 C6*C7"
    assert expected_terms in session_command

    input_by_key = {key(row): row for row in inputs}
    mt_rows = mt["design_rows"]
    mini_by_key = {key(row): row for row in mini["rows"]}
    assert len(input_by_key) == len(inputs) == len(mt_rows) == len(mini_by_key) == 14
    assert len({key(row) for row in mt_rows}) == len(mt_rows)
    assert set(input_by_key) == {key(row) for row in mt_rows} == set(mini_by_key)
    for mini_row in mini["rows"]:
        assert np.array_equal(
            np.asarray(mini["matrix"][int(mini_row["run_order"]) - 1], dtype=float),
            np.asarray(mini_row["matrix"], dtype=float),
        )
    assert tuple(mini["column_names"]) == TERMS
    assert tuple(row["term"] for row in mini["coefficients"]) == TERMS
    assert len(mt["matrix"]) == len(mt["fits"]) == len(mt_rows)
    assert len(mt["coefficients"]) == len(TERMS)
    assert len(mt["standard_errors"]) == len(TERMS)

    x_rows, events, trials = [], [], []
    p_minitab, p_minijmp = [], []
    aligned_rows = []
    for mt_index, mt_row in enumerate(mt_rows):
        row_key = key(mt_row)
        input_row = input_by_key[row_key]
        mini_row = mini_by_key[row_key]
        xrow = x_from_settings(ast.literal_eval(input_row["settings"]))
        mt_x = np.asarray(mt["matrix"][mt_index], dtype=float)
        mini_x = np.asarray(mini_row["matrix"], dtype=float)
        event_count, trial_count = int(input_row["events"]), int(input_row["trials"])
        assert event_count <= trial_count and trial_count > 0
        assert (int(mt_row["events"]), int(mt_row["trials"])) == (event_count, trial_count)
        assert (int(mini_row["events"]), int(mini_row["trials"])) == (event_count, trial_count)
        np.testing.assert_array_equal(mt_x, xrow)
        np.testing.assert_array_equal(np.asarray(mt_row["matrix"], dtype=float), xrow)
        np.testing.assert_array_equal(mini_x, xrow)
        assert float(mt["fits"][mt_index]) == float(mt_row["fit"])

        x_rows.append(xrow)
        events.append(event_count)
        trials.append(trial_count)
        p_minitab.append(float(mt["fits"][mt_index]))
        p_minijmp.append(float(mini_row["fit"]))
        aligned_rows.append({
            "point_key": row_key[0],
            "occurrence": row_key[1],
            "input_standard_order": int(input_row["standard_order"]),
            "minitab_design_row": mt_index + 1,
            "minitab_standard_order": int(mt_row["standard_order"]),
            "minitab_run_order": int(mt_row["run_order"]),
            "events": event_count,
            "trials": trial_count,
            "fit_minitab_direct": float(mt["fits"][mt_index]),
            "fit_from_minitab_beta": None,
            "fit_minijmp_final": float(mini_row["fit"]),
            "weight_minitab_fits": None,
            "weight_minitab_beta": None,
            "weight_minijmp_final": None,
            **{f"x_{term}": value for term, value in zip(TERMS, xrow)},
        })

    x = np.asarray(x_rows, dtype=float)
    events = np.asarray(events, dtype=float)
    trials = np.asarray(trials, dtype=float)
    beta_minitab = np.asarray(mt["coefficients"], dtype=float)
    beta_minijmp = np.asarray([row["coefficient"] for row in mini["coefficients"]], dtype=float)
    se_minitab_direct = np.asarray(mt["standard_errors"], dtype=float)
    m2 = np.asarray(mt["xpw_inverse"], dtype=float)
    fits_direct = np.asarray(p_minitab, dtype=float)
    fits_beta = expit(x @ beta_minitab)
    fits_minijmp = np.asarray(p_minijmp, dtype=float)
    assert x.shape == (14, 10) and m2.shape == (10, 10)
    assert np.linalg.matrix_rank(x) == 10
    assert np.max(np.abs(fits_direct - fits_beta)) < 2e-16
    assert np.max(np.abs(fits_direct - fits_minijmp)) < 2e-16
    assert np.array_equal(np.sqrt(np.diag(m2)), se_minitab_direct)
    assert np.max(np.abs(m2 - m2.T)) == 0.0
    for index, row in enumerate(aligned_rows):
        row["fit_from_minitab_beta"] = float(fits_beta[index])
        row["weight_minitab_fits"] = float(trials[index] * fits_direct[index] * (1.0 - fits_direct[index]))
        row["weight_minitab_beta"] = float(trials[index] * fits_beta[index] * (1.0 - fits_beta[index]))
        row["weight_minijmp_final"] = float(trials[index] * fits_minijmp[index] * (1.0 - fits_minijmp[index]))

    original_z = {
        row["term"]: row for row in original
        if row["case_id"] == "BIN-RSM" and row["statistic"] == "wald_z"
    }
    repaired_z = {
        row["term"]: row for row in repaired
        if row["case_id"] == "BIN-RSM" and row["statistic"] == "wald_z"
    }
    assert set(original_z) == set(TERMS)
    assert set(repaired_z) == set(FOCUS)
    assert all(original_z[term]["status"] == "FAIL" for term in FOCUS)
    assert all(repaired_z[term]["status"] == "FAIL" for term in FOCUS)
    native_se_m2 = np.sqrt(np.diag(m2))
    native_z = beta_minitab / native_se_m2
    np.testing.assert_allclose(
        native_z,
        np.asarray([float(original_z[term]["minitab_value"]) for term in TERMS]),
        rtol=0,
        atol=2e-15,
    )

    candidates = []

    def add_candidate(name, probabilities, source, method, state=None, step_inf=None):
        weights, info, weighted_x = information_for(x, trials, probabilities)
        covariance = solve_covariance(info, weighted_x, method)
        delta = m2 - covariance
        ij = np.unravel_index(np.argmax(np.abs(delta)), delta.shape)
        candidate = {
            "name": name,
            "source": source,
            "method": method,
            "state": state,
            "step_inf": step_inf,
            "information": info,
            "covariance": covariance,
            "max_abs": float(np.abs(delta[ij])),
            "max_i": int(ij[0]),
            "max_j": int(ij[1]),
            "relative_at_max": float(abs(delta[ij]) / max(abs(m2[ij]), abs(covariance[ij]))),
            "global_relative": float(np.max(np.abs(delta)) / np.max(np.abs(m2))),
            "frobenius": float(np.linalg.norm(delta, ord="fro")),
            "spectral": float(np.linalg.norm(delta, ord=2)),
            "condition_info": float(np.linalg.cond(info)),
            "condition_weighted_x": float(np.linalg.cond(weighted_x)),
            "candidate_residual_inf": float(np.linalg.norm(info @ covariance - np.eye(10), ord=np.inf)),
            "m2_residual_inf": float(np.linalg.norm(info @ m2 - np.eye(10), ord=np.inf)),
            "asymmetry": float(np.max(np.abs(covariance - covariance.T))),
            "p_max_abs_vs_minitab_fits": float(np.max(np.abs(probabilities - fits_direct))),
        }
        candidates.append(candidate)
        return candidate

    fits_candidate = add_candidate("FITS_DIRECT_Cholesky", fits_direct, "Minitab FITS (DIRECT)", "cholesky")
    add_candidate("BETA_EXPIT_Cholesky", fits_beta, "expit(M1 × Minitab beta)", "cholesky")
    add_candidate("MINIJMP_FINAL_P_Cholesky", fits_minijmp, "MiniJMP archived final p", "cholesky")
    for method in ("solve", "qr", "svd"):
        add_candidate(f"FITS_DIRECT_{method.upper()}", fits_direct, "Minitab FITS (DIRECT)", method)

    beta_state = np.zeros(10, dtype=float)
    irls_trace = []
    irls_candidates = {}
    for state in range(20):
        probabilities = expit(x @ beta_state)
        weights, info, weighted_x = information_for(x, trials, probabilities)
        score = x.T @ (events - trials * probabilities)
        beta_step = np.linalg.solve(info, score)
        step_inf = float(np.max(np.abs(beta_step)))
        beta_after = beta_state + beta_step
        probabilities_after = expit(x @ beta_after)
        candidate = add_candidate(
            f"IRLS_BETA_{state}", probabilities, f"offline Newton state beta_{state}",
            "cholesky", state=state, step_inf=step_inf,
        )
        irls_candidates[state] = candidate
        irls_trace.append({
            "state": state,
            "weight_state_definition": "p(beta_state) before the Newton update",
            "beta_current": json_vector(beta_state),
            "probabilities_current": json_vector(probabilities),
            "weights_current": json_vector(weights),
            "score_inf": float(np.max(np.abs(score))),
            "newton_step_inf": step_inf,
            "beta_after_update": json_vector(beta_after),
            "probabilities_after_update": json_vector(probabilities_after),
            "weights_after_update": json_vector(
                trials * probabilities_after * (1.0 - probabilities_after)
            ),
            "candidate_max_abs_m2_minus_v": candidate["max_abs"],
            "candidate_max_location": f"{TERMS[candidate['max_i']]} × {TERMS[candidate['max_j']]}",
            "candidate_frobenius_norm": candidate["frobenius"],
            "candidate_m2_inverse_residual_inf": candidate["m2_residual_inf"],
        })
        if step_inf <= 1e-14:
            beta_state = beta_after
            break
        beta_state = beta_after
    else:
        raise AssertionError("offline Newton reference did not converge")
    assert np.max(np.abs(beta_state - beta_minitab)) < 2e-14
    assert len(irls_trace) >= 2
    for before, after in zip(irls_trace, irls_trace[1:]):
        assert before["beta_after_update"] == after["beta_current"]
        assert before["probabilities_after_update"] == after["probabilities_current"]
        assert before["weights_after_update"] == after["weights_current"]
    previous_state = len(irls_trace) - 2

    focus_index = {term: TERMS.index(term) for term in FOCUS}
    for term, index in focus_index.items():
        assert abs(float(repaired_z[term]["minijmp_value"]) -
                   beta_minijmp[index] / np.sqrt(candidates[2]["covariance"][index, index])) < 2e-12

    matrix_rows = []
    for candidate in candidates:
        covariance = candidate["covariance"]
        for i, row_term in enumerate(TERMS):
            for j, column_term in enumerate(TERMS):
                diagonal = i == j
                row = {
                    "candidate": candidate["name"],
                    "probability_source": candidate["source"],
                    "solver": candidate["method"],
                    "irls_state": "" if candidate["state"] is None else candidate["state"],
                    "newton_step_inf": "" if candidate["step_inf"] is None else candidate["step_inf"],
                    "matrix_row": i + 1,
                    "matrix_column": j + 1,
                    "row_term": row_term,
                    "column_term": column_term,
                    "information_value": float(candidate["information"][i, j]),
                    "m2_value": float(m2[i, j]),
                    "candidate_covariance": float(covariance[i, j]),
                    "m2_minus_candidate": float(m2[i, j] - covariance[i, j]),
                    "absolute_element_difference": float(abs(m2[i, j] - covariance[i, j])),
                    "relative_element_difference": float(
                        abs(m2[i, j] - covariance[i, j]) /
                        max(abs(m2[i, j]), abs(covariance[i, j]))
                    ) if max(abs(m2[i, j]), abs(covariance[i, j])) else 0.0,
                    "candidate_max_abs_difference": candidate["max_abs"],
                    "candidate_relative_at_max": candidate["relative_at_max"],
                    "candidate_global_relative": candidate["global_relative"],
                    "candidate_frobenius_norm": candidate["frobenius"],
                    "candidate_spectral_norm": candidate["spectral"],
                    "information_condition_number": candidate["condition_info"],
                    "weighted_design_condition_number": candidate["condition_weighted_x"],
                    "candidate_inverse_residual_inf": candidate["candidate_residual_inf"],
                    "m2_inverse_residual_inf": candidate["m2_residual_inf"],
                    "candidate_asymmetry_max": candidate["asymmetry"],
                    "candidate_p_max_abs_vs_minitab_fits": candidate["p_max_abs_vs_minitab_fits"],
                }
                if diagonal:
                    reference = original_z[row_term]
                    candidate_se = float(np.sqrt(covariance[i, i]))
                    candidate_minijmp_z = float(beta_minijmp[i] / candidate_se)
                    status, error, relative = compare(
                        candidate_minijmp_z, float(reference["minitab_value"]),
                        float(reference["absolute_tolerance"]), float(reference["relative_tolerance"]),
                    )
                    row.update({
                        "native_beta": float(beta_minitab[i]),
                        "minijmp_beta": float(beta_minijmp[i]),
                        "archived_m2_variance": float(m2[i, i]),
                        "archived_m2_se": float(native_se_m2[i]),
                        "minitab_direct_se": float(se_minitab_direct[i]),
                        "m2_se_minus_direct_se": float(native_se_m2[i] - se_minitab_direct[i]),
                        "candidate_variance": float(covariance[i, i]),
                        "m2_minus_candidate_variance": float(m2[i, i] - covariance[i, i]),
                        "candidate_se": candidate_se,
                        "m2_minus_candidate_se": float(native_se_m2[i] - candidate_se),
                        "native_z_from_m2": float(native_z[i]),
                        "native_z_from_direct_se": float(beta_minitab[i] / se_minitab_direct[i]),
                        "candidate_z_using_native_beta": float(beta_minitab[i] / candidate_se),
                        "candidate_native_beta_z_minus_m2": float(beta_minitab[i] / candidate_se - native_z[i]),
                        "candidate_z_using_minijmp_beta": candidate_minijmp_z,
                        "candidate_minijmp_z_minus_m2": float(candidate_minijmp_z - native_z[i]),
                        "candidate_minijmp_z_abs_error": error,
                        "candidate_minijmp_z_relative_error": relative,
                        "candidate_minijmp_z_status": status,
                        "archived_original_z_status": reference["status"],
                        "repaired_minijmp_z": repaired_z.get(row_term, {}).get("minijmp_value", ""),
                        "repaired_z_status": repaired_z.get(row_term, {}).get("status", ""),
                    })
                matrix_rows.append(row)

    matrix_fields = list(matrix_rows[0])
    write_csv(OUT / "covariance_comparison.csv", matrix_rows, matrix_fields)
    alignment_fields = list(aligned_rows[0])
    write_csv(OUT / "aligned_rows.csv", aligned_rows, alignment_fields)
    trace_fields = list(irls_trace[0])
    write_csv(OUT / "irls_trace.csv", irls_trace, trace_fields)

    method_candidates = [
        candidate for candidate in candidates
        if candidate["source"] == "Minitab FITS (DIRECT)"
    ]
    solver_spread = max(
        float(np.max(np.abs(left["covariance"] - right["covariance"])))
        for left in method_candidates for right in method_candidates
    )
    endpoint = fits_candidate
    prior = irls_candidates[previous_state]
    candidate_by_name = {candidate["name"]: candidate for candidate in candidates}

    def diagonal_row(candidate_name, term):
        return next(
            row for row in matrix_rows
            if row["candidate"] == candidate_name and row["row_term"] == term
            and row["row_term"] == row["column_term"]
        )

    def fmt_sci(value):
        return f"{float(value):.12e}"

    focus_lines = []
    for term in FOCUS:
        ref, current = original_z[term], repaired_z[term]
        focus_lines.append(
            f"| {term} | {f(ref['minitab_value'])} | {f(current['minijmp_value'])} | "
            f"{fmt_sci(float(current['minijmp_value']) - float(ref['minitab_value']))} | "
            f"{f(current['absolute_error'])} | {f(current['relative_error'])} | {current['status']} |"
        )

    diag_lines = []
    for term in TERMS:
        end_row = diagonal_row(endpoint["name"], term)
        prev_row = diagonal_row(prior["name"], term)
        diag_lines.append(
            f"| {term} | {f(end_row['archived_m2_variance'])} | "
            f"{fmt_sci(end_row['m2_minus_candidate_variance'])} | "
            f"{fmt_sci(end_row['m2_minus_candidate_se'])} | "
            f"{fmt_sci(prev_row['m2_minus_candidate_variance'])} | "
            f"{fmt_sci(prev_row['m2_minus_candidate_se'])} |"
        )

    candidate_lines = []
    for candidate in candidates:
        location = f"{TERMS[candidate['max_i']]} × {TERMS[candidate['max_j']]}"
        candidate_lines.append(
            f"| {candidate['name']} | {candidate['source']} / {candidate['method']} | "
            f"{fmt_sci(candidate['max_abs'])} | {location} | "
            f"{fmt_sci(candidate['relative_at_max'])} | {fmt_sci(candidate['global_relative'])} | "
            f"{fmt_sci(candidate['frobenius'])} | {fmt_sci(candidate['candidate_residual_inf'])} |"
        )

    solver_lines = []
    for candidate in method_candidates:
        spread_from_chol = float(np.max(np.abs(
            candidate["covariance"] - candidate_by_name["FITS_DIRECT_Cholesky"]["covariance"]
        )))
        solver_lines.append(
            f"| {candidate['method']} | {fmt_sci(spread_from_chol)} | "
            f"{fmt_sci(candidate['candidate_residual_inf'])} | "
            f"{fmt_sci(candidate['asymmetry'])} |"
        )

    irls_lines = []
    for trace_row in irls_trace:
        candidate = irls_candidates[int(trace_row["state"])]
        z_deltas = []
        for term in FOCUS:
            i = focus_index[term]
            z = beta_minijmp[i] / np.sqrt(candidate["covariance"][i, i])
            target = float(original_z[term]["minitab_value"])
            z_deltas.append(fmt_sci(z - target))
        irls_lines.append(
            f"| {trace_row['state']} | {fmt_sci(trace_row['newton_step_inf'])} | "
            f"{fmt_sci(candidate['max_abs'])} | {fmt_sci(candidate['frobenius'])} | "
            + " | ".join(z_deltas) + " |"
        )

    fits_max = float(np.max(np.abs(fits_direct - fits_beta)))
    mini_p_max = float(np.max(np.abs(fits_direct - fits_minijmp)))
    x_rank = int(np.linalg.matrix_rank(x))
    m2_symmetry = float(np.max(np.abs(m2 - m2.T)))
    m2_se_error = float(np.max(np.abs(native_se_m2 - se_minitab_direct)))
    m2_endpoint_residual = endpoint["m2_residual_inf"]
    previous_improvement = endpoint["max_abs"] / prior["max_abs"]
    solver_orders_smaller = endpoint["max_abs"] / solver_spread
    current_result_rows = [repaired_z[term] for term in FOCUS]
    current_status_counts = {
        status: sum(row["status"] == status for row in current_result_rows)
        for status in ("PASS", "FAIL")
    }
    assert current_status_counts == {"PASS": 0, "FAIL": 4}
    assert len(matrix_rows) == len(candidates) * 100
    assert len(aligned_rows) == 14 and len(irls_trace) >= 2
    assert solver_spread < 1e-15
    assert prior["max_abs"] < endpoint["max_abs"]
    assert prior["max_abs"] > solver_spread * 1e5

    report = [
        "# BIN-RSM 原生 M2 与终点 Fisher 的离线数值溯源",
        "",
        "日期：2026-10-31（Asia/Shanghai）  ",
        "范围：仅复核冻结 BIN-RSM 归档；未启动 Minitab/COM、未运行 `binary/verify.py`、未调用生产拟合算法。",
        "",
        "## 结论",
        "",
        f"- 原生归档 M2 与终点 Fisher 协方差的最大元素差为 **{f(endpoint['max_abs'])}**，位置 **{TERMS[endpoint['max_i']]} × {TERMS[endpoint['max_j']]}**；该元素的相对差为 **{f(endpoint['relative_at_max'])}**，以 M2 最大绝对元素归一的矩阵相对差为 **{f(endpoint['global_relative'])}**。Frobenius 差范数为 `{f(endpoint['frobenius'])}`。",
        f"- 按同一终点 FITS 信息矩阵，Cholesky/solve/加权 QR/SVD 的协方差最大两两差仅 **{f(solver_spread)}**，约比 M2 偏差小 **{f(solver_orders_smaller)}** 倍；条件数为 `{f(endpoint['condition_info'])}`。标准双精度求解器差异不足以解释 M2 偏差。",
        f"- 从 beta=0 开始的离线 Newton 轨迹中，前一权重状态 beta_{previous_state} 的协方差与 M2 最大差为 `{f(prior['max_abs'])}`，比终点 Fisher 更接近约 `{f(previous_improvement)}` 倍；但仍比求解器间差异大约 `{f(prior['max_abs'] / solver_spread)}` 倍，且没有重现 M2。该轨迹不是 Minitab 内部日志，不能据此认定 Minitab 使用 beta_{previous_state} 权重。",
        "- 归档中的 4 项 BIN-RSM Wald z 在第二阶段修复结果中仍全部为 **FAIL**，原有 `abs_tol=rel_tol=1e-9` 不变。现有证据排除了普通线性求解舍入作为充分解释；权重取值时点有数值上的接近迹象，但**无法唯一归因 Minitab 内部实现，根因保留未知**。不建议据此修改 MiniJMP 终点 Fisher 生产算法。",
        "",
        "## 证据分层与对齐",
        "",
        "- **DIRECT（冻结归档）**：Minitab `matrix`（M1）、FITS、系数、SECOEFFICIENTS 与 `xpw_inverse`（M2）；MiniJMP 当前 JSON 的行、拟合概率和矩阵；输入 CSV 的 events/trials/settings；原比较及第二阶段修复比较。Minitab 命令顺序来自同目录 `session_commands.txt` 的 BRSREG `TERMS`。",
        "- **DERIVED（本脚本）**：按 `(point_key, occurrence)` 把 14 行输入、Minitab `design_rows`/M1/FITS 与 MiniJMP 行逐一配对。按 [1,A,B,C,A²,B²,C²,A×B,A×C,B×C] 重构 X，并与两个归档矩阵逐元素核对；counts 也逐行相等。详细行键、三个概率来源和 10 列 M1 见 `aligned_rows.csv`。",
        f"- 对齐结果：{len(aligned_rows)} 行；X 形状 `{x.shape[0]}×{x.shape[1]}`、rank `{x_rank}`；M1 对重构矩阵最大绝对差为 `0`。重复中心点保留 occurrence 1/2。Minitab FITS 与 `expit(X beta_Minitab)` 最大差 `{f(fits_max)}`；Minitab FITS 与 MiniJMP 归档最终 p 最大差 `{f(mini_p_max)}`。每行均使用 grouped-binomial events/trials（合计 trials=`{int(np.sum(trials))}`）。",
        f"- M2 对称性最大误差 `{f(m2_symmetry)}`；`sqrt(diag(M2))` 与 10 个直接归档 SE 逐项完全相同（最大差 `{f(m2_se_error)}`）。以 M2 对角 SE 派生的原生 z 与冻结 Minitab 比较值最大差不超过 `2e-15`。",
        "",
        "## M2 与终点 Fisher 及求解误差",
        "",
        "每个概率候选均使用 `wᵢ = trialsᵢ pᵢ(1-pᵢ)`、`I = XᵀWX`、`V = I⁻¹`。默认协方差用 Cholesky 两次三角求解；交叉方法分别对同一信息矩阵使用 `solve`、对加权设计矩阵做 QR 和 SVD。没有用显示舍入值。",
        "",
        "| 候选概率 / 权重来源 | 求解 | max_abs(M2−V) | 位置 | 该位置相对差 | max差/max_abs(M2) | Frobenius | solve_residual_inf |",
        "|---|---|---:|---|---:|---:|---:|---:|",
        *candidate_lines,
        "",
        "“该位置相对差”以该矩阵元素两边绝对值的较大者作分母；“max差/max|M2|”是整个矩阵按最大 M2 元素归一的相对差，避免近零非对角元导致逐元素相对误差失真。`||IV−I₁₀||∞` 是候选协方差求解残差的无穷范数。",
        "",
        f"在 Minitab FITS 的同一终点信息矩阵下，native M2 的 `||I M2−I₁₀||∞` 为 **{f(m2_endpoint_residual)}**，而各求解器自身残差如下：",
        "",
        "| 求解 | 相对 Cholesky 的 max_abs(ΔV) | solve_residual_inf | 协方差非对称 max |",
        "|---|---:|---:|---:|",
        *solver_lines,
        "",
        f"四种求解结果最大两两差 `{f(solver_spread)}`，信息矩阵条件数 `{f(endpoint['condition_info'])}`（加权设计矩阵条件数 `{f(endpoint['condition_weighted_x'])}`）。M2 对终点信息矩阵的残差远大于这些解法的残差，因此不能把差额归为常规双精度求解器舍入。",
        "",
        "## IRLS 权重状态候选（仅离线重建）",
        "",
        "以 beta₀=0 起步，每一状态先计算 p(betaₖ)、Wₖ 和候选协方差，再按 grouped-binomial Newton 步更新 betaₖ₊₁。`irls_trace.csv` 保留每态 beta、更新前后 p/W、步长与 M2 残差；更新后的状态协方差对应 `covariance_comparison.csv` 中下一 beta 状态的完整信息矩阵和协方差。其中 k=4 是收敛前一权重状态，k=5 已到终点。此处是 MiniJMP/离线参考重建，不是 Minitab 迭代日志。",
        "",
        "| 权重状态 k | Newton 步 max | max_abs(M2−Vₖ) | Frobenius | Δz A | Δz A² | Δz B² | Δz A*C |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|",
        *irls_lines,
        "",
        f"Δz 定义为该状态协方差配 MiniJMP beta 得到的 z 减去原生 M2 的 Minitab z。前态 k={previous_state} 的 p 与 Minitab FITS 最大差为 `{f(prior['p_max_abs_vs_minitab_fits'])}`；它在 M2 最大元素上更接近，但不等于 M2，残差也远超解法噪声。会话输出只记录 `ITERATION 200`、`CTOLERANCE 1e-10` 等命令/报告设置，没有 beta、逐轮 p 或逐轮 W，故无法验证 Minitab 的起始值、停止态或协方差计算时点。",
        "",
        "### 对角方差、SE 与 z 的误差传递",
        "",
        "| 项 | M2 方差 | M2−V（终点） | M2 SE−SE终点 | M2−V（IRLS前态） | M2 SE−SE前态 |",
        "|---|---:|---:|---:|---:|---:|",
        *diag_lines,
        "",
        "固定 beta 时，`z=beta/SE`，小误差满足 `Δz/z ≈ −0.5·ΔV/V`；因此方差的微小相对差会以约一半幅度传到 z 的相对差，而非证明系数或响应行错位。上表的 signed `M2−V`、SE 差与下表 z 差保留方向；逐项完整值和 10×10 协方差元素见 `covariance_comparison.csv`。",
        "",
        "## 原有四项 1e-9 验收状态",
        "",
        "| 项 | Minitab 原生 M2 z | MiniJMP 修复后终点 Fisher z | MiniJMP−Minitab | 归档绝对误差 | 归档相对误差 | 原状态 |",
        "|---|---:|---:|---:|---:|---:|---|",
        *focus_lines,
        "",
        "第二阶段验收中，原 16 项 FAIL 有 12 项修复通过，BIN-RSM 这 4 项仍为 FAIL。本调查未改冻结比较、第二阶段 CSV/报告、容差或七项 supplemental 汇总。IRLS 候选在某些项上可能满足数值门槛，只说明假设权重态的数值结果，不改变任何已归档验收状态。",
        "",
        "## 因果判断与后续",
        "",
        "- **已排除到何种程度**：行错配、M1 编码/列序差异、events/trials 错配、FITS 与 beta 响应概率不一致均被逐项核对排除；Cholesky、solve、QR、SVD 的普通双精度解法差异约为 1e-17 量级，远小于 M2 差值。",
        "- **仍未知**：前态权重候选比终点更接近 M2，但不在求解噪声内重现；现有证据不能把差异唯一归因于 Minitab 的权重取值时点，也不能判定其他未导出的内部数值处理。根因置信度：对“普通求解器舍入不足以解释”高；对“前态权重是 Minitab 根因”低/未证实。",
        "- **建议**：不修改当前终点 Fisher 生产实现，不放宽 1e-9；继续保留 4 项 FAIL。只有后续需要对 Minitab 内部来源作唯一归因或要求关闭这 4 项时，才值得另行获取可验证的原生迭代/权重证据；当前归档不能替代该证据。",
        "",
        "## 来源完整性与复跑",
        "",
        "脚本只读下列归档，并在执行前后核对 SHA-256；自检还断言行键、矩阵、SE、原 z、IRLS 收敛和输出行数。重跑命令（项目 Python）：",
        "",
        "```powershell",
        "& (Resolve-Path '.venv\\Scripts\\python.exe').Path -B 'Out\\minitab19_parity\\supplemental\\binary\\fisher_diagnosis\\m2_investigation\\investigate_m2.py'",
        "```",
        "",
        "| 冻结来源 | SHA-256 |",
        "|---|---|",
        *[f"| `{path}` | `{digest}` |" for path, digest in hashes_before.items()],
        "",
        "输出：`aligned_rows.csv`（14 行键、响应、概率和 M1），`covariance_comparison.csv`（每个候选的完整 10×10 M2−V、求解残差及对角 SE/z），`irls_trace.csv`（更新前后状态）。",
        "",
    ]
    report_path = OUT / "m2_investigation.md"
    report_path.write_text("\n".join(report), encoding="utf-8")

    assert source_hashes() == hashes_before
    with (OUT / "covariance_comparison.csv").open(newline="", encoding="utf-8-sig") as stream:
        assert sum(1 for _ in csv.DictReader(stream)) == len(matrix_rows)
    with (OUT / "aligned_rows.csv").open(newline="", encoding="utf-8-sig") as stream:
        assert sum(1 for _ in csv.DictReader(stream)) == 14
    with (OUT / "irls_trace.csv").open(newline="", encoding="utf-8-sig") as stream:
        assert sum(1 for _ in csv.DictReader(stream)) == len(irls_trace)
    assert report_path.is_file()

    print(json.dumps({
        "self_check": "PASS",
        "aligned_rows": len(aligned_rows),
        "matrix_candidates": len(candidates),
        "matrix_element_rows": len(matrix_rows),
        "irls_states": len(irls_trace),
        "native_m2_vs_endpoint_max_abs": endpoint["max_abs"],
        "native_m2_vs_previous_irls_max_abs": prior["max_abs"],
        "solver_pairwise_spread": solver_spread,
        "remaining_wald_z_status": current_status_counts,
        "source_hashes_unchanged": True,
        "outputs": [path.name for path in (report_path, OUT / "aligned_rows.csv", OUT / "covariance_comparison.csv", OUT / "irls_trace.csv")],
    }, ensure_ascii=True, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
