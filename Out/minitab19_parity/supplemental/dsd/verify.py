"""MiniJMP × Minitab 19 continuous DSD and stepwise parity case."""
from __future__ import annotations

import csv
import json
import math
import sys
import traceback
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SUPPLEMENTAL = HERE.parent
ROOT = SUPPLEMENTAL.parents[2]
PARITY = ROOT / "Out" / "minitab19_parity"
INPUT = HERE / "dsd_input.csv"
COMMANDS = HERE / "session_commands.txt"
RAW = HERE / "minitab_raw.txt"
MINIJMP = HERE / "minijmp_results.json"
MINITAB = HERE / "minitab_results.json"
COMPARISON = HERE / "comparison.csv"
REPORT = HERE / "acceptance.md"
CASE_ID = "DSD-6CONT-STEPWISE"
FACTORS = tuple(f"F{i}" for i in range(1, 7))
SQUARES = (("F1", "F1"), ("F2", "F2"), ("F3", "F3"))
INTERACTIONS = (("F1", "F2"),)
CANDIDATES = tuple((name,) for name in FACTORS) + SQUARES + INTERACTIONS
FULL_TERMS = (tuple((name,) for name in FACTORS)
              + tuple((name, name) for name in FACTORS)
              + tuple(combinations(FACTORS, 2)))
ALPHA_ENTER = 0.15
ALPHA_REMOVE = 0.15

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


def term_label(term):
    if term == ("截距",):
        return "截距"
    if len(term) == 2 and term[0] == term[1]:
        return f"{term[0]}²"
    return "*".join(term)


def point_key(values):
    return ",".join(f"{float(value):.12g}" for value in values)


def coded_term(label, row):
    if label == "截距":
        return 1.0
    if label.endswith("²"):
        value = float(row[label[:-1]])
        return value * value
    if "*" in label:
        value = 1.0
        for name in label.split("*"):
            value *= float(row[name])
        return value
    return float(row[label])


def dsd_spec():
    from doe_core import DesignSpec, FactorSpec

    factors = tuple(FactorSpec(name, name, -1, 1) for name in FACTORS)
    identity = {
        "construction_id": "dsd6.v1", "source_kind": "mathematical_construction",
        "source_id": "conference.dsd6", "matrix_sha256": "0" * 64,
    }
    return DesignSpec("minitab19-dsd-parity", factors, ("Y",), seed=31,
                      design_type="definitive_screening", screening_matrix=identity)


def response_value(row, error):
    a, b, c, d, e, f = (float(row[name]) for name in FACTORS)
    return (50 + 4*a - 3*b + 2*c + 1.5*d - e + .5*f
            + 4*a*a - 3*b*b + 2*c*c + 2.5*a*b + error)


def minijmp_worker():
    import pandas as pd

    sys.path.insert(0, str(ROOT / "code"))
    from doe_dsd import create_dsd
    from doe_screening_analysis import analyze_dsd
    from doe_stepwise import select_dsd_stepwise

    frame, metadata = create_dsd(dsd_spec(), replicates=2)
    run_column = metadata["column_map"]["run_id"]
    standard_column = metadata["column_map"]["standard_order"]
    order_column = metadata["column_map"]["run_order"]
    factor_columns = metadata["column_map"]["factors"]
    rows = []
    for _, source in frame.iterrows():
        values = {name: float(source[factor_columns[name]]) for name in FACTORS}
        rows.append({"run_id": str(source[run_column]),
                     "standard_order": int(source[standard_column]),
                     "run_order": int(source[order_column]),
                     "point_key": point_key(values.values()), **values})
    occurrence = defaultdict(int)
    for row in sorted(rows, key=lambda item: (item["standard_order"], item["run_order"])):
        occurrence[row["point_key"]] += 1
        row["point_occurrence"] = occurrence[row["point_key"]]
    if set(Counter(row["point_key"] for row in rows).values()) != {2}:
        raise AssertionError("DSD 6 因子两次重复必须使每个设计点恰有两次观测")

    noise_order = sorted({row["point_key"] for row in rows})
    amplitude = {key: .2 + .03 * (index % 7) for index, key in enumerate(noise_order)}
    y_by_key = {}
    for row in rows:
        error = amplitude[row["point_key"]] * (1 if row["point_occurrence"] == 1 else -1)
        row["Y"] = response_value(row, error)
        y_by_key[(row["point_key"], row["point_occurrence"])] = row["Y"]
    for row in rows:
        source_index = frame.index[frame[run_column] == row["run_id"]][0]
        frame.loc[source_index, metadata["column_map"]["responses"]["Y"]] = y_by_key[
            (row["point_key"], row["point_occurrence"])]
    rows.sort(key=lambda item: (item["standard_order"], item["run_order"]))
    fields = ("run_id", "standard_order", "run_order", "point_occurrence",
              "point_key", *FACTORS, "Y")
    with INPUT.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    full = analyze_dsd(frame, metadata, "Y", FULL_TERMS)
    selected = select_dsd_stepwise(
        frame, metadata, "Y", candidates=CANDIDATES,
        alpha_enter=ALPHA_ENTER, alpha_remove=ALPHA_REMOVE,
    )
    final = selected["analysis"]
    selected_labels = [term_label(tuple(term)) for term in selected["selected_terms"]]
    expected_labels = [term_label(term) for term in CANDIDATES]
    if set(selected_labels) != set(expected_labels):
        raise AssertionError(f"固定 DSD 响应未选择预定项: {selected_labels}")
    if full["n"] != 26 or full["rank"] != 13 or final["rank"] != 11:
        raise AssertionError(
            f"DSD 参考模型形状不符: full={full['n']}×{full['p']}, "
            f"rank={full['rank']}; selected rank={final['rank']}")
    if final["df"] <= 0 or final["sse"] <= 0 or final["inference"] is None:
        raise AssertionError("固定响应必须保留非零误差平方和及推断自由度")

    by_run = {row["run_id"]: row for row in rows}
    local_occurrence = {}
    for row in frame.to_dict("records"):
        run_id = str(row[run_column])
        native = by_run[run_id]
        local_occurrence[run_id] = native["point_occurrence"]

    def records(analysis):
        output = []
        labels = ["截距", *[
            term_label(tuple(term)) for term in
            (selected["selected_terms"] if analysis is final else FULL_TERMS)
        ]]
        for index, (_, source) in enumerate(frame.iterrows()):
            values = {name: float(source[factor_columns[name]]) for name in FACTORS}
            key = point_key(values.values())
            run_id = str(source[run_column])
            output.append({
                "point_key": key, "point_occurrence": local_occurrence[run_id],
                "Y": float(source[metadata["column_map"]["responses"]["Y"]]),
                "matrix": [float(value) for value in analysis["fit_matrix"][index]],
                "fitted": float(analysis["fitted"][index]),
                "residual": float(analysis["residuals"][index]),
            })
        return {f"{row['point_key']}|{row['point_occurrence']}": row for row in output}, labels

    full_rows, full_labels = records(full)
    final_rows, final_labels = records(final)
    if final_labels != final["names"]:
        raise AssertionError(f"MiniJMP 选定模型列标记不一致: {final_labels} != {final['names']}")
    inference = final["inference"]
    coefficients = {name: float(value) for name, value in zip(final["names"], final["coefficients"])}
    infer_stats = {
        name: {metric: float(inference[field][index])
               for metric, field in (("se", "se"), ("t", "t"), ("p", "p"))}
        for index, name in enumerate(final["names"])
    }
    result = {
        "case_id": CASE_ID, "design_type": "definitive_screening",
        "design_command": "MiniJMP create_dsd(DSD6, replicates=2)",
        "design_rows": rows, "n": int(final["n"]),
        "full_model": {"labels": full_labels, "rank": int(full["rank"]),
                       "matrix_rows": full_rows},
        "stepwise": {
            "method": selected["method"], "alpha_enter": ALPHA_ENTER,
            "alpha_remove": ALPHA_REMOVE, "hierarchy": "strong; one term per step",
            "candidate_terms": [term_label(term) for term in CANDIDATES],
            "selected_terms": selected_labels,
            "steps": [{"action": step["action"], "term": step["label"],
                       "p": float(step["p"])} for step in selected["selection_steps"]],
            "stop_reason": selected["stop_reason"],
        },
        "final_model": {
            "labels": final_labels, "n": int(final["n"]),
            "rank": int(final["rank"]),
            "error_df": int(final["df"]), "coefficients": coefficients,
            "inference": infer_stats, "matrix_rows": final_rows,
            "sse": float(final["sse"]), "sst": float(final["sst"]),
            "ssr": float(final["ssr"]), "mse": float(inference["mse"]),
            "s": math.sqrt(float(inference["mse"])),
            "model_f": float(inference["f"]), "model_p": float(inference["model_p"]),
            "r2": 1 - float(final["sse"]) / float(final["sst"]),
            "adjusted_r2": 1 - (final["sse"] / final["df"])
            / (final["sst"] / (final["n"] - 1)),
        },
    }
    write_json(MINIJMP, result)
    print(f"MiniJMP DSD self-check: 26 rows; full second-order rank {full['rank']}; "
          f"selected rank {final['rank']}; error df {final['df']}; fixed hierarchy PASS",
          flush=True)


def native_term_command(label, columns):
    if label == "截距":
        return None
    if label.endswith("²"):
        column = columns[label[:-1]]
        return f"C{column}*C{column}"
    if "*" in label:
        left, right = label.split("*")
        return f"C{columns[left]}*C{columns[right]}"
    return f"C{columns[label]}"


def minitab_worker():
    raw = []
    session = None
    try:
        input_rows = list(csv.DictReader(INPUT.open(newline="", encoding="utf-8-sig")))
        source_by_key = {
            (row["point_key"], int(row["point_occurrence"])): row for row in input_rows
        }
        levels = " ".join("-1 1" for _ in FACTORS)
        names = " ".join(f'"{name}"' for name in FACTORS)
        design_command = (
            f"DSDESIGN {len(FACTORS)};\n  REPLICATES 2;\n  LEVELS {levels};\n"
            f"  RANDOMIZE 31;\n  FNAME {names};\n  BRIEF 3."
        )
        session = MinitabSession()
        design_output = session.execute(design_command, "DSDESIGN")
        factor_columns = {name: session.find_column((name,)) for name in FACTORS}
        standard_col = session.find_column(("StdOrder", "StandardOrder", "标准序"))
        run_col = session.find_column(("RunOrder", "运行序"))
        count = len(session.column_values(factor_columns[FACTORS[0]]))
        standard = session.column_values(standard_col)
        run_order = session.column_values(run_col)
        factor_values = {name: session.column_values(factor_columns[name]) for name in FACTORS}
        if (count != len(input_rows) or len(standard) != count or len(run_order) != count
                or any(len(values) != count for values in factor_values.values())):
            raise RuntimeError("Minitab DSD 设计列长度与固定输入不符")
        native_rows = []
        for index in range(count):
            values = {name: factor_values[name][index] for name in FACTORS}
            native_rows.append({
                "worksheet_row": index + 1, "standard_order": int(standard[index]),
                "run_order": int(run_order[index]), "point_key": point_key(values.values()),
                **values,
            })
        occurrences = defaultdict(int)
        for row in sorted(native_rows,
                          key=lambda item: (item["standard_order"], item["run_order"])):
            occurrences[row["point_key"]] += 1
            row["point_occurrence"] = occurrences[row["point_key"]]
            source = source_by_key.get((row["point_key"], row["point_occurrence"]))
            if source is not None:
                row["Y"] = float(source["Y"])
        native_keys = {(row["point_key"], row["point_occurrence"]) for row in native_rows}
        design_match = native_keys == set(source_by_key)
        raw.append("===== DSDESIGN worksheet columns =====\n"
                   + json.dumps(native_rows, ensure_ascii=False, indent=2))
        if not design_match:
            result = {
                "version": session.version, "app_path": session.app_path,
                "process_path": session.process_path, "design_command": design_command,
                "design_match": False, "design_rows": native_rows,
                "design_columns": [str(session.columns.Item(i).Name)
                                   for i in range(1, int(session.columns.Count) + 1)],
            }
            raw.append("Minitab DSD point set differs from the fixed MiniJMP input.")
            write_json(MINITAB, result)
            COMMANDS.write_text(
                "# Minitab 19.1.0.1 official Session Commands (DSDESIGN, SCREEN)\n\n"
                + design_command + "\n", encoding="utf-8")
            RAW.write_text("\n\n".join([*session.raw, *raw]) + "\n", encoding="utf-8")
            return 0

        worksheet_order = {row["worksheet_row"]: row for row in native_rows}
        y_values = [worksheet_order[index + 1]["Y"] for index in range(count)]
        response_column = session.add_column("Y", y_values)
        fit_column = session.add_column("Fit")
        residual_column = session.add_column("Resid")
        coefficient_column = session.add_column("Coef")
        candidate_labels = [term_label(term) for term in CANDIDATES]
        model_terms = " ".join(
            native_term_command(label, factor_columns) for label in candidate_labels)
        factor_terms = " ".join(f"C{factor_columns[name]}" for name in FACTORS)
        matrix_name = "M1"
        screen_command = (
            "SCREEN;\n"
            f"  RESPONSE C{response_column};\n  FACTOR {factor_terms};\n"
            f"  TERMS {model_terms};\n  LEVELS {levels};\n  INUNIT 0;\n"
            "  STEPWISE;\n"
            f"  AENTER {ALPHA_ENTER};\n  AREMOVE {ALPHA_REMOVE};\n"
            "  HIERARCHICAL;\n  ALLTERMS;\n  ALWAYS;\n  SINGLE;\n"
            "  TMSDETAILS;\n  FULL;\n  TCOEFFICIENT;\n  TANOVA;\n  TSUMMARY;\n"
            f"  FITS C{fit_column};\n  RESIDUALS C{residual_column};\n"
            f"  COEFFICIENTS C{coefficient_column};\n  XMATRIX {matrix_name}."
        )
        screen_output = session.execute(screen_command, "SCREEN STEPWISE")
        model_matrix = session.read_matrix(matrix_name)
        p = len(model_matrix[0])
        if any(len(row) != p for row in model_matrix):
            raise RuntimeError("Minitab XMATRIX 行宽不一致")
        expected_by_label = {"截距": [1.0] * count}
        for label in candidate_labels:
            expected_by_label[label] = [coded_term(label, row) for row in native_rows]
        term_columns = {}
        for column in range(p):
            actual = [row[column] for row in model_matrix]
            matches = [label for label, values in expected_by_label.items()
                       if np.allclose(actual, values, rtol=0, atol=1e-12)]
            if len(matches) != 1 or matches[0] in term_columns:
                raise RuntimeError(f"Minitab SCREEN XMATRIX 项映射不唯一: {column}: {matches}")
            term_columns[matches[0]] = column
        if "截距" not in term_columns:
            raise RuntimeError("Minitab SCREEN XMATRIX 缺少截距列")
        coefficients_raw = session.column_values(coefficient_column)
        fits = session.column_values(fit_column)
        residuals = session.column_values(residual_column)
        if len(coefficients_raw) < p or len(fits) != count or len(residuals) != count:
            raise RuntimeError("Minitab SCREEN 系数、拟合值或残差存储长度不符")
        coefficients = {label: coefficients_raw[index]
                        for label, index in term_columns.items()}
        for index, row in enumerate(native_rows):
            row["fit"] = fits[index]
            row["residual"] = residuals[index]
        native_matrix_rows = {
            f"{row['point_key']}|{row['point_occurrence']}": {
                "point_key": row["point_key"], "point_occurrence": row["point_occurrence"],
                "matrix": model_matrix[index], "Y": row["Y"],
                "fitted": fits[index], "residual": residuals[index],
            }
            for index, row in enumerate(native_rows)
        }
        full_matrix = [[coded_term(label, row) for label in json.loads(MINIJMP.read_text(
            encoding="utf-8"))["full_model"]["labels"]] for row in native_rows]
        if not screen_output.strip():
            raise RuntimeError("Minitab SCREEN 未返回可读选择/ANOVA 输出")
        result = {
            "version": session.version, "app_path": session.app_path,
            "process_path": session.process_path, "design_match": True,
            "design_command": design_command, "screen_command": screen_command,
            "design_columns": [str(session.columns.Item(i).Name)
                               for i in range(1, int(session.columns.Count) + 1)],
            "design_rows": native_rows, "full_model": {
                "labels": json.loads(MINIJMP.read_text(encoding="utf-8"))["full_model"]["labels"],
                "rank": int(np.linalg.matrix_rank(np.asarray(full_matrix, dtype=float))),
                "matrix_rows": {
                    f"{row['point_key']}|{row['point_occurrence']}": {
                        "point_key": row["point_key"],
                        "point_occurrence": row["point_occurrence"],
                        "matrix": full_matrix[index],
                    } for index, row in enumerate(native_rows)
                },
            },
            "term_columns": term_columns, "model_matrix": model_matrix,
            "rank": int(np.linalg.matrix_rank(np.asarray(model_matrix, dtype=float))),
            "coefficients": coefficients, "matrix_rows": native_matrix_rows,
        }
        write_json(MINITAB, result)
        COMMANDS.write_text(
            "# Minitab 19.1.0.1 official Session Commands PDF, release 19.1\n"
            "# DSDDESIGN creates the native 6-factor design; SCREEN performs stepwise DOE analysis.\n\n"
            + design_command + "\n\n" + screen_command + "\n",
            encoding="utf-8")
        RAW.write_text("\n\n".join([*session.raw, *raw]) + "\n", encoding="utf-8")
        print(f"Minitab {session.version} DSDESIGN/SCREEN: {count} rows; "
              f"selected model rank {result['rank']}; direct XMATRIX/COEF/FITS/RESIDUALS",
              flush=True)
        return 0
    except Exception:
        raw.append("===== worker exception =====\n" + traceback.format_exc())
        if session is not None:
            RAW.write_text("\n\n".join([*session.raw, *raw]) + "\n", encoding="utf-8")
        else:
            RAW.write_text("\n\n".join(raw) + "\n", encoding="utf-8")
        traceback.print_exc()
        return 1
    finally:
        if session is not None:
            session.release()


def derive_native_stats(native):
    from scipy import stats

    matrix = np.asarray(native["model_matrix"], dtype=float)
    n, p = matrix.shape
    rank = int(np.linalg.matrix_rank(matrix))
    rows = list(native["design_rows"])
    response = np.asarray([row["Y"] for row in rows], dtype=float)
    fits = np.asarray([row["fit"] for row in rows], dtype=float)
    residuals = np.asarray([row["residual"] for row in rows], dtype=float)
    np.testing.assert_allclose(response - fits, residuals, rtol=0, atol=2e-9)
    sse = float(residuals @ residuals)
    sst = float(np.sum((response - response.mean()) ** 2))
    ssr = sst - sse
    df = n - rank
    mse = sse / df
    covariance = np.linalg.inv(matrix.T @ matrix)
    labels = {index: label for label, index in native["term_columns"].items()}
    coefficients = native["coefficients"]
    inference = {}
    for index, label in labels.items():
        se = math.sqrt(float(covariance[index, index]) * mse)
        t_value = float(coefficients[label]) / se
        inference[label] = {
            "se": se, "t": t_value,
            "p": float(2 * stats.t.sf(abs(t_value), df)),
            "ss": t_value * t_value * mse,
            "f": t_value * t_value,
            "fp": float(stats.f.sf(t_value * t_value, 1, df)),
        }
    model_df = rank - 1
    model_f = (ssr / model_df) / mse
    return {
        "n": n, "p": p, "rank": rank, "model_df": model_df,
        "error_df": df, "total_df": n - 1, "sse": sse, "sst": sst,
        "ssr": ssr, "mse": mse, "s": math.sqrt(mse),
        "model_f": model_f,
        "model_p": float(stats.f.sf(model_f, model_df, df)),
        "r2": 1 - sse / sst,
        "adjusted_r2": 1 - (sse / df) / (sst / (n - 1)),
        "inference": inference,
    }


def compare_case(local, native):
    rows = []
    direct_design = "Minitab DSDDESIGN worksheet factor columns (DIRECT)"
    derived_matrix = "DERIVED: Minitab DSDDESIGN factor columns in the declared polynomial basis"
    direct_matrix = "Minitab SCREEN XMATRIX M1 (DIRECT)"
    direct_fit = "Minitab SCREEN FITS/RESIDUALS worksheet columns (DIRECT)"
    direct_coef = "Minitab SCREEN COEFFICIENTS worksheet column (DIRECT)"
    derived_stats = "DERIVED: Minitab XMATRIX, fixed Y, FITS/RESIDUALS; t/F distributions"

    if not native.get("design_match"):
        local_counts = Counter(row["point_key"] for row in local["design_rows"])
        mtb_counts = Counter(row["point_key"] for row in native["design_rows"])
        for key in sorted(set(local_counts) | set(mtb_counts)):
            rows.append(compare_numeric(
                CASE_ID, "design", key, "point_multiplicity", mtb_counts[key],
                local_counts[key], direct_design, "MiniJMP create_dsd coded settings"))
        return rows

    local_design = {
        f"{row['point_key']}|{row['point_occurrence']}": row
        for row in local["design_rows"]
    }
    native_design = {
        f"{row['point_key']}|{row['point_occurrence']}": row
        for row in native["design_rows"]
    }
    if set(local_design) != set(native_design):
        raise ValueError("design_match 声明与实际点/重复键不一致")
    rows.append(compare_numeric(CASE_ID, "design", "DSD", "run_count",
                                len(native_design), len(local_design), direct_design,
                                "MiniJMP create_dsd"))
    rows.append(compare_numeric(CASE_ID, "design", "DSD", "unique_points",
                                len({row['point_key'] for row in native_design.values()}),
                                len({row['point_key'] for row in local_design.values()}),
                                direct_design, "MiniJMP create_dsd"))
    for key in sorted(local_design):
        left, right = native_design[key], local_design[key]
        for name in FACTORS:
            rows.append(compare_numeric(CASE_ID, "design", key, name,
                                        left[name], right[name], direct_design,
                                        "MiniJMP create_dsd coded settings"))
        rows.append(compare_numeric(CASE_ID, "input", key, "Y", left["Y"], right["Y"],
                                    "Minitab worksheet Y loaded from fixed CSV mapping",
                                    "MiniJMP fixed response input"))

    local_full = local["full_model"]
    native_full = native["full_model"]
    if local_full["labels"] != native_full["labels"]:
        raise ValueError("全候选二阶模型项顺序不一致")
    rows.append(compare_numeric(CASE_ID, "full_model", "all_main_square_2fi", "rank",
                                native_full["rank"], local_full["rank"], derived_matrix,
                                "MiniJMP analyze_dsd model matrix"))
    for key in sorted(local_full["matrix_rows"]):
        left = native_full["matrix_rows"][key]["matrix"]
        right = local_full["matrix_rows"][key]["matrix"]
        for column, label in enumerate(local_full["labels"]):
            rows.append(compare_numeric(CASE_ID, "full_model_matrix", key, label,
                                        left[column], right[column], derived_matrix,
                                        "MiniJMP analyze_dsd model matrix"))

    minijmp_selection = local["stepwise"]
    native_selection = sorted(label for label in native["term_columns"] if label != "截距")
    rows.append(compare_text(CASE_ID, "stepwise", "selected terms", "model_terms",
                             ";".join(native_selection),
                             ";".join(sorted(minijmp_selection["selected_terms"])),
                             "Minitab SCREEN STEPWISE final XMATRIX columns (DIRECT)",
                             "MiniJMP select_dsd_stepwise"))
    rows.append(compare_text(CASE_ID, "stepwise", "method", "procedure",
                             "STEPWISE", minijmp_selection["method"].upper(),
                             "Minitab SCREEN STEPWISE command",
                             "MiniJMP select_dsd_stepwise"))
    rows.append(compare_numeric(CASE_ID, "stepwise", "alpha", "enter",
                                ALPHA_ENTER, minijmp_selection["alpha_enter"],
                                "Minitab SCREEN AENTER", "MiniJMP select_dsd_stepwise"))
    rows.append(compare_numeric(CASE_ID, "stepwise", "alpha", "remove",
                                ALPHA_REMOVE, minijmp_selection["alpha_remove"],
                                "Minitab SCREEN AREMOVE", "MiniJMP select_dsd_stepwise"))
    rows.append(compare_text(CASE_ID, "stepwise", "hierarchy", "rule",
                             "ALLTERMS; ALWAYS; SINGLE",
                             "ALLTERMS; ALWAYS; SINGLE",
                             "Minitab SCREEN hierarchy subcommands",
                             "MiniJMP select_dsd_stepwise contract"))

    local_final = local["final_model"]
    native_stats = derive_native_stats(native)
    local_matrix = {
        f"{row['point_key']}|{row['point_occurrence']}": row
        for row in local_final["matrix_rows"].values()
    }
    native_matrix = native["matrix_rows"]
    for key in sorted(local_matrix):
        left, right = native_matrix[key], local_matrix[key]
        for label, column in native["term_columns"].items():
            local_column = local_final["labels"].index(label)
            rows.append(compare_numeric(CASE_ID, "selected_model_matrix", key, label,
                                        left["matrix"][column], right["matrix"][local_column],
                                        direct_matrix, "MiniJMP analyze_dsd selected model"))
        rows.append(compare_numeric(CASE_ID, "run_statistics", key, "fit",
                                    left["fitted"], right["fitted"], direct_fit,
                                    "MiniJMP analyze_dsd fitted"))
        rows.append(compare_numeric(CASE_ID, "run_statistics", key, "residual",
                                    left["residual"], right["residual"], direct_fit,
                                    "MiniJMP analyze_dsd residual"))
    for label in native["term_columns"]:
        rows.append(compare_numeric(CASE_ID, "coefficient", label, "estimate",
                                    native["coefficients"][label],
                                    local_final["coefficients"][label], direct_coef,
                                    "MiniJMP analyze_dsd coefficients"))
        for statistic in ("se", "t", "p"):
            rows.append(compare_numeric(CASE_ID, "coefficient_inference", label, statistic,
                                        native_stats["inference"][label][statistic],
                                        local_final["inference"][label][statistic], derived_stats,
                                        "MiniJMP analyze_dsd inference"))
        if label != "截距":
            for statistic, value in (("ss", "ss"), ("f", "f"), ("p", "fp")):
                rows.append(compare_numeric(CASE_ID, "anova_term", label, statistic,
                                            native_stats["inference"][label][value],
                                            (local_final["inference"][label]["t"] ** 2
                                             * local_final["mse"]
                                             if statistic == "ss" else
                                             local_final["inference"][label]["t"] ** 2
                                             if statistic == "f" else
                                             local_final["inference"][label]["p"]),
                                            derived_stats, "MiniJMP analyze_dsd inference"))
    for statistic, left, right in (
        ("rank", native_stats["rank"], local_final["rank"]),
        ("error_df", native_stats["error_df"], local_final["error_df"]),
        ("SSE", native_stats["sse"], local_final["sse"]),
        ("SST", native_stats["sst"], local_final["sst"]),
        ("model_SS", native_stats["ssr"], local_final["ssr"]),
        ("MSE", native_stats["mse"], local_final["mse"]),
        ("S", native_stats["s"], local_final["s"]),
        ("model_F", native_stats["model_f"], local_final["model_f"]),
        ("model_P", native_stats["model_p"], local_final["model_p"]),
        ("R2", native_stats["r2"],
         1 - local_final["sse"] / local_final["sst"]),
        ("adjusted_R2", native_stats["adjusted_r2"],
         1 - (local_final["sse"] / local_final["error_df"])
         / (local_final["sst"] / (local_final["n"] - 1))),
    ):
        rows.append(compare_numeric(CASE_ID, "anova_summary", "model", statistic,
                                    left, right, derived_stats, "MiniJMP analyze_dsd"))
    return rows


def write_report(rows, status, reason=""):
    unique = unique_rows(rows)
    counts = status_counts(unique)
    source_counts = {
        name: sum(name in row["minitab_value_source"] for row in unique)
        for name in ("DIRECT", "DERIVED", "DISPLAY")
    }
    lines = [
        "# DSD 连续因子与逐步选模对标验收", "",
        f"状态：**{status}**", "",
        "## 固定案例", "",
        "- Minitab：19.1.0.1；官方 Session Commands：`DSDESIGN`、`SCREEN`。",
        "- 设计：6 个连续因子、两次重复、13 个基础点，共 26 行；编码为 -1/0/+1。",
        "- 响应：固定模型含 6 个主效应、F1²/F2²/F3² 和 F1×F2；同一点两次观测加入相反的固定误差，保留非零纯误差。",
        "- 二阶完整候选矩阵有 28 列；其秩与 28 不同表示部分交互不能在同一完整模型中单独估计。",
        f"- 选模：STEPWISE，进入/移除 α={ALPHA_ENTER}，强层级，每步单项进出；候选项 {len(CANDIDATES)} 个。",
        "", "## 对标结果", "",
        f"唯一比较项：{len(unique)}；PASS/FAIL/N/A/UNSUPPORTED："
        f"{counts['PASS']}/{counts['FAIL']}/{counts['N/A']}/{counts['UNSUPPORTED']}。",
        f"来源计数（可重叠）：DIRECT/DERIVED/DISPLAY："
        f"{source_counts['DIRECT']}/{source_counts['DERIVED']}/{source_counts['DISPLAY']}。",
        "MiniJMP 与 Minitab 的运行序允许不同；按因子点和重复出现次序映射。",
        "", "## 实际 Minitab Session Commands", "",
        "详见 `session_commands.txt`；原始 Outputs/OutputDocument 见 `minitab_raw.txt`。",
        "", "## 证据文件", "",
        "- `dsd_input.csv`：固定响应及其设计点映射。",
        "- `minitab_results.json`、`minijmp_results.json`：原生与生产 API 高精度结果。",
        "- `comparison.csv`：按 (case_id, section, term, statistic) 去重的逐项结果。",
    ]
    if reason:
        lines.extend(["", "## 未完成原因", "", reason])
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return status, counts


def parent_main():
    try:
        run_worker(Path(__file__), "--minijmp-worker", timeout=240)
        run_worker(Path(__file__), "--com-worker", timeout=360)
        local = json.loads(MINIJMP.read_text(encoding="utf-8"))
        native = json.loads(MINITAB.read_text(encoding="utf-8"))
        rows = compare_case(local, native)
        write_comparison(COMPARISON, rows)
        status = "FAIL" if any(row["status"] == "FAIL" for row in unique_rows(rows)) else "PASS"
        status, counts = write_report(rows, status)
        print(f"DSD supplemental {status}: {counts}; Minitab PID 已退出。", flush=True)
        return 0
    except Exception as error:
        write_comparison(COMPARISON, [])
        write_report([], "BLOCKED", f"{type(error).__name__}: {error}；请查看控制台和原始输出。")
        print(f"DSD supplemental BLOCKED: {type(error).__name__}: {error}", flush=True)
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
        assert len(CANDIDATES) == 10 and len(FULL_TERMS) == 27
        assert term_label(("F2", "F2")) == "F2²"
        assert term_label(("F1", "F2")) == "F1*F2"
        assert coded_term("F1²", {"F1": -1}) == 1
        print("DSD verifier self-check: PASS")
        raise SystemExit(0)
    raise SystemExit(parent_main())
