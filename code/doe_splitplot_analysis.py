"""平衡两水平 Split-Plot ANOVA，按整区和子区误差分层推断。"""
from itertools import product

import numpy as np
from scipy import stats

from doe_splitplot import validate_split_plot_design


def analyze_split_plot(frame, metadata, response):
    """拟合固定区组、A、B 与 A:B 的平衡裂区模型。"""
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

    hard = next(factor for factor in spec.factors
                if factor.randomization_role == "hard_to_change")
    easy = next(factor for factor in spec.factors
                if factor.randomization_role == "easy_to_change")
    rows = [(run.block, int(hard.to_coded(run.settings[hard.factor_id])),
             int(easy.to_coded(run.settings[easy.factor_id])), value)
            for run, value in zip(runs, y)]
    blocks = range(1, spec.block_count + 1)
    grand = float(y.mean())
    block_means = {block: float(np.mean([value for b, _, _, value in rows if b == block]))
                   for block in blocks}
    a_means = {a: float(np.mean([value for _, aa, _, value in rows if aa == a]))
               for a in (-1, 1)}
    b_means = {b: float(np.mean([value for _, _, bb, value in rows if bb == b]))
               for b in (-1, 1)}
    cell_means = {
        (a, b): float(np.mean([value for _, aa, bb, value in rows
                               if aa == a and bb == b]))
        for a, b in product((-1, 1), repeat=2)
    }
    whole_plot_means = {
        (block, a): float(np.mean([value for b, aa, _, value in rows
                                  if b == block and aa == a]))
        for block in blocks for a in (-1, 1)
    }

    block_count = spec.block_count
    ss_block = 4 * sum((value - grand) ** 2 for value in block_means.values())
    ss_a = 2 * block_count * sum((value - grand) ** 2 for value in a_means.values())
    ss_b = 2 * block_count * sum((value - grand) ** 2 for value in b_means.values())
    ss_ab = block_count * sum(
        (cell_means[a, b] - a_means[a] - b_means[b] + grand) ** 2
        for a, b in product((-1, 1), repeat=2))
    ss_whole_plot = 2 * sum(
        (whole_plot_means[block, a] - block_means[block] - a_means[a] + grand) ** 2
        for block in blocks for a in (-1, 1))
    fixed_residuals = np.asarray([
        value - block_means[block] - cell_means[a, b] + grand
        for block, a, b, value in rows
    ])
    whole_plot_residuals = np.asarray([
        whole_plot_means[block, a] - block_means[block] - a_means[a] + grand
        for block, a, _, _ in rows
    ])
    subplot_residuals = fixed_residuals - whole_plot_residuals
    ss_subplot = float(subplot_residuals @ subplot_residuals)
    ss_total = float(np.sum((y - grand) ** 2))
    sums = (ss_block, ss_a, ss_b, ss_ab, ss_whole_plot, ss_subplot, ss_total)
    if not np.isfinite([grand, *sums]).all():
        raise ValueError("响应超出可分析的数值范围")

    df_block = block_count - 1
    df_whole_plot = block_count - 1
    df_subplot = 2 * (block_count - 1)
    ms_whole_plot = ss_whole_plot / df_whole_plot
    ms_subplot = ss_subplot / df_subplot

    def test_statistic(ss, ms_error, df_error):
        if ms_error <= 0:
            return None, None
        f_value = ss / ms_error
        return float(f_value), float(stats.f.sf(f_value, 1, df_error))

    f_a, p_a = test_statistic(ss_a, ms_whole_plot, df_whole_plot)
    f_b, p_b = test_statistic(ss_b, ms_subplot, df_subplot)
    f_ab, p_ab = test_statistic(ss_ab, ms_subplot, df_subplot)
    anova = [
        {"term": "block", "ss": ss_block, "df": df_block,
         "ms": ss_block / df_block, "f": None, "p": None, "error_stratum": None},
        {"term": hard.factor_id, "ss": ss_a, "df": 1, "ms": ss_a,
         "f": f_a, "p": p_a, "error_stratum": "whole_plot_error"},
        {"term": "whole_plot_error", "ss": ss_whole_plot,
         "df": df_whole_plot, "ms": ms_whole_plot, "f": None, "p": None,
         "error_stratum": "whole_plot_error"},
        {"term": easy.factor_id, "ss": ss_b, "df": 1, "ms": ss_b,
         "f": f_b, "p": p_b, "error_stratum": "subplot_error"},
        {"term": f"{hard.factor_id}:{easy.factor_id}", "ss": ss_ab, "df": 1, "ms": ss_ab,
         "f": f_ab, "p": p_ab, "error_stratum": "subplot_error"},
        {"term": "subplot_error", "ss": ss_subplot,
         "df": df_subplot, "ms": ms_subplot, "f": None, "p": None,
         "error_stratum": "subplot_error"},
        {"term": "total", "ss": ss_total, "df": len(runs) - 1,
         "ms": None, "f": None, "p": None, "error_stratum": None},
    ]
    fitted = np.asarray([
        block_means[block] + cell_means[a, b] - grand
        for block, a, b, _ in rows
    ])
    residuals = y - fitted
    return {
        "design": design,
        "response": response, "n": len(runs), "anova": anova,
        "fitted": fitted, "residuals": residuals,
        "status": ("可推断；A 使用整区误差，B 和 A:B 使用子区误差"
                   if ms_whole_plot > 0 and ms_subplot > 0
                   else "至少一个误差层方差为零，相关 F/p 不可用"),
        "assumption": ("平衡随机化裂区设计；区组为固定效应；整区相互独立；"
                       "各误差层内误差正态且方差齐性。"),
    }
