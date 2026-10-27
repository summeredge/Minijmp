"""多响应叠加等高线：两个绘图因子，其余固定，按各自可接受范围求交集。"""
import math

import numpy as np

from doe_predict import snapshot_id
from doe_rsm import analyze_rsm


def _category(factor, level):
    if level not in factor.levels:
        raise ValueError(f'分类因子 {factor.factor_id} 的水平不在已声明范围内')
    return level


def overlay_contours(frame, metadata, responses, factor_x, factor_y, fixed=None,
                     categories=None, grid=60):
    """计算叠加等高线与可行区域。

    responses 为 {响应名: (可接受下限, 可接受上限)}；上下限含端点。
    返回的 feasible 为所有响应同时落在各自范围内的网格掩码。
    """
    if not isinstance(responses, dict) or len(responses) < 2:
        raise ValueError('叠加等高线至少需要两个响应')
    if not isinstance(grid, int) or isinstance(grid, bool) or not 5 <= grid <= 200:
        raise ValueError('网格数必须是 5 至 200 的整数')
    analyses, limits = {}, {}
    for name, bounds in responses.items():
        if (not isinstance(bounds, (tuple, list)) or len(bounds) != 2):
            raise ValueError(f'响应 {name} 的可接受范围必须是两个数值')
        try:
            low, high = float(bounds[0]), float(bounds[1])
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f'响应 {name} 的可接受范围必须是有限数值') from exc
        if not math.isfinite(low) or not math.isfinite(high) or low >= high:
            raise ValueError(f'响应 {name} 的可接受下限必须小于上限')
        analyses[name] = analyze_rsm(frame, metadata, name)
        limits[name] = (low, high)
    design = analyses[next(iter(analyses))]['design']
    spec = design.spec
    factor_ids = [factor.factor_id for factor in spec.factors
                  if factor.factor_type == 'continuous']
    if factor_x not in factor_ids or factor_y not in factor_ids or factor_x == factor_y:
        raise ValueError('请选择两个不同的连续因子')
    fixed = dict(fixed or {})
    categories = dict(categories or {})
    unknown = set(fixed) | set(categories)
    unknown -= set(factor_ids) | {f.factor_id for f in spec.factors
                                  if f.factor_type == 'categorical'}
    if unknown:
        raise ValueError('存在未知因子：' + '、'.join(sorted(unknown)))
    if set(fixed) & set(categories):
        raise ValueError('因子不能同时作为连续与分类设置')
    if {factor_x, factor_y} & set(fixed):
        raise ValueError('绘图因子不能同时设置为固定水平')
    settings = {}
    for factor in spec.factors:
        if factor.factor_type == 'categorical':
            settings[factor.factor_id] = _category(
                factor, categories.get(factor.factor_id, factor.levels[0]))
            continue
        factor_id = factor.factor_id
        if factor_id in (factor_x, factor_y):
            continue
        value = fixed.get(factor_id, 0.0)
        if isinstance(value, bool):
            raise ValueError(f'因子 {factor_id} 的固定水平必须是数值')
        try:
            value = float(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f'因子 {factor_id} 的固定水平必须是数值') from exc
        if not math.isfinite(value) or not -1 <= value <= 1:
            raise ValueError(f'因子 {factor_id} 的固定编码水平必须位于 −1 至 1')
        settings[factor_id] = value
    axis = np.linspace(-1, 1, grid)
    xx, yy = np.meshgrid(axis, axis)
    point_settings = dict(settings)
    feasible = np.ones(xx.shape, dtype=bool)
    zz = {}
    # 与拟合一致：模型列使用 1 起的区组序号，参考区组为第 1 组。
    first = analyses[next(iter(analyses))]
    block = first['blocks'][0] if first['blocks'] else None
    block_code = 1 if block is not None else None
    for name, analysis in analyses.items():
        model, coefficients = analysis['term_model'], analysis['coefficients']
        rows = []
        for x_value, y_value in zip(xx.ravel(), yy.ravel()):
            point = dict(point_settings)
            point[factor_x], point[factor_y] = x_value, y_value
            rows.append(model.row(point, block_code))
        values = (np.vstack(rows) @ np.asarray(coefficients, dtype=float)).reshape(xx.shape)
        if not np.isfinite(values).all():
            raise ValueError(f'响应 {name} 的预测值超出有限范围')
        low, high = limits[name]
        inside = (values >= low) & (values <= high)
        feasible &= inside
        zz[name] = values
    return {
        'x': axis, 'y': axis, 'xx': xx, 'yy': yy, 'z': zz,
        'limits': limits, 'feasible': feasible,
        'feasible_fraction': float(feasible.mean()),
        'inside_fraction': {name: float(((zz[name] >= limits[name][0]) &
                                        (zz[name] <= limits[name][1])).mean())
                            for name in zz},
        'snapshot_id': snapshot_id(frame, metadata),
        'terms': {name: list(analyses[name]['terms']) for name in analyses},
        'factors': (factor_x, factor_y), 'fixed': dict(settings),
        'block': block, 'design_type': spec.design_type,
    }
