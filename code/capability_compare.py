"""改善前后过程能力对比：阶段划分与单阶段能力复用现有实现。

单阶段能力仍由 capability.analyze_capability 计算；本模块只负责阶段划分、
对比结果、稳定性/分布适用性诊断与统一报告，不重新实现能力公式。
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd

from capability import analyze_capability
from capability_plots import _charts
from control_chart import _panel_events
from improvement_chart import (SPLITS, _differences, _display, _print_frame,
                               split_phases)


ALPHA = .05
DISTRIBUTIONS = {'normal': '正态', 'weibull': 'Weibull', 'lognormal': 'Lognormal',
                 'gamma': 'Gamma'}
NORMAL_INDICES = ('Cp', 'Cpl', 'Cpu', 'Cpk', 'Pp', 'Ppl', 'Ppu', 'Ppk')
NONNORMAL_INDICES = ('Pp', 'Ppl', 'Ppu', 'Ppk')


def _columns(names):
    return ['指标', names[0], names[1], '差值', '变化率（%）', '波动比', '说明']


@dataclass
class CapabilityComparison:
    tables: dict
    notes: list
    plot: dict


def _finite(value):
    return (isinstance(value, (int, float, np.integer, np.floating))
            and not isinstance(value, bool) and np.isfinite(value))


def _row(label, before, after, note='', change=True, ratio=False):
    """只有两侧都可计算时才给差值与变化；不可计算一律“不适用”，不写 0。"""
    if not (_finite(before) and _finite(after)):
        return [label, before if _finite(before) else '不适用',
                after if _finite(after) else '不适用', '不适用', '不适用', '不适用', note]
    return [label, before, after, after - before,
            (after / before - 1) * 100 if change and before else ('不适用' if change else ''),
            after / before if ratio and before else ('不适用' if ratio else ''), note]


def _at(value, index):
    if isinstance(value, (list, tuple, np.ndarray)):
        return value[index] if index < len(value) else np.nan
    return value


def _special_causes(stage):
    """正态主图跑 Nelson；非正态主图只判拟合分位限越界；极差类图始终只判越限。

    非正态 I 图上下限来自拟合分布的 0.135%/99.865% 分位，两侧距离不对称，
    不能把 (UCL-CL)/3 当公共尺度去套 Nelson 连续点规则。
    """
    chart, first, second = _charts(
        stage, [np.asarray(group, dtype=float) for group in stage['groups']])
    primary, secondary = first.split()[0], second.split()[0]
    normal_primary = stage['model'].dist.name == 'norm'
    rules = normal_primary
    center, upper = chart['bar1'], chart['ucl1']
    scales = [(_at(upper, i) - _at(center, i)) / 3 for i in range(len(chart['Y1']))]
    events = _panel_events(chart['Y1'], center, chart['lcl1'], upper, None,
                           scales if rules else None, use_rules=rules, panel=primary)
    events += _panel_events(chart['Y2'], chart['bar2'], chart['lcl2'], chart['ucl2'],
                            None, None, use_rules=False, panel=secondary)
    return {'primary': primary, 'secondary': secondary, 'rules': rules,
            'alarms': len({event['point'] for event in events if event['panel'] == primary}),
            'beyond': len({event['point'] for event in events
                           if event['panel'] == secondary}),
            'points': len(chart['Y1'])}


def _stage_ids(subgroup_ids, mask, index):
    if subgroup_ids is None:
        return None
    if isinstance(subgroup_ids, pd.Series):
        return subgroup_ids[mask]
    return pd.Series(np.asarray(subgroup_ids)[mask], index=index)


def _observed(stage):
    row = stage['tables']['PPM'].iloc[0]
    return int(row['合计实测计数']), float(row['合计超规率'])


def _spec_text(lsl, usl, target, k):
    values = '；'.join('%s=%s' % (label, 'NA' if value is None else '%.6g' % value)
                      for label, value in (('LSL', lsl), ('USL', usl), ('Target', target)))
    return values + '；K=%g（两阶段共用）' % k


def analyze_capability_comparison(df, measurement, split='stage', stage=None,
                                  time=None, cutoff=None, lsl=None, usl=None,
                                  target=None, subgroup_size=1, subgroup_ids=None,
                                  distribution='normal', confidence=.95, k=6,
                                  missing='error'):
    """返回两阶段能力对比表、诊断与报告；规格与 K 共用，阶段内独立估计。"""
    if not isinstance(df, pd.DataFrame) or not df.columns.is_unique:
        raise ValueError('输入须为列名唯一的工作表。')
    if measurement not in df:
        raise ValueError('工作表缺少测量列：' + str(measurement))
    if subgroup_ids is not None and len(subgroup_ids) != len(df):
        raise ValueError('子组 ID 长度须与工作表一致。')
    if lsl is None and usl is None:
        raise ValueError('改善前后能力对比至少需要一侧规格；本模式不做纯变换诊断。')
    before, after, names, split_info = split_phases(df, split, stage, time, cutoff)
    positions = [np.flatnonzero(before), np.flatnonzero(after)]
    if subgroup_ids is not None:
        labels = (subgroup_ids if isinstance(subgroup_ids, pd.Series)
                  else pd.Series(np.asarray(subgroup_ids), index=df.index))
        labels = labels.reindex(df.index)
        if labels[before].isin(labels[after]).any():
            raise ValueError('子组标识跨越阶段边界；子组不得跨阶段。')
    stages = []
    for mask, rows in zip((before, after), positions):
        data = df.loc[mask, measurement]
        result = analyze_capability(
            data, lsl=lsl, usl=usl, target=target, subgroup_size=subgroup_size,
            subgroup_ids=_stage_ids(subgroup_ids, mask, data.index),
            distribution=distribution, confidence=confidence, k=k, missing=missing)
        # 来源行号回到整张工作表位置，阶段内下标不外泄。
        rows_out = rows[result['source_row'] - 1] + 1
        result['source_row'] = rows_out
        result['tables']['来源观测']['source_row'] = rows_out
        stages.append(result)
    specials = [_special_causes(stage) for stage in stages]
    observed = [_observed(stage) for stage in stages]
    dropped = [len(rows) - len(stage['data']) for rows, stage in zip(positions, stages)]
    test_rows, test_notes = _differences(stages[0]['data'], stages[1]['data'], ALPHA)
    # 检验与自相关行的阶段名跟随实际阶段标签。
    tests = [[row[0].replace('改善前', names[0], 1).replace('改善后', names[1], 1)]
             + row[1:] for row in test_rows]
    columns = _columns(names)

    summary = pd.DataFrame([
        ['测量列', measurement],
        ['阶段划分', SPLITS[split]],
        ['阶段定义', split_info],
        ['规格', _spec_text(lsl, usl, target, k)],
        ['分布族', DISTRIBUTIONS[distribution] + '（各阶段独立估计参数）'],
        ['分析尺度', '原始测量尺度；不对两阶段分别变换'],
        ['阶段样本量', '%s=%d；%s=%d' % (names[0], len(stages[0]['data']),
                                         names[1], len(stages[1]['data']))],
        ['阶段来源行', '%s：%d → %d；%s：%d → %d' % (
            names[0], positions[0][0] + 1, positions[0][-1] + 1,
            names[1], positions[1][0] + 1, positions[1][-1] + 1)],
        ['删除缺失观测', '；'.join('%s=%d' % (name, gap)
                                   for name, gap in zip(names, dropped))],
        ['子组', '按阶段内子组标识划分，子组不跨阶段' if subgroup_ids is not None
         else '连续子组大小 %s，在每阶段内部重新分组，不跨阶段' % subgroup_size],
    ], columns=['项目', '内容'])

    def note_for(key):
        reasons = []
        nonnormal = stages[0]['model'].dist.name != 'norm'
        for stage_ in stages:
            if stage_['indices'].get(key) is not None:
                continue
            if nonnormal and key.startswith('C'):
                reason = '非正态百分位法不定义 ' + key
            elif stage_['lsl'] is None or stage_['usl'] is None:
                reason = '需双侧规格'
            else:
                reason = '本阶段不可计算'
            reasons.append(reason)
        return '；'.join(dict.fromkeys(reasons))

    index_rows = [_row(key, stages[0]['indices'].get(key), stages[1]['indices'].get(key),
                       note_for(key))
                  for key in (NONNORMAL_INDICES if distribution != 'normal'
                              else NORMAL_INDICES)]
    for key, label in (('Z_lower', '等价 Z（下侧）'), ('Z_upper', '等价 Z（上侧）'),
                       ('Z_bench', '等价 Z（基准）')):
        values = [stage_['z'].get(key) for stage_ in stages]
        note = '规格触及分布支持域或数值尾域，无限 Z 不解释为有限能力保证' if any(
            value is not None and not np.isfinite(value) for value in values) else ''
        index_rows.append(_row(label, *[np.nan if value is None else value
                                        for value in values], note=note, change=False))
    indices = pd.DataFrame(index_rows, columns=columns)

    spread_rows = [
        _row('均值', stages[0]['mean'], stages[1]['mean']),
        _row('组内标准差', stages[0]['within_sigma'], stages[1]['within_sigma'], ratio=True),
        _row('整体标准差', stages[0]['overall_sigma'], stages[1]['overall_sigma'], ratio=True),
        _row('实测超规数', observed[0][0], observed[1][0],
             '严格低于 LSL 或高于 USL 的观测数', change=False),
        _row('实测超规率（%）', observed[0][1] * 100, observed[1][1] * 100,
             '按各阶段有效观测计数；差值为百分点', change=False),
        _row('预计 PPM（整体）', stages[0]['ppm']['overall']['total'],
             stages[1]['ppm']['overall']['total'], '拟合分布预测，不是实测'),
    ]
    within_ppm = [stage_['ppm'].get('within', {}).get('total') for stage_ in stages]
    if all(value is not None for value in within_ppm):
        spread_rows.append(_row('预计 PPM（组内）', *within_ppm,
                                '仅正态且未变换时定义'))
    spread = pd.DataFrame(spread_rows, columns=columns)

    diagnostics = []
    for name, stage_, special, gap in zip(names, stages, specials, dropped):
        weak = special['alarms'] or special['beyond']
        method = ('%s（Nelson 规则）；%s（越限）' % (special['primary'], special['secondary'])
                  if special['rules'] else
                  '%s（仅越限，未执行 Nelson 连续模式）；%s（越限）' % (
                      special['primary'], special['secondary']))
        diagnostics.append([
            name, '过程稳定性', method,
            '异常 %d 点 / %d 点；超限 %d 点' % (special['alarms'], special['points'],
                                               special['beyond']),
            '存在特殊原因' if weak else '未发现特殊原因',
            '仅描述本阶段样本期；能力指数不宜直接预测未来稳定运行' if weak
            else '未命中不等于证明稳定；%s' % (
                '控制限与规格限用途不同'
                if special['rules'] else '非正态连续点判异尚未实现，稳定性仅按越限描述')])
        fit = stage_['fit']
        detail = 'AD=%.4g' % fit['AD']
        if fit.get('KS') is not None:
            detail += '；KS=%.4g' % fit['KS']
        if fit.get('p_value') is not None:
            detail += '；p=%.3g' % fit['p_value']
        diagnostics.append([
            name, '分布适用性', DISTRIBUTIONS[fit['distribution']], detail,
            '拟合失配（5%）' if fit['mismatch'] else '未拒绝指定分布',
            fit['method'] + ('；保留描述性指标，预计 PPM 不可靠' if fit['mismatch'] else '')])
        count = len(stage_['data'])
        diagnostics.append([
            name, '数据充分性', '有效 n=%d；子组数=%d' % (count, len(stage_['groups'])),
            '缺失行 %d' % gap,
            'n<30：尾部 PPM 与拟合不可靠' if count < 30 else '样本量未见明显不足',
            '未评价检验功效；分位外推仍受拟合影响'])
    diagnostics = pd.DataFrame(diagnostics, columns=['阶段', '检查项', '对象', '结果',
                                                     '判定', '说明'])

    unstable = [name for name, special in zip(names, specials)
                if special['alarms'] or special['beyond']]
    mismatch = [name for name, stage_ in zip(names, stages) if stage_['fit']['mismatch']]
    autocorrelated = [row[0].removesuffix('自相关') for row in tests
                      if row[0].endswith('自相关') and row[4] == '存在明显自相关']
    unevaluated = [row[0].removesuffix('自相关') for row in tests
                   if row[0].endswith('自相关') and str(row[4]).startswith('样本不足')]
    small = [name for name, stage_ in zip(names, stages) if len(stage_['data']) < 30]

    conclusions = []
    for key in ('Cpk', 'Ppk'):
        left, right = stages[0]['indices'].get(key), stages[1]['indices'].get(key)
        if _finite(left) and _finite(right):
            conclusions.append(['能力指数 ' + key, '%.6g → %.6g（差值 %+.4g）'
                                % (left, right, right - left)])
        else:
            conclusions.append(['能力指数 ' + key,
                                '不适用：' + (note_for(key) or '不可计算')])
    conclusions.append(['规格外比例', '实测 %.4g%% → %.4g%%；预计 PPM（整体）%.4g → %.4g'
                        % (observed[0][1] * 100, observed[1][1] * 100,
                           stages[0]['ppm']['overall']['total'],
                           stages[1]['ppm']['overall']['total'])])
    limits = ['%s（%s）' % (text, '、'.join(group)) for text, group in (
        ('存在特殊原因', unstable), ('分布拟合失配', mismatch),
        ('明显自相关', autocorrelated), ('自相关无法评价', unevaluated),
        ('样本量 n<30', small)) if group]
    conclusions.append(['解释限制', '；'.join(limits) if limits
                        else '各阶段未发现特殊原因，指定分布未被拒绝'])
    conclusions.append(['统计评价范围',
                        '仅 Welch 均值差异、Levene 波动差异与 Ljung-Box；'
                        'Cpk/Ppk 差值无置信区间或检验'])
    conclusions.append(['改善结论', '仅描述样本期能力变化，不输出显著改善结论'
                        if limits else '可描述样本期能力变化；未评价能力指数差值的显著性'])

    notes = [
        split_info,
        '两阶段共用同一组 LSL/USL/Target 与能力总宽 K，在原始测量尺度比较；不对两阶段分别变换。',
        '各阶段独立估计分布参数与能力指数；子组在阶段内独立划分，不跨阶段。',
        '实测超规率按原始观测计数，预计 PPM 按各阶段拟合分布计算，两者不是同一口径。',
        '能力指数差值仅为描述性比较；未提供差值区间或检验，不以置信区间重叠判定改善。',
        '显著性水平 %.2g 仅用于 Welch 均值差异、Levene 波动差异与 Ljung-Box 自相关。' % ALPHA,
        '能力改善不等同于证明特定工艺措施具有因果效果。',
    ]
    for name, stage_ in zip(names, stages):
        notes += ['%s：%s' % (name, note) for note in stage_['warnings']]
    notes += test_notes
    if unstable:
        notes.append('%s存在特殊原因：能力指数描述样本期表现，不宜直接用于预测未来稳定运行。'
                     % '、'.join(unstable))

    tables = {'数据与规格摘要': summary, '能力指数对比': indices,
              '波动与超规对比': spread, '稳定性与分布诊断': diagnostics,
              '统计检验': pd.DataFrame(tests, columns=['项目', '方法', '统计量',
                                                       'p 值', '结论']),
              '分析结论': pd.DataFrame(conclusions, columns=['项目', '结论'])}
    return CapabilityComparison(tables, notes, {
        'names': names, 'results': stages, 'diagnostics': specials,
        'split_info': split_info})


def print_report(result, print_port):
    """统一报告；表格与图形共用同一份后端结果。"""
    print_port('\n---- 改善前后过程能力分析报告 ----')
    print_port('\nA. 数据与规格摘要')
    for row in result.tables['数据与规格摘要'].itertuples(index=False):
        print_port('%s：%s' % (row[0], _display(row[1])))
    print_port('\nB. 过程稳定性与分布适用性')
    _print_frame(print_port, '稳定性与分布诊断', result.tables['稳定性与分布诊断'])
    print_port('\nC. 能力指数前后比较')
    _print_frame(print_port, '能力指数对比', result.tables['能力指数对比'])
    print_port('\nD. 整体与组内波动变化、E. 超规率与预计 PPM')
    _print_frame(print_port, '波动与超规对比', result.tables['波动与超规对比'])
    print_port('整体标准差描述全部观测，组内标准差来自合并子组；两者口径不同。')
    print_port('\nF. 统计检验与自相关')
    _print_frame(print_port, '统计检验', result.tables['统计检验'])
    print_port('\nG. 分析结论与适用边界')
    _print_frame(print_port, '分析结论', result.tables['分析结论'])
    for note in result.notes:
        print_port(note)
    print_port('能力改善不等同于证明特定工艺措施具有因果效果；结论应结合工艺背景与采样方式。')

