"""Exercise real Windows Tk windows, not mocked lift/focus calls."""
import tkinter as tk

import numpy as np
import pandas as pd
import pytest

from MiniJMP import Minijmp
from basic_plot_dialog import BasicPlotDialog
from stat_plot_dialog import StatPlotDialog
from time_series_dialog import TimeSeriesDialog
from sb_box_dialog import singleBoxDialog, multiBoxDialog
from sb_hist_dialog import singleHistoDialog, multiHistoDialog, xyHistoDialog
from sb_misc_dialog import countPlotDialog, linePlotDialog, dotPlotDialog
from dist_plot_dialog import displayProbDialog, displayProb2xDialog


@pytest.fixture
def app(tk_root, monkeypatch):
    monkeypatch.setattr(Minijmp, 'start_logging', lambda self: None)
    previous = set(tk_root.winfo_children())
    tk_root.deiconify()
    app = Minijmp(parent=tk_root)
    app.table.model.df = pd.DataFrame({
        'x': [1., 2., 3., 4., 5., 6.], 'y': [2., 4., 3., 7., 5., 8.],
        'group': ['a', 'a', 'a', 'b', 'b', 'b']})
    app.gui_errors = []
    monkeypatch.setattr('sbplot_dialog.messagebox.showerror',
                        lambda *a, **k: app.gui_errors.append(a))
    yield app
    tk_root.configure(menu='')
    for widget in set(tk_root.winfo_children()) - previous:
        widget.destroy()
    tk_root.withdraw()
    tk_root.update()


def make_dialog(app, cls=BasicPlotDialog, **kwargs):
    dialog = cls(app.table, df=app.table.model.df, app=app, **kwargs)
    dialog.main.update()
    return dialog


def select(dialog, widget='variables', last=0):
    getattr(dialog, widget).selection_set(0, last)


def assert_interactive(dialog, viewer):
    dialog.main.update()
    assert dialog.main.grab_current() is None
    assert dialog.main.winfo_viewable() and viewer.main.winfo_viewable()
    assert not dialog.main.attributes('-topmost')
    assert not viewer.main.attributes('-topmost')
    assert dialog.main.focus_get().winfo_toplevel() is viewer.main
    for window in (dialog.main, viewer.main):
        entry = tk.Entry(window)
        entry.place(x=2, y=2, width=70, height=22)
        window.update()
        entry.focus_force()
        window.update()
        assert window.focus_get() is entry
        assert entry.winfo_viewable()
        entry.event_generate('<KeyPress-a>')
        window.update()
        assert entry.get() == 'a'
        entry.destroy()


@pytest.mark.parametrize('kind', [
    'time', 'hist-single', 'hist-multi', 'hist-group', 'hist-xy',
    'box-single', 'box-multi', 'box-group', 'count', 'line', 'dot',
    'bar', 'scatter', 'stat', 'stat-interval', 'stat-probability',
    'prob', 'prob-compare'])
def test_plot_entries_release_modal_and_accept_input(app, kind, tmp_path):
    classes = {'time': TimeSeriesDialog, 'hist-single': singleHistoDialog,
               'hist-multi': multiHistoDialog, 'hist-group': multiHistoDialog,
               'hist-xy': xyHistoDialog, 'box-single': singleBoxDialog,
               'box-multi': singleBoxDialog, 'box-group': multiBoxDialog,
               'count': countPlotDialog, 'line': linePlotDialog,
               'dot': dotPlotDialog, 'bar': BasicPlotDialog,
               'scatter': BasicPlotDialog, 'stat': StatPlotDialog,
               'stat-interval': StatPlotDialog,
               'stat-probability': StatPlotDialog,
               'prob': displayProbDialog, 'prob-compare': displayProb2xDialog}
    options = ({'kind': {'scatter': 'scatter_matrix',
                         'stat-interval': 'interval',
                         'stat-probability': 'probability'}[kind]}
               if kind in ('scatter', 'stat-interval', 'stat-probability') else {})
    dialog = make_dialog(app, classes[kind], **options)
    if kind == 'time':
        select(dialog, 'ylist', 1)
        dialog.update_variables()
    elif kind in ('bar', 'scatter', 'stat', 'stat-interval', 'stat-probability'):
        select(dialog, last=1 if kind == 'scatter' else 0)
    elif kind in ('hist-multi', 'box-multi'):
        select(dialog, 'grpvar', 1)
    elif kind.startswith('prob'):
        for distribution in ([dialog.dist] if kind == 'prob' else [dialog.dist1, dialog.dist2]):
            for entry, value in zip(distribution.entries, ['0', '1']):
                entry['input'].set(value)
    else:
        dialog.xvar.set('x')
        if kind in ('hist-group', 'box-group', 'count'):
            dialog.grouping.set('group')
        if kind in ('hist-xy', 'line', 'dot'):
            dialog.yvar.set('y')
    assert dialog.main.grab_current() is dialog.main
    dialog.preview()
    assert not app.gui_errors
    viewer = app.table.pf
    assert viewer is not None and not dialog.no_preview
    assert any(ax.has_data() for ax in viewer.fig.axes)
    assert_interactive(dialog, viewer)
    viewer.savePlot(str(tmp_path / (kind + '.png')))
    assert (tmp_path / (kind + '.png')).stat().st_size > 1000
    dialog.quit()
    assert viewer.main.grab_current() is None
    assert viewer.main.winfo_exists()
    viewer.close()
    viewer.close()
    assert app.table.pf is None


def test_replot_history_close_recreate_and_native_destroy(app, monkeypatch):
    source = app.table
    old = app.showPlotViewer()
    old.fig.add_subplot().plot([1, 2], [3, 4])
    dialog = make_dialog(app)
    select(dialog)
    dialog.preview()
    first = source.pf
    assert not old.main.winfo_exists()
    assert len(app.plots) == 1
    assert next(iter(app.plots)).startswith(app.getCurrentSheet())
    dialog.preview()
    second = source.pf
    assert not first.main.winfo_exists() and second is not first
    assert len(app.plots) == 1
    closed = []
    monkeypatch.setattr('plots.plt.close', lambda figure: closed.append(figure))
    second.main.destroy()
    assert source.pf is None and second._drag_handler is None
    second.close()
    assert closed == [second.fig]
    dialog.preview()
    assert source.pf.main.winfo_exists()
    dialog.quit()
    dialog.preview()


def test_viewer_cleanup_releases_figure_once(app, monkeypatch):
    viewer = app.showPlotViewer()
    closed = []
    monkeypatch.setattr('plots.plt.close', lambda figure: closed.append(figure))
    viewer.close()
    viewer.close()
    assert closed == [viewer.fig]
    assert app.table.pf is None


def test_close_before_plotting_releases_modal(app):
    dialog = make_dialog(app)
    assert dialog.main.grab_current() is dialog.main
    dialog.main.destroy()
    assert app.main.grab_current() is None
    dialog.preview()
    assert getattr(app.table, 'pf', None) is None


def test_probability_text_only_keeps_modal_and_previous_plot(app):
    old = app.showPlotViewer()
    old.fig.add_subplot().plot([1, 2])
    dialog = make_dialog(app, displayProbDialog)
    for entry, value in zip(dialog.dist.entries, ['0', '1']):
        entry['input'].set(value)
    dialog.plot_out.set(False)
    dialog.preview()
    assert dialog.main.grab_current() is dialog.main
    assert dialog.no_preview
    assert app.table.pf is old and old.main.winfo_exists()
    assert not app.plots and not app.gui_errors
    dialog.quit()


def test_histogram_fit_failure_keeps_valid_preview(app, monkeypatch):
    dialog = make_dialog(app, singleHistoDialog)
    dialog.xvar.set('x')
    dialog.fit_dist.set(True)
    output = []
    monkeypatch.setattr(dialog.app, 'print', output.append)
    monkeypatch.setattr('sb_hist_dialog.compare_dist', lambda *a, **k: [])
    dialog.preview()
    assert app.table.pf is not None and not dialog.no_preview
    assert app.table.pf.ax.has_data()
    assert any('无法使用所选分布进行拟合' in line for line in output)
    assert dialog.main.grab_current() is None


@pytest.mark.parametrize('failure', ['missing', 'before-viewer', 'after-viewer',
                                     'draw', 'reported', 'destroyed'])
@pytest.mark.parametrize('already_plotted', [False, True])
def test_failed_plot_preserves_grab_focus_history_and_previous(app, monkeypatch,
                                                               failure, already_plotted):
    old = app.showPlotViewer()
    old.fig.add_subplot().plot([1, 2], [3, 4])
    dialog = make_dialog(app)
    if already_plotted:
        select(dialog)
        dialog.preview()
        old = app.table.pf
    dialog.main.focus_force()
    dialog.main.update()
    focused = dialog.main.focus_get()
    grab = dialog.main.grab_current()
    history = dict(app.plots)
    no_preview = dialog.no_preview
    pending = []

    def fail():
        if failure == 'before-viewer':
            raise ValueError('invalid data')
        viewer = dialog.showPlotViewer()
        pending.append(viewer)
        viewer.fig.add_subplot().plot([1, 2])
        if failure == 'draw':
            def fail_draw():
                raise ValueError('draw failed')
            monkeypatch.setattr(viewer.canvas, 'draw', fail_draw)
        elif failure == 'reported':
            dialog.error('failed after creating viewer')
        elif failure == 'destroyed':
            viewer.close()
        else:
            raise ValueError('plot failed')

    if failure == 'missing':
        dialog.variables.selection_clear(0, tk.END)
    else:
        monkeypatch.setattr(dialog, 'apply', fail)
    dialog.preview()
    dialog.main.update()
    assert app.table.pf is old and old.main.winfo_exists()
    assert dialog.no_preview == no_preview
    assert app.plots == history
    assert dialog.main.grab_current() is grab
    assert dialog.main.focus_get() is focused
    assert all(not viewer.main.winfo_exists() for viewer in pending)
    assert dialog._preview_viewer is None
    assert not app.gui_errors
    dialog.quit()


def test_source_sheet_isolation_history_and_deleted_source(app, monkeypatch):
    source = app.table
    dialog = make_dialog(app)
    select(dialog)
    other = app.addSheet('B', pd.DataFrame({'x': [99., 100.]}))
    other_viewer = app.showPlotViewer()
    other_viewer.fig.add_subplot().plot([99., 100.])
    dialog.preview()
    viewer = source.pf
    assert app.table is other and other.pf is other_viewer
    np.testing.assert_equal([p.get_height() for p in viewer.ax.patches], source.model.df.x.to_numpy())
    assert not app.plots
    second = BasicPlotDialog(source, df=source.model.df, app=app)
    select(second)
    second.preview()
    assert len(app.plots) == 1
    assert next(iter(app.plots)).startswith('工作表1 ')
    monkeypatch.setattr('worksheets.messagebox.askyesno', lambda *a, **k: True)
    app.nb.select(app.sheetframes['工作表1'])
    app.getCurrentTable()
    assert app.deleteSheet()
    second.preview()
    assert '来源工作表已关闭' in app.gui_errors[-1][1]
    assert other.pf is other_viewer and other_viewer.main.winfo_exists()
    dialog.quit()
    second.quit()


def test_child_viewer_replacement_and_sheet_deletion_cleanup(app, monkeypatch):
    source = app.table
    source.createChildTable(pd.DataFrame({'x': [1., 2.]}))
    child = source.child
    child_viewer = app.showPlotViewer(table=child, save_last=False)
    parent_viewer = app.showPlotViewer(table=source, save_last=False)
    assert child_viewer.main.winfo_exists()
    assert child.pf is child_viewer

    parent_viewer.close()
    child_viewer = app.showPlotViewer(table=child, save_last=False)
    other = app.addSheet('B', pd.DataFrame({'x': [3., 4.]}))
    other_viewer = app.showPlotViewer()
    monkeypatch.setattr('worksheets.messagebox.askyesno', lambda *a, **k: True)
    app.nb.select(app.sheetframes['工作表1'])
    app.getCurrentTable()
    assert app.deleteSheet()
    assert not child_viewer.main.winfo_exists()
    assert other.pf is other_viewer and other_viewer.main.winfo_exists()


@pytest.mark.parametrize('kind', ['regression', 'control'])
def test_ordinary_statistics_close_modal_before_plotting(app, kind):
    from fit_dialog import LinearFitDialog
    from ctrlchart_dialog import IMRDialog
    dialog = make_dialog(app, LinearFitDialog if kind == 'regression' else IMRDialog)
    dialog.xvar.set('x')
    if kind == 'regression':
        dialog.yvar.set('y')
    assert dialog.main.grab_current() is dialog.main
    dialog.ok()
    app.main.update()
    assert not dialog.main.winfo_exists()
    assert app.main.grab_current() is None
    assert app.table.pf.main.winfo_viewable()
    assert any(ax.has_data() for ax in app.table.pf.fig.axes)
