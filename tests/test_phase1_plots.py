from types import SimpleNamespace
import tkinter as tk

import numpy as np
import pandas as pd
import pytest

from pandastable_local.plotting import (PlotViewer, MPLBaseOptions, MPL3DOptions,
                                       AnnotationOptions, ExtraOptions, util)
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg


@pytest.fixture
def sample():
    return pd.DataFrame({'x': [0., 1., 0., 1., .5],
                         'y': [0., 0., 1., 1., .4],
                         'z': [1., 2., 3., 4., 2.3]})


@pytest.fixture
def legacy(sample, monkeypatch):
    monkeypatch.setattr(util, 'getFonts', lambda: [])
    viewer = PlotViewer.__new__(PlotViewer)
    viewer.fig = Figure()
    viewer.canvas = FigureCanvasAgg(viewer.fig)
    viewer.style = None
    viewer.globalopts = {'grid layout': 0, '3D plot': 0, 'dpi': 100}
    viewer.layoutopts = SimpleNamespace(modevar=SimpleNamespace(get=lambda: ''))
    for name, cls in [('mplopts', MPLBaseOptions), ('mplopts3d', MPL3DOptions),
                      ('labelopts', AnnotationOptions), ('styleopts', ExtraOptions)]:
        opts = cls()
        opts.kwds = {key: (bool(value.get('default', False))
                           if value['type'] == 'checkbutton' else value.get('default', ''))
                     for key, value in opts.opts.items()}
        if name == 'labelopts':
            opts.redraw = lambda: None
        setattr(viewer, name, opts)
    return viewer


@pytest.mark.parametrize('kind', ['bar', 'barh', 'pie', 'area', 'dotplot',
                                 'scatter_matrix', 'contour', 'scatter3d', 'surface'])
def test_legacy_nonempty_and_save(legacy, sample, kind, tmp_path):
    original = sample.copy(deep=True)
    legacy.data = sample
    warnings = []
    legacy.showWarning = warnings.append
    if kind in ('scatter3d', 'surface'):
        legacy.globalopts['3D plot'] = True
        legacy.mplopts3d.kwds['kind'] = 'scatter' if kind == 'scatter3d' else kind
    else:
        legacy.mplopts.kwds['kind'] = kind
    legacy.plotCurrent()
    assert not warnings, warnings
    assert any(ax.lines or ax.collections or ax.patches for ax in legacy.fig.axes)
    if kind == 'bar':
        np.testing.assert_allclose([p.get_height() for p in legacy.ax.patches[:5]], sample.x)
    elif kind == 'barh':
        np.testing.assert_allclose([p.get_width() for p in legacy.ax.patches[:5]], sample.x)
    elif kind == 'scatter_matrix':
        assert len(legacy.fig.axes) == 9
        assert len(legacy.fig.axes[1].collections[0].get_paths()[0].vertices) > 0
    elif kind == 'scatter3d':
        np.testing.assert_allclose(legacy.ax.collections[0]._offsets3d, sample.to_numpy().T)
    elif kind == 'surface':
        assert legacy.ax.collections[0].get_array().size > 0
    pd.testing.assert_frame_equal(sample, original)
    path = tmp_path / f'{kind}.png'
    legacy.savePlot(str(path))
    assert path.stat().st_size > 1000


@pytest.mark.parametrize('kind', ['bar', 'pie', 'area'])
def test_legacy_labels_do_not_mutate(legacy, sample, kind):
    sample.insert(0, 'label', ['a', 'b', 'a', 'd', 'e'])
    original = sample.copy(deep=True)
    legacy.data = sample
    legacy.mplopts.kwds.update(kind=kind, use_index=False)
    warnings = []
    legacy.showWarning = warnings.append
    legacy.plotCurrent()
    assert not warnings, warnings
    pd.testing.assert_frame_equal(sample, original)


@pytest.mark.parametrize('kind', ['bar', 'barh', 'pie', 'area', 'dotplot',
                                 'scatter_matrix', 'contour', 'scatter3d', 'surface'])
def test_legacy_missing_values(legacy, sample, kind):
    sample.loc[4, 'z'] = np.nan
    original = sample.copy(deep=True)
    legacy.data = sample
    warnings = []
    legacy.showWarning = warnings.append
    if kind in ('scatter3d', 'surface'):
        legacy.globalopts['3D plot'] = True
        legacy.mplopts3d.kwds['kind'] = 'scatter' if kind == 'scatter3d' else kind
    else:
        legacy.mplopts.kwds['kind'] = kind
    legacy.plotCurrent()
    assert not warnings, warnings
    assert any(ax.lines or ax.collections or ax.patches for ax in legacy.fig.axes)
    pd.testing.assert_frame_equal(sample, original)


@pytest.mark.parametrize('points, message', [
    ([[0, 0, 1], [1, 1, 2]], '至少'),
    ([[0, 0, 1], [1, 1, 2], [2, 2, 3]], '共线'),
    ([[0, 0, 1], [0, 0, 2], [1, 1, 3]], '重复'),
    ([[0, 0, 1], [1, 0, np.inf], [0, 1, 3]], '至少')])
def test_mesh_invalid(points, message):
    with pytest.raises(ValueError, match=message):
        PlotViewer.meshData(None, *np.array(points).T)


def test_mesh_plane_and_failed_interpolation(sample, monkeypatch):
    from scipy import interpolate
    from scipy.spatial import QhullError
    sample['z'] = sample.x + 2 * sample.y + 1
    X, Y, Z = PlotViewer.meshData(None, *sample.to_numpy().T)
    np.testing.assert_allclose(Z, X + 2 * Y + 1, atol=1e-6)
    def fail(*args, **kwargs):
        raise QhullError('test')
    monkeypatch.setattr(interpolate, 'griddata', fail)
    with pytest.raises(ValueError, match='插值失败'):
        PlotViewer.meshData(None, *sample.to_numpy().T)
    monkeypatch.setattr(interpolate, 'griddata', lambda *a, **k: np.full((50, 50), np.nan))
    with pytest.raises(ValueError, match='未产生'):
        PlotViewer.meshData(None, *sample.to_numpy().T)


@pytest.fixture
def app(tk_root, monkeypatch):
    from MiniJMP import Minijmp
    monkeypatch.setattr(Minijmp, 'start_logging', lambda self: None)
    previous = set(tk_root.winfo_children())
    created = Minijmp(parent=tk_root)
    yield created
    tk_root.configure(menu='')
    for widget in set(tk_root.winfo_children()) - previous:
        widget.destroy()


@pytest.mark.parametrize('kind,label', [
    ('bar', '条形图'), ('pie', '饼图'), ('area', '区域图'), ('dotplot', '点图'),
    ('scatter_matrix', '矩阵图'), ('contour', '等值线图'),
    ('scatter3d', '三维散点图'), ('surface', '三维曲面图')])
def test_real_menu_dialog_plot_save(app, sample, kind, label, monkeypatch, tmp_path):
    import basic_plot_dialog as basic
    app.table.model.df = sample.copy()
    original = app.table.model.df.copy(deep=True)
    dialogs = []
    init = basic.BasicPlotDialog.__init__
    def record(self, *args, **kwargs):
        init(self, *args, **kwargs)
        dialogs.append(self)
    monkeypatch.setattr(basic.BasicPlotDialog, '__init__', record)
    menu = app.plots_menu['var']
    index = next(i for i in range(menu.index('end') + 1)
                 if menu.type(i) == 'command' and menu.entrycget(i, 'label').strip() == label)
    menu.invoke(index)
    dialog, = dialogs
    errors = []
    dialog.error = errors.append
    if kind in ('contour', 'scatter3d', 'surface'):
        for var, col in zip(dialog.xyz, sample.columns):
            var.set(col)
    else:
        cols = ['z'] if kind == 'pie' else list(sample.columns)
        monkeypatch.setattr(dialog.variables, 'getSelectedItem', lambda: cols)
    dialog.preview()
    assert not errors, errors
    viewer = app.table.pf
    assert any(ax.lines or ax.collections or ax.patches for ax in viewer.fig.axes)
    if kind == 'bar':
        np.testing.assert_allclose([p.get_height() for p in viewer.ax.patches[:5]], sample.x)
        dialog.horizontal.set(True)
        dialog.preview()
        viewer = app.table.pf
        np.testing.assert_allclose([p.get_width() for p in viewer.ax.patches[:5]], sample.x)
    elif kind == 'scatter_matrix':
        assert len(viewer.fig.axes) == 9
        np.testing.assert_allclose(viewer.fig.axes[1].collections[0].get_offsets(), sample[['y', 'x']])
    elif kind == 'dotplot':
        assert len(viewer.ax.get_xticklabels()) == 3
        points = [l for l in viewer.ax.lines if l.get_marker() == 'o' and len(l.get_ydata()) == len(sample)]
        assert len(points) == 3
        for col, line in zip(sample.columns, points):
            np.testing.assert_allclose(line.get_ydata(), sample[col])
    path = tmp_path / f'menu-{kind}.png'
    viewer.savePlot(str(path))
    assert path.stat().st_size > 1000
    pd.testing.assert_frame_equal(app.table.model.df, original)
    viewer.close()
    dialog.quit()


@pytest.mark.parametrize('kind,cols,values,message', [
    ('bar', [], [[1, 2, 3]], '选择'),
    ('bar', ['absent'], [[1, 2, 3]], '选择'),
    ('bar', ['x'], [['bad', 2, 3]], 'parse'),
    ('bar', ['x'], [[np.nan, 2, 3]], '没有'),
    ('bar', ['x'], [[np.inf, 2, 3]], '没有'),
    ('pie', ['x', 'y'], [[1, 2, 3]], '一列'),
    ('pie', ['x'], [[-1, 2, 3]], '非负'),
    ('pie', ['x'], [[0, 2, 3]], '大于零'),
    ('dotplot', ['x', 'y'], [[1, np.nan, 3]], '每个'),
    ('scatter_matrix', ['x'], [[1, 2, 3]], '两列'),
    ('scatter_matrix', ['x', 'y'], [[1, 2, 3], [1, 3, 4]], '不同'),
    ('contour', ['x', 'y', 'z'], [[0, 0, 1], [1, 1, 2], [2, 2, 3]], '共线'),
    ('surface', ['x', 'y', 'z'], [[0, 0, 1], [1, 0, 2]], '至少'),
    ('scatter3d', ['x', 'x', 'z'], [[0, 0, 1]], '不同的列'),
])
def test_dialog_invalid_does_not_replace_plot(kind, cols, values, message):
    from basic_plot_dialog import BasicPlotDialog
    dialog = BasicPlotDialog.__new__(BasicPlotDialog)
    dialog.kind = kind
    dialog.df = pd.DataFrame(values, columns=['x', 'y', 'z'])
    original = dialog.df.copy(deep=True)
    dialog.variables = SimpleNamespace(getSelectedItem=lambda: cols)
    dialog.xyz = [SimpleNamespace(get=lambda c=c: c) for c in cols]
    dialog.labels = SimpleNamespace(get=lambda: '')
    errors = []
    dialog.error = errors.append
    def forbidden():
        pytest.fail('无效输入不得替换当前图形')
    dialog.showPlotViewer = forbidden
    dialog.apply()
    assert len(errors) == 1 and message in errors[0], errors
    pd.testing.assert_frame_equal(dialog.df, original)


def test_duplicate_index_labels_and_missing_preserve_rows(app, sample, monkeypatch):
    from basic_plot_dialog import BasicPlotDialog
    sample.index = [1, 1, 2, 2, 2]
    sample['label'] = ['甲', '甲', '乙', '丙', '丁']
    sample.loc[2, 'z'] = np.nan
    app.table.model.df = sample
    original = sample.copy(deep=True)
    dialog = BasicPlotDialog(app.table, app=app, df=sample, kind='bar')
    monkeypatch.setattr(dialog.variables, 'getSelectedItem', lambda: ['z'])
    dialog.labels.set('label')
    dialog.apply()
    assert [p.get_height() for p in app.table.pf.ax.patches] == [1., 2.]
    assert [t.get_text() for t in app.table.pf.ax.get_xticklabels()] == ['甲', '甲']
    pd.testing.assert_frame_equal(sample, original)
    app.table.pf.close()
    dialog.quit()


@pytest.mark.parametrize('kind,topic', [('bar', 'basic'), ('pie', 'pie'), ('area', 'area'),
                                     ('dotplot', 'dot'), ('scatter_matrix', 'matrix'),
                                     ('contour', 'contour'), ('scatter3d', 'scatter3d'), ('surface', 'surface')])
def test_dialog_help_routes(kind, topic, monkeypatch):
    from basic_plot_dialog import BasicPlotDialog
    import help_link
    dialog = BasicPlotDialog.__new__(BasicPlotDialog)
    dialog.kind, dialog.main = kind, object()
    calls = []
    monkeypatch.setattr(help_link, 'open_help', lambda key, parent: calls.append((key, parent)))
    assert dialog.help() == 'break'
    assert calls == [('plots.' + topic, dialog.main)]


def test_legacy_four_point_3d_color_is_uniform(legacy, sample):
    legacy.data = sample.iloc[:4]
    legacy.globalopts['3D plot'] = True
    legacy.mplopts3d.kwds['kind'] = 'scatter'
    legacy.plotCurrent()
    colors = legacy.ax.collections[0].get_facecolor()
    # 3D 深度可改变透明度，但不应把 RGBA 四元组解释为四个点的数值。
    np.testing.assert_allclose(colors[:, :3], np.broadcast_to(colors[0, :3], colors[:, :3].shape))


def test_legacy_surface_triangle_finite_color_limits(legacy):
    legacy.data = pd.DataFrame({'x': [0., 1., 0.], 'y': [0., 0., 1.], 'z': [1., 2., 3.]})
    legacy.globalopts['3D plot'] = True
    legacy.mplopts3d.kwds['kind'] = 'surface'
    legacy.plotCurrent()
    limits = legacy.ax.collections[0].get_clim()
    np.testing.assert_allclose(limits, [1., 3.], atol=1e-6)
