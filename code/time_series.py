"""Raw time-series data and native Matplotlib axes; no statistical transforms."""

import re
from decimal import Decimal, InvalidOperation
from numbers import Real

import numpy as np
import pandas as pd
from pandas.api.types import (is_numeric_dtype, is_complex_dtype,
                              is_datetime64_any_dtype, is_bool_dtype,
                              is_object_dtype, is_string_dtype)
from matplotlib import colormaps
from matplotlib.dates import AutoDateLocator, ConciseDateFormatter
from chart_style import style_axes


AXIS_MODES = ('单 Y 轴', '双 Y 轴', '多 Y 轴')


def time_values(series):
    if is_numeric_dtype(series.dtype):
        raise ValueError('时间列必须是日期时间；数值列请使用样本序号模式。')
    try:
        values = pd.to_datetime(series, format='mixed', errors='coerce')
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError('时间列无法解析为统一的日期时间。') from exc
    invalid = values.isna()
    if invalid.any():
        raise ValueError(f'时间列包含 {invalid.sum()} 个无效或缺失时间值，请修正后绘图。')
    if not is_datetime64_any_dtype(values.dtype):
        raise ValueError('时间列时区不一致，请先统一时区。')
    return values


def default_time_column(data):
    # Prefer native datetimes; only inspect text columns after them.
    columns = sorted(data.columns, key=lambda c: not is_datetime64_any_dtype(data[c].dtype))
    for column in columns:
        if is_numeric_dtype(data[column].dtype) or data.empty:
            continue
        try:
            time_values(data[column])
        except ValueError:
            continue
        return column
    return None


def axis_assignments(columns, assignments=None, mode=AXIS_MODES[0]):
    if mode not in AXIS_MODES:
        raise ValueError('未知 Y 轴模式。')
    limit = {AXIS_MODES[0]: 1, AXIS_MODES[1]: 2}.get(mode, max(1, len(columns)))
    result = {}
    for column in columns:
        axis = (assignments or {}).get(column, 1)
        if not isinstance(axis, int) or isinstance(axis, bool) or axis < 1:
            axis = 1
        result[column] = min(axis, limit)
    return result


def _mixed_numeric_y(series):
    """Project predominantly numeric text/status data for plotting only.

    PIReader preserves status text in an object column. Plot those rows as
    gaps while leaving the worksheet and its original values unchanged.
    """
    if not (is_object_dtype(series.dtype) or is_string_dtype(series.dtype)):
        return None
    cleaned = series.map(lambda value: None if isinstance(value, str)
                         and not value.strip() else value)
    present = cleaned.dropna()
    if present.empty or any(
            isinstance(value, bool) or not isinstance(value, (str, Real, Decimal))
            for value in present):
        return None
    try:
        numeric = pd.to_numeric(cleaned, errors='coerce')
    except (TypeError, ValueError, OverflowError):
        return None
    good = cleaned.notna() & numeric.notna()
    count = int(good.sum())
    status_count = int((cleaned.notna() & ~good).sum())
    if count < 2 or count <= status_count:
        return None  # Mostly status text or a single numeric-looking identifier.
    for raw, converted in zip(cleaned[good], numeric[good]):
        if isinstance(raw, str) and re.fullmatch(r'[+-]?0\d+', raw.strip()):
            return None  # Do not interpret zero-padded IDs as measurements.
        try:
            if Decimal(str(raw)) != Decimal(str(converted)):
                return None  # Do not hide precision loss.
        except InvalidOperation:
            return None
    values = numeric.to_numpy(dtype=float, na_value=np.nan)
    if np.isinf(values).any():
        return None
    return values


def is_numeric_y_candidate(series):
    """Shared criterion for time-series Y selection and rendering."""
    if is_bool_dtype(series.dtype) or is_complex_dtype(series.dtype):
        return False
    return is_numeric_dtype(series.dtype) or _mixed_numeric_y(series) is not None


def prepare_time_series(data, columns, time_column=None):
    if data.empty:
        raise ValueError('没有可绘制的数据。')
    if not data.columns.is_unique:
        raise ValueError('列名重复，请先使用唯一列名。')
    if not columns:
        raise ValueError('请至少选择一个 Y 数值列。')
    if len(set(columns)) != len(columns):
        raise ValueError('Y 变量不能重复。')
    ys = {}
    for column in columns:
        if column not in data or not is_numeric_y_candidate(data[column]):

            raise ValueError(f'Y 变量“{column}”必须是实数数值列。')
        # 原生数值数组无需装箱；扩展类型保留 object 以免大整数缺失值转成浮点。
        dtype = data[column].dtype
        if is_numeric_dtype(dtype):
            values = data[column].to_numpy(dtype=None if isinstance(dtype, np.dtype) else object,
                                           na_value=np.nan)
        else:
            values = _mixed_numeric_y(data[column])
        if pd.isna(values).all():
            raise ValueError(f'Y 变量“{column}”全部缺失。')
        if is_numeric_dtype(dtype) and np.isinf(data[column]).any():
            raise ValueError(f'Y 变量“{column}”包含无穷值。')
        ys[column] = values
    if time_column is None:
        return np.arange(1, len(data) + 1), ys
    if time_column not in data:
        raise ValueError('请选择有效的时间列。')
    times = time_values(data[time_column])
    order = np.argsort(times.to_numpy(), kind='stable')
    return times.iloc[order].to_numpy(), {c: y[order] for c, y in ys.items()}


def time_series_plot(figure, data, columns, time_column=None, assignments=None,
                     mode=AXIS_MODES[0], title='', xlabel='', ylabels=None,
                     legend=True, grid=True, *, prepared=None):
    # 对话框在替换旧窗口前验证；同一次同步绘图直接使用该结果。
    x, ys = prepare_time_series(data, columns, time_column) if prepared is None else prepared
    assigned = axis_assignments(columns, assignments, mode)
    used = sorted(set(assigned.values()))
    figure.clear()
    figure.set_layout_engine('constrained')
    width, height = figure.get_size_inches()
    figure.set_size_inches(max(width, 6 + 1.15 * (len(used) - 1)), height)
    main = figure.add_subplot(111)
    axes = {used[0]: main}
    for position, number in enumerate(used[1:], start=int(used[0] != 1)):
        ax = main.twinx()
        ax.spines['right'].set_position(('outward', position * 70))
        axes[number] = ax
    if used[0] != 1:
        main.yaxis.tick_right()
        main.yaxis.set_label_position('right')
        main.spines['left'].set_visible(False)
    colors = colormaps['turbo'](np.linspace(.08, .92, max(2, len(columns))))
    colors[:, :3] *= .7
    lines = []
    for column, color in zip(columns, colors):
        line, = axes[assigned[column]].plot(x, ys[column], label=str(column), color=color)
        lines.append(line)
    main.set_title(title)
    main.set_xlabel(xlabel or (str(time_column) if time_column is not None else '样本序号'))
    main.grid(grid)
    if time_column is not None:
        locator = AutoDateLocator()
        main.xaxis.set_major_locator(locator)
        main.xaxis.set_major_formatter(ConciseDateFormatter(locator))
    if legend:
        main.legend(handles=lines)
    for number, ax in axes.items():
        members = [c for c in columns if assigned[c] == number]
        label = (ylabels or {}).get(number) or ', '.join(map(str, members))
        ax.set_ylabel(label)
        style_axes(ax)
        color = ax.lines[0].get_color() if len(members) == 1 else '#303841'
        ax.yaxis.label.set_color(color)
        ax.tick_params(axis='y', colors=color)
        ax.spines['left' if number == 1 else 'right'].set_color(color)
    return axes
