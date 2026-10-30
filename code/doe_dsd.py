"""已验证 conference matrix 及单分类 DSD 构造。"""
from dataclasses import replace
from itertools import product
from numbers import Integral
import random

import numpy as np
import pandas as pd

from doe_ccd import _center_level
from doe_core import (DesignResult, DesignSpec, RunRecord, _validate_screening_construction,
                      randomized_run_order, screening_matrix_sha256, worksheet_metadata)
from doe_screening_matrices import MATRICES


def _integer_determinant(matrix):
    """用 Bareiss 消元精确计算整数矩阵的行列式。"""
    work = [list(map(int, row)) for row in matrix]
    size = len(work)
    denominator = sign = 1
    for pivot_index in range(size - 1):
        if work[pivot_index][pivot_index] == 0:
            swap = next((row for row in range(pivot_index + 1, size)
                         if work[row][pivot_index]), None)
            if swap is None:
                return 0
            work[pivot_index], work[swap] = work[swap], work[pivot_index]
            sign = -sign
        pivot = work[pivot_index][pivot_index]
        for row in range(pivot_index + 1, size):
            for column in range(pivot_index + 1, size):
                work[row][column] = (
                    work[row][column] * pivot
                    - work[row][pivot_index] * work[pivot_index][column]
                ) // denominator
            work[row][pivot_index] = 0
        denominator = pivot
    return sign * work[-1][-1] if size else 1


def _multi_categorical_dsd_matrix(continuous_count, categorical_count):
    factor_count = continuous_count + categorical_count
    base = MATRICES[f'dsd{factor_count}']
    centers = [index for index, row in enumerate(base) if not any(row)]
    if len(centers) != 1:
        raise ValueError('基础 DSD 必须且只能包含一个全零中心行')
    rows = [list(row) for index, row in enumerate(base) if index != centers[0]]
    zero_pairs = []
    for column in range(continuous_count, factor_count):
        pair = [index for index, row in enumerate(rows) if row[column] == 0]
        if len(pair) != 2:
            raise ValueError('基础 DSD 的分类列必须恰有两个非中心零位')
        zero_pairs.append(pair)

    best_determinant, best_rows = -1, None
    # b 优先于 z 枚举；严格大于保留并列时字典序最先的配置。
    for signs in product((-1, 1), repeat=2 * categorical_count):
        b, z = signs[:categorical_count], signs[categorical_count:]
        candidate = [row[:] for row in rows]
        for column, pair, value in zip(range(continuous_count, factor_count), zero_pairs, z):
            # 论文将每个分类因子的零位设为 z_j 与 -z_j，以保留折叠配对。
            candidate[pair[0]][column] = value
            candidate[pair[1]][column] = -value
        # 论文的 2×c B 矩阵两行为 b 与 -b。
        candidate.extend((
            [0] * continuous_count + list(b),
            [0] * continuous_count + [-value for value in b],
        ))
        first_order = np.column_stack((np.ones(len(candidate), dtype=int), candidate))
        determinant = _integer_determinant(first_order.T @ first_order)
        if determinant > best_determinant:
            best_determinant, best_rows = determinant, candidate
    return tuple(tuple(row) for row in best_rows)


def _dsd_matrix_for_key(key):
    """返回固定 DSD 矩阵，或按 Jones–Nachtsheim 重建多分类矩阵。"""
    if isinstance(key, str) and key.startswith('dsd') and key in MATRICES:
        return MATRICES[key]
    if not isinstance(key, str):
        raise KeyError(key)
    prefix, separator, suffix = key.partition('c')
    try:
        continuous_count = int(prefix.removeprefix('dsd'))
        categorical_count = int(suffix)
    except ValueError as error:
        raise KeyError(key) from error
    if (not separator or prefix != f'dsd{continuous_count}'
            or suffix != str(categorical_count)
            or not 4 <= continuous_count <= 12
            or not 2 <= categorical_count <= 4
            or (continuous_count, categorical_count) == (4, 2)):
        raise KeyError(key)
    return _multi_categorical_dsd_matrix(continuous_count, categorical_count)


def validate_dsd(result):
    if not isinstance(result, DesignResult) or result.spec.design_type != 'definitive_screening':
        raise ValueError('需要 DSD 设计')
    _validate_screening_construction(result)
    if screening_matrix_sha256(result) != result.spec.screening_matrix['matrix_sha256']:
        raise ValueError('DSD 矩阵摘要不匹配')


def create_dsd(spec, replicates=1, measured=False, blocks=1, center_points=None):
    """生成已验证构造；区组均分完整重复。"""
    if not isinstance(spec, DesignSpec) or spec.design_type != 'definitive_screening':
        raise ValueError('需要 definitive_screening 设计定义')
    types = [factor.factor_type for factor in spec.factors]
    continuous_count = types.count('continuous')
    categorical_count = len(types) - continuous_count
    if types == ['continuous'] * 4 + ['categorical'] * 2:
        key, source = 'dsd4c2', 'foldover.dsd4c2'
    elif (4 <= continuous_count <= 12 and 2 <= categorical_count <= 4
          and (continuous_count, categorical_count) != (4, 2)
          and types == ['continuous'] * continuous_count + ['categorical'] * categorical_count):
        key = f'dsd{continuous_count}c{categorical_count}'
        source = f'jones.{key}'
    elif 2 <= len(types) <= 48 and types == ['continuous'] * (len(types) - 1) + ['categorical']:
        key = f'dsd{len(types) - 1}c1'
        source = f'jones.{key}'
    elif all(value == 'continuous' for value in types) and len(types) in range(2, 49):
        key = f'dsd{len(types)}'
        source = f'conference.{key}'
    else:
        raise ValueError('当前支持 2–48 个连续因子、1–47 连续加 1 分类，及 4–12 连续加 2–4 分类（保留既有 4+2 构造）')
    if center_points is None:
        center_count = spec.center_point_count or 0
    elif (isinstance(center_points, bool) or not isinstance(center_points, Integral)
          or center_points < 0):
        raise ValueError('额外中心点数必须是非负整数')
    else:
        center_count = int(center_points)
    if categorical_count and center_count % (1 << categorical_count):
        raise ValueError('含分类因子的 DSD 额外中心点数必须是全部分类组合数的倍数')
    if center_count and spec.schema_version < 5:
        raise ValueError('DSD 额外中心点需要 schema v5')
    if isinstance(replicates, bool) or not isinstance(replicates, Integral) or replicates < 1:
        raise ValueError('重复数必须是正整数')
    if (isinstance(blocks, bool) or not isinstance(blocks, Integral) or blocks < 1 or
            blocks > replicates or replicates % blocks):
        raise ValueError('区组数必须均分完整重复')
    matrix = _dsd_matrix_for_key(key)
    base_size = len(matrix)
    runs_per_replicate = base_size + center_count
    total = runs_per_replicate * replicates
    if total > 10000:
        raise ValueError('运行总数不能超过 10000')
    if center_count:
        if categorical_count:
            combinations = tuple(product((-1, 1), repeat=categorical_count))
            extra_rows = tuple((0,) * continuous_count + combinations[index % len(combinations)]
                               for index in range(center_count))
        else:
            extra_rows = ((0,) * len(spec.factors),) * center_count
        matrix = matrix + extra_rows
    if spec.seed is None or not isinstance(measured, bool):
        raise ValueError('需要随机 seed 和有效的实测列选项')
    identity = {'construction_id': key + '.v1', 'source_kind': 'mathematical_construction',
                'source_id': source, 'matrix_sha256': '0' * 64}
    spec = replace(spec, screening_matrix=identity, block_count=blocks if blocks > 1 else None,
                   center_point_count=center_count or None)
    columns = {'run_id': '运行ID', 'standard_order': '标准序', 'run_order': '运行序',
               'point_type': '点类型', 'replicate': '重复', 'block': '区组' if blocks > 1 else None,
               'factors': {f.factor_id: f'设定_{f.factor_id}' for f in spec.factors},
               'measured_levels': {f.factor_id: f'实测_{f.factor_id}' for f in spec.factors
                                   if measured and f.factor_type == 'continuous'},
               'responses': {name: f'响应_{name}' for name in spec.response_names}}
    levels = [{-1: f.low, 0: _center_level(f), 1: f.high} if f.factor_type == 'continuous'
              else {-1: f.levels[0], 1: f.levels[1]} for f in spec.factors]
    ids = [f'R{i:05d}' for i in range(1, total + 1)]
    positions = {run_id: i for i, run_id in enumerate(ids)}
    if blocks > 1:
        rng = random.Random(spec.seed)
        shuffled = []
        block_size = total // blocks
        for block in range(blocks):
            group = ids[block * block_size:(block + 1) * block_size]
            rng.shuffle(group)
            shuffled.extend(group)
    else:
        shuffled = randomized_run_order(ids, spec.seed)
    rows, records = [], []
    for order, run_id in enumerate(shuffled, 1):
        index = positions[run_id]
        offset = index % runs_per_replicate
        rep = index // runs_per_replicate + 1
        point = ('pseudo_center' if categorical_count and offset >= base_size - 2 else
                 'center' if not categorical_count and offset >= base_size - 1 else 'screening')
        settings = {f.factor_id: choices[value] for f, choices, value in zip(spec.factors, levels, matrix[offset])}
        row = {'运行ID': run_id, '标准序': index + 1, '运行序': order, '点类型': point, '重复': rep}
        block = (rep - 1) // (replicates // blocks) + 1 if blocks > 1 else None
        if block is not None:
            row['区组'] = block
        row.update({columns['factors'][name]: value for name, value in settings.items()})
        row.update({name: None for name in columns['measured_levels'].values()})
        row.update({name: None for name in columns['responses'].values()})
        rows.append(row)
        records.append(RunRecord(run_id, index + 1, order, point, settings, replicate=rep, block=block,
                                 responses={name: None for name in spec.response_names}))
    identity['matrix_sha256'] = screening_matrix_sha256(DesignResult(spec, tuple(records)))
    spec = replace(spec, screening_matrix=identity)
    frame = pd.DataFrame(rows)
    for name in columns['factors'].values():
        frame[name] = pd.Series([row[name] for row in rows], dtype=object)
    for name in (*columns['measured_levels'].values(), *columns['responses'].values()):
        frame[name] = pd.array([None] * total, dtype='Float64')
    return frame, worksheet_metadata(frame, spec, columns)
