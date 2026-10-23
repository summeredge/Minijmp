"""逐方法独立参考证据（生产入口均为 analyze_time_series）。

correlation/acf -> test_acf_*: 全局中心化内积，Bartlett 方差公式；不调用 acf。
correlation/pacf -> test_pacf_*: Toeplitz 正规方程独立求解，不调用 pacf。
correlation/ccf -> test_ccf_*: 逐滞后手工 Pearson，非对称领先信号反例。
decomposition/trend -> test_trend_*: 最小二乘闭式及残差均方/t 分布。
decomposition/seasonal -> test_decomposition_*: 已知线性趋势/周期项；奇偶周期。
stationarity/ADF -> test_adf_*: 差分回归的独立正规方程 t 值，固定滞后。
stationarity/KPSS -> test_kpss_*: 累积残差平方 / Bartlett 长期方差。
ARIMA/SARIMA -> test_*forecast*: 白噪声、AR(1)、随机游走、季节AR(1)的
解析条件均值/创新传播方差/z区间；使用拟合参数核对传播，不以同模型自比。
model/diagnostics -> test_ljung_box_*: n(n+2)sum(r_k²/(n-k))及chi²尾概率。
model/IC -> test_information_criteria: -2llf+2k / -2llf+log(n_eff)k。
全部证据均同时覆盖列契约、来源不变及关键边界。p/临界值由官方校准表
（ADF MacKinnon/KPSS）提供；检验统计量的计算用公式独立验证。
"""
import threading
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
from numpy.testing import assert_allclose
from pandas.testing import assert_frame_equal
from scipy import stats

import time_series_analysis as tsa
from time_series_analysis import analyze_time_series


def frame(n=80, seed=42):
    return pd.DataFrame({'Y': np.random.default_rng(seed).normal(size=n)})


def analyze(data=None, **kwargs):
    return analyze_time_series(frame() if data is None else data, 'Y', **kwargs)


def manual_acf(values, count):
    z = values - np.mean(values)
    return np.array([sum(z[k:] * z[:len(z)-k]) / sum(z*z) for k in range(count+1)])


@pytest.mark.parametrize('count', [0, 1, 5, 20])
def test_acf_biased_and_bartlett(count):
    data = frame()
    table = analyze(data, analysis='correlation', lags=count).tables['acf']
    expected = manual_acf(data.Y.to_numpy(), count)
    assert_allclose(table.correlation, expected, atol=1e-14)
    variance = np.zeros(count + 1)
    for lag in range(1, count + 1):
        variance[lag] = (1 + 2 * sum(expected[1:lag]**2)) / len(data)
    radius = stats.norm.ppf(.975) * np.sqrt(variance)
    assert_allclose(table.ci_lower, expected-radius)
    assert_allclose(table.ci_upper, expected+radius)
    assert table.n_pairs.tolist() == list(range(len(data), len(data)-count-1, -1))


@pytest.mark.parametrize('count', [0, 1, 6, 15])
def test_pacf_yule_walker_normal_equations(count):
    data = frame()
    table = analyze(data, analysis='correlation', lags=count).tables['pacf']
    rho = manual_acf(data.Y.to_numpy(), count)
    reference = [1.]
    for lag in range(1, count+1):
        matrix = np.array([[rho[abs(i-j)] for j in range(lag)] for i in range(lag)])
        reference.append(np.linalg.solve(matrix, rho[1:lag+1])[-1])
    assert_allclose(table.correlation, reference, atol=2e-14)
    if count:
        assert_allclose(table.ci_upper.iloc[1:]-table.correlation.iloc[1:], stats.norm.ppf(.975)/np.sqrt(len(data)))


@pytest.mark.parametrize('n', [3, 4, 5, 12])
def test_lag_clipping_and_short_correlation(n):
    r = analyze(frame(n), analysis='correlation', lags=100)
    assert r.tables['acf'].lag.max() == n-1
    assert r.tables['pacf'].lag.max() == n//2-1


def pearson(a, b):
    aa = a - sum(a)/len(a)
    bb = b - sum(b)/len(b)
    return sum(aa*bb) / np.sqrt(sum(aa*aa)*sum(bb*bb))


def test_ccf_overlap_pearson_and_positive_direction():
    x = np.array([7, 1, 3, 8, 2, 9, 6, 4, 12, 10, 5, 11.])
    y = np.r_[2., 3., x[:-2]]
    data = pd.DataFrame({'Y': y, 'X': x})
    table = analyze(data, other='X', analysis='correlation', lags=6).tables['ccf'].set_index('lag')
    for k in range(-6, 7):
        indices = [(t, t-k) for t in range(len(y)) if 0 <= t-k < len(x)]
        expected = pearson(np.array([y[t] for t, _ in indices]), np.array([x[j] for _, j in indices]))
        assert table.loc[k, 'correlation'] == pytest.approx(expected)
        assert table.loc[k, 'n_pairs'] == len(indices)
    assert table.loc[2, 'correlation'] == pytest.approx(1.)
    assert table.loc[-2, 'correlation'] < .9
    assert not {'ci_lower', 'ci_upper'} & set(table.columns)


def test_ccf_constant_overlap_is_unavailable_not_zero():
    data = pd.DataFrame({'Y': [1., 2, 3, 4, 5, 6], 'X': [1., 1, 1, 2, 4, 3]})
    table = analyze(data, other='X', analysis='correlation', lags=20).tables['ccf'].set_index('lag')
    assert pd.isna(table.loc[3, 'correlation'])
    assert table.n_pairs.min() == 3


def test_trend_closed_form_inference():
    data = frame(40)
    data.Y += np.arange(40)*.75 + 3
    r = analyze(data, analysis='decomposition')
    x = np.arange(len(data), dtype=float)
    y = data.Y.to_numpy()
    slope = sum((x-x.mean())*(y-y.mean()))/sum((x-x.mean())**2)
    intercept = y.mean()-slope*x.mean()
    e = y-intercept-slope*x
    variance = sum(e*e)/(len(x)-2)
    ses = np.sqrt([variance*(1/len(x)+x.mean()**2/sum((x-x.mean())**2)), variance/sum((x-x.mean())**2)])
    coef = r.tables['trend_coefficients']
    assert coef.term.tolist() == ['intercept', 'slope']
    assert_allclose(coef.coefficient, [intercept, slope])
    assert_allclose(coef.std_error, ses)
    assert_allclose(coef.p_value, 2*stats.t.sf(np.abs(coef.coefficient/ses), len(x)-2))
    assert_allclose(coef.ci_upper, coef.coefficient+stats.t.ppf(.975,len(x)-2)*ses)
    assert_allclose(r.tables['trend'].residual, e)
    assert 'decomposition' not in r.tables


@pytest.mark.parametrize('period', [3, 4, 5, 6])
def test_decomposition_additive_known_signal(period):
    n = period*8
    trend = 12 + np.arange(n)*.2
    seasonal = np.resize(np.arange(period) - (period-1)/2, n)
    r = analyze(pd.DataFrame({'Y': trend+seasonal}), analysis='decomposition', period=period)
    out = r.tables['decomposition']
    good = out.trend.notna()
    assert_allclose(out.trend[good], trend[good], atol=1e-12)
    assert_allclose(out.seasonal, seasonal, atol=1e-12)
    assert_allclose(out.residual[good], 0, atol=1e-12)
    assert out.residual.isna().any()


@pytest.mark.parametrize('period', [3, 4])
def test_decomposition_multiplicative_known_signal(period):
    seasonal = np.resize(np.arange(1, period+1)/np.mean(np.arange(1, period+1)), period*8)
    r = analyze(pd.DataFrame({'Y': 10*seasonal}), analysis='decomposition', period=period, decomposition='multiplicative')
    out = r.tables['decomposition']
    assert_allclose(out.trend.dropna(), 10)
    assert_allclose(out.seasonal, seasonal)
    assert_allclose(out.residual.dropna(), 1)


@pytest.mark.parametrize('lag', [0, 1, 3, 8])
def test_adf_fixed_lags_manual_regression(lag):
    data = frame(120)
    values = data.Y.to_numpy()
    table = analyze(data, analysis='stationarity', lags=lag).tables['stationarity'].set_index('test')
    delta = np.diff(values)
    response = delta[lag:]
    design = np.column_stack([values[lag:-1], *[delta[lag-j:-j] for j in range(1,lag+1)], np.ones(len(response))])
    beta = np.linalg.solve(design.T@design, design.T@response)
    residual = response-design@beta
    covariance = np.linalg.inv(design.T@design)*sum(residual**2)/(len(response)-design.shape[1])
    expected = beta[0]/np.sqrt(covariance[0,0])
    assert table.loc['ADF','statistic'] == pytest.approx(expected, rel=2e-12)
    assert table.loc['ADF','lags'] == lag
    assert table.loc['ADF','nobs'] == len(response)
    assert table.loc['ADF','null'] == '单位根'
    assert table.loc['ADF','critical_1pct'] < table.loc['ADF','critical_5pct'] < table.loc['ADF','critical_10pct']


@pytest.mark.parametrize('lag', [0, 1, 3, 8])
def test_kpss_bartlett_long_run_variance(lag):
    data = frame(120)
    values = data.Y.to_numpy()
    table = analyze(data, analysis='stationarity', lags=lag).tables['stationarity'].set_index('test')
    z = values-values.mean()
    n = len(z)
    long_variance = sum(z*z)/n + 2*sum((1-k/(lag+1))*sum(z[k:]*z[:-k])/n for k in range(1,lag+1))
    expected = sum(np.cumsum(z)**2)/(n*n*long_variance)
    assert table.loc['KPSS','statistic'] == pytest.approx(expected, rel=2e-12)
    assert table.loc['KPSS','lags'] == lag
    assert table.loc['KPSS','null'] == '水平平稳'
    assert table.loc['KPSS','critical_5pct'] == .463


def test_kpss_report_pvalue_bound_and_undecidable_alpha():
    r = analyze(frame(120), analysis='stationarity', lags=2, alpha=.2)
    kp = r.tables['stationarity'].set_index('test').loc['KPSS']
    assert kp.p_value_bound == 'greater_than'
    assert kp.p_value == .1
    assert pd.isna(kp.reject)
    assert any('actual p-value' in note for note in r.notes)


def test_kpss_nonstationary_bound():
    data = frame(200)
    data.Y += np.arange(len(data))*.3
    kp = analyze(data, analysis='stationarity', lags=2).tables['stationarity'].set_index('test').loc['KPSS']
    assert kp.p_value_bound == 'less_than'
    assert kp.reject


@pytest.mark.parametrize('order', [(0,0,0), (1,0,0), (0,1,0)])
def test_arima_analytic_forecast_intervals(order):
    data = frame(300, 14)
    if order == (1,0,0):
        for i in range(1,len(data)):
            data.loc[i,'Y'] += .65*data.loc[i-1,'Y']
    elif order == (0,1,0):
        data.Y = data.Y.cumsum()
    r = analyze(data, analysis='ARIMA', order=order, forecast_steps=8)
    params = dict(zip(r.model.param_names, r.model.params))
    h = np.arange(1,9)
    sigma2 = params['sigma2']
    if order == (0,0,0):
        expected = np.repeat(params['const'], 8)
        variance = np.repeat(sigma2, 8)
        assert params['const'] == pytest.approx(data.Y.mean(), abs=2e-5)
        assert sigma2 == pytest.approx(np.var(data.Y), rel=2e-4)
    elif order == (1,0,0):
        phi, mu = params['ar.L1'], params['const']
        expected = mu + phi**h*(data.Y.iloc[-1]-mu)
        variance = sigma2 * np.array([sum(phi**(2*j) for j in range(i)) for i in h])
    else:
        expected = np.repeat(data.Y.iloc[-1],8)
        variance = sigma2*h
    forecast = r.tables['forecast']
    assert_allclose(forecast.predicted, expected, atol=1e-8)
    assert_allclose(forecast.ci_upper, expected+stats.norm.ppf(.975)*np.sqrt(variance), atol=1e-8)
    assert_allclose(forecast.ci_lower, expected-stats.norm.ppf(.975)*np.sqrt(variance), atol=1e-8)
    assert forecast.source_row.isna().all()
    assert all(members == [] for members in forecast.source_rows)
    assert forecast.time.isna().all()


def test_sarima_seasonal_ar_analytic_forecast_intervals():
    period = 4
    data = frame(320, 222)
    for i in range(period,len(data)):
        data.loc[i,'Y'] += .6*data.loc[i-period,'Y']
    r = analyze(data, analysis='SARIMA', order=(0,0,0), seasonal_order=(1,0,0,period), forecast_steps=10)
    params = dict(zip(r.model.param_names, r.model.params))
    mu, phi, sigma2 = params['const'], params['ar.S.L4'], params['sigma2']
    history = list(data.Y)
    expected, variances = [], []
    for step in range(1,11):
        prediction = mu+phi*(history[-period]-mu)
        expected.append(prediction)
        history.append(prediction)
        variances.append(sigma2*sum(phi**(2*j) for j in range((step-1)//period+1)))
    assert r.tables['model_summary'].model.iloc[0] == 'SARIMA'
    assert_allclose(r.tables['forecast'].predicted, expected, atol=2e-8)
    assert_allclose(r.tables['forecast'].ci_upper, np.array(expected)+stats.norm.ppf(.975)*np.sqrt(variances), atol=2e-8)


def test_ljung_box_independent_q_and_p():
    r = analyze(frame(140), analysis='ARIMA', order=(1,0,0), lags=8)
    resid = r.tables['residuals']
    e = resid.loc[resid.diagnostic_used,'residual'].to_numpy()
    rho = manual_acf(e,8)
    n = len(e)
    table = r.tables['diagnostics']
    for _, row in table.iterrows():
        lag = int(row.lag)
        expected = n*(n+2)*sum(rho[k]**2/(n-k) for k in range(1,lag+1))
        assert row.statistic == pytest.approx(expected, abs=1e-12)
        if lag > 1:
            assert row.p_value == pytest.approx(stats.chi2.sf(expected,lag-1))
        else:
            assert pd.isna(row.p_value)


def test_information_criteria_and_gaussian_white_noise_likelihood():
    data = frame(120)
    r = analyze(data, analysis='ARIMA', order=(0,0,0), lags=4)
    summary = r.tables['model_summary'].iloc[0]
    coef = r.tables['model_coefficients'].set_index('term')
    mu, variance = coef.loc['const','coefficient'], coef.loc['sigma2','coefficient']
    llf = -.5*len(data)*np.log(2*np.pi*variance)-sum((data.Y-mu)**2)/(2*variance)
    assert summary.log_likelihood == pytest.approx(llf)
    assert summary.aic == pytest.approx(-2*llf+2*len(coef))
    assert summary.bic == pytest.approx(-2*llf+np.log(len(data))*len(coef))
    assert summary.rmse == pytest.approx(np.sqrt(np.mean((data.Y-mu)**2)))


def test_differencing_burn_is_excluded_from_diagnostics():
    data = frame(150)
    data.Y = data.Y.cumsum()+1000
    r = analyze(data, analysis='ARIMA', order=(0,1,0))
    table = r.tables['residuals']
    burn = r.tables['model_summary'].burn.iloc[0]
    assert burn >= 1
    assert table.diagnostic_used.sum() == len(data)-burn
    assert r.tables['model_summary'].rmse.iloc[0] == pytest.approx(np.sqrt(np.mean(np.diff(data.Y)**2)))


def test_no_input_mutation_and_duplicate_index_provenance():
    data = frame(40)
    data.index = [('group',i//2) for i in range(len(data))]
    original = data.copy(deep=True)
    r = analyze(data, analysis='all', period=4)
    assert_frame_equal(data, original)
    assert r.tables['data'].source_row.tolist() == list(range(1,41))
    assert r.tables['data'].source_index.tolist() == list(data.index)
    for name in ('trend','decomposition','residuals'):
        assert r.tables[name].source_index.tolist() == list(data.index)
    assert r.tables['status'].status.eq('ok').all()


@pytest.mark.parametrize('strategy,expected,representative', [('first',1,1),('last',3,2),('mean',2,1)])
def test_duplicate_strategies_pairing_and_all_members(strategy,expected,representative):
    data = pd.DataFrame({'Y':[1.,3,5,7,9,11], 'X':[10.,30,50,70,90,110],
                         'T': pd.to_datetime(['2024-01-01','2024-01-01','2024-01-02','2024-01-03','2024-01-04','2024-01-05'])},
                        index=['a','b','c','d','e','f'])
    r = analyze(data, time='T', other='X', duplicates=strategy, analysis='correlation', lags=1)
    first = r.tables['data'].iloc[0]
    assert first.value == expected
    assert first.other == expected*10
    assert first.source_row == representative
    assert first.source_rows == [1,2]
    assert first.source_indices == ['a','b']
    assert first.source_index == ('b' if strategy == 'last' else 'a')
    assert isinstance(r.series.index,pd.DatetimeIndex)


@pytest.mark.parametrize('timestamp', [False,True])
def test_missing_complete_cases_then_irregular_policy(timestamp):
    data = frame(12)
    data['X'] = np.arange(len(data),dtype=float)
    data.loc[4,'X'] = np.nan
    data['T'] = pd.date_range('2024-01-01',periods=len(data),freq='min')
    with pytest.raises(ValueError,match='缺失'):
        analyze(data, time='T' if timestamp else None, other='X', analysis='correlation')
    with pytest.raises(ValueError,match='不规则'):
        analyze(data, time='T' if timestamp else None, other='X', missing='drop', analysis='correlation')
    r = analyze(data,time='T' if timestamp else None,other='X',missing='drop',irregular='sequence',analysis='correlation')
    assert r.tables['data'].source_row.tolist() == [1,2,3,4,6,7,8,9,10,11,12]
    assert len(r.series)==11
    assert isinstance(r.series.index,pd.RangeIndex)


@pytest.mark.parametrize('timestamp', [False,True])
def test_sequence_predictions_never_guess_future_time(timestamp):
    data = frame(60)
    data['T'] = pd.date_range('2024-01-01',periods=len(data),freq='min')
    data.loc[40:,'T'] += pd.Timedelta('3min')
    r = analyze(data,time='T' if timestamp else None,irregular='sequence',analysis='ARIMA',order=(0,0,0))
    future = r.tables['forecast']
    assert future.time.isna().all() and future.elapsed.isna().all()
    assert future.sequence.tolist() == list(range(61,71))
    assert any('丢失实际时间尺度' in note for note in r.notes)


@pytest.mark.parametrize('timezone', [None,'Asia/Shanghai'])
def test_actual_regular_time_forecast_and_dtype(timezone):
    data = frame(60)
    data['T'] = pd.date_range('2024-01-01',periods=len(data),freq='7s',tz=timezone)
    r = analyze(data,time='T',analysis='ARIMA',order=(0,0,0),interval='not used')
    assert r.tables['data'].time.dtype == data['T'].dtype
    expected = pd.date_range(data['T'].iloc[-1]+pd.Timedelta('7s'),periods=10,freq='7s')
    assert r.tables['forecast'].time.tolist() == list(expected)
    assert r.tables['forecast'].elapsed.iloc[0] == pd.Timedelta('420s')


def test_fixed_interval_has_elapsed_without_invented_dates():
    r = analyze(analysis='ARIMA',order=(0,0,0),interval='1min')
    assert r.tables['data'].time.isna().all()
    assert r.tables['data'].elapsed.iloc[-1] == pd.Timedelta('79min')
    assert r.tables['forecast'].elapsed.iloc[0] == pd.Timedelta('80min')


@pytest.mark.parametrize('options,pattern', [
    ({'analysis':'unknown'},'analysis'), ({'lags':True},'lags'), ({'lags':-1},'lags'),
    ({'lags':1.5},'lags'), ({'alpha':0},'alpha'), ({'alpha':1},'alpha'),
    ({'alpha':np.nan},'alpha'), ({'alpha':True},'alpha'), ({'alpha':'bad'},'alpha'),
    ({'missing':'fill'},'missing'), ({'duplicates':'median'},'duplicates'),
    ({'irregular':'interpolate'},'irregular'), ({'interval':'1M'},'interval'),
    ({'interval':'-1s'},'interval'), ({'interval':'0s'},'interval'),
    ({'interval':1},'interval'), ({'interval':'garbage'},'interval')])
def test_invalid_common_options(options,pattern):
    with pytest.raises(ValueError,match=pattern):
        analyze(**options)


@pytest.mark.parametrize('values', [[1,1,1,1,1], [1,2,np.inf,4,5], [1,2,-np.inf,4,5], ['1','2','3'], [True,False,True], [1j,2j,3j]])
def test_invalid_values(values):
    with pytest.raises(ValueError):
        analyze(pd.DataFrame({'Y':values}),analysis='correlation')


@pytest.mark.parametrize('analysis', ['correlation','stationarity','ARIMA','SARIMA'])
def test_constant_single_analysis_rejected(analysis):
    with pytest.raises(ValueError,match='常量'):
        analyze(pd.DataFrame({'Y':np.ones(40)}),analysis=analysis)


@pytest.mark.parametrize('n', [0,1,2])
def test_insufficient_valid_rows(n):
    with pytest.raises(ValueError):
        analyze(frame(n),analysis='correlation')


def test_empty_after_drop():
    with pytest.raises(ValueError,match='样本量不足'):
        analyze(pd.DataFrame({'Y':[np.nan]*10}),missing='drop')


def test_missing_variable_and_duplicate_names():
    with pytest.raises(ValueError,match='找不到'):
        analyze(pd.DataFrame({'X':[1.,2,3]}))
    with pytest.raises(ValueError,match='列名重复'):
        analyze(pd.DataFrame([[1.,2],[3,4]],columns=['Y','Y']))


@pytest.mark.parametrize('kind', ['numeric','invalid','unsorted','duplicates','mixed_timezone'])
def test_bad_time_columns(kind):
    data = frame(10)
    if kind == 'numeric':
        data['T'] = np.arange(10)
    elif kind == 'invalid':
        data['T'] = ['not a date']*10
    elif kind == 'unsorted':
        data['T'] = pd.date_range('2024-01-01',periods=10)[::-1]
    elif kind == 'duplicates':
        data['T'] = pd.Timestamp('2024-01-01')
    else:
        data['T'] = ['2024-01-01 00:00:00+00:00','2024-01-01 00:00:00+08:00']*5
    with pytest.raises(ValueError):
        analyze(data,time='T',analysis='correlation')


def test_nat_drop_and_irregular_handling():
    data = frame(10)
    data['T'] = pd.date_range('2024-01-01',periods=10)
    data.loc[3,'T'] = pd.NaT
    with pytest.raises(ValueError,match='缺失'):
        analyze(data,time='T',analysis='correlation')
    r = analyze(data,time='T',missing='drop',irregular='sequence',analysis='correlation')
    assert 4 not in r.tables['data'].source_row.tolist()


@pytest.mark.parametrize('options,pattern', [
    ({'period':1},'period'), ({'period':True},'period'), ({'period':100},'周期'),
    ({'period':4,'decomposition':'stl'},'decomposition')])
def test_invalid_decomposition_options(options,pattern):
    with pytest.raises(ValueError,match=pattern):
        analyze(analysis='decomposition',**options)


def test_multiplicative_nonpositive():
    with pytest.raises(ValueError,match='严格为正'):
        analyze(analysis='decomposition',period=4,decomposition='multiplicative')


def test_all_partial_failures_preserve_successes():
    r = analyze(frame(8),analysis='all',period=12,order=(10,0,0))
    status = r.tables['status'].set_index('analysis')
    assert status.loc['decomposition','status']=='unavailable'
    assert status.loc['model','status']=='unavailable'
    assert status.loc['correlation','status']=='ok'
    assert status.loc['stationarity','status']=='ok'
    assert 'acf' in r.tables and 'stationarity' in r.tables
    assert r.model is None


def test_single_short_stationarity_does_not_break_correlation():
    with pytest.raises(ValueError,match='至少需要 5'):
        analyze(frame(4),analysis='stationarity')
    assert 'acf' in analyze(frame(4),analysis='correlation').tables


@pytest.mark.parametrize('options', [
    {'order':(1,0)}, {'order':(-1,0,0)}, {'order':(True,0,0)},
    {'order':(1,0.,0)}, {'order':(100,0,0)}, {'forecast_steps':0},
    {'forecast_steps':True}])
def test_invalid_model_options(options):
    with pytest.raises(ValueError):
        analyze(analysis='ARIMA',**options)


@pytest.mark.parametrize('seasonal_order', [(0,0,0,0),(1,0,0,1),(0,0,0,4),(1,0,0),(True,0,0,4),(1,0,0,80)])
def test_invalid_seasonal_orders(seasonal_order):
    with pytest.raises(ValueError):
        analyze(analysis='SARIMA',seasonal_order=seasonal_order)


def test_unselected_features_not_validated_or_fitted(monkeypatch):
    monkeypatch.setattr(tsa,'ARIMA',lambda *args,**kwargs: pytest.fail('unselected model was called'))
    r = analyze(analysis='correlation',period=0,order=('bad',),forecast_steps=-1)
    assert 'model_summary' not in r.tables


def test_nonconvergence_never_published(monkeypatch):
    monkeypatch.setattr(tsa,'ARIMA',lambda *args,**kwargs: SimpleNamespace(fit=lambda:SimpleNamespace(mle_retvals={'converged':False})))
    with pytest.raises(ValueError,match='未收敛'):
        analyze(analysis='ARIMA')
    r = analyze(analysis='all')
    assert r.model is None
    assert 'forecast' not in r.tables
    assert r.tables['status'].set_index('analysis').loc['model','status']=='unavailable'


def test_cancellation_event_and_callback():
    event = threading.Event()
    event.set()
    for cancel in (event,lambda:True):
        with pytest.raises(InterruptedError,match='取消'):
            analyze(cancel=cancel)


def test_cancellation_during_ccf_is_not_swallowed():
    calls = 0
    def cancel():
        nonlocal calls
        calls += 1
        return calls>5
    data = frame()
    data['X'] = frame(seed=35).Y
    with pytest.raises(InterruptedError):
        analyze(data,other='X',analysis='all',cancel=cancel)


def test_cancellation_after_model_fit(monkeypatch):
    event = threading.Event()
    def fake_fit():
        event.set()
        return None
    monkeypatch.setattr(tsa,'ARIMA',lambda *args,**kwargs:SimpleNamespace(fit=fake_fit))
    with pytest.raises(InterruptedError):
        analyze(analysis='ARIMA',cancel=event)


def test_model_zero_lags_leaves_explicit_empty_diagnostics():
    r = analyze(analysis='ARIMA',order=(0,0,0),lags=0)
    assert r.tables['diagnostics'].empty
    assert r.tables['residual_acf'].correlation.tolist()==[1.]


def test_large_interval_never_wraps_nanoseconds():
    r = analyze(interval='10000 days',analysis='correlation')
    assert r.tables['data'].elapsed.iloc[-1].total_seconds() == 790000*86400
    assert r.tables['data'].elapsed.is_monotonic_increasing


@pytest.mark.parametrize('timestamp', [False, True])
def test_regular_thinning_is_not_mistaken_for_original_cadence(timestamp):
    data = frame(20)
    data['T'] = pd.date_range('2024-01-01',periods=20,freq='min')
    data.loc[1::2,'Y'] = np.nan
    with pytest.raises(ValueError,match='不规则'):
        analyze(data,time='T' if timestamp else None,missing='drop',analysis='correlation')


def test_all_model_selection_uses_only_one_fit():
    r = analyze(frame(140),analysis='all',order=(0,0,0),seasonal_order=(1,0,0,4),period=4)
    assert r.tables['model_summary'].model.tolist()==['SARIMA']
    assert r.tables['status'].analysis.tolist().count('model')==1


def test_all_accepts_list_zero_seasonal_order():
    r = analyze(analysis='all',order=(0,0,0),seasonal_order=[0,0,0,0])
    assert r.tables['model_summary'].model.tolist()==['ARIMA']


@pytest.mark.parametrize('amplitude', [1e200, 1e-200])
def test_numerical_scale_failure_is_explicit(amplitude):
    with pytest.raises(ValueError,match='量纲'):
        analyze(pd.DataFrame({'Y':np.array([1.,2,3,2,4])*amplitude}),analysis='correlation')
