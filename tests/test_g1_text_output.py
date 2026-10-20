"""使用真实 Tk 控件验证文本结果窗口，文件对话框保持非交互。"""
from types import SimpleNamespace
from unittest.mock import Mock
import tkinter as tk

import pytest

import txt_output
from plots import plot_viewer
from utilities import gen_table


@pytest.fixture
def viewer(tk_root):
    window = txt_output.txt_viewer(SimpleNamespace(tOut=None))
    window.main.update()
    yield window
    if window.main.winfo_exists():
        window.close()


def test_real_font_and_table_column_pixel_alignment(viewer):
    table = gen_table([['项目 Item', '估计值', '备注'],
                       ['均值 Mean', '1.23', '中文 ABC'], ['标准差 SD', '.456', '测试']])
    viewer.add_txt(str(table))
    viewer.main.update()
    assert str(viewer.T.cget('wrap')) == 'none'
    assert viewer.main.title() == 'Minijmp - 统计结果'
    assert viewer.output_font.measure('中') == 2 * viewer.output_font.measure('0')
    assert viewer.output_font.measure('i') == viewer.output_font.measure('W')
    positions = []
    for row, line in enumerate(str(table).splitlines(), 1):
        if '|' in line:
            positions.append([viewer.T.bbox(f'{row}.{col}')[0]
                              for col, char in enumerate(line) if char == '|'])
    assert all(columns == positions[0] for columns in positions)


@pytest.mark.parametrize('geometry', ['480x320', '1000x750'])
def test_wide_long_output_scrolls_without_wrapping_or_hiding_controls(viewer, geometry):
    viewer.main.geometry(geometry)
    content = str(gen_table([['项目', '内容'], ['长行', '中文 ABC ' * 60]])) + '\n'
    viewer.add_txt(content * 100)
    viewer.main.update()
    assert viewer.T.xview()[1] < 1
    assert viewer.T.yview()[1] < 1
    viewer.hsb.tk.call(viewer.hsb.cget('command'), 'moveto', .5)
    viewer.main.update()
    assert viewer.T.xview()[0] > 0
    viewer.vsb.tk.call(viewer.vsb.cget('command'), 'moveto', .5)
    assert viewer.T.yview()[0] > 0
    viewer.to_end()
    assert viewer.T.yview()[1] == 1
    assert viewer.ctrlfr.winfo_ismapped()
    assert viewer.ctrlfr.winfo_y() + viewer.ctrlfr.winfo_height() <= viewer.main.winfo_height()
    assert viewer.T.get('1.0', 'end-1c') == content * 100


def test_save_utf8_cancel_clear_and_copy_selection(viewer, tmp_path, monkeypatch):
    content = '统计结果 μ = 1.23\n中文 English\n'
    viewer.add_txt(content)
    target = tmp_path / '中文结果.txt'
    dialog = Mock(return_value=str(target))
    monkeypatch.setattr(txt_output.filedialog, 'asksaveasfilename', dialog)
    viewer.save()
    assert target.read_bytes().decode('utf-8').replace('\r\n', '\n') == content
    assert viewer.currentdir == str(tmp_path)
    assert dialog.call_args.kwargs['defaultextension'] == '.txt'
    viewer.select_all()
    assert viewer.T.get('sel.first', 'sel.last') == content
    # 验证原生复制事件及选择范围，不覆盖用户系统剪贴板。
    copied = []
    def intercept_copy(event):
        copied.append(viewer.T.get('sel.first', 'sel.last'))
        return 'break'
    viewer.T.bind('<<Copy>>', intercept_copy)
    buttons = viewer.ctrlfr.winfo_children()[0].winfo_children()
    next(button for button in buttons if button.cget('text') == '复制').invoke()
    assert copied == [content]
    dialog.return_value = ''
    viewer.save()
    assert target.read_text(encoding='utf-8') == content
    assert viewer.currentdir == str(tmp_path)
    next(button for button in buttons if button.cget('text') == '清空').invoke()
    assert viewer.T.get('1.0', 'end-1c') == ''


def test_save_failure_keeps_content_and_reports_error(viewer, tmp_path, monkeypatch):
    viewer.add_txt('保留结果')
    error = Mock()
    monkeypatch.setattr(txt_output.messagebox, 'showerror', error)
    viewer.save(tmp_path / '不存在的目录' / '结果.txt')
    error.assert_called_once()
    assert error.call_args.args[0] == '保存失败'
    assert viewer.T.get('1.0', 'end-1c') == '保留结果'


def test_real_theme_switch_keeps_text_font_and_selection(viewer):
    style = viewer.ui_style
    original = style.theme_use()
    viewer.add_txt('中文表格 English\n123')
    viewer.select_all()
    original_font = viewer.T.cget('font')
    try:
        for name, background, foreground in [('g1-dark', '#202020', '#eeeeee'),
                                              ('g1-light', '#ffffff', '#111111')]:
            if name not in style.theme_names():
                style.theme_create(name, parent='clam', settings={
                    'TEntry': {'configure': {'fieldbackground': background}},
                    'TLabel': {'configure': {'foreground': foreground}}})
            style.theme_use(name)
            viewer.main.update()
            assert viewer.T.cget('background') == background
            assert viewer.T.cget('foreground') == foreground
            assert viewer.T.cget('font') == original_font
            assert viewer.T.get('sel.first', 'sel.last') == '中文表格 English\n123'
    finally:
        style.theme_use(original)
        viewer._apply_theme()


def test_font_unavailable_uses_tk_fixed_font(tk_root, monkeypatch):
    monkeypatch.setattr(txt_output.font, 'families', lambda root: ())
    host = tk.Frame(tk_root)
    window = txt_output.txt_viewer(None, parent=host)
    try:
        default = txt_output.font.nametofont('TkFixedFont', root=tk_root)
        assert window.output_font.actual() == default.actual()
    finally:
        window.close()


@pytest.mark.parametrize('scaling', [1, 1.33333, 2, 2.66667])
def test_cjk_font_alignment_at_different_dpi(tk_root, scaling):
    original = tk_root.tk.call('tk', 'scaling')
    window = None
    try:
        tk_root.tk.call('tk', 'scaling', scaling)
        window = txt_output.txt_viewer(None)
        assert window.output_font.measure('中') == 2 * window.output_font.measure('0')
        assert window.output_font.measure('i') == window.output_font.measure('W')
    finally:
        if window is not None:
            window.close()
        tk_root.tk.call('tk', 'scaling', original)


def test_close_releases_reference_without_debug_output(viewer, capsys):
    capsys.readouterr()
    table = viewer.table
    viewer.close()
    assert table.tOut is None
    assert not viewer.main.winfo_exists()
    assert capsys.readouterr().out == ''


def test_plot_open_close_keeps_figure_lifecycle_without_debug_output(tk_root, capsys):
    host = tk.Frame(tk_root)
    table = SimpleNamespace(pf=None)
    capsys.readouterr()
    window = plot_viewer(table, parent=host)
    window.close()
    assert table.pf is None
    assert not host.winfo_exists()
    assert capsys.readouterr().out == ''
