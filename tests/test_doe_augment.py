import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from doe_augment import augment, select_augment
from doe_core import DesignSpec, FactorSpec, restore_design_result, worksheet_metadata
from doe_custom import define_custom


REFERENCE = json.loads((Path(__file__).parent / "fixtures" / "doe_optimal_reference"
                        / "reference.json").read_text(encoding="utf-8"))


def base_design():
    frame = pd.DataFrame({
        "运行ID": ["R1", "R2", "R3", "R4"],
        "标准序": [1, 2, 3, 4],
        "运行序": [1, 2, 3, 4],
        "点类型": ["factorial"] * 4,
        "重复": [1] * 4,
        "批次": ["BASE"] * 4,
        "来源": [None] * 4,
        "A": [1, 1, -1, -1],
        "B": [1, -1, 1, -1],
        "Y": [10.0, 12.0, 14.0, 16.0],
    })
    factors = (FactorSpec("A", "A", -1, 1), FactorSpec("B", "B", -1, 1))
    mapping = _mapping()
    spec = DesignSpec("aug-parent", factors, ("Y",), seed=1,
                      design_type="custom_factorial")
    metadata = worksheet_metadata(frame, spec, mapping)
    return frame, metadata


def _mapping():
    return {"run_id": "运行ID", "standard_order": "标准序", "run_order": "运行序",
            "point_type": "点类型", "replicate": "重复", "block": None,
            "batch_id": "批次", "source_run_id": "来源",
            "factors": {"A": "A", "B": "B"}, "responses": {"Y": "Y"}}


def test_select_augment_matches_independent_reference():
    case = REFERENCE["augment_initial"]
    initial = [[1, row[1], row[2], row[1] ** 2, row[2] ** 2, row[1] * row[2]]
               for row in case["initial"]]
    candidates = [[1, row[1], row[2], row[1] ** 2, row[2] ** 2, row[1] * row[2]]
                  for row in case["candidates"]]
    result = select_augment(initial, candidates, case["select"])
    assert list(result["indices"]) == case["expected"]["selected"]
    assert result["initial_rank"] == case["expected"]["initial_rank"]
    assert result["augmented_rank"] == case["expected"]["augmented_rank"] == 6
    assert np.isclose(np.exp(result["logdet"]),
                      float(case["expected"]["det_xtx"]), rtol=1e-9)


def test_augment_preserves_parent_responses_and_lineage():
    frame, metadata = base_design()
    result, result_metadata, summary = augment(
        frame, metadata, [{"A": 0, "B": 0}], 1, batch_id="AUG1",
        point_types=["center"])
    design = restore_design_result(result, result_metadata)
    assert len(result) == len(frame) + 1
    assert design.spec.augmentation_lineage is not None
    assert design.spec.augmentation_lineage["parent_design_id"] == "aug-parent"
    assert design.spec.augmentation_lineage["batch_id"] == "AUG1"
    added = result[result["批次"] == "AUG1"]
    assert len(added) == 1
    assert added["Y"].isna().all()
    assert result[result["批次"] == "BASE"]["Y"].tolist() == [10.0, 12.0, 14.0, 16.0]
    assert summary["initial_rank"] == 3
    assert summary["augmented_rank"] == 3
    assert summary["parent_design_id"] == "aug-parent"
    assert sorted(result["标准序"]) == list(range(1, len(result) + 1))


def test_augment_rejects_run_id_conflict_and_missing_batch_columns():
    frame, metadata = base_design()
    candidates = [{"A": 0, "B": 0}, {"A": 0.5, "B": 0}]
    with pytest.raises(ValueError, match="冲突"):
        augment(frame, metadata, candidates, 1, run_ids=["R1"])
    broken = dict(metadata)
    broken["column_map"] = {key: value for key, value in
                            metadata["column_map"].items()
                            if key not in ("batch_id", "source_run_id")}
    with pytest.raises(ValueError, match="映射|批次"):
        augment(frame, broken, candidates, 1)


def test_augment_rejects_invalid_candidate_and_cancel_keeps_source():
    frame, metadata = base_design()
    original = frame.copy(deep=True)
    with pytest.raises(ValueError, match="覆盖全部因子"):
        augment(frame, metadata, [{"A": 0}], 1)
    with pytest.raises(ValueError, match="Distance"):
        augment(frame, metadata, [{"A": 0, "B": 0}], 1, criterion="distance")
    with pytest.raises(ValueError, match="正整数"):
        augment(frame, metadata, [{"A": 0, "B": 0}], 0)
    pd.testing.assert_frame_equal(frame, original)


def test_augment_select_is_deterministic_and_reports_rank():
    initial = [[1, 1, 1], [1, 1, -1], [1, -1, 1], [1, -1, -1]]
    candidates = [[1, 0, 0], [1, 1.5, 0], [1, 0, 1.5]]
    first = select_augment(initial, candidates, 1)
    second = select_augment(initial, candidates, 1)
    assert first["indices"] == second["indices"]
    assert first["initial_rank"] == 3
    assert first["augmented_rank"] == 3
    assert first["logdet"] is not None


def test_augment_rejects_existing_design_point_as_new_run():
    frame, metadata = base_design()
    with pytest.raises(ValueError, match="重复"):
        augment(frame, metadata, [{"A": 1, "B": 1}], 1)


def test_augment_rejects_stale_parent_rows_and_run_ids():
    frame, metadata = base_design()
    candidates = [{"A": 0, "B": 0}]
    # 行内容改变：映射仍存在但输入摘要已失效，必须拒绝而不是用旧摘要增补。
    changed = frame.copy(deep=True)
    changed.loc[0, "A"] = -1.0
    with pytest.raises(ValueError):
        augment(changed, metadata, candidates, 1)
    # 行顺序调换：run_id 到行位置的映射失效。
    swapped = frame.iloc[[1, 0, 2, 3]].reset_index(drop=True)
    with pytest.raises(ValueError, match="映射|变化"):
        augment(swapped, metadata, candidates, 1)
    # run_id 被改写：同样使映射失效。
    renamed = frame.copy(deep=True)
    renamed.loc[0, "运行ID"] = "R9"
    with pytest.raises(ValueError, match="映射|变化"):
        augment(renamed, metadata, candidates, 1)
    # 父来源工作表被删除后只剩空表：不能凭空增补。
    with pytest.raises(ValueError, match="行数|映射|变化"):
        augment(frame.iloc[0:0].copy(), metadata, candidates, 1)


def test_augment_rejects_run_total_over_limit():
    frame, metadata = base_design()
    import doe_augment as module
    assert module._MAX_RUNS == 10000
    # 用恰好超过上限的请求验证拒绝发生在写入之前，来源表保持原样。
    original = frame.copy(deep=True)
    with pytest.raises(ValueError, match="10000"):
        augment(frame, metadata, [{"A": 0, "B": 0}], module._MAX_RUNS)
    pd.testing.assert_frame_equal(frame, original)


def test_select_augment_budget_uses_combination_count_not_row_count():
    import doe_augment as module

    initial = [[1, 1, 1], [1, 1, -1]]
    candidates = [[1, index / 10, (index % 5) / 10] for index in range(30)]
    # 30 选 15 = 155117520 个子集；必须降级而不是穷举。
    result = select_augment(initial, candidates, 15)
    assert result["subsets"] == 155_117_520
    assert result["method"] == "greedy_exchange"
    assert result["global_optimum_proven"] is False
    assert result["evaluations"] < 30_000
    assert "超过预算" in result["stop_reason"]
    assert len(set(result["selection_order"])) == 15
    # 30 选 2 = 435 仍在预算内，继续穷举并声明全局最优。
    small = select_augment(initial, candidates, 2)
    assert small["method"] == "exact_enumeration"
    assert small["global_optimum_proven"] is True
    assert small["exact_budget"] == module._MAX_EXACT_SUBSETS


def rsm_parent():
    """2^2 因子点 + 1 中心点；完整二次模型初始秩 5/6，需轴点补满。"""
    frame = pd.DataFrame({
        "运行ID": ["R1", "R2", "R3", "R4", "R5"],
        "标准序": [1, 2, 3, 4, 5], "运行序": [1, 2, 3, 4, 5],
        "点类型": ["factorial"] * 4 + ["center"], "重复": [1] * 5,
        "批次": ["BASE"] * 5, "来源": [None] * 5,
        "X1": [1, -1, 1, -1, 0], "X2": [1, 1, -1, -1, 0],
        "Y": [10.0, 12.0, 14.0, 16.0, 13.0],
    })
    spec = DesignSpec(
        "rsm-parent", (FactorSpec("X1", "X1", -1, 1),
                        FactorSpec("X2", "X2", -1, 1)),
        ("Y",), design_type="custom_rsm", schema_version=5,
        model_terms=("X1", "X2", "X1²", "X2²", "X1*X2"))
    mapping = {"run_id": "运行ID", "standard_order": "标准序",
               "run_order": "运行序", "point_type": "点类型",
               "replicate": "重复", "block": None, "batch_id": "批次",
               "source_run_id": "来源",
               "factors": {"X1": "X1", "X2": "X2"}, "responses": {"Y": "Y"}}
    return frame, worksheet_metadata(frame, spec, mapping)


def test_augment_keeps_parent_runs_fixed_and_never_swaps_them():
    frame, metadata = rsm_parent()
    candidates = [{"X1": 1.7, "X2": 0}, {"X1": -1.7, "X2": 0},
                  {"X1": 0, "X2": 1.7}]
    result, result_metadata, summary = augment(
        frame, metadata, candidates, 2, criterion="d_optimal",
        point_types=["axial"] * 3)
    assert summary["initial_rank"] == 5
    base = result[result["批次"] == "BASE"]
    assert base["运行ID"].tolist() == frame["运行ID"].tolist()
    assert base["Y"].tolist() == [10.0, 12.0, 14.0, 16.0, 13.0]
    assert restore_design_result(result, result_metadata).spec.augmentation_lineage


def test_augment_manual_criterion_uses_given_order_not_d_optimal():
    frame, metadata = rsm_parent()
    # 手动保留前两个轴点：D-optimal 会为行列式另选组合，manual 必须按输入顺序。
    candidates = [{"X1": 0, "X2": 1.7}, {"X1": 0, "X2": -1.7},
                  {"X1": 1.7, "X2": 0}, {"X1": -1.7, "X2": 0}]
    result, result_metadata, summary = augment(
        frame, metadata, candidates, 2, criterion="manual", batch_id="MAN1",
        point_types=["axial"] * 4)
    assert summary["method"] == "manual"
    assert list(summary["selection_order"]) == [0, 1]
    assert summary["global_optimum_proven"] is False
    added = result[result["批次"] == "MAN1"]
    assert added["X1"].tolist() == [0.0, 0.0]
    assert added["X2"].tolist() == [1.7, -1.7]
    lineage = restore_design_result(result, result_metadata).spec.augmentation_lineage
    assert lineage["criterion"] == "manual"


def test_augment_accepts_rank_deficient_parent_when_target_becomes_full_rank():
    frame, metadata = base_design()
    short = frame.iloc[0:3].copy().reset_index(drop=True)
    spec = DesignSpec("aug-short", (FactorSpec("A", "A", -1, 1),
                                   FactorSpec("B", "B", -1, 1)),
                      ("Y",), seed=1, design_type="custom_factorial")
    short_metadata = worksheet_metadata(short, spec, _mapping())
    result, result_metadata, summary = augment(
        short, short_metadata, [{"A": -1, "B": -1}], 1)
    # 父设计秩亏时先如实报告初始秩，再核对增补后是否满秩。
    assert summary["initial_rank"] == 3 == summary["p"]
    assert summary["augmented_rank"] == summary["p"]
    assert summary["rank_improved"] is False
    assert restore_design_result(result, result_metadata).spec.design_id.startswith("aug-")
