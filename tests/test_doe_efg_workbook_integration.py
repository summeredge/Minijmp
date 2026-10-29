"""E/F/G 设计共存于同一 .dexpl 工程时的保存、复制与分析回归。"""
import copy
import gzip
import math
import pickle

import pandas as pd
from pandas.testing import assert_frame_equal

from doe_augment import augment
from doe_core import (DesignSpec, FactorSpec, restore_design_result,
                      worksheet_metadata)
from doe_custom_analysis import analyze_custom_rsm
from doe_dialog import AnalyzeDOE
from doe_mixture import MixtureSpec, restore_mixture
from doe_mixture_analysis import analyze_mixture
from doe_mixture_constraints import ComponentSpec, VariableSpec
from doe_mixture_designs import create_mixture_design
from doe_mixture_dialog import (AnalyzeMixtureDesign, MixturePlots,
                                PredictMixture)
from doe_predict_dialog import PredictRSM
from doe_taguchi import create_taguchi
from doe_taguchi_analysis_dialog import AnalyzeTaguchi
from doe_taguchi_arrays import ARRAYS
from test_csv_import import csv_app


def _e_augmented_rsm():
    frame = pd.DataFrame({
        "运行ID": ["R1", "R2", "R3", "R4", "R5"],
        "标准序": [1, 2, 3, 4, 5],
        "运行序": [1, 2, 3, 4, 5],
        "点类型": ["factorial"] * 4 + ["center"],
        "重复": [1] * 5,
        "批次": ["BASE"] * 5,
        "来源": [None] * 5,
        "X1": [1, -1, 1, -1, 0],
        "X2": [1, 1, -1, -1, 0],
        "Y": [10.0, 12.0, 14.0, 16.0, 13.0],
    })
    terms = ("X1", "X2", "X1²", "X2²", "X1*X2")
    spec = DesignSpec(
        "E-parent",
        (FactorSpec("X1", "X1", -1.7, 1.7),
         FactorSpec("X2", "X2", -1.7, 1.7)),
        ("Y",), seed=13, design_type="custom_rsm", model_terms=terms)
    columns = {
        "run_id": "运行ID", "standard_order": "标准序", "run_order": "运行序",
        "point_type": "点类型", "replicate": "重复", "batch_id": "批次",
        "source_run_id": "来源", "factors": {"X1": "X1", "X2": "X2"},
        "responses": {"Y": "Y"},
    }
    metadata = worksheet_metadata(frame, spec, columns)
    frame, metadata, summary = augment(
        frame, metadata,
        [{"X1": 1.7, "X2": 0}, {"X1": -1.7, "X2": 0},
         {"X1": 0, "X2": 1.7}, {"X1": 0, "X2": -1.7}],
        2, batch_id="E-AUG", point_types=["axial"] * 4)
    assert summary["augmented_rank"] == summary["p"] == 6
    frame["Y"] = [10 + 2 * x1 - 3 * x2 + 4 * x1 ** 2 + 5 * x2 ** 2 + x1 * x2
                   for x1, x2 in zip(frame["X1"], frame["X2"])]
    return frame, metadata


def _f_mixture():
    spec = MixtureSpec(
        "F-mixture",
        tuple(ComponentSpec(key, key) for key in "ABC"),
        ("Y",), "simplex_centroid", None,
        process_variables=(VariableSpec("P", "温度", 20, 40, "C"),),
        amount_variables=(VariableSpec("T", "总量", 100, 300, "g", "amount"),),
        amount_settings=(("T", 200),), seed=9)
    frame, metadata = create_mixture_design(spec)
    a, b, c = (frame[f"设定_{key}"] for key in "ABC")
    process = (frame["设定_P"] - 30) / 10
    frame["响应_Y"] = (2 * a + 4 * b + 6 * c + 8 * a * b + 2 * a * c - 3 * b * c
                       + process * (a + 2 * b - c))
    return frame, metadata


def _g_taguchi():
    array = ARRAYS["L4(2^3)"]
    factors = tuple(
        FactorSpec(key, key, None, None, factor_type="categorical",
                   levels=("低", "高"), level_type="text")
        for key in "ABC")
    spec = DesignSpec(
        "G-taguchi", factors, ("Y",), seed=17, design_type="taguchi",
        taguchi={"kind": "static", "array_id": array.array_id,
                 "matrix_sha256": array.sha256,
                 "columns": {key: index for index, key in enumerate("ABC", 1)},
                 "noise_array_id": None, "noise_matrix_sha256": None,
                 "noise_columns": {}, "signal_factor": None})
    frame, metadata = create_taguchi(spec, replicates=2)
    sign = {"低": -1, "高": 1}
    frame["响应_Y"] = [
        20 + 2 * sign[row["设定_A"]] + 3 * sign[row["设定_B"]]
        + 4 * sign[row["设定_C"]] + (0.5 if row["重复"] == 1 else -0.5)
        for _, row in frame.iterrows()]
    return frame, metadata


def _g_dynamic_taguchi():
    array = ARRAYS["L4(2^3)"]
    factors = (
        FactorSpec("A", "A", None, None, factor_type="categorical",
                   levels=("低", "高"), level_type="text"),
        FactorSpec("B", "B", None, None, factor_type="categorical",
                   levels=("低", "高"), level_type="text"),
        FactorSpec("N", "N", None, None, factor_type="categorical",
                   levels=("低", "高"), level_type="text"),
        FactorSpec("M", "M", None, None, factor_type="categorical",
                   levels=("低", "高"), level_type="text"),
        FactorSpec("S", "S", None, None, factor_type="categorical",
                   levels=(1.0, 2.0, 3.0), level_type="numeric"),
    )
    spec = DesignSpec(
        "G-dynamic-taguchi", factors, ("Y",), seed=23, design_type="taguchi",
        taguchi={"kind": "dynamic", "array_id": array.array_id,
                 "matrix_sha256": array.sha256, "columns": {"A": 1, "B": 2},
                 "noise_array_id": array.array_id,
                 "noise_matrix_sha256": array.sha256, "noise_columns": {"N": 1, "M": 2},
                 "signal_factor": "S"})
    frame, metadata = create_taguchi(spec)
    sign = {"低": -1, "高": 1}
    frame["响应_Y"] = [
        5 + (2 + 0.4 * sign[row["设定_A"]] - 0.25 * sign[row["设定_N"]])
        * row["设定_S"] + 0.1 * row["设定_S"] ** 2
        + 0.15 * sign[row["设定_N"]]
        for _, row in frame.iterrows()]
    return frame, metadata


def _select(app, name):
    app.nb.select(app.sheetframes[name])
    return app.getCurrentTable()


def test_efg_designs_share_project_roundtrip_copy_analysis_and_metadata_isolation(
        csv_app, tmp_path, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr("worksheets.messagebox.askyesno", lambda *args, **kwargs: True)
    monkeypatch.setattr("worksheets.messagebox.askyesnocancel",
                        lambda *args, **kwargs: False)
    monkeypatch.setattr("doe_dialog.messagebox.showerror", error)
    monkeypatch.setattr("doe_predict_dialog.messagebox.showerror", error)
    monkeypatch.setattr("doe_mixture_dialog.messagebox.showerror", error)
    monkeypatch.setattr("doe_taguchi_analysis_dialog.messagebox.showerror", error)

    plain_name = app.getCurrentSheet()
    plain = app.getCurrentTable()
    assert "doe" not in app.saveMeta(plain)
    assert "mixture" not in app.saveMeta(plain)

    e_name, f_name, g_name, gd_name = (
        "E 自定义响应面", "F 混料", "G Taguchi", "G Taguchi 动态")
    e_frame, e_meta = _e_augmented_rsm()
    e_table = app.addSheet(e_name, e_frame, {"doe": e_meta})
    f_frame, f_meta = _f_mixture()
    f_table = app.addSheet(f_name, f_frame, f_meta)
    g_frame, g_meta = _g_taguchi()
    g_table = app.addSheet(g_name, g_frame, {"doe": g_meta})
    gd_frame, gd_meta = _g_dynamic_taguchi()
    gd_table = app.addSheet(gd_name, gd_frame, {"doe": gd_meta})
    expected_frames = {name: frame.copy(deep=True) for name, frame in (
        (e_name, e_frame), (f_name, f_frame), (g_name, g_frame), (gd_name, gd_frame))}

    e_analysis = analyze_custom_rsm(e_table.model.df, e_table.doe_metadata, "Y")
    assert e_analysis["rank"] == 6 and e_analysis["n"] == 7
    assert "mixture" not in app.saveMeta(e_table)
    assert "mixture" in app.saveMeta(f_table)
    assert app.saveMeta(g_table)["doe"]["design"]["design_type"] == "taguchi"
    assert "mixture" not in app.saveMeta(g_table)
    assert analyze_mixture(f_table.model.df, f_table.mixture_metadata, "Y")["rank"] == 9

    _select(app, f_name)
    mixture_analysis = AnalyzeMixtureDesign(app)
    mixture_analysis.analyze()
    assert mixture_analysis.result is not None and mixture_analysis.result["rank"] == 9
    assert f_table.mixture_model["degree"] == 2
    assert f_table.mixture_model["terms"] == [
        "A", "B", "C", "A*B", "A*C", "B*C", "A*P", "B*P", "C*P"]
    mixture_analysis.main.destroy()

    _select(app, g_name)
    taguchi_analysis = AnalyzeTaguchi(app)
    taguchi_analysis.analyze()
    assert taguchi_analysis.result is not None
    assert taguchi_analysis.result["n_observations"] == 8
    assert g_table.doe_metadata["analysis"]["sn_kind"] == "smaller"
    taguchi_analysis.main.destroy()

    _select(app, gd_name)
    dynamic_analysis = AnalyzeTaguchi(app)
    dynamic_analysis.analyze()
    assert dynamic_analysis.result is not None
    assert dynamic_analysis.result["kind"] == "dynamic"
    assert dynamic_analysis.result["n_observations"] == 48
    assert gd_table.doe_metadata["analysis"] == {
        "kind": "dynamic", "reference_mode": "free", "reference": None,
        "adjusted": False}
    dynamic_analysis.main.destroy()

    path = tmp_path / "doe-efg.dexpl"
    assert app._save_project(path)
    assert app.load_file(path)

    plain = app.sheets[plain_name]
    e_source, f_source, g_source, gd_source = (app.sheets[name] for name in
                                                (e_name, f_name, g_name, gd_name))
    assert plain.doe_metadata is None and plain.mixture_metadata is None
    assert_frame_equal(e_source.model.df, expected_frames[e_name])
    e_restored = restore_design_result(e_source.model.df, e_source.doe_metadata)
    assert [run.run_id for run in e_restored.runs] == expected_frames[e_name]["运行ID"].tolist()
    assert [run.responses["Y"] for run in e_restored.runs] == expected_frames[e_name]["Y"].tolist()
    assert e_restored.spec.model_terms == ("X1", "X2", "X1²", "X2²", "X1*X2")
    lineage = e_restored.spec.augmentation_lineage
    assert lineage["parent_design_id"] == "E-parent" and lineage["batch_id"] == "E-AUG"
    added_ids = {new_id for _, new_id in lineage["run_map"]}
    assert len(added_ids) == 2
    assert all(run.batch_id == "E-AUG" for run in e_restored.runs
               if run.run_id in added_ids)
    assert e_source.mixture_metadata is None
    assert f_source.doe_metadata["design"]["design_type"] == "mixture"
    assert f_source.mixture_metadata["spec"]["design_id"] == "F-mixture"
    assert f_source.mixture_model == f_table.mixture_model
    f_spec, f_rows = restore_mixture(f_source.model.df, f_source.mixture_metadata)
    assert [row["run_id"] for row in f_rows] == expected_frames[f_name]["运行ID"].tolist()
    assert [row["row"]["响应_Y"] for row in f_rows] == \
        expected_frames[f_name]["响应_Y"].tolist()
    assert f_spec.component_ids == ("A", "B", "C")
    assert [item.role for item in f_spec.process_variables] == ["process"]
    assert [item.role for item in f_spec.amount_variables] == ["amount"]
    assert dict(f_spec.amount_settings) == {"T": 200.0}
    assert f_source.mixture_model["terms"] == [
        "A", "B", "C", "A*B", "A*C", "B*C", "A*P", "B*P", "C*P"]
    assert g_source.doe_metadata["design"]["taguchi"]["array_id"] == "L4(2^3)"
    assert g_source.doe_metadata["analysis"]["sn_kind"] == "smaller"
    g_restored = restore_design_result(g_source.model.df, g_source.doe_metadata)
    assert [run.run_id for run in g_restored.runs] == expected_frames[g_name]["运行ID"].tolist()
    assert [run.responses["Y"] for run in g_restored.runs] == \
        expected_frames[g_name]["响应_Y"].tolist()
    assert all(run.control_run_id is not None and run.noise_condition_id is not None
               for run in g_restored.runs)
    assert g_source.mixture_metadata is None
    gd_restored = restore_design_result(gd_source.model.df, gd_source.doe_metadata)
    assert [run.run_id for run in gd_restored.runs] == expected_frames[gd_name]["运行ID"].tolist()
    assert [run.responses["Y"] for run in gd_restored.runs] == \
        expected_frames[gd_name]["响应_Y"].tolist()
    assert gd_restored.spec.taguchi["signal_factor"] == "S"
    assert dict(gd_restored.spec.taguchi["columns"]) == {"A": 1, "B": 2}
    assert dict(gd_restored.spec.taguchi["noise_columns"]) == {"N": 1, "M": 2}
    assert all(run.control_run_id is not None and run.noise_condition_id is not None
               for run in gd_restored.runs)
    assert gd_source.doe_metadata["analysis"] == {
        "kind": "dynamic", "reference_mode": "free", "reference": None,
        "adjusted": False}
    assert "doe" not in app.saveMeta(plain) and "mixture" not in app.saveMeta(plain)

    copies = {}
    for name in (e_name, f_name, g_name, gd_name):
        source = _select(app, name)
        copied = app.copySheet()
        copies[name] = copied
        assert_frame_equal(copied.model.df, expected_frames[name])
        assert copied.doe_metadata == source.doe_metadata
        assert copied.doe_metadata is not source.doe_metadata
        assert copied.doe_metadata["design"] is not source.doe_metadata["design"]
    assert copies[f_name].mixture_metadata == f_source.mixture_metadata
    assert copies[f_name].mixture_metadata is not f_source.mixture_metadata
    assert copies[f_name].mixture_model == f_source.mixture_model
    assert copies[f_name].mixture_model is not f_source.mixture_model

    e_copy_result = analyze_custom_rsm(
        copies[e_name].model.df, copies[e_name].doe_metadata, "Y")
    assert e_copy_result["n"] == 7 and e_copy_result["rank"] == 6

    _select(app, e_name + " 副本")
    doe_analysis = AnalyzeDOE(app)
    doe_analysis.analyze()
    assert doe_analysis.result is not None
    diagnostic_tabs = [tab for tab in doe_analysis.tabs.tabs()
                       if doe_analysis.tabs.tab(tab, 'text') == '逐点影响诊断']
    assert len(diagnostic_tabs) == 1
    diagnostic_frame = doe_analysis.tabs.nametowidget(diagnostic_tabs[0])
    diagnostic_table = next(child.table for child in diagnostic_frame.winfo_children()
                            if getattr(child, 'table', None) is not None)
    assert [row[0] for row in diagnostic_table.values] == \
        expected_frames[e_name]['运行ID'].tolist()
    doe_analysis.factor_x.set("X1")
    doe_analysis.factor_y.set("X2")
    doe_analysis.plot()
    assert copies[e_name].pf is not None and len(copies[e_name].pf.fig.axes) == 4
    doe_analysis.main.destroy()
    copies[e_name].pf.close()
    e_prediction = PredictRSM(app)
    e_prediction.predict()
    assert e_prediction.block is not None
    assert any(row[0] == "预测响应" and math.isclose(float(row[1]), 10, abs_tol=1e-8)
               for row in e_prediction.block.table.values)
    e_prediction.main.destroy()

    _select(app, f_name + " 副本")
    predictor = PredictMixture(app)
    predictor.predict()
    prediction_rows = [row for tab in predictor.tabs.tabs()
                       for block in predictor.tabs.nametowidget(tab).winfo_children()
                       for row in getattr(getattr(block, "table", None), "values", [])]
    expected_prediction = 2 / 3 + 4 / 3 + 6 / 3 + 7 / 9
    assert any(row[0] == "Y" and math.isclose(float(row[1]), expected_prediction,
                                                rel_tol=1e-7)
               for row in prediction_rows)
    predictor.main.destroy()

    mixture_plots = MixturePlots(app)
    mixture_plots.kind.set("Trace")
    mixture_plots.draw()
    assert copies[f_name].pf is not None
    assert "Trace Plot" in copies[f_name].pf.fig.axes[0].get_title()
    copies[f_name].pf.close()
    mixture_plots.main.destroy()

    mixture_copy_analysis = AnalyzeMixtureDesign(app)
    assert mixture_copy_analysis.degree.get() == "2"
    mixture_copy_analysis.degree.set("1")
    mixture_copy_analysis.terms.delete(0, "end")
    mixture_copy_analysis.analyze()
    assert mixture_copy_analysis.result is not None
    assert copies[f_name].mixture_model["degree"] == 1
    assert f_source.mixture_model["degree"] == 2
    mixture_copy_analysis.main.destroy()

    _select(app, g_name + " 副本")
    taguchi_copy_analysis = AnalyzeTaguchi(app)
    assert taguchi_copy_analysis.sn_kind.get() == "Smaller is better"
    taguchi_copy_analysis.sn_kind.set("Larger is better")
    taguchi_copy_analysis.analyze()
    assert taguchi_copy_analysis.result is not None
    assert copies[g_name].doe_metadata["analysis"]["sn_kind"] == "larger"
    assert g_source.doe_metadata["analysis"]["sn_kind"] == "smaller"
    taguchi_copy_analysis.best()
    assert math.isfinite(taguchi_copy_analysis.best_window.result['predicted_mean'])
    taguchi_copy_analysis.best_window.main.destroy()
    taguchi_copy_analysis.plot()
    assert copies[g_name].pf is not None
    taguchi_copy_analysis.main.destroy()
    copies[g_name].pf.close()

    _select(app, gd_name + " 副本")
    dynamic_copy_analysis = AnalyzeTaguchi(app)
    assert dynamic_copy_analysis.reference_mode.get() == "自由截距"
    dynamic_copy_analysis.reference_mode.set("固定参考点")
    dynamic_copy_analysis.signal_reference.insert(0, "2")
    dynamic_copy_analysis.response_reference.insert(0, "5")
    dynamic_copy_analysis.analyze()
    assert dynamic_copy_analysis.result is not None
    dynamic_copy_analysis.best()
    assert math.isfinite(dynamic_copy_analysis.best_window.result['predicted_mean'])
    dynamic_copy_analysis.best_window.main.destroy()
    dynamic_copy_analysis.plot()
    assert copies[gd_name].pf is not None
    assert copies[gd_name].pf.fig.axes[0].get_title() == "Signal vs Response"
    assert copies[gd_name].doe_metadata["analysis"] == {
        "kind": "dynamic", "reference_mode": "fixed", "reference": [2.0, 5.0],
        "adjusted": False}
    assert gd_source.doe_metadata["analysis"]["reference_mode"] == "free"
    dynamic_copy_analysis.main.destroy()
    copies[gd_name].pf.close()

    error.assert_not_called()

    with gzip.open(path, "rb") as stream:
        damaged = pickle.load(stream)
    damaged[g_name]["meta"]["doe"]["analysis"]["sn_kind"] = "invalid"
    bad_path = tmp_path / "doe-efg-bad-meta.dexpl"
    with gzip.open(bad_path, "wb") as stream:
        pickle.dump(damaged, stream, protocol=pickle.HIGHEST_PROTOCOL)
    live_tables = dict(app.sheets)
    live_active = app.getCurrentTable()
    live_frames = {name: table.model.df.copy(deep=True)
                   for name, table in live_tables.items()}
    live_metadata = {name: copy.deepcopy(app.saveMeta(table, validate_doe=False))
                     for name, table in live_tables.items()}
    assert not app.load_file(bad_path)
    assert list(app.sheets) == list(live_tables)
    assert app.table is live_active
    assert app.getCurrentTable() is live_active
    for name, table in live_tables.items():
        assert app.sheets[name] is table
        assert_frame_equal(table.model.df, live_frames[name])
        assert app.saveMeta(table, validate_doe=False) == live_metadata[name]
    error.assert_called_once()
