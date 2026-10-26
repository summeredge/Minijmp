"""G17 与 G15 冻结函数对照，兼顾实际覆盖层及 pandas 3。"""
import ast
import codecs
import csv
from decimal import Decimal
import inspect
import importlib.util
import io
import json
from pathlib import Path
import re
from types import SimpleNamespace
import textwrap
import tkinter as tk
import subprocess
import sys
import warnings
from unittest.mock import Mock

import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal
import pytest

from df_combine import df_combine
from dialog import findRepDialog
from modified_table import MTable
from pandastable_local.core import Table
from pandastable_local.core_orig import Table as OriginalTable
from pandastable_local.dialogs import FindReplaceDialog
from pandastable_local import csv_import
from utilities import is_void, number_2Dlist, transpose_2D_list, verifyNewColName


BEFORE = json.loads((Path(__file__).parent / 'fixtures/g17_before.json').read_text(encoding='utf-8'))


def legacy(key):
    """只执行冻结函数；不导入历史应用或历史环境。"""
    namespace = dict(pd=pd, np=np, codecs=codecs, csv=csv, io=io, re=re,
                     Path=Path, NUMBER=csv_import.NUMBER, DELIMITERS=csv_import.DELIMITERS,
                     transpose_2D_list=transpose_2D_list, is_void=is_void)
    exec(BEFORE.get('pandastable_local/csv_import.py:read_records', ''), namespace)
    exec(BEFORE[key], namespace)
    return namespace[key.split(':')[-1]]


def search_object(frame, query, case=True):
    table = SimpleNamespace(model=SimpleNamespace(df=frame), highlighted=None,
                            delete=Mock(), redraw=Mock())
    obj = SimpleNamespace(table=table, searchvar=SimpleNamespace(get=lambda: query),
                          casevar=SimpleNamespace(get=lambda: case))
    obj.clear = lambda: FindReplaceDialog.clear(obj)
    return obj


@pytest.mark.parametrize('offset', [(0, 0), (1, 1), (5, 8), (0, 4), (4, 0), (-1, -1)])
@pytest.mark.parametrize('kind', ['mixed', 'nullable', 'dates', 'empty', 'zero_columns', 'duplicates', 'large_int'])
def test_combine_preserves_g15_values_dtypes_axes_and_inputs(kind, offset):
    frames = {
        'mixed': pd.DataFrame({'a': [1, None, 3], 'b': ['x', '', None], 'c': [True, False, True]}),
        'nullable': pd.DataFrame({'a': pd.Series([1, pd.NA, 3], dtype='Int64'),
                                  'b': pd.Series(['x', pd.NA, ''], dtype='string')}),
        'dates': pd.DataFrame({'a': pd.to_datetime(['2026-01-01', None, '2026-01-03'], utc=True),
                               'b': pd.to_timedelta([1, None, 3], unit='D')}),
        'empty': pd.DataFrame(columns=['a', 'b']),
        'zero_columns': pd.DataFrame(index=[8, 4, 2]),
        'duplicates': pd.DataFrame([[1, 'a'], [2, 'b']], columns=['x', 'x']),
        'large_int': pd.DataFrame({'a': [2**63 + 1, 2**63 + 3], 'b': [1.5, 2.5]}),
    }
    first = frames[kind]
    first.index = pd.Index(range(100, 100 + len(first)), name='source')
    second = pd.DataFrame([[None, 'new'], [2**63 + 5, np.nan]], columns=['other', 'other'])
    original = first.copy(deep=True), second.copy(deep=True)
    x, y = offset
    assert_frame_equal(df_combine(first, second, x, y), legacy('df_combine.py:df_combine')(first, second, x, y))
    assert_frame_equal(first, original[0])
    assert_frame_equal(second, original[1])


@pytest.mark.parametrize('first,second', [(pd.DataFrame(), pd.DataFrame()),
    (pd.DataFrame(columns=['a']), pd.DataFrame(columns=['b', 'c'])),
    (pd.DataFrame({'a': [1, 2]}), pd.DataFrame(index=range(3)))])
def test_combine_empty_blocks(first, second):
    assert_frame_equal(df_combine(first, second, 2, 3), legacy('df_combine.py:df_combine')(first, second, 2, 3))


def test_empty_patch_does_not_validate_unused_negative_column_offset():
    first = pd.DataFrame({'a': [1, 2]})
    empty = pd.DataFrame(columns=['p'])
    for x, y in [(-2, 0), (-100, -1), (-3, 4)]:
        assert_frame_equal(df_combine(first, empty, x, y), legacy('df_combine.py:df_combine')(first, empty, x, y))


@pytest.mark.parametrize('dtype', ['int8', 'int16', 'int32', 'uint8', 'uint32', 'uint64',
                                 'float16', 'float32', 'complex64', 'complex128'])
def test_combine_preserves_numpy_scalar_dtype(dtype):
    first = pd.DataFrame({'narrow': pd.Series([1, 2, 3], dtype=dtype), 'other': ['a', 'b', 'c']})
    for patch, x, y in [(pd.DataFrame(), 0, 0), (pd.DataFrame({'text': ['x']}), 2, 0),
                         (pd.DataFrame({'number': pd.Series([4], dtype=dtype)}), 0, 1),
                         (pd.DataFrame({'number': [np.nan]}), 0, 3)]:
        assert_frame_equal(df_combine(first, patch, x, y), legacy('df_combine.py:df_combine')(first, patch, x, y))


@pytest.mark.parametrize('dtype', ['complex64', 'complex128'])
def test_number_cleaning_keeps_numpy_complex_conversion_and_warning(dtype):
    frame = pd.DataFrame({'a': pd.Series([1 + 0j, 2 + 3j, np.nan], dtype=dtype)})
    with warnings.catch_warnings(record=True) as before_warnings:
        warnings.simplefilter('always')
        expected = legacy('utilities.py:number_2Dlist')(frame, ['a'])
    with warnings.catch_warnings(record=True) as after_warnings:
        warnings.simplefilter('always')
        assert number_2Dlist(frame, ['a']) == expected == [[1., 2.]]
    assert [(w.category, str(w.message)) for w in after_warnings] == [
        (w.category, str(w.message)) for w in before_warnings]


@pytest.mark.parametrize('cols', [['a', 'b'], ['b', 'a'], ['a', 'a'], ['a'], ['bad'], ['duplicate']])
def test_number_cleaning_preserves_float_semantics_and_complete_rows(cols):
    frame = pd.DataFrame({
        'a': ['1_000', '１２', Decimal('1.25'), True, 'nan', None, 'inf', '-inf', ' 2 ', pd.NA],
        'b': [2, 'bad', '3', False, 4, 5, 6, 7, 8, 9], 'bad': ['bad'] * 10,
        'duplicate': range(10), 'other': range(10)})
    frame.columns = ['a', 'b', 'bad', 'duplicate', 'duplicate']
    frame.index = [9, 8, 7, 6, 5, 4, 3, 2, 1, 0]
    expected_log, actual_log = [], []
    expected = legacy('utilities.py:number_2Dlist')(frame, cols, True, expected_log.append)
    assert number_2Dlist(frame, cols, True, actual_log.append) == expected
    assert actual_log == expected_log


def test_number_cleaning_empty_and_invalid_selection():
    assert number_2Dlist(pd.DataFrame(columns=['a']), ['a']) == []
    with pytest.raises(IndexError):
        number_2Dlist(pd.DataFrame({'a': [1]}), [])
    with pytest.raises(KeyError):
        number_2Dlist(pd.DataFrame({'a': [1]}), ['missing'])


@pytest.mark.parametrize('query', ['', ' ', '   ', '\t', '\n', 'nan', 'NaN', 'None', '<NA>', 'NaT',
                                   'a', 'A', 'a.b', '.', '^a$', 'SS', 'İ', 'True', '1'])
@pytest.mark.parametrize('case', [True, False])
def test_exact_find_matches_g15_rules_with_boolean_mask(query, case):
    frame = pd.DataFrame([
        [None, np.nan, pd.NA], [pd.NaT, '', ' '], ['   ', '\t', '\n'],
        ['nan', 'NaN', 'None'], ['<NA>', 'NaT', 'a'], ['A', 'a.b', '.'],
        ['^a$', 'ß', 'İ'], [True, 1, '1']], columns=['same', 'same', 'c'],
        index=[8, 6, 4, 2, 0, -2, -4, -6])
    original = frame.copy(deep=True)
    obj = search_object(frame, query, case)
    findRepDialog.find(obj)
    strings = frame.astype(object).astype(str)
    expected = np.zeros(frame.shape, dtype=bool)
    for y in range(len(frame)):
        for x in range(len(frame.columns)):
            value = strings.iloc[y, x]
            expected[y, x] = bool(query) and not is_void(value) and (
                str(value) if case else str(value).upper()) == (query if case else query.upper())
    coords = [(x, y) for y, x in zip(*np.nonzero(expected))]
    assert obj.coords == coords
    if query:
        assert_frame_equal(obj.table.highlighted, pd.DataFrame(expected, index=frame.index, columns=frame.columns))
        assert obj.current == 0
    else:
        assert obj.table.highlighted is None
    assert_frame_equal(frame, original)


def test_find_replace_updates_typed_columns_without_rounding():
    frame = pd.DataFrame({
        'number': pd.Series([2**60 + 1, 2**60 + 3], index=[8, 4], dtype='int64'),
        'text': pd.Series(['old', 'keep'], index=[8, 4], dtype='str'),
    })
    table = SimpleNamespace(
        requireUnfiltered=lambda: True, model=SimpleNamespace(df=frame),
        _formula_targets_in=lambda rows, cols: [],
        _reject_formula_edit=lambda columns: False,
        storeCurrent=Mock(), tableChanged=Mock(return_value=False),
        redraw=Mock(), parentframe=None)
    search = SimpleNamespace(
        table=table, find=Mock(), coords=[(0, 0), (1, 1)],
        replacevar=SimpleNamespace(get=lambda: '9007199254740995'),
        search_changed=False)

    findRepDialog.replace(search)

    assert frame['number'].iloc[0] == 9007199254740995
    assert frame['number'].iloc[1] == 2**60 + 3
    assert frame['text'].iloc[1] == '9007199254740995'
    assert frame['number'].dtype == np.dtype('int64')
    table.storeCurrent.assert_called_once()
    table.tableChanged.assert_called_once()


def test_find_replace_invalid_numeric_value_is_atomic(monkeypatch):
    frame = pd.DataFrame({
        'text': pd.Series(['keep'], dtype='str'),
        'integer': pd.Series([1], dtype='int64'),
    })
    before = frame.copy(deep=True)
    table = SimpleNamespace(
        requireUnfiltered=lambda: True, model=SimpleNamespace(df=frame),
        _formula_targets_in=lambda rows, cols: [],
        _reject_formula_edit=lambda columns: False,
        storeCurrent=Mock(), tableChanged=Mock(return_value=False),
        redraw=Mock(), parentframe=None)
    search = SimpleNamespace(
        table=table, find=Mock(), coords=[(0, 0), (1, 0)],
        replacevar=SimpleNamespace(get=lambda: '1.5'),
        search_changed=False)
    warnings = []
    monkeypatch.setattr('dialog.messagebox.showwarning',
                        lambda title, message, **kw: warnings.append(message))

    findRepDialog.replace(search)

    assert_frame_equal(frame, before)
    table.storeCurrent.assert_not_called()
    table.tableChanged.assert_not_called()
    assert warnings and '整数' in warnings[-1]


@pytest.mark.parametrize('cls', [FindReplaceDialog, findRepDialog])
@pytest.mark.parametrize('shape', [(0, 0), (0, 3), (3, 0)])
def test_find_empty_shapes(cls, shape):
    obj = search_object(pd.DataFrame(index=range(shape[0]), columns=range(shape[1])), 'x', False)
    cls.find(obj)
    assert obj.coords == []
    assert obj.table.highlighted.shape == shape


@pytest.mark.parametrize('case', [True, False])
def test_base_find_keeps_regex_and_row_column_coordinates(case):
    frame = pd.DataFrame([['a.b', 'A'], ['ab', None], ['cat', 'a.b']],
                         columns=['x', 'x'], index=['z', 'q', 'z'])
    obj = search_object(frame, r'a.b|^a$', case)
    FindReplaceDialog.find(obj)
    expected = frame.astype(object).astype(str).apply(
        lambda col: col.str.contains(r'a.b|^a$', case=case, na=False)).astype(bool)
    assert_frame_equal(obj.table.highlighted, expected)
    assert obj.coords == list(zip(*(a.tolist() for a in np.nonzero(expected.to_numpy()))))


def test_pandas3_legacy_assignment_failure_is_fixed():
    frame = pd.DataFrame({'text': pd.Series(['needle', 'other', None], dtype='str')})
    obj = search_object(frame, 'needle')
    with pytest.raises(TypeError, match='Invalid value|dtype'):
        legacy('dialog.py:find')(obj)
    findRepDialog.find(obj)
    assert obj.coords == [(0, 0)]
    assert obj.table.highlighted['text'].dtype == bool


@pytest.mark.parametrize('rows,cols,axis', [
    ([3, 1], [3, 1], 'cell'), ([3, 1], [], 'row'),
    ([], [1, 3], 'column'), ([], [], 'cell'),
])
def test_mtable_paste_dispatches_to_safe_selection(rows, cols, axis):
    paste = Mock(return_value=True)
    table = SimpleNamespace(multiplerowlist=rows, multiplecollist=cols,
                            allrows=False, currentrow=0, currentcol=0,
                            paste_context_selection=paste)

    assert MTable.paste(table)
    paste.assert_called_once_with(axis, rows or [0], cols or [0])


@pytest.mark.parametrize('selected', [True, False])
def test_paste_header_preserves_offset_headers(monkeypatch, selected):
    old = pd.DataFrame([[1, 'old'], [2, 'keep']], columns=['a', 'b'], index=[20, 10])
    pasted = pd.DataFrame([['new', None], ['next', 'tail']], columns=['b', 'b'])
    table = SimpleNamespace(requireUnfiltered=lambda: True, storeCurrent=Mock(),
                            model=SimpleNamespace(df=old.copy()), redraw=Mock(), updateIndex=Mock(),
                            parentframe=None, multiplerowlist=[3, 1] if selected else [],
                            multiplecollist=[3, 1] if selected else [],
                            _formula_targets_in=lambda rows, cols: [],
                            _reject_formula_edit=lambda columns: False)
    table.updateModel = lambda model: setattr(table, 'model', model)
    reader = Mock(return_value=pasted)
    monkeypatch.setattr(pd, 'read_clipboard', reader)
    MTable.paste_header(table)
    x, y = (1, 1) if selected else (0, 0)
    y = 0
    expected = legacy('df_combine.py:df_combine')(old, pasted, x, y)
    names = list(expected)
    for i, name in enumerate(pasted.columns):
        names[x + i] = verifyNewColName(name, names)
    expected.columns = names
    assert_frame_equal(table.model.df, expected)
    table.storeCurrent.assert_called_once()
    assert reader.call_args.kwargs == {'sep': ','}
    table.updateIndex.assert_called_once_with(ask=False)


def test_active_overrides_and_no_scalar_access_hotspots():
    assert MTable.__mro__[1:3] == (Table, OriginalTable)
    assert Table.paste is OriginalTable.paste
    assert MTable.paste is not Table.paste
    assert Table.importCSV is OriginalTable.importCSV
    assert MTable.doCombine is OriginalTable.doCombine
    assert MTable.merge is OriginalTable.merge
    for function in [df_combine, number_2Dlist, findRepDialog.find, FindReplaceDialog.find]:
        tree = ast.parse(textwrap.dedent(inspect.getsource(function)))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                assert node.attr not in ('iloc', 'iat', 'iterrows', 'iteritems'), function.__qualname__
    assert 'paste_context_selection(' in inspect.getsource(MTable.paste)
    for method in [MTable.paste_header, MTable.stackColumn]:
        assert 'df_combine(' in inspect.getsource(method)


@pytest.mark.parametrize('cls', [OriginalTable, Table, MTable])
def test_real_search_dialog_dispatch_and_highlight_redraw(tk_root, cls):
    parent = tk.Frame(tk_root)
    parent.pack(fill='both', expand=True)
    frame = pd.DataFrame({'text': ['needle', 'Needle', None], 'n': [1, 2, 3]})
    table = cls(parent, dataframe=frame)
    try:
        table.show()
        tk_root.update()
        table.findText()
        search = table.searchframe
        assert type(search) is (findRepDialog if cls is MTable else FindReplaceDialog)
        search.searchvar.set('needle')
        search.casevar.set(False)
        search.findAll()
        tk_root.update()
        assert search.coords == ([(0, 0), (0, 1)] if cls is MTable else [(0, 0), (1, 0)])
        assert table.highlighted.iloc[:, 0].tolist() == [True, True, False]
        assert_frame_equal(table.model.df, frame)
        search.clear()
        assert table.highlighted is None and search.coords == []
    finally:
        parent.destroy()


def test_real_mtable_stack_routes_shared_combine(tk_root):
    parent = tk.Frame(tk_root)
    parent.pack(fill='both', expand=True)
    frame = pd.DataFrame({'a': [1, np.nan, 3], 'b': [4, 5, 6]})
    table = MTable(parent, dataframe=frame.copy())
    try:
        table.show()
        table.multiplecollist = [0, 1]
        table.stackColumn()
        expected = frame.copy()
        expected['Stk Keys'] = np.nan
        expected['Stk Data'] = np.nan
        stacked = pd.DataFrame({'1': ['a', 'a', 'b', 'b', 'b'], '2': [1., 3., 4., 5., 6.]})
        expected = legacy('df_combine.py:df_combine')(expected, stacked, 2, 0)
        assert_frame_equal(table.model.df, expected)
        assert_frame_equal(table.prevdf[0], frame)
    finally:
        parent.destroy()


def test_benchmark_records_three_valid_samples_after_equality_check(tmp_path):
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run([sys.executable, str(root / 'tools/benchmark_data_processing.py'),
                            '--rows', '3', '--output', str(tmp_path)],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    records = pd.read_csv(tmp_path / 'performance.csv')
    assert len(records) == 6 * 2 * 4
    assert (records.status == 'ok').all()
    assert (records.loc[~records.warmup].groupby(['case', 'variant']).size() == 3).all()


def test_benchmark_does_not_record_failed_comparison_as_success(tmp_path, monkeypatch):
    script = Path(__file__).resolve().parents[1] / 'tools/benchmark_data_processing.py'
    spec = importlib.util.spec_from_file_location('g17_benchmark_probe', script)
    benchmark = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(benchmark)
    monkeypatch.setattr(sys, 'argv', [str(script), '--rows', '3', '--cases', 'df_combine',
                                      '--output', str(tmp_path)])
    monkeypatch.setattr(benchmark, 'df_combine', lambda *args, **kwargs: pd.DataFrame({'wrong': [0]}))
    with pytest.raises(AssertionError):
        benchmark.main()
    assert pd.read_csv(tmp_path / 'performance.csv').empty
