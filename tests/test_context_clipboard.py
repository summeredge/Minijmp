from types import SimpleNamespace
import tkinter as tk

import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from modified_table import MTable
from pandastable_local.data import TableModel


@pytest.fixture
def unposted_menus(monkeypatch):
    monkeypatch.setattr(tk.Menu, 'post', lambda self, *args: None)


@pytest.fixture
def table(tk_root, unposted_menus):
    frame = tk.Frame(tk_root)
    frame.pack(fill='both', expand=True)
    data = pd.DataFrame([[1, 2, 3], [4, 5, 6], [7, 8, 9]])
    widget = MTable(frame, dataframe=data, showtoolbar=False, showstatusbar=False)
    widget.show()
    tk_root.update()
    widget.setColPositions()
    widget.redraw()
    yield widget
    frame.destroy()


def replace(table, dataframe):
    table.updateModel(TableModel(dataframe=dataframe.copy()))
    table.redraw()


def cell_event(table, row, col):
    x = int(table.col_positions[col] + 5)
    y = int(table.y_start + table.rowheight * row + 3)
    return SimpleNamespace(x=x, y=y, x_root=10, y_root=10)


def row_event(table, row):
    return SimpleNamespace(x=5, y=int(table.y_start + table.rowheight * row + 3),
                           x_root=10, y_root=10)


def menu_labels(menu):
    return [menu.entrycget(index, 'label')
            for index in range(menu.index('end') + 1)
            if menu.type(index) in ('command', 'cascade')]


def invoke(menu, label):
    index = next(index for index in range(menu.index('end') + 1)
                 if menu.type(index) == 'command' and menu.entrycget(index, 'label') == label)
    menu.invoke(index)


def test_cell_context_menu_and_right_click_selection(table):
    table.multiplecollist = [0, 1]
    table.multiplerowlist = [0, 1]
    table.currentrow, table.currentcol = 0, 0
    table.handle_right_click(cell_event(table, 1, 1))
    assert table.multiplerowlist == [0, 1]
    assert table.multiplecollist == [0, 1]
    assert menu_labels(table.rightmenu) == ['复制所选', '粘贴', '撤销', '清除所选', '公式']

    table.handle_right_click(cell_event(table, 2, 2))
    assert table.multiplerowlist == [2]
    assert table.multiplecollist == [2]
    assert (table.currentrow, table.currentcol) == (2, 2)
    assert menu_labels(table.rightmenu) == ['复制所选', '粘贴', '撤销', '清除所选', '公式']

    table.enable_menus = False
    table.rightmenu.destroy()
    table.rightmenu = None
    table.handle_right_click(cell_event(table, 0, 0))
    assert table.rightmenu is None


def test_tsv_copy_paste_preserves_empty_chinese_commas_tabs_and_newlines(table, monkeypatch):
    original = pd.DataFrame([
        ['中文,逗号', np.nan, '保留'],
        ['含\t制表', '换行\n文本', '保留2'],
        ['尾行', '尾列', '保留3'],
    ], dtype=object)
    replace(table, original)
    written = []
    monkeypatch.setattr(table, 'clipboard_clear', lambda: None)
    monkeypatch.setattr(table, 'clipboard_append', written.append)
    assert table.copy_context_selection([0, 1], [0, 1])
    payload = written[0]
    assert '\t' in payload and '中文,逗号' in payload and '含\t制表' in payload
    monkeypatch.setattr(table, 'clipboard_get', lambda: payload)

    assert table.paste_context_selection('cell', [1, 2], [1, 2])
    result = table.model.df
    assert result.iat[1, 1] == '中文,逗号'
    assert pd.isna(result.iat[1, 2])
    assert result.iat[2, 1] == '含\t制表'
    assert result.iat[2, 2] == '换行\n文本'
    table.undo()
    assert_frame_equal(table.model.df, original)

    monkeypatch.setattr(table, 'clipboard_get', lambda: '逗号,仍在一个单元格')
    assert table.paste_context_selection('cell', [0], [0])
    assert table.model.df.iat[0, 0] == '逗号,仍在一个单元格'
    table.undo()
    assert_frame_equal(table.model.df, original)


def test_csv_shape_compatibility_and_rejections_are_atomic(table, monkeypatch):
    original = pd.DataFrame([[1, 2], [3, 4]])
    replace(table, original)
    warnings = []
    monkeypatch.setattr('modified_table.messagebox.showwarning',
                        lambda *args, **kwargs: warnings.append(args[1]))
    monkeypatch.setattr(table, 'clipboard_get', lambda: '9,8\n7,6')
    assert table.paste_context_selection('cell', [0, 1], [0, 1])
    assert table.model.df.values.tolist() == [[9, 8], [7, 6]]
    table.undo()
    assert_frame_equal(table.model.df, original)

    monkeypatch.setattr(table, 'clipboard_get', lambda: '')
    assert table.paste_context_selection('cell', [0], [0])
    assert pd.isna(table.model.df.iat[0, 0])
    table.undo()
    assert_frame_equal(table.model.df, original)

    table.multiplerowlist = [0, 1]
    table.multiplecollist = [0, 1]
    monkeypatch.setattr(table, 'clipboard_get', lambda: '99')
    assert not table.paste_context_selection('cell', [0, 1], [0, 1])
    assert_frame_equal(table.model.df, original)
    assert table.prevdf is None or table.prevdf_end == 0

    monkeypatch.setattr(table, 'clipboard_get', lambda: '10\t11')
    assert not table.paste_context_selection('cell', [1], [1])
    assert_frame_equal(table.model.df, original)

    monkeypatch.setattr(table, 'clipboard_get', lambda: '中文')
    assert not table.paste_context_selection('cell', [0], [0])
    assert_frame_equal(table.model.df, original)
    assert len(warnings) == 3


def test_row_column_header_menus_copy_and_paste_multiple_targets(table, monkeypatch):
    original = pd.DataFrame([
        ['a0', 'b0', 'c0'], ['a1', 'b1', 'c1'], ['a2', 'b2', 'c2']
    ])
    replace(table, original)
    written = []
    monkeypatch.setattr(table, 'clipboard_clear', lambda: None)
    monkeypatch.setattr(table, 'clipboard_append', written.append)
    table.multiplecollist = [0, 2]
    table.currentcol = 0
    table.colheader.handle_right_click(cell_event(table, 0, 2))
    colmenu = table.colheader.rightmenu
    labels = menu_labels(colmenu)
    assert '复制整列' in labels and '粘贴整列' in labels
    assert '删除列' in labels and '重命名列' in labels and '设置数据类型' in labels
    invoke(colmenu, '复制整列')
    assert written[-1].splitlines() == ['a0\tc0', 'a1\tc1', 'a2\tc2']
    monkeypatch.setattr(table, 'clipboard_get', lambda: 'x0\tz0\nx1\tz1\nx2\tz2')
    invoke(colmenu, '粘贴整列')
    assert table.model.df.iloc[:, [0, 2]].values.tolist() == [
        ['x0', 'z0'], ['x1', 'z1'], ['x2', 'z2']]
    assert len(table.colheader.find_withtag('rect')) == 2

    replace(table, original)
    table.multiplerowlist = [0, 2]
    table.currentrow = 0
    table.rowheader.handle_right_click(row_event(table, 2))
    rowmenu = table.rowheader.rightmenu
    assert '复制行' in menu_labels(rowmenu)
    assert '复制整行' in menu_labels(rowmenu) and '粘贴整行' in menu_labels(rowmenu)
    invoke(rowmenu, '复制整行')
    assert written[-1].splitlines() == ['a0\tb0\tc0', 'a2\tb2\tc2']

    monkeypatch.setattr(table, 'clipboard_get', lambda: 'r0\ts0\tt0\nr2\ts2\tt2')
    invoke(rowmenu, '粘贴整行')
    assert table.model.df.iloc[[0, 2]].values.tolist() == [
        ['r0', 's0', 't0'], ['r2', 's2', 't2']]
    assert len(table.rowheader.find_withtag('rect')) == 2

    before_rows = len(table.model.df)
    invoke(rowmenu, '复制行')
    assert len(table.model.df) == before_rows + 2
    assert written[-1].splitlines() == ['a0\tb0\tc0', 'a2\tb2\tc2']


def test_column_header_formula_menu_targets_clicked_column(table, monkeypatch):
    table.multiplecollist = [0, 2]
    table.currentcol = 0
    table.formulas_auto = False
    calls = []
    for method in ('assign_column_formula', 'edit_column_formula',
                   'view_column_formula', 'delete_column_formula',
                   'recalculate_formulas'):
        monkeypatch.setattr(
            table, method,
            lambda method=method: calls.append((method, table.currentcol)))
    monkeypatch.setattr(table, 'refresh_formulas', lambda force: None)
    monkeypatch.setattr(table, 'redraw', lambda: None)
    monkeypatch.setattr(table, 'tableChanged', lambda: None)

    table.colheader.handle_right_click(cell_event(table, 0, 2))
    menu = table.colheader.rightmenu
    assert menu_labels(menu) == [
        '按 0,2 升序排序全表 ↓', '按 0,2 降序排序全表 ↑',
        '复制整列', '粘贴整列', '删除列', '重命名列', '添加列', '公式',
        '设置对齐方式', '填充数据', '设置数据类型']
    assert table.multiplecollist == [0, 2]
    assert table.currentcol == 0

    formula_menu = menu.nametowidget(menu.entrycget('公式', 'menu'))
    formula_labels = [
        formula_menu.entrycget(index, 'label')
        for index in range(formula_menu.index('end') + 1)
        if formula_menu.type(index) in ('command', 'checkbutton')]
    assert formula_labels == [
        '向列分配公式', '编辑列公式', '查看列公式', '删除列公式',
        '自动计算所有公式', '立即计算所有公式']
    assert [formula_menu.type(index)
            for index in range(formula_menu.index('end') + 1)] == [
                'command', 'command', 'command', 'command', 'separator',
                'checkbutton', 'command']
    assert not table._formula_auto_var().get()

    for label in formula_labels[:4]:
        invoke(formula_menu, label)
    assert calls[:4] == [
        ('assign_column_formula', 2), ('edit_column_formula', 2),
        ('view_column_formula', 2), ('delete_column_formula', 2)]

    auto_index = next(
        index for index in range(formula_menu.index('end') + 1)
        if formula_menu.type(index) == 'checkbutton')
    formula_menu.invoke(auto_index)
    assert table.formulas_auto and table._formula_auto_var().get()
    invoke(formula_menu, '立即计算所有公式')
    assert calls[-1] == ('recalculate_formulas', 2)


def test_keyboard_copy_paste_respects_row_and_column_headers(table, monkeypatch):
    original = pd.DataFrame([
        ['a0', 'b0', 'c0'], ['a1', 'b1', 'c1'], ['a2', 'b2', 'c2']
    ])
    replace(table, original)
    written = []
    monkeypatch.setattr(table, 'clipboard_clear', lambda: None)
    monkeypatch.setattr(table, 'clipboard_append', written.append)

    table.multiplerowlist, table.multiplecollist = [0], [1]
    table.allrows = True
    table.rowheader.handle_left_click(row_event(table, 2))
    assert table.multiplerowlist == [2]
    assert table.multiplecollist == [] and not table.allrows
    assert table.bind('<Control-c>')
    assert table.copy(SimpleNamespace(widget=table))
    assert written[-1] == 'a2\tb2\tc2\n'

    monkeypatch.setattr(table, 'clipboard_get', lambda: 'r2\ts2\tt2')
    assert table.bind('<Control-v>')
    assert table.paste(SimpleNamespace(widget=table))
    assert table.model.df.iloc[2].tolist() == ['r2', 's2', 't2']

    table.multiplerowlist, table.multiplecollist = [], []
    table.allrows = False
    table.colheader.handle_left_click(cell_event(table, 0, 1), allow_resize=False)
    assert table.multiplecollist == [1] and table.allrows
    monkeypatch.setattr(table, 'clipboard_get', lambda: 'x0\nx1\nx2')
    assert table.paste(SimpleNamespace(widget=table))
    assert table.model.df.iloc[:, 1].tolist() == ['x0', 'x1', 'x2']
    assert len(table.colheader.find_withtag('rect')) == 1


@pytest.mark.parametrize(
    'axis,selection,payload,expected',
    [
        ('column', [0, 2], '10\n20', None),
        ('column', [1], '10\t20', None),
        ('row', [0, 2], '10\t11\t12', None),
        ('row', [1], '10\t11\t12\n20\t21\t22', None),
        ('column', [1], '10\n20', None),
        ('row', [1], '10\t11', None),
        ('column', [0, 2], '10\t30\n40\t60\n70\t90',
         [[10, 2, 30], [40, 5, 60], [70, 8, 90]]),
        ('row', [0, 2], '10\t11\t12\n20\t21\t22',
         [[10, 11, 12], [4, 5, 6], [20, 21, 22]]),
    ],
)
def test_row_column_context_paste_requires_exact_shape_and_is_atomic(
        table, monkeypatch, axis, selection, payload, expected):
    original = pd.DataFrame([[1, 2, 3], [4, 5, 6], [7, 8, 9]])
    replace(table, original)
    warnings = []
    monkeypatch.setattr('modified_table.messagebox.showwarning',
                        lambda *args, **kwargs: warnings.append(args[1]))
    monkeypatch.setattr(table, 'clipboard_get', lambda: payload)
    history_before = (None if table.prevdf is None
                      else [frame.copy(deep=True) for frame in table.prevdf])
    history_end_before = getattr(table, 'prevdf_end', None)
    rows, cols = ((list(range(len(original))), selection) if axis == 'column'
                  else (selection, list(range(len(original.columns)))))

    pasted = table.paste_context_selection(axis, rows=rows, cols=cols)
    if expected is None:
        assert not pasted
        assert_frame_equal(table.model.df, original)
        assert getattr(table, 'prevdf_end', None) == history_end_before
        if history_before is None:
            assert table.prevdf is None
        else:
            assert len(table.prevdf) == len(history_before)
            for actual, before in zip(table.prevdf, history_before):
                assert_frame_equal(actual, before)
        assert warnings and '剪贴板' in warnings[-1]
        return

    assert pasted
    assert not warnings
    assert_frame_equal(table.model.df, pd.DataFrame(expected))
    if axis == 'column':
        assert_frame_equal(table.model.df.iloc[:, [1]], original.iloc[:, [1]])
    else:
        assert_frame_equal(table.model.df.iloc[[1]], original.iloc[[1]])
    assert table.prevdf is not None
    table.undo()
    assert_frame_equal(table.model.df, original)


def test_context_paste_rejects_out_of_bounds_target_without_history(table, monkeypatch):
    original = pd.DataFrame([[1, 2, 3], [4, 5, 6], [7, 8, 9]])
    replace(table, original)
    warnings = []
    monkeypatch.setattr('modified_table.messagebox.showwarning',
                        lambda *args, **kwargs: warnings.append(args[1]))
    monkeypatch.setattr(table, 'clipboard_get', lambda: '10\t20\n30\t40\n50\t60')

    assert not table.paste_context_selection('column', cols=[0, 3])
    assert_frame_equal(table.model.df, original)
    assert table.prevdf is None
    assert warnings and '超出工作表范围' in warnings[-1]


def test_cell_menu_paste_and_clear_are_undoable(table, monkeypatch):
    original = pd.DataFrame([[1, 2], [3, 4]])
    replace(table, original)
    monkeypatch.setattr(table, 'clipboard_get', lambda: '42')
    table.handle_right_click(cell_event(table, 1, 1))
    invoke(table.rightmenu, '粘贴')
    assert table.model.df.iat[1, 1] == 42

    table.handle_right_click(cell_event(table, 1, 1))
    invoke(table.rightmenu, '撤销')
    assert_frame_equal(table.model.df, original)

    monkeypatch.setattr('modified_table.messagebox.askyesno', lambda *args, **kwargs: True)
    table.handle_right_click(cell_event(table, 0, 0))
    invoke(table.rightmenu, '清除所选')
    assert pd.isna(table.model.df.iat[0, 0])
    table.handle_right_click(cell_event(table, 0, 0))
    invoke(table.rightmenu, '撤销')
    assert_frame_equal(table.model.df, original)


def test_empty_paste_preserves_unselected_large_integers_and_undo(table, monkeypatch):
    original = pd.DataFrame({'value': np.array([2**60 + 1, 2**60 + 3], dtype=np.int64)})
    replace(table, original)
    monkeypatch.setattr(table, 'clipboard_get', lambda: '')

    assert table.paste_context_selection('cell', [0], [0])

    assert pd.isna(table.model.df.iloc[0, 0])
    assert table.model.df.iloc[1, 0] == 2**60 + 3
    assert table.model.df['value'].dtype == pd.Int64Dtype()
    table.undo()
    assert_frame_equal(table.model.df, original)


def test_invalid_cell_type_paste_is_atomic(table, monkeypatch):
    original = pd.DataFrame({
        'text': pd.Series(['keep'], dtype='string'),
        'category': pd.Categorical(['A'], categories=['A', 'B']),
    })
    replace(table, original)
    warnings = []
    monkeypatch.setattr(table, 'clipboard_get', lambda: 'changed\tunknown')
    monkeypatch.setattr('modified_table.messagebox.showwarning',
                        lambda *args, **kwargs: warnings.append(args[1]))

    assert not table.paste_context_selection('cell', [0], [0, 1])

    assert_frame_equal(table.model.df, original)
    assert table.prevdf is None
    assert warnings


@pytest.mark.parametrize('filtered,editable', [(True, True), (False, False)])
def test_readonly_and_filter_protect_context_paste_and_clear(table, monkeypatch, filtered, editable):
    original = table.model.df.copy()
    table.filtered = filtered
    if filtered:
        table.dataframe = original.copy()
    table.editable = editable
    monkeypatch.setattr(table, 'clipboard_get', lambda: '88')
    monkeypatch.setattr('modified_table.messagebox.showwarning', lambda *args, **kwargs: None)
    table.clear_context_selection([0], [0])
    assert not table.paste_context_selection('cell', [0], [0])
    assert_frame_equal(table.model.df, original)


@pytest.mark.parametrize('shape', [(0, 2), (2, 0), (0, 0)])
def test_context_copy_paste_leave_empty_tables_unchanged(table, monkeypatch, shape):
    original = pd.DataFrame(index=range(shape[0]), columns=range(shape[1]))
    replace(table, original)
    warnings = []
    monkeypatch.setattr('modified_table.messagebox.showwarning',
                        lambda *args, **kwargs: warnings.append(args[1]))
    monkeypatch.setattr(table, 'clipboard_get', lambda: '1\t2')
    assert not table.copy_context_selection()
    assert not table.paste_context_selection('cell', [0], [0])
    assert_frame_equal(table.model.df, original)
    assert warnings
