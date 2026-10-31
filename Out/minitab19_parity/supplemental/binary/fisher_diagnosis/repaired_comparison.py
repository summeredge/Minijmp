"""Replay the archived binary DOE inputs through MiniJMP and compare offline."""
import ast
import csv
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
from scipy.special import expit

HERE = Path(__file__).resolve().parent
BINARY = HERE.parent
SUPPLEMENTAL = BINARY.parent
ROOT = HERE.parents[4]
sys.path[:0] = [str(BINARY), str(SUPPLEMENTAL), str(ROOT / "code")]

import verify  # noqa: E402
from common import unique_rows  # noqa: E402
from doe_bbd import create_bbd  # noqa: E402
from doe_binary_analysis import analyze_binary_doe, predict_binary_probability  # noqa: E402
from doe_core import DesignSpec, FactorSpec, restore_design_result  # noqa: E402
from doe_factorial import create_factorial  # noqa: E402

INPUT_FILES = {
    "BIN-FACTORIAL": BINARY / "bin_factorial_input.csv",
    "BIN-RSM": BINARY / "bin_rsm_input.csv",
}
MINIJMP = BINARY / "minijmp_results.json"
MINITAB = BINARY / "minitab_results.json"
OLD_COMPARISON = BINARY / "comparison.csv"
OUT_CSV = HERE / "repaired_comparison.csv"
OUT_REPORT = HERE / "repair_acceptance.md"
CSV_FIELDS = [
    "case_id", "comparison_run", "section", "term", "statistic",
    "old_status", "old_minijmp_value", "old_absolute_error", "old_relative_error",
    "minitab_value", "minijmp_value", "absolute_error", "relative_error",
    "absolute_tolerance", "relative_tolerance", "minitab_value_source",
    "minijmp_value_source", "status",
]
COMPARE_KEY = ("case_id", "section", "term", "statistic")


def read_csv(path):
    with path.open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def replay_case(case_id, archived_inputs):
    if case_id == "BIN-FACTORIAL":
        names = ("A", "B")
        spec = DesignSpec(
            "binary-full", (FactorSpec("A", "A", -1, 1), FactorSpec("B", "B", -1, 1)),
            ("Events", "Trials"), seed=11, design_type="two_level_full",
        )
        frame, metadata = create_factorial(spec)
        family, model_order = "factorial", 2
    else:
        names = tuple("ABC")
        spec = DesignSpec(
            "binary-bbd", tuple(FactorSpec(name, name, -1, 1) for name in names),
            ("Events", "Trials"), seed=11, design_type="box_behnken",
            ccd_center_points=2,
        )
        frame, metadata = create_bbd(spec)
        family, model_order = "rsm", 2

    archived_by_key = {}
    for row in archived_inputs:
        settings = ast.literal_eval(row["settings"])
        key = (verify.point_key(settings, names), int(row["occurrence"]))
        archived_by_key[key] = row

    design = restore_design_result(frame, metadata)
    occurrences, counts_by_run, seen_keys = Counter(), {}, set()
    for run in sorted(design.runs, key=lambda item: item.standard_order):
        settings = {name: float(run.settings[name]) for name in names}
        point = verify.point_key(settings, names)
        occurrences[point] += 1
        key = (point, occurrences[point])
        seen_keys.add(key)
        source = archived_by_key[key]
        source_settings = ast.literal_eval(source["settings"])
        if any(float(source_settings[name]) != settings[name] for name in names):
            raise AssertionError(f"{case_id} archived point mismatch: {key}")
        counts_by_run[run.run_id] = (int(source["events"]), int(source["trials"]))
    if seen_keys != set(archived_by_key):
        raise AssertionError(f"{case_id} archived input row mapping mismatch")

    run_id_column = metadata["column_map"]["run_id"]
    events_column = metadata["column_map"]["responses"]["Events"]
    trials_column = metadata["column_map"]["responses"]["Trials"]
    values = [counts_by_run[run_id] for run_id in frame[run_id_column]]
    frame[events_column] = [pair[0] for pair in values]
    frame[trials_column] = [pair[1] for pair in values]
    result = analyze_binary_doe(
        frame, metadata, events_column, trials_column, family, model_order=model_order)
    local_case = verify.analysis_summary(case_id, frame, metadata, result)
    if case_id == "BIN-RSM":
        model = result["detail"]["term_model"]
        local_case["prediction_settings"] = verify.RSM_PREDICTION
        local_case["prediction_row"] = [
            float(value) for value in model.row(model.coded(verify.RSM_PREDICTION))
        ]
        local_case["prediction"] = predict_binary_probability(
            result, verify.RSM_PREDICTION, confidence=0.95)
    return local_case


def key(row):
    return tuple(row[name] for name in COMPARE_KEY)


def fisher_covariance(information):
    lower = np.linalg.cholesky(information)
    identity = np.eye(information.shape[0])
    return np.linalg.solve(lower.T, np.linalg.solve(lower, identity))


def main():
    minijmp = json.loads(MINIJMP.read_text(encoding="utf-8"))
    minitab = json.loads(MINITAB.read_text(encoding="utf-8"))
    old_rows = read_csv(OLD_COMPARISON)
    new_cases = {
        case_id: replay_case(case_id, read_csv(INPUT_FILES[case_id]))
        for case_id in verify.CASE_IDS
    }

    for case_id, case in new_cases.items():
        original = minijmp[case_id]
        if case["rank"] != original["rank"] or len(case["rows"]) != original["n_runs"]:
            raise AssertionError(f"{case_id} replay shape/rank changed")
        old_coefficients = np.asarray([row["coefficient"] for row in original["coefficients"]])
        new_coefficients = np.asarray([row["coefficient"] for row in case["coefficients"]])
        if not np.allclose(old_coefficients, new_coefficients, rtol=0, atol=1e-12):
            raise AssertionError(f"{case_id} coefficient estimates changed")
        old_by_key = {(row["point_key"], row["occurrence"]): row for row in original["rows"]}
        new_by_key = {(row["point_key"], row["occurrence"]): row for row in case["rows"]}
        for row in case["rows"]:
            old = old_by_key[(row["point_key"], row["occurrence"])]
            if (row["events"], row["trials"]) != (old["events"], old["trials"]):
                raise AssertionError(f"{case_id} fixed counts changed")
            if not np.allclose(row["matrix"], old["matrix"], rtol=0, atol=0):
                raise AssertionError(f"{case_id} design matrix changed")
        for field in ("model_df", "residual_df"):
            if case[field] != original[field]:
                raise AssertionError(f"{case_id} {field} changed")
        for field in ("log_likelihood", "model_lr", "model_p", "deviance",
                      "deviance_p", "pearson_chi_square", "pearson_p"):
            current, previous = case[field], original[field]
            if ((current is None or previous is None) and current is not previous
                    or current is not None and not np.isclose(
                        current, previous, rtol=0, atol=1e-12)):
                raise AssertionError(f"{case_id} {field} changed")
        if set(new_by_key) != set(old_by_key):
            raise AssertionError(f"{case_id} point/occurrence mapping changed")

    new_rows = [
        row for case_id in verify.CASE_IDS
        for row in verify.compare_case(case_id, new_cases[case_id], minitab[case_id])
    ]
    old_unique, new_unique = unique_rows(old_rows), unique_rows(new_rows)
    old_by_key = {key(row): row for row in old_unique}
    new_by_key = {key(row): row for row in new_unique}
    if (len(old_by_key) != len(old_unique) or len(new_by_key) != len(new_unique)
            or set(old_by_key) != set(new_by_key)):
        raise AssertionError("offline comparison keys differ from the frozen CSV")
    old_failures = [row for row in old_unique if row["status"] == "FAIL"]
    if len(old_failures) != 16:
        raise AssertionError(f"expected the frozen 16 FAIL rows, got {len(old_failures)}")
    expected_rsm_failures = {("BIN-RSM", "coefficient", term, "wald_z")
                             for term in ("A", "A²", "B²", "A*C")}
    repaired = [new_by_key[key(row)] for row in old_failures]
    repaired_counts = Counter(row["status"] for row in repaired)
    if repaired_counts != Counter({"PASS": 12, "FAIL": 4}):
        raise AssertionError(f"unexpected repaired status counts: {repaired_counts}")
    if {key(row) for row in repaired if row["status"] == "FAIL"} != expected_rsm_failures:
        raise AssertionError("the four remaining failures differ from the frozen BIN-RSM z rows")
    if any(new_by_key[key(row)]["status"] != row["status"]
           for row in old_unique if row["status"] != "FAIL"):
        raise AssertionError("a comparison outside the original 16 FAIL rows changed status")

    full_counts = Counter(row["status"] for row in new_unique)
    if full_counts != Counter({"PASS": 189, "FAIL": 4, "N/A": 2}):
        raise AssertionError(f"unexpected full comparison status counts: {full_counts}")

    csv_rows = []
    for old in old_failures:
        new = new_by_key[key(old)]
        csv_rows.append({
            **{field: new[field] for field in (
                "case_id", "comparison_run", "section", "term", "statistic",
                "minitab_value", "minijmp_value", "absolute_error", "relative_error",
                "absolute_tolerance", "relative_tolerance", "minitab_value_source",
                "minijmp_value_source", "status",
            )},
            "old_status": old["status"],
            "old_minijmp_value": old["minijmp_value"],
            "old_absolute_error": old["absolute_error"],
            "old_relative_error": old["relative_error"],
        })

    old_coefficient_changes, old_probability_changes = [], []
    for case_id, case in new_cases.items():
        original = minijmp[case_id]
        old_coefficient_changes.extend(
            abs(new["coefficient"] - old["coefficient"])
            for new, old in zip(case["coefficients"], original["coefficients"])
        )
        original_rows = {(row["point_key"], row["occurrence"]): row
                         for row in original["rows"]}
        old_probability_changes.extend(
            abs(row["fit"] - original_rows[(row["point_key"], row["occurrence"])]["fit"])
            for row in case["rows"]
        )

    rsm_local = new_cases["BIN-RSM"]
    rsm_native = minitab["BIN-RSM"]
    local_rows = {(row["point_key"], row["occurrence"]): row for row in rsm_local["rows"]}
    native_rows = {(row["point_key"], row["occurrence"]): row
                   for row in rsm_native["design_rows"]}
    ordered_keys = sorted(local_rows)
    x_local = np.asarray([local_rows[item]["matrix"] for item in ordered_keys])
    x_native = np.asarray([native_rows[item]["matrix"] for item in ordered_keys])
    probabilities = np.asarray([native_rows[item]["fit"] for item in ordered_keys])
    trials = np.asarray([native_rows[item]["trials"] for item in ordered_keys], dtype=float)
    beta_native = np.asarray(rsm_native["coefficients"], dtype=float)
    if not np.array_equal(x_local, x_native):
        raise AssertionError("Minitab M1 and MiniJMP RSM matrix differ")
    information = x_native.T @ ((trials * probabilities * (1 - probabilities))[:, None]
                                * x_native)
    covariance_from_fits = fisher_covariance(information)
    covariance_m2 = np.asarray(rsm_native["xpw_inverse"], dtype=float)
    native_se = np.asarray(rsm_native["standard_errors"], dtype=float)
    m2_se = np.sqrt(np.diag(covariance_m2))
    fisher_se = np.sqrt(np.diag(covariance_from_fits))
    if not np.array_equal(m2_se, native_se):
        raise AssertionError("Minitab M2 diagonal does not reproduce its direct SE values")
    covariance_delta = covariance_m2 - covariance_from_fits
    delta_index = np.unravel_index(np.argmax(np.abs(covariance_delta)), covariance_delta.shape)
    probability_reconstruction = float(np.max(np.abs(expit(x_native @ beta_native) - probabilities)))
    z_rows = [row for row in repaired
              if row["case_id"] == "BIN-RSM" and row["statistic"] == "wald_z"]
    max_z_row = max(z_rows, key=lambda row: float(row["absolute_error"]))

    with OUT_CSV.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(csv_rows)

    lines = [
        "# Binary Logistic 最终 Fisher 修复后离线验收", "",
        "日期：2026-10-31（Asia/Shanghai）  ",
        "状态：**BIN-FACTORIAL 原 12 条 FAIL 已修复；BIN-RSM 原 4 条 Wald z 仍 FAIL。**", "",
        "## 范围与方法", "",
        "- 直接用当前 MiniJMP `fit_grouped_binomial()` 重放归档的两份固定输入，并调用既有 `compare_case()` 与冻结 Minitab 19 JSON 对比。",
        "- 比较仍使用冻结键与 `abs_tol=rel_tol=1e-9`，按原比较器规则满足绝对或相对容差即 PASS。",
        "- 只列出原 `comparison.csv` 中的 16 条 FAIL；每行同时保留旧状态、旧值和旧误差。完整冻结比较、输入、JSON 与 Minitab 原始证据未改写。",
        "- 本次未调用 `verify.py` 入口、未启动 Minitab/COM，也未改写原始 Minitab 参考。", "",
        "## 对比结果", "",
        f"原冻结比较：{Counter(row['status'] for row in old_unique)}；本次完整离线重比：{full_counts}。",
        f"原 16 条 FAIL：**12 PASS、4 FAIL**。修复后逐项值见 [`repaired_comparison.csv`](repaired_comparison.csv)。", "",
        "### 已修复的 12 项", "",
        "| 案例 | 项 | 指标 | 修复后绝对误差 |",
        "|---|---|---|---:|",
    ]
    for row in csv_rows:
        if row["status"] == "PASS":
            lines.append(
                f"| {row['case_id']} | {row['term']} | {row['statistic']} | {float(row['absolute_error']):.12g} |"
            )
    lines.extend([
        "", "### 保留的 4 项 BIN-RSM Wald z FAIL", "",
        "| 项 | MiniJMP 修复后 z | Minitab 派生 z | 绝对误差 | 相对误差 |",
        "|---|---:|---:|---:|---:|",
    ])
    for row in z_rows:
        lines.append(
            f"| {row['term']} | {float(row['minijmp_value']):.16g} | {float(row['minitab_value']):.16g} | "
            f"{float(row['absolute_error']):.12g} | {float(row['relative_error']):.12g} |"
        )
    lines.extend([
        "", f"最大误差是 `{max_z_row['term']}`：MiniJMP z={float(max_z_row['minijmp_value']):.16g}，",
        f"Minitab 派生 z={float(max_z_row['minitab_value']):.16g}，绝对误差 `{float(max_z_row['absolute_error']):.16g}`。", "",
        "## BIN-RSM M2 数值定位", "",
        f"- X 为 `{x_native.shape[0]}×{x_native.shape[1]}`、秩 {int(np.linalg.matrix_rank(x_native))}；矩阵列序为：",
        "  `" + "、".join(rsm_local["column_names"]) + "`。归档 Minitab M1 与 MiniJMP X 逐元素相同；FITS 与 `expit(Xβ)` 最大差为 `" + f"{probability_reconstruction:.12g}`。",
        "- Minitab M2 对角线开方与 10 个直接 `SECOEFFICIENTS` 完全相等。下表将 M2 对角方差、原生 SE 与按归档 FITS 重算的终点 Fisher SE 并列。", "",
        "| 项 | M2 对角方差 | M2 开方 / 原生 SE | 终点 Fisher SE |",
        "|---|---:|---:|---:|",
    ])
    for index, term in enumerate(rsm_local["column_names"]):
        lines.append(
            f"| {term} | {covariance_m2[index, index]:.16g} | {m2_se[index]:.16g} | {fisher_se[index]:.16g} |"
        )
    row_name, col_name = (rsm_local["column_names"][delta_index[0]],
                          rsm_local["column_names"][delta_index[1]])
    lines.extend([
        "",
        f"M2 与按 FITS、X、trials 重算的 Fisher 协方差最大元素差为 `{abs(covariance_delta[delta_index]):.16g}`，位置 `{row_name} × {col_name}`。",
        "四个 z 差异与 M2/终点 Fisher 的微小 SE 差相符；终点 Fisher 仍未使它们满足容差。现有归档不能区分 Minitab 内部权重时点、矩阵算法或其他数值细节，**剩余根因未知**。未仿制 Minitab 特有计算，也未改容差。", "",
        "## 未变化的拟合输出", "",
        f"- 两案例系数最大绝对变化：`{max(old_coefficient_changes):.12g}`。",
        f"- 两案例拟合概率最大绝对变化：`{max(old_probability_changes):.12g}`。",
        "- LogLik、Deviance、Pearson 与 LR/df 的定义和输出仍由原拟合路径计算；本修复只改终点推断协方差及 SE/z/p。",
        "- 定向测试验证 `covariance_array`、系数 SE/z/p 和 RSM 预测区间使用同一终点 Fisher 协方差。", "",
        "可进入下一轮 Minitab XPWXINVERSE 独立调查；本阶段不宣称 Binary Logistic 全部对标通过。", "",
    ])
    OUT_REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({
        "old_failures": len(old_failures), "repaired_status_counts": dict(repaired_counts),
        "full_status_counts": dict(full_counts), "max_rsm_z": max_z_row,
        "max_m2_fisher_delta": float(abs(covariance_delta[delta_index])),
        "max_m2_fisher_delta_position": [row_name, col_name],
        "csv": str(OUT_CSV), "report": str(OUT_REPORT),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
