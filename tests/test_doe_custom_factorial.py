import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from doe_core import DesignSpec, FactorSpec, restore_design_result
from doe_custom import define_custom, design_matrix, validate_custom
from doe_custom_analysis import analyze_custom_factorial


REFERENCE = json.loads((Path(__file__).parent / "fixtures" / "doe_optimal_reference"
                        / "reference.json").read_text(encoding="utf-8"))


def reference_frame():
    case = REFERENCE["custom_factorial_2x3"]
    return pd.DataFrame({
        "运行ID": [row["run_id"] for row in case["rows"]],
        "标准序": [row["standard_order"] for row in case["rows"]],
        "运行序": [row["run_order"] for row in case["rows"]],
        "点类型": ["factorial"] * len(case["rows"]),
        "重复": [row["replicate"] for row in case["rows"]],
        "A": [row["settings"]["A"] for row in case["rows"]],
        "B": [row["settings"]["B"] for row in case["rows"]],
        "C": [row["settings"]["C"] for row in case["rows"]],
        "Y": [row["Y"] for row in case["rows"]],
    })


def columns():
    return {"run_id": "运行ID", "standard_order": "标准序", "run_order": "运行序",
            "point_type": "点类型", "replicate": "重复", "factors": {
                "A": "A", "B": "B", "C": "C"}, "responses": {"Y": "Y"}}


def factors():
    return tuple(FactorSpec(key, key, None, None, factor_type="categorical",
                            levels=("低", "高"), level_type="text")
                 for key in "ABC")


def test_custom_factorial_definition_keeps_rows_levels_and_analysis():
    frame = reference_frame()
    original = frame.copy(deep=True)
    result, metadata, summary = define_custom(
        frame, design_type="custom_factorial", factors=factors(),
        responses=("Y",), column_map=columns(), design_id="custom-abc")
    pd.testing.assert_frame_equal(frame, original)
    assert summary["complete_factorial"] is True
    assert summary["rank"] == 4 == summary["p"]
    assert summary["regular_fraction"] is False
    assert metadata["design"]["design_type"] == "custom_factorial"
    assert metadata["design"]["schema_version"] == 5
    restored = restore_design_result(result, metadata)
    assert [run.run_id for run in restored.runs] == list(frame["运行ID"])
    assert [run.run_order for run in restored.runs] == list(frame["运行序"])
    analysis = analyze_custom_factorial(result, metadata, "Y", 1)
    expected = REFERENCE["custom_factorial_2x3"]["expected"]["coefficients"]
    assert analysis["names"] == ["截距", "A", "B", "C"]
    assert np.isclose(analysis["coefficients"][1], float(expected["A"]))
    assert np.isclose(analysis["coefficients"][2], float(expected["B"]))
    assert np.isclose(analysis["coefficients"][3], float(expected["C"]))
    assert analysis["n"] == 8 and analysis["df"] == 4


def test_custom_factorial_rejects_duplicate_run_ids_and_bad_orders():
    frame = reference_frame()
    frame.loc[1, "运行ID"] = frame.loc[0, "运行ID"]
    with pytest.raises(ValueError, match="唯一"):
        define_custom(frame, design_type="custom_factorial", factors=factors(),
                      responses=("Y",), column_map=columns())
    frame = reference_frame()
    frame.loc[0, "标准序"] = 9
    with pytest.raises(ValueError, match="standard_order"):
        define_custom(frame, design_type="custom_factorial", factors=factors(),
                      responses=("Y",), column_map=columns())
    frame = reference_frame()
    frame.loc[0, "运行序"] = 0
    with pytest.raises(ValueError, match="run_order"):
        define_custom(frame, design_type="custom_factorial", factors=factors(),
                      responses=("Y",), column_map=columns())


def test_custom_factorial_rejects_unknown_levels_and_bad_point_types():
    frame = reference_frame()
    frame.loc[0, "A"] = "中"
    with pytest.raises(ValueError, match="水平"):
        define_custom(frame, design_type="custom_factorial", factors=factors(),
                      responses=("Y",), column_map=columns())
    frame = reference_frame()
    frame.loc[0, "点类型"] = "axial"
    with pytest.raises(ValueError, match="不支持轴点"):
        define_custom(frame, design_type="custom_factorial", factors=factors(),
                      responses=("Y",), column_map=columns())


def test_custom_factorial_rejects_missing_or_duplicate_columns():
    frame = reference_frame().drop(columns=["B"])
    with pytest.raises(ValueError, match="不存在"):
        define_custom(frame, design_type="custom_factorial", factors=factors(),
                      responses=("Y",), column_map=columns())
    frame = reference_frame()
    mapping = columns()
    mapping["factors"] = {"A": "A", "B": "A", "C": "C"}
    with pytest.raises(ValueError, match="同一列"):
        define_custom(frame, design_type="custom_factorial", factors=factors(),
                      responses=("Y",), column_map=mapping)


def test_custom_factorial_incomplete_matrix_is_flagged_not_claimed_regular():
    frame = reference_frame().iloc[:4].reset_index(drop=True)
    frame["运行序"] = range(1, 5)
    result, metadata, summary = define_custom(
        frame, design_type="custom_factorial", factors=factors(),
        responses=("Y",), column_map=columns())
    assert summary["complete_factorial"] is False
    assert summary["regular_fraction"] is False
    assert summary["unique_points"] == 4


def test_source_column_change_invalidates_identity():
    frame = reference_frame()
    result, metadata, _ = define_custom(
        frame, design_type="custom_factorial", factors=factors(),
        responses=("Y",), column_map=columns())
    result.loc[0, "A"] = "高" if result.loc[0, "A"] == "低" else "低"
    with pytest.raises(ValueError):
        restore_design_result(result, metadata)


def test_rank_deficient_model_is_rejected_for_custom_factorial():
    frame = reference_frame().iloc[:2].reset_index(drop=True)
    frame["标准序"] = [1, 2]
    frame["运行序"] = [1, 2]
    frame.loc[1, ["A", "B", "C"]] = frame.loc[0, ["A", "B", "C"]]
    with pytest.raises(ValueError, match="重复"):
        define_custom(frame, design_type="custom_factorial", factors=factors(),
                      responses=("Y",), column_map=columns())
