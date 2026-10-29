"""跨设计诊断字段语义：统一含义，不强制统一统计模型。"""
import numpy as np


_NOT_APPLICABLE = '不适用'


def _row(label, value, note=''):
    return {'item': label, 'value': value, 'note': note}


def _finite(value):
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if np.isfinite(number) else None


def contract(result, design_type):
    """从各分析器结果提取统一诊断字段；缺失项明确标注不适用原因。"""
    rows = []
    n = result.get('n')
    p = result.get('p')
    rank = result.get('rank', p)
    df = result.get('df')
    rows.append(_row('运行数 n', n))
    rows.append(_row('参数数 p', p, '模型矩阵列数' if p is not None else '该分析器不构造列矩阵'))
    rows.append(_row('矩阵秩', rank,
                     '按当前模型实际矩阵' if rank is not None else '该分析器不报告矩阵秩'))
    rows.append(_row('残差自由度', df))
    for label, key in (('SSE', 'sse'), ('SST', 'sst')):
        rows.append(_row(label, _finite(result.get(key))))
    pure_df = result.get('pure_error_df')
    pure_sse = result.get('pure_error_sse')
    rows.append(_row('纯误差自由度', pure_df,
                     '相同设定独立重复' if pure_df else '无独立重复或该设计不提供'))
    rows.append(_row('纯误差平方和', _finite(pure_sse)))
    rows.append(_row('失拟自由度', result.get('lack_of_fit_df')))
    rows.append(_row('失拟平方和', _finite(result.get('lack_of_fit_sse'))))
    lack_of_fit = result.get('lack_of_fit')
    rows.append(_row('失拟 F / p',
                     None if not lack_of_fit else
                     f"{lack_of_fit['f']:.6g} / {lack_of_fit['p']:.6g}",
                     '已计算' if lack_of_fit else '纯误差或失拟自由度不足，不提供'))
    curvature = result.get('curvature')
    rows.append(_row('中心点曲率',
                     None if not curvature else f"差值 {curvature['difference']:.6g}",
                     '含 F/p' if curvature and curvature.get('f') is not None
                     else '仅差值或不可用'))
    inference = result.get('inference')
    has_f = bool(inference) and 'f' in inference
    rows.append(_row('模型 F / p',
                     f"{inference['f']:.6g} / {inference['model_p']:.6g}" if has_f
                     else None,
                     '已计算' if has_f else
                     '该分析器不提供模型 F 检验' if inference else '误差自由度或方差不足'))
    condition = result.get('condition')
    rows.append(_row('条件数', _finite(condition),
                     '>1e10 视为病态' if condition is not None else '该分析器不计算'))
    rows.append(_row('模型可估计性',
                     '满列秩' if p is not None and rank == p else
                     '秩亏，仅部分项可估计' if p is not None else '不适用',
                     '按所选模型矩阵'))
    aliases = result.get('alias_groups')
    rows.append(_row('别名/混杂关系',
                     len(aliases) if aliases is not None else None,
                     '别名组数' if aliases is not None
                     else '该设计族不使用正规分数别名假设'))
    point_diagnostics = result.get('diagnostics')
    if point_diagnostics is None:
        rows.append(_row('杠杆值', None, '当前分析器不输出逐点杠杆'))
    else:
        available = sum(row['leverage'] is not None for row in point_diagnostics)
        influence = sum(row['cooks_distance'] is not None
                        or row['dfits'] is not None for row in point_diagnostics)
        rows.append(_row('杠杆值', f'{available}/{len(point_diagnostics)}',
                         '按本次拟合实际模型矩阵的投影对角线计算'))
        rows.append(_row('逐点影响量', f'{influence}/{len(point_diagnostics)}',
                         "标准化/删除残差、Cook's D 与 DFITS；不可用行在逐点表中说明原因"))
    rows.append(_row('假设检验',
                     '未自动检验',
                     '残差图只辅助诊断，不证明独立、同方差或正态'))
    return {'design_type': design_type, 'status': result.get('status', ''),
            'assumption': result.get('assumption', ''), 'rows': rows}
