"""MiniJMP × Minitab 19 12-run Plackett–Burman parity check."""
from __future__ import annotations

import csv
import ctypes
import json
import math
import subprocess
import sys
import time
import traceback
from collections import Counter
from itertools import combinations
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
MTB_EXE = Path(r"D:\Program\Minitab 19\Mtb.exe")
PROJECT_PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
FIXTURE = ROOT / "tests" / "fixtures" / "doe_screening_reference" / "pb" / "pb12.csv"
INPUT = OUT / "doe_pb_input.csv"
COMMANDS = OUT / "doe_pb_session_commands.txt"
RAW = OUT / "doe_pb_minitab_raw.txt"
MINIJMP = OUT / "doe_pb_minijmp.json"
MINITAB = OUT / "doe_pb_minitab.json"
COMPARISON = OUT / "doe_pb_comparison.csv"
REPORT = OUT / "doe_pb_acceptance_report.md"
FACTORS = tuple("ABCDEFG")
TERMS = ("截距", *FACTORS)

from verify_doe_ccd import (canonical, capture_command_output, compare_values,
                            running_minitab_pids, write_csv)


def row_key(values):
    return tuple(round(float(value), 12) for value in values)


def response_value(codes):
    a, b, c, d, e, f, g = (codes[name] for name in FACTORS)
    return float(40 + 3*a - 2*b + 1.5*c + .75*d - 1.25*e + 2*f - .5*g
                 + .8*a*b - .6*c*d + .4*e*g + .35*b*f)


def read_fixture():
    with FIXTURE.open(newline="", encoding="utf-8-sig") as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != 12:
        raise ValueError("冻结 PB12 数学参考必须包含 12 行")
    matrix = [{name: float(row[f"X{index}"])
               for index, name in enumerate(FACTORS, 1)} for row in rows]
    if any(value not in (-1.0, 1.0) for row in matrix for value in row.values()):
        raise ValueError("PB12 独立参考水平必须是 -1/+1")
    return matrix


def write_input(rows):
    fields = ("run_id", "standard_order", "run_order", "replicate", "point_type", *FACTORS, "Y")
    with INPUT.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def read_input():
    with INPUT.open(newline="", encoding="utf-8-sig") as stream:
        rows = []
        for row in csv.DictReader(stream):
            rows.append({"run_id": row["run_id"],
                         "standard_order": int(row["standard_order"]),
                         "run_order": int(row["run_order"]),
                         "replicate": int(row["replicate"]),
                         "point_type": row["point_type"],
                         **{name: float(row[name]) for name in FACTORS},
                         "Y": float(row["Y"])})
    if (len(rows) != 12
            or [row["standard_order"] for row in sorted(rows, key=lambda item: item["standard_order"])]
            != list(range(1, 13))
            or Counter(row["point_type"] for row in rows) != {"factorial": 12}):
        raise ValueError("PB 输入必须为 12 个无中心点、单次运行")
    if any(value not in (-1.0, 1.0) for row in rows for value in (row[name] for name in FACTORS)):
        raise ValueError("PB 输入因子必须是 -1/+1 编码")
    if len({row_key(row[name] for name in FACTORS) for row in rows}) != 12:
        raise ValueError("PB 输入运行点必须唯一")
    if any(not math.isfinite(row["Y"]) or row["Y"] <= 0 for row in rows):
        raise ValueError("PB 响应必须是有限正数")
    return rows


def run_minijmp_worker():
    if (not PROJECT_PYTHON.is_file()
            or Path(sys.executable).resolve() != PROJECT_PYTHON.resolve()):
        raise RuntimeError(f"请使用项目解释器运行: {PROJECT_PYTHON}")
    sys.path.insert(0, str(ROOT / "code"))
    import numpy as np
    import pandas as pd
    from doe_core import DesignSpec, FactorSpec
    from doe_pb import create_pb
    from doe_screening_analysis import analyze_pb

    fixture = read_fixture()
    identity = {"construction_id": "pb12.v1", "source_kind": "publication",
                "source_id": "nist.pb12", "matrix_sha256": "0" * 64}
    spec = DesignSpec("minitab19-pb-parity",
                      tuple(FactorSpec(name, name, -1, 1) for name in FACTORS),
                      ("Y",), seed=19, design_type="plackett_burman",
                      screening_matrix=identity)
    frame, metadata = create_pb(spec, 12)
    by_order = {index + 1: row for index, row in enumerate(fixture)}
    rows = []
    for _, row in frame.iterrows():
        order = int(row["标准序"])
        codes = {name: float(row[f"设定_{name}"]) for name in FACTORS}
        if codes != by_order[order]:
            raise AssertionError(f"MiniJMP PB12 矩阵与独立 NIST fixture 不符：标准序 {order}")
        rows.append({"run_id": str(row["运行ID"]), "standard_order": order,
                     "run_order": int(row["运行序"]), "replicate": int(row["重复"]),
                     "point_type": str(row["点类型"]), **codes,
                     "Y": response_value(codes)})
    write_input(rows)
    rows = read_input()
    x_factors = np.asarray([[row[name] for name in FACTORS] for row in rows], dtype=float)
    if not np.array_equal(x_factors.T @ x_factors, 12 * np.eye(7)):
        raise AssertionError("PB12 参考矩阵必须平衡且正交")
    frame.loc[:, "响应_Y"] = pd.array([row["Y"] for row in rows], dtype="Float64")
    analysis = analyze_pb(frame, metadata, "Y")
    reference_x = np.column_stack([np.ones(12), x_factors])
    reference_y = np.asarray([row["Y"] for row in rows], dtype=float)
    beta, _, rank, _ = np.linalg.lstsq(reference_x, reference_y, rcond=None)
    np.testing.assert_allclose(analysis["fit_matrix"], reference_x, rtol=0, atol=1e-12)
    np.testing.assert_allclose(analysis["coefficients"], beta, rtol=0, atol=1e-10)
    interaction_reference = np.column_stack([
        x_factors[:, a] * x_factors[:, b] for a, b in combinations(range(7), 2)
    ])
    expected_alias = np.linalg.lstsq(reference_x, interaction_reference, rcond=None)[0]
    alias = np.asarray(analysis["alias_matrix"]["values"], dtype=float)
    np.testing.assert_allclose(alias, expected_alias, rtol=0, atol=1e-12)
    if (rank != 8 or analysis["rank"] != 8 or analysis["df"] != 4
            or analysis["sse"] <= 1e-10 or analysis["inference"] is None
            or analysis["pure_error_df"] != 0):
        raise AssertionError("PB12 主效应模型秩、残差自由度或非完全拟合自检失败")

    fit_rows = []
    for index, row in enumerate(rows):
        fit_rows.append({**row, "fit": float(analysis["fitted"][index]),
                         "residual": float(analysis["residuals"][index]),
                         "matrix": [float(value) for value in analysis["fit_matrix"][index]]})
    inference = analysis["inference"]
    main_anova = {}
    for index, name in enumerate(FACTORS, 1):
        f_value = float(inference["t"][index] ** 2)
        main_anova[name] = {
            "ss": f_value * float(inference["mse"]), "df": 1.0,
            "ms": f_value * float(inference["mse"]), "f": f_value,
            "p": float(inference["p"][index]),
            "se": float(inference["se"][index]),
            "t": float(inference["t"][index]),
            "coefficient_p": float(inference["p"][index]),
        }
    result = {
        "terms": list(analysis["names"]), "rank": int(analysis["rank"]),
        "n": int(analysis["n"]), "p": int(analysis["p"]),
        "df": int(analysis["df"]), "model_df": int(analysis["rank"] - 1),
        "total_df": int(analysis["n"] - 1),
        "coefficients": {term: float(value)
                         for term, value in zip(analysis["names"], analysis["coefficients"])},
        "effects": {name: float(analysis["effects"][index + 1])
                    for index, name in enumerate(FACTORS)},
        "fits": fit_rows,
        "summary": {"rank": int(analysis["rank"]),
                    "model_df": int(analysis["rank"] - 1),
                    "error_df": int(analysis["df"]),
                    "total_df": int(analysis["n"] - 1),
                    "sse": float(analysis["sse"]), "sst": float(analysis["sst"]),
                    "ssr": float(analysis["ssr"]), "mse": float(inference["mse"]),
                    "s": math.sqrt(float(inference["mse"])),
                    "r2": 1 - float(analysis["sse"]) / float(analysis["sst"]),
                    "adjusted_r2": 1 - (analysis["sse"] / analysis["df"])
                    / (analysis["sst"] / (analysis["n"] - 1)),
                    "model_f": float(inference["f"]),
                    "model_p": float(inference["model_p"])},
        "main_anova": main_anova,
        "alias_matrix": analysis["alias_matrix"],
    }
    MINIJMP.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("MiniJMP PB self-check: NIST PB12 fixture, 7 balanced orthogonal factors, "
          "rank 8, residual df 4, nonzero SSE, full alias projection PASS", flush=True)


def _column_values(column):
    values = column.GetData()
    return [float(values)] if isinstance(values, (int, float)) else [float(value) for value in values]


def _find_column(names, wanted, required=True):
    targets = {str(value).replace(" ", "").casefold() for value in wanted}
    for index, name in enumerate(names, 1):
        if str(name).replace(" ", "").casefold() in targets:
            return index
    if required:
        raise RuntimeError(f"Minitab PB 缺少列 {tuple(wanted)}；实际列={names}")
    return None


def _execute(project, app, command, raw, label):
    before = int(project.Commands.Count)
    project.ExecuteCommand(command)
    deadline = time.monotonic() + 12
    while int(project.Commands.Count) <= before and time.monotonic() < deadline:
        time.sleep(.1)
    after = int(project.Commands.Count)
    if after <= before:
        message = str(app.LastError or "")
        raw.append(f"===== {label} actual command =====\n{command}\n"
                   f"===== command object =====\nnot created\n===== LastError =====\n{message}")
        raise RuntimeError(f"{label} 未创建 Minitab 命令对象: {message!r}")
    output = capture_command_output(project, after)
    raw.append(f"===== {label} actual command =====\n{command}\n"
               f"===== {label} OutputDocument/Outputs =====\n{output}\n"
               f"===== LastError =====\n{app.LastError!r}")
    if "* 错误 *" in output or "* ERROR *" in output.upper():
        raise RuntimeError(f"{label} 返回 Minitab 错误信息")
    return output


def minitab_worker():
    import winreg
    import win32api
    import win32process
    import pythoncom
    import win32com.client
    import numpy as np

    raw, app = [], None
    project = ui = worksheet = columns = matrices = None
    try:
        if not MTB_EXE.is_file():
            raise FileNotFoundError(MTB_EXE)
        if running_minitab_pids():
            raise RuntimeError("已有 Mtb.exe 正在运行；拒绝连接用户会话")
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r"Mtb.Application\CLSID") as key:
            clsid = winreg.QueryValueEx(key, "")[0]
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, rf"CLSID\{clsid}\LocalServer32") as key:
            server_command = winreg.QueryValueEx(key, "")[0]
        server_path = (server_command.strip().split('"')[1] if '"' in server_command
                       else server_command.split()[0])
        if canonical(server_path) != canonical(MTB_EXE):
            raise RuntimeError(f"Mtb.Application 注册服务器不匹配: {server_command}")
        info = win32api.GetFileVersionInfo(str(MTB_EXE), "\\")
        ms, ls = info["FileVersionMS"], info["FileVersionLS"]
        version = ".".join(str(value) for value in (
            win32api.HIWORD(ms), win32api.LOWORD(ms),
            win32api.HIWORD(ls), win32api.LOWORD(ls)))
        if version != "19.1.0.1":
            raise RuntimeError(f"要求 Minitab 19.1.0.1，实际版本 {version}")
        app = win32com.client.DispatchEx("Mtb.Application")
        pythoncom.PumpWaitingMessages()
        ui = app.UserInterface
        ui.Visible = False
        ui.UserControl = False
        ui.DisplayAlerts = False
        app_path = str(app.AppPath)
        hwnd = int(app.Handle)
        _, process_id = win32process.GetWindowThreadProcessId(hwnd)
        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, process_id)
        if not handle:
            raise ctypes.WinError()
        try:
            size = ctypes.c_ulong(32768)
            buffer = ctypes.create_unicode_buffer(size.value)
            if not ctypes.windll.kernel32.QueryFullProcessImageNameW(
                    handle, 0, buffer, ctypes.byref(size)):
                raise ctypes.WinError()
            process_path = buffer.value
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
        if (canonical(app_path) != canonical(MTB_EXE)
                or canonical(process_path) != canonical(MTB_EXE)):
            raise RuntimeError(f"COM 实例路径不匹配: AppPath={app_path}, process={process_path}")

        rows = read_input()
        app.New()
        project = app.ActiveProject
        levels = " ".join("-1 1" for _ in FACTORS)
        design_command = f"PBDESIGN 7 12;\n  LEVELS {levels};\n  DESIGN."
        _execute(project, app, design_command, raw, "PBDESIGN")
        worksheet = project.ActiveWorksheet
        columns = worksheet.Columns
        names = [str(columns.Item(index).Name) for index in range(1, int(columns.Count) + 1)]
        factor_columns = {name: _find_column(names, (name,)) for name in FACTORS}
        std_column = _find_column(names, ("StdOrder", "StandardOrder", "标准序"), False)
        run_column = _find_column(names, ("RunOrder", "运行序"), False)
        raw_columns = {index: _column_values(columns.Item(index))
                       for index in set(factor_columns.values()) | {c for c in (std_column, run_column)
                                                                    if c is not None}}
        if len(raw_columns[factor_columns["A"]]) != 12:
            raise RuntimeError(f"PBDESIGN 应生成 12 行，实际 {len(raw_columns[factor_columns['A']])}")
        input_by_key = {row_key(row[name] for name in FACTORS): row for row in rows}
        native_rows = []
        for index in range(12):
            codes = {name: raw_columns[factor_columns[name]][index] for name in FACTORS}
            source = input_by_key.get(row_key(codes[name] for name in FACTORS))
            if source is None:
                raise RuntimeError("Minitab PB12 设计点无法与 MiniJMP/NIST 固定输入逐项映射")
            native_rows.append({
                "standard_order": (int(raw_columns[std_column][index])
                                   if std_column else index + 1),
                "run_order": (int(raw_columns[run_column][index])
                              if run_column else index + 1),
                **codes, "Y": source["Y"],
            })
        raw.append("===== PBDESIGN native columns =====\n" + repr(names)
                   + "\n===== mapped design rows and response =====\n"
                   + json.dumps(native_rows, ensure_ascii=False, indent=2))

        def add_column(name, values=None):
            column = columns.Add(None, None, 1)
            column.Name = name
            index = int(columns.Count)
            if values is not None:
                column.SetData(tuple(values), 1, len(values))
            return index

        response_column = add_column("Y", [row["Y"] for row in native_rows])
        output_columns = {name: add_column(name) for name in ("Fit", "Resid", "Coef")}
        matrices = worksheet.Matrices
        existing = {str(matrices.Item(i).Name).casefold()
                    for i in range(1, int(matrices.Count) + 1)}
        matrix_name = next(f"M{i}" for i in range(1, 100) if f"m{i}" not in existing)
        factor_terms = [f"C{factor_columns[name]}" for name in FACTORS]
        terms = " ".join(factor_terms)
        screen_command = (
            "SCREEN;\n"
            + f"  RESPONSE C{response_column};\n"
            + "  FACTOR " + " ".join(factor_terms) + ";\n"
            + "  TERMS " + terms + ";\n"
            + f"  LEVELS {levels};\n  INUNIT 0;\n"
            + f"  FITS C{output_columns['Fit']};\n"
            + f"  RESIDUALS C{output_columns['Resid']};\n"
            + f"  COEFFICIENTS C{output_columns['Coef']};\n"
            + f"  XMATRIX {matrix_name}."
        )
        _execute(project, app, screen_command, raw, "SCREEN")
        matrix_index = next((i for i in range(1, int(worksheet.Matrices.Count) + 1)
                             if str(worksheet.Matrices.Item(i).Name).casefold()
                             == matrix_name.casefold()), None)
        if matrix_index is None:
            raise RuntimeError(f"SCREEN 未存储矩阵 {matrix_name}")
        matrix = worksheet.Matrices.Item(matrix_index)
        n, p = int(matrix.RowCount), int(matrix.ColumnCount)
        if (n, p) != (12, 8):
            raise RuntimeError(f"SCREEN XMATRIX 应为 12×8，实际 {n}×{p}")
        flat = [float(value) for value in matrix.GetData()]
        model_matrix = [[flat[column * n + row] for column in range(p)]
                        for row in range(n)]
        expected = {term: ([1.0] * n if term == "截距"
                           else [row[term] for row in native_rows]) for term in TERMS}
        term_columns = {}
        for column in range(p):
            actual = [model_matrix[row][column] for row in range(n)]
            matches = [term for term, vector in expected.items()
                       if np.allclose(actual, vector, rtol=0, atol=1e-12)]
            if len(matches) != 1 or matches[0] in term_columns:
                raise RuntimeError(f"Minitab SCREEN XMATRIX 列映射不唯一: {column}, {matches}")
            term_columns[matches[0]] = column
        if set(term_columns) != set(TERMS):
            raise RuntimeError(f"Minitab SCREEN 项映射不完整: {term_columns}")
        coefficients_raw = _column_values(columns.Item(output_columns["Coef"]))[:p]
        coefficients = {term: coefficients_raw[index]
                        for term, index in term_columns.items()}
        fits = _column_values(columns.Item(output_columns["Fit"]))[:n]
        residuals = _column_values(columns.Item(output_columns["Resid"]))[:n]
        mtb_result = {
            "version": version, "app_path": app_path, "process_path": process_path,
            "design_command": design_command, "screen_command": screen_command,
            "design_columns": names, "matrix_name": matrix_name,
            "design_rows": native_rows, "term_columns": term_columns,
            "coefficients": coefficients, "model_matrix": model_matrix,
            "rank": int(np.linalg.matrix_rank(model_matrix)),
            "fits": fits, "residuals": residuals,
        }
        MINITAB.write_text(json.dumps(mtb_result, ensure_ascii=False, indent=2), encoding="utf-8")
        RAW.write_text("\n\n".join(raw) + "\n", encoding="utf-8")
        print(f"Minitab {version}: PBDESIGN + SCREEN; matrix={n}×{p}, "
              f"rank={mtb_result['rank']}; direct coefficients/fits/residuals stored", flush=True)
        return 0
    except Exception:
        raw.append("===== worker exception =====\n" + traceback.format_exc())
        RAW.write_text("\n\n".join(raw) + "\n", encoding="utf-8")
        traceback.print_exc()
        return 1
    finally:
        matrices = columns = worksheet = project = ui = app = None


def derive_minitab_stats(mtb):
    import numpy as np
    from scipy import stats

    x = np.asarray(mtb["model_matrix"], dtype=float)
    rows = mtb["design_rows"]
    y = np.asarray([row["Y"] for row in rows], dtype=float)
    fits = np.asarray(mtb["fits"], dtype=float)
    residuals = np.asarray(mtb["residuals"], dtype=float)
    n, p = x.shape
    rank = int(np.linalg.matrix_rank(x))
    if (n, p, rank) != (12, 8, 8):
        raise ValueError("Minitab SCREEN 主效应矩阵的秩/维度不符")
    np.testing.assert_allclose(y - fits, residuals, rtol=0, atol=2e-9)
    sse = float(residuals @ residuals)
    sst = float(np.sum((y - y.mean())**2))
    ssr = max(0.0, sst - sse)
    df = n - rank
    model_df = rank - 1
    mse = sse / df
    model_f = (ssr / model_df) / mse
    inverse = np.linalg.inv(x.T @ x)
    coefficients = np.asarray([mtb["coefficients"][term] for term in TERMS])
    se = np.sqrt(np.maximum(np.diag(inverse) * mse, 0))
    t_value = coefficients / se
    main_anova = {}
    for factor in FACTORS:
        term_column = mtb["term_columns"][factor]
        reduced = np.delete(x, term_column, axis=1)
        beta = np.linalg.lstsq(reduced, y, rcond=None)[0]
        ss = max(0.0, float(np.sum((y - reduced @ beta)**2)) - sse)
        f_value = ss / mse
        main_anova[factor] = {
            "ss": ss, "df": 1, "ms": ss, "f": f_value,
            "p": float(stats.f.sf(f_value, 1, df)),
            "se": float(se[term_column]), "t": float(t_value[term_column]),
            "coefficient_p": float(2 * stats.t.sf(abs(t_value[term_column]), df)),
            "effect": 2 * float(coefficients[term_column]),
        }
    base = x
    interaction_matrix = np.column_stack([
        [row[a] * row[b] for row in rows] for a, b in combinations(FACTORS, 2)
    ])
    aliases = np.linalg.lstsq(base, interaction_matrix, rcond=None)[0]
    interactions = [f"{a}*{b}" for a, b in combinations(FACTORS, 2)]
    return {
        "rank": rank, "n": n, "p": p, "model_df": model_df,
        "error_df": df, "total_df": n - 1, "sse": sse, "sst": sst,
        "ssr": ssr, "mse": mse, "s": math.sqrt(mse),
        "r2": 1 - sse / sst,
        "adjusted_r2": 1 - (sse / df) / (sst / (n - 1)),
        "model_f": model_f,
        "model_p": float(stats.f.sf(model_f, model_df, df)),
        "main_anova": main_anova,
        "effects": {name: main_anova[name]["effect"] for name in FACTORS},
        "alias_matrix": {"rows": list(TERMS), "columns": interactions,
                         "values": aliases.tolist()},
    }


def compare_case(local, mtb):
    result_rows = []
    direct_design = "Minitab 19 PBDESIGN worksheet storage (DIRECT)"
    direct_matrix = "Minitab 19 SCREEN XMATRIX (DIRECT)"
    direct_model = "Minitab 19 SCREEN COEFFICIENTS/FITS/RESIDUALS (DIRECT)"
    derived = ("DERIVED: Minitab SCREEN XMATRIX, coefficients, fits/residuals, "
               "fixed response and scipy.stats")
    local_by_key = {row_key(row[name] for name in FACTORS): row for row in local["fits"]}
    mtb_by_key = {row_key(row[name] for name in FACTORS): index
                  for index, row in enumerate(mtb["design_rows"])}
    if set(local_by_key) != set(mtb_by_key):
        raise ValueError("Minitab PB12 因子矩阵不能与 MiniJMP/NIST 列映射")
    for key in sorted(local_by_key):
        local_row, index = local_by_key[key], mtb_by_key[key]
        native = mtb["design_rows"][index]
        label = str(key)
        for factor in FACTORS:
            result_rows.append(compare_values(1, "design", label, factor,
                                              native[factor], local_row[factor],
                                              direct_design, "MiniJMP create_pb (NIST PB12 mapping)"))
        result_rows.append(compare_values(1, "design", label, "Y", native["Y"],
                                          local_row["Y"], "Fixed input CSV (shared DIRECT)",
                                          "Fixed input CSV (shared DIRECT)"))
        for term, column in mtb["term_columns"].items():
            local_column = local["terms"].index(term)
            result_rows.append(compare_values(1, "model_matrix", label, term,
                                              mtb["model_matrix"][index][column],
                                              local_row["matrix"][local_column], direct_matrix,
                                              "MiniJMP screening main-effects matrix (DIRECT)"))
        result_rows.append(compare_values(1, "fit", label, "fitted", mtb["fits"][index],
                                          local_row["fit"], direct_model,
                                          "MiniJMP analyze_pb"))
        result_rows.append(compare_values(1, "fit", label, "residual", mtb["residuals"][index],
                                          local_row["residual"], direct_model,
                                          "MiniJMP analyze_pb"))
    for term in TERMS:
        result_rows.append(compare_values(1, "coefficient", term, "estimate",
                                          mtb["coefficients"][term], local["coefficients"][term],
                                          direct_model, "MiniJMP analyze_pb"))
    stats = derive_minitab_stats(mtb)
    local_summary = local["summary"]
    for metric in ("rank", "model_df", "error_df", "total_df", "sse", "sst", "ssr",
                   "mse", "s", "r2", "adjusted_r2", "model_f", "model_p"):
        result_rows.append(compare_values(1, "model_summary", "model", metric,
                                          stats[metric], local_summary[metric], derived,
                                          "MiniJMP analyze_pb"))
    for factor in FACTORS:
        native = stats["main_anova"][factor]
        result_rows.append(compare_values(1, "main_effect", factor, "effect",
                                          native["effect"], local["effects"][factor],
                                          "DERIVED: 2 × Minitab coded coefficient",
                                          "MiniJMP analyze_pb effects"))
        for metric in ("ss", "df", "ms", "f", "p", "se", "t", "coefficient_p"):
            result_rows.append(compare_values(1, "main_effect", factor, metric,
                                              native[metric],
                                              local["main_anova"][factor][metric],
                                              derived, "MiniJMP analyze_pb"))
    local_alias = local["alias_matrix"]
    for row_index, base_term in enumerate(stats["alias_matrix"]["rows"]):
        local_row = local_alias["rows"].index(base_term)
        for column_index, interaction in enumerate(stats["alias_matrix"]["columns"]):
            local_column = local_alias["columns"].index(interaction)
            result_rows.append(compare_values(
                1, "alias_projection", base_term, interaction,
                stats["alias_matrix"]["values"][row_index][column_index],
                local_alias["values"][local_row][local_column],
                "DERIVED: Minitab PBDESIGN matrix projection",
                "MiniJMP analyze_pb actual-matrix projection"))
    mtb_effect_order = sorted(FACTORS, key=lambda name: (-abs(stats["effects"][name]), name))
    local_effect_order = sorted(FACTORS, key=lambda name: (-abs(local["effects"][name]), name))
    for factor in FACTORS:
        result_rows.append(compare_values(1, "effect_ranking", factor, "rank",
                                          mtb_effect_order.index(factor) + 1,
                                          local_effect_order.index(factor) + 1,
                                          "DERIVED: Minitab effect magnitude, ties by factor ID",
                                          "MiniJMP effect magnitude, ties by factor ID"))
    return result_rows, stats


def write_report(rows, status, reason=""):
    counts = {name: sum(row["status"] == name for row in rows)
              for name in ("PASS", "FAIL", "N/A", "UNSUPPORTED")}
    sources = {name: sum(name in row["minitab_value_source"] for row in rows)
               for name in ("DIRECT", "DERIVED", "DISPLAY")}
    measured = [row for row in rows if row["absolute_error"] is not None]
    maximum = max(measured, key=lambda row: row["absolute_error"], default=None)
    report = ["# MiniJMP × Minitab 19 Plackett–Burman 12-run 对标", "",
              f"**阶段状态：{status}**", "",
              f"比较计数：PASS {counts['PASS']} / FAIL {counts['FAIL']} / "
              f"N/A {counts['N/A']} / UNSUPPORTED {counts['UNSUPPORTED']}。",
              f"来源分类（Minitab 侧）：DIRECT {sources['DIRECT']} / "
              f"DERIVED {sources['DERIVED']} / DISPLAY {sources['DISPLAY']}。",
              (f"最大绝对误差：{maximum['absolute_error']:.10g}，"
               f"{maximum['section']} / {maximum['term']} / {maximum['statistic']}。"
               if maximum else "最大绝对误差：无可比较数值项。"), "",
              "## 方法与范围", "",
              "- 固定设计为 12 次运行、7 个连续两水平因子，-1/+1 编码，无中心点、重复或区组；MiniJMP 点集另与冻结 NIST PB12 独立 fixture 核对。响应包含主效应与多个二阶交互，主效应模型不完全拟合。",
              "- Minitab 19 原生 `PBDESIGN 7 12` 与 `SCREEN` 拟合七个主效应；Minitab 的系数按 coded level 存储，效果值按 2×系数换算。",
              "- DIRECT 包含设计矩阵、SCREEN XMATRIX、系数、拟合值与残差；ANOVA、标准误、t/F/P、效果排序及 2FI→主效应投影由 Minitab 高精度矩阵和固定数据 DERIVED。",
              "- PB 不提供独立纯误差：12 个设置均唯一，误差自由度为 4，SSE 用于主效应模型推断。完整 8×21 截距/主效应对二因子交互投影由 Minitab 原生矩阵重建，不称为 SCREEN 原生别名表。",
              "- 2FI 部分混杂按实际矩阵投影比较；不采用正规分数因子的 defining relation 或完整别名等式。效果排名并列时按因子 ID 升序打破并列。", "",
              "## 执行结果", "",
              f"Minitab 版本：{json.loads(MINITAB.read_text(encoding='utf-8'))['version']}" if MINITAB.is_file() else "Minitab 版本：未取得",
              f"输入行数：{len(read_input()) if INPUT.is_file() else 0}。",
              "固定响应、原生命令和完整输出见 `doe_pb_input.csv`、`doe_pb_session_commands.txt`、`doe_pb_minitab_raw.txt`。"]
    if reason:
        report.extend(["", "## 未完成原因", "", reason])
    report.extend(["", "## 证据文件", "",
                   "两侧模型 JSON、数值比较 CSV、独立 PB12 fixture 映射与本报告均保存在项目证据目录。"])
    REPORT.write_text("\n".join(report) + "\n", encoding="utf-8")
    return counts, sources, maximum


def parent_main():
    if (not PROJECT_PYTHON.is_file()
            or Path(sys.executable).resolve() != PROJECT_PYTHON.resolve()):
        raise RuntimeError(f"请使用项目解释器运行: {PROJECT_PYTHON}")
    levels = " ".join("-1 1" for _ in FACTORS)
    design_command = f"PBDESIGN 7 12;\n  LEVELS {levels};\n  DESIGN."
    COMMANDS.write_text(
        "# Native Minitab 19 PBDESIGN: 12 runs, 7 two-level factors\n"
        + design_command + "\n\n"
        + "# Fit only estimable main effects and retain the native model matrix\n"
        + "SCREEN;\n  RESPONSE <Y>;\n  FACTOR <A> <B> <C> <D> <E> <F> <G>;\n"
        + "  TERMS <A> <B> <C> <D> <E> <F> <G>;\n"
        + f"  LEVELS {levels};\n  INUNIT 0;\n"
        + "  FITS <Fit>;\n  RESIDUALS <Resid>;\n  COEFFICIENTS <Coef>;\n  XMATRIX <M>.\n",
        encoding="utf-8")
    command = [str(PROJECT_PYTHON), "-X", "utf8", str(Path(__file__).resolve())]
    local = subprocess.run(command + ["--minijmp-worker"], capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=240)
    print(local.stdout.rstrip(), flush=True)
    if local.stderr.strip():
        print("MiniJMP worker stderr:\n" + local.stderr.rstrip(), flush=True)
    if local.returncode:
        write_csv(COMPARISON, [])
        write_report([], "BLOCKED", "MiniJMP PB worker 执行失败；详见控制台输出。")
        return 1
    process = subprocess.run(command + ["--com-worker"], capture_output=True,
                             text=True, encoding="utf-8", errors="replace", timeout=360)
    if process.stdout.strip():
        print(process.stdout.rstrip(), flush=True)
    if process.stderr.strip():
        print("Minitab worker stderr:\n" + process.stderr.rstrip(), flush=True)
    for _ in range(40):
        if not running_minitab_pids():
            break
        time.sleep(.5)
    pids = running_minitab_pids()
    if process.returncode or pids or not MINITAB.is_file():
        reason = f"Minitab COM worker 退出码 {process.returncode}；残留 Mtb.exe={pids}。"
        write_csv(COMPARISON, [])
        write_report([], "BLOCKED", reason + "实际命令/错误见 doe_pb_minitab_raw.txt。")
        print("PB stage BLOCKED: " + reason, flush=True)
        return 1
    local = json.loads(MINIJMP.read_text(encoding="utf-8"))
    native = json.loads(MINITAB.read_text(encoding="utf-8"))
    if (native["version"] != "19.1.0.1" or canonical(native["app_path"]) != canonical(MTB_EXE)
            or canonical(native["process_path"]) != canonical(MTB_EXE)):
        write_csv(COMPARISON, [])
        write_report([], "BLOCKED", "Minitab 19.1.0.1 COM 程序路径或版本不符。")
        return 1
    comparisons, _ = compare_case(local, native)
    write_csv(COMPARISON, comparisons)
    status = ("FAIL" if any(row["status"] == "FAIL" for row in comparisons)
              else "PARTIAL" if any(row["status"] == "UNSUPPORTED" for row in comparisons)
              else "PASS")
    counts, _, maximum = write_report(comparisons, status)
    print(f"PB stage {status}: {counts}; max abs error="
          f"{maximum['absolute_error'] if maximum else None}; Minitab PID 已退出。", flush=True)
    return 1 if status in ("FAIL", "BLOCKED") else 0


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--minijmp-worker":
        try:
            run_minijmp_worker()
            raise SystemExit(0)
        except Exception:
            traceback.print_exc()
            raise SystemExit(1)
    if len(sys.argv) == 2 and sys.argv[1] == "--com-worker":
        raise SystemExit(minitab_worker())
    raise SystemExit(parent_main())
