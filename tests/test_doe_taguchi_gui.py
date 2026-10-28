"""Taguchi 创建/分析/最佳设置的真实 Tk 工程闭环。"""
from unittest.mock import Mock

import pytest

from doe_taguchi_analysis_dialog import AnalyzeTaguchi
from doe_taguchi_dialog import CreateTaguchi
from test_csv_import import csv_app


def invoke(app, label):
    menu = app.doe_menu['var']
    index = next(i for i in range(menu.index('end') + 1)
                 if menu.type(i) == 'command'
                 and menu.entrycget(i, 'label').strip() == label)
    previous = set(app.main.winfo_children())
    menu.invoke(index)
    return next((widget for widget in set(app.main.winfo_children()) - previous
                 if isinstance(widget, type(widget)) and widget.winfo_exists()), None)


def configure_static(dialog):
    dialog.array.set('L9(3^4)')
    dialog.factor_count.set('3')
    dialog.update_rows()
    for index in range(3):
        _, _, levels, column, role = dialog.rows[index]
        levels.delete(0, 'end')
        levels.insert(0, '低;中;高')
        role.set('控制')
        column.set(str(index + 1))
    dialog.replicates.delete(0, 'end')
    dialog.replicates.insert(0, '2')
    dialog.seed.delete(0, 'end')
    dialog.seed.insert(0, '31')


def fill_static(table):
    frame = table.model.df
    coded = {'低': -1, '中': 0, '高': 1}
    response = frame.columns.get_loc('响应_Y')
    for index, row in frame.iterrows():
        a = coded[row['设定_A']]
        b = coded[row['设定_B']]
        jitter = 0.4 if row['重复'] == 1 else -0.4
        table.model.setValueAt(str(10 + 5 * a + 2 * b + jitter), index, response)


def test_taguchi_static_menu_preview_analysis_best_save_reopen_copy(
        csv_app, tmp_path, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr('doe_taguchi_dialog.messagebox.showerror', error)
    monkeypatch.setattr('doe_taguchi_analysis_dialog.messagebox.showerror', error)
    monkeypatch.setattr('worksheets.messagebox.askyesnocancel', lambda *a, **k: False)
    monkeypatch.setattr('worksheets.messagebox.askyesno', lambda *a, **k: True)
    names = list(app.sheets)

    window = invoke(app, '创建 Taguchi 设计（静态）')
    assert window is not None
    window.destroy()
    assert list(app.sheets) == names

    dialog = CreateTaguchi(app)
    configure_static(dialog)
    assert dialog.preview() is True
    preview = dialog.preview_text.get('1.0', 'end')
    assert '运行 18 次' in preview and 'L9(3^4)' in preview
    assert list(app.sheets) == names
    assert dialog.create() is True

    table = app.getCurrentTable()
    assert table.doe_metadata['design']['design_type'] == 'taguchi'
    assert table.doe_metadata['design']['taguchi']['kind'] == 'static'
    fill_static(table)

    analysis = AnalyzeTaguchi(app)
    analysis.analyze()
    assert analysis.result is not None, error.call_args_list
    assert [analysis.tabs.tab(tab, 'text') for tab in analysis.tabs.tabs()][:2] == [
        '组合统计', 'S/N响应表']
    assert analysis.result['n_observations'] == 18
    analysis.plot()
    assert table.pf is not None
    assert table.pf.fig.axes[0].get_title() == 'S/N 主效应'

    analysis.best()
    assert analysis.best_window.main.title() == 'Taguchi 最佳设置预测'
    analysis.best_window.main.destroy()
    assert table.doe_metadata['analysis']['kind'] == 'static'

    path = tmp_path / 'taguchi.dexpl'
    assert app._save_project(path)
    assert app.load_file(path)
    name = next(sheet_name for sheet_name, item in app.sheets.items()
                if item.doe_metadata
                and item.doe_metadata['design']['design_type'] == 'taguchi')
    app.nb.select(app.sheetframes[name])
    reopened = app.getCurrentTable()
    copied = app.copySheet()
    assert copied.doe_metadata == reopened.doe_metadata
    again = AnalyzeTaguchi(app)
    assert again.sn_kind.get() == 'Smaller is better'
    again.analyze()
    assert again.result is not None
    assert again.result['n_observations'] == 18
    assert error.call_count == 0
    analysis.main.destroy()
    again.main.destroy()


@pytest.mark.parametrize("label,kind,expected", [
    ('Smaller is better', 'smaller', -10 * __import__('math').log10(4)),
    ('Larger is better', 'larger', -10 * __import__('math').log10(1 / 4)),
])
def test_l4_single_observation_analysis_and_dexpl_reopen(
        csv_app, tmp_path, monkeypatch, label, kind, expected):
    from stat_table import TableBlock

    app, error = csv_app
    monkeypatch.setattr('doe_taguchi_dialog.messagebox.showerror', error)
    monkeypatch.setattr('doe_taguchi_analysis_dialog.messagebox.showerror', error)
    monkeypatch.setattr('worksheets.messagebox.askyesnocancel', lambda *a, **k: False)
    monkeypatch.setattr('worksheets.messagebox.askyesno', lambda *a, **k: True)
    dialog = CreateTaguchi(app)
    dialog.array.set('L4(2^3)')
    dialog.factor_count.set('2')
    dialog.update_rows()
    for index in range(2):
        dialog.rows[index][2].delete(0, 'end')
        dialog.rows[index][2].insert(0, '低;高')
        dialog.rows[index][3].set(str(index + 1))
        dialog.rows[index][4].set('控制')
    assert dialog.preview()
    assert dialog.create()

    table = app.getCurrentTable()
    table.model.df['响应_Y'] = 2.0
    analysis = AnalyzeTaguchi(app)
    analysis.sn_kind.set(label)
    analysis.ln_sd.set(True)
    analysis.analyze()
    assert analysis.result is not None, error.call_args_list
    assert [analysis.tabs.tab(tab, 'text') for tab in analysis.tabs.tabs()][:2] == [
        '组合统计', 'S/N响应表']
    assert all(row['n'] == 1 and row['mean'] == 2.0 and row['sd'] is None
               and row['ln_sd'] is None and row['sn'] == pytest.approx(expected)
               for row in analysis.result['combinations'])
    assert all(level['sd'] is None for factor_row
               in analysis.result['response_table']['factors']
               for level in factor_row['levels'])
    summary = analysis.tabs.nametowidget(analysis.tabs.tabs()[0])
    stat = next(child.table for child in summary.winfo_children()
                if isinstance(child, TableBlock))
    assert 'SD' in stat.headers and 'ln(SD)' in stat.headers
    assert all(row[stat.headers.index('SD')] is None for row in stat.values)
    assert all(row[stat.headers.index('ln(SD)')] is None for row in stat.values)
    assert all(row[stat.headers.index('SD')] == '*'
               and row[stat.headers.index('ln(SD)')] == '*'
               for row in stat.display)

    path = tmp_path / f'{kind}.dexpl'
    assert app._save_project(path)
    assert app.load_file(path)
    name = next(sheet_name for sheet_name, item in app.sheets.items()
                if item.doe_metadata
                and item.doe_metadata['design']['design_type'] == 'taguchi')
    app.nb.select(app.sheetframes[name])
    reopened = AnalyzeTaguchi(app)
    assert reopened.sn_kind.get() == label
    assert reopened.ln_sd.get() is True
    reopened.analyze()
    assert reopened.result is not None, error.call_args_list
    assert all(row['sd'] is None for row in reopened.result['combinations'])
    assert error.call_count == 0
    analysis.main.destroy()
    reopened.main.destroy()


def test_target_mean_gui_reports_complete_tied_combinations_and_confirmation_state(
        csv_app, monkeypatch):
    from stat_table import TableBlock

    app, error = csv_app
    monkeypatch.setattr('doe_taguchi_dialog.messagebox.showerror', error)
    monkeypatch.setattr('doe_taguchi_analysis_dialog.messagebox.showerror', error)
    dialog = CreateTaguchi(app)
    dialog.array.set('L4(2^3)')
    dialog.factor_count.set('2')
    dialog.update_rows()
    for index in range(2):
        dialog.rows[index][2].delete(0, 'end')
        dialog.rows[index][2].insert(0, '低;高')
        dialog.rows[index][3].set(str(index + 1))
        dialog.rows[index][4].set('控制')
    dialog.replicates.delete(0, 'end')
    dialog.replicates.insert(0, '2')
    assert dialog.create()
    table = app.getCurrentTable()
    means = {
        ('低', '低'): 8.0, ('低', '高'): 20.0,
        ('高', '低'): 20.0, ('高', '高'): 32.0,
    }
    spreads = {
        ('低', '低'): 1.0, ('低', '高'): 1.0,
        ('高', '低'): 1.0, ('高', '高'): 100.0,
    }
    table.model.df['响应_Y'] = [
        means[(row['设定_A'], row['设定_B'])]
        + (-1.0 if row['重复'] == 1 else 1.0)
        * spreads[(row['设定_A'], row['设定_B'])] / (2 ** 0.5)
        for _, row in table.model.df.iterrows()]

    analysis = AnalyzeTaguchi(app)
    analysis.analyze()
    analysis.best_metric.set('目标均值')
    analysis.best_target.delete(0, 'end')
    analysis.best_target.insert(0, '20')
    analysis.best()
    result = analysis.best_window.result
    assert result['best'] == {'A': '低', 'B': '高'}
    assert result['predicted_mean'] == pytest.approx(20.0)
    assert len(result['tied_combinations']) == 2
    assert result['is_observed'] is True
    assert '该组合已在实验中观测' in result['status']
    assert [analysis.best_window.tabs.tab(tab, 'text')
            for tab in analysis.best_window.tabs.tabs()] == [
                '推荐水平', '预测与确认', '目标最优组合']
    frame = analysis.best_window.tabs.nametowidget(
        analysis.best_window.tabs.tabs()[2])
    block = next(child for child in frame.winfo_children()
                 if isinstance(child, TableBlock))
    assert [row[1] for row in block.table.values] == [
        'A=低；B=高', 'A=高；B=低']
    assert block.table.values[0][2] == pytest.approx(20.0)
    analysis.best_window.main.destroy()

    analysis.best_target.delete(0, 'end')
    analysis.best_target.insert(0, '8')
    analysis.best()
    negative = analysis.best_window
    assert negative.result['predicted_sd'] is None
    summary = negative.tabs.nametowidget(negative.tabs.tabs()[1])
    block = next(child for child in summary.winfo_children()
                 if isinstance(child, TableBlock))
    rows = dict(block.table.values)
    assert rows['预测 SD'] == '不可用'
    assert '加性主效应预测为负' in rows['SD 说明']
    assert error.call_count == 0
    negative.main.destroy()
    analysis.main.destroy()


def test_taguchi_f1_help_and_cancel(csv_app, monkeypatch):
    app, _ = csv_app
    help_open = Mock()
    monkeypatch.setattr('doe_taguchi_dialog.open_help', help_open)
    dialog = CreateTaguchi(app)
    assert '<Key-F1>' in dialog.main.bind()
    dialog.main.update()
    dialog.main.focus_force()
    dialog.main.event_generate('<F1>')
    dialog.main.update()
    help_open.assert_called_once_with('doe.taguchi', parent=dialog.main)
    names = list(app.sheets)
    dialog.cancel_button.invoke()
    assert list(app.sheets) == names


def test_taguchi_invalid_input_does_not_create_sheet(csv_app, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr('doe_taguchi_dialog.messagebox.showerror', error)
    names = list(app.sheets)
    dialog = CreateTaguchi(app)
    configure_static(dialog)
    dialog.rows[0][4].set('信号')
    assert dialog.preview() is False
    dialog.rows[0][4].set('控制')
    dialog.rows[1][3].set('1')
    assert dialog.preview() is False
    assert list(app.sheets) == names
    assert error.call_count == 2
    dialog.main.destroy()


def test_l18_gui_rejects_nonorthogonal_selected_columns(csv_app, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr('doe_taguchi_dialog.messagebox.showerror', error)
    names = list(app.sheets)
    dialog = CreateTaguchi(app)
    dialog.array.set('L18(2^1 3^7)')
    dialog.factor_count.set('2')
    dialog.update_rows()
    for index, column_number in enumerate(('3', '8')):
        dialog.rows[index][2].delete(0, 'end')
        dialog.rows[index][2].insert(0, '低;中;高')
        dialog.rows[index][3].set(column_number)
        dialog.rows[index][4].set('控制')
    assert dialog.preview() is False
    assert '3/8' in error.call_args.args[1]
    assert list(app.sheets) == names
    dialog.main.destroy()


def test_l8_two_factor_subset_is_explained_and_valid_three_column_subset_works(
        csv_app, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr('doe_taguchi_dialog.messagebox.showerror', error)
    names = list(app.sheets)
    dialog = CreateTaguchi(app)
    dialog.factor_count.set('2')
    dialog.array.set('L18(2^1 3^7)')
    dialog.update_rows()
    assert '所选控制列会产生重复设定' in dialog.limit_label.cget('text')

    dialog.array.set('L8(2^7)')
    dialog.factor_count.set('3')
    dialog.update_rows()
    assert '不能区分全部 8 行' in dialog.limit_label.cget('text')
    dialog.factor_count.set('2')
    dialog.update_rows()
    assert '四种 2×2 组合各重复 2 次' in dialog.limit_label.cget('text')
    for index, column_number in enumerate(('1', '2')):
        _, _, levels, column, role = dialog.rows[index]
        levels.delete(0, 'end')
        levels.insert(0, '低;高')
        column.set(column_number)
        role.set('控制')

    assert dialog.preview() is False
    message = error.call_args.args[1]
    assert '四种 2×2 组合各重复 2 次' in message
    assert '每行设定唯一' in message
    assert dialog.limit_label.cget('text') == message
    assert list(app.sheets) == names

    dialog.factor_count.set('3')
    dialog.update_rows()
    _, _, levels, column, role = dialog.rows[2]
    levels.delete(0, 'end')
    levels.insert(0, '低;高')
    column.set('4')
    role.set('控制')
    dialog.update_rows()
    assert dialog.limit_label.cget('text') == ''
    assert dialog.preview() is True
    assert '运行 8 次；L8(2^7)' in dialog.preview_text.get('1.0', 'end')
    assert dialog.create() is True

    frame = app.getCurrentTable().model.df
    assert len(frame) == 8
    assert len(set(zip(frame['设定_A'], frame['设定_B'], frame['设定_C']))) == 8
    assert error.call_count == 1


def test_dynamic_design_requires_signal_and_roundtrips(csv_app, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr('doe_taguchi_dialog.messagebox.showerror', error)
    dialog = CreateTaguchi(app, dynamic=True)
    dialog.array.set('L4(2^3)')
    dialog.factor_count.set('3')
    dialog.update_rows()
    dialog.rows[0][3].set('1')
    dialog.rows[1][3].set('2')
    dialog.rows[2][3].set('')
    for index in (0, 1):
        dialog.rows[index][2].delete(0, 'end')
        dialog.rows[index][2].insert(0, '低;高')
    dialog.rows[2][1].set('数值')
    dialog.rows[2][2].delete(0, 'end')
    dialog.rows[2][2].insert(0, '1;2;3')
    dialog.rows[2][4].set('信号')
    assert dialog.preview() is True, error.call_args_list
    assert '运行 12 次' in dialog.preview_text.get('1.0', 'end')
    assert dialog.create() is True
    table = app.getCurrentTable()
    assert table.doe_metadata['design']['taguchi']['kind'] == 'dynamic'
    assert table.doe_metadata['design']['taguchi']['signal_factor'] == 'C'
    frame = table.model.df
    assert set(frame['设定_C']) == {1.0, 2.0, 3.0}
    assert error.call_count == 0

    response = frame.columns.get_loc('响应_Y')
    for index, row in frame.iterrows():
        slope = 2.0 if row['设定_A'] == '低' else 5.0
        table.model.setValueAt(
            str(1.0 + slope * row['设定_C']
                + (0.3 if int(row['设定_C']) % 2 else -0.2)), index, response)

    analysis = AnalyzeTaguchi(app)
    analysis.analyze()
    assert analysis.result is not None, error.call_args_list
    assert analysis.result['kind'] == 'dynamic'
    assert [analysis.tabs.tab(tab, 'text') for tab in analysis.tabs.tabs()][0] == '动态拟合'
    assert {row['df'] for row in analysis.result['combinations']} == {1}
    analysis.plot()
    assert table.pf is not None
    assert table.pf.fig.axes[0].get_title() == 'Signal vs Response'
    # 散点 + 拟合线成对出现，确认拟合线已绘制
    assert len(table.pf.fig.axes[0].lines) == 2 * min(
        6, len(analysis.result['combinations']))

    analysis.best_metric.set('目标斜率')
    analysis.best_target.delete(0, 'end')
    analysis.best_target.insert(0, '4')
    analysis.best()
    assert analysis.best_window.result['metric'] == 'slope'
    assert analysis.best_window.result['best']['A'] == '高'
    analysis.best_window.main.destroy()
    analysis.main.destroy()
    assert error.call_count == 0


def test_noise_robustness_window_reports_control_levels(csv_app, monkeypatch):
    from doe_taguchi_analysis_dialog import NoiseTaguchi
    from doe_taguchi_analysis import noise_robustness
    from doe_taguchi import create_taguchi
    from doe_taguchi_arrays import ARRAYS
    from doe_core import DesignSpec, FactorSpec, restore_design_result
    app, error = csv_app
    monkeypatch.setattr('doe_taguchi_analysis_dialog.messagebox.showerror', error)
    factors = tuple(FactorSpec(chr(65 + index), chr(65 + index), None, None,
                               factor_type='categorical', levels=('低', '高'),
                               level_type='text') for index in range(3))
    spec = DesignSpec('TG', factors, ('Y',), seed=8, design_type='taguchi',
                      taguchi={'kind': 'static', 'array_id': 'L4(2^3)',
                               'matrix_sha256': ARRAYS['L4(2^3)'].sha256,
                               'columns': {'A': 1, 'B': 3},
                               'noise_array_id': 'L4(2^3)',
                               'noise_matrix_sha256': ARRAYS['L4(2^3)'].sha256,
                               'noise_columns': {'C': 2}, 'signal_factor': None})
    frame, metadata = create_taguchi(spec)
    design = restore_design_result(frame, metadata)
    values = {run.run_id: 10.0 + (4.0 if run.settings['A'] == '低' else 1.0)
              * (1 if run.settings['C'] == '高' else 0) for run in design.runs}
    frame['响应_Y'] = [values[run_id] for run_id in frame['运行ID']]
    app.addSheet('Taguchi', frame, {'doe': metadata})

    analysis = AnalyzeTaguchi(app)
    analysis.noise()
    window = analysis.noise_window
    assert window.main.title() == 'Taguchi 噪声稳健性'
    assert [window.tabs.tab(tab, 'text') for tab in window.tabs.tabs()] == [
        '控制设定', '因子水平 S/N', 'Delta/Rank']
    assert window.result['response_table']['best']['A'] == '高'
    window.main.destroy()
    analysis.main.destroy()
    assert error.call_count == 0


@pytest.mark.parametrize('label, expected', [
    ('Smaller is better', -6.020599913279624),
    ('Larger is better', 6.020599913279624),
])
def test_noise_window_displays_zero_sd_and_valid_sn(csv_app, monkeypatch, label, expected):
    from doe_taguchi import create_taguchi
    from test_doe_taguchi_noise import inner_outer_spec

    app, error = csv_app
    monkeypatch.setattr('doe_taguchi_analysis_dialog.messagebox.showerror', error)
    frame, metadata = create_taguchi(inner_outer_spec())
    frame['响应_Y'] = 2.0
    app.addSheet('Taguchi', frame, {'doe': metadata})
    analysis = AnalyzeTaguchi(app)
    analysis.sn_kind.set(label)
    analysis.noise()
    window = analysis.noise_window
    tab = window.tabs.nametowidget(window.tabs.tabs()[0])
    values = next(child.table.values for child in tab.winfo_children()
                  if hasattr(child, 'table'))
    assert len(values) == 4
    assert all(row[4] == 0 and row[5] == pytest.approx(expected, abs=1e-10)
               for row in values)
    assert error.call_count == 0
    window.main.destroy()
    analysis.main.destroy()
