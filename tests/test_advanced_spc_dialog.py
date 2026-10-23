"""真实 Tk 高级 SPC 连接、来源归属、输出和异步生命周期。"""
from concurrent.futures import Future
from threading import Event, get_ident
from unittest.mock import Mock
import time

from matplotlib.backend_bases import MouseEvent
import numpy as np
import pandas as pd
import pytest
from PIL import Image

from MiniJMP import Minijmp
from advanced_spc_dialog import AdvancedSPCDialog, CURRENT, display_frame, export_frame
from stat_table import StatTable
from test_regression_dialog import dispose


def make_dialog(tk_root, monkeypatch):
    monkeypatch.setattr(Minijmp, 'start_logging', lambda self: None)
    app = Minijmp(parent=tk_root)
    rng = np.random.default_rng(8503)
    values = rng.normal(size=(60, 2))
    values[35:] += 2.5
    data = pd.DataFrame(values, columns=['X', 'Y'])
    source = app.addSheet('SPC来源', data.copy(deep=True))
    baseline_data = pd.DataFrame(rng.normal(size=(80, 2)), columns=['X', 'Y'])
    baseline = app.addSheet('独立历史', baseline_data.copy(deep=True))
    # 创建窗口时活动表已经不同；parent 仍标识真正来源。
    dialog = AdvancedSPCDialog(source, data, app)
    dialog.error = Mock()
    dialog.x_list.selection_set(0)
    return dialog, app, source, baseline, data, baseline_data


def finish(tk_root, dialog):
    deadline = time.monotonic()+30
    while dialog.future is not None and time.monotonic() < deadline:
        tk_root.update()
        time.sleep(.01)
    assert dialog.future is None, '后台计算未在30秒内结束'
    dialog.error.assert_not_called()


def click(viewer, axis, x, y):
    pixel = axis.transData.transform((x, y))
    event = MouseEvent('button_press_event', viewer.canvas, *pixel, button=1)
    viewer.canvas.callbacks.process('button_press_event', event)


@pytest.mark.parametrize('kind,label', [('EWMA', 'EWMA'), ('CUSUM', 'CUSUM'),
                                        ('Nelson', 'Nelson'), ('T2', 'Hotelling T²')])
def test_four_kinds_history_report_plot_and_source(tk_root, monkeypatch, tmp_path, kind, label):
    dialog, app, source, baseline, data, baseline_data = make_dialog(tk_root, monkeypatch)
    try:
        dialog.fields['kind'].set(label)
        dialog.fields['baseline'].set('历史：独立历史')
        dialog.fields['confidence'].set('99')
        if kind == 'T2':
            dialog.x_list.selection_set(1)
        dialog.analyze()
        finish(tk_root, dialog)
        assert dialog.result.kind == kind
        assert {'summary', 'parameters', 'comparison', 'limits', 'observations', 'baseline', 'alarms'} <= dialog.tables.keys()
        summary = dialog.tables['summary'].set_index('parameter')['value']
        assert summary['phase'] == 'phase2'
        assert summary['baseline_n'] == len(baseline_data)
        np.testing.assert_allclose(dialog.tables['comparison']['baseline_mean'],
            baseline_data[['X', 'Y'] if kind == 'T2' else ['X']].mean())
        if kind == 'T2':
            assert list(display_frame(dialog.tables['covariance'])) == ['行变量', '列变量', '协方差']
            assert display_frame(dialog.tables['summary']).iloc[0]['数值'] == 'Hotelling T²'
        app.print = Mock()
        dialog.report()
        dialog.error.assert_not_called()
        assert all(call.kwargs['table'] is source for call in app.print.call_args_list)
        assert any(isinstance(call.args[0], StatTable) for call in app.print.call_args_list)
        dialog.plot()
        dialog.error.assert_not_called()
        assert source.pf is not None and getattr(baseline, 'pf', None) is None
        assert len(source.pf.fig.axes) == 2
        observed = dialog.tables['observations'].iloc[2]
        click(source.pf, source.pf.fig.axes[0], observed['sequence'], observed['statistic'])
        assert source.multiplerowlist == [2]
        historic = dialog.tables['baseline'].iloc[8]
        click(source.pf, source.pf.fig.axes[1], historic['sequence'], historic['statistic'])
        assert source.multiplerowlist == [2], '历史基线不可定位到当前来源表'
        output = tmp_path/(kind+'.png')
        source.pf.savePlot(str(output))
        with Image.open(output) as image:
            assert image.width > 300 and image.height > 200
            image.verify()
        pd.testing.assert_frame_equal(source.model.df, data)
        pd.testing.assert_frame_equal(baseline.model.df, baseline_data)
    finally:
        dialog.close()
        dispose(app)


def test_phase1_known_parameters_rules_and_compact_geometry(tk_root, monkeypatch):
    dialog, app, source, baseline, data, _ = make_dialog(tk_root, monkeypatch)
    try:
        dialog.fields['kind'].set('Hotelling T²')
        dialog.x_list.selection_set(1)
        dialog.analyze()
        finish(tk_root, dialog)
        assert 'baseline' not in dialog.tables
        assert dialog.tables['observations']['phase'].eq('phase1').all()
        dialog.fields['kind'].set('Nelson')
        dialog.x_list.selection_clear(1)
        dialog.fields['mean'].set('0')
        dialog.fields['sigma'].set('1')
        for rule, variable in dialog.rules.items():
            variable.set(rule in (1, 2))
        dialog.analyze()
        finish(tk_root, dialog)
        assert dialog.tables['observations']['phase'].eq('known').all()
        assert dialog.tables['settings']['value'].tolist() == ['1,2']
        assert set(dialog.tables['alarms']['rule']) <= {'Nelson 1', 'Nelson 2'}
        assert dialog.tables['parameters']['mean'].tolist() == [0.]
        dialog.main.geometry('900x640')
        tk_root.update()
        assert dialog.notebook.winfo_height() > 100
        assert dialog.outputs.winfo_y()+dialog.outputs.winfo_height() <= dialog.main.winfo_height()
        for widget in dialog.outputs.winfo_children():
            assert widget.winfo_ismapped()
            assert widget.winfo_x()+widget.winfo_width() <= dialog.outputs.winfo_width()
        pd.testing.assert_frame_equal(source.model.df, data)
    finally:
        dialog.close()
        dispose(app)


def test_exports_new_sheet_excel_csv_and_identifiers(tk_root, monkeypatch, tmp_path):
    dialog, app, source, baseline, data, _ = make_dialog(tk_root, monkeypatch)
    try:
        # 来源行号映射保持工作表位置；索引标签允许大整数及前导零。
        data.index = pd.Index([9007199254740993, '000001']+list(range(2, len(data))), dtype=object)
        source.model.df.index = data.index
        dialog.df = data.copy(deep=True)
        dialog.analyze()
        finish(tk_root, dialog)
        frame = dialog.tables['observations']
        dialog.notebook.select(dialog.tabs['observations'])
        path = tmp_path/'observations.xlsx'
        monkeypatch.setattr('advanced_spc_dialog.filedialog.asksaveasfilename', lambda **kw: str(path))
        dialog.export()
        actual = pd.read_excel(path, dtype={'来源索引': str})
        expected = export_frame(frame)
        assert actual['来源索引'].iloc[:2].tolist() == ['9007199254740993', '000001']
        pd.testing.assert_frame_equal(actual.fillna(''), expected.fillna(''), check_dtype=False, atol=1e-13)
        path = tmp_path/'observations.csv'
        dialog.export()
        actual = pd.read_csv(path, dtype={'来源索引': str}, encoding='utf-8-sig')
        pd.testing.assert_frame_equal(actual.fillna(''), expected.fillna(''), check_dtype=False, atol=1e-13)
        dialog.to_sheet()
        dialog.error.assert_not_called()
        assert app.table is not source and app.table is not baseline
        pd.testing.assert_frame_equal(app.table.model.df, display_frame(frame))
        block = dialog.tabs['observations'].winfo_children()[0]
        carrier = block.table
        index_column = carrier.headers.index('来源索引')
        assert [row[index_column] for row in carrier.values[:2]] == ['9007199254740993', '000001']
        # TableBlock 内建导出与报告共用的载体也必须保护来源标识。
        from stat_table import export_excel
        path = tmp_path/'table-carrier.xlsx'
        export_excel(carrier, path)
        actual = pd.read_excel(path, header=1, dtype={'来源索引': str})
        assert actual['来源索引'].iloc[:2].tolist() == ['9007199254740993', '000001']
        app.print = Mock()
        dialog.report()
        report_tables = [call.args[0] for call in app.print.call_args_list if isinstance(call.args[0], StatTable)]
        observed = next(table for table in report_tables if table.title == '当前监控观测')
        assert [row[index_column] for row in observed.values[:2]] == ['9007199254740993', '000001']
        assert observed.values[0][observed.headers.index('统计量')] == frame['statistic'].iloc[0]
        dialog.pick(4)
        assert source.multiplerowlist == [3]
        pd.testing.assert_frame_equal(source.model.df, data)
    finally:
        dialog.close()
        dispose(app)


def test_validation_and_independent_equal_data_are_allowed(tk_root, monkeypatch):
    dialog, app, source, baseline, data, _ = make_dialog(tk_root, monkeypatch)
    try:
        assert all(table is not source for table in dialog.baseline_tables.values())
        dialog.x_list.selection_clear(0, 'end')
        with pytest.raises(ValueError, match='选择'):
            dialog.options()
        dialog.x_list.selection_set(0, 1)
        with pytest.raises(ValueError, match='只选择一列'):
            dialog.options()
        dialog.x_list.selection_clear(1)
        dialog.fields['mean'].set('0')
        with pytest.raises(ValueError, match='同时填写'):
            dialog.options()
        dialog.fields['sigma'].set('1')
        dialog.fields['baseline'].set('历史：独立历史')
        with pytest.raises(ValueError, match='不可与历史基线混用'):
            dialog.options()
        dialog.fields['mean'].set('')
        dialog.fields['sigma'].set('')
        baseline.model.df = data.copy(deep=True)
        dialog.analyze()
        finish(tk_root, dialog)
        assert dialog.tables['observations']['phase'].eq('phase2').all()
        dialog.fields['baseline'].set('历史：SPC来源')
        with pytest.raises(ValueError, match='其他工作表'):
            dialog.options()
        dialog.fields['baseline'].set('历史：独立历史')
        baseline.destroy()
        with pytest.raises(ValueError, match='其他工作表'):
            dialog.options()
    finally:
        dialog.close()
        dispose(app)


def test_baseline_snapshot_worker_thread_and_cancel_keeps_result(tk_root, monkeypatch):
    import advanced_spc
    dialog, app, source, baseline, data, baseline_data = make_dialog(tk_root, monkeypatch)
    entered, release = Event(), Event()
    captured = {}
    original = advanced_spc.analyze_spc
    ui_thread = get_ident()

    def blocked(frame, **options):
        captured.update(frame=frame, options=options, thread=get_ident())
        entered.set()
        assert release.wait(10), '测试未释放后台计算'
        return original(frame, **options)

    try:
        dialog.analyze()
        finish(tk_root, dialog)
        previous = dialog.result
        monkeypatch.setattr(advanced_spc, 'analyze_spc', blocked)
        dialog.fields['baseline'].set('历史：独立历史')
        dialog.analyze()
        assert entered.wait(3)
        tk_root.update()
        assert captured['thread'] != ui_thread
        assert str(dialog.run_button['state']) == 'disabled'
        expected_baseline = baseline.model.df.copy(deep=True)
        baseline.model.df.iloc[0, 0] += 50
        pd.testing.assert_frame_equal(captured['options']['baseline'], expected_baseline)
        pd.testing.assert_frame_equal(captured['frame'], data)
        dialog.cancel()
        release.set()
        finish(tk_root, dialog)
        assert dialog.result is previous and '已取消' in dialog.status.get()
        assert str(dialog.run_button['state']) == 'normal'
        assert str(dialog.cancel_button['state']) == 'disabled'
    finally:
        release.set()
        dialog.close()
        dispose(app)


def test_missing_drop_stale_source_and_closed_source(tk_root, monkeypatch):
    dialog, app, source, baseline, data, _ = make_dialog(tk_root, monkeypatch)
    try:
        source.model.df.iloc[1, 0] = np.nan
        dialog.df = source.model.df.copy(deep=True)
        dialog.fields['missing'].set('删除不完整行')
        dialog.analyze()
        finish(tk_root, dialog)
        assert dialog.tables['observations']['source_row'].iloc[:3].tolist() == [1, 3, 4]
        dialog.pick(3)
        assert source.multiplerowlist == [2]
        source.model.df.iloc[0, 0] += 1
        dialog.pick(1)
        assert '已更改' in str(dialog.error.call_args.args[0])
        dialog.error.reset_mock()
        source.destroy()
        for action in (dialog.analyze, dialog.report, dialog.plot, dialog.to_sheet):
            action()
            assert '来源工作表已关闭' in str(dialog.error.call_args.args[0])
            dialog.error.reset_mock()
        assert dialog.future is None
    finally:
        dialog.close()
        dispose(app)


def test_plot_error_preserves_previous_viewer_and_close_stops_poll(tk_root, monkeypatch):
    dialog, app, source, baseline, _, _ = make_dialog(tk_root, monkeypatch)
    try:
        dialog.analyze()
        finish(tk_root, dialog)
        dialog.plot()
        dialog.error.assert_not_called()
        previous = source.pf
        monkeypatch.setattr('advanced_spc_plots.spc_plot', Mock(side_effect=ValueError('绘图失败')))
        dialog.plot()
        assert source.pf is previous and previous.main.winfo_exists()
        assert '绘图失败' in str(dialog.error.call_args.args[0])
        pending = dialog.future = Future()
        poll_id = dialog.poll_id
        dialog.close()
        assert dialog.cancel_event.is_set() and pending.cancelled()
        assert poll_id not in tk_root.tk.call('after', 'info')
        assert not dialog.main.winfo_exists()
    finally:
        if dialog.main.winfo_exists():
            dialog.close()
        dispose(app)
