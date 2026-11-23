import tkinter as tk

import numpy as np
import pandas as pd

from modified_table import MTable
from pandastable_local.plotting import PlotViewer


DATA = pd.DataFrame({'温度': [70., 72., 71., 75.],
                     '压力': [2.0, 2.2, 2.1, 2.3],
                     '流量': [10., 11., 12., 13.],
                     '工况': pd.Categorical(['A', 'A', 'B', 'B'])})


def make_viewer(tk_root, data=DATA):
    frame = tk.Frame(tk_root)
    frame.pack()
    table = MTable(frame, dataframe=data.copy(), showtoolbar=False, showstatusbar=False)
    table.show()
    table.multiplerowlist = [0, 1, 2, 3]
    table.multiplecollist = [0, 1]
    return table, frame, PlotViewer(table=table)


def scatter_offsets(viewer):
    return [collection.get_offsets().data.tolist()
            for collection in viewer.ax.collections]


def test_roles_ignore_source_column_order_and_keep_categorical_groups(tk_root):
    reordered = DATA[['工况', '流量', '压力', '温度']]
    table, frame, viewer = make_viewer(tk_root, reordered)
    try:
        original = table.model.df.copy(deep=True)
        viewer.mplopts.tkvars['kind'].set('scatter')
        viewer.xcol, viewer.ycols = '流量', ['温度']
        assert viewer.plotRoles()
        assert viewer.ax.get_xlabel() == '流量'
        np.testing.assert_allclose(scatter_offsets(viewer)[0], DATA[['流量', '温度']].to_numpy())

        viewer.ycols = ['温度', '压力']
        viewer.groupcol = '工况'
        assert viewer.plotRoles()
        pairs = {(row[0], round(row[1], 2)) for collection in scatter_offsets(viewer)
                 for row in collection if np.isfinite(row).all()}
        expected = {(x, y) for x, y in DATA[['流量', '温度', '压力']].to_numpy()[:, :2]}
        expected |= {(x, y) for x, y in DATA[['流量', '温度', '压力']].to_numpy()[:, [0, 2]]}
        assert pairs == expected
        legend = [item.get_text() for item in viewer.ax.get_legend().get_texts()]
        assert '温度（A）' in legend and '压力（B）' in legend
        assert table.model.df['工况'].dtype.name == 'category'
        pd.testing.assert_frame_equal(table.model.df, original)
    finally:
        viewer.close()
        table.destroy()
        frame.destroy()


def test_roles_line_bar_area_and_index_fallback(tk_root):
    table, frame, viewer = make_viewer(tk_root)
    try:
        viewer.xcol, viewer.ycols, viewer.groupcol = '流量', ['温度', '压力'], '工况'
        for kind in ('line', 'bar', 'area'):
            viewer.mplopts.tkvars['kind'].set(kind)
            assert viewer.plotRoles()
            labels = [item.get_text() for item in viewer.ax.get_legend().get_texts()]
            assert labels == ['温度（A）', '温度（B）', '压力（A）', '压力（B）']
        viewer.groupcol = None
        viewer.mplopts.tkvars['kind'].set('line')
        assert viewer.plotRoles()
        assert len(viewer.ax.lines) == 2
        viewer.xcol = None
        assert viewer.plotRoles()
        assert len(viewer.ax.lines) == 2
    finally:
        viewer.close()
        table.destroy()
        frame.destroy()


def test_invalid_role_selection_warns_without_raising(tk_root):
    table, frame, viewer = make_viewer(tk_root)
    warnings = []
    viewer.showWarning = warnings.append
    try:
        viewer.mplopts.tkvars['kind'].set('scatter')
        viewer.xcol, viewer.ycols = None, ['温度']
        assert viewer.plotRoles() is False
        assert 'X 轴列' in warnings[-1]
        viewer.xcol, viewer.ycols = '流量', ['工况']
        assert viewer.plotRoles() is False
        assert '数值列' in warnings[-1]
        viewer.xcol, viewer.ycols = '流量', []
        assert viewer.plotRoles() is False
        assert 'Y 轴列' in warnings[-1]
        viewer.ycols = ['温度']
        viewer.xcol = '不存在'
        assert viewer.plotRoles() is False
        assert '重新选择' in warnings[-1]
        viewer.xcol, viewer.ycols = '流量', ['温度']
        viewer.mplopts.tkvars['kind'].set('pie')
        assert viewer.plotRoles() is False
    finally:
        viewer.close()
        table.destroy()
        frame.destroy()


def test_role_widgets_sync_and_apply_or_reload_selection(tk_root):
    table, frame, viewer = make_viewer(tk_root)
    try:
        assert viewer.nb.tab(viewer.nb.tabs()[0], 'text') == '数据配置'
        assert list(viewer.ylistbox.get(0, 'end')) == list(DATA.columns)
        viewer.mplopts.tkvars['kind'].set('pie')
        assert str(viewer.xcombo['state']) == 'disabled'
        viewer.mplopts.tkvars['kind'].set('scatter')
        viewer.xcombo.current(3)
        viewer.ylistbox.selection_set(0)
        viewer.xcombo.event_generate('<<ComboboxSelected>>')
        viewer.main.update()
        assert viewer.xcol == '流量' and viewer.ycols == ['温度']
        viewer.bycombo.current(4)
        viewer.bycombo.event_generate('<<ComboboxSelected>>')
        viewer.main.update()
        assert viewer.groupcol == '工况' and viewer.mplopts.tkvars['by'].get() == '工况'
        viewer.plotRoles()
        viewer.updatePlot()
        assert '列配置' in viewer.inputvar.get()
        assert viewer.ax.collections
        viewer.zoom()
        assert viewer._role_mode and 'X=流量' in viewer.inputvar.get()

        viewer.rangevar.set('选中行')
        table.multiplerowlist = [0, 1]
        viewer.mplopts.tkvars['kind'].set('line')
        viewer.plotRoles()
        assert len(viewer.data) == 2
        table.multiplecollist = [2]
        viewer.replot()
        assert len(viewer.data) == 2 and not viewer._role_mode
        assert '工作表选区' in viewer.inputvar.get()

        viewer._role_columns = list(DATA.columns)
        viewer._role_mode = True
        viewer.xcol, viewer.ycols, viewer.groupcol = '流量', ['温度'], '工况'
        table.model.df = table.model.df.rename(columns={'温度': '温度2'})
        viewer.updateData()
        assert viewer.ycols == [] and viewer.groupcol == '工况'
        assert '温度' in viewer.roledesc.cget('text')
        assert '温度2' in list(viewer.ylistbox.get(0, 'end'))
    finally:
        viewer.close()
        table.destroy()
        frame.destroy()


def test_empty_group_keeps_other_groups_and_all_empty_y_is_reported(tk_root):
    data = pd.DataFrame({'Y': [10., 20., np.nan, np.nan],
                         'G': pd.Categorical(['A', 'A', 'B', 'B'])})
    table, frame, viewer = make_viewer(tk_root, data)
    try:
        viewer.ycols, viewer.groupcol = ['Y'], 'G'
        viewer.mplopts.tkvars['kind'].set('line')
        built = viewer.roleData(table.model.df, 'line')
        assert list(built.columns) == ['Y（A）']
        np.testing.assert_array_equal(built['Y（A）'].dropna().to_numpy(), [10., 20.])
        assert built['Y（A）'].isna().sum() == 2
        assert viewer.plotRoles()
        assert [item.get_text() for item in viewer.ax.get_legend().get_texts()] == ['Y（A）']

        table.model.df['Y'] = np.nan
        warnings = []
        viewer.showWarning = warnings.append
        assert viewer.plotRoles() is False
        assert 'Y' in warnings[-1] and '没有可绘图的数值' in warnings[-1]
    finally:
        viewer.close()
        table.destroy()
        frame.destroy()


def test_numeric_and_string_column_names_stay_separate(tk_root):
    data = pd.DataFrame({1: [1., 2., 3.], '1': [10., 20., 30.],
                         'X': [0., 1., 2.]})
    table, frame, viewer = make_viewer(tk_root, data)
    try:
        viewer.mplopts.tkvars['kind'].set('line')
        viewer.xcol, viewer.ycols, viewer.groupcol = 'X', [1, '1'], None
        built = viewer.roleData(table.model.df, 'line')
        assert list(built.columns) == ['1', '1（2）']
        np.testing.assert_array_equal(built['1'].to_numpy(), data[1].to_numpy())
        np.testing.assert_array_equal(built['1（2）'].to_numpy(), data['1'].to_numpy())
        assert list(table.model.df.columns) == [1, '1', 'X']
        assert viewer.plotRoles()
        assert len(viewer.ax.lines) == 2
        np.testing.assert_array_equal(viewer.ax.lines[0].get_ydata(), data[1].to_numpy())
        np.testing.assert_array_equal(viewer.ax.lines[1].get_ydata(), data['1'].to_numpy())
    finally:
        viewer.close()
        table.destroy()
        frame.destroy()


def test_x_and_y_same_source_is_plotted_or_rejected_clearly(tk_root):
    table, frame, viewer = make_viewer(tk_root)
    warnings = []
    viewer.showWarning = warnings.append
    try:
        viewer.mplopts.tkvars['kind'].set('line')
        viewer.xcol, viewer.ycols = '流量', ['流量']
        built = viewer.roleData(table.model.df, 'line')
        np.testing.assert_array_equal(built.index.to_numpy(), DATA['流量'].to_numpy())
        np.testing.assert_array_equal(built['流量'].to_numpy(), DATA['流量'].to_numpy())
        assert viewer.plotRoles()
        np.testing.assert_array_equal(viewer.ax.lines[0].get_ydata(), DATA['流量'].to_numpy())

        viewer.mplopts.tkvars['kind'].set('scatter')
        assert viewer.plotRoles() is False
        assert '同一个源列' in warnings[-1]
        assert viewer.mplopts.tkvars['kind'].get() == 'scatter'
        # the previous role plot is kept so the user can just pick another X
        assert viewer.ax.lines
    finally:
        viewer.close()
        table.destroy()
        frame.destroy()


def test_switching_kind_or_3d_leaves_role_mode(tk_root):
    table, frame, viewer = make_viewer(tk_root)
    try:
        viewer.mplopts.tkvars['kind'].set('line')
        viewer.xcol, viewer.ycols = '流量', ['温度']
        assert viewer.plotRoles() and viewer._role_mode
        viewer.mplopts.tkvars['kind'].set('pie')
        viewer.updatePlot()
        assert viewer._role_mode is False
        assert '工作表选区' in viewer.inputvar.get()

        viewer.mplopts.tkvars['kind'].set('line')
        assert viewer.plotRoles() and viewer._role_mode
        viewer.mplopts.tkvars['kind'].set('histogram')
        viewer.plotCurrent()
        assert viewer._role_mode is False

        viewer.mplopts.tkvars['kind'].set('line')
        assert viewer.plotRoles() and viewer._role_mode
        viewer.mplopts.tkvars['kind'].set('pie')
        viewer.plot2D()
        assert viewer._role_mode is False

        viewer.mplopts.tkvars['kind'].set('line')
        assert viewer.plotRoles() and viewer._role_mode
        viewer.globalvars['3D plot'].set(True)
        viewer.setGlobalOption('3D plot')
        viewer.updatePlot()
        assert viewer._role_mode is False
        assert len(viewer.data.columns) >= 2

        viewer.globalvars['3D plot'].set(False)
        viewer.setGlobalOption('3D plot')
        viewer.mplopts.tkvars['kind'].set('line')
        assert viewer.plotRoles() and viewer._role_mode
    finally:
        viewer.close()
        table.destroy()
        frame.destroy()


def test_linked_formula_results_flow_into_replotted_roles(tk_root):
    data = pd.DataFrame({'X': [0., 1., 2.], '来源': [2., 3., 4.]})
    frame = tk.Frame(tk_root)
    frame.pack()
    table = MTable(frame, dataframe=data.copy(), showtoolbar=False, showstatusbar=False)
    table.show()
    table.define_formula('结果', 'C2 * 2', link=True)
    viewer = PlotViewer(table=table)
    viewer.mplopts.tkvars['kind'].set('line')
    viewer.xcol, viewer.ycols = 'X', ['结果']
    viewer.groupcol = None

    try:
        assert viewer.plotRoles()
        np.testing.assert_allclose(viewer.ax.lines[0].get_ydata(), [4., 6., 8.])

        table.formulas_auto = False
        table.drawCellEntry(0, 1)
        table.cellentryvar.set('5')
        table.handleCellEntry(0, 1)
        assert table.formulas['结果']['stale'] is True
        assert table.model.df['结果'].tolist() == [4., 6., 8.]
        viewer.updatePlot()
        np.testing.assert_allclose(viewer.ax.lines[0].get_ydata(), [4., 6., 8.])

        table.recalculate_formulas()
        viewer.updatePlot()
        np.testing.assert_allclose(viewer.ax.lines[0].get_ydata(), [10., 6., 8.])

        table.formulas_auto = True
        table.drawCellEntry(1, 1)
        table.cellentryvar.set('7')
        table.handleCellEntry(1, 1)
        viewer.updatePlot()
        np.testing.assert_allclose(viewer.ax.lines[0].get_ydata(), [10., 14., 8.])
        assert table.model.df['来源'].tolist() == [5., 7., 4.]
        assert table.model.df['结果'].tolist() == [10., 14., 8.]
    finally:
        viewer.close()
        table.destroy()
        frame.destroy()


def test_menu_preview_updates_saves_and_cancels_on_its_source(tk_root, monkeypatch, tmp_path):
    from MiniJMP import Minijmp
    from test_regression_dialog import dispose

    monkeypatch.setattr(Minijmp, 'start_logging', lambda self: None)
    errors = []
    monkeypatch.setattr(tk_root, 'report_callback_exception', lambda *args: errors.append(args))
    app = Minijmp(parent=tk_root)
    source = app.addSheet('来源', DATA.copy())
    source.multiplecollist = [0, 1]
    source.multiplerowlist = [0, 1, 2, 3]
    previous = app.showPlotViewer()
    previous.fig.add_subplot().plot([10, 20], [30, 40])
    try:
        menu = app.plots_menu['var']
        entry = next(i for i in range(menu.index('end') + 1)
                     if menu.type(i) == 'command' and menu.entrycget(i, 'label').strip() == '通用绘图器')
        menu.invoke(entry)
        viewer = source._plot_preview
        assert viewer is not previous and source.pf is previous
        assert len(viewer.ax.lines) == 2
        viewer.kindcombo.current(viewer.mplopts.kinds.index('scatter'))
        viewer.kindcombo.event_generate('<<ComboboxSelected>>')
        viewer.xcombo.current(3)
        viewer.ylistbox.selection_set(0)
        viewer.xcombo.event_generate('<<ComboboxSelected>>')
        viewer.main.update()
        np.testing.assert_allclose(scatter_offsets(viewer)[0], DATA[['流量', '温度']])
        viewer.ylistbox.selection_clear(0, 'end')
        viewer.ylistbox.selection_set(1)
        viewer.ylistbox.event_generate('<<ListboxSelect>>')
        viewer.main.update()
        np.testing.assert_allclose(scatter_offsets(viewer)[0], DATA[['流量', '压力']])
        assert not viewer.save_button.instate(['disabled'])

        other = app.addSheet('其他', pd.DataFrame({'温度': [999.], '流量': [1000.]}))
        assert app.getCurrentTable() is other
        viewer.mplopts.tkvars['kind'].set('histogram')
        viewer.mplopts.tkvars['bins'].set(7)
        viewer.main.update()
        assert viewer.table is source
        assert len(viewer.ax.patches) == 7
        viewer.savePlot(str(tmp_path / 'preview.png'))
        assert (tmp_path / 'preview.png').stat().st_size > 1000
        assert source.pf is previous and not app.plots and getattr(other, 'pf', None) is None
        viewer.close()
        assert source.pf is previous and source._plot_preview is None and not app.plots

        app.nb.select(app.sheetframes['来源'])
        app._sheet_changed()
        app.plot_selected()
        viewer = source._plot_preview
        app.nb.select(app.sheetframes['其他'])
        app._sheet_changed()
        viewer.confirm_button.invoke()
        assert source.pf is viewer and source._plot_preview is None and getattr(other, 'pf', None) is None
        assert not previous.main.winfo_exists()
        assert next(iter(app.plots)).startswith('来源 ')
        archived = next(iter(app.plots.values()))
        assert any(list(line.get_ydata()) == [30, 40] for ax in archived.axes for line in ax.lines)
        viewer.main.destroy()
        assert source.pf is None
        assert not errors
    finally:
        dispose(app)


def test_preview_reports_invalid_roles_and_removes_pending_update(tk_root):
    data = pd.DataFrame({'X': [1., np.nan], 'Y': [np.nan, 2.], '标签': ['a', 'b']})
    table, frame, viewer = make_viewer(tk_root, data)
    try:
        table.multiplecollist = [0, 1]
        table.multiplerowlist = [0, 1]
        viewer.startPreview(lambda pending: None, '来源')
        assert '缺失值' in viewer.inputvar.get()
        viewer.mplopts.tkvars['kind'].set('scatter')
        viewer.xcombo.current(1)
        viewer.ylistbox.selection_set(1)
        viewer.xcombo.event_generate('<<ComboboxSelected>>')
        viewer.main.update()
        assert '成对' in viewer.preview_error.get()
        assert viewer.confirm_button.instate(['disabled'])
        assert viewer.save_button.instate(['disabled'])

        viewer.ylistbox.selection_clear(0, 'end')
        viewer.ylistbox.selection_set(2)
        viewer.ylistbox.event_generate('<<ListboxSelect>>')
        viewer.main.update()
        assert '数值列' in viewer.preview_error.get()

        viewer.mplopts.tkvars['kind'].set('line')
        assert viewer._preview_after is not None
        viewer.main.destroy()
        tk_root.update()
        assert viewer._preview_after is None
        assert table._plot_preview is None
    finally:
        viewer.close()
        table.destroy()
        frame.destroy()


def test_general_plotly_data_and_histogram_edges():
    import pytest
    from plots import general_plotly_figure
    pytest.importorskip('plotly')

    data = pd.DataFrame({'Y': [1., np.nan, 3., 4.], 'Z': [2., 4., 6., np.nan]},
                        index=pd.Index([30, 10, 20, 30], name='X'))
    options = dict(bins=2, legend=True, grid=True, title='标题', xlabel='', ylabel='')
    line = general_plotly_figure(data, 'line', **options)
    assert list(line.data[0].x) == [30, 10, 20, 30]
    np.testing.assert_allclose(line.data[0].y, [1, np.nan, 3, 4])
    assert not line.data[0].connectgaps and line.layout.xaxis.title.text == 'X'
    bar = general_plotly_figure(data, 'bar', **options)
    assert list(bar.layout.xaxis.ticktext) == ['30', '10', '20', '30']
    assert list(bar.data[0].x) == [0, 1, 2, 3]
    assert list(bar.data[0].y) == [1, 0, 3, 4]
    scatter = general_plotly_figure(data.reset_index(), 'scatter', **options)
    assert [list(trace.y) for trace in scatter.data] == [[1, 3, 4], [2, 4, 6]]
    assert list(scatter.data[0].x) == [30, 20, 30]
    hist = general_plotly_figure(data, 'histogram', **options)
    assert [list(trace.y) for trace in hist.data] == [[2, 1], [1, 2]]
    assert list(hist.data[0].width) == [2.5, 2.5]
    assert hist.layout.yaxis.title.text == '频数' and hist.layout.showlegend
    assert hist.layout.title.text == '标题' and hist.layout.yaxis.showgrid


def test_general_plotly_live_webview_and_exports(tk_root, monkeypatch, tmp_path):
    import json
    import sys
    import time
    from tkinter import filedialog, messagebox

    import pytest
    from PIL import Image
    from MiniJMP import Minijmp
    from test_regression_dialog import dispose

    if sys.platform != 'win32':
        pytest.skip('原生验证需要 Windows WebView2')
    pytest.importorskip('plotly')
    pytest.importorskip('tkwry')
    monkeypatch.setattr(Minijmp, 'start_logging', lambda self: None)
    errors = []
    monkeypatch.setattr(messagebox, 'showerror', lambda *args, **kw: errors.append(args))
    monkeypatch.setattr(tk_root, 'report_callback_exception', lambda *args: errors.append(args))
    app = Minijmp(parent=tk_root)
    source = app.addSheet('Plotly 来源', DATA.copy())
    original = source.model.df.copy()
    source.multiplerowlist = list(range(len(DATA)))
    source.multiplecollist = [0, 1]
    previous = app.showPlotViewer()
    previous.fig.add_subplot().plot([1, 2], [3, 4])

    def wait_until(condition):
        end = time.monotonic() + 18
        while not condition() and not errors and time.monotonic() < end:
            tk_root.update()
            time.sleep(.02)
        assert not errors, errors
        assert condition()

    def js(browser, expression):
        result = []
        browser.webview.eval_js_with_callback(expression, result.append, on_error=errors.append)
        wait_until(lambda: result)
        return json.loads(result[0])

    try:
        app.plot_selected()
        viewer = source._plot_preview
        buttons = [widget for widget in viewer.engine_panel.winfo_children()
                   if widget.winfo_class() == 'TRadiobutton']
        assert [button.cget('text') for button in buttons] == ['Matplotlib', 'Plotly（试验）']
        assert viewer.engine.get() == 'Matplotlib'
        viewer.xcombo.current(3)
        viewer.ylistbox.selection_set(0)
        viewer.xcombo.event_generate('<<ComboboxSelected>>')
        for kind in ('line', 'scatter', 'bar', 'histogram'):
            viewer.mplopts.tkvars['kind'].set(kind)
            tk_root.update()
            assert not viewer.confirm_button.instate(['disabled']), viewer.preview_error.get()
            assert viewer.ax.has_data()
        viewer.mplopts.tkvars['kind'].set('scatter')
        buttons[1].invoke()
        tk_root.update()
        browser = viewer.plotly_viewer
        assert browser is not None, viewer.preview_error.get()
        wait_until(lambda: browser._live_ready)
        assert browser.main.winfo_viewable()
        assert viewer.confirm_button.instate(['disabled'])
        assert js(browser, "document.querySelector('.js-plotly-plot').data[0].x") == [10, 11, 12, 13]

        app.addSheet('其他来源', pd.DataFrame({'压力': [999.]}))
        viewer.ylistbox.selection_clear(0, 'end')
        viewer.ylistbox.selection_set(1)
        viewer.ylistbox.event_generate('<<ListboxSelect>>')
        viewer.labelopts.tkvars['title'].set('实时压力')
        tk_root.update()
        assert viewer.plotly_viewer is browser
        assert viewer.table is source
        for kind, expected in [('line', 'scatter'), ('bar', 'bar'), ('histogram', 'bar')]:
            viewer.mplopts.tkvars['kind'].set(kind)
            viewer.mplopts.tkvars['bins'].set(3)
            tk_root.update()
            assert viewer.plotly_viewer is browser
            graph = "document.querySelector('.js-plotly-plot')"
            assert js(browser, f"[{graph}.data[0].type, {graph}.data[0].name, {graph}.layout.title.text]") == [
                expected, '压力', '实时压力']
        assert js(browser, f"{graph}.data[0].y") == [1, 1, 2]

        for filename in ('preview.html', 'preview.png'):
            output = tmp_path / filename
            monkeypatch.setattr(filedialog, 'asksaveasfilename', lambda **kwargs: str(output))
            browser.export()
            wait_until(output.is_file)
        assert 'Plotly.newPlot' in (tmp_path / 'preview.html').read_text(encoding='utf-8')
        html = (tmp_path / 'preview.html').read_text(encoding='utf-8')
        assert json.dumps('实时压力') in html and '<script src=' not in html
        assert js(browser, f'{graph}._context.scrollZoom') is True
        with Image.open(tmp_path / 'preview.png') as image:
            assert image.width > 100
            image.verify()

        viewer.mplopts.tkvars['kind'].set('scatter')
        viewer.bycombo.current(4)
        viewer.bycombo.event_generate('<<ComboboxSelected>>')
        tk_root.update()
        assert js(browser, f"{graph}.data.map(trace => [trace.name, trace.x])") == [
            ['压力（A）', [10, 11]], ['压力（B）', [12, 13]]]
        viewer.bycombo.current(0)
        viewer.bycombo.event_generate('<<ComboboxSelected>>')
        viewer.mplopts.tkvars['kind'].set('boxplot')
        tk_root.update()
        assert viewer.engine.get() == 'Plotly（试验）'
        assert '使用 Matplotlib' in viewer.engine_message.get()
        assert not browser.main.winfo_exists() and browser.directory is None
        assert viewer.ax.has_data()
        viewer.mplopts.tkvars['kind'].set('line')
        tk_root.update()
        replacement = viewer.plotly_viewer
        assert replacement is not None and replacement is not browser
        buttons[0].invoke()
        tk_root.update()
        assert not replacement.main.winfo_exists()
        assert viewer.ycols == ['压力'] and viewer.xcol == '流量'
        assert viewer.ax.has_data() and not viewer.confirm_button.instate(['disabled'])

        buttons[1].invoke()
        tk_root.update()
        browser = viewer.plotly_viewer
        viewer.close()
        assert not browser.main.winfo_exists() and browser.directory is None
        assert source._plot_preview is None and source.pf is previous
        assert not app.plots
        pd.testing.assert_frame_equal(source.model.df, original)
        assert not errors
    finally:
        dispose(app)
