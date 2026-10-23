"""真实 Tk 菜单、来源快照、后台取消、结果和文件导出。"""
from concurrent.futures import Future
import time
from unittest.mock import Mock
import pandas as pd
import numpy as np
from PIL import Image, ImageGrab
import pytest
from quality_tools_dialog import QualityToolsDialog
from test_capability_dialog import dispose


def finish(root, dialog):
    deadline = time.monotonic()+30
    while dialog.future is not None and time.monotonic() < deadline:
        root.update()
        time.sleep(.01)
    assert dialog.future is None
    dialog.error.assert_not_called()


def evidence(root, dialog, source, monkeypatch, path):
    dialog.main.geometry('760x580')
    root.update()
    assert dialog.fit_button.winfo_rooty()+dialog.fit_button.winfo_height() < dialog.main.winfo_rooty()+580
    assert dialog.notebook.winfo_height() >= 140
    ImageGrab.grab(window=dialog.main.winfo_id()).save(path/'dialog.png')
    viewer = source.pf
    viewer.canvas.draw()
    viewer.savePlot(str(path/'saved-via-viewer.png'))
    with Image.open(path/'saved-via-viewer.png') as image:
        image.verify()
    if dialog.kind != 'cause_effect':
        from matplotlib.backend_bases import MouseEvent
        ax = viewer.fig.axes[0]
        limits = ax.get_xlim()
        viewer.navigation.zoom()
        points = [ax.transAxes.transform((.2, .2)), ax.transAxes.transform((.8, .8))]
        for name, point in [('button_press_event', points[0]), ('motion_notify_event', points[1]), ('button_release_event', points[1])]:
            event = MouseEvent(name, viewer.canvas, *point, **({'buttons': {1}} if name == 'motion_notify_event' else {'button': 1}))
            viewer.canvas.callbacks.process(name, event)
        assert np.diff(ax.get_xlim())[0] < np.diff(limits)[0]
        viewer.navigation.zoom()
        viewer.navigation.home()
        np.testing.assert_allclose(ax.get_xlim(), limits)
    for title, frame in dialog.tables.items():
        tab = next(key for key, value in dialog.blocks.items() if value == title)
        dialog.notebook.select(tab)
        for suffix in ['csv', 'xlsx']:
            destination = path/f'{title}.{suffix}'
            monkeypatch.setattr('quality_tools_dialog.filedialog.asksaveasfilename', lambda **kw: str(destination))
            dialog.export()
            output = pd.read_csv(destination) if suffix == 'csv' else pd.read_excel(destination)
            assert output.shape == frame.shape
            for col in frame.select_dtypes(include='number'):
                np.testing.assert_allclose(output[col], frame[col], rtol=1e-14, atol=1e-15, equal_nan=True)
    before = len(dialog.app.sheets)
    dialog.to_sheet()
    assert len(dialog.app.sheets) == before+1
    assert dialog.app.getCurrentTable() is source
    dialog.error.assert_not_called()


def test_pareto_gui(tk_root, monkeypatch, tmp_path):
    from MiniJMP import Minijmp
    monkeypatch.setattr(Minijmp, 'start_logging', lambda self: None)
    app = Minijmp(tk_root)
    data = pd.DataFrame({'缺陷': ['甲', '甲', '乙', '丙']})
    source = app.addSheet('质量来源', data.copy(deep=True))
    dialog = app.pareto_chart()
    dialog.error = Mock()
    try:
        dialog.fields['category'].set('缺陷')
        dialog.fit()
        finish(tk_root, dialog)
        pd.testing.assert_frame_equal(source.model.df, data)
        app.addSheet('另一表', pd.DataFrame({'x': [0]}))
        assert dialog.app.getCurrentTable() is source
        dialog.report()
        assert source.tOut is not None
        dialog.plot()
        path = tmp_path/'pareto.png'
        source.pf.fig.savefig(path)
        assert Image.open(path).width > 500
        for suffix in ('csv', 'xlsx'):
            path = tmp_path/f'pareto.{suffix}'
            monkeypatch.setattr('quality_tools_dialog.filedialog.asksaveasfilename', lambda **kw: str(path))
            dialog.export()
            output = pd.read_csv(path) if suffix == 'csv' else pd.read_excel(path)
            assert output['频数'].tolist() == [2, 1, 1]
        dialog.main.geometry('760x580')
        dialog.main.update()
        assert dialog.fit_button.winfo_rooty()+dialog.fit_button.winfo_height() < dialog.main.winfo_rooty()+580
        ImageGrab.grab(window=dialog.main.winfo_id()).save(tmp_path/'pareto-dialog.png')
        previous = dialog.result
        dialog.future = Future()
        dialog.cancel()
        if not dialog.future.cancelled():
            dialog.future.set_result({})
        dialog.poll()
        assert dialog.result is previous and '已取消' in dialog.status.get()
        dialog.error.assert_not_called()
        evidence(tk_root, dialog, source, monkeypatch, tmp_path)
        source.destroy()
        dialog.fit()
        assert '来源工作表已关闭' in str(dialog.error.call_args.args[0])
    finally:
        dialog.close()
        dispose(app)


def test_run_gui(tk_root, monkeypatch, tmp_path):
    from MiniJMP import Minijmp
    monkeypatch.setattr(Minijmp, 'start_logging', lambda self: None)
    app = Minijmp(tk_root)
    data = pd.DataFrame({'y': list(range(40))})
    source = app.addSheet('运行来源', data.copy(deep=True))
    dialog = app.run_chart()
    dialog.error = Mock()
    try:
        dialog.fields['measurement'].set('y')
        dialog.fit()
        finish(tk_root, dialog)
        dialog.plot()
        assert len(source.pf.fig.axes[0].lines) == 2
        source.pf.fig.savefig(tmp_path/'run.png')
        assert Image.open(tmp_path/'run.png').width > 500
        dialog.report()
        pd.testing.assert_frame_equal(data, source.model.df)
        evidence(tk_root, dialog, source, monkeypatch, tmp_path)
    finally:
        dialog.close()
        dispose(app)


def test_cause_editor_gui(tk_root, monkeypatch, tmp_path):
    from MiniJMP import Minijmp
    monkeypatch.setattr(Minijmp, 'start_logging', lambda self: None)
    app = Minijmp(tk_root)
    data = pd.DataFrame({'cat': ['机'], 'cause': ['设备磨损'], 'sub': ['维护周期过长']})
    source = app.addSheet('鱼骨来源', data.copy(deep=True))
    dialog = app.cause_effect()
    dialog.error = Mock()
    try:
        dialog.fields['problem'].set('不良率增加')
        dialog.node_text.set('自定义')
        dialog.add_cause(root=True)
        category = dialog.causes.get_children('')[-1]
        dialog.causes.selection_set(category)
        dialog.node_text.set('主原因')
        dialog.add_cause()
        cause = dialog.causes.get_children(category)[0]
        dialog.causes.selection_set(cause)
        dialog.node_text.set('次原因')
        dialog.add_cause()
        dialog.node_text.set('修改原因')
        dialog.rename_cause()
        assert dialog.causes.item(cause, 'text') == '修改原因'
        for key, value in [('category_col', 'cat'), ('cause_col', 'cause'), ('subcause_col', 'sub')]:
            dialog.fields[key].set(value)
        dialog.import_causes()
        dialog.fit()
        finish(tk_root, dialog)
        assert '维护周期过长' in dialog.tables['原因结构']['子原因'].tolist()
        dialog.plot()
        source.pf.fig.savefig(tmp_path/'fishbone.png')
        assert Image.open(tmp_path/'fishbone.png').width > 1000
        evidence(tk_root, dialog, source, monkeypatch, tmp_path)
        dialog.causes.selection_set(category)
        dialog.delete_cause()
        dialog.fit()
        finish(tk_root, dialog)
        assert '自定义' not in dialog.tables['原因结构']['类别'].tolist()
        pd.testing.assert_frame_equal(data, source.model.df)
    finally:
        dialog.close()
        dispose(app)


def test_multivari_gui(tk_root, monkeypatch, tmp_path):
    from MiniJMP import Minijmp
    monkeypatch.setattr(Minijmp, 'start_logging', lambda self: None)
    app = Minijmp(tk_root)
    data = pd.DataFrame({'y': [1, 3, 5, 7], 'a': ['A', 'A', 'B', 'B'], 'b': ['X', 'Y', 'X', 'Y']})
    source = app.addSheet('多变异来源', data.copy(deep=True))
    dialog = app.multi_vari()
    dialog.error = Mock()
    try:
        for key, value in [('response', 'y'), ('factor1', 'a'), ('factor2', 'b')]:
            dialog.fields[key].set(value)
        dialog.fit()
        finish(tk_root, dialog)
        dialog.plot()
        assert len(source.pf.fig.axes[0].lines) == 2
        source.pf.fig.savefig(tmp_path/'multi.png')
        dialog.report()
        pd.testing.assert_frame_equal(data, source.model.df)
        evidence(tk_root, dialog, source, monkeypatch, tmp_path)
    finally:
        dialog.close()
        dispose(app)


@pytest.mark.parametrize('standard', [False, True])
def test_attribute_gui(tk_root, monkeypatch, tmp_path, standard):
    from MiniJMP import Minijmp
    from test_attribute_agreement import long_data
    monkeypatch.setattr(Minijmp, 'start_logging', lambda self: None)
    app = Minijmp(tk_root)
    data = long_data([[0, 0, 0, 0], [1, 1, 1, 1], [2, 2, 1, 2]]*12, trials=2, standard=[0, 1, 2]*12)
    source = app.addSheet('属性来源', data.copy(deep=True))
    dialog = app.attribute_agreement()
    dialog.error = Mock()
    try:
        for key in ('sample', 'appraiser', 'response', 'trial'):
            dialog.fields[key].set(key)
        if standard:
            dialog.fields['standard'].set('standard')
        dialog.fields['scale'].set('有序')
        dialog.fields['order'].set('0,1,2')
        dialog.fit()
        finish(tk_root, dialog)
        assert dialog.result['has_standard'] == standard
        dialog.plot()
        assert len(source.pf.fig.axes) == (2 if standard else 1)
        source.pf.fig.savefig(tmp_path/'attribute.png')
        assert Image.open(tmp_path/'attribute.png').width > 500
        dialog.report()
        for title, frame in dialog.tables.items():
            tab = next(key for key, value in dialog.blocks.items() if value == title)
            dialog.notebook.select(tab)
            for suffix in ['csv', 'xlsx']:
                path = tmp_path/f'{title}.{suffix}'
                monkeypatch.setattr('quality_tools_dialog.filedialog.asksaveasfilename', lambda **kw: str(path))
                dialog.export()
                output = pd.read_csv(path) if suffix == 'csv' else pd.read_excel(path)
                assert list(output.columns) == list(frame.columns)
                assert len(output) == len(frame)
        dialog.error.assert_not_called()
        pd.testing.assert_frame_equal(data, source.model.df)
        evidence(tk_root, dialog, source, monkeypatch, tmp_path)
    finally:
        dialog.close()
        dispose(app)


def test_running_cancel_and_close_discard_late_result(tk_root, monkeypatch):
    from MiniJMP import Minijmp
    from threading import Event
    monkeypatch.setattr(Minijmp, 'start_logging', lambda self: None)
    app = Minijmp(tk_root)
    source = app.addSheet('取消来源', pd.DataFrame({'y': range(40)}))
    dialog = app.run_chart()
    dialog.error = Mock()
    started, release = Event(), Event()
    def worker(data):
        started.set()
        assert release.wait(10)
        return {'late': True}
    monkeypatch.setattr(dialog, 'options', lambda: (worker, {}))
    try:
        dialog.fit()
        assert started.wait(2)
        ticks = []
        tk_root.after(0, lambda: ticks.append(True))
        tk_root.update()
        assert ticks and dialog.future is not None
        dialog.cancel()
        release.set()
        finish(tk_root, dialog)
        assert dialog.result is None and '已取消' in dialog.status.get()
        release.clear(); started.clear()
        dialog.fit()
        assert started.wait(2)
        future = dialog.future
        dialog.close()
        release.set()
        assert future.result(timeout=5) == {'late': True}
        tk_root.update()
        assert not dialog.main.winfo_exists()
    finally:
        release.set()
        if dialog.main.winfo_exists():
            dialog.close()
        dispose(app)
