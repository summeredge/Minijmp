from __future__ import annotations

import csv
import gc
import hashlib
import json
import math
import os
import subprocess
import sys
import traceback
from pathlib import Path


PHASE2 = Path(__file__).resolve().parent
OUT = PHASE2.parent
ROOT = OUT.parents[1]
INPUT = PHASE2 / "case_inputs.json"
MTB_EXE = Path(r"D:\Program\Minitab 19\Mtb.exe")
PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
STATUS_ORDER = ("PASS", "FAIL", "METHOD_DIFF", "UNSUPPORTED", "NOT_RUN")

sys.path.insert(0, str(ROOT / "code"))
sys.path.insert(0, str(ROOT / "Out" / "minitab19_parity"))

import verify_minitab19_com as com_check  # noqa: E402
from verify_doe_2x2 import capture_command_output, running_minitab_pids  # noqa: E402


INPUT_COLUMNS = {
    "CAP-01": {"values": [1]}, "CAP-02": {"values": [2]},
    "CAP-03": {"values": [3]}, "SPC-01": {"values": [4]},
    "SPC-02": {"values": [5]}, "SPC-03": {"groups": list(range(6, 11))},
    "SPC-04": {"groups": list(range(11, 21))},
    "CAP-04": {"values": [21]}, "CAP-05": {"values": [22]},
    "GRR-01": {"measurement": [23], "part": [24], "operator": [25]},
}
CAP_STORAGE = ("MEAN", "SDT", "SDO", "CP", "CPL", "CPU", "CPK",
               "PP", "PPL", "PPU", "PPK", "EPLO", "EPUO", "EPTO")
NN_STORAGE = ("MEAN", "N", "SSHAPE", "SSCALE", "SLOCATION", "STHRESHOLD",
              "PP", "PPL", "PPU", "PPK", "PPML", "PPMU", "PPMT", "EPLO", "EPUO", "EPTO")
CHART_STORAGE = ("POINTS_1", "POINTS_2", "CENTER_1", "CENTER_2",
                 "LIMIT_1_LOWER", "LIMIT_1_UPPER", "LIMIT_2_LOWER", "LIMIT_2_UPPER",
                 "TEST_1", "TEST_2")
OUTPUT_START = {"CAP-01": 30, "CAP-02": 45, "CAP-03": 60,
                "CAP-04": 75, "CAP-05": 92, "SPC-01": 110,
                "SPC-02": 122, "SPC-03": 134, "SPC-04": 146,
                "GRR-01": 158}


def read_inputs() -> dict:
    data = json.loads(INPUT.read_text(encoding="utf-8"))
    if len(data["cases"]) != 10:
        raise ValueError(f"预期 10 个固定案例，实际 {len(data['cases'])}")
    return data


def list_data(values) -> list:
    if values is None:
        return []
    if isinstance(values, (tuple, list)):
        return list(values)
    return [values]


def clean_number(value):
    if value is None or str(value).strip() in {"", "*", "None"}:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if abs(number) >= 1e30:
        return None
    return number if math.isfinite(number) else None


def column_values(worksheet, index: int) -> list:
    values = list_data(worksheet.Columns.Item(index).GetData())
    cleaned = [clean_number(value) for value in values]
    while cleaned and cleaned[-1] is None:
        cleaned.pop()
    return cleaned


def add_column(columns, name: str):
    column = columns.Add(None, None, 1)
    column.Name = name
    return column


def prepare_columns(worksheet, count: int) -> None:
    columns = worksheet.Columns
    while int(columns.Count) < count:
        add_column(columns, f"P2C{int(columns.Count) + 1:03d}")
    for index in range(1, count + 1):
        columns.Item(index).Name = f"P2C{index:03d}"


def input_vectors(cases: dict) -> dict[int, tuple[str, list]]:
    vectors = {}
    for case_id, case in cases.items():
        mapping = INPUT_COLUMNS[case_id]
        if "values" in case:
            vectors[mapping["values"][0]] = (f"{case_id}_Y", case["values"])
        elif case_id == "CAP-02":
            vectors[mapping["values"][0]] = ("CAP-02_Y", [value for group in case["subgroups"] for value in group])
        elif "subgroups" in case:
            for column, values in zip(mapping["groups"], zip(*case["subgroups"])):
                vectors[column] = (f"{case_id}_G{column}", list(values))
        if case_id == "GRR-01":
            for field in ("measurement", "part", "operator"):
                vectors[mapping[field][0]] = (f"GRR_{field}", case[field])
    return vectors


def write_and_check_inputs(worksheet, cases: dict) -> dict:
    vectors = input_vectors(cases)
    loaded_inputs = {}
    for index, (name, values) in vectors.items():
        column = worksheet.Columns.Item(index)
        column.Name = name
        column.SetData(tuple(values), 1, len(values))
        loaded = list_data(column.GetData())
        if len(loaded) != len(values):
            raise AssertionError(f"Minitab C{index} 回读行数不符：{len(loaded)} != {len(values)}")
        if all(isinstance(value, str) for value in values):
            if [str(value) for value in loaded] != values:
                raise AssertionError(f"Minitab C{index} 文本输入回读不同")
        elif any(float(actual) != float(expected) for actual, expected in zip(loaded, values)):
            raise AssertionError(f"Minitab C{index} 数值输入回读不同")
        loaded_inputs[str(index)] = {"name": name, "values": loaded}
    return loaded_inputs


def cap_command(case_id: str, case: dict, data_column: int) -> tuple[str, dict]:
    start = OUTPUT_START[case_id]
    stored = {name: start + index for index, name in enumerate(CAP_STORAGE)}
    args = [f"CAPA C{data_column}"]
    if "subgroups" in case:
        args[0] += f" {case['subgroup_size']}"
    else:
        args[0] += " 1"
    lines = [args[0] + ";"]
    if case.get("lsl") is not None:
        lines.append(f"  LSPEC {case['lsl']};")
    if case.get("usl") is not None:
        lines.append(f"  USPEC {case['usl']};")
    if case.get("target") is not None:
        lines.append(f"  TARGET {case['target']};")
    if "subgroups" in case:
        lines.append("  POOLED;")
    else:
        lines.extend(("  AMR;", "  RSPAN 2;"))
    lines.extend(("  OBIASED;", f"  TOLER {case.get('k', 6)};", "  NOCI;", "  NOCHART;"))
    lines.extend(f"  {name} C{column};" for name, column in stored.items())
    lines[-1] = lines[-1][:-1] + "."
    return "\n".join(lines), {name: [column] for name, column in stored.items()}


def nonnormal_command(case_id: str, case: dict, data_column: int) -> tuple[str, dict]:
    start = OUTPUT_START[case_id]
    stored = {name: start + index for index, name in enumerate(NN_STORAGE)}
    lines = [f"NNCAPA C{data_column};"]
    if case.get("lsl") is not None:
        lines.append(f"  LSPEC {case['lsl']};")
    if case.get("usl") is not None:
        lines.append(f"  USPEC {case['usl']};")
    lines.extend(("  ISOINDEX;", f"  {case['minitab_distribution']};", "  NOCHART;"))
    lines.extend(f"  {name} C{column};" for name, column in stored.items())
    lines[-1] = lines[-1][:-1] + "."
    return "\n".join(lines), {name: [column] for name, column in stored.items()}


def chart_command(case_id: str, case: dict) -> tuple[str, dict]:
    start = OUTPUT_START[case_id]
    stored = {name: start + index for index, name in enumerate(CHART_STORAGE)}
    if case_id in {"SPC-01", "SPC-02"}:
        command = f"IMRCHART C{INPUT_COLUMNS[case_id]['values'][0]};"
        lines = [command, "  AMR;", f"  RSPAN {case['mr_span']};", "  TEST 1;"]
    else:
        command = "XRCHART;" if case_id == "SPC-03" else "XSCHART;"
        cols = INPUT_COLUMNS[case_id]["groups"]
        lines = [command, "  RSUBS " + " ".join(f"C{col}" for col in cols) + ";", "  TEST 1;"]
    lines.extend((
        f"  PPOINTS C{stored['POINTS_1']} C{stored['POINTS_2']};",
        f"  CENLINE C{stored['CENTER_1']} C{stored['CENTER_2']};",
        "  CONLIMITS " + " ".join(f"C{stored[name]}" for name in
            ("LIMIT_1_LOWER", "LIMIT_1_UPPER", "LIMIT_2_LOWER", "LIMIT_2_UPPER")) + ";",
        f"  TRESULTS C{stored['TEST_1']} C{stored['TEST_2']}.",
    ))
    return "\n".join(lines), {name: [column] for name, column in stored.items()}


def grr_command() -> tuple[str, dict]:
    start = OUTPUT_START["GRR-01"]
    stored = {
        "VARIANCE": [start],
        "CONTRIBUTION": [start + 1],
        "STUDYVAR": [start + 2],
        "STUDYPERCENT": [start + 3],
        "NDC": [start + 8],
    }
    return "\n".join((
        "GAGERR;",
        f"  PARTS C{INPUT_COLUMNS['GRR-01']['part'][0]};",
        f"  OPERS C{INPUT_COLUMNS['GRR-01']['operator'][0]};",
        f"  RESPONSE C{INPUT_COLUMNS['GRR-01']['measurement'][0]};",
        "  PVALUE 0.05;",
        "  STUDYVAR 6;",
        f"  SVARCOMP C{stored['VARIANCE'][0]} C{stored['CONTRIBUTION'][0]};",
        f"  SSTUDYVAR C{stored['STUDYVAR'][0]} C{stored['STUDYPERCENT'][0]};",
        f"  SDISTINCT C{stored['NDC'][0]}.",
    )), stored


def commands_for(cases: dict) -> list[dict]:
    commands = []
    for case_id, case in cases.items():
        if case_id.startswith("CAP-") and "distribution" in case:
            command, storage = nonnormal_command(case_id, case, INPUT_COLUMNS[case_id]["values"][0])
        elif case_id.startswith("CAP-"):
            command, storage = cap_command(case_id, case, INPUT_COLUMNS[case_id]["values"][0])
        elif case_id.startswith("SPC-"):
            command, storage = chart_command(case_id, case)
        else:
            command, storage = grr_command()
        commands.append({"case_id": case_id, "command": command, "storage": storage})
    return commands


def com_worker() -> dict:
    import pythoncom
    import win32process
    import win32com.client

    app = project = ui = worksheet = columns = None
    outputs = {}
    metadata = {}
    try:
        if not MTB_EXE.is_file():
            raise FileNotFoundError(f"指定的 Minitab 不存在：{MTB_EXE}")
        before = running_minitab_pids()
        if before:
            raise RuntimeError(f"启动前检测到 Mtb.exe PID {before}；保护已有会话，拒绝连接")
        clsid, registered_path, registered_command = com_check.registered_server()
        if com_check.canonical(registered_path) != com_check.canonical(MTB_EXE):
            raise RuntimeError(f"Mtb.Application 注册路径不符：{registered_command}")
        version = com_check.file_version(MTB_EXE)
        if version != "19.1.0.1":
            raise RuntimeError(f"目标版本必须为 19.1.0.1，实际为 {version}")
        app = win32com.client.DispatchEx("Mtb.Application")
        pythoncom.PumpWaitingMessages()
        ui = app.UserInterface
        ui.Visible = False
        ui.UserControl = False
        ui.DisplayAlerts = False
        app_path = str(app.AppPath)
        hwnd = int(app.Handle)
        process_id, process_path = com_check.process_image_path(hwnd)
        after = running_minitab_pids()
        if (com_check.canonical(app_path) != com_check.canonical(MTB_EXE)
                or com_check.canonical(process_path) != com_check.canonical(MTB_EXE)
                or process_id in before or process_id not in after):
            raise RuntimeError(f"DispatchEx 实例路径/PID 核验失败：{app_path}; {process_path}; {process_id}")
        app.New()
        project = app.ActiveProject
        if project is None:
            raise RuntimeError("Minitab 未返回独立 ActiveProject")
        worksheet = project.ActiveWorksheet
        columns = worksheet.Columns
        cases = read_inputs()["cases"]
        commands = commands_for(cases)
        last_column = max(max(cols) for item in commands for cols in item["storage"].values())
        prepare_columns(worksheet, last_column)
        loaded_inputs = write_and_check_inputs(worksheet, cases)
        metadata = {
            "version": version, "clsid": clsid, "registered_server": registered_command,
            "app_path": app_path, "process_path": process_path, "process_id": process_id,
            "project_name": str(project.Name), "worksheet_name": str(worksheet.Name),
            "python": sys.executable, "loaded_inputs": loaded_inputs,
        }
        for item in commands:
            case_id, command_text = item["case_id"], item["command"]
            before_count = int(project.Commands.Count)
            try:
                project.ExecuteCommand(command_text)
                after_count = int(project.Commands.Count)
                output = capture_command_output(project, after_count) if after_count > before_count else ""
                last_error = str(app.LastError or "")
                accepted = after_count > before_count and not last_error.strip()
                stored, storage_errors = {}, {}
                if accepted:
                    for name, cols in item["storage"].items():
                        try:
                            stored[name] = column_values(worksheet, cols[0]) if len(cols) == 1 else [
                                column_values(worksheet, column) for column in cols]
                        except Exception as exc:
                            storage_errors[name] = f"{type(exc).__name__}: {exc}"
                outputs[case_id] = {
                    "executed": accepted, "command_count": [before_count, after_count],
                    "command": command_text, "output": output, "last_error": last_error,
                    "stored": stored, "storage_errors": storage_errors,
                    "storage_columns": item["storage"],
                }
            except Exception as exc:
                outputs[case_id] = {
                    "executed": False, "command": command_text,
                    "command_count": [before_count, int(project.Commands.Count)],
                    "error": f"{type(exc).__name__}: {exc}", "last_error": str(app.LastError or ""),
                    "stored": {}, "storage_errors": {}, "storage_columns": item["storage"],
                    "traceback": traceback.format_exc(),
                }
        return {"metadata": metadata, "outputs": outputs}
    except Exception:
        return {"metadata": metadata, "outputs": outputs, "fatal_error": traceback.format_exc()}
    finally:
        columns = worksheet = project = app = ui = None
        gc.collect()


def write_csv(path: Path, fieldnames: tuple[str, ...], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def production_results(cases: dict) -> dict:
    import GRR
    import capability
    import control_chart

    result = {}
    for case_id, case in cases.items():
        if case_id.startswith("CAP-"):
            values = case.get("values")
            subgroup_size = 1
            if "subgroups" in case:
                values = [value for group in case["subgroups"] for value in group]
                subgroup_size = case["subgroup_size"]
            result[case_id] = capability.analyze_capability(
                values, lsl=case.get("lsl"), usl=case.get("usl"), target=case.get("target"),
                subgroup_size=subgroup_size, distribution=case.get("distribution", "normal"), k=case["k"])
        elif case_id in {"SPC-01", "SPC-02"}:
            result[case_id] = control_chart.x_mR(case["values"], case["mr_span"], k=case["k"])
        elif case_id == "SPC-03":
            result[case_id] = control_chart.xBar_R(case["subgroups"], k=case["k"])
        elif case_id == "SPC-04":
            result[case_id] = control_chart.xBar_S(case["subgroups"], k=case["k"])
        else:
            report = []
            result[case_id] = GRR.grr_master(
                y=case["measurement"], part=case["part"], op=case["operator"],
                mode="AIAG", inter="auto", alpha=case["alpha"],
                print_out=True, print_port=report.append)
            result[case_id]["_method_report"] = "\n".join(report)
    return result


def run_com() -> tuple[dict, str, str, int]:
    if not PYTHON.is_file():
        return {}, f"项目 .venv Python 不存在：{PYTHON}", "", 1
    command = [str(PYTHON), "-X", "utf8", str(Path(__file__).resolve()), "--com-worker"]
    env = os.environ.copy()
    for name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        env[name] = "1"
    try:
        process = subprocess.run(command, capture_output=True, text=True, encoding="utf-8",
                                 errors="replace", timeout=300, check=False, env=env)
        result = json.loads(process.stdout) if process.stdout.strip() else {}
        after = running_minitab_pids()
        if after:
            result.setdefault("cleanup_error", f"COM worker 退出后仍有 Mtb.exe PID {after}；未操作這些进程")
        exit_code = process.returncode or (1 if result.get("fatal_error") or result.get("cleanup_error") else 0)
        return result, process.stderr, process.stdout, exit_code
    except Exception as exc:
        return {}, f"{type(exc).__name__}: {exc}", "", 1


def metric_value(result: dict, metric: str):
    if metric == "mean":
        return result["mean"]
    if metric == "within_sigma":
        return result["within_sigma"]
    if metric == "overall_sigma":
        return result["overall_sigma"]
    if metric.startswith("index:"):
        return result["indices"].get(metric.split(":", 1)[1])
    if metric.startswith("ppm:"):
        _, period, side = metric.split(":")
        return result["ppm"].get(period, {}).get(side)
    if metric.startswith("parameter:"):
        return result["fit"]["parameters"].get(metric.split(":", 1)[1])
    if metric.startswith("spc:"):
        _, key, index = metric.split(":")
        values = result.get(key)
        if isinstance(values, (tuple, list)):
            return values[int(index)]
        return values
    return None


COMPARISON_FIELDS = (
    "case_id", "feature", "metric", "match_key", "minijmp_value", "minitab_value",
    "absolute_error", "relative_error", "tolerance", "status", "minijmp_source",
    "minitab_source", "method_note",
)


def append_comparison(rows: list[dict], case_id: str, case: dict, metric: str, match_key: str,
                      expected, actual, tolerance: float, mini_source: str, mtb_source: str,
                      command_result: dict, method_diff: str = "") -> None:
    status = "PASS"
    error = ""
    if not command_result or not command_result.get("executed"):
        status = "NOT_RUN" if not command_result else "UNSUPPORTED"
        error = (command_result or {}).get("error") or (command_result or {}).get("last_error") or "Minitab command was not accepted"
    elif expected is None or actual is None:
        status = "UNSUPPORTED"
        error = "Minitab direct storage or MiniJMP metric is unavailable"
    else:
        expected, actual = float(expected), float(actual)
        error = abs(expected - actual)
        status = "METHOD_DIFF" if method_diff else ("PASS" if error <= tolerance else "FAIL")
    rel = None
    if isinstance(error, (int, float)) and expected not in (None, 0):
        rel = error / abs(float(expected))
    rows.append({
        "case_id": case_id, "feature": case["feature"], "metric": metric,
        "match_key": match_key, "minijmp_value": expected, "minitab_value": actual,
        "absolute_error": error if isinstance(error, (int, float)) else "",
        "relative_error": rel if rel is not None else "", "tolerance": tolerance,
        "status": status, "minijmp_source": mini_source, "minitab_source": mtb_source,
        "method_note": case.get("method", "") + (
            f"; {method_diff or error}" if method_diff or isinstance(error, str) else ""),
    })


def stored_scalar(command_result: dict, key: str):
    values = command_result.get("stored", {}).get(key, []) if command_result else []
    if isinstance(values, list) and values and isinstance(values[0], list):
        values = values[0]
    return values[0] if values else None


def compare_capability(rows: list[dict], case_id: str, case: dict, mini: dict, mtb: dict, tol: dict) -> None:
    command = mtb.get("outputs", {}).get(case_id, {})
    storage = command.get("stored", {})
    mtb_source = lambda key: f"Minitab COM {case_id}; stored {key} in {command.get('storage_columns', {}).get(key, [])}"
    mini_source = "code.capability.analyze_capability"
    if case_id == "CAP-01":
        metrics = [("Mean", "mean", "MEAN", "capability_parameter_abs"),
                   ("Within Sigma", "within_sigma", "SDT", "capability_parameter_abs"),
                   ("Overall Sigma", "overall_sigma", "SDO", "capability_parameter_abs"),
                   ("Cp", "index:Cp", "CP", "capability_index_abs"),
                   ("Cpk", "index:Cpk", "CPK", "capability_index_abs"),
                   ("Pp", "index:Pp", "PP", "capability_index_abs"),
                   ("Ppk", "index:Ppk", "PPK", "capability_index_abs")]
    elif case_id == "CAP-02":
        metrics = [("Within Sigma", "within_sigma", "SDT", "capability_parameter_abs"),
                   ("Overall Sigma", "overall_sigma", "SDO", "capability_parameter_abs"),
                   ("Cp", "index:Cp", "CP", "capability_index_abs"),
                   ("Cpk", "index:Cpk", "CPK", "capability_index_abs"),
                   ("Pp", "index:Pp", "PP", "capability_index_abs"),
                   ("Ppk", "index:Ppk", "PPK", "capability_index_abs")]
    else:
        metrics = [("Cpu", "index:Cpu", "CPU", "capability_index_abs"),
                   ("Cpk", "index:Cpk", "CPK", "capability_index_abs"),
                   ("Ppk", "index:Ppk", "PPK", "capability_index_abs"),
                   ("Expected upper PPM", "ppm:overall:upper", "EPUO", "capability_ppm_abs")]
    for label, key, store, tol_key in metrics:
        val = metric_value(mini, key)
        actual = stored_scalar(command, store)
        if actual is None and command.get("executed") and key.startswith("index:") and val is None:
            continue
        method_diff = case.get("method_diff", "") if label in case.get("method_diff_metrics", []) else ""
        append_comparison(rows, case_id, case, label, "overall", val, actual, tol[tol_key],
                          mini_source, mtb_source(store), command, method_diff)


def compare_nonnormal(rows: list[dict], case_id: str, case: dict, mini: dict, mtb: dict, tol: dict) -> None:
    command = mtb.get("outputs", {}).get(case_id, {})
    values = command.get("stored", {})
    source = lambda key: f"Minitab COM NNCAPA {case['minitab_distribution']}; direct storage {key}"
    mini_source = "code.capability.analyze_capability"
    if case["distribution"] == "weibull":
        metrics = [
            ("Shape", mini["fit"]["parameters"]["shape"], stored_scalar(command, "SSHAPE"), "capability_parameter_abs", "SSHAPE"),
            ("Scale", mini["fit"]["parameters"]["scale"], stored_scalar(command, "SSCALE"), "capability_parameter_abs", "SSCALE"),
        ]
    else:
        mu = math.log(mini["fit"]["parameters"]["scale"])
        sigma = mini["fit"]["parameters"]["shape"]
        metrics = [
            ("Lognormal log-mean", mu, stored_scalar(command, "SLOCATION"), "capability_parameter_abs", "SLOCATION"),
            ("Lognormal log-SD", sigma, stored_scalar(command, "SSCALE"), "capability_parameter_abs", "SSCALE"),
        ]
    for label, expected, actual, tol_key, store in metrics:
        method_diff = case.get("method_diff", "") if label in case.get("method_diff_metrics", []) else ""
        append_comparison(rows, case_id, case, label, "fit", expected, actual, tol[tol_key],
                          mini_source, source(store), command, method_diff)
    for label, key, store in (("Pp", "Pp", "PP"), ("Ppk", "Ppk", "PPK"),
                              ("Ppl", "Ppl", "PPL"), ("Ppu", "Ppu", "PPU")):
        method_diff = case.get("method_diff", "") if label in case.get("method_diff_metrics", []) else ""
        append_comparison(rows, case_id, case, label, "overall", mini["indices"].get(key),
                          stored_scalar(command, store), tol["capability_index_abs"],
                          mini_source, source(store), command, method_diff)
    for side, store in (("lower", "EPLO"), ("upper", "EPUO"), ("total", "EPTO")):
        label = f"Expected {side} PPM"
        method_diff = case.get("method_diff", "") if label in case.get("method_diff_metrics", []) else ""
        append_comparison(rows, case_id, case, label, side,
                          mini["ppm"]["overall"][side], stored_scalar(command, store),
                          tol["capability_ppm_abs"], mini_source, source(store), command, method_diff)
    for side, store in (("lower", "PPML"), ("upper", "PPMU"), ("total", "PPMT")):
        append_comparison(rows, case_id, case, f"Observed {side} PPM", side,
                          mini["ppm"]["observed"][side], stored_scalar(command, store),
                          tol["capability_ppm_abs"], mini_source, source(store), command)


def sequence(values, expected_length: int, leading_missing: bool = False) -> list:
    result = list(values or [])
    if leading_missing and len(result) == expected_length - 1:
        return [None, *result]
    return result


def expand_series(value, count: int) -> list:
    if isinstance(value, (tuple, list)):
        return list(value)
    return [value] * count


def compare_chart_series(rows: list[dict], case_id: str, case: dict, command: dict,
                         metric: str, expected, actual, count: int, tolerance: float,
                         mini_source: str, mtb_source: str) -> None:
    expected_values = expand_series(expected, count)
    actual_values = list(actual or [])
    if len(actual_values) == 1 and len(expected_values) > 1:
        first = clean_number(expected_values[0])
        if all(clean_number(value) == first for value in expected_values):
            expected_values = [expected_values[0]]
            keys = ["constant"]
        else:
            keys = [f"point:{index+1}" for index in range(len(expected_values))]
    else:
        keys = [f"point:{index+1}" for index in range(len(expected_values))]
    for index in range(max(len(expected_values), len(actual_values))):
        expected_value = expected_values[index] if index < len(expected_values) else None
        actual_value = actual_values[index] if index < len(actual_values) else None
        match_key = keys[index] if index < len(keys) else f"point:{index+1}"
        append_comparison(rows, case_id, case, metric, match_key, expected_value, actual_value,
                          tolerance, mini_source, mtb_source, command)


def compare_spc(rows: list[dict], case_id: str, case: dict, mini: dict, mtb: dict, tol: dict) -> None:
    command = mtb.get("outputs", {}).get(case_id, {})
    stored = command.get("stored", {})
    mini_source = "code.control_chart.x_mR" if case_id in {"SPC-01", "SPC-02"} else (
        "code.control_chart.xBar_R" if case_id == "SPC-03" else "code.control_chart.xBar_S")
    n1, n2 = len(mini["Y1"]), len(mini["Y2"])
    for panel, key, n, allow_leading_missing in ((1, "POINTS_1", n1, False),
                                                  (2, "POINTS_2", n2, case_id in {"SPC-01", "SPC-02"})):
        expected = list(mini[f"Y{panel}"])
        actual = sequence(stored.get(key, []), n, allow_leading_missing)
        for index in range(min(n, max(len(expected), len(actual)))):
            exp = clean_number(expected[index]) if index < len(expected) else None
            got = actual[index] if index < len(actual) else None
            if exp is None and got is None:
                continue
            append_comparison(rows, case_id, case, f"Chart {panel} plotted point", f"point:{index+1}", exp, got,
                              tol["spc_point_abs"], mini_source, f"Minitab COM PPOINTS column {key}", command)
    centers = [mini["bar1"], mini["bar2"]]
    lowers = [mini["lcl1"], mini["lcl2"]]
    uppers = [mini["ucl1"], mini["ucl2"]]
    counts = [n1, n2]
    for panel in (1, 2):
        compare_chart_series(rows, case_id, case, command, f"Chart {panel} center line", centers[panel-1],
                             stored.get(f"CENTER_{panel}", []), counts[panel-1], tol["spc_limit_abs"],
                             mini_source, f"Minitab COM CENLINE column CENTER_{panel}")
        for side, expected, store in (("LCL", lowers[panel-1], f"LIMIT_{panel}_LOWER"),
                                      ("UCL", uppers[panel-1], f"LIMIT_{panel}_UPPER")):
            compare_chart_series(rows, case_id, case, command, f"Chart {panel} {side}", expected,
                                 stored.get(store, []), counts[panel-1], tol["spc_limit_abs"],
                                 mini_source, f"Minitab COM CONLIMITS {store}")
    points = [mini["Y1"], mini["Y2"]]
    for panel in (1, 2):
        values = points[panel-1]
        lower = expand_series(lowers[panel-1], len(values))
        upper = expand_series(uppers[panel-1], len(values))
        flags = [None if clean_number(value) is None else
                 int(value < lower[index] or value > upper[index])
                 for index, value in enumerate(values)]
        actual = sequence(stored.get(f"TEST_{panel}", []), len(flags), panel == 2 and case_id in {"SPC-01", "SPC-02"})
        for index, flag in enumerate(flags):
            if flag is None:
                continue
            got = actual[index] if index < len(actual) else None
            append_comparison(rows, case_id, case, f"Chart {panel} single-point test", f"point:{index+1}",
                              flag, got, 0.0, mini_source,
                              f"Minitab COM TEST 1 / TRESULTS panel {panel}", command)


def grr_variance_parts(result: dict) -> dict:
    interaction = float(result["INT"])
    reproducibility = float(result["AV"])
    return {
        "Total Gage R&R": float(result["RR"]), "Repeatability": float(result["EV"]),
        "Reproducibility": reproducibility, "Operator": reproducibility - interaction,
        "Operator*Part": interaction, "Part-To-Part": float(result["PV"]),
        "Total Variation": float(result["TV"]),
    }


def compare_grr(rows: list[dict], case_id: str, case: dict, mini: dict, mtb: dict, tol: dict) -> None:
    command = mtb.get("outputs", {}).get(case_id, {})
    stored = command.get("stored", {})
    parts = grr_variance_parts(mini)
    # GAGERR stores rows in the order shown by its Variance Components table.
    order = ("Total Gage R&R", "Repeatability", "Reproducibility", "Operator",
             "Operator*Part", "Part-To-Part", "Total Variation")
    for index, source_name in enumerate(order):
        expected = parts[source_name]
        actual = stored.get("VARIANCE", [])[index] if index < len(stored.get("VARIANCE", [])) else None
        append_comparison(rows, case_id, case, "Variance component", source_name, expected, actual,
                          tol["grr_variance_abs"], "code.GRR.grr_master(mode=AIAG, inter=auto)",
                          f"Minitab COM GAGERR SVARCOMP row {index+1}: {source_name}", command)
        expected_contribution = 100 * expected / float(mini["TV"])
        contribution = stored.get("CONTRIBUTION", [])
        actual_contribution = contribution[index] if index < len(contribution) else None
        append_comparison(rows, case_id, case, "Variance contribution (%)", source_name,
                          expected_contribution, actual_contribution, tol["grr_percent_abs"],
                          "code.GRR.grr_master → variance / total variance", "Minitab COM SVARCOMP %Contribution", command)
        expected_study = 100 * math.sqrt(expected / float(mini["TV"]))
        study = stored.get("STUDYPERCENT", [])
        actual_study = study[index] if index < len(study) else None
        append_comparison(rows, case_id, case, "Study variation (%)", source_name,
                          expected_study, actual_study, tol["grr_percent_abs"],
                          "code.GRR.grr_master → SD / total SD", "Minitab COM SSTUDYVAR %StudyVar", command)
    actual_ndc = stored_scalar(command, "NDC")
    expected_ndc = int(math.sqrt(2 * float(mini["PV"]) / float(mini["RR"]))) if mini["RR"] > 0 else None
    append_comparison(rows, case_id, case, "ndc", "overall", expected_ndc, actual_ndc,
                      tol["ndc_abs"], "code.GRR.grr_master AIAG rule: int(sqrt(2*PV/RR))",
                      "Minitab COM GAGERR SDISTINCT", command)


def comparison_rows(cases: dict, mini_results: dict, mtb_result: dict, tolerances: dict) -> list[dict]:
    rows = []
    for case_id, case in cases.items():
        mini = mini_results[case_id]
        if case_id.startswith("CAP-") and "distribution" in case:
            compare_nonnormal(rows, case_id, case, mini, mtb_result, tolerances)
        elif case_id.startswith("CAP-"):
            compare_capability(rows, case_id, case, mini, mtb_result, tolerances)
        elif case_id.startswith("SPC-"):
            compare_spc(rows, case_id, case, mini, mtb_result, tolerances)
        else:
            compare_grr(rows, case_id, case, mini, mtb_result, tolerances)
    return rows


def result_hash(value) -> str:
    raw = json.dumps(json_safe(value), ensure_ascii=False, sort_keys=True,
                     separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def json_safe(value):
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [json_safe(item) for item in value]
    return value


def write_outputs(runs: list[dict], all_rows: list[list[dict]], cases: dict, inputs: dict,
                  production_runs: list[dict], stderr: list[str], exit_codes: list[int]) -> None:
    rows = all_rows[0]
    write_csv(PHASE2 / "comparison.csv", COMPARISON_FIELDS, rows)
    summary = []
    for case_id, case in cases.items():
        case_rows = [row for row in rows if row["case_id"] == case_id]
        counts = {status: sum(row["status"] == status for row in case_rows) for status in STATUS_ORDER}
        output_runs = [run.get("outputs", {}).get(case_id, {}) for run in runs]
        executed = sum(bool(item.get("executed")) for item in output_runs)
        if counts["FAIL"]:
            state = "FAIL"
        elif counts["METHOD_DIFF"]:
            state = "METHOD_DIFF"
        elif counts["UNSUPPORTED"]:
            state = "UNSUPPORTED"
        elif counts["NOT_RUN"]:
            state = "NOT_RUN"
        else:
            state = "PASS"
        summary.append({
            "case_id": case_id, "feature": case["feature"], "指标数": len(case_rows),
            **counts, "Minitab命令成功运行次数": f"{executed}/2", "案例状态": state,
            "备注": case.get("method", "") + (
                f"；MiniJMP ANOVA 交互方差={production_runs[0]['GRR-01']['INT']:.12g}；"
                "Minitab 交互项筛选/方差分量见 minitab_raw_outputs.txt"
                if case_id == "GRR-01" else ""),
        })
    write_csv(PHASE2 / "summary.csv",
              ("case_id", "feature", "指标数", *STATUS_ORDER, "Minitab命令成功运行次数", "案例状态", "备注"), summary)

    command_blocks = [
        "Minitab 19.1.0.1 phase 2 commands; each full case set executed twice in independent COM projects.",
        f"Executable: {MTB_EXE}", "",
    ]
    for item in commands_for(cases):
        command_blocks.extend((f"===== {item['case_id']} =====", item["command"], ""))
    (PHASE2 / "minitab_session_commands.txt").write_text("\n".join(command_blocks), encoding="utf-8")

    raw_blocks = []
    for index, (run, stderr_text, exit_code) in enumerate(zip(runs, stderr, exit_codes), start=1):
        raw_blocks.append(f"===== Minitab COM run {index}; exit={exit_code} =====")
        if run.get("fatal_error"):
            raw_blocks.append("FATAL\n" + run["fatal_error"])
        if run.get("cleanup_error"):
            raw_blocks.append("CLEANUP\n" + run["cleanup_error"])
        if stderr_text:
            raw_blocks.append("STDERR\n" + stderr_text)
        raw_blocks.append("METADATA\n" + json.dumps(run.get("metadata", {}), ensure_ascii=False, indent=2))
        for case_id, output in run.get("outputs", {}).items():
            raw_blocks.append(f"===== {case_id}: actual Minitab Session command =====\n{output.get('command','')}")
            raw_blocks.append("===== OutputDocument.Text / Output.Text =====\n" + (output.get("output") or "(empty)"))
            raw_blocks.append("===== Minitab direct storage =====\n" + json.dumps(
                {"executed": output.get("executed"), "command_count": output.get("command_count"),
                 "last_error": output.get("last_error"), "stored": output.get("stored", {}),
                 "storage_errors": output.get("storage_errors", {}),
                 "storage_columns": output.get("storage_columns", {})},
                ensure_ascii=False, indent=2))
            if output.get("error"):
                raw_blocks.append("ERROR\n" + output["error"] + "\n" + output.get("traceback", ""))
        if index <= len(production_runs) and production_runs[index - 1].get("GRR-01", {}).get("_method_report"):
            raw_blocks.append("===== MiniJMP GRR ANOVA auto-interaction evidence =====\n"
                              + production_runs[index - 1]["GRR-01"]["_method_report"])
    raw_blocks.append(
        "===== Preliminary command probes excluded from final counts =====\n"
        "Minitab 19 CAPA rejected SDW; final CAPA stores within sigma with SDT.\n"
        "Minitab 19 NNCAPA rejected NOCI: 子命令 NOCI 失序，或者对于该命令无效；其余子命令被忽略，计算不可能完成。\n"
        "Final NNCAPA omits NOCI.\n"
        "These probes are not included in comparison.csv or summary.csv counts."
    )
    (PHASE2 / "minitab_raw_outputs.txt").write_text("\n\n".join(raw_blocks) + "\n", encoding="utf-8")

    input_sha = hashlib.sha256(INPUT.read_bytes()).hexdigest()
    def compact_production(mini):
        compact = {}
        for key, value in mini.items():
            if key.startswith("SPC-") or key == "GRR-01":
                compact[key] = json_safe(value)
            else:
                compact[key] = json_safe({
                    "mean": value["mean"], "within_sigma": value["within_sigma"],
                    "overall_sigma": value["overall_sigma"], "indices": value["indices"],
                    "ppm": value["ppm"], "fit_parameters": value["fit"].get("parameters", {})})
        return compact

    production_hashes = [result_hash(compact_production(mini)) for mini in production_runs]
    compare_hashes = [result_hash(run_rows) for run_rows in all_rows]
    minitab_hashes = [result_hash({case_id: {"executed": output.get("executed"),
                                             "stored": output.get("stored", {})}
                                   for case_id, output in run.get("outputs", {}).items()})
                      for run in runs]
    complete_attempts = all(
        run.get("metadata", {}).get("version") == "19.1.0.1"
        and len(run.get("outputs", {})) == len(cases)
        and len(run.get("metadata", {}).get("loaded_inputs", {})) == len(input_vectors(cases))
        and not run.get("fatal_error") and not run.get("cleanup_error")
        for run in runs
    )
    repeatability_ok = (exit_codes == [0, 0] and complete_attempts
                        and production_hashes[0] == production_hashes[1]
                        and compare_hashes[0] == compare_hashes[1]
                        and minitab_hashes[0] == minitab_hashes[1])
    repeatability = [
        "MiniJMP × Minitab 19 phase 2 repeatability check",
        f"case_inputs.json SHA256: {input_sha}",
        f"Planned cases: {len(cases)}; fixed order: {', '.join(cases)}",
        f"Minitab COM worker exit codes: {exit_codes}",
        f"Minitab versions: {[run.get('metadata', {}).get('version') for run in runs]}",
        f"Production calculation hashes identical: {production_hashes[0] == production_hashes[1]}",
        f"Production run 1 SHA256: {production_hashes[0]}",
        f"Production run 2 SHA256: {production_hashes[1]}",
        f"Comparison rows identical: {compare_hashes[0] == compare_hashes[1]}",
        f"Comparison run 1 SHA256: {compare_hashes[0]}",
        f"Comparison run 2 SHA256: {compare_hashes[1]}",
        f"All 10 commands attempted and inputs read back in both independent COM projects: {complete_attempts}",
        f"Minitab direct stored values identical: {minitab_hashes[0] == minitab_hashes[1]}",
        f"Minitab result run 1 SHA256: {minitab_hashes[0]}",
        f"Minitab result run 2 SHA256: {minitab_hashes[1]}",
        "PASS: fixed inputs, complete run attempts, production results, Minitab storage, and comparisons repeat."
        if input_sha and repeatability_ok else "NOT PASS: see run completeness and hashes above.",
        "",
    ]
    (PHASE2 / "repeatability_check.txt").write_text("\n".join(repeatability), encoding="utf-8")


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "--com-worker":
        try:
            result = com_worker()
        except Exception:
            result = {"metadata": {}, "outputs": {}, "fatal_error": traceback.format_exc()}
        sys.stdout.write(json.dumps(result, ensure_ascii=False, allow_nan=False))
        return 0

    inputs = read_inputs()
    cases = inputs["cases"]
    registered_clsid, registered_path, registered_command = com_check.registered_server()
    version = com_check.file_version(MTB_EXE)
    if com_check.canonical(registered_path) != com_check.canonical(MTB_EXE):
        raise RuntimeError(f"Mtb.Application 注册服务器不符：{registered_command}")
    if version != inputs["metadata"]["required_version"]:
        raise RuntimeError(f"要求 Minitab {inputs['metadata']['required_version']}，实际为 {version}")
    if running_minitab_pids():
        raise RuntimeError("启动前检测到 Mtb.exe；为保护已有会话，本脚本拒绝连接或运行")

    production_runs, runs, stderr, exit_codes, all_rows = [], [], [], [], []
    for run_number in (1, 2):
        production_runs.append(production_results(cases))
        run, error_text, _, exit_code = run_com()
        runs.append(run)
        stderr.append(error_text)
        exit_codes.append(exit_code)
        all_rows.append(comparison_rows(cases, production_runs[-1], run, inputs["tolerances"]))

    write_outputs(runs, all_rows, cases, inputs, production_runs, stderr, exit_codes)
    print(f"Minitab {version}; CLSID={registered_clsid}; COM runs={exit_codes}; cases={len(cases)}")
    statuses = {status: sum(row["status"] == status for row in all_rows[0]) for status in STATUS_ORDER}
    print(f"Comparison metrics={len(all_rows[0])}; statuses={statuses}")
    return 0 if all(code == 0 for code in exit_codes) else 1


if __name__ == "__main__":
    raise SystemExit(main())
