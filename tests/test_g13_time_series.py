"""G13: real curves, raw values, axes, native dialog and viewer integration."""
import ast
import inspect
from types import SimpleNamespace
import tkinter as tk

import numpy as np
import pandas as pd
import pytest
from MiniJMP import Minijmp
import matplotlib

matplotlib.use('Agg')
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.backend_bases import MouseEvent
from matplotlib.figure import Figure
from matplotlib.dates import AutoDateLocator, ConciseDateFormatter

import time_series
from time_series import (AXIS_MODES, axis_assignments, default_time_column,
                         prepare_time_series, time_series_plot)
from time_series_dialog import TimeSeriesDialog


@pytest.fixture
def data():
    return pd.DataFrame({'时间': pd.to_datetime(['2026-10-03', '2026-10-01', '2026-10-01', '2026-10-02']),
                         '温度': [30., 10., 11., np.nan], '压力': [300., 100., 110., 200.],
                         '流量': [3000., 1000., 1100., 2000.], '批次': ['甲', '乙', '丙', '丁']},
                        index=[9, 4, 4, 2])


@pytest.fixture
def figure():
    fig = Figure(figsize=(10, 7))
    FigureCanvasAgg(fig)
    return fig


@pytest.mark.parametrize('kind', ['datetime', 'string', 'sample', 'timezone'])
def test_raw_values_stable_duplicates_missing_and_immutable(data, figure, kind):
    if kind == 'string':
        data['时间'] = data['时间'].astype(str)
    if kind == 'timezone':
        data['时间'] = data['时间'].dt.tz_localize('Asia/Shanghai')
    before = data.copy(deep=True)
    axes = time_series_plot(figure, data, ['温度', '压力'], None if kind == 'sample' else '时间')
    ax = axes[1]
    order = [0, 1, 2, 3] if kind == 'sample' else [1, 2, 3, 0]
    for line, column in zip(ax.lines, ['温度', '压力']):
        np.testing.assert_equal(np.asarray(line.get_ydata(), dtype=float), data[column].to_numpy()[order])
        assert len(line.get_xdata()) == 4
    if kind == 'sample':
        np.testing.assert_equal(ax.lines[0].get_xdata(), [1, 2, 3, 4])
    else:
        assert ax.lines[0].get_xdata()[0] == ax.lines[0].get_xdata()[1]
        assert isinstance(ax.xaxis.get_major_locator(), AutoDateLocator)
        assert isinstance(ax.xaxis.get_major_formatter(), ConciseDateFormatter)
    assert np.isnan(ax.lines[0].get_path().vertices[:, 1]).sum() == 1
    pd.testing.assert_frame_equal(data, before)


@pytest.mark.parametrize('mode,count,expected', [(AXIS_MODES[0], 1, [1, 1, 1]),
    (AXIS_MODES[1], 2, [1, 2, 2]), (AXIS_MODES[2], 3, [1, 2, 3])])
def test_modes_ownership_shared_x_independent_y(data, figure, mode, count, expected):
    columns = ['温度', '压力', '流量']
    axes = time_series_plot(figure, data, columns, '时间', dict(zip(columns, [1, 2, 3])), mode)
    assert len(figure.axes) == count
    for column, number in zip(columns, expected):
        assert column in [line.get_label() for line in axes[number].lines]
    main = figure.axes[0]
    assert [t.get_text() for t in main.get_legend().get_texts()] == columns
    assert len({tuple(line.get_color()) for ax in axes.values() for line in ax.lines}) == 3
    for ax in figure.axes[1:]:
        assert ax.get_shared_x_axes().joined(ax, main)
        assert not ax.get_shared_y_axes().joined(ax, main)
    if count == 3:
        assert axes[2].spines['right'].get_position() == ('outward', 0)
        assert axes[3].spines['right'].get_position() == ('outward', 70)
        assert axes[1].get_ylim() != axes[2].get_ylim() != axes[3].get_ylim()


def test_same_axis_sparse_axes_and_replot(data, figure):
    columns = ['温度', '压力', '流量']
    axes = time_series_plot(figure, data, columns, assignments=dict(zip(columns, [1, 3, 3])), mode=AXIS_MODES[2])
    assert set(axes) == {1, 3} and len(axes[3].lines) == 2
    assert axes[3].yaxis.label.get_color() == '#303841'
    for mode, count in [(AXIS_MODES[1], 2), (AXIS_MODES[0], 1), (AXIS_MODES[2], 3)]:
        time_series_plot(figure, data, columns, assignments=dict(zip(columns, [1, 2, 3])), mode=mode)
        assert len(figure.axes) == count
        assert sum(len(ax.lines) for ax in figure.axes) == 3


@pytest.mark.parametrize('mode,expected', [(AXIS_MODES[0], [1, 1, 1, 1, 1]),
    (AXIS_MODES[1], [1, 1, 1, 2, 2]), (AXIS_MODES[2], [1, 1, 1, 3, 5])])
def test_invalid_assignments(mode, expected):
    columns = list('abcde')
    assert list(axis_assignments(columns, dict(zip(columns, [None, -1, 'Y2', 3, 99])), mode).values()) == expected
    with pytest.raises(ValueError, match='模式'):
        axis_assignments(columns, mode='unknown')


@pytest.mark.parametrize('change,columns,time_column,message', [
    ('empty', ['温度'], None, '没有'), ('none', [], None, '至少'),
    ('none', ['批次'], None, '数值'), ('none', ['不存在'], None, '数值'),
    ('nan', ['温度'], None, '全部缺失'), ('badtime', ['温度'], '时间', '无效'),
    ('nat', ['温度'], '时间', '无效'), ('numeric_time', ['温度'], '时间', '日期时间'),
    ('none', ['温度'], 'missing', '时间列'), ('inf', ['温度'], None, '无穷'),
    ('complex', ['温度'], None, '实数'), ('duplicate', ['温度'], None, '列名重复'),
    ('boolean', ['温度'], None, '实数'),
    ('none', ['温度', '温度'], None, '重复')])
def test_validation_preserves_previous_figure(data, figure, change, columns, time_column, message):
    if change == 'empty': data = data.iloc[:0]
    if change == 'nan': data['温度'] = np.nan
    if change == 'badtime': data['时间'] = ['bad'] * 4
    if change == 'nat': data['时间'] = pd.NaT
    if change == 'numeric_time': data['时间'] = [1, 2, 3, 4]
    if change == 'inf': data['温度'] = np.inf
    if change == 'complex': data['温度'] = 1 + 2j
    if change == 'boolean': data['温度'] = pd.array([True, None, False, True], dtype='boolean')
    if change == 'duplicate': data.columns = ['时间', '温度', '温度', '流量', '批次']
    old = figure.add_subplot()
    with pytest.raises(ValueError, match=message):
        time_series_plot(figure, data, columns, time_column)
    assert figure.axes == [old]


def test_datetime_default_nullable_numeric_and_large_data(figure):
    data = pd.DataFrame({'文本时间': ['2026-10-01', '2026-10-02'],
                         '时间': pd.date_range('2026-10-01', periods=2),
                         '值': pd.array([1, None], dtype='Int64')})
    assert default_time_column(data) == '时间'
    assert default_time_column(data.drop(columns='时间')) == '文本时间'
    assert default_time_column(pd.DataFrame({'值': [1, 2]})) is None
    _, ys = prepare_time_series(data, ['值'])
    np.testing.assert_equal(np.asarray(ys['值'], dtype=float), [1, np.nan])
    large = pd.DataFrame({'值': np.arange(50000, dtype=float)})
    axes = time_series_plot(figure, large, ['值'])
    assert len(axes[1].lines) == 1 and len(axes[1].lines[0].get_ydata()) == 50000


def test_integer_values_not_rounded_and_only_used_right_axes(figure):
    data = pd.DataFrame({'a': [2**60 + 1, 2**60 + 2], 'b': [1, 2], 'c': [3, 4]})
    axes = time_series_plot(figure, data, ['a', 'b', 'c'], assignments={'a': 2, 'b': 3, 'c': 3},
                            mode=AXIS_MODES[2])
    assert set(axes) == {2, 3} and len(figure.axes) == 2
    np.testing.assert_array_equal(axes[2].lines[0].get_ydata(), data['a'])
    assert axes[2].yaxis.get_label_position() == 'right'
    assert axes[2].yaxis.get_ticks_position() == 'right'
    assert axes[3].spines['right'].get_position() == ('outward', 70)
    nullable = pd.DataFrame({'值': pd.array([2**60 + 1, None], dtype='Int64')})
    axes = time_series_plot(figure, nullable, ['值'])
    assert axes[1].lines[0].get_ydata()[0] == 2**60 + 1
    assert pd.isna(axes[1].lines[0].get_ydata()[1])


def test_many_axes_layout(figure):
    data = pd.DataFrame({f'Y{i}': np.arange(5) * 10. ** i for i in range(1, 7)})
    time_series_plot(figure, data, list(data), assignments={c: i for i, c in enumerate(data, 1)},
                     mode=AXIS_MODES[2], legend=False, grid=False)
    figure.canvas.draw()
    renderer = figure.canvas.get_renderer()
    assert len(figure.axes) == 6 and figure.axes[0].get_legend() is None
    labels = [ax.yaxis.label.get_window_extent(renderer) for ax in figure.axes]
    assert all(box.x0 >= 0 and box.x1 <= figure.bbox.width for box in labels)
    assert not any(a.overlaps(b) for i, a in enumerate(labels) for b in labels[i + 1:])


@pytest.mark.parametrize('extension', ['png', 'svg', 'pdf'])
def test_multi_axis_layout_and_native_save(data, figure, tmp_path, extension):
    from pandastable_local.plotting import PlotViewer
    columns = ['温度', '压力', '流量']
    time_series_plot(figure, data, columns, '时间', dict(zip(columns, [1, 2, 3])), AXIS_MODES[2],
                     title='生产趋势', ylabels={1: '温度 ℃', 2: '压力 MPa', 3: '流量 m³/h'})
    figure.canvas.draw()
    renderer = figure.canvas.get_renderer()
    for ax in figure.axes:
        low, high = sorted(ax.get_ylim())
        ticks = [text for value, text in zip(ax.get_yticks(), ax.get_yticklabels()) if low <= value <= high]
        for text in [ax.yaxis.label, ax.xaxis.label, ax.title, *ticks]:
            if text.get_visible() and text.get_text():
                box = text.get_window_extent(renderer)
                assert box.x0 >= 0 and box.x1 <= figure.bbox.width
                assert box.y0 >= 0 and box.y1 <= figure.bbox.height
    target = tmp_path / f'trend.{extension}'
    viewer = SimpleNamespace(fig=figure, globalopts={'dpi': 100})
    PlotViewer.savePlot(viewer, str(target))
    assert target.stat().st_size > 1000


@pytest.fixture
def dialog(tk_root, data):
    from MiniJMP import Minijmp
    from modified_app import Minijmp_pre
    parent = tk.Frame(tk_root)
    parent.pf = None
    output = []
    app = SimpleNamespace(table=parent, print=output.append,
                          dialog_help_msg=lambda **kw: Minijmp_pre.dialog_help_msg(None, **kw),
                          addPlot=lambda: None)
    app.showPlotViewer = lambda **kw: Minijmp.showPlotViewer(app, **kw)
    instance = TimeSeriesDialog(parent, df=data, app=app, title='时间序列图')
    instance.output = output
    yield instance
    if parent.pf is not None: parent.pf.close()
    instance.main.destroy()
    parent.destroy()


def choose(dialog):
    dialog.ylist.selection_set(0, 2)
    dialog.update_variables()
    dialog.main.update()


def test_real_dialog_selection_modes_assignments_and_titles(dialog):
    assert dialog.xvar.get() == '时间' and not dialog.sample_mode.get()
    assert dialog.mode.get() == AXIS_MODES[0]
    assert dialog.ylist.size() == 3
    choose(dialog)
    columns = dialog.selected_columns()
    dialog.mode_combo.current(2)
    dialog.mode_combo.event_generate('<<ComboboxSelected>>')
    for i, column in enumerate(columns):
        dialog.axis_table.selection_set(str(i))
        dialog.select_variable()
        dialog.axisvar.set(f'Y{i + 1}')
        dialog.assign_axis()
    assert list(dialog.assignments.values()) == [1, 2, 3]
    dialog.label_axis.set('Y3')
    dialog.select_axis_title()
    dialog.ylabel.set('流量单位')
    dialog.save_axis_title()
    assert dialog.ylabels[3] == '流量单位'
    for mode, expected in [(AXIS_MODES[1], [1, 2, 2]), (AXIS_MODES[0], [1, 1, 1]),
                            (AXIS_MODES[2], [1, 1, 1])]:
        dialog.mode.set(mode)
        dialog.update_variables()
        assert dialog.selected_columns() == columns
        assert list(dialog.assignments.values()) == expected
    dialog.assignments[columns[0]] = -5
    dialog.update_variables()
    assert dialog.assignments[columns[0]] == 1
    dialog.sample_mode.set(True)
    dialog.update_x_mode()
    assert str(dialog.time_combo.cget('state')) == 'disabled'


def test_real_viewer_replot_navigation_and_save(dialog, tmp_path):
    choose(dialog)
    dialog.mode.set(AXIS_MODES[2])
    dialog.assignments = dict(zip(dialog.selected_columns(), [1, 2, 3]))
    dialog.apply()
    viewer = dialog.app.table.pf
    viewer.main.geometry('760x560')
    viewer.main.update()
    assert len(viewer.fig.axes) == 3
    toolbar = viewer.toolbar
    assert toolbar.winfo_ismapped()
    assert toolbar.winfo_rooty() + toolbar.winfo_height() <= viewer.main.winfo_rooty() + viewer.main.winfo_height()
    toolbar.push_current()
    original = viewer.ax.get_xlim()
    for operation in ['pan', 'zoom']:
        getattr(toolbar, operation)()
        assert operation in str(toolbar.mode).lower()
        getattr(toolbar, operation)()
    viewer.ax.set_xlim(original[0], sum(original) / 2)
    toolbar.push_current()
    toolbar.back()
    np.testing.assert_allclose(viewer.ax.get_xlim(), original)
    viewer.canvas.draw()
    # Exercise actual native drag events on the topmost twin axes.
    ax = viewer.fig.axes[-1]
    toolbar.pan()
    px, py = ax.transAxes.transform((.5, .5))
    for name, x in [('button_press_event', px), ('motion_notify_event', px + 30),
                     ('button_release_event', px + 30)]:
        event = MouseEvent(name, viewer.canvas, x, py, button=1,
                           buttons={1} if name == 'motion_notify_event' else None)
        viewer.canvas.callbacks.process(name, event)
    toolbar.pan()
    assert viewer.ax.get_xlim() != original
    for ax in viewer.fig.axes[1:]:
        assert ax.get_xlim() == viewer.ax.get_xlim()
    before_zoom = viewer.ax.get_xlim()
    toolbar.zoom()
    for name, fraction in [('button_press_event', .2), ('button_release_event', .8)]:
        zx, zy = ax.transAxes.transform((fraction, fraction))
        viewer.canvas.callbacks.process(name, MouseEvent(name, viewer.canvas, zx, zy, button=1))
    toolbar.zoom()
    assert np.diff(viewer.ax.get_xlim())[0] < np.diff(before_zoom)[0]
    viewer.savePlot(str(tmp_path / 'native.png'))
    assert (tmp_path / 'native.png').stat().st_size > 1000
    old = viewer.main
    dialog.no_preview = False
    dialog.mode.set(AXIS_MODES[0])
    dialog.apply()
    assert not old.winfo_exists()
    assert len(dialog.app.table.pf.fig.axes) == 1
    dialog.sample_mode.set(True)
    dialog.apply()
    np.testing.assert_equal(dialog.app.table.pf.fig.axes[0].lines[0].get_xdata(), [1, 2, 3, 4])
    dialog.ylist.selection_clear(0, tk.END)
    dialog.apply()
    assert '至少' in dialog.output[-1]
    assert len(dialog.app.table.pf.fig.axes) == 1


def test_menu_entry_reaches_real_dialog(tk_root, monkeypatch):
    from MiniJMP import Minijmp
    monkeypatch.setattr(Minijmp, 'start_logging', lambda self: None)
    previous = set(tk_root.winfo_children())
    app = Minijmp(parent=tk_root)
    try:
        menu = app.plots_menu['var']
        labels = {menu.entrycget(i, 'label').strip(): i for i in range(menu.index('end') + 1)
                  if menu.type(i) == 'command'}
        assert '线条图' in labels and '时间序列图' in labels
        menu.invoke(labels['时间序列图'])
        tk_root.update()
        tops = [w for w in tk_root.winfo_children() if isinstance(w, tk.Toplevel)]
        assert any(w.title() == '时间序列图' for w in tops)
    finally:
        tk_root.configure(menu='')
        for widget in set(tk_root.winfo_children()) - previous:
            widget.destroy()


def test_help_button_resolves_new_topic(dialog, monkeypatch):
    import help_link
    opened = []
    monkeypatch.setattr(help_link.webbrowser, 'open', lambda url, **kwargs: opened.append(url) or True)
    dialog.help()
    assert opened[0].endswith('#plots.time_series')


def test_production_path_has_no_aggregation_and_single_axes_implementation():
    tree = ast.parse(inspect.getsource(time_series))
    forbidden = {'groupby', 'resample', 'interpolate', 'ffill', 'bfill', 'lineplot', 'pointplot'}
    assert not [n for n in ast.walk(tree) if isinstance(n, ast.Attribute) and n.attr in forbidden]
    assert sum(isinstance(n, ast.Attribute) and n.attr == 'twinx' for n in ast.walk(tree)) == 1
    source = inspect.getsource(TimeSeriesDialog.apply)
    assert 'time_series_plot(' in source and 'make_working_df' not in source


def test_grouped_line_existing_behavior(figure):
    from sb_misc import line_plot
    ax = figure.add_subplot()
    line_plot(ax=ax, data=pd.DataFrame({'x': [1, 1, 2, 2], 'y': [2., 4., 6., 8.]}),
              x='x', y='y', errorbar=None)
    np.testing.assert_equal(ax.lines[0].get_xdata(), [1, 2])
    np.testing.assert_equal(ax.lines[0].get_ydata(), [3, 7])
