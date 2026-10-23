"""真实 Tk 连接、后台任务生命周期及来源表边界。"""
from concurrent.futures import Future
from types import SimpleNamespace
from unittest.mock import Mock
import time

import numpy as np
import pandas as pd
import pytest
from PIL import Image

from regression_dialog import RegressionDialog, HEADERS


def make_dialog(tk_root, monkeypatch):
    from MiniJMP import Minijmp
    monkeypatch.setattr(Minijmp, 'start_logging', lambda self: None)
    app = Minijmp(parent=tk_root)
    rng = np.random.default_rng(3801)
    x = rng.normal(size=(60, 2))
    data = pd.DataFrame({'Y': 3 + 2*x[:, 0] - x[:, 1]+rng.normal(0, .3, 60),
                         'X1': x[:, 0], 'X2': x[:, 1]})
    source = app.addSheet('回归来源', data)
    dialog = RegressionDialog(source, data, app)
    dialog.error = Mock()
    dialog.fields['y'].set('Y')
    dialog.x_list.selection_set(1, 2)
    return dialog, app, source, data


def finish(tk_root, dialog):
    deadline = time.monotonic() + 30
    while dialog.future is not None and time.monotonic() < deadline:
        tk_root.update()
        time.sleep(.01)
    assert dialog.future is None, '后台计算未在30秒内结束'
    dialog.error.assert_not_called()


def dispose(app):
    for name, table in list(app.sheets.items()):
        app._dispose_sheet(table, app.sheetframes[name])
    app.nb.destroy()
    app.main.configure(menu='')
    app.destroy()


def test_fit_predict_export_and_source_binding(tk_root, monkeypatch, tmp_path):
    dialog, app, source, data = make_dialog(tk_root, monkeypatch)
    try:
        dialog.fit()
        finish(tk_root, dialog)
        assert dialog.result is not None
        assert {'summary', 'coefficients', 'observations'} <= dialog.tables.keys()
        other = app.addSheet('预测数据', data[['X1', 'X2']].iloc[:5].copy())
        assert dialog.app.getCurrentTable() is source
        dialog.refresh_sheets()
        dialog.sheet_name.set('预测数据')
        dialog.predict()
        finish(tk_root, dialog)
        assert len(dialog.prediction) == 5
        frame = dialog.prediction.rename(columns=HEADERS).copy()
        destination = tmp_path/'regression.xlsx'
        monkeypatch.setattr('regression_dialog.filedialog.asksaveasfilename', lambda **kw: str(destination))
        dialog.export()
        pd.testing.assert_frame_equal(pd.read_excel(destination), frame, check_dtype=False)
        dialog.to_sheet()
        pd.testing.assert_frame_equal(app.table.model.df, frame)
        dialog.plot_kind.set('实测与预测')
        dialog.plot()
        dialog.error.assert_not_called()
        assert source.pf is not None
        assert getattr(other, 'pf', None) is None
        output = tmp_path/'observed.png'
        source.pf.fig.savefig(output)
        with Image.open(output) as image:
            assert image.width > 300 and image.height > 200
            image.verify()
        dialog.select_row(4)
        assert source.currentrow == 3
        pd.testing.assert_frame_equal(source.model.df, data)
        app.print = Mock()
        dialog.report()
        assert app.print.call_count > 1
        assert all(call.kwargs['table'] is source for call in app.print.call_args_list)
    finally:
        dialog.close()
        dispose(app)


def test_cancel_discards_late_result_and_preserves_last_model(tk_root, monkeypatch):
    dialog, app, source, data = make_dialog(tk_root, monkeypatch)
    try:
        previous = dialog.result = object()
        future = dialog.future = Future()
        dialog.task = 'fit'
        dialog.cancel()
        future.set_result(SimpleNamespace(tables={}))
        dialog.poll()
        assert dialog.result is previous
        assert dialog.future is None
        assert '已取消' in dialog.status.get()
        dialog.error.assert_not_called()
    finally:
        dialog.close()
        dispose(app)


def test_changed_source_blocks_row_selection(tk_root, monkeypatch):
    dialog, app, source, data = make_dialog(tk_root, monkeypatch)
    try:
        source.model.df.iloc[0, 0] += 10
        dialog.select_row(1)
        assert '已更改' in str(dialog.error.call_args.args[0])
        dialog.error.reset_mock()
        source.destroy()
        dialog.fit()
        assert '来源工作表已关闭' in str(dialog.error.call_args.args[0])
    finally:
        dialog.close()
        dispose(app)


@pytest.mark.parametrize('model', ['WLS', 'Logistic', '非线性'])
def test_model_specific_gui_fit_and_prediction(tk_root, monkeypatch, model):
    dialog, app, source, data = make_dialog(tk_root, monkeypatch)
    try:
        rng = np.random.default_rng(6238)
        dialog.fields['model'].set(model)
        if model == 'WLS':
            data['X2'] = rng.uniform(.4, 2., len(data))
            dialog.fields['weight'].set('X2')
        elif model == 'Logistic':
            data['Y'] = rng.binomial(1, 1/(1+np.exp(-data.X1)))
        else:
            data['X1'] = np.linspace(.2, 3., len(data))
            data['Y'] = 2*np.exp(.3*data.X1)+.2+rng.normal(0, .01, len(data))
            dialog.x_list.selection_clear(2)
            dialog.fields['initial'].set('a=2,b=.3,c=.2')
        source.model.df = data.copy()
        dialog.df = data.copy()
        dialog.fit()
        finish(tk_root, dialog)
        assert dialog.result is not None
        if model == 'Logistic':
            assert 'classification' in dialog.tabs and 'anova' not in dialog.tabs
            dialog.plot_kind.set('ROC 曲线')
        elif model == '非线性':
            assert 'anova' not in dialog.tabs
            dialog.plot_kind.set('系数置信区间')
        else:
            dialog.plot_kind.set('残差与拟合值')
        dialog.plot()
        dialog.error.assert_not_called()
        dialog.sheet_name.set('回归来源')
        dialog.predict()
        finish(tk_root, dialog)
        assert len(dialog.prediction) == len(data)
        if model == 'Logistic':
            assert dialog.prediction.predicted.between(0, 1).all()
        else:
            assert (dialog.prediction.pi_lower < dialog.prediction.pi_upper).all()
    finally:
        dialog.close()
        dispose(app)
