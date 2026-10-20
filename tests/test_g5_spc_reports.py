"""G5：全部 SPC 报告入口、原计算/绘图契约及真实 Tk 输出。"""
import ast
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest
from matplotlib.figure import Figure

import control_chart as spc
import ctrlchart_dialog as dialogs
import txt_output
from test_g1_text_output import viewer
from test_dialog_translation import widgets


ROOT = Path(__file__).resolve().parents[1]
BASELINE = json.loads((ROOT / 'tests/fixtures/g5_spc_algorithm_ast.json').read_text())


@pytest.fixture
def report(monkeypatch):
    tables, lines = [], []
    original = spc.gen_table
    def capture(rows):
        table = original(rows)
        tables.append(table)
        return table
    monkeypatch.setattr(spc, 'gen_table', capture)
    monkeypatch.setattr(spc.plt, 'show', Mock())
    return tables, lines


def numeric(value):
    return '*' if np.isnan(value) else '%.6g' % value


def assert_report(lines, title):
    text = '\n'.join(lines)
    assert lines[0] == f'\n---- SPC 控制图报告：{title} ----'
    headings = ['控制图信息', '控制限汇总', '过程统计摘要与逐点明细', '特殊原因及异常点', '结论说明']
    assert [text.index(heading) for heading in headings] == sorted(text.index(h) for h in headings)
    assert '当前实现未执行特殊原因规则判定' in text
    assert '未提供异常点索引或规则明细' in text
    assert '不能据此认定过程受控或满足产品规格' in text
    assert 'LCL = 下控制限；CL = 中心线；UCL = 上控制限' in text
    assert '控制限不是产品规格限' in text
    assert '没有异常' not in text and '| 异常 |' not in text


@pytest.mark.parametrize('name', BASELINE)
def test_computation_plotting_signatures_and_returns_match_before_g5_ast(name):
    tree = ast.parse((ROOT / 'code/control_chart.py').read_text(encoding='utf-8'))
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    # 计算函数保持 G5 基线；五个绘图函数采用 G6 展示基线，坐标另由 G6 专项保护。
    # 只排除三个输出入口的顶层 print_out 分支，保留所有计算和绘图语句。
    if name in {'x_plot', 'p_np_plot', 'cu_plot'}:
        function.body = [n for n in function.body if not (
            isinstance(n, ast.If) and isinstance(n.test, ast.Name) and n.test.id == 'print_out')]
    assert hashlib.sha256(ast.dump(function).encode()).hexdigest() == BASELINE[name]


@pytest.mark.parametrize('name,old_pattern', [
    ('x_plot', 't[1].append("Multiple")'),
    ('p_np_plot', 'print("mean = %.4f" % (p_bar))'),
    ('cu_plot', 'print("mean = %.4f" % (c_bar))'),
])
def test_each_report_entry_retires_its_specific_old_output(name, old_pattern):
    source = (ROOT / 'code/control_chart.py').read_text(encoding='utf-8')
    function = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == name)
    body = ast.get_source_segment(source, function)
    assert old_pattern not in body
    assert '---- Control Chart ----' not in body
    assert '_print_spc_report(' in body


@pytest.mark.parametrize('options,data,title,names', [
    ({}, [1., 3., 2., 5.], 'I-MR', ['I 图（单值）', 'MR 图（移动极差）']),
    ({'mr_range': 3}, [1., 3., 2., 5.], 'I-MR', ['I 图（单值）', 'MR 图（移动极差）']),
    ({'mr_range': 99}, [1., 3., 2., 5.], 'I-MR', ['I 图（单值）', 'MR 图（移动极差）']),
    ({'one_chart': True, 'mean': 0, 'sigma': 1}, [-3., 0., 3., 12.], 'I', ['I 图（单值）']),
    ({'chart_two_only': True}, [1., 3., 2., 5.], 'MR', ['MR 图（移动极差）']),
    ({'plot_type': 'XBAR_R'}, [[1., 3.], [2., 5.], [3., 4.]], 'Xbar-R', ['Xbar 图（子组均值）', 'R 图（子组极差）']),
    ({'plot_type': 'XBAR_R', 'pooled': True}, [[1., 3.], [2., 5., 6.], [3., 4.]], 'Xbar-R', ['Xbar 图（子组均值）', 'R 图（子组极差）']),
    ({'plot_type': 'XBAR_S'}, [[1., 3.], [2., 5., 6.], [3., 4.]], 'Xbar-S', ['Xbar 图（子组均值）', 'S 图（子组标准差）']),
    ({'plot_type': 'XBAR_S', 'sigma': 2, 'mean': 1}, [[1., 3.], [2., 5., 6.], [3., 4.]], 'Xbar-S', ['Xbar 图（子组均值）', 'S 图（子组标准差）']),
])
def test_variable_charts_report_actual_statistics_limits_and_selected_panels(report, options, data, title, names):
    tables, lines = report
    fig = Figure()
    axs = fig.subplots(2)
    result = spc.x_plot(data, fig=fig, axs=axs, print_out=True,
                        xLabels=['甲', '乙', '丙', '丁'], print_port=lines.append, **options)
    assert_report(lines, title)
    assert [row[0] for row in tables[0].rows] == names
    if 'BAR' in options.get('plot_type', ''):
        calculation = spc.xBar_R if title == 'Xbar-R' else spc.xBar_S
        expected = calculation(data, **{k: v for k, v in options.items() if k in {'mean', 'sigma', 'pooled'}})
        size = expected['n']
        assert '观测总数：%d' % sum(size) in lines
    else:
        mr = options.get('mr_range', 2)
        mr = mr if 2 <= mr <= len(data) else 2
        expected = spc.x_mR(data, mr, **{k: v for k, v in options.items() if k in {'mean', 'sigma'}})
        size = [1] * len(data)
        assert any(f'移动极差跨度：{mr}；' in line for line in lines)
    assert result.keys() == {'lcl1', 'bar1', 'ucl1', 'lcl2', 'bar2', 'ucl2', 'n'}
    for key in result:
        np.testing.assert_array_equal(result[key], expected[key])
    panel_ids = [2] if title == 'MR' else [1] if title == 'I' else [1, 2]
    for table, panel in zip(tables[1:], panel_ids):
        for i, row in enumerate(table.rows):
            assert row[:4] == [i + 1, ['甲', '乙', '丙', '丁'][i], numeric(size[i]), numeric(expected[f'Y{panel}'][i])]
            actual_limits = []
            for key in [f'lcl{panel}', f'bar{panel}', f'ucl{panel}']:
                value = expected[key]
                actual_limits.append(numeric(value[i] if isinstance(value, list) else value))
            assert row[4:] == actual_limits
    if title == 'I':
        assert tables[1].rows[-1][3] == '12'  # 明确越限；报告仍不能凭图补算异常。
        assert tables[0].rows[0][1:] == ['-3', '0', '3']
    if options.get('mr_range') == 3:
        assert [row[3] for row in tables[2].rows[:2]] == ['*', '*']
    if title in {'Xbar-R', 'Xbar-S'} and len(set(size)) > 1:
        assert tables[0].rows[0][1] == '逐点变化（见明细）'


@pytest.mark.parametrize('function,options,data,n,title,stat_name', [
    (spc.p_np_plot, {}, [.02, .03, .04], [100, 120, 80], 'P', 'P 图（不合格比例）'),
    (spc.p_np_plot, {}, [0., 0., 0.], 100, 'P', 'P 图（不合格比例）'),
    (spc.p_np_plot, {}, [1e-7, 2e-7, 3e-7], [1e8, 2e8, 3e8], 'P', 'P 图（不合格比例）'),
    (spc.p_np_plot, {'NP': True}, [.02, .03, .04], 100, 'NP', 'NP 图（不合格品数）'),
    (spc.p_np_plot, {'NP': True}, [.02, .03, .04], [100, 120, 80], 'NP', 'NP 图（不合格品数）'),
    (spc.cu_plot, {'C': True}, [1., 3., 5.], 1, 'C', 'C 图（缺陷数）'),
    (spc.cu_plot, {}, [1., 3., 5.], [2, 4, 8], 'U', 'U 图（单位缺陷数）'),
    (spc.cu_plot, {}, [0., 0., 0.], [2, 4, 8], 'U', 'U 图（单位缺陷数）'),
])
@pytest.mark.parametrize('override', [False, True])
def test_attribute_reports_show_every_actual_point_and_limit(report, function, options, data, n, title, stat_name, override):
    tables, lines = report
    fig = Figure()
    ax = fig.subplots()
    extra = {'lcl1': -2., 'bar1': 1., 'ucl1': 7.} if override else {}
    key = 'p' if function is spc.p_np_plot else 'c'
    assert function(**{key: data}, n=n, fig=fig, ax=ax, print_out=True,
                    xLabels=['早班', '中班', '夜班'], print_port=lines.append, **options, **extra) is None
    assert_report(lines, title)
    assert tables[0].rows[0][0] == stat_name
    plotted = ax.lines[0].get_ydata()
    nlist = n if isinstance(n, list) else [n] * len(data)
    expected_points = np.array(data) * (nlist[0] if options.get('NP') else 1) if key == 'p' else np.array(data) / nlist
    np.testing.assert_array_equal(plotted, expected_points)
    for i, row in enumerate(tables[1].rows):
        assert row[:4] == [i + 1, ['早班', '中班', '夜班'][i], numeric(nlist[i]), numeric(plotted[i])]
        center = ax.lines[1].get_ydata()[0]
        upper = ax.lines[2].get_ydata()[0 if override else i * 2]
        lower = ax.lines[3].get_ydata()[0 if override else i * 2]
        assert row[4:] == [numeric(lower), numeric(center), numeric(upper)]
    if override:
        assert tables[0].rows[0][1:] == ['-2', '1', '7']
    elif len(set(nlist)) > 1 and any(data):
        assert tables[0].rows[0][3] == '逐点变化（见明细）'
    else:
        assert '逐点变化' not in str(tables[0])


@pytest.mark.parametrize('function,kwargs', [
    (spc.x_plot, {'data': [1, 2, 4, 3]}),
    (spc.p_np_plot, {'p': [.01, .02, .03], 'n': 100}),
    (spc.cu_plot, {'c': [1, 2, 3], 'n': 1, 'C': True}),
])
def test_report_off_has_no_output_and_does_not_change_plot_or_return(report, function, kwargs):
    tables, lines = report
    fig = Figure()
    result = function(**kwargs, fig=fig, ax=fig.subplots(), print_out=False, print_port=lines.append)
    assert result is None if function is not spc.x_plot else isinstance(result, dict)
    assert lines == [] and tables == []


def test_x_plot_override_is_reported_instead_of_recalculated_limit(report):
    tables, lines = report
    fig = Figure()
    result = spc.x_plot([1, 3, 2, 5], fig=fig, ax=fig.subplots(),
        print_out=True, print_port=lines.append, lcl1=[-5, -4, -3, -2],
        bar1=0., ucl1=9., lcl2=-1., bar2=2., ucl2=8.)
    assert result['lcl1'] == [-5, -4, -3, -2]
    assert tables[0].rows == [
        ['I 图（单值）', '逐点变化（见明细）', '0', '9'], ['MR 图（移动极差）', '-1', '2', '8']]
    assert [row[4] for row in tables[1].rows] == ['-5', '-4', '-3', '-2']


@pytest.mark.parametrize('key,value,panel,column', [
    ('lcl1', [-5.], 1, 4), ('bar1', [2.], 1, 5), ('ucl1', [9.], 1, 6),
    ('lcl2', [-1.], 2, 4), ('bar2', [2.], 2, 5), ('ucl2', [8.], 2, 6),
    ('lcl1', [-5., -5.], 1, 4),
])
def test_constant_override_lists_keep_existing_horizontal_line_semantics(report, key, value, panel, column):
    tables, lines = report
    fig = Figure()
    result = spc.x_plot([1, 3, 2, 5], fig=fig, axs=fig.subplots(2),
        all_SD_lines=False, print_out=True, print_port=lines.append, **{key: value})
    assert result[key] == value
    assert all(row[column] == numeric(value[0]) for row in tables[panel].rows)


def test_short_varying_override_does_not_invent_limits_for_uncovered_points(report):
    tables, lines = report
    fig = Figure()
    spc.x_plot([1, 3, 2, 5], fig=fig, axs=fig.subplots(2), lcl1=[-5., -4.],
               all_SD_lines=False, print_out=True, print_port=lines.append)
    assert [row[4] for row in tables[1].rows] == ['-5', '-4', '*', '*']


@pytest.mark.parametrize('options', [{'one_chart': True, 'chart_two_only': True}, {'plot_type': 'XBAR_UNKNOWN'}])
def test_existing_panel_flags_and_unknown_plot_type_keep_successful_return(report, options):
    tables, lines = report
    fig = Figure()
    result = spc.x_plot([1, 3, 2, 5], fig=fig, ax=fig.subplots(), print_out=True,
                        print_port=lines.append, **options)
    assert result['bar1'] == 2.75
    if options.get('one_chart'):
        assert tables == [] and '未选择可报告的图表。' in lines
    else:
        assert_report(lines, 'I-MR')


@pytest.mark.parametrize('function,options', [
    (spc.p_np_plot, {'p': [.01, np.nan, .03], 'n': 100}),
    (spc.p_np_plot, {'p': [.01, np.nan, .03], 'n': 100, 'NP': True}),
    (spc.cu_plot, {'c': [1, np.nan, 3], 'n': 1, 'C': True}),
    (spc.cu_plot, {'c': [1, np.nan, 3], 'n': [2, 4, 8]}),
])
def test_missing_limits_are_unavailable_not_falsely_variable_or_abnormal(report, function, options):
    tables, lines = report
    fig = Figure()
    assert function(**options, fig=fig, ax=fig.subplots(), print_out=True, print_port=lines.append) is None
    # 原算法的 max(0, NaN) 保留下限 0；中心线/上限不可用，不能编造逐点变化。
    assert tables[0].rows[0][1:] == ['0', '*', '*']
    assert all(row[1] == '*' for row in tables[1].rows)
    assert '| 异常 |' not in '\n'.join(lines)


DIALOG_CASES = [
    (dialogs.IMRDialog, 'I-MR'), (dialogs.IDialog, 'I'), (dialogs.MRDialog, 'MR'),
    (dialogs.XBRDialog, 'Xbar-R'), (dialogs.XBSDialog, 'Xbar-S'),
    (dialogs.PDialog, 'P'), (dialogs.NPDialog, 'NP'),
    (dialogs.CDialog, 'C'), (dialogs.UDialog, 'U'),
]


@pytest.mark.parametrize('cls,title', DIALOG_CASES)
@pytest.mark.parametrize('with_ids', [False, True])
def test_real_dialog_get_data_and_confirm_reach_each_report(tk_root, report, monkeypatch, cls, title, with_ids):
    tables, lines = report
    df = pd.DataFrame({'测量': [1., 3., None, 2., 4., 3.],
                       '批次': ['甲', '甲', '乙', '乙', '丙', '丙'],
                       '数量': [10., 12., 11., 10., 12., 10.]})
    figures = []
    def show_plot():
        fig = Figure()
        figures.append(fig)
        return SimpleNamespace(fig=fig)
    app = SimpleNamespace(print=lines.append, showPlotViewer=show_plot,
                          dialog_help_msg=lambda **kwargs: '')
    dialog = cls(tk_root, df=df, app=app, title='控制图')
    errors = []
    original = tk_root.report_callback_exception
    tk_root.report_callback_exception = lambda *args: errors.append(args)
    monkeypatch.setattr(dialog, 'error', Mock())
    try:
        dialog.xvar.set('测量')
        if with_ids:
            dialog.xlabelID.set('批次')
        if cls in {dialogs.XBRDialog, dialogs.XBSDialog}:
            # 保留原有分组逻辑，使用有效子组；缺失值清洗由其他入口覆盖。
            dialog.df = df.fillna({'测量': 1.})
            dialog.gid.set('批次')
        elif cls is dialogs.NPDialog:
            dialog.N.set(100)
        elif cls in {dialogs.PDialog, dialogs.UDialog}:
            dialog.N.set('数量')
        confirm = next(w for w in widgets(dialog.main)
                       if 'text' in w.keys() and str(w.cget('text')) == '确定')
        confirm.invoke()
        assert errors == []
        dialog.error.assert_not_called()
        assert len(figures) == 1
        assert_report(lines, title)
        assert len(tables) == (3 if title in {'I-MR', 'Xbar-R', 'Xbar-S'} else 2)
        expected_panels = 2 if title in {'I-MR', 'Xbar-R', 'Xbar-S'} else 1
        assert len(figures[0].axes) == expected_panels
        assert all(axis.lines for axis in figures[0].axes)
        if with_ids:
            assert tables[1].rows[0][1] == '甲'
        if title in {'I', 'MR', 'I-MR', 'P', 'NP', 'C', 'U'}:
            assert len(tables[1].rows) == 5
        if title == 'U':
            # 原有 UDialog 两条分支不一致：带标识列传原始计数，否则先除单位数。
            assert tables[1].rows[0][3] == ('0.1' if with_ids else '0.01')
    finally:
        tk_root.report_callback_exception = original
        if dialog.main.winfo_exists():
            dialog.quit()


def test_spc_report_in_real_output_window_aligns_scrolls_copies_and_saves(viewer, report, tmp_path, monkeypatch):
    tables, lines = report
    fig = Figure()
    spc.x_plot([[1, 2], [3, 4, 5], [2, 3]], plot_type='XBAR_S', fig=fig, axs=fig.subplots(2),
               xLabels=['批次甲', '批次乙', '批次丙'], print_out=True, print_port=lines.append)
    for title, function, options in [('P', spc.p_np_plot, {'p': [.01, .02, .03], 'n': [100, 120, 80]}),
                                      ('U', spc.cu_plot, {'c': [1, 2, 3], 'n': [2, 4, 8]})]:
        other = Figure()
        function(**options, fig=other, ax=other.subplots(), print_out=True, print_port=lines.append)
    for table in tables:
        positions = [[viewer.output_font.measure(line[:i]) for i, c in enumerate(line) if c == '|']
                     for line in str(table).splitlines() if '|' in line]
        assert all(row == positions[0] for row in positions)
    content = '\n'.join(lines) + '\n'
    viewer.main.geometry('480x320')
    viewer.add_txt(content)
    viewer.main.update()
    assert viewer.T.xview()[1] < 1 and viewer.T.yview()[1] < 1
    viewer.T.xview_moveto(.5)
    assert viewer.T.xview()[0] > 0
    assert viewer.ctrlfr.winfo_ismapped()
    viewer.select_all()
    copied = []
    def copy(event):
        copied.append(viewer.T.get('sel.first', 'sel.last'))
        return 'break'
    viewer.T.bind('<<Copy>>', copy)
    next(w for w in widgets(viewer.ctrlfr) if 'text' in w.keys() and str(w.cget('text')) == '复制').invoke()
    assert copied == [content]
    target = tmp_path / '控制图报告.txt'
    monkeypatch.setattr(txt_output.filedialog, 'asksaveasfilename', lambda **kwargs: str(target))
    viewer.save()
    assert target.read_text(encoding='utf-8') == content
