"""高级 SPC 结果图；只呈现后端统计量、控制限和报警，不重新计算。

on_pick 接收当前监控数据的 1 基 source_row，历史基线不关联当前工作表。
调用方重绘前应 mpl_disconnect 返回的 connections，并清空旧图。
"""

import numpy as np
import pandas as pd
from matplotlib.ticker import MaxNLocator

from chart_style import style_axes


_TITLES = {'EWMA': 'EWMA 控制图', 'CUSUM': 'CUSUM 控制图',
           'Nelson': 'Nelson 判异规则控制图', 'T2': 'Hotelling T² 控制图'}


def spc_plot(result, figure, on_pick=None):
    """绘制 observations 和可选 baseline；返回 axes 和鼠标连接编号。

    sequence 仅用于横坐标，source_row 保留删缺失值后的非连续原行号。
    CUSUM negative 已是负支，不再取负；按必需的 rules 字段分支标记。
    Nelson 仅显示给定的中心及 ±3σ 限，不从当前样本反推 σ。
    """
    kind = result.kind
    if kind not in _TITLES:
        raise ValueError('未知 SPC 图形：' + str(kind))
    current = result.tables.get('observations')
    if current is None or current.empty:
        raise ValueError('没有可用的当前监控观测。')
    baseline = result.tables.get('baseline')
    stages = [(current, '当前监控（Phase II）')]
    if baseline is not None and not baseline.empty:
        stages.append((baseline, '历史基线（Phase I）'))
    required = {'sequence', 'statistic', 'lower', 'center', 'upper', 'alarm'}
    if kind == 'CUSUM':
        required.add('rules')
    for table, phase in stages:
        missing = required - set(table)
        if table is current and kind == 'CUSUM' and 'negative' not in table:
            missing.add('negative')
        if missing:
            raise ValueError(phase + '缺少绘图列：' + '、'.join(sorted(missing)))
    x = current['sequence'].to_numpy(dtype=float, na_value=np.nan)
    branches = ['statistic', 'negative'] if kind == 'CUSUM' else ['statistic']
    xy = [np.column_stack((x, current[column].to_numpy(dtype=float, na_value=np.nan)))
          for column in branches]
    if not any(np.isfinite(points).all(axis=1).any() for points in xy):
        raise ValueError('当前监控没有有效统计量。')

    axes = [figure.add_subplot(len(stages), 1, i+1) for i in range(len(stages))]
    for axis, (table, phase) in zip(axes, stages):
        if 'phase' in table:
            phase_name = {'phase1': 'Phase I：基线回顾', 'phase2': 'Phase II：新样本监控',
                          'known': '已知参数'}.get(table['phase'].iloc[0])
            if phase_name:
                phase = ('当前监控' if table is current else '历史基线') + '（' + phase_name + '）'
        sequence = table['sequence'].to_numpy(dtype=float, na_value=np.nan)
        alarm = table['alarm'].fillna(False).to_numpy(dtype=bool)
        columns = ['statistic']
        labels = ['观测值' if kind == 'Nelson' else 'T²' if kind == 'T2' else 'EWMA 统计量']
        if kind == 'CUSUM':
            labels = ['正支 C⁺']
            if 'negative' in table:
                columns.append('negative')
                labels.append('负支 −C⁻')
        alarm_points = []
        for column, label, color in zip(columns, labels, ('#0072b2', '#009e73')):
            values = table[column].to_numpy(dtype=float, na_value=np.nan)
            valid = np.isfinite(sequence) & np.isfinite(values)
            axis.plot(sequence, np.where(valid, values, np.nan), 'o-',
                      color=color, markersize=3, linewidth=1, label=label)
            branch_alarm = alarm
            if kind == 'CUSUM':
                rule = 'CUSUM+' if column == 'statistic' else 'CUSUM-'
                branch_alarm = alarm & table['rules'].fillna('').str.split('; ').map(
                    lambda rules: rule in rules).to_numpy(dtype=bool)
            alarm_points.append(np.column_stack((sequence[branch_alarm & valid], values[branch_alarm & valid])))
        for column, label, color, linestyle in (
                ('center', '中心线', '#666666', ':'),
                ('lower', '下控制限（−3σ）' if kind == 'Nelson' else '下控制限', '#d55e00', '--'),
                ('upper', '上控制限（+3σ）' if kind == 'Nelson' else '上控制限', '#d55e00', '--')):
            if kind == 'T2':
                if column == 'center':
                    continue
                if column == 'lower':
                    label, color, linestyle = '统计量零界', '#666666', ':'
            values = table[column].to_numpy(dtype=float, na_value=np.nan)
            axis.plot(sequence, np.where(np.isfinite(values), values, np.nan),
                      color=color, linestyle=linestyle, linewidth=1, label=label)
        points = np.concatenate(alarm_points)
        axis.scatter(points[:, 0], points[:, 1], marker='x', s=48,
                     color='#c62828', linewidths=1.6, zorder=5, label='异常观测')
        ylabel = '标准化累积和' if kind == 'CUSUM' else 'T²' if kind == 'T2' else '原单位'
        axis.set(title=_TITLES[kind] + ' — ' + phase, xlabel='观测序号', ylabel=ylabel)
        axis.xaxis.set_major_locator(MaxNLocator(integer=True))
        axis.grid(alpha=.3)
        axis.legend(fontsize=8, loc='best')
        style_axes(axis)

    connections = []
    if on_pick is not None and 'source_row' in current:
        source_rows = current['source_row'].to_numpy()
        mapped = pd.notna(source_rows)

        def click(event):
            if event.button != 1 or event.inaxes is not axes[0]:
                return
            best = None
            for points in xy:
                indices = np.flatnonzero(np.isfinite(points).all(axis=1) & mapped)
                if not len(indices):
                    continue
                pixels = axes[0].transData.transform(points[indices])
                distance = np.linalg.norm(pixels - [event.x, event.y], axis=1)
                nearest = int(np.argmin(distance))
                if distance[nearest] <= 10 and (best is None or distance[nearest] < best[0]):
                    best = (distance[nearest], int(source_rows[indices[nearest]]))
            if best is not None:
                on_pick(best[1])

        connections.append(figure.canvas.mpl_connect('button_press_event', click))
    figure.set_layout_engine('constrained')
    return {'axes': axes, 'connections': connections}
