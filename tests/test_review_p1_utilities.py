"""REVIEW-005/012：稳定相关及正态子组标准差的独立参考。"""
import numpy as np
import pytest
from scipy import stats
from matplotlib.figure import Figure

from utilities import pearson_correlation, c4_values
from cpk import cpk
from linear_plot import fit_plot, multi_fit


def test_pearson_translation_and_real_consumers():
    x = np.arange(1., 7.)
    y = np.array([1., 4., 2., 5., 3., 7.])
    expected = stats.pearsonr(x, y)
    results = [pearson_correlation(x + shift, y + shift, print_out=False)
               for shift in (0, 1e8, 1e9)]
    for result in results:
        assert result['r'] == pytest.approx(expected.statistic, abs=1e-14)
        assert result['p'] == pytest.approx(expected.pvalue, abs=1e-14)
        assert result['ellipse']['a'] > 0 and result['ellipse']['b'] > 0
    x, y = x + 1e9, y + 1e9
    lines = []
    plotted = fit_plot(x, y, ellipse=True, print_out=True,
                       print_port=lines.append, ax=Figure().subplots())
    assert plotted['Pearson']['r'] == results[-1]['r']
    fig = Figure()
    matrix = multi_fit([x, y], ['X', 'Y'], fig=fig, ax=fig.subplots())
    assert matrix['pearson'][0][1]['r'] == results[-1]['r']
    assert matrix['pearson'][1][0]['p'] == results[-1]['p']
    assert any(getattr(line, 'title', '') == 'Pearson 相关分析' for line in lines)


@pytest.mark.parametrize('x,y,expected', [
    ([1., 1., 1., 1.], [1., 2., 3., 4.], np.nan),
    ([1e9 + i*1e-6 for i in range(6)], [1., 4., 2., 5., 3., 7.], None),
    ([1., 2., 3., 4.], [-1., -2., -3., -4.], -1.),
])
def test_pearson_degenerate_and_near_constant(x, y, expected):
    result = pearson_correlation(x, y, print_out=False)
    if expected is not None and np.isnan(expected):
        assert all(np.isnan(result[k]) for k in ('r', 'p', 'r_l', 'r_u'))
    else:
        reference = stats.pearsonr(x, y)
        assert result['r'] == pytest.approx(reference.statistic, abs=1e-14)
        assert result['p'] == pytest.approx(reference.pvalue, abs=1e-14)
        if expected == -1:
            assert result['r_l'] == result['r_u'] == -1


@pytest.mark.parametrize('n', [5, 343, 344, 345])
def test_c4_chi_expectation_and_legacy_capability(n):
    # 正态样本 S/sigma 服从 chi(n-1)/sqrt(n-1)，用密度积分独立求期望。
    reference = stats.chi.expect(args=(n-1,)) / np.sqrt(n-1)
    assert c4_values(n) == pytest.approx(reference, rel=5e-13)
    data = list(range(n))
    result = cpk([data], target=n/2, lsl=-1, usl=n+1, print_out=False)
    sigma = np.std(data, ddof=1) / reference
    assert result['Within Sigma'] == pytest.approx(sigma, rel=5e-13)
    assert result['Within']['cp'] == pytest.approx((n+2)/(6*sigma), rel=5e-13)
    if n == 344:
        assert sigma == pytest.approx(99.5209897571, abs=1e-9)
        assert result['Within']['cp'] == pytest.approx(.579442254417, abs=1e-12)


@pytest.mark.parametrize('n', [1, 0, -1, np.inf, np.nan])
def test_c4_rejects_invalid_n(n):
    with pytest.raises(ValueError):
        c4_values(n)
