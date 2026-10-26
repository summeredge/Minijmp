"""真实 Tk 菜单、后台生命周期、来源快照和导出。"""
from concurrent.futures import Future
import time
from unittest.mock import Mock

import numpy as np
import pandas as pd
from PIL import Image, ImageGrab
import pytest

from capability_dialog import CapabilityDialog
from sheet_context import export_source_labels


def create(tk_root, monkeypatch, mode='正态能力'):
    from MiniJMP import Minijmp
    monkeypatch.setattr(Minijmp, 'start_logging', lambda self: None)
    app = Minijmp(parent=tk_root)
    data = pd.DataFrame({'测量': np.random.default_rng(239).lognormal(1, .25, 80),
                         '批次': np.repeat(['A'+str(i) for i in range(20)], 4),
                         '阶段': ['改善前'] * 40 + ['改善后'] * 40,
                         '时间': np.arange(1, 81)})
    data.index = pd.Index([f'{i:018d}' for i in range(len(data))])
    source = app.addSheet('能力来源', data.copy(deep=True))
    dialog = CapabilityDialog(source, data, app, mode=mode)
    dialog.error = Mock()
    dialog.fields['measurement'].set('测量')
    dialog.fields['lsl'].set('1')
    dialog.fields['usl'].set('6')
    return dialog, app, source, data


def finish(root, dialog):
    deadline = time.monotonic() + 45
    while dialog.future is not None and time.monotonic() < deadline:
        root.update()
        time.sleep(.01)
    assert dialog.future is None
    dialog.error.assert_not_called()


def dispose(app):
    for name, table in list(app.sheets.items()):
        app._dispose_sheet(table, app.sheetframes[name])
    app.nb.destroy()
    app.main.configure(menu='')
    app.destroy()


@pytest.mark.parametrize('mode', ['正态能力', '非正态能力', '变换诊断', '正态 Sixpack', '非正态 Sixpack'])
def test_real_sheet_fit_plot_export_and_report(tk_root, monkeypatch, tmp_path, mode):
    dialog, app, source, data = create(tk_root, monkeypatch, mode)
    try:
        if mode == '变换诊断':
            dialog.fields['lsl'].set('')
            dialog.fields['usl'].set('')
        dialog.fit()
        finish(tk_root, dialog)
        assert dialog.result is not None and dialog.tables
        pd.testing.assert_frame_equal(source.model.df, data)
        dialog.main.update()
        first_tab = dialog.notebook.nametowidget(dialog.notebook.tabs()[0])
        block = first_tab.winfo_children()[0]
        assert block.tree.master.winfo_width() >= dialog.main.winfo_width()*.85
        ImageGrab.grab(window=dialog.main.winfo_id()).save(tmp_path/'result-dialog.png')
        other = app.addSheet('另一表', pd.DataFrame({'x': [1, 2]}))
        assert dialog.app.getCurrentTable() is source
        source.model.df.iloc[0, 0] = 999
        assert dialog.df.iloc[0, 0] != 999
        dialog.plot()
        dialog.error.assert_not_called()
        assert source.pf is not None and getattr(other, 'pf', None) is None
        from matplotlib.backend_bases import MouseEvent
        viewer = source.pf
        tk_root.update()
        viewer.canvas.draw()
        axes = viewer.fig.axes[0]
        original_limits = axes.get_xlim()
        viewer.navigation.zoom()
        assert 'zoom' in str(viewer.navigation.mode).lower()
        points = [axes.transAxes.transform((.2, .2)), axes.transAxes.transform((.8, .8))]
        for name, point in [('button_press_event', points[0]), ('motion_notify_event', points[1]),
                            ('button_release_event', points[1])]:
            event = MouseEvent(name, viewer.canvas, *point,
                               **({'buttons': {1}} if name == 'motion_notify_event' else {'button': 1}))
            assert event.inaxes is axes
            viewer.canvas.callbacks.process(name, event)
        assert np.diff(axes.get_xlim())[0] < np.diff(original_limits)[0]
        viewer.navigation.zoom()
        viewer.navigation.home()
        np.testing.assert_allclose(axes.get_xlim(), original_limits)
        path = tmp_path/'capability.png'
        source.pf.savePlot(str(path))
        with Image.open(path) as image:
            assert image.width >= 600
            image.verify()
        if 'Sixpack' in mode:
            assert len(source.pf.fig.axes) == 6
        observation_title = next((title for title, item in dialog.tables.items()
                                  if 'source_row' in item), None)
        if observation_title is not None:
            tab = next(tab for tab, title in dialog.blocks.items() if title == observation_title)
            dialog.notebook.select(tab)
        _, frame = dialog.current_table()
        for suffix in ['csv', 'xlsx']:
            destination = tmp_path/f'capability.{suffix}'
            monkeypatch.setattr('capability_dialog.filedialog.asksaveasfilename', lambda **kw: str(destination))
            dialog.export()
            label_types = {'source_index': str, 'subgroup_id': str}
            loaded = (pd.read_csv(destination, dtype=label_types) if suffix == 'csv' else
                      pd.read_excel(destination, dtype=label_types))
            assert list(loaded.columns) == list(frame.columns)
            assert loaded.shape == frame.shape
            for column in frame.select_dtypes(include='number'):
                np.testing.assert_allclose(pd.to_numeric(loaded[column]), frame[column], rtol=1e-12, equal_nan=True)
            assert loaded['source_index'].tolist() == frame['source_index'].tolist()
        dialog.to_sheet()
        pd.testing.assert_frame_equal(app.table.model.df, export_source_labels(frame))
        app.print = Mock()
        dialog.report()
        assert app.print.call_count > 1
        assert all(call.kwargs['table'] is source for call in app.print.call_args_list)
        assert source.model.df.iloc[0, 0] == 999
        pd.testing.assert_frame_equal(dialog.df, data)
    finally:
        dialog.close()
        dispose(app)


def test_cancel_failure_close_and_small_window(tk_root, monkeypatch, tmp_path):
    dialog, app, source, _ = create(tk_root, monkeypatch)
    try:
        dialog.main.geometry('760x580')
        dialog.main.update()
        assert dialog.fit_button.winfo_rooty() + dialog.fit_button.winfo_height() <= dialog.main.winfo_rooty()+580
        previous = dialog.result = object()
        dialog.future = Future()
        dialog.cancel()
        dialog.future.set_result({})
        dialog.poll()
        assert dialog.result is previous and '已取消' in dialog.status.get()
        dialog.fields['measurement'].set('不存在')
        dialog.fit()
        assert dialog.error.called
        dialog.error.reset_mock()
        dialog.fields['measurement'].set('测量')
        source.destroy()
        dialog.fit()
        assert '来源工作表已关闭' in str(dialog.error.call_args.args[0])
    finally:
        dialog.close()
        dispose(app)


@pytest.mark.parametrize('subgroup,size', [('批次', '1'), ('', '4')])
def test_subgroups_single_spec_and_confidence(tk_root, monkeypatch, subgroup, size):
    dialog, app, source, data = create(tk_root, monkeypatch, '正态 Sixpack')
    try:
        dialog.fields['subgroup'].set(subgroup)
        dialog.fields['size'].set(size)
        dialog.fields['lsl'].set('')
        dialog.fields['confidence'].set('90')
        dialog.fields['k'].set('5')
        dialog.fit()
        finish(tk_root, dialog)
        assert len(dialog.result['groups']) == 20
        assert dialog.result['indices']['Cp'] is None
        assert dialog.result['target'] is None
        assert dialog.result['k'] == 5
        dialog.plot()
        dialog.error.assert_not_called()
        assert source.pf.fig.axes[0].get_title().startswith('Xbar')
        pd.testing.assert_frame_equal(source.model.df, data)
    finally:
        dialog.close()
        dispose(app)


@pytest.mark.parametrize('distribution,transform', [('Lognormal', '无'), ('Gamma', '无'),
                                                  ('Weibull', 'Johnson SU')])
def test_distribution_and_johnson_gui_options(tk_root, monkeypatch, distribution, transform):
    from scipy import stats
    mode = '变换诊断' if transform == 'Johnson SU' else '非正态能力'
    dialog, app, source, data = create(tk_root, monkeypatch, mode)
    try:
        dialog.fields['distribution'].set(distribution)
        dialog.fields['transform'].set(transform)
        if transform == 'Johnson SU':
            q = stats.norm.ppf((np.arange(1, 81)-.5)/80)
            data['测量'] = -2+2.5*np.sinh((q-.7)/1.3)
            source.model.df = data.copy(deep=True)
            dialog.df = data.copy(deep=True)
            dialog.fields['lsl'].set('-10')
            dialog.fields['usl'].set('3')
        dialog.fit()
        finish(tk_root, dialog)
        dialog.plot()
        dialog.error.assert_not_called()
        assert len(source.pf.fig.axes) == (4 if transform == 'Johnson SU' else 2)
        pd.testing.assert_frame_equal(source.model.df, data)
    finally:
        dialog.close()
        dispose(app)


def test_quality_menu_opens_all_five_dialogs(tk_root, monkeypatch, tmp_path):
    dialog, app, source, _ = create(tk_root, monkeypatch)
    dialog.close()
    opened = []
    original = CapabilityDialog.__init__
    def capture(self, *args, **kwargs):
        original(self, *args, **kwargs)
        opened.append(self)
    monkeypatch.setattr(CapabilityDialog, '__init__', capture)
    try:
        menu = app.quality_menu['var']
        wanted = ['正态过程能力（完整）', '非正态过程能力', 'Box-Cox / Johnson 变换',
                  '正态能力 Sixpack', '非正态能力 Sixpack']
        for label in wanted:
            index = next(i for i in range(menu.index('end')+1)
                         if menu.type(i) == 'command' and menu.entrycget(i, 'label').strip() == label)
            menu.invoke(index)
            assert opened[-1].main.winfo_exists()
            opened[-1].main.update()
        screenshot = tmp_path/'capability-dialog.png'
        ImageGrab.grab(window=opened[-1].main.winfo_id()).save(screenshot)
        with Image.open(screenshot) as image:
            assert image.width >= 760 and image.height >= 580
    finally:
        for window in opened:
            window.close()
        dispose(app)


def test_split_combobox_choices_drive_real_analysis(tk_root, monkeypatch):
    """下拉框显示名与内部键分离；两种划分方式都能真实执行分析。"""
    import improvement_chart
    dialog, app, source, data = create(tk_root, monkeypatch)
    try:
        dialog.stage_compare.set(True)
        dialog.toggle_compare()
        dialog.main.update()
        box = dialog.compare_widgets['compare_split']
        # 显示名是中文标签，不是内部 stage/time 键。
        assert tuple(box.cget('values')) == tuple(improvement_chart.SPLITS.values())
        assert box.get() == '阶段列'
        assert dialog.split_mode() == 'stage'
        assert str(dialog.compare_widgets['compare_stage'].cget('state')) == 'readonly'
        for key in ('compare_time', 'compare_cutoff'):
            assert str(dialog.compare_widgets[key].cget('state')) == 'disabled'

        # 阶段列：按实际出现顺序拆分，忽略列表中的时间设置。
        dialog.fields['missing'].set('删除不完整行')
        dialog.compare_stage.set('阶段')
        dialog.fit()
        finish(tk_root, dialog)
        by_stage = dialog.result
        assert [len(stage['data']) for stage in by_stage.plot['results']] == [40, 40]
        assert by_stage.tables['数据与规格摘要'].set_index('项目').at['阶段划分', '内容'] \
            == '阶段列'

        # 切到时间分界点：字段状态反转，并按分界值拆分。
        box.set('时间分界点')
        dialog.main.update()
        assert dialog.split_mode() == 'time'
        assert str(dialog.compare_widgets['compare_stage'].cget('state')) == 'disabled'
        for key in ('compare_time', 'compare_cutoff'):
            assert str(dialog.compare_widgets[key].cget('state')) == 'normal'
        dialog.compare_time.set('时间')
        dialog.compare_cutoff.set('41')
        dialog.fit()
        finish(tk_root, dialog)
        by_time = dialog.result
        assert [len(stage['data']) for stage in by_time.plot['results']] == [40, 40]
        summary = by_time.tables['数据与规格摘要'].set_index('项目')
        assert summary.at['阶段划分', '内容'] == '时间分界点'
        assert '分界 = 41' in summary.at['阶段定义', '内容']

        # 阶段划分不同，但同一批行的能力指数应一致（只换拆分入口）。
        np.testing.assert_allclose(
            by_stage.tables['能力指数对比'].set_index('指标')[['改善前', '改善后']]
            .loc[['Cpk', 'Ppk']].astype(float),
            by_time.tables['能力指数对比'].set_index('指标')[['改善前', '改善后']]
            .loc[['Cpk', 'Ppk']].astype(float))

        # 未知选项直接报错，不隐式归为时间模式。
        dialog.compare_split.set('阶段')
        dialog.fit()
        assert '未知的阶段划分方式' in str(dialog.error.call_args.args[0])
        dialog.error.reset_mock()
        pd.testing.assert_frame_equal(source.model.df, data)
    finally:
        dialog.close()
        dispose(app)


def test_stage_comparison_defaults_off_then_switches_result(tk_root, monkeypatch, tmp_path):
    """默认关闭；勾选后展开设置，结果与图形切换为阶段对比。"""
    dialog, app, source, data = create(tk_root, monkeypatch)
    try:
        dialog.main.update()
        assert dialog.stage_compare.get() is False
        assert not dialog.compare_frame.winfo_manager()
        dialog.fields['lsl'].set('')
        dialog.fields['usl'].set('6')
        dialog.fit()
        finish(tk_root, dialog)
        # 未勾选时仍是原有单阶段结果与控制图诊断。
        assert isinstance(dialog.result, dict)
        assert '控制图诊断' in dialog.tables
        assert '能力指数对比' not in dialog.tables

        dialog.stage_compare.set(True)
        dialog.toggle_compare()
        dialog.main.update()
        assert dialog.compare_frame.winfo_manager() == 'pack'
        assert str(dialog.compare_widgets['compare_time'].cget('state')) == 'disabled'
        dialog.fields['missing'].set('删除不完整行')
        dialog.compare_stage.set('阶段')
        dialog.fit()
        finish(tk_root, dialog)
        assert '能力指数对比' in dialog.tables
        assert '控制图诊断' not in dialog.tables
        pd.testing.assert_frame_equal(source.model.df, data)

        dialog.plot()
        dialog.error.assert_not_called()
        viewer = source.pf
        tk_root.update()
        viewer.canvas.draw()
        assert [ax.get_title() for ax in viewer.fig.axes][:2] == [
            name + '能力直方图' for name in dialog.result.plot['names']]
        low, high = viewer.fig.axes[0].get_xlim()
        assert viewer.fig.axes[1].get_xlim() == (low, high)
        path = tmp_path / 'comparison.png'
        viewer.savePlot(str(path))
        with Image.open(path) as image:
            assert image.width >= 600
            image.verify()

        app.print = Mock()
        dialog.report()
        output = '\n'.join(call.args[0] for call in app.print.call_args_list if call.args)
        assert '改善前后过程能力分析报告' in output
        assert '能力指数前后比较' in output
        assert all(call.kwargs['table'] is source for call in app.print.call_args_list)

        destination = tmp_path / 'comparison.xlsx'
        monkeypatch.setattr('capability_dialog.filedialog.asksaveasfilename',
                            lambda **kw: str(destination))
        dialog.notebook.select(next(tab for tab, title in dialog.blocks.items()
                                   if title == '能力指数对比'))
        dialog.export()
        loaded = pd.read_excel(destination)
        assert list(loaded.columns) == list(dialog.tables['能力指数对比'].columns)

        dialog.fields['transform'].set('Box-Cox')
        dialog.stage_compare.set(True)
        dialog.fit()
        assert '原始测量尺度' in str(dialog.error.call_args.args[0])
        dialog.error.reset_mock()
    finally:
        dialog.close()
        dispose(app)
