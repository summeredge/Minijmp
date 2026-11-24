import pandas as pd
import numpy as np
import pytest

from time_series_analysis import analyze_time_series


def test_moving_average_window_and_forecast_index():
    values = [4, 5, 8, 9, 10]
    dates = pd.date_range('2026-01-01', periods=5, freq='h', tz='Asia/Shanghai')
    result = analyze_time_series(pd.DataFrame({'y': values, 't': dates}), 'y', time='t',
                                 analysis='moving_average', window=3, forecast_steps=4)
    fit, future = (result.tables[key] for key in ('smoothing', 'forecast'))
    averages = [np.nan, np.nan] + [sum(values[i:i+3])/3 for i in range(3)]
    np.testing.assert_allclose(fit.smoothed, averages)
    np.testing.assert_allclose(fit.fitted, [np.nan, *averages[:-1]])
    np.testing.assert_allclose(fit.residual, np.array(values) - [np.nan, *averages[:-1]])
    np.testing.assert_allclose(future.predicted, [9]*4)
    assert list(future.sequence) == [6, 7, 8, 9]
    assert list(future.time) == list(pd.date_range(dates[-1]+pd.Timedelta(hours=1), periods=4, freq='h'))
    assert future.source_row.isna().all()
    with pytest.raises(ValueError, match='窗口'):
        analyze_time_series(pd.DataFrame({'y': values}), 'y', analysis='moving_average', window=6)


@pytest.mark.parametrize('weight', [0, .3, 1])
def test_ses_closed_form(weight):
    y = np.array([4., 5., 8., 9., 10., 12., 17.])
    initial = sum(y[:6])/6
    levels = [(1-weight)**t*initial + sum(weight*(1-weight)**(t-j-1)*y[j]
              for j in range(t)) for t in range(1, len(y)+1)]
    result = analyze_time_series(pd.DataFrame({'y': y}), 'y',
                                 analysis='single_exponential', level_weight=weight, forecast_steps=3)
    np.testing.assert_allclose(result.tables['smoothing'].smoothed, levels)
    np.testing.assert_allclose(result.tables['smoothing'].fitted, [initial, *levels[:-1]])
    np.testing.assert_allclose(result.tables['forecast'].predicted, [levels[-1]]*3)


def test_holt_exact_linear_series():
    y = np.arange(7, 20, 2)
    result = analyze_time_series(pd.DataFrame({'y': y}), 'y', analysis='double_exponential',
                                 level_weight=.3, trend_weight=.7, forecast_steps=2)
    np.testing.assert_allclose(result.tables['smoothing'].fitted, y)
    np.testing.assert_allclose(result.tables['forecast'].predicted, [21, 23])


@pytest.mark.parametrize('mode', ['additive', 'multiplicative'])
def test_winters_updated_and_wrapped_seasons(mode):
    # Independent scalar phase calculations for [10,14] and [13,17].
    # Initial level and slope are 12 and 1.5. Each update uses halfway weights.
    y = [10, 14, 13, 17]
    if mode == 'additive':
        l1, b1, a1 = 12.75, 1.125, -2.375
        l2, b2, a2 = 12.9375, .65625, 1.53125
        l3 = (l2+b2+13-a1)/2
        b3 = (b2+l3-l2)/2
        a3 = (a1+13-l3)/2
        l4 = (l3+b3+17-a2)/2
        b4 = (b3+l4-l3)/2
        a4 = (a2+17-l4)/2
        fitted = [11.5, l1+b1+2, l2+b2+a1, l3+b3+a2]
        forecast = [l4+b4+a3, l4+2*b4+a4, l4+3*b4+a3]
    else:
        l1, b1 = 12.75, 1.125
        a1 = (5/6+10/l1)/2
        l2 = (l1+b1+12)/2
        b2 = (b1+l2-l1)/2
        a2 = (7/6+14/l2)/2
        l3 = (l2+b2+13/a1)/2
        b3 = (b2+l3-l2)/2
        a3 = (a1+13/l3)/2
        l4 = (l3+b3+17/a2)/2
        b4 = (b3+l4-l3)/2
        a4 = (a2+17/l4)/2
        fitted = [11.25, (l1+b1)*7/6, (l2+b2)*a1, (l3+b3)*a2]
        forecast = [(l4+b4)*a3, (l4+2*b4)*a4, (l4+3*b4)*a3]
    result = analyze_time_series(pd.DataFrame({'y': y}), 'y', analysis='winters',
                                 decomposition=mode, period=2, level_weight=.5,
                                 trend_weight=.5, seasonal_weight=.5, forecast_steps=3)
    np.testing.assert_allclose(result.tables['smoothing'].fitted, fitted)
    np.testing.assert_allclose(result.tables['forecast'].predicted, forecast)

@pytest.mark.parametrize('width', [3,4])
def test_centered_average_origin_and_prediction_interval(width):
    from scipy.stats import t
    y = [4,5,8,9,10,14,19,200,500]
    dates = pd.date_range('2026-01-01',periods=len(y),freq='h')
    result = analyze_time_series(pd.DataFrame({'y':y,'time':dates}),'y',time='time',
        analysis='moving_average',window=width,centered=True,origin=7,forecast_steps=3,smoothing_interval=True)
    expected = [np.nan]*7
    for i in range(width//2, 7-width//2):
        window = y[i-width//2:i+width//2+1]
        expected[i] = sum(window)/width if width%2 else (sum(window)-(window[0]+window[-1])/2)/width
    np.testing.assert_allclose(result.tables['smoothing'].smoothed,expected)
    future = result.tables['forecast']
    assert list(future.time[:2]) == list(dates[7:9])
    assert list(future.sequence) == [8,9,10]
    value = np.mean(y[7-width:7])
    np.testing.assert_allclose(future.predicted,value)
    margin = t.ppf(.975,width-1)*np.std(y[7-width:7],ddof=1)*np.sqrt(1+1/width)
    np.testing.assert_allclose(future.ci_upper, value+margin)
    np.testing.assert_allclose(future.ci_lower, value-margin)


def test_additive_innovation_interval_and_regression_initialization():
    from scipy.stats import norm, linregress
    y = np.array([10,14,13,17,20,16,18,22,21,27,25,28,23,29,31,32,36,30])
    first = linregress(range(1,7),y[:6])
    trend = linregress(range(1,19),y)
    phase_means = [sum(y[j] - trend.intercept - trend.slope*(j+1) for j in range(i,18,6))/3
                   for i in range(6)]
    frame = pd.DataFrame({'y':y})
    r = analyze_time_series(frame,'y',analysis='winters',period=6,winters_init='regression',
                            level_weight=0,trend_weight=0,seasonal_weight=0,forecast_steps=3)
    np.testing.assert_allclose(r.tables['forecast'].predicted,[first.intercept+step*first.slope+phase_means[i]
                                     for i,step in enumerate(range(19,22))])
    r = analyze_time_series(frame,'y',analysis='winters',period=6,winters_init='regression',forecast_steps=3)
    np.testing.assert_allclose(r.tables['forecast'].predicted,
                               [32.15519175546595,36.770012612779205,36.72226739103863],rtol=0,atol=1e-12)
    r = analyze_time_series(frame,'y',analysis='single_exponential',level_weight=.4,
                            smoothing_interval=True,forecast_steps=4)
    residual = r.tables['smoothing'].residual.iloc[6:]
    forecast = r.tables['forecast']
    for j in range(4):
        assert forecast.ci_upper.iloc[j] - forecast.predicted.iloc[j] == pytest.approx(
            norm.ppf(.975)*np.sqrt(np.mean(residual**2)*(1+j*.4**2)))


def test_auto_arima_criterion_and_origin():
    from statsmodels.tsa.statespace.sarimax import SARIMAX
    rng = np.random.default_rng(113)
    y = np.empty(70)
    y[0]=0
    for i, error in enumerate(rng.normal(size=69),1):
        y[i] = .7*y[i-1]+error
    result = analyze_time_series(pd.DataFrame({'y':y}),'y',analysis='auto_arima',
                                 order=(1,0,1),origin=60,arima_criterion='BIC',forecast_steps=2)
    ranked=result.tables['model_selection']
    assert ranked.selected.sum() == 1
    assert ranked.iloc[0].selected
    reference = {}
    for p,q in [(0,0),(0,1),(1,0),(1,1)]:
        order = (p,0,q)
        fit = SARIMAX(y[:60]-y[:60].mean(),order=order,trend='c').fit(disp=False)
        if fit.mle_retvals['converged']:
            reference[order] = fit.bic
    winner = min(reference,key=reference.get)
    assert ranked.iloc[0].order == winner
    assert ranked.iloc[0].BIC == pytest.approx(reference[winner],rel=1e-6)
    assert list(result.tables['forecast'].sequence) == [61,62]



@pytest.mark.parametrize('period, native', [
    (2, [35.198914930535295, 36.400239417887306, 37.68852660434906]),
    (3, [34.90191502621498, 38.00130245880733, 36.63213676796022]),
    (4, [34.84128313275227, 37.55571841037086, 37.513233898634745]),
])
def test_short_additive_regression_matches_minitab_19(period, native):
    # TSWINT C1 p; ADDITIVE; WEIGHTS 0.2 0.2 0.2; FORECASTS 3; FSTORE C2.
    frame = pd.DataFrame({'y':[10,14,13,17,20,16,18,22,21,27,25,28,23,29,31,32,36,30]})
    result = analyze_time_series(frame, 'y', analysis='winters', period=period,
                                 winters_init='regression', forecast_steps=3)
    np.testing.assert_allclose(result.tables['forecast'].predicted, native, rtol=0, atol=1e-12)


def test_multiplicative_interval_against_reference_recursion():
    from scipy.stats import norm
    values = np.array([12, 18, 13, 22, 15, 24, 20, 25])
    result = analyze_time_series(pd.DataFrame({'y': values}), 'y',
        analysis='winters', period=2, decomposition='multiplicative',
        level_weight=.25, trend_weight=.3, seasonal_weight=.4, smoothing_interval=True,
        forecast_steps=5)
    level, slope = 15., 1.25
    phases = [.8, 1.2]
    errors = []
    for i, observed in enumerate(values):
        phase = i % 2
        season = phases[phase]
        errors.append(abs(observed/season-level-slope))
        next_level = .25*observed/season + .75*(level+slope)
        slope = .3*(next_level-level) + .7*slope
        level = next_level
        phases[phase] = .4*observed/level + .6*season
    h = np.arange(1, 6)
    # Expand the published polynomial for theta=.4, nu=.6.
    polynomial = 6.176 + .896*h + .128*h**2
    width = 1.25*norm.ppf(.975)*np.mean(errors[1:])*np.sqrt(polynomial/polynomial[0])
    forecast = result.tables['forecast']
    np.testing.assert_allclose(forecast.ci_upper-forecast.predicted, width)
    np.testing.assert_allclose(forecast.predicted-forecast.ci_lower, width)


@pytest.mark.parametrize('lam', [-.5, 0, .5])
def test_auto_arima_boxcox_and_constant_against_white_noise(lam):
    from scipy.stats import norm
    rng = np.random.default_rng(530)
    values = 20*np.exp(rng.normal(scale=.07,size=90))
    fit = analyze_time_series(pd.DataFrame({'y':values}), 'y', analysis='auto_arima',
         order=(0,0,0), arima_boxcox=lam, arima_constant='search', forecast_steps=3)
    assert fit.tables['model_selection'].deterministic.tolist() == ['c', 'n']
    z = np.sign(lam)*values**lam if lam else np.log(values)
    mu, variance = z.mean(), z.var()
    delta = norm.ppf(.975)*np.sqrt(variance)
    if lam:
        mean = (np.sign(lam)*mu)**(1/lam)*(1+(1-lam)*variance/(2*(lam*mu)**2))
        limits = (np.sign(lam)*(mu+np.array([-delta,delta])))**(1/lam)
    else:
        mean = np.exp(mu)*(1+variance/2)
        limits = np.exp(mu+np.array([-delta,delta]))
    future = fit.tables['forecast']
    np.testing.assert_allclose(future.predicted, mean, rtol=1e-4)
    np.testing.assert_allclose(future[['ci_lower','ci_upper']], np.tile(limits,(3,1)), rtol=1e-4)
    np.testing.assert_allclose(fit.tables['residuals'].value_transformed, z)


def test_auto_arima_guerrero_groups_and_random_walk_drift():
    # All complete pairs have an identical CV. The leading value is omitted
    # from lambda estimation, but included in the training fit.
    values = [1, *np.ravel([(scale, 1.2*scale) for scale in range(5, 38)])]
    result = analyze_time_series(pd.DataFrame({'y':values}), 'y', analysis='auto_arima',
            order=(0,1,0), arima_boxcox='auto', arima_constant='search', forecast_steps=2)
    assert result.tables['model_summary'].boxcox_lambda.iloc[0] == 0
    assert set(result.tables['model_selection'].deterministic) == {'n','t'}
    walk = 20 + np.cumsum(np.random.default_rng(41).normal(loc=2, size=100))
    fit = analyze_time_series(pd.DataFrame({'y':walk}), 'y', analysis='auto_arima',
        order=(0,1,0), arima_constant='search', forecast_steps=2)
    assert fit.tables['model_summary'].deterministic.iloc[0] == 't'
    np.testing.assert_allclose(fit.tables['forecast'].predicted,
                              walk[-1] + np.arange(1,3)*np.diff(walk).mean(), atol=2e-5)
