"""REVIEW-009/010/011：独立数学参考与真实生产路径的最小反例。"""
from types import SimpleNamespace

import numpy as np
import pytest
from matplotlib.figure import Figure
from scipy.integrate import quad
from scipy.stats import chi2, norm

import cpk as legacy_cpk
import ortho_fit
from capability import analyze_capability
from capability_plots import control_diagnostics, plot_capability
from control_chart import xBar_R
from cpk_plot import cpk_plot
from ctrl_chart_const import df as constants


@pytest.mark.parametrize('x,y,ratio', [
    ([-2, -1, 0, 1, 2], [0, 1, 0, 1, 0], 1),
    ([1, 2, 4, 5, 7, 8], [2, 4, 3, 8, 6, 10], 1.3),
    ([1, 2, 4, 5, 7, 8], [10, 6, 8, 3, 4, 2], 1.3),
])
def test_review009_orthogonal_matches_whitened_principal_direction(x, y, ratio):
    # 将 Y 按测量误差缩放，主特征向量给出 Deming 回归方向。
    scaled = np.column_stack((x, np.asarray(y) / np.sqrt(ratio)))
    _, vectors = np.linalg.eigh(np.cov(scaled, rowvar=False))
    direction = vectors[:, -1]
    slope = np.sqrt(ratio) * direction[1] / direction[0]
    result = ortho_fit.orthogonal_fit(x, y, error_ratio=ratio, print_out=False)
    assert result['slope'] == pytest.approx(slope, abs=1e-12)
    assert result['intercept'] == pytest.approx(np.mean(y) - slope * np.mean(x))
    assert np.isfinite(result['St Resid']).all()
    assert result['Var E'] == ratio * result['Var U']
    if slope == 0:
        assert result['intercept'] == pytest.approx(.4)


@pytest.mark.parametrize('x,y,message', [
    ([0, 1, 0, 1, 0], [-2, -1, 0, 1, 2], '竖直'),
    ([1, -1, 0, 0], [0, 0, 1, -1], '方向不可识别'),
    ([-2, -1, 0, 1, 2], [0, 1, np.nan, 1, 0], '有限'),
    ([-2, -1, 0, 1, 2], [0, 1e-10, 0, 1e-10, 1e-10], '残差'),
])
def test_review009_invalid_direction_stops_before_diagnostics(monkeypatch, x, y, message):
    def unexpected_diagnostic(*args, **kwargs):
        pytest.fail('无效拟合不应进入正态性诊断')
    monkeypatch.setattr(ortho_fit, 'norm_test', unexpected_diagnostic)
    with np.errstate(divide='ignore', invalid='ignore'), pytest.raises(ValueError, match=message):
        ortho_fit.orthogonal_fit(x, y, print_out=False)


def noncentral_t_cdf_integral(t, df, delta):
    # T=(Z+delta)/sqrt(V/df)，Z~N(0,1)、V~chi2(df)，相互独立。
    value, error = quad(lambda v: norm.cdf(t * np.sqrt(v / df) - delta) * chi2.pdf(v, df),
                        0, np.inf, epsabs=1e-10, epsrel=1e-10)
    assert error < 1e-8
    return value


def test_review010_signed_intervals_satisfy_independent_coverage_and_report():
    data = [-2, -1, 0, 1, 2]
    negative = legacy_cpk.cpk(data, target=-15, lsl=-20, usl=-10, print_out=False)['Overall']
    positive = legacy_cpk.cpk(data, target=0, lsl=-10, usl=10, print_out=False)['Overall']
    reflected = legacy_cpk.cpk(data, target=15, lsl=10, usl=20, print_out=False)['Overall']
    bounds = [negative['cpu_l'], negative['cpu_u']]
    np.testing.assert_allclose(bounds, [-3.544270004, -.696017773], atol=1e-9, rtol=0)
    np.testing.assert_allclose([reflected['cpl_l'], reflected['cpl_u']], bounds, atol=1e-11)
    np.testing.assert_allclose([positive['cpu_l'], positive['cpu_u']], -np.asarray(bounds)[::-1])
    for result in (negative, positive, reflected):
        for side in ('cpu', 'cpl'):
            t = result[side] * 3 * np.sqrt(5)
            for suffix, probability in (('_l', .975), ('_u', .025)):
                delta = result[side + suffix] * 3 * np.sqrt(5)
                assert noncentral_t_cdf_integral(t, 4, delta) == pytest.approx(probability, abs=1e-8)
    output = []
    cpk_plot(data, target=-15, lsl=-20, usl=-10, print_out=True,
             ax=Figure().subplots(), print_port=output.append)
    text = '\n'.join(map(str, output))
    assert '-3.544' in text and '-0.696' in text


@pytest.mark.parametrize('solution', [
    SimpleNamespace(converged=False, root=0.),
    SimpleNamespace(converged=True, root=np.nan),
    SimpleNamespace(converged=True, root=0.),
])
def test_review010_unreliable_roots_are_unavailable(monkeypatch, solution):
    monkeypatch.setattr(legacy_cpk, 'root_scalar', lambda *args, **kwargs: solution)
    assert np.isnan(legacy_cpk.cpl_cpu_95(-2., 5, 4)).all()


def test_review011_five_point_range_limits_and_actual_sixpack_alarm():
    # Review 的独立正态极值联合密度积分 d3(5)=.8640819411；表按四位小数存储。
    d3_reference = .8640819411
    assert constants.loc[5, 'd3'] == pytest.approx(d3_reference, abs=5e-5)
    data = [0, 0, 0, 0, 5] + [0] * 20
    groups = np.reshape(data, (5, 5)).tolist()
    chart = xBar_R(groups)
    assert chart['ucl2'][0] == pytest.approx(1 + 3 * .8641 / 2.326)
    assert chart['Y2'][0] == 5 > chart['ucl2'][0]
    result = analyze_capability(data, lsl=-10, usl=10, subgroup_size=5)
    # 当前合并组内估计 sp/c4(21)；chi 分布均值给出独立 c4 参考。
    from scipy.stats import chi
    sigma = 1 / (chi.mean(20) / np.sqrt(20))
    expected_ucl = (2.326 + 3 * .8641) * sigma
    assert expected_ucl == pytest.approx(4.9801387368)
    ranges = control_diagnostics(result).query("chart == 'R 极差图'")
    np.testing.assert_allclose(ranges.ucl, expected_ucl)
    assert ranges.outside.tolist() == [True, False, False, False, False]
    figure = plot_capability(result)
    alarms = next(line for line in figure.axes[2].lines if line.get_label() == '超控制限')
    np.testing.assert_array_equal(alarms.get_xdata(), [1])
    np.testing.assert_array_equal(alarms.get_ydata(), [5])
