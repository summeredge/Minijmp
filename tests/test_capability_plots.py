"""Independent analytic control-limit and rendered-artifact checks."""
import numpy as np
import pytest
from PIL import Image
from scipy import stats
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg

from capability_plots import control_diagnostics, plot_capability


def result(groups=None, model=None):
    if groups is None:
        groups = [[9.], [10.], [11.], [10.], [25.]]
    data = np.concatenate(groups)
    return dict(data=data, groups=groups, mean=10., within_sigma=2.,
                overall_sigma=3., lsl=None, usl=18., target=None,
                model=model or stats.norm(10, 3), indices={"Cp": None, "Cpk": 1.3},
                ppm={}, fit={}, warnings=[], transform=None)


def line(ax, label):
    return next(item for item in ax.lines if item.get_label() == label)


@pytest.mark.parametrize("n", [1, 4, 9])
def test_sixpack_order_and_png(n, tmp_path):
    groups = [np.arange(n) + 7. + i / 3 for i in range(6)]
    res = result(groups)
    before = res["data"].copy()
    fig = Figure(figsize=(12, 10), layout="constrained")
    FigureCanvasAgg(fig)
    assert plot_capability(res, fig, recent=3) is fig
    titles = [ax.get_title() for ax in fig.axes]
    assert titles[0].startswith("I " if n == 1 else "Xbar")
    assert titles[1] == "能力直方图"
    assert titles[2].startswith({1: "MR ", 4: "R ", 9: "S "}[n])
    assert titles[3] == "概率图（Q-Q）"
    assert titles[4] == "最近 3 个子组"
    assert titles[5].startswith("能力比较")
    assert [item.get_xdata()[0] for item in fig.axes[4].lines if item.get_label() != '整体均值'] == [4, 5, 6]
    np.testing.assert_allclose(line(fig.axes[4], '整体均值').get_ydata(), res['mean'])
    assert not any(item.get_label() == "LSL" for item in fig.axes[1].lines)
    assert line(fig.axes[1], "USL").get_xdata()[0] == 18.
    fig.canvas.draw()
    path = tmp_path / f"sixpack-{n}.png"
    fig.savefig(path)
    with Image.open(path) as image:
        assert image.size == (1200, 1000)
        image.verify()
    np.testing.assert_array_equal(res["data"], before)


def test_individual_limits_and_red_points():
    fig = plot_capability(result())
    np.testing.assert_allclose(line(fig.axes[0], "LCL").get_ydata(), 4)
    np.testing.assert_allclose(line(fig.axes[0], "UCL").get_ydata(), 16)
    np.testing.assert_allclose(line(fig.axes[0], "超控制限").get_ydata(), [25])
    # n=2 range constants from the SPC table: d2=1.128, d3=.8525.
    np.testing.assert_allclose(line(fig.axes[2], "UCL").get_ydata(),
                               (1.128 + 3 * .8525) * 2)


@pytest.mark.parametrize("model", [stats.lognorm(.8, scale=4),
                                   stats.weibull_min(1.5, scale=5),
                                   stats.gamma(2, scale=3)])
def test_nonnormal_limits_are_model_quantiles(model):
    res = result(model=model)
    fig = plot_capability(res)
    np.testing.assert_allclose(line(fig.axes[0], "LCL").get_ydata(), model.ppf(.00135))
    np.testing.assert_allclose(line(fig.axes[0], "UCL").get_ydata(), model.ppf(.99865))
    assert not any(item.get_label() == "组内正态" for item in fig.axes[1].lines)
    ranks = (np.arange(1, 6) - .3) / 5.4
    np.testing.assert_allclose(fig.axes[3].lines[0].get_xdata(), model.ppf(ranks))


def test_varying_subgroup_limits_and_range():
    res = result([[1., 2.], [3., 4., 5., 6.]])
    fig = plot_capability(res)
    np.testing.assert_allclose(line(fig.axes[0], "UCL").get_ydata(),
                               [10 + 6 / np.sqrt(2), 13])
    np.testing.assert_allclose(line(fig.axes[2], "观测值").get_ydata(), [1, 3])
    np.testing.assert_allclose(line(fig.axes[2], "CL").get_ydata(), [2 * 1.128, 2 * 2.059])


def test_s_chart_independent_chi_distribution_reference():
    sizes = np.array([9, 12])
    fig = plot_capability(result([np.arange(n) for n in sizes]))
    # Sample SD / sigma has chi(n-1) / sqrt(n-1) distribution.
    means = np.array([stats.chi.mean(int(n - 1)) / np.sqrt(n - 1) for n in sizes]) * 2
    sds = np.array([stats.chi.std(int(n - 1)) / np.sqrt(n - 1) for n in sizes]) * 2
    np.testing.assert_allclose(line(fig.axes[2], "CL").get_ydata(), means)
    np.testing.assert_allclose(line(fig.axes[2], "UCL").get_ydata(), means + 3 * sds)
    np.testing.assert_allclose(line(fig.axes[2], "LCL").get_ydata(), np.maximum(0, means - 3 * sds))


def test_transform_diagnostics_and_reused_figure(tmp_path):
    res = result()
    res.update(transform={"method": "boxcox", "lambda": 0}, original=np.exp(res["data"]))
    fig = plot_capability(res, sixpack=False)
    FigureCanvasAgg(fig)
    assert len(fig.axes) == 4
    np.testing.assert_allclose(fig.axes[1].lines[0].get_ydata(), np.sort(res["original"]))
    np.testing.assert_allclose(fig.axes[3].lines[0].get_ydata(), np.sort(res["data"]))
    fig.savefig(tmp_path / "transform.png")
    with Image.open(tmp_path / "transform.png") as image:
        image.verify()
    plot_capability(result(), fig, sixpack=False)
    assert len(fig.axes) == 2


@pytest.mark.parametrize("recent", [0, -1, 1.2, True])
def test_invalid_recent(recent):
    with pytest.raises(ValueError, match="正整数"):
        plot_capability(result(), recent=recent)


@pytest.mark.parametrize("data", [[1., 1.], [1., np.nan], [1.]])
def test_invalid_data(data):
    res = result()
    res["data"] = data
    with pytest.raises(ValueError, match="观测值"):
        plot_capability(res)


def test_capability_k_does_not_change_spc_limits():
    res = result()
    res["k"] = 4
    fig = plot_capability(res)
    np.testing.assert_allclose(line(fig.axes[0], "UCL").get_ydata(), 16)
    np.testing.assert_allclose(line(fig.axes[5], "组内").get_xdata(), [6, 14])


def test_control_diagnostics_matches_limits_without_mutation():
    res = result()
    keys = set(res)
    table = control_diagnostics(res)
    assert set(res) == keys
    individual = table[table.chart == "I 单值图"]
    np.testing.assert_allclose(individual.lcl, 4)
    np.testing.assert_allclose(individual.ucl, 16)
    assert individual.outside.tolist() == [False, False, False, False, True]
    moving = table[table.chart == "MR 移动极差图"]
    assert np.isnan(moving.statistic.iloc[0])
    assert moving.outside.isna().tolist() == [True, False, False, False, False]
    assert individual.subgroup.tolist() == [1, 2, 3, 4, 5]


@pytest.mark.parametrize("size", [1, 4, 9])
def test_nonnormal_diagnostic_method_discloses_approximation(size):
    res = result([np.arange(size) + i + 1. for i in range(5)], stats.gamma(2, scale=3))
    table = control_diagnostics(res)
    if size == 1:
        assert table.method.iloc[0].startswith("拟合分布")
        assert "正态 MR(2)" in table.method.iloc[-1]
    else:
        assert all("正态 3σ 近似" in item for item in table.method)
        assert "正态近似" in plot_capability(res)._suptitle.get_text()


def test_lower_only_spec_and_original_dictionary(tmp_path):
    res = result()
    res.update(lsl=8., usl=None, transform={"method": "boxcox", "lambda": 0},
               original={"data": np.exp(res["data"])})
    fig = plot_capability(res, sixpack=False)
    FigureCanvasAgg(fig)
    assert not any(item.get_label() == "USL" for item in fig.axes[2].lines)
    assert line(fig.axes[2], "LSL").get_xdata()[0] == 8
    fig.savefig(tmp_path / "transform-dictionary.png")
    with Image.open(tmp_path / "transform-dictionary.png") as image:
        image.verify()


def test_nonnormal_comparison_uses_standard_normal_z_scale():
    res = result(model=stats.lognorm(.6, scale=4))
    res.update(lsl=2., usl=8.)
    fig = plot_capability(res)
    ax = fig.axes[5]
    np.testing.assert_allclose(line(ax, '整体（Z 尺度）').get_xdata(), [-3, 3])
    # Lognormal maps to z=(log(x)-log(scale))/shape analytically.
    np.testing.assert_allclose(line(ax, 'LSL（Z）').get_xdata(), np.log(2/4)/.6)
    np.testing.assert_allclose(line(ax, 'USL（Z）').get_xdata(), np.log(8/4)/.6)


def test_johnson_only_displays_overall_capability_curves():
    res = result()
    res.update(transform={'method': 'johnson'}, original=res['data'].copy())
    fig = plot_capability(res)
    assert not any(item.get_label() == '组内正态' for item in fig.axes[1].lines)
    assert not any(item.get_label() == '组内' for item in fig.axes[5].lines)
