from math import sqrt

import numpy as np
import pandas as pd
import pytest
from scipy import stats

from GRR import type1_gage, gage_linearity


def test_type1_gage_definitions():
    result = type1_gage([9,10,11],10,12,50,6)
    assert result['sd'] == 1
    assert result['study_variation'] == 6
    assert result['cg'] == result['cgk'] == 1
    assert result['bias_p'] == 1
    result = type1_gage([9,10,11],7,12,50,6)
    assert result['cgk'] == 0
    assert result['bias_t'] == pytest.approx(3*sqrt(3))
    assert result['bias_p'] == pytest.approx(1-3*sqrt(3)/sqrt(29))
    assert type1_gage([10,10],10,12,50,6)['cg'] is None
    for readings in ([10], [10,np.nan]):
        with pytest.raises(ValueError):
            type1_gage(readings,10,12,50,6)


def test_gage_linearity_reference_and_invalid_pairs():
    import statsmodels.api as sm
    x = np.repeat([1.,3.,6.],3)
    y = x + .25*x + np.tile([-.1,.2,.1],3)
    parts = np.repeat(['a','b','c'],3)
    _, coef, grouped, (grid,_,lower,upper) = gage_linearity(y,x,parts)
    ref = sm.OLS(y-x, sm.add_constant(x)).fit()
    np.testing.assert_allclose([row[1] for row in coef], ref.params)
    np.testing.assert_allclose([row[-1] for row in coef], ref.pvalues)
    np.testing.assert_allclose(np.array([lower,upper]).T,ref.get_prediction(sm.add_constant(grid)).conf_int())
    for i, row in enumerate(grouped):
        assert row[-1] == pytest.approx(stats.ttest_1samp((y-x)[i*3:i*3+3],0).pvalue)
    with pytest.raises(ValueError,match='仅允许一个参考值'):
        gage_linearity(y,x,np.roll(parts,1))


def test_gage_menu_and_report(tk_root, monkeypatch, tmp_path):
    from MiniJMP import Minijmp
    from qc_dialog import Type1GageDialog
    from stat_table import StatTable
    from test_menu_localization import read_menu
    from test_regression_dialog import dispose

    monkeypatch.setattr(Minijmp, 'start_logging', lambda self: None)
    app = Minijmp(parent=tk_root)
    source = app.addSheet('量具来源',pd.DataFrame({'测量':[1.,1.1,2.1,2.2,3.,3.3],
                                                '标准件':['a','a','b','b','c','c'],
                                                '参考':[1,1,2,2,3,3]}))
    original = Type1GageDialog.__init__
    opened, reports = [], []

    def capture(self,*args,**kwargs):
        original(self,*args,**kwargs)
        opened.append(self)

    monkeypatch.setattr(Type1GageDialog,'__init__',capture)
    monkeypatch.setattr(app,'print',lambda value,**kw: reports.append((value,kw['table'])))
    try:
        menu = app.quality_menu['var']
        for label, fields in [
            ('量具研究（1 型）',{'reference':'2','tolerance':'8','percent':'20','multiplier':'6'}),
            ('量具线性与偏倚',{'reference':'参考','part':'标准件'}),
        ]:
            menu.invoke(next(i for i,_,text in read_menu(menu) if text.strip()==label))
            dialog = opened[-1]
            dialog.fields['measurement'].set('测量')
            for key,value in fields.items():
                dialog.fields[key].set(value)
            dialog.ok()
            assert isinstance(reports[-1][0],StatTable)
            assert reports[-1][1] is source
            assert source.pf is not None
            output = tmp_path/(label+'.png')
            source.pf.savePlot(str(output))
            assert output.stat().st_size > 1000
    finally:
        dispose(app)
