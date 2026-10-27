"""叠加等高线真实 Tk：范围输入、可行交集、无交集提示与来源失效。"""
from unittest.mock import Mock

import numpy as np
import pytest

from doe_dialog import CreateDOE
from doe_overlay_dialog import OverlayContours
from test_csv_import import csv_app


def _make_ccd(app, monkeypatch):
    monkeypatch.setattr('worksheets.messagebox.askyesnocancel', lambda *a, **k: False)
    monkeypatch.setattr('worksheets.messagebox.askyesno', lambda *a, **k: True)
    create = CreateDOE(app, ccd=True)
    create.factor_count.set('3')
    create.update_factor_rows()
    create.options['响应名称'].delete(0, 'end')
    create.options['响应名称'].insert(0, 'Y,Z')
    create.create()
    table = app.getCurrentTable()
    frame = table.model.df
    a, b, c = (frame[f'编码_{name}'].to_numpy(float) for name in 'ABC')
    for name, values in (('Y', 10 + 2*a - b + c), ('Z', 20 - a + 3*b)):
        column = frame.columns.get_loc(f'响应_{name}')
        for row, value in enumerate(values):
            table.model.setValueAt(repr(float(value)), row, column)
    return table


def _set(dialog, name, low, high):
    chosen, low_entry, high_entry = dialog.rows[name]
    chosen.set(True)
    for entry, value in ((low_entry, low), (high_entry, high)):
        entry.delete(0, 'end')
        entry.insert(0, value)
    dialog._update_state()


def test_overlay_draws_two_response_contours_and_feasible_region(csv_app, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr('doe_overlay_dialog.messagebox.showerror', error)
    table = _make_ccd(app, monkeypatch)
    dialog = OverlayContours(app)
    assert str(dialog.draw_button['state']) == 'normal'
    _set(dialog, 'Y', '5', '15')
    _set(dialog, 'Z', '15', '25')
    dialog.draw()
    assert error.call_count == 0, error.call_args
    assert dialog.viewer is not None, dialog.status.get()
    result = dialog.last['result']
    np.testing.assert_allclose(result['z']['Y'], 10 + 2*result['xx'] - result['yy'],
                               atol=1e-9)
    expected = ((result['z']['Y'] >= 5) & (result['z']['Y'] <= 15) &
                (result['z']['Z'] >= 15) & (result['z']['Z'] <= 25))
    np.testing.assert_array_equal(result['feasible'], expected)
    assert '可行网格占比' in dialog.status.get()
    assert dialog.viewer.fig._suptitle.get_text().startswith('快照')
    dialog.close()
    assert dialog.viewer is None


def test_overlay_reports_an_empty_feasible_region(csv_app, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr('doe_overlay_dialog.messagebox.showerror', error)
    _make_ccd(app, monkeypatch)
    dialog = OverlayContours(app)
    _set(dialog, 'Y', '1000', '2000')
    _set(dialog, 'Z', '1000', '2000')
    dialog.draw()
    assert not dialog.last['result']['feasible'].any()
    assert '可行区域为空' in dialog.status.get()
    dialog.close()


def test_overlay_requires_two_ranges_and_different_factors(csv_app, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr('doe_overlay_dialog.messagebox.showerror', error)
    _make_ccd(app, monkeypatch)
    dialog = OverlayContours(app)
    dialog.rows['Z'][0].set(False)
    dialog._update_state()
    assert str(dialog.draw_button['state']) == 'disabled'
    assert '至少需要两个响应' in dialog.status.get()
    dialog.rows['Z'][0].set(True)
    _set(dialog, 'Y', '0', '100')
    _set(dialog, 'Z', '0', '100')
    dialog.factor_y.set(dialog.factor_x.get())
    dialog._update_state()
    assert str(dialog.draw_button['state']) == 'disabled'
    assert '两个不同的因子' in dialog.status.get()
    dialog.close()


def test_overlay_invalidates_on_source_change_and_metadata_change(csv_app, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr('doe_overlay_dialog.messagebox.showerror', error)
    table = _make_ccd(app, monkeypatch)
    dialog = OverlayContours(app)
    _set(dialog, 'Y', '0', '100')
    _set(dialog, 'Z', '0', '100')
    dialog.draw()
    assert dialog.last is not None
    dialog.fixed['C'].delete(0, 'end')
    dialog.fixed['C'].insert(0, '0.5')
    dialog._update_state()
    assert dialog.last is None
    assert '重新绘图' in dialog.status.get()
    _set(dialog, 'Y', '0', '100')
    _set(dialog, 'Z', '0', '100')
    dialog.draw()
    table.doe_metadata['design']['seed'] = 999
    dialog.draw()
    assert '重新打开' in dialog.status.get()
    dialog.close()

