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

