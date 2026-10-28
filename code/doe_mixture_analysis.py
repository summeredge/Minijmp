"""Scheffé 混料最小二乘、ANOVA 与推断可用性。"""
from __future__ import annotations

import hashlib
import json
import math

import numpy as np
from scipy import stats

from doe_mixture import MixtureSpec, input_fingerprint, mixture_rows, restore_mixture
from doe_mixture_constraints import MixtureConstraintError, TOLERANCE
from doe_mixture_model import MixtureTermModel, is_component_main


def _spec_rows(frame, metadata, response):
    if isinstance(metadata, MixtureSpec):
        spec = metadata
        rows = mixture_rows(frame, spec)
    elif isinstance(metadata, dict) and 'spec' in metadata:
        spec, rows = restore_mixture(frame, metadata)
    else:
        raise MixtureConstraintError('需要混料设计元数据或 MixtureSpec')
    column = f'响应_{response}'
    if response not in spec.response_names:
        raise MixtureConstraintError('响应不属于该混料设计')
    values = []
    for item in rows:
        value = item['row'][column]
        if value is None or (isinstance(value, float) and not math.isfinite(value)) \
                or isinstance(value, bool) or not isinstance(value, (int, float)):
            raise MixtureConstraintError(f'响应 {response} 存在缺失或非有限值')
        values.append(float(value))
    return spec, rows, np.asarray(values, dtype=float)


def _group_key(item, frame, block_column):
    key = tuple(round(value, 12) for value in item['settings'].values())
    if block_column is not None:
        key += (item['row'][block_column],)
    return key


def analyze_mixture(frame, metadata, response, terms=None, degree=2):
    """拟合当前响应；秩亏时给出最小范数解并禁用推断。"""
    spec, rows, y = _spec_rows(frame, metadata, response)
    model = MixtureTermModel(spec, terms, degree)
    x = model.matrix([item['settings'] for item in rows])
    n, p = x.shape
    u, singular, vt = np.linalg.svd(x, full_matrices=False)
    tolerance = singular[0] * np.finfo(float).eps * max(n, p)
    valid = singular > tolerance
    rank = int(valid.sum())
    inverse = np.where(valid, 1 / np.where(valid, singular, 1), 0)
    beta = vt.T @ (inverse * (u.T @ y))
    fitted = x @ beta
    residuals = y - fitted
    sse = float(residuals @ residuals)
    row_basis = vt[:rank].T
    constant = np.ones(n)
    constant_projected = u[:, :rank] @ (u[:, :rank].T @ constant)
    has_constant = np.linalg.norm(constant - constant_projected) <= 1e-8 * math.sqrt(n)
    # 含隐含截距时使用校正平方和；不含量向量时使用未校正平方和。
    if has_constant:
        sst = float(np.sum((y - y.mean()) ** 2))
        total_df = n - 1
        model_df = max(0, rank - 1)
    else:
        sst = float(y @ y)
        total_df = n
        model_df = rank
    ssr = max(0.0, sst - sse)
    df = n - rank
    estimable = []
    for column in range(p):
        vector = np.zeros(p)
        vector[column] = 1.0
        projected = row_basis @ (row_basis.T @ vector)
        estimable.append(bool(np.linalg.norm(vector - projected) <= 1e-8))
    block_column = '区组' if '区组' in frame.columns else None
    cells = {}
    for item, value in zip(rows, y):
        cells.setdefault(_group_key(item, frame, block_column), []).append(value)
    pure_df = sum(len(cell) - 1 for cell in cells.values())
    pure_sse = sum(float(np.sum((np.asarray(cell) - np.mean(cell)) ** 2))
                   for cell in cells.values())
    tol = np.finfo(float).eps * max(n, p) * max(float(np.linalg.norm(y)), 1.0)
    lof_sse = sse - pure_sse
    if lof_sse < 0:
        if -lof_sse > 2 * tol * math.sqrt(max(pure_sse, 0.0)) + tol * tol:
            raise MixtureConstraintError('纯误差平方和超过模型残差平方和')
        lof_sse = 0.0
    lof_df = df - pure_df
    inference = None
    mse = sse / df if df > 0 else None
    if (rank == p and df > 0 and pure_df > 0 and mse is not None and mse > 0
            and pure_sse > 1e-12 * max(1.0, sst)):
        try:
            covariance = np.linalg.inv(x.T @ x) * mse
        except np.linalg.LinAlgError:
            covariance = None
        if covariance is not None and np.isfinite(covariance).all():
            se = np.sqrt(np.maximum(np.diag(covariance), 0.0))
            t_values = beta / se
            critical = stats.t.ppf(0.975, df)
            inference = {
                'mse': mse, 'se': se, 't': t_values,
                'p': 2 * stats.t.sf(np.abs(t_values), df),
                'ci_low': beta - critical * se, 'ci_high': beta + critical * se,
                'model_df': model_df,
                'f': float((ssr / model_df) / mse) if model_df > 0 else None,
                'model_p': (float(stats.f.sf((ssr / model_df) / mse, model_df, df))
                            if model_df > 0 else None),
            }
            for index, term in enumerate(model.terms):
                if is_component_main(term, model):
                    inference['p'][index] = None
    lof = None
    if inference is not None and lof_df > 0 and pure_sse > 0:
        value = (lof_sse / lof_df) / (pure_sse / pure_df)
        lof = {'f': float(value), 'p': float(stats.f.sf(value, lof_df, pure_df))}
    anova = []
    for index, term in enumerate(model.terms):
        reduced = np.delete(x, index, axis=1)
        if reduced.shape[1]:
            reduced_beta = np.linalg.lstsq(reduced, y, rcond=None)[0]
            sums = float(np.sum((y - reduced @ reduced_beta) ** 2) - sse)
        else:
            sums = ssr
        sums = max(0.0, sums)
        estimate = sums
        component_main = is_component_main(term, model)
        f_value = p_value = None
        if inference is not None and mse > 0 and not component_main:
            f_value = estimate / mse
            p_value = float(stats.f.sf(f_value, 1, df))
        anova.append({'source': term, 'ss': sums, 'df': 1, 'ms': estimate,
                      'f': f_value, 'p': p_value, 'component_main': component_main,
                      'interpretation': ('删除项条件平方和；混料组分相互依赖，'
                                         '不报告独立主效应 F/p' if component_main
                                         else '删除项条件检验')})
    snapshot = hashlib.sha256(json.dumps({
        'input': input_fingerprint(frame, spec), 'response': response,
        'values': list(y), 'terms': list(model.terms), 'degree': degree,
    }, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()[:16]
    if rank < p:
        status = f'模型秩亏（秩 {rank}，项数 {p}），系数与 F/p 不可靠'
    elif df <= 0:
        status = '模型饱和，残差自由度为 0，统计推断不可用'
    elif inference is None:
        status = '纯误差不足或残差方差为零，统计推断不可用'
    else:
        status = '可推断（混料组分主效应不报告 p 值）'
    return {
        'spec': spec, 'design': spec, 'response': response, 'model': model,
        'term_model': model, 'terms': model.terms, 'names': model.names,
        'coefficients': beta, 'fitted': fitted, 'residuals': residuals,
        'n': n, 'p': p, 'rank': rank, 'df': df, 'sse': sse, 'sst': sst,
        'has_constant': bool(has_constant), 'total_df': total_df,
        'model_df': model_df, 'row_space': row_basis,
        'ssr': ssr, 'pure_error_df': pure_df, 'pure_error_sse': pure_sse,
        'lack_of_fit_df': lof_df, 'lack_of_fit_sse': lof_sse,
        'lack_of_fit': lof, 'inference': inference, 'anova': anova,
        'estimable': estimable, 'rows': rows, 'settings': [item['settings'] for item in rows],
        'r2': 1 - sse / sst if sst > 0 else None,
        'adjusted_r2': (1 - (sse / df) / (sst / total_df)
                        if df > 0 and sst > 0 and total_df > 0 else None),
        'status': status,
        'assumption': '组分为比例且总和为 1；推断假设独立重复、误差独立同方差且正态，模型充分。',
        'snapshot_id': snapshot,
    }


def contrast_estimable(result, weights):
    """单位系数向量或线性对比是否位于 X 的行空间。"""
    weights = np.asarray(weights, dtype=float)
    if weights.shape != (len(result['names']),) or not np.isfinite(weights).all():
        raise MixtureConstraintError('对比权重必须与模型项一一对应且为有限数值')
    basis = result['row_space']
    projected = basis @ (basis.T @ weights)
    return bool(np.linalg.norm(weights - projected) <= 1e-8 * max(1.0, np.linalg.norm(weights)))
