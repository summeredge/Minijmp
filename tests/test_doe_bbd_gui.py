"""Box-Behnken 的真实 Tk 创建、分析、图形、保存重开与复制。"""
from unittest.mock import Mock

import numpy as np
from doe_dialog import AnalyzeDOE, CreateDOE
from test_csv_import import csv_app


def _fill(create, rows):
    for field, value in rows:
        field.delete(0, 'end')
        field.insert(0, value)


def test_bbd_create_analyze_plot_and_project_roundtrip(csv_app, tmp_path, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr('doe_dialog.messagebox.showerror', error)
    monkeypatch.setattr('worksheets.messagebox.askyesnocancel', lambda *a, **k: False)
    monkeypatch.setattr('worksheets.messagebox.askyesno', lambda *a, **k: True)

    cancelled = CreateDOE(app, bbd=True)
    before = list(app.sheets)
    cancelled.main.destroy()
    assert list(app.sheets) == before

    create = CreateDOE(app, bbd=True)
    assert create.factor_count.get() == '3'
    _fill(create, [(create.fields[0][1], '10'), (create.fields[0][2], '20'),
                   (create.fields[1][1], '0'), (create.fields[1][2], '1'),
                   (create.fields[2][1], '-1'), (create.fields[2][2], '3')])
    create.preview()
    assert '边点 12' in create.preview_text.get()
    assert '中心点 3' in create.preview_text.get()
    create.create()
    assert list(app.sheets) != before

    table = app.getCurrentTable()
    frame = table.model.df
    assert len(frame) == 15
    assert set(frame['点类型']) == {'edge', 'center'}
    metadata = table.doe_metadata
    saved = frame[['设定_A', '设定_B', '设定_C', '编码_A', '编码_B', '编码_C']].to_dict('records')
    a = frame['编码_A'].to_numpy(float)
    b = frame['编码_B'].to_numpy(float)
    c = frame['编码_C'].to_numpy(float)
    values = 40 + 3*a - 2*b + c + 4*a*b - 1.5*b*c + 5*a**2 + 2*b**2 - 3*c**2
    for i, value in enumerate(values):
        table.model.setValueAt(str(value), i, frame.columns.get_loc('响应_Y'))

    dialog = AnalyzeDOE(app)
    dialog.analyze()
    assert dialog.result is not None
    assert dialog.result['design'].spec.design_type == 'box_behnken'
    coefficients = dict(zip(dialog.result['names'], dialog.result['coefficients']))
    assert abs(coefficients['截距'] - 40) < 1e-8
    assert abs(coefficients['A*B'] - 4) < 1e-8
    assert abs(coefficients['B*C'] + 1.5) < 1e-8
    assert abs(coefficients['A²'] - 5) < 1e-8
    tabs = [dialog.tabs.tab(tab, 'text') for tab in dialog.tabs.tabs()]
    assert '诊断可用性' in tabs
    assert '项平方和' in tabs
    dialog.plot()
    assert len(table.pf.fig.axes) == 4
    dialog.main.destroy()

    target = tmp_path / 'bbd.dexpl'
    assert app._save_project(target)
    assert app.load_file(target)
    restored = app.getCurrentTable()
    assert restored.doe_metadata['design']['design_type'] == 'box_behnken'
    assert restored.doe_metadata['schema_version'] == 2
    assert restored.model.df[['设定_A', '设定_B', '设定_C', '编码_A',
                              '编码_B', '编码_C']].to_dict('records') == saved
    reopened = AnalyzeDOE(app)
    reopened.analyze()
    assert reopened.result is not None
    assert abs(dict(zip(reopened.result['names'],
                        reopened.result['coefficients']))['A*B'] - 4) < 1e-8
    reopened.main.destroy()

    copied = app.copySheet()
    assert copied.doe_metadata == restored.doe_metadata
    assert copied.doe_metadata is not restored.doe_metadata
    copy_dialog = AnalyzeDOE(app)
    copy_dialog.analyze()
    assert copy_dialog.result is not None
    copy_dialog.main.destroy()
    error.assert_not_called()


def test_bbd_rejects_missing_response_in_analysis(csv_app, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr('doe_dialog.messagebox.showerror', error)
    create = CreateDOE(app, bbd=True)
    create.create()
    dialog = AnalyzeDOE(app)
    dialog.analyze()
    assert dialog.result is None
    assert '缺失' in error.call_args.args[1]
    dialog.main.destroy()


def test_bbd_term_omission_reports_unknown_terms(csv_app, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr('doe_dialog.messagebox.showerror', error)
    create = CreateDOE(app, bbd=True)
    create.create()
    table = app.getCurrentTable()
    frame = table.model.df
    for i in range(len(frame)):
        table.model.setValueAt('1', i, frame.columns.get_loc('响应_Y'))
    dialog = AnalyzeDOE(app)
    dialog.omit_terms.set('A*Z')
    dialog.analyze()
    assert '排除项' in error.call_args.args[1]
    dialog.main.destroy()
