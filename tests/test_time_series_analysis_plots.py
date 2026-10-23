"""Plot contract references: literal table values, Filliben QQ positions and pixel clicks.

Plotting consumes statistics from the backend; it does not estimate correlations,
confidence limits, decomposition or forecasts. Tests inspect the rendered values.
"""

from types import SimpleNamespace

from matplotlib.backend_bases import MouseEvent
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib import dates
from matplotlib.ticker import MaxNLocator
import numpy as np
import pandas as pd
from PIL import Image
import pytest
from scipy.special import ndtri

from time_series_analysis_plots import time_series_analysis_plot


KINDS = ('series', 'acf', 'pacf', 'ccf', 'decomposition', 'trend',
         'residual', 'residual_qq', 'forecast')


@pytest.fixture(params=['sequence', 'elapsed', 'datetime'])
def result(request):
    if request.param != 'datetime':
        timestamp = pd.Series([pd.NaT] * 4)
        future = pd.Series([pd.NaT] * 2)
        index = pd.RangeIndex(1, 5)
    else:
        timestamp = pd.date_range('2026-01-01', periods=4, freq='2D')
        future = pd.date_range('2026-01-09', periods=2, freq='2D')
        index = timestamp
    rows = [2, 5, 8, 12]
    elapsed = pd.to_timedelta([0, 1800, 3600, 5400], unit='s')
    prepared = pd.DataFrame({'time': timestamp, 'sequence': [1, 2, 3, 4], 'elapsed': elapsed, 'value': [2., 4., 3., 6.],
                             'source_row': rows, 'source_rows': [[2], [5, 6], [8], [12]]})
    correlation = pd.DataFrame({'lag': [0, 1, 2], 'correlation': [1., .4, -.1],
                                'ci_lower': [1., .1, -.5], 'ci_upper': [1., .7, .3]})
    pacf = correlation.copy()
    notes = ['irregular=sequence：按观测顺序等间隔重新解释，丢失实际时间尺度；未来仅输出序号。'] if request.param == 'sequence' else []
    return SimpleNamespace(series=pd.Series([2., 4., 3., 6.], index=index), notes=notes, tables={
        'data': prepared,
        'acf': correlation,
        'pacf': pacf,
        'ccf': pd.DataFrame({'lag': [-2, -1, 0, 1, 2], 'correlation': [.1, .2, .5, .8, -.2]}),
        'decomposition': pd.DataFrame({'time': timestamp, 'sequence': [1, 2, 3, 4], 'elapsed': elapsed, 'value': [2., 4., 3., 6.],
            'trend': [np.nan, 3., 4., np.nan], 'seasonal': [-1., 1., -1., 1.],
            'residual': [np.nan, 0., 0., np.nan], 'source_row': rows}),
        'trend': pd.DataFrame({'time': timestamp, 'sequence': [1, 2, 3, 4], 'elapsed': elapsed, 'value': [2., 4., 3., 6.],
                               'fitted': [2., 3., 4., 5.], 'source_row': rows}),
        'residuals': pd.DataFrame({'time': timestamp, 'sequence': [1, 2, 3, 4], 'elapsed': elapsed, 'residual': [3., -1., np.nan, 1.],
                                   'source_row': rows}),
        'forecast': pd.DataFrame({'time': future, 'sequence': [5, 6], 'elapsed': pd.to_timedelta([7200, 9000], unit='s'), 'predicted': [7., 8.],
                                  'ci_lower': [6., 6.5], 'ci_upper': [8., 9.5]})})


def draw(result, kind, on_pick=None):
    figure = Figure(figsize=(8, 6))
    FigureCanvasAgg(figure)
    handles = time_series_analysis_plot(result, kind, figure, on_pick=on_pick)
    figure.canvas.draw()
    return figure, handles


def click(figure, axis, xy, button=1, dx=0, dy=0):
    x, y = axis.transData.transform(xy)
    event = MouseEvent('button_press_event', figure.canvas, x+dx, y+dy, button=button)
    figure.canvas.callbacks.process('button_press_event', event)


@pytest.mark.parametrize('kind', KINDS)
def test_render_and_reopen_png(result, kind, tmp_path):
    original = {key: value.copy(deep=True) for key, value in result.tables.items()}
    figure, handles = draw(result, kind)
    assert len(handles['axes']) == (4 if kind == 'decomposition' else 1)
    assert handles['connections'] == []
    filename = tmp_path / (kind+'.png')
    figure.savefig(filename)
    with Image.open(filename) as image:
        assert image.size == (800, 600)
        image.verify()
    for key in original:
        pd.testing.assert_frame_equal(result.tables[key], original[key])


@pytest.mark.parametrize('kind,columns', [
    ('series', ['value']), ('trend', ['value', 'fitted']), ('residual', ['residual']),
    ('decomposition', ['value', 'trend', 'seasonal', 'residual'])])
def test_actual_table_values_and_time_locators(result, kind, columns):
    _, handles = draw(result, kind)
    table = result.tables[{'series': 'data', 'residual': 'residuals'}.get(kind, kind)]
    for i, column in enumerate(columns):
        axis = handles['axes'][i if kind == 'decomposition' else 0]
        line = axis.lines[0 if kind == 'decomposition' else i]
        np.testing.assert_allclose(line.get_ydata(), table[column], equal_nan=True)
        if result.notes:
            np.testing.assert_allclose(line.get_xdata(), table['sequence'])
            assert isinstance(axis.xaxis.get_major_locator(), MaxNLocator)
        elif isinstance(result.series.index, pd.DatetimeIndex):
            expected = dates.date2num(table['time'].to_numpy())
            np.testing.assert_allclose(line.get_xdata(), expected)
            assert isinstance(axis.xaxis.get_major_locator(), dates.AutoDateLocator)
            assert isinstance(axis.xaxis.get_major_formatter(), dates.ConciseDateFormatter)
        else:
            np.testing.assert_allclose(line.get_xdata(), table['elapsed'].dt.total_seconds())
            assert axis.get_xlabel() == '相对时间（秒）'


@pytest.mark.parametrize('kind', ['acf', 'pacf'])
def test_ci_is_translated_from_estimate_to_zero(result, kind):
    _, handles = draw(result, kind)
    axis = handles['axes'][0]
    np.testing.assert_allclose(axis.lines[0].get_ydata(), [1., .4, -.1])
    vertices = axis.collections[1].get_paths()[0].vertices
    for lag, expected in [(0, [0., 0.]), (1, [-.3, .3]), (2, [-.4, .4])]:
        boundary = vertices[vertices[:, 0] == lag, 1]
        np.testing.assert_allclose([boundary.min(), boundary.max()], expected)
    text = axis.get_legend().get_texts()[0].get_text()
    assert ('Bartlett' if kind == 'acf' else '正态近似') in text
    assert '以 0 为中心' in text


def test_ccf_lag_direction_and_no_invented_band(result):
    _, handles = draw(result, 'ccf')
    axis = handles['axes'][0]
    np.testing.assert_array_equal(axis.lines[0].get_xdata(), [-2, -1, 0, 1, 2])
    np.testing.assert_allclose(axis.lines[0].get_ydata(), [.1, .2, .5, .8, -.2])
    assert len(axis.collections) == 1
    assert 'k > 0：X 领先 Y' in axis.get_xlabel()


def test_qq_independent_filliben_positions_and_sorted_source_rows(result):
    rows = []
    figure, handles = draw(result, 'residual_qq', rows.append)
    axis = handles['axes'][0]
    probabilities = [1-.5**(1/3), .5, .5**(1/3)]
    np.testing.assert_allclose(axis.lines[0].get_xdata(), ndtri(probabilities))
    np.testing.assert_allclose(axis.lines[0].get_ydata(), [-1., 1., 3.])
    click(figure, axis, [ndtri(probabilities[0]), -1.])
    assert rows == [5]


@pytest.mark.parametrize('kind', ['series', 'trend', 'decomposition', 'residual'])
def test_click_nearest_pixel_and_source_rows(result, kind):
    rows = []
    figure, handles = draw(result, kind, rows.append)
    axis = handles['axes'][0]
    x = axis.lines[0].get_xdata()[1]
    y = axis.lines[0].get_ydata()[1]
    click(figure, axis, [x, y], dx=3, dy=2)
    assert rows == ([[5, 6]] if kind == 'series' else [5])
    click(figure, axis, [x, y], button=3)
    click(figure, axis, [x, y], dx=25, dy=25)
    assert len(rows) == 1
    for connection in handles['connections']:
        figure.canvas.mpl_disconnect(connection)
    click(figure, axis, [x, y])
    assert len(rows) == 1


def test_forecast_context_intervals_future_unmapped(result):
    rows = []
    # Even an unexpected backend row field must not make future points clickable.
    result.tables['forecast']['source_row'] = [901, 902]
    figure, handles = draw(result, 'forecast', rows.append)
    axis = handles['axes'][0]
    np.testing.assert_allclose(axis.lines[0].get_ydata(), [2., 4., 3., 6.])
    np.testing.assert_allclose(axis.lines[1].get_ydata(), [7., 8.])
    boundary = axis.collections[0].get_paths()[0].vertices[:, 1]
    np.testing.assert_allclose([boundary.min(), boundary.max()], [6., 9.5])
    click(figure, axis, [axis.lines[1].get_xdata()[1], 8.])
    assert rows == []
    click(figure, axis, [axis.lines[0].get_xdata()[1], 4.])
    assert rows == [[5, 6]]


def test_missing_and_infinite_values_remain_gaps(result):
    result.tables['data']['value'] = [2., np.nan, np.inf, 6.]
    rows = []
    figure, handles = draw(result, 'series', rows.append)
    np.testing.assert_allclose(handles['axes'][0].lines[0].get_ydata(),
                               [2., np.nan, np.nan, 6.], equal_nan=True)
    result.tables['data']['source_rows'] = [[], [], [], []]
    _, no_rows = draw(result, 'series', rows.append)
    assert len(no_rows['connections']) == 1


@pytest.mark.parametrize('kind', KINDS)
def test_empty_or_missing_table_is_explicit(result, kind):
    name = {'series': 'data', 'residual': 'residuals', 'residual_qq': 'residuals'}.get(kind, kind)
    result.tables[name] = pd.DataFrame()
    with pytest.raises(ValueError, match='没有可用'):
        time_series_analysis_plot(result, kind, Figure())
    del result.tables[name]
    with pytest.raises(ValueError, match='没有可用'):
        time_series_analysis_plot(result, kind, Figure())


@pytest.mark.parametrize('kind,name,column', [
    ('series', 'data', 'value'), ('residual', 'residuals', 'residual'),
    ('trend', 'trend', 'fitted'), ('acf', 'acf', 'correlation'),
    ('forecast', 'forecast', 'predicted')])
def test_all_unusable_data_explicit(result, kind, name, column):
    result.tables[name][column] = np.nan
    with pytest.raises(ValueError, match='没有有效|没有可用'):
        time_series_analysis_plot(result, kind, Figure())


def test_short_samples_and_unavailable_decomposition(result):
    result.tables['residuals'] = result.tables['residuals'].iloc[:1]
    with pytest.raises(ValueError, match='至少需要 2'):
        time_series_analysis_plot(result, 'residual_qq', Figure())
    result.tables['data'] = result.tables['data'].iloc[:1]
    _, handles = draw(result, 'series')
    assert len(handles['axes'][0].lines[0].get_ydata()) == 1
    result.tables['decomposition']['trend'] = np.nan
    _, handles = draw(result, 'decomposition')
    assert '无可用数据' in handles['axes'][1].texts[0].get_text()


def test_unknown_kind_fails_before_creating_axes(result):
    figure = Figure()
    with pytest.raises(ValueError, match='未知时间序列图形'):
        time_series_analysis_plot(result, 'unknown', figure)
    assert figure.axes == []


def test_no_source_metadata_does_not_invent_rows(result):
    result.tables['data'] = result.tables['data'].drop(columns=['source_row', 'source_rows'])
    rows = []
    figure, handles = draw(result, 'series', rows.append)
    axis = handles['axes'][0]
    click(figure, axis, [axis.lines[0].get_xdata()[1], 4.])
    assert rows == []


def test_source_members_numpy_lists_and_singletons(result):
    result.tables['data']['source_rows'] = [np.array([2, 3]), [5], [], None]
    rows = []
    figure, handles = draw(result, 'series', rows.append)
    axis = handles['axes'][0]
    for i, y in enumerate([2., 4., 3., 6.]):
        click(figure, axis, [axis.lines[0].get_xdata()[i], y])
    assert rows == [[2, 3], 5, 12]


@pytest.mark.parametrize('time_axis', ['datetime', 'elapsed', 'sequence'])
def test_real_backend_all_plots_and_ci_contract(time_axis):
    from time_series_analysis import analyze_time_series

    n = 64
    position = np.arange(n)
    y = 4+.03*position+np.sin(position*np.pi/2)+np.random.default_rng(53).normal(0, .3, n)
    data = pd.DataFrame({'Y': y, 'X': np.roll(y, -1),
                         'T': pd.date_range('2026-01-01', periods=n, freq='h', tz='Asia/Shanghai')})
    result = analyze_time_series(data, 'Y', time=None if time_axis == 'elapsed' else 'T', other='X',
                                 interval='30min', irregular='sequence' if time_axis == 'sequence' else 'error',
                                 lags=5, period=4, order=(1, 0, 0), forecast_steps=3,
                                 alpha=.1, analysis='all')
    assert (result.tables['status']['status'] == 'ok').all()
    assert any('Bartlett' in note and 'Yule-Walker MLE' in note for note in result.notes)
    assert result.tables['model_summary'].iloc[0]['alpha'] == .1
    assert result.tables['forecast']['source_rows'].to_list() == [[], [], []]
    assert result.tables['forecast']['source_row'].isna().all()
    for kind in KINDS:
        rows = []
        figure, handles = draw(result, kind, rows.append)
        axis = handles['axes'][0]
        if kind in ('acf', 'pacf'):
            # Backend CI is centered on rho. Its plotted first-lag half-width
            # must equal the normal pointwise bound z_(.95)/sqrt(n), not rho+z*se.
            bounds = axis.collections[1].get_paths()[0].vertices
            at_one = bounds[bounds[:, 0] == 1, 1]
            expected = ndtri(.95)/np.sqrt(n)
            np.testing.assert_allclose([at_one.min(), at_one.max()], [-expected, expected])
        if kind == 'series':
            np.testing.assert_allclose(axis.lines[0].get_ydata(), y)
            click(figure, axis, [axis.lines[0].get_xdata()[5], y[5]])
            assert rows == [6]
            if time_axis == 'datetime':
                assert str(axis.xaxis.get_major_formatter()._tz) == 'Asia/Shanghai'
        if kind == 'forecast':
            np.testing.assert_allclose(axis.lines[1].get_ydata(), result.tables['forecast']['predicted'])
            expected_x = (dates.date2num(result.tables['forecast']['time'].to_numpy())
                          if time_axis == 'datetime' else
                          [64*1800, 65*1800, 66*1800] if time_axis == 'elapsed' else [65, 66, 67])
            np.testing.assert_allclose(axis.lines[1].get_xdata(), expected_x)
            click(figure, axis, [axis.lines[1].get_xdata()[-1], axis.lines[1].get_ydata()[-1]])
            assert rows == []
        if kind == 'residual_qq':
            residuals = result.tables['residuals'].loc[result.tables['residuals']['diagnostic_used'], 'residual']
            np.testing.assert_allclose(axis.lines[0].get_ydata(), np.sort(residuals))


def test_real_backend_sequence_forecast_stays_on_sequence_axis():
    from time_series_analysis import analyze_time_series

    times = pd.date_range('2026-01-01', periods=32, freq='h').delete(7)
    data = pd.DataFrame({'T': times, 'Y': np.random.default_rng(52).normal(size=len(times))})
    result = analyze_time_series(data, 'Y', time='T', irregular='sequence', analysis='ARIMA',
                                 forecast_steps=2, lags=3)
    rows = []
    figure, handles = draw(result, 'forecast', rows.append)
    axis = handles['axes'][0]
    np.testing.assert_array_equal(axis.lines[0].get_xdata(), np.arange(1, 32))
    np.testing.assert_array_equal(axis.lines[1].get_xdata(), [32, 33])
    assert result.tables['forecast']['time'].isna().all()
    assert axis.get_xlabel() == '序号'


def test_real_backend_duplicate_aggregation_click_and_positive_ccf():
    from time_series_analysis import analyze_time_series

    x = np.random.default_rng(53).normal(size=32)
    y = np.r_[0., x[:-1]]
    data = pd.DataFrame({'T': pd.date_range('2026-01-01', periods=32, freq='h'), 'Y': y, 'X': x})
    data = pd.concat([data.iloc[:1], data], ignore_index=True)
    result = analyze_time_series(data, 'Y', time='T', other='X', duplicates='mean',
                                 analysis='correlation', lags=3)
    rows = []
    figure, handles = draw(result, 'series', rows.append)
    axis = handles['axes'][0]
    click(figure, axis, [axis.lines[0].get_xdata()[0], y[0]])
    assert rows == [[1, 2]]
    _, handles = draw(result, 'ccf')
    axis = handles['axes'][0]
    at_one = axis.lines[0].get_ydata()[axis.lines[0].get_xdata() == 1]
    np.testing.assert_allclose(at_one, [1.])
    assert 'X 领先 Y' in axis.get_xlabel()


def test_backend_burn_residuals_are_not_qq_diagnostic_samples(result):
    result.tables['residuals']['diagnostic_used'] = [False, True, True, True]
    _, handles = draw(result, 'residual_qq')
    np.testing.assert_array_equal(handles['axes'][0].lines[0].get_ydata(), [-1., 1.])
