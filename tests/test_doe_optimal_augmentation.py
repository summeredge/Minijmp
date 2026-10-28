import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from doe_augment import augment, select_augment
from doe_core import DesignSpec, FactorSpec, restore_design_result, worksheet_metadata
from doe_custom import coded_value, design_matrix
from doe_optimal import evaluate


REFERENCE = json.loads((Path(__file__).parent / "fixtures" / "doe_optimal_reference"
                        / "reference.json").read_text(encoding="utf-8"))


def rsm_design():
    """2^2 因子点 + 1 中心点；完整二次模型初始欠秩，需要轴点增补。"""
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
    spec = DesignSpec(
        "rsm-parent", (FactorSpec("X1", "X1", -1.7, 1.7),
                       FactorSpec("X2", "X2", -1.7, 1.7)),
        ("Y",), design_type="custom_rsm", schema_version=5,
        model_terms=("X1", "X2", "X1²", "X2²", "X1*X2"))
    mapping = {"run_id": "运行ID", "standard_order": "标准序",
               "run_order": "运行序", "point_type": "点类型",
               "replicate": "重复", "block": None, "batch_id": "批次",
               "source_run_id": "来源",
               "factors": {"X1": "X1", "X2": "X2"}, "responses": {"Y": "Y"}}
    return frame, worksheet_metadata(frame, spec, mapping)


def test_optimal_augmentation_improves_rank_and_keeps_fixed_runs():
    frame, metadata = rsm_design()
    design = restore_design_result(frame, metadata)
    before, _ = design_matrix(design)
    candidates = [{"X1": 1.7, "X2": 0}, {"X1": -1.7, "X2": 0},
                  {"X1": 0, "X2": 1.7}, {"X1": 0, "X2": -1.7}]
    result, result_metadata, summary = augment(
        frame, metadata, candidates, 2, batch_id="AUG2",
        point_types=["axial"] * 4)
    after_design = restore_design_result(result, result_metadata)
    after, _ = design_matrix(after_design)
    assert summary["initial_rank"] < summary["p"]
    assert summary["augmented_rank"] == summary["p"] == 6
    assert np.linalg.matrix_rank(after) == 6
    assert result[result["批次"] == "BASE"]["Y"].tolist() == \
        [10.0, 12.0, 14.0, 16.0, 13.0]
    assert result[result["批次"] == "AUG2"]["Y"].isna().all()
    assert evaluate(after.tolist())["logdet"] > 0
    lineage = after_design.spec.augmentation_lineage
    assert lineage["batch_id"] == "AUG2"
    assert len(lineage["run_map"]) == 2
    assert np.linalg.matrix_rank(before) == summary["initial_rank"]


def test_augmentation_never_removes_executed_runs():
    frame, metadata = rsm_design()
    candidates = [{"X1": 1.7, "X2": 0}, {"X1": -1.7, "X2": 0},
                  {"X1": 0, "X2": 1.7}, {"X1": 0, "X2": -1.7}]
    result, _, _ = augment(frame, metadata, candidates, 2,
                           point_types=["axial"] * 4)
    base = result[result["批次"] == "BASE"]
    assert len(base) == len(frame)
    assert base["运行ID"].tolist() == frame["运行ID"].tolist()


def test_augmentation_rejects_no_rank_improvement():
    frame, metadata = rsm_design()
    with pytest.raises(ValueError, match="秩|满秩"):
        augment(frame, metadata, [{"X1": 0, "X2": 0}], 1, point_types=["center"])


def test_augmentation_rejects_duplicate_candidate_and_run_id_conflict():
    frame, metadata = rsm_design()
    candidates = [{"X1": 1.7, "X2": 0}, {"X1": 1.7, "X2": 0}]
    with pytest.raises(ValueError, match="候选点不足"):
        augment(frame, metadata, candidates, 2, point_types=["axial"] * 2)
    with pytest.raises(ValueError, match="冲突"):
        augment(frame, metadata, candidates, 1, run_ids=["R1"],
                point_types=["axial"] * 2)


def test_augmentation_requires_matching_point_types():
    frame, metadata = rsm_design()
    with pytest.raises(ValueError, match="点类型|中点"):
        augment(frame, metadata, [{"X1": 1.7, "X2": 0}], 1,
                point_types=["center"])


def distance_parent():
    """四角固定的响应面父设计；轴点/中心留作距离增补候选。"""
    frame = pd.DataFrame({
        "运行ID": ["R1", "R2", "R3", "R4"],
        "标准序": [1, 2, 3, 4], "运行序": [1, 2, 3, 4],
        "点类型": ["factorial"] * 4, "重复": [1] * 4,
        "批次": ["BASE"] * 4, "来源": [None] * 4,
        "X1": [1, -1, -1, 1], "X2": [1, 1, -1, -1],
        "Y": [10.0, 12.0, 9.0, 13.0],
    })
    spec = DesignSpec(
        "distance-parent", (FactorSpec("X1", "X1", -1, 1),
                            FactorSpec("X2", "X2", -1, 1)),
        ("Y",), design_type="custom_rsm", schema_version=5,
        model_terms=("X1", "X2", "X1*X2"))
    mapping = {"run_id": "运行ID", "standard_order": "标准序",
               "run_order": "运行序", "point_type": "点类型",
               "replicate": "重复", "block": None, "batch_id": "批次",
               "source_run_id": "来源",
               "factors": {"X1": "X1", "X2": "X2"}, "responses": {"Y": "Y"}}
    return frame, worksheet_metadata(frame, spec, mapping)


def test_distance_augmentation_matches_hand_computed_order():
    case = REFERENCE["distance_augment"]
    frame, metadata = distance_parent()
    candidates = [{"X1": point[0], "X2": point[1]}
                  for point in case["candidates"]]
    result, result_metadata, summary = augment(
        frame, metadata, candidates, case["select"], criterion="distance",
        batch_id="AUGD", point_types=["center", "edge", "edge", "edge", "edge"])
    selected = list(summary["selection_order"])
    assert selected == case["expected"]["order"]
    assert summary["method"] == "distance"
    assert summary["global_optimum_proven"] is False
    assert np.isclose(summary["min_squared_distance"],
                      case["expected"]["augmented_min_squared_distance"])
    added = result[result["批次"] == "AUGD"]
    assert [(row["X1"], row["X2"]) for _, row in added.iterrows()] == \
        [tuple(point) for point in case["expected"]["selected_points"]]
    # 已执行运行与响应保留，增补行响应为空。
    assert result[result["批次"] == "BASE"]["Y"].tolist() == [10.0, 12.0, 9.0, 13.0]
    assert added["Y"].isna().all()
    lineage = restore_design_result(result, result_metadata).spec.augmentation_lineage
    assert lineage["criterion"] == "distance"
    assert lineage["batch_id"] == "AUGD"


def test_distance_augmentation_rejects_factorial_family_and_repeats():
    # 自定义响应面的父设计可用距离准则；自定义因子设计必须明确拒绝。
    frame = pd.DataFrame({
        "运行ID": ["F1", "F2", "F3", "F4"],
        "标准序": [1, 2, 3, 4], "运行序": [1, 2, 3, 4],
        "点类型": ["factorial"] * 4, "重复": [1] * 4,
        "批次": ["BASE"] * 4, "来源": [None] * 4,
        "A": [1, 1, -1, -1], "B": [1, -1, 1, -1],
        "Y": [10.0, 12.0, 14.0, 16.0],
    })
    spec = DesignSpec("factor-parent", (FactorSpec("A", "A", -1, 1),
                                        FactorSpec("B", "B", -1, 1)),
                      ("Y",), design_type="custom_factorial")
    mapping = {"run_id": "运行ID", "standard_order": "标准序",
               "run_order": "运行序", "point_type": "点类型",
               "replicate": "重复", "block": None, "batch_id": "批次",
               "source_run_id": "来源",
               "factors": {"A": "A", "B": "B"}, "responses": {"Y": "Y"}}
    metadata = worksheet_metadata(frame, spec, mapping)
    with pytest.raises(ValueError, match="响应面"):
        augment(frame, metadata, [{"A": 0, "B": 0}], 1, criterion="distance")


def test_distance_augmentation_deduplicates_selected_points():
    frame, metadata = distance_parent()
    # 四角父设计已用掉全部四角，只给重复候选时必须明确拒绝而不是复制。
    with pytest.raises(ValueError, match="候选点不足"):
        augment(frame, metadata, [{"X1": 1, "X2": 1}, {"X1": 1, "X2": 1}], 2,
                criterion="distance")


def axial_parent():
    """2^2 因子点 + 1 中心点，low/high = -1/1；轴点坐标在声明范围之外。"""
    frame = pd.DataFrame({
        "运行ID": ["R1", "R2", "R3", "R4", "R5"],
        "标准序": [1, 2, 3, 4, 5], "运行序": [1, 2, 3, 4, 5],
        "点类型": ["factorial"] * 4 + ["center"], "重复": [1] * 5,
        "批次": ["BASE"] * 5, "来源": [None] * 5,
        "X1": [1, -1, 1, -1, 0], "X2": [1, 1, -1, -1, 0],
        "Y": [10.0, 12.0, 14.0, 16.0, 13.0],
    })
    spec = DesignSpec(
        "axial-parent", (FactorSpec("X1", "X1", -1, 1),
                         FactorSpec("X2", "X2", -1, 1)),
        ("Y",), design_type="custom_rsm", schema_version=5,
        model_terms=("X1", "X2", "X1²", "X2²", "X1*X2"))
    mapping = {"run_id": "运行ID", "standard_order": "标准序",
               "run_order": "运行序", "point_type": "点类型",
               "replicate": "重复", "block": None, "batch_id": "批次",
               "source_run_id": "来源",
               "factors": {"X1": "X1", "X2": "X2"}, "responses": {"Y": "Y"}}
    return frame, worksheet_metadata(frame, spec, mapping)


AXIAL_POINTS = [{"X1": 1.682, "X2": 0}, {"X1": -1.682, "X2": 0},
                {"X1": 0, "X2": 1.682}, {"X1": 0, "X2": -1.682}]


def test_axial_augmentation_encodes_beyond_declared_range_for_both_criteria():
    # 父设计四角 + 中心：完整二次模型秩 5/6，需要 2 个轴点补满。
    frame, metadata = axial_parent()
    for criterion, batch in (("d_optimal", "AXD"), ("distance", "AXS")):
        result, result_metadata, summary = augment(
            frame, metadata, AXIAL_POINTS, 2, criterion=criterion,
            batch_id=batch, point_types=["axial"] * 4)
        assert summary["initial_rank"] == 5
        assert summary["augmented_rank"] == summary["p"] == 6, criterion
        design = restore_design_result(result, result_metadata)
        matrix, _ = design_matrix(design)
        assert np.linalg.matrix_rank(matrix) == 6
        # 轴点必须按 1.682 编码（不是被裁剪或拒绝），即平方项约为 2.829。
        added = result[result["批次"] == batch]
        assert len(added) == 2
        assert set(added["X1"].abs().tolist()) <= {0.0, 1.682}
        assert added["Y"].isna().all()
        assert result[result["批次"] == "BASE"]["Y"].tolist() == \
            [10.0, 12.0, 14.0, 16.0, 13.0]
        assert result[result["批次"] == batch]["运行ID"].is_unique
        assert restore_design_result(result, result_metadata).spec.\
            augmentation_lineage["batch_id"] == batch
        coded = design.spec.factors[0]
        assert abs(coded_value(coded, 1.682, "axial")) == pytest.approx(1.682)


def test_out_of_range_candidate_marked_factorial_is_rejected():
    frame, metadata = axial_parent()
    with pytest.raises(ValueError, match="范围"):
        augment(frame, metadata, [AXIAL_POINTS[0], AXIAL_POINTS[2]], 2,
                criterion="d_optimal", point_types=["factorial", "factorial"])
