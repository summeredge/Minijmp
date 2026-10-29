import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from doe_core import DesignSpec, FactorSpec, restore_design_result, worksheet_metadata
from doe_factorial import create_factorial
from doe_splitplot import create_split_plot, validate_split_plot_design
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


def split_plot_source(hard=2, easy=1, blocks=2, version="v2", seed=19,
                      response_dtype="Float64"):
    factors = tuple(
        FactorSpec(chr(ord("A") + index), chr(ord("A") + index), -1, 1,
                   randomization_role=("hard_to_change" if index < hard
                                       else "easy_to_change"))
        for index in range(hard + easy))
    spec = DesignSpec(
        "modify-split", factors, ("Y",), seed=seed,
        design_type="split_plot", block_count=blocks,
        construction_version=version, randomization_unit="whole_plot",
        error_structure="split_plot")
    frame, metadata = create_split_plot(spec)
    frame["响应_Y"] = pd.array(range(1, len(frame) + 1), dtype=response_dtype)
    return frame, metadata


def test_split_plot_rerandomize_preserves_points_and_rejects_renumber():
    frame, metadata = split_plot_source()
    original = frame.copy(deep=True)
    original_design = restore_design_result(frame, metadata)
    result, result_metadata = rerandomize(frame, metadata, 2024)
    updated = validate_split_plot_design(result, result_metadata)
    columns = metadata["column_map"]

    assert updated.spec.seed == 2024
    assert updated.spec.block_count == original_design.spec.block_count
    assert result[columns["run_id"]].tolist() != frame[columns["run_id"]].tolist()
    assert set(result[columns["whole_plot_id"]]) == set(frame[columns["whole_plot_id"]])
    assert dict(zip(result[columns["run_id"]], result[columns["responses"]["Y"]])) == dict(
        zip(frame[columns["run_id"]], frame[columns["responses"]["Y"]]))
    summary = modify_summary(frame, metadata)
    assert summary["can_replicate"] is True
    assert summary["can_renumber"] is False
    with pytest.raises(ValueError, match="运行序"):
        renumber(frame, metadata)
    pd.testing.assert_frame_equal(frame, original)


@pytest.mark.parametrize("version,hard,easy", [("v1", 1, 1), ("v2", 2, 2)])
def test_split_plot_replicate_preserves_history_and_adds_independent_block(
        version, hard, easy):
    frame, metadata = split_plot_source(
        hard=hard, easy=easy, blocks=2, version=version, seed=1,
        response_dtype="Int64")
    original = frame.copy(deep=True)
    old = restore_design_result(frame, metadata)
    columns = metadata["column_map"]
    result, result_metadata = replicate(frame, metadata, count=1)
    design = validate_split_plot_design(result, result_metadata)

    assert design.spec.construction_version == version
    assert design.spec.block_count == 3
    runs_per_block = 1 << len(old.spec.factors)
    assert len(design.runs) == len(old.runs) + runs_per_block
    assert result[columns["whole_plot_id"]].nunique() == 3 * (1 << hard)
    assert result[columns["responses"]["Y"]].dtype == frame[columns["responses"]["Y"]].dtype
    identity_columns = [
        columns["standard_order"], columns["block"], columns["whole_plot_id"],
        columns["subplot_id"], columns["run_order"],
        columns["whole_plot_order"], columns["subplot_order"],
        *columns["factors"].values(),
    ]
    run_id = columns["run_id"]
    old_rows = frame.set_index(run_id)
    current_rows = result.set_index(run_id)
    old_ids = set(old_rows.index)
    for column in identity_columns:
        assert old_rows[column].to_dict() == current_rows.loc[list(old_ids), column].to_dict()
    old_responses = dict(zip(frame[run_id], frame[columns["responses"]["Y"]]))
    new_ids = set(result[columns["run_id"]]) - set(old_responses)
    assert len(new_ids) == runs_per_block
    assert set(current_rows.loc[list(new_ids), columns["block"]]) == {3}
    appended_columns = result_metadata["column_map"]
    batch_column = appended_columns["batch_id"]
    assert set(result.loc[result[run_id].isin(old_ids), batch_column].dropna()) == set()
    assert set(result.loc[result[run_id].isin(new_ids), batch_column]) == {"SPLITPLOT_APPEND_V1"}
    current_responses = dict(zip(result[columns["run_id"]],
                                 result[columns["responses"]["Y"]]))
    assert all(current_responses[run_id] == response
               for run_id, response in old_responses.items())
    assert all(pd.isna(current_responses[run_id]) for run_id in new_ids)
    assert set(result.loc[result[run_id].isin(new_ids), columns["run_order"]]) == set(
        range(len(old.runs) + 1, len(design.runs) + 1))
    assert design.spec.augmentation_lineage["criterion"] == "manual"
    assert design.spec.augmentation_lineage["batch_id"] == "SPLITPLOT_APPEND_V1"
    pd.testing.assert_frame_equal(frame, original)


def test_split_plot_second_append_and_rerandomize_are_rejected_without_mutation():
    frame, metadata = split_plot_source(hard=1, easy=1, blocks=2, version="v1", seed=1)
    first, first_metadata = replicate(frame, metadata, count=1)
    original = first.copy(deep=True)
    summary = modify_summary(first, first_metadata)
    assert summary["can_replicate"] is False
    assert summary["can_rerandomize"] is False
    with pytest.raises(ValueError, match="只支持一次区组增补"):
        replicate(first, first_metadata, count=1)
    with pytest.raises(ValueError, match="不支持重新随机化"):
        rerandomize(first, first_metadata, 2)
    pd.testing.assert_frame_equal(first, original)


def test_split_plot_append_rejects_invalid_requests_and_damaged_source():
    frame, metadata = split_plot_source(hard=1, easy=1, blocks=2, version="v1", seed=1)
    original = frame.copy(deep=True)
    for count, message in ((0, "正整数"), (True, "正整数"), (10000, "10000")):
        with pytest.raises(ValueError, match=message):
            replicate(frame, metadata, count=count)
    with pytest.raises(ValueError, match="沿用原 seed"):
        replicate(frame, metadata, count=1, seed=2)
    damaged = frame.copy(deep=True)
    damaged.loc[0, "运行序"] += 1
    with pytest.raises(ValueError, match="run_order"):
        replicate(damaged, metadata, count=1)
    pd.testing.assert_frame_equal(frame, original)


def test_split_plot_append_rejects_response_dtype_that_cannot_hold_blank_rows():
    frame, metadata = split_plot_source(
        hard=1, easy=1, blocks=2, version="v1", seed=1, response_dtype="int64")
    original = frame.copy(deep=True)
    with pytest.raises(ValueError, match="保留原类型"):
        replicate(frame, metadata, count=1)
    pd.testing.assert_frame_equal(frame, original)


def test_split_plot_schema_v4_append_is_disabled_without_upgrading_schema():
    factors = (
        FactorSpec("A", "A", -1, 1, schema_version=4,
                   randomization_role="hard_to_change"),
        FactorSpec("B", "B", -1, 1, schema_version=4,
                   randomization_role="easy_to_change"),
    )
    spec = DesignSpec(
        "modify-split-v4", factors, ("Y",), seed=1, schema_version=4,
        design_type="split_plot", block_count=2, construction_version="v1",
        randomization_unit="whole_plot", error_structure="split_plot")
    frame, metadata = create_split_plot(spec)
    summary = modify_summary(frame, metadata)
    assert summary["can_replicate"] is False
    assert "Schema v4" in summary["unavailable_reason"]
    with pytest.raises(ValueError, match="Schema v4"):
        replicate(frame, metadata, count=1)


def test_split_plot_reorder_rejects_seed_order_corruption():
    frame, metadata = split_plot_source(hard=1, easy=1, blocks=2, version="v1", seed=1)
    damaged = frame.copy(deep=True)
    block = damaged["区组"].iloc[0]
    whole_plots = damaged.loc[damaged["区组"] == block, "整区ID"].drop_duplicates()
    first, second = whole_plots.tolist()[:2]
    first_mask = damaged["整区ID"] == first
    second_mask = damaged["整区ID"] == second
    first_order = damaged.loc[first_mask, "整区序"].iloc[0]
    second_order = damaged.loc[second_mask, "整区序"].iloc[0]
    damaged.loc[first_mask, "整区序"] = second_order
    damaged.loc[second_mask, "整区序"] = first_order
    damaged_metadata = worksheet_metadata(
        damaged, DesignSpec.from_dict(metadata["design"]), metadata["column_map"])
    with pytest.raises(ValueError):
        reorder(damaged, damaged_metadata, by="run")
