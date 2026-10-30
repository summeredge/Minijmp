"""从候选工作表选择最优设计并生成独立工作表。"""
from dataclasses import replace
from hashlib import sha256
import json

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


def _mixture_source(frame, mixture_metadata, doe_metadata):
    from doe_core import restore_design_result
    from doe_mixture import restore_mixture

    design = restore_design_result(frame, doe_metadata)
    mixture, rows = restore_mixture(frame, mixture_metadata, doe_metadata)
    if (design.spec.design_type != 'mixture'
            or design.spec.design_id != mixture.design_id
            or tuple(factor.factor_id for factor in design.spec.factors)
            != (*mixture.component_ids, *mixture.variable_ids)):
        raise ValueError('DOE 与 Mixture 设计身份不一致')
    return mixture, rows, design


def _unique_mixture_candidates(spec, rows):
    keys = (*spec.component_ids, *spec.variable_ids)
    selected, seen = [], set()
    for item in rows:
        key = tuple(item['settings'][name] for name in keys)
        if key not in seen:
            selected.append(item)
            seen.add(key)
    return selected, len(rows) - len(selected)


def _mixture_digest(payload):
    encoded = json.dumps(payload, allow_nan=False, sort_keys=True,
                         separators=(',', ':')).encode('utf-8')
    return sha256(encoded).hexdigest()


def _new_source_column(frame, column_map):
    column_map = dict(column_map)
    column = column_map.get('source_run_id')
    if column is None:
        base, column = 'DOE 源运行ID', 'DOE 源运行ID'
        index = 2
        while column in frame.columns:
            column = f'{base} ({index})'
            index += 1
        frame[column] = None
        column_map['source_run_id'] = column
    return column_map, column


def select_mixture_optimal(frame, mixture_metadata, doe_metadata, count, *,
                           criterion='d_optimal', degree=None, terms=None,
                           allow_repeats=False, distance_variables=(), seed=None,
                           design_id=None):
    """从合法 Mixture 候选工作表选点，返回新工作表、双层元数据和摘要。

    新设计使用独立 run ID、空响应和 source_run_id 映射；来源候选表不修改。
    """
    from collections import Counter
    from uuid import uuid4

    from doe_core import restore_design_result, worksheet_metadata
    from doe_mixture import (mixture_metadata as make_mixture_metadata,
                             mixture_model_config)
    from doe_mixture_model import MixtureTermModel

    if criterion not in ('d_optimal', 'distance'):
        raise ValueError('准则必须是 d_optimal 或 distance')
    if not isinstance(allow_repeats, bool):
        raise ValueError('allow_repeats 必须是布尔值')
    if criterion == 'distance' and allow_repeats:
        raise ValueError('Distance-based 不允许重复设计点')
    if isinstance(count, bool) or not isinstance(count, (int, np.integer)) or count < 1:
        raise ValueError('所选运行数必须是正整数')
    if count > 10000:
        raise ValueError('运行总数不能超过 10000')
    if seed is not None and (isinstance(seed, bool) or not isinstance(seed, (int, np.integer))):
        raise ValueError('seed 必须是整数或 None')
    if (not isinstance(mixture_metadata, dict)
            or mixture_metadata.get('schema_version') != 1):
        raise ValueError('改善谱系设计不能作为普通选点来源；请使用新的候选设计')

    source_spec, source_rows, source_design = _mixture_source(
        frame, mixture_metadata, doe_metadata)
    candidates, duplicate_count = _unique_mixture_candidates(source_spec, source_rows)
    model_degree = degree if degree is not None else (source_spec.degree or 2)
    model = MixtureTermModel(source_spec, terms, model_degree)
    candidate_matrix = model.matrix([item['settings'] for item in candidates])
    if not isinstance(distance_variables, (tuple, list)):
        raise ValueError('距离变量必须是过程/总量变量 ID 列表')
    variables = tuple(distance_variables)
    if (len(variables) != len(set(variables))
            or any(name not in source_spec.variable_ids for name in variables)):
        raise ValueError('距离变量只能是不重复的过程/总量变量 ID')
    if criterion == 'd_optimal' and variables:
        raise ValueError('D-optimal 的变量必须通过 Scheffé 模型项指定')

    if criterion == 'd_optimal':
        summary = select(candidate_matrix.tolist(), int(count), seed=seed,
                         allow_repeats=allow_repeats)
        selected_indices = summary['selection_order']
        search_method = summary['method']
        global_optimum = summary['global_optimum_proven']
        candidate_identity = {
            'model_terms': list(model.terms), 'degree': model.degree,
            'component_units': 'proportions',
            'allow_repeats': allow_repeats,
            'candidate_matrix': sorted(map(list, candidate_matrix.tolist())),
        }
        summary['criterion'] = 'd_optimal'
        summary['allow_repeats'] = allow_repeats
    else:
        component_count = len(source_spec.components)
        variables, coordinates = _mixture_distance_coordinates(
            source_spec, candidates, variables)
        summary = select_distance(
            coordinates, int(count), kind='mixture', component_count=component_count)
        selected_indices = summary['selection_order']
        search_method = 'distance_farthest_point'
        global_optimum = False
        candidate_identity = {
            'component_units': 'proportions', 'variables': list(variables),
            'normalization': 'declared low/high to [0,1]',
            'coordinates': sorted(map(list, coordinates)),
        }
        summary['criterion'] = 'distance'
        summary['allow_repeats'] = False

    selected_items = [candidates[index] for index in selected_indices]
    counts = Counter(selected_indices)
    summary['multiplicities'] = tuple(
        (candidates[index]['run_id'], multiplicity)
        for index, multiplicity in sorted(counts.items()))
    selected_matrix = model.matrix([item['settings'] for item in selected_items])
    evaluation = evaluate(selected_matrix.tolist())
    if evaluation['rank'] != evaluation['p']:
        raise ValueError(
            f'所选 Mixture 设计不能估计模型（秩 {evaluation["rank"]}/{evaluation["p"]}）')
    summary.update({
        'method': search_method, 'global_optimum_proven': global_optimum,
        'candidate_count': len(candidates), 'candidate_rows': len(source_rows),
        'collapsed_duplicate_candidates': duplicate_count,
        'selected_n': len(selected_items), 'selected_p': evaluation['p'],
        'selected_rank': evaluation['rank'], 'rank': evaluation['rank'],
        'p': evaluation['p'], 'condition': evaluation['condition'],
        'logdet': evaluation['logdet'], 'estimable': True,
        'model_terms': model.terms, 'degree': model.degree,
        'distance_variables': variables,
        'stop_reason': summary.get('stop_reason', '达到目标运行数，最远点选择结束'),
    })

    selected_id = design_id or f'optimal-mixture-{uuid4().hex}'
    selected_frame = frame.iloc[[item['position'] for item in selected_items]].copy()
    selected_frame = selected_frame.reset_index(drop=True)
    column_map, source_column = _new_source_column(
        selected_frame, doe_metadata['column_map'])
    count_by_settings = Counter()
    replicate_values = []
    setting_ids = (*source_spec.component_ids, *source_spec.variable_ids)
    for item in selected_items:
        key = tuple(item['settings'][name] for name in setting_ids)
        count_by_settings[key] += 1
        replicate_values.append(count_by_settings[key])
    new_run_ids = [f'MO{index:05d}' for index in range(1, len(selected_items) + 1)]
    selected_frame[column_map['run_id']] = new_run_ids
    selected_frame[column_map['standard_order']] = list(range(1, len(selected_items) + 1))
    selected_frame[column_map['run_order']] = list(range(1, len(selected_items) + 1))
    selected_frame[column_map['replicate']] = replicate_values
    selected_frame[source_column] = [item['run_id'] for item in selected_items]
    for column in column_map['responses'].values():
        selected_frame[column] = pd.array([None] * len(selected_items), dtype='Float64')

    lineage = {
        'parent_design_id': source_spec.design_id,
        'criterion': criterion,
        'candidate_sha256': _mixture_digest(candidate_identity),
        'selection_order': tuple(new_run_ids), 'batch_id': 'OPT1',
    }
    selected_doe_spec = replace(
        source_design.spec, design_id=selected_id,
        optimal_lineage=lineage, augmentation_lineage=None)
    selected_doe_metadata = worksheet_metadata(
        selected_frame, selected_doe_spec, column_map)
    selected_mixture_spec = replace(source_spec, design_id=selected_id)
    selected_mixture_metadata = make_mixture_metadata(
        selected_frame, selected_mixture_spec)
    model_config = mixture_model_config(
        selected_frame, selected_mixture_metadata,
        selected_mixture_spec.response_names[0], model.degree, model.terms)
    restored = restore_design_result(selected_frame, selected_doe_metadata)
    if tuple(run.run_id for run in restored.runs) != tuple(new_run_ids):
        raise ValueError('最优选点输出顺序与 DOE 谱系不一致')
    summary['selected_run_ids'] = tuple(new_run_ids)
    summary['selected_source_run_ids'] = tuple(item['run_id'] for item in selected_items)
    summary['candidate_sha256'] = lineage['candidate_sha256']
    summary['component_units'] = 'proportions'
    return selected_frame, selected_doe_metadata, selected_mixture_metadata, model_config, summary


def _mixture_distance_coordinates(spec, rows, distance_variables):
    if not isinstance(distance_variables, (tuple, list)):
        raise ValueError('距离变量必须是过程/总量变量 ID 列表')
    variables = tuple(distance_variables)
    if (len(variables) != len(set(variables))
            or any(name not in spec.variable_ids for name in variables)):
        raise ValueError('距离变量只能是不重复的过程/总量变量 ID')
    coordinates = []
    for item in rows:
        settings = item['settings']
        point = [settings[name] for name in spec.component_ids]
        for name in variables:
            variable = spec.variable(name)
            point.append((settings[name] - variable.low)
                         / (variable.high - variable.low))
        coordinates.append(tuple(point))
    return tuple(variables), coordinates


def evaluate_mixture_design(frame, mixture_metadata, doe_metadata, *,
                           criterion='d_optimal', degree=None, terms=None,
                           distance_variables=()):
    """评价当前 Mixture 工作表的模型信息或距离覆盖，不修改来源表。"""
    from doe_mixture_model import MixtureTermModel

    from doe_optimal import evaluate

    if criterion not in ('d_optimal', 'distance'):
        raise ValueError('评价准则必须是 d_optimal 或 distance')
    if criterion == 'd_optimal' and distance_variables:
        raise ValueError('D-optimal 评价不接受距离变量')
    spec, rows, _ = _mixture_source(frame, mixture_metadata, doe_metadata)
    model_degree = degree if degree is not None else (spec.degree or 2)
    model = MixtureTermModel(spec, terms, model_degree)
    matrix = model.matrix([item['settings'] for item in rows])
    summary = evaluate(matrix.tolist())
    summary.update({
        'criterion': criterion, 'method': ('information_matrix'
                                            if criterion == 'd_optimal'
                                            else 'minimum_distance'),
        'n': len(rows), 'model_terms': model.terms, 'degree': model.degree,
        'estimable': summary['rank'] == summary['p'],
    })
    if criterion == 'distance':
        variables, coordinates = _mixture_distance_coordinates(
            spec, rows, distance_variables)
        points = {tuple(point) for point in coordinates}
        distances = [float(np.sum((np.asarray(coordinates[a])
                                  - np.asarray(coordinates[b])) ** 2))
                     for a in range(len(coordinates))
                     for b in range(a + 1, len(coordinates))]
        summary.update({
            'distance_variables': variables,
            'unique_distance_points': len(points),
            'collapsed_duplicate_points': len(coordinates) - len(points),
            'min_squared_distance': min(distances) if distances else None,
        })
    return summary
