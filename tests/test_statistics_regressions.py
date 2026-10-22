"""Regression checks for the existing statistics and plotting call paths."""
from types import SimpleNamespace
from unittest.mock import Mock

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest
from scipy import stats

from describe import describe
from linear_fit import linear_fit
from linear_plot import fit_plot, multi_fit, multi_fit_orig
from Residual import linear_fit_resid_test
from cpk_plot import cpk_plot, hist_norm
from control_chart import x_plot
from sb_histo import histo_n_fit
from sbplot_dialog import SBDialog
from grr_plot import grr_plot
from basic_dialogs import DescribeDialog, MultiDescribeDialog
from sb_hist_dialog import singleHistoDialog
from fit_dialog import LinearFitDialog, ResidDialog, CorrelationDialog


@pytest.fixture(autouse=True)
def close_figures():
    yield
    plt.close("all")


def test_describe_zero_mean_preserves_other_statistics():
    result = describe([-1, 0, 1], print_out=True, print_port=lambda *a: None)
    assert result["mean"] == 0
    assert result["stdev"] == 1
    assert np.isnan(result["coefvar"])


@pytest.mark.parametrize("data", [[], [1], [np.nan, "bad"]])
def test_describe_insufficient_data_retains_no_result_contract(data):
    assert describe(data) is None


@pytest.mark.parametrize("dialog_type", [DescribeDialog, MultiDescribeDialog])
@pytest.mark.parametrize("data", [[], [1], [np.nan]])
def test_description_dialog_reports_insufficient_numeric_data(dialog_type, data):
    dialog = SimpleNamespace(df=pd.DataFrame({"X": data}),
        xvar=SimpleNamespace(get=lambda: "X"), grpcols=["X"],
        error=Mock(), app=SimpleNamespace(print=Mock()))
    dialog_type.apply(dialog)
    dialog.error.assert_called_once()


def test_linear_regression_two_x_levels_skips_unavailable_lack_of_fit():
    x, y = [0, 0, 1, 1], [1, 2, 3, 5]
    result = linear_fit(x, y, print_out=True, print_port=lambda *a: None)
    expected = stats.linregress(x, y)
    assert result["slope"] == pytest.approx(expected.slope)
    assert result["intercept"] == pytest.approx(expected.intercept)
    assert result["p slope"] == pytest.approx(expected.pvalue)
    assert result["DFLF"] == 0
    assert result["p lack"] == -1


@pytest.mark.parametrize("y", [[1, 3, 2, 3, 1], [2, 4, 6, 8, 10]])
def test_residual_plot_handles_constant_fitted_values_or_residuals(y):
    fig, axs = plt.subplots(2, 2)
    linear_fit_resid_test([1, 2, 3, 4, 5], y, axs=axs)
    assert len(axs[0, 1].collections) == 1
    assert len(axs[0, 1].lines) == 0
    fig.canvas.draw()


def test_numeric_plot_data_keeps_group_row_alignment():
    dialog = SimpleNamespace(df=pd.DataFrame({
        "数值": [1, "", "bad", 4], "分组": ["甲", "乙", "丙", "丁"]}))
    SBDialog.make_working_df(dialog, cols=["分组"], numcols=["数值"])
    assert dialog.working_df["分组"].tolist() == ["甲", "乙", "丙", "丁"]
    np.testing.assert_allclose(dialog.working_df["数值"], [1, np.nan, np.nan, 4], equal_nan=True)


def test_histogram_uses_axes_figure_for_legend_and_ignores_missing_values():
    fig, ax = plt.subplots()
    histo_n_fit(df=pd.DataFrame({"X": [1, np.nan, 2, 3]}), xkey="X", ax=ax, legend=True)
    assert len(fig.legends) == 1
    assert np.isfinite(ax.get_xlim()).all()


@pytest.mark.parametrize("values", [[1, "bad", None, "3"], [None, "bad"]])
def test_histogram_dialog_passes_numeric_data_without_changing_source(values):
    dialog = object.__new__(singleHistoDialog)
    dialog.df = pd.DataFrame({"X": values})
    original = dialog.df.copy(deep=True)
    dialog.xvar = SimpleNamespace(get=lambda: "X")
    dialog.stat = SimpleNamespace(get=lambda: "count")
    dialog.fit_dist = SimpleNamespace(get=lambda: False)
    dialog.get_x_plot_settings = Mock()
    dialog.get_misc_plot_settings = Mock()
    dialog.get_histo_setting = Mock()
    dialog.app = SimpleNamespace(print=Mock())
    dialog.error = Mock()
    dialog.showPlotViewer = Mock(return_value=SimpleNamespace(fig=plt.figure()))
    dialog.xlabel_v, dialog.x_min_v, dialog.x_max_v = None, None, None
    dialog.bins_v, dialog.binwidth_v = "auto", None
    dialog.ax_margin_v, dialog.show_legend_v, dialog.grid_v = 0.1, False, False
    dialog.apply()
    pd.testing.assert_frame_equal(dialog.df, original)
    if any(isinstance(x, int) for x in values):
        assert dialog.working_df["X"].dropna().tolist() == [1, 3]
        dialog.error.assert_not_called()
    else:
        dialog.error.assert_called_once()
        dialog.showPlotViewer.assert_not_called()


@pytest.mark.parametrize("draw", [
    lambda ax, name: fit_plot([1, 2, 3, 4], [1, 3, 2, 5], ax=ax, filename=name),
    lambda ax, name: multi_fit([[1, 2, 3, 4], [1, 3, 2, 5]], ["X", "Y"], ax=ax, fig=ax.figure, filename=name),
    lambda ax, name: multi_fit_orig([[1, 2, 3, 4], [1, 3, 2, 5]], ["X", "Y"], axs=[[ax]], fig=ax.figure, filename=name),
    lambda ax, name: hist_norm([1, 3, 2, 5], ax=ax, filename=name),
    lambda ax, name: cpk_plot([1, 3, 2, 5], usl=8, target=4, lsl=0, ax=ax, filename=name),
    lambda ax, name: x_plot([1, 3, 2, 5], ax=ax, one_chart=True, filename=name),
    lambda ax, name: linear_fit_resid_test([1, 2, 3, 4], [1, 3, 2, 5], axs=ax.figure.subplots(2, 2), filename=name),
])
def test_export_saves_target_axes_figure_not_current_pyplot_figure(draw, tmp_path, monkeypatch):
    target, ax = plt.subplots()
    unrelated = plt.figure()
    target_save = Mock()
    unrelated_save = Mock()
    monkeypatch.setattr(target, "savefig", target_save)
    monkeypatch.setattr(unrelated, "savefig", unrelated_save)
    draw(ax, str(tmp_path / "图表"))
    target_save.assert_called_once()
    unrelated_save.assert_not_called()


def test_grr_part_positions_are_consistent_across_operators():
    fig, ax = plt.subplots()
    grr_plot(y=[10, 20, 21, 11], part=["A", "B", "B", "A"],
             op=["one", "one", "two", "two"], ax=ax)
    assert [[tick.get_text() for tick in child.get_xticklabels()]
            for child in ax.child_axes] == [["A", "B"], ["A", "B"]]


def test_representative_statistics_match_existing_reference_algorithms():
    from t_test import t_test_1sample, t_test_2samples
    from one_way_ANOVA import one_way_anova
    from cpk import cpk
    a, b = [1, 2, 4, 5, 7], [2, 3, 5, 8, 9]
    assert t_test_1sample(a, 3)["p"] == pytest.approx(stats.ttest_1samp(a, 3).pvalue)
    assert t_test_2samples(a, b)["p"] == pytest.approx(stats.ttest_ind(a, b, equal_var=False).pvalue)
    assert one_way_anova([a, b], ["A", "B"])["F"] == pytest.approx(stats.f_oneway(a, b).statistic)
    result = cpk(a, target=4, usl=10, lsl=0, print_out=False)
    assert result["Overall"]["cp"] == pytest.approx(10 / (6 * np.std(a, ddof=1)))


def test_describe_correlation_regression_known_results_smoke():
    from utilities import pearson_correlation
    result = describe([1, 2, 3, 4, 5])
    assert result["mean"] == 3
    assert result["var"] == 2.5
    assert result["Q1"] == 1.5
    assert result["Q3"] == 4.5
    x, y = [1, 2, 3, 4, 5], [1, 3, 2, 5, 4]
    corr = pearson_correlation(x, y, print_out=False)
    assert corr["r"] == pytest.approx(0.8)
    assert corr["p"] == pytest.approx(stats.pearsonr(x, y).pvalue)
    fit = linear_fit(x, y, print_out=False)
    assert fit["slope"] == pytest.approx(0.8)
    assert fit["intercept"] == pytest.approx(0.6)
    assert fit["R Square"] == pytest.approx(0.64)
    assert fit["SSE"] == pytest.approx(3.6)


def test_two_way_anova_grr_and_spc_known_results_smoke():
    from two_way_anova import two_way_anova
    from GRR import grr_master
    from control_chart import x_mR, xBar_R, xBar_S
    anova = two_way_anova([[[1, 2], [3, 4]], [[2, 4], [5, 8]]])
    assert anova["SSA"] == pytest.approx(10.125)
    assert anova["SSB"] == pytest.approx(15.125)
    assert anova["SSAB"] == pytest.approx(1.125)
    assert anova["MSE"] == pytest.approx(1.875)
    grr = grr_master(y=[1, 2, 3, 4, 1, 2, 3, 4],
        part=["A", "A", "B", "B"] * 2, op=["one"] * 4 + ["two"] * 4,
        mode="AIAG", inter="Off")
    assert grr == pytest.approx({"EV": 0.4, "AV": 0, "PV": 1.9,
                                "RR": 0.4, "TV": 2.3, "INT": 0})
    individuals = x_mR([1, 3, 2, 5], 2, sigma=1)
    assert individuals["bar1"] == 2.75
    assert individuals["ucl1"] == 5.75
    assert individuals["lcl1"] == -0.25
    for draw in (xBar_R, xBar_S):
        result = draw([[1, 2, 3], [2, 3, 5], [4, 5, 6]], mean=3, sigma=1)
        np.testing.assert_allclose(result["Y1"], [2, 10 / 3, 5])
        np.testing.assert_allclose(result["ucl1"], 4.732050807568877)
        np.testing.assert_allclose(result["lcl1"], 1.267949192431123)


def test_plot_viewer_close_releases_owned_references_and_figure():
    import pickle
    from plots import plot_viewer
    figure, ax = plt.subplots()
    ax.plot([1, 2], [3, 4])
    stored = pickle.loads(pickle.dumps(figure))
    child = SimpleNamespace()
    table = SimpleNamespace(child=child)
    viewer = SimpleNamespace(table=table, fig=figure, main=Mock(), animateopts=Mock(),
                             globalvars={}, _cleaned_up=False, _drag_handler=None)
    viewer._cleanup = lambda: plot_viewer._cleanup(viewer)
    table.pf = child.pf = viewer
    plot_viewer.close(viewer)
    assert table.pf is child.pf is None
    assert figure.number not in plt.get_fignums()
    viewer.animateopts.stop.assert_called_once()
    viewer.main.destroy.assert_called_once()
    assert stored.axes[0].lines[0].get_ydata().tolist() == [3, 4]


def test_closing_previous_plot_keeps_new_plot_reference():
    from plots import plot_viewer
    current = object()
    table = SimpleNamespace(pf=current)
    viewer = SimpleNamespace(table=table, fig=plt.figure(), main=Mock(), globalvars={},
                             _cleaned_up=False, _drag_handler=None)
    viewer._cleanup = lambda: plot_viewer._cleanup(viewer)
    plot_viewer.close(viewer)
    assert table.pf is current


def test_embedded_plot_windows_close_and_leave_stored_figure_usable(tk_root):
    import gc
    import pickle
    import tkinter as tk
    import weakref
    from plots import plot_viewer
    root = tk_root
    table = SimpleNamespace(child=SimpleNamespace(pf=None))
    initial_managers = plt.get_fignums()
    figure_refs = []
    try:
        for _ in range(3):
            host = tk.Frame(root)
            viewer = plot_viewer(table=table, parent=host)
            table.child.pf = viewer
            ax = viewer.fig.add_subplot(111)
            ax.plot([1, 2], [3, 4])
            stored = pickle.loads(pickle.dumps(viewer.fig))
            figure_refs.append(weakref.ref(viewer.fig))
            viewer.close()
            assert not host.winfo_exists()
            assert table.pf is table.child.pf is None
            assert stored.axes[0].lines[0].get_ydata().tolist() == [3, 4]
            del ax, viewer, host
        root.update_idletasks()
        gc.collect()
        assert plt.get_fignums() == initial_managers
        assert all(ref() is None for ref in figure_refs)
    finally:
        for host in root.winfo_children():
            host.destroy()


def variable(value):
    return SimpleNamespace(get=lambda: value)


@pytest.mark.parametrize("dialog_type", [LinearFitDialog, ResidDialog, CorrelationDialog])
@pytest.mark.parametrize("x, y", [([], []), ([1], [2]), ([1, 1, 1, 1], [1, 2, 3, 4]),
                                  ([1, 2, 3, 4], [1, 1, 1, 1])])
def test_fit_dialog_rejects_unestimable_input_before_plot_creation(dialog_type, x, y):
    dialog = SimpleNamespace(df=pd.DataFrame({"X": x, "Y": y}),
        xvar=variable("X"), yvar=variable("Y"), linear=variable(True),
        ortho=variable(False), cor_p=variable(True), cor_h=variable(False),
        error=Mock(), app=SimpleNamespace(print=Mock(), showPlotViewer=Mock()))
    dialog_type.apply(dialog)
    dialog.error.assert_called_once()
    dialog.app.showPlotViewer.assert_not_called()


@pytest.mark.parametrize("dialog_type, parameters", [
    ("t", {"sample_n": "1", "sample_std": "2", "sample_mean": "3"}),
    ("t", {"sample_n": "5", "sample_std": "0", "sample_mean": "3"}),
    ("t", {"sample_n": "5", "sample_std": "2", "sample_mean": "3", "alpha": "1"}),
    ("z", {"sample_n": "5", "sample_mean": "3", "s0": "0"}),
])
def test_mean_test_dialog_rejects_invalid_summary_parameters(dialog_type, parameters):
    from sample_test_dialog import Mean1SampleDialog, Mean1SampleZDialog
    values = dict(xvar="", sample_mean="", sample_std="", sample_n="", u0="0", s0="1", alpha="0.05")
    values.update(parameters)
    dialog = SimpleNamespace(**{key: variable(value) for key, value in values.items()},
                             error=Mock(), app=SimpleNamespace(print=Mock()))
    (Mean1SampleDialog if dialog_type == "t" else Mean1SampleZDialog).apply(dialog)
    dialog.error.assert_called_once()


@pytest.mark.parametrize("values", [[], [1], [2, 2, 2]])
def test_capability_dialog_rejects_insufficient_or_constant_data(values):
    from qc_dialog import CpkDialog
    dialog = SimpleNamespace(df=pd.DataFrame({"X": values}), xvar=variable("X"), error=Mock())
    CpkDialog.apply(dialog)
    dialog.error.assert_called_once()


@pytest.mark.parametrize("plot_type, data", [("x_mR", []), ("x_mR", [1]),
    ("XBAR_R", [[1]]), ("XBAR_R", [list(range(26))]), ("XBAR_S", [[1]])])
def test_control_chart_dialog_rejects_unsupported_sample_sizes(plot_type, data):
    from ctrlchart_dialog import IMRDialog
    dialog = SimpleNamespace(get_data=lambda: (data, None, None, None, None),
                             plot_type=plot_type, error=Mock())
    IMRDialog.apply(dialog)
    dialog.error.assert_called_once()


@pytest.mark.parametrize("group_size", ["", "0", "1"])
def test_subgroup_chart_preserves_group_labels_and_rejects_invalid_size(group_size):
    from ctrlchart_dialog import XBRDialog
    dialog = object.__new__(XBRDialog)
    dialog.df = pd.DataFrame({"Y": [1, 2, 3, 4], "G": ["b", "b", "a", "a"]})
    dialog.gsize, dialog.gid = variable(group_size), variable("G")
    dialog.xvar, dialog.xlabelID = variable("Y"), variable("")
    dialog.error, dialog.get_axs = Mock(), Mock(return_value=(None, None, None))
    result = dialog.get_data()
    if group_size == "":
        assert result[:2] == ([[3, 4], [1, 2]], ["a", "b"])
        dialog.error.assert_not_called()
    else:
        assert result is None
        dialog.error.assert_called_once()
        dialog.get_axs.assert_not_called()


@pytest.mark.parametrize("values", [[1], [1, 1]])
def test_anova_dialog_rejects_insufficient_or_zero_variance_groups(values):
    from anova_dialog import Anova1WayDialog
    dialog = SimpleNamespace(df=pd.DataFrame({"A": values, "B": values}),
        grpcols=["A", "B"], alpha=variable(.05), xvar=variable(""),
        grouping=variable(""), error=Mock(), app=SimpleNamespace(print=Mock()))
    Anova1WayDialog.apply(dialog)
    dialog.error.assert_called_once()
