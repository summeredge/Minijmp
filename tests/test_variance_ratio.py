import numpy as np
import pytest
from scipy.special import betainc
from scipy.stats import f, levene

from chi_sq import two_pop_var_test, variance_ratio_test


X = [1, 2, 4, 3, 5, 7, 2, 6, 8, 4, 7, 9]
Y = [2, 3, 5, 5, 7, 9, 3, 7, 10, 5, 9, 11]


@pytest.mark.parametrize("alternative", ["less", "greater", "two-sided"])
def test_classical_f_references(alternative):
    res = variance_ratio_test(summary=[(7, 15), (10, 5)], target=2,
                              alternative=alternative)
    p = betainc(3, 4.5, 6*1.5/(6*1.5+9))
    assert res["estimate"] == pytest.approx(3)
    assert res["statistic"] == pytest.approx(1.5)
    assert res["pvalue"] == pytest.approx(dict(less=p, greater=1-p, **{"two-sided": 2*min(p, 1-p)})[alternative])
    lo, hi = res["interval"]
    tail = .025 if alternative == "two-sided" else .05
    if lo:
        assert f.sf(3/lo, 6, 9) == pytest.approx(tail)
    if np.isfinite(hi):
        assert f.cdf(3/hi, 6, 9) == pytest.approx(tail)


@pytest.mark.parametrize("method", ["F", "Bonett", "Levene"])
def test_scale_and_nonunit_null(method):
    variance = variance_ratio_test([X, Y], method=method, target=.64)
    std = variance_ratio_test([X, Y], method=method, scale="std", target=.8)
    assert variance["pvalue"] == pytest.approx(std["pvalue"])
    assert variance["estimate"] == pytest.approx(std["estimate"]**2)
    assert variance["interval"] == pytest.approx(tuple(v*v for v in std["interval"]))


def test_native_fixed_case_and_legacy_labels():
    bonett = variance_ratio_test([X, Y], method="Bonett")
    levene_result = variance_ratio_test([X, Y], method="Levene")
    assert bonett["estimate"] == pytest.approx(.762069, abs=1e-6)
    assert bonett["pvalue"] == pytest.approx(.536, abs=.001)
    assert bonett["interval"] == pytest.approx((.281, 2.042), abs=.003)
    assert levene_result["pvalue"] == pytest.approx(levene(X, Y, center="median").pvalue)
    assert levene_result["interval"] == pytest.approx((.259, 2.135), abs=.0005)
    old = two_pop_var_test(X, Y, print_out=False)
    assert old["F"]["p"] == pytest.approx(variance_ratio_test([X, Y])["pvalue"])
    assert old["Brown_Forsythe"]["p"] == pytest.approx(levene_result["pvalue"])


def test_levene_scaled_null_and_bonett_interval_inversion():
    ratio = 1.45
    res = variance_ratio_test([X, Y], method="Levene", target=ratio, scale="std")
    assert res["pvalue"] == pytest.approx(levene(X, np.array(Y)*ratio, center="median").pvalue)
    for method in ("Bonett", "Levene"):
        two = variance_ratio_test([X, Y], method=method)
        for side, bound in zip(("greater", "less"), two["interval"]):
            one = variance_ratio_test([X, Y], method=method, target=bound, alternative=side)
            assert one["pvalue"] == pytest.approx(.025)
