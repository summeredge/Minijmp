import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from doe_core import FactorSpec, restore_design_result
from doe_custom import design_matrix
from doe_optimal import select_distance
from doe_optimal_design import optimal_from_candidates


REFERENCE = json.loads((Path(__file__).parent / "fixtures" / "doe_optimal_reference"
                        / "reference.json").read_text(encoding="utf-8"))


def grid_frame():
    points = REFERENCE["distance_rsm"]["points"]
    return pd.DataFrame({
        "运行ID": [f"C{index:05d}" for index in range(1, len(points) + 1)],
        "标准序": list(range(1, len(points) + 1)),
        "运行序": list(range(1, len(points) + 1)),
        "点类型": ["factorial"] * len(points),
        "重复": [1] * len(points),
        "X1": [row[0] for row in points],
        "X2": [row[1] for row in points],
        "Y": [None] * len(points),
    })


def factors():
    return (FactorSpec("X1", "X1", -1, 1), FactorSpec("X2", "X2", -1, 1))


def mapping():
    return {"run_id": "运行ID", "standard_order": "标准序",
            "run_order": "运行序", "point_type": "点类型", "replicate": "重复",
            "factors": {"X1": "X1", "X2": "X2"}, "responses": {"Y": "Y"}}


def test_distance_selection_order_matches_hand_computed_reference():
    case = REFERENCE["distance_rsm"]
    summary = select_distance(case["points"], case["select"])
    assert list(summary["selection_order"]) == case["expected"]["order"]
    assert summary["min_squared_distance"] == 4
    assert len(set(summary["selection_order"])) == case["select"]


def test_distance_design_creates_persistable_workbook_with_lineage():
    case = REFERENCE["distance_rsm"]
    result, metadata, summary = optimal_from_candidates(
        grid_frame(), design_type="custom_rsm", factors=factors(),
        responses=("Y",), column_map=mapping(), count=case["select"],
        model_terms=["X1", "X2", "X1*X2"], criterion="distance")
    assert len(result) == case["select"]
    design = restore_design_result(result, metadata)
    assert design.spec.optimal_lineage["criterion"] == "distance"
    points = case["points"]
    assert [(row["X1"], row["X2"]) for _, row in result.iterrows()] == [
        tuple(points[index]) for index in case["expected"]["order"]]


def test_distance_requires_response_surface_family():
    with pytest.raises(ValueError, match="D-optimality"):
        optimal_from_candidates(grid_frame(), design_type="custom_factorial",
                                factors=factors(), responses=("Y",),
                                column_map=mapping(), count=3,
                                criterion="distance")


def test_distance_does_not_repeat_points_and_uses_coded_origin():
    case = REFERENCE["distance_rsm"]
    summary = select_distance(case["points"], 6)
    assert len(set(summary["selection_order"])) == 6
    # 起点是编码原点最远点（四角之一），不是中心点。
    assert case["points"][summary["selection_order"][0]] != [0, 0]


def test_mixture_distance_requires_component_count():
    with pytest.raises(ValueError, match="组分列数"):
        select_distance([[1, 0], [0, 1]], 2, kind="mixture")


def test_mixture_distance_never_repeats_selected_coordinates():
    points = [[1, 0, 0], [0, 1, 0], [0, 0, 1], [1, 0, 0]]
    summary = select_distance(points, 3, kind="mixture", component_count=3)
    assert len(set(summary["selection_order"])) == 3
    assert summary["selection_order"] == (0, 1, 2)
    with pytest.raises(ValueError, match="候选点不足"):
        select_distance(points, 4, kind="mixture", component_count=3)


def quadratic_grid_frame():
    """3×3 网格 + 中心：完整二次模型 6 参数。"""
    points = [[x1, x2] for x1 in (-1, 0, 1) for x2 in (-1, 0, 1)]
    return pd.DataFrame({
        "运行ID": [f"C{index:05d}" for index in range(1, len(points) + 1)],
        "标准序": list(range(1, len(points) + 1)),
        "运行序": list(range(1, len(points) + 1)),
        "点类型": ["factorial"] * len(points), "重复": [1] * len(points),
        "X1": [row[0] for row in points], "X2": [row[1] for row in points],
        "Y": [None] * len(points)})


QUADRATIC = ["X1", "X2", "X1²", "X2²", "X1*X2"]


def test_distance_selection_rejects_rank_deficient_three_point_design():
    # 3 点无法估计 6 参数完整二次模型：不能静默生成"可分析"的设计。
    with pytest.raises(ValueError, match="秩为 3/6|不能估计"):
        optimal_from_candidates(quadratic_grid_frame(), design_type="custom_rsm",
                                factors=factors(), responses=("Y",),
                                column_map=mapping(), count=3,
                                model_terms=QUADRATIC, criterion="distance")


def test_distance_selection_accepts_full_rank_six_point_design():
    result, metadata, summary = optimal_from_candidates(
        quadratic_grid_frame(), design_type="custom_rsm", factors=factors(),
        responses=("Y",), column_map=mapping(), count=6,
        model_terms=QUADRATIC, criterion="distance")
    assert summary["estimable"] is True
    assert summary["selected_rank"] == summary["selected_p"] == 6
    design = restore_design_result(result, metadata)
    matrix, _ = design_matrix(design)
    assert np.linalg.matrix_rank(matrix) == 6
    # 手算 3×3 网格（行优先索引 0..8）：原点最远四角并列取 0；随后最远 8；
    # 再并列取 2；再 6；中心 4 的最近距离 2 大于其余边中点 1；最后并列取 1。
    assert list(summary["selection_order"]) == [0, 8, 2, 6, 4, 1]
    assert summary["min_squared_distance"] == 1
