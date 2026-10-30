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


def select_dsd_stepwise(frame, metadata, response, *, alpha_enter=DEFAULT_ALPHA,
                        alpha_remove=DEFAULT_ALPHA, candidates=None,
                        initial=None, forced=None, max_steps=DEFAULT_MAX_STEPS):
    """按部分 F 检验逐步选择 DSD 模型项。"""
    design = restore_design_result(frame, metadata)
    validate_dsd(design)
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
    terms = [term for term in order if term in set(initial) | set(forced)]
    if not _hierarchical(terms):
        raise ValueError('初始项与强制保留项不满足强层级结构')
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

    def _exact_rank(matrix):
        """按修正 Gram–Schmidt 逐列计数可估计维度。

        ``_fit`` 的奇异值截断会把近似相关的列当成独立，在饱和边界与精确
        参考不一致；这里用同一列顺序做正交化，秩与残差自由度由此统一。
        """
        basis = []
        tolerance = 1e-10
        for index in range(matrix.shape[1]):
            column = matrix[:, index].astype(float)
            scale = float(np.max(np.abs(column)))
            if scale == 0:
                continue
            for vector in basis:
                column = column - (vector @ column) * vector
            norm = float(np.linalg.norm(column))
            if norm > tolerance * scale:
                basis.append(column / norm)
        return len(basis)

    def evaluate(selected):
        matrix = _columns(selected)
        beta, _, _, p, fitted, residuals, sse, sst, ssr, _, inference, status, details = (
            _fit(coded, y, names, selected, block_columns, allow_rank_deficiency=True))
        rank = _exact_rank(matrix)
        return {'rank': rank, 'sse': float(sse), 'p': p, 'df': n - rank,
                'beta': beta, 'fitted': fitted}

    def dimension(term, selected):
        """候选项在“截距 + 已选项 + 区组”之上新增的实际维度。"""
        base = _columns(selected)
        column = np.prod(coded[:, [names.index(name) for name in term]], axis=1)
        return (_exact_rank(np.column_stack([base, column])) -
                _exact_rank(base))

    steps, visited = [], set()
    stop_reason = None
    for iteration in range(1, int(max_steps) + 1):
        state = frozenset(terms)
        if state in visited:
            stop_reason = 'model_cycle_detected'
            break
        visited.add(state)
        current = evaluate(terms)
        if current['df'] < 1:
            stop_reason = 'residual_df_limit'
            break
        tolerance = (np.finfo(float).eps * max(n, current['p'])
                     * max(float(np.linalg.norm(y)), 1.0))
        mse = current['sse'] / current['df']
        if not np.isfinite(mse) or current['sse'] <= tolerance ** 2:
            stop_reason = 'zero_error_variance'
            break

        removals = []
        for term in terms:
            if term in forced_terms:
                continue
            reduced = [item for item in terms if item != term]
            if not _hierarchical(reduced):
                continue
            trial = evaluate(reduced)
            df_removed = current['rank'] - trial['rank']
            if df_removed <= 0:
                continue
            f = ((trial['sse'] - current['sse']) / df_removed) / mse
            removals.append({'term': term, 'f': float(f), 'df': df_removed,
                             'sse': trial['sse'], 'rank': trial['rank'],
                             'p_value': _p_value(f, df_removed, current['df'])})
        if removals:
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
                    })
                    terms = [item for item in terms if item != removed['term']]
                    continue

        remaining = [term for term in order if term not in terms]
        entries, rank_blocked, df_blocked = [], 0, 0
        for term in remaining:
            trial_terms = terms + [term]
            if not _hierarchical(trial_terms):
                continue
            if not dimension(term, terms):
                rank_blocked += 1
                continue
            trial = evaluate(trial_terms)
            df_added = trial['rank'] - current['rank']
            trial_df = n - trial['rank']
            if df_added <= 0:
                rank_blocked += 1
                continue
            if trial_df < 1:
                df_blocked += 1
                continue
            trial_mse = trial['sse'] / trial_df
            if not np.isfinite(trial_mse) or trial_mse <= 0:
                continue
            f = ((current['sse'] - trial['sse']) / df_added) / trial_mse
            entries.append({'term': term, 'f': float(f), 'df': df_added,
                            'sse': trial['sse'], 'rank': trial['rank'],
                            'p_value': _p_value(f, df_added, trial_df)})
        candidates_entry = [row for row in entries if row['p_value'] is not None]
        if candidates_entry:
            entered = min(candidates_entry,
                          key=lambda row: (row['p_value'], position[row['term']]))
            if entered['p_value'] < alpha_enter:
                # 保留进入顺序：步骤历史与最终项集合都按实际选入次序展示。
                terms = terms + [entered['term']]
                steps.append({
                    'step': len(steps) + 1, 'action': 'enter',
                    'term': entered['term'], 'label': _label(entered['term']),
                    'f': entered['f'], 'p': entered['p_value'],
                    'df_changed': entered['df'],
                    'sse_before': current['sse'], 'sse_after': entered['sse'],
                    'rank_before': current['rank'], 'rank_after': entered['rank'],
                    'error_df': n - entered['rank'],
                    'terms': list(terms),
                })
                continue
        # 顺序：可进入项耗尽 → 不可估计项 → 残差自由度 → 无显著项。
        # 纯不可估计项即使已无可加入项也必须如实报告，不能伪装成稳定结束。
        if not candidates_entry and rank_blocked:
            stop_reason = 'rank_deficiency'
        elif not candidates_entry and df_blocked:
            stop_reason = 'residual_df_limit'
        elif not remaining:
            stop_reason = 'selection_stable'
        else:
            stop_reason = 'no_eligible_entry'
        break
    else:
        stop_reason = 'iteration_budget'

    final = evaluate(terms)
    analysis = analyze_dsd(frame, metadata, response, tuple(terms))
    if analysis['rank'] != final['rank'] or abs(analysis['sse'] - final['sse']) > 1e-9 * max(1.0, final['sse']):
        raise ValueError('选择结果与最终模型重分析不一致')
    return {
        'method': 'stepwise', 'alpha_enter': alpha_enter,
        'alpha_remove': alpha_remove,
        'initial_terms': tuple(initial), 'forced_terms': tuple(forced),
        'candidate_terms': tuple(order), 'selected_terms': tuple(terms),
        'selection_steps': steps, 'stop_reason': stop_reason,
        'iterations': len(steps), 'final_rank': final['rank'],
        'final_residual_df': n - final['rank'],
        'selection_status': ('stable' if stop_reason in
                             ('no_eligible_entry', 'selection_stable') else stop_reason),
        'analysis': analysis,
        'note': ('选择后的系数 p 值、置信区间与效应为未校正模型选择偏差的名义统计量，'
                 '不构成独立确认性检验。'),
    }
