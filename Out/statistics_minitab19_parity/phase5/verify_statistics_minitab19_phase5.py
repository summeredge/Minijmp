from __future__ import annotations

import csv
import gc
import json
import math
import statistics
import sys
import time
import traceback
from collections import Counter
from pathlib import Path


PHASE = Path(__file__).resolve().parent
ROOT = PHASE.parents[2]
OUT = ROOT / "Out" / "statistics_minitab19_parity"
CODE = ROOT / "code"
PHASE4 = OUT / "phase4"
INPUT = PHASE / "case_inputs.json"
PROJECT_PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
MTB_EXE = Path(r"D:\Program\Minitab 19\Mtb.exe")
MISSING_SENTINEL = 1.23456e30
STATUS_ORDER = ("PASS", "FAIL", "METHOD_DIFF", "UNSUPPORTED", "NOT_RUN")
COMPARISON_FIELDS = (
    "case_id", "功能", "统计量", "Minitab值", "MiniJMP值", "绝对误差", "容差", "结果",
    "Minitab结果来源", "MiniJMP结果来源", "统计定义/配置", "判断依据", "测试数据集",
    "Minitab参考版本", "Minitab原生字段", "Minitab存储列", "Minitab存储索引",
    "Minitab原生输出行", "工作包",
)
SUMMARY_FIELDS = ("case_id", "比较指标数", *STATUS_ORDER, "功能状态", "备注")

sys.path.insert(0, str(CODE))
sys.path.insert(0, str(OUT))
sys.path.insert(0, str(OUT / "phase4"))

import verify_statistics_minitab19 as matrix_builder  # noqa: E402
import verify_statistics_minitab19_phase4 as phase4  # noqa: E402
import verify_minitab19_com as com_check  # noqa: E402
from verify_doe_2x2 import capture_command_output, running_minitab_pids  # noqa: E402
from t_test import paired_t_test, t_test_1sample, t_test_2samples  # noqa: E402
from one_way_ANOVA import JMP_ANOVA_t_test, one_way_anova  # noqa: E402
from two_way_anova import two_way_anova  # noqa: E402
from nonpara_cor import kendall, spearman  # noqa: E402
from utilities import filter_voids, norm_test, number_2lists, number_list  # noqa: E402


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict], fields: tuple[str, ...]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def input_vectors(cases: dict) -> dict[int, tuple[str, list]]:
    old = phase4.load_inputs()["cases"]
    vectors = {
        index: (name, values)
        for index, (name, values) in phase4.input_vectors(old).items()
        if index in (16, 17, 18, 25, 26)
    }
    vectors.update({
        31: ("OneT", cases["one_sample_t_missing"]["values"]),
        32: ("PairBefore", cases["paired_t_one_side_missing"]["sample1"]),
        33: ("PairAfter", cases["paired_t_one_side_missing"]["sample2"]),
        34: ("Welch1", cases["welch_t_different_missing"]["sample1"]),
        35: ("Welch2", cases["welch_t_different_missing"]["sample2"]),
        36: ("Rank1X", cases["rank_one_column_missing"]["x"]),
        37: ("Rank1Y", cases["rank_one_column_missing"]["y"]),
        38: ("Rank2X", cases["rank_different_positions_missing"]["x"]),
        39: ("Rank2Y", cases["rank_different_positions_missing"]["y"]),
        40: ("NormalityY", cases["normality_missing"]["values"]),
        41: ("OneWayY", [v for values in cases["one_way_anova_missing"]["groups"].values() for v in values]),
        42: ("OneWayGroup", [name for name, values in cases["one_way_anova_missing"]["groups"].items() for _ in values]),
        43: ("TwoWayY", cases["two_way_anova_missing"]["response"]),
        44: ("FactorA", cases["two_way_anova_missing"]["factor_a"]),
        45: ("FactorB", cases["two_way_anova_missing"]["factor_b"]),
    })
    return vectors


def mtb_value(value):
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    return None if number == MISSING_SENTINEL else number


def run_minitab(cases: dict) -> dict:
    import pythoncom
    import win32com.client

    if not MTB_EXE.is_file() or com_check.file_version(MTB_EXE) != "19.1.0.1":
        raise RuntimeError(f"需要本机 Minitab 19.1.0.1：{MTB_EXE}")
    pids_before = running_minitab_pids()
    if pids_before:
        raise RuntimeError(f"启动前检测到现有 Mtb.exe PID {pids_before}；拒绝连接既有会话")

    app = project = ui = worksheet = columns = None
    outputs, loaded_inputs, commands = {}, {}, []
    try:
        app = win32com.client.DispatchEx("Mtb.Application")
        pythoncom.PumpWaitingMessages()
        ui = app.UserInterface
        ui.Visible = False
        ui.UserControl = False
        ui.DisplayAlerts = False
        hwnd = int(app.Handle)
        process_id, process_path = com_check.process_image_path(hwnd)
        app_path = str(app.AppPath)
        if (com_check.canonical(app_path) != com_check.canonical(MTB_EXE)
                or com_check.canonical(process_path) != com_check.canonical(MTB_EXE)
                or process_id in pids_before):
            raise RuntimeError(f"COM 新实例路径/PID 核验失败：{app_path}; {process_path}; {process_id}")
        app.New()
        project = app.ActiveProject
        worksheet = project.ActiveWorksheet
        columns = worksheet.Columns
        while int(columns.Count) < 124:
            column = columns.Add(None, None, 1)
            column.Name = f"P5C{int(columns.Count):03d}"

        for index, (name, values) in input_vectors(cases).items():
            column = columns.Item(index)
            column.Name = name
            if any(value is None for value in values):
                data = " ".join("*" if value is None else format(float(value), ".17g") for value in values)
                command = f"SET C{index}\n{data}\nEND"
                before = int(project.Commands.Count)
                project.ExecuteCommand(command)
                after = int(project.Commands.Count)
                error = str(app.LastError or "")
                commands.append({"command": command, "executed": after > before and not error.strip(), "last_error": error})
                if after <= before or error.strip():
                    raise RuntimeError(f"Minitab 缺失值载入失败 C{index}: {error}")
            else:
                column.SetData(tuple(values), 1, len(values))
            back = column.GetData()
            back = list(back) if isinstance(back, (tuple, list)) else [back]
            if len(back) != len(values):
                raise AssertionError(f"Minitab C{index} 回读行数不符")
            native_values = [mtb_value(value) for value in back]
            expected_n = sum(value is not None for value in values)
            actual_n = sum(value is not None for value in native_values)
            if expected_n != actual_n:
                raise AssertionError(f"Minitab C{index} 有效 N 不符：{expected_n} != {actual_n}")
            if all(isinstance(value, str) for value in values):
                if native_values != values:
                    raise AssertionError(f"Minitab C{index} 文本数据回读不同")
            else:
                for expected, actual in zip(values, native_values):
                    if expected is not None and float(expected) != actual:
                        raise AssertionError(f"Minitab C{index} 数值数据回读不同")
            loaded_inputs[str(index)] = {"name": name, "values": native_values, "effective_n": actual_n}

        analysis_commands = {
            "ols_multiple": phase4.COMMANDS["ols_multiple"],
            "ols_prediction": (
                "PREDICT C16;\n  CPREDICTORS C25 C26;\n  CONFIDENCE 95;\n  TPREDICTION;\n"
                "  PFITS C114;\n  PSEFITS C115;\n  CLIMITS C116 C117;\n  PLIMITS C118 C119."
            ),
            "one_sample_t_missing": "ONET C31;\n  TEST 8;\n  ALTERNATIVE 1;\n  CONFIDENCE 90;\n  SPVALUE C70;\n  SCONF C71 C72.",
            "paired_t_one_side_missing": "PAIR C32 C33;\n  TEST 0;\n  CONFIDENCE 95;\n  SPVALUE C73;\n  SCONF C74 C75.",
            "welch_t_different_missing": "TWOSAMPLE 95 C35 C34;\n  TEST 0;\n  SPVALUE C76;\n  SCONF C77 C78.",
            "spearman_rank_one_missing": "CORRELATION C36 C37;\n  SPEARMAN;\n  SCORRELATION M5;\n  SPVALUES M6.",
            "kendall_rank_one_missing": "XTABS C36 C37;\n  COUNTS;\n  CONCORDANT.",
            "spearman_rank_different_missing": "CORRELATION C38 C39;\n  SPEARMAN;\n  SCORRELATION M7;\n  SPVALUES M8.",
            "kendall_rank_different_missing": "XTABS C38 C39;\n  COUNTS;\n  CONCORDANT.",
            "normality_missing": "NORMTEST C40;\n  SPVALUE C79.",
            "one_way_anova_missing": (
                "ONEWAY;\n  RESPONSE C41;\n  CATEGORICAL C42;\n  CONFIDENCE 95;\n"
                "  FISHER;\n  TANOVA;\n  TMEANS;\n  TMTEST."
            ),
            "two_way_anova_missing": (
                "GLM;\n  RESPONSE C43;\n  CATEGORICAL C44 C45;\n  TERMS C44 C45 C44*C45;\n"
                "  EFFECT;\n  TANOVA;\n  TSUMMARY."
            ),
        }
        for command_id, command in analysis_commands.items():
            commands.append({"command": command, "case_id": command_id})
            before = int(project.Commands.Count)
            try:
                project.ExecuteCommand(command)
                after = int(project.Commands.Count)
                error = str(app.LastError or "")
                outputs[command_id] = {
                    "executed": after > before and not error.strip(),
                    "command_count": [before, after], "command": command,
                    "last_error": error,
                    "output": capture_command_output(project, after) if after > before else "",
                }
            except Exception as exc:
                outputs[command_id] = {
                    "executed": False, "command_count": [before, int(project.Commands.Count)],
                    "command": command, "error": f"{type(exc).__name__}: {exc}",
                    "output": "", "traceback": traceback.format_exc(),
                }

        storage = {
            "ols_prediction": {"fit": 114, "se_fit": 115, "ci_low": 116, "ci_high": 117, "pi_low": 118, "pi_high": 119},
            "one_sample_t_missing": {"p": 70, "bound_low": 71, "bound_high": 72},
            "paired_t_one_side_missing": {"p": 73, "ci_low": 74, "ci_high": 75},
            "welch_t_different_missing": {"p": 76, "ci_low": 77, "ci_high": 78},
            "normality_missing": {"p": 79},
        }
        for command_id, fields in storage.items():
            stored = {}
            errors = {}
            for field, index in fields.items():
                try:
                    values = columns.Item(index).GetData()
                    values = list(values) if isinstance(values, (tuple, list)) else [values]
                    stored[field] = [mtb_value(value) for value in values]
                except Exception as exc:
                    errors[field] = f"C{index}: {type(exc).__name__}: {exc}"
            outputs[command_id]["stored"] = stored
            if errors:
                outputs[command_id]["storage_errors"] = errors

        matrices = worksheet.Matrices
        matrix_storage = {
            "spearman_rank_one_missing": {"rho": ("M5", 2, 1), "p": ("M6", 2, 1)},
            "spearman_rank_different_missing": {"rho": ("M7", 2, 1), "p": ("M8", 2, 1)},
        }
        for command_id, fields in matrix_storage.items():
            stored, errors = {}, {}
            for field, (name, row, column) in fields.items():
                try:
                    matrix = next(matrices.Item(i) for i in range(1, int(matrices.Count) + 1)
                                  if str(matrices.Item(i).Name).casefold() == name.casefold())
                    rows, cols = int(matrix.RowCount), int(matrix.ColumnCount)
                    flat = [float(value) for value in matrix.GetData()]
                    if (rows, cols) != (2, 2) or len(flat) != 4:
                        raise ValueError(f"{name} 不是 2x2 矩阵")
                    stored[field] = [flat[(column - 1) * rows + row - 1]]
                except Exception as exc:
                    errors[field] = f"{name}: {type(exc).__name__}: {exc}"
            outputs[command_id]["stored"] = stored
            if errors:
                outputs[command_id]["storage_errors"] = errors

        return {
            "version": "19.1.0.1", "clsid": com_check.registered_server()[0],
            "registered_server": com_check.registered_server()[2], "app_path": app_path,
            "process_path": process_path, "process_id": process_id,
            "project_name": str(project.Name), "worksheet_name": str(worksheet.Name),
            "python": sys.executable, "loaded_inputs": loaded_inputs,
            "commands": commands, "outputs": outputs,
        }
    finally:
        columns = worksheet = project = app = ui = None
        gc.collect()
        for _ in range(15):
            if not running_minitab_pids():
                break
            time.sleep(0.2)


def add_local(local: dict, case_id: str, key: str, value, source: str) -> None:
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"MiniJMP 结果非有限值：{case_id}.{key}={value}")
    local[f"{case_id}.{key}"] = {"value": value, "source": source}


def production_results(cases: dict) -> dict:
    import pandas as pd
    from advanced_regression import fit_regression

    local = {}
    old = phase4.load_inputs()["cases"]["ols_multiple"]
    model = fit_regression(pd.DataFrame({"y": old["y"], "x1": old["x1"], "x2": old["x2"]}),
                           "y", ["x1", "x2"], model="OLS", alpha=0.05)
    prediction = model.predict(pd.DataFrame({"x1": [7], "x2": [5]}), alpha=0.05).iloc[0]
    for key, field in (("prediction", "predicted"), ("ci_low", "mean_ci_lower"),
                       ("ci_high", "mean_ci_upper"), ("pi_low", "pi_lower"), ("pi_high", "pi_upper")):
        add_local(local, "ols_prediction", key, prediction[field], "advanced_regression.fit_regression.predict; 95%")

    case = cases["one_sample_t_missing"]
    values = number_list(case["values"])
    result = t_test_1sample(values, case["mu0"], alpha=1-case["confidence"])
    for key, value in (("n", len(values)), ("mean", result["mean"]), ("stdev", result["stdev"]),
                       ("se", result["stdev"] / math.sqrt(len(values))), ("t", result["t"]),
                       ("df", result["df"]), ("p", result["p gt"]), ("bound_low", result["u0 lower"])):
        add_local(local, "one_sample_t_missing", key, value, "sample_test_dialog number_list → t_test.t_test_1sample")

    case = cases["paired_t_one_side_missing"]
    before, after = number_2lists(case["sample1"], case["sample2"])
    result = paired_t_test(before, after, u0=case["null_difference"], alpha=1-case["confidence"])
    for key, value in (("n", len(before)), ("mean", result["mean"]), ("stdev", result["stdev"]),
                       ("se", result["stdev"] / math.sqrt(len(before))), ("t", result["t"]),
                       ("df", result["df"]), ("p", result["p"]), ("ci_low", result["u0_95range"][0]),
                       ("ci_high", result["u0_95range"][1])):
        add_local(local, "paired_t_one_side_missing", key, value, "PairedTDialog number_2lists → t_test.paired_t_test")

    case = cases["welch_t_different_missing"]
    sample1, sample2 = number_list(case["sample1"]), number_list(case["sample2"])
    result = t_test_2samples(sample1, sample2, alpha=1-case["confidence"], d0=case["null_difference"], pooled=False)
    mean1, mean2 = statistics.mean(sample1), statistics.mean(sample2)
    sd1, sd2 = statistics.stdev(sample1), statistics.stdev(sample2)
    for key, value in (("n1", len(sample1)), ("n2", len(sample2)), ("mean1", mean1), ("mean2", mean2),
                       ("stdev1", sd1), ("stdev2", sd2), ("difference", mean2-mean1),
                       ("se", math.sqrt(sd1**2/len(sample1)+sd2**2/len(sample2))), ("t", result["t"]),
                       ("df", result["df"]), ("p", result["p"]), ("ci_low", result["CI"][0]),
                       ("ci_high", result["CI"][1])):
        add_local(local, "welch_t_different_missing", key, value, "Mean2SampleDialog number_list → t_test.t_test_2samples (Welch)")

    for case_id in ("rank_one_column_missing", "rank_different_positions_missing"):
        case = cases[case_id]
        x, y = number_2lists(case["x"], case["y"])
        for method, function in (("spearman", spearman), ("kendall", kendall)):
            result = function(x, y)
            for key, value in (("n", len(x)), ("cor", result["cor"]), ("p", result["p"])):
                add_local(local, f"{case_id}_{method}", key, value, f"CorrelationDialog number_2lists → nonpara_cor.{method}")

    case = cases["normality_missing"]
    values = number_list(case["values"])
    result = norm_test(values)
    for key, value in (("n", len(values)), ("ad", result["AD s"]), ("p", result["AD p"]),
                       ("shapiro_w", result["shapiro s"]), ("shapiro_p", result["shapiro p"])):
        add_local(local, "normality_missing", key, value, "NormTestDialog number_list → utilities.norm_test")

    case = cases["one_way_anova_missing"]
    groups = {name: number_list(values) for name, values in case["groups"].items()}
    labels = list(groups)
    values = list(groups.values())
    result = one_way_anova(values, labels, alpha=1-case["confidence"])
    ss_between = result["MSB"] * result["df B"]
    ss_error = result["MSW"] * result["df W"]
    ss_total = ss_between + ss_error
    for key, value in (("n", sum(map(len, values))), ("df_between", result["df B"]),
                       ("df_error", result["df W"]), ("df_total", result["df TTL"]),
                       ("ss_between", ss_between), ("ms_between", result["MSB"]),
                       ("ss_error", ss_error), ("ms_error", result["MSW"]),
                       ("ss_total", ss_total), ("f", result["F"]), ("p", result["p"]),
                       ("s", math.sqrt(result["MSW"])),
                       ("r2_percent", 100*ss_between/ss_total),
                       ("r2_adjusted_percent", 100*(1-result["MSW"]/(ss_total/result["df TTL"])) )):
        add_local(local, "one_way_anova_missing", key, value, "Anova1WayDialog number_list → one_way_ANOVA.one_way_anova")
    for name in labels:
        add_local(local, f"one_way_anova_missing.{name}", "n", len(groups[name]), "Anova1WayDialog number_list per group")
        add_local(local, f"one_way_anova_missing.{name}", "mean", statistics.mean(groups[name]), "one_way_ANOVA.one_way_anova group mean")
        for key, value in zip(("ci_low", "ci_high"), result["CI"][labels.index(name)]):
            add_local(local, f"one_way_anova_missing.{name}", key, value, "Anova1WayDialog one_way_ANOVA.one_way_anova 95% CI")
    pairwise = JMP_ANOVA_t_test(values, labels)
    for i in range(1, len(labels)):
        for j in range(i):
            key = f"pair_p_{labels[i]}_{labels[j]}"
            add_local(local, "one_way_anova_missing", key, pairwise["p"][i][j],
                      "Anova1WayDialog JMP_ANOVA_t_test; pooled two-sided p, no multiple-comparison adjustment")

    case = cases["two_way_anova_missing"]
    response_with_nan = [math.nan if value is None else value for value in case["response"]]
    factors_a, factors_b, response = filter_voids([case["factor_a"], case["factor_b"], response_with_nan])
    result = two_way_anova(response, factor_listA=factors_a, factor_listB=factors_b, interaction=True)
    ss_total = sum((v-statistics.mean(response))**2 for v in response)
    df_error = len(response)-1-result["DF A"]-result["DF B"]-result["DF AB"]
    for key, value in (("n", len(response)), ("df_a", result["DF A"]), ("df_b", result["DF B"]),
                       ("df_ab", result["DF AB"]), ("df_error", df_error), ("df_total", len(response)-1),
                       ("ss_a", result["SSA"]), ("ss_b", result["SSB"]), ("ss_ab", result["SSAB"]),
                       ("ss_error", result["SSE"]), ("ss_total", ss_total),
                       ("ms_a", result["MSA"]), ("ms_b", result["MSB"]), ("ms_ab", result["MSAB"]),
                       ("ms_error", result["MSE"]), ("f_a", result["F A"]), ("f_b", result["F B"]),
                       ("f_ab", result["F AB"]), ("p_a", result["p A"]), ("p_b", result["p B"]),
                       ("p_ab", result["p AB"]), ("s", math.sqrt(result["MSE"])),
                       ("r2_percent", 100*(1-result["SSE"]/ss_total)),
                       ("r2_adjusted_percent", 100*(1-(result["SSE"]/df_error)/(ss_total/(len(response)-1))))):
        add_local(local, "two_way_anova_missing", key, value, "Anova2WayDialog filter_voids → two_way_anova Type III")
    return local


def pairwise_n(values1: list, values2: list) -> int:
    return sum(a is not None and b is not None for a, b in zip(values1, values2))


def add_row(rows, local, native, *, case_id, feature, metric, minijmp_key, command_id,
            config, dataset, package, source_type="direct", field="", storage_col="", storage_index=0,
            row_aliases=(), column_aliases=(), status_override="", reason="", tolerance=None,
            input_column=None, input_n=None, display_value=None, display_token=""):
    state = native["outputs"].get(command_id, {})
    local_result = local.get(minijmp_key)
    value = local_result["value"] if local_result else None
    raw_output = state.get("output", "")
    reference = None
    token = ""
    status = status_override
    if state.get("executed") is not True:
        status = "NOT_RUN"
        reason = reason or state.get("last_error") or state.get("error") or "Minitab 命令未执行。"
    elif source_type == "direct":
        values = state.get("stored", {}).get(field, [])
        if len(values) <= storage_index or values[storage_index] is None:
            status = "NOT_RUN"
            reason = reason or f"Minitab 原生存储字段 {field} 未返回值。"
        else:
            reference = float(values[storage_index])
            tolerance = 1e-10 if tolerance is None else tolerance
    elif source_type == "display":
        try:
            reference, token = matrix_builder.displayed_cell(raw_output, row_aliases, column_aliases)
            tolerance = matrix_builder.display_tolerance(token)
        except (ValueError, TypeError):
            status = "NOT_RUN"
            reason = reason or f"不能从 Minitab 原生输出读取 {row_aliases}/{column_aliases}。"
    elif source_type == "display_value":
        if display_value is None:
            status = "NOT_RUN"
            reason = reason or "Minitab 原生输出字段解析失败。"
        else:
            reference, token = float(display_value), display_token
            tolerance = matrix_builder.display_tolerance(token)
    elif source_type == "derived_native":
        reference = float(display_value)
        tolerance = 0.0 if tolerance is None else tolerance
    elif source_type == "native_input_n":
        reference = float(input_n)
        token = str(int(reference))
        tolerance = 0.0
        storage_col = input_column
        field = "Minitab worksheet readback: effective N"
    elif source_type == "unavailable":
        status = status or "UNSUPPORTED"
        reason = reason or "Minitab 19.1.0.1 未提供可稳定读取的对应原生字段。"
    if value is None:
        status = "NOT_RUN"
        reason = reason or "MiniJMP 生产入口未返回对应指标。"
    elif reference is not None and status not in ("METHOD_DIFF", "UNSUPPORTED", "NOT_RUN", "FAIL"):
        error = abs(value-reference)
        status = "PASS" if error <= tolerance or math.isclose(error, tolerance, rel_tol=1e-12, abs_tol=1e-15) else "FAIL"
    else:
        error = abs(value-reference) if value is not None and reference is not None else None

    if source_type == "direct":
        source = f"{command_id} / Minitab worksheet storage {field}"
    elif source_type == "display":
        source = f"{command_id} / OutputDocument.Text；{row_aliases or '统计表'} / {column_aliases}；显示 {token}"
    elif source_type == "display_value":
        source = f"{command_id} / OutputDocument.Text；显示值 {token}"
    elif source_type == "derived_native":
        source = f"{command_id} / 由 Minitab 命令定义推导；{display_token}"
    elif source_type == "native_input_n":
        source = f"Minitab C{input_column} SetData/SET 后回读；有效观测数"
    else:
        source = f"{command_id} / 未取得原生字段"
    rows.append({
        "case_id": case_id, "功能": feature, "统计量": metric,
        "Minitab值": format(reference, ".15g") if reference is not None else "",
        "MiniJMP值": format(value, ".15g") if value is not None else "",
        "绝对误差": format(error, ".8g") if error is not None else "",
        "容差": format(tolerance, ".8g") if tolerance is not None else "",
        "结果": status, "Minitab结果来源": source,
        "MiniJMP结果来源": local_result["source"] if local_result else "",
        "统计定义/配置": config, "判断依据": reason or (
            f"Minitab 显示值 {token}，按半个显示单位容差比较。" if source_type == "display" else
            "Minitab 原生结果与 MiniJMP 生产入口比较。"),
        "测试数据集": dataset, "Minitab参考版本": native["version"],
        "Minitab原生字段": field or ("/".join(column_aliases) if column_aliases else ""),
        "Minitab存储列": storage_col, "Minitab存储索引": storage_index if source_type == "direct" else "",
        "Minitab原生输出行": token, "工作包": package,
    })


def first_report_values(raw: str, heading: str, count: int) -> list[tuple[float, str]]:
    lines = raw.replace("\r", "\n").splitlines()
    start = next((i for i, line in enumerate(lines) if heading in line), None)
    if start is None:
        raise ValueError(f"Minitab 输出缺少区段：{heading}")
    for line in lines[start+1:start+12]:
        tokens = matrix_builder.NUMBER_RE.findall(line)
        if "(" in line and len(tokens) >= count:
            return [(float(token), token) for token in tokens[:count]]
    raise ValueError(f"Minitab 输出区段 {heading} 中缺少数值行")


def displayed_interval(raw: str, row_label: str) -> list[tuple[float, str]]:
    lines = raw.replace("\r\n", "\n").replace("\r", "\n").splitlines()
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith(row_label) or len(stripped) == len(row_label):
            continue
        if not stripped[len(row_label)].isspace() or "(" not in line:
            continue
        tokens = matrix_builder.NUMBER_RE.findall(line)
        if len(tokens) >= 2:
            return [(float(token), token) for token in tokens[-2:]]
    raise ValueError(f"Minitab 输出未找到 {row_label} 均值区间")


def displayed_last_value(raw: str, row_label: str) -> tuple[float, str]:
    for line in raw.replace("\r\n", "\n").replace("\r", "\n").splitlines():
        stripped = line.strip()
        if stripped.startswith(row_label) and len(stripped) > len(row_label) and stripped[len(row_label)].isspace():
            tokens = matrix_builder.NUMBER_RE.findall(line)
            if tokens:
                return float(tokens[-1]), tokens[-1]
    raise ValueError(f"Minitab 输出未找到 {row_label} 行")


def main() -> int:
    if com_check.canonical(sys.executable) != com_check.canonical(PROJECT_PYTHON):
        raise RuntimeError(f"请使用项目解释器运行：{PROJECT_PYTHON}")
    inputs = read_json(INPUT)
    local = production_results(inputs["cases"])
    legacy_welch_review()
    write_json(PHASE / "minijmp_results.json", {"python": sys.executable, "case_inputs": inputs, "results": local})
    native = run_minitab(inputs["cases"])
    write_json(PHASE / "minitab_results.json", native)
    write_json(PHASE / "minitab_metadata.json", {
        key: native[key] for key in ("version", "clsid", "registered_server", "app_path", "process_path",
                                     "process_id", "project_name", "worksheet_name", "python")
    })

    commands = [entry["command"] for entry in native["commands"]]
    for item in native["outputs"].values():
        commands.append(item["command"])
    (PHASE / "minitab_session_commands.txt").write_text("\n\n".join(commands)+"\n", encoding="utf-8")
    raw = []
    for key, item in native["outputs"].items():
        raw.append(f"===== {key} =====\n{item.get('command','')}\n{item.get('output') or '(empty)'}\nLastError: {item.get('last_error', item.get('error',''))}")
    (PHASE / "minitab_raw_outputs.txt").write_text("\n\n".join(raw)+"\n", encoding="utf-8")

    rows = []
    data = inputs["cases"]
    # OLS PREDICT: the worksheet model is keyed by response C16 in Minitab 19.
    for key, metric, field, column, config in (
        ("prediction", "新 X 预测值", "fit", "C114", "x1=7; x2=5; 95%"),
        ("ci_low", "均值响应 95% CI 下限", "ci_low", "C116", "x1=7; x2=5; 95%"),
        ("ci_high", "均值响应 95% CI 上限", "ci_high", "C117", "x1=7; x2=5; 95%"),
        ("pi_low", "新观测 95% PI 下限", "pi_low", "C118", "x1=7; x2=5; 95%"),
        ("pi_high", "新观测 95% PI 上限", "pi_high", "C119", "x1=7; x2=5; 95%"),
    ):
        add_row(rows, local, native, case_id="ols_prediction", feature="18完整回归分析", metric=metric,
                minijmp_key=f"ols_prediction.{key}", command_id="ols_prediction", field=field,
                storage_col=column, tolerance=1e-8, config=config,
                dataset="phase4/case_inputs.json#cases.ols_multiple", package="P0-A")

    one = data["one_sample_t_missing"]
    n = len(number_list(one["values"]))
    cfg = f"μ0={one['mu0']}; right-tailed; confidence={one['confidence']}; valid N={n}; null is SET '*'"
    for metric, key, aliases in (
        ("样本均值", "mean", ("均值", "Mean")), ("样本标准差", "stdev", ("标准差", "StDev")),
        ("均值标准误", "se", ("均值标准误", "SE Mean")), ("t", "t", ("T 值", "T-Value", "T Value")),
    ):
        add_row(rows, local, native, case_id="one_sample_t_missing", feature="25单样本均值 t 检验",
                metric=metric, minijmp_key=f"one_sample_t_missing.{key}", command_id="one_sample_t_missing",
                config=cfg, dataset="phase5/case_inputs.json#cases.one_sample_t_missing", package="P0-B",
                source_type="display", column_aliases=aliases)
    add_row(rows, local, native, case_id="one_sample_t_missing", feature="25单样本均值 t 检验",
            metric="有效 N", minijmp_key="one_sample_t_missing.n", command_id="one_sample_t_missing",
            source_type="native_input_n", input_column=31, input_n=n, config=cfg,
            dataset="phase5/case_inputs.json#cases.one_sample_t_missing", package="P0-B")
    add_row(rows, local, native, case_id="one_sample_t_missing", feature="25单样本均值 t 检验",
            metric="自由度", minijmp_key="one_sample_t_missing.df", command_id="one_sample_t_missing",
            source_type="derived_native", display_value=n-1, display_token=f"ONET df=N−1={n-1}",
            reason="Minitab ONET 输出不单列 df；按 ONET 定义由原生有效 N 推导。", config=cfg,
            dataset="phase5/case_inputs.json#cases.one_sample_t_missing", package="P0-B")
    for metric, key, field, col in (("右侧 p 值", "p", "p", "C70"), ("90% 单侧下限", "bound_low", "bound_low", "C71")):
        add_row(rows, local, native, case_id="one_sample_t_missing", feature="25单样本均值 t 检验",
                metric=metric, minijmp_key=f"one_sample_t_missing.{key}", command_id="one_sample_t_missing",
                field=field, storage_col=col, tolerance=1e-8, config=cfg,
                dataset="phase5/case_inputs.json#cases.one_sample_t_missing", package="P0-B")

    paired = data["paired_t_one_side_missing"]
    px, py = number_2lists(paired["sample1"], paired["sample2"])
    n = len(px)
    native_pair_n = pairwise_n(native["loaded_inputs"]["32"]["values"], native["loaded_inputs"]["33"]["values"])
    cfg = f"sample1−sample2; two-sided; confidence={paired['confidence']}; valid pairs N={n}; one null on sample2; zero retained"
    paired_output = native["outputs"]["paired_t_one_side_missing"]["output"]
    try:
        paired_tokens = first_report_values(paired_output, "差值的估计值", 3)
    except ValueError:
        paired_tokens = [(None, "")] * 3
    for index, (metric, key) in enumerate((("差值均值", "mean"), ("差值标准差", "stdev"), ("差值标准误", "se"))):
        display, token = paired_tokens[index]
        add_row(rows, local, native, case_id="paired_t_one_side_missing", feature="30配对 t 检验",
                metric=metric, minijmp_key=f"paired_t_one_side_missing.{key}", command_id="paired_t_one_side_missing",
                source_type="display_value", display_value=display, display_token=token,
                reason="从 PAIR 差值估计表读取 Minitab 显示值。" if display is not None else "未解析到 PAIR 差值估计表。",
                config=cfg, dataset="phase5/case_inputs.json#cases.paired_t_one_side_missing", package="P0-B")
    add_row(rows, local, native, case_id="paired_t_one_side_missing", feature="30配对 t 检验",
            metric="有效配对 N", minijmp_key="paired_t_one_side_missing.n", command_id="paired_t_one_side_missing",
            source_type="native_input_n", input_column="C32/C33", input_n=native_pair_n, config=cfg,
            dataset="phase5/case_inputs.json#cases.paired_t_one_side_missing", package="P0-B")
    add_row(rows, local, native, case_id="paired_t_one_side_missing", feature="30配对 t 检验",
            metric="t", minijmp_key="paired_t_one_side_missing.t", command_id="paired_t_one_side_missing",
            source_type="display", column_aliases=("T 值", "T-Value", "T Value"), config=cfg,
            dataset="phase5/case_inputs.json#cases.paired_t_one_side_missing", package="P0-B")
    add_row(rows, local, native, case_id="paired_t_one_side_missing", feature="30配对 t 检验",
            metric="自由度", minijmp_key="paired_t_one_side_missing.df", command_id="paired_t_one_side_missing",
            source_type="derived_native", display_value=n-1, display_token=f"PAIR df=N−1={n-1}",
            reason="Minitab PAIR 输出不单列 df；按 PAIR 定义由完整配对 N 推导。", config=cfg,
            dataset="phase5/case_inputs.json#cases.paired_t_one_side_missing", package="P0-B")
    for metric, key, field, col in (("双侧 p 值", "p", "p", "C73"), ("95% CI 下限", "ci_low", "ci_low", "C74"),
                                   ("95% CI 上限", "ci_high", "ci_high", "C75")):
        add_row(rows, local, native, case_id="paired_t_one_side_missing", feature="30配对 t 检验",
                metric=metric, minijmp_key=f"paired_t_one_side_missing.{key}", command_id="paired_t_one_side_missing",
                field=field, storage_col=col, tolerance=1e-10, config=cfg,
                dataset="phase5/case_inputs.json#cases.paired_t_one_side_missing", package="P0-B")

    welch = data["welch_t_different_missing"]
    wx, wy = number_list(welch["sample1"]), number_list(welch["sample2"])
    n1, n2 = len(wx), len(wy)
    native_n1 = native["loaded_inputs"]["34"]["effective_n"]
    native_n2 = native["loaded_inputs"]["35"]["effective_n"]
    cfg = f"Welch unpooled; two-sided; confidence=95%; N1={n1}, N2={n2}; 2 nulls in sample1, 1 in sample2; zero retained"
    for metric, key, column, aliases, row_alias in (
        ("样本 1 有效 N", "n1", 34, ("N",), ("Welch1",)), ("样本 2 有效 N", "n2", 35, ("N",), ("Welch2",)),
        ("样本 1 均值", "mean1", None, ("均值", "Mean"), ("Welch1",)),
        ("样本 2 均值", "mean2", None, ("均值", "Mean"), ("Welch2",)),
        ("样本 1 标准差", "stdev1", None, ("标准差", "StDev"), ("Welch1",)),
        ("样本 2 标准差", "stdev2", None, ("标准差", "StDev"), ("Welch2",)),
        ("t", "t", None, ("T 值", "T-Value", "T Value"), ()),
        ("自由度", "df", None, ("自由度", "DF"), ()),
    ):
        is_n = key in ("n1", "n2")
        add_row(rows, local, native, case_id="welch_t_different_missing", feature="29双样本 t 检验",
                metric=metric, minijmp_key=f"welch_t_different_missing.{key}", command_id="welch_t_different_missing",
                config=cfg, dataset="phase5/case_inputs.json#cases.welch_t_different_missing", package="P0-B/C",
                source_type="native_input_n" if is_n else "display",
                input_column=column if is_n else None,
                input_n=(native_n1 if key == "n1" else native_n2) if is_n else None,
                column_aliases=aliases, row_aliases=row_alias,
                status_override="METHOD_DIFF" if key == "df" else "",
                reason="Minitab 19 将 Welch 自由度截为整数；MiniJMP 保留 Welch-Satterthwaite 小数自由度。" if key == "df" else "")
    for metric, key, field, col, state in (
        ("Welch 双侧 p 值", "p", "p", "C76", "METHOD_DIFF"),
        ("95% CI 下限", "ci_low", "ci_low", "C77", "METHOD_DIFF"),
        ("95% CI 上限", "ci_high", "ci_high", "C78", "METHOD_DIFF"),
    ):
        add_row(rows, local, native, case_id="welch_t_different_missing", feature="29双样本 t 检验",
                metric=metric, minijmp_key=f"welch_t_different_missing.{key}", command_id="welch_t_different_missing",
                field=field, storage_col=col, tolerance=1e-10, config=cfg,
                dataset="phase5/case_inputs.json#cases.welch_t_different_missing", package="P0-B/C",
                status_override=state,
                reason="Minitab 19 截断 Welch 自由度并用整数自由度计算尾概率和置信区间；MiniJMP 保留分数自由度。" if state else "")

    for rank_case, command_suffix, x_col, y_col, matrix_r, matrix_p in (
        ("rank_one_column_missing", "rank_one_missing", 36, 37, "M5", "M6"),
        ("rank_different_positions_missing", "rank_different_missing", 38, 39, "M7", "M8"),
    ):
        rank = data[rank_case]
        rx, ry = number_2lists(rank["x"], rank["y"])
        n = len(rx)
        native_n = pairwise_n(native["loaded_inputs"][str(x_col)]["values"],
                              native["loaded_inputs"][str(y_col)]["values"])
        cfg = f"paired complete rows; N={n}; ties retained; null positions=" + ",".join(
            str(i+1) for i,(a,b) in enumerate(zip(rank["x"],rank["y"])) if a is None or b is None)
        spearman_id, kendall_id = f"spearman_{command_suffix}", f"kendall_{command_suffix}"
        add_row(rows, local, native, case_id=f"{rank_case}_spearman", feature="13相关分析",
                metric="有效配对 N", minijmp_key=f"{rank_case}_spearman.n", command_id=spearman_id,
                config=cfg, dataset=f"phase5/case_inputs.json#cases.{rank_case}", package="P0-B",
                source_type="native_input_n", input_column=f"C{x_col}/C{y_col}", input_n=native_n)
        add_row(rows, local, native, case_id=f"{rank_case}_spearman", feature="13相关分析",
                metric="Spearman rho", minijmp_key=f"{rank_case}_spearman.cor", command_id=spearman_id,
                field="rho", storage_col=matrix_r, tolerance=1e-10, config=cfg,
                dataset=f"phase5/case_inputs.json#cases.{rank_case}", package="P0-B")
        add_row(rows, local, native, case_id=f"{rank_case}_spearman", feature="13相关分析",
                metric="Spearman 双侧 p 值", minijmp_key=f"{rank_case}_spearman.p", command_id=spearman_id,
                field="p", storage_col=matrix_p, tolerance=1e-10, config=cfg,
                dataset=f"phase5/case_inputs.json#cases.{rank_case}", package="P0-B")
        add_row(rows, local, native, case_id=f"{rank_case}_kendall", feature="13相关分析",
                metric="有效配对 N", minijmp_key=f"{rank_case}_kendall.n", command_id=kendall_id,
                config=cfg, dataset=f"phase5/case_inputs.json#cases.{rank_case}", package="P0-B",
                source_type="native_input_n", input_column=f"C{x_col}/C{y_col}", input_n=native_n)
        # Minitab's XTABS CONCORDANT is a concordance test; MiniJMP reports the two-sided tau-b test.
        try:
            tau_value, tau_token = tau_b_display(native["outputs"].get(kendall_id, {}).get("output", ""))
        except ValueError:
            tau_value, tau_token = None, ""
        add_row(rows, local, native, case_id=f"{rank_case}_kendall", feature="13相关分析",
                metric="Kendall tau-b", minijmp_key=f"{rank_case}_kendall.cor", command_id=kendall_id,
                source_type="display_value", display_value=tau_value, display_token=tau_token,
                config=cfg, dataset=f"phase5/case_inputs.json#cases.{rank_case}", package="P0-B")
        try:
            p_value, p_token = concordance_p_display(native["outputs"].get(kendall_id, {}).get("output", ""))
        except ValueError:
            p_value, p_token = None, ""
        add_row(rows, local, native, case_id=f"{rank_case}_kendall", feature="13相关分析",
                metric="Minitab XTABS 一致性检验 p 值", minijmp_key=f"{rank_case}_kendall.p", command_id=kendall_id,
                source_type="display_value", display_value=p_value, display_token=p_token,
                config=cfg, dataset=f"phase5/case_inputs.json#cases.{rank_case}", package="P0-B",
                status_override="METHOD_DIFF",
                reason="XTABS CONCORDANT 检验有序类别一致性；MiniJMP 用 Kendall tau-b 双侧检验，保留既有方法差异。")

    normal = data["normality_missing"]
    normal_n = len(number_list(normal["values"]))
    native_normal_n = native["loaded_inputs"]["40"]["effective_n"]
    cfg = f"Minitab NORMTEST 默认 Anderson-Darling; effective N={normal_n}; missing='*'; zero retained"
    add_row(rows, local, native, case_id="normality_missing", feature="04正态性检验",
            metric="有效 N", minijmp_key="normality_missing.n", command_id="normality_missing",
            source_type="native_input_n", input_column=40, input_n=native_normal_n, config=cfg,
            dataset="phase5/case_inputs.json#cases.normality_missing", package="P0-C")
    try:
        ad, ad_token = matrix_builder.displayed_cell(native["outputs"]["normality_missing"]["output"],
                                                       ("Anderson-Darling", "Anderson", "AD"), ("AD",))
        add_row(rows, local, native, case_id="normality_missing", feature="04正态性检验",
                metric="Anderson-Darling 统计量", minijmp_key="normality_missing.ad", command_id="normality_missing",
                source_type="display_value", display_value=ad, display_token=ad_token, config=cfg,
                dataset="phase5/case_inputs.json#cases.normality_missing", package="P0-C")
    except (KeyError, ValueError, TypeError):
        add_row(rows, local, native, case_id="normality_missing", feature="04正态性检验",
                metric="Anderson-Darling 统计量", minijmp_key="normality_missing.ad", command_id="normality_missing",
                source_type="unavailable", status_override="UNSUPPORTED",
                reason="Minitab 19 NORMTEST COM 只返回正态概率图标题，未提供可稳定读取的 AD 统计量。",
                config=cfg, dataset="phase5/case_inputs.json#cases.normality_missing", package="P0-C")
    add_row(rows, local, native, case_id="normality_missing", feature="04正态性检验",
            metric="Anderson-Darling p 值", minijmp_key="normality_missing.p", command_id="normality_missing",
            field="p", storage_col="C79", tolerance=0.0005, config=cfg,
            dataset="phase5/case_inputs.json#cases.normality_missing", package="P0-C",
            reason="Minitab NORMTEST SPVALUE 按原生报告 3 位小数精度比较。")
    for metric, key in (("Shapiro-Wilk W", "shapiro_w"), ("Shapiro-Wilk p 值", "shapiro_p")):
        reason = "MiniJMP 实现 Shapiro-Wilk；Minitab 19 NORMTEST 提供 AD、RJTEST（Ryan-Joiner，与 Shapiro-Wilk 相似但定义不同）及 KSTEST，无同名 Shapiro-Wilk 原生字段；未将 RJ/KS 冒充参考值。"
        add_row(rows, local, native, case_id="normality_missing", feature="04正态性检验",
                metric=metric, minijmp_key=f"normality_missing.{key}", command_id="normality_missing",
                source_type="unavailable", status_override="UNSUPPORTED", reason=reason, config=cfg,
                dataset="phase5/case_inputs.json#cases.normality_missing", package="P0-C")
        rows[-1]["Minitab结果来源"] = "docs/minitab19_session_commands.pdf p.164–165；NORMTEST 无 Shapiro-Wilk 原生字段"

    # This is the one-way missing-response case requested as a representative additional test.
    one_case = data["one_way_anova_missing"]
    one_n = sum(len(number_list(v)) for v in one_case["groups"].values())
    one_y_native = native["loaded_inputs"]["41"]["values"]
    one_group_native = native["loaded_inputs"]["42"]["values"]
    one_native_n = sum(y is not None for y in one_y_native)
    one_cfg = f"traditional equal-variance one-way ANOVA; Fisher LSD; effective N={one_n}; missing responses omitted"
    add_row(rows, local, native, case_id="one_way_anova_missing", feature="34单因子方差分析",
            metric="有效 N", minijmp_key="one_way_anova_missing.n", command_id="one_way_anova_missing",
            source_type="native_input_n", input_column="C41/C42 complete response rows", input_n=one_native_n,
            config=one_cfg, dataset="phase5/case_inputs.json#cases.one_way_anova_missing", package="P0-B/C")
    for name in one_case["groups"]:
        n = len(number_list(one_case["groups"][name]))
        native_group_n = sum(y is not None and group == name for y,group in zip(one_y_native,one_group_native))
        add_row(rows, local, native, case_id="one_way_anova_missing", feature="34单因子方差分析",
                metric=f"{name} 组有效 N", minijmp_key=f"one_way_anova_missing.{name}.n",
                command_id="one_way_anova_missing", source_type="native_input_n",
                input_column="C41/C42 complete response rows", input_n=native_group_n, config=one_cfg,
                dataset="phase5/case_inputs.json#cases.one_way_anova_missing", package="P0-B/C")
    for metric,key,row_aliases,col_aliases in (
        ("组间 SS","ss_between",("Group","组别"),("Adj SS","Adjusted SS","调整平方和")),
        ("组间 DF","df_between",("Group","组别"),("DF","自由度")),
        ("组间 MS","ms_between",("Group","组别"),("Adj MS","Adjusted MS","调整均方")),
        ("F","f",("Group","组别"),("F-Value","F 值","F值")),
        ("p","p",("Group","组别"),("P-Value","P 值","P值")),
        ("误差 SS","ss_error",("Error","误差"),("Adj SS","Adjusted SS","调整平方和")),
        ("误差 DF","df_error",("Error","误差"),("DF","自由度")),
        ("误差 MS","ms_error",("Error","误差"),("Adj MS","Adjusted MS","调整均方")),
        ("总 SS","ss_total",("Total","总计","合计"),("Adj SS","Adjusted SS","调整平方和")),
        ("总 DF","df_total",("Total","总计","合计"),("DF","自由度")),
    ):
        add_row(rows, local, native, case_id="one_way_anova_missing", feature="34单因子方差分析",
                metric=metric, minijmp_key=f"one_way_anova_missing.{key}", command_id="one_way_anova_missing",
                source_type="display", row_aliases=row_aliases, column_aliases=col_aliases,
                config=one_cfg, dataset="phase5/case_inputs.json#cases.one_way_anova_missing", package="P0-C")

    one_output = native["outputs"]["one_way_anova_missing"]["output"]
    for metric, key, aliases in (("模型 S", "s", ("S",)), ("R² %", "r2_percent", ("R-sq",)),
                                 ("调整 R² %", "r2_adjusted_percent", ("R-sq（调整）", "R-sq (调整)"))):
        add_row(rows, local, native, case_id="one_way_anova_missing", feature="34单因子方差分析",
                metric=metric, minijmp_key=f"one_way_anova_missing.{key}", command_id="one_way_anova_missing",
                source_type="display", column_aliases=aliases, config=one_cfg,
                dataset="phase5/case_inputs.json#cases.one_way_anova_missing", package="P0-C")
    for name in one_case["groups"]:
        add_row(rows, local, native, case_id="one_way_anova_missing", feature="34单因子方差分析",
                metric=f"{name} 组均值", minijmp_key=f"one_way_anova_missing.{name}.mean",
                command_id="one_way_anova_missing", source_type="display", row_aliases=(name,),
                column_aliases=("均值", "Mean"), config=one_cfg,
                dataset="phase5/case_inputs.json#cases.one_way_anova_missing", package="P0-C")
        try:
            limits = displayed_interval(one_output, name)
        except ValueError:
            limits = [(None, ""), (None, "")]
        for (metric, key), (value, token) in zip(((f"{name} 均值 CI 下限", "ci_low"),
                                                 (f"{name} 均值 CI 上限", "ci_high")), limits):
            add_row(rows, local, native, case_id="one_way_anova_missing", feature="34单因子方差分析",
                    metric=metric, minijmp_key=f"one_way_anova_missing.{name}.{key}",
                    command_id="one_way_anova_missing", source_type="display_value", display_value=value,
                    display_token=token, reason="Minitab ONEWAY 均值表中的单组置信区间。" if value is not None else "未解析到组均值置信区间。",
                    config=one_cfg, dataset="phase5/case_inputs.json#cases.one_way_anova_missing", package="P0-C")
    for pair in ("B_A", "C_A", "C_B"):
        left, right = pair.split("_")
        try:
            p_value, p_token = displayed_last_value(one_output, f"{left} - {right}")
        except ValueError:
            p_value, p_token = None, ""
        add_row(rows, local, native, case_id="one_way_anova_missing", feature="34单因子方差分析",
                metric=f"Fisher LSD {left}−{right} 双侧 p", minijmp_key=f"one_way_anova_missing.pair_p_{pair}",
                command_id="one_way_anova_missing", source_type="display_value", display_value=p_value,
                display_token=p_token, reason="Minitab Fisher LSD 单个检验表行末 p 值。" if p_value is not None else "未解析到 Fisher LSD 两两比较。",
                config=one_cfg,
                dataset="phase5/case_inputs.json#cases.one_way_anova_missing", package="P0-C")

    two_case = data["two_way_anova_missing"]
    two_complete = sum(a is not None and b is not None and y is not None
                       for a,b,y in zip(two_case["factor_a"],two_case["factor_b"],two_case["response"]))
    two_native_n = sum(a is not None and b is not None and y is not None for a,b,y in zip(
        native["loaded_inputs"]["44"]["values"], native["loaded_inputs"]["45"]["values"],
        native["loaded_inputs"]["43"]["values"]))
    two_cfg = f"unbalanced 2x2 fixed effects; A+B+A*B; Type III adjusted SS; effect coding; complete-case N={two_complete}"
    add_row(rows, local, native, case_id="two_way_anova_missing", feature="35双因子方差分析",
            metric="有效 N", minijmp_key="two_way_anova_missing.n", command_id="two_way_anova_missing",
            source_type="native_input_n", input_column="C43:C45 complete rows", input_n=two_native_n,
            config=two_cfg, dataset="phase5/case_inputs.json#cases.two_way_anova_missing", package="P0-C")
    terms = (("FactorA", "a", ("FactorA",)), ("FactorB", "b", ("FactorB",)),
             ("FactorA*FactorB", "ab", ("FactorA*FactorB",)), ("Error", "error", ("Error", "误差")),
             ("Total", "total", ("Total", "合计", "总计")))
    columns = (("SS", "ss", ("Adj SS", "调整平方和")), ("DF", "df", ("DF", "自由度")),
               ("MS", "ms", ("Adj MS", "调整均方")), ("F", "f", ("F-Value", "F 值")),
               ("p", "p", ("P-Value", "P 值")))
    for term, suffix, term_aliases in terms:
        for stat_name, key, aliases in columns:
            local_key=f"two_way_anova_missing.{key}_{suffix}"
            if local_key not in local:
                continue
            add_row(rows, local, native, case_id="two_way_anova_missing", feature="35双因子方差分析",
                    metric=f"{term} {stat_name}", minijmp_key=local_key, command_id="two_way_anova_missing",
                    source_type="display", row_aliases=term_aliases, column_aliases=aliases,
                    config=two_cfg, dataset="phase5/case_inputs.json#cases.two_way_anova_missing", package="P0-C")
    two_output = native["outputs"]["two_way_anova_missing"]["output"]
    for metric, key, aliases in (("模型 S", "s", ("S",)), ("R² %", "r2_percent", ("R-sq",)),
                                 ("调整 R² %", "r2_adjusted_percent", ("R-sq（调整）", "R-sq (调整)"))):
        add_row(rows, local, native, case_id="two_way_anova_missing", feature="35双因子方差分析",
                metric=metric, minijmp_key=f"two_way_anova_missing.{key}", command_id="two_way_anova_missing",
                source_type="display", column_aliases=aliases, config=two_cfg,
                dataset="phase5/case_inputs.json#cases.two_way_anova_missing", package="P0-C")

    # Reclassify phase4 NOT_RUN rows where Minitab completed but had no intercept Wald fields.
    historical = read_json(PHASE4 / "minitab_results.json")
    historical_rows = list(csv.DictReader((PHASE4 / "comparison.csv").open(encoding="utf-8-sig")))
    if sum(row["case_id"] in ("binary_logistic", "poisson") and
           row["统计量"] in ("截距 z 统计量", "截距 p 值") for row in historical_rows) != 4:
        raise AssertionError("phase4 Logistic/Poisson 截距 z/p 历史记录不是预期的 4 项")
    review_native = {"version": historical["version"], "outputs": {}}
    for case_id in ("binary_logistic", "poisson"):
        state = historical["outputs"][case_id]
        if state.get("executed") is not True or state.get("last_error"):
            raise AssertionError(f"phase4 {case_id} 命令并未成功，不能重分类字段状态")
        coefficient_section = state["output"].split("系数", 1)[1].split("模型汇总", 1)[0]
        if any(label in coefficient_section for label in ("z 值", "Z-Value", "P 值", "P-Value")):
            raise AssertionError(f"phase4 {case_id} 系数表出现截距 z/p 字段，需重新对标")
        stored = state.get("stored", {})
        if set(stored) != {"coefficients", "se_coefficients"}:
            raise AssertionError(f"phase4 {case_id} 存储字段已变化：{sorted(stored)}")
        review_native["outputs"][case_id] = {"executed": True, "output": state["output"]}
        for old in historical_rows:
            if old["case_id"] != case_id or old["统计量"] not in ("截距 z 统计量", "截距 p 值"):
                continue
            key = f"{case_id}.reference_review.{old['统计量']}"
            local[key] = {"value": float(old["MiniJMP值"]), "source": old["MiniJMP结果来源"]}
            reason = "phase4 Minitab 命令已成功；原生系数表仅含系数、SE，COM 仅存系数与 SE，无截距 z/p 字段。历史 NOT_RUN 在第三轮确认为参考字段缺失，保留原 phase4 文件不变。"
            add_row(rows, local, review_native, case_id=case_id, feature=old["功能"], metric=old["统计量"],
                    minijmp_key=key, command_id=case_id, config=old["统计定义/配置"],
                    dataset=f"phase4/{old['测试数据集']}", package="P0-A", source_type="unavailable",
                    status_override="UNSUPPORTED", reason=reason)
            rows[-1]["Minitab结果来源"] = f"phase4/minitab_raw_outputs.txt#{case_id}；命令成功，原生系数表及存储无该字段"

    write_csv(PHASE / "comparison.csv", rows, COMPARISON_FIELDS)
    reference_fields = ("case_id", "功能", "统计量", "Minitab值", "Minitab结果来源", "Minitab原生字段",
                        "Minitab存储列", "Minitab存储索引", "Minitab原生输出行", "判断依据",
                        "测试数据集", "Minitab参考版本")
    write_csv(PHASE / "minitab_reference.csv", rows, reference_fields)
    grouped = {}
    for row in rows:
        grouped.setdefault(row["case_id"], []).append(row)
    summaries = []
    for case_id, items in grouped.items():
        counts = Counter(item["结果"] for item in items)
        states = [state for state in STATUS_ORDER if counts[state]]
        summaries.append({"case_id": case_id, "比较指标数": len(items), **{state: counts[state] for state in STATUS_ORDER},
                          "功能状态": "PASS" if states == ["PASS"] else (states[0] if len(states)==1 else "MIXED"),
                          "备注": "；".join(dict.fromkeys(item["判断依据"] for item in items if item["结果"]!="PASS"))})
    write_csv(PHASE / "summary.csv", summaries, SUMMARY_FIELDS)
    counts = Counter(row["结果"] for row in rows)
    overall = [{"本轮范围": "phase5 新增/复验及历史字段复核", "比较指标数": len(rows),
                **{state: counts[state] for state in STATUS_ORDER},
                "唯一固定案例数": len({row["测试数据集"] for row in rows}),
                "说明": "103 项新增/复验比较，另含 4 项 phase4 截距字段状态复核；不重复累计 phase4 历史 257 项。Welch 第一阶段复核另记在 welch_historical_review.csv。"}]
    write_csv(PHASE / "overall_summary.csv", overall,
              ("本轮范围", "比较指标数", *STATUS_ORDER, "唯一固定案例数", "说明"))
    package_rows = []
    for package, included in (("P0-A", {"P0-A"}), ("P0-B", {"P0-B", "P0-B/C"}),
                              ("P0-C", {"P0-C", "P0-B/C"})):
        selected = [row for row in rows if row["工作包"] in included]
        package_counts = Counter(row["结果"] for row in selected)
        package_rows.append({
            "工作包": package, "配置数": len({row["测试数据集"] for row in selected}), "指标数": len(selected),
            **{state: package_counts[state] for state in STATUS_ORDER},
            "备注": "P0-A 含 4 项 phase4 原生字段缺失复核；P0-B/C 共用 Welch 与单因子 ANOVA 案例，总体指标只计一次。",
        })
    write_csv(PHASE / "package_summary.csv", package_rows,
              ("工作包", "配置数", "指标数", *STATUS_ORDER, "备注"))

    matrix_builder.build_feature_matrix([])
    failed = [row for row in rows if row["结果"] in ("FAIL", "NOT_RUN")]
    print(f"P0-A/B/C phase5: {len({row['case_id'] for row in rows})} 个固定配置，{len(rows)} 个比较指标；"
          + ", ".join(f"{state}={counts[state]}" for state in STATUS_ORDER))
    return 1 if failed else 0


def tau_b_display(raw: str) -> tuple[float,str]:
    for line in raw.replace("\xa0", " ").splitlines():
        if "Kendall" in line and "Tau-b" in line:
            tokens=matrix_builder.NUMBER_RE.findall(line)
            if tokens: return float(tokens[-1]),tokens[-1]
    raise ValueError("Minitab XTABS 输出未找到 Kendall Tau-b")


def concordance_p_display(raw: str) -> tuple[float,str]:
    lines=raw.replace("\xa0", " ").splitlines()
    for index,line in enumerate(lines):
        if "一致性检验" in line or "Concordance Test" in line:
            for candidate in lines[index+1:index+6]:
                tokens=matrix_builder.NUMBER_RE.findall(candidate)
                if tokens: return float(tokens[-1]),tokens[-1]
    raise ValueError("Minitab XTABS 输出未找到一致性检验 p 值")


def legacy_welch_review() -> list[dict]:
    from scipy.stats import t as t_distribution

    cases = read_json(OUT / "case_inputs.json")["cases"]["two_sample_t"]
    result = t_test_2samples(cases["sample1"], cases["sample2"], pooled=False)
    old_rows = {}
    with (OUT / "comparison.csv").open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            if row["case_id"] == "two_sample_t":
                old_rows[row["统计量"]] = row
    df_display = float(old_rows["df"]["Minitab值"])
    p_minitab = float(old_rows["p"]["Minitab值"])
    p_floor = float(2 * t_distribution.sf(abs(result["t"]), math.floor(result["df"])))
    p_fractional = float(2 * t_distribution.sf(abs(result["t"]), result["df"]))
    t_display = float(old_rows["t"]["Minitab值"])
    se_minitab = float(old_rows["SE difference"]["Minitab值"])
    se_minijmp = float(old_rows["SE difference"]["MiniJMP值"])
    if abs(t_display-result["t"]) > 0.005 or not math.isclose(se_minitab, se_minijmp, rel_tol=1e-10, abs_tol=1e-12):
        raise AssertionError("第一阶段 Welch t/标准误与当前 MiniJMP 固定输入复算不一致")
    if not math.isclose(p_minitab, p_floor, rel_tol=1e-10, abs_tol=1e-12):
        raise AssertionError(f"历史 Welch 原生 p 不匹配截断 df 复算：{p_minitab} vs {p_floor}")
    if not math.isclose(p_fractional, result["p"], rel_tol=1e-10, abs_tol=1e-12):
        raise AssertionError("MiniJMP Welch p 与分数自由度复算不符")
    records = [
        {"统计量": "t", "Minitab 19.1.0.1": old_rows["t"]["Minitab值"],
         "MiniJMP": format(result["t"], ".15g"), "截断 df 复算": "", "结果": "PASS",
         "依据": "Minitab 显示 t=-2.79，两位小数容差为 0.005；两边使用相同 Welch 标准误。"},
        {"统计量": "df", "Minitab 19.1.0.1": format(df_display, ".15g"),
         "MiniJMP": format(result["df"], ".15g"), "截断 df 复算": format(math.floor(result["df"]), ".15g"),
         "结果": "METHOD_DIFF", "依据": "Minitab 桌面版按 Welch-Satterthwaite df 向下截为整数；MiniJMP 保留分数 df。"},
        {"统计量": "双侧 p", "Minitab 19.1.0.1": format(p_minitab, ".15g"),
         "MiniJMP": format(result["p"], ".15g"), "截断 df 复算": format(p_floor, ".15g"),
         "结果": "METHOD_DIFF", "依据": "Minitab 原生 p 与相同 t 值、df=12 的双侧尾概率吻合；分数 df 得到 MiniJMP p。"},
        {"统计量": "SE difference", "Minitab 19.1.0.1": format(se_minitab, ".15g"),
         "MiniJMP": format(se_minijmp, ".15g"), "截断 df 复算": "", "结果": "PASS",
         "依据": "Minitab 与 MiniJMP 的不合并样本方差、n1/n2 和 Welch 标准误一致。"},
    ]
    write_csv(PHASE / "welch_historical_review.csv", records,
              ("统计量", "Minitab 19.1.0.1", "MiniJMP", "截断 df 复算", "结果", "依据"))
    return records


if __name__ == "__main__":
    raise SystemExit(main())
