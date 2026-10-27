"""中心复合设计生成与设计矩阵校验。"""
from collections import Counter
from itertools import product
from numbers import Integral
import math

import pandas as pd

from doe_core import DesignSpec, _number, randomized_run_order, worksheet_metadata


def axial_levels(factor, alpha):
    """返回由浮点运算得到的轴点；拒绝无法区分的设定水平。"""
    low, high = factor.low, factor.high
    if any(isinstance(v, int) and int(float(v)) != v for v in (low, high)):
        raise ValueError('因子水平不能无损表示为浮点数')
    center = _number(factor.from_coded(0), '中心点水平')
    half = (float(high) - float(low)) / 2
    levels = (float(center) - alpha * half, float(center) + alpha * half)
    if not all(math.isfinite(v) for v in levels) or not levels[0] < center < levels[1]:
        raise ValueError('轴点超出有限数值范围或因精度不足无法区分')
    return levels


def validate_ccd(result):
    spec, runs = result.spec, result.runs
    k = len(spec.factors)
    if (spec.design_type != 'central_composite' or not 2 <= k <= 5 or
            spec.ccd_alpha is None or spec.ccd_center_points is None or
            spec.ccd_axial_points is None or spec.generators or
            spec.defining_relations or spec.aliases):
        raise ValueError('CCD 设计定义不完整')
    alpha = spec.ccd_alpha
    if alpha != 1 and not math.isclose(alpha, (2 ** k) ** .25, rel_tol=1e-14):
        raise ValueError('仅支持面心或旋转外接 CCD')
    centers = [_number(f.from_coded(0), '中心点水平') for f in spec.factors]
    axial = [axial_levels(f, alpha) for f in spec.factors]
    groups = {}
    center_replicates = []
    coded = []
    for run in runs:
        if run.block is not None:
            raise ValueError('CCD 不支持区组')
        values = [run.settings[f.factor_id] for f in spec.factors]
        if run.point_type == 'center':
            if values != centers:
                raise ValueError('CCD 中心点设定错误')
            center_replicates.append(run.replicate)
            row = (0,) * k
        elif run.point_type == 'factorial':
            row = tuple(-1 if v == f.low else 1 if v == f.high else None
                        for v, f in zip(values, spec.factors))
            if None in row:
                raise ValueError('CCD 因子点设定错误')
        elif run.point_type == 'axial':
            matches = [(i, sign) for i in range(k) for sign in (-1, 1)
                       if values == [axial[j][0 if sign == -1 else 1]
                                     if j == i else centers[j] for j in range(k)]]
            if len(matches) != 1:
                raise ValueError('CCD 轴点设定错误')
            i, sign = matches[0]
            row = tuple(sign * alpha if j == i else 0 for j in range(k))
        else:
            raise ValueError('CCD 点类型错误')
        if run.point_type != 'center':
            groups.setdefault(run.replicate, []).append((run.point_type, row))
        coded.append(row)
    expected = Counter([('factorial', row) for row in product((-1, 1), repeat=k)] +
                       [('axial', tuple(sign * alpha if j == i else 0 for j in range(k)))
                        for i in range(k) for sign in (-1, 1)])
    if (not groups or set(groups) != set(range(1, len(groups) + 1)) or
            any(Counter(group) != expected for group in groups.values()) or
            sorted(center_replicates) != list(range(1, spec.ccd_center_points + 1)) or
            sum(r.point_type == 'axial' for r in runs) != spec.ccd_axial_points):
        raise ValueError('CCD 设计矩阵不完整或重复')
    return coded


def create_ccd(spec, replicates=1, measured=False):
    if not isinstance(spec, DesignSpec) or spec.design_type != 'central_composite':
        raise ValueError('需要中心复合设计定义')
    if isinstance(replicates, bool) or not isinstance(replicates, Integral) or replicates < 1:
        raise ValueError('重复数必须是正整数')
    if not isinstance(measured, bool) or spec.seed is None:
        raise ValueError('实测列选项或随机种子无效')
    k = len(spec.factors)
    if not 2 <= k <= 5 or spec.ccd_alpha is None or spec.ccd_center_points is None:
        raise ValueError('CCD 需要 2 至 5 个因子及完整定义')
    total = replicates * (2**k + 2*k) + spec.ccd_center_points
    if total > 10000:
        raise ValueError('运行总数不能超过 10000')
    centers = [_number(f.from_coded(0), '中心点水平') for f in spec.factors]
    axial = [axial_levels(f, spec.ccd_alpha) for f in spec.factors]
    columns = {'run_id': '运行ID', 'standard_order': '标准序', 'run_order': '运行序',
               'point_type': '点类型', 'replicate': '重复',
               'factors': {f.factor_id: f'设定_{f.factor_id}' for f in spec.factors},
               'measured_levels': {f.factor_id: f'实测_{f.factor_id}' for f in spec.factors} if measured else {},
               'responses': {name: f'响应_{name}' for name in spec.response_names}}
    rows = []
    for rep in range(1, replicates + 1):
        for n in range(2**k):
            rows.append(('factorial', rep, [f.high if n & (1 << i) else f.low for i, f in enumerate(spec.factors)]))
        for i in range(k):
            for sign in (0, 1):
                rows.append(('axial', rep, [axial[j][sign] if j == i else centers[j] for j in range(k)]))
    rows.extend(('center', i + 1, centers) for i in range(spec.ccd_center_points))
    ids = [f'R{i:05d}' for i in range(1, total + 1)]
    positions = {run_id: i for i, run_id in enumerate(ids)}
    data = []
    for order, run_id in enumerate(randomized_run_order(ids, spec.seed), 1):
        index = positions[run_id]
        point, rep, levels = rows[index]
        row = {'运行ID': run_id, '标准序': index + 1, '运行序': order, '点类型': point, '重复': rep}
        row.update({columns['factors'][f.factor_id]: v for f, v in zip(spec.factors, levels)})
        for i, factor in enumerate(spec.factors):
            value = (-1 if levels[i] == factor.low else 1) if point == 'factorial' else (
                0 if point == 'center' or levels[i] == centers[i] else
                -spec.ccd_alpha if levels[i] == axial[i][0] else spec.ccd_alpha)
            row[f'编码_{factor.factor_id}'] = value
        row.update({name: None for name in (*columns['measured_levels'].values(), *columns['responses'].values())})
        data.append(row)
    frame = pd.DataFrame(data)
    for name in columns['factors'].values():
        frame[name] = pd.Series([row[name] for row in data], dtype=object)
    for name in (*columns['measured_levels'].values(), *columns['responses'].values()):
        frame[name] = pd.array([None] * total, dtype='Float64')
    meta = worksheet_metadata(frame, spec, columns)
    return frame, meta
