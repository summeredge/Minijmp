"""混料模型点预测：先核验全部真实约束，再使用当前拟合快照。"""
from __future__ import annotations

import math

import numpy as np
from scipy import stats

from doe_mixture import MixtureSpec
from doe_mixture_analysis import analyze_mixture
from doe_mixture_constraints import (
    MixtureConstraintError, actual_amounts, check_point, normalize_proportions,
)
from doe_mixture_model import predict_row


def _validate_confidence(confidence):
    if (isinstance(confidence, bool) or not isinstance(confidence, (int, float))
            or not math.isfinite(confidence) or not 0 < confidence < 1):
        raise ValueError('置信水平必须是 0 与 1 之间的比例')
    return float(confidence)


def _mixture_prediction_intervals(analysis, row, confidence):
    """对固定 Scheffé 模型点计算均值 CI 与单次观测 PI。"""
    result = {
        'status': '不可用', 'reason': '', 'confidence': confidence,
        'df': analysis['df'], 'h0': None, 'se_fit': None,
        'ci_low': None, 'ci_high': None, 'pi_low': None, 'pi_high': None,
        'critical_value': None,
        'assumption': 'Scheffé 无截距模型；误差独立、同方差且正态；按固定设定点计算。',
    }
    if row is None:
        result['reason'] = '没有满足约束的优化点。'
        return result
    if analysis['rank'] < analysis['p']:
        result['reason'] = 'Scheffé 模型秩亏、不可估，区间不可用。'
        return result
    df = analysis['df']
    if df <= 0:
        result['reason'] = '残差自由度不为正，无法估计误差方差。'
        return result
    mse = analysis['sse'] / df
    response = np.asarray(analysis['fitted']) + np.asarray(analysis['residuals'])
    epsilon = np.finfo(float).eps
    scale = max(analysis['n'], analysis['p'])
    mse_floor = max(epsilon * scale * max(0.0, analysis['sst']),
                    (epsilon * scale * float(np.linalg.norm(response))) ** 2)
    if not math.isfinite(mse) or analysis['sse'] <= mse_floor:
        result['reason'] = '残差方差为零或数值上不可辨。'
        return result
    try:
        matrix = analysis['model'].matrix(analysis['settings'])
        solution = np.linalg.lstsq(matrix.T, np.asarray(row, dtype=float), rcond=None)[0]
        h0 = float(solution @ solution)
    except (ValueError, np.linalg.LinAlgError, OverflowError) as error:
        result['reason'] = f'无法稳定计算预测方差：{error}'
        return result
    if not math.isfinite(h0) or h0 < 0:
        result['reason'] = '预测方差因子不是有限非负数。'
        return result
    prediction = float(np.asarray(row, dtype=float) @ analysis['coefficients'])
    critical = float(stats.t.ppf((1 + confidence) / 2, df))
    se_fit = math.sqrt(mse * h0)
    se_prediction = math.sqrt(mse * (1 + h0))
    margins = critical * se_fit, critical * se_prediction
    bounds = (prediction - margins[0], prediction + margins[0],
              prediction - margins[1], prediction + margins[1])
    if not math.isfinite(critical) or not all(math.isfinite(value) for value in bounds):
        result['reason'] = '指定置信水平的区间超出有限数值范围。'
        return result
    result.update(status='可用', h0=h0, se_fit=se_fit,
                  ci_low=bounds[0], ci_high=bounds[1],
                  pi_low=bounds[2], pi_high=bounds[3],
                  critical_value=critical)
    return result


def predict_mixture(frame, metadata, response, proportions, process=None,
                    amount=None, terms=None, degree=2, *, doe_metadata=None,
                    confidence=0.95):
    """给定实际组分比例与工艺条件，返回点预测、模型区间及模型范围。"""
    confidence = _validate_confidence(confidence)
    analysis = analyze_mixture(frame, metadata, response, terms, degree,
                               doe_metadata=doe_metadata)
    spec = analysis['spec']
    if not isinstance(proportions, (list, tuple, dict)):
        raise MixtureConstraintError('组分比例必须是列表或映射')
    if isinstance(proportions, dict):
        missing = [item.component_id for item in spec.components
                   if item.component_id not in proportions]
        unknown = set(proportions) - set(spec.component_ids)
        if missing or unknown:
            raise MixtureConstraintError('组分比例必须覆盖全部组分且不含未知组分')
        values = [proportions[item.component_id] for item in spec.components]
    else:
        values = list(proportions)
    values = normalize_proportions(spec.components, values)
    check_point(spec.components, spec.linear_constraints, values)
    settings = {component.component_id: value
                for component, value in zip(spec.components, values)}
    process = {} if process is None else process
    if not isinstance(process, dict):
        raise MixtureConstraintError('过程变量设定必须是映射')
    for variable in spec.process_variables:
        if variable.variable_id not in process:
            raise MixtureConstraintError(f'缺少过程变量设定：{variable.variable_id}')
        settings[variable.variable_id] = process[variable.variable_id]
    amount = {} if amount is None else amount
    if not isinstance(amount, dict):
        raise MixtureConstraintError('总量设定必须是映射')
    declared = dict(spec.amount_settings)
    for variable in spec.amount_variables:
        settings[variable.variable_id] = amount.get(variable.variable_id,
                                                    declared[variable.variable_id])
    # 变量范围由 to_coded 再次核验，非有限值在编码/预测处拒绝。
    row = analysis['model'].row(settings)
    prediction = predict_row(analysis['model'], analysis['coefficients'], settings)
    intervals = _mixture_prediction_intervals(analysis, row, confidence)
    amounts = None
    if spec.amount_variables:
        total = settings[spec.amount_variables[0].variable_id]
        if total > 0:
            amounts = dict(zip(spec.component_ids, actual_amounts(values, total)))
    proportion_map = dict(zip(spec.component_ids, values))
    return {
        'response': response, 'prediction': prediction, 'settings': settings,
        'intervals': intervals,
        'proportions': proportion_map, 'actual_amounts': amounts,
        'terms': analysis['terms'],
        'model': analysis['model'], 'spec': spec,
        'snapshot_id': analysis['snapshot_id'],
        'model_range': {item.component_id: [item.lower, item.upper]
                        for item in spec.components},
        'status': analysis['status'],
        'note': ('点预测来自当前拟合模型；CI/PI 按固定设定点计算；'
                 '组分比例与过程/总量条件已核验。'),
    }
