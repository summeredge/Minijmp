from types import SimpleNamespace
from unittest.mock import Mock
from pathlib import Path
import tkinter as tk

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from pandastable_local.csv_import import detect_csv, read_csv
from pandastable_local import core_orig, dialogs
from pandastable_local.data import TableModel


@pytest.fixture
def csv_app(tk_root, monkeypatch):
    from MiniJMP import Minijmp

    previous = set(tk_root.winfo_children())
    callbacks = []
    monkeypatch.setattr(tk_root, 'report_callback_exception', lambda *args: callbacks.append(args))
    monkeypatch.setattr(Minijmp, 'start_logging', lambda self: None)
    app = Minijmp(parent=tk_root)
    error = Mock()
    monkeypatch.setattr(core_orig.messagebox, 'showerror', error)
    try:
        yield app, error
        assert not callbacks, callbacks
    finally:
        tk_root.configure(menu='')
        for widget in set(tk_root.winfo_children()) - previous:
            widget.destroy()


def invoke_csv_menu(app, advanced=False):
    menu = app.file_menu['var']
    label = 'Advanced Import' if advanced else 'Import CSV'
    index = next(i for i in range(menu.index('end') + 1)
                 if menu.type(i) == 'command' and menu.entrycget(i, 'label').strip() == label)
    menu.invoke(index)


@pytest.mark.parametrize('name,shape', [
    ('coatings.csv', (32, 2)),
    ('ElectricCarData_Clean-kaggle.csv', (103, 14)),
    ('human_age_prediction-Kaggle.csv', (3000, 25)),
])
def test_real_file_menu_imports_samples_without_parameter_window(csv_app, monkeypatch, name, shape):
    app, error = csv_app
    path = Path(__file__).resolve().parents[1] / 'sample_data' / name
    monkeypatch.setattr(core_orig.filedialog, 'askopenfilename', Mock(return_value=str(path)))
    windows = Mock(side_effect=AssertionError('明确格式不应打开参数窗口'))
    monkeypatch.setattr(tk.Misc, 'wait_window', windows)
    invoke_csv_menu(app)
    assert app.table.model.df.shape == shape
    assert app.table.filename is None and app.table.prevdf is None
    assert app.main.title() == 'Untitled - Minijmp'
    windows.assert_not_called()
    error.assert_not_called()


@pytest.mark.parametrize('kind', ['plain', 'header', 'encoding', 'advanced',
                                  'cancel_file', 'cancel_preview', 'cancel_advanced',
                                  'damaged', 'missing'])
def test_real_file_menu_confirmation_advanced_and_protection(csv_app, tmp_path, monkeypatch, kind):
    app, error = csv_app
    path = tmp_path / 'menu.csv'
    text = '名称,数值\n中文,1\n其他,2\n'
    if kind in ('header', 'cancel_preview'):
        text = 'red,large\nblue,small\n'
    elif kind == 'damaged':
        text = 'name,value\nA,1\nB,2,3\n'
    path.write_text(text, encoding='gb18030' if kind == 'encoding' else 'utf-8')
    if kind == 'missing':
        path.unlink()
    monkeypatch.setattr(core_orig.filedialog, 'askopenfilename', Mock(
        return_value='' if kind == 'cancel_file' else str(path)))
    original = pd.DataFrame({'old': [42]})
    app.table.updateModel(TableModel(original.copy()))
    app.table.filename = 'old.pickle'
    app.table.prevdf = original.copy()
    app.update_title()
    seen = []

    def respond(window, *args, **kwargs):
        seen.append(window.title())
        if kind.startswith('cancel_'):
            window.destroy()
            return
        expected = 'Text Import' if kind == 'advanced' else '确认 CSV 导入'
        assert window.title() == expected
        widgets = list(window.winfo_children())
        for widget in widgets:
            widgets.extend(widget.winfo_children())
        # Invoke the real button after both the constructor and preview have run.
        button = next(w for w in widgets if isinstance(w, (tk.Button, dialogs.Button))
                      and w.cget('text') == ('Import' if kind == 'advanced' else '导入'))
        button.invoke()

    monkeypatch.setattr(tk.Misc, 'wait_window', respond)
    invoke_csv_menu(app, advanced=kind in ('advanced', 'cancel_advanced'))
    unchanged = kind.startswith('cancel_') or kind in ('damaged', 'missing')
    if unchanged:
        assert_frame_equal(app.table.model.df, original)
        assert_frame_equal(app.table.prevdf, original)
        assert app.table.filename == 'old.pickle'
        assert app.main.title() == 'old.pickle - Minijmp'
    else:
        assert app.table.model.df.shape == (2, 2)
        assert app.table.filename is None and app.table.prevdf is None
        if kind == 'header':
            assert app.table.model.df.iloc[0].tolist() == ['red', 'large']
        else:
            assert app.table.model.df.iloc[0].tolist() == ['中文', 1]
    assert error.call_count == int(kind in ('damaged', 'missing'))
    if kind in ('plain', 'cancel_file', 'damaged', 'missing'):
        assert not seen
    else:
        assert seen == ['Text Import' if 'advanced' in kind else '确认 CSV 导入']


@pytest.mark.parametrize('delimiter', [',', '\t', ';', '|'])
@pytest.mark.parametrize('encoding', ['utf-8', 'utf-8-sig', 'utf-16'])
def test_detection_quotes_empty_chinese_and_no_dates(tmp_path, delimiter, encoding):
    import csv
    path = tmp_path / 'data.csv'
    with path.open('w', encoding=encoding, newline='') as stream:
        writer = csv.writer(stream, delimiter=delimiter)
        writer.writerows([['名称', '数值', '日期', '编号'],
                          ['中文,"引号"\n换行', '1.5', '2026-10-20', '001'],
                          ['NA', '', '2026-10-21', '002']])
    options = detect_csv(path)
    assert options.pop('confirm') is False
    assert options['header'] is True
    assert options['delimiter'] == delimiter
    frame = read_csv(path, **options)
    assert frame.shape == (2, 4)
    assert frame.iloc[0].tolist() == ['中文,"引号"\n换行', 1.5, '2026-10-20', '001']
    assert frame.iloc[1, 0] == 'NA'
    assert pd.isna(frame.iloc[1, 1])


@pytest.mark.parametrize('text', ['red,large\nblue,small\n', 'name\nAlice\nBob\n',
                                 'a,b;c\n1,2;3\n', 'name,value\n', 'x,x\n1,2\n'])
def test_ambiguity_requires_confirmation(tmp_path, text):
    path = tmp_path / 'uncertain.csv'
    path.write_text(text, encoding='utf-8')
    assert detect_csv(path)['confirm']


def test_legacy_encoding_requires_confirmation(tmp_path):
    path = tmp_path / 'legacy.csv'
    path.write_text('名称,数值\n中文,1\n', encoding='gb18030')
    options = detect_csv(path)
    assert options.pop('confirm')
    assert options['encoding'] == 'gb18030'
    assert read_csv(path, **options).iloc[0, 0] == '中文'


@pytest.mark.parametrize('text', ['a,b\n1,2\n3\n', 'a,b\n1,2\n3,4,5\n',
                                 'a,b\n1,2\n"unterminated,3', '', 'a,b\n\x00,1'])
def test_failure_preserves_table_and_state(tmp_path, monkeypatch, text):
    path = tmp_path / 'bad.csv'
    path.write_text(text, encoding='utf-8')
    old = pd.DataFrame({'old': [42]})
    table = SimpleNamespace(master=None, model=TableModel(old), currentdir='.',
                            importpath='before', filename='old.pickle', prevdf=old,
                            updateModel=Mock(), redraw=Mock())
    error = Mock()
    monkeypatch.setattr(core_orig.messagebox, 'showerror', error)
    core_orig.Table.importCSV(table, path)
    error.assert_called_once()
    table.updateModel.assert_not_called()
    table.redraw.assert_not_called()
    assert table.filename == 'old.pickle' and table.importpath == 'before'
    assert_frame_equal(table.model.df, old)
    assert_frame_equal(table.prevdf, old)


@pytest.mark.parametrize('advanced', [False, True])
def test_cancel_and_advanced_routing(tmp_path, monkeypatch, advanced):
    path = tmp_path / 'text.csv'
    path.write_text('red,large\nblue,small\n', encoding='utf-8')
    table = SimpleNamespace(master=None, currentdir='.', importpath='.',
                            updateModel=Mock(), redraw=Mock())
    preview = Mock(return_value=SimpleNamespace(df=None))
    settings = Mock(return_value=SimpleNamespace(df=None))
    monkeypatch.setattr(core_orig, 'CSVPreviewDialog', preview)
    monkeypatch.setattr(core_orig, 'ImportDialog', settings)
    core_orig.Table.importCSV(table, path, dialog=advanced)
    assert settings.call_count == int(advanced)
    assert preview.call_count == int(not advanced)
    table.updateModel.assert_not_called()


def test_real_preview_header_toggle_and_import(tk_root, tmp_path, monkeypatch):
    path = tmp_path / 'text.csv'
    path.write_text('red,large\nblue,small\n', encoding='utf-8')
    monkeypatch.setattr('tkinter.Misc.wait_window', lambda *args: None)
    dialog = dialogs.CSVPreviewDialog(tk_root, path, detect_csv(path))
    try:
        assert '2 行 × 2 列' in dialog.preview.get('1.0', 'end')
        dialog.header.set(True)
        dialog.update_preview()
        assert '1 行 × 2 列' in dialog.preview.get('1.0', 'end')
        dialog.header.set(False)
        dialog.doImport()
        assert dialog.df.values.tolist() == [['red', 'large'], ['blue', 'small']]
    finally:
        if dialog.main.winfo_exists():
            dialog.main.destroy()


def test_numeric_identifiers_and_localized_numbers_preserved(tmp_path):
    path = tmp_path / 'numbers.csv'
    path.write_text('id,long,local,value\n001,1234567890123456789,"1,25",2.5\n'
                    '002,1234567890123456790,"2,25",3.5\n', encoding='utf-8')
    options = detect_csv(path)
    assert not options.pop('confirm')
    frame = read_csv(path, **options)
    assert frame.iloc[0].tolist() == ['001', '1234567890123456789', '1,25', 2.5]


def test_confirmed_import_resets_state(tmp_path, monkeypatch):
    path = tmp_path / 'text.csv'
    path.write_text('red,large\nblue,small\n', encoding='utf-8')
    expected = pd.DataFrame([['red', 'large'], ['blue', 'small']])
    preview = Mock(return_value=SimpleNamespace(df=expected))
    monkeypatch.setattr(core_orig, 'CSVPreviewDialog', preview)
    table = SimpleNamespace(master=None, currentdir='.', importpath='.',
                            filename='old.pickle', prevdf=expected, updateModel=Mock(), redraw=Mock())
    core_orig.Table.importCSV(table, path)
    preview.assert_called_once()
    assert_frame_equal(table.updateModel.call_args.args[0].df, expected)
    assert table.filename is None and table.prevdf is None
    assert table.importpath == str(tmp_path)
    table.redraw.assert_called_once()


def test_preview_invalid_choice_blocks_import(tk_root, tmp_path, monkeypatch):
    path = tmp_path / 'text.csv'
    path.write_text('name;value\n中文;1\n', encoding='utf-8')
    monkeypatch.setattr('tkinter.Misc.wait_window', lambda *args: None)
    error = Mock()
    monkeypatch.setattr(dialogs.messagebox, 'showerror', error)
    dialog = dialogs.CSVPreviewDialog(tk_root, path, detect_csv(path))
    try:
        dialog.encoding.set('ascii')
        dialog.update_preview()
        assert str(dialog.button['state']) == 'disabled'
        dialog.doImport()
        assert dialog.df is None and dialog.main.winfo_exists()
        error.assert_called_once()
        dialog.encoding.set('utf-8-sig')
        dialog.update_preview()
        assert str(dialog.button['state']) == 'normal'
    finally:
        dialog.main.destroy()
