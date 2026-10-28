"""CCD 新选项的真实 Tk 入口：分数、区组与分类因子。"""
from unittest.mock import Mock
import pytest

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


@pytest.mark.parametrize('ccd_type', ['CCF', 'CCC'])
def test_categorical_preview_and_creation(csv_app, monkeypatch, ccd_type):
    app, error = csv_app
    monkeypatch.setattr('doe_dialog.messagebox.showerror', error)
    monkeypatch.setattr('doe_dialog.messagebox.askyesno', lambda *a, **k: True)
    create = CreateDOE(app, ccd=True)
    create.factor_count.set('3')
    create.update_factor_rows()
    create.ccd_type.set(ccd_type)
    create.fields[2][4].insert(0, '甲;乙')
    before = list(app.sheets)
    create.preview()
    summary = create.preview_text.get()
    assert list(app.sheets) == before
    assert '甲 / 乙' in summary and '轴点 8' in summary
    create.create()
    frame = app.getCurrentTable().model.df
    assert f'{len(frame)} 次运行' in summary
    assert set(frame['设定_C']) == {'甲', '乙'}
    error.assert_not_called()


@pytest.mark.parametrize(('count', 'fraction'), [
    (6, '全因子'), (8, '1/2 分数'), (9, '1/4 分数'), (10, '1/8 分数'),
])
def test_high_dimension_ccd_dialog_creates_design(csv_app, monkeypatch, count, fraction):
    app, error = csv_app
    monkeypatch.setattr('doe_dialog.messagebox.showerror', error)
    create = CreateDOE(app, ccd=True)
    assert str(count) in tuple(map(str, create.factor_count['values']))
    create.factor_count.set(str(count))
    create.update_factor_rows()
    create.ccd_fraction.set(fraction)
    create.preview()
    assert '次运行' in create.preview_text.get()
    create.create()
    assert len(app.getCurrentTable().doe_metadata['design']['factors']) == count
    error.assert_not_called()


def test_ccd_invalid_fraction_and_buttons_at_small_window(csv_app, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr('doe_dialog.messagebox.showerror', error)
    create = CreateDOE(app, ccd=True)
    create.main.geometry('640x480')
    create.factor_count.set('9')
    create.update_factor_rows()
    create.main.update()
    bar = next(widget for widget in create.main.winfo_children()
               if any(child.winfo_class() == 'TButton' for child in widget.winfo_children()))
    buttons = bar.winfo_children()
    assert all(button.winfo_ismapped() and button.winfo_rooty() + button.winfo_height()
               <= create.main.winfo_rooty() + create.main.winfo_height() for button in buttons)
    before = list(app.sheets)
    buttons[1].invoke()
    assert list(app.sheets) == before
    error.assert_called_once()
    buttons[2].invoke()
    assert not create.main.winfo_exists()
