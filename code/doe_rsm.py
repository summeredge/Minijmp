"""响应面分析：CCD/Box-Behnken 共用二次模型拟合，设计校验各自独立。"""
from itertools import combinations

import numpy as np
from scipy import stats

from doe_core import restore_design_result
from doe_rsm_model import TermModel


def model_matrix(coded):
    """完整二次模型矩阵（无区组、无分类项）；保留供旧调用兼容。"""
    coded = np.asarray(coded, dtype=float)
    k = coded.shape[1]
    return np.column_stack([np.ones(len(coded)), coded, coded**2] +
                           [coded[:, i]*coded[:, j]
                            for i, j in combinations(range(k), 2)])


def validate_design(result):
    """按设计类型分派到各自校验，返回标准序编码矩阵。"""
    design_type = result.spec.design_type
    if design_type == 'central_composite':
        from doe_ccd import validate_ccd
        return np.asarray(validate_ccd(result), dtype=float)
    if design_type == 'box_behnken':
        from doe_bbd import validate_bbd
        return np.asarray(validate_bbd(result), dtype=float)
    raise ValueError('仅支持中心复合设计或 Box-Behnken 设计')


def _coded_rows(frame, design):
    """读取工作表中的编码列，核对顺序与设计校验结果一致。"""
    factors = [factor for factor in design.spec.factors
               if factor.factor_type == 'continuous']
    columns = [f'编码_{factor.factor_id}' for factor in factors]
    missing = [name for name in columns
               if name not in frame.columns or list(frame.columns).count(name) != 1]
    if missing:
        raise ValueError('编码水平列缺失或重复：' + '、'.join(missing))
    try:
        values = frame[columns].to_numpy(dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError('编码水平必须是有限数值') from exc
    if len(values) != len(design.runs) or not np.isfinite(values).all():
        raise ValueError('编码水平行数或数值无效')
    expected = validate_design(design)
    if not np.allclose(values, expected, rtol=0, atol=1e-12):
        raise ValueError('编码水平与实际设定不一致')
    return values


def analyze_rsm(frame, metadata, response, terms=None, use_blocks=True):
    """拟合当前响应面模型。

    terms 为用户选择的模型项；None 表示完整二次模型。use_blocks=False 时
    不纳入区组效应（仅用于对照，不作为推荐输出）。
    """
    design = restore_design_result(frame, metadata)
    spec, runs = design.spec, design.runs
    if not isinstance(use_blocks, bool):
        raise ValueError('use_blocks 必须是布尔值')
    coded = _coded_rows(frame, design)
    if response not in spec.response_names:
        raise ValueError('响应不属于该设计')
    values = [run.responses[response] for run in runs]
    if any(value is None for value in values):
        raise ValueError('响应存在缺失值')
    try:
        y = np.asarray(values, dtype=float)
    except (ValueError, OverflowError) as exc:
        raise ValueError('响应超出可分析数值范围') from exc
    if not np.isfinite(y).all() or any(
            isinstance(v, int) and int(x) != v for v, x in zip(values, y)):
        raise ValueError('响应必须为可无损表示的有限数值')

    blocks = sorted({run.block for run in runs if run.block is not None})
    if any(run.block is None for run in runs) and blocks:
        raise ValueError('区组列存在部分缺失')
    if not use_blocks:
        blocks = []
    block_index = {value: i + 1 for i, value in enumerate(blocks)}
    model = TermModel(spec.factors, terms, blocks=len(blocks))
    settings = []
    for row, run in enumerate(runs):
        row_settings = {factor.factor_id: coded[row, i]
                        for i, factor in enumerate(
                            [f for f in spec.factors
                             if f.factor_type == 'continuous'])}
        row_settings.update({factor.factor_id: run.settings[factor.factor_id]
                             for factor in spec.factors
                             if factor.factor_type == 'categorical'})
        settings.append(row_settings)
    if terms is None and model.blocks <= 1 and not model.categorical():
        # 无区组、无分类因子的完整二次模型沿用历史矩阵入口。
        x = model_matrix(coded)
    else:
        x = model.matrix(settings, [block_index[run.block] if blocks and run.block is not None
                                    else None for run in runs])
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
    categorical = [f.factor_id for f in spec.factors if f.factor_type == 'categorical']
    for row, value, run in zip(coded, y, runs):
        key = (tuple(row), tuple(run.settings[name] for name in categorical), run.block)
        cells.setdefault(key, []).append(value)
    pure_df = sum(len(cell)-1 for cell in cells.values())
    pure_sse = sum(float(np.sum((np.asarray(cell)-np.mean(cell))**2)) for cell in cells.values())
    lof_df = df-pure_df
    tol = np.finfo(float).eps * max(n, p) * max(float(np.linalg.norm(y)), 1.)
    lof_sse = sse-pure_sse
    if lof_sse < 0:
        if -lof_sse > 2*tol*np.sqrt(pure_sse) + tol**2:
            raise ValueError('纯误差平方和超过模型残差平方和')
        lof_sse = 0.
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
    # 曲率对照：CCD 用立方点，BBD 无立方点时用边点。
    reference_type = ('factorial' if any(run.point_type == 'factorial' for run in runs)
                      else 'edge')
    outer = [v for run, v in zip(runs, y) if run.point_type == reference_type]
    curvature = None
    if center and outer:
        difference = float(np.mean(center)-np.mean(outer))
        ss = difference**2/(1/len(center)+1/len(outer))
        curvature = {'difference': difference, 'ss': ss, 'df': 1, 'f': None, 'p': None}
        # 原始中心点与外点均值未调整区组效应，不能用于带区组的曲率检验。
        if error_available and len({run.block for run in runs}) <= 1:
            f = ss/(pure_sse/pure_df)
            curvature.update(f=float(f), p=float(stats.f.sf(f, 1, pure_df)))
    anova = []
    for term in model.terms:
        columns = [i for i, column in enumerate(model.columns)
                   if column[0] == term or column[0].startswith(term + '[')]
        dof, f_value, p_value = len(columns), None, None
        reduced = np.delete(x, columns, axis=1)
        if reduced.shape[1]:
            reduced_beta = np.linalg.lstsq(reduced, y, rcond=None)[0]
            sums = float(np.sum((y - reduced @ reduced_beta)**2) - sse)
        else:
            sums = max(0., sst - sse)
        estimate = sums/dof if dof else None
        if inference:
            mse = inference['mse']
            if estimate is not None and mse > 0:
                f_value = estimate/mse
                p_value = float(stats.f.sf(f_value, dof, df))
        anova.append({'source': term, 'ss': sums, 'df': dof,
                      'ms': estimate, 'f': f_value, 'p': p_value})

    return {'design': design, 'response': response, 'names': model.names,
            'terms': model.terms, 'term_model': model, 'blocks': blocks,
            'coefficients': beta, 'effects': [None]*p, 'coded': coded, 'fitted': fitted,
            'residuals': residuals, 'n': n, 'p': p, 'rank': p, 'condition': condition,
            'df': df, 'sse': sse, 'sst': sst, 'ssr': ssr, 'pure_error_df': pure_df,
            'pure_error_sse': pure_sse, 'lack_of_fit_df': lof_df, 'lack_of_fit_sse': lof_sse,
            'lack_of_fit': lof, 'curvature': curvature, 'anova': anova,
            'r2': 1-sse/sst if sst > 0 else None,
            'adjusted_r2': 1-(sse/df)/(sst/(n-1)) if df > 0 and sst > 0 else None,
            'inference': inference,
            'status': '可推断' if inference else '纯误差或残差自由度不足，统计推断不可用',
            'assumption': '独立重复；推断假设误差独立、同方差且正态，模型充分'}
