import pandas as pd

from doe_dialog import AnalyzeDOE
from doe_optimal_dialog import (AugmentDesignDialog, ImproveDesignDialog,
                               OptimalDesignDialog)
from test_csv_import import csv_app
from test_doe_optimal_improvement import (_FACTORIAL_CANDIDATES,
                                          _FACTORIAL_POINTS, make_design)


def test_improve_operation_preview_create_save_reopen_and_analyze(
        csv_app, tmp_path, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr('doe_optimal_dialog.messagebox.showerror', error)
    monkeypatch.setattr('worksheets.messagebox.showerror', error)
    monkeypatch.setattr('worksheets.messagebox.askyesno', lambda *a, **k: True)
    monkeypatch.setattr('worksheets.messagebox.askyesnocancel', lambda *a, **k: False)
    parent, parent_meta = make_design(
        'gui-parent', 'custom_factorial', _FACTORIAL_POINTS,
        responses=[72, None, None, None])
    candidates, candidate_meta = make_design(
        'gui-candidates', 'custom_factorial', _FACTORIAL_CANDIDATES)
    app.addSheet('Parent', parent, {'doe': parent_meta})
    app.addSheet('Candidates', candidates, {'doe': candidate_meta})
    original_parent = parent.copy(deep=True)
    app.nb.select(app.sheetframes['Parent'])

    select_dialog = OptimalDesignDialog(app)
    assert tuple(select_dialog.operation['values']) == ('Select', 'Augment', 'Improve')
    select_dialog.operation.set('Augment')
    augment_dialog = select_dialog._operation_changed()
    assert isinstance(augment_dialog, AugmentDesignDialog)
    augment_dialog.main.destroy()

    select_dialog = OptimalDesignDialog(app)
    select_dialog.operation.set('Improve')
    dialog = select_dialog._operation_changed()
    assert isinstance(dialog, ImproveDesignDialog)
    dialog.parent_sheet.set('Parent')
    dialog.candidate_sheet.set('Candidates')
    dialog._parent_changed()
    dialog._candidate_changed()

    rows_by_id = {dialog.run_tree.item(iid, 'values')[0]: iid
                  for iid in dialog.run_tree.get_children()}
    for run_id in ('gui-parent-2', 'gui-parent-3'):
        dialog.run_tree.selection_set(rows_by_id[run_id])
        dialog._toggle_runs()
        dialog.run_tree.selection_remove(rows_by_id[run_id])
    candidate_index = next(
        index for index in range(dialog.candidate_runs.size())
        if dialog.candidate_runs.get(index) == 'gui-candidates-4')
    dialog.candidate_runs.selection_set(candidate_index)

    assert dialog.preview(), dialog.preview_text.get('1.0', 'end')
    preview = dialog.preview_text.get('1.0', 'end')
    assert '运行数：4 → 4' in preview
    assert 'Locked：3；Replaceable：1；实际替换：1' in preview
    assert '模型秩：3/3 → 3/3' in preview
    assert 'gui-candidates-4 → IMP00001 → gui-parent-4' in preview
    assert '不保证全局最优' in preview
    assert dialog.create()

    pd.testing.assert_frame_equal(app.sheets['Parent'].model.df, original_parent)
    improved_table = app.getCurrentTable()
    assert len(improved_table.model.df) == 4
    lineage = improved_table.doe_metadata['design']['improvement_lineage']
    assert lineage['parent_design_id'] == parent_meta['design']['design_id']
    assert lineage['run_map'][0][0] == 'gui-candidates-4'
    assert pd.isna(improved_table.model.df.loc[3, 'Y'])

    columns = improved_table.doe_metadata['column_map']
    response_column = improved_table.model.df.columns.get_loc(columns['responses']['Y'])
    for index, row in improved_table.model.df.iterrows():
        if pd.isna(row[columns['responses']['Y']]):
            value = 30 + row[columns['factors']['A']] + 2 * row[columns['factors']['B']]
            improved_table.model.setValueAt(str(value), index, response_column)
    project = tmp_path / 'improve-roundtrip.dexpl'
    assert app._save_project(project), error.call_args_list
    assert app.load_file(project)

    reopened_name = next(
        name for name, table in app.sheets.items()
        if table.doe_metadata
        and table.doe_metadata['design'].get('improvement_lineage') is not None)
    app.nb.select(app.sheetframes[reopened_name])
    analysis = AnalyzeDOE(app)
    analysis.analyze()
    assert analysis.result is not None, error.call_args_list
    analysis.main.destroy()
    assert error.call_count == 0
