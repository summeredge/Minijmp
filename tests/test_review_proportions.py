"""REVIEW-004/006/007: independent exact references, not historical golden values."""
from math import comb

import numpy as np
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
