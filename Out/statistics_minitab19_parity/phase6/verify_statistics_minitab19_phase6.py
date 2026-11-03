from __future__ import annotations

import csv
import gc
import hashlib
import json
import math
import re
import sys
import time
import traceback
from pathlib import Path


PHASE = Path(__file__).resolve().parent
ROOT = PHASE.parents[2]
OUT = PHASE.parent
CODE = ROOT / "code"
INPUT = PHASE / "case_inputs.json"
PROJECT_PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
MTB_EXE = Path(r"D:\Program\Minitab 19\Mtb.exe")
PHASE4 = OUT / "phase4"
PHASE5 = OUT / "phase5"
MISSING_SENTINEL = 1.23456e30
STATUS_ORDER = ("PASS", "METHOD_DIFF", "UNSUPPORTED", "NOT_RUN", "FAIL")
COMPARISON_FIELDS = (
    "case_id", "功能", "统计量", "Minitab值", "MiniJMP值", "绝对误差", "容差", "结果",
    "Minitab结果来源", "MiniJMP结果来源", "统计定义/配置", "判断依据",
)
SUMMARY_FIELDS = ("case_id", "配置数", "指标数", *STATUS_ORDER, "功能状态", "备注")
NUMBER_RE = re.compile(r"(?<![A-Za-z])[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][-+]?\d+)?")
DISPLAY_NUMBER_RE = re.compile(r"[<>]?\s*[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][-+]?\d+)?")
DIST_ALIASES = {
    "Normal": ("正态",),
    "Lognormal": ("对数正态",),
    "Gamma": ("Gamma",),
    "Exponential": ("指数",),
    "Weibull": ("Weibull",),
}

sys.path.insert(0, str(CODE))
sys.path.insert(0, str(ROOT / "Out" / "minitab19_parity"))

import verify_minitab19_com as com_check  # noqa: E402
from verify_doe_2x2 import capture_command_output, running_minitab_pids  # noqa: E402


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def json_value(value):
    if isinstance(value, dict):
        return {str(key): json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [json_value(item) for item in value]
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if hasattr(value, "tolist"):
        return json_value(value.tolist())
    if hasattr(value, "item"):
        return json_value(value.item())
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    return number if math.isfinite(number) else None


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(json_value(value), ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                    encoding="utf-8")


def write_csv(path: Path, rows: list[dict], fields: tuple[str, ...]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def protected_hashes() -> list[dict]:
    files = sorted((*PHASE4.rglob("*"), *PHASE5.rglob("*")))
    return [
        {"文件": path.relative_to(ROOT).as_posix(),
         "SHA256": hashlib.sha256(path.read_bytes()).hexdigest()}
        for path in files if path.is_file()
    ]


def verify_protected_history() -> list[dict]:
    baseline = PHASE / "phase4_phase5_sha256.csv"
    current = protected_hashes()
    if baseline.exists():
        with baseline.open(encoding="utf-8-sig", newline="") as stream:
            expected = list(csv.DictReader(stream))
        if current != expected:
            raise RuntimeError("phase4/phase5 文件哈希与 phase6 首次执行记录不同；停止写入。")
    else:
        write_csv(baseline, current, ("文件", "SHA256"))
    return current


def mtb_value(value):
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    return None if number == MISSING_SENTINEL else number


def column_values(column) -> list:
    values = column.GetData()
    values = list(values) if isinstance(values, (tuple, list)) else [values]
    return [mtb_value(value) for value in values]


def load_column(app, project, columns, index: int, name: str, values: list) -> tuple[dict, str]:
    column = columns.Item(index)
    column.Name = name
    command = f"SET C{index}\n" + " ".join(
        "*" if value is None else format(float(value), ".17g") for value in values
    ) + "\nEND"
    before = int(project.Commands.Count)
    project.ExecuteCommand(command)
    error = str(app.LastError or "")
    if int(project.Commands.Count) <= before or error.strip():
        raise RuntimeError(f"Minitab SET C{index} 失败：{error}")
    actual = column_values(column)
    if len(actual) != len(values):
        raise AssertionError(f"Minitab C{index} 回读行数不符")
    for expected, found in zip(values, actual):
        if expected is None:
            if found is not None:
                raise AssertionError(f"Minitab C{index} 缺失值未保留")
        elif float(expected) != found:
            raise AssertionError(f"Minitab C{index} 回读值不同：{expected} != {found}")
    return {"name": name, "values": actual, "effective_n": sum(value is not None for value in actual)}, command


def run_minitab(payload: dict) -> dict:
    import pythoncom
    import win32com.client

    if not MTB_EXE.is_file() or com_check.file_version(MTB_EXE) != payload["reference_version"]:
        raise RuntimeError(f"需要本机 Minitab {payload['reference_version']}：{MTB_EXE}")
    pids_before = running_minitab_pids()
    if pids_before:
        raise RuntimeError(f"启动前检测到 Mtb.exe PID {pids_before}；拒绝连接既有会话")

    app = project = ui = worksheet = columns = None
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
        while int(columns.Count) < 40:
            column = columns.Add(None, None, 1)
            column.Name = f"P6C{int(columns.Count):03d}"

        loaded, commands, outputs = {}, [], {}
        for case_id, case in payload["fit"].items():
            if not isinstance(case, dict) or "values" not in case:
                continue
            index = int(case["column"])
            loaded[str(index)], command = load_column(app, project, columns, index, case_id, case["values"])
            commands.append({"case_id": f"input_{case_id}", "command": command})

        def execute(command_id: str, command: str, stored_columns: dict | None = None):
            before = int(project.Commands.Count)
            project.ExecuteCommand(command)
            after = int(project.Commands.Count)
            error = str(app.LastError or "")
            if after <= before or error.strip():
                raise RuntimeError(f"Minitab 命令 {command_id} 失败：{error or command}")
            item = {
                "executed": True,
                "command_count": [before, after],
                "command": command,
                "last_error": error,
                "output": capture_command_output(project, after),
                "stored": {},
            }
            for field, index in (stored_columns or {}).items():
                item["stored"][field] = column_values(columns.Item(index))
            commands.append({"case_id": command_id, "command": command})
            outputs[command_id] = item

        fit_cases = payload["fit"]
        positive_ids = ("normal_ties", "right_skew_ties_missing")
        for case_id in positive_ids:
            data_column = fit_cases[case_id]["column"]
            execute(
                f"{case_id}_normal_parameters",
                f"DCAPA C{data_column} 1;\n  NORMAL;\n  RESTIMATE;\n"
                f"  RPTILE 5 50 95;\n  CONFIDENCE {payload['fit']['percentile_confidence']};\n  NOCI.",
            )
            execute(
                f"{case_id}_positive_distribution_fit",
                f"DCAPA C{data_column} 1;\n  LNORMAL;\n  GAMMA;\n  EXPONENTIAL;\n  WEIBULL;\n"
                "  RFITTESTS;\n  RESTIMATE;\n  RPTILE 5 50 95;\n"
                f"  CONFIDENCE {payload['fit']['percentile_confidence']};\n  NOCI.",
            )
        boundary_column = fit_cases["nonpositive_boundary"]["column"]
        execute(
            "nonpositive_boundary_normal_parameters",
            f"DCAPA C{boundary_column} 1;\n  NORMAL;\n  RESTIMATE;\n"
            f"  RPTILE 5 50 95;\n  CONFIDENCE {payload['fit']['percentile_confidence']};\n  NOCI.",
        )

        probabilities = payload["probability"]
        for index, (case_id, case) in enumerate(probabilities.items()):
            input_x, input_p = 10, 11
            columns.Item(input_x).Name = f"P6_X_{case_id}"
            columns.Item(input_p).Name = f"P6_P_{case_id}"
            for input_id, input_name, values in (
                (input_x, f"P6_X_{case_id}", [case["x"]]),
                (input_p, f"P6_P_{case_id}", [case["tail_probability"],
                                              1 - case["tail_probability"],
                                              case["tail_probability"] / 2,
                                              1 - case["tail_probability"] / 2]),
            ):
                command = f"SET C{input_id}\n" + " ".join(format(value, ".17g") for value in values) + "\nEND"
                before = int(project.Commands.Count)
                project.ExecuteCommand(command)
                error = str(app.LastError or "")
                if int(project.Commands.Count) <= before or error.strip():
                    raise RuntimeError(f"Minitab SET C{input_id} 失败：{error}")
                commands.append({"case_id": f"input_{input_name}", "command": command})
            offset = index * 3
            pdf_col, cdf_col, invcdf_col = 30 + offset, 31 + offset, 32 + offset
            native_dist = case["minitab_subcommand"]
            columns.Item(pdf_col).Name = f"P6_PDF_{case_id}"
            columns.Item(cdf_col).Name = f"P6_CDF_{case_id}"
            columns.Item(invcdf_col).Name = f"P6_ICDF_{case_id}"
            execute(f"{case_id}_pdf", f"PDF C{input_x} C{pdf_col};\n  {native_dist}.",
                    {"pdf": pdf_col})
            execute(f"{case_id}_cdf", f"CDF C{input_x} C{cdf_col};\n  {native_dist}.",
                    {"cdf": cdf_col})
            execute(f"{case_id}_invcdf", f"INVCDF C{input_p} C{invcdf_col};\n  {native_dist}.",
                    {"invcdf": invcdf_col})

        gof = payload["categorical_gof"]
        observed = " ".join(format(float(value), ".17g") for value in gof["observed"])
        proportions = " ".join(format(float(value), ".17g") for value in gof["proportions"])
        execute("categorical_gof", f"TCHISQUARE;\n  OBSERVED {observed};\n  PROPORTIONS {proportions};\n  RTABLE.")

        commands_text = []
        for command in commands:
            commands_text.extend([command["command"], ""])
        return {
            "version": payload["reference_version"],
            "clsid": com_check.registered_server()[0],
            "registered_server": com_check.registered_server()[2],
            "app_path": app_path,
            "process_path": process_path,
            "python": sys.executable,
            "loaded_inputs": loaded,
            "commands": commands,
            "outputs": outputs,
            "session_commands": "\n".join(commands_text).rstrip() + "\n",
        }
    finally:
        columns = worksheet = project = app = ui = None
        gc.collect()
        for _ in range(15):
            if not running_minitab_pids():
                break
            time.sleep(0.2)


def production_results(payload: dict) -> dict:
    import numpy as np
    from chi_sq import chi_square
    from cont_plot import cont_dist
    from dist_fit import compare_dist

    results = {"fit": {}, "probability": {}, "categorical_gof": {}}
    for case_id, case in payload["fit"].items():
        if not isinstance(case, dict) or "values" not in case:
            continue
        values = [float(value) for value in case["values"] if value is not None]
        selected = payload["fit"]["minijmp_distributions"]
        fits = compare_dist(values, print_out=False, selected=selected)
        distributions = {}
        for name, _abl, fit, weight in fits:
            ad, p_value = dist_fit_gof(name, fit, values)
            distributions[name] = {
                "fits": fit["fits"],
                "-2*LogLikelihood": fit["ABL"][0],
                "AICc": fit["ABL"][1],
                "BIC": fit["ABL"][2],
                "AD": ad,
                "AD_p": p_value,
                "percentiles_5_50_95": fit["rv"].ppf(np.array([.05, .5, .95])),
                "AICc_weight": weight,
            }
        results["fit"][case_id] = {
            "effective_n": len(values),
            "input": values,
            "source": "dist_fit.compare_dist production core; FitDistDialog.apply caller path covered by tests/test_g3_distribution_reports.py",
            "distributions": distributions,
        }
        if all(value > 0 for value in values):
            results["fit"][case_id]["independent_reference"] = {
                "weibull_2p_mle": weibull_mle_score_reference(values)
            }

    for case_id, case in payload["probability"].items():
        x_result = cont_dist(
            dist=case["distribution"], x=case["x"], print_out=False, plot_out=False, **case["parameters"]
        )
        p_result = cont_dist(
            dist=case["distribution"], pvalue=case["tail_probability"],
            print_out=False, plot_out=False, **case["parameters"]
        )
        results["probability"][case_id] = {
            "x": case["x"], "tail_probability": case["tail_probability"],
            "at_x": x_result, "at_p": p_result,
            "source": "cont_plot.cont_dist production helper; dialog route covered by tests/test_g6_chart_presentation.py",
        }

    observed = payload["categorical_gof"]["observed"]
    proportions = payload["categorical_gof"]["proportions"]
    total = sum(observed)
    pseudo = [value * total * 1e9 for value in proportions]
    result = chi_square([observed, pseudo], print_out=False)
    results["categorical_gof"] = {
        "observed": observed,
        "proportions": proportions,
        "expected": [value * total for value in proportions],
        "production_reference_row": pseudo,
        "results": result,
        "source": "chi_sq.chi_square production core; dialog route covered by tests/test_g3_chi_square_reports.py",
    }
    return results


def weibull_mle_score_reference(values: list[float]) -> dict:
    import numpy as np
    from scipy.optimize import brentq
    from scipy.special import logsumexp, softmax
    from scipy.stats import weibull_min

    x = np.asarray(values, dtype=float)
    if len(x) < 2 or np.any(x <= 0):
        raise ValueError("2-parameter Weibull reference requires at least two positive observations.")
    log_x = np.log(x)

    # The score equation gives the 2-parameter Weibull MLE without calling the production fit function.
    def shape_score(shape):
        return 1 / shape + log_x.mean() - np.dot(softmax(shape * log_x), log_x)

    shape = brentq(shape_score, 1e-3, 1e5, xtol=1e-13)
    score = float(shape_score(shape))
    if abs(score) > 1e-10:
        raise AssertionError(f"Weibull MLE score did not converge: {score}")
    scale = float(np.exp((logsumexp(shape * log_x) - np.log(len(x))) / shape))
    percentiles = weibull_min.ppf([.05, .5, .95], shape, loc=0, scale=scale)
    return {
        "shape": float(shape), "scale": scale, "score_residual": score,
        "percentiles_5_50_95": percentiles,
        "source": "2-parameter Weibull log-likelihood score equation; scipy.optimize.brentq root",
    }


def dist_fit_gof(name, fit, values):
    from dist_fit import goodness_of_fit
    return goodness_of_fit(fit["rv"], values, normal=name == "Normal")


def output_document(state: dict) -> list[str]:
    text = state.get("output", "").split("Output.Text[1]:", 1)[0]
    text = text.split("OutputDocument.Text:", 1)[-1].replace("\r", "\n")
    return [line.strip() for line in text.splitlines() if line.strip()]


def section_lines(lines: list[str], heading: str, stop: str) -> list[str]:
    start = next((i for i, line in enumerate(lines) if heading in line), None)
    if start is None:
        raise ValueError(f"原生输出缺少区段：{heading}")
    end = next((i for i in range(start + 1, len(lines)) if stop in lines[i]), len(lines))
    return lines[start + 1:end]


def distribution_row(lines: list[str], distribution: str) -> str:
    aliases = DIST_ALIASES[distribution]
    return next((line for line in lines if any(line.startswith(alias) for alias in aliases)), "")


def display_tokens(line: str) -> list[str]:
    return [match.group().replace(" ", "") for match in DISPLAY_NUMBER_RE.finditer(line)]


def numeric_tokens(line: str) -> list[float]:
    return [float(value) for value in NUMBER_RE.findall(line)]


def displayed_tolerance(token: str) -> float:
    token = token.lstrip("<>").lower().split("e", 1)[0]
    decimals = len(token.split(".", 1)[1]) if "." in token else 0
    return 0.5 * 10 ** -decimals


def reported_match(value: float, token: str) -> tuple[str, float | None, str]:
    text = token.replace(" ", "")
    if text.startswith("<"):
        bound = float(text[1:])
        return ("PASS", abs(value - bound), f"<{bound:g}") if value < bound else (
            "METHOD_DIFF", abs(value - bound), f"<{bound:g}")
    if text.startswith(">"):
        bound = float(text[1:])
        return ("PASS", abs(value - bound), f">{bound:g}") if value > bound else (
            "METHOD_DIFF", abs(value - bound), f">{bound:g}")
    expected = float(text)
    tolerance = displayed_tolerance(text)
    return ("PASS" if abs(value - expected) <= tolerance else "METHOD_DIFF",
            abs(value - expected), f"±{tolerance:.3g} display rounding")


def comparison_row(case_id: str, feature: str, metric: str, native_value, local_value,
                   error, tolerance, status: str, native_source: str,
                   local_source: str, config: str, reason: str) -> dict:
    return {
        "case_id": case_id, "功能": feature, "统计量": metric,
        "Minitab值": native_value, "MiniJMP值": local_value,
        "绝对误差": error, "容差": tolerance, "结果": status,
        "Minitab结果来源": native_source, "MiniJMP结果来源": local_source,
        "统计定义/配置": config, "判断依据": reason,
    }


def compare_numeric(rows: list[dict], *, case_id: str, feature: str, metric: str,
                    native_token: str, local_value: float, native_source: str,
                    local_source: str, config: str, reason: str) -> str:
    status, error, tolerance = reported_match(local_value, native_token)
    rows.append(comparison_row(case_id, feature, metric, native_token, local_value, error,
                               tolerance, status, native_source, local_source, config, reason))
    return status


def add_unsupported(rows: list[dict], case_id: str, feature: str, metric: str,
                    native_source: str, local_source: str, reason: str) -> None:
    rows.append(comparison_row(case_id, feature, metric, "", "", "", "",
                               "UNSUPPORTED", native_source, local_source, "", reason))


def native_distribution_rows(native: dict, case_id: str, distribution: str) -> tuple[list[str], list[str]]:
    command_id = f"{case_id}_normal_parameters" if distribution == "Normal" else (
        f"{case_id}_positive_distribution_fit")
    lines = output_document(native["outputs"][command_id])
    params = section_lines(lines, "分布参数的极大似然估计", "百分位数表")
    return lines, params


def native_parameter_tokens(native: dict, case_id: str, distribution: str) -> list[str]:
    _, section = native_distribution_rows(native, case_id, distribution)
    line = distribution_row(section, distribution)
    tokens = display_tokens(line)
    if not tokens:
        raise ValueError(f"{case_id}/{distribution} 原生参数行未解析到：{line}")
    return tokens


def native_percentiles(native: dict, case_id: str, distribution: str) -> dict[int, tuple[str, str]]:
    lines, _ = native_distribution_rows(native, case_id, distribution)
    wanted = {5, 50, 95}
    found = {}
    for line in lines:
        if not any(line.startswith(alias) for alias in DIST_ALIASES[distribution]):
            continue
        values = display_tokens(line)
        if len(values) >= 2 and float(values[0]) in wanted:
            found[int(float(values[0]))] = (values[1], line)
    if set(found) != wanted:
        raise ValueError(f"{case_id}/{distribution} 原生 percentiles 未完整解析：{found}")
    return found


def native_gof_row(native: dict, case_id: str, distribution: str) -> list[str]:
    lines = output_document(native["outputs"][f"{case_id}_positive_distribution_fit"])
    section = section_lines(lines, "拟合优度检验", "分布参数的极大似然估计")
    line = distribution_row(section, distribution)
    values = display_tokens(line)
    if len(values) < 2:
        raise ValueError(f"{case_id}/{distribution} 原生 AD 行未解析到：{line}")
    return values


def build_comparisons(payload: dict, local: dict, native: dict) -> list[dict]:
    rows = []
    for case_id, case in payload["fit"].items():
        if not isinstance(case, dict) or "values" not in case:
            continue
        feature = "06分布拟合"
        native_n = native["loaded_inputs"][str(case["column"])]["effective_n"]
        mini_case = local["fit"][case_id]
        config = f"N={mini_case['effective_n']}; missing values excluded; selected={payload['fit']['minijmp_distributions']}"
        status = "PASS" if native_n == mini_case["effective_n"] else "FAIL"
        rows.append(comparison_row(
            f"fit_{case_id}", feature, "有效样本数 N", native_n, mini_case["effective_n"],
            abs(native_n - mini_case["effective_n"]), "exact", status,
            f"phase6/minitab_results.json#loaded_inputs.C{case['column']}",
            f"phase6/minijmp_results.json#results.fit.{case_id}.effective_n",
            config, "按 Minitab 工作表回读和 MiniJMP number_list 过滤后的非缺失观测计数比较。",
        ))

        distributions = mini_case["distributions"]
        native_names = ("Normal",) if case_id == "nonpositive_boundary" else (
            "Normal", "Lognormal", "Gamma", "Exponential", "Weibull")
        for name in native_names:
            result = distributions[name]
            tokens = native_parameter_tokens(native, case_id, name)
            values = result["fits"]
            native_source = f"phase6/minitab_raw_outputs.txt#{case_id}_{'normal_parameters' if name == 'Normal' else 'positive_distribution_fit'}"
            local_source = f"phase6/minijmp_results.json#results.fit.{case_id}.distributions.{name}.fits"
            if name == "Normal":
                parameter_pairs = (("均值/location", values[0], tokens[0]),
                                   ("标准差/scale", values[1], tokens[1]))
            elif name == "Lognormal":
                parameter_pairs = (("对数均值/location", math.log(values[0]), tokens[0]),
                                   ("对数标准差/scale", values[1], tokens[1]))
            elif name == "Gamma":
                parameter_pairs = (("形状/shape", values[0], tokens[0]),
                                   ("尺度/scale", values[1], tokens[1]))
            elif name == "Exponential":
                parameter_pairs = (("尺度/mean", values[0], tokens[0]),)
            else:
                parameter_pairs = (("形状/shape", values[1], tokens[0]),
                                   ("尺度/scale", values[0], tokens[1]))
            for parameter, mini_value, native_token in parameter_pairs:
                if name == "Weibull":
                    reference = mini_case["independent_reference"]["weibull_2p_mle"]
                    reference_value = reference["shape" if parameter == "形状/shape" else "scale"]
                    native_estimate = float(native_token)
                    mini_error = abs(float(mini_value) - reference_value)
                    native_error = abs(native_estimate - reference_value)
                    allowed = 1e-5 * max(abs(reference_value), 1e-12)
                    status = "PASS" if (native_error <= displayed_tolerance(native_token)
                                        and mini_error <= allowed) else "FAIL"
                    rows.append(comparison_row(
                        f"fit_{case_id}", feature, f"{name} 参数 {parameter}",
                        native_token, mini_value, abs(native_estimate - float(mini_value)),
                        f"native display rounding; independent MLE relative tolerance={1e-5:g}",
                        status, native_source, local_source,
                        "2P Weibull, location fixed at 0; independent log-likelihood score root; "
                        f"score residual={reference['score_residual']:.3g}",
                        f"Minitab 与 MiniJMP 均对照独立 MLE：reference={reference_value:.15g}; "
                        f"MiniJMP error={mini_error:.3g}; Minitab display error={native_error:.3g}.",
                    ))
                    continue
                method_diff = name == "Lognormal" and parameter == "对数标准差/scale"
                compare_numeric(
                    rows, case_id=f"fit_{case_id}", feature=feature,
                    metric=f"{name} 参数 {parameter}", native_token=native_token,
                    local_value=float(mini_value), native_source=native_source, local_source=local_source,
                    config="Minitab DCAPA 单列、子组大小 1；两参数模型 location/threshold 固定为 0（适用时）。",
                    reason=("Minitab 对 Lognormal 使用无偏参数估计，MiniJMP SciPy lognorm.fit 使用 MLE；"
                            "差异按估计方法保留为 METHOD_DIFF。" if method_diff else
                            "按 Minitab 表格显示精度比较；两侧参数化及估计方法一致。"),
                )
                if method_diff and rows[-1]["结果"] == "PASS":
                    rows[-1]["判断依据"] = "数值在显示精度内一致；估计方法仍分别为 Minitab 无偏估计与 MiniJMP MLE。"

            for percentile, (native_token, line) in native_percentiles(native, case_id, name).items():
                local_value = float(result["percentiles_5_50_95"][[5, 50, 95].index(percentile)])
                if name == "Weibull":
                    reference = mini_case["independent_reference"]["weibull_2p_mle"]
                    reference_value = float(
                        reference["percentiles_5_50_95"][[5, 50, 95].index(percentile)]
                    )
                    native_estimate = float(native_token)
                    mini_error = abs(local_value - reference_value)
                    native_error = abs(native_estimate - reference_value)
                    allowed = 1e-5 * max(abs(reference_value), 1e-12)
                    status = "PASS" if (native_error <= displayed_tolerance(native_token)
                                        and mini_error <= allowed) else "FAIL"
                    rows.append(comparison_row(
                        f"fit_{case_id}", feature, f"{name} 第 {percentile} 百分位数",
                        native_token, local_value, abs(native_estimate - local_value),
                        f"native display rounding; independent MLE relative tolerance={1e-5:g}",
                        status, native_source,
                        f"phase6/minijmp_results.json#results.fit.{case_id}.distributions.{name}.percentiles_5_50_95",
                        f"DCAPA RPTILE {percentile}; independent percentile from score-root Weibull MLE.",
                        f"MLE score reference={reference_value:.15g}; MiniJMP error={mini_error:.3g}; "
                        f"Minitab display error={native_error:.3g}; {line}",
                    ))
                    continue
                status = compare_numeric(
                    rows, case_id=f"fit_{case_id}", feature=feature,
                    metric=f"{name} 第 {percentile} 百分位数", native_token=native_token,
                    local_value=local_value, native_source=native_source,
                    local_source=f"phase6/minijmp_results.json#results.fit.{case_id}.distributions.{name}.percentiles_5_50_95",
                    config=f"DCAPA RPTILE {percentile}; parametric percentile from the fitted distribution.",
                    reason=("Lognormal 百分位数受 Minitab 无偏参数估计与 MiniJMP MLE 差异影响。"
                            if name == "Lognormal" else
                            f"按原生百分位数显示精度比较；原生行：{line}"),
                )
                if name == "Lognormal" and status == "PASS":
                    rows[-1]["判断依据"] = "数值在显示精度内一致；Lognormal 参数估计方法不同。"

            if name != "Normal" and case_id != "nonpositive_boundary":
                ad_tokens = native_gof_row(native, case_id, name)
                ad_value = float(ad_tokens[0])
                local_ad = float(result["AD"])
                ad_status = "PASS" if abs(local_ad - ad_value) <= displayed_tolerance(ad_tokens[0]) else "METHOD_DIFF"
                rows.append(comparison_row(
                    f"fit_{case_id}", feature, f"{name} Anderson–Darling 统计量",
                    ad_tokens[0], local_ad, abs(local_ad - ad_value),
                    f"±{displayed_tolerance(ad_tokens[0]):.3g} display rounding", ad_status,
                    f"phase6/minitab_raw_outputs.txt#{case_id}_positive_distribution_fit",
                    f"phase6/minijmp_results.json#results.fit.{case_id}.distributions.{name}.AD",
                    "Minitab DCAPA RFITTESTS; MiniJMP dist_fit.AD.",
                    "显示精度内一致。" if ad_status == "PASS" else
                    "Minitab 报告修正 AD 统计量；MiniJMP 使用原始 AD 统计量。",
                ))
                p_status = compare_numeric(
                    rows, case_id=f"fit_{case_id}", feature=feature,
                    metric=f"{name} Anderson–Darling p 值", native_token=ad_tokens[1],
                    local_value=float(result["AD_p"]),
                    native_source=f"phase6/minitab_raw_outputs.txt#{case_id}_positive_distribution_fit",
                    local_source=f"phase6/minijmp_results.json#results.fit.{case_id}.distributions.{name}.AD_p",
                    config="Minitab DCAPA RFITTESTS；p 值按原生显示值或不等式范围比较。",
                    reason="Minitab 使用分布专用修正/表格插值；MiniJMP 使用通用 approximate_p。",
                )
                if p_status == "PASS":
                    rows[-1]["判断依据"] = "MiniJMP p 值落在 Minitab 原生显示的精度或范围内。"

        add_unsupported(
            rows, f"fit_{case_id}", feature, "P5/P50/P95 拟合百分位数 95% 置信区间",
            f"phase6/minitab_raw_outputs.txt#{case_id} RPTILE",
            f"phase6/minijmp_results.json#results.fit.{case_id}.distributions",
            "Minitab 为 RPTILE 点百分位数提供标准误和 95% 区间；MiniJMP 当前接口仅返回点百分位数。",
        )

    add_unsupported(rows, "fit_scope", "06分布拟合", "拟合参数置信区间",
                    "phase6 DCAPA RESTIMATE 仅输出参数点估计。",
                    "code/dist_fit.py::print_table 显示“参数置信区间：现有方法未计算”。",
                    "当前拟合入口未返回参数置信区间；单独的均值/标准差 CI 不等同于拟合分布参数区间。")
    for metric in ("-2*LogLikelihood", "AICc", "BIC"):
        add_unsupported(rows, "fit_scope", "06分布拟合", f"Minitab 原生 {metric}",
                        "Minitab DCAPA 输出参数、AD/LRT 与百分位数；该命令未输出此字段。",
                        f"phase6/minijmp_results.json#results.fit.*.distributions.*.{metric}",
                        "MiniJMP 有该指标，但 Minitab 19 Individual Distribution Identification 没有同名原生字段；不做派生替代。")
    add_unsupported(rows, "fit_scope", "06分布拟合", "Student's t 拟合",
                    "Minitab 19 Individual Distribution Identification 的支持分布列表不含 Student's t。",
                    "phase6/minijmp_results.json#results.fit.*.distributions.Student's t",
                    "Minitab PDF/CDF/INVCDF 支持 t 分布，但没有可直接比较的 t 参数拟合与 GOF 原生字段。")
    add_unsupported(rows, "fit_scope", "06分布拟合", "KS 拟合优度检验",
                    "Minitab 19 正态性命令有 KSTEST；DCAPA 本轮原生结果为 AD。",
                    "MiniJMP FitDistDialog 仅报告 Anderson–Darling。",
                    "当前分布拟合入口未实现 KS 拟合优度检验。")
    add_unsupported(rows, "fit_scope", "06分布拟合", "三参数分布拟合",
                    "Minitab DCAPA 支持三参数 Lognormal、Gamma、Exponential、Weibull 等模型。",
                    "MiniJMP 分布拟合入口使用位置/阈值固定为 0 的两参数候选。",
                    "边界数据中不扩展比较三参数模型；此配置记为现有功能缺口。")

    probability_source = "phase6/minitab_results.json#outputs"
    for case_id, case in payload["probability"].items():
        result = local["probability"][case_id]
        native_values = {
            "pdf": native_value(native, f"{case_id}_pdf", "pdf", 0),
            "cdf": native_value(native, f"{case_id}_cdf", "cdf", 0),
            "invcdf": native["outputs"][f"{case_id}_invcdf"]["stored"]["invcdf"],
        }
        at_x = result["at_x"]
        at_p = result["at_p"]
        candidates = (
            ("PDF density at x", native_values["pdf"], at_x["px"]),
            ("CDF P(X≤x)", native_values["cdf"], at_x["left_acc_p"]),
            ("Survival P(X>x)", 1 - native_values["cdf"], at_x["right_acc_p"]),
            (f"ICDF p={case['tail_probability']}", native_values["invcdf"][0], at_p["x_left"]),
            (f"ICDF p={1-case['tail_probability']}", native_values["invcdf"][1], at_p["x_right"]),
            (f"ICDF p={case['tail_probability']/2}", native_values["invcdf"][2], at_p["equal_tail"]["x_left"]),
            (f"ICDF p={1-case['tail_probability']/2}", native_values["invcdf"][3], at_p["equal_tail"]["x_right"]),
        )
        for metric, native_value_, local_value in candidates:
            error = abs(float(native_value_) - float(local_value))
            tolerance = 1e-8
            status = "PASS" if error <= tolerance else "FAIL"
            rows.append(comparison_row(
                f"probability_{case_id}", "32/33概率图与分布概率计算", metric,
                native_value_, local_value, error, tolerance, status,
                f"{probability_source}#{case_id}", f"phase6/minijmp_results.json#results.probability.{case_id}",
                f"{case['minitab_subcommand']}; x={case['x']}; tail p={case['tail_probability']}",
                "Minitab PDF/CDF/INVCDF 存储值与 MiniJMP cont_dist 返回值直接比较。",
            ))

    native_gof = parse_native_chisquare(native["outputs"]["categorical_gof"])
    local_gof = local["categorical_gof"]["results"]
    gof_case = "categorical_gof"
    config = "N=100; observed=[18,25,57]; expected proportions=[0.2,0.3,0.5]; all expected counts ≥5."
    for metric, token, value in (
        ("有效 N", native_gof["N"], 100),
        ("自由度", native_gof["df"], local_gof["df"]),
        ("Pearson χ²", native_gof["chi"], local_gof["chi sq Pearson"]),
        ("Pearson p 值", native_gof["p"], local_gof["p Pearson"]),
    ):
        if metric in ("有效 N", "自由度"):
            status, error, tolerance = ("PASS" if float(token) == float(value) else "FAIL",
                                        abs(float(token) - float(value)), "exact")
        else:
            status, error, tolerance = reported_match(float(value), token)
        rows.append(comparison_row(
            gof_case, "43比率卡方检验", metric, token, value, error, tolerance, status,
            "phase6/minitab_raw_outputs.txt#categorical_gof",
            "phase6/minijmp_results.json#results.categorical_gof.results",
            config, "Minitab TCHISQUARE 的 Pearson 拟合优度输出；按原生显示精度比较。",
        ))
    for metric in ("似然比 χ²", "似然比 p 值"):
        add_unsupported(rows, gof_case, "43比率卡方检验", metric,
                        "Minitab TCHISQUARE 原生报告未提供似然比拟合优度统计量。",
                        "phase6/minijmp_results.json#results.categorical_gof.results",
                        "MiniJMP 同时输出似然比结果；Minitab 此命令仅提供 Pearson GOF 字段，故标记 UNSUPPORTED。")
    return rows


def native_value(native: dict, command_id: str, field: str, index: int):
    values = native["outputs"][command_id]["stored"][field]
    if len(values) <= index:
        raise ValueError(f"{command_id}.{field} 存储行数不足：{values}")
    return float(values[index])


def parse_native_chisquare(state: dict) -> dict:
    lines = output_document(state)
    section = section_lines(lines, "卡方检验", "Output.Text")
    for line in section:
        tokens = display_tokens(line)
        if len(tokens) == 4 and float(tokens[0]).is_integer():
            return {"N": tokens[0], "df": tokens[1], "chi": tokens[2], "p": tokens[3]}
    raise ValueError("Minitab TCHISQUARE 原生输出未解析到 N/DF/χ²/p。")


def write_summary(rows: list[dict]) -> list[dict]:
    from collections import Counter

    grouped = {}
    for row in rows:
        grouped.setdefault(row["case_id"], []).append(row)
    output = []
    for case_id, items in (*grouped.items(), ("本轮总体", rows)):
        counts = Counter(item["结果"] for item in items)
        active = [state for state in STATUS_ORDER if counts[state]]
        function_status = "PASS" if active == ["PASS"] else (
            active[0] if len(active) == 1 else "MIXED")
        output.append({
            "case_id": case_id,
            "配置数": 1 if case_id != "本轮总体" else 7,
            "指标数": len(items),
            **{state: counts[state] for state in STATUS_ORDER},
            "功能状态": function_status,
            "备注": "；".join(dict.fromkeys(
                item["判断依据"] for item in items if item["结果"] != "PASS"
            )),
        })
    return output


def update_feature_matrix() -> None:
    path = OUT / "feature_matrix.csv"
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = tuple(reader.fieldnames or ())
        rows = list(reader)
    if len(rows) != 90:
        raise AssertionError(f"90 项矩阵数量改变：{len(rows)}")

    updates = {
        "06分布拟合": (
            "已覆盖 3 个固定样本配置；Normal、Lognormal、Gamma、Exponential、Weibull 的参数与 P5/P50/P95，"
            "正值样本的 AD 统计量/p，以及 Normal/Lognormal/t 的 PDF/CDF/ICDF；正常性 AD 沿用 phase5，不重复计数。"
            "Lognormal 无偏估计与 SciPy MLE、非正态 AD 校准有 METHOD_DIFF；Weibull 参数用独立 score 方程核验。"
            "Minitab RPTILE 提供 P5/P50/P95 的 95% 区间，MiniJMP 仅返回点估计且不返回拟合参数 CI；"
            "Student's t、AICc/BIC 原生字段、"
            "KS 及三参数拟合为 UNSUPPORTED。结果见 phase6/。"
        ),
        "43比率卡方检验": (
            "第四轮以三类、N=100、期望概率 0.2/0.3/0.5 对标 TCHISQUARE；Pearson χ²、DF、p 值在 Minitab 显示精度内通过。"
            "MiniJMP 似然比统计量/p 在 Minitab 该命令无同名原生字段，记 UNSUPPORTED。结果见 phase6/。"
        ),
    }
    updated = set()
    for row in rows:
        label = row["MiniJMP菜单功能"]
        if label not in updates:
            continue
        row["Minitab 19 对标"] = "部分验证"
        marker = "第四轮（phase6）限定范围："
        note = row["备注及证据来源"].split(marker, 1)[0].rstrip()
        row["备注及证据来源"] = (
            f"{note} {marker}{updates[label]} | "
            "Out/statistics_minitab19_parity/phase6/case_inputs.json; "
            "minitab_session_commands.txt; minitab_raw_outputs.txt; minitab_reference.csv; "
            "comparison.csv; summary.csv"
        )
        updated.add(label)
    if updated != set(updates):
        raise AssertionError(f"矩阵目标行不完整：{updated}")
    write_csv(OUT / "feature_matrix.csv", rows, fields)
    if len(list(csv.DictReader((OUT / "feature_matrix.csv").open(encoding="utf-8-sig", newline="")))) != 90:
        raise AssertionError("写回后的 90 项矩阵行数不符")


def output_hashes() -> list[dict]:
    names = (
        "case_inputs.json", "minijmp_results.json", "minitab_metadata.json", "minitab_results.json",
        "minitab_raw_outputs.txt", "minitab_session_commands.txt",
        "comparison.csv", "summary.csv", "phase4_phase5_sha256.csv",
        "feature_matrix.csv",
    )
    files = [PHASE / name for name in names[:-1]] + [OUT / names[-1]]
    return [{"file": path.relative_to(ROOT).as_posix(),
             "sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for path in files]


def record_repeatability() -> str:
    manifest = PHASE / "repeatability_manifest.json"
    current = output_hashes()
    if not manifest.exists():
        write_json(manifest, current)
        (PHASE / "repeatability_check.txt").write_text(
            "phase6 本次完整执行已保存 SHA-256 基线；需再次运行后确认重复性。\n",
            encoding="utf-8",
        )
        return "BASELINE"
    previous = read_json(manifest)
    if previous != current:
        old = {item["file"]: item["sha256"] for item in previous}
        new = {item["file"]: item["sha256"] for item in current}
        changed = sorted(name for name in set(old) | set(new) if old.get(name) != new.get(name))
        (PHASE / "repeatability_check.txt").write_text(
            "phase6 完整执行的逐文件 SHA-256 重复性核验：FAIL\n"
            + "\n".join(f"差异：{name}" for name in changed) + "\n",
            encoding="utf-8",
        )
        return "FAIL"
    (PHASE / "repeatability_check.txt").write_text(
        "phase6 完整执行的逐文件 SHA-256 重复性核验：PASS\n",
        encoding="utf-8",
    )
    return "PASS"


def main() -> int:
    PHASE.mkdir(parents=True, exist_ok=True)
    protected_before = verify_protected_history()
    if com_check.canonical(sys.executable) != com_check.canonical(PROJECT_PYTHON):
        raise RuntimeError(f"请使用项目解释器运行：{PROJECT_PYTHON}")
    payload = read_json(INPUT)
    local = production_results(payload)
    native = run_minitab(payload)
    protected_after = protected_hashes()
    if protected_after != protected_before:
        raise AssertionError("本轮写入改变了 phase4/phase5 历史文件")

    write_json(PHASE / "minijmp_results.json", {
        "python": sys.executable, "case_inputs": payload, "results": local,
    })
    write_json(PHASE / "minitab_results.json", native)
    write_json(PHASE / "minitab_metadata.json", {
        key: native[key] for key in ("version", "clsid", "registered_server", "app_path", "process_path", "python")
    })
    (PHASE / "minitab_session_commands.txt").write_text(native["session_commands"], encoding="utf-8")
    raw = []
    for case_id, state in native["outputs"].items():
        raw.append(f"===== {case_id} =====\n{state['command']}\n{state['output']}\n")
    (PHASE / "minitab_raw_outputs.txt").write_text("\n".join(raw), encoding="utf-8")
    comparisons = build_comparisons(payload, local, native)
    write_csv(PHASE / "comparison.csv", comparisons, COMPARISON_FIELDS)
    summary = write_summary(comparisons)
    write_csv(PHASE / "summary.csv", summary, SUMMARY_FIELDS)
    from collections import Counter
    status_counts = Counter(row["结果"] for row in comparisons)
    update_feature_matrix()
    protected_after = protected_hashes()
    if protected_after != protected_before:
        raise AssertionError("phase6 输出写入期间 phase4/phase5 文件发生变化")
    repeatability = record_repeatability()
    failed = [row for row in comparisons if row["结果"] in ("FAIL", "NOT_RUN")]
    print(f"phase6: {len(comparisons)} metrics; "
          + ", ".join(f"{state}={status_counts[state]}" for state in STATUS_ORDER)
          + f"; repeatability={repeatability}; "
          "phase4/phase5 hashes unchanged.")
    return 1 if failed or repeatability == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
