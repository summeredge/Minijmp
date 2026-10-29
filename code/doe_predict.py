"""通用响应面点预测：与拟合使用同一模型项、同一系数快照。"""
import hashlib
import json
import math

import numpy as np
from scipy import stats

from doe_rsm import analyze_rsm


def snapshot_id(frame, metadata):
    """输入快照摘要：任何响应、设定或映射变化都会改变它。"""
    digest = hashlib.sha256()
    structure = {
        "columns": [(type(column).__name__, repr(column)) for column in frame.columns],
        "dtypes": [str(dtype) for dtype in frame.dtypes],
    }
    digest.update(json.dumps(structure, sort_keys=True, separators=(",", ":")).encode())
    import pandas as pd
    digest.update(pd.util.hash_pandas_object(frame, index=True).to_numpy(
        dtype=np.uint64).tobytes())
    digest.update(json.dumps(metadata, sort_keys=True, separators=(",", ":"),
                             allow_nan=False).encode())
    return digest.hexdigest()[:16]


def _prediction_intervals(analysis, row, confidence, side):
    if (isinstance(confidence, bool) or not isinstance(confidence, (int, float))
            or not math.isfinite(confidence) or not 0 < confidence < 1):
        raise ValueError('置信水平必须是 0 与 1 之间的比例')
    if side not in ('two_sided', 'lower', 'upper'):
        raise ValueError('区间方向必须是 two_sided、lower 或 upper')
    result = {'status': '不可用', 'reason': '', 'confidence': float(confidence),
              'side': side, 'df': analysis['df'], 'se_fit': None,
              'ci_low': None, 'ci_high': None, 'pi_low': None, 'pi_high': None,
              'assumption': '连续响应线性模型；误差独立、同方差且正态。'}
    run_blocks = [run.block for run in analysis['design'].runs]
    block_levels = {block for block in run_blocks if block is not None}
    if (len(block_levels) > 1
            or (block_levels and any(block is None for block in run_blocks))):
        result['reason'] = '设计含区组；本版本未验证区组预测行和方差合同。'
        return result
    df = analysis['df']
    mse = analysis['residual_mse']
    if df <= 0:
        result['reason'] = '残差自由度不为正，无法估计误差方差。'
        return result
    if mse is None or not math.isfinite(mse) or analysis['sse'] <= analysis['mse_floor']:
        result['reason'] = '残差方差为零或数值上不可辨。'
        return result
    matrix = analysis['matrix']
    try:
        solution = np.linalg.lstsq(matrix.T, np.asarray(row, dtype=float), rcond=None)[0]
        h0 = float(solution @ solution)
    except (ValueError, np.linalg.LinAlgError, OverflowError) as error:
        result['reason'] = f'无法稳定计算预测方差：{error}'
        return result
    if not math.isfinite(h0) or h0 < 0:
        result['reason'] = '预测方差因子不是有限非负数。'
        return result
    se_fit = math.sqrt(mse * h0)
    se_prediction = math.sqrt(mse * (1.0 + h0))
    probability = (1 + confidence) / 2 if side == 'two_sided' else confidence
    critical = float(stats.t.ppf(probability, df))
    if not math.isfinite(critical):
        result['reason'] = '无法取得指定置信水平的 t 临界值。'
        return result
    prediction = float(row @ np.asarray(analysis['coefficients'], dtype=float))
    ci_margin, pi_margin = critical * se_fit, critical * se_prediction
    bounds = (prediction - ci_margin, prediction + ci_margin,
              prediction - pi_margin, prediction + pi_margin)
    if not all(math.isfinite(value) for value in bounds):
        result['reason'] = '预测区间超出有限数值范围。'
        return result
    result.update(status='可用', reason='', se_fit=se_fit, h0=h0,
                  critical_value=critical)
    if side == 'two_sided':
        result.update(ci_low=prediction - ci_margin, ci_high=prediction + ci_margin,
                      pi_low=prediction - pi_margin, pi_high=prediction + pi_margin)
    elif side == 'lower':
        result.update(ci_low=prediction - ci_margin, pi_low=prediction - pi_margin)
    else:
        result.update(ci_high=prediction + ci_margin, pi_high=prediction + pi_margin)
    return result


def _outside_observed_ranges(design, settings):
    categorical = [factor for factor in design.spec.factors
                   if factor.factor_type == 'categorical']
    reference = [run for run in design.runs
                 if all(run.settings[factor.factor_id] == settings[factor.factor_id]
                        for factor in categorical)]
    if not reference:
        return True
    for factor in design.spec.factors:
        if factor.factor_type != 'continuous':
            continue
        values = [float(run.settings[factor.factor_id]) for run in reference]
        value = float(settings[factor.factor_id])
        tolerance = np.finfo(float).eps * max(1.0, *(abs(item) for item in values)) * 10
        if value < min(values) - tolerance or value > max(values) + tolerance:
            return True
    return False


def predict_point(frame, metadata, response, settings, terms=None, blocks=True,
                  confidence=None, side='two_sided'):
    """给定实际因子设置，返回预测值与编码值。

    settings 必须覆盖全部因子；分类因子使用其水平标签。区组取模型中
    的第一个区组（参考区组），并在结果中标明。
    """
    design_metadata = metadata.get('design') if isinstance(metadata, dict) else None
    if isinstance(design_metadata, dict) and design_metadata.get('design_type') == 'custom_rsm':
        from doe_custom_analysis import analyze_custom_rsm
        analysis = analyze_custom_rsm(frame, metadata, response, terms=terms,
                                      use_blocks=blocks)
    else:
        analysis = analyze_rsm(frame, metadata, response, terms=terms, use_blocks=blocks)
    model = analysis['term_model']
    design = analysis['design']
    missing = [factor.factor_id for factor in design.spec.factors
               if factor.factor_id not in settings]
    if missing:
        raise ValueError('缺少因子设置：' + '、'.join(missing))
    unknown = set(settings) - {factor.factor_id for factor in design.spec.factors}
    if unknown:
        raise ValueError('存在未知因子：' + '、'.join(sorted(unknown)))
    coded = {}
    for factor in design.spec.factors:
        value = settings[factor.factor_id]
        if factor.factor_type == 'categorical':
            if value not in factor.levels:
                raise ValueError(f'因子 {factor.factor_id} 的水平不在已声明范围内')
            coded[factor.factor_id] = value
        else:
            coded[factor.factor_id] = float(factor.to_coded(value))
    # 模型列按 1 起的区组序号编码，参考区组固定为第 1 组。
    block = analysis['blocks'][0] if analysis['blocks'] else None
    row = model.row(coded, 1 if block is not None else None)
    prediction = float(row @ np.asarray(analysis['coefficients'], dtype=float))
    if not math.isfinite(prediction):
        raise ValueError('预测值超出有限范围')
    extrapolation = _outside_observed_ranges(design, settings)
    result = {
        'response': response, 'prediction': prediction, 'settings': dict(settings),
        'coded': coded, 'block': block, 'terms': analysis['terms'],
        'model': model, 'design': design,
        'snapshot_id': snapshot_id(frame, metadata),
        'condition': analysis['condition'], 'inference': analysis['inference'],
        'extrapolation': extrapolation,
        'extrapolation_note': ('超出至少一个连续因子的单因子观测范围'
                               if extrapolation else
                               '单因子观测范围内；未判定联合设计区域'),
        'note': '点预测来自当前拟合模型，不等于确认试验结果。',
    }
    if confidence is not None:
        result['intervals'] = _prediction_intervals(analysis, row, confidence, side)
    return result
