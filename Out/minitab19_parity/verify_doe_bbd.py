"""MiniJMP × Minitab 19 three-factor Box-Behnken parity check."""
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
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
MTB_EXE = Path(r"D:\Program\Minitab 19\Mtb.exe")
PROJECT_PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
INPUT = OUT / "doe_bbd_input.csv"
COMMANDS = OUT / "doe_bbd_session_commands.txt"
RAW = OUT / "doe_bbd_minitab_raw.txt"
MINIJMP = OUT / "doe_bbd_minijmp.json"
MINITAB = OUT / "doe_bbd_minitab.json"
COMPARISON = OUT / "doe_bbd_comparison.csv"
REPORT = OUT / "doe_bbd_acceptance_report.md"
TOL = 1e-9
TERMS = ("截距", "A", "B", "C", "A²", "B²", "C²", "A*B", "A*C", "B*C")
PREDICTIONS = ((0.0, 0.0, 0.0), (0.5, -0.25, 0.4), (-1.0, 0.0, 1.0))
CENTER_OFFSETS = (-0.2, 0.0, 0.2)

from verify_doe_ccd import (canonical, capture_command_output, compare_values,
                            running_minitab_pids, write_csv)


def point_key(a, b, c):
    return tuple(round(float(value), 12) for value in (a, b, c))


def independent_row(a, b, c):
    return [1.0, a, b, c, a*a, b*b, c*c, a*b, a*c, b*c]


def response_value(a, b, c, center_occurrence=0):
    value = (80 + 4*a - 3*b + 2*c + 1.5*a*b - .75*a*c + 2.25*b*c
             + 1.2*a*a - .8*b*b + .6*c*c + .025*a*a*b)
    if center_occurrence:
        value += CENTER_OFFSETS[center_occurrence - 1]
    return float(value)


def write_input(rows):
    fields = ("run_id", "standard_order", "run_order", "replicate", "point_type",
              "center_occurrence", "A", "B", "C", "Y")
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
                         "center_occurrence": int(row["center_occurrence"]),
                         **{name: float(row[name]) for name in "ABC"},
                         "Y": float(row["Y"])})
    if (len(rows) != 15
            or [row["standard_order"] for row in sorted(rows, key=lambda x: x["standard_order"])]
            != list(range(1, 16))
            or Counter(row["point_type"] for row in rows) != {"edge": 12, "center": 3}):
        raise ValueError("BBD 固定输入必须是 12 个边点和 3 个中心点")
    centers = [row for row in rows if row["point_type"] == "center"]
    if {row["center_occurrence"] for row in centers} != {1, 2, 3}:
        raise ValueError("三个中心点必须按标准序拥有唯一重复映射")
    if any((row["point_type"] == "center") != (point_key(row["A"], row["B"], row["C"]) == (0, 0, 0))
           for row in rows):
        raise ValueError("BBD 点类型与因子编码不一致")
    if len({(point_key(row["A"], row["B"], row["C"]), row["center_occurrence"])
            for row in rows}) != 15:
        raise ValueError("BBD 设计点与响应映射不唯一")
    if any(not math.isfinite(row["Y"]) or row["Y"] <= 0 for row in rows):
        raise ValueError("BBD 响应必须是有限正数")
    return rows


def run_minijmp_worker():
    if (not PROJECT_PYTHON.is_file()
            or Path(sys.executable).resolve() != PROJECT_PYTHON.resolve()):
        raise RuntimeError(f"请使用项目解释器运行: {PROJECT_PYTHON}")
    sys.path.insert(0, str(ROOT / "code"))
    import numpy as np
    import pandas as pd
    from doe_bbd import create_bbd
    from doe_core import DesignSpec, FactorSpec
    from doe_predict import predict_point
    from doe_rsm import analyze_rsm

    spec = DesignSpec("minitab19-bbd-parity",
                      tuple(FactorSpec(name, name, -1, 1) for name in "ABC"),
                      ("Y",), seed=19, design_type="box_behnken",
                      ccd_center_points=3)
    frame, metadata = create_bbd(spec)
    center_orders = sorted(int(value) for value in frame.loc[
        frame["点类型"] == "center", "标准序"])
    center_occurrence = {order: index + 1 for index, order in enumerate(center_orders)}
    rows = []
    for _, row in frame.iterrows():
        settings = {name: float(row[f"编码_{name}"]) for name in "ABC"}
        occurrence = center_occurrence.get(int(row["标准序"]), 0)
        rows.append({"run_id": str(row["运行ID"]),
                     "standard_order": int(row["标准序"]),
                     "run_order": int(row["运行序"]), "replicate": int(row["重复"]),
                     "point_type": str(row["点类型"]),
                     "center_occurrence": occurrence, **settings,
                     "Y": response_value(*settings.values(), occurrence)})
    write_input(rows)
    rows = read_input()
    frame.loc[:, "响应_Y"] = pd.array([row["Y"] for row in rows], dtype="Float64")
    analysis = analyze_rsm(frame, metadata, "Y", use_blocks=False)
    matrix_ref = np.asarray([independent_row(row["A"], row["B"], row["C"])
                             for row in rows], dtype=float)
    beta_ref, _, rank_ref, _ = np.linalg.lstsq(matrix_ref,
                                               np.asarray([row["Y"] for row in rows]), rcond=None)
    np.testing.assert_allclose(analysis["matrix"], matrix_ref, rtol=0, atol=1e-12)
    np.testing.assert_allclose(analysis["coefficients"], beta_ref, rtol=0, atol=1e-10)
    if (len(rows) != 15 or rank_ref != 10 or analysis["rank"] != 10
            or analysis["df"] != 5 or analysis["pure_error_df"] != 2
            or not math.isclose(analysis["pure_error_sse"], .08, rel_tol=0, abs_tol=1e-12)
            or analysis["lack_of_fit_df"] != 3
            or analysis["lack_of_fit_sse"] <= 1e-8 or analysis["inference"] is None):
        raise AssertionError("BBD 固定输入的 full-quadratic / pure-error / lack-of-fit 自检失败")

    matrix = np.asarray(analysis["matrix"], dtype=float)
    fit_rows = []
    for index, row in enumerate(rows):
        fit_rows.append({**row, "fit": float(analysis["fitted"][index]),
                         "residual": float(analysis["residuals"][index]),
                         "matrix": [float(value) for value in matrix[index]]})
    predictions = []
    for point in PREDICTIONS:
        settings = dict(zip("ABC", point))
        result = predict_point(frame, metadata, "Y", settings, blocks=False,
                               confidence=.95)
        interval = result["intervals"]
        if interval["status"] != "可用":
            raise AssertionError(f"BBD 预测点 {point} 的 95% CI/PI 不可用")
        predictions.append({"A": point[0], "B": point[1], "C": point[2],
                            "fit": float(result["prediction"]),
                            **{key: float(interval[key]) for key in
                               ("se_fit", "ci_low", "ci_high", "pi_low", "pi_high")}})
    inference = analysis["inference"]
    result = {
        "terms": list(analysis["names"]), "rank": int(analysis["rank"]),
        "n": int(analysis["n"]), "p": int(analysis["p"]),
        "df": int(analysis["df"]), "model_df": int(analysis["p"] - 1),
        "total_df": int(analysis["n"] - 1),
        "analysis_matrix": [[float(value) for value in row] for row in analysis["matrix"]],
        "response": [float(row["Y"]) for row in rows],
        "coefficients": {term: float(value)
                         for term, value in zip(analysis["names"], analysis["coefficients"])},
        "fits": fit_rows,
        "summary": {"rank": int(analysis["rank"]),
                    "model_df": int(analysis["p"] - 1),
                    "error_df": int(analysis["df"]),
                    "total_df": int(analysis["n"] - 1),
                    "sse": float(analysis["sse"]), "sst": float(analysis["sst"]),
                    "ssr": float(analysis["ssr"]), "mse": float(inference["mse"]),
                    "s": math.sqrt(float(inference["mse"])),
                    "r2": float(analysis["r2"]),
                    "adjusted_r2": float(analysis["adjusted_r2"]),
                    "model_f": float(inference["f"]),
                    "model_p": float(inference["model_p"]),
                    "pure_error_df": float(analysis["pure_error_df"]),
                    "pure_error_sse": float(analysis["pure_error_sse"]),
                    "lack_of_fit_df": float(analysis["lack_of_fit_df"]),
                    "lack_of_fit_sse": float(analysis["lack_of_fit_sse"]),
                    "lack_of_fit_f": _number(analysis["lack_of_fit"]["f"]),
                    "lack_of_fit_p": _number(analysis["lack_of_fit"]["p"])},
        "anova": [{"term": item["source"], "ss": float(item["ss"]),
                   "df": float(item["df"]), "f": _number(item["f"]),
                   "p": _number(item["p"])} for item in analysis["anova"]],
        "predictions": predictions,
    }
    MINIJMP.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("MiniJMP BBD self-check: 15 runs, full-quadratic rank 10, error df=5, "
          "pure-error df=2/SSE=.08, nonzero lack-of-fit, three 95% CI/PI PASS", flush=True)


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
        raise RuntimeError(f"Minitab BBD 缺少列 {tuple(wanted)}；实际列={names}")
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
        design_command = "BBDESIGN 3;\n  CENTER 3;\n  DESIGN."
        _execute(project, app, design_command, raw, "BBDESIGN")
        worksheet = project.ActiveWorksheet
        columns = worksheet.Columns
        names = [str(columns.Item(index).Name) for index in range(1, int(columns.Count) + 1)]
        factor_columns = {name: _find_column(names, (name,)) for name in "ABC"}
        std_column = _find_column(names, ("StdOrder", "StandardOrder", "标准序"), False)
        run_column = _find_column(names, ("RunOrder", "运行序"), False)
        type_column = _find_column(names, ("PtType", "PointType", "点类型"), False)
        raw_columns = {index: _column_values(columns.Item(index))
                       for index in set(factor_columns.values()) | {c for c in
                           (std_column, run_column, type_column) if c is not None}}
        if len(raw_columns[factor_columns["A"]]) != 15:
            raise RuntimeError(f"BBDESIGN 应生成 15 行，实际 {len(raw_columns[factor_columns['A']])}")
        input_lookup = {(point_key(row["A"], row["B"], row["C"]), row["center_occurrence"]): row
                        for row in rows}
        occurrences = Counter()
        native_rows = []
        for index in range(15):
            setting = {name: raw_columns[factor_columns[name]][index] for name in "ABC"}
            key = point_key(setting["A"], setting["B"], setting["C"])
            center_occurrence = 0
            if key == (0, 0, 0):
                occurrences[key] += 1
                center_occurrence = occurrences[key]
            source = input_lookup.get((key, center_occurrence))
            if source is None:
                raise RuntimeError(f"Minitab BBD 点/中心序号无法映射固定输入: {key}, {center_occurrence}")
            native_rows.append({
                "standard_order": (int(raw_columns[std_column][index])
                                   if std_column else index + 1),
                "run_order": (int(raw_columns[run_column][index])
                              if run_column else index + 1),
                "point_type": (str(raw_columns[type_column][index]) if type_column else ""),
                "center_occurrence": center_occurrence,
                **setting, "Y": source["Y"],
            })
        if occurrences[(0, 0, 0)] != 3:
            raise RuntimeError("Minitab BBD 中心点数不是 3")
        if any(min(row[name] for name in "ABC") < -1 or max(row[name] for name in "ABC") > 1
               for row in native_rows):
            raise RuntimeError("Minitab BBD 因子水平超出编码范围")
        raw.append("===== BBDESIGN native columns =====\n" + repr(names)
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
        factor_terms = [f"C{factor_columns[name]}" for name in "ABC"]
        squares = [f"C{factor_columns[name]}*C{factor_columns[name]}" for name in "ABC"]
        interactions = [f"C{factor_columns[first]}*C{factor_columns[second]}"
                        for first, second in (("A", "B"), ("A", "C"), ("B", "C"))]
        analysis_command = (
            "RSREG;\n"
            + f"  RESPONSE C{response_column};\n"
            + "  FACTORS " + " ".join(factor_terms) + ";\n"
            + "  TERMS " + " ".join([*factor_terms, *squares, *interactions]) + ";\n"
            + "  LEVELS -1 1 -1 1 -1 1;\n  INUNIT 0;\n  CONFIDENCE 95;\n"
            + f"  FITS C{output_columns['Fit']};\n"
            + f"  RESIDUALS C{output_columns['Resid']};\n"
            + f"  COEFFICIENTS C{output_columns['Coef']};\n"
            + f"  XMATRIX {matrix_name}."
        )
        _execute(project, app, analysis_command, raw, "RSREG")
        matrix_index = next((i for i in range(1, int(worksheet.Matrices.Count) + 1)
                             if str(worksheet.Matrices.Item(i).Name).casefold()
                             == matrix_name.casefold()), None)
        if matrix_index is None:
            raise RuntimeError(f"RSREG 未存储矩阵 {matrix_name}")
        matrix = worksheet.Matrices.Item(matrix_index)
        n, p = int(matrix.RowCount), int(matrix.ColumnCount)
        if (n, p) != (15, 10):
            raise RuntimeError(f"BBD RSREG XMATRIX 应为 15×10，实际 {n}×{p}")
        flat = [float(value) for value in matrix.GetData()]
        model_matrix = [[flat[column * n + row] for column in range(p)] for row in range(n)]
        expected = {term: [independent_row(row["A"], row["B"], row["C"])[index]
                           for row in native_rows]
                    for index, term in enumerate(TERMS)}
        term_columns = {}
        for column in range(p):
            actual = [model_matrix[row][column] for row in range(n)]
            matches = [term for term, vector in expected.items()
                       if np.allclose(actual, vector, rtol=0, atol=1e-12)]
            if len(matches) != 1 or matches[0] in term_columns:
                raise RuntimeError(f"Minitab RSREG XMATRIX 列映射不唯一: {column}, {matches}")
            term_columns[matches[0]] = column
        if set(term_columns) != set(TERMS):
            raise RuntimeError(f"Minitab BBD 模型项映射不完整: {term_columns}")
        coefficients_raw = _column_values(columns.Item(output_columns["Coef"]))[:p]
        coefficients = {term: coefficients_raw[index]
                        for term, index in term_columns.items()}
        fits = _column_values(columns.Item(output_columns["Fit"]))[:n]
        residuals = _column_values(columns.Item(output_columns["Resid"]))[:n]

        prediction_columns = {name: add_column(name) for name in (
            "PredFit", "PredSE", "CILow", "CIHigh", "PILow", "PIHigh")}
        prediction_command = (
            f"PREDICT C{response_column};\n"
            + "  KPREDICTORS 0 0 0;\n"
            + "  KPREDICTORS 0.5 -0.25 0.4;\n"
            + "  KPREDICTORS -1 0 1;\n  CONFIDENCE 95;\n"
            + f"  PFITS C{prediction_columns['PredFit']};\n"
            + f"  PSEFITS C{prediction_columns['PredSE']};\n"
            + f"  CLIMITS C{prediction_columns['CILow']} C{prediction_columns['CIHigh']};\n"
            + f"  PLIMITS C{prediction_columns['PILow']} C{prediction_columns['PIHigh']}."
        )
        _execute(project, app, prediction_command, raw, "PREDICT")
        predictions_data = {name: _column_values(columns.Item(index))[:3]
                            for name, index in prediction_columns.items()}
        predictions = [{"A": point[0], "B": point[1], "C": point[2],
                        "fit": predictions_data["PredFit"][i],
                        "se_fit": predictions_data["PredSE"][i],
                        "ci_low": predictions_data["CILow"][i],
                        "ci_high": predictions_data["CIHigh"][i],
                        "pi_low": predictions_data["PILow"][i],
                        "pi_high": predictions_data["PIHigh"][i]}
                       for i, point in enumerate(PREDICTIONS)]
        mtb_result = {
            "version": version, "app_path": app_path, "process_path": process_path,
            "design_command": design_command, "analysis_command": analysis_command,
            "prediction_command": prediction_command, "design_columns": names,
            "matrix_name": matrix_name, "design_rows": native_rows,
            "term_columns": term_columns, "coefficients": coefficients,
            "model_matrix": model_matrix, "rank": int(np.linalg.matrix_rank(model_matrix)),
            "fits": fits, "residuals": residuals, "predictions": predictions,
        }
        MINITAB.write_text(json.dumps(mtb_result, ensure_ascii=False, indent=2), encoding="utf-8")
        RAW.write_text("\n\n".join(raw) + "\n", encoding="utf-8")
        print(f"Minitab {version}: BBDESIGN + RSREG + PREDICT; matrix={n}×{p}, "
              f"rank={mtb_result['rank']}; native intervals stored", flush=True)
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
    fitted = np.asarray(mtb["fits"], dtype=float)
    residuals = np.asarray(mtb["residuals"], dtype=float)
    n, p = x.shape
    rank = int(np.linalg.matrix_rank(x))
    if (n, p, rank) != (15, 10, 10) or len(fitted) != n or len(residuals) != n:
        raise ValueError("Minitab BBD 高精度输出的维度/秩无效")
    np.testing.assert_allclose(y - fitted, residuals, rtol=0, atol=2e-9)
    sse = float(residuals @ residuals)
    sst = float(np.sum((y - y.mean())**2))
    model_df, error_df, total_df = rank - 1, n - rank, n - 1
    ssr = max(0.0, sst - sse)
    mse = sse / error_df
    model_f = (ssr / model_df) / mse
    cells = defaultdict(list)
    for row in rows:
        cells[point_key(row["A"], row["B"], row["C"])].append(row["Y"])
    pure_df = sum(len(cell) - 1 for cell in cells.values())
    pure_sse = sum(float(np.sum((np.asarray(cell) - np.mean(cell))**2))
                   for cell in cells.values())
    lof_df = error_df - pure_df
    lof_sse = max(0.0, sse - pure_sse)
    lof_f = ((lof_sse / lof_df) / (pure_sse / pure_df)) if lof_df > 0 else None
    result = {
        "rank": rank, "n": n, "p": p, "model_df": model_df,
        "error_df": error_df, "total_df": total_df, "sse": sse,
        "sst": sst, "ssr": ssr, "mse": mse, "s": math.sqrt(mse),
        "r2": 1 - sse / sst,
        "adjusted_r2": 1 - (sse / error_df) / (sst / total_df),
        "model_f": model_f,
        "model_p": float(stats.f.sf(model_f, model_df, error_df)),
        "pure_error_df": pure_df, "pure_error_sse": pure_sse,
        "lack_of_fit_df": lof_df, "lack_of_fit_sse": lof_sse,
        "lack_of_fit_f": lof_f,
        "lack_of_fit_p": (float(stats.f.sf(lof_f, lof_df, pure_df))
                           if lof_f is not None else None),
        "term_anova": {}, "group_anova": {},
    }
    groups = {"Linear": ("A", "B", "C"),
              "Square": ("A²", "B²", "C²"),
              "2-Way Interaction": ("A*B", "A*C", "B*C")}
    for term in TERMS[1:]:
        column = mtb["term_columns"][term]
        reduced = np.delete(x, column, axis=1)
        beta = np.linalg.lstsq(reduced, y, rcond=None)[0]
        reduced_sse = float(np.sum((y - reduced @ beta)**2))
        ss = max(0.0, reduced_sse - sse)
        f_value = ss / mse
        result["term_anova"][term] = {
            "ss": ss, "df": 1, "f": f_value,
            "p": float(stats.f.sf(f_value, 1, error_df)),
        }
    for name, terms in groups.items():
        columns = [mtb["term_columns"][term] for term in terms]
        reduced = np.delete(x, columns, axis=1)
        beta = np.linalg.lstsq(reduced, y, rcond=None)[0]
        reduced_sse = float(np.sum((y - reduced @ beta)**2))
        ss = max(0.0, reduced_sse - sse)
        df = len(columns)
        f_value = (ss / df) / mse
        result["group_anova"][name] = {
            "ss": ss, "df": df, "ms": ss / df, "f": f_value,
            "p": float(stats.f.sf(f_value, df, error_df)),
        }
    inverse = np.linalg.inv(x.T @ x)
    critical = float(stats.t.ppf(.975, error_df))
    beta = np.asarray([mtb["coefficients"][term] for term in TERMS])
    result["predictions"] = []
    for point in PREDICTIONS:
        a, b, c = point
        x0 = np.asarray(independent_row(a, b, c), dtype=float)
        fit = float(x0 @ beta)
        h0 = float(x0 @ inverse @ x0)
        se_fit = math.sqrt(mse * h0)
        se_prediction = math.sqrt(mse * (1 + h0))
        result["predictions"].append({
            "A": a, "B": b, "C": c, "fit": fit, "se_fit": se_fit,
            "ci_low": fit - critical * se_fit, "ci_high": fit + critical * se_fit,
            "pi_low": fit - critical * se_prediction,
            "pi_high": fit + critical * se_prediction,
        })
    return result


def compare_case(minijmp, mtb):
    comparisons = []
    direct_design = "Minitab 19 BBDESIGN worksheet values (DIRECT)"
    direct_matrix = "Minitab 19 RSREG XMATRIX (DIRECT)"
    direct_model = "Minitab 19 RSREG COEFFICIENTS/FITS/RESIDUALS (DIRECT)"
    derived = ("DERIVED: Minitab RSREG XMATRIX, COEFFICIENTS, FITS/RESIDUALS, "
               "fixed response and scipy.stats")
    local_source = "MiniJMP analyze_rsm"
    local_by_key = {(point_key(row["A"], row["B"], row["C"]), row["center_occurrence"]): row
                    for row in minijmp["fits"]}
    mtb_by_key = {(point_key(row["A"], row["B"], row["C"]), row["center_occurrence"]): index
                  for index, row in enumerate(mtb["design_rows"])}
    if set(local_by_key) != set(mtb_by_key):
        raise ValueError("MiniJMP/Minitab BBD 设计点和中心点顺序无法一一映射")
    for key in sorted(local_by_key):
        local, index = local_by_key[key], mtb_by_key[key]
        native = mtb["design_rows"][index]
        label = f"{key[0]} / center occurrence {key[1]}"
        for name in "ABC":
            comparisons.append(compare_values(1, "design", label, name, native[name],
                                              local[name], direct_design,
                                              "MiniJMP create_bbd coded design (DIRECT)"))
        comparisons.append(compare_values(1, "design", label, "Y", native["Y"], local["Y"],
                                          "Fixed input CSV (shared DIRECT)",
                                          "Fixed input CSV (shared DIRECT)"))
        for term, column in mtb["term_columns"].items():
            local_column = minijmp["terms"].index(term)
            comparisons.append(compare_values(
                1, "model_matrix", label, term,
                mtb["model_matrix"][index][column], local["matrix"][local_column],
                direct_matrix, "MiniJMP TermModel matrix (DIRECT)"))
        comparisons.append(compare_values(1, "fit", label, "fitted", mtb["fits"][index],
                                          local["fit"], direct_model, local_source))
        comparisons.append(compare_values(1, "fit", label, "residual", mtb["residuals"][index],
                                          local["residual"], direct_model, local_source))

    for term in TERMS:
        comparisons.append(compare_values(1, "coefficient", term, "estimate",
                                          mtb["coefficients"][term],
                                          minijmp["coefficients"][term], direct_model,
                                          local_source))
    stats = derive_minitab_stats(mtb)
    local_summary = minijmp["summary"]
    for metric in ("rank", "model_df", "error_df", "total_df", "sse", "sst", "ssr",
                   "mse", "s", "r2", "adjusted_r2", "model_f", "model_p",
                   "pure_error_df", "pure_error_sse", "lack_of_fit_df",
                   "lack_of_fit_sse", "lack_of_fit_f", "lack_of_fit_p"):
        comparisons.append(compare_values(1, "model_summary", "model", metric,
                                          stats[metric], local_summary[metric],
                                          derived, local_source))
    local_anova = {item["term"]: item for item in minijmp["anova"]}
    for term in TERMS[1:]:
        for metric in ("ss", "df", "f", "p"):
            comparisons.append(compare_values(1, "term_anova", term, metric,
                                              stats["term_anova"][term][metric],
                                              local_anova[term][metric], derived, local_source))
    local_groups = {}
    for name, terms in {"Linear": ("A", "B", "C"),
                        "Square": ("A²", "B²", "C²"),
                        "2-Way Interaction": ("A*B", "A*C", "B*C")}.items():
        local_groups[name] = _group_from_local(minijmp, terms)
    for name in local_groups:
        for metric in ("ss", "df", "ms", "f", "p"):
            comparisons.append(compare_values(1, "effect_group_anova", name, metric,
                                              stats["group_anova"][name][metric],
                                              local_groups[name][metric], derived, local_source))
    for index, prediction in enumerate(mtb["predictions"]):
        local = minijmp["predictions"][index]
        for metric in ("fit", "se_fit", "ci_low", "ci_high", "pi_low", "pi_high"):
            comparisons.append(compare_values(
                1, "prediction", f"P{index + 1}", metric, prediction[metric], local[metric],
                "Minitab 19 RSREG PREDICT storage (DIRECT)",
                "MiniJMP predict_point(confidence=.95)"))
            comparisons.append(compare_values(
                1, "prediction_derived", f"P{index + 1}", metric,
                stats["predictions"][index][metric], local[metric],
                derived + " and coded-point t interval", local_source))
    return comparisons, stats


def _group_from_local(local, terms):
    import numpy as np
    from scipy import stats

    analysis = local["analysis_matrix"]
    x = np.asarray(analysis, dtype=float)
    y = np.asarray(local["response"], dtype=float)
    sse = local["summary"]["sse"]
    mse = local["summary"]["mse"]
    df_error = local["summary"]["error_df"]
    indices = [local["terms"].index(term) for term in terms]
    reduced = np.delete(x, indices, axis=1)
    beta = np.linalg.lstsq(reduced, y, rcond=None)[0]
    reduced_sse = float(np.sum((y - reduced @ beta)**2))
    ss = max(0.0, reduced_sse - sse)
    df = len(indices)
    f_value = (ss / df) / mse
    return {"ss": ss, "df": df, "ms": ss / df, "f": f_value,
            "p": float(stats.f.sf(f_value, df, df_error))}


def _write_report(comparisons, status, reason=""):
    counts = {name: sum(row["status"] == name for row in comparisons)
              for name in ("PASS", "FAIL", "N/A", "UNSUPPORTED")}
    sources = {name: sum(name in row["minitab_value_source"] for row in comparisons)
               for name in ("DIRECT", "DERIVED", "DISPLAY")}
    measured = [row for row in comparisons if row["absolute_error"] is not None]
    maximum = max(measured, key=lambda row: row["absolute_error"], default=None)
    report = ["# MiniJMP × Minitab 19 三因子 Box–Behnken 对标", "",
              f"**阶段状态：{status}**", "",
              f"比较计数：PASS {counts['PASS']} / FAIL {counts['FAIL']} / "
              f"N/A {counts['N/A']} / UNSUPPORTED {counts['UNSUPPORTED']}。",
              f"来源分类（Minitab 侧）：DIRECT {sources['DIRECT']} / "
              f"DERIVED {sources['DERIVED']} / DISPLAY {sources['DISPLAY']}。",
              (f"最大绝对误差：{maximum['absolute_error']:.10g}，"
               f"{maximum['section']} / {maximum['term']} / {maximum['statistic']}。"
               if maximum else "最大绝对误差：无可比较数值项。"), "",
              "## 方法与范围", "",
              "- 固定设计为 3 个连续两水平因子、12 个 BBD 边点和 3 个中心点，共 15 次运行；无区组。响应含完整二次项、固定三阶偏差与三个中心观测偏差。",
              "- Minitab 19 原生 `BBDESIGN 3` 与 `RSREG` 执行完整二次模型；按实际编码行映射 Minitab 与 MiniJMP 设计，XMATRIX 的十列按数值映射至截距、线性、平方和交互项。",
              "- DIRECT 包含设计、XMATRIX、系数、拟合/残差和三点 PREDICT/SE Fit/95% CI/PI；DERIVED 由 Minitab 高精度输出和固定输入重建 ANOVA、线性/平方/二因子交互效应组、纯误差与失拟。",
              "- 预测点为中心点、内部非设计点 (0.5, -0.25, 0.4) 和边点 (-1, 0, 1)；区间置信水平 95%。", "",
              "## 执行结果", "",
              f"Minitab 版本：{json.loads(MINITAB.read_text(encoding='utf-8'))['version']}" if MINITAB.is_file() else "Minitab 版本：未取得",
              f"输入行数：{len(read_input()) if INPUT.is_file() else 0}。",
              "原始 Session Command 输出见 `doe_bbd_minitab_raw.txt`。"]
    if reason:
        report.extend(["", "## 未完成原因", "", reason])
    report.extend(["", "## 证据文件", "",
                   "固定输入、Session Commands、Minitab 原始输出、两侧 JSON、数值比较 CSV 与本报告均保存在本目录。"])
    REPORT.write_text("\n".join(report) + "\n", encoding="utf-8")
    return counts, sources, maximum


def parent_main():
    if (not PROJECT_PYTHON.is_file()
            or Path(sys.executable).resolve() != PROJECT_PYTHON.resolve()):
        raise RuntimeError(f"请使用项目解释器运行: {PROJECT_PYTHON}")
    design_command = "BBDESIGN 3;\n  CENTER 3;\n  DESIGN."
    COMMANDS.write_text(
        "# Native 3-factor BBD, 12 edge points and 3 centers\n" + design_command + "\n\n"
        + "# Full quadratic coded response surface, independent of row order\n"
        + "RSREG;\n  RESPONSE <Y>;\n  FACTORS <A> <B> <C>;\n"
        + "  TERMS <A> <B> <C> <A>*<A> <B>*<B> <C>*<C> <A>*<B> <A>*<C> <B>*<C>;\n"
        + "  LEVELS -1 1 -1 1 -1 1;\n  INUNIT 0;\n  CONFIDENCE 95;\n"
        + "  FITS <Fit>;\n  RESIDUALS <Resid>;\n  COEFFICIENTS <Coef>;\n  XMATRIX <M>.\n\n"
        + "# Native prediction at 3 points with SE Fit and 95% intervals\n"
        + "PREDICT <Y>;\n  KPREDICTORS 0 0 0;\n  KPREDICTORS 0.5 -0.25 0.4;\n"
        + "  KPREDICTORS -1 0 1;\n  CONFIDENCE 95;\n  PFITS <PredFit>;\n"
        + "  PSEFITS <PredSE>;\n  CLIMITS <CILow> <CIHigh>;\n"
        + "  PLIMITS <PILow> <PIHigh>.\n", encoding="utf-8")
    command = [str(PROJECT_PYTHON), "-X", "utf8", str(Path(__file__).resolve())]
    local = subprocess.run(command + ["--minijmp-worker"], capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=240)
    print(local.stdout.rstrip(), flush=True)
    if local.stderr.strip():
        print("MiniJMP worker stderr:\n" + local.stderr.rstrip(), flush=True)
    if local.returncode:
        write_csv(COMPARISON, [])
        _write_report([], "BLOCKED", "MiniJMP BBD/RSM worker 执行失败；详见控制台输出。")
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
        _write_report([], "BLOCKED", reason + "原始命令/错误见 doe_bbd_minitab_raw.txt。")
        print("BBD stage BLOCKED: " + reason, flush=True)
        return 1
    local_result = json.loads(MINIJMP.read_text(encoding="utf-8"))
    native = json.loads(MINITAB.read_text(encoding="utf-8"))
    if (native["version"] != "19.1.0.1" or canonical(native["app_path"]) != canonical(MTB_EXE)
            or canonical(native["process_path"]) != canonical(MTB_EXE)):
        write_csv(COMPARISON, [])
        _write_report([], "BLOCKED", "Minitab 19.1.0.1 COM 程序路径或版本不符。")
        return 1
    comparisons, _ = compare_case(local_result, native)
    write_csv(COMPARISON, comparisons)
    status = ("FAIL" if any(row["status"] == "FAIL" for row in comparisons)
              else "PARTIAL" if any(row["status"] == "UNSUPPORTED" for row in comparisons)
              else "PASS")
    counts, _, maximum = _write_report(comparisons, status)
    print(f"BBD stage {status}: {counts}; max abs error="
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
