"""CCD 新选项的真实 Tk 入口：分数、区组与分类因子。"""
from unittest.mock import Mock

from doe_dialog import AnalyzeDOE, CreateDOE
from test_csv_import import csv_app


def test_half_fraction_and_blocks_are_reachable_from_the_dialog(csv_app, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr('doe_dialog.messagebox.showerror', error)
    confirm = Mock(return_value=True)
    monkeypatch.setattr('doe_dialog.messagebox.askyesno', confirm)
    create = CreateDOE(app, ccd=True)
    create.factor_count.set('5')
    create.update_factor_rows()
    create.ccd_type.set('CCC')
    create.ccd_fraction.set('1/2 分数')
    create.ccd_blocks.set('2')
    create.options['中心点数'].delete(0, 'end')
    create.options['中心点数'].insert(0, '默认')
    create.preview()
    assert '32' in create.preview_text.get() or '33' in create.preview_text.get()
    create.create()
    table = app.getCurrentTable()
    metadata = table.doe_metadata
    assert metadata['design']['ccd_fraction'] == 'half'
    assert metadata['design']['block_count'] == 2
    assert table.model.df['区组'].nunique() == 2
    confirm.assert_called_once()
    error.assert_not_called()


def test_face_centered_with_blocks_is_rejected_without_creating_a_sheet(
        csv_app, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr('doe_dialog.messagebox.showerror', error)
    before = list(app.sheets)
    create = CreateDOE(app, ccd=True)
    create.ccd_blocks.set('2')
    create.create()
    assert list(app.sheets) == before
    assert '区组' in error.call_args.args[1]


def test_categorical_factor_column_creates_reference_coded_design(csv_app, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr('doe_dialog.messagebox.showerror', error)
    monkeypatch.setattr('worksheets.messagebox.askyesnocancel', lambda *a, **k: False)
    create = CreateDOE(app, ccd=True)
    assert len(create.fields[0]) == 5
    create.fields[2][4].insert(0, '甲;乙')
    create.factor_count.set('3')
    create.update_factor_rows()
    create.create()
    table = app.getCurrentTable()
    frame = table.model.df
    assert set(frame['设定_C']) == {'甲', '乙'}
    assert '编码_C' not in frame.columns
    # 每个分类水平各 5 个中心点。
    assert (frame['点类型'] == 'center').sum() == 10
    dialog = AnalyzeDOE(app)
    assert '编码_C' not in dialog.fixed
    dialog.main.destroy()


def test_duplicate_categorical_levels_are_rejected(csv_app, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr('doe_dialog.messagebox.showerror', error)
    before = list(app.sheets)
    create = CreateDOE(app, ccd=True)
    create.fields[2][4].insert(0, '甲;甲')
    create.factor_count.set('3')
    create.update_factor_rows()
    create.create()
    assert list(app.sheets) == before
    assert '不重复' in error.call_args.args[1]
