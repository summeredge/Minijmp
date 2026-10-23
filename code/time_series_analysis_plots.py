"""时间序列结果图；不拟合、不补值，也不创建 Tk 窗口。

返回 {'axes': [...], 'connections': [...]}；GUI 重绘前应 mpl_disconnect
所有 connections。on_pick 接收原工作表行号或聚合观测的 source_rows 列表，
行号沿用后端，不重编号。未来预测和相关系数点没有来源行映射。
"""

import numpy as np
import pandas as pd
from matplotlib import dates
from matplotlib.ticker import MaxNLocator
from scipy import stats

from chart_style import style_axes


_KINDS = ('series', 'acf', 'pacf', 'ccf', 'decomposition', 'trend',
          'residual', 'residual_qq', 'forecast')


def _time_values(axis, table, mode):
    if mode == 'sequence':
        x = table['sequence'].to_numpy(dtype=float, na_value=np.nan)
        axis.xaxis.set_major_locator(MaxNLocator(integer=True))
        axis.set_xlabel('序号')
        return x
    if mode == 'elapsed':
        axis.set_xlabel('相对时间（秒）')
        return table['elapsed'].dt.total_seconds().to_numpy(dtype=float, na_value=np.nan)
    values = pd.to_datetime(table['time'])
    timezone = values.dt.tz
    x = dates.date2num(values.to_numpy())
    locator = dates.AutoDateLocator(tz=timezone)
    axis.xaxis.set_major_locator(locator)
    axis.xaxis.set_major_formatter(dates.ConciseDateFormatter(locator, tz=timezone))
    axis.set_xlabel('时间')
    return x


def _source_rows(table):
    rows = []
    groups = table['source_rows'].to_list() if 'source_rows' in table else [None] * len(table)
    singles = table['source_row'].to_list() if 'source_row' in table else [None] * len(table)
    for group, row in zip(groups, singles):
        if isinstance(group, (list, tuple, np.ndarray)):
            members = [int(row) for row in group if pd.notna(row)]
            rows.append(members[0] if len(members) == 1 else members or None)
        else:
            rows.append(int(row) if pd.notna(row) else None)
    return rows


def time_series_analysis_plot(result, kind, figure, on_pick=None):
    """消费 result.tables；未知、空或不可用图形以 ValueError 明确报告。

    表结构与 time_series_analysis 一致：data/time/sequence/value，
    decomposition.value 为观测，forecast.predicted 为预测。时间轴沿用
    result.series 的日期模式，固定采样使用 elapsed 秒；后端 notes 明确
    irregular=sequence 时只使用序号，不猜测未来时间。
    ACF/PACF 区间围绕估计值，显示时平移到零。不为 CCF 添加假设区间。
    """
    if kind not in _KINDS:
        raise ValueError('未知时间序列图形：' + str(kind))
    table_name = {'series': 'data', 'residual': 'residuals',
                  'residual_qq': 'residuals'}.get(kind, kind)
    table = result.tables.get(table_name)
    if table is None or table.empty:
        raise ValueError('此分析没有可用的' + table_name + '数据。')
    if kind in ('residual', 'residual_qq') and 'diagnostic_used' in table:
        table = table.loc[table['diagnostic_used'].fillna(False)]
    mode = ('date' if isinstance(result.series.index, pd.DatetimeIndex) else
            'sequence' if any(note.startswith('irregular=sequence：') for note in result.notes) else
            'elapsed')
    count = 4 if kind == 'decomposition' else 1
    axes = [figure.add_subplot(count, 1, i+1) for i in range(count)]
    axis = axes[0]
    points = []

    def time_line(ax, data, column, label, *, mapped=True, **kwargs):
        x = _time_values(ax, data, mode)
        y = data[column].to_numpy(dtype=float, na_value=np.nan)
        valid = np.isfinite(x) & np.isfinite(y)
        # 保留 NaN 空隙，避免把不可用观测画成补值或跨缺口连线。
        y = np.where(valid, y, np.nan)
        line, = ax.plot(x, y, 'o-', markersize=3, label=label, **kwargs)
        if mapped and on_pick is not None:
            points.append((ax, np.column_stack((x, y)), _source_rows(data)))
        return line, valid

    if kind in ('acf', 'pacf', 'ccf'):
        lag = table['lag'].to_numpy(dtype=float, na_value=np.nan)
        correlation = table['correlation'].to_numpy(dtype=float, na_value=np.nan)
        valid = np.isfinite(lag) & np.isfinite(correlation)
        if not valid.any():
            raise ValueError('相关分析没有可用的滞后值。')
        axis.vlines(lag[valid], 0, correlation[valid], color='#0072b2')
        axis.plot(lag[valid], correlation[valid], 'o', markersize=4, color='#0072b2')
        if kind != 'ccf' and {'ci_lower', 'ci_upper'} <= set(table):
            lower = table['ci_lower'].to_numpy(dtype=float, na_value=np.nan)
            upper = table['ci_upper'].to_numpy(dtype=float, na_value=np.nan)
            usable = valid & np.isfinite(lower) & np.isfinite(upper)
            if usable.any():
                method = 'Bartlett 点态区间' if kind == 'acf' else '正态近似点态区间'
                axis.fill_between(lag, lower-correlation, upper-correlation, where=usable,
                                  alpha=.2, label=method+'（以 0 为中心）')
                axis.legend(fontsize=8)
        axis.axhline(0, color='gray', linewidth=.8)
        axis.xaxis.set_major_locator(MaxNLocator(integer=True))
        axis.set(xlabel='滞后 k', ylabel='相关系数', title=kind.upper())
        if kind == 'pacf':
            axis.set_title('PACF（Yule–Walker MLE）')
        if kind == 'ccf':
            axis.set_xlabel('滞后 k（k > 0：X 领先 Y）')
    elif kind == 'decomposition':
        for ax, column, label in zip(axes, ('value', 'trend', 'seasonal', 'residual'),
                                     ('观测', '趋势', '季节', '残差')):
            _, valid = time_line(ax, table, column, label)
            ax.set_ylabel(label)
            if not valid.any():
                ax.text(.5, .5, '此分量无可用数据', ha='center', transform=ax.transAxes)
        axis.set_title('季节分解')
    elif kind == 'residual_qq':
        residual = table['residual'].to_numpy(dtype=float, na_value=np.nan)
        valid = np.isfinite(residual)
        if np.count_nonzero(valid) < 2:
            raise ValueError('残差 QQ 图至少需要 2 个有效观测。')
        order = np.flatnonzero(valid)[np.argsort(residual[valid], kind='stable')]
        (quantiles, ordered), (slope, intercept, _) = stats.probplot(residual[valid])
        axis.plot(quantiles, ordered, 'o', markersize=4)
        axis.plot(quantiles, intercept+slope*quantiles, '--', color='gray')
        if on_pick is not None:
            rows = _source_rows(table)
            points.append((axis, np.column_stack((quantiles, ordered)), [rows[i] for i in order]))
        axis.set(xlabel='正态理论分位数', ylabel='残差分位数', title='残差 QQ 图')
    else:
        if kind == 'series':
            _, valid = time_line(axis, table, 'value', '观测')
            axis.set(ylabel='数值', title='时间序列')
        elif kind == 'trend':
            time_line(axis, table, 'value', '观测')
            _, valid = time_line(axis, table, 'fitted', '趋势', mapped=False)
            axis.set(ylabel='数值', title='趋势分析')
            axis.legend()
        elif kind == 'residual':
            _, valid = time_line(axis, table, 'residual', '残差')
            axis.axhline(0, color='gray', linestyle='--')
            axis.set(ylabel='残差', title='残差序列')
        else:
            history = result.tables.get('data')
            if history is not None and not history.empty:
                time_line(axis, history, 'value', '观测')
            forecast_line, valid = time_line(axis, table, 'predicted', '预测', mapped=False)
            if {'ci_lower', 'ci_upper'} <= set(table):
                lower = table['ci_lower'].to_numpy(dtype=float, na_value=np.nan)
                upper = table['ci_upper'].to_numpy(dtype=float, na_value=np.nan)
                axis.fill_between(forecast_line.get_xdata(), lower, upper,
                                  where=valid & np.isfinite(lower) & np.isfinite(upper),
                                  color=forecast_line.get_color(), alpha=.2, label='预测区间')
            axis.set(ylabel='数值', title='时间序列预测')
            axis.legend()
        if not valid.any():
            raise ValueError('此图没有有效观测。')

    connections = []
    if points:
        def click(event):
            if event.button != 1 or event.inaxes not in axes:
                return
            best = None
            for ax, xy, rows in points:
                if event.inaxes is not ax:
                    continue
                valid = np.isfinite(xy).all(axis=1) & np.array([row is not None for row in rows])
                indices = np.flatnonzero(valid)
                if not len(indices):
                    continue
                distance = np.linalg.norm(ax.transData.transform(xy[valid]) - [event.x, event.y], axis=1)
                nearest = int(np.argmin(distance))
                if distance[nearest] <= 10 and (best is None or distance[nearest] < best[0]):
                    best = (distance[nearest], rows[indices[nearest]])
            if best is not None:
                on_pick(best[1])
        connections.append(figure.canvas.mpl_connect('button_press_event', click))
    for ax in axes:
        ax.grid(alpha=.3)
        style_axes(ax)
    figure.set_layout_engine('constrained')
    return {'axes': axes, 'connections': connections}
