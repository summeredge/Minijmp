import json
from copy import deepcopy
from pathlib import Path

import pandas as pd
import pytest

from doe_core import (DOE_SCHEMA_VERSION, DesignSpec, FactorSpec,
                      restore_design_result, validate_worksheet_metadata)
from doe_custom import define_custom


REFERENCE = json.loads((Path(__file__).parent / "fixtures" / "doe_optimal_reference"
                        / "reference.json").read_text(encoding="utf-8"))


def custom_case():
    frame = pd.DataFrame({
        "运行ID": ["R1", "R2", "R3", "R4"],
        "标准序": [1, 2, 3, 4], "运行序": [1, 2, 3, 4],
        "点类型": ["factorial"] * 4, "重复": [1] * 4,
        "A": ["低", "高", "低", "高"], "B": ["低", "低", "高", "高"],
        "Y": [1.0, 2.0, 3.0, 5.0],
    })
    factors = (FactorSpec("A", "A", None, None, factor_type="categorical",
                          levels=("低", "高"), level_type="text"),
               FactorSpec("B", "B", None, None, factor_type="categorical",
                          levels=("低", "高"), level_type="text"))
    mapping = {"run_id": "运行ID", "standard_order": "标准序",
               "run_order": "运行序", "point_type": "点类型",
               "replicate": "重复", "factors": {"A": "A", "B": "B"},
               "responses": {"Y": "Y"}}
    return frame, factors, mapping


def test_schema_version_is_five_and_custom_design_roundtrips():
    frame, factors, mapping = custom_case()
    result, metadata, summary = define_custom(
        frame, design_type="custom_factorial", factors=factors,
        responses=("Y",), column_map=mapping, design_id="schema-e")
    assert DOE_SCHEMA_VERSION == 5
    assert metadata["schema_version"] == 5
    assert metadata["design"]["design_type"] == "custom_factorial"
    assert metadata["design"]["model_terms"] == []
    assert metadata["design"]["optimal_lineage"] is None
    restored = restore_design_result(result, metadata)
    assert restored.spec.design_id == "schema-e"
    assert [run.settings["A"] for run in restored.runs] == ["低", "高", "低", "高"]
    # 重新校验后仍为 v5，且摘要可复算。
    again = validate_worksheet_metadata(result, metadata)
    assert again["schema_version"] == 5
    assert restore_design_result(result, again).runs[3].responses["Y"] == 5.0


def test_v5_rejects_extra_or_missing_design_fields():
    frame, factors, mapping = custom_case()
    _, metadata, _ = define_custom(
        frame, design_type="custom_factorial", factors=factors,
        responses=("Y",), column_map=mapping)
    extra = deepcopy(metadata)
    extra["design"]["unknown_field"] = 1
    with pytest.raises(ValueError, match="字段"):
        restore_design_result(frame, extra)
    missing = deepcopy(metadata)
    missing["design"].pop("optimal_lineage")
    with pytest.raises(ValueError, match="字段"):
        restore_design_result(frame, missing)


def test_custom_types_require_v5():
    with pytest.raises(ValueError, match="schema v5"):
        DesignSpec("old-custom", (FactorSpec("A", "A", 0, 1),), ("Y",),
                   design_type="custom_factorial", schema_version=4)
    with pytest.raises(ValueError, match="schema v5"):
        DesignSpec("old-rsm", (FactorSpec("A", "A", 0, 1),), ("Y",),
                   design_type="custom_rsm", schema_version=4)


def test_v5_model_terms_only_for_custom_designs():
    with pytest.raises(ValueError, match="model_terms"):
        DesignSpec("plain", (FactorSpec("A", "A", 0, 1),), ("Y",),
                   design_type="two_level_full", schema_version=5,
                   model_terms=("A",))


def test_optimal_and_augmentation_lineage_are_mutually_exclusive():
    lineage = {"parent_design_id": "parent", "criterion": "d_optimal",
               "candidate_sha256": "0" * 64, "selection_order": ("R1",),
               "batch_id": "OPT1"}
    augment = {"parent_design_id": "parent", "batch_id": "AUG1",
               "criterion": "manual", "run_map": [(None, "A1")],
               "source_matrix_sha256": "0" * 64,
               "current_matrix_sha256": "1" * 64}
    with pytest.raises(ValueError, match="不能同时存在"):
        DesignSpec("both", (FactorSpec("A", "A", 0, 1),), ("Y",),
                   design_type="custom_factorial", schema_version=5,
                   optimal_lineage=lineage, augmentation_lineage=augment)


def test_bad_lineage_parent_and_criterion_are_rejected():
    with pytest.raises(ValueError, match="父设计"):
        DesignSpec("self-parent", (FactorSpec("A", "A", 0, 1),), ("Y",),
                   design_type="custom_factorial", schema_version=5,
                   optimal_lineage={"parent_design_id": "self-parent",
                                    "criterion": "d_optimal",
                                    "candidate_sha256": "0" * 64,
                                    "selection_order": ("R1",),
                                    "batch_id": "OPT1"})
    with pytest.raises(ValueError, match="准则"):
        DesignSpec("bad-criterion", (FactorSpec("A", "A", 0, 1),), ("Y",),
                   design_type="custom_factorial", schema_version=5,
                   optimal_lineage={"parent_design_id": "parent",
                                    "criterion": "a_optimal",
                                    "candidate_sha256": "0" * 64,
                                    "selection_order": ("R1",),
                                    "batch_id": "OPT1"})


def test_old_v4_design_still_reads_as_v5_without_new_fields():
    spec = DesignSpec("v4-plain", (FactorSpec("A", "A", 0, 1),), ("Y",),
                      design_type="two_level_full", schema_version=4)
    payload = spec.to_dict()
    assert payload["schema_version"] == 4
    restored = DesignSpec.from_dict(payload)
    assert restored.schema_version == 5
    assert restored.model_terms == ()
    assert restored.optimal_lineage is None
