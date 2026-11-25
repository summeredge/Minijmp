import numpy as np
import pytest
from scipy.stats import t
from statsmodels.stats.weightstats import ttost_ind, ttost_paired

from t_test import equivalence_tost


def test_single_sample_target_and_boundary():
    x = np.array([8., 9., 10., 11., 12.])
    se = np.std(x, ddof=1) / np.sqrt(len(x))
    radius = t.isf(.05, 4) * se
    result = equivalence_tost(x, target=10, lower=-2, upper=3)
    assert result["equivalent"]
    assert result["interval"] == pytest.approx((-radius, radius))
    assert result["p_lower"] == pytest.approx(t.sf(2/se, 4))
    assert not equivalence_tost(x, target=10, lower=-radius+.001, upper=3)["equivalent"]
    assert equivalence_tost(x, target=10, lower=-radius-.001, upper=3)["equivalent"]
    assert equivalence_tost(x, target=20, lower=-2, upper=3)["interval"][1] < -2


@pytest.mark.parametrize("pooled", [False, True])
def test_independent_tost_against_statsmodels(pooled):
    x = [1, 3, 5, 6, 7]
    y = [3, 3, 4, 5, 6, 8, 10]
    result = equivalence_tost(x, y, lower=-2, upper=3, pooled=pooled)
    expected = ttost_ind(y, x, -2, 3, usevar="pooled" if pooled else "unequal")
    assert (result["t_lower"], result["p_lower"], result["df"]) == pytest.approx(expected[1])
    assert (result["t_upper"], result["p_upper"], result["df"]) == pytest.approx(expected[2])
    assert not result["equivalent"]


def test_paired_tost_removes_incomplete_pairs_without_realigning():
    x = np.array([1., np.nan, 5., 6., 7., 9.])
    y = np.array([1.2, 3., np.nan, 7.2, 7.3, 9.2])
    valid = np.isfinite(x) & np.isfinite(y)
    result = equivalence_tost(x, y, lower=-1, upper=2, paired=True)
    expected = ttost_paired(y[valid], x[valid], -1, 2)
    assert result["n"] == (4,)
    assert result["p_lower"] == pytest.approx(expected[1][1])
    assert result["p_upper"] == pytest.approx(expected[2][1])
    assert result["equivalent"]
