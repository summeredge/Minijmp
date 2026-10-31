"""MiniJMP × Minitab 19 balanced 2-hard × 2-easy split-plot parity check."""
from __future__ import annotations

import csv
import ctypes
import json
import math
import subprocess
import sys
import time
import traceback
from collections import Counter, defaultdict
from fractions import Fraction
from itertools import combinations
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
MTB_EXE = Path(r"D:\Program\Minitab 19\Mtb.exe")
PROJECT_PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
INPUT = OUT / "doe_splitplot_input.csv"
COMMANDS = OUT / "doe_splitplot_session_commands.txt"
RAW = OUT / "doe_splitplot_minitab_raw.txt"
MINIJMP = OUT / "doe_splitplot_minijmp.json"
MINITAB = OUT / "doe_splitplot_minitab.json"
COMPARISON = OUT / "doe_splitplot_comparison.csv"
REPORT = OUT / "doe_splitplot_acceptance_report.md"
FACTORS = tuple("AB")
HARD = frozenset("A")
WHOLE_PLOT_FACTOR = "A"
SUBPLOT_FACTOR = "B"
BLOCKS = 3
RUNS = 12
RUNS_PER_BLOCK = 4
WHOLE_PLOTS = 6
SUBPLOTS_PER_WHOLE_PLOT = 2
WHOLE_PLOT_DF = 2
SUBPLOT_DF = 4
BLOCK_OFFSETS = {1: Fraction(-1), 2: Fraction(0), 3: Fraction(1)}
WP_OFFSETS = {1: Fraction(-1, 2), 2: Fraction(1, 4), 3: Fraction(1, 4)}
SP_OFFSETS = {1: Fraction(-1, 4), 2: Fraction(1, 8), 3: Fraction(1, 8)}
COEFFICIENTS = {"A": Fraction(2), "B": Fraction(3, 2), "A:B": Fraction(-1, 2)}
TREATMENT_TERMS = tuple(
    ":".join(term) for order in range(1, len(FACTORS) + 1)
    for term in combinations(FACTORS, order)
)

from verify_doe_ccd import (canonical, capture_command_output, compare_values,
                            running_minitab_pids, write_csv)


def point_key(block, *values):
    return (int(block), *(round(float(value), 12) for value in values))


def treatment_value(codes, term):
    return math.prod(codes[name] for name in term.split(":"))


def response_value(block, codes):
    fixed = sum(float(COEFFICIENTS[term]) * treatment_value(codes, term)
                for term in TREATMENT_TERMS)
    return float(100 + float(BLOCK_OFFSETS[block]) + fixed
                 + float(WP_OFFSETS[block]) * codes[WHOLE_PLOT_FACTOR]
                 + float(SP_OFFSETS[block]) * codes[SUBPLOT_FACTOR])


def model_matrix(rows):
    import numpy as np

    blocks = sorted({row["block"] for row in rows})
    block = np.column_stack([[float(row["block"] == level) for row in rows]
                             for level in blocks])
    terms = np.column_stack([[treatment_value(row, term) for row in rows]
                             for term in TREATMENT_TERMS])
    return np.column_stack((block, terms)), blocks


def write_input(rows):
    fields = ("run_id", "standard_order", "run_order", "block", "replicate",
              "whole_plot_id", "subplot_id", "whole_plot_order", "subplot_order", *FACTORS, "Y")
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
                         "run_order": int(row["run_order"]), "block": int(row["block"]),
                         "replicate": int(row["replicate"]),
                         "whole_plot_id": row["whole_plot_id"],
                         "subplot_id": row["subplot_id"],
                         "whole_plot_order": int(row["whole_plot_order"]),
                         "subplot_order": int(row["subplot_order"]),
                         **{name: float(row[name]) for name in FACTORS},
                         "Y": float(row["Y"])})
    if (len(rows) != RUNS
            or Counter(row["block"] for row in rows)
            != dict.fromkeys(range(1, BLOCKS + 1), RUNS_PER_BLOCK)
            or len({row["whole_plot_id"] for row in rows}) != WHOLE_PLOTS):
        raise ValueError("最小裂区输入必须为 3 区组、6 个整区、12 次运行")
    cells = defaultdict(list)
    for row in rows:
        if any(row[name] not in (-1.0, 1.0) for name in FACTORS):
            raise ValueError("裂区因子必须使用 -1/+1 编码")
        cells[(row["block"], row["whole_plot_id"])].append(row)
    if any(len(group) != SUBPLOTS_PER_WHOLE_PLOT
           or len({row[WHOLE_PLOT_FACTOR] for row in group}) != 1
           or len({row[SUBPLOT_FACTOR] for row in group}) != SUBPLOTS_PER_WHOLE_PLOT
           for group in cells.values()):
        raise ValueError("每个整区必须固定 A 并包含 B 的两个子区水平")
    if any(not math.isfinite(row["Y"]) for row in rows):
        raise ValueError("裂区响应必须全部为有限值")
    return rows


def _fraction_close(value, expected, tol=2e-10):
    return math.isclose(float(value), float(expected), rel_tol=0, abs_tol=tol)


def run_minijmp_worker():
    if (not PROJECT_PYTHON.is_file()
            or Path(sys.executable).resolve() != PROJECT_PYTHON.resolve()):
        raise RuntimeError(f"请使用项目解释器运行: {PROJECT_PYTHON}")
    sys.path.insert(0, str(ROOT / "code"))
    import numpy as np
    import pandas as pd
    from doe_core import DesignSpec, FactorSpec
    from doe_splitplot import create_split_plot
    from doe_splitplot_analysis import analyze_split_plot

    factors = tuple(FactorSpec(name, name, -1, 1,
                               randomization_role=("hard_to_change" if name in HARD
                                                   else "easy_to_change"))
                    for name in FACTORS)
    spec = DesignSpec("minitab19-splitplot-parity", factors, ("Y",), seed=19,
                      design_type="split_plot", schema_version=5, block_count=BLOCKS,
                      construction_version="v2", randomization_unit="whole_plot",
                      error_structure="split_plot")
    frame, metadata = create_split_plot(spec)
    columns = metadata["column_map"]
    rows = []
    for _, row in frame.iterrows():
        settings = {name: float(row[columns["factors"][name]]) for name in FACTORS}
        block = int(row[columns["block"]])
        rows.append({"run_id": str(row[columns["run_id"]]),
                     "standard_order": int(row[columns["standard_order"]]),
                     "run_order": int(row[columns["run_order"]]), "block": block,
                     "replicate": int(row[columns["replicate"]]),
                     "whole_plot_id": str(row[columns["whole_plot_id"]]),
                     "subplot_id": str(row[columns["subplot_id"]]),
                     "whole_plot_order": int(row[columns["whole_plot_order"]]),
                     "subplot_order": int(row[columns["subplot_order"]]),
                     **settings, "Y": response_value(block, settings)})
    write_input(rows)
    rows = read_input()
    frame.loc[:, columns["responses"]["Y"]] = pd.array([row["Y"] for row in rows],
                                                        dtype="Float64")
    analysis = analyze_split_plot(frame, metadata, "Y")
    runs = analysis["design"].runs
    run_rows = {row["run_id"]: row for row in rows}
    design_rows = []
    for run in runs:
        row = run_rows[str(run.run_id)]
        design_rows.append(row)
    x_ref, levels = model_matrix(design_rows)
    if analysis["rank"] != 6 or analysis["p"] != 6 or analysis["df"] != 6:
        raise AssertionError("裂区完整模型秩与残差自由度不符")
    np.testing.assert_allclose(
        x_ref.T @ x_ref,
        np.diag([4.0] * BLOCKS + [float(RUNS)] * len(TREATMENT_TERMS)),
        rtol=0, atol=1e-12)
    anova = {item["term"]: item for item in analysis["anova"]}
    expected_wp_ss = Fraction(3, 2)
    expected_sp_ss = Fraction(3, 8)
    expected_term_ss = {term: RUNS * coefficient**2
                        for term, coefficient in COEFFICIENTS.items()}
    expected_total = Fraction(703, 8)
    if (not _fraction_close(analysis["error_strata"]["whole_plot_error"]["ss"], expected_wp_ss)
            or not _fraction_close(analysis["error_strata"]["subplot_error"]["ss"], expected_sp_ss)
            or analysis["error_strata"]["whole_plot_error"]["df"] != WHOLE_PLOT_DF
            or analysis["error_strata"]["subplot_error"]["df"] != SUBPLOT_DF
            or not _fraction_close(anova["block"]["ss"], Fraction(8))
            or not _fraction_close(analysis["sse"], expected_wp_ss + expected_sp_ss)
            or not _fraction_close(analysis["sst"], expected_total)):
        raise AssertionError("裂区独立有理数参考未满足 WP/SP 分层预期")
    if any(not _fraction_close(anova[term]["coefficient"], coefficient)
           or not _fraction_close(anova[term]["ss"], expected_term_ss[term])
           for term, coefficient in COEFFICIENTS.items()):
        raise AssertionError("裂区固定效应系数或平方和偏离独立有理数参考")
    local_matrix = x_ref
    if local_matrix.shape != (RUNS, 6) or np.linalg.matrix_rank(local_matrix) != 6:
        raise AssertionError("最小裂区参考模型矩阵必须为 12×6 满秩")

    fit_rows = []
    for index, run in enumerate(runs):
        row = run_rows[str(run.run_id)]
        fit_rows.append({**row, "fit": float(analysis["fitted"][index]),
                         "residual": float(analysis["residuals"][index]),
                         "whole_plot_residual": float(
                             analysis["whole_plot_residual_contribution"][index]),
                         "subplot_residual": float(
                             analysis["subplot_residual_contribution"][index]),
                         "matrix": [float(value) for value in local_matrix[index]]})
    result = {
        "n": int(analysis["n"]), "p": int(analysis["p"]),
        "rank": int(analysis["rank"]), "df": int(analysis["df"]),
        "blocks": list(levels), "terms": list(TREATMENT_TERMS),
        "fits": fit_rows,
        "anova": [{key: (bool(value) if key in ("available", "inference_available")
                           else _number(value) if isinstance(value, (int, float))
                           or value is None else value)
                   for key, value in item.items()} for item in analysis["anova"]],
        "error_strata": {
            name: {"ss": float(item["ss"]), "df": int(item["df"]),
                   "ms": _number(item["ms"]), "available": bool(item["available"]),
                   "reason": item["reason"]}
            for name, item in analysis["error_strata"].items()},
        "summary": {"sst": float(analysis["sst"]), "sse": float(analysis["sse"]),
                    "block_ss": float(anova["block"]["ss"]),
                    "whole_plot_error_ss": float(
                        analysis["error_strata"]["whole_plot_error"]["ss"]),
                    "whole_plot_error_df": int(
                        analysis["error_strata"]["whole_plot_error"]["df"]),
                    "whole_plot_error_ms": float(
                        analysis["error_strata"]["whole_plot_error"]["ms"]),
                    "subplot_error_ss": float(
                        analysis["error_strata"]["subplot_error"]["ss"]),
                    "subplot_error_df": int(
                        analysis["error_strata"]["subplot_error"]["df"]),
                    "subplot_error_ms": float(
                        analysis["error_strata"]["subplot_error"]["ms"])},
        "status": analysis["status"],
    }
    MINIJMP.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("MiniJMP Split-Plot self-check: 12 runs, 6 whole plots, rank 6, "
          "WP df/SS=2/1.5, subplot df/SS=4/0.375, independent Fraction oracle PASS",
          flush=True)


def _number(value):
    return None if value is None else float(value)


def _column_values(column):
    values = column.GetData()
    return [float(values)] if isinstance(values, (int, float)) else [float(value) for value in values]


def _find_column(names, wanted, required=True):
    targets = {str(value).replace(" ", "").casefold() for value in wanted}
    for index, name in enumerate(names, 1):
        if str(name).replace(" ", "").casefold() in targets:
            return index
    if required:
        raise RuntimeError(f"Minitab Split-Plot 缺少列 {tuple(wanted)}；实际列={names}")
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
        design_command = (
            f"SPDESIGN {len(FACTORS)} {len(HARD)};\n"
            f"  PLOTS {2 ** len(HARD)} {2 ** (len(FACTORS) - len(HARD))};\n"
            "  WPREPLICATES 3;\n  RBLOCK;\n  RANDOMIZE 19;\n"
            f"  LEVELS {levels};\n  DESIGN.")
        _execute(project, app, design_command, raw, "SPDESIGN")
        worksheet = project.ActiveWorksheet
        columns = worksheet.Columns
        names = [str(columns.Item(index).Name) for index in range(1, int(columns.Count) + 1)]
        factor_columns = {name: _find_column(names, (name, f"{name}[HTC]"))
                          for name in FACTORS}
        block_column = _find_column(names, ("Blocks", "Block", "区组"))
        std_column = _find_column(names, ("StdOrder", "StandardOrder", "标准序"), False)
        run_column = _find_column(names, ("RunOrder", "运行序"), False)
        native_wpid_column = _find_column(
            names, ("WPID", "WholePlot", "WholePlotID", "整区ID", "整区"), False)
        read_columns = set(factor_columns.values()) | {block_column} | {
            c for c in (std_column, run_column, native_wpid_column) if c is not None}
        raw_columns = {index: columns.Item(index).GetData() for index in read_columns}

        def values(index):
            data = raw_columns[index]
            if isinstance(data, (int, float, str)):
                return [data]
            return list(data)

        if len(values(factor_columns["A"])) != RUNS:
            raise RuntimeError(f"SPDESIGN 应生成 {RUNS} 次运行，实际 {len(values(factor_columns['A']))}")
        raw_block_values = values(block_column)
        block_levels = sorted(set(raw_block_values))
        if len(block_levels) != BLOCKS:
            raise RuntimeError(f"SPDESIGN 应生成 {BLOCKS} 个 RBLOCK 区组，实际={block_levels}")
        block_map = {value: index + 1 for index, value in enumerate(block_levels)}
        local_by_key = {point_key(row["block"], *(row[name] for name in FACTORS)): row
                        for row in rows}
        native_rows = []
        native_group_rows = defaultdict(list)
        for index in range(RUNS):
            codes = {name: float(values(factor_columns[name])[index]) for name in FACTORS}
            block_value = raw_block_values[index]
            block = block_map[block_value]
            source = local_by_key.get(point_key(block, *(codes[name] for name in FACTORS)))
            if source is None:
                raise RuntimeError(f"SPDESIGN 因子/区组无法映射固定工作表：{block}, {codes}")
            whole_plot_key = (block, *(codes[name] for name in sorted(HARD)))
            native_group_rows[whole_plot_key].append(index)
            native_rows.append({
                "standard_order": (int(values(std_column)[index])
                                   if std_column is not None else index + 1),
                "run_order": (int(values(run_column)[index])
                              if run_column is not None else index + 1),
                "block": block, "source_block": str(block_value),
                "whole_plot_key": list(whole_plot_key),
                "native_whole_plot_id": (str(values(native_wpid_column)[index])
                                         if native_wpid_column is not None else None),
                "whole_plot_id": source["whole_plot_id"],
                "subplot_id": source["subplot_id"], **codes, "Y": source["Y"],
            })
        if (len(native_group_rows) != WHOLE_PLOTS
                or any(len(group) != SUBPLOTS_PER_WHOLE_PLOT
                       for group in native_group_rows.values())):
            raise RuntimeError(
                f"SPDESIGN 需形成 {WHOLE_PLOTS} 个整区，每个整区包含 "
                f"{SUBPLOTS_PER_WHOLE_PLOT} 个子区")
        for key, indices in native_group_rows.items():
            if len({tuple(native_rows[index][name] for name in FACTORS if name not in HARD)
                    for index in indices}) != SUBPLOTS_PER_WHOLE_PLOT:
                raise RuntimeError(f"整区内子区因子水平不完整：{key}")
        native_id_to_key = defaultdict(set)
        key_to_native_ids = defaultdict(set)
        for row in native_rows:
            if row["native_whole_plot_id"] is not None:
                native_id_to_key[(row["block"], row["native_whole_plot_id"])].add(
                    tuple(row["whole_plot_key"]))
                key_to_native_ids[tuple(row["whole_plot_key"])].add(
                    row["native_whole_plot_id"])
        if native_id_to_key and (any(len(values) != 1 for values in native_id_to_key.values())
                                 or any(len(values) != 1 for values in key_to_native_ids.values())):
            raise RuntimeError("Minitab 原生 whole-plot ID 与硬因子/区组分组不一致")
        group_ids = {key: index + 1 for index, key in enumerate(sorted(native_group_rows))}
        raw.append("===== SPDESIGN native columns =====\n" + repr(names)
                   + "\n===== mapped block/whole-plot rows =====\n"
                   + json.dumps(native_rows, ensure_ascii=False, indent=2))

        def add_column(name, data):
            column = columns.Add(None, None, 1)
            column.Name = name
            column.SetData(tuple(data), 1, len(data))
            return int(columns.Count)

        response_column = add_column("Y", [row["Y"] for row in native_rows])
        wpid_column = add_column("CodexWPID", [group_ids[tuple(row["whole_plot_key"])]
                                              for row in native_rows])
        output_columns = {name: int(columns.Count) + offset for offset, name in enumerate(
            ("Fit", "Resid", "WPResid", "Coef"), 1)}
        for name in output_columns:
            column = columns.Add(None, None, 1)
            column.Name = name
        matrices = worksheet.Matrices
        existing = {str(matrices.Item(i).Name).casefold()
                    for i in range(1, int(matrices.Count) + 1)}
        matrix_name = next(f"M{i}" for i in range(1, 100) if f"m{i}" not in existing)
        factor_c = {name: factor_columns[name] for name in FACTORS}
        terms = [f"C{block_column}", *[f"C{factor_c[name]}" for name in FACTORS]]
        for order in range(2, len(FACTORS) + 1):
            for subset in combinations(FACTORS, order):
                terms.append("*".join(f"C{factor_c[name]}" for name in subset))
        analysis_command = (
            "SPFACTORIAL;\n"
            + f"  RESPONSE C{response_column};\n"
            + "  FACTOR " + " ".join(f"C{factor_c[name]}" for name in FACTORS) + ";\n"
            + "  HTCHANGE " + " ".join(f"C{factor_c[name]}" for name in sorted(HARD)) + ";\n"
            + f"  WPID C{wpid_column};\n  BLOCKS C{block_column};\n"
            + "  TERMS " + " ".join(terms) + ";\n"
            + "  INUNIT 0;\n"
            + f"  LEVELS {levels};\n  FITS C{output_columns['Fit']};\n"
            + f"  RESIDUALS C{output_columns['Resid']};\n"
            + f"  WRESIDUALS C{output_columns['WPResid']};\n"
            + f"  COEFFICIENTS C{output_columns['Coef']};\n"
            + "  TANOVA;\n  TCOEFFICIENTS;\n  TSUMMARY;\n"
            + f"  XMATRIX {matrix_name}."
        )
        _execute(project, app, analysis_command, raw, "SPFACTORIAL")
        matrix_index = next((i for i in range(1, int(worksheet.Matrices.Count) + 1)
                             if str(worksheet.Matrices.Item(i).Name).casefold()
                             == matrix_name.casefold()), None)
        if matrix_index is None:
            raise RuntimeError(f"SPFACTORIAL 未存储 XMATRIX {matrix_name}")
        matrix = worksheet.Matrices.Item(matrix_index)
        n, p = int(matrix.RowCount), int(matrix.ColumnCount)
        if n != RUNS or p < BLOCKS + len(TREATMENT_TERMS):
            raise RuntimeError(
                f"SPFACTORIAL XMATRIX 应至少为 {RUNS}×{BLOCKS + len(TREATMENT_TERMS)}，"
                f"实际 {n}×{p}")
        flat = [float(value) for value in matrix.GetData()]
        model_matrix = [[flat[column * n + row] for column in range(p)]
                        for row in range(n)]
        expected_treatment = {
            term: [treatment_value(row, term) for row in native_rows]
            for term in TREATMENT_TERMS
        }
        term_columns = {}
        block_indicators = {
            f"BLOCK{block}": [float(row["block"] == block) for row in native_rows]
            for block in range(1, 4)
        }
        expected_basis = {"截距": [1.0] * n, **block_indicators, **expected_treatment}
        for column in range(p):
            actual = [model_matrix[row][column] for row in range(n)]
            matches = [term for term, vector in expected_basis.items()
                       if np.allclose(actual, vector, rtol=0, atol=1e-12)]
            if len(matches) == 1 and matches[0] in expected_treatment:
                term_columns[matches[0]] = column
        if set(term_columns) != set(TREATMENT_TERMS):
            raise RuntimeError(f"Minitab XMATRIX 未包含全部裂区处理项: {term_columns}")
        coefficients_raw = _column_values(columns.Item(output_columns["Coef"]))
        if len(coefficients_raw) < p:
            raise RuntimeError(f"SPFACTORIAL 系数列长度 {len(coefficients_raw)} 小于 XMATRIX 列数 {p}")
        coefficients = {term: coefficients_raw[column]
                        for term, column in term_columns.items()}
        fits = _column_values(columns.Item(output_columns["Fit"]))[:n]
        residuals = _column_values(columns.Item(output_columns["Resid"]))[:n]
        whole_plot_residuals = _column_values(columns.Item(output_columns["WPResid"]))[:n]
        mtb_result = {
            "version": version, "app_path": app_path, "process_path": process_path,
            "design_command": design_command, "analysis_command": analysis_command,
            "design_columns": names, "matrix_name": matrix_name,
            "design_rows": native_rows, "term_columns": term_columns,
            "coefficients": coefficients, "model_matrix": model_matrix,
            "rank": int(np.linalg.matrix_rank(model_matrix)),
            "fits": fits, "residuals": residuals,
            "whole_plot_residuals": whole_plot_residuals,
        }
        MINITAB.write_text(json.dumps(mtb_result, ensure_ascii=False, indent=2), encoding="utf-8")
        RAW.write_text("\n\n".join(raw) + "\n", encoding="utf-8")
        print(f"Minitab {version}: SPDESIGN + SPFACTORIAL; matrix={n}×{p}, "
              f"rank={mtb_result['rank']}; WPID derived from block+hard settings", flush=True)
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

    rows = mtb["design_rows"]
    y = np.asarray([row["Y"] for row in rows], dtype=float)
    x = np.asarray(mtb["model_matrix"], dtype=float)
    fits = np.asarray(mtb["fits"], dtype=float)
    subplot_residuals = np.asarray(mtb["residuals"], dtype=float)
    whole_plot_residuals = np.asarray(mtb["whole_plot_residuals"], dtype=float)
    n, p = x.shape
    rank = int(np.linalg.matrix_rank(x))
    if (n != RUNS or rank != BLOCKS + len(TREATMENT_TERMS) or len(fits) != n
            or len(subplot_residuals) != n or len(whole_plot_residuals) != n):
        raise ValueError(f"Minitab split-plot matrix rank/shape mismatch: {n}x{p}, rank {rank}")
    np.testing.assert_allclose(y - fits, whole_plot_residuals + subplot_residuals,
                               rtol=0, atol=2e-8)
    ss_total = float(np.sum((y - y.mean())**2))
    block_rows = defaultdict(list)
    whole_rows = defaultdict(list)
    for index, row in enumerate(rows):
        block_rows[row["block"]].append(index)
        whole_rows[tuple(row["whole_plot_key"])].append(index)
    blocks = sorted(block_rows)
    whole_plot_means = []
    whole_plot_data = []
    for key in sorted(whole_rows):
        indices = whole_rows[key]
        first = rows[indices[0]]
        whole_plot_means.append(float(np.mean(y[indices])))
        whole_plot_data.append({"block": first["block"],
                                **{name: first[name] for name in FACTORS}})
    hard_terms = tuple(term for term in TREATMENT_TERMS
                       if set(term.split(":")) <= HARD)
    wp_x = np.column_stack([
        [float(item["block"] == block) for item in whole_plot_data] for block in blocks
    ] + [[treatment_value(item, term) for item in whole_plot_data]
         for term in hard_terms])
    wp_beta = np.linalg.lstsq(wp_x, np.asarray(whole_plot_means), rcond=None)[0]
    wp_residuals = np.asarray(whole_plot_means) - wp_x @ wp_beta
    wp_ss = float(sum(len(whole_rows[key]) * residual**2
                      for key, residual in zip(sorted(whole_rows), wp_residuals)))
    wp_residual_by_key = dict(zip(sorted(whole_rows), wp_residuals))
    full_wp_residual = np.asarray([wp_residual_by_key[tuple(row["whole_plot_key"])]
                                   for row in rows])
    subplot_ss = float(subplot_residuals @ subplot_residuals)
    wp_df, sp_df = WHOLE_PLOT_DF, SUBPLOT_DF
    wp_ms, sp_ms = wp_ss / wp_df, subplot_ss / sp_df
    block_means = {block: float(np.mean(y[indices])) for block, indices in block_rows.items()}
    block_ss = float(sum(len(block_rows[block]) * (block_means[block] - y.mean())**2
                         for block in blocks))
    term_values = {term: float(mtb["coefficients"][term]) for term in TREATMENT_TERMS}
    term_anova = {}
    for term, coefficient in term_values.items():
        ss = float(n * coefficient**2)
        hard_only = set(term.split(":")) <= HARD
        mse, error_df, stratum = ((wp_ms, wp_df, "whole_plot_error") if hard_only
                                  else (sp_ms, sp_df, "subplot_error"))
        f_value = ss / mse
        term_anova[term] = {
            "coefficient": coefficient, "effect": 2 * coefficient,
            "ss": ss, "df": 1, "ms": ss, "f": f_value,
            "p": float(stats.f.sf(f_value, 1, error_df)),
            "error_stratum": stratum, "error_df": error_df,
        }
    total_residuals = y - fits
    if not math.isclose(wp_ss + subplot_ss, float(total_residuals @ total_residuals),
                        rel_tol=0, abs_tol=2e-8):
        raise ValueError("Minitab 两层残差平方和未闭合")
    return {
        "n": n, "p": p, "rank": rank, "df": wp_df + sp_df,
        "block_df": len(blocks) - 1, "block_ss": block_ss,
        "whole_plot_error": {"ss": wp_ss, "df": wp_df, "ms": wp_ms},
        "subplot_error": {"ss": subplot_ss, "df": sp_df, "ms": sp_ms},
        "sse": wp_ss + subplot_ss, "sst": ss_total,
        "term_anova": term_anova,
        "derived_whole_plot_residuals": full_wp_residual.tolist(),
        "whole_plot_residuals": whole_plot_residuals.tolist(),
        "subplot_residuals": subplot_residuals.tolist(),
    }


def compare_case(local, mtb):
    import numpy as np

    comparisons = []
    direct_design = "Minitab 19 SPDESIGN worksheet values (DIRECT)"
    direct_matrix = "Minitab 19 SPFACTORIAL XMATRIX (DIRECT)"
    direct_model = "Minitab 19 SPFACTORIAL COEFFICIENTS/FITS/RESIDUALS (DIRECT)"
    derived = ("DERIVED: Minitab split-plot XMATRIX, fixed response, whole-plot grouping "
               "and scipy.stats")
    stats = derive_minitab_stats(mtb)
    local_by_key = {point_key(row["block"], *(row[name] for name in FACTORS)): row
                    for row in local["fits"]}
    mtb_by_key = {point_key(row["block"], *(row[name] for name in FACTORS)): index
                  for index, row in enumerate(mtb["design_rows"])}
    if set(local_by_key) != set(mtb_by_key):
        raise ValueError("Minitab/MiniJMP 裂区设定与区组不能一一映射")
    for key in sorted(local_by_key):
        local_row, index = local_by_key[key], mtb_by_key[key]
        native = mtb["design_rows"][index]
        label = f"block {key[0]} / {key[1:]}"
        for factor in FACTORS:
            comparisons.append(compare_values(1, "design", label, factor,
                                              native[factor], local_row[factor],
                                              direct_design, "MiniJMP create_split_plot"))
        comparisons.append(compare_values(1, "fit", label, "fitted", mtb["fits"][index],
                                          local_row["fit"], direct_model,
                                          "MiniJMP analyze_split_plot"))
        comparisons.append(compare_values(1, "fit", label, "residual",
                                          native["Y"] - mtb["fits"][index],
                                          local_row["residual"],
                                          "DERIVED: Minitab response minus FITS",
                                          "MiniJMP analyze_split_plot"))
        comparisons.append(compare_values(1, "error_contribution", label, "whole_plot_residual",
                                          stats["whole_plot_residuals"][index],
                                          local_row["whole_plot_residual"],
                                          "Minitab SPFACTORIAL WRESIDUALS (DIRECT)",
                                          "MiniJMP analyze_split_plot"))
        comparisons.append(compare_values(
            1, "error_contribution_check", label, "whole_plot_stored_vs_derived",
            stats["whole_plot_residuals"][index],
            stats["derived_whole_plot_residuals"][index],
            "Minitab SPFACTORIAL WRESIDUALS (DIRECT)", derived))
        comparisons.append(compare_values(1, "error_contribution", label, "subplot_residual",
                                          stats["subplot_residuals"][index],
                                          local_row["subplot_residual"],
                                          "Minitab SPFACTORIAL RESIDUALS (DIRECT)",
                                          "MiniJMP analyze_split_plot"))

    ordered_keys = sorted(local_by_key)
    local_x = np.asarray([local_by_key[key]["matrix"] for key in ordered_keys], dtype=float)
    mtb_x = np.asarray([mtb["model_matrix"][mtb_by_key[key]] for key in ordered_keys],
                       dtype=float)
    local_projection = local_x @ np.linalg.pinv(local_x)
    mtb_projection = mtb_x @ np.linalg.pinv(mtb_x)
    projection_error = float(np.max(np.abs(mtb_projection - local_projection)))
    comparisons.append(compare_values(
        1, "model_space", "full fixed model", "projection_max_abs_error",
        projection_error, 0.0, direct_matrix, "MiniJMP full block + treatment matrix",
        ))
    if set(mtb["term_columns"]) != set(TREATMENT_TERMS):
        raise ValueError("Minitab SPFACTORIAL 缺少一个或多个完整处理项")
    for term in TREATMENT_TERMS:
        local_term = next(item for item in local["anova"] if item["term"] == term)
        native_term = stats["term_anova"][term]
        for metric in ("coefficient", "effect", "ss", "df", "ms", "f", "p"):
            comparisons.append(compare_values(
                1, "treatment_effect", term, metric, native_term[metric],
                local_term[metric],
                direct_model if metric == "coefficient" else derived,
                "MiniJMP analyze_split_plot"))
        comparisons.append(compare_values(
            1, "error_stratum", term, "stratum_is_whole_plot",
            1.0 if native_term["error_stratum"] == "whole_plot_error" else 0.0,
            1.0 if local_term["error_stratum"] == "whole_plot_error" else 0.0,
            "Derived from Minitab whole-plot/hard-factor design (DERIVED)",
            "MiniJMP analyze_split_plot"))
    local_anova = {item["term"]: item for item in local["anova"]}
    for term, values in (("block", {"ss": stats["block_ss"], "df": stats["block_df"],
                                     "ms": stats["block_ss"] / stats["block_df"]}),
                         ("whole_plot_error", stats["whole_plot_error"]),
                         ("subplot_error", stats["subplot_error"]),
                         ("total", {"ss": stats["sst"], "df": RUNS - 1})):
        for metric in ("ss", "df", "ms"):
            native_value = values.get(metric)
            local_value = local_anova[term].get(metric)
            comparisons.append(compare_values(1, "error_anova", term, metric,
                                              native_value, local_value,
                                              derived, "MiniJMP analyze_split_plot"))
    return comparisons, stats


def write_report(rows, status, reason=""):
    counts = {name: sum(row["status"] == name for row in rows)
              for name in ("PASS", "FAIL", "N/A", "UNSUPPORTED")}
    sources = {name: sum(name in row["minitab_value_source"] for row in rows)
               for name in ("DIRECT", "DERIVED", "DISPLAY")}
    measured = [row for row in rows if row["absolute_error"] is not None]
    maximum = max(measured, key=lambda row: row["absolute_error"], default=None)
    report = ["# MiniJMP × Minitab 19 平衡 Split-Plot 对标", "",
              f"**阶段状态：{status}**", "",
              f"比较计数：PASS {counts['PASS']} / FAIL {counts['FAIL']} / "
              f"N/A {counts['N/A']} / UNSUPPORTED {counts['UNSUPPORTED']}。",
              f"来源分类（Minitab 侧）：DIRECT {sources['DIRECT']} / "
              f"DERIVED {sources['DERIVED']} / DISPLAY {sources['DISPLAY']}。",
              (f"最大绝对误差：{maximum['absolute_error']:.10g}，"
               f"{maximum['section']} / {maximum['term']} / {maximum['statistic']}。"
               if maximum else "最大绝对误差：无可比较的数值项。"), "",
              "## 方法与范围", "",
              "- 采用最小两因子结构：A（整区）和 B（子区），完整两水平设计分 3 个区组、6 个整区、12 次运行，使整区/子区误差自由度为 2/4；模型含 A、B、A×B。两层误差均非零且由有理数参考分别核验。",
              "- Minitab 19 原生 `SPDESIGN` 与 `SPFACTORIAL`；WPID 按实际区组和 A 水平标识，核验每整区包含 B 的两个水平。",
              "- Minitab 系数、XMATRIX、拟合值、整区残差和子区残差为 DIRECT。ANOVA 两个误差层 SS/MS、各处理项 F/P 和误差自由度按 Minitab 固定输入、whole-plot 分组及高精度输出 DERIVED，并与 MiniJMP 分层 ANOVA 比较。",
              "- 固定区组模型秩与投影子空间均核对；A 使用 whole-plot error（df=2），B 与 A×B 使用 subplot error（df=4）。不将结果化简为普通 OLS；未比较随机区组方差分量、REML 或非平衡设计。", "",
              "## 执行结果", "",
              f"Minitab 版本：{json.loads(MINITAB.read_text(encoding='utf-8'))['version']}" if MINITAB.is_file() else "Minitab 版本：未取得",
              f"输入行数：{len(read_input()) if INPUT.is_file() else 0}。",
              "实际 Session Command 和原始结果见 `doe_splitplot_minitab_raw.txt`。"]
    if reason:
        report.extend(["", "## 未完成原因", "", reason])
    report.extend(["", "## 证据文件", "",
                   "固定输入、两套 JSON、模型空间/误差层比较 CSV、Session Commands 与原始输出均保存在本目录。"])
    REPORT.write_text("\n".join(report) + "\n", encoding="utf-8")
    return counts, sources, maximum


def parent_main():
    if (not PROJECT_PYTHON.is_file()
            or Path(sys.executable).resolve() != PROJECT_PYTHON.resolve()):
        raise RuntimeError(f"请使用项目解释器运行: {PROJECT_PYTHON}")
    levels = " ".join("-1 1" for _ in FACTORS)
    design_command = (
        f"SPDESIGN {len(FACTORS)} {len(HARD)};\n"
        f"  PLOTS {2 ** len(HARD)} {2 ** (len(FACTORS) - len(HARD))};\n"
        "  WPREPLICATES 3;\n  RBLOCK;\n  RANDOMIZE 19;\n"
        f"  LEVELS {levels};\n  DESIGN.")
    terms = " ".join(("<BLOCK>", *(f"<{name}>" for name in FACTORS)))
    terms += " " + " ".join("*".join(subset)
                             for order in range(2, len(FACTORS) + 1)
                             for subset in combinations(FACTORS, order))
    COMMANDS.write_text(
        "# Native 2-factor split-plot: A hard, B easy, 3 blocks for WP/SP df 2/4\n"
        + design_command + "\n\n"
        + "# Split-plot analysis retains whole-plot and subplot error strata\n"
        + "SPFACTORIAL;\n  RESPONSE <Y>;\n  FACTOR "
        + " ".join(f"<{name}>" for name in FACTORS) + ";\n"
        + "  HTCHANGE " + " ".join(f"<{name}>" for name in sorted(HARD))
        + ";\n  WPID <derived whole-plot ID>;\n"
        + "  BLOCKS <block>;\n  TERMS " + terms + ";\n  INUNIT 0;\n"
        + f"  LEVELS {levels};\n"
        + "  TANOVA;\n  TCOEFFICIENTS;\n  TSUMMARY;\n"
        + "  FITS <Fit>;\n  RESIDUALS <Resid>;\n"
        + "  WRESIDUALS <WPResid>;\n  COEFFICIENTS <Coef>;\n  XMATRIX <M>.\n",
        encoding="utf-8")
    command = [str(PROJECT_PYTHON), "-X", "utf8", str(Path(__file__).resolve())]
    local = subprocess.run(command + ["--minijmp-worker"], capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=300)
    print(local.stdout.rstrip(), flush=True)
    if local.stderr.strip():
        print("MiniJMP worker stderr:\n" + local.stderr.rstrip(), flush=True)
    if local.returncode:
        write_csv(COMPARISON, [])
        write_report([], "BLOCKED", "MiniJMP Split-Plot worker 执行失败；详见控制台输出。")
        return 1
    process = subprocess.run(command + ["--com-worker"], capture_output=True,
                             text=True, encoding="utf-8", errors="replace", timeout=420)
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
        write_report([], "BLOCKED", reason + "实际命令/错误见 doe_splitplot_minitab_raw.txt。")
        print("Split-Plot stage BLOCKED: " + reason, flush=True)
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
    expected_na = {("error_anova", "total", "ms")}
    unexpected_na = [row for row in comparisons if row["status"] == "N/A"
                     and (row["section"], row["term"], row["statistic"]) not in expected_na]
    status = ("FAIL" if any(row["status"] == "FAIL" for row in comparisons)
              or unexpected_na else
              "PARTIAL" if any(row["status"] == "UNSUPPORTED" for row in comparisons)
              else "PASS")
    reason = ("发现未预期的 N/A 比较：" + "; ".join(
        f"{row['section']}/{row['term']}/{row['statistic']}" for row in unexpected_na)
        if unexpected_na else "")
    counts, _, maximum = write_report(comparisons, status, reason)
    print(f"Split-Plot stage {status}: {counts}; max abs error="
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
