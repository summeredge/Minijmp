"""Plackett–Burman 折叠：复制当前批次范围并翻转选中的因子。

PB 没有正规 defining relation；此处只按实际编码矩阵计算秩、投影与
完全/部分混杂，不生成正规别名。
"""
from dataclasses import replace

import numpy as np
import pandas as pd

from doe_core import (RunRecord, _screening_level, foldover_matrix_fingerprint,
                      pb_foldover_fingerprint, randomized_run_order, restore_design_result,
                      screening_level_series, worksheet_metadata)
from doe_pb import validate_pb
from doe_foldover import fold_factor_ids


MAX_RUNS = 10000


def _columns(coded, names, term):
    return np.prod(coded[:, [names.index(name) for name in term]], axis=1)


def foldover_estimability(coded, names):
    """按实际编码矩阵报告主效应/联合秩、完全与部分混杂。"""
    n = len(coded)
    mains = [_columns(coded, names, (name,)) for name in names]
    pairs = [(a, b) for i, a in enumerate(names) for b in names[i + 1:]]
    interactions = [_columns(coded, names, pair) for pair in pairs]
    main_matrix = np.column_stack([np.ones(n)] + mains)
    joint_matrix = np.column_stack([np.ones(n)] + mains + interactions)
    main_rank = int(np.linalg.matrix_rank(main_matrix))
    joint_rank = int(np.linalg.matrix_rank(joint_matrix))
    unique = main_rank == main_matrix.shape[1]
    # 用一次伪逆把全部交互列批量投影，避免逐对 lstsq。
    pinv = np.linalg.pinv(main_matrix)
    all_coefficients = pinv @ np.column_stack(interactions) if interactions else None
    all_fitted = main_matrix @ all_coefficients if interactions else None
    complete, partial, unestimable = [], [], []
    tolerance = 1e-8
    main_array = np.column_stack(mains) if mains else np.empty((n, 0))
    for index, (pair, column) in enumerate(zip(pairs, interactions)):
        label = f'{pair[0]}*{pair[1]}'
        # 交互列恰为某主效应列或其反号：完全混杂，先于此判断可估计性。
        positive = np.max(np.abs(main_array - column[:, None]), axis=0) <= tolerance
        negative = np.max(np.abs(main_array + column[:, None]), axis=0) <= tolerance
        match = positive | negative
        exact = ((int(np.argmax(match)) + 1, 1 if positive.any() else -1)
                 if match.any() else None)
        if exact is not None:
            complete.append({'interaction': label, 'main': names[exact[0] - 1],
                             'projection': float(exact[1])})
            continue
        coefficients = all_coefficients[:, index]
        residual = column - all_fitted[:, index]
        if float(np.linalg.norm(residual)) <= tolerance * max(n, 1):
            complete.append({'interaction': label, 'main': None,
                             'projection': float(np.max(np.abs(coefficients[1:])))})
            continue
        if not unique:
            unestimable.append(label)
            continue
        magnitude = float(np.max(np.abs(coefficients[1:])))
        if magnitude > tolerance:
            partial.append({'interaction': label, 'projection': magnitude})
    return {'runs': n, 'main_rank': main_rank, 'joint_rank': joint_rank,
            'joint_parameter_count': joint_matrix.shape[1],
            'joint_residual_df': n - joint_rank,
            'interaction_count': len(pairs),
            'complete': complete, 'partial': partial,
            'unestimable': unestimable,
            # 可单独估计的二因子交互：既非完全混杂，也未被秩亏吞掉。
            'estimable': [f'{a}*{b}' for a, b in pairs
                          if f'{a}*{b}' not in {row['interaction'] for row in complete}
                          and f'{a}*{b}' not in unestimable]}


def _coded_frame(design):
    factors = design.spec.factors
    return (np.asarray([[float(_screening_level(factor, run.settings[factor.factor_id]))
                         for factor in factors] for run in design.runs]),
            [factor.factor_id for factor in factors])


def _settings(factor, source, flip):
    coded = _screening_level(factor, source.settings[factor.factor_id])
    if not flip or source.point_type != 'factorial':
        return source.settings[factor.factor_id]
    if factor.factor_type == 'categorical':
        return factor.levels[1] if coded == -1 else factor.levels[0]
    return factor.high if coded == -1 else factor.low


def _unique_column(frame, base):
    names = set(frame.columns)
    candidate, index = base, 2
    while candidate in names:
        candidate = f'{base} ({index})'
        index += 1
    return candidate


def _nullable_dtype(column):
    """numpy dtype 无法记录空值，转同域可空 dtype；数值精度不变。"""
    if pd.api.types.is_extension_array_dtype(column.dtype) or column.dtype.kind == 'O':
        return column.dtype
    target = {'f': 'Float64', 'i': 'Int64', 'u': 'UInt64'}.get(column.dtype.kind)
    if target is None:
        raise ValueError(f'列 {column.name} 的 dtype {column.dtype} 无法记录空响应')
    return target


def create_pb_foldover(frame, metadata, folded_factors=None):
    """返回 (折叠工作表, 元数据, 摘要)；来源工作表不被修改。"""
    design = restore_design_result(frame, metadata)
    validate_pb(design)
    spec = design.spec
    factor_ids = tuple(factor.factor_id for factor in spec.factors)
    folded = fold_factor_ids(factor_ids,folded_factors)
    base_runs = tuple(sorted(design.runs, key=lambda run: run.standard_order))
    if len(base_runs) * 2 > MAX_RUNS:
        raise ValueError(f'折叠后运行总数不能超过 {MAX_RUNS}')
    base_count = len(base_runs)
    previous = spec.foldover_lineage
    batch_number = 1 if previous is None else int(previous['batch_id'].removeprefix('FOLD'))+1
    batch = f'FOLD{batch_number}'
    extended = (previous is not None or spec.block_count is not None
                or len({run.replicate for run in base_runs}) != 1
                or any(run.point_type != 'factorial' for run in base_runs)
                or any(factor.factor_type == 'categorical' for factor in spec.factors))
    columns = dict(metadata['column_map'])
    original = frame.copy(deep=True).reset_index(drop=True)
    if previous is None:
        columns['batch_id'] = _unique_column(frame, 'DOE 批次')
        columns['source_run_id'] = _unique_column(frame, 'DOE 源运行ID')
        original[columns['batch_id']] = 'BASE'
        original[columns['source_run_id']] = None

    factor_map = {factor.factor_id: factor for factor in spec.factors}
    prefix = 'F' if batch_number == 1 else f'F{batch_number}_'
    new_ids = [f'{prefix}{i:05d}' for i in range(1,base_count+1)]
    block_offset = spec.block_count or 0
    if block_offset:
        shuffled = []
        for block in range(1,block_offset+1):
            ids = [key for key,run in zip(new_ids,base_runs) if run.block == block]
            shuffled.extend(randomized_run_order(ids,spec.seed+block))
        order = {key: base_count+i for i,key in enumerate(shuffled,1)}
    else:
        order = {key: base_count+i for i,key in enumerate(
            randomized_run_order(new_ids,spec.seed),1)}
    additions, addition_records, run_map = [], [], []
    for index, (run_id, run) in enumerate(zip(new_ids,base_runs),1):
        settings = {factor_id: _settings(factor_map[factor_id], run, factor_id in folded)
                    for factor_id in factor_ids}
        row = {column: None for column in frame.columns}
        row[columns['run_id']] = run_id
        row[columns['standard_order']] = base_count + index
        row[columns['point_type']] = run.point_type
        block = run.block+block_offset if block_offset else None
        if columns.get('block') is not None:
            row[columns['block']] = block
        row[columns['replicate']] = run.replicate
        row.update({column: settings[factor_id]
                    for factor_id, column in columns['factors'].items()})
        row[columns['batch_id']] = batch
        row[columns['source_run_id']] = run.run_id
        additions.append(row)
        addition_records.append(replace(
            run, run_id=run_id, standard_order=base_count + index,
            run_order=order[run_id],
            settings=settings, block=block, measured_levels={key: None for key in run.measured_levels},
            responses={key: None for key in run.responses},
            batch_id=batch, source_run_id=run.run_id))
        run_map.append((run.run_id, run_id))
    for row in additions:
        row[columns['run_order']] = order[row[columns['run_id']]]

    fingerprint = pb_foldover_fingerprint if extended else foldover_matrix_fingerprint
    source_hash = fingerprint(base_runs,spec.factors)
    current_hash = fingerprint((*base_runs,*addition_records),spec.factors)
    tag = ('all' if folded == factor_ids else folded[0] if len(folded) == 1
           else 'M' + '-'.join(str(factor_ids.index(key) + 1) for key in folded))
    lineage = {'parent_design_id': spec.design_id, 'batch_id': batch,
               'folded_factors': folded, 'run_map': tuple(run_map),
               'source_matrix_sha256': source_hash,
               'current_matrix_sha256': current_hash}
    if previous is not None:
        lineage['previous'] = previous
    design_id = f'fold-{spec.design_id[:40]}-{tag}' if not extended else f'fold{batch_number}-{spec.design_id[:39]}-{tag}'
    folded_spec = replace(spec,design_id=design_id,
                          construction_version='v3' if extended else 'v2',
                          block_count=2*block_offset or None,foldover_lineage=lineage)
    result = pd.concat((original, pd.DataFrame(additions, columns=original.columns)),
                       ignore_index=True)
    result = result.sort_values(columns['run_order'], kind='stable').reset_index(drop=True)
    for factor in spec.factors:
        column = columns['factors'][factor.factor_id]
        result[column] = screening_level_series(result[column],factor)
    for column in (*columns['measured_levels'].values(), *columns['responses'].values()):
        result[column] = pd.array(result[column], dtype=_nullable_dtype(original[column]))
    result_metadata = worksheet_metadata(result, folded_spec, columns)
    validate_pb(restore_design_result(result, result_metadata))
    return result, result_metadata, pb_foldover_summary(result, result_metadata)


def pb_foldover_summary(frame, metadata):
    """折叠前后主效应/联合秩与混杂变化摘要。"""
    design = restore_design_result(frame, metadata)
    validate_pb(design)
    coded, names = _coded_frame(design)
    lineage = design.spec.foldover_lineage
    base = [run for run in design.runs if lineage is None or run.batch_id != lineage['batch_id']]
    added = [run for run in design.runs
             if lineage is not None and run.batch_id == lineage['batch_id']]
    before_coded = np.asarray([[float(_screening_level(f, run.settings[f.factor_id]))
                                for f in design.spec.factors] for run in base]) \
        if base else coded
    after = foldover_estimability(coded, names)
    before = foldover_estimability(before_coded, names)
    if lineage is None:
        return {'folded': False, 'base_runs': len(before_coded), 'added_runs': 0,
                'total_runs': len(coded), 'folded_factors': (), 'before': before,
                'after': after, 'batch_id': None, 'replicates_only': False,
                'confounding_reduced': False}
    folded = [run for run in base]
    copies = len({tuple(run.settings[f.factor_id] for f in design.spec.factors)
                  for run in folded})
    return {
        'folded': True, 'base_runs': len(before_coded), 'added_runs': len(added),
        'total_runs': len(coded), 'folded_factors': lineage['folded_factors'],
        'before': before, 'after': after, 'batch_id': lineage['batch_id'],
        'replicates_only': (copies < len(before_coded) or
                            after['joint_rank'] == before['joint_rank']),
        'confounding_reduced': (after['joint_rank'] > before['joint_rank'] or
                                len(after['complete']) < len(before['complete'])),
    }
