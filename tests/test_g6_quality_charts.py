"""G6 quality charts: presentation, unchanged plot data and reused GUI paths."""
from types import SimpleNamespace
from unittest.mock import Mock

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest
from PIL import Image

import control_chart as cc
import cpk_plot as capability
import ctrlchart_dialog as controls
import grr_plot as grr
import qc_dialog as quality


def var(value):
    return SimpleNamespace(get=lambda: value)


@pytest.fixture(autouse=True)
def figures(monkeypatch):
    monkeypatch.setattr(plt, 'show', Mock())
    yield
    plt.close('all')


@pytest.mark.parametrize('values,x,y', [
    (3., [0, 1], [3., 3.]),
    ([3., 3., 3.], [0, 1], [3., 3.]),
    ([2., 4., 3.], [0, .5, .5, 1.5, 1.5, 2], [2., 2., 4., 4., 3., 3.]),
])
def test_limit_line_keeps_scalar_and_variable_coordinates(values, x, y):
    fig, ax = plt.subplots()
    assert cc.limit_line(ax, values, color='red', linestyle='--', label='UCL') is None
    line, = ax.lines
    np.testing.assert_array_equal(line.get_xdata(), x)
    np.testing.assert_array_equal(line.get_ydata(), y)
    assert line.get_label() == 'UCL'
    assert ax.texts[0].get_text() == f'UCL = {y[-1]:.2f}'
    fig.canvas.draw()
    before = ax.texts[0].get_transform().transform(ax.texts[0].get_position())
    ax.set_xlim(-20, 100)
    fig.canvas.draw()
    after = ax.texts[0].get_transform().transform(ax.texts[0].get_position())
    np.testing.assert_array_equal(before, after)


@pytest.mark.parametrize('kind,options', [
    ('x_mR', {}), ('x_mR', {'one_chart': True}),
    ('x_mR', {'chart_two_only': True}),
    ('XBAR_R', {}), ('XBAR_S', {}),
    ('XBAR_R', {'pooled': True}), ('XBAR_S', {'sigma': 1.5}),
])
@pytest.mark.parametrize('gui', [False, True])
def test_control_chart_direct_and_gui_preserve_limits_and_observations(kind, options, gui):
    data = [1., 3., 2., 5.] if kind == 'x_mR' else [[1., 3.], [2., 4., 5.], [3., 6.]]
    single = options.get('one_chart') or options.get('chart_two_only')
    fig = plt.figure()
    axes = [fig.subplots()] if single else list(fig.subplots(2))
    kw = dict(options, plot_type=kind, fig=fig,
              ax=axes[0] if single else None, axs=None if single else axes,
              all_SD_lines=False, xLabels=['a', 'b', 'c', 'd'][:len(data)])
    if gui:
        dialog = SimpleNamespace(
            get_data=lambda: (data, kw['xLabels'], fig, kw['ax'], kw['axs']),
            plot_type=kind, one_chart=bool(options.get('one_chart')),
            chart_two_only=bool(options.get('chart_two_only')),
            mean=var(''), sigma=var(options.get('sigma', '')), mr_range=var(2),
            pooled=var(options.get('pooled', False)), all_lines=var(False),
            xlabel=var('批次'), xvar=var('测量'), y1label=var(''), y2label=var(''),
            max_x_labels=var(25), y1ref=var(''), y2ref=var(''),
            error=Mock(), app=SimpleNamespace(print=Mock()))
        assert controls.IMRDialog.apply(dialog) is None
        dialog.error.assert_not_called()
    else:
        result = cc.x_plot(data, **kw)
    calculate = cc.x_mR if kind == 'x_mR' else cc.xBar_R if kind == 'XBAR_R' else cc.xBar_S
    expected = calculate(data, 2) if kind == 'x_mR' else calculate(
        data, pooled=options.get('pooled', False), sigma=options.get('sigma'))
    if not gui:
        assert result == {name: expected[name] for name in result}
    indexes = [2] if options.get('chart_two_only') else [1] if single else [1, 2]
    for ax, index in zip(axes, indexes):
        np.testing.assert_array_equal(ax.lines[0].get_xdata(), expected['X'])
        np.testing.assert_array_equal(ax.lines[0].get_ydata(), expected[f'Y{index}'])
        assert [line.get_label() for line in ax.lines[1:]] == ['CL', 'UCL', 'LCL']
        assert [line.get_linestyle() for line in ax.lines[1:]] == ['-', '--', '--']
        for line, name, key in zip(ax.lines[1:], ['CL', 'UCL', 'LCL'], ['bar', 'ucl', 'lcl']):
            values = expected[f'{key}{index}']
            if isinstance(values, list) and len(set(values)) != 1:
                np.testing.assert_array_equal(line.get_ydata(), np.repeat(values, 2))
            else:
                value = values[0] if isinstance(values, list) else values
                np.testing.assert_array_equal(line.get_ydata(), [value, value])
            assert any(text.get_text().startswith(name + ' = ') for text in ax.texts)
    if len(axes) == 2:
        assert not axes[0].get_xticklabels()


def test_auxiliary_lines_keep_values_and_differ_from_control_limits():
    fig, ax = plt.subplots()
    cc.x_plot([1., 3., 2., 5.], ax=ax, one_chart=True)
    assert all(line.get_linestyle() == ':' for line in ax.lines[4:])
    cl = ax.lines[1].get_ydata()[0]
    ucl = ax.lines[2].get_ydata()[0]
    lcl = ax.lines[3].get_ydata()[0]
    np.testing.assert_array_equal([line.get_ydata()[0] for line in ax.lines[4:]],
                                 [cl + (ucl-cl)/3*2, cl + (ucl-cl)/3,
                                  cl + (lcl-cl)/3*2, cl + (lcl-cl)/3])


def test_mr_zero_lower_limit_has_no_duplicate_auxiliary_annotation():
    fig, ax = plt.subplots()
    data = [1., 3., 2., 5.]
    expected = cc.x_mR(data, 2)
    result = cc.x_plot(data, ax=ax, chart_two_only=True, all_SD_lines=True)
    assert result == {key: expected[key] for key in result}
    assert result['lcl2'] == 0
    np.testing.assert_array_equal(ax.lines[0].get_xdata(), expected['X'])
    np.testing.assert_array_equal(ax.lines[0].get_ydata(), expected['Y2'])
    center, upper = result['bar2'], result['ucl2']
    values = [center, upper, 0, center + (upper-center)/3*2,
              center + (upper-center)/3, max(0, center-(upper-center)/3*2),
              max(0, center-(upper-center)/3)]
    assert len(ax.lines) == 8
    assert values.count(0) > 1
    for line, value in zip(ax.lines[1:], values):
        np.testing.assert_array_equal(line.get_xdata(), [0, 1])
        np.testing.assert_array_equal(line.get_ydata(), [value, value])
    assert [text.get_text() for text in ax.texts] == [
        f'CL = {center:.2f}', f'UCL = {upper:.2f}', 'LCL = 0.00']
    assert [text for text in ax.texts if text.xy[1] == 0] == [ax.texts[-1]]


@pytest.mark.parametrize('kind', ['P', 'NP', 'C', 'U'])
@pytest.mark.parametrize('overrides', [False, True])
def test_attribute_charts_preserve_step_coordinates_and_have_named_limits(kind, overrides):
    fig, ax = plt.subplots()
    n = 100 if kind == 'NP' else 1 if kind == 'C' else [100, 200, 80]
    data = [.02, .04, .03] if kind in ('P', 'NP') else [3., 4., 5.]
    options = dict(fig=fig, ax=ax, n=n)
    if overrides:
        options.update(bar1=.2, ucl1=.4, lcl1=0)
    if kind in ('P', 'NP'):
        assert cc.p_np_plot(p=data, NP=kind == 'NP', **options) is None
        ns = [n] * len(data) if np.isscalar(n) else n
        center = sum(p*size for p, size in zip(data, ns)) / sum(ns)
        upper = [center + 3*(center*(1-center)/size)**.5 for size in ns]
        lower = [max(0, center - 3*(center*(1-center)/size)**.5) for size in ns]
        scale = ns[0] if kind == 'NP' else 1
        expected = np.array(data)*scale
        center *= scale
        upper, lower = np.array(upper)*scale, np.array(lower)*scale
    else:
        assert cc.cu_plot(c=data, C=kind == 'C', **options) is None
        ns = [n] * len(data) if np.isscalar(n) else n
        center = sum(data) / sum(ns)
        upper = [center + 3*(center/size)**.5 for size in ns]
        lower = [max(0, center - 3*(center/size)**.5) for size in ns]
        expected = [count/size for count, size in zip(data, ns)]
    np.testing.assert_array_equal(ax.lines[0].get_ydata(), expected)
    assert [text.get_text() for text in ax.get_legend().get_texts()] == ['CL', 'UCL', 'LCL']
    np.testing.assert_array_equal(ax.lines[1].get_ydata(), [.2, .2] if overrides else [center, center])
    for line, values, override in zip(ax.lines[2:], [upper, lower], [.4, 0]):
        assert line.get_linestyle() == '--'
        np.testing.assert_array_equal(line.get_ydata(), [override, override] if overrides else np.repeat(values, 2))
        np.testing.assert_array_equal(line.get_xdata(), [0, 1] if overrides else [-.5, .5, .5, 1.5, 1.5, 2.5])
    fig.canvas.draw()
    assert ax.get_legend().get_window_extent().x0 > ax.get_window_extent().x1


@pytest.mark.parametrize('dialog_type,kind,n', [
    (controls.NPDialog, 'NP', 100), (controls.PDialog, 'P', [100, 200, 80]),
    (controls.CDialog, 'C', 1), (controls.UDialog, 'U', [100, 200, 80]),
])
def test_attribute_dialog_reuses_actual_plot(dialog_type, kind, n):
    fig, ax = plt.subplots()
    data = [.02, .04, .03] if kind in ('P', 'NP') else [3., 4., 5.]
    dialog = SimpleNamespace(get_data=lambda: (data, ['a', 'b', 'c'], fig, ax, n),
        plot_type=kind, y1label=var(''), xvar=var('缺陷'), xlabel=var(''),
        xlabelID=var('批次'), max_x_labels=var(25), y1ref=var(''),
        app=SimpleNamespace(print=Mock()))
    assert dialog_type.apply(dialog) is None
    assert ax.get_xlabel() == '批次'
    assert [line.get_label() for line in ax.lines[1:]] == ['CL', 'UCL', 'LCL']


@pytest.mark.parametrize('within,legend,spec', [
    (True, True, True), (False, True, True), (True, False, False),
])
def test_capability_curves_specifications_and_visibility(within, legend, spec):
    fig, ax = plt.subplots()
    data = [1., 3., 2., 5.]
    result = capability.cpk_plot(data, usl=8, target=4, lsl=0, ax=ax,
        show_within=within, show_legend=legend, show_spec=spec)
    expected = capability.cpk(data, target=4, usl=8, lsl=0, print_out=False, within=within)
    assert result == expected
    assert len(fig.axes) == 2
    assert ax.get_ylabel() == 'Density' and fig.axes[1].get_ylabel() == 'Counts'
    assert [line.get_label() for line in ax.lines[:1+within]] == ['Overall', 'Within'][:1+within]
    assert (ax.get_legend() is not None) == legend
    if legend:
        assert [text.get_text() for text in ax.get_legend().get_texts()] == ['Overall', 'Within'][:1+within]
    if spec:
        assert [text.get_text() for text in ax.texts] == ['Target', 'USL', 'LSL']
        for line, value, style in zip(ax.lines[1+within:], [4, 8, 0], [':', '-.', '-.']):
            np.testing.assert_array_equal(line.get_xdata(), [value, value])
            assert line.get_linestyle() == style
    else:
        assert not ax.texts


@pytest.mark.parametrize('grouped', [False, True])
def test_capability_dialog_uses_same_specification_plot(grouped):
    fig = plt.figure()
    dialog = SimpleNamespace(df=pd.DataFrame({'测量': [1., 3., 2., 5.]}),
        xvar=var('测量'), lsl=var(0.), target=var(4.), usl=var(8.), alpha=var(.05),
        xlabel=var(''), show_legend=var(True), show_within=var(True), show_spec=var(True),
        app=SimpleNamespace(showPlotViewer=lambda: SimpleNamespace(fig=fig), print=Mock()),
        error=Mock(), mvar=var('Size'), subsize=var(2), subm=var('Unbiased Std Dev'))
    assert (quality.CpkSubDialog if grouped else quality.CpkDialog).apply(dialog) is None
    dialog.error.assert_not_called()
    chart = fig.axes[0]
    assert chart.get_xlabel() == '测量'
    assert [text.get_text() for text in chart.texts] == ['Target', 'USL', 'LSL']
    for line, value in zip(chart.lines[-3:], [4, 8, 0]):
        np.testing.assert_array_equal(line.get_xdata(), [value, value])


@pytest.mark.parametrize('operators', [False, True])
def test_grr_keeps_measurements_part_order_and_readable_labels(operators):
    fig, ax = plt.subplots()
    parts = ['Long component A', 'Long component B', 'Long component B', 'Long component A']
    values = [10., 20., 21., 11.]
    assert grr.grr_plot(y=values, part=parts, op=['one', 'one', 'two', 'two'] if operators else None,
                        ax=ax, ylabel='测量值') is None
    axes = ax.child_axes if operators else [ax]
    assert axes[0].get_ylabel() == '测量值'
    drawn = []
    for child in axes:
        assert [text.get_text() for text in child.get_xticklabels()] == parts[:2]
        assert all(text.get_rotation() == 60 and text.get_ha() == 'right' for text in child.get_xticklabels())
        drawn.extend(float(point[1]) for collection in child.collections for point in collection.get_offsets())
    assert sorted(drawn) == sorted(values)
    if operators:
        assert [child.get_ylim() for child in axes] == [(8.9, 22.1), (8.9, 22.1)]
        fig.canvas.draw()
        assert axes[0].get_window_extent().x1 < axes[1].get_window_extent().x0


@pytest.mark.parametrize('operators', [False, True])
def test_grr_dialog_passes_measurement_label_and_operator_facets(operators, monkeypatch):
    monkeypatch.setattr(quality, 'grr_master', Mock())
    fig = plt.figure()
    dialog = SimpleNamespace(df=pd.DataFrame({'测量': [10., 20., 21., 11.],
        '部件': ['a', 'b', 'b', 'a'], '操作员': ['one', 'one', 'two', 'two']}),
        xvar=var('测量'), yvar=var('部件'), ovar=var('操作员' if operators else ''),
        alpha=var(.05), hist_std=var(''), spec_gap=var(''), mvar=var('ANOVA'),
        inter=var(True), ylabel=var(''),
        app=SimpleNamespace(showPlotViewer=lambda: SimpleNamespace(fig=fig), print=Mock()))
    assert quality.GRRDialog.apply(dialog) is None
    ax = fig.axes[0]
    assert (ax.child_axes[0] if operators else ax).get_ylabel() == '测量'
    assert len(ax.child_axes) == (2 if operators else 0)


@pytest.mark.parametrize('kind', ['I', 'IMR', 'P', 'NP', 'C', 'U', 'CPK', 'HIST', 'GRR'])
def test_standalone_charts_use_constrained_layout_without_extra_figures(kind):
    before = set(plt.get_fignums())
    if kind in ('I', 'IMR'):
        cc.x_plot([1., 3., 2., 5.], one_chart=kind == 'I', all_SD_lines=False)
    elif kind in ('P', 'NP'):
        cc.p_np_plot(p=[.02, .04, .03], n=100, NP=kind == 'NP')
    elif kind in ('C', 'U'):
        cc.cu_plot(c=[3., 4., 5.], n=1 if kind == 'C' else [2, 4, 3], C=kind == 'C')
    elif kind == 'CPK':
        capability.cpk_plot([1., 3., 2., 5.], usl=8, target=4, lsl=0)
    elif kind == 'HIST':
        capability.hist_norm([1., 3., 2., 5.])
    else:
        grr.grr_plot(y=[10., 20., 21., 11.], part=['a', 'b', 'b', 'a'],
                     op=['one', 'one', 'two', 'two'])
    created = set(plt.get_fignums()) - before
    assert len(created) == 1
    fig = plt.figure(created.pop())
    assert isinstance(fig.get_layout_engine(), matplotlib.layout_engine.ConstrainedLayoutEngine)
    if kind in ('P', 'NP', 'C', 'U'):
        np.testing.assert_array_equal(fig.get_size_inches(), [15., 15.])
    fig.canvas.draw()


@pytest.mark.parametrize('kind', ['I', 'IMR', 'CPK', 'HIST'])
def test_png_exports_keep_existing_contract_and_include_outside_annotations(kind, tmp_path, monkeypatch):
    fig = plt.figure(figsize=(6.4, 4.8))
    axes = list(fig.subplots(2)) if kind == 'IMR' else [fig.subplots()]
    saved = Mock(wraps=fig.savefig)
    monkeypatch.setattr(fig, 'savefig', saved)
    name = str(tmp_path / '质量图表')
    if kind in ('I', 'IMR'):
        cc.x_plot([1., 3., 2., 5.], ax=axes[0] if kind == 'I' else None,
                  fig=fig, axs=axes if kind == 'IMR' else None,
                  one_chart=kind == 'I', all_SD_lines=False, filename=name)
    elif kind == 'CPK':
        capability.cpk_plot([1., 3., 2., 5.], usl=8, target=4, lsl=0,
                            ax=axes[0], filename=name, transparent=True)
    else:
        assert capability.hist_norm([1., 3., 2., 5.], ax=axes[0], filename=name) is None
    saved.assert_called_once()
    assert saved.call_args.args == (name + '.png',)
    assert saved.call_args.kwargs['dpi'] == 200
    assert saved.call_args.kwargs['format'] == 'png'
    assert saved.call_args.kwargs['bbox_inches'] == 'tight'
    if kind == 'CPK':
        assert saved.call_args.kwargs['transparent'] is True
    with Image.open(name + '.png') as image:
        assert image.format == 'PNG' and image.width > 800 and image.height > 600
        assert image.info['dpi'] == pytest.approx((200, 200), abs=.01)
        if kind == 'CPK':
            assert image.getpixel((0, 0))[3] == 0
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    tight = fig.get_tightbbox(renderer).transformed(fig.dpi_scale_trans)
    for ax in axes:
        for text in ax.texts:
            box = text.get_window_extent(renderer)
            assert tight.x0 <= box.x0 and tight.x1 >= box.x1
            assert tight.y0 <= box.y0 and tight.y1 >= box.y1
