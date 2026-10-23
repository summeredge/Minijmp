"""REVIEW-001/002：位置删除及失败导出不得丢失原数据。"""
import hashlib
import importlib
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from modified_table import MTable
from pandastable_local.data import TableModel
from pandastable_local.data_orig import TableModel as OriginalTableModel


def table_stub(frame, rows, cols):
    table = SimpleNamespace(
        requireUnfiltered=lambda: True, allrows=False, editable=True,
        parentframe=None, multiplerowlist=rows, multiplecollist=cols,
        model=TableModel(frame.copy()), filtered=False, prevdf=None,
        redraw=Mock(), updateModel=Mock())
    table.storeCurrent = lambda: MTable.storeCurrent(table)
    return table


@pytest.mark.parametrize('rows,cols', [([0], [0]), ([2, 0], [0, 2])])
def test_shift_deletes_positions_and_undo_restores_values(rows, cols, monkeypatch):
    frame = pd.DataFrame({'x': [1, 65535, 3], 'keep': [7, 8, 9],
                          'z': [65536, 65535, 65537]}, index=[8, 8, 3])
    table = table_stub(frame, rows, cols)
    monkeypatch.setattr('modified_table.messagebox.askyesno', lambda *a, **kw: True)
    MTable.clearDataUp(table)
    keep = [i for i in range(len(frame)) if i not in rows]
    for col in cols:
        expected = frame.iloc[keep, col].tolist() + [np.nan] * len(rows)
        np.testing.assert_equal(table.model.df.iloc[:, col].to_numpy(), expected)
    for col in set(range(len(frame.columns))) - set(cols):
        assert table.model.df.iloc[:, col].equals(frame.iloc[:, col])
    assert table.model.df.index.equals(frame.index)
    MTable.undo(table)
    assert_frame_equal(table.model.df, frame)


def test_filtered_shift_is_rejected_without_history_or_writes(monkeypatch):
    table = table_stub(pd.DataFrame({'x': [1, 65535, 3]}), [0], [0])
    before = table.model.df.copy()
    table.requireUnfiltered = lambda: False
    confirm = Mock()
    monkeypatch.setattr('modified_table.messagebox.askyesno', confirm)
    MTable.clearDataUp(table)
    confirm.assert_not_called()
    assert table.prevdf is None
    assert_frame_equal(table.model.df, before)


@pytest.mark.parametrize('model_type', [OriginalTableModel, TableModel])
def test_timezone_export_failure_preserves_existing_sha256(tmp_path, model_type):
    path = tmp_path / 'existing.xlsx'
    pd.DataFrame({'valuable': ['original']}).to_excel(path, index=False)
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    frame = pd.DataFrame({'t': pd.date_range('2026-01-01', periods=1, tz='UTC')})
    with pytest.raises(ValueError, match='timezone'):
        model_type(frame).save(path)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before
    assert pd.read_excel(path).valuable.tolist() == ['original']
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.parametrize('extension,method', [('.csv', 'to_csv'), ('.xlsx', 'to_excel'),
                                            ('.pickle', 'to_pickle')])
def test_partial_serialization_failure_preserves_existing_file(tmp_path, monkeypatch, extension, method):
    path = tmp_path / ('existing' + extension)
    path.write_bytes(b'original bytes')

    def fail(frame, filename, **kwargs):
        from pathlib import Path
        Path(filename).write_bytes(b'partial output')
        raise ValueError('serialization failed')

    monkeypatch.setattr(pd.DataFrame, method, fail)
    with pytest.raises(ValueError, match='serialization failed'):
        TableModel(pd.DataFrame({'x': [1]})).save(path)
    assert path.read_bytes() == b'original bytes'
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.parametrize('extension', ['.csv', '.xlsx'])
def test_successful_export_replaces_existing_and_is_readable(tmp_path, extension):
    path = tmp_path / ('existing' + extension)
    path.write_bytes(b'old bytes')
    expected = pd.DataFrame({'编号': ['001', '002'], '值': [1.5, 3.5]})
    TableModel(expected).save(path)
    reader = pd.read_csv if extension == '.csv' else pd.read_excel
    assert_frame_equal(reader(path, index_col=0, dtype={'编号': str}), expected)
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.parametrize('extension', ['.CSV', '.XLSX'])
def test_uppercase_export_extensions(tmp_path, extension):
    path = tmp_path / ('uppercase' + extension)
    TableModel(pd.DataFrame({'x': [1]})).save(path)
    reader = pd.read_csv if extension == '.CSV' else pd.read_excel
    assert reader(path, index_col=0).x.tolist() == [1]


@pytest.mark.parametrize('existing', [False, True])
def test_replace_failure_preserves_destination_and_removes_temporary(tmp_path, monkeypatch, existing):
    path = tmp_path / 'target.csv'
    if existing:
        path.write_bytes(b'original')
    monkeypatch.setattr('pandastable_local.util.os.replace', Mock(side_effect=PermissionError('locked')))
    with pytest.raises(PermissionError, match='locked'):
        TableModel(pd.DataFrame({'x': [1]})).save(path)
    assert path.read_bytes() == b'original' if existing else not path.exists()
    assert list(tmp_path.iterdir()) == ([path] if existing else [])


@pytest.mark.parametrize('module_name,class_name', [
    ('capability_dialog', 'CapabilityDialog'), ('quality_tools_dialog', 'QualityToolsDialog'),
    ('advanced_spc_dialog', 'AdvancedSPCDialog'),
    ('advanced_time_series_dialog', 'TimeSeriesAnalysisDialog'),
    ('pca_dialog', 'PCADialog'), ('regression_dialog', 'RegressionDialog'),
])
@pytest.mark.parametrize('extension', ['.csv', '.xlsx'])
def test_analysis_export_failure_is_reported_without_overwrite(
        tmp_path, monkeypatch, module_name, class_name, extension):
    module = importlib.import_module(module_name)
    path = tmp_path / ('existing' + extension)
    path.write_bytes(b'original')
    frame = pd.DataFrame({'x': [1]})
    dialog = SimpleNamespace(main=None, current_table=lambda: ('result', frame), error=Mock())
    monkeypatch.setattr(module.filedialog, 'asksaveasfilename', lambda **kw: str(path))

    def fail(frame, filename, **kwargs):
        from pathlib import Path
        Path(filename).write_bytes(b'partial')
        raise ValueError('serialization failed')

    monkeypatch.setattr(pd.DataFrame, 'to_csv' if extension == '.csv' else 'to_excel', fail)
    getattr(module, class_name).export(dialog)
    assert path.read_bytes() == b'original'
    dialog.error.assert_called_once()
    assert 'serialization failed' in str(dialog.error.call_args.args[0])
    assert list(tmp_path.iterdir()) == [path]


def test_stat_table_excel_failure_preserves_destination(tmp_path, monkeypatch):
    from openpyxl import Workbook
    from stat_table import StatTable, export_excel
    path = tmp_path / 'existing.xlsx'
    path.write_bytes(b'original')

    def fail(book, filename):
        from pathlib import Path
        Path(filename).write_bytes(b'partial')
        raise OSError('disk write failed')

    monkeypatch.setattr(Workbook, 'save', fail)
    with pytest.raises(OSError, match='disk write failed'):
        export_excel(StatTable(headers=['x'], values=[[1]]), path)
    assert path.read_bytes() == b'original'
    assert list(tmp_path.iterdir()) == [path]


def test_real_table_shift_undo_redo_and_filter(tk_root, monkeypatch):
    import tkinter as tk
    parent = tk.Frame(tk_root)
    table = MTable(parent, dataframe=pd.DataFrame({'x': [1, 65535, 3]}))
    table.show()
    monkeypatch.setattr('modified_table.messagebox.askyesno', lambda *a, **kw: True)
    monkeypatch.setattr('pandastable_local.core_orig.messagebox.showwarning', Mock())
    original = table.model.df.copy()
    try:
        table.multiplerowlist, table.multiplecollist = [0], [0]
        table.clearDataUp()
        np.testing.assert_equal(table.model.df.x.to_numpy(), [65535, 3, np.nan])
        shifted = table.model.df.copy()
        table.undo()
        assert_frame_equal(table.model.df, original)
        table.redo()
        assert_frame_equal(table.model.df, shifted)
        table.dataframe = shifted.copy()
        table.model.df = shifted.iloc[[0]].copy()
        table.filtered = True
        visible = table.model.df.copy()
        table.clearDataUp()
        assert_frame_equal(table.model.df, visible)
        assert_frame_equal(table.dataframe, shifted)
    finally:
        parent.destroy()
