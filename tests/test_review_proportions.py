"""REVIEW-004/006/007: independent exact references, not historical golden values."""
from math import comb

import numpy as np
import pandas as pd
import pytest
from scipy import stats

from proportion_test import prop_2sample, prop_test_1sample
from stat_table import StatTable


def exact_fisher(n1, n2, e1, e2):
    # Common denominator C(n1+n2, e1+e2): integer comparisons include exact ties.
    total = e1 + e2
    weights = {x: comb(n1, x) * comb(n2, total - x)
               for x in range(max(0, total - n2), min(n1, total) + 1)}
    selected = [x for x, weight in weights.items() if weight <= weights[e1]]
    return selected, sum(weights[x] for x in selected) / comb(n1 + n2, total)


@pytest.mark.parametrize('n1,n2,e1,e2', [
    (10, 10, 1, 6), (10, 10, 2, 8), (10, 10, 1, 5),
    (10, 10, 3, 8), (10, 10, 2, 7), (9, 13, 2, 8),
    (10, 10, 0, 0), (10, 10, 10, 10), (10, 10, 0, 10),
    (1, 1, 0, 1), (1_000_001, 1_000_000, 0, 1),
])
def test_fisher_integer_enumeration_and_swaps(n1, n2, e1, e2):
    selected, expected = exact_fisher(n1, n2, e1, e2)
    if (n1, n2, e1, e2) == (10, 10, 1, 6):
        assert selected == [0, 1, 6, 7]
        assert expected == pytest.approx(0.057275541795665644)
    for a, b, x, y in [(n1, n2, e1, e2), (n2, n1, e2, e1),
                        (n1, n2, n1 - e1, n2 - e2)]:
        result = prop_2sample(a, b, x, y)
        table = [[x, a - x], [y, b - y]]
        assert result['p Fisher'] == stats.fisher_exact(table).pvalue
        assert result['p Fisher'] == pytest.approx(expected, rel=1e-9, abs=1e-15)
        for alternative, key in [('less', 'p p1<p2 Fisher'),
                                 ('greater', 'p p1>p2 Fisher')]:
            assert result[key] == pytest.approx(stats.fisher_exact(table, alternative).pvalue)


def test_fisher_tolerance_does_not_admit_unequal_support():
    selected, expected = exact_fisher(1_000_001, 1_000_000, 0, 1)
    assert selected == [0]
    # A blanket relative tolerance of 1e-5 would admit x=1 and incorrectly give 1.
    assert 1_000_001 <= 1_000_000 * (1 + 1e-5)
    actual = prop_2sample(1_000_001, 1_000_000, 0, 1)['p Fisher']
    assert actual == pytest.approx(expected, rel=1e-9)
    assert actual < .500001


@pytest.mark.parametrize('events', [0, 1, 5, 9, 10])
@pytest.mark.parametrize('alpha', [.05, .1])
def test_clopper_pearson_two_and_one_sided(events, alpha):
    result = prop_test_1sample(events, 10, .5, alpha=alpha)['CI exact']
    for alternative, low_key, high_key in [
        ('two-sided', 'CI l', 'CI u'),
        ('greater', 'CI low', None), ('less', None, 'CI high')]:
        ci = stats.binomtest(events, 10, alternative=alternative).proportion_ci(
            confidence_level=1 - alpha, method='exact')
        if low_key:
            assert result[low_key] == pytest.approx(ci.low, abs=1e-12)
        if high_key:
            assert result[high_key] == pytest.approx(ci.high, abs=1e-12)
    if events == 0:
        assert result['CI l'] == result['CI low'] == 0
        assert result['CI u'] == pytest.approx(1 - (alpha / 2)**.1)
        assert result['CI high'] == pytest.approx(1 - alpha**.1)
    if events == 10:
        assert result['CI u'] == result['CI high'] == 1
        assert result['CI l'] == pytest.approx((alpha / 2)**.1)
        assert result['CI low'] == pytest.approx(alpha**.1)


@pytest.mark.parametrize('e1,e2', [(0, 0), (10, 10), (0, 10), (10, 0)])
def test_zero_standard_error_reports_na_and_keeps_fisher(e1, e2):
    lines = []
    result = prop_2sample(10, 10, e1, e2, print_out=True, print_port=lines.append)
    assert np.isnan(result['p sep'])
    assert np.isnan(result['p Pooled']) == (e1 == e2)
    assert result['p Fisher'] == pytest.approx(exact_fisher(10, 10, e1, e2)[1])
    text = '\n'.join(map(str, lines))
    assert 'NA' in text and '标准误为 0' in text and 'Fisher 精确' in text
    table = next(line for line in lines if isinstance(line, StatTable)
                 and line.title == '检验结果')
    assert table.display[1][1:] == ['NA'] * 4
    if e1 == e2:
        assert table.display[2][1:] == ['NA'] * 4
    else:
        assert all(value != 'NA' for value in table.display[2][1:])


@pytest.mark.parametrize('n1,n2,e1,e2', [(0, 10, 0, 1), (10, 0, 1, 0),
                                        (10, 10, 11, 1), (10, 10, 1, -1)])
def test_two_sample_rejects_invalid_counts(n1, n2, e1, e2):
    with pytest.raises(ValueError, match='样本量'):
        prop_2sample(n1, n2, e1, e2)


@pytest.mark.parametrize('kwargs', [dict(n1=10.5, n2=10, e1=1, e2=2),
                                    dict(n1=10, n2=10.0, e1=1.9, e2=2),
                                    dict(n1=10, n2=10, e1=1, e2=2.5),
                                    dict(n1=10.5, n2=10, e1=1.0, e2=2.0)])
def test_two_sample_rejects_non_integer_counts(kwargs):
    with pytest.raises(ValueError, match='样本量'):
        prop_2sample(**kwargs)


def test_two_sample_accepts_integer_valued_floats():
    assert prop_2sample(10.0, 10, 3.0, 5) == prop_2sample(10, 10, 3, 5)


@pytest.mark.parametrize('events,N,p0', [(0, 0, .5), (5, 0, .5), (11, 10, .5),
                                         (-1, 10, .5), (5, 10, 0), (5, 10, 1)])
def test_one_sample_rejects_undefined_inputs(events, N, p0):
    with pytest.raises(ValueError):
        prop_test_1sample(events, N, p0)


@pytest.mark.parametrize('events,N', [(5, 10.5), (1.9, 10), (5.5, 10.0)])
def test_one_sample_rejects_non_integer_counts(events, N):
    with pytest.raises(ValueError, match='样本量'):
        prop_test_1sample(events, N, .4)


def test_one_sample_accepts_integer_valued_floats():
    assert prop_test_1sample(3.0, 20.0, .4) == prop_test_1sample(3, 20, .4)


def test_one_sample_defaults_do_not_divide_by_zero():
    result = prop_test_1sample()
    assert np.isfinite(result['p norm'])


def dialog(**fields):
    from types import SimpleNamespace
    from unittest.mock import Mock
    values = dict(xvar='', yvar='', event_name='1', event_name2='1', alpha=.05,
                  event_cnt='', ttl_cnt='', event_cnt2='', ttl_cnt2='')
    values.update(fields)
    lines = []
    return SimpleNamespace(**{k: SimpleNamespace(get=lambda v=v: v) for k, v in values.items()},
        df=pd.DataFrame({'X': [1] * 3 + [0] * 7, 'Y': [1] * 5 + [0] * 5}),
        app=SimpleNamespace(print=lines.append), error=Mock(), lines=lines)


@pytest.mark.parametrize('xvar,yvar', [('X', ''), ('', 'Y')])
def test_two_sample_dialog_skips_missing_group_without_key_error(xvar, yvar):
    from sample_test_dialog import Prop2SDialog
    d = dialog(xvar=xvar, yvar=yvar)
    Prop2SDialog.apply(d)
    d.error.assert_not_called()
    assert not d.lines


def test_two_sample_dialog_reads_each_column_independently():
    from sample_test_dialog import Prop2SDialog
    d = dialog(xvar='X', yvar='Y')
    Prop2SDialog.apply(d)
    d.error.assert_not_called()
    table = next(line for line in d.lines if isinstance(line, StatTable) and line.title == '样本统计')
    assert [row[1:3] for row in table.display] == [['10', '3'], ['10', '5']]


def test_two_sample_dialog_rejects_zero_denominator():
    from sample_test_dialog import Prop2SDialog
    d = dialog(event_cnt='0', ttl_cnt='0', event_cnt2='1', ttl_cnt2='10')
    Prop2SDialog.apply(d)
    d.error.assert_called_once()
    assert '试验次数' in d.error.call_args.args[0]
    assert not d.lines


@pytest.mark.parametrize('fields', [
    dict(event_cnt='3', ttl_cnt='10.5', event_cnt2='1', ttl_cnt2='10'),
    dict(event_cnt='1.9', ttl_cnt='10', event_cnt2='1', ttl_cnt2='10'),
    dict(event_cnt='3', ttl_cnt='10', event_cnt2='1', ttl_cnt2='10.5')])
def test_two_sample_dialog_rejects_fractional_counts(fields):
    from sample_test_dialog import Prop2SDialog
    d = dialog(**fields)
    Prop2SDialog.apply(d)
    d.error.assert_called_once()
    assert '试验次数' in d.error.call_args.args[0]
    assert not d.lines


@pytest.mark.parametrize('p0', ['0', '1', '1.5'])
def test_one_sample_dialog_rejects_boundary_p0(p0):
    from sample_test_dialog import Prop1SDialog
    d = dialog(p0=p0, event_cnt='5', ttl_cnt='10')
    Prop1SDialog.apply(d)
    d.error.assert_called_once()
    assert 'p0' in d.error.call_args.args[0]
    assert not d.lines


@pytest.mark.parametrize('fields', [dict(event_cnt='3', ttl_cnt='10.5'),
                                    dict(event_cnt='1.9', ttl_cnt='10')])
def test_one_sample_dialog_rejects_fractional_counts(fields):
    from sample_test_dialog import Prop1SDialog
    d = dialog(p0='.4', **fields)
    Prop1SDialog.apply(d)
    d.error.assert_called_once()
    assert '试验次数' in d.error.call_args.args[0]
    assert not d.lines


def test_dialogs_accept_integer_form_float_counts():
    from sample_test_dialog import Prop1SDialog, Prop2SDialog
    one = dialog(p0='.4', event_cnt='3.0', ttl_cnt='10.0')
    Prop1SDialog.apply(one)
    one.error.assert_not_called()
    assert any(isinstance(line, StatTable) for line in one.lines)

    two = dialog(event_cnt='3.0', ttl_cnt='10.0', event_cnt2='5', ttl_cnt2='10.0')
    Prop2SDialog.apply(two)
    two.error.assert_not_called()
    table = next(line for line in two.lines
                 if isinstance(line, StatTable) and line.title == '样本统计')
    assert [row[1:3] for row in table.display] == [['10', '3'], ['10', '5']]
