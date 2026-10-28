"""混料图形采样：Trace、Ternary 等高线/曲面与叠加可行域。"""
from __future__ import annotations

import math

import numpy as np

from doe_mixture_constraints import (
    MixtureConstraintError, TOLERANCE, check_point,
)
from doe_mixture_model import predict_row


def _conditions(spec, conditions):
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
    return fixed


def _reference(spec, reference):
    if reference is None:
        values = [(item.lower + item.upper) / 2 for item in spec.components]
        total = sum(values)
        values = [value / total for value in values]
    elif isinstance(reference, dict):
        values = [reference[item.component_id] for item in spec.components]
    else:
        values = list(reference)
    check_point(spec.components, spec.linear_constraints, values)
    return dict(zip(spec.component_ids, values))


def trace_series(spec, model, coefficients, reference, component_id, *,
                 steps=41, conditions=None):
    """保持其余组分相对比例，改变一个组分；跳过不可行采样点。"""
    if component_id not in spec.component_ids:
        raise MixtureConstraintError('Trace 组分不在当前混料设计中')
    reference = _reference(spec, reference)
    if component_id not in reference:
        raise MixtureConstraintError('参考混合物缺少 Trace 组分')
    start_value = reference[component_id]
    if start_value >= 1 - TOLERANCE:
        raise MixtureConstraintError('参考混合物中该组分占满全部比例，不能改变')
    component = spec.component(component_id)
    fixed = _conditions(spec, conditions)
    points, values, skipped = [], [], 0
    for value in np.linspace(component.lower, component.upper, int(steps)):
        factor = (1 - float(value)) / (1 - start_value)
        point = {item.component_id:
                 (float(value) if item.component_id == component_id
                  else reference[item.component_id] * factor)
                 for item in spec.components}
        try:
            check_point(spec.components, spec.linear_constraints,
                        [point[item.component_id] for item in spec.components])
        except MixtureConstraintError:
            skipped += 1
            continue
        settings = dict(point)
        settings.update(fixed)
        points.append(point)
        values.append(predict_row(model, coefficients, settings))
    if len(points) < 2:
        raise MixtureConstraintError('该组分范围内没有足够的可行 Trace 点')
    return {'component': component_id, 'reference': reference,
            'points': points, 'values': values, 'skipped': skipped,
            'rule': '其余组分按参考比例缩放，总和保持为 1'}


def ternary_xy(point):
    """三组分重心坐标到平面：C 在顶部，B 在右下。"""
    return float(point[1] + 0.5 * point[2]), float(math.sqrt(3) / 2 * point[2])


def simplex_grid(spec, model, coefficients, *, axes=None, reference=None,
                 steps=21, conditions=None):
    """合法三组分面或高维混料切片；不可行点保留掩码，不填响应。"""
    if steps < 2:
        raise MixtureConstraintError('网格步数至少为 2')
    fixed = _conditions(spec, conditions)
    q = len(spec.components)
    if q < 3:
        raise MixtureConstraintError('双组分混料只有一维可行曲线，请使用 Trace 图')
    if axes is None:
        axes = (spec.component_ids[1], spec.component_ids[0])
    if len(axes) != 2 or axes[0] == axes[1] or any(
            item not in spec.component_ids for item in axes):
        raise MixtureConstraintError('需要两个不同的切片组分')
    first, second = axes
    remaining = 1.0
    fixed_components = {}
    free = [item.component_id for item in spec.components
            if item.component_id not in (first, second)]
    third = free[-1]
    if q > 3:
        reference = _reference(spec, reference)
        fixed_components = {component_id: reference[component_id]
                            for component_id in free[:-1]}
        remaining = 1 - sum(fixed_components.values())
        if remaining <= TOLERANCE:
            raise MixtureConstraintError('固定组分已占满全部比例，切片为空')
    points, feasible, predicted = [], [], []
    n = int(steps)
    for i in range(n + 1):
        for j in range(n + 1 - i):
            point = {item.component_id: 0.0 for item in spec.components}
            point.update(fixed_components)
            point[first] = i / n * remaining
            point[second] = j / n * remaining
            point[third] = remaining - point[first] - point[second]
            try:
                check_point(spec.components, spec.linear_constraints,
                            [point[item.component_id] for item in spec.components])
                ok = True
            except MixtureConstraintError:
                ok = False
            points.append(point)
            feasible.append(ok)
            if ok:
                settings = dict(point)
                settings.update(fixed)
                predicted.append(predict_row(model, coefficients, settings))
            else:
                predicted.append(float('nan'))
    grid = {'points': points, 'feasible': np.asarray(feasible, dtype=bool),
            'values': np.asarray(predicted, dtype=float), 'axes': axes,
            'steps': n, 'remaining': remaining, 'fixed': fixed_components,
            'row_lengths': [n + 1 - i for i in range(n + 1)]}
    if q == 3:
        grid['xy'] = np.asarray([ternary_xy([point[item.component_id]
                                             for item in spec.components])
                                 for point in points])
    else:
        grid['xy'] = np.asarray([[point[first], point[second]] for point in points])
    return grid


def overlay_grid(spec, models, coefficients, limits, *, axes=None, reference=None,
                 steps=21, conditions=None):
    """多个响应的区间可行集合交集；空交集显式返回。"""
    if len(models) != len(limits):
        raise MixtureConstraintError('响应模型与区间数量不一致')
    base = simplex_grid(spec, models[0], coefficients[0], axes=axes,
                        reference=reference, steps=steps, conditions=conditions)
    masks = []
    for model, beta, limit in zip(models, coefficients, limits):
        predicted = np.asarray([
            predict_row(model, beta, {**point, **_conditions(spec, conditions)})
            if ok else np.nan
            for point, ok in zip(base['points'], base['feasible'])])
        low, high = limit
        if not low < high:
            raise MixtureConstraintError('叠加等高线响应上下限必须 low < high')
        masks.append((predicted >= low) & (predicted <= high))
    intersection = np.logical_and.reduce(masks + [base['feasible']])
    return {'grid': base, 'masks': masks, 'intersection': intersection,
            'count': int(intersection.sum()), 'empty': not bool(intersection.any()),
            'limits': list(limits)}


def surface_data(spec, model, coefficients, **kwargs):
    return simplex_grid(spec, model, coefficients, **kwargs)


def grid_triangulation(grid):
    """屏蔽含不可行顶点的三角形，避免图形跨不可行区域插值。"""
    import matplotlib.tri as mtri
    triangulation = mtri.Triangulation(grid['xy'][:, 0], grid['xy'][:, 1])
    keep = grid['feasible'][triangulation.triangles].all(axis=1)
    triangulation.set_mask(~keep)
    return triangulation
