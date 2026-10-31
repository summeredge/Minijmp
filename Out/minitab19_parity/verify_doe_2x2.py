from __future__ import annotations

import csv
import ctypes
import json
import math
import os
import subprocess
import sys
import time
import traceback
from collections import Counter, defaultdict
from pathlib import Path


OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
INPUT = OUT / "doe_2x2_replicated_input.csv"
MTB_EXE = Path(r"D:\Program\Minitab 19\Mtb.exe")
PROJECT_PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
LOG = OUT / "doe_2x2_run.log"
COMMANDS_FILE = OUT / "doe_2x2_session_commands.txt"
TOL_ABS = 1e-9
TOL_REL = 1e-9

DESIGN_COMMAND = "FFDESIGN 2 4;\n  REPS 2;\n  LEVELS -1 1 -1 1;\n  DESIGN."
ANALYSIS_COMMAND = (
    "FFACTORIAL;\n"
    "  RESPONSE C7;\n"
    "  FACTOR C5 C6;\n"
    "  TERMS C5 C6 C5*C6;\n"
    "  LEVELS -1 1 -1 1;\n"
    "  INUNIT 0;\n"
    "  FITS C8;\n"
    "  RESIDUALS C9;\n"
    "  COEFFICIENTS C10;\n"
    "  XMATRIX M1;\n"
    "  TEXPAND."
)
TERM_NAMES = ("Intercept", "A", "B", "A*B")
EXPECTED_COEFFICIENTS = {"Intercept": 50.0, "A": 3.0, "B": -2.0, "A*B": 4.0}


def log(message: str) -> None:
    print(message, flush=True)
    with LOG.open("a", encoding="utf-8") as stream:
        stream.write(message + "\n")


def canonical(path: str | Path) -> str:
    return os.path.normcase(os.path.realpath(os.path.abspath(path)))


def read_input() -> list[dict]:
    with INPUT.open(newline="", encoding="utf-8-sig") as stream:
        rows = [
            {"run_id": int(row["run_id"]), "replicate": int(row["replicate"]),
             "A": int(row["A"]), "B": int(row["B"]), "Y": float(row["Y"])}
            for row in csv.DictReader(stream)
        ]
    if len(rows) != 8 or [row["run_id"] for row in rows] != list(range(1, 9)):
        raise ValueError("输入必须是固定的 8 行 2² 两次重复数据")
    if any(row[factor] not in (-1, 1) for row in rows for factor in ("A", "B")):
        raise ValueError("因子必须使用 -1/+1 编码")
    cells = Counter((row["replicate"], row["A"], row["B"]) for row in rows)
    if cells != Counter({(rep, a, b): 1 for rep in (1, 2) for a in (-1, 1) for b in (-1, 1)}):
        raise ValueError("每次重复必须恰好包含四个因子组合")
    return rows


def run_minitab(run_number: int, rows: list[dict]) -> dict:
    if not MTB_EXE.is_file():
        raise FileNotFoundError(MTB_EXE)
    if running_minitab_pids():
        raise RuntimeError("检测到已有 Mtb.exe；为保护用户项目，本次不连接现有会话")

    result_path = OUT / f"doe_2x2_minitab_run{run_number}.json"
    process = subprocess.run(
        [str(COM_PYTHON), "-X", "utf8", str(Path(__file__).resolve()),
         "--com-worker", str(run_number)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
    )
    if process.stdout.strip():
        log(process.stdout.rstrip())
    if process.stderr.strip():
        log("COM worker stderr:\n" + process.stderr.rstrip())
    if process.returncode:
        raise RuntimeError(f"Minitab COM worker run {run_number} 失败，退出码 {process.returncode}")
    for _ in range(30):
        if not running_minitab_pids():
            break
        time.sleep(0.5)
    pids = running_minitab_pids()
    if pids:
        raise RuntimeError(f"Minitab COM worker 结束后仍有 Mtb.exe 进程: {pids}")
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if result["version"] != "19.1.0.1":
        raise RuntimeError(f"COM worker 连接的版本不是 19.1.0.1: {result['version']}")
    if canonical(result["app_path"]) != canonical(MTB_EXE) or canonical(result["process_path"]) != canonical(MTB_EXE):
        raise RuntimeError("COM worker 的 AppPath 或进程映像与指定 Mtb.exe 不一致")
    actual_by_id = {
        row["run_id"]: {key: row[key] for key in ("run_id", "replicate", "A", "B", "Y")}
        for row in result["data_rows"]
    }
    expected_by_id = {row["run_id"]: row for row in rows}
    if actual_by_id != expected_by_id:
        raise RuntimeError("Minitab 设计中的响应与固定 CSV 输入未能逐运行对齐")
    return result


def run_minijmp(rows: list[dict]) -> dict:
    if canonical(sys.executable) != canonical(PROJECT_PYTHON):
        raise RuntimeError(f"请使用项目解释器运行: {PROJECT_PYTHON}")
    sys.path.insert(0, str(ROOT / "code"))
    import numpy as np
    from doe_analysis import analyze_factorial
    from doe_core import DesignSpec, FactorSpec
    from doe_factorial import create_factorial

    spec = DesignSpec(
        "minitab19-2x2-parity", (FactorSpec("A", "A", -1, 1),
                                  FactorSpec("B", "B", -1, 1)),
        ("Y",), seed=10, design_type="two_level_full",
    )
    frame, metadata = create_factorial(spec, replicates=2)
    data_by_run = {(row["replicate"], row["A"], row["B"]): row["Y"] for row in rows}
    response = []
    for replicate, a, b in zip(frame["重复"], frame["设定_A"], frame["设定_B"]):
        response.append(data_by_run[(int(replicate), int(a), int(b))])
    frame["响应_Y"] = response
    result = analyze_factorial(frame, metadata, "Y", order=2, ss_type="I")

    coded = np.asarray(result["coded"], dtype=float)
    matrix = np.column_stack((np.ones(len(coded)), coded[:, 0], coded[:, 1], coded[:, 0] * coded[:, 1]))
    rows_by_id = {}
    for index, run in enumerate(result["observed_runs"]):
        key = (int(run.replicate), int(coded[index, 0]), int(coded[index, 1]))
        input_row = data_by_run[key]
        matching = next(row for row in rows if (row["replicate"], row["A"], row["B"]) == key)
        rows_by_id[matching["run_id"]] = {
            "run_id": matching["run_id"], "replicate": key[0], "A": key[1], "B": key[2],
            "Y": float(input_row), "fit": float(result["fitted"][index]),
            "residual": float(result["residuals"][index]),
            "matrix": matrix[index].tolist(),
        }
    if sorted(rows_by_id) != list(range(1, 9)):
        raise AssertionError("MiniJMP 运行没有与固定输入一一对应")
    anova = {row["term"]: {key: (float(value) if value is not None else None)
                           for key, value in row.items() if key != "term"}
             for row in result["anova"]}
    rank = int(np.linalg.matrix_rank(matrix))
    if rank != result["rank"]:
        raise AssertionError(f"独立矩阵秩 {rank} 与 MiniJMP 返回秩 {result['rank']} 不同")
    if not np.allclose(matrix.T @ matrix, np.diag([8.0] * 4), atol=1e-12, rtol=0):
        raise AssertionError("本例的完整平衡 2² 模型列应正交")

    return {
        "coefficients": {
            ("Intercept" if name == "截距" else name): float(value)
            for name, value in zip(result["names"], result["coefficients"])
        },
        "model_matrix": [rows_by_id[i]["matrix"] for i in range(1, 9)],
        "rank": rank, "rows": [rows_by_id[i] for i in range(1, 9)],
        "anova": anova, "n": int(result["n"]), "p": int(result["p"]),
        "residual_df": int(result["df"]), "sse": float(result["sse"]),
        "sst": float(result["sst"]), "ssr": float(result["ssr"]),
        "r2": float(result["r2"]), "adjusted_r2": float(result["adjusted_r2"]),
        "mse": float(result["inference"]["mse"]), "model_f": float(result["inference"]["f"]),
        "model_p": float(result["inference"]["model_p"]),
        "ss_type": result["ss_type"], "model_terms": ["A", "B", "A*B"],
    }


def native_minitab_stats(minitab: dict) -> dict:
    import numpy as np
    from scipy import stats

    matrix = np.asarray(minitab["model_matrix"], dtype=float)
    coefficients = np.asarray([minitab["coefficients"][name] for name in TERM_NAMES], dtype=float)
    observations = np.asarray([row["Y"] for row in minitab["data_rows"]], dtype=float)
    fits = np.asarray([row["fit"] for row in minitab["rows"]], dtype=float)
    residuals = np.asarray([row["residual"] for row in minitab["rows"]], dtype=float)
    if matrix.shape != (8, 4) or coefficients.shape != (4,) or minitab["rank"] != 4:
        raise AssertionError("Minitab native FFACTORIAL did not return an 8x4 full-rank model")
    if not np.allclose(matrix @ coefficients, fits, atol=1e-10, rtol=1e-10):
        raise AssertionError("Minitab stored fits do not equal XMATRIX × stored coefficients")
    if not np.allclose(observations - fits, residuals, atol=1e-10, rtol=1e-10):
        raise AssertionError("Minitab stored residuals do not equal response − fit")
    if not np.allclose(matrix[:, 0], 1.0, atol=0, rtol=0):
        raise AssertionError("Minitab XMATRIX first column is not the intercept")

    residual_df = len(observations) - minitab["rank"]
    sse = float(residuals @ residuals)
    sst = float(np.sum((observations - observations.mean()) ** 2))
    term_rows = {}
    for index, name in enumerate(TERM_NAMES[1:], start=1):
        ss = float(coefficients[index] ** 2 * (matrix[:, index] @ matrix[:, index]))
        f_value = ss / (sse / residual_df)
        term_rows[name] = {"df": 1.0, "ss": ss, "ms": ss, "f": f_value,
                           "p": float(stats.f.sf(f_value, 1, residual_df))}
    model_ss = sum(row["ss"] for row in term_rows.values())
    model_df = minitab["rank"] - 1
    model_ms = model_ss / model_df
    model_f = model_ms / (sse / residual_df)
    term_rows["Model"] = {"df": float(model_df), "ss": model_ss, "ms": model_ms,
                          "f": model_f, "p": float(stats.f.sf(model_f, model_df, residual_df))}
    term_rows["残差"] = {"df": float(residual_df), "ss": sse, "ms": sse / residual_df,
                       "f": None, "p": None}
    term_rows["总计"] = {"df": float(len(observations) - 1), "ss": sst,
                       "ms": None, "f": None, "p": None}
    return {
        "anova": term_rows, "r2": 1.0 - sse / sst,
        "adjusted_r2": 1.0 - (sse / residual_df) / (sst / (len(observations) - 1)),
        "sse": sse, "sst": sst, "ssr": model_ss,
        "mse": sse / residual_df, "s": math.sqrt(sse / residual_df),
    }


def compare_values(run: int, section: str, term: str, statistic: str,
                   minitab_value, minijmp_value, source: str) -> dict:
    if minitab_value is None or minijmp_value is None:
        return {"run": run, "section": section, "term": term, "statistic": statistic,
                "minitab_value": minitab_value, "minijmp_value": minijmp_value,
                "absolute_error": None, "relative_error": None,
                "absolute_tolerance": TOL_ABS, "relative_tolerance": TOL_REL,
                "minitab_value_source": source, "status": "N/A"}
    a, b = float(minitab_value), float(minijmp_value)
    error = abs(a - b)
    relative = error / abs(a) if a else (0.0 if error == 0 else None)
    passed = math.isclose(a, b, rel_tol=TOL_REL, abs_tol=TOL_ABS)
    return {"run": run, "section": section, "term": term, "statistic": statistic,
            "minitab_value": a, "minijmp_value": b, "absolute_error": error,
            "relative_error": relative, "absolute_tolerance": TOL_ABS,
            "relative_tolerance": TOL_REL, "minitab_value_source": source,
            "status": "PASS" if passed else "FAIL"}


def compare_run(run_number: int, minitab: dict, minijmp: dict) -> tuple[list[dict], dict]:
    import numpy as np

    rows = []
    source_matrix = "Minitab FFACTORIAL storage XMATRIX M1 (full precision)"
    source_coef = "Minitab FFACTORIAL storage COEFFICIENTS C10 (full precision)"
    source_fit = "Minitab FFACTORIAL FITS C8 / RESIDUALS C9 (full precision)"
    source_anova = "derived from exact Minitab M1, C10, C8/C9 and fixed Y; P via scipy.stats.f.sf; native rounded table retained"

    for run_id in range(1, 9):
        mtb_row = next(row for row in minitab["rows"] if row["run_id"] == run_id)
        jmp_row = next(row for row in minijmp["rows"] if row["run_id"] == run_id)
        for col, term in enumerate(TERM_NAMES):
            rows.append(compare_values(run_number, "model_matrix", f"run_id={run_id}:{term}",
                                       "X", mtb_row["matrix"][col], jmp_row["matrix"][col], source_matrix))
        for field in ("Y",):
            rows.append(compare_values(run_number, "input", f"run_id={run_id}", field,
                                       mtb_row[field], jmp_row[field], "fixed CSV input"))
        for field in ("fit", "residual"):
            rows.append(compare_values(run_number, "run_statistics", f"run_id={run_id}", field,
                                       mtb_row[field], jmp_row[field], source_fit))

    rows.append(compare_values(run_number, "model", "model", "rank", minitab["rank"], minijmp["rank"],
                               "rank of Minitab XMATRIX M1 / MiniJMP result rank"))
    for term in TERM_NAMES:
        rows.append(compare_values(run_number, "coefficient", term, "estimate",
                                   minitab["coefficients"][term], minijmp["coefficients"][term], source_coef))

    mtb_stats = native_minitab_stats(minitab)
    jmp_anova = minijmp["anova"]
    for term in ("Model", "A", "B", "A*B", "残差", "总计"):
        jmp_term = ("残差" if term == "残差" else "总计" if term == "总计" else term)
        if term == "Model":
            jmp_values = {"df": float(minijmp["rank"] - 1), "ss": minijmp["ssr"],
                          "ms": minijmp["ssr"] / (minijmp["rank"] - 1),
                          "f": minijmp["model_f"], "p": minijmp["model_p"]}
        else:
            jmp_values = jmp_anova[jmp_term]
        for metric in ("df", "ss", "ms", "f", "p"):
            rows.append(compare_values(run_number, "anova", term, metric,
                                       mtb_stats["anova"][term][metric], jmp_values[metric], source_anova))
    for metric in ("r2", "adjusted_r2", "sse", "sst", "ssr", "mse"):
        rows.append(compare_values(run_number, "model_summary", "model", metric,
                                   mtb_stats[metric], minijmp[metric], source_anova))
    rows.append(compare_values(run_number, "model_summary", "model", "S",
                               mtb_stats["s"], math.sqrt(minijmp["mse"]), source_anova))

    expected_coefficients = {name: minitab["coefficients"][name] for name in TERM_NAMES}
    for name, expected in EXPECTED_COEFFICIENTS.items():
        if not math.isclose(expected_coefficients[name], expected, abs_tol=TOL_ABS, rel_tol=TOL_REL):
            raise AssertionError(f"Minitab {name} 系数与固定参考不符: {expected_coefficients[name]}")
    if not math.isclose(mtb_stats["sse"], 8.0, abs_tol=TOL_ABS, rel_tol=TOL_REL):
        raise AssertionError(f"Minitab SSE 应为 8，实际为 {mtb_stats['sse']}")
    if not np.allclose(np.asarray(minitab["model_matrix"]).T @ np.asarray(minitab["model_matrix"]),
                       np.diag([8.0] * 4), atol=TOL_ABS, rtol=0):
        raise AssertionError("Minitab 模型矩阵不符合此完整平衡设计的正交结构")
    return rows, mtb_stats


def write_csv(path: Path, rows: list[dict]) -> None:
    fields = ("run", "section", "term", "statistic", "minitab_value", "minijmp_value",
              "absolute_error", "relative_error", "absolute_tolerance", "relative_tolerance",
              "minitab_value_source", "status")
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def parent_main() -> int:
    LOG.write_text("", encoding="utf-8")
    COMMANDS_FILE.write_text(
        "# 由本机 Minitab 19.1.0.1 COM ExecuteCommand 实际运行\n\n"
        "# Native 2² full factorial design, two replicates, coded levels -1/+1\n"
        + DESIGN_COMMAND + "\n\n# Native DOE factorial analysis of the same fixed response data\n"
        + ANALYSIS_COMMAND + "\n",
        encoding="utf-8",
    )
    rows = read_input()
    log("MiniJMP × Minitab 19 2² DOE 对标")
    log(f"项目 Python: {sys.executable}")
    log(f"Minitab: {MTB_EXE}; 固定数据: {INPUT.name}; 两次独立运行")
    log("MiniJMP 入口: code/doe_analysis.py::analyze_factorial(order=2, ss_type='I')")

    all_comparisons = []
    mtb_runs, jmp_runs = {}, {}
    mtb_statistics = {}
    failures = []
    for run_number in (1, 2):
        log(f"===== 独立运行 {run_number}/2 =====")
        process = subprocess.run(
            [sys.executable, "-X", "utf8", str(Path(__file__).resolve()),
             "--com-worker", str(run_number)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=150,
        )
        if process.stdout.strip():
            log(process.stdout.rstrip())
        if process.stderr.strip():
            log("COM worker stderr:\n" + process.stderr.rstrip())
        if process.returncode:
            raise RuntimeError(f"Minitab COM worker {run_number} 退出码 {process.returncode}")
        for _ in range(30):
            if not running_minitab_pids():
                break
            time.sleep(0.5)
        if running_minitab_pids():
            raise RuntimeError("一次 Minitab COM 运行后仍有 Mtb.exe 进程")

        minitab = json.loads((OUT / f"doe_2x2_minitab_run{run_number}.json").read_text(encoding="utf-8"))
        minijmp = run_minijmp(rows)
        minitab.update(native_minitab_stats(minitab))
        comparisons, exact_minitab_stats = compare_run(run_number, minitab, minijmp)
        all_comparisons.extend(comparisons)
        mtb_runs[run_number] = minitab
        jmp_runs[run_number] = minijmp
        mtb_statistics[run_number] = exact_minitab_stats
        failures.extend(row for row in comparisons if row["status"] == "FAIL")
        pass_count = sum(row["status"] == "PASS" for row in comparisons)
        na_count = sum(row["status"] == "N/A" for row in comparisons)
        run_failures = sum(row["status"] == "FAIL" for row in comparisons)
        log(f"运行 {run_number}: {pass_count} 项数值比较通过，{na_count} 项 N/A，"
            f"{run_failures} 项失败；Minitab PID 已退出。")

        (OUT / f"doe_2x2_minijmp_run{run_number}.json").write_text(
            json.dumps(minijmp, ensure_ascii=False, indent=2), encoding="utf-8",
        )

    # Cross-run repeatability for the exact native and MiniJMP outputs.
    for software, runs in (("Minitab", mtb_runs), ("MiniJMP", jmp_runs)):
        first = runs[1]
        second = runs[2]
        flat_first = flatten_repeatability(first)
        flat_second = flatten_repeatability(second)
        for key in sorted(flat_first):
            row = compare_values("run1_vs_run2", f"repeatability_{software}", key, "value",
                                 flat_first[key], flat_second[key], f"{software} sequential clean-process rerun")
            all_comparisons.append(row)
            if row["status"] == "FAIL":
                failures.append(row)

    write_csv(OUT / "doe_2x2_comparison.csv", all_comparisons)
    (OUT / "doe_2x2_minitab_results.json").write_text(
        json.dumps({str(k): v for k, v in mtb_runs.items()}, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    (OUT / "doe_2x2_minijmp_results.json").write_text(
        json.dumps({str(k): v for k, v in jmp_runs.items()}, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    report = make_report(rows, mtb_runs, jmp_runs, mtb_statistics, all_comparisons, failures)
    (OUT / "doe_2x2_acceptance_report.md").write_text(report, encoding="utf-8")
    result = "PASS" if not failures else "FAIL"
    log(f"最终结果: {result}; 比较记录 {len(all_comparisons)} 项；"
        f"PASS={sum(row['status'] == 'PASS' for row in all_comparisons)}, "
        f"N/A={sum(row['status'] == 'N/A' for row in all_comparisons)}, FAIL={len(failures)}。")
    if failures:
        for row in failures[:20]:
            log(f"FAIL {row['run']} {row['section']} {row['term']} {row['statistic']}: "
                f"Minitab={row['minitab_value']}, MiniJMP={row['minijmp_value']}, "
                f"abs={row['absolute_error']}, rel={row['relative_error']}")
        return 1
    log(f"交付目录: {OUT}")
    return 0


def flatten_repeatability(result: dict) -> dict[str, float]:
    flat = {}
    for name, value in result["coefficients"].items():
        flat[f"coefficient:{name}"] = float(value)
    flat["rank"] = float(result["rank"])
    for i, row in enumerate(result["rows"], 1):
        flat[f"fit:{row['run_id']}"] = float(row["fit"])
        flat[f"residual:{row['run_id']}"] = float(row["residual"])
        for j, value in enumerate(row["matrix"]):
            flat[f"matrix:{row['run_id']}:{j}"] = float(value)
    for key in ("r2", "adjusted_r2", "sse", "sst", "ssr", "mse"):
        flat[key] = float(result[key])
    flat["S"] = math.sqrt(float(result["mse"]))
    for term, values in result["anova"].items():
        for metric, value in values.items():
            if value is not None:
                flat[f"anova:{term}:{metric}"] = float(value)
    if "model_f" in result:
        model_df = int(result["rank"]) - 1
        model_values = {"df": model_df, "ss": result["ssr"],
                        "ms": result["ssr"] / model_df,
                        "f": result["model_f"], "p": result["model_p"]}
        for metric, value in model_values.items():
            flat[f"anova:Model:{metric}"] = float(value)
    return flat


def make_report(input_rows, mtb_runs, jmp_runs, mtb_stats, comparisons, failures) -> str:
    success = not failures
    term_stats = mtb_stats[1]["anova"]
    return f"""# 2² 两水平全因子首个自动对标

## 验收结果

**{'PASS' if success else 'FAIL'}**：两次独立 Minitab COM 会话与 MiniJMP 分析均已完成；比较 CSV 共 {len(comparisons)} 行，其中 {sum(row['status'] == 'PASS' for row in comparisons)} 项数值通过、{sum(row['status'] == 'N/A' for row in comparisons)} 项 N/A、{len(failures)} 项失败。N/A 是 Error/Total 行没有定义的 F/P 或 MS。

## 数据与方法

- 固定输入：`doe_2x2_replicated_input.csv`，8 个运行（2 个完整重复），A/B 编码为 −1/+1。响应由 `Y = 50 + 3A − 2B + 4AB + ε` 构成，重复误差为 −1/+1，确保 SSE 非零。
- MiniJMP 使用生产入口 `code/doe_analysis.py::analyze_factorial(order=2, ss_type='I')`；设计由 `code/doe_factorial.py::create_factorial` 建立，系数顺序为截距、A、B、A*B。
- Minitab 19.1.0.1 使用 COM `DispatchEx("Mtb.Application")`；先由 `FFDESIGN` 创建 2²、两次重复、编码水平 −1/+1 的 DOE，再运行原生 `FFACTORIAL`，模型项为 C5、C6、C5*C6。
- MiniJMP 与 COM worker 均由项目 `.venv` 的 Python 3.11.9 运行，COM 使用 `.venv` 中的 pywin32。
- MiniJMP 报 Type I 平方和。此完整平衡设计的模型列正交，A/B/AB 的 sequential 与 adjusted SS 相等。

## Minitab 精度来源

Minitab 原生 `FFACTORIAL` 的完整输出保存在 `doe_2x2_minitab_raw_run1.txt` 与 `doe_2x2_minitab_raw_run2.txt`。对比不从报表舍入值反推系数、矩阵或拟合值：系数来自 C10，模型矩阵来自 M1，拟合值/残差来自 C8/C9，均由 COM 直接回读。ANOVA SS 由这些机器精度的 Minitab 结果及固定输入重建；F/P 使用对应自由度，P 值由 `scipy.stats.f.sf` 计算，并与原生 Minitab 输出一并保留以便复核。

## 首次运行参考值

- 系数：截距=50，A=3，B=−2，AB=4。
- 模型矩阵：8×4，列为 `[1, A, B, AB]`，rank=4；残差 df=4。
- SSE=8，MSE=2，S=√2；SS(A)=72，SS(B)=32，SS(AB)=128，模型 SS=232，总 SS=240，R²=232/240。
- 单项 F：A=36、B=16、AB=64；精确 P 与逐运行拟合值见 `doe_2x2_comparison.csv`。
- ANOVA 数值源：Model `SS={term_stats['Model']['ss']:.12g}, F={term_stats['Model']['f']:.12g}, P={term_stats['Model']['p']:.12g}`；Error `SS={term_stats['残差']['ss']:.12g}, df={term_stats['残差']['df']:.0f}, MS={term_stats['残差']['ms']:.12g}`。

## 文件

- 固定输入：`doe_2x2_replicated_input.csv`
- 本机实际 Session Commands：`doe_2x2_session_commands.txt`
- Minitab 两次原始输出：`doe_2x2_minitab_raw_run1.txt`、`doe_2x2_minitab_raw_run2.txt`
- 精确 Minitab/MiniJMP JSON：`doe_2x2_minitab_results.json`、`doe_2x2_minijmp_results.json`
- 逐项误差与两次重跑一致性：`doe_2x2_comparison.csv`
- 运行日志：`doe_2x2_run.log`

范围仅是一个 2² 完整平衡连续因子案例；不代表其他 DOE 类型或全部统计输出的 parity。
"""


def worker_main(run_number: int) -> int:
    import winreg
    import win32api
    import win32process
    import pythoncom
    import win32com
    import win32com.client
    from importlib.metadata import version as package_version

    result_path = OUT / f"doe_2x2_minitab_run{run_number}.json"
    raw_path = OUT / f"doe_2x2_minitab_raw_run{run_number}.txt"
    raw_sections = []
    app = project = ui = worksheet = columns = None
    factor_a = factor_b = response_col = fit_col = residual_col = coefficient_col = None
    matrix = matrices = command = None
    try:
        if not MTB_EXE.is_file():
            raise FileNotFoundError(MTB_EXE)
        if running_minitab_pids():
            raise RuntimeError("已有 Mtb.exe 正在运行；拒绝连接用户会话")
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r"Mtb.Application\CLSID") as key:
            clsid = winreg.QueryValueEx(key, "")[0]
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, rf"CLSID\{clsid}\LocalServer32") as key:
            server_command = winreg.QueryValueEx(key, "")[0]
        server_path = server_command.strip().split('"')[1] if '"' in server_command else server_command.split()[0]
        if canonical(server_path) != canonical(MTB_EXE):
            raise RuntimeError(f"Mtb.Application 注册服务器不匹配: {server_command}")
        info = win32api.GetFileVersionInfo(str(MTB_EXE), "\\")
        ms, ls = info["FileVersionMS"], info["FileVersionLS"]
        version = ".".join(str(value) for value in (
            win32api.HIWORD(ms), win32api.LOWORD(ms), win32api.HIWORD(ls), win32api.LOWORD(ls)))
        if version != "19.1.0.1":
            raise RuntimeError(f"要求 Minitab 19.1.0.1，实际版本 {version}")

        input_rows = read_input()
        by_cell = defaultdict(list)
        for row in input_rows:
            by_cell[(row["A"], row["B"])].append(row)
        occurrence = Counter()

        app = win32com.client.DispatchEx("Mtb.Application")
        pythoncom.PumpWaitingMessages()
        ui = app.UserInterface
        ui.Visible = False
        ui.UserControl = False
        ui.DisplayAlerts = False
        app_path = str(app.AppPath)
        hwnd = int(app.Handle)
        _, process_id = win32process.GetWindowThreadProcessId(hwnd)
        kernel32 = ctypes.windll.kernel32
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
            raise RuntimeError(f"FFDESIGN 未生成标准六列，Columns.Count={columns.Count}")
        factor_a, factor_b = columns.Item(5), columns.Item(6)
        if (str(factor_a.Name), str(factor_b.Name)) != ("A", "B"):
            raise RuntimeError(f"FFDESIGN 因子列名不符: {factor_a.Name}, {factor_b.Name}")
        a_values = [float(value) for value in factor_a.GetData()]
        b_values = [float(value) for value in factor_b.GetData()]
        if len(a_values) != 8 or len(b_values) != 8:
            raise RuntimeError(f"FFDESIGN 应生成 8 行，实际 A/B 长度 {len(a_values)}/{len(b_values)}")

        data_rows, response_values = [], []
        for a, b in zip(a_values, b_values):
            key = (int(a), int(b))
            index = occurrence[key]
            cell_rows = by_cell[key]
            if index >= len(cell_rows):
                raise RuntimeError(f"FFDESIGN 因子组合重复过多: {key}")
            row = cell_rows[index]
            occurrence[key] += 1
            response_values.append(row["Y"])
            data_rows.append({**row, "design_A": int(a), "design_B": int(b)})
        if any(occurrence[(a, b)] != 2 for a in (-1, 1) for b in (-1, 1)):
            raise RuntimeError(f"FFDESIGN 不是每个组合两次重复: {dict(occurrence)}")

        response_col = columns.Add(None, None, 1)
        response_col.Name = "Y"
        response_col.SetData(tuple(response_values), 1, len(response_values))
        fit_col = columns.Add(None, None, 1)
        fit_col.Name = "MtbFit"
        residual_col = columns.Add(None, None, 1)
        residual_col.Name = "MtbResidual"
        coefficient_col = columns.Add(None, None, 1)
        coefficient_col.Name = "MtbCoefficients"
        if [int(v) for v in response_col.GetData()] != [int(row["Y"]) for row in data_rows]:
            raise AssertionError("Minitab 响应列写入/回读与固定 CSV 不一致")

        design_output = capture_command_output(project)
        raw_sections.append("===== FFDESIGN actual command =====\n" + DESIGN_COMMAND
                            + "\n===== FFDESIGN OutputDocument/Outputs =====\n" + design_output)
        command_count_before = int(project.Commands.Count)
        project.ExecuteCommand(ANALYSIS_COMMAND)
        command_count_after = int(project.Commands.Count)
        analysis_error = str(app.LastError or "")
        analysis_status = str(app.Status)
        if command_count_after <= command_count_before:
            raw_sections.append(
                f"FFACTORIAL command count before/after: {command_count_before}/{command_count_after}\n"
                f"Application.LastError: {analysis_error}\nApplication.Status: {analysis_status}"
            )
            raise RuntimeError(
                f"FFACTORIAL 未创建命令对象；LastError={analysis_error!r}; Status={analysis_status}"
            )
        analysis_output = capture_command_output(project, command_count_after)
        raw_sections.append("===== FFACTORIAL actual command =====\n" + ANALYSIS_COMMAND
                            + "\n===== FFACTORIAL OutputDocument/Outputs =====\n" + analysis_output)
        if not analysis_output.strip():
            raise RuntimeError("FFACTORIAL 未返回可读统计输出")

        # The storage columns are created before analysis so these COM values stay unrounded.
        coefficient_values = [float(value) for value in coefficient_col.GetData()]
        fit_values = [float(value) for value in fit_col.GetData()]
        residual_values = [float(value) for value in residual_col.GetData()]
        if len(coefficient_values) != 4 or len(fit_values) != 8 or len(residual_values) != 8:
            raise RuntimeError("FFACTORIAL 存储结果的行数不符合 4 系数、8 拟合和 8 残差")
        matrices = worksheet.Matrices
        if int(matrices.Count) < 1:
            raise RuntimeError("FFACTORIAL 没有存储 XMATRIX M1")
        matrix = matrices.Item(1)
        if str(matrix.Name).casefold() != "m1" or int(matrix.RowCount) != 8 or int(matrix.ColumnCount) != 4:
            raise RuntimeError(f"Minitab M1 矩阵维度/名称异常: {matrix.Name}, {matrix.RowCount}x{matrix.ColumnCount}")
        flat = [float(value) for value in matrix.GetData()]
        if len(flat) != 32:
            raise RuntimeError(f"Minitab XMATRIX M1 应有 32 个值，实际 {len(flat)}")
        model_matrix = [[flat[col * 8 + row] for col in range(4)] for row in range(8)]
        matrix_rank = int(__import__("numpy").linalg.matrix_rank(model_matrix))
        coefficients = dict(zip(TERM_NAMES, coefficient_values))
        fits_by_id, residuals_by_id, matrix_by_id = {}, {}, {}
        for index, row in enumerate(data_rows):
            run_id = row["run_id"]
            fits_by_id[run_id] = fit_values[index]
            residuals_by_id[run_id] = residual_values[index]
            matrix_by_id[run_id] = model_matrix[index]
        result = {
            "run": run_number, "version": version, "clsid": clsid,
            "python_executable": sys.executable, "pywin32_version": package_version("pywin32"),
            "pythoncom_module": pythoncom.__file__, "win32com_module": win32com.__file__,
            "local_server": server_command, "app_path": app_path, "process_path": process_path,
            "native_commands": [DESIGN_COMMAND, ANALYSIS_COMMAND],
            "factor_columns": {"A": a_values, "B": b_values}, "data_rows": data_rows,
            "coefficients": coefficients,
            "model_matrix": [matrix_by_id[i] for i in range(1, 9)], "rank": matrix_rank,
            "rows": [{**row, "fit": fits_by_id[row["run_id"]],
                      "residual": residuals_by_id[row["run_id"]],
                      "matrix": matrix_by_id[row["run_id"]]} for row in data_rows],
        }
        result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        raw_path.write_text("\n\n".join(raw_sections) + "\n", encoding="utf-8")
        print(f"COM worker Python: {sys.executable}; pywin32={package_version('pywin32')}")
        print(f"COM worker run {run_number}: Minitab {version}; AppPath/进程映像已核实; "
              f"FFDESIGN+FFACTORIAL 完成; rank={matrix_rank}; C10/M1/C8/C9 已回读。", flush=True)
        return 0
    except Exception:
        raw_path.write_text("\n\n".join(raw_sections) + "\n", encoding="utf-8")
        traceback.print_exc()
        return 1
    finally:
        matrix = matrices = coefficient_col = residual_col = fit_col = response_col = None
        factor_a = factor_b = columns = worksheet = project = app = ui = None


def capture_command_output(project, command_index=None) -> str:
    commands = project.Commands
    command = commands.Item(int(command_index if command_index is not None else commands.Count))
    outputs = command.Outputs
    texts = [str(outputs.Item(index).Text or "") for index in range(1, int(outputs.Count) + 1)]
    document_text = str(command.OutputDocument.Text or "")
    blocks = ["OutputDocument.Text:\n" + document_text]
    blocks.extend(f"Output.Text[{index}]:\n{text}" for index, text in enumerate(texts, 1))
    return "\n\n".join(blocks)


def running_minitab_pids() -> list[int]:
    result = subprocess.run(
        ["tasklist.exe", "/FI", "IMAGENAME eq Mtb.exe", "/FO", "CSV", "/NH"],
        check=True, capture_output=True, text=True, encoding="mbcs", errors="replace",
    )
    return [int(row[1]) for row in csv.reader(result.stdout.splitlines())
            if len(row) >= 2 and row[0].casefold() == "mtb.exe" and row[1].isdigit()]


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


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
        log("FAIL: " + traceback.format_exc())
        (OUT / "doe_2x2_acceptance_report.md").write_text(
            "# 2² 两水平全因子自动对标\n\n**FAIL**\n\n````text\n" + traceback.format_exc()
            + "````\n", encoding="utf-8",
        )
        raise SystemExit(1)
