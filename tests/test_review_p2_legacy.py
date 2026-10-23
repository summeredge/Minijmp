"""REVIEW-016～019：真实选列、独立报告开关和子组边界。"""
from types import SimpleNamespace
from unittest.mock import Mock
from tkinter import ttk

import numpy as np
import pandas as pd
import pytest
from matplotlib.figure import Figure
from scipy import stats

import fit_dialog
import linear_plot
import qc_dialog
from capability_dialog import CapabilityDialog
from cpk import cpk
from test_capability_dialog import finish
from test_csv_import import csv_app


def value(v):
    return SimpleNamespace(get=lambda: v)


@pytest.mark.parametrize('mixed', [False, True], ids=['headerless-csv', 'int-and-str'])
def test_review016_actual_capability_column_labels(csv_app, monkeypatch, tmp_path, mixed):
    app, errors = csv_app
    if mixed:
        frame = pd.DataFrame({0: [1., 2., 3., 4.], '0': [2., 5., 5., 9.]})
        source = app.addSheet('混合列名', frame.copy())
    else:
        path = tmp_path / 'headerless.csv'
        path.write_text('1,2\n2,5\n3,5\n4,9\n', encoding='utf-8')
        assert app.import_csv(filename=str(path), header=None)
        source = app.getCurrentTable()
        frame = source.model.df.copy()
    dialog = CapabilityDialog(source, frame, app)
    dialog.error = Mock()
    try:
        dialog.fields['lsl'].set('0')
        dialog.fields['usl'].set('10')
        combo = next(w for w in dialog.main.winfo_children()[0].winfo_children()
                     if isinstance(w, ttk.Combobox) and
                     str(w.cget('textvariable')) == str(dialog.fields['measurement']))
        for column in ([0, '0'] if mixed else [0]):
            combo.current(list(frame.columns).index(column))
            assert type(dialog.options()[0]) is type(column)
            dialog.fit()
            finish(app.main, dialog)
            np.testing.assert_array_equal(dialog.result['original'], frame[column])
        if mixed:
            assert len(set(combo.cget('values'))) == 2
        pd.testing.assert_frame_equal(source.model.df, frame)
        errors.assert_not_called()
    finally:
        dialog.close()


@pytest.mark.parametrize('ellipse,outline', [(False, False), (True, False), (False, True)])
def test_review017_pearson_report_independent_of_ellipse(monkeypatch, ellipse, outline):
    x = 1e9 + np.array([1., 2., 3., 4.])
    y = 1e9 + np.array([1., 3., 2., 4.])
    output = []
    flags = dict(cor_p=True, cor_s=False, cor_k=False, cor_h=False,
                 ellipse=ellipse, red_ellipse=outline, scatter=True, alpha=.05)
    d = SimpleNamespace(df=pd.DataFrame({'X': x, 'Y': y}), xvar=value('X'), yvar=value('Y'),
        **{key: value(v) for key, v in flags.items()},
        app=SimpleNamespace(print=output.append, showPlotViewer=lambda: SimpleNamespace(fig=Figure())),
        get_plot_settings=lambda: None, remember_columns=Mock(), xlabel='X', ylabel='Y',
        x_min=None, x_max=None, y_min=None, y_max=None, ax_margin=.1,
        show_legend=False, grid=False)
    calculate = Mock(wraps=linear_plot.pearson_correlation)
    monkeypatch.setattr(linear_plot, 'pearson_correlation', calculate)
    fit_dialog.CorrelationDialog.apply(d)
    calculate.assert_called_once()
    table = [v for v in output if getattr(v, 'title', '') == 'Pearson 相关分析']
    assert len(table) == 1
    reference = stats.pearsonr([1., 2., 3., 4.], [1., 3., 2., 4.])
    assert table[0].values[0][3:] == pytest.approx([reference.statistic, reference.pvalue])


def subgroup_dialog(data, ids=None, ranges=False):
    fields = dict(mvar='Use Subgrp ID Col.' if ids is not None else 'Use Subgrp Size',
                  subid='ID', xvar='X', subsize=2, alpha=.05,
                  subm='Ranges' if ranges else 'Unbiased Std Dev', lsl=0, target=2, usl=5,
                  xlabel='', show_legend=False, show_within=True, show_spec=True)
    frame = pd.DataFrame({'X': data})
    if ids is not None:
        frame['ID'] = pd.Series(ids, dtype=object)
    return SimpleNamespace(df=frame, **{key: value(v) for key, v in fields.items()},
        error=Mock(), remember_columns=Mock(),
        app=SimpleNamespace(print=Mock(), showPlotViewer=Mock(return_value=SimpleNamespace(fig=Figure()))))


@pytest.mark.parametrize('ranges', [False, True])
def test_review018_singleton_subgroup_is_rejected_before_plot(ranges):
    d = subgroup_dialog([1, 2, 3], ranges=ranges)
    qc_dialog.CpkSubDialog.apply(d)
    d.error.assert_called_once()
    assert '至少' in d.error.call_args.args[0]
    d.app.showPlotViewer.assert_not_called()
    with pytest.raises(ValueError, match='子组至少'):
        cpk([[1, 2], [3]], 2, 5, 0, use_range=ranges, print_out=False)
    valid = cpk([[1, 2], [3, 4]], 2, 5, 0, use_range=ranges, print_out=False)
    expected_sigma = 1 / (2 / np.sqrt(np.pi)) if ranges else np.sqrt(np.pi) / 2
    assert valid['Within Sigma'] == pytest.approx(expected_sigma, rel=1e-8)


def test_review019_mixed_ids_keep_first_appearance_and_capability(monkeypatch):
    d = subgroup_dialog([1, 2, 3, 4], ['A', 'A', 1, 1])
    plot = Mock()
    grouping = Mock(wraps=qc_dialog.grouping_by_labels)
    monkeypatch.setattr(qc_dialog, 'grouping_by_labels', grouping)
    monkeypatch.setattr(qc_dialog, 'cpk_plot', plot)
    qc_dialog.CpkSubDialog.apply(d)
    d.error.assert_not_called()
    assert grouping.call_args.kwargs['keys'] == ['A', 1]
    assert [type(k) for k in grouping.call_args.kwargs['keys']] == [str, int]
    groups = plot.call_args.args[0]
    assert groups == [[1., 2.], [3., 4.]]
    result = cpk(groups, 2, 5, 0, print_out=False)
    assert result['Within Sigma'] == pytest.approx(np.sqrt(np.pi)/2)
    assert result['Within']['cp'] == pytest.approx(5 / (3*np.sqrt(np.pi)))
