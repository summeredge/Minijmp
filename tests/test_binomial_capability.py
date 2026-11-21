from math import comb, inf
from statistics import NormalDist

import pandas as pd
import pytest

from capability import analyze_binomial_capability
from test_capability_dialog import dispose


@pytest.mark.parametrize('sizes, totals', [(20, [20] * 4), ([20, 100, 30, 50], [20, 100, 30, 50])])
def test_binomial_reference(sizes, totals):
    summary, groups = analyze_binomial_capability([1, 4, 2, 0], sizes, confidence=.90)
    n, d = sum(totals), 7
    p = d / n
    low, high = summary.iloc[0, 2:]
    # Independently invert equal binomial tails by checking the probability sums.
    def mass(k, prob):
        return comb(n, k) * prob**k * (1 - prob)**(n - k)

    assert sum(mass(k, low) for k in range(d, n + 1)) == pytest.approx(.05)
    assert sum(mass(k, high) for k in range(d + 1)) == pytest.approx(.05)
    assert summary.iloc[:, 1].tolist() == pytest.approx(
        [p, 100 * p, 1e6 * p, NormalDist().inv_cdf(1 - p)])
    assert summary.iloc[1, 2:].tolist() == pytest.approx([100 * low, 100 * high])
    assert summary.iloc[2, 2:].tolist() == pytest.approx([1e6 * low, 1e6 * high])
    assert summary.iloc[3, 2:].tolist() == pytest.approx(
        [NormalDist().inv_cdf(1 - high), NormalDist().inv_cdf(1 - low)])
    assert groups['累计不合格率'].tolist() == pytest.approx(
        [events / sum(totals[:i]) for i, events in enumerate((1, 5, 7, 7), 1)])


@pytest.mark.parametrize('defects, rate, z', [([0, 0], 0, inf), ([10, 20], 1, -inf)])
def test_binomial_boundaries(defects, rate, z):
    summary, _ = analyze_binomial_capability(defects, [10, 20])
    edge = .025**(1 / 30)
    assert summary.iloc[0, 1:].tolist() == pytest.approx(
        [0, 0, 1 - edge] if rate == 0 else [1, edge, 1])
    values = summary.iloc[3, 1:].tolist()
    assert values[0] == z
    assert values[2 if rate == 0 else 1] == z
    assert values[1 if rate == 0 else 2] == pytest.approx(
        NormalDist().inv_cdf(edge if rate == 0 else 1 - edge))


@pytest.mark.parametrize('defects, sizes', [
    ([], 5), ([0, 1], [1]), ([1.5], 5), ([-1], 5), ([6], 5), ([0], 0),
    ([0], 2.5), ([0], [None]), ([pd.NA], 10), ([True], 1), ([1], ''), ([0], None),
])
def test_invalid_binomial_counts(defects, sizes):
    with pytest.raises(ValueError):
        analyze_binomial_capability(defects, sizes)


def test_binomial_menu_workflow(tk_root, monkeypatch):
    from MiniJMP import Minijmp

    monkeypatch.setattr(Minijmp, 'start_logging', lambda self: None)
    app = Minijmp(parent=tk_root)
    source = app.addSheet('二项来源', pd.DataFrame({'不合格': [0, 0, 9], '总数': [10, 10, 10]}))
    menu = app.quality_menu['var']
    for index in range(menu.index('end') + 1):
        if menu.type(index) == 'command' and menu.entrycget(index, 'label').strip() == '二项过程能力':
            menu.invoke(index)
            break
    else:
        pytest.fail('找不到二项过程能力菜单项')
    dialog = next(child for child in source.winfo_children()
                  if hasattr(child, 'title') and child.title() == '二项过程能力')
    try:
        app.addSheet('另一表', pd.DataFrame({'无关': [1]}))
        controls, actions, status, notebook = dialog.winfo_children()
        options = [w for w in controls.winfo_children() if w.winfo_class() in ('TCombobox', 'TEntry')]
        options[0].current(0)
        options[1].current(2)
        run = actions.winfo_children()[0]
        run.invoke()
        tk_root.update()
        assert [notebook.tab(i, 'text') for i in notebook.tabs()] == [
            '二项能力统计', '子组明细', '稳定性与累计图']
        report = dialog.nametowidget(notebook.tabs()[0]).winfo_children()[0]
        assert report.tree.item(report.tree.get_children()[0], 'values')[1] == '0.3'
        assert '规则信号' in status.cget('text')
        options[1].current(0)
        options[2].insert(0, '8')
        run.invoke()
        assert not notebook.tabs()
        assert '第 3 行' in status.cget('text')
        options[2].delete(0, 'end')
        options[2].insert(0, '10')
        run.invoke()
        assert len(notebook.tabs()) == 3
    finally:
        dialog.destroy()
        dispose(app)


def test_minitab_22_bcapa_fixed_reference():
    # 22.6.0.0 BCAPA storage results, recorded in docs/capability-validation.md.
    summary, _ = analyze_binomial_capability([1, 4, 2, 0], [20, 100, 30, 50])
    for row, expected in {
        0: [.035, .0141855258986459, .0707809983509771],
        2: [35000, 14185.5258986459, 70780.9983509771],
        3: [1.81191067274624, 1.46999910379542, 2.19211710763098],
    }.items():
        assert summary.iloc[row, 1:].tolist() == pytest.approx(expected, rel=1e-9)
