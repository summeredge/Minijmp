"""真实菜单/对话框及独立数值参考；不替代人工操作验收。"""
import numpy as np
import pandas as pd
import pytest
from PIL import Image
from scipy import stats

from stat_plot_dialog import StatPlotDialog, TITLES
from test_phase1_plots import app


@pytest.fixture
def sample():
    return pd.DataFrame({'x': [1., 2., 2., 4., np.nan, np.inf],
                         'y': [3., 5., 7., 9., 11., 12.],
                         'size': [0., 2., 4., 8., 1., 1.],
                         'group': ['a', 'a', 'b', 'b', 'b', None]}, index=[0, 0, 1, 1, 2, 2])


def select(dialog, cols):
    if hasattr(dialog, 'xyz'):
        for var, col in zip(dialog.xyz, cols):
            var.set(col)
    else:
        # 与用户多选相同的真实 Tk Listbox selection。
        box = dialog.variables
        box.selection_clear(0, 'end')
        for col in cols:
            box.selection_set(dialog.cols.index(col))


@pytest.mark.parametrize('kind', list(TITLES))
def test_real_menu_output_and_export(app, sample, kind, monkeypatch, tmp_path):
    app.table.model.df = sample
    before = sample.copy(deep=True)
    dialogs = []
    init = StatPlotDialog.__init__
    def record(self, *args, **kwargs):
        init(self, *args, **kwargs)
        dialogs.append(self)
    monkeypatch.setattr(StatPlotDialog, '__init__', record)
    menu = app.plots_menu['var']
    index = next(i for i in range(menu.index('end') + 1)
                 if menu.type(i) == 'command' and menu.entrycget(i, 'label').strip() == TITLES[kind])
    menu.invoke(index)
    dialog, = dialogs
    cols = {'bubble': ['x', 'y', 'size'], 'marginal': ['x', 'y'],
            'stem': ['x'], 'probability': ['x']}.get(kind, ['x', 'y'])
    select(dialog, cols)
    if hasattr(dialog, 'group'):
        dialog.group.set('group')
    errors = []
    dialog.error = errors.append
    dialog.preview()
    assert not errors, errors
    if kind == 'stem':
        assert app.table.tOut is not None
        path = tmp_path / 'stem.txt'
        app.table.tOut.save(str(path))
        text = path.read_text(encoding='utf-8')
        assert '茎叶图' in text and '叶单位' in text
        pd.testing.assert_frame_equal(sample, before)
        dialog.quit()
        return
    viewer = app.table.pf
    assert any(ax.lines or ax.collections or ax.patches for ax in viewer.fig.axes)
    for suffix in ('png', 'svg', 'pdf'):
        path = tmp_path / f'{kind}.{suffix}'
        viewer.savePlot(str(path))
        assert path.stat().st_size > 1000
        if suffix == 'png':
            with Image.open(path) as image:
                image.load()
                assert np.asarray(image.convert('RGB')).std() > 1
    pd.testing.assert_frame_equal(sample, before)
    viewer.close()
    dialog.quit()


@pytest.mark.parametrize('kind', ['bubble', 'ecdf', 'individual', 'interval'])
def test_independent_references(app, sample, kind):
    dialog = StatPlotDialog(app.table, df=sample, app=app, kind=kind)
    select(dialog, ['x', 'y', 'size'] if kind == 'bubble' else ['x'])
    dialog.apply()
    ax = app.table.pf.ax
    if kind == 'bubble':
        np.testing.assert_allclose(ax.collections[0].get_offsets(), [[1, 3], [2, 5], [2, 7], [4, 9]])
        np.testing.assert_allclose(ax.collections[0].get_sizes(), [0, 125, 250, 500])
    elif kind == 'ecdf':
        line = ax.lines[0]
        xs, ys = line.get_data()
        # 独立定义 F(t) = #{X <= t}/n，重复值跳跃取最右端。
        for x in [1., 2., 4.]:
            assert ys[np.where(xs == x)[0][-1]] == sum(v <= x for v in [1, 2, 2, 4]) / 4
        assert ax.get_ylim() == (0., 1.)
    elif kind == 'individual':
        np.testing.assert_allclose(ax.collections[0].get_offsets()[:, 1], [1, 2, 2, 4])
    else:
        # n=4, mean=2.25, unbiased variance=1.583333..., t_(.975,3)=3.182446...
        margin = 3.182446305284263 * np.sqrt(19 / 12) / 2
        line = next(l for l in ax.lines if len(l.get_ydata()) > 2)
        ys = np.asarray(line.get_ydata())
        assert np.nanmin(ys) == pytest.approx(2.25 - margin)
        assert np.nanmax(ys) == pytest.approx(2.25 + margin)
    app.table.pf.close()
    dialog.quit()


@pytest.mark.parametrize('kind', ['bubble', 'ecdf', 'individual', 'interval'])
@pytest.mark.parametrize('bad', ['text', 'empty', 'selection', 'reference'])
def test_invalid_preserves_viewer(app, sample, kind, bad, monkeypatch):
    sample = sample.copy()
    if bad == 'text':
        sample['x'] = '错误'
    if bad == 'empty':
        sample['x'] = np.nan
    dialog = StatPlotDialog(app.table, df=sample, app=app, kind=kind)
    select(dialog, ['x', 'y', 'size'] if kind == 'bubble' else ['x'])
    if bad == 'selection':
        if kind == 'bubble':
            dialog.xyz[0].set('')
        else:
            dialog.variables.selection_clear(0, 'end')
    if bad == 'reference':
        dialog.yref.set('inf')
    errors = []
    dialog.error = errors.append
    monkeypatch.setattr(dialog, 'showPlotViewer', lambda: pytest.fail('替换了已有图形'))
    dialog.apply()
    assert errors
    dialog.quit()


def test_interval_constant_and_singleton(app):
    dialog = StatPlotDialog(app.table, df=pd.DataFrame({'x': [2., 2.]}), app=app, kind='interval')
    select(dialog, ['x'])
    dialog.apply()
    assert app.table.pf.ax.lines[0].get_ydata()[0] == 2
    app.table.pf.close()
    dialog.df = pd.DataFrame({'x': [2.]})
    errors = []
    dialog.error = errors.append
    dialog.apply()
    assert '至少两个' in errors[0]
    dialog.quit()


def test_stem_signed_decimal_duplicates_and_range():
    from stat_plot_dialog import stem_leaf
    text = stem_leaf([-12.3, -1.2, -.2, 0., .2, 1.2, 1.2, 12.3], '-1')
    assert 'N = 8' in text and '叶单位 = 0.1' in text
    for row in ['-12 | 3', '-1 | 2', '-0 | 2', '0 | 0 2', '1 | 2 2', '12 | 3']:
        assert row in text
    assert '0 | 9' in stem_leaf([.999], '-1')
    with pytest.raises(ValueError, match='范围过大'):
        stem_leaf([0., 1e20], '0')
    with pytest.raises(ValueError):
        stem_leaf([1.], '1.5')


@pytest.mark.parametrize('kind', ['marginal', 'probability', 'stem'])
def test_batch2_reference(app, sample, kind):
    dialog = StatPlotDialog(app.table, df=sample, app=app, kind=kind)
    select(dialog, ['x', 'y'] if kind == 'marginal' else ['x'])
    if kind == 'stem':
        output = []
        dialog.app.print = output.append
        dialog.apply()
        assert 'N = 4' in output[0]
        assert '2 | 0 0' in output[0]
    else:
        dialog.apply()
        axes = app.table.pf.fig.axes
        if kind == 'marginal':
            np.testing.assert_allclose(axes[0].collections[0].get_offsets(), [[1, 3], [2, 5], [2, 7], [4, 9]])
            assert sum(p.get_height() for p in axes[1].patches) == 4
            assert sum(p.get_width() for p in axes[2].patches) == 4
        else:
            # Filliben plotting positions, independently constructed; OLS via numpy.
            positions = [1 - .5**.25, (2 - .3175) / 4.365, (3 - .3175) / 4.365, .5**.25]
            theoretical = stats.norm.ppf(positions)
            np.testing.assert_allclose(axes[0].lines[0].get_xdata(), theoretical)
            np.testing.assert_allclose(axes[0].lines[0].get_ydata(), [1, 2, 2, 4])
            fit = np.polyfit(theoretical, [1, 2, 2, 4], 1)
            np.testing.assert_allclose(axes[0].lines[1].get_ydata(), np.polyval(fit, theoretical))
        app.table.pf.close()
    dialog.quit()


@pytest.mark.parametrize('kind', ['marginal', 'probability', 'stem'])
def test_batch2_invalid(app, sample, kind, monkeypatch):
    dialog = StatPlotDialog(app.table, df=sample, app=app, kind=kind)
    select(dialog, ['x', 'y'] if kind == 'marginal' else ['x'])
    if kind == 'marginal':
        dialog.bins.set('0')
    elif kind == 'stem':
        dialog.exponent.set('bad')
    else:
        dialog.df = sample.iloc[:1]
    errors = []
    dialog.error = errors.append
    monkeypatch.setattr(dialog, 'showPlotViewer', lambda: pytest.fail('无效输入替换了图形'))
    dialog.apply()
    assert errors
    dialog.quit()


@pytest.mark.parametrize('kind', list(TITLES))
def test_source_switch_invalid_and_deleted_sheet(app, sample, kind, monkeypatch):
    source = app.table
    name = app.getCurrentSheet()
    source.model.df = sample
    before = sample.copy(deep=True)
    dialog = StatPlotDialog(source, df=sample, app=app, kind=kind)
    cols = {'bubble': ['x', 'y', 'size'], 'marginal': ['x', 'y']}.get(kind, ['x'])
    select(dialog, cols)
    other = app.addSheet('另一工作表', dataframe=pd.DataFrame({'x': [999.]}))
    dialog.apply()
    if kind == 'stem':
        viewer = source.tOut
        assert 'N = 4' in viewer.T.get('1.0', 'end')
        assert getattr(other, 'tOut', None) is None
        dialog.exponent.set('无效')
    else:
        viewer = source.pf
        assert viewer is not None and getattr(other, 'pf', None) is None
        dialog.yref.set('无效')
    errors = []
    dialog.error = errors.append
    dialog.apply()
    assert errors
    assert (source.tOut if kind == 'stem' else source.pf) is viewer
    pd.testing.assert_frame_equal(sample, before)
    app.nb.select(app.sheetframes[name])
    app._sheet_changed()
    monkeypatch.setattr('worksheets.messagebox.askyesno', lambda *a, **k: True)
    assert app.deleteSheet()
    notices = []
    monkeypatch.setattr('stat_plot_dialog.messagebox.showerror', lambda *a, **k: notices.append(a))
    dialog.apply()
    assert '来源工作表已关闭' in notices[0][1]
    dialog.quit()


@pytest.mark.parametrize('kind', list(TITLES))
def test_empty_and_text_are_chinese_errors(app, kind):
    for values in ([np.nan, np.inf], ['错误', 1]):
        frame = pd.DataFrame({'x': values, 'y': [1., 2.], 'size': [1., 2.]})
        dialog = StatPlotDialog(app.table, df=frame, app=app, kind=kind)
        select(dialog, {'bubble': ['x', 'y', 'size'], 'marginal': ['x', 'y']}.get(kind, ['x']))
        errors = []
        dialog.error = errors.append
        dialog.apply()
        assert errors and '输入无效' in errors[0]
        dialog.quit()


@pytest.mark.parametrize('size', [[-1., 2.], [0., 0.]])
def test_bubble_invalid_sizes(app, size):
    dialog = StatPlotDialog(app.table, df=pd.DataFrame({'x': [1., 2.], 'y': [3., 4.], 's': size}), app=app, kind='bubble')
    select(dialog, ['x', 'y', 's'])
    errors = []
    dialog.error = errors.append
    dialog.apply()
    assert '面积必须非负' in errors[0]
    dialog.quit()


def test_grouped_columnwise_missing_and_confidence(app):
    data = pd.DataFrame({'x': [1., 3., np.nan, 10., 14., np.inf],
                         'y': [2., np.nan, 8., 20., 22., 24.],
                         'group': ['a', 'a', 'a', 'b', 'b', None]})
    dialog = StatPlotDialog(app.table, df=data, app=app, kind='interval')
    select(dialog, ['x', 'y'])
    dialog.group.set('group')
    dialog.confidence.set('90')
    _, groups, _ = dialog.prepare()
    assert [(k, v.tolist()) for k, v in groups] == [('x / a', [1., 3.]), ('x / b', [10., 14.]),
                                                               ('y / a', [2., 8.]), ('y / b', [20., 22.])]
    dialog.apply()
    # df=1 的 t(.95)=tan(.45*pi)；第一组 s/sqrt(n)=1。
    line = next(l for l in app.table.pf.ax.lines if len(l.get_ydata()) > len(groups))
    assert np.nanmin(line.get_ydata()) == pytest.approx(2 - np.tan(.45 * np.pi))
    app.table.pf.close()
    for value in ('0', '100', 'nan', '错误'):
        dialog.confidence.set(value)
        errors = []
        dialog.error = errors.append
        dialog.apply()
        assert errors
    dialog.quit()


@pytest.mark.parametrize('kind', ['ecdf', 'individual', 'probability', 'marginal', 'stem'])
def test_constants_and_small_samples(app, kind):
    data = pd.DataFrame({'x': [2., 2.], 'y': [3., 3.]})
    dialog = StatPlotDialog(app.table, df=data, app=app, kind=kind)
    select(dialog, ['x', 'y'] if kind == 'marginal' else ['x'])
    errors = []
    dialog.error = errors.append
    dialog.apply()
    assert not errors
    if kind != 'stem':
        app.table.pf.close()
    if kind != 'probability':
        dialog.df = data.iloc[:1]
        dialog.apply()
        assert not errors
        if kind != 'stem':
            app.table.pf.close()
    dialog.quit()


@pytest.mark.parametrize('kind', list(TITLES))
def test_help_route(kind, monkeypatch):
    dialog = StatPlotDialog.__new__(StatPlotDialog)
    dialog.kind, dialog.main = kind, object()
    opened = []
    monkeypatch.setattr('help_link.open_help', lambda key, parent: opened.append(key))
    assert dialog.help() == 'break'
    assert opened == ['plots.' + kind]


@pytest.mark.parametrize('kind', ['bubble', 'ecdf', 'individual', 'marginal', 'interval', 'probability'])
def test_extreme_range_rejected_before_viewer(app, kind, monkeypatch):
    dialog = StatPlotDialog(app.table, df=pd.DataFrame({'x': [-1e308, 1e308], 'y': [1., 2.], 'size': [1., 2.]}), app=app, kind=kind)
    select(dialog, {'bubble': ['x', 'y', 'size'], 'marginal': ['x', 'y']}.get(kind, ['x']))
    errors = []
    dialog.error = errors.append
    monkeypatch.setattr(dialog, 'showPlotViewer', lambda: pytest.fail('极端输入替换了图形'))
    with np.errstate(all='ignore'):
        dialog.apply()
    assert errors
    dialog.quit()


def test_missing_group_column_and_ambiguous_names(app):
    data = pd.DataFrame({'x': [1., 2.], 'y': [np.nan, np.nan], 'g': [1, '1']})
    dialog = StatPlotDialog(app.table, df=data, app=app, kind='ecdf')
    dialog.group.set('g')
    select(dialog, ['y'])
    with pytest.raises(ValueError, match='每个数值列'):
        dialog.prepare()
    select(dialog, ['x'])
    with pytest.raises(ValueError, match='显示名称重复'):
        dialog.prepare()
    dialog.quit()


@pytest.mark.parametrize('value,exponent,row', [
    (9007199254740993, '0', '900719925474099 | 3'),
    ('0.99999999999999999', '-2', '9 | 9')])
def test_stem_does_not_round_through_binary_float(app, value, exponent, row):
    from stat_plot_dialog import stem_leaf
    dialog = StatPlotDialog(app.table, df=pd.DataFrame({'x': [value]}), app=app, kind='stem')
    select(dialog, ['x'])
    _, data, _ = dialog.prepare()
    assert row in stem_leaf(data[0][1], exponent)
    dialog.quit()
