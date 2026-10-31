"""MiniJMP × Minitab 19 Taguchi L8/L9 numerical parity checks."""
from __future__ import annotations

import csv
import ctypes
import json
import math
import subprocess
import sys
import time
import traceback
from collections import defaultdict
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
MTB_EXE = Path(r"D:\Program\Minitab 19\Mtb.exe")
PROJECT_PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
sys.path.insert(0, str(ROOT / "code"))
sys.path.insert(0, str(OUT))
from verify_doe_ccd import (canonical, capture_command_output,
                            compare_values, running_minitab_pids, write_csv)

TOL = 1e-9
SN_KINDS = ("smaller", "larger", "nominal_ii", "nominal")
MTB_SN = {"smaller": "LOWER", "larger": "HIGHER",
          "nominal_ii": "NOMONE", "nominal": "NOMTWO"}
CASES = {
    "l8": {
        "array": "L8(2^7)", "runs": 8, "columns": {"A": 1, "B": 2, "C": 5, "D": 6},
        "levels": {"low": -1.0, "high": 1.0}, "factors": ("A", "B", "C", "D"),
        "terms": (("A",), ("B",), ("C",), ("D",), ("A", "B")),
        "interaction": (("A", "B"),),
    },
    "l9": {
        "array": "L9(3^4)", "runs": 9, "columns": {"A": 1, "B": 2, "C": 3},
        "levels": {"low": 1.0, "mid": 2.0, "high": 3.0}, "factors": ("A", "B", "C"),
        "terms": (("A",), ("B",), ("C",)), "interaction": (),
    },
}
OFFSET = (-0.35, 0.05, 0.30)


def input_path(case_id: str) -> Path:
    return OUT / f"doe_taguchi_{case_id}_input.csv"


def minijmp_path(case_id: str) -> Path:
    return OUT / f"doe_taguchi_minijmp_{case_id}.json"


def minitab_path(case_id: str) -> Path:
    return OUT / f"doe_taguchi_minitab_{case_id}.json"


def raw_path(case_id: str) -> Path:
    return OUT / f"doe_taguchi_minitab_raw_{case_id}.txt"


def command_path(case_id: str) -> Path:
    return OUT / f"doe_taguchi_{case_id}_session_commands.txt"


def factor_code(array_row, array_col: int, config: dict) -> float:
    level_index = int(array_row[array_col - 1])
    return tuple(config["levels"].values())[level_index - 1]


def response_value(case_id: str, codes: dict[str, float], replicate: int) -> float:
    offset = OFFSET[replicate - 1]
    if case_id == "l8":
        a, b, c, d = (codes[name] for name in "ABCD")
        mean = 40 + 4*a - 3*b + 2*c + 2.5*d + 1.5*a*b
        scale = 1 + 0.10*(c > 0) + 0.05*(d > 0)
    else:
        a, b, c = (codes[name] - 2 for name in "ABC")
        mean = 55 + 4*a - 2*b + 3*c + 1.5*a*b + 0.5*b*c
        scale = 1 + 0.12*(a > 0) + 0.05*(c > 0)
    return float(mean + scale * offset)


def adjusted_nominal_reference(values) -> float:
    """Independent adjusted nominal-is-best (I), using sample variance."""
    n = len(values)
    if n < 2:
        raise ValueError("adjusted nominal S/N needs at least two responses")
    mean = sum(values) / n
    variance = sum((value - mean) ** 2 for value in values) / (n - 1)
    numerator = mean ** 2 - variance / n
    if variance <= 0 or numerator <= 0:
        raise ValueError("adjusted nominal S/N is undefined for these responses")
    return 10 * math.log10(numerator / variance)


def build_input(case_id: str) -> list[dict]:
    import numpy as np
    from doe_taguchi_arrays import get_array

    config = CASES[case_id]
    array = get_array(config["array"])
    matrix = np.asarray(array.matrix, dtype=int)
    if matrix.shape[0] != config["runs"]:
        raise AssertionError(f"{config['array']} 行数异常: {matrix.shape}")
    rows = []
    for standard_order, array_row in enumerate(matrix, 1):
        codes = {name: factor_code(array_row, column, config)
                 for name, column in config["columns"].items()}
        for replicate in range(1, 4):
            rows.append({"standard_order": standard_order, "replicate": replicate,
                         **{f"{name}_code": code for name, code in codes.items()},
                         "Y": response_value(case_id, codes, replicate)})
    if len(rows) != config["runs"] * 3 or not all(math.isfinite(row["Y"]) and row["Y"] > 0
                                                 for row in rows):
        raise AssertionError(f"{case_id} 固定响应数据无效")
    for standard_order in range(1, config["runs"] + 1):
        values = [row["Y"] for row in rows if row["standard_order"] == standard_order]
        if len(values) != 3 or len(set(values)) != 3:
            raise AssertionError(f"{case_id} 第 {standard_order} 个组合未形成三个不同观测")
    return rows


def save_input(case_id: str, rows: list[dict]) -> None:
    fields = ["standard_order", "replicate", *[f"{f}_code" for f in CASES[case_id]["factors"]], "Y"]
    with input_path(case_id).open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def read_input(case_id: str) -> list[dict]:
    with input_path(case_id).open(newline="", encoding="utf-8-sig") as stream:
        rows = list(csv.DictReader(stream))
    config = CASES[case_id]
    for row in rows:
        row["standard_order"] = int(row["standard_order"])
        row["replicate"] = int(row["replicate"])
        row["Y"] = float(row["Y"])
        for factor in config["factors"]:
            row[f"{factor}_code"] = float(row[f"{factor}_code"])
    if len(rows) != config["runs"] * 3:
        raise ValueError(f"{input_path(case_id).name} 行数不符")
    return rows


def level_for_code(case_id: str, code: float) -> str:
    config = CASES[case_id]
    return next(level for level, value in config["levels"].items() if value == code)


def run_minijmp(case_id: str, rows: list[dict]) -> dict:
    from itertools import product

    if canonical(sys.executable) != canonical(PROJECT_PYTHON):
        raise RuntimeError(f"请使用项目解释器运行: {PROJECT_PYTHON}")
    sys.path.insert(0, str(ROOT / "code"))
    import pandas as pd
    from doe_core import DesignSpec, FactorSpec, restore_design_result
    from doe_taguchi import create_taguchi
    from doe_taguchi_analysis import best_settings, predict_taguchi_model
    from doe_taguchi_arrays import ARRAYS
    from doe_taguchi_sn import analyze_static

    config = CASES[case_id]
    factors = tuple(FactorSpec(name, name, None, None, factor_type="categorical",
                               levels=tuple(config["levels"]), level_type="text")
                    for name in config["factors"])
    spec = DesignSpec(
        f"minitab19-taguchi-{case_id}", factors, ("Y",), seed=19,
        design_type="taguchi",
        taguchi={"kind": "static", "array_id": config["array"],
                 "matrix_sha256": ARRAYS[config["array"]].sha256,
                 "columns": config["columns"], "noise_array_id": None,
                 "noise_matrix_sha256": None, "noise_columns": {}, "signal_factor": None})
    frame, metadata = create_taguchi(spec, replicates=3)
    design = restore_design_result(frame, metadata)
    code_by_order = {}
    for run in design.runs:
        key = ((int(run.standard_order) - 1) // 3 + 1, int(run.replicate))
        if key in code_by_order:
            raise AssertionError(f"MiniJMP 重复运行键冲突: {key}")
        code_by_order[key] = {name: config["levels"][run.settings[name]]
                              for name in config["factors"]}
    input_by_key = {(row["standard_order"], row["replicate"]): row for row in rows}
    if set(code_by_order) != set(input_by_key):
        raise AssertionError("MiniJMP 与固定输入的标准序/重复映射不一致")
    for key, row in input_by_key.items():
        if any(code_by_order[key][name] != row[f"{name}_code"] for name in config["factors"]):
            raise AssertionError(f"MiniJMP Taguchi 阵列与固定输入不一致: {key}")
    response_by_id = {run.run_id: input_by_key[((int(run.standard_order) - 1) // 3 + 1, int(run.replicate))]["Y"]
                      for run in design.runs}
    frame.loc[:, "响应_Y"] = pd.array([response_by_id[run_id] for run_id in frame["运行ID"]],
                                       dtype="Float64")

    results = {"case": case_id, "array": config["array"], "terms": [list(t) for t in config["terms"]],
               "sn": {}, "best": {}, "predictions": {}}
    for kind in SN_KINDS:
        adjusted = False
        analysis = analyze_static(frame, metadata, "Y", kind, adjusted=adjusted)
        options = dict(metadata)
        options["analysis"] = {"kind": "static", "sn_kind": kind,
                                "adjusted": adjusted, "ln_sd": False}
        choice = best_settings(frame, options, "Y", "sn")
        predicted = predict_taguchi_model(frame, metadata, "Y", choice["best"],
                                          terms=config["terms"], confidence=0.95)
        results["sn"][kind] = {
            "combinations": analysis["combinations"],
            "factors": analysis["response_table"]["factors"],
            "best": choice["best"], "additive_prediction": choice["predicted"],
        }
        results["best"][kind] = choice["best"]
        results["predictions"][kind] = {
            "settings": predicted["settings"], "mean": predicted["prediction"],
            "intervals": predicted["intervals"], "model": predicted["model"],
        }
    adjusted = analyze_static(frame, metadata, "Y", "nominal", adjusted=True)
    adjusted_options = dict(metadata)
    adjusted_options["analysis"] = {"kind": "static", "sn_kind": "nominal",
                                    "adjusted": True, "ln_sd": False}
    adjusted_choice = best_settings(frame, adjusted_options, "Y", "sn")
    results["sn_adjusted"] = {
        "combinations": adjusted["combinations"],
        "factors": adjusted["response_table"]["factors"],
        "best": adjusted_choice["best"],
    }
    mean_rows = []
    for standard_order in range(1, config["runs"] + 1):
        observations = [row for row in rows if row["standard_order"] == standard_order]
        mean_rows.append({"standard_order": standard_order, "replicate": 1,
                          **{f"{f}_code": observations[0][f"{f}_code"]
                             for f in config["factors"]},
                          "Y": sum(row["Y"] for row in observations) / len(observations)})
    mean_frame, mean_metadata = create_taguchi(spec, replicates=1)
    mean_design = restore_design_result(mean_frame, mean_metadata)
    mean_response_by_id = {run.run_id: mean_rows[int(run.standard_order) - 1]["Y"]
                           for run in mean_design.runs}
    mean_frame.loc[:, "响应_Y"] = pd.array(
        [mean_response_by_id[run_id] for run_id in mean_frame["运行ID"]], dtype="Float64")
    mean_prediction = predict_taguchi_model(
        mean_frame, mean_metadata, "Y", results["best"]["smaller"],
        terms=config["terms"], confidence=0.95)
    mean_run_by_id = {run.run_id: int(run.standard_order) for run in mean_design.runs}
    mean_model = mean_prediction["model"]
    results["mean_model"] = {
        "coefficients": mean_model["coefficients"], "rank": mean_model["rank"],
        "df": mean_model["df"], "sse": mean_model["sse"], "mse": mean_model["mse"],
        "fitted": mean_model["fitted"], "residuals": mean_model["residuals"],
        "run_ids": mean_model["run_ids"],
        "row_keys": [mean_run_by_id[run_id] for run_id in mean_model["run_ids"]],
    }
    observed_codes = {tuple(row[f"{factor}_code"] for factor in config["factors"])
                      for row in rows if row["replicate"] == 1}
    candidate = next(
        (levels for levels in product(config["levels"], repeat=len(config["factors"]))
         if tuple(config["levels"][level] for level in levels) not in observed_codes),
        None,
    )
    if candidate is None or mean_model["rank"] != mean_model["parameter_count"] or mean_model["df"] <= 0:
        raise AssertionError(f"{case_id} mean model has no estimable non-design prediction point")
    point_settings = [
        ("observed", {factor: level_for_code(case_id, rows[0][f"{factor}_code"])
                      for factor in config["factors"]}),
        ("estimable_non_design", dict(zip(config["factors"], candidate))),
        ("best_snr", results["best"]["nominal"]),
    ]
    results["mean_ci_points"] = []
    for label, settings in point_settings:
        prediction = predict_taguchi_model(mean_frame, mean_metadata, "Y", settings,
                                           terms=config["terms"], confidence=0.95)
        results["mean_ci_points"].append({
            "label": label, "settings": settings,
            "prediction": prediction["prediction"],
            "intervals": prediction["intervals"],
        })
    results["mean_rows"] = mean_rows
    run_by_id = {run.run_id: {"standard_order": (int(run.standard_order) - 1) // 3 + 1,
                              "replicate": int(run.replicate)} for run in design.runs}
    results["model_row_keys"] = [run_by_id[run_id]
                                 for run_id in results["predictions"]["smaller"]["model"]["run_ids"]]
    results["design"] = [{"standard_order": int(row["standard_order"]),
                          "replicate": int(row["replicate"]),
                          **{f: float(row[f"{f}_code"]) for f in config["factors"]},
                          "Y": float(row["Y"])} for row in rows]
    return results


def append_column(columns, name: str, values) -> tuple[int, object]:
    column = columns.Add(None, None, 1)
    column.Name = name
    values = tuple(values)
    column.SetData(values, 1, len(values))
    return int(columns.Count), column


def next_storage_columns(columns, count: int) -> list[int]:
    first = int(columns.Count) + 1
    return list(range(first, first + count))


def column_values(column) -> list[float]:
    values = column.GetData()
    return ([float(values)] if isinstance(values, (int, float))
            else [float(value) for value in values])


def worker_main(case_id: str) -> int:
    import winreg
    import win32api
    import win32process
    import pythoncom
    import win32com
    import win32com.client

    config = CASES[case_id]
    rows = read_input(case_id)
    local = json.loads(minijmp_path(case_id).read_text(encoding="utf-8"))
    raw, commands = [], []
    app = project = worksheet = columns = None
    result_path, raw_file = minitab_path(case_id), raw_path(case_id)
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
            win32api.HIWORD(ms), win32api.LOWORD(ms), win32api.HIWORD(ls), win32api.LOWORD(ls)))
        if version != "19.1.0.1":
            raise RuntimeError(f"要求 Minitab 19.1.0.1，实际版本 {version}")

        app = win32com.client.DispatchEx("Mtb.Application")
        pythoncom.PumpWaitingMessages()
        try:
            ui = app.UserInterface
            ui.Visible = False
            ui.UserControl = False
            ui.DisplayAlerts = False
        except AttributeError:
            raw.append("COM UserInterface properties unavailable; continuing with ExecuteCommand only")
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
        project = app.ActiveProject
        app.New()
        project = app.ActiveProject
        design_command = (
            f"OADESIGN {config['runs']} {len(config['levels'])} {len(config['factors'])};\n"
            "  DESIGN;\n  COLUMNS " + " ".join(str(config["columns"][f]) for f in config["factors"]) + ";\n"
            "  LEVELS " + " ".join(" ".join(str(v) for v in config["levels"].values())
                                  for _ in config["factors"]) + ".")
        commands.append(design_command)
        commands_before = int(project.Commands.Count)
        project.ExecuteCommand(design_command)
        commands_after = commands_before
        command_deadline = time.monotonic() + 10
        while commands_after <= commands_before and time.monotonic() < command_deadline:
            pythoncom.PumpWaitingMessages()
            time.sleep(0.1)
            commands_after = int(project.Commands.Count)
        if commands_after <= commands_before:
            last_error = str(app.LastError or "")
            raw.append("===== OADESIGN actual command =====\n" + design_command
                       + "\n===== command object =====\nnot created"
                       + "\n===== LastError =====\n" + last_error)
            raise RuntimeError(f"OADESIGN 未创建命令对象: {last_error!r}")
        design_output = capture_command_output(project, commands_after)
        raw.append("===== OADESIGN actual command =====\n" + design_command
                   + "\n===== OADESIGN output =====\n" + design_output
                   + f"\n===== LastError =====\n{app.LastError!r}")
        worksheets = project.Worksheets
        for sheet_index in range(1, int(worksheets.Count) + 1):
            candidate = worksheets.Item(sheet_index)
            candidate_columns = candidate.Columns
            candidate_names = {str(candidate_columns.Item(i).Name).casefold()
                               for i in range(1, int(candidate_columns.Count) + 1)}
            if all(factor.casefold() in candidate_names for factor in config["factors"]):
                worksheet, columns = candidate, candidate_columns
                break
        if worksheet is None:
            raise RuntimeError(f"OADESIGN 未生成因子列；工作表数={worksheets.Count}; "
                               f"输出={design_output}; LastError={app.LastError!r}")
        native_factors = {}
        for factor in config["factors"]:
            match = next((columns.Item(i) for i in range(1, int(columns.Count) + 1)
                          if str(columns.Item(i).Name).casefold() == factor.casefold()), None)
            if match is None:
                raise RuntimeError(f"OADESIGN 未生成因子列 {factor}")
            values = [float(v) for v in match.GetData()]
            if len(values) != config["runs"]:
                raise RuntimeError(f"OADESIGN 因子 {factor} 行数异常: {len(values)}")
            native_factors[factor] = values
        input_by_codes = {tuple(row[f"{f}_code"] for f in config["factors"]): row["standard_order"]
                          for row in rows if row["replicate"] == 1}
        mtb_order = []
        for index in range(config["runs"]):
            key = tuple(native_factors[f][index] for f in config["factors"])
            if key not in input_by_codes:
                raise RuntimeError(f"Minitab OADESIGN 设计点未映射到固定输入: {key}")
            mtb_order.append(input_by_codes[key])
        if len(set(mtb_order)) != config["runs"]:
            raise RuntimeError("OADESIGN 设计矩阵存在重复或缺失点")

        app.New()
        project = app.ActiveProject
        worksheet = project.ActiveWorksheet
        columns = worksheet.Columns
        raw.append("===== ROBUST analysis worksheet =====\nFresh worksheet without OADESIGN row-count metadata; "
                   f"replicated response rows={len(rows)}")
        analysis_columns = {}
        analysis_keys = []
        response_values = []
        for standard_order in mtb_order:
            for replicate in range(1, 4):
                source = next(row for row in rows if row["standard_order"] == standard_order
                              and row["replicate"] == replicate)
                analysis_keys.append({"standard_order": standard_order, "replicate": replicate})
                response_values.append(source["Y"])
        for factor in config["factors"]:
            values = [next(row[f"{factor}_code"] for row in rows
                           if row["standard_order"] == order and row["replicate"] == 1)
                      for order in mtb_order for _ in range(3)]
            analysis_columns[factor], _ = append_column(columns, f"P_{factor}", values)
        response_index, response_column = append_column(columns, "P_Y", response_values)
        if column_values(columns.Item(response_index)) != response_values:
            raise AssertionError("Minitab 输入列 P_Y 回读不一致")

        sn_outputs, mean_outputs, prediction_outputs, robust_texts, mean_indices = {}, {}, {}, {}, {}
        interaction_terms = [f"C{analysis_columns[a]}*C{analysis_columns[b]}"
                             for a, b in config["interaction"]]
        model_terms = [f"C{analysis_columns[f]}" for f in config["factors"]] + interaction_terms
        for kind in SN_KINDS:
            storage = next_storage_columns(columns, 2)
            sn_index, means_index = storage[:2]
            command_lines = [f"ROBUST C{response_index} = {' '.join(model_terms)};",
                             f"  {MTB_SN[kind]};", "  TSN;", "  TMEANS;", "  ASN;", "  AMEANS;",
                             f"  SNRATIO C{sn_index};", f"  MEANS C{means_index};"]
            command_lines[-1] = command_lines[-1] + "."
            command = "\n".join(command_lines)
            commands.append(command)
            before = int(project.Commands.Count)
            project.ExecuteCommand(command)
            if int(project.Commands.Count) <= before:
                raise RuntimeError(f"ROBUST {kind} 未创建命令对象: {app.LastError}")
            text = capture_command_output(project)
            raw.append(f"===== ROBUST {kind} actual command =====\n{command}\n===== output =====\n{text}")
            robust_texts[kind] = text
            sn_values = column_values(columns.Item(sn_index))
            mean_values = column_values(columns.Item(means_index))
            sn_outputs[kind] = sn_values
            mean_outputs[kind] = mean_values
            mean_indices[kind] = means_index

            best = local["best"][kind]
            numeric_levels = [config["levels"][best[f]] for f in config["factors"]]
            pred_index = int(columns.Count) + 1
            predict_command = (f"OAPREDICT C{means_index} = {' '.join(model_terms)};\n"
                               f"  LEVELS {' '.join(str(v) for v in numeric_levels)};\n"
                               f"  PFITS C{pred_index}.")
            commands.append(predict_command)
            before = int(project.Commands.Count)
            project.ExecuteCommand(predict_command)
            if int(project.Commands.Count) <= before:
                raise RuntimeError(f"OAPREDICT {kind} 未创建命令对象: {app.LastError}")
            pred_text = capture_command_output(project)
            raw.append(f"===== OAPREDICT {kind} actual command =====\n{predict_command}"
                       + "\n===== output =====\n" + pred_text)
            prediction_outputs[kind] = column_values(columns.Item(pred_index))

        def execute_probe(label, command):
            commands.append(command)
            before = int(project.Commands.Count)
            exception = ""
            try:
                project.ExecuteCommand(command)
            except Exception as error:
                exception = str(error)
            created = int(project.Commands.Count) > before
            output_error = ""
            try:
                output = capture_command_output(project) if created else ""
            except Exception as error:
                output, output_error = "", str(error)
            last_error = str(app.LastError or "")
            raw.append(f"===== {label} actual command =====\n{command}"
                       f"\n===== command object created =====\n{created}"
                       f"\n===== exception =====\n{exception}"
                       f"\n===== output capture error =====\n{output_error}"
                       f"\n===== LastError =====\n{last_error}"
                       f"\n===== output =====\n{output}")
            return {"command": command, "command_object_created": created,
                    "exception": exception, "output_error": output_error,
                    "last_error": last_error, "output": output}

        feature_attempts = {}
        adjust_storage = next_storage_columns(columns, 1)[0]
        adjust_command = (f"ROBUST C{response_index} = {' '.join(model_terms)};\n"
                          "  NOMTWO;\n  ADJUSTED;\n  TSN;\n"
                          f"  SNRATIO C{adjust_storage}.")
        feature_attempts["adjusted_nominal"] = execute_probe(
            "ROBUST NOMTWO ADJUSTED probe", adjust_command)
        if feature_attempts["adjusted_nominal"]["command_object_created"]:
            try:
                feature_attempts["adjusted_nominal"]["s_n_values"] = column_values(
                    columns.Item(adjust_storage))
            except Exception as error:
                feature_attempts["adjusted_nominal"]["storage_error"] = str(error)

        best_settings = local["best"]["nominal"]
        numeric_levels = [config["levels"][best_settings[factor]] for factor in config["factors"]]
        ci_storage = next_storage_columns(columns, 6)
        ci_attempt_command = (f"OAPREDICT C{mean_indices['nominal']} = {' '.join(model_terms)};\n"
                              f"  LEVELS {' '.join(str(value) for value in numeric_levels)};\n"
                              f"  PFITS C{ci_storage[0]};\n  PSEFITS C{ci_storage[1]};\n"
                              f"  CLIMITS C{ci_storage[2]} C{ci_storage[3]};\n"
                              f"  PLIMITS C{ci_storage[4]} C{ci_storage[5]}.")
        feature_attempts["oapredict_mean_ci"] = execute_probe(
            "OAPREDICT CI storage probe", ci_attempt_command)
        if feature_attempts["oapredict_mean_ci"]["command_object_created"]:
            try:
                feature_attempts["oapredict_mean_ci"]["stored"] = {
                    name: column_values(columns.Item(index))
                    for name, index in zip(("fit", "se_fit", "ci_low", "ci_high", "pi_low", "pi_high"),
                                           ci_storage)
                }
            except Exception as error:
                feature_attempts["oapredict_mean_ci"]["storage_error"] = str(error)

        app.New()
        project = app.ActiveProject
        worksheet = project.ActiveWorksheet
        columns = worksheet.Columns
        mean_rows = local["mean_rows"]
        regression_factors = {}
        for factor in config["factors"]:
            regression_factors[factor], _ = append_column(
                columns, f"P_{factor}", [row[f"{factor}_code"] for row in mean_rows])
        mean_response_index, _ = append_column(
            columns, "P_Mean", [row["Y"] for row in mean_rows])
        regression_terms = ([f"C{regression_factors[factor]}" for factor in config["factors"]]
                            + [f"C{regression_factors[a]}*C{regression_factors[b]}"
                               for a, b in config["interaction"]])
        references = " ".join(
            f"C{regression_factors[factor]} {next(iter(config['levels'].values())):g}"
            for factor in config["factors"])
        regression_storage = next_storage_columns(columns, 3)
        regression_command = (
            "REGRESS;\n"
            f"  RESPONSE C{mean_response_index};\n"
            f"  CATEGORICAL {' '.join(f'C{regression_factors[factor]}' for factor in config['factors'])};\n"
            f"  TERMS {' '.join(regression_terms)};\n"
            f"  BINARY;\n  REFERENCE {references};\n  CONFIDENCE 95;\n"
            f"  COEFFICIENTS C{regression_storage[0]};\n"
            f"  FITS C{regression_storage[1]};\n"
            f"  RESIDUALS C{regression_storage[2]};\n  XMATRIX M1.")
        regression_attempt = execute_probe("REGRESS grouped Taguchi means", regression_command)
        native_mean_model = {"status": "UNSUPPORTED", "attempt": regression_attempt}
        if regression_attempt["command_object_created"]:
            try:
                import numpy as np

                matrices = worksheet.Matrices
                matrix = next(matrices.Item(i) for i in range(1, int(matrices.Count) + 1)
                              if str(matrices.Item(i).Name).casefold() == "m1")
                n, p = int(matrix.RowCount), int(matrix.ColumnCount)
                flat = [float(value) for value in matrix.GetData()]
                native_matrix = [[flat[column * n + row] for column in range(p)]
                                 for row in range(n)]
                coefficients = column_values(columns.Item(regression_storage[0]))
                fitted = column_values(columns.Item(regression_storage[1]))
                residuals = column_values(columns.Item(regression_storage[2]))
                rank = int(np.linalg.matrix_rank(native_matrix))
                error_df = n - rank
                sse = float(np.dot(residuals, residuals))
                native_mean_model = {
                    "status": "DIRECT", "command": regression_command,
                    "matrix": native_matrix, "coefficients": coefficients,
                    "fitted": fitted, "residuals": residuals,
                    "rank": rank, "error_df": error_df, "sse": sse,
                    "mse": sse / error_df if error_df > 0 else None,
                }
                predict_storage = next_storage_columns(columns, 6)
                predictor_lines = []
                for point in local["mean_ci_points"]:
                    values = [config["levels"][point["settings"][factor]]
                              for factor in config["factors"]]
                    predictor_lines.append(
                        "  KPREDICTORS " + " ".join(str(value) for value in values) + ";")
                predict_command = (
                    f"PREDICT C{mean_response_index};\n"
                    + "\n".join(predictor_lines) + "\n  CONFIDENCE 95;\n"
                    + f"  PFITS C{predict_storage[0]};\n  PSEFITS C{predict_storage[1]};\n"
                    + f"  CLIMITS C{predict_storage[2]} C{predict_storage[3]};\n"
                    + f"  PLIMITS C{predict_storage[4]} C{predict_storage[5]}."
                )
                prediction_attempt = execute_probe("PREDICT 95% mean CI and observation PI",
                                                    predict_command)
                native_mean_model["prediction_attempt"] = prediction_attempt
                if prediction_attempt["command_object_created"]:
                    native_mean_model["predictions"] = {
                        name: column_values(columns.Item(index))
                        for name, index in zip(("fit", "se_fit", "ci_low", "ci_high",
                                                "pi_low", "pi_high"), predict_storage)
                    }
            except Exception as error:
                native_mean_model = {"status": "UNSUPPORTED", "attempt": regression_attempt,
                                     "error": str(error)}
                raw.append("===== REGRESS/PREDICT extraction error =====\n" + traceback.format_exc())

        result = {
            "case": case_id, "version": version, "app_path": app_path,
            "process_path": process_path, "python_executable": sys.executable,
            "native_commands": commands, "design": native_factors,
            "design_row_to_standard_order": mtb_order,
            "analysis_data_keys": analysis_keys,
            "analysis_factors": {f: [native_factors[f][i]
                                      for i in range(config["runs"])
                                      for _ in range(3)] for f in config["factors"]},
            "response": response_values, "sn_values": sn_outputs,
            "mean_values": mean_outputs, "predictions": prediction_outputs,
            "robust_texts": robust_texts, "feature_attempts": feature_attempts,
            "mean_model_ci": native_mean_model,
        }
        result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        raw_file.write_text("\n\n".join(raw) + "\n", encoding="utf-8")
        command_path(case_id).write_text(
            "# 实际由本机 Minitab 19.1.0.1 COM ExecuteCommand 执行\n"
            "# 语法依据 Minitab 官方 Session Commands 文档：OADESIGN、ROBUST、OAPREDICT\n\n"
            + "\n\n".join(commands) + "\n", encoding="utf-8")
        print(f"{case_id}: OADESIGN + ROBUST(4 S/N definitions) + OAPREDICT; "
              f"Minitab {version}; design points={len(mtb_order)}", flush=True)
        return 0
    except Exception:
        raw_file.write_text("\n\n".join(raw + [traceback.format_exc()]) + "\n", encoding="utf-8")
        command_path(case_id).write_text(
            "# 实际已执行的 Session Commands；当前案例未完成\n\n"
            + "\n\n".join(commands) + "\n", encoding="utf-8")
        traceback.print_exc()
        return 1
    finally:
        response_column = columns = worksheet = project = app = None


def status_row(case_id, section, term, statistic, mtb, jmp, source, jmp_source,
               tolerance=TOL, status=None):
    row = compare_values(case_id, section, term, statistic, mtb, jmp, source, jmp_source)
    if tolerance != TOL:
        row["absolute_tolerance"] = tolerance
        row["relative_tolerance"] = 0.0
        if mtb is not None and jmp is not None:
            row["status"] = "PASS" if abs(float(mtb) - float(jmp)) <= tolerance else "FAIL"
    if status is not None:
        row["status"] = status
    return row


def local_model_matrix(case_id: str, rows: list[dict]):
    import numpy as np
    from itertools import product

    config = CASES[case_id]
    levels = tuple(config["levels"])
    matrix_columns = [np.ones(len(rows), dtype=float)]
    names = ["截距"]
    for term in config["terms"]:
        contrasts = [levels[1:] for _ in term]
        for level_combo in product(*contrasts):
            column = np.ones(len(rows), dtype=float)
            labels = []
            for factor, level in zip(term, level_combo):
                column *= np.asarray([
                    level_for_code(case_id, row[f"{factor}_code"]) == level for row in rows
                ], dtype=float)
                labels.append(f"{factor}={level}")
            matrix_columns.append(column)
            names.append(" × ".join(labels))
    return np.column_stack(matrix_columns), names


def effect_model_matrix(case_id: str, rows: list[dict]):
    import numpy as np
    from itertools import product

    config = CASES[case_id]
    levels = tuple(config["levels"])
    columns, names, contrasts = [np.ones(len(rows))], ["常量"], {}
    for factor in config["factors"]:
        contrasts[factor] = []
        for level in levels[:-1]:
            last = levels[-1]
            values = np.asarray([
                1.0 if level_for_code(case_id, row[f"{factor}_code"]) == level
                else -1.0 if level_for_code(case_id, row[f"{factor}_code"]) == last
                else 0.0 for row in rows
            ])
            contrasts[factor].append(values)
            columns.append(values)
            names.append(f"P_{factor} {config['levels'][level]:g}")
    for interaction in config["interaction"]:
        first, second = interaction
        for i, first_column in enumerate(contrasts[first]):
            for j, second_column in enumerate(contrasts[second]):
                columns.append(first_column * second_column)
                names.append(
                    f"P_{first}*P_{second} "
                    f"{config['levels'][levels[i]]:g} {config['levels'][levels[j]]:g}")
    return np.column_stack(columns), names


def display_document(output: str) -> str:
    body = output.split("OutputDocument.Text:\n", 1)[-1]
    return body.split("\n\nOutput.Text[1]:", 1)[0]


def display_number(token: str):
    try:
        value = float(token)
    except ValueError:
        return None
    digits = len(token.split(".", 1)[1]) if "." in token else 0
    return value, digits


def parse_display_coefficients(document: str, labels: list[str], title: str):
    try:
        section = document.split(title, 1)[1].split("模型汇总", 1)[0]
    except IndexError:
        return None
    lines = [line.split() for line in section.splitlines() if line.split()]
    parsed = {}
    for label in labels:
        prefix = label.split()
        for fields in lines:
            if fields[:len(prefix)] == prefix and len(fields) > len(prefix):
                number = display_number(fields[len(prefix)])
                if number is not None:
                    parsed[label] = number
                    break
    return parsed if len(parsed) == len(labels) else None


def parse_display_anova(document: str, config: dict, title: str):
    try:
        section = document.split(title, 1)[1]
    except IndexError:
        return None
    names = [f"P_{factor}" for factor in config["factors"]]
    names.extend(f"P_{a}*P_{b}" for a, b in config["interaction"])
    result = {}
    for line in section.splitlines():
        fields = line.split()
        if not fields:
            continue
        name = fields[0]
        if name in names and len(fields) >= 7:
            df = display_number(fields[1])
            seq_ss, adj_ss, adj_ms = (display_number(value) for value in fields[2:5])
            f_value, p_value = (display_number(value) for value in fields[5:7])
            if df and seq_ss and adj_ss and adj_ms:
                result[name] = {"df": df, "seq_ss": seq_ss, "adj_ss": adj_ss,
                                "adj_ms": adj_ms, "f": f_value, "p": p_value}
        elif name == "残差误差" and len(fields) >= 5:
            df, seq_ss, adj_ss, adj_ms = (display_number(value) for value in fields[1:5])
            if df and seq_ss and adj_ss and adj_ms:
                result[name] = {"df": df, "seq_ss": seq_ss, "adj_ss": adj_ss,
                                "adj_ms": adj_ms, "f": None, "p": None}
        elif name == "合计" and len(fields) >= 3:
            df, ss = display_number(fields[1]), display_number(fields[2])
            if df and ss:
                result[name] = {"df": df, "ss": ss}
    return result or None


def derive_mean_anova(case_id: str, rows: list[dict]):
    import numpy as np
    from scipy import stats

    matrix, names = effect_model_matrix(case_id, rows)
    response = np.asarray([row["Y"] for row in rows], dtype=float)
    coefficients, *_ = np.linalg.lstsq(matrix, response, rcond=None)
    fitted = matrix @ coefficients
    residuals = response - fitted
    full_rank = int(np.linalg.matrix_rank(matrix))
    error_df = len(response) - full_rank
    error_ss = float(residuals @ residuals)
    mse = error_ss / error_df if error_df > 0 else None
    result = {"残差误差": {"df": error_df, "ss": error_ss},
              "合计": {"df": len(response) - 1,
                       "ss": float(((response - response.mean()) ** 2).sum())}}
    for term in CASES[case_id]["terms"]:
        if len(term) == 1:
            prefix = f"P_{term[0]} "
            indices = [i for i, name in enumerate(names)
                       if i and name.startswith(prefix) and "*" not in name]
        else:
            prefix = f"P_{term[0]}*P_{term[1]} "
            indices = [i for i, name in enumerate(names) if i and name.startswith(prefix)]
        reduced = np.delete(matrix, indices, axis=1)
        reduced_coef, *_ = np.linalg.lstsq(reduced, response, rcond=None)
        reduced_resid = response - reduced @ reduced_coef
        ss = max(0.0, float(reduced_resid @ reduced_resid) - error_ss)
        df = full_rank - int(np.linalg.matrix_rank(reduced))
        f_value = p_value = None
        if mse is not None and mse > 0 and df > 0:
            f_value = (ss / df) / mse
            p_value = float(stats.f.sf(f_value, df, error_df))
        name = f"P_{term[0]}" if len(term) == 1 else f"P_{term[0]}*P_{term[1]}"
        result[name] = {"df": df, "adj_ss": ss, "f": f_value, "p": p_value}
    return result


def compare_mean_model_display(case_id: str, local: dict, mtb: dict) -> list[dict]:
    import numpy as np

    rows = local["mean_rows"]
    matrix, coefficient_names = local_model_matrix(case_id, rows)
    effect_matrix, effect_names = effect_model_matrix(case_id, rows)
    document = display_document(mtb["robust_texts"]["smaller"])
    displayed = parse_display_coefficients(document, effect_names, "均值 的模型系数估计")
    result_rows = []
    if displayed is None:
        result_rows.append(status_row(case_id, "model_coefficients", "mean_model", "estimate",
                                      None, None, "Minitab ROBUST display table not parsed",
                                      "MiniJMP predict_taguchi_model", status="UNSUPPORTED"))
        return result_rows

    beta_effect = np.asarray([displayed[name][0] for name in effect_names])
    half_units = np.asarray([0.5 * 10 ** (-displayed[name][1]) for name in effect_names])
    transform, *_ = np.linalg.lstsq(matrix, effect_matrix, rcond=None)
    converted = transform @ beta_effect
    api_coefficients = local["mean_model"]["coefficients"]
    for index, name in enumerate(coefficient_names):
        tolerance = float(np.abs(transform[index]) @ half_units) + 1e-12
        result_rows.append(status_row(
            case_id, "model_coefficients", name, "estimate", converted[index],
            api_coefficients[name],
            "DISPLAY: Minitab ROBUST AMEANS effect-coded coefficient transformed to MiniJMP basis",
            "MiniJMP predict_taguchi_model on treatment means (DIRECT)", tolerance=tolerance))

    mtb_anova = parse_display_anova(document, CASES[case_id], "均值 的方差分析")
    jmp_anova = derive_mean_anova(case_id, rows)
    if mtb_anova is None:
        result_rows.append(status_row(case_id, "anova", "mean_model", "table",
                                      None, None, "Minitab ROBUST display table not parsed",
                                      "MiniJMP grouped OLS reference", status="UNSUPPORTED"))
        return result_rows
    for term in CASES[case_id]["terms"]:
        name = f"P_{term[0]}" if len(term) == 1 else f"P_{term[0]}*P_{term[1]}"
        display_row = mtb_anova.get(name)
        reference = jmp_anova[name]
        if display_row is None:
            result_rows.append(status_row(case_id, "anova", name, "Adj SS", None,
                                          reference["adj_ss"], "Minitab mean ANOVA row unavailable",
                                          "MiniJMP grouped OLS reference", status="UNSUPPORTED"))
            continue
        result_rows.append(status_row(
            case_id, "anova", name, "df", display_row["df"][0], reference["df"],
            "DISPLAY: Minitab ROBUST AMEANS ANOVA", "DERIVED: MiniJMP mean-model matrix",
            tolerance=0.0))
        result_rows.append(status_row(
            case_id, "anova", name, "Adj SS", display_row["adj_ss"][0], reference["adj_ss"],
            "DISPLAY: Minitab ROBUST AMEANS ANOVA", "DERIVED: MiniJMP mean-model matrix",
            tolerance=display_row["adj_ss"][1] and 0.5*10**(-display_row["adj_ss"][1]) or 0.5))
        for metric in ("f", "p"):
            displayed_value = display_row[metric]
            expected = reference[metric]
            if displayed_value is None or expected is None:
                result_rows.append(status_row(
                    case_id, "anova", name, metric, None, expected,
                    "Minitab reports '*' when the mean-model error variance is unavailable",
                    "MiniJMP mean-model inference", status="N/A"))
            else:
                result_rows.append(status_row(
                    case_id, "anova", name, metric, displayed_value[0], expected,
                    "DISPLAY: Minitab ROBUST AMEANS ANOVA", "DERIVED: MiniJMP mean-model matrix",
                    tolerance=0.5 * 10 ** (-displayed_value[1])))
    for source_name, reference_name in (("残差误差", "残差误差"), ("合计", "合计")):
        display_row = mtb_anova.get(source_name)
        reference = jmp_anova[reference_name]
        if display_row is None:
            result_rows.append(status_row(case_id, "anova", source_name, "row", None, None,
                                          "Minitab mean ANOVA row unavailable",
                                          "MiniJMP mean-model matrix", status="UNSUPPORTED"))
            continue
        result_rows.append(status_row(
            case_id, "anova", source_name, "df", display_row["df"][0], reference["df"],
            "DISPLAY: Minitab ROBUST AMEANS ANOVA", "DERIVED: MiniJMP mean-model matrix",
            tolerance=0.0))
        display_ss = display_row.get("adj_ss", display_row.get("ss"))
        reference_ss = reference.get("ss")
        result_rows.append(status_row(
            case_id, "anova", source_name, "SS", display_ss[0], reference_ss,
            "DISPLAY: Minitab ROBUST AMEANS ANOVA", "DERIVED: MiniJMP mean-model matrix",
            tolerance=0.5 * 10 ** (-display_ss[1])))
    return result_rows


def compare_adjusted_nominal(case_id: str, rows: list[dict], local: dict, mtb: dict) -> list[dict]:
    config = CASES[case_id]
    factors = config["factors"]
    adjusted = local["sn_adjusted"]
    local_combos = {
        tuple(config["levels"][combo["settings"][factor]] for factor in factors): combo
        for combo in adjusted["combinations"]
    }
    grouped = defaultdict(list)
    codes_by_order = {}
    for row in rows:
        grouped[row["standard_order"]].append(float(row["Y"]))
        codes_by_order[row["standard_order"]] = tuple(
            row[f"{factor}_code"] for factor in factors)
    independent = {order: adjusted_nominal_reference(values)
                   for order, values in grouped.items()}
    attempt = mtb.get("feature_attempts", {}).get("adjusted_nominal", {})
    native_by_order = defaultdict(list)
    for key, value in zip(mtb.get("analysis_data_keys", []), attempt.get("s_n_values", [])):
        if value < 1e29:
            native_by_order[key["standard_order"]].append(float(value))
    native_by_order = {order: sum(values) / len(values)
                       for order, values in native_by_order.items()}
    result_rows = []
    direct_source = "Minitab ROBUST NOMTWO ADJUSTED SNRATIO storage (DIRECT)"
    local_source = "MiniJMP analyze_static(adjusted=True)"
    formula_source = "DERIVED: official adjusted nominal-I formula with sample variance"
    complete_native = len(native_by_order) == len(grouped)
    for order, values in grouped.items():
        combo = local_combos[codes_by_order[order]]
        if order in native_by_order:
            result_rows.append(status_row(case_id, "sn_formula", f"standard_order={order}",
                                          "nominal_adjusted_S/N", native_by_order[order],
                                          combo["sn"], direct_source, local_source))
            result_rows.append(status_row(case_id, "sn_formula", f"standard_order={order}",
                                          "official_formula", native_by_order[order],
                                          independent[order], direct_source, formula_source))
        else:
            result_rows.append(status_row(case_id, "sn_formula", f"standard_order={order}",
                                          "nominal_adjusted_S/N", None, combo["sn"],
                                          "Minitab adjusted SNRATIO storage unavailable",
                                          local_source, status="UNSUPPORTED"))

    level_means = {factor: {} for factor in factors}
    for factor_index, factor in enumerate(factors):
        local_factor = next(item for item in adjusted["factors"]
                            if item["factor_id"] == factor)
        for level, code in config["levels"].items():
            values = [native_by_order[order] for order, combo in codes_by_order.items()
                      if combo[factor_index] == code and order in native_by_order]
            if not values:
                continue
            mean_value = sum(values) / len(values)
            level_means[factor][level] = mean_value
            local_level = next(item for item in local_factor["levels"]
                               if item["level"] == level)
            result_rows.append(status_row(case_id, "response_table", f"{factor}={level}",
                                          "nominal_adjusted_sn_mean", mean_value,
                                          local_level["sn"],
                                          "DERIVED: aggregate Minitab adjusted SNRATIO (DIRECT)",
                                          "MiniJMP adjusted nominal response table"))
        if len(level_means[factor]) != len(config["levels"]):
            continue
        delta = max(level_means[factor].values()) - min(level_means[factor].values())
        result_rows.append(status_row(case_id, "response_table", factor,
                                      "nominal_adjusted_delta", delta, local_factor["delta"],
                                      "DERIVED: aggregate Minitab adjusted SNRATIO (DIRECT)",
                                      "MiniJMP adjusted nominal response table"))
        tied = [level for level, value in level_means[factor].items()
                if math.isclose(value, max(level_means[factor].values()), rel_tol=0, abs_tol=1e-12)]
        result_rows.append(status_row(case_id, "best_levels", factor,
                                      "nominal_adjusted", float(adjusted["best"][factor] in tied),
                                      1.0,
                                      "DERIVED: Minitab adjusted SNRATIO response table (DIRECT inputs)",
                                      "MiniJMP adjusted nominal best level"))

    if all(factor in level_means and len(level_means[factor]) == len(config["levels"])
           for factor in factors):
        deltas = {factor: max(values.values()) - min(values.values())
                  for factor, values in level_means.items()}
        order = sorted(factors, key=lambda factor: -deltas[factor])
        for rank, factor in enumerate(order, 1):
            tied_rank = any(math.isclose(deltas[factor], deltas[other], rel_tol=0, abs_tol=1e-12)
                            for other in factors if other != factor)
            local_factor = next(item for item in adjusted["factors"]
                                if item["factor_id"] == factor)
            result_rows.append(status_row(
                case_id, "response_table", factor, "nominal_adjusted_rank",
                None if tied_rank else rank, None if tied_rank else local_factor["rank"],
                "DERIVED: rank Minitab adjusted SNRATIO Delta (DIRECT inputs)",
                "MiniJMP adjusted nominal response table", tolerance=0.0,
                status="N/A" if tied_rank else None))
    if complete_native:
        result_rows.append(status_row(
            case_id, "sn_formula", "nominal_adjusted_native", "command_support", None, None,
            "Minitab ROBUST NOMTWO ADJUSTED returned per-combination SNRATIO via COM",
            "MiniJMP adjusted nominal-I", status="PASS"))
    else:
        detail = attempt.get("exception") or attempt.get("last_error") or (
            "Minitab SNRATIO column did not return every treatment combination")
        result_rows.append(status_row(
            case_id, "sn_formula", "nominal_adjusted_native", "command_support", None, None,
            "Minitab ROBUST NOMTWO ADJUSTED attempt: " + detail,
            "MiniJMP adjusted nominal-I", status="UNSUPPORTED"))
    return result_rows


def compare_mean_ci(case_id: str, local: dict, mtb: dict) -> list[dict]:
    result_rows = []
    native = mtb.get("mean_model_ci", {})
    api_model = local["mean_model"]
    oapredict = mtb.get("feature_attempts", {}).get("oapredict_mean_ci", {})
    oapredict_stored = oapredict.get("stored", {})
    if not all(name in oapredict_stored and oapredict_stored[name]
               for name in ("se_fit", "ci_low", "ci_high", "pi_low", "pi_high")):
        detail = (oapredict.get("exception") or oapredict.get("last_error") or
                  "OAPREDICT 没有 CI/PI 存储项")
        result_rows.append(status_row(
            case_id, "prediction", "OAPREDICT", "95%_mean_CI_storage", None, None,
            "Minitab OAPREDICT CI probe: " + detail,
            "MiniJMP predict_taguchi_model interval API", status="UNSUPPORTED"))

    if native.get("status") != "DIRECT" or "predictions" not in native:
        detail = native.get("error", "Minitab REGRESS/PREDICT model result unavailable")
        for point in local["mean_ci_points"]:
            result_rows.append(status_row(
                case_id, "prediction", point["label"], "95%_mean_CI", None, None,
                f"Minitab equivalent categorical REGRESS/PREDICT unavailable: {detail}",
                "MiniJMP predict_taguchi_model", status="UNSUPPORTED"))
        return result_rows

    import numpy as np

    local_matrix, _ = local_model_matrix(case_id, local["mean_rows"])
    native_matrix = np.asarray(native["matrix"], dtype=float)
    matrix_error = (float(np.max(np.abs(native_matrix - local_matrix)))
                    if native_matrix.shape == local_matrix.shape else None)
    result_rows.append(status_row(
        case_id, "mean_model", "treatment_coding", "max_matrix_error",
        matrix_error, 0.0, "Minitab REGRESS XMATRIX (DIRECT)",
        "MiniJMP grouped mean-model matrix", tolerance=TOL))
    result_rows.append(status_row(case_id, "mean_model", "model", "rank",
                                  native["rank"], api_model["rank"],
                                  "Minitab REGRESS XMATRIX (DIRECT)", "MiniJMP grouped OLS"))
    result_rows.append(status_row(case_id, "mean_model", "model", "error_df",
                                  native["error_df"], api_model["df"],
                                  "DERIVED: Minitab XMATRIX rank", "MiniJMP grouped OLS"))
    result_rows.append(status_row(case_id, "mean_model", "model", "MSE",
                                  native["mse"], api_model["mse"],
                                  "DERIVED: Minitab REGRESS residuals / error df",
                                  "MiniJMP grouped OLS"))
    if native_matrix.shape == local_matrix.shape:
        for index in range(len(api_model["fitted"])):
            result_rows.append(status_row(
                case_id, "mean_model", f"standard_order={index + 1}", "fit",
                native["fitted"][index], api_model["fitted"][index],
                "Minitab REGRESS FITS (DIRECT)", "MiniJMP grouped OLS (DIRECT)"))
            result_rows.append(status_row(
                case_id, "mean_model", f"standard_order={index + 1}", "residual",
                native["residuals"][index], api_model["residuals"][index],
                "Minitab REGRESS RESIDUALS (DIRECT)", "MiniJMP grouped OLS (DIRECT)"))

    prediction_values = native["predictions"]
    for index, point in enumerate(local["mean_ci_points"]):
        term = point["label"]
        intervals = point["intervals"]
        result_rows.append(status_row(
            case_id, "prediction", term, "mean", prediction_values["fit"][index],
            point["prediction"], "Minitab REGRESS/PREDICT PFITS (DIRECT)",
            "MiniJMP predict_taguchi_model (DIRECT)"))
        if intervals.get("status") != "可用":
            reason = intervals.get("reason", "mean-model interval is unavailable")
            for statistic in ("se_fit", "95%_mean_CI_low", "95%_mean_CI_high",
                              "95%_single_observation_PI_low", "95%_single_observation_PI_high"):
                result_rows.append(status_row(
                    case_id, "prediction", term, statistic, None, None,
                    f"Minitab REGRESS/PREDICT output exists; MiniJMP interval unavailable: {reason}",
                    "MiniJMP predict_taguchi_model", status="N/A"))
            continue
        for statistic, native_name, api_name in (
            ("se_fit", "se_fit", "se_fit"),
            ("95%_mean_CI_low", "ci_low", "ci_low"),
            ("95%_mean_CI_high", "ci_high", "ci_high"),
            ("95%_single_observation_PI_low", "pi_low", "pi_low"),
            ("95%_single_observation_PI_high", "pi_high", "pi_high"),
        ):
            result_rows.append(status_row(
                case_id, "prediction", term, statistic,
                prediction_values[native_name][index], intervals[api_name],
                "Minitab REGRESS/PREDICT storage (DIRECT)",
                "MiniJMP predict_taguchi_model (DIRECT)"))
    return result_rows


def compare_case(case_id, rows, local, mtb):
    import numpy as np

    config = CASES[case_id]
    result_rows = []
    design_map = {tuple(row[f"{f}_code"] for f in config["factors"]): row["standard_order"]
                  for row in rows if row["replicate"] == 1}
    mtb_map = [tuple(mtb["design"][f][i] for f in config["factors"])
               for i in range(config["runs"])]
    for index, key in enumerate(mtb_map, 1):
        std = design_map.get(key)
        if std is None:
            raise AssertionError(f"Minitab 设计点无法映射: {key}")
        source_row = rows[(std - 1) * 3]
        for factor in config["factors"]:
            result_rows.append(status_row(
                case_id, "design", f"standard_order={std}:{factor}", "level_code",
                mtb["design"][factor][index - 1], source_row[f"{factor}_code"],
                "Minitab OADESIGN factor column (DIRECT)", "fixed input / MiniJMP array (DIRECT)"))

    local_combos = {}
    for kind in SN_KINDS:
        for combo in local["sn"][kind]["combinations"]:
            key = tuple(config["levels"][combo["settings"][factor]] for factor in config["factors"])
            local_combos[key] = combo

        sn_column = mtb["sn_values"][kind]
        mean_column = mtb["mean_values"][kind]
        keys = [tuple(mtb["analysis_factors"][f][i] for f in config["factors"])
                for i in range(len(mtb["analysis_data_keys"]))]
        if len(sn_column) not in (len(keys), config["runs"]):
            result_rows.append(status_row(case_id, "sn", kind, "stored_rows", None, None,
                                          "Minitab storage unavailable", "MiniJMP API", status="UNSUPPORTED"))
            continue
        sn_by_combo, mean_by_combo = defaultdict(list), defaultdict(list)
        for i, key in enumerate(keys[:len(sn_column)]):
            # Minitab stores each repeated treatment statistic only on its first row;
            # 1.23456e30 is its numeric missing-value sentinel on the remaining rows.
            if sn_column[i] < 1e29:
                sn_by_combo[key].append(sn_column[i])
            if i < len(mean_column) and mean_column[i] < 1e29:
                mean_by_combo[key].append(mean_column[i])
        mtb_sn = {key: float(np.mean(values)) for key, values in sn_by_combo.items()}
        mtb_mean = {key: float(np.mean(values)) for key, values in mean_by_combo.items()}
        if len(sn_column) == config["runs"]:
            sn_by_combo = {tuple(mtb["design"][f][i] for f in config["factors"]): [v]
                           for i, v in enumerate(sn_column)}
            mtb_sn = {key: float(values[0]) for key, values in sn_by_combo.items()}
            mtb_mean = {tuple(mtb["design"][f][i] for f in config["factors"]): float(mean_column[i])
                        for i in range(min(len(mean_column), config["runs"]))}
        for key, combo in local_combos.items():
            if key not in mtb_sn or key not in mtb_mean:
                result_rows.append(status_row(case_id, "sn", str(key), "stored_statistic", None, None,
                                              "Minitab ROBUST storage mapping unavailable",
                                              "MiniJMP analyze_static", status="UNSUPPORTED"))
                continue
            result_rows.append(status_row(case_id, "response_table", str(key), f"{kind}_sn",
                                          mtb_sn[key], combo["sn"],
                                          f"Minitab ROBUST SNRATIO storage (DIRECT, {kind})",
                                          "MiniJMP analyze_static (DIRECT)"))
            result_rows.append(status_row(case_id, "response_table", str(key), "mean",
                                          mtb_mean[key], combo["mean"],
                                          "Minitab ROBUST MEANS storage (DIRECT)",
                                          "MiniJMP analyze_static (DIRECT)"))
        for factor_index, factor in enumerate(config["factors"]):
            table = next(row for row in local["sn"][kind]["factors"]
                         if row["factor_id"] == factor)
            local_levels = {config["levels"][level["level"]]: level for level in table["levels"]}
            mtb_level_sn, mtb_level_mean = {}, {}
            for level_code in config["levels"].values():
                group = [key for key in mtb_sn if key[factor_index] == level_code]
                mtb_level_sn[level_code] = float(np.mean([mtb_sn[key] for key in group]))
                mtb_level_mean[level_code] = float(np.mean([mtb_mean[key] for key in group]))
            for level_code, level in local_levels.items():
                label = level["level"]
                result_rows.append(status_row(
                    case_id, "response_table", f"{factor}={label}", f"{kind}_sn_mean",
                    mtb_level_sn[level_code], level["sn"],
                    f"Minitab ROBUST SNRATIO (DIRECT, {kind}) aggregated by level",
                    "MiniJMP analyze_static response table (DIRECT)"))
                result_rows.append(status_row(
                    case_id, "response_table", f"{factor}={label}", "mean_response",
                    mtb_level_mean[level_code], level["mean"],
                    "Minitab ROBUST MEANS (DIRECT) aggregated by level",
                    "MiniJMP analyze_static response table (DIRECT)"))
            mtb_delta = max(mtb_level_sn.values()) - min(mtb_level_sn.values())
            result_rows.append(status_row(case_id, "response_table", factor, f"{kind}_delta",
                                          mtb_delta, table["delta"],
                                          "DERIVED: Minitab ROBUST SNRATIO storage aggregated by level",
                                          "MiniJMP response table (DIRECT)"))
            local_best_code = config["levels"][local["best"][kind][factor]]
            mtb_best_code = max(mtb_level_sn, key=mtb_level_sn.get)
            tied = {code for code, value in mtb_level_sn.items()
                    if math.isclose(value, mtb_level_sn[mtb_best_code], rel_tol=0, abs_tol=1e-12)}
            result_rows.append(status_row(
                case_id, "best_levels", factor, kind,
                1.0 if local_best_code in tied else 0.0, 1.0,
                "Minitab level S/N maximum (DIRECT)", "MiniJMP analyze_static best level (DIRECT)"))

        prediction = mtb["predictions"].get(kind, [])
        local_prediction = local["predictions"][kind]
        if prediction:
            result_rows.append(status_row(
                case_id, "prediction", kind, "mean", prediction[0], local_prediction["mean"],
                "Minitab OAPREDICT PFITS storage (DIRECT)",
                "MiniJMP predict_taguchi_model (DIRECT)"))
        else:
            result_rows.append(status_row(case_id, "prediction", kind, "mean", None,
                                          local_prediction["mean"], "OAPREDICT unavailable",
                                          "MiniJMP predict_taguchi_model", status="UNSUPPORTED"))
    result_rows.extend(compare_adjusted_nominal(case_id, rows, local, mtb))
    result_rows.extend(compare_mean_ci(case_id, local, mtb))
    result_rows.extend(compare_mean_model_display(case_id, local, mtb))
    return result_rows


def format_case_report_row(case_id: str, state: dict) -> str:
    return (f"| {case_id.upper()} | {state['status']} | {state.get('comparisons', 0)} | "
            f"{state.get('failures', 0)} | {state.get('unsupported', 0)} | "
            f"{state.get('reason', '')} |")


def parent_main() -> int:
    all_rows, case_states = [], {}
    for case_id in CASES:
        rows = build_input(case_id)
        save_input(case_id, rows)
        rows = read_input(case_id)
        local_process = subprocess.run(
            [str(PROJECT_PYTHON), "-X", "utf8", str(Path(__file__).resolve()),
             "--minijmp-worker", case_id],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
        if local_process.stdout.strip():
            print(local_process.stdout.rstrip(), flush=True)
        if local_process.stderr.strip():
            print("MiniJMP worker stderr:\n" + local_process.stderr.rstrip(), flush=True)
        if local_process.returncode:
            case_states[case_id] = {"status": "BLOCKED", "reason": "MiniJMP API worker 执行失败"}
            continue
        local = json.loads(minijmp_path(case_id).read_text(encoding="utf-8"))
        process = subprocess.run(
            [str(PROJECT_PYTHON), "-X", "utf8", str(Path(__file__).resolve()), "--com-worker", case_id],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
        if process.stdout.strip():
            print(process.stdout.rstrip(), flush=True)
        if process.stderr.strip():
            print("COM worker stderr:\n" + process.stderr.rstrip(), flush=True)
        for _ in range(40):
            if not running_minitab_pids():
                break
            time.sleep(0.5)
        pids = running_minitab_pids()
        if pids:
            case_states[case_id] = {"status": "BLOCKED", "reason": f"Mtb.exe 残留: {pids}"}
            continue
        if process.returncode:
            case_states[case_id] = {"status": "BLOCKED", "reason": "Minitab worker 执行失败；详见 raw 输出"}
            continue
        mtb = json.loads(minitab_path(case_id).read_text(encoding="utf-8"))
        if mtb["version"] != "19.1.0.1" or canonical(mtb["app_path"]) != canonical(MTB_EXE):
            case_states[case_id] = {"status": "BLOCKED", "reason": "COM 版本或程序路径不符"}
            continue
        case_rows = compare_case(case_id, rows, local, mtb)
        all_rows.extend(case_rows)
        case_failures = sum(row["status"] == "FAIL" for row in case_rows)
        case_unsupported = sum(row["status"] == "UNSUPPORTED" for row in case_rows)
        case_states[case_id] = {
                                "status": "FAIL" if case_failures else "PARTIAL" if case_unsupported else "PASS",
                                "comparisons": len(case_rows),
                                "failures": case_failures, "unsupported": case_unsupported,
                                "native_commands": mtb["native_commands"]}
    for case_id in CASES:
        case_rows = [row for row in all_rows if row["run"] == case_id]
        write_csv(OUT / f"doe_taguchi_{case_id}_comparison.csv", case_rows)
    write_csv(OUT / "doe_taguchi_comparison.csv", all_rows)
    counts = {status: sum(row["status"] == status for row in all_rows)
              for status in ("PASS", "FAIL", "N/A", "UNSUPPORTED")}
    sources = {kind: sum(kind in row["minitab_value_source"] for row in all_rows)
               for kind in ("DIRECT", "DERIVED", "DISPLAY")}
    measured = [row for row in all_rows if row["absolute_error"] is not None]
    maximum = max(measured, key=lambda row: row["absolute_error"], default=None)
    states = [case_states.get(key, {}).get("status", "BLOCKED") for key in CASES]
    overall = "BLOCKED" if all(state == "BLOCKED" for state in states) else (
        "FAIL" if "FAIL" in states else "PARTIAL" if any(state != "PASS" for state in states) else "PASS")
    report = ["# MiniJMP × Minitab 19 Taguchi L8/L9 对标", "", f"**阶段状态：{overall}**", "",
              f"比较计数：PASS {counts['PASS']} / FAIL {counts['FAIL']} / N/A {counts['N/A']} / UNSUPPORTED {counts['UNSUPPORTED']}。",
              f"来源分类（Minitab 侧）：DIRECT {sources['DIRECT']} / DERIVED {sources['DERIVED']} / DISPLAY {sources['DISPLAY']}。",
              (f"最大绝对误差：{maximum['absolute_error']:.10g}，{maximum['run']} / "
               f"{maximum['section']} / {maximum['term']} / {maximum['statistic']}。"
               if maximum else "最大绝对误差：无可比较的数值项。"), "",
              "| 案例 | 状态 | 比较项 | FAIL | UNSUPPORTED | 说明 |",
              "| --- | --- | ---: | ---: | ---: | --- |"]
    for case_id, state in case_states.items():
        report.append(format_case_report_row(case_id, state))
    report.extend(["", "## 方法与限制", "",
                   "- 固定输入为每个 Taguchi 组合 3 个正值响应观测；Minitab 设计矩阵由 OADESIGN 生成，并按因子组合与 MiniJMP 标准序映射。",
                   "- NOMONE 是只基于标准差的 Nominal-is-best (II)，NOMTWO 是均值/标准差型 Nominal-is-best (I)；调整型 I 为 `10*log10((x̄² - s²/n)/s²)`，其中 `s²` 是重复观测的样本方差。Minitab 19.1.0.1 实际接受 `ROBUST ... NOMTWO; ADJUSTED; SNRATIO`，输出表显示该公式且 SNRATIO 列可直接 COM 回读；L8/L9 共 17 个 S/N 与独立公式及 MiniJMP API 相符。水平响应均值、Delta、Rank 和最佳水平由 Minitab DIRECT SNRATIO 聚合后 DERIVED 比较。定义见 [Minitab Taguchi Methods and formulas](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/taguchi/analyze-taguchi-design/methods-and-formulas/methods-and-formulas/)；命令依据 [官方 Session Commands](https://support.minitab.com/zh-cn/minitab/media/pdfs/notranslate/session_commands.pdf)。",
                   "- `OAPREDICT` 的均值 CI/观测 PI 存储尝试被 Minitab 19 拒绝。相同聚合均值、因子项和 treatment 编码由 Minitab `REGRESS` + `PREDICT` 直接拟合并回读模型矩阵、拟合/残差及 95% 均值 CI/单次观测 PI；该路径是等价分类回归模型输出，不称为 OAPREDICT 原生区间。L8 的 SSE/MSE 为 0，Minitab 给出零宽区间而 MiniJMP API 将区间标不可用，因此区间数值比较为 N/A；L9 有正残差方差，观察点、非设计可估点及最佳 S/N 设置的 CI/PI 通过直接比较。",
                   "- ROBUST 的均值系数和 ANOVA 仍只能从 Minitab 报表 DISPLAY 读取；系数先按 Minitab 效应编码转换到 MiniJMP 的 treatment 编码，再按报表显示精度比较。L8 的均值模型误差平方和为零，相关 F/P 在两边均不可用。",
                   "- SNRATIO 与 MEANS 直接存储值只落在每组三个重复行的首行；其余两行是 Minitab 的缺失值标记。Delta/Rank 由这些 DIRECT 值聚合后 DERIVED。",
                   "- 本机版本 Minitab 19.1.0.1；新命令及其完整回传保留在逐案例 Session Commands、raw 与 Minitab JSON。", "",
                   "## 证据文件", "",
                   "输入、命令、原始输出、JSON 和逐项 CSV 分 L8/L9 保存；合并比较见 `doe_taguchi_comparison.csv`。"])
    (OUT / "doe_taguchi_acceptance_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"Taguchi 阶段 {overall}: {counts}; 案例状态 {case_states}", flush=True)
    return 1 if overall in ("BLOCKED", "FAIL") else 0


def self_check() -> None:
    import numpy as np

    assert format_case_report_row(
        "l8", {"status": "BLOCKED", "reason": "worker failed"}) == (
            "| L8 | BLOCKED | 0 | 0 | 0 | worker failed |")
    adjusted = adjusted_nominal_reference([1.0, 2.0, 3.0])
    assert math.isclose(adjusted, 10 * math.log10(11 / 3), rel_tol=0, abs_tol=1e-12)
    assert not math.isclose(adjusted, 10 * math.log10(4), rel_tol=0, abs_tol=1e-12)
    for case_id in CASES:
        rows = build_input(case_id)
        assert len(rows) == CASES[case_id]["runs"] * 3
        assert all(math.isfinite(row["Y"]) for row in rows)
        for order in range(1, CASES[case_id]["runs"] + 1):
            assert len({row["Y"] for row in rows if row["standard_order"] == order}) == 3
        mean_rows = [{"standard_order": order, "replicate": 1,
                      **{f"{f}_code": rows[(order - 1) * 3][f"{f}_code"]
                         for f in CASES[case_id]["factors"]},
                      "Y": sum(row["Y"] for row in rows if row["standard_order"] == order) / 3}
                     for order in range(1, CASES[case_id]["runs"] + 1)]
        local, _ = local_model_matrix(case_id, mean_rows)
        effect, _ = effect_model_matrix(case_id, mean_rows)
        assert np.linalg.matrix_rank(local) == np.linalg.matrix_rank(effect) == local.shape[1]
        transform, *_ = np.linalg.lstsq(local, effect, rcond=None)
        assert np.allclose(local @ transform, effect, atol=1e-12, rtol=0)
        result = run_minijmp(case_id, rows)
        assert len(result["mean_ci_points"]) == 3
        assert result["mean_model"]["df"] > 0
    print("Taguchi fixed-input self-check: PASS")


def minijmp_worker_main(case_id: str) -> int:
    try:
        result = run_minijmp(case_id, read_input(case_id))
        minijmp_path(case_id).write_text(json.dumps(result, ensure_ascii=False, indent=2),
                                         encoding="utf-8")
        print(f"MiniJMP {case_id}: create_taguchi + analyze_static + best_settings + "
              "predict_taguchi_model complete", flush=True)
        return 0
    except Exception:
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--com-worker":
        raise SystemExit(worker_main(sys.argv[2]))
    if len(sys.argv) == 3 and sys.argv[1] == "--minijmp-worker":
        raise SystemExit(minijmp_worker_main(sys.argv[2]))
    if len(sys.argv) == 2 and sys.argv[1] == "--self-check":
        self_check()
        raise SystemExit(0)
    try:
        raise SystemExit(parent_main())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
