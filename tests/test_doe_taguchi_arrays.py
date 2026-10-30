"""Taguchi 数组目录、设计网格与 Schema v5 合同。"""
import copy
from collections import Counter
from itertools import product

import pytest

from doe_core import DOE_SCHEMA_VERSION, DesignSpec, FactorSpec, restore_design_result
from doe_taguchi import create_taguchi
from doe_taguchi_arrays import ARRAYS, column_counts, pair_counts, validate_array


_OFFICIAL_L36 = tuple(tuple(map(int, row.split())) for row in """
1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1 1 1 1 2 2 2 2 2 2 2 2 2 2 2 2
1 1 1 1 1 1 1 1 1 1 1 3 3 3 3 3 3 3 3 3 3 3 3
1 1 1 1 1 2 2 2 2 2 2 1 1 1 1 2 2 2 2 3 3 3 3
1 1 1 1 1 2 2 2 2 2 2 2 2 2 2 3 3 3 3 1 1 1 1
1 1 1 1 1 2 2 2 2 2 2 3 3 3 3 1 1 1 1 2 2 2 2
1 1 2 2 2 1 1 1 2 2 2 1 1 2 3 1 2 3 3 1 2 2 3
1 1 2 2 2 1 1 1 2 2 2 2 2 3 1 2 3 1 1 2 3 3 1
1 1 2 2 2 1 1 1 2 2 2 3 3 1 2 3 1 2 2 3 1 1 2
1 2 1 2 2 1 2 2 1 1 2 1 1 3 2 1 3 2 3 2 1 3 2
1 2 1 2 2 1 2 2 1 1 2 2 2 1 3 2 1 3 1 3 2 1 3
1 2 1 2 2 1 2 2 1 1 2 3 3 2 1 3 2 1 2 1 3 2 1
1 2 2 1 2 2 1 2 1 2 1 1 2 3 1 3 2 1 3 3 2 1 2
1 2 2 1 2 2 1 2 1 2 1 2 3 1 2 1 3 2 1 1 3 2 3
1 2 2 1 2 2 1 2 1 2 1 3 1 2 3 2 1 3 2 2 1 3 1
1 2 2 2 1 2 2 1 2 1 1 1 2 3 2 1 1 3 2 3 3 2 1
1 2 2 2 1 2 2 1 2 1 1 2 3 1 3 2 2 1 3 1 1 3 2
1 2 2 2 1 2 2 1 2 1 1 3 1 2 1 3 3 2 1 2 2 1 3
2 1 2 2 1 1 2 2 1 2 1 1 2 1 3 3 3 1 2 2 1 2 3
2 1 2 2 1 1 2 2 1 2 1 2 3 2 1 1 1 2 3 3 2 3 1
2 1 2 2 1 1 2 2 1 2 1 3 1 3 2 2 2 3 1 1 3 1 2
2 1 2 1 2 2 2 1 1 1 2 1 2 2 3 3 1 2 1 1 3 3 2
2 1 2 1 2 2 2 1 1 1 2 2 3 3 1 1 2 3 2 2 1 1 3
2 1 2 1 2 2 2 1 1 1 2 3 1 1 2 2 3 1 3 3 2 2 1
2 1 1 2 2 2 1 2 2 1 1 1 3 2 1 2 3 3 1 3 1 2 2
2 1 1 2 2 2 1 2 2 1 1 2 1 3 2 3 1 1 2 1 2 3 3
2 1 1 2 2 2 1 2 2 1 1 3 2 1 3 1 2 2 3 2 3 1 1
2 2 2 1 1 1 1 2 2 1 2 1 3 2 2 2 1 1 3 2 3 1 3
2 2 2 1 1 1 1 2 2 1 2 2 1 3 3 3 2 2 1 3 1 2 1
2 2 2 1 1 1 1 2 2 1 2 3 2 1 1 1 3 3 2 1 2 3 2
2 2 1 2 1 2 1 1 1 2 2 1 3 3 3 2 3 2 2 1 2 1 1
2 2 1 2 1 2 1 1 1 2 2 2 1 1 1 3 1 3 3 2 3 2 2
2 2 1 2 1 2 1 1 1 2 2 3 2 2 2 1 2 1 1 3 1 3 3
2 2 1 1 2 1 2 1 2 2 1 1 3 1 2 3 2 3 1 2 2 3 1
2 2 1 1 2 1 2 1 2 2 1 2 1 2 3 1 3 1 2 3 3 1 2
2 2 1 1 2 1 2 1 2 2 1 3 2 3 1 2 1 2 3 1 1 2 3
""".strip().splitlines())


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
    import json
    from pathlib import Path

    assert DOE_SCHEMA_VERSION == 5
    fixtures = Path(__file__).parent / "fixtures"
    legacy = json.loads((fixtures / "doe_taguchi_reference" / "manifest.json").read_text(
        encoding="utf-8"))["fixtures"]
    assert {case["array_id"]: case["sha256"] for case in legacy} == {
        key: ARRAYS[key].sha256 for key in
        ("L4(2^3)", "L8(2^7)", "L9(3^4)", "L16(4^5)",
         "L18(2^1 3^7)", "L25(5^6)")}
    p4bc = json.loads((fixtures / "doe_phase2_p4bc_reference" / "reference.json").read_text(
        encoding="utf-8"))
    assert {item["array_id"]: item["matrix_sha256"]
            for item in p4bc["taguchi_arrays"]} == {
        key: ARRAYS[key].sha256
        for key in ("L8(4^1 2^4)", "L16(4^1 2^12)", "L18(2^1 3^7)")}


@pytest.mark.parametrize("array_id", sorted(ARRAYS))
def test_every_catalogued_array_passes_balance_and_pair_audit(array_id):
    audit = validate_array(ARRAYS[array_id])
    assert audit["run_count"] == ARRAYS[array_id].run_count
    assert audit["unbalanced_pairs"] == list(ARRAYS[array_id].documented_unbalanced_pairs)


def test_l36_matches_official_matrix_balance_pairs_and_model_rank():
    import numpy as np

    array = ARRAYS["L36(2^11 3^12)"]
    assert len(_OFFICIAL_L36) == 36
    assert all(len(row) == 23 for row in _OFFICIAL_L36)
    assert array.matrix == _OFFICIAL_L36
    assert array.levels == (2,) * 11 + (3,) * 12
    assert array.column_numbers == tuple(range(1, 24))

    for column, level_count in enumerate(array.levels):
        expected = {level: 36 // level_count for level in range(1, level_count + 1)}
        assert dict(Counter(row[column] for row in _OFFICIAL_L36)) == expected
        assert column_counts(array)[column + 1] == expected
    for first in range(23):
        for second in range(first + 1, 23):
            expected = {
                (left, right): 36 // (array.levels[first] * array.levels[second])
                for left, right in product(range(1, array.levels[first] + 1),
                                           range(1, array.levels[second] + 1))}
            reference = dict(Counter((row[first], row[second])
                                     for row in _OFFICIAL_L36))
            assert reference == expected
            assert pair_counts(array, first + 1, second + 1) == expected

    matrix = np.asarray(_OFFICIAL_L36, dtype=float)
    assert np.linalg.matrix_rank(matrix) == 23
    model_columns = [np.ones(len(_OFFICIAL_L36))]
    for column, level_count in enumerate(array.levels):
        model_columns.extend(np.asarray([row[column] == level for row in _OFFICIAL_L36],
                                        dtype=float)
                             for level in range(2, level_count + 1))
    model = np.column_stack(model_columns)
    assert model.shape == (36, 36)
    assert np.linalg.matrix_rank(model) == 36


def test_l36_partial_column_assignment_uses_selected_official_columns():
    array = ARRAYS["L36(2^11 3^12)"]
    factors = (factor("A", ("off", "on")), factor("B", ("cold", "hot")),
               factor("C", ("low", "mid", "high")),
               factor("D", ("small", "medium", "large")))
    columns = {"A": 1, "B": 2, "C": 12, "D": 18}
    spec = DesignSpec(
        "TG", factors, ("Y",), seed=11, design_type="taguchi",
        taguchi={"kind": "static", "array_id": array.array_id,
                 "matrix_sha256": array.sha256, "columns": columns,
                 "noise_array_id": None, "noise_matrix_sha256": None,
                 "noise_columns": {}, "signal_factor": None})

    frame, metadata = create_taguchi(spec)
    assert len(frame) == 36
    assert metadata["design"]["taguchi"]["columns"] == columns
    assert set(frame["设定_A"]) == {"off", "on"}
    assert set(frame["设定_B"]) == {"cold", "hot"}
    assert set(frame["设定_C"]) == {"low", "mid", "high"}
    assert set(frame["设定_D"]) == {"small", "medium", "large"}


def test_l18_unbalanced_pairs_are_recorded_not_silently_claimed_orthogonal():
    array = ARRAYS["L18(2^1 3^7)"]
    assert array.documented_unbalanced_pairs == ((3, 8), (4, 8), (5, 8), (6, 8), (7, 8))
    assert set(pair_counts(array, 3, 8).values()) != {2}
    assert set(pair_counts(array, 1, 8).values()) == {3}


def test_l18_balanced_control_columns_including_official_column_nine_remain_usable():
    array = ARRAYS["L18(2^1 3^7)"]
    assert array.column_numbers == (1, 2, 3, 4, 5, 6, 7, 9)
    assert array.official_column(8) == 9
    assert array.column_position(9) == 8
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
    with pytest.raises(ValueError, match="3/9.*不满足两两正交"):
        l18_spec({"A": 1, "B": 2, "C": 3, "D": 8})


def test_l18_nonorthogonal_noise_pair_is_rejected_at_core_construction():
    array = ARRAYS["L18(2^1 3^7)"]
    factors = (factor("A", ("低", "高")), factor("B", ("b1", "b2", "b3")),
               factor("C", ("c1", "c2", "c3")),
               factor("D", ("d1", "d2", "d3")),
               factor("E", ("e1", "e2", "e3")))
    with pytest.raises(ValueError, match="噪声列组合 3/9.*不满足两两正交"):
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
    with pytest.raises(ValueError, match="3/9.*不满足两两正交"):
        restore_design_result(frame, broken)
    with pytest.raises(ValueError, match="3/9.*不满足两两正交"):
        analyze_static(frame, broken, "Y", "smaller")


@pytest.mark.parametrize("levels", [2, 3, 4, 5])
def test_column_counts_are_balanced_for_every_level_count(levels):
    for array in ARRAYS.values():
        for column, counts in column_counts(array).items():
            if array.levels[column - 1] == levels:
                assert set(counts.values()) == {array.run_count // levels}


@pytest.mark.parametrize("array_id, capacity", [("L4(2^3)", 3), ("L8(2^7)", 7),
                                                ("L9(3^4)", 4), ("L16(4^5)", 5),
                                                ("L18(2^1 3^7)", 8), ("L25(5^6)", 6),
                                                ("L36(2^11 3^12)", 23),
                                                ("L8(4^1 2^4)", 5),
                                                ("L16(4^1 2^12)", 13)])
def test_array_capacity_and_duplicate_columns(array_id, capacity):
    array = ARRAYS[array_id]
    assert array.factor_capacity == capacity
    assert array.columns_for(2) == tuple(index + 1 for index, value
                                         in enumerate(array.levels) if value == 2)
    with pytest.raises(ValueError):
        pair_counts(array, 1, 1)
    with pytest.raises(ValueError):
        pair_counts(array, 1, capacity + 1)


def test_new_mixed_arrays_use_catalogue_columns_and_are_pairwise_balanced():
    for array_id, expected_levels in (
            ("L8(4^1 2^4)", (4, 2, 2, 2, 2)),
            ("L16(4^1 2^12)", (4,) + (2,) * 12)):
        array = ARRAYS[array_id]
        assert array.levels == expected_levels
        assert array.column_numbers == tuple(range(1, len(expected_levels) + 1))
        assert len(array.matrix) == (8 if array_id.startswith("L8") else 16)
        assert not validate_array(array)["unbalanced_pairs"]


def test_l8_two_factor_projection_is_balanced_but_rejected_by_design_contract():
    array = ARRAYS['L8(2^7)']
    counts = {}
    for row in array.matrix:
        pair = (row[0], row[1])
        counts[pair] = counts.get(pair, 0) + 1
    assert counts == {(1, 1): 2, (1, 2): 2, (2, 1): 2, (2, 2): 2}

    with pytest.raises(ValueError, match='所选列存在重复行'):
        DesignSpec(
            'TG', (factor('A', ('a1', 'a2')), factor('B', ('b1', 'b2'))),
            ('Y',), seed=1, design_type='taguchi',
            taguchi={'kind': 'static', 'array_id': array.array_id,
                     'matrix_sha256': array.sha256, 'columns': {'A': 1, 'B': 2},
                     'noise_array_id': None, 'noise_matrix_sha256': None,
                     'noise_columns': {}, 'signal_factor': None})


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
    for key in ("taguchi", "model_terms", "optimal_lineage", "augmentation_lineage"):
        payload.pop(key)
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
