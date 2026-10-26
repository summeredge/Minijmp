"""G6: chart objects, exact plotting data, CJK, export and the existing Tk viewer."""
from types import SimpleNamespace
from unittest.mock import Mock
import ast
import inspect
import textwrap
import warnings

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
import numpy as np
import pandas as pd
from PIL import Image
import pytest
from scipy import stats

from chart_style import CJK_FONTS, font_families, style_axes
from linear_plot import fit_plot, multi_fit, multi_fit_orig
from Residual import resid_test, linear_fit_resid_test
from sb_histo import histo_n_fit, histo_full, histo_xy
from sb_boxplot import single_boxplot, multi_boxplot
from sb_misc import interval_plot, count_plot, dot_plot, line_plot
from cont_plot import cont_dist
from binomial import binomial
from poisson import poisson
from pandastable_local.plotting import PlotViewer


X = [1, 2, 3, 4, 5, 6]
Y = [2, 4, 3, 8, 6, 10]
LABEL = "生产线温度（摄氏度）"


@pytest.fixture(autouse=True)
def close_figures():
    yield
    plt.close("all")


def test_style_preserves_axes_data_limits_scale_grid_and_selected_font():
    fig, ax = plt.subplots()
    ax.plot(X, Y, color="purple", linestyle="--")
    ax.set(xscale="log", xlim=(.5, 10), ylim=(-2, 12))
    ax.set_xlabel(LABEL, fontfamily="Arial")
    before = [(line.get_visible(), line.get_xdata().copy(), line.get_ydata().copy())
              for line in ax.lines]
    grid = [line.get_visible() for line in ax.get_xgridlines() + ax.get_ygridlines()]
    rc = dict(matplotlib.rcParams)
    style_axes(ax)
    assert ax.get_xlim() == (.5, 10) and ax.get_ylim() == (-2, 12)
    assert ax.get_xscale() == "log"
    assert ax.xaxis.label.get_fontfamily()[0] == "Arial"
    assert ax.lines[0].get_color() == "purple" and ax.lines[0].get_linestyle() == "--"
    assert grid == [line.get_visible() for line in ax.get_xgridlines() + ax.get_ygridlines()]
    for line, (visible, x, y) in zip(ax.lines, before):
        assert line.get_visible() == visible
        np.testing.assert_array_equal(line.get_xdata(), x)
        np.testing.assert_array_equal(line.get_ydata(), y)
    assert dict(matplotlib.rcParams) == rc
    assert font_families(font_families("Arial")) == font_families("Arial")


@pytest.mark.parametrize("entry", [single_boxplot, multi_boxplot, interval_plot, count_plot])
def test_long_category_labels_remain_complete_and_do_not_overlap(entry):
    groups = [f"第{i}条生产线的温度测量结果" for i in range(1, 5)]
    df = pd.DataFrame({"组别": [g for g in groups for _ in range(4)], "值": list(range(16))})
    fig, ax = plt.subplots(figsize=(6.4, 4.8), layout="constrained")
    kwargs = {"data": df, "x": "组别", "ax": ax}
    if entry is not count_plot:
        kwargs["y"] = "值"
    if entry is interval_plot:
        kwargs["seed"] = 0
    entry(**kwargs)
    fig.canvas.draw()
    labels = ax.get_xticklabels()
    assert [label.get_text() for label in labels] == groups
    assert all(label.get_rotation() == 60 for label in labels)
    boxes = [label.get_window_extent(fig.canvas.get_renderer()) for label in labels]
    assert not any(a.overlaps(b) for a, b in zip(boxes, boxes[1:]))
    assert all(box.y0 >= 0 for box in boxes)


def test_regression_intervals_are_distinct_and_match_original_equations():
    fig, ax = plt.subplots(layout="constrained")
    result = fit_plot(X, Y, ax=ax, linear=True, ortho=True, show_CI=True,
                      show_PI=True, show_legend=True, xlabel=LABEL, ylabel="压力 MPa")
    reference = stats.linregress(X, Y)
    fit = result["Linear Regression"]
    assert fit["slope"] == pytest.approx(reference.slope)
    assert fit["intercept"] == pytest.approx(reference.intercept)
    assert set(result) == {"Linear Regression", "Orthogonal Regression"}
    np.testing.assert_array_equal(ax.collections[0].get_offsets(), np.column_stack([X, Y]))
    assert len(ax.lines) == 6
    pi, ci = ax.lines[2], ax.lines[4]
    assert pi.get_linestyle() == "--" and ci.get_linestyle() == ":"
    assert "预测区间 (PI)" in pi.get_label() and "置信区间 (CI)" in ci.get_label()
    n = len(X)
    xx = ci.get_xdata()
    base = fit["slope"] * xx + fit["intercept"]
    term = 1 / n + (xx - np.mean(X)) ** 2 / np.sum((np.array(X) - np.mean(X)) ** 2)
    multiplier = stats.t.ppf(.975, n - 2)
    np.testing.assert_allclose(ci.get_ydata(), base + multiplier * np.sqrt(fit["MSE"] * term))
    np.testing.assert_allclose(pi.get_ydata(), base + multiplier * fit["Root MSE"] * np.sqrt(1 + term))
    assert len(ax.get_legend().get_texts()) == 5


@pytest.mark.parametrize("entry", [multi_fit, multi_fit_orig])
@pytest.mark.parametrize("count", [2, 3, 4])
def test_both_matrix_entries_keep_pair_data_and_full_variable_names(entry, count):
    data = [np.array(Y) + np.array(X) * i for i in range(count)]
    labels = [f"第{i + 1}组测量变量（单位 mm）" for i in range(count)]
    fig = plt.figure(figsize=(9, 8))
    if entry is multi_fit:
        root = fig.add_subplot()
        result = entry(data, labels, ax=root, fig=fig)
        axes = root.child_axes
    else:
        axes = fig.subplots(count - 1, count - 1, squeeze=False)
        result = entry(data, labels, axs=axes, fig=fig)
        axes = axes.ravel()
    active = [ax for ax in axes if ax.axison]
    assert len(active) == count * (count - 1) // 2
    for ax in active:
        assert len(ax.collections) == 1
        offsets = ax.collections[0].get_offsets()
        assert any(np.array_equal(offsets, np.column_stack([data[i], data[j]]))
                   for i in range(count) for j in range(i + 1, count))
        assert not ax.get_xlabel() or ax.get_xlabel() in labels
        assert not ax.get_ylabel() or ax.get_ylabel() in labels
    for i in range(count):
        for j in range(count):
            assert result["pearson"][i][j]["r"] == pytest.approx(stats.pearsonr(data[i], data[j]).statistic)
    fig.canvas.draw()


def test_legacy_two_variable_matrix_without_supplied_axes():
    assert multi_fit_orig([X, Y], ["温度", "压力"])["pearson"][0][1]["r"] == pytest.approx(stats.pearsonr(X, Y).statistic)
    assert len(plt.gcf().axes) == 1


@pytest.mark.parametrize("supplied", [False, True])
def test_residual_titles_quantiles_and_returns(supplied):
    fig = plt.figure(layout="constrained")
    axes = fig.subplots(2, 2) if supplied else None
    result = linear_fit_resid_test(X, Y, axs=axes)
    if not supplied:
        fig = plt.gcf()
    assert len(fig.axes) == 5  # histogram's existing count/density twin is retained
    main = fig.axes[:4]
    assert [ax.get_title() for ax in main] == ["残差与观测顺序", "残差与拟合值", "残差直方图", "正态 Q-Q 图"]
    fit = stats.linregress(X, Y)
    residual = np.array(Y) - (fit.intercept + fit.slope * np.array(X))
    expected = stats.probplot(residual, dist="norm")[0]
    np.testing.assert_allclose(main[3].lines[0].get_xdata(), expected[0])
    np.testing.assert_allclose(main[3].lines[0].get_ydata(), expected[1])
    assert result["shapiro p"] == pytest.approx(stats.shapiro(residual).pvalue)
    fig.canvas.draw()


def draw_basic(name, ax):
    df = pd.DataFrame({"数值": Y, "横轴": X, "组别": ["甲", "甲", "乙", "乙", "丙", "丙"]})
    if name == "histo_n_fit":
        histo_n_fit(df=df, xkey="数值", ax=ax, xlabel=LABEL,
                    rv=stats.norm(np.mean(Y), np.std(Y, ddof=1)), legend=True)
    elif name == "histo_full":
        histo_full(data=df, x="数值", hue="组别", ax=ax, xlabel=LABEL)
    elif name == "histo_xy":
        histo_xy(data=df, x="横轴", y="数值", ax=ax, xlabel=LABEL, ylabel="压力 MPa")
    elif name in ("single_boxplot", "multi_boxplot"):
        kwargs = dict(data=df, x="组别", y="数值", ax=ax, xlabel=LABEL, ylabel="压力 MPa")
        (single_boxplot if name == "single_boxplot" else multi_boxplot)(**kwargs)
    elif name == "interval_plot":
        from utilities import hash_combined
        intervals = {hash_combined(Y[i:i+2]): (min(Y[i:i+2]), max(Y[i:i+2])) for i in (0, 2, 4)}
        interval_plot(data=df, x="组别", y="数值", ax=ax, CIs=intervals, xlabel=LABEL)
    elif name == "count_plot":
        count_plot(data=df, x="组别", ax=ax, xlabel=LABEL)
    else:
        (dot_plot if name == "dot_plot" else line_plot)(data=df, x="横轴", y="数值", ax=ax, xlabel=LABEL)


BASIC_CHARTS = ["histo_n_fit", "histo_full", "histo_xy", "single_boxplot",
                "multi_boxplot", "interval_plot", "count_plot", "dot_plot", "line_plot"]


@pytest.mark.parametrize("name", BASIC_CHARTS)
def test_basic_chart_objects_and_chinese_exports(name, tmp_path):
    fig, ax = plt.subplots(figsize=(8, 6), layout="constrained")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        draw_basic(name, ax)
        assert ax.get_xlabel() == LABEL
        assert ax.lines or ax.collections or ax.patches
        target = tmp_path / f"中文图表-{name}.png"
        fig.savefig(target, dpi=150, bbox_inches="tight")
    assert not [w for w in caught if "Glyph" in str(w.message)]
    with Image.open(target) as image:
        assert image.format == "PNG" and image.width >= 600 and image.height >= 400
    if name == "histo_n_fit":
        assert len(fig.axes) == 2 and len(fig.legends) == 1
        assert [t.get_text() for t in fig.legends[0].get_texts()] == [LABEL, "拟合分布 (norm)"]
        assert fig.axes[1].get_ylabel() == "Density"


@pytest.mark.parametrize("name", ["Normal", "Binomial", "Poisson"])
def test_probability_plot_paths_keep_existing_values_and_semantics(name):
    fig, ax = plt.subplots()
    if name == "Normal":
        result = cont_dist(dist=name, x=-1, plot_out=True, print_out=False, ax=ax,
                           **{"Mean": 0, "Standard deviation": 1})
        assert result["px"] == pytest.approx(stats.norm.pdf(-1))
        np.testing.assert_allclose(ax.lines[0].get_ydata(), stats.norm.pdf(ax.lines[0].get_xdata()))
    else:
        function, args = (binomial, (20, .3)) if name == "Binomial" else (poisson, (5,))
        result = function(*args, x=3, ax=ax)
        reference = stats.binom(20, .3) if name == "Binomial" else stats.poisson(5)
        assert result["px"] == pytest.approx(reference.pmf(3))
        assert ax.patches and ax.get_ylabel() == "Probability"
    style_axes(ax)
    fig.canvas.draw()


@pytest.mark.skipif(not CJK_FONTS, reason="需要已安装的中文字体")
@pytest.mark.parametrize("extension", ["png", "jpg", "tif", "pdf", "eps", "svg"])
def test_existing_viewer_export_formats_keep_names_dpi_and_complete_text(extension, tmp_path):
    fig = Figure(figsize=(8, 6), dpi=100, layout="constrained")
    FigureCanvasAgg(fig)
    ax = fig.subplots()
    ax.plot([-2, -1, 0, 1], [-3, 2, 0, 4], label="中文图例 α β μ −1")
    ax.set(title="中文统计图 $R^2$、σ、χ²", xlabel=LABEL, ylabel="压力 / MPa")
    ax.legend()
    style_axes(ax)
    viewer = SimpleNamespace(fig=fig, globalopts={"dpi": 180}, currentdir=str(tmp_path))
    target = tmp_path / f"统计图.{extension}"
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        PlotViewer.savePlot(viewer, str(target))
    assert target.stat().st_size > 1000
    assert not [w for w in caught if "Glyph" in str(w.message)]
    assert viewer.currentdir == str(tmp_path)
    np.testing.assert_array_equal(fig.get_size_inches(), [8, 6])
    assert fig.dpi == 100
    if extension in ("png", "jpg", "tif"):
        with Image.open(target) as image:
            assert image.width >= 1000 and image.height >= 750
            assert image.info["dpi"][0] == pytest.approx(180, abs=1)
    elif extension == "pdf":
        assert target.read_bytes().startswith(b"%PDF-")
    elif extension == "svg":
        text = target.read_text(encoding="utf-8")
        assert "<svg" in text and LABEL in text and "中文图例" in text
    else:
        assert target.read_bytes().startswith(b"%!PS-Adobe")


def test_save_cancel_and_failure_keep_existing_behavior(monkeypatch, tmp_path):
    from pandastable_local import plotting
    viewer = SimpleNamespace(fig=Mock(), master=Mock(), currentdir=str(tmp_path), globalopts={"dpi": 100})
    monkeypatch.setattr(plotting.filedialog, "asksaveasfilename", Mock(return_value=""))
    PlotViewer.savePlot(viewer)
    viewer.fig.savefig.assert_not_called()
    viewer.fig.savefig.side_effect = OSError("save failed")
    with pytest.raises(OSError, match="save failed"):
        PlotViewer.savePlot(viewer, str(tmp_path / "fail.png"))


def test_click_release_without_single_ax_keeps_multiplot_viewer_usable(capsys):
    from pandastable_local.handlers import DragHandler
    fig = Figure()
    fig.subplots(2, 2)
    handler = DragHandler(SimpleNamespace(fig=fig))
    assert handler.on_release_event(SimpleNamespace(xdata=None, ydata=None)) is True
    assert handler.dragged is None
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize('ind,labels', [([1], ['r1']), ([1, 3], ['r1', 'r3']),
                                        ([], [])])
def test_scatter_pick_uses_positions_on_custom_index(capsys, ind, labels):
    from pandastable_local.handlers import DragHandler

    fig = Figure()
    FigureCanvasAgg(fig)
    ax = fig.add_subplot(111)
    data = pd.DataFrame({'x': [1., 2., 3., 4.], 'y': [4., 3., 2., 1.]},
                        index=['r0', 'r1', 'r2', 'r3'])
    collection = ax.scatter(data['x'], data['y'])
    handler = DragHandler(SimpleNamespace(fig=fig, data=data, ax=ax))
    assert handler.on_pick_event(SimpleNamespace(artist=collection, ind=ind)) is True
    out = capsys.readouterr().out
    assert out.startswith('onpick scatter:')
    for label in labels:
        assert label in out
    assert 'r0' not in out and 'r2' not in out
    assert handler.dragged is collection


def test_scatter_pick_with_invalid_indices_does_not_raise(capsys):
    from pandastable_local.handlers import DragHandler

    fig = Figure()
    FigureCanvasAgg(fig)
    ax = fig.add_subplot(111)
    data = pd.DataFrame({'x': [1., 2.], 'y': [2., 1.]}, index=[30, 10])
    collection = ax.scatter(data['x'], data['y'])
    handler = DragHandler(SimpleNamespace(fig=fig, data=data, ax=ax))
    assert handler.on_pick_event(SimpleNamespace(artist=collection, ind=None)) is True
    assert handler.on_pick_event(SimpleNamespace(artist=collection, ind=[9])) is True
    assert capsys.readouterr().out.count('onpick scatter:') == 2


def test_line_pick_and_other_artists_keep_working(capsys):
    from matplotlib.lines import Line2D
    from pandastable_local.handlers import DragHandler

    fig = Figure()
    FigureCanvasAgg(fig)
    ax = fig.add_subplot(111)
    line, = ax.plot([0., 1., 2.], [0., 1., 4.])
    handler = DragHandler(SimpleNamespace(fig=fig, data=pd.DataFrame(), ax=ax))
    assert isinstance(line, Line2D)
    assert handler.on_pick_event(SimpleNamespace(artist=line, ind=[1])) is True
    out = capsys.readouterr().out
    assert 'onpick line:' in out
    from matplotlib.patches import Rectangle
    patch = ax.add_patch(Rectangle((0., 0.), 1., 1.))
    assert handler.on_pick_event(SimpleNamespace(artist=patch, ind=[])) is True
    assert 'onpick patch:' in capsys.readouterr().out


def test_normal_qq_and_residual_dialogs_reach_styled_plot_and_keep_reports():
    from basic_dialogs import NormTestDialog
    from fit_dialog import ResidDialog
    fig = Figure(layout="constrained")
    FigureCanvasAgg(fig)
    output = Mock()
    variable = lambda value: SimpleNamespace(get=lambda: value)
    dialog = SimpleNamespace(remember_columns=Mock(), df=pd.DataFrame({"温度": X, "压力": Y}),
        xvar=variable("温度"), yvar=variable("压力"), qq=variable(True),
        app=SimpleNamespace(print=output, showPlotViewer=lambda: SimpleNamespace(fig=fig)))
    NormTestDialog.apply(dialog)
    assert fig.axes[0].get_ylabel() == "温度"
    reference = stats.probplot(X, dist="norm")[0]
    np.testing.assert_array_equal(fig.axes[0].lines[0].get_xdata(), reference[0])
    np.testing.assert_array_equal(fig.axes[0].lines[0].get_ydata(), reference[1])
    assert output.called
    fig.clear()
    ResidDialog.apply(dialog)
    assert len(fig.axes) == 5
    assert fig.axes[3].get_title() == "正态 Q-Q 图"
    fig.canvas.draw()


def test_legacy_options_preserve_selected_font_and_add_cjk(monkeypatch):
    from pandastable_local import plotting
    options = SimpleNamespace(kwds={"font": "Arial", "fontsize": 13})
    monkeypatch.setattr(plotting.TkOptions, "applyOptions", Mock())
    with matplotlib.rc_context():
        plotting.MPLBaseOptions.applyOptions(options)
        assert matplotlib.rcParams["font.family"] == font_families("Arial")
        assert matplotlib.rcParams["font.size"] == 13
        assert matplotlib.rcParams["legend.fontsize"] == 12


@pytest.mark.parametrize("function", [fit_plot, multi_fit, multi_fit_orig, resid_test])
def test_export_source_keeps_target_figure_png_and_dpi(function):
    tree = ast.parse(textwrap.dedent(inspect.getsource(function)))
    saves = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
             and isinstance(node.func, ast.Attribute) and node.func.attr == "savefig"]
    assert len(saves) == 1
    call = saves[0]
    assert ast.unparse(call.func.value) in ("ax.figure", "fig", "axs[0][0].figure")
    assert {kw.arg: ast.literal_eval(kw.value) for kw in call.keywords} == {
        "dpi": 200, "format": "png", "bbox_inches": "tight"}


def test_shared_canvas_source_does_not_override_active_layout_engine():
    from pandastable_local.plotting import addFigure
    tree = ast.parse(textwrap.dedent(inspect.getsource(addFigure)))
    guards = [node for node in ast.walk(tree) if isinstance(node, ast.If)
              and ast.unparse(node.test) == "figure.get_layout_engine() is None"]
    assert len(guards) == 1
    assert ast.unparse(guards[0].body[0]) == "figure.subplots_adjust(bottom=0.15)"


@pytest.mark.parametrize("entry", ["fit", "matrix", "matrix_orig", "residual"])
def test_regression_png_exports_keep_filename_dpi_and_own_figure(entry, tmp_path):
    fig = Figure(figsize=(8, 6), layout="constrained")
    FigureCanvasAgg(fig)
    name = str(tmp_path / "回归中文")
    save = Mock(wraps=fig.savefig)
    fig.savefig = save
    if entry == "residual":
        linear_fit_resid_test(X, Y, axs=fig.subplots(2, 2), filename=name)
    elif entry == "fit":
        fit_plot(X, Y, ax=fig.subplots(), linear=True, show_CI=True, show_PI=True,
                 xlabel=LABEL, show_legend=True, filename=name)
    else:
        kwargs = {"ax": fig.subplots()} if entry == "matrix" else {"axs": fig.subplots(1, 1, squeeze=False)}
        (multi_fit if entry == "matrix" else multi_fit_orig)([X, Y], [LABEL, "压力 MPa"],
            fig=fig, filename=name, **kwargs)
    save.assert_called_once_with(name + ".png", dpi=200, format="png", bbox_inches="tight")
    with Image.open(name + ".png") as image:
        assert image.format == "PNG" and image.width > 1000 and image.height > 750
        assert image.info["dpi"][0] == pytest.approx(200, abs=1)


@pytest.mark.parametrize("size,scaling", [((1000, 750), 1), ((640, 480), 1), ((640, 480), 2)])
def test_real_tk_viewer_resize_controls_canvas_and_close(tk_root, tmp_path, size, scaling, monkeypatch):
    import tkinter as tk
    import gc
    import weakref
    from matplotlib.backend_bases import MouseEvent, KeyEvent
    from pandastable_local.handlers import DragHandler
    from plots import plot_viewer
    released = []
    original_release = DragHandler.on_release_event
    def release(handler, event):
        released.append(event.name)
        return original_release(handler, event)
    monkeypatch.setattr(DragHandler, "on_release_event", release)
    previous_scaling = tk_root.tk.call("tk", "scaling")
    tk_root.tk.call("tk", "scaling", scaling)
    parent = tk.Toplevel(tk_root)
    parent.geometry(f"{size[0]}x{size[1]}")
    table = SimpleNamespace(child=None)
    viewer = plot_viewer(table, parent=parent)
    handler_ref = weakref.ref(viewer._drag_handler)
    try:
        gc.collect()
        assert handler_ref() is not None
        viewer.canvas.callbacks.process("button_release_event", MouseEvent(
            "button_release_event", viewer.canvas, 10, 10, button=1))
        assert released == ["button_release_event"]
        for key in ("a", "delete"):
            viewer.canvas.callbacks.process("key_press_event", KeyEvent(
                "key_press_event", viewer.canvas, key=key))
        ax = viewer.fig.subplots()
        fit_plot(X, Y, ax=ax, xlabel=LABEL, ylabel="压力 MPa", linear=True,
                 show_CI=True, show_PI=True, show_legend=True)
        tk_root.update()
        viewer.canvas.draw()
        renderer = viewer.canvas.get_renderer()
        bounds = viewer.fig.bbox
        for artist in [ax.xaxis.label, ax.yaxis.label, ax.get_legend()]:
            box = artist.get_window_extent(renderer)
            assert box.x0 >= -1 and box.y0 >= -1
            assert box.x1 <= bounds.x1 + 1 and box.y1 <= bounds.y1 + 1
        assert viewer.ctrlfr.winfo_y() + viewer.ctrlfr.winfo_height() <= parent.winfo_height()
        viewer.globalvars["dpi"].set(160)
        assert viewer.globalopts["dpi"] == 160
        viewer.savePlot(str(tmp_path / "窗口图表.png"))
        with Image.open(tmp_path / "窗口图表.png") as image:
            assert image.info["dpi"][0] == pytest.approx(160, abs=1)
    finally:
        viewer.close()
        tk_root.tk.call("tk", "scaling", previous_scaling)
    assert not parent.winfo_exists() and table.pf is None
    del viewer
    gc.collect()
    assert handler_ref() is None
