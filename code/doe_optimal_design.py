"""从候选工作表选择最优设计并生成独立工作表。"""
from dataclasses import replace

import numpy as np
import pandas as pd

from doe_core import (DesignResult, DesignSpec, FactorSpec, restore_design_result,
                      worksheet_metadata)
from doe_custom import (coded_value, design_matrix, matrix_sha256,
                        matrix_summary, validate_custom)
from doe_optimal import candidate_digest, evaluate, select, select_distance


def _candidate_spec(factors, responses, model_terms=()):
    copied = []
    for factor in factors:
        if factor.factor_type == 'continuous':
            copied.append(FactorSpec(factor.factor_id, factor.name, factor.low,
                                     factor.high, factor.unit))
        else:
            copied.append(FactorSpec(
                factor.factor_id, factor.name, None, None, factor.unit,
                factor_type='categorical', levels=tuple(factor.levels),
                level_type=('text' if all(isinstance(level, str)
                                          for level in factor.levels) else 'numeric')))
    return tuple(copied)


def optimal_from_candidates(frame, *, design_type, factors, responses,
                            column_map, count, model_terms=(), criterion='d_optimal',
                            seed=None, design_id=None, block_count=None):
    """在候选工作表上按 D-optimal 或 distance 准则选点。

    返回 (选中工作表, 元数据, 摘要)；候选工作表本身不被修改。
    """
    if criterion not in ('d_optimal', 'distance'):
        raise ValueError('准则必须是 d_optimal 或 distance')
    if design_type == 'custom_factorial' and criterion != 'd_optimal':
        raise ValueError('Factorial 设计只支持 D-optimality')
    if design_type not in ('custom_factorial', 'custom_rsm'):
        raise ValueError('当前最优设计只支持自定义因子或响应面设计')
    if design_type == 'custom_rsm' and not model_terms:
        raise ValueError('响应面最优设计必须显式声明模型项')
    if block_count is not None or column_map.get('block') is not None:
        raise ValueError(
            '带区组的候选工作表暂不支持最优设计：当前选点模型未纳入区组项，已拒绝创建')
    spec = DesignSpec(
        design_id or f'optimal-{design_type.split("_", 1)[1]}',
        _candidate_spec(factors, responses), tuple(responses), seed=seed,
        design_type=design_type, schema_version=5,
        model_terms=tuple(model_terms))
    metadata = worksheet_metadata(frame, spec, column_map)
    design = restore_design_result(frame, metadata)
    matrix, model = design_matrix(design)
    if criterion == 'd_optimal':
        summary = select(matrix.tolist(), count, seed=seed)
        if summary['rank'] != matrix.shape[1]:
            raise ValueError('所选设计不能估计目标模型（秩亏）')
        summary['selected_n'] = summary['count']
        summary['selected_p'] = summary['p']
        summary['selected_rank'] = summary['rank']
        summary['estimable'] = True
    else:
        continuous = [factor for factor in spec.factors
                      if factor.factor_type == 'continuous']
        # 轴点可位于声明范围之外，必须与设计矩阵使用同一编码语义。
        coded = np.asarray([[coded_value(factor, run.settings[factor.factor_id],
                                         run.point_type)
                             for factor in continuous] for run in design.runs])
        summary = select_distance(coded.tolist(), count)
        # 距离准则只管空间填充：按真正选中的运行重建模型矩阵，如实报告可估计性。
        order = list(summary['selection_order'])
        chosen_runs = tuple(
            replace(design.runs[index], standard_order=position + 1,
                    run_order=position + 1, replicate=1)
            for position, index in enumerate(order))
        selected_matrix = design_matrix(DesignResult(
            replace(spec, design_id=f'optimal-{design_type.split("_", 1)[1]}-opt'),
            chosen_runs))[0]
        selected = matrix_summary(selected_matrix)
        # 与 D-optimal 统一口径：报告的秩/参数数/logdet 都取自真正选中的运行。
        summary['rank'] = selected['rank']
        summary['p'] = selected['p']
        summary['logdet'] = evaluate(selected_matrix.tolist())['logdet']
        summary['selected_n'] = selected['n']
        summary['selected_p'] = selected['p']
        summary['selected_rank'] = selected['rank']
        summary['estimable'] = selected['estimable']
        summary['condition'] = selected['condition']
        if not selected['estimable']:
            raise ValueError(
                f"Distance-based 所选 {selected['n']} 个运行的模型矩阵秩为 "
                f"{selected['rank']}/{selected['p']}，不能估计目标模型")
    chosen = [design.runs[index] for index in summary['selection_order']]
    selected_frame = frame.iloc[list(summary['selection_order'])].reset_index(drop=True)
    selected_frame[column_map['standard_order']] = list(
        range(1, len(selected_frame) + 1))
    selected_frame[column_map['run_order']] = list(
        range(1, len(selected_frame) + 1))
    selected_frame[column_map['replicate']] = 1
    selected_id = design_id or f'optimal-{design_type.split("_", 1)[1]}'
    selected_spec = replace(
        spec, design_id=f'{selected_id}-opt', optimal_lineage={
            'parent_design_id': spec.design_id,
            'criterion': 'd_optimal' if criterion == 'd_optimal' else 'distance',
            'candidate_sha256': candidate_digest(matrix.tolist()),
            'selection_order': tuple(run.run_id for run in chosen),
            'batch_id': 'OPT1',
        })
    result_metadata = worksheet_metadata(selected_frame, selected_spec, column_map)
    return selected_frame, result_metadata, summary
