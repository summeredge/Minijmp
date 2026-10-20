import json
import subprocess
import threading
import time
from unittest.mock import Mock

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

import pi_reader
import pi_import
from pi_import import PIImportDialog, query_size
from test_csv_import import csv_app
from utilities import number_list


def pump(root, condition):
    deadline = time.monotonic() + 5
    while not condition() and time.monotonic() < deadline:
        root.update()
        time.sleep(.01)
    assert condition()


def open_menu(app, monkeypatch, action):
    def respond(window):
        assert isinstance(window, PIImportDialog)
        assert window.grab_current() == window
        action(window)
    monkeypatch.setattr(app.main, 'wait_window', respond)
    menu = app.file_menu['var']
    index = next(i for i in range(menu.index('end') + 1)
                 if menu.type(i) == 'command' and menu.entrycget(i, 'label').strip() in ('Import PI Data', '导入 PI 数据'))
    menu.invoke(index)


def frame():
    return pi_reader._read_reader_json({'columns': ['Timestamp', 'B', 'A'], 'data': [
        ['2026-10-20 01:00:00', 2, 'Bad Input'],
        ['2026-10-20 01:05:00', None, 4],
        ['2026-10-20 01:10:00', 6, 8]]})


def test_menu_import_updates_real_table_and_statistics(csv_app, monkeypatch, tmp_path):
    app, error = csv_app
    expected = frame().reset_index()
    app.table.filename = 'old.pickle'
    app.table.prevdf = app.table.model.df.copy()
    read = Mock(return_value=frame())
    monkeypatch.setattr(pi_reader, 'read_pi_data', read)

    def action(window):
        window.tags.insert('1.0', 'B\n b\nA\n')
        window.start.set('*-1h')
        window.interval.set('10m')
        window.import_button.invoke()
        pump(app.main, lambda: not window.winfo_exists())
    open_menu(app, monkeypatch, action)
    assert_frame_equal(app.table.model.df, expected)
    assert list(app.table.model.df.columns) == ['Timestamp', 'B', 'A']
    assert app.table.colheader.model is app.table.model
    assert app.table.filename is None and app.table.prevdf is None
    assert app.main.title() == 'Untitled - Minijmp'
    assert number_list(app.table.model.df['B']) == [2, 6]
    assert number_list(app.table.model.df['A']) == [4, 8]
    assert read.call_args.args == (['B', 'A'], '*-1h', '*', '10m')
    filename = tmp_path / 'import.pickle'
    app.table.model.save(filename)
    assert_frame_equal(pd.read_pickle(filename), expected)
    error.assert_not_called()


@pytest.mark.parametrize('failure', ['error', 'timeout', 'empty', 'cancel', 'missing'])
def test_failed_or_canceled_query_preserves_sheet(csv_app, monkeypatch, failure):
    app, error = csv_app
    old = pd.DataFrame({'original': [42]})
    from pandastable_local.data import TableModel
    app.table.updateModel(TableModel(old.copy()))
    app.table.filename = 'old.pickle'
    app.table.prevdf = old.copy()
    app.update_title()
    started, finish = threading.Event(), threading.Event()

    def read(*args, **kwargs):
        started.set()
        if failure == 'cancel':
            assert finish.wait(5)
            return frame()
        if failure == 'empty':
            return frame().iloc[:0]
        if failure == 'timeout':
            raise RuntimeError('PIReader 查询超时')
        raise RuntimeError('PI SDK unavailable / server connection failed / invalid Tag')

    if failure != 'missing':
        monkeypatch.setattr(pi_reader, 'read_pi_data', read)

    def action(window):
        window.exe.set('missing-PIReader.exe')
        window.config.set('missing-config.txt')
        window.tags.insert('1.0', 'A')
        window.query()
        if failure == 'cancel':
            pump(app.main, started.is_set)
            # The Tk thread remains responsive while a worker is blocked.
            window.cancel()
            finish.set()
        else:
            pump(app.main, lambda: not window.busy)
            assert window.df is None
            assert window.status_view.get('1.0', 'end-1c')
            window.cancel()
    open_menu(app, monkeypatch, action)
    app.main.update()
    assert_frame_equal(app.table.model.df, old)
    assert_frame_equal(app.table.prevdf, old)
    assert app.table.filename == 'old.pickle'
    assert app.main.title() == 'old.pickle - Minijmp'
    error.assert_not_called()


def test_search_selection_and_validation(tk_root, monkeypatch):
    window = PIImportDialog(tk_root)
    search = Mock(return_value={'tags': ['B', 'A'], 'count': 2, 'truncated': True, 'message': ''})
    monkeypatch.setattr(pi_reader, 'search_pi_tags', search)
    try:
        window.mask.set('FIC*')
        window.search_button.invoke()
        pump(tk_root, lambda: not window.busy)
        assert '截断' in window.status_view.get('1.0', 'end-1c')
        for item in window.results.get_children():
            window.results.item(item, values=('☑', window.results.item(item, 'values')[1]))
        window.tags.insert('1.0', 'b\n')
        window.add_tags()
        assert window.tags.get('1.0', 'end').strip().splitlines() == ['b', 'A']
        window.tags.delete('1.0', 'end')
        window.tags.insert('1.0', '\n'.join(f'T{i}' for i in range(21)))
        window.query()
        assert '20' in window.status_view.get('1.0', 'end-1c') and not window.busy
        assert search.call_args.args == ('FIC*',)
    finally:
        window.cancel()


def test_large_range_requires_confirmation(tk_root, monkeypatch):
    window = PIImportDialog(tk_root)
    ask = Mock(return_value=False)
    monkeypatch.setattr(pi_import.messagebox, 'askokcancel', ask)
    operation = Mock()
    monkeypatch.setattr(window, 'run', operation)
    try:
        window.tags.insert('1.0', 'A\nB')
        window.start.set('2020-01-01')
        window.end.set('2026-01-01')
        window.interval.set('1m')
        window.query()
        ask.assert_called_once()
        operation.assert_not_called()
        assert query_size(['A', 'B'], '*-1h', '*', '5m') == 26
        assert query_size(['A'], '*-1d', '*', '1h') == 25
        assert query_size(['A'], '*-1w', '*', '1h') is None
        with pytest.raises(ValueError):
            query_size(['A'], '*', '*-1h', '1m')
    finally:
        window.cancel()


def test_explicit_paths_and_values(monkeypatch, tmp_path):
    exe, config = tmp_path / 'PIReader.exe', tmp_path / 'config.txt'
    exe.touch()
    config.touch()
    monkeypatch.setenv('PI_CONFIG', 'wrong-config')
    monkeypatch.setenv('PI_READER_EXE', 'wrong-exe')
    response = {'columns': ['Timestamp', 'A'], 'data': [['2026-01-01', None]]}
    run = Mock(return_value=subprocess.CompletedProcess([], 0, json.dumps(response), ''))
    monkeypatch.setattr(pi_reader.subprocess, 'run', run)
    result = pi_reader.read_pi_data(['A'], '*-1d', '*', config_path=str(config), executable_path=str(exe))
    assert run.call_args.args[0][:3] == [str(exe.resolve()), '--config', str(config.resolve())]
    assert pd.isna(result.iloc[0, 0])


@pytest.mark.parametrize('payload', [None, {}, {'columns': ['A'], 'data': []},
    {'columns': ['Timestamp', 'A'], 'data': [[1]]},
    {'columns': ['Timestamp'], 'data': [['not a date']]}])
def test_invalid_protocol(payload):
    with pytest.raises((ValueError, TypeError)):
        pi_reader._read_reader_json(payload)


@pytest.mark.parametrize('tags,time_column', [
    (['Timestamp', 'A'], 'Timestamp (time 1)'),
    (['Timestamp', 'Timestamp (time 1)', 'A'], 'Timestamp (time 2)'),
])
def test_timestamp_tag_through_reader_and_real_menu(csv_app, monkeypatch, tmp_path,
                                                   tags, time_column):
    app, error = csv_app
    exe, config = tmp_path / 'PIReader.exe', tmp_path / 'config.txt'
    exe.touch()
    config.touch()
    rows = [[f'2026-10-20 01:0{i}:00', *([i + 1] * len(tags))] for i in range(2)]
    response = {'columns': ['Timestamp', *tags], 'data': rows}
    monkeypatch.setattr(pi_reader.subprocess, 'run', Mock(return_value=
        subprocess.CompletedProcess([], 0, json.dumps(response), '')))

    def action(window):
        window.exe.set(str(exe))
        window.config.set(str(config))
        window.tags.insert('1.0', '\n'.join(tags))
        window.import_button.invoke()
        pump(app.main, lambda: not window.winfo_exists())

    open_menu(app, monkeypatch, action)
    result = app.table.model.df
    assert result.columns.tolist() == [time_column, *tags]
    assert result.columns.is_unique
    assert result[time_column].tolist() == list(pd.to_datetime([row[0] for row in rows]))
    for tag in tags:
        assert number_list(result[tag]) == [1, 2]
    filename = tmp_path / 'timestamp-tag.pickle'
    app.table.model.save(filename)
    assert_frame_equal(pd.read_pickle(filename), result)
    error.assert_not_called()


def test_long_error_keeps_buttons_visible_and_details_scrollable(csv_app, monkeypatch):
    app, error = csv_app
    details = ('PI SDK unavailable / connection failed\n' * 100) + 'END OF ERROR'
    monkeypatch.setattr(pi_reader, 'read_pi_data', Mock(side_effect=RuntimeError(details)))
    old = app.table.model.df.copy(deep=True)
    app.main.deiconify()
    app.main.update()

    def action(window):
        window.update()
        initial_height = window.winfo_height()
        window.tags.insert('1.0', 'A')
        window.import_button.invoke()
        pump(app.main, lambda: not window.busy)
        window.update()
        assert window.winfo_height() == initial_height
        assert window.winfo_reqheight() <= initial_height
        assert window.status_view.get('1.0', 'end-1c') == '查询失败：' + details
        assert str(window.status_view.cget('state')) == 'disabled'
        assert window.import_button.winfo_rooty() + window.import_button.winfo_height() <= (
            window.winfo_rooty() + window.winfo_height())
        assert window.winfo_rooty() + window.winfo_height() <= window.winfo_screenheight()
        window.status_view.yview_moveto(1)
        window.update()
        assert window.status_view.yview()[0] > 0
        cancel = next(widget for widget in window.import_button.master.winfo_children()
                      if widget.winfo_class() == 'TButton' and widget.cget('text') == '取消')
        cancel.invoke()
        assert not window.winfo_exists()

    try:
        open_menu(app, monkeypatch, action)
    finally:
        app.main.withdraw()
    assert_frame_equal(app.table.model.df, old)
    error.assert_not_called()
