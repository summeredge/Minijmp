"""Full balanced Split-Plot ANOVA with whole-plot and subplot strata."""
import math
from itertools import combinations

import numpy as np
from scipy import stats

from doe_splitplot import validate_split_plot_design


def analyze_split_plot(frame, metadata, response):
    """Fit every factorial effect and test it against its experimental-unit error."""
    design = validate_split_plot_design(frame, metadata)
    spec, runs = design.spec, design.runs
    if response not in spec.response_names:
        raise ValueError("响应不属于该设计")
    values = [run.responses[response] for run in runs]
    if any(value is None for value in values):
        raise ValueError("响应存在缺失值，请填写全部运行的响应")
    try:
        y = np.asarray(values, dtype=float)
    except (ValueError, OverflowError) as exc:
        raise ValueError("响应超出可分析的数值范围") from exc
    if (not np.isfinite(y).all() or any(
            isinstance(value, int) and int(converted) != value
            for value, converted in zip(values, y))):
        raise ValueError("响应必须是有限且可表示的数值")

    factors = spec.factors
    factor_ids = tuple(factor.factor_id for factor in factors)
    hard_ids = tuple(factor.factor_id for factor in factors
                     if factor.randomization_role == "hard_to_change")
    blocks = tuple(sorted({run.block for run in runs}))
    hard_count = 1 << len(hard_ids)
    easy_count = 1 << (len(factors) - len(hard_ids))
    block_index = {block: index for index, block in enumerate(blocks)}
    factor_by_id = {factor.factor_id: factor for factor in factors}
    coded = np.asarray([
        [int(factor_by_id[factor_id].to_coded(run.settings[factor_id]))
         for factor_id in factor_ids]
        for run in runs
    ], dtype=float)
    subsets = [subset for order in range(1, len(factors) + 1)
               for subset in combinations(range(len(factors)), order)]
    term_names = [":".join(factor_ids[index] for index in subset)
                  for subset in subsets]
    term_matrix = np.column_stack([
        np.prod(coded[:, subset], axis=1) for subset in subsets
    ])
    block_matrix = np.eye(len(blocks))[np.asarray([block_index[run.block] for run in runs])]
    model_matrix = np.column_stack((block_matrix, term_matrix))
    model_rank = int(np.linalg.matrix_rank(model_matrix))
    expected_rank = len(blocks) + (1 << len(factors)) - 1
    if model_rank != expected_rank:
        raise ValueError(f"裂区模型矩阵秩亏：rank={model_rank}，期望 {expected_rank}；F/p 不可用")
    n = len(runs)
    term_gram = term_matrix.T @ term_matrix
    if (not np.array_equal(block_matrix.T @ term_matrix,
                           np.zeros((len(blocks), len(subsets))))
            or not np.array_equal(term_gram, np.eye(len(subsets)) * n)):
        raise ValueError("裂区因子对比矩阵不正交；F/p 不可用")

    # Remove a common response offset before centering to preserve small residuals.
    offset = float(y[0])
    centered_values = y - offset
    center = float(centered_values.mean())
    centered = centered_values - center
    grand = offset + center
    block_rows = [np.flatnonzero(block_matrix[:, index]) for index in range(len(blocks))]
    block_coefficients = np.asarray([
        math.fsum(float(centered[index]) for index in indices) / len(indices)
        for indices in block_rows
    ])
    term_coefficients = np.asarray([
        math.fsum(float(term_matrix[row, column] * centered[row])
                  for row in range(n)) / n
        for column in range(len(subsets))
    ])
    fixed_fitted_centered = np.asarray([
        math.fsum(
            [float(block_coefficients[block_index[run.block]])]
            + [float(term_matrix[row, column] * term_coefficients[column])
               for column in range(len(subsets))])
        for row, run in enumerate(runs)
    ])
    residuals = centered - fixed_fitted_centered
    fitted = grand + fixed_fitted_centered
    ss_total = float(centered @ centered)
    ss_block = float(math.fsum(
        len(indices) * float(coefficient) ** 2
        for indices, coefficient in zip(block_rows, block_coefficients)))
    term_ss = {
        name: float(coefficient * coefficient * n)
        for name, coefficient in zip(term_names, term_coefficients)
    }

    whole_plots = {}
    for index, run in enumerate(runs):
        whole_plots.setdefault(run.whole_plot_id, []).append(index)
    plot_ids = tuple(whole_plots)
    plot_means = np.asarray([
        math.fsum(float(centered[index]) for index in whole_plots[plot_id])
        / len(whole_plots[plot_id]) for plot_id in plot_ids
    ])
    plot_blocks = [runs[whole_plots[plot_id][0]].block for plot_id in plot_ids]
    plot_block_matrix = np.eye(len(blocks))[[block_index[block] for block in plot_blocks]]
    plot_coded = np.asarray([
        [int(factor_by_id[factor_id].to_coded(
            runs[whole_plots[plot_id][0]].settings[factor_id]))
         for factor_id in factor_ids]
        for plot_id in plot_ids
    ], dtype=float)
    hard_subsets = [subset for subset in subsets
                    if set(factor_ids[index] for index in subset) <= set(hard_ids)]
    hard_matrix = np.column_stack([
        np.prod(plot_coded[:, subset], axis=1) for subset in hard_subsets
    ])
    plot_model = np.column_stack((plot_block_matrix, hard_matrix))
    wp_rank = int(np.linalg.matrix_rank(plot_model))
    expected_wp_rank = len(blocks) + hard_count - 1
    if wp_rank != expected_wp_rank:
        raise ValueError(f"整区模型矩阵秩亏：rank={wp_rank}，期望 {expected_wp_rank}；F/p 不可用")
    plot_count = len(plot_ids)
    if (not np.array_equal(plot_block_matrix.T @ hard_matrix,
                           np.zeros((len(blocks), len(hard_subsets))))
            or not np.array_equal(hard_matrix.T @ hard_matrix,
                                  np.eye(len(hard_subsets)) * plot_count)):
        raise ValueError("整区因子对比矩阵不正交；F/p 不可用")
    plot_block_rows = [np.flatnonzero(plot_block_matrix[:, index])
                       for index in range(len(blocks))]
    plot_block_coefficients = np.asarray([
        math.fsum(float(plot_means[index]) for index in indices) / len(indices)
        for indices in plot_block_rows
    ])
    hard_coefficients = np.asarray([
        math.fsum(float(hard_matrix[row, column] * plot_means[row])
                  for row in range(plot_count)) / plot_count
        for column in range(len(hard_subsets))
    ])
    wp_residual_by_plot = np.asarray([
        plot_means[row] - math.fsum(
            [float(plot_block_coefficients[block_index[plot_blocks[row]]])]
            + [float(hard_matrix[row, column] * hard_coefficients[column])
               for column in range(len(hard_subsets))])
        for row in range(plot_count)
    ])
    wp_residual_map = dict(zip(plot_ids, wp_residual_by_plot))
    whole_plot_residual = np.asarray([
        wp_residual_map[run.whole_plot_id] for run in runs
    ])
    subplot_residual = residuals - whole_plot_residual

    ss_wp = float(easy_count * (wp_residual_by_plot @ wp_residual_by_plot))
    ss_subplot = float(subplot_residual @ subplot_residual)
    df_total = n - 1
    df_block = len(blocks) - 1
    df_wp = (len(blocks) - 1) * (hard_count - 1)
    df_easy = hard_count * (easy_count - 1)
    df_subplot = hard_count * (len(blocks) - 1) * (easy_count - 1)
    df_fixed_residual = df_wp + df_subplot
    error_ss = ss_wp + ss_subplot
    closure = ss_block + sum(term_ss.values()) + error_ss
    epsilon = np.finfo(float).eps
    closure_tolerance = 256 * epsilon * max(n, model_rank) * ss_total
    roundoff_per_run = 4 * epsilon * float(np.max(np.abs(centered)))
    zero_ss_tolerance = n * roundoff_per_run * roundoff_per_run
    if not np.isfinite([grand, ss_total, ss_block, ss_wp, ss_subplot,
                        closure, *term_ss.values()]).all():
        raise ValueError("响应平方和超出可分析数值范围")
    if min(ss_total, ss_block, ss_wp, ss_subplot, *term_ss.values()) < -closure_tolerance:
        raise ValueError("裂区平方和出现不可接受的负值")
    if abs(ss_total - closure) > closure_tolerance:
        raise ValueError("整区/子区平方和未闭合，裂区推断不可用")
    if df_total != df_block + (hard_count - 1) + df_wp + df_easy + df_subplot:
        raise ValueError("裂区自由度未闭合，推断不可用")
    if not np.allclose(residuals, whole_plot_residual + subplot_residual,
                       rtol=0, atol=np.sqrt(closure_tolerance)):
        raise ValueError("两层残差贡献未闭合，裂区推断不可用")

    error_strata = {}
    for name, ss, df in (("whole_plot_error", ss_wp, df_wp),
                         ("subplot_error", ss_subplot, df_subplot)):
        mse = ss / df if df > 0 else None
        available = (df > 0 and mse is not None and np.isfinite(mse)
                     and ss > zero_ss_tolerance)
        if df <= 0:
            reason = "误差层自由度为零"
        elif not np.isfinite(ss) or not np.isfinite(mse):
            reason = "误差层方差非有限"
        elif ss <= zero_ss_tolerance:
            reason = "误差层平方和在数值容差内为零"
        else:
            reason = None
        error_strata[name] = {
            "ss": ss, "df": df, "ms": mse if available else None,
            "available": available, "reason": reason,
        }

    anova = [{"term": "block", "coefficient": None, "effect": None,
              "ss": ss_block, "df": df_block,
              "ms": ss_block / df_block if df_block else None,
              "f": None, "p": None, "error_stratum": None,
              "inference_available": False, "inference_reason": "固定区组调整项"}]

    def term_row(name, index):
        hard_only = set(factors[j].factor_id for j in subsets[index]) <= set(hard_ids)
        stratum = "whole_plot_error" if hard_only else "subplot_error"
        error = error_strata[stratum]
        ss = term_ss[name]
        f_value = p_value = None
        reason = error["reason"]
        if error["available"]:
            f_value = ss / error["ms"]
            if np.isfinite(f_value):
                p_value = float(stats.f.sf(f_value, 1, error["df"]))
            else:
                f_value = None
                reason = "F 统计量非有限"
        return {
            "term": name, "coefficient": float(term_coefficients[index]),
            "effect": float(2 * term_coefficients[index]),
            "ss": ss, "df": 1, "ms": ss, "f": f_value, "p": p_value,
            "error_stratum": stratum,
            "error_df": error["df"],
            "inference_available": f_value is not None and p_value is not None,
            "inference_reason": reason,
        }

    hard_indices = [index for index, subset in enumerate(subsets)
                    if set(factor_ids[j] for j in subset) <= set(hard_ids)]
    easy_indices = [index for index, subset in enumerate(subsets)
                    if not set(factor_ids[j] for j in subset) <= set(hard_ids)]
    anova.extend(term_row(term_names[index], index) for index in hard_indices)
    anova.append({"term": "whole_plot_error", "coefficient": None, "effect": None,
                  **error_strata["whole_plot_error"], "f": None, "p": None,
                  "error_stratum": "whole_plot_error",
                  "inference_available": error_strata["whole_plot_error"]["available"],
                  "inference_reason": error_strata["whole_plot_error"]["reason"]})
    anova.extend(term_row(term_names[index], index) for index in easy_indices)
    anova.append({"term": "subplot_error", "coefficient": None, "effect": None,
                  **error_strata["subplot_error"], "f": None, "p": None,
                  "error_stratum": "subplot_error",
                  "inference_available": error_strata["subplot_error"]["available"],
                  "inference_reason": error_strata["subplot_error"]["reason"]})
    anova.append({"term": "total", "coefficient": None, "effect": None,
                  "ss": ss_total, "df": df_total, "ms": None, "f": None,
                  "p": None, "error_stratum": None,
                  "inference_available": False, "inference_reason": None})

    status = "；".join(
        f"{label}{'可用' if item['available'] else '不可用：' + item['reason']}"
        for label, item in (("整区误差", error_strata["whole_plot_error"]),
                            ("子区误差", error_strata["subplot_error"]))
    )
    return {
        "design": design, "response": response, "n": n,
        "p": expected_rank, "rank": model_rank, "df": df_fixed_residual,
        "sse": error_ss, "sst": ss_total,
        "anova": anova, "error_strata": error_strata,
        "fitted": fitted, "residuals": residuals,
        "whole_plot_residual_contribution": whole_plot_residual,
        "subplot_residual_contribution": subplot_residual,
        "status": status,
        "assumption": ("完整平衡两水平裂区模型；区组为固定效应；整区相互独立；"
                       "两层误差分别正态且方差齐性；整体残差图不检验两层误差假设。"),
    }
