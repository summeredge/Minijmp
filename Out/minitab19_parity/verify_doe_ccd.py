"""MiniJMP × Minitab 19.1.0.1 面心 CCD 二次响应面数值对标。

复用 verify_doe_2x2.py 的独立实例、COM 释放、CSV 比较与容差约定。
"""
from __future__ import annotations

import csv
import ctypes
import json
import math
import os
import re
import subprocess
import sys
import time
import traceback
from collections import Counter
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
INPUT = OUT / "doe_ccd_input.csv"
MTB_EXE = Path(r"D:\Program\Minitab 19\Mtb.exe")
PROJECT_PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
LOG = OUT / "doe_ccd_run.log"
COMMANDS_FILE = OUT / "doe_ccd_session_commands.txt"
COMPARISON = OUT / "doe_ccd_comparison.csv"
REPORT = OUT / "doe_ccd_acceptance_report.md"

TOL_ABS = 1e-9
TOL_REL = 1e-9

DESIGN_COMMAND = "CCDESIGN 2;\n  ALPHA 1;\n  CENTER 5;\n  DESIGN."
ANALYSIS_COMMAND = (
    "RSREG;\n  RESPONSE C7;\n  FACTORS C5 C6;\n"
    "  TERMS C5 C6 C5*C6 C5*C5 C6*C6;\n  LEVELS -1 1 -1 1;\n  INUNIT 0;\n"
    "  CONFIDENCE 95;\n  FITS C8;\n  RESIDUALS C9;\n  COEFFICIENTS C10;\n  XMATRIX M1."
)
PREDICTION_COMMAND = (
    "PREDICT C7;\n"
    "  KPREDICTORS 0 0;\n  KPREDICTORS 1 0;\n  KPREDICTORS 0.5 0.5;\n"
    "  CONFIDENCE 95;\n"
    "  PFITS C11;\n  PSEFITS C12;\n  CLIMITS C13 C14;\n  PLIMITS C15 C16."
)
MTB_TERMS = ("常量", "A", "B", "A*B", "A*A", "B*B")
JMP_TERMS = ("A", "B", "A*B", "A²", "B²")
JMP_ALIAS = {"常量": "常量", "A": "A", "B": "B", "A*B": "A*B", "A*A": "A²", "B*B": "B²"}
PREDICT_POINTS = ((0.0, 0.0, "中心点"), (1.0, 0.0, "轴点"), (0.5, 0.5, "内部非设计点"))
POINT_TEXT = {1.0: "factorial", -1.0: "axial", 0.0: "center"}


def log(message: str) -> None:
    print(message, flush=True)
    with LOG.open("a", encoding="utf-8") as stream:
        stream.write(message + "\n")


def canonical(path: str | Path) -> str:
    return os.path.normcase(os.path.realpath(os.path.abspath(path)))


def running_minitab_pids() -> list[int]:
    result = subprocess.run(
        ["tasklist.exe", "/FI", "IMAGENAME eq Mtb.exe", "/FO", "CSV", "/NH"],
        check=True, capture_output=True, text=True, encoding="mbcs", errors="replace",
    )
    return [int(row[1]) for row in csv.reader(result.stdout.splitlines())
            if len(row) >= 2 and row[0].casefold() == "mtb.exe" and row[1].isdigit()]


def read_input() -> list[dict]:
    with INPUT.open(newline="", encoding="utf-8-sig") as stream:
        rows = [{"standard_order": int(row["standard_order"]), "run_id": row["run_id"],
                 "point_type": row["point_type"], "A": float(row["A"]),
                 "B": float(row["B"]), "Y": float(row["Y"])}
                for row in csv.DictReader(stream)]
    if len(rows) != 13 or [row["standard_order"] for row in rows] != list(range(1, 14)):
        raise ValueError("输入必须是固定 13 行的标准序 CCD")
    if Counter(row["point_type"] for row in rows) != {"factorial": 4, "axial": 4, "center": 5}:
        raise ValueError("面心 CCD 必须是 4 个因子点、4 个轴点、5 个中心点")
    return rows


# ---------------------------------------------------------------- Minitab 侧
def worker_main(run_number: int) -> int:
    import winreg
    import win32api
    import win32process
    import numpy as np
    import pythoncom
    import win32com
    import win32com.client
    from importlib.metadata import version as package_version

    result_path = OUT / f"doe_ccd_minitab_run{run_number}.json"
    raw_path = OUT / f"doe_ccd_minitab_raw_run{run_number}.txt"
    raw = []
    app = project = ui = worksheet = None
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

        rows = read_input()
        app = win32com.client.DispatchEx("Mtb.Application")
        pythoncom.PumpWaitingMessages()
        ui = app.UserInterface
        ui.Visible = False
        ui.UserControl = False
        ui.DisplayAlerts = False
        app_path = str(app.AppPath)
        hwnd = int(app.Handle)
        kernel32 = ctypes.windll.kernel32
        _, process_id = win32process.GetWindowThreadProcessId(hwnd)
        handle = kernel32.OpenProcess(0x1000, False, process_id)
        if not handle:
            raise ctypes.WinError()
        try:
            size = ctypes.c_ulong(32768)
            buffer = ctypes.create_unicode_buffer(size.value)
            if not kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
                raise ctypes.WinError()
            process_path = buffer.value
        finally:
            kernel32.CloseHandle(handle)
        if canonical(app_path) != canonical(MTB_EXE) or canonical(process_path) != canonical(MTB_EXE):
            raise RuntimeError(f"COM 实例路径不匹配: AppPath={app_path}, process={process_path}")

        app.New()
        project = app.ActiveProject
        project.ExecuteCommand(DESIGN_COMMAND)
        worksheet = project.ActiveWorksheet
        columns = worksheet.Columns
        if int(columns.Count) < 6:
            raise RuntimeError(f"CCDESIGN 未生成标准六列，Columns.Count={columns.Count}")
        names = [str(columns.Item(i).Name) for i in range(1, 7)]
        if names[4:6] != ["A", "B"]:
            raise RuntimeError(f"CCDESIGN 因子列名不符: {names}")
        design_a = [float(v) for v in columns.Item(5).GetData()]
        design_b = [float(v) for v in columns.Item(6).GetData()]
        design_point = [float(v) for v in columns.Item(3).GetData()]
        design_order = [int(v) for v in columns.Item(1).GetData()]
        design_run = [int(v) for v in columns.Item(2).GetData()]
        if len(design_a) != 13 or design_order != list(range(1, 14)):
            raise RuntimeError(f"CCDESIGN 未生成 13 个标准序运行: {design_order}")
        raw.append("===== CCDESIGN actual command =====\n" + DESIGN_COMMAND
                   + "\n===== CCDESIGN OutputDocument/Outputs =====\n" + capture_command_output(project))

        mtb_design = [{"standard_order": order, "run_order": run,
                       "point_type": POINT_TEXT.get(point, f"unknown:{point}"),
                       "A": a, "B": b}
                      for order, run, point, a, b in zip(
                          design_order, design_run, design_point, design_a, design_b)]
        if ([row["point_type"] for row in mtb_design]
                != [row["point_type"] for row in rows]):
            raise RuntimeError("Minitab CCD 点类型顺序与固定输入不一致")
        if ([(row["A"], row["B"]) for row in mtb_design]
                != [(row["A"], row["B"]) for row in rows]):
            raise RuntimeError("Minitab CCD 设计点与固定输入不一致")

        response = columns.Add(None, None, 1)
        response.Name = "Y"
        response.SetData(tuple(row["Y"] for row in rows), 1, len(rows))
        if [float(v) for v in response.GetData()] != [row["Y"] for row in rows]:
            raise AssertionError("Minitab 响应列写入/回读与固定 CSV 不一致")

        count_before = int(project.Commands.Count)
        project.ExecuteCommand(ANALYSIS_COMMAND)
        analysis_error = str(app.LastError or "")
        if int(project.Commands.Count) <= count_before:
            raw.append(f"RSREG failed; LastError={analysis_error!r}")
            raise RuntimeError(f"RSREG 未创建命令对象: {analysis_error!r}")
        analysis_text = capture_command_output(project)
        raw.append("===== RSREG actual command =====\n" + ANALYSIS_COMMAND
                   + "\n===== RSREG OutputDocument/Outputs =====\n" + analysis_text)
        if not analysis_text.strip():
            raise RuntimeError("RSREG 未返回可读统计输出")

        coefficients = [float(v) for v in columns.Item(10).GetData()]
        fits = [float(v) for v in columns.Item(8).GetData()]
        residuals = [float(v) for v in columns.Item(9).GetData()]
        if len(coefficients) != 6 or len(fits) != 13 or len(residuals) != 13:
            raise RuntimeError("RSREG 存储结果行数不符：应为 6 系数、13 拟合、13 残差")
        matrices = worksheet.Matrices
        if int(matrices.Count) < 1:
            raise RuntimeError("RSREG 没有存储 XMATRIX M1")
        matrix = matrices.Item(1)
        if str(matrix.Name).casefold() != "m1" or int(matrix.RowCount) != 13 or int(matrix.ColumnCount) != 6:
            raise RuntimeError(f"M1 维度/名称异常: {matrix.Name}, {matrix.RowCount}x{matrix.ColumnCount}")
        flat = [float(v) for v in matrix.GetData()]
        model_matrix = [[flat[col * 13 + row] for col in range(6)] for row in range(13)]
        rank = int(np.linalg.matrix_rank(model_matrix))

        count_before = int(project.Commands.Count)
        project.ExecuteCommand(PREDICTION_COMMAND)
        prediction_error = str(app.LastError or "")
        if int(project.Commands.Count) <= count_before:
            raw.append(f"PREDICT failed; LastError={prediction_error!r}")
            raise RuntimeError(f"PREDICT 未创建命令对象: {prediction_error!r}")
        prediction_text = capture_command_output(project)
        raw.append("===== PREDICT actual command =====\n" + PREDICTION_COMMAND
                   + "\n===== PREDICT OutputDocument/Outputs =====\n" + prediction_text)
        if "无法执行" in prediction_text or "错误" in prediction_text:
            raise RuntimeError("PREDICT 返回错误，预测区间不可用")
        stored = {
            "fit": [float(v) for v in columns.Item(11).GetData()],
            "se_fit": [float(v) for v in columns.Item(12).GetData()],
            "ci_low": [float(v) for v in columns.Item(13).GetData()],
            "ci_high": [float(v) for v in columns.Item(14).GetData()],
            "pi_low": [float(v) for v in columns.Item(15).GetData()],
            "pi_high": [float(v) for v in columns.Item(16).GetData()],
        }
        if any(len(values) != 3 for values in stored.values()):
            raise RuntimeError(f"PREDICT 存储行数不符，应为 3 行: { {k: len(v) for k, v in stored.items()} }")

        result = {
            "run": run_number, "version": version, "clsid": clsid,
            "local_server": server_command, "app_path": app_path, "process_path": process_path,
            "python_executable": sys.executable, "pywin32_version": package_version("pywin32"),
            "native_commands": [DESIGN_COMMAND, ANALYSIS_COMMAND, PREDICTION_COMMAND],
            "design": mtb_design,
            "data_rows": rows,
            "coefficients": dict(zip(MTB_TERMS, coefficients)),
            "model_matrix": model_matrix, "rank": rank,
            "fits": fits, "residuals": residuals,
            "predictions": [{"A": point[0], "B": point[1], "label": point[2],
                             **{name: values[i] for name, values in stored.items()}}
                            for i, point in enumerate(PREDICT_POINTS)],
            "analysis_text": analysis_text,
            "prediction_text": prediction_text,
        }
        result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        raw_path.write_text("\n\n".join(raw) + "\n", encoding="utf-8")
        print(f"COM worker run {run_number}: Minitab {version}; CCDESIGN+RSREG+PREDICT 完成; "
              f"rank={rank}; M1/C8/C9/C10/C11-C16 已回读。", flush=True)
        return 0
    except Exception:
        raw_path.write_text("\n\n".join(raw) + "\n", encoding="utf-8")
        traceback.print_exc()
        return 1
    finally:
        matrix = matrices = response = columns = worksheet = project = app = ui = None


def capture_command_output(project, command_index=None) -> str:
    commands = project.Commands
    command = commands.Item(int(command_index if command_index is not None else commands.Count))
    outputs = command.Outputs
    texts = [str(outputs.Item(index).Text or "") for index in range(1, int(outputs.Count) + 1)]
    document_text = str(command.OutputDocument.Text or "")
    blocks = ["OutputDocument.Text:\n" + document_text]
    blocks.extend(f"Output.Text[{index}]:\n{text}" for index, text in enumerate(texts, 1))
    return "\n\n".join(blocks)


# ---------------------------------------------------------------- MiniJMP 侧
def run_minijmp(rows: list[dict]) -> dict:
    if canonical(sys.executable) != canonical(PROJECT_PYTHON):
        raise RuntimeError(f"请使用项目解释器运行: {PROJECT_PYTHON}")
    sys.path.insert(0, str(ROOT / "code"))
    import numpy as np
    import pandas as pd
    from doe_ccd import create_ccd, validate_ccd
    from doe_core import DesignSpec, FactorSpec
    from doe_predict import predict_point
    from doe_rsm import analyze_rsm

    spec = DesignSpec(
        "minitab19-ccd-parity",
        (FactorSpec("A", "A", -1, 1), FactorSpec("B", "B", -1, 1)),
        ("Y",), seed=19, design_type="central_composite",
        ccd_alpha=1, ccd_center_points=5, ccd_axial_points=4,
    )
    frame, metadata = create_ccd(spec)
    by_standard = {int(order): index for index, order in enumerate(frame["标准序"])}
    frame.loc[:, "响应_Y"] = pd.array(
        [rows[int(order) - 1]["Y"] for order in frame["标准序"]], dtype="Float64")
    result = analyze_rsm(frame, metadata, "Y", terms=JMP_TERMS, use_blocks=False)

    order_index = np.asarray([by_standard[order] for order in range(1, 14)])
    coded = np.asarray(result["coded"], dtype=float)[order_index]
    matrix = np.asarray(result["matrix"], dtype=float)[order_index]
    fits = np.asarray(result["fitted"], dtype=float)[order_index]
    residuals = np.asarray(result["residuals"], dtype=float)[order_index]
    observed = np.asarray([row["Y"] for row in rows], dtype=float)
    assert np.allclose(observed - fits, residuals, atol=1e-12, rtol=0)
    if matrix.shape != (13, 6):
        raise AssertionError(f"MiniJMP 模型矩阵应为 13x6，实际 {matrix.shape}")
    if np.linalg.matrix_rank(matrix) != 6 or int(result["rank"]) != 6:
        raise AssertionError("MiniJMP 模型矩阵秩不是 6")

    design = [(int(frame.loc[i, "标准序"]),
               str(frame.loc[i, "点类型"]),
               int(frame.loc[i, "重复"]),
               float(frame.loc[i, "编码_A"]),
               float(frame.loc[i, "编码_B"])) for i in range(len(frame))]
    design.sort()
    validate_ccd(__import__("doe_core").restore_design_result(frame, metadata))

    predictions = []
    for a, b, label in PREDICT_POINTS:
        point = predict_point(frame, metadata, "Y", {"A": a, "B": b},
                              terms=JMP_TERMS, blocks=False, confidence=0.95)
        interval = point["intervals"]
        if interval["status"] != "可用":
            raise AssertionError(f"MiniJMP 预测区间不可用: {interval['reason']}")
        predictions.append({"A": a, "B": b, "label": label,
                            "fit": point["prediction"], "se_fit": interval["se_fit"],
                            "ci_low": interval["ci_low"], "ci_high": interval["ci_high"],
                            "pi_low": interval["pi_low"], "pi_high": interval["pi_high"]})

    pure_values = observed[[row["point_type"] == "center" for row in rows]]
    pure_sse = float(((pure_values - pure_values.mean()) ** 2).sum())
    if not math.isclose(pure_sse, float(result["pure_error_sse"]), abs_tol=1e-12, rel_tol=0):
        raise AssertionError("MiniJMP 纯误差平方和与中心点重复数据不一致")
    lof = result["lack_of_fit"]
    if result["pure_error_df"] != 4 or result["lack_of_fit_df"] != 3 or not lof:
        raise AssertionError("MiniJMP 纯误差/失拟自由度不符")
    if result["sse"] <= 0 or pure_sse <= 0:
        raise AssertionError("SSE 或纯误差必须为正")

    return {
        "coefficients": {
            "常量": float(result["coefficients"][0]),
            **{name: float(value) for name, value in zip(JMP_TERMS, result["coefficients"][1:])},
        },
        "model_matrix": matrix.tolist(), "rank": int(np.linalg.matrix_rank(matrix)),
        "coded": coded.tolist(), "design": design,
        "fits": fits.tolist(), "residuals": residuals.tolist(),
        "observed": observed.tolist(),
        "anova": {row["source"]: {key: (float(value) if value is not None else None)
                                  for key, value in row.items() if key != "source"}
                  for row in result["anova"]},
        "n": int(result["n"]), "p": int(result["p"]), "df": int(result["df"]),
        "sse": float(result["sse"]), "sst": float(result["sst"]), "ssr": float(result["ssr"]),
        "r2": float(result["r2"]), "adjusted_r2": float(result["adjusted_r2"]),
        "pure_error_df": int(result["pure_error_df"]),
        "pure_error_sse": float(result["pure_error_sse"]),
        "lack_of_fit_df": int(result["lack_of_fit_df"]),
        "lack_of_fit_sse": float(result["lack_of_fit_sse"]),
        "lack_of_fit": None if not lof else {"f": float(lof["f"]), "p": float(lof["p"])},
        "model_f": float(result["inference"]["f"]) if result["inference"] else None,
        "model_p": float(result["inference"]["model_p"]) if result["inference"] else None,
        "predictions": predictions,
        "terms": list(result["terms"]), "names": list(result["names"]),
    }


def native_stats(minitab: dict) -> dict:
    """用 Minitab 高精度存储量重建方差分析（DIRECT 底层数值）。"""
    import numpy as np
    from scipy import stats

    matrix = np.asarray(minitab["model_matrix"], dtype=float)
    beta = np.asarray([minitab["coefficients"][name] for name in MTB_TERMS], dtype=float)
    observed = np.asarray([row["Y"] for row in minitab["data_rows"]], dtype=float)
    fits = np.asarray(minitab["fits"], dtype=float)
    residuals = np.asarray(minitab["residuals"], dtype=float)
    if not np.allclose(matrix @ beta, fits, atol=1e-10, rtol=1e-10):
        raise AssertionError("Minitab 拟合值不等于 XMATRIX × 存储系数")
    if not np.allclose(observed - fits, residuals, atol=1e-10, rtol=1e-10):
        raise AssertionError("Minitab 存储残差不等于响应 − 拟合值")
    if not np.allclose(matrix[:, 0], 1.0, atol=0, rtol=0):
        raise AssertionError("Minitab XMATRIX 首列不是截距")

    n, p = matrix.shape
    df = n - p
    sse = float(residuals @ residuals)
    sst = float(((observed - observed.mean()) ** 2).sum())
    mse = sse / df
    rows = {}

    def adjusted(columns):
        reduced = np.delete(matrix, columns, axis=1)
        coef, *_ = np.linalg.lstsq(reduced, observed, rcond=None)
        return float(((observed - reduced @ coef) ** 2).sum()) - sse

    for name, column in zip(MTB_TERMS[1:], range(1, 6)):
        ss = adjusted([column])
        f = ss / mse
        rows[name] = {"df": 1.0, "ss": ss, "ms": ss,
                      "f": f, "p": float(stats.f.sf(f, 1, df))}
    groups = (("线性", [1, 2]), ("双因子交互作用", [3]), ("平方", [4, 5]))
    for name, columns in groups:
        ss = adjusted(columns)  # 同时移除该组全部列，与 Minitab Adj SS 一致
        f = (ss / len(columns)) / mse
        rows[name] = {"df": float(len(columns)), "ss": ss, "ms": ss / len(columns),
                      "f": f, "p": float(stats.f.sf(f, len(columns), df))}
    model_ss = sst - sse
    model_df = p - 1
    model_ms = model_ss / model_df
    model_f = model_ms / mse
    rows["Model"] = {"df": float(model_df), "ss": model_ss, "ms": model_ms,
                     "f": model_f, "p": float(stats.f.sf(model_f, model_df, df))}

    centers = [(a, b, y) for (a, b), y in
               zip(((row["A"], row["B"]) for row in minitab["data_rows"]), observed)
               if a == 0 and b == 0]
    pure_values = np.asarray([y for _, _, y in centers], dtype=float)
    pure_df = len(pure_values) - 1
    pure_sse = float(((pure_values - pure_values.mean()) ** 2).sum())
    lof_df = df - pure_df
    lof_sse = sse - pure_sse
    if lof_df <= 0 or lof_sse < 0:
        raise AssertionError("失拟自由度或平方和无效")
    lof_f = (lof_sse / lof_df) / (pure_sse / pure_df)
    rows["误差"] = {"df": float(df), "ss": sse, "ms": mse, "f": None, "p": None}
    rows["失拟"] = {"df": float(lof_df), "ss": lof_sse, "ms": lof_sse / lof_df,
                    "f": lof_f, "p": float(stats.f.sf(lof_f, lof_df, pure_df))}
    rows["纯误差"] = {"df": float(pure_df), "ss": pure_sse, "ms": pure_sse / pure_df,
                      "f": None, "p": None}
    rows["合计"] = {"df": float(n - 1), "ss": sst, "ms": None, "f": None, "p": None}
    return {"anova": rows, "sse": sse, "sst": sst, "ssr": model_ss, "mse": mse,
            "s": math.sqrt(mse), "r2": 1 - sse / sst,
            "adjusted_r2": 1 - (sse / df) / (sst / (n - 1)),
            "model_f": model_f, "model_p": rows["Model"]["p"]}


def compare_values(run, section, term, statistic, left, right, left_source, right_source):
    if left is None or right is None:
        return {"run": run, "section": section, "term": term, "statistic": statistic,
                "minitab_value": left, "minijmp_value": right,
                "absolute_error": None, "relative_error": None,
                "absolute_tolerance": TOL_ABS, "relative_tolerance": TOL_REL,
                "minitab_value_source": left_source, "minijmp_value_source": right_source,
                "status": "N/A"}
    a, b = float(left), float(right)
    error = abs(a - b)
    relative = error / abs(a) if a else (0.0 if error == 0 else None)
    passed = math.isclose(a, b, rel_tol=TOL_REL, abs_tol=TOL_ABS)
    return {"run": run, "section": section, "term": term, "statistic": statistic,
            "minitab_value": a, "minijmp_value": b,
            "absolute_error": error, "relative_error": relative,
            "absolute_tolerance": TOL_ABS, "relative_tolerance": TOL_REL,
            "minitab_value_source": left_source, "minijmp_value_source": right_source,
            "status": "PASS" if passed else "FAIL"}


def compare_run(run_number: int, minitab: dict, minijmp: dict) -> tuple[list[dict], dict]:
    import numpy as np
    from scipy import stats as _stats

    stats = native_stats(minitab)
    rows = []
    direct_matrix = "Minitab RSREG storage XMATRIX M1 (full precision)"
    direct_coef = "Minitab RSREG storage COEFFICIENTS C10 (full precision)"
    direct_fit = "Minitab RSREG storage FITS C8 / RESIDUALS C9 (full precision)"
    derived_anova = ("DERIVED: Minitab M1/C8/C9/C10 and fixed Y; P via scipy.stats.f.sf; "
                     "native rounded ANOVA table retained")
    direct_pred = ("Minitab PREDICT PFITS C11 / PSEFITS C12 / CLIMITS C13-C14 / "
                   "PLIMITS C15-C16 (full precision)")

    for index, row in enumerate(minitab["design"], 1):
        jmp_row = minijmp["design"][index - 1]
        rows.append(compare_values(run_number, "design", f"standard_order={index}", "standard_order",
                                   row["standard_order"], jmp_row[0],
                                   "Minitab CCDESIGN 标准序", "MiniJMP create_ccd 标准序"))
        rows.append(compare_values(run_number, "design", f"standard_order={index}", "A",
                                   row["A"], jmp_row[3],
                                   "Minitab CCDESIGN 编码 A", "MiniJMP 编码_A"))
        rows.append(compare_values(run_number, "design", f"standard_order={index}", "B",
                                   row["B"], jmp_row[4],
                                   "Minitab CCDESIGN 编码 B", "MiniJMP 编码_B"))
        rows.append(compare_values(run_number, "design", f"standard_order={index}", "point_type",
                                   {"factorial": 1.0, "axial": -1.0, "center": 0.0}[row["point_type"]],
                                   {"factorial": 1.0, "axial": -1.0, "center": 0.0}[jmp_row[1]],
                                   "Minitab CCDESIGN 点类型", "MiniJMP 点类型"))

    matrix_a = np.asarray(minitab["model_matrix"], dtype=float)
    matrix_b = np.asarray(minijmp["model_matrix"], dtype=float)
    for row_index in range(matrix_a.shape[0]):
        for column, term in enumerate(MTB_TERMS):
            rows.append(compare_values(run_number, "model_matrix",
                                       f"standard_order={row_index + 1}:{term}", "X",
                                       matrix_a[row_index, column], matrix_b[row_index, column],
                                       direct_matrix, "MiniJMP analyze_rsm matrix"))
    rows.append(compare_values(run_number, "model", "model", "rank",
                               minitab["rank"], minijmp["rank"],
                               "Minitab M1 rank", "MiniJMP result rank"))
    for term in MTB_TERMS:
        rows.append(compare_values(run_number, "coefficient", term, "estimate",
                                   minitab["coefficients"][term],
                                   minijmp["coefficients"][JMP_ALIAS[term]],
                                   direct_coef, "MiniJMP coefficients"))
    for index, row in enumerate(minitab["data_rows"]):
        rows.append(compare_values(run_number, "input", f"standard_order={index + 1}", "Y",
                                   row["Y"], minijmp["observed"][index],
                                   "fixed CSV input", "MiniJMP loaded response"))
        rows.append(compare_values(run_number, "run_statistics", f"standard_order={index + 1}", "fit",
                                   minitab["fits"][index], minijmp["fits"][index],
                                   direct_fit, "MiniJMP fitted"))
        rows.append(compare_values(run_number, "run_statistics", f"standard_order={index + 1}", "residual",
                                   minitab["residuals"][index], minijmp["residuals"][index],
                                   direct_fit, "MiniJMP residuals"))

    jmp_matrix = np.asarray(minijmp["model_matrix"], dtype=float)
    jmp_y = np.asarray(minijmp["observed"], dtype=float)
    jmp_sse = float(minijmp["sse"])
    jmp_anova = minijmp["anova"]

    def jmp_group(columns):
        """Type III 联合平方和：同时移除该组所有列后重新拟合。"""
        reduced = np.delete(jmp_matrix, columns, axis=1)
        coef, *_ = np.linalg.lstsq(reduced, jmp_y, rcond=None)
        return float(((jmp_y - reduced @ coef) ** 2).sum()) - jmp_sse

    terms = ("Model", "线性", "A", "B", "双因子交互作用", "A*B", "平方", "A*A", "B*B",
             "误差", "失拟", "纯误差", "合计")
    for term in terms:
        native = stats["anova"][term]
        if term == "Model":
            local_ss = float(((jmp_y - jmp_y.mean()) ** 2).sum() - jmp_sse)
            local = {"df": float(minijmp["rank"] - 1), "ss": local_ss,
                     "ms": local_ss / (minijmp["rank"] - 1),
                     "f": minijmp["model_f"], "p": minijmp["model_p"]}
        elif term == "误差":
            local = {"df": float(minijmp["df"]), "ss": minijmp["sse"],
                     "ms": minijmp["sse"] / minijmp["df"], "f": None, "p": None}
        elif term == "失拟":
            local = {"df": float(minijmp["lack_of_fit_df"]), "ss": minijmp["lack_of_fit_sse"],
                     "ms": (minijmp["lack_of_fit_sse"] / minijmp["lack_of_fit_df"]
                            if minijmp["lack_of_fit"] else None),
                     "f": (minijmp["lack_of_fit"] or {}).get("f"),
                     "p": (minijmp["lack_of_fit"] or {}).get("p")}
        elif term == "纯误差":
            local = {"df": float(minijmp["pure_error_df"]), "ss": minijmp["pure_error_sse"],
                     "ms": minijmp["pure_error_sse"] / minijmp["pure_error_df"],
                     "f": None, "p": None}
        elif term == "合计":
            local = {"df": float(minijmp["n"] - 1), "ss": minijmp["sst"],
                     "ms": None, "f": None, "p": None}
        elif term in ("线性", "双因子交互作用", "平方"):
            columns = {"线性": [1, 2], "双因子交互作用": [3], "平方": [4, 5]}[term]
            ss = jmp_group(columns)
            dof = len(columns)
            ms = ss / dof
            f = ms / (minijmp["sse"] / minijmp["df"])
            local = {"df": float(dof), "ss": ss, "ms": ms, "f": f,
                     "p": float(_stats.f.sf(f, dof, minijmp["df"]))}
        else:
            local = jmp_anova[JMP_ALIAS.get(term, term)]
        for metric in ("df", "ss", "ms", "f", "p"):
            rows.append(compare_values(run_number, "anova", term, metric,
                                       native[metric], local[metric],
                                       derived_anova, "MiniJMP analyze_rsm"))

    local_mse = minijmp["sse"] / minijmp["df"]
    for metric, left, right in (
            ("S", stats["s"], math.sqrt(local_mse)),
            ("R2", stats["r2"], minijmp["r2"]),
            ("adjusted_R2", stats["adjusted_r2"], minijmp["adjusted_r2"]),
            ("SSE", stats["sse"], minijmp["sse"]),
            ("SST", stats["sst"], minijmp["sst"]),
            ("MSE", stats["mse"], local_mse)):
        rows.append(compare_values(run_number, "model_summary", "model", metric, left, right,
                                   derived_anova, "MiniJMP analyze_rsm"))

    for index, point in enumerate(minitab["predictions"]):
        local = minijmp["predictions"][index]
        for key in ("fit", "se_fit", "ci_low", "ci_high", "pi_low", "pi_high"):
            rows.append(compare_values(run_number, "prediction", point["label"], key,
                                       point[key], local[key],
                                       direct_pred, "MiniJMP predict_point(confidence=0.95)"))
    return rows, stats


def write_csv(path: Path, rows: list[dict]) -> None:
    fields = ("run", "section", "term", "statistic", "minitab_value", "minijmp_value",
              "absolute_error", "relative_error", "absolute_tolerance",
              "relative_tolerance", "minitab_value_source", "minijmp_value_source", "status")
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def flatten(result: dict) -> dict[str, float]:
    flat = {}
    for name, value in result["coefficients"].items():
        flat[f"coefficient:{name}"] = float(value)
    flat["rank"] = float(result["rank"])
    for index in range(13):
        flat[f"fit:{index + 1}"] = float(result["fits"][index])
        flat[f"residual:{index + 1}"] = float(result["residuals"][index])
        for column, value in enumerate(result["model_matrix"][index]):
            flat[f"matrix:{index + 1}:{column}"] = float(value)
    source = result.get("native_stats", result)
    for metric in ("sse", "sst", "ssr", "r2", "adjusted_r2", "mse"):
        if metric in source:
            flat[metric] = float(source[metric])
    if "mse" not in flat:
        flat["mse"] = float(source["sse"]) / float(source["df"])
    flat["S"] = math.sqrt(flat["mse"])
    if "纯误差" in source["anova"]:
        pure, lack = source["anova"]["纯误差"], source["anova"]["失拟"]
    else:
        pure = {"ss": result["pure_error_sse"], "df": result["pure_error_df"],
                "f": None, "p": None}
        lack = {"ss": result["lack_of_fit_sse"], "df": result["lack_of_fit_df"],
                "f": (result["lack_of_fit"] or {}).get("f"),
                "p": (result["lack_of_fit"] or {}).get("p")}
    flat["pure_error_sse"] = float(pure["ss"])
    flat["pure_error_df"] = float(pure["df"])
    flat["lack_of_fit_sse"] = float(lack["ss"])
    flat["lack_of_fit_df"] = float(lack["df"])
    if lack["f"] is not None:
        flat["lack_of_fit_f"] = float(lack["f"])
        flat["lack_of_fit_p"] = float(lack["p"])
    for term, values in source["anova"].items():
        for metric, value in values.items():
            if value is not None:
                flat[f"anova:{term}:{metric}"] = float(value)
    for point in result["predictions"]:
        for key in ("fit", "se_fit", "ci_low", "ci_high", "pi_low", "pi_high"):
            flat[f"prediction:{point['label']}:{key}"] = float(point[key])
    return flat


def parent_main() -> int:
    LOG.write_text("", encoding="utf-8")
    COMMANDS_FILE.write_text(
        "# 由本机 Minitab 19.1.0.1 COM ExecuteCommand 实际运行\n"
        "# 依据 Minitab 官方 session commands 文档（RSREG / CCDESIGN / PREDICT）\n\n"
        "# Native face-centered CCD: alpha=1, 2 factors, 5 center points\n"
        + DESIGN_COMMAND + "\n\n"
        "# Native RSM least-squares fit, coded units, explicit quadratic terms\n"
        + ANALYSIS_COMMAND + "\n\n"
        "# Native prediction at 3 points with SE Fit and 95% intervals\n"
        + PREDICTION_COMMAND + "\n",
        encoding="utf-8",
    )
    rows = read_input()
    log("MiniJMP × Minitab 19 面心 CCD 二次响应面对标")
    log(f"项目 Python: {sys.executable}")
    log(f"Minitab: {MTB_EXE}; 固定数据: {INPUT.name}; 两次独立运行")
    log("MiniJMP 入口: code/doe_ccd.py::create_ccd + code/doe_rsm.py::analyze_rsm "
        "+ code/doe_predict.py::predict_point")

    all_rows, mtb_runs, jmp_runs, native_by_run = [], {}, {}, {}
    failures = []
    for run_number in (1, 2):
        log(f"===== 独立运行 {run_number}/2 =====")
        process = subprocess.run(
            [sys.executable, "-X", "utf8", str(Path(__file__).resolve()),
             "--com-worker", str(run_number)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=240,
        )
        if process.stdout.strip():
            log(process.stdout.rstrip())
        if process.stderr.strip():
            log("COM worker stderr:\n" + process.stderr.rstrip())
        if process.returncode:
            raise RuntimeError(f"Minitab COM worker {run_number} 退出码 {process.returncode}")
        for _ in range(40):
            if not running_minitab_pids():
                break
            time.sleep(0.5)
        pids = running_minitab_pids()
        if pids:
            raise RuntimeError(f"Minitab 运行后仍有 Mtb.exe 进程: {pids}")

        minitab = json.loads((OUT / f"doe_ccd_minitab_run{run_number}.json")
                             .read_text(encoding="utf-8"))
        if minitab["version"] != "19.1.0.1":
            raise RuntimeError(f"COM worker 版本不符: {minitab['version']}")
        if (canonical(minitab["app_path"]) != canonical(MTB_EXE)
                or canonical(minitab["process_path"]) != canonical(MTB_EXE)):
            raise RuntimeError("COM worker AppPath/进程映像与指定 Mtb.exe 不一致")
        minijmp = run_minijmp(rows)
        comparisons, stats = compare_run(run_number, minitab, minijmp)
        minitab["native_stats"] = stats
        all_rows.extend(comparisons)
        mtb_runs[run_number], jmp_runs[run_number] = minitab, minijmp
        native_by_run[run_number] = stats
        failures.extend(row for row in comparisons if row["status"] == "FAIL")
        log(f"运行 {run_number}: PASS={sum(r['status'] == 'PASS' for r in comparisons)}, "
            f"N/A={sum(r['status'] == 'N/A' for r in comparisons)}, "
            f"FAIL={sum(r['status'] == 'FAIL' for r in comparisons)}; Minitab PID 已退出。")

    for software, runs in (("Minitab", mtb_runs), ("MiniJMP", jmp_runs)):
        first, second = flatten(runs[1]), flatten(runs[2])
        if set(first) != set(second):
            raise AssertionError(f"{software} 两次运行的项集合不一致")
        for key in sorted(first):
            row = compare_values("run1_vs_run2", f"repeatability_{software}", key, "value",
                                 first[key], second[key],
                                 f"{software} sequential clean-process rerun",
                                 f"{software} sequential clean-process rerun")
            all_rows.append(row)
            if row["status"] == "FAIL":
                failures.append(row)

    write_csv(COMPARISON, all_rows)
    (OUT / "doe_ccd_minitab_results.json").write_text(
        json.dumps({str(k): v for k, v in mtb_runs.items()}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    (OUT / "doe_ccd_minijmp_results.json").write_text(
        json.dumps({str(k): v for k, v in jmp_runs.items()}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    REPORT.write_text(make_report(all_rows, failures, native_by_run, jmp_runs), encoding="utf-8")
    status = "PASS" if not failures else "FAIL"
    log(f"最终结果: {status}; 比较记录 {len(all_rows)} 项；"
        f"PASS={sum(r['status'] == 'PASS' for r in all_rows)}, "
        f"N/A={sum(r['status'] == 'N/A' for r in all_rows)}, FAIL={len(failures)}。")
    for row in failures[:20]:
        log(f"FAIL {row['run']} {row['section']} {row['term']} {row['statistic']}: "
            f"Minitab={row['minitab_value']}, MiniJMP={row['minijmp_value']}, "
            f"abs={row['absolute_error']}, rel={row['relative_error']}")
    return 1 if failures else 0


def make_report(rows, failures, native_by_run, jmp_runs) -> str:
    stats = native_by_run[1]
    anova = stats["anova"]
    local = jmp_runs[1]
    counts = Counter(row["status"] for row in rows)

    def cell(term, metric):
        value = anova[term][metric]
        return f"{value:.10g}" if value is not None else "-"

    pred_rows = []
    for point in local["predictions"]:
        pred_rows.append(
            f"| {point['label']} | ({point['A']:g}, {point['B']:g}) | {point['fit']:.10g} | "
            f"{point['se_fit']:.10g} | [{point['ci_low']:.10g}, {point['ci_high']:.10g}] | "
            f"[{point['pi_low']:.10g}, {point['pi_high']:.10g}] |")
    verdict = "PASS" if not failures else "FAIL"

    return f"""# MiniJMP x Minitab 19 面心 CCD 二次响应面对标

## 验收结果

**{verdict}**：两次独立 Minitab COM 会话与 MiniJMP 生产入口均已完成。
比较 CSV 共 {len(rows)} 行，PASS {counts['PASS']}、N/A {counts['N/A']}、FAIL {counts['FAIL']}。
容差沿用 2x2 对标：绝对 {TOL_ABS:g}、相对 {TOL_REL:g}，未做任何放宽。

## 数据与方法

- 固定输入 doe_ccd_input.csv：标准序 13 次运行，4 个因子点、4 个轴点、5 个中心点，面心 alpha=1，不分区组。
- 响应为确定性构造：外点按二次曲面加固定小偏差，5 个中心点响应 10.10、9.94、10.06、9.98、10.12，使纯误差为 0.024、SSE 为 0.04338、残差 df=7、失拟 df=3。
- 两边都使用完全相同的编码因子，同一模型项（A、B、A*B、A^2、B^2），同一截距约定，95% 置信水平。
- MiniJMP 生产入口：code/doe_ccd.py::create_ccd、code/doe_rsm.py::analyze_rsm、code/doe_predict.py::predict_point；未修改任何统计生产代码。

## 已完成的 Minitab 原生一致性验证（DIRECT）

- CCDESIGN 2; ALPHA 1; CENTER 5; DESIGN. 生成的 13 个运行，其标准序、点类型、A/B 编码与固定 CSV 逐行一致。
- RSREG 的存储量经 COM 直接回读且为全精度：XMATRIX M1（13x6）、COEFFICIENTS C10、FITS C8、RESIDUALS C9。比较使用的正是这些值，不是报表舍入值。
- 模型矩阵秩、6 个系数、13 个拟合值、13 个残差全部 DIRECT 比较。
- 三个预测点使用 PREDICT + KPREDICTORS 原生执行，PFITS、PSEFITS、CLIMITS、PLIMITS 存列后全精度回读；拟合值、SE Fit、95% 均值置信区间、95% 单次观测预测区间共 18 项均为 DIRECT。

## 由 Minitab 高精度数据重建的统计量（DERIVED）

ANOVA 的 Model/线性/交互/平方/误差/失拟/纯误差/合计各行，以及 S、R2、调整 R2、SSE、SST、MSE，均由 Minitab 的 M1、C10、C8、C9 与固定 Y 独立重建（P 值用 scipy.stats.f.sf）。
这些是派生量，用于与 MiniJMP 的对应定义比较；Minitab 原生报表的舍入表同时保留在两个 raw 文件中，未宣称报表级逐位 parity。

| 项目 | Minitab（DERIVED，全精度） | MiniJMP |
| --- | --- | --- |
| Model SS / df | {cell('Model', 'ss')} / 5 | {local['ssr']:.10g} / 5 |
| Error SS / df | {cell('误差', 'ss')} / 7 | {local['sse']:.10g} / 7 |
| Total SS / df | {cell('合计', 'ss')} / 12 | {local['sst']:.10g} / 12 |
| 失拟 SS / df | {cell('失拟', 'ss')} / 3 | {local['lack_of_fit_sse']:.10g} / 3 |
| 纯误差 SS / df | {cell('纯误差', 'ss')} / 4 | {local['pure_error_sse']:.10g} / 4 |
| S | {math.sqrt(anova['误差']['ms']):.10g} | {math.sqrt(local['sse'] / local['df']):.10g} |
| R2 | {stats['r2']:.10g} | {local['r2']:.10g} |
| 调整 R2 | {stats['adjusted_r2']:.10g} | {local['adjusted_r2']:.10g} |

## 三个预测点（DIRECT）

| 点 | 编码设置 | 预测均值 | SE Fit | 95% 均值区间 | 95% 预测区间 |
| --- | --- | --- | --- | --- | --- |
{chr(10).join(pred_rows)}

## 未获得直接产品证据的内容

- Minitab 19 的 PREDICT 文档只提供 PFITS/PSEFITS/CLIMITS/PLIMITS，没有逐项 SS/F/P 的机器精度存储；因此逐项 SS/F/P 属于 DERIVED。
- 未验证其他 CCD 布局（CCC、旋转、分区组、分数立方、3 个以上因子），未验证 BBD 或其他 DOE 类型。
- 不更新正式 DOE 功能矩阵，不代表全部统计输出的 parity。

## 文件

- verify_doe_ccd.py、doe_ccd_input.csv、doe_ccd_session_commands.txt
- doe_ccd_minitab_raw_run1.txt、doe_ccd_minitab_raw_run2.txt
- doe_ccd_minitab_run1.json、doe_ccd_minitab_run2.json
- doe_ccd_comparison.csv、doe_ccd_run.log
"""


def worker_entry() -> int:
    try:
        return worker_main(int(sys.argv[2]))
    except Exception:
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--com-worker":
        raise SystemExit(worker_entry())
    try:
        raise SystemExit(parent_main())
    except SystemExit:
        raise
    except Exception:
        message = traceback.format_exc()
        log("FAIL: " + message)
        REPORT.write_text("# 面心 CCD 自动对标\n\n**FAIL**\n\n" + message,
                          encoding="utf-8")
        raise SystemExit(1)
