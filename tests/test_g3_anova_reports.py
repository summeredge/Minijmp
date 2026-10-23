"""ANOVA 报告专项：固定数值、真实 apply 路由和报告格式；不依赖本机快照。"""
import ast
import inspect
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest
from matplotlib.figure import Figure
from scipy import stats
from wcwidth import wcswidth

import anova_dialog
import GRR
import one_way_ANOVA as one
import qc_dialog
import two_way_anova as two
from utilities import hash_combined
from test_g1_text_output import viewer


DATA = [[1., 2., 3.], [2., 4., 6.], [10., 11., 12., 13.]]
LABELS = ['工艺甲', 'B', '较长中文工艺组 C']
CROSSED = [[[1, 2], [3, 4]], [[2, 4], [5, 8]]]
NESTED = dict(y=[1, 3, 5, 7, 9, 11, 13, 15],
              op=['A'] * 4 + ['B'] * 4, part=[1, 1, 2, 2, 3, 3, 4, 4])


def capture_tables(monkeypatch, module):
    tables = []
    original = module.gen_table
    def capture(rows):
        table = original(rows)
        tables.append(table)
        return table
    monkeypatch.setattr(module, 'gen_table', capture)
    return tables


def variable(value):
    return SimpleNamespace(get=lambda: value)


@pytest.mark.parametrize('alpha', [.05, .1])
@pytest.mark.parametrize('print_out', [False, True])
def test_one_way_values_intervals_types_and_summary(monkeypatch, alpha, print_out, capsys):
    tables = capture_tables(monkeypatch, one)
    lines = []
    result = one.one_way_anova(DATA, LABELS, alpha=alpha,
                               print_out=print_out, print_port=lines.append)
    expected = {'F': 41.86, 'p': stats.f_oneway(*DATA).pvalue,
        'df B': 2, 'df W': 7, 'df TTL': 9, 'MSB': 89.7,
        'MSW': 15 / 7, 'MSE': 15 / 7, 'MSA': 89.7}
    assert list(result) == list(expected) + ['CI']
    for key, value in expected.items():
        assert result[key] == pytest.approx(value)
        expected_type = int if key.startswith('df ') else (
            float if key in ['MSW', 'MSE'] else np.float64)
        assert type(result[key]) is expected_type
    assert type(result['CI']) is list
    for i, (group, interval) in enumerate(zip(DATA, result['CI'])):
        assert type(interval) is tuple
        assert all(type(x) is np.float64 for x in interval)
        np.testing.assert_allclose(interval, stats.t.interval(
            1 - alpha, 7, loc=np.mean(group), scale=np.sqrt(15 / 7 / len(group))))
    assert capsys.readouterr().out == ''
    if not print_out:
        assert not tables and not lines
        return
    assert tables[0].field_names == ['组别', 'N', '均值', '均值标准误', '置信下限', '置信上限']
    assert [row[:4] for row in tables[0].rows] == [
        [LABELS[0], 3, '2.000', '0.845'], [LABELS[1], 3, '4.000', '0.845'],
        [LABELS[2], 4, '11.500', '0.732']]
    assert [row[4:] for row in tables[0].rows] == [
        ['%.3f' % lo, '%.3f' % hi] for lo, hi in result['CI']]
    assert tables[1].field_names == ['来源', '自由度', '平方和', '均方', 'F 值', 'p 值']
    assert tables[1].rows == [
        ['组间', 2, '179.400', '89.700', '41.860', '0.000'],
        ['组内（误差）', 7, '15.000', '2.143', '*', '*'],
        ['总计', 9, '194.400', '*', '*', '*']]
    text = '\n'.join(lines)
    assert '%.1f%% 总体均值双侧置信区间' % ((1 - alpha) * 100) in text
    assert 'alpha = %.3f' % alpha in text
    assert '非同时置信区间' in text and '未检验这些条件' in text
    assert '至少一组总体均值不同' in text
    assert '舍入结果，不代表概率严格为零' in text


@pytest.mark.parametrize('alpha,groups', [(.05, [[2], [1, 0]]), (.2, [[2], [1], [0]])])
@pytest.mark.parametrize('print_out', [False, True])
def test_pairwise_p_values_letter_order_and_contract(monkeypatch, alpha, groups, print_out, capsys):
    tables = capture_tables(monkeypatch, one)
    lines = []
    result = one.JMP_ANOVA_t_test(DATA, LABELS, alpha=alpha,
                                 print_out=print_out, print_port=lines.append)
    assert list(result) == ['p', 'keys', 'groups']
    assert type(result['p']) is np.ndarray and result['p'].dtype == np.dtype('float64')
    assert type(result['keys']) is list and result['keys'] == LABELS
    assert type(result['groups']) is list and result['groups'] == groups
    assert all(type(g) is list and all(type(i) is int for i in g) for g in result['groups'])
    # 现有算法的 df 是 N-1=9；保留它，不替换成 ANOVA 的误差 df=7。
    expected = np.ones((3, 3))
    for i in range(1, 3):
        for j in range(i):
            se = np.sqrt((15 / 7) * (1 / len(DATA[i]) + 1 / len(DATA[j])))
            expected[i, j] = expected[j, i] = 2 * stats.t.sf(
                abs(np.mean(DATA[i]) - np.mean(DATA[j])) / se, 9)
    np.testing.assert_allclose(result['p'], expected, rtol=1e-10)
    assert capsys.readouterr().out == ''
    if not print_out:
        assert not lines and not tables
        return
    assert tables[0].field_names == ['组别 1', '组别 2', 'p 值']
    assert tables[0].rows == [[LABELS[1], LABELS[0], '0.129'],
        [LABELS[2], LABELS[0], '0.000'], [LABELS[2], LABELS[1], '0.000']]
    assert tables[1].field_names == ['字母分组', '组别', '均值']
    assert [row[1:] for row in tables[1].rows] == [
        [LABELS[2], '11.500'], [LABELS[1], '4.000'], [LABELS[0], '2.000']]
    assert [row[0].strip() for row in tables[1].rows] == (
        ['A', 'B', 'B'] if alpha == .05 else ['A', 'B', 'C'])
    text = '\n'.join(lines)
    assert '自由度 = 9' in text and '合并方差 = 2.143' in text
    assert '未作多重比较校正' in text and '不代表总体均值相等' in text
    assert 'H1：两组总体均值不同（双侧）' in text
    assert '舍入结果，不代表概率严格为零' in text


def test_unbalanced_letter_grouping_does_not_override_significant_pair(monkeypatch):
    tables = capture_tables(monkeypatch, one)
    lines = []
    result = one.JMP_ANOVA_t_test([[-20., 42.], [10.] * 100, [9.] * 100],
        ['A', 'B', 'C'], print_out=True, print_port=lines.append)
    # 原分组算法可令显著不同的 B/C 共用字母；只约束说明，不修改算法。
    assert result['groups'] == [[0, 1, 2]]
    assert result['p'][1, 2] == pytest.approx(2 * stats.t.sf(1 / np.sqrt((1922 / 199) * .02), 201))
    assert result['p'][1, 2] < .05
    assert tables[0].rows[-1] == ['C', 'B', '0.024']
    assert [row[0].strip() for row in tables[1].rows] == ['A', 'A', 'A']
    text = '\n'.join(lines)
    assert '具体差异以逐对 p 值为准' in text
    assert '共享字母表示现有逐对检验未发现显著差异' not in text


@pytest.mark.parametrize('interaction', [False, True])
@pytest.mark.parametrize('print_out', [False, True])
def test_two_way_models_exact_fields_values_and_absent_interaction(monkeypatch, interaction, print_out):
    tables = capture_tables(monkeypatch, two)
    lines = []
    result = two.two_way_anova(CROSSED, interaction=interaction, name_a='温度因子 A',
        name_b='较长批次因子 B', print_out=print_out, print_port=lines.append)
    expected = {'N': 8, 'SSE': 7.5 if interaction else 8.625,
        'MSE': 1.875 if interaction else 1.725, 'SSA': 10.125, 'MSA': 10.125,
        'SSB': 15.125, 'SSAB': 1.125 if interaction else 0, 'MSB': 15.125,
        'MSAB': 1.125 if interaction else -1, 'DF A': 1, 'DF B': 1,
        'DF AB': 1 if interaction else 0, 'F A': 5.4 if interaction else 135 / 23,
        'F B': 121 / 15 if interaction else 605 / 69,
        'F AB': .6 if interaction else -1,
        'p A': stats.f.sf(5.4, 1, 4) if interaction else stats.f.sf(135 / 23, 1, 5),
        'p B': stats.f.sf(121 / 15, 1, 4) if interaction else stats.f.sf(605 / 69, 1, 5),
        'p AB': stats.f.sf(.6, 1, 4) if interaction else -1}
    assert list(result) == list(expected)
    assert result == pytest.approx(expected)
    for key in result:
        integer = key == 'N' or key.startswith('DF ') or (
            not interaction and key in ['SSAB', 'MSAB', 'F AB', 'p AB'])
        typ = int if integer else float if interaction and key in ['SSE', 'MSE'] else np.float64
        assert type(result[key]) is typ
    if not print_out:
        assert not tables and not lines
        return
    assert tables[0].field_names == ['因子', '水平数']
    assert tables[0].rows == [['温度因子 A', 2], ['较长批次因子 B', 2]]
    assert tables[1].field_names == ['来源', '自由度', '调整平方和', '调整均方', 'F 值', 'p 值']
    assert tables[1].rows == ([
        ['温度因子 A', 1, '10.125', '10.125', '5.400', '0.081'],
        ['较长批次因子 B', 1, '15.125', '15.125', '8.067', '0.047'],
        ['温度因子 A*较长批次因子 B', 1, '1.125', '1.125', '0.600', '0.482'],
        ['误差', 4, '7.500', '1.875', '*', '*'], ['总计', 7, '33.875', '*', '*', '*']
    ] if interaction else [
        ['温度因子 A', 1, '10.125', '10.125', '5.870', '0.060'],
        ['较长批次因子 B', 1, '15.125', '15.125', '8.768', '0.031'],
        ['误差', 5, '8.625', '1.725', '*', '*'], ['总计', 7, '33.875', '*', '*', '*']])
    assert '调整平方和采用 III 型' in '\n'.join(lines)
    assert 'alpha' not in '\n'.join(lines)  # 此入口没有显著性参数。


@pytest.mark.parametrize('interaction,rows,values', [
    (True, [
        ['A', 1, '17.515', '17.515', '5.590', '0.064'],
        ['B', 1, '24.242', '24.242', '7.737', '0.039'],
        ['A*B', 1, '3.879', '3.879', '1.238', '0.316'],
        ['误差', 5, '15.667', '3.133', '*', '*'], ['总计', 8, '70.000', '*', '*', '*']],
        [17.515151515151523, 24.24242424242426, 3.878787878787878, 15.666666666666666]),
    (False, [
        ['A', 1, '19.205', '19.205', '5.895', '0.051'],
        ['B', 1, '26.255', '26.255', '8.060', '0.030'],
        ['误差', 6, '19.545', '3.258', '*', '*'], ['总计', 8, '70.000', '*', '*', '*']],
        [19.20454545454546, 26.254545454545465, 0, 215 / 11]),
])
def test_unbalanced_two_way_fixed_original_results(monkeypatch, interaction, rows, values):
    # 无交互 SSE=215/11 由 REVIEW-003 独立矩阵测试验证；其余冻结不变。
    tables = capture_tables(monkeypatch, two)
    result = two.two_way_anova([[[1, 2], [3, 4]], [[2, 4], [5, 8, 10]]],
        interaction=interaction, print_out=True, print_port=lambda line: None)
    assert result['N'] == 9
    assert [result[key] for key in ['SSA', 'SSB', 'SSAB', 'SSE']] == pytest.approx(values)
    assert tables[1].rows == rows


@pytest.mark.parametrize('print_out', [False, True])
def test_nested_main_table_keeps_distinct_model_and_evaluation(monkeypatch, print_out):
    tables = capture_tables(monkeypatch, GRR)
    lines = []
    result = GRR.grr_nested(**NESTED, print_out=print_out, print_port=lines.append)
    expected = {'Distinct Categories': 1, 'P value operator': stats.f.sf(8, 1, 2),
        'P value part': stats.f.sf(8, 2, 4), 'GRR%': 100 * np.sqrt(30 / 37),
        'GRR STD': np.sqrt(30), 'Repeatability STD': np.sqrt(2),
        'Reproducibility STD': np.sqrt(28)}
    assert list(result) == list(expected)
    assert result == pytest.approx(expected)
    assert [type(v) for v in result.values()] == [int, np.float64, np.float64, float, float, float, float]
    if not print_out:
        assert not lines and not tables
        return
    assert len(tables) == 3  # G4 同时规范方差分量和研究变异表。
    assert tables[0].field_names == ['来源', '自由度', '平方和 SS', '均方 MS', 'F 值', 'p 值']
    assert tables[0].rows == [
        ['操作者', 1, '128.000', '128.000', '8.000', '0.106'],
        ['零件（操作者内）', 2, '32.000', '16.000', '8.000', '0.040'],
        ['重复性', 4, '8.000', '2.000', '*', '*'],
        ['合计', 7, '168.000', '*', '*', '*']]
    text = '\n'.join(lines)
    assert '操作员均方 / 操作员内零件均方' in text
    assert '随机效应的方差分量为零' in text
    assert '方差分量' in text and '研究变异' in text


@pytest.mark.parametrize('hist', [None, 3])
def test_nested_not_estimable_marks_main_table_only(monkeypatch, hist):
    tables = capture_tables(monkeypatch, GRR)
    lines = []
    result = GRR.grr_nested(**{**NESTED, 'y': [1] * 8}, hist_std=hist,
                            print_out=True, print_port=lines.append)
    assert np.isnan(result['P value operator']) and np.isnan(result['P value part'])
    assert tables[0].rows[:2] == [
        ['操作者', 1, '0.000', '0.000', '*', '*'],
        ['零件（操作者内）', 2, '0.000', '0.000', '*', '*']]
    assert 'not estimable' in '\n'.join(lines)


@pytest.mark.parametrize('compare', [False, True])
@pytest.mark.parametrize('plot', [False, True])
def test_real_one_way_apply_cleans_routes_and_preserves_plot(monkeypatch, compare, plot):
    lines = []
    plot_view = SimpleNamespace(fig=Figure())
    dialog = SimpleNamespace(df=pd.DataFrame({'甲': [1, 2, 3, 'bad'], '乙': [2, 4, 6, None]}),
        grpcols=['甲', '乙'], xvar=variable(''), grouping=variable(''), alpha=variable(.1),
        comp_mean=variable(compare), show_plot=variable(plot), error=Mock(),
        app=SimpleNamespace(print=lines.append), showPlotViewer=Mock(return_value=plot_view),
        get_y_plot_settings=Mock(), xlabel=variable(''), ylabel='', y_max=None, y_min=None,
        yref=variable(''), yref_label=variable(False), show_grid=variable(False))
    anova_spy = Mock(wraps=one.one_way_anova)
    compare_spy = Mock(wraps=one.JMP_ANOVA_t_test)
    draw = Mock()
    monkeypatch.setattr(anova_dialog, 'one_way_anova', anova_spy)
    monkeypatch.setattr(anova_dialog, 'JMP_ANOVA_t_test', compare_spy)
    monkeypatch.setattr(anova_dialog, 'interval_plot', draw)
    assert anova_dialog.Anova1WayDialog.apply(dialog) is None
    dialog.error.assert_not_called()
    assert anova_spy.call_args.args == ([[1., 2., 3.], [2., 4., 6.]], ['甲', '乙'])
    assert anova_spy.call_args.kwargs['alpha'] == .1
    assert compare_spy.call_count == int(compare) and draw.call_count == int(plot)
    assert dialog.showPlotViewer.call_count == int(plot)
    if plot:
        expected = one.one_way_anova([[1., 2., 3.], [2., 4., 6.]], ['甲', '乙'], alpha=.1)
        assert draw.call_args.kwargs['CIs'] == {
            hash_combined(d): ci for d, ci in zip([[1., 2., 3.], [2., 4., 6.]], expected['CI'])}
        assert draw.call_args.kwargs['ax'] is plot_view.ax
        assert len(plot_view.fig.axes) == 1
    assert ('均值逐对比较' in '\n'.join(lines)) == compare


@pytest.mark.parametrize('groups', [[], ['甲'], ['甲', '乙']])
def test_one_way_apply_input_guards_still_stop_analysis(monkeypatch, groups):
    spy = Mock()
    monkeypatch.setattr(anova_dialog, 'one_way_anova', spy)
    dialog = SimpleNamespace(df=pd.DataFrame({'甲': [1, 1], '乙': [2, 2]}),
        grpcols=groups, xvar=variable(''), grouping=variable(''), alpha=variable(.05),
        error=Mock(), app=SimpleNamespace(print=Mock()))
    assert anova_dialog.Anova1WayDialog.apply(dialog) is None
    dialog.error.assert_called_once()
    spy.assert_not_called()


def test_real_stacked_one_way_apply_keeps_original_cleaning(monkeypatch):
    lines = []
    spy = Mock(wraps=one.one_way_anova)
    monkeypatch.setattr(anova_dialog, 'one_way_anova', spy)
    dialog = SimpleNamespace(df=pd.DataFrame({
        '测量': [1, 2, 'bad', 3, 2, 4, None, 6], '分组': ['甲'] * 4 + ['乙'] * 4}),
        grpcols=[], xvar=variable('测量'), grouping=variable('分组'), alpha=variable(.05),
        comp_mean=variable(False), show_plot=variable(False), error=Mock(),
        app=SimpleNamespace(print=lines.append))
    dialog.make_working_df = lambda **kwargs: anova_dialog.Anova1WayDialog.make_working_df(dialog, **kwargs)
    assert anova_dialog.Anova1WayDialog.apply(dialog) is None
    dialog.error.assert_not_called()
    assert spy.call_args.args[0] == [[1, 2, 3], [2, 4, 6]]
    assert list(spy.call_args.args[1]) == ['甲', '乙']
    assert dialog.working_df['测量'].isna().tolist() == [False, False, True, False, False, False, True, False]
    assert '组数 = 2；总样本量 N = 6' in '\n'.join(lines)


@pytest.mark.parametrize('cls,title', [(anova_dialog.Anova1WayDialog_old, '单因素方差分析'),
                                     (anova_dialog.TtestDialog, '均值逐对比较')])
def test_old_one_way_and_standalone_comparison_apply(cls, title):
    lines = []
    dialog = SimpleNamespace(df=pd.DataFrame({'甲': [1, 2, 3, None], '乙': [2, 4, 6, 'bad']}),
        grpcols=['甲', '乙'], alpha=variable(.05), app=SimpleNamespace(print=lines.append))
    assert cls.apply(dialog) is None
    assert title in '\n'.join(lines)
    assert 'alpha = 0.050' in '\n'.join(lines)


@pytest.mark.parametrize('interaction', [False, True])
def test_real_two_way_apply_cleans_and_routes_model(monkeypatch, interaction):
    lines = []
    spy = Mock(wraps=two.two_way_anova)
    monkeypatch.setattr(anova_dialog, 'two_way_anova', spy)
    df = pd.DataFrame({'温度': ['低'] * 4 + ['高'] * 4 + ['低', np.nan],
        '批次': ['甲', '甲', '乙', '乙'] * 2 + ['甲', '甲'],
        '测量': [1, 2, 3, 4, 2, 4, 5, 8, 'bad', 9]})
    dialog = SimpleNamespace(df=df, xvar=variable('温度'), yvar=variable('批次'),
        zvar=variable('测量'), inter=variable(interaction), app=SimpleNamespace(print=lines.append))
    assert anova_dialog.Anova2WayDialog.apply(dialog) is None
    assert spy.call_args.args == ([1., 2., 3., 4., 2., 4., 5., 8.],)
    assert spy.call_args.kwargs['interaction'] is interaction
    assert spy.call_args.kwargs['factor_listA'] == ['低'] * 4 + ['高'] * 4
    assert spy.call_args.kwargs['name_a'] == '温度'
    assert spy.call_args.kwargs['name_b'] == '批次'
    assert '调整平方和' in '\n'.join(lines)


def test_real_nested_apply_cleans_and_preserves_validation(monkeypatch):
    spy = Mock(wraps=GRR.grr_nested)
    monkeypatch.setattr(qc_dialog, 'grr_nested', spy)
    lines = []
    df = pd.DataFrame({'y': NESTED['y'] + ['bad', 9], 'p': NESTED['part'] + [5, None],
                       'o': NESTED['op'] + ['B', 'B']})
    dialog = SimpleNamespace(df=df, xvar=variable('y'), yvar=variable('p'), ovar=variable('o'),
        hist_std=variable(''), error=Mock(), app=SimpleNamespace(print=lines.append))
    assert qc_dialog.GRR_Nested_Dialog.apply(dialog) is None
    dialog.error.assert_not_called()
    assert spy.call_args.kwargs['y'] == NESTED['y']
    assert spy.call_args.kwargs['part'] == NESTED['part']
    assert '嵌套型量具 R&R' in '\n'.join(lines)
    dialog.df.loc[0, 'p'] = 9
    assert qc_dialog.GRR_Nested_Dialog.apply(dialog) is None
    dialog.error.assert_called_once()


@pytest.mark.parametrize('mode', ['AIAG', 'EMP'])
def test_grr_auto_interaction_routes_report_without_changing_components(monkeypatch, mode):
    spy = Mock(wraps=two.two_way_anova)
    monkeypatch.setattr(GRR, 'two_way_anova', spy)
    inputs = dict(y=[1, 2, 3, 4, 2, 4, 5, 8], part=['P', 'P', 'Q', 'Q'] * 2,
                  op=['A'] * 4 + ['B'] * 4, mode=mode)
    silent = GRR.grr_master(**inputs)
    lines = []
    spy.reset_mock()
    printed = GRR.grr_master(**inputs, print_out=True, print_port=lines.append)
    assert type(printed) is dict and list(printed) == ['EV', 'AV', 'PV', 'RR', 'TV', 'INT']
    assert printed == silent
    assert [type(v) for v in printed.values()] == [type(v) for v in silent.values()]
    first = spy.call_args_list[0].kwargs
    assert first['interaction'] is True and first['print_out'] is False
    assert (first['name_a'], first['name_b']) == ('Part', 'Operator')
    assert all(call.kwargs['print_out'] is False for call in spy.call_args_list[1:])
    text = '\n'.join(lines)
    assert text.count('GRR 交互项筛选：完整模型 ANOVA') == 1
    assert '（%s ANOVA 法）' % mode in text


@pytest.mark.parametrize('module,name,args,kwargs', [
    (one, 'one_way_anova', [DATA, LABELS], {}),
    (one, 'JMP_ANOVA_t_test', [DATA, LABELS], {}),
    (two, 'two_way_anova', [CROSSED], {'name_a': '温度 A', 'name_b': '较长批次 B'}),
    (two, 'two_way_anova', [CROSSED], {'interaction': False}),
    (GRR, 'grr_nested', [], NESTED),
])
def test_report_alignment_in_real_output_font(monkeypatch, viewer, module, name, args, kwargs):
    tables = capture_tables(monkeypatch, module)
    lines = []
    getattr(module, name)(*args, **kwargs, print_out=True, print_port=lines.append)
    viewer.add_txt('\n'.join(lines))
    viewer.main.update()
    for table in tables:
        for column in table.field_names:
            assert table.align[column] == ('l' if column in [
                '组别', '来源', '因子', '组别 1', '组别 2', '字母分组'] else 'r')
        text = str(table)
        assert not any(char in text for char in 'μσαβχ≠')
        assert len({wcswidth(line) for line in text.splitlines()}) == 1
        positions = [[viewer.output_font.measure(line[:i]) for i, char in enumerate(line) if char == '|']
                     for line in text.splitlines() if '|' in line]
        assert positions and all(row == positions[0] for row in positions)


@pytest.mark.parametrize('module,name,old', [
    (one, 'one_way_anova', ['Oneway Anova', 'CI of Mean', 'PT()']),
    (one, 'JMP_ANOVA_t_test', ['Means Comparisons', 'Connecting Report', '%.2f', 'PT()']),
    (two, 'two_way_anova', ['Two Way ANOVA', 'F-value', 'PT()']),
    (GRR, 'grr_nested', ['Gage R&R Nested ANOVA', 'F Ratio', 'P Value']),
])
def test_old_report_patterns_are_gone_only_in_target_print_branch(module, name, old):
    tree = ast.parse(inspect.getsource(getattr(module, name)))
    report = next(node for node in tree.body[0].body if isinstance(node, ast.If)
                  and isinstance(node.test, ast.Name) and node.test.id == 'print_out')
    source = ast.unparse(report)
    for pattern in old:
        assert pattern not in source
    assert 'gen_table' in source and 'format_stat' in source


def test_signatures_and_defaults_remain_public_contract():
    assert str(inspect.signature(one.one_way_anova)) == '(data, labels, print_out=False, print_port=<built-in function print>, alpha=0.05)'
    assert inspect.signature(one.JMP_ANOVA_t_test) == inspect.signature(one.one_way_anova)
    assert str(inspect.signature(two.two_way_anova)) == "(data, factor_listA=None, print_port=<built-in function print>, interaction=True, factor_listB=None, print_out=False, name_a='A', name_b='B')"
    assert str(inspect.signature(GRR.grr_nested)) == '(y=None, op=None, part=None, print_out=False, print_port=<built-in function print>, hist_std=None)'


@pytest.mark.parametrize('function,args,kwargs', [
    (one.one_way_anova, [DATA, LABELS], {'alpha': .1}),
    (one.JMP_ANOVA_t_test, [DATA, LABELS], {'alpha': .2}),
    (two.two_way_anova, [CROSSED], {'interaction': True}),
    (two.two_way_anova, [CROSSED], {'interaction': False}),
    (GRR.grr_nested, [], NESTED),
])
def test_report_switch_preserves_exact_return_values(function, args, kwargs):
    silent = function(*args, **kwargs, print_out=False)
    printed = function(*args, **kwargs, print_out=True, print_port=lambda line: None)
    assert list(silent) == list(printed)
    for key in silent:
        assert type(silent[key]) is type(printed[key])
        if isinstance(silent[key], np.ndarray):
            np.testing.assert_array_equal(silent[key], printed[key])
        else:
            assert silent[key] == printed[key]
