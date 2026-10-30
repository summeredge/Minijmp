import pandas as pd

from doe_core import DesignSpec, FactorSpec, restore_design_result
from doe_taguchi import create_taguchi
from doe_taguchi_analysis_dialog import AnalyzeTaguchi
from doe_taguchi_arrays import ARRAYS
from test_csv_import import csv_app


def factor(factor_id):
    return FactorSpec(factor_id, factor_id, None, None, factor_type='categorical',
                      levels=('low', 'high'), level_type='text')


def make_noise_sheet(app):
    spec = DesignSpec(
        'TG', tuple(factor(key) for key in ('A', 'B', 'N1', 'N2')), ('Y',),
        seed=19, design_type='taguchi',
        taguchi={'kind': 'static', 'array_id': 'L4(2^3)',
                 'matrix_sha256': ARRAYS['L4(2^3)'].sha256,
                 'columns': {'A': 1, 'B': 2},
                 'noise_array_id': 'L4(2^3)',
                 'noise_matrix_sha256': ARRAYS['L4(2^3)'].sha256,
                 'noise_columns': {'N1': 1, 'N2': 2}, 'signal_factor': None})
    frame, metadata = create_taguchi(spec)
    design = restore_design_result(frame, metadata)
    values = {}
    for run in design.runs:
        a, b, n1, n2 = (-1 if run.settings[key] == 'low' else 1
                        for key in ('A', 'B', 'N1', 'N2'))
        values[run.run_id] = 30 + 2*a - 3*b + 4*n1 + 5*n2 + 6*a*b + 2*a*n1 \
            + 0.75*a*b*n1
    frame['响应_Y'] = [values[run_id] for run_id in frame['运行ID']]
    table = app.addSheet('Taguchi 噪声', frame, {'doe': metadata})
    return table


def test_taguchi_model_terms_ci_specified_prediction_and_confirmation_sheet(
        csv_app, tmp_path, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr('doe_taguchi_analysis_dialog.messagebox.showerror', error)
    monkeypatch.setattr('worksheets.messagebox.askyesnocancel', lambda *a, **k: False)
    monkeypatch.setattr('worksheets.messagebox.askyesno', lambda *a, **k: True)
    source = make_noise_sheet(app)
    original = source.model.df.copy(deep=True)
    analysis = AnalyzeTaguchi(app)
    analysis.analyze()
    analysis.best_metric.set('目标均值')
    analysis.best_target.insert(0, '30')
    analysis.confidence.set('90%')

    analysis.edit_model_terms()
    terms_dialog = analysis.model_terms_dialog
    terms_dialog.listbox.selection_set(2)
    terms_dialog.apply()
    assert ('A', 'B') in analysis.model_terms
    analysis.best()
    best = analysis.best_window
    assert best.result['model_terms'] == analysis.model_terms
    assert best.result['mean_ci']['status'] == '可用'
    assert best.result['model']['rank'] == best.result['model']['parameter_count']

    best.predict_specific()
    point = best.point_prediction
    assert point.predict() is True
    assert 'CI' in point.output.get()
    point.levels['A'].set('high')
    assert point.predict() is True

    best.confirm_sheet_button.invoke()
    confirmation = app.getCurrentTable()
    plan = confirmation.model.df
    assert plan['DOE 试验类型'].value_counts().to_dict() == {
        '原始运行': len(original), '确认试验': 4}
    additions = plan[plan['DOE 试验类型'] == '确认试验']
    assert additions['响应_Y'].isna().all()
    assert set(additions['设定_A']) == {best.result['best']['A']}
    assert set(additions['设定_B']) == {best.result['best']['B']}
    assert set(additions['设定_N1']) == {'low', 'high'}
    assert set(additions['设定_N2']) == {'low', 'high'}
    pd.testing.assert_frame_equal(source.model.df, original)

    path = tmp_path / 'taguchi-confirmation.dexpl'
    assert app._save_project(path)
    assert app.load_file(path)
    reopened_name = next(name for name, table in app.sheets.items()
                         if 'DOE 试验类型' in table.model.df.columns)
    app.nb.select(app.sheetframes[reopened_name])
    reopened = app.getCurrentTable()
    copied = app.copySheet()
    pd.testing.assert_frame_equal(copied.model.df, reopened.model.df)
    assert error.call_count == 0
    point.main.destroy()
    best.main.destroy()
    analysis.main.destroy()


def test_noise_response_model_gui_fits_selected_interaction_and_mean_range(
        csv_app, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr('doe_taguchi_analysis_dialog.messagebox.showerror', error)
    table = make_noise_sheet(app)
    analysis = AnalyzeTaguchi(app)
    analysis.analyze()
    analysis.noise()
    analysis.noise_window.response_model()
    model = analysis.noise_window.model_window
    model.listbox.selection_set(0)
    model.constraint_mode.set('均值范围')
    model._constraint_changed()
    model.lower.insert(0, '27')
    model.upper.insert(0, '33')
    assert model.fit() is True, error.call_args_list
    assert model.result['estimable'] is True
    assert model.result['interactions'] == (('A', 'N1'),)
    assert model.result['search']['eligible_count'] == 2
    assert model.result['best'] is not None
    assert len(model.result['candidates']) == 4
    assert '系数' in [model.tabs.tab(tab, 'text') for tab in model.tabs.tabs()]
    assert error.call_count == 0
    model.main.destroy()
    analysis.noise_window.main.destroy()
    analysis.main.destroy()


def test_confirmation_sheet_rejects_source_changed_after_best_settings(
        csv_app, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr('doe_taguchi_analysis_dialog.messagebox.showerror', error)
    source = make_noise_sheet(app)
    analysis = AnalyzeTaguchi(app)
    analysis.analyze()
    analysis.best_metric.set('目标均值')
    analysis.best_target.insert(0, '30')
    analysis.best()
    best = analysis.best_window
    names = list(app.sheets)
    source.model.setValueAt('100', 0, source.model.df.columns.get_loc('响应_Y'))
    best.create_confirmation_sheet()
    assert error.call_count == 1
    assert '来源试验数据已更改' in error.call_args.args[1]
    assert list(app.sheets) == names
    best.main.destroy()
    analysis.main.destroy()
