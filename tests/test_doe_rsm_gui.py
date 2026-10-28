from unittest.mock import Mock
import copy
import numpy as np
import pytest
from pandas.testing import assert_frame_equal
from doe_core import restore_design_result
from doe_dialog import CreateDOE, AnalyzeDOE
from test_csv_import import csv_app


@pytest.mark.parametrize(('count', 'display_fraction', 'fraction'), [
    (6, '全因子', None), (8, '1/2 分数', 'half'),
    (9, '1/4 分数', 'quarter'), (10, '1/8 分数', 'eighth'),
])
def test_high_dimension_ccd_project_lifecycle(
        csv_app, tmp_path, monkeypatch, count, display_fraction, fraction):
    app, error = csv_app
    monkeypatch.setattr('doe_dialog.messagebox.showerror', error)
    monkeypatch.setattr('worksheets.messagebox.askyesno', lambda *a, **k: True)
    monkeypatch.setattr('worksheets.messagebox.askyesnocancel', lambda *a, **k: False)
    create = CreateDOE(app, ccd=True)
    create.factor_count.set(str(count))
    create.update_factor_rows()
    create.ccd_fraction.set(display_fraction)
    before = list(app.sheets)
    create.preview()
    assert list(app.sheets) == before
    preview = create.preview_text.get()
    create.create()
    table = app.getCurrentTable()
    frame = table.model.df
    factors = [chr(65 + i) for i in range(count)]
    coded = frame[[f'编码_{name}' for name in factors]].to_numpy(float)
    response = 10 + coded @ np.arange(1, count + 1) + (coded ** 2).sum(axis=1)
    frame['响应_Y'] = response
    snapshot = frame.copy(deep=True)
    metadata = copy.deepcopy(table.doe_metadata)
    assert f'{len(frame)} 次运行' in preview
    assert metadata['schema_version'] == 2
    assert metadata['design']['ccd_fraction'] == fraction
    assert len(metadata['design']['factors']) == count
    assert metadata['column_map']['responses']['Y'] == '响应_Y'
    old_frame = app.sheetframes[app.getCurrentSheet()]
    target = tmp_path / f'ccd-{count}.dexpl'
    assert app._save_project(target)
    assert app.new_file()
    assert not old_frame.winfo_exists()
    assert app.load_file(target)
    restored = app.getCurrentTable()
    assert restored is not table
    assert_frame_equal(restored.model.df, snapshot)
    assert restored.doe_metadata == metadata
    result = restore_design_result(restored.model.df, restored.doe_metadata)
    assert len(result.runs) == len(snapshot)
    assert result.spec.ccd_fraction == fraction
    assert result.spec.block_count is None
    assert all(factor.to_coded(value) == pytest.approx(code)
               for run, row in zip(result.runs, coded)
               for factor, code in zip(result.spec.factors, row)
               for value in [run.settings[factor.factor_id]])
    copied = app.copySheet()
    assert copied.doe_metadata == metadata and copied.doe_metadata is not restored.doe_metadata
    assert_frame_equal(copied.model.df, snapshot)
    analysis = AnalyzeDOE(app)
    analysis.analyze()
    assert analysis.result is not None
    np.testing.assert_allclose(analysis.result['fitted'], response, atol=1e-8)
    analysis.main.destroy()
    error.assert_not_called()


def test_ccd_roundtrip_and_plot(csv_app, tmp_path, monkeypatch):
    app, _ = csv_app
    error = Mock()
    confirm = Mock(return_value=False)
    monkeypatch.setattr('doe_dialog.messagebox.showerror', error)
    monkeypatch.setattr('doe_dialog.messagebox.askyesno', confirm)
    monkeypatch.setattr('worksheets.messagebox.askyesnocancel', lambda *a, **k: False)
    create = CreateDOE(app, ccd=True)
    create.ccd_type.set('CCC')
    for field, value in ((create.fields[0][1], '0.1'),
                         (create.fields[0][2], '0.2'),
                         (create.fields[1][1], '65.3'),
                         (create.fields[1][2], '68.3')):
        field.delete(0, 'end')
        field.insert(0, value)
    create.preview()
    assert '超出' in create.preview_text.get()
    before = list(app.sheets)
    create.create()
    assert list(app.sheets) == before
    confirm.return_value = True
    create.create()
    table = app.getCurrentTable()
    frame = table.model.df
    a = frame['编码_A'].to_numpy(float)
    b = frame['编码_B'].to_numpy(float)
    saved_levels = frame[['设定_A', '设定_B', '编码_A', '编码_B']].to_dict('records')
    values = 40+3*a-2*b+4*a*b+5*a*a-1.5*b*b
    for i, value in enumerate(values):
        table.model.setValueAt(str(value), i, frame.columns.get_loc('响应_Y'))
    dialog = AnalyzeDOE(app)
    dialog.analyze()
    np.testing.assert_allclose(dialog.result['coefficients'], [40, 3, -2, 5, -1.5, 4], atol=1e-10)
    dialog.plot()
    assert len(table.pf.fig.axes) == 4
    target = tmp_path / 'ccd.dexpl'
    assert app._save_project(target)
    assert app.load_file(target)
    restored_table = app.getCurrentTable()
    assert restored_table.model.df[['设定_A', '设定_B', '编码_A', '编码_B']].to_dict('records') == saved_levels
    assert [factor['low'] for factor in restored_table.doe_metadata['design']['factors']] == [0.1, 65.3]
    assert [factor['high'] for factor in restored_table.doe_metadata['design']['factors']] == [0.2, 68.3]
    dialog.main.destroy()
    reopened = AnalyzeDOE(app)
    reopened.analyze()
    assert reopened.result is not None
    error.assert_not_called()
    reopened.main.destroy()
    restored_table = app.getCurrentTable()
    copied = app.copySheet()
    assert copied.doe_metadata == restored_table.doe_metadata
    assert copied.doe_metadata is not restored_table.doe_metadata
    copy_dialog = AnalyzeDOE(app)
    copy_dialog.analyze()
    np.testing.assert_allclose(copy_dialog.result['coefficients'], [40, 3, -2, 5, -1.5, 4], atol=1e-10)
    copy_dialog.main.destroy()


def test_ccf_create_cancel(csv_app):
    app, _ = csv_app
    before = list(app.sheets)
    cancelled = CreateDOE(app, ccd=True)
    cancelled.main.destroy()
    assert list(app.sheets) == before
    create = CreateDOE(app, ccd=True)
    create.measured.set(True)
    create.create()
    assert app.getCurrentTable().doe_metadata['design']['ccd_alpha'] == 1
    assert '实测_A' in app.getCurrentTable().model.df


def test_center_that_rounds_to_an_endpoint_does_not_create_sheet(csv_app, monkeypatch):
    app, _ = csv_app
    error = Mock()
    monkeypatch.setattr('doe_dialog.messagebox.showerror', error)
    before = list(app.sheets)
    create = CreateDOE(app, ccd=True)
    create.fields[0][1].delete(0, 'end')
    create.fields[0][1].insert(0, '1.0')
    create.fields[0][2].delete(0, 'end')
    create.fields[0][2].insert(0, '1.0000000000000002')
    create.create()
    assert list(app.sheets) == before
    assert '中心点' in error.call_args.args[1]
    create.main.destroy()


def test_multiple_responses_and_source_invalidation(csv_app, monkeypatch):
    app, _ = csv_app
    error = Mock()
    monkeypatch.setattr('doe_dialog.messagebox.showerror', error)
    monkeypatch.setattr('worksheets.messagebox.askyesno', lambda *a, **k: True)
    create = CreateDOE(app, ccd=True)
    create.options['响应名称'].delete(0, 'end')
    create.options['响应名称'].insert(0, 'Y,Z')
    create.create()
    first = app.getCurrentTable()
    frame = first.model.df
    for i in range(len(frame)):
        for name, value in [('Y', i+1), ('Z', 2*(i+1))]:
            first.model.setValueAt(str(value), i, frame.columns.get_loc(f'响应_{name}'))
    dialog = AnalyzeDOE(app)
    dialog.response.set('Z')
    dialog.analyze()
    assert dialog.result['response'] == 'Z'
    CreateDOE(app, ccd=True).create()
    dialog.analyze()
    assert '来源工作表已切换' in error.call_args.args[1]
    app.nb.select(app.sheetframes[next(name for name in app.sheets if app.sheets[name] is first)])
    assert app.deleteSheet()
    dialog.analyze()
    assert '来源工作表已关闭' in error.call_args.args[1]
    dialog.main.destroy()


def test_three_factor_plot_uses_fixed_factor_and_model(csv_app, monkeypatch):
    app, _ = csv_app
    error = Mock()
    monkeypatch.setattr('doe_dialog.messagebox.showerror', error)
    create = CreateDOE(app, ccd=True)
    create.factor_count.set('3')
    create.update_factor_rows()
    create.create()
    table = app.getCurrentTable()
    frame = table.model.df
    a = frame['编码_A'].to_numpy(float)
    b = frame['编码_B'].to_numpy(float)
    c = frame['编码_C'].to_numpy(float)
    values = 2+3*a-2*b+4*c+5*a*c+2*b*b
    for i, value in enumerate(values):
        table.model.setValueAt(str(value), i, frame.columns.get_loc('响应_Y'))
    dialog = AnalyzeDOE(app)
    dialog.analyze()
    dialog.fixed['C'].delete(0, 'end')
    dialog.fixed['C'].insert(0, '.5')
    dialog.plot()
    assert 'C=0.5' in table.pf.fig._suptitle.get_text()
    error.assert_not_called()
    dialog.main.destroy()
