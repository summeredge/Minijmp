"""P2-4A 真实 Tk：DSD 逐步选模失效路径与 PB Foldover 生命周期。"""
from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest

from doe_core import restore_design_result
from doe_dialog import AnalyzeDOE, CreateDOE
from doe_foldover_dialog import FoldoverDOE
from test_csv_import import csv_app


def select_folded(dialog, *factor_ids):
    choices = tuple(dialog.folded.get(0, 'end'))
    dialog.folded.selection_clear(0, 'end')
    for value in factor_ids or ('全部',):
        dialog.folded.selection_set(choices.index(value))


def create_dsd(app, factors='6'):
    dialog = CreateDOE(app, dsd=True)
    dialog.factor_count.set(factors)
    dialog.update_factor_rows()
    dialog.create()
    return app.getCurrentSheet(), app.getCurrentTable()


def fill_dsd(table, name='响应_Y'):
    frame = table.model.df
    column = frame.columns.get_loc(name)
    for index, row in frame.iterrows():
        a = 2 * row['设定_F1'] - 1
        b = 2 * row['设定_F2'] - 1
        table.model.setValueAt(str(40 + 5 * a - 3 * b), index, column)


def test_dsd_stepwise_gui_selects_shows_history_and_invalidates(
        csv_app, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr('doe_dialog.messagebox.showerror', error)
    _, table = create_dsd(app)
    fill_dsd(table)
    dialog = AnalyzeDOE(app, screening=True)
    assert dialog.dsd and dialog.use_stepwise.get() is False
    dialog.use_stepwise.set(True)
    dialog.analyze()
    assert dialog.result is not None, error.call_args_list
    assert dialog.selection is not None
    selected = [tuple(term) for term in dialog.selection['selected_terms']]
    assert ('F1',) in selected and ('F2',) in selected
    labels = [dialog.tabs.tab(tab, 'text') for tab in dialog.tabs.tabs()]
    assert '选择历史' in labels and '选模汇总' in labels
    assert '名义统计量' in dialog.stepwise_status.get()

    # 参数变化立即失效旧结果；未重分析时绘图被拒绝。
    dialog.alpha_enter.delete(0, 'end')
    dialog.alpha_enter.insert(0, '0.05')
    dialog._invalidate_screening()
    assert dialog.result is None and dialog.selection is None
    assert not dialog.tabs.tabs()
    dialog.plot()
    assert '请先分析' in error.call_args.args[1]
    error.reset_mock()
    dialog.analyze()
    assert dialog.result is not None

    # 响应列改变后不得继续使用旧模型结果。
    table.model.setValueAt('1', 0, table.model.df.columns.get_loc('响应_Y'))
    dialog.plot()
    assert '重新分析' in error.call_args.args[1]
    error.reset_mock()
    dialog.main.destroy()


def test_dsd_stepwise_gui_rejects_invalid_alpha_and_steps(csv_app, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr('doe_dialog.messagebox.showerror', error)
    _, table = create_dsd(app)
    fill_dsd(table)
    dialog = AnalyzeDOE(app, screening=True)
    dialog.use_stepwise.set(True)
    dialog.analyze()
    assert dialog.result is not None
    for widget, value in ((dialog.alpha_enter, 'abc'), (dialog.alpha_enter, '0'),
                          (dialog.alpha_remove, '1'), (dialog.max_steps, '0')):
        error.reset_mock()
        original = widget.get()
        widget.delete(0, 'end')
        widget.insert(0, value)
        dialog.analyze()
        assert dialog.result is None
        assert error.called
        widget.delete(0, 'end')
        widget.insert(0, original)
    dialog.main.destroy()


def test_dsd_manual_model_remains_default(csv_app, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr('doe_dialog.messagebox.showerror', error)
    _, table = create_dsd(app)
    fill_dsd(table)
    dialog = AnalyzeDOE(app, screening=True)
    dialog.analyze()
    assert dialog.result is not None and dialog.selection is None
    assert dialog.stepwise_status.get() == ''
    labels = [dialog.tabs.tab(tab, 'text') for tab in dialog.tabs.tabs()]
    assert '选择历史' not in labels
    dialog.main.destroy()


def test_dsd_model_response_and_contrast_changes_invalidate_results(csv_app, monkeypatch):
    """模型项、响应列与对比修改后旧表格必须清空，不能继续显示别的模型结果。"""
    app, error = csv_app
    monkeypatch.setattr('doe_dialog.messagebox.showerror', error)
    _, table = create_dsd(app)
    fill_dsd(table)
    dialog = AnalyzeDOE(app, screening=True)
    dialog.analyze()
    assert dialog.result is not None and dialog.tabs.tabs()

    # Tk 的 event_generate 在本环境不投递按键事件，直接调用绑定处理函数，
    # 与 KeyRelease 回调走同一条业务路径。
    triggers = {
        'model': lambda: (dialog.screening_model.set('主效应与平方'),
                          dialog.screening_model.event_generate('<<ComboboxSelected>>')),
        'terms': lambda: (dialog.screening_terms.insert('end', 'F1'),
                          dialog._invalidate_screening()),
        'contrast': lambda: (dialog.screening_contrast.insert('end', 'F1=1'),
                             dialog._invalidate_screening()),
    }
    for trigger, fire in triggers.items():
        fire()
        dialog.main.update()
        assert dialog.result is None, trigger
        assert not dialog.tabs.tabs(), trigger
        assert '重新分析' in dialog.status.get(), trigger
        dialog.analyze()
        assert dialog.result is not None, trigger
    dialog.main.destroy()


def test_dsd_stepwise_gui_custom_candidates_initial_and_forced(csv_app, monkeypatch):
    """候选项/初始项/强制项文本框直接驱动选模，并拒绝非法模型项。"""
    app, error = csv_app
    monkeypatch.setattr('doe_dialog.messagebox.showerror', error)
    _, table = create_dsd(app)
    fill_dsd(table)
    dialog = AnalyzeDOE(app, screening=True)
    dialog.use_stepwise.set(True)
    dialog.screening_candidates.delete(0, 'end')
    dialog.screening_candidates.insert(0, 'F1;F2;F1^2;F1*F2')
    dialog.screening_forced.delete(0, 'end')
    dialog.screening_forced.insert(0, 'F1')
    dialog.analyze()
    assert dialog.result is not None, error.call_args_list
    assert ('F1',) in dialog.selection['selected_terms']
    assert set(map(tuple, dialog.selection['candidate_terms'])) == {
        ('F1',), ('F2',), ('F1', 'F1'), ('F1', 'F2')}
    labels = [dialog.tabs.tab(tab, 'text') for tab in dialog.tabs.tabs()]
    assert '选择历史' in labels

    # 初始项必须属于候选项；否则明确报错且不产生结果。
    dialog.screening_initial.delete(0, 'end')
    dialog.screening_initial.insert(0, 'F3')
    dialog.analyze()
    assert dialog.result is None and '子集' in error.call_args.args[1]
    error.reset_mock()

    # 非法语法（空项）在界面层被拒绝。
    dialog.screening_initial.delete(0, 'end')
    dialog.screening_candidates.delete(0, 'end')
    dialog.screening_candidates.insert(0, 'F1;;F2')  # 空项被忽略，仍合法
    dialog.analyze()
    assert dialog.result is not None, error.call_args_list
    error.reset_mock()
    dialog.screening_candidates.delete(0, 'end')
    dialog.screening_candidates.insert(0, ';')  # 只有分隔符
    dialog.analyze()
    assert dialog.result is None and '分隔符' in error.call_args.args[1]
    dialog.main.destroy()


def test_dsd_stepwise_candidate_cap_is_shown_and_enforced(csv_app, monkeypatch):
    """界面提示 64 上限；13 因子全二阶候选超过上限时明确拒绝。"""
    app, error = csv_app
    monkeypatch.setattr('doe_dialog.messagebox.showerror', error)
    _, table = create_dsd(app, factors='13')
    fill_dsd(table)
    dialog = AnalyzeDOE(app, screening=True)
    assert '64' in dialog.stepwise_hint.get()
    dialog.use_stepwise.set(True)
    dialog.analyze()
    assert dialog.result is None
    assert '64' in error.call_args.args[1]
    dialog.main.destroy()


def create_pb(app, run_count='12'):
    dialog = CreateDOE(app, pb=True)
    # PB 创建窗体的运行数由因子数推断；使用 3 因子即 PB12。
    dialog.factor_count.set('3')
    dialog.update_factor_rows()
    dialog.create()
    return app.getCurrentSheet(), app.getCurrentTable()


def fill_pb(table):
    frame = table.model.df
    column = frame.columns.get_loc('响应_Y')
    for index, row in frame.iterrows():
        table.model.setValueAt(str(10 + 2 * row['设定_F1'] - 3 * row['设定_F2']),
                               index, column)


def test_pb_foldover_preview_create_and_reopen(csv_app, tmp_path, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr('doe_foldover_dialog.messagebox.showerror', error)
    monkeypatch.setattr('worksheets.messagebox.askyesno', lambda *a, **k: True)
    monkeypatch.setattr('worksheets.messagebox.askyesnocancel', lambda *a, **k: False)
    source_name, table = create_pb(app)
    fill_pb(table)
    before = table.model.df.copy(deep=True)

    cancelled = FoldoverDOE(app)
    cancelled.cancel_button.invoke()
    pd.testing.assert_frame_equal(table.model.df, before)
    assert list(app.sheets)[-1] == source_name

    dialog = FoldoverDOE(app)
    assert dialog.source.get() == source_name
    assert 'Plackett–Burman' in dialog.limits.get()
    dialog.preview_button.invoke()
    preview = dialog.preview_text.get('1.0', 'end')
    assert '运行数：12 → 24' in preview
    assert '主效应模型秩' in preview and '完全混杂交互' in preview
    assert '可单独估计交互' in preview and '不可估计交互' in preview
    # 该用例是 3 因子 PB12：3 个交互，折叠后全部可单独估计（3 → 3 全部可估）。
    assert '可单独估计交互：3 → 3' in preview
    assert '正规定义关系' not in preview.replace('无正规定义关系', '')
    dialog.create_button.invoke()

    folded_name = app.getCurrentSheet()
    folded = app.getCurrentTable()
    assert folded_name != source_name
    assert source_name in app.sheets
    assert len(folded.model.df) == 24
    assert folded.doe_metadata['design']['design_type'] == 'plackett_burman'
    assert folded.doe_metadata['design']['foldover_lineage']['folded_factors'] == [
        'F1', 'F2', 'F3']
    pd.testing.assert_frame_equal(app.sheets[source_name].model.df, before)

    path = tmp_path / 'pb-foldover.dexpl'
    assert app._save_project(path)
    assert app.load_file(path)
    reopened = next(name for name, sheet in app.sheets.items()
                    if sheet.doe_metadata and sheet.doe_metadata['design'].get(
                        'foldover_lineage') is not None)
    app.nb.select(app.sheetframes[reopened])
    copied = app.copySheet()
    assert copied.doe_metadata == app.getCurrentTable().doe_metadata


def test_pb_foldover_dexpl_survives_corrupted_metadata_isolation(
        csv_app, tmp_path, monkeypatch):
    """保存重开后伪造谱系摘要必须被拒绝，且不影响其余工作表。"""
    import json

    app, error = csv_app
    monkeypatch.setattr('worksheets.messagebox.askyesno', lambda *a, **k: True)
    monkeypatch.setattr('worksheets.messagebox.askyesnocancel', lambda *a, **k: False)
    source_name, table = create_pb(app)
    fill_pb(table)
    dialog = FoldoverDOE(app)
    dialog.create_button.invoke()
    folded_name = app.getCurrentSheet()
    path = tmp_path / 'pb-foldover-corrupt.dexpl'
    assert app._save_project(path)

    damaged = json.loads(json.dumps(app.sheets[folded_name].doe_metadata))
    damaged['design']['foldover_lineage']['current_matrix_sha256'] = 'f' * 64
    with pytest.raises(ValueError):
        restore_design_result(app.sheets[folded_name].model.df, damaged)
    # 原始来源仍可独立载入分析，证明隔离只针对损坏设计。
    assert app.sheets[source_name].doe_metadata['design'].get('foldover_lineage') is None
    app.nb.select(app.sheetframes[source_name])
    analysis = AnalyzeDOE(app)
    assert analysis.pb
    analysis.main.destroy()


def test_pb_foldover_single_factor_and_analysis_after_editing(csv_app, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr('doe_foldover_dialog.messagebox.showerror', error)
    monkeypatch.setattr('doe_dialog.messagebox.showerror', error)
    source_name, table = create_pb(app)
    fill_pb(table)
    dialog = FoldoverDOE(app)
    select_folded(dialog, 'F1')
    dialog.preview_button.invoke()
    preview = dialog.preview_text.get('1.0', 'end')
    assert '折叠：F1' in preview
    dialog.create_button.invoke()
    folded = app.getCurrentTable()
    frame = folded.model.df
    columns = folded.doe_metadata['column_map']
    added = frame[columns['batch_id']] == 'FOLD1'
    assert added.sum() == 12
    assert frame.loc[added, columns['responses']['Y']].isna().all()

    analysis = AnalyzeDOE(app)
    analysis.analyze()
    assert analysis.result is None
    assert '缺失' in error.call_args.args[1]
    error.reset_mock()
    column = frame.columns.get_loc(columns['responses']['Y'])
    for index in frame.index[added]:
        row = frame.loc[index]
        folded.model.setValueAt(str(10 + 2 * row['设定_F1'] - 3 * row['设定_F2']),
                                index, column)
    analysis.analyze()
    assert analysis.result is not None, error.call_args_list
    assert analysis.result['n'] == 24
    assert analysis.result['design'].spec.foldover_lineage['folded_factors'] == ('F1',)
    analysis.main.destroy()


def test_pb_multi_factor_foldover_preview_and_creation(csv_app, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr('doe_foldover_dialog.messagebox.showerror', error)
    source_name, source = create_pb(app)
    fill_pb(source)
    before = source.model.df.copy(deep=True)
    dialog = FoldoverDOE(app)
    select_folded(dialog, 'F1', 'F3')
    assert dialog.preview()
    preview = dialog.preview_text.get('1.0', 'end')
    assert '折叠：F1、F3' in preview
    assert 'F1:' in preview and 'F3:' in preview and '未选因子不变' in preview
    dialog.create_button.invoke()

    folded = app.getCurrentTable()
    columns = folded.doe_metadata['column_map']
    assert folded.doe_metadata['design']['foldover_lineage']['folded_factors'] == [
        'F1', 'F3']
    base = folded.model.df[folded.model.df[columns['batch_id']] == 'BASE'].set_index(
        columns['run_id'])
    added = folded.model.df[folded.model.df[columns['batch_id']] == 'FOLD1'].set_index(
        columns['source_run_id'])
    for run_id, original in base.iterrows():
        row = added.loc[run_id]
        assert row[columns['factors']['F1']] == 1 - original[columns['factors']['F1']]
        assert row[columns['factors']['F2']] == original[columns['factors']['F2']]
        assert row[columns['factors']['F3']] == 1 - original[columns['factors']['F3']]
        assert pd.isna(row[columns['responses']['Y']])
    pd.testing.assert_frame_equal(source.model.df, before)
    coded = folded.model.df[[columns['factors'][key] for key in ('F1', 'F2', 'F3')]
                            ].to_numpy(dtype=float)
    matrix = np.column_stack((np.ones(len(coded)), coded,
                              coded[:, 0] * coded[:, 1],
                              coded[:, 0] * coded[:, 2],
                              coded[:, 1] * coded[:, 2]))
    from doe_pb_foldover import pb_foldover_summary
    assert pb_foldover_summary(folded.model.df, folded.doe_metadata)['after'][
        'joint_rank'] == np.linalg.matrix_rank(matrix)
    assert error.call_count == 0


def test_pb_foldover_ignores_unsupported_sources(csv_app, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr('doe_foldover_dialog.messagebox.showerror', error)
    dialog = FoldoverDOE(app)
    assert getattr(dialog, 'main', None) is None
    error.assert_called_once()


def test_pb_foldover_refuses_when_source_sheet_is_closed(csv_app, monkeypatch):
    """来源工作表被删除后，预览与创建都必须安全拒绝且不新增工作表。"""
    app, error = csv_app
    monkeypatch.setattr('doe_foldover_dialog.messagebox.showerror', error)
    monkeypatch.setattr('worksheets.messagebox.askyesno', lambda *a, **k: True)
    monkeypatch.setattr('worksheets.messagebox.askyesnocancel', lambda *a, **k: False)
    source_name, table = create_pb(app)
    fill_pb(table)
    dialog = FoldoverDOE(app)
    names_before = list(app.sheets)
    # 模拟来源被关闭：直接移除该表，但保留对话框中的下拉值。
    app.sheets.pop(source_name, None)
    error.reset_mock()
    assert dialog.preview() is False
    assert '来源工作表已关闭' in error.call_args.args[1]
    error.reset_mock()
    assert dialog.create() is False
    assert '来源工作表已关闭' in error.call_args.args[1]
    assert len(app.sheets) == len(names_before) - 1
    dialog.main.destroy()


def test_fractional_foldover_path_still_works(csv_app, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr('doe_foldover_dialog.messagebox.showerror', error)
    create = CreateDOE(app, fractional=True)
    create.factor_count.set('4')
    create.update_factor_rows()
    for index, entries in enumerate(create.fields[:4]):
        for entry, value in zip(entries, (chr(65 + index), '0', '1', '')):
            entry.delete(0, 'end')
            entry.insert(0, value)
    create.generators.delete(0, 'end')
    create.generators.insert(0, 'D=ABC')
    create.create()
    source = app.getCurrentTable()
    frame = source.model.df
    column = frame.columns.get_loc('响应_Y')
    for index, row in frame.iterrows():
        total = 20 + sum(2 * row[f'设定_{key}'] - 1 for key in 'ABCD')
        source.model.setValueAt(str(total), index, column)
    dialog = FoldoverDOE(app)
    select_folded(dialog, 'A')
    dialog.preview_button.invoke()
    assert '分辨度' in dialog.preview_text.get('1.0', 'end')
    dialog.create_button.invoke()
    assert len(app.getCurrentTable().model.df) == 16
    assert error.call_count == 0
