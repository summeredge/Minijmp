from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from doe_mixture_dialog import (AnalyzeMixtureDesign, CreateMixtureDesign,
                                MixtureOptimalDesignDialog, MixturePlots,
                                OptimizeMixture, PredictMixture)
from test_csv_import import csv_app


def test_mixture_gui_full_lifecycle(csv_app, tmp_path, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr('doe_mixture_dialog.messagebox.showerror', error)
    monkeypatch.setattr('worksheets.messagebox.askyesno', lambda *a, **k: True)
    monkeypatch.setattr('worksheets.messagebox.askyesnocancel', lambda *a, **k: False)
    create = CreateMixtureDesign(app)
    assert create.count.get() == '3'
    before = list(app.sheets)
    create.preview()
    assert list(app.sheets) == before
    assert '6 次运行' in create.preview_text.get()
    create.create()
    table = app.getCurrentTable()
    frame = table.model.df
    frame['响应_Y'] = (2 * frame['设定_A'] + 4 * frame['设定_B'] + 6 * frame['设定_C']
                       + 8 * frame['设定_A'] * frame['设定_B']
                       + 2 * frame['设定_A'] * frame['设定_C']
                       - 3 * frame['设定_B'] * frame['设定_C'])
    expected = frame.copy(deep=True)
    metadata = table.mixture_metadata.copy()
    path = tmp_path / 'mixture.dexpl'
    assert app._save_project(path)
    assert app.new_file()
    assert app.load_file(path)
    restored = app.getCurrentTable()
    assert_frame_equal(restored.model.df, expected)
    assert restored.mixture_metadata == metadata
    copy = app.copySheet()
    assert copy.mixture_metadata == metadata
    assert copy.mixture_metadata is not restored.mixture_metadata

    dialog = AnalyzeMixtureDesign(app)
    dialog.analyze()
    assert dialog.result is not None
    np.testing.assert_allclose(dialog.result['fitted'], expected['响应_Y'], atol=1e-8)
    saved_model = copy.mixture_model.copy()
    assert saved_model['response'] == 'Y'
    dialog.main.destroy()
    copy2 = app.copySheet()
    assert copy2.mixture_model == saved_model

    path2 = tmp_path / 'mixture-model.dexpl'
    assert app._save_project(path2)
    assert app.new_file()
    assert app.load_file(path2)
    reopened = app.getCurrentTable()
    assert reopened.mixture_model == saved_model
    dialog2 = AnalyzeMixtureDesign(app)
    assert dialog2.response.get() == saved_model['response']
    assert dialog2.degree.get() == str(saved_model['degree'])
    assert dialog2.terms.get() == ';'.join(saved_model['terms'])
    dialog2.main.destroy()

    predictor = PredictMixture(app)
    for key, value in (('A', 0.2), ('B', 0.3), ('C', 0.5)):
        predictor.entries[key].delete(0, 'end')
        predictor.entries[key].insert(0, str(value))
    predictor.predict()
    values = [row for tab in predictor.tabs.tabs()
              for block in predictor.tabs.nametowidget(tab).winfo_children()
              for row in getattr(getattr(block, 'table', None), 'values', [])]
    assert any(isinstance(row[1], float) and row[1] == pytest.approx(4.83, abs=1e-9)
               for row in values)
    predictor.main.destroy()

    optimizer = OptimizeMixture(app)
    optimizer.optimize()
    assert optimizer.status.get()
    optimizer.main.destroy()

    for kind in ('Trace', '等高线', '曲面', '叠加等高线'):
        plots = MixturePlots(app)
        plots.kind.set(kind)
        plots.build_limits()
        plots.draw()
        plots.main.destroy()
    error.assert_not_called()


def test_mixture_gui_invalid_configuration_keeps_workbook(csv_app, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr('doe_mixture_dialog.messagebox.showerror', error)
    create = CreateMixtureDesign(app)
    create.components[0][0].delete(0, 'end')
    create.components[0][0].insert(0, 'A')
    create.components[0][2].delete(0, 'end')
    create.components[0][2].insert(0, '0.9')
    before = list(app.sheets)
    create.create()
    assert list(app.sheets) == before
    error.assert_called()
    create.main.destroy()


def test_mixture_menu_entries_exist(csv_app):
    app, _ = csv_app
    menu = app.doe_menu['var']
    labels = [menu.entrycget(index, 'label') for index in range(menu.index('end') + 1)
              if menu.type(index) == 'command']
    assert any('混料设计' in label for label in labels)
    assert any('混料最优设计' in label for label in labels)
    assert any('混料图形' in label for label in labels)


def test_mixture_optimal_gui_selection_augmentation_and_persistence(
        csv_app, tmp_path, monkeypatch, request):
    app, error = csv_app
    request.addfinalizer(app.main.withdraw)
    app.main.deiconify()
    app.main.update()
    monkeypatch.setattr('doe_mixture_dialog.messagebox.showerror', error)
    monkeypatch.setattr('worksheets.messagebox.askyesno', lambda *a, **k: True)
    monkeypatch.setattr('worksheets.messagebox.askyesnocancel', lambda *a, **k: False)

    create = CreateMixtureDesign(app)
    create.create()
    candidate_name = app.getCurrentSheet()
    candidate = app.getCurrentTable()
    columns = candidate.doe_metadata['column_map']
    response = next(iter(columns['responses'].values()))
    factors = columns['factors']
    candidate.model.df[response] = (
        candidate.model.df[factors['A']]
        + 2 * candidate.model.df[factors['B']]
        + 3 * candidate.model.df[factors['C']])

    before = list(app.sheets)
    cancelled = MixtureOptimalDesignDialog(app)
    assert '组分（比例和=1）' in cancelled.design_summary.get()
    cancelled.degree.set('1')
    cancelled._default_terms()
    cancelled.count.delete(0, 'end')
    cancelled.count.insert(0, '3')
    cancelled.preview()
    assert list(app.sheets) == before
    assert cancelled.status.get()
    cancelled.main.destroy()

    dialog = MixtureOptimalDesignDialog(app)
    dialog.degree.set('1')
    dialog._default_terms()
    dialog.count.delete(0, 'end')
    dialog.count.insert(0, '3')
    dialog.preview()
    dialog.count.delete(0, 'end')
    dialog.count.insert(0, '2')
    dialog.create()
    assert list(app.sheets) == before
    dialog.count.delete(0, 'end')
    dialog.count.insert(0, '3')
    dialog.preview()
    candidate.model.df.loc[0, response] += 1
    dialog.create()
    assert list(app.sheets) == before
    dialog.preview()
    dialog.main.geometry('700x480')
    dialog.main.deiconify()
    dialog.main.update()
    assert dialog.execute_button.winfo_viewable()
    assert (dialog.execute_button.winfo_rooty() + dialog.execute_button.winfo_height()
            <= dialog.main.winfo_rooty() + dialog.main.winfo_height())
    dialog.create()
    selected_name = app.getCurrentSheet()
    selected = app.getCurrentTable()
    selected_frame = selected.model.df
    selected_columns = selected.doe_metadata['column_map']
    selected_response = next(iter(selected_columns['responses'].values()))
    assert selected_frame[selected_columns['run_id']].is_unique
    assert selected_frame[selected_response].isna().all()
    assert selected.mixture_model['degree'] == 1

    selected.model.df[selected_response] = [10.0, 20.0, 30.0]
    augment = MixtureOptimalDesignDialog(app)
    augment.operation.set('增补')
    augment._operation_changed()
    augment.candidate.set(candidate_name)
    augment._candidate_changed()
    augment.parent_sheet.set(selected_name)
    augment.criterion.set('Distance-based')
    augment._criterion_changed()
    augment.degree.set('1')
    augment._default_terms()
    augment.count.delete(0, 'end')
    augment.count.insert(0, '1')
    augment.batch_id.delete(0, 'end')
    augment.batch_id.insert(0, 'GUI-AUG')
    augment.preview()
    augment.create()
    augmented_name = app.getCurrentSheet()
    augmented = app.getCurrentTable()
    augmented_frame = augmented.model.df.copy(deep=True)
    augmented_columns = augmented.doe_metadata['column_map']
    augmented_response = next(iter(augmented_columns['responses'].values()))
    assert len(augmented_frame) == 4
    assert augmented_frame[augmented_response].iloc[:3].tolist() == [10.0, 20.0, 30.0]
    assert pd.isna(augmented_frame[augmented_response].iloc[3])
    assert augmented_frame[augmented_columns['run_id']].is_unique
    assert augmented.doe_metadata['design']['augmentation_lineage']['batch_id'] == 'GUI-AUG'
    augmented.model.df.loc[3, augmented_response] = 15.0
    augmented_frame = augmented.model.df.copy(deep=True)

    evaluation = MixtureOptimalDesignDialog(app)
    evaluation.operation.set('评价')
    evaluation._operation_changed()
    evaluation.degree.set('1')
    evaluation._default_terms()
    count_before_evaluation = len(app.sheets)
    evaluation.preview()
    assert 'logdet' in evaluation.preview_text.get('1.0', 'end')
    assert len(app.sheets) == count_before_evaluation
    evaluation.main.destroy()

    path = tmp_path / 'mixture-optimal.dexpl'
    assert app._save_project(path)
    assert app.new_file()
    assert app.load_file(path)
    restored = app.getCurrentTable()
    assert_frame_equal(restored.model.df, augmented_frame)
    assert restored.doe_metadata == augmented.doe_metadata
    assert restored.mixture_metadata == augmented.mixture_metadata
    copied = app.copySheet()
    assert copied.doe_metadata == restored.doe_metadata
    assert copied.doe_metadata is not restored.doe_metadata
    analysis = AnalyzeMixtureDesign(app)
    analysis.analyze()
    assert analysis.result is not None
    analysis.main.destroy()
    assert error.call_count == 2


def test_mixture_gui_high_dimensional_slice(csv_app, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr('doe_mixture_dialog.messagebox.showerror', error)
    create = CreateMixtureDesign(app)
    assert '12' in tuple(map(str, create.count['values']))
    create.count.set('4')
    create.update_rows()
    create.kind.set('Simplex Centroid')
    create.create()
    frame = app.getCurrentTable().model.df
    frame['响应_Y'] = (frame['设定_A'] + 2 * frame['设定_B'] + 3 * frame['设定_C']
                       + 4 * frame['设定_D'])
    plots = MixturePlots(app)
    plots.kind.set('等高线')
    plots.draw()
    assert '剩余比例' in plots.status.get()
    plots.main.destroy()
    error.assert_not_called()


def test_mixture_gui_extreme_vertices_process_and_amount(csv_app, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr('doe_mixture_dialog.messagebox.showerror', error)
    create = CreateMixtureDesign(app)
    create.kind.set('Extreme Vertices')
    create.count.set('3')
    create.update_rows()
    for index, (low, high) in enumerate((('0.2', '0.6'), ('0.1', '0.5'), ('0.2', '0.7'))):
        create.components[index][1].delete(0, 'end')
        create.components[index][1].insert(0, low)
        create.components[index][2].delete(0, 'end')
        create.components[index][2].insert(0, high)
    create.constraints.insert(0, 'A+B<=0.75')
    create.process_count.set('1')
    create.update_rows()
    for key, value in zip(create.processes[0], ('温度', '20', '40', 'C')):
        key.insert(0, value)
    create.amount_enabled.set(True)
    create.update_rows()
    for key, value in (('name', '总量'), ('low', '100'), ('high', '300'),
                       ('fixed', '200'), ('unit', 'g')):
        create.amount[key].delete(0, 'end')
        create.amount[key].insert(0, value)
    create.create()
    table = app.getCurrentTable()
    frame = table.model.df
    spec = table.mixture_metadata['spec']
    assert len(frame) == 12
    assert frame['设定_T'].unique().tolist() == [200]
    assert set(frame['设定_P1']) == {20, 40}
    assert np.allclose(frame[['设定_A', '设定_B', '设定_C']].sum(axis=1), 1)
    assert spec['process_variables'][0]['role'] == 'process'
    assert spec['amount_variables'][0]['role'] == 'amount'
    assert spec['amount_variables'][0]['unit'] == 'g'
    error.assert_not_called()


def test_two_component_gui_only_exposes_trace(csv_app, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr('doe_mixture_dialog.messagebox.showerror', error)
    create = CreateMixtureDesign(app)
    create.count.set('2')
    create.update_rows()
    create.create()
    table = app.getCurrentTable()
    frame = table.model.df
    frame['响应_Y'] = 2 * frame['设定_A'] + 3 * frame['设定_B']
    plots = MixturePlots(app)
    assert str(plots.axis_first['state']) == 'disabled'
    before = getattr(table, 'pf', None)
    plots.kind.set('等高线')
    plots.draw()
    error.assert_called_once()
    assert getattr(table, 'pf', None) is before
    error.reset_mock()
    plots.kind.set('Trace')
    plots.draw()
    error.assert_not_called()
    plots.main.destroy()


def test_rank_deficient_gui_shows_true_estimability(csv_app, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr('doe_mixture_dialog.messagebox.showerror', error)
    create = CreateMixtureDesign(app)
    create.degree.set('1')
    create.create()
    frame = app.getCurrentTable().model.df
    frame['响应_Y'] = frame['设定_A'] + frame['设定_B']
    dialog = AnalyzeMixtureDesign(app)
    dialog.analyze()
    assert dialog.result['rank'] < dialog.result['p']
    titles = [dialog.tabs.tab(tab, 'text') for tab in dialog.tabs.tabs()]
    assert '可估计性' in titles
    tab = dialog.tabs.nametowidget(dialog.tabs.tabs()[titles.index('可估计性')])
    rows = [row for block in tab.winfo_children()
            for row in getattr(getattr(block, 'table', None), 'values', [])]
    assert any(row[1] == '不可单独估计' for row in rows)
    assert not any(row[1] == '不可单独估计' and row[0] in ('A', 'B', 'C') for row in rows)
    dialog.main.destroy()
