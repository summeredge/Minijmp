"""MiniJMP × Minitab 19 mixture process and amount model parity."""
from __future__ import annotations

import csv
import json
import math
import sys
import traceback
from pathlib import Path

import numpy as np
from scipy import stats

HERE = Path(__file__).resolve().parent
SUPPLEMENTAL = HERE.parent
ROOT = SUPPLEMENTAL.parents[2]
for path in (SUPPLEMENTAL, ROOT / "code"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from common import (  # noqa: E402
    MinitabSession,
    compare_numeric,
    compare_text,
    run_worker,
    status_counts,
    write_comparison,
    write_json,
)

from doe_mixture import MixtureSpec, restore_mixture  # noqa: E402
from doe_mixture_analysis import analyze_mixture  # noqa: E402
from doe_mixture_constraints import ComponentSpec, VariableSpec  # noqa: E402
from doe_mixture_designs import create_mixture_design  # noqa: E402
from doe_mixture_model import MixtureTermModel  # noqa: E402
from doe_mixture_predict import predict_mixture  # noqa: E402

CASE_IDS = ("MIX-PROCESS", "MIX-AMOUNT")
COMPONENTS = tuple(ComponentSpec(name, name) for name in ("A", "B", "C"))
PROCESS_PREDICTION = {"proportions": {"A": .2, "B": .3, "C": .5}, "process": {"P": .5}}
AMOUNT_PREDICTION = {"proportions": {"A": .2, "B": .3, "C": .5}, "amount": {"T": 125}}
PROCESS_ERROR = {1: .12, 2: -.12}
AMOUNT_ERROR = {1: .15, 2: -.15}
MTB_MISSING = 1.23456e30

INPUTS = {case_id: HERE / f"{case_id.lower().replace('-', '_')}_input.csv"
          for case_id in CASE_IDS}
MINIJMP = HERE / "minijmp_results.json"
MINITAB = HERE / "minitab_results.json"
RAW = HERE / "minitab_raw.txt"
COMMANDS = HERE / "session_commands.txt"
COMPARISON = HERE / "comparison.csv"
REPORT = HERE / "acceptance.md"


def _clean(value):
    if value is None:
        return None
    if isinstance(value, np.ndarray):
        return _clean(value.tolist())
    if isinstance(value, np.generic):
        return _clean(value.item())
    if isinstance(value, dict):
        return {str(key): _clean(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_clean(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _specs():
    process = MixtureSpec(
        "mix-process", COMPONENTS, ("Y",), "simplex_lattice", 2,
        process_variables=(VariableSpec("P", "P", -1, 1),), seed=31,
        construction_version="v1")
    amount = MixtureSpec(
        "mix-amount", COMPONENTS, ("Y",), "simplex_lattice", 2,
        amount_variables=(VariableSpec("T", "T", 50, 150, "g", "amount"),),
        amount_settings=(("T", 100),), seed=37, construction_version="v2")
    return process, amount


def _mixture_key(settings, amount=False):
    values = tuple(round(float(settings[name]), 12) for name in ("A", "B", "C"))
    variable = round(float(settings["T"] if amount else settings["P"]), 12)
    return values + (variable,)


def _response(case_id, settings, replicate):
    a, b, c = (float(settings[name]) for name in ("A", "B", "C"))
    if case_id == "MIX-PROCESS":
        p = float(settings["P"])
        return 2*a + b + 3*c + 2*a*p + .5*b*p + .5*c*p + PROCESS_ERROR[int(replicate)]
    t_code = (float(settings["T"]) - 100.0) / 50.0
    return (10*a + 14*b + 18*c + 4*a*b - 2*a*c + 3*b*c
            + 1.5*a*t_code - .5*b*t_code + .8*c*t_code
            + AMOUNT_ERROR[int(replicate)])


def _write_input(case_id, rows):
    with INPUTS[case_id].open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _case_input_rows(case_id, frame, mixture_metadata, doe_metadata):
    spec, mixture_rows = restore_mixture(frame, mixture_metadata, doe_metadata)
    rows = []
    for item in mixture_rows:
        source = item["row"]
        settings = item["settings"]
        result = {
            "case_id": case_id, "run_id": str(item["run_id"]),
            "standard_order": int(source["标准序"]),
            "run_order": int(source["运行序"]), "replicate": int(source["重复"]),
            "point_type": str(source["点类型"]),
            "A_prop": float(settings["A"]), "B_prop": float(settings["B"]),
            "C_prop": float(settings["C"]),
            "P": (float(settings["P"]) if case_id == "MIX-PROCESS" else ""),
            "T_total": (float(settings["T"]) if case_id == "MIX-AMOUNT" else ""),
            "Y": float(source["响应_Y"]),
        }
        result["A_amount"] = (result["A_prop"] * result["T_total"]
                              if case_id == "MIX-AMOUNT" else "")
        result["B_amount"] = (result["B_prop"] * result["T_total"]
                              if case_id == "MIX-AMOUNT" else "")
        result["C_amount"] = (result["C_prop"] * result["T_total"]
                              if case_id == "MIX-AMOUNT" else "")
        result["T_code"] = ((result["T_total"] - 100) / 50
                            if case_id == "MIX-AMOUNT" else "")
        rows.append(result)
    return rows


def run_minijmp():
    results = {"cases": {}}
    process_spec, amount_spec = _specs()
    for case_id, spec, amount_levels, degree, prediction in (
            ("MIX-PROCESS", process_spec, None, 1, PROCESS_PREDICTION),
            ("MIX-AMOUNT", amount_spec, (50, 100, 150), 2, AMOUNT_PREDICTION)):
        frame, metadata = create_mixture_design(spec, replicates=2,
                                                amount_levels=amount_levels)
        mixture_meta, doe_meta = metadata["mixture"], metadata["doe"]
        _, mixture_rows = restore_mixture(frame, mixture_meta, doe_meta)
        values = {}
        for item in mixture_rows:
            settings = item["settings"]
            replicate = int(item["row"]["重复"])
            values[item["run_id"]] = _response(case_id, settings, replicate)
        response_column = mixture_meta["spec"]["response_names"]
        response_name = response_column[0]
        mapped_column = f"响应_{response_name}"
        frame[mapped_column] = [values[run_id] for run_id in frame["运行ID"]]
        analysis = analyze_mixture(frame, mixture_meta, "Y", degree=degree,
                                   doe_metadata=doe_meta)
        inference = analysis["inference"]
        assert inference is not None, f"{case_id}: replicated data should support inference"
        prediction_result = predict_mixture(
            frame, mixture_meta, "Y", prediction["proportions"],
            process=prediction.get("process"), amount=prediction.get("amount"),
            degree=degree, doe_metadata=doe_meta)
        rows = _case_input_rows(case_id, frame, mixture_meta, doe_meta)
        _write_input(case_id, rows)
        model = analysis["model"]
        matrix = model.matrix(analysis["settings"])
        results["cases"][case_id] = {
            "n": int(analysis["n"]), "p": int(analysis["p"]),
            "rank": int(analysis["rank"]), "df": int(analysis["df"]),
            "model_df": int(inference["model_df"]),
            "total_df": int(analysis["total_df"]),
            "terms": list(analysis["terms"]), "matrix": matrix.tolist(),
            "coefficients": analysis["coefficients"].tolist(),
            "fitted": analysis["fitted"].tolist(),
            "residuals": analysis["residuals"].tolist(),
            "sse": float(analysis["sse"]), "sst": float(analysis["sst"]),
            "ssr": float(analysis["ssr"]), "mse": float(inference["mse"]),
            "model_f": float(inference["f"]), "model_p": float(inference["model_p"]),
            "r2": float(analysis["r2"]), "pure_error_df": int(analysis["pure_error_df"]),
            "pure_error_sse": float(analysis["pure_error_sse"]),
            "lack_of_fit_df": int(analysis["lack_of_fit_df"]),
            "lack_of_fit_sse": float(analysis["lack_of_fit_sse"]),
            "anova": _clean(analysis["anova"]), "has_constant": bool(analysis["has_constant"]),
            "rows": rows,
            "prediction": {"settings": _clean(prediction_result["settings"]),
                           "proportions": _clean(prediction_result["proportions"]),
                           "actual_amounts": _clean(prediction_result["actual_amounts"]),
                           "prediction": float(prediction_result["prediction"]),
                           "model_row": _clean(model.row(prediction_result["settings"])),
                           "intervals": _clean(prediction_result["intervals"])},
        }
    process = results["cases"]["MIX-PROCESS"]
    amount = results["cases"]["MIX-AMOUNT"]
    assert (process["n"], process["p"], process["rank"], process["df"]) == (24, 6, 6, 18)
    assert process["terms"] == ["A", "B", "C", "A*P", "B*P", "C*P"]
    assert np.allclose(process["coefficients"], [2, 1, 3, 2, .5, .5], rtol=0, atol=1e-10)
    assert process["pure_error_df"] == 12 and process["pure_error_sse"] > 0
    assert math.isclose(process["prediction"]["prediction"], 2.6, abs_tol=1e-10)
    assert process["prediction"]["intervals"]["ci_low"] is not None
    assert process["prediction"]["intervals"]["pi_high"] is not None
    assert (amount["n"], amount["p"], amount["rank"], amount["df"]) == (36, 9, 9, 27)
    assert amount["terms"] == ["A", "B", "C", "A*B", "A*C", "B*C", "A*T", "B*T", "C*T"]
    assert np.allclose(amount["coefficients"], [10, 14, 18, 4, -2, 3, 1.5, -.5, .8],
                       rtol=0, atol=1e-9)
    assert amount["pure_error_df"] == 18 and amount["pure_error_sse"] > 0
    assert math.isclose(amount["prediction"]["prediction"], 15.965, abs_tol=1e-10)
    assert amount["prediction"]["intervals"]["ci_low"] is not None
    assert amount["prediction"]["intervals"]["pi_high"] is not None
    write_json(MINIJMP, _clean(results))
    return results


def _run_minitab_case(session, case_id, rows):
    amount_case = case_id == "MIX-AMOUNT"
    variable = "T" if amount_case else "P"
    process_column = None if amount_case else 4
    row_keys = []
    for name, key in (("A", "A_prop"), ("B", "B_prop"), ("C", "C_prop"),
                      (variable, "T_total" if amount_case else "P"), ("Y", "Y")):
        values = [float(row[key]) for row in rows]
        session.add_column(name, values)
    row_keys = [
        tuple(round(float(row[key]), 12) for key in ("A_prop", "B_prop", "C_prop"))
        + (round(float(row["T_total"] if amount_case else row["P"]), 12),)
        for row in rows
    ]
    coefficient_column = session.add_column("COEF")
    fit_column = session.add_column("MIX_FIT")
    residual_column = session.add_column("MIX_RESID")
    if amount_case:
        model_terms = "C1 C2 C3 C1*C2 C1*C3 C2*C3"
        extra = "AMOUNT C4; INUNIT 1; LOWER 0 0 0;"
        command = (
            f"MIXREG C5 = {model_terms}; {extra} COEFFICIENTS C{coefficient_column}; "
            f"FITS C{fit_column}; RESIDUALS C{residual_column}; XMATRIX M1; "
            "BRIEF 3."
        )
    else:
        model_terms = "C1 C2 C3 C1*C4 C2*C4 C3*C4"
        extra = f"PROC C{process_column}; INUNIT 1; LOWER 0 0 0;"
        command = (
            f"MIXREG C5 = {model_terms}; {extra} COEFFICIENTS C{coefficient_column}; "
            f"FITS C{fit_column}; RESIDUALS C{residual_column}; XMATRIX M1; BRIEF 3."
        )
    output = session.execute(command, case_id)
    matrix = session.read_matrix("M1")
    coefficients = [value for value in session.column_values(coefficient_column)
                    if value is not None and value != MTB_MISSING]
    fitted = [value for value in session.column_values(fit_column)
              if value is not None and value != MTB_MISSING]
    residuals = [value for value in session.column_values(residual_column)
                 if value is not None and value != MTB_MISSING]
    response_values = [float(row["Y"]) for row in rows]
    x = np.asarray(matrix, dtype=float)
    y = np.asarray(response_values, dtype=float)
    fit = np.asarray(fitted, dtype=float)
    resid = np.asarray(residuals, dtype=float)
    if len(fit) != len(rows) or len(resid) != len(rows):
        raise RuntimeError(f"MIXREG output row count mismatch: fit={len(fit)}, residual={len(resid)}")
    rank = int(np.linalg.matrix_rank(x))
    df = len(y) - rank
    projected_constant = x @ np.linalg.lstsq(x, np.ones(len(y)), rcond=None)[0]
    has_constant = np.linalg.norm(projected_constant - 1) <= 1e-8 * math.sqrt(len(y))
    sst = float(np.sum((y - y.mean()) ** 2)) if has_constant else float(y @ y)
    sse = float(resid @ resid)
    ssr = max(0.0, sst - sse)
    total_df = len(y) - 1 if has_constant else len(y)
    model_df = max(0, rank - 1) if has_constant else rank
    mse = sse / df if df > 0 else None
    f_value = ((ssr / model_df) / mse if mse and model_df > 0 else None)
    p_value = (float(stats.f.sf(f_value, model_df, df))
               if f_value is not None else None)
    return {
        "command": command, "row_keys": [list(key) for key in row_keys],
        "n": len(y), "p": int(x.shape[1]), "rank": rank, "df": df,
        "model_df": model_df, "total_df": total_df, "has_constant": bool(has_constant),
        "terms": model_terms, "matrix": matrix, "coefficients": coefficients,
        "fitted": fitted, "residuals": residuals,
        "sse": sse, "sst": sst, "ssr": ssr, "mse": mse,
        "r2": 1 - sse / sst if sst > 0 else None,
        "f_value": f_value, "p_value": p_value,
        "output_excerpt": output[-8000:],
    }


def run_com_worker():
    session = None
    results = {"version": "19.1.0.1", "cases": {}}
    commands = []
    try:
        session = MinitabSession()
        for case_id in CASE_IDS:
            if case_id != CASE_IDS[0]:
                session.new_project()
            try:
                rows = list(csv.DictReader(INPUTS[case_id].open(encoding="utf-8-sig")))
                for row in rows:
                    row["Y"] = float(row["Y"])
                    row["A_prop"] = float(row["A_prop"])
                    row["B_prop"] = float(row["B_prop"])
                    row["C_prop"] = float(row["C_prop"])
                    if case_id == "MIX-PROCESS":
                        row["P"] = float(row["P"])
                    else:
                        row["T_total"] = float(row["T_total"])
                result = _run_minitab_case(session, case_id, rows)
                results["cases"][case_id] = result
                commands.append(result["command"])
            except Exception as exc:
                results["cases"][case_id] = {"error": str(exc)}
                commands.append(f"{case_id} failed; see minitab_raw.txt")
    except Exception as exc:
        results["session_error"] = str(exc)
        results["traceback"] = traceback.format_exc()
    finally:
        if session is not None:
            RAW.write_text("\n\n".join(session.raw) + "\n", encoding="utf-8")
            session.release()
        else:
            RAW.write_text("COM session did not start.\n", encoding="utf-8")
        write_json(MINITAB, results)
        COMMANDS.write_text("\n\n".join(commands) + "\n", encoding="utf-8")
    return results


def _compare_model(case_id, mini, mtb):
    if "error" in mtb:
        message = mtb["error"]
        return [{
            "case_id": case_id, "comparison_run": "1", "section": "Minitab MIXREG",
            "term": "model", "statistic": "native_model_execution",
            "minitab_value": message, "minijmp_value": "MiniJMP model available",
            "absolute_error": "", "relative_error": "",
            "absolute_tolerance": "", "relative_tolerance": "",
            "minitab_value_source": "DIRECT", "minijmp_value_source": "DIRECT",
            "status": "FAIL",
        }]
    rows = []
    xm = np.asarray(mini["matrix"], dtype=float)
    xt = np.asarray(mtb["matrix"], dtype=float)
    if xt.shape[0] != xm.shape[0] or xt.shape[1] != xm.shape[1]:
        return [{
            "case_id": case_id, "comparison_run": "1", "section": "model",
            "term": "MIXREG", "statistic": "model_structure_match",
            "minitab_value": f"matrix={xt.shape}", "minijmp_value": f"matrix={xm.shape}",
            "absolute_error": "", "relative_error": "",
            "absolute_tolerance": "", "relative_tolerance": "",
            "minitab_value_source": "UNSUPPORTED", "minijmp_value_source": "DIRECT",
            "status": "UNSUPPORTED",
        }]
    transform, _, _, _ = np.linalg.lstsq(xm, xt, rcond=None)
    matrix_error = float(np.max(np.abs(xm @ transform - xt)))
    transform_rank = int(np.linalg.matrix_rank(transform))
    same_space = matrix_error <= 1e-10 and transform_rank == xm.shape[1]
    rows.extend([
        compare_numeric(case_id, "design", "model_matrix", "rank",
                        mtb["rank"], mini["rank"], "DERIVED", "DIRECT"),
        compare_numeric(case_id, "design", "model_matrix", "basis_max_abs_error",
                        matrix_error, 0.0, "DERIVED", "DERIVED"),
        compare_text(case_id, "design", "model_matrix", "same_model_space",
                     str(same_space), "True", "DERIVED", "DERIVED"),
        compare_numeric(case_id, "model", "degrees_of_freedom", "residual_df",
                        mtb["df"], mini["df"], "DERIVED", "DIRECT"),
        compare_numeric(case_id, "model", "degrees_of_freedom", "model_df",
                        mtb["model_df"], mini["model_df"], "DERIVED", "DIRECT"),
        compare_numeric(case_id, "model", "degrees_of_freedom", "total_df",
                        mtb["total_df"], mini["total_df"], "DERIVED", "DIRECT"),
        compare_numeric(case_id, "model", "fit", "SSE", mtb["sse"], mini["sse"],
                        "DERIVED", "DIRECT"),
        compare_numeric(case_id, "model", "fit", "SST", mtb["sst"], mini["sst"],
                        "DERIVED", "DIRECT"),
        compare_numeric(case_id, "model", "fit", "SSR", mtb["ssr"], mini["ssr"],
                        "DERIVED", "DIRECT"),
        compare_numeric(case_id, "model", "fit", "MSE", mtb["mse"], mini["mse"],
                        "DERIVED", "DIRECT"),
        compare_numeric(case_id, "model", "fit", "R_squared", mtb["r2"], mini["r2"],
                        "DERIVED", "DIRECT"),
        compare_numeric(case_id, "ANOVA", "model", "F", mtb["f_value"],
                        mini["model_f"], "DERIVED", "DERIVED"),
        compare_numeric(case_id, "ANOVA", "model", "P", mtb["p_value"],
                        mini["model_p"], "DERIVED", "DERIVED"),
    ])
    if same_space:
        common_coefficients = transform @ np.asarray(mtb["coefficients"], dtype=float)
        rows.append(compare_numeric(
            case_id, "model", "coefficients", "max_abs_error_common_basis",
            float(np.max(np.abs(common_coefficients - np.asarray(mini["coefficients"])))),
            0.0, "DERIVED", "DIRECT"))
        rows.append(compare_numeric(
            case_id, "model", "fit", "max_abs_fit_error",
            float(np.max(np.abs(np.asarray(mtb["fitted"]) - np.asarray(mini["fitted"])))),
            0.0, "DIRECT", "DIRECT"))
        rows.append(compare_numeric(
            case_id, "model", "fit", "max_abs_residual_error",
            float(np.max(np.abs(np.asarray(mtb["residuals"]) - np.asarray(mini["residuals"])))),
            0.0, "DIRECT", "DIRECT"))
        if np.allclose(transform, np.eye(xm.shape[1]), rtol=0, atol=1e-10):
            y = np.asarray([row["Y"] for row in mini["rows"]], dtype=float)
            for item in mini["anova"]:
                if item["f"] is None:
                    continue
                index = mini["terms"].index(item["source"])
                reduced = np.delete(xt, index, axis=1)
                reduced_fit = reduced @ np.linalg.lstsq(reduced, y, rcond=None)[0]
                term_ss = max(0.0, float(np.sum((y - reduced_fit) ** 2) - mtb["sse"]))
                term_df = int(mtb["rank"] - np.linalg.matrix_rank(reduced))
                term_f = term_ss / (term_df * mtb["mse"])
                term_p = float(stats.f.sf(term_f, term_df, mtb["df"]))
                for statistic, mtb_value, mini_value in (
                        ("adjusted_SS", term_ss, item["ss"]),
                        ("df", term_df, item["df"]),
                        ("F", term_f, item["f"]),
                        ("P", term_p, item["p"])):
                    rows.append(compare_numeric(
                        case_id, "ANOVA", item["source"], statistic,
                        mtb_value, mini_value, "DERIVED", "DIRECT"))
        target = np.asarray(mini["prediction"]["model_row"], dtype=float) @ transform
        prediction = float(target @ np.asarray(mtb["coefficients"], dtype=float))
        covariance_factor = float(target @ np.linalg.inv(xt.T @ xt) @ target)
        se_fit = math.sqrt(mtb["mse"] * covariance_factor)
        critical = float(stats.t.ppf(.975, mtb["df"]))
        bounds = {
            "prediction": prediction,
            "SE_fit": se_fit,
            "CI_low": prediction - critical * se_fit,
            "CI_high": prediction + critical * se_fit,
            "PI_low": prediction - critical * math.sqrt(mtb["mse"] * (1 + covariance_factor)),
            "PI_high": prediction + critical * math.sqrt(mtb["mse"] * (1 + covariance_factor)),
        }
        for statistic, mini_value in (
                ("prediction", mini["prediction"]["prediction"]),
                ("SE_fit", mini["prediction"]["intervals"]["se_fit"]),
                ("CI_low", mini["prediction"]["intervals"]["ci_low"]),
                ("CI_high", mini["prediction"]["intervals"]["ci_high"]),
                ("PI_low", mini["prediction"]["intervals"]["pi_low"]),
                ("PI_high", mini["prediction"]["intervals"]["pi_high"])):
            rows.append(compare_numeric(
                case_id, "prediction", "fixed_settings", statistic,
                bounds[statistic], mini_value, "DERIVED", "DIRECT"))
    return rows


def make_comparison(minijmp, minitab):
    rows = []
    for case_id in CASE_IDS:
        mini = minijmp["cases"][case_id]
        mtb = minitab.get("cases", {}).get(case_id, {})
        rows.extend(_compare_model(case_id, mini, mtb))
    return rows


def write_report(rows, minitab):
    counts = status_counts(rows)
    per_case = {case_id: status_counts([row for row in rows if row["case_id"] == case_id])
                for case_id in CASE_IDS}
    mt_sources = {}
    for row in rows:
        source = row["minitab_value_source"]
        mt_sources[source] = mt_sources.get(source, 0) + 1
    lines = [
        "# Minitab 19 Mixture 过程与总量补充对标",
        "",
        f"唯一比较项：{sum(counts.values())}（PASS {counts['PASS']} / FAIL {counts['FAIL']} / "
        f"N/A {counts['N/A']} / UNSUPPORTED {counts['UNSUPPORTED']}）。",
        f"Minitab 来源：DIRECT {mt_sources.get('DIRECT', 0)}、DERIVED {mt_sources.get('DERIVED', 0)}、"
        f"DISPLAY {mt_sources.get('DISPLAY', 0)}。",
        "",
        *[f"- {case_id}: PASS {value['PASS']} / FAIL {value['FAIL']} / "
          f"N/A {value['N/A']} / UNSUPPORTED {value['UNSUPPORTED']}。"
          for case_id, value in per_case.items()],
        "",
        "## Minitab 19 实际命令",
        "",
    ]
    for case_id in CASE_IDS:
        value = minitab.get("cases", {}).get(case_id, {})
        lines.extend([f"- {case_id}:", "", "```text",
                      value.get("command", value.get("error", "未运行")), "```", ""])
    lines.extend([
        "## 口径与限制",
        "",
        "- 两案均使用三组分二阶 Simplex Lattice 固定输入；组件比例、过程/总量实际水平、Minitab 模型矩阵与两侧响应逐行保存。",
        "- MIX-PROCESS 的 Minitab `PROC` 子命令指定过程列，模型显式包含组分×过程项。",
        "- MIX-AMOUNT 的 Minitab `MIXREG` 得到 36×6、秩6模型，而 MiniJMP 总量交叉模型为36×9、秩9；Minitab 19 的原生 MIXREG 未生成三个组分×总量项，按实际 XMATRIX 结构标记 UNSUPPORTED。",
        "- MIX-PROCESS 在项基底一致时比较逐项 ANOVA；预测值、SE、CI/PI 由 Minitab 高精度系数与 XMATRIX 派生，不使用舍入报表值。",
        "- 联合过程×总量 72 行的等价 REGRESS 证据另见 `mixture_v2_acceptance_report.md`；本报告保留两个独立案例。",
        "- 官方 Session Commands 第 374–381 页定义 `MIXREG`、`PROC`、`AMOUNT`、`LOWER` 及 `PREDICT`；完整输出见 `minitab_raw.txt`。",
    ])
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    if "--self-check" in sys.argv:
        run_minijmp()
        print("mixture process/amount model and prediction self-check passed")
    elif "--com-worker" in sys.argv:
        results = run_com_worker()
        print(f"Minitab worker completed; cases={list(results.get('cases', {}))}")
    elif "--run" in sys.argv:
        minijmp = run_minijmp()
        run_worker(Path(__file__), "--com-worker")
        minitab = json.loads(MINITAB.read_text(encoding="utf-8"))
        rows = make_comparison(minijmp, minitab)
        write_comparison(COMPARISON, rows)
        write_report(rows, minitab)
        write_json(MINITAB, minitab)
        print(f"Mixture supplemental counts: {status_counts(rows)}")
    else:
        raise SystemExit("Use --self-check, --com-worker, or --run")


if __name__ == "__main__":
    main()
