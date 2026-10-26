"""回归报告的单元格映射、边界、实际入口和图形契约。"""
import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest
from matplotlib.figure import Figure
from scipy import stats
from wcwidth import wcswidth

import fit_dialog
import linear_fit as ols
import linear_plot
import ortho_fit
import Residual
from utilities import format_stat

X = [1., 2., 4., 5., 7., 8.]
Y = [2., 4., 3., 8., 6., 10.]
ROOT = Path(__file__).resolve().parents[1]


def capture(monkeypatch, module):
    tables = []
    original = module.gen_table
    def table(rows):
        result = original(rows)
        tables.append(result)
        return result
    monkeypatch.setattr(module, 'gen_table', table)
    return tables


def variable(value):
    return SimpleNamespace(get=lambda: value)


def test_ols_summary_coefficients_anova_and_diagnostics(monkeypatch):
    tables = capture(monkeypatch, ols)
    lines = []
    r = ols.linear_fit(X, Y, print_port=lines.append)
    ref = stats.linregress(X, Y)
    assert r['slope'] == pytest.approx(ref.slope)
    assert r['intercept'] == pytest.approx(ref.intercept)
    assert r['p slope'] == pytest.approx(ref.pvalue)
    assert tables[0].field_names == ['N', 'R-sq', '调整 R-sq', '残差标准误 S', '响应均值']
    assert tables[0].rows == [[6] + [format_stat(r[k]) for k in
        ['R Square', 'R Square Adj', 'Root MSE', 'Mean of Response']]]
    assert tables[1].field_names == ['参数', '系数', '标准误', 't 绝对值', 'p 值']
    assert tables[1].rows == [
        ['截距'] + [format_stat(r[k]) for k in ['intercept', 'Std Error Int.', 't int.', 'p int.']],
        ['X（斜率）'] + [format_stat(r[k]) for k in ['slope', 'Std Error Slope', 't slope', 'p slope']]]
    assert tables[2].field_names == ['来源', '自由度', '平方和 SS', '均方 MS', 'F 值', 'p 值']
    assert tables[2].rows == [
        ['回归', 1] + [format_stat(r[k]) for k in ['SSR', 'MSR', 'F Reg', 'p reg']],
        ['误差', 4, format_stat(r['SSE']), format_stat(r['MSE']), '*', '*'],
        ['总计', 5, format_stat(r['SST']), '*', '*', '*']]
    normal = r['Normal Test Resid']
    assert tables[3].rows == [
        ['Shapiro-Wilk', format_stat(normal['shapiro s']), format_stat(normal['shapiro p'])],
        ['Anderson-Darling', format_stat(normal['AD s']), format_stat(normal['AD p'])]]
    text = '\n'.join(lines)
    assert f'Y = {r["intercept"]:.3f} {r["slope"]:+.3f} * X' in text
    assert '未计算系数置信区间' in text and '不保证模型正确' in text
    assert '0.000 是舍入结果' in text and '失拟检验不可用' in text
    assert all(len({wcswidth(line) for line in str(t).splitlines()}) == 1 for t in tables)
    assert all(t.align[c] == 'r' for t in tables for c in t.field_names[1:])


def test_lack_of_fit_decomposes_error_not_total(monkeypatch):
    tables = capture(monkeypatch, ols)
    r = ols.linear_fit([1, 1, 2, 2, 3, 3], Y, print_port=lambda line: None)
    assert r['p lack'] >= 0
    assert tables[3].rows == [
        ['失拟', r['DFLF']] + [format_stat(r[k]) for k in ['SSLF', 'MSLF', 'F lack', 'p lack']],
        ['纯误差', r['DFPE'], format_stat(r['SSPE']), format_stat(r['MSPE']), '*', '*'],
        ['误差合计', r['DF Error'], format_stat(r['SSE']), format_stat(r['MSE']), '*', '*']]


def test_perfect_fit_unestimable_tests_are_not_negative_statistics(monkeypatch):
    tables = capture(monkeypatch, ols)
    r = ols.linear_fit([1, 2, 3, 4], [3, 5, 7, 9], print_port=lambda line: None)
    assert r['t slope'] == r['F Reg'] == -1
    assert r['p slope'] == r['p reg'] == 0
    assert tables[1].rows[1][-2:] == ['*', '*']
    assert tables[2].rows[0][-2:] == ['*', '*']


@pytest.mark.parametrize('alpha,ratio', [(.05, 1), (.1, 1.3)])
def test_orthogonal_parameter_intervals_and_residual_rows(monkeypatch, alpha, ratio):
    tables = capture(monkeypatch, ortho_fit)
    lines = []
    r = ortho_fit.orthogonal_fit(X, Y, alpha=alpha, error_ratio=ratio,
        print_residual=True, print_port=lines.append)
    assert tables[0].field_names == ['参数', '系数', '置信下限', '置信上限']
    assert tables[0].rows == [
        ['截距'] + [format_stat(r[k]) for k in ['intercept', 'int_l', 'int_u']],
        ['X（斜率）'] + [format_stat(r[k]) for k in ['slope', 'slope_l', 'slope_u']]]
    assert tables[1].rows == [['X', format_stat(r['Var U'])], ['Y', format_stat(r['Var E'])]]
    assert tables[2].field_names == ['观测', 'X', '拟合 X', 'Y', '拟合 Y', '残差', '标准化残差']
    for i, row in enumerate(tables[2].rows):
        assert row == [i+1, format_stat(X[i]), format_stat(r['Fitted X'][i]),
            format_stat(Y[i]), format_stat(r['Fitted Y'][i]),
            format_stat(r['Residuals'][i]), format_stat(r['St Resid'][i])]
    text = '\n'.join(lines)
    assert f'{(1-alpha)*100:.1f}% 双侧置信区间' in text
    assert f'Var(Y误差) / Var(X误差) = {ratio:.3f}' in text
    assert '不是单次观测的预测区间' in text


@pytest.mark.parametrize('method', [ols.linear_fit, ortho_fit.orthogonal_fit])
def test_regression_print_switch_keeps_raw_return_values(method):
    quiet, loud = [], []
    a = method(X, Y, print_out=False, print_port=quiet.append)
    b = method(X, Y, print_out=True, print_port=loud.append)
    assert quiet == [] and loud
    assert a.keys() == b.keys()
    for key in a:
        assert type(a[key]) is type(b[key])
        if isinstance(a[key], dict):
            assert a[key] == b[key]
        else:
            np.testing.assert_equal(a[key], b[key])


def test_independent_orthogonal_residual_switch_is_preserved(monkeypatch):
    tables = capture(monkeypatch, ortho_fit)
    lines = []
    ortho_fit.orthogonal_fit(X, Y, print_out=False, print_residual=True, print_port=lines.append)
    assert len(tables) == 1 and len(tables[0].rows) == len(X)
    assert not any('正交回归' in line for line in lines)


@pytest.mark.parametrize('linear,ortho', [(True, False), (False, True), (True, True)])
def test_plot_labels_interval_meanings_and_unchanged_curves(linear, ortho):
    lines = []
    outputs = []
    for print_out in (False, True):
        ax = Figure().subplots()
        result = linear_plot.fit_plot(X, Y, ax=ax, linear=linear, ortho=ortho,
            xlabel='温度 Temperature 很长的预测变量名', ylabel='响应 Response 压力',
            show_CI=True, show_PI=True, alpha=.1, print_out=print_out, print_port=lines.append)
        outputs.append((result, [(a.get_label(), a.get_xdata(), a.get_ydata()) for a in ax.lines]))
    assert outputs[0][0] == outputs[1][0]
    assert len(outputs[0][1]) == (5 if linear else 0) + int(ortho)
    for first, second in zip(outputs[0][1], outputs[1][1]):
        assert first[0] == second[0]
        np.testing.assert_array_equal(first[1], second[1])
        np.testing.assert_array_equal(first[2], second[2])
    text = '\n'.join(lines)
    assert '温度 Temperature 很长的预测变量名' in text and '响应 Response 压力' in text
    if linear:
        assert '90.0%' in text and '总体平均响应的置信区间' in text and '新观测的预测区间' in text


@pytest.mark.parametrize('method', [Residual.resid_test, Residual.linear_fit_resid_test])
def test_residual_diagnostic_direct_and_fitted_entry(method):
    lines = []
    args = (Y, X) if method is Residual.resid_test else (X, Y)
    quiet = method(*args, axs=Figure().subplots(2, 2), print_port=lines.append)
    assert lines == []
    loud = method(*args, axs=Figure().subplots(2, 2), print_out=True, print_port=lines.append)
    assert quiet == loud
    data = Y if method is Residual.resid_test else ols.linear_fit(X, Y, print_out=False)['Residual']
    assert loud['shapiro p'] == stats.shapiro(data).pvalue
    assert '针对残差' in '\n'.join(lines)


@pytest.mark.parametrize('dialog_class', [fit_dialog.LinearFitDialog, fit_dialog.OrthoFitDialog,
                                        fit_dialog.ResidDialog])
def test_actual_dialog_apply_keeps_cleaning_and_reaches_report(dialog_class):
    lines = []
    figure = Figure()
    d = SimpleNamespace(df=pd.DataFrame({'温度': X + [None], '响应': Y + [15]}),
        xvar=variable('温度'), yvar=variable('响应'), error=Mock(), remember_columns=Mock(),
        app=SimpleNamespace(print=lines.append, showPlotViewer=lambda: SimpleNamespace(fig=figure)))
    if dialog_class is not fit_dialog.ResidDialog:
        for key, value in dict(linear=dialog_class is fit_dialog.LinearFitDialog,
            ortho=dialog_class is fit_dialog.OrthoFitDialog, ellipse=False, red_ellipse=False,
            show_CI=True, show_PI=True, ortho_resid=True, scatter=True, alpha=.1, ortho_ratio=1.3).items():
            setattr(d, key, variable(value))
        for key, value in dict(xlabel=None, ylabel=None, x_min=None, x_max=None, y_min=None,
            y_max=None, ax_margin=.1, show_legend=False, grid=False).items():
            setattr(d, key, value)
        d.get_plot_settings = lambda: None
    dialog_class.apply(d)
    d.error.assert_not_called()
    d.remember_columns.assert_called_once_with()
    from stat_table import StatTable
    assert any(isinstance(line, StatTable) for line in lines)
    text = '\n'.join(lines)
    expected = {fit_dialog.LinearFitDialog: '普通最小二乘线性回归',
        fit_dialog.OrthoFitDialog: '正交回归', fit_dialog.ResidDialog: '残差正态性诊断'}[dialog_class]
    assert expected in text and 'Valid number pairs: 6' in text
    assert len(figure.axes) == (5 if dialog_class is fit_dialog.ResidDialog else 1)
    d.df = pd.DataFrame({'温度': [1, 1], '响应': [2, 3]})
    dialog_class.apply(d)
    d.error.assert_called_once()


@pytest.mark.parametrize('filename,function,old', [
    ('linear_fit.py', 'linear_fit', 'Summary of Fit'),
    ('ortho_fit.py', 'orthogonal_fit', 'Slope %.3f CI'),
    ('Residual.py', 'resid_test', None), ('linear_plot.py', 'fit_plot', None)])
def test_scoped_report_source_and_public_signature(filename, function, old):
    source = (ROOT / 'code' / filename).read_text(encoding='utf-8')
    node = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == function)
    body = ast.get_source_segment(source, node)
    if old:
        assert old not in body and 'PT()' not in body
    assert 'print_out' in ast.unparse(node.args)


@pytest.mark.parametrize('pearson', [True, False])
def test_correlation_dialog_forwards_pearson_switch(monkeypatch, pearson):
    captured = {}
    def fit(x, y, **kwargs):
        captured.update(x=x, y=y, kwargs=kwargs)
        return {}
    monkeypatch.setattr(fit_dialog, 'fit_plot', fit)
    d = SimpleNamespace(df=pd.DataFrame({'X': X, 'Y': Y}), xvar=variable('X'), yvar=variable('Y'),
        error=Mock(), remember_columns=Mock(), get_plot_settings=lambda: None,
        app=SimpleNamespace(print=Mock(), showPlotViewer=lambda: SimpleNamespace(fig=Figure())))
    for key, value in dict(cor_p=pearson, cor_s=False, cor_k=False, cor_h=False, ellipse=True,
            red_ellipse=False, scatter=True, alpha=.05, ax_margin=.1).items():
        setattr(d, key, variable(value))
    for key, value in dict(xlabel=None, ylabel=None, x_min=None, x_max=None, y_min=None,
            y_max=None, show_legend=False, grid=False).items():
        setattr(d, key, value)
    fit_dialog.CorrelationDialog.apply(d)
    d.error.assert_not_called()
    assert captured['x'] == X and captured['y'] == Y
    kwargs = captured['kwargs']
    assert kwargs['pearson'] is pearson
    assert kwargs['ellipse'] is pearson and kwargs['print_out'] is pearson


@pytest.mark.parametrize('model_name', ['OLS', 'GLS', 'Logit'])
def test_statsviewer_reuses_complete_native_model_summary(model_name, monkeypatch):
    import statsmodels.api as sm
    from pandastable_local.stats import StatsViewer
    x = np.arange(12.)
    y = np.array([0, 0, 1, 0, 1, 0, 1, 1, 0, 1, 1, 1]) if model_name == 'Logit' else x + np.sin(x)
    model = getattr(sm, model_name)(y, sm.add_constant(x))
    result = model.fit(disp=False) if model_name == 'Logit' else model.fit()
    expected_summary = result.summary()
    monkeypatch.setattr(result, 'summary', lambda: expected_summary)
    before = result.params.copy()
    outputs = []
    viewer = SimpleNamespace(add_table=lambda table, end: outputs.append(str(table)+end),
                             add_txt=outputs.append, to_end=Mock())
    StatsViewer.summary(SimpleNamespace(fit=result, fitinfo=viewer))
    summary = ''.join(outputs)
    assert summary == str(result.summary())
    assert model_name in str(summary) and 'coef' in str(summary) and '[0.025' in str(summary)
    np.testing.assert_array_equal(result.params, before)


def test_statsviewer_regression_plot_iterates_native_parameters():
    import statsmodels.api as sm
    from pandastable_local.stats import StatsViewer

    x = np.arange(1., 7.)
    design = pd.DataFrame({'const': np.ones(len(x)), 'x': x})
    response = pd.Series(1 + 2*x, name='y')
    model = sm.OLS(response, design)
    fit = model.fit()
    viewer = SimpleNamespace(model=model, sub=[0, 1, 2, 3], X=design, y=response)
    axis = Figure().add_subplot(111)

    StatsViewer.plotRegression(viewer, fit, 'x', axis, marker='', colormap='viridis')

    assert len(axis.collections) == 3
    assert any(text.get_text().startswith('x: ') for text in axis.texts)
