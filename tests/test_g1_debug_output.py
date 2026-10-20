"""G1 收尾：具体统计执行路径的调试输出和原有报告契约。"""
import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest
from matplotlib.figure import Figure
from scipy import stats

import basic_dialogs
import control_chart
import ctrlchart_dialog
import fit_dialog
from control_chart import x_mR
from describe import describe


ROOT = Path(__file__).resolve().parents[1]


def variable(value):
    return SimpleNamespace(get=lambda: value)


def test_describe_apply_keeps_report_without_printing_column(capsys, monkeypatch):
    output = []
    dialog = SimpleNamespace(df=pd.DataFrame({'X': [1, 'bad', 3, 2, 5]}),
        xvar=variable('X'), pct=variable('100,50,0'), error=Mock(),
        app=SimpleNamespace(print=output.append))
    spy = Mock(wraps=basic_dialogs.describe)
    monkeypatch.setattr(basic_dialogs, 'describe', spy)
    basic_dialogs.DescribeDialog.apply(dialog)
    spy.assert_called_once_with([1., 3., 2., 5.], print_out=False,
                               percentiles=[100., 50., 0.])
    result = describe([1., 3., 2., 5.], percentiles=[100., 50., 0.])
    assert result['mean'] == 2.75
    assert result['var'] == pytest.approx(np.var([1, 3, 2, 5], ddof=1))
    text = '\n'.join(output)
    assert '描述性统计' in text and 'N*' in text
    row = next(line for line in text.splitlines() if line.startswith('| X'))
    assert [cell.strip() for cell in row.split('|')[1:5]] == ['X', '4', '1', '2.750']
    assert '100.00%' in text and '50.00%' in text and '0.00%' in text
    dialog.error.assert_not_called()
    assert capsys.readouterr().out == ''


@pytest.mark.parametrize('mr,ranges,d2,d3', [
    (2, [np.nan, 2, 1, 3], 1.128, .8525),
    (3, [np.nan, np.nan, 2, 3], 1.693, .8884),
])
@pytest.mark.parametrize('sigma', [None, 1])
def test_x_mr_keeps_complete_data_structure_without_debug_parameters(mr, ranges, d2, d3, sigma, capsys):
    data = [1, 3, 2, 5]
    result = x_mR(data, mr, sigma=sigma)
    rbar = np.nanmean(ranges)
    deviation = rbar/d2 if sigma is None else sigma
    expected = {'Y1': data, 'Y2': ranges, 'bar1': 2.75,
        'ucl1': 2.75+3*deviation, 'lcl1': 2.75-3*deviation,
        'bar2': rbar, 'ucl2': d2*deviation+3*deviation*d3,
        'lcl2': max(0, d2*deviation-3*deviation*d3), 'n': 2,
        'X': [0, 1, 2, 3], 'ylabel1': 'Individual Values',
        'ylabel2': f'Moving Range (n={mr})'}
    assert result.keys() == expected.keys()
    for key, value in expected.items():
        if isinstance(value, str):
            assert result[key] == value
        else:
            np.testing.assert_allclose(result[key], value, equal_nan=True)
    assert capsys.readouterr().out == ''


@pytest.mark.parametrize('dialog_type,n', [(ctrlchart_dialog.NPDialog, 100),
                                          (ctrlchart_dialog.PDialog, [100, 120, 80])])
def test_np_p_apply_keeps_plot_data_labels_and_report(dialog_type, n, capsys, monkeypatch):
    figure = Figure()
    ax = figure.subplots()
    output = []
    data = [.02, .04, .03]
    chart = 'NP' if dialog_type is ctrlchart_dialog.NPDialog else 'P'
    dialog = SimpleNamespace(get_data=lambda: (data, ['A', 'B', 'C'], figure, ax, n),
        plot_type=chart, y1label=variable(''), xvar=variable('缺陷'),
        xlabel=variable(''), xlabelID=variable('批次'), max_x_labels=variable(25),
        y1ref=variable(''), app=SimpleNamespace(print=output.append))
    original = ctrlchart_dialog.p_np_plot
    spy = Mock(wraps=original)
    monkeypatch.setattr(ctrlchart_dialog, 'p_np_plot', spy)
    monkeypatch.setattr(control_chart.plt, 'show', Mock())
    assert dialog_type.apply(dialog) is None
    spy.assert_called_once()
    options = spy.call_args.kwargs
    assert options['p'] == data and options['n'] == n
    assert options['NP'] is (chart == 'NP')
    assert options['xLabels'] == ['A', 'B', 'C'] and options['xlabel'] == '批次'
    expected_label = ('Count' if chart == 'NP' else 'Proportion') + ' (缺陷)'
    assert ax.get_ylabel() == expected_label
    np.testing.assert_allclose(ax.lines[0].get_ydata(), np.array(data)*(100 if chart == 'NP' else 1))
    expected_output = []
    other = Figure()
    assert original(**dict(options, fig=other, ax=other.subplots(),
                           print_port=expected_output.append)) is None
    assert output == expected_output
    assert output[0] == f'\n---- SPC 控制图报告：{chart} ----'
    assert f'输入标签（Y 轴）：{expected_label}' in output
    assert capsys.readouterr().out == ''


@pytest.mark.parametrize('dialog_type', [fit_dialog.LinearFitDialog, fit_dialog.CorrelationDialog])
def test_both_fit_apply_implementations_keep_results_reports_and_axis_labels(dialog_type, capsys, monkeypatch):
    x, y = [1, 2, 3, 4, 5, 6], [2, 4, 3, 8, 6, 10]
    figure = Figure()
    viewer = SimpleNamespace(fig=figure)
    output = []
    flags = dict(linear=True, ortho=False, ellipse=True, red_ellipse=False,
        show_CI=False, show_PI=False, ortho_resid=False, ortho_ratio=1,
        scatter=True, alpha=.05, cor_p=True, cor_s=False, cor_k=False, cor_h=False)
    dialog = SimpleNamespace(**{key: variable(value) for key, value in flags.items()},
        df=pd.DataFrame({'X': x, 'Y': y}), xvar=variable('X'), yvar=variable('Y'),
        get_plot_settings=Mock(), xlabel='横轴', ylabel='纵轴',
        x_min=None, x_max=None, y_min=None, y_max=None, ax_margin=.1,
        show_legend=False, grid=False, error=Mock(),
        app=SimpleNamespace(print=output.append, showPlotViewer=lambda: viewer))
    original = fit_dialog.fit_plot
    captured = {}
    def run_fit(*args, **kwargs):
        captured['args'], captured['kwargs'] = args, kwargs
        captured['result'] = original(*args, **kwargs)
        return captured['result']
    monkeypatch.setattr(fit_dialog, 'fit_plot', run_fit)
    dialog_type.apply(dialog)
    assert captured['args'] == (list(map(float, x)), list(map(float, y)))
    result = captured['result']
    assert result['Pearson']['r'] == pytest.approx(stats.pearsonr(x, y).statistic)
    if dialog_type is fit_dialog.LinearFitDialog:
        assert result['Linear Regression']['slope'] == pytest.approx(stats.linregress(x, y).slope)
        assert result['Linear Regression']['p slope'] == pytest.approx(stats.linregress(x, y).pvalue)
    expected_output = []
    other = Figure()
    expected_result = original(*captured['args'], **dict(captured['kwargs'],
        ax=other.subplots(), print_port=expected_output.append))
    assert result == expected_result
    assert output[2:] == expected_output
    assert any('Pearson 相关分析' in line for line in expected_output)
    assert viewer.ax.get_xlabel() == '横轴' and viewer.ax.get_ylabel() == '纵轴'
    dialog.error.assert_not_called()
    assert capsys.readouterr().out == ''


def test_shared_statistics_dialog_construction_does_not_print(tk_root, capsys):
    dialog = basic_dialogs.DescribeDialog(tk_root, df=pd.DataFrame({'X': [1, 2, 3]}),
        title='Describe', app=SimpleNamespace(dialog_help_msg=lambda **kwargs: ''))
    try:
        assert dialog.main.winfo_exists()
        assert capsys.readouterr().out == ''
    finally:
        dialog.quit()


@pytest.mark.parametrize('filename,owner,function,old_pattern', [
    ('basic_dialogs.py', 'DescribeDialog', 'apply', 'print(x)'),
    ('control_chart.py', None, 'x_mR', 'print("mr", mr)'),
    ('ctrlchart_dialog.py', 'NPDialog', 'apply', 'print(NP)'),
    ('fit_dialog.py', 'LinearFitDialog', 'apply', 'print("xlabel", xlabel, "y", ylabel)'),
    ('fit_dialog.py', 'CorrelationDialog', 'apply', 'print("xlabel", xlabel, "y", ylabel)'),
    ('dialog.py', 'Dialogs', '__init__', 'print("Gen new dialog", self.title)'),
])
def test_each_named_function_and_each_duplicate_has_no_direct_debug_print(filename, owner, function, old_pattern):
    source = (ROOT/'code'/filename).read_text(encoding='utf-8')
    assert old_pattern not in source
    scope = ast.parse(source)
    if owner is not None:
        scope = next(node for node in scope.body if isinstance(node, ast.ClassDef) and node.name == owner)
    method = next(node for node in scope.body if isinstance(node, ast.FunctionDef) and node.name == function)
    assert not any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                   and node.func.id == 'print' for node in ast.walk(method))


@pytest.mark.parametrize('filename', ['chi_sq.py', 'linear_fit.py', 'nonpara_cor.py',
    'plots.py', 'proportion_test.py', 't_test.py', 'txt_output.py', 'utilities.py'])
def test_g1_files_keep_verified_head_lf_style(filename):
    assert b'\r' not in (ROOT/'code'/filename).read_bytes()
