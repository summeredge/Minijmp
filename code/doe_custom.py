"""把用户已有工作表的实验运行定义为自定义 DOE 设计。

只识别实际矩阵，不重新生成标准设计，也不给任意矩阵套上 CCD/BBD/DSD
身份。分析能力按实际可估计性判断。
"""
from itertools import product
from fractions import Fraction
import hashlib
import json

import numpy as np
import pandas as pd

from doe_core import DesignSpec, FactorSpec, restore_design_result, worksheet_metadata
from doe_rsm_model import TermModel


CUSTOM_TYPES = frozenset({'custom_factorial', 'custom_rsm', 'custom_screening'})


def _factor_specs(factors):
    """复制为自定义设计因子；文本/数值分类标签保持原类型。"""
    result = []
    for factor in factors:
        if factor.factor_type == 'continuous':
            result.append(FactorSpec(factor.factor_id, factor.name, factor.low,
                                     factor.high, factor.unit))
        else:
            result.append(FactorSpec(
                factor.factor_id, factor.name, None, None, factor.unit,
                factor_type='categorical', levels=tuple(factor.levels),
                level_type=('text' if all(isinstance(level, str)
                                          for level in factor.levels) else 'numeric')))
    return tuple(result)


def coded_value(factor, value, point_type=None):
    """连续因子编码；轴点允许位于声明 low/high 之外（与 CCD 一致）。"""
    if point_type != 'axial':
        return float(factor.to_coded(value))
    low, high = Fraction(factor.low), Fraction(factor.high)
    return float(2 * (Fraction(value) - low) / (high - low) - 1)


def design_matrix(design, terms=None):
    """按实际运行重建模型矩阵；自定义 RSM 使用显式模型项。"""
    spec = design.spec
    model = TermModel(spec.factors, terms or spec.model_terms or None,
                      blocks=1 if spec.block_count else 0)
    blocks = [run.block for run in design.runs]
    if spec.block_count and None in blocks:
        raise ValueError('区组列存在缺失值')
    settings = []
    for run in design.runs:
        row = {}
        for factor in spec.factors:
            value = run.settings[factor.factor_id]
            row[factor.factor_id] = (value if factor.factor_type == 'categorical'
                                     else coded_value(factor, value, run.point_type))
        settings.append(row)
    block_index = ({value: position + 1 for position, value in
                    enumerate(sorted(set(blocks)))} if spec.block_count else None)
    return model.matrix(settings, [block_index[block] if block_index else None
                                   for block in blocks]), model


def matrix_summary(matrix):
    singular = np.linalg.svd(matrix, compute_uv=False)
    rank = int(np.linalg.matrix_rank(matrix))
    return {'n': int(matrix.shape[0]), 'p': int(matrix.shape[1]), 'rank': rank,
            'condition': (float(singular[0] / singular[-1]) if len(singular)
                          and singular[-1] > 0 else None),
            'estimable': rank == matrix.shape[1]}


def matrix_sha256(design):
    """模型矩阵身份：按标准序记录编码设定与模型项。

    使用编码值而非原始数值，使 1 与 1.0 的存储差异不影响身份。
    """
    spec = design.spec
    rows = [{'run_id': run.run_id, 'standard_order': run.standard_order,
             'settings': {factor.factor_id: (
                 run.settings[factor.factor_id]
                 if factor.factor_type == 'categorical'
                 else coded_value(factor, run.settings[factor.factor_id],
                                  run.point_type))
                 for factor in spec.factors}}
            for run in sorted(design.runs, key=lambda item: item.standard_order)]
    payload = {'design_type': spec.design_type,
               'terms': list(spec.model_terms), 'rows': rows}
    encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False,
                         sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def define_custom(frame, *, design_type, factors, responses, column_map,
                  design_id=None, seed=None, model_terms=(), block_count=None,
                  require_estimable=True):
    """定义自定义设计并返回 (DataFrame, 元数据)；失败不修改来源。"""
    if design_type not in CUSTOM_TYPES:
        raise ValueError('未知自定义设计类型')
    if not isinstance(frame, pd.DataFrame):
        raise ValueError('数据源必须是 pandas DataFrame')
    factors = tuple(factors)
    if not factors or any(not isinstance(factor, FactorSpec) for factor in factors):
        raise ValueError('自定义设计必须包含因子定义')
    responses = tuple(responses)
    if not responses or any(not isinstance(name, str) or not name for name in responses):
        raise ValueError('自定义设计至少需要一个响应名称')
    frame = frame.copy(deep=True).reset_index(drop=True)
    column_map = dict(column_map)
    # 自定义设计没有批次/来源列时按默认规则补列，供后续增补保留谱系。
    for key, base, default in (('batch_id', 'DOE 批次', 'BASE'),
                               ('source_run_id', 'DOE 源运行ID', None)):
        if column_map.get(key) is not None:
            continue
        name = base
        index = 2
        while name in frame.columns:
            name = f'{base} ({index})'
            index += 1
        frame[name] = default
        column_map[key] = name
    spec = DesignSpec(
        design_id or f'custom-{design_type.split("_", 1)[1]}',
        _factor_specs(factors), responses, seed=seed, design_type=design_type,
        schema_version=5, model_terms=tuple(model_terms), block_count=block_count,
        randomization_unit='block' if block_count else 'run')
    metadata = worksheet_metadata(frame, spec, column_map)
    result = restore_design_result(frame, metadata)
    summary = validate_custom(result, require_estimable=require_estimable)
    return frame.copy(deep=True), metadata, summary


def validate_custom(result, *, require_estimable=True):
    """按实际点集核验自定义设计身份；不重新计算摘要掩盖篡改。"""
    spec = result.spec
    kind = spec.design_type
    if kind not in CUSTOM_TYPES:
        raise ValueError('设计类型不是受支持的自定义设计')
    if kind == 'custom_factorial':
        return _validate_factorial(result)
    if kind == 'custom_rsm':
        return _validate_rsm(result, require_estimable)
    return _validate_screening(result)


def _validate_factorial(result):
    spec, runs = result.spec, result.runs
    if any(factor.factor_type == 'categorical' and len(factor.levels) != 2
           for factor in spec.factors):
        raise ValueError('自定义两水平因子设计只接受两水平因子')
    if spec.model_terms:
        raise ValueError('自定义因子设计不接受响应面模型项')
    if any(run.point_type not in ('factorial', 'center') for run in runs):
        raise ValueError('自定义因子设计只接受因子点或中心点')
    factorial, centers = [], []
    # 独立重复是合法设计：同一因子点可在不同重复编号下出现一次。
    seen = set()
    for run in runs:
        coded = []
        for factor in spec.factors:
            value = run.settings[factor.factor_id]
            if factor.factor_type == 'categorical':
                coded.append(-1 if value == factor.levels[0] else 1)
            else:
                number = float(factor.to_coded(value))
                if number not in (-1.0, 0.0, 1.0):
                    raise ValueError('自定义因子设计只接受低、中、高水平')
                coded.append(int(number))
        point = tuple(coded)
        if run.point_type == 'center':
            centers.append(point)
            continue
        key = (run.replicate, point)
        if key in seen:
            raise ValueError('因子点重复；独立重复应使用不同重复编号')
        seen.add(key)
        factorial.append(point)
    if any(any(value not in (-1, 1) for value in point) for point in factorial):
        raise ValueError('因子点必须恰为低或高水平')
    if any(any(value != 0 for value in point) for point in centers):
        raise ValueError('中心点必须位于所有因子的中点')
    unique = set(factorial)
    complete = unique == set(product((-1, 1), repeat=len(spec.factors)))
    matrix = np.asarray([[1] + list(point) for point in sorted(unique)], dtype=float)
    summary = matrix_summary(matrix)
    return {'design_type': spec.design_type, 'n': len(runs),
            'factor_count': len(spec.factors), 'unique_points': len(unique),
            'complete_factorial': complete, 'center_rows': len(centers),
            'replicates': len(runs) - len(unique), 'rank': summary['rank'],
            'p': len(spec.factors) + 1,
            'estimable': summary['rank'] == len(spec.factors) + 1,
            'condition': summary['condition'], 'regular_fraction': False,
            'analysis': ('完整两水平全因子' if complete else '自定义非完整因子矩阵')}


def _validate_rsm(result, require_estimable=True):
    spec, runs = result.spec, result.runs
    if not spec.model_terms:
        raise ValueError('自定义响应面设计必须显式声明模型项')
    continuous = [factor for factor in spec.factors
                  if factor.factor_type == 'continuous']
    if not 2 <= len(continuous) <= 10:
        raise ValueError('自定义响应面设计需要 2–10 个连续因子')
    for run in runs:
        for factor in continuous:
            value = run.settings[factor.factor_id]
            coded = coded_value(factor, value, run.point_type)
            if run.point_type != 'axial' and not -1 <= coded <= 1:
                raise ValueError(f'因子 {factor.factor_id} 水平超出设计范围')
    matrix, model = design_matrix(result)
    summary = matrix_summary(matrix)
    if not summary['estimable'] and require_estimable:
        raise ValueError('所选模型项在设计矩阵上不可估计（秩亏）')
    return {'design_type': spec.design_type, 'n': len(runs),
            'factor_count': len(spec.factors), 'terms': model.terms,
            'rank': summary['rank'], 'p': summary['p'],
            'estimable': summary['estimable'],
            'condition': summary['condition'],
            'analysis': '自定义响应面模型（按实际矩阵）'}


def screening_properties(matrix):
    """DSD 必要构造性质：主效应正交、主效应×二因子交互正交、存在 0 水平。"""
    matrix = np.asarray(matrix, dtype=float)
    columns = [matrix[:, index] for index in range(matrix.shape[1])]
    main = np.column_stack(columns)
    gram = main.T @ main
    off = gram - np.diag(np.diag(gram))
    interactions = [columns[first] * columns[second]
                    for first in range(len(columns))
                    for second in range(first + 1, len(columns))]
    cross = (float(np.max(np.abs(main.T @ np.column_stack(interactions))))
             if interactions else 0.0)
    return {'main_orthogonal': bool(np.max(np.abs(off)) <= 1e-9),
            'main_two_factor_orthogonal': cross <= 1e-9,
            'has_zeros': bool(any(np.any(column == 0) for column in columns)),
            'main_sums_of_squares': [float(value) for value in np.diag(gram)]}


def _validate_screening(result):
    spec, runs = result.spec, result.runs
    if any(factor.factor_type == 'categorical' and len(factor.levels) != 2
           for factor in spec.factors):
        raise ValueError('自定义筛选设计只接受两水平分类因子')
    if not 2 <= len(spec.factors) <= 48:
        raise ValueError('自定义筛选设计需要 2–48 个因子')
    if len(runs) > 10000:
        raise ValueError('运行总数不能超过 10000')
    coded = []
    for run in runs:
        row = []
        for factor in spec.factors:
            value = run.settings[factor.factor_id]
            if factor.factor_type == 'categorical':
                row.append(-1 if value == factor.levels[0] else 1)
            else:
                number = float(factor.to_coded(value))
                if number not in (-1.0, 0.0, 1.0):
                    raise ValueError('连续筛选因子只接受低、中、高水平')
                row.append(int(number))
        coded.append(row)
    matrix = np.asarray(coded, dtype=float)
    if len(set(map(tuple, matrix.tolist()))) != len(matrix):
        raise ValueError('筛选设计不得包含重复设计点；独立重复应使用不同重复编号')
    properties = screening_properties(matrix)
    if not properties['main_two_factor_orthogonal']:
        raise ValueError('主效应与二因子交互不正交，不能定义为 DSD')
    if not properties['has_zeros']:
        raise ValueError('矩阵没有三水平（含 0）连续因子点，不是 DSD 构造')
    return {'design_type': spec.design_type, 'n': len(runs),
            'factor_count': len(spec.factors), **properties,
            'continuous_factors': sum(factor.factor_type == 'continuous'
                                      for factor in spec.factors),
            'categorical_factors': sum(factor.factor_type == 'categorical'
                                       for factor in spec.factors),
            'analysis': '自定义筛选矩阵（按实际点集核验）'}
