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
