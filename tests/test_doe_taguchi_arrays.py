"""Taguchi 数组目录、设计网格与 Schema v5 合同。"""
import copy

import pytest

from doe_core import DOE_SCHEMA_VERSION, DesignSpec, FactorSpec, restore_design_result
from doe_taguchi import create_taguchi
from doe_taguchi_arrays import ARRAYS, column_counts, pair_counts, validate_array


def factor(factor_id, levels, numeric=False):
    return FactorSpec(factor_id, factor_id, None, None, factor_type="categorical",
                      levels=tuple(levels),
                      level_type="numeric" if numeric else "text")


def static_spec(array_id="L9(3^4)", columns=None, kind="static", extra=()):
    array = ARRAYS[array_id]
    levels = [tuple(f"x{index}" for index in range(1, count + 1))
              for count in array.levels]
    factors = [factor(chr(65 + index), value) for index, value in enumerate(levels)]
    factors.extend(extra)
    mapping = columns or {item.factor_id: index + 1
                          for index, item in enumerate(factors)}
    return DesignSpec("TG", tuple(factors), ("Y",), seed=11, design_type="taguchi",
                      taguchi={"kind": kind, "array_id": array_id,
                               "matrix_sha256": array.sha256, "columns": mapping,
                               "noise_array_id": None, "noise_matrix_sha256": None,
                               "noise_columns": {}, "signal_factor": None})


def l18_spec(columns):
    array = ARRAYS["L18(2^1 3^7)"]
    factors = tuple(
        factor(factor_id, tuple(f"{factor_id}{level}"
                                for level in range(1, array.levels[column - 1] + 1)))
        for factor_id, column in columns.items())
    return DesignSpec(
        "TG", factors, ("Y",), seed=2,
        design_type="taguchi",
        taguchi={"kind": "static", "array_id": array.array_id,
                 "matrix_sha256": array.sha256, "columns": columns,
                 "noise_array_id": None, "noise_matrix_sha256": None,
                 "noise_columns": {}, "signal_factor": None})


def test_schema_version_is_five_and_arrays_match_reference_hashes():
    assert DOE_SCHEMA_VERSION == 5
    assert {case["array_id"]: case["sha256"]
            for case in __import__("json").loads(
                (__import__("pathlib").Path(__file__).parent / "fixtures"
                 / "doe_taguchi_reference" / "manifest.json").read_text(encoding="utf-8")
            )["fixtures"]} == {key: value.sha256 for key, value in ARRAYS.items()}


@pytest.mark.parametrize("array_id", sorted(ARRAYS))
def test_every_catalogued_array_passes_balance_and_pair_audit(array_id):
    audit = validate_array(ARRAYS[array_id])
    assert audit["run_count"] == ARRAYS[array_id].run_count
    assert audit["unbalanced_pairs"] == list(ARRAYS[array_id].documented_unbalanced_pairs)


def test_l18_unbalanced_pairs_are_recorded_not_silently_claimed_orthogonal():
    array = ARRAYS["L18(2^1 3^7)"]
    assert array.documented_unbalanced_pairs == ((3, 8), (4, 8), (5, 8), (6, 8), (7, 8))
    assert set(pair_counts(array, 3, 8).values()) != {2}
    assert set(pair_counts(array, 1, 8).values()) == {3}


def test_l18_balanced_control_columns_including_official_column_nine_remain_usable():
    array = ARRAYS["L18(2^1 3^7)"]
    spec = DesignSpec(
        "TG", (factor("A", ("低", "高")),
               factor("B", ("b1", "b2", "b3")),
               factor("C", ("c1", "c2", "c3"))), ("Y",), seed=2,
        design_type="taguchi",
        taguchi={"kind": "static", "array_id": array.array_id,
                 "matrix_sha256": array.sha256,
                 "columns": {"A": 1, "B": 2, "C": 8},
                 "noise_array_id": None, "noise_matrix_sha256": None,
                 "noise_columns": {}, "signal_factor": None})
    frame, metadata = create_taguchi(spec, replicates=2)
    assert len(restore_design_result(frame, metadata).runs) == 36
    assert {run.settings["C"] for run in restore_design_result(
        frame, metadata).runs} == {"c1", "c2", "c3"}
    assert array.sha256 == "767f1ad05d8f96ba082346c8bd4c06bad848e7e82a88438d1756f6d6c3b99a76"


def test_l18_nonorthogonal_control_pair_is_rejected_at_core_construction():
    with pytest.raises(ValueError, match="3/8.*不满足两两正交"):
        l18_spec({"A": 1, "B": 2, "C": 3, "D": 8})


def test_l18_nonorthogonal_noise_pair_is_rejected_at_core_construction():
    array = ARRAYS["L18(2^1 3^7)"]
    factors = (factor("A", ("低", "高")), factor("B", ("b1", "b2", "b3")),
               factor("C", ("c1", "c2", "c3")),
               factor("D", ("d1", "d2", "d3")),
               factor("E", ("e1", "e2", "e3")))
    with pytest.raises(ValueError, match="噪声列组合 3/8.*不满足两两正交"):
        DesignSpec(
            "TG", factors, ("Y",), seed=5, design_type="taguchi",
            taguchi={"kind": "static", "array_id": array.array_id,
                     "matrix_sha256": array.sha256,
                     "columns": {"A": 1, "B": 2, "C": 8},
                     "noise_array_id": array.array_id,
                     "noise_matrix_sha256": array.sha256,
                     "noise_columns": {"D": 3, "E": 8},
                     "signal_factor": None})


def test_l18_bad_pair_cannot_be_restored_or_analyzed_from_tampered_metadata():
    from copy import deepcopy
    from doe_taguchi_sn import analyze_static

    frame, metadata = create_taguchi(
        l18_spec({"A": 1, "B": 2, "C": 3, "D": 4}), replicates=2)
    frame["响应_Y"] = [float(index % 5 + 1) for index in range(len(frame))]
    broken = deepcopy(metadata)
    broken["design"]["taguchi"]["columns"]["D"] = 8
    with pytest.raises(ValueError, match="3/8.*不满足两两正交"):
        restore_design_result(frame, broken)
    with pytest.raises(ValueError, match="3/8.*不满足两两正交"):
        analyze_static(frame, broken, "Y", "smaller")


@pytest.mark.parametrize("levels", [2, 3, 4, 5])
def test_column_counts_are_balanced_for_every_level_count(levels):
    for array in ARRAYS.values():
        for column, counts in column_counts(array).items():
            if array.levels[column - 1] == levels:
                assert set(counts.values()) == {array.run_count // levels}


@pytest.mark.parametrize("array_id, capacity", [("L4(2^3)", 3), ("L8(2^7)", 7),
                                                ("L9(3^4)", 4), ("L16(4^5)", 5),
                                                ("L18(2^1 3^7)", 8), ("L25(5^6)", 6)])
def test_array_capacity_and_duplicate_columns(array_id, capacity):
    array = ARRAYS[array_id]
    assert array.factor_capacity == capacity
    assert array.columns_for(2) == tuple(index + 1 for index, value
                                         in enumerate(array.levels) if value == 2)
    with pytest.raises(ValueError):
        pair_counts(array, 1, 1)
    with pytest.raises(ValueError):
        pair_counts(array, 1, capacity + 1)


def test_static_design_generates_full_grid_and_roundtrips():
    spec = static_spec()
    frame, metadata = create_taguchi(spec, replicates=2)
    assert metadata["schema_version"] == 5
    assert len(frame) == 18
    result = restore_design_result(frame, metadata)
    assert len(result.runs) == 18
    assert {run.replicate for run in result.runs} == {1, 2}
    assert result.spec.taguchi["array_id"] == "L9(3^4)"


def test_mismatched_level_count_and_duplicate_column_are_rejected():
    array = ARRAYS["L9(3^4)"]
    with pytest.raises(ValueError, match="水平数"):
        DesignSpec("TG", (factor("A", ("a", "b")), factor("B", ("b1", "b2", "b3"))),
                   ("Y",), seed=1, design_type="taguchi",
                   taguchi={"kind": "static", "array_id": "L9(3^4)",
                            "matrix_sha256": array.sha256, "columns": {"A": 1, "B": 2},
                            "noise_array_id": None, "noise_matrix_sha256": None,
                            "noise_columns": {}, "signal_factor": None})
    with pytest.raises(ValueError, match="同一列"):
        DesignSpec("TG", (factor("A", ("a1", "a2", "a3")), factor("B", ("b1", "b2", "b3"))),
                   ("Y",), seed=1, design_type="taguchi",
                   taguchi={"kind": "static", "array_id": "L9(3^4)",
                            "matrix_sha256": array.sha256, "columns": {"A": 1, "B": 1},
                            "noise_array_id": None, "noise_matrix_sha256": None,
                            "noise_columns": {}, "signal_factor": None})


def test_wrong_matrix_hash_and_unknown_array_are_rejected():
    array = ARRAYS["L9(3^4)"]
    for array_id, digest in (("L9(3^4)", "0" * 64), ("L12(2^11)", array.sha256)):
        with pytest.raises(ValueError):
            DesignSpec("TG", tuple(factor(chr(65 + index), ("a", "b", "c"))
                                   for index in range(3)), ("Y",), seed=1,
                       design_type="taguchi",
                       taguchi={"kind": "static", "array_id": array_id,
                                "matrix_sha256": digest,
                                "columns": {"A": 1, "B": 2, "C": 3},
                                "noise_array_id": None, "noise_matrix_sha256": None,
                                "noise_columns": {}, "signal_factor": None})


def test_schema_v5_roundtrip_preserves_taguchi_identity():
    spec = static_spec()
    payload = spec.to_dict()
    assert payload["schema_version"] == 5
    assert payload["taguchi"]["array_id"] == "L9(3^4)"
    restored = DesignSpec.from_dict(payload)
    assert restored == spec
    assert dict(restored.taguchi["columns"]) == {"A": 1, "B": 2, "C": 3, "D": 4}


def test_v4_payload_does_not_gain_taguchi_fields():
    spec = DesignSpec("v4", (FactorSpec("A", "A", 0, 1), FactorSpec("B", "B", 0, 1)),
                      ("Y",), seed=1, design_type="two_level_full")
    payload = copy.deepcopy(spec.to_dict())
    payload["schema_version"] = 4
    for item in payload["factors"]:
        item["schema_version"] = 4
    payload.pop("taguchi")
    assert DesignSpec.from_dict(payload).schema_version == 5



def base_identity(**overrides):
    array = ARRAYS["L4(2^3)"]
    identity = {"kind": "static", "array_id": "L4(2^3)",
                "matrix_sha256": array.sha256, "columns": {"A": 1, "B": 2},
                "noise_array_id": None, "noise_matrix_sha256": None,
                "noise_columns": {}, "signal_factor": None}
    identity.update(overrides)
    return identity


def three_factor_spec(identity, levels=("a", "b")):
    return DesignSpec("TG", tuple(factor(chr(65 + index), levels)
                                  for index in range(3)), ("Y",), seed=1,
                      design_type="taguchi", taguchi=identity)


def test_unassigned_factor_and_orphan_noise_table_are_rejected():
    with pytest.raises(ValueError, match="控制、噪声或信号"):
        three_factor_spec(base_identity())
    with pytest.raises(ValueError, match="未分配噪声因子"):
        three_factor_spec(base_identity(
            noise_array_id="L4(2^3)",
            noise_matrix_sha256=ARRAYS["L4(2^3)"].sha256))


def test_level_mismatch_and_duplicate_column_are_rejected():
    with pytest.raises(ValueError, match="水平数"):
        DesignSpec("TG", (factor("A", ("a", "b", "c")), factor("B", ("c", "d"))),
                   ("Y",), seed=1, design_type="taguchi",
                   taguchi=base_identity())
    with pytest.raises(ValueError, match="同一列"):
        three_factor_spec(base_identity(columns={"A": 1, "B": 1}))


def test_repeated_configuration_rows_from_column_subset_are_rejected():
    """L9 只用三水平列中的两列时仍须产生 9 个不同控制组合。"""
    array = ARRAYS["L9(3^4)"]
    identity = {"kind": "static", "array_id": "L9(3^4)",
                "matrix_sha256": array.sha256,
                "columns": {"A": 1, "B": 2, "C": 3},
                "noise_array_id": None, "noise_matrix_sha256": None,
                "noise_columns": {}, "signal_factor": None}
    spec = DesignSpec("TG", tuple(factor(chr(65 + index), ("低", "中", "高"))
                                  for index in range(3)), ("Y",), seed=1,
                      design_type="taguchi", taguchi=identity)
    frame, metadata = create_taguchi(spec)
    frame.loc[0, "设定_A"] = "高" if frame.loc[0, "设定_A"] != "高" else "低"
    with pytest.raises(ValueError):
        restore_design_result(frame, metadata)


def test_static_design_rejects_signal_factor_and_dynamic_requires_one():
    with pytest.raises(ValueError, match="升序数值"):
        three_factor_spec(base_identity(columns={"A": 1, "B": 2},
                                        signal_factor="C", kind="dynamic"))
    with pytest.raises(ValueError, match="信号因子"):
        three_factor_spec(base_identity(columns={"A": 1, "B": 2, "C": 3},
                                        signal_factor="C"))

