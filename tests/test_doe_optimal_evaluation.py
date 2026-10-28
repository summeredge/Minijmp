import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from doe_core import FactorSpec, restore_design_result
from doe_custom import design_matrix, define_custom
from doe_optimal import evaluate
from doe_optimal_design import optimal_from_candidates


REFERENCE = json.loads((Path(__file__).parent / "fixtures" / "doe_optimal_reference"
                        / "reference.json").read_text(encoding="utf-8"))


def candidate_frame():
    case = REFERENCE["rsm_candidates"]
    rows = []
    for index, row in enumerate(case["candidates"]):
        rows.append({"运行ID": f"C{index + 1:05d}", "标准序": index + 1,
                     "运行序": index + 1, "点类型": "factorial", "重复": 1,
                     "X1": row[1], "X2": row[2], "Y": None})
    return pd.DataFrame(rows)


def factors():
    return (FactorSpec("X1", "X1", -1, 1), FactorSpec("X2", "X2", -1, 1))


def mapping():
    return {"run_id": "运行ID", "standard_order": "标准序",
            "run_order": "运行序", "point_type": "点类型", "replicate": "重复",
            "factors": {"X1": "X1", "X2": "X2"}, "responses": {"Y": "Y"}}


def test_optimal_selection_matches_exhaustive_reference():
    case = REFERENCE["rsm_candidates"]
    result, metadata, summary = optimal_from_candidates(
        candidate_frame(), design_type="custom_rsm", factors=factors(),
        responses=("Y",), column_map=mapping(), count=case["select"],
        model_terms=["X1", "X2", "X1²", "X2²", "X1*X2"])
    assert summary["method"] == "exact_enumeration"
    assert summary["global_optimum_proven"] is True
    assert len(result) == case["select"]
    assert list(result["X1"]) == [case["candidates"][index][1]
                                  for index in case["expected"]["selected"]]
    assert np.isclose(np.exp(summary["logdet"]),
                      float(case["expected"]["det_xtx"]), rtol=1e-9)
    design = restore_design_result(result, metadata)
    assert design.spec.optimal_lineage["criterion"] == "d_optimal"
    assert design.spec.optimal_lineage["batch_id"] == "OPT1"
    assert len(design.spec.optimal_lineage["selection_order"]) == case["select"]
    matrix, _ = design_matrix(design)
    assert evaluate(matrix.tolist())["rank"] == 6


def test_factorial_rejects_distance_based_criterion():
    frame = candidate_frame()
    with pytest.raises(ValueError, match="D-optimality"):
        optimal_from_candidates(frame, design_type="custom_factorial",
                                factors=factors(), responses=("Y",),
                                column_map=mapping(), count=2,
                                criterion="distance")


def test_optimal_selection_requires_model_terms_for_rsm():
    with pytest.raises(ValueError, match="模型项"):
        optimal_from_candidates(candidate_frame(), design_type="custom_rsm",
                                factors=factors(), responses=("Y",),
                                column_map=mapping(), count=3)


def test_optimal_selection_rejects_insufficient_points():
    with pytest.raises(ValueError, match="不能超过候选行数"):
        optimal_from_candidates(candidate_frame(), design_type="custom_rsm",
                                factors=factors(), responses=("Y",),
                                column_map=mapping(), count=20,
                                model_terms=["X1", "X2", "X1²", "X2²", "X1*X2"])


def test_optimal_selection_rejects_blocked_candidates_with_rank_reference():
    blocks = np.array([1, 2, 1, 2])
    coded = np.array([-1, -1, 1, 1])
    blocked_model = np.column_stack((np.ones(4), coded, blocks == 2))
    assert np.linalg.matrix_rank(blocked_model) == 3
    assert np.linalg.det(blocked_model.T @ blocked_model) == pytest.approx(16)
    assert all(np.linalg.matrix_rank(blocked_model[list(pair)]) < 3
               for pair in ((0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)))

    frame = pd.DataFrame({
        "运行ID": [f"C{i}" for i in range(4)], "标准序": range(1, 5),
        "运行序": range(1, 5), "点类型": ["factorial"] * 4,
        "重复": blocks, "区组": blocks, "X1": coded, "Y": [None] * 4,
    })
    column_map = {
        "run_id": "运行ID", "standard_order": "标准序", "run_order": "运行序",
        "point_type": "点类型", "replicate": "重复", "block": "区组",
        "factors": {"X1": "X1"}, "responses": {"Y": "Y"},
    }
    with pytest.raises(ValueError, match="带区组的候选工作表暂不支持最优设计"):
        optimal_from_candidates(
            frame, design_type="custom_factorial",
            factors=(FactorSpec("X1", "X1", -1, 1),), responses=("Y",),
            column_map=column_map, count=2)
    unblocked = frame.drop(columns=["区组"])
    unblocked_map = {**column_map, "block": None}
    with pytest.raises(ValueError, match="带区组的候选工作表暂不支持最优设计"):
        optimal_from_candidates(
            unblocked, design_type="custom_factorial",
            factors=(FactorSpec("X1", "X1", -1, 1),), responses=("Y",),
            column_map=unblocked_map, count=2, block_count=1)


def test_blocked_rsm_two_factor_model_requires_block_column():
    points = [(x, y, block) for block in (1, 2)
              for x, y in ((-1, -1), (-1, 1), (1, -1), (1, 1))]
    matrix = np.array([[1, x, y, int(block == 2)] for x, y, block in points])
    assert np.linalg.matrix_rank(matrix) == 4
    assert np.linalg.det(matrix.T @ matrix) == pytest.approx(1024)
    assert np.linalg.matrix_rank(matrix[:4]) == 3
    frame = pd.DataFrame({"运行ID": [f"R{i}" for i in range(8)],
                          "标准序": range(1, 9), "运行序": range(1, 9),
                          "点类型": ["factorial"] * 8, "重复": [1] * 8,
                          "B": [b for _, _, b in points],
                          "X1": [x for x, _, _ in points],
                          "X2": [y for _, y, _ in points], "Y": [None] * 8})
    mapping = {"run_id": "运行ID", "standard_order": "标准序", "run_order": "运行序",
               "point_type": "点类型", "replicate": "重复", "block": "B",
               "factors": {"X1": "X1", "X2": "X2"}, "responses": {"Y": "Y"}}
    for criterion in ("d_optimal", "distance"):
        with pytest.raises(ValueError, match="带区组"):
            optimal_from_candidates(
                frame, design_type="custom_rsm",
                factors=(FactorSpec("X1", "X1", -1, 1), FactorSpec("X2", "X2", -1, 1)),
                responses=("Y",), column_map=mapping, count=4,
                model_terms=("X1", "X2"), criterion=criterion, block_count=2)


def test_evaluate_compares_only_same_model_and_run_count():
    case = REFERENCE["rsm_candidates"]
    chosen = [case["candidates"][index] for index in case["expected"]["selected"]]
    summary = evaluate(chosen)
    assert summary["n"] == 6 and summary["p"] == 6
    assert summary["rank"] == 6 and not summary["singular"]
    assert np.isclose(summary["det_xtx"], float(case["expected"]["det_xtx"]),
                      rtol=1e-9)
    assert summary["min_squared_distance"] is not None
    # 不同运行数的评价只报告各自目标，不产生跨规模比较结论。
    smaller = evaluate(chosen[:4])
    assert smaller["n"] == 4 and smaller["p"] == 6
    assert smaller["singular"] is True
