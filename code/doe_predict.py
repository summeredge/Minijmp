"""通用响应面点预测：与拟合使用同一模型项、同一系数快照。"""
import hashlib
import json
import math

import numpy as np

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


def predict_point(frame, metadata, response, settings, terms=None, blocks=True):
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
    return {
        'response': response, 'prediction': prediction, 'settings': dict(settings),
        'coded': coded, 'block': block, 'terms': analysis['terms'],
        'model': model, 'design': design,
        'snapshot_id': snapshot_id(frame, metadata),
        'condition': analysis['condition'], 'inference': analysis['inference'],
        'note': '点预测来自当前拟合模型，不等于确认试验结果。',
    }
