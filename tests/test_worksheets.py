"""Real Windows Tk/MTable workbook acceptance checks."""
import gzip
import pickle
from unittest.mock import Mock

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from test_csv_import import csv_app
from modified_table import MTable
import worksheets


@pytest.fixture
def workbook(csv_app, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr(worksheets.messagebox, 'askyesno', lambda *a, **k: True)
    monkeypatch.setattr(worksheets.messagebox, 'askyesnocancel', lambda *a, **k: False)
    return app, error


def test_independent_tables_history_names_and_last_delete(workbook):
    app, error = workbook
    first = app.table
    second = app.addSheet('二', pd.DataFrame({'x': [2., 3.]}))
    second.storeCurrent()
    second.model.df.iloc[0, 0] = 99.
    third = app.copySheet()
    assert all(isinstance(t, MTable) for t in app.sheets.values())
    assert len(app.nb.tabs()) == 3
    assert third.model.df is not second.model.df and third.prevdf is None
    third.model.df.iloc[0, 0] = 10.
    app.nb.select(app.sheetframes['二'])
    assert app.getCurrentTable() is app.table is second
    app.undo()
    assert second.model.df.iloc[0, 0] == 2.
    assert third.model.df.iloc[0, 0] == 10.
    assert first.prevdf is None
    assert app.renameSheet('重命名')
    assert list(app.sheets) == ['工作表1', '重命名', '二 副本']
    assert not app.renameSheet('二 副本')
    assert not app.renameSheet('坏/名称')
    error.reset_mock()
    for _ in range(3):
        assert app.deleteSheet()
    assert len(app.sheets) == len(app.nb.tabs()) == 1
    assert app.table is not first
    error.assert_not_called()


def test_roundtrip_nullable_order_active_width_and_filter(workbook, tmp_path):
    app, error = workbook
    frame = pd.DataFrame({'日期': pd.to_datetime(['2026-10-21', None]),
                          '整数': pd.array([1, None], dtype='Int64'),
                          '文本': pd.array(['中文', None], dtype='string'),
                          '数值': [float('nan'), 1.2345678901234567]})
    b = app.addSheet('B', frame.copy())
    app.addSheet('A', pd.DataFrame({'x': [3]}))
    app.nb.select(app.sheetframes['B'])
    b.columnwidths = {'整数': 143}
    b.floatprecision = 7
    # Saving must use the complete source without clearing the visible filter.
    b.dataframe = frame.copy()
    b.model.df = frame.iloc[[1]].copy()
    b.filtered = True
    target = tmp_path / '三张表.dexpl'
    assert app._save_project(target)
    assert b.filtered and len(b.model.df) == 1
    assert app.load_file(target)
    assert list(app.sheets) == ['工作表1', 'B', 'A']
    assert app.getCurrentSheet() == 'B'
    assert_frame_equal(app.table.model.df, frame)
    assert app.table.columnwidths == {'整数': 143}
    assert app.table.floatprecision == 7
    assert app.filename == str(target)
    error.assert_not_called()


def test_old_project_and_pickle(workbook, tmp_path):
    app, error = workbook
    df = pd.DataFrame({'x': pd.array([1, None], dtype='Int64')})
    legacy = tmp_path / '旧.dexpl'
    with gzip.open(legacy, 'wb') as stream:
        pickle.dump({'Z': {'table': df, 'meta': {'mplopts': object()}},
                     'A': {'table': df.copy()}}, stream)
    assert app.load_file(legacy)
    assert list(app.sheets) == ['Z', 'A']
    assert_frame_equal(app.table.model.df, df)
    single = tmp_path / '单表.pickle'
    df.to_pickle(single)
    assert app.load_file(single)
    assert app.filename is None and len(app.sheets) == 1
    assert_frame_equal(app.table.model.df, df)
    error.assert_not_called()


@pytest.mark.parametrize('problem', ['bad_data', 'bad_meta', 'bad_active', 'damaged', 'build_failure'])
def test_failed_load_rolls_back(workbook, tmp_path, monkeypatch, problem):
    app, error = workbook
    original = app.table
    names = list(app.sheets)
    target = tmp_path / 'bad.dexpl'
    data = {'first': {'table': pd.DataFrame({'x': [1]})},
            'second': {'table': pd.DataFrame({'x': [2]})}}
    if problem == 'bad_data':
        data['second']['table'] = [1]
    if problem == 'bad_meta':
        data['second']['meta'] = {'minijmp': 1, 'columnwidths': {'x': -1}}
    if problem == 'bad_active':
        data['meta'] = {'active': ['first']}
    with gzip.open(target, 'wb') as stream:
        pickle.dump(data, stream)
    if problem == 'damaged':
        target.write_bytes(b'invalid')
    if problem == 'build_failure':
        real = app._make_sheet
        count = []
        def fail(*args):
            count.append(1)
            if len(count) == 2:
                raise RuntimeError('simulated widget failure')
            return real(*args)
        monkeypatch.setattr(app, '_make_sheet', fail)
    assert not app.load_file(target)
    assert app.table is original and list(app.sheets) == names
    assert len(app.nb.tabs()) == 1
    error.assert_called_once()


def test_atomic_save_and_cancel(workbook, tmp_path, monkeypatch):
    app, error = workbook
    path = tmp_path / 'project.dexpl'
    path.write_bytes(b'original')
    monkeypatch.setattr(worksheets.os, 'replace', Mock(side_effect=OSError('denied')))
    assert not app._save_project(path)
    assert path.read_bytes() == b'original'
    assert list(tmp_path.iterdir()) == [path]
    assert app.filename is None
    error.reset_mock()
    app.addSheet('changed')
    monkeypatch.setattr(worksheets.messagebox, 'askyesnocancel', lambda *a, **k: None)
    assert not app.new_file()
    app.quit()
    assert app.main.winfo_exists() and len(app.sheets) == 2
    monkeypatch.setattr(worksheets.messagebox, 'askyesnocancel', lambda *a, **k: True)
    monkeypatch.setattr(worksheets.filedialog, 'asksaveasfilename', lambda **k: '')
    assert not app.new_file()
    assert len(app.sheets) == 2


@pytest.mark.parametrize('cancel', ['trust', 'unsaved'])
def test_open_cancel_preserves_project(workbook, tmp_path, monkeypatch, cancel):
    app, error = workbook
    original = app.table
    app.addSheet('尚未保存', pd.DataFrame({'x': [42]}))
    path = tmp_path / 'incoming.pickle'
    pd.DataFrame({'incoming': [0]}).to_pickle(path)
    if cancel == 'trust':
        monkeypatch.setattr(worksheets.messagebox, 'askyesno', lambda *a, **k: False)
    else:
        monkeypatch.setattr(worksheets.messagebox, 'askyesnocancel', lambda *a, **k: None)
    assert not app.load_file(path)
    assert list(app.sheets) == ['工作表1', '尚未保存']
    assert app.sheets['工作表1'] is original
    assert app.table.model.df.iloc[0, 0] == 42
    error.assert_not_called()


def test_excel_widget_failure_leaves_no_extra_tabs(workbook, tmp_path, monkeypatch):
    app, error = workbook
    original = app.table
    monkeypatch.setattr(worksheets.pd, 'read_excel', lambda *a, **k: {
        'one': pd.DataFrame({'x': [1]}), 'two': pd.DataFrame({'x': [2]})})
    make = app._make_sheet
    calls = []
    def fail_second(*args):
        calls.append(1)
        if len(calls) == 2:
            raise RuntimeError('widget allocation failure')
        return make(*args)
    monkeypatch.setattr(app, '_make_sheet', fail_second)
    assert not app.load_excel(tmp_path / 'book.xlsx')
    assert len(app.nb.tabs()) == len(app.sheets) == 1
    assert app.table is original
    error.assert_called_once()


def test_excel_multi_sheet_csv_preserve_existing(workbook, tmp_path):
    app, error = workbook
    old = app.table
    old.model.df = pd.DataFrame({'原始': [42]})
    path = tmp_path / 'book.xlsx'
    with pd.ExcelWriter(path) as writer:
        pd.DataFrame({'x': [1]}).to_excel(writer, sheet_name='工作表1', index=False)
        pd.DataFrame({'y': [2]}).to_excel(writer, sheet_name='two', index=False)
    assert app.load_excel(path)
    assert list(app.sheets) == ['工作表1', '工作表1 (2)', 'two']
    assert old.model.df.iloc[0, 0] == 42
    csv = tmp_path / 'two.csv'
    csv.write_text('name,value\nA,1\nB,2\n', encoding='utf-8')
    assert app.import_csv(filename=csv)
    assert app.getCurrentSheet() == 'two (2)'
    assert old.model.df.iloc[0, 0] == 42
    assert len(app.sheets) == 4
    error.assert_not_called()


def test_table_file_actions_and_keyboard_route(workbook, tmp_path):
    app, error = workbook
    first = app.table
    first.model.df = pd.DataFrame({'x': [1., 2.]})
    csv = tmp_path / 'import.csv'
    csv.write_text('name,value\nA,1\nB,2\n', encoding='utf-8')
    assert first.importCSV(filename=csv)
    assert len(app.sheets) == 2 and first.model.df.iloc[0, 0] == 1.
    active = app.table
    assert active.bind('<Return>') and first.bind('<Return>')
    assert active.bind('<Return>') != first.bind('<Return>')
    assert not app.main.bind_all('<Return>')
    assert not app.main.bind_all('<Tab>')
    app.main.deiconify()
    try:
        app.main.update()
        active.focus_force()
        active.event_generate('<KeyPress-Tab>')
        app.main.update()
        assert active.currentcol == 1 and first.currentcol == 0
        active.storeCurrent()
        active.model.df.iloc[0, 1] = 99
        active.event_generate('<Control-z>')
        app.main.update()
        assert active.model.df.iloc[0, 1] == 1
        assert first.model.df.iloc[0, 0] == 1.
    finally:
        app.main.withdraw()
    active.currentrow = 1
    active.currentcol = 0
    app.nb.select(app.sheetframes['工作表1'])
    assert app.table is first and first.currentrow == 0
    app.nb.select(app.sheetframes['import'])
    assert app.table.currentrow == 1
    error.assert_not_called()


def test_pending_cell_entry_is_saved_without_advancing_edit(workbook, tmp_path):
    app, error = workbook
    table = app.addSheet('编辑', pd.DataFrame({'x': [1., 2.]}))
    table.redraw()
    app.main.update()
    table.drawCellEntry(0, 0)
    table.cellentryvar.set('42')
    copied = app.copySheet()
    assert copied.model.df.iloc[0, 0] == 42.
    path = tmp_path / 'edited.dexpl'
    assert app._save_project(path)
    with gzip.open(path, 'rb') as stream:
        stored = pickle.load(stream)
    assert stored['编辑']['table'].iloc[0, 0] == 42.
    assert not table.cellentry.winfo_exists()
    error.assert_not_called()


def test_open_results_and_plot_cleanup(workbook):
    app, error = workbook
    a = app.table
    app.print('第一张表')
    viewer = app.showPlotViewer(save_last=False)
    app.addSheet('第二张', pd.DataFrame({'x': [2]}))
    app.print('第二张表')
    assert a.tOut is not app.table.tOut
    assert a.pf is viewer and getattr(app.table, 'pf', None) is None
    app.nb.select(app.sheetframes['工作表1'])
    app.deleteSheet()
    assert not viewer.main.winfo_exists()
    assert a.tOut is None and a.pf is None
    assert app.table.tOut is not None
    error.assert_not_called()


def test_archived_plots_keep_source_and_clear_with_project(workbook, monkeypatch):
    app, error = workbook
    first = app.table
    app.showPlotViewer(save_last=False)
    second = app.addSheet('第二张')
    app.showPlotViewer(save_last=False)
    monkeypatch.setattr('MiniJMP.time.strftime', lambda *a: '12:00:00')
    app.addPlot(table=first)
    app.addPlot(table=second)
    assert len(app.plots) == 2
    assert list(app.plots)[0].startswith('工作表1 ')
    assert list(app.plots)[1].startswith('第二张 ')
    assert app.new_file()
    assert not app.plots and len(app.sheets) == 1
    notice = Mock()
    monkeypatch.setattr(worksheets.messagebox, 'showinfo', notice)
    app.addPlot()
    notice.assert_called_once()
    error.assert_not_called()


def test_dialogs_keep_source_after_switch(workbook):
    from basic_dialogs import DescribeDialog
    from time_series_dialog import TimeSeriesDialog
    import numpy as np

    app, error = workbook
    source = app.addSheet('来源', pd.DataFrame({'时间': pd.date_range('2026-01-01', periods=3),
                                              'x': [1., 2., 3.]}))
    describe = DescribeDialog(source, df=source.model.df, app=app, title='描述性统计')
    trend = TimeSeriesDialog(source, df=source.model.df, app=app, title='时间序列图')
    try:
        app.addSheet('当前', pd.DataFrame({'x': [100., 200., 300.]}))
        describe.xvar.set('x')
        describe.apply()
        assert source.tOut is not None and app.table.tOut is None
        result = source.tOut.T.get('1.0', 'end')
        assert '2.000' in result
        trend.ylist.selection_set(0)
        trend.update_variables()
        trend.apply()
        source.pf.canvas.draw()
        np.testing.assert_array_equal(source.pf.fig.axes[0].lines[0].get_ydata(), [1., 2., 3.])
        assert getattr(app.table, 'pf', None) is None
        app.nb.select(app.sheetframes['来源'])
        app.deleteSheet()
        with pytest.raises(RuntimeError, match='来源工作表已关闭'):
            describe.app.print('不可输出')
    finally:
        describe.quit()
        trend.quit()
    error.assert_not_called()
