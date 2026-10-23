"""独立的字面量绘图契约：不依赖 SPC 算法作为曲线和限的参考。"""

from types import SimpleNamespace

from matplotlib.backend_bases import MouseEvent
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
import numpy as np
import pandas as pd
from PIL import Image
import pytest

from advanced_spc_plots import spc_plot


KINDS = ('EWMA', 'CUSUM', 'Nelson', 'T2')


@pytest.fixture(params=KINDS)
def result(request):
    kind = request.param
    table = pd.DataFrame({
        'source_row': [2, 5, 9, 14], 'source_index': ['a', 'd', 'h', 'm'],
        'sequence': [1, 2, 3, 4], 'value': [10., 11., 13., 12.],
        'statistic': [10., 10.2, 10.76, 11.008],
        'lower': [9.4, 9.23, 9.14, 9.09], 'center': [10.] * 4,
        'upper': [10.6, 10.77, 10.86, 10.91],
        # An in-limit alarm must still be shown (e.g. a Nelson run rule).
        'alarm': [False, True, False, True], 'rules': ['', 'N2', '', 'N1']})
    if kind == 'CUSUM':
        table['statistic'] = [0., 1., 2., 6.]
        table['negative'] = [0., -1., -5.5, -2.]
        table['lower'], table['center'], table['upper'] = -5., 0., 5.
        table['rules'] = ['', 'CUSUM-', '', 'CUSUM+']
    elif kind == 'Nelson':
        table['statistic'] = table['value']
        table['lower'], table['center'], table['upper'] = 7., 10., 13.
    elif kind == 'T2':
        table = table.drop(columns='value')
        table['statistic'] = [.3, 1., 2., 9.]
        table['lower'], table['center'], table['upper'] = 0., 0., 7.5
    return SimpleNamespace(kind=kind, tables={'observations': table})


def draw(result, on_pick=None):
    figure = Figure(figsize=(8, 6))
    FigureCanvasAgg(figure)
    handles = spc_plot(result, figure, on_pick)
    figure.canvas.draw()
    return figure, handles


def click(figure, axis, xy, button=1, dx=0, dy=0):
    x, y = axis.transData.transform(xy)
    event = MouseEvent('button_press_event', figure.canvas, x+dx, y+dy, button=button)
    figure.canvas.callbacks.process('button_press_event', event)


def test_literal_values_limits_alarms_and_png(result, tmp_path):
    table = result.tables['observations']
    original = table.copy(deep=True)
    figure, handles = draw(result)
    assert handles['connections'] == []
    assert len(handles['axes']) == 1
    axis = handles['axes'][0]
    columns = ['statistic', 'negative'] if result.kind == 'CUSUM' else ['statistic']
    references = ['lower', 'upper'] if result.kind == 'T2' else ['center', 'lower', 'upper']
    assert len(axis.lines) == len(columns) + len(references)
    for line, column in zip(axis.lines, columns + references):
        np.testing.assert_allclose(line.get_xdata(), [1, 2, 3, 4])
        np.testing.assert_allclose(line.get_ydata(), table[column])
        assert line.get_picker() is None
    expected_alarm = np.concatenate([
        np.column_stack(([2, 4], table.loc[table['alarm'], column])) for column in columns])
    if result.kind == 'CUSUM':
        expected_alarm = [[4, 6.], [2, -1.]]
    np.testing.assert_allclose(axis.collections[0].get_offsets(), expected_alarm)
    legend = ' '.join(text.get_text() for text in axis.get_legend().get_texts())
    if result.kind == 'T2':
        assert all(label in legend for label in ('统计量零界', '上控制限', '异常观测'))
        assert '下控制限' not in legend and '中心线' not in legend
    else:
        assert all(label in legend for label in ('中心线', '下控制限', '上控制限', '异常观测'))
    assert '当前监控' in axis.get_title() and 'Phase II' in axis.get_title()
    assert ('T²' if result.kind == 'T2' else result.kind) in axis.get_title()
    assert axis.get_ylabel() == ('标准化累积和' if result.kind == 'CUSUM' else
                                 'T²' if result.kind == 'T2' else '原单位')
    if result.kind == 'Nelson':
        assert '−3σ' in legend and '+3σ' in legend
    filename = tmp_path / (result.kind + '.png')
    figure.savefig(filename)
    with Image.open(filename) as image:
        assert image.size == (800, 600)
        image.verify()
    pd.testing.assert_frame_equal(table, original)


def test_click_uses_noncontinuous_source_rows_and_disconnect(result):
    picked = []
    figure, handles = draw(result, picked.append)
    axis = handles['axes'][0]
    table = result.tables['observations']
    click(figure, axis, [3, table['statistic'].iloc[2]], dx=3, dy=2)
    assert picked == [9]
    click(figure, axis, [3, table['statistic'].iloc[2]], dx=9)
    assert picked == [9, 9]
    if result.kind == 'CUSUM':
        click(figure, axis, [2, -1.])
        assert picked == [9, 9, 5]
    count = len(picked)
    click(figure, axis, [3, table['statistic'].iloc[2]], button=3)
    click(figure, axis, [3, table['statistic'].iloc[2]], dx=13)
    click(figure, axis, [3, table['statistic'].iloc[2]], dx=25, dy=25)
    click(figure, axis, [0, 1000])
    assert len(picked) == count
    assert len(handles['connections']) == 1
    figure.canvas.mpl_disconnect(handles['connections'][0])
    click(figure, axis, [3, table['statistic'].iloc[2]])
    assert len(picked) == count


def test_history_has_own_limits_and_never_maps_current_rows(result, tmp_path):
    baseline = pd.DataFrame({'source_row': [301, 302], 'source_index': ['x', 'y'],
                             'sequence': [1, 2], 'statistic': [1., 4.],
                             'lower': [0., 0.], 'center': [0., 0.],
                             'upper': [3., 3.], 'alarm': [False, True]})
    if result.kind == 'CUSUM':
        baseline['rules'] = ['', 'CUSUM+']
    result.tables['baseline'] = baseline
    original = baseline.copy(deep=True)
    picked = []
    figure, handles = draw(result, picked.append)
    current_axis, history_axis = handles['axes']
    assert figure.axes == handles['axes']
    assert current_axis.get_position().y0 > history_axis.get_position().y0
    assert '历史基线' in history_axis.get_title() and 'Phase I' in history_axis.get_title()
    np.testing.assert_allclose(history_axis.lines[0].get_ydata(), [1., 4.])
    np.testing.assert_allclose(history_axis.lines[-1].get_ydata(), [3., 3.])
    np.testing.assert_allclose(current_axis.lines[-1].get_ydata(),
                               result.tables['observations']['upper'])
    np.testing.assert_allclose(history_axis.collections[0].get_offsets(), [[2, 4.]])
    click(figure, history_axis, [2, 4.])
    assert picked == []
    click(figure, current_axis, [2, result.tables['observations']['statistic'].iloc[1]])
    assert picked == [5]
    pd.testing.assert_frame_equal(baseline, original)
    filename = tmp_path / (result.kind + '-history.png')
    figure.savefig(filename)
    with Image.open(filename) as image:
        image.verify()


def test_nan_gaps_missing_source_and_empty_alarm(result):
    table = result.tables['observations']
    table['statistic'] = [1., np.nan, np.inf, 4.]
    table['alarm'] = False
    table['source_row'] = pd.array([2, 5, 9, pd.NA], dtype='Int64')
    picked = []
    figure, handles = draw(result, picked.append)
    axis = handles['axes'][0]
    np.testing.assert_allclose(axis.lines[0].get_ydata(), [1., np.nan, np.nan, 4.], equal_nan=True)
    assert axis.collections[0].get_offsets().shape == (0, 2)
    click(figure, axis, [4, 4.])
    assert picked == []
    click(figure, axis, [1, 1.])
    assert picked == [2]


@pytest.mark.parametrize('baseline', [None, pd.DataFrame()])
def test_empty_history_is_omitted(result, baseline):
    result.tables['baseline'] = baseline
    assert len(draw(result)[1]['axes']) == 1


@pytest.mark.parametrize('bad', ['unknown', None])
def test_unknown_kind_fails_without_creating_axes(bad):
    figure = Figure()
    with pytest.raises(ValueError, match='未知 SPC'):
        spc_plot(SimpleNamespace(kind=bad, tables={}), figure)
    assert not figure.axes


@pytest.mark.parametrize('table', [None, pd.DataFrame()])
def test_missing_or_empty_observations_is_explicit(table):
    with pytest.raises(ValueError, match='没有可用'):
        spc_plot(SimpleNamespace(kind='T2', tables={'observations': table}), Figure())


def test_required_columns_and_unusable_statistics(result):
    table = result.tables['observations']
    table['statistic'] = np.nan
    if result.kind == 'CUSUM':
        table['negative'] = np.nan
    with pytest.raises(ValueError, match='没有有效统计量'):
        spc_plot(result, Figure())
    result.tables['observations'] = table.drop(columns='upper')
    figure = Figure()
    with pytest.raises(ValueError, match='缺少绘图列.*upper'):
        spc_plot(result, figure)
    assert not figure.axes


def test_cusum_requires_negative_current_but_not_history():
    result = SimpleNamespace(kind='CUSUM', tables={'observations': pd.DataFrame({
        'sequence': [1], 'statistic': [0.], 'lower': [-5.], 'center': [0.],
        'upper': [5.], 'alarm': [False], 'rules': ['']})})
    with pytest.raises(ValueError, match='negative'):
        spc_plot(result, Figure())


def test_no_metadata_does_not_invent_source_mapping(result):
    result.tables['observations'] = result.tables['observations'].drop(columns='source_row')
    picked = []
    _, handles = draw(result, picked.append)
    assert handles['connections'] == [] and picked == []


@pytest.mark.parametrize('phase,label', [('phase1', 'Phase I：基线回顾'),
                                        ('phase2', 'Phase II：新样本监控'), ('known', '已知参数')])
def test_backend_phase_overrides_default_title(result, phase, label):
    result.tables['observations']['phase'] = phase
    _, handles = draw(result)
    assert label in handles['axes'][0].get_title()


def test_single_observation_preserves_sequence_and_source(result):
    result.tables['observations'] = result.tables['observations'].iloc[[2]].copy()
    result.tables['observations']['sequence'] = 40
    picked = []
    figure, handles = draw(result, picked.append)
    axis = handles['axes'][0]
    np.testing.assert_array_equal(axis.lines[0].get_xdata(), [40])
    click(figure, axis, [40, result.tables['observations']['statistic'].iloc[0]])
    assert picked == [9]


def test_cusum_negative_branch_is_independently_pickable_when_positive_missing():
    result = SimpleNamespace(kind='CUSUM', tables={'observations': pd.DataFrame({
        'source_row': [42], 'sequence': [1], 'statistic': [np.nan], 'negative': [-6.],
        'lower': [-5.], 'center': [0.], 'upper': [5.], 'alarm': [True], 'rules': ['CUSUM-']})})
    picked = []
    figure, handles = draw(result, picked.append)
    click(figure, handles['axes'][0], [1, -6.])
    assert picked == [42]
    np.testing.assert_allclose(handles['axes'][0].collections[0].get_offsets(), [[1, -6.]])


@pytest.mark.parametrize('historical', [False, True])
def test_cusum_marks_only_branch_named_by_exact_rule(historical):
    table = pd.DataFrame({
        'sequence': [1, 2, 3, 4, 5], 'source_row': [2, 5, 8, 11, 14],
        'statistic': [0., 6., 7., 8., 9.], 'negative': [-6., 0., -7., -8., -9.],
        'lower': -5., 'center': 0., 'upper': 5., 'alarm': [True, True, True, True, False],
        'rules': ['CUSUM-', 'CUSUM+', 'CUSUM+; CUSUM-', 'NOT_CUSUM+', 'CUSUM+; CUSUM-']})
    result = SimpleNamespace(kind='CUSUM', tables={'observations': table})
    if historical:
        result.tables['baseline'] = table.copy()
    _, handles = draw(result)
    for axis in handles['axes']:
        np.testing.assert_allclose(axis.collections[0].get_offsets(),
                                   [[2, 6.], [3, 7.], [1, -6.], [3, -7.]])


@pytest.mark.parametrize('historical', [False, True])
def test_cusum_missing_rules_is_schema_error(historical):
    table = pd.DataFrame({'sequence': [1, 2], 'statistic': [0., 6.], 'negative': [-6., 0.],
                          'lower': -5., 'center': 0., 'upper': 5., 'alarm': [True, False],
                          'rules': ['CUSUM-', '']})
    tables = {'observations': table}
    tables['baseline' if historical else 'observations'] = table.drop(columns='rules')
    figure = Figure()
    with pytest.raises(ValueError, match='缺少绘图列：rules'):
        spc_plot(SimpleNamespace(kind='CUSUM', tables=tables), figure)
    assert not figure.axes


@pytest.mark.parametrize('kind,phase', [(kind, phase) for kind in KINDS
                         for phase in ('phase1', 'phase2', 'known')
                         if (kind, phase) != ('T2', 'known')])
def test_real_backend_result_smoke(kind, phase):
    from advanced_spc import analyze_spc

    rng = np.random.default_rng(760)
    baseline = pd.DataFrame(rng.normal(size=(80, 2)), columns=['x', 'y'])
    current = pd.DataFrame(rng.normal(size=(16, 2)), columns=['x', 'y'])
    current.iloc[-3:] += 8
    current.loc[[1, 4], 'y'] = np.nan
    options = {'baseline': baseline} if phase == 'phase2' else {'mean': 0., 'sigma': 1.} if phase == 'known' else {}
    result = analyze_spc(current, ['x', 'y'] if kind == 'T2' else ['y'], kind,
                         missing='drop', **options)
    table = result.tables['observations']
    picked = []
    figure, handles = draw(result, picked.append)
    axis = handles['axes'][0]
    np.testing.assert_allclose(axis.lines[0].get_xdata(), table['sequence'])
    np.testing.assert_allclose(axis.lines[0].get_ydata(), table['statistic'])
    np.testing.assert_allclose(axis.lines[-1].get_ydata(), table['upper'])
    assert (('Phase I：' if phase == 'phase1' else 'Phase II：') if phase != 'known' else '已知参数') in axis.get_title()
    columns = ['statistic', 'negative'] if kind == 'CUSUM' else ['statistic']
    if kind == 'CUSUM':
        expected_alarm = np.concatenate([
            table.loc[table['alarm'] & table['rules'].isin([rule, 'CUSUM+; CUSUM-']),
                      ['sequence', c]].to_numpy()
            for rule, c in [('CUSUM+', 'statistic'), ('CUSUM-', 'negative')]])
    else:
        expected_alarm = table.loc[table['alarm'], ['sequence', 'statistic']].to_numpy()
    np.testing.assert_allclose(axis.collections[0].get_offsets(), expected_alarm)
    assert table.source_row.tolist() == [1, 3, 4] + list(range(6, 17))
    click(figure, axis, [table.sequence.iloc[-1], table.statistic.iloc[-1]])
    assert picked == [16]
    if phase == 'phase2':
        assert len(handles['axes']) == 2
        history_axis = handles['axes'][1]
        historical = result.tables['baseline']
        np.testing.assert_allclose(history_axis.lines[-1].get_ydata(), historical['upper'])
        assert 'Phase I：' in history_axis.get_title()
        if kind == 'T2':
            assert historical.upper.iloc[0] != table.upper.iloc[0]
        click(figure, history_axis, [1, historical.statistic.iloc[0]])
        assert picked == [16]
