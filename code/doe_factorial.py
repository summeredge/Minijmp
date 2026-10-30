"""两水平全因子运行表生成；标准顺序中第一个因子变化最快。"""
from numbers import Integral
from itertools import product
import math
import random

import pandas as pd

from doe_core import (
    DesignSpec, randomized_run_order, restore_design_result, worksheet_metadata,
)


def _blocked_order(run_groups, seed):
    rng = random.Random(int(seed))
    blocks = list(run_groups)
    rng.shuffle(blocks)
    result = []
    for block in blocks:
        runs = run_groups[block].copy()
        rng.shuffle(runs)
        result.extend(runs)
    return tuple(result)


def confounded_block_effects(spec):
    """返回与区组混杂的生成元及其乘积效应。"""
    positions = {factor.factor_id: index for index, factor in enumerate(spec.factors)}
    generators = [sum(1 << positions[name] for name in item)
                 for item in spec.confounded_block_generators]
    effects = {0}
    for generator in generators:
        effects |= {effect ^ generator for effect in tuple(effects)}
    return tuple(
        tuple(factor.factor_id for index, factor in enumerate(spec.factors)
              if mask & (1 << index))
        for mask in sorted(effects - {0}, key=lambda value: (value.bit_count(), value)))


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
    confounded = bool(spec.confounded_block_generators)
    blocked = spec.block_count is not None
    if confounded:
        if (replicates != 1 or center_points or spec.randomization_unit != 'confounded_block'
                or spec.block_count != 1 << len(spec.confounded_block_generators)):
            raise ValueError('混杂区组只支持单次完整因子试验且不加中心点')
    elif ((blocked and (spec.block_count < 2 or spec.block_count != replicates
                        or spec.randomization_unit != 'block'))
          or (not blocked and spec.randomization_unit != 'run')):
        raise ValueError('区组设计只支持每个完整重复作为一个区组')
    if blocked and center_points % replicates:
        raise ValueError('区组中心点必须平均分配到每个完整重复')
    total = (1 << len(spec.factors)) * replicates + center_points
    if total > 10000:
        raise ValueError('运行总数不能超过 10000')

    columns = {'run_id': '运行ID', 'standard_order': '标准序', 'run_order': '运行序',
               'point_type': '点类型', 'replicate': '重复',
               'block': '区组' if blocked else None,
               'factors': {f.factor_id: f'设定_{f.factor_id}' for f in spec.factors},
               'measured_levels': {f.factor_id: f'实测_{f.factor_id}'
                                   for f in spec.factors} if measured else {},
               'responses': {name: f'响应_{name}' for name in spec.response_names}}
    rows, row_blocks = [], []
    block_for_combination = {}
    if confounded:
        positions = {factor.factor_id: index for index, factor in enumerate(spec.factors)}
        block_numbers = {
            signature: index + 1
            for index, signature in enumerate(
                product((-1, 1), repeat=len(spec.confounded_block_generators)))
        }
        for combination in range(1 << len(spec.factors)):
            coded = [1 if combination & (1 << index) else -1
                     for index in range(len(spec.factors))]
            signature = tuple(
                math.prod(coded[positions[name]] for name in generator)
                for generator in spec.confounded_block_generators)
            block_for_combination[combination] = block_numbers[signature]
    centers = [f.from_coded(0) for f in spec.factors]
    if center_points:
        from doe_core import _number
        centers = [_number(value, '中心点水平') for value in centers]
    centers_per_block = center_points // replicates if blocked else 0
    for rep in range(1, replicates + 1):
        for combination in range(1 << len(spec.factors)):
            rows.append(('factorial', rep, [f.high if combination & (1 << i) else f.low
                                           for i, f in enumerate(spec.factors)]))
            row_blocks.append(block_for_combination.get(combination, rep if blocked else None))
        if blocked:
            rows.extend(('center', rep, centers) for _ in range(centers_per_block))
            row_blocks.extend([rep] * centers_per_block)
    if center_points and not blocked:
        rows.extend(('center', i + 1, centers) for i in range(center_points))
    ids = [f'R{i:05d}' for i in range(1, total + 1)]
    if blocked:
        grouped_ids = ({block: [] for block in range(1, spec.block_count + 1)}
                       if confounded else {})
        for run_id, block in zip(ids, row_blocks):
            grouped_ids.setdefault(block, []).append(run_id)
        shuffled = _blocked_order(grouped_ids, spec.seed)
    else:
        shuffled = randomized_run_order(ids, spec.seed)
    positions = {run_id: i for i, run_id in enumerate(ids)}
    data = []
    for run_order, run_id in enumerate(shuffled, 1):
        index = positions[run_id]
        point, rep, levels = rows[index]
        row = {'运行ID': run_id, '标准序': index + 1, '运行序': run_order,
               '点类型': point, '重复': rep}
        if blocked:
            row['区组'] = f'B{row_blocks[index]}'
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
    if blocked:
        frame['区组'] = pd.Series([row['区组'] for row in data], dtype=object)
    for name in (*columns['measured_levels'].values(), *columns['responses'].values()):
        frame[name] = pd.array([None] * total, dtype='Float64')
    return frame, worksheet_metadata(frame, spec, columns)


def validate_factorial_design(frame, metadata):
    result = restore_design_result(frame, metadata)
    spec, runs = result.spec, result.runs
    if spec.design_type != 'two_level_full' or not 2 <= len(spec.factors) <= 6:
        raise ValueError('仅支持 2 至 6 因子的两水平全因子设计')
    factorial = [run for run in runs if run.point_type == 'factorial']
    centers = [run for run in runs if run.point_type == 'center']
    replicates = sorted({run.replicate for run in factorial})
    if replicates != list(range(1, len(replicates) + 1)):
        raise ValueError('重复编号必须连续且从 1 开始')
    confounded = bool(spec.confounded_block_generators)
    blocked = spec.block_count is not None
    by_replicate = {replicate: [run for run in runs if run.replicate == replicate]
                    for replicate in replicates}
    if confounded:
        if (not blocked or replicates != [1] or centers
                or spec.block_count != 1 << len(spec.confounded_block_generators)
                or spec.randomization_unit != 'confounded_block'
                or len(runs) != 1 << len(spec.factors)
                or {run.block for run in runs}
                != {f'B{block}' for block in range(1, spec.block_count + 1)}):
            raise ValueError('混杂区组必须是无中心点的单次完整因子试验')
    elif blocked:
        if (spec.block_count != len(replicates) or spec.block_count < 2
                or spec.randomization_unit != 'block'
                or any(run.block != f'B{run.replicate}' for run in runs)):
            raise ValueError('区组必须各自包含一个完整重复')
    elif (spec.randomization_unit != 'run' or any(run.block is not None for run in runs)):
        raise ValueError('区组必须各自包含一个完整重复')

    combinations = set(product((-1, 1), repeat=len(spec.factors)))
    for replicate in replicates:
        runs_here = by_replicate[replicate]
        observed = [tuple(factor.to_coded(run.settings[factor.factor_id])
                          for factor in spec.factors)
                    for run in runs_here if run.point_type == 'factorial']
        if len(observed) != len(combinations) or set(observed) != combinations:
            raise ValueError('每个重复必须包含且仅包含全部两水平组合')
        if any(run.point_type not in ('factorial', 'center') for run in runs_here):
            raise ValueError('全因子设计只能包含因子点和中心点')
        for run in runs_here:
            if run.point_type == 'center' and any(
                    factor.to_coded(run.settings[factor.factor_id]) != 0
                    for factor in spec.factors):
                raise ValueError('中心点必须位于所有因子的中点')
            if run.point_type == 'factorial':
                combination = sum(1 << index for index, factor in enumerate(spec.factors)
                                  if factor.to_coded(run.settings[factor.factor_id]) == 1)
                centers_per_block = (sum(item.point_type == 'center' for item in runs_here)
                                     if blocked else 0)
                expected_standard = ((replicate - 1) * (len(combinations) + centers_per_block)
                                     + combination + 1 if blocked else
                                     (replicate - 1) * len(combinations) + combination + 1)
                if run.standard_order != expected_standard:
                    raise ValueError('标准序与两水平组合不一致')
                if confounded:
                    positions = {factor.factor_id: index
                                 for index, factor in enumerate(spec.factors)}
                    codes = [int(factor.to_coded(run.settings[factor.factor_id]))
                             for factor in spec.factors]
                    signature = tuple(
                        math.prod(codes[positions[name]] for name in generator)
                        for generator in spec.confounded_block_generators)
                    expected_blocks = {
                        key: block for block, key in enumerate(
                            product((-1, 1), repeat=len(spec.confounded_block_generators)), 1)
                    }
                    if run.block != f'B{expected_blocks[signature]}':
                        raise ValueError('混杂区组与生成元不一致')

    if confounded:
        expected_size = len(combinations) // spec.block_count
        if any(sum(run.block == f'B{block}' for run in runs) != expected_size
               for block in range(1, spec.block_count + 1)):
            raise ValueError('混杂区组运行数必须相等')
        grouped_ids = {
            f'B{block}': [run.run_id for run in sorted(
                runs, key=lambda item: item.standard_order) if run.block == f'B{block}']
            for block in range(1, spec.block_count + 1)
        }
        expected_order = _blocked_order(grouped_ids, spec.seed)
    elif blocked:
        center_counts = [sum(run.point_type == 'center'
                             for run in by_replicate[replicate])
                         for replicate in replicates]
        if not center_counts or len(set(center_counts)) != 1:
            raise ValueError('区组中心点必须平均分配到每个完整重复')
        centers_per_block = center_counts[0]
        for replicate in replicates:
            expected = ((replicate - 1) * (len(combinations) + centers_per_block)
                        + len(combinations) + 1)
            actual = sorted(run.standard_order for run in by_replicate[replicate]
                            if run.point_type == 'center')
            if actual != list(range(expected, expected + centers_per_block)):
                raise ValueError('区组中心点标准序必须位于本重复因子点之后')
        grouped_ids = {
            replicate: [run.run_id for run in sorted(by_replicate[replicate],
                                                      key=lambda item: item.standard_order)]
            for replicate in replicates
        }
        expected_order = _blocked_order(grouped_ids, spec.seed)
    else:
        expected_centers = sorted(centers, key=lambda run: run.standard_order)
        start = len(combinations) * len(replicates)
        if any(run.standard_order != start + index or run.replicate != index
               for index, run in enumerate(expected_centers, 1)):
            raise ValueError('中心点标准序或重复编号无效')
        ids = [f'R{i:05d}' for i in range(1, len(runs) + 1)]
        expected_order = randomized_run_order(ids, spec.seed)
    if any(run.run_id != f'R{run.standard_order:05d}' for run in runs):
        raise ValueError('运行 ID 必须与标准序一致')
    orders = {run_id: order for order, run_id in enumerate(expected_order, 1)}
    if any(run.run_order != orders.get(run.run_id) for run in runs):
        raise ValueError('随机运行序与设计 seed 不一致')
    return result
