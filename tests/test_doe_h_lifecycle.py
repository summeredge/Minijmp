from dataclasses import replace

import pandas as pd
from pandas.testing import assert_frame_equal

from doe_core import DesignSpec, FactorSpec, restore_design_result
from doe_bbd import create_bbd
from doe_dsd import create_dsd
from doe_factorial import create_factorial
from doe_fractional import create_fractional
from doe_general_factorial import create_general_factorial
from doe_pb import create_pb
from doe_binary_dialog import AnalyzeBinaryDOE
from doe_variability_dialog import AnalyzeVariabilityDOE
from doe_power_dialog import AnalyzeDOEPower
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
