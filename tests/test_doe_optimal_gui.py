from unittest.mock import Mock

import pandas as pd

from doe_custom_dialog import DefineCustomDOE
from doe_optimal_dialog import OptimalDesignDialog
from test_csv_import import csv_app
from test_doe_custom_gui import custom_source, fill_dialog


def rsm_source(app):
    frame = pd.DataFrame({
        "运行ID": [f"C{i}" for i in range(1, 7)],
        "标准序": list(range(1, 7)),
        "运行序": list(range(1, 7)),
        "点类型": ["factorial"] * 6,
        "重复": [1] * 6,
        "X1": [-1, 1, -1, 1, 0, 0],
        "X2": [-1, -1, 1, 1, -1, 1],
        "Y": [None] * 6,
    })
    return app.addSheet("候选", frame)


def make_rsm(app):
    dialog = DefineCustomDOE(app, "custom_rsm")
    for index, factor in enumerate(("X1", "X2")):
        row = dialog.factor_rows[index]
        row[0].delete(0, "end")
        row[0].insert(0, factor)
        row[2].set("连续")
        row[3].insert(0, "-1")
        row[4].insert(0, "1")
        row[6].delete(0, "end")
        row[6].insert(0, factor)
    for row in dialog.factor_rows[2:]:
        row[0].delete(0, "end")
    for key, label in (("run_id", "运行ID"), ("standard_order", "标准序"),
                       ("run_order", "运行序"), ("point_type", "点类型"),
                       ("replicate", "重复")):
        dialog.mapping[key].set(label)
    dialog.mapping["block"].set("")
    dialog.response.set("Y")
    dialog.terms.delete(0, "end")
    dialog.terms.insert(0, "X1;X2;X1*X2")
    assert dialog.create()
    return app.getCurrentTable()


def test_optimal_gui_preview_cancel_and_create(csv_app, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr("doe_optimal_dialog.messagebox.showerror", error)
    monkeypatch.setattr("worksheets.messagebox.askyesno", lambda *a, **k: True)
    monkeypatch.setattr("worksheets.messagebox.askyesnocancel", lambda *a, **k: False)
    rsm_source(app)
    make_rsm(app)
    defined = app.getCurrentSheet()
    names = list(app.sheets)
    dialog = OptimalDesignDialog(app)
    dialog.sheet.set(defined)
    dialog.kind.set("自定义响应面")
    dialog._kind_changed()
    dialog.count.delete(0, "end")
    dialog.count.insert(0, "4")
    dialog.seed.delete(0, "end")
    dialog.seed.insert(0, "3")
    dialog.preview_click()
    preview = dialog.preview.get("1.0", "end")
    assert "已选数：4" in preview
    assert "全局最优已证明：是" in preview
    dialog.main.destroy()
    assert list(app.sheets) == names

    dialog = OptimalDesignDialog(app)
    dialog.sheet.set(defined)
    dialog.kind.set("自定义响应面")
    dialog._kind_changed()
    dialog.count.delete(0, "end")
    dialog.count.insert(0, "4")
    assert dialog.create()
    table = app.getCurrentTable()
    assert len(table.model.df) == 4
    lineage = table.doe_metadata["design"]["optimal_lineage"]
    assert lineage["criterion"] == "d_optimal"
    assert len(lineage["selection_order"]) == 4
    assert error.call_count == 0


def test_optimal_gui_rejects_factorial_distance_option(csv_app, monkeypatch):
    app, _ = csv_app
    error = Mock()
    monkeypatch.setattr("doe_optimal_dialog.messagebox.showerror", error)
    custom_source(app)
    dialog = DefineCustomDOE(app, "custom_factorial")
    fill_dialog(dialog)
    dialog.create()
    optimal = OptimalDesignDialog(app)
    optimal.sheet.set("源")
    assert tuple(optimal.criterion["values"]) == ("D-optimal",)
    assert str(optimal.criterion["state"]) == "disabled"
    optimal.main.destroy()
    assert error.call_count == 0


def test_optimal_gui_distance_preview_reports_rank_and_rejects_deficient(
        csv_app, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr("doe_optimal_dialog.messagebox.showerror", error)
    monkeypatch.setattr("worksheets.messagebox.askyesno", lambda *a, **k: True)
    monkeypatch.setattr("worksheets.messagebox.askyesnocancel", lambda *a, **k: False)
    rsm_source(app)
    make_rsm(app)
    defined = app.getCurrentSheet()
    names = list(app.sheets)

    dialog = OptimalDesignDialog(app)
    dialog.sheet.set(defined)
    dialog.kind.set("自定义响应面")
    dialog._kind_changed()
    dialog.criterion.set("Distance-based")
    dialog.count.delete(0, "end")
    dialog.count.insert(0, "3")
    assert not dialog.preview_click()
    preview = dialog.preview.get("1.0", "end")
    assert "预览不可用" in preview
    assert "不能估计目标模型" in preview
    dialog.main.destroy()
    assert list(app.sheets) == names

    dialog = OptimalDesignDialog(app)
    dialog.sheet.set(defined)
    dialog.kind.set("自定义响应面")
    dialog._kind_changed()
    dialog.criterion.set("Distance-based")
    dialog.count.delete(0, "end")
    dialog.count.insert(0, "6")
    assert dialog.preview_click()
    preview = dialog.preview.get("1.0", "end")
    assert "选中运行：6" in preview
    # 该夹具模型项为 X1;X2;X1*X2，故参数数为 4，秩同为 4。
    assert "参数数：4" in preview
    assert "实际秩：4" in preview
    assert "模型可估计" in preview
    dialog.main.destroy()


def _button_bars(window):
    """返回含按钮的容器及其 pack 边；底部操作条必须是 side='bottom'。"""
    bars = {}
    stack = [window]
    while stack:
        widget = stack.pop()
        stack.extend(widget.winfo_children())
        if widget.winfo_class() != "TFrame":
            continue
        labels = [child.cget("text") for child in widget.winfo_children()
                  if child.winfo_class() == "TButton"]
        if labels:
            bars[tuple(labels)] = widget.pack_info()["side"]
    return bars


def test_e_dialogs_keep_bottom_buttons_visible_in_small_window(
        csv_app, monkeypatch):
    from doe_optimal_dialog import AugmentDesignDialog, ModifyDesignDialog

    app, _ = csv_app
    monkeypatch.setattr("doe_optimal_dialog.messagebox.showerror", Mock())
    custom_source(app)
    dialog = DefineCustomDOE(app, "custom_factorial")
    fill_dialog(dialog)
    dialog.create()
    rsm_source(app)
    make_rsm(app)
    defined = app.getCurrentSheet()
    windows = {"modify": ModifyDesignDialog(app).main,
               "augment": AugmentDesignDialog(app).main}
    optimal = OptimalDesignDialog(app)
    optimal.sheet.set(defined)
    optimal.kind.set("自定义响应面")
    optimal._kind_changed()
    windows["optimal"] = optimal.main
    for name, window in windows.items():
        # 根窗口在测试中不映射，几何测量不可靠；断言打包契约即可。
        bars = _button_bars(window)
        assert bars, name
        assert all(side == "bottom" for side in bars.values()), (name, bars)
        window.destroy()


def test_augment_gui_offers_distance_only_for_response_surface(
        csv_app, monkeypatch):
    from doe_optimal_dialog import AugmentDesignDialog

    app, error = csv_app
    monkeypatch.setattr("doe_optimal_dialog.messagebox.showerror", error)
    monkeypatch.setattr("worksheets.messagebox.askyesno", lambda *a, **k: True)
    monkeypatch.setattr("worksheets.messagebox.askyesnocancel", lambda *a, **k: False)

    custom_source(app)
    dialog = DefineCustomDOE(app, "custom_factorial")
    fill_dialog(dialog)
    assert dialog.create()
    factor_dialog = AugmentDesignDialog(app)
    # 因子设计只提供 D-optimal 与按输入顺序，不提供距离准则。
    assert tuple(factor_dialog.criterion["values"]) == ("D-optimal", "按输入顺序")
    assert "Distance-based" not in factor_dialog.criterion["values"]
    factor_dialog.main.destroy()

    rsm_source(app)
    make_rsm(app)
    rsm_dialog = AugmentDesignDialog(app)
    assert tuple(rsm_dialog.criterion["values"]) == (
        "D-optimal", "Distance-based", "按输入顺序")
    # 距离准则走完整 GUI 提交路径：父设计 6 行、完整二次项需 6 参数，
    # 只补 1 个中心点即可满秩，谱系必须记录 distance。
    rsm_dialog.criterion.set("Distance-based")
    rsm_dialog.point_type.set("center")
    rsm_dialog.candidates.insert("1.0", "0,0")
    assert rsm_dialog.create(), error.call_args_list
    lineage = app.getCurrentTable().doe_metadata["design"]["augmentation_lineage"]
    assert lineage["criterion"] == "distance"
    assert error.call_count == 0
