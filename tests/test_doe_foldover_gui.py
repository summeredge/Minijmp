import pandas as pd
from pandas.testing import assert_frame_equal

from doe_dialog import AnalyzeDOE, CreateDOE
from doe_foldover_dialog import FoldoverDOE
from test_csv_import import csv_app


def select_folded(dialog, *factor_ids):
    choices = tuple(dialog.folded.get(0, 'end'))
    dialog.folded.selection_clear(0, 'end')
    for value in factor_ids or ('全部',):
        dialog.folded.selection_set(choices.index(value))


def create_fractional_source(app):
    dialog = CreateDOE(app, fractional=True)
    dialog.factor_count.set('4')
    dialog.update_factor_rows()
    for index, entries in enumerate(dialog.fields[:4]):
        for entry, value in zip(entries, (chr(65 + index), '0', '1', '')):
            entry.delete(0, 'end')
            entry.insert(0, value)
    dialog.generators.delete(0, 'end')
    dialog.generators.insert(0, 'D=ABC')
    dialog.create()
    return app.getCurrentSheet()


def fill_response(table):
    frame = table.model.df
    response_column = frame.columns.get_loc('响应_Y')
    for index, row in frame.iterrows():
        a, b, c, d = (2 * row[f'设定_{factor}'] - 1 for factor in 'ABCD')
        table.model.setValueAt(str(20 + 2*a + 3*b + 4*c + 5*d),
                               index, response_column)


def invoke_foldover_menu(app):
    menu = app.doe_menu['var']
    index = next(i for i in range(menu.index('end') + 1)
                 if menu.type(i) == 'command'
                 and menu.entrycget(i, 'label').strip() == '折叠两水平部分因子设计')
    previous = set(app.main.winfo_children())
    menu.invoke(index)
    created = set(app.main.winfo_children()) - previous
    return next((widget for widget in created
                 if widget.title() == '折叠两水平部分因子设计'), None)


def test_foldover_menu_preview_create_save_reopen_copy_and_analysis(
        csv_app, tmp_path, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr('doe_foldover_dialog.messagebox.showerror', error)
    monkeypatch.setattr('worksheets.messagebox.askyesnocancel', lambda *a, **k: False)
    monkeypatch.setattr('worksheets.messagebox.askyesno', lambda *a, **k: True)

    source_name = create_fractional_source(app)
    source = app.sheets[source_name]
    fill_response(source)
    original_frame = source.model.df.copy(deep=True)
    original_names = list(app.sheets)

    cancelled = FoldoverDOE(app)
    cancelled.cancel_button.invoke()
    assert list(app.sheets) == original_names
    assert_frame_equal(source.model.df, original_frame)

    menu_window = invoke_foldover_menu(app)
    assert menu_window is not None
    assert menu_window.title() == '折叠两水平部分因子设计'
    menu_window.destroy()
    dialog = FoldoverDOE(app)
    assert tuple(dialog.source['values']) == (source_name,)
    assert tuple(dialog.folded.get(0, 'end')) == ('全部', 'A', 'B', 'C', 'D')

    select_folded(dialog)
    dialog.preview_button.invoke()
    preview = dialog.preview_text.get('1.0', 'end')
    assert '运行数：8 → 16（新增 8）' in preview
    assert '分辨度：IV → IV' in preview
    assert '全模型秩：8 → 8' in preview
    assert '别名组无变化。' in preview
    dialog.create_button.invoke()
    all_folded = app.getCurrentTable()
    assert len(all_folded.model.df) == 16
    assert all_folded.doe_metadata['design']['defining_relations'] == ['I=ABCD']

    dialog = FoldoverDOE(app)
    select_folded(dialog, 'A')
    dialog.preview_button.invoke()
    preview = dialog.preview_text.get('1.0', 'end')
    assert '分辨度：IV → 无非平凡定义关系' in preview
    assert '全模型秩：8 → 16' in preview
    assert '− ' in preview and '+ ' in preview
    dialog.create_button.invoke()

    folded_name = app.getCurrentSheet()
    folded = app.getCurrentTable()
    assert folded_name != source_name
    assert source_name in app.sheets
    assert_frame_equal(source.model.df, original_frame)
    frame = folded.model.df
    metadata = folded.doe_metadata
    run_id = metadata['column_map']['run_id']
    response = metadata['column_map']['responses']['Y']
    added = frame[frame[run_id].astype(str).str.startswith('F')]
    assert len(added) == 8
    assert added[response].isna().all()
    assert metadata['design']['foldover_lineage']['folded_factors'] == ['A']
    fill_response(folded)

    path = tmp_path / 'fractional-foldover.dexpl'
    assert app._save_project(path)
    assert app.load_file(path)
    folded_name = next(name for name, table in app.sheets.items()
                       if table.doe_metadata
                       and table.doe_metadata['design']['foldover_lineage'] is not None
                       and table.doe_metadata['design']['foldover_lineage']['folded_factors'] == ['A'])
    app.nb.select(app.sheetframes[folded_name])
    reopened = app.getCurrentTable()
    copied = app.copySheet()
    assert copied.doe_metadata == reopened.doe_metadata
    assert_frame_equal(copied.model.df, reopened.model.df)

    analysis = AnalyzeDOE(app)
    analysis.analyze()
    assert analysis.result is not None, error.call_args_list
    assert analysis.result['n'] == 16
    assert analysis.result['design'].spec.foldover_lineage['folded_factors'] == ('A',)
    assert error.call_count == 0
    analysis.main.destroy()


def test_multi_factor_foldover_preview_create_and_reopen(csv_app, tmp_path, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr('doe_foldover_dialog.messagebox.showerror', error)
    monkeypatch.setattr('worksheets.messagebox.askyesnocancel', lambda *a, **k: False)
    monkeypatch.setattr('worksheets.messagebox.askyesno', lambda *a, **k: True)
    source_name = create_fractional_source(app)
    source = app.sheets[source_name]
    fill_response(source)
    original = source.model.df.copy(deep=True)

    dialog = FoldoverDOE(app)
    select_folded(dialog, 'A', 'C')
    assert dialog.preview()
    preview = dialog.preview_text.get('1.0', 'end')
    assert '折叠 A、C' in preview and 'A:' in preview and 'C:' in preview
    assert '未选因子不变' in preview and '新运行响应为空' in preview
    dialog.create_button.invoke()

    folded_name = app.getCurrentSheet()
    folded = app.getCurrentTable()
    columns = folded.doe_metadata['column_map']
    assert folded.doe_metadata['design']['foldover_lineage']['folded_factors'] == ['A', 'C']
    assert len(folded.model.df) == 16
    added = folded.model.df[columns['batch_id']] == 'FOLD1'
    assert folded.model.df.loc[added, columns['responses']['Y']].isna().all()
    pd.testing.assert_frame_equal(source.model.df, original)

    for index in folded.model.df.index[added]:
        row = folded.model.df.loc[index]
        a, b, c, d = (2 * row[f'设定_{factor}'] - 1 for factor in 'ABCD')
        folded.model.setValueAt(str(20 + 2*a + 3*b + 4*c + 5*d), index,
                                folded.model.df.columns.get_loc(columns['responses']['Y']))
    path = tmp_path / 'multi-factor-foldover.dexpl'
    assert app._save_project(path)
    assert app.load_file(path)
    reopened = next(name for name, table in app.sheets.items()
                    if table.doe_metadata and table.doe_metadata['design'].get(
                        'foldover_lineage') is not None
                    and table.doe_metadata['design']['foldover_lineage'][
                        'folded_factors'] == ['A', 'C'])
    app.nb.select(app.sheetframes[reopened])
    copied = app.copySheet()
    assert copied.doe_metadata == app.getCurrentTable().doe_metadata
    analysis = AnalyzeDOE(app)
    analysis.analyze()
    assert analysis.result is not None, error.call_args_list
    assert analysis.result['design'].spec.foldover_lineage['folded_factors'] == ('A', 'C')
    assert error.call_count == 0
    analysis.main.destroy()


def test_foldover_menu_rejects_workbook_without_regular_fractional_source(
        csv_app, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr('doe_foldover_dialog.messagebox.showerror', error)
    names = list(app.sheets)
    dialog = invoke_foldover_menu(app)
    assert dialog is None
    assert list(app.sheets) == names
    error.assert_called_once()
