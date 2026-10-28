"""混料模型点预测：先核验全部真实约束，再使用当前拟合快照。"""
from __future__ import annotations

from doe_mixture import MixtureSpec
from doe_mixture_analysis import analyze_mixture
from doe_mixture_constraints import (
    MixtureConstraintError, check_point, normalize_proportions,
)
from doe_mixture_model import predict_row


def predict_mixture(frame, metadata, response, proportions, process=None,
                    amount=None, terms=None, degree=2):
    """给定实际组分比例与工艺条件，返回预测及模型范围。"""
    analysis = analyze_mixture(frame, metadata, response, terms, degree)
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
    prediction = predict_row(analysis['model'], analysis['coefficients'], settings)
    return {
        'response': response, 'prediction': prediction, 'settings': settings,
        'proportions': dict(settings), 'terms': analysis['terms'],
        'model': analysis['model'], 'spec': spec,
        'snapshot_id': analysis['snapshot_id'],
        'model_range': {item.component_id: [item.lower, item.upper]
                        for item in spec.components},
        'status': analysis['status'],
        'note': '点预测来自当前拟合模型；组分比例与过程/总量条件已核验。',
    }
