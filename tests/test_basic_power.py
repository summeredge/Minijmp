from math import erf, sqrt

import numpy as np
import pandas as pd
import pytest
from scipy import stats
from statsmodels.stats.power import TTestPower, TTestIndPower, FTestAnovaPower

from basic_power import basic_power
from utilities import normality_option


@pytest.mark.parametrize('direction, sm_direction', [('greater','larger'),('less','smaller'),('two-sided','two-sided')])
@pytest.mark.parametrize('method, api', [('t1',TTestPower),('t2',TTestIndPower)])
def test_power_t_reference_and_minimum(method,api,direction,sm_direction):
    effect = -.4 if direction == 'less' else .4
    result = basic_power(method,target=.8,effect=effect,alternative=direction)
    n = result['n']
    assert api().power(effect,n,.05,alternative=sm_direction) == pytest.approx(result['power'])
    assert api().power(effect,n-1,.05,alternative=sm_direction) < .8 <= result['power']
    solved = basic_power(method,n=n,target=result['power'],alternative=direction)
    assert solved['effect'] == pytest.approx(effect)


@pytest.mark.parametrize('method, multiplier', [('z1',1),('z2',2)])
def test_power_z_closed_form(method,multiplier):
    result = basic_power(method,n=30,effect=.4,sigma=2,alternative='greater')
    assert result['power'] == pytest.approx((1+erf((.2*sqrt(30/multiplier)-1.64485362695)/sqrt(2)))/2)


@pytest.mark.parametrize('method', ['p1','p2'])
def test_proportion_against_raw_difference_probability(method):
    p0,p1 = .2,.35
    n = 80
    pc = (p0+p1)/2
    standard_null = sqrt((p0*(1-p0) if method == 'p1' else 2*pc*(1-pc))/n)
    standard_alt = sqrt((p1*(1-p1)+(p0*(1-p0) if method == 'p2' else 0))/n)
    cutoff = 1.95996398454*standard_null
    ref = stats.norm.cdf(-cutoff,p1-p0,standard_alt)+stats.norm.sf(cutoff,p1-p0,standard_alt)
    assert basic_power(method,n=n,p0=p0,p1=p1)['power'] == pytest.approx(ref)
    m = basic_power(method,target=.8,p0=p0,p1=p1)['n']
    assert basic_power(method,n=m-1,p0=p0,p1=p1)['power'] < .8
    assert basic_power(method,n=m,p0=p0,p1=p1)['power'] >= .8


def test_anova_and_boundaries():
    assert basic_power('anova',n=24,effect=.25,groups=4)['power'] == pytest.approx(
        FTestAnovaPower().power(.25,96,.05,k_groups=4))
    assert basic_power('anova',n=2,effect=0,groups=4)['power'] == .05
    assert basic_power('p1',n=1,p0=.5,p1=.5)['power'] == .05
    for kw in (dict(n=1,effect=.5),dict(n=10,target=1),dict(target=.8,effect=0),
               dict(target=.8,effect=.4,alternative='less')):
        with pytest.raises(ValueError):
            basic_power('t2',**kw)


def test_normality_options():
    x = np.array([1,2,2,3,4,6,12,24])
    n = len(x)
    normal_cdf = stats.norm.cdf(x,loc=x.mean(),scale=x.std(ddof=1))
    reference = max(max(i/n-p,p-(i-1)/n) for i,p in enumerate(normal_cdf,1))
    ks, p, _ = normality_option(x,'KS')
    assert ks == pytest.approx(reference)
    assert p < stats.kstest(x, 'norm',args=(x.mean(),x.std(ddof=1))).pvalue
    scores = stats.norm.ppf([(i-.375)/(n+.25) for i in range(1,n+1)])
    r,p,_ = normality_option(x,'Ryan–Joiner')
    assert r == pytest.approx(stats.pearsonr(x,scores).statistic)
    assert 0 < p < .05
    assert normality_option(7*x+2,'Ryan–Joiner')[:2] == pytest.approx((r,p))
    with pytest.raises(ValueError):
        normality_option([1,1,1,1],'KS')


def test_s2_menu_power_report_and_plot(tk_root,monkeypatch,tmp_path):
    from MiniJMP import Minijmp
    from sample_test_dialog import BasicPowerDialog
    from stat_table import StatTable
    from test_menu_localization import read_menu
    from test_regression_dialog import dispose

    monkeypatch.setattr(Minijmp,'start_logging',lambda self:None)
    app=Minijmp(parent=tk_root)
    source=app.addSheet('功效来源',pd.DataFrame({'x':[1,2]}))
    reports, opened = [], []
    original = BasicPowerDialog.__init__

    def capture(self,*args,**kwargs):
        original(self,*args,**kwargs)
        opened.append(self)

    monkeypatch.setattr(BasicPowerDialog,'__init__',capture)
    monkeypatch.setattr(app,'print',lambda value,**kw: reports.append((value,kw['table'])))
    try:
        menu=app.stats_menu['var']
        menu.invoke(next(i for i,_,label in read_menu(menu) if label.strip()=='基础功效与样本量'))
        dialog=opened[-1]
        dialog.fields['target'].set('.8')
        dialog.fields['effect'].set('.4')
        dialog.ok()
        assert isinstance(reports[0][0],StatTable)
        assert all(table is source for _,table in reports)
        output=tmp_path/'power.png'
        source.pf.savePlot(str(output))
        assert output.stat().st_size>1000
    finally:
        dispose(app)

def test_graphical_multiple_comparisons_equal_sizes():
    from chi_sq import equal_variances_mc
    groups = [[5,7,8,9,10,12,14,15],[7,8,9,11,13,14,16,17],[4,6,7,8,10,11,13,14]]
    p, bounds = equal_variances_mc(groups)
    assert p == pytest.approx(.965541768,abs=1e-8)
    assert round(p,3) == .966  # Minitab 19 VARTEST fixed case.
    assert (bounds[:,0] < np.std(groups,axis=1,ddof=1)).all()
    assert (bounds[:,1] > np.std(groups,axis=1,ddof=1)).all()
    assert bounds[:,0].max() < bounds[:,1].min()
    # A deliberately separated group must have an interval disjoint from the other two.
    shifted = [groups[0],groups[1],np.array(groups[2])*20]
    p, bounds = equal_variances_mc(shifted)
    assert p < .05
    assert bounds[2,0] > bounds[:2,1].max()
    with pytest.raises(ValueError,match='样本量相同'):
        equal_variances_mc([*groups[:2],groups[2][1:]])
