"""G2 的报告入口、列对应、原始数值和文本窗口回归。"""
import ast
import importlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest
from matplotlib.figure import Figure
from scipy import stats
from statsmodels.stats.diagnostic import normal_ad
from wcwidth import wcswidth

import basic_dialogs
import describe as description
import fit_dialog
import linear_plot
import nonpara_cor
import sample_test_dialog
import utilities
from pandastable_local.app import DataExplore
from pandastable_local.core_orig import Table
from test_g1_text_output import viewer  # 复用真实 Tk 窗口及生命周期 fixture。


DATA = [1., 2., 4., 5., 7., 8.]
OTHER = [2., 4., 3., 8., 6., 10.]
ROOT = Path(__file__).resolve().parents[1]


def capture_tables(monkeypatch, module):
    tables = []
    original = module.gen_table
    def capture(rows):
        table = original(rows)
        tables.append(table)
        return table
    monkeypatch.setattr(module, 'gen_table', capture)
    return tables


def variable(value):
    return SimpleNamespace(get=lambda: value)


def test_describe_core_supplement_and_custom_percentiles(monkeypatch):
    tables = capture_tables(monkeypatch, description)
    lines = []
    result = description.describe([1, 'bad', None, np.nan, 2, 4, 5],
        print_out=True, print_port=lines.append, percentiles=[90, 33, 0])
    assert tables[0].field_names == ['变量', 'N', 'N*', '均值', '均值标准误',
        '标准差', '最小值', 'Q1', '中位数', 'Q3', '最大值']
    assert tables[0].rows[0] == ['数据', '4', 3, '3.000',
        utilities.format_stat(result['SEM']), utilities.format_stat(result['stdev']),
        '1.000', utilities.format_stat(result['Q1']), '3.000',
        utilities.format_stat(result['Q3']), '5.000']
    assert tables[1].field_names == ['变量', '方差', '变异系数 (%)', '总和',
        '极差', '四分位距', '偏度', '峰度', '众数', '众数频数']
    assert tables[2].rows == [['90.00%', utilities.format_stat(result['quantiles'][0])],
        ['33.00%', utilities.format_stat(result['quantiles'][1])], ['0.00%', '1.000']]
    assert result['mean'] == np.mean([1, 2, 4, 5])
    assert result['stdev'] == np.std([1, 2, 4, 5], ddof=1)
    assert result['quantiles'] == utilities.quantiles([1, 2, 4, 5], percentiles=[90, 33, 0])
    for table in tables:
        assert all(table.align[name] == 'r' for name in table.field_names if name != '变量')
        assert len({wcswidth(line) for line in str(table).splitlines()}) == 1


def test_generator_has_no_invented_missing_count(monkeypatch):
    tables = capture_tables(monkeypatch, description)
    result = description.describe((x for x in [1, 'bad', 3, 4]), print_out=True,
                                  print_port=lambda line: None)
    assert result['N'] == 3
    assert 'N*' not in tables[0].field_names


@pytest.mark.parametrize('data', [[], [None, 'bad', np.nan], [1]])
def test_insufficient_description_keeps_no_result_and_dialog_error(data):
    lines = []
    assert description.describe(data, print_out=True, print_port=lines.append) is None
    assert lines == []
    single = SimpleNamespace(df=pd.DataFrame({'测量': data}), xvar=variable('测量'),
        pct=variable('100,50,0'), error=Mock(), app=SimpleNamespace(print=lines.append))
    basic_dialogs.DescribeDialog.apply(single)
    single.error.assert_called_once()
    assert lines == []
    multi = SimpleNamespace(df=single.df, grpcols=['测量'], error=Mock(),
                            app=single.app)
    basic_dialogs.MultiDescribeDialog.apply(multi)
    multi.error.assert_called_once()


@pytest.mark.parametrize('multiple', [False, True])
def test_dialog_rows_bind_original_columns_and_cleaning_counts(monkeypatch, multiple):
    tables = capture_tables(monkeypatch, description)
    df = pd.DataFrame({'温度': [1, 'bad', None, 4, 7],
                       '压力': [10, 20, 30, np.nan, 50]})
    lines = []
    dialog = SimpleNamespace(remember_columns=Mock(), df=df, error=Mock(), app=SimpleNamespace(print=lines.append),
        xvar=variable('温度'), pct=variable('0,50,100'), grpcols=['压力', '温度'],
        names=list(description.STAT_LABELS),
        picks={key: variable(True) for key in description.STAT_LABELS})
    if multiple:
        basic_dialogs.MultiDescribeDialog.apply(dialog)
        assert [row[:3] for row in tables[0].rows] == [['压力', '4', 1], ['温度', '3', 2]]
        assert [row[3] for row in tables[0].rows] == ['27.500', '4.000']
    else:
        basic_dialogs.DescribeDialog.apply(dialog)
        assert tables[0].rows[0][:4] == ['温度', '3', 2, '4.000']
        assert tables[-1].rows == [['0.00%', '1.000'], ['50.00%', '4.000'], ['100.00%', '7.000']]
    assert tables[0].field_names == ['变量', 'N', 'N*', '均值', '均值标准误',
        '标准差', '最小值', 'Q1', '中位数', 'Q3', '最大值']
    dialog.error.assert_not_called()


def test_multidescribe_selected_statistics_still_control_columns(monkeypatch):
    tables = capture_tables(monkeypatch, description)
    dialog = SimpleNamespace(remember_columns=Mock(), df=pd.DataFrame({'X': DATA}), grpcols=['X'], error=Mock(),
        names=list(description.STAT_LABELS),
        picks={key: variable(key in ['Mean', 'Variance']) for key in description.STAT_LABELS},
        app=SimpleNamespace(print=lambda line: None))
    basic_dialogs.MultiDescribeDialog.apply(dialog)
    assert [t.field_names for t in tables] == [['变量', '均值'], ['变量', '方差']]


@pytest.mark.parametrize('entry', ['table', 'application'])
def test_dataframe_child_table_entry_preserves_pandas_statistics(entry):
    # 这两条入口输出 DataFrame 子表，不经过文本报告；不得用另一套分位数替换。
    df = pd.DataFrame({'温度': DATA, '压力': OTHER, '标签': ['A'] * 6})
    child = Mock()
    table = SimpleNamespace(model=SimpleNamespace(df=df), createChildTable=child)
    if entry == 'table':
        assert Table.describe(table) is None
    else:
        assert DataExplore.describe(SimpleNamespace(getCurrentTable=lambda: table)) is None
        assert child.call_args.kwargs == {'index': True}
    pd.testing.assert_frame_equal(child.call_args.args[0], df.describe())


@pytest.mark.parametrize('dialog', [False, True])
def test_normality_table_direct_and_dialog(monkeypatch, dialog):
    tables = capture_tables(monkeypatch, utilities)
    lines = []
    if dialog:
        basic_dialogs.NormTestDialog.apply(SimpleNamespace(remember_columns=Mock(),
            df=pd.DataFrame({'测量': DATA}), xvar=variable('测量'), qq=variable(False),
            app=SimpleNamespace(print=lines.append)))
    else:
        result = utilities.norm_test(DATA, print_out=True, print_port=lines.append)
        assert result == {'shapiro s': stats.shapiro(DATA).statistic,
            'shapiro p': stats.shapiro(DATA).pvalue,
            'AD s': normal_ad(np.array(DATA))[0], 'AD p': normal_ad(np.array(DATA))[1]}
    assert tables[0].field_names == ['检验方法', '统计量', 'p 值']
    assert tables[0].rows == [['Shapiro-Wilk', utilities.format_stat(stats.shapiro(DATA).statistic),
        utilities.format_stat(stats.shapiro(DATA).pvalue)], ['Anderson-Darling',
        utilities.format_stat(normal_ad(np.array(DATA))[0]), utilities.format_stat(normal_ad(np.array(DATA))[1])]]
    assert '未拒绝 H0 不代表证明数据正态' in '\n'.join(lines)


def test_normality_keeps_small_sample_warning_and_missing_marker():
    lines = []
    with pytest.warns():
        result = utilities.norm_test([1., 2.], print_out=True, print_port=lines.append)
    assert np.isnan(result['shapiro p'])
    assert '| Shapiro-Wilk' in '\n'.join(lines) and '*' in '\n'.join(lines)


@pytest.mark.parametrize('alpha', [.05, .1])
@pytest.mark.parametrize('dialog', [False, True])
def test_mean_sd_interval_rows_match_parameter_tail_and_level(monkeypatch, alpha, dialog):
    tables = capture_tables(monkeypatch, utilities)
    lines = []
    if dialog:
        basic_dialogs.CIDialog.apply(SimpleNamespace(remember_columns=Mock(), df=pd.DataFrame({'测量': DATA}),
            xvar=variable('测量'), alpha=variable(alpha), app=SimpleNamespace(print=lines.append)))
    else:
        result = utilities.mean_std_CIs(DATA, alpha=alpha, print_out=True, print_port=lines.append)
        mean, sd = np.mean(DATA), np.std(DATA, ddof=1)
        np.testing.assert_allclose(result['mean 2side'], stats.t.interval(1-alpha, 5,
            loc=mean, scale=sd/np.sqrt(6)), rtol=1e-14)
    table = tables[0]
    result = utilities.mean_std_CIs(DATA, alpha=alpha)
    assert table.field_names == ['参数', '点估计', '双侧下限', '双侧上限', '单侧置信下限', '单侧置信上限']
    for row, key in zip(table.rows, ['mean', 'std']):
        assert row[2:] == list(map(utilities.format_stat, [*result[key+' 2side'], *result[key+' 1side']]))
    assert f'置信水平 = {1-alpha:.1%}' in '\n'.join(lines)


@pytest.mark.parametrize('method,reference', [(nonpara_cor.spearman, stats.spearmanr),
                                             (nonpara_cor.kendall, stats.kendalltau)])
def test_rank_single_reports_keep_raw_coefficients_and_p_values(monkeypatch, method, reference):
    tables = capture_tables(monkeypatch, nonpara_cor)
    lines = []
    result = method(DATA, OTHER, print_out=True, print_port=lines.append)
    assert result['cor'] == reference(DATA, OTHER).statistic
    assert result['p'] == reference(DATA, OTHER).pvalue
    assert tables[0].field_names == ['变量组合', '方法', 'N', '相关系数', 'p 值']
    assert tables[0].rows[0][2:] == [6, utilities.format_stat(result['cor']), utilities.format_stat(result['p'])]
    assert '不等同于变量独立' in '\n'.join(lines)


def test_pearson_and_hoeffding_single_reports_keep_additional_metrics(monkeypatch):
    tables = capture_tables(monkeypatch, utilities)
    lines = []
    result = utilities.pearson_correlation(DATA, OTHER, print_port=lines.append)
    assert result['r'] == pytest.approx(stats.pearsonr(DATA, OTHER).statistic)
    assert tables[0].rows[0][2:] == [6, utilities.format_stat(result['r']), utilities.format_stat(result['p'])]
    assert tables[1].rows == [[utilities.format_stat(result[key]) for key in ['cov', 'r_l', 'r_u']]]
    tables = capture_tables(monkeypatch, nonpara_cor)
    result = nonpara_cor.hoeffding(DATA, OTHER, print_out=True, print_port=lines.append)
    assert result['cor'] == nonpara_cor.hoeffd_example(DATA, OTHER)
    assert result['p'] == nonpara_cor.phoeffd(result['cor'], len(DATA))
    assert tables[0].rows[0][1] == "Hoeffding's D"
    assert 'H0：两变量独立' in '\n'.join(lines)


@pytest.mark.parametrize('function', [linear_plot.multi_fit, linear_plot.multi_fit_orig])
def test_both_pearson_matrix_implementations_preserve_cell_mapping(monkeypatch, function):
    tables = capture_tables(monkeypatch, linear_plot)
    data = [DATA, OTHER, [4., 5., 1., 8., 9., 7.]]
    labels = ['温度', '压力', '流量']
    figure = Figure()
    options = {'fig': figure, 'ellipse': False, 'print_out': True, 'print_port': lambda line: None}
    options.update({'ax': figure.subplots()} if function is linear_plot.multi_fit
                   else {'axs': figure.subplots(2, 2)})
    result = function(data, labels, **options)
    for row in range(3):
        assert tables[0].rows[row][0] == labels[row]
        for column in range(3):
            expected = utilities.pearson_correlation(data[column], data[row], print_out=False)
            assert result['pearson'][row][column] == expected
            assert tables[0].rows[row][column+1] == utilities.format_stat(expected['r'])
            assert tables[1].rows[row][column+1] == utilities.format_stat(expected['p'])
    assert tables[0].field_names == ['\\'] + labels
    assert all(tables[0].align[label] == 'r' for label in labels)


@pytest.mark.parametrize('method', [nonpara_cor.spearman, nonpara_cor.kendall, nonpara_cor.hoeffding])
def test_rank_and_hoeffding_matrices_preserve_method_and_variable_mapping(monkeypatch, method):
    tables = capture_tables(monkeypatch, fit_dialog)
    lines = []
    assert fit_dialog.print_multi_col_tables([DATA, OTHER], ['温度', '压力'], method,
        name=method.__name__, print_port=lines.append) is None
    for row, y in enumerate([DATA, OTHER]):
        for column, x in enumerate([DATA, OTHER]):
            expected = method(x, y)
            assert tables[0].rows[row][column+1] == utilities.format_stat(expected['cor'])
            assert tables[1].rows[row][column+1] == utilities.format_stat(expected['p'])
    assert method.__name__ in lines[0] and 'p 值矩阵' in lines[2]


@pytest.mark.parametrize('name,title', [
    ('Mean1SampleDialog', '单样本 t 检验'), ('Mean1SampleZDialog', '单样本 Z 检验'),
    ('Var1SampleDialog', '单样本标准差检验'), ('Mean2SampleDialog', '两独立样本 t 检验'),
    ('Prop1SDialog', '单比例检验'), ('Prop2SDialog', '两比例检验')])
@pytest.mark.parametrize('summarized', [False, True])
def test_hypothesis_dialog_raw_and_summary_routes_reach_g2_reports(monkeypatch, name, title, summarized):
    tables = capture_tables(monkeypatch, utilities)
    lines = []
    fields = dict(xvar='X', yvar='Y', u0=3, s0=2, d0=1, alpha=.05, pooled=False,
        sample_mean=30 if summarized else '', sample_std=4 if summarized else '',
        sample_n=20 if summarized else '',
        u1=30 if summarized else '', s1=4 if summarized else '', n1=20 if summarized else '',
        u2=35 if summarized else '', s2=6 if summarized else '', n2=25 if summarized else '',
        event_name='1', event_name2='2', p0=.4,
        event_cnt=3 if summarized else '', ttl_cnt=20 if summarized else '',
        event_cnt2=8 if summarized else '', ttl_cnt2=25 if summarized else '')
    dialog = SimpleNamespace(remember_columns=Mock(), **{key: variable(value) for key, value in fields.items()},
        df=pd.DataFrame({'X': DATA, 'Y': OTHER}), error=Mock(),
        app=SimpleNamespace(print=lines.append))
    getattr(sample_test_dialog, name).apply(dialog)
    assert f'---- {title} ----' in '\n'.join(lines)
    assert '检验结果' in '\n'.join(lines) and '置信区间' in '\n'.join(lines)
    sample_rows = tables[0].rows
    assert sample_rows[0][1] == (20.0 if summarized else 6)
    if name in ['Mean1SampleDialog', 'Mean1SampleZDialog', 'Mean2SampleDialog']:
        assert sample_rows[0][2] == ('30.000' if summarized else '4.500')
    elif name in ['Prop1SDialog', 'Prop2SDialog']:
        assert sample_rows[0][2] == (3.0 if summarized else 1)
    dialog.error.assert_not_called()


def test_paired_dialog_cleans_pairs_and_labels_difference(monkeypatch):
    tables = capture_tables(monkeypatch, utilities)
    lines = []
    dialog = SimpleNamespace(remember_columns=Mock(), df=pd.DataFrame({'X': [1, 'bad', 4, 5, 7],
        'Y': [2, 4, 3, 8, 6]}), xvar=variable('X'), yvar=variable('Y'),
        d0=variable(0), alpha=variable(.05), error=Mock(), app=SimpleNamespace(print=lines.append))
    sample_test_dialog.PairedTDialog.apply(dialog)
    assert tables[0].rows[0][1:3] == [4, '-0.500']
    assert '差值 = 样本 1 - 样本 2' in '\n'.join(lines)
    dialog.error.assert_not_called()


def test_multi_correlation_dialog_reaches_all_four_matrix_reports():
    lines = []
    flags = dict(cor_p=True, cor_s=True, cor_k=True, cor_h=True, ellipse=False,
        red_ellipse=False, alpha=.05, ax_margin=.1, ylabel_0deg=False,
        xlabel_45deg=False, xtick_45deg=False)
    dialog = SimpleNamespace(remember_columns=Mock(), df=pd.DataFrame({'温度': DATA, '压力': OTHER}),
        grpcols=['温度', '压力'], **{key: variable(value) for key, value in flags.items()},
        app=SimpleNamespace(print=lines.append,
                            showPlotViewer=lambda **kwargs: SimpleNamespace(fig=Figure())))
    fit_dialog.MCorDialog.apply(dialog)
    text = '\n'.join(lines)
    for method in ['Pearson', "Spearman's rho", "Kendall's tau", "Hoeffding's D"]:
        assert f'{method} 相关系数矩阵' in text and f'{method} p 值矩阵' in text


def test_actual_wide_g2_report_renders_scrolls_and_saves(viewer, tmp_path, monkeypatch):
    lines = []
    description.describe(DATA, print_out=True, print_port=lines.append)
    content = '\n'.join(lines)
    viewer.main.geometry('480x320')
    viewer.add_txt(content)
    viewer.main.update()
    assert viewer.T.xview()[1] < 1
    core_table = lines[1]
    positions = [[viewer.output_font.measure(line[:index])
                  for index, char in enumerate(line) if char == '|']
                 for line in core_table.splitlines() if '|' in line]
    assert positions and all(row == positions[0] for row in positions)
    viewer.hsb.tk.call(viewer.hsb.cget('command'), 'moveto', .5)
    viewer.main.update()
    assert viewer.T.xview()[0] > 0
    assert viewer.T.get('1.0', 'end-1c') == content
    target = tmp_path / 'G2统计结果.txt'
    viewer.save(target)
    assert target.read_text(encoding='utf-8') == content
    viewer.select_all()
    assert viewer.T.get('sel.first', 'sel.last') == content
    viewer.clear()
    assert viewer.T.get('1.0', 'end-1c') == ''


@pytest.mark.parametrize('module,name,args,options', [
    ('describe', 'describe', [DATA], {}),
    ('utilities', 'norm_test', [DATA], {}),
    ('utilities', 'mean_std_CIs', [DATA], {}),
    ('utilities', 'pearson_correlation', [DATA, OTHER], {}),
    ('nonpara_cor', 'spearman', [DATA, OTHER], {}),
    ('nonpara_cor', 'kendall', [DATA, OTHER], {}),
    ('nonpara_cor', 'hoeffding', [DATA, OTHER], {}),
    ('t_test', 't_test_1sample', [DATA, 3], {}),
    ('t_test', 'z_test_1sample', [DATA, 3, 2], {}),
    ('t_test', 'paired_t_test', [DATA, OTHER], {}),
    ('t_test', 't_test_2samples', [DATA, OTHER], {}),
    ('chi_sq', 'chi2_test_stdev', [DATA, 2], {}),
    ('chi_sq', 'chi2_var_1sample', [DATA], {'s0': 2}),
    ('chi_sq', 'var_1sample', [DATA], {'s0': 2}),
    ('proportion_test', 'prop_test_1sample', [3, 20, .4], {}),
    ('proportion_test', 'prop_2sample', [], {'n1': 20, 'n2': 25, 'e1': 3, 'e2': 8}),
])
def test_each_g2_report_aligns_in_actual_g1_font(viewer, module, name, args, options):
    lines = []
    getattr(importlib.import_module(module), name)(*args, print_out=True,
        print_port=lines.append, **options)
    viewer.add_txt('\n'.join(lines))
    viewer.main.update()
    count = 0
    for chunk in lines:
        positions = [[viewer.output_font.measure(line[:index])
                      for index, char in enumerate(line) if char == '|']
                     for line in chunk.splitlines() if '|' in line]
        if positions:
            assert all(row == positions[0] for row in positions), (module, name, chunk)
            count += 1
    assert count > 0


@pytest.mark.parametrize('filename,function,old', [
    ('describe.py', 'describe', 'Descriptive Statistics'),
    ('utilities.py', 'norm_test', 'Normality Test'),
    ('utilities.py', 'pearson_correlation', 'Correlation coefficient:'),
    ('linear_plot.py', 'multi_fit', 'Pearson correlation coefficient'),
    ('linear_plot.py', 'multi_fit_orig', 'Pearson correlation coefficient'),
    ('fit_dialog.py', 'print_multi_col_tables', ' correlation p-value'),
])
def test_replaced_legacy_output_is_absent_in_each_function(filename, function, old):
    source = (ROOT / 'code' / filename).read_text(encoding='utf-8')
    node = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == function)
    assert old not in ast.get_source_segment(source, node)


def test_multi_description_has_no_legacy_transposed_report():
    source = (ROOT / 'code/basic_dialogs.py').read_text(encoding='utf-8')
    owner = next(n for n in ast.parse(source).body if isinstance(n, ast.ClassDef)
                 and n.name == 'MultiDescribeDialog')
    node = next(n for n in owner.body if isinstance(n, ast.FunctionDef) and n.name == 'apply')
    text = ast.get_source_segment(source, node)
    assert 'Statitstics' not in text and 't.field_names = [""] + self.grpcols' not in text
    assert 'print_descriptive' in text


@pytest.mark.parametrize('value,expected', [(None, '*'), (np.nan, '*'), (-1.25, '-1.250'), (0, '0.000')])
def test_missing_statistic_format(value, expected):
    assert utilities.format_stat(value) == expected
