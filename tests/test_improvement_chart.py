"""改善前后控制图的独立参考、模式语义、检验适用性与报告一致性。"""
from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

import control_chart
import improvement_chart as subject
from advanced_spc import nelson_events


def two_phase(before, after, stage=('改善前', '改善后')):
    return pd.DataFrame({'值': np.r_[before, after],
                         '阶段': [stage[0]] * len(before) + [stage[1]] * len(after)})


def test_phase_splits_follow_appearance_order_and_validate_continuity():
    df = two_phase([1., 2., 3., 4.], [5., 6., 7.], stage=('Z 后', 'A 前'))
    before, after, names, info = subject.split_phases(df, 'stage', '阶段')
    assert names == ['Z 后', 'A 前']
    assert before.tolist() == [True] * 4 + [False] * 3
    assert after.tolist() == [False] * 4 + [True] * 3
    assert '实际出现顺序' in info
    alternating = two_phase([1., 2.], [3., 4.])
    alternating['阶段'] = ['A', 'B', 'A', 'B']
    with pytest.raises(ValueError, match='恰好形成两个连续阶段'):
        subject.split_phases(alternating, 'stage', '阶段')
    three = two_phase([1., 2.], [3., 4.])
    three['阶段'] = ['A', 'A', 'B', 'C']
    with pytest.raises(ValueError, match='恰好形成两个连续阶段'):
        subject.split_phases(three, 'stage', '阶段')


def test_time_cutoff_requires_sorted_unique_boundary():
    df = pd.DataFrame({'值': [1., 2., 3., 4.],
                       '时间': pd.date_range('2026-01-01', periods=4, freq='h')})
    before, after, names, _ = subject.split_phases(
        df, 'time', time='时间', cutoff='2026-01-01 02:00')
    assert before.tolist() == [True, True, False, False]
    assert after.tolist() == [False, False, True, True]
    assert names == ['改善前', '改善后']
    with pytest.raises(ValueError, match='非递减'):
        subject.split_phases(df.sort_values('时间', ascending=False), 'time',
                             time='时间', cutoff='2026-01-01 02:00')
    with pytest.raises(ValueError, match='两个阶段'):
        subject.split_phases(df, 'time', time='时间', cutoff='2020-01-01')
    numeric = pd.DataFrame({'值': [1., 2., 3.], '时间': [1., 2., 3.]})
    before, _, _, _ = subject.split_phases(numeric, 'time', time='时间', cutoff='2')
    assert before.tolist() == [True, False, False]


def test_metrics_standardize_chart_limits_and_spc_sigma():
    before = np.arange(1., 13.) * .3 + 10
    after = np.arange(1., 13.) * .15 + 8
    df = two_phase(before, after)
    result = subject.analyze_improvement(df, '值', stage='阶段')
    metrics = result.tables['metrics'].set_index('指标')
    assert metrics.loc['均值', '改善前'] == pytest.approx(before.mean())
    assert metrics.loc['均值', '改善后'] == pytest.approx(after.mean())
    assert metrics.loc['均值', '差值'] == pytest.approx(after.mean() - before.mean())
    assert metrics.loc['标准差（整体）', '改善后'] == pytest.approx(after.std(ddof=1))
    ratios = result.tables['ratios'].set_index('指标')['数值']
    assert ratios.iloc[0] == pytest.approx(after.std(ddof=1) / before.std(ddof=1))
    assert ratios.iloc[1] == pytest.approx((after.std(ddof=1) / before.std(ddof=1) - 1) * 100)
    # I-MR 的 SPC 组内波动来自 MR 图中心线 / d2(2)。
    mr = control_chart.x_mR(list(after), 2)['bar2']
    assert metrics.loc['SPC 组内波动', '改善后'] == pytest.approx(mr / 1.128, rel=1e-12)
    independent = result.tables['limits'].set_index(['阶段', '图表'])
    assert independent.loc[('改善前', 'I'), 'CL'] != independent.loc[('改善后', 'I'), 'CL']
    assert independent.loc[('改善前', 'MR'), 'CL'] != independent.loc[('改善后', 'MR'), 'CL']


def test_baseline_mode_uses_only_before_parameters():
    rng = np.random.default_rng(410)
    before = rng.normal(10, 2, 40)
    after = rng.normal(12, 4, 40)
    df = two_phase(before, after)
    independent = subject.analyze_improvement(df, '值', stage='阶段')
    baseline = subject.analyze_improvement(df, '值', stage='阶段', limit_mode='baseline')
    base = control_chart.x_mR(list(before), 2)
    rows = baseline.tables['limits'].set_index(['阶段', '图表'])
    for panel, center, lower, upper in [('I', 'bar1', 'lcl1', 'ucl1'),
                                       ('MR', 'bar2', 'lcl2', 'ucl2')]:
        assert rows.loc[('改善前', panel), 'CL'] == pytest.approx(base[center])
        assert rows.loc[('改善后', panel), 'CL'] == pytest.approx(base[center])
        assert rows.loc[('改善后', panel), 'LCL'] == pytest.approx(base[lower])
        assert rows.loc[('改善后', panel), 'UCL'] == pytest.approx(base[upper])
    changed = independent.tables['limits'].set_index(['阶段', '图表'])
    assert changed.loc[('改善后', 'I'), 'UCL'] != rows.loc[('改善后', 'I'), 'UCL']
    # 固定基线的组内波动比按基线口径为 1，不把改善后自身波动重新估计后混入。
    ratios = baseline.tables['ratios'].set_index('指标')['数值']
    assert ratios.iloc[2] == pytest.approx(1.)
    assert '控制限不随改善后数据重新估计' in '\n'.join(baseline.notes)


@pytest.mark.parametrize('chart,panel', [('Xbar-R', 'R'), ('Xbar-S', 'S')])
def test_fixed_baseline_keeps_subgroup_limits_from_before(chart, panel):
    rng = np.random.default_rng(63)
    values = np.zeros(60)
    for start in (0, 30):
        values[start:start+3] = rng.normal(10 if start == 0 else 13, 1, 3)
        for i in range(start+3, start+30):
            values[i] = values[i-1] + rng.normal(0, 1 if start == 0 else 3)
    df = pd.DataFrame({'值': values, '阶段': ['前'] * 30 + ['后'] * 30})
    result = subject.analyze_improvement(df, '值', chart=chart, stage='阶段',
                                         subgroup_size=3, limit_mode='baseline')
    rows = result.tables['limits'].set_index(['阶段', '图表'])
    for key in ('LCL', 'CL', 'UCL'):
        assert rows.loc[('后', panel), key] == pytest.approx(rows.loc[('前', panel), key])
    center = result.plot['results'][1]
    assert np.allclose(center['ucl1'], result.plot['results'][0]['ucl1'])


def test_fixed_baseline_xbar_s_uses_after_subgroup_sizes():
    rng = np.random.default_rng(31)
    values = np.r_[rng.normal(10, 1, 12), rng.normal(10, 1, 20)]
    groups = [f'a{i//3}' for i in range(12)] + [f'b{i//5}' for i in range(20)]
    df = pd.DataFrame({'值': values, '阶段': ['前'] * 12 + ['后'] * 20, '组': groups})
    result = subject.analyze_improvement(df, '值', chart='Xbar-S', stage='阶段',
                                         subgroup_id='组', limit_mode='baseline')
    before, after = result.plot['results']
    from utilities import c4_values
    sigma = before['bar2'][0] / c4_values(3)
    assert after['n'] == [5] * 4
    np.testing.assert_allclose(after['bar2'], [c4_values(5) * sigma] * 4)
    # 基线中心保持改善前均值；子组大小变化时控制限按 n=5 重算。
    assert after['bar1'] == pytest.approx(before['bar1'])
    np.testing.assert_allclose(after['ucl1'], [before['bar1'] + 3 * sigma / 5 ** .5] * 4)
    rows = result.tables['limits'].set_index(['阶段', '图表'])
    assert rows.loc[('后', 'S'), 'CL'] == pytest.approx(c4_values(5) * sigma)


def test_unequal_subgroup_limits_are_reported_per_point():
    rng = np.random.default_rng(88)
    # 同一阶段内子组大小为 3、5、3、4，控制限逐子组变化。
    sizes = [3, 5, 3, 4]
    groups = [f'a{index}' for index, size in enumerate(sizes) for _ in range(size)]
    data = np.r_[rng.normal(10, 1, sum(sizes)), rng.normal(10, 1, 12)]
    df = pd.DataFrame({'值': data, '阶段': ['前'] * sum(sizes) + ['后'] * 12,
                       '组': groups + [f'b{index // 4}' for index in range(12)]})
    result = subject.analyze_improvement(df, '值', chart='Xbar-R', stage='阶段',
                                         subgroup_id='组')
    summary = result.tables['limits']
    varies = summary[(summary['阶段'] == '前') & (summary['图表'] == 'Xbar')]
    assert set(varies['UCL']) == {subject.LIMIT_VARIES}
    assert set(varies['LCL']) == {subject.LIMIT_VARIES}
    # R 图下限恒为 0，上限随子组大小变化。
    r_limits = summary[(summary['阶段'] == '前') & (summary['图表'] == 'R')]
    assert set(r_limits['LCL']) == {0.}
    assert set(r_limits['UCL']) == {subject.LIMIT_VARIES}
    details = result.tables['limit_details']
    # 改善前 4 个子组的 Xbar 与 R 各 4 行；改善后子组等大，只按需列出。
    before = result.plot['results'][0]
    rows = details[(details['阶段'] == '前') & (details['图表'] == 'Xbar')]
    assert len(rows) == 4
    for index in range(4):
        row = rows.iloc[index]
        for column, key in (('LCL', 'lcl1'), ('CL', 'bar1'), ('UCL', 'ucl1')):
            value = before[key]
            value = value[index] if isinstance(value, (list, tuple, np.ndarray)) else value
            assert row[column] == pytest.approx(value)
    figure = Figure(figsize=(8, 6))
    FigureCanvasAgg(figure)
    axes = subject.phase_control_plot(result, figure)['axes']
    np.testing.assert_allclose(axes[0].lines[3].get_ydata(), before['lcl1'])
    np.testing.assert_allclose(axes[1].lines[2].get_ydata(), before['ucl2'])
    # 固定限时汇总保持简洁标量，不产生明细。
    constant = subject.analyze_improvement(
        pd.DataFrame({'值': np.arange(16.), '阶段': ['前'] * 8 + ['后'] * 8}),
        '值', chart='Xbar-R', stage='阶段', subgroup_size=4)
    assert not len(constant.tables['limit_details'])
    assert all(isinstance(v, float) for v in constant.tables['limits']['UCL'])


def test_xbar_subgroups_do_not_cross_phase_and_reject_repeated_ids():
    data = np.arange(24, dtype=float)
    df = pd.DataFrame({'值': data, '阶段': ['前'] * 12 + ['后'] * 12,
                       '组': [f'g{i//3}' for i in range(24)]})
    result = subject.analyze_improvement(df, '值', chart='Xbar-R', stage='阶段',
                                         subgroup_id='组')
    for name, stage in zip(result.plot['names'], result.plot['results']):
        assert len(stage['Y1']) == 4
    crossing = df.copy()
    crossing.loc[9:14, '组'] = '跨界'
    with pytest.raises(ValueError, match='跨越阶段'):
        subject.analyze_improvement(crossing, '值', chart='Xbar-R', stage='阶段',
                                    subgroup_id='组')
    repeated = df.copy()
    repeated['组'] = ([f'p{i//3}' for i in range(4)] * 3 +
                      [f'q{i//3}' for i in range(4)] * 3)
    with pytest.raises(ValueError, match='不连续重复'):
        subject.analyze_improvement(repeated, '值', chart='Xbar-R', stage='阶段',
                                    subgroup_id='组')
    uneven = pd.DataFrame({'值': np.arange(22, dtype=float),
                           '阶段': ['前'] * 11 + ['后'] * 11})
    with pytest.raises(ValueError, match='不足两个'):
        subject.analyze_improvement(uneven, '值', chart='Xbar-R', stage='阶段',
                                    subgroup_size=5)


@pytest.mark.parametrize('chart', ['Xbar-R', 'Xbar-S'])
@pytest.mark.parametrize('mode', ['independent', 'baseline'])
def test_xbar_subgroups_use_their_own_phase_values(chart, mode):
    df = pd.DataFrame({'值': [1., 2., 3., 4., 101., 102., 103., 104.],
                       '阶段': ['前'] * 4 + ['后'] * 4})
    result = subject.analyze_improvement(df, '值', chart=chart, stage='阶段',
                                         subgroup_size=2, limit_mode=mode)
    before, after = result.plot['results']
    assert before['Y1'] == [1.5, 3.5]
    assert after['Y1'] == [101.5, 103.5]
    # R 图取极差，S 图取组内标准差。
    secondary = ([1., 1., 1., 1.] if chart == 'Xbar-R'
                 else [abs(2. - 1.) / 2 ** .5] * 4)
    assert before['Y2'] == pytest.approx(secondary[:2])
    assert after['Y2'] == pytest.approx(secondary[2:])


def test_xbar_subgroup_ids_and_missing_values_keep_source_rows():
    df = pd.DataFrame({'值': [1., 2., np.nan, 3., 4., 101., 102., 103., 104.],
                       '阶段': ['前'] * 5 + ['后'] * 4,
                       '组': ['a1', 'a1', 'a1', 'a2', 'a2', 'b1', 'b1', 'b2', 'b2']})
    result = subject.analyze_improvement(df, '值', chart='Xbar-R', stage='阶段',
                                         subgroup_id='组')
    before, after = result.plot['results']
    assert before['Y1'] == [1.5, 3.5]
    assert after['Y1'] == [101.5, 103.5]
    anomalies = result.tables['anomalies']
    # 来源行指向原始工作表（从 1 开始），缺失行不计入。
    assert set(anomalies['来源行']).issubset({1, 2, 4, 5, 6, 7, 8, 9})


def test_xbar_phase_plot_uses_subgroup_positions():
    df = pd.DataFrame({'值': np.r_[np.arange(1., 13.), np.arange(101., 109.)],
                       '阶段': ['前'] * 12 + ['后'] * 8})
    result = subject.analyze_improvement(df, '值', chart='Xbar-R', stage='阶段',
                                         subgroup_size=4)
    figure = Figure(figsize=(8, 6))
    FigureCanvasAgg(figure)
    handles = subject.phase_control_plot(result, figure)
    figure.canvas.draw()
    first, second = handles['axes']
    # 改善前 3 个、改善后 2 个子组：分界应落在第 3/4 个子组之间。
    np.testing.assert_allclose(first.lines[0].get_xdata(), [1, 2, 3])
    np.testing.assert_allclose(first.lines[4].get_xdata(), [4, 5])
    boundary = first.lines[-1]  # 两阶段各 4 条线后追加的分界虚线
    assert boundary.get_xdata()[0] == pytest.approx(boundary.get_xdata()[1])
    assert boundary.get_xdata()[0] == pytest.approx(3.5)
    assert '子组序号' in second.get_xlabel()


def test_i_chart_events_match_existing_nelson_helper():
    limit = 3 * 2
    values = [10.] * 30
    values[10] = 10 + 2 + 1e-9  # 规则2：连续9点同侧，从 2 起的 9 点
    values[20] = 10 + limit + .5
    df = pd.DataFrame({'值': values, '阶段': ['前'] * 15 + ['后'] * 15})
    result = subject.analyze_improvement(df, '值', stage='阶段')
    before = np.array(values[:15])
    mr = control_chart.x_mR(list(before), 2)
    center = mr['bar1']
    sigma = mr['bar2'] / 1.128
    z = (before - center) / sigma
    expected = nelson_events(z)
    actual = result.tables['anomalies']
    i_events = actual[(actual['阶段'] == '前') & (actual['图表'] == 'I')]
    assert {(row['窗口点号'].split('-')[1], int(row['触发规则'].split()[1]))
            for _, row in i_events.iterrows()} == {(str(e[0] + 1), e[1]) for e in expected}
    assert set(actual['触发规则']) <= {f'Nelson {i}' for i in range(1, 9)} | {'越限'}


@pytest.mark.parametrize('chart,panel', [('I-MR', 'MR'), ('Xbar-R', 'R'), ('Xbar-S', 'S')])
def test_range_panels_only_flag_limit_crossings(chart, panel):
    rng = np.random.default_rng(15)
    before = rng.normal(5, 1, 60)
    after = rng.normal(5, 1, 60)
    after[30] += 20
    df = two_phase(before, after)
    kwargs = {'subgroup_size': 3} if chart != 'I-MR' else {}
    result = subject.analyze_improvement(df, '值', chart=chart, stage='阶段', **kwargs)
    table = result.tables['anomalies']
    range_rows = table[table['图表'] == panel]
    assert set(range_rows['触发规则']) <= {'越限'}
    stage = result.plot['results'][1]
    low = stage['lcl2'] if not isinstance(stage['lcl2'], list) else stage['lcl2'][0]
    high = stage['ucl2'] if not isinstance(stage['ucl2'], list) else stage['ucl2'][0]
    for index in range_rows.index:
        value = table.loc[index, '统计值']
        assert value < low or value > high


def test_alarm_counts_use_points_and_do_not_double_count_panels():
    rng = np.random.default_rng(505)
    values = np.r_[rng.normal(10, 1, 12), rng.normal(10, 1, 12)]
    # 改善前建立基线；改善后第一组同时抬高均值与极差，两块面板都越限。
    values[12:16] = [40., 46., 41., 47.]
    df = pd.DataFrame({'值': values, '阶段': ['前'] * 12 + ['后'] * 12})
    result = subject.analyze_improvement(df, '值', chart='Xbar-R', stage='阶段',
                                         subgroup_size=4, limit_mode='baseline')
    table = result.tables['anomalies']
    after = table[table['阶段'] == '后']
    assert {'Xbar', 'R'} <= set(after['图表'])
    both = set(after[after['图表'] == 'Xbar']['点号']) & set(
        after[after['图表'] == 'R']['点号'])
    assert both
    metrics = result.tables['metrics'].set_index('指标')
    assert metrics.loc['异常子组比例', '后'] == pytest.approx(
        len(set(after['点号'])) / 3)
    assert metrics.loc['异常点数', '后'] == len(set(after['点号']))
    assert metrics.loc['异常规则记录数', '后'] == len(after)
    assert metrics.loc['异常规则记录数', '后'] > metrics.loc['异常点数', '后']
    assert '异常子组比例' in result.tables['metrics']['指标'].tolist()
    assert '异常观测比例' not in result.tables['metrics']['指标'].tolist()
    conclusions = result.tables['conclusions'].set_index('项目')['结论']
    assert '分母：子组数 3 → 3' in conclusions.loc['控制状态']


def test_i_mr_alarm_rate_uses_observations():
    rng = np.random.default_rng(606)
    values = np.r_[rng.normal(10, 1, 10), rng.normal(10, 1, 10)]
    values[0] = 40.
    df = pd.DataFrame({'值': values, '阶段': ['前'] * 10 + ['后'] * 10})
    result = subject.analyze_improvement(df, '值', stage='阶段')
    metrics = result.tables['metrics'].set_index('指标')
    assert '异常观测比例' in metrics.index
    before = result.tables['anomalies']
    before = before[before['阶段'] == '前']
    assert metrics.loc['异常观测比例', '前'] == pytest.approx(
        len(set(before['点号'])) / 10)
    assert '异常观测比例' in result.tables['conclusions'].set_index('项目')['结论'].loc['控制状态']
    assert '分母：观测数 10 → 10' in result.tables['conclusions'].set_index('项目')['结论'].loc['控制状态']


def test_single_point_subgroup_id_is_rejected_before_computation():
    df = pd.DataFrame({'值': [1., 2., 3., 4., 5., 6., 7.],
                       '阶段': ['前'] * 4 + ['后'] * 3,
                       '组': ['a1', 'a1', 'a2', 'a3', 'b1', 'b1', 'b2']})
    with pytest.raises(ValueError, match='至少需要两个观测值'):
        subject.analyze_improvement(df, '值', chart='Xbar-S', stage='阶段',
                                    subgroup_id='组')


def test_strong_autocorrelation_blocks_independent_significance():
    rng = np.random.default_rng(202)
    def ar1(n, phi, scale):
        values = np.zeros(n)
        for i in range(1, n):
            values[i] = phi * values[i-1] + rng.normal(0, scale)
        return values
    before = ar1(120, .8, 1)
    after = ar1(120, .8, 1) + 1
    df = two_phase(before, after)
    result = subject.analyze_improvement(df, '值', stage='阶段')
    tests = result.tables['tests'].set_index('项目')
    assert '自相关' in tests.loc['改善前自相关', '结论']
    assert tests.loc['均值差异', '结论'].startswith('显著性未评价')
    assert tests.loc['波动差异', '结论'].startswith('显著性未评价')
    assert pd.isna(tests.loc['均值差异', 'p 值'])
    assert any('独立样本检验不适用' in note for note in result.notes)
    # 描述性指标仍可计算且不被当成显著改善。
    assert np.isfinite(result.tables['metrics'].set_index('指标').loc['均值', '改善后'])


def test_weak_autocorrelation_uses_welch_and_brown_forsythe():
    from scipy import stats
    rng = np.random.default_rng(90)
    before = rng.normal(10, 1.2, 50)
    after = rng.normal(12, 2.5, 45)
    df = two_phase(before, after)
    result = subject.analyze_improvement(df, '值', stage='阶段', alpha=.01)
    tests = result.tables['tests'].set_index('项目')
    assert tests.loc['均值差异', '统计量'] == pytest.approx(
        stats.ttest_ind(after, before, equal_var=False).statistic)
    assert tests.loc['均值差异', 'p 值'] == pytest.approx(
        stats.ttest_ind(after, before, equal_var=False).pvalue)
    assert tests.loc['波动差异', 'p 值'] == pytest.approx(
        stats.levene(after, before, center='median').pvalue)
    assert result.tables['summary'].set_index('项目').loc['显著性水平', '内容'] == .01


def test_short_series_leaves_independence_unevaluated():
    # 每阶段 5 点：Ljung-Box 无法评价，不能声明独立性成立。
    df = two_phase([10., 11., 10., 11., 10.], [20., 21., 20., 21., 20.])
    result = subject.analyze_improvement(df, '值', stage='阶段')
    tests = result.tables['tests'].set_index('项目')
    assert tests.loc['均值差异', '结论'].startswith('显著性未评价')
    assert tests.loc['波动差异', '结论'].startswith('显著性未评价')
    assert '独立性未充分评价' in ' '.join(result.notes)
    assert tests.loc['改善前自相关', '结论'].startswith('样本不足或常数列')


def test_zero_variance_and_mean_report_not_applicable_with_reason():
    df = two_phase([0.] * 30, [1.] * 30)
    result = subject.analyze_improvement(df, '值', stage='阶段')
    ratios = result.tables['ratios'].set_index('指标')['数值']
    assert pd.isna(ratios.filter(like='均值变化率').iloc[0])
    assert pd.isna(ratios.filter(like='整体标准差').iloc[0])
    conclusions = result.tables['conclusions'].set_index('项目')['结论']
    assert '均值为 0' in conclusions.loc['均值变化（描述性）']
    assert '标准差为 0' in conclusions.loc['波动变化（描述性）']


def test_plot_values_match_tables_and_export(tmp_path):
    rng = np.random.default_rng(77)
    df = two_phase(rng.normal(10, 2, 25), rng.normal(9, 1, 20))
    result = subject.analyze_improvement(df, '值', stage='阶段')
    figure = Figure(figsize=(9, 7))
    FigureCanvasAgg(figure)
    handles = subject.phase_control_plot(result, figure)
    figure.canvas.draw()
    assert len(handles['axes']) == 2
    limits = result.tables['limits']
    for axis, panel in zip(handles['axes'], ['I', 'MR']):
        key = 'Y1' if panel == 'I' else 'Y2'
        np.testing.assert_allclose(axis.lines[0].get_ydata(),
                                   result.plot['results'][0][key])
        np.testing.assert_allclose(axis.lines[4].get_ydata(),
                                   result.plot['results'][1][key])
        for stage in ('改善前', '改善后'):
            row = limits[(limits['阶段'] == stage) & (limits['图表'] == panel)].iloc[0]
            y = axis.lines[1 if stage == '改善前' else 5].get_ydata()
            np.testing.assert_allclose(y[0], row['CL'])
            np.testing.assert_allclose(y[-1], row['CL'])
        assert any(text.get_text() in ('改善前', '改善后') for text in axis.texts)
    target = tmp_path / '改善前后.png'
    figure.savefig(target)
    assert target.stat().st_size > 1000


def test_print_report_sections_and_causality_caveat():
    df = two_phase(np.arange(20.), np.arange(20.) * .5)
    result = subject.analyze_improvement(df, '值', stage='阶段')
    lines = []
    subject.print_report(result, lines.append)
    text = '\n'.join(map(str, lines))
    for heading in ('A. 数据摘要', 'B. 控制图结果', 'C. 改善效果对比',
                    'D. 统计检验', 'E. 分析结论'):
        assert heading in text
    assert '统计显著差异不等于因果改善' in text
    assert '口径不同' in text


def test_dialog_reuses_source_sheet_and_plot_viewer(tk_root, monkeypatch):
    from MiniJMP import Minijmp
    from improvement_dialog import ImprovementChartDialog
    from test_regression_dialog import dispose

    monkeypatch.setattr(Minijmp, 'start_logging', lambda self: None)
    app = Minijmp(parent=tk_root)
    rng = np.random.default_rng(2048)
    data = pd.DataFrame({'测量': np.r_[rng.normal(10, 2, 30), rng.normal(9, 1, 30)],
                         '阶段': ['改善前'] * 30 + ['改善后'] * 30})
    source = app.addSheet('来源', data.copy(deep=True))
    result = subject.analyze_improvement(data, '测量', stage='阶段')
    dialog = ImprovementChartDialog(source, app, result)
    try:
        dialog.error = Mock()
        dialog.error.assert_not_called()
        # 后端始终提供该表；控制限固定时为空，UI 不显示空白标签页。
        assert 'limit_details' in result.tables
        assert not len(result.tables['limit_details'])
        assert set(dialog.tables) == {'summary', 'metrics', 'ratios', 'limits',
                                      'anomalies', 'tests', 'conclusions'}
        assert 'limit_details' not in dialog.tabs
        labels = [dialog.notebook.tab(tab, 'text') for tab in dialog.notebook.tabs()]
        assert '逐子组控制限' not in labels
        assert len(labels) == len(dialog.tables)
        app.print = Mock()
        dialog.report()
        assert app.print.call_count > 5
        assert all(call.kwargs['table'] is source for call in app.print.call_args_list)
        dialog.plot()
        dialog.error.assert_not_called()
        assert source.pf is not None and len(source.pf.fig.axes) == 2
        pd.testing.assert_frame_equal(source.model.df, data)
    finally:
        dialog.close()
        dispose(app)


def test_dialog_shows_limit_details_tab_only_when_limits_vary(tk_root, monkeypatch):
    import improvement_dialog
    from MiniJMP import Minijmp
    from test_regression_dialog import dispose

    monkeypatch.setattr(Minijmp, 'start_logging', lambda self: None)
    app = Minijmp(parent=tk_root)
    rng = np.random.default_rng(913)
    sizes = [3, 5, 3, 4]
    groups = [f'a{index}' for index, size in enumerate(sizes) for _ in range(size)]
    values = np.r_[rng.normal(10, 1, sum(sizes)), rng.normal(10, 1, 8)]
    data = pd.DataFrame({'测量': values, '阶段': ['前'] * sum(sizes) + ['后'] * 8,
                         '组': groups + [f'b{index // 4}' for index in range(8)]})
    source = app.addSheet('来源', data.copy(deep=True))
    result = subject.analyze_improvement(data, '测量', chart='Xbar-R', stage='阶段',
                                         subgroup_id='组')
    assert len(result.tables['limit_details'])
    dialog = improvement_dialog.ImprovementChartDialog(source, app, result)
    try:
        dialog.error = Mock()
        assert 'limit_details' in dialog.tabs
        labels = [dialog.notebook.tab(tab, 'text') for tab in dialog.notebook.tabs()]
        assert labels.count('逐子组控制限') == 1
        shown = dialog.tables['limit_details']
        assert len(shown) and {'阶段', '图表', '点号', 'LCL', 'CL', 'UCL'} <= set(shown.columns)
        dialog.notebook.select(dialog.tabs['limit_details'])
        _, exported = dialog.current_table()
        assert exported is shown
        app.print = Mock()
        dialog.report()
        dialog.error.assert_not_called()
        assert app.print.call_count > 5
        pd.testing.assert_frame_equal(source.model.df, data)
    finally:
        dialog.close()
        dispose(app)


def test_original_control_chart_dialog_runs_stage_compare(tk_root, monkeypatch):
    import improvement_dialog
    from MiniJMP import Minijmp
    from test_regression_dialog import dispose

    monkeypatch.setattr(Minijmp, 'start_logging', lambda self: None)
    captured = []
    monkeypatch.setattr(improvement_dialog, 'ImprovementChartDialog',
                        lambda parent, app, result: captured.append(result))
    app = Minijmp(parent=tk_root)
    data = pd.DataFrame({'测量': [1., 2., 3., 4., 101., 102., 103., 104.],
                         '阶段': ['前'] * 4 + ['后'] * 4})
    source = app.addSheet('来源', data.copy(deep=True))
    from ctrlchart_dialog import IMRDialog, XBRDialog
    for cls, chart in ((IMRDialog, 'I-MR'), (XBRDialog, 'Xbar-R')):
        dialog = cls(source, df=source.model.df, app=app, title='控制图')
        try:
            # 默认关闭时不展开设置，保持原布局与流程。
            assert not dialog.stage_compare.get()
            assert not hasattr(dialog, 'sc_frame')
            dialog.xvar.set('测量')
            if chart != 'I-MR':
                dialog.gsize.set('2')
            dialog.stage_compare.set(True)
            import stage_compare
            stage_compare.toggle(dialog)
            dialog.sc_stage.set('阶段')
            dialog.apply()
        finally:
            if dialog.main.winfo_exists():
                dialog.quit()
        result = captured.pop()
        assert result.plot['chart'] == chart
        expected = ([[1.5, 3.5], [101.5, 103.5]] if chart == 'Xbar-R'
                    else [[1., 2., 3., 4.], [101., 102., 103., 104.]])
        assert [stage['Y1'] for stage in result.plot['results']] == expected
    dispose(app)


def test_stage_compare_result_window_plots_matching_values(tk_root, monkeypatch):
    from MiniJMP import Minijmp
    from improvement_dialog import ImprovementChartDialog
    from test_regression_dialog import dispose

    monkeypatch.setattr(Minijmp, 'start_logging', lambda self: None)
    app = Minijmp(parent=tk_root)
    data = pd.DataFrame({'测量': [1., 2., 3., 4., 101., 102., 103., 104.],
                         '阶段': ['前'] * 4 + ['后'] * 4})
    source = app.addSheet('来源', data.copy(deep=True))
    result = subject.analyze_improvement(data, '测量', chart='Xbar-R',
                                         stage='阶段', subgroup_size=2)
    dialog = ImprovementChartDialog(source, app, result)
    try:
        dialog.error = Mock()
        dialog.plot()
        dialog.error.assert_not_called()
        first = source.pf.fig.axes[0]
        np.testing.assert_allclose(first.lines[0].get_ydata(), [1.5, 3.5])
        np.testing.assert_allclose(first.lines[4].get_ydata(), [101.5, 103.5])
        # 分界落在第 2/3 个子组之间，而不是原始行数 4/5。
        boundary = first.lines[-1].get_xdata()[0]
        assert boundary == pytest.approx(2.5)
        pd.testing.assert_frame_equal(source.model.df, data)
    finally:
        dialog.close()
        dispose(app)


def test_stage_compare_rejects_cutoff_outside_range(tk_root, monkeypatch):
    import improvement_dialog
    from MiniJMP import Minijmp
    from test_regression_dialog import dispose
    from ctrlchart_dialog import IMRDialog

    monkeypatch.setattr(Minijmp, 'start_logging', lambda self: None)
    calls = []
    monkeypatch.setattr(improvement_dialog, 'ImprovementChartDialog',
                        lambda *args: calls.append(args))
    app = Minijmp(parent=tk_root)
    source = app.addSheet('来源', pd.DataFrame({'测量': [1., 2., 3., 4.],
                                               '时间': [1., 2., 3., 4.]}))
    dialog = IMRDialog(source, df=source.model.df, app=app, title='控制图')
    try:
        dialog.xvar.set('测量')
        dialog.stage_compare.set(True)
        import stage_compare
        stage_compare.toggle(dialog)
        dialog.sc_split.set('时间分界点')
        dialog.sc_time.set('时间')
        dialog.sc_cutoff.set('99')
        dialog.error = Mock()
        dialog.apply()
        dialog.error.assert_called_once()
        assert '分界时间' in str(dialog.error.call_args)
        assert calls == []
    finally:
        if dialog.main.winfo_exists():
            dialog.quit()
    dispose(app)
