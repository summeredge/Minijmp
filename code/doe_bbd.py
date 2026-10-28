"""Box-Behnken 设计生成、区组划分与严格结构校验。

连续因子取低/中/高三水平；分类因子按水平组合展开，每个水平组合各自
包含一组中心点（Minitab 官方说明：每个分类水平同样增加中心点）。
9/10 因子区组依据 Box 与 Behnken (1960) 的正交构造；用户提供的
Minitab 22 默认设计经行与区组重排后等价，标准序不同。
"""
from fractions import Fraction
from itertools import product
from numbers import Integral
import math

import pandas as pd

from doe_core import (DesignSpec, category_combinations, randomized_run_order,
                      worksheet_metadata)


_MAX_RUNS = 10000
_DEFAULT_CENTERS = {3: 3, 4: 3, 5: 6, 6: 6, 7: 6, 9: 10, 10: 10}
_BLOCK_OPTIONS = {3: (1,), 4: (1, 3), 5: (1, 2), 6: (1, 2), 7: (1, 2),
                  9: (1, 5, 10), 10: (1, 2)}
_TRIPLES = {
    3: ((0, 1), (0, 2), (1, 2)),
    4: ((0, 1), (2, 3), (0, 3), (1, 2), (0, 2), (1, 3)),
    5: ((0, 1), (0, 2), (2, 3), (3, 4), (1, 4),
        (0, 3), (0, 4), (1, 2), (1, 3), (2, 4)),
    6: ((0, 1, 3), (1, 2, 4), (2, 3, 5), (0, 3, 4), (1, 4, 5), (0, 2, 5)),
    7: ((3, 4, 5), (0, 5, 6), (1, 4, 6), (0, 1, 3),
        (2, 3, 6), (0, 2, 4), (1, 2, 5)),
    # Box and Behnken (1960), Table 4, designs 6 and 7.
    9: ((0, 3, 6), (1, 4, 7), (2, 5, 8),
        (0, 1, 2), (3, 4, 5), (6, 7, 8),
        (0, 4, 8), (2, 3, 7), (1, 5, 6),
        (0, 5, 7), (1, 3, 8), (2, 4, 6),
        (0, 3, 6), (1, 4, 7), (2, 5, 8)),
    10: ((1, 5, 6, 9), (0, 1, 4, 9), (1, 2, 6, 7),
         (1, 3, 5, 8), (0, 7, 8, 9), (2, 3, 4, 9),
         (0, 3, 6, 7), (2, 4, 6, 8), (0, 2, 5, 8), (3, 4, 5, 7)),
}


def _structure(spec):
    """校验设计定义，返回连续因子、因子组、中心点数与区组数。"""
    if not isinstance(spec, DesignSpec) or spec.design_type != 'box_behnken':
        raise ValueError('需要 box_behnken 设计定义')
    continuous = [factor for factor in spec.factors
                  if factor.factor_type == 'continuous']
    k = len(continuous)
    if k not in _TRIPLES:
        raise ValueError('Box-Behnken 设计支持 3 至 7、9 或 10 个连续因子')
    if spec.seed is None:
        raise ValueError('随机化必须指定整数 seed')
    if spec.generators or spec.defining_relations or spec.aliases:
        raise ValueError('Box-Behnken 设计不包含部分因子定义')
    if spec.ccd_alpha is not None or spec.ccd_axial_points not in (None, 0):
        raise ValueError('Box-Behnken 设计没有轴点和 alpha')
    if spec.ccd_fraction is not None:
        raise ValueError('Box-Behnken 设计没有设计分数选项')
    blocks = 1 if spec.block_count is None else spec.block_count
    if blocks not in _BLOCK_OPTIONS[k]:
        raise ValueError(f'{k} 因子 Box-Behnken 的区组数只能是 '
                         + ' 或 '.join(map(str, _BLOCK_OPTIONS[k])))
    centers = spec.ccd_center_points
    if centers is None:
        centers = _DEFAULT_CENTERS[k]
    if centers < 0:
        raise ValueError('中心点数不能为负')
    if centers % blocks:
        raise ValueError('中心点数必须能按区组均分')
    return continuous, _TRIPLES[k], centers, blocks


def _rows(spec, replicates):
    """标准序：每个重复、每个分类组合依次为边点与中心点。"""
    continuous, groups, centers, blocks = _structure(spec)
    k = len(continuous)
    categories = category_combinations(spec.factors)
    pair_groups = len(groups) if len(groups[0]) == 2 else 0
    rows = []
    for replicate in range(1, replicates + 1):
        for category in categories:
            for group, triple in enumerate(groups):
                for signs in product((-1, 1), repeat=len(triple)):
                    row = [0] * k
                    for index, sign in zip(triple, signs):
                        row[index] = sign
                    if blocks == 1:
                        block = 0
                    elif k == 9:
                        block = group // 3
                        if blocks == 10:
                            block = 2 * block + int(math.prod(signs) < 0)
                    elif k == 10:
                        block = int(math.prod(signs) < 0)
                    elif blocks == 3:
                        block = group // 2
                    elif pair_groups:
                        block = 0 if group < pair_groups // 2 else 1
                    else:
                        # 三联组内按符号乘积分半，区组指示与模型项正交。
                        block = 0 if signs[0] * signs[1] * signs[2] == 1 else 1
                    rows.append(('edge', row, block, replicate, category))
            for block in range(blocks):
                rows.extend(('center', [0] * k, block, replicate, category)
                            for _ in range(centers // blocks))
    return rows


def _levels(factor, coded):
    value = factor.from_coded(coded)
    if isinstance(value, Fraction):
        value = float(value)
    if not math.isfinite(value) or not factor.low <= value <= factor.high:
        raise ValueError(f'因子 {factor.factor_id} 的中心或边点水平超出范围')
    if abs(float(factor.to_coded(value)) - coded) > 1e-8:
        raise ValueError(f'因子 {factor.factor_id} 舍入后无法保持编码精度')
    return value


def create_bbd(spec, replicates=1, measured=False):
    """生成 Box-Behnken 工作表；区组内随机化，标准序保持不变。"""
    if isinstance(replicates, bool) or not isinstance(replicates, Integral) or replicates < 1:
        raise ValueError('重复数必须是正整数')
    if not isinstance(measured, bool):
        raise ValueError('实测列选项必须是布尔值')
    continuous, groups, centers, blocks = _structure(spec)
    rows = _rows(spec, int(replicates))
    total = len(rows)
    if total > _MAX_RUNS:
        raise ValueError(f'运行总数不能超过 {_MAX_RUNS}')
    columns = {
        'run_id': '运行ID', 'standard_order': '标准序', 'run_order': '运行序',
        'point_type': '点类型', 'replicate': '重复', 'block': '区组',
        'factors': {f.factor_id: f'设定_{f.factor_id}' for f in spec.factors},
        'measured_levels': ({f.factor_id: f'实测_{f.factor_id}' for f in spec.factors}
                            if measured else {}),
        'responses': {name: f'响应_{name}' for name in spec.response_names},
    }
    ids = [f'R{i:05d}' for i in range(1, total + 1)]
    order, sequence = {}, 1
    for block in range(blocks):
        block_ids = [rid for rid, row in zip(ids, rows) if row[2] == block]
        for rid in randomized_run_order(block_ids, spec.seed + block):
            order[rid] = sequence
            sequence += 1
    data = []
    for index in sorted(range(total), key=lambda i: order[ids[i]]):
        point, coded, block, replicate, category = rows[index]
        row = {'运行ID': ids[index], '标准序': index + 1,
               '运行序': order[ids[index]], '点类型': point,
               '重复': replicate, '区组': block + 1}
        for factor, value in zip(continuous, coded):
            row[columns['factors'][factor.factor_id]] = _levels(factor, value)
            row[f'编码_{factor.factor_id}'] = value
        for key, level in category.items():
            row[columns['factors'][key]] = level
        row.update({name: None for name in (*columns['measured_levels'].values(),
                                            *columns['responses'].values())})
        data.append(row)
    frame = pd.DataFrame(data)
    for factor in spec.factors:
        name = columns['factors'][factor.factor_id]
        frame[name] = pd.Series([row[name] for row in data], dtype=object)
    for name in (*columns['measured_levels'].values(), *columns['responses'].values()):
        frame[name] = pd.array([None] * total, dtype='Float64')
    return frame, worksheet_metadata(frame, spec, columns)


def validate_bbd(result, frame=None):
    """核验运行集合、编码列、分类水平与区组分配。"""
    spec = result.spec
    continuous, groups, centers, blocks = _structure(spec)
    runs = result.runs
    ordered = sorted(runs, key=lambda run: run.standard_order)
    base = _rows(spec, 1)
    per_base = len(base)
    if not runs or len(runs) % per_base:
        raise ValueError('Box-Behnken 运行数不是基础设计的整数倍')
    expected_rows = _rows(spec, len(runs) // per_base)
    by_standard = {}
    for index, run in enumerate(ordered):
        if run.run_id != f'R{index + 1:05d}':
            raise ValueError('Box-Behnken 运行 ID 与标准序不一致')
        point, coded, block, replicate, category = expected_rows[index]
        if (run.point_type != point or run.block != block + 1
                or run.replicate != replicate):
            raise ValueError('Box-Behnken 点类型、区组或重复编号与设计定义不一致')
        for factor, value in zip(continuous, coded):
            if float(factor.to_coded(run.settings[factor.factor_id])) != value:
                raise ValueError('Box-Behnken 设定水平与编码矩阵不一致')
        for key, level in category.items():
            if run.settings[key] != level:
                raise ValueError('Box-Behnken 分类因子水平与设计定义不一致')
        by_standard[run.standard_order] = coded
    for block in range(blocks):
        orders = sorted(run.run_order for run in runs if run.block == block + 1)
        if not orders:
            raise ValueError('Box-Behnken 区组为空')
        if orders != list(range(min(orders), min(orders) + len(orders))):
            raise ValueError('Box-Behnken 区组内运行序不连续')
    if sorted(run.run_order for run in runs) != list(range(1, len(runs) + 1)):
        raise ValueError('Box-Behnken 运行序必须是 1 到运行数的排列')
    if frame is not None:
        if len(frame) != len(runs):
            raise ValueError('Box-Behnken 工作表行数与运行记录不一致')
        for factor in continuous:
            label = f'编码_{factor.factor_id}'
            if label not in frame.columns or list(frame.columns).count(label) != 1:
                raise ValueError('Box-Behnken 编码水平列缺失或重复')
            position = continuous.index(factor)
            for row, run in enumerate(runs):
                if float(frame.iloc[row][label]) != by_standard[
                        run.standard_order][position]:
                    raise ValueError('Box-Behnken 编码水平与实际设定不一致')
    return [[float(value) for value in by_standard[run.standard_order]]
            for run in runs]

