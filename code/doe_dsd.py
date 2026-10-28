"""已验证 conference matrix 及单分类 DSD 构造。"""
from dataclasses import replace
from numbers import Integral
import random

import pandas as pd

from doe_ccd import _center_level
from doe_core import (DesignResult, DesignSpec, RunRecord, _validate_screening_construction,
                      randomized_run_order, screening_matrix_sha256, worksheet_metadata)
from doe_screening_matrices import MATRICES


def validate_dsd(result):
    if not isinstance(result, DesignResult) or result.spec.design_type != 'definitive_screening':
        raise ValueError('需要 DSD 设计')
    _validate_screening_construction(result)
    if screening_matrix_sha256(result) != result.spec.screening_matrix['matrix_sha256']:
        raise ValueError('DSD 矩阵摘要不匹配')


def create_dsd(spec, replicates=1, measured=False, blocks=1):
    """生成已验证构造；区组均分完整重复。"""
    if not isinstance(spec, DesignSpec) or spec.design_type != 'definitive_screening':
        raise ValueError('需要 definitive_screening 设计定义')
    types = [factor.factor_type for factor in spec.factors]
    if types == ['continuous'] * 4 + ['categorical'] * 2:
        key, source = 'dsd4c2', 'foldover.dsd4c2'
    elif 2 <= len(types) <= 48 and types == ['continuous'] * (len(types) - 1) + ['categorical']:
        key = f'dsd{len(types) - 1}c1'
        source = f'jones.{key}'
    elif all(value == 'continuous' for value in types) and len(types) in range(2, 49):
        key = f'dsd{len(types)}'
        source = f'conference.{key}'
    else:
        raise ValueError('当前支持 2–48 个连续因子、1–47 连续加 1 分类，或 4 连续加 2 分类')
    if isinstance(replicates, bool) or not isinstance(replicates, Integral) or replicates < 1:
        raise ValueError('重复数必须是正整数')
    if (isinstance(blocks, bool) or not isinstance(blocks, Integral) or blocks < 1 or
            blocks > replicates or replicates % blocks):
        raise ValueError('区组数必须均分完整重复')
    matrix = MATRICES[key]
    total = len(matrix) * replicates
    if total > 10000:
        raise ValueError('运行总数不能超过 10000')
    if spec.seed is None or not isinstance(measured, bool):
        raise ValueError('需要随机 seed 和有效的实测列选项')
    identity = {'construction_id': key + '.v1', 'source_kind': 'mathematical_construction',
                'source_id': source, 'matrix_sha256': '0' * 64}
    spec = replace(spec, screening_matrix=identity, block_count=blocks if blocks > 1 else None)
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
        offset = index % len(matrix)
        rep = index // len(matrix) + 1
        point = ('pseudo_center' if key.endswith(('c1', 'c2')) and offset >= len(matrix) - 2 else
                 'center' if not key.endswith(('c1', 'c2')) and offset == len(matrix) - 1 else 'screening')
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
