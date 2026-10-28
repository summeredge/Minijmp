"""PB 创建、分析和工程生命周期的真实 Tk 路径。"""
from unittest.mock import Mock

import numpy as np
import pytest

from doe_dialog import AnalyzeDOE, CreateDOE
from test_csv_import import csv_app


def test_pb_create_analyze_plot_save_copy_and_reanalyze(csv_app, tmp_path, monkeypatch):
    app, _ = csv_app
    error = Mock()
    monkeypatch.setattr('doe_dialog.messagebox.showerror', error)
    monkeypatch.setattr('worksheets.messagebox.askyesno', lambda *a, **k: True)
    monkeypatch.setattr('worksheets.messagebox.askyesnocancel', lambda *a, **k: False)
    before = list(app.sheets)
    cancelled = CreateDOE(app, pb=True)
    cancelled.main.destroy()
    assert list(app.sheets) == before
    create = CreateDOE(app, pb=True)
    create.preview()
    assert '12 次运行' in create.preview_text.get()
    preview = next(child for child in create.main.winfo_children() if child.winfo_class() == 'Toplevel')
    tree = next(child for child in preview.winfo_children() if child.winfo_class() == 'Treeview')
    assert len(tree.get_children()) == 12
    assert {'标准序', '运行序', '点类型', '重复', '设定_F1'} <= set(tree['columns'])
    assert list(app.sheets) == before
    create.create()
    table = app.getCurrentTable()
    frame = table.model.df
    for i in range(len(frame)):
        row = frame.iloc[i]
        y = 10 + 2 * (2 * row['设定_F1'] - 1) - 3 * (2 * row['设定_F2'] - 1)
        table.model.setValueAt(str(y), i, frame.columns.get_loc('响应_Y'))
    dialog = AnalyzeDOE(app)
    dialog.analyze()
    assert dialog.pb and dialog.result is not None
    np.testing.assert_allclose(dialog.result['coefficients'], [10, 2, -3, 0], atol=1e-12)
    assert '混杂投影' in [dialog.tabs.tab(tab, 'text') for tab in dialog.tabs.tabs()]
    dialog.plot()
    assert table.pf is not None
    frame.loc[0, '响应_Y'] += 1
    dialog.analyze()
    assert dialog.result['inference'] is not None
    dialog.plot()
    assert table.pf.fig.axes[5].get_title() == '残差正态概率图'
    from scipy import stats
    pareto = table.pf.fig.axes[3]
    np.testing.assert_allclose([bar.get_width() for bar in pareto.patches],
                               sorted(abs(t) for t in dialog.result['inference']['t'][1:]))
    assert any(np.allclose(line.get_xdata(), stats.t.ppf(.975, dialog.result['df'])) for line in pareto.lines)
    path = tmp_path / 'pb.dexpl'
    assert app._save_project(path) and app.load_file(path)
    dialog.plot()
    assert '来源工作表已关闭' in error.call_args.args[1]
    error.reset_mock()
    dialog.main.destroy()
    restored = app.getCurrentTable()
    duplicate = app.copySheet()
    assert duplicate.doe_metadata == restored.doe_metadata
    again = AnalyzeDOE(app)
    again.analyze()
    assert again.result is not None
    duplicate.model.df.loc[0, '响应_Y'] += 1
    again.plot()
    assert '重新分析' in error.call_args.args[1]
    again.main.destroy()


def test_dsd_mixed_create_preview_and_persistence(csv_app, tmp_path, monkeypatch):
    app, _ = csv_app
    error = Mock()
    monkeypatch.setattr('doe_dialog.messagebox.showerror', error)
    monkeypatch.setattr('worksheets.messagebox.askyesno', lambda *a, **k: True)
    create = CreateDOE(app, dsd=True)
    create.factor_count.set('5')
    create.update_factor_rows()
    create.fields[4][4].insert(0, '甲;乙')
    create.options['响应名称'].delete(0, 'end')
    create.options['响应名称'].insert(0, 'Y,Z')
    create.preview()
    assert '14 次运行' in create.preview_text.get()
    assert '甲 / 乙' in create.preview_text.get()
    preview = next(child for child in create.main.winfo_children() if child.winfo_class() == 'Toplevel')
    tree = next(child for child in preview.winfo_children() if child.winfo_class() == 'Treeview')
    assert len(tree.get_children()) == 14 and '设定_F5' in tree['columns']
    create.create()
    table = app.getCurrentTable()
    assert set(table.model.df['设定_F5']) == {'甲', '乙'}
    assert sum(table.model.df['点类型'] == 'pseudo_center') == 2
    for i in range(len(table.model.df)):
        row = table.model.df.iloc[i]
        y = 10 + 2 * (2 * row['设定_F1'] - 1) + (1 if row['设定_F5'] == '乙' else -1) + i % 3
        table.model.setValueAt(str(y), i, table.model.df.columns.get_loc('响应_Y'))
        table.model.setValueAt(str(2*y), i, table.model.df.columns.get_loc('响应_Z'))
    dialog = AnalyzeDOE(app, screening=True)
    dialog.analyze()
    assert dialog.result is not None and dialog.result['inference'] is not None
    assert '方差分析' in [dialog.tabs.tab(tab, 'text') for tab in dialog.tabs.tabs()]
    dialog.plot()
    assert table.pf is not None and len(table.pf.fig.axes) == 4
    widths = [bar.get_width() for bar in table.pf.fig.axes[1].patches]
    assert widths == sorted(widths)
    assert '标准化效应' in table.pf.fig.axes[1].get_title()
    for mode in ('正态', '半正态'):
        dialog.effect_plot.set(mode)
        dialog.plot()
        assert mode in table.pf.fig.axes[1].get_title()
    dialog.screening_model.set('主效应与平方')
    dialog.analyze()
    assert dialog.result is not None and 'F1²' in dialog.result['names']
    dialog.effect_plot.set('Pareto')
    dialog.plot()
    assert 'F1²' in [tick.get_text() for tick in table.pf.fig.axes[1].get_yticklabels()]
    dialog.screening_model.set('自定义')
    dialog.screening_terms.insert(0, 'F1;F2;F3;F4;F5;F1*F5')
    dialog.analyze()
    assert dialog.result is not None and 'F1*F5' in dialog.result['names']
    original_beta = dialog.result['coefficients'].copy()
    dialog.response.set('Z')
    dialog.analyze()
    np.testing.assert_allclose(dialog.result['coefficients'], 2 * original_beta, atol=1e-10)
    target = tmp_path / 'dsd.dexpl'
    assert app._save_project(target) and app.load_file(target)
    restored = app.getCurrentTable()
    assert app.copySheet().doe_metadata == restored.doe_metadata
    again = AnalyzeDOE(app, screening=True)
    again.analyze()
    assert again.result is not None
    again.main.destroy()
    dialog.main.destroy()
    error.assert_not_called()


@pytest.mark.parametrize('kind', ['pb', 'dsd'])
def test_invalid_create_and_small_window_actions(csv_app, monkeypatch, kind):
    app, _ = csv_app
    error = Mock()
    monkeypatch.setattr('doe_dialog.messagebox.showerror', error)
    original = list(app.sheets)
    dialog = CreateDOE(app, pb=kind == 'pb', dsd=kind == 'dsd')
    dialog.main.geometry('620x500')
    dialog.main.update()
    buttons = [w for parent in dialog.main.winfo_children() for w in parent.winfo_children()
               if w.winfo_class() == 'TButton']
    assert {button.cget('text') for button in buttons} >= {'预览', '创建', '取消'}
    for button in buttons:
        assert button.winfo_rooty() + button.winfo_height() <= dialog.main.winfo_rooty() + dialog.main.winfo_height()
    dialog.factor_count.set('27' if kind == 'pb' else '5')
    dialog.update_factor_rows()
    if kind == 'dsd':
        dialog.fields[3][4].insert(0, '甲;乙')
        dialog.fields[4][4].insert(0, '关;开')
    dialog.create()
    assert list(app.sheets) == original
    assert error.call_count == 1
    dialog.main.destroy()


@pytest.mark.parametrize('kind', ['pb', 'dsd'])
def test_source_switch_edit_and_deletion_invalidate_snapshot(csv_app, monkeypatch, kind):
    app, _ = csv_app
    error = Mock()
    monkeypatch.setattr('doe_dialog.messagebox.showerror', error)
    monkeypatch.setattr('worksheets.messagebox.askyesno', lambda *a, **k: True)
    previous = list(app.sheets)[0]
    CreateDOE(app, pb=kind == 'pb', dsd=kind == 'dsd').create()
    table = app.getCurrentTable()
    source_name = next(name for name, sheet in app.sheets.items() if sheet is table)
    table.model.df['响应_Y'] = np.arange(len(table.model.df), dtype=float)
    dialog = AnalyzeDOE(app, screening=kind == 'dsd')
    dialog.analyze()
    assert dialog.result is not None
    app.nb.select(app.sheetframes[previous])
    dialog.plot()
    assert '来源工作表已切换' in error.call_args.args[1]
    app.nb.select(app.sheetframes[source_name])
    original = table.model.df.loc[0, '设定_F1']
    table.model.df.loc[0, '设定_F1'] = 1 - original
    dialog.plot()
    assert '重新分析' in error.call_args.args[1]
    table.model.df.loc[0, '设定_F1'] = original
    assert app.deleteSheet()
    dialog.analyze()
    assert '来源工作表已关闭' in error.call_args.args[1]
    dialog.main.destroy()


@pytest.mark.parametrize('kind,count,runs', [
    ('pb', 3, 20), ('pb', 3, 24), ('pb', 3, 28), ('pb', 3, 32), ('pb', 3, 36),
    ('pb', 3, 40), ('pb', 3, 44), ('pb', 3, 48),
    ('dsd', 2, 13), ('dsd', 3, 13), ('dsd', 4, 13), ('dsd', 5, 13),
    ('dsd', 6, 13), ('dsd', 7, 17), ('dsd', 8, 17), ('dsd', 9, 21), ('dsd', 10, 21),
])
def test_other_screening_configurations_project_lifecycle(csv_app, tmp_path, monkeypatch, kind, count, runs):
    app, _ = csv_app
    error = Mock()
    monkeypatch.setattr('doe_dialog.messagebox.showerror', error)
    monkeypatch.setattr('worksheets.messagebox.askyesno', lambda *a, **k: True)
    create = CreateDOE(app, pb=kind == 'pb', dsd=kind == 'dsd')
    create.factor_count.set(str(count))
    create.update_factor_rows()
    if kind == 'pb':
        create.pb_runs.set(str(runs))
    create.create()
    table = app.getCurrentTable()
    assert len(table.model.df) == runs
    table.model.df['响应_Y'] = np.arange(runs, dtype=float) % 7
    analysis = AnalyzeDOE(app, screening=kind == 'dsd')
    analysis.analyze()
    assert analysis.result is not None
    if (kind == 'pb' and runs in (24, 32, 36, 40, 44, 48)) or (kind == 'dsd' and count in (2, 3, 4, 5, 9)):
        analysis.plot()
    path = tmp_path / f'{kind}-{count}-{runs}.dexpl'
    assert app._save_project(path) and app.load_file(path)
    restored = app.getCurrentTable()
    copied = app.copySheet()
    assert copied.doe_metadata == restored.doe_metadata
    again = AnalyzeDOE(app, screening=kind == 'dsd')
    again.analyze()
    assert again.result is not None and again.result['n'] == runs
    again.main.destroy()
    analysis.main.destroy()
    error.assert_not_called()


@pytest.mark.parametrize('continuous', [1, 2, 3, 5])
def test_dsd_new_mixed_configurations_gui_lifecycle(csv_app, tmp_path, monkeypatch, continuous):
    app, _ = csv_app
    error = Mock()
    monkeypatch.setattr('doe_dialog.messagebox.showerror', error)
    monkeypatch.setattr('worksheets.messagebox.askyesno', lambda *a, **k: True)
    create = CreateDOE(app, dsd=True)
    create.factor_count.set(str(continuous + 1))
    create.update_factor_rows()
    create.fields[continuous][4].insert(0, '甲;乙')
    create.preview()
    assert '14 次运行' in create.preview_text.get()
    create.create()
    table = app.getCurrentTable()
    assert set(table.model.df[f'设定_F{continuous + 1}']) == {'甲', '乙'}
    table.model.df['响应_Y'] = np.arange(14, dtype=float) % 7
    analysis = AnalyzeDOE(app, screening=True)
    analysis.analyze()
    assert analysis.result is not None
    analysis.plot()
    path = tmp_path / f'dsd-{continuous}-1.dexpl'
    assert app._save_project(path) and app.load_file(path)
    restored = app.getCurrentTable()
    copied = app.copySheet()
    assert copied.doe_metadata == restored.doe_metadata
    again = AnalyzeDOE(app, screening=True)
    again.analyze()
    assert again.result is not None
    again.main.destroy()
    analysis.main.destroy()
    error.assert_not_called()


def test_dsd_two_categories_gui_lifecycle(csv_app, tmp_path, monkeypatch):
    app, _ = csv_app
    error = Mock()
    monkeypatch.setattr('doe_dialog.messagebox.showerror', error)
    monkeypatch.setattr('worksheets.messagebox.askyesno', lambda *a, **k: True)
    create = CreateDOE(app, dsd=True)
    create.factor_count.set('6')
    create.update_factor_rows()
    create.fields[4][4].insert(0, '甲;乙')
    create.fields[5][4].insert(0, '低;高')
    create.preview()
    assert '14 次运行' in create.preview_text.get()
    create.create()
    table = app.getCurrentTable()
    assert set(table.model.df['设定_F5']) == {'甲', '乙'}
    assert set(table.model.df['设定_F6']) == {'低', '高'}
    table.model.df['响应_Y'] = np.arange(14, dtype=float) % 7
    analysis = AnalyzeDOE(app, screening=True)
    analysis.analyze()
    assert analysis.result is not None
    analysis.plot()
    path = tmp_path / 'dsd-4c2.dexpl'
    assert app._save_project(path) and app.load_file(path)
    restored = app.getCurrentTable()
    copied = app.copySheet()
    assert copied.doe_metadata == restored.doe_metadata
    again = AnalyzeDOE(app, screening=True)
    again.analyze()
    assert again.result is not None
    again.main.destroy()
    analysis.main.destroy()
    error.assert_not_called()


def test_dsd_blocks_gui_lifecycle_and_invalid_partition(csv_app, tmp_path, monkeypatch):
    app, _ = csv_app
    error = Mock()
    monkeypatch.setattr('doe_dialog.messagebox.showerror', error)
    monkeypatch.setattr('worksheets.messagebox.askyesno', lambda *a, **k: True)
    original = app.getCurrentTable()
    sheets = list(app.sheets)
    invalid = CreateDOE(app, dsd=True)
    invalid.options['重复数'].delete(0, 'end')
    invalid.options['重复数'].insert(0, '3')
    invalid.dsd_blocks.delete(0, 'end')
    invalid.dsd_blocks.insert(0, '2')
    invalid.create()
    assert error.called and app.getCurrentTable() is original and list(app.sheets) == sheets
    invalid.main.destroy()
    error.reset_mock()
    create = CreateDOE(app, dsd=True)
    create.options['重复数'].delete(0, 'end')
    create.options['重复数'].insert(0, '4')
    create.dsd_blocks.delete(0, 'end')
    create.dsd_blocks.insert(0, '2')
    create.preview()
    assert '52 次运行' in create.preview_text.get()
    create.create()
    table = app.getCurrentTable()
    assert table.model.df['区组'].value_counts().to_dict() == {1: 26, 2: 26}
    table.model.df['响应_Y'] = np.arange(52, dtype=float) % 7
    analysis = AnalyzeDOE(app, screening=True)
    analysis.analyze()
    assert analysis.result is not None and '区组2' in analysis.result['names']
    analysis.plot()
    assert '区组2' not in [tick.get_text() for tick in table.pf.fig.axes[1].get_yticklabels()]
    path = tmp_path / 'dsd-blocks.dexpl'
    assert app._save_project(path) and app.load_file(path)
    restored = app.getCurrentTable()
    copied = app.copySheet()
    assert copied.doe_metadata == restored.doe_metadata
    again = AnalyzeDOE(app, screening=True)
    again.analyze()
    assert again.result is not None and '区组2' in again.result['names']
    again.main.destroy()
    analysis.main.destroy()
    error.assert_not_called()


@pytest.mark.parametrize('count', range(11, 49))
@pytest.mark.parametrize('mixed', [False, True])
def test_dsd_large_configurations_gui_lifecycle(csv_app, tmp_path, monkeypatch, count, mixed):
    app, _ = csv_app
    error = Mock()
    monkeypatch.setattr('doe_dialog.messagebox.showerror', error)
    monkeypatch.setattr('worksheets.messagebox.askyesno', lambda *a, **k: True)
    create = CreateDOE(app, dsd=True)
    create.factor_count.set(str(count))
    create.update_factor_rows()
    if mixed:
        create.fields[count - 1][4].insert(0, '甲;乙')
    create.preview()
    assert '次运行' in create.preview_text.get()
    create.create()
    table = app.getCurrentTable()
    if mixed:
        assert set(table.model.df[f'设定_F{count}']) == {'甲', '乙'}
    table.model.df['响应_Y'] = np.arange(len(table.model.df), dtype=float) % 7
    analysis = AnalyzeDOE(app, screening=True)
    analysis.analyze()
    assert analysis.result is not None
    if mixed:
        analysis.factor_y.set(f'F{count}')
    analysis.plot()
    labels = [line.get_label() for line in table.pf.fig.axes[0].lines]
    assert len(labels) == 2
    if mixed:
        assert any('甲 / 乙' in label for label in labels)
    path = tmp_path / f'dsd-{count}-{mixed}.dexpl'
    assert app._save_project(path) and app.load_file(path)
    restored = app.getCurrentTable()
    copied = app.copySheet()
    assert copied.doe_metadata == restored.doe_metadata
    again = AnalyzeDOE(app, screening=True)
    again.analyze()
    assert again.result is not None
    again.main.destroy()
    analysis.main.destroy()
    error.assert_not_called()


def test_pb_centers_and_blocks_gui_lifecycle(csv_app, tmp_path, monkeypatch):
    app, _ = csv_app
    error = Mock()
    monkeypatch.setattr('doe_dialog.messagebox.showerror', error)
    monkeypatch.setattr('worksheets.messagebox.askyesno', lambda *a, **k: True)
    create = CreateDOE(app, pb=True)
    create.options['重复数'].delete(0, 'end')
    create.options['重复数'].insert(0, '2')
    create.options['中心点数'].delete(0, 'end')
    create.options['中心点数'].insert(0, '2')
    create.pb_block_replicates.set(True)
    create.create()
    table = app.getCurrentTable()
    assert len(table.model.df) == 28
    assert table.model.df['区组'].value_counts().to_dict() == {1: 14, 2: 14}
    table.model.df['响应_Y'] = np.arange(28, dtype=float) % 7
    analysis = AnalyzeDOE(app)
    analysis.analyze()
    assert analysis.result['curvature'] is not None
    assert '纯误差与曲率' in [analysis.tabs.tab(tab, 'text') for tab in analysis.tabs.tabs()]
    analysis.plot()
    path = tmp_path / 'pb-centers-blocks.dexpl'
    assert app._save_project(path) and app.load_file(path)
    original = app.getCurrentTable()
    copied = app.copySheet()
    assert copied.doe_metadata == original.doe_metadata
    again = AnalyzeDOE(app)
    again.analyze()
    assert again.result['curvature'] is not None
    again.main.destroy()
    analysis.main.destroy()
    error.assert_not_called()


def test_invalid_pb_center_configuration_does_not_change_workbook(csv_app, monkeypatch):
    app, _ = csv_app
    original = app.getCurrentTable()
    sheets = list(app.sheets)
    error = Mock()
    monkeypatch.setattr('doe_dialog.messagebox.showerror', error)
    create = CreateDOE(app, pb=True)
    create.options['中心点数'].delete(0, 'end')
    create.options['中心点数'].insert(0, '-1')
    create.create()
    assert error.called
    create.main.destroy()
    assert app.getCurrentTable() is original and list(app.sheets) == sheets


def test_pb_text_centers_blocks_gui_lifecycle(csv_app, tmp_path, monkeypatch):
    app, _ = csv_app
    error = Mock()
    monkeypatch.setattr('doe_dialog.messagebox.showerror', error)
    monkeypatch.setattr('worksheets.messagebox.askyesno', lambda *a, **k: True)
    create = CreateDOE(app, pb=True)
    create.fields[1][4].insert(0, '甲;乙')
    create.fields[2][4].insert(0, '关;开')
    for key in ('重复数', '中心点数'):
        create.options[key].delete(0, 'end')
        create.options[key].insert(0, '2')
    create.pb_block_replicates.set(True)
    create.preview()
    assert '40 次运行' in create.preview_text.get() and '甲 / 乙' in create.preview_text.get()
    create.create()
    table = app.getCurrentTable()
    assert (table.model.df['点类型'] == 'pseudo_center').sum() == 16
    table.model.df['响应_Y'] = np.arange(40, dtype=float) % 7
    analysis = AnalyzeDOE(app)
    analysis.analyze()
    assert analysis.result['curvature'] is not None
    analysis.plot()
    assert any('甲 / 乙' in line.get_label() for line in table.pf.fig.axes[0].lines)
    path = tmp_path / 'pb-text-centers.dexpl'
    assert app._save_project(path) and app.load_file(path)
    restored = app.getCurrentTable()
    copied = app.copySheet()
    assert copied.doe_metadata == restored.doe_metadata
    again = AnalyzeDOE(app)
    again.analyze()
    assert again.result is not None
    again.main.destroy()
    analysis.main.destroy()
    error.assert_not_called()


def test_pb_maximum_capacity_saturated_gui(csv_app, monkeypatch):
    app, _ = csv_app
    error = Mock()
    monkeypatch.setattr('doe_dialog.messagebox.showerror', error)
    create = CreateDOE(app, pb=True)
    create.factor_count.set('27')
    create.update_factor_rows()
    create.pb_runs.set('28')
    create.create()
    table = app.getCurrentTable()
    assert len(table.model.df) == 28
    table.model.df['响应_Y'] = np.arange(28, dtype=float)
    analysis = AnalyzeDOE(app)
    analysis.analyze()
    assert analysis.result is not None and analysis.result['rank'] == 28
    assert analysis.result['df'] == 0 and analysis.result['inference'] is None
    assert 'Lenth' in analysis.status.get()
    analysis.main.destroy()
    error.assert_not_called()


def test_pb48_maximum_capacity_graph_and_project(csv_app, tmp_path, monkeypatch):
    app, _ = csv_app
    error = Mock()
    monkeypatch.setattr('doe_dialog.messagebox.showerror', error)
    monkeypatch.setattr('worksheets.messagebox.askyesno', lambda *a, **k: True)
    create = CreateDOE(app, pb=True)
    create.factor_count.set('47')
    create.update_factor_rows()
    create.pb_runs.set('48')
    create.create()
    table = app.getCurrentTable()
    table.model.df['响应_Y'] = np.arange(48, dtype=float) % 7
    analysis = AnalyzeDOE(app)
    analysis.analyze()
    assert analysis.result is not None and analysis.result['rank'] == 48
    analysis.factor_y.set('F47')
    analysis.plot()
    assert [line.get_label() for line in table.pf.fig.axes[0].lines] == ['F1', 'F47']
    path = tmp_path / 'pb48-max.dexpl'
    assert app._save_project(path) and app.load_file(path)
    restored = app.getCurrentTable()
    copied = app.copySheet()
    assert copied.doe_metadata == restored.doe_metadata
    again = AnalyzeDOE(app)
    again.analyze()
    assert again.result is not None and again.result['rank'] == 48
    again.main.destroy()
    analysis.main.destroy()
    error.assert_not_called()


@pytest.mark.parametrize('runs', [24, 32, 36, 40, 44])
def test_pb_new_run_counts_at_capacity_gui(csv_app, tmp_path, monkeypatch, runs):
    app, _ = csv_app
    error = Mock()
    monkeypatch.setattr('doe_dialog.messagebox.showerror', error)
    monkeypatch.setattr('worksheets.messagebox.askyesno', lambda *a, **k: True)
    create = CreateDOE(app, pb=True)
    create.factor_count.set(str(runs - 1))
    create.update_factor_rows()
    create.pb_runs.set(str(runs))
    create.preview()
    assert f'{runs} 次运行' in create.preview_text.get()
    create.create()
    table = app.getCurrentTable()
    table.model.df['响应_Y'] = np.arange(runs, dtype=float) % 7
    analysis = AnalyzeDOE(app)
    analysis.analyze()
    assert analysis.result is not None and analysis.result['rank'] == runs
    analysis.plot()
    assert len(table.pf.fig.axes[0].lines) == 2
    path = tmp_path / f'pb-{runs}-max.dexpl'
    assert app._save_project(path) and app.load_file(path)
    restored = app.getCurrentTable()
    copied = app.copySheet()
    assert copied.doe_metadata == restored.doe_metadata
    again = AnalyzeDOE(app)
    again.analyze()
    assert again.result is not None and again.result['rank'] == runs
    again.main.destroy()
    analysis.main.destroy()
    error.assert_not_called()


@pytest.mark.parametrize('runs,count', [(runs, count) for runs in (24, 32, 36, 40, 44, 48)
                                         for count in range(2, runs) if count not in (3, runs - 1)])
def test_pb_new_run_counts_all_factor_counts_gui(csv_app, tmp_path, monkeypatch, runs, count):
    app, _ = csv_app
    error = Mock()
    monkeypatch.setattr('doe_dialog.messagebox.showerror', error)
    monkeypatch.setattr('worksheets.messagebox.askyesno', lambda *a, **k: True)
    create = CreateDOE(app, pb=True)
    create.factor_count.set(str(count))
    create.update_factor_rows()
    create.pb_runs.set(str(runs))
    create.create()
    table = app.getCurrentTable()
    assert len(table.model.df) == runs
    table.model.df['响应_Y'] = np.arange(runs, dtype=float) % 7
    analysis = AnalyzeDOE(app)
    analysis.analyze()
    assert analysis.result is not None and analysis.result['rank'] == count + 1
    analysis.plot()
    path = tmp_path / f'pb-{runs}-{count}.dexpl'
    assert app._save_project(path) and app.load_file(path)
    restored = app.getCurrentTable()
    copied = app.copySheet()
    assert copied.doe_metadata == restored.doe_metadata
    again = AnalyzeDOE(app)
    again.analyze()
    assert again.result is not None and again.result['rank'] == count + 1
    again.main.destroy()
    analysis.main.destroy()
    error.assert_not_called()


def test_pb_saturated_lenth_and_effect_plot_modes(csv_app, monkeypatch):
    app, _ = csv_app
    error = Mock()
    monkeypatch.setattr('doe_dialog.messagebox.showerror', error)
    create = CreateDOE(app, pb=True)
    create.factor_count.set('11')
    create.update_factor_rows()
    create.create()
    table = app.getCurrentTable()
    x = 2 * table.model.df[[f'设定_F{i}' for i in range(1, 12)]].to_numpy(dtype=float) - 1
    table.model.df['响应_Y'] = 5 + x @ (np.array([2] * 10 + [50]) / 2)
    analysis = AnalyzeDOE(app)
    analysis.analyze()
    assert analysis.result['lenth']['pse'] == pytest.approx(3)
    assert 'Lenth PSE' in [analysis.tabs.tab(tab, 'text') for tab in analysis.tabs.tabs()]
    for mode in ('Pareto', '正态', '半正态'):
        analysis.effect_plot.set(mode)
        analysis.plot()
        axis = table.pf.fig.axes[3]
        assert mode in axis.get_title()
        assert any(np.allclose(line.get_xdata(), 8.636634489208934) for line in axis.lines)
    analysis.main.destroy()
    error.assert_not_called()


def test_dsd_rank_deficient_model_and_contrast_gui(csv_app, monkeypatch):
    app, _ = csv_app
    error = Mock()
    monkeypatch.setattr('doe_dialog.messagebox.showerror', error)
    CreateDOE(app, dsd=True).create()
    table = app.getCurrentTable()
    table.model.df['响应_Y'] = np.arange(13, dtype=float)
    dialog = AnalyzeDOE(app, screening=True)
    dialog.screening_model.set('自定义')
    terms = [f'F{i}' for i in range(1, 7)] + [f'F{i}^2' for i in range(1, 7)] + ['F1*F2']
    dialog.screening_terms.insert(0, ';'.join(terms))
    dialog.screening_contrast.insert(0, 'F1=1')
    dialog.analyze()
    assert dialog.result['rank'] == 13 and dialog.result['p'] == 14
    assert dialog.result['contrast']['estimable']
    assert {'零空间', '可估计性', '指定对比'} <= {dialog.tabs.tab(tab, 'text') for tab in dialog.tabs.tabs()}
    dialog.screening_contrast.delete(0, 'end')
    dialog.screening_contrast.insert(0, 'F1*F2=1')
    dialog.analyze()
    assert not dialog.result['contrast']['estimable']
    dialog.plot()
    dialog.screening_contrast.delete(0, 'end')
    dialog.screening_terms.delete(0, 'end')
    dialog.screening_terms.insert(0, 'F1;F2;F3;F1^2;F2*F3')
    dialog.analyze()
    assert '平方与交互投影' in [dialog.tabs.tab(tab, 'text') for tab in dialog.tabs.tabs()]
    dialog.main.destroy()
    error.assert_not_called()


def test_dsd_saturated_and_invalid_hierarchy_gui(csv_app, monkeypatch):
    app, _ = csv_app
    error = Mock()
    monkeypatch.setattr('doe_dialog.messagebox.showerror', error)
    CreateDOE(app, dsd=True).create()
    table = app.getCurrentTable()
    table.model.df['响应_Y'] = np.arange(len(table.model.df), dtype=float)
    dialog = AnalyzeDOE(app, screening=True)
    dialog.screening_model.set('主效应与平方')
    dialog.analyze()
    assert dialog.result is not None and dialog.result['df'] == 0
    assert dialog.result['inference'] is None
    assert '方差分析' not in [dialog.tabs.tab(tab, 'text') for tab in dialog.tabs.tabs()]
    dialog.plot()
    assert all('残差诊断不可用' in axis.texts[0].get_text() for axis in table.pf.fig.axes[2:])
    dialog.screening_model.set('自定义')
    dialog.screening_terms.insert(0, 'F1;F1*F2')
    dialog.analyze()
    assert dialog.result is None and '主效应' in error.call_args.args[1]
    dialog.main.destroy()
