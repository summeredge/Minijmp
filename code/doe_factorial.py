"""两水平全因子运行表生成；标准顺序中第一个因子变化最快。"""
from numbers import Integral

import pandas as pd

from doe_core import DesignSpec, randomized_run_order, worksheet_metadata


def create_factorial(spec, replicates=1, center_points=0, measured=False):
    """返回运行表和 DOE-0 元数据；中心点放在全部因子点之后再统一随机化。"""
    if not isinstance(spec, DesignSpec) or spec.design_type != 'two_level_full':
        raise ValueError('需要 two_level_full 设计定义')
    if not 2 <= len(spec.factors) <= 6:
        raise ValueError('全因子设计需要 2 至 6 个因子')
    if spec.seed is None:
        raise ValueError('随机化必须指定整数 seed')
    if spec.generators or spec.defining_relations or spec.aliases or any(
            value is not None for value in (spec.ccd_alpha, spec.ccd_center_points,
                                             spec.ccd_axial_points)):
        raise ValueError('全因子设计不能包含生成元、别名或 CCD 定义')
    for value, label, minimum in ((replicates, '重复数', 1),
                                  (center_points, '中心点数', 0)):
        if isinstance(value, bool) or not isinstance(value, Integral) or value < minimum:
            raise ValueError(f'{label}必须是不小于 {minimum} 的整数')
    if not isinstance(measured, bool):
        raise ValueError('实测列选项必须是布尔值')
    total = (1 << len(spec.factors)) * replicates + center_points
    if total > 10000:
        raise ValueError('运行总数不能超过 10000')

    columns = {'run_id': '运行ID', 'standard_order': '标准序', 'run_order': '运行序',
               'point_type': '点类型', 'replicate': '重复',
               'factors': {f.factor_id: f'设定_{f.factor_id}' for f in spec.factors},
               'measured_levels': {f.factor_id: f'实测_{f.factor_id}'
                                   for f in spec.factors} if measured else {},
               'responses': {name: f'响应_{name}' for name in spec.response_names}}
    rows = []
    for rep in range(1, replicates + 1):
        for combination in range(1 << len(spec.factors)):
            rows.append(('factorial', rep, [f.high if combination & (1 << i) else f.low
                                           for i, f in enumerate(spec.factors)]))
    if center_points:
        centers = [f.from_coded(0) for f in spec.factors]
        # DOE-0 only serializes integers or exactly representable floating values.
        from doe_core import _number
        centers = [_number(value, '中心点水平') for value in centers]
        rows.extend(('center', i + 1, centers) for i in range(center_points))
    ids = [f'R{i:05d}' for i in range(1, total + 1)]
    shuffled = randomized_run_order(ids, spec.seed)
    positions = {run_id: i for i, run_id in enumerate(ids)}
    data = []
    for run_order, run_id in enumerate(shuffled, 1):
        index = positions[run_id]
        point, rep, levels = rows[index]
        row = {'运行ID': run_id, '标准序': index + 1, '运行序': run_order,
               '点类型': point, '重复': rep}
        row.update({columns['factors'][f.factor_id]: level
                    for f, level in zip(spec.factors, levels)})
        row.update({name: None for name in columns['measured_levels'].values()})
        row.update({name: None for name in columns['responses'].values()})
        data.append(row)
    frame = pd.DataFrame(data)
    # Prevent pandas from rounding mixed large integer and floating settings.
    for factor in spec.factors:
        name = columns['factors'][factor.factor_id]
        frame[name] = pd.Series([row[name] for row in data], dtype=object)
    for name in (*columns['measured_levels'].values(), *columns['responses'].values()):
        frame[name] = pd.array([None] * total, dtype='Float64')
    return frame, worksheet_metadata(frame, spec, columns)
