"""Independent high-precision likelihood and probability enumeration for G20."""
from decimal import Decimal, localcontext
from math import comb

import numpy as np
import pytest

from proportion_test import p_likelihood_ratio


def reference(n, p0, x):
    # No SciPy PMF, logs, KL, or production helpers in this oracle.
    with localcontext() as ctx:
        ctx.prec = 100
        p = Decimal.from_float(float(p0))

        def likelihood(y, p):
            return (p ** y if y else Decimal(1)) * (
                (1 - p) ** (n - y) if n != y else Decimal(1))

        def ratio(y):
            return likelihood(y, p) / likelihood(y, Decimal(y) / n) if n else Decimal(1)

        observed = ratio(x)
        # A float such as .8 slightly splits exact ties; include roundoff ties.
        selected = [y for y in range(n + 1)
                    if ratio(y) <= observed * (1 + Decimal('1e-13'))]
        return float(sum(Decimal(comb(n, y)) * likelihood(y, p) for y in selected)), selected


@pytest.mark.parametrize('n', [0, 1, 2, 3, 7, 10, 25, 60])
@pytest.mark.parametrize('p0', [0., 1e-8, .1, .3, .5, .8, 1 - 1e-8, 1.])
def test_all_support_points_against_independent_reference(n, p0):
    for x in range(n + 1):
        expected, _ = reference(n, p0, x)
        actual = p_likelihood_ratio(n, p0, x)
        assert isinstance(actual, float)
        assert np.isfinite(actual) and 0 <= actual <= 1
        assert actual == pytest.approx(expected, rel=3e-12, abs=0)


def test_g19_b01_rejects_old_central_ordering():
    expected, selected = reference(10, .5, 8)
    assert selected == [0, 1, 2, 8, 9, 10]
    assert expected == .109375
    assert p_likelihood_ratio(10, .5, 8) == pytest.approx(expected)
    assert p_likelihood_ratio(10, .5, 8) != pytest.approx(.978515625)


@pytest.mark.parametrize('n,p0,x', [
    (1000, .5, 0), (1000, .5, 1000), (1000, .001, 100),
    (2000, .5, 0), (100, 1e-12, 20), (100, 1 - 1e-12, 80),
    (100, np.nextafter(0., 1.), 0), (100, np.nextafter(1., 0.), 100),
])
def test_extreme_tails(n, p0, x):
    expected, _ = reference(n, p0, x)
    actual = p_likelihood_ratio(n, p0, x)
    assert np.isfinite(actual) and 0 <= actual <= 1
    assert actual == pytest.approx(expected, rel=5e-11, abs=0)


@pytest.mark.parametrize('n,x', [(10, 8), (31, 27), (100, 90), (1000, 600)])
def test_floating_symmetric_ties(n, x):
    expected, selected = reference(n, .5, x)
    assert n - x in selected and x in selected
    assert p_likelihood_ratio(n, .5, x) == pytest.approx(expected, rel=3e-12, abs=0)
    assert p_likelihood_ratio(n, .5, n - x) == pytest.approx(expected, rel=3e-12, abs=0)


@pytest.mark.parametrize('p0', [.5 - 1e-10, .5 + 1e-10])
def test_near_ties_are_not_mathematical_ties(p0):
    expected, selected = reference(10, p0, 8)
    assert (2 in selected) == (p0 > .5)
    assert p_likelihood_ratio(10, p0, 8) == pytest.approx(expected, rel=3e-12, abs=0)


@pytest.mark.parametrize('args', [(-1, .5, 0), (3.5, .5, 1), (3, .5, -1),
                                  (3, .5, 4), (3, .5, 1.5), (3, -.1, 1),
                                  (3, 1.1, 1), (3, float('nan'), 1)])
def test_invalid_domain(args):
    with pytest.raises(ValueError):
        p_likelihood_ratio(*args)
