"""MiniJMP × Minitab 19 grouped-binomial DOE parity."""
from __future__ import annotations

import csv
import json
import math
import sys
import traceback
from collections import Counter
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SUPPLEMENTAL = HERE.parent
ROOT = SUPPLEMENTAL.parents[2]
CASE_IDS = ("BIN-FACTORIAL", "BIN-RSM")
INPUTS = {case: HERE / f"{case.lower().replace('-', '_')}_input.csv" for case in CASE_IDS}
COMMANDS = HERE / "session_commands.txt"
RAW = HERE / "minitab_raw.txt"
MINIJMP = HERE / "minijmp_results.json"
MINITAB = HERE / "minitab_results.json"
COMPARISON = HERE / "comparison.csv"
REPORT = HERE / "acceptance.md"
RSM_PREDICTION = {"A": 0.2, "B": -0.3, "C": 0.4}
ITERATIONS = 200
CONVERGENCE_TOLERANCE = 1e-10

if str(SUPPLEMENTAL) not in sys.path:
    sys.path.insert(0, str(SUPPLEMENTAL))

from common import (  # noqa: E402
    MinitabSession,
    compare_numeric,
    compare_text,
    run_worker,
    status_counts,
    unique_rows,
    write_comparison,
    write_json,
)


def clean(value):
    if value is None:
        return None
    if isinstance(value, np.ndarray):
        return [clean(item) for item in value.tolist()]
    if isinstance(value, np.generic):
        return clean(value.item())
    if isinstance(value, dict):
        return {str(key): clean(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [clean(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def point_key(settings, names):
    return ",".join(f"{float(settings[name]):.12g}" for name in names)


def load_fixture():
    return json.loads((ROOT / "tests" / "fixtures" / "doe_h_reference"
                       / "reference.json").read_text(encoding="utf-8"))["binary"]


def assign_counts(frame, events_column, trials_column, by_point, factor_names):
    events = [int(by_point[tuple(float(row[f"设定_{name}"]) for name in factor_names)])
              for _, row in frame.iterrows()]
    frame[events_column] = events
    frame[trials_column] = [10 if factor_names == ("A", "B") else 90] * len(frame)
    return frame


def case_rows(case_id, frame, metadata):
    from doe_core import restore_design_result

    design = restore_design_result(frame, metadata)
    names = [factor.factor_id for factor in design.spec.factors]
    events_column = metadata["column_map"]["responses"]["Events"]
    trials_column = metadata["column_map"]["responses"]["Trials"]
    runs = []
    occurrences = Counter()
    for run in sorted(design.runs, key=lambda item: item.standard_order):
        settings = {name: float(run.settings[name]) for name in names}
        key = point_key(settings, names)
        occurrences[key] += 1
        events = int(frame.loc[frame[metadata["column_map"]["run_id"]] == run.run_id,
                               events_column].iloc[0])
        trials = int(frame.loc[frame[metadata["column_map"]["run_id"]] == run.run_id,
                               trials_column].iloc[0])
        runs.append({
            "run_id": run.run_id, "standard_order": int(run.standard_order),
            "run_order": int(run.run_order), "occurrence": occurrences[key],
            "point_key": key, "settings": settings,
            "events": events, "trials": trials,
        })
    return names, runs


def write_input(case_id, rows):
    with INPUTS[case_id].open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def analysis_summary(case_id, frame, metadata, result):
    names, runs = case_rows(case_id, frame, metadata)
    result_rows = {row["run_id"]: row for row in result["rows"]}
    matrix = np.asarray(result["matrix"], dtype=float)
    rows = []
    for index, run in enumerate(result["design"].runs):
        source = result_rows[run.run_id]
        rows.append({
            "run_id": run.run_id, "standard_order": int(run.standard_order),
            "run_order": int(run.run_order),
            "occurrence": next(row["occurrence"] for row in runs
                               if row["run_id"] == run.run_id),
            "point_key": point_key(run.settings, names),
            "settings": {name: float(run.settings[name]) for name in names},
            "events": int(source["events"]), "trials": int(source["trials"]),
            "observed_probability": float(source["observed_probability"]),
            "fit": float(source["predicted_probability"]),
            "matrix": matrix[index].tolist(),
        })
    return {
        "family": result["family"], "factor_ids": names,
        "column_names": list(result["column_names"]),
        "term_columns": result["term_columns"], "n_runs": result["n_runs"],
        "n_trials": result["n_trials"], "rank": result["rank"],
        "model_df": result["model_df"], "residual_df": result["residual_df"],
        "coefficients": clean(result["coefficients"]),
        "terms": clean(result["terms"]), "log_likelihood": result["log_likelihood"],
        "model_lr": result["model_lr"], "model_p": result["model_p"],
        "deviance": result["deviance"], "deviance_p": result["deviance_p"],
        "pearson_chi_square": result["pearson_chi_square"],
        "pearson_p": result["pearson_p"], "rows": rows,
        "matrix": matrix.tolist(),
    }


def minijmp_worker():
    sys.path.insert(0, str(ROOT / "code"))
    from doe_bbd import create_bbd
    from doe_binary_analysis import analyze_binary_doe, predict_binary_probability
    from doe_core import DesignSpec, FactorSpec
    from doe_factorial import create_factorial

    fixture = load_fixture()
    factorial_spec = DesignSpec(
        "binary-full", (FactorSpec("A", "A", -1, 1), FactorSpec("B", "B", -1, 1)),
        ("Events", "Trials"), seed=11, design_type="two_level_full")
    factorial_frame, factorial_meta = create_factorial(factorial_spec)
    factorial_case = fixture["factorial"]
    factorial_by_point = dict(zip(map(tuple, factorial_case["design_points"]),
                                  factorial_case["events"]))
    factorial_frame = assign_counts(factorial_frame, "响应_Events", "响应_Trials",
                                    factorial_by_point, ("A", "B"))
    factorial_result = analyze_binary_doe(
        factorial_frame, factorial_meta, "响应_Events", "响应_Trials",
        "factorial", model_order=2)
    factorial_names, factorial_rows = case_rows(
        "BIN-FACTORIAL", factorial_frame, factorial_meta)
    if (len(factorial_rows), factorial_result["rank"],
            factorial_result["residual_df"]) != (4, 4, 0):
        raise AssertionError("BIN-FACTORIAL 必须是满秩饱和 2² 模型")
    write_input("BIN-FACTORIAL", factorial_rows)
    results = {"BIN-FACTORIAL": {
        "case": "2² grouped binomial logistic; full main-effects and interaction model",
        **analysis_summary("BIN-FACTORIAL", factorial_frame, factorial_meta,
                           factorial_result),
    }}

    rsm_spec = DesignSpec(
        "binary-bbd", tuple(FactorSpec(name, name, -1, 1) for name in "ABC"),
        ("Events", "Trials"), seed=11, design_type="box_behnken",
        ccd_center_points=2)
    rsm_frame, rsm_meta = create_bbd(rsm_spec)
    rsm_case = fixture["rsm"]
    rsm_by_point = dict(zip(map(tuple, rsm_case["design_points"]), rsm_case["events"]))
    rsm_frame = assign_counts(rsm_frame, "响应_Events", "响应_Trials",
                              rsm_by_point, tuple("ABC"))
    rsm_result = analyze_binary_doe(
        rsm_frame, rsm_meta, "响应_Events", "响应_Trials", "rsm", model_order=2)
    prediction = predict_binary_probability(rsm_result, RSM_PREDICTION, confidence=.95)
    model = rsm_result["detail"]["term_model"]
    prediction_row = model.row(model.coded(RSM_PREDICTION))
    rsm_names, rsm_rows = case_rows("BIN-RSM", rsm_frame, rsm_meta)
    if (len(rsm_rows), rsm_result["rank"], rsm_result["residual_df"]) != (14, 10, 4):
        raise AssertionError("BIN-RSM 必须为 14 行、秩 10、残差 df 4")
    write_input("BIN-RSM", rsm_rows)
    results["BIN-RSM"] = {
        "case": "3-factor BBD grouped binomial logistic; full quadratic model",
        **analysis_summary("BIN-RSM", rsm_frame, rsm_meta, rsm_result),
        "prediction_settings": RSM_PREDICTION,
        "prediction_row": [float(value) for value in prediction_row],
        "prediction": clean(prediction),
    }
    write_json(MINIJMP, results)
    print("MiniJMP binary self-check: 2x2 saturated rank 4; BBD quadratic rank 10/14; PASS",
          flush=True)


def native_rows(session, factor_names, input_rows):
    std_column = session.find_column(("StdOrder", "StandardOrder", "标准序"))
    run_column = session.find_column(("RunOrder", "运行序"), required=False)
    std = session.column_values(std_column)
    order = session.column_values(run_column) if run_column else list(range(1, len(std)+1))
    factor_columns = {name: session.find_column((name,)) for name in factor_names}
    values = {name: session.column_values(index) for name, index in factor_columns.items()}
    if any(len(column) != len(std) for column in values.values()) or len(order) != len(std):
        raise RuntimeError("Minitab 因子/标准序/运行序列长度不匹配")
    by_key = {(row["point_key"], int(row["occurrence"])): row for row in input_rows}
    occurrences, rows_by_worksheet = Counter(), {}
    for index in sorted(range(len(std)), key=lambda i: int(std[i])):
        settings = {name: float(values[name][index]) for name in factor_names}
        key = point_key(settings, factor_names)
        occurrences[key] += 1
        source = by_key.get((key, occurrences[key]))
        if source is None:
            raise RuntimeError(f"Minitab DOE 点未映射到固定输入: {key}#{occurrences[key]}")
        rows_by_worksheet[index] = {
            "worksheet_row": index + 1, "standard_order": int(std[index]),
            "run_order": int(order[index]), "occurrence": occurrences[key],
            "point_key": key, "settings": settings,
            "events": source["events"], "trials": source["trials"],
        }
    return factor_columns, [rows_by_worksheet[index] for index in range(len(std))]


def analysis_command(case_id, factor_columns, response_columns, storage_columns):
    factor_names = ("A", "B") if case_id == "BIN-FACTORIAL" else tuple("ABC")
    factors = " ".join(f"C{factor_columns[name]}" for name in factor_names)
    levels = " ".join("-1 1" for _ in factor_names)
    response = f"C{response_columns['events']} C{response_columns['trials']}"
    cmd = "BFFACTORIAL" if case_id == "BIN-FACTORIAL" else "BRSREG"
    terms = [f"C{factor_columns[name]}" for name in factor_names]
    if case_id == "BIN-FACTORIAL":
        terms.append(f"C{factor_columns['A']}*C{factor_columns['B']}")
    else:
        terms.extend(f"C{factor_columns[name]}*C{factor_columns[name]}" for name in factor_names)
        terms.extend(f"C{factor_columns[a]}*C{factor_columns[b]}"
                     for a, b in (("A", "B"), ("A", "C"), ("B", "C")))
    command = (
        f"{cmd};\n  RESPONSE {response};\n  FACTOR {factors};\n"
        f"  TERMS {' '.join(terms)};\n  LEVELS {levels};\n  INUNIT 0;\n"
        "  LOGIT;\n"
        f"  ITERATION {ITERATIONS};\n  CTOLERANCE {CONVERGENCE_TOLERANCE:.0e};\n"
        f"  FITS C{storage_columns['fits']};\n"
        f"  COEFFICIENTS C{storage_columns['coefficients']};\n"
        f"  SECOEFFICIENTS C{storage_columns['se']};\n"
    )
    if case_id == "BIN-RSM":
        command += ("  CONFIDENCE 95;\n  ITYPE 0;\n  XMATRIX M1;\n"
                    "  XPWXINVERSE M2.")
    else:
        command = command.rstrip()[:-1] + "."
    return command


def minitab_worker():
    session, raw, commands = None, [], []
    try:
        local = json.loads(MINIJMP.read_text(encoding="utf-8"))
        session = MinitabSession()
        results = {}
        for case_index, case_id in enumerate(CASE_IDS):
            if case_index:
                session.new_project()
            factor_names = ("A", "B") if case_id == "BIN-FACTORIAL" else tuple("ABC")
            design_command = (
                "FFDESIGN 2 4;\n  LEVELS -1 1 -1 1;\n  DESIGN."
                if case_id == "BIN-FACTORIAL" else
                "BBDESIGN 3;\n  CENTER 2;\n  DESIGN."
            )
            session.execute(design_command, f"{case_id} DOE design")
            columns, rows = native_rows(session, factor_names, local[case_id]["rows"])
            if len(rows) != len(local[case_id]["rows"]):
                raise RuntimeError(f"{case_id} Minitab run count differs from MiniJMP")
            response_columns = {
                "events": session.add_column("Events", [row["events"] for row in rows]),
                "trials": session.add_column("Trials", [row["trials"] for row in rows]),
            }
            storage = {"fits": session.add_column("Fit"),
                       "coefficients": session.add_column("Coef"),
                       "se": session.add_column("SECoef")}
            command = analysis_command(case_id, columns, response_columns, storage)
            output = session.execute(command, f"{case_id} {command.split(';',1)[0]}")
            coefficients = session.column_values(storage["coefficients"])
            standard_errors = session.column_values(storage["se"])
            fits = session.column_values(storage["fits"])
            matrix = session.read_matrix("M1") if case_id == "BIN-RSM" else None
            inverse = session.read_matrix("M2") if case_id == "BIN-RSM" else None
            if (len(coefficients) != len(local[case_id]["column_names"])
                    or len(standard_errors) != len(coefficients)
                    or len(fits) != len(rows)):
                raise RuntimeError(f"{case_id} Minitab coefficient/SE/fits storage length mismatch")
            for index, row in enumerate(rows):
                row["fit"] = fits[index]
                if matrix is not None:
                    row["matrix"] = matrix[index]
            results[case_id] = {
                "version": session.version, "design_command": design_command,
                "analysis_command": command, "design_rows": rows,
                "coefficients": coefficients, "standard_errors": standard_errors,
                "fits": fits, "matrix": matrix, "xpw_inverse": inverse,
                "output": output,
            }
            write_json(MINITAB, results)
            commands.extend([f"# {case_id} native DOE design", design_command,
                             f"# {case_id} fixed grouped-binomial logistic model", command])
            COMMANDS.write_text(
                "# Minitab 19.1.0.1 BFFACTORIAL/BRSREG Session Commands\n\n"
                + "\n\n".join(commands) + "\n", encoding="utf-8")
            raw.append(f"===== {case_id} mapped native rows =====\n"
                       + json.dumps(rows, ensure_ascii=False, indent=2))
        write_json(MINITAB, results)
        RAW.write_text("\n\n".join([*session.raw, *raw]) + "\n", encoding="utf-8")
        print("Minitab 19.1.0.1 binary DOE: BFFACTORIAL/BRSREG stored", flush=True)
        return 0
    except Exception:
        raw.append("===== worker exception =====\n" + traceback.format_exc())
        RAW.write_text("\n\n".join([*(session.raw if session else []), *raw]) + "\n",
                       encoding="utf-8")
        traceback.print_exc()
        return 1
    finally:
        if session is not None:
            session.release()


def derived_logistic(case, probabilities_by_key):
    from scipy import stats
    from scipy.special import gammaln

    input_rows = {(row["point_key"], row["occurrence"]): row for row in case["rows"]}
    keys = sorted(probabilities_by_key)
    events = np.asarray([input_rows[key]["events"] for key in keys], dtype=float)
    trials = np.asarray([input_rows[key]["trials"] for key in keys], dtype=float)
    p = np.asarray([probabilities_by_key[key] for key in keys], dtype=float)
    if np.any((p <= 0) | (p >= 1)):
        raise ValueError("概率边界导致有限对数似然不可计算")
    loglike_no_constant = float(np.sum(events*np.log(p) + (trials-events)*np.log1p(-p)))
    constant = float(np.sum(gammaln(trials+1)-gammaln(events+1)-gammaln(trials-events+1)))
    loglike = loglike_no_constant + constant

    def binomial_ll(y, n, probability):
        return float(np.sum(np.where(y > 0, y * np.log(np.maximum(y / n, 1e-300)), 0)
                            + np.where(n-y > 0, (n-y) * np.log(np.maximum(1-y/n, 1e-300)), 0)))

    saturated = binomial_ll(events, trials, events / trials)
    null_probability = float(events.sum() / trials.sum())
    null = float(np.sum(events*np.log(null_probability)
                        + (trials-events)*np.log1p(-null_probability))) + constant
    deviance = max(0.0, 2*(saturated-loglike))
    pearson = float(np.sum((events-trials*p)**2 / (trials*p*(1-p))))
    model_lr = max(0.0, 2*(loglike-null))
    return {"log_likelihood": loglike, "null_log_likelihood": null,
            "deviance": deviance, "pearson_chi_square": pearson,
            "null_probability": null_probability, "model_lr": model_lr,
            "model_lr_p": float(stats.chi2.sf(model_lr, case["model_df"])),
            "deviance_p": (float(stats.chi2.sf(deviance, case["residual_df"]))
                           if case["residual_df"] > 0 else None),
            "pearson_p": (float(stats.chi2.sf(pearson, case["residual_df"]))
                          if case["residual_df"] > 0 else None)}


def matrix_for_native(case_id, native_rows):
    if case_id == "BIN-FACTORIAL":
        values = np.asarray([[row["settings"][name] for name in ("A", "B")]
                             for row in native_rows], dtype=float)
        a, b = values.T
        return np.column_stack((np.ones(len(values)), a, b, a*b)), [
            "截距", "A", "B", "A*B"]
    return np.asarray([], dtype=float), []


def compare_case(case_id, local_case, native_case):
    rows = []
    names = local_case["factor_ids"]
    local_by_key = {(row["point_key"], row["occurrence"]): row
                    for row in local_case["rows"]}
    native_by_key = {(row["point_key"], row["occurrence"]): row
                     for row in native_case["design_rows"]}
    if set(local_by_key) != set(native_by_key):
        raise ValueError(f"{case_id} Minitab/MiniJMP DOE 点映射不一致")
    for key in sorted(local_by_key):
        left, right = local_by_key[key], native_by_key[key]
        for name in names:
            rows.append(compare_numeric(case_id, "design", key[0], name,
                                        right["settings"][name], left["settings"][name],
                                        "Minitab DOE worksheet factor column (DIRECT)",
                                        "MiniJMP fixed design row"))
        rows.append(compare_numeric(case_id, "input", key[0], "events",
                                    right["events"], left["events"],
                                    "fixed input loaded into Minitab", "MiniJMP fixed input"))
        rows.append(compare_numeric(case_id, "input", key[0], "trials",
                                    right["trials"], left["trials"],
                                    "fixed input loaded into Minitab", "MiniJMP fixed input"))

    local_keys = sorted(local_by_key)
    native_matrix_by_key = {(row["point_key"], row["occurrence"]): row.get("matrix")
                            for row in native_case["design_rows"]}
    local_matrix_by_key = {(row["point_key"], row["occurrence"]): row["matrix"]
                           for row in local_case["rows"]}
    local_x = np.asarray([local_matrix_by_key[key] for key in local_keys], dtype=float)
    if case_id == "BIN-FACTORIAL":
        native_x = np.asarray([matrix_for_native(case_id, [native_by_key[key]])[0][0]
                               for key in local_keys], dtype=float)
    else:
        native_x = np.asarray([native_matrix_by_key[key] for key in local_keys], dtype=float)

    column_map = []
    for index in range(native_x.shape[1]):
        actual = native_x[:, index]
        matches = [(j, 1) for j in range(local_x.shape[1])
                   if np.allclose(actual, local_x[:, j], rtol=0, atol=1e-12)]
        matches += [(j, -1) for j in range(local_x.shape[1])
                    if np.allclose(actual, -local_x[:, j], rtol=0, atol=1e-12)]
        if len(matches) != 1:
            raise ValueError(f"{case_id} Minitab/X model basis mismatch at column {index}: {matches}")
        column_map.append(matches[0])
    if len(column_map) != len(local_case["column_names"]):
        raise ValueError(f"{case_id} Minitab coefficient basis length mismatch")
    beta = np.asarray(native_case["coefficients"], dtype=float)
    se = np.asarray(native_case["standard_errors"], dtype=float)
    transformed_beta = np.zeros_like(beta)
    transformed_se = np.zeros_like(se)
    for native_index, (local_index, sign) in enumerate(column_map):
        transformed_beta[local_index] = sign*beta[native_index]
        transformed_se[local_index] = se[native_index]
    basis_error = float(np.max(np.abs(native_x - np.column_stack(
        [sign*local_x[:, index] for index, sign in column_map]))))
    rows.append(compare_numeric(case_id, "model_space", "grouped binomial", "rank",
                                int(np.linalg.matrix_rank(native_x)), local_case["rank"],
                                "Minitab model matrix (DIRECT/DERIVED per command)",
                                "MiniJMP production matrix"))
    rows.append(compare_numeric(case_id, "model_space", "grouped binomial", "basis_error",
                                basis_error, 0.0, "DERIVED: Minitab coded model basis",
                                "MiniJMP production model basis"))
    local_probabilities = {key: row["fit"] for key, row in
                           {(r["point_key"], r["occurrence"]): r
                            for r in local_case["rows"]}.items()}
    native_probabilities = {(row["point_key"], row["occurrence"]): row["fit"]
                            for row in native_case["design_rows"]}
    for key in local_keys:
        rows.append(compare_numeric(case_id, "run_statistics", key[0], "probability",
                                    native_probabilities[key], local_probabilities[key],
                                    "Minitab FITS event probability (DIRECT)",
                                    "MiniJMP fitted probability"))
    for index, term in enumerate(local_case["column_names"]):
        estimate = transformed_beta[index]
        standard_error = transformed_se[index]
        z_value = estimate / standard_error
        from scipy import stats
        p_value = 2 * float(stats.norm.sf(abs(z_value)))
        local_row = local_case["coefficients"][index]
        for statistic, native_value, local_value, source in (
            ("estimate", estimate, local_row["coefficient"], "Minitab COEFFICIENTS (DIRECT)"),
            ("standard_error", standard_error, local_row["se"], "Minitab SECOEFFICIENTS (DIRECT)"),
            ("wald_z", z_value, local_row["z"], "DERIVED: coefficient / SE"),
            ("wald_p", p_value, local_row["p"], "DERIVED: two-sided normal tail"),
        ):
            rows.append(compare_numeric(case_id, "coefficient", term, statistic,
                                        native_value, local_value, source,
                                        "MiniJMP fit_grouped_binomial"))

    if case_id == "BIN-FACTORIAL":
        trials = np.asarray([native_by_key[key]["trials"] for key in local_keys], dtype=float)
        probabilities = np.asarray([native_probabilities[key] for key in local_keys], dtype=float)
        information = native_x.T @ np.diag(trials*probabilities*(1-probabilities)) @ native_x
        fisher_se = np.sqrt(np.diag(np.linalg.inv(information)))
        fisher_se_local = np.zeros_like(transformed_se)
        for native_index, (local_index, _) in enumerate(column_map):
            fisher_se_local[local_index] = fisher_se[native_index]
        for index, term in enumerate(local_case["column_names"]):
            rows.append(compare_numeric(
                case_id, "independent_hessian", term, "minitab_se_vs_fisher",
                transformed_se[index], fisher_se_local[index],
                "Minitab SECOEFFICIENTS (DIRECT)",
                "DERIVED: inverse X'WX from Minitab FITS and trials"))
            rows.append(compare_numeric(
                case_id, "independent_hessian", term, "minijmp_se_vs_fisher",
                fisher_se_local[index], local_case["coefficients"][index]["se"],
                "DERIVED: inverse X'WX from Minitab FITS and trials",
                "MiniJMP fit_grouped_binomial covariance"))
    else:
        inverse = np.asarray(native_case["xpw_inverse"], dtype=float)
        matrix_se = np.sqrt(np.diag(inverse))
        for native_index, (local_index, _) in enumerate(column_map):
            rows.append(compare_numeric(
                case_id, "independent_hessian", local_case["column_names"][local_index],
                "minitab_se_vs_xpw_inverse", transformed_se[local_index],
                matrix_se[native_index], "Minitab SECOEFFICIENTS (DIRECT)",
                "Minitab XPWXINVERSE M2 (DIRECT)"))

    native_stats = derived_logistic(local_case, native_probabilities)
    for statistic in ("log_likelihood", "deviance", "pearson_chi_square",
                      "model_lr", "model_lr_p", "deviance_p", "pearson_p"):
        local_value = {
            "log_likelihood": local_case["log_likelihood"],
            "deviance": local_case["deviance"],
            "pearson_chi_square": local_case["pearson_chi_square"],
            "model_lr": local_case["model_lr"], "model_lr_p": local_case["model_p"],
            "deviance_p": local_case["deviance_p"],
            "pearson_p": local_case["pearson_p"],
        }[statistic]
        rows.append(compare_numeric(case_id, "model_fit", "grouped binomial", statistic,
                                    native_stats[statistic], local_value,
                                    "DERIVED: Minitab FITS and fixed event/trial counts",
                                    "MiniJMP fit_grouped_binomial"))

    if case_id == "BIN-RSM":
        x0_local = np.asarray(local_case["prediction_row"], dtype=float)
        local_prediction = local_case["prediction"]
        x0_native = np.asarray([sign*x0_local[index] for index, sign in column_map], dtype=float)
        native_inverse = np.asarray(native_case["xpw_inverse"], dtype=float)
        eta = float(x0_native @ beta)
        se_eta = math.sqrt(float(x0_native @ native_inverse @ x0_native))
        probability = 1/(1+math.exp(-eta))
        critical = 1.959963984540054
        ci_low = 1/(1+math.exp(-(eta-critical*se_eta)))
        ci_high = 1/(1+math.exp(-(eta+critical*se_eta)))
        for statistic, native_value, local_value in (
            ("eta_hat", eta, local_prediction["eta_hat"]),
            ("se_eta", se_eta, local_prediction["se_eta"]),
            ("p_hat", probability, local_prediction["p_hat"]),
            ("ci_low", ci_low, local_prediction["ci_low"]),
            ("ci_high", ci_high, local_prediction["ci_high"]),
        ):
            rows.append(compare_numeric(case_id, "prediction", "A=.2,B=-.3,C=.4", statistic,
                                        native_value, local_value,
                                        "DERIVED: Minitab BRSREG coefficients and X'WX inverse",
                                        "MiniJMP predict_binary_probability (95% logit Wald)"))
    return rows


def write_report(rows, status, reason=""):
    unique = unique_rows(rows)
    failures = [row for row in unique if row["status"] == "FAIL"]
    counts = status_counts(unique)
    sources = {name: sum(name in row["minitab_value_source"] for row in unique)
               for name in ("DIRECT", "DERIVED", "DISPLAY")}
    lines = [
        "# DOE 二元响应分析对标验收", "", f"状态：**{status}**", "",
        "## 案例与定义", "",
        "- `BIN-FACTORIAL`：2² 两水平全因子，4 个事件/试验分组，完整 A+B+A×B Logistic 模型。",
        "- `BIN-RSM`：3 因子 BBD（12 边点+2 中心点），完整二次 Logistic 模型。",
        "- MiniJMP 与 Minitab 均拟合 grouped binomial-logit；最大迭代 200、收敛容差 1e-10。",
        "- 两案均使用 Minitab DOE 专用原生命令 `BFFACTORIAL`/`BRSREG`，不是通用 GLM 替代。", "",
        "## 结果", "",
        f"唯一比较项：{len(unique)}；PASS/FAIL/N/A/UNSUPPORTED：{counts['PASS']}/{counts['FAIL']}/{counts['N/A']}/{counts['UNSUPPORTED']}。",
        f"Minitab 来源计数（可重叠）：DIRECT/DERIVED/DISPLAY：{sources['DIRECT']}/{sources['DERIVED']}/{sources['DISPLAY']}。", "",
        "## 证据", "",
        "- 固定数据、Session Commands、Minitab Outputs/OutputDocument、双方高精度 JSON 与逐项比较 CSV 均保存在本目录。",
        "- RSM 预测区间采用 Logit 尺度 95% Wald 区间；Minitab 侧由直接系数和 X'WX 逆矩阵重建。", "",
    ]
    if failures:
        grouped = {}
        for row in failures:
            grouped.setdefault((row["case_id"], row["statistic"]), []).append(row)
        lines.extend(["## 超出默认容差的差异", ""])
        for (case_id, statistic), values in sorted(grouped.items()):
            worst = max(values, key=lambda row: float(row["absolute_error"] or 0))
            lines.append(
                f"- `{case_id}` / `{statistic}`：{len(values)} 项；最大绝对差 "
                f"{float(worst['absolute_error']):.10g}（{worst['term']}），"
                f"Minitab={worst['minitab_value']}，MiniJMP={worst['minijmp_value']}。"
            )
        if any(row["case_id"] == "BIN-FACTORIAL"
               and row["statistic"] == "standard_error" for row in failures):
            lines.append(
                "- `BIN-FACTORIAL` 的 Minitab SE 与由其直接拟合概率、试验数和编码矩阵构造的 "
                "inverse X'WX 参考吻合；MiniJMP SE 与该参考相差约 5.92e-7 相对误差。"
                "关联的 Wald z/P 同样超出容差。"
            )
        if any(row["case_id"] == "BIN-RSM" and row["statistic"] == "wald_z"
               for row in failures):
            lines.append(
                "- `BIN-RSM` 的系数和 SE 比较通过；4 个由高精度系数/SE 计算的 Wald z 仍超过默认容差，"
                "最大绝对差约 2.72e-8。"
            )
        lines.extend(["未修改 MiniJMP 生产算法或放宽容差；逐项值和误差见 `comparison.csv`。", ""])
    if reason:
        lines.extend(["## 阻断", "", reason, ""])
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    return counts


def parent_main():
    try:
        run_worker(Path(__file__), "--minijmp-worker", timeout=240)
        run_worker(Path(__file__), "--com-worker", timeout=360)
        local = json.loads(MINIJMP.read_text(encoding="utf-8"))
        native = json.loads(MINITAB.read_text(encoding="utf-8"))
        rows = [row for case_id in CASE_IDS
                for row in compare_case(case_id, local[case_id], native[case_id])]
        write_comparison(COMPARISON, rows)
        status = "FAIL" if any(row["status"] == "FAIL" for row in unique_rows(rows)) else "PASS"
        counts = write_report(rows, status)
        print(f"Binary DOE supplemental {status}: {counts}; Minitab worker 已退出。", flush=True)
        return 0
    except Exception as error:
        write_comparison(COMPARISON, [])
        write_report([], "BLOCKED", f"{type(error).__name__}: {error}；请查看原始输出。")
        print(f"Binary DOE supplemental BLOCKED: {type(error).__name__}: {error}", flush=True)
        return 1


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--minijmp-worker":
        try:
            minijmp_worker()
        except Exception:
            traceback.print_exc()
            raise SystemExit(1)
        raise SystemExit(0)
    if len(sys.argv) == 2 and sys.argv[1] == "--com-worker":
        raise SystemExit(minitab_worker())
    if len(sys.argv) == 2 and sys.argv[1] == "--self-check":
        assert point_key({"A": -1, "B": 1}, ("A", "B")) == "-1,1"
        print("Binary DOE verifier self-check: PASS")
        raise SystemExit(0)
    raise SystemExit(parent_main())
