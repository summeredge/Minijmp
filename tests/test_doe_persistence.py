import gzip
import pickle
from dataclasses import replace
from unittest.mock import Mock

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from doe_core import (
    DesignSpec,
    FactorSpec,
    restore_design_result,
    validate_worksheet_metadata,
    worksheet_metadata,
)
from doe_splitplot import append_split_plot_blocks, create_split_plot, validate_split_plot_design
from doe_splitplot_analysis import analyze_split_plot
from test_csv_import import csv_app


@pytest.fixture
def workbook(csv_app, monkeypatch):
    app, error = csv_app
    monkeypatch.setattr("worksheets.messagebox.askyesno", lambda *a, **k: True)
    monkeypatch.setattr("worksheets.messagebox.askyesnocancel", lambda *a, **k: False)
    return app, error


def _source():
    frame = pd.DataFrame(
        {
            "运行ID": ["R-03", "R-01", "R-04", "R-02"],
            "标准序": [3, 1, 4, 2],
            "运行序": [3, 1, 4, 2],
            "点类型": ["factorial"] * 4,
            "重复": [1, 1, 2, 2],
            "批次ID": pd.array([2**60 + i for i in range(4)], dtype="Int64"),
            "1": [10, 10, 20, 20],
            1: [6, 2, 6, 2],
            "A实测": pd.array([10.0, pd.NA, 19.5, 20.0], dtype="Float64"),
            "收率列": pd.array([pd.NA] * 4, dtype="Float64"),
        },
        index=[50, 50, 8, 100],
    )
    spec = DesignSpec(
        design_id="doe-persistence",
        factors=(FactorSpec("A", "温度", 10, 20, "°C"),
                 FactorSpec("B", "压力", 2, 6, "kPa")),
        response_names=("收率",),
        seed=31,
    )
    columns = {
        "run_id": "运行ID",
        "standard_order": "标准序",
        "run_order": "运行序",
        "point_type": "点类型",
        "replicate": "重复",
        "block": "批次ID",
        "factors": {"A": "1", "B": 1},
        "measured_levels": {"A": "A实测"},
        "responses": {"收率": "收率列"},
    }
    return frame, spec, columns


def test_mixed_sheet_dexpl_roundtrip_preserves_doe_and_late_responses(
        workbook, tmp_path):
    app, error = workbook
    frame, spec, columns = _source()
    original = frame.copy(deep=True)
    payload = worksheet_metadata(frame, spec, columns)
    doe_table = app.addSheet("DOE", frame.copy(deep=True), {"doe": payload})
    app.addSheet("普通表", pd.DataFrame({"批次ID": pd.array(
        [2**60 + 7], dtype="Int64"), "说明": ["保留"]}))

    copied_plain = app.copySheet()
    assert "doe" not in app.saveMeta(copied_plain)
    app.nb.select(app.sheetframes["DOE"])
    copied_doe = app.copySheet()
    assert copied_doe.doe_metadata == doe_table.doe_metadata
    assert copied_doe.doe_metadata is not doe_table.doe_metadata
    assert copied_doe.doe_metadata["design"] is not doe_table.doe_metadata["design"]

    target = tmp_path / "doe-mixed.dexpl"
    assert app._save_project(target)
    assert app.load_file(target)
    restored = app.sheets["DOE"]
    restored_doe = restored.model.df
    assert_frame_equal(restored_doe, frame)
    assert restored_doe.index.tolist() == [50, 50, 8, 100]
    assert restored_doe["批次ID"].iloc[0] == 2**60
    assert restored_doe["批次ID"].dtype == pd.Int64Dtype()
    assert app.sheets["普通表"].model.df.iloc[0]["批次ID"] == 2**60 + 7
    assert "doe" not in app.saveMeta(app.sheets["普通表"])
    assert [run.responses["收率"] for run in
            restore_design_result(restored_doe, restored.doe_metadata).runs] == [None] * 4

    response_col = restored_doe.columns.get_loc("收率列")
    restored_doe.iloc[0, response_col] = 12.5
    assert app._save_project(target)
    assert app.load_file(target)
    final_table = app.sheets["DOE"]
    final_result = restore_design_result(final_table.model.df, final_table.doe_metadata)
    assert final_result.runs[0].responses["收率"] == 12.5
    assert_frame_equal(frame, original)
    error.assert_not_called()


def test_design_types_roundtrip_in_mixed_dexpl_without_generating_designs(
        workbook, tmp_path):
    app, error = workbook
    frame, spec, columns = _source()
    design_types = ("two_level_full", "two_level_fractional", "central_composite")
    for design_type in design_types:
        typed_spec = replace(spec, design_type=design_type)
        name = f"DOE {design_type}"
        metadata = worksheet_metadata(frame, typed_spec, columns)
        app.addSheet(name, frame.copy(deep=True), {"doe": metadata})
    app.addSheet("普通表", pd.DataFrame({"x": [1]}))

    target = tmp_path / "design-types.dexpl"
    assert app._save_project(target)
    assert app.load_file(target)
    for design_type in design_types:
        table = app.sheets[f"DOE {design_type}"]
        result = restore_design_result(table.model.df, table.doe_metadata)
        assert result.spec.design_type == design_type
        assert {run.point_type for run in result.runs} == {"factorial"}
    error.assert_not_called()


@pytest.mark.parametrize(
    "problem",
    ["unknown_schema", "invalid_run_mapping", "duplicate_columns", "renamed_column",
     "missing_design_type", "invalid_design_type"],
)
def test_bad_doe_metadata_fails_project_load_without_replacing_live_sheets(
        workbook, tmp_path, problem):
    app, error = workbook
    frame, spec, columns = _source()
    metadata = worksheet_metadata(frame, spec, columns)
    damaged_frame = frame.copy(deep=True)
    if problem == "unknown_schema":
        metadata["schema_version"] = 99
    elif problem == "invalid_run_mapping":
        metadata["worksheet"]["run_rows"][0]["run_id"] = "missing-run"
    elif problem == "missing_design_type":
        metadata["design"].pop("design_type")
    elif problem == "invalid_design_type":
        metadata["design"]["design_type"] = "full_factorial_guess"
    elif problem == "duplicate_columns":
        damaged_frame.columns = [
            "运行ID", "标准序", "运行序", "点类型", "重复", "批次ID",
            "1", "1", "A实测", "收率列",
        ]
    else:
        damaged_frame = damaged_frame.rename(columns={"1": "温度"})
    target = tmp_path / "invalid-doe.dexpl"
    data = {
        "健康工作表": {"table": pd.DataFrame({"x": [1]})},
        "DOE": {"table": damaged_frame, "meta": {"doe": metadata}},
        "meta": {"active": "健康工作表", "minijmp": 1},
    }
    with gzip.open(target, "wb") as stream:
        pickle.dump(data, stream)

    original_table = app.table
    original_names = list(app.sheets)
    assert not app.load_file(target)
    assert app.table is original_table
    assert list(app.sheets) == original_names
    error.assert_called_once()


def test_corrupt_splitplot_project_does_not_replace_live_workbook(
        workbook, tmp_path):
    app, error = workbook
    factors = (
        FactorSpec("A", "A", -1, 1, randomization_role="hard_to_change"),
        FactorSpec("B", "B", -1, 1, randomization_role="easy_to_change"),
        FactorSpec("C", "C", -1, 1, randomization_role="easy_to_change"),
    )
    spec = DesignSpec(
        "bad-splitplot-load", factors, ("Y",), seed=31, design_type="split_plot",
        block_count=2, construction_version="v2", randomization_unit="whole_plot",
        error_structure="split_plot")
    frame, metadata = create_split_plot(spec)
    columns = metadata["column_map"]
    frame.loc[0, columns["whole_plot_id"]] = "WP99999H1"
    target = tmp_path / "bad-splitplot.dexpl"
    data = {
        "健康工作表": {"table": pd.DataFrame({"x": [1]})},
        "DOE Split-Plot": {"table": frame, "meta": {"doe": metadata}},
        "meta": {"active": "健康工作表", "minijmp": 1},
    }
    with gzip.open(target, "wb") as stream:
        pickle.dump(data, stream)

    original_table = app.table
    original_names = list(app.sheets)
    assert not app.load_file(target)
    assert app.table is original_table
    assert list(app.sheets) == original_names
    error.assert_called_once()


def test_stale_doe_inputs_block_save_without_overwriting_existing_project(
        workbook, tmp_path, monkeypatch):
    app, error = workbook
    frame, spec, columns = _source()
    table = app.addSheet("DOE", frame, {"doe": worksheet_metadata(frame, spec, columns)})
    target = tmp_path / "existing.dexpl"
    target.write_bytes(b"existing project")
    table.model.df.iloc[0, table.model.df.columns.get_loc("1")] = 20

    from worksheets import messagebox
    prompt = Mock(return_value=None)
    monkeypatch.setattr(messagebox, "askyesnocancel", prompt)
    assert app._confirm_discard() is False
    prompt.assert_called_once()
    assert not app._save_project(target)
    assert target.read_bytes() == b"existing project"
    error.assert_called_once()


def test_loaded_doe_metadata_is_a_safe_copy(workbook):
    app, _ = workbook
    frame, spec, columns = _source()
    source_metadata = worksheet_metadata(frame, spec, columns)
    table = app.addSheet("DOE", frame, {"doe": source_metadata})
    source_metadata["design"]["factors"][0]["name"] = "被外部修改"

    restored = restore_design_result(table.model.df, table.doe_metadata)
    assert restored.spec.factors[0].name == "温度"
    duplicate = app.copySheet()
    assert duplicate.doe_metadata is not table.doe_metadata
    assert duplicate.doe_metadata == table.doe_metadata


@pytest.mark.parametrize("version,hard,easy", [("v1", 1, 1), ("v2", 2, 2)])
def test_splitplot_append_dexpl_copy_and_reanalysis_roundtrip(
        workbook, tmp_path, version, hard, easy):
    app, error = workbook
    factors = tuple(FactorSpec(
        chr(65 + index), chr(65 + index), -1, 1,
        randomization_role=("hard_to_change" if index < hard else "easy_to_change"))
        for index in range(hard + easy))
    spec = DesignSpec(
        f"persist-split-{version}", factors, ("Y",), seed=1,
        design_type="split_plot", block_count=2, construction_version=version,
        randomization_unit="whole_plot", error_structure="split_plot")
    frame, metadata = create_split_plot(spec)
    response = metadata["column_map"]["responses"]["Y"]
    frame[response] = pd.array(range(1, len(frame) + 1), dtype="Float64")
    appended, appended_metadata = append_split_plot_blocks(frame, metadata, 1)
    validate_split_plot_design(appended, appended_metadata)
    validate_worksheet_metadata(appended, appended_metadata)
    table = app.addSheet("Split-Plot", appended, {"doe": appended_metadata})
    app.nb.select(app.sheetframes["Split-Plot"])

    copied = app.copySheet()
    assert_frame_equal(copied.model.df, appended)
    assert validate_split_plot_design(copied.model.df, copied.doe_metadata).spec.block_count == 3
    target = tmp_path / f"splitplot-{version}.dexpl"
    assert app._save_project(target)
    assert app.load_file(target)
    restored = app.sheets["Split-Plot"]
    assert_frame_equal(restored.model.df, appended)
    result = validate_split_plot_design(restored.model.df, restored.doe_metadata)
    assert result.spec.construction_version == version
    assert result.spec.block_count == 3
    assert result.spec.augmentation_lineage["criterion"] == "manual"
    batch_column = restored.doe_metadata["column_map"]["batch_id"]
    new_rows = restored.model.df[
        restored.model.df[batch_column] == "SPLITPLOT_APPEND_V1"].index
    response_column = restored.doe_metadata["column_map"]["responses"]["Y"]
    restored.model.df.loc[new_rows, response_column] = range(101, 101 + len(new_rows))
    assert analyze_split_plot(restored.model.df, restored.doe_metadata, "Y")["n"] == len(appended)
    assert error.call_count == 0


def test_corrupt_splitplot_append_order_is_rejected_on_dexpl_load(
        workbook, tmp_path):
    app, error = workbook
    factors = (
        FactorSpec("A", "A", -1, 1, randomization_role="hard_to_change"),
        FactorSpec("B", "B", -1, 1, randomization_role="easy_to_change"),
    )
    spec = DesignSpec(
        "corrupt-split-append", factors, ("Y",), seed=1,
        design_type="split_plot", block_count=2, construction_version="v1",
        randomization_unit="whole_plot", error_structure="split_plot")
    frame, metadata = create_split_plot(spec)
    appended, appended_metadata = append_split_plot_blocks(frame, metadata, 1)
    damaged = appended.copy(deep=True)
    block_column = appended_metadata["column_map"]["block"]
    whole_plot_column = appended_metadata["column_map"]["whole_plot_id"]
    whole_plot_order_column = appended_metadata["column_map"]["whole_plot_order"]
    first_block = damaged[block_column].iloc[0]
    whole_plots = damaged.loc[damaged[block_column] == first_block,
                              whole_plot_column].drop_duplicates().tolist()
    first, second = whole_plots[:2]
    first_mask = damaged[whole_plot_column] == first
    second_mask = damaged[whole_plot_column] == second
    first_order = damaged.loc[first_mask, whole_plot_order_column].iloc[0]
    second_order = damaged.loc[second_mask, whole_plot_order_column].iloc[0]
    damaged.loc[first_mask, whole_plot_order_column] = second_order
    damaged.loc[second_mask, whole_plot_order_column] = first_order
    augmented_spec = DesignSpec.from_dict(appended_metadata["design"])
    damaged_metadata = worksheet_metadata(
        damaged, augmented_spec, appended_metadata["column_map"])
    target = tmp_path / "damaged-splitplot-append.dexpl"
    data = {
        "健康工作表": {"table": pd.DataFrame({"x": [1]})},
        "DOE Split-Plot": {"table": damaged, "meta": {"doe": damaged_metadata}},
        "meta": {"active": "健康工作表", "minijmp": 1},
    }
    with gzip.open(target, "wb") as stream:
        pickle.dump(data, stream)

    original_table = app.table
    original_names = list(app.sheets)
    assert not app.load_file(target)
    assert app.table is original_table
    assert list(app.sheets) == original_names
    error.assert_called_once()
