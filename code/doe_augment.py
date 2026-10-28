"""通用运行增补：保留父设计、原始响应与运行映射，新增批次独立。"""
from dataclasses import replace
from itertools import combinations
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


def select_augment(initial, candidates, count, *, exact_limit=_MAX_EXACT_SUBSETS):
    """固定初始运行，从候选行选 count 行最大化 det(X'X)。

    精确穷举由组合数预算决定，而不是只看候选行数：父设计点始终固定，
    只从候选行新增，交换/删除不会触及已执行运行。
    """
    initial = np.asarray(initial, dtype=float)
    candidates = np.asarray(candidates, dtype=float)
    if candidates.ndim != 2 or not len(candidates):
        raise ValueError('候选矩阵必须是非空二维矩阵')
    if isinstance(count, bool) or not isinstance(count, Integral) or count < 1:
        raise ValueError('增补数量必须是正整数')
    count = int(count)
    if count > len(candidates):
        raise ValueError('增补数量不能超过候选行数')
    if len({tuple(row) for row in candidates.tolist()}) < count:
        raise ValueError('候选点不足：增补数量超过不同候选行数')
    subsets = comb(len(candidates), count)
    best, best_value = None, None
    if subsets <= exact_limit:
        for indices in combinations(range(len(candidates)), count):
            value = _logdet(np.vstack((initial, candidates[list(indices)])))
            if value is not None and (best_value is None or value > best_value + 1e-12):
                best, best_value = list(indices), value
        method = 'exact_enumeration'
        reason = '完成全部候选组合穷举'
        evaluations = subsets
    else:
        best, best_value, evaluations = _greedy_augment(initial, candidates, count)
        method = 'greedy_exchange'
        reason = f'候选组合数 {subsets} 超过预算 {exact_limit}'
    if best is None:
        raise ValueError('没有使模型满秩的增补候选组合')
    combined = np.vstack((initial, candidates[best]))
    return {'indices': tuple(sorted(best)), 'selection_order': tuple(best),
            'logdet': float(best_value), 'method': method,
            'initial_rank': int(np.linalg.matrix_rank(initial)),
            'augmented_rank': int(np.linalg.matrix_rank(combined)),
            'p': int(combined.shape[1]),
            'subsets': subsets, 'evaluations': evaluations,
            'exact_budget': exact_limit, 'stop_reason': reason,
            'global_optimum_proven': method == 'exact_enumeration'}


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
