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
