"""Worksheet formula evaluation, dependencies, editing rules and persistence."""
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from dialog import findRepDialog
from test_csv_import import csv_app
from worksheet_formulas import FormulaError, cycle_message, evaluate, make_formula


def sheet_app(csv_app):
    app, errors = csv_app
    table = app.addSheet('公式', pd.DataFrame({'C1': [100., 90.], 'C2': [80., 45.]}))
    return app, table, errors


def assign(table, target='结果', expression='(C1-C2)/C2*100', link=True):
    table.define_formula(target, expression, link=link)


def test_percent_change_and_one_shot_values():
    df = pd.DataFrame({'C1': [100.], 'C2': [80.], 'C3': [0.]})
    formula = make_formula('C3', '(C1-C2)/C2*100', df)
    result = evaluate({'C3': formula}, df)
    assert result['C3'].tolist() == [25.0]
    assert formula['sources'] == {'C1': 'C1', 'C2': 'C2'}


@pytest.mark.parametrize('expression', [
    '__import__("os")', 'C1.real', 'C1 if C2 else 0', '[C1]', 'C1 **',
    'SUM(C1)', 'C9 + 1', 'C1 > 2',
])
def test_unsupported_syntax_is_rejected(expression):
    with pytest.raises(FormulaError):
        make_formula('结果', expression, pd.DataFrame({'C1': [1.], 'C2': [2.]}))


def test_non_numeric_source_and_division_use_clean_errors():
    df = pd.DataFrame({'C1': [1., 2.], 'C2': ['a', 'b']})
    with pytest.raises(FormulaError):
        make_formula('结果', 'C1 + C2', df)
    zeros = pd.DataFrame({'C1': [1., 2.], 'C2': [0., 2.]})
    formula = make_formula('结果', 'C1 / C2', zeros)
    result = evaluate({'结果': formula}, zeros.assign(结果=0.0))
    assert pd.isna(result['结果'].iloc[0])
    assert result['结果'].iloc[1] == 1.0
    assert '溢出' in formula['warning']


def test_chained_formulas_recalculate_in_dependency_order():
    df = pd.DataFrame({'C1': [10.], 'C2': [2.], 'C3': [0.], 'C4': [0.]})
    formulas = {'C4': make_formula('C4', 'C3 * 2', df),
                'C3': make_formula('C3', 'C1 / C2', df)}
    result = evaluate(formulas, df)
    assert result['C3'].tolist() == [5.0]
    assert result['C4'].tolist() == [10.0]


def test_cycle_is_reported_and_still_blocked_for_three_columns():
    df = pd.DataFrame({'a': [1.], 'b': [2.], 'c': [3.]})
    formulas = {'a': make_formula('a', 'C2', df),
                'b': make_formula('b', 'C3', df),
                'c': make_formula('c', 'C1', df)}
    assert cycle_message(formulas)
    assert evaluate(formulas, df).equals(df)


def test_auto_recalculation_stale_manual_mode_and_unlink(csv_app, monkeypatch):
    app, table, errors = sheet_app(csv_app)
    monkeypatch.setattr('modified_table.messagebox.askyesno', lambda *a, **k: True)
    assign(table)
    assert table.model.df['结果'].tolist() == [25.0, 100.0]

    table.model.df.loc[0, 'C1'] = 120.0
    table.tableChanged()
    assert table.model.df['结果'].iloc[0] == 50.0

    table.formulas_auto = False
    table.model.df.loc[1, 'C2'] = 60.0
    table.tableChanged()
    assert table.model.df['结果'].iloc[1] == 100.0
    assert table.formulas['结果']['stale']
    table.recalculate_formulas()
    assert table.model.df['结果'].iloc[1] == 50.0
    assert not table.formulas['结果']['stale']

    table.setSelectedCol(list(table.model.df.columns).index('结果'))
    table.delete_column_formula()
    assert '结果' not in table.formulas
    assert table.model.df['结果'].iloc[1] == 50.0
    errors.assert_not_called()


def test_one_shot_does_not_follow_source_and_formula_columns_are_readonly(csv_app, monkeypatch):
    app, table, errors = sheet_app(csv_app)
    monkeypatch.setattr('modified_table.messagebox.askyesno', lambda *a, **k: True)
    warnings = []
    monkeypatch.setattr('modified_table.messagebox.showwarning',
                        lambda title, message, **kw: warnings.append(message))
    assign(table, link=False)
    assert not table.formulas
    table.model.df.loc[0, 'C1'] = 200.0
    table.tableChanged()
    assert table.model.df['结果'].iloc[0] == 25.0

    assign(table)
    table.setSelectedCol(2)
    assert table.paste_context_selection('cell', [0], [2]) is False
    assert warnings
    assert table.model.df['结果'].iloc[0] == 150.0

    table.setSelectedCol(0)
    table.model.df.loc[0, 'C1'] = 120.0
    table.tableChanged()
    table.setSelectedCol(2)
    table.delete_column_formula()
    assert table.model.df['结果'].iloc[0] == 50.0


def test_fill_down_rejects_formula_results_and_recalculates_sources(csv_app, monkeypatch):
    app, table, errors = sheet_app(csv_app)
    assign(table)
    before = table.model.df.copy(deep=True)
    history = [frame.copy(deep=True) for frame in table.prevdf]
    warnings = []
    monkeypatch.setattr('modified_table.messagebox.showwarning',
                        lambda title, message, **kw: warnings.append(message))

    table.fillDown([0, 1], [2])
    assert_frame_equal(table.model.df, before)
    assert warnings and '结果' in warnings[-1]
    assert len(table.prevdf) == len(history)
    for actual, expected in zip(table.prevdf, history):
        assert_frame_equal(actual, expected)

    table.fillDown([0, 1], [0])
    assert table.model.df['C1'].tolist() == [100.0, 100.0]
    assert table.model.df['结果'].iloc[1] == pytest.approx((100 - 45) / 45 * 100)
    errors.assert_not_called()


def test_find_replace_rejects_linked_formula_results(csv_app, monkeypatch):
    app, table, errors = sheet_app(csv_app)
    assign(table)
    before = table.model.df.copy(deep=True)
    history = [frame.copy(deep=True) for frame in table.prevdf]
    warnings = []
    monkeypatch.setattr('modified_table.messagebox.showwarning',
                        lambda title, message, **kw: warnings.append(message))
    search = SimpleNamespace(table=table, find=lambda: None,
                             coords=[(2, 0)],
                             replacevar=SimpleNamespace(get=lambda: '999'))

    findRepDialog.replace(search)

    assert_frame_equal(table.model.df, before)
    assert len(table.prevdf) == len(history)
    for actual, expected in zip(table.prevdf, history):
        assert_frame_equal(actual, expected)
    assert warnings and '结果' in warnings[-1]
    errors.assert_not_called()


def test_failed_expression_leaves_data_untouched(csv_app):
    app, table, errors = sheet_app(csv_app)
    original = table.model.df.copy(deep=True)
    with pytest.raises(FormulaError):
        assign(table, expression='C9 + 1')
    assert_frame_equal(table.model.df, original)
    assert not table.formulas


def test_cycle_cannot_be_assigned_and_new_column_is_added(csv_app):
    app, table, errors = sheet_app(csv_app)
    assign(table, 'C3', 'C1 - C2')
    with pytest.raises(FormulaError):
        assign(table, 'C1', 'C3 + 1')
    assign(table, '新列', 'C1 + 1')
    assert table.model.df['新列'].tolist() == [101.0, 91.0]


def test_creation_adds_new_column(csv_app):
    app, table, errors = sheet_app(csv_app)
    assign(table, '增长率', '(C1-C2)/C2*100')
    assert list(table.model.df.columns)[-1] == '增长率'
    assert table.model.df['增长率'].tolist() == [25.0, 100.0]


def test_formula_symbols_and_functions():
    df = pd.DataFrame({'C1': [2.0, 3.0], 'C2': [3.0, 2.0], 'c': [1.0] * 2})
    expressions = {
        'c': 'ABS(C1) + SQRT(C1) + LOG(C1) + EXP(1) + ROUND(C2 / 2, 1) + C1 ** 2 - C1 % 2',
    }
    formula = make_formula('c', expressions['c'], df)
    result = evaluate({'c': formula}, df)
    expected = (np.abs(df.C1) + np.sqrt(df.C1) + np.log(df.C1) + np.exp(1)
                + np.round(df.C2 / 2, 1) + df.C1 ** 2 - df.C1 % 2)
    np.testing.assert_allclose(result['c'], expected)


def test_rename_and_delete_keep_formula_references_explicit(csv_app):
    app, table, errors = sheet_app(csv_app)
    assign(table)
    table.model.df.rename(columns={'C1': '温度'}, inplace=True)
    table.formula_column_renamed('C1', '温度')
    table.model.df.loc[0, '温度'] = 120.0
    table.tableChanged()
    assert table.model.df['结果'].iloc[0] == 50.0
    assert table.formulas['结果']['sources']['C1'] == '温度'

    table.model.df.rename(columns={'C2': '压力'}, inplace=True)
    table.formula_column_renamed('C2', '压力')
    assert table.formulas['结果']['sources']['C2'] == '压力'
    table.model.df.drop(columns=['压力'], inplace=True)
    table.formula_source_removed('压力')
    table.tableChanged()
    assert '已不存在' in table.formulas['结果']['error']


def test_project_roundtrip_restores_formula_state(csv_app, monkeypatch, tmp_path):
    import worksheets
    app, table, errors = sheet_app(csv_app)
    monkeypatch.setattr(worksheets.messagebox, 'askyesno', lambda *a, **k: True)
    monkeypatch.setattr(worksheets.messagebox, 'askyesnocancel', lambda *a, **k: False)
    assign(table)
    table.formulas_auto = False
    table.model.df.loc[0, 'C1'] = 120.0
    table.tableChanged()
    path = tmp_path / '公式.dexpl'
    assert app._save_project(path)
    assert app.load_file(path)
    restored = app.getCurrentTable()
    assert restored.formulas['结果']['expression'] == '(C1-C2)/C2*100'
    assert restored.formulas['结果']['sources'] == {'C1': 'C1', 'C2': 'C2'}
    assert restored.formulas_auto is False
    assert restored.model.df['结果'].iloc[0] == 25.0
    assert restored.formulas['结果']['stale'] is True
    restored.recalculate_formulas()
    assert restored.model.df['结果'].iloc[0] == 50.0
    assert restored.formulas['结果']['stale'] is False
    errors.assert_not_called()


def test_cell_paste_expansion_into_formula_column_is_rejected(csv_app, monkeypatch):
    app, table, errors = sheet_app(csv_app)
    assign(table)
    original = table.model.df.copy(deep=True)
    warnings = []
    monkeypatch.setattr('modified_table.messagebox.showwarning',
                        lambda title, message, **kw: warnings.append(message))
    monkeypatch.setattr(table, 'clipboard_get', lambda: '1\t2')
    assert table.paste_context_selection('cell', [0], [1]) is False
    assert_frame_equal(table.model.df, original)
    assert warnings and '先解除公式关联' in warnings[0]


def test_row_paste_covering_formula_column_is_rejected(csv_app, monkeypatch):
    app, table, errors = sheet_app(csv_app)
    assign(table)
    original = table.model.df.copy(deep=True)
    monkeypatch.setattr('modified_table.messagebox.showwarning', lambda *a, **k: None)
    monkeypatch.setattr(table, 'clipboard_get', lambda: '1\t2\t3')
    assert table.paste_context_selection('row', [1], list(range(3))) is False
    assert_frame_equal(table.model.df, original)


def test_keyboard_row_paste_cannot_overwrite_formula_column(csv_app, monkeypatch):
    app, table, errors = sheet_app(csv_app)
    assign(table)
    original = table.model.df.copy(deep=True)
    warnings = []
    monkeypatch.setattr('modified_table.messagebox.showwarning',
                        lambda title, message, **kw: warnings.append(message))
    monkeypatch.setattr(table, 'clipboard_get', lambda: '1\t2\t3')
    table.multiplerowlist, table.multiplecollist = [0], []
    table.allrows = False
    history_before = table.prevdf
    history_end_before = table.prevdf_end

    table.paste()

    assert_frame_equal(table.model.df, original)
    assert warnings and '先解除公式关联' in warnings[0]
    assert table.prevdf is history_before
    assert table.prevdf_end == history_end_before
    errors.assert_not_called()


def test_keyboard_column_paste_cannot_overwrite_formula_column(csv_app, monkeypatch):
    app, table, errors = sheet_app(csv_app)
    assign(table)
    original = table.model.df.copy(deep=True)
    warnings = []
    monkeypatch.setattr('modified_table.messagebox.showwarning',
                        lambda title, message, **kw: warnings.append(message))
    monkeypatch.setattr(table, 'clipboard_get', lambda: '10\n20')
    table.multiplerowlist, table.multiplecollist = [], [2]
    table.allrows = True
    history_before = table.prevdf
    history_end_before = getattr(table, 'prevdf_end', None)

    assert table.paste() is False

    assert_frame_equal(table.model.df, original)
    assert warnings and '先解除公式关联' in warnings[0]
    assert table.prevdf is history_before
    assert getattr(table, 'prevdf_end', None) == history_end_before
    errors.assert_not_called()


def test_row1_to_header_rebinds_formula_sources_by_position(csv_app):
    app, table, errors = sheet_app(csv_app)
    table.model.df = pd.DataFrame({'C1': [101., 100., 90.],
                                   'C2': [102., 80., 45.]})
    assign(table)
    table.row1ToHeader()
    assert list(table.model.df.columns)[:2] == [101.0, 102.0]
    formula = next(iter(table.formulas.values()))
    assert formula['sources'] == {'C1': 101.0, 'C2': 102.0}
    table.model.df.iloc[0, 0] = 120.0
    table.model.df.iloc[0, 1] = 80.0
    table.tableChanged()
    assert table.model.df.iloc[0, 2] == 50.0


def test_numeric_column_names_survive_project_roundtrip(csv_app, monkeypatch, tmp_path):
    import worksheets
    app, table, errors = sheet_app(csv_app)
    monkeypatch.setattr(worksheets.messagebox, 'askyesno', lambda *a, **k: True)
    monkeypatch.setattr(worksheets.messagebox, 'askyesnocancel', lambda *a, **k: False)
    table.model.df = pd.DataFrame({'C1': [101., 100., 90.],
                                   'C2': [102., 80., 45.]})
    assign(table)
    table.row1ToHeader()
    assert list(table.model.df.columns)[:2] == [101.0, 102.0]
    path = tmp_path / '数值列名.dexpl'
    assert app._save_project(path)
    assert app.load_file(path)
    restored = app.getCurrentTable()
    assert list(restored.model.df.columns)[:2] == [101.0, 102.0]
    assert set(restored.formulas) == {restored.model.df.columns[2]}
    formula = next(iter(restored.formulas.values()))
    assert formula['sources'] == {'C1': 101.0, 'C2': 102.0}
    restored.model.df.iloc[0, 0] = 120.0
    restored.model.df.iloc[0, 1] = 80.0
    restored.tableChanged()
    assert restored.model.df.iloc[0, 2] == 50.0
    errors.assert_not_called()


def test_sorting_formula_source_updates_formula_results(csv_app, monkeypatch):
    app, table, errors = sheet_app(csv_app)
    assign(table)
    table.model.df['C1'] = [90.0, 100.0]
    table.tableChanged()
    table.setSelectedCol(0)
    monkeypatch.setattr('modified_table.MultipleValDialog', lambda **kw:
                        type('D', (), {'result': True,
                                       'results': ['C1', True, '', True, '', True]})())
    table.sortSelected()
    assert table.model.df['C1'].tolist() == [90.0, 100.0]
    np.testing.assert_allclose(table.model.df['结果'], [12.5, 100 / 45 * 100 - 100])


def test_insert_and_delete_rows_refresh_linked_formulas(csv_app):
    app, table, errors = sheet_app(csv_app)
    table.model.df = pd.DataFrame({'C1': [100., 90.], 'C2': [80., 45.]})
    assign(table)

    table.setSelectedRow(1)
    table.insertRow()
    assert len(table.model.df) == 3
    assert table.model.df['结果'].iloc[[0, 2]].tolist() == [25., 100.]
    assert pd.isna(table.model.df['结果'].iloc[1])

    table.setSelectedRow(1)
    table.deleteRow()
    assert table.model.df['结果'].tolist() == [25., 100.]
    errors.assert_not_called()


def test_formula_undo_redo_keeps_definitions_and_data_in_sync(csv_app):
    app, table, errors = sheet_app(csv_app)
    before = table.model.df.copy(deep=True)
    assign(table)
    after = table.model.df.copy(deep=True)
    table.undo()
    assert_frame_equal(table.model.df, before)
    assert not table.formulas
    table.redo()
    assert_frame_equal(table.model.df, after)
    assert table.formulas['结果']['sources'] == {'C1': 'C1', 'C2': 'C2'}


def test_repeated_undo_redo_never_detaches_formula_from_data(csv_app):
    app, table, errors = sheet_app(csv_app)
    before = table.model.df.copy(deep=True)
    assign(table)
    after = table.model.df.copy(deep=True)
    for _ in range(3):
        table.undo()
        assert_frame_equal(table.model.df, before)
        assert not table.formulas
        table.redo()
        assert_frame_equal(table.model.df, after)
        assert '结果' in table.formulas


@pytest.mark.parametrize(('operation', 'auto'), [
    ('clear', True), ('clear', False), ('shift', True), ('shift', False),
])
def test_clearing_formula_sources_updates_or_marks_stale(
        csv_app, monkeypatch, operation, auto):
    app, table, errors = sheet_app(csv_app)
    monkeypatch.setattr('modified_table.messagebox.askyesno', lambda *a, **k: True)
    table.model.df = pd.DataFrame({'C1': [100., 90., 70.],
                                   'C2': [80., 45., 50.]})
    assign(table)
    table.formulas_auto = auto
    table.multiplerowlist, table.multiplecollist = [0], [0]
    table.allrows = False

    if operation == 'clear':
        table.clearData()
    else:
        table.clearDataUp()

    if auto:
        expected = ([np.nan, 100., 40.] if operation == 'clear'
                    else [(90. - 80.) / 80. * 100.,
                          (70. - 45.) / 45. * 100., np.nan])
        np.testing.assert_allclose(table.model.df['结果'], expected, equal_nan=True)
        assert table.formulas['结果']['stale'] is False
    else:
        assert table.model.df['结果'].tolist() == [25., 100., 40.]
        assert table.formulas['结果']['stale'] is True
    errors.assert_not_called()


def test_multiple_sheet_formula_state_roundtrip_is_isolated(csv_app, monkeypatch, tmp_path):
    import worksheets
    app, first, errors = sheet_app(csv_app)
    monkeypatch.setattr(worksheets.messagebox, 'askyesno', lambda *a, **k: True)
    monkeypatch.setattr(worksheets.messagebox, 'askyesnocancel', lambda *a, **k: False)
    assign(first)

    second = app.addSheet('第二张', pd.DataFrame({'C1': [60., 40.], 'C2': [20., 10.]}))
    assign(second)
    second.formulas_auto = False
    second.model.df.loc[0, 'C1'] = 80.
    second.tableChanged()
    first.model.df.loc[0, 'C1'] = 120.
    first.tableChanged()
    assert first.formulas_auto is True and second.formulas_auto is False
    assert first.model.df['结果'].tolist() == [50., 100.]
    assert second.model.df['结果'].tolist() == [200., 300.]
    assert second.formulas['结果']['stale'] is True

    path = tmp_path / '多工作表公式.dexpl'
    assert app._save_project(path)
    assert app.load_file(path)
    restored_first = app.sheets['公式']
    restored_second = app.sheets['第二张']
    assert restored_first.formulas_auto is True
    assert restored_first.model.df['结果'].tolist() == [50., 100.]
    assert restored_second.formulas_auto is False
    assert restored_second.model.df['结果'].tolist() == [200., 300.]
    assert restored_second.formulas['结果']['stale'] is True

    restored_second.recalculate_formulas()
    assert restored_second.model.df['结果'].tolist() == [300., 300.]
    assert restored_first.model.df['结果'].tolist() == [50., 100.]
    errors.assert_not_called()
