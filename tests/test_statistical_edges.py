import numpy as np
import pytest
from scipy.stats import chi2_contingency, norm

from chi_sq import chi_square
from cpk import cpk, cpk_calc, cpl_cpu_95
from GRR import grr_master


def test_zero_cpk_and_one_sided_intervals_are_defined():
    result = cpk([-2, -1, 0, 1, 2], target=5, lsl=0, usl=10, print_out=False)
    expected = norm.ppf(.975) / (3 * np.sqrt(5))
    for estimate in [result['Overall'], result['Within']]:
        assert estimate['cpk'] == 0
        assert estimate['cpk_l'] == pytest.approx(-expected)
        assert estimate['cpk_u'] == pytest.approx(expected)
        assert estimate['cpl_l'] == pytest.approx(-expected)
        assert estimate['cpl_u'] == pytest.approx(expected)


@pytest.mark.parametrize('mean', [1, 3, 5, 7, 9])
def test_positive_cpk_interval_matches_previous_formula(mean):
    result = cpk_calc(mean, 1, 5, 10, 0, 19, 20, print_out=False)
    index = result['cpk']
    previous = norm.ppf(.975) * np.sqrt(1 / (9 * 20 * index**2) + 1 / (2 * 19)) * index
    assert result['cpk_l'] == pytest.approx(index - previous)
    assert result['cpk_u'] == pytest.approx(index + previous)


def test_negative_cpk_interval_keeps_lower_and_upper_in_order():
    result = cpk_calc(-1, 1, 5, 10, 0, 19, 20, print_out=False)
    assert result['cpk_l'] < result['cpk'] < result['cpk_u']


@pytest.mark.parametrize('index', [0, 1e-12, -1e-12])
def test_noncentral_interval_near_zero_matches_zero_limit(index):
    expected = norm.ppf(.975) / (3 * np.sqrt(20))
    np.testing.assert_allclose(cpl_cpu_95(index, 20, 19), [-expected, expected], atol=1e-10)


@pytest.mark.parametrize('data', [[[0, 10], [5, 5]], [[2, 10], [5, 7]]])
def test_likelihood_ratio_including_zero_counts_matches_scipy(data):
    result = chi_square(data, print_out=False)
    expected = chi2_contingency(data, correction=False, lambda_='log-likelihood')
    assert result['chi sq LR'] == pytest.approx(expected.statistic)
    assert result['p LR'] == pytest.approx(expected.pvalue)
    pearson = chi2_contingency(data, correction=False)
    assert result['chi sq Pearson'] == pytest.approx(pearson.statistic)


@pytest.mark.parametrize('offset', [0, 2])
def test_grr_reproducibility_has_real_nonnegative_variance(offset):
    y = [1, 2, 3, 4] + [1 + offset, 2 + offset, 3 + offset, 4 + offset]
    result = grr_master(y=y, op=['one']*4 + ['two']*4,
                        part=['A', 'A', 'B', 'B']*2, mode='XBAR/R',
                        print_out=True, print_port=lambda *a: None)
    assert all(np.isreal(v) and np.isfinite(v) and v >= 0 for v in result.values())
    assert result['AV'] == 0 if offset == 0 else result['AV'] > 0


def test_rectangular_contingency_dialog_prints_all_rows():
    import pandas as pd
    from types import SimpleNamespace
    from chi2_dialog import Chi2TableDialog
    output = []
    dialog = SimpleNamespace(df=pd.DataFrame({'x': [10, 20, 30], 'y': [20, 10, 30]}),
        grpcols=['x', 'y'], rvar=SimpleNamespace(get=lambda: ''),
        app=SimpleNamespace(print=lambda *args: output.extend(map(str, args))))
    Chi2TableDialog.apply(dialog)
    text = '\n'.join(output)
    assert 'C' in text
    assert '30 / 30.00' in text
