from concurrent.futures import Future
from unittest.mock import Mock
import time

import numpy as np
import pandas as pd
from PIL import Image

from MiniJMP import Minijmp
from advanced_time_series_dialog import TimeSeriesAnalysisDialog, HEADERS, export_frame
from test_regression_dialog import dispose


def make_dialog(tk_root, monkeypatch):
    monkeypatch.setattr(Minijmp, 'start_logging', lambda self: None)
    app = Minijmp(parent=tk_root)
    rng = np.random.default_rng(4836)
    x = rng.normal(size=120)
    y = np.empty_like(x)
    y[0] = x[0]
    for i in range(1, len(y)):
        y[i] = .5*y[i-1]+x[i]
    data = pd.DataFrame({'时间': pd.date_range('2026-10-01', periods=len(y), freq='1min'), 'Y': y, 'X': x})
    source = app.addSheet('时序来源', data)
    dialog = TimeSeriesAnalysisDialog(source, data, app)
    dialog.error = Mock()
    dialog.fields['y'].set('Y')
    dialog.fields['time'].set('时间')
    dialog.fields['other'].set('X')
    dialog.fields['lags'].set('10')
    return dialog, app, source, data


def finish(tk_root, dialog):
    deadline = time.monotonic()+40
    while dialog.future is not None and time.monotonic() < deadline:
        tk_root.update()
        time.sleep(.01)
    assert dialog.future is None
    dialog.error.assert_not_called()


def test_analyze_forecast_export_and_source_binding(tk_root, monkeypatch, tmp_path):
    dialog, app, source, data = make_dialog(tk_root, monkeypatch)
    try:
        dialog.fields['analysis'].set('ARIMA 建模')
        dialog.analyze()
        finish(tk_root, dialog)
        assert len(dialog.result.tables['forecast']) == 10
        app.addSheet('另一工作表', pd.DataFrame({'a': [1, 2]}))
        dialog.notebook.select(dialog.tabs['forecast'])
        output = tmp_path/'forecast.xlsx'
        monkeypatch.setattr('advanced_time_series_dialog.filedialog.asksaveasfilename', lambda **kw: str(output))
        dialog.export()
        expected = dialog.tables['forecast'].rename(columns=HEADERS)
        exported = expected.copy()
        exported['经过时间'] = expected['经过时间'].astype(str)
        exported['来源行号集合'] = ['[]']*len(expected)
        exported['来源索引集合'] = ['[]']*len(expected)
        reopened = pd.read_excel(output)
        assert reopened[['来源行号', '来源索引']].isna().all().all()
        pd.testing.assert_frame_equal(reopened.drop(columns=['来源行号', '来源索引']),
            exported.drop(columns=['来源行号', '来源索引']), check_dtype=False)
        dialog.to_sheet()
        pd.testing.assert_frame_equal(app.table.model.df, expected)
        dialog.plot_kind.set('模型预测')
        dialog.plot()
        dialog.error.assert_not_called()
        assert source.pf is not None
        filename = tmp_path/'forecast.png'
        source.pf.savePlot(str(filename))
        with Image.open(filename) as image:
            assert image.width > 300
            image.verify()
        dialog.pick([3, 4])
        assert source.multiplerowlist == [2, 3]
        pd.testing.assert_frame_equal(source.model.df, data)
        app.print = Mock()
        dialog.report()
        assert app.print.call_count > 1
        assert all(call.kwargs['table'] is source for call in app.print.call_args_list)
    finally:
        dialog.close()
        dispose(app)


def test_correlation_decomposition_and_stationarity_gui(tk_root, monkeypatch):
    dialog, app, source, data = make_dialog(tk_root, monkeypatch)
    try:
        for analysis, key, graph in [('相关分析', 'ccf', '交叉相关 CCF'),
                                     ('趋势与季节分解', 'decomposition', '季节分解'),
                                     ('平稳性检验', 'stationarity', '原始序列'),
                                     ('SARIMA 建模', 'forecast', '模型预测')]:
            if analysis == 'SARIMA 建模':
                dialog.fields['order'].set('0,0,0')
                dialog.fields['seasonal_order'].set('1,0,0,12')
            dialog.fields['analysis'].set(analysis)
            dialog.analyze()
            finish(tk_root, dialog)
            assert key in dialog.tables
            dialog.plot_kind.set(graph)
            dialog.plot()
            dialog.error.assert_not_called()
    finally:
        dialog.close()
        dispose(app)


def test_export_preserves_timezone_duration_identifiers_and_precision(tmp_path):
    frame = pd.DataFrame({'time': pd.date_range('2026-10-01', periods=2, tz='Asia/Shanghai'),
        'elapsed': pd.to_timedelta([1, None], unit='s'),
        'source_index': [9007199254740993, '000001'],
        'source_indices': [[9007199254740993], ['000001']],
        'predicted': [1.123456789012345, 2.5]})
    path = tmp_path/'typed.xlsx'
    export_frame(frame).to_excel(path, index=False)
    actual = pd.read_excel(path, dtype={'来源索引': str})
    assert actual['来源索引'].tolist() == ['9007199254740993', '000001']
    assert actual['实际时间'].str.endswith('+08:00').all()
    assert actual['经过时间'].iloc[0] == '0 days 00:00:01'
    assert pd.isna(actual['经过时间'].iloc[1])
    assert actual['来源索引集合'].iloc[0] == '[9007199254740993]'
    np.testing.assert_allclose(actual['预测值'], frame['predicted'], rtol=1e-15)


def test_cancel_and_source_change_are_explicit(tk_root, monkeypatch):
    dialog, app, source, data = make_dialog(tk_root, monkeypatch)
    try:
        old = dialog.result = object()
        future = dialog.future = Future()
        dialog.cancel()
        future.set_result(None)
        dialog.poll()
        assert dialog.result is old and '已取消' in dialog.status.get()
        source.model.df.iloc[0, 1] += 1
        dialog.pick(1)
        assert '已更改' in str(dialog.error.call_args.args[0])
        dialog.error.reset_mock()
        source.destroy()
        dialog.analyze()
        assert '来源工作表已关闭' in str(dialog.error.call_args.args[0])
    finally:
        dialog.close()
        dispose(app)
