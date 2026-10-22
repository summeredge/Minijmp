from types import SimpleNamespace
from unittest.mock import Mock
from tkinter import TclError

import pandas as pd
import pytest

from dialog import Dialogs
from sheet_context import SheetApp


@pytest.mark.parametrize('tk_failure', [False, True])
def test_closed_source_blocks_reads_and_output(tk_root, tk_failure):
    import tkinter as tk

    source = tk.Frame(tk_root)
    app = SimpleNamespace(table=object(), print=Mock(), showPlotViewer=Mock())
    proxy = SheetApp(app, source)
    source.destroy()
    if tk_failure:
        source.winfo_exists = Mock(side_effect=TclError('application destroyed'))
    for action in (proxy.getCurrentTable, lambda: proxy.print('result'),
                   proxy.showPlotViewer):
        with pytest.raises(RuntimeError, match='来源工作表已关闭'):
            action()
    app.print.assert_not_called()
    app.showPlotViewer.assert_not_called()


def test_proxy_keeps_source_after_switch_and_forwards_output_options():
    source, other = object(), object()
    app = SimpleNamespace(table=source, print=Mock(), showPlotViewer=Mock(),
                          dialog_help_msg=Mock(return_value='help'))
    proxy = SheetApp(app, source)
    app.table = other
    assert proxy.table is source
    assert proxy.getCurrentTable() is source
    payload = object()
    assert proxy.print(payload, end='!') is app.print.return_value
    app.print.assert_called_once_with(payload, end='!', table=source)
    assert proxy.showPlotViewer(other, (3, 4), False) is app.showPlotViewer.return_value
    app.showPlotViewer.assert_called_once_with(
        parent=other, figsize=(3, 4), save_last=False, table=source, deferred=False)
    assert proxy.dialog_help_msg(key='test') == 'help'
    app.dialog_help_msg.assert_called_once_with(key='test')


@pytest.mark.parametrize('hook', ['absent', 'instance', 'class'])
def test_dialog_binds_only_explicit_sheet_hook(tk_root, monkeypatch, hook):
    class App:
        print = Mock()

        def sheet_app(self, table):
            return SheetApp(self, table)

    app = App() if hook == 'class' else Mock()
    source = tk_root
    bound = SheetApp(app, source)
    if hook == 'instance':
        app.sheet_app = Mock(return_value=bound)
    monkeypatch.setattr(Dialogs, 'add_window_help', lambda *args: None)
    monkeypatch.setattr(Dialogs, 'createWidgets', lambda *args: None, raising=False)
    dialog = Dialogs(source, df=pd.DataFrame({'x': [1.]}), app=app)
    try:
        if hook == 'class':
            assert isinstance(dialog.app, SheetApp)
            assert dialog.app.table is source
            app.table = object()
            dialog.app.print('source output')
            app.print.assert_called_once_with('source output', end='\n', table=source)
        elif hook == 'instance':
            assert dialog.app is bound
            app.sheet_app.assert_called_once_with(source)
        else:
            assert dialog.app is app
            assert 'sheet_app' not in app._mock_children
    finally:
        dialog.quit()
