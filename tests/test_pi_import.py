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

_real_load_pi_paths = pi_import.load_pi_paths
_real_save_pi_paths = pi_import.save_pi_paths


@pytest.fixture(autouse=True)
def isolated_pi_settings(monkeypatch):
    """Keep GUI tests independent of the actual Windows user registry."""
    stored = {}
    monkeypatch.setattr(pi_import, 'load_pi_paths', lambda: dict(stored))
    monkeypatch.setattr(pi_import, 'save_pi_paths', lambda paths: stored.update(paths))
    return stored


def test_paths_browse_autosaves_and_reopens(tk_root, tmp_path, monkeypatch, isolated_pi_settings):
    exe = tmp_path / 'PIReader.exe'
    config = tmp_path / 'config.txt'
    exe.write_bytes(b'MZ')
    config.write_text('[test]', encoding='utf-8')
    choices = iter((exe.as_posix(), config.as_posix()))
    monkeypatch.setattr(pi_import.filedialog, 'askopenfilename', lambda **kw: next(choices))
    window = PIImportDialog(tk_root)
    try:
        window.browse(window.exe, '*.exe')
        window.browse(window.config, '*.txt')
        assert window.exe.get() == pi_import.normalize_pi_path(exe.as_posix())
        assert window.config.get() == pi_import.normalize_pi_path(config.as_posix())
        assert isolated_pi_settings == {
            'executable_path': window.exe.get(), 'config_path': window.config.get()}
        assert '自动保存' in window.status_view.get('1.0', 'end-1c')
    finally:
        window.cancel()

    reopened = PIImportDialog(tk_root)
    try:
        assert reopened.exe.get() == pi_import.normalize_pi_path(exe)
        assert reopened.config.get() == pi_import.normalize_pi_path(config)
        assert reopened.paths() == dict(
            executable_path=pi_import.normalize_pi_path(exe),
            config_path=pi_import.normalize_pi_path(config))
    finally:
        reopened.cancel()


def test_manual_paths_autosave_and_skip_missing_files(
        tk_root, tmp_path, isolated_pi_settings):
    exe, config = tmp_path / 'Reader New.exe', tmp_path / 'config.txt'
    exe.write_bytes(b'MZ')
    config.write_text('config', encoding='utf-8')
    window = PIImportDialog(tk_root)
    try:
        window.exe.set(exe.as_posix())
        window.config.set(config.as_posix())
        pump(tk_root, lambda: isolated_pi_settings.get('config_path') ==
             pi_import.normalize_pi_path(config))
        assert isolated_pi_settings['executable_path'] == pi_import.normalize_pi_path(exe)
        assert window.paths()['executable_path'] == pi_import.normalize_pi_path(exe)
        missing = tmp_path / 'missing.exe'
        window.exe.set(str(missing))
        window.save_current_paths()
        assert isolated_pi_settings['executable_path'] == pi_import.normalize_pi_path(exe)
        assert window.paths()['executable_path'] == pi_import.normalize_pi_path(missing)
    finally:
        window.cancel()
    reopened = PIImportDialog(tk_root)
    try:
        assert reopened.exe.get() == pi_import.normalize_pi_path(exe)
    finally:
        reopened.cancel()


@pytest.mark.skipif(pi_import.os.name != 'nt', reason='Windows path normalization')
@pytest.mark.parametrize('path', ['D:/xx/PIReader.exe', 'D:/xx\\PIReader.exe'])
def test_windows_pi_paths_use_native_separators(path):
    assert pi_import.normalize_pi_path(path) == r'D:\xx\PIReader.exe'


@pytest.mark.parametrize('subdir', [None, 'PIReader'])
def test_default_pi_paths_support_both_layouts(
        tk_root, tmp_path, monkeypatch, subdir, isolated_pi_settings):
    project = tmp_path / 'project'
    code_dir = project / 'code'
    code_dir.mkdir(parents=True)
    files_dir = project / subdir if subdir else project
    files_dir.mkdir(exist_ok=True)
    exe, config = files_dir / 'PIReader.exe', files_dir / 'config.txt'
    exe.touch()
    config.touch()
    monkeypatch.setattr(pi_import, '__file__', str(code_dir / 'pi_import.py'))
    monkeypatch.delenv('PI_READER_EXE', raising=False)
    monkeypatch.delenv('PI_CONFIG', raising=False)
    window = PIImportDialog(tk_root)
    try:
        assert window.exe.get() == pi_import.normalize_pi_path(exe)
        assert window.config.get() == pi_import.normalize_pi_path(config)
    finally:
        window.cancel()


def test_manual_entry_return_and_focus_out_save_immediately(
        tk_root, tmp_path, isolated_pi_settings):
    exe, config = tmp_path / 'PIReader.exe', tmp_path / 'config.txt'
    exe.touch()
    config.touch()
    root_was_withdrawn = tk_root.state() == 'withdrawn'
    if root_was_withdrawn:
        tk_root.deiconify()
        tk_root.update()
    window = PIImportDialog(tk_root)
    try:
        entries = [widget for widget in window.winfo_children()[0].winfo_children()
                   if isinstance(widget, pi_import.ttk.Entry)]
        exe_entry = next(widget for widget in entries
                         if widget.cget('textvariable') == str(window.exe))
        config_entry = next(widget for widget in entries
                            if widget.cget('textvariable') == str(window.config))
        window.exe.set(exe.as_posix())
        exe_entry.focus_force()
        tk_root.update()
        exe_entry.event_generate('<Return>', when='now')
        tk_root.update()
        assert isolated_pi_settings['executable_path'] == pi_import.normalize_pi_path(exe)
        window.config.set(config.as_posix())
        config_entry.event_generate('<FocusOut>', when='now')
        tk_root.update()
        assert isolated_pi_settings['config_path'] == pi_import.normalize_pi_path(config)
    finally:
        window.cancel()
        if root_was_withdrawn:
            tk_root.withdraw()


@pytest.mark.skipif(pi_import.os.name != 'nt', reason='Windows current-user registry')
def test_registry_pi_paths_round_trip_in_isolated_hkcu_key(monkeypatch):
    import uuid
    import winreg

    assert pi_import._PI_SETTINGS_KEY == r'Software\MiniJMP\PIImport'
    key_name = rf'Software\MiniJMP-PIImportTest-{uuid.uuid4().hex}'
    monkeypatch.setattr(pi_import, '_PI_SETTINGS_KEY', key_name)
    try:
        _real_save_pi_paths({
            'executable_path': 'D:/xx/PIReader.exe',
            'config_path': r'D:\xx\config.txt',
            'password': 'must not be stored',
        })
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_name) as key:
            names = {winreg.EnumValue(key, index)[0]
                     for index in range(winreg.QueryInfoKey(key)[1])}
        assert names == {'executable_path', 'config_path'}
        assert _real_load_pi_paths() == {
            'executable_path': r'D:\xx\PIReader.exe',
            'config_path': r'D:\xx\config.txt',
        }
    finally:
        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key_name)
        except FileNotFoundError:
            pass


def test_json_pi_paths_round_trip_in_isolated_file(tmp_path, monkeypatch):
    settings_file = tmp_path / 'pi-import-paths.json'
    monkeypatch.setattr(pi_import, '_pi_settings_file', lambda: settings_file)
    with monkeypatch.context() as isolated:
        isolated.setattr(pi_import.os, 'name', 'posix')
        _real_save_pi_paths({'executable_path': 'reader.exe', 'config_path': 'config.txt'})
        assert _real_load_pi_paths() == {
            'executable_path': pi_import.normalize_pi_path('reader.exe'),
            'config_path': pi_import.normalize_pi_path('config.txt'),
        }


def test_settings_read_failure_is_visible_and_does_not_block_dialog(
        tk_root, monkeypatch, isolated_pi_settings):
    monkeypatch.setattr(pi_import, 'load_pi_paths', Mock(side_effect=PermissionError('registry denied')))
    window = PIImportDialog(tk_root)
    try:
        assert '路径设置读取失败' in window.status_view.get('1.0', 'end-1c')
        paths = window.paths()
        assert set(paths) == {'config_path', 'executable_path'}
    finally:
        window.cancel()


def test_save_failure_does_not_block_query_with_manual_paths(
        tk_root, tmp_path, monkeypatch, isolated_pi_settings):
    exe, config = tmp_path / 'PIReader.exe', tmp_path / 'config.txt'
    exe.touch()
    config.touch()
    monkeypatch.setattr(pi_import, 'save_pi_paths', Mock(side_effect=PermissionError('registry denied')))
    read = Mock(return_value=pd.DataFrame(
        {'A': [1]}, index=pd.to_datetime(['2026-01-01'])))
    monkeypatch.setattr(pi_reader, 'read_pi_data', read)
    window = PIImportDialog(tk_root)
    statuses = []
    set_status = window.set_status

    def record_status(message):
        statuses.append(message)
        set_status(message)

    monkeypatch.setattr(window, 'set_status', record_status)
    try:
        window.exe.set(exe.as_posix())
        window.config.set(config.as_posix())
        window.tags.insert('1.0', 'A')
        window.query()
        pump(tk_root, lambda: not window.winfo_exists())
        assert any('路径自动保存失败' in message for message in statuses)
        assert read.call_args.kwargs == {
            'config_path': pi_import.normalize_pi_path(config),
            'executable_path': pi_import.normalize_pi_path(exe),
        }
        assert window.df is not None
    finally:
        if window.winfo_exists():
            window.cancel()


def test_destroy_cancels_pending_path_autosave(
        tk_root, tmp_path, isolated_pi_settings):
    exe = tmp_path / 'PIReader.exe'
    exe.touch()
    window = PIImportDialog(tk_root)
    errors = []
    window.report_callback_exception = lambda *error: errors.append(error)
    window.exe.set(exe.as_posix())
    assert window._save_after is not None
    window.destroy()
    assert window._save_after is None
    window.exe.set('changed after destruction')
    assert window._save_after is None
    deadline = time.monotonic() + .75
    pump(tk_root, lambda: time.monotonic() >= deadline)
    assert isolated_pi_settings == {}
    assert errors == []


def pump(root, condition):
    deadline = time.monotonic() + 5
    while not condition() and time.monotonic() < deadline:
        root.update()
        time.sleep(.01)
    assert condition()


def open_menu(app, monkeypatch, action):
    def respond(window):
        assert isinstance(window, PIImportDialog)
        assert window.title() == '导入 PI 数据'
        assert window.grab_current() == window
        action(window)
    monkeypatch.setattr(app.main, 'wait_window', respond)
    menu = app.file_menu['var']
    index = next(i for i in range(menu.index('end') + 1)
                 if menu.type(i) == 'command' and menu.entrycget(i, 'label').strip() == '导入 PI 数据')
    menu.invoke(index)


def frame():
    return pi_reader._read_reader_json({'columns': ['Timestamp', 'B', 'A'], 'data': [
        ['2026-10-20 01:00:00', 2, 'Bad Input'],
        ['2026-10-20 01:05:00', None, 4],
        ['2026-10-20 01:10:00', 6, 8]]})


def test_pi_negative_measurements_with_status_gap_are_selectable(csv_app, monkeypatch):
    import numpy as np
    from time_series_dialog import TimeSeriesDialog

    app, error = csv_app
    tag = 'LX_NJADS_DCS_FCS0101_FIC450002'
    payload = {'columns': ['Timestamp', tag], 'data': [
        ['2026-10-20 15:53:32', '-2.74876'],
        ['2026-10-20 15:54:32', '-2.78499627'],
        ['2026-10-20 15:55:32', 'Bad Input'],
        ['2026-10-20 15:56:32', '-2.63170552'],
        ['2026-10-20 15:57:32', '-2.63646555'],
        ['2026-10-20 15:58:32', 'Shutdown'],
    ]}
    monkeypatch.setattr(pi_reader, 'read_pi_data',
                        lambda *a, **kw: pi_reader._read_reader_json(payload))

    def action(window):
        window.tags.insert('1.0', tag)
        window.query()
        pump(app.main, lambda: not window.winfo_exists())

    open_menu(app, monkeypatch, action)
    data = app.table.model.df
    original = data.copy(deep=True)
    assert data[tag].dtype == object and data[tag].iloc[2] == 'Bad Input'
    dialog = TimeSeriesDialog(app.table, df=data, app=app, title='时间序列图')
    try:
        assert dialog.xvar.get() == 'Timestamp'
        assert dialog.ylist.get(0, 'end') == (tag,)
        dialog.ylist.selection_set(0)
        dialog.update_variables()
        dialog.apply()
        viewer = app.table.pf
        viewer.canvas.draw()
        line = viewer.fig.axes[0].lines[0]
        np.testing.assert_equal(line.get_ydata(),
                                [-2.74876, -2.78499627, np.nan,
                                 -2.63170552, -2.63646555, np.nan])
        assert len(line.get_xdata()) == len(data) == 6
        assert_frame_equal(data, original)
        error.assert_not_called()
    finally:
        if app.table.pf is not None:
            app.table.pf.close()
        dialog.main.destroy()


def test_pi_strings_reach_real_y_candidates_and_plot(csv_app, monkeypatch):
    import numpy as np
    from time_series_dialog import TimeSeriesDialog

    app, error = csv_app
    payload = {'columns': ['Timestamp', 'Tag', 'Mixed', 'Precise'], 'data': [
        ['2026-10-20 01:10:00', '6.5', 'Bad Input', '0.123456789012345678901'],
        ['2026-10-20 01:00:00', '2', '4', '1'],
        ['2026-10-20 01:00:00', None, None, None],
        ['2026-10-20 01:05:00', '4e0', 'Shutdown', '2']]}
    monkeypatch.setattr(pi_reader, 'read_pi_data', lambda *a, **kw: pi_reader._read_reader_json(payload))

    def action(window):
        window.tags.insert('1.0', 'Tag\nMixed\nPrecise')
        window.query()
        pump(app.main, lambda: not window.winfo_exists())

    open_menu(app, monkeypatch, action)
    data = app.table.model.df
    assert data['Mixed'].tolist() == ['Bad Input', '4', None, 'Shutdown']
    assert data['Precise'].iloc[0] == '0.123456789012345678901'
    dialog = TimeSeriesDialog(app.table, df=data, app=app, title='时间序列图')
    try:
        assert dialog.xvar.get() == 'Timestamp'
        assert dialog.ylist.get(0, 'end') == ('Tag',)
        dialog.ylist.selection_set(0)
        dialog.update_variables()
        dialog.apply()
        viewer = app.table.pf
        viewer.canvas.draw()
        line = viewer.fig.axes[0].lines[0]
        np.testing.assert_equal(line.get_ydata(), [2., np.nan, 4., 6.5])
        np.testing.assert_array_equal(line.get_xdata(), pd.to_datetime([
            '2026-10-20 01:00:00', '2026-10-20 01:00:00',
            '2026-10-20 01:05:00', '2026-10-20 01:10:00']).to_numpy())
        assert len(line.get_xdata()) == len(data) == 4
        error.assert_not_called()
    finally:
        if app.table.pf is not None:
            app.table.pf.close()
        dialog.main.destroy()


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
    assert app.main.title() == f'未命名项目 — {app.getCurrentSheet()} - Minijmp'
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
    assert app.main.title() == f'未命名项目 — {app.getCurrentSheet()} - Minijmp'
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
