"""六项定向修复：独立数值参考、真实消费者和授权范围外不变性。"""
import ast
import inspect
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest
from matplotlib.figure import Figure
from scipy import stats
from source_baselines import read_source_baseline

import control_chart as spc
import ctrlchart_dialog as dialogs
import utilities
import proportion_test as prop

ROOT = Path(__file__).resolve().parents[1]
BASE = '5b68df06ce3892eace5f43f2c142df4d1b273eeb'


def before(module):
    source = read_source_baseline(BASE, f'code/{module.__name__}.py')
    namespace = dict(module.__dict__)
    exec(compile(source, f'<before:{module.__name__}>', 'exec'), namespace)
    return SimpleNamespace(**namespace)


def var(value):
    return SimpleNamespace(get=lambda: value)


def u_input(df, labels=''):
    fig = Figure()
    ax = fig.subplots()
    dialog = SimpleNamespace(df=df, xvar=var('count'), N=var('units'), xlabelID=var(labels),
                             get_axs=lambda: (fig, ax, None))
    return dialogs.UDialog.get_data(dialog)


def chart(function, **kwargs):
    fig = Figure()
    ax = fig.subplots()
    lines = []
    result = function(fig=fig, ax=ax, print_out=True, print_port=lines.append, **kwargs)
    return result, ax, '\n'.join(lines)


@pytest.fixture(autouse=True)
def no_show(monkeypatch):
    monkeypatch.setattr(spc.plt, 'show', Mock())


@pytest.mark.parametrize('counts,units', [([1], [10]), ([1, 0, 4], [10, 20, 5])])
def test_u_raw_counts_with_and_without_labels(counts, units):
    df = pd.DataFrame({'count': counts, 'units': units, 'ID': list('ABC')[:len(counts)]})
    outputs = []
    for label in ['', 'ID']:
        data, labels, fig, ax, n = u_input(df, label)
        assert data == counts
        assert n == units
        assert labels == (df.ID.tolist() if label else list(range(1, len(counts)+1)))
        assert spc.cu_plot(c=data, n=n, fig=fig, ax=ax) is None
        outputs.append([line.get_ydata() for line in ax.lines])
    for a, b in zip(*outputs):
        np.testing.assert_array_equal(a, b)
    np.testing.assert_array_equal(outputs[0][0], np.array(counts)/units)
    assert outputs[0][1][0] == sum(counts)/sum(units)


@pytest.mark.parametrize('label', ['', 'ID'])
def test_u_paired_cleaning_order_and_invalid_columns(label):
    df = pd.DataFrame({'count': [4, None, 0, 'bad', 1, 9],
                       'units': [5, 10, 20, 4, None, 'bad'], 'ID': list('FEDCBA')})
    data, labels, _, _, n = u_input(df, label)
    assert data == [4., 0.] and n == [5., 20.]
    assert labels == (['F', 'D'] if label else [1, 2])
    with pytest.raises(KeyError):
        u_input(df.drop(columns='units'), label)


@pytest.mark.parametrize('C,n', [(True, 1), (False, [10, 20, 5])])
def test_c_u_correct_direct_path_unchanged(C, n):
    old = chart(before(spc).cu_plot, c=[1, 0, 4], n=n, C=C)
    new = chart(spc.cu_plot, c=[1, 0, 4], n=n, C=C)
    assert old[0] is new[0] is None and old[2] == new[2]
    for a, b in zip(old[1].lines, new[1].lines):
        np.testing.assert_array_equal(a.get_ydata(), b.get_ydata())


@pytest.mark.parametrize('n1,n2,e1,e2', [(10,10,0,5), (10,10,10,5), (20,20,3,14), (9,17,2,8)])
def test_fisher_right_tail_and_other_results(n1, n2, e1, e2):
    kwargs = dict(n1=n1, n2=n2, e1=e1, e2=e2)
    old = before(prop).prop_2sample(**kwargs)
    lines = []
    result = prop.prop_2sample(**kwargs, print_out=True, print_port=lines.append)
    right = stats.hypergeom.sf(e1-1, n1+n2, e1+e2, n1)
    assert result['p p1>p2 Fisher'] == right
    assert right == pytest.approx(stats.fisher_exact([[e1,n1-e1],[e2,n2-e2]], alternative='greater').pvalue)
    assert result.keys() == old.keys()
    assert {k:v for k,v in result.items() if k != 'p p1>p2 Fisher'} == {k:v for k,v in old.items() if k != 'p p1>p2 Fisher'}
    row = next(line for line in '\n'.join(lines).splitlines() if line.startswith('| Fisher'))
    assert row.split('|')[-2].strip() == f'{right:.3f}'


@pytest.mark.parametrize('sign', [1, -1])
@pytest.mark.parametrize('alpha', [.05, .1])
def test_pearson_perfect_direction(sign, alpha):
    x = [1., 2., 3., 4., 5.]
    y = [sign*i for i in x]
    old = before(utilities).pearson_correlation(x, y, alpha=alpha, print_out=False)
    lines = []
    result = utilities.pearson_correlation(x, y, alpha=alpha, print_port=lines.append)
    assert (result['r'], result['r_l'], result['r_u']) == (sign, sign, sign)
    assert {k:v for k,v in result.items() if k not in ('r_l','r_u')} == {k:v for k,v in old.items() if k not in ('r_l','r_u')}
    assert '双侧置信下限' in '\n'.join(lines)


@pytest.mark.parametrize('y', [[2,4,5,8,11], [-2,-4,-5,-8,-11], [1,2,3,4,5.00001], [-1,-2,-3,-4,-5.00001]])
@pytest.mark.parametrize('alpha', [.01, .1])
def test_pearson_nonperfect_unchanged(y, alpha):
    x = [1.,2.,3.,4.,5.]
    result = utilities.pearson_correlation(x,y,alpha=alpha,print_out=False)
    assert result == before(utilities).pearson_correlation(x,y,alpha=alpha,print_out=False)
    z = np.arctanh(result['r'])
    np.testing.assert_array_equal([result['r_l'],result['r_u']], np.tanh([z-stats.norm.ppf(1-alpha/2)/np.sqrt(2),z+stats.norm.ppf(1-alpha/2)/np.sqrt(2)]))


def test_p1_old_patterns_removed():
    assert 'data.append(float(i) / float(k))' not in inspect.getsource(dialogs.UDialog.get_data)
    assert 'cdf(max(e1 - 1, 0))' not in inspect.getsource(prop.prop_2sample)
    assert 'r_z = 10000' not in inspect.getsource(utilities.pearson_correlation)

@pytest.mark.parametrize('NP,n', [(False,100), (False,[50,100,80]), (True,100), (True,[100,100,100]), (True,[50,100,80])])
@pytest.mark.parametrize('p', [[.1,.2,.05], [0.,0.,0.], [1.,.5,1.]])
def test_np_p_per_point_counts_limits_and_reports(NP, n, p, monkeypatch):
    tables = []
    original = spc.gen_table
    def capture(rows):
        table = original(rows)
        tables.append(table)
        return table
    monkeypatch.setattr(spc,'gen_table',capture)
    result, ax, text = chart(spc.p_np_plot, p=p, n=n, NP=NP)
    nlist = np.array(n if isinstance(n,list) else [n]*len(p))
    pbar = sum(np.array(p)*nlist)/sum(nlist)
    center = np.repeat(pbar,len(p))
    upper = center + 3*np.sqrt(pbar*(1-pbar)/nlist)
    lower = np.maximum(0,center - 3*np.sqrt(pbar*(1-pbar)/nlist))
    points = np.array(p)
    if NP:
        center,upper,lower,points = [value*nlist for value in (center,upper,lower,points)]
    assert result is None
    np.testing.assert_array_equal(ax.lines[0].get_ydata(), points)
    actual_center = ax.lines[1].get_ydata()
    np.testing.assert_array_equal(actual_center, [center[0]]*2 if len(set(center))==1 else np.repeat(center,2))
    np.testing.assert_allclose(ax.lines[2].get_ydata(),np.repeat(upper,2))
    np.testing.assert_allclose(ax.lines[3].get_ydata(),np.repeat(lower,2))
    for i,row in enumerate(tables[1].rows):
        assert row[3:] == ['%.6g'%v for v in (points[i],lower[i],center[i],upper[i])]
    if not NP or len(set(nlist)) == 1:
        old = chart(before(spc).p_np_plot,p=p,n=n,NP=NP)
        for a,b in zip(old[1].lines,ax.lines):
            np.testing.assert_array_equal(a.get_ydata(),b.get_ydata())
        if not NP:
            assert old[2] == text


def blaker_reference(n,p,k):
    # 定义：gamma(i)=min(P[X<=i],P[X>=i])，累加 gamma(i)<=gamma(k) 的概率。
    from math import comb
    mass = [comb(n,i)*p**i*(1-p)**(n-i) for i in range(n+1)]
    gamma = [min(sum(mass[:i+1]),sum(mass[i:])) for i in range(n+1)]
    return min(1.,sum(m for m,g in zip(mass,gamma) if g<=gamma[k]))


@pytest.mark.parametrize('n,p', [(1,.4),(5,.1),(20,.4),(20,.8),(50,.4)])
def test_blaker_boundary_pvalues_definition_and_normal_baseline(n,p):
    old = before(prop)
    for k in sorted({0,1,n//2,n-1,n}):
        value = prop.p_blaker(n,p,k)
        assert 0<=value<=1
        assert value == pytest.approx(blaker_reference(n,p,k),abs=3e-14)
        try:
            previous = old.p_blaker(n,p,k)
        except ValueError:
            continue
        if k not in (0,n):
            assert value == previous


@pytest.mark.parametrize('n', [5,20])
@pytest.mark.parametrize('alpha', [.05,.1])
def test_blaker_intervals_and_full_single_report(n,alpha):
    for k in [0,1,n-1,n]:
        lines=[]
        result=prop.prop_test_1sample(k,n,.4,alpha=alpha,print_out=True,print_port=lines.append)
        lo,hi=result['Blaker CI']
        assert 0<=lo<=k/n<=hi<=1
        assert result['p Blaker']==pytest.approx(blaker_reference(n,.4,k),abs=3e-14)
        assert '调整 Blaker' in '\n'.join(lines)
        # 区间反演：内点不拒绝，区间外点拒绝；容差避开离散跳点。
        for theta in [max(1e-5,lo-.002), (lo+hi)/2, min(1-1e-5,hi+.002)]:
            if lo+.002<theta<hi-.002:
                assert blaker_reference(n,theta,k)>=alpha-1e-5
            elif theta<lo-.001 or theta>hi+.001:
                assert blaker_reference(n,theta,k)<=alpha+1e-5


@pytest.mark.parametrize('n', [5,10])
def test_blaker_interval_coverage(n):
    from blakerCI import binom_blaker_limits
    for alpha in [.05,.1]:
        intervals=[binom_blaker_limits(k,n,level=1-alpha,tol=1e-6) for k in range(n+1)]
        for theta in [.01,.1,.3,.5,.8,.99]:
            coverage=sum(stats.binom.pmf(k,n,theta) for k,(lo,hi) in enumerate(intervals) if lo<=theta<=hi)
            assert coverage>=1-alpha-1e-6



def test_p2_old_patterns_removed():
    from pandastable_local.plotting import PlotViewer
    assert 'nlist[0]' not in inspect.getsource(spc.p_np_plot)
    assert "errors='ignore'" not in inspect.getsource(PlotViewer._checkNumeric)
    source=ast.parse(inspect.getsource(prop.p_blaker))
    for call in ast.walk(source):
        if isinstance(call,ast.Call) and isinstance(call.func,ast.Name) and call.func.id in {'max','min'}:
            assert any(kw.arg=='default' for kw in call.keywords)


def test_pearson_roundoff_is_clipped():
    x=[2/7+i*.13 for i in range(5)]
    y=[-3*i+.1 for i in x]
    result=utilities.pearson_correlation(x,y,print_out=False)
    assert result['r']==result['r_l']==result['r_u']==-1
    assert result['p']==0 and np.isfinite(result['cov'])


@pytest.mark.parametrize('name',['LinearFitDialog','CorrelationDialog','MCorDialog'])
def test_real_pearson_dialog_consumers_use_correct_interval(name,monkeypatch):
    import fit_dialog
    x=[1.,2.,3.,4.,5.]; y=[-v for v in x]
    lines=[]; viewer=SimpleNamespace(fig=Figure())
    flags=dict(linear=False,ortho=False,ellipse=True,red_ellipse=False,
               show_CI=False,show_PI=False,ortho_resid=False,ortho_ratio=1,
               scatter=True,alpha=.05,cor_p=True,cor_s=False,cor_k=False,cor_h=False,
               ylabel_0deg=False,xlabel_45deg=False,xtick_45deg=False)
    dialog=SimpleNamespace(**{k:var(v) for k,v in flags.items()},df=pd.DataFrame({'X':x,'Y':y}),
        grpcols=['X','Y'],xvar=var('X'),yvar=var('Y'),get_plot_settings=Mock(),
        xlabel='X',ylabel='Y',x_min=None,x_max=None,y_min=None,y_max=None,ax_margin=var(.1) if name=='MCorDialog' else .1,
        show_legend=False,grid=False,error=Mock(),
        app=SimpleNamespace(print=lines.append,showPlotViewer=lambda **kwargs:viewer))
    target='multi_fit' if name=='MCorDialog' else 'fit_plot'
    original=getattr(fit_dialog,target)
    captured=[]
    def run(*args,**kwargs):
        result=original(*args,**kwargs);captured.append(result);return result
    monkeypatch.setattr(fit_dialog,target,run)
    getattr(fit_dialog,name).apply(dialog)
    result=captured[0]['pearson'][0][1] if name=='MCorDialog' else captured[0]['Pearson']
    assert (result['r'],result['r_l'],result['r_u'])==(-1,-1,-1)
    assert 'Pearson' in '\n'.join(lines)
    dialog.error.assert_not_called()


@pytest.mark.parametrize('name',['multi_fit','multi_fit_orig'])
def test_both_pearson_matrix_consumers(name):
    import linear_plot
    data=[[1.,2.,3.,4.,5.],[-1.,-2.,-3.,-4.,-5.]]
    fig=Figure(); lines=[]
    options={'ax':fig.subplots()} if name=='multi_fit' else {'axs':fig.subplots(1,1,squeeze=False)}
    result=getattr(linear_plot,name)(data,['X','Y'],fig=fig,ellipse=False,print_out=True,print_port=lines.append,**options)
    assert result['pearson'][0][1]['r_l']==result['pearson'][0][1]['r_u']==-1
    assert 'Pearson 相关系数矩阵' in '\n'.join(lines)


@pytest.mark.parametrize('summarized',[False,True])
def test_fisher_real_dialog_reports_correct_zero_tail(summarized):
    import sample_test_dialog
    fields=dict(xvar='X',yvar='Y',event_name='1',event_name2='1',alpha=.05,
                event_cnt=0 if summarized else '',ttl_cnt=10 if summarized else '',
                event_cnt2=5 if summarized else '',ttl_cnt2=10 if summarized else '')
    lines=[]
    dialog=SimpleNamespace(**{k:var(v) for k,v in fields.items()},
        df=pd.DataFrame({'X':[0]*10,'Y':[1]*5+[0]*5}),app=SimpleNamespace(print=lines.append))
    sample_test_dialog.Prop2SDialog.apply(dialog)
    row=next(line for line in '\n'.join(lines).splitlines() if line.startswith('| Fisher'))
    assert row.split('|')[-2].strip()=='1.000'


def test_legacy_conversion_against_actual_pandas2_fixture(monkeypatch):
    import json
    from pandastable_local.plotting import PlotViewer
    baseline=json.loads((ROOT/'tests/fixtures/pandas2_numeric_baseline.json').read_text())
    original=pd.DataFrame.apply
    outputs=[]
    def capture(frame,*args,**kwargs):
        result=original(frame,*args,**kwargs);outputs.append(result);return result
    monkeypatch.setattr(pd.DataFrame,'apply',capture)
    for case in baseline['cases']:
        frame=pd.DataFrame({'value':pd.Series(case['input'],dtype=object)})
        assert PlotViewer._checkNumeric(SimpleNamespace(),frame) is None
        expected=pd.Series(case['output'],name='value',dtype=case['dtype'])
        pd.testing.assert_series_equal(outputs[-1]['value'],expected)
    assert PlotViewer._checkNumeric(SimpleNamespace(),pd.DataFrame()) is False


@pytest.mark.parametrize('events',[3,8,14])
@pytest.mark.parametrize('alpha',[.05,.1])
def test_single_proportion_nonboundary_results_exactly_unchanged(events,alpha):
    actual=prop.prop_test_1sample(events,20,.4,alpha=alpha)
    previous=before(prop).prop_test_1sample(events,20,.4,alpha=alpha)
    assert actual==previous


@pytest.mark.parametrize('function,kwargs',[(spc.cu_plot,{'c':[1],'n':0}),
    (spc.p_np_plot,{'p':[.1],'n':0,'NP':True}),
    (spc.p_np_plot,{'p':[],'n':100,'NP':True})])
def test_control_chart_existing_invalid_input_failures(function,kwargs):
    old=getattr(before(spc),function.__name__)
    with pytest.raises(Exception) as baseline:
        chart(old,**kwargs)
    with pytest.raises(type(baseline.value)):
        chart(function,**kwargs)


@pytest.mark.parametrize('n,p,k',[(5,.5,0),(5,.5,5),(20,.5,0),(20,.5,20),(50,.4,50),(50,.8,0)])
def test_blaker_full_event_tails_include_exact_ties_and_tiny_mass(n,p,k):
    assert prop.p_blaker(n,p,k)==pytest.approx(blaker_reference(n,p,k),rel=1e-12,abs=1e-30)

@pytest.mark.parametrize('k',[1,2,3,4])
def test_blaker_internal_tie_behavior_is_outside_boundary_fix(k):
    assert prop.p_blaker(5,.5,k)==before(prop).p_blaker(5,.5,k)
