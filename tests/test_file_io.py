"""File/model regressions using the real pandas readers and model methods."""
import csv
import gzip
import io
import pickle
import tkinter as tk
import warnings
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from pandastable_local import dialogs
from pandastable_local.data import TableModel
from pandastable_local.data_orig import TableModel as OriginalTableModel


MODELS = [OriginalTableModel, TableModel]
SAMPLES = Path(__file__).resolve().parents[1] / "sample_data"


@pytest.fixture
def mixed_frame():
    return pd.DataFrame({
        "数值": [1.25, float("nan"), -3.0],
        "文本": ['中文,带逗号', '制表\t和"引号"', '多行\n文本'],
        "日期": pd.to_datetime(["2024-01-01", None, "2024-02-29"]),
    }).rename_axis("行号")


@pytest.mark.parametrize("model_type", MODELS)
def test_pickle_chinese_mixed_roundtrip(tmp_path, mixed_frame, model_type):
    filename = tmp_path / "中文混合数据.pickle"
    model_type(mixed_frame).save(filename)
    restored = model_type()
    restored.load(filename)
    assert_frame_equal(restored.df, mixed_frame)


@pytest.mark.parametrize("extension", [".csv", ".CSV", ".xlsx", ".XLSX"])
def test_export_chinese_mixed_roundtrip(tmp_path, mixed_frame, extension):
    filename = tmp_path / ("中文导出" + extension)
    TableModel(mixed_frame).save(filename)
    if extension.lower() == ".csv":
        restored = pd.read_csv(filename, index_col=0, parse_dates=["日期"])
    else:
        restored = pd.read_excel(filename, index_col=0)
    assert_frame_equal(restored, mixed_frame)


@pytest.mark.parametrize("model_type", MODELS)
def test_unsupported_save_fails_without_overwriting(tmp_path, model_type):
    filename = tmp_path / "已有数据.unknown"
    filename.write_bytes(b"preserve existing content")
    with pytest.raises(ValueError, match="Unsupported file extension"):
        model_type(pd.DataFrame({"x": [1]})).save(filename)
    assert filename.read_bytes() == b"preserve existing content"


@pytest.mark.parametrize("model_type", MODELS)
@pytest.mark.parametrize("columns", [[], ["单列"], ["数值", "日期"]])
def test_add_rows_empty_preserves_columns(model_type, columns):
    model = model_type(pd.DataFrame(columns=columns))
    model.autoAddRows(2)
    assert model.df.shape == (2, len(columns))
    assert list(model.df.columns) == columns
    assert model.df.isna().all().all()


@pytest.mark.parametrize("model_type", MODELS)
@pytest.mark.parametrize("values", [[10, 20, 30], [10.0, 20.0, 30.0]])
def test_filtered_edit_updates_source_and_display(model_type, values):
    full = pd.DataFrame({"x": values}, index=[100, 200, 300])
    model = model_type(full.iloc[[2]].copy())
    model.setValueAt("99", 0, 0, df=full)
    assert full.x.tolist() == [10.0, 20.0, 99.0]
    assert model.df.x.tolist() == [99.0]
    model.setValueAt("", 0, 0, df=full)
    assert pd.isna(full.loc[300, "x"])
    assert pd.isna(model.df.iloc[0, 0])


@pytest.mark.parametrize("model_type", MODELS)
def test_filtered_duplicate_index_rejected_without_writes(model_type):
    full = pd.DataFrame({"x": [10, 20, 30]}, index=[1, 1, 2])
    model = model_type(full.iloc[[1]].copy())
    before = full.copy(deep=True)
    visible_before = model.df.copy(deep=True)
    with pytest.raises(ValueError, match="non-unique source index"):
        model.setValueAt("99", 0, 0, df=full)
    assert_frame_equal(full, before)
    assert_frame_equal(model.df, visible_before)


@pytest.mark.parametrize("model_type", MODELS)
def test_filtered_reordered_columns_edit_correct_source_cell(model_type):
    full = pd.DataFrame({"数值": [10.0, 20.0, 30.0], "文本": ["a", "b", "c"]},
                        index=[100, 200, 300])
    model = model_type(full.iloc[[2]].copy())
    model.moveColumn(1, 0)
    model.setValueAt("已修改", 0, 0, df=full)
    model.setValueAt("99", 0, 1, df=full)
    expected = pd.DataFrame({"数值": [10.0, 20.0, 99.0], "文本": ["a", "b", "已修改"]},
                            index=[100, 200, 300])
    assert_frame_equal(full, expected)
    assert_frame_equal(model.df, expected.loc[[300], ["文本", "数值"]])


@pytest.mark.parametrize("model_type", MODELS)
def test_filtered_duplicate_columns_rejected_without_writes(model_type):
    full = pd.DataFrame([[1.0, 2.0], [3.0, 4.0]], columns=["x", "x"])
    model = model_type(full.iloc[[1]].copy())
    before = full.copy(deep=True)
    visible_before = model.df.copy(deep=True)
    with pytest.raises(ValueError, match="non-unique source columns"):
        model.setValueAt("99", 0, 0, df=full)
    assert_frame_equal(full, before)
    assert_frame_equal(model.df, visible_before)


@pytest.mark.parametrize("model_type", MODELS)
def test_unfiltered_duplicate_labels_edit_one_cell(model_type):
    model = model_type(pd.DataFrame([[1.0, 2.0], [3.0, 4.0]],
                                   index=[1, 1], columns=["x", "x"]))
    model.setValueAt("99", 1, 1)
    assert model.df.values.tolist() == [[1.0, 2.0], [3.0, 99.0]]


def make_import_dialog(filename, monkeypatch, **overrides):
    defaults = {
        "delimiter": ("combobox", ","), "encoding": ("combobox", "utf-8"),
        "header": ("entry", 0), "skiprows": ("entry", 0),
        "skip_blank_lines": ("checkbutton", 0),
        "parse_dates": ("checkbutton", 1),
        "numbers_as_string": ("checkbutton", 0),
        "time format": ("combobox", ""), "rowsperfile": ("entry", ""),
    }
    dialog = object.__new__(dialogs.ImportDialog)
    dialog.filename = filename
    dialog.df = None
    dialog.main = Mock()
    dialog.opts = {k: {"type": t, "default": v} for k, (t, v) in defaults.items()}
    dialog.tkvars = {k: Mock(get=Mock(return_value=overrides.get(k, v)))
                     for k, (_, v) in defaults.items()}
    dialog.showText = Mock()
    dialog.quit = Mock()
    dialog.previewtable = SimpleNamespace(updateModel=Mock(), showIndex=Mock(), redraw=Mock())
    error = Mock()
    monkeypatch.setattr(dialogs.messagebox, "showerror", error)
    return dialog, error


@pytest.mark.parametrize("time_format", ["", "infer", "%d/%m/%Y"])
@pytest.mark.parametrize("as_string", [0, 1])
def test_import_preview_and_full_use_same_options(tmp_path, monkeypatch, time_format, as_string):
    filename = tmp_path / "中文导入.csv"
    filename.write_text('编号,备注\n001,"中文,逗号"\n002,"引号""和文字"\n', encoding="utf-8")
    dialog, error = make_import_dialog(filename, monkeypatch,
                                      **{"time format": time_format, "numbers_as_string": as_string})
    dialog.doImport()
    preview = dialog.previewtable.updateModel.call_args.args[0].df
    assert_frame_equal(dialog.df, preview)
    assert dialog.df.iloc[0, 1] == "中文,逗号"
    assert dialog.df.iloc[0, 0] == ("001" if as_string else 1)
    assert dialog.kwds.get("date_format") == (time_format if time_format not in ("", "infer") else None)
    error.assert_not_called()
    dialog.quit.assert_called_once()


@pytest.mark.parametrize("as_string", [0, 1])
def test_import_bad_lines_fail_visibly_without_partial_data(tmp_path, monkeypatch, as_string):
    filename = tmp_path / "坏行.csv"
    filename.write_text("a,b\n1,2\n3,4,5\n", encoding="utf-8")
    dialog, error = make_import_dialog(filename, monkeypatch, numbers_as_string=as_string)
    dialog.doImport()
    assert dialog.df is None
    assert dialog.previewtable.updateModel.call_args.args[0].df.empty
    assert "Expected 2 fields" in error.call_args.args[1]
    dialog.quit.assert_not_called()


def test_import_bad_line_after_preview_does_not_import_partial_data(tmp_path, monkeypatch):
    filename = tmp_path / "后部坏行.csv"
    filename.write_text("a,b\n" + "1,2\n" * 600 + "3,4,5\n", encoding="utf-8")
    dialog, error = make_import_dialog(filename, monkeypatch)
    dialog.doImport()
    assert dialog.df is None
    assert len(dialog.previewtable.updateModel.call_args.args[0].df) == 500
    assert error.call_count == 1
    dialog.quit.assert_not_called()


@pytest.mark.parametrize("filename,shape,type_counts", [
    ("ElectricCarData_Clean-kaggle.csv", (103, 14), {"object": 8, "int64": 5, "float64": 1}),
    ("human_age_prediction-Kaggle.csv", (3000, 25), {"object": 13, "float64": 12}),
])
def test_official_comma_csv_encoding_shape_and_types(filename, shape, type_counts):
    path = SAMPLES / filename
    text = path.read_bytes().decode("utf-8")
    rows = list(csv.reader(io.StringIO(text)))
    frame = import_through_menu(path)
    assert frame.shape == shape
    assert len(rows) == shape[0] + 1
    assert {len(row) for row in rows} == {shape[1]}
    assert frame.dtypes.astype(str).value_counts().to_dict() == type_counts


def test_coatings_is_tab_separated_and_has_no_header():
    path = SAMPLES / "coatings.csv"
    text = path.read_bytes().decode("ascii")
    records = [row for row in csv.reader(io.StringIO(text), delimiter="\t") if row]
    assert len(records) == 32
    assert {len(row) for row in records} == {2}
    assert import_through_menu(path).shape == (31, 1)
    frame = import_through_menu(path, sep="\t", header=None)
    assert frame.shape == (32, 2)
    assert frame.iloc[0].tolist() == [1, 18.5]
    assert frame.dtypes.astype(str).tolist() == ["int64", "float64"]


@pytest.mark.parametrize("skip_blank_lines,expected_rows", [(0, 33), (1, 32)])
def test_coatings_dialog_explicit_tab_empty_header(tmp_path, monkeypatch, skip_blank_lines, expected_rows, tk_root):
    dialog, error = make_import_dialog(SAMPLES / "coatings.csv", monkeypatch,
                                      delimiter=r"\t", skip_blank_lines=skip_blank_lines)
    header = tk.IntVar(master=tk_root, value=0)
    header.set("")
    dialog.tkvars["header"] = header
    with warnings.catch_warnings():
        warnings.simplefilter("error", pd.errors.ParserWarning)
        dialog.doImport()
    assert dialog.kwds["header"] is None
    assert dialog.kwds["delimiter"] == "\t"
    assert dialog.df.shape == (expected_rows, 2)
    assert dialog.df.iloc[0].tolist() == [1, 18.5]
    assert_frame_equal(dialog.previewtable.updateModel.call_args.args[0].df, dialog.df)
    error.assert_not_called()
    dialog.quit.assert_called_once()


def test_gb18030_dialog_import(tmp_path, monkeypatch):
    filename = tmp_path / "中文旧编码.csv"
    filename.write_text("名称,数值\n中文,1.5\n", encoding="gb18030")
    dialog, error = make_import_dialog(filename, monkeypatch, encoding="gb18030")
    dialog.doImport()
    assert list(dialog.df.columns) == ["名称", "数值"]
    assert dialog.df.iloc[0].tolist() == ["中文", 1.5]
    error.assert_not_called()


def import_through_menu(filename, **kwargs):
    from pandastable_local.core_orig import Table

    table = SimpleNamespace(importpath=None, currentdir=str(SAMPLES),
                            updateModel=Mock(), redraw=Mock())
    Table.importCSV(table, filename=filename, **kwargs)
    return table.updateModel.call_args.args[0].df


def test_official_excel_read():
    with pd.ExcelFile(SAMPLES / "Gasket.xlsx") as workbook:
        assert workbook.sheet_names == ["Gasket"]
        frame = workbook.parse("Gasket")
    assert frame.shape == (30, 3)
    assert frame.dtypes.astype(str).to_dict() == {"Operator": "object", "Part": "int64", "Y": "int64"}


def test_project_real_save_and_load_chinese_mixed_roundtrip(tmp_path, mixed_frame, monkeypatch):
    import matplotlib

    with monkeypatch.context() as scoped:
        scoped.setattr(matplotlib, "use", Mock())
        from pandastable_local.app import DataExplore

    filename = tmp_path / "中文工程.dexpl"
    metadata = {"table": {"note": "中文备注"}}
    app = SimpleNamespace(
        sheets={"中文工作表": SimpleNamespace(model=TableModel(mixed_frame))},
        _checkTables=Mock(), saveMeta=Mock(return_value=metadata),
    )
    DataExplore.doSaveProject(app, str(filename))
    with gzip.open(filename, "rb") as stream:
        saved = pickle.load(stream)
    assert_frame_equal(saved["中文工作表"]["table"], mixed_frame)
    assert saved["中文工作表"]["meta"] == metadata
    loaded = SimpleNamespace(newProject=Mock(), main=Mock(), addRecent=Mock())
    DataExplore.loadProject(loaded, str(filename))
    restored = loaded.newProject.call_args.args[0]
    assert_frame_equal(restored["中文工作表"]["table"], mixed_frame)
    assert restored["中文工作表"]["meta"] == metadata
