"""Mixture D-optimal Replace/Improve and its Schema 2 recovery contract."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import date, datetime
from hashlib import sha256
import json
import math
from numbers import Integral, Real
import random
import re

import numpy as np
import pandas as pd

from doe_augment import _MAX_EXACT_SUBSETS, select_augment
from doe_core import restore_design_result, worksheet_metadata
from doe_mixture import (MixtureSpec, input_fingerprint, mixture_rows,
                         restore_mixture)
from doe_mixture_constraints import MixtureConstraintError
from doe_mixture_model import MixtureTermModel
from doe_optimal import evaluate
from doe_mixture_designs import MAX_RUNS


_SNAPSHOT_KEYS = {'frame', 'doe', 'mixture'}
_FRAME_KEYS = {'columns', 'rows'}
_LINEAGE_KEYS = {
    'parent_design_id', 'parent_snapshot', 'parent_snapshot_sha256',
    'parent_input_fingerprint', 'parent_response_snapshot',
    'parent_response_sha256', 'locked_run_ids', 'replaceable_run_ids',
    'retained_run_ids', 'candidate_design_id', 'candidate_snapshot',
    'candidate_snapshot_sha256', 'candidate_input_fingerprint',
    'candidate_run_ids', 'selected_run_ids',
    'candidate_to_replaced_parent', 'criterion', 'model_degree',
    'model_terms', 'candidate_matrix_sha256', 'parent_matrix_sha256',
    'current_matrix_sha256', 'parent_rank', 'parent_logdet', 'current_rank',
    'current_logdet', 'seed', 'evaluation_budget', 'actual_evaluations',
    'stop_reason', 'global_optimum_proven',
}


def _json_bytes(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True,
                      separators=(',', ':')).encode('utf-8')


def _digest(value):
    return sha256(_json_bytes(value)).hexdigest()


def _encode_scalar(value):
    if value is None:
        return {'type': 'none'}
    if value is pd.NA:
        return {'type': 'pd.NA'}
    if value is pd.NaT:
        return {'type': 'pd.NaT'}
    if isinstance(value, pd.Timestamp):
        return {'type': 'timestamp', 'value': value.isoformat()}
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, bool):
        return {'type': 'bool', 'value': value}
    if isinstance(value, Integral):
        return {'type': 'int', 'value': str(int(value))}
    if isinstance(value, Real):
        return {'type': 'float', 'value': float(value).hex()}
    if isinstance(value, datetime):
        return {'type': 'datetime', 'value': value.isoformat()}
    if isinstance(value, date):
        return {'type': 'date', 'value': value.isoformat()}
    if isinstance(value, str):
        return {'type': 'str', 'value': value}
    raise MixtureConstraintError(
        f'改善谱系快照不支持工作表单元格类型 {type(value).__name__}')


def _decode_scalar(value):
    if not isinstance(value, dict) or not isinstance(value.get('type'), str):
        raise MixtureConstraintError('改善谱系单元格快照无效')
    kind = value['type']
    if kind in ('none', 'pd.NA', 'pd.NaT'):
        if set(value) != {'type'}:
            raise MixtureConstraintError('改善谱系空值快照无效')
        return {'none': None, 'pd.NA': pd.NA, 'pd.NaT': pd.NaT}[kind]
    if set(value) != {'type', 'value'}:
        raise MixtureConstraintError('改善谱系单元格字段无效')
    raw = value['value']
    if kind == 'bool' and type(raw) is bool:
        return raw
    if kind == 'int' and isinstance(raw, str) \
            and re.fullmatch(r'-?(?:0|[1-9][0-9]*)', raw):
        return int(raw)
    if kind == 'float' and isinstance(raw, str):
        try:
            number = float.fromhex(raw)
        except ValueError as error:
            raise MixtureConstraintError('改善谱系浮点快照无效') from error
        if number.hex() == raw:
            return number
    if kind == 'str' and isinstance(raw, str):
        return raw
    if kind == 'timestamp' and isinstance(raw, str):
        try:
            return pd.Timestamp(raw)
        except ValueError as error:
            raise MixtureConstraintError('改善谱系时间快照无效') from error
    if kind == 'datetime' and isinstance(raw, str):
        try:
            return datetime.fromisoformat(raw)
        except ValueError as error:
            raise MixtureConstraintError('改善谱系时间快照无效') from error
    if kind == 'date' and isinstance(raw, str):
        try:
            return date.fromisoformat(raw)
        except ValueError as error:
            raise MixtureConstraintError('改善谱系日期快照无效') from error
    raise MixtureConstraintError('改善谱系单元格类型或值无效')


def _frame_snapshot(frame):
    return {
        'columns': [_encode_scalar(name) for name in frame.columns.tolist()],
        'rows': [[_encode_scalar(value) for value in row]
                 for row in frame.itertuples(index=False, name=None)],
    }


def _snapshot(frame, doe_metadata, mixture_metadata_value):
    return {'frame': _frame_snapshot(frame), 'doe': deepcopy(doe_metadata),
            'mixture': deepcopy(mixture_metadata_value)}


def _snapshot_frame(snapshot):
    if not isinstance(snapshot, dict) or set(snapshot) != _SNAPSHOT_KEYS:
        raise MixtureConstraintError('改善谱系设计快照结构无效')
    raw = snapshot['frame']
    if (not isinstance(raw, dict) or set(raw) != _FRAME_KEYS
            or not isinstance(raw['columns'], list)
            or not isinstance(raw['rows'], list)):
        raise MixtureConstraintError('改善谱系工作表快照结构无效')
    columns = [_decode_scalar(value) for value in raw['columns']]
    rows = []
    for row in raw['rows']:
        if not isinstance(row, list) or len(row) != len(columns):
            raise MixtureConstraintError('改善谱系工作表行快照无效')
        rows.append([_decode_scalar(value) for value in row])
    try:
        return pd.DataFrame(rows, columns=columns, dtype=object)
    except (TypeError, ValueError) as error:
        raise MixtureConstraintError('改善谱系工作表快照无法恢复') from error


def _id_key(value):
    if isinstance(value, bool) or not isinstance(value, (str, Integral)):
        raise MixtureConstraintError('改善谱系运行 ID 必须是字符串或整数')
    if isinstance(value, str) and not value:
        raise MixtureConstraintError('改善谱系运行 ID 不能为空')
    return ('int', int(value)) if isinstance(value, Integral) else ('str', value)


def _ids(values, label):
    if not isinstance(values, (list, tuple, set, frozenset)):
        raise MixtureConstraintError(f'{label} 必须是运行 ID 集合')
    result = tuple(values)
    keys = [_id_key(value) for value in result]
    if len(set(keys)) != len(keys):
        raise MixtureConstraintError(f'{label}不得含重复 ID')
    return result


def _hash_value(value, label):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9a-f]{64}', value):
        raise MixtureConstraintError(f'{label} SHA-256 无效')


def _v5_source(frame, mixture_meta, doe_meta, label):
    if not frame.columns.is_unique:
        raise MixtureConstraintError(f'{label} 工作表列名必须唯一')
    if (not isinstance(doe_meta, dict)
            or type(doe_meta.get('schema_version')) is not int
            or doe_meta['schema_version'] != 5):
        raise MixtureConstraintError(f'{label} 必须使用 DOE Schema v5')
    if (not isinstance(mixture_meta, dict)
            or type(mixture_meta.get('schema_version')) is not int
            or mixture_meta['schema_version'] != 1):
        raise MixtureConstraintError(f'{label} 必须是普通 Mixture Schema 1 设计')
    spec, rows = restore_mixture(frame, mixture_meta, doe_meta)
    if len(rows) > MAX_RUNS:
        raise MixtureConstraintError(f'{label} 运行总数不能超过 {MAX_RUNS}')
    for variable in spec.amount_variables:
        if any(item['settings'][variable.variable_id] <= 0 for item in rows):
            raise MixtureConstraintError(f'{label} 总量变量 {variable.variable_id} 必须大于 0')
    design = restore_design_result(frame, doe_meta)
    if (design.spec.design_type != 'mixture'
            or design.spec.design_id != spec.design_id
            or design.spec.construction_version != spec.construction_version
            or tuple(factor.factor_id for factor in design.spec.factors)
            != (*spec.component_ids, *spec.variable_ids)
            or design.spec.response_names != spec.response_names):
        raise MixtureConstraintError(f'{label} 的 DOE v5 与 Mixture 身份不一致')
    return spec, rows, design


def _domain_signature(spec):
    data = spec.to_dict()
    return {key: data[key] for key in (
        'components', 'process_variables', 'amount_variables',
        'linear_constraints', 'response_names', 'construction_version')}


def _ordered(items, column):
    return sorted(items, key=lambda item: int(item['row'][column]))


def _matrix_digest(model, items, run_id_column, order_column):
    ordered = _ordered(items, order_column)
    matrix = model.matrix([item['settings'] for item in ordered])
    return _digest({
        'terms': list(model.terms),
        'run_ids': [_encode_scalar(item['row'][run_id_column]) for item in ordered],
        'matrix': [[float(value).hex() for value in row] for row in matrix],
    })


def _response_snapshot(frame, spec, rows):
    return [
        {'run_id': _encode_scalar(item['run_id']),
         'responses': {name: _encode_scalar(item['row'][f'响应_{name}'])
                       for name in spec.response_names}}
        for item in rows
    ]


def _run_snapshot(frame, row, column_map):
    position = row['position']
    labels = []
    for key in ('run_id', 'standard_order', 'run_order', 'point_type',
                'replicate', 'block', 'whole_plot_id', 'subplot_id',
                'whole_plot_order', 'subplot_order', 'batch_id',
                'source_run_id', 'control_run_id', 'noise_condition_id'):
        label = column_map.get(key)
        if label is not None and label not in labels:
            labels.append(label)
    for key in ('factors', 'measured_levels', 'responses'):
        labels.extend(label for label in column_map.get(key, {}).values()
                      if label is not None and label not in labels)
    return [[_encode_scalar(label), _encode_scalar(frame.iloc[position][label])]
            for label in labels]


def _has_experiment_identity(run):
    return (any(value is not None for value in run.responses.values())
            or any(value is not None for value in run.measured_levels.values()))


def _new_run_id(parent_id, candidate_design_id, candidate_id, replaced_id,
                seed, used):
    if _id_key(candidate_id) not in used:
        return candidate_id
    for salt in range(100):
        suffix = _digest({
            'parent': parent_id, 'candidate_design': candidate_design_id,
            'candidate': _encode_scalar(candidate_id), 'seed': seed,
            'replaced': _encode_scalar(replaced_id), 'salt': salt,
        })[:24]
        value = 'IMP-' + suffix
        if _id_key(value) not in used:
            return value
    raise MixtureConstraintError('无法生成不冲突的新增运行 ID')


def _search(spec, parent_rows, candidate_rows, locked_ids, replaceable_ids,
            candidate_ids, model, seed, budget):
    parent_by_id = {_id_key(item['run_id']): item for item in parent_rows}
    candidate_by_id = {_id_key(item['run_id']): item for item in candidate_rows}
    locked = [parent_by_id[_id_key(value)] for value in locked_ids]
    replaceable = _ordered(
        [parent_by_id[_id_key(value)] for value in replaceable_ids], '标准序')
    candidates = [candidate_by_id[_id_key(value)] for value in candidate_ids]
    if not replaceable:
        raise MixtureConstraintError('必须明确指定至少一个可替换运行')
    if len(candidates) < len(replaceable):
        raise MixtureConstraintError('候选不足：候选运行数少于可替换运行数')
    factor_ids = (*spec.component_ids, *spec.variable_ids)
    parent_points = {tuple(item['settings'][key] for key in factor_ids)
                     for item in parent_rows}
    candidate_points = [tuple(item['settings'][key] for key in factor_ids)
                        for item in candidates]
    if any(point in parent_points for point in candidate_points):
        raise MixtureConstraintError('候选设计包含已存在于父设计的运行设定')
    if len(set(candidate_points)) != len(candidate_points):
        raise MixtureConstraintError('候选设计含重复运行设定，候选身份不唯一')
    combinations_count = math.comb(len(candidates), len(replaceable))
    if combinations_count > budget:
        raise MixtureConstraintError(
            f'候选子集数 {combinations_count} 超过评价预算 {budget}；未创建改善设计')
    locked_matrix = (model.matrix([item['settings'] for item in locked])
                     if locked else np.empty((0, model.width), dtype=float))
    candidate_matrix = model.matrix([item['settings'] for item in candidates])
    order = list(range(len(candidates)))
    random.Random(seed).shuffle(order)
    selected = select_augment(
        locked_matrix, candidate_matrix[order], len(replaceable),
        exact_limit=budget, allow_repeats=False)
    chosen = [candidates[order[index]] for index in selected['selection_order']]
    if (selected['method'] != 'exact_enumeration'
            or not selected['global_optimum_proven']
            or selected['evaluations'] != combinations_count):
        raise MixtureConstraintError('候选搜索未完成预算内的精确穷举')
    return replaceable, candidates, chosen, selected


def _validation_source(snapshot, label):
    frame = _snapshot_frame(snapshot)
    spec, rows, design = _v5_source(
        frame, snapshot['mixture'], snapshot['doe'], label)
    return frame, spec, rows, design


def _validate_lineage_shape(lineage):
    if not isinstance(lineage, dict) or set(lineage) != _LINEAGE_KEYS:
        raise MixtureConstraintError('improvement_lineage 字段无效')
    for key in ('parent_snapshot_sha256', 'parent_response_sha256',
                'candidate_snapshot_sha256', 'candidate_matrix_sha256',
                'parent_matrix_sha256', 'current_matrix_sha256'):
        _hash_value(lineage[key], key)
    for key in ('parent_design_id', 'candidate_design_id',
                'parent_input_fingerprint', 'candidate_input_fingerprint',
                'criterion', 'stop_reason'):
        if not isinstance(lineage[key], str) or not lineage[key]:
            raise MixtureConstraintError(f'{key} 必须是非空字符串')
    if lineage['criterion'] != 'd_optimal':
        raise MixtureConstraintError('仅支持 D-optimal Replace/Improve')
    if lineage['stop_reason'] != 'exhaustive_candidate_subsets':
        raise MixtureConstraintError('改善搜索停止原因无效')
    for key in ('locked_run_ids', 'replaceable_run_ids', 'retained_run_ids',
                'candidate_run_ids', 'selected_run_ids'):
        values = lineage[key]
        if not isinstance(values, list):
            raise MixtureConstraintError(f'{key} 必须是列表')
        if len({_id_key(_decode_scalar(value)) for value in values}) != len(values):
            raise MixtureConstraintError(f'{key} 不得含重复 ID')
    if not isinstance(lineage['candidate_to_replaced_parent'], list):
        raise MixtureConstraintError('替换映射必须是列表')
    for pair in lineage['candidate_to_replaced_parent']:
        if (not isinstance(pair, dict) or set(pair) != {
                'candidate_run_id', 'selected_run_id', 'replaced_parent_run_id'}):
            raise MixtureConstraintError('候选替换映射字段无效')
        for value in pair.values():
            _decode_scalar(value)
    if isinstance(lineage['model_degree'], bool) or type(lineage['model_degree']) is not int \
            or not 1 <= lineage['model_degree'] <= 3:
        raise MixtureConstraintError('模型阶数无效')
    if (not isinstance(lineage['model_terms'], list) or not lineage['model_terms']
            or any(not isinstance(term, str) or not term for term in lineage['model_terms'])
            or len(set(lineage['model_terms'])) != len(lineage['model_terms'])):
        raise MixtureConstraintError('模型项列表无效')
    if isinstance(lineage['seed'], bool) or not isinstance(lineage['seed'], Integral):
        raise MixtureConstraintError('随机 seed 必须是整数')
    for key in ('evaluation_budget', 'actual_evaluations', 'parent_rank', 'current_rank'):
        if isinstance(lineage[key], bool) or type(lineage[key]) is not int \
                or lineage[key] < (1 if 'evaluations' in key or key == 'evaluation_budget' else 0):
            raise MixtureConstraintError(f'{key} 数值无效')
    for key in ('parent_logdet', 'current_logdet'):
        value = lineage[key]
        if value is not None and (isinstance(value, bool) or not isinstance(value, Real)
                                  or not math.isfinite(float(value))):
            raise MixtureConstraintError(f'{key} 必须是有限数值或 null')
    if lineage['global_optimum_proven'] is not True:
        raise MixtureConstraintError('精确候选穷举必须证明当前候选域内全局最优')
    if not isinstance(lineage['parent_response_snapshot'], list):
        raise MixtureConstraintError('父响应快照必须是列表')


def _same_number(left, right):
    return ((left is None and right is None)
            or (left is not None and right is not None
                and math.isclose(float(left), float(right), rel_tol=1e-12, abs_tol=1e-12)))


def _validate_metrics(lineage, parent_matrix, candidate_matrix,
                      current_matrix, model, chosen, budget):
    before = evaluate(parent_matrix.tolist())
    after = evaluate(current_matrix.tolist())
    if after['rank'] != model.width or after['logdet'] is None:
        raise MixtureConstraintError('改善后模型矩阵不满秩')
    if (before['logdet'] is not None
            and after['logdet'] < before['logdet'] - 1e-12):
        raise MixtureConstraintError('候选域无法得到 logdet 不劣于父设计的改善结果')
    if (lineage['parent_rank'] != before['rank']
            or lineage['current_rank'] != after['rank']
            or not _same_number(lineage['parent_logdet'], before['logdet'])
            or not _same_number(lineage['current_logdet'], after['logdet'])
            or lineage['actual_evaluations'] != chosen['evaluations']
            or lineage['evaluation_budget'] != budget
            or lineage['actual_evaluations'] != math.comb(
                len(candidate_matrix), len(chosen['selection_order']))):
        raise MixtureConstraintError('改善优化评价与候选矩阵重算结果不一致')


def validate_improvement_lineage(current_frame, mixture_meta, doe_meta):
    """重建父/候选设计并重算候选穷举，联合验证 DOE v5 与当前表。"""
    lineage = mixture_meta['improvement_lineage']
    _validate_lineage_shape(lineage)
    current_spec = MixtureSpec.from_dict(mixture_meta['spec'])
    current_design = restore_design_result(current_frame, doe_meta)
    if (current_design.spec.design_type != 'mixture'
            or current_design.spec.design_id != current_spec.design_id
            or current_design.spec.augmentation_lineage is not None
            or current_design.spec.optimal_lineage is not None
            or tuple(factor.factor_id for factor in current_design.spec.factors)
            != (*current_spec.component_ids, *current_spec.variable_ids)
            or current_design.spec.response_names != current_spec.response_names):
        raise MixtureConstraintError('DOE v5 与改善后 Mixture 身份不一致')

    parent_frame, parent_spec, parent_rows, parent_design = _validation_source(
        lineage['parent_snapshot'], '父设计快照')
    candidate_frame, candidate_spec, candidate_rows, candidate_design = _validation_source(
        lineage['candidate_snapshot'], '候选设计快照')
    if (parent_spec.design_id != lineage['parent_design_id']
            or candidate_spec.design_id != lineage['candidate_design_id']
            or _domain_signature(parent_spec) != _domain_signature(candidate_spec)
            or _domain_signature(parent_spec) != _domain_signature(current_spec)):
        raise MixtureConstraintError('父、候选与当前混料设计定义不一致')
    if (parent_design.spec.design_type != 'mixture'
            or candidate_design.spec.design_type != 'mixture'
            or parent_design.spec.response_names != candidate_design.spec.response_names
            or lineage['parent_snapshot']['doe']['column_map']
            != lineage['candidate_snapshot']['doe']['column_map']
            or parent_frame.columns.tolist() != candidate_frame.columns.tolist()
            or parent_frame.columns.tolist() != current_frame.columns.tolist()
            or lineage['parent_input_fingerprint']
            != lineage['parent_snapshot']['mixture']['worksheet']['input_fingerprint']
            or lineage['candidate_input_fingerprint']
            != lineage['candidate_snapshot']['mixture']['worksheet']['input_fingerprint']):
        raise MixtureConstraintError('父、候选或当前工作表输入身份不一致')
    if (_digest(lineage['parent_snapshot']) != lineage['parent_snapshot_sha256']
            or _digest(lineage['candidate_snapshot'])
            != lineage['candidate_snapshot_sha256']):
        raise MixtureConstraintError('父或候选设计快照 SHA-256 不匹配')

    response_snapshot = _response_snapshot(parent_frame, parent_spec, parent_rows)
    if (response_snapshot != lineage['parent_response_snapshot']
            or _digest(response_snapshot) != lineage['parent_response_sha256']):
        raise MixtureConstraintError('父设计原始响应快照与 SHA-256 不一致')

    parent_ids = [_id_key(item['run_id']) for item in parent_rows]
    locked_ids = [_decode_scalar(value) for value in lineage['locked_run_ids']]
    replaceable_ids = [_decode_scalar(value) for value in lineage['replaceable_run_ids']]
    retained_ids = [_decode_scalar(value) for value in lineage['retained_run_ids']]
    candidate_ids = [_decode_scalar(value) for value in lineage['candidate_run_ids']]
    selected_ids = [_decode_scalar(value) for value in lineage['selected_run_ids']]
    if (set(map(_id_key, locked_ids)) & set(map(_id_key, replaceable_ids))
            or set(map(_id_key, (*locked_ids, *replaceable_ids))) != set(parent_ids)
            or set(map(_id_key, retained_ids)) != set(map(_id_key, locked_ids))
            or set(map(_id_key, candidate_ids)) - {_id_key(item['run_id'])
                                                    for item in candidate_rows}
            or len(candidate_ids) != len(lineage['candidate_run_ids'])):
        raise MixtureConstraintError('Locked/Replaceable/Candidate 身份集合不合法')
    parent_run_by_id = {_id_key(run.run_id): run for run in parent_design.runs}
    for run_id in replaceable_ids:
        if _has_experiment_identity(parent_run_by_id[_id_key(run_id)]):
            raise MixtureConstraintError(
                f'已执行或有实验身份的父运行不可替换：{run_id}')
    candidate_run_by_id = {_id_key(run.run_id): run for run in candidate_design.runs}
    for run_id in candidate_ids:
        if _has_experiment_identity(candidate_run_by_id[_id_key(run_id)]):
            raise MixtureConstraintError(
                f'已执行或有实验身份的候选运行不可选择：{run_id}')

    degree = lineage['model_degree']
    terms = tuple(lineage['model_terms'])
    model = MixtureTermModel(parent_spec, terms, degree)
    if list(model.terms) != lineage['model_terms']:
        raise MixtureConstraintError('改善模型项顺序无效')
    budget = lineage['evaluation_budget']
    if budget > _MAX_EXACT_SUBSETS:
        raise MixtureConstraintError('改善评价预算超过现有 D-optimal 核心上限')
    replaceable, candidate_pool, chosen, search = _search(
        parent_spec,
        parent_rows, candidate_rows, locked_ids, replaceable_ids,
        candidate_ids, model, int(lineage['seed']), budget)
    if search['global_optimum_proven'] is not True:
        raise MixtureConstraintError('候选子集未完成穷举')

    used_ids = {_id_key(item['run_id']) for item in parent_rows}
    expected_mapping = []
    for candidate, replaced in zip(chosen, replaceable):
        new_id = _new_run_id(parent_spec.design_id, candidate_spec.design_id,
                             candidate['run_id'], replaced['run_id'],
                             int(lineage['seed']), used_ids)
        used_ids.add(_id_key(new_id))
        expected_mapping.append({
            'candidate_run_id': _encode_scalar(candidate['run_id']),
            'selected_run_id': _encode_scalar(new_id),
            'replaced_parent_run_id': _encode_scalar(replaced['run_id']),
        })
    if (lineage['candidate_to_replaced_parent'] != expected_mapping
            or [_decode_scalar(item['selected_run_id']) for item in expected_mapping]
            != selected_ids):
        raise MixtureConstraintError('候选到替换父运行的映射与重算选择不一致')

    current_rows = mixture_rows(current_frame, current_spec)
    current_run_by_id = {_id_key(run.run_id): run for run in current_design.runs}
    expected_current = set(map(_id_key, locked_ids + selected_ids))
    if ({_id_key(item['run_id']) for item in current_rows} != expected_current
            or len(current_rows) != len(expected_current)):
        raise MixtureConstraintError('改善后运行身份与 Locked/Selected 集合不一致')
    parent_by_id = {_id_key(item['run_id']): item for item in parent_rows}
    current_by_id = {_id_key(item['run_id']): item for item in current_rows}
    parent_map = lineage['parent_snapshot']['doe']['column_map']
    current_map = doe_meta['column_map']
    if current_map != parent_map:
        raise MixtureConstraintError('改善前后 DOE 列映射不一致')
    for run_id in locked_ids:
        before = _run_snapshot(parent_frame, parent_by_id[_id_key(run_id)], parent_map)
        after = _run_snapshot(current_frame, current_by_id[_id_key(run_id)], current_map)
        if before != after:
            raise MixtureConstraintError(
                f'Locked 运行与父设计快照不一致：{run_id}；历史响应或实测设定已变化')

    pair_by_parent = {_id_key(_decode_scalar(item['replaced_parent_run_id'])): item
                      for item in expected_mapping}
    candidate_by_id = {_id_key(item['run_id']): item for item in candidate_rows}
    for parent_id, pair in pair_by_parent.items():
        current = current_by_id[_id_key(_decode_scalar(pair['selected_run_id']))]
        candidate = candidate_by_id[_id_key(_decode_scalar(pair['candidate_run_id']))]
        old = parent_by_id[parent_id]
        current_run = current_run_by_id[_id_key(_decode_scalar(pair['selected_run_id']))]
        candidate_run = candidate_run_by_id[
            _id_key(_decode_scalar(pair['candidate_run_id']))]
        old_run = parent_run_by_id[parent_id]
        if (current['row']['标准序'] != old['row']['标准序']
                or current['row']['运行序'] != old['row']['运行序']
                or any(current['settings'][key] != candidate['settings'][key]
                       for key in parent_spec.component_ids + parent_spec.variable_ids)
                or current_run.settings != candidate_run.settings
                or current_run.point_type != candidate_run.point_type
                or current_run.replicate != candidate_run.replicate
                or current_run.block != old_run.block
                or any(getattr(current_run, key) != getattr(candidate_run, key)
                       for key in ('whole_plot_id', 'subplot_id', 'whole_plot_order',
                                   'subplot_order', 'batch_id', 'source_run_id',
                                   'control_run_id', 'noise_condition_id'))):
            raise MixtureConstraintError('新增运行设定或替换位置与谱系不一致')

    parent_matrix = model.matrix([item['settings'] for item in _ordered(
        parent_rows, parent_map['standard_order'])])
    candidate_matrix = model.matrix([item['settings'] for item in candidate_pool])
    current_matrix = model.matrix([item['settings'] for item in _ordered(
        current_rows, current_map['standard_order'])])
    if (lineage['parent_matrix_sha256'] != _matrix_digest(
            model, parent_rows, parent_map['run_id'], parent_map['standard_order'])
            or lineage['candidate_matrix_sha256'] != _matrix_digest(
                model, candidate_pool, parent_map['run_id'], parent_map['standard_order'])
            or lineage['current_matrix_sha256'] != _matrix_digest(
                model, current_rows, current_map['run_id'], current_map['standard_order'])):
        raise MixtureConstraintError('父、候选或当前模型矩阵 SHA-256 不匹配')
    _validate_metrics(lineage, parent_matrix, candidate_matrix,
                      current_matrix, model, search, budget)


def improve_mixture_design(parent_frame, parent_mixture, parent_doe,
                           candidate_frame, candidate_mixture, candidate_doe,
                           locked_run_ids, replaceable_run_ids, candidate_run_ids,
                           *, degree=2, terms=None, seed=0,
                           evaluation_budget=_MAX_EXACT_SUBSETS):
    """在显式候选域内穷举 D-optimal 替换，返回新表及 Schema 2 谱系。"""
    if (isinstance(seed, bool) or not isinstance(seed, Integral)
            or isinstance(evaluation_budget, bool)
            or not isinstance(evaluation_budget, Integral)
            or evaluation_budget < 1 or evaluation_budget > _MAX_EXACT_SUBSETS):
        raise MixtureConstraintError(
            f'seed 必须是整数，评价预算须为 1–{_MAX_EXACT_SUBSETS}')
    locked_ids = _ids(locked_run_ids, 'Locked Run IDs')
    replaceable_ids = _ids(replaceable_run_ids, 'Replaceable Run IDs')
    requested_candidates = _ids(candidate_run_ids, 'Candidate Run IDs')
    parent_spec, parent_rows, parent_design = _v5_source(
        parent_frame, parent_mixture, parent_doe, '父设计')
    candidate_spec, candidate_rows, candidate_design = _v5_source(
        candidate_frame, candidate_mixture, candidate_doe, '候选设计')
    if (_domain_signature(parent_spec) != _domain_signature(candidate_spec)
            or parent_frame.columns.tolist() != candidate_frame.columns.tolist()
            or parent_doe['column_map'] != candidate_doe['column_map']):
        raise MixtureConstraintError('父设计与候选表的混料定义或列映射不一致')
    if len(parent_rows) > MAX_RUNS:
        raise MixtureConstraintError(f'运行总数不能超过 {MAX_RUNS}')

    parent_by_id = {_id_key(item['run_id']): item for item in parent_rows}
    parent_design_by_id = {_id_key(run.run_id): run for run in parent_design.runs}
    if set(map(_id_key, locked_ids)) & set(map(_id_key, replaceable_ids)):
        raise MixtureConstraintError('Locked 与 Replaceable 运行集合不得重叠')
    if set(map(_id_key, locked_ids + replaceable_ids)) != set(parent_by_id):
        raise MixtureConstraintError('每个父运行必须且只能明确标记为 Locked 或 Replaceable')
    parent_order = _ordered(parent_rows, parent_doe['column_map']['standard_order'])
    locked_keys = set(map(_id_key, locked_ids))
    replaceable_keys = set(map(_id_key, replaceable_ids))
    locked_ids = tuple(item['run_id'] for item in parent_order
                       if _id_key(item['run_id']) in locked_keys)
    replaceable_ids = tuple(item['run_id'] for item in parent_order
                            if _id_key(item['run_id']) in replaceable_keys)
    for run_id in replaceable_ids:
        run = parent_design_by_id.get(_id_key(run_id))
        if run is None:
            raise MixtureConstraintError(f'父设计不存在运行 {run_id}')
        if _has_experiment_identity(run):
            raise MixtureConstraintError(f'已执行或有实验身份的运行不可替换：{run_id}')
    candidate_by_id = {_id_key(item['run_id']): item for item in candidate_rows}
    candidate_design_by_id = {_id_key(run.run_id): run for run in candidate_design.runs}
    if any(_id_key(run_id) not in candidate_by_id for run_id in requested_candidates):
        raise MixtureConstraintError('候选选择范围包含不存在的运行 ID')
    candidate_ids = tuple(item['run_id'] for item in _ordered(
        [candidate_by_id[_id_key(value)] for value in requested_candidates],
        candidate_doe['column_map']['standard_order']))
    for run_id in candidate_ids:
        if _has_experiment_identity(candidate_design_by_id[_id_key(run_id)]):
            raise MixtureConstraintError(f'已执行或有实验身份的候选运行不可选择：{run_id}')
    if not candidate_ids:
        raise MixtureConstraintError('至少选择一个 Candidate Run ID')

    model = MixtureTermModel(parent_spec, terms, int(degree))
    replaceable, candidate_pool, chosen, search = _search(
        parent_spec,
        parent_rows, candidate_rows, locked_ids, replaceable_ids,
        candidate_ids, model, int(seed), int(evaluation_budget))
    used_ids = set(parent_by_id)
    output_pairs = []
    for candidate, replaced in zip(chosen, replaceable):
        new_id = _new_run_id(parent_spec.design_id, candidate_spec.design_id,
                             candidate['run_id'], replaced['run_id'], int(seed), used_ids)
        used_ids.add(_id_key(new_id))
        output_pairs.append({
            'candidate_run_id': _encode_scalar(candidate['run_id']),
            'selected_run_id': _encode_scalar(new_id),
            'replaced_parent_run_id': _encode_scalar(replaced['run_id']),
        })
    response_column_map = parent_doe['column_map']
    pair_by_parent = {_id_key(_decode_scalar(item['replaced_parent_run_id'])): item
                      for item in output_pairs}
    output = parent_frame.copy(deep=True).reset_index(drop=True)
    run_id_column = response_column_map['run_id']
    response_columns = tuple(response_column_map['responses'].values())
    for column in (run_id_column, *response_columns):
        output[column] = output[column].astype(object)
    column_index = {name: index for index, name in enumerate(output.columns)}
    for parent_item in parent_rows:
        pair = pair_by_parent.get(_id_key(parent_item['run_id']))
        if pair is None:
            continue
        candidate = candidate_by_id[_id_key(_decode_scalar(pair['candidate_run_id']))]
        old = parent_item['row']
        new_id = _decode_scalar(pair['selected_run_id'])
        for column in output.columns:
            output.iat[parent_item['position'], column_index[column]] = \
                candidate['row'][column]
        output.iat[parent_item['position'], column_index[run_id_column]] = new_id
        for key in ('standard_order', 'run_order', 'replicate', 'block'):
            column = response_column_map.get(key)
            if column is not None:
                output.iat[parent_item['position'], column_index[column]] = old[column]
        for column in response_columns:
            output.iat[parent_item['position'], column_index[column]] = None

    parent_snapshot = _snapshot(parent_frame, parent_doe, parent_mixture)
    candidate_snapshot = _snapshot(candidate_frame, candidate_doe, candidate_mixture)
    parent_response_snapshot = _response_snapshot(parent_frame, parent_spec, parent_rows)
    parent_matrix = model.matrix([item['settings'] for item in _ordered(
        parent_rows, parent_doe['column_map']['standard_order'])])
    candidate_matrix = model.matrix([item['settings'] for item in candidate_pool])
    current_rows = mixture_rows(output, parent_spec)
    current_matrix = model.matrix([item['settings'] for item in _ordered(
        current_rows, parent_doe['column_map']['standard_order'])])
    before = evaluate(parent_matrix.tolist())
    after = evaluate(current_matrix.tolist())
    if after['rank'] != model.width or after['logdet'] is None:
        raise MixtureConstraintError('改善后模型矩阵不满秩')
    if before['logdet'] is not None and after['logdet'] < before['logdet'] - 1e-12:
        raise MixtureConstraintError('候选域无法得到 logdet 不劣于父设计的改善结果')

    identity = _digest({
        'parent': parent_spec.design_id, 'parent_snapshot': _digest(parent_snapshot),
        'candidate': candidate_spec.design_id,
        'candidate_snapshot': _digest(candidate_snapshot),
        'selected': output_pairs, 'terms': list(model.terms),
        'degree': model.degree, 'seed': int(seed),
    })
    design_id = 'mixture-improve-' + identity[:20]
    current_mixture_spec = replace(parent_spec, design_id=design_id)
    current_doe_spec = replace(
        parent_design.spec, design_id=design_id, optimal_lineage=None,
        augmentation_lineage=None)
    current_doe = worksheet_metadata(output, current_doe_spec,
                                     deepcopy(parent_doe['column_map']))
    current_mixture = {
        'schema_version': 2,
        'spec': current_mixture_spec.to_dict(),
        'worksheet': {
            'row_count': len(output),
            'input_fingerprint': input_fingerprint(output, current_mixture_spec),
        },
        'improvement_lineage': {
            'parent_design_id': parent_spec.design_id,
            'parent_snapshot': parent_snapshot,
            'parent_snapshot_sha256': _digest(parent_snapshot),
            'parent_input_fingerprint': parent_mixture['worksheet']['input_fingerprint'],
            'parent_response_snapshot': parent_response_snapshot,
            'parent_response_sha256': _digest(parent_response_snapshot),
            'locked_run_ids': [_encode_scalar(value) for value in locked_ids],
            'replaceable_run_ids': [_encode_scalar(value) for value in replaceable_ids],
            'retained_run_ids': [_encode_scalar(value) for value in locked_ids],
            'candidate_design_id': candidate_spec.design_id,
            'candidate_snapshot': candidate_snapshot,
            'candidate_snapshot_sha256': _digest(candidate_snapshot),
            'candidate_input_fingerprint': candidate_mixture['worksheet']['input_fingerprint'],
            'candidate_run_ids': [_encode_scalar(value) for value in candidate_ids],
            'selected_run_ids': [pair['selected_run_id'] for pair in output_pairs],
            'candidate_to_replaced_parent': output_pairs,
            'criterion': 'd_optimal',
            'model_degree': model.degree,
            'model_terms': list(model.terms),
            'candidate_matrix_sha256': _matrix_digest(
                model, candidate_pool, candidate_doe['column_map']['run_id'],
                candidate_doe['column_map']['standard_order']),
            'parent_matrix_sha256': _matrix_digest(
                model, parent_rows, parent_doe['column_map']['run_id'],
                parent_doe['column_map']['standard_order']),
            'current_matrix_sha256': _matrix_digest(
                model, current_rows, current_doe['column_map']['run_id'],
                current_doe['column_map']['standard_order']),
            'parent_rank': before['rank'], 'parent_logdet': before['logdet'],
            'current_rank': after['rank'], 'current_logdet': after['logdet'],
            'seed': int(seed), 'evaluation_budget': int(evaluation_budget),
            'actual_evaluations': search['evaluations'],
            'stop_reason': 'exhaustive_candidate_subsets',
            'global_optimum_proven': True,
        },
    }
    report = {
        'criterion': 'd_optimal', 'method': 'exact_enumeration',
        'parent_n': len(parent_rows), 'current_n': len(current_rows),
        'replaced_n': len(replaceable), 'candidate_count': len(candidate_pool),
        'selected_candidate_run_ids': tuple(
            _decode_scalar(item['candidate_run_id']) for item in output_pairs),
        'selected_run_ids': tuple(
            _decode_scalar(item['selected_run_id']) for item in output_pairs),
        'candidate_to_replaced_parent': tuple(
            (_decode_scalar(item['candidate_run_id']),
             _decode_scalar(item['selected_run_id']),
             _decode_scalar(item['replaced_parent_run_id']))
            for item in output_pairs),
        'parent_rank': before['rank'], 'parent_logdet': before['logdet'],
        'current_rank': after['rank'], 'current_logdet': after['logdet'],
        'parent_matrix_sha256': current_mixture['improvement_lineage'][
            'parent_matrix_sha256'],
        'current_matrix_sha256': current_mixture['improvement_lineage'][
            'current_matrix_sha256'],
        'candidate_matrix_sha256': current_mixture['improvement_lineage'][
            'candidate_matrix_sha256'],
        'seed': int(seed), 'evaluation_budget': int(evaluation_budget),
        'evaluations': search['evaluations'], 'subsets': search['subsets'],
        'stop_reason': 'exhaustive_candidate_subsets',
        'global_optimum_proven': True,
        'new_run_responses_empty': True,
    }
    model_config = {
        'response': current_mixture_spec.response_names[0],
        'degree': model.degree,
        'terms': list(model.terms),
        'input_fingerprint': current_mixture['worksheet']['input_fingerprint'],
    }
    return output, current_doe, current_mixture, model_config, report
