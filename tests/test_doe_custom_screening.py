import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from doe_core import FactorSpec, restore_design_result
from doe_custom import define_custom, screening_properties
from doe_custom_analysis import analyze_custom_screening


REFERENCE = json.loads((Path(__file__).parent / "fixtures" / "doe_optimal_reference"
                        / "reference.json").read_text(encoding="utf-8"))


def reference_frame():
    case = REFERENCE["custom_dsd"]
    matrix = case["matrix"]
    frame = pd.DataFrame({
        "运行ID": [f"R{index:05d}" for index in range(1, len(matrix) + 1)],
        "标准序": list(range(1, len(matrix) + 1)),
        "运行序": list(range(1, len(matrix) + 1)),
        "点类型": ["screening"] * (len(matrix) - 1) + ["center"],
        "重复": [1] * len(matrix),
    })
    for index in range(6):
        frame[f"X{index + 1}"] = [row[index] for row in matrix]
    values = np.asarray(matrix, dtype=float)
    frame["Y"] = 20 + 2 * values[:, 0] - values[:, 1] + 0.5 * values[:, 0] ** 2
    return frame


def factors():
    return tuple(FactorSpec(f"X{index + 1}", f"X{index + 1}", -1, 1)
                 for index in range(6))


def columns():
    return {"run_id": "运行ID", "standard_order": "标准序", "run_order": "运行序",
            "point_type": "点类型", "replicate": "重复",
            "factors": {f"X{index + 1}": f"X{index + 1}" for index in range(6)},
            "responses": {"Y": "Y"}}


def test_custom_screening_verifies_construction_and_keeps_matrix():
    frame = reference_frame()
    original = frame.copy(deep=True)
    result, metadata, summary = define_custom(
        frame, design_type="custom_screening", factors=factors(),
        responses=("Y",), column_map=columns(), design_id="custom-dsd")
    pd.testing.assert_frame_equal(frame, original)
    expected = REFERENCE["custom_dsd"]["expected"]
    assert summary["main_two_factor_orthogonal"] is True
    assert summary["has_zeros"] is True
    assert summary["continuous_factors"] == 6
    assert summary["main_sums_of_squares"] == expected["main_sums_of_squares"]
    assert summary["n"] == 13
    design = restore_design_result(result, metadata)
    assert [run.settings["X1"] for run in design.runs] == [
        row[0] for row in expected and REFERENCE["custom_dsd"]["matrix"]]


def test_custom_screening_analysis_reports_estimable_main_effects():
    frame = reference_frame()
    result, metadata, _ = define_custom(
        frame, design_type="custom_screening", factors=factors(),
        responses=("Y",), column_map=columns())
    analysis = analyze_custom_screening(result, metadata, "Y")
    assert analysis["n"] == 13
    assert analysis["rank"] == 7
    assert analysis["properties"]["main_orthogonal"] is True
    assert np.isclose(analysis["coefficients"][1], 2)
    assert np.isclose(analysis["coefficients"][2], -1)


def test_custom_screening_rejects_three_level_non_dsd_matrix():
    frame = reference_frame()
    frame.loc[0, "X1"] = 1
    frame.loc[1, "X1"] = 1
    with pytest.raises(ValueError, match="正交|重复"):
        define_custom(frame, design_type="custom_screening", factors=factors(),
                      responses=("Y",), column_map=columns())


def test_custom_screening_rejects_pb_like_two_level_matrix():
    frame = reference_frame()
    values = np.asarray(
        [[frame.loc[row, f"X{index + 1}"] for index in range(6)]
         for row in range(len(frame))], dtype=float)
    matrix = np.where(values == 0, 1, values)
    for row in range(len(frame)):
        for index in range(6):
            frame.loc[row, f"X{index + 1}"] = matrix[row, index]
    with pytest.raises(ValueError, match="重复|三水平|正交"):
        define_custom(frame, design_type="custom_screening", factors=factors(),
                      responses=("Y",), column_map=columns())


def test_custom_screening_rejects_duplicate_design_points_and_bad_levels():
    frame = reference_frame()
    for index in range(6):
        frame[f"X{index + 1}"] = frame[f"X{index + 1}"].astype(float)
    frame.loc[1, [f"X{index + 1}" for index in range(6)]] = \
        frame.loc[0, [f"X{index + 1}" for index in range(6)]].tolist()
    with pytest.raises(ValueError, match="重复"):
        define_custom(frame, design_type="custom_screening", factors=factors(),
                      responses=("Y",), column_map=columns())
    frame = reference_frame()
    for index in range(6):
        frame[f"X{index + 1}"] = frame[f"X{index + 1}"].astype(float)
    frame.loc[0, "X1"] = 0.5
    with pytest.raises(ValueError, match="筛选因子"):
        define_custom(frame, design_type="custom_screening", factors=factors(),
                      responses=("Y",), column_map=columns())


def test_custom_screening_with_text_categorical_factors():
    case = REFERENCE["custom_dsd_text"]
    matrix = case["matrix"]
    frame = pd.DataFrame({
        "运行ID": [f"R{index:05d}" for index in range(1, len(matrix) + 1)],
        "标准序": list(range(1, len(matrix) + 1)),
        "运行序": list(range(1, len(matrix) + 1)),
        "点类型": ["screening"] * (len(matrix) - 1) + ["center"],
        "重复": [1] * len(matrix),
    })
    for index in range(5):
        frame[f"X{index + 1}"] = [row[index] for row in matrix]
    frame["E"] = ["低" if row[4] < 0 else "高" for row in matrix]
    frame["Y"] = np.arange(len(frame), dtype=float)
    factor_specs = tuple(FactorSpec(f"X{index + 1}", f"X{index + 1}", -1, 1)
                         for index in range(4)) + (
        FactorSpec("E", "E", None, None, factor_type="categorical",
                   levels=("低", "高"), level_type="text"),)
    mapping = {"run_id": "运行ID", "standard_order": "标准序",
               "run_order": "运行序", "point_type": "点类型", "replicate": "重复",
               "factors": {**{f"X{index + 1}": f"X{index + 1}"
                              for index in range(4)}, "E": "E"},
               "responses": {"Y": "Y"}}
    result, metadata, summary = define_custom(
        frame, design_type="custom_screening", factors=factor_specs,
        responses=("Y",), column_map=mapping)
    assert summary["continuous_factors"] == 4
    assert summary["categorical_factors"] == 1
    design = restore_design_result(result, metadata)
    assert design.runs[0].settings["E"] in ("低", "高")
