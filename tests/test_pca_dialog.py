from concurrent.futures import Future
from unittest.mock import Mock
import time

import numpy as np
import pandas as pd
from PIL import Image

from MiniJMP import Minijmp
from pca_dialog import PCADialog, HEADERS
from test_regression_dialog import dispose


def make_pca(tk_root, monkeypatch):
    monkeypatch.setattr(Minijmp, 'start_logging', lambda self: None)
    app = Minijmp(parent=tk_root)
    rng = np.random.default_rng(439)
    values = rng.normal(size=(60, 3))
    data = pd.DataFrame(values, columns=['温度', '压力', '流量'])
    data['批次'] = ['甲', '乙']*30
    source = app.addSheet('PCA来源', data)
    dialog = PCADialog(source, data, app)
    dialog.error = Mock()
    dialog.columns.selection_set(0, 2)
    dialog.fields['components'].set('2')
    return dialog, app, source, data


def finish(tk_root, dialog):
    deadline = time.monotonic()+30
    while dialog.future is not None and time.monotonic() < deadline:
        tk_root.update()
        time.sleep(.01)
    assert dialog.future is None
    dialog.error.assert_not_called()


def test_fit_project_export_and_source_binding(tk_root, monkeypatch, tmp_path):
    dialog, app, source, data = make_pca(tk_root, monkeypatch)
    try:
        dialog.fit()
        finish(tk_root, dialog)
        assert dialog.model.n_components == 2
        assert dialog.data.scores.shape == (60, 2)
        dialog.color_column.set('批次')
        dialog.draw()
        callbacks = len(dialog.canvas.callbacks.callbacks['button_press_event'])
        dialog.draw()
        assert len(dialog.canvas.callbacks.callbacks['button_press_event']) == callbacks
        dialog.pick(3)
        assert source.currentrow == 3
        assert 'contribution' in dialog.tables
        dialog.select([0, 1, 2], 'A')
        dialog.select([3, 4], 'B')
        tk_root.update()
        assert dialog.groups == {'A': [0, 1, 2], 'B': [3, 4]}
        dialog.compare()
        comparison = dialog.tables['groups']
        assert len(comparison) == 3
        np.testing.assert_allclose(comparison.mean_a, data.iloc[:3, :3].mean())
        np.testing.assert_allclose(comparison.std_b, data.iloc[3:5, :3].std(ddof=1))
        output = tmp_path/'pca.xlsx'
        monkeypatch.setattr('pca_dialog.filedialog.asksaveasfilename', lambda **kw: str(output))
        dialog.export()
        pd.testing.assert_frame_equal(pd.read_excel(output), comparison.rename(columns=HEADERS), check_dtype=False)
        dialog.to_sheet()
        pd.testing.assert_frame_equal(app.table.model.df, comparison.rename(columns=HEADERS))
        plot = tmp_path/'scores.png'
        monkeypatch.setattr('pca_dialog.filedialog.asksaveasfilename', lambda **kw: str(plot))
        dialog.save_plot()
        with Image.open(plot) as image:
            assert image.width > 300
            image.verify()
        model_file = tmp_path/'model.json'
        monkeypatch.setattr('pca_dialog.filedialog.asksaveasfilename', lambda **kw: str(model_file))
        dialog.save_model()
        finish(tk_root, dialog)
        assert model_file.is_file()
        scores = dialog.data.scores.copy()
        monkeypatch.setattr('pca_dialog.filedialog.askopenfilename', lambda **kw: str(model_file))
        dialog.load_model()
        finish(tk_root, dialog)
        np.testing.assert_allclose(dialog.data.scores, scores)
        assert dialog.active_table is None
        new_frame = data.iloc[:6].copy()
        projected = app.addSheet('新样本', new_frame)
        dialog.refresh_sheets()
        dialog.sheet_name.set('新样本')
        dialog.project()
        finish(tk_root, dialog)
        assert dialog.projection is not None and len(dialog.data.scores) == 6
        dialog.pick(2)
        assert projected.currentrow == 2
        pd.testing.assert_frame_equal(source.model.df, data)
        app.print = Mock()
        dialog.report()
        assert app.print.call_count > 2
        assert all(call.kwargs['table'] is source for call in app.print.call_args_list)
    finally:
        dialog.close()
        dispose(app)


def test_cancel_keeps_previous_model(tk_root, monkeypatch):
    dialog, app, source, data = make_pca(tk_root, monkeypatch)
    try:
        previous = dialog.model = object()
        future = dialog.future = Future()
        dialog.task = 'fit'
        dialog.cancel()
        future.set_result(None)
        dialog.poll()
        assert dialog.model is previous and dialog.future is None
        assert '已取消' in dialog.status.get()
        dialog.error.assert_not_called()
    finally:
        dialog.close()
        dispose(app)


def test_changed_and_closed_source_are_explicit(tk_root, monkeypatch):
    dialog, app, source, data = make_pca(tk_root, monkeypatch)
    try:
        source.destroy()
        dialog.fit()
        assert '来源工作表已关闭' in str(dialog.error.call_args.args[0])
    finally:
        dialog.close()
        dispose(app)


def test_categorical_missing_labels_and_selection_invalidation(tk_root, monkeypatch):
    dialog, app, source, data = make_pca(tk_root, monkeypatch)
    try:
        data['批次'] = pd.Categorical(['甲', None]*30)
        dialog.df = data.copy()
        source.model.df = data.copy()
        dialog.fit()
        finish(tk_root, dialog)
        dialog.color_column.set('批次')
        dialog.draw()
        dialog.select([0, 1, 2], 'A')
        dialog.select([3, 4], 'B')
        dialog.compare()
        assert 'groups' in dialog.tables
        dialog.select([2, 3], 'A')
        assert 'groups' not in dialog.tables
        source.model.df.iloc[0, 0] += 1
        dialog.pick(0)
        assert '已关闭或更改' in str(dialog.error.call_args.args[0])
    finally:
        dialog.close()
        dispose(app)
