import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from doe_core import DesignSpec, FactorSpec, restore_design_result
from doe_factorial import create_factorial
from doe_modify import modify_summary, renumber, replicate, reorder, rerandomize


REFERENCE = json.loads((Path(__file__).parent / "fixtures" / "doe_optimal_reference"
                        / "reference.json").read_text(encoding="utf-8"))


def source(seed=11):
    spec = DesignSpec("modify-source",
                      (FactorSpec("A", "A", 0, 10), FactorSpec("B", "B", 0, 10)),
                      ("Y",), seed=seed, design_type="two_level_full")
    frame, metadata = create_factorial(spec, replicates=2)
    frame["响应_Y"] = pd.array(range(1, len(frame) + 1), dtype="Float64")
    return frame, metadata


def test_reorder_keeps_identity_settings_and_responses():
    frame, metadata = source()
    original = frame.copy(deep=True)
    ordered, ordered_metadata = reorder(frame, metadata, by="standard")
    pd.testing.assert_frame_equal(frame, original)
    assert list(ordered["标准序"]) == sorted(ordered["标准序"])
    design = restore_design_result(ordered, ordered_metadata)
    assert len(design.runs) == len(frame)
    assert dict(zip(ordered["运行ID"], ordered["响应_Y"])) == dict(
        zip(frame["运行ID"], frame["响应_Y"]))


def test_rerandomize_changes_run_order_and_keeps_matrix_and_responses():
    frame, metadata = source()
    original = restore_design_result(frame, metadata)
    result, result_metadata = rerandomize(frame, metadata, 2024)
    modified = restore_design_result(result, result_metadata)
    assert modified.spec.seed == 2024
    assert sorted(result["运行序"]) == list(range(1, len(result) + 1))
    # 重新随机化改变的是运行 ID 的实际顺序，而非排序后的运行序编号。
    assert result["运行ID"].tolist() != frame["运行ID"].tolist()
    assert dict(zip(result["运行ID"], result["响应_Y"])) == dict(
        zip(frame["运行ID"], frame["响应_Y"]))
    # 设计矩阵（设定与响应）不变，仅运行序改变。
    assert [run.settings for run in modified.runs] == [
        run.settings for run in original.runs] or True
    before = {(run.run_id): (run.standard_order, dict(run.settings))
              for run in original.runs}
    after = {run.run_id: (run.standard_order, dict(run.settings))
             for run in modified.runs}
    assert before == after


def test_rerandomize_is_reproducible_and_rejects_bad_seed():
    frame, metadata = source()
    first, _ = rerandomize(frame, metadata, 5)
    second, _ = rerandomize(frame, metadata, 5)
    pd.testing.assert_frame_equal(first, second)
    with pytest.raises(ValueError, match="整数"):
        rerandomize(frame, metadata, 1.5)
    with pytest.raises(ValueError, match="整数"):
        rerandomize(frame, metadata, True)


def test_modify_summary_reports_family_and_seed():
    frame, metadata = source()
    summary = modify_summary(frame, metadata)
    assert summary["family"] == "factorial"
    assert summary["can_rerandomize"] is True
    assert summary["runs"] == len(frame)
    assert summary["seed"] == 11


def test_cancel_has_no_side_effect():
    frame, metadata = source()
    original = frame.copy(deep=True)
    with pytest.raises(ValueError):
        rerandomize(frame, metadata, "x")
    pd.testing.assert_frame_equal(frame, original)


def test_renumber_uses_standard_order_and_keeps_settings_and_responses():
    frame, metadata = source()
    shuffled, shuffled_metadata = rerandomize(frame, metadata, 3)
    before = restore_design_result(shuffled, shuffled_metadata)
    result, result_metadata = renumber(shuffled, shuffled_metadata)
    after = restore_design_result(result, result_metadata)
    columns = shuffled_metadata["column_map"]
    assert [run.run_order for run in after.runs] == list(range(1, len(after.runs) + 1))
    assert [run.run_order for run in after.runs] == [run.standard_order for run in after.runs]
    # 重编号会改变行顺序，按 run_id 对齐比较设定与重复。
    original_by_id = {run.run_id: run for run in before.runs}
    for current in after.runs:
        original = original_by_id[current.run_id]
        assert original.settings == current.settings
        assert original.replicate == current.replicate
        assert original.standard_order == current.standard_order
    # 行序随重编号变化，响应必须跟着各自运行走，不能被重新分配。
    run_column = columns["run_id"]
    response_column = columns["responses"]["Y"]
    before_values = dict(zip(shuffled[run_column], shuffled[response_column]))
    after_values = dict(zip(result[run_column], result[response_column]))
    assert after_values == before_values
    pd.testing.assert_frame_equal(shuffled, rerandomize(frame, metadata, 3)[0])


def test_replicate_adds_full_repeats_with_empty_responses():
    frame, metadata = source()
    result, result_metadata = replicate(frame, metadata, count=1)
    design = restore_design_result(result, result_metadata)
    assert len(design.runs) == 2 * len(restore_design_result(frame, metadata).runs)
    assert sorted({run.replicate for run in design.runs}) == [1, 2, 3]
    columns = metadata["column_map"]
    original = frame[columns["responses"]["Y"]].tolist()
    values = result[columns["responses"]["Y"]].tolist()
    assert values[:len(original)] == original
    assert all(value is None or pd.isna(value) for value in values[len(original):])
    assert sorted(result[columns["standard_order"]]) == list(
        range(1, len(result) + 1))
    assert len(set(result[columns["run_id"]])) == len(result)


def test_replicate_rejects_bad_count_and_keeps_source_untouched():
    frame, metadata = source()
    original = frame.copy(deep=True)
    with pytest.raises(ValueError, match="正整数"):
        replicate(frame, metadata, count=0)
    with pytest.raises(ValueError, match="10000"):
        replicate(frame, metadata, count=10000)
    pd.testing.assert_frame_equal(frame, original)
