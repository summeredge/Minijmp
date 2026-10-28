import pandas as pd
from unittest.mock import Mock

from doe_core import restore_design_result
from doe_custom_dialog import DefineCustomDOE
from doe_dialog import AnalyzeDOE
from doe_optimal_dialog import AugmentDesignDialog, EvaluateDesignDialog, ModifyDesignDialog
from test_csv_import import csv_app
from test_doe_custom_gui import custom_source, fill_dialog


def define_custom_sheet(app, name="自定义"):
    custom_source(app)
    dialog = DefineCustomDOE(app, "custom_factorial")
    fill_dialog(dialog)
    assert dialog.create()
    return app.getCurrentSheet()


def define_partial_sheet(app):
    """只定义 3 个因子点，留一个候选运行用于增补。"""
    frame = pd.DataFrame({
        "运行ID": ["R1", "R2", "R3"],
        "标准序": [1, 2, 3], "运行序": [1, 2, 3],
        "点类型": ["factorial"] * 3, "重复": [1] * 3,
        "A": ["低", "高", "低"], "B": ["低", "低", "高"],
        "Y": [10.0, 14.0, 12.0],
    })
    app.addSheet("部分", frame)
    dialog = DefineCustomDOE(app, "custom_factorial")
    fill_dialog(dialog)
    dialog.response.set("Y")
    assert dialog.create()
    return app.getCurrentSheet()


def test_custom_design_save_reopen_copy_and_reanalyze(csv_app, tmp_path, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr("doe_dialog.messagebox.showerror", error)
    monkeypatch.setattr("worksheets.messagebox.askyesno", lambda *a, **k: True)
    monkeypatch.setattr("worksheets.messagebox.askyesnocancel", lambda *a, **k: False)
    name = define_custom_sheet(app)
    table = app.sheets[name]
    frame = table.model.df
    frame.loc[:, "Y"] = [10.0, 14.0, 12.0, 20.0]
    path = tmp_path / "custom.dexpl"
    assert app._save_project(path)
    assert app.load_file(path)
    reopened = app.sheets[name]
    assert reopened.doe_metadata["design"]["design_type"] == "custom_factorial"
    assert restore_design_result(reopened.model.df,
                                 reopened.doe_metadata).runs[1].responses["Y"] == 14.0
    app.nb.select(app.sheetframes[name])
    copied = app.copySheet()
    assert copied.doe_metadata["design"] == reopened.doe_metadata["design"]
    assert copied.doe_metadata is not reopened.doe_metadata
    analysis = AnalyzeDOE(app)
    analysis.analyze()
    assert analysis.result is not None, analysis.status.get()
    analysis.main.destroy()
    assert error.call_count == 0


def test_augmented_design_survives_save_reopen_and_reanalysis(
        csv_app, tmp_path, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr("doe_dialog.messagebox.showerror", error)
    monkeypatch.setattr("doe_optimal_dialog.messagebox.showerror", error)
    monkeypatch.setattr("worksheets.messagebox.askyesno", lambda *a, **k: True)
    monkeypatch.setattr("worksheets.messagebox.askyesnocancel", lambda *a, **k: False)
    name = define_partial_sheet(app)
    table = app.sheets[name]
    assert len(table.model.df) == 3
    dialog = AugmentDesignDialog(app)
    dialog.candidates.insert("1.0", "高,高")
    assert dialog.create(), error.call_args_list
    augmented_name = app.getCurrentSheet()
    augmented = app.sheets[augmented_name]
    assert augmented.doe_metadata["design"]["augmentation_lineage"] is not None
    # 原始工作表仍保留
    assert name in app.sheets
    path = tmp_path / "augmented.dexpl"
    assert app._save_project(path)
    assert app.load_file(path)
    reopened = app.sheets[augmented_name]
    lineage = reopened.doe_metadata["design"]["augmentation_lineage"]
    assert lineage["parent_design_id"]
    design = restore_design_result(reopened.model.df, reopened.doe_metadata)
    assert len(design.runs) == 4
    app.nb.select(app.sheetframes[augmented_name])
    copied = app.copySheet()
    assert copied.doe_metadata["design"]["augmentation_lineage"] == lineage


def test_bad_metadata_does_not_replace_live_workbook(csv_app, tmp_path, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr("worksheets.messagebox.showerror", error)
    monkeypatch.setattr("worksheets.messagebox.askyesno", lambda *a, **k: True)
    monkeypatch.setattr("worksheets.messagebox.askyesnocancel", lambda *a, **k: False)
    name = define_custom_sheet(app)
    path = tmp_path / "good.dexpl"
    assert app._save_project(path)
    import gzip
    import pickle
    payload = pickle.loads(gzip.decompress(path.read_bytes()))
    for sheet in payload.values():
        if isinstance(sheet, dict) and "meta" in sheet:
            if sheet["meta"].get("doe"):
                sheet["meta"]["doe"]["design"]["design_type"] = "central_composite"
    path.write_bytes(gzip.compress(pickle.dumps(payload)))
    before = list(app.sheets)
    assert not app.load_file(path)
    assert list(app.sheets) == before
    assert app.sheets[name].doe_metadata["design"]["design_type"] == "custom_factorial"


def test_source_sheet_deletion_blocks_analysis_without_crashing(csv_app, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr("doe_dialog.messagebox.showerror", error)
    monkeypatch.setattr("worksheets.messagebox.askyesno", lambda *a, **k: True)
    name = define_custom_sheet(app)
    analysis = AnalyzeDOE(app)
    analysis.main.destroy()
    app.deleteSheet()
    assert name not in app.sheets
    assert error.call_count == 0


def test_distance_augmented_design_round_trips_project(csv_app, tmp_path, monkeypatch):
    """距离增补谱系必须在保存/重开/复制后保持，且父运行响应不变。"""
    from test_doe_optimal_gui import make_rsm, rsm_source

    app, error = csv_app
    monkeypatch.setattr("doe_optimal_dialog.messagebox.showerror", error)
    monkeypatch.setattr("worksheets.messagebox.askyesno", lambda *a, **k: True)
    monkeypatch.setattr("worksheets.messagebox.askyesnocancel", lambda *a, **k: False)
    rsm_source(app)
    make_rsm(app)
    source = app.getCurrentSheet()
    app.sheets[source].model.df["Y"] = [10.0, 12.0, 11.0, 13.0, 12.5, 12.2]
    dialog = AugmentDesignDialog(app)
    dialog.criterion.set("Distance-based")
    dialog.point_type.set("center")
    dialog.candidates.insert("1.0", "0,0")
    assert dialog.create(), error.call_args_list
    name = app.getCurrentSheet()
    path = tmp_path / "distance-augmented.dexpl"
    assert app._save_project(path)
    assert app.load_file(path)
    reopened = app.sheets[name]
    lineage = reopened.doe_metadata["design"]["augmentation_lineage"]
    assert lineage["criterion"] == "distance"
    design = restore_design_result(reopened.model.df, reopened.doe_metadata)
    base = [run for run in design.runs if run.batch_id in (None, "BASE")]
    assert len(base) == 6
    assert [run.responses["Y"] for run in base] == [10.0, 12.0, 11.0, 13.0, 12.5, 12.2]
    app.nb.select(app.sheetframes[name])
    copied = app.copySheet()
    assert copied.doe_metadata["design"]["augmentation_lineage"] == lineage
    assert error.call_count == 0
