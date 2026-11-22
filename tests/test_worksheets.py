"""Real Windows Tk/MTable workbook acceptance checks."""
import gzip
import json
import pickle
import zipfile
from unittest.mock import Mock

import pandas as pd
import numpy as np
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


def test_subset_condition_masks():
    from pandastable_local.dialogs import subset_row_mask

    frame = pd.DataFrame({
        '整数': pd.array([9007199254740993, 2, None, 3], dtype='Int64'),
        '文本': pd.Categorical(['甲', '乙', None, '甲']),
        '数值': [2.5, 10.0, float('nan'), 4.0],
    }, index=[42, 7, 42, 1])
    bounds = (2, '区间', '2.5', '4')
    text = (1, '=', '甲', '')
    missing = (0, '为空', '', '')
    assert subset_row_mask(frame, conditions=[bounds, text]).tolist() == [True, False, False, True]
    assert subset_row_mask(frame, conditions=[missing, text], match_all=False,
                           exclude=True).tolist() == [False, True, False, False]
    for symbol, expected in {
        '=': [False, False, False, False], '≠': [True, True, False, True],
        '>': [True, False, False, False], '≥': [True, False, False, False],
        '<': [False, True, False, True], '≤': [False, True, False, True],
    }.items():
        assert subset_row_mask(frame, conditions=[(0, symbol, '9007199254740992.9', '')]).tolist() == expected
    assert subset_row_mask(frame, conditions=[(1, '非空', '', '')]).tolist() == [True, True, False, True]
    with pytest.raises(ValueError, match='列类型'):
        subset_row_mask(frame, conditions=[(0, '=', '甲', '')])
    with pytest.raises(ValueError, match='下限不能大于上限'):
        subset_row_mask(frame, conditions=[(2, '区间', '4', '2')])


@pytest.mark.parametrize('exclude', [False, True])
def test_subset_row_positions(exclude):
    from pandastable_local.dialogs import subset_row_mask

    frame = pd.DataFrame({'列': [1, 2, 3, 4, 5]}, index=[10, 8, 10, 1, 0])
    assert subset_row_mask(frame, rows=' 4-5，2, 4 ', exclude=exclude).tolist() == [
        value != exclude for value in (False, True, False, True, True)]
    for entry in ('', '0', '4-2', '6', '1,,3', '1.5'):
        with pytest.raises(ValueError, match='行号'):
            subset_row_mask(frame, rows=entry)


@pytest.mark.parametrize('case', ['condition', 'doe', 'empty', 'cancel', 'invalid'])
def test_subset_menu_dialog_creates_independent_sheet(workbook, tmp_path, monkeypatch, case):
    from doe_dialog import CreateDOE
    from pandastable_local.dialogs import SubsetWorksheetDialog

    app, error = workbook
    menu = app.data_menu['var']
    commands = {menu.entrycget(i, 'label').strip(): i for i in range(menu.index('end') + 1)
                if menu.type(i) == 'command'}
    if case == 'doe':
        create = CreateDOE(app)
        create.create()
        source = app.table
        metadata = source.doe_metadata
        assert metadata
        expected = source.model.df.iloc[1:].copy()
    else:
        frame = pd.DataFrame({'n': pd.array([7, None, 8], dtype='Int64'),
                              'text': ['甲', '乙', '丙']}, index=[10, 2, 10])
        app.addSheet('原表 子集')
        source = app.addSheet('原表', frame)
        menu.invoke(commands['筛选行'])
        source.qframe.queryvar.set("text != '甲'")
        source.qframe.query()
        assert source.filtered
        assert_frame_equal(source.model.df, frame.iloc[[1, 2]])
        metadata = None
        expected = source.model.df.head(0 if case == 'empty' else 1).copy()
    original_visible = source.model.df.copy()
    original_full = app._full_frame(source).copy()
    original_filter = source.filtered
    original_query = getattr(source, 'qframe', None)
    original_names = list(app.sheets)
    default_name = app.getCurrentSheet() + ' 子集'
    info = Mock()
    monkeypatch.setattr(worksheets.messagebox, 'showinfo', info)

    class DrivenDialog(SubsetWorksheetDialog):
        def body(self, parent):
            entry = super().body(parent)
            self.after(0, self.drive)
            return entry

        def drive(self):
            try:
                assert self.name.get() == default_name
                if case in ('cancel', 'invalid', 'doe'):
                    self.mode.set('rows')
                    self._switch_mode()
                    self.rows.set('1' if case != 'invalid' else '0')
                    self.exclude.set(case == 'doe')
                    if case == 'doe':
                        self.name.set('自定义 DOE 子集')
                else:
                    _, op, first, _ = self.conditions[0]
                    if case == 'empty':
                        first.set('99')
                    else:
                        op.set('为空')
                if case == 'cancel':
                    self.cancel()
                    return
                if case != 'invalid':
                    self.preview_rows()
                    assert f'结果 {len(expected)} 行' in self.preview.get()
                self.ok()
            finally:
                if self.winfo_exists():
                    self.cancel()

    monkeypatch.setattr(worksheets, 'SubsetWorksheetDialog', DrivenDialog)
    menu.invoke(commands['子集化工作表'])
    assert_frame_equal(source.model.df, original_visible)
    assert_frame_equal(app._full_frame(source), original_full)
    assert source.filtered == original_filter and getattr(source, 'doe_metadata', None) is metadata
    assert getattr(source, 'qframe', None) is original_query
    if case in ('cancel', 'invalid'):
        assert list(app.sheets) == original_names and app.table is source
        assert error.call_count == (case == 'invalid')
        return

    name = '自定义 DOE 子集' if case == 'doe' else default_name + ' (2)'
    assert list(app.sheets) == [*original_names, name] and app.getCurrentSheet() == name
    assert_frame_equal(app.table.model.df, expected)
    assert app.table.prevdf is None and getattr(app.table, 'doe_metadata', None) is None
    assert info.call_count == (case == 'empty')
    if case == 'condition':
        app.table.model.df.iat[0, 0] = 123
        expected.iat[0, 0] = 123
        assert_frame_equal(source.model.df, original_visible)
    export = tmp_path / 'subset.csv'
    monkeypatch.setattr(worksheets.filedialog, 'asksaveasfilename', lambda **kw: str(export))
    app.export_sheet()
    exported = pd.read_csv(export, index_col=0)
    assert exported.shape == expected.shape and list(exported.columns) == list(expected.columns)
    target = tmp_path / 'subset.dexpl'
    assert app._save_project(target), error.call_args
    assert app.load_file(target)
    assert app.getCurrentSheet() == name
    assert_frame_equal(app.table.model.df, expected)
    assert getattr(app.table, 'doe_metadata', None) is None
    error.assert_not_called()


def test_split_worksheet_groups_by_position_and_first_appearance():
    from pandastable_local.dialogs import split_worksheet_groups

    frame = pd.DataFrame({
        '装置': pd.Categorical(['B', None, 'A', 'B', 'B'], categories=['A', 'B', '未出现']),
        '日期': pd.to_datetime(['2026-11-19', '2026-11-19', None, None, '2026-11-19']),
    }, index=[4, 4, 0, 8, 2])
    frame.columns = ['分类', '分类']
    namer = worksheets.Worksheets()._unique_name
    single = split_worksheet_groups(frame, [0], (), namer)
    assert [(name, positions.tolist()) for _, name, positions in single] == [
        ('B', [0, 3, 4]), ('缺失', [1]), ('A', [2])]
    multiple = split_worksheet_groups(frame, [0, 1], (), namer)
    assert [(name, positions.tolist()) for _, name, positions in multiple] == [
        ('B_2026-11-19 000000', [0, 4]), ('缺失_2026-11-19 000000', [1]),
        ('A_缺失', [2]), ('B_缺失', [3])]


def test_split_worksheet_names_use_existing_rules():
    from pandastable_local.dialogs import split_worksheet_groups

    long = '类' * 70
    frame = pd.DataFrame({'类别': ['A/B', 'A:B', long + '甲', long + '乙', '缺失', None, '/']})
    groups = split_worksheet_groups(frame, [0], ['AB', '缺失'], worksheets.Worksheets()._unique_name)
    assert [name for _, name, _ in groups] == [
        'AB (2)', 'AB (3)', long, f'{long} (2)', '缺失 (2)', '缺失 (3)', '工作表']


def test_project_category_codes_restore_ordered_labels_and_reject_invalid_position():
    labels = pd.date_range('2026-11-19', periods=3, tz='Asia/Shanghai')
    frame = pd.DataFrame({'日期类别': pd.Categorical.from_codes([1, -1], labels, ordered=True)})
    content, columns, attrs, metadata, nulls = worksheets._write_frame(frame)
    assert_frame_equal(worksheets._read_frame(content, columns, attrs, metadata, nulls), frame)
    metadata['minijmp_categories'][0][0] = 1
    with pytest.raises(ValueError, match='无效的分类列信息'):
        worksheets._read_frame(content, columns, attrs, metadata, nulls)


@pytest.mark.parametrize('case', ['create', 'doe', 'cancel', 'no_columns', 'empty', 'sheet_limit',
                                  'failed_creation'])
def test_split_worksheet_menu_dialog_preview_and_creation(workbook, tmp_path, monkeypatch, case):
    from doe_dialog import CreateDOE
    from pandastable_local.dialogs import SplitWorksheetDialog

    app, error = workbook
    menu = app.data_menu['var']
    commands = {menu.entrycget(i, 'label').strip(): i for i in range(menu.index('end') + 1)
                if menu.type(i) == 'command'}
    if case == 'doe':
        CreateDOE(app).create()
        source = app.table
        assert source.doe_metadata
        expected_frames = [source.model.df.iloc[[i]].copy() for i in range(len(source.model.df))]
    else:
        frame = pd.DataFrame({'装置': pd.Categorical(['隐藏', 'B', None, 'A', 'B']),
                              '班组': pd.array([0, 2, 2, 1, 2], dtype='Int64'),
                              '可见': [False, True, True, True, True]},
                             index=[9, 0, 5, 0, 2])
        app.addSheet('B_2')
        source = app.addSheet('源表', frame.iloc[:0].copy() if case == 'empty' else frame)
        if case != 'empty':
            menu.invoke(commands['筛选行'])
            source.qframe.queryvar.set('可见 == True')
            source.qframe.query()
            assert source.filtered
            assert_frame_equal(source.model.df, frame.iloc[1:])
        expected_frames = [frame.iloc[rows].copy() for rows in ([1, 4], [2], [3])]
    original_full = app._full_frame(source).copy()
    original_visible = source.model.df.copy()
    original_names = list(app.sheets)
    source_name = app.getCurrentSheet()
    filter_state = source.filtered, getattr(source, 'qframe', None)
    metadata = getattr(source, 'doe_metadata', None)
    preview = []

    if case == 'failed_creation':
        build = app._make_sheet
        monkeypatch.setattr(app, '_make_sheet', Mock(side_effect=[build(expected_frames[0]),
                                                                 RuntimeError('模拟建表失败')]))
    if case == 'sheet_limit':
        monkeypatch.setattr('pandastable_local.dialogs.MAX_SHEETS', len(original_names) + 1)

    class DrivenDialog(SplitWorksheetDialog):
        def body(self, parent):
            focus = super().body(parent)
            self.after(0, self.drive)
            return focus

        def drive(self):
            try:
                if case != 'no_columns':
                    self.columns.selection_set(0, 0 if case == 'doe' else 1)
                if case not in ('no_columns', 'empty', 'sheet_limit'):
                    self.preview_sheets()
                    preview.extend(self.preview.item(item, 'values') for item in self.preview.get_children())
                    assert f'当前可见 {len(original_visible)} 行，预计生成 {len(expected_frames)} 张工作表' == self.summary.get()
                    assert list(app.sheets) == original_names
                if case != 'cancel':
                    self.ok()
            finally:
                if self.winfo_exists():
                    self.cancel()

    monkeypatch.setattr(worksheets, 'SplitWorksheetDialog', DrivenDialog)
    menu.invoke(commands['按类别拆分工作表'])
    assert_frame_equal(source.model.df, original_visible)
    assert_frame_equal(app._full_frame(source), original_full)
    assert (source.filtered, getattr(source, 'qframe', None)) == filter_state
    assert getattr(source, 'doe_metadata', None) is metadata
    if case not in ('create', 'doe'):
        assert list(app.sheets) == original_names and app.getCurrentSheet() == source_name
        assert error.call_count == (case != 'cancel')
        return

    names = list(app.sheets)[len(original_names):]
    assert len(names) == len(expected_frames) and app.getCurrentSheet() == names[0]
    if case == 'create':
        assert names == ['B_2 (2)', '缺失_2', 'A_1']
    assert preview == [(name, str(len(frame))) for name, frame in zip(names, expected_frames)]
    for name, expected in zip(names, expected_frames):
        assert_frame_equal(app.sheets[name].model.df, expected)
        assert getattr(app.sheets[name], 'doe_metadata', None) is None
    if case == 'create':
        app.table.model.df.iat[0, 1] = 123
        expected_frames[0].iat[0, 1] = 123
        assert_frame_equal(source.model.df, original_visible)
        export = tmp_path / 'split.csv'
        monkeypatch.setattr(worksheets.filedialog, 'asksaveasfilename', lambda **kw: str(export))
        app.export_sheet()
        assert pd.read_csv(export, index_col=0)['班组'].tolist() == [123, 2]
    target = tmp_path / 'split.dexpl'
    assert app._save_project(target), error.call_args
    assert app.load_file(target)
    assert app.getCurrentSheet() == names[0]
    for name, expected in zip(names, expected_frames):
        assert_frame_equal(app.sheets[name].model.df, expected)
        assert getattr(app.sheets[name], 'doe_metadata', None) is None
    error.assert_not_called()


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
    assert app._save_project(target), error.call_args
    assert b.filtered and len(b.model.df) == 1
    assert app.load_file(target)
    assert list(app.sheets) == ['工作表1', 'B', 'A']
    assert app.getCurrentSheet() == 'B'
    assert_frame_equal(app.table.model.df, frame)
    assert app.table.columnwidths == {'整数': 143}
    assert app.table.floatprecision == 7
    assert app.filename == str(target)
    error.assert_not_called()


def test_old_project_and_pickle_are_rejected(workbook, tmp_path):
    app, error = workbook
    df = pd.DataFrame({'x': pd.array([1, None], dtype='Int64')})
    original = app.table
    legacy = tmp_path / '旧.dexpl'
    with gzip.open(legacy, 'wb') as stream:
        pickle.dump({'Z': {'table': df, 'meta': {'mplopts': object()}},
                     'A': {'table': df.copy()}}, stream)
    before = legacy.read_bytes()
    assert not app.load_file(legacy)
    assert legacy.read_bytes() == before and app.table is original
    assert '旧版工程使用不安全的 pickle 格式' in error.call_args.args[1]
    error.reset_mock()
    single = tmp_path / '单表.pickle'
    df.to_pickle(single)
    before = single.read_bytes()
    assert not app.load_file(single)
    assert single.read_bytes() == before and app.table is original
    assert 'pickle' in error.call_args.args[1]


@pytest.mark.parametrize('problem', ['bad_data', 'bad_meta', 'bad_active', 'bad_version', 'damaged', 'build_failure'])
def test_failed_load_rolls_back(workbook, tmp_path, monkeypatch, problem):
    app, error = workbook
    original = app.table
    names = list(app.sheets)
    target = tmp_path / 'bad.dexpl'
    data = {'first': {'table': pd.DataFrame({'x': [1]})},
            'second': {'table': pd.DataFrame({'x': [2]})}}
    if problem == 'bad_meta':
        data['second']['meta'] = {'minijmp': 1, 'columnwidths': {'x': -1}}
    if problem == 'bad_active':
        data['meta'] = {'active': ['first']}
    worksheets.write_project_file(target, data)
    if problem in ('bad_data', 'bad_version'):
        with zipfile.ZipFile(target) as archive:
            entries = {name: archive.read(name) for name in archive.namelist()}
        if problem == 'bad_data':
            entries['worksheets/sheet_002.parquet'] = b'corrupt parquet'
        else:
            manifest = json.loads(entries['manifest.json'])
            manifest['version'] = 999
            entries['manifest.json'] = json.dumps(manifest).encode('utf-8')
        with zipfile.ZipFile(target, 'w') as archive:
            for name, content in entries.items():
                archive.writestr(name, content)
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


def test_legacy_project_cannot_be_overwritten(workbook, tmp_path):
    app, error = workbook
    path = tmp_path / 'old.dexpl'
    path.write_bytes(gzip.compress(b'legacy content'))
    before = path.read_bytes()
    assert not app._save_project(path)
    assert path.read_bytes() == before
    assert app.filename is None
    assert '旧版工程使用不安全的 pickle 格式' in error.call_args.args[1]


def test_object_null_types_and_metadata_are_preserved(workbook, tmp_path):
    app, error = workbook
    frame = pd.DataFrame({'x': pd.Series([None, float('nan'), pd.NA, pd.NaT, 'ARROW:schema'], dtype=object)})
    frame.attrs = {'键': (1, {'1': '文本', 1: '整数'}), '类型': np.int64(2**60 + 7)}
    app.addSheet('数据', frame)
    path = tmp_path / 'nulls.dexpl'
    assert app._save_project(path), error.call_args
    assert app.load_file(path)
    actual = app.sheets['数据'].model.df
    assert_frame_equal(actual, frame)
    assert [type(x) for x in actual['x']] == [type(x) for x in frame['x']]
    assert actual.attrs == frame.attrs
    assert type(actual.attrs['类型']) is np.int64
    error.assert_not_called()


def test_unsupported_value_refuses_save_without_overwriting(workbook, tmp_path):
    app, error = workbook
    app.table.model.df = pd.DataFrame({'复杂值': [1 + 2j]})
    path = tmp_path / 'existing.dexpl'
    path.write_bytes(b'existing project')
    assert not app._save_project(path)
    assert path.read_bytes() == b'existing project'
    assert app.filename is None
    assert '无法使用安全格式无损保存' in error.call_args.args[1]


def test_unsupported_metadata_refuses_save_without_overwriting(workbook, tmp_path):
    app, error = workbook
    app.table.model.df.attrs['unsupported'] = object()
    path = tmp_path / 'existing.dexpl'
    path.write_bytes(b'existing project')
    assert not app._save_project(path)
    assert path.read_bytes() == b'existing project'
    assert app.filename is None
    assert '无法安全保存的元数据类型' in error.call_args.args[1]


def test_open_cancel_preserves_project(workbook, tmp_path, monkeypatch):
    app, error = workbook
    original = app.table
    app.addSheet('尚未保存', pd.DataFrame({'x': [42]}))
    path = tmp_path / 'incoming.dexpl'
    worksheets.write_project_file(path, {'incoming': {'table': pd.DataFrame({'incoming': [0]})}})
    monkeypatch.setattr(worksheets.messagebox, 'askyesnocancel', lambda *a, **k: None)
    assert not app.load_file(path)
    assert list(app.sheets) == ['工作表1', '尚未保存']
    assert app.sheets['工作表1'] is original
    assert app.table.model.df.iloc[0, 0] == 42
    error.assert_not_called()


def test_excel_widget_failure_leaves_no_extra_tabs(workbook, tmp_path, monkeypatch):
    app, error = workbook
    original = app.table
    path = tmp_path / 'book.xlsx'
    with pd.ExcelWriter(path) as writer:
        for name in ('one', 'two'):
            pd.DataFrame({'x': [1]}).to_excel(writer, sheet_name=name, index=False)
    make = app._make_sheet
    calls = []
    def fail_second(*args):
        calls.append(1)
        if len(calls) == 2:
            raise RuntimeError('widget allocation failure')
        return make(*args)
    monkeypatch.setattr(app, '_make_sheet', fail_second)
    assert not app.load_excel(path)
    assert len(calls) == 2
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
    stored = worksheets.read_project_file(path)
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
    trend.engine.set('Matplotlib')
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
