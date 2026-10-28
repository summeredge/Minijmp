import json
from pathlib import Path

from pandas.testing import assert_frame_equal
import pytest

from doe_dialog import AnalyzeDOE
from doe_splitplot_dialog import CreateSplitPlot
from test_csv_import import csv_app


REFERENCE = json.loads((Path(__file__).parent / "fixtures" / "doe_factorial_reference"
                        / "reference.json").read_text(encoding="utf-8"))["split_plot"]


def invoke_splitplot_menu(app):
    menu = app.doe_menu["var"]
    index = next(i for i in range(menu.index("end") + 1)
                 if menu.type(i) == "command"
                 and menu.entrycget(i, "label").strip() == "创建两水平裂区设计")
    previous = set(app.main.winfo_children())
    menu.invoke(index)
    created = set(app.main.winfo_children()) - previous
    return next((widget for widget in created
                 if widget.title() == "创建两水平 Split-Plot 裂区设计"), None)


def fill_reference_response(table):
    frame = table.model.df
    values = {(row["block"], row["A"], row["B"]): row["Y"]
              for row in REFERENCE["rows"]}
    response_column = frame.columns.get_loc("响应_Y")
    for index, row in frame.iterrows():
        a = 1 if row["设定_A"] == 1 else -1
        b = 1 if row["设定_B"] == 1 else -1
        block = int(row["区组"])
        table.model.setValueAt(str(values[(block, a, b)]), index, response_column)


def test_splitplot_menu_preview_analysis_save_reopen_copy_and_plot(
        csv_app, tmp_path, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr("doe_dialog.messagebox.showerror", error)
    monkeypatch.setattr("doe_splitplot_dialog.messagebox.showerror", error)
    monkeypatch.setattr("worksheets.messagebox.askyesnocancel", lambda *a, **k: False)
    monkeypatch.setattr("worksheets.messagebox.askyesno", lambda *a, **k: True)
    source_name = app.getCurrentSheet()
    source_frame = app.getCurrentTable().model.df.copy(deep=True)

    menu_window = invoke_splitplot_menu(app)
    assert menu_window is not None
    menu_window.destroy()
    dialog = CreateSplitPlot(app)
    dialog.seed.delete(0, "end")
    dialog.seed.insert(0, "23")
    assert dialog.preview() is True
    preview = dialog.preview_text.get("1.0", "end")
    assert "运行 12 次；区组 3；整区 6" in preview
    assert "R00001" in preview
    assert dialog.create() is True

    name = app.getCurrentSheet()
    assert name != source_name
    table = app.getCurrentTable()
    assert table.doe_metadata["design"]["design_type"] == "split_plot"
    assert table.doe_metadata["design"]["randomization_unit"] == "whole_plot"
    assert table.doe_metadata["design"]["error_structure"] == "split_plot"
    assert_frame_equal(app.sheets[source_name].model.df, source_frame)
    fill_reference_response(table)

    analysis = AnalyzeDOE(app)
    analysis.analyze()
    assert analysis.result is not None, error.call_args_list
    expected = REFERENCE["expected"]
    anova = {row["term"]: row for row in analysis.result["anova"]}
    assert anova["A"]["f"] == pytest.approx(expected["f"]["A"])
    assert anova["B"]["f"] == pytest.approx(expected["f"]["B"])
    assert anova["A:B"]["f"] == pytest.approx(expected["f"]["A:B"])
    assert [analysis.tabs.tab(tab, "text") for tab in analysis.tabs.tabs()] == [
        "诊断合同", "裂区方差分析", "拟合与残差"]
    analysis.plot()
    assert table.pf is not None
    assert table.pf.fig.axes[2].get_title() == '残差与实际运行顺序'
    assert table.pf.fig.axes[5].get_title() == '残差正态概率图'

    path = tmp_path / "splitplot.dexpl"
    assert app._save_project(path)
    assert app.load_file(path)
    name = next(sheet_name for sheet_name, item in app.sheets.items()
                if item.doe_metadata
                and item.doe_metadata["design"]["design_type"] == "split_plot")
    app.nb.select(app.sheetframes[name])
    reopened = app.getCurrentTable()
    copied = app.copySheet()
    assert copied.doe_metadata == reopened.doe_metadata
    assert_frame_equal(copied.model.df, reopened.model.df)
    again = AnalyzeDOE(app)
    again.analyze()
    assert again.result is not None
    assert error.call_count == 0
    analysis.main.destroy()
    again.main.destroy()


def test_splitplot_cancel_and_invalid_blocks_leave_workbook_unchanged(csv_app, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr("doe_splitplot_dialog.messagebox.showerror", error)
    names = list(app.sheets)
    dialog = CreateSplitPlot(app)
    dialog.cancel_button.invoke()
    assert list(app.sheets) == names

    dialog = CreateSplitPlot(app)
    dialog.blocks.delete(0, "end")
    dialog.blocks.insert(0, "1")
    dialog.create_button.invoke()
    assert list(app.sheets) == names
    error.assert_called_once()
    dialog.main.destroy()


def preview_lines(dialog):
    return dialog.preview_text.get("1.0", "end").splitlines()


def test_preview_truncates_at_threshold_and_refreshes_after_setting_change(
        csv_app, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr("doe_splitplot_dialog.messagebox.showerror", error)
    dialog = CreateSplitPlot(app)
    assert len(preview_lines(dialog)) == 2 + 12
    assert "仅显示前" not in dialog.preview_text.get("1.0", "end")

    dialog.blocks.delete(0, "end")
    dialog.blocks.insert(0, "26")
    assert dialog.preview() is True
    lines = preview_lines(dialog)
    assert lines[0] == "运行 104 次；区组 26；整区 52"
    assert len(lines) == 2 + 100 + 1
    assert lines[-1] == "仅显示前 100 行，共 104 行"

    dialog.blocks.delete(0, "end")
    dialog.blocks.insert(0, "3")
    assert dialog.preview() is True
    assert len(preview_lines(dialog)) == 2 + 12
    assert error.call_count == 0
    dialog.main.destroy()


def test_preview_of_maximum_legal_design_stays_bounded(csv_app):
    app, _ = csv_app
    dialog = CreateSplitPlot(app)
    dialog.blocks.delete(0, "end")
    dialog.blocks.insert(0, "2500")
    assert dialog.preview() is True
    lines = preview_lines(dialog)
    assert lines[0] == "运行 10000 次；区组 2500；整区 5000"
    assert len(lines) == 2 + 100 + 1
    assert lines[-1] == "仅显示前 100 行，共 10000 行"
    dialog.main.destroy()


def test_preview_has_horizontal_scrollbar(csv_app):
    app, _ = csv_app
    dialog = CreateSplitPlot(app)
    assert str(dialog.preview_text.cget("xscrollcommand")) != ""
    assert str(dialog.preview_horizontal.cget("orient")) == "horizontal"
    dialog.main.destroy()


def test_too_many_runs_is_rejected_without_preview_or_new_sheet(csv_app, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr("doe_splitplot_dialog.messagebox.showerror", error)
    names = list(app.sheets)
    dialog = CreateSplitPlot(app)
    dialog.blocks.delete(0, "end")
    dialog.blocks.insert(0, "2501")
    assert dialog.preview() is False
    assert dialog.preview_text.get("1.0", "end").strip() == ""
    dialog.create_button.invoke()
    assert list(app.sheets) == names
    assert error.call_count == 2
    dialog.main.destroy()
