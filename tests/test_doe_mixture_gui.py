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


def test_mixture_v2_gui_lifecycle_uses_saved_model_and_actual_amounts(
        csv_app, tmp_path, monkeypatch):
    import json
    from pathlib import Path
    import doe_mixture_dialog as mixture_dialog
    from doe_mixture_analysis import analyze_mixture
    from doe_mixture_predict import predict_mixture

    app, error = csv_app
    monkeypatch.setattr('doe_mixture_dialog.messagebox.showerror', error)
    monkeypatch.setattr('worksheets.messagebox.askyesno', lambda *a, **k: True)
    monkeypatch.setattr('worksheets.messagebox.askyesnocancel', lambda *a, **k: False)
    reference = json.loads((Path(__file__).parent / 'fixtures'
                            / 'doe_phase2_p4bc_reference' / 'reference.json').read_text(
                                encoding='utf-8'))['joint_mixture_process_amount_model']
    response_by_key = {
        (tuple(round(float(value), 12) for value in item['proportions']),
         tuple(item['process_codes']), item['amount_code']): response
        for item, response in zip(reference['rows'], reference['responses'])}

    create = CreateMixtureDesign(app)
    create.process_count.set('2')
    create.update_rows()
    for index, fields in enumerate(create.processes[:2], 1):
        for field, value in zip(fields, (f'P{index}', '1', '2', '')):
            field.delete(0, 'end')
            field.insert(0, value)
    create.amount_enabled.set(True)
    create.update_rows()
    for key, value in (('name', 'T'), ('low', '100'), ('high', '200'),
                       ('fixed', '150'), ('unit', 'g')):
        create.amount[key].delete(0, 'end')
        create.amount[key].insert(0, value)
    for entry, value in zip(create.amount['levels'], ('100', '150', '200')):
        entry.insert(0, value)
    children = set(create.main.winfo_children())
    create.preview()
    assert '72 次运行' in create.preview_text.get()
    for child in create.main.winfo_children():
        if child not in children:
            child.destroy()
    create.create()
    create.main.destroy()
    source_name = app.getCurrentSheet()
    source = app.getCurrentTable()
    frame = source.model.df
    assert source.mixture_metadata['spec']['construction_version'] == 'v2'
    assert source.mixture_metadata['spec']['amount_settings'] == {'T': 150.0}
    assert source.doe_metadata['schema_version'] == 5

    def row_key(row):
        proportions = tuple(round(float(row[f'设定_{key}']), 12)
                            for key in ('A', 'B', 'C'))
        process = tuple(-1 if row[f'设定_P{index}'] == 1 else 1
                        for index in (1, 2))
        amount = 2 * (row['设定_T'] - 100) / 100 - 1
        return proportions, process, amount

    frame['响应_Y'] = [response_by_key[row_key(row)] for _, row in frame.iterrows()]
    before = frame.copy(deep=True)
    metadata = source.mixture_metadata.copy()
    path = tmp_path / 'mixture-v2.dexpl'
    assert app._save_project(path)
    assert app.new_file()
    assert app.load_file(path)
    source = app.sheets[source_name]
    assert_frame_equal(source.model.df, before)
    assert source.mixture_metadata == metadata
    copied = app.copySheet()
    assert copied.mixture_metadata == metadata
    app.nb.select(app.sheetframes[source_name])
    source = app.getCurrentTable()

    analysis = AnalyzeMixtureDesign(app)
    analysis.degree.set('1')
    analysis.terms.insert(0, 'A;B;C')
    analysis.analyze()
    assert analysis.result['rank'] == 3
    assert source.mixture_model['terms'] == ['A', 'B', 'C']
    saved_model = source.mixture_model.copy()
    analysis.main.destroy()

    path = tmp_path / 'mixture-v2-model.dexpl'
    assert app._save_project(path)
    assert app.new_file()
    assert app.load_file(path)
    source = app.sheets[source_name]
    assert source.mixture_model == saved_model
    app.nb.select(app.sheetframes[source_name])
    source = app.getCurrentTable()
    frame = source.model.df.copy(deep=True)

    predictor = PredictMixture(app)
    predictor.confidence.set('90%')
    for key, value in (('A', str(1 / 3)), ('B', str(1 / 3)), ('C', str(1 / 3)),
                       ('P1', '1'), ('P2', '2'), ('T', '175')):
        predictor.entries[key].delete(0, 'end')
        predictor.entries[key].insert(0, value)
    expected = predict_mixture(
        frame, source.mixture_metadata, 'Y', {'A': 1 / 3, 'B': 1 / 3, 'C': 1 / 3},
        {'P1': 1, 'P2': 2}, {'T': 175}, terms=saved_model['terms'], degree=1)
    predictor.predict()
    prediction_tab = predictor.tabs.nametowidget(predictor.tabs.tabs()[0])
    prediction_table = next(child.table for child in prediction_tab.winfo_children()
                            if hasattr(child, 'table'))
    assert prediction_table.values[0][1] == pytest.approx(expected['prediction'])
    interval_tab = next(tab for tab in predictor.tabs.tabs()
                        if predictor.tabs.tab(tab, 'text') == '预测区间')
    interval_table = next(child.table for child in
                          predictor.tabs.nametowidget(interval_tab).winfo_children()
                          if hasattr(child, 'table'))
    assert interval_table.values[0][0] == '90% 均值 CI'
    assert 'df=' in interval_table.values[2][1]
    assert '可用' in interval_table.values[2][1]
    actual_tab = next(tab for tab in predictor.tabs.tabs()
                      if predictor.tabs.tab(tab, 'text') == '实际组分用量')
    actual_table = next(child.table for child in
                        predictor.tabs.nametowidget(actual_tab).winfo_children()
                        if hasattr(child, 'table'))
    assert sum(row[1] for row in actual_table.values) == pytest.approx(175)
    predictor.main.destroy()

    optimizer = OptimizeMixture(app)
    optimizer.confidence.set('90%')
    for key, value in (('P1', '1'), ('P2', '2'), ('T', '175')):
        optimizer.conditions[key].delete(0, 'end')
        optimizer.conditions[key].insert(0, value)
    original_optimize = mixture_dialog.optimize_mixture
    calls = []

    def checked_optimize(*args, **kwargs):
        calls.append((kwargs.get('terms'), kwargs.get('degree'), args[3]))
        return original_optimize(*args, **kwargs)

    monkeypatch.setattr(mixture_dialog, 'optimize_mixture', checked_optimize)
    optimizer.optimize()
    result_tab = next(tab for tab in optimizer.tabs.tabs()
                      if optimizer.tabs.tab(tab, 'text') == '响应预测')
    result_table = next(child.table for child in
                        optimizer.tabs.nametowidget(result_tab).winfo_children()
                        if hasattr(child, 'table'))
    assert '均值 CI' in result_table.headers
    assert result_table.values[0][8] == '90%'
    assert result_table.values[0][9] == '可用'
    assert '未校正' in optimizer.status.get()
    assert calls[0][0] == tuple(saved_model['terms'])
    assert calls[0][1] == saved_model['degree']
    assert calls[0][2] == {'P1': 1, 'P2': 2, 'T': 175}
    assert any(optimizer.tabs.tab(tab, 'text') == '实际组分用量'
               for tab in optimizer.tabs.tabs())
    optimizer.main.destroy()

    original_analyze = mixture_dialog.analyze_mixture
    plot_calls = []

    def checked_analyze(*args, **kwargs):
        plot_calls.append((kwargs.get('terms'), kwargs.get('degree')))
        return original_analyze(*args, **kwargs)

    monkeypatch.setattr(mixture_dialog, 'analyze_mixture', checked_analyze)
    plots = MixturePlots(app)
    plots.entries['T'].delete(0, 'end')
    plots.entries['T'].insert(0, '175')
    plots.entries['P1'].delete(0, 'end')
    plots.entries['P1'].insert(0, '1')
    plots.entries['P2'].delete(0, 'end')
    plots.entries['P2'].insert(0, '2')
    plots.draw()
    assert plot_calls == [(tuple(saved_model['terms']), saved_model['degree'])]
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


def test_mixture_improve_gui_lifecycle_after_source_sheets_are_deleted(
        csv_app, monkeypatch, tmp_path):
    from test_doe_mixture_improve import _oracle_sources

    from doe_mixture_dialog import MixtureOptimalDesignDialog

    app, error = csv_app
    monkeypatch.setattr('doe_mixture_dialog.messagebox.showerror', error)
    monkeypatch.setattr('worksheets.messagebox.askyesno', lambda *a, **k: True)
    monkeypatch.setattr('worksheets.messagebox.askyesnocancel', lambda *a, **k: False)
    case, parent, parent_mixture, parent_doe, candidates, candidate_mixture, candidate_doe = \
        _oracle_sources()
    parent_table = app.addSheet(
        'Improve Parent', parent,
        {'doe': parent_doe, 'mixture': parent_mixture})
    candidate_table = app.addSheet(
        'Improve Candidates', candidates,
        {'doe': candidate_doe, 'mixture': candidate_mixture})
    parent_original = parent.copy(deep=True)
    candidate_original = candidates.copy(deep=True)

    dialog = MixtureOptimalDesignDialog(app)
    dialog.operation.set('改善')
    dialog._operation_changed()
    dialog.parent_sheet.set('Improve Parent')
    dialog._parent_changed()
    dialog.candidate.set('Improve Candidates')
    dialog._candidate_changed()
    dialog.degree.set('1')
    dialog._default_terms()
    dialog.run_tree.selection_set('p2')
    dialog._toggle_run_state()
    assert dialog.run_tree.item('p0', 'values')[1] == '已保护'
    assert dialog.run_tree.item('p1', 'values')[1] == '已保护'
    assert dialog.run_tree.item('p2', 'values')[1] == '可替换'
    dialog.preview()
    assert 'rank 3' in dialog.preview_text.get('1.0', 'end')
    assert 'CAND-C' in dialog.preview_text.get('1.0', 'end')
    assert parent_table.model.df.equals(parent_original)
    assert candidate_table.model.df.equals(candidate_original)
    dialog.create()

    improved_name = app.getCurrentSheet()
    improved = app.getCurrentTable()
    improved_frame = improved.model.df.copy(deep=True)
    assert improved.mixture_metadata['schema_version'] == 2
    assert improved.doe_metadata['schema_version'] == 5
    assert improved_frame['运行ID'].tolist() == case['after']['run_ids']
    assert pd.isna(improved_frame.loc[2, '响应_Y'])

    for name in ('Improve Parent', 'Improve Candidates'):
        app.nb.select(app.sheetframes[name])
        app._sheet_changed()
        assert app.deleteSheet()
    assert 'Improve Parent' not in app.sheets
    assert 'Improve Candidates' not in app.sheets

    path = tmp_path / 'mixture-improve.dexpl'
    assert app._save_project(path)
    assert app.new_file()
    assert app.load_file(path)
    assert improved_name in app.sheets
    restored = app.sheets[improved_name]
    assert_frame_equal(restored.model.df, improved_frame)
    assert restored.mixture_metadata['improvement_lineage'] == \
        improved.mixture_metadata['improvement_lineage']
    copied = app.copySheet()
    assert copied.mixture_metadata == restored.mixture_metadata
    assert copied.doe_metadata == restored.doe_metadata
    assert error.call_count == 0


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
