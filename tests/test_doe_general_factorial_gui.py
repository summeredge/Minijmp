from unittest.mock import Mock

from doe_dialog import AnalyzeDOE, CreateGeneralFactorial
from test_csv_import import csv_app


def configure(dialog, *, replicates=3, blocks=True):
    dialog.fields[1][1].set('数值')
    dialog.fields[1][2].delete(0, 'end')
    dialog.fields[1][2].insert(0, '100;150;200')
    dialog.replicates.delete(0, 'end')
    dialog.replicates.insert(0, str(replicates))
    dialog.seed.delete(0, 'end')
    dialog.seed.insert(0, '27')
    dialog.block_replicates.set(blocks)


def test_general_factorial_menu_and_f1_open_help(csv_app, monkeypatch):
    app, _ = csv_app
    menu = app.doe_menu['var']
    index = next(i for i in range(menu.index('end') + 1)
                 if menu.type(i) == 'command'
                 and menu.entrycget(i, 'label').strip() == '创建一般全因子设计')
    help_open = Mock()
    monkeypatch.setattr('doe_dialog.open_help', help_open)
    previous = set(app.main.winfo_children())
    menu.invoke(index)
    dialog = next(widget for widget in set(app.main.winfo_children()) - previous
                  if widget.title() == '创建一般全因子设计')
    dialog.update()
    dialog.focus_force()
    dialog.event_generate('<F1>')
    dialog.update()
    help_open.assert_called_once_with('doe.general_factorial', parent=dialog)
    dialog.destroy()


def test_create_preview_cancel_analysis_plot_save_reopen_copy(csv_app, tmp_path, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr('doe_dialog.messagebox.showerror', error)
    monkeypatch.setattr('worksheets.messagebox.askyesnocancel', lambda *a, **k: False)
    monkeypatch.setattr('worksheets.messagebox.askyesno', lambda *a, **k: True)
    before = list(app.sheets)
    cancelled = CreateGeneralFactorial(app)
    cancelled.main.destroy()
    assert list(app.sheets) == before

    create = CreateGeneralFactorial(app)
    configure(create)
    assert [(row[1].get(), row[2].get()) for row in create.fields[:2]] == [
        ('文字', '低;高'), ('数值', '100;150;200')]
    create.preview()
    assert error.call_count == 0, error.call_args
    assert '18 次运行' in create.preview_text.get()
    assert list(app.sheets) == before
    create.create()
    table = app.getCurrentTable()
    frame = table.model.df
    for index, row in frame.iterrows():
        block = int(row['区组'][1:])
        a = -1 if row['设定_A'] == '低' else 1
        b = {100: -1, 150: 0, 200: 1}[row['设定_B']]
        noise = block - 2
        frame.loc[index, '响应_Y'] = 10 + 2*a + 3*b + 4*a*b + noise + noise*a*b

    analysis = AnalyzeDOE(app)
    analysis.analyze()
    assert analysis.result is not None
    assert analysis.result['design'].spec.design_type == 'general_full_factorial'
    assert analysis.result['design'].spec.block_count == 3
    assert any(row['term'] == 'A*B' and row['df'] == 2 for row in analysis.result['anova'])
    analysis.plot()
    assert table.pf is not None
    assert [label.get_text() for label in table.pf.fig.axes[0].get_xticklabels()] == ['低', '高']
    assert table.pf.fig.axes[1].get_title() == 'A × B 交互作用图'
    assert table.pf.fig.axes[4].get_title() == '残差正态概率图'
    assert table.pf.fig.axes[5].get_title() == '残差与实际运行顺序'
    assert table.pf.fig.axes[5].get_title() == '残差与实际运行顺序'

    path = tmp_path / 'general-factorial.dexpl'
    assert app._save_project(path)
    analysis.main.destroy()
    assert app.load_file(path)
    reopened = app.getCurrentTable()
    assert reopened.doe_metadata['schema_version'] == 4
    assert reopened.doe_metadata['design']['factors'][1]['levels'] == [100, 150, 200]
    copied = app.copySheet()
    assert copied.doe_metadata == reopened.doe_metadata
    analysis_copy = AnalyzeDOE(app)
    analysis_copy.analyze()
    assert analysis_copy.result['n'] == 18
    assert error.call_count == 0
    analysis_copy.main.destroy()


def test_invalid_numeric_labels_do_not_add_a_sheet(csv_app, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr('doe_dialog.messagebox.showerror', error)
    before = list(app.sheets)
    dialog = CreateGeneralFactorial(app)
    dialog.fields[1][1].set('数值')
    dialog.fields[1][2].delete(0, 'end')
    dialog.fields[1][2].insert(0, '100;bad;200')
    dialog.create()
    assert list(app.sheets) == before
    error.assert_called_once()
    dialog.main.destroy()
