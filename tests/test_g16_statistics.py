"""G16 numerical/protocol oracles use the immutable, pre-optimization HEAD.

Independent formula and work-count tests supplement the legacy comparisons.
"""
import ast
import inspect
from pathlib import Path
import statistics as stat
import subprocess
import types
from unittest.mock import Mock

import numpy as np
import pytest
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
BEFORE = '38b907f0dcf62f234561838f3cca93ad0a8545ef'


@pytest.fixture(scope='module')
def old():
    modules = {}
    for name in ('linear_fit', 'chi_sq', 'nonpara_cor', 'fit_dialog', 'binomial',
                 'proportion_test', 'dist_fit', 'two_way_anova', 'GRR'):
        source = subprocess.check_output(['git', 'show', f'{BEFORE}:code/{name}.py'],
                                         cwd=ROOT).decode('utf-8')
        module = types.ModuleType('g16_before_' + name)
        exec(compile(source, f'g16_before/{name}.py', 'exec'), module.__dict__)
        modules[name] = module
    modules['proportion_test'].binomial = modules['binomial'].binomial
    modules['GRR'].two_way_anova = modules['two_way_anova'].two_way_anova
    return types.SimpleNamespace(**modules)


def equal(actual, expected):
    if isinstance(expected, dict):
        assert actual.keys() == expected.keys()
        for key in expected:
            equal(actual[key], expected[key])
    elif isinstance(expected, (list, tuple)):
        assert type(actual) is type(expected)
        assert len(actual) == len(expected)
        for a, b in zip(actual, expected):
            equal(a, b)
    elif isinstance(expected, (int, float, np.number)):
        assert actual == pytest.approx(expected, rel=2e-12, abs=1e-12, nan_ok=True)
    else:
        assert actual == expected


def same_call(actual, expected, *args, **kwargs):
    before_lines, after_lines = [], []
    result = expected(*args, print_port=before_lines.append, **kwargs)
    equal(actual(*args, print_port=after_lines.append, **kwargs), result)
    assert list(map(str, after_lines)) == list(map(str, before_lines))


@pytest.mark.parametrize('x,y', [
    ([1., 1., 2., 2., 3., 3.], [2., 3., 4., 6., 5., 8.]),
    ([1., 1., 2., 2., 3., 3.], [3., 3., 5., 5., 7., 7.]),
    ([1., 2., 3., 4., 5., 6.], [2., 3., 4., 6., 5., 8.]),
    ([1., 1., 1., 2., 2., 2.], [2., 3., 4., 6., 5., 8.]),
    ([1e9 + x for x in [1, 1, 2, 2, 3, 3]], [2., 3., 4., 6., 5., 8.]),
    ([1., 1., 2., 2., np.nan, np.nan], [1., 2., 3., 4., 5., 6.]),
    ([np.nan] * 6, [1., 2., 3., 4., 5., 6.]),
    ([1., 1., 2., 2., np.inf, np.inf], [1., 2., 3., 4., 5., 6.]),
])
def test_f01_numerical_and_report(old, x, y):
    from linear_fit import linear_fit
    same_call(linear_fit, old.linear_fit.linear_fit, x, y, print_out=True)
    result = linear_fit(x, y, print_out=False)
    groups = [[b for a, b in zip(x, y) if a == v] for v in set(x)]
    pe = sum(sum((v - stat.mean(g))**2 for v in g) for g in groups)
    assert result['SSPE'] == pytest.approx(pe)


@pytest.mark.parametrize('x,y', [([], []), ([1, 1, 1], [2, 3, 4]),
                                ([1, 2], [2, 4]), ([1, 2, 3], [1, 1, 1])])
def test_f01_degenerate_errors(old, x, y):
    from linear_fit import linear_fit
    with pytest.raises(Exception) as before:
        old.linear_fit.linear_fit(x, y, print_out=False)
    with pytest.raises(type(before.value)):
        linear_fit(x, y, print_out=False)


def test_f01_group_mean_work(monkeypatch):
    import linear_fit
    mean = Mock(wraps=stat.mean)
    monkeypatch.setattr(linear_fit.stat, 'mean', mean)
    x = [1., 2., 3.] * 20
    linear_fit.linear_fit(x, list(range(60)), print_out=False)
    assert mean.call_count == 6  # Three overall means, one per X level.


@pytest.mark.parametrize('groups', [
    [[1., 2., 4.], [2., 5., 9.], [1., 5., 7.]],
    [[1., 1., 1., 5.], [2., 2., 8., 20., 25.]],
    [[-5., -4., -2., 0.], [1., 3., 6., 10., 15.], [2., 3., 5.]],
])
def test_f11_numerical_report_and_scipy(old, groups):
    from chi_sq import multi_pop_var_test
    labels = list('ABC')[:len(groups)]
    same_call(multi_pop_var_test, old.chi_sq.multi_pop_var_test, groups, labels, print_out=True)
    result = multi_pop_var_test(groups, labels)
    for name, center in [('Levene', 'mean'), ('Brown_Forsythe', 'median')]:
        reference = stats.levene(*groups, center=center)
        assert result[name]['F'] == pytest.approx(reference.statistic)
        assert result[name]['p'] == pytest.approx(reference.pvalue)
    reference = stats.f_oneway(*stats.obrientransform(*groups)) if len(set(map(len, groups))) == 1 else None
    if reference:
        assert result['OBrien']['F'] == pytest.approx(reference.statistic)


@pytest.mark.parametrize('groups', [[], [[1.], [2.]], [[1., 2.], [3., 4.]],
                                     [[1., 1., 1.], [2., 2., 2.]]])
def test_f11_degenerate(old, groups):
    from chi_sq import multi_pop_var_test
    try:
        expected = old.chi_sq.multi_pop_var_test(groups, list('ABC'))
    except Exception as before:
        with pytest.raises(type(before)):
            multi_pop_var_test(groups, list('ABC'))
    else:
        equal(multi_pop_var_test(groups, list('ABC')), expected)


def test_f11_statistics_count(monkeypatch):
    import chi_sq
    spies = {name: Mock(wraps=getattr(stat, name)) for name in ('mean', 'variance', 'median')}
    for name, spy in spies.items():
        monkeypatch.setattr(chi_sq.stat, name, spy)
    groups = [list(np.random.default_rng(i).normal(size=20)) for i in range(3)]
    chi_sq.multi_pop_var_test(groups, list('ABC'))
    assert spies['mean'].call_count == 12  # 3 original + 3*3 transformed.
    assert spies['variance'].call_count == spies['median'].call_count == 3


@pytest.mark.parametrize('x,y', [
    ([1., 2., 3., 4., 5.], [5., 2., 4., 1., 3.]),
    ([1., 1., 2., 2., 3., 3.], [1., 2., 1., 2., 3., 3.]),
    ([1.] * 6, [1., 2., 3., 4., 5., 6.]),
    ([1.] * 6, [2.] * 6),
    ([1., 2., np.nan, 4., 5.], [5., 4., 3., 2., 1.]),
    ([1., 2., np.inf, 4., 5.], [5., 4., 3., 2., 1.]),
    ([1., 2., 3., 4.], [4., 3., 2., 1.]),
])
def test_f02_scalar_ties_constants_small_and_nonfinite(old, x, y):
    import nonpara_cor
    same_call(nonpara_cor.hoeffding, old.nonpara_cor.hoeffding, x, y, print_out=True)
    equal(nonpara_cor.hoeffd_example(x, y), old.nonpara_cor.hoeffd_example(x, y))


@pytest.mark.parametrize('method', ['spearman', 'kendall', 'hoeffding'])
def test_f02_matrix_values_reports_and_unordered_pairs(old, monkeypatch, method):
    import fit_dialog
    import nonpara_cor
    data = [[1., 1., 2., 2., 3., 4.], [1., 4., 2., 5., 3., 2.], [3.] * 6]
    before, after = [], []
    func = getattr(nonpara_cor, method)
    old.fit_dialog.print_multi_col_tables(data, ['甲', '乙', '丙'], func,
        print_port=before.append, name=method)
    spy = Mock(wraps=func)
    fit_dialog.print_multi_col_tables(data, ['甲', '乙', '丙'], spy,
        print_port=after.append, name=method)
    assert spy.call_count == 6  # Includes real diagonal evaluations for constant inputs.
    assert list(map(str, after)) == list(map(str, before))
    for a, b in zip(after, before):
        if hasattr(a, 'values'):
            equal(a.values, b.values)


def test_f02_no_python_boolean_sum_or_repeated_comparison():
    import nonpara_cor
    tree = ast.parse(inspect.getsource(nonpara_cor.hoeffd_example))
    loop = next(n for n in ast.walk(tree) if isinstance(n, ast.For))
    assert not any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                   and n.func.id == 'sum' for n in ast.walk(loop))
    assert len([n for n in ast.walk(loop) if isinstance(n, ast.Compare)]) == 4


@pytest.mark.parametrize('n,p,x', [(12, .3, 0), (12, .3, 12), (15, .4, 4),
                                  (17, .7, 14), (20, .5, 9), (20, .5, 11)])
def test_f04_binomial_legacy(old, n, p, x):
    from binomial import binomial
    same_call(binomial, old.binomial.binomial, n, p, x=x, print_out=True)


@pytest.mark.parametrize('n,p,x', [(1000, .5, 500), (10, 0., 0), (10, 1., 10),
                                  (0, .5, 0), (20, .3, 0), (20, .3, 20)])
def test_f04_binomial_center_and_boundaries(old, n, p, x):
    from binomial import binomial
    if n == 1000:
        with pytest.raises(NameError):
            old.binomial.binomial(n, p, x=x)
    result = binomial(n, p, x=x)
    assert result['px'] == pytest.approx(stats.binom.pmf(x, n, p))
    assert result['left_acc_p'] == pytest.approx(stats.binom.cdf(x, n, p))
    assert result['right_acc_p'] == pytest.approx(stats.binom.sf(x - 1, n, p))
    tail = result['equal_tail']
    for side in ('left', 'right'):
        boundary = tail['x_' + side]
        expected = stats.binom.cdf(boundary, n, p) if side == 'left' else stats.binom.sf(boundary - 1, n, p)
        assert tail['acc_p_' + side] == pytest.approx(expected, abs=1e-14)


@pytest.mark.parametrize('pvalue', [0., .001, .05, .5, 1.])
def test_f04_binomial_probability_mode(old, pvalue):
    from binomial import binomial
    if pvalue < 1:
        same_call(binomial, old.binomial.binomial, 20, .3, pvalue=pvalue, print_out=True)
    else:
        result = binomial(20, .3, pvalue=pvalue)
        assert result['x_left'] == 20 and result['x_right'] == 0


@pytest.mark.parametrize('n,p,k', [(5, .5, 2), (7, .3, 0), (7, .3, 7),
                                  (20, .4, 9), (20, .4, 0), (20, .4, 20)])
def test_f04_proportion_functions(old, n, p, k):
    import proportion_test as prop
    # G20 tests LR independently: the historical LR ordering is statistically wrong.
    for name in ('p_blaker', 'p_sterne'):
        equal(getattr(prop, name)(n, p, k), getattr(old.proportion_test, name)(n, p, k))
    same_call(prop.prop_test_1sample, old.proportion_test.prop_test_1sample,
              k, n, p, print_out=True)


def test_f04_one_support_evaluation_for_entire_single_proportion(monkeypatch):
    import binomial
    import proportion_test
    rv = stats.binom(100, .4)
    rv.pmf = Mock(wraps=rv.pmf)
    monkeypatch.setattr(binomial, 'binom', lambda *a: rv)
    monkeypatch.setattr(proportion_test, 'binom', lambda *a: rv)
    proportion_test.prop_test_1sample(39, 100, .4)
    assert rv.pmf.call_count == 1
    np.testing.assert_array_equal(rv.pmf.call_args.args[0], np.arange(101))


def test_f04_individual_pmf_call_counts(monkeypatch):
    import proportion_test as prop
    rv = stats.binom(20, .4)
    rv.pmf = Mock(wraps=rv.pmf)
    monkeypatch.setattr(prop, 'binom', lambda *a: rv)
    for name in ('p_blaker', 'p_sterne', 'p_likelihood_ratio'):
        rv.pmf.reset_mock()
        getattr(prop, name)(20, .4, 7)
        assert rv.pmf.call_count == 1


def test_f04_empty_tail_guards_remain():
    import proportion_test as prop
    tree = ast.parse(inspect.getsource(prop._p_blaker))
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
             and isinstance(node.func, ast.Name) and node.func.id in ('min', 'max')]
    assert len(calls) == 2
    assert all(any(kw.arg == 'default' for kw in node.keywords) for node in calls)


@pytest.mark.parametrize('p', [1e-8, .03, .5, .99, 1 - 1e-8])
def test_f04_sterne_and_blaker_extreme_tails(old, p):
    import proportion_test as prop
    for k in (0, 1, 99, 100):
        equal(prop.p_sterne(100, p, k), old.proportion_test.p_sterne(100, p, k))
        equal(prop.p_blaker(100, p, k), old.proportion_test.p_blaker(100, p, k))


@pytest.mark.parametrize('rv,k,data', [
    (stats.norm(1, 2), 2, [-3., 1., 2., 5.]),
    (stats.gamma(2, scale=3), 2, [1., 2., 4., 8., 12.]),
    (stats.expon(scale=2), 1, [0., 1., 2., 3.]),
    (stats.norm(), 2, []), (stats.norm(), 2, [0., 1., 2.]),
    (stats.norm(), 2, [np.nan]),
])
def test_f06_abl_numeric_small_empty_and_nan(old, rv, k, data):
    import dist_fit
    equal(dist_fit.ABL(rv, data, k), old.dist_fit.ABL(rv, data, k))


@pytest.mark.parametrize('rv,data', [(stats.norm(), [1e3]),
                                    (stats.expon(), [-1.]), (stats.norm(), [np.inf])])
def test_f06_zero_density_still_raises(old, rv, data):
    import dist_fit
    with pytest.raises(ValueError):
        old.dist_fit.ABL(rv, data, 2)
    with pytest.raises(ValueError):
        dist_fit.ABL(rv, data, 2)


def test_f06_pdf_dispatch_count():
    from dist_fit import ABL
    rv = stats.norm()
    rv.pdf = Mock(wraps=rv.pdf)
    rv.logpdf = Mock(side_effect=AssertionError('Must retain ln(pdf) underflow contract'))
    ABL(rv, list(range(20)), 2)
    assert rv.pdf.call_count == 1
    assert not rv.logpdf.called


@pytest.mark.parametrize('data', [[1., 2., 3., 5., 8., 13.], [1., 2., 3.],
                                 [-2., -1., 0., 1., 2.], [0.] * 6])
def test_f06_all_fits_and_model_selection(old, data):
    import dist_fit
    before, after = [], []
    expected = old.dist_fit.compare_dist(data, print_port=before.append)
    actual = dist_fit.compare_dist(data, print_port=after.append)
    assert [r[0] for r in actual] == [r[0] for r in expected]
    for a, b in zip(actual, expected):
        equal(a[1], b[1])
        equal(a[2]['fits'], b[2]['fits'])
        equal(a[3], b[3])
    assert list(map(str, after)) == list(map(str, before))


@pytest.mark.parametrize('interaction', [True, False])
@pytest.mark.parametrize('data', [
    [[[1., 2., 4.], [3., 4., 8.]], [[2., 4., 5.], [5., 8., 9.]]],
    [[[1., 2.], [3., 4.]], [[2., 4.], [5., 8., 10.]]],
    [[[1., 2., 3.], []], [[2., 4.], [5., 8.]]],
    np.array([[[1., 2.], [3., 4.]], [[2., 4.], [5., 8.]]]),
])
def test_f08_two_way_balanced_and_unbalanced(old, data, interaction):
    from two_way_anova import two_way_anova
    same_call(two_way_anova, old.two_way_anova.two_way_anova,
              data, interaction=interaction, print_out=True)


def test_f08_cell_means_count(monkeypatch):
    import two_way_anova as two
    mean = Mock(wraps=stat.mean)
    monkeypatch.setattr(two.stat, 'mean', mean)
    data = [[[float(i + j + k % 3) for k in range(20)] for j in range(2)] for i in range(3)]
    two.two_way_anova(data)
    assert mean.call_count == 7  # Overall and each of six cells once.


@pytest.mark.parametrize('mode', ['AIAG', 'EMP'])
@pytest.mark.parametrize('inter', ['Auto', 'On', 'Off'])
@pytest.mark.parametrize('unbalanced', [False, True])
def test_f08_grr_all_decisions_reports_and_variance_clamps(old, mode, inter, unbalanced):
    import GRR
    part = [p for p in 'ABC' for op in 'XY' for _ in range(3)]
    ops = [op for p in 'ABC' for op in 'XY' for _ in range(3)]
    y = np.random.default_rng(81).normal(size=len(part)).tolist()
    if unbalanced:
        y, part, ops = y[:-1], part[:-1], ops[:-1]
    same_call(GRR.grr_master, old.GRR.grr_master, y=y, part=part, op=ops,
              mode=mode, inter=inter, print_out=True)


@pytest.mark.parametrize('mode', ['AIAG', 'EMP'])
@pytest.mark.parametrize('inter', ['Auto', 'On', 'Off'])
def test_f08_grr_full_model_never_refitted(monkeypatch, mode, inter):
    import GRR
    spy = Mock(wraps=GRR.two_way_anova)
    monkeypatch.setattr(GRR, 'two_way_anova', spy)
    part = ['A', 'A', 'B', 'B', 'C', 'C'] * 2
    op = ['X'] * 6 + ['Y'] * 6
    y = [1., 3., 4., 6., 7., 9., 2., 2., 5., 5., 8., 8.]
    GRR.grr_master(y=y, part=part, op=op, mode=mode, inter=inter)
    full = [c for c in spy.call_args_list if c.kwargs.get('interaction', True)]
    simple = [c for c in spy.call_args_list if not c.kwargs.get('interaction', True)]
    assert len(full) == 1
    assert len(simple) <= 1


@pytest.mark.parametrize('data', [[], [[[]]], [[[1.], [2.]], [[3.], [4.]]]])
def test_f08_degenerate_errors(old, data):
    from two_way_anova import two_way_anova
    with pytest.raises(Exception) as before:
        old.two_way_anova.two_way_anova(data)
    with pytest.raises(type(before.value)):
        two_way_anova(data)


@pytest.mark.parametrize('name', ['grr_inter', 'grr_simple', 'grr_anova_AIAG', 'grr_anova_EMP'])
def test_f08_direct_entrypoints(old, name):
    import GRR
    part = ['A', 'A', 'B', 'B', 'C', 'C'] * 2
    op = ['X'] * 6 + ['Y'] * 6
    y = [1., 3., 4., 6., 7., 9., 2., 2., 5., 5., 8., 8.]
    equal(getattr(GRR, name)(y, op, part), getattr(old.GRR, name)(y, op, part))


@pytest.mark.parametrize('mode', ['AIAG', 'EMP'])
def test_f08_no_operator(old, mode):
    import GRR
    same_call(GRR.grr_master, old.GRR.grr_master,
              y=[1., 3., 4., 6., 7., 9.], part=['A', 'A', 'B', 'B', 'C', 'C'],
              mode=mode, print_out=True)


@pytest.mark.parametrize('mode', ['AIAG', 'EMP'])
def test_f08_retained_interaction_and_exact_threshold(old, mode):
    import GRR
    part = ['A', 'A', 'B', 'B', 'C', 'C'] * 2
    op = ['X'] * 6 + ['Y'] * 6
    strong = [1., 1.2, 10., 10.2, 20., 20.2, 20., 20.2, 10., 10.2, 1., 1.2]
    result = GRR.grr_master(y=strong, part=part, op=op, mode=mode)
    assert result['INT'] > 0
    same_call(GRR.grr_master, old.GRR.grr_master, y=strong, part=part, op=op,
              mode=mode, print_out=True)
    y = np.random.default_rng(81).normal(size=12).tolist()
    p_ab = GRR.two_way_anova(y, factor_listA=part, factor_listB=op)['p AB']
    assert 0 < p_ab < 1
    for alpha in (np.nextafter(p_ab, 0), p_ab, np.nextafter(p_ab, 1)):
        same_call(GRR.grr_master, old.GRR.grr_master, y=y, part=part, op=op,
                  mode=mode, alpha=alpha, print_out=True)


def test_f01_mismatched_lengths(old):
    from linear_fit import linear_fit
    assert linear_fit([1., 2., 3.], [1., 2.], print_out=False) is None
    assert old.linear_fit.linear_fit([1., 2., 3.], [1., 2.], print_out=False) is None


def test_benchmark_case_matrix_and_self_check():
    from tools.benchmark_statistics import cases, measure
    for hotspot in ('F01', 'F11', 'F02', 'F04', 'F06', 'F08'):
        matrix = cases(hotspot)
        assert matrix and len(set(matrix)) == len(matrix)
        assert all(n > 0 and p > 0 for _, n, p in matrix)
    assert len(measure(lambda: sum(range(10)))) == 3
