import json
import math
from pathlib import Path
from dataclasses import replace
from fractions import Fraction

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from doe_core import (
    DesignResult,
    DesignSpec,
    FactorSpec,
    ModelResult,
    OptimizationResult,
    RunRecord,
    design_from_worksheet,
    randomized_run_order,
    restore_design_result,
    validate_worksheet_metadata,
    worksheet_metadata,
)


ROOT = Path(__file__).resolve().parents[1]


def sample_spec():
    return DesignSpec(
        design_id="doe-demo",
        factors=(
            FactorSpec("A", "温度", 10, 20, "°C"),
            FactorSpec("B", "压力", 2, 6, "kPa"),
        ),
        response_names=("收率",),
        seed=2026,
    )


def sample_frame():
    return pd.DataFrame(
        {
            "运行ID": ["R-03", "R-01", "R-04", "R-02"],
            "标准序": [3, 1, 4, 2],
            "运行序": [3, 1, 4, 2],
            "点类型": ["factorial"] * 4,
            "重复": [1, 1, 2, 2],
            "批次ID": pd.array([2**60 + i for i in range(4)], dtype="Int64"),
            "1": [10, 10, 20, 20],
            1: [6, 2, 6, 2],
            "A实测": pd.array([10.0, pd.NA, 19.5, 20.0], dtype="Float64"),
            "收率列": pd.array([pd.NA] * 4, dtype="Float64"),
        },
        index=[50, 50, 8, 100],
    )


def sample_column_map():
    return {
        "run_id": "运行ID",
        "standard_order": "标准序",
        "run_order": "运行序",
        "point_type": "点类型",
        "replicate": "重复",
        "block": "批次ID",
        "factors": {"A": "1", "B": 1},
        "measured_levels": {"A": "A实测"},
        "responses": {"收率": "收率列"},
    }


def test_actual_and_coded_levels_follow_independent_affine_formula():
    factor = FactorSpec("A", "温度", 10, 20, "°C")
    expected = 2 * (13 - 10) / (20 - 10) - 1
    assert math.isclose(factor.to_coded(13), expected, abs_tol=1e-15)
    assert factor.from_coded(-1) == 10
    assert factor.from_coded(1) == 20
    for actual in (10, 12, 15, 18, 20):
        assert math.isclose(float(factor.from_coded(factor.to_coded(actual))),
                            actual, abs_tol=1e-12)


def test_large_integer_factor_endpoints_and_midpoint_are_not_rounded():
    low = 2**60 + 1
    high = low + 2
    factor = FactorSpec("A", "批量设定", low, high)
    assert factor.from_coded(-1) == low
    assert factor.from_coded(1) == high
    assert factor.from_coded(0) == low + 1
    wide = FactorSpec("wide", "宽范围", 2**60, 2**61)
    assert wide.to_coded(2**60 + 1) != wide.to_coded(2**60)
    assert wide.from_coded(wide.to_coded(2**60 + 1)) == 2**60 + 1


def test_fractional_coding_is_reversible_and_json_numeric_values_stay_simple():
    factor = FactorSpec("A", "温度", 10, 21)
    coded = factor.to_coded(13)
    assert factor.from_coded(coded) == 13
    assert factor.from_coded(0) == 15.5
    RunRecord("R1", 1, 1, "center", {"A": factor.from_coded(0)},
              responses={"Y": None})
    exact = factor.from_coded(Fraction(1, 3))
    assert exact == Fraction(52, 3)
    assert factor.to_coded(exact) == Fraction(1, 3)
    with pytest.raises(ValueError, match="无损表示"):
        RunRecord("R1", 1, 1, "center", {"A": exact}, responses={"Y": None})


@pytest.mark.parametrize(
    "low,high,pattern",
    [
        (1, 1, "low 必须小于 high"),
        (float("nan"), 2, "有限"),
        (1, float("inf"), "有限"),
    ],
)
def test_factor_rejects_invalid_actual_ranges(low, high, pattern):
    with pytest.raises(ValueError, match=pattern):
        FactorSpec("A", "温度", low, high)


def test_factor_rejects_nonfinite_and_out_of_range_conversion_values():
    factor = FactorSpec("A", "温度", 1, 9)
    for actual in (float("nan"), float("inf"), 0, 10):
        with pytest.raises(ValueError):
            factor.to_coded(actual)
    for coded in (float("nan"), float("-inf"), -1.01, 1.01):
        with pytest.raises(ValueError):
            factor.from_coded(coded)


def test_design_spec_rejects_duplicate_ids_names_and_illegal_dimensions():
    with pytest.raises(ValueError, match="factor_id 不得重复"):
        DesignSpec("doe-1", (FactorSpec("A", "甲", 0, 1),
                             FactorSpec("A", "乙", 0, 1)), ("Y",))
    with pytest.raises(ValueError, match="展示名称不得重复"):
        DesignSpec("doe-1", (FactorSpec("A", "甲", 0, 1),
                             FactorSpec("B", "甲", 0, 1)), ("Y",))
    with pytest.raises(ValueError, match="必须包含 FactorSpec"):
        DesignSpec("doe-1", (), ("Y",))
    with pytest.raises(ValueError, match="至少需要一个响应"):
        DesignSpec("doe-1", (FactorSpec("A", "甲", 0, 1),), ())


@pytest.mark.parametrize(
    "design_type",
    ["two_level_full", "two_level_fractional", "central_composite", "unspecified"],
)
def test_design_type_is_controlled_and_versioned_in_design_spec(design_type):
    spec = replace(sample_spec(), design_type=design_type)
    assert DesignSpec.from_dict(spec.to_dict()).design_type == design_type
    frame = sample_frame()
    metadata = worksheet_metadata(frame, spec, sample_column_map())
    normalized = validate_worksheet_metadata(frame, metadata)
    assert normalized["design"]["design_type"] == design_type
    assert restore_design_result(frame, normalized).spec.design_type == design_type


def test_missing_or_invalid_design_type_is_rejected_without_guessing():
    spec = sample_spec()
    assert spec.design_type == "unspecified"
    payload = spec.to_dict()
    payload.pop("design_type")
    with pytest.raises(ValueError, match="缺少 design_type"):
        DesignSpec.from_dict(payload)
    with pytest.raises(ValueError, match="design_type 必须是"):
        replace(spec, design_type="guess_from_generators")


def test_categorical_factor_is_reserved_but_mixed_design_is_not_implemented():
    categorical = FactorSpec("lot", "批次", None, None,
                             factor_type="categorical", levels=("low", "high"))
    with pytest.raises(NotImplementedError, match="分类或混合水平设计"):
        DesignSpec("doe-1", (FactorSpec("A", "温度", 0, 1), categorical), ("Y",))
    with pytest.raises(TypeError, match="分类因子"):
        categorical.to_coded("low")


def test_future_generator_alias_and_ccd_fields_roundtrip_without_generation():
    factors = tuple(FactorSpec(key, key, 0, 1) for key in "ABCD")
    spec = DesignSpec(
        "doe-future", factors, ("Y",),
        generators=("D=ABC",), defining_relations=("I=ABCD",),
        aliases=("A=BCD",), ccd_alpha=1.681792830507429,
        ccd_center_points=5, ccd_axial_points=8,
    )
    assert DesignSpec.from_dict(spec.to_dict()) == spec
    with pytest.raises(ValueError, match="受控关系格式"):
        replace(spec, aliases=("not a relation",))


def test_seeded_run_order_repeats_without_mutating_the_input():
    run_ids = ["R1", "R2", "R3", "R4"]
    first = randomized_run_order(run_ids, 2026)
    second = randomized_run_order(run_ids, 2026)
    assert first == second
    assert set(first) == set(run_ids)
    assert run_ids == ["R1", "R2", "R3", "R4"]


def test_worksheet_binding_is_bijective_typed_and_non_mutating():
    frame = sample_frame()
    frame["备注列"] = ["合成数据"] * len(frame)
    before = frame.copy(deep=True)
    spec = sample_spec()
    metadata = worksheet_metadata(frame, spec, sample_column_map())
    result = restore_design_result(frame, metadata)

    assert_frame_equal(frame, before)
    assert result.runs[0].run_id == "R-03"
    assert result.runs[0].standard_order == 3
    assert result.runs[0].run_order == 3
    assert result.runs[0].settings == {"A": 10, "B": 6}
    assert result.runs[0].block == 2**60
    assert result.runs[0].measured_levels == {"A": 10.0}
    assert result.runs[1].measured_levels == {"A": None}
    assert result.runs[0].responses == {"收率": None}
    assert frame.index.tolist() == [50, 50, 8, 100]
    assert frame["批次ID"].iloc[0] == 2**60
    assert type(metadata["column_map"]["factors"]["A"]) is str
    assert type(metadata["column_map"]["factors"]["B"]) is int
    json.dumps(metadata, ensure_ascii=False, allow_nan=False)
    assert str(2**60) not in repr(metadata)
    assert "备注列" not in repr(metadata)


def test_nullable_integer_block_column_is_recovered_without_rounding_ids():
    frame = sample_frame()
    frame["区组"] = [1.0, float("nan"), 2.0, float("nan")]
    columns = sample_column_map()
    columns["block"] = "区组"
    result = design_from_worksheet(frame, sample_spec(), columns)
    assert [run.block for run in result.runs] == [1, None, 2, None]

    frame["区组"] = [float(2**60), float("nan"), 2.0, float("nan")]
    with pytest.raises(ValueError, match="可精确恢复"):
        design_from_worksheet(frame, sample_spec(), columns)


def test_response_can_be_filled_without_staling_design_mapping():
    frame = sample_frame()
    frame["A实测"] = pd.array([pd.NA] * 4, dtype="Float64")
    metadata = worksheet_metadata(frame, sample_spec(), sample_column_map())
    frame.iloc[0, frame.columns.get_loc("收率列")] = 12.5
    frame.iloc[0, frame.columns.get_loc("A实测")] = 10.5
    result = restore_design_result(frame, metadata)
    assert result.runs[0].responses["收率"] == 12.5
    assert result.runs[0].measured_levels["A"] == 10.5


def test_design_can_map_more_than_one_nullable_response():
    frame = sample_frame()
    frame["第二响应"] = pd.array([1.0, pd.NA, 3.0, 4.0], dtype="Float64")
    spec = replace(sample_spec(), response_names=("收率", "质量"))
    columns = sample_column_map()
    columns["responses"]["质量"] = "第二响应"
    result = design_from_worksheet(frame, spec, columns)
    assert result.runs[0].responses == {"收率": None, "质量": 1.0}
    assert result.runs[1].responses == {"收率": None, "质量": None}


def test_stale_column_or_input_mapping_fails_closed():
    frame = sample_frame()
    metadata = worksheet_metadata(frame, sample_spec(), sample_column_map())
    renamed = frame.rename(columns={"1": "温度"})
    with pytest.raises(ValueError, match="映射列不存在"):
        restore_design_result(renamed, metadata)
    changed = frame.copy(deep=True)
    changed.iloc[0, changed.columns.get_loc("1")] = 20
    with pytest.raises(ValueError, match="设计输入或运行映射已变化"):
        restore_design_result(changed, metadata)
    reordered = frame.loc[:, list(reversed(frame.columns))]
    with pytest.raises(ValueError, match="列名或列顺序已变化"):
        restore_design_result(reordered, metadata)


def test_run_id_mapping_rejects_float_coercion():
    frame = sample_frame()
    metadata = worksheet_metadata(frame, sample_spec(), sample_column_map())
    metadata["worksheet"]["run_rows"][0]["run_id"] = 1.0
    with pytest.raises(ValueError, match="映射含无效 ID"):
        restore_design_result(frame, metadata)


def test_design_type_change_is_bound_to_the_persisted_input_fingerprint():
    frame = sample_frame()
    metadata = worksheet_metadata(frame, sample_spec(), sample_column_map())
    metadata["design"]["design_type"] = "two_level_full"
    with pytest.raises(ValueError, match="设计输入或运行映射已变化"):
        restore_design_result(frame, metadata)


def test_response_column_remap_cannot_silently_redirect_observations():
    frame = sample_frame()
    frame["替代收率"] = pd.array([100.0, 200.0, 300.0, 400.0], dtype="Float64")
    metadata = worksheet_metadata(frame, sample_spec(), sample_column_map())
    metadata["column_map"]["responses"]["收率"] = "替代收率"
    with pytest.raises(ValueError, match="设计输入或运行映射已变化"):
        restore_design_result(frame, metadata)


def test_response_rejects_infinity_and_identifiers_reject_absolute_paths():
    frame = sample_frame()
    frame.iloc[0, frame.columns.get_loc("收率列")] = float("inf")
    with pytest.raises(ValueError, match="有限"):
        worksheet_metadata(frame, sample_spec(), sample_column_map())
    with pytest.raises(ValueError, match="绝对路径"):
        FactorSpec("A", r"C:\sensitive", 0, 1)


def test_result_contract_rejects_duplicate_ids_and_nonpermutation_orders():
    frame = sample_frame()
    result = design_from_worksheet(frame, sample_spec(), sample_column_map())
    first = result.runs[0]
    duplicated = (*result.runs[:2], replace(result.runs[2], run_id=first.run_id),
                  *result.runs[3:])
    with pytest.raises(ValueError, match="run_id 必须唯一"):
        DesignResult(result.spec, duplicated)
    malformed = RunRecord(
        run_id=first.run_id, standard_order=1, run_order=1,
        point_type="factorial", settings={"A": 10, "B": 6},
        responses={"收率": None},
    )
    with pytest.raises(ValueError, match="standard_order 必须是"):
        DesignResult(result.spec, (malformed, *result.runs[1:]))


def test_axial_run_can_store_future_out_of_range_target_without_generating_it():
    spec = DesignSpec("doe-ccd-placeholder",
                      (FactorSpec("A", "温度", 0, 10),), ("Y",),
                      ccd_alpha=1.5, ccd_axial_points=1)
    run = RunRecord(
        run_id="axial-1", standard_order=1, run_order=1,
        point_type="axial", settings={"A": 15}, responses={"Y": None},
    )
    result = DesignResult(spec, (run,))
    assert result.runs[0].settings["A"] == 15
    invalid_spec = replace(spec, ccd_alpha=None)
    with pytest.raises(ValueError, match="必须匹配已声明的 CCD alpha"):
        DesignResult(invalid_spec, (run,))


def test_axial_rejected_for_other_families_and_unencodable_values():
    factor = FactorSpec("A", "A", 0, 1)
    run = RunRecord(run_id="r1", standard_order=1, run_order=1,
                    point_type="axial", settings={"A": 2}, responses={"Y": None})
    with pytest.raises(ValueError, match="不支持轴点"):
        DesignResult(DesignSpec("d", (factor,), ("Y",),
                                design_type="two_level_full"), (run,))
    huge = replace(run, settings={"A": 10 ** 400})
    spec = DesignSpec("d", (factor,), ("Y",), ccd_alpha=2, ccd_axial_points=1)
    with pytest.raises(ValueError, match="轴点编码"):
        DesignResult(spec, (huge,))


def test_saturated_model_contract_forbids_residual_inference():
    with pytest.raises(ValueError, match="不得提供 t/p/F"):
        ModelResult(
            design_id="doe-demo", response_name="收率",
            coefficients={"Intercept": 50}, residual_df=0, saturated=True,
            inference_status="evaluated", f_statistic=3.2,
        )
    model = ModelResult(
        design_id="doe-demo", response_name="收率",
        coefficients={"Intercept": 50}, residual_df=0,
        independent_error_df=3, saturated=True,
        inference_status="unavailable_saturated",
    )
    with pytest.raises(TypeError):
        model.coefficients["Intercept"] = 0
    optimization = OptimizationResult("doe-demo", {"A": 15}, {"收率": 50})
    with pytest.raises(TypeError):
        optimization.factor_levels["A"] = 20


def test_independent_two_level_reference_fixture_has_known_effects():
    reference = json.loads((ROOT / "tests" / "fixtures" /
                            "doe_2x2_reference.json").read_text(encoding="utf-8"))
    rows = reference["rows"]
    assert [(row["A"], row["B"], row["Y"]) for row in rows] == [
        (-1, -1, 53), (-1, 1, 41), (1, -1, 51), (1, 1, 55),
    ]
    a_plus = [row["Y"] for row in rows if row["A"] == 1]
    a_minus = [row["Y"] for row in rows if row["A"] == -1]
    b_plus = [row["Y"] for row in rows if row["B"] == 1]
    b_minus = [row["Y"] for row in rows if row["B"] == -1]
    ab_plus = [row["Y"] for row in rows if row["A"] * row["B"] == 1]
    ab_minus = [row["Y"] for row in rows if row["A"] * row["B"] == -1]
    assert (sum(a_plus) - sum(a_minus)) / 2 == reference["effects"]["A"] == 6
    assert (sum(b_plus) - sum(b_minus)) / 2 == reference["effects"]["B"] == -4
    assert (sum(ab_plus) - sum(ab_minus)) / 2 == reference["effects"]["AB"] == 8
