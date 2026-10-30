"""Plackett–Burman 折叠：复制原运行并翻转全部或一个因子。

PB 没有正规 defining relation；此处只按实际编码矩阵计算秩、投影与
完全/部分混杂，不生成正规别名。
"""
from dataclasses import replace

import numpy as np
import pandas as pd

from doe_core import (RunRecord, _screening_level, foldover_matrix_fingerprint,
                      randomized_run_order, restore_design_result,
                      screening_matrix_sha256, worksheet_metadata)
from doe_pb import validate_pb


BATCH_ID = 'FOLD1'
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


def _check_source(design, folded):
    spec = design.spec
    if design.spec.foldover_lineage is not None:
        raise ValueError('不支持对已有 Foldover 设计再次折叠')
    if any(factor.factor_type != 'continuous' for factor in spec.factors):
        raise ValueError('PB Foldover 仅支持连续两水平因子')
    if spec.block_count is not None:
        raise ValueError('PB Foldover 不支持分区组设计')
    if len({run.replicate for run in design.runs}) != 1:
        raise ValueError('PB Foldover 不支持多个重复批次')
    if any(run.point_type != 'factorial' for run in design.runs):
        raise ValueError('PB Foldover 不支持中心点或伪中心点')
    factor_ids = tuple(factor.factor_id for factor in spec.factors)
    if folded is None:
        folded = factor_ids
    elif isinstance(folded, str) and folded == '全部':
        folded = factor_ids
    elif isinstance(folded, str):
        folded = (folded,)
    elif isinstance(folded, (tuple, list)):
        folded = tuple(folded)
    else:
        raise ValueError('折叠因子必须是全部或一个因子 ID')
    if folded != factor_ids and (len(folded) != 1 or folded[0] not in factor_ids):
        raise ValueError('仅支持折叠全部因子或指定一个因子')
    if len(set(folded)) != len(folded):
        raise ValueError('折叠因子不得重复')
    return tuple(key for key in factor_ids if key in folded)


def _settings(factor, source, flip):
    coded = _screening_level(factor, source.settings[factor.factor_id])
    value = -coded if flip else coded
    return factor.low if value == -1 else factor.high


def _unique_column(frame, base):
    names = set(frame.columns)
    candidate, index = base, 2
    while candidate in names:
        candidate = f'{base} ({index})'
        index += 1
    return candidate


def _folded_order(seed, base_count):
    """新增批次的运行序区间：仅追加在 base_count 之后。"""
    new_ids = [f'F{i:05d}' for i in range(1, base_count + 1)]
    return {run_id: base_count + index
            for index, run_id in enumerate(randomized_run_order(new_ids, seed), 1)}


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
    folded = _check_source(design, folded_factors)
    spec = design.spec
    factor_ids = tuple(factor.factor_id for factor in spec.factors)
    base_runs = tuple(sorted(design.runs, key=lambda run: run.standard_order))
    if len(base_runs) * 2 > MAX_RUNS:
        raise ValueError(f'折叠后运行总数不能超过 {MAX_RUNS}')
    base_count = len(base_runs)
    columns = dict(metadata['column_map'])
    columns['batch_id'] = _unique_column(frame, 'DOE 批次')
    columns['source_run_id'] = _unique_column(frame, 'DOE 源运行ID')
    original = frame.copy(deep=True).reset_index(drop=True)
    original[columns['batch_id']] = 'BASE'
    original[columns['source_run_id']] = None

    factor_map = {factor.factor_id: factor for factor in spec.factors}
    order = _folded_order(spec.seed, base_count)
    additions, addition_records, run_map = [], [], []
    for index, run in enumerate(base_runs, 1):
        run_id = f'F{index:05d}'
        settings = {factor_id: _settings(factor_map[factor_id], run, factor_id in folded)
                    for factor_id in factor_ids}
        row = {column: None for column in frame.columns}
        row[columns['run_id']] = run_id
        row[columns['standard_order']] = base_count + index
        row[columns['point_type']] = 'factorial'
        row[columns['replicate']] = run.replicate
        row.update({column: settings[factor_id]
                    for factor_id, column in columns['factors'].items()})
        row[columns['batch_id']] = BATCH_ID
        row[columns['source_run_id']] = run.run_id
        additions.append(row)
        addition_records.append(replace(
            run, run_id=run_id, standard_order=base_count + index,
            run_order=order[run_id],
            settings=settings, measured_levels={key: None for key in run.measured_levels},
            responses={key: None for key in run.responses},
            batch_id=BATCH_ID, source_run_id=run.run_id))
        run_map.append((run.run_id, run_id))
    for row in additions:
        row[columns['run_order']] = order[row[columns['run_id']]]

    source_hash = foldover_matrix_fingerprint(base_runs, spec.factors)
    current_hash = foldover_matrix_fingerprint((*base_runs, *addition_records),
                                               spec.factors)
    tag = 'all' if folded == factor_ids else folded[0]
    lineage = {'parent_design_id': spec.design_id, 'batch_id': BATCH_ID,
               'folded_factors': folded, 'run_map': tuple(run_map),
               'source_matrix_sha256': source_hash,
               'current_matrix_sha256': current_hash}
    folded_spec = replace(spec, design_id=f'fold-{spec.design_id[:40]}-{tag}',
                          construction_version='v2', foldover_lineage=lineage)
    result = pd.concat((original, pd.DataFrame(additions, columns=original.columns)),
                       ignore_index=True)
    result = result.sort_values(columns['run_order'], kind='stable').reset_index(drop=True)
    for column in columns['factors'].values():
        result[column] = result[column].astype(object)
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
    base = [run for run in design.runs if run.batch_id in (None, 'BASE')]
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
