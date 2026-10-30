"""基于实际筛选设计矩阵的连续响应分析。"""
from itertools import combinations

import numpy as np
from scipy import stats

from doe_core import restore_design_result
from doe_pb import validate_pb


def _lenth_pse(effects, tolerance):
    absolute = np.abs(np.asarray(effects, dtype=float))
    initial = 1.5 * float(np.median(absolute))
    retained = absolute[absolute < 2.5 * initial]
    if not len(retained):
        return None
    pse = 1.5 * float(np.median(retained))
    if pse <= tolerance:
        return None
    df = len(absolute) / 3
    return {'pse': pse, 'margin': float(stats.t.ppf(.975, df) * pse), 'df': df}


def _alias_projection(base, base_terms, model_terms, model_labels):
    """把候选项投影到基础模型；秩亏时遮蔽不可唯一估计的系数。"""
    u, singular, vh = np.linalg.svd(base, full_matrices=base.shape[1] > base.shape[0])
    tolerance = (np.finfo(float).eps * max(base.shape) * singular[0]
                 if len(singular) else 0.0)
    rank = int(np.count_nonzero(singular > tolerance))
    nullspace = vh[rank:]
    coefficient_tolerance = 8 * np.finfo(float).eps * max(base.shape)
    unique = (np.linalg.norm(nullspace, axis=0) <= coefficient_tolerance
              if len(nullspace) else np.ones(base.shape[1], dtype=bool))
    coefficients = ((vh[:rank].T / singular[:rank])
                    @ (u[:, :rank].T @ model_terms))
    estimable = np.broadcast_to(unique[:, None], coefficients.shape)
    values = np.where(estimable, coefficients, np.nan)
    relationships = []
    for i, base_term in enumerate(base_terms):
        for j, model_term in enumerate(model_labels):
            estimable_pair = bool(estimable[i, j])
            relationships.append({'main': base_term, 'effect': model_term,
                                  'coefficient': float(coefficients[i, j]) if estimable_pair else None,
                                  'estimable': estimable_pair})
    matrix = {'rows': list(base_terms), 'columns': list(model_labels),
              'values': [[float(value) if np.isfinite(value) else None for value in row]
                         for row in values]}
    return matrix, relationships


def _model_matrix(coded, names, selected, nuisance=()):
    positions = {name: i for i, name in enumerate(names)}
    columns = [np.ones(len(coded))] + [
        np.prod(coded[:, [positions[name] for name in term]], axis=1)
        for term in selected
    ] + list(nuisance)
    labels = ['截距'] + [f'{term[0]}²' if len(term) == 2 and term[0] == term[1]
                         else '*'.join(term) for term in selected]
    return np.column_stack(columns), labels


def _fit(coded, y, names, selected, nuisance=(), allow_rank_deficiency=False,
         fit_matrix=None):
    x = fit_matrix if fit_matrix is not None else _model_matrix(
        coded, names, selected, nuisance)[0]
    beta, _, rank, _ = np.linalg.lstsq(x, y, rcond=None)
    n, p = x.shape
    if rank != p and not allow_rank_deficiency:
        raise ValueError('所选模型秩亏，系数不可唯一估计')
    nullspace = np.empty((0, p))
    estimable = np.ones(p, dtype=bool)
    unit_cov = None
    contrast_tolerance = 8 * np.finfo(float).eps * max(n, p)
    if rank != p:
        _, singular, vh = np.linalg.svd(x, full_matrices=p > n)
        nullspace = vh[int(rank):]
        estimable = np.linalg.norm(nullspace, axis=0) <= contrast_tolerance
        unit_cov = (vh[:rank].T / singular[:rank]**2) @ vh[:rank]
    fitted = x @ beta
    residuals = y - fitted
    sse = float(residuals @ residuals)
    sst = float(np.sum((y - y.mean()) ** 2))
    if not np.isfinite(beta).all() or not np.isfinite([sse, sst]).all():
        raise ValueError('响应超出可分析的数值范围')
    ssr = sst - sse
    if ssr < -64 * np.finfo(float).eps * max(n, p) * max(sse, sst, 1.0):
        raise ValueError('回归平方和计算不一致，无法可靠分析')
    ssr = max(0.0, ssr)
    df = n - rank
    tolerance = np.finfo(float).eps * max(n, p) * max(float(np.linalg.norm(y)), 1.0)
    inference = None
    if df <= 0:
        status = '模型饱和，残差自由度不足，常规推断不可用'
    elif np.sqrt(sse) <= tolerance:
        status = '残差方差为零或无法辨认，常规推断不可用'
    else:
        mse = sse / df
        if unit_cov is None:
            _, singular, vh = np.linalg.svd(x, full_matrices=False)
            unit_cov = (vh.T / singular**2) @ vh
        se = np.sqrt(np.diag(unit_cov) * mse)
        se[~estimable] = np.nan
        t = beta / se
        critical = stats.t.ppf(.975, df)
        model_df = rank - 1
        f = ssr / model_df / mse if model_df else None
        inference = {'mse': mse, 'se': se, 't': t, 'p': 2 * stats.t.sf(abs(t), df),
                     'ci_low': beta - critical * se, 'ci_high': beta + critical * se,
                     'f': f, 'model_p': float(stats.f.sf(f, model_df, df)) if f is not None else None}
        status = '推断以模型充分、误差独立同方差且正态为前提'
    if rank != p:
        status = '模型秩亏，仅可解释经零空间验证的系数或对比；' + status
    details = {'nullspace': nullspace, 'estimable': estimable, 'beta': beta,
               'unit_cov': unit_cov, 'tolerance': contrast_tolerance}
    return beta, rank, n, p, fitted, residuals, sse, sst, ssr, df, inference, status, details


def screening_contrast(result, weights):
    """检查指定系数线性组合是否在所选模型的行空间内。"""
    try:
        vector = np.asarray(weights, dtype=float)
    except (ValueError, TypeError, OverflowError) as error:
        raise ValueError('对比权重必须是有限数值') from error
    if vector.shape != (result['p'],) or not np.isfinite(vector).all() or not np.any(vector):
        raise ValueError('对比权重必须是非零且有限的模型系数向量')
    details = result['_fit_details']
    scale = float(np.max(np.abs(vector)))
    normalized = vector / scale
    estimable = np.linalg.norm(details['nullspace'] @ normalized) <= details['tolerance'] * max(1., np.linalg.norm(normalized))
    if not estimable:
        return {'estimable': False, 'estimate': None, 'se': None, 't': None, 'p': None}
    with np.errstate(over='ignore', invalid='ignore'):
        estimate = float((normalized @ details['beta']) * scale)
    if not np.isfinite(estimate):
        raise ValueError('对比结果超出有限数值范围')
    se = t = probability = None
    if result['inference'] is not None:
        variance = float(normalized @ details['unit_cov'] @ normalized) * result['inference']['mse']
        if variance > 0 and np.isfinite(variance):
            se = float(np.sqrt(variance) * scale)
            if not np.isfinite(se):
                raise ValueError('对比标准误超出有限数值范围')
            t = estimate / se
            if not np.isfinite(t):
                raise ValueError('对比统计量超出有限数值范围')
            probability = float(2 * stats.t.sf(abs(t), result['df']))
    return {'estimable': True, 'estimate': estimate, 'se': se, 't': t, 'p': probability}


def analyze_pb(frame, metadata, response, terms=None):
    """拟合 PB 项并报告主效应与二因子交互的实际投影。"""
    design = restore_design_result(frame, metadata)
    validate_pb(design)
    factors = design.spec.factors
    names = [factor.factor_id for factor in factors]
    if response not in design.spec.response_names:
        raise ValueError('响应不属于该设计')
    values = [run.responses[response] for run in design.runs]
    if any(value is None for value in values):
        raise ValueError('响应存在缺失值，请填写全部运行的响应')
    try:
        y = np.asarray(values, dtype=float)
    except (ValueError, OverflowError) as error:
        raise ValueError('响应超出可分析的数值范围') from error
    if not np.isfinite(y).all() or any(isinstance(v, int) and int(x) != v for v, x in zip(values, y)):
        raise ValueError('响应不是有限或可精确表示的数值')
    from doe_core import _screening_level
    coded = np.asarray([[_screening_level(f, run.settings[f.factor_id]) for f in factors]
                        for run in design.runs])
    main = [(name,) for name in names]
    if terms is None:
        selected = main
    else:
        if (not isinstance(terms, (list, tuple)) or
                any(not isinstance(t, (tuple, list)) or any(not isinstance(v, str) for v in t)
                    for t in terms)):
            raise ValueError('模型项必须是因子标识组成的列表')
        selected = [tuple(t) for t in terms]
        permitted = set(main + list(combinations(names, 2)))
        if len(set(selected)) != len(selected) or any(t not in permitted for t in selected):
            raise ValueError('模型项重复或无效')
        if any((name,) not in selected for t in selected if len(t) == 2 for name in t):
            raise ValueError('交互项必须包含对应的主效应')
    center = np.asarray([run.point_type in ('center', 'pseudo_center') for run in design.runs], dtype=float)
    nuisance, nuisance_names = [], []
    if center.any():
        nuisance.append(center)
        nuisance_names.append('中心点偏差')
    if design.spec.block_count is not None:
        for block in range(2, design.spec.block_count + 1):
            nuisance.append(np.asarray([run.block == block for run in design.runs], dtype=float))
            nuisance_names.append(f'区组{block}')
    fit_matrix, fit_terms = _model_matrix(coded, names, selected, nuisance)
    positions = {name: i for i, name in enumerate(names)}
    fit_terms += nuisance_names
    beta, rank, n, p, fitted, residuals, sse, sst, ssr, df, inference, status, _ = _fit(
        coded, y, names, selected, nuisance, fit_matrix=fit_matrix)
    lenth = None
    if df == 0:
        if selected == main and not nuisance:
            tolerance = np.finfo(float).eps * max(n, p) * float(np.linalg.norm(y))
            lenth = _lenth_pse(2 * beta[1:], tolerance)
        status += ('；Lenth PSE 依据效应稀疏假设，仅作探索' if lenth else
                   '；Lenth PSE 不可用')
    projections = []
    for a, b in combinations(range(len(names)), 2):
        interaction = coded[:, a] * coded[:, b]
        for j, name in enumerate(names):
            coefficient = float(coded[:, j] @ interaction / (coded[:, j] @ coded[:, j]))
            if coefficient:
                projections.append({'main': name, 'interaction': f'{names[a]}*{names[b]}',
                                    'projection': coefficient})
    all_terms = list(main) + list(combinations(names, 2))
    omitted_terms = [term for term in all_terms if term not in selected]
    alias_labels = [f'{term[0]}²' if len(term) == 2 and term[0] == term[1] else '*'.join(term)
                    for term in omitted_terms]
    alias_terms = (np.column_stack([np.prod(coded[:, [positions[name] for name in term]], axis=1)
                                    for term in omitted_terms]) if omitted_terms
                   else np.empty((len(y), 0)))
    alias_matrix, alias_relations = _alias_projection(fit_matrix, fit_terms,
                                                      alias_terms, alias_labels)
    cells = {}
    for run, levels, value in zip(design.runs, coded, y):
        cells.setdefault((run.block, tuple(levels)), []).append(value)
    pure_df = sum(len(cell) - 1 for cell in cells.values())
    pure_sse = sum(float(np.sum((np.asarray(cell) - np.mean(cell)) ** 2)) for cell in cells.values())
    curvature_index = len(selected) + 1 if center.any() else None
    curvature = None if curvature_index is None else {
        'difference': float(beta[curvature_index]),
        'f': float(inference['t'][curvature_index] ** 2) if inference else None,
        'p': float(inference['p'][curvature_index]) if inference else None,
    }
    return {'design': design, 'response': response,
            'names': ['截距'] + ['*'.join(t) for t in selected] + nuisance_names,
            'coefficients': beta, 'effects': [None] + [2 * float(v) for v in beta[1:len(selected)+1]] + [None] * len(nuisance),
            'fitted': fitted, 'residuals': residuals, 'coded': coded, 'n': n, 'p': p,
            'rank': int(rank), 'df': df, 'sse': sse, 'sst': sst,
            'ssr': ssr, 'inference': inference, 'status': status,
            'projections': projections, 'lenth': lenth, 'pure_error_df': pure_df,
            'alias_matrix': alias_matrix,
            'alias_relations': alias_relations, 'fit_terms': fit_terms,
            'fit_matrix': fit_matrix,
            'pure_error_sse': pure_sse if pure_df else None, 'curvature': curvature,
            'assumption': ('主效应可能与未纳入模型的交互部分或完全混杂；投影不代表因果效应。'
                           + ('中心点只能检验整体曲率，不能独立估计各平方项。' if center.any() else ''))}


def analyze_dsd(frame, metadata, response, terms=None):
    """拟合指定模型；秩亏时只报告可估计的系数及对比。"""
    from doe_core import _screening_level
    from doe_dsd import validate_dsd
    design = restore_design_result(frame, metadata)
    validate_dsd(design)
    factors = design.spec.factors
    names = [f.factor_id for f in factors]
    if response not in design.spec.response_names:
        raise ValueError('响应不属于该设计')
    values = [run.responses[response] for run in design.runs]
    if any(value is None for value in values):
        raise ValueError('响应存在缺失值，请填写全部运行的响应')
    try:
        y = np.asarray(values, dtype=float)
    except (ValueError, OverflowError) as error:
        raise ValueError('响应超出可分析的数值范围') from error
    if not np.isfinite(y).all() or any(isinstance(v, int) and int(x) != v for v, x in zip(values, y)):
        raise ValueError('响应不是有限或可精确表示的数值')
    coded = np.asarray([[_screening_level(f, run.settings[f.factor_id]) for f in factors]
                        for run in design.runs], dtype=float)
    main = [(name,) for name in names]
    squares = [(f.factor_id, f.factor_id) for f in factors if f.factor_type == 'continuous']
    permitted = set(main + squares + list(combinations(names, 2)))
    if terms is None:
        selected = main
    else:
        if (not isinstance(terms, (list, tuple)) or
                any(not isinstance(t, (tuple, list)) or any(not isinstance(v, str) for v in t)
                    for t in terms)):
            raise ValueError('模型项必须是因子标识组成的列表')
        selected = [tuple(t) for t in terms]
        if len(set(selected)) != len(selected) or any(t not in permitted for t in selected):
            raise ValueError('模型项重复或无效')
        if any((name,) not in selected for t in selected if len(t) == 2 for name in t):
            raise ValueError('平方或交互项必须包含对应的主效应')
    block_names = [f'区组{block}' for block in range(2, (design.spec.block_count or 1) + 1)]
    block_columns = [np.asarray([run.block == block for run in design.runs], dtype=float)
                     for block in range(2, (design.spec.block_count or 1) + 1)]
    n = len(y)
    positions = {name: i for i, name in enumerate(names)}
    fit_matrix, fit_terms = _model_matrix(coded, names, selected, block_columns)
    fit_terms += block_names
    beta, rank, n, p, fitted, residuals, sse, sst, ssr, df, inference, status, details = _fit(
        coded, y, names, selected, block_columns, allow_rank_deficiency=True,
        fit_matrix=fit_matrix)
    main_matrix = np.column_stack([np.ones(n), coded] + block_columns)
    projections = []
    second_order = [(f'{f.factor_id}²', coded[:, i] ** 2) for i, f in enumerate(factors)
                    if f.factor_type == 'continuous']
    second_order += [(f'{names[a]}*{names[b]}', coded[:, a] * coded[:, b])
                     for a, b in combinations(range(len(names)), 2)]
    all_terms = list(main) + list(squares) + list(combinations(names, 2))
    omitted_terms = [term for term in all_terms if term not in selected]
    alias_labels = [f'{t[0]}²' if len(t) == 2 and t[0] == t[1] else '*'.join(t)
                    for t in omitted_terms]
    alias_terms = (np.column_stack([np.prod(coded[:, [positions[name] for name in term]], axis=1)
                                    for term in omitted_terms]) if omitted_terms
                   else np.empty((n, 0)))
    alias_matrix, alias_relations = _alias_projection(fit_matrix, fit_terms,
                                                      alias_terms, alias_labels)
    all_projections = np.linalg.lstsq(main_matrix, np.column_stack([column for _, column in second_order]), rcond=None)[0]
    for (label, _), projection in zip(second_order, all_projections.T):
        for name, value in zip(['截距'] + names + block_names, projection):
            if abs(value) > 1e-12:
                projections.append({'main': name, 'interaction': label, 'projection': float(value)})
    selected_squares = [t for t in selected if len(t) == 2 and t[0] == t[1]]
    selected_interactions = [t for t in selected if len(t) == 2 and t[0] != t[1]]
    nonlinear_projections = []
    if selected_squares and selected_interactions:
        linear = np.column_stack([np.ones(n)] + [coded[:, positions[t[0]]] for t in selected if len(t) == 1] + block_columns)
        nonlinear = selected_squares + selected_interactions
        columns = np.column_stack([coded[:, positions[a]] * coded[:, positions[b]] for a, b in nonlinear])
        residual_columns = columns - linear @ np.linalg.lstsq(linear, columns, rcond=None)[0]
        for i, square in enumerate(selected_squares):
            norm = float(residual_columns[:, i] @ residual_columns[:, i])
            if norm <= np.finfo(float).eps * n:
                continue
            for j, interaction in enumerate(selected_interactions, len(selected_squares)):
                value = float(residual_columns[:, i] @ residual_columns[:, j] / norm)
                if abs(value) > 1e-12:
                    nonlinear_projections.append({'square': f'{square[0]}²',
                                                  'interaction': '*'.join(interaction), 'projection': value})
    labels = ['截距'] + [f'{t[0]}²' if len(t) == 2 and t[0] == t[1] else '*'.join(t) for t in selected] + block_names
    reported_beta = np.where(details['estimable'], beta, np.nan)
    return {'design': design, 'response': response, 'names': labels, 'coefficients': reported_beta,
            'effects': [None] + [None if not details['estimable'][i] or (len(t) == 2 and t[0] == t[1]) else 2*float(v)
                                 for i, (t, v) in enumerate(zip(selected, beta[1:len(selected)+1]), 1)] + [None] * len(block_names),
            'fitted': fitted, 'residuals': residuals, 'coded': coded, 'n': n, 'p': p,
            'rank': int(rank), 'df': df, 'sse': sse, 'sst': sst,
            'ssr': ssr, 'inference': inference, 'status': status,
            'projections': projections, 'nonlinear_projections': nonlinear_projections,
            'alias_matrix': alias_matrix,
            'alias_relations': alias_relations, 'fit_terms': fit_terms,
            'fit_matrix': fit_matrix,
            'nullspace': details['nullspace'],
            'estimable': details['estimable'], '_fit_details': details,
            'effect_indices': tuple(range(1, len(selected) + 1)),
            'assumption': ('可估计性和混杂取决于实际设计与所选模型；不能假定完整二次模型可估计。'
                           '所选模型的 p 值为名义值，不代表独立确认。'
                           + ('平方与交互投影仅调整截距、所选主效应和区组。' if nonlinear_projections else ''))}
