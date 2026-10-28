from collections import Counter

import pandas as pd
import pytest

from doe_core import DesignSpec, FactorSpec, restore_design_result, worksheet_metadata
from doe_general_factorial import create_general_factorial, validate_general_factorial


def spec(levels=("low", "high"), *, blocks=None, seed=17):
    factors = (
        FactorSpec("A", "开关", None, None, factor_type="categorical", levels=levels),
        FactorSpec("B", "温度", None, None, factor_type="categorical",
                   levels=(100, 150, 200), level_type="numeric"),
    )
    return DesignSpec("general", factors, ("Y",), seed=seed,
                      design_type="general_full_factorial", block_count=blocks,
                      randomization_unit="block" if blocks else "run")


def test_two_by_three_mixed_label_types_roundtrip_and_response_update():
    design = spec()
    frame, metadata = create_general_factorial(design)
    assert len(frame) == 6
    assert frame["设定_A"].dtype == object and frame["设定_B"].dtype == object
    assert set(frame["设定_A"]) == {"low", "high"}
    assert all(type(value) is int for value in frame["设定_B"])
    assert len(set(zip(frame["设定_A"], frame["设定_B"]))) == 6
    assert validate_general_factorial(frame, metadata).spec.factors[1].levels == (100, 150, 200)
    frame.loc[frame["设定_B"] == 150, "响应_Y"] = 12.5
    restored = restore_design_result(frame, metadata)
    assert sum(run.responses["Y"] == 12.5 for run in restored.runs) == 2
    assert restored.spec.factors[1].level_type == "numeric"


def test_mixed_2x3x4_cartesian_product_and_reproducible_run_order():
    factors = (
        FactorSpec("A", "A", None, None, factor_type="categorical", levels=("off", "on")),
        FactorSpec("B", "B", None, None, factor_type="categorical", levels=(100, 150, 200),
                   level_type="numeric"),
        FactorSpec("C", "C", None, None, factor_type="categorical", levels=("1", "2", "3", "4")),
    )
    design = DesignSpec("mixed", factors, ("Y",), seed=92,
                        design_type="general_full_factorial")
    first, metadata = create_general_factorial(design)
    second, _ = create_general_factorial(design)
    assert len(first) == 24
    assert Counter(first["运行序"]) == Counter(range(1, 25))
    assert first["运行ID"].tolist() == second["运行ID"].tolist()
    assert first["运行序"].tolist() == second["运行序"].tolist()
    assert len({tuple(row) for row in first[["设定_A", "设定_B", "设定_C"]].itertuples(
        index=False, name=None)}) == 24
    assert validate_general_factorial(first, metadata).spec.design_type == "general_full_factorial"


def test_each_full_replicate_can_be_a_randomized_complete_block():
    design = spec(blocks=3, seed=991)
    frame, metadata = create_general_factorial(design, replicates=3)
    assert frame["区组"].nunique() == 3
    assert set(frame.groupby("区组").size()) == {6}
    assert set(frame.groupby("区组")["设定_B"].nunique()) == {3}
    assert validate_general_factorial(frame, metadata).spec.block_count == 3


def test_row_limit_is_checked_before_cartesian_product(monkeypatch):
    factors = (
        FactorSpec("A", "A", None, None, factor_type="categorical",
                   levels=tuple(range(100)), level_type="numeric"),
        FactorSpec("B", "B", None, None, factor_type="categorical",
                   levels=tuple(range(101)), level_type="numeric"),
    )
    design = DesignSpec("large", factors, ("Y",), seed=1,
                        design_type="general_full_factorial")
    monkeypatch.setattr("doe_general_factorial._combinations",
                        lambda _: pytest.fail("product allocated before run-limit rejection"))
    with pytest.raises(ValueError, match="10000"):
        create_general_factorial(design)


def _categorical_spec(count, levels=("low", "high"), replicates=None):
    factors = tuple(
        FactorSpec(chr(65 + index), f"F{index}", None, None,
                   factor_type="categorical", levels=levels)
        for index in range(count))
    return DesignSpec("count", factors, ("Y",), seed=5,
                      design_type="general_full_factorial")


@pytest.mark.parametrize("count", [1, 11])
def test_factor_count_outside_two_to_ten_is_rejected(count):
    with pytest.raises(ValueError, match="2–10"):
        create_general_factorial(_categorical_spec(count))


def test_ten_factors_are_valid_but_still_limited_to_10000_runs():
    frame, metadata = create_general_factorial(_categorical_spec(10), replicates=9)
    assert len(frame) == 9216
    assert validate_general_factorial(frame, metadata).spec.factors[9].factor_id == "J"
    with pytest.raises(ValueError, match="10000"):
        create_general_factorial(_categorical_spec(10), replicates=10)


@pytest.mark.parametrize("count", [1, 11])
def test_restore_validation_rejects_saved_designs_outside_factor_range(count):
    design = _categorical_spec(count)
    values = {f.factor_id: f.levels[0] for f in design.factors}
    columns = {
        "run_id": "运行ID", "standard_order": "标准序", "run_order": "运行序",
        "point_type": "点类型", "replicate": "重复",
        "factors": {f.factor_id: f"设定_{f.factor_id}" for f in design.factors},
        "measured_levels": {}, "responses": {"Y": "响应_Y"},
    }
    row = {"运行ID": "R00001", "标准序": 1, "运行序": 1,
           "点类型": "factorial", "重复": 1, "响应_Y": None}
    row.update({columns["factors"][key]: value for key, value in values.items()})
    frame = pd.DataFrame([row])
    with pytest.raises(ValueError, match="2–10"):
        validate_general_factorial(frame, worksheet_metadata(frame, design, columns))


def test_incomplete_or_repeated_factor_combinations_are_rejected():
    frame, _ = create_general_factorial(spec())
    frame.loc[0, "设定_A"] = frame.loc[1, "设定_A"]
    columns = {
        "run_id": "运行ID", "standard_order": "标准序", "run_order": "运行序",
        "point_type": "点类型", "replicate": "重复",
        "factors": {"A": "设定_A", "B": "设定_B"},
        "measured_levels": {}, "responses": {"Y": "响应_Y"},
    }
    tampered = worksheet_metadata(frame, spec(), columns)
    with pytest.raises(ValueError, match="每个分类组合"):
        validate_general_factorial(frame, tampered)


def test_numeric_categorical_labels_are_not_text_or_continuous_levels():
    numeric = FactorSpec("T", "温度", None, None, factor_type="categorical",
                         levels=(100, 150, 200), level_type="numeric")
    assert numeric.level_type == "numeric" and numeric.levels == (100, 150, 200)
    with pytest.raises(ValueError, match="不得重复"):
        FactorSpec("T", "温度", None, None, factor_type="categorical",
                   levels=(100, 100.0), level_type="numeric")
    with pytest.raises(ValueError, match="分类因子数值水平"):
        FactorSpec("T", "温度", None, None, factor_type="categorical",
                   levels=("100", "150"), level_type="numeric")
