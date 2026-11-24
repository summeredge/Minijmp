from math import comb, erf, exp, factorial, log, sqrt

import pandas as pd
import pytest

from proportion_test import poisson_rate


@pytest.mark.parametrize('x', [0, 1, 5])
@pytest.mark.parametrize('direction', ['less', 'greater', 'two-sided'])
def test_poisson_tail_and_rate_limits(x, direction):
    result = poisson_rate([x], [2.5], null=1.2, alternative=direction)
    mass = lambda k: exp(-3)*3**k/factorial(k)
    low = sum(mass(k) for k in range(x+1))
    high = 1-sum(mass(k) for k in range(x))
    assert result['pvalue'] == pytest.approx(
        {'less': low, 'greater': high, 'two-sided': min(1, 2*min(low, high))}[direction])
    assert result['rates'] == (x/2.5,)
    if x == 0 and direction != 'greater':
        assert result['interval'][1] == pytest.approx(-log(.025 if direction == 'two-sided' else .05)/2.5)


@pytest.mark.parametrize('x,y', [(0,0), (0,2), (1,0), (2,3), (2,4), (5,3)])
@pytest.mark.parametrize('direction', ['less', 'greater', 'two-sided'])
def test_conditional_binomial_enumeration(x, y, direction):
    result = poisson_rate([x,y], [1,2], alternative=direction)
    n = x+y
    mass = [comb(n,k)*2**(n-k)/3**n for k in range(n+1)]
    low, high = sum(mass[:x+1]), sum(mass[x:])
    assert result['pvalue'] == pytest.approx(
        {'less': low, 'greater': high, 'two-sided': min(1, 2*min(low, high))}[direction])
    assert result['difference'] == x-y/2
    assert result['ratio'] == (2*x/y if y else float('inf') if x else None)
    for limit, upper in zip(result['interval'], (False, True)):
        if limit == 0 or limit == float('inf'):
            continue
        p = limit/(limit+2)
        support = range(x+1) if upper else range(x,n+1)
        assert sum(comb(n,k)*p**k*(1-p)**(n-k) for k in support) == pytest.approx(
            .025 if direction == 'two-sided' else .05)


def test_normal_and_invalid_counts():
    one = poisson_rate([30],[10],null=2,method='normal')
    assert one['statistic'] == pytest.approx(10/sqrt(20))
    assert one['interval'] == pytest.approx((3-1.95996398454*sqrt(30)/10, 3+1.95996398454*sqrt(30)/10))
    two = poisson_rate([30,30],[10,20],method='normal',alternative='greater')
    assert two['pvalue'] == pytest.approx((1-erf(log(2)/sqrt(2/15)))/2)
    assert two['difference_ci'][0] == pytest.approx(1.5-1.64485362695*sqrt(.375))
    for counts, exposures in [([0],[10]), ([1.5],[1]), ([20],[0]), ([20,20],[1,40])]:
        with pytest.raises(ValueError):
            poisson_rate(counts, exposures, method='normal')


def test_poisson_rate_menu_report(tk_root, monkeypatch):
    from MiniJMP import Minijmp
    from sample_test_dialog import PoissonRateDialog
    from test_capability_dialog import dispose
    from test_menu_localization import read_menu

    monkeypatch.setattr(Minijmp, 'start_logging', lambda self: None)
    app = Minijmp(parent=tk_root)
    original = PoissonRateDialog.__init__
    opened = []
    output = []

    def capture(self, *args, **kwargs):
        original(self, *args, **kwargs)
        opened.append(self)

    monkeypatch.setattr(PoissonRateDialog, '__init__', capture)
    monkeypatch.setattr(app, 'print', lambda text, **kw: output.append((text, kw['table'])))
    try:
        source = app.addSheet('泊松率来源', pd.DataFrame({'值': [1]}))
        menu = app.stats_menu['var']
        for label, groups in [('单样本泊松率检验',1), ('双样本泊松率检验',2)]:
            menu.invoke(next(i for i, kind, text in read_menu(menu) if text.strip() == label))
            dialog = opened[-1]
            assert dialog.df is source.model.df
            dialog.ok()
            assert '请检查输入' in output[-1][0]
            assert dialog.main.winfo_exists()
            for i in range(groups):
                dialog.counts[i].set('30')
                dialog.exposures[i].set(str(10+10*i))
            dialog.unit.set('小时')
            dialog.ok()
            assert '3 事件/小时' in output[-1][0]
            assert output[-1][1] is source
            assert 'p =' in output[-1][0]
            if groups == 2:
                assert '率比：2' in output[-1][0]
    finally:
        dispose(app)

