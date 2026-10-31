"""MiniJMP × Minitab 19 quadratic Scheffé mixture parity check."""
from __future__ import annotations

import csv
import ctypes
import json
import math
import re
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
INPUT = OUT / "doe_mixture_input.csv"
COMMANDS = OUT / "doe_mixture_session_commands.txt"
RAW = OUT / "doe_mixture_minitab_raw.txt"
MINIJMP = OUT / "doe_mixture_minijmp.json"
MINITAB = OUT / "doe_mixture_minitab.json"
COMPARISON = OUT / "doe_mixture_comparison.csv"
REPORT = OUT / "doe_mixture_acceptance_report.md"
TOL_ABS = 1e-9
TOL_REL = 1e-9
TERMS = ("A", "B", "C", "A*B", "A*C", "B*C")
PREDICTIONS = ((0.2, 0.3, 0.5), (0.15, 0.55, 0.30), (0.4, 0.2, 0.4))
REPLICATE_OFFSETS = (-0.25, 0.25)


def point_key(a, b, c):
    return tuple(round(float(value), 12) for value in (a, b, c))


def response_value(a, b, c, replicate):
    return (50 * a + 35 * b + 45 * c + 12 * a * b - 8 * a * c
            + 6 * b * c + REPLICATE_OFFSETS[replicate - 1])


def read_input():
    with INPUT.open(newline="", encoding="utf-8-sig") as stream:
        rows = []
        for row in csv.DictReader(stream):
            item = {"run_id": row["run_id"], "standard_order": int(row["standard_order"]),
                    "run_order": int(row["run_order"]), "replicate": int(row["replicate"]),
                    "point_type": row["point_type"],
                    **{name: float(row[name]) for name in "ABC"}, "Y": float(row["Y"])}
            rows.append(item)
    expected_points = {
        point_key(1, 0, 0), point_key(0, 1, 0), point_key(0, 0, 1),
        point_key(.5, .5, 0), point_key(.5, 0, .5), point_key(0, .5, .5),
        point_key(1 / 3, 1 / 3, 1 / 3),
    }
    if len(rows) != 14 or Counter(row["replicate"] for row in rows) != {1: 7, 2: 7}:
        raise ValueError("固定混料输入必须为 7 个设计点各重复 2 次")
    if {point_key(row["A"], row["B"], row["C"]) for row in rows} != expected_points:
        raise ValueError("固定输入必须包含 3 个顶点、3 个边中点和 1 个中心点")
    if any(min(row[name] for name in "ABC") < 0
           or not math.isclose(sum(row[name] for name in "ABC"), 1, abs_tol=1e-12)
           for row in rows):
        raise ValueError("混料输入违反非负或比例和为 1 的约束")
    if any(not math.isfinite(row["Y"]) or row["Y"] <= 0 for row in rows):
        raise ValueError("响应必须为有限正数")
    if len({(point_key(row["A"], row["B"], row["C"]), row["replicate"])
            for row in rows}) != 14:
        raise ValueError("固定输入的设计点/重复映射不唯一")
    return rows


def write_input(rows):
    fields = ("run_id", "standard_order", "run_order", "replicate", "point_type",
              "A", "B", "C", "Y")
    with INPUT.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def run_minijmp_worker():
    if (not PROJECT_PYTHON.is_file()
            or str(Path(sys.executable).resolve()).casefold()
            != str(PROJECT_PYTHON.resolve()).casefold()):
        raise RuntimeError(f"请使用项目解释器运行: {PROJECT_PYTHON}")
    sys.path.insert(0, str(ROOT / "code"))
    import numpy as np
    import pandas as pd
    from doe_mixture import MixtureSpec
    from doe_mixture_analysis import analyze_mixture
    from doe_mixture_constraints import ComponentSpec
    from doe_mixture_designs import create_mixture_design
    from doe_mixture_predict import predict_mixture

    spec = MixtureSpec("minitab19-mixture-parity",
                       tuple(ComponentSpec(name, name) for name in "ABC"),
                       ("Y",), "simplex_centroid", None, seed=19)
    frame, metadata = create_mixture_design(spec, replicates=2, include_centroid=True)
    rows = []
    for _, row in frame.iterrows():
        replicate = int(row["重复"])
        a, b, c = (float(row[f"设定_{name}"]) for name in "ABC")
        rows.append({"run_id": str(row["运行ID"]),
                     "standard_order": int(row["标准序"]),
                     "run_order": int(row["运行序"]), "replicate": replicate,
                     "point_type": str(row["点类型"]), "A": a, "B": b, "C": c,
                     "Y": response_value(a, b, c, replicate)})
    write_input(rows)
    rows = read_input()
    frame.loc[:, "响应_Y"] = pd.array([row["Y"] for row in rows], dtype="Float64")
    analysis = analyze_mixture(frame, metadata["mixture"], "Y", degree=2,
                               doe_metadata=metadata["doe"])
    if (analysis["terms"] != TERMS or analysis["rank"] != 6 or analysis["n"] != 14
            or analysis["df"] != 8 or analysis["pure_error_df"] != 7
            or not math.isclose(analysis["pure_error_sse"], .875, abs_tol=1e-12)
            or not math.isclose(analysis["sse"], .875, abs_tol=1e-12)
            or abs(analysis["lack_of_fit_sse"]) > 1e-12):
        raise AssertionError("固定输入的 Scheffé 模型自检失败")
    np.testing.assert_allclose(analysis["coefficients"], [50, 35, 45, 12, -8, 6],
                               rtol=0, atol=1e-10)

    fit_rows = []
    matrix = analysis["model"].matrix(analysis["settings"])
    for index, row in enumerate(rows):
        fit_rows.append({**row, "fit": float(analysis["fitted"][index]),
                         "residual": float(analysis["residuals"][index]),
                         "matrix": [float(value) for value in matrix[index]]})
    predictions = []
    for point in PREDICTIONS:
        result = predict_mixture(frame, metadata["mixture"], "Y", point,
                                degree=2, doe_metadata=metadata["doe"], confidence=.95)
        interval = result["intervals"]
        predictions.append({"A": point[0], "B": point[1], "C": point[2],
                            "fit": float(result["prediction"]),
                            "se_fit": _number(interval["se_fit"]),
                            "ci_low": _number(interval["ci_low"]),
                            "ci_high": _number(interval["ci_high"]),
                            "pi_low": _number(interval["pi_low"]),
                            "pi_high": _number(interval["pi_high"]),
                            "interval_status": interval["status"]})
    if any(item["interval_status"] != "可用" for item in predictions):
        raise AssertionError("内部预测自检要求三个点的 95% CI/PI 均可用")
    inference = analysis["inference"]
    result = {
        "spec": spec.to_dict(), "terms": list(analysis["terms"]),
        "has_constant": analysis["has_constant"], "rank": analysis["rank"],
        "n": analysis["n"], "p": analysis["p"], "df": analysis["df"],
        "model_df": analysis["model_df"], "total_df": analysis["total_df"],
        "coefficients": {term: float(value)
                          for term, value in zip(analysis["terms"], analysis["coefficients"])},
        "fits": fit_rows,
        "summary": {"rank": int(analysis["rank"]), "model_df": int(analysis["model_df"]),
                    "error_df": int(analysis["df"]), "total_df": int(analysis["total_df"]),
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
        "predictions": predictions, "snapshot_id": analysis["snapshot_id"],
        "status": analysis["status"],
    }
    MINIJMP.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("MiniJMP mixture self-check: 7 points × 2 replicates, rank 6, SSE=.875, "
          "pure error df=7, three 95% prediction intervals PASS", flush=True)


def _number(value):
    return None if value is None else float(value)


def _column_values(column):
    values = column.GetData()
    return [float(values)] if isinstance(values, (int, float)) else [float(v) for v in values]


def _normalized_name(value):
    return re.sub(r"[\s_]", "", str(value)).casefold()


def parse_prediction_display(output):
    pattern = re.compile(
        r"(?m)^\s*(\d+)\s+([-+\d.eE]+)\s+([-+\d.eE]+)\s+"
        r"\(([-+\d.eE]+),\s*([-+\d.eE]+)\)\s+"
        r"\(([-+\d.eE]+),\s*([-+\d.eE]+)\)\s*$"
    )
    matches = pattern.findall(output)
    if len(matches) < 3 or [int(row[0]) for row in matches[:3]] != [1, 2, 3]:
        raise RuntimeError("Minitab MIXREG PREDICT 未返回三行完整 95% 预测表")
    return [{"fit": float(row[1]), "se_fit": float(row[2]),
             "ci_low": float(row[3]), "ci_high": float(row[4]),
             "pi_low": float(row[5]), "pi_high": float(row[6])}
            for row in matches[:3]]


def _find_column(names, wanted, required=True):
    targets = {_normalized_name(value) for value in wanted}
    for index, name in enumerate(names, 1):
        if _normalized_name(name) in targets:
            return index
    if required:
        raise RuntimeError(f"Minitab 设计缺少列 {tuple(wanted)}；实际列={names}")
    return None


def _execute(project, app, command, raw, label):
    from verify_doe_ccd import capture_command_output

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
    if re.search(r"(?im)^\s*\*\s*(?:错误|ERROR)\s*\*", output):
        raise RuntimeError(f"{label} 返回 Minitab 错误信息")
    return output


def minitab_worker():
    import winreg
    import win32api
    import win32process
    import pythoncom
    import win32com.client
    import numpy as np

    from verify_doe_ccd import canonical, running_minitab_pids

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
        design_command = ("SCDESIGN 3;\n  ALLREP 2;\n  PROPORTIONS;\n  DESIGN.")
        _execute(project, app, design_command, raw, "SCDESIGN")
        worksheet = project.ActiveWorksheet
        columns = worksheet.Columns
        names = [str(columns.Item(index).Name) for index in range(1, int(columns.Count) + 1)]
        factor_columns = {name: _find_column(names, (name,)) for name in "ABC"}
        std_column = _find_column(names, ("StdOrder", "StandardOrder", "标准序"), required=False)
        run_column = _find_column(names, ("RunOrder", "运行序"), required=False)
        type_column = _find_column(names, ("PtType", "PointType", "点类型"), required=False)
        design_count = len(_column_values(columns.Item(factor_columns["A"])))
        if design_count != 14:
            raise RuntimeError(f"SCDESIGN 应生成 14 行，实际 {design_count}；列={names}")
        coordinates = [{name: _column_values(columns.Item(factor_columns[name]))[index]
                        for name in "ABC"} for index in range(design_count)]
        occurrences = defaultdict(int)
        input_lookup = {(point_key(row["A"], row["B"], row["C"]), row["replicate"]): row
                        for row in rows}
        native_rows = []
        for index, setting in enumerate(coordinates):
            key = point_key(*(setting[name] for name in "ABC"))
            occurrences[key] += 1
            replicate = occurrences[key]
            source = input_lookup.get((key, replicate))
            if source is None:
                raise RuntimeError(f"SCDESIGN 点/重复无法映射固定输入: {key}, replicate={replicate}")
            native_rows.append({
                "standard_order": (int(_column_values(columns.Item(std_column))[index])
                                   if std_column else index + 1),
                "run_order": (int(_column_values(columns.Item(run_column))[index])
                              if run_column else index + 1),
                "point_type": (str(columns.Item(type_column).GetData()[index])
                               if type_column else ""),
                "replicate": replicate, **setting, "Y": source["Y"],
            })
        if any(count != 2 for count in occurrences.values()) or len(occurrences) != 7:
            raise RuntimeError(f"SCDESIGN 点集或重复次数不符: {dict(occurrences)}")
        if any(not math.isclose(sum(row[name] for name in "ABC"), 1, abs_tol=1e-12)
               or min(row[name] for name in "ABC") < -1e-12 for row in native_rows):
            raise RuntimeError("SCDESIGN 比例单位下存在无效混料点")
        raw.append("===== SCDESIGN native worksheet columns =====\n" + repr(names)
                   + "\n===== mapped design rows and fixed response =====\n"
                   + json.dumps(native_rows, ensure_ascii=False, indent=2))

        def add_column(name, values=None):
            column = columns.Add(None, None, 1)
            column.Name = name
            index = int(columns.Count)
            if values is not None:
                column.SetData(tuple(values), 1, len(values))
            return index

        response_column = add_column("Y", [row["Y"] for row in native_rows])
        prediction_columns = [add_column(f"P_{name}", [point[index] for point in PREDICTIONS])
                              for index, name in enumerate("ABC")]
        output_columns = {name: add_column(name) for name in ("Fit", "Resid", "Coef")}
        matrices = worksheet.Matrices
        existing_matrices = {str(matrices.Item(i).Name).casefold()
                             for i in range(1, int(matrices.Count) + 1)}
        matrix_name = next(f"M{i}" for i in range(1, 100)
                           if f"m{i}" not in existing_matrices)
        analysis_command = (
            f"MIXREG C{response_column} = "
            + " ".join(f"C{factor_columns[name]}" for name in "ABC") + " "
            + " ".join(f"C{factor_columns[first]}*C{factor_columns[second]}"
                        for first, second in (("A", "B"), ("A", "C"), ("B", "C")))
            + ";\n"
            + "  INUNIT 1;\n  LOWER 0 0 0;\n  BRIEF 3;\n"
            + f"  FITS C{output_columns['Fit']};\n"
            + f"  RESIDUALS C{output_columns['Resid']};\n"
            + f"  COEFFICIENTS C{output_columns['Coef']};\n"
            + f"  XMATRIX {matrix_name};\n"
            + "  PREDICT " + " ".join(f"C{index}" for index in prediction_columns) + ";\n"
            + "  CONFIDENCE 95."
        )
        analysis_output = _execute(project, app, analysis_command, raw, "MIXREG")
        display_predictions = parse_prediction_display(analysis_output)
        matrix_index = next((i for i in range(1, int(worksheet.Matrices.Count) + 1)
                             if str(worksheet.Matrices.Item(i).Name).casefold()
                             == matrix_name.casefold()), None)
        if matrix_index is None:
            raise RuntimeError(f"MIXREG 未存储矩阵 {matrix_name}")
        native_matrix = worksheet.Matrices.Item(matrix_index)
        n, p = int(native_matrix.RowCount), int(native_matrix.ColumnCount)
        if (n, p) != (14, 6):
            raise RuntimeError(f"MIXREG XMATRIX 应为 14×6，实际 {n}×{p}")
        flat = [float(value) for value in native_matrix.GetData()]
        model_matrix = [[flat[column * n + row] for column in range(p)]
                        for row in range(n)]
        expected_by_term = {
            term: [row["A"] if term == "A" else row["B"] if term == "B"
                   else row["C"] if term == "C"
                   else row[term.split("*")[0]] * row[term.split("*")[1]]
                   for row in native_rows]
            for term in TERMS
        }
        term_columns = {}
        for column in range(p):
            actual = [model_matrix[row][column] for row in range(n)]
            matches = [term for term, values in expected_by_term.items()
                       if np.allclose(actual, values, rtol=0, atol=1e-12)]
            if len(matches) != 1 or matches[0] in term_columns:
                raise RuntimeError(f"Minitab XMATRIX 列无法唯一映射到 Scheffé 项: {column}, {matches}")
            term_columns[matches[0]] = column
        if set(term_columns) != set(TERMS):
            raise RuntimeError(f"Minitab Scheffé 项映射不完整: {term_columns}")

        fits = _column_values(columns.Item(output_columns["Fit"]))[:n]
        residuals = _column_values(columns.Item(output_columns["Resid"]))[:n]
        coefficients_raw = _column_values(columns.Item(output_columns["Coef"]))[:p]
        coefficients = {term: coefficients_raw[index]
                        for term, index in term_columns.items()}
        mtb_result = {
            "version": version, "app_path": app_path, "process_path": process_path,
            "design_command": design_command, "analysis_command": analysis_command,
            "design_columns": names, "matrix_name": matrix_name,
            "design_rows": native_rows, "term_columns": term_columns,
            "coefficients": coefficients, "fits": fits, "residuals": residuals,
            "model_matrix": model_matrix, "rank": int(np.linalg.matrix_rank(model_matrix)),
            "prediction_display": display_predictions,
        }
        MINITAB.write_text(json.dumps(mtb_result, ensure_ascii=False, indent=2), encoding="utf-8")
        RAW.write_text("\n\n".join(raw) + "\n", encoding="utf-8")
        print(f"Minitab {version}: SCDESIGN + MIXREG; matrix={n}×{p}, rank={mtb_result['rank']}; "
              "native PREDICT executed", flush=True)
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
    if rank != p or len(y) != n or len(fitted) != n or len(residuals) != n:
        raise ValueError("Minitab MIXREG 高精度输出的长度/秩不满足完整二次模型")
    np.testing.assert_allclose(y - fitted, residuals, rtol=0, atol=2e-9)
    sse = float(residuals @ residuals)
    constant_projection = x @ np.linalg.lstsq(x, np.ones(n), rcond=None)[0]
    has_constant = np.linalg.norm(np.ones(n) - constant_projection) <= 1e-8 * math.sqrt(n)
    sst = float(np.sum((y - y.mean()) ** 2)) if has_constant else float(y @ y)
    total_df = n - 1 if has_constant else n
    model_df = rank - 1 if has_constant else rank
    error_df = n - rank
    ssr = max(0.0, sst - sse)
    mse = sse / error_df
    model_f = (ssr / model_df) / mse
    pure_cells = defaultdict(list)
    for row in rows:
        pure_cells[point_key(row["A"], row["B"], row["C"])].append(row["Y"])
    pure_error_df = sum(len(cell) - 1 for cell in pure_cells.values())
    pure_error_sse = sum(sum((value - sum(cell) / len(cell)) ** 2 for value in cell)
                         for cell in pure_cells.values())
    lack_of_fit_df = error_df - pure_error_df
    lack_of_fit_sse = max(0.0, sse - pure_error_sse)
    lack_of_fit_f = ((lack_of_fit_sse / lack_of_fit_df)
                     / (pure_error_sse / pure_error_df)) if lack_of_fit_df > 0 else None
    xtx_inverse = np.linalg.inv(x.T @ x)
    critical = float(stats.t.ppf(.975, error_df))
    coefficients = np.asarray([mtb["coefficients"][term] for term in TERMS])
    predictions = []
    for point in PREDICTIONS:
        a, b, c = point
        x0 = np.asarray([a, b, c, a * b, a * c, b * c], dtype=float)
        fit = float(x0 @ coefficients)
        h0 = float(x0 @ xtx_inverse @ x0)
        se_fit = math.sqrt(mse * h0)
        se_prediction = math.sqrt(mse * (1 + h0))
        predictions.append({"A": a, "B": b, "C": c, "fit": fit,
                            "se_fit": se_fit, "ci_low": fit - critical * se_fit,
                            "ci_high": fit + critical * se_fit,
                            "pi_low": fit - critical * se_prediction,
                            "pi_high": fit + critical * se_prediction})
    result = {
        "rank": rank, "n": n, "p": p, "model_df": model_df,
        "error_df": error_df, "total_df": total_df, "sse": sse,
        "sst": sst, "ssr": ssr, "mse": mse, "s": math.sqrt(mse),
        "r2": 1 - sse / sst, "adjusted_r2": 1 - (sse / error_df) / (sst / total_df),
        "model_f": model_f,
        "model_p": float(stats.f.sf(model_f, model_df, error_df)),
        "pure_error_df": pure_error_df, "pure_error_sse": pure_error_sse,
        "lack_of_fit_df": lack_of_fit_df, "lack_of_fit_sse": lack_of_fit_sse,
        "lack_of_fit_f": lack_of_fit_f,
        "lack_of_fit_p": (float(stats.f.sf(lack_of_fit_f, lack_of_fit_df, pure_error_df))
                           if lack_of_fit_f is not None else None),
        "term_anova": {}, "predictions": predictions,
    }
    for index, term in enumerate(TERMS):
        reduced = np.delete(x, index, axis=1)
        reduced_beta = np.linalg.lstsq(reduced, y, rcond=None)[0]
        reduced_sse = float(np.sum((y - reduced @ reduced_beta) ** 2))
        ss = max(0.0, reduced_sse - sse)
        if term in "ABC":
            f_value = p_value = None
        else:
            f_value = ss / mse
            p_value = float(stats.f.sf(f_value, 1, error_df))
        result["term_anova"][term] = {
            "ss": ss, "df": 1, "f": f_value, "p": p_value,
        }
    return result


def compare_values(section, term, statistic, left, right, left_source, right_source,
                   abs_tolerance=TOL_ABS, rel_tolerance=TOL_REL):
    if left is None or right is None:
        return {"run": "MIX-SL2", "section": section, "term": term,
                "statistic": statistic, "minitab_value": left, "minijmp_value": right,
                "absolute_error": None, "relative_error": None,
                "absolute_tolerance": abs_tolerance, "relative_tolerance": rel_tolerance,
                "minitab_value_source": left_source, "minijmp_value_source": right_source,
                "status": "N/A"}
    a, b = float(left), float(right)
    error = abs(a - b)
    relative = error / abs(a) if a else (0.0 if error == 0 else None)
    passed = math.isclose(a, b, rel_tol=rel_tolerance, abs_tol=abs_tolerance)
    return {"run": "MIX-SL2", "section": section, "term": term,
            "statistic": statistic, "minitab_value": a, "minijmp_value": b,
            "absolute_error": error, "relative_error": relative,
            "absolute_tolerance": abs_tolerance, "relative_tolerance": rel_tolerance,
            "minitab_value_source": left_source, "minijmp_value_source": right_source,
            "status": "PASS" if passed else "FAIL"}


def compare_case(minijmp, mtb):
    rows = []
    direct_design = "Minitab 19 SCDESIGN worksheet storage (DIRECT)"
    local_design = "MiniJMP create_mixture_design (DIRECT)"
    direct_matrix = "Minitab 19 MIXREG XMATRIX (DIRECT)"
    direct_model = "Minitab 19 MIXREG COEFFICIENTS/FITS/RESIDUALS (DIRECT)"
    derived = ("DERIVED: Minitab MIXREG XMATRIX, COEFFICIENTS, FITS/RESIDUALS, "
               "fixed response and scipy.stats")
    local_analysis = "MiniJMP analyze_mixture"
    local_rows = {(point_key(row["A"], row["B"], row["C"]), row["replicate"]): row
                  for row in minijmp["fits"]}
    mtb_rows = {(point_key(row["A"], row["B"], row["C"]), row["replicate"]): index
                for index, row in enumerate(mtb["design_rows"])}
    if set(local_rows) != set(mtb_rows):
        raise ValueError("MiniJMP/Minitab 混料点与重复数不能一一映射")

    for key in sorted(local_rows):
        local, index = local_rows[key], mtb_rows[key]
        native = mtb["design_rows"][index]
        label = f"{key[0]} / rep {key[1]}"
        for name in "ABC":
            rows.append(compare_values("design", label, name, native[name], local[name],
                                       direct_design, local_design))
        rows.append(compare_values("design", label, "Y", native["Y"], local["Y"],
                                   "Fixed input CSV (shared DIRECT)", "Fixed input CSV (shared DIRECT)"))
        local_fit = local["matrix"]
        for term, column in mtb["term_columns"].items():
            rows.append(compare_values("model_matrix", label, term,
                                       mtb["model_matrix"][index][column],
                                       local_fit[TERMS.index(term)], direct_matrix,
                                       "MiniJMP MixtureTermModel matrix (DIRECT)"))
        rows.append(compare_values("fit", label, "fitted", mtb["fits"][index],
                                   local["fit"], direct_model, local_analysis))
        rows.append(compare_values("fit", label, "residual", mtb["residuals"][index],
                                   local["residual"], direct_model, local_analysis))

    for term in TERMS:
        rows.append(compare_values("coefficient", term, "estimate", mtb["coefficients"][term],
                                   minijmp["coefficients"][term], direct_model, local_analysis))
    stats = derive_minitab_stats(mtb)
    local_summary = minijmp["summary"]
    summary_metrics = ("rank", "model_df", "error_df", "total_df", "sse", "sst", "ssr",
                       "mse", "s", "r2", "adjusted_r2", "model_f", "model_p",
                       "pure_error_df", "pure_error_sse", "lack_of_fit_df",
                       "lack_of_fit_sse", "lack_of_fit_f", "lack_of_fit_p")
    for metric in summary_metrics:
        rows.append(compare_values("model_summary", "model", metric, stats[metric],
                                   local_summary[metric], derived, local_analysis))
    local_anova = {item["term"]: item for item in minijmp["anova"]}
    for term in TERMS:
        for metric in ("ss", "df", "f", "p"):
            rows.append(compare_values("term_anova", term, metric,
                                       stats["term_anova"][term][metric],
                                       local_anova[term][metric], derived, local_analysis))
    for index, prediction in enumerate(stats["predictions"]):
        local = minijmp["predictions"][index]
        for metric in ("fit", "se_fit", "ci_low", "ci_high", "pi_low", "pi_high"):
            rows.append(compare_values("prediction", f"P{index + 1}", metric,
                                       prediction[metric], local[metric],
                                       "DERIVED: Minitab MIXREG COEFFICIENTS/XMATRIX and residual variance",
                                       "MiniJMP predict_mixture(confidence=.95)"))
            rows.append(compare_values(
                "prediction_display", f"P{index + 1}", metric,
                mtb["prediction_display"][index][metric], local[metric],
                "DISPLAY: Minitab 19 MIXREG PREDICT (3 decimals)",
                "MiniJMP predict_mixture(confidence=.95)", abs_tolerance=5.1e-4,
                rel_tolerance=0))
    return rows, stats


def write_comparison(rows):
    fields = ("run", "section", "term", "statistic", "minitab_value", "minijmp_value",
              "absolute_error", "relative_error", "absolute_tolerance", "relative_tolerance",
              "minitab_value_source", "minijmp_value_source", "status")
    with COMPARISON.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_report(rows, status, reason=""):
    counts = {name: sum(row["status"] == name for row in rows)
              for name in ("PASS", "FAIL", "N/A", "UNSUPPORTED")}
    sources = {name: sum(name in row["minitab_value_source"] for row in rows)
               for name in ("DIRECT", "DERIVED", "DISPLAY")}
    measured = [row for row in rows if row["absolute_error"] is not None]
    maximum = max(measured, key=lambda row: row["absolute_error"], default=None)
    report = ["# MiniJMP × Minitab 19 三组分二次 Scheffé 混料对标", "",
              f"**阶段状态：{status}**", "",
              f"比较计数：PASS {counts['PASS']} / FAIL {counts['FAIL']} / "
              f"N/A {counts['N/A']} / UNSUPPORTED {counts['UNSUPPORTED']}。",
              f"来源分类（Minitab 侧）：DIRECT {sources['DIRECT']} / "
              f"DERIVED {sources['DERIVED']} / DISPLAY {sources['DISPLAY']}。",
              (f"最大绝对误差：{maximum['absolute_error']:.10g}，"
               f"{maximum['section']} / {maximum['term']} / {maximum['statistic']}。"
               if maximum else "最大绝对误差：无可比较的数值项。"), "",
              "## 方法与范围", "",
              "- 固定设计为三组分 7 点 Simplex Centroid：3 个顶点、3 个边中点和 1 个中心点，各重复 2 次；前 6 点对应二次 Simplex Lattice，另加中心点以满足内部点和纯误差要求。响应含 A×B、A×C、B×C 交互和对称重复偏差。",
              "- Minitab 19 原生 `SCDESIGN` 生成比例设计；`MIXREG` 显式列出 A、B、C 及三个二阶交互项，配合 `INUNIT 1` 和零组分下界，拟合完整二次 Scheffé 模型。",
              "- `MIXREG` 可直接保存 XMATRIX、系数、拟合值和残差，并执行 95% `PREDICT`；Minitab 19.1.0.1 拒绝 `PSFITS` 存储子命令。预测表显示到 3 位小数并按显示精度比较；同时以 Minitab 原生高精度模型矩阵、系数和误差项独立重建预测区间。",
              "- 先按三组分比例和重复序号对齐 Minitab 与 MiniJMP 行；Minitab XMATRIX 列按实际值映射到六个 Scheffé 项，避免依赖列顺序假设。",
              "- DIRECT 包含设计、XMATRIX、系数和拟合/残差；DISPLAY 为 Minitab 的舍入预测表；DERIVED 统计量及预测区间由 Minitab 高精度存储、固定响应和 SciPy 公式重建。",
              "- MiniJMP 不为受比例和约束的组分主项报告单项 F/P；这些单项比较记为 N/A。纯误差与失拟由重复点残差重建。", "",
              "## 执行结果", "",
              f"Minitab 版本：{json.loads(MINITAB.read_text(encoding='utf-8'))['version']}" if MINITAB.is_file() else "Minitab 版本：未取得",
              f"输入行数：{len(read_input()) if INPUT.is_file() else 0}。",
              "原始 Session Command 输出见 `doe_mixture_minitab_raw.txt`。"]
    if reason:
        report.extend(["", "## 未完成原因", "", reason])
    report.extend(["", "## 证据文件", "",
                   "输入、命令、原始输出、MiniJMP/Minitab JSON 与逐项 CSV 均保存在本目录。"])
    REPORT.write_text("\n".join(report) + "\n", encoding="utf-8")
    return counts, sources, maximum


def parent_main():
    if (not PROJECT_PYTHON.is_file()
            or str(Path(sys.executable).resolve()).casefold()
            != str(PROJECT_PYTHON.resolve()).casefold()):
        raise RuntimeError(f"请使用项目解释器运行: {PROJECT_PYTHON}")
    design_command = "SCDESIGN 3;\n  ALLREP 2;\n  PROPORTIONS;\n  DESIGN."
    COMMANDS.write_text(
        "# Native Minitab 19 7-point simplex centroid design, 2 replicates\n"
        + design_command + "\n\n"
        + "# Native quadratic Scheffe fit, stored matrix/coefficient/fit/residual and displayed 95% prediction\n"
        + "MIXREG <Y> = <A> <B> <C> <A>*<B> <A>*<C> <B>*<C>;\n"
        + "  INUNIT 1;\n  LOWER 0 0 0;\n  BRIEF 3;\n  FITS <Fit>;\n  RESIDUALS <Resid>;\n"
        + "  COEFFICIENTS <Coef>;\n  XMATRIX <M>;\n"
        + "  PREDICT <P_A> <P_B> <P_C>;\n  CONFIDENCE 95;\n"
        + "  CONFIDENCE 95.\n",
        encoding="utf-8")
    command = [str(PROJECT_PYTHON), "-X", "utf8", str(Path(__file__).resolve())]
    local = subprocess.run(command + ["--minijmp-worker"], capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=240)
    print(local.stdout.rstrip(), flush=True)
    if local.stderr.strip():
        print("MiniJMP worker stderr:\n" + local.stderr.rstrip(), flush=True)
    if local.returncode:
        write_comparison([])
        write_report([], "BLOCKED", "MiniJMP 混料 API worker 执行失败；详见控制台输出。")
        return 1
    from verify_doe_ccd import running_minitab_pids

    mtb = subprocess.run(command + ["--com-worker"], capture_output=True,
                         text=True, encoding="utf-8", errors="replace", timeout=360)
    if mtb.stdout.strip():
        print(mtb.stdout.rstrip(), flush=True)
    if mtb.stderr.strip():
        print("Minitab worker stderr:\n" + mtb.stderr.rstrip(), flush=True)
    for _ in range(40):
        if not running_minitab_pids():
            break
        time.sleep(.5)
    pids = running_minitab_pids()
    if mtb.returncode or pids or not MINITAB.is_file():
        reason = (f"Minitab COM worker 退出码 {mtb.returncode}；残留进程={pids}。"
                  "原始错误与已有命令输出见 doe_mixture_minitab_raw.txt。")
        write_comparison([])
        write_report([], "BLOCKED", reason)
        print("Mixture stage BLOCKED: " + reason, flush=True)
        return 1
    minijmp = json.loads(MINIJMP.read_text(encoding="utf-8"))
    native = json.loads(MINITAB.read_text(encoding="utf-8"))
    from verify_doe_ccd import canonical

    if (native["version"] != "19.1.0.1" or canonical(native["app_path"]) != canonical(MTB_EXE)
            or canonical(native["process_path"]) != canonical(MTB_EXE)):
        write_comparison([])
        write_report([], "BLOCKED", "Minitab 19.1.0.1 COM 路径/版本验证失败。")
        return 1
    comparisons, _ = compare_case(minijmp, native)
    write_comparison(comparisons)
    status = ("FAIL" if any(row["status"] == "FAIL" for row in comparisons)
              else "PARTIAL" if any(row["status"] == "UNSUPPORTED" for row in comparisons)
              else "PASS")
    counts, _, maximum = write_report(comparisons, status)
    print(f"Mixture stage {status}: {counts}; max abs error="
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
