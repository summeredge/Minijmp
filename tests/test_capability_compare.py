"""改善前后能力对比：独立参考计算、阶段划分、适用性限制与图形边界。"""
import numpy as np
import pandas as pd
import pytest
from matplotlib.figure import Figure
from scipy import stats

from capability import analyze_capability
from capability_compare import analyze_capability_comparison, print_report
from capability_plots import plot_capability_comparison


def reference(values, lsl=None, usl=None, k=6.):
    """独立参考：单值 MR 组内标准差、样本标准差与正态 PPM。"""
    x = np.asarray(values, dtype=float)
    sw = np.mean(np.abs(np.diff(x))) / (2 / np.sqrt(np.pi))
    so = np.std(x, ddof=1)
    h = k / 2
    sides = [index for index, spec in ((0, lsl), (1, usl)) if spec is not None]
    cpk = min((x.mean() - lsl) / (h * sw) if 0 in sides else np.inf,
              (usl - x.mean()) / (h * sw) if 1 in sides else np.inf)
    ppk = min((x.mean() - lsl) / (h * so) if 0 in sides else np.inf,
              (usl - x.mean()) / (h * so) if 1 in sides else np.inf)
    ppm = 0.
    if lsl is not None:
        ppm += stats.norm.cdf((lsl - x.mean()) / so) * 1e6
    if usl is not None:
        ppm += stats.norm.sf((usl - x.mean()) / so) * 1e6
    count = int(np.count_nonzero(x < lsl) if lsl is not None else 0) + \
        int(np.count_nonzero(x > usl) if usl is not None else 0)
    return dict(mean=x.mean(), within=sw, overall=so, cpk=cpk, ppk=ppk,
                ppm=ppm, count=count)


def phases(before, after, names=('改善前', '改善后')):
    values = np.concatenate([before, after])
    labels = [names[0]] * len(before) + [names[1]] * len(after)
    return pd.DataFrame({'测量': values, '阶段': labels})


def test_two_phases_match_independent_reference_and_share_specs():
    before = np.random.default_rng(11).normal(10., 2., 90)
    after = np.random.default_rng(12).normal(10.5, 1., 110)
    frame = phases(before, after)
    result = analyze_capability_comparison(frame, '测量', lsl=4, usl=17, target=10.5,
                                           stage='阶段')
    indices = result.tables['能力指数对比'].set_index('指标')
    spread = result.tables['波动与超规对比'].set_index('指标')
    for name, values in (('改善前', before), ('改善后', after)):
        expected = reference(values, 4, 17)
        assert indices.at['Cpk', name] == pytest.approx(expected['cpk'])
        assert indices.at['Ppk', name] == pytest.approx(expected['ppk'])
        assert spread.at['均值', name] == pytest.approx(expected['mean'])
        assert spread.at['组内标准差', name] == pytest.approx(expected['within'])
        assert spread.at['整体标准差', name] == pytest.approx(expected['overall'])
        assert spread.at['预计 PPM（整体）', name] == pytest.approx(expected['ppm'])
        assert spread.at['实测超规数', name] == expected['count']
    # 差值只在同一规格与同一尺度下计算。
    mask = np.isfinite(before)
    for key, expected in (('Cpk', reference(after, 4, 17)['cpk']
                           - reference(before, 4, 17)['cpk']),):
        assert indices.at[key, '差值'] == pytest.approx(expected)
    summary = result.tables['数据与规格摘要'].set_index('项目')['内容']
    assert 'LSL=4' in summary['规格'] and 'USL=17' in summary['规格']
    assert '原始测量尺度' in summary['分析尺度']


def test_stage_order_subgroups_and_source_rows_stay_within_phase():
    frame = pd.DataFrame({
        '测量': [10., 10.2, 9.8, 10.1, 12., 12.3, 12.1, 11.9],
        '阶段': ['B'] * 4 + ['A'] * 4,
        '批次': [1, 1, 2, 2, 3, 3, 4, 4]})
    result = analyze_capability_comparison(frame, '测量', lsl=5, usl=15,
                                           subgroup_ids=frame['批次'], stage='阶段')
    names = result.plot['names']
    assert names == ['B', 'A']  # 实际出现顺序，不按标签排序
    rows = [stage['source_row'].tolist() for stage in result.plot['results']]
    assert rows == [[1, 2, 3, 4], [5, 6, 7, 8]]
    assert [len(stage['groups']) for stage in result.plot['results']] == [2, 2]
    spread = result.tables['波动与超规对比'].set_index('指标')
    # 组内标准差只在阶段内合并，不与另一阶段共用子组。
    for name, group in (('B', [[10., 10.2], [9.8, 10.1]]),
                        ('A', [[12., 12.3], [12.1, 11.9]])):
        independent = analyze_capability(group[0] + group[1], lsl=5, usl=15,
                                        subgroup_size=2)
        assert spread.at['组内标准差', name] == pytest.approx(independent['within_sigma'])


def test_subgroup_crossing_phase_boundary_is_rejected():
    frame = pd.DataFrame({'测量': [1., 2., 3., 4.], '阶段': ['B', 'B', 'A', 'A'],
                          '批次': [1, 1, 1, 2]})
    with pytest.raises(ValueError, match='子组不得跨阶段'):
        analyze_capability_comparison(frame, '测量', lsl=0, usl=10,
                                      subgroup_ids=frame['批次'], stage='阶段')


def test_one_sided_specs_zero_defects_and_not_applicable():
    rng = np.random.default_rng(31)
    frame = phases(rng.normal(20, 1, 60), rng.normal(21, 1, 60))
    result = analyze_capability_comparison(frame, '测量', lsl=15, stage='阶段')
    indices = result.tables['能力指数对比'].set_index('指标')
    assert indices.at['Cp', '改善前'] == '不适用'  # 单侧规格不定义 Cp
    assert indices.at['Cpk', '改善前'] == pytest.approx((20 - 15) / (3 * 1), rel=.2)
    spread = result.tables['波动与超规对比'].set_index('指标')
    assert spread.at['实测超规数', '改善前'] == 0
    assert spread.at['实测超规率（%）', '改善前'] == 0
    assert indices.at['Cp', '说明'] == '需双侧规格'
    # 单侧 LSL 仍可定义 Cpl/Cpk，且与单阶段结果一致。
    single = analyze_capability(before := frame['测量'].to_numpy()[:60], lsl=15)
    assert indices.at['Cpl', '改善前'] == pytest.approx(single['indices']['Cpl'])
    assert indices.at['Cpk', '改善前'] == pytest.approx(single['indices']['Cpk'])


def test_nonnormal_mode_never_mixes_normal_indices():
    rng = np.random.default_rng(41)
    frame = phases(rng.lognormal(.5, .3, 120), rng.lognormal(.55, .25, 120))
    result = analyze_capability_comparison(frame, '测量', lsl=1, usl=8,
                                           distribution='lognormal', stage='阶段')
    metrics = result.tables['能力指数对比']
    assert not metrics['指标'].isin(['Cp', 'Cpk', 'Cpl', 'Cpu']).any()
    assert {'Pp', 'Ppk'} <= set(metrics['指标'])
    spread = result.tables['波动与超规对比']
    assert not spread['指标'].str.startswith('预计 PPM（组内）').any()
    indices = metrics.set_index('指标')
    left = result.plot['results'][0]['indices']
    assert indices.at['Ppk', '改善前'] == pytest.approx(left['Ppk'])


def test_autocorrelation_and_fit_mismatch_limit_conclusions():
    rng = np.random.default_rng(51)
    before = np.cumsum(rng.normal(0, .2, 120)) + 10
    after = np.cumsum(rng.normal(0, .2, 120)) + 20
    frame = phases(before, after)
    result = analyze_capability_comparison(frame, '测量', lsl=-20, usl=60, stage='阶段')
    tests = result.tables['统计检验'].set_index('项目')
    correlation = tests.loc[[name for name in tests.index if name.endswith('自相关')]]
    assert any('存在明显自相关' in str(value) for value in correlation['结论'])
    conclusions = result.tables['分析结论'].set_index('项目')['结论']
    assert '明显自相关' in conclusions['解释限制']
    assert '不输出显著改善结论' in conclusions['改善结论']

    skewed = phases(rng.exponential(1., 150), rng.exponential(1., 150))
    mismatch = analyze_capability_comparison(skewed, '测量', lsl=0., usl=12.,
                                             stage='阶段')
    diagnostics = mismatch.tables['稳定性与分布诊断']
    assert diagnostics['检查项'].str.contains('分布适用性').any()
    assert '分布拟合失配' in mismatch.tables['分析结论'].set_index('项目').at['解释限制', '结论']


def test_report_uses_same_tables_without_touching_source():
    rng = np.random.default_rng(61)
    frame = phases(rng.normal(10, 1.5, 80), rng.normal(10, .8, 80))
    before = frame.copy(deep=True)
    result = analyze_capability_comparison(frame, '测量', lsl=4, usl=16, stage='阶段')
    lines = []
    print_report(result, lines.append)
    text = '\n'.join(lines)
    for title in ('A. 数据与规格摘要', 'B. 过程稳定性与分布适用性',
                  'C. 能力指数前后比较', 'D. 整体与组内波动变化',
                  'F. 统计检验与自相关', 'G. 分析结论与适用边界'):
        assert title in text
    assert 'Cpk' in text and 'PPM' in text
    pd.testing.assert_frame_equal(frame, before)


def test_comparison_plot_shares_scale_specs_and_indices():
    rng = np.random.default_rng(71)
    frame = phases(rng.normal(10, 2, 100), rng.normal(10.5, 1, 100))
    result = analyze_capability_comparison(frame, '测量', lsl=4, usl=17, target=10,
                                           stage='阶段')
    fig = plot_capability_comparison(result)
    assert isinstance(fig, Figure)
    low, high = fig.axes[0].get_xlim()
    assert fig.axes[1].get_xlim() == (low, high)
    assert low <= 4 and high >= 17  # 规格限两阶段共用同一范围
    for ax in fig.axes[:2]:
        labels = {line.get_label() for line in ax.lines}
        assert {'LSL', 'USL', 'Target', '整体拟合'} <= labels
    bars = fig.axes[2].patches
    expected = [value for stage in result.plot['results']
                for value in (stage['indices']['Cp'], stage['indices']['Cpk'],
                              stage['indices']['Pp'], stage['indices']['Ppk'])]
    assert len(bars) == len(expected)
    heights = [bar.get_height() for bar in bars]
    assert np.allclose(sorted(heights), sorted(expected))
    reuse = Figure()
    assert plot_capability_comparison(result, reuse) is reuse
    assert len(reuse.axes) == 4


def ppm_axis(figure):
    """返回 PPM 面板的 (行中心 y, 条形) 与文字，用于核对单位与数值。"""
    ax = figure.axes[3]
    bars = [(patch.get_y() + patch.get_height() / 2, patch) for patch in ax.patches]
    return ax, bars, [text.get_text() for text in ax.texts]


def stage_bar(bars, row, index):
    """条形中心 = 行号 + (阶段序-.5)*.36；只取位于该位置的条形。"""
    target = row + (index - .5) * .36
    return [patch for center, patch in bars if abs(center - target) < .1]


def test_ppm_panel_uses_data_keys_and_ppm_units():
    rng = np.random.default_rng(101)
    before = rng.normal(10, 2., 200)
    after = rng.normal(10, .5, 200)
    before[0], before[1] = 2.5, 17.5      # 两阶段实际超规数不同
    frame = phases(before, after)
    result = analyze_capability_comparison(frame, '测量', lsl=4, usl=16, stage='阶段')
    spread = result.tables['波动与超规对比'].set_index('指标')
    counts = [spread.at['实测超规数', name] for name in result.plot['names']]
    assert counts[0] != counts[1]          # 两阶段实际超规数不同
    assert 0 in counts                     # 其中一侧完全无超规

    figure = plot_capability_comparison(result)
    ax, bars, labels = ppm_axis(figure)
    assert [tick.get_text() for tick in ax.get_yticklabels()] == [
        '实测超规 PPM', '预计 PPM（整体）', '预计 PPM（组内）']
    # 实测行以 PPM 为单位，与统计表的超规率×1e4 一致；0 只标注不画条形。
    for name, count in zip(result.plot['names'], counts):
        ppm = float(spread.at['实测超规率（%）', name]) * 1e4
        assert ppm == pytest.approx(count / 200 * 1e6)
        assert ('%.4g' % ppm) in labels
    for index, count in enumerate(counts):
        assert len(stage_bar(bars, 0, index)) == (1 if count else 0)
    # 预计 PPM 两阶段不同、与表中一致，且不与实测行混用同一数值。
    predicted = [spread.at['预计 PPM（整体）', name] for name in result.plot['names']]
    assert predicted[0] != pytest.approx(predicted[1])
    assert all('%.4g' % value in labels for value in predicted)


def test_ppm_panel_marks_missing_as_na_and_zero_predicts():
    rng = np.random.default_rng(102)
    frame = phases(rng.normal(10, 1., 120), rng.normal(13, 1., 120))
    result = analyze_capability_comparison(frame, '测量', lsl=5, usl=15, stage='阶段')
    spread = result.tables['波动与超规对比'].set_index('指标')
    assert spread.at['实测超规数', '改善前'] == 0     # 实测为零
    predicted = spread.at['预计 PPM（整体）', '改善前']
    assert predicted > 0                            # 预计非零
    figure = plot_capability_comparison(result)
    ax, bars, labels = ppm_axis(figure)
    assert ('%.4g' % predicted) in labels
    # 实测为 0 的一侧不画条形，零值只有文字 "0"。
    assert '0' in labels
    assert len(stage_bar(bars, 0, 0)) == 0   # 实测 0：不画误导性的非零条形
    assert len(stage_bar(bars, 0, 1)) == 1   # 改善后实测非零

    # 组内 PPM 未定义（非正态）时该行整体消失，不留下“NA”占位。
    nonnormal = analyze_capability_comparison(
        phases(rng.lognormal(.4, .2, 120), rng.lognormal(.5, .2, 120)),
        '测量', lsl=1., usl=8., distribution='lognormal', stage='阶段')
    ax2, bars2, labels2 = ppm_axis(plot_capability_comparison(nonnormal))
    ticks = [tick.get_text() for tick in ax2.get_yticklabels()]
    assert '预计 PPM（组内）' not in ticks and not any('组内' in t for t in ticks)
    assert all(tick in ('实测超规 PPM', '预计 PPM（整体）') for tick in ticks)


def test_nonnormal_special_causes_only_flag_limits():
    """非正态 I 图上下限不对称；只判越限，不套 Nelson。"""
    from capability_compare import _special_causes
    from capability import analyze_capability

    rng = np.random.default_rng(103)
    values = rng.lognormal(.6, .3, 200)
    stage = analyze_capability(values, lsl=1., usl=12., distribution='lognormal')
    special = _special_causes(stage)
    assert special['rules'] is False
    lower, upper = stage['model'].ppf([.00135, .99865])
    assert upper - stage['mean'] > stage['mean'] - lower   # 确实不对称
    outside = int((values < lower).sum() + (values > upper).sum())
    assert special['alarms'] == outside
    assert special['beyond'] <= special['points']

    normal = analyze_capability(rng.normal(10, 1., 200), lsl=5, usl=15)
    assert _special_causes(normal)['rules'] is True


def test_nonnormal_in_limit_sequence_does_not_trigger_nelson():
    """限内的连续上升点：旧做法按对称尺度误报连续模式，新做法只判越界。"""
    from capability_compare import _special_causes
    from capability import analyze_capability
    from capability_plots import _charts
    from control_chart import _panel_events

    rng = np.random.default_rng(11)
    values = rng.lognormal(.6, .2, 300)
    ramp = np.arange(150, 159)
    values[ramp] = values[ramp].mean() + np.linspace(-.6, .6, 9) * .3
    stage = analyze_capability(values, lsl=.5, usl=25., distribution='lognormal')
    chart, _, _ = _charts(stage, [np.asarray(g, float) for g in stage['groups']])
    plotted = np.asarray(chart['Y1'], float)
    assert plotted.min() > chart['lcl1'] and plotted.max() < chart['ucl1']  # 全部在限内

    # 旧做法把 (UCL-CL)/3 当公共尺度：同一数据命中连续模式规则。
    scales = [(chart['ucl1'] - chart['bar1']) / 3] * len(plotted)
    legacy = _panel_events(chart['Y1'], chart['bar1'], chart['lcl1'], chart['ucl1'],
                           None, scales, panel='I')
    assert {event['rule'] for event in legacy} & {'Nelson 2', 'Nelson 3', 'Nelson 7'}
    # 新做法只判越界：限内连续点不产生任何异常。
    assert not _special_causes(stage)['rules']
    assert _special_causes(stage)['alarms'] == 0


def test_nonnormal_two_sided_limit_crossings():
    """非对称分布的上下控制限：两侧越界都计入，预期数按重拟合后的实际限计算。"""
    from capability_compare import _special_causes
    from capability import analyze_capability

    rng = np.random.default_rng(104)
    base = np.sort(rng.lognormal(.6, .25, 240))
    stage = analyze_capability(base, lsl=1., usl=12., distribution='lognormal')
    lower, upper = stage['model'].ppf([.00135, .99865])
    data = base.copy()
    data[0], data[-1] = lower * .9, upper * 1.1
    # 插入越界点后参数会变，预期必须以重拟合后的控制限为准。
    stage = analyze_capability(data, lsl=1., usl=12., distribution='lognormal')
    lower, upper = stage['model'].ppf([.00135, .99865])
    below, above = int((data < lower).sum()), int((data > upper).sum())
    assert below >= 1 and above >= 1          # 上下两侧都确实越界
    special = _special_causes(stage)
    assert not special['rules']
    assert special['alarms'] == below + above


def test_invalid_inputs_are_rejected():
    frame = phases([1., 2., 3.], [4., 5., 6.])
    with pytest.raises(ValueError, match='规格'):
        analyze_capability_comparison(frame, '测量', stage='阶段')
    with pytest.raises(ValueError, match='测量列'):
        analyze_capability_comparison(frame, '缺失', lsl=0, stage='阶段')
    single = pd.DataFrame({'测量': [1., 2., 3.], '阶段': ['A'] * 3})
    with pytest.raises(ValueError, match='两个连续阶段'):
        analyze_capability_comparison(single, '测量', lsl=0, stage='阶段')
    with pytest.raises(ValueError, match='时间列'):
        analyze_capability_comparison(frame, '测量', lsl=0, split='time',
                                      time=None, cutoff='1')

