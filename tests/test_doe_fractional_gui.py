from unittest.mock import Mock

import pytest

from doe_dialog import AnalyzeDOE, CreateDOE
from test_csv_import import csv_app


def configure_fractional(dialog, count, generators):
    dialog.factor_count.set(str(count))
    dialog.update_factor_rows()
    for index, entries in enumerate(dialog.fields[:count]):
        for entry, value in zip(entries, (chr(65 + index), '0', '1', '')):
            entry.delete(0, 'end')
            entry.insert(0, value)
    dialog.generators.delete(0, 'end')
    dialog.generators.insert(0, generators)


@pytest.mark.parametrize(('preset', 'count', 'generators', 'runs', 'resolution'), [
    ('3因子（C=AB）', 3, 'C=AB', 4, 'III'),
    ('4因子（D=ABC）', 4, 'D=ABC', 8, 'IV'),
    ('5因子（E=ABCD）', 5, 'E=ABCD', 16, 'V'),
    ('5因子（D=AB;E=AC）', 5, 'D=AB;E=AC', 8, 'III'),
    ('自定义', 6, 'F=ABC', 32, 'IV'),
])
def test_fractional_creation_preview_and_supported_factor_counts(
        csv_app, preset, count, generators, runs, resolution):
    app, error = csv_app
    dialog = CreateDOE(app, fractional=True)
    assert tuple(map(int, dialog.factor_count['values'])) == (3, 4, 5, 6)
    assert dialog.generators.get() == ''
    if preset == '自定义':
        configure_fractional(dialog, count, generators)
    else:
        dialog.preset.set(preset)
        dialog.apply_fractional_preset()
        assert dialog.factor_count.get() == str(count)
        assert dialog.generators.get() == generators
    dialog.preview()
    assert f'{runs} 次运行' in dialog.preview_text.get()
    assert f'分辨度 {resolution}' in dialog.preview_text.get()
    assert all(relation in dialog.preview_text.get()
               for relation in generators.split(';'))
    assert error.call_count == 0
    dialog.create()
    table = app.getCurrentTable()
    assert table.doe_metadata['design']['design_type'] == 'two_level_fractional'
    assert tuple(table.doe_metadata['design']['generators']) == tuple(generators.split(';'))


@pytest.mark.parametrize(('generators', 'centers'), [
    ('d=ABC', '0'),
    ('D =ABC', '0'),
    ('D=ABC', '1'),
])
def test_fractional_creation_rejects_noncanonical_inputs_without_adding_sheet(
        csv_app, monkeypatch, generators, centers):
    app, error = csv_app
    monkeypatch.setattr('doe_dialog.messagebox.showerror', error)
    existing = list(app.sheets)
    dialog = CreateDOE(app, fractional=True)
    configure_fractional(dialog, 4, generators)
    dialog.options['中心点数'].delete(0, 'end')
    dialog.options['中心点数'].insert(0, centers)
    dialog.create()
    assert list(app.sheets) == existing
    error.assert_called_once()
    dialog.main.destroy()


def test_fractional_menu_opens_creation_dialog(csv_app):
    app, _ = csv_app
    menu = app.doe_menu['var']
    index = next(i for i in range(menu.index('end') + 1)
                 if menu.type(i) == 'command' and
                 menu.entrycget(i, 'label').strip() == '创建两水平部分因子设计')
    previous = set(app.main.winfo_children())
    menu.invoke(index)
    created = set(app.main.winfo_children()) - previous
    dialog = next(widget for widget in created
                  if widget.title() == '创建两水平部分因子设计')
    assert dialog.winfo_exists()
    dialog.destroy()


def test_fractional_f1_opens_help_from_create_and_analysis(csv_app, monkeypatch):
    app, _ = csv_app
    help_open = Mock()
    monkeypatch.setattr('doe_dialog.open_help', help_open)
    create = CreateDOE(app, fractional=True)
    create.main.update()
    create.main.focus_force()
    create.main.event_generate('<F1>')
    create.main.update()
    help_open.assert_called_once_with('doe.fractional', parent=create.main)
    create.main.destroy()
    help_open.reset_mock()

    create = CreateDOE(app, fractional=True)
    configure_fractional(create, 4, 'D=ABC')
    create.create()
    analysis = AnalyzeDOE(app)
    analysis.main.update()
    analysis.main.focus_force()
    analysis.main.event_generate('<F1>')
    analysis.main.update()
    help_open.assert_called_once_with('doe.fractional', parent=analysis.main)
    analysis.main.destroy()


def test_fractional_roundtrip_analysis_and_plot_are_alias_aware(
        csv_app, tmp_path, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr('doe_dialog.messagebox.showerror', error)
    monkeypatch.setattr('worksheets.messagebox.askyesnocancel', lambda *a, **k: False)
    monkeypatch.setattr('worksheets.messagebox.askyesno', lambda *a, **k: True)
    create = CreateDOE(app, fractional=True)
    configure_fractional(create, 4, 'D=ABC')
    create.create()
    table = app.getCurrentTable()
    frame = table.model.df
    for row in range(len(frame)):
        values = [2 * frame.iloc[row][f'设定_{factor}'] - 1 for factor in 'ABCD']
        a, b, c, d = values
        response = 20 + 2*a + 3*b + 4*c + 5*d
        table.model.setValueAt(str(response), row, frame.columns.get_loc('响应_Y'))

    target = tmp_path / 'fractional.dexpl'
    assert app._save_project(target)
    assert app.load_file(target)
    restored = app.getCurrentTable()
    assert restored.doe_metadata['design']['generators'] == ['D=ABC']

    analysis = AnalyzeDOE(app)
    analysis.analyze()
    assert analysis.result is not None
    assert analysis.result['design'].spec.design_type == 'two_level_fractional'
    assert any(group['representative'] == 'A' and 'B*C*D' in group['label']
               for group in analysis.result['alias_groups'])
    assert '纯误差' in analysis.result['status'] or analysis.result['inference'] is None
    tabs = [analysis.tabs.tab(tab, 'text') for tab in analysis.tabs.tabs()]
    assert '系数与别名组效应' in tabs
    assert '别名与代表项' in tabs
    analysis.plot()
    assert restored.pf is not None
    assert '可能混杂' in restored.pf.fig.axes[1].get_title()
    assert '别名组' in restored.pf.fig.axes[2].get_title()
    assert error.call_count == 0
    analysis.main.destroy()


def test_quarter_fraction_multiple_responses_and_source_lifecycle(csv_app, tmp_path, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr('doe_dialog.messagebox.showerror', error)
    monkeypatch.setattr('worksheets.messagebox.askyesno', lambda *a, **k: True)
    monkeypatch.setattr('worksheets.messagebox.askyesnocancel', lambda *a, **k: False)
    before = list(app.sheets)
    cancelled = CreateDOE(app, fractional=True)
    cancelled.main.destroy()
    assert list(app.sheets) == before
    create = CreateDOE(app, fractional=True)
    configure_fractional(create, 5, 'D=AB;E=AC')
    create.options['响应名称'].delete(0, 'end')
    create.options['响应名称'].insert(0, 'Y,Z')
    create.create()
    table = app.getCurrentTable()
    frame = table.model.df
    for i in range(len(frame)):
        a = 2 * frame.iloc[i]['设定_A'] - 1
        for name, value in (('Y', 10 + 2*a), ('Z', 30 - 3*a)):
            table.model.setValueAt(str(value), i, frame.columns.get_loc('响应_' + name))
    target = tmp_path / 'quarter.dexpl'
    assert app._save_project(target)
    assert app.load_file(target)
    dialog = AnalyzeDOE(app)
    dialog.order.set('1')
    dialog.analyze()
    assert dialog.result['coefficients'][1] == pytest.approx(2)
    dialog.response.set('Z')
    dialog.analyze()
    assert dialog.result['coefficients'][1] == pytest.approx(-3)
    app.nb.select(app.sheetframes[before[0]])
    dialog.plot()
    assert '来源工作表已切换' in error.call_args.args[1]
    app.nb.select(app.sheetframes[next(name for name, item in app.sheets.items()
                                       if item is dialog.source)])
    assert app.deleteSheet()
    dialog.analyze()
    assert '来源工作表已关闭' in error.call_args.args[1]
    dialog.main.destroy()
