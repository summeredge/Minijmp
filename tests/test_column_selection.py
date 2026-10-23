from types import SimpleNamespace
from unittest.mock import Mock
import tkinter as tk
import importlib
import sys

import pandas as pd
import pytest

import dialog as shared
from basic_dialogs import DescribeDialog, MultiDescribeDialog
from fit_dialog import LinearFitDialog
from basic_plot_dialog import BasicPlotDialog
from test_phase1_plots import app

read_history = shared._read_column_history
write_history = shared._write_column_history


@pytest.fixture
def setup(tk_root, monkeypatch):
    history = {}
    monkeypatch.setattr(shared, '_read_column_history', lambda key: history.get(key, {}))
    monkeypatch.setattr(shared, '_write_column_history', lambda key, value: history.update({key: value}))
    monkeypatch.setattr(shared.Dialogs, 'add_window_help', lambda *args: None)
    source = tk.Frame(tk_root)
    source.multiplecollist = []
    source.currentcol = 0
    app = SimpleNamespace(print=Mock())
    df = pd.DataFrame({'A': [1., 2., 4., 5.], 'B': [2., 3., 5., 7.],
                       'C': [3., 5., 6., 9.], 'group': ['x', 'y', 'x', 'y']})
    opened = []

    def create(cls=DescribeDialog, **kwargs):
        obj = cls(source, df=df, app=app, **kwargs)
        opened.append(obj)
        return obj

    yield source, history, create
    for obj in opened:
        if obj.main.winfo_exists():
            obj.quit()
    source.destroy()


def test_explicit_selection_history_and_manual_success(setup):
    source, history, create = setup
    d = create()
    assert d.xvar.get() == ''  # The implicit currentcol=0 is not a selection.
    d.xvar.set('B')
    d.ok()
    assert create().xvar.get() == 'B'
    source.multiplecollist = [2]
    d = create()
    assert d.xvar.get() == 'C'
    d.xvar.set('A')
    d.ok()
    source.multiplecollist = []
    assert create().xvar.get() == 'A'
    assert create(LinearFitDialog).xvar.get() == ''


@pytest.mark.parametrize('indices', [[-1, 99, True, '0'], []])
def test_invalid_indices_and_stale_or_wrong_type_history(setup, indices):
    source, history, create = setup
    d = create()
    source.multiplecollist = indices
    for name in ['removed', 'group', ['unhashable']]:
        history[d._column_key] = {'xvar': [name]}
        assert create().xvar.get() == ''


def test_multi_selection_sorted_and_saved_before_destroy(setup):
    source, history, create = setup
    source.multiplecollist = [1, 0, 1, -1, 99]
    d = create(MultiDescribeDialog)
    assert d.grpvar.getSelectedItem() == ['A', 'B']
    d.ok()
    source.multiplecollist = []
    assert create(MultiDescribeDialog).grpvar.getSelectedItem() == ['A', 'B']


def test_roles_never_receive_same_automatic_column(setup):
    source, history, create = setup
    d = create(LinearFitDialog)
    history[d._column_key] = {'xvar': ['B'], 'yvar': ['C']}
    source.multiplecollist = [2]
    d = create(LinearFitDialog)
    assert (d.xvar.get(), d.yvar.get()) == ('C', '')
    source.multiplecollist = [1, 0]
    d = create(LinearFitDialog)
    assert (d.xvar.get(), d.yvar.get()) == ('A', 'B')


def test_cancel_validation_and_exception_preserve_history(setup, monkeypatch):
    source, history, create = setup
    d = create()
    history[d._column_key] = {'xvar': ['B']}
    d.xvar.set('C')
    d.quit()
    assert create().xvar.get() == 'B'
    d = create()
    d.df.loc[:, 'A'] = float('nan')
    d.xvar.set('A')
    d.ok()
    assert history[d._column_key] == {'xvar': ['B']}
    d = create()
    d.xvar.set('C')
    monkeypatch.setattr('basic_dialogs.describe', Mock(side_effect=ValueError('failed')))
    with pytest.raises(ValueError, match='failed'):
        d.ok()
    assert history[d._column_key] == {'xvar': ['B']}


def test_plot_kinds_have_separate_history_and_roles(setup):
    source, history, create = setup
    source.multiplecollist = [0, 1, 2]
    d = create(BasicPlotDialog, kind='scatter3d')
    assert [v.get() for v in d.xyz] == ['A', 'B', 'C']
    d.remember_columns()
    source.multiplecollist = []
    assert not create(BasicPlotDialog, kind='bar').variables.getSelectedItem()
    assert [v.get() for v in create(BasicPlotDialog, kind='scatter3d').xyz] == ['A', 'B', 'C']


def test_portable_storage_round_trip_and_corruption(tmp_path, monkeypatch):
    # Exercise the file backend without touching the user's real preferences.
    monkeypatch.setattr(shared, 'os', SimpleNamespace(name='posix', replace=shared.os.replace))
    path = tmp_path / 'settings.json'
    monkeypatch.setattr(shared, '_column_settings_file', lambda: path)
    write_history('describe', {'xvar': ['A']})
    write_history('fit', {'xvar': ['B'], 'yvar': ['C']})
    assert read_history('describe') == {'xvar': ['A']}
    assert read_history('fit')['yvar'] == ['C']
    path.write_text('{broken', encoding='utf-8')
    assert read_history('describe') == {}


@pytest.mark.parametrize('module', ['basic_dialogs', 'fit_dialog', 'sample_test_dialog',
                                   'qc_dialog', 'ctrlchart_dialog', 'anova_dialog',
                                   'sb_hist_dialog'])
def test_registered_dialogs_build_with_valid_distinct_roles(setup, module):
    source, history, create = setup
    source.multiplecollist = [0, 1, 2, 3]
    for cls in vars(importlib.import_module(module)).values():
        if not isinstance(cls, type) or cls.__module__ != module or not getattr(cls, 'column_roles', ()):
            continue
        d = create(cls)
        picks = [c for values in d._collect_column_selection().values() for c in values]
        assert picks and len(picks) == len(set(picks)), cls.__name__
        d.quit()


def test_windows_registry_round_trip_without_user_writes(monkeypatch):
    from contextlib import nullcontext
    values = {}
    registry = SimpleNamespace(
        HKEY_CURRENT_USER=1, KEY_SET_VALUE=2, REG_SZ=1,
        CreateKeyEx=lambda *args: nullcontext('key'),
        OpenKey=lambda *args: nullcontext('key'),
        SetValueEx=lambda key, name, unused, kind, value: values.update({name: value}),
        QueryValueEx=lambda key, name: (values[name], 1))
    monkeypatch.setitem(sys.modules, 'winreg', registry)
    monkeypatch.setattr(shared, 'os', SimpleNamespace(name='nt'))
    write_history('describe', {'xvar': ['中文列']})
    write_history('fit', {'xvar': ['X'], 'yvar': ['Y']})
    assert read_history('describe') == {'xvar': ['中文列']}
    assert read_history('fit') == {'xvar': ['X'], 'yvar': ['Y']}


def test_real_preview_success_failure_and_source_switch(app, monkeypatch):
    from stat_plot_dialog import StatPlotDialog
    history = {}
    monkeypatch.setattr(shared, '_read_column_history', lambda key: history.get(key, {}))
    monkeypatch.setattr(shared, '_write_column_history', lambda key, value: history.update({key: value}))
    source = app.table
    source.model.df = pd.DataFrame({'A': [1., 2., 3.], 'B': [4., 5., 6.]})
    source.multiplecollist = [0]
    d = BasicPlotDialog(source, df=source.model.df, app=app, kind='bar')
    d.preview()
    assert history[d._column_key]['variables'] == ['A']
    viewer = source.pf
    d.variables.selection_clear(0, 'end')
    d.variables.selection_set(1)
    monkeypatch.setattr(app, 'replacePlotViewer', Mock(side_effect=ValueError('failed render')))
    d.preview()
    assert history[d._column_key]['variables'] == ['A']
    assert source.pf is viewer
    d.quit()
    source.multiplecollist = []
    d = BasicPlotDialog(source, df=source.model.df, app=app, kind='bar')
    assert d.variables.getSelectedItem() == ['A']
    d.quit()
    # Text-only successful previews (stem-and-leaf) have no PlotViewer to commit.
    source.multiplecollist = [0, 1]
    d = StatPlotDialog(source, df=source.model.df, app=app, kind='stem')
    assert d.variables.getSelectedItem() == ['A']
    d.preview()
    assert history[d._column_key]['variables'] == ['A']
    d.quit()


def test_dialog_selection_is_bound_to_source_sheet(setup):
    source, history, create = setup
    source.multiplecollist = [0]
    d = create()
    # The application's active table can change while this dialog is open.
    d.app.table = SimpleNamespace(model=SimpleNamespace(df=pd.DataFrame({'other': [1.]})),
                                  multiplecollist=[0])
    d.xvar.set('B')
    d.ok()
    source.multiplecollist = []
    assert create().xvar.get() == 'B'


def test_unused_summary_roles_keep_previous_columns(setup):
    from sample_test_dialog import Mean1SampleDialog, Mean2SampleDialog
    source, history, create = setup
    d = create(Mean1SampleDialog)
    history[d._column_key] = {'xvar': ['B']}
    d.xvar.set('C')
    for name, value in [('sample_n', '10'), ('sample_mean', '5'),
                        ('sample_std', '2'), ('u0', '0')]:
        getattr(d, name).set(value)
    d.ok()
    assert history[d._column_key] == {'xvar': ['B']}
    d = create(Mean2SampleDialog)
    history[d._column_key] = {'xvar': ['B'], 'yvar': ['C']}
    d.xvar.set('A')
    d.yvar.set('B')
    for name, value in [('n2', '10'), ('u2', '5'), ('s2', '2')]:
        getattr(d, name).set(value)
    d.ok()
    assert history[d._column_key] == {'xvar': ['A'], 'yvar': ['C']}


def test_nonfinite_normality_result_does_not_replace_history(setup, monkeypatch):
    from basic_dialogs import NormTestDialog
    source, history, create = setup
    d = create(NormTestDialog)
    history[d._column_key] = {'xvar': ['B']}
    d.xvar.set('A')
    monkeypatch.setattr('basic_dialogs.norm_test', lambda *args, **kwargs: {'p': float('nan')})
    d.ok()
    assert history[d._column_key] == {'xvar': ['B']}
