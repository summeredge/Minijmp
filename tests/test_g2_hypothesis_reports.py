"""G2 假设检验：核对真实表格、方法/尾部映射及未格式化的统计结果。"""
import ast
import inspect
from pathlib import Path

import numpy as np
import pytest
from scipy import stats
from wcwidth import wcswidth

import utilities
from bonett import var_1sample as bonett_reference
from chi_sq import chi2_test_stdev, chi2_var_1sample, var_1sample
from proportion_test import (prop_2sample, prop_test_1sample, p_blaker,
                             p_sterne)
from t_test import (paired_t_test, t_test_1sample, t_test_2samples,
                    z_test_1sample)


DATA = [1, 2, 4, 5, 7, 8]
OTHER = [2, 4, 3, 8, 6, 10]
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def report(monkeypatch, capsys):
    tables = []
    original = utilities.gen_table

    def capture(rows):
        table = original(rows)
        tables.append(table)
        return table

    monkeypatch.setattr(utilities, 'gen_table', capture)

    def run(function, *args, **kwargs):
        tables.clear()
        lines = []
        result = function(*args, print_out=True, print_port=lines.append, **kwargs)
        text = '\n'.join(lines)
        assert capsys.readouterr().out == ''
        alpha = kwargs.get('alpha', .05)
        assert f'显著性水平 α = {alpha:.3f}；置信水平 = {1-alpha:.1%}' in text
        assert '样本统计' in text and '检验结果' in text and '置信区间' in text
        assert 'p 值保留三位小数，0.000 为舍入显示。' in text
        assert text.splitlines()[1].startswith('---- ')
        for table in tables:
            assert table.align[table.field_names[0]] == 'l'
            assert all(table.align[name] == 'r' for name in table.field_names[1:])
            rendered = str(table)
            assert rendered in text
            assert len({wcswidth(line) for line in rendered.splitlines()}) == 1
        return result, text, list(tables)

    return run


def numeric_cells(cells, expected):
    """读取真实表格单元格；独立数值断言在各检验中直接针对原始返回值。"""
    assert len(cells) == len(expected)
    for cell, value in zip(cells, expected):
        if value is None or np.isnan(value):
            assert cell == '*'
        else:
            assert float(cell) == pytest.approx(value, rel=0, abs=.00050000001)


def interval_rows(table, interval, lower, upper):
    assert table.field_names == ['区间', '下限', '上限']
    assert [row[0] for row in table.rows] == ['双侧置信区间', '单侧置信下限', '单侧置信上限']
    numeric_cells(table.rows[0][1:], interval)
    numeric_cells(table.rows[1][1:], [lower, None])
    numeric_cells(table.rows[2][1:], [None, upper])


@pytest.mark.parametrize('alpha', [.05, .1])
@pytest.mark.parametrize('null', [0, 10])
@pytest.mark.parametrize('kind', ['t', 'z', 'paired'])
def test_mean_reports_tail_statistics_and_intervals(report, kind, null, alpha):
    sample = np.array(DATA) - np.array(OTHER) if kind == 'paired' else np.array(DATA)
    if kind == 'paired':
        result, text, tables = report(paired_t_test, DATA, OTHER, u0=null, alpha=alpha)
        assert '差值 = 样本 1 - 样本 2' in text
        parameter = 'mu_d'
    else:
        function = t_test_1sample if kind == 't' else z_test_1sample
        extra = {} if kind == 't' else {'s0': 2}
        result, text, tables = report(function, DATA, null, alpha=alpha, **extra)
        parameter = 'mu'
    assert len(tables) == 3
    sd = 2 if kind == 'z' else np.std(sample, ddof=1)
    se = sd / np.sqrt(len(sample))
    statistic = (np.mean(sample) - null) / se
    distribution = stats.norm if kind == 'z' else stats.t(df=len(sample)-1)
    numeric_cells(tables[0].rows[0][1:], [len(sample), np.mean(sample), sd])
    assert tables[1].field_names == ['检验', '备择假设 H1', 'Z' if kind == 'z' else 't', '自由度', 'p 值']
    expected_p = [2 * distribution.sf(abs(statistic)), distribution.cdf(statistic), distribution.sf(statistic)]
    for row, tail, symbol, key, p in zip(tables[1].rows, ['双侧', '左尾', '右尾'],
                                       ['!=', '<', '>'], ['p', 'p lt', 'p gt'], expected_p):
        assert row[:2] == [tail, f'{parameter} {symbol} mu0']
        numeric_cells(row[2:], [statistic, len(sample)-1, p])
        assert result[key] == pytest.approx(p)
    assert result['z' if kind == 'z' else 't'] == pytest.approx(statistic)
    interval = np.mean(sample) + se * distribution.ppf([alpha/2, 1-alpha/2])
    lower, upper = np.mean(sample) + se * distribution.ppf([alpha, 1-alpha])
    np.testing.assert_allclose(result['u0_95range'], interval)
    assert result['u0 lower'] == pytest.approx(lower)
    assert result['u0 upper'] == pytest.approx(upper)
    interval_rows(tables[2], interval, lower, upper)


@pytest.mark.parametrize('kind', ['t', 'z'])
def test_summarized_mean_paths_and_custom_df(report, kind):
    extra = {'sample_mean': 4.5, 'sample_n': 12}
    if kind == 't':
        extra.update(sample_std=2, df=20)
        function = t_test_1sample
    else:
        extra['s0'] = 2
        function = z_test_1sample
    result, text, tables = report(function, [], 3, **extra)
    distribution = stats.t(20) if kind == 't' else stats.norm
    statistic = 1.5 / (2 / np.sqrt(12))
    assert result['p'] == pytest.approx(2 * distribution.sf(statistic))
    numeric_cells(tables[0].rows[0][1:], [12, 4.5, 2])
    numeric_cells(tables[1].rows[0][2:], [statistic, 20 if kind == 't' else 11, result['p']])
    if kind == 'z':
        assert 'Z 检验使用标准正态分布；自由度为沿用的样本信息，不参与 Z 的 p 值或区间计算。' in text


@pytest.mark.parametrize('l1,l2', [(DATA, OTHER[:4]), (DATA[:4], OTHER)])
def test_paired_unequal_lengths_report_only_actual_pairs(report, l1, l2):
    differences = np.array([x-y for x, y in zip(l1, l2)])
    result, _, tables = report(paired_t_test, l1, l2)
    reference = stats.ttest_1samp(differences, 0)
    assert tables[0].rows[0][1] == len(differences)
    assert result['df'] == len(differences)-1
    assert result['t'] == pytest.approx(reference.statistic)
    assert result['p'] == pytest.approx(reference.pvalue)
    numeric_cells(tables[0].rows[0][1:], [len(differences), np.mean(differences), np.std(differences, ddof=1)])
    for row in tables[1].rows:
        numeric_cells([row[3]], [len(differences)-1])


@pytest.mark.parametrize('alpha', [.05, .1])
@pytest.mark.parametrize('pooled', [False, True])
@pytest.mark.parametrize('d0', [-2, 3])
@pytest.mark.parametrize('summarized', [False, True])
def test_two_sample_t_methods_direction_and_only_provided_ci(report, alpha, pooled, d0, summarized):
    extra = ({'n1': len(DATA), 'n2': len(OTHER), 'u1': np.mean(DATA), 'u2': np.mean(OTHER),
              's1': np.std(DATA, ddof=1), 's2': np.std(OTHER, ddof=1)} if summarized
             else {'l1': DATA, 'l2': OTHER})
    result, text, tables = report(t_test_2samples, alpha=alpha, pooled=pooled, d0=d0, **extra)
    assert len(tables) == 3
    assert ('合并方差 t（pooled）' if pooled else 'Welch t（JMP 17，不等方差）') in text
    assert 'H0: μ2 - μ1 = d0' in text
    assert '单侧置信' not in text
    numeric_cells(tables[0].rows[0][1:], [len(DATA), np.mean(DATA), np.std(DATA, ddof=1)])
    numeric_cells(tables[0].rows[1][1:], [len(OTHER), np.mean(OTHER), np.std(OTHER, ddof=1)])
    reference = stats.ttest_ind(np.array(OTHER)-d0, DATA, equal_var=pooled)
    assert result['t'] == pytest.approx(reference.statistic)
    assert result['p'] == pytest.approx(reference.pvalue)
    assert result['df'] == pytest.approx(reference.df)
    for row, symbol, key, p in zip(tables[1].rows, ['!=', '<', '>'],
                                 ['p', 'p lower', 'p upper'],
                                 [reference.pvalue, stats.t.cdf(reference.statistic, reference.df),
                                  stats.t.sf(reference.statistic, reference.df)]):
        assert row[1] == f'mu2 - mu1 {symbol} d0'
        assert result[key] == pytest.approx(p)
        numeric_cells(row[2:], [reference.statistic, reference.df, p])
    interval = np.array(reference.confidence_interval(1-alpha)) + d0
    np.testing.assert_allclose(result['CI'], interval)
    assert len(tables[2].rows) == 1
    numeric_cells(tables[2].rows[0][1:], interval)


@pytest.mark.parametrize('s0', [.5, 5])
@pytest.mark.parametrize('alpha', [.05, .1])
@pytest.mark.parametrize('summarized', [False, True])
def test_chi_square_sd_tails_and_legacy_reference_ranges(report, s0, alpha, summarized):
    extra = {'sample_n': len(DATA), 'sample_std': np.std(DATA, ddof=1)} if summarized else {'data': DATA}
    result, _, tables = report(chi2_var_1sample, s0=s0, alpha=alpha, **extra)
    df = len(DATA)-1
    distribution = stats.chi2(df)
    statistic = df * np.var(DATA, ddof=1) / s0**2
    lower_p, upper_p = distribution.cdf(statistic), distribution.sf(statistic)
    assert result['p'] == pytest.approx(2 * min(lower_p, upper_p))
    for row, symbol, key, p in zip(tables[1].rows, ['!=', '<', '>'], ['p', 'p lt', 'p gt'],
                                 [2 * min(lower_p, upper_p), lower_p, upper_p]):
        assert row[1] == f'sigma {symbol} sigma0'
        assert result[key] == pytest.approx(p)
        numeric_cells(row[2:], [statistic, df, p])
    numerator = np.sqrt(df * np.var(DATA, ddof=1))
    interval = numerator / np.sqrt(distribution.ppf([1-alpha/2, alpha/2]))
    lower = numerator / np.sqrt(distribution.ppf(1-alpha))
    upper = numerator / np.sqrt(distribution.ppf(alpha))
    np.testing.assert_allclose(result['CI 95'], interval)
    assert result['CI lower'] == pytest.approx(lower)
    assert result['CI upper'] == pytest.approx(upper)
    interval_rows(tables[2], interval, lower, upper)
    legacy, text, tables = report(chi2_test_stdev, DATA, s0, alpha=alpha)
    assert len(tables[1].rows) == 1 and tables[1].rows[0][0:2] == ['右尾', 'sigma > sigma0']
    numeric_cells(tables[1].rows[0][2:], [statistic, df, upper_p])
    assert legacy['p'] == pytest.approx(upper_p)
    np.testing.assert_allclose(legacy['95_range_from_S'], interval)
    numeric_cells(tables[2].rows[0][1:], interval)
    assert tables[2].rows[1][0] == '单侧置信上限'
    numeric_cells(tables[2].rows[1][1:], [None, upper])
    quantiles = distribution.ppf([alpha/2, 1-alpha/2])
    sampling_range = np.sqrt(quantiles * s0**2 / df)
    numeric_cells(tables[3].rows[0][1:], quantiles)
    numeric_cells(tables[3].rows[1][1:], sampling_range)
    np.testing.assert_allclose(legacy['95_chi2_range'], quantiles)
    np.testing.assert_allclose(legacy['95_range_from_P'], sampling_range)
    assert '样本标准差的抽样分布中央区间' in text


@pytest.mark.parametrize('mode', ['data', 'summary', 'small'])
def test_combined_sd_methods_and_unavailable_bonett(report, mode):
    sample = [1, 3] if mode == 'small' else DATA
    extra = ({'sample_n': len(sample), 'sample_std': np.std(sample, ddof=1)}
             if mode == 'summary' else {'data': sample})
    result, text, tables = report(var_1sample, s0=2, alpha=.01, **extra)
    chi = chi2_var_1sample(s0=2, alpha=.01, **extra)
    bonett = bonett_reference(sample, s0=2, alpha=.01) if mode == 'data' else None
    assert tables[1].field_names == ['方法', 'p 值']
    assert tables[2].field_names == ['方法', '双侧下限', '双侧上限', '单侧置信下限', '单侧置信上限']
    assert [row[0] for row in tables[1].rows] == ['卡方', 'Bonett']
    assert result['p'] == chi['p']
    numeric_cells(tables[1].rows[0][1:], [chi['p']])
    numeric_cells(tables[2].rows[0][1:], [*chi['CI 95'], chi['CI lower'], chi['CI upper']])
    if bonett is None:
        assert np.isnan(result['Bonett p'])
        assert tables[1].rows[1][1:] == ['*']
        assert tables[2].rows[1][1:] == ['*'] * 4
    else:
        assert result['Bonett p'] == bonett['Bonett p']
        numeric_cells(tables[1].rows[1][1:], [bonett['Bonett p']])
        numeric_cells(tables[2].rows[1][1:], [*bonett['Bonett CI'], bonett['One tail lower boundary'], bonett['One tail upper boundary']])
    assert '近似推断' in text and '重尾分布需谨慎' in text


@pytest.mark.parametrize('alpha', [.05, .1])
@pytest.mark.parametrize('events,p0', [(0, .4), (3, .4), (14, .4), (20, .6)])
def test_single_proportion_all_methods_intervals_and_nested_chi(report, alpha, events, p0):
    result, text, tables = report(prop_test_1sample, events=events, N=20, p0=p0, alpha=alpha)
    assert len(tables) == 4
    numeric_cells(tables[0].rows[0][1:], [20, events, events/20])
    assert '双侧 p ≠ p0；左尾 p < p0；右尾 p > p0' in text
    assert tables[1].field_names == ['方法', '双侧 p 值', '左尾 p 值', '右尾 p 值']
    assert [row[0] for row in tables[1].rows] == ['正态近似', 'Sterne 精确', 'Blaker 精确', '调整 Blaker 精确', '二项精确']
    z = (events/20 - p0) / np.sqrt(p0*(1-p0)/20)
    expected = [2 * stats.norm.sf(abs(z)), stats.norm.cdf(z), stats.norm.sf(z)]
    numeric_cells(tables[1].rows[0][1:], expected)
    assert result['p norm'] == pytest.approx(expected[0])
    assert result['Z p less'] == pytest.approx(expected[1])
    for row, key, reference in [(tables[1].rows[1], 'p Sterne', p_sterne),
                                (tables[1].rows[2], 'p Blaker', p_blaker)]:
        assert result[key] == reference(20, p0, events)
        numeric_cells(row[1:], [result[key], None, None])
    numeric_cells(tables[1].rows[3][1:], [result['Blaker p'], None, None])
    left = stats.binomtest(events, 20, p0, alternative='less').pvalue
    right = stats.binomtest(events, 20, p0, alternative='greater').pvalue
    assert result['p Binomial'] == pytest.approx(left)
    numeric_cells(tables[1].rows[4][1:], [None, left, right])
    assert tables[2].field_names == ['方法', '双侧下限', '双侧上限', '单侧置信下限', '单侧置信上限']
    for row, key in zip(tables[2].rows[:2], ['CI norm', 'CI exact']):
        numeric_cells(row[1:], [result[key][k] for k in ['CI l', 'CI u', 'CI low', 'CI high']])
    se = np.sqrt((events/20)*(1-events/20)/20)
    norm_ci = np.clip(events/20 + stats.norm.ppf([alpha/2, 1-alpha/2, alpha, 1-alpha])*se, 0, 1)
    np.testing.assert_allclose([result['CI norm'][k] for k in ['CI l', 'CI u', 'CI low', 'CI high']], norm_ci)
    if 0 < events < 20:
        exact = [stats.beta.ppf(alpha/2, events, 21-events), stats.beta.ppf(1-alpha/2, events+1, 20-events),
                 stats.beta.ppf(alpha, events, 21-events), stats.beta.ppf(1-alpha, events+1, 20-events)]
        np.testing.assert_allclose([result['CI exact'][k] for k in ['CI l', 'CI u', 'CI low', 'CI high']], exact)
    numeric_cells(tables[2].rows[2][1:], [*result['Blaker CI'], None, None])
    contingency = [[events, 20-events], [10000*20*p0, 10000*20*(1-p0)]]
    for row, suffix, method in zip(tables[3].rows, ['Pearson', 'LR'], [None, 'log-likelihood']):
        reference = stats.chi2_contingency(contingency, correction=False, lambda_=method)
        assert result['JMP chi sq']['chi sq '+suffix] == pytest.approx(reference.statistic)
        assert result['JMP chi sq']['p '+suffix] == pytest.approx(reference.pvalue)
        numeric_cells(row[1:], [reference.statistic, reference.dof, reference.pvalue])
    assert [row[0] for row in tables[3].rows] == ['Pearson', '似然比']
    assert '---- Chi square test ----' not in text


@pytest.mark.parametrize('alpha', [.05, .1])
@pytest.mark.parametrize('e1,e2', [(3, 14), (14, 3)])
def test_two_proportion_methods_difference_and_tail_columns(report, alpha, e1, e2):
    n1, n2 = 20, 25
    result, text, tables = report(prop_2sample, n1=n1, n2=n2, e1=e1, e2=e2, alpha=alpha)
    assert 'H0: p1 - p2 = 0' in text
    assert '双侧 p1 - p2 ≠ 0；左尾 p1 - p2 < 0；右尾 p1 - p2 > 0' in text
    assert tables[1].field_names == ['方法', 'Z', '双侧 p 值', '左尾 p 值', '右尾 p 值']
    assert [row[0] for row in tables[1].rows] == ['Fisher 精确', '正态近似（非合并）', '正态近似（合并）']
    for row, n, e in zip(tables[0].rows, [n1, n2], [e1, e2]):
        numeric_cells(row[1:], [n, e, e/n])
    for column, alternative, key in [(2, 'two-sided', 'p Fisher'), (3, 'less', 'p p1<p2 Fisher'), (4, 'greater', 'p p1>p2 Fisher')]:
        reference = stats.fisher_exact([[e1, n1-e1], [e2, n2-e2]], alternative=alternative).pvalue
        assert result[key] == pytest.approx(reference)
        numeric_cells([tables[1].rows[0][column]], [reference])
    assert tables[1].rows[0][1] == '*'
    difference = e1/n1 - e2/n2
    sep = np.sqrt((e1/n1)*(1-e1/n1)/n1 + (e2/n2)*(1-e2/n2)/n2)
    pooled_p = (e1+e2)/(n1+n2)
    pooled = np.sqrt(pooled_p*(1-pooled_p)*(1/n1+1/n2))
    for row, se, suffix, two_key in zip(tables[1].rows[1:], [sep, pooled], ['', ' Pooled'], ['p sep', 'p Pooled']):
        z = difference/se
        ps = [2*stats.norm.sf(abs(z)), stats.norm.cdf(z), stats.norm.sf(z)]
        numeric_cells(row[1:], [z, *ps])
        for key, expected in zip([two_key, 'p p1<p2'+suffix, 'p p1>p2'+suffix], ps):
            assert result[key] == pytest.approx(expected)
    interval = difference + stats.norm.ppf([alpha/2, 1-alpha/2])*sep
    lower, upper = difference + stats.norm.ppf([alpha, 1-alpha])*sep
    interval_rows(tables[2], interval, lower, upper)


@pytest.mark.parametrize('function,args,kwargs', [
    (t_test_1sample, (DATA, 3), {}), (z_test_1sample, (DATA, 3, 2), {}),
    (paired_t_test, (DATA, OTHER), {}), (t_test_2samples, (DATA, OTHER), {}),
    (chi2_test_stdev, (DATA, 2), {}), (chi2_var_1sample, (DATA,), {'s0': 2}),
    (var_1sample, (DATA,), {'s0': 2}), (prop_test_1sample, (3, 20, .4), {}),
    (prop_2sample, (), {'n1': 20, 'n2': 25, 'e1': 3, 'e2': 14})])
def test_print_out_false_is_silent_and_does_not_build_tables(monkeypatch, capsys, function, args, kwargs):
    def unexpected(*args, **kwargs):
        pytest.fail('print_out=False 不应构建报告')
    monkeypatch.setattr(utilities, 'gen_table', unexpected)
    function(*args, print_out=False, print_port=unexpected, **kwargs)
    assert capsys.readouterr().out == ''


@pytest.mark.parametrize('function,signature', [
    (t_test_1sample, '(data_list, u0, print_out=False, sample_mean=None, sample_std=None, sample_n=None, df=None, alpha=0.05, print_port=<built-in function print>)'),
    (z_test_1sample, '(data_list, u0, s0, sample_mean=None, alpha=0.05, sample_n=None, print_out=True, print_port=<built-in function print>)'),
    (paired_t_test, '(l1, l2, print_out=False, u0=0, alpha=0.05, print_port=<built-in function print>)'),
    (t_test_2samples, '(l1=None, l2=None, n1=None, n2=None, u1=None, u2=None, s1=None, s2=None, alpha=0.05, d0=0, pooled=False, print_out=False, print_port=<built-in function print>)'),
    (chi2_test_stdev, '(data_list, s0, print_out=False, alpha=0.05, print_port=<built-in function print>)'),
    (chi2_var_1sample, '(data=None, sample_n=None, sample_std=None, print_port=<built-in function print>, print_out=False, alpha=0.05, s0=None)'),
    (var_1sample, '(data=None, sample_n=None, sample_std=None, print_port=<built-in function print>, print_out=False, alpha=0.05, s0=None)'),
    (prop_test_1sample, '(events=1, N=1, p0=1, print_port=<built-in function print>, print_out=False, alpha=0.05)'),
    (prop_2sample, '(n1=None, n2=None, e1=None, e2=None, alpha=0.05, print_out=False, print_port=<built-in function print>)')])
def test_signatures_and_defaults_preserved(function, signature):
    assert str(inspect.signature(function)) == signature


def test_scoped_old_report_builders_removed_and_lf_preserved():
    targets = {'t_test.py': ['t_test_1sample', 'z_test_1sample', 'paired_t_test', 't_test_2samples'],
               'chi_sq.py': ['chi2_test_stdev', 'chi2_var_1sample', 'var_1sample'],
               'proportion_test.py': ['prop_test_1sample', 'prop_2sample']}
    for filename, functions in targets.items():
        raw = (ROOT/'code'/filename).read_bytes()
        assert b'\r\n' not in raw
        for node in ast.parse(raw).body:
            if isinstance(node, ast.FunctionDef) and node.name in functions:
                assert not any(isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
                               and call.func.id == 'PT' for call in ast.walk(node))
                assert any(isinstance(item, ast.ImportFrom) and item.module == 'utilities'
                           for item in ast.walk(node))
    assert b'\r\n' not in Path(__file__).read_bytes()
