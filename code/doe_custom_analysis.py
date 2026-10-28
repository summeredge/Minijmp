"""自定义设计的分析：按实际矩阵拟合，不假定标准生成结构。"""
from collections import defaultdict
from itertools import combinations

import numpy as np
from scipy import stats

from doe_core import restore_design_result
from doe_custom import coded_value, validate_custom
from doe_rsm import fit_rsm


def _values(design, response):
    spec = design.spec
    if response not in spec.response_names:
        raise ValueError('响应不属于该设计')
    values = [run.responses[response] for run in design.runs]
    if any(value is None for value in values):
        raise ValueError('响应存在缺失值，请填写全部运行的响应')
    try:
        y = np.asarray(values, dtype=float)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError('响应超出可分析的数值范围') from error
    if not np.isfinite(y).all():
        raise ValueError('响应必须是有限数值')
    return y


def _coded_matrix(design):
    spec = design.spec
    rows = []
    for run in design.runs:
        row = []
        for factor in spec.factors:
            value = run.settings[factor.factor_id]
            if factor.factor_type == 'categorical':
                row.append(-1 if value == factor.levels[0] else 1)
            else:
                row.append(float(factor.to_coded(value)))
        rows.append(row)
    return np.asarray(rows, dtype=float)


def _cells(coded):
    result = defaultdict(list)
    for index, row in enumerate(map(tuple, coded.tolist())):
        result[row].append(index)
    return result


def analyze_custom_factorial(frame, metadata, response, order=2):
    """自定义两水平设计：按实际 ±1 矩阵拟合，纯误差来自相同设定重复。"""
    design = restore_design_result(frame, metadata)
    summary = validate_custom(design)
    spec = design.spec
    k = len(spec.factors)
    if isinstance(order, bool) or not isinstance(order, int) or not 1 <= order <= k:
        raise ValueError('模型阶次无效')
    y = _values(design, response)
    coded = _coded_matrix(design)
    if any(value not in (-1.0, 1.0) for value in coded.ravel()):
        raise ValueError('自定义因子分析只接受因子点（低/高水平）')
    terms = [()] + [term for degree in range(1, order + 1)
                    for term in combinations(range(k), degree)]
    x = np.asarray([[1.0 if not term else np.prod(row[list(term)])
                     for term in terms] for row in coded], dtype=float)
    if not summary['complete_factorial']:
        # 非完整矩阵可能秩亏；报告实际秩与可估计性，而不是假装正规设计。
        rank = int(np.linalg.matrix_rank(x))
        if rank != x.shape[1]:
            raise ValueError('所选模型项在自定义矩阵上秩亏，无法估计')
    beta, _, rank, _ = np.linalg.lstsq(x, y, rcond=None)
    n, p = x.shape
    if rank != p:
        raise ValueError('设计矩阵秩亏，无法估计模型')
    fitted = x @ beta
    residuals = y - fitted
    sse = float(residuals @ residuals)
    sst = float(np.sum((y - y.mean()) ** 2))
    df = n - p
    cells = _cells(coded)
    pure_df = sum(len(group) - 1 for group in cells.values())
    pure_sse = sum(float(np.sum((y[group] - y[group].mean()) ** 2))
                   for group in cells.values())
    tolerance = np.finfo(float).eps * max(n, p) * max(float(y @ y), 1.0)
    error_available = df > 0 and pure_df > 0 and pure_sse > tolerance
    inference = None
    if error_available:
        mse = sse / df
        se = np.sqrt(np.diag(np.linalg.inv(x.T @ x)) * mse)
        t = beta / se
        critical = stats.t.ppf(.975, df)
        f = (max(0.0, sst - sse) / (p - 1)) / mse
        inference = {'mse': mse, 'se': se, 't': t,
                     'p': 2 * stats.t.sf(abs(t), df),
                     'ci_low': beta - critical * se,
                     'ci_high': beta + critical * se, 'f': float(f),
                     'model_p': float(stats.f.sf(f, p - 1, df))}
    names = ['截距'] + ['*'.join(spec.factors[index].factor_id for index in term)
                        for term in terms[1:]]
    effects = [None] + [2 * float(value) for value in beta[1:]]
    anova = []
    for index, term in enumerate(terms[1:], 1):
        ss = float(beta[index] ** 2 * (x[:, index] @ x[:, index]))
        anova.append({'term': names[index], 'ss': ss, 'df': 1, 'ms': ss,
                      'f': (ss / inference['mse']) if inference else None,
                      'p': float(stats.f.sf(ss / inference['mse'], 1, df))
                      if inference and inference['mse'] > 0 else None})
    anova.append({'term': '残差', 'ss': sse, 'df': df,
                  'ms': sse / df if df else None, 'f': None, 'p': None})
    anova.append({'term': '总计', 'ss': sst, 'df': n - 1, 'ms': None,
                  'f': None, 'p': None})
    lack_of_fit_df = len(cells) - 1 - (p - 1)
    lack_of_fit_sse = max(0.0, sse - pure_sse)
    lack_of_fit = None
    if error_available and lack_of_fit_df > 0:
        value = (lack_of_fit_sse / lack_of_fit_df) / (pure_sse / pure_df)
        lack_of_fit = {'ss': lack_of_fit_sse, 'df': lack_of_fit_df,
                       'f': float(value),
                       'p': float(stats.f.sf(value, lack_of_fit_df, pure_df))}
    condition = (float(np.linalg.cond(x)) if p else None)
    return {'design': design, 'response': response, 'order': order,
            'names': names, 'coefficients': beta, 'effects': effects, 'fitted': fitted,
            'residuals': residuals, 'coded': coded, 'n': n, 'p': p, 'rank': int(rank),
            'df': df, 'sse': sse, 'sst': sst, 'ssr': max(0.0, sst - sse),
            'pure_error_df': pure_df, 'pure_error_sse': pure_sse,
            'lack_of_fit_df': lack_of_fit_df,
            'lack_of_fit_sse': lack_of_fit_sse, 'lack_of_fit': lack_of_fit,
            'curvature': None, 'condition': condition, 'anova': anova,
            'r2': 1 - sse / sst if sst > 0 else None,
            'adjusted_r2': (1 - (sse / df) / (sst / (n - 1))
                            if df > 0 and sst > 0 else None),
            'inference': inference,
            'status': ('可推断；按实际自定义矩阵' if inference else
                       '无独立纯误差自由度或方差，统计推断不可用'),
            'assumption': ('自定义设计按实际矩阵分析；完整性与混杂需由用户核对，'
                           '推断假设误差独立、同方差且正态')}


def analyze_custom_rsm(frame, metadata, response, terms=None, use_blocks=True):
    """自定义响应面：用显式模型项与实际设定编码重建矩阵后拟合。"""
    design = restore_design_result(frame, metadata)
    validate_custom(design)
    # 未显式指定时使用设计声明的模型项；否则会退回完整二次模型而与实际设计不符。
    if terms is None:
        terms = list(design.spec.model_terms)
    continuous = [factor for factor in design.spec.factors
                  if factor.factor_type == 'continuous']
    coded = np.asarray([[coded_value(factor, run.settings[factor.factor_id],
                                     run.point_type) for factor in continuous]
                        for run in design.runs],
                       dtype=float)
    return fit_rsm(design, response, coded, terms=terms, use_blocks=use_blocks)


def analyze_custom_screening(frame, metadata, response, terms=None):
    """自定义筛选：主效应模型；秩亏时报告可估计性与零空间。"""
    from doe_screening_analysis import _fit
    design = restore_design_result(frame, metadata)
    summary = validate_custom(design)
    spec = design.spec
    names = [factor.factor_id for factor in spec.factors]
    y = _values(design, response)
    coded = _coded_matrix(design)
    main = [(name,) for name in names]
    selected = main if terms is None else [tuple(item) for item in terms]
    permitted = set(main + list(combinations(names, 2)))
    if len(set(selected)) != len(selected) or any(
            term not in permitted for term in selected):
        raise ValueError('模型项重复或无效')
    beta, rank, n, p, fitted, residuals, sse, sst, ssr, df, inference, status, details = _fit(
        coded, y, names, selected, (), allow_rank_deficiency=True)
    cells = _cells(coded)
    pure_df = sum(len(group) - 1 for group in cells.values())
    pure_sse = sum(float(np.sum((y[group] - y[group].mean()) ** 2))
                   for group in cells.values())
    reported = np.where(details['estimable'], beta, np.nan)
    return {'design': design, 'response': response,
            'names': ['截距'] + ['*'.join(term) for term in selected],
            'coefficients': reported,
            'effects': [None] + [None if not details['estimable'][index] else
                                 2 * float(value)
                                 for index, value in enumerate(beta[1:len(selected) + 1], 1)],
            'fitted': fitted, 'residuals': residuals, 'coded': coded, 'n': n,
            'p': p, 'rank': int(rank), 'df': df, 'sse': sse, 'sst': sst,
            'ssr': ssr, 'inference': inference, 'status': status,
            'pure_error_df': pure_df,
            'pure_error_sse': pure_sse if pure_df else None,
            'curvature': None, 'condition': float(np.linalg.cond(coded)),
            'estimable': details['estimable'],
            'nullspace': details['nullspace'], '_fit_details': details,
            'effect_indices': tuple(range(1, len(selected) + 1)),
            'properties': summary,
            'assumption': ('自定义筛选矩阵按实际点集核验；主效应投影不等同'
                           '因果效应，所选模型 p 值为名义值')}


def analyze_custom(frame, metadata, response, order=2, terms=None,
                   use_blocks=True):
    """按设计类型分派自定义分析；未知类型明确拒绝。"""
    design = restore_design_result(frame, metadata)
    kind = design.spec.design_type
    if kind == 'custom_factorial':
        return analyze_custom_factorial(frame, metadata, response, order)
    if kind == 'custom_rsm':
        return analyze_custom_rsm(frame, metadata, response, terms, use_blocks)
    if kind == 'custom_screening':
        return analyze_custom_screening(frame, metadata, response, terms)
    raise ValueError('当前设计不是受支持的自定义设计')
