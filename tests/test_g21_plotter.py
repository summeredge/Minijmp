import tkinter as tk
import gc
import weakref
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
import matplotlib as mpl
from matplotlib.backend_bases import MouseEvent, PickEvent, KeyEvent

from modified_table import MTable
from pandastable_local.plotting import PlotViewer


def test_plot_options_do_not_change_process_save_dpi(monkeypatch):
    dpi = mpl.rcParams['savefig.dpi']
    monkeypatch.setitem(mpl.rcParams, 'savefig.dpi', dpi)
    options = SimpleNamespace(applyOptions=lambda: None)
    viewer = SimpleNamespace(globalopts={'dpi': 80}, mplopts=options, mplopts3d=options,
                             labelopts=options, styleopts=options)

    PlotViewer.applyPlotoptions(viewer)

    assert mpl.rcParams['savefig.dpi'] == dpi


@pytest.mark.parametrize('showoptions', [True, False])
def test_general_viewer_drag_handler_lifecycle(tk_root, tmp_path, monkeypatch, showoptions):
    from pandastable_local.handlers import DragHandler

    released = []
    errors = []
    original_release = DragHandler.on_release_event

    def release(handler, event):
        released.append(event.name)
        return original_release(handler, event)

    monkeypatch.setattr(DragHandler, 'on_release_event', release)
    monkeypatch.setattr(tk_root, 'report_callback_exception', lambda *args: errors.append(args))
    table, frame = make_table(tk_root)
    viewer = PlotViewer(table=table, showoptions=showoptions)
    handler_ref = weakref.ref(viewer._drag_handler)
    canvas = viewer.canvas
    methods = {'pick_event': 'on_pick_event',
               'button_press_event': 'button_press_event',
               'button_release_event': 'on_release_event',
               'key_press_event': 'key_press_event'}

    def connections():
        return {event: [cid for cid, callback in canvas.callbacks.callbacks[event].items()
                        if getattr(callback(), '__self__', None) is handler_ref()
                        and getattr(callback(), '__func__', None) is getattr(DragHandler, method)]
                for event, method in methods.items()}

    try:
        gc.collect()
        assert handler_ref() is viewer._drag_handler
        initial = connections()
        assert all(len(ids) == 1 for ids in initial.values())
        viewer.main.geometry('900x720+20+20')
        viewer.replot()
        viewer.main.update()
        assert viewer.main.winfo_width() == 900
        assert viewer.main.winfo_height() == 720
        assert viewer.plotfr.winfo_height() >= 640
        for size in ('640x480', '1024x768', '900x720'):
            viewer.main.geometry(size)
            viewer.toggle_options()
            viewer.main.update()
            viewer.toggle_options()
            viewer.updatePlot()
            viewer.main.update()
            assert connections() == initial

        viewer.zoom()
        viewer.zoom(False)
        viewer.canvas.draw()
        viewer.savePlot(str(tmp_path / 'general-events.png'))
        assert (tmp_path / 'general-events.png').stat().st_size > 1000

        # Use the actual annotation factory so Matplotlib's draggable callbacks run too.
        viewer.labelopts.addTextBox(key='event-test')
        annotation = next(a for a in viewer.fig.axes[0].texts if a._id == 'event-test')
        before = annotation.xyann
        bbox = annotation.get_window_extent()
        x, y = (bbox.x0 + bbox.x1) / 2, (bbox.y0 + bbox.y1) / 2
        press = MouseEvent('button_press_event', canvas, x, y, button=1)
        canvas.callbacks.process('button_press_event', press)
        canvas.callbacks.process('pick_event', PickEvent('pick_event', canvas, press, annotation))
        assert viewer._drag_handler.selected is annotation
        canvas.callbacks.process('motion_notify_event', MouseEvent(
            'motion_notify_event', canvas, x + 25, y + 15, button=1))
        canvas.callbacks.process('button_release_event', MouseEvent(
            'button_release_event', canvas, x + 25, y + 15, button=1))
        assert released == ['button_release_event']
        assert viewer._drag_handler.dragged is None
        assert annotation.xyann != before
        assert 'xy' in viewer.labelopts.textboxes['event-test']
        canvas.callbacks.process('key_press_event', KeyEvent('key_press_event', canvas, key='delete'))
        assert not annotation.get_visible()
        assert 'event-test' not in viewer.labelopts.textboxes

        viewer.close()
        gc.collect()
        assert handler_ref() is None
        for event, ids in initial.items():
            assert all(cid not in canvas.callbacks.callbacks.get(event, {}) for cid in ids)
        canvas.callbacks.process('button_release_event', MouseEvent(
            'button_release_event', canvas, 10, 10, button=1))
        tk_root.update()
        assert released == ['button_release_event']
        assert not errors
        viewer = PlotViewer(table=table, showoptions=showoptions)
        viewer.replot()
        viewer.main.update()
        assert viewer._drag_handler is not None
    finally:
        if viewer.main.winfo_exists():
            viewer.close()
        table.destroy()
        frame.destroy()


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
