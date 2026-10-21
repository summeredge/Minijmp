import tkinter as tk

import numpy as np
import pandas as pd

from modified_table import MTable
from pandastable_local.plotting import PlotViewer


def make_viewer(tk_root):
    frame = tk.Frame(tk_root)
    frame.pack()
    data = pd.DataFrame({'温度': [70., 72., 71., 75.],
                         '压力': [2.0, 2.2, 2.1, 2.3],
                         '批次': ['A', 'A', 'B', 'B']})
    table = MTable(frame, dataframe=data, showtoolbar=False, showstatusbar=False)
    table.show()
    table.multiplerowlist = [0, 1, 2]
    table.multiplecollist = [0, 1, 2]
    return table, PlotViewer(table=table)


def make_table(tk_root):
    frame = tk.Frame(tk_root)
    frame.pack()
    data = pd.DataFrame({'温度': [70., 72., 71., 75.],
                         '压力': [2.0, 2.2, 2.1, 2.3],
                         '批次': ['A', 'A', 'B', 'B']})
    table = MTable(frame, dataframe=data, showtoolbar=False, showstatusbar=False)
    table.show()
    table.multiplerowlist = [0, 1, 2]
    table.multiplecollist = [0, 1, 2]
    return table, frame


def test_selection_reload_and_apply_keep_distinct_data(tk_root):
    table, viewer = make_viewer(tk_root)
    try:
        viewer.replot()
        first = viewer.data.copy()
        assert first.shape == (3, 3)
        assert '3 行 × 3 列' in viewer.inputvar.get()
        table.multiplerowlist = [0, 1, 2, 3]
        table.multiplecollist = [0, 1]
        viewer.updatePlot()
        pd.testing.assert_frame_equal(viewer.data, first)
        assert '3 行 × 3 列' in viewer.inputvar.get()
        viewer.replot()
        assert viewer.data.shape == (4, 2)
        assert '4 行 × 2 列' in viewer.inputvar.get()
    finally:
        viewer.close()
        table.destroy()


def test_summary_truncates_columns_and_handles_empty(tk_root):
    table, viewer = make_viewer(tk_root)
    try:
        wide = pd.DataFrame(np.ones((2, 8)), columns=list('abcdefgh'))
        text = viewer.updateInputSummary(wide)
        assert text.startswith('当前绘图数据（工作表选区）：2 行 × 8 列｜')
        assert 'a、b、c、d、e、f 等 8 列' == text.split('｜', 1)[1]
        assert '0 行' in viewer.updateInputSummary(pd.DataFrame())
        assert '尚未绘图' in viewer.updateInputSummary()
    finally:
        viewer.close()
        table.destroy()


def test_options_toggle_and_close_restore_state(tk_root, tmp_path):
    table, viewer = make_viewer(tk_root)
    try:
        viewer.replot()
        viewer.main.update()
        assert viewer.nb.winfo_ismapped()
        viewer.toggle_options()
        assert not viewer.nb.winfo_ismapped()
        assert viewer.options_button.cget('text') == '显示参数区'
        viewer.toggle_options()
        viewer.main.update()
        assert viewer.nb.winfo_ismapped()
        assert viewer.options_button.cget('text') == '隐藏参数区'
        viewer.savePlot(str(tmp_path / 'plot.png'))
        assert (tmp_path / 'plot.png').stat().st_size > 1000
        viewer.close()
        assert table.pf is None
        assert not viewer.main.winfo_exists()
    finally:
        if table.pf is not None:
            viewer.close()
        table.destroy()


def test_help_anchor_and_plot_selected_callback_stay_compatible(tk_root):
    from types import SimpleNamespace
    from unittest.mock import Mock
    from MiniJMP import Minijmp
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    topics = json.loads((root / 'help/help-map.json').read_text(encoding='utf-8'))['topics']
    topic = next(item for item in topics if item['id'] == 'plots.plot_wizard')
    assert topic['title'] == '通用绘图器'
    assert topic['entry'] == 'MiniJMP.plot_selected'
    assert (root / 'help/pages/graphs.html').read_text(encoding='utf-8').count(
        'id="plots.plot_wizard"') == 1
    table = SimpleNamespace(pf=None)
    app = SimpleNamespace(table=table, _call=Mock(), addPlot=Mock())
    Minijmp.plot_selected(app)
    app._call.assert_called_once_with('plotSelected')


def test_showoptions_false_initializes_hidden_and_cycles(tk_root, tmp_path):
    table, frame = make_table(tk_root)
    viewer = PlotViewer(table=table, showoptions=False)
    try:
        assert viewer.nb.winfo_manager() == ''
        assert viewer.options_button.cget('text') == '显示参数区'
        assert viewer.inputvar.get().startswith('当前绘图数据：尚未绘图')
        viewer.replot()
        assert '3 行 × 3 列' in viewer.inputvar.get()
        viewer.savePlot(str(tmp_path / 'hidden-options.png'))
        assert (tmp_path / 'hidden-options.png').stat().st_size > 1000

        viewer.toggle_options()
        tk_root.update()
        assert viewer.nb.winfo_manager() == 'pack'
        assert viewer.options_button.cget('text') == '隐藏参数区'
        viewer.toggle_options()
        tk_root.update()
        assert viewer.nb.winfo_manager() == ''
        assert viewer.options_button.cget('text') == '显示参数区'
        viewer.toggle_options()
        tk_root.update()
        assert viewer.nb.winfo_manager() == 'pack'
        assert viewer.options_button.cget('text') == '隐藏参数区'

        viewer.close()
        assert table.pf is None
        assert not viewer.main.winfo_exists()
    finally:
        if table.pf is not None:
            viewer.close()
        table.destroy()
        frame.destroy()


def test_showoptions_true_initializes_visible(tk_root):
    table, frame = make_table(tk_root)
    viewer = PlotViewer(table=table, showoptions=True)
    try:
        assert viewer.nb.winfo_manager() == 'pack'
        assert viewer.options_button.cget('text') == '隐藏参数区'
        assert viewer.inputvar.get().startswith('当前绘图数据：尚未绘图')
        viewer.toggle_options()
        tk_root.update()
        assert viewer.nb.winfo_manager() == ''
        assert viewer.options_button.cget('text') == '显示参数区'
        viewer.toggle_options()
        tk_root.update()
        assert viewer.nb.winfo_manager() == 'pack'
        assert viewer.options_button.cget('text') == '隐藏参数区'
    finally:
        viewer.close()
        table.destroy()
        frame.destroy()
