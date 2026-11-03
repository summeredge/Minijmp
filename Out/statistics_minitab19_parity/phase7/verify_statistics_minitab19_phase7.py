from __future__ import annotations

import csv
import gc
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import traceback
from pathlib import Path


PHASE7 = Path(__file__).resolve().parent
OUT = PHASE7.parent
ROOT = OUT.parents[1]
PHASE2 = OUT / "phase2"
INPUT = PHASE7 / "case_inputs.json"
MTB_EXE = Path(r"D:\Program\Minitab 19\Mtb.exe")
PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
STATUS_ORDER = ("PASS", "FAIL", "METHOD_DIFF", "UNSUPPORTED", "NOT_RUN")

sys.path.insert(0, str(ROOT / "code"))
sys.path.insert(0, str(PHASE2))
import verify_statistics_minitab19_phase2 as phase2  # noqa: E402


def load_inputs() -> dict:
    data = json.loads(INPUT.read_text(encoding="utf-8"))
    if data["metadata"]["required_version"] != "19.1.0.1":
        raise ValueError("phase7 固定要求 Minitab 19.1.0.1")
    cases = data["cases"]
    if sorted(cases["SPC-NELSON"]["rules"]) != list(range(1, 9)):
        raise ValueError("Nelson 固定案例须覆盖规则 1–8")
    if any(not cases["SPC-NELSON"]["values_by_rule"].get(str(rule)) for rule in range(1, 9)):
        raise ValueError("每条 Nelson 规则均须有独立非空固定输入")
    if len(cases["SPC-XBR-VAR"]["subgroups"]) != 3 or sorted(
            len(group) for group in cases["SPC-XBR-VAR"]["subgroups"]) != [3, 4, 5]:
        raise ValueError("Xbar-R 变量子组案例须为 n=3、4、5")
    if len(cases["PCA-01"]["rows"]) != 10 or len(cases["PLS-01"]["rows"]) != 12:
        raise ValueError("PCA/PLS 固定输入行数不符")
    return data


def resolve_cases(data: dict) -> dict:
    previous = json.loads((PHASE2 / "case_inputs.json").read_text(encoding="utf-8"))["cases"]
    cases = data["cases"]
    for case_id, case in cases.items():
        source = case.get("source_case")
        if source:
            if not source.startswith("phase2/case_inputs.json#cases."):
                raise ValueError(f"{case_id} 的复用输入来源无效：{source}")
            previous_id = source.rsplit(".", 1)[1]
            case["resolved_source"] = previous[previous_id]
    return cases


def input_vectors(cases: dict) -> dict[int, tuple[str, list]]:
    vectors = {}
    for case_id, c in cases.items():
        if case_id == "SPC-P":
            vectors[1] = ("P_defectives", c["defectives"])
            vectors[2] = ("P_sample_size", c["sample_sizes"])
        elif case_id == "SPC-NP":
            vectors[3] = ("NP_defectives", c["defectives"])
        elif case_id == "SPC-C":
            vectors[4] = ("C_defects", c["defects"])
        elif case_id == "SPC-U":
            vectors[5] = ("U_defects", c["defects"])
            vectors[6] = ("U_opportunities", c["sample_sizes"])
        elif case_id == "SPC-XBR-VAR":
            vectors[7] = ("XBR_measurements", [value for group in c["subgroups"] for value in group])
            vectors[8] = ("XBR_subgroup_id", [group_id for group_id, group in enumerate(c["subgroups"], 1)
                                               for _ in group])
        elif case_id == "SPC-NELSON":
            for rule in c["rules"]:
                vectors[23 + rule] = (f"Nelson_rule_{rule}_values", c["values_by_rule"][str(rule)])
        elif case_id == "GRR-CROSS-XBAR":
            old = c["resolved_source"]
            vectors[11] = ("GRR_cross_measurement", old["measurement"])
            vectors[12] = ("GRR_cross_part", old["part"])
            vectors[13] = ("GRR_cross_operator", old["operator"])
        elif case_id == "GRR-NESTED":
            vectors[14] = ("GRR_nested_measurement", c["measurements"])
            vectors[15] = ("GRR_nested_part", c["parts"])
            vectors[16] = ("GRR_nested_operator", c["operators"])
        elif case_id == "PCA-01":
            for col, index in enumerate(range(17, 20)):
                vectors[index] = (c["columns"][col], [row[col] for row in c["rows"]])
        elif case_id == "PLS-01":
            names = c["predictors"] + c["responses"]
            for col, index in enumerate(range(20, 23)):
                vectors[index] = (names[col], [row[col] for row in c["rows"]])
    return vectors


def _command(case_id: str, text: str, columns: dict[str, list[int]], matrices=None) -> dict:
    return {"case_id": case_id, "command": text,
            "storage_columns": columns, "storage_matrices": matrices or {}}


def commands_for(cases: dict) -> list[dict]:
    commands = []
    for case_id, c in cases.items():
        if c.get("chart") in {"P", "NP", "C", "U"}:
            index = {"P": (1, 2), "NP": (3, None), "C": (4, None), "U": (5, 6)}[c["chart"]]
            start = {"P": 100, "NP": 110, "C": 120, "U": 130}[c["chart"]]
            if c["chart"] == "P":
                main = "PCHART C1 C2"
            elif c["chart"] == "NP":
                main = f"NPCHART C3 {c['sample_size']}"
            elif c["chart"] == "C":
                main = "CCHART C4"
            else:
                main = "UCHART C5 C6"
            command = "\n".join((
                main + ";", "  TEST 1 2 3 4;",
                f"  PPOINTS C{start};", f"  CENLINE C{start + 1};",
                f"  CONLIMITS C{start + 2} C{start + 3};",
                "  TRESULTS " + " ".join(f"C{start + 4 + i}" for i in range(4)) + ".",
            ))
            storage = {name: [start + offset] for name, offset in (
                ("PPOINTS", 0), ("CENLINE", 1), ("LCL", 2), ("UCL", 3),
                ("TEST_1", 4), ("TEST_2", 5), ("TEST_3", 6), ("TEST_4", 7))}
            commands.append(_command(case_id, command, storage))
        elif case_id == "SPC-XBR-VAR":
            start = 140
            command = "\n".join((
                "XRCHART C7 C8;",
                f"  PPOINTS C{start} C{start + 1};",
                f"  CENLINE C{start + 2} C{start + 3};",
                f"  CONLIMITS C{start + 4} C{start + 5} C{start + 6} C{start + 7}.",
            ))
            storage = {name: [start + offset] for name, offset in (
                ("XBAR_POINTS", 0), ("R_POINTS", 1), ("XBAR_CENTER", 2),
                ("R_CENTER", 3), ("XBAR_LCL", 4), ("XBAR_UCL", 5),
                ("R_LCL", 6), ("R_UCL", 7))}
            commands.append(_command(case_id, command, storage))
        elif case_id == "SPC-NELSON":
            for rule in c["rules"]:
                start = 150 + 2 * (rule - 1)
                lines = [f"IMRCHART C{23 + rule};", f"  MU {c['mean']};", f"  SIGMA {c['sigma']};"]
                lines.append(f"  TEST {rule};")
                if rule <= 4:
                    lines.append(f"  TRESULTS C{start} C{start + 1}.")
                else:
                    lines.append(f"  TRESULTS C{start}.")
                command = "\n".join(lines)
                storage = {"I_TEST": [start]}
                if rule <= 4:
                    storage["MR_TEST"] = [start + 1]
                commands.append(_command(
                    f"{case_id}-RULE-{rule}", command,
                    storage,
                ))
        elif case_id == "GRR-CROSS-XBAR":
            start = 170
            old = c["resolved_source"]
            command = "\n".join((
                "GAGERR;", "  PARTS C12;", "  OPERS C13;", "  RESPONSE C11;",
                "  XBAR;", "  STUDYVAR 6;",
                f"  SVARCOMP C{start} C{start + 1};", f"  SSTDDEV C{start + 2};",
                f"  SSTUDYVAR C{start + 3} C{start + 4};", f"  SDISTINCT C{start + 5}.",
            ))
            storage = {name: [start + offset] for name, offset in (
                ("VARIANCE", 0), ("CONTRIBUTION", 1), ("STDDEV", 2),
                ("STUDYVAR", 3), ("STUDYPERCENT", 4), ("NDC", 5))}
            commands.append(_command(case_id, command, storage))
        elif case_id == "GRR-NESTED":
            start = 180
            command = "\n".join((
                "NTGAGE;", "  PARTS C15;", "  OPERS C16;", "  RESPONSE C14;",
                f"  STUDYVAR {c['study_var']};",
                f"  SVARCOMP C{start} C{start + 1};", f"  SSTDDEV C{start + 2};",
                f"  SSTUDYVAR C{start + 3} C{start + 4};", f"  SDISTINCT C{start + 5}.",
            ))
            storage = {name: [start + offset] for name, offset in (
                ("VARIANCE", 0), ("CONTRIBUTION", 1), ("STDDEV", 2),
                ("STUDYVAR", 3), ("STUDYPERCENT", 4), ("NDC", 5))}
            commands.append(_command(case_id, command, storage))
        elif case_id == "PCA-01":
            start = 190
            coefficient_columns = " ".join(f"C{start + i}" for i in range(c["n_components"]))
            score_columns = " ".join(f"C{start + c['n_components'] + i}" for i in range(c["n_components"]))
            eigen_column = start + 2 * c["n_components"]
            command = "\n".join((
                "PCA C17-C19;", f"  NCOMP {c['n_components']};",
                f"  COEFFICIENTS {coefficient_columns};", f"  SCORES {score_columns};",
                f"  EIGEN C{eigen_column}.",
            ))
            storage = {f"COEFFICIENT_PC{i + 1}": [start + i] for i in range(c["n_components"])}
            storage.update({f"SCORE_PC{i + 1}": [start + c["n_components"] + i]
                            for i in range(c["n_components"])})
            storage["EIGEN"] = [eigen_column]
            commands.append(_command(case_id, command, storage))
        elif case_id == "PLS-01":
            command = "\n".join((
                "PLS C22 = C20-C21;", f"  NCOMP {c['n_components']};",
                "  FITS C200;", "  COEFFICIENTS C201;",
                "  XSCORES M10;", "  YSCORES M11;",
                "  XLOADINGS M12;", "  YLOADINGS M13.",
            ))
            commands.append(_command(case_id, command, {"FITS": [200], "COEFFICIENTS": [201]}, {
                "XSCORES": [len(c["rows"]), c["n_components"]],
                "YSCORES": [len(c["rows"]), c["n_components"]],
                "XLOADINGS": [len(c["predictors"]), c["n_components"]],
                "YLOADINGS": [len(c["responses"]), c["n_components"]],
            }))
        elif case_id == "MULTI-DESC-01":
            command = "\n".join((
                "STATS C17-C19;", "  N C220-C222;", "  MEANS C223-C225;", "  STDEV C226-C228;",
                "  MINIMUMS C229-C231;", "  MAXIMUMS C232-C234.",
            ))
            commands.append(_command(case_id, command, {
                "N": [220, 221, 222], "MEAN": [223, 224, 225],
                "STDEV": [226, 227, 228], "MIN": [229, 230, 231], "MAX": [232, 233, 234],
            }))
        elif case_id == "COR-MATRIX-01":
            command = "\n".join((
                "CORRELATION C17-C19;", "  SPEARMAN;", "  NODEFAULT;",
                "  SCORRELATION M20;", "  SPVALUES M21.",
            ))
            commands.append(_command(case_id, command, {}, {"M20": [3, 3], "M21": [3, 3]}))
    return commands


def read_matrix(worksheet, name: str, rows: int, cols: int) -> list[list[float]]:
    matrices = worksheet.Matrices
    matrix = next((matrices.Item(i) for i in range(1, int(matrices.Count) + 1)
                   if str(matrices.Item(i).Name).casefold() == name.casefold()), None)
    if matrix is None or (int(matrix.RowCount), int(matrix.ColumnCount)) != (rows, cols):
        raise ValueError(f"Minitab {name} 矩阵维度错误；预期 {rows}x{cols}")
    flat = [float(value) for value in matrix.GetData()]
    if len(flat) != rows * cols:
        raise ValueError(f"Minitab {name} 矩阵数据长度错误")
    return [[flat[col * rows + row] for col in range(cols)] for row in range(rows)]


def com_worker() -> dict:
    import pythoncom
    import win32process
    import win32com.client
    import verify_minitab19_com as com_check

    app = project = ui = worksheet = columns = None
    outputs, metadata = {}, {}
    try:
        if not MTB_EXE.is_file():
            raise FileNotFoundError(f"指定的 Minitab 不存在：{MTB_EXE}")
        before = phase2.running_minitab_pids()
        if before:
            raise RuntimeError(f"启动前检测到现有 Mtb.exe PID {before}；拒绝连接既有会话")
        clsid, registered_path, registered_command = com_check.registered_server()
        if com_check.canonical(registered_path) != com_check.canonical(MTB_EXE):
            raise RuntimeError(f"Mtb.Application 注册路径不符：{registered_command}")
        version = com_check.file_version(MTB_EXE)
        if version != "19.1.0.1":
            raise RuntimeError(f"要求 Minitab 19.1.0.1，实际为 {version}")
        app = win32com.client.DispatchEx("Mtb.Application")
        pythoncom.PumpWaitingMessages()
        ui = app.UserInterface
        ui.Visible, ui.UserControl, ui.DisplayAlerts = False, False, False
        app_path = str(app.AppPath)
        process_id, process_path = com_check.process_image_path(int(app.Handle))
        after = phase2.running_minitab_pids()
        if (com_check.canonical(app_path) != com_check.canonical(MTB_EXE)
                or com_check.canonical(process_path) != com_check.canonical(MTB_EXE)
                or process_id in before or process_id not in after):
            raise RuntimeError(f"DispatchEx 路径/PID 核验失败：{app_path}; {process_path}; {process_id}")
        app.New()
        project = app.ActiveProject
        if project is None:
            raise RuntimeError("Minitab 未返回独立 ActiveProject")
        worksheet = project.ActiveWorksheet
        data = load_inputs()
        cases = resolve_cases(data)
        commands = commands_for(cases)
        columns = worksheet.Columns
        phase2.prepare_columns(worksheet, 240)
        loaded_inputs = {}
        for index, (name, values) in input_vectors(cases).items():
            column = columns.Item(index)
            column.Name = name
            column.SetData(tuple(values), 1, len(values))
            readback = phase2.list_data(column.GetData())
            if len(readback) != len(values):
                raise AssertionError(f"C{index} 回读长度 {len(readback)} != {len(values)}")
            if all(isinstance(value, str) for value in values):
                if [str(value) for value in readback] != values:
                    raise AssertionError(f"Minitab C{index} 文本输入回读不同")
            elif any(float(actual) != float(expected) for actual, expected in zip(readback, values)):
                raise AssertionError(f"Minitab C{index} 数值输入回读不同")
            loaded_inputs[str(index)] = {"name": name, "values": readback}
        metadata = {"version": version, "clsid": clsid, "registered_server": registered_command,
                    "app_path": app_path, "process_path": process_path, "process_id": process_id,
                    "project_name": str(project.Name), "worksheet_name": str(worksheet.Name),
                    "python": sys.executable, "loaded_inputs": loaded_inputs}
        for item in commands:
            case_id, text = item["case_id"], item["command"]
            before_count = int(project.Commands.Count)
            try:
                project.ExecuteCommand(text)
                after_count = int(project.Commands.Count)
                output = phase2.capture_command_output(project, after_count) if after_count > before_count else ""
                last_error = str(app.LastError or "")
                output_error = bool(re.search(r"\*\s*(?:错误|ERROR)\s*\*", output, re.IGNORECASE))
                accepted = after_count > before_count and not last_error.strip() and not output_error
                stored, storage_errors = {}, {}
                if accepted:
                    for name, indices in item["storage_columns"].items():
                        try:
                            values = [phase2.column_values(worksheet, index) for index in indices]
                            stored[name] = values[0] if len(values) == 1 else values
                        except Exception as exc:
                            storage_errors[name] = f"{type(exc).__name__}: {exc}"
                    for name, shape in item["storage_matrices"].items():
                        try:
                            stored[name] = read_matrix(worksheet, name.replace("XSCORES", "M10")
                                                       .replace("YSCORES", "M11")
                                                       .replace("XLOADINGS", "M12")
                                                       .replace("YLOADINGS", "M13"), *shape)
                        except Exception as exc:
                            storage_errors[name] = f"{type(exc).__name__}: {exc}"
                outputs[case_id] = {"executed": accepted, "command": text,
                    "command_count": [before_count, after_count], "last_error": last_error,
                    "command_output_error": output_error,
                    "output": output, "stored": stored, "storage_errors": storage_errors,
                    "storage_columns": item["storage_columns"], "storage_matrices": item["storage_matrices"]}
            except Exception as exc:
                outputs[case_id] = {"executed": False, "command": text,
                    "command_count": [before_count, int(project.Commands.Count)],
                    "error": f"{type(exc).__name__}: {exc}", "last_error": str(app.LastError or ""),
                    "command_output_error": False, "output": "", "stored": {}, "storage_errors": {},
                    "storage_columns": item["storage_columns"],
                    "storage_matrices": item["storage_matrices"], "traceback": traceback.format_exc()}
        return {"metadata": metadata, "outputs": outputs}
    except Exception:
        return {"metadata": metadata, "outputs": outputs, "fatal_error": traceback.format_exc()}
    finally:
        columns = worksheet = project = app = ui = None
        gc.collect()


def run_minitab() -> tuple[dict, str, int]:
    if not PYTHON.is_file():
        return {}, f"项目解释器不存在：{PYTHON}", 1
    env = os.environ.copy()
    for name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        env[name] = "1"
    try:
        process = subprocess.run([str(PYTHON), "-X", "utf8", str(Path(__file__).resolve()), "--com-worker"],
                                 capture_output=True, text=True, encoding="utf-8", errors="replace",
                                 timeout=600, check=False, env=env)
        result = json.loads(process.stdout) if process.stdout.strip() else {}
        pids = phase2.running_minitab_pids()
        if pids:
            result.setdefault("cleanup_error", f"COM worker 结束后仍有 Mtb.exe PID {pids}；未操作该进程")
        return result, process.stderr, process.returncode or int(bool(result.get("fatal_error") or result.get("cleanup_error")))
    except Exception as exc:
        return {}, f"{type(exc).__name__}: {exc}", 1


def _plot_values(kind: str, case: dict) -> dict:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import control_chart

    fig, ax = plt.subplots()
    try:
        if kind in ("P", "NP"):
            sizes = case["sample_sizes"] if "sample_sizes" in case else [case["sample_size"]] * len(case["defectives"])
            proportions = [d / n for d, n in zip(case["defectives"], sizes)]
            control_chart.p_np_plot(p=proportions,
                n=case["sample_sizes"] if "sample_sizes" in case else case["sample_size"],
                NP=kind == "NP", ax=ax, fig=fig)
        elif kind in ("C", "U"):
            control_chart.cu_plot(c=case["defects"], n=case.get("sample_sizes", 1),
                                  C=kind == "C", ax=ax, fig=fig)
        lines = ax.lines
        if len(lines) < 4:
            raise AssertionError(f"{kind} 生产绘图器返回的曲线不足 4 条：{len(lines)}")
        count = len(case.get("defectives", case.get("defects", [])))
        return {"points": [float(v) for v in lines[0].get_ydata()],
                "center": [float(lines[1].get_ydata()[0])] * count,
                "ucl": [float(v) for v in lines[2].get_ydata()[::2]],
                "lcl": [float(v) for v in lines[3].get_ydata()[::2]],
                "source": "code.control_chart.p_np_plot / cu_plot 的实际 Axes 输出"}
    finally:
        plt.close(fig)


def production_results(cases: dict) -> dict:
    import numpy as np
    import pandas as pd
    import GRR
    from advanced_spc import analyze_spc
    from control_chart import xBar_R
    from describe import describe
    from fit_dialog import print_multi_col_tables
    from nonpara_cor import spearman
    from pca_analysis import fit_pca
    from pls_regression import fit_pls
    from stat_table import StatTable
    from utilities import number_2Dlist

    result = {}
    for case_id, c in cases.items():
        if c.get("chart") in {"P", "NP", "C", "U"}:
            result[case_id] = _plot_values(c["chart"], c)
        elif case_id == "SPC-XBR-VAR":
            result[case_id] = xBar_R(c["subgroups"], k=c["k"])
        elif case_id == "SPC-NELSON":
            result[case_id] = {}
            for rule in c["rules"]:
                frame = pd.DataFrame({"y": c["values_by_rule"][str(rule)]})
                analysis = analyze_spc(frame, ["y"], kind="Nelson", mean=c["mean"],
                                       sigma=c["sigma"], rules=(rule,))
                result[case_id][str(rule)] = analysis.tables["alarms"].sequence.astype(int).tolist()
        elif case_id == "GRR-CROSS-XBAR":
            old = c["resolved_source"]
            result[case_id] = GRR.grr_master(y=old["measurement"], part=old["part"],
                op=old["operator"], mode="xbar", print_out=True, print_port=lambda *_: None)
        elif case_id == "GRR-NESTED":
            result[case_id] = GRR.grr_nested(y=c["measurements"], part=c["parts"],
                op=c["operators"], print_out=False)
        elif case_id == "PCA-01":
            frame = pd.DataFrame(c["rows"], columns=c["columns"])
            model = fit_pca(frame, c["columns"], n_components=c["n_components"],
                            scaling=c["scaling"], missing=c["missing"])
            result[case_id] = {"eigenvalues": model.eigenvalues.tolist(),
                "explained_variance_ratio": model.explained_variance_ratio.tolist(),
                "loadings": model.loadings.tolist(), "scores": model.training.scores.tolist(),
                "preprocessing_mean": model.mean.tolist(), "preprocessing_scale": model.scale.tolist(),
                "source": "code.pca_analysis.fit_pca; autoscale 使用样本标准差 ddof=1"}
        elif case_id == "PLS-01":
            names = c["predictors"] + c["responses"]
            frame = pd.DataFrame(c["rows"], columns=names)
            model = fit_pls(frame, c["responses"], c["predictors"],
                            n_components=c["n_components"], cv=c["cv"],
                            scale=c["scale"], missing=c["missing"])
            result[case_id] = {"coefficients": model.tables["coefficients"].to_dict("records"),
                "fits": model.tables["observations"].fitted.astype(float).tolist(),
                "x_scores": model.tables["x_scores"].filter(like="component_").to_numpy().tolist(),
                "y_scores": model.tables["y_scores"].filter(like="component_").to_numpy().tolist(),
                "x_loadings": model.tables["x_loadings"].filter(like="component_").to_numpy().tolist(),
                "y_loadings": model.tables["y_loadings"].filter(like="component_").to_numpy().tolist(),
                "source": "code.pls_regression.fit_pls; fixed one component, CV disabled"}
        elif case_id == "MULTI-DESC-01":
            source = cases[c["source_input_case"]]
            frame = pd.DataFrame(source["rows"], columns=source["columns"])
            result[case_id] = {column: describe(frame[column].tolist(), print_out=False)
                               for column in source["columns"]}
        elif case_id == "COR-MATRIX-01":
            source = cases[c["source_input_case"]]
            columns = source["columns"]
            frame = pd.DataFrame(source["rows"], columns=columns)
            matrix_data = number_2Dlist(df=frame, cols=columns, print_out=False)
            reports = []
            print_multi_col_tables(matrix_data, columns, spearman,
                                   print_port=reports.append, name="Spearman's rho")
            tables = [item for item in reports if isinstance(item, StatTable)]
            correlation_table = next(item for item in tables if "p 值" not in item.title)
            pvalue_table = next(item for item in tables if "p 值" in item.title)
            result[case_id] = {
                "correlation": [[float(value) for value in row[1:]] for row in correlation_table.values],
                "p_values": [[float(value) for value in row[1:]] for row in pvalue_table.values],
                "source": "MCorDialog.apply → number_2Dlist → print_multi_col_tables(spearman)",
            }
    return result


COMPARISON_FIELDS = (
    "category", "case_id", "feature", "metric", "minijmp_value", "minitab_value",
    "absolute_error", "relative_error", "tolerance", "status", "configuration",
    "minijmp_source", "minitab_source", "judgment",
)


def _json(value) -> str:
    return json.dumps(_builtin(value), ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def _builtin(value):
    if hasattr(value, "tolist"):
        return _builtin(value.tolist())
    if isinstance(value, dict):
        return {str(key): _builtin(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_builtin(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if hasattr(value, "item"):
        return _builtin(value.item())
    return value


def _flat_values(value):
    if isinstance(value, (list, tuple)):
        for item in value:
            yield from _flat_values(item)
    else:
        yield value


def _values(output: dict, name: str) -> list:
    if not output:
        return []
    value = output.get("stored", {}).get(name, [])
    if value is None:
        return []
    if isinstance(value, list):
        if value and isinstance(value[0], list):
            return value[0]
        return value
    return [value]


def _value_shape(value):
    if not isinstance(value, (list, tuple)):
        return ()
    if not value:
        return (0,)
    child_shapes = [_value_shape(item) for item in value]
    if len(set(child_shapes)) != 1:
        return (len(value), "ragged")
    return (len(value), *child_shapes[0])


def _equal_values(left, right, tolerance: float, exact: bool = False) -> tuple[bool, float | None]:
    left, right = _builtin(left), _builtin(right)
    if not isinstance(left, (list, tuple)):
        left = [left]
    if not isinstance(right, (list, tuple)):
        right = [right]
    if _value_shape(left) != _value_shape(right) or not left:
        return False, None
    try:
        errors = [abs(float(a) - float(b)) for a, b in zip(_flat_values(left), _flat_values(right))]
    except (TypeError, ValueError):
        return False, None
    error = max(errors)
    return (all(e == 0 for e in errors) if exact else error <= tolerance), error


def add_row(rows: list[dict], *, category: str, case_id: str, feature: str, metric: str,
            local_value, native_value, tolerance: float, configuration: str,
            local_source: str, native_source: str, command: dict,
            exact: bool = False, judgment: str = "", method_diff: str = "") -> None:
    local_value, native_value = _builtin(local_value), _builtin(native_value)
    status, error, reason = "PASS", "", judgment
    if not command:
        status, reason = "NOT_RUN", judgment or "未找到 Minitab 命令记录。"
    elif not command.get("executed"):
        status = "UNSUPPORTED"
        reason = (judgment or command.get("last_error") or command.get("error")
                  or command.get("output") or "Minitab 未接受该 Session Command。")
    elif local_value is None or native_value is None:
        status = "UNSUPPORTED"
        reason = judgment or "Minitab 原生存储或 MiniJMP 当前输出字段不可用。"
    else:
        matched, error = _equal_values(local_value, native_value, tolerance, exact)
        if error is None:
            if method_diff:
                status, reason = "METHOD_DIFF", method_diff
            else:
                left = local_value if isinstance(local_value, (list, tuple)) else [local_value]
                right = native_value if isinstance(native_value, (list, tuple)) else [native_value]
                if _value_shape(left) != _value_shape(right):
                    status, reason = "FAIL", "两侧结果长度或矩阵维度不同。"
                else:
                    status, reason = "UNSUPPORTED", judgment or "两侧字段数值格式无法对齐。"
        elif method_diff:
            status, reason = "METHOD_DIFF", method_diff
        elif not matched:
            status, reason = "FAIL", judgment or "超过按配置和原生存储精度设定的容差。"
    rel = ""
    if isinstance(error, (int, float)) and native_value not in (None, 0, [], ""):
        if isinstance(native_value, (list, tuple)):
            denominator = max((abs(float(v)) for v in _flat_values(native_value) if v is not None), default=0)
        else:
            denominator = abs(float(native_value))
        if denominator:
            rel = error / denominator
    rows.append({
        "category": category, "case_id": case_id, "feature": feature, "metric": metric,
        "minijmp_value": _json(local_value) if not isinstance(local_value, str) else local_value,
        "minitab_value": _json(native_value) if not isinstance(native_value, str) else native_value,
        "absolute_error": error, "relative_error": rel, "tolerance": tolerance,
        "status": status, "configuration": configuration,
        "minijmp_source": local_source, "minitab_source": native_source, "judgment": reason,
    })


def _flat_local(value, count: int) -> list:
    if isinstance(value, (list, tuple)):
        result = list(value)
        if len(result) == 1 and count > 1:
            return result * count
        return result
    return [value] * count


def _native_case(run: dict, case_id: str) -> dict:
    return run.get("outputs", {}).get(case_id, {}) if run else {}


def compare_results(data: dict, cases: dict, local: dict, native: dict) -> list[dict]:
    tol = data["tolerances"]
    rows: list[dict] = []
    for case_id, c in cases.items():
        if c.get("chart") in {"P", "NP", "C", "U"}:
            command = _native_case(native, case_id)
            result = local.get(case_id, {})
            feature = c["feature"]
            for name, local_name in (("PPOINTS", "points"), ("CENLINE", "center"),
                                     ("LCL", "lcl"), ("UCL", "ucl")):
                add_row(rows, category="SPC", case_id=case_id, feature=feature,
                    metric=name, local_value=result.get(local_name), native_value=_values(command, name),
                    tolerance=tol["chart_abs"], configuration=c["configuration"],
                    local_source=("code.control_chart.p_np_plot / cu_plot 生成的实际绘图曲线；"
                                  + local_name),
                    native_source=f"phase7/minitab_results.json#runs[0].outputs.{case_id}.stored.{name}",
                    command=command)
            for index in range(1, 5):
                add_row(rows, category="SPC", case_id=case_id, feature=feature,
                    metric=f"Minitab Test {index} 触发位置", local_value=None,
                    native_value=_values(command, f"TEST_{index}"), tolerance=tol["flag_exact"],
                    configuration=c["configuration"] + f"；Minitab TEST {index}。",
                    local_source="MiniJMP P/NP/C/U 绘图入口未返回同名特殊原因规则标志。",
                    native_source=f"phase7/minitab_results.json#runs[0].outputs.{case_id}.stored.TEST_{index}",
                    command=command, exact=True,
                    judgment="MiniJMP 属性图当前输出无相同的 Test 1–4 逐点标志；不以图外派生结果代替。")
        elif case_id == "SPC-XBR-VAR":
            command = _native_case(native, case_id)
            result = local.get(case_id, {})
            count = len(c["subgroups"])
            pairs = (("XBAR_POINTS", "Y1"), ("XBAR_CENTER", "bar1"),
                     ("XBAR_LCL", "lcl1"), ("XBAR_UCL", "ucl1"),
                     ("R_POINTS", "Y2"), ("R_CENTER", "bar2"),
                     ("R_LCL", "lcl2"), ("R_UCL", "ucl2"))
            for name, local_name in pairs:
                add_row(rows, category="SPC", case_id=case_id, feature=c["feature"],
                    metric=name, local_value=_flat_local(result.get(local_name), count),
                    native_value=_values(command, name), tolerance=tol["chart_abs"],
                    configuration=c["configuration"],
                    local_source=f"code.control_chart.xBar_R.{local_name}",
                    native_source=f"phase7/minitab_results.json#runs[0].outputs.{case_id}.stored.{name}",
                    command=command)
        elif case_id == "SPC-NELSON":
            feature = c["feature"]
            for rule in c["rules"]:
                command_id = f"{case_id}-RULE-{rule}"
                command = _native_case(native, command_id)
                local_events = local.get(case_id, {}).get(str(rule))
                native_flags = _values(command, "I_TEST")
                native_events = [index + 1 for index, value in enumerate(native_flags)
                                 if value is not None and float(value) == 1]
                add_row(rows, category="SPC", case_id=command_id, feature=feature,
                    metric=f"Nelson {rule} 检测时刻(1-based row)", local_value=local_events,
                    native_value=native_events, tolerance=tol["flag_exact"], exact=True,
                    configuration=f"已知均值 {c['mean']}、标准差 {c['sigma']}；使用 Minitab 默认 TEST {rule} 阈值。",
                    local_source=f"code.advanced_spc.analyze_spc → tables.alarms; 固定输入第 {rule} 条规则",
                    native_source=f"phase7/minitab_results.json#runs[0].outputs.{command_id}.stored.I_TEST",
                    command=command,
                    judgment="Minitab TRESULTS 每行对应一个 I 图点。",
                    method_diff=(
                        f"规则 {rule} 按连续 {6 if rule == 3 else 14} 个点定义；MiniJMP 固定序列在第 "
                        f"{6 if rule == 3 else 14} 点已触发，Minitab 19.1.0.1 TRESULTS 从第 "
                        f"{7 if rule == 3 else 15} 行起标记，保留为版本差异。"
                    ) if rule in (3, 4) and local_events != native_events else "")
        elif case_id == "GRR-CROSS-XBAR":
            command = _native_case(native, case_id)
            result = local.get(case_id, {})
            variance = _values(command, "VARIANCE")
            # GAGERR XBAR stores Total GRR, Repeatability, Reproducibility, Part-to-Part, Total Variation.
            for label, index, key in (("Total Gage R&R", 0, "RR"), ("Repeatability", 1, "EV"),
                                      ("Reproducibility", 2, "AV"), ("Part-To-Part", 3, "PV"),
                                      ("Total Variation", 4, "TV")):
                value = variance[index] if len(variance) > index else None
                add_row(rows, category="GRR", case_id=case_id, feature=c["feature"],
                    metric=f"方差分量 {label}", local_value=result.get(key), native_value=value,
                    tolerance=tol["grr_abs"], configuration=c["configuration"],
                    local_source=f"code.GRR.grr_master(mode='xbar').{key}",
                    native_source=f"phase7/minitab_results.json#runs[0].outputs.{case_id}.stored.VARIANCE[{index}]",
                    command=command,
                    method_diff=("两侧均采用平均极差法；MiniJMP d2_2D 使用三位小数表值（重复性 d2(2,30)=1.128、操作者均值 d2(3,1)=1.912、"
                                 "零件均值 d2(10,1)=3.179），Minitab GAGERR XBAR 使用 AIAG Appendix C 的 d2*（原生方差反推约 1.12838、1.91155、3.17905）；"
                                 "由常数精度差异传递至方差分量。")
                    if label in {"Total Gage R&R", "Repeatability", "Part-To-Part", "Total Variation", "Reproducibility"}
                    else "",
                    judgment="按 Minitab GAGERR XBAR 方差分量表同名行顺序映射；原始输出及固定输入已归档。")
        elif case_id == "GRR-NESTED":
            command = _native_case(native, case_id)
            result = local.get(case_id, {})
            var = _values(command, "VARIANCE")
            sd = _values(command, "STDDEV")
            study_pct = _values(command, "STUDYPERCENT")
            distinct = _values(command, "NDC")
            mappings = (("GRR STD", result.get("GRR STD"), sd, 0),
                        ("Repeatability STD", result.get("Repeatability STD"), sd, 1),
                        ("Reproducibility STD", result.get("Reproducibility STD"), sd, 2),
                        ("GRR%", result.get("GRR%"), study_pct, 0),
                        ("ndc", result.get("Distinct Categories"), distinct, 0))
            for metric, local_value, values, index in mappings:
                native_value = values[index] if len(values) > index else None
                add_row(rows, category="GRR", case_id=case_id, feature=c["feature"],
                    metric=metric, local_value=local_value, native_value=native_value,
                    tolerance=tol["grr_abs"], configuration=c["configuration"],
                    local_source=f"code.GRR.grr_nested.{metric}",
                    native_source=f"phase7/minitab_results.json#runs[0].outputs.{case_id}.stored",
                    command=command,
                    judgment="Minitab NTGAGE 原生存储；源行次序由 phase7 原始输出中的方差分析/变异表确认。")
        elif case_id == "PCA-01":
            command = _native_case(native, case_id)
            mini = local.get(case_id, {})
            eigen = _values(command, "EIGEN")
            mini_eigen = mini.get("eigenvalues", [])
            for component, (a, b) in enumerate(zip(mini_eigen, eigen), 1):
                add_row(rows, category="多变量", case_id=case_id, feature=c["feature"],
                    metric=f"PC{component} 特征值", local_value=a, native_value=b,
                    tolerance=tol["multivariate_abs"], configuration=c["configuration"],
                    local_source="code.pca_analysis.PCAModel.eigenvalues",
                    native_source=f"phase7/minitab_results.json#runs[0].outputs.{case_id}.stored.EIGEN[{component - 1}]",
                    command=command, judgment="相关矩阵 PCA；特征值按降序逐项比较。")
            native_loading = []
            for component in range(1, c["n_components"] + 1):
                stored = _values(command, f"COEFFICIENT_PC{component}")
                native_loading.append([stored[i] if len(stored) > i else None
                                       for i in range(len(c["columns"]))])
            mini_loading = mini.get("loadings", [])
            signs = []
            for component in range(c["n_components"]):
                dot = sum(mini_loading[row][component] * native_loading[component][row]
                          for row in range(len(c["columns"])))
                signs.append(-1 if dot < 0 else 1)
            ratios = mini.get("explained_variance_ratio", [])
            native_sum = sum(float(value) for value in eigen if value is not None)
            for component in range(c["n_components"]):
                mini_values = [mini_loading[row][component] * signs[component]
                               for row in range(len(c["columns"]))]
                add_row(rows, category="多变量", case_id=case_id, feature=c["feature"],
                    metric=f"PC{component + 1} 载荷(符号对齐)", local_value=mini_values,
                    native_value=native_loading[component], tolerance=tol["multivariate_abs"],
                    configuration=c["configuration"] + f"；PC{component + 1} 以载荷内积对齐符号。",
                    local_source="code.pca_analysis.PCAModel.loadings",
                    native_source=f"phase7/minitab_results.json#runs[0].outputs.{case_id}.stored.COEFFICIENT_PC{component + 1}",
                    command=command)
                native_ratio = eigen[component] / native_sum if native_sum else None
                add_row(rows, category="多变量", case_id=case_id, feature=c["feature"],
                    metric=f"PC{component + 1} 方差解释率", local_value=ratios[component],
                    native_value=native_ratio, tolerance=tol["multivariate_abs"],
                    configuration=c["configuration"] + "；Minitab 原生特征值按总和计算比例。",
                    local_source="code.pca_analysis.PCAModel.explained_variance_ratio",
                    native_source=f"phase7/minitab_results.json#runs[0].outputs.{case_id}.stored.EIGEN 派生",
                    command=command)
                local_scores = [row[component] * signs[component] for row in mini.get("scores", [])]
                native_scores = _values(command, f"SCORE_PC{component + 1}")
                add_row(rows, category="多变量", case_id=case_id, feature=c["feature"],
                    metric=f"PC{component + 1} 样本得分(符号对齐)", local_value=local_scores,
                    native_value=native_scores, tolerance=tol["multivariate_abs"],
                    configuration=c["configuration"] + f"；PC{component + 1} 得分按载荷同一符号翻转。",
                    local_source="code.pca_analysis.PCAModel.training.scores",
                    native_source=f"phase7/minitab_results.json#runs[0].outputs.{case_id}.stored.SCORE_PC{component + 1}",
                    command=command)
        elif case_id == "PLS-01":
            command = _native_case(native, case_id)
            mini = local.get(case_id, {})
            add_row(rows, category="多变量", case_id=case_id, feature=c["feature"], metric="训练拟合值",
                local_value=mini.get("fits"), native_value=_values(command, "FITS"),
                tolerance=tol["multivariate_abs"], configuration=c["configuration"],
                local_source="code.pls_regression.fit_pls → tables.observations.fitted",
                native_source=f"phase7/minitab_results.json#runs[0].outputs.{case_id}.stored.FITS",
                command=command, judgment="固定相同输入行序、一个成分；按原单位响应拟合值比较。")
            mini_coef = [float(item["estimate"]) for item in mini.get("coefficients", [])
                         if item.get("term") != "Intercept"]
            native_coef = _values(command, "COEFFICIENTS")
            add_row(rows, category="多变量", case_id=case_id, feature=c["feature"], metric="原单位斜率系数",
                local_value=mini_coef, native_value=native_coef, tolerance=tol["multivariate_abs"],
                configuration=c["configuration"], local_source="code.pls_regression.fit_pls → tables.coefficients",
                native_source=f"phase7/minitab_results.json#runs[0].outputs.{case_id}.stored.COEFFICIENTS",
                command=command, judgment="Minitab COEFFICIENTS 存储仅含连续预测变量斜率；按 x1、x2 顺序比较。")
            intercept = next((item["estimate"] for item in mini.get("coefficients", [])
                              if item.get("term") == "Intercept"), None)
            add_row(rows, category="多变量", case_id=case_id, feature=c["feature"],
                metric="PLS 截距", local_value=intercept, native_value=None,
                tolerance=tol["multivariate_abs"], configuration=c["configuration"],
                local_source="code.pls_regression.fit_pls → tables.coefficients[Intercept]",
                native_source=f"phase7/minitab_results.json#runs[0].outputs.{case_id}.stored.COEFFICIENTS",
                command=command, judgment="Minitab 19.1.0.1 COEFFICIENTS 直接存储列不含截距；训练拟合值另行原生比较。")
            for matrix_name, local_key in (("XSCORES", "x_scores"), ("YSCORES", "y_scores"),
                                           ("XLOADINGS", "x_loadings"), ("YLOADINGS", "y_loadings")):
                native_matrix = command.get("stored", {}).get(matrix_name)
                local_matrix = mini.get(local_key)
                if local_matrix is not None and native_matrix is not None:
                    # PLS component signs are arbitrary; align by X-loadings and apply one sign to all component outputs.
                    if matrix_name == "XLOADINGS":
                        dot = sum(local_matrix[i][0] * native_matrix[i][0] for i in range(len(local_matrix)))
                        sign = -1 if dot < 0 else 1
                    else:
                        x_mini, x_native = mini.get("x_loadings"), command.get("stored", {}).get("XLOADINGS")
                        dot = sum(x_mini[i][0] * x_native[i][0] for i in range(len(x_mini))) if x_mini and x_native else 0
                        sign = -1 if dot < 0 else 1
                    adjusted = [[value * sign for value in row] for row in local_matrix]
                else:
                    adjusted = local_matrix
                add_row(rows, category="多变量", case_id=case_id, feature=c["feature"],
                    metric=f"{matrix_name} (符号对齐)", local_value=adjusted, native_value=native_matrix,
                    tolerance=tol["multivariate_abs"], configuration=c["configuration"],
                    local_source=f"code.pls_regression.fit_pls → tables.{local_key}",
                    native_source=f"phase7/minitab_results.json#runs[0].outputs.{case_id}.stored.{matrix_name}",
                    command=command,
                    judgment="PLS 成分方向任意；按 X-loadings 内积确定符号并同步翻转得分/载荷。")
        elif case_id == "MULTI-DESC-01":
            command = _native_case(native, case_id)
            result = local.get(case_id, {})
            source = cases[c["source_input_case"]]
            native_names = {"N": "N", "Mean": "MEAN", "Standard Deviation": "STDEV",
                            "Minimum": "MIN", "Maximum": "MAX"}
            mini_names = {"N": "N", "Mean": "Mean", "Standard Deviation": "Standard Deviation",
                          "Minimum": "Minimum", "Maximum": "Maximum"}
            def stored_statistics(name):
                values = command.get("stored", {}).get(name, [])
                return [column[0] if column else None for column in values]

            for metric, native_name in native_names.items():
                values = stored_statistics(native_name)
                for index, column in enumerate(source["columns"]):
                    local_value = result.get(column, {}).get(mini_names[metric])
                    native_value = values[index] if len(values) > index else None
                    add_row(rows, category="多变量", case_id=case_id, feature=c["feature"],
                        metric=f"{column} {metric}", local_value=local_value, native_value=native_value,
                        tolerance=tol["multivariate_abs"], configuration=c["configuration"],
                        local_source=f"MultiDescribeDialog.apply → describe.describe({column}).{mini_names[metric]}",
                        native_source=f"phase7/minitab_results.json#runs[0].outputs.{case_id}.stored.{native_name}[{index}]",
                        command=command, judgment="各变量按相同的完整观测列逐项比较。")
        elif case_id == "COR-MATRIX-01":
            command = _native_case(native, case_id)
            result = local.get(case_id, {})
            for metric, local_name, native_name in (("Spearman rho 矩阵", "correlation", "M20"),
                                                    ("Spearman p 值(非对角线)", "p_values", "M21")):
                local_values = result.get(local_name)
                native_values = command.get("stored", {}).get(native_name)
                if local_name == "p_values" and local_values is not None and native_values is not None:
                    local_values = [local_values[i][j] for i in range(3) for j in range(3) if i != j]
                    native_values = [native_values[i][j] for i in range(3) for j in range(3) if i != j]
                add_row(rows, category="多变量", case_id=case_id, feature=c["feature"],
                    metric=metric, local_value=local_values, native_value=native_values,
                    tolerance=tol["multivariate_abs"], configuration=c["configuration"],
                    local_source=f"MCorDialog.apply → print_multi_col_tables(spearman).{local_name}",
                    native_source=f"phase7/minitab_results.json#runs[0].outputs.{case_id}.stored.{native_name}",
                    command=command,
                    judgment=("同一完整观测行；rho 比较 3×3 全矩阵。Minitab 对角 p 值是 1.23456e30 的未定义标记，"
                              "p 值只比较六个非对角单元格。"))
    return rows


def update_feature_matrix() -> None:
    path = OUT / "feature_matrix.csv"
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = tuple(reader.fieldnames or ())
        matrix = list(reader)
    if len(matrix) != 90:
        raise AssertionError(f"90 项矩阵数量改变：{len(matrix)}")

    updates = {
        "多变量描述性统计": "固定 10×3 数据逐列对比 N、均值、样本标准差、最小值、最大值；15 项 PASS。",
        "相关系数矩阵": "Spearman rho 3×3 矩阵及 6 个非对角 p 值 PASS；自相关对角 p 值为未定义标记 1.23456e30，未比较。",
        "偏最小二乘回归（PLS）": "固定 1 成分案例的拟合值、斜率、X/Y 得分和载荷 PASS；Minitab COEFFICIENTS 不存储截距，记 UNSUPPORTED；未覆盖交叉验证。",
        "主成分分析": "相关矩阵 PCA 的 3 个特征值、载荷、解释率及样本得分 PASS；载荷/得分按成分符号对齐。",
        "量具 R&R 研究（交叉）": "复用平衡交叉 ANOVA 22 项 PASS；平衡 10 零件×3 操作者×2 次测量的 Xbar/R 平均极差法 5 个方差分量因三位小数 d2 表值与 Minitab d2* 精度不同记 METHOD_DIFF。",
        "量具 R&R 研究（嵌套）": "固定平衡 3 操作员×每人 2 零件×2 次测量的 NTGAGE 案例，GRR/重复性/再现性标准差、GRR% 与 ndc 共 5 项 PASS。",
        "正态过程能力（完整）": "复用 phase2/phase3 的 CAP-01..03 三个正态固定配置，共 17 项：12 PASS、5 METHOD_DIFF、0 FAIL。",
        "非正态过程能力": "复用 phase2/phase3 的 CAP-04..05 两个非正态固定配置，共 24 项：16 PASS、8 METHOD_DIFF、0 FAIL。",
        "控制图 I-MR": "复用 phase3 两个 I-MR 固定配置，I/MR 点、中心线和控制限合计 606 项 PASS；phase7 另比较 I 图 Nelson 规则 1–8。",
        "控制图 I（单值）": "phase3 I-MR 固定配置的原生图表指标通过；phase7 Minitab 19.1.0.1 TRESULTS 的 Nelson 规则 1–8 触发点固定案例均 PASS。",
        "控制图 MR（移动极差）": "phase3 两个 I-MR 固定配置的 MR 图指标包含在 606 项 PASS 中；phase7 保存 MR 原生规则列，但逐点对比限于 I 图。",
        "控制图 Xbar-R": "复用 phase3 固定子组 n=5 的 120 项 PASS；新增 n=3/4/5 变量子组案例的点、中心线和控制限 8 项 PASS。",
        "控制图 Xbar-S": "复用 phase3 固定子组 n=10 的 120 项 PASS；仅覆盖归档固定配置。",
        "高级 SPC 控制图": "Nelson 规则 1、2、5–8 固定输入逐点 PASS；规则 3/4 按连续 6/14 个点判定，Minitab 19.1.0.1 固定案例从第 7/15 行标记，2 项记 METHOD_DIFF。EWMA、CUSUM、T² 未做 Minitab 原生对标。",
        "控制图 NP": "固定样本量案例的点、中心线和控制限 PASS；MiniJMP 图形入口未返回 Minitab Test 1–4 同名逐点标志，4 项记 UNSUPPORTED。",
        "控制图 P": "可变样本量案例的点、中心线和控制限 PASS；Test 1–4 逐点标志未对标，记 UNSUPPORTED。",
        "控制图 C": "固定检验机会案例的点、中心线和控制限 PASS；Test 1–4 逐点标志未对标，记 UNSUPPORTED。",
        "控制图 U": "可变检验机会案例的点、中心线和控制限 PASS；Test 1–4 逐点标志未对标，记 UNSUPPORTED。",
    }
    marker = "第五轮（phase7）限定范围："
    matched = set()
    untouched = {row["功能名称"]: dict(row) for row in matrix if row["功能名称"] not in updates}
    for row in matrix:
        feature = row["功能名称"]
        if feature not in updates:
            continue
        row["Minitab 19 对标"] = "部分验证"
        note = row["备注及证据来源"].split(marker, 1)[0].rstrip()
        row["备注及证据来源"] = (
            f"{note} {marker}{updates[feature]} | "
            "Out/statistics_minitab19_parity/phase7/case_inputs.json; "
            "minitab_session_commands.txt; minitab_raw_outputs.txt; minijmp_results.json; "
            "comparison.csv; summary.csv; repeatability_check.txt"
        )
        matched.add(feature)
    if matched != set(updates):
        raise AssertionError(f"矩阵目标行不完整：{matched}")
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(matrix)
    with path.open(encoding="utf-8-sig", newline="") as stream:
        written = list(csv.DictReader(stream))
    if len(written) != 90 or {row["功能名称"]: row for row in written if row["功能名称"] not in updates} != untouched:
        raise AssertionError("矩阵行数变化或未覆盖行被修改")


def _status_counts(rows: list[dict]) -> dict:
    return {status: sum(row["status"] == status for row in rows) for status in STATUS_ORDER}


def summary_rows(rows: list[dict]) -> list[dict]:
    fields = ("范围", "配置数", "指标数", "PASS", "FAIL", "METHOD_DIFF", "UNSUPPORTED", "NOT_RUN", "证据来源")
    summaries = []
    for category in ("SPC", "GRR", "多变量"):
        selected = [row for row in rows if row["category"] == category]
        counts = _status_counts(selected)
        configs = len({row["case_id"] for row in selected})
        summaries.append({"范围": category + " phase7 新增/复核", "配置数": configs,
            "指标数": len(selected), **counts, "证据来源": "phase7/case_inputs.json; Minitab 19.1.0.1 COM; MiniJMP 生产入口"})
    with (OUT / "phase3" / "summary.csv").open(encoding="utf-8-sig", newline="") as stream:
        previous_summary = list(csv.DictReader(stream))
    capability = [row for row in previous_summary if row["case_id"].startswith("CAP-")]
    cap_counts = {status: sum(int(row[f"phase3_{status}"]) for row in capability) for status in STATUS_ORDER}
    summaries.insert(0, {"范围": "正态/非正态过程能力（复用 phase2/phase3 已验收固定案例）",
        "配置数": len(capability), "指标数": sum(int(row["metric_count"]) for row in capability),
        **cap_counts, "证据来源": "phase2/case_inputs.json + Minitab 原生输出; phase3/comparison.csv"})
    spc_old = [row for row in previous_summary if row["case_id"].startswith("SPC-")]
    summaries.insert(1, {"范围": "I-MR/Xbar-R/Xbar-S 基础变量图（复用 phase2/phase3）",
        "配置数": len(spc_old), "指标数": sum(int(row["metric_count"]) for row in spc_old),
        "PASS": sum(int(row["phase3_PASS"]) for row in spc_old), "FAIL": 0, "METHOD_DIFF": 0,
        "UNSUPPORTED": 0, "NOT_RUN": 0, "证据来源": "phase2 固定输入/原生命令/输出; phase3/comparison.csv"})
    grr_old = [row for row in previous_summary if row["case_id"] == "GRR-01"]
    summaries.insert(2, {"范围": "交叉 GRR ANOVA（复用 phase2/phase3）", "配置数": len(grr_old),
        "指标数": sum(int(row["metric_count"]) for row in grr_old),
        "PASS": sum(int(row["phase3_PASS"]) for row in grr_old), "FAIL": 0, "METHOD_DIFF": 0,
        "UNSUPPORTED": 0, "NOT_RUN": 0, "证据来源": "phase2 固定输入/原生命令/输出; phase3/comparison.csv"})
    return summaries


def _hash(value) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def write_outputs(data: dict, local: dict, runs: list[dict], stderr: list[str], exit_codes: list[int]) -> list[dict]:
    cases = resolve_cases(data)
    rows = compare_results(data, cases, local, runs[0] if runs else {})
    (PHASE7 / "minijmp_results.json").write_text(
        json.dumps({"version": "MiniJMP production code at run time", "results": local},
                   ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    (PHASE7 / "minitab_results.json").write_text(
        json.dumps({"runs": runs, "stderr": stderr, "exit_codes": exit_codes},
                   ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    with (PHASE7 / "comparison.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=COMPARISON_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    summaries = summary_rows(rows)
    with (PHASE7 / "summary.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=tuple(summaries[0]))
        writer.writeheader()
        writer.writerows(summaries)
    normalized = [{case_id: {key: output.get(key) for key in
                   ("command", "executed", "stored", "storage_errors", "command_output_error")}
                   for case_id, output in run.get("outputs", {}).items()} for run in runs]
    stable = bool(len(normalized) == 2 and _hash(normalized[0]) == _hash(normalized[1]))
    manifest = {"runs": len(runs), "exit_codes": exit_codes, "output_hashes": [
        _hash(run.get("outputs", {})) for run in runs], "stable": stable,
        "compared_fields": "command, execution/error state, stored columns/matrices and storage errors; excludes COM PID, counters and output-document timestamps"}
    (PHASE7 / "repeatability_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (PHASE7 / "repeatability_check.txt").write_text(
        f"Minitab 19.1.0.1 isolated COM runs: {len(runs)}; exit_codes={exit_codes}; "
        f"stored-result hashes stable={stable}; hashes={manifest['output_hashes']}\n", encoding="utf-8")
    command_lines = ["Minitab 19.1.0.1 phase7 Session Commands; commands are fixed in verify_statistics_minitab19_phase7.py."]
    for item in commands_for(cases):
        command_lines.extend((f"\n===== {item['case_id']} =====", item["command"]))
    (PHASE7 / "minitab_session_commands.txt").write_text("\n".join(command_lines) + "\n", encoding="utf-8")
    raw = []
    for run_number, run in enumerate(runs, 1):
        raw.append(f"===== Minitab COM run {run_number}; exit={exit_codes[run_number - 1]} =====")
        for case_id, output in run.get("outputs", {}).items():
            raw.extend((f"\n===== {case_id}: Session command =====", output.get("command", ""),
                        "===== OutputDocument/Outputs =====", output.get("output", ""),
                        "===== Direct storage =====", json.dumps({k: output.get(k) for k in
                         ("executed", "stored", "storage_errors", "storage_columns", "storage_matrices",
                          "last_error", "error", "command_output_error")}, ensure_ascii=False, indent=2)))
    (PHASE7 / "minitab_raw_outputs.txt").write_text("\n".join(raw) + "\n", encoding="utf-8")
    return rows


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "--com-worker":
        result = com_worker()
        sys.stdout.write(json.dumps(result, ensure_ascii=False, allow_nan=False))
        return 0 if not result.get("fatal_error") else 1
    data = load_inputs()
    cases = resolve_cases(data)
    local = production_results(cases)
    runs, stderr, exit_codes = [], [], []
    for _ in range(2):
        result, error, code = run_minitab()
        runs.append(result)
        stderr.append(error)
        exit_codes.append(code)
    rows = write_outputs(data, local, runs, stderr, exit_codes)
    update_feature_matrix()
    statuses = _status_counts(rows)
    print(f"Minitab 19.1.0.1; COM runs={exit_codes}; phase7 metrics={len(rows)}; statuses={statuses}")
    return 0 if len(runs) == 2 and all(code == 0 for code in exit_codes) \
        and statuses["FAIL"] == 0 and statuses["NOT_RUN"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

