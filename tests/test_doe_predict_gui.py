"""响应面预测窗口：真实 Tk 入口、快照一致性、分类水平与过期模型。"""
from unittest.mock import Mock

import numpy as np
import pytest

from doe_dialog import CreateDOE
from doe_predict_dialog import PredictRSM
from test_csv_import import csv_app
from test_doe_predict import _custom_interval_design


def _fill_response(table, values):
    frame = table.model.df
    column = frame.columns.get_loc(f'响应_{"Y"}')
    for row, value in enumerate(values):
        table.model.setValueAt(repr(float(value)), row, column)


def _create(app, monkeypatch, **kwargs):
    monkeypatch.setattr('worksheets.messagebox.askyesnocancel', lambda *a, **k: False)
    monkeypatch.setattr('worksheets.messagebox.askyesno', lambda *a, **k: True)
    create = CreateDOE(app, **kwargs)
    create.create()
    return app.getCurrentTable()


def test_prediction_dialog_matches_single_point_analysis(csv_app, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr('doe_predict_dialog.messagebox.showerror', error)
    table = _create(app, monkeypatch, bbd=True)
    frame = table.model.df
    _fill_response(table, 10 + 2*frame['编码_A'] - frame['编码_B'] + 4*frame['编码_C'])
    dialog = PredictRSM(app)
    dialog.entries['A'].delete(0, 'end')
    dialog.entries['A'].insert(0, '1')
    dialog.predict()
    assert error.call_count == 0, error.call_args
    values = dialog.block.table.values
    prediction = next(row[1] for row in values if row[0] == '预测响应')
    assert prediction == pytest.approx(12.0, abs=1e-9)
    assert '快照' in dialog.status.get()
    dialog.main.destroy()


def test_prediction_rejects_value_outside_design_range(csv_app, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr('doe_predict_dialog.messagebox.showerror', error)
    table = _create(app, monkeypatch, bbd=True)
    _fill_response(table, np.zeros(len(table.model.df)))
    dialog = PredictRSM(app)
    dialog.entries['B'].delete(0, 'end')
    dialog.entries['B'].insert(0, '5')
    dialog.predict()
    assert '超出' in dialog.status.get()
    dialog.main.destroy()


def test_prediction_uses_selected_categorical_level(csv_app, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr('doe_predict_dialog.messagebox.showerror', error)
    monkeypatch.setattr('worksheets.messagebox.askyesnocancel', lambda *a, **k: False)
    monkeypatch.setattr('worksheets.messagebox.askyesno', lambda *a, **k: True)
    create = CreateDOE(app, ccd=True)
    create.fields[2][4].insert(0, '甲;乙')
    create.factor_count.set('3')
    create.update_factor_rows()
    create.create()
    table = app.getCurrentTable()
    frame = table.model.df
    second = (frame['设定_C'] == '乙').to_numpy(float)
    _fill_response(table, 5 + 3*frame['编码_A'] + 9*second)
    dialog = PredictRSM(app)
    assert dialog.entries['C'].get() == '甲'
    dialog.entries['C'].set('乙')
    dialog.entries['A'].delete(0, 'end')
    dialog.entries['A'].insert(0, '1')
    dialog.predict()
    assert error.call_count == 0, error.call_args
    assert any(row[1] == 17.0 for row in dialog.block.table.values)
    dialog.main.destroy()


def test_prediction_detects_changed_design_metadata(csv_app, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr('doe_predict_dialog.messagebox.showerror', error)
    table = _create(app, monkeypatch, bbd=True)
    _fill_response(table, np.arange(len(table.model.df), dtype=float))
    dialog = PredictRSM(app)
    metadata = table.doe_metadata
    metadata['design']['seed'] = 999
    dialog.predict()
    assert '重新打开' in dialog.status.get()
    dialog.main.destroy()


def test_prediction_rejects_non_doe_sheet(csv_app, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr('doe_predict_dialog.messagebox.showerror', error)
    PredictRSM(app)
    assert error.called
    assert 'DOE' in error.call_args.args[1]


def test_prediction_roundtrips_through_a_saved_project(csv_app, tmp_path, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr('doe_predict_dialog.messagebox.showerror', error)
    table = _create(app, monkeypatch, bbd=True)
    frame = table.model.df
    _fill_response(table, 10 + 2*frame['编码_A'] - frame['编码_B'] + 4*frame['编码_C'])
    target = tmp_path / 'predict.dexpl'
    assert app._save_project(target)
    assert app.load_file(target)
    dialog = PredictRSM(app)
    dialog.entries['C'].delete(0, 'end')
    dialog.entries['C'].insert(0, '1')
    dialog.predict()
    assert error.call_count == 0, error.call_args
    assert next(row[1] for row in dialog.block.table.values
                if row[0] == '预测响应') == pytest.approx(14.0, abs=1e-9)
    dialog.main.destroy()


def test_prediction_gui_intervals_and_response_snapshot_refresh(csv_app, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr('doe_predict_dialog.messagebox.showerror', error)
    frame, metadata = _custom_interval_design()
    original_response = frame['Y'].copy(deep=True)
    app.addSheet('自定义区间设计', frame, {'doe': metadata})
    dialog = PredictRSM(app)
    dialog.confidence.set('90%')
    dialog.interval_side.set('单侧下限')
    dialog.predict()
    assert error.call_count == 0, error.call_args
    values = dialog.block.table.values
    lower_ci = next(row[1] for row in values if row[0] == '拟合均值 CI 下限')
    lower_pi = next(row[1] for row in values if row[0] == '单次观测 PI 下限')
    old_snapshot = next(row[1] for row in values if row[0] == '快照')
    se_fit = next(row[1] for row in values if row[0] == 'SE Fit')
    assert float(se_fit) > 0
    assert float(lower_pi) < float(lower_ci)
    assert 'df=3' in next(row[1] for row in values if row[0] == '区间状态')

    previous_block = dialog.block
    app.getCurrentTable().model.df['Y'] *= 2
    dialog.predict()
    values = dialog.block.table.values
    new_snapshot = next(row[1] for row in values if row[0] == '快照')
    new_lower_ci = next(row[1] for row in values if row[0] == '拟合均值 CI 下限')
    assert new_snapshot != old_snapshot
    assert float(new_lower_ci) == pytest.approx(2*float(lower_ci), rel=1e-9)
    assert not previous_block.winfo_exists()
    assert error.call_count == 0, error.call_args

    failed_block = dialog.block
    app.getCurrentTable().model.df['Y'] = [None] * len(frame)
    dialog.predict()
    assert dialog.block is None
    assert not failed_block.winfo_exists()
    assert '预测失败' in dialog.status.get()

    app.getCurrentTable().model.df['Y'] = original_response
    dialog.predict()
    source_block = dialog.block
    app.addSheet('其他工作表', frame.copy(deep=True), {})
    dialog.predict()
    assert dialog.block is None
    assert not source_block.winfo_exists()
    assert '来源工作表已切换' in dialog.status.get()
    dialog.main.destroy()

