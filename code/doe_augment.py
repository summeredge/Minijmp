"""通用运行增补：保留父设计、原始响应与运行映射，新增批次独立。"""
from dataclasses import replace
from itertools import combinations, combinations_with_replacement
from math import comb
from numbers import Integral

import numpy as np
import pandas as pd

from doe_core import (RunRecord, restore_design_result, worksheet_metadata)
from doe_rsm_model import TermModel
from doe_optimal import select_distance
from doe_custom import coded_value


_MAX_RUNS = 10000
# 增补穷举按组合数限额：30 选 15 = 155117520 个子集必须降级为启发式。
_MAX_EXACT_SUBSETS = 200_000


def _model_terms(spec, terms):
    if terms is not None:
        return tuple(terms)
    if spec.model_terms:
        return tuple(spec.model_terms)
    if spec.design_type in ('custom_factorial', 'general_full_factorial'):
        return tuple(factor.factor_id for factor in spec.factors)
    return None


def _rows(design, settings_rows, terms, point_types=None):
    """用与设计相同的模型项构造矩阵；分类水平按参考水平哑变量。

    连续因子统一走 coded_value(factor, value, point_type)：轴点允许位于
    声明 low/high 之外，其余点类型仍严格校验取值范围。
    """
    spec = design.spec
    model = TermModel(spec.factors, terms, blocks=0)
    coded = []
    for position, settings in enumerate(settings_rows):
        point = (None if point_types is None else
                 point_types[position] if position < len(point_types) else None)
        row = {}
        for factor in spec.factors:
            value = settings[factor.factor_id]
            if factor.factor_type == 'categorical':
                if value not in factor.levels:
                    raise ValueError(f'因子 {factor.factor_id} 的水平不在已声明范围内')
                row[factor.factor_id] = value
            else:
                row[factor.factor_id] = coded_value(factor, value, point)
        coded.append(row)
    return model, model.matrix(coded)


def _logdet(matrix):
    singular = np.linalg.svd(matrix, compute_uv=False)
    if not len(singular) or singular[-1] <= 1e-10 * max(1.0, singular[0]):
        return None
    return float(2 * np.sum(np.log(singular)))


def _greedy_augment_with_replacement(initial, candidates, count):
    """固定父矩阵，对新增候选做多起点贪婪+交换，允许新增重复点。"""
    import random
    rng = random.Random(0)
    starts = [None] + list(range(min(len(candidates), 8)))
    rng.shuffle(starts)
    best, best_value, evaluations = None, None, 0
    for start in starts:
        chosen = [] if start is None else [start]
        while len(chosen) < count:
            ranked = []
            for index in range(len(candidates)):
                matrix = np.vstack((initial, candidates[chosen + [index]]))
                value = _logdet(matrix)
                evaluations += 1
                ranked.append((int(np.linalg.matrix_rank(matrix)),
                               value if value is not None else float('-inf'),
                               index))
            ranked.sort(key=lambda item: (-item[0], -item[1], item[2]))
            chosen.append(ranked[0][2])
        chosen, value, extra = _exchange_augment_with_replacement(
            initial, candidates, chosen)
        evaluations += extra
        if value is not None and (best_value is None or value > best_value + 1e-12):
            best, best_value = chosen, value
    return best, best_value, evaluations


def _exchange_augment_with_replacement(initial, candidates, chosen):
    """仅交换新增位置，允许与父点或其他新增点重合。"""
    chosen = list(chosen)
    current = _logdet(np.vstack((initial, candidates[chosen])))
    if current is None:
        return chosen, current, 0
    evaluations = 0
    for _ in range(100):
        improved = False
        for position in range(len(chosen)):
            for candidate in range(len(candidates)):
                if candidate == chosen[position]:
                    continue
                trial = chosen.copy()
                trial[position] = candidate
                value = _logdet(np.vstack((initial, candidates[trial])))
                evaluations += 1
                if value is not None and value > current + 1e-12:
                    chosen, current = trial, value
                    improved = True
                    break
            if improved:
                break
        if not improved:
            break
    return chosen, current, evaluations


def select_augment(initial, candidates, count, *, exact_limit=_MAX_EXACT_SUBSETS,
                   allow_repeats=False):
    """固定初始运行，从候选行选 count 行最大化 det(X'X)。

    精确穷举由组合数预算决定，而不是只看候选行数：父设计点始终固定，
    只从候选行新增，交换/删除不会触及已执行运行。
    """
    if not isinstance(allow_repeats, bool):
        raise ValueError('allow_repeats 必须是布尔值')
    initial = np.asarray(initial, dtype=float)
    candidates = np.asarray(candidates, dtype=float)
    if candidates.ndim != 2 or not len(candidates):
        raise ValueError('候选矩阵必须是非空二维矩阵')
    if isinstance(count, bool) or not isinstance(count, Integral) or count < 1:
        raise ValueError('增补数量必须是正整数')
    count = int(count)
    if not allow_repeats and count > len(candidates):
        raise ValueError('增补数量不能超过候选行数')
    if not allow_repeats and len({tuple(row) for row in candidates.tolist()}) < count:
        raise ValueError('候选点不足：增补数量超过不同候选行数')
    subsets = (comb(len(candidates) + count - 1, count) if allow_repeats
               else comb(len(candidates), count))
    best, best_value = None, None
    if subsets <= exact_limit:
        choices = (combinations_with_replacement(range(len(candidates)), count)
                   if allow_repeats else combinations(range(len(candidates)), count))
        for indices in choices:
            value = _logdet(np.vstack((initial, candidates[list(indices)])))
            if value is not None and (best_value is None or value > best_value + 1e-12):
                best, best_value = list(indices), value
        method = 'exact_enumeration'
        reason = '完成全部候选组合穷举'
        evaluations = subsets
    else:
        if allow_repeats:
            best, best_value, evaluations = _greedy_augment_with_replacement(
                initial, candidates, count)
        else:
            best, best_value, evaluations = _greedy_augment(initial, candidates, count)
        method = 'greedy_exchange'
        reason = f'候选组合数 {subsets} 超过预算 {exact_limit}'
    if best is None:
        raise ValueError('没有使模型满秩的增补候选组合')
    combined = np.vstack((initial, candidates[best]))
    result = {'indices': tuple(sorted(best)), 'selection_order': tuple(best),
            'logdet': float(best_value), 'method': method,
            'initial_rank': int(np.linalg.matrix_rank(initial)),
            'augmented_rank': int(np.linalg.matrix_rank(combined)),
            'p': int(combined.shape[1]),
            'subsets': subsets, 'evaluations': evaluations,
            'exact_budget': exact_limit, 'stop_reason': reason,
            'global_optimum_proven': method == 'exact_enumeration'}
    if allow_repeats:
        counts = {}
        for index in best:
            counts[index] = counts.get(index, 0) + 1
        result['multiplicities'] = tuple(sorted(counts.items()))
        result['allow_repeats'] = True
    return result


def _greedy_augment(initial, candidates, count):
    """有界确定性增补搜索：多起点贪婪 + 只换候选的交换改进。

    initial 固定在前，交换只在新增位置与未选候选之间进行，因此已执行运行
    不会被删除或替换。返回 (选中索引, logdet, 评价次数)。
    """
    import random
    rng = random.Random(0)
    starts = list(range(min(len(candidates), 8)))
    rng.shuffle(starts)
    best, best_value, evaluations = None, None, 0
    for start in starts:
        chosen = [start]
        remaining = [index for index in range(len(candidates)) if index != start]
        while len(chosen) < count:
            ranked = []
            for index in remaining:
                matrix = np.vstack((initial, candidates[chosen + [index]]))
                value = _logdet(matrix)
                evaluations += 1
                ranked.append((int(np.linalg.matrix_rank(matrix)),
                               value if value is not None else float('-inf'),
                               index))
            ranked.sort(key=lambda item: (-item[0], -item[1], item[2]))
            chosen.append(ranked[0][2])
            remaining.remove(ranked[0][2])
        chosen, value, extra = _exchange_augment(initial, candidates, chosen)
        evaluations += extra
        if value is not None and (best_value is None or value > best_value + 1e-12):
            best, best_value = chosen, value
    return best, best_value, evaluations


def _exchange_augment(initial, candidates, chosen):
    """仅在新增位置与未选候选间交换；父设计行不参与。"""
    chosen = list(chosen)
    current = _logdet(np.vstack((initial, candidates[chosen])))
    if current is None:
        return chosen, current, 0
    evaluations = 0
    for _ in range(100):
        improved = False
        outside = [index for index in range(len(candidates)) if index not in chosen]
        for position in range(len(chosen)):
            for candidate in outside:
                trial = chosen.copy()
                trial[position] = candidate
                value = _logdet(np.vstack((initial, candidates[trial])))
                evaluations += 1
                if value is not None and value > current + 1e-12:
                    chosen, current = trial, value
                    improved = True
                    break
            if improved:
                break
        if not improved:
            break
    return chosen, current, evaluations


def _distance_augment(design, candidates, initial, candidate_matrix, count,
                      point_types=None):
    """Distance-based 增补：父设计运行作为固定已选点，按最远点规则补点。

    距离坐标只取连续因子的编码值（响应面设计空间），与 select_distance 一致。
    """
    continuous = [factor for factor in design.spec.factors
                  if factor.factor_type == 'continuous']
    if not continuous:
        raise ValueError('Distance-based 增补需要至少一个连续因子')
    fixed = [[coded_value(factor, run.settings[factor.factor_id], run.point_type)
              for factor in continuous] for run in design.runs]
    points = [[coded_value(factor, settings[factor.factor_id],
                           None if point_types is None else point_types[position])
               for factor in continuous]
              for position, settings in enumerate(candidates)]
    summary = select_distance(points, count, initial=fixed)
    combined = np.vstack((initial, candidate_matrix[list(summary['selection_order'])]))
    value = _logdet(combined)
    return {'indices': summary['indices'],
            'selection_order': summary['selection_order'],
            'logdet': value, 'method': 'distance',
            'min_squared_distance': summary['min_squared_distance'],
            'initial_logdet': _logdet(initial),
            'initial_rank': int(np.linalg.matrix_rank(initial)),
            'augmented_rank': int(np.linalg.matrix_rank(combined)),
            'p': int(combined.shape[1]),
            'global_optimum_proven': False}


def augment(frame, metadata, candidates, count, *, terms=None, seed=None,
            batch_id='AUG1', criterion='d_optimal', run_ids=None,
            design_id=None, point_types=None):
    """返回 (新工作表, 元数据, 增补摘要)；来源工作表不被修改。"""
    design = restore_design_result(frame, metadata)
    spec, runs = design.spec, design.runs
    if spec.design_type == 'mixture':
        raise ValueError('混料设计必须使用混料最优设计增补，不能使用普通 DOE 矩阵')
    if spec.design_type == 'split_plot':
        raise ValueError('Split-Plot 请使用“修改设计”中的“增加完整区组”')
    if spec.foldover_lineage is not None:
        raise ValueError('折叠设计已含批次谱系；请新建设计，不要通过增补改写历史运行')
    if criterion not in ('d_optimal', 'manual', 'distance'):
        raise ValueError('增补准则无效')
    if criterion == 'distance' and spec.design_type != 'custom_rsm':
        raise ValueError('Distance-based 增补只支持响应面设计')
    if len(runs) + count > _MAX_RUNS:
        raise ValueError(f'运行总数不能超过 {_MAX_RUNS}')
    if isinstance(count, bool) or not isinstance(count, Integral) or count < 1:
        raise ValueError('增补数量必须是正整数')
    if not isinstance(candidates, (list, tuple)) or not candidates:
        raise ValueError('必须提供候选运行设置')
    factor_ids = {factor.factor_id for factor in spec.factors}
    for settings in candidates:
        if not isinstance(settings, dict) or set(settings) != factor_ids:
            raise ValueError('每个候选运行必须覆盖全部因子')
    if point_types is None:
        point_types = ['factorial'] * len(candidates)
    if len(point_types) != len(candidates) or any(
            value not in ('factorial', 'center', 'axial', 'edge')
            for value in point_types):
        raise ValueError('候选点类型数量或取值无效')
    model, initial = _rows(design, [run.settings for run in runs],
                           _model_terms(spec, terms),
                           [run.point_type for run in runs])
    _, candidate_matrix = _rows(design, candidates, _model_terms(spec, terms),
                                point_types)
    if criterion == 'manual':
        # 用户明确按给定顺序选择候选：不重新优化，只取前 count 行。
        order = list(range(int(count)))
        combined = np.vstack((initial, candidate_matrix[order]))
        chosen = {'indices': tuple(range(int(count))),
                  'selection_order': tuple(order),
                  'logdet': _logdet(combined), 'method': 'manual',
                  'initial_rank': int(np.linalg.matrix_rank(initial)),
                  'augmented_rank': int(np.linalg.matrix_rank(combined)),
                  'p': int(combined.shape[1]),
                  'global_optimum_proven': False,
                  'subsets': 1, 'evaluations': 1, 'exact_budget': 0,
                  'stop_reason': '按用户给定候选顺序增补，未执行准则搜索'}
    else:
        chosen = (_distance_augment(design, candidates, initial, candidate_matrix,
                                    int(count), point_types)
                  if criterion == 'distance'
                  else select_augment(initial, candidate_matrix, int(count)))
    # 距离准则不优化行列式，可能选不出可估计的补点；此时拒绝写入，避免
    # 产生一个保存后无法分析的增补设计。
    if chosen['augmented_rank'] < chosen['p']:
        raise ValueError('增补后模型仍秩亏，所选候选不能使目标模型可估计')
    chosen['rank_improved'] = chosen['augmented_rank'] > chosen['initial_rank']
    columns = metadata['column_map']
    batch_column = columns.get('batch_id')
    source_column = columns.get('source_run_id')
    if batch_column is None or source_column is None:
        raise ValueError('当前设计列映射缺少批次或来源运行列')
    existing = set(run.run_id for run in runs)
    start = len(runs) + 1
    new_ids = ([f'A{index:05d}' for index in range(1, int(count) + 1)]
               if run_ids is None else list(run_ids))
    if len(new_ids) != int(count) or len(set(new_ids)) != len(new_ids):
        raise ValueError('新增运行 ID 数量或唯一性无效')
    if existing & set(new_ids):
        raise ValueError('新增运行 ID 与已有运行冲突')
    result = frame.copy(deep=True).reset_index(drop=True)
    result[batch_column] = result[batch_column].where(
        result[batch_column].notna(), 'BASE')
    result[source_column] = result[source_column].where(
        result[source_column].isna(), None)
    additions, records = [], []
    for offset, index in enumerate(chosen['selection_order']):
        settings = dict(candidates[index])
        point = point_types[index]
        continuous_zero = all(
            factor.factor_type != 'continuous'
            or coded_value(factor, settings[factor.factor_id], point) == 0.0
            for factor in spec.factors)
        if point == 'factorial' and spec.design_type == 'custom_factorial':
            for factor in spec.factors:
                if factor.factor_type == 'categorical':
                    continue
                coded = coded_value(factor, settings[factor.factor_id], point)
                if coded not in (-1.0, 1.0):
                    raise ValueError('自定义两水平因子设计只能增补低/高水平因子点')
        if point == 'center' and not continuous_zero:
            raise ValueError('中心点候选必须位于全部连续因子中点')
        row = {column: None for column in result.columns}
        run_id = new_ids[offset]
        row[columns['run_id']] = run_id
        row[columns['standard_order']] = start + offset
        row[columns['run_order']] = start + offset
        row[columns['point_type']] = point
        row[columns['replicate']] = 1
        if columns.get('block') is not None:
            row[columns['block']] = None
        for factor_id, column in columns['factors'].items():
            row[column] = settings[factor_id]
        row[batch_column] = batch_id
        row[source_column] = None
        additions.append(row)
        records.append(RunRecord(
            run_id=run_id, standard_order=start + offset,
            run_order=start + offset, point_type=point,
            settings=settings, replicate=1, block=None,
            responses={name: None for name in spec.response_names},
            batch_id=batch_id))
    result = pd.concat((result, pd.DataFrame(additions, columns=result.columns)),
                       ignore_index=True)
    for factor_id, column in columns['factors'].items():
        result[column] = result[column].astype(object)
    for column in (*columns['measured_levels'].values(), *columns['responses'].values()):
        result[column] = pd.array(result[column], dtype='Float64')
    result[columns['standard_order']] = result[columns['standard_order']].astype(int)
    result[columns['run_order']] = result[columns['run_order']].astype(int)
    result[columns['replicate']] = result[columns['replicate']].astype(int)
    from doe_core import DesignResult
    from doe_custom import matrix_sha256
    parent = DesignResult(spec, tuple(runs))
    from dataclasses import replace as _replace
    parent_hash = matrix_sha256(parent)
    target_id = design_id or f'aug-{spec.design_id[:40]}-{batch_id}'
    current_hash = matrix_sha256(DesignResult(spec, tuple(runs) + tuple(records)))
    augmented_spec = replace(
        spec, design_id=target_id,
        augmentation_lineage={
            'parent_design_id': spec.design_id,
            'batch_id': batch_id,
            'criterion': criterion,
            'run_map': [(None, record.run_id) for record in records],
            'source_matrix_sha256': parent_hash,
            'current_matrix_sha256': current_hash,
        })
    result_metadata = worksheet_metadata(result, augmented_spec, columns)
    chosen['parent_design_id'] = spec.design_id
    chosen['batch_id'] = batch_id
    return result, result_metadata, chosen


def augment_mixture(parent_frame, parent_mixture, parent_doe,
                    candidate_frame, candidate_mixture, candidate_doe,
                    count, *, criterion='d_optimal', degree=None, terms=None,
                    allow_repeats=False, distance_variables=(), batch_id='AUG1',
                    design_id=None):
    """Mixture 专用增补：Scheffé D-optimal 或组件/归一化变量 Distance。"""
    from collections import Counter
    from uuid import uuid4

    import pandas as pd

    from doe_core import (DesignResult, RunRecord, restore_design_result,
                          worksheet_metadata)
    from doe_custom import matrix_sha256
    from doe_mixture import (mixture_metadata, mixture_model_config,
                             restore_mixture)
    from doe_mixture_model import MixtureTermModel
    from doe_optimal import evaluate, select_distance
    from doe_optimal_design import (_mixture_distance_coordinates,
                                    _mixture_source,
                                    _unique_mixture_candidates)
    from doe_mixture_designs import MAX_RUNS

    if criterion not in ('d_optimal', 'distance'):
        raise ValueError('混料增补准则必须是 d_optimal 或 distance')
    if not isinstance(allow_repeats, bool):
        raise ValueError('allow_repeats 必须是布尔值')
    if criterion == 'distance' and allow_repeats:
        raise ValueError('Distance-based 增补不允许重复设计点')
    if isinstance(count, bool) or not isinstance(count, Integral) or count < 1:
        raise ValueError('增补数量必须是正整数')
    count = int(count)
    if not isinstance(distance_variables, (tuple, list)):
        raise ValueError('距离变量必须是过程/总量变量 ID 列表')
    variables = tuple(distance_variables)
    if (len(variables) != len(set(variables))
            or any(not isinstance(name, str) for name in variables)):
        raise ValueError('距离变量只能是不重复的过程/总量变量 ID')
    if criterion == 'd_optimal' and variables:
        raise ValueError('D-optimal 增补的变量必须通过 Scheffé 模型项指定')
    if not isinstance(batch_id, str) or not batch_id or batch_id != batch_id.strip():
        raise ValueError('batch_id 必须是非空字符串')
    if batch_id == 'BASE':
        raise ValueError('增补 batch_id 不能使用保留值 BASE')
    if (not isinstance(parent_mixture, dict)
            or not isinstance(candidate_mixture, dict)
            or parent_mixture.get('schema_version') != 1
            or candidate_mixture.get('schema_version') != 1):
        raise ValueError('Schema 2 改善设计不能作为普通 append-only 增补来源')

    parent_spec, parent_rows, parent_design = _mixture_source(
        parent_frame, parent_mixture, parent_doe)
    candidate_spec, candidate_rows, _ = _mixture_source(
        candidate_frame, candidate_mixture, candidate_doe)
    if parent_design.spec.augmentation_lineage is not None:
        raise ValueError('当前仅支持对尚未增补过的 Mixture 父设计增补')
    if (parent_spec.components != candidate_spec.components
            or parent_spec.process_variables != candidate_spec.process_variables
            or parent_spec.amount_variables != candidate_spec.amount_variables
            or parent_spec.amount_settings != candidate_spec.amount_settings
            or parent_spec.linear_constraints != candidate_spec.linear_constraints
            or parent_spec.response_names != candidate_spec.response_names):
        raise ValueError('父设计与候选表的组分、变量、约束或响应定义不一致')
    if len(parent_rows) + count > MAX_RUNS:
        raise ValueError(f'运行总数不能超过 {MAX_RUNS}')
    if any(name not in parent_spec.variable_ids for name in variables):
        raise ValueError('距离变量只能选择已声明的过程/总量变量')

    model_degree = degree if degree is not None else (parent_spec.degree or 2)
    model = MixtureTermModel(parent_spec, terms, model_degree)
    parent_matrix = model.matrix([item['settings'] for item in parent_rows])
    candidates, duplicate_count = _unique_mixture_candidates(
        candidate_spec, candidate_rows)
    parent_keys = {
        tuple(item['settings'][name]
              for name in (*parent_spec.component_ids, *parent_spec.variable_ids))
        for item in parent_rows}

    if criterion == 'd_optimal':
        if not allow_repeats:
            candidates = [item for item in candidates
                          if tuple(item['settings'][name]
                                   for name in (*parent_spec.component_ids,
                                                *parent_spec.variable_ids))
                          not in parent_keys]
        if not candidates:
            raise ValueError('没有可用的 Mixture 增补候选点')
        candidate_matrix = model.matrix([item['settings'] for item in candidates])
        chosen = select_augment(parent_matrix, candidate_matrix, count,
                                allow_repeats=allow_repeats)
        selected_indices = chosen['selection_order']
        method = chosen['method']
        global_optimum = chosen['global_optimum_proven']
        distance_summary = None
    else:
        component_count = len(parent_spec.components)
        variables, parent_coordinates = _mixture_distance_coordinates(
            parent_spec, parent_rows, variables)
        _, candidate_coordinates = _mixture_distance_coordinates(
            parent_spec, candidates, variables)
        seen_coordinates = set(parent_coordinates)
        unique_candidates = []
        unique_coordinates = []
        for item, point in zip(candidates, candidate_coordinates):
            if point in seen_coordinates:
                continue
            seen_coordinates.add(point)
            unique_candidates.append(item)
            unique_coordinates.append(point)
        candidates = unique_candidates
        if not candidates:
            raise ValueError('候选点不足：没有未使用的 Mixture 距离点')
        distance_summary = select_distance(
            unique_coordinates, count, kind='mixture',
            component_count=component_count, initial=parent_coordinates)
        selected_indices = distance_summary['selection_order']
        method = 'distance_farthest_point'
        global_optimum = False
        candidate_matrix = model.matrix([item['settings'] for item in candidates])
        combined_matrix = np.vstack((parent_matrix,
                                     candidate_matrix[list(selected_indices)]))
        initial_evaluation = evaluate(parent_matrix.tolist())
        final_evaluation = evaluate(combined_matrix.tolist())
        chosen = {
            'indices': distance_summary['indices'],
            'selection_order': tuple(selected_indices),
            'logdet': final_evaluation['logdet'], 'method': method,
            'initial_rank': initial_evaluation['rank'],
            'augmented_rank': final_evaluation['rank'],
            'p': final_evaluation['p'],
            'subsets': 0, 'evaluations': distance_summary['evaluations'],
            'exact_budget': 0, 'stop_reason': '按固定父设计锚点完成最远点增补',
            'global_optimum_proven': False,
            'min_squared_distance': distance_summary['min_squared_distance'],
        }

    combined_matrix = np.vstack((parent_matrix,
                                 candidate_matrix[list(selected_indices)]))
    initial_evaluation = evaluate(parent_matrix.tolist())
    final_evaluation = evaluate(combined_matrix.tolist())
    if final_evaluation['rank'] != final_evaluation['p']:
        raise ValueError('增补后 Mixture 模型仍秩亏，候选点未写入')

    selected_items = [candidates[index] for index in selected_indices]
    counts = Counter(selected_indices)
    multiplicities = tuple((candidates[index]['run_id'], multiplicity)
                           for index, multiplicity in sorted(counts.items()))
    batch_column = parent_doe['column_map'].get('batch_id')
    source_column = parent_doe['column_map'].get('source_run_id')
    result = parent_frame.copy(deep=True).reset_index(drop=True)
    column_map = dict(parent_doe['column_map'])
    for key, base, default in (('batch_id', 'DOE 批次', 'BASE'),
                               ('source_run_id', 'DOE 源运行ID', None)):
        column = column_map.get(key)
        if column is None:
            name, suffix = base, 2
            while name in result.columns:
                name = f'{base} ({suffix})'
                suffix += 1
            result[name] = default
            column_map[key] = name
        elif column not in result.columns:
            raise ValueError(f'DOE 列映射缺少字段 {column}')
    batch_column, source_column = column_map['batch_id'], column_map['source_run_id']
    batches = result[batch_column].dropna().tolist()
    if any(value != 'BASE' for value in batches):
        raise ValueError('Mixture 父设计包含其他批次；当前不支持重复增补')

    from collections import defaultdict
    replicate_by_settings = defaultdict(int)
    for item in parent_rows:
        key = tuple(item['settings'][name]
                    for name in (*parent_spec.component_ids, *parent_spec.variable_ids))
        replicate_by_settings[key] = max(
            replicate_by_settings[key], int(item['row']['重复']))
    start = len(parent_rows) + 1
    existing_ids = {(type(item['run_id']).__name__, item['run_id'])
                    for item in parent_rows}
    new_ids = []
    next_id = 1
    while len(new_ids) < count:
        candidate_id = f'MA{next_id:05d}'
        next_id += 1
        key = (type(candidate_id).__name__, candidate_id)
        if key not in existing_ids:
            new_ids.append(candidate_id)
            existing_ids.add(key)

    additions, records = [], []
    for offset, (item, run_id) in enumerate(zip(selected_items, new_ids)):
        settings = dict(item['settings'])
        key = tuple(settings[name]
                    for name in (*parent_spec.component_ids, *parent_spec.variable_ids))
        replicate_by_settings[key] += 1
        point_type = item['row']['点类型']
        row = {column: None for column in result.columns}
        row[column_map['run_id']] = run_id
        row[column_map['standard_order']] = start + offset
        row[column_map['run_order']] = start + offset
        row[column_map['point_type']] = point_type
        row[column_map['replicate']] = replicate_by_settings[key]
        for factor_id, column in column_map['factors'].items():
            row[column] = settings[factor_id]
        row[batch_column] = batch_id
        row[source_column] = item['run_id']
        additions.append(row)
        records.append(RunRecord(
            run_id=run_id, standard_order=start + offset,
            run_order=start + offset, point_type=point_type,
            settings=settings, replicate=replicate_by_settings[key], block=None,
            responses={name: None for name in parent_spec.response_names},
            batch_id=batch_id, source_run_id=item['run_id']))

    result = pd.concat((result, pd.DataFrame(additions, columns=result.columns)),
                       ignore_index=True)
    for factor_id, column in column_map['factors'].items():
        result[column] = result[column].astype(object)
    result[column_map['standard_order']] = result[column_map['standard_order']].astype(int)
    result[column_map['run_order']] = result[column_map['run_order']].astype(int)
    result[column_map['replicate']] = result[column_map['replicate']].astype(int)

    target_id = design_id or f'mix-aug-{parent_spec.design_id[:32]}-{batch_id}'
    parent_hash = matrix_sha256(parent_design)
    target_spec = replace(
        parent_design.spec, design_id=target_id, optimal_lineage=None,
        augmentation_lineage=None)
    current_hash = matrix_sha256(DesignResult(
        target_spec, tuple(parent_design.runs) + tuple(records)))
    target_spec = replace(target_spec, augmentation_lineage={
        'parent_design_id': parent_spec.design_id,
        'batch_id': batch_id, 'criterion': criterion,
        'run_map': [(item['run_id'], run_id)
                    for item, run_id in zip(selected_items, new_ids)],
        'source_matrix_sha256': parent_hash,
        'current_matrix_sha256': current_hash,
    })
    result_doe = worksheet_metadata(result, target_spec, column_map)
    result_mixture_spec = replace(parent_spec, design_id=target_id)
    result_mixture = mixture_metadata(result, result_mixture_spec)
    model_config = mixture_model_config(
        result, result_mixture, result_mixture_spec.response_names[0],
        model.degree, model.terms, result_doe)

    summary = dict(chosen)
    summary.update({
        'criterion': criterion, 'parent_design_id': parent_spec.design_id,
        'batch_id': batch_id, 'initial_n': len(parent_rows),
        'added_n': count, 'augmented_n': len(parent_rows) + count,
        'initial_rank': initial_evaluation['rank'],
        'augmented_rank': final_evaluation['rank'],
        'initial_logdet': initial_evaluation['logdet'],
        'logdet': final_evaluation['logdet'],
        'condition': final_evaluation['condition'],
        'p': final_evaluation['p'], 'rank_improved': (
            final_evaluation['rank'] > initial_evaluation['rank']),
        'global_optimum_proven': global_optimum,
        'multiplicities': multiplicities,
        'selected_run_ids': tuple(new_ids),
        'selected_source_run_ids': tuple(item['run_id'] for item in selected_items),
        'collapsed_duplicate_candidates': duplicate_count,
        'model_terms': model.terms, 'degree': model.degree,
        'distance_variables': variables,
    })
    restored = restore_design_result(result, result_doe)
    if tuple(run.run_id for run in restored.runs[-count:]) != tuple(new_ids):
        raise ValueError('Mixture 增补 run_id 映射与新增运行不一致')
    if tuple(run.source_run_id for run in restored.runs[-count:]) != tuple(
            item['run_id'] for item in selected_items):
        raise ValueError('Mixture 增补来源运行映射不一致')
    summary['candidate_count'] = len(candidates)
    return result, result_doe, result_mixture, model_config, summary
