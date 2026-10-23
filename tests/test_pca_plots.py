"""PCA plotting contract: hand-computed geometry/data, Agg interactions and PNG I/O.

Production → independent reference → boundaries:
_ellipse → diagonal covariance (4,1), χ²(2) quantile = -2 log(1-p) → 95/99%, singular;
pca_plot selectors → inclusive rectangle / unit-circle inequalities → reversed, edge, empty;
pca_plot clicks → explicit display-pixel distances → nearest category, >10px, source position;
other plots → literal eigenvalue/cumulative/contribution fixture → all eleven kinds, projection.
"""

from types import SimpleNamespace
import gc
import weakref

from matplotlib.backend_bases import MouseEvent
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.patches import Ellipse
from matplotlib.widgets import EllipseSelector, RectangleSelector
import numpy as np
import pandas as pd
from PIL import Image
import pytest

from pca_plots import pca_plot


@pytest.fixture
def model():
    scores = np.array([[-2., 0., 1.], [2., 0., -1.], [0., -1., 2.],
                       [0., 1., -2.], [0., 0., 0.]])
    residuals = np.array([[1., 2., 3.], [2., 1., 0.], [0., 1., 2.],
                          [1., 0., 1.], [0., 0., 0.]])
    training = SimpleNamespace(
        scores=scores, t2=np.array([1., 2., 3., 10., 0.]), q=np.array([14., 5., 5., 2., 0.]),
        scaled=scores.copy(), residuals=residuals, reconstructed=scores-residuals,
        data=pd.DataFrame(scores, columns=['x', 'y', 'z']),
        phase='phase1', source=pd.DataFrame({'source_row': [2, 5, 7, 9, 12],
                             'source_index': ['a', 'a', 'c', 'd', 'e']}),
        tables={'monitoring': pd.DataFrame({'t2_flag_95': [False, False, False, True, False],
                  'q_flag_95': [True, False, False, False, False],
                  't2_flag_99': [False, False, False, False, False],
                  'q_flag_99': [True, False, False, False, False]})})

    def contributions(row, kind='t2', projection=None):
        data = training if projection is None else projection
        # Deliberately reverse variable order to verify alignment by variable name.
        values = data.residuals[row]**2 if kind == 'q' else data.scores[row]**2/np.array([4., 1., .5])
        return pd.DataFrame({'variable': ['z', 'y', 'x'], 'contribution': values[::-1]})

    return SimpleNamespace(columns=['x', 'y', 'z'], eigenvalues=np.array([4., 1., .5]),
                           loadings=np.eye(3), n_components=3, training=training,
                           contributions=contributions,
                           tables={'limits': pd.DataFrame({'phase': ['phase1', 'phase1', 'phase2', 'phase2'],
                               'confidence': [.95, .99, .95, .99], 't2': [5., 8., 9., 13.],
                               'q': [8., 12., 8., 12.], 't2_method': ['Beta', 'Beta', 'F', 'F'],
                               'q_method': ['Q 近似']*4})})


def plot(model, kind='score', **kwargs):
    figure = Figure(figsize=(8, 5))
    FigureCanvasAgg(figure)
    handles = pca_plot(model, kind, figure, **kwargs)
    return figure, handles


@pytest.mark.parametrize('kind', ['scree', 'cumulative', 'score', 'loading', 'biplot',
                                  't2', 'q', 'contribution_t2', 'contribution_q',
                                  'single_variable', 'compare_contribution'])
def test_all_kinds_save_and_reopen(model, kind, tmp_path):
    options = {'variable': 'x'} if kind == 'single_variable' else {}
    if kind == 'compare_contribution':
        options['groups'] = {'A': [0, 1], 'B': [3]}
    fig, handles = plot(model, kind, **options)
    assert len(handles['axes']) == 1
    fig.canvas.draw()
    filename = tmp_path / f'{kind}.png'
    fig.savefig(filename)
    with Image.open(filename) as image:
        assert image.size == (800, 500)
        image.verify()


def test_scree_and_cumulative_include_discarded_eigenvalues(model):
    model.n_components = 2
    _, handles = plot(model, 'scree')
    np.testing.assert_allclose(handles['axes'][0].lines[0].get_ydata(), [4., 1., .5])
    _, handles = plot(model, 'cumulative')
    np.testing.assert_allclose(handles['axes'][0].lines[0].get_ydata(), [800/11, 1000/11, 100.])


@pytest.mark.parametrize('confidence', [.95, .99])
def test_score_ellipse_hand_computed_covariance(model, confidence):
    # Five rows have covariance diag(2, .5); not the eigenvalues in model.
    _, handles = plot(model, confidence=confidence)
    ellipse = next(p for p in handles['axes'][0].patches if isinstance(p, Ellipse))
    quantile = -2*np.log(1-confidence)  # exact CDF inverse for χ²(2)
    np.testing.assert_allclose([ellipse.width, ellipse.height],
                               [2*np.sqrt(2*quantile), 2*np.sqrt(.5*quantile)])
    np.testing.assert_allclose(ellipse.center, [0, 0])
    assert ellipse.get_label() == f'{confidence:.0%} 得分覆盖轮廓'


def test_projection_ellipse_uses_training_covariance(model):
    projection = SimpleNamespace(**vars(model.training))
    projection.scores = model.training.scores+30
    _, handles = plot(model, projection=projection)
    ellipse = next(p for p in handles['axes'][0].patches if isinstance(p, Ellipse))
    np.testing.assert_allclose(ellipse.center, [0, 0])
    np.testing.assert_allclose(handles['points'][0][0].get_offsets(), projection.scores[:, :2])


def test_singular_ellipse_explains_omission(model):
    model.training.scores[:, 1] = 0
    _, handles = plot(model)
    assert not handles['axes'][0].patches
    assert any('奇异' in t.get_text() for t in handles['axes'][0].texts)


def test_arbitrary_components_and_loading_coordinates(model):
    _, handles = plot(model, components=(3, 1))
    np.testing.assert_allclose(handles['points'][0][0].get_offsets(), model.training.scores[:, [2, 0]])
    _, handles = plot(model, 'loading', components=(3, 1))
    texts = {t.get_text(): t.get_position() for t in handles['axes'][0].texts if t.get_text()}
    assert texts == {'x': (0., 1.), 'y': (0., 0.), 'z': (1., 0.)}


@pytest.mark.parametrize('components', [(1, 1), (0, 2), (1, 4), (1.5, 2), (True, 2), (1,)])
@pytest.mark.parametrize('kind', ['score', 'loading', 'biplot'])
def test_invalid_components_do_not_add_axes(model, components, kind):
    fig = Figure()
    with pytest.raises(ValueError, match='主成分'):
        pca_plot(model, kind, fig, components=components)
    assert not fig.axes


def test_one_component_errors_clearly_but_can_plot_scree(model):
    model.n_components = 1
    with pytest.raises(ValueError, match='至少需要保留 2'):
        plot(model)
    plot(model, 'scree')


@pytest.mark.parametrize('projection,expected', [(False, [5., 8.]), (True, [9., 13.])])
def test_t2_limit_scene_and_source_row(model, projection, expected):
    data = SimpleNamespace(**vars(model.training)) if projection else None
    if data is not None:
        data.phase = 'phase2'
    _, handles = plot(model, 't2', projection=data)
    axis = handles['axes'][0]
    np.testing.assert_allclose(axis.lines[0].get_xdata(), [2, 5, 7, 9, 12])
    assert [line.get_ydata()[0] for line in axis.lines[1:]] == expected
    abnormal = axis.collections[-1].get_offsets()
    np.testing.assert_allclose(abnormal, [[9., 10.]])


def test_score_flags_combine_t2_and_q(model):
    _, handles = plot(model)
    abnormal = next(a for a in handles['axes'][0].collections if a.get_label() == '95% 监控异常')
    np.testing.assert_allclose(abnormal.get_offsets(), [[-2., 0.], [0., 1.]])


def test_flags_use_selected_confidence(model):
    _, handles = plot(model, confidence=.99)
    abnormal = next(a for a in handles['axes'][0].collections if a.get_label() == '99% 监控异常')
    np.testing.assert_allclose(abnormal.get_offsets(), [[-2., 0.]])


@pytest.mark.parametrize('missing', [pd.NA, None])
@pytest.mark.parametrize('kind', ['score', 'biplot', 't2', 'q'])
def test_nullable_flags_are_not_reported_as_normal(model, missing, kind):
    monitoring = model.training.tables['monitoring']
    statistic = 'q' if kind == 'q' else 't2'
    monitoring[statistic+'_flag_95'] = [missing, False, False, False, False]
    _, handles = plot(model, kind)
    axis = handles['axes'][0]
    unknown = next(a for a in axis.collections if a.get_label() == '判异不可用')
    assert len(unknown.get_offsets()) == 1
    assert any('不能视为统计正常' in t.get_text() for t in axis.texts)


def test_vectorized_contribution_paths_use_signed_t2_definition(model):
    # A rank-one loading (3/5,4/5), λ=2: row (2,-1) has score 2/5,
    # hence signed contributions (6/25,-4/25); row (1,3) gives (9/10,18/5).
    # This rejects squared-loading/squared-score approximations that lose signs.
    model.columns = ['x', 'y']
    model.n_components = 1
    model.eigenvalues = np.array([2., 0.])
    model.loadings = np.array([[.6], [.8]])
    model.training.scores = np.array([[.4], [3.]])
    model.training.scaled = np.array([[2., -1.], [1., 3.]])
    model.training.residuals = np.array([[1.76, -1.32], [-.8, .6]])

    def no_per_row_dataframe(*args, **kwargs):
        raise AssertionError('Vectorized plot must not construct contribution DataFrames per row')

    model.contributions = no_per_row_dataframe
    _, handles = plot(model, 'compare_contribution', variable='t2', groups={'A': [0, 1], 'B': [0]})
    np.testing.assert_allclose([b.get_height() for b in handles['axes'][0].patches],
                               [.57, 1.72, .24, -.16])
    _, handles = plot(model, 'compare_contribution', variable='q', groups={'A': [0, 1], 'B': [0]})
    np.testing.assert_allclose([b.get_height() for b in handles['axes'][0].patches],
                               [1.8688, 1.0512, 3.0976, 1.7424])
    # Keep source row metadata consistent for the per-sample series.
    model.training.source = model.training.source.iloc[:2].copy()
    _, handles = plot(model, 'single_variable', variable='y')
    np.testing.assert_allclose(handles['axes'][0].lines[0].get_ydata(), [1.7424, .36])


@pytest.mark.parametrize('shape,expected', [('rectangle', [0, 1, 2, 3, 4]), ('ellipse', [2, 3, 4])])
def test_selector_boundaries_are_inclusive_and_reversed(model, shape, expected):
    # Rectangle [-2,2]×[-1,1] contains all. Ellipse radii (2,1): all four axial
    # endpoints lie ON boundary; replace PC1 coordinates to test diagonal corners.
    model.training.scores[:, :2] = [[-2., -1.], [2., 1.], [0., -1.], [0., 1.], [0., 0.]]
    calls = []
    _, handles = plot(model, on_select=lambda rows, group: calls.append((rows, group)),
                      selection_shape=shape, active_group='B', groups={'A': [1, 3]})
    selector = handles['selectors'][0]
    assert isinstance(selector, RectangleSelector if shape == 'rectangle' else EllipseSelector)
    selector.onselect(SimpleNamespace(xdata=2., ydata=1.), SimpleNamespace(xdata=-2., ydata=-1.))
    np.testing.assert_array_equal(calls[0][0], expected)
    assert calls[0][1] == 'B'
    np.testing.assert_array_equal(handles['groups']['A'], [1, 3])
    np.testing.assert_array_equal(handles['groups']['B'], expected)
    highlights = {a.get_label(): a for a in handles['axes'][0].collections}
    np.testing.assert_allclose(highlights['选区 A'].get_offsets(), [[2., 1.], [0., 1.]])
    assert len(highlights['选区 B'].get_offsets()) == len(expected)


def test_ellipse_axial_boundary_and_degenerate_selection(model):
    calls = []
    _, handles = plot(model, on_select=lambda rows, _: calls.append(rows), selection_shape='ellipse')
    selector = handles['selectors'][0]
    selector.onselect(SimpleNamespace(xdata=-2., ydata=-1.), SimpleNamespace(xdata=2., ydata=1.))
    np.testing.assert_array_equal(calls[-1], [0, 1, 2, 3, 4])
    selector.onselect(SimpleNamespace(xdata=0., ydata=-1.), SimpleNamespace(xdata=0., ydata=1.))
    assert calls[-1].size == 0


def test_real_mouse_drag_and_selector_strong_reference(model):
    calls = []
    fig, handles = plot(model, on_select=lambda rows, group: calls.append((rows, group)))
    reference = weakref.ref(handles['selectors'][0])
    gc.collect()
    assert reference() is not None
    fig.canvas.draw()
    axis = handles['axes'][0]
    for name, data in [('button_press_event', (-.5, -.5)), ('motion_notify_event', (.5, .5)),
                       ('button_release_event', (.5, .5))]:
        x, y = axis.transData.transform(data)
        event = MouseEvent(name, fig.canvas, x, y, button=1)
        fig.canvas.callbacks.process(name, event)
    assert calls[-1][1] == 'A'
    np.testing.assert_array_equal(calls[-1][0], [4])
    reference().disconnect_events()


def test_click_returns_effective_position_not_dataframe_index_or_source_row(model):
    calls = []
    fig, handles = plot(model, on_pick=calls.append, labels=['a', 'b', 'b', None, 'a'])
    fig.canvas.draw()
    axis = handles['axes'][0]
    x, y = axis.transData.transform([2., 0.])
    fig.canvas.callbacks.process('button_press_event', MouseEvent('button_press_event', fig.canvas, x, y, button=1))
    assert calls == [1]
    assert all(not artist.get_picker() for artist, _ in handles['points'])
    annotation = [t for t in axis.texts if t.get_visible() and '来源行：' in t.get_text()]
    assert annotation[0].get_text() == '来源行：5'
    for event in [MouseEvent('button_press_event', fig.canvas, x+20, y+20, button=1),
                  MouseEvent('button_press_event', fig.canvas, x, y, button=3),
                  MouseEvent('button_press_event', fig.canvas, 0, 0, button=1)]:
        fig.canvas.callbacks.process('button_press_event', event)
    assert calls == [1]


def test_click_is_globally_nearest_across_category_artists(model):
    model.training.scores[1, :2] = [-1.96, 0.]
    calls = []
    fig, _ = plot(model, labels=['first', 'second', 'first', 'second', 'first'], on_pick=calls.append)
    fig.canvas.draw()
    x, y = fig.axes[0].transData.transform([-1.96, 0.])
    fig.canvas.callbacks.process('button_press_event', MouseEvent('button_press_event', fig.canvas, x, y, button=1))
    assert calls == [1]


def test_contributions_align_columns_and_average_groups(model):
    _, handles = plot(model, 'contribution_q', contribution_row=0)
    assert [bar.get_height() for bar in handles['axes'][0].patches] == [1., 4., 9.]
    assert handles['axes'][0].get_title() == '来源行 2 的 Q 贡献'
    _, handles = plot(model, 'contribution_t2', contribution_row=1)
    assert handles['axes'][0].get_title() == '来源行 5 的 T² 贡献'
    _, handles = plot(model, 'single_variable', variable='y')
    np.testing.assert_allclose(handles['axes'][0].lines[0].get_ydata(), [4., 1., 1., 0., 0.])
    _, handles = plot(model, 'compare_contribution', groups={'A': [0, 1], 'B': [3]})
    assert [bar.get_height() for bar in handles['axes'][0].patches] == [2.5, 2.5, 4.5, 1., 0., 1.]
    _, handles = plot(model, 'compare_contribution', variable='t2', groups={'A': [0], 'B': [1]})
    assert [bar.get_height() for bar in handles['axes'][0].patches] == [1., 0., 2., 1., 0., 2.]


def test_labels_groups_do_not_mutate_caller_data(model):
    source = model.training.source.copy(deep=True)
    data = model.training.data.copy(deep=True)
    groups = {'A': [0, 1], 'B': [2]}
    _, handles = plot(model, labels=['a', None, 'b', 'a', 'b'], groups=groups,
                      on_select=lambda *_: None)
    handles['selectors'][0].onselect(SimpleNamespace(xdata=-.1, ydata=-.1),
                                    SimpleNamespace(xdata=.1, ydata=.1))
    assert groups == {'A': [0, 1], 'B': [2]}
    pd.testing.assert_frame_equal(model.training.source, source)
    pd.testing.assert_frame_equal(model.training.data, data)


@pytest.mark.parametrize('kwargs,match', [({'kind': 'unknown'}, '未知'),
    ({'confidence': 1.}, '置信'), ({'labels': ['short']}, '标签'),
    ({'selection_shape': 'triangle'}, '形状'), ({'active_group': 'C'}, '活动'),
    ({'groups': {'A': [5]}}, '样本位置'), ({'groups': {'B': [-1]}}, '样本位置'),
    ({'groups': {'A': [1.5]}}, '样本位置'),
    ({'kind': 'single_variable', 'variable': 'missing'}, '变量'),
    ({'kind': 'compare_contribution', 'groups': {'A': [1]}}, '两组'),
    ({'kind': 'contribution_q', 'contribution_row': -1}, '样本位置')])
def test_invalid_inputs(model, kwargs, match):
    kind = kwargs.pop('kind', 'score')
    with pytest.raises(ValueError, match=match):
        plot(model, kind, **kwargs)


@pytest.fixture
def fitted_model():
    from pca_analysis import fit_pca
    data = pd.DataFrame({'x': [1., 4., np.nan, 3., 8., 2., 6., 5., 9.],
                         'y': [3., 2., 7., 6., 1., 9., 4., 8., 5.],
                         'z': [4., 9., 1., 2., 7., 6., 3., 5., 8.]},
                        index=['duplicate']*9)
    return fit_pca(data, ['x', 'y', 'z'], n_components=2, missing='drop')


@pytest.mark.parametrize('kind', ['scree', 'cumulative', 'score', 'loading', 'biplot',
                                  't2', 'q', 'contribution_t2', 'contribution_q',
                                  'single_variable', 'compare_contribution'])
def test_real_fit_pca_all_plot_kinds(fitted_model, kind):
    kwargs = {'groups': {'A': [0, 1], 'B': [2, 3]}}
    if kind == 'single_variable':
        kwargs['variable'] = 'z'
    fig, handles = plot(fitted_model, kind, **kwargs)
    fig.canvas.draw()
    assert len(handles['axes']) == 1
    if kind in ('t2', 'q', 'single_variable'):
        np.testing.assert_array_equal(handles['axes'][0].lines[0].get_xdata(), [1, 2, 4, 5, 6, 7, 8, 9])


def test_real_projection_uses_phase2_control_limits(fitted_model):
    projection = fitted_model.project(pd.DataFrame({'x': [100., 150.], 'y': [2., 30.], 'z': [9., 10.]}))
    fig, handles = plot(fitted_model, 't2', projection=projection, confidence=.99)
    fig.canvas.draw()
    limits = fitted_model.tables['limits'].query('phase == "phase2"')
    np.testing.assert_allclose([line.get_ydata()[0] for line in handles['axes'][0].lines[1:]], limits.t2)
    assert all('F ' in line.get_label() for line in handles['axes'][0].lines[1:])
    np.testing.assert_array_equal(handles['points'][0][1], [0, 1])


def test_real_no_centering_marks_t2_unavailable(fitted_model):
    from pca_analysis import fit_pca
    model = fit_pca(fitted_model.training.data, fitted_model.columns, n_components=2, scaling='none')
    fig, handles = plot(model, 't2')
    fig.canvas.draw()
    assert len(handles['axes'][0].lines) == 1  # No invented finite T² limit.
    unknown = next(a for a in handles['axes'][0].collections if a.get_label() == '判异不可用')
    assert len(unknown.get_offsets()) == len(model.training.data)


def test_connections_can_be_disconnected_before_redraw(model):
    fig, handles = plot(model, on_select=lambda *_: None, on_pick=lambda _: None)
    for selector in handles['selectors']:
        selector.disconnect_events()
    for cid in handles['connections']:
        fig.canvas.mpl_disconnect(cid)
    assert all(cid not in callbacks for callbacks in fig.canvas.callbacks.callbacks.values()
               for cid in handles['connections'])
    fig.clear()
    pca_plot(model, 'score', fig)
    fig.canvas.draw()


def test_click_ten_pixel_inclusive_threshold(model):
    calls = []
    fig, handles = plot(model, on_pick=calls.append)
    fig.canvas.draw()
    axis = handles['axes'][0]
    x, y = axis.transData.transform([2., 0.])
    for offset in (10., 11.):
        event = MouseEvent('button_press_event', fig.canvas, x+offset, y, button=1)
        # MouseEvent normally rounds positions to integer pixels. Preserve the exact
        # transformed offset here to independently check the inclusive cutoff.
        event.x, event.y = x+offset, y
        fig.canvas.callbacks.process('button_press_event', event)
    assert calls == [1]
