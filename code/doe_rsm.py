"""完整二次响应面模型，以编码因子拟合。"""
from itertools import combinations

import numpy as np
from scipy import stats

from doe_core import restore_design_result


def model_matrix(coded):
    coded = np.asarray(coded, dtype=float)
    k = coded.shape[1]
    return np.column_stack([np.ones(len(coded)), coded, coded**2] +
                           [coded[:, i]*coded[:, j] for i, j in combinations(range(k), 2)])


def analyze_rsm(frame, metadata, response):
    design = restore_design_result(frame, metadata)
    spec, runs = design.spec, design.runs
    if spec.design_type != 'central_composite' or spec.ccd_alpha is None:
        raise ValueError('仅支持完整的中心复合设计')
    coded = frame[[f'编码_{factor.factor_id}' for factor in spec.factors]].to_numpy(dtype=float)
    if response not in spec.response_names:
        raise ValueError('响应不属于该设计')
    values = [run.responses[response] for run in runs]
    if any(value is None for value in values):
        raise ValueError('响应存在缺失值')
    try:
        y = np.asarray(values, dtype=float)
    except (ValueError, OverflowError) as exc:
        raise ValueError('响应超出可分析数值范围') from exc
    if not np.isfinite(y).all() or any(isinstance(v, int) and int(x) != v for v, x in zip(values, y)):
        raise ValueError('响应必须为可无损表示的有限数值')
    x = model_matrix(coded)
    u, singular, vt = np.linalg.svd(x, full_matrices=False)
    n, p = x.shape
    if len(singular) != p or singular[-1] <= singular[0] * np.finfo(float).eps * max(n, p):
        raise ValueError('设计矩阵秩亏')
    condition = singular[0] / singular[-1]
    if condition > 1e10:
        raise ValueError('设计矩阵病态')
    beta = vt.T @ ((u.T @ y) / singular)
    fitted = x @ beta
    residuals = y - fitted
    sse = float(residuals @ residuals)
    sst = float(np.sum((y - y.mean())**2))
    if not np.isfinite(beta).all() or not np.isfinite([sse, sst]).all():
        raise ValueError('响应超出可分析数值范围')
    ssr = max(0., sst-sse)
    df = n-p
    cells = {}
    for row, value in zip(coded, y):
        cells.setdefault(tuple(row), []).append(value)
    pure_df = sum(len(cell)-1 for cell in cells.values())
    pure_sse = sum(float(np.sum((np.asarray(cell)-np.mean(cell))**2)) for cell in cells.values())
    lof_df = df-pure_df
    lof_sse = max(0., sse-pure_sse)
    tol = np.finfo(float).eps * max(n, p) * max(float(np.linalg.norm(y)), 1.)
    error_available = pure_df > 0 and np.sqrt(pure_sse) > tol
    inference = None
    if df > 0 and error_available:
        mse = sse/df
        se = np.sqrt(np.sum((vt.T / singular)**2, axis=1)*mse)
        t = beta/se
        critical = stats.t.ppf(.975, df)
        f = (ssr/(p-1))/mse
        inference = {'mse': mse, 'se': se, 't': t, 'p': 2*stats.t.sf(abs(t), df),
                     'ci_low': beta-critical*se, 'ci_high': beta+critical*se,
                     'f': float(f), 'model_p': float(stats.f.sf(f, p-1, df))}
    lof = None
    if error_available and lof_df > 0:
        f = (lof_sse/lof_df)/(pure_sse/pure_df)
        lof = {'f': float(f), 'p': float(stats.f.sf(f, lof_df, pure_df))}
    center = [v for run, v in zip(runs, y) if run.point_type == 'center']
    factorial = [v for run, v in zip(runs, y) if run.point_type == 'factorial']
    curvature = None
    if center:
        difference = float(np.mean(center)-np.mean(factorial))
        ss = difference**2/(1/len(center)+1/len(factorial))
        curvature = {'difference': difference, 'ss': ss, 'df': 1, 'f': None, 'p': None}
        if error_available:
            f = ss/(pure_sse/pure_df)
            curvature.update(f=float(f), p=float(stats.f.sf(f, 1, pure_df)))
    ids = [f.factor_id for f in spec.factors]
    names = ['截距'] + ids + [f'{i}²' for i in ids] + [f'{ids[i]}*{ids[j]}' for i, j in combinations(range(len(ids)), 2)]
    return {'design': design, 'response': response, 'names': names, 'coefficients': beta,
            'effects': [None]*p, 'coded': coded, 'fitted': fitted, 'residuals': residuals,
            'n': n, 'p': p, 'rank': p, 'condition': condition, 'df': df,
            'sse': sse, 'sst': sst, 'ssr': ssr, 'pure_error_df': pure_df,
            'pure_error_sse': pure_sse, 'lack_of_fit_df': lof_df, 'lack_of_fit_sse': lof_sse,
            'lack_of_fit': lof, 'curvature': curvature,
            'r2': 1-sse/sst if sst > 0 else None,
            'adjusted_r2': 1-(sse/df)/(sst/(n-1)) if df > 0 and sst > 0 else None,
            'inference': inference, 'status': '可推断' if inference else '纯误差或残差自由度不足，统计推断不可用',
            'assumption': '独立重复；推断假设误差独立、同方差且正态，模型充分'}
