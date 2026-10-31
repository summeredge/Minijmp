"""MiniJMP × Minitab 19 fractional/PB foldover parity."""
from __future__ import annotations

import csv
import json
import math
import sys
import traceback
from collections import Counter
from itertools import combinations
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SUPPLEMENTAL = HERE.parent
ROOT = SUPPLEMENTAL.parents[2]
CASE_IDS = ("FOLD-REG", "FOLD-PB")
REG_FACTORS = ("A", "B", "C")
PB_FACTORS = tuple(f"F{i}" for i in range(1, 12))
MTB_PB_FACTORS = ("A", "B", "C", "D", "E", "F", "G", "H", "J", "K", "L")
INPUTS = {case: HERE / f"{case.lower().replace('-', '_')}_input.csv" for case in CASE_IDS}
COMMANDS = HERE / "session_commands.txt"
RAW = HERE / "minitab_raw.txt"
MINIJMP = HERE / "minijmp_results.json"
MINITAB = HERE / "minitab_results.json"
COMPARISON = HERE / "comparison.csv"
REPORT = HERE / "acceptance.md"

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


def coded(value):
    return int(round(float(value)))


def point_key(values):
    return ",".join(str(coded(value)) for value in values)


def response_value(case_id, settings, replicate=1):
    if case_id == "FOLD-REG":
        a, b, c = (coded(settings[name]) for name in REG_FACTORS)
        noise = -0.3 if int(replicate) == 1 else 0.3
        return 30 + 2*a - 1.5*b + .8*c + 1.75*a*b + .45*b*c + noise
    x = {name: coded(settings[name]) for name in PB_FACTORS}
    return (20 + 1.8*x["F1"] - 2.2*x["F2"] + 1.4*x["F3"]
            + .75*x["F1"]*x["F2"] - .55*x["F4"]*x["F5"]
            + .3*x["F7"]*x["F9"])


def make_spec(case_id):
    from doe_core import DesignSpec, FactorSpec

    if case_id == "FOLD-REG":
        factors = tuple(FactorSpec(name, name, -1, 1) for name in REG_FACTORS)
        return DesignSpec("fold-reg", factors, ("Y",), seed=23,
                          generators=("C=AB",), design_type="two_level_fractional")
    factors = tuple(FactorSpec(name, name, -1, 1) for name in PB_FACTORS)
    screening_matrix = {"construction_id": "pb12.v1", "source_kind": "publication",
                        "source_id": "nist.pb12", "matrix_sha256": "0" * 64}
    return DesignSpec("fold-pb12", factors, ("Y",), seed=7,
                      design_type="plackett_burman", screening_matrix=screening_matrix)


def analysis_rows(case_id, result):
    design = result["design"]
    x = (np.asarray(result["fit_matrix"], dtype=float) if case_id == "FOLD-PB"
         else np.column_stack((np.ones(len(result["coded"])), result["coded"])))
    terms = result["names"]
    rows = []
    for index, run in enumerate(design.runs):
        batch = run.batch_id or "BASE"
        settings = {name: coded(run.settings[name]) for name in (
            REG_FACTORS if case_id == "FOLD-REG" else PB_FACTORS)}
        rows.append({
            "batch_id": batch, "run_id": run.run_id,
            "source_run_id": run.source_run_id,
            "standard_order": int(run.standard_order),
            "run_order": int(run.run_order),
            "replicate": int(run.replicate or 1),
            "settings": settings,
            "point_key": point_key(settings.values()),
            "Y": float(run.responses["Y"]),
            "matrix": x[index].tolist(),
            "fit": float(result["fitted"][index]),
            "residual": float(result["residuals"][index]),
        })
    inference = result.get("inference")
    return {
        "terms": list(terms), "n": int(result["n"]), "p": int(result["p"]),
        "rank": int(result["rank"]), "df": int(result["df"]),
        "sse": float(result["sse"]), "sst": float(result["sst"]),
        "ssr": float(result["ssr"]),
        "coefficients": clean(result["coefficients"]),
        "effects": clean(result.get("effects")),
        "inference": clean(inference), "anova": clean(result.get("anova")),
        "pure_error_df": result.get("pure_error_df"),
        "pure_error_sse": result.get("pure_error_sse"),
        "lack_of_fit_df": result.get("lack_of_fit_df"),
        "lack_of_fit_sse": result.get("lack_of_fit_sse"),
        "status": result.get("status"), "rows": rows,
    }


def input_rows(case_id, frame, metadata):
    from doe_core import restore_design_result

    design = restore_design_result(frame, metadata)
    names = REG_FACTORS if case_id == "FOLD-REG" else PB_FACTORS
    result = []
    for run in design.runs:
        settings = {name: coded(run.settings[name]) for name in names}
        result.append({
            "case_id": case_id, "batch_id": run.batch_id or "BASE",
            "run_id": run.run_id, "source_run_id": run.source_run_id,
            "standard_order": int(run.standard_order),
            "run_order": int(run.run_order), "replicate": int(run.replicate or 1),
            "point_key": point_key(settings.values()),
            **{f"{name}_code": settings[name] for name in names},
            "Y": float(run.responses["Y"]),
        })
    return sorted(result, key=lambda row: (row["batch_id"], row["standard_order"]))


def write_input(case_id, rows):
    fields = list(rows[0])
    with INPUTS[case_id].open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def run_fractional():
    import pandas as pd
    from doe_fractional import create_fractional
    from doe_fractional_analysis import analyze_fractional
    from doe_foldover import create_foldover, foldover_summary

    case_id = "FOLD-REG"
    spec = make_spec(case_id)
    base, base_meta = create_fractional(spec, replicates=2)
    base["响应_Y"] = pd.array([
        response_value(case_id, {name: row[f"设定_{name}"] for name in REG_FACTORS},
                       row["重复"])
        for _, row in base.iterrows()
    ], dtype="Float64")
    before = analyze_fractional(base, base_meta, "Y", order=1)
    folded, folded_meta = create_foldover(base, base_meta, "A")
    folded["响应_Y"] = pd.array([
        response_value(case_id, {name: row[f"设定_{name}"] for name in REG_FACTORS},
                       row["重复"])
        for _, row in folded.iterrows()
    ], dtype="Float64")
    after = analyze_fractional(folded, folded_meta, "Y", order=1)
    if (len(base) != 8 or len(folded) != 16 or
            foldover_summary(base, base_meta)["model_rank"] != 4 or
            foldover_summary(folded, folded_meta)["model_rank"] != 8 or
            after["pure_error_df"] != 8 or after["df"] != 12):
        raise AssertionError("FOLD-REG 点数、别名秩或重复误差结构不符")
    rows = input_rows(case_id, folded, folded_meta)
    write_input(case_id, rows)
    return {
        "case_id": case_id, "factor_ids": list(REG_FACTORS),
        "folded_factors": ["A"], "base_runs": input_rows(case_id, base, base_meta),
        "input_rows": rows,
        "before_summary": clean(foldover_summary(base, base_meta)),
        "after_summary": clean(foldover_summary(folded, folded_meta)),
        "before_analysis": analysis_rows(case_id, before),
        "after_analysis": analysis_rows(case_id, after),
    }


def run_pb():
    import pandas as pd
    from doe_pb import create_pb
    from doe_pb_foldover import create_pb_foldover, pb_foldover_summary
    from doe_screening_analysis import analyze_pb

    case_id = "FOLD-PB"
    spec = make_spec(case_id)
    base, base_meta = create_pb(spec, 12)
    base["响应_Y"] = pd.array([
        response_value(case_id, {name: row[f"设定_{name}"] for name in PB_FACTORS})
        for _, row in base.iterrows()
    ], dtype="Float64")
    before = analyze_pb(base, base_meta, "Y")
    folded, folded_meta, summary = create_pb_foldover(base, base_meta)
    folded["响应_Y"] = pd.array([
        response_value(case_id, {name: row[f"设定_{name}"] for name in PB_FACTORS})
        for _, row in folded.iterrows()
    ], dtype="Float64")
    after = analyze_pb(folded, folded_meta, "Y")
    if (len(base) != 12 or len(folded) != 24 or
            summary["before"]["joint_rank"] != 12 or
            summary["after"]["joint_rank"] != 23 or
            len(summary["before"]["complete"]) != 55 or
            len(summary["after"]["estimable"]) != 55 or
            after["df"] != 12 or after["sse"] <= 0):
        raise AssertionError("FOLD-PB 秩、混杂或固定响应误差结构不符")
    rows = input_rows(case_id, folded, folded_meta)
    write_input(case_id, rows)
    return {
        "case_id": case_id, "factor_ids": list(PB_FACTORS),
        "folded_factors": list(PB_FACTORS), "base_runs": input_rows(case_id, base, base_meta),
        "input_rows": rows,
        "before_summary": clean(pb_foldover_summary(base, base_meta)),
        "after_summary": clean(summary),
        "before_analysis": analysis_rows(case_id, before),
        "after_analysis": analysis_rows(case_id, after),
    }


def minijmp_worker():
    sys.path.insert(0, str(ROOT / "code"))
    result = {"FOLD-REG": run_fractional(), "FOLD-PB": run_pb()}
    write_json(MINIJMP, result)
    print("MiniJMP foldover self-check: REG 8→16 runs; PB12 12→24; PASS", flush=True)


def find_design_columns(session, factor_names):
    factor_columns = {name: session.find_column((name,)) for name in factor_names}
    std_column = session.find_column(("StdOrder", "StandardOrder", "标准序"))
    run_column = session.find_column(("RunOrder", "运行序"), required=False)
    factor_values = {name: session.column_values(index)
                     for name, index in factor_columns.items()}
    std = session.column_values(std_column)
    order = (session.column_values(run_column) if run_column
             else list(range(1, len(std) + 1)))
    if any(len(values) != len(std) for values in factor_values.values()) or len(order) != len(std):
        raise RuntimeError("Minitab 设计因子/标准序/运行序列长度不一致")
    return factor_columns, std, order, factor_values


def mtb_rows(session, factor_names, base_count, folded_factors, input_by_key):
    _, std, order, values = find_design_columns(session, factor_names)
    occurrences = Counter()
    rows = []
    for index in sorted(range(len(std)), key=lambda i: int(std[i])):
        codes = tuple(coded(values[name][index]) for name in factor_names)
        batch = "BASE" if int(std[index]) <= base_count else "FOLD1"
        occurrences[(batch, codes)] += 1
        replicate = occurrences[(batch, codes)]
        key = (batch, point_key(codes), replicate)
        source_codes = list(codes)
        if batch == "FOLD1":
            for factor in folded_factors:
                factor_index = factor_names.index(factor)
                source_codes[factor_index] = -source_codes[factor_index]
        source_point = point_key(source_codes) if batch == "FOLD1" else None
        source = input_by_key.get(key)
        rows.append({
            "worksheet_row": index + 1, "batch_id": batch,
            "standard_order": int(std[index]), "run_order": int(order[index]),
            "replicate": replicate,
            "settings": dict(zip(factor_names, codes)),
            "point_key": point_key(codes), "source_point_key": source_point,
            "source_run_id": source["source_run_id"] if source else None,
            "Y": source["Y"] if source else None,
        })
    return rows


def analysis_command(case_id, columns, response_column, fit_column,
                     residual_column, coefficient_column, matrix_name):
    factor_terms = " ".join(f"C{index}" for index in columns.values())
    levels = " ".join("-1 1" for _ in (
        REG_FACTORS if case_id == "FOLD-REG" else PB_FACTORS))
    command = "FFACTORIAL" if case_id == "FOLD-REG" else "SCREEN"
    return (
        f"{command};\n  RESPONSE C{response_column};\n"
        f"  FACTOR {factor_terms};\n  TERMS {factor_terms};\n"
        f"  LEVELS {levels};\n  INUNIT 0;\n"
        f"  FITS C{fit_column};\n  RESIDUALS C{residual_column};\n"
        f"  COEFFICIENTS C{coefficient_column};\n  XMATRIX {matrix_name};\n"
        + ("  TEXPAND." if case_id == "FOLD-REG" else "  TANOVA.")
    )


def minitab_worker():
    raw, commands, session = [], [], None
    try:
        local = json.loads(MINIJMP.read_text(encoding="utf-8"))
        session = MinitabSession()
        results = {}
        for case_index, case_id in enumerate(CASE_IDS):
            if case_index:
                session.new_project()
            factor_names = (REG_FACTORS if case_id == "FOLD-REG" else MTB_PB_FACTORS)
            local_names = (REG_FACTORS if case_id == "FOLD-REG" else PB_FACTORS)
            levels = " ".join("-1 1" for _ in local_names)
            if case_id == "FOLD-REG":
                design_command = (
                    "FFDESIGN 3 4;\n  REPS 2;\n"
                    "  LEVELS -1 1 -1 1 -1 1;\n  DESIGN."
                )
            else:
                design_command = f"PBDESIGN 11 12;\n  LEVELS {levels};\n  DESIGN."
            session.execute(design_command, f"{case_id} native base design")
            base_count = len(local[case_id]["base_runs"])
            factor_columns, base_std, _, base_values = find_design_columns(session, factor_names)
            if len(base_std) != base_count:
                raise RuntimeError(f"{case_id} Minitab base runs {len(base_std)} != {base_count}")
            base_rows = []
            for index in range(len(base_std)):
                settings = {name: coded(base_values[name][index]) for name in factor_names}
                base_rows.append({"batch_id": "BASE", "standard_order": int(base_std[index]),
                                  "settings": settings,
                                  "point_key": point_key(settings.values())})
            fold_command = ("MDESIGN;\n  FOLD A." if case_id == "FOLD-REG"
                            else "MDESIGN;\n  FOLD.")
            session.execute(fold_command, f"{case_id} native foldover")
            native_input = local[case_id]["input_rows"]
            input_by_key = {
                (row["batch_id"], row["point_key"], int(row["replicate"])): row
                for row in native_input
            }
            design_rows = mtb_rows(session, factor_names, base_count,
                                   (("A",) if case_id == "FOLD-REG" else factor_names),
                                   input_by_key)
            expected_keys = set(input_by_key)
            actual_keys = {(row["batch_id"], row["point_key"], row["replicate"])
                           for row in design_rows}
            if actual_keys != expected_keys:
                raise RuntimeError(
                    f"{case_id} native fold points differ: missing={sorted(expected_keys-actual_keys)[:8]}, "
                    f"extra={sorted(actual_keys-expected_keys)[:8]}")
            if any(row["Y"] is None for row in design_rows):
                raise RuntimeError(f"{case_id} Minitab design failed fixed-response mapping")
            raw.append(f"===== {case_id} native base design rows =====\n"
                       + json.dumps(base_rows, ensure_ascii=False, indent=2))
            raw.append(f"===== {case_id} native folded rows =====\n"
                       + json.dumps(design_rows, ensure_ascii=False, indent=2))
            response_column = session.add_column(
                "Y", [float(row["Y"]) for row in design_rows])
            fit_column = session.add_column("Fit")
            residual_column = session.add_column("Resid")
            coefficient_column = session.add_column("Coef")
            matrix_name = "M1"
            command = analysis_command(case_id, factor_columns, response_column,
                                       fit_column, residual_column,
                                       coefficient_column, matrix_name)
            output = session.execute(command, f"{case_id} {command.split(';',1)[0]}")
            matrix = session.read_matrix(matrix_name)
            coefficients = session.column_values(coefficient_column)
            fits = session.column_values(fit_column)
            residuals = session.column_values(residual_column)
            p = len(matrix[0])
            if (len(matrix) != len(design_rows) or len(coefficients) != p
                    or len(fits) != len(design_rows)
                    or len(residuals) != len(design_rows)):
                raise RuntimeError(f"{case_id} native matrix/coefficients/fits length mismatch")
            for index, row in enumerate(design_rows):
                row["matrix"] = matrix[index]
                row["coefficient_fit"] = float(fits[index])
                row["residual"] = float(residuals[index])
            results[case_id] = {
                "version": session.version, "design_command": design_command,
                "fold_command": fold_command, "analysis_command": command,
                "base_rows": base_rows, "design_rows": design_rows,
                "matrix": matrix, "coefficients": coefficients,
                "rank": int(np.linalg.matrix_rank(matrix)), "output": output,
            }
            write_json(MINITAB, results)
            commands.extend([f"# {case_id} base design", design_command,
                             f"# {case_id} foldover", fold_command,
                             f"# {case_id} fixed-response model", command])
            COMMANDS.write_text(
                "# Minitab 19.1.0.1 Session Commands from the official release 19.1 manual\n\n"
                + "\n\n".join(commands) + "\n", encoding="utf-8")
        write_json(MINITAB, results)
        RAW.write_text("\n\n".join([*session.raw, *raw]) + "\n", encoding="utf-8")
        print("Minitab 19.1.0.1 foldover: FFDESIGN/MDESIGN and PBDESIGN/MDESIGN stored",
              flush=True)
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


def polynomial_rank(rows, case_id, include_interactions, factor_names=None):
    names = factor_names or (REG_FACTORS if case_id == "FOLD-REG" else PB_FACTORS)
    x = np.asarray([[row["settings"][name] for name in names] for row in rows], dtype=float)
    columns = [np.ones(len(rows))] + [x[:, index] for index in range(len(names))]
    if include_interactions:
        columns.extend(x[:, left] * x[:, right]
                       for left, right in combinations(range(len(names)), 2))
        if case_id == "FOLD-REG":
            columns.append(np.prod(x, axis=1))
    return int(np.linalg.matrix_rank(np.column_stack(columns)))


def confounding_counts(rows, factor_names):
    x = np.asarray([[row["settings"][name] for name in factor_names] for row in rows],
                   dtype=float)
    mains = [x[:, index] for index in range(len(factor_names))]
    complete = estimable = 0
    base = np.column_stack([np.ones(len(rows)), *mains])
    rank = int(np.linalg.matrix_rank(base))
    for left, right in combinations(range(len(factor_names)), 2):
        interaction = x[:, left] * x[:, right]
        if int(np.linalg.matrix_rank(np.column_stack((base, interaction)))) == rank:
            complete += 1
        else:
            estimable += 1
    return {"main_rank": rank, "joint_rank": polynomial_rank(
                rows, "FOLD-PB", True, factor_names),
            "complete_confounding_count": complete, "estimable_interaction_count": estimable}


def derive_native_stats(native, local_case):
    from scipy import stats

    rows = native["design_rows"]
    x = np.asarray(native["matrix"], dtype=float)
    beta = np.asarray(native["coefficients"], dtype=float)
    y = np.asarray([row["Y"] for row in rows], dtype=float)
    fits = np.asarray([row["coefficient_fit"] for row in rows], dtype=float)
    residuals = np.asarray([row["residual"] for row in rows], dtype=float)
    np.testing.assert_allclose(x @ beta, fits, rtol=0, atol=2e-9)
    np.testing.assert_allclose(y - fits, residuals, rtol=0, atol=2e-9)
    sse = float(residuals @ residuals)
    sst = float(np.sum((y - y.mean()) ** 2))
    rank = int(np.linalg.matrix_rank(x))
    df = len(y) - rank
    mse = sse / df
    covariance = mse * np.linalg.inv(x.T @ x)
    se = np.sqrt(np.diag(covariance))
    t_values = beta / se
    p_values = 2 * stats.t.sf(np.abs(t_values), df)
    model_df = rank - 1
    model_f = ((sst - sse) / model_df) / mse
    return {"n": len(y), "p": x.shape[1], "rank": rank, "df": df,
            "sse": sse, "sst": sst, "ssr": sst - sse, "mse": mse,
            "model_f": float(model_f), "model_p": float(stats.f.sf(model_f, model_df, df)),
            "coefficients": beta.tolist(), "se": se.tolist(),
            "t": t_values.tolist(), "coefficient_p": p_values.tolist(),
            "fits": fits.tolist(), "residuals": residuals.tolist()}


def compare_case(case_id, local_case, native_case):
    rows = []
    local_inputs = local_case["input_rows"]
    native_rows = native_case["design_rows"]
    names = local_case["factor_ids"]
    native_names = REG_FACTORS if case_id == "FOLD-REG" else MTB_PB_FACTORS
    local_by_key = {(row["batch_id"], row["point_key"], int(row["replicate"])): row
                    for row in local_inputs}
    native_by_key = {(row["batch_id"], row["point_key"], int(row["replicate"])): row
                     for row in native_rows}
    local_keys, native_keys = set(local_by_key), set(native_by_key)
    rows.append(compare_text(case_id, "design_mapping", "all runs", "point_keys",
                             ";".join(sorted(map(str, native_keys))),
                             ";".join(sorted(map(str, local_keys))),
                             "Minitab native design factor columns (DIRECT)",
                             "MiniJMP design matrix and foldover lineage"))
    for key in sorted(local_keys & native_keys):
        local_row, native_row = local_by_key[key], native_by_key[key]
        row_key = f"{local_row['batch_id']}/{local_row['point_key']}/r{local_row['replicate']}"
        rows.append(compare_numeric(case_id, "input", row_key, "Y",
                                    native_row["Y"], local_row["Y"],
                                    "fixed response loaded into Minitab worksheet",
                                    "MiniJMP fixed input"))
        for name, native_name in zip(names, native_names):
            rows.append(compare_numeric(case_id, "design", local_row["batch_id"],
                                        f"{row_key}:{name}",
                                        native_row["settings"][native_name],
                                        local_row[f"{name}_code"],
                                        "Minitab native factor column (DIRECT)",
                                        "MiniJMP coded design row"))

    local_sources = {row["run_id"]: row["point_key"] for row in local_case["base_runs"]}
    for row in native_rows:
        if row["batch_id"] != "FOLD1":
            continue
        local_row = local_by_key[(row["batch_id"], row["point_key"], row["replicate"])]
        local_source = local_sources.get(local_row["source_run_id"])
        row_key = f"{row['batch_id']}/{row['point_key']}/r{row['replicate']}"
        rows.append(compare_text(case_id, "foldover_map", row_key, "source_point",
                                 row["source_point_key"], local_source,
                                 "Minitab factor flip mapped to base point (DERIVED)",
                                 "MiniJMP source_run_id lineage"))

    local_before, local_after = local_case["before_summary"], local_case["after_summary"]
    native_base = native_case["base_rows"]
    for phase, native_design, local_summary in (
            ("before", native_base, local_before),
            ("after", native_rows, local_after)):
        if case_id == "FOLD-REG":
            native_rank = polynomial_rank(native_design, case_id, True)
            local_rank = local_summary["model_rank"]
            rows.append(compare_numeric(case_id, f"{phase}_design", "full model", "rank",
                                        native_rank, local_rank,
                                        "DERIVED: Minitab native factor columns, all factorial terms",
                                        "MiniJMP foldover_summary"))
            count = len(native_base) if phase == "before" else sum(
                row["batch_id"] == "FOLD1" for row in native_rows)
            expected = (len(local_case["base_runs"]) if phase == "before" else
                        len(local_case["input_rows"]) - len(local_case["base_runs"]))
            rows.append(compare_numeric(case_id, f"{phase}_design", "runs", "count",
                                        count, expected,
                                        "Minitab native design columns (DIRECT)",
                                        "MiniJMP foldover design"))
        else:
            native_stats = confounding_counts(native_design, MTB_PB_FACTORS)
            local_stats = local_summary["before" if phase == "before" else "after"]
            for statistic in ("main_rank", "joint_rank"):
                rows.append(compare_numeric(case_id, f"{phase}_design", "PB12", statistic,
                                            native_stats[statistic], local_stats[statistic],
                                            "DERIVED: Minitab native PB factor matrix",
                                            "MiniJMP pb_foldover_summary"))
            rows.append(compare_numeric(
                case_id, f"{phase}_design", "two-factor interactions", "complete_confounding_count",
                native_stats["complete_confounding_count"], len(local_stats["complete"]),
                "DERIVED: Minitab native PB factor matrix",
                "MiniJMP pb_foldover_summary"))
            rows.append(compare_numeric(
                case_id, f"{phase}_design", "two-factor interactions", "estimable_count",
                native_stats["estimable_interaction_count"], len(local_stats["estimable"]),
                "DERIVED: Minitab native PB factor matrix",
                "MiniJMP pb_foldover_summary"))
            count = len(native_design)
            expected = local_summary["base_runs"] if phase == "before" else local_summary["total_runs"]
            rows.append(compare_numeric(case_id, f"{phase}_design", "PB12", "runs",
                                        count, expected,
                                        "Minitab native design columns (DIRECT)",
                                        "MiniJMP foldover design"))

    if case_id == "FOLD-PB":
        rows.append(compare_numeric(case_id, "before_statistics", "main effects", "inference",
                                    None, None, "saturated PB12 main-effects model (df=0)",
                                    "MiniJMP saturated PB12 main-effects model (df=0)"))

    local_analysis = local_case["after_analysis"]
    native_stats = derive_native_stats(native_case, local_case)
    local_rows = {(row["batch_id"], row["point_key"], row["replicate"]): row
                  for row in local_analysis["rows"]}
    native_rows_observed = {(row["batch_id"], row["point_key"], row["replicate"]): row
                            for row in native_rows}
    common_keys = sorted(set(local_rows) & set(native_rows_observed))
    local_matrix = np.asarray([local_rows[key]["matrix"] for key in common_keys], dtype=float)
    native_matrix = np.asarray([native_rows_observed[key]["matrix"] for key in common_keys], dtype=float)
    column_map = []
    for index in range(native_matrix.shape[1]):
        actual = native_matrix[:, index]
        matches = [(j, 1) for j in range(local_matrix.shape[1])
                   if np.allclose(actual, local_matrix[:, j], rtol=0, atol=1e-12)]
        matches += [(j, -1) for j in range(local_matrix.shape[1])
                    if np.allclose(actual, -local_matrix[:, j], rtol=0, atol=1e-12)]
        if len(matches) != 1:
            raise ValueError(f"{case_id} XMATRIX 列与 MiniJMP 项无法唯一映射: {index}, {matches}")
        column_map.append(matches[0])
    if len({index for index, _ in column_map}) != len(column_map):
        raise ValueError(f"{case_id} XMATRIX 含重复模型项")
    transformed_beta = np.zeros(len(local_analysis["terms"]))
    transformed_se = np.zeros_like(transformed_beta)
    transformed_t = np.zeros_like(transformed_beta)
    transformed_p = np.zeros_like(transformed_beta)
    for native_index, (local_index, sign) in enumerate(column_map):
        transformed_beta[local_index] = sign * native_stats["coefficients"][native_index]
        transformed_se[local_index] = native_stats["se"][native_index]
        transformed_t[local_index] = sign * native_stats["t"][native_index]
        transformed_p[local_index] = native_stats["coefficient_p"][native_index]
    basis_error = float(np.max(np.abs(native_matrix -
                                      np.column_stack([sign * local_matrix[:, index]
                                                       for index, sign in column_map]))))
    rows.append(compare_numeric(case_id, "model_space", "main-effects model", "rank",
                                native_stats["rank"], local_analysis["rank"],
                                "Minitab stored XMATRIX (DIRECT)",
                                "MiniJMP production model matrix"))
    rows.append(compare_numeric(case_id, "model_space", "main-effects model", "basis_error",
                                basis_error, 0.0,
                                "DERIVED: Minitab XMATRIX mapped to MiniJMP term basis",
                                "MiniJMP coded model matrix"))
    for statistic in ("n", "p", "df", "sse", "sst", "ssr", "mse", "model_f", "model_p"):
        local_value = {
            "n": local_analysis["n"], "p": local_analysis["p"],
            "df": local_analysis["df"], "sse": local_analysis["sse"],
            "sst": local_analysis["sst"], "ssr": local_analysis["ssr"],
            "mse": (local_analysis["inference"] or {}).get("mse"),
            "model_f": (local_analysis["inference"] or {}).get("f"),
            "model_p": (local_analysis["inference"] or {}).get("model_p"),
        }[statistic]
        rows.append(compare_numeric(case_id, "model_summary", "after foldover", statistic,
                                    native_stats[{"df": "df"}.get(statistic, statistic)], local_value,
                                    "DERIVED: Minitab XMATRIX, FITS/RESIDUALS and fixed response",
                                    "MiniJMP production analysis"))
    local_inference = local_analysis["inference"] or {}
    effects = local_analysis.get("effects") or []
    for index, term in enumerate(local_analysis["terms"]):
        rows.append(compare_numeric(case_id, "coefficient", term, "estimate",
                                    transformed_beta[index], local_analysis["coefficients"][index],
                                    "Minitab COEFFICIENTS transformed to MiniJMP basis (DIRECT)",
                                    "MiniJMP production coefficient"))
        rows.append(compare_numeric(case_id, "effect", term, "coded_effect",
                                    2 * transformed_beta[index] if index else None,
                                    effects[index] if index < len(effects) else None,
                                    "DERIVED: twice Minitab coded coefficient",
                                    "MiniJMP production effect"))
        rows.append(compare_numeric(case_id, "coefficient", term, "standard_error",
                                    transformed_se[index],
                                    (local_inference.get("se") or [None]*len(effects))[index]
                                    if local_inference else None,
                                    "DERIVED: Minitab XMATRIX and MSE",
                                    "MiniJMP production inference"))
        rows.append(compare_numeric(case_id, "coefficient", term, "t",
                                    transformed_t[index],
                                    (local_inference.get("t") or [None]*len(effects))[index]
                                    if local_inference else None,
                                    "DERIVED: Minitab coefficient and standard error",
                                    "MiniJMP production inference"))
        rows.append(compare_numeric(case_id, "coefficient", term, "p",
                                    transformed_p[index],
                                    (local_inference.get("p") or [None]*len(effects))[index]
                                    if local_inference else None,
                                    "DERIVED: two-sided Student t distribution",
                                    "MiniJMP production inference"))
        rows.append(compare_numeric(case_id, "coefficient", term, "F",
                                    transformed_t[index] ** 2,
                                    ((local_inference.get("t") or [None]*len(effects))[index] ** 2
                                     if local_inference else None),
                                    "DERIVED: Minitab t statistic squared (1 df)",
                                    "MiniJMP production t statistic squared"))
    for key in common_keys:
        local_row, native_row = local_rows[key], native_rows_observed[key]
        row_key = f"{key[0]}/{key[1]}/r{key[2]}"
        rows.append(compare_numeric(case_id, "run_statistics", row_key, "fit",
                                    native_row["coefficient_fit"], local_row["fit"],
                                    "Minitab FITS (DIRECT)", "MiniJMP fitted value"))
        rows.append(compare_numeric(case_id, "run_statistics", row_key, "residual",
                                    native_row["residual"], local_row["residual"],
                                    "Minitab RESIDUALS (DIRECT; Y−Fit)",
                                    "MiniJMP residual (Y−Fit)"))
    return rows


def write_report(rows, status, reason=""):
    unique = unique_rows(rows)
    counts = status_counts(unique)
    sources = {name: sum(name in row["minitab_value_source"] for row in unique)
               for name in ("DIRECT", "DERIVED", "DISPLAY")}
    lines = [
        "# 正规部分因子与 PB Foldover 对标验收", "",
        f"状态：**{status}**", "",
        "## 案例", "",
        "- `FOLD-REG`：3 因子、4-run 正规分数设计，C=AB；2 次重复后单因子 A 折叠，运行数 8→16。",
        "- `FOLD-PB`：PB12、11 个因子，全因子折叠，运行数 12→24。",
        "- 行序按因子设置、重复号及 BASE/FOLD1 批次映射；新增运行按翻转因子回链至来源运行。",
        "- Minitab 以 `FFDESIGN`/`PBDESIGN` 生成原设计，以 `MDESIGN; FOLD` 执行折叠；模型使用 `FFACTORIAL` 或 `SCREEN` 主效应项。",
        "- PB 的主效应模型不含二因子交互；其误差项包含未建模交互，结果按固定模型解释。PB12 基线饱和，常规推断 N/A。", "",
        "## 比较结果", "",
        f"唯一比较项：{len(unique)}；PASS/FAIL/N/A/UNSUPPORTED：{counts['PASS']}/{counts['FAIL']}/{counts['N/A']}/{counts['UNSUPPORTED']}。",
        "N/A 项为 PB12 基线无残差自由度，以及两个案例中的截距效应（截距不是因子效应）。",
        f"Minitab 来源计数（可重叠）：DIRECT/DERIVED/DISPLAY：{sources['DIRECT']}/{sources['DERIVED']}/{sources['DISPLAY']}。", "",
        "## 证据", "",
        "- 固定响应与运行映射见两份 `*_input.csv`；实际命令、COM 输出及工作表值分别见 `session_commands.txt`、`minitab_raw.txt` 和两侧 JSON。",
        "- 逐项数值比较见 `comparison.csv`。", "",
    ]
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
        print(f"Foldover supplemental {status}: {counts}; Minitab worker 已退出。", flush=True)
        return 0
    except Exception as error:
        write_comparison(COMPARISON, [])
        write_report([], "BLOCKED", f"{type(error).__name__}: {error}；请查看原始输出。")
        print(f"Foldover supplemental BLOCKED: {type(error).__name__}: {error}", flush=True)
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
        assert point_key((-1, 1, -1)) == "-1,1,-1"
        assert response_value("FOLD-REG", {"A": -1, "B": 1, "C": 1}, 1) \
            != response_value("FOLD-REG", {"A": -1, "B": 1, "C": 1}, 2)
        print("Foldover verifier self-check: PASS")
        raise SystemExit(0)
    raise SystemExit(parent_main())
