"""改善前后控制图：阶段划分、控制限比较、效果量化与适用性检验。

复用 control_chart 的 I-MR / Xbar-R / Xbar-S 计算和 advanced_spc 的
Nelson 判异；不修改来源数据，不补值、不插值，子组不跨阶段。
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats

from control_chart import _panel_events, xBar_R, xBar_S, x_mR
from chart_style import font_families, style_axes
from ctrl_chart_const import df as CONSTANTS
from stat_table import StatTable
from utilities import c4_values


CHARTS = {'I-MR': 'I-MR', 'Xbar-R': 'Xbar-R', 'Xbar-S': 'Xbar-S'}
LIMIT_MODES = {'independent': '各阶段独立控制限', 'baseline': '改善前固定基线'}
SPLITS = {'stage': '阶段列', 'time': '时间分界点'}
LIMIT_VARIES = '逐子组变化'


@dataclass
class ImprovementResult:
    tables: dict
    notes: list
    plot: dict


def _number(value, name, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float, np.number)):
        raise ValueError(name + '须为有限实数。')
    value = float(value)
    if not np.isfinite(value) or (positive and value <= 0):
        raise ValueError(name + ('须为正的有限实数。' if positive else '须为有限实数。'))
    return value


def _values(df, column):
    if column not in df:
        raise ValueError('工作表缺少观测值列：' + str(column))
    series = df[column]
    if (not pd.api.types.is_numeric_dtype(series) or pd.api.types.is_bool_dtype(series)
            or pd.api.types.is_complex_dtype(series)):
        raise ValueError('观测值须为实数数值列。')
    values = series.to_numpy(dtype=float, na_value=np.nan)
    if np.isinf(values).any():
        raise ValueError('观测值包含无穷大；请先处理。')
    return values


def split_phases(df, split='stage', stage=None, time=None, cutoff=None):
    """返回 (改善前掩码, 改善后掩码, 阶段名, 阶段起止说明)。

    阶段列按实际出现顺序识别，不按标签排序；只接受恰好两个连续阶段。
    """
    if split not in SPLITS:
        raise ValueError('阶段划分方式须为阶段列或时间分界点。')
    if split == 'stage':
        if stage not in df:
            raise ValueError('请选择阶段标识列。')
        raw = df[stage].to_numpy()
        if pd.isna(raw).any():
            raise ValueError('阶段标识存在缺失值；每行须属于一个阶段。')
        try:
            cuts = np.flatnonzero(raw[1:] != raw[:-1]) + 1
        except TypeError as exc:
            raise ValueError('阶段标识须为可比较的标量。') from exc
        blocks = np.split(np.arange(len(df)), cuts)
        names = [str(raw[block[0]]) for block in blocks]
        if len(names) != 2:
            raise ValueError('阶段列须按顺序恰好形成两个连续阶段；当前出现 %d 段（%s）。'
                             % (len(names), '、'.join(names)))
        before = np.zeros(len(df), dtype=bool)
        before[blocks[0]] = True
        return (before, ~before, names, '阶段列“%s”，按实际出现顺序：%s → %s' % (
            stage, names[0], names[1]))
    if time not in df:
        raise ValueError('请选择时间列。')
    raw = df[time]
    if raw.isna().any():
        raise ValueError('时间列存在缺失值。')
    if pd.api.types.is_numeric_dtype(raw) and not pd.api.types.is_bool_dtype(raw):
        stamps = raw.to_numpy(dtype=float)
        if not np.isfinite(stamps).all():
            raise ValueError('时间列包含非有限数值。')
        try:
            boundary = float(str(cutoff).strip())
        except (TypeError, ValueError) as exc:
            raise ValueError('分界时间须为数值：' + str(cutoff)) from exc
        if not np.isfinite(boundary):
            raise ValueError('分界时间须为有限数值。')
        display = '%.6g'
    else:
        stamps = pd.to_datetime(raw, errors='coerce')
        if stamps.isna().any():
            raise ValueError('时间列含无法解析的时间值。')
        try:
            boundary = pd.Timestamp(cutoff)
        except (TypeError, ValueError) as exc:
            raise ValueError('分界时间无法解析：' + str(cutoff)) from exc
        stamps = stamps.to_numpy()
        display = '%s'
    if not np.all(stamps[1:] >= stamps[:-1]):
        raise ValueError('时间列须按非递减顺序排列；程序不会隐式重排数据。')
    before = (stamps < boundary)
    if not before.any() or before.all():
        raise ValueError('分界时间须落在数据时间范围内，使两个阶段都包含观测。')
    names = ['改善前', '改善后']
    return (before, ~before, names, '时间列“%s”，分界 = %s（前段 < 分界，后段 ≥ 分界）' % (
        time, display % boundary))


def _subgroups(df, mask, size, group_col):
    """只在该阶段的行内分组；组标识不得跨阶段或非连续重复。"""
    if group_col:
        if group_col not in df:
            raise ValueError('工作表缺少子组标识列。')
        labels = df.loc[mask, group_col].to_numpy()
        if pd.isna(labels).any():
            raise ValueError('子组标识存在缺失值。')
        try:
            cuts = np.flatnonzero(labels[1:] != labels[:-1]) + 1
        except TypeError as exc:
            raise ValueError('子组标识须为可比较的标量。') from exc
        seen, previous = set(), None
        for i, label in enumerate(labels):
            if i == 0 or label != previous:
                if label in seen:
                    raise ValueError('子组标识不连续重复；不能排序合并。')
                seen.add(label)
            previous = label
        groups = np.split(np.arange(len(labels)), cuts)
        if any(len(group) < 2 for group in groups):
            # 先于统计计算拒绝单点子组，避免在极差/标准差为 0 时给出误导结果。
            raise ValueError('子组标识“%s”只含一个观测值；每个子组至少需要两个观测值。'
                             % next(labels[group[0]] for group in groups
                                    if len(group) < 2))
        return groups
    if size is None:
        raise ValueError('Xbar 图须指定子组大小或子组标识列。')
    size = _number(size, '子组大小')
    if size != int(size) or not 2 <= size <= 25:
        raise ValueError('子组大小须为 2 至 25 的整数。')
    count = int(mask.sum())
    groups = [np.arange(i, min(i + int(size), count)) for i in range(0, count, int(size))]
    if groups and len(groups[-1]) < 2:
        raise ValueError('阶段末子组不足两个观测值；请调整子组大小或改用子组标识列。')
    return groups


def _chart(values, groups, chart, mean=None, sigma=None):
    """values 为阶段内的有效观测，groups 是相对该阶段的下标。"""
    if chart == 'I-MR':
        return x_mR([float(values[i]) for i in groups], 2, mean=mean, sigma=sigma)
    function = xBar_R if chart == 'Xbar-R' else xBar_S
    return function([[float(values[i]) for i in group] for group in groups],
                    mean=mean, sigma=sigma)


def _limit(value, index=0):
    if isinstance(value, (list, tuple, np.ndarray)):
        return value[index] if index < len(value) else np.nan
    return value


def _limit_summary(value):
    """常量限返回标量；随子组大小变化时标记为明细表。"""
    if not isinstance(value, (list, tuple, np.ndarray)):
        return value
    values = np.asarray(value, dtype=float)
    if len(values) and np.all(values == values[0]):
        return float(values[0])
    return LIMIT_VARIES


def _sigma(result, chart):
    """由各图实际中心/控制限反算用于区内判异的组内标准差。"""
    if chart == 'I-MR':
        return _limit(result['bar2']) / CONSTANTS['d2'][2]
    size = result['n'][0]
    if chart == 'Xbar-R':
        return _limit(result['bar2']) / CONSTANTS['d2'][size]
    return _limit(result['bar2']) / c4_values(size)


def _stage_events(result, chart, labels):
    primary = 'I' if chart == 'I-MR' else 'Xbar'
    secondary = 'MR' if chart == 'I-MR' else ('R' if chart == 'Xbar-R' else 'S')
    center, upper = result['bar1'], result['ucl1']
    scales = [(_limit(upper, i) - _limit(center, i)) / 3 for i in range(len(result['Y1']))]
    events = _panel_events(result['Y1'], center, result['lcl1'], upper,
                           labels, scales, panel=primary)
    events += _panel_events(result['Y2'], result['bar2'], result['lcl2'],
                            result['ucl2'], labels, None, use_rules=False,
                            panel=secondary)
    return events


def _ljung_box(values):
    values = np.asarray(values, dtype=float)
    n = len(values)
    if n < 8 or np.ptp(values) == 0:
        return np.nan, np.nan
    lags = min(10, n // 5)
    centered = values - values.mean()
    denominator = float(centered @ centered)
    acf = [float(centered[:-lag] @ centered[lag:]) / denominator
           for lag in range(1, lags + 1)]
    statistic = n * (n + 2) * sum(rho * rho / (n - lag)
                                  for lag, rho in enumerate(acf, 1))
    return statistic, float(stats.chi2.sf(statistic, lags))


def _display(value):
    if value is None or (isinstance(value, (float, np.floating)) and not np.isfinite(value)):
        return '*'
    if isinstance(value, (int, np.integer)):
        return str(value)
    if isinstance(value, (float, np.floating)):
        return '%.6g' % value
    return str(value)


def _print_frame(print_port, title, frame):
    values = frame.astype(object).where(pd.notna(frame), None).values.tolist()
    display = [[_display(cell) for cell in row] for row in values]
    print_port(StatTable(title=title, headers=list(frame.columns), values=values,
                         display=display,
                         number_formats=['General'] * len(frame.columns)))


def _differences(before, after, alpha):
    rows, notes = [], []
    usable = len(before) > 1 and len(after) > 1
    if not usable:
        notes.append('每阶段至少需要两个有效观测才能执行检验。')
    autocorrelation = []
    constant = {}
    for name, values in (('改善前', before), ('改善后', after)):
        statistic, pvalue = _ljung_box(values)
        constant[name] = bool(np.ptp(values) == 0)
        flagged = np.isfinite(pvalue) and pvalue < alpha
        autocorrelation.append((name, statistic, pvalue, flagged))
    # 自相关无法评价时不能当作已满足独立性假设；常数列另按“不适用”处理。
    unevaluated = [item[0] for item in autocorrelation
                   if not np.isfinite(item[2]) and not constant[item[0]]]
    if usable and unevaluated:
        usable = False
        notes.append('%s的自相关无法评价（样本不足或为常数列）；独立性未充分评价，显著性未评价。'
                     % '、'.join(unevaluated))
    if usable and any(item[3] for item in autocorrelation):
        usable = False
        notes.append('检测到明显序列自相关（Ljung-Box p < %.3g）；独立样本检验不适用，显著性未评价。' % alpha)
    if usable:
        for name, values in (('改善前', before), ('改善后', after)):
            if np.ptp(values) == 0:
                rows.append([name + '趋势', 'Spearman 与顺序相关', np.nan, np.nan,
                             '常数列不适用'])
                continue
            trend = stats.spearmanr(np.arange(len(values)), values)
            rows.append([name + '趋势', 'Spearman 与顺序相关', float(trend.statistic),
                         float(trend.pvalue),
                         '存在显著趋势' if trend.pvalue < alpha else '未发现显著趋势'])
        if any(row[0].endswith('趋势') and np.isfinite(row[3]) and row[3] < alpha
               for row in rows):
            notes.append('阶段内存在与观测顺序相关的显著趋势；均值差异可能反映趋势或工况变化，不能直接归为改善。')
        if np.ptp(before) == 0 and np.ptp(after) == 0:
            rows += [['均值差异', 'Welch t 检验', np.nan, np.nan, '两阶段均为常数列，不适用'],
                     ['波动差异', 'Levene（Brown-Forsythe）', np.nan, np.nan,
                      '两阶段均为常数列，不适用']]
        else:
            welch = stats.ttest_ind(after, before, equal_var=False)
            levene = stats.levene(after, before, center='median')
            rows += [
                ['均值差异', 'Welch t 检验', float(welch.statistic), float(welch.pvalue),
                 '两阶段均值存在显著差异' if welch.pvalue < alpha else '未发现显著差异'],
                ['波动差异', 'Levene（Brown-Forsythe）', float(levene.statistic),
                 float(levene.pvalue),
                 '两阶段波动存在显著差异' if levene.pvalue < alpha else '未发现显著差异'],
            ]
    else:
        reason = notes[-1] if notes else '数据不足'
        rows += [['均值差异', 'Welch t 检验', np.nan, np.nan, '显著性未评价：' + reason],
                 ['波动差异', 'Levene（Brown-Forsythe）', np.nan, np.nan,
                  '显著性未评价：' + reason]]
    for name, statistic, pvalue, flagged in autocorrelation:
        rows.append([name + '自相关', 'Ljung-Box（滞后≤10）', statistic, pvalue,
                     '存在明显自相关' if flagged else
                     '未发现明显自相关' if np.isfinite(pvalue) else '样本不足或常数列，未评价'])
    return rows, notes


def analyze_improvement(df, value, chart='I-MR', split='stage', stage=None,
                        time=None, cutoff=None, limit_mode='independent',
                        alpha=.05, subgroup_size=None, subgroup_id=None):
    """返回阶段控制图、效果指标、检验和报告表；统计与界面分离。"""
    if not isinstance(df, pd.DataFrame) or not df.columns.is_unique:
        raise ValueError('输入须为列名唯一的工作表。')
    if chart not in CHARTS:
        raise ValueError('控制图类型须为 I-MR、Xbar-R 或 Xbar-S。')
    if limit_mode not in LIMIT_MODES:
        raise ValueError('控制限模式无效。')
    alpha = _number(alpha, '显著性水平')
    if not 0 < alpha < 1:
        raise ValueError('显著性水平须在 0 与 1 之间。')
    values = _values(df, value)
    before, after, names, split_info = split_phases(df, split, stage, time, cutoff)
    usable = ~np.isnan(values)
    dropped = int((~usable).sum())
    before &= usable
    after &= usable
    if not before.any() or not after.any():
        raise ValueError('每个阶段至少需要一个有效观测值。')
    positions = [np.flatnonzero(before), np.flatnonzero(after)]
    # 阶段内有效观测；子组下标只在该阶段数据上有意义。
    stage_values = [values[p] for p in positions]
    if subgroup_id:
        if subgroup_id not in df:
            raise ValueError('工作表缺少子组标识列。')
        if df[subgroup_id].isna().any():
            raise ValueError('子组标识存在缺失值。')
        for mask in (before, after):
            phase_ids = set(df.loc[mask, subgroup_id].tolist())
            # 缺失观测行不参与分组，不应被误判为另一阶段。
            other = set(df.loc[usable & ~mask, subgroup_id].tolist())
            if phase_ids & other:
                raise ValueError('子组标识跨越阶段边界；子组不得跨阶段。')
    phase_groups = ([np.arange(len(p)) for p in positions] if chart == 'I-MR' else
                    [_subgroups(df, mask, subgroup_size, subgroup_id)
                     for mask in (before, after)])
    # 子组在统计计算前校验，避免从 0 极差反推出误导性控制限。
    if chart == 'Xbar-R' and any(len(g) > 25 for groups in phase_groups for g in groups):
        raise ValueError('Xbar-R 子组大小须为 2 至 25。')
    results = [_chart(data, groups, chart)
               for data, groups in zip(stage_values, phase_groups)]
    if limit_mode == 'baseline':
        mean, sigma = _limit(results[0]['bar1']), _sigma(results[0], chart)
        if not np.isfinite(mean) or not np.isfinite(sigma) or sigma <= 0:
            raise ValueError('改善前阶段无法估计正的组内波动，不能建立固定基线。')
        results[1] = _chart(stage_values[1], phase_groups[1], chart,
                            mean=mean, sigma=sigma)
        if chart == 'I-MR':
            results[1]['bar2'] = CONSTANTS['d2'][2] * sigma
        elif chart == 'Xbar-S':
            # xBar_S 在指定 sigma 时把 S 中心线当 sigma 本身，须恢复可绘制的 S 统计量限。
            sizes = results[1]['n']
            results[1]['bar2'] = [c4_values(n) * sigma for n in sizes]
            results[1]['ucl2'] = [c4_values(n) * sigma
                                  + 3 * sigma * (1 - c4_values(n) ** 2) ** .5
                                  for n in sizes]
            results[1]['lcl2'] = [max(0., c4_values(n) * sigma
                                      - 3 * sigma * (1 - c4_values(n) ** 2) ** .5)
                                  for n in sizes]
    point_rows = [positions[i] + 1 if chart == 'I-MR' else
                  [positions[i][group[0]] + 1 for group in phase_groups[i]]
                  for i in (0, 1)]
    labels = [[df.index.to_numpy()[row - 1] for row in rows] for rows in point_rows]
    events = []
    for name, label, source_row, result in zip(names, labels, point_rows, results):
        stage_events = _stage_events(result, chart, label)
        for event in stage_events:
            event['stage'] = name
            event['source_row'] = int(source_row[event['x']])
            event['source_label'] = label[event['x']]
        events += stage_events
    stage_sigma = [_sigma(result, chart) for result in results]
    if limit_mode == 'baseline':
        stage_sigma[1] = stage_sigma[0]
    rows = []
    for i, (name, mask, data, sigma) in enumerate(zip(names, (before, after),
                                                     stage_values, stage_sigma)):
        sd = float(np.std(data, ddof=1)) if len(data) > 1 else np.nan
        stage_events = [e for e in events if e['stage'] == name]
        # 同一观测/子组在两个面板同时异常只计一次；分母是该阶段绘制点数。
        alarm_points = {e['point'] for e in stage_events}
        points = len(results[i]['Y1'])
        rows.append({'stage': name, 'n': int(mask.sum()), 'mean': float(np.mean(data)),
                     'sd': sd, 'sigma': sigma, 'start': positions[i][0] + 1,
                     'end': positions[i][-1] + 1, 'alarms': len(alarm_points),
                     'points': points, 'rate': len(alarm_points) / points,
                     'records': len(stage_events)})
    base, current = rows
    mean_diff = current['mean'] - base['mean']
    mean_rate = mean_diff / base['mean'] * 100 if base['mean'] != 0 else np.nan
    sd_rate = (current['sd'] / base['sd'] - 1) * 100 if base['sd'] else np.nan
    sd_ratio = current['sd'] / base['sd'] if base['sd'] else np.nan
    sigma_rate = ((current['sigma'] / base['sigma'] - 1) * 100
                  if base['sigma'] else np.nan)
    tables = {}
    unit = '观测' if chart == 'I-MR' else '子组'
    tables['summary'] = pd.DataFrame([
        ['变量', value], ['控制图', chart], ['阶段划分', SPLITS[split]],
        ['阶段定义', split_info], ['控制限模式', LIMIT_MODES[limit_mode]],
        ['阶段样本量', '%s=%d；%s=%d' % (names[0], base['n'], names[1], current['n'])],
        ['阶段起止行', '%s：%d → %d；%s：%d → %d' % (
            names[0], base['start'], base['end'], names[1], current['start'], current['end'])],
        ['删除缺失观测', dropped],
        ['子组', 'I-MR 单值；移动极差跨度 2；子组不跨阶段' if chart == 'I-MR'
         else '按阶段内顺序分组；子组不跨阶段'],
        ['显著性水平', alpha],
    ], columns=['项目', '内容'])
    tables['metrics'] = pd.DataFrame([
        ['样本数', base['n'], current['n'], np.nan, np.nan],
        ['均值', base['mean'], current['mean'], mean_diff, mean_rate],
        ['标准差（整体）', base['sd'], current['sd'], current['sd'] - base['sd'], sd_rate],
        ['SPC 组内波动', base['sigma'], current['sigma'],
         current['sigma'] - base['sigma'], sigma_rate],
        ['异常点数', base['alarms'], current['alarms'],
         current['alarms'] - base['alarms'], np.nan],
        ['异常%s比例' % unit, base['rate'], current['rate'],
         current['rate'] - base['rate'], np.nan],
        ['异常规则记录数', base['records'], current['records'],
         current['records'] - base['records'], np.nan],
    ], columns=['指标', names[0], names[1], '差值', '变化率（%）'])
    reasons = {'均值': '不适用：改善前均值为 0',
               '标准差（整体）': '不适用：改善前标准差为 0',
               'SPC 组内波动': '不适用：改善前组内波动为 0'}
    rates = tables['metrics']['变化率（%）'].astype(object)
    for i in tables['metrics'].index:
        if pd.isna(rates.iloc[i]) and tables['metrics'].at[i, '指标'] in reasons:
            rates.iloc[i] = '不适用'
    tables['metrics']['变化率（%）'] = rates
    tables['ratios'] = pd.DataFrame([
        ['波动比（改善后整体标准差 / 改善前）', sd_ratio,
         '' if np.isfinite(sd_ratio) else '不适用：改善前标准差为 0'],
        ['整体标准差变化率（%）', sd_rate,
         '' if np.isfinite(sd_rate) else '不适用：改善前标准差为 0'],
        ['SPC 组内波动比（改善后 / 改善前）',
         current['sigma'] / base['sigma'] if base['sigma'] else np.nan,
         '' if base['sigma'] else '不适用：改善前组内波动为 0'],
        ['均值变化率（%）', mean_rate,
         '' if np.isfinite(mean_rate) else '不适用：改善前均值为 0'],
    ], columns=['指标', '数值', '说明'])
    tables['limits'] = pd.DataFrame([
        [name, panel, _limit_summary(lower), _limit_summary(center),
         _limit_summary(upper)]
        for name, result in zip(names, results)
        for panel, center, lower, upper in [
            ('I' if chart == 'I-MR' else 'Xbar', result['bar1'], result['lcl1'], result['ucl1']),
            ('MR' if chart == 'I-MR' else 'R' if chart == 'Xbar-R' else 'S',
             result['bar2'], result['lcl2'], result['ucl2'])]
    ], columns=['阶段', '图表', 'LCL', 'CL', 'UCL'])
    # 子组大小不等时逐点列出实际控制限，与绘图和判异共用同一结果对象。
    tables['limit_details'] = pd.DataFrame([
        [name, panel, index + 1, _limit(lower, index), _limit(center, index),
         _limit(upper, index)]
        for name, result in zip(names, results)
        for panel, center, lower, upper in [
            ('I' if chart == 'I-MR' else 'Xbar', result['bar1'], result['lcl1'], result['ucl1']),
            ('MR' if chart == 'I-MR' else 'R' if chart == 'Xbar-R' else 'S',
             result['bar2'], result['lcl2'], result['ucl2'])]
        if LIMIT_VARIES in (_limit_summary(lower), _limit_summary(center),
                            _limit_summary(upper))
        for index in range(len(result['Y1']))
    ], columns=['阶段', '图表', '点号', 'LCL', 'CL', 'UCL'])
    tables['anomalies'] = pd.DataFrame([
        [event['stage'], event['panel'], event['point'],
         event['source_row'], event['source_label'],
         event['value'], event['lower'], event['center'], event['upper'],
         event['rule'], event['description'],
         '%d-%d' % (event['window_start'], event['window_end'])]
        for event in events
    ], columns=['阶段', '图表', '点号', '来源行', '来源标识', '统计值', 'LCL', 'CL', 'UCL',
                '触发规则', '规则说明', '窗口点号'])
    test_rows, test_notes = _differences(stage_values[0], stage_values[1], alpha)
    tables['tests'] = pd.DataFrame(test_rows, columns=['项目', '方法', '统计量', 'p 值', '结论'])
    conclusions = []
    if np.isfinite(mean_rate):
        conclusions.append(['均值变化（描述性）',
                            '均值下降 %.3g%%' % -mean_rate if mean_rate < 0
                            else '均值上升 %.3g%%' % mean_rate if mean_rate > 0
                            else '均值未变化'])
    else:
        conclusions.append(['均值变化（描述性）', '不适用：改善前均值为 0'])
    if np.isfinite(sd_rate):
        conclusions.append(['波动变化（描述性）',
                            '标准差下降 %.3g%%' % -sd_rate if sd_rate < 0
                            else '标准差上升 %.3g%%' % sd_rate if sd_rate > 0
                            else '标准差未变化'])
    else:
        conclusions.append(['波动变化（描述性）', '不适用：改善前标准差为 0'])
    for row in test_rows:
        if row[0] in ('均值差异', '波动差异'):
            conclusions.append([row[0] + '（统计）', row[4]])
    conclusions.append(['控制状态', '异常%s比例 %s → %s（分母：%s数 %d → %d）' % (
        unit, '%.3g%%' % (base['rate'] * 100), '%.3g%%' % (current['rate'] * 100),
        unit, base['points'], current['points'])])
    tables['conclusions'] = pd.DataFrame(conclusions, columns=['项目', '结论'])
    notes = [split_info, '控制限模式：' + LIMIT_MODES[limit_mode] + '。',
             '整体标准差为样本标准差（ddof=1）；SPC 组内波动来自各阶段控制图实际控制限，两者口径不同。',
             '异常记录按主图 Nelson 规则和极差类图越限统计；同一窗口可命中多条规则。',
             '统计显著差异不等同于改善由 APC、PID 整定或其他特定措施造成。',
             '标准差下降只描述波动缩小，不保证中心或规格符合性改善。']
    if limit_mode == 'baseline':
        notes.append('改善后阶段沿用改善前估计的均值与过程标准差，控制限不随改善后数据重新估计。')
    if dropped:
        notes.append('分析排除了 %d 个观测值缺失的行；来源工作表未修改。' % dropped)
    notes += test_notes
    return ImprovementResult(tables, notes, {
        'chart': chart, 'names': names, 'results': results, 'events': events,
        'limit_mode': limit_mode})


def phase_control_plot(result, figure):
    """绘制两阶段控制图；曲线和控制限全部取自后端结果。"""
    data = result.plot
    chart, names, results = data['chart'], data['names'], data['results']
    if figure.axes:
        raise ValueError('绘图画布已有内容。')
    axes = [figure.add_subplot(2, 1, 1), figure.add_subplot(2, 1, 2)]
    panels = [('Y1', 'bar1', 'lcl1', 'ucl1',
               'I 图（单值）' if chart == 'I-MR' else 'Xbar 图（子组均值）'),
              ('Y2', 'bar2', 'lcl2', 'ucl2',
               'MR 图（移动极差）' if chart == 'I-MR' else
               'R 图（子组极差）' if chart == 'Xbar-R' else 'S 图（子组标准差）')]
    colors = ['#0072b2', '#009e73']
    # 横轴按实际绘制点数：I-MR 为观测序号，Xbar 为子组序号。
    boundary = len(results[0]['Y1'])
    offsets = [0, boundary]
    ends = [boundary, boundary + len(results[1]['Y1'])]
    for axis, (value_key, center_key, lower_key, upper_key, title) in zip(axes, panels):
        for index, (name, stage) in enumerate(zip(names, results)):
            values = np.asarray(stage[value_key], dtype=float)
            x = np.arange(1, len(values) + 1) + offsets[index]
            role = '改善前' if index == 0 else '改善后'
            axis.plot(x, values, 'o-', color=colors[index], markersize=3,
                      linewidth=1, label=role if name == role else role + '（' + name + '）')
            for key, style, label in ((center_key, '-', 'CL'),
                                      (upper_key, '--', 'UCL'),
                                      (lower_key, '--', 'LCL')):
                limit = stage[key]
                y = (np.asarray(limit, dtype=float) if isinstance(limit, (list, tuple, np.ndarray))
                     and len(limit) == len(x) else np.full(len(x), float(limit)))
                axis.plot(x, y, style, color='#555555' if key == center_key else '#b2182b',
                          linewidth=.9, alpha=.85,
                          label=label if index == 0 else None)
        axis.axvline(boundary + .5, color='#333333', linestyle=':', linewidth=1)
        axis.text(boundary / 2 + .5, .96, '改善前', transform=axis.get_xaxis_transform(),
                  ha='center', va='top', fontsize=9)
        axis.text((boundary + ends[1]) / 2 + .5, .96,
                  '改善后', transform=axis.get_xaxis_transform(),
                  ha='center', va='top', fontsize=9)
        axis.set(title=title, ylabel='原单位')
        axis.grid(alpha=.3)
        axis.legend(fontsize=8, loc='best')
        style_axes(axis)
    for axis, panel in zip(axes, ['I' if chart == 'I-MR' else 'Xbar',
                                   'MR' if chart == 'I-MR' else
                                   'R' if chart == 'Xbar-R' else 'S']):
        selected = [event for event in data['events'] if event['panel'] == panel]
        if selected:
            axis.scatter([event['x'] + 1 + offsets[0 if event['stage'] == names[0] else 1]
                          for event in selected], [event['value'] for event in selected],
                         marker='x', s=48, color='#c62828', linewidths=1.6, zorder=5,
                         label='异常点')
    axes[0].tick_params(axis='x', labelbottom=False)
    axes[1].set_ylim(bottom=0)
    axes[-1].set(xlabel=('观测序号（按原始行顺序）' if chart == 'I-MR'
                         else '子组序号（阶段内按原始行顺序分组）'))
    figure.suptitle('改善前后控制图（%s）' % LIMIT_MODES[data['limit_mode']],
                    fontfamily=font_families('Microsoft YaHei')[:2])
    return {'axes': axes, 'connections': []}


def print_report(result, print_port):
    """统一报告；控制图、指标、检验与结论共用同一份后端结果。"""
    print_port('\n---- 过程改善前后控制图分析报告 ----')
    summary = result.tables['summary']
    print_port('\nA. 数据摘要')
    for row in summary.itertuples(index=False):
        print_port('%s：%s' % (row[0], _display(row[1])))
    print_port('\nB. 控制图结果')
    _print_frame(print_port, '控制限汇总', result.tables['limits'])
    if len(result.tables['limit_details']):
        _print_frame(print_port, '逐子组控制限明细', result.tables['limit_details'])
    anomalies = result.tables['anomalies']
    if len(anomalies):
        _print_frame(print_port, '异常点明细', anomalies)
        print_port('异常规则说明：')
        for rule, description in sorted(set(zip(anomalies['触发规则'], anomalies['规则说明']))):
            print_port('  %s：%s' % (rule, description))
        print_port('主图使用 Nelson 规则；极差类图只判定控制限越界；重叠窗口不等同于独立事件。')
    else:
        print_port('未发现异常点。主图按 Nelson 规则检查；极差类图检查是否越限。')
    print_port('\nC. 改善效果对比')
    _print_frame(print_port, '阶段指标对比', result.tables['metrics'])
    _print_frame(print_port, '变化率与波动比', result.tables['ratios'])
    print_port('整体标准差与 SPC 组内波动口径不同，不能合并解释为同一指标。')
    print_port('\nD. 统计检验')
    _print_frame(print_port, '统计检验与适用性', result.tables['tests'])
    print_port('\nE. 分析结论')
    _print_frame(print_port, '结论', result.tables['conclusions'])
    for note in result.notes:
        print_port(note)
    print_port('统计显著差异不等于因果改善；结论应结合工艺背景、采样方式和工程判断。')
