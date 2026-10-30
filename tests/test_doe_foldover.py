import json
from itertools import product
from pathlib import Path

import pandas as pd
import numpy as np
import pytest

from doe_core import DesignSpec, FactorSpec, restore_design_result, worksheet_metadata
from doe_foldover import create_foldover, foldover_summary
from doe_fractional import create_fractional, validate_fractional_design


REFERENCE = json.loads((Path(__file__).parent / "fixtures" / "doe_factorial_reference"
                       / "reference.json").read_text(encoding="utf-8"))
FOLDOVER_REFERENCE = REFERENCE["foldover"]


def source_design(generators=("D=ABC",), *, seed=23, centers=0, replicates=1):
    spec = DesignSpec(
        "fold-source",
        tuple(FactorSpec(key, f"因子{key}", 0, 10) for key in "ABCD"),
        ("Y",), seed=seed, generators=generators,
        design_type="two_level_fractional",
    )
    frame, metadata = create_fractional(spec, replicates=replicates,
                                        center_points=centers, measured=True)
    frame["响应_Y"] = pd.array(range(1, len(frame) + 1), dtype="Float64")
    frame["实测_A"] = pd.array([float(i) for i in range(len(frame))], dtype="Float64")
    return frame, metadata


def coded_points(frame):
    return {tuple(1 if frame[f"设定_{key}"].iloc[row] == 10 else -1
                  for key in "ABCD") for row in range(len(frame))
            if frame["点类型"].iloc[row] == "factorial"}


def test_all_factor_foldover_preserves_source_and_truthfully_keeps_alias_rank():
    source, metadata = source_design()
    before = source.copy(deep=True)
    result, folded_metadata = create_foldover(source, metadata)
    repeated_result, _ = create_foldover(source, metadata)

    pd.testing.assert_frame_equal(source, before)
    pd.testing.assert_series_equal(result["运行ID"], repeated_result["运行ID"])
    pd.testing.assert_series_equal(result["运行序"], repeated_result["运行序"])
    assert len(result) == 16
    assert set(result["标准序"]) == set(range(1, 17))
    assert set(result["运行序"]) == set(range(1, 17))
    assert result["DOE 批次"].value_counts().to_dict() == {"BASE": 8, "FOLD1": 8}
    assert coded_points(result) == coded_points(source)
    source_response = dict(zip(source["运行ID"], source["响应_Y"]))
    base = result[result["DOE 批次"] == "BASE"]
    assert dict(zip(base["运行ID"], base["响应_Y"])) == source_response
    assert dict(zip(base["运行ID"], base["运行序"])) == dict(
        zip(source["运行ID"], source["运行序"]))
    added = result[result["DOE 批次"] == "FOLD1"]
    assert added["响应_Y"].isna().all() and added["实测_A"].isna().all()
    assert set(added["DOE 源运行ID"]) == set(source["运行ID"])

    summary = foldover_summary(result, folded_metadata)
    assert summary["resolution"] == 4
    assert summary["model_rank"] == 8
    original_summary = foldover_summary(source, metadata)
    assert summary["defining_relations"] == original_summary["defining_relations"]
    assert summary["alias_groups"] == original_summary["alias_groups"]
    lineage = folded_metadata["design"]["foldover_lineage"]
    assert lineage["parent_design_id"] == "fold-source"
    assert lineage["folded_factors"] == list("ABCD")
    assert len(lineage["run_map"]) == 8
    assert lineage["source_matrix_sha256"] != lineage["current_matrix_sha256"]
    validate_fractional_design(result, folded_metadata)


def test_single_factor_foldover_completes_full_factorial_and_updates_aliases():
    source, metadata = source_design()
    result, folded_metadata = create_foldover(source, metadata, "A")

    assert len(coded_points(result)) == 16
    summary = foldover_summary(result, folded_metadata)
    assert summary["resolution"] is None
    assert summary["defining_relations"] == ()
    assert summary["model_rank"] == 16
    assert summary["alias_groups"][0]["terms"] == ("截距",)
    assert all(len(group["terms"]) == 1 for group in summary["alias_groups"])
    assert folded_metadata["design"]["aliases"] == []


def test_multi_factor_foldover_flips_only_selected_factors_and_records_lineage():
    source, metadata = source_design()
    before = source.copy(deep=True)
    result, folded_metadata = create_foldover(source, metadata, ("A", "C"))
    columns = folded_metadata["column_map"]
    base = result[result[columns["batch_id"]] == "BASE"].set_index(columns["run_id"])
    added = result[result[columns["batch_id"]] == "FOLD1"].set_index(
        columns["source_run_id"])
    for run_id, original in base.iterrows():
        folded = added.loc[run_id]
        for factor_id, column in columns["factors"].items():
            expected = 10 - original[column] if factor_id in ("A", "C") else original[column]
            assert folded[column] == expected
        assert pd.isna(folded[columns["responses"]["Y"]])
    pd.testing.assert_frame_equal(source, before)
    lineage = folded_metadata["design"]["foldover_lineage"]
    assert lineage["folded_factors"] == ["A", "C"]
    assert folded_metadata["design"]["design_id"] != create_foldover(
        source, metadata, "A")[1]["design"]["design_id"]
    coded = np.column_stack([
        2 * result[columns["factors"][factor_id]].to_numpy(dtype=float) / 10 - 1
        for factor_id in ("A", "B", "C", "D")])
    matrix = np.column_stack([
        np.prod(coded[:, [index for index in range(4) if mask & (1 << index)]], axis=1)
        if mask else np.ones(len(coded))
        for mask in range(1 << 4)])
    assert foldover_summary(result, folded_metadata)["model_rank"] == \
        np.linalg.matrix_rank(matrix)


def test_foldover_matches_independent_fraction_reference():
    source, metadata = source_design()
    all_factor, all_metadata = create_foldover(source, metadata)
    single, single_metadata = create_foldover(source, metadata, "A")
    expected_parent = {tuple(row) for row in REFERENCE["regular_fraction"][
        "D=ABC"]["rows"]}
    assert coded_points(source) == expected_parent
    assert coded_points(all_factor) == expected_parent
    assert coded_points(single) == {
        tuple(row) for row in product((-1, 1), repeat=4)}
    all_summary = foldover_summary(all_factor, all_metadata)
    single_summary = foldover_summary(single, single_metadata)
    assert all_summary["defining_relations"] == tuple(
        FOLDOVER_REFERENCE["all_factor_expected"]["defining_relations"])
    assert all_summary["resolution"] == FOLDOVER_REFERENCE["all_factor_expected"]["resolution"]
    assert all_summary["model_rank"] == FOLDOVER_REFERENCE["all_factor_expected"]["model_rank"]
    assert single_summary["defining_relations"] == tuple(
        FOLDOVER_REFERENCE["single_A_expected"]["defining_relations"])
    assert single_summary["resolution"] == FOLDOVER_REFERENCE["single_A_expected"]["resolution"]
    assert single_summary["model_rank"] == FOLDOVER_REFERENCE["single_A_expected"]["model_rank"]
    aliases = [group["label"].replace(" = ", "=").replace("*", "")
               for group in all_summary["alias_groups"] if "截距" not in group["terms"]]
    assert aliases == FOLDOVER_REFERENCE["all_factor_expected"]["alias_groups"]


def test_center_points_remain_in_base_batch_and_are_not_duplicated():
    source, metadata = source_design(centers=2)
    result, folded_metadata = create_foldover(source, metadata, "A")

    assert len(result) == 18
    assert result["点类型"].value_counts().to_dict() == {
        "factorial": 16, "center": 2}
    assert result.loc[result["点类型"] == "center", "DOE 批次"].tolist() == ["BASE", "BASE"]
    assert folded_metadata["design"]["center_point_count"] == 2
    assert len(folded_metadata["design"]["foldover_lineage"]["run_map"]) == 8
    validate_fractional_design(result, folded_metadata)


def test_foldover_keeps_existing_user_columns_and_uses_unique_lineage_columns():
    source, metadata = source_design()
    source["DOE 批次"] = "用户数据"
    source["DOE 源运行ID"] = "用户来源"
    metadata = worksheet_metadata(
        source, DesignSpec.from_dict(metadata["design"]), metadata["column_map"])

    result, folded_metadata = create_foldover(source, metadata, "A")
    original = result[result["DOE 批次"] == "用户数据"]
    added = result[result["DOE 批次 (2)"] == "FOLD1"]
    assert set(original["DOE 批次"]) == {"用户数据"}
    assert set(original["DOE 源运行ID"]) == {"用户来源"}
    assert added["DOE 批次"].isna().all()
    assert added["DOE 源运行ID"].isna().all()
    assert result["DOE 批次 (2)"].value_counts().to_dict() == {"BASE": 8, "FOLD1": 8}
    assert folded_metadata["column_map"]["batch_id"] == "DOE 批次 (2)"


@pytest.mark.parametrize("folded", [(), "Z", ["A", "A"], ["A", []]])
def test_unsupported_foldover_factor_selections_fail_without_mutating_source(folded):
    source, metadata = source_design()
    before = source.copy(deep=True)
    with pytest.raises(ValueError):
        create_foldover(source, metadata, folded)
    pd.testing.assert_frame_equal(source, before)


def test_repeat_foldover_and_run_limit_are_rejected():
    source, metadata = source_design()
    folded, folded_metadata = create_foldover(source, metadata, "A")
    with pytest.raises(ValueError, match="再次折叠"):
        create_foldover(folded, folded_metadata, "B")

    large, large_metadata = source_design(replicates=1000)
    with pytest.raises(ValueError, match="10000"):
        create_foldover(large, large_metadata, "A")


def test_foldover_matrix_tampering_is_rejected_on_restore():
    frame, metadata = create_foldover(*source_design(), folded_factors="A")
    tampered = frame.copy(deep=True)
    row = tampered.index[tampered["DOE 批次"] == "FOLD1"][0]
    tampered.at[row, "设定_B"] = 10 if tampered.at[row, "设定_B"] == 0 else 0
    with pytest.raises(ValueError, match="Foldover"):
        restore_design_result(tampered, metadata)


def test_signed_fraction_foldover_updates_actual_definition_sign():
    source, metadata = source_design(("D=-ABC",))
    all_factor, all_metadata = create_foldover(source, metadata)
    assert foldover_summary(all_factor, all_metadata)["defining_relations"] == ("I=-ABCD",)
    single, single_metadata = create_foldover(source, metadata, "A")
    assert foldover_summary(single, single_metadata)["defining_relations"] == ()
