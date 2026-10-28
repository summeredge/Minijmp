"""General Full Factorial 的分类对比、边际均值和 ANOVA。"""
from collections import defaultdict
from itertools import combinations, product
from numbers import Real

import numpy as np
from scipy import stats

from doe_general_factorial import validate_general_factorial
from doe_factorial_anova import partition_factorial_error


# shortcut: dense matrices are capped at 10 million cells; use cell-mean projections if larger models are needed.
_MAX_MODEL_MATRIX_CELLS = 10_000_000


def _same_level(left, right):
    if isinstance(left, str) or isinstance(right, str):
        return isinstance(left, str) and isinstance(right, str) and left == right
    return (isinstance(left, Real) and not isinstance(left, bool)
            and isinstance(right, Real) and not isinstance(right, bool) and left == right)


def _contrast_basis(values, levels):
    base = levels[0]
    return np.column_stack([
        [1.0 if _same_level(value, level) else -1.0 if _same_level(value, base) else 0.0
         for value in values]
        for level in levels[1:]
    ])


def _fit(x, y):
    beta, _, rank, _ = np.linalg.lstsq(x, y, rcond=None)
    if rank != x.shape[1]:
        raise ValueError("模型矩阵秩亏，无法估计所选项")
    fitted = x @ beta
    residual = y - fitted
    return beta, fitted, residual, float(residual @ residual), int(rank)


def analyze_general_factorial(frame, metadata, response, order=2):
    """用 sum-to-zero 对比拟合阶次模型；数值标签始终是离散水平。"""
    design = validate_general_factorial(frame, metadata)
    spec, runs = design.spec, design.runs
    if response not in spec.response_names:
        raise ValueError("响应不属于该设计")
    k = len(spec.factors)
    if isinstance(order, bool) or not isinstance(order, int) or not 1 <= order <= k:
        raise ValueError("模型阶次无效")
    selected_terms = [term for degree in range(1, order + 1)
                      for term in combinations(range(k), degree)]
    treatment_df = sum(int(np.prod([len(spec.factors[index].levels) - 1
                                    for index in term]))
                       for term in selected_terms)
    parameter_count = 1 + max(0, (spec.block_count or 1) - 1) + treatment_df
    if len(runs) * parameter_count > _MAX_MODEL_MATRIX_CELLS:
        raise ValueError("所选模型矩阵超过 1000 万个单元，请降低模型阶次或水平数")
    values = [run.responses[response] for run in runs]
    if any(value is None for value in values):
        raise ValueError("响应存在缺失值，请填写全部运行的响应")
    try:
        y = np.asarray(values, dtype=float)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError("响应超出可分析的数值范围") from error
    if not np.isfinite(y).all() or any(
            isinstance(value, int) and int(float_value) != value
            for value, float_value in zip(values, y)):
        raise ValueError("响应必须是有限且可精确表示的数值")

    factor_values = [[run.settings[factor.factor_id] for run in runs]
                     for factor in spec.factors]
    bases = [_contrast_basis(column, factor.levels)
             for factor, column in zip(spec.factors, factor_values)]
    blocks = list(dict.fromkeys(run.block for run in runs if run.block is not None))
    block_basis = (_contrast_basis([run.block for run in runs], blocks)
                   if blocks else np.empty((len(runs), 0)))
    term_matrices = {}
    for term in selected_terms:
        columns = []
        for contrast_indices in product(*(range(bases[index].shape[1]) for index in term)):
            columns.append(np.prod(np.column_stack([
                bases[index][:, column]
                for index, column in zip(term, contrast_indices)]), axis=1))
        term_matrices[term] = np.column_stack(columns)
    groups = [("截距", np.ones((len(runs), 1)))]
    if blocks:
        groups.append(("区组", block_basis))
    groups.extend(("*".join(spec.factors[index].factor_id for index in term), matrix)
                  for term, matrix in term_matrices.items())
    x = np.column_stack([matrix for _, matrix in groups])
    beta, fitted, residuals, sse, rank = _fit(x, y)
    n, p = x.shape
    df = n - rank
    sst = float(np.sum((y - y.mean()) ** 2))
    ssr = max(0.0, sst - sse)
    cell_values = defaultdict(list)
    cell_keys = []
    for run, value in zip(runs, y):
        cell = tuple(run.settings[factor.factor_id] for factor in spec.factors)
        typed_cell = tuple(("text" if isinstance(level, str) else "numeric", level)
                           for level in cell)
        cell_keys.append(typed_cell)
        cell_values[typed_cell].append(float(value))
    cell_count = int(np.prod([len(factor.levels) for factor in spec.factors]))
    has_blocks = block_basis.shape[1] > 0
    error = partition_factorial_error(
        y, cell_keys, [run.block for run in runs] if has_blocks else None)
    pure_sse, pure_df = error['pure_error_ss'], error['pure_error_df']
    block_error_ss, block_error_df = error['block_error_ss'], error['block_error_df']
    model_treatment_df = sum(matrix.shape[1] for matrix in term_matrices.values())
    lof_df = cell_count - 1 - model_treatment_df
    lof_sse = max(0.0, sse - pure_sse - block_error_ss)
    df = n - rank
    ss_tolerance = np.finfo(float).eps * max(n, p) * max(float(y @ y), 1.0)
    if df != pure_df + block_error_df + lof_df:
        raise ValueError("残差自由度无法分解为纯误差、区组误差和失拟")
    pure_mse = pure_sse / pure_df if pure_df > 0 else None
    pure_error_available = pure_df > 0 and pure_sse > ss_tolerance
    error_available = (df > 0 and lof_df == 0 and sse > ss_tolerance
                       if has_blocks else
                       df > 0 and pure_error_available and sse > ss_tolerance)

    anova = []
    mse = sse / df if error_available else None
    cursor = 1
    if blocks:
        block_end = cursor + block_basis.shape[1]
        block_beta = beta[cursor:block_end]
        cursor = block_end
        block_ss = max(0.0, float(block_beta @ (block_basis.T @ block_basis) @ block_beta))
        block_df = block_basis.shape[1]
        anova.append({"term": "区组", "ss": block_ss, "df": block_df,
                      "ms": block_ss / block_df if block_df else None,
                      "f": block_ss / block_df / mse if mse and block_df else None,
                      "p": float(stats.f.sf(block_ss / block_df / mse, block_df, df))
                      if mse and block_df else None})
    for term, matrix in term_matrices.items():
        term_columns = slice(cursor, cursor + matrix.shape[1])
        term_beta = beta[term_columns]
        cursor = term_columns.stop
        term_ss = max(0.0, float(term_beta @ (matrix.T @ matrix) @ term_beta))
        term_df = matrix.shape[1]
        term_f = term_ss / term_df / mse if mse and term_df else None
        anova.append({"term": "*".join(spec.factors[index].factor_id for index in term),
                      "ss": term_ss, "df": term_df,
                      "ms": term_ss / term_df,
                      "f": term_f,
                      "p": float(stats.f.sf(term_f, term_df, df))
                      if term_f is not None else None})
    anova.append({"term": "误差", "ss": sse, "df": df, "ms": mse, "f": None, "p": None})
    anova.append({"term": "总计", "ss": sst, "df": n - 1, "ms": None, "f": None, "p": None})

    lack_of_fit = None
    if not has_blocks and pure_error_available and lof_df > 0:
        lof_f = (lof_sse / lof_df) / pure_mse
        lack_of_fit = {"ss": lof_sse, "df": lof_df, "ms": lof_sse / lof_df,
                       "pure_error_ss": pure_sse, "pure_error_df": pure_df,
                       "pure_error_ms": pure_mse, "f": float(lof_f),
                       "p": float(stats.f.sf(lof_f, lof_df, pure_df))}

    marginal_means = []
    for factor in spec.factors:
        for level in factor.levels:
            group = [value for run, value in zip(runs, y)
                     if _same_level(run.settings[factor.factor_id], level)]
            marginal_means.append({"factor_id": factor.factor_id,
                                   "level": level, "mean": float(np.mean(group)),
                                   "n": len(group)})
    means_by_cell = {cell: float(np.mean(observations))
                     for cell, observations in cell_values.items()}
    cell_means = []
    for values in product(*(factor.levels for factor in spec.factors)):
        key = tuple(("text" if isinstance(level, str) else "numeric", level)
                    for level in values)
        cell_means.append({"levels": dict(zip((f.factor_id for f in spec.factors), values)),
                           "mean": means_by_cell[key],
                           "n": len(cell_values[key])})

    if not error_available:
        status = ("区组模型未包含全部处理自由度，或区组调整残差误差不可用；统计显著性不可用"
                  if has_blocks else
                  "没有可用的独立纯误差自由度或残差方差，统计显著性不可用")
    else:
        status = ("可推断；模型项平方和为平衡设计的偏平方和，区组推断假设无处理×区组交互"
                  if has_blocks else "可推断；模型项平方和为平衡设计的偏平方和")
    return {
        "design": design, "response": response, "order": order,
        "names": ["截距"] + [name for name, _ in groups[1:]],
        "coefficients": beta, "fitted": fitted, "residuals": residuals,
        "n": n, "p": p, "rank": rank, "df": df,
        "sse": sse, "sst": sst, "ssr": ssr,
        "pure_error_df": pure_df, "pure_error_sse": pure_sse,
        "block_error_df": block_error_df, "block_error_sse": block_error_ss,
        "block_error_ms": block_error_ss / block_error_df if block_error_df else None,
        "lack_of_fit_df": lof_df, "lack_of_fit_sse": lof_sse,
        "lack_of_fit": lack_of_fit, "anova": anova,
        "marginal_means": marginal_means, "cell_means": cell_means,
        "ss_method": "平衡分类对比的偏平方和（等价 Type III）",
        "inference": {"mse": mse} if error_available and mse is not None else None,
        "status": status,
        "assumption": ("数值水平按分类标签编码；纯误差按相同设置及相同区组分组。"
                       "完整区组模型以区组×处理残差作误差项，并假设无处理×区组交互；"
                       "显著性还假设实验误差独立、方差同质且近似正态。"),
    }
