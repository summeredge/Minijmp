"""Plackett–Burman 固定构造及工作表生成。"""
from dataclasses import replace
from numbers import Integral
import random

import pandas as pd

from doe_core import (DesignResult, DesignSpec, RunRecord, _validate_screening_construction, category_combinations,
                      randomized_run_order, screening_matrix_sha256, worksheet_metadata)
from doe_screening_matrices import MATRICES


def validate_pb(result):
    if not isinstance(result, DesignResult) or result.spec.design_type != 'plackett_burman':
        raise ValueError('需要 PB 设计')
    _validate_screening_construction(result)
    if screening_matrix_sha256(result) != result.spec.screening_matrix['matrix_sha256']:
        raise ValueError('PB 矩阵摘要不匹配')


def create_pb(spec, run_count, replicates=1, measured=False, center_points=0, block_replicates=False):
    """返回随机化工作表；中心点数按每重复指定。"""
    if not isinstance(spec, DesignSpec) or spec.design_type != 'plackett_burman':
        raise ValueError('需要 plackett_burman 设计定义')
    if isinstance(run_count, bool) or not isinstance(run_count, Integral) or run_count not in (12, 20, 24, 28, 32, 36, 40, 44, 48):
        raise ValueError('PB 运行数仅支持 12、20、24、28、32、36、40、44 或 48')
    if not 2 <= len(spec.factors) < run_count:
        raise ValueError('PB 因子数必须不小于 2 且小于运行数')
    if isinstance(replicates, bool) or not isinstance(replicates, Integral) or replicates < 1:
        raise ValueError('重复数必须是正整数')
    if isinstance(center_points, bool) or not isinstance(center_points, Integral) or center_points < 0:
        raise ValueError('每重复中心点数必须是非负整数')
    if not isinstance(block_replicates, bool):
        raise ValueError('按重复分区组选项必须是布尔值')
    categorical = [f for f in spec.factors if f.factor_type == 'categorical']
    if any(len(f.levels) != 2 for f in categorical):
        raise ValueError('PB 分类因子必须恰有两个水平')
    if center_points and len(categorical) == len(spec.factors):
        raise ValueError('全部因子为分类因子时不能添加中心点')
    centers_per_rep = center_points * (1 << len(categorical))
    total = (run_count + centers_per_rep) * replicates
    if total > 10000:
        raise ValueError('运行总数不能超过 10000')
    if spec.seed is None or not isinstance(measured, bool):
        raise ValueError('需要随机 seed 和有效的实测列选项')
    mathematical = run_count in (32, 40, 44, 48)
    identity = {'construction_id': f'pb{run_count}.v1',
                'source_kind': 'mathematical_construction' if mathematical else 'publication',
                'source_id': f'{"hadamard" if mathematical else "nist"}.pb{run_count}', 'matrix_sha256': '0' * 64}
    spec = replace(spec, screening_matrix=identity, block_count=replicates if block_replicates else None)
    matrix = MATRICES[f'pb{run_count}']
    columns = {'run_id': '运行ID', 'standard_order': '标准序', 'run_order': '运行序',
               'point_type': '点类型', 'replicate': '重复', 'block': '区组' if block_replicates else None,
               'factors': {f.factor_id: f'设定_{f.factor_id}' for f in spec.factors},
               'measured_levels': {f.factor_id: f'实测_{f.factor_id}' for f in spec.factors
                                   if measured and f.factor_type == 'continuous'},
               'responses': {name: f'响应_{name}' for name in spec.response_names}}
    if center_points:
        from doe_ccd import _center_level
        centers = {factor.factor_id: _center_level(factor) for factor in spec.factors
                   if factor.factor_type == 'continuous'}
        categories = category_combinations(spec.factors)
    ids = [f'R{i:05d}' for i in range(1, total + 1)]
    if block_replicates:
        rng = random.Random(spec.seed)
        shuffled = []
        for i in range(replicates):
            group = ids[i * (run_count + centers_per_rep):(i + 1) * (run_count + centers_per_rep)]
            rng.shuffle(group)
            shuffled.extend(group)
    else:
        shuffled = randomized_run_order(ids, spec.seed)
    positions = {run_id: i for i, run_id in enumerate(ids)}
    rows, records = [], []
    for order, run_id in enumerate(shuffled, 1):
        index = positions[run_id]
        rep, position = divmod(index, run_count + centers_per_rep)
        rep += 1
        center = position >= run_count
        settings = ({**centers, **categories[(position - run_count) % len(categories)]} if center else
                    {factor.factor_id: (factor.levels[0] if value == -1 else factor.levels[1])
                     if factor.factor_type == 'categorical' else (factor.low if value == -1 else factor.high)
                     for factor, value in zip(spec.factors, matrix[position])})
        row = {'运行ID': run_id, '标准序': index + 1, '运行序': order,
               '点类型': 'pseudo_center' if center and categorical else 'center' if center else 'factorial', '重复': rep}
        if block_replicates:
            row['区组'] = rep
        row.update({columns['factors'][key]: value for key, value in settings.items()})
        row.update({name: None for name in columns['measured_levels'].values()})
        row.update({name: None for name in columns['responses'].values()})
        rows.append(row)
        records.append(RunRecord(run_id, index + 1, order, row['点类型'], settings,
                                 replicate=rep, block=rep if block_replicates else None,
                                 responses={name: None for name in spec.response_names}))
    result = DesignResult(spec, tuple(records))
    identity['matrix_sha256'] = screening_matrix_sha256(result)
    spec = replace(spec, screening_matrix=identity)
    frame = pd.DataFrame(rows)
    for name in columns['factors'].values():
        frame[name] = pd.Series([row[name] for row in rows], dtype=object)
    for name in (*columns['measured_levels'].values(), *columns['responses'].values()):
        frame[name] = pd.array([None] * total, dtype='Float64')
    return frame, worksheet_metadata(frame, spec, columns)
