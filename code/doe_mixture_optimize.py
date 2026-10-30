"""混料可行域内的单/多响应优化；不宣称全局最优。"""
from __future__ import annotations

import math

import numpy as np
from scipy.optimize import minimize

from doe_mixture_analysis import analyze_mixture
from doe_mixture_constraints import (
    MixtureConstraintError, TOLERANCE, actual_amounts, check_point,
    normalize_proportions,
)
from doe_mixture_model import predict_row


def _objective_config(item, spec):
    if not isinstance(item, dict):
        raise MixtureConstraintError('响应目标定义无效')
    response = item.get('response')
    if response not in spec.response_names:
        raise MixtureConstraintError('优化目标含未知响应')
    goal = item.get('goal')
    if goal not in ('maximize', 'minimize', 'target'):
        raise MixtureConstraintError('优化目标必须是 maximize、minimize 或 target')
    lower = item.get('lower')
    upper = item.get('upper')
    if lower is None or upper is None or not math.isfinite(lower) or not math.isfinite(upper) \
            or lower >= upper:
        raise MixtureConstraintError('优化目标需要有效 lower < upper')
    target = item.get('target')
    if goal == 'target':
        if target is None or not math.isfinite(target) or not lower < target < upper:
            raise MixtureConstraintError('逼近目标必须满足 lower < target < upper')
    elif target is not None:
        raise MixtureConstraintError('仅逼近目标提供 target')
    weight = item.get('weight', 1.0)
    if not isinstance(weight, (int, float)) or isinstance(weight, bool) \
            or not math.isfinite(weight) or not 0.1 <= weight <= 10:
        raise MixtureConstraintError('期望权重必须在 0.1 到 10 之间')
    return {'response': response, 'goal': goal, 'lower': float(lower),
            'upper': float(upper),
            'target': None if target is None else float(target),
            'weight': float(weight)}


def _desirability(value, config):
    lower, upper = config['lower'], config['upper']
    if config['goal'] == 'maximize':
        d = (value - lower) / (upper - lower)
    elif config['goal'] == 'minimize':
        d = (upper - value) / (upper - lower)
    else:
        target = config['target']
        d = ((value - lower) / (target - lower) if value <= target
             else (upper - value) / (upper - target))
    return float(np.clip(d, 0.0, 1.0) ** config['weight'])


def optimize_mixture(frame, metadata, objectives, conditions=None, terms=None,
                     degree=2, starts=None, *, doe_metadata=None):
    """在组分约束与固定工艺条件下优化；返回求解状态与真实残差。"""
    analyses = []
    for item in objectives:
        analyses.append(analyze_mixture(
            frame, metadata, item['response'], terms, degree,
            doe_metadata=doe_metadata))
    spec = analyses[0]['spec']
    if any(item['spec'].to_dict() != spec.to_dict() for item in analyses):
        raise MixtureConstraintError('多响应不属于同一混料设计')
    configs = [_objective_config(item, spec) for item in objectives]
    if len({config['response'] for config in configs}) != len(configs):
        raise MixtureConstraintError('同一响应不能重复优化')
    fixed = {}
    for variable in spec.process_variables:
        if conditions is None or variable.variable_id not in conditions:
            raise MixtureConstraintError(f'缺少过程变量条件：{variable.variable_id}')
        fixed[variable.variable_id] = conditions[variable.variable_id]
    declared = dict(spec.amount_settings)
    for variable in spec.amount_variables:
        fixed[variable.variable_id] = (declared[variable.variable_id]
                                       if conditions is None
                                       else conditions.get(variable.variable_id,
                                                           declared[variable.variable_id]))

    def settings(point):
        result = {component.component_id: float(value)
                  for component, value in zip(spec.components, point)}
        result.update(fixed)
        return result

    def predictions(point):
        row = settings(point)
        return [predict_row(analysis['model'], analysis['coefficients'], row)
                for analysis in analyses]

    lower = np.asarray([item.lower for item in spec.components])
    upper = np.asarray([item.upper for item in spec.components])
    constraints = [{'type': 'eq', 'fun': lambda x: float(np.sum(x) - 1)}]
    for constraint in spec.linear_constraints:
        weights = np.asarray([constraint.coefficients.get(item.component_id, 0.0)
                              for item in spec.components])
        constraints.append({'type': 'ineq',
                            'fun': lambda x, w=weights, b=constraint.bound:
                            float(b - w @ x)})

    if starts is None:
        candidates = [np.asarray(item['proportions']) for item in analyses[0]['rows']]
        centroid = np.asarray([(item.lower + item.upper) / 2 for item in spec.components])
        candidates.append(centroid)
    else:
        candidates = [np.asarray(point, dtype=float) for point in starts]
    feasible_starts = []
    for candidate in candidates:
        if candidate.shape != lower.shape or not np.isfinite(candidate).all():
            continue
        try:
            candidate = np.asarray(normalize_proportions(spec.components, candidate))
            check_point(spec.components, spec.linear_constraints, candidate)
        except MixtureConstraintError:
            continue
        feasible_starts.append(candidate)
    if not feasible_starts:
        raise MixtureConstraintError('组分约束没有可行起点，无法优化')

    single = len(configs) == 1

    def score(point):
        predicted = predictions(point)
        if single:
            config = configs[0]
            value = predicted[0]
            if config['goal'] == 'maximize':
                return -value, predicted, 0.0
            if config['goal'] == 'minimize':
                return value, predicted, 0.0
            return (value - config['target']) ** 2, predicted, 0.0
        values = [_desirability(value, config)
                  for value, config in zip(predicted, configs)]
        if min(values) <= 0:
            return 1.0, predicted, 0.0
        aggregate = float(np.prod(values) ** (1 / len(values)))
        return -aggregate, predicted, aggregate

    best = None
    for start in feasible_starts:
        result = minimize(lambda x: score(x)[0], start, method='SLSQP',
                          bounds=list(zip(lower, upper)), constraints=constraints,
                          options={'maxiter': 500, 'ftol': 1e-12})
        point = np.asarray(result.x, dtype=float)
        try:
            point = np.asarray(normalize_proportions(spec.components, point))
            check_point(spec.components, spec.linear_constraints, point)
            objective, predicted, aggregate = score(point)
            feasible = True
        except (MixtureConstraintError, FloatingPointError):
            feasible = False
            objective = math.inf
            predicted, aggregate = [], 0.0
        candidate = {'success': bool(result.success), 'feasible': feasible,
                     'message': str(result.message), 'point': point,
                     'settings': settings(point) if feasible else None,
                     'predictions': predicted, 'objective': objective,
                     'aggregate': aggregate, 'nit': int(result.nit)}
        if best is None or (feasible and candidate['objective'] < best['objective']):
            best = candidate
    point = best['point']
    residual = 0.0
    if best['feasible']:
        residual = max(residual, abs(float(np.sum(point)) - 1))
        for value, low, high in zip(point, lower, upper):
            residual = max(residual, low - float(value), float(value) - high)
        for constraint in spec.linear_constraints:
            weights = np.asarray([constraint.coefficients.get(item.component_id, 0.0)
                                  for item in spec.components])
            residual = max(residual, float(weights @ point - constraint.bound))
    configurations = [dict(config) for config in configs]
    for config, value in zip(configurations, best['predictions']):
        config['prediction'] = value
        if not single:
            config['desirability'] = _desirability(value, config)
    aggregate = best['aggregate'] if not single else None
    actual = None
    if best['feasible'] and spec.amount_variables:
        total = best['settings'][spec.amount_variables[0].variable_id]
        if total > 0:
            actual = dict(zip(
                spec.component_ids,
                actual_amounts([best['settings'][key] for key in spec.component_ids], total)))
    if single and best['predictions']:
        if configs[0]['goal'] == 'target':
            objective_value = abs(best['predictions'][0] - configs[0]['target'])
        else:
            objective_value = best['predictions'][0]
    elif not single:
        objective_value = aggregate
    else:
        objective_value = None
    if not single and aggregate is not None and aggregate <= 0:
        status = '综合期望为 0：至少一个响应未进入目标区间'
    elif best['feasible'] and best['success']:
        status = '求解器收敛；结果依赖起点与局部搜索，不宣称全局最优'
    elif best['feasible']:
        status = '求解器未确认收敛；返回满足约束的当前最优候选'
    else:
        status = '没有找到满足全部约束的候选点'
    return {
        'success': bool(best['success'] and best['feasible']),
        'feasible': best['feasible'], 'status': status,
        'message': best['message'], 'components': {
            item.component_id: float(value)
            for item, value in zip(spec.components, point)},
        'settings': best['settings'], 'predictions': best['predictions'],
        'actual_amounts': actual,
        'objectives': configurations,
        'objective': (None if not best['feasible'] or objective_value is None
                      else float(objective_value)),
        'solver_objective': (None if not best['feasible']
                             else float(best['objective'])),
        'aggregate_desirability': aggregate if not single else None,
        'constraint_residual': float(residual), 'nit': best['nit'],
        'starts': len(feasible_starts), 'global_claim': False,
        'note': '目标函数来自当前拟合模型；约束残差按总和、上下界与线性不等式计算。',
    }
