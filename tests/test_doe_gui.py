from unittest.mock import Mock

import numpy as np

from doe_dialog import AnalyzeDOE, CreateDOE
from test_csv_import import csv_app


def test_doe_create_analyze_save_load_and_source_binding(csv_app, tmp_path, monkeypatch):
    app, _ = csv_app
    error = Mock()
    monkeypatch.setattr('doe_dialog.messagebox.showerror', error)
    monkeypatch.setattr('worksheets.messagebox.askyesnocancel', lambda *a, **k: False)
    monkeypatch.setattr('worksheets.messagebox.askyesno', lambda *a, **k: True)
    names = list(app.sheets)
    cancelled = CreateDOE(app)
    cancelled.main.destroy()
    assert list(app.sheets) == names
    create = CreateDOE(app)
    create.preview()
    assert '4 次运行' in create.preview_text.get()
    create.create()
    table = app.getCurrentTable()
    frame = table.model.df
    a, b = frame['设定_A'], frame['设定_B']
    values = 50 + 3*(2*a-1) - 2*(2*b-1) + 4*(2*a-1)*(2*b-1)
    for row, value in enumerate(values):
        table.model.setValueAt(str(value), row, frame.columns.get_loc('响应_Y'))
    dialog = AnalyzeDOE(app)
    dialog.analyze()
    assert dialog.result is not None and dialog.result['df'] == 0
    dialog.plot()
    assert table.pf is not None and table.pf.table is table
    target = tmp_path / 'doe.dexpl'
    assert app._save_project(target)
    assert app.load_file(target)
    dialog.plot()
    assert '来源工作表已关闭' in error.call_args.args[1]
    error.reset_mock()
    dialog.main.destroy()
    app.getCurrentTable().model.df.loc[0, '响应_Y'] += 1
    restored = AnalyzeDOE(app)
    restored.analyze()
    assert restored.result is not None
    app.nb.select(app.sheetframes[names[0]])
    restored.analyze()
    error.assert_called_once()
    restored.main.destroy()


def test_replicates_show_anova(csv_app, monkeypatch):
    app, _ = csv_app
    error = Mock()
    monkeypatch.setattr('doe_dialog.messagebox.showerror', error)
    create = CreateDOE(app)
    create.options['重复数'].delete(0, 'end')
    create.options['重复数'].insert(0, '2')
    create.create()
    table = app.getCurrentTable()
    frame = table.model.df
    for i in range(len(frame)):
        row = frame.iloc[i]
        a, b = 2*row['设定_A']-1, 2*row['设定_B']-1
        y = 50+3*a-2*b+4*a*b+(-1 if row['重复'] == 1 else 1)
        table.model.setValueAt(str(y), i, frame.columns.get_loc('响应_Y'))
    dialog = AnalyzeDOE(app)
    dialog.analyze()
    assert dialog.result['inference'] is not None
    assert [dialog.tabs.tab(tab, 'text') for tab in dialog.tabs.tabs()] == [
        '系数与效应', '模型', '方差分析', '拟合与残差']
    error.assert_not_called()
    dialog.main.destroy()


def test_three_factor_pairs_multiple_responses_and_deleted_source(csv_app, monkeypatch):
    app, _ = csv_app
    error = Mock()
    monkeypatch.setattr('doe_dialog.messagebox.showerror', error)
    monkeypatch.setattr('worksheets.messagebox.askyesno', lambda *a, **k: True)
    create = CreateDOE(app)
    for widget, value in zip(create.fields[2], ('C', '0', '1', '')):
        widget.insert(0, value)
    create.options['响应名称'].delete(0, 'end')
    create.options['响应名称'].insert(0, 'Y,Z')
    create.options['中心点数'].delete(0, 'end')
    create.options['中心点数'].insert(0, '2')
    create.create()
    table = app.getCurrentTable()
    frame = table.model.df
    for i in range(len(frame)):
        row = frame.iloc[i]
        a, b, c = (2*row[f'设定_{factor}']-1 for factor in 'ABC')
        y = 1000 if row['点类型'] == 'center' else 10+2*a-3*b+4*c+5*a*c
        for response, value in (('Y', y), ('Z', 2*y)):
            table.model.setValueAt(str(value), i, frame.columns.get_loc(f'响应_{response}'))
    dialog = AnalyzeDOE(app)
    dialog.analyze()
    for first, second, expected in [
        ('A', 'B', [[11, 15], [5, 9]]),
        ('A', 'C', [[9, 3], [7, 21]]),
        ('B', 'C', [[9, 3], [17, 11]]),
    ]:
        dialog.factor_x.set(first)
        dialog.factor_y.set(second)
        dialog.plot()
        axes = table.pf.fig.axes[1]
        assert axes.get_title() == f'{first} × {second} 交互图'
        np.testing.assert_allclose([line.get_ydata() for line in axes.lines], expected)
    dialog.response.set('Z')
    dialog.analyze()
    assert dialog.result['response'] == 'Z'
    np.testing.assert_allclose(dialog.result['coefficients'][:4], [20, 4, -6, 8], atol=1e-12)
    dialog.factor_y.set('B')
    dialog.factor_x.set('B')
    dialog.plot()
    assert '两个不同' in error.call_args.args[1]
    assert app.deleteSheet()
    dialog.analyze()
    assert '来源工作表已关闭' in error.call_args.args[1]
    dialog.plot()
    assert '来源工作表已关闭' in error.call_args.args[1]
    dialog.main.destroy()


def test_invalid_create_preserves_sheet_and_two_designs_are_independent(csv_app, monkeypatch):
    app, _ = csv_app
    error = Mock()
    monkeypatch.setattr('doe_dialog.messagebox.showerror', error)
    before = list(app.sheets)
    bad = CreateDOE(app)
    bad.options['重复数'].delete(0, 'end')
    bad.options['重复数'].insert(0, '0')
    bad.create()
    assert list(app.sheets) == before
    assert error.call_count == 1
    bad.main.destroy()
    CreateDOE(app).create()
    first = app.getCurrentTable()
    CreateDOE(app).create()
    second = app.getCurrentTable()
    assert first is not second and first.doe_metadata is not second.doe_metadata
    first.model.setValueAt('7', 0, first.model.df.columns.get_loc('响应_Y'))
    assert second.model.df['响应_Y'].isna().all()
