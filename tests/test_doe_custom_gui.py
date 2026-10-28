import pandas as pd
from unittest.mock import Mock

from doe_custom_dialog import DefineCustomDOE
from doe_dialog import AnalyzeDOE
from doe_optimal_dialog import AugmentDesignDialog, EvaluateDesignDialog, ModifyDesignDialog
from test_csv_import import csv_app


def custom_source(app):
    frame = pd.DataFrame({
        "运行ID": [f"R{i}" for i in range(1, 5)],
        "标准序": [1, 2, 3, 4],
        "运行序": [1, 2, 3, 4],
        "点类型": ["factorial"] * 4,
        "重复": [1] * 4,
        "A": ["低", "高", "低", "高"],
        "B": ["低", "低", "高", "高"],
        "Y": [10.0, 14.0, 12.0, 20.0],
    })
    return app.addSheet("源", frame)


def fill_dialog(dialog):
    for index in range(2):
        row = dialog.factor_rows[index]
        row[0].delete(0, "end")
        row[0].insert(0, "AB"[index])
        row[2].set("两水平分类")
        row[5].insert(0, "低;高")
        row[6].delete(0, "end")
        row[6].insert(0, "AB"[index])
    for row in dialog.factor_rows[2:]:
        row[0].delete(0, "end")
    for key in ("run_id", "standard_order", "run_order", "point_type", "replicate"):
        dialog.mapping[key].set({"run_id": "运行ID", "standard_order": "标准序",
                                 "run_order": "运行序", "point_type": "点类型",
                                 "replicate": "重复"}[key])
    dialog.mapping["block"].set("")
    dialog.response.set("Y")


def test_custom_factorial_gui_preview_cancel_create_and_analyze(csv_app, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr("doe_custom_dialog.messagebox.showerror", error)
    monkeypatch.setattr("worksheets.messagebox.askyesno", lambda *a, **k: True)
    monkeypatch.setattr("worksheets.messagebox.askyesnocancel", lambda *a, **k: False)
    custom_source(app)
    names = list(app.sheets)
    dialog = DefineCustomDOE(app, "custom_factorial")
    fill_dialog(dialog)
    dialog.preview_click()
    preview = dialog.preview.get("1.0", "end")
    assert "运行数：4" in preview
    assert "矩阵秩：3 / 3" in preview
    dialog.main.destroy()
    assert list(app.sheets) == names

    dialog = DefineCustomDOE(app, "custom_factorial")
    fill_dialog(dialog)
    assert dialog.create()
    table = app.getCurrentTable()
    assert table.doe_metadata["design"]["design_type"] == "custom_factorial"
    assert len(table.model.df) == 4
    analysis = AnalyzeDOE(app)
    analysis.analyze()
    assert analysis.result is not None, analysis.status.get()
    tabs = [analysis.tabs.tab(tab, "text") for tab in analysis.tabs.tabs()]
    assert "诊断合同" in tabs
    analysis.factor_x.set("A")
    analysis.factor_y.set("B")
    analysis.plot()
    assert table.pf is not None and len(table.pf.fig.axes) == 6
    assert table.pf.fig.axes[1].get_title() == "A × B 交互图"
    assert error.call_count == 0
    analysis.main.destroy()


def test_custom_gui_rejects_bad_input_without_adding_sheet(csv_app, monkeypatch):
    app, _ = csv_app
    error = Mock()
    monkeypatch.setattr("doe_custom_dialog.messagebox.showerror", error)
    custom_source(app)
    names = list(app.sheets)
    dialog = DefineCustomDOE(app, "custom_rsm")
    fill_dialog(dialog)
    assert not dialog.create()
    assert list(app.sheets) == names
    assert error.call_count == 1
    dialog.main.destroy()


def test_modify_and_evaluate_dialogs_operate_on_custom_design(csv_app, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr("doe_optimal_dialog.messagebox.showerror", error)
    custom_source(app)
    dialog = DefineCustomDOE(app, "custom_factorial")
    fill_dialog(dialog)
    dialog.create()
    modify = ModifyDesignDialog(app)
    assert modify.summary["family"] == "custom"
    modify.seed.delete(0, "end")
    modify.seed.insert(0, "9")
    assert modify.preview_click()
    preview = modify.preview.get("1.0", "end")
    assert "修改前" in preview and "修改后" in preview
    assert "运行序变化" in preview
    # 预览必须与真实重算一致：同一 seed 的随机化结果就是运行序的真值。
    from doe_modify import rerandomize
    frame = app._full_frame(app.getCurrentTable())
    expected, _ = rerandomize(frame, app.getCurrentTable().doe_metadata, 9)
    columns = app.getCurrentTable().doe_metadata["column_map"]
    for run_id, order in zip(expected[columns["run_id"]], expected[columns["run_order"]]):
        assert f"{run_id}@{order}" in " ".join(preview.split())
    assert modify.rerandomize()
    assert "重新随机化" in app.getCurrentSheet()
    evaluate = EvaluateDesignDialog(app)
    text = evaluate.text.get("1.0", "end")
    assert "矩阵秩" in text
    assert "仅可与相同模型项" in text
    evaluate.main.destroy()
    augment = AugmentDesignDialog(app)
    augment.main.destroy()
    assert error.call_count == 0


def test_modify_preview_distinguishes_rerandomize_from_display_reorder(
        csv_app, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr("doe_optimal_dialog.messagebox.showerror", error)
    custom_source(app)
    dialog = DefineCustomDOE(app, "custom_factorial")
    fill_dialog(dialog)
    dialog.create()
    sheets = list(app.sheets)
    modify = ModifyDesignDialog(app)
    assert modify.preview_click()
    rerandomized = modify.preview.get("1.0", "end")
    assert "重新随机化" in rerandomized
    modify.order.set("run")
    assert modify.preview_click()
    reordered = modify.preview.get("1.0", "end")
    # 只重排显示时同一运行的运行序不变，不能报告成随机化。
    assert "按运行序重排显示" in reordered
    assert "运行序变化：0/" in reordered
    modify.seed.delete(0, "end")
    modify.seed.insert(0, "bad")
    modify.order.set("standard")
    assert not modify.preview_click()
    assert "预览不可用" in modify.status.get()
    # 预览与失败都不应写入工作簿。
    assert list(app.sheets) == sheets
    modify.main.destroy()
    assert error.call_count == 0


def test_modify_gui_renumber_and_full_replicate_then_analyze(csv_app, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr("doe_optimal_dialog.messagebox.showerror", error)
    monkeypatch.setattr("doe_dialog.messagebox.showerror", error)
    custom_source(app)
    dialog = DefineCustomDOE(app, "custom_factorial")
    fill_dialog(dialog)
    dialog.create()

    modify = ModifyDesignDialog(app)
    assert modify.renumber()
    assert "重编号" in app.getCurrentSheet()

    modify = ModifyDesignDialog(app)
    modify.rep_count.delete(0, "end")
    modify.rep_count.insert(0, "1")
    assert modify.replicate()
    sheet = app.getCurrentSheet()
    assert "完整重复" in sheet
    table = app.getCurrentTable()
    assert len(table.model.df) == 8
    assert sorted(set(table.model.df["重复"])) == [1, 2]
    # 新增重复的响应留空，分析前需实际填写；这里按同一模型补齐。
    frame = table.model.df
    for index, row in frame.iterrows():
        a = 2 * (row["A"] == "高") - 1
        b = 2 * (row["B"] == "高") - 1
        table.model.setValueAt(str(10 + 3 * a - 2 * b + 4 * a * b), index,
                               frame.columns.get_loc("Y"))

    analysis = AnalyzeDOE(app)
    analysis.analyze()
    assert analysis.result is not None, analysis.status.get()
    # 独立重复应给出纯误差自由度，且原响应不被复制到新增行。
    assert analysis.result["pure_error_df"] == 4
    assert analysis.result["n"] == 8
    analysis.main.destroy()
    assert error.call_count == 0


def test_custom_rsm_gui_analysis_and_response_surface_plot(csv_app, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr("doe_dialog.messagebox.showerror", error)
    from doe_core import FactorSpec
    from doe_custom import define_custom
    from test_doe_custom_rsm import reference_frame, factors, columns
    from test_doe_custom_rsm import TERMS

    out, metadata, summary = define_custom(
        reference_frame(), design_type="custom_rsm", factors=factors(),
        responses=("Y",), column_map=columns(), model_terms=TERMS,
        design_id="custom-rsm")
    assert summary["rank"] == 10 == summary["p"]
    table = app.addSheet("自定义响应面", out)
    table.doe_metadata = metadata
    analysis = AnalyzeDOE(app)
    analysis.analyze()
    assert analysis.result is not None, analysis.status.get()
    assert "项平方和" in [analysis.tabs.tab(tab, "text")
                          for tab in analysis.tabs.tabs()]
    analysis.factor_x.set("X1")
    analysis.factor_y.set("X2")
    analysis.plot()
    assert table.pf is not None and len(table.pf.fig.axes) == 4
    assert "因子点范围外" in table.pf.fig.axes[0].get_title()
    assert error.call_count == 0
    analysis.main.destroy()


def test_custom_screening_gui_analysis_and_effect_plot(csv_app, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr("doe_dialog.messagebox.showerror", error)
    from doe_custom import define_custom
    from test_doe_custom_screening import reference_frame, factors, columns

    out, metadata, summary = define_custom(
        reference_frame(), design_type="custom_screening", factors=factors(),
        responses=("Y",), column_map=columns(), design_id="custom-dsd")
    assert summary["main_orthogonal"] is True
    assert summary["main_two_factor_orthogonal"] is True
    table = app.addSheet("自定义筛选", out)
    table.doe_metadata = metadata
    analysis = AnalyzeDOE(app)
    analysis.analyze()
    assert analysis.result is not None, analysis.status.get()
    analysis.plot()
    assert table.pf is not None and len(table.pf.fig.axes) == 6
    assert table.pf.fig.axes[0].get_title() == "主效应绝对值 Pareto 图"
    assert error.call_count == 0
    analysis.main.destroy()
