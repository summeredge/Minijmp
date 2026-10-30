import json
from pathlib import Path

import pandas as pd
from pandas.testing import assert_frame_equal
import pytest

from doe_dialog import AnalyzeDOE
from doe_splitplot import validate_split_plot_design
from doe_splitplot_dialog import CreateSplitPlot
from doe_optimal_dialog import ModifyDesignDialog
from test_csv_import import csv_app


REFERENCE = json.loads((Path(__file__).parent / "fixtures" / "doe_factorial_reference"
                        / "reference.json").read_text(encoding="utf-8"))["split_plot"]
PHASE2 = json.loads((Path(__file__).parent / "fixtures" / "doe_phase2_splitplot_reference"
                     / "reference.json").read_text(encoding="utf-8"))


def invoke_splitplot_menu(app):
    menu = app.doe_menu["var"]
    index = next(i for i in range(menu.index("end") + 1)
                 if menu.type(i) == "command"
                 and menu.entrycget(i, "label").strip() == "创建多因子裂区设计")
    previous = set(app.main.winfo_children())
    menu.invoke(index)
    created = set(app.main.winfo_children()) - previous
    return next((widget for widget in created
                 if widget.title() == "创建 Split-Plot 裂区设计"), None)


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


def test_multifactor_splitplot_create_analyze_plot_and_project_roundtrip(
        csv_app, tmp_path, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr("doe_dialog.messagebox.showerror", error)
    monkeypatch.setattr("doe_splitplot_dialog.messagebox.showerror", error)
    monkeypatch.setattr("worksheets.messagebox.askyesnocancel", lambda *a, **k: False)
    monkeypatch.setattr("worksheets.messagebox.askyesno", lambda *a, **k: True)

    case = PHASE2["cases"][2]
    dialog = CreateSplitPlot(app)
    dialog.factor_count_var.set("4")
    dialog.factor_values[1]["role"].set("整区因子")
    dialog.blocks_var.set("3")
    assert dialog.preview() is True
    assert "48 次；区组 3；整区 12；每整区子区 4；整区误差 df 6；子区误差 df 24" \
        in dialog.summary.cget("text")
    assert dialog.create() is True

    table = app.getCurrentTable()
    metadata = table.doe_metadata
    assert metadata["design"]["construction_version"] == "v2"
    assert metadata["design"]["schema_version"] == 5
    assert len(table.model.df) == 48
    fixture_responses = {row["run_id"]: row["y"] for row in case["rows"]}
    frame = table.model.df
    response_column = metadata["column_map"]["responses"]["Y"]
    run_ids = frame[metadata["column_map"]["run_id"]].tolist()
    for index, run_id in enumerate(run_ids):
        table.model.setValueAt(str(fixture_responses[run_id]),
                               index, frame.columns.get_loc(response_column))

    analysis = AnalyzeDOE(app)
    analysis.analyze()
    assert analysis.result is not None, error.call_args_list
    expected = case["expected"]
    actual = {row["term"]: row for row in analysis.result["anova"]}
    assert actual["whole_plot_error"]["df"] == expected["summary"]["df_whole_plot_error"]
    assert actual["subplot_error"]["df"] == expected["summary"]["df_subplot_error"]
    for term in ("A", "B", "C", "D", "A:B", "A:B:C:D"):
        assert actual[term]["ss"] == pytest.approx(expected["terms"][term]["ss"])
        assert actual[term]["f"] == pytest.approx(expected["terms"][term]["f"])
    analysis.plot()
    assert table.pf is not None
    assert table.pf.fig.axes[0].get_title() == "整区误差贡献"
    assert table.pf.fig.axes[1].get_title() == "子区误差贡献"

    identity_columns = [metadata["column_map"][key] for key in (
        "run_id", "run_order", "block", "whole_plot_id", "subplot_id",
        "whole_plot_order", "subplot_order")]
    before = frame[identity_columns].copy(deep=True)
    path = tmp_path / "splitplot-v2.dexpl"
    assert app._save_project(path)
    assert app.load_file(path)
    sheet_name = next(name for name, item in app.sheets.items()
                      if item.doe_metadata
                      and item.doe_metadata["design"].get("construction_version") == "v2"
                      and item.doe_metadata["design"]["design_type"] == "split_plot")
    app.nb.select(app.sheetframes[sheet_name])
    reopened = app.getCurrentTable()
    assert_frame_equal(reopened.model.df[identity_columns], before)
    copied = app.copySheet()
    assert copied.doe_metadata == reopened.doe_metadata
    assert_frame_equal(copied.model.df, reopened.model.df)
    again = AnalyzeDOE(app)
    again.analyze()
    assert again.result is not None, error.call_args_list
    assert error.call_count == 0
    analysis.main.destroy()
    again.main.destroy()


def test_eight_factor_categorical_splitplot_ui_and_project_roundtrip(
        csv_app, tmp_path, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr("doe_splitplot_dialog.messagebox.showerror", error)
    monkeypatch.setattr("worksheets.messagebox.askyesnocancel", lambda *a, **k: False)
    monkeypatch.setattr("worksheets.messagebox.askyesno", lambda *a, **k: True)
    dialog = CreateSplitPlot(app)
    assert "8" in dialog.factor_count.cget("values")
    dialog.factor_count_var.set("8")
    dialog.factor_values[0]["factor_type"].set("分类")
    dialog.factor_values[0]["low"].set("slow")
    dialog.factor_values[0]["high"].set("fast")
    dialog.factor_values[7]["factor_type"].set("分类")
    dialog.factor_values[7]["low"].set("manual")
    dialog.factor_values[7]["high"].set("automatic")
    dialog.blocks_var.set("2")
    assert dialog.preview() is True
    assert "运行 512 次；区组 2；整区 4；每整区子区 128" in dialog.summary.cget("text")
    assert dialog.create() is True

    table = app.getCurrentTable()
    metadata = table.doe_metadata
    assert metadata["schema_version"] == metadata["design"]["schema_version"] == 5
    assert metadata["design"]["construction_version"] == "v3"
    result = validate_split_plot_design(table.model.df, metadata)
    assert len(result.spec.factors) == 8
    assert result.spec.factors[0].levels == ("slow", "fast")
    assert result.spec.factors[7].levels == ("manual", "automatic")

    path = tmp_path / "splitplot-v3.dexpl"
    assert app._save_project(path)
    assert app.load_file(path)
    name = next(sheet_name for sheet_name, item in app.sheets.items()
                if item.doe_metadata
                and item.doe_metadata["design"].get("construction_version") == "v3")
    app.nb.select(app.sheetframes[name])
    reopened = app.getCurrentTable()
    assert validate_split_plot_design(reopened.model.df, reopened.doe_metadata).spec == result.spec
    copied = app.copySheet()
    assert copied.doe_metadata == reopened.doe_metadata
    assert_frame_equal(copied.model.df, reopened.model.df)
    assert error.call_count == 0


def test_splitplot_plot_rejects_result_after_response_changes(csv_app, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr("doe_dialog.messagebox.showerror", error)
    monkeypatch.setattr("doe_splitplot_dialog.messagebox.showerror", error)
    dialog = CreateSplitPlot(app)
    assert dialog.create() is True
    table = app.getCurrentTable()
    fill_reference_response(table)
    analysis = AnalyzeDOE(app)
    analysis.analyze()
    assert analysis.result is not None
    response_column = table.model.df.columns.get_loc("响应_Y")
    table.model.setValueAt("999", 0, response_column)
    analysis.plot()
    assert not hasattr(table, "pf")
    error.assert_called_once()
    assert "工作表已更改" in error.call_args.args[1]
    analysis.main.destroy()


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


def test_splitplot_modify_adds_a_complete_block_and_disables_renumber(
        csv_app, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr("doe_splitplot_dialog.messagebox.showerror", error)
    monkeypatch.setattr("doe_optimal_dialog.messagebox.showerror", error)
    source = CreateSplitPlot(app)
    assert source.create() is True
    original = app.getCurrentTable()
    response_column = original.doe_metadata["column_map"]["responses"]["Y"]
    original.model.df[response_column] = pd.array(
        range(1, len(original.model.df) + 1), dtype="Float64")
    original_frame = original.model.df.copy(deep=True)
    names = list(app.sheets)
    cancelled = ModifyDesignDialog(app)
    cancelled.cancel_button.invoke()
    assert list(app.sheets) == names
    assert_frame_equal(original.model.df, original_frame)
    modify = ModifyDesignDialog(app)
    assert str(modify.replicate_button.cget("state")) == "normal"
    assert str(modify.renumber_button.cget("state")) == "disabled"
    modify.rep_count.delete(0, "end")
    modify.rep_count.insert(0, "0")
    modify.replicate_button.invoke()
    assert list(app.sheets) == names
    assert error.call_count == 1
    error.reset_mock()
    modify.rep_count.delete(0, "end")
    modify.rep_count.insert(0, "1")
    modify.replicate_button.invoke()
    expanded = app.getCurrentTable()
    result = validate_split_plot_design(expanded.model.df, expanded.doe_metadata)
    assert result.spec.block_count == 4
    assert len(result.runs) == 16
    assert_frame_equal(original.model.df, original_frame)
    columns = original.doe_metadata["column_map"]
    old_ids = original_frame[columns["run_id"]].tolist()
    old_rows = original_frame.set_index(columns["run_id"])
    new_rows = expanded.model.df.set_index(columns["run_id"])
    for name in (columns["standard_order"], columns["block"],
                 columns["whole_plot_id"], columns["subplot_id"],
                 columns["run_order"], columns["whole_plot_order"],
                 columns["subplot_order"], response_column):
        assert old_rows.loc[old_ids, name].tolist() == new_rows.loc[old_ids, name].tolist()
    repeated = ModifyDesignDialog(app)
    assert str(repeated.replicate_button.cget("state")) == "disabled"
    assert str(repeated.rerandomize_button.cget("state")) == "disabled"
    assert "只支持一次区组增补" in repeated.status.get()
    repeated.main.destroy()
    assert error.call_count == 0


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
    assert lines[0].startswith("运行 104 次；区组 26；整区 52；")
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
    assert lines[0].startswith("运行 10000 次；区组 2500；整区 5000；")
    assert len(lines) == 2 + 100 + 1
    assert lines[-1] == "仅显示前 100 行，共 10000 行"
    dialog.main.destroy()


def test_preview_has_horizontal_scrollbar(csv_app):
    app, _ = csv_app
    dialog = CreateSplitPlot(app)
    assert str(dialog.preview_text.cget("xscrollcommand")) != ""
    assert str(dialog.preview_horizontal.cget("orient")) == "horizontal"
    dialog.main.destroy()


def test_factor_count_roles_and_blocks_recompute_splitplot_preview(csv_app, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr("doe_splitplot_dialog.messagebox.showerror", error)
    dialog = CreateSplitPlot(app)

    def wait_for_preview():
        dialog.main.after(200, dialog.main.quit)
        dialog.main.mainloop()

    dialog.factor_count_var.set("4")
    dialog.factor_values[1]["role"].set("整区因子")
    wait_for_preview()
    assert len(dialog.factor_rows) == 4
    assert "运行 48 次；区组 3；整区 12；每整区子区 4；整区误差 df 6；子区误差 df 24" in \
        dialog.summary.cget("text")
    assert "设定_D" in dialog.preview_text.get("1.0", "end")

    dialog.blocks_var.set("2")
    wait_for_preview()
    assert "运行 32 次；区组 2；整区 8；每整区子区 4；整区误差 df 3；子区误差 df 12" in \
        dialog.summary.cget("text")
    _, metadata = dialog.build()
    assert metadata["design"]["construction_version"] == "v2"
    assert error.call_count == 0
    dialog.close()


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
