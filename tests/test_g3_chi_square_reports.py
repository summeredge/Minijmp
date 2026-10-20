"""卡方报告：固定改前代表值、SciPy 参考及真实 Dialog apply；不依赖本机快照。"""
import ast
import inspect
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
from scipy.stats import chi2_contingency
from wcwidth import wcswidth

import chi2_dialog
import chi_sq
import proportion_test
import utilities


ROOT = Path(__file__).resolve().parents[1]
KEYS = ['p Pearson', 'chi sq Pearson', 'df', 'p LR', 'chi sq LR']
DATA = [[95, 43], [101, 64]]


def variable(value):
    return SimpleNamespace(get=lambda: value)


def assert_result(actual, expected):
    assert type(actual) is dict
    assert list(actual) == KEYS
    for key, value in zip(KEYS, expected):
        assert type(actual[key]) is (int if key == 'df' else np.float64)
        if np.isnan(value):
            assert np.isnan(actual[key])
        else:
            assert actual[key] == value


@pytest.fixture
def tables(monkeypatch):
    captured = []
    original = utilities.gen_table

    def capture(rows):
        table = original(rows)
        captured.append(table)
        return table

    monkeypatch.setattr(utilities, 'gen_table', capture)
    monkeypatch.setattr(chi2_dialog, 'gen_table', capture)
    return captured


def assert_table_layout(tables, text):
    for table in tables:
        assert str(table) in text
        assert table.align[table.field_names[0]] == 'l'
        assert all(table.align[name] == 'r' for name in table.field_names[1:])
        assert len({wcswidth(line) for line in str(table).splitlines()}) == 1
        assert not any(c in str(table) for c in 'χμσρ≠')


def assert_results_table(table, result):
    assert table.field_names == ['方法', '卡方统计量', '自由度', 'p 值']
    assert table.rows == [
        ['Pearson', f"{result['chi sq Pearson']:.3f}", result['df'], f"{result['p Pearson']:.3f}"],
        ['似然比', f"{result['chi sq LR']:.3f}", result['df'], f"{result['p LR']:.3f}"]]


# 代表值取自修改前实现；保留浮点原值而非三位小数报告值。
@pytest.mark.parametrize('data,expected', [
    (DATA, [0.16647204780896319, 1.9144295348814409, 1, 0.1655331296500937, 1.9229380806084624]),
    ([[0, 10], [5, 5]], [0.009823274507519186, 6.666666666666667, 1, 0.0033058769121899756, 8.630462173553425]),
    ([[30, 76, 49], [1, 37, 62], [11, 11, 26]], [9.990869065390484e-08, 38.24152269158459, 4, 1.8787608135895084e-09, 46.564810865779506]),
    ([[1.5, 2.5], [3.5, 4.5]], [0.8359944985248411, 0.04285714285714286, 1, 0.8355273836921946, 0.043105162109427664]),
    ([[0, 0], [5, 5]], [np.nan, np.nan, 1, np.nan, np.nan]),
    ([[1000, 1], [1, 1000]], [0., 1994.007992007992, 1, 0., 2743.728290512426])])
@pytest.mark.parametrize('print_out', [False, True])
def test_fixed_before_values_types_keys_and_print_switch(data, expected, print_out, capsys):
    lines = []
    with np.errstate(divide='ignore', invalid='ignore'):
        result = chi_sq.chi_square(data, print_out=print_out, print_port=lines.append)
    assert_result(result, expected)
    assert bool(lines) is print_out
    assert capsys.readouterr().out == ''


def test_contingency_cells_expected_totals_order_and_hypotheses(tables):
    lines = []
    result = chi_sq.chi_square(DATA, print_port=lines.append, print_table=True,
                               rKeys=['中文长行标签一', 'row B'], cKeys=['列甲', 'long column B'])
    text = '\n'.join(lines)
    assert '卡方独立性检验' in text and 'H0：行变量与列变量相互独立' in text
    assert 'H1：行变量与列变量不独立' in text and '未作连续性校正' in text
    assert '0.000 为舍入显示，不代表概率严格为零' in text
    assert '不是 H0 成立的概率' in text
    assert len(tables) == 2
    counts = tables[0]
    assert counts.field_names == ['行 / 列', '列甲', 'long column B', '合计']
    expected = chi2_contingency(DATA, correction=False).expected_freq
    assert [row[0] for row in counts.rows] == ['中文长行标签一', 'row B', '合计']
    for y, row in enumerate(counts.rows[:2]):
        assert row[1:-1] == [f'{DATA[y][x]:g} / {expected[y, x]:.3f}' for x in range(2)]
        assert float(row[-1]) == sum(DATA[y])
    assert list(map(float, counts.rows[-1][1:])) == [196., 107., 303.]
    assert_results_table(tables[1], result)
    assert_table_layout(tables, text)


def test_large_observed_counts_are_not_rounded_to_six_significant_digits(tables):
    data = [[12345678, 99999999], [9, 2]]
    chi_sq.chi_square(data, print_port=lambda text: None, print_table=True,
                      rKeys=['A', 'B'], cKeys=['C', 'D'])
    assert tables[0].rows[0][1].split(' / ')[0] == '12345678'
    assert tables[0].rows[0][2].split(' / ')[0] == '99999999'


@pytest.mark.parametrize('print_table,rkeys,ckeys,count', [
    (False, ['A', 'B'], ['C', 'D'], 1),
    (True, None, ['C', 'D'], 1),
    (True, ['A', 'B'], None, 1),
    (True, None, None, 1),
    (True, ['A', 'B'], ['C', 'D'], 2)])
def test_contingency_table_switch_and_missing_labels(tables, print_table, rkeys, ckeys, count):
    lines = []
    chi_sq.chi_square(DATA, print_port=lines.append, print_table=print_table, rKeys=rkeys, cKeys=ckeys)
    assert len(tables) == count
    assert ('列联表（观测频数' in '\n'.join(lines)) is (count == 2)


@pytest.mark.parametrize('data,warning', [(DATA, False), ([[0, 10], [5, 5]], True)])
def test_small_expected_warning_uses_existing_frequencies(tables, data, warning):
    lines = []
    chi_sq.chi_square(data, print_port=lines.append)
    text = '\n'.join(lines)
    assert ('期望频数小于 5' in text) is warning
    if warning:
        assert '2/4 个单元格' in text


def test_unavailable_results_and_rounded_zero_are_explicit(tables):
    lines = []
    with np.errstate(divide='ignore', invalid='ignore'):
        chi_sq.chi_square([[0, 0], [5, 5]], print_port=lines.append)
    assert tables[-1].rows == [['Pearson', '*', 1, '*'], ['似然比', '*', 1, '*']]
    assert '* 表示不可用' in '\n'.join(lines)
    lines.clear()
    chi_sq.chi_square([[1000, 1], [1, 1000]], print_port=lines.append)
    assert [row[-1] for row in tables[-1].rows] == ['0.000', '0.000']
    assert '不代表概率严格为零' in '\n'.join(lines)


@pytest.fixture
def route(monkeypatch):
    calls = []
    original = chi_sq.chi_square

    def capture(data, **kwargs):
        result = original(data, **kwargs)
        calls.append((data, kwargs, result))
        return result

    monkeypatch.setattr(chi2_dialog, 'chi_square', capture)
    monkeypatch.setattr(proportion_test, 'chi_square', capture)
    return calls


@pytest.mark.parametrize('mode', ['raw', 'summary', 'summary_labels'])
def test_independence_real_apply_routing_cleaning_and_return(tables, route, mode):
    lines = []
    dialog = SimpleNamespace(app=SimpleNamespace(print=lines.append), rvar=variable(''))
    if mode == 'raw':
        dialog.df = pd.DataFrame({'r': ['甲', '甲', '乙', '乙', '甲', None, '乙'],
                                  'c': ['a', 'b', 'a', 'b', 'a', 'b', '']})
        dialog.grpcols = []
        dialog.xvar, dialog.yvar = variable('r'), variable('c')
        expected, rkeys, ckeys = [[1, 1], [2, 1]], ['乙', '甲'], ['a', 'b']
        # 分类排序沿用 utilities；中文 Unicode 顺序为乙、甲。
    else:
        dialog.df = pd.DataFrame({'x': [10, 20, 30, 'bad'], 'y': [20, 10, 30, 9],
                                  'label': ['组甲', '组乙', 'long row C', '']})
        dialog.grpcols = ['x', 'y']
        if mode == 'summary_labels':
            dialog.rvar = variable('label')
        expected, ckeys = [[10., 20.], [20., 10.], [30., 30.]], ['x', 'y']
        rkeys = ['组甲', '组乙', 'long row C'] if mode == 'summary_labels' else ['A', 'B', 'C']
    assert chi2_dialog.Chi2TableDialog.apply(dialog) is None
    assert len(route) == 1
    data, kwargs, result = route[0]
    assert data == expected
    assert kwargs == dict(print_out=True, print_port=dialog.app.print, print_table=True, cKeys=ckeys, rKeys=rkeys)
    reference = chi2_contingency(expected, correction=False)
    assert result['chi sq Pearson'] == pytest.approx(reference.statistic)
    assert result['p Pearson'] == pytest.approx(reference.pvalue)
    assert_results_table(tables[-1], result)
    assert_table_layout(tables, '\n'.join(lines))


def probability_dialog(monkeypatch, probabilities, calls, cancelled=False):
    def prompt(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(result=None if cancelled else True, results=probabilities)
    monkeypatch.setattr(chi2_dialog, 'ProbabilityDialog', prompt)


@pytest.mark.parametrize('mode', ['raw', 'summary', 'normalized'])
def test_goodness_of_fit_real_apply_probabilities_route_and_existing_results(tables, route, monkeypatch, mode):
    lines, errors, prompts = [], [], []
    dialog = SimpleNamespace(app=SimpleNamespace(print=lines.append), error=errors.append,
                             parent=object(), rvar=variable(''), cnt=variable(''), xvar=variable('raw'))
    if mode == 'raw':
        dialog.df = pd.DataFrame({'raw': ['甲', '乙', '甲', None, '', '乙', '乙']})
        counts, labels = [3, 2], ['乙', '甲']
    else:
        dialog.df = pd.DataFrame({'level': ['乙', '甲', None], 'count': [30., 20., 999.]})
        dialog.rvar, dialog.cnt = variable('level'), variable('count')
        counts, labels = [30., 20.], ['乙', '甲']
    probabilities = [2., 3.] if mode == 'normalized' else [.4, .6]
    probability_dialog(monkeypatch, probabilities, prompts)
    assert chi2_dialog.Chi2PropDialog.apply(dialog) is None
    assert len(prompts) == len(route) == 1
    assert prompts[0]['labels'] == labels and prompts[0]['types'] == ['float', 'float']
    assert prompts[0]['parent'] is dialog.parent and prompts[0]['initialvalues'] == [0, 0]
    assert bool(errors) is (mode == 'normalized')
    data, kwargs, result = route[0]
    assert data == [counts, [.4 * sum(counts) * 1e9, .6 * sum(counts) * 1e9]]
    assert kwargs == dict(print_out=False, print_port=dialog.app.print, print_table=False)
    assert list(result) == KEYS and type(result['df']) is int
    for method, suffix in [(None, 'Pearson'), ('log-likelihood', 'LR')]:
        reference = chi2_contingency(data, correction=False, lambda_=method)
        assert result['chi sq ' + suffix] == pytest.approx(reference.statistic, abs=1e-5)
        assert result['p ' + suffix] == pytest.approx(reference.pvalue, abs=1e-6)
    text = '\n'.join(lines)
    assert '卡方拟合优度检验' in text and '卡方独立性检验' not in text
    assert 'H0：各水平的总体概率等于指定的假设概率' in text
    assert 'H1：至少一个水平的总体概率不同于假设概率' in text
    assert '大样本参考行' in text and '未作连续性校正' in text
    assert '未提供各水平的期望频数；不另行推算' in text
    assert '本报告未对小期望频数作自动判断' in text
    assert '不是 H0 成立的概率' in text and '不代表概率严格为零' in text
    assert len(tables) == 2
    assert tables[0].field_names == ['水平', '观测频数', '估计概率', '假设概率']
    assert tables[0].rows == [[labels[i], counts[i], f'{counts[i]/sum(counts):.3f}', f'{[.4,.6][i]:.3f}'] for i in range(2)]
    assert_results_table(tables[1], result)
    assert_table_layout(tables, text)


@pytest.mark.parametrize('probabilities,cancelled,error', [
    ([.4, .6], True, None), ([1.], False, '输入无效。'),
    ([0., 1.], False, '假设概率必须大于 0 且小于 1。'),
    ([-.1, 1.1], False, '假设概率必须大于 0 且小于 1。')])
def test_goodness_of_fit_preserves_cancel_and_input_guards(route, monkeypatch, probabilities, cancelled, error):
    prompts, lines, errors = [], [], []
    probability_dialog(monkeypatch, probabilities, prompts, cancelled=cancelled)
    dialog = SimpleNamespace(df=pd.DataFrame({'level': ['A','B'], 'count': [10,20]}),
                             rvar=variable('level'), cnt=variable('count'), parent=object(),
                             app=SimpleNamespace(print=lines.append), error=errors.append)
    assert chi2_dialog.Chi2PropDialog.apply(dialog) is None
    assert errors == ([] if error is None else [error])
    assert not route and not lines


@pytest.mark.parametrize('print_out', [False, True])
def test_g2_single_proportion_keeps_silent_nested_route_and_report(tables, route, print_out):
    lines = []
    result = proportion_test.prop_test_1sample(9, 250, .073, print_out=print_out, print_port=lines.append)
    assert len(route) == 1
    data, kwargs, nested = route[0]
    assert data == [[9, 241], [10000 * 250 * .073, 10000 * 250 * (1 - .073)]]
    assert kwargs['print_out'] is False and kwargs['print_port'] == lines.append
    assert result['JMP chi sq'] is nested
    for suffix in ['Pearson', 'LR']:
        reference = chi2_contingency(data, correction=False, lambda_=None if suffix == 'Pearson' else 'log-likelihood')
        assert nested['chi sq ' + suffix] == pytest.approx(reference.statistic)
        assert nested['p ' + suffix] == pytest.approx(reference.pvalue)
    text = '\n'.join(lines)
    assert bool(lines) is print_out
    assert '卡方独立性检验' not in text and '卡方拟合优度检验' not in text
    if print_out:
        assert 'JMP 列联表' in text
        assert_results_table(tables[-1], nested)


def test_scoped_old_report_patterns_and_signature_contract():
    source = inspect.getsource(chi_sq.chi_square)
    for old in ['Contingency Table', 'Count/Expected', 'P > ChiSq', 'Likelihood Ratio', 'PT()']:
        assert old not in source
    signature = inspect.signature(chi_sq.chi_square)
    assert list(signature.parameters) == ['data', 'print_out', 'print_port', 'print_table', 'rKeys', 'cKeys']
    assert [p.default for p in list(signature.parameters.values())[1:]] == [True, print, False, None, None]
    tree = ast.parse((ROOT / 'code/chi2_dialog.py').read_bytes())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Chi2PropDialog')
    apply = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'apply')
    report_source = ast.unparse(apply)
    for old in ['Test Probabilities', 'Est Prob', 'Hypoth Prob', 'PT()']:
        assert old not in report_source
    assert 'sum(res) != 1' in report_source
    assert 'any((_ <= 0 for _ in res))' in report_source
    assert 'd.result is None' in report_source
    assert 'ratio = sum(cnts) * 1000000000.0' in report_source


def test_chinese_and_ascii_tables_align_in_real_output_font(tk_root, monkeypatch):
    from txt_output import txt_viewer
    lines = []
    chi_sq.chi_square(DATA, print_port=lines.append, print_table=True,
                      rKeys=['中文长行标签一', 'row B'], cKeys=['列甲', 'long column B'])
    probability_dialog(monkeypatch, [.4, .6], [])
    dialog = SimpleNamespace(df=pd.DataFrame({'level': ['中文长行标签一', 'row B'], 'count': [10, 20]}),
                             rvar=variable('level'), cnt=variable('count'), parent=tk_root,
                             app=SimpleNamespace(print=lines.append), error=lambda message: pytest.fail(message))
    chi2_dialog.Chi2PropDialog.apply(dialog)
    viewer = txt_viewer(None)
    try:
        for block in lines:
            rows = [line for line in block.splitlines() if line.startswith('|')]
            if not rows:
                continue
            positions = [[viewer.output_font.measure(line[:i]) for i, c in enumerate(line) if c == '|'] for line in rows]
            assert all(position == positions[0] for position in positions)
    finally:
        viewer.close()
