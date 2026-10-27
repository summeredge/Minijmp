import math
from unittest.mock import Mock

import numpy as np
import pytest

from pandas.testing import assert_frame_equal

from doe_dialog import CreateDOE
from doe_optimize_dialog import OptimizeRSM
from test_csv_import import csv_app


def _make_ccd(app, two_responses=True):
    create = CreateDOE(app, ccd=True)
    create.fields[0][0].delete(0, 'end')
    create.fields[0][0].insert(0, '温度')
    create.fields[0][1].delete(0, 'end')
    create.fields[0][1].insert(0, '0.1')
    create.fields[0][2].delete(0, 'end')
    create.fields[0][2].insert(0, '0.2')
    create.fields[0][3].delete(0, 'end')
    create.fields[0][3].insert(0, '°C')
    create.fields[1][0].delete(0, 'end')
    create.fields[1][0].insert(0, '压力')
    create.fields[1][1].delete(0, 'end')
    create.fields[1][1].insert(0, '65.3')
    create.fields[1][2].delete(0, 'end')
    create.fields[1][2].insert(0, '68.3')
    create.fields[1][3].delete(0, 'end')
    create.fields[1][3].insert(0, 'MPa')
    if two_responses:
        create.options['响应名称'].delete(0, 'end')
        create.options['响应名称'].insert(0, '收率,强度')
    create.create()
    table = app.getCurrentTable()
    frame = table.model.df
    a = frame['编码_A'].to_numpy(dtype=float)
    b = frame['编码_B'].to_numpy(dtype=float)
    responses = {'收率': 40 + 3*a - 2*b + 4*a*b + 5*a*a - 1.5*b*b,
                 '强度': 10 - (a - .3)**2 - 2*(b + .4)**2}
    names = ['收率', '强度'] if two_responses else ['Y']
    for index, name in enumerate(names):
        values = responses[name] if name in responses else 2 + 3*a - 2*b + a*b
        column = frame.columns.get_loc(f'响应_{name}')
        for row, value in enumerate(values):
            table.model.setValueAt(repr(float(value)), row, column)
    return table


def _set_multi_objectives(dialog):
    dialog.low.set('0')
    dialog.high.set('100')
    dialog.weight.set('1')
    dialog._response_changed()
    dialog.response_list.selection_clear(0, 'end')
    dialog.response_list.selection_set(0, 1)
    dialog.response_list.activate(1)
    dialog._select_response()
    dialog.low.set('0')
    dialog.high.set('20')
    dialog.weight.set('1')
    dialog._response_changed()
    dialog._update_run_state()


def _set_decimal_bounds(dialog):
    dialog.bound_entries['A'][0].delete(0, 'end')
    dialog.bound_entries['A'][0].insert(0, '0.12')
    dialog.bound_entries['A'][1].delete(0, 'end')
    dialog.bound_entries['A'][1].insert(0, '0.18')
    dialog.bound_entries['B'][0].delete(0, 'end')
    dialog.bound_entries['B'][0].insert(0, '65.8')
    dialog.bound_entries['B'][1].delete(0, 'end')
    dialog.bound_entries['B'][1].insert(0, '67.8')
    dialog._bounds_changed()
    dialog._update_run_state()


def test_ccd_optimize_reopens_and_recomputes(csv_app, tmp_path, monkeypatch):
    app, _ = csv_app
    monkeypatch.setattr('worksheets.messagebox.askyesnocancel', lambda *a, **k: False)
    monkeypatch.setattr('worksheets.messagebox.askyesno', lambda *a, **k: True)
    source = _make_ccd(app)
    original = source.model.df.copy(deep=True)
    dialog = OptimizeRSM(app)
    for entry in dialog.bound_entries['A'][:2]:
        entry.delete(0, 'end')
        entry.insert(0, '0.15')
    dialog._bounds_changed()
    fixed_bounds, fixed_actual = dialog._read_bounds()
    assert fixed_actual['A'] == (0.15, 0.15)
    assert fixed_bounds['A'][0] == fixed_bounds['A'][1]
    _set_decimal_bounds(dialog)
    _set_multi_objectives(dialog)
    assert str(dialog.run_button['state']) == 'normal'
    dialog.optimize()
    assert dialog.last['result']['success']
    assert dialog.result_block.table.title == '优化建议与响应预测'
    assert dialog.candidate_block.table.title == '搜索候选'
    assert any(row[1] == 'A 温度' and '°C' in row[3]
               for row in dialog.result_block.table.display)
    assert any(row[1] == '收率' and row[6] != '' for row in dialog.result_block.table.display)
    assert any(row[1] == '强度' and row[6] != '' for row in dialog.result_block.table.display)
    assert all(-1 <= value <= 1 for value in dialog.last['result']['best']['coded'].values())
    assert all(0 <= value <= 1
               for value in dialog.last['result']['best']['desirabilities'].values())
    assert_frame_equal(source.model.df, original)

    dialog.plot()
    assert dialog.viewer is not None, dialog.status.get()
    assert len(dialog.viewer.fig.axes) == 2
    first = dialog.last['result']['best']['coded']
    predictions = dialog.last['result']['best']['predictions'].copy()
    snapshot_id = dialog.last['result']['snapshot_id']
    target = tmp_path / 'doe4.dexpl'
    assert app._save_project(target)
    dialog.close()
    assert app.load_file(target)

    reopened = OptimizeRSM(app)
    _set_decimal_bounds(reopened)
    _set_multi_objectives(reopened)
    reopened.optimize()
    assert reopened.last['result']['best']['coded'] == first
    assert reopened.last['result']['best']['predictions'] == predictions
    assert reopened.last['result']['snapshot_id'] == snapshot_id
    reopened.close()


def test_multiresponse_target_difference_is_shown_for_each_response(csv_app):
    app, _ = csv_app
    source = _make_ccd(app)
    frame = source.model.df
    coded_a = frame['编码_A'].to_numpy(dtype=float)
    for name in ('收率', '强度'):
        column = frame.columns.get_loc(f'响应_{name}')
        for row, value in enumerate(coded_a):
            source.model.setValueAt(repr(float(value)), row, column)

    dialog = OptimizeRSM(app)
    configs = (
        (0, '逼近目标', -1, 0, 1, 1, 10, 1),
        (1, '最大化', -1, '', 1, 1, 1, 12),
    )
    for index, mode, low, target, high, power_low, power_high, weight in configs:
        dialog.response_list.selection_clear(0, 'end')
        dialog.response_list.selection_set(index)
        dialog.response_list.activate(index)
        dialog._select_response()
        dialog.mode.set(mode)
        dialog._update_shape_controls()
        dialog.low.set(str(low))
        dialog.target.set(str(target))
        dialog.high.set(str(high))
        dialog.power_low.set(str(power_low))
        dialog.power_high.set(str(power_high))
        dialog.weight.set(str(weight))
        dialog._response_changed()

    dialog.response_list.selection_clear(0, 'end')
    dialog.response_list.selection_set(0, 1)
    dialog.response_list.activate(1)
    dialog._select_response()
    dialog._update_run_state()
    assert dialog.response_list.curselection() == (0, 1)
    assert str(dialog.run_button['state']) == 'normal'
    dialog.optimize()

    assert dialog.last['result']['success']
    best = dialog.last['result']['best']
    expected = abs(best['predictions']['收率'] - 0)
    target_values = next(row for row in dialog.result_block.table.values
                         if row[1] == '收率')
    target_display = next(row for row in dialog.result_block.table.display
                          if row[1] == '收率')
    assert math.isfinite(target_values[5])
    assert target_values[5] == pytest.approx(expected)
    assert float(target_display[5]) == pytest.approx(expected)
    assert '超出有限表示范围' not in target_display[5]

    dialog.response_list.selection_clear(0, 'end')
    dialog.response_list.selection_set(0)
    dialog.response_list.activate(0)
    dialog._select_response()
    dialog.optimize()
    single = dialog.last['result']['best']
    single_row = next(row for row in dialog.result_block.table.values
                      if row[1] == '收率')
    assert single_row[5] == pytest.approx(single['target_difference'])
    dialog.close()


def test_optimizer_binds_source_and_invalidates_changed_snapshot(csv_app, tmp_path, monkeypatch):
    app, _ = csv_app
    monkeypatch.setattr('worksheets.messagebox.askyesno', lambda *a, **k: True)
    monkeypatch.setattr('worksheets.messagebox.askyesnocancel', lambda *a, **k: False)
    source = _make_ccd(app, two_responses=False)
    dialog = OptimizeRSM(app)
    dialog.low.set('0')
    dialog.high.set('100')
    dialog._response_changed()
    dialog._update_run_state()
    copied = app.copySheet()
    dialog.optimize()
    assert '来源工作表已切换' in dialog.status.get()

    app.nb.select(app.sheetframes[next(name for name, table in app.sheets.items()
                                       if table is source)])
    dialog.optimize()
    assert dialog.last is not None
    snapshot_id = dialog.last['result']['snapshot_id']
    column = source.model.df.columns.get_loc('响应_Y')
    source.model.setValueAt(str(source.model.df.iloc[0, column] + .5), 0, column)
    dialog.plot()
    assert '来源数据已更新' in dialog.status.get()
    dialog.optimize()
    assert dialog.last is not None
    assert dialog.last['result']['snapshot_id'] != snapshot_id

    app.nb.select(app.sheetframes[next(name for name, table in app.sheets.items()
                                       if table is source)])
    assert app.deleteSheet()
    dialog.optimize()
    assert '来源工作表已关闭' in dialog.status.get()
    dialog.close()
    assert copied is not source

    reopened_source = OptimizeRSM(app)
    project = tmp_path / 'replacement.dexpl'
    assert app._save_project(project)
    assert app.load_file(project)
    reopened_source.optimize()
    assert '来源工作表已关闭' in reopened_source.status.get()
    reopened_source.close()


def test_optimizer_rejects_non_ccd_and_disables_invalid_bounds(csv_app, monkeypatch):
    app, _ = csv_app
    error = Mock()
    monkeypatch.setattr('doe_optimize_dialog.messagebox.showerror', error)
    missing = OptimizeRSM(app)
    assert not hasattr(missing, 'main')
    assert error.call_count == 1

    CreateDOE(app).create()
    wrong_type = OptimizeRSM(app)
    assert not hasattr(wrong_type, 'main')
    assert error.call_count == 2

    source = _make_ccd(app, two_responses=False)
    dialog = OptimizeRSM(app)
    dialog.bound_entries['A'][0].delete(0, 'end')
    dialog.bound_entries['A'][0].insert(0, '-0.1')
    dialog._bounds_changed()
    assert str(dialog.run_button['state']) == 'disabled'
    assert 'low/high' in dialog.status.get()
    dialog.close()


def test_bbd_optimizer_reaches_the_analytic_optimum(csv_app, monkeypatch):
    app, _ = csv_app
    monkeypatch.setattr('worksheets.messagebox.askyesno', lambda *a, **k: True)
    monkeypatch.setattr('worksheets.messagebox.askyesnocancel', lambda *a, **k: False)
    create = CreateDOE(app, bbd=True)
    create.create()
    table = app.getCurrentTable()
    frame = table.model.df
    a, b, c = (frame[f'编码_{name}'].to_numpy(float) for name in 'ABC')
    values = 7 - (a - .25)**2 - 2*(b + .5)**2 - .5*(c + .2)**2
    column = frame.columns.get_loc('响应_Y')
    for row, value in enumerate(values):
        table.model.setValueAt(repr(float(value)), row, column)
    dialog = OptimizeRSM(app)
    dialog.high.set('100')
    dialog.low.set('-100')
    dialog._response_changed()
    dialog.optimize()
    assert dialog.last is not None, dialog.status.get()
    best = dialog.last['result']['best']
    assert best['coded']['A'] == pytest.approx(.25, abs=1e-4)
    assert best['coded']['B'] == pytest.approx(-.5, abs=1e-4)
    assert best['coded']['C'] == pytest.approx(-.2, abs=1e-4)
    assert dialog.last['result']['global_optimum_guaranteed'] is False
    dialog.plot()
    assert dialog.viewer is not None, dialog.status.get()
    dialog.close()


@pytest.mark.parametrize('offset', [11, 23])
def test_blocked_optimizer_contour_uses_reference_block(csv_app, monkeypatch, offset):
    app, _ = csv_app
    monkeypatch.setattr('worksheets.messagebox.askyesno', lambda *a, **k: True)
    monkeypatch.setattr('worksheets.messagebox.askyesnocancel', lambda *a, **k: False)
    create = CreateDOE(app, ccd=True)
    create.ccd_type.set('CCC')
    create.ccd_blocks.set('2')
    create.create()
    table = app.getCurrentTable()
    frame = table.model.df
    a = frame['编码_A'].to_numpy(dtype=float)
    b = frame['编码_B'].to_numpy(dtype=float)
    second_block = (frame['区组'].to_numpy(dtype=float) == 2).astype(float)
    response = 40 - (a - .25)**2 - 2*(b + .5)**2 + offset*second_block
    column = frame.columns.get_loc('响应_Y')
    for row, value in enumerate(response):
        table.model.setValueAt(repr(float(value)), row, column)

    dialog = OptimizeRSM(app)
    dialog.low.set('-100')
    dialog.high.set('100')
    dialog._response_changed()
    dialog.optimize()
    assert dialog.last is not None, dialog.status.get()

    from matplotlib.axes import Axes
    original_contourf = Axes.contourf
    surfaces = []

    def capture_contour(ax, *args, **kwargs):
        surfaces.append(tuple(np.asarray(values) for values in args[:3]))
        return original_contourf(ax, *args, **kwargs)

    monkeypatch.setattr(Axes, 'contourf', capture_contour)
    try:
        dialog.plot()
        assert dialog.viewer is not None, dialog.status.get()
        xx, yy, zz = surfaces[0]
        expected = 40 - (xx - .25)**2 - 2*(yy + .5)**2
        np.testing.assert_allclose(zz, expected, rtol=1e-12, atol=1e-12)
        best = dialog.last['result']['best']
        assert best['predictions']['Y'] == pytest.approx(
            40 - (best['coded']['A'] - .25)**2 - 2*(best['coded']['B'] + .5)**2)
        assert '参考区组 1' in dialog.viewer.fig._suptitle.get_text()
    finally:
        dialog.close()
