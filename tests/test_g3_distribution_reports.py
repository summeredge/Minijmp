"""分布拟合呈现契约；代表值在 G3 修改前以 SciPy 1.15.3 实际计算。"""
import ast
import inspect
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest
from matplotlib.figure import Figure
from scipy import stats

import basic_dialogs
import dist_fit
import sb_hist_dialog
from test_g1_text_output import viewer


DATA = [1., 2., 3., 4., 2., 12., 3., 12., 3., 2., 40., 3., 2.]
# 名称、函数、表内参数顺序、原始 fits、ABL、AD 统计量及 p 值。
CASES = [
    ('Normal', 'fit_norm', ['总体均值 mu', '总体标准差 sigma'],
     (6.846153846153846, 10.59753236879663),
     (97.26855250745247, 102.46855250745247, 102.39845122237554),
     (2.4640161940626157, 1.188665222608914e-6)),
    ("Student's t", 'fit_t', ['位置 loc', '尺度 scale', '自由度 df'],
     (2.5817802627945747, .7843199376161987, .7427137276103728),
     (69.78246880323393, 78.4491354699006, 77.47731687561854),
     (1.246668065280291, .00304388623514128)),
    ('Gamma', 'fit_gamma', ['形状 shape', '尺度 scale'],
     (.9664322484856769, 7.08394598470946),
     (76.00593557093752, 81.20593557093753, 81.1358342858606),
     (1.4892588133109435, .0007714599668939043)),
    ('Lognormal', 'fit_lognorm', ['对数均值 mu', '对数标准差 sigma'],
     (3.7584322754649038, .9543430894024632),
     (70.10141881485742, 75.30141881485743, 75.2313175297805),
     (.9838428413660552, .013500143390714228)),
    ('Exponential', 'fit_expon', ['尺度 scale (均值)'],
     (6.846153846153846,),
     (76.01586231903566, 78.37949868267202, 78.5808116764972),
     (1.5326237776493201, .0006037448134309269)),
    ('Weibull', 'fit_weibull', ['尺度 scale', '形状 shape'],
     (6.346110156213206, .8881557995025409),
     (75.6042544843507, 80.80425448435071, 80.73415319927378),
     (1.2945953007205286, .002320502783517517)),
]
ORDER = ['Lognormal', 'Exponential', "Student's t", 'Weibull', 'Gamma', 'Normal']
WEIGHTS = [.6502410461311354, .13953328855655106, .1347585699731787,
           .04150962381880772, .033956651534672116, 8.199856548451121e-7]


@pytest.fixture
def tables(monkeypatch):
    captured = []
    original = dist_fit.gen_table
    def capture(rows):
        table = original(rows)
        captured.append(table)
        return table
    monkeypatch.setattr(dist_fit, 'gen_table', capture)
    return captured


def formatted(values):
    return ['%.3f' % value for value in values]


def reference_rv(name, fits):
    if name == 'Normal':
        return stats.norm(*fits)
    if name == "Student's t":
        return stats.t(fits[2], loc=fits[0], scale=fits[1])
    if name == 'Gamma':
        return stats.gamma(fits[0], loc=0, scale=fits[1])
    if name == 'Lognormal':
        return stats.lognorm(fits[1], loc=0, scale=fits[0])
    if name == 'Exponential':
        return stats.expon(loc=0, scale=fits[0])
    return stats.weibull_min(fits[1], loc=0, scale=fits[0])


@pytest.mark.parametrize('case', CASES, ids=[case[0] for case in CASES])
@pytest.mark.parametrize('print_out', [False, True])
def test_all_fits_values_fields_parameter_order_and_output_switch(case, print_out, tables, capsys):
    name, function, labels, fits, abl, gof = case
    lines = []
    result = getattr(dist_fit, function)(DATA, print_out=print_out, print_port=lines.append)
    assert type(result) is dict and list(result) == ['fits', 'ABL', 'rv']
    assert type(result['fits']) is tuple and type(result['ABL']) is tuple
    expected_types = {
        'fit_norm': [float, float],
        'fit_t': [np.float64, np.float64, np.float64],
        'fit_gamma': [float, np.float64],
        'fit_lognorm': [np.float64, np.float64],
        'fit_expon': [float],
        'fit_weibull': [np.float64, np.float64],
    }
    assert [type(x) for x in result['fits']] == expected_types[function]
    assert all(type(x) is float for x in result['ABL'])
    assert result['fits'] == pytest.approx(fits, rel=2e-6)
    assert result['ABL'] == pytest.approx(abl, rel=2e-6)
    reference = reference_rv(name, fits)
    assert type(result['rv']) is type(reference)
    assert result['rv'].dist.name == reference.dist.name
    assert result['rv'].args == pytest.approx(reference.args, rel=2e-6)
    assert result['rv'].kwds == pytest.approx(reference.kwds, rel=2e-6)
    np.testing.assert_allclose(result['rv'].pdf(DATA), reference.pdf(DATA), rtol=2e-6)
    assert dist_fit.goodness_of_fit(result['rv'], DATA, normal=name == 'Normal') == pytest.approx(gof, rel=2e-6)
    silent = getattr(dist_fit, function)(DATA, print_out=False, print_port=lines.append)
    for key in ['fits', 'ABL']:
        assert result[key] == silent[key]
        assert [type(x) for x in result[key]] == [type(x) for x in silent[key]]
    if not print_out:
        assert tables == [] and lines == []
    else:
        assert len(tables) == 3
        assert tables[0].field_names == ['参数', '估计值']
        displayed = (np.log(fits[0]), fits[1]) if name == 'Lognormal' else fits
        assert tables[0].rows == [list(row) for row in zip(labels, formatted(displayed))]
        assert tables[1].field_names == ['-2*LogLikelihood', 'AICc', 'BIC']
        assert tables[1].rows == [formatted(abl)]
        assert tables[2].field_names == ['拟合优度方法', 'AD 统计量', '近似 p 值']
        assert tables[2].rows == [['Anderson-Darling', *formatted(gof)]]
        text = '\n'.join(lines)
        assert '样本量 N = 13' in text
        assert name in text
        assert text.index('---- 分布拟合 ----') < text.index('样本量 N') < text.index('候选分布') < text.index('参数置信区间')
        assert '参数置信区间：现有方法未计算' in text
        assert 'p = 0.000' in text and '不代表概率严格为零' in text
        assert '未拒绝 H0 不等于证明' in text
        assert '未进行分布专用校准' in text
        for table in tables:
            for column in table.field_names:
                assert table.align[column] == ('l' if column in ['参数', '拟合优度方法'] else 'r')
        if name == "Student's t":
            assert '并非标准差' in text
        if name == 'Lognormal':
            assert 'ln(X)' in text and 'SciPy scale = exp(mu)' in text
        if name in ['Gamma', 'Lognormal', 'Exponential', 'Weibull']:
            assert '位置固定为 0' in text
    assert capsys.readouterr().out == ''


@pytest.mark.parametrize('print_out', [False, True])
def test_comparison_actual_order_weights_fields_and_selection(print_out, tables):
    lines = []
    result = dist_fit.compare_dist(DATA, print_out=print_out, print_port=lines.append)
    assert type(result) is list
    assert [row[0] for row in result] == ORDER
    assert [row[-1] for row in result] == pytest.approx(WEIGHTS, rel=2e-6)
    for row in result:
        assert type(row) is list and len(row) == 4
        assert row[1] is row[2]['ABL']
        assert type(row[-1]) is float
    if print_out:
        comparison = tables[-1]
        assert comparison.field_names == ['分布', 'AICc', 'AICc 权重', 'BIC', '-2*LogLikelihood']
        expected = {case[0]: case[4] for case in CASES}
        assert comparison.rows == [[name, *formatted([expected[name][1], weight, expected[name][2], expected[name][0]])]
                                   for name, weight in zip(ORDER, WEIGHTS)]
        assert comparison.align['分布'] == 'l'
        assert all(comparison.align[column] == 'r' for column in comparison.field_names[1:])
        assert '不是模型为真或必为最佳模型的概率' in '\n'.join(lines)
        assert 'AD 用于检验分布相容性，不参与此处排序' in '\n'.join(lines)
    else:
        assert lines == [] and tables == []


@pytest.mark.parametrize('selected', [['Gamma'], ['Weibull', 'Normal'], [], ['Unknown']])
def test_selected_models_and_single_model_comparison_gate(selected, tables):
    lines = []
    result = dist_fit.compare_dist(DATA, selected=selected, print_port=lines.append)
    assert {row[0] for row in result} == set(selected) - {'Unknown'}
    assert ('---- 分布比较 ----' in '\n'.join(lines)) == (len(selected) > 1)
    if len(selected) == 1 and selected != ['Unknown']:
        assert result[0][-1] == 1.
        assert len(tables) == 3


def test_small_sample_missing_aicc_and_weights_preserve_nan_order(tables):
    result = dist_fit.compare_dist([1., 2., 3.], print_port=lambda line: None)
    assert [row[0] for row in result] == [case[0] for case in CASES]
    assert all(np.isnan(row[-1]) for row in result)
    comparison = tables[-1]
    assert [row[2] for row in comparison.rows] == ['*'] * 6
    assert [row[1] for row in comparison.rows] == ['*', '*', '*', '*', '16.159', '*']
    assert tables[1].rows == [['7.514', '*', '9.711']]
    lines = []
    dist_fit.compare_dist([1., 2., 3.], print_port=lines.append, selected=['Normal', 'Exponential'])
    assert 'AICc 或权重为 * 时，现有排序不提供有效的优劣结论。' in lines


@pytest.mark.parametrize('print_out', [False, True])
def test_failed_candidates_are_reported_and_excluded_without_altering_valid_fits(print_out, tables):
    lines = []
    result = dist_fit.compare_dist([-2., -1., 0., 1., 2.], print_out=print_out, print_port=lines.append)
    assert [row[0] for row in result] == ['Normal', "Student's t"]
    assert result[0][1] == pytest.approx((17.770838991417502, 27.770838991417502, 20.9897148162857))
    assert result[0][-1] == pytest.approx(.999951898116555)
    if print_out:
        assert sum('拟合失败' in line for line in lines) == 4
        assert [row[0] for row in tables[-1].rows] == ['Normal', "Student's t"]
    else:
        assert lines == [] and tables == []


def test_all_failed_candidates_explain_no_comparison_without_building_empty_table(tables):
    for print_out in [True, False]:
        lines = []
        result = dist_fit.compare_dist([-2., -1., 0.], selected=['Gamma', 'Lognormal'],
            print_out=print_out, print_port=lines.append)
        assert type(result) is list and result == []
        assert tables == []
        if print_out:
            assert sum('拟合失败' in line for line in lines) == 2
            assert '无法比较：没有成功拟合的候选分布。' in lines
            assert not any('排序沿用' in line for line in lines)
        else:
            assert lines == []


def test_shared_table_missing_cells_are_not_invented(tables):
    lines = []
    assert dist_fit.print_table('测试 Distribution', ['参数 shape'], [None],
        (np.nan, None, 1.23456), np.nan, None, print_port=lines.append) is None
    assert tables[0].rows == [['参数 shape', '*']]
    assert tables[1].rows == [['*', '*', '1.235']]
    assert tables[2].rows == [['Anderson-Darling', '*', '*']]
    assert '* 表示不可用或未计算' in '\n'.join(lines)


def variable(value):
    return SimpleNamespace(get=lambda: value)


def test_fit_dialog_apply_cleans_selected_data_and_routes_actual_reports(monkeypatch, tables):
    lines = []
    calls = Mock(wraps=dist_fit.compare_dist)
    monkeypatch.setattr(basic_dialogs, 'compare_dist', calls)
    column = '很长的中文测量变量名称 Mixed ASCII'
    frame = pd.DataFrame({column: [*DATA, 'bad', None, np.nan, '5']})
    original = frame.copy(deep=True)
    selected = ['Gamma', 'Lognormal', 'Weibull']
    dialog = SimpleNamespace(remember_columns=Mock(), df=frame, xvar=variable(column), dists=[case[0] for case in CASES],
        picks={case[0]: variable(case[0] in selected) for case in CASES},
        app=SimpleNamespace(print=lines.append))
    assert basic_dialogs.FitDistDialog.apply(dialog) is None
    from stat_table import StatTable
    assert sum(isinstance(line, StatTable) for line in lines) == 10
    assert calls.call_args.args == ([*DATA, 5.],)
    assert calls.call_args.kwargs == dict(print_out=True, print_port=lines.append, selected=selected)
    pd.testing.assert_frame_equal(frame, original)
    expected = dist_fit.compare_dist([*DATA, 5.], selected=selected, print_out=False)
    assert tables[-1].rows == [[r[0], *formatted([r[1][1], r[-1], r[1][2], r[1][0]])] for r in expected]
    assert '样本量 N = 14' in lines
    assert column in '\n'.join(lines)


@pytest.mark.parametrize('fit_enabled, distribution, failed', [
    (False, 'Lognormal', False), (True, 'Lognormal', False), (True, 'Gamma', True)])
def test_histogram_apply_uses_same_frozen_rv_and_curve_without_changing_source(monkeypatch, fit_enabled, distribution, failed):
    comparison = Mock(wraps=dist_fit.compare_dist)
    plotting = Mock(wraps=sb_hist_dialog.histo_n_fit)
    monkeypatch.setattr(sb_hist_dialog, 'compare_dist', comparison)
    monkeypatch.setattr(sb_hist_dialog, 'histo_n_fit', plotting)
    dialog = object.__new__(sb_hist_dialog.singleHistoDialog)
    values = [-x for x in DATA] if failed else DATA
    dialog.df = pd.DataFrame({'测量 Column': [*values, 'bad', None, '5']})
    original = dialog.df.copy(deep=True)
    dialog.xvar, dialog.dist = variable('测量 Column'), variable(distribution)
    dialog.stat, dialog.fit_dist = variable('density'), variable(fit_enabled)
    dialog.get_x_plot_settings, dialog.get_misc_plot_settings, dialog.get_histo_setting = Mock(), Mock(), Mock()
    lines = []
    dialog.app = SimpleNamespace(print=lines.append)
    dialog.error = Mock()
    figure = Figure()
    dialog.showPlotViewer = Mock(return_value=SimpleNamespace(fig=figure))
    dialog.xlabel_v, dialog.x_min_v, dialog.x_max_v = '', None, None
    dialog.bins_v, dialog.binwidth_v = 'auto', None
    dialog.ax_margin_v, dialog.show_legend_v, dialog.grid_v = .1, False, False
    assert dialog.apply() is None
    pd.testing.assert_frame_equal(dialog.df, original)
    assert dialog.working_df['测量 Column'].dropna().tolist() == [*values, 5.]
    if failed:
        dialog.error.assert_called_once_with(
            '无法使用所选分布进行拟合。', preview_failed=False)
    else:
        dialog.error.assert_not_called()
    assert plotting.call_args.kwargs['fig'] is figure
    rv = plotting.call_args.kwargs['rv']
    if fit_enabled:
        assert comparison.call_args.args == ([*values, 5.],)
        assert comparison.call_args.kwargs == dict(print_out=True, print_port=lines.append, selected=[distribution])
        if failed:
            assert rv is None and len(figure.axes) == 1
            assert any('拟合失败' in line for line in lines)
            return
        from stat_table import StatTable
        assert sum(isinstance(line, StatTable) for line in lines) == 3
        expected = dist_fit.fit_lognorm([*DATA, 5.], print_out=False)['rv']
        np.testing.assert_array_equal(rv.pdf(DATA), expected.pdf(DATA))
        assert len(figure.axes) == 2
        curve = figure.axes[1].lines[0]
        assert len(curve.get_xdata()) == 100
        np.testing.assert_array_equal(curve.get_ydata(), rv.pdf(curve.get_xdata()))
        assert '样本量 N = 14' in lines
        assert '---- 分布比较 ----' not in '\n'.join(lines)
    else:
        comparison.assert_not_called()
        assert rv is None and len(figure.axes) == 1
        assert not any('分布拟合' in line for line in lines)


def test_histogram_empty_input_protection_prevents_fit_and_plot(monkeypatch):
    comparison = Mock()
    monkeypatch.setattr(sb_hist_dialog, 'compare_dist', comparison)
    dialog = SimpleNamespace(df=pd.DataFrame({'X': ['bad', None, np.nan]}),
        xvar=variable('X'), get_x_plot_settings=Mock(), get_misc_plot_settings=Mock(),
        get_histo_setting=Mock(), error=Mock(), app=SimpleNamespace(print=Mock()),
        showPlotViewer=Mock())
    assert sb_hist_dialog.singleHistoDialog.apply(dialog) is None
    dialog.error.assert_called_once_with('没有可供绘图的数值观测值。')
    comparison.assert_not_called()
    dialog.showPlotViewer.assert_not_called()


def test_actual_report_tables_align_in_text_viewer_font(viewer, tables):
    dist_fit.compare_dist(DATA, print_port=lambda line: None)
    for table in tables:
        positions = []
        for line in str(table).splitlines():
            if '|' in line:
                positions.append([viewer.output_font.measure(line[:i])
                                  for i, char in enumerate(line) if char == '|'])
                assert not any(char in line for char in 'μσχαβΔ')
        assert positions and all(row == positions[0] for row in positions)


def test_scoped_source_legacy_report_patterns_and_public_contracts():
    for _, function, *_ in CASES:
        signature = inspect.signature(getattr(dist_fit, function))
        assert list(signature.parameters) == ['data', 'print_out', 'print_port']
        assert signature.parameters['print_out'].default is True
        assert signature.parameters['print_port'].default is print
    signature = inspect.signature(dist_fit.compare_dist)
    assert list(signature.parameters) == ['data', 'print_out', 'print_port', 'selected']
    assert signature.parameters['print_out'].default is True
    assert signature.parameters['print_port'].default is print
    assert signature.parameters['selected'].default == [case[0] for case in CASES]
    assert list(inspect.signature(dist_fit.print_table).parameters) == ['fit_name', 'para_names', 'paras', 'abl', 'a2', 'p', 'print_port']
    source = Path(dist_fit.__file__).read_bytes().decode('utf-8')
    tree = ast.parse(source)
    functions = {node.name: ast.get_source_segment(source, node) for node in tree.body if isinstance(node, ast.FunctionDef)}
    for name in ['print_table', 'compare_dist']:
        for legacy in ['PT()', '%.2f', 'probability that a given model is the best', 'A-sq', 'Approx. p-value']:
            assert legacy not in functions[name]
        assert 'gen_table(' in functions[name] and 'format_stat(' in functions[name]
    assert 'Stundent' not in functions['fit_t']
    assert 'Scale mu' not in functions['fit_lognorm']
    assert 'except BaseException:' in functions['compare_dist']
    assert 'if print_out and len(selected) > 1:' in functions['compare_dist']
    assert 'res.sort(key=lambda x: -x[-1])' in functions['compare_dist']
    for name in ['fit_gamma', 'fit_weibull', 'fit_lognorm', 'fit_expon']:
        assert 'floc=0' in functions[name]
    assert 'print(johnsonsu.fit(data))' in functions['fit_jsu']
