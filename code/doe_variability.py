"""两水平 Factorial 的变异性预处理与等权 ln(SD) 主效应模型。"""
import numpy as np
from scipy import stats

from doe_core import restore_design_result


_STATUS_MESSAGES = {
    "available": "等权 ln(SD) 主效应与区组推断可用",
    "missing_measurements": "存在缺失测量，不执行等权 ln(SD) 推断",
    "unequal_sample_sizes": "各摘要样本数不等，不执行等权 ln(SD) 推断",
    "insufficient_measurements": "至少一组有效测量少于 2，SD 不可计算",
    "zero_sd": "至少一组 SD 为 0，ln(SD) 模型不可用",
    "rank_deficient": "主效应与区组模型矩阵秩亏；保留拟合值，不报告唯一系数或 F/p",
    "saturated": "模型饱和且没有误差自由度；保留拟合，不报告 F/p",
    "zero_mse": "模型误差均方为 0；保留拟合，不报告 F/p",
}


def analyze_variability(frame, metadata, responses, mode="within_run"):
    """计算重复测量摘要及可用时的等权 ln(SD) 主效应/固定区组模型。

    mode 为 within_run 时，responses 是同一 DOE 运行的多个响应列；
    independent_runs 时仅接受一个响应列，并按因子设定与区组聚合不同 run_id。
    """
    design = restore_design_result(frame, metadata)
    spec = design.spec
    if spec.design_type == "split_plot":
        raise ValueError("Variability 不支持 Split-Plot 设计")
    if spec.design_type not in (
            "two_level_full", "two_level_fractional", "general_full_factorial"):
        raise ValueError("Variability 仅支持两水平全/部分因子及一般全因子的两水平子集")
    if len(spec.factors) < 2:
        raise ValueError("Variability 至少需要两个因子")
    if mode not in ("within_run", "independent_runs"):
        raise ValueError("mode 必须是 within_run 或 independent_runs")
    if isinstance(responses, str):
        responses = (responses,)
    elif isinstance(responses, (list, tuple)):
        responses = tuple(responses)
    else:
        raise ValueError("responses 必须是响应列名或列名序列")
    if (not responses or any(not isinstance(name, str) for name in responses)
            or len(set(responses)) != len(responses)):
        raise ValueError("responses 必须是非空且不重复的响应列名")
    if mode == "independent_runs" and len(responses) != 1:
        raise ValueError("独立运行重复只能选择一个响应列")
    if any(name not in metadata["column_map"]["responses"] for name in responses):
        raise ValueError("响应不属于 DOE 声明的映射列")

    coded_runs = []
    for run in design.runs:
        if run.point_type != "factorial":
            raise ValueError("Variability 只接受两水平因子点")
        coded = []
        for factor in spec.factors:
            value = run.settings[factor.factor_id]
            if factor.factor_type == "continuous":
                coded.append(factor.to_coded(value))
            elif factor.factor_type == "categorical" and len(factor.levels) == 2:
                coded.append(-1 if value == factor.levels[0] else 1)
            else:
                raise ValueError("Variability 要求每个因子恰有两个水平")
        coded = tuple(coded)
        if any(value not in (-1, 1) for value in coded):
            raise ValueError("Variability 因子设定必须恰为低或高水平")
        coded_runs.append((run, coded))

    blocks = [run.block for run, _ in coded_runs]
    if any(block is None for block in blocks) and any(block is not None for block in blocks):
        raise ValueError("区组列不能只对部分运行填写")

    if mode == "within_run":
        groups = [{"runs": [run], "coded": coded, "block": run.block}
                  for run, coded in coded_runs]
    else:
        groups = []
        by_setting = {}
        for run, coded in coded_runs:
            key = (coded, run.block)
            if key not in by_setting:
                by_setting[key] = {"runs": [], "coded": coded, "block": run.block}
                groups.append(by_setting[key])
            by_setting[key]["runs"].append(run)

    summaries = []
    for group in groups:
        runs = group["runs"]
        if mode == "within_run":
            measurements = [runs[0].responses[name] for name in responses]
        else:
            measurements = [run.responses[responses[0]] for run in runs]
        values = [value for value in measurements if value is not None]
        n = len(values)
        mean = float(np.mean(values)) if n else None
        sd = float(np.std(values, ddof=1)) if n >= 2 else None
        summaries.append({
            "settings": dict(runs[0].settings), "block": group["block"],
            "mean": mean, "sd": sd, "n": n,
            "missing": len(measurements) - n,
            "run_ids": [run.run_id for run in runs],
        })

    reasons = []
    if any(row["missing"] for row in summaries):
        reasons.append("missing_measurements")
    sample_sizes = {row["n"] for row in summaries}
    if len(sample_sizes) > 1:
        reasons.append("unequal_sample_sizes")
    if any(row["n"] < 2 for row in summaries):
        reasons.append("insufficient_measurements")
    if any(row["sd"] == 0 for row in summaries if row["sd"] is not None):
        reasons.append("zero_sd")
    if reasons:
        status = reasons[0]
        return {
            "mode": mode, "summaries": summaries, "fit": None,
            "inference_status": status, "status_reasons": reasons,
            "status_message": _STATUS_MESSAGES[status],
        }

    factor_matrix = np.asarray([group["coded"] for group in groups], dtype=float)
    block_levels = list(dict.fromkeys(row["block"] for row in summaries))
    has_blocks = block_levels[0] is not None
    block_columns = [
        np.asarray([float(row["block"] == level) for row in summaries])
        for level in block_levels[1:]
    ] if has_blocks else []
    x = np.column_stack([np.ones(len(summaries)), factor_matrix, *block_columns])
    y = np.log(np.asarray([row["sd"] for row in summaries], dtype=float))
    beta, _, rank, _ = np.linalg.lstsq(x, y, rcond=None)
    rank = int(rank)
    fitted = x @ beta
    residuals = y - fitted
    sse = float(residuals @ residuals)
    df_error = len(summaries) - rank
    residual_tolerance = (np.finfo(float).eps * max(x.shape) * max(
        float(np.linalg.norm(x, ord=np.inf) * np.linalg.norm(beta, ord=np.inf)),
        float(np.linalg.norm(y, ord=np.inf)),
    ))
    if np.linalg.norm(residuals, ord=np.inf) <= residual_tolerance:
        # Exact fits can leave machine-roundoff residuals that would create false F tests.
        sse = 0.0
    mse = sse / df_error if df_error > 0 else None

    if rank < x.shape[1]:
        status = "rank_deficient"
    elif df_error <= 0:
        status = "saturated"
    elif mse == 0:
        status = "zero_mse"
    else:
        status = "available"

    full_rank = rank == x.shape[1]
    factor_coefficients = {
        factor.factor_id: float(beta[index + 1]) if full_rank else None
        for index, factor in enumerate(spec.factors)
    }
    terms = {}
    covariance = np.linalg.inv(x.T @ x) if status == "available" else None
    for index, factor in enumerate(spec.factors, 1):
        coefficient = factor_coefficients[factor.factor_id]
        term = {
            "coefficient": coefficient,
            "effect_high_minus_low": 2 * coefficient if coefficient is not None else None,
            "standard_error": None, "adjusted_ss": None,
            "f": None, "df_numerator": 1, "df_error": df_error, "p": None,
        }
        if status == "available":
            variance_factor = float(covariance[index, index])
            term["standard_error"] = float(np.sqrt(mse * variance_factor))
            term["adjusted_ss"] = coefficient ** 2 / variance_factor
            term["f"] = term["adjusted_ss"] / mse
            term["p"] = float(stats.f.sf(term["f"], 1, df_error))
        terms[factor.factor_id] = term

    block_effects = {}
    if has_blocks:
        block_effects[block_levels[0]] = 0.0 if full_rank else None
        for index, level in enumerate(block_levels[1:], 1):
            block_effects[level] = (float(beta[len(spec.factors) + index])
                                    if full_rank else None)
    fit = {
        "intercept": float(beta[0]) if full_rank else None,
        "coefficients": factor_coefficients,
        "terms": terms,
        "block_reference": block_levels[0] if has_blocks else None,
        "block_effects": block_effects,
        "fitted_log_sd": [float(value) for value in fitted],
        "residuals": [float(value) for value in residuals],
        "sse": sse, "rank": rank, "df_error": df_error, "mse": mse,
        "inference_status": status,
    }
    return {
        "mode": mode, "summaries": summaries, "fit": fit,
        "inference_status": status,
        "status_reasons": [] if status == "available" else [status],
        "status_message": _STATUS_MESSAGES[status],
    }
