"""高级 SPC 的独立参考；不以旧控制图或被测公共 helper 作唯一依据。"""
from threading import Event
import json

import numpy as np
import pandas as pd
import pytest
from scipy import special

from advanced_spc import analyze_spc, nelson_events


def test_ewma_nist_example_and_independent_weighted_sum():
    # NIST pmc324：历史 mu=50,sigma=2.0539,lambda=.3；表中已舍入的统计量。
    x = np.array([52.,47.,53.,49.3,50.1,47.,51.,50.1,51.2,50.5,49.6,47.6,
                  49.9,51.3,47.8,51.2,52.6,52.4,53.6,52.1])
    r = analyze_spc(pd.DataFrame({'x':x}), ['x'], mean=50.,sigma=2.0539,ewma_lambda=.3)
    t = r.tables['observations']
    expected = [50*(.7**i)+sum(.3*.7**(i-j)*x[j-1] for j in range(1,i+1)) for i in range(1,len(x)+1)]
    np.testing.assert_allclose(t.statistic, expected, rtol=1e-14)
    np.testing.assert_allclose(t.statistic.iloc[:5], [50.6,49.52,50.564,50.1848,50.15936])
    variance = np.array([2.0539**2*sum((.3*.7**j)**2 for j in range(i)) for i in range(1,len(x)+1)])
    np.testing.assert_allclose(t.upper, 50+3*np.sqrt(variance))
    np.testing.assert_allclose(t.lower, 50-3*np.sqrt(variance))
    assert not t.alarm.any()
    assert r.tables['summary'].set_index('parameter').loc['phase','value'] == 'known'


@pytest.mark.parametrize('lam', [1.,.01,.2])
def test_ewma_strict_alarm_indices_and_startup(lam):
    x = np.r_[np.zeros(8),np.full(20,5.)]
    r = analyze_spc(pd.DataFrame({'x':x}),['x'],mean=0.,sigma=1.,ewma_lambda=lam)
    out=r.tables['observations']
    weights=np.array([[lam*(1-lam)**(i-j) if j<=i else 0. for j in range(len(x))] for i in range(len(x))])
    expected=weights@x
    limits=3*np.sqrt((weights**2).sum(axis=1))
    np.testing.assert_allclose(out.statistic,expected,atol=1e-14)
    np.testing.assert_allclose(out.upper,limits)
    assert out.alarm.tolist() == (np.abs(expected)>limits).tolist()
    assert r.tables['alarms'].source_row.tolist() == (np.flatnonzero(np.abs(expected)>limits)+1).tolist()
    exact=analyze_spc(pd.DataFrame({'x':[3.,-3.]}),['x'],mean=0.,sigma=1.,ewma_lambda=1.)
    assert not exact.tables['observations'].alarm.any()


def test_cusum_nist_detection_and_suffix_sum_reference():
    # NIST pmc313，个体值为原例子组均值，故其已知sigma=.635。
    x=np.array([324.925,324.675,324.725,324.350,325.350,325.225,324.125,324.525,
                325.225,324.600,324.625,325.150,328.325,327.250,327.825,328.500,
                326.675,327.775,326.875,328.350])
    r=analyze_spc(pd.DataFrame({'x':x}),['x'],kind='CUSUM',mean=325.,sigma=.635,cusum_h=6.6077)
    out=r.tables['observations']; z=(x-325)/.635
    # 独立穷举全部后缀和，而非复制递推路径。
    plus=[max([0.]+[sum(z[j:i+1]-.5) for j in range(i+1)]) for i in range(len(x))]
    minus=[-max([0.]+[sum(-z[j:i+1]-.5) for j in range(i+1)]) for i in range(len(x))]
    np.testing.assert_allclose(out.statistic,plus,atol=1e-12)
    np.testing.assert_allclose(out.negative,minus,atol=1e-12)
    assert r.tables['alarms'].source_row.tolist() == list(range(14,21))
    assert out.statistic.iloc[-1] > out.statistic.iloc[13]  # 不在报警后静默复位。


def test_cusum_negative_branch_strict_threshold_and_event_value():
    r=analyze_spc(pd.DataFrame({'x':[-1.5,-1.5,-1.5]}),['x'],kind='CUSUM',mean=0.,sigma=1.,cusum_h=2.)
    out=r.tables['observations']; alarms=r.tables['alarms']
    assert out.alarm.tolist() == [False,False,True]
    assert alarms.rule.tolist() == ['CUSUM-']
    assert alarms.statistic.tolist() == [-3.]
    assert alarms.lower.tolist() == [-2.]


@pytest.mark.parametrize('rule,values', [
    (1,[0.,3.01]), (2,[.5]*9), (3,[-.3,-.2,-.1,0.,.1,.2]),
    (4,[-.2,.2]*7), (5,[2.1,0.,2.2]), (6,[1.1,1.2,0.,1.3,1.4]),
    (7,[0.]*15), (8,[-1.1,1.1]*4),
])
def test_each_nelson_rule_known_minimal_pattern(rule,values):
    assert nelson_events(values,[rule]) == [(len(values)-1,rule,0 if rule!=1 else 1)]
    assert nelson_events(values[:-1],[rule]) == []
    if rule != 7:
        assert nelson_events(-np.array(values),[rule]) == [(len(values)-1,rule,0 if rule!=1 else 1)]
    r=analyze_spc(pd.DataFrame({'x':values}),['x'],kind='Nelson',mean=0.,sigma=1.,rules=[rule])
    alarm=r.tables['alarms'].iloc[0]
    assert alarm.source_row==len(values) and alarm.rule=='Nelson '+str(rule)
    assert json.loads(alarm.members) == ([2] if rule==1 else list(range(1,len(values)+1)))
    assert r.tables['observations'].alarm.sum()==1


@pytest.mark.parametrize('rule,values', [
    (1,[-3.,3.]),(2,[1.]*4+[0.]+[1.]*4),(3,[0,1,2,2,3,4]),
    (4,[0.,1.]*6+[1.,0.]),(5,[2.,2.,0.]),(5,[2.1,-2.1,0.]),
    (6,[1.,1.,1.,1.,0.]),(7,[0.]*14+[np.nextafter(1.,np.inf)]),(8,[-1.1,1.1]*3+[-1.,1.1]),
    (5,[2.1,2.2,0.]),(6,[1.1,1.2,1.3,1.4,0.]),
    (8,[1.1]*8),
])
def test_nelson_boundaries_ties_and_sides_do_not_trigger(rule,values):
    assert nelson_events(values,[rule])==[]


def test_nelson_no_fuzzy_threshold_and_rule_selection():
    assert nelson_events([np.nextafter(3.,np.inf)],[1])==[(0,1,0)]
    assert nelson_events([3.],[1])==[]
    assert nelson_events([5.]*20,[])==[]
    result=nelson_events([4.]*10,[1,2])
    assert result[-2:]==[(9,1,9),(9,2,1)]
    assert nelson_events([1.,-1.]*7+[0.],[7])==[(14,7,0)]


def test_t2_independent_covariance_quadratic_forms_and_distribution_cdf():
    rng=np.random.default_rng(732)
    baseline=pd.DataFrame(rng.normal(size=(40,3))@np.array([[1.,.3,0],[0,2.,.2],[.4,0,1.]]),columns=['a','b','variable'])
    current=pd.DataFrame([[0.,0.,0.],[12.,15.,14.]],columns=baseline.columns,index=['000001',9007199254740993])
    r=analyze_spc(current,list(current),kind='T2',baseline=baseline)
    centered=baseline.to_numpy()-baseline.mean().to_numpy()
    cov=centered.T@centered/39
    d=current.to_numpy()-baseline.mean().to_numpy()
    expected=np.array([v@np.linalg.inv(cov)@v for v in d])
    np.testing.assert_allclose(r.tables['observations'].statistic,expected)
    n,p=40,3
    for row in r.tables['limits'].itertuples():
        if row.phase=='phase1':
            probability=special.betainc(p/2,(n-p-1)/2,row.upper/((n-1)**2/n))
        else:
            f=row.upper/(p*(n+1)*(n-1)/(n*(n-p)))
            probability=special.betainc(p/2,(n-p)/2,p*f/(p*f+n-p))
        assert probability==pytest.approx(row.confidence,abs=2e-13)
    assert r.tables['observations'].alarm.tolist()==[False,True]
    assert r.tables['alarms'].source_index.tolist()==[9007199254740993]
    h=r.tables['baseline']
    np.testing.assert_allclose(h.statistic,[v@np.linalg.inv(cov)@v for v in centered])
    assert h.upper.iloc[0] != r.tables['observations'].upper.iloc[0]
    np.testing.assert_allclose(r.tables['covariance'].covariance.to_numpy().reshape(3,3),cov)
    phase1=analyze_spc(baseline,list(baseline),kind='T2')
    np.testing.assert_allclose(phase1.tables['observations'].statistic,h.statistic)
    np.testing.assert_allclose(phase1.tables['observations'].upper,h.upper)


def test_t2_single_variable_and_confidence_selection():
    base=pd.DataFrame({'x':[-2.,-1.,0.,1.,2.]})
    r=analyze_spc(pd.DataFrame({'x':[4.]}),['x'],kind='T2',baseline=base,confidence=.99)
    assert r.tables['observations'].statistic.iloc[0]==pytest.approx(16/2.5)
    limits=r.tables['limits'].set_index(['phase','confidence'])
    assert r.tables['observations'].upper.iloc[0]==limits.loc[('phase2',.99),'upper']


@pytest.mark.parametrize('kind', ['EWMA','CUSUM','Nelson','T2'])
def test_fixed_baseline_source_provenance_missing_and_comparison(kind):
    base=pd.DataFrame({'x':[-2.,-1.,0.,1.,2.]})
    cur=pd.DataFrame({'x':[6.,np.nan,7.,8.]},index=['0001','skip',9007199254740993,'tail'])
    original=cur.copy(deep=True);base_original=base.copy(deep=True)
    r=analyze_spc(cur,['x'],kind=kind,baseline=base,missing='drop')
    out=r.tables['observations']
    assert out.source_row.tolist()==[1,3,4]
    assert out.source_index.tolist()==['0001',9007199254740993,'tail']
    assert out.sequence.tolist()==[1,2,3]
    assert r.tables['parameters']['mean'].iloc[0]==0
    assert r.tables['parameters']['std'].iloc[0]==pytest.approx(np.sqrt(2.5))
    cmp=r.tables['comparison'].iloc[0]
    assert cmp.difference==7 and cmp.current_n==3 and cmp.baseline_n==5
    assert cmp.current_std==1
    pd.testing.assert_frame_equal(cur,original);pd.testing.assert_frame_equal(base,base_original)


@pytest.mark.parametrize('kwargs', [
    {'columns':[]},{'columns':['x','x']},{'columns':['missing']},{'kind':'wrong'},
    {'mean':0.},{'sigma':1.},{'mean':0.,'sigma':0.}, {'mean':0.,'sigma':np.inf},
    {'mean':1j,'sigma':1.}, {'mean':True,'sigma':1.},
    {'ewma_lambda':0.},{'ewma_lambda':1.1},{'ewma_width':-1.},
    {'kind':'CUSUM','cusum_k':-1.},{'kind':'CUSUM','cusum_h':0.},
    {'kind':'Nelson','rules':[9]}, {'kind':'Nelson','rules':[True]}, {'kind':'Nelson','rules':[1,1]},
    {'confidence':.9},{'missing':'fill'}, {'kind':'T2','mean':0.,'sigma':1.},
    {'baseline':pd.DataFrame({'x':[-1.,1.]}),'mean':0.,'sigma':1.},
])
def test_invalid_configuration_is_explicit(kwargs):
    options={'columns':['x']};options.update(kwargs)
    with pytest.raises(ValueError):
        analyze_spc(pd.DataFrame({'x':[-1.,0.,1.]}),**options)


@pytest.mark.parametrize('values', [[np.nan,1.],[np.inf,1.],['1','2'],[True,False],[1j,2j],[np.nan,np.nan]])
def test_invalid_observations_not_silently_coerced(values):
    with pytest.raises(ValueError):
        analyze_spc(pd.DataFrame({'x':values}),['x'])


def test_constant_singular_and_sample_size_boundaries():
    for data,columns,kind in [(pd.DataFrame({'x':[1.,1.]}),['x'],'EWMA'),
        (pd.DataFrame({'x':[1.]}),['x'],'EWMA'),
        (pd.DataFrame({'x':[0.,1.,2.,3.],'y':[0.,2.,4.,6.]}),['x','y'],'T2'),
        (pd.DataFrame({'x':[0.,1.,2.],'y':[1.,0.,2.]}),['x','y'],'T2')]:
        with pytest.raises(ValueError):
            analyze_spc(data,columns,kind=kind)
    # 当前稳定常量不是错误：有独立历史方差即可监控。
    r=analyze_spc(pd.DataFrame({'x':[0.,0.]}),['x'],baseline=pd.DataFrame({'x':[-1.,0.,1.]}))
    assert not r.tables['observations'].alarm.any()


def test_cancel_and_nullable_input():
    event=Event();event.set()
    with pytest.raises(InterruptedError):
        analyze_spc(pd.DataFrame({'x':[0.,1.]}),['x'],cancel=event)
    r=analyze_spc(pd.DataFrame({'x':pd.Series([0,pd.NA,1],dtype='Int64')}),['x'],missing='drop')
    assert r.tables['observations'].source_row.tolist()==[1,3]
