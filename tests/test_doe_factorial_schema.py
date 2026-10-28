from copy import deepcopy

import pytest

from doe_core import DOE_SCHEMA_VERSION, DesignSpec, FactorSpec, restore_design_result
from doe_general_factorial import create_general_factorial


def general_spec():
    return DesignSpec(
        "schema-v4", (
            FactorSpec("A", "配方", None, None, factor_type="categorical",
                       levels=("甲", "乙"), level_type="text"),
            FactorSpec("B", "温度", None, None, factor_type="categorical",
                       levels=(100, 150, 200), level_type="numeric"),
        ), ("Y",), seed=17, design_type="general_full_factorial")


def test_schema_v4_preserves_numeric_and_text_factor_labels():
    spec = general_spec()
    payload = spec.to_dict()
    assert payload["schema_version"] == DOE_SCHEMA_VERSION == 5
    assert payload["construction_version"] == "v1"
    assert payload["randomization_unit"] == "run"
    assert payload["error_structure"] == "fixed"
    restored = DesignSpec.from_dict(payload)
    assert restored == spec
    assert restored.factors[0].levels == ("甲", "乙")
    assert restored.factors[1].levels == (100, 150, 200)
    assert restored.factors[1].level_type == "numeric"


@pytest.mark.parametrize("change", ["missing_design_field", "extra_design_field",
                                     "missing_factor_field", "wrong_factor_version",
                                     "numeric_as_text"])
def test_schema_v4_rejects_malformed_or_ambiguous_factor_contract(change):
    payload = deepcopy(general_spec().to_dict())
    if change == "missing_design_field":
        payload.pop("error_structure")
    elif change == "extra_design_field":
        payload["free_form"] = {"anything": True}
    elif change == "missing_factor_field":
        payload["factors"][1].pop("level_type")
    elif change == "wrong_factor_version":
        payload["factors"][1]["schema_version"] = 3
        payload["factors"][1].pop("level_type")
        payload["factors"][1].pop("randomization_role")
    else:
        payload["factors"][1]["levels"] = ["100", "150", "200"]
    with pytest.raises(ValueError):
        DesignSpec.from_dict(payload)


def test_schema_v4_worksheet_fingerprint_binds_levels_but_allows_response_fill():
    frame, metadata = create_general_factorial(general_spec())
    frame.loc[0, "响应_Y"] = 8.5
    assert restore_design_result(frame, metadata).runs[0].responses["Y"] == 8.5
    frame.loc[0, "设定_B"] = 200 if frame.loc[0, "设定_B"] != 200 else 100
    with pytest.raises(ValueError, match="设计输入"):
        restore_design_result(frame, metadata)
