"""第二批数值修复：独立解析参考及最小反例，不冻结错误输出。"""
from math import gamma, sqrt

import numpy as np
import pytest
from scipy.stats import t

import GRR
import control_chart as chart
from one_way_ANOVA import JMP_ANOVA_t_test
from utilities import d2_2D


def test_lsd_error_df_and_significance():
    # SSE=3/2，MSE=1/2；H0: mu_A=mu_B，双侧、未校正的 Fisher LSD。
    lines = []
    result = JMP_ANOVA_t_test([[1, 2], [3, 4], [5, 6]], list('ABC'),
                              print_out=True, print_port=lines.append)
    assert result['p'][0, 1] == pytest.approx(2 * t.sf(sqrt(8), 3))
    assert result['p'][0, 1] == pytest.approx(.0662756, abs=1e-7)
    assert result['p'][0, 1] > .05
    assert any(0 in group and 1 in group for group in result['groups'])
    assert not any(0 in group and 2 in group for group in result['groups'])
    assert '自由度 = 3' in '\n'.join(map(str, lines))


@pytest.mark.parametrize('data', [[], [[1, 2]], [[], [1, 2]], [[1], [2]],
                                      [[1, 1], [2, 2]], [[1, float('nan')], [2, 3]]])
def test_lsd_rejects_unestimable_inputs(data):
    with pytest.raises(ValueError):
        JMP_ANOVA_t_test(data, list(range(len(data))))


def test_lsd_singleton_group_with_positive_error_df():
    result = JMP_ANOVA_t_test([[1], [2, 3]], ['A', 'B'])
    assert result['p'][0, 1] == pytest.approx(2 * t.sf(sqrt(3), 1))


@pytest.mark.parametrize('n,k', [(1, 2), (0, 1), (-1, 1), (2, 0), (2, -1),
                                    (2.5, 1), (2, 1.5), (True, 1), (2, True),
                                    (float('nan'), 1), (2, float('inf'))])
def test_d2_rejects_invalid_dimensions(n, k):
    with pytest.raises(ValueError, match='d2'):
        d2_2D(n, k)


@pytest.mark.parametrize('n,k,expected', [(2, 1, 1.414), (3, 2, 1.809),
                                             (2, 4, 1.206), (15, 16, 3.472),
                                             (20, 30, 3.472)])
def test_d2_preserves_tabulated_constants(n, k, expected):
    assert d2_2D(n, k) == expected


@pytest.mark.parametrize('mode', ['xbar', 'aiag', 'emp'])
@pytest.mark.parametrize('inter', ['auto', 'off', 'on'])
def test_grr_rejects_single_replicates(mode, inter):
    with pytest.raises(ValueError, match='两次重复'):
        GRR.grr_master(y=[1, 2, 3, 4], part=['A', 'B'] * 2,
                       op=['X', 'X', 'Y', 'Y'], mode=mode, inter=inter)


def test_grr_ev_uses_repeat_dimension():
    # 四个组合各重复两次，极差均为 2；表格常数 d2*(2,4)=1.206。
    result = GRR.grr_xbar_r(y=[1, 3, 5, 7, 2, 4, 6, 8],
                            part=['A', 'A', 'B', 'B'] * 2,
                            op=['X'] * 4 + ['Y'] * 4)
    assert result['EV'] == pytest.approx((2 / 1.206)**2)


@pytest.mark.parametrize('method', [GRR.grr_inter, GRR.grr_simple])
def test_direct_grr_anova_rejects_single_replicates(method):
    with pytest.raises(ValueError, match='两次重复'):
        method([1, 2, 3, 4], ['X', 'X', 'Y', 'Y'], ['A', 'B'] * 2)


@pytest.mark.parametrize('method', [GRR.grr_no_op, GRR.grr_xbar_r])
def test_grr_without_operator_rejects_single_replicates(method):
    with pytest.raises(ValueError, match='两次重复'):
        if method is GRR.grr_no_op:
            method([1, 2], ['A', 'B'])
        else:
            method(y=[1, 2], part=['A', 'B'])


@pytest.mark.parametrize('entry', ['GRR_xbar', 'grr_xbar_r', 'grr_inter', 'grr_simple',
                                  'grr_anova_AIAG', 'grr_anova_EMP',
                                  'master_aiag', 'master_emp', 'master_xbar'])
@pytest.mark.parametrize('counts,reason', [([2, 3, 3, 3], '重复次数一致'),
                                          ([2, 2, 2, 0], '缺少'),
                                          ([2, 2, 0, 0], '两个操作者'),
                                          ([2, 0, 2, 0], '两个零件'),
                                          ([1, 1, 1, 1], '两次重复')])
def test_grr_crossed_design_rejected_before_calculation(monkeypatch, entry, counts, reason):
    import pandas as pd
    parts, ops, y = [], [], []
    for (operator, part), count in zip([('X', 'A'), ('X', 'B'), ('Y', 'A'), ('Y', 'B')], counts):
        parts.extend([part] * count)
        ops.extend([operator] * count)
        y.extend(range(count))
    def unexpected(*args, **kwargs):
        pytest.fail('无效设计不应进入统计计算')
    monkeypatch.setattr(GRR, 'two_way_anova', unexpected)
    monkeypatch.setattr(GRR, 'one_way_anova', unexpected)
    monkeypatch.setattr(GRR, 'd2', unexpected)
    with pytest.raises(ValueError, match=reason):
        if entry == 'GRR_xbar':
            GRR.GRR_xbar(pd.DataFrame({'Y': y, 'Part': parts, 'Operator': ops}), print_out=False)
        elif entry.startswith('master_'):
            GRR.grr_master(y=y, part=parts, op=ops, mode=entry.split('_')[1])
        else:
            getattr(GRR, entry)(y=y, part=parts, op=ops)


@pytest.mark.parametrize('entry', ['GRR_xbar', 'grr_xbar_r', 'grr_no_op',
                                  'grr_anova_AIAG', 'grr_anova_EMP',
                                  'master_aiag', 'master_emp', 'master_xbar'])
@pytest.mark.parametrize('parts,reason', [(['A'] * 4, '两个零件'),
                                        (['A', 'B'], '两次重复'),
                                        (['A']*2+['B']*3, '重复次数一致'),
                                        (['A']*2+['B']*2, None)])
def test_grr_single_factor_design(entry, parts, reason):
    import pandas as pd
    y = list(range(len(parts)))
    def calculate():
        if entry == 'GRR_xbar':
            return GRR.GRR_xbar(pd.DataFrame({'Y': y, 'Part': parts}), has_op_col=False, print_out=False)
        if entry.startswith('master_'):
            return GRR.grr_master(y=y, part=parts, mode=entry.split('_')[1])
        return getattr(GRR, entry)(y=y, part=parts)
    if reason:
        with pytest.raises(ValueError, match=reason):
            calculate()
    else:
        result = calculate()
        if entry == 'grr_no_op':
            assert result == pytest.approx((.5, 0, 0, 1.75))
        else:
            assert list(result) == ['EV', 'AV', 'PV', 'RR', 'TV', 'INT']
            assert result['AV'] == 0
            # 两个零件各两次，组内 SSE=1、df=2；极差法 d2*(2,2)=1.279。
            expected_ev = (1 / 1.279)**2 if 'xbar' in entry.lower() else .5
            assert result['EV'] == pytest.approx(expected_ev)


@pytest.mark.parametrize('method', [chart.xBar_R, chart.xBar_S])
@pytest.mark.parametrize('groups,df,sse', [([[1, 3]], 1, 2),
                                         ([[1, 3], [2, 4, 6]], 3, 10)])
def test_pooled_sigma_and_limits(method, groups, df, sse):
    # 正态误差：sqrt(SSE/df) 的期望偏差为 E[chi_df]/sqrt(df)。
    correction = sqrt(2 / df) * gamma((df + 1) / 2) / gamma(df / 2)
    sigma = sqrt(sse / df) / correction
    result = method(groups, pooled=True)
    mean = np.mean([v for group in groups for v in group])
    np.testing.assert_allclose(result['ucl1'], [mean + 3*sigma/sqrt(len(g)) for g in groups])
    np.testing.assert_allclose(result['lcl1'], [mean - 3*sigma/sqrt(len(g)) for g in groups])
    if method is chart.xBar_S:
        c = [sqrt(2/(len(g)-1))*gamma(len(g)/2)/gamma((len(g)-1)/2) for g in groups]
        np.testing.assert_allclose(result['bar2'], np.array(c)*sigma)
        np.testing.assert_allclose(result['ucl2'], [sigma*(v+3*sqrt(1-v*v)) for v in c])
        np.testing.assert_allclose(result['lcl2'], [max(0, sigma*(v-3*sqrt(1-v*v))) for v in c])
    else:
        # n=2、3 的标准极差矩常数（既有控制图常数表精度）。
        d2 = [1.128, 1.693][:len(groups)]
        d3 = [.853, .888][:len(groups)]
        np.testing.assert_allclose(result['bar2'], np.array(d2)*sigma, rtol=.001)
        np.testing.assert_allclose(result['ucl2'], (np.array(d2)+3*np.array(d3))*sigma, rtol=.001)
        np.testing.assert_allclose(result['lcl2'], np.maximum(0, (np.array(d2)-3*np.array(d3))*sigma), rtol=.001)


@pytest.mark.parametrize('method', [chart.xBar_R, chart.xBar_S])
def test_nonpooled_and_supplied_sigma_preserved(method):
    # 授权范围外行为与历史源码对照；正确性由上面的独立参考承担。
    from pathlib import Path
    namespace = dict(chart.__dict__)
    source = Path(__file__).parent / 'fixtures/g18_before/control_chart.py'
    exec(compile(source.read_text(encoding='utf-8'), str(source), 'exec'), namespace)
    for kwargs in ({'pooled': False}, {'sigma': 2., 'pooled': True}):
        result = method([[1, 3], [2, 4, 6]], **kwargs)
        expected = namespace[method.__name__]([[1, 3], [2, 4, 6]], **kwargs)
        assert result == expected
