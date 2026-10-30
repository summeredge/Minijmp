"""DSD 逐步模型选择：逐项 F 检验、强制层级、确定性并列规则。

只选择模型项；最终系数与推断仍由 analyze_dsd() 按实际矩阵重新分析。
选择后的名义 p 值未校正模型选择偏差。
"""
from itertools import combinations
from numbers import Integral, Real

import numpy as np
from scipy import stats

from doe_core import _screening_level, restore_design_result
from doe_dsd import validate_dsd
from doe_screening_analysis import _fit, analyze_dsd


MAX_CANDIDATES = 64
DEFAULT_ALPHA = 0.15
DEFAULT_MAX_STEPS = 200


def _label(term):
    return f'{term[0]}²' if len(term) == 2 and term[0] == term[1] else '*'.join(term)


def _parents(term):
    if len(term) == 1:
        return ()
    return ((term[0],),) if term[0] == term[1] else ((term[0],), (term[1],))


def _hierarchical(terms):
    present = set(terms)
    return all(parent in present for term in terms for parent in _parents(term))


def _term_list(value, field, permitted):
    if value is None:
        return ()
    if not isinstance(value, (list, tuple)):
        raise ValueError(f'{field} 必须是模型项列表')
    result = []
    for item in value:
        if (not isinstance(item, (tuple, list)) or not item
                or any(not isinstance(name, str) for name in item)):
            raise ValueError(f'{field} 的每项必须是因子标识组成的元组')
        term = tuple(item)
        if term not in permitted:
            raise ValueError(f'{field} 含无效模型项：{_label(term)}')
        if term in result:
            raise ValueError(f'{field} 含重复模型项：{_label(term)}')
        result.append(term)
    return tuple(result)


def _alpha(value, field):
    if isinstance(value, bool) or not isinstance(value, Real) or not np.isfinite(value):
        raise ValueError(f'{field} 必须是 0 与 1 之间的数值')
    if not 0 < float(value) < 1:
        raise ValueError(f'{field} 必须严格位于 0 与 1 之间')
    return float(value)


def _response(design, response):
    if response not in design.spec.response_names:
        raise ValueError('响应不属于该设计')
    values = [run.responses[response] for run in design.runs]
    if any(value is None for value in values):
        raise ValueError('响应存在缺失值，请填写全部运行的响应')
    try:
        y = np.asarray(values, dtype=float)
    except (ValueError, OverflowError) as error:
        raise ValueError('响应超出可分析的数值范围') from error
    if not np.isfinite(y).all() or any(isinstance(v, int) and int(x) != v
                                       for v, x in zip(values, y)):
        raise ValueError('响应不是有限或可精确表示的数值')
    return y


def _p_value(f, df1, df2):
    if f is None or not np.isfinite(f) or df1 < 1 or df2 < 1:
        return None
    return float(stats.f.sf(f, df1, df2))


def _information_criterion(sse, n, rank, criterion):
    """Gaussian OLS AICc/BIC; k counts estimable mean coefficients."""
    df = n - rank
    k = rank
    if (df < 1 or not np.isfinite(sse) or sse <= 0 or n < 2
            or criterion == 'aicc' and n - k - 1 <= 0):
        return None
    log_likelihood = -0.5 * n * (np.log(2 * np.pi) + 1 + np.log(sse / n))
    value = -2 * log_likelihood
    if criterion == 'aicc':
        value += 2 * k * n / (n - k - 1)
    else:
        value += k * np.log(n)
    return float(value) if np.isfinite(value) else None


def select_dsd_stepwise(frame, metadata, response, *, alpha_enter=DEFAULT_ALPHA,
                        alpha_remove=DEFAULT_ALPHA, candidates=None,
                        initial=None, forced=None, max_steps=DEFAULT_MAX_STEPS,
                        method='stepwise', criterion=None):
    """按部分 F 或前向信息准则选择 DSD 模型项。"""
    design = restore_design_result(frame, metadata)
    validate_dsd(design)
    methods = ('stepwise', 'forward', 'backward', 'information_criteria')
    if method not in methods:
        raise ValueError('模型选择方法无效')
    if method == 'information_criteria':
        criterion = 'aicc' if criterion is None else criterion
        if not isinstance(criterion, str) or criterion.lower() not in ('aicc', 'bic'):
            raise ValueError('信息准则必须是 aicc 或 bic')
        criterion = criterion.lower()
    elif criterion is not None:
        raise ValueError('信息准则仅适用于前向信息准则方法')
    alpha_enter = _alpha(alpha_enter, 'Alpha to enter')
    alpha_remove = _alpha(alpha_remove, 'Alpha to remove')
    if isinstance(max_steps, bool) or not isinstance(max_steps, Integral) or max_steps < 1:
        raise ValueError('最大步骤数必须是正整数')
    y = _response(design, response)
    factors = design.spec.factors
    names = [factor.factor_id for factor in factors]
    mains = tuple((name,) for name in names)
    squares = tuple((f.factor_id, f.factor_id) for f in factors
                    if f.factor_type == 'continuous')
    interactions = tuple(combinations(names, 2))
    permitted = set(mains + squares + interactions)
    if candidates is None:
        order = list(mains + squares + interactions)
    else:
        order = list(_term_list(candidates, '候选项', permitted))
        if not order:
            raise ValueError('候选项不能为空')
    if len(order) > MAX_CANDIDATES:
        raise ValueError(f'Stepwise 候选项不能超过 {MAX_CANDIDATES} 个；'
                         '请显式指定较小的候选项集合')
    initial = list(_term_list(initial, '初始项', permitted))
    forced = list(_term_list(forced, '强制保留项', permitted))
    outside = [term for term in initial + forced if term not in order]
    if outside:
        raise ValueError('初始项与强制保留项必须是候选项的子集：'
                         + '、'.join(_label(term) for term in outside))
    if method == 'backward':
        if initial:
            raise ValueError('Backward 方法从完整候选模型开始，不接受初始项')
        terms = list(order)
    else:
        terms = [term for term in order if term in set(initial) | set(forced)]
    if not _hierarchical(terms):
        raise ValueError('初始项、强制保留项或完整候选模型不满足强层级结构')
    position = {term: index for index, term in enumerate(order)}
    coded = np.asarray([[_screening_level(f, run.settings[f.factor_id]) for f in factors]
                        for run in design.runs], dtype=float)
    block_columns = [np.asarray([run.block == block for run in design.runs], dtype=float)
                     for block in range(2, (design.spec.block_count or 1) + 1)]
    forced_terms = set(forced)
    n = len(y)

    def _columns(selected):
        return np.column_stack([np.ones(n), *block_columns, *[
            np.prod(coded[:, [names.index(name) for name in item]], axis=1)
            for item in selected]])

    def evaluate(selected):
        _, rank, _, p, _, _, sse, _, _, _, _, _, _ = (
            _fit(coded, y, names, selected, block_columns, allow_rank_deficiency=True))
        return {'rank': rank, 'sse': float(sse), 'p': p, 'df': n - rank}

    def dimension(term, selected):
        """候选项在“截距 + 已选项 + 区组”之上新增的实际维度。"""
        base = _columns(selected)
        column = np.prod(coded[:, [names.index(name) for name in term]], axis=1)
        return (np.linalg.matrix_rank(np.column_stack([base, column])) -
                np.linalg.matrix_rank(base))

    steps, visited = [], set()
    criterion_path, candidate_path = [], []
    best_terms = None
    best_criterion = None
    stop_reason = None
    for iteration in range(1, int(max_steps) + 1):
        state = frozenset(terms)
        if state in visited:
            stop_reason = 'model_cycle_detected'
            break
        visited.add(state)
        current = evaluate(terms)
        if current['df'] < 1:
            stop_reason = ('initial_model_saturated'
                           if method == 'backward' and not steps else
                           'residual_df_limit')
            break
        tolerance = (np.finfo(float).eps * max(n, current['p'])
                     * max(float(np.linalg.norm(y)), 1.0))
        mse = current['sse'] / current['df']
        if not np.isfinite(mse) or current['sse'] <= tolerance ** 2:
            stop_reason = 'zero_error_variance'
            break
        if method == 'information_criteria' and not criterion_path:
            value = _information_criterion(current['sse'], n, current['rank'], criterion)
            if value is None:
                stop_reason = 'information_criterion_unavailable'
                break
            best_terms, best_criterion = list(terms), value
            criterion_path.append({'step': 0, 'terms': tuple(terms),
                                   'rank': current['rank'], 'error_df': current['df'],
                                   'sse': current['sse'], 'k': current['rank'],
                                   'value': value})
            if current['df'] <= 1:
                stop_reason = 'residual_df_limit'
                break

        if method in ('stepwise', 'backward'):
            removals, removal_evaluations, rank_blocked_removal = [], [], 0
            for term in terms:
                if term in forced_terms:
                    removal_evaluations.append({'term': term, 'label': _label(term),
                                                'p_value': None, 'status': 'forced'})
                    continue
                reduced = [item for item in terms if item != term]
                if not _hierarchical(reduced):
                    removal_evaluations.append({'term': term, 'label': _label(term),
                                                'p_value': None, 'status': 'hierarchy_required'})
                    continue
                trial = evaluate(reduced)
                df_removed = current['rank'] - trial['rank']
                if df_removed <= 0:
                    rank_blocked_removal += 1
                    removal_evaluations.append({'term': term, 'label': _label(term),
                                                'p_value': None, 'status': 'rank_deficient'})
                    continue
                f = ((trial['sse'] - current['sse']) / df_removed) / mse
                p_value = _p_value(f, df_removed, current['df'])
                removals.append({'term': term, 'f': float(f), 'df': df_removed,
                                 'sse': trial['sse'], 'rank': trial['rank'],
                                 'p_value': p_value})
                removal_evaluations.append({'term': term, 'label': _label(term),
                                            'f': float(f), 'p_value': p_value,
                                            'criterion_value': None,
                                            'error_df': current['df'],
                                            'status': 'eligible' if p_value is not None else
                                            'p_value_unavailable'})
            candidate_path.append({'step': len(steps) + 1, 'action': 'remove',
                                   'current_terms': tuple(terms),
                                   'candidates': removal_evaluations})
            candidates_removal = [row for row in removals if row['p_value'] is not None]
            if candidates_removal:
                removed = max(candidates_removal,
                              key=lambda row: (row['p_value'], -position[row['term']]))
                if removed['p_value'] > alpha_remove:
                    steps.append({
                        'step': len(steps) + 1, 'action': 'remove',
                        'term': removed['term'], 'label': _label(removed['term']),
                        'f': removed['f'], 'p': removed['p_value'],
                        'df_changed': removed['df'],
                        'sse_before': current['sse'], 'sse_after': removed['sse'],
                        'rank_before': current['rank'], 'rank_after': removed['rank'],
                        'error_df': n - removed['rank'],
                        'terms': [item for item in terms if item != removed['term']],
                        'criterion': 'p_value', 'criterion_before': None,
                        'criterion_after': None,
                        'candidate_evaluations': removal_evaluations,
                    })
                    terms = [item for item in terms if item != removed['term']]
                    continue
                if method == 'backward':
                    stop_reason = 'selection_stable'
                    break
            elif method == 'backward':
                stop_reason = ('initial_model_rank_deficient'
                               if rank_blocked_removal and not steps else
                               'rank_deficiency' if rank_blocked_removal
                               else 'no_eligible_removal')
                break

        remaining = [term for term in order if term not in terms]
        entries, entry_evaluations, rank_blocked, df_blocked = [], [], 0, 0
        ic_blocked = zero_variance_blocked = 0
        for term in remaining:
            evaluation = {'term': term, 'label': _label(term), 'f': None,
                           'p_value': None, 'criterion_value': None,
                           'status': 'eligible'}
            trial_terms = terms + [term]
            if not _hierarchical(trial_terms):
                evaluation['status'] = 'hierarchy_required'
                entry_evaluations.append(evaluation)
                continue
            if not dimension(term, terms):
                rank_blocked += 1
                evaluation['status'] = 'rank_deficient'
                entry_evaluations.append(evaluation)
                continue
            trial = evaluate(trial_terms)
            df_added = trial['rank'] - current['rank']
            trial_df = n - trial['rank']
            evaluation.update({'rank': trial['rank'], 'error_df': trial_df,
                               'sse': trial['sse'], 'df_changed': df_added})
            if df_added <= 0:
                rank_blocked += 1
                evaluation['status'] = 'rank_deficient'
                entry_evaluations.append(evaluation)
                continue
            if trial_df < 1:
                df_blocked += 1
                evaluation['status'] = 'residual_df_limit'
                entry_evaluations.append(evaluation)
                continue
            if (method == 'information_criteria' and criterion == 'aicc'
                    and trial_df <= 1):
                ic_blocked += 1
                evaluation['status'] = 'information_criterion_unavailable'
                entry_evaluations.append(evaluation)
                continue
            trial_mse = trial['sse'] / trial_df
            if not np.isfinite(trial_mse) or trial_mse <= 0:
                zero_variance_blocked += 1
                evaluation['status'] = 'zero_error_variance'
                entry_evaluations.append(evaluation)
                continue
            f = ((current['sse'] - trial['sse']) / df_added) / trial_mse
            if method == 'information_criteria' and trial['sse'] <= tolerance ** 2:
                zero_variance_blocked += 1
                evaluation['status'] = 'zero_error_variance'
                entry_evaluations.append(evaluation)
                continue
            value = (_information_criterion(trial['sse'], n, trial['rank'], criterion)
                     if method == 'information_criteria' else None)
            if method == 'information_criteria' and value is None:
                ic_blocked += 1
                evaluation['status'] = 'information_criterion_unavailable'
                entry_evaluations.append(evaluation)
                continue
            p_value = _p_value(f, df_added, trial_df)
            evaluation.update({'f': float(f), 'p_value': p_value,
                               'criterion_value': value, 'k': trial['rank'],
                               'status': 'eligible' if p_value is not None else
                               'p_value_unavailable'})
            entry_evaluations.append(evaluation)
            entries.append({'term': term, 'f': float(f), 'df': df_added,
                            'sse': trial['sse'], 'rank': trial['rank'],
                            'p_value': p_value,
                            'criterion_value': value})
        candidate_path.append({'step': len(steps) + 1, 'action': 'enter',
                               'current_terms': tuple(terms),
                               'candidates': entry_evaluations})
        candidates_entry = [row for row in entries if row['p_value'] is not None]
        if method == 'information_criteria' and zero_variance_blocked:
            stop_reason = 'zero_error_variance'
            break
        if candidates_entry:
            entered = min(candidates_entry,
                          key=lambda row: (row['p_value'], position[row['term']]))
            enters = (method == 'information_criteria' or
                      entered['p_value'] < alpha_enter)
            if enters:
                # 保留进入顺序：步骤历史与最终项集合都按实际选入次序展示。
                terms = terms + [entered['term']]
                step = {
                    'step': len(steps) + 1, 'action': 'enter',
                    'term': entered['term'], 'label': _label(entered['term']),
                    'f': entered['f'], 'p': entered['p_value'],
                    'df_changed': entered['df'],
                    'sse_before': current['sse'], 'sse_after': entered['sse'],
                    'rank_before': current['rank'], 'rank_after': entered['rank'],
                    'error_df': n - entered['rank'],
                    'terms': list(terms),
                    'criterion': criterion if method == 'information_criteria' else 'p_value',
                    'criterion_before': (criterion_path[-1]['value']
                                         if method == 'information_criteria' else None),
                    'criterion_after': entered['criterion_value'],
                    'candidate_evaluations': entry_evaluations,
                }
                steps.append(step)
                if method == 'information_criteria':
                    value = entered['criterion_value']
                    step.update({'criterion_value': value,
                                 'k': entered['rank']})
                    criterion_path.append({'step': len(steps), 'terms': tuple(terms),
                                           'rank': entered['rank'],
                                           'error_df': n - entered['rank'],
                                           'sse': entered['sse'],
                                           'k': entered['rank'], 'value': value})
                    if value < best_criterion:
                        best_terms, best_criterion = list(terms), value
                    if n - entered['rank'] <= 1:
                        stop_reason = 'residual_df_limit'
                        break
                continue
        # 顺序：可进入项耗尽 → 不可估计项 → 残差自由度 → 无显著项。
        # 纯不可估计项即使已无可加入项也必须如实报告，不能伪装成稳定结束。
        if method == 'information_criteria' and ic_blocked and not candidates_entry:
            stop_reason = 'information_criterion_unavailable'
        elif not candidates_entry and rank_blocked:
            stop_reason = 'rank_deficiency'
        elif not candidates_entry and df_blocked:
            stop_reason = 'residual_df_limit'
        elif method == 'information_criteria' and not remaining:
            stop_reason = 'full_model'
        elif method == 'forward' and candidates_entry:
            stop_reason = 'selection_stable'
        elif not remaining:
            stop_reason = 'selection_stable'
        else:
            stop_reason = 'no_eligible_entry'
        break
    else:
        stop_reason = 'iteration_budget'

    final_terms = best_terms if method == 'information_criteria' and best_terms is not None else terms
    final = evaluate(final_terms)
    analysis = analyze_dsd(frame, metadata, response, tuple(final_terms))
    if analysis['rank'] != final['rank'] or abs(analysis['sse'] - final['sse']) > 1e-9 * max(1.0, final['sse']):
        raise ValueError('选择结果与最终模型重分析不一致')
    active_criterion = criterion if method == 'information_criteria' else 'p_value'
    return {
        'method': method, 'criterion': active_criterion,
        'criterion_definition': (
            '正态误差 OLS 最大似然；k = rank(X)，含截距、所选项及区组系数，不含残差尺度参数。'
            if method == 'information_criteria' else '偏 F 检验 p 值'),
        'alpha_enter': alpha_enter,
        'alpha_remove': alpha_remove,
        'initial_terms': tuple(initial), 'forced_terms': tuple(forced),
        'candidate_terms': tuple(order), 'selected_terms': tuple(final_terms),
        'selection_steps': steps, 'stop_reason': stop_reason,
        'candidate_path': candidate_path, 'criterion_path': criterion_path,
        'best_criterion': best_criterion,
        'iterations': len(steps), 'final_rank': final['rank'],
        'final_residual_df': n - final['rank'],
        'selection_status': ('stable' if stop_reason in
                             ('no_eligible_entry', 'selection_stable') else stop_reason),
        'analysis': analysis,
        'note': ('选择后的系数 p 值、置信区间与效应为未校正模型选择偏差的名义统计量，'
                 '不构成独立确认性检验。'),
    }
