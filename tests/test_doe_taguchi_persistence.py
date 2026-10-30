"""Taguchi 工程持久化、原始观测保存与无效设计拒绝。"""
from copy import deepcopy

import pytest

from doe_core import (DesignSpec, FactorSpec, _fingerprint, restore_design_result,
                      validate_worksheet_metadata)
from doe_taguchi import create_taguchi
from doe_taguchi_arrays import ARRAYS
from test_csv_import import csv_app


def factor(factor_id, levels):
    return FactorSpec(factor_id, factor_id, None, None, factor_type="categorical",
                      levels=tuple(levels), level_type="text")


def spec_for(array_id, count):
    array = ARRAYS[array_id]
    factors = [factor(chr(65 + index),
                      tuple(f"l{index + 1}" for index in range(level)))
               for index, level in enumerate(array.levels[:count])]
    return DesignSpec("TG", tuple(factors), ("Y",), seed=13, design_type="taguchi",
                      taguchi={"kind": "static", "array_id": array_id,
                               "matrix_sha256": array.sha256,
                               "columns": {item.factor_id: index + 1
                                           for index, item in enumerate(factors)},
                               "noise_array_id": None, "noise_matrix_sha256": None,
                               "noise_columns": {}, "signal_factor": None})


@pytest.mark.parametrize("array_id,count,expected", [
    ("L8(2^7)", 4, 8), ("L9(3^4)", 4, 9), ("L18(2^1 3^7)", 7, 18),
    ("L16(4^5)", 5, 16), ("L25(5^6)", 6, 25),
    ("L8(4^1 2^4)", 5, 8), ("L16(4^1 2^12)", 13, 16),
])
def test_project_roundtrip_keeps_original_observations(array_id, count, expected):
    spec = spec_for(array_id, count)
    frame, metadata = create_taguchi(spec)
    assert len(frame) == expected
    frame["响应_Y"] = [float(index) for index in range(len(frame))]
    restored = restore_design_result(frame, metadata)
    assert [run.responses["Y"] for run in restored.runs] == [
        float(index) for index in range(expected)]
    assert restored.spec.taguchi["array_id"] == array_id


def test_worksheet_copy_keeps_taguchi_metadata_identity():
    spec = spec_for("L9(3^4)", 4)
    frame, metadata = create_taguchi(spec, replicates=2)
    copy = frame.copy(deep=True)
    assert validate_worksheet_metadata(copy, metadata)["design"]["taguchi"][
        "array_id"] == "L9(3^4)"
    copy.loc[0, "设定_A"] = "l3" if copy.loc[0, "设定_A"] != "l3" else "l1"
    with pytest.raises(ValueError):
        restore_design_result(copy, metadata)


def test_missing_or_corrupt_taguchi_identity_is_rejected():
    spec = spec_for("L8(2^7)", 4)
    frame, metadata = create_taguchi(spec)
    broken = deepcopy(metadata)
    broken["design"]["taguchi"]["matrix_sha256"] = "f" * 64
    with pytest.raises(ValueError):
        restore_design_result(frame, broken)
    broken = deepcopy(metadata)
    broken["design"]["taguchi"]["array_id"] = "L12(2^11)"
    with pytest.raises(ValueError):
        restore_design_result(frame, broken)
    broken = deepcopy(metadata)
    broken["design"]["taguchi"]["columns"] = {"A": 1}
    with pytest.raises(ValueError):
        restore_design_result(frame, broken)


def test_legacy_v5_shapes_migrate_and_taguchi_ids_are_fingerprinted():
    spec = spec_for("L4(2^3)", 3)
    frame, metadata = create_taguchi(spec)
    result = restore_design_result(frame, metadata)
    legacy = deepcopy(metadata)
    for key in ("model_terms", "optimal_lineage", "augmentation_lineage"):
        legacy["design"].pop(key)
    legacy["worksheet"]["input_fingerprint"] = _fingerprint(
        legacy["design"], legacy["column_map"], result,
        include_taguchi_ids=False)
    migrated = validate_worksheet_metadata(frame, legacy)
    assert migrated["design"]["taguchi"]["array_id"] == "L4(2^3)"
    assert "model_terms" in migrated["design"]

    corrupted = frame.copy(deep=True)
    corrupted.loc[0, "控制运行"] = "C99999"
    with pytest.raises(ValueError, match="ID 与标准序不一致"):
        restore_design_result(corrupted, migrated)


def test_e_only_schema_v5_shape_remains_readable():
    spec = DesignSpec("legacy-e", (factor("A", ("低", "高")),), ("Y",),
                      design_type="general_full_factorial")
    payload = spec.to_dict()
    payload.pop("taguchi")
    restored = DesignSpec.from_dict(payload)
    assert restored.design_type == "general_full_factorial"
    assert restored.taguchi is None


def test_taguchi_dexpl_save_reopen_copy(csv_app, tmp_path, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr("worksheets.messagebox.askyesnocancel", lambda *a, **k: False)
    monkeypatch.setattr("worksheets.messagebox.askyesno", lambda *a, **k: True)
    spec = spec_for("L9(3^4)", 4)
    frame, metadata = create_taguchi(spec, replicates=2)
    frame["响应_Y"] = [float(index) for index in range(len(frame))]
    app.addSheet("Taguchi", frame, {"doe": metadata})
    table = app.getCurrentTable()
    path = tmp_path / "taguchi.dexpl"
    assert app._save_project(path)
    assert app.load_file(path)
    name = next(sheet for sheet, item in app.sheets.items()
                if item.doe_metadata
                and item.doe_metadata["design"]["design_type"] == "taguchi")
    app.nb.select(app.sheetframes[name])
    reopened = app.getCurrentTable()
    design = restore_design_result(reopened.model.df, reopened.doe_metadata)
    assert len(design.runs) == 18
    assert design.spec.taguchi["array_id"] == "L9(3^4)"
    copied = app.copySheet()
    assert copied.doe_metadata == reopened.doe_metadata
    assert copied.model.df.equals(reopened.model.df)



def dynamic_spec(replicates=1):
    factors = (factor("A", ("低", "高")), factor("B", ("低", "高")),
               FactorSpec("S", "S", None, None, factor_type="categorical",
                          levels=(1.0, 2.0, 3.0), level_type="numeric"))
    return DesignSpec("TG", factors, ("Y",), seed=3, design_type="taguchi",
                      taguchi={"kind": "dynamic", "array_id": "L4(2^3)",
                               "matrix_sha256": ARRAYS["L4(2^3)"].sha256,
                               "columns": {"A": 1, "B": 2},
                               "noise_array_id": None, "noise_matrix_sha256": None,
                               "noise_columns": {}, "signal_factor": "S"})


def noise_spec():
    return DesignSpec("TG", (factor("A", ("低", "高")), factor("B", ("低", "高")),
                             factor("N", ("n1", "n2"))), ("Y",), seed=9,
                      design_type="taguchi",
                      taguchi={"kind": "static", "array_id": "L4(2^3)",
                               "matrix_sha256": ARRAYS["L4(2^3)"].sha256,
                               "columns": {"A": 1, "B": 3},
                               "noise_array_id": "L4(2^3)",
                               "noise_matrix_sha256": ARRAYS["L4(2^3)"].sha256,
                               "noise_columns": {"N": 2}, "signal_factor": None})


@pytest.mark.parametrize("spec_factory,expected_kind,signal_levels", [
    (lambda: spec_for("L8(2^7)", 4), "static", None),
    (lambda: spec_for("L9(3^4)", 4), "static", None),
    (lambda: spec_for("L18(2^1 3^7)", 7), "static", None),
    (lambda: spec_for("L16(4^5)", 5), "static", None),
    (lambda: spec_for("L25(5^6)", 6), "static", None),
    (lambda: spec_for("L8(4^1 2^4)", 5), "static", None),
    (lambda: spec_for("L16(4^1 2^12)", 13), "static", None),
    (dynamic_spec, "dynamic", (1.0, 2.0, 3.0)),
])
def test_dexpl_roundtrip_covers_every_array_family(
        spec_factory, expected_kind, signal_levels, csv_app, tmp_path, monkeypatch):
    app, _ = csv_app
    monkeypatch.setattr("worksheets.messagebox.askyesnocancel", lambda *a, **k: False)
    monkeypatch.setattr("worksheets.messagebox.askyesno", lambda *a, **k: True)
    spec = spec_factory()
    frame, metadata = create_taguchi(spec)
    frame["响应_Y"] = [float(index) + 1 for index in range(len(frame))]
    app.addSheet("Taguchi", frame, {"doe": metadata})
    path = tmp_path / f"{metadata['design']['taguchi']['array_id']}.dexpl"
    assert app._save_project(path)
    assert app.load_file(path)
    name = next(sheet for sheet, item in app.sheets.items()
                if item.doe_metadata
                and item.doe_metadata["design"]["design_type"] == "taguchi")
    app.nb.select(app.sheetframes[name])
    reopened = app.getCurrentTable()
    design = restore_design_result(reopened.model.df, reopened.doe_metadata)
    assert design.spec.taguchi["kind"] == expected_kind
    assert design.spec.taguchi["array_id"] == spec.taguchi["array_id"]
    assert design.spec.taguchi["matrix_sha256"] == spec.taguchi["matrix_sha256"]
    assert [run.responses["Y"] for run in design.runs] == [
        float(index) + 1 for index in range(len(frame))]
    if signal_levels is not None:
        assert {run.settings["S"] for run in design.runs} == set(signal_levels)
    copied = app.copySheet()
    assert copied.doe_metadata == reopened.doe_metadata
    again = restore_design_result(copied.model.df, copied.doe_metadata)
    assert len(again.runs) == len(design.runs)


def test_dynamic_dexpl_recomputes_slope_and_sn_after_reopen(csv_app, tmp_path,
                                                            monkeypatch):
    app, _ = csv_app
    monkeypatch.setattr("worksheets.messagebox.askyesnocancel", lambda *a, **k: False)
    monkeypatch.setattr("worksheets.messagebox.askyesno", lambda *a, **k: True)
    spec = dynamic_spec()
    frame, metadata = create_taguchi(spec)
    design = restore_design_result(frame, metadata)
    values = {run.run_id: 1.0 + (2.0 if run.settings["A"] == "低" else 5.0)
              * run.settings["S"] + (0.3 if int(run.settings["S"]) % 2 else -0.2)
              for run in design.runs}
    frame["响应_Y"] = [values[run_id] for run_id in frame["运行ID"]]
    app.addSheet("Taguchi", frame, {"doe": metadata})
    path = tmp_path / "dynamic.dexpl"
    assert app._save_project(path)
    assert app.load_file(path)
    name = next(sheet for sheet, item in app.sheets.items()
                if item.doe_metadata
                and item.doe_metadata["design"]["design_type"] == "taguchi")
    app.nb.select(app.sheetframes[name])
    reopened = app.getCurrentTable()
    from doe_taguchi_analysis import analyze_dynamic
    result = analyze_dynamic(reopened.model.df, reopened.doe_metadata, "Y")
    slopes = {row["settings"]["A"]: row["slope"] for row in result["combinations"]}
    assert slopes["低"] == pytest.approx(2.0, abs=1e-9)
    assert slopes["高"] == pytest.approx(5.0, abs=1e-9)
    assert all(row["df"] == 1 for row in result["combinations"])


def test_noise_factor_dexpl_keeps_inner_outer_mapping(csv_app, tmp_path, monkeypatch):
    app, _ = csv_app
    monkeypatch.setattr("worksheets.messagebox.askyesnocancel", lambda *a, **k: False)
    monkeypatch.setattr("worksheets.messagebox.askyesno", lambda *a, **k: True)
    spec = noise_spec()
    frame, metadata = create_taguchi(spec, replicates=2)
    frame["响应_Y"] = [float(index) for index in range(len(frame))]
    app.addSheet("Taguchi", frame, {"doe": metadata})
    path = tmp_path / "noise.dexpl"
    assert app._save_project(path)
    assert app.load_file(path)
    name = next(sheet for sheet, item in app.sheets.items()
                if item.doe_metadata
                and item.doe_metadata["design"]["design_type"] == "taguchi")
    app.nb.select(app.sheetframes[name])
    reopened = app.getCurrentTable()
    design = restore_design_result(reopened.model.df, reopened.doe_metadata)
    assert design.spec.taguchi["noise_array_id"] == "L4(2^3)"
    assert dict(design.spec.taguchi["noise_columns"]) == {"N": 2}
    assert len({run.control_run_id for run in design.runs}) == 4
    assert len(design.runs) == 16


def test_response_change_invalidates_cached_sn_but_keeps_original_runs():
    from doe_taguchi_sn import analyze_static
    spec = spec_for("L9(3^4)", 3)
    spec = DesignSpec(spec.design_id, spec.factors, spec.response_names,
                      seed=spec.seed, design_type="taguchi",
                      taguchi={**spec.taguchi, "columns": {"A": 1, "B": 2, "C": 3}})
    frame, metadata = create_taguchi(spec, replicates=2)
    design = restore_design_result(frame, metadata)
    frame["响应_Y"] = [(run.replicate * 10.0) for run in design.runs]
    first = analyze_static(frame, metadata, "Y", "smaller")
    before = [row["sn"] for row in first["combinations"]]
    frame["响应_Y"] = [(run.replicate * 20.0) for run in design.runs]
    second = analyze_static(frame, metadata, "Y", "smaller")
    assert [row["sn"] for row in second["combinations"]] != before
    assert len(restore_design_result(frame, metadata).runs) ==         len(design.runs)


def test_saved_analysis_options_survive_validation_and_copy():
    spec = spec_for("L9(3^4)", 3)
    frame, metadata = create_taguchi(spec, replicates=2)
    frame["响应_Y"] = [float(index % 3 + 1) for index in range(len(frame))]
    options = {"kind": "static", "sn_kind": "nominal", "adjusted": True,
               "ln_sd": True}
    saved = validate_worksheet_metadata(frame, {**metadata, "analysis": options})
    assert saved["analysis"] == options
    assert validate_worksheet_metadata(frame, saved)["analysis"] == options
    with pytest.raises(ValueError, match="nominal-is-best"):
        validate_worksheet_metadata(frame, {**metadata, "analysis": {
            **options, "sn_kind": "smaller"}})
    with pytest.raises(ValueError, match="分析选项"):
        validate_worksheet_metadata(frame, {**metadata, "analysis": {
            **options, "kind": "dynamic"}})
