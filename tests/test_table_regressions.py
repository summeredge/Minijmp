from pathlib import Path
from types import SimpleNamespace
import tkinter as tk
import warnings

import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from modified_table import MTable
from pandastable_local.core import Table
from pandastable_local.core_orig import Table as OriginalTable
from pandastable_local.data import TableModel
from pandastable_local import config, core_orig
from test_csv_import import csv_app


@pytest.fixture(params=[OriginalTable, Table, MTable])
def table(request, tk_root):
    root = tk_root
    errors = []
    root.report_callback_exception = lambda *args: errors.append(args)
    frame = tk.Frame(root)
    frame.pack(fill='both', expand=True)
    widget = request.param(frame)
    widget.show()
    root.update()
    try:
        yield widget
    finally:
        frame.destroy()
    assert not errors


def replace(table, df):
    table.updateModel(TableModel(dataframe=df.copy()))
    table.redraw()


def event(table, row=0, col=0):
    return SimpleNamespace(x=table.col_positions[col] + 5,
                           y=table.y_start + table.rowheight * row + 5,
                           keysym='Down')


def header_event_generate(table, sequence, canvas_x, y=10, state=None):
    header = table.colheader
    args = {'x': round(canvas_x - header.canvasx(0)), 'y': y}
    if state is not None:
        args['state'] = state
    header.event_generate(sequence, **args)
    header.update()


@pytest.fixture
def visible_table(table):
    root = table.winfo_toplevel()
    root.geometry('900x650+0+0')
    root.deiconify()
    root.update()
    yield table
    root.withdraw()


def header_double_click(table, canvas_x, y=10):
    reset_x = table.colheader.canvasx(0)
    header_event_generate(table, '<Button-1>', reset_x, y)
    header_event_generate(table, '<ButtonRelease-1>', reset_x, y)
    for _ in range(2):
        header_event_generate(table, '<Button-1>', canvas_x, y)
        header_event_generate(table, '<ButtonRelease-1>', canvas_x, y)


@pytest.mark.parametrize('shape', [(1, 1), (1, 3), (0, 1), (1, 0), (0, 0)])
def test_switch_model_clears_stale_state_and_mouse_events(table, shape):
    table.setSelectedRow(12)
    table.setSelectedCol(4)
    table.multiplecollist = [0, 4]
    table.multiplerowlist = [0, 12]
    table.filtered = True
    table.dataframe = table.model.df.copy()
    table.highlighted = pd.DataFrame(True, index=range(20), columns=range(5))
    replace(table, pd.DataFrame(np.ones(shape)))
    assert (table.currentrow, table.currentcol) == (0, 0)
    assert table.multiplecollist == table.multiplerowlist == []
    assert not table.filtered and not hasattr(table, 'dataframe')
    assert table.highlighted is None
    assert table.colheader.model is table.model
    table.handle_left_click(SimpleNamespace(x=5, y=5))
    table.handle_left_release(SimpleNamespace(x=5, y=5))
    table.handle_left_release(SimpleNamespace(x=10000, y=10000))
    table.handle_arrow_keys(SimpleNamespace(keysym='Down'))
    table.updateModel()
    assert table.rowheader.model is table.model


@pytest.mark.parametrize('name,options,shape', [
    ('coatings.csv', {'sep': '\t', 'header': None}, (32, 2)),
    ('ElectricCarData_Clean-kaggle.csv', {}, (103, 14)),
    ('human_age_prediction-Kaggle.csv', {}, (3000, 25)),
])
def test_official_csv_import_then_click_and_edit(table, name, options, shape):
    filename = Path(__file__).resolve().parents[1] / 'sample_data' / name
    expected = pd.read_csv(filename, **options)
    table.setSelectedCol(4)
    table.importCSV(str(filename))
    assert table.model.df.shape == shape
    assert_frame_equal(table.model.df, expected)
    table.handle_left_click(event(table))
    table.handle_left_release(event(table))
    table.drawCellEntry(0, 0)
    table.cellentryvar.set('123')
    table.handleCellEntry(0, 0)
    assert str(table.model.df.iloc[0, 0]) == '123'


@pytest.mark.parametrize('advanced', [False, True])
def test_csv_menu_exposes_smart_and_advanced_import(advanced, csv_app, monkeypatch):
    from unittest.mock import Mock
    app, error = csv_app
    command = Mock()
    monkeypatch.setattr(app, 'import_csv', command)
    app.createMenuBar()
    from test_csv_import import invoke_csv_menu
    invoke_csv_menu(app, advanced=advanced)
    command.assert_called_once_with(**({'advanced': True} if advanced else {}))
    error.assert_not_called()


def test_real_import_dialog_preserves_hash_text_and_default_rows(table, tmp_path, monkeypatch):
    from pandastable_local import dialogs
    from unittest.mock import Mock
    path = tmp_path / 'notes.csv'
    path.write_text('note,amount\nlot#A,1\n\nlotB,2\n', encoding='utf-8')
    monkeypatch.setattr(tk.Misc, 'wait_window', lambda *a: None)
    error = Mock()
    monkeypatch.setattr(dialogs.messagebox, 'showerror', error)
    dialog = dialogs.ImportDialog(table, filename=str(path))
    try:
        dialog.doImport()
        expected = pd.read_csv(path)
        assert_frame_equal(dialog.df, expected)
        assert dialog.kwds['comment'] is None
        error.assert_not_called()
    finally:
        if dialog.main.winfo_exists():
            dialog.main.destroy()


def test_all_statistics_menu_dialogs_construct_and_close(tk_root):
    import inspect
    import MiniJMP
    from dialog import Dialogs
    app = SimpleNamespace(dialog_help_msg=lambda **kw: '')
    data = pd.DataFrame({'x': [1., 2., 3.], 'y': [4., 6., 5.], 'group': ['a', 'a', 'b']})
    types = [cls for _, cls in inspect.getmembers(MiniJMP, inspect.isclass)
             if issubclass(cls, Dialogs) and cls is not Dialogs]
    assert len(types) >= 40
    for cls in types:
        widget = cls(parent=tk_root, df=data.copy(), title=cls.__name__, app=app)
        widget.main.withdraw()
        tk_root.update_idletasks()
        assert widget.main.winfo_exists(), cls.__name__
        widget.quit()


@pytest.mark.parametrize('tab', [False, True])
def test_last_cell_edit_does_not_advance_outside_table(table, tab):
    replace(table, pd.DataFrame({'x': [1]}))
    table.drawCellEntry(0, 0)
    table.cellentryvar.set('7')
    if isinstance(table, MTable):
        table.handleCellEntry(0, 0, nxt_col=tab)
    else:
        table.handleCellEntry(0, 0)
    assert table.model.df.iloc[0, 0] == 7
    assert (table.currentrow, table.currentcol) == (0, 0)
    table.drawCellEntry(1, 0)
    table.drawCellEntry(0, 1)


def test_delete_selected_columns_and_rows_then_select(table):
    replace(table, pd.DataFrame({'a': [1, 2], 'b': [3, 4]}))
    table.setSelectedCells(0, 2, 0, 2)
    table.deleteColumn(ask=False)
    table.redraw()
    assert table.model.df.shape == (2, 0)
    assert table.multiplecollist == []
    replace(table, pd.DataFrame({'a': [1, 2]}))
    table.multiplerowlist = [0, 1]
    table.deleteRow(ask=False)
    assert table.model.df.shape == (0, 1)
    table.handle_left_release(SimpleNamespace(x=5, y=5))


def test_redraw_missing_objects_without_future_warning(table):
    df = pd.DataFrame({'x': pd.Series([1, None], dtype=object),
                       'y': pd.Series([True, None], dtype=object)})
    with warnings.catch_warnings():
        warnings.simplefilter('error', FutureWarning)
        replace(table, df)
    assert_frame_equal(table.model.df, df)


def test_wrapped_header_handles_empty_table(table):
    table.colheader.wrap = True
    replace(table, pd.DataFrame())
    table.handle_left_release(SimpleNamespace(x=5, y=5))


def test_real_filter_query_edit_toggle_and_close(table):
    from pandastable_local.dialogs import QueryDialog
    replace(table, pd.DataFrame({'x': [10, 20, 30]}))
    table.queryBar()
    query = table.qframe
    try:
        query.queryvar.set('x >= 20')
        query.query()
        assert table.filtered
        assert table.model.df.x.tolist() == [20, 30]
        table.model.setValueAt('99', 0, 0, df=table.dataframe)
        query.applyqueryvar.set(False)
        query.query()
        assert not table.filtered
        assert table.model.df.x.tolist() == [10, 99, 30]
        query.applyqueryvar.set(True)
        query.queryvar.set('x > 100')
        query.query()
        assert table.model.df.empty
    finally:
        query.close()
    assert table.model.df.x.tolist() == [10, 99, 30]
    assert not table.filtered


def test_sort_columns_uses_row_position_after_sorting(table):
    replace(table, pd.DataFrame({'a': [2, 9], 'b': [1, 8], 'text': ['x', 'y']},
                                index=[100, 50]))
    table.currentrow = 1
    table.sortColumnIndex()
    assert list(table.model.df.columns) == ['b', 'a', 'text']


def test_header_sort_and_undo_use_existing_table_implementations(table):
    original = pd.DataFrame({'a': [2, 1], 'b': ['second', 'first']})
    replace(table, original)
    table.setSelectedCol(0)
    table.sortTable()
    assert table.model.df.a.tolist() == [1, 2]
    assert table.model.df.b.tolist() == ['first', 'second']
    table.undo()
    assert_frame_equal(table.model.df, original)


def test_sort_selected_preserves_custom_index_values_and_types(table, monkeypatch):
    if not isinstance(table, MTable):
        return
    import modified_table
    original = pd.DataFrame({'a': [2, 1], 'b': ['stay', 'put']}, index=[100, 200])
    replace(table, original)
    table.setSelectedCol(0)
    monkeypatch.setattr(modified_table, 'MultipleValDialog', lambda **kw:
        SimpleNamespace(result=True, results=['a', True, '', True, '', True]))
    table.sortSelected()
    assert_frame_equal(table.model.df,
                       pd.DataFrame({'a': [1, 2], 'b': ['stay', 'put']}, index=[100, 200]))


def test_clean_data_cancel_preserves_data(table, monkeypatch):
    original = pd.DataFrame({'a': [1., np.nan]})
    replace(table, original)
    monkeypatch.setattr(core_orig, 'MultipleValDialog', lambda **kw:
        SimpleNamespace(result=True, results=['fill scalar', '0', '10', 0, 0,
                                              'any', '', 0, 0, '0']))
    monkeypatch.setattr(core_orig.messagebox, 'askyesno', lambda *a, **kw: False)
    table.cleanData()
    assert_frame_equal(table.model.df, original)


def test_convert_negative_numbers_keeps_sign(table, monkeypatch):
    replace(table, pd.DataFrame({'a': ['-1.5', '($2.5)', '3.0']}))
    table.multiplecollist = [0]
    monkeypatch.setattr(core_orig, 'MultipleValDialog', lambda **kw:
        SimpleNamespace(result=True, results=['float', 1, 1, 1, 0]))
    table.convertNumeric()
    assert table.model.df.a.tolist() == [-1.5, -2.5, 3.0]


def test_existing_column_expansion_apis(table, monkeypatch):
    replace(table, pd.DataFrame({'a': ['x-y', 'y-z']}))
    table.currentcol = 0
    monkeypatch.setattr(core_orig, 'MultipleValDialog', lambda **kw:
        SimpleNamespace(result=True, results=[0, '', 1, '', '', '']))
    table.createCategorical()
    assert list(table.model.df.columns) == ['a', 'x-y', 'y-z']
    table.setSelectedCol(0)
    monkeypatch.setattr(core_orig, 'MultipleValDialog', lambda **kw:
        SimpleNamespace(result=True, results=['split', '-', 0, 0, '', '', 0]))
    table.applyStringMethod()
    assert table.model.df['a_0'].tolist() == ['x', 'y']
    assert table.model.df['a_1'].tolist() == ['y', 'z']


def test_undo_redo_and_history_are_independent(table):
    if not isinstance(table, MTable):
        return
    table.undo()
    table.redo()
    replace(table, pd.DataFrame({'a': [1]}))
    table.storeCurrent()
    table.model.df.iloc[0, 0] = 2
    table.undo()
    assert table.model.df.iloc[0, 0] == 1
    table.model.df.iloc[0, 0] = 7
    assert table.prevdf[0].iloc[0, 0] == 1
    table.redo()
    assert table.model.df.iloc[0, 0] == 2
    table.undo()
    assert table.model.df.iloc[0, 0] == 1


def test_filtered_edit_and_undo_keep_hidden_rows(table):
    full = pd.DataFrame({'x': [10, 20, 30]}, index=[100, 200, 300])
    replace(table, full)
    table.dataframe = table.model.df.copy()
    table.model.df = table.model.df.iloc[[2]].copy()
    table.filtered = True
    table.redraw()
    table.drawCellEntry(0, 0)
    table.cellentryvar.set('99')
    table.handleCellEntry(0, 0)
    assert table.dataframe.x.tolist() == [10, 20, 99]
    assert table.model.df.x.tolist() == [99]
    table.undo()
    assert_frame_equal(table.model.df, full)
    if isinstance(table, MTable):
        table.redo()
        assert table.model.df.x.tolist() == [10, 20, 99]


def test_filtered_ambiguous_index_fails_visibly_without_writes(table, monkeypatch):
    from unittest.mock import Mock
    full = pd.DataFrame({'x': [10, 20]}, index=[1, 1])
    replace(table, full)
    table.dataframe = table.model.df.copy()
    table.model.df = table.model.df.iloc[[1]].copy()
    table.filtered = True
    table.redraw()
    error = Mock()
    monkeypatch.setattr(core_orig.messagebox, 'showerror', error)
    table.drawCellEntry(0, 0)
    table.cellentryvar.set('99')
    table.handleCellEntry(0, 0)
    assert_frame_equal(table.dataframe, full)
    assert table.model.df.x.tolist() == [20]
    error.assert_called_once()


def test_category_edit_synchronizes_filtered_source(table):
    full = pd.DataFrame({'cat': pd.Categorical(['A', 'B', 'A'])})
    replace(table, full)
    table.dataframe = table.model.df.copy()
    table.model.df = table.model.df.iloc[[1]].copy()
    table.filtered = True
    table.redraw()
    table.handle_left_click(event(table))
    table.handle_left_release(event(table))
    table.dropvar.set('A')
    assert table.dataframe.cat.tolist() == ['A', 'A', 'A']
    assert table.model.df.cat.tolist() == ['A']


def test_filtered_bulk_changes_and_project_save_are_rejected_before_writes(table, monkeypatch, tmp_path):
    from unittest.mock import Mock
    full = pd.DataFrame({'x': [10, 20, 30]}, index=[100, 200, 300])
    replace(table, full)
    table.dataframe = full.copy()
    table.model.df = full.iloc[[2]].copy()
    table.filtered = True
    table.redraw()
    before = table.model.df.copy()
    warning = Mock()
    monkeypatch.setattr(core_orig.messagebox, 'showwarning', warning)
    calls = [('deleteCells', ([0], [0])), ('deleteRow', ()), ('deleteColumn', ()),
             ('paste', ()), ('sortTable', ()), ('setColumnType', ()),
             ('convertNumeric', ()), ('cleanData', ()), ('fillColumn', ()),
             ('addColumn', ()), ('saveAs', (str(tmp_path / 'filtered.pickle'),))]
    if isinstance(table, MTable):
        calls.extend((name, ()) for name in ['paste_header', 'stackColumn', 'splitColumn',
                                              'row1ToHeader', 'clearDataUp', 'sortSelected'])
    for method, args in calls:
        getattr(table, method)(*args)
        assert_frame_equal(table.model.df, before)
        assert_frame_equal(table.dataframe, full)
    assert warning.call_count == len(calls)
    assert not (tmp_path / 'filtered.pickle').exists()
    table.showAll()
    assert_frame_equal(table.model.df, full)


def test_filter_boundary_covers_duplicate_removal_merge_and_replace(table, monkeypatch):
    from unittest.mock import Mock
    from pandastable_local import dialogs
    from dialog import findRepDialog
    full = pd.DataFrame({'x': [1, 2, 2]})
    replace(table, full)
    table.dataframe = full.copy()
    table.model.df = full.iloc[[1, 2]].copy()
    table.filtered = True
    table.redraw()
    warning = Mock()
    monkeypatch.setattr(core_orig.messagebox, 'showwarning', warning)
    monkeypatch.setattr(core_orig, 'MultipleValDialog', lambda **kw:
        SimpleNamespace(result=True, results=[True, False, 'first']))
    table.findDuplicates()
    merge = SimpleNamespace(parent=table, result=pd.DataFrame({'x': [2, 2, 9]}))
    dialogs.CombineDialog.replaceTable(merge)
    for cls in [dialogs.FindReplaceDialog, findRepDialog]:
        cls.replace(SimpleNamespace(table=table))
    table.colheader.renameColumn()
    assert warning.call_count == 5
    assert_frame_equal(table.model.df, full.iloc[[1, 2]])
    assert_frame_equal(table.dataframe, full)


def test_arrow_selection_matches_copied_cell(table, monkeypatch):
    replace(table, pd.DataFrame({'a': [10, 20], 'b': [30, 40]}))
    table.handle_left_click(event(table))
    table.handle_arrow_keys(SimpleNamespace(keysym='Right'))
    assert (table.currentrow, table.currentcol) == (0, 1)
    assert table.multiplerowlist == [0]
    assert table.multiplecollist == [1]
    copied = []
    monkeypatch.setattr(pd.DataFrame, 'to_clipboard', lambda df, **kw: copied.append(df.copy()))
    table.copy(None)
    assert copied[0].iloc[0, 0] == 30
    table.handle_arrow_keys(SimpleNamespace(keysym='Down'))
    assert table.multiplerowlist == [1]
    assert table.multiplecollist == [1]


def test_original_project_save_open_uses_directory_and_clears_old_history(table, tmp_path, monkeypatch):
    original = pd.DataFrame({'x': [1.5, np.nan], 'text': ['中文', 'a,b']})
    replace(table, original)
    filename = tmp_path / '中文工程.pickle'
    table.saveAs(str(filename))
    assert filename.is_file()
    assert table.filename == str(filename)
    assert table.currentdir == str(tmp_path)
    table.storeCurrent()
    table.model.df = pd.DataFrame({'different': [99]})
    table.load(str(filename))
    assert table.prevdf is None
    assert_frame_equal(table.model.df, original)


def test_copy_preserves_text_in_mixed_column(table, monkeypatch):
    replace(table, pd.DataFrame({'mixed': ['1', '中文'], 'id': ['001', '002']}))
    table.selectAll()
    copied = []
    monkeypatch.setattr(pd.DataFrame, 'to_clipboard', lambda df, **kw: copied.append(df.copy()))
    table.copy(None)
    assert_frame_equal(copied[0], table.model.df)


def test_paste_rejects_malformed_rows_without_partial_write(table, monkeypatch):
    import io
    from unittest.mock import Mock
    original = pd.DataFrame({'a': [1], 'b': [2]})
    replace(table, original)
    error = Mock()
    monkeypatch.setattr(core_orig.messagebox, 'showwarning', error)
    def read_clipboard(**kwargs):
        return pd.read_csv(io.StringIO('a,b\n1,2\n3,4,5\n'), **kwargs)
    monkeypatch.setattr(pd, 'read_clipboard', read_clipboard)
    table.paste()
    assert_frame_equal(table.model.df, original)
    error.assert_called_once()


@pytest.mark.parametrize('rows,low,high', [(0, 1, 1), (1, 1, 5), (3, 2, 2), (3, 1, 3)])
def test_fill_linear_small_tables(table, monkeypatch, rows, low, high):
    import modified_table
    replace(table, pd.DataFrame({'a': np.zeros(rows)}))
    if isinstance(table, MTable):
        monkeypatch.setattr(modified_table, 'MultipleValDialog', lambda **kw:
            SimpleNamespace(result=True, results=[str(low), str(high), False, False,
                                                  'normal', 0., 1.]))
    else:
        monkeypatch.setattr(core_orig, 'MultipleValDialog', lambda **kw:
            SimpleNamespace(result=True, results=[str(low), str(high), False,
                                                  'normal', 0., 1.]))
    table.fillColumn()
    np.testing.assert_allclose(table.model.df.a,
                              np.linspace(low, high, rows, endpoint=isinstance(table, MTable)))


def test_resource_paths_do_not_depend_on_cwd(tmp_path, monkeypatch):
    from pandastable_local import core
    repo = Path(__file__).resolve().parents[1]
    assert Path(core.parent_path) == repo
    assert Path(config.configpath) == repo / 'user_config'
    monkeypatch.chdir(tmp_path)
    assert Path(config.write_default_config()) == repo / 'user_config/default.conf'


@pytest.mark.parametrize('column', [0, 1, 2])
def test_column_header_drag_resizes_first_middle_and_last_columns(visible_table, column):
    table = visible_table
    replace(table, pd.DataFrame({'a': [1], 'b': [2], 'c': [3]}))
    header = table.colheader
    old_widths = [table.col_positions[i + 1] - table.col_positions[i]
                  for i in range(table.cols)]
    edge = table.col_positions[column + 1]

    header_event_generate(table, '<Motion>', edge)
    header_event_generate(table, '<Button-1>', edge)
    header_event_generate(table, '<B1-Motion>', edge + 25, state=0x100)
    assert header.find_withtag('resizeline')
    assert table.find_withtag('resizeline')
    header_event_generate(table, '<ButtonRelease-1>', edge + 25)

    widths = [table.col_positions[i + 1] - table.col_positions[i]
              for i in range(table.cols)]
    assert widths[column] == old_widths[column] + 25
    assert [width for i, width in enumerate(widths) if i != column] == [
        width for i, width in enumerate(old_widths) if i != column]
    assert not header.find_withtag('resizeline')
    assert not table.find_withtag('resizeline')
    header_event_generate(table, '<Motion>', table.col_positions[column] + 10)
    assert header.cget('cursor') == ''
    header_event_generate(table, '<Motion>', table.col_positions[column + 1])
    header_event_generate(table, '<Leave>', table.col_positions[column + 1])
    assert not header.atdivider
    assert header.cget('cursor') == ''

    edge = table.col_positions[column + 1]
    before_width = edge - table.col_positions[column]
    header_event_generate(table, '<Motion>', edge - 3)
    header_event_generate(table, '<Button-1>', edge - 3)
    header_event_generate(table, '<B1-Motion>', edge - 2, state=0x100)
    header_event_generate(table, '<ButtonRelease-1>', edge - 2)
    assert table.col_positions[column + 1] - table.col_positions[column] == before_width + 1

    before = dict(table.columnwidths)
    edge = table.col_positions[1] + 3
    header_event_generate(table, '<Motion>', edge)
    header_event_generate(table, '<Button-1>', edge)
    header_event_generate(table, '<ButtonRelease-1>', edge)
    assert table.columnwidths == before
    assert header.atdivider
    assert header.cget('cursor') == 'sb_h_double_arrow'


def test_column_header_drag_clamps_width_and_survives_redraw_and_resize(visible_table):
    table = visible_table
    replace(table, pd.DataFrame({'a': [1], 'b': [2]}))
    table.mincellwidth = 35
    table.maxcellwidth = 150
    header = table.colheader

    def drag_first_column(target_x):
        edge = table.col_positions[1]
        header_event_generate(table, '<Motion>', edge)
        header_event_generate(table, '<Button-1>', edge)
        header_event_generate(table, '<B1-Motion>', target_x, state=0x100)
        header_event_generate(table, '<ButtonRelease-1>', target_x)

    drag_first_column(5)
    assert table.columnwidths['a'] == 35
    drag_first_column(400)
    assert table.columnwidths['a'] == 150

    table.redraw()
    header_event_generate(table, '<Button-1>', table.col_positions[1] + 20)
    header_event_generate(table, '<ButtonRelease-1>', table.col_positions[1] + 20)
    table.currwidth = table.parentframe.winfo_width() + 1
    table.parentframe.event_generate('<Configure>')
    table.parentframe.update()

    assert table.columnwidths['a'] == 150
    assert table.col_positions[1] - table.col_positions[0] == 150
    grid_x = [table.colheader.coords(item)[0]
              for item in table.colheader.find_withtag('gridline')]
    assert all(any(abs(x - pos) <= 1 for x in grid_x)
               for pos in table.col_positions[1:])


def test_column_header_drag_targets_correct_column_after_horizontal_scroll(visible_table):
    table = visible_table
    replace(table, pd.DataFrame({f'column_{i}': [i] for i in range(24)}))
    table.set_xviews('moveto', 0.6)
    header = table.colheader
    left = header.canvasx(0)
    right = header.canvasx(header.winfo_width())
    col = next(i for i, edge in enumerate(table.col_positions[1:])
               if left + 10 < edge < right - 40)
    edge = table.col_positions[col + 1]
    before = table.col_positions[col + 1] - table.col_positions[col]
    other_widths = [table.col_positions[i + 1] - table.col_positions[i]
                    for i in range(table.cols)]

    header_event_generate(table, '<Motion>', edge)
    header_event_generate(table, '<Button-1>', edge)
    header_event_generate(table, '<B1-Motion>', edge + 25, state=0x100)
    header_event_generate(table, '<ButtonRelease-1>', edge + 25)

    widths = [table.col_positions[i + 1] - table.col_positions[i]
              for i in range(table.cols)]
    assert widths[col] == before + 25
    assert [width for i, width in enumerate(widths) if i != col] == [
        width for i, width in enumerate(other_widths) if i != col]
    assert table.xview()[0] == pytest.approx(header.xview()[0])


def test_column_header_double_click_fits_font_measured_contents(visible_table, monkeypatch):
    from tkinter import font as tkfont
    from unittest.mock import Mock
    table = visible_table
    rename = Mock()
    monkeypatch.setattr(table.colheader, 'renameColumn', rename)
    dataframe = pd.DataFrame({
        '客户姓名': ['', None, '张晓明', '王小明'],
        'Timestamp': pd.to_datetime([
            '2025-01-02 03:04:05.123456', None,
            '2026-10-20 12:30:45.654321', '2024-09-08 08:00:00.000000']),
        '说明': ['简短', None, '', '长文本' * 100],
        '数值': [1e15, None, 1234.5, 1.2],
    })
    before = dataframe.copy(deep=True)
    replace(table, dataframe)
    table.mincellwidth = 35
    table.maxcellwidth = 220
    table.floatprecision = 2
    table.thousandseparator = ','
    for name in dataframe.columns:
        table.columnwidths[name] = table.cellwidth
    table.setColPositions()
    table.redraw()
    measure = tkfont.Font(root=table.winfo_toplevel(), font=table.thefont).measure

    for col, name in enumerate(dataframe.columns):
        values = dataframe[name].dropna()
        if name == '数值':
            values = values.apply(lambda value: table.setPrecision(value, 2))
        values = [str(value) for value in values]
        expected = max([measure(str(name))] + [measure(value) for value in values])
        edge = table.col_positions[col + 1]
        header_double_click(table, edge)
        rename.assert_not_called()
        width = table.col_positions[col + 1] - table.col_positions[col]
        assert min(expected, table.maxcellwidth) <= width <= table.maxcellwidth

    assert table.columnwidths['说明'] == table.maxcellwidth
    assert_frame_equal(table.model.df, before)

    later_text = pd.DataFrame({'长文本': ['短'] * 200 + ['末尾文本' * 100]})
    replace(table, later_text)
    table.columnwidths['长文本'] = table.cellwidth
    table.setColPositions()
    table.redraw()
    header_double_click(table, table.col_positions[1])
    rename.assert_not_called()
    assert table.columnwidths['长文本'] == table.maxcellwidth
    assert_frame_equal(table.model.df, later_text)

    long_label = '第二级长标题' * 2
    multi = pd.DataFrame([[1, 2]], columns=pd.MultiIndex.from_tuples([
        ('组一', long_label), ('组二', '短')]))
    replace(table, multi)
    table.columnwidths[str(multi.columns[0])] = table.cellwidth
    table.setColPositions()
    table.redraw()
    header_double_click(table, table.col_positions[1])
    rename.assert_not_called()
    assert table.columnwidths[str(multi.columns[0])] >= measure(long_label)
    rename.assert_not_called()
    header_text = [table.colheader.itemcget(item, 'text')
                   for item in table.colheader.find_withtag('text')]
    assert long_label in header_text
    assert_frame_equal(table.model.df, multi)


def test_column_header_body_double_click_rename_and_multiselect_context_menu(visible_table, monkeypatch):
    from unittest.mock import Mock
    table = visible_table
    replace(table, pd.DataFrame({f'column_{i}': [i] for i in range(4)}))
    header = table.colheader
    rename = Mock()
    popup = Mock(return_value=SimpleNamespace(destroy=Mock()))
    monkeypatch.setattr(header, 'renameColumn', rename)
    monkeypatch.setattr(header, 'popupMenu', popup)

    selected_x = (table.col_positions[1] + table.col_positions[2]) / 2
    header_event_generate(table, '<Button-1>', selected_x)
    header_event_generate(table, '<ButtonRelease-1>', selected_x)
    assert table.currentcol == 1
    assert header.resizecol is None

    body_x = (table.col_positions[0] + table.col_positions[1]) / 2
    header_double_click(table, body_x)
    rename.assert_called_once_with()

    edge = table.col_positions[1]
    header_event_generate(table, '<Motion>', edge)
    header_event_generate(table, '<Button-3>', edge)
    assert table.currentcol == 0
    assert header.find_withtag('rect')

    first_x = (table.col_positions[0] + table.col_positions[1]) / 2
    third_x = (table.col_positions[2] + table.col_positions[3]) / 2
    fourth_x = (table.col_positions[3] + table.col_positions[4]) / 2
    header_event_generate(table, '<Button-1>', first_x)
    header_event_generate(table, '<ButtonRelease-1>', first_x)
    header_event_generate(table, '<Control-Button-1>', third_x)
    assert 2 in table.multiplecollist
    current = table.currentcol
    header_event_generate(table, '<Shift-Button-1>', fourth_x)
    assert table.multiplecollist == list(range(min(current, 3), max(current, 3) + 1))

    table.enable_menus = True
    header_event_generate(table, '<Button-3>', fourth_x)
    popup.assert_called()
    assert table.multiplecollist == list(range(min(current, 3), max(current, 3) + 1))
