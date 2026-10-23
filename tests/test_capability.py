"""逐方法独立参考：手算、闭式MLE、得分方程、解析CDF/PPF和逆变换。

不以旧 Cpk 或被测函数的往返结果代替统计正确性参考。
"""
from math import erf, erfc, exp, log, pi, sqrt

import numpy as np
import pandas as pd
import pytest
from scipy import integrate, optimize, special, stats

from capability import analyze_capability, transform_values


def normal_cdf(x):
    return .5*(1+erf(x/sqrt(2)))


def test_normal_mr_order_indices_ppm_and_no_target():
    x = np.array([8., 11., 9., 12., 10.])
    res = analyze_capability(x, lsl=9, usl=11)
    sw = (3+2+3+2)/4/(2/sqrt(pi))
    so = sqrt(10/4)
    assert res['mean'] == 10
    assert res['within_sigma'] == pytest.approx(sw)
    assert res['overall_sigma'] == pytest.approx(so)
    for key, expected in dict(Cp=2/(6*sw), Cpl=1/(3*sw), Cpu=1/(3*sw),
                              Cpk=1/(3*sw), Pp=2/(6*so), Ppk=1/(3*so)).items():
        assert res['indices'][key] == pytest.approx(expected)
    assert res['indices']['Cpm'] is None and res['target'] is None
    assert res['ppm']['observed'] == dict(lower=200000., upper=200000., total=400000.)
    ppm_table = res['tables']['PPM'].set_index('类型')
    assert ppm_table.loc['实测', ['下侧超规率', '上侧超规率', '合计超规率']].tolist() == [1/5, 1/5, 2/5]
    assert ppm_table.loc['实测', ['下侧实测计数', '上侧实测计数', '合计实测计数']].tolist() == [1, 1, 2]
    assert ppm_table.loc['预计（整体）', ['下侧实测计数', '上侧实测计数', '合计实测计数']].isna().all()
    assert ppm_table.loc['预计（整体）', '合计超规率'] == pytest.approx(normal_cdf(-1/so)*2)
    for key, sigma in [('within', sw), ('overall', so)]:
        assert res['ppm'][key]['lower'] == pytest.approx(normal_cdf(-1/sigma)*1e6)
        assert res['ppm'][key]['upper'] == pytest.approx(erfc(1/sigma/sqrt(2))*.5e6)
    assert res['intervals']['Cp'] == (None, None)
    assert res['sigma_ci']['within'] == (None, None)
    assert res['intervals']['Cpk'] == (None, None)
    np.testing.assert_array_equal(res['data'], x)
    assert res['within_sigma'] != analyze_capability(sorted(x), usl=11)['within_sigma']


def test_pooled_c4_and_exact_ci_uses_uncorrected_sp():
    x = [1., 3., 5., 7., 4., 8.]
    res = analyze_capability(x, lsl=0, usl=12, subgroup_size=2, target=5, confidence=.9)
    # Within SS=2+2+8=12, df=3. E[chi(3)]/sqrt(3)=c4(4).
    sp = 2.
    correction = 2*sqrt(2/pi)/sqrt(3)
    assert res['within_sigma'] == pytest.approx(sp/correction)
    overall = sqrt(sum((value-14/3)**2 for value in x)/5)
    assert res['overall_sigma'] == pytest.approx(overall)
    assert res['indices']['Cpm'] == pytest.approx(12/(6*sqrt(overall**2+(14/3-5)**2)))
    # Invert independent chi-square quantiles, not the bias-corrected estimator.
    lower, upper = stats.chi2.ppf([.05, .95], 3)
    np.testing.assert_allclose(res['sigma_ci']['within'], [sp*sqrt(3/upper), sp*sqrt(3/lower)])
    np.testing.assert_allclose(res['intervals']['Cp'], [12/(6*sp)*sqrt(lower/3), 12/(6*sp)*sqrt(upper/3)])
    low, high = stats.chi2.ppf([.05, .95], 5)
    np.testing.assert_allclose(res['intervals']['Pp'], [12/(6*overall)*sqrt(low/5), 12/(6*overall)*sqrt(high/5)])
    assert '未修正sp' in res['tables']['能力指数'].query("指标 == 'Cp'")['区间方法'].iloc[0]


@pytest.mark.parametrize('side', ['lower', 'upper'])
def test_one_sided_negative_index_and_extreme_normal_tail(side):
    x = np.array([-2., -1., 0., 1., 2.])
    kwargs = {'lsl': 1.} if side == 'lower' else {'usl': -1.}
    r = analyze_capability(x, **kwargs)
    assert r['indices']['Cp'] is None and r['indices']['Pp'] is None
    assert r['indices']['Ppk'] < 0
    assert r['indices']['Cpm'] is None
    r = analyze_capability(x, usl=10*np.std(x, ddof=1))
    assert r['ppm']['overall']['upper'] == pytest.approx(erfc(10/sqrt(2))*.5e6, rel=1e-13)
    assert r['ppm']['overall']['upper'] > 0
    assert r['z']['Z_upper'] == pytest.approx(10)


@pytest.fixture(scope='module')
def fitted_lognormal():
    # Specified log-values give a closed-form zero-location lognormal MLE.
    logs = stats.norm.ppf((np.arange(1, 81)-.5)/80)*.7+1.2
    x = np.exp(logs)
    return x, analyze_capability(x, lsl=.5, usl=8., distribution='lognormal')


def test_lognormal_closed_mle_percentile_and_z_are_distinct(fitted_lognormal):
    x, r = fitted_lognormal
    m = sum(log(value) for value in x)/len(x)
    s = sqrt(sum((log(value)-m)**2 for value in x)/len(x))
    assert r['fit']['parameters']['shape'] == pytest.approx(s)
    assert r['fit']['parameters']['scale'] == pytest.approx(exp(m))
    ql, median, qu = exp(m-3*s), exp(m), exp(m+3*s)
    assert r['indices']['Pp'] == pytest.approx(7.5/(qu-ql))
    assert r['indices']['Ppl'] == pytest.approx((median-.5)/(median-ql))
    assert r['indices']['Ppu'] == pytest.approx((8-median)/(qu-median))
    assert r['indices']['Ppk'] == pytest.approx(min((median-.5)/(median-ql), (8-median)/(qu-median)))
    assert r['indices']['Cp'] is None and r['indices']['Cpk'] is None
    assert r['z']['Z_upper'] == pytest.approx((log(8)-m)/s)
    assert r['z']['Z_lower'] == pytest.approx((m-log(.5))/s)
    assert r['indices']['Ppk'] != pytest.approx(min(r['z']['Z_lower'], r['z']['Z_upper'])/3)
    assert r['ppm']['overall']['upper'] == pytest.approx(erfc((log(8)-m)/s/sqrt(2))*.5e6)
    assert r['intervals']['Pp'] == (None, None)
    assert '重拟合' in r['fit']['method'] and r['fit']['bootstrap_replicates'] == 199
    assert 0 < r['fit']['p_value'] <= 1


def test_weibull_score_and_analytic_tails():
    x = np.array([.7, 1.1, 1.5, 2.2, 2.7, 3., 4., 5.2, 7., 8.1])
    r = analyze_capability(x, lsl=-1, usl=9, distribution='weibull')
    shape, scale = r['fit']['parameters']['shape'], r['fit']['parameters']['scale']
    lx = np.log(x)
    # Independent shape score: 1/c + mean(log x) - sum(x^c log x)/sum(x^c)=0.
    score = lambda c: 1/c + np.mean(lx) - np.sum(x**c*lx)/np.sum(x**c)
    root = optimize.brentq(score, .1, 10)
    assert shape == pytest.approx(root, rel=1e-4)
    assert scale == pytest.approx(np.mean(x**root)**(1/root), rel=1e-4)
    assert r['ppm']['overall']['lower'] == 0
    assert r['ppm']['overall']['upper'] == pytest.approx(exp(-(9/scale)**shape)*1e6)
    p = normal_cdf(-3)
    q = lambda probability: scale*(-log(1-probability))**(1/shape)
    assert r['indices']['Pp'] == pytest.approx(10/(q(1-p)-q(p)), rel=1e-11)
    assert np.isposinf(r['z']['Z_lower'])


def test_gamma_score_and_independent_integral():
    x = np.array([.01, .05, .2, .3, .6, 1., 2., 4., 6., 8.])
    r = analyze_capability(x, usl=3, distribution='gamma')
    mean = sum(x)/len(x)
    target = log(mean)-sum(log(value) for value in x)/len(x)
    root = optimize.brentq(lambda a: log(a)-special.digamma(a)-target, .01, 100)
    shape, scale = r['fit']['parameters']['shape'], r['fit']['parameters']['scale']
    assert shape < 1
    assert shape == pytest.approx(root)
    assert scale == pytest.approx(mean/root)
    density = lambda t: t**(root-1)*exp(-t/scale)/(special.gamma(root)*scale**root)
    tail, _ = integrate.quad(density, 3, np.inf, epsabs=1e-12)
    assert r['ppm']['overall']['upper'] == pytest.approx(tail*1e6, rel=1e-10)
    # Quantiles obtained from an integrated density + root solver.
    cdf = lambda value: integrate.quad(density, 0, value, epsabs=1e-10)[0]
    median = optimize.brentq(lambda t: cdf(t)-.5, .001, 30)
    high = optimize.brentq(lambda t: cdf(t)-normal_cdf(3), 3, 100)
    assert r['indices']['Ppk'] == pytest.approx((3-median)/(high-median), rel=1e-8)
    assert r['indices']['Pp'] is None


def test_nonnormal_support_domain_extreme_tails_and_failure(monkeypatch):
    x = np.exp(np.linspace(-1, 1, 40))
    r = analyze_capability(x, usl=-1, distribution='lognormal')
    assert r['ppm']['overall']['upper'] == 1e6
    assert np.isneginf(r['z']['Z_upper'])
    assert np.isneginf(r['z']['Z_bench'])
    assert r['indices']['Ppk'] < 0
    r = analyze_capability(x, usl=exp(10*np.std(np.log(x))), distribution='lognormal')
    assert r['ppm']['overall']['upper'] == pytest.approx(erfc(10/sqrt(2))*.5e6)
    monkeypatch.setattr(stats.gamma, 'fit', lambda *args, **kwargs: (np.nan, 0, 1))
    with pytest.raises(ValueError, match='拟合失败'):
        analyze_capability(x, usl=2, distribution='gamma')


def test_bad_nonnormal_fit_is_flagged_and_bootstrap_is_repeatable():
    x = np.r_[np.linspace(1, 1.05, 40), np.linspace(9.95, 10, 40)]
    r = analyze_capability(x, usl=12, distribution='lognormal')
    assert r['fit']['mismatch']
    assert any('失配' in item for item in r['warnings'])
    assert r['fit']['p_value'] == analyze_capability(x, usl=12, distribution='lognormal')['fit']['p_value']


@pytest.mark.parametrize('lam', [0., 1e-12, -1e-12, 1., -1., .5])
def test_boxcox_analytic_forward_inverse(lam):
    x = np.array([.2, .7, 1., 2., 8.])
    p = dict(method='boxcox', **{'lambda': lam})
    expected = np.log(x) if lam == 0 else np.expm1(lam*np.log(x))/lam
    np.testing.assert_allclose(transform_values(x, p), expected, atol=1e-14)
    # Inverse compared directly with externally specified y, not a round-trip.
    y = np.array([-.2, 0, .2])
    inverse = np.exp(y) if lam == 0 else np.exp(np.log1p(lam*y)/lam)
    np.testing.assert_allclose(transform_values(y, p, inverse=True), inverse)


def test_boxcox_log_specs_ppm_and_original_quantiles():
    y = stats.norm.ppf((np.arange(1, 81)-.5)/80)*.4+1
    x = np.exp(y)
    r = analyze_capability(pd.Series(x), lsl=exp(.2), usl=exp(1.8), target=exp(1.1),
                           transform='boxcox', fixed_lambda=0)
    np.testing.assert_allclose(r['data'], y)
    assert r['lsl'] == pytest.approx(.2) and r['usl'] == pytest.approx(1.8)
    assert r['target'] == pytest.approx(1.1)
    assert r['ppm']['observed']['total'] == np.mean((y<.2)|(y>1.8))*1e6
    std = sqrt(sum((value-1)**2 for value in y)/(len(y)-1))
    assert r['original_quantiles']['lower'] == pytest.approx(exp(1-3*std))
    assert r['original_quantiles']['upper'] == pytest.approx(exp(1+3*std))
    assert r['intervals']['Pp'] == (None, None)
    assert r['sigma_ci']['overall'] == (None, None)
    np.testing.assert_allclose(r['original'], x)


def test_boxcox_mle_matches_profile_likelihood_and_domain_extrapolation():
    x = np.exp(stats.norm.ppf((np.arange(1, 101)-.5)/100)*.5 + np.linspace(-.2,.4,100)**2)
    r = analyze_capability(x, transform='boxcox', allow_no_specs=True)
    # Independent profile likelihood using explicit expm1 formula and Jacobian.
    lx = np.log(x)
    def nll(lam):
        y = lx if lam == 0 else np.expm1(lam*lx)/lam
        return len(x)/2*log(np.var(y))-(lam-1)*sum(lx)
    optimum = optimize.minimize_scalar(nll, bounds=(-1, 1), method='bounded',
                                       options={'xatol': 1e-11}).x
    assert r['transform']['lambda'] == pytest.approx(optimum, abs=1e-6)
    assert r['z']['Z_bench'] is None and r['ppm']['overall']['total'] is None
    assert r['tables']['PPM'][['合计超规率', '合计实测计数']].isna().all().all()
    y = 1+stats.norm.ppf((np.arange(1, 101)-.5)/100)*.6
    # lambda=1 -> x-1. Normal model has positive probability below x=0.
    positive = y[y > 0]
    fixed = analyze_capability(positive, transform='boxcox', fixed_lambda=1, allow_no_specs=True)
    assert fixed['fit']['outside_transform_domain_probability'] > 0
    assert any('像域外' in item for item in fixed['warnings'])
    assert fixed['original_quantiles']['lower'] is None


def test_johnson_analytic_parameters_and_mle_score():
    p = dict(method='johnson', a=.7, b=1.3, loc=-2., scale=2.5)
    x = np.array([-10., -2., 0., 12.])
    np.testing.assert_allclose(transform_values(x, p), [.7+1.3*np.arcsinh((v+2)/2.5) for v in x])
    z = np.array([-2., 0, 1.])
    np.testing.assert_allclose(transform_values(z, p, inverse=True), [-2+2.5*np.sinh((v-.7)/1.3) for v in z])
    q = stats.norm.ppf((np.arange(1, 161)-.5)/160)
    data = -2+2.5*np.sinh((q-.7)/1.3)
    r = analyze_capability(data, lsl=-10, usl=3, target=-2, transform='johnson')
    fitted = r['transform']
    a, b, loc, scale = [fitted[key] for key in ('a', 'b', 'loc', 'scale')]
    assert b > 0 and scale > 0
    assert r['lsl'] == pytest.approx(a+b*np.arcsinh((-10-loc)/scale))
    assert r['usl'] == pytest.approx(a+b*np.arcsinh((3-loc)/scale))
    # Independent SU log likelihood from Jacobian + standard normal density.
    def nll(theta):
        aa, bb, ll, ss = theta
        t = (data-ll)/ss
        zz = aa+bb*np.arcsinh(t)
        return float(np.sum(.5*zz**2+.5*np.log1p(t*t)+log(ss)-log(bb)))
    theta = np.array([a,b,loc,scale])
    for i in range(4):
        step = np.zeros(4)
        step[i] = 1e-5
        assert abs((nll(theta+step)-nll(theta-step))/(2e-5)) < 1e-3
    assert any('Chou' in item for item in r['warnings'])
    assert r['ppm']['observed']['lower'] == pytest.approx(np.mean(data < -10)*1e6)
    assert all(r['indices'][key] is None for key in ('Cp','Cpl','Cpu','Cpk','Cpm'))
    assert 'within' not in r['ppm']


def test_transform_domain_bad_parameters_and_no_qualified_transform(monkeypatch):
    with pytest.raises(ValueError, match='逆变换'):
        transform_values([-2], dict(method='boxcox', **{'lambda': 1}), inverse=True)
    with pytest.raises(ValueError, match='严格为正'):
        transform_values([0], dict(method='boxcox', **{'lambda': 0}))
    with pytest.raises(ValueError, match='参数'):
        transform_values([1], dict(method='johnson', a=0, b=0, loc=0, scale=1))
    with pytest.raises(ValueError, match='溢出'):
        transform_values([1000], dict(method='boxcox', **{'lambda': 0}), inverse=True)
    x = np.r_[np.ones(30), np.full(30, 10.)]
    with pytest.raises(ValueError, match='无合格变换'):
        analyze_capability(x, usl=12, transform='boxcox', fixed_lambda=1)
    def fail(*args, **kwargs):
        raise RuntimeError('solver failed')
    monkeypatch.setattr(stats.johnsonsu, 'fit', fail)
    with pytest.raises(ValueError, match='未收敛'):
        analyze_capability([1., 2., 3.], usl=4, transform='johnson')


def test_source_missing_and_ids_preserved_without_regrouping():
    index = pd.Index([1234567890123456789, 2, 3, 4, 5, 6])
    x = pd.Series([1., 2., None, 4., 5., 6.], index=index)
    ids = pd.Series(['01','01','01', 1234567890123456789,1234567890123456789,1234567890123456789], index=index)
    with pytest.raises(ValueError, match='缺失'):
        analyze_capability(x, usl=8, subgroup_ids=ids)
    r = analyze_capability(x, usl=8, subgroup_ids=ids, missing='drop')
    assert [list(group) for group in r['groups']] == [[1.,2.], [4.,5.,6.]]
    assert r['source_row'].tolist() == [1,2,4,5,6]
    assert r['source_index'][0] == 1234567890123456789
    assert r['subgroup_ids'][0] == '01' and r['subgroup_ids'][-1] == 1234567890123456789
    frame = r['tables']['来源观测']
    assert frame['subgroup_id'].tolist() == ['01','01']+['1234567890123456789']*3
    assert frame.source_index.iloc[0] == 1234567890123456789
    fixed = analyze_capability([1.,2.,np.nan,4.,5.,6.], usl=9, subgroup_size=3, missing='drop')
    assert [list(group) for group in fixed['groups']] == [[1.,2.], [4.,5.,6.]]
    assert any('删除 1' in item for item in fixed['warnings'])
    assert x.isna().sum() == 1 and ids.iloc[0] == '01'


@pytest.mark.parametrize('data,kwargs,match', [
    ([1.,2.,3.], dict(lsl=4,usl=2), 'LSL < USL'),
    ([1.,2.,3.], {}, '一侧规格'),
    ([1.,2.,3.], dict(allow_no_specs=True), '一侧规格'),
    ([1.,2.,3.], dict(usl=np.inf), '有限'),
    ([1.,2.,3.], dict(usl=4, confidence=1), '置信水平'),
    ([1.,2.,3.], dict(usl=4,k=0), 'K'),
    ([1.,2.], dict(usl=4), '不足'),
    ([1.,1.,1.], dict(usl=4), '常数'),
    ([1.,np.inf,3.], dict(usl=4,missing='drop'), '有限'),
    ([1.,'2',3.], dict(usl=4), '实数'),
    ([1.,2.,3.], dict(usl=4,subgroup_size=2), '余数'),
    ([1.,2.,3.], dict(usl=4,subgroup_size=True), '正整数'),
    ([1.,2.,3.], dict(usl=4,subgroup_ids=['a','b','a']), '不连续'),
    ([1.,2.,3.], dict(usl=4,subgroup_ids=['a','a','b']), '混合'),
    ([1.,2.,3.], dict(usl=4,subgroup_ids=['a']), '长度'),
    ([1.,1.,2.,2.], dict(usl=4,subgroup_size=2), '组内波动'),
    ([0.,1.,2.], dict(usl=4,distribution='gamma'), '严格为正'),
    ([1.,2.,3.], dict(usl=4,transform='boxcox',distribution='gamma'), '不能同时变换'),
    ([1.,2.,3.], dict(usl=4,fixed_lambda=0), '仅适用'),
    ([1.,2.,3.], dict(usl=4,missing='fill'), 'missing'),
    ([1.,2.,3.], dict(usl=4,distribution='unknown'), '分布'),
    ([1.,2.,3.], dict(usl=4,transform='unknown'), '变换'),
])
def test_invalid_inputs(data, kwargs, match):
    with pytest.raises(ValueError, match=match):
        analyze_capability(data, **kwargs)


def test_tables_and_consumers_contract(fitted_lognormal):
    _, r = fitted_lognormal
    assert {'摘要','能力指数','PPM','拟合诊断','变换参数','来源观测'} <= r['tables'].keys()
    assert all(isinstance(table, pd.DataFrame) for table in r['tables'].values())
    assert all(value is None or isinstance(value, (float, np.floating)) for value in r['indices'].values())
    assert isinstance(r['data'], np.ndarray) and all(isinstance(g, np.ndarray) for g in r['groups'])
    assert r['model'].dist.name == 'lognorm'
    assert r['fit']['converged']
    normal = analyze_capability([-1.,0.,1.,2.,3.], usl=5, target=999)
    assert normal['target'] == 999 and normal['indices']['Cpm'] is None
    assert normal['fit']['p_value'] is None
    assert any('小样本' in text for text in normal['warnings'])


@pytest.mark.parametrize('side', ['lower', 'upper'])
def test_exact_one_sided_nct_intervals(side):
    x = np.array([1.,2.,3.,4.,6.,8.])
    kwargs = dict(lsl=2) if side == 'lower' else dict(usl=2)
    key = 'Ppl' if side == 'lower' else 'Ppu'
    r = analyze_capability(x, confidence=.9, k=5, **kwargs)
    mean = sum(x)/len(x)
    s = sqrt(sum((v-mean)**2 for v in x)/(len(x)-1))
    t = (mean-2 if side=='lower' else 2-mean)*sqrt(len(x))/s
    lower, upper = r['intervals'][key]
    assert lower < r['indices'][key] < upper
    # Independent defining coverage equations, including negative tstat.
    assert stats.nct.cdf(t, len(x)-1, lower*2.5*sqrt(len(x))) == pytest.approx(.95, abs=1e-12)
    assert stats.nct.cdf(t, len(x)-1, upper*2.5*sqrt(len(x))) == pytest.approx(.05, abs=1e-12)


def test_numeric_parameters_sigma_and_raw_diagnostics_are_exportable():
    x = np.exp(stats.norm.ppf((np.arange(1,81)-.5)/80)*.5)
    r = analyze_capability(x, lsl=.1, usl=5, transform='boxcox', fixed_lambda=0)
    assert pd.api.types.is_numeric_dtype(r['tables']['拟合参数']['估计值'])
    assert '原始正态性诊断' in r['tables']
    raw = stats.anderson(x, dist='norm')
    assert r['fit']['original_normality']['AD'] == pytest.approx(raw.statistic)
    assert r['tables']['标准差区间']['置信下限'].isna().all()
    plain = analyze_capability([1.,2.,3.,4.,5.,6.], usl=8, subgroup_size=2)
    table = plain['tables']['标准差区间']
    assert table['置信下限'].notna().all()
