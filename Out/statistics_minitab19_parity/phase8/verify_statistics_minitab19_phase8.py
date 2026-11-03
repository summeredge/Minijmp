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


PHASE8 = Path(__file__).resolve().parent
ROOT = PHASE8.parents[2]
OUT = PHASE8.parent
PHASE7 = OUT / "phase7"
PHASE2 = OUT / "phase2"
INPUT = PHASE8 / "case_inputs.json"
MATRIX = OUT / "feature_matrix.csv"
MTB_EXE = Path(r"D:\Program\Minitab 19\Mtb.exe")
PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
STATUS_ORDER = ("PASS", "FAIL", "METHOD_DIFF", "UNSUPPORTED", "NOT_RUN")
ATTRIBUTE_PHASE7_CASES = ("SPC-P", "SPC-NP", "SPC-C", "SPC-U")
ATTRIBUTE_EDGE_CASES = ("ATTR-P-EDGE", "ATTR-NP-EDGE", "ATTR-C-EDGE", "ATTR-U-EDGE")
ATTRIBUTE_RULE_CASES = ("ATTR-P-RULES", "ATTR-NP-RULES", "ATTR-C-RULES", "ATTR-U-RULES")
COMPARISON_FIELDS = (
    "category", "case_id", "feature", "metric", "minijmp_value", "minitab_value",
    "absolute_error", "relative_error", "tolerance", "status", "configuration",
    "minijmp_source", "minitab_source", "judgment",
)

sys.path.insert(0, str(ROOT / "code"))
sys.path.insert(0, str(PHASE2))
import verify_statistics_minitab19_phase2 as phase2  # noqa: E402


def load_inputs() -> dict:
    data = json.loads(INPUT.read_text(encoding="utf-8"))
    if data["metadata"]["required_version"] != "19.1.0.1":
        raise ValueError("phase8 固定要求 Minitab 19.1.0.1")
    cases = data["cases"]
    if len(cases["DESCRIBE-01"]["values"]) < 5:
        raise ValueError("描述统计固定样本量不足")
    for case_id, case in (("LINEAR-FIT-01", cases["LINEAR-FIT-01"]),
                          ("COR-PAIR-MISSING-01", cases["COR-PAIR-MISSING-01"])):
        if len(case["x"]) != len(case["y"]):
            raise ValueError(f"{case_id} 的 X/Y 行数不同")
    for case_id in ("PCA-02", "PLS-CV-01"):
        if len(cases[case_id]["rows"]) < 4:
            raise ValueError(f"{case_id} 输入行数不足")
    pls = cases["PLS-CV-01"]
    if len(pls["cv_groups"]) != len(pls["rows"]):
        raise ValueError("PLS CV 分组数必须与输入行数相同")
    if sorted(set(pls["cv_groups"])) != list(range(1, pls["cv"] + 1)):
        raise ValueError("PLS CV 分组编号必须从 1 连续递增")
    if len(cases["PCA-02"]["columns"]) != 3 or cases["PCA-02"]["n_components"] != 2:
        raise ValueError("PCA 固定配置必须是 3 列、保留 2 个主成分")
    return data


def input_vectors(cases: dict) -> dict[int, tuple[str, list]]:
    desc = cases["DESCRIBE-01"]["values"]
    linear = cases["LINEAR-FIT-01"]
    corr = cases["COR-PAIR-MISSING-01"]
    pca = cases["PCA-02"]
    pls = cases["PLS-CV-01"]
    attr_p = cases["ATTR-P-EDGE"]
    attr_np = cases["ATTR-NP-EDGE"]
    attr_c = cases["ATTR-C-EDGE"]
    attr_u = cases["ATTR-U-EDGE"]
    rule_p = cases["ATTR-P-RULES"]
    rule_np = cases["ATTR-NP-RULES"]
    rule_c = cases["ATTR-C-RULES"]
    rule_u = cases["ATTR-U-RULES"]
    return {
        1: ("DESCRIBE_value", desc),
        2: ("LINEAR_X", linear["x"]),
        3: ("LINEAR_Y", linear["y"]),
        4: ("CORR_X", corr["x"]),
        5: ("CORR_Y", corr["y"]),
        6: (pca["columns"][0], [row[0] for row in pca["rows"]]),
        7: (pca["columns"][1], [row[1] for row in pca["rows"]]),
        8: (pca["columns"][2], [row[2] for row in pca["rows"]]),
        10: (pls["predictors"][0], [row[0] for row in pls["rows"]]),
        11: (pls["predictors"][1], [row[1] for row in pls["rows"]]),
        12: (pls["responses"][0], [row[2] for row in pls["rows"]]),
        13: ("PLS_CV_group", pls["cv_groups"]),
        14: ("PLS_predict_x1", [row[0] for row in pls["prediction_rows"]]),
        15: ("PLS_predict_x2", [row[1] for row in pls["prediction_rows"]]),
        16: ("P_EDGE_defectives", attr_p["defectives"]),
        17: ("P_EDGE_sample_sizes", attr_p["sample_sizes"]),
        18: ("NP_EDGE_defectives", attr_np["defectives"]),
        19: ("C_EDGE_defects", attr_c["defects"]),
        20: ("U_EDGE_defects", attr_u["defects"]),
        21: ("U_EDGE_opportunities", attr_u["sample_sizes"]),
        22: ("P_RULE_defectives", rule_p["defectives"]),
        23: ("P_RULE_sample_sizes", rule_p["sample_sizes"]),
        24: ("NP_RULE_defectives", rule_np["defectives"]),
        25: ("C_RULE_defects", rule_c["defects"]),
        26: ("U_RULE_defects", rule_u["defects"]),
        27: ("U_RULE_opportunities", rule_u["sample_sizes"]),
    }


def command_specs(cases: dict) -> list[dict]:
    return [
        {
            "case_id": "DESCRIBE-01",
            "command": (
                "STATS C1;\n  N C30;\n  NMISS C31;\n  COUNT C32;\n"
                "  MEAN C33;\n  SEMEAN C34;\n  STDEV C35;\n  VARIANCE C36;\n"
                "  CVARIATION C37;\n  MEDIAN C38;\n  SUMS C39;\n  MINIMUMS C40;\n"
                "  MAXIMUMS C41;\n  RANGE C42;\n  SKEWNESS C43;\n  KURTOSIS C44.\n"
            ),
            "storage_columns": {
                "N": [30], "NMISS": [31], "COUNT": [32], "MEAN": [33],
                "SEMEAN": [34], "STDEV": [35], "VARIANCE": [36],
                "CVARIATION": [37], "MEDIAN": [38], "SUMS": [39],
                "MIN": [40], "MAX": [41], "RANGE": [42],
                "SKEWNESS": [43], "KURTOSIS": [44],
            },
            "storage_matrices": {},
        },
        {
            "case_id": "DESCRIBE-01-DISPLAY",
            "command": "DESCRIBE C1.\n",
            "storage_columns": {},
            "storage_matrices": {},
        },
        {
            "case_id": "LINEAR-FIT-01",
            "command": (
                "REGRESS;\n  RESPONSE C3;\n  CONTINUOUS C2;\n  TERMS C2;\n"
                "  CONSTANT;\n  UNSTANDARDIZED;\n  CONFIDENCE 95;\n"
                "  COEFFICIENTS C50;\n  FITS C52;\n  RESIDUALS C53;\n"
                "  SS C54;\n  SRSQ C55;\n  SRSADJ C56;\n  SPVALUE C57;\n"
                "  TCOEFFICIENTS;\n  TANOVA;\n  TSUMMARY.\n"
            ),
            "storage_columns": {
                "COEFFICIENTS": [50], "FITS": [52], "RESIDUALS": [53],
                "S": [54], "R2": [55], "R2ADJ": [56], "PVALUES": [57],
            },
            "storage_matrices": {},
        },
        {
            "case_id": "COR-PAIR-MISSING-01",
            "command": (
                "CORRELATION C4 C5;\n  PEARSON;\n  NODEFAULT;\n"
                "  SCORRELATION M20;\n  SPVALUES M21.\n"
            ),
            "storage_columns": {},
            "storage_matrices": {
                "CORRELATION": {"name": "M20"},
                "PVALUES": {"name": "M21"},
            },
        },
        {
            "case_id": "COR-PAIR-MISSING-01-TABLE",
            "command": "CORRELATION C4 C5;\n  PEARSON;\n  TPCORRELATION.\n",
            "storage_columns": {},
            "storage_matrices": {},
        },
        {
            "case_id": "COR-PAIR-MISSING-01-N-PROBE",
            "command": "CORRELATION C4 C5;\n  PEARSON;\n  TPCORRELATION M22.\n",
            "storage_columns": {},
            "storage_matrices": {},
        },
        {
            "case_id": "ATTR-P-EDGE",
            "command": (
                "PCHART C16 C17;\n  PPOINTS C80;\n  CENLINE C81;\n"
                "  CONLIMITS C82 C83.\n"
            ),
            "storage_columns": {
                "PPOINTS": [80], "CENLINE": [81], "CONLIMITS": [82, 83],
            },
            "storage_matrices": {},
        },
        {
            "case_id": "ATTR-NP-EDGE",
            "command": (
                "NPCHART C18 10;\n  PPOINTS C84;\n  CENLINE C85;\n"
                "  CONLIMITS C86 C87.\n"
            ),
            "storage_columns": {
                "PPOINTS": [84], "CENLINE": [85], "CONLIMITS": [86, 87],
            },
            "storage_matrices": {},
        },
        {
            "case_id": "ATTR-C-EDGE",
            "command": (
                "CCHART C19;\n  PPOINTS C88;\n  CENLINE C89;\n"
                "  CONLIMITS C90 C91.\n"
            ),
            "storage_columns": {
                "PPOINTS": [88], "CENLINE": [89], "CONLIMITS": [90, 91],
            },
            "storage_matrices": {},
        },
        {
            "case_id": "ATTR-U-EDGE",
            "command": (
                "UCHART C20 C21;\n  PPOINTS C92;\n  CENLINE C93;\n"
                "  CONLIMITS C94 C95.\n"
            ),
            "storage_columns": {
                "PPOINTS": [92], "CENLINE": [93], "CONLIMITS": [94, 95],
            },
            "storage_matrices": {},
        },
        {
            "case_id": "ATTR-P-RULES",
            "command": (
                "PCHART C22 C23;\n  TEST 1 2 3 4;\n  PPOINTS C150;\n"
                "  CENLINE C151;\n  CONLIMITS C152 C153;\n"
                "  TRESULTS C154 C155 C156 C157.\n"
            ),
            "storage_columns": {
                "PPOINTS": [150], "CENLINE": [151], "CONLIMITS": [152, 153],
                "TEST_1": [154], "TEST_2": [155], "TEST_3": [156], "TEST_4": [157],
            },
            "storage_matrices": {},
        },
        {
            "case_id": "ATTR-NP-RULES",
            "command": (
                "NPCHART C24 100;\n  TEST 1 2 3 4;\n  PPOINTS C158;\n"
                "  CENLINE C159;\n  CONLIMITS C160 C161;\n"
                "  TRESULTS C162 C163 C164 C165.\n"
            ),
            "storage_columns": {
                "PPOINTS": [158], "CENLINE": [159], "CONLIMITS": [160, 161],
                "TEST_1": [162], "TEST_2": [163], "TEST_3": [164], "TEST_4": [165],
            },
            "storage_matrices": {},
        },
        {
            "case_id": "ATTR-C-RULES",
            "command": (
                "CCHART C25;\n  TEST 1 2 3 4;\n  PPOINTS C166;\n"
                "  CENLINE C167;\n  CONLIMITS C168 C169;\n"
                "  TRESULTS C170 C171 C172 C173.\n"
            ),
            "storage_columns": {
                "PPOINTS": [166], "CENLINE": [167], "CONLIMITS": [168, 169],
                "TEST_1": [170], "TEST_2": [171], "TEST_3": [172], "TEST_4": [173],
            },
            "storage_matrices": {},
        },
        {
            "case_id": "ATTR-U-RULES",
            "command": (
                "UCHART C26 C27;\n  TEST 1 2 3 4;\n  PPOINTS C174;\n"
                "  CENLINE C175;\n  CONLIMITS C176 C177;\n"
                "  TRESULTS C178 C179 C180 C181.\n"
            ),
            "storage_columns": {
                "PPOINTS": [174], "CENLINE": [175], "CONLIMITS": [176, 177],
                "TEST_1": [178], "TEST_2": [179], "TEST_3": [180], "TEST_4": [181],
            },
            "storage_matrices": {},
        },
        {
            "case_id": "PCA-02",
            "command": (
                "PCA C6-C8;\n  NCOMP 2;\n"
                "  COEFFICIENTS C60 C61;\n  SCORES C62 C63;\n"
                "  EIGEN C64;\n  DISTANCE C65.\n"
            ),
            "storage_columns": {
                "COEFFICIENTS": [60, 61], "SCORES": [62, 63],
                "EIGEN": [64], "DISTANCE": [65],
            },
            "storage_matrices": {},
        },
        {
            "case_id": "PLS-CV-01",
            "command": (
                "PLS C12 = C10-C11;\n  NCOMP 2;\n  XVALIDATION C13;\n"
                "  FITS C70;\n  CVFITS C71;\n  PRESIDUALS C72;\n"
                "  COEFFICIENTS C73;\n  XSCORES M23;\n  YSCORES M24;\n"
                "  XLOADINGS M25;\n  YLOADINGS M26;\n"
                "  PCONTINUOUS C14 C15;\n  PFITS C74;\n"
                "  TSELECTION;\n  TCOEFFICIENTS;\n  TFITS.\n"
            ),
            "storage_columns": {
                "FITS": [70], "CVFITS": [71], "PRESIDUALS": [72],
                "COEFFICIENTS": [73], "PFITS": [74],
            },
            "storage_matrices": {
                "XSCORES": {"name": "M23"},
                "YSCORES": {"name": "M24"},
                "XLOADINGS": {"name": "M25"},
                "YLOADINGS": {"name": "M26"},
            },
        },
    ]


def read_matrix(worksheet, name: str) -> dict:
    matrices = worksheet.Matrices
    matrix = next((matrices.Item(i) for i in range(1, int(matrices.Count) + 1)
                   if str(matrices.Item(i).Name).casefold() == name.casefold()), None)
    if matrix is None:
        raise ValueError(f"Minitab 矩阵不存在：{name}")
    rows, cols = int(matrix.RowCount), int(matrix.ColumnCount)
    flat = [float(value) for value in matrix.GetData()]
    if len(flat) != rows * cols:
        raise ValueError(f"Minitab {name} 矩阵数据长度与维度不符")
    return {
        "rows": rows,
        "columns": cols,
        "values": [[flat[col * rows + row] for col in range(cols)] for row in range(rows)],
    }


def com_worker(case_ids=None) -> dict:
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
        vectors = input_vectors(load_inputs()["cases"])
        columns = worksheet.Columns
        phase2.prepare_columns(worksheet, 181)
        loaded_inputs, input_commands = {}, []
        for index, (name, values) in vectors.items():
            column = columns.Item(index)
            column.Name = name
            if any(value is None for value in values):
                data = " ".join("*" if value is None else format(float(value), ".17g")
                                for value in values)
                command = f"SET C{index}\n{data}\nEND"
                before_count = int(project.Commands.Count)
                project.ExecuteCommand(command)
                after_count = int(project.Commands.Count)
                if after_count <= before_count or str(app.LastError or "").strip():
                    raise RuntimeError(f"Minitab 缺失值载入失败 C{index}: {app.LastError}")
                input_commands.append(command)
            else:
                column.SetData(tuple(values), 1, len(values))
            readback = phase2.column_values(worksheet, index)
            expected = [phase2.clean_number(value) for value in values]
            if len(readback) != len(expected) or any(
                    actual != wanted for actual, wanted in zip(readback, expected)):
                raise AssertionError(f"Minitab C{index} 输入回读与固定数据不同")
            loaded_inputs[str(index)] = {
                "name": name, "values": readback,
                "effective_n": sum(value is not None for value in readback),
            }
        metadata = {
            "version": version, "clsid": clsid, "registered_server": registered_command,
            "app_path": app_path, "process_path": process_path, "process_id": process_id,
            "project_name": str(project.Name), "worksheet_name": str(worksheet.Name),
            "python": sys.executable, "loaded_inputs": loaded_inputs,
            "input_commands": input_commands,
        }
        specs = command_specs(load_inputs()["cases"])
        if case_ids is not None:
            requested = set(case_ids)
            specs = [item for item in specs if item["case_id"] in requested]
            missing = requested - {item["case_id"] for item in specs}
            if missing:
                raise ValueError(f"Minitab 命令配置缺失：{sorted(missing)}")
        for item in specs:
            case_id, command = item["case_id"], item["command"]
            before_count = int(project.Commands.Count)
            try:
                project.ExecuteCommand(command)
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
                    for name, spec in item["storage_matrices"].items():
                        try:
                            stored[name] = read_matrix(worksheet, spec["name"])
                        except Exception as exc:
                            storage_errors[name] = f"{type(exc).__name__}: {exc}"
                outputs[case_id] = {
                    "executed": accepted, "command": command,
                    "command_count": [before_count, after_count],
                    "last_error": last_error, "command_output_error": output_error,
                    "output": output, "stored": stored, "storage_errors": storage_errors,
                    "storage_columns": item["storage_columns"],
                    "storage_matrices": item["storage_matrices"],
                }
            except Exception as exc:
                outputs[case_id] = {
                    "executed": False, "command": command,
                    "command_count": [before_count, int(project.Commands.Count)],
                    "error": f"{type(exc).__name__}: {exc}",
                    "last_error": str(app.LastError or ""),
                    "command_output_error": False, "output": "", "stored": {},
                    "storage_errors": {}, "storage_columns": item["storage_columns"],
                    "storage_matrices": item["storage_matrices"],
                    "traceback": traceback.format_exc(),
                }
        return {"metadata": metadata, "outputs": outputs}
    except Exception:
        return {"metadata": metadata, "outputs": outputs, "fatal_error": traceback.format_exc()}
    finally:
        columns = worksheet = project = app = ui = None
        gc.collect()


def run_minitab(case_ids=None) -> tuple[dict, str, int]:
    if not PYTHON.is_file():
        return {}, f"项目解释器不存在：{PYTHON}", 1
    env = os.environ.copy()
    for name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        env[name] = "1"
    try:
        command = [str(PYTHON), "-X", "utf8", str(Path(__file__).resolve()), "--com-worker"]
        if case_ids is not None:
            command.extend(case_ids)
        process = subprocess.run(
            command,
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=600, check=False, env=env,
        )
        result = json.loads(process.stdout) if process.stdout.strip() else {}
        pids = phase2.running_minitab_pids()
        if pids:
            result.setdefault("cleanup_error", f"COM worker 结束后仍有 Mtb.exe PID {pids}；未操作该进程")
        return result, process.stderr, process.returncode or int(
            bool(result.get("fatal_error") or result.get("cleanup_error")))
    except Exception as exc:
        return {}, f"{type(exc).__name__}: {exc}", 1


def _attribute_chart_values(case: dict) -> dict:
    import matplotlib
    matplotlib.use("Agg", force=True)
    import matplotlib.pyplot as plt
    import control_chart

    kind = case["chart"]
    if kind in ("P", "NP"):
        raw = case["defectives"]
        sizes = ([case["sample_size"]] * len(raw) if kind == "NP"
                 else case["sample_sizes"])
        valid = [(float(value), float(size)) for value, size in zip(raw, sizes)
                 if value is not None and size is not None]
        defects, sizes = zip(*valid)
        points = [value / size for value, size in zip(defects, sizes)]
        fig, ax = plt.subplots()
        try:
            events = control_chart.p_np_plot(
                p=points, n=case["sample_size"] if kind == "NP" else list(sizes),
                NP=kind == "NP", ax=ax, fig=fig, detect_rules=True,
            )
            chart_points = [float(value) for value in ax.lines[0].get_ydata()]
            center_line = [float(value) for value in ax.lines[1].get_ydata()]
            ucl_line = [float(value) for value in ax.lines[2].get_ydata()]
            lcl_line = [float(value) for value in ax.lines[3].get_ydata()]
        finally:
            plt.close(fig)
    else:
        raw = case["defects"]
        sizes = [1] * len(raw) if kind == "C" else case["sample_sizes"]
        valid = [(float(value), float(size)) for value, size in zip(raw, sizes)
                 if value is not None and size is not None]
        defects, sizes = zip(*valid)
        fig, ax = plt.subplots()
        try:
            events = control_chart.cu_plot(
                c=list(defects), n=1 if kind == "C" else list(sizes),
                C=kind == "C", ax=ax, fig=fig, detect_rules=True,
            )
            chart_points = [float(value) for value in ax.lines[0].get_ydata()]
            center_line = [float(value) for value in ax.lines[1].get_ydata()]
            ucl_line = [float(value) for value in ax.lines[2].get_ydata()]
            lcl_line = [float(value) for value in ax.lines[3].get_ydata()]
        finally:
            plt.close(fig)
    n = len(chart_points)
    def plotted_values(line):
        if len(line) == 2 and n > 2 and line[0] == line[1]:
            return [line[0]] * n
        values = line[::2] if len(line) == 2 * n else line
        return (values * n if len(values) == 1 else values)
    return {
        "points": chart_points,
        "center": plotted_values(center_line),
        "ucl": plotted_values(ucl_line),
        "lcl": plotted_values(lcl_line),
        "events": events,
        "source": "code.control_chart.p_np_plot / cu_plot actual Axes",
    }


def production_results(cases: dict) -> dict:
    import numpy as np
    import pandas as pd
    from describe import describe
    from linear_fit import linear_fit
    from pca_analysis import fit_pca
    from pls_regression import fit_pls
    from utilities import number_2lists, pearson_correlation

    result = {}
    desc = cases["DESCRIBE-01"]["values"]
    result["DESCRIBE-01"] = describe(desc, print_out=False)

    linear = cases["LINEAR-FIT-01"]
    fit = linear_fit(linear["x"], linear["y"], print_out=False)
    result["LINEAR-FIT-01"] = {
        **fit,
        "Fitted": [y - residual for y, residual in zip(linear["y"], fit["Residual"])],
        "source": "code.linear_fit.linear_fit",
    }

    corr = cases["COR-PAIR-MISSING-01"]
    x, y = number_2lists(corr["x"], corr["y"])
    result["COR-PAIR-MISSING-01"] = {
        **pearson_correlation(x, y, print_out=False),
        "paired_x": x,
        "paired_y": y,
        "source": "fit_dialog.CorrelationDialog.apply → number_2lists → pearson_correlation",
    }

    pca = cases["PCA-02"]
    frame = pd.DataFrame(pca["rows"], columns=pca["columns"])
    model = fit_pca(frame, pca["columns"], n_components=pca["n_components"],
                    scaling=pca["scaling"], missing=pca["missing"])
    result["PCA-02"] = {
        "eigenvalues": model.eigenvalues.tolist(),
        "explained_variance_ratio": model.explained_variance_ratio.tolist(),
        "cumulative_explained_variance_ratio": np.cumsum(model.explained_variance_ratio).tolist(),
        "loadings": model.loadings.tolist(),
        "scores": model.training.scores.tolist(),
        "reconstructed": model.training.reconstructed.tolist(),
        "t2": model.training.t2.tolist(),
        "q": model.training.q.tolist(),
        "mean": model.mean.tolist(),
        "scale": model.scale.tolist(),
        "source": "code.pca_analysis.fit_pca; correlation matrix; sample SD ddof=1",
    }

    pls = cases["PLS-CV-01"]
    columns = pls["predictors"] + pls["responses"]
    frame = pd.DataFrame(pls["rows"], columns=columns)
    model = fit_pls(frame, pls["responses"], pls["predictors"],
                    n_components=pls["n_components"], cv=pls["cv"],
                    scale=pls["scale"], missing=pls["missing"])
    prediction_frame = pd.DataFrame(pls["prediction_rows"], columns=pls["predictors"])
    result["PLS-CV-01"] = {
        "coefficients": model.tables["coefficients"].to_dict("records"),
        "summary": model.tables["summary"].to_dict("records"),
        "fits": model.tables["observations"].fitted.astype(float).tolist(),
        "cv": model.tables["cv"].to_dict("records"),
        "cv_predictions": model.tables["cv_predictions"].to_dict("records"),
        "x_scores": model.tables["x_scores"].filter(like="component_").to_numpy().tolist(),
        "y_scores": model.tables["y_scores"].filter(like="component_").to_numpy().tolist(),
        "x_loadings": model.tables["x_loadings"].filter(like="component_").to_numpy().tolist(),
        "y_loadings": model.tables["y_loadings"].filter(like="component_").to_numpy().tolist(),
        "predictions": model.predict(prediction_frame).predicted.astype(float).tolist(),
        "source": "code.pls_regression.fit_pls; fixed 2 components, 4 consecutive folds",
    }
    phase7_cases = json.loads((PHASE7 / "case_inputs.json").read_text(encoding="utf-8"))["cases"]
    for case_id in ATTRIBUTE_PHASE7_CASES:
        result[case_id] = _attribute_chart_values(phase7_cases[case_id])
    for case_id in ATTRIBUTE_EDGE_CASES + ATTRIBUTE_RULE_CASES:
        result[case_id] = _attribute_chart_values(cases[case_id])
    return result


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


def _json(value) -> str:
    return json.dumps(_builtin(value), ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def _flat(value):
    if hasattr(value, "tolist"):
        yield from _flat(value.tolist())
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            yield from _flat(item)
    else:
        yield value


def _equal_values(left, right, tolerance: float) -> tuple[bool, float | None, float | None]:
    left, right = list(_flat(left)), list(_flat(right))
    if len(left) != len(right):
        return False, None, None
    errors, relative = [], []
    for a, b in zip(left, right):
        if a is None or b is None:
            if a is not None or b is not None:
                return False, None, None
            continue
        error = abs(float(a) - float(b))
        errors.append(error)
        relative.append(error / abs(float(b)) if float(b) else error)
    maximum = max(errors, default=0.0)
    return maximum <= tolerance, maximum, max(relative, default=0.0)


def _add(rows: list[dict], *, category: str, case_id: str, feature: str,
         metric: str, local, native, tolerance: float, configuration: str,
         local_source: str, native_source: str, judgment: str,
         forced_status: str | None = None) -> None:
    if forced_status:
        status, absolute, relative = forced_status, None, None
    else:
        passed, absolute, relative = _equal_values(local, native, tolerance)
        status = "PASS" if passed else "FAIL"
    rows.append({
        "category": category, "case_id": case_id, "feature": feature, "metric": metric,
        "minijmp_value": _json(local), "minitab_value": _json(native),
        "absolute_error": "" if absolute is None else f"{absolute:.17g}",
        "relative_error": "" if relative is None else f"{relative:.17g}",
        "tolerance": f"{tolerance:.17g}", "status": status,
        "configuration": configuration, "minijmp_source": local_source,
        "minitab_source": native_source, "judgment": judgment,
    })


def _stored(run: dict, case_id: str, name: str):
    output = run.get("outputs", {}).get(case_id, {})
    value = output.get("stored", {}).get(name)
    if value is None:
        return None
    return value


def _column_scalar(run: dict, case_id: str, name: str):
    value = _stored(run, case_id, name)
    if isinstance(value, list):
        return value[0] if value else None
    return value


def _matrix_values(run: dict, case_id: str, name: str):
    value = _stored(run, case_id, name)
    return value.get("values") if isinstance(value, dict) else None


def _command_ok(run: dict, case_id: str) -> bool:
    return bool(run.get("outputs", {}).get(case_id, {}).get("executed"))


def _attribute_rule_flags(local_case: dict, test: int) -> list[int]:
    points = {event["point"] for event in local_case["events"]
              if event["rule_number"] == test}
    return [int(point in points) for point in range(1, len(local_case["points"]) + 1)]


def _numeric_tokens(line: str) -> list[tuple[str, float]]:
    pattern = r"(?<![A-Za-z])[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?"
    result = []
    for token in re.findall(pattern, line.replace(",", "")):
        try:
            result.append((token, float(token)))
        except ValueError:
            pass
    return result


def _describe_display(output: dict, n: int) -> dict | None:
    lines = output.get("output", "").splitlines()
    for line in lines:
        tokens = _numeric_tokens(line)
        for start, (token, value) in enumerate(tokens):
            if value == n and len(tokens) - start >= 10:
                return {
                    "tokens": [item[0] for item in tokens[start:start + 10]],
                    "values": [item[1] for item in tokens[start:start + 10]],
                }
    return None


def _rounding_tolerance(token: str) -> float:
    lower = token.lower()
    if "e" in lower:
        mantissa, exponent = lower.split("e", 1)
        decimals = len(mantissa.partition(".")[2])
        return .5 * 10 ** (int(exponent) - decimals)
    decimals = len(token.partition(".")[2])
    return .5 * 10 ** (-decimals) if decimals else 0.0


def _output_row(output: dict, label: str) -> list[tuple[str, float]] | None:
    for line in output.get("output", "").splitlines():
        if re.match(r"^" + re.escape(label) + r"\s+[-+]?(?:\d|\.)", line.strip()):
            values = _numeric_tokens(line)
            if values:
                return values
    return None


def _pairwise_n(output: dict, first_name: str, second_name: str) -> int | None:
    for line in output.get("output", "").splitlines():
        if first_name in line and second_name in line:
            numbers = _numeric_tokens(line)
            if numbers and numbers[0][1].is_integer() and numbers[0][1] >= 2:
                return int(numbers[0][1])
    return None


def _infer_pearson_n(r: float, p: float, maximum_n: int) -> list[int]:
    from scipy.stats import t as t_dist

    if not math.isfinite(r) or not math.isfinite(p) or abs(r) >= 1:
        return []
    matches = []
    for n in range(3, maximum_n + 1):
        statistic = abs(r) * math.sqrt((n - 2) / (1 - r * r))
        if abs(float(2 * t_dist.sf(statistic, n - 2)) - p) <= 1e-12:
            matches.append(n)
    return matches


def compare_results(data: dict, local: dict, runs: list[dict]) -> list[dict]:
    cases, first = data["cases"], runs[0] if runs else {}
    rows = []

    # Reclassify phase7's 16 attribute-chart flags from the owning production paths.
    old_native = json.loads((PHASE7 / "minitab_results.json").read_text(encoding="utf-8"))["runs"][0]
    old_cases = json.loads((PHASE7 / "case_inputs.json").read_text(encoding="utf-8"))["cases"]
    attribute_sources = {
        "SPC-P": ("P", "P 图"),
        "SPC-NP": ("NP", "NP 图"),
        "SPC-C": ("C", "C 图"),
        "SPC-U": ("U", "U 图"),
    }
    for old_case, (chart, feature) in attribute_sources.items():
        local_case = local[old_case]
        output = old_native.get("outputs", {}).get(old_case, {})
        for test in range(1, 5):
            flags = _stored(old_native, old_case, f"TEST_{test}")
            local_flags = _attribute_rule_flags(local_case, test)
            forced_status = None if output.get("executed") and flags is not None else (
                "UNSUPPORTED" if output.get("executed") else "NOT_RUN")
            _add(
                rows, category="SPC", case_id=old_case, feature=feature,
                metric=f"Minitab Test {test} 逐点标志",
                local=local_flags, native=flags, tolerance=0,
                configuration=old_cases[old_case]["configuration"],
                local_source="code.control_chart.p_np_plot / cu_plot → returned Test flags",
                native_source=f"phase7/minitab_results.json#runs[0].outputs.{old_case}.stored.TEST_{test}",
                judgment=(f"复用 phase7 固定序列验证 Test {test} 的逐点标志；"
                          f"MiniJMP 报警点={sorted(event['point'] for event in local_case['events'] if event['rule_number'] == test)}。"),
                forced_status=forced_status,
            )

    edge_features = {
        "ATTR-P-EDGE": ("控制图 P", "P"),
        "ATTR-NP-EDGE": ("控制图 NP", "NP"),
        "ATTR-C-EDGE": ("控制图 C", "C"),
        "ATTR-U-EDGE": ("控制图 U", "U"),
    }
    for case_id, (feature, chart) in edge_features.items():
        local_edge = local[case_id]
        points = _stored(first, case_id, "PPOINTS")
        center = _stored(first, case_id, "CENLINE")
        limits = _stored(first, case_id, "CONLIMITS")
        valid_indices = ([i for i, value in enumerate(points) if value is not None]
                         if points is not None else [])

        def align(values):
            if values is None:
                return None
            if len(values) == 1:
                return values * len(local_edge["points"])
            if points is not None and len(values) == len(points):
                return [values[i] for i in valid_indices]
            if len(values) == len(local_edge["points"]):
                return values
            return None

        native_points = align(points)
        native_center = align(center)
        if limits and len(limits) == 2:
            first_limit, second_limit = align(limits[0]), align(limits[1])
        else:
            first_limit = second_limit = None
        if native_center and first_limit and second_limit:
            first_distance = sum(a-b for a, b in zip(first_limit, native_center))
            second_distance = sum(a-b for a, b in zip(second_limit, native_center))
            native_ucl, native_lcl = ((first_limit, second_limit)
                                      if first_distance >= second_distance
                                      else (second_limit, first_limit))
        else:
            native_ucl = native_lcl = None
        native_chart = {
            "points": native_points, "center": native_center,
            "ucl": native_ucl, "lcl": native_lcl,
        }
        executed = _command_ok(first, case_id)
        for metric in ("points", "center", "ucl", "lcl"):
            native_value = native_chart[metric]
            _add(
                rows, category="SPC", case_id=case_id, feature=feature,
                metric=f"{chart} {metric.upper()}（零值/缺失边界）",
                local=local_edge[metric], native=native_value,
                tolerance=data["tolerances"]["numeric_abs"],
                configuration=cases[case_id]["configuration"],
                local_source="code.control_chart.p_np_plot / cu_plot；对话框先剔除缺失行",
                native_source=f"phase8/minitab_results.json#runs[0].outputs.{case_id}.stored",
                judgment="按 Minitab 原始 PPOINTS 非缺失位置对齐；CONLIMITS 两列按与中心线的方向识别 UCL/LCL。",
                forced_status=None if executed and native_value is not None else
                ("NOT_RUN" if not executed else "UNSUPPORTED"),
            )

    expected_local_points = {1: [4], 2: [14], 3: [22, 23], 4: [38, 39]}
    for case_id in ATTRIBUTE_RULE_CASES:
        local_case = local[case_id]
        case = cases[case_id]
        feature = case["feature"]
        run_events = local_case["events"]
        executed = _command_ok(first, case_id)
        for test in range(1, 5):
            native_flags = _stored(first, case_id, f"TEST_{test}")
            local_flags = _attribute_rule_flags(local_case, test)
            local_points = sorted(event["point"] for event in run_events
                                  if event["rule_number"] == test)
            native_points = (sorted(i + 1 for i, value in enumerate(native_flags) if value)
                             if native_flags is not None else None)
            windows = [f"{event['point']}({event['window_start']}-{event['window_end']})"
                       for event in run_events if event["rule_number"] == test]
            native_source = f"phase8/minitab_results.json#runs[0].outputs.{case_id}.stored.TEST_{test}"
            forced_status = None if executed and native_flags is not None else (
                "UNSUPPORTED" if executed else "NOT_RUN")
            judgment = (f"MiniJMP 逐点标志；本地窗口末点/窗口={windows}；"
                        f"Minitab TRESULTS 标记点={native_points}。")
            _add(
                rows, category="SPC", case_id=case_id, feature=feature,
                metric=f"Test {test} 正向序列逐点标志",
                local=local_flags, native=native_flags, tolerance=0,
                configuration=case["configuration"],
                local_source="code.control_chart._attribute_events → p_np_plot / cu_plot",
                native_source=native_source, judgment=judgment,
                forced_status=forced_status,
            )
            row = rows[-1]
            if local_points != expected_local_points[test]:
                row["status"] = "FAIL"
                row["judgment"] += f" 独立窗口预期点={expected_local_points[test]}，实际={local_points}。"
            elif (test in (3, 4) and native_points == local_points[1:]
                  and native_flags is not None
                  and native_flags == [int(i + 1 in native_points) for i in range(len(local_flags))]):
                row["status"] = "METHOD_DIFF"
                row["judgment"] += (
                    f" 规则窗口按 6/14 点在 MiniJMP 首次成立于 {local_points[0]}，"
                    f"Minitab 19 TRESULTS 仅标记重叠窗口的后一个末点 {native_points}；"
                    "保留已确认的单点标记时点差异，不延迟 MiniJMP 判异。")

    # Derive the missing PLS-01 intercept from archived Minitab slopes and the exact input rows.
    old_inputs = json.loads((PHASE7 / "case_inputs.json").read_text(encoding="utf-8"))["cases"]["PLS-01"]
    old_minitab = json.loads((PHASE7 / "minitab_results.json").read_text(encoding="utf-8"))["runs"]
    old_minijmp = json.loads((PHASE7 / "minijmp_results.json").read_text(encoding="utf-8"))["results"]["PLS-01"]
    old_stored = old_minitab[0]["outputs"]["PLS-01"]["stored"]
    beta = old_stored["COEFFICIENTS"]
    means_x = [sum(row[j] for row in old_inputs["rows"]) / len(old_inputs["rows"]) for j in (0, 1)]
    mean_y = sum(row[2] for row in old_inputs["rows"]) / len(old_inputs["rows"])
    derived_intercept = mean_y - sum(b * means_x[j] for j, b in enumerate(beta))
    local_intercept = next(row["estimate"] for row in old_minijmp["coefficients"]
                           if row["term"] == "Intercept")
    _add(
        rows, category="多变量", case_id="PLS-01-INTERCEPT",
        feature="偏最小二乘回归 PLS", metric="PLS 截距（原生斜率和输入均值复算）",
        local=local_intercept, native=derived_intercept,
        tolerance=data["tolerances"]["numeric_abs"],
        configuration="复用 phase7 PLS-01：12 行、2 个 X、1 个 Y、1 component、CV 关闭。",
        local_source="phase7/minijmp_results.json#results.PLS-01.coefficients[Intercept]",
        native_source="phase7/minitab_results.json#runs[0].outputs.PLS-01.stored.COEFFICIENTS + phase7/case_inputs.json",
        judgment=(f"原生存储没有截距字段。b0=mean(y)-Σβj·mean(xj)；"
                  f"mean(x)={_json(means_x)}，mean(y)={mean_y:.17g}，原单位 β={_json(beta)}。"),
    )
    old_fits = old_stored["FITS"]
    reconstructed_fits = [derived_intercept + sum(row[j] * beta[j] for j in range(2))
                          for row in old_inputs["rows"]]
    _add(
        rows, category="多变量", case_id="PLS-01-INTERCEPT",
        feature="偏最小二乘回归 PLS", metric="复算截距后的训练拟合值",
        local=reconstructed_fits, native=old_fits,
        tolerance=data["tolerances"]["numeric_abs"],
        configuration="同 PLS-01 固定配置。",
        local_source="phase7 PLS-01 原始 X/Y 和 Minitab 原单位斜率；按截距公式重建",
        native_source="phase7/minitab_results.json#runs[0].outputs.PLS-01.stored.FITS",
        judgment="训练拟合值作为独立校验，确认原生系数处于原始变量尺度。",
    )

    # Single-column descriptive menu; STATS fields are stored at full precision.
    desc, nd = local["DESCRIBE-01"], first
    desc_case = cases["DESCRIBE-01"]
    desc_map = [
        ("N", "N", "N"), ("NMISS", "missing", "NMISS"), ("COUNT", "count", "COUNT"),
        ("MEAN", "mean", "mean"), ("SEMEAN", "SEM", "SEMEAN"),
        ("STDEV", "stdev", "stdev"), ("VARIANCE", "var", "variance"),
        ("CVARIATION", "coefvar", "coefvar"), ("MEDIAN", "median", "median"),
        ("SUMS", "sum", "sum"), ("MIN", "min", "min"), ("MAX", "max", "max"),
        ("RANGE", "range", "range"), ("SKEWNESS", "skew", "skewness"),
        ("KURTOSIS", "kurt", "kurtosis"),
    ]
    n_valid = desc["N"]
    missing_count = len(desc_case["values"]) - n_valid
    desc_locals = {"missing": missing_count, "count": len(desc_case["values"]), **desc}
    for field, local_key, native_key in desc_map:
        native_value = _column_scalar(nd, "DESCRIBE-01", field)
        command_ok = _command_ok(nd, "DESCRIBE-01")
        _add(
            rows, category="统计", case_id="DESCRIBE-01", feature="描述性统计",
            metric=field, local=desc_locals.get(local_key), native=native_value,
            tolerance=data["tolerances"]["numeric_abs"],
            configuration=desc_case["configuration"],
            local_source="code.basic_dialogs.DescribeDialog → describe.describe",
            native_source=f"phase8/minitab_results.json#runs[0].outputs.DESCRIBE-01.stored.{field}",
            judgment="STATS 直接存储；N 按非缺失数，COUNT 保留输入行数。",
            forced_status=None if command_ok and native_value is not None else
            ("NOT_RUN" if not command_ok else "UNSUPPORTED"),
        )
    display = first.get("outputs", {}).get("DESCRIBE-01-DISPLAY", {})
    shown = _describe_display(display, int(desc["N"]))
    if shown:
        for label, local_value, index in (
                ("Q1", desc["quantiles"][6], 6),
                ("Q3", desc["quantiles"][4], 8)):
            _add(
                rows, category="统计", case_id="DESCRIBE-01", feature="描述性统计",
                metric=f"{label} 四分位数（显示值）",
                local=local_value, native=shown["values"][index],
                tolerance=_rounding_tolerance(shown["tokens"][index]),
                configuration=desc_case["configuration"],
                local_source="code.describe.describe.quantiles",
                native_source="Minitab DESCRIBE C1 输出表；按 N、N*、Mean、SE Mean、StDev、Min、Q1、Median、Q3、Max 解析",
                judgment=f"native_token={shown['tokens'][index]}；舍入容差取显示末位的一半。",
            )
    else:
        for label in ("Q1", "Q3"):
            _add(
                rows, category="统计", case_id="DESCRIBE-01", feature="描述性统计",
                metric=f"{label} 四分位数",
                local=desc["quantiles"][6 if label == "Q1" else 4], native=None,
                tolerance=data["tolerances"]["display_abs"],
                configuration=desc_case["configuration"],
                local_source="code.describe.describe.quantiles",
                native_source="Minitab DESCRIBE C1 输出未被当前 COM 字段提取器解析",
                judgment="原生结果仅以显示表提供；保留为本轮未成功提取，不以公式替代原生参考。",
                forced_status="NOT_RUN",
            )

    # The dedicated fitted-line menu calls linear_fit, not the multiple regression dialog.
    linear, nl = local["LINEAR-FIT-01"], first
    linear_case = cases["LINEAR-FIT-01"]
    coefficient_values = _stored(nl, "LINEAR-FIT-01", "COEFFICIENTS")
    coefficient_table = nl.get("outputs", {}).get("LINEAR-FIT-01", {})
    constant_row = _output_row(coefficient_table, "常量")
    slope_row = _output_row(coefficient_table, "LINEAR_X")
    linear_fields = [
        ("截距与斜率", [linear["intercept"], linear["slope"]], coefficient_values),
        ("拟合值", linear["Fitted"], _stored(nl, "LINEAR-FIT-01", "FITS")),
        ("残差", linear["Residual"], _stored(nl, "LINEAR-FIT-01", "RESIDUALS")),
        ("残差标准差 S", linear["Root MSE"], _column_scalar(nl, "LINEAR-FIT-01", "S")),
        ("R²", linear["R Square"], _column_scalar(nl, "LINEAR-FIT-01", "R2")),
        ("调整 R²", linear["R Square Adj"], _column_scalar(nl, "LINEAR-FIT-01", "R2ADJ")),
        ("斜率双侧 p 值", linear["p slope"],
         (_stored(nl, "LINEAR-FIT-01", "PVALUES") or [None])[-1]),
    ]
    for metric, local_value, native_value in linear_fields:
        ok = _command_ok(nl, "LINEAR-FIT-01") and native_value is not None
        _add(
            rows, category="统计", case_id="LINEAR-FIT-01", feature="线性回归",
            metric=metric, local=local_value, native=native_value,
            tolerance=data["tolerances"]["numeric_abs"],
            configuration=linear_case["configuration"],
            local_source="MiniJMP.py 线性回归菜单 → linear_plot.fit_plot → linear_fit.linear_fit",
            native_source=f"phase8/minitab_results.json#runs[0].outputs.LINEAR-FIT-01.stored.{metric}",
            judgment="Minitab REGRESS 原生存储；重复 X 水平，覆盖纯误差。",
            forced_status=None if ok else ("NOT_RUN" if not _command_ok(nl, "LINEAR-FIT-01") else "UNSUPPORTED"),
        )
    for label, local_se, local_t, native_row in (
            ("常量", linear["Std Error Int."], linear["t int."], constant_row),
            ("LINEAR_X", linear["Std Error Slope"], linear["t slope"], slope_row)):
        for metric, local_value, column_index in (
                ("系数标准误", local_se, 1), ("系数 t 值", local_t, 2)):
            available = _command_ok(nl, "LINEAR-FIT-01") and native_row is not None and len(native_row) > column_index
            token, native_value = native_row[column_index] if available else ("", None)
            _add(
                rows, category="统计", case_id="LINEAR-FIT-01", feature="线性回归",
                metric=f"{label} {metric}", local=local_value, native=native_value,
                tolerance=_rounding_tolerance(token) if available else data["tolerances"]["display_abs"],
                configuration=linear_case["configuration"],
                local_source="code.linear_fit.linear_fit",
                native_source="Minitab REGRESS TCOEFFICIENTS 输出表",
                judgment=f"按显示值精度核对，native_token={token}。",
                forced_status=None if available else
                ("NOT_RUN" if not _command_ok(nl, "LINEAR-FIT-01") else "UNSUPPORTED"),
            )
    anova_rows = {
        "回归": (("DF reg", 0), ("SSR", 1), ("MSR", 2), ("F Reg", 3), ("p reg", 4)),
        "误差": (("DF Error", 0), ("SSE", 1), ("MSE", 2)),
        "失拟": (("DFLF", 0), ("SSLF", 1), ("MSLF", 2), ("F lack", 3), ("p lack", 4)),
        "纯误差": (("DFPE", 0), ("SSPE", 1), ("MSPE", 2)),
        "合计": (("DF Total", 0), ("SST", 1)),
    }
    local_names = {key: key for values in anova_rows.values() for key, _ in values}
    for label, metrics in anova_rows.items():
        native_row = _output_row(coefficient_table, label)
        for metric, index in metrics:
            available = _command_ok(nl, "LINEAR-FIT-01") and native_row is not None and len(native_row) > index
            token, native_value = native_row[index] if available else ("", None)
            _add(
                rows, category="统计", case_id="LINEAR-FIT-01", feature="线性回归",
                metric=f"ANOVA {label} {metric}", local=linear[local_names[metric]],
                native=native_value,
                tolerance=_rounding_tolerance(token) if available else data["tolerances"]["display_abs"],
                configuration=linear_case["configuration"],
                local_source="code.linear_fit.linear_fit",
                native_source="Minitab REGRESS TANOVA 输出表",
                judgment=f"ANOVA 表按显示值精度核对，native_token={token}。",
                forced_status=None if available else
                ("NOT_RUN" if not _command_ok(nl, "LINEAR-FIT-01") else "UNSUPPORTED"),
            )

    # Pearson uses complete pairs; compare Minitab's native correlation and p-value matrices.
    corr_case, corr_local = cases["COR-PAIR-MISSING-01"], local["COR-PAIR-MISSING-01"]
    corr_native = _matrix_values(first, "COR-PAIR-MISSING-01", "CORRELATION")
    p_native = _matrix_values(first, "COR-PAIR-MISSING-01", "PVALUES")
    pairwise_output = first.get("outputs", {}).get("COR-PAIR-MISSING-01-TABLE", {})
    corr_ok = _command_ok(first, "COR-PAIR-MISSING-01")
    native_r = corr_native[0][1] if corr_native else None
    native_p = p_native[0][1] if p_native else None
    direct_n = _pairwise_n(pairwise_output, "CORR_X", "CORR_Y")
    matches = (_infer_pearson_n(native_r, native_p, len(corr_case["x"]))
               if native_r is not None and native_p is not None else [])
    derived_n = matches[0] if len(matches) == 1 else None
    for metric, local_value, native_value in (
            ("有效配对 N（由原生 r/p 复算）", corr_local["N"], direct_n or derived_n),
            ("Pearson r", corr_local["r"], native_r),
            ("双侧零相关 p", corr_local["p"], native_p)):
        available = corr_ok and native_value is not None
        _add(
            rows, category="统计", case_id="COR-PAIR-MISSING-01", feature="相关分析",
            metric=metric, local=local_value, native=native_value,
            tolerance=data["tolerances"]["correlation_abs"],
            configuration=corr_case["configuration"],
            local_source="CorrelationDialog.apply → number_2lists → pearson_correlation",
            native_source=("Minitab CORRELATION PEARSON; SCORRELATION/SPVALUES"
                           if metric != "有效配对 N（由原生 r/p 复算）"
                           else "若表未存 N，则由原生 r/p 按 Pearson 双侧 t 检验反推"),
            judgment=("MiniJMP 两列共同有效行；Minitab 原生 pairwise correlation。"
                      if metric != "有效配对 N（由原生 r/p 复算）" else
                      (f"直接读取原生配对 N={direct_n}。" if direct_n is not None else
                       f"p=2·t.sf(|r|√((n−2)/(1−r²)), n−2)；在 3..{len(corr_case['x'])} 中唯一命中 "
                       f"n={derived_n}，原生 r/p 匹配容差 1e-12。")),
            forced_status=None if available else
            ("NOT_RUN" if not corr_ok else "UNSUPPORTED"),
        )
    if direct_n is None:
        _add(
            rows, category="统计", case_id="COR-PAIR-MISSING-01", feature="相关分析",
            metric="Minitab 直接输出的有效配对 N", local=corr_local["N"], native=None,
            tolerance=0, configuration=corr_case["configuration"],
            local_source="CorrelationDialog.apply → number_2lists",
            native_source="Minitab 19.1.0.1 TPCORRELATION 输出表及 M22 存储探测",
            judgment=("输出表显示总体使用行数 10、r、CI 和 p，但不显示这对变量的有效 N；"
                      "TPCORRELATION M22 探测返回“1 变元太多”。原生 r/p 反推的 N 已单列比较。"),
            forced_status="UNSUPPORTED",
        )
    # PCA component signs are aligned per component; reconstruction and diagnostics are sign-invariant.
    pca_case, pca_local = cases["PCA-02"], local["PCA-02"]
    pca_ok = _command_ok(first, "PCA-02")
    coef_columns = _stored(first, "PCA-02", "COEFFICIENTS")
    score_columns = _stored(first, "PCA-02", "SCORES")
    eigen = _stored(first, "PCA-02", "EIGEN")
    if coef_columns and score_columns and eigen:
        import numpy as np
        native_loadings = np.asarray(list(map(list, zip(*coef_columns))), dtype=float)
        native_scores = np.asarray(list(map(list, zip(*score_columns))), dtype=float)
        native_eigen = np.asarray(eigen, dtype=float)
        local_loadings = np.asarray(pca_local["loadings"], dtype=float)
        local_scores = np.asarray(pca_local["scores"], dtype=float)
        signs = np.where(np.sum(local_loadings * native_loadings, axis=0) < 0, -1.0, 1.0)
        aligned_loadings = local_loadings * signs
        aligned_scores = local_scores * signs
        values = np.asarray(pca_case["rows"], dtype=float)
        standardized = (values - values.mean(axis=0)) / values.std(axis=0, ddof=1)
        native_zhat = native_scores @ native_loadings.T
        native_reconstructed = native_zhat * values.std(axis=0, ddof=1) + values.mean(axis=0)
        native_q = np.sum((standardized - native_zhat) ** 2, axis=1)
        native_t2 = np.sum(native_scores ** 2 / native_eigen[:pca_case["n_components"]], axis=1)
        native_cumulative = np.cumsum(native_eigen / len(pca_case["columns"]))
        pca_metrics = [
            ("特征值", pca_local["eigenvalues"][:len(eigen)], eigen),
            ("累计方差解释率",
             pca_local["cumulative_explained_variance_ratio"][:len(eigen)],
             native_cumulative.tolist()),
            ("载荷（逐成分符号对齐）", aligned_loadings.tolist(), native_loadings.tolist()),
            ("得分（逐成分符号对齐）", aligned_scores.tolist(), native_scores.tolist()),
            ("2-PC 原单位重构", pca_local["reconstructed"], native_reconstructed.tolist()),
            ("T²（保留成分）", pca_local["t2"], native_t2.tolist()),
            ("Q 残差平方和", pca_local["q"], native_q.tolist()),
        ]
    else:
        pca_metrics = [(name, pca_local.get(key), None) for name, key in (
            ("特征值", "eigenvalues"), ("累计方差解释率", "cumulative_explained_variance_ratio"),
            ("载荷（逐成分符号对齐）", "loadings"), ("得分（逐成分符号对齐）", "scores"),
            ("2-PC 原单位重构", "reconstructed"), ("T²（保留成分）", "t2"), ("Q 残差平方和", "q"))]
    for metric, local_value, native_value in pca_metrics:
        direct_or_derived = metric in ("特征值", "载荷（逐成分符号对齐）", "得分（逐成分符号对齐）")
        _add(
            rows, category="多变量", case_id="PCA-02", feature="主成分分析 PCA",
            metric=metric, local=local_value, native=native_value,
            tolerance=data["tolerances"]["model_abs"],
            configuration=pca_case["configuration"],
            local_source="code.pca_analysis.fit_pca",
            native_source=("Minitab PCA COEFFICIENTS/SCORES/EIGEN" if direct_or_derived else
                           "由 Minitab 原生 SCORES/COEFFICIENTS/EIGEN 和输入均值、样本 SD 复算"),
            judgment=("特征向量和得分按同一 PC 点积符号对齐；不做额外尺度缩放。"
                      if metric in ("载荷（逐成分符号对齐）", "得分（逐成分符号对齐）") else
                      "相关矩阵 PCA；重构在标准化空间做 score × loadingᵀ，再还原原单位。"),
            forced_status=None if pca_ok and native_value is not None else
            ("NOT_RUN" if not pca_ok else "UNSUPPORTED"),
        )

    # PLS training fit, CV, model representation, and point prediction.
    pls_case, pls_local = cases["PLS-CV-01"], local["PLS-CV-01"]
    pls_ok = _command_ok(first, "PLS-CV-01")
    native_xscores = _matrix_values(first, "PLS-CV-01", "XSCORES")
    native_yscores = _matrix_values(first, "PLS-CV-01", "YSCORES")
    native_xloadings = _matrix_values(first, "PLS-CV-01", "XLOADINGS")
    native_yloadings = _matrix_values(first, "PLS-CV-01", "YLOADINGS")
    native_beta = _stored(first, "PLS-CV-01", "COEFFICIENTS")
    if all(value is not None for value in
           (native_xscores, native_yscores, native_xloadings, native_yloadings)):
        import numpy as np
        local_xscores = np.asarray(pls_local["x_scores"], dtype=float)
        local_yscores = np.asarray(pls_local["y_scores"], dtype=float)
        local_xloadings = np.asarray(pls_local["x_loadings"], dtype=float)
        local_yloadings = np.asarray(pls_local["y_loadings"], dtype=float)
        nx, ny = np.asarray(native_xscores), np.asarray(native_yscores)
        nxl, nyl = np.asarray(native_xloadings), np.asarray(native_yloadings)
        signs = np.where(np.sum(local_xloadings * nxl, axis=0) < 0, -1.0, 1.0)
        aligned = {
            "X 得分（组件符号对齐）": (local_xscores * signs, nx),
            "Y 得分（组件符号对齐）": (local_yscores * signs, ny),
            "X 载荷（组件符号对齐）": (local_xloadings * signs, nxl),
            "Y 载荷（组件符号对齐）": (local_yloadings * signs, nyl),
        }
    else:
        aligned = {}
    pls_stored_fits = _stored(first, "PLS-CV-01", "FITS")
    pls_cv_fits = _stored(first, "PLS-CV-01", "CVFITS")
    pls_cv = next((row for row in pls_local["cv"]
                   if row["n_components"] == pls_case["n_components"]), None)
    cv_predictions = sorted(
        (row for row in pls_local["cv_predictions"]
         if row["n_components"] == pls_case["n_components"]),
        key=lambda row: row["source_row"],
    )
    beta_terms = {row["term"]: row["estimate"] for row in pls_local["coefficients"]}
    native_intercept = None
    if native_beta is not None and len(native_beta) == len(pls_case["predictors"]):
        means_x = [sum(row[j] for row in pls_case["rows"]) / len(pls_case["rows"])
                   for j in range(len(pls_case["predictors"]))]
        mean_y = sum(row[-1] for row in pls_case["rows"]) / len(pls_case["rows"])
        native_intercept = mean_y - sum(b * means_x[j] for j, b in enumerate(native_beta))
    cv_press = (sum((row[-1] - fit) ** 2
                    for row, fit in zip(pls_case["rows"], pls_cv_fits))
                if pls_cv_fits is not None and len(pls_cv_fits) == len(pls_case["rows"]) else None)
    cv_rmse = math.sqrt(cv_press / len(pls_case["rows"])) if cv_press is not None else None
    pls_metrics = [
        ("训练拟合值", pls_local["fits"], pls_stored_fits),
        ("交叉验证拟合值", [row["predicted"] for row in cv_predictions], pls_cv_fits),
        ("原单位斜率", [beta_terms.get(name) for name in pls_case["predictors"]], native_beta),
        ("截距（原生斜率和输入均值复算）", beta_terms.get("Intercept"), native_intercept),
        ("新点预测值", pls_local["predictions"], _stored(first, "PLS-CV-01", "PFITS")),
        ("CV PRESS", pls_cv.get("press") if pls_cv else None, cv_press),
        ("CV RMSE", pls_cv.get("rmsecv") if pls_cv else None, cv_rmse),
    ]
    pls_metrics.extend((metric, local_value, native_value)
                       for metric, (local_value, native_value) in aligned.items())
    for metric, local_value, native_value in pls_metrics:
        _add(
            rows, category="多变量", case_id="PLS-CV-01", feature="偏最小二乘回归 PLS",
            metric=metric, local=local_value, native=native_value,
            tolerance=data["tolerances"]["model_abs"],
            configuration=pls_case["configuration"],
            local_source="code.pls_regression.fit_pls / PLSResult.predict",
            native_source=("Minitab PLS COEFFICIENTS/FITS/CVFITS/PFITS and component matrices"
                           if metric != "截距（原生斜率和输入均值复算）"
                           else "由 Minitab COEFFICIENTS 和固定输入均值按 b0=ȳ-Σβjx̄j 复算"),
            judgment=("CV groups match MiniJMP's contiguous 4-fold split; component scores and loadings "
                      "share one sign per component. The intercept is derived, not directly stored."),
            forced_status=None if pls_ok and native_value is not None else
            ("NOT_RUN" if not pls_ok else "UNSUPPORTED"),
        )
    return rows


def _status_counts(rows: list[dict]) -> dict:
    return {status: sum(row["status"] == status for row in rows) for status in STATUS_ORDER}


def summary_rows(rows: list[dict]) -> list[dict]:
    fields = ("范围", "配置数", "指标数", *STATUS_ORDER, "证据来源")
    summaries = []
    labels = {
        "SPC": "P0-A 属性图限值边界与规则缺口复核",
        "统计": "P0-C 描述统计、线性回归与 Pearson 缺失配对",
        "多变量": "P0-B PCA/PLS 模型与预测扩展",
    }
    for category, label in labels.items():
        selected = [row for row in rows if row["category"] == category]
        counts = _status_counts(selected)
        summaries.append({
            "范围": label, "配置数": len({row["case_id"] for row in selected}),
            "指标数": len(selected), **counts,
            "证据来源": "phase8 固定输入；Minitab 19.1.0.1 COM；MiniJMP 生产入口",
        })
    counts = _status_counts(rows)
    summaries.append({
        "范围": "第六轮合计", "配置数": len({row["case_id"] for row in rows}),
        "指标数": len(rows), **counts,
        "证据来源": "phase8/comparison.csv",
    })
    return summaries


def _hash(value) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def update_feature_matrix() -> None:
    with MATRIX.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = tuple(reader.fieldnames or ())
        matrix = list(reader)
    if len(matrix) != 90:
        raise AssertionError(f"90 项矩阵数量改变：{len(matrix)}")
    updates = {
        "描述性统计": "单列菜单新增固定配置；N、缺失数、均值、样本标准差、标准误、方差、变异系数、中位数、总和、最小/最大值、极差、偏度和峰度按 Minitab STATS 对标。四分位数按 DESCRIBE 显示精度核验。",
        "线性回归": "独立 linear_fit 菜单入口新增 5 个 X 水平、每水平 4 次重复的原生案例；对标系数、系数标准误、逐点拟合和残差。",
        "相关分析": "第六轮新增 Pearson 两列不同位置缺失案例；r、双侧 p 与原生值 PASS；有效 N=7 由原生 r/p 按双侧 t 关系唯一复算 PASS。Minitab 直接配对 N 字段未输出，保留 1 项 UNSUPPORTED。原 Spearman/Kendall 方法差异不变。",
        "主成分分析": "phase7 3-PC 原生指标保持；phase8 新增 2-PC 配置，按符号对齐核验载荷/得分，并由原生 score、loading、eigen 严格复算累计解释率、原单位重构、T² 和 Q。",
        "偏最小二乘回归（PLS）": "phase7 截距原生列缺失由 b0=ȳ-Σβjx̄j 复算，截距与训练拟合值通过；phase8 新增 2 成分、4 折分组交叉验证及 3 点原单位预测。预测区间未覆盖。",
        "控制图 P": "phase7 可变样本量点/中心线/限通过；phase8 零值与缺失组点限通过。原 phase7 16 项零报警标志复算通过；新增 39 组变样本量序列核对 Test 1–4，Test 3/4 的 6/14 点窗口与 Minitab TRESULTS 末点相差一行，记 METHOD_DIFF。",
        "控制图 NP": "phase7 固定样本量点/中心线/限通过；phase8 零值与缺失组点限通过。原 phase7 16 项零报警标志复算通过；新增 39 组固定样本量序列核对 Test 1–4，Test 3/4 的 6/14 点窗口与 Minitab TRESULTS 末点相差一行，记 METHOD_DIFF。",
        "控制图 C": "phase7 固定机会数点/中心线/限通过；phase8 零值与缺失组点限通过。原 phase7 16 项零报警标志复算通过；新增 39 组固定机会序列核对 Test 1–4，Test 3/4 的 6/14 点窗口与 Minitab TRESULTS 末点相差一行，记 METHOD_DIFF。",
        "控制图 U": "phase7 可变机会数点/中心线/限通过；phase8 零值与缺失组点限通过。原 phase7 16 项零报警标志复算通过；新增 39 组变机会序列核对 Test 1–4，Test 3/4 的 6/14 点窗口与 Minitab TRESULTS 末点相差一行，记 METHOD_DIFF。",
    }
    marker = "第六轮（phase8）限定范围："
    matched = set()
    untouched = {row["功能名称"]: dict(row) for row in matrix if row["功能名称"] not in updates}
    for row in matrix:
        feature = row["功能名称"]
        if feature not in updates:
            continue
        if feature in ("描述性统计", "线性回归"):
            row["Minitab 19 对标"] = "部分验证"
        elif feature in {"控制图 P", "控制图 NP", "控制图 C", "控制图 U"}:
            row["Minitab 19 对标"] = "方法不同"
        note = row["备注及证据来源"].split(marker, 1)[0].rstrip()
        row["备注及证据来源"] = (
            f"{note} {marker}{updates[feature]} | "
            "Out/statistics_minitab19_parity/phase8/case_inputs.json; "
            "minitab_session_commands.txt; minitab_raw_outputs.txt; "
            "minijmp_results.json; minitab_results.json; comparison.csv; summary.csv; "
            "repeatability_check.txt"
        )
        matched.add(feature)
    if matched != set(updates):
        raise AssertionError(f"矩阵目标行不完整：{matched}")
    with MATRIX.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(matrix)
    with MATRIX.open(encoding="utf-8-sig", newline="") as stream:
        written = list(csv.DictReader(stream))
    if len(written) != 90 or {
            row["功能名称"]: dict(row) for row in written if row["功能名称"] not in updates
    } != untouched:
        raise AssertionError("矩阵行数变化或未覆盖行被修改")


def write_outputs(data: dict, local: dict, runs: list[dict], stderr: list[str],
                  exit_codes: list[int]) -> list[dict]:
    rows = compare_results(data, local, runs)
    (PHASE8 / "minijmp_results.json").write_text(
        json.dumps({"version": "MiniJMP production code at run time", "results": _builtin(local)},
                   ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    (PHASE8 / "minitab_results.json").write_text(
        json.dumps({"runs": runs, "stderr": stderr, "exit_codes": exit_codes},
                   ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (PHASE8 / "comparison.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=COMPARISON_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    summaries = summary_rows(rows)
    with (PHASE8 / "summary.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=tuple(summaries[0]))
        writer.writeheader()
        writer.writerows(summaries)

    normalized = [{
        case_id: {key: output.get(key) for key in
                  ("command", "executed", "stored", "storage_errors", "command_output_error")}
        for case_id, output in run.get("outputs", {}).items()
    } for run in runs]
    stable = bool(len(normalized) == 2 and _hash(normalized[0]) == _hash(normalized[1]))
    manifest = {
        "runs": len(runs), "exit_codes": exit_codes,
        "output_hashes": [_hash(run.get("outputs", {})) for run in runs],
        "stable": stable,
        "compared_fields": "command, execution/error state, stored columns/matrices and storage errors; excludes COM PID, counters and output-document timestamps",
    }
    (PHASE8 / "repeatability_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (PHASE8 / "repeatability_check.txt").write_text(
        f"Minitab 19.1.0.1 isolated COM runs: {len(runs)}; exit_codes={exit_codes}; "
        f"stored-result hashes stable={stable}; hashes={manifest['output_hashes']}\n",
        encoding="utf-8")
    command_lines = ["Minitab 19.1.0.1 phase8 Session Commands; commands are fixed in verify_statistics_minitab19_phase8.py."]
    if runs and runs[0].get("metadata", {}).get("input_commands"):
        command_lines.extend(("\n===== missing values loaded by SET =====",
                              *runs[0]["metadata"]["input_commands"]))
    for item in command_specs(data["cases"]):
        command_lines.extend((f"\n===== {item['case_id']} =====", item["command"]))
    (PHASE8 / "minitab_session_commands.txt").write_text(
        "\n".join(command_lines) + "\n", encoding="utf-8")
    raw = []
    for run_number, run in enumerate(runs, 1):
        raw.append(f"===== Minitab COM run {run_number}; exit={exit_codes[run_number - 1]} =====")
        for case_id, output in run.get("outputs", {}).items():
            raw.extend((
                f"\n===== {case_id}: Session command =====", output.get("command", ""),
                "===== OutputDocument/Outputs =====", output.get("output", ""),
                "===== Direct storage =====",
                json.dumps({key: output.get(key) for key in
                            ("executed", "stored", "storage_errors", "storage_columns",
                             "storage_matrices", "last_error", "error", "command_output_error")},
                           ensure_ascii=False, indent=2),
            ))
    raw.append("\n===== Reused phase7 evidence =====")
    raw.append("Attribute Test_1..4 storage: phase7/minitab_results.json; source rows and MiniJMP paths: phase7/case_inputs.json and code/control_chart.py.")
    raw.append("PLS-01 intercept is derived as b0=mean(y)-sum(beta_j*mean(x_j)); see phase8/comparison.csv judgment and archived phase7 coefficients/fits.")
    (PHASE8 / "minitab_raw_outputs.txt").write_text("\n".join(raw) + "\n", encoding="utf-8")
    update_feature_matrix()
    return rows


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "--com-worker":
        result = com_worker(sys.argv[2:] or None)
        sys.stdout.write(json.dumps(result, ensure_ascii=False, allow_nan=False))
        return 0 if not result.get("fatal_error") else 1
    data = load_inputs()
    local = production_results(data["cases"])
    if len(sys.argv) > 1 and sys.argv[1] == "--attribute-rules-only":
        case_ids = ("ATTR-P-RULES", "ATTR-NP-RULES", "ATTR-C-RULES", "ATTR-U-RULES")
        previous = json.loads((PHASE8 / "minitab_results.json").read_text(encoding="utf-8"))
        old_runs = previous.get("runs", [])
        old_codes = previous.get("exit_codes", [])
        if len(old_runs) != 2 or old_codes != [0, 0]:
            print("原 phase8 双跑基线不存在或未成功；未覆盖任何结果。", file=sys.stderr)
            return 1
        additions, errors, codes = [], [], []
        for _ in range(2):
            result, error, code = run_minitab(case_ids)
            additions.append(result)
            errors.append(error)
            codes.append(code)
        if (codes != [0, 0] or any(
                not all(_command_ok(run, case_id) for case_id in case_ids)
                for run in additions)):
            diagnostics = []
            for i, (run, error, code) in enumerate(zip(additions, errors, codes), 1):
                failed = {
                    case_id: {key: run.get("outputs", {}).get(case_id, {}).get(key)
                              for key in ("executed", "error", "last_error",
                                          "command_output_error", "storage_errors")}
                    for case_id in case_ids
                    if not _command_ok(run, case_id)
                    or run.get("outputs", {}).get(case_id, {}).get("storage_errors")
                }
                if code or error or run.get("fatal_error") or run.get("cleanup_error") or failed:
                    diagnostics.append({
                        "run": i, "exit_code": code, "stderr": error,
                        "fatal_error": run.get("fatal_error"),
                        "cleanup_error": run.get("cleanup_error"), "failed_commands": failed,
                    })
            print(f"属性图定向 COM 未完整成功：exit_codes={codes}；未覆盖原 phase8 结果。\n"
                  + json.dumps(diagnostics, ensure_ascii=False, indent=2), file=sys.stderr)
            return 1
        merged_runs = []
        for old_run, addition in zip(old_runs, additions):
            metadata = dict(old_run.get("metadata", {}))
            metadata["supplemental_attribute_rule_run"] = addition.get("metadata", {})
            merged_runs.append({
                **old_run,
                "metadata": metadata,
                "outputs": {**old_run.get("outputs", {}), **addition.get("outputs", {})},
            })
        stderr = [
            "\n".join(value for value in (previous.get("stderr", [""] * 2)[i], errors[i]) if value)
            for i in range(2)
        ]
        rows = write_outputs(data, local, merged_runs, stderr, [0, 0])
        counts = _status_counts(rows)
        stable = json.loads((PHASE8 / "repeatability_manifest.json").read_text(encoding="utf-8"))["stable"]
        print(f"Minitab 19.1.0.1 targeted COM runs={codes}; phase8 metrics={len(rows)}; "
              f"statuses={counts}; stable={stable}")
        return int(not (stable and counts["FAIL"] == 0 and counts["NOT_RUN"] == 0))

    runs, stderr, exit_codes = [], [], []
    for _ in range(2):
        result, error, code = run_minitab()
        runs.append(result)
        stderr.append(error)
        exit_codes.append(code)
    rows = write_outputs(data, local, runs, stderr, exit_codes)
    counts = _status_counts(rows)
    stable = json.loads((PHASE8 / "repeatability_manifest.json").read_text(encoding="utf-8"))["stable"]
    print(f"Minitab 19.1.0.1; COM runs={exit_codes}; phase8 metrics={len(rows)}; statuses={counts}; stable={stable}")
    return int(not (len(runs) == 2 and all(code == 0 for code in exit_codes)
                    and stable and counts["FAIL"] == 0 and counts["NOT_RUN"] == 0))


if __name__ == "__main__":
    raise SystemExit(main())
