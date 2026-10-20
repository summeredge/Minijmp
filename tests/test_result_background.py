"""统计结果公共组件的白底及主题隔离回归。"""
from tkinter import ttk

import pytest

from stat_table import RESULT_BACKGROUND
from test_g1_text_output import viewer
from test_g8_tables import report as descriptive_report, CASES as DESCRIPTIVE_CASES
from test_g9_tables import report as hypothesis_report, DIRECT
from stat_table import StatTable


def assert_white(widget, style):
    if isinstance(widget, (ttk.Frame, ttk.Label, ttk.Menubutton)):
        name = widget.cget('style')
        assert name.startswith('Result.')
        for state in ((), ('active',), ('pressed',), ('disabled',), ('focus',)):
            assert style.lookup(name, 'background', state) == '#FFFFFF'
    for child in widget.winfo_children():
        assert_white(child, style)


@pytest.mark.parametrize('case', DESCRIPTIVE_CASES + list(DIRECT))
def test_report_backgrounds(viewer, case):
    style = viewer.ui_style
    original = style.theme_use()
    defaults = {name: style.lookup(name, 'background')
                for name in ('TFrame', 'TLabel', 'TMenubutton')}
    lines = (descriptive_report if case in DESCRIPTIVE_CASES else hypothesis_report)(case)
    for line in lines:
        if isinstance(line, StatTable):
            viewer.add_table(line)
        else:
            viewer.add_txt(str(line) + '\n')
    try:
        for theme in (original, 'clam'):
            style.theme_use(theme)
            viewer.main.update()
            assert RESULT_BACKGROUND == viewer.T.cget('background') == '#FFFFFF'
            assert_white(viewer.m, style)
            assert viewer.table_blocks
        style.theme_use(original)
        viewer.main.update()
        assert defaults == {name: style.lookup(name, 'background') for name in defaults}
    finally:
        style.theme_use(original)
        viewer.main.update()
