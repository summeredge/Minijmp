"""正规两水平部分因子分析；别名关系从实际设计矩阵验证并导出。"""
from collections import defaultdict
from itertools import combinations
from numbers import Integral

import numpy as np
from scipy import stats

from doe_fractional import validate_fractional_design
from doe_factorial_anova import partition_factorial_error


def _fractional_design(frame, metadata):
    design = validate_fractional_design(frame, metadata)
    runs = design.runs
    factors = design.spec.factors
    coded = []
    for run in runs:
        coded.append(tuple(factor.to_coded(run.settings[factor.factor_id])
                           for factor in factors))
    return design, np.asarray(coded, dtype=float)


def _term_label(term, factor_ids):
    return '*'.join(factor_ids[index] for index in term) if term else '截距'


def _alias_groups(unique_coded, factor_ids):
    groups = {}
    k = len(factor_ids)
    factor_masks = [sum(1 << i for i, row in enumerate(unique_coded) if row[j] == -1)
                    for j in range(k)]
    full_mask = (1 << len(unique_coded)) - 1
    for degree in range(k + 1):
        for term in combinations(range(k), degree):
            signature = 0
            for index in term:
                signature ^= factor_masks[index]
            opposite = full_mask ^ signature
            sign = 1 if signature <= opposite else -1
            signature = min(signature, opposite)
            groups.setdefault(signature, []).append((term, sign))
    ordered = sorted(groups.values(), key=lambda group: (len(group[0][0]), group[0][0]))
    result, term_to_group = [], {}
    for group_index, members in enumerate(ordered):
        terms = tuple(_term_label(term, factor_ids) for term, _ in members)
        signed_terms = tuple(label if sign > 0 else '-' + label
                             for label, (_, sign) in zip(terms, members))
        group = {'terms': terms, 'signs': tuple(sign for _, sign in members),
                 'label': ' = '.join(signed_terms), 'representative': None}
        result.append(group)
        for term, _ in members:
            term_to_group[term] = group_index
    return result, term_to_group


def fractional_alias_groups(frame, metadata, order=None):
    """返回别名组；响应可未填写，order 仅筛选当前可选的代表项。"""
    design, coded = _fractional_design(frame, metadata)
    factors = design.spec.factors
    k = len(factors)
    include_all = order is None
    if order is None:
        order = k
    if isinstance(order, bool) or not isinstance(order, Integral) or not 1 <= order <= k:
        raise ValueError('模型阶次无效')
    factor_ids = [factor.factor_id for factor in factors]
    factorial = np.asarray([run.point_type == 'factorial' for run in design.runs])
    unique_coded = np.asarray(sorted(set(map(tuple, coded[factorial]))), dtype=int)
    groups, term_to_group = _alias_groups(unique_coded, factor_ids)
    selectable = defaultdict(list)
    for degree in range(1, int(order) + 1):
        for term in combinations(range(k), degree):
            group_index = term_to_group[term]
            if group_index != term_to_group[()]:
                selectable[group_index].append(_term_label(term, factor_ids))
    return [dict(group, selectable_terms=tuple(selectable.get(i, ())))
            for i, group in enumerate(groups) if include_all or i in selectable]


def analyze_fractional(frame, metadata, response, order=2, representatives=None):
    """拟合正规部分因子模型；系数和推断始终解释为完整别名组。"""
    design, coded = _fractional_design(frame, metadata)
    spec, runs = design.spec, design.runs
    factors, k = spec.factors, len(spec.factors)
    if response not in spec.response_names:
        raise ValueError('响应不属于该设计')
    if isinstance(order, bool) or not isinstance(order, Integral) or not 1 <= order <= k:
        raise ValueError('模型阶次无效')
    order = int(order)
    values = [run.responses[response] for run in runs]
    if any(value is None for value in values):
        raise ValueError('响应存在缺失值，请填写全部运行的响应')
    try:
        y = np.asarray(values, dtype=float)
    except (ValueError, OverflowError) as exc:
        raise ValueError('响应超出可分析的数值范围') from exc
    if (not np.isfinite(y).all() or any(
            isinstance(value, int) and int(converted) != value
            for value, converted in zip(values, y))):
        raise ValueError('响应超出可分析的数值范围或不能无损表示为浮点数')

    factor_ids = [factor.factor_id for factor in factors]
    factorial = np.asarray([run.point_type == 'factorial' for run in runs])
    unique_coded = np.asarray(sorted(set(map(tuple, coded[factorial]))), dtype=int)
    alias_groups, term_to_group = _alias_groups(unique_coded, factor_ids)
    candidates = [term for degree in range(1, order + 1)
                  for term in combinations(range(k), degree)]
    labels = {_term_label(term, factor_ids): term for term in candidates}
    candidates_by_group = defaultdict(list)
    for term in candidates:
        candidates_by_group[term_to_group[term]].append(term)

    if representatives is None:
        selected = [terms[0] for group_index, terms in candidates_by_group.items()
                    if group_index != term_to_group[()]]
    else:
        if not isinstance(representatives, (tuple, list)):
            raise ValueError('representatives 必须是项名称列表')
        if any(not isinstance(name, str) or name not in labels for name in representatives):
            raise ValueError('代表项必须是模型阶次内的项，例如 A*B')
        selected, selected_groups = [], set()
        for name in representatives:
            term = labels[name]
            group_index = term_to_group[term]
            if group_index == term_to_group[()]:
                raise ValueError('与截距混杂的项不能作为独立代表项')
            if group_index in selected_groups:
                raise ValueError('同一别名组只能选择一个代表项')
            selected_groups.add(group_index)
            selected.append(term)

    chosen_by_group = {term_to_group[term]: _term_label(term, factor_ids)
                       for term in selected}
    for group_index, group in enumerate(alias_groups):
        group['selectable_terms'] = tuple(
            _term_label(term, factor_ids)
            for term in candidates_by_group.get(group_index, ()))
        if group_index == term_to_group[()]:
            group['representative'] = '截距'
        else:
            group['representative'] = chosen_by_group.get(group_index)

    centers = np.asarray([run.point_type == 'center' for run in runs])
    has_center = bool(centers.any())
    columns = [np.ones(len(coded))]
    columns.extend(np.prod(coded[:, term], axis=1) for term in selected)
    if has_center:
        columns.append(centers.astype(float))
    block_levels = list(dict.fromkeys(run.block for run in runs if run.block is not None))
    block_df = max(0, len(block_levels) - 1)
    block_basis = (np.column_stack([
        [1.0 if run.block == block else 0.0 for run in runs]
        for block in block_levels[:-1]
    ]) if len(block_levels) > 1 else np.empty((len(runs), 0)))
    x = np.column_stack(columns + [block_basis[:, index]
                                   for index in range(block_basis.shape[1])])
    beta, _, rank, _ = np.linalg.lstsq(x, y, rcond=None)
    n, p = x.shape
    if rank != p:
        raise ValueError('所选代表项设计矩阵秩亏')
    fitted = x @ beta
    residuals = y - fitted
    sse = float(residuals @ residuals)
    sst = float(np.sum((y - y.mean()) ** 2))
    if not np.isfinite(beta).all() or not np.isfinite([sse, sst]).all():
        raise ValueError('响应超出可分析的数值范围')
    ssr = max(0.0, sst - sse)

    treatment_cells = [tuple(row) for row in coded]
    error = partition_factorial_error(
        y, treatment_cells, [run.block for run in runs] if block_df else None)
    pure_error_df, pure_error_sse = error['pure_error_df'], error['pure_error_ss']
    block_error_df, block_error_sse = error['block_error_df'], error['block_error_ss']
    model_treatment_df = len(selected) + int(has_center)
    lack_of_fit_df = len(set(treatment_cells)) - 1 - model_treatment_df
    lack_of_fit_sse = max(0.0, sse - pure_error_sse - block_error_sse)
    df = n - p
    ss_tolerance = np.finfo(float).eps * max(n, p) * max(float(y @ y), 1.0)
    if df != pure_error_df + block_error_df + lack_of_fit_df:
        raise ValueError('残差自由度无法分解为纯误差、区组误差和失拟')
    pure_mse = pure_error_sse / pure_error_df if pure_error_df else None
    pure_error_available = pure_error_df > 0 and pure_error_sse > ss_tolerance
    error_available = (df > 0 and lack_of_fit_df == 0 and sse > ss_tolerance
                       if block_df else df > 0 and pure_error_available)
    inference = None
    if df == 0:
        status = '模型饱和，不能进行统计推断'
    elif block_df and lack_of_fit_df:
        status = '区组模型未包含全部别名自由度，不能分离失拟与区组误差'
    elif not error_available:
        status = ('区组调整误差自由度或方差不可用，统计推断不可用' if block_df else
                  '无正的独立纯误差自由度或方差，统计推断不可用')
    else:
        mse = sse / df
        se = np.sqrt(np.diag(np.linalg.inv(x.T @ x)) * mse)
        t = beta / se
        critical = stats.t.ppf(.975, df)
        model_df = p - 1
        f = (ssr / model_df) / mse if model_df else None
        inference = {
            'mse': mse, 'se': se, 't': t,
            'p': 2 * stats.t.sf(abs(t), df),
            'ci_low': beta - critical * se, 'ci_high': beta + critical * se,
            'f': float(f) if f is not None else None,
            'model_p': float(stats.f.sf(f, model_df, df)) if f is not None else None,
        }
        status = '可推断；系数按完整别名组解释，区组误差假设无处理×区组交互'

    names = ['截距'] + [_term_label(term, factor_ids) for term in selected]
    effects = [None] + [2 * float(value) for value in beta[1:1 + len(selected)]]
    if has_center:
        names.append('中心点偏移')
        effects.append(None)
    block_names = [f'区组 {block}' for block in block_levels[:-1]]
    names.extend(block_names)
    effects.extend([None] * len(block_names))
    block_values = {block: [value for run, value in zip(runs, y) if run.block == block]
                    for block in block_levels}
    block_ss = (sum(len(values) * (float(np.mean(values)) - float(np.mean(y))) ** 2
                    for values in block_values.values()) if block_names else 0.0)
    curvature = None
    if has_center:
        factorial_y = y[~centers]
        center_y = y[centers]
        difference = float(np.mean(center_y) - np.mean(factorial_y))
        contrast_ss = difference ** 2 / (1 / len(center_y) + 1 / len(factorial_y))
        curvature = {'difference': difference, 'ss': contrast_ss, 'df': 1,
                     'f': None, 'p': None}
        if pure_error_available:
            curvature_mse, curvature_df = pure_mse, pure_error_df
        else:
            curvature_mse, curvature_df = None, None
        if curvature_mse is not None:
            f_curvature = contrast_ss / curvature_mse
            curvature.update(f=float(f_curvature),
                             p=float(stats.f.sf(f_curvature, 1, curvature_df)))
    lack_of_fit = None
    if not block_df and pure_error_available and lack_of_fit_df > 0:
        f_lof = (lack_of_fit_sse / lack_of_fit_df) / pure_mse
        lack_of_fit = {'ss': lack_of_fit_sse, 'df': lack_of_fit_df,
                       'pure_error_ss': pure_error_sse, 'pure_error_df': pure_error_df,
                       'f': float(f_lof),
                       'p': float(stats.f.sf(f_lof, lack_of_fit_df, pure_error_df))}
    mse = sse / df if error_available else None
    anova = []
    if block_df:
        block_ms = block_ss / block_df
        block_f = block_ms / mse if mse is not None else None
        anova.append({'term': '区组', 'ss': block_ss, 'df': block_df, 'ms': block_ms,
                      'f': block_f,
                      'p': float(stats.f.sf(block_f, block_df, df)) if block_f is not None else None})
    for index, term in enumerate(selected, start=1):
        term_ss = float(beta[index] ** 2 * (x[:, index] @ x[:, index]))
        term_f = term_ss / mse if mse is not None else None
        anova.append({'term': _term_label(term, factor_ids), 'ss': term_ss, 'df': 1,
                      'ms': term_ss, 'f': term_f,
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
    return {
        'design': design, 'response': response, 'order': order,
        'names': names, 'representatives': tuple(
            _term_label(term, factor_ids) for term in selected),
        'alias_groups': alias_groups, 'coefficients': beta, 'effects': effects,
        'fitted': fitted, 'residuals': residuals, 'coded': coded,
        'n': n, 'p': p, 'rank': int(rank), 'df': df,
        'block_ss': block_ss, 'block_df': len(block_names),
        'block_error_sse': block_error_sse, 'block_error_df': block_error_df,
        'block_error_ms': block_error_sse / block_error_df if block_error_df else None,
        'sse': sse, 'sst': sst, 'ssr': ssr,
        'pure_error_df': pure_error_df, 'pure_error_sse': pure_error_sse,
        'lack_of_fit_df': lack_of_fit_df, 'lack_of_fit_sse': lack_of_fit_sse,
        'lack_of_fit': lack_of_fit, 'anova': anova,
        'curvature': curvature,
        'r2': 1 - sse / sst if sst > 0 else None,
        'adjusted_r2': 1 - (sse / df) / (sst / (n - 1)) if df > 0 and sst > 0 else None,
        'inference': inference, 'status': status,
        'assumption': ('每个效应仅解释为完整别名组；纯误差按相同因子设置及相同区组分组。'
                       '区组推断假设模型充分且无处理×区组交互；推断还假设误差独立、同方差且正态。'),
    }
