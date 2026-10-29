from dataclasses import replace
import math
from threading import Event
import time

import pandas as pd
from pandas.testing import assert_frame_equal
import pytest

from doe_core import DesignSpec, FactorSpec, restore_design_result
from doe_bbd import create_bbd
from doe_custom import define_custom
from doe_dsd import create_dsd
from doe_factorial import create_factorial
from doe_fractional import create_fractional
from doe_general_factorial import create_general_factorial
from doe_pb import create_pb
from doe_binary_dialog import AnalyzeBinaryDOE
from doe_variability_dialog import AnalyzeVariabilityDOE
from doe_power_dialog import AnalyzeDOEPower
from test_doe_custom_rsm import columns as custom_columns
from test_doe_custom_rsm import factors as custom_factors
from test_doe_custom_rsm import reference_frame as custom_rsm_frame
from test_doe_dsd import dsd_spec as make_dsd_spec
from test_doe_pb import pb_spec as make_pb_spec
from test_csv_import import csv_app


def _factorial_data():
    spec = DesignSpec(
        "h-lifecycle", (FactorSpec("A", "A", -1, 1),
                        FactorSpec("B", "B", -1, 1)),
        ("Events", "Trials", "M1", "M2", "M3"), seed=17,
        design_type="two_level_full",
    )
    frame, metadata = create_factorial(spec, replicates=2)
    for index, row in frame.iterrows():
        a = int(row["设定_A"])
        b = int(row["设定_B"])
        frame.at[index, "响应_Events"] = 8 + 2 * a + b
        frame.at[index, "响应_Trials"] = 20
        spread = 1 + 0.2 * a + 0.15 * b + 0.1 * int(row["重复"])
        center = 12 + a + 0.5 * b
        for name, value in zip(("M1", "M2", "M3"),
                               (center - spread, center, center + spread)):
            frame.at[index, f"响应_{name}"] = value
    return frame, metadata


def _add_h_design(app):
    frame, metadata = _factorial_data()
    table = app.addSheet("DOE H", frame, {"doe": metadata})
    app.nb.select(app.sheetframes["DOE H"])
    return table


def _set_binary_counts(frame, event_function, trials=20):
    for index, row in frame.iterrows():
        frame.at[index, "响应_Events"] = event_function(row)
        frame.at[index, "响应_Trials"] = trials
    return frame


def _binary_optimizer_rsm_table(app, seed, name):
    factors = tuple(FactorSpec(name, name, -1, 1) for name in "ABC")
    spec = DesignSpec(f"binary-optimizer-{seed}", factors, ("Events", "Trials"),
                      seed=seed, design_type="box_behnken")
    frame, metadata = create_bbd(spec)
    frame = _set_binary_counts(
        frame, lambda row: 10 + int(row["设定_A"] > 0)
        + int(row["设定_B"] > 0) + int(row["设定_C"] > 0), trials=20)
    return app.addSheet(name, frame, {"doe": metadata})


def _binary_optimizer_dialog(app, seed=67, name="Binary Optimizer RSM"):
    table = _binary_optimizer_rsm_table(app, seed, name)
    app.nb.select(app.sheetframes[name])
    dialog = AnalyzeBinaryDOE(app, "rsm")
    dialog.events.set("响应_Events")
    dialog.trials.set("响应_Trials")
    _button(dialog, "分析").invoke()
    assert dialog.result is not None
    assert str(dialog.probability_button["state"]) == "normal"
    assert str(dialog.optimizer_button["state"]) == "normal"
    return dialog, table


def _wait_binary_optimizer(app, dialog, timeout=5):
    deadline = time.monotonic() + timeout
    while dialog.future is not None and time.monotonic() < deadline:
        app.update()
        time.sleep(0.01)
    app.update()
    assert dialog.future is None


def _button(dialog, label):
    for parent in dialog.main.winfo_children():
        for child in parent.winfo_children():
            if child.winfo_class() == "TButton" and child.cget("text") == label:
                return child
    raise AssertionError(f"button not found: {label}")


def _radio(dialog, label):
    pending = list(dialog.main.winfo_children())
    while pending:
        widget = pending.pop()
        if widget.winfo_class() == "TRadiobutton" and widget.cget("text") == label:
            return widget
        pending.extend(widget.winfo_children())
    raise AssertionError(f"radio button not found: {label}")


def _menu_labels(menu):
    return {
        menu.entrycget(index, "label").strip()
        for index in range(menu.index("end") + 1)
        if menu.type(index) == "command"
    }


def test_h_binary_variability_and_power_windows_use_real_tk(csv_app, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr("doe_binary_dialog.messagebox.showerror", error)
    monkeypatch.setattr("doe_variability_dialog.messagebox.showerror", error)
    monkeypatch.setattr("doe_power_dialog.messagebox.showerror", error)
    assert {
        "因子设计二元响应分析", "筛选设计二元响应分析",
        "响应面二元响应分析", "因子设计变异性分析",
    } <= _menu_labels(app.doe_menu["var"])
    assert "试验设计功效与样本量" in _menu_labels(app.stats_menu["var"])
    table = _add_h_design(app)

    binary = AnalyzeBinaryDOE(app, "factorial")
    binary.main.update_idletasks()
    assert binary.main.winfo_exists()
    binary.events.set("响应_Events")
    binary.trials.set("响应_Trials")
    assert str(_button(binary, "分析")["state"]) == "normal"
    _button(binary, "分析").invoke()
    assert binary.result["n_runs"] == len(table.model.df)
    assert len(binary.tabs.tabs()) == 4
    binary.main.update_idletasks()
    _button(binary, "取消").invoke()
    assert not binary.main.winfo_exists()

    app.nb.select(app.sheetframes["DOE H"])
    variability = AnalyzeVariabilityDOE(app)
    variability.response_list.selection_set(2, 4)
    _button(variability, "分析").invoke()
    assert variability.result["mode"] == "within_run"
    assert len(variability.result["summaries"]) == len(table.model.df)
    assert variability.result["summaries"][0]["n"] == 3
    assert variability.result["fit"]["df_error"] > 0
    _button(variability, "ln(SD) 主效应图").invoke()
    assert any(variability.tabs.tab(tab, "text") == "ln(SD) 主效应图"
               for tab in variability.tabs.tabs())
    _radio(variability, "独立运行单响应").invoke()
    _button(variability, "分析").invoke()
    assert variability.result["mode"] == "independent_runs"
    assert len(variability.result["summaries"]) == 4
    assert all(row["n"] == 2 for row in variability.result["summaries"])
    _button(variability, "取消").invoke()
    assert not variability.main.winfo_exists()

    app.nb.select(app.sheetframes["DOE H"])
    power = AnalyzeDOEPower(app)
    power.main.update_idletasks()
    assert power.main.winfo_exists()
    power.delta.set("-2")
    _button(power, "计算").invoke()
    assert power.result["total_runs"] == 8
    assert 0 < power.result["power"] < 1
    assert "δ（高－低）=-2" in power.assumptions.get()
    assert "非方向性的一自由度 F 检验" in power.assumptions.get()
    power.mode.set("target")
    power.target_power.set("0.8")
    _button(power, "计算").invoke()
    assert power.result["power"] >= 0.8
    assert power.result["total_runs"] == 4 * power.result["replicates"]
    _button(power, "取消").invoke()
    assert not power.main.winfo_exists()
    error.assert_not_called()


def test_h_dexpl_copy_and_reanalysis_preserve_v5_run_lineage(
        csv_app, tmp_path, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr("worksheets.messagebox.askyesno", lambda *a, **k: True)
    monkeypatch.setattr("worksheets.messagebox.askyesnocancel", lambda *a, **k: False)
    monkeypatch.setattr("doe_binary_dialog.messagebox.showerror", error)
    table = _add_h_design(app)
    before = table.model.df.copy(deep=True)
    metadata = table.doe_metadata
    expected_runs = restore_design_result(before, metadata).runs

    path = tmp_path / "doe-h.dexpl"
    assert app._save_project(path)
    assert app.load_file(path)
    restored = app.sheets["DOE H"]
    assert_frame_equal(restored.model.df, before)
    assert restored.doe_metadata == metadata
    runs = restore_design_result(restored.model.df, restored.doe_metadata).runs
    assert [run.run_id for run in runs] == [run.run_id for run in expected_runs]
    assert [run.run_order for run in runs] == [run.run_order for run in expected_runs]
    assert [run.responses for run in runs] == [run.responses for run in expected_runs]

    app.nb.select(app.sheetframes["DOE H"])
    copied = app.copySheet()
    assert copied.doe_metadata == restored.doe_metadata
    assert_frame_equal(copied.model.df, restored.model.df)
    copied_runs = restore_design_result(copied.model.df, copied.doe_metadata).runs
    assert [run.run_id for run in copied_runs] == [run.run_id for run in runs]

    assert app.getCurrentTable() is copied
    dialog = AnalyzeBinaryDOE(app, "factorial")
    assert dialog.optimizer_button is None
    dialog.events.set("响应_Events")
    dialog.trials.set("响应_Trials")
    _button(dialog, "分析").invoke()
    assert [row["run_id"] for row in dialog.result["rows"]] == [
        run.run_id for run in copied_runs]
    _button(dialog, "取消").invoke()
    error.assert_not_called()


def test_h_binary_results_clear_after_source_response_changes(csv_app, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr("doe_binary_dialog.messagebox.showerror", error)
    table = _add_h_design(app)
    dialog = AnalyzeBinaryDOE(app, "factorial")
    dialog.events.set("响应_Events")
    dialog.trials.set("响应_Trials")
    _button(dialog, "分析").invoke()
    assert dialog.result is not None

    response = table.model.df.columns.get_loc("响应_Events")
    table.model.df.iloc[0, response] += 1
    dialog._check_source()
    assert dialog.result is None
    assert not dialog.tabs.tabs()
    assert "旧结果已清除" in dialog.status.get()
    _button(dialog, "取消").invoke()
    error.assert_not_called()


def test_h_binary_dsd_terms_and_rsm_probability_plot(csv_app, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr("doe_binary_dialog.messagebox.showerror", error)
    dsd_spec = replace(make_dsd_spec("dsd3", 3),
                       response_names=("Events", "Trials"))
    frame, metadata = create_dsd(dsd_spec)
    for index, row in frame.iterrows():
        coded = [(-1 if row[f"设定_F{i}"] == 0.1 else
                  1 if row[f"设定_F{i}"] == 0.3 else 0) for i in range(1, 4)]
        frame.at[index, "响应_Events"] = 10 + 2 * coded[0] - coded[1]
        frame.at[index, "响应_Trials"] = 20
    dsd_table = app.addSheet("DSD H", frame, {"doe": metadata})
    app.nb.select(app.sheetframes["DSD H"])

    dsd = AnalyzeBinaryDOE(app, "screening")
    dsd.events.set("响应_Events")
    dsd.trials.set("响应_Trials")
    dsd.screening_model.set("主效应与平方")
    _button(dsd, "分析").invoke()
    assert dsd.optimizer_button is None
    assert dsd.result["model_df"] == 6
    assert len(dsd.result["coefficients"]) == 7
    _button(dsd, "取消").invoke()

    rsm_factors = tuple(FactorSpec(name, name, -1, 1) for name in "ABC")
    rsm_spec = DesignSpec("h-bbd-gui", rsm_factors, ("Events", "Trials"),
                          seed=19, design_type="box_behnken")
    frame, metadata = create_bbd(rsm_spec)
    for index, row in frame.iterrows():
        a, b, c = (int(row[f"设定_{name}"]) for name in "ABC")
        frame.at[index, "响应_Events"] = 10 + 2 * a - b + c + a * b
        frame.at[index, "响应_Trials"] = 20
    rsm = app.addSheet("RSM H", frame, {"doe": metadata})
    app.nb.select(app.sheetframes["RSM H"])

    dialog = AnalyzeBinaryDOE(app, "rsm")
    dialog.events.set("响应_Events")
    dialog.trials.set("响应_Trials")
    _button(dialog, "分析").invoke()
    assert dialog.result["model_df"] == 9
    dialog.plot()
    assert dialog.figure_canvas is not None
    assert any(dialog.tabs.tab(tab, "text") == "概率图"
               for tab in dialog.tabs.tabs())
    app.addSheet("Other", pd.DataFrame({"x": [1]}))
    dialog._check_source()
    assert dialog.result is None
    assert not dialog.tabs.tabs()
    _button(dialog, "取消").invoke()
    assert dsd_table.doe_metadata is not None
    assert rsm.doe_metadata is not None
    error.assert_not_called()


def test_h_binary_probability_window_uses_fit_and_clears_stale_result(
        csv_app, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr("doe_binary_dialog.messagebox.showerror", error)
    factors = tuple(FactorSpec(name, name, -1, 1) for name in "ABC")
    spec = DesignSpec("binary-probability-gui", factors, ("Events", "Trials"),
                      seed=47, design_type="box_behnken")
    frame, metadata = create_bbd(spec)
    frame = _set_binary_counts(
        frame, lambda row: 10 + int(row["设定_A"] > 0)
        + int(row["设定_B"] > 0) + int(row["设定_C"] > 0), trials=20)
    table = app.addSheet("Binary RSM", frame, {"doe": metadata})
    app.nb.select(app.sheetframes["Binary RSM"])

    dialog = AnalyzeBinaryDOE(app, "rsm")
    dialog.events.set("响应_Events")
    dialog.trials.set("响应_Trials")
    _button(dialog, "分析").invoke()
    assert dialog.result is not None
    assert str(dialog.probability_button["state"]) == "normal"
    responses = table.model.df[["响应_Events", "响应_Trials"]].copy(deep=True)

    _button(dialog, "预测概率").invoke()
    prediction = dialog.probability_dialog
    prediction.confidence.set("90%")
    prediction.side.set("单侧下限")
    prediction.predict()
    assert prediction.result is not None
    assert prediction.result["confidence"] == 0.9
    assert prediction.result["side"] == "lower"
    assert prediction.result["ci_high"] is None
    labels = [row[0] for row in prediction.result_block.table.display]
    assert "Wald 概率下限" in labels
    assert not any("PI" in label or "预测区间" in label for label in labels)
    assert "SE on Logit scale" in labels
    assert_frame_equal(
        table.model.df[["响应_Events", "响应_Trials"]], responses)

    prediction.entries["A"].delete(0, "end")
    prediction.entries["A"].insert(0, "0.25")
    app.update_idletasks()
    assert prediction.result is None and prediction.result_block is None
    prediction.predict()
    assert prediction.result is not None

    table.model.df.iloc[0, table.model.df.columns.get_loc("响应_Events")] += 1
    dialog._check_source()
    assert dialog.result is None
    assert prediction.result is None
    assert not prediction.main.winfo_exists()
    assert str(dialog.probability_button["state"]) == "disabled"
    assert str(dialog.optimizer_button["state"]) == "disabled"
    dialog.close()
    error.assert_not_called()


def test_h_binary_probability_window_close_and_response_change(csv_app, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr("doe_binary_dialog.messagebox.showerror", error)
    factors = tuple(FactorSpec(name, name, -1, 1) for name in "ABC")
    spec = DesignSpec("binary-probability-close", factors, ("Events", "Trials"),
                      seed=53, design_type="box_behnken")
    frame, metadata = create_bbd(spec)
    frame = _set_binary_counts(
        frame, lambda row: 10 + int(row["设定_A"] > 0)
        + int(row["设定_B"] > 0) + int(row["设定_C"] > 0), trials=20)
    table = app.addSheet("Binary RSM Close", frame, {"doe": metadata})
    app.nb.select(app.sheetframes["Binary RSM Close"])
    dialog = AnalyzeBinaryDOE(app, "rsm")
    dialog.events.set("响应_Events")
    dialog.trials.set("响应_Trials")
    _button(dialog, "分析").invoke()
    _button(dialog, "预测概率").invoke()
    prediction = dialog.probability_dialog
    prediction.predict()
    assert prediction.result is not None
    responses = table.model.df[["响应_Events", "响应_Trials"]].copy(deep=True)

    prediction.close()
    assert dialog.probability_dialog is None
    assert_frame_equal(table.model.df[["响应_Events", "响应_Trials"]], responses)

    _button(dialog, "预测概率").invoke()
    prediction = dialog.probability_dialog
    prediction.predict()
    assert prediction.result is not None
    dialog.events.current(1)
    dialog.events.event_generate("<<ComboboxSelected>>")
    app.update()
    assert dialog.result is None
    assert not prediction.main.winfo_exists()
    dialog.close()
    error.assert_not_called()


@pytest.mark.parametrize("change", ("data", "metadata", "sheet"))
def test_h_binary_probability_window_invalidates_on_source_change(
        csv_app, monkeypatch, change):
    app, error = csv_app
    monkeypatch.setattr("doe_binary_dialog.messagebox.showerror", error)
    factors = tuple(FactorSpec(name, name, -1, 1) for name in "ABC")
    spec = DesignSpec("binary-probability-stale", factors, ("Events", "Trials"),
                      seed=59, design_type="box_behnken")
    frame, metadata = create_bbd(spec)
    frame = _set_binary_counts(
        frame, lambda row: 10 + int(row["设定_A"] > 0)
        + int(row["设定_B"] > 0) + int(row["设定_C"] > 0), trials=20)
    table = app.addSheet("Binary RSM Stale", frame, {"doe": metadata})
    app.nb.select(app.sheetframes["Binary RSM Stale"])
    dialog = AnalyzeBinaryDOE(app, "rsm")
    dialog.events.set("响应_Events")
    dialog.trials.set("响应_Trials")
    _button(dialog, "分析").invoke()
    _button(dialog, "预测概率").invoke()
    prediction = dialog.probability_dialog
    prediction.predict()
    assert prediction.result is not None

    response_index = table.model.df.columns.get_loc("响应_Events")
    original_event = table.model.df.iloc[0, response_index]
    if change == "data":
        table.model.df.iloc[0, response_index] += 1
    elif change == "metadata":
        table.doe_metadata["stale_probe"] = True
    else:
        app.addSheet("Other", pd.DataFrame({"x": [1]}))
        app.nb.select(app.sheetframes["Other"])
    dialog._check_source()
    assert dialog.result is None
    assert prediction.result is None
    assert not prediction.main.winfo_exists()
    assert str(dialog.probability_button["state"]) == "disabled"
    assert str(dialog.optimizer_button["state"]) == "disabled"

    if change == "data":
        table.model.df.iloc[0, response_index] = original_event
    elif change == "metadata":
        del table.doe_metadata["stale_probe"]
    else:
        app.nb.select(app.sheetframes["Binary RSM Stale"])
    _button(dialog, "分析").invoke()
    assert dialog.result is not None
    assert str(dialog.probability_button["state"]) == "normal"
    assert str(dialog.optimizer_button["state"]) == "normal"
    dialog.close()
    error.assert_not_called()


@pytest.mark.parametrize("response_column", ("events", "trials"))
def test_h_binary_rsm_buttons_follow_response_selection(
        csv_app, monkeypatch, response_column):
    app, error = csv_app
    monkeypatch.setattr("doe_binary_dialog.messagebox.showerror", error)
    dialog, _table = _binary_optimizer_dialog(app, seed=61,
                                               name=f"Binary Button {response_column}")
    widget = getattr(dialog, response_column)
    original = widget.get()
    alternative = next(value for value in widget["values"] if value != original)

    widget.set(alternative)
    widget.event_generate("<<ComboboxSelected>>")
    assert dialog.result is None
    assert str(dialog.probability_button["state"]) == "disabled"
    assert str(dialog.optimizer_button["state"]) == "disabled"

    widget.set(original)
    widget.event_generate("<<ComboboxSelected>>")
    _button(dialog, "分析").invoke()
    assert dialog.result is not None
    assert str(dialog.probability_button["state"]) == "normal"
    assert str(dialog.optimizer_button["state"]) == "normal"
    dialog.close()
    error.assert_not_called()


def test_h_binary_probability_window_preserves_numeric_category_level(
        csv_app, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr("doe_binary_dialog.messagebox.showerror", error)
    frame = custom_rsm_frame().drop(columns="X3")
    frame["C"] = [10 if index % 2 else 20 for index in range(len(frame))]
    frame["Events"] = [6 + int(value == 20) for value in frame["C"]]
    frame["Trials"] = 10
    factors = custom_factors()[:2] + (
        FactorSpec("C", "C", None, None, factor_type="categorical",
                   levels=(10, 20), level_type="numeric"),
    )
    column_map = custom_columns()
    column_map["factors"] = {name: name for name in ("X1", "X2", "C")}
    column_map["responses"] = {"Events": "Events", "Trials": "Trials"}
    frame, metadata, _ = define_custom(
        frame, design_type="custom_rsm", factors=factors,
        responses=("Events", "Trials"), column_map=column_map,
        model_terms=["X1", "X2", "C"], design_id="binary-category-gui",
    )
    table = app.addSheet("Binary Category RSM", frame, {"doe": metadata})
    app.nb.select(app.sheetframes["Binary Category RSM"])
    dialog = AnalyzeBinaryDOE(app, "rsm")
    dialog.events.set("Events")
    dialog.trials.set("Trials")
    _button(dialog, "分析").invoke()
    assert dialog.result is not None
    _button(dialog, "预测概率").invoke()
    prediction = dialog.probability_dialog
    prediction.entries["C"].current(1)
    prediction.predict()
    assert prediction.result["settings"]["C"] == 20
    assert prediction.result["coded"]["C"] == 20
    assert table.doe_metadata == metadata
    prediction.close()
    dialog.close()
    error.assert_not_called()


def test_h_fractional_binary_gui_keeps_alias_groups(csv_app, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr("doe_binary_dialog.messagebox.showerror", error)
    spec = DesignSpec(
        "h-fractional-gui", tuple(FactorSpec(name, name, -1, 1) for name in "ABC"),
        ("Events", "Trials"), seed=31, generators=("C=AB",),
        design_type="two_level_fractional",
    )
    frame, metadata = create_fractional(spec)
    frame = _set_binary_counts(
        frame, lambda row: 8 if all(row[f"设定_{name}"] == 1 for name in "ABC") else 3,
        trials=10)
    app.addSheet("Fractional H", frame, {"doe": metadata})
    app.nb.select(app.sheetframes["Fractional H"])

    dialog = AnalyzeBinaryDOE(app, "factorial")
    dialog.events.set("响应_Events")
    dialog.trials.set("响应_Trials")
    assert str(dialog.model_order["state"]) == "disabled"
    _button(dialog, "分析").invoke()
    assert all(" = " in row["term"] for row in dialog.result["coefficients"][1:])
    _button(dialog, "取消").invoke()

    power = AnalyzeDOEPower(app)
    _button(power, "计算").invoke()
    assert power.result["total_runs"] == 8
    _button(power, "取消").invoke()
    error.assert_not_called()


def test_h_pb_binary_and_power_gui(csv_app, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr("doe_binary_dialog.messagebox.showerror", error)
    spec = replace(make_pb_spec(12, factors=3),
                   response_names=("Events", "Trials"))
    frame, metadata = create_pb(spec, 12)
    frame = _set_binary_counts(frame,
                               lambda row: 8 if row["设定_F1"] == 1 else 3,
                               trials=10)
    app.addSheet("PB H", frame, {"doe": metadata})
    app.nb.select(app.sheetframes["PB H"])

    binary = AnalyzeBinaryDOE(app, "factorial")
    binary.events.set("响应_Events")
    binary.trials.set("响应_Trials")
    assert str(binary.model_order["state"]) == "disabled"
    _button(binary, "分析").invoke()
    assert binary.result["residual_df"] == 8
    _button(binary, "取消").invoke()

    power = AnalyzeDOEPower(app)
    _button(power, "计算").invoke()
    assert power.result["total_runs"] == 24
    _button(power, "取消").invoke()
    error.assert_not_called()


def test_h_numeric_label_gff_binary_and_power_gui(csv_app, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr("doe_binary_dialog.messagebox.showerror", error)
    monkeypatch.setattr("doe_power_dialog.messagebox.showerror", error)
    factors = (
        FactorSpec("A", "A", None, None, factor_type="categorical",
                   levels=(10, 20), level_type="numeric"),
        FactorSpec("B", "B", None, None, factor_type="categorical",
                   levels=(-1, 1), level_type="numeric"),
    )
    spec = DesignSpec("h-gff-gui", factors, ("Events", "Trials"), seed=13,
                      design_type="general_full_factorial")
    frame, metadata = create_general_factorial(spec)
    frame = _set_binary_counts(
        frame, lambda row: 6 + (row["设定_A"] // 20) + (row["设定_B"] == 1),
        trials=20)
    app.addSheet("GFF H", frame, {"doe": metadata})
    app.nb.select(app.sheetframes["GFF H"])

    binary = AnalyzeBinaryDOE(app, "factorial")
    binary.events.set("响应_Events")
    binary.trials.set("响应_Trials")
    binary.model_order.set("1")
    _button(binary, "分析").invoke()
    assert binary.result["model_df"] == 2
    _button(binary, "取消").invoke()

    power = AnalyzeDOEPower(app)
    _button(power, "计算").invoke()
    assert power.result["total_runs"] == 8
    _button(power, "取消").invoke()
    error.assert_not_called()


def test_h_binary_optimizer_previews_and_runs_without_writing_responses(
        csv_app, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr("doe_binary_dialog.messagebox.showerror", error)
    dialog, table = _binary_optimizer_dialog(app)
    responses = table.model.df[["响应_Events", "响应_Trials"]].copy(deep=True)
    _button(dialog, "响应优化").invoke()
    optimizer = dialog.optimizer_dialog
    for factor in "ABC":
        low, high = optimizer.bounds_entries[factor]
        low.set("0")
        high.set("0")
        optimizer.start_entries[factor].set("0")
    optimizer.limits["target"].set("0.5")
    _button(optimizer, "预览").invoke()
    labels = [row[0] for row in optimizer.output_block.table.display]
    assert "类别组合数" in labels
    assert optimizer.result is None

    _button(optimizer, "优化").invoke()
    _wait_binary_optimizer(app, optimizer)
    result = optimizer.result
    assert result["candidate_found"] is True
    assert result["global_optimum_proven"] is True
    assert result["model_snapshot"] == dialog.result["model_snapshot"]
    model = dialog.result["detail"]["term_model"]
    eta = model.row(model.coded(result["settings"])) @ dialog.result["coefficients_array"]
    assert result["probability"] == pytest.approx(1 / (1 + math.exp(-eta)))
    assert_frame_equal(table.model.df[["响应_Events", "响应_Trials"]], responses)

    optimizer.limits["target"].set("0.6")
    assert optimizer.result is None and optimizer.output_block is None
    optimizer.close()
    dialog.close()
    error.assert_not_called()


def test_h_binary_optimizer_reanalyzes_after_dexpl_reopen_and_copy(
        csv_app, tmp_path, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr("worksheets.messagebox.askyesno", lambda *a, **k: True)
    monkeypatch.setattr("worksheets.messagebox.askyesnocancel", lambda *a, **k: False)
    monkeypatch.setattr("doe_binary_dialog.messagebox.showerror", error)
    source = _binary_optimizer_rsm_table(app, 79, "Binary Optimizer Persist")
    before = source.model.df.copy(deep=True)
    metadata = source.doe_metadata
    path = tmp_path / "binary-optimizer.dexpl"
    assert app._save_project(path)
    assert app.load_file(path)
    restored = app.sheets["Binary Optimizer Persist"]
    assert_frame_equal(restored.model.df, before)
    assert restored.doe_metadata == metadata
    assert restore_design_result(restored.model.df, restored.doe_metadata).schema_version == 5

    app.nb.select(app.sheetframes["Binary Optimizer Persist"])
    copied = app.copySheet()
    copy_name = app.getCurrentSheet()
    assert copied.doe_metadata == restored.doe_metadata
    assert_frame_equal(copied.model.df, restored.model.df)

    def analyze_fixed(sheet_name):
        app.nb.select(app.sheetframes[sheet_name])
        dialog = AnalyzeBinaryDOE(app, "rsm")
        dialog.events.set("响应_Events")
        dialog.trials.set("响应_Trials")
        _button(dialog, "分析").invoke()
        _button(dialog, "响应优化").invoke()
        optimizer = dialog.optimizer_dialog
        for factor in "ABC":
            low, high = optimizer.bounds_entries[factor]
            low.set("0")
            high.set("0")
        optimizer.optimize()
        _wait_binary_optimizer(app, optimizer)
        result = dict(optimizer.result)
        assert_frame_equal(dialog.source.model.df, before)
        optimizer.close()
        dialog.close()
        return result

    original_result = analyze_fixed("Binary Optimizer Persist")
    copy_result = analyze_fixed(copy_name)
    assert original_result["settings"] == copy_result["settings"]
    assert original_result["probability"] == pytest.approx(copy_result["probability"])
    assert original_result["model_snapshot"] == copy_result["model_snapshot"]
    error.assert_not_called()


def test_h_binary_optimizer_preserves_numeric_category_levels(csv_app, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr("doe_binary_dialog.messagebox.showerror", error)
    frame = custom_rsm_frame().drop(columns="X3")
    frame["C"] = [10 if index % 2 else 20 for index in range(len(frame))]
    frame["Events"] = [6 + int(value == 20) for value in frame["C"]]
    frame["Trials"] = 10
    factors = custom_factors()[:2] + (
        FactorSpec("C", "C", None, None, factor_type="categorical",
                   levels=(10, 20), level_type="numeric"),
    )
    column_map = custom_columns()
    column_map["factors"] = {name: name for name in ("X1", "X2", "C")}
    column_map["responses"] = {"Events": "Events", "Trials": "Trials"}
    frame, metadata, _ = define_custom(
        frame, design_type="custom_rsm", factors=factors,
        responses=("Events", "Trials"), column_map=column_map,
        model_terms=["X1", "X2", "C"], design_id="binary-optimizer-numeric-category",
    )
    table = app.addSheet("Binary Optimizer Numeric Category", frame, {"doe": metadata})
    app.nb.select(app.sheetframes["Binary Optimizer Numeric Category"])
    dialog = AnalyzeBinaryDOE(app, "rsm")
    dialog.events.set("Events")
    dialog.trials.set("Trials")
    _button(dialog, "分析").invoke()
    _button(dialog, "响应优化").invoke()
    optimizer = dialog.optimizer_dialog
    for factor in ("X1", "X2"):
        low, high = optimizer.bounds_entries[factor]
        low.set("0")
        high.set("0")
    levels = optimizer.category_lists["C"]
    levels.selection_clear(0, "end")
    levels.selection_set(1)
    _button(optimizer, "优化").invoke()
    _wait_binary_optimizer(app, optimizer)
    result = optimizer.result
    assert result["settings"]["C"] == 20
    assert type(result["settings"]["C"]) is int
    assert result["global_optimum_proven"] is True
    optimizer.close()
    dialog.close()
    assert table.doe_metadata == metadata
    error.assert_not_called()


def test_h_binary_optimizer_cancel_and_close_stop_background_search(
        csv_app, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr("doe_binary_dialog.messagebox.showerror", error)
    started, finished = Event(), Event()

    def wait_for_cancel(_analysis, **options):
        started.set()
        try:
            options["cancel"].wait(5)
            raise InterruptedError("已取消")
        finally:
            finished.set()

    monkeypatch.setattr("doe_binary_dialog.optimize_binary_rsm", wait_for_cancel)
    dialog, table = _binary_optimizer_dialog(app, seed=71, name="Binary Optimizer Cancel")
    responses = table.model.df[["响应_Events", "响应_Trials"]].copy(deep=True)
    _button(dialog, "响应优化").invoke()
    optimizer = dialog.optimizer_dialog
    optimizer.optimize()
    assert started.wait(2)
    _button(optimizer, "取消计算").invoke()
    _wait_binary_optimizer(app, optimizer)
    assert optimizer.result is None
    assert "已取消" in optimizer.status.get()
    assert_frame_equal(table.model.df[["响应_Events", "响应_Trials"]], responses)

    started.clear()
    finished.clear()
    optimizer.optimize()
    assert started.wait(2)
    optimizer.close()
    assert optimizer.cancel_event.is_set()
    assert finished.wait(2)
    dialog.close()
    error.assert_not_called()


@pytest.mark.parametrize("change", ("metadata", "sheet", "data", "delete", "response"))
def test_h_binary_optimizer_closes_when_source_changes(csv_app, monkeypatch, change):
    app, error = csv_app
    monkeypatch.setattr("doe_binary_dialog.messagebox.showerror", error)
    started, finished = Event(), Event()

    def wait_for_cancel(_analysis, **options):
        started.set()
        try:
            options["cancel"].wait(5)
            raise InterruptedError("已取消")
        finally:
            finished.set()

    monkeypatch.setattr("doe_binary_dialog.optimize_binary_rsm", wait_for_cancel)
    dialog, table = _binary_optimizer_dialog(
        app, seed=73, name=f"Binary Optimizer Stale {change}")
    _button(dialog, "响应优化").invoke()
    optimizer = dialog.optimizer_dialog
    optimizer.optimize()
    assert started.wait(2)
    if change == "metadata":
        table.doe_metadata["stale_probe"] = True
    elif change == "sheet":
        app.addSheet("Other Binary Optimizer", pd.DataFrame({"x": [1]}))
        app.nb.select(app.sheetframes["Other Binary Optimizer"])
    elif change == "data":
        table.model.df.iloc[0, table.model.df.columns.get_loc("响应_Events")] += 1
    elif change == "delete":
        monkeypatch.setattr("worksheets.messagebox.askyesno", lambda *a, **k: True)
        assert app.deleteSheet()
    else:
        dialog.events.current(1)
        dialog.events.event_generate("<<ComboboxSelected>>")
    dialog._check_source()
    assert dialog.result is None
    assert not optimizer.main.winfo_exists()
    assert optimizer.cancel_event.is_set()
    assert finished.wait(2)
    assert optimizer.result is None
    assert str(dialog.probability_button["state"]) == "disabled"
    assert str(dialog.optimizer_button["state"]) == "disabled"
    dialog.close()
    error.assert_not_called()


def test_h_binary_optimizer_parent_close_cancels_background_search(csv_app, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr("doe_binary_dialog.messagebox.showerror", error)
    started, finished = Event(), Event()

    def wait_for_cancel(_analysis, **options):
        started.set()
        try:
            options["cancel"].wait(5)
            raise InterruptedError("已取消")
        finally:
            finished.set()

    monkeypatch.setattr("doe_binary_dialog.optimize_binary_rsm", wait_for_cancel)
    dialog, table = _binary_optimizer_dialog(app, seed=83, name="Binary Optimizer Parent Close")
    before = table.model.df[["响应_Events", "响应_Trials"]].copy(deep=True)
    _button(dialog, "响应优化").invoke()
    optimizer = dialog.optimizer_dialog
    optimizer.optimize()
    assert started.wait(2)
    dialog.close()
    assert optimizer.cancel_event.is_set()
    assert not optimizer.main.winfo_exists()
    assert finished.wait(2)
    assert_frame_equal(table.model.df[["响应_Events", "响应_Trials"]], before)
    error.assert_not_called()
