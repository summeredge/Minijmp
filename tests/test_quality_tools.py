"""逐阶段独立数值约定；人工可计算频数与图形文件。"""
import numpy as np
import pandas as pd
import pytest
from PIL import Image
from quality_tools import pareto_chart
from quality_tools import run_chart
from quality_tools import cause_effect
from quality_tools import multi_vari
from itertools import product
from quality_tools_plots import plot_quality


def test_pareto_counts_threshold_groups_and_order(tmp_path):
    data = pd.DataFrame({'缺陷': ['中文', 'B', 'C', '中文', 'D'], '频数': [4, 3, 1, 1, 1], '组': ['甲']*5})
    original = data.copy(deep=True)
    result = pareto_chart(data, '缺陷', '频数', '组', threshold=80)
    table = result['tables']['分组 甲']
    assert table['类别'].tolist() == ['中文', 'B', 'C', '其他（合并）']
    assert table['频数'].tolist() == [5, 3, 1, 1]
    np.testing.assert_allclose(table['累计百分比'], [50, 80, 90, 100])
    assert pareto_chart(data, '缺陷', '频数', threshold=None, max_categories=3)['tables']['分组 全部']['频数'].tolist() == [5, 3, 2]
    assert pareto_chart(data, '缺陷', threshold=None)['tables']['分组 全部']['频数'].tolist() == [2, 1, 1, 1]
    pd.testing.assert_frame_equal(data, original)
    path = tmp_path/'pareto.png'
    plot_quality(result).savefig(path)
    assert Image.open(path).width > 500


@pytest.mark.parametrize('counts', [[-1, 2], [1.5, 2], [0, 0], [float('inf'), 2], ['bad', 2], [None, 2]])
def test_pareto_bad_frequency(counts):
    with pytest.raises(ValueError):
        pareto_chart(pd.DataFrame({'c': ['A', 'B'], 'n': counts}), 'c', 'n')


def test_pareto_empty_missing_many_zero_and_groups():
    for cats in [[], [None], ['']]:
        with pytest.raises(ValueError):
            pareto_chart(pd.DataFrame({'c': cats}), 'c')
    frame = pd.DataFrame({'c': list(range(200)), 'n': [0]+[1]*199, 'g': ['A']*100+['B']*100})
    result = pareto_chart(frame, 'c', 'n', 'g', threshold=None)
    assert len(result['tables']) == 2
    assert sum(t['频数'].sum() for t in result['tables'].values()) == 199
    assert len(pareto_chart(frame, 'c', 'n', threshold=100)['tables']['分组 全部']) == 200


def test_run_counts_order_ties_subgroups():
    r = run_chart(pd.DataFrame({'y': [1, 2, 2, 3, 1]}), 'y')
    t = r['tables']['随机性检验']
    assert t['运行段数'].tolist() == [3, 4]
    assert t['期望运行数'].tolist() == [2.6, 3.0]
    assert t['Z'].isna().all()
    assert r['tables']['运行图数据']['统计量'].tolist() == [1, 2, 2, 3, 1]
    r = run_chart(pd.DataFrame({'y': [1, 3, 2, 6, 8, 10], 'g': ['B', 'B', 'A', 'A', 'C', 'C']}), 'y', subgroup='g')
    assert r['tables']['运行图数据']['子组'].tolist() == ['B', 'A', 'C']
    assert r['tables']['运行图数据']['统计量'].tolist() == [2, 4, 9]
    assert run_chart(pd.DataFrame({'y': range(12)}), 'y', size=4, statistic='median')['tables']['运行图数据']['统计量'].tolist() == [1.5, 5.5, 9.5]


def test_run_independent_normal_reference_and_patterns():
    from scipy.special import ndtr
    for y, expected_runs, updown in [(np.arange(40), 2, 1), (np.ravel(np.column_stack((np.arange(20), np.arange(20)+100))), 40, 39)]:
        r = run_chart(pd.DataFrame({'y': y}), 'y')
        t = r['tables']['随机性检验']
        assert t['运行段数'].tolist() == [expected_runs, updown]
        # 20 above and 20 below: E=21, Var=380/39; up/down E=79/3, Var=611/90.
        z = [(expected_runs-21)/np.sqrt(380/39), (updown-79/3)/np.sqrt(611/90)]
        np.testing.assert_allclose(t['Z'], z)
        np.testing.assert_allclose(t['左尾 p'], ndtr(z))
        assert ('趋势' in t.iloc[1]['模式']) if updown == 1 else ('振荡' in t.iloc[1]['模式'])
    with pytest.raises(ValueError):
        run_chart(pd.DataFrame({'y': [1, 2]}), 'y')
    with pytest.raises(ValueError):
        run_chart(pd.DataFrame({'y': [1, 2, 3], 'g': ['A', 'B', 'A']}), 'y', subgroup='g')
    assert run_chart(pd.DataFrame({'y': [5]*20}), 'y')['tables']['随机性检验']['Z'].isna().all()


def test_cause_structure_and_long_chinese(tmp_path):
    frame = pd.DataFrame([['人', '培训不足', '操作说明不清楚'*3], ['人', '培训不足', '操作说明不清楚'*3], ['机', '', '']], columns=['类别', '原因', '子原因'])
    result = cause_effect(frame, '产品缺陷')
    assert len(result['tables']['原因结构']) == 2
    assert '因果证明' in result['warnings'][0]
    plot_quality(result).savefig(tmp_path/'fishbone.png')
    assert Image.open(tmp_path/'fishbone.png').height >= 700
    with pytest.raises(ValueError):
        cause_effect(frame, '')
    with pytest.raises(ValueError):
        cause_effect(pd.DataFrame([['人', '', '孤立']], columns=frame.columns), '问题')
    dense = pd.DataFrame([['人', cause, child*3] for cause in ['培训不足', '流程遗漏', '交接不清']
                          for child in ['操作说明不清楚', '缺少现场指导', '检查时间不足']], columns=frame.columns)
    fig = plot_quality(cause_effect(dense, '缺陷增加'))
    assert fig.get_figheight() > 10
    fig.savefig(tmp_path/'dense-fishbone.png')


@pytest.mark.parametrize('n_factors', [1, 2, 3, 4])
def test_multivari_independent_cells_and_plot(n_factors, tmp_path):
    factors = [f'f{i}' for i in range(n_factors)]
    rows = [list(cell)+[sum(cell)*10+offset] for cell in product([0, 1], repeat=n_factors) for offset in [0, 2]]
    frame = pd.DataFrame(rows, columns=factors+['y'])
    result = multi_vari(frame, 'y', factors)
    table = result['tables']['组合统计']
    assert len(table) == 2**n_factors
    assert table['N'].tolist() == [2]*(2**n_factors)
    np.testing.assert_allclose(table['均值'], [sum(cell)*10+1 for cell in product([0, 1], repeat=n_factors)])
    np.testing.assert_allclose(table['SD'], np.sqrt(2))
    assert table['极差'].eq(2).all()
    fig = plot_quality(result)
    assert len(fig.axes) == 2**max(0, n_factors-2)
    fig.savefig(tmp_path/f'multivari{n_factors}.png')
    assert Image.open(tmp_path/f'multivari{n_factors}.png').width >= 1000
    pd.testing.assert_frame_equal(frame, pd.DataFrame(rows, columns=factors+['y']))


def test_multivari_missing_combinations_and_coverage():
    frame = pd.DataFrame({'a': [0, 0, 1], 'b': [0, 1, 0], 'y': [1, 2, 3]})
    result = multi_vari(frame, 'y', ['a', 'b'])
    assert result['coverage'] == .75
    assert result['tables']['组合统计']['N'].tolist() == [1, 1, 1, 0]
    assert result['tables']['组合统计']['SD'].isna().all()
    with pytest.raises(ValueError, match='60%'):
        multi_vari(frame.iloc[1:], 'y', ['a', 'b'])


def test_internal_column_names_and_random_runs_reference():
    from statsmodels.sandbox.stats.runs import runstest_1samp
    counts = pareto_chart(pd.DataFrame({'_count': ['A', 'B', 'A']}), '_count', threshold=None)
    assert counts['tables']['分组 全部']['类别'].tolist() == ['A', 'B']
    result = multi_vari(pd.DataFrame({'_y': ['A', 'A', 'B', 'B'], 'v': [1, 3, 5, 7]}), 'v', ['_y'])
    assert result['tables']['组合统计']['均值'].tolist() == [2, 6]
    y = np.random.default_rng(20261023).permutation(100)
    result = run_chart(pd.DataFrame({'y': y}), 'y')
    ref_z, ref_p = runstest_1samp(y, cutoff='median', correction=False)
    assert result['tables']['随机性检验'].iloc[0]['Z'] == pytest.approx(ref_z)
    assert min(result['tables']['随机性检验'].iloc[0][['左尾 p', '右尾 p']])*2 == pytest.approx(ref_p)
    grouped = pareto_chart(pd.DataFrame({'c': ['A', 'B'], 'g': [1, '1']}), 'c', group='g')
    assert len(grouped['tables']) == 2
