"""G4：质量报告语义、所有入口、真实返回契约和 Tk 显示回归。"""
import ast
import inspect
import math
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest
from matplotlib.figure import Figure
from scipy.stats import norm

import cpk
import GRR
import qc_dialog
import ti
import txt_output
from cpk_plot import cpk_plot
from utilities import format_stat
from test_g1_text_output import viewer
from source_baselines import read_source_baseline


ROOT = Path(__file__).resolve().parents[1]
BASELINE = '191c3b7b245ff40f600d442bbf18ea7e523a28df'
SHARED_BASELINE = 'da54ca1bdc1e5e9d197d5a31308b94754a6d0a9f'
Y = [10., 11., 20., 22., 31., 30., 12., 13., 25., 26., 40., 42.]
PART = ['P1', 'P1', 'P2', 'P2', 'P3', 'P3'] * 2
OP = ['甲'] * 6 + ['乙'] * 6
NEST_PART = ['P1', 'P1', 'P2', 'P2', 'P3', 'P3', 'P4', 'P4']
NEST_OP = ['甲'] * 4 + ['乙'] * 4
NEST_Y = [1., 3., 5., 7., 9., 11., 13., 15.]


@pytest.fixture(scope='module')
def originals():
    modules = {}
    for name in ('cpk', 'GRR', 'ti', 'qc_dialog'):
        source = read_source_baseline(BASELINE, f'code/{name}.py')
        module = ModuleType('g4_original_' + name)
        exec(compile(source, f'baseline/{name}.py', 'exec'), module.__dict__)
        modules[name] = module
    return modules


def equal_result(actual, expected):
    assert type(actual) is type(expected)
    if isinstance(expected, dict):
        assert list(actual) == list(expected)
        for key in expected:
            equal_result(actual[key], expected[key])
    elif isinstance(expected, (list, tuple)):
        assert len(actual) == len(expected)
        for a, b in zip(actual, expected):
            equal_result(a, b)
    elif isinstance(expected, (float, np.floating)) and math.isnan(expected):
        assert math.isnan(actual)
    else:
        assert actual == expected


def capture_tables(monkeypatch, module):
    tables = []
    original = module.gen_table
    def capture(rows):
        table = original(rows)
        tables.append(table)
        return table
    monkeypatch.setattr(module, 'gen_table', capture)
    return tables


@pytest.mark.parametrize('data,use_range', [
    ([1., 2., 4., 5., 7., 8.], False),
    ([[1., 2., 4.], [5., 7., 8.]], False),
    ([[1., 2., 4.], [5., 7., 8.]], True),
    ([[1., 2., 4.], [5., 7.]], False),
    ([[1., 2., 4.], [5., 7.]], True)])
@pytest.mark.parametrize('within', [False, True])
@pytest.mark.parametrize('alpha', [.05, .1])
@pytest.mark.parametrize('print_out', [False, True])
def test_capability_exact_returns(originals, data, use_range, within, alpha, print_out):
    args = dict(data=data, target=4, lsl=0, usl=9, within=within,
                use_range=use_range, alpha=alpha, print_out=print_out, print_port=lambda s: None)
    equal_result(cpk.cpk(**args), originals['cpk'].cpk(**args))


@pytest.mark.parametrize('overall', [False, True])
def test_capability_indices_and_confidence_columns(monkeypatch, overall, originals):
    tables = capture_tables(monkeypatch, cpk)
    args = dict(mean=2, std=1.3, T=4, usl=9, lsl=0, df=19, N=20,
                name='Overall (AKA Ppk in JMP)' if overall else 'Within')
    result = cpk.cpk_calc(**args, print_port=lambda s: None)
    equal_result(result, originals['cpk'].cpk_calc(**args, print_out=False))
    table = tables[0]
    prefix = 'P' if overall else 'C'
    assert [row[0] for row in table.rows] == [prefix + x for x in ('p', 'pk', 'pl', 'pu')] + ['Cpm']
    for row, key in zip(table.rows[:4], ('cp', 'cpk', 'cpl', 'cpu')):
        assert row[1:] == [format_stat(result[k]) for k in (key, key + '_l', key + '_u')]
    assert table.rows[-1] == ['Cpm', format_stat(result['cpm']), '*', '*']


@pytest.mark.parametrize('within', [False, True])
@pytest.mark.parametrize('data,use_range,method', [
    ([1., 2., 4., 5., 7., 8.], False, '移动极差'),
    ([[1., 2., 4.], [5., 7., 8.]], False, '无偏标准差'),
    ([[1., 2., 4.], [5., 7., 8.]], True, '极差除以 d2')])
def test_capability_sample_specifications_and_sigma_method(monkeypatch, within, data, use_range, method):
    tables = capture_tables(monkeypatch, cpk)
    lines = []
    result = cpk.cpk(data, target=4, lsl=0, usl=9, within=within, use_range=use_range, print_port=lines.append)
    row = dict(zip(tables[0].field_names, tables[0].rows[0]))
    assert row['N'] == result['N']
    assert row['子组数'] == result['N Subgroups']
    for label, key in [('LSL', 'LSL'), ('目标值 Target', 'Target'), ('USL', 'USL'),
                       ('过程均值', 'mean'), ('整体标准差', 'Overall Sigma')]:
        assert row[label] == format_stat(result[key])
    if within:
        assert row['组内标准差'] == format_stat(result['Within Sigma'])
        assert row['整体/组内标准差比'] == format_stat(result['Stability Index'])
        assert method in '\n'.join(lines)
    else:
        assert '组内标准差' not in row
        assert all(t.rows[0][0] != 'Cp' for t in tables)


@pytest.mark.parametrize('within', [False, True])
def test_nonconformance_observed_within_overall_are_distinct(monkeypatch, within, originals):
    tables = capture_tables(monkeypatch, cpk)
    args = dict(data=[-1., 2., 3., 7., 12.], t=4, lsl=0, usl=10, u=4, sw=1, so=3, within=within)
    result = cpk.nonconformance(**args, print_port=lambda s: None)
    equal_result(result, originals['cpk'].nonconformance(**args, print_out=False))
    assert tables[0].rows[0] == ['实际观测', '20.000', '20.000', '40.000']
    if within:
        assert tables[0].rows[1] == ['正态预测（组内）'] + [format_stat(100 * result[k]) for k in ('below_w', 'above_w', 'ttl_w')]
    assert tables[0].rows[-1] == ['正态预测（整体）'] + [format_stat(100 * result[k]) for k in ('below_o', 'above_o', 'ttl_o')]


@pytest.mark.parametrize('method', ['grr_anova_AIAG', 'grr_anova_EMP', 'grr_xbar_r', 'grr_master'])
@pytest.mark.parametrize('op', [None, OP])
@pytest.mark.parametrize('print_out', [False, True])
def test_crossed_exact_returns(originals, method, op, print_out):
    args = dict(y=Y, part=PART, op=op, print_out=print_out, print_port=lambda s: None)
    if method in ('grr_anova_AIAG', 'grr_xbar_r', 'grr_master'):
        args.update(hist_std=12., spec_gap=80.)
    equal_result(getattr(GRR, method)(**args), getattr(originals['GRR'], method)(**args))


@pytest.mark.parametrize('mode', ['AIAG', 'EMP', 'XBAR/R'])
@pytest.mark.parametrize('inter', ['Auto', 'On', 'Off'])
def test_master_dispatch_interaction_and_screening_table(monkeypatch, originals, mode, inter):
    tables = capture_tables(monkeypatch, GRR)
    lines = []
    args = dict(y=Y, part=PART, op=OP, mode=mode, inter=inter, alpha=.1, print_out=True)
    result = GRR.grr_master(**args, print_port=lines.append)
    equal_result(result, originals['GRR'].grr_master(**args, print_port=lambda s: None))
    screening = [t for t in tables if '平方和 SS' in t.field_names]
    if mode != 'XBAR/R' and inter == 'Auto':
        assert len(screening) == 1
        anova = GRR.two_way_anova(Y, factor_listA=PART, factor_listB=OP)
        for row, key in zip(screening[0].rows[:3], ['A', 'B', 'AB']):
            assert row[1:] == [anova['DF ' + key]] + [format_stat(anova[k + key]) for k in ('SS', 'MS', 'F ', 'p ')]
        assert screening[0].rows[-2][2:4] == [format_stat(anova['SSE']), format_stat(anova['MSE'])]
        assert '用于交互项筛选' in '\n'.join(lines)
    else:
        assert not screening


@pytest.mark.parametrize('y', [Y, [1., 2., 3., 4., 5., 6., 2., 3., 4., 5., 6., 7.], Y[:-1]])
def test_master_screening_total_ss_and_original_interaction_decision(monkeypatch, originals, y):
    tables = capture_tables(monkeypatch, GRR)
    lines = []
    args = dict(y=y, part=PART[:len(y)], op=OP[:len(y)], print_out=True)
    actual = GRR.grr_master(**args, print_port=lines.append)
    equal_result(actual, originals['GRR'].grr_master(**args, print_port=lambda s: None))
    assert tables[0].rows[-1][2] == format_stat(sum((value - sum(y) / len(y))**2 for value in y))
    anova = GRR.two_way_anova(y, factor_listA=PART[:len(y)], factor_listB=OP[:len(y)])
    assert ('未达到保留条件' in '\n'.join(lines)) == (anova['p AB'] > .05)


@pytest.mark.parametrize('hist', [None, 3., 10.])
@pytest.mark.parametrize('y', [NEST_Y, [1.] * 8, [1., 1., 2., 2., 1., 1., 2., 2.]])
@pytest.mark.parametrize('print_out', [False, True])
def test_nested_exact_returns(originals, hist, y, print_out):
    args = dict(y=y, part=NEST_PART, op=NEST_OP, hist_std=hist,
                print_out=print_out, print_port=lambda s: None)
    equal_result(GRR.grr_nested(**args), originals['GRR'].grr_nested(**args))


@pytest.mark.parametrize('method', ['grr_anova_AIAG', 'grr_anova_EMP', 'grr_xbar_r'])
def test_grr_components_and_percentage_denominators(monkeypatch, method):
    tables = capture_tables(monkeypatch, GRR)
    args = dict(y=Y, part=PART, op=OP, print_out=True, print_port=lambda s: None)
    if method != 'grr_anova_EMP':
        args.update(hist_std=12., spec_gap=80.)
    result = getattr(GRR, method)(**args)
    variance, study = tables[:2]
    expected = {'总量具 R&R (GRR)': result['RR'], '重复性 (EV)': result['EV'],
                '零件间 (PV)': result['PV'], '总变异': result['TV']}
    expected['再现性（操作者）' if method == 'grr_anova_EMP' else '再现性 (AV)'] = result['AV']
    if method != 'grr_xbar_r':
        expected['零件 x 操作者'] = result['INT']
    if method == 'grr_anova_AIAG':
        expected['操作者'] = result['AV'] - result['INT']
    for row in variance.rows:
        value = expected[row[0]]
        assert row[1:] == [format_stat(value), format_stat(100 * value / result['TV'])]
    for row in study.rows:
        sd = expected[row[0]]**.5
        assert row[1] == format_stat(sd)
        if method != 'grr_anova_EMP':
            assert row[2:] == [format_stat(6 * sd), format_stat(100 * sd / result['TV']**.5),
                               format_stat(100 * sd / 12), format_stat(600 * sd / 80)]
    if method == 'grr_anova_EMP':
        assert study.field_names == ['来源', '标准差 SD']
        assert result['RR'] == result['EV'] + result['AV']
        assert result['TV'] == result['RR'] + result['PV'] + result['INT']
    else:
        assert variance.rows[0][2] != study.rows[0][3]


@pytest.mark.parametrize('op', [None, OP])
def test_direct_dataframe_xbar_entry_and_custom_column_names(originals, op):
    data = pd.DataFrame({'长度': Y, '部件': PART})
    if op is not None:
        data['人员'] = op
    args = dict(op_key='人员', pt_key='部件', y_key='长度', has_op_col=op is not None,
                print_out=True, print_port=lambda s: None)
    equal_result(GRR.GRR_xbar(data.copy(), **args), originals['GRR'].GRR_xbar(data.copy(), **args))


@pytest.mark.parametrize('method', ['grr_xbar_r', 'grr_anova_AIAG'])
def test_zero_report_denominators_show_unavailable_without_changing_results(monkeypatch, method):
    tables = capture_tables(monkeypatch, GRR)
    args = dict(y=Y, part=PART, op=OP)
    expected = getattr(GRR, method)(**args)
    actual = getattr(GRR, method)(**args, hist_std=0., spec_gap=0., print_out=True, print_port=lambda s: None)
    equal_result(actual, expected)
    assert all(row[-2:] == ['*', '*'] for row in tables[1].rows)


def test_zero_xbar_variation_is_not_reported_as_valid_zero_percent(monkeypatch):
    tables = capture_tables(monkeypatch, GRR)
    lines = []
    result = GRR.grr_xbar_r(y=[1.] * len(Y), part=PART, op=OP, print_out=True, print_port=lines.append)
    assert result['TV'] == 0
    assert all(row[2] == '*' for row in tables[0].rows)
    assert all(row[3] == '*' for row in tables[1].rows)
    assert 'ndc = *' in '\n'.join(lines)


def test_nested_components_anova_and_history_semantics(monkeypatch):
    tables = capture_tables(monkeypatch, GRR)
    lines = []
    result = GRR.grr_nested(y=NEST_Y, part=NEST_PART, op=NEST_OP, hist_std=10.,
                            print_out=True, print_port=lines.append)
    anova, variance, study = tables
    assert anova.rows[0][1:] == [1, '128.000', '128.000', '8.000', format_stat(result['P value operator'])]
    assert anova.rows[1][1:] == [2, '32.000', '16.000', '8.000', format_stat(result['P value part'])]
    assert anova.rows[-1][2] == '168.000'
    assert variance.rows[0][1:] == ['30.000', '30.000']
    assert variance.rows[3][1:] == ['70.000', '70.000']
    assert study.rows[0][3] == format_stat(100 * math.sqrt(30) / 10)
    assert '已用于估计' in '\n'.join(lines)
    assert '零件数 = 4' in '\n'.join(lines)
    assert '操作者的零件数 = 2' in '\n'.join(lines)


@pytest.mark.parametrize('summary', [False, True])
@pytest.mark.parametrize('alpha,P', [(.05, .9), (.1, .8)])
@pytest.mark.parametrize('print_out', [False, True])
def test_tolerance_exact_returns_and_factors(monkeypatch, originals, summary, alpha, P, print_out):
    tables = capture_tables(monkeypatch, ti)
    lines = []
    args = dict(alpha=alpha, P=P, print_out=print_out)
    if summary:
        args.update(data=[999.], sample_n=10, sample_std=3.052, sample_mean=5.95)
    else:
        args['data'] = Y
    result = ti.ti_norm(**args, print_port=lines.append)
    expected = originals['ti'].ti_norm(**args, print_port=lambda s: None)
    equal_result(result, expected)
    if not print_out:
        assert not lines and not tables
        return
    n, mean, sd = (10, 5.95, 3.052) if summary else (len(Y), np.mean(Y), np.std(Y, ddof=1))
    assert tables[0].rows == [[n, format_stat(mean), format_stat(sd)]]
    table = tables[1]
    assert [row[1] for row in table.rows] == ['双侧区间', '单侧下限', '单侧上限']
    assert all(row[2:4] == ['%.1f%%' % (P * 100), '%.1f%%' % ((1 - alpha) * 100)] for row in table.rows)
    assert table.rows[0][4:6] == [format_stat(x) for x in result['TI']]
    assert table.rows[1][4:6] == [format_stat(result['Lower Bound']), '*']
    assert table.rows[2][4:6] == ['*', format_stat(result['Upper Bound'])]
    assert table.rows[0][6] == format_stat((result['TI'][1] - mean) / sd)
    assert table.rows[1][6] == table.rows[2][6] == format_stat((result['Upper Bound'] - mean) / sd)
    assert '不能拼成双侧区间' in '\n'.join(lines)


def variable(value):
    return SimpleNamespace(get=lambda: value)


def dialog_for(df):
    lines, figures = [], []
    def plot():
        figure = SimpleNamespace(fig=Figure())
        figures.append(figure)
        return figure
    app = SimpleNamespace(print=lines.append, showPlotViewer=Mock(side_effect=plot))
    values = dict(xvar='长度', yvar='部件', ovar='人员', mvar='AIAG (ANOVA)', inter='Auto',
                  hist_std='', spec_gap='', ylabel='mm', xlabel='mm', alpha=.05,
                  target=20., lsl=0., usl=50., show_legend=True, show_spec=True,
                  show_within=True, subid='部件', subsize=2, subm='Unbiased Std Dev',
                  sample_mean='', sample_std='', sample_n='', prop=.9)
    dialog = SimpleNamespace(df=df, app=app, error=Mock(), **{k: variable(v) for k, v in values.items()})
    return dialog, lines, figures


@pytest.mark.parametrize('cls,method', [
    ('CpkDialog', None), ('CpkSubDialog', 'Use Subgrp Size'),
    ('CpkSubDialog', 'Use Subgrp ID Col.'), ('GRRDialog', 'AIAG (ANOVA)'),
    ('GRRDialog', 'EMP (ANOVA)'), ('GRRDialog', 'XBAR/R'),
    ('GRR_Nested_Dialog', None), ('TIDialog', None)])
def test_all_dialog_apply_entries_keep_plots_and_variable_identity(cls, method):
    nested = cls == 'GRR_Nested_Dialog'
    df = pd.DataFrame({'长度': NEST_Y if nested else Y, '部件': NEST_PART if nested else PART,
                       '人员': NEST_OP if nested else OP})
    dialog, lines, figures = dialog_for(df)
    if method:
        dialog.mvar = variable(method)
    getattr(qc_dialog, cls).apply(dialog)
    dialog.error.assert_not_called()
    assert '分析变量：长度' in '\n'.join(lines)
    if cls in ('GRR_Nested_Dialog', 'TIDialog'):
        assert not figures
    else:
        assert len(figures) == 1
        if cls.startswith('Cpk'):
            assert figures[0].ax.get_xlabel() == 'mm'
            assert len(figures[0].fig.axes) == 2
            assert len(figures[0].ax.lines) == 5  # 两条密度曲线和三个规格参考线。
        else:
            assert figures[0].ax.child_axes[0].get_ylabel() == 'mm'
            assert len(figures[0].ax.child_axes) == 2


def test_tolerance_summary_dialog_does_not_claim_selected_variable():
    dialog, lines, _ = dialog_for(pd.DataFrame({'长度': Y}))
    dialog.sample_n, dialog.sample_mean, dialog.sample_std = variable('10'), variable('5.95'), variable('3.052')
    qc_dialog.TIDialog.apply(dialog)
    assert '分析变量：汇总数据（未指定变量名）' in lines[0]
    assert '数据来源：汇总数据' in '\n'.join(lines)


@pytest.mark.parametrize('subgroup', [False, True])
def test_capability_plot_keeps_return_and_curve_data(originals, subgroup):
    data = [[1., 2., 4.], [5., 7., 8.]] if subgroup else [1., 2., 4., 5., 7., 8.]
    figure = Figure()
    axis = figure.add_subplot(111)
    result = cpk_plot(data, 9, 4, 0, ax=axis, print_out=True, print_port=lambda s: None)
    equal_result(result, originals['cpk'].cpk(data, 4, 9, 0, print_out=False))
    np.testing.assert_array_equal(axis.lines[0].get_ydata(),
        norm.pdf(axis.lines[0].get_xdata(), result['mean'], result['Overall Sigma']))
    np.testing.assert_array_equal(axis.lines[1].get_ydata(),
        norm.pdf(axis.lines[1].get_xdata(), result['mean'], result['Within Sigma']))


@pytest.mark.parametrize('kind', ['capability', 'aiag', 'emp', 'xbar', 'nested', 'tolerance'])
def test_report_tables_align_in_actual_font_and_save(viewer, monkeypatch, tmp_path, kind):
    module = cpk if kind == 'capability' else ti if kind == 'tolerance' else GRR
    tables = capture_tables(monkeypatch, module)
    lines = []
    if kind == 'capability':
        cpk.cpk(Y, 20, 50, 0, print_port=lines.append)
    elif kind == 'tolerance':
        ti.ti_norm(data=Y, print_out=True, print_port=lines.append)
    elif kind == 'nested':
        GRR.grr_nested(y=NEST_Y, part=NEST_PART, op=NEST_OP, print_out=True, print_port=lines.append)
    else:
        GRR.grr_master(y=Y, part=PART, op=OP, mode=kind, hist_std=12, spec_gap=80,
                      print_out=True, print_port=lines.append)
    for table in tables:
        expected = None
        for line in str(table).splitlines():
            if '|' not in line:
                continue
            positions = [viewer.output_font.measure(line[:i]) for i, char in enumerate(line) if char == '|']
            expected = expected or positions
            assert positions == expected
        for col in table.field_names:
            if col not in ('来源', '指标', '方法', '限类型', '统计量', '原有 EMP 分类',
                           '类别', '组内相关', '过程信号衰减', '检验 1 检出概率', '检验 1/5/6/8 检出概率'):
                assert table.align[col] == 'r'
    content = '\n'.join(lines) + '\n'
    viewer.main.geometry('480x320')
    viewer.add_txt(content)
    viewer.main.update()
    assert str(viewer.T.cget('wrap')) == 'none'
    assert viewer.T.xview()[1] < 1
    viewer.hsb.tk.call(viewer.hsb.cget('command'), 'moveto', .5)
    assert viewer.T.xview()[0] > 0
    assert viewer.ctrlfr.winfo_ismapped()
    target = tmp_path / '质量报告.txt'
    monkeypatch.setattr(txt_output.filedialog, 'asksaveasfilename', lambda **kw: str(target))
    viewer.save()
    assert target.read_text(encoding='utf-8') == content
    viewer.select_all()
    copied = []
    def copy(event):
        copied.append(viewer.T.get('sel.first', 'sel.last'))
        return 'break'
    viewer.T.bind('<<Copy>>', copy)
    viewer.T.event_generate('<<Copy>>')
    assert copied == [content]


class ComputationOnly(ast.NodeTransformer):
    def visit_If(self, node):
        if isinstance(node.test, ast.Name) and node.test.id == 'print_out':
            return None
        return self.generic_visit(node)

    def visit_Assign(self, node):
        if any(isinstance(t, ast.Name) and t.id == 'guideline' for t in node.targets):
            return None
        return self.generic_visit(node)

    def visit_Call(self, node):
        if isinstance(node.func, ast.Name) and node.func.id == 'two_way_anova':
            for kw in node.keywords:
                if kw.arg == 'print_out':
                    kw.value = ast.Constant(False)
        return self.generic_visit(node)


@pytest.mark.parametrize('module', [cpk, GRR, ti])
def test_original_computations_signatures_and_defaults_are_unchanged(originals, module):
    original = originals[module.__name__]
    old_tree = ast.parse(read_source_baseline(BASELINE, f'code/{module.__name__}.py'))
    new_tree = ast.parse((ROOT / 'code' / (module.__name__ + '.py')).read_text(encoding='utf-8'))
    for name, function in inspect.getmembers(original, inspect.isfunction):
        if function.__module__ != original.__name__:
            continue
        current = getattr(module, name)
        optimized = module is GRR and name in {
            'grr_inter', 'grr_anova_EMP', 'grr_anova_AIAG', 'grr_master'}
        if optimized:
            # G16 preserves existing arguments; private keyword-only inputs reuse one fit.
            before_args = inspect.signature(function).parameters
            after_args = inspect.signature(current).parameters
            assert list(after_args)[:len(before_args)] == list(before_args), name
            assert all(after_args[key] == value for key, value in before_args.items()), name
            extra = list(after_args.values())[len(before_args):]
            assert [arg.name for arg in extra] == ([] if name == 'grr_master' else
                ['_anova' if name == 'grr_inter' else '_full_anova'])
            assert all(arg.kind == inspect.Parameter.KEYWORD_ONLY and arg.default is None for arg in extra)
        else:
            assert inspect.signature(current) == inspect.signature(function), name
        # 原函数由固定基线编译，逐函数取 AST，保留所有非报告计算和保护逻辑。
        old = next(n for n in old_tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
        new = next(n for n in new_tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
        if not optimized:
            assert ast.dump(ComputationOnly().visit(new)) == ast.dump(ComputationOnly().visit(old)), name
        # G16's frozen numerical/report comparisons and fit counts cover these four bodies.


@pytest.mark.parametrize('module,function,old', [
    (cpk, 'cpk', '---- Process Capabilities ----'),
    (cpk, 'cpk_calc', '"Index", "Estimate"'),
    (cpk, 'nonconformance', 'Expected Within%'),
    (GRR, 'GRR_xbar', 'Gage Evaluation'),
    (GRR, 'grr_anova_AIAG', 'Gage R&R / Total Variation'),
    (GRR, 'grr_anova_EMP', 'Variance Components'),
    (GRR, 'grr_master', 'alpha to remove interaction term'),
    (GRR, 'grr_nested', 'Gage R&R Nested for Response'),
    (ti, 'ti_norm', '"Lower TI", "Upper TI"')])
def test_specific_replaced_output_patterns(originals, module, function, old):
    source = read_source_baseline(BASELINE, f'code/{module.__name__}.py')
    node = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == function)
    assert old in ast.get_source_segment(source, node)
    assert old not in inspect.getsource(getattr(module, function))


def test_shared_modules_and_plot_implementations_remain_at_baseline():
    # txt_output 已接入 G8；真实控件与 TXT 由 G1/G10/G11 测试保护。
    for name in ('utilities.py', 'dialog.py', 'two_way_anova.py',
                 'one_way_ANOVA.py', 'cpk_plot.py', 'grr_plot.py'):
        # 仅两份绘图源码转为已验收的 G6 基线，其余共享模块仍保留原守卫。
        baseline = '0320b7bdc49321eb7a54f67ddc89dc08edc32f3e' if name in {'cpk_plot.py', 'grr_plot.py'} else SHARED_BASELINE
        old = read_source_baseline(baseline, f'code/{name}')
        if name in {'one_way_ANOVA.py', 'two_way_anova.py'}:
            # G9 仅迁移报告；计算守卫继续保留，完整 TXT 由 G9 固定夹具验证。
            current = ast.parse((ROOT / 'code' / name).read_text(encoding='utf-8'))
            current.body = [node for node in current.body if not (
                isinstance(node, ast.ImportFrom) and node.module == 'stat_table')]
            original = ast.parse(old)
            if name == 'two_way_anova.py':
                for tree in (current, original):
                    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                                    and n.name == 'two_way_anova')
                    branch = next(n for n in function.body if isinstance(n, ast.If)
                                  and isinstance(n.test, ast.Name) and n.test.id == 'interaction')
                    # G16 covers optimized cell SSE with frozen values and mean counts.
                    branch.body = branch.body[:1]
            assert ast.dump(ComputationOnly().visit(current)) == ast.dump(
                ComputationOnly().visit(original))
            continue
        if name == 'utilities.py':
            # P1/P2 仅授权 Pearson 舍入截断及完全相关区间方向，保留整文件其余守卫。
            old = old.replace('\r\n', '\n')
            statement = '    cov = sum('
            assert old.count(statement) == 1
            old = old.replace(statement, '    r = np.clip(r, -1, 1)\n' + statement)
            assert old.count('r_z = 10000') == 1
            old = old.replace('r_z = 10000', 'r_z = np.copysign(np.inf, r)')
            current = ast.parse((ROOT / 'code' / name).read_text(encoding='utf-8'))
            original = ast.parse(old)
            for tree in (current, original):
                # G17 数字清洗有独立冻结数据及热点守卫，保留其余共享函数保护。
                tree.body = [n for n in tree.body if not (
                    isinstance(n, ast.FunctionDef) and n.name == 'number_2Dlist')]
            current.body = [node for node in current.body if not (
                isinstance(node, ast.ImportFrom) and node.module == 'stat_table')]
            for tree in (current, original):
                for node in tree.body:
                    if isinstance(node, ast.FunctionDef) and node.name in {'pearson_correlation', 'norm_test', 'mean_std_CIs'}:
                        # G10/G12 只放行报告块，计算与其余共享函数仍完整比较。
                        ComputationOnly().visit(node)
            assert ast.dump(current) == ast.dump(original)
            continue
        if name == 'dialog.py':
            trees = [ast.parse(source) for source in (
                old, (ROOT / 'code' / name).read_text(encoding='utf-8'))]
            current = trees[1]
            added_import = ast.parse('from inspect import getattr_static').body[0]
            assert sum(ast.dump(n) == ast.dump(added_import) for n in current.body) == 1
            current.body = [n for n in current.body if ast.dump(n) != ast.dump(added_import)]
            owner = next(n for n in current.body if isinstance(n, ast.ClassDef) and n.name == 'Dialogs')
            init = next(n for n in owner.body if isinstance(n, ast.FunctionDef) and n.name == '__init__')
            binding = next(n for n in init.body if isinstance(n, ast.Assign)
                           and ast.unparse(n.targets[0]) == 'self.app')
            # 仅放行有真实跨表输出测试接管的来源绑定，继续冻结其余对话框。
            allowed = ast.parse("app.sheet_app(parent) if callable(getattr_static(app, 'sheet_app', None)) else app", mode='eval').body
            assert ast.dump(binding.value) == ast.dump(allowed)
            binding.value = ast.Name(id='app', ctx=ast.Load())
            for tree in trees:
                owner = next(n for n in tree.body if isinstance(n, ast.ClassDef)
                             and n.name == 'findRepDialog')
                # G17 保留其他对话框全文，只由查找边界/坐标测试接管 find。
                owner.body = [n for n in owner.body if not (
                    isinstance(n, ast.FunctionDef) and n.name == 'find')]
            assert ast.dump(trees[0]) == ast.dump(trees[1])
            continue
        assert (ROOT / 'code' / name).read_text(encoding='utf-8') == old.replace('\r\n', '\n')


def test_quality_dialog_changes_are_only_output_statements(originals):
    old = read_source_baseline(BASELINE, 'code/qc_dialog.py')
    current = (ROOT / 'code/qc_dialog.py').read_text(encoding='utf-8')
    class ReportOnly(ast.NodeTransformer):
        def visit_Expr(self, node):
            call = node.value
            if isinstance(call, ast.Call) and ast.unparse(call.func) == 'self.app.print' and call.args:
                first = call.args[0]
                if isinstance(first, ast.JoinedStr) and isinstance(first.values[0], ast.Constant) and first.values[0].value == '分析变量：':
                    return None
            return self.generic_visit(node)
        def visit_Constant(self, node):
            texts = {'Received %d valid data pairs for group ID and measurement.': '子组标识与测量值的有效配对数 = %d。',
                     'WARNING: Unbalanced subgrouping.': '警告：子组大小不相等。'}
            if isinstance(node.value, str):
                node.value = texts.get(node.value, node.value)
            return node
    assert current.count('self.app.print(f"分析变量：') == 5
    assert ast.dump(ReportOnly().visit(ast.parse(current))) == ast.dump(ReportOnly().visit(ast.parse(old)))
