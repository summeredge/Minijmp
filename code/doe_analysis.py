"""两水平全因子线性模型；工作表摘要验证由 DOE-0 负责。"""
from collections import Counter
from itertools import combinations, product

import numpy as np
from scipy import stats

from doe_factorial import validate_factorial_design
from doe_factorial_anova import partition_factorial_error


def analyze_factorial(frame, metadata, response, order=2):
    """拟合层级完整的指定阶次模型；中心点单独设截距偏移。"""
    result = validate_factorial_design(frame, metadata)
    spec, runs = result.spec, result.runs
    k = len(spec.factors)
    if (spec.design_type != 'two_level_full' or not 2 <= k <= 6 or
            spec.generators or spec.defining_relations or spec.aliases or
            any(x is not None for x in (spec.ccd_alpha, spec.ccd_center_points,
                                         spec.ccd_axial_points))):
        raise ValueError('仅支持 2 至 6 因子的两水平全因子设计')
    if response not in spec.response_names:
        raise ValueError('响应不属于该设计')
    if isinstance(order, bool) or not isinstance(order, int) or not 1 <= order <= k:
        raise ValueError('模型阶次无效')
    coded, groups, has_center = [], {}, False
    for run in runs:
        levels = tuple(f.to_coded(run.settings[f.factor_id]) for f in spec.factors)
        if run.point_type == 'factorial':
            if any(x not in (-1, 1) for x in levels):
                raise ValueError('因子点必须恰为低或高水平')
            groups.setdefault(run.replicate, []).append(levels)
        elif run.point_type == 'center':
            if any(x != 0 for x in levels):
                raise ValueError('中心点必须位于所有因子的中点')
            has_center = True
        else:
            raise ValueError('全因子设计不能包含轴点')
        if run.responses[response] is None:
            raise ValueError('响应存在缺失值，请填写全部运行的响应')
        coded.append(levels)
    expected = Counter(product((-1, 1), repeat=k))
    if not groups or any(Counter(group) != expected for group in groups.values()):
        raise ValueError('每次重复必须包含且仅包含全部两水平组合')
    if set(groups) != set(range(1, len(groups) + 1)):
        raise ValueError('重复编号必须连续且从 1 开始')

    terms = [()] + [term for degree in range(1, order + 1)
                    for term in combinations(range(k), degree)]
    x = np.array([[1.0 if not term else np.prod([row[i] for i in term])
                   for term in terms] + ([1.0 if run.point_type == 'center' else 0.0]
                                         if has_center else [])
                  for row, run in zip(coded, runs)], dtype=float)
    block_levels = list(dict.fromkeys(run.block for run in runs if run.block is not None))
    block_df = max(0, len(block_levels) - 1)
    block_basis = (np.column_stack([[1.0 if run.block == block else 0.0 for run in runs]
                                    for block in block_levels[:-1]])
                   if len(block_levels) > 1 else np.empty((len(runs), 0)))
    if block_basis.shape[1]:
        x = np.column_stack((x, block_basis))
    values = [run.responses[response] for run in runs]
    try:
        y = np.array(values, dtype=float)
    except (ValueError, OverflowError) as exc:
        raise ValueError('响应超出可分析的数值范围') from exc
    if not np.isfinite(y).all():
        raise ValueError('响应必须是有限数值')
    if any(isinstance(value, int) and int(converted) != value
           for value, converted in zip(values, y)):
        raise ValueError('整数响应不能无损表示为浮点数')
    beta, _, rank, _ = np.linalg.lstsq(x, y, rcond=None)
    n, p = x.shape
    if rank != p:
        raise ValueError('设计矩阵秩亏，无法估计模型')
    fitted = x @ beta
    residuals = y - fitted
    sse = float(residuals @ residuals)
    sst = float(np.sum((y - y.mean()) ** 2))
    if not np.isfinite(beta).all() or not np.isfinite([sse, sst]).all():
        raise ValueError('响应超出可分析的数值范围')
    ssr = max(0.0, sst - sse)
    df = n - p
    treatment_cells = [tuple(row) for row in coded]
    error = partition_factorial_error(
        y, treatment_cells, [run.block for run in runs] if len(block_levels) > 1 else None)
    pure_df, pure_sse = error['pure_error_df'], error['pure_error_ss']
    block_error_df, block_error_sse = error['block_error_df'], error['block_error_ss']
    full_treatment_df = len(set(treatment_cells)) - 1
    model_treatment_df = len(terms) - 1 + int(has_center)
    lack_of_fit_df = full_treatment_df - model_treatment_df
    lack_of_fit_sse = max(0.0, sse - pure_sse - block_error_sse)
    ss_tolerance = np.finfo(float).eps * max(n, p) * max(float(y @ y), 1.0)
    if df != pure_df + block_error_df + lack_of_fit_df:
        raise ValueError('残差自由度无法分解为纯误差、区组误差和失拟')
    names = ['截距' if not term else '*'.join(spec.factors[i].factor_id for i in term)
             for term in terms] + (['中心点偏移'] if has_center else [])
    block_names = [f'区组 {block}' for block in block_levels[:-1]]
    names.extend(block_names)
    effects = ([None] + [2 * float(v) for v in beta[1:len(terms)]]
               + ([None] if has_center else []) + [None] * len(block_names))
    pure_error_available = pure_df > 0 and pure_sse > ss_tolerance
    error_available = (df > 0 and lack_of_fit_df == 0 and sse > ss_tolerance
                       if block_df else df > 0 and pure_error_available)
    inference = None
    if df == 0:
        status = '残差自由度不足，不能进行统计推断'
    elif block_df and lack_of_fit_df:
        status = '区组模型未包含全部处理组合自由度，不能分离失拟与区组误差'
    elif not error_available:
        status = ('区组调整误差自由度或方差不可用，统计推断不可用' if block_df else
                  '无独立纯误差自由度或方差，统计推断不可用')
    else:
        mse = sse / df
        se = np.sqrt(np.diag(np.linalg.inv(x.T @ x)) * mse)
        t = beta / se
        critical = stats.t.ppf(.975, df)
        f = (ssr / (p - 1)) / mse
        inference = {'mse': mse, 'se': se, 't': t, 'p': 2 * stats.t.sf(abs(t), df),
                     'ci_low': beta - critical * se, 'ci_high': beta + critical * se,
                     'f': float(f), 'model_p': float(stats.f.sf(f, p - 1, df))}
        status = '可推断；含区组时使用区组调整残差，假设模型充分且无处理×区组交互'
    pure_mse = pure_sse / pure_df if pure_df else None
    lack_of_fit = None
    if not block_df and pure_error_available and lack_of_fit_df > 0:
        f_lof = (lack_of_fit_sse / lack_of_fit_df) / pure_mse
        lack_of_fit = {'ss': lack_of_fit_sse, 'df': lack_of_fit_df,
                       'pure_error_ss': pure_sse, 'pure_error_df': pure_df,
                       'f': float(f_lof),
                       'p': float(stats.f.sf(f_lof, lack_of_fit_df, pure_df))}
    curvature = None
    if has_center:
        factorial_y = [value for run, value in zip(runs, y) if run.point_type == 'factorial']
        center_y = [value for run, value in zip(runs, y) if run.point_type == 'center']
        difference = float(np.mean(center_y) - np.mean(factorial_y))
        contrast_ss = difference ** 2 / (1 / len(center_y) + 1 / len(factorial_y))
        curvature = {'difference': difference, 'ss': contrast_ss, 'df': 1,
                     'f': None, 'p': None}
        if pure_error_available and not block_df:
            f_curvature = contrast_ss / pure_mse
            curvature.update(f=float(f_curvature),
                             p=float(stats.f.sf(f_curvature, 1, pure_df)))
    block_values = {block: [value for run, value in zip(runs, y) if run.block == block]
                    for block in block_levels}
    block_ss = (sum(len(values) * (float(np.mean(values)) - float(np.mean(y))) ** 2
                    for values in block_values.values()) if block_df else 0.0)
    mse = sse / df if error_available else None
    anova = []
    if block_df:
        block_ms = block_ss / block_df
        block_f = block_ms / mse if mse is not None else None
        anova.append({'term': '区组', 'ss': block_ss, 'df': block_df, 'ms': block_ms,
                      'f': block_f,
                      'p': float(stats.f.sf(block_f, block_df, df)) if block_f is not None else None})
    for index, term in enumerate(terms[1:], start=1):
        term_ss = float(beta[index] ** 2 * (x[:, index] @ x[:, index]))
        term_f = term_ss / mse if mse is not None else None
        anova.append({'term': '*'.join(spec.factors[i].factor_id for i in term),
                      'ss': term_ss, 'df': 1, 'ms': term_ss, 'f': term_f,
                      'p': float(stats.f.sf(term_f, 1, df)) if term_f is not None else None})
    if curvature:
        term_f = curvature['ss'] / mse if mse is not None else None
        anova.append({'term': '中心点偏移', 'ss': curvature['ss'], 'df': 1,
                      'ms': curvature['ss'], 'f': term_f,
                      'p': float(stats.f.sf(term_f, 1, df)) if term_f is not None else None})
    anova.extend([
        {'term': '残差', 'ss': sse, 'df': df, 'ms': mse, 'f': None, 'p': None},
        {'term': '总计', 'ss': sst, 'df': n - 1, 'ms': None, 'f': None, 'p': None},
    ])
    return {'design': result, 'response': response, 'order': order, 'names': names,
            'coefficients': beta, 'effects': effects, 'fitted': fitted,
            'residuals': residuals, 'n': n, 'p': p, 'rank': int(rank), 'df': df,
            'block_ss': block_ss, 'block_df': block_df,
            'block_ms': block_ss / block_df if block_df else None,
            'block_names': block_names,
            'block_error_sse': block_error_sse, 'block_error_df': block_error_df,
            'block_error_ms': block_error_sse / block_error_df if block_error_df else None,
            'sse': sse, 'sst': sst, 'ssr': ssr,
            'pure_error_df': pure_df, 'pure_error_sse': pure_sse,
            'lack_of_fit_df': lack_of_fit_df, 'lack_of_fit_sse': lack_of_fit_sse,
            'lack_of_fit': lack_of_fit, 'curvature': curvature, 'anova': anova,
            'r2': 1 - sse / sst if sst > 0 else None,
            'adjusted_r2': 1 - (sse / df) / (sst / (n - 1)) if df > 0 and sst > 0 else None,
            'inference': inference, 'status': status,
            'assumption': ('纯误差按相同因子设置及相同区组分组；区组模型使用区组调整残差，'
                           '并假设模型充分、无处理×区组交互；推断还假设误差独立、同方差且正态'),
            'coded': np.asarray(coded, dtype=float)}
