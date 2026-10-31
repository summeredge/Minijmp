"""MiniJMP × Minitab 19 mixed-level General Full Factorial parity."""
from __future__ import annotations

import csv
import json
import math
import sys
import traceback
from collections import Counter, defaultdict
from itertools import product
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SUPPLEMENTAL = HERE.parent
ROOT = SUPPLEMENTAL.parents[2]
CASE_IDS = ("GFF-2X3", "GFF-TYPEIII")
INPUTS = {case: HERE / f"{case.lower().replace('-', '_')}_input.csv" for case in CASE_IDS}
COMMANDS = HERE / "session_commands.txt"
RAW = HERE / "minitab_raw.txt"
MINIJMP = HERE / "minijmp_results.json"
MINITAB = HERE / "minitab_results.json"
COMPARISON = HERE / "comparison.csv"
REPORT = HERE / "acceptance.md"
FACTOR_IDS = ("A", "B")
TERM_NAMES = ("A", "B", "A*B")

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
    if isinstance(value, (list, tuple)):
        return [clean(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    return value


def code_for(level, levels):
    return levels.index(level) + 1


def contrast_columns(values, levels):
    base = levels[0]
    return np.column_stack([
        [1.0 if value == level else -1.0 if value == base else 0.0 for value in values]
        for level in levels[1:]
    ])


def model_matrix(factors, runs):
    n = len(runs)
    bases = {}
    for factor in factors:
        values = [run["settings"][factor["factor_id"]] for run in runs]
        bases[factor["factor_id"]] = contrast_columns(values, factor["levels"])

    columns = [np.ones(n)]
    labels = ["截距"]
    groups = {"截距": [0, 1]}
    for factor in factors:
        name = factor["factor_id"]
        start = len(columns)
        for level, column in zip(factor["levels"][1:], bases[name].T):
            columns.append(column)
            labels.append(f"{name}[{level}]")
        groups[name] = [start, len(columns)]
    start = len(columns)
    left, right = (factor["factor_id"] for factor in factors)
    for left_index, left_level in enumerate(factors[0]["levels"][1:]):
        for right_index, right_level in enumerate(factors[1]["levels"][1:]):
            columns.append(bases[left][:, left_index] * bases[right][:, right_index])
            labels.append(f"{left}[{left_level}]*{right}[{right_level}]")
    groups[f"{left}*{right}"] = [start, len(columns)]
    return np.column_stack(columns), labels, groups


def observation_key(a_code, b_code, replicate):
    return f"{int(a_code)}|{int(b_code)}|{int(replicate)}"


def general_spec(kind):
    from doe_core import DesignSpec, FactorSpec

    if kind == "GFF-2X3":
        factors = (
            FactorSpec("A", "开关", None, None, factor_type="categorical",
                       levels=("low", "high")),
            FactorSpec("B", "温度", None, None, factor_type="categorical",
                       levels=(100, 150, 200), level_type="numeric"),
        )
        seed, replicates = 1, 2
    else:
        factors = (
            FactorSpec("A", "开关", None, None, factor_type="categorical",
                       levels=("off", "on")),
            FactorSpec("B", "温度", None, None, factor_type="categorical",
                       levels=(100, 150, 200), level_type="numeric"),
        )
        seed, replicates = 19, 3
    spec = DesignSpec(kind, factors, ("Y",), seed=seed,
                      design_type="general_full_factorial")
    return spec, replicates


def _set_two_by_three(frame, case):
    lookup = {
        (row["A"], row["B"], int(row["replicate"])): float(row["Y"])
        for row in case["rows"]
    }
    for index, row in frame.iterrows():
        key = (row["设定_A"], row["设定_B"], int(row["重复"]))
        frame.loc[index, "响应_Y"] = lookup[key]


def _set_type_iii_response(frame):
    a_code = np.asarray([1 if value == "on" else -1 for value in frame["设定_A"]])
    b_code = np.asarray([{100: -1, 150: 0, 200: 1}[value]
                         for value in frame["设定_B"]])
    replicate = frame["重复"].to_numpy(dtype=int)
    noise = np.choose(replicate - 1, [-1.2, .35, 1.4]) * (1 + .1*a_code - .08*b_code)
    response = 25 + 2*a_code + b_code - 1.5*a_code*b_code + noise
    frame["响应_Y"] = response
    missing_index = frame.index[0]
    frame.loc[missing_index, "响应_Y"] = None
    return str(frame.loc[missing_index, "运行ID"])


def design_rows(frame, metadata):
    # Restored metadata is authoritative for typed categorical level order.
    from doe_core import restore_design_result
    design = restore_design_result(frame, metadata)
    factors = [{"factor_id": factor.factor_id, "levels": factor.levels}
               for factor in design.spec.factors]
    records = []
    for run in design.runs:
        settings = {factor.factor_id: run.settings[factor.factor_id]
                    for factor in design.spec.factors}
        codes = {name: code_for(settings[name],
                                next(factor["levels"] for factor in factors
                                     if factor["factor_id"] == name))
                 for name in FACTOR_IDS}
        records.append({
            "run_id": run.run_id, "standard_order": int(run.standard_order),
            "run_order": int(run.run_order), "replicate": int(run.replicate),
            "A": settings["A"], "B": settings["B"],
            "A_code": codes["A"], "B_code": codes["B"],
            "Y": run.responses["Y"],
            "point_key": observation_key(codes["A"], codes["B"], run.replicate),
        })
    return design, factors, records


def summarize_analysis(result, rows, factors, groups):
    observed = result["observed_runs"]
    x, labels, actual_groups = model_matrix(factors, [
        {"settings": run.settings} for run in observed
    ])
    if actual_groups != groups:
        raise AssertionError("Type I/III 模型项列组不一致")
    fitted = np.asarray(result["fitted"], dtype=float)
    residual = np.asarray(result["residuals"], dtype=float)
    model_rows = {}
    for index, run in enumerate(observed):
        a_code = code_for(run.settings["A"], factors[0]["levels"])
        b_code = code_for(run.settings["B"], factors[1]["levels"])
        key = observation_key(a_code, b_code, run.replicate)
        model_rows[key] = {
            "point_key": key, "standard_order": int(run.standard_order),
            "run_order": int(run.run_order), "replicate": int(run.replicate),
            "A": run.settings["A"], "B": run.settings["B"],
            "A_code": a_code, "B_code": b_code,
            "Y": float(run.responses["Y"]),
            "matrix": x[index].tolist(), "fit": float(fitted[index]),
            "residual": float(residual[index]),
        }
    anova = result["anova"]
    return {
        "ss_type": result["ss_type"], "n": int(result["n"]),
        "p": int(result["p"]), "rank": int(result["rank"]),
        "error_df": int(result["df"]), "sse": float(result["sse"]),
        "sst": float(result["sst"]), "ssr": float(result["ssr"]),
        "anova": clean(anova), "inference": clean(result["inference"]),
        "coefficients": clean(result["coefficients"]), "names": result["names"],
        "labels": labels, "groups": groups, "matrix_rows": model_rows,
        "cell_means": clean(result["cell_means"]),
        "marginal_means": clean(result["marginal_means"]),
        "missing_run_id": next((row["run_id"] for row in rows if row["Y"] is None), None),
        "design_rows": rows,
    }


def minijmp_worker():
    import pandas as pd

    sys.path.insert(0, str(ROOT / "code"))
    from doe_general_factorial import create_general_factorial
    from doe_general_factorial_analysis import analyze_general_factorial

    fixture_path = ROOT / "tests" / "fixtures" / "doe_factorial_reference" / "reference.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    results = {}
    for case_id in CASE_IDS:
        spec, replicates = general_spec(case_id)
        frame, metadata = create_general_factorial(spec, replicates=replicates)
        missing_run_id = None
        if case_id == "GFF-2X3":
            _set_two_by_three(frame, fixture["general_full_factorial"]["two_by_three"])
        else:
            missing_run_id = _set_type_iii_response(frame)
        design, factors, rows = design_rows(frame, metadata)
        input_path = INPUTS[case_id]
        fields = ("run_id", "standard_order", "run_order", "replicate", "point_key",
                  "A", "B", "A_code", "B_code", "Y")
        with input_path.open("w", newline="", encoding="utf-8-sig") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(sorted(rows, key=lambda row: row["standard_order"]))

        a_levels = tuple(factors[0]["levels"])
        b_levels = tuple(factors[1]["levels"])
        x, labels, groups = model_matrix(factors, [
            {"settings": run.settings} for run in design.runs
        ])
        if (x.shape[1] != 6 or np.linalg.matrix_rank(x) != 6
                or len({row["point_key"] for row in rows}) != len(rows)):
            raise AssertionError(f"{case_id} 全因子模型秩或运行标识不符")

        if case_id == "GFF-2X3":
            analysis_i = analyze_general_factorial(frame, metadata, "Y", order=2, ss_type="I")
            analysis_iii = analyze_general_factorial(frame, metadata, "Y", order=2, ss_type="III")
            if (analysis_i["n"], analysis_i["rank"], analysis_i["df"],
                    analysis_i["pure_error_df"]) != (12, 6, 6, 6):
                raise AssertionError("GFF-2X3 必须为满模型、6 个误差自由度及独立纯误差")
            if not math.isclose(analysis_i["sse"], 12.0, rel_tol=0, abs_tol=1e-12):
                raise AssertionError("GFF-2X3 固定参考的非零残差平方和不符")
            analyses = {"I": summarize_analysis(analysis_i, rows, factors, groups),
                        "III": summarize_analysis(analysis_iii, rows, factors, groups)}
        else:
            analysis_iii = analyze_general_factorial(frame, metadata, "Y", order=2,
                                                      ss_type="III")
            if (analysis_iii["n"], analysis_iii["rank"], analysis_iii["df"]) != (17, 6, 11):
                raise AssertionError("GFF-TYPEIII 缺失一个响应后秩/自由度不符")
            if any(not row.get("estimable", False) for row in analysis_iii["anova"]
                   if row["term"] in TERM_NAMES):
                raise AssertionError("GFF-TYPEIII 效应组必须完整可估计")
            analyses = {"III": summarize_analysis(analysis_iii, rows, factors, groups)}

        results[case_id] = {
            "case_id": case_id, "design_type": "general_full_factorial",
            "factors": [{"factor_id": factor["factor_id"],
                         "levels": list(factor["levels"])} for factor in factors],
            "factor_levels": {factor["factor_id"]: list(factor["levels"])
                              for factor in factors},
            "native_level_map": {
                "A": {str(level): index + 1 for index, level in enumerate(a_levels)},
                "B": {str(level): index + 1 for index, level in enumerate(b_levels)},
            },
            "design_command": f"FDESIGN 2 3; REPS {replicates}; DESIGN.",
            "model_terms": list(TERM_NAMES), "contrast_labels": labels,
            "effect_groups": groups, "design_rows": rows,
            "model_matrix_rows": analyses["III"]["matrix_rows"],
            "cell_means": analyses["III"]["cell_means"],
            "marginal_means": analyses["III"]["marginal_means"],
            "missing_run_id": missing_run_id, "analyses": analyses,
        }
    write_json(MINIJMP, results)
    print("MiniJMP GFF self-check: 2×3 replicated model rank 6/12; "
          "Type III model 17 observed rows, rank 6, error df 11; PASS", flush=True)


def minitab_worker():
    raw = []
    commands = []
    session = None
    try:
        local = json.loads(MINIJMP.read_text(encoding="utf-8"))
        session = MinitabSession()
        results = {}
        for case_index, case_id in enumerate(CASE_IDS):
            if case_index:
                session.new_project()
            rows = list(csv.DictReader(INPUTS[case_id].open(
                newline="", encoding="utf-8-sig")))
            replicates = max(int(row["replicate"]) for row in rows)
            design_command = f"FDESIGN 2 3;\n  REPS {replicates};\n  DESIGN."
            session.execute(design_command, f"{case_id} FDESIGN")
            factor_columns = {name: session.find_column((name,)) for name in FACTOR_IDS}
            standard_column = session.find_column(("StdOrder", "StandardOrder", "标准序"))
            order_column = session.find_column(("RunOrder", "运行序"))
            standard = session.column_values(standard_column)
            order = session.column_values(order_column)
            factor_values = {name: session.column_values(factor_columns[name])
                             for name in FACTOR_IDS}
            count = len(standard)
            if (len(order) != count or any(len(values) != count
                                           for values in factor_values.values())):
                raise RuntimeError(f"{case_id} FDESIGN 结果列长度不符")
            native_rows = []
            for index in range(count):
                a_code = int(round(factor_values["A"][index]))
                b_code = int(round(factor_values["B"][index]))
                native_rows.append({
                    "worksheet_row": index + 1,
                    "standard_order": int(standard[index]),
                    "run_order": int(order[index]),
                    "A_code": a_code, "B_code": b_code,
                    "point_key": f"{a_code}|{b_code}",
                })
            occurrences = defaultdict(int)
            for row in sorted(native_rows,
                              key=lambda item: (item["standard_order"], item["run_order"])):
                occurrences[row["point_key"]] += 1
                row["replicate"] = occurrences[row["point_key"]]
                row["key"] = observation_key(row["A_code"], row["B_code"], row["replicate"])
            # Each factor combination repeats once per replicate; occurrence disambiguates rows.
            input_by_key = {
                observation_key(int(row["A_code"]), int(row["B_code"]), int(row["replicate"])): row
                for row in rows
            }
            for row in native_rows:
                source = input_by_key.get(row["key"])
                if source is not None:
                    row["A"] = source["A"]
                    row["B"] = source["B"]
                    row["Y"] = (None if source["Y"] == "" else float(source["Y"]))
            native_keys = {row["key"] for row in native_rows}
            design_match = native_keys == set(input_by_key)
            raw.append(f"===== {case_id} native FDESIGN rows =====\n"
                       + json.dumps(native_rows, ensure_ascii=False, indent=2))
            commands.extend([f"# {case_id}: native 2×3 general full factorial design",
                             design_command])
            if not design_match:
                results[case_id] = {"design_match": False, "design_command": design_command,
                                    "design_rows": native_rows}
                continue

            worksheet_rows = {row["worksheet_row"]: row for row in native_rows}
            y_values = [0.0 if worksheet_rows[index + 1]["Y"] is None
                        else worksheet_rows[index + 1]["Y"] for index in range(count)]
            response_column = session.add_column("Y", y_values)
            missing_rows = [row for row in native_rows if row["Y"] is None]
            for row in missing_rows:
                missing_command = (
                    f"LET C{response_column}({row['worksheet_row']}) = '*'"
                )
                session.execute(missing_command, f"{case_id} set missing response")
                commands.append(missing_command)
            fit_column = session.add_column("Fit")
            residual_column = session.add_column("Resid")
            coefficient_column = session.add_column("Coef")
            a_column, b_column = factor_columns["A"], factor_columns["B"]
            matrix_name = "M1"
            analysis_command = (
                "GFACTORIAL;\n"
                f"  RESPONSE C{response_column};\n"
                f"  FACTOR C{a_column} C{b_column};\n"
                f"  TERMS C{a_column} C{b_column} C{a_column}*C{b_column};\n"
                f"  FITS C{fit_column};\n  RESIDUALS C{residual_column};\n"
                f"  COEFFICIENTS C{coefficient_column};\n  XMATRIX {matrix_name};\n"
                "  TANOVA."
            )
            output = session.execute(analysis_command, f"{case_id} GFACTORIAL")
            matrix = session.read_matrix(matrix_name)
            coefficient_column_values = session.column_values(coefficient_column)
            fits = session.column_values(fit_column)
            residuals = session.column_values(residual_column)
            p = len(matrix[0])
            expected_full_coefficients = (
                1 + len(local[case_id]["factor_levels"]["A"])
                + len(local[case_id]["factor_levels"]["B"])
                + len(local[case_id]["factor_levels"]["A"])
                * len(local[case_id]["factor_levels"]["B"])
            )
            if (len(coefficient_column_values) < expected_full_coefficients
                    or any(value is None
                           for value in coefficient_column_values[:expected_full_coefficients])):
                raise RuntimeError(
                    f"{case_id} Minitab COEFFICIENTS 行数不足或含缺失: "
                    f"rows={len(coefficient_column_values)}, expected={expected_full_coefficients}")
            coefficients = coefficient_column_values[:expected_full_coefficients]
            if len(matrix) != count or len(fits) != count or len(residuals) != count:
                raise RuntimeError(f"{case_id} Minitab GFACTORIAL 存储行数不符")
            for index, row in enumerate(native_rows):
                row["fit"] = fits[index]
                row["residual_y_minus_fit"] = residuals[index]
                row["matrix"] = matrix[index]
            observed_matrix = [row["matrix"] for row in native_rows
                               if row["Y"] is not None]
            results[case_id] = {
                "design_match": True, "version": session.version,
                "app_path": session.app_path, "process_path": session.process_path,
                "design_command": design_command, "analysis_command": analysis_command,
                "design_rows": native_rows, "matrix": matrix,
                "coefficients": coefficients,
                "rank": int(np.linalg.matrix_rank(observed_matrix)),
                "term_groups": local[case_id]["effect_groups"],
                "output": output,
            }
            write_json(MINITAB, results)
            commands.append(analysis_command)
            COMMANDS.write_text(
                "# Minitab 19.1.0.1 official Session Commands: FDESIGN / GFACTORIAL\n\n"
                + "\n\n".join(commands) + "\n", encoding="utf-8")
        write_json(MINITAB, results)
        COMMANDS.write_text(
            "# Minitab 19.1.0.1 official Session Commands: FDESIGN / GFACTORIAL\n\n"
            + "\n\n".join(commands) + "\n", encoding="utf-8")
        RAW.write_text("\n\n".join([*session.raw, *raw]) + "\n", encoding="utf-8")
        print("Minitab 19.1.0.1 FDESIGN/GFACTORIAL: two cases stored", flush=True)
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


def fit_ss(y, matrix):
    beta, _, rank, _ = np.linalg.lstsq(matrix, y, rcond=None)
    residual = y - matrix @ beta
    return float(residual @ residual), int(rank)


def full_level_coefficient_matrix(rows, n_a=2, n_b=3):
    columns = [np.ones(len(rows))]
    columns.extend([np.asarray([row["A_code"] == level for row in rows], dtype=float)
                    for level in range(1, n_a + 1)])
    columns.extend([np.asarray([row["B_code"] == level for row in rows], dtype=float)
                    for level in range(1, n_b + 1)])
    columns.extend([np.asarray([row["A_code"] == a and row["B_code"] == b
                                for row in rows], dtype=float)
                    for a, b in product(range(1, n_a + 1), range(1, n_b + 1))])
    return np.column_stack(columns)


def derive_native_statistics(native_case, local_case):
    from scipy import stats

    all_rows = native_case["design_rows"]
    matrix_by_key = {
        row["key"]: row["matrix"] for row in all_rows
        if row.get("Y") is not None
    }
    observed_rows = [row for row in all_rows if row.get("Y") is not None]
    x = np.asarray([matrix_by_key[row["key"]] for row in observed_rows], dtype=float)
    y = np.asarray([float(row["Y"]) for row in observed_rows], dtype=float)
    fits = np.asarray([float(row["fit"]) for row in observed_rows], dtype=float)
    raw_residuals = np.asarray([float(row["residual_y_minus_fit"]) for row in observed_rows],
                               dtype=float)
    np.testing.assert_allclose(y - fits, raw_residuals, rtol=0, atol=2e-9)
    residuals = raw_residuals
    sse = float(residuals @ residuals)
    sst = float(np.sum((y - y.mean()) ** 2))
    ssr = sst - sse
    rank = int(np.linalg.matrix_rank(x))
    error_df = len(y) - rank
    mse = sse / error_df
    group_columns = {name: tuple(range(start, stop))
                     for name, (start, stop) in local_case["effect_groups"].items()}
    sequential = {}
    previous_columns = [0]
    previous_sse, previous_rank = fit_ss(y, x[:, previous_columns])
    for term in TERM_NAMES:
        new_columns = list(group_columns[term])
        current_columns = previous_columns + new_columns
        current_sse, current_rank = fit_ss(y, x[:, current_columns])
        df = current_rank - previous_rank
        ss = previous_sse - current_sse
        f_value = (ss / df) / mse
        sequential[term] = {"ss": ss, "df": df, "ms": ss / df,
                            "f": f_value,
                            "p": float(stats.f.sf(f_value, df, error_df))}
        previous_columns, previous_sse, previous_rank = (
            current_columns, current_sse, current_rank)
    adjusted = {}
    for term in TERM_NAMES:
        removed = set(group_columns[term])
        reduced_columns = [index for index in range(x.shape[1]) if index not in removed]
        reduced_sse, reduced_rank = fit_ss(y, x[:, reduced_columns])
        df = rank - reduced_rank
        ss = reduced_sse - sse
        f_value = (ss / df) / mse
        adjusted[term] = {"ss": ss, "df": df, "ms": ss / df,
                          "f": f_value,
                          "p": float(stats.f.sf(f_value, df, error_df))}
    return {
        "n": len(y), "p": x.shape[1], "rank": rank,
        "error_df": error_df, "sse": sse, "sst": sst, "ssr": ssr,
        "mse": mse, "model_f": (ssr / (rank - 1)) / mse,
        "model_p": float(stats.f.sf((ssr / (rank - 1)) / mse, rank - 1, error_df)),
        "sequential": sequential, "adjusted": adjusted,
        "observed_rows": observed_rows, "x": x, "y": y,
        "fits": fits, "residuals": residuals,
    }


def compare_case(case_id, local_case, native_case):
    rows = []
    design_source = "Minitab FDESIGN worksheet factors (DIRECT)"
    matrix_source = "Minitab GFACTORIAL XMATRIX (DIRECT)"
    coefficient_source = "Minitab GFACTORIAL COEFFICIENTS (DIRECT)"
    fit_source = "Minitab GFACTORIAL FITS/RESIDUALS (DIRECT)"
    derived_source = "DERIVED: Minitab XMATRIX, fixed response, grouped model terms"
    local_rows = {row["point_key"]: row for row in local_case["design_rows"]}
    native_rows = {row.get("key", row.get("point_key")): row
                   for row in native_case["design_rows"]}
    if not native_case.get("design_match") or set(local_rows) != set(native_rows):
        local_counts = Counter(row["point_key"] for row in local_case["design_rows"])
        native_counts = Counter(row.get("point_key", row.get("key"))
                                for row in native_case["design_rows"])
        for key in sorted(set(local_counts) | set(native_counts)):
            rows.append(compare_numeric(case_id, "design", key, "multiplicity",
                                        native_counts[key], local_counts[key],
                                        design_source, "MiniJMP create_general_factorial"))
        return rows

    for key in sorted(local_rows):
        local_row, native_row = local_rows[key], native_rows[key]
        for factor in FACTOR_IDS:
            rows.append(compare_numeric(case_id, "design", key, f"{factor}_native_level",
                                        native_row[f"{factor}_code"], local_row[f"{factor}_code"],
                                        design_source, "MiniJMP level map from factor levels"))
            rows.append(compare_text(case_id, "design", key, f"{factor}_label",
                                     str(local_row[factor]), str(local_row[factor]),
                                     "Minitab FDESIGN level-code mapping",
                                     "MiniJMP FactorSpec levels"))
        left_y = native_row.get("Y")
        right_y = local_row.get("Y")
        rows.append(compare_numeric(case_id, "input", key, "Y", left_y, right_y,
                                    "fixed input loaded into Minitab worksheet",
                                    "MiniJMP fixed response input"))

    stats_native = derive_native_statistics(native_case, local_case)
    local_observed = {key: row for key, row in local_case["model_matrix_rows"].items()}
    local_matrix = np.asarray([local_observed[row["key"]]["matrix"]
                               for row in stats_native["observed_rows"]], dtype=float)
    native_matrix = stats_native["x"]
    if local_matrix.shape != native_matrix.shape:
        raise ValueError(f"{case_id} MiniJMP/Minitab 模型矩阵维度不符: "
                         f"{local_matrix.shape} != {native_matrix.shape}")
    transform, *_ = np.linalg.lstsq(local_matrix, native_matrix, rcond=None)
    residual_matrix = local_matrix @ transform - native_matrix
    basis_error = float(np.max(np.abs(residual_matrix)))
    rows.append(compare_numeric(case_id, "model_space", "full factorial", "rank",
                                int(np.linalg.matrix_rank(native_matrix)),
                                int(np.linalg.matrix_rank(local_matrix)), matrix_source,
                                "MiniJMP full categorical model matrix"))
    rows.append(compare_numeric(case_id, "model_space", "full factorial", "basis_error",
                                basis_error, 0.0, derived_source,
                                "MiniJMP sum-to-zero contrast matrix"))
    native_beta = np.asarray(native_case["coefficients"], dtype=float)
    coefficient_rows = [row for row in native_case["design_rows"] if row.get("Y") is not None]
    full_effect_matrix = full_level_coefficient_matrix(coefficient_rows)
    coefficient_fits = full_effect_matrix @ native_beta
    native_fits = np.asarray([row["fit"] for row in coefficient_rows], dtype=float)
    np.testing.assert_allclose(coefficient_fits, native_fits, rtol=0, atol=2e-9)
    transformed_beta, *_ = np.linalg.lstsq(local_matrix, coefficient_fits, rcond=None)
    local_beta = np.asarray(local_case["analyses"]["III"]["coefficients"], dtype=float)
    for index, label in enumerate(local_case["contrast_labels"]):
        rows.append(compare_numeric(case_id, "coefficient", label, "estimate",
                                    transformed_beta[index], local_beta[index],
                                    "Minitab coefficient transformed to MiniJMP contrast basis",
                                    "MiniJMP analyze_general_factorial coefficients"))

    native_by_key = {row["key"]: row for row in stats_native["observed_rows"]}
    for key in sorted(native_by_key):
        native_row = native_by_key[key]
        local_row = local_observed[key]
        rows.append(compare_numeric(case_id, "run_statistics", key, "fit",
                                    native_row["fit"], local_row["fit"], fit_source,
                                    "MiniJMP fitted values"))
        rows.append(compare_numeric(case_id, "run_statistics", key, "residual",
                                    native_row["residual_y_minus_fit"], local_row["residual"],
                                    fit_source, "MiniJMP residuals (Y - fit)"))

    local_analyzes = local_case["analyses"]
    ss_modes = ["I", "III"] if case_id == "GFF-2X3" else ["III"]
    for ss_type in ss_modes:
        source_stats = (stats_native["sequential"] if ss_type == "I"
                        else stats_native["adjusted"])
        local_terms = {row["term"]: row for row in local_analyzes[ss_type]["anova"]}
        for term in TERM_NAMES:
            local_term = local_terms[term]
            for statistic in ("ss", "df", "ms", "f", "p"):
                rows.append(compare_numeric(
                    case_id, f"anova_type_{ss_type}", term, statistic,
                    source_stats[term][statistic], local_term[statistic],
                    derived_source, f"MiniJMP analyze_general_factorial ss_type={ss_type}"))

    local_final = local_analyzes["III"]
    for statistic, native_value, local_value in (
        ("n", stats_native["n"], local_final["n"]),
        ("rank", stats_native["rank"], local_final["rank"]),
        ("error_df", stats_native["error_df"], local_final["error_df"]),
        ("sse", stats_native["sse"], local_final["sse"]),
        ("sst", stats_native["sst"], local_final["sst"]),
        ("model_ss", stats_native["ssr"], local_final["ssr"]),
        ("mse", stats_native["mse"], local_final["inference"]["mse"]),
        ("model_f", stats_native["model_f"], local_final["inference"]["f"]),
        ("model_p", stats_native["model_p"], local_final["inference"]["model_p"]),
    ):
        rows.append(compare_numeric(case_id, "anova_summary", "model", statistic,
                                    native_value, local_value, derived_source,
                                    "MiniJMP analyze_general_factorial"))

    native_cells = defaultdict(list)
    native_marginals = {"A": defaultdict(list), "B": defaultdict(list)}
    for row in stats_native["observed_rows"]:
        key = f"{row['A_code']}|{row['B_code']}"
        native_cells[key].append(float(row["fit"]))
        native_marginals["A"][int(row["A_code"])].append(float(row["Y"]))
        native_marginals["B"][int(row["B_code"])].append(float(row["Y"]))
    local_cells = {
        f"{code_for(row['levels']['A'], local_case['factor_levels']['A'])}|"
        f"{code_for(row['levels']['B'], local_case['factor_levels']['B'])}": row
        for row in local_case["cell_means"]
    }
    for key in sorted(local_cells):
        mtb_mean = float(np.mean(native_cells[key]))
        rows.append(compare_numeric(case_id, "cell_mean", key, "fit_mean", mtb_mean,
                                    local_cells[key]["mean"],
                                    "DERIVED: Minitab direct FITS grouped by full cell",
                                    "MiniJMP general factorial cell means"))
    for factor in FACTOR_IDS:
        factor_levels = local_case["factor_levels"][factor]
        for index, level in enumerate(factor_levels, 1):
            observed = float(np.mean(native_marginals[factor][index]))
            local_item = next(item for item in local_case["marginal_means"]
                              if item["factor_id"] == factor and item["level"] == level)
            rows.append(compare_numeric(case_id, "observed_marginal_mean",
                                        f"{factor}={level}", "mean", observed,
                                        local_item["mean"],
                                        "DERIVED: Minitab fixed response grouped by factor level",
                                        "MiniJMP observed marginal means"))
            cell_predictions = [float(np.mean(native_cells[f"{a}|{b}"]))
                                for a, b in (product((index,), range(1, 4))
                                             if factor == "A" else
                                             product(range(1, 3), (index,)))]
            rows.append(compare_numeric(case_id, "least_squares_marginal_mean",
                                        f"{factor}={level}", "mean",
                                        float(np.mean(cell_predictions)),
                                        float(np.mean([local_cells[
                                            f"{a}|{b}"]["mean"] for a, b in
                                            (product((index,), range(1, 4))
                                             if factor == "A" else
                                             product(range(1, 3), (index,)))])),
                                        "DERIVED: equally weighted Minitab fitted cell means",
                                        "DERIVED: equally weighted MiniJMP cell means"))
    return rows


def write_report(all_rows, status, reason=""):
    unique = unique_rows(all_rows)
    counts = status_counts(unique)
    source_counts = {
        name: sum(name in row["minitab_value_source"] for row in unique)
        for name in ("DIRECT", "DERIVED", "DISPLAY")
    }
    lines = [
        "# 一般全因子与多水平 ANOVA 对标验收", "",
        f"状态：**{status}**", "",
        "## 案例与方法", "",
        "- `GFF-2X3`：2×3 分类全因子、每个组合两次独立重复；Minitab 使用 `FDESIGN`/`GFACTORIAL`。",
        "- `GFF-TYPEIII`：2×3 全因子三次重复，固定一个缺失响应；使用完整 A、B、A×B 效应组。",
        "- MiniJMP sum-to-zero contrast basis 与 Minitab `XMATRIX` 先求线性变换，再比较对应系数和模型空间。",
        "- Minitab 输出称 Adjusted SS；Type III parity 按删去完整效应列组重拟合核算。",
        "- Minitab 存储残差为 Y−Fit，与 MiniJMP 定义一致；原生工作表值直接比较。",
        "", "## 数值结果", "",
        f"唯一比较项：{len(unique)}；PASS/FAIL/N/A/UNSUPPORTED："
        f"{counts['PASS']}/{counts['FAIL']}/{counts['N/A']}/{counts['UNSUPPORTED']}。",
        f"来源计数（可重叠）：DIRECT/DERIVED/DISPLAY："
        f"{source_counts['DIRECT']}/{source_counts['DERIVED']}/{source_counts['DISPLAY']}。",
        "", "## Minitab 19 Session Commands", "",
        "实际命令见 `session_commands.txt`，原始 Outputs/OutputDocument 见 `minitab_raw.txt`。",
        "", "## 证据文件", "",
        "- `gff_2x3_input.csv`、`gff_typeiii_input.csv`：设计点、水平映射、重复和响应。",
        "- `minijmp_results.json`、`minitab_results.json`：生产 API 与原生高精度结果。",
        "- `comparison.csv`：稳定键去重的逐项数值比较。",
    ]
    if reason:
        lines.extend(["", "## 未完成原因", "", reason])
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
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
        print(f"General factorial supplemental {status}: {counts}; Minitab PID 已退出。",
              flush=True)
        return 0
    except Exception as error:
        write_comparison(COMPARISON, [])
        write_report([], "BLOCKED", f"{type(error).__name__}: {error}；请查看原始输出。")
        print(f"General factorial supplemental BLOCKED: {type(error).__name__}: {error}",
              flush=True)
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
        assert observation_key(1, 3, 2) == "1|3|2"
        assert contrast_columns(["a", "b"], ("a", "b")).tolist() == [[-1], [1]]
        print("General factorial verifier self-check: PASS")
        raise SystemExit(0)
    raise SystemExit(parent_main())
