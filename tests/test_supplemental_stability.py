import math
import string
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import tkinter as tk

import pandas as pd
import pytest
from scipy.stats import f
from GRR import grr_nested
from modified_table import MTable
from pandastable_local.core import Table
from pandastable_local.core_orig import Table as OriginalTable
from pandastable_local import core_orig
from pandastable_local.data import TableModel
from pandastable_local.data_orig import TableModel as OriginalModel
from qc_dialog import GRR_Nested_Dialog

OP = ['A'] * 4 + ['B'] * 4
PART = [1, 1, 2, 2, 3, 3, 4, 4]

@pytest.mark.parametrize('columns', [26, 27, 50])
@pytest.mark.parametrize('model', [OriginalModel, TableModel])
def test_model_columns(model, columns):
    df = model(rows=3, columns=columns).df
    assert df.shape == (3, columns)
    assert df.columns.is_unique
    assert list(df.columns[:26]) == list(string.ascii_lowercase)
    assert list(df.columns) == list(model(columns=columns).df.columns)

@pytest.mark.parametrize('columns', [26, 27, 50])
@pytest.mark.parametrize('cls', [OriginalTable, Table, MTable])
def test_gui_new_columns(tk_root, monkeypatch, cls, columns):
    frame = tk.Frame(tk_root)
    try:
        table = cls(frame, rows=3, cols=columns)
        table.show()
        tk_root.update()
        assert table.model.df.shape == (3, columns)
        monkeypatch.setattr(core_orig, 'MultipleValDialog', lambda **kw: SimpleNamespace(result=True, results=[4, columns]))
        table.new()
        tk_root.update()
        assert table.model.df.shape == (4, columns)
        assert table.model.df.columns.is_unique
        assert list(table.model.df.columns[:26]) == list(string.ascii_lowercase)
    finally:
        frame.destroy()


def test_nested_reference():
    result = grr_nested(y=[1,3,5,7,9,11,13,15], op=OP, part=PART)
    assert result == pytest.approx({'Distinct Categories': 1, 'P value operator': 1-f.cdf(8,1,2),
        'P value part': 1-f.cdf(8,2,4), 'GRR%': 100*math.sqrt(30/37),
        'GRR STD': math.sqrt(30), 'Repeatability STD': math.sqrt(2), 'Reproducibility STD': math.sqrt(28)})

@pytest.mark.parametrize('y', [[1]*8, [1,1,2,2,1,1,2,2], [1,1,1,1,2,2,2,2], [0,2]*4])
@pytest.mark.parametrize('hist', [None, 3])
def test_nested_zero_components(y, hist):
    output = []
    result = grr_nested(y=y, op=OP, part=PART, hist_std=hist, print_out=True, print_port=output.append)
    assert all(isinstance(v, (int, float)) and (math.isnan(v) or math.isfinite(v)) for v in result.values())
    assert all(result[k] >= 0 for k in ['GRR STD', 'Repeatability STD', 'Reproducibility STD'])
    if len(set(y)) == 1:
        assert math.isnan(result['P value operator'])
        assert math.isnan(result['P value part'])
        assert math.isnan(result['Distinct Categories'])
        assert result['GRR%'] == 0 if hist else math.isnan(result['GRR%'])
    assert 'not estimable' in '\n'.join(output)

@pytest.mark.parametrize('y,op,part', [([],[],[]), ([1]*8,OP,PART[:-1]),
    ([1]*4,['A']*4,[1,1,2,2]), ([1]*4,['A','A','B','B'],[1,2,3,4]),
    ([1]*4,['A','A','B','B'],[1,1,2,2]), ([1]*8,OP,[1,1,2,2]*2),
    ([1]*8,OP,[1,1,1,2,3,3,4,4]), ([float('inf')]*8,OP,PART)])
def test_nested_degenerate_design(y,op,part):
    with pytest.raises(ValueError):
        grr_nested(y=y,op=op,part=part)

@pytest.mark.parametrize('hist', [0,-1,float('nan'),float('inf')])
def test_nested_invalid_history(hist):
    with pytest.raises(ValueError, match='Historical'):
        grr_nested(y=[1]*8,op=OP,part=PART,hist_std=hist)

@pytest.mark.parametrize('valid', [True,False])
def test_nested_actual_dialog_apply(tk_root, valid):
    app = SimpleNamespace(print=Mock(), dialog_help_msg=lambda **kw: '')
    df = pd.DataFrame({'y':[1]*8,'op':OP if valid else ['A']*8,'part':PART})
    dialog = GRR_Nested_Dialog(tk_root, df=df, app=app)
    try:
        dialog.xvar.set('y'); dialog.yvar.set('part'); dialog.ovar.set('op')
        dialog.error = Mock()
        dialog.apply()
        if valid:
            dialog.error.assert_not_called()
            assert 'not estimable' in '\n'.join(str(c.args[0]) for c in app.print.call_args_list)
        else:
            dialog.error.assert_called_once()
    finally:
        dialog.main.destroy()


def test_column_fix_is_in_shared_setup():
    assert TableModel.setup is OriginalModel.setup
    assert Table.new is OriginalTable.new and MTable.new is OriginalTable.new
    root = Path(__file__).resolve().parents[1]
    assert 'ascii_lowercase[:columns]' not in (root/'code/pandastable_local/data_orig.py').read_text(encoding='utf-8')
    assert (root/'code/pandastable_local/core_orig.py').read_text(encoding='utf-8').count('TableModel(rows=rows, columns=cols)') == 2

