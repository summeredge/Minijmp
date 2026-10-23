"""REVIEW-014：来源销毁、非阻塞清理及迟到结果抑制。"""
from concurrent.futures import Future
from threading import Event
from unittest.mock import Mock

import pytest
import pandas as pd

from MiniJMP import Minijmp
from test_advanced_spc_dialog import make_dialog as make_spc
from test_capability_dialog import create as make_capability
from test_pca_dialog import make_pca
from test_regression_dialog import dispose, make_dialog as make_regression
from test_time_series_analysis_dialog import make_dialog as make_time_series
from quality_tools_dialog import QualityToolsDialog


@pytest.fixture
def tk_errors(tk_root, monkeypatch):
    errors = []
    monkeypatch.setattr(tk_root, 'report_callback_exception', lambda *args: errors.append(args))
    command = tk_root.register(errors.append)
    had_bgerror = bool(tk_root.tk.call('info', 'commands', 'bgerror'))
    if had_bgerror:
        tk_root.tk.call('rename', 'bgerror', 'review014_old_bgerror')
    tk_root.tk.call('proc', 'bgerror', 'message', command + ' $message')
    yield errors
    tk_root.tk.call('rename', 'bgerror', '')
    if had_bgerror:
        tk_root.tk.call('rename', 'review014_old_bgerror', 'bgerror')
    tk_root.deletecommand(command)


@pytest.mark.parametrize('factory,action', [
    (make_pca, 'delete'), (make_pca, 'replace'), (make_spc, 'delete'),
], ids=['pca-delete', 'pca-replace', 'spc-delete'])
def test_running_source_disposal(tk_root, monkeypatch, tk_errors, factory, action):
    dialog, app, source, *_ = factory(tk_root, monkeypatch)
    started, cancelled, release = Event(), Event(), Event()
    sentinel = object()

    def worker(*args, **kwargs):
        started.set()
        assert dialog.cancel_event.wait(5)
        cancelled.set()
        assert release.wait(5)
        return sentinel

    shutdown = Mock(wraps=dialog.executor.shutdown)
    monkeypatch.setattr(dialog.executor, 'shutdown', shutdown)
    monkeypatch.setattr(dialog, 'publish', Mock())
    future = None
    try:
        if factory is make_pca:
            dialog.start(worker, 'fit')
            dialog.redraw_id = dialog.main.after_idle(dialog.redraw)
        else:
            monkeypatch.setattr('advanced_spc.analyze_spc', worker)
            dialog.analyze()
        future = dialog.future
        assert started.wait(2)
        timers = [dialog.poll_id]
        if factory is make_pca:
            timers.append(dialog.redraw_id)
        if action == 'delete':
            name = next(name for name, table in app.sheets.items() if table is source)
            app.nb.select(app.sheetframes[name])
            monkeypatch.setattr('worksheets.messagebox.askyesno', lambda *a, **kw: True)
            assert app.deleteSheet()
        else:
            app._replace({'新项目': {'table': None}}, None)
        assert not dialog.main.winfo_exists()
        assert dialog.cancel_event.is_set() and cancelled.wait(2)
        assert not future.done(), '销毁不应等待仍在运行的工作线程'
        assert dialog.poll_id is None
        if factory is make_pca:
            assert dialog.redraw_id is None
        assert not set(timers).intersection(tk_root.tk.call('after', 'info'))
        dialog.close()
        shutdown.assert_called_once_with(wait=False, cancel_futures=True)
        release.set()
        assert future.result(timeout=5) is sentinel
        dialog.poll()
        if factory is make_pca:
            dialog.redraw()
        tk_root.update()
        dialog.publish.assert_not_called()
        dialog.error.assert_not_called()
        assert not tk_errors
    finally:
        dialog.cancel_event.set()
        release.set()
        dialog.close()
        if future is not None:
            future.result(timeout=5)
        dispose(app)


@pytest.mark.parametrize('kind', ['regression', 'capability', 'time-series', 'quality'])
def test_destroy_cleanup_is_local_and_idempotent(tk_root, monkeypatch, tk_errors, kind):
    factories = {'regression': make_regression, 'capability': make_capability,
                 'time-series': make_time_series}
    if kind == 'quality':
        monkeypatch.setattr(Minijmp, 'start_logging', lambda self: None)
        app = Minijmp(tk_root)
        data = pd.DataFrame({'类别': ['甲', '乙']})
        source = app.addSheet('质量来源', data)
        dialog = QualityToolsDialog(source, data, app)
    else:
        dialog, app, source, *_ = factories[kind](tk_root, monkeypatch)
    shutdown = Mock(wraps=dialog.executor.shutdown)
    monkeypatch.setattr(dialog.executor, 'shutdown', shutdown)
    pending = dialog.future = Future()
    timer = dialog.poll_id
    try:
        dialog.progress.destroy()
        assert not dialog._closed and not dialog.cancel_event.is_set()
        dialog.main.destroy()
        dialog.close()
        dialog.poll()
        assert dialog._closed and dialog.cancel_event.is_set() and pending.cancelled()
        assert dialog.poll_id is None
        assert timer not in tk_root.tk.call('after', 'info')
        shutdown.assert_called_once_with(wait=False, cancel_futures=True)
        tk_root.update()
        assert not tk_errors
    finally:
        dialog.close()
        dispose(app)
