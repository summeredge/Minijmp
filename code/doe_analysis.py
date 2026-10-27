"""两水平全因子线性模型；工作表摘要验证由 DOE-0 负责。"""
from collections import Counter
from itertools import combinations, product

import numpy as np
from scipy import stats

from doe_core import restore_design_result


def analyze_factorial(frame, metadata, response, order=2):
    """拟合层级完整的指定阶次模型；中心点单独设截距偏移。"""
    result = restore_design_result(frame, metadata)
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
        if run.block is not None:
            raise ValueError('区组效应未实现，不能分析带区组的设计')
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
    cells = {}
    for levels, run, value in zip(coded, runs, y):
        cells.setdefault(levels, []).append(value)
    pure_df = sum(len(cell) - 1 for cell in cells.values())
    pure_sse = 0.0
    for cell in cells.values():
        deviations = np.asarray(cell) - np.mean(cell)
        pure_sse += float(deviations @ deviations)
    lack_of_fit_sse = max(0.0, sse - pure_sse)
    lack_of_fit_df = df - pure_df
    tolerance = np.finfo(float).eps * max(n, p) * max(float(np.linalg.norm(y)), 1.0)
    names = ['截距' if not term else '*'.join(spec.factors[i].factor_id for i in term)
             for term in terms] + (['中心点偏移'] if has_center else [])
    effects = [None] + [2 * float(v) for v in beta[1:len(terms)]]
    if has_center:
        effects.append(None)
    inference = None
    status = '残差自由度不足，不能进行统计推断' if df == 0 else '可推断'
    if has_center:
        status = '含中心点设计的模型统计推断尚未实现'
    elif not pure_df:
        status = ('残差自由度不足，不能进行统计推断' if df == 0 else
                  '无独立纯误差，剩余项可能是未拟合交互，不能进行统计推断')
    elif pure_sse ** .5 > tolerance:
        mse = sse / df
        se = np.sqrt(np.diag(np.linalg.inv(x.T @ x)) * mse)
        t = beta / se
        critical = stats.t.ppf(.975, df)
        f = (ssr / (p - 1)) / mse
        inference = {'mse': mse, 'se': se, 't': t, 'p': 2 * stats.t.sf(abs(t), df),
                     'ci_low': beta - critical * se, 'ci_high': beta + critical * se,
                     'f': float(f), 'model_p': float(stats.f.sf(f, p - 1, df))}
    elif df > 0:
        status = '纯误差方差为零或无法辨认，统计推断不可用'
    pure_mse = pure_sse / pure_df if pure_df else None
    error_available = pure_df > 0 and pure_sse ** .5 > tolerance
    lack_of_fit = None
    if error_available and lack_of_fit_df > 0:
        f_lof = (lack_of_fit_sse / lack_of_fit_df) / pure_mse
        lack_of_fit = {'f': float(f_lof),
                       'p': float(stats.f.sf(f_lof, lack_of_fit_df, pure_df))}
    curvature = None
    if has_center:
        factorial_y = [value for run, value in zip(runs, y) if run.point_type == 'factorial']
        center_y = [value for run, value in zip(runs, y) if run.point_type == 'center']
        difference = float(np.mean(center_y) - np.mean(factorial_y))
        contrast_ss = difference ** 2 / (1 / len(center_y) + 1 / len(factorial_y))
        curvature = {'difference': difference, 'ss': contrast_ss, 'df': 1,
                     'f': None, 'p': None}
        if error_available:
            f_curvature = contrast_ss / pure_mse
            curvature.update(f=float(f_curvature),
                             p=float(stats.f.sf(f_curvature, 1, pure_df)))
    return {'design': result, 'response': response, 'order': order, 'names': names,
            'coefficients': beta, 'effects': effects, 'fitted': fitted,
            'residuals': residuals, 'n': n, 'p': p, 'rank': int(rank), 'df': df,
            'sse': sse, 'sst': sst, 'ssr': ssr,
            'pure_error_df': pure_df, 'pure_error_sse': pure_sse,
            'lack_of_fit_df': lack_of_fit_df, 'lack_of_fit_sse': lack_of_fit_sse,
            'lack_of_fit': lack_of_fit, 'curvature': curvature,
            'r2': 1 - sse / sst if sst > 0 else None,
            'adjusted_r2': 1 - (sse / df) / (sst / (n - 1)) if df > 0 and sst > 0 else None,
            'inference': inference, 'status': status,
            'assumption': '重复须为独立运行；推断假设误差独立、同方差且正态；OLS 推断还假设模型充分',
            'coded': np.asarray(coded, dtype=float)}
