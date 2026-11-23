from math import exp, factorial, log, sqrt

from matplotlib.figure import Figure
import pandas as pd
import pytest

from capability import analyze_poisson_capability
from capability_plots import plot_poisson_capability
from test_capability_dialog import dispose


@pytest.mark.parametrize('sizes, total, dpu, cumulative', [
    (2.5, 10, [0.4, 1.6, 0.8, 0], [0.4, 1, 7 / 7.5, 0.7]),
    ([2.5, 1, 4, 10], 17.5, [0.4, 4, 0.5, 0], [0.4, 5 / 3.5, 7 / 7.5, 0.4]),
])
def test_poisson_reference(sizes, total, dpu, cumulative):
    summary, groups = analyze_poisson_capability([1, 4, 2, 0], sizes, .90, target=.3)
    stats = summary.set_index('指标')['估计值']
    assert stats.to_dict() == pytest.approx({
        'Mean DPU': 7 / total, '子组数': 4, '总缺陷数': 7, '总检验单位数': total,
        '最小 DPU': min(dpu), '最大 DPU': max(dpu),
        '目标 DPU': .3, 'Mean DPU − 目标': 7 / total - .3,
    })
    assert groups['缺陷数'].tolist() == [1, 4, 2, 0]
    assert groups['DPU'].tolist() == pytest.approx(dpu)
    assert groups['累计 DPU'].tolist() == pytest.approx(cumulative)
    lower, upper = summary.iloc[0, 2:] * total
    # Independently check equal tails of the total count by summing Poisson masses.
    assert 1 - exp(-lower) * sum(lower**k / factorial(k) for k in range(7)) == pytest.approx(.05)
    assert exp(-upper) * sum(upper**k / factorial(k) for k in range(8)) == pytest.approx(.05)


@pytest.mark.parametrize('counts,sizes', [([0, 0], [3, 7]), ([0], 10)])
def test_zero_defects(counts, sizes):
    summary, groups = analyze_poisson_capability(counts, sizes)
    assert summary.iloc[0, 1:].tolist() == pytest.approx([0, 0, -log(.025) / 10])
    assert groups['累计 DPU'].tolist() == [0] * len(counts)
    assert not plot_poisson_capability(summary, groups, Figure())


def test_single_subgroup():
    summary, groups = analyze_poisson_capability([3], .5, target=0)
    assert groups.iloc[0].tolist() == [1, 3, .5, 6, 6]
    assert summary.iloc[-1, 1] == 6
    assert summary.iloc[0, 2] < 6 < summary.iloc[0, 3]
    assert not plot_poisson_capability(summary, groups, Figure())


@pytest.mark.parametrize('counts,sizes', [
    ([], 5), ([0, 1], [1]), ([-1], 5), ([1.5], 5), ([True], 5), ([0], 0), ([0], -1),
    ([pd.NA], 5), ([float('nan')], 5), ([float('inf')], 5), ([1], [None]),
    ([1], [float('inf')]), ([1], [float('nan')]), ([1], True), ([1], ''),
])
def test_invalid_data(counts, sizes):
    with pytest.raises(ValueError):
        analyze_poisson_capability(counts, sizes)


@pytest.mark.parametrize('confidence,target', [(0, None), (1, None), (float('nan'), None),
                                               (.95, -1), (.95, float('inf')), (.95, float('nan'))])
def test_invalid_options(confidence, target):
    with pytest.raises(ValueError):
        analyze_poisson_capability([0], 1, confidence, target)


def test_minitab_19_pcapa_fixed_reference():
    summary, _ = analyze_poisson_capability([1, 4, 2, 0], [20, 100, 30, 50], target=.04)
    assert summary.iloc[0, 1:].tolist() == pytest.approx(
        [.035, .014071815257655851, .07211337680851168], rel=1e-9)
    assert summary.iloc[4:7, 1].tolist() == pytest.approx([0, 1 / 15, .04], rel=1e-9)


@pytest.mark.parametrize('sizes', [[2, 3, 1], [2, 2, 2]])
def test_plot_values_and_diagnostics(sizes):
    summary, groups = analyze_poisson_capability([0, 0, 24], sizes)
    figure = Figure()
    assert plot_poisson_capability(summary, groups, figure)
    u, cumulative, diagnostic = figure.axes
    assert u.lines[0].get_ydata() == pytest.approx([0, 0, 24 / sizes[-1]])
    limits = {line.get_label(): line.get_ydata()[::2] for line in u.lines}
    assert limits['UCL'] == pytest.approx([4 + 6 / sqrt(n) for n in sizes])
    assert limits['LCL'] == pytest.approx([max(0, 4 - 6 / sqrt(n)) for n in sizes])
    assert cumulative.lines[0].get_ydata() == [4, 4]
    assert cumulative.lines[1].get_ydata() == pytest.approx([0, 0, 4])
    points = diagnostic.collections[0].get_offsets()
    if sizes[0] == sizes[1] == sizes[2]:
        assert diagnostic.get_title() == '泊松拟合诊断'
        assert points[0].tolist() == pytest.approx([exp(-8), 2 / 3])
    else:
        assert diagnostic.get_title() == '缺陷率与检验单位数'
        assert points[:, 0].tolist() == sizes
        assert points[:, 1].tolist() == [0, 0, 24]


def test_poisson_menu_workflow(tk_root, monkeypatch):
    from MiniJMP import Minijmp

    monkeypatch.setattr(Minijmp, 'start_logging', lambda self: None)
    app = Minijmp(parent=tk_root)
    source = app.addSheet('泊松来源', pd.DataFrame({'缺陷': [0, 0, 24], '小时 ': [2, 3, 1]}))
    try:
        menu = app.quality_menu['var']
        index = next(i for i in range(menu.index('end') + 1)
                     if menu.type(i) == 'command' and menu.entrycget(i, 'label').strip() == '泊松过程能力')
        menu.invoke(index)
        dialog = next(child for child in source.winfo_children()
                      if hasattr(child, 'title') and child.title() == '泊松过程能力')
        app.addSheet('另一表', pd.DataFrame({'无关': [1]}))
        source.model.df.iloc[2, 0] = 0
        controls, actions, status, notebook = dialog.winfo_children()
        options = [w for w in controls.winfo_children() if w.winfo_class() in ('TCombobox', 'TEntry')]
        options[0].current(0)
        options[1].current(2)
        options[4].insert(0, '3.5')
        run = actions.winfo_children()[0]
        run.invoke()
        tk_root.update()
        assert [notebook.tab(tab, 'text') for tab in notebook.tabs()] == [
            '泊松能力统计', '子组明细', '稳定性与诊断图'], status.cget('text')
        report, detail, graph = [dialog.nametowidget(tab) for tab in notebook.tabs()]
        tree = report.winfo_children()[0].tree
        assert tree.item(tree.get_children()[0], 'values')[1] == '4'
        assert tree.item(tree.get_children()[-1], 'values')[1] == '0.5'
        details = detail.winfo_children()[0].tree
        assert details.item(details.get_children()[-1], 'values') == ('3', '24', '1', '24', '4')
        assert '小时' in status.cget('text')
        assert '请先调查过程稳定性' in status.cget('text')
        notebook.select(graph)
        tk_root.update()
        canvas = next(w for w in graph.winfo_children() if w.winfo_class() == 'Canvas')
        assert canvas.winfo_ismapped() and canvas.find_all()

        options[1].current(0)
        options[2].insert(0, '0')
        run.invoke()
        assert not notebook.tabs()
        assert '第 1 行' in status.cget('text')
        options[2].delete(0, 'end')
        options[2].insert(0, '1.5')
        run.invoke()
        assert len(notebook.tabs()) == 3
    finally:
        dispose(app)
