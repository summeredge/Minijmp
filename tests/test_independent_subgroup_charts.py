from math import gamma, pi, sqrt

from matplotlib.figure import Figure
import numpy as np
import pytest

from control_chart import x_plot
from stat_table import StatTable


def output(data, kind, *, historical=False):
    fig = Figure()
    independent = kind in ("Xbar", "R", "S")
    axes = fig.subplots(1 if independent else 2)
    entries = []
    plot_type = "XBAR_S" if kind in ("S", "Xbar-S") else "XBAR_R"
    x_plot(data, fig=fig, ax=axes if independent else None, axs=None if independent else axes,
           print_out=True, print_port=entries.append, detect_rules=True,
           one_chart=kind == "Xbar", chart_two_only=kind in ("R", "S"), plot_type=plot_type,
           mean=10 if historical else None, sigma=2 if historical else None)
    return fig, [value for value in entries if isinstance(value, StatTable)]


@pytest.mark.parametrize("kind,combined,panel", [
    ("Xbar", "Xbar-R", 0), ("R", "Xbar-R", 1), ("S", "Xbar-S", 1),
])
@pytest.mark.parametrize("historical", [True, False])
def test_independent_panel_equals_combination(kind, combined, panel, historical):
    data = [[2,3,4], [3,6], [30,42,86], [2,4]]
    figure, one = output(data, kind, historical=historical)
    _, two = output(data, combined, historical=historical)
    assert len(figure.axes) == 1
    assert one[0].values == [two[0].values[panel]]
    assert one[1].values == two[1+panel].values
    expected = [row for table in two[3:] for row in table.values if row[0] == kind]
    actual = [row for table in one[2:] for row in table.values]
    assert actual == expected


def test_f3_1_native_inputs_against_fixed_n_formulas():
    groups = [[1,2,3], [4,5,6], [7,8,9], [10,11,12]]
    mean_range = 2
    c4 = sqrt(2 / (3-1))*gamma(3/2)/gamma(1)
    for kind in ("Xbar", "R", "S"):
        _, tables = output(groups, kind)
        actual = np.array([row[2:] for row in tables[1].values])
        if kind == "Xbar":
            sigma = mean_range / (3/sqrt(pi))
            width = 3*sigma/sqrt(3)
            expected = [[3, mean, 6.5-width, 6.5, 6.5+width] for mean in (2,5,8,11)]
        elif kind == "R":
            # Published n=3 range constant D4 is rounded to 2.574.
            expected = [[3, 2, 0, 2, 2.574*mean_range]]*4
        else:
            expected = [[3, 1, 0, 1, 1+3*sqrt(1-c4*c4)/c4]]*4
        np.testing.assert_allclose(actual, expected, atol=.002)


def test_unequal_s_chart_with_historical_sigma_against_gamma_formula():
    groups = [[2, 4], [5, 6, 7], [4, 7, 10, 13]]
    _, tables = output(groups, "S", historical=True)
    for row, group in zip(tables[1].values, groups):
        n = len(group)
        c4 = sqrt(2/(n-1))*gamma(n/2)/gamma((n-1)/2)
        width = 6*sqrt(1-c4*c4)/c4
        assert row[2:] == pytest.approx([n, np.std(group, ddof=1), max(0,2-width), 2, 2+width])
