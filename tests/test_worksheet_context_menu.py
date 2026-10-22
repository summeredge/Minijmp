"""Real Tk checks for worksheet-tab context menu ownership."""
import tkinter as tk

import pandas as pd
import pytest

from modified_table import MTable
from test_csv_import import csv_app
import worksheets


@pytest.fixture
def visible_workbook(csv_app):
    app, error = csv_app
    app.main.deiconify()
    app.main.update()
    yield app, error
    if app.nb.winfo_exists():
        app._sheet_context_menu.unpost()
    app.main.withdraw()


def tab_point(notebook, index):
    notebook.update_idletasks()
    y = min(10, notebook.winfo_height() - 1)
    for x in range(notebook.winfo_width()):
        try:
            if notebook.index(f'@{x},{y}') == index:
                return x, y
        except tk.TclError:
            pass
    raise AssertionError(f'找不到第 {index} 个工作表标签')


def right_click(app, point):
    menu = app._sheet_context_menu
    popup_calls = []
    menu.tk_popup = lambda *coords: popup_calls.append(coords)
    x, y = point
    app.nb.event_generate('<Button-3>', x=x, y=y,
                          rootx=app.nb.winfo_rootx() + x,
                          rooty=app.nb.winfo_rooty() + y, when='tail')
    app.main.update()
    return menu, popup_calls


def menu_index(menu, label):
    for index in range(menu.index('end') + 1):
        if menu.type(index) == 'command' and menu.entrycget(index, 'label') == label:
            return index
    raise AssertionError(f'菜单缺少“{label}”')


def test_context_menu_requires_tab_hit_and_cancel_has_no_effect(visible_workbook):
    app, error = visible_workbook
    first_frame = app.sheetframes['工作表1']
    app.addSheet('目标', pd.DataFrame({'值': [1]}))
    app.nb.select(first_frame)
    app.main.update()

    target_point = tab_point(app.nb, app.nb.index(app.sheetframes['目标']))
    menu, popup_calls = right_click(app, target_point)
    assert len(popup_calls) == 1
    assert app.getCurrentSheet() == '工作表1'
    assert [menu.entrycget(i, 'label') for i in range(menu.index('end') + 1)
            if menu.type(i) == 'command'] == [
                '新增工作表', '复制工作表', '重命名工作表', '删除工作表', '导出当前工作表']

    assert app.getCurrentSheet() == '工作表1'

    x, y = target_point
    blank_x = app.nb.winfo_width() - 2
    with pytest.raises(tk.TclError):
        app.nb.index(f'@{blank_x},{y}')
    _, blank_popup_calls = right_click(app, (blank_x, y))
    assert blank_popup_calls == []
    assert app.getCurrentSheet() == '工作表1'
    error.assert_not_called()


@pytest.mark.parametrize('label', [
    '新增工作表', '复制工作表', '重命名工作表', '删除工作表', '导出当前工作表',
])
def test_context_menu_actions_use_right_clicked_sheet(visible_workbook, monkeypatch, tmp_path, label):
    app, error = visible_workbook
    first_frame = app.sheetframes['工作表1']
    target = app.addSheet('目标', pd.DataFrame({'值': [7, 8]}))
    target_frame = app.sheetframes['目标']
    app.nb.select(first_frame)
    app.main.update()
    observed = []

    if label == '新增工作表':
        original = app.addSheet

        def add_sheet(*args, **kwargs):
            observed.append(app.getCurrentSheet())
            return original(*args, **kwargs)

        monkeypatch.setattr(app, 'addSheet', add_sheet)
    elif label == '复制工作表':
        original = app.copySheet

        def copy_sheet():
            observed.append(app.getCurrentSheet())
            return original()

        monkeypatch.setattr(app, 'copySheet', copy_sheet)
    elif label == '重命名工作表':
        monkeypatch.setattr(worksheets.simpledialog, 'askstring',
                            lambda *a, **k: (observed.append(app.getCurrentSheet()) or '目标改名'))
    elif label == '删除工作表':
        monkeypatch.setattr(worksheets.messagebox, 'askyesno',
                            lambda title, message, **k: (observed.append((app.getCurrentSheet(), message)) or True))
    else:
        saved = []
        monkeypatch.setattr(worksheets.filedialog, 'asksaveasfilename',
                            lambda **k: str(tmp_path / 'unused.pickle'))
        monkeypatch.setattr(MTable, 'saveAs', lambda table, filename: saved.append((table, filename)))

    menu, popup_calls = right_click(app, tab_point(app.nb, app.nb.index(target_frame)))
    assert len(popup_calls) == 1
    menu.invoke(menu_index(menu, label))
    app.main.update()

    if label == '新增工作表':
        assert observed == ['目标']
        assert app.getCurrentSheet() == '工作表'
    elif label == '复制工作表':
        assert observed == ['目标']
        assert app.getCurrentSheet() == '目标 副本'
        assert app.table.model.df.equals(target.model.df)
    elif label == '重命名工作表':
        assert observed == ['目标']
        assert '目标改名' in app.sheets and '工作表1' in app.sheets
    elif label == '删除工作表':
        assert observed[0][0] == '目标'
        assert '目标' not in app.sheets and '工作表1' in app.sheets
    else:
        assert len(saved) == 1 and saved[0][0] is target
        assert app.getCurrentSheet() == '目标'
    error.assert_not_called()


def test_delete_confirmation_cancel_and_last_sheet_replacement(visible_workbook, monkeypatch):
    app, error = visible_workbook
    original = app.table
    point = tab_point(app.nb, app.nb.index(app.sheetframes['工作表1']))
    menu, popup_calls = right_click(app, point)
    assert len(popup_calls) == 1

    monkeypatch.setattr(worksheets.messagebox, 'askyesno', lambda *a, **k: False)
    menu.invoke(menu_index(menu, '删除工作表'))
    menu.unpost()
    app.main.update()
    assert list(app.sheets) == ['工作表1']
    assert app.table is original

    monkeypatch.setattr(worksheets.messagebox, 'askyesno', lambda *a, **k: True)
    menu, popup_calls = right_click(app, point)
    assert len(popup_calls) == 1
    menu.invoke(menu_index(menu, '删除工作表'))
    app.main.update()
    assert len(app.sheets) == len(app.nb.tabs()) == 1
    assert app.table is not original
    assert app.getCurrentSheet() == '工作表'
    error.assert_not_called()
