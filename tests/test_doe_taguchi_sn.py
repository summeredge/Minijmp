"""静态 Taguchi S/N 数值合同、响应表与边界。"""
import math

import pytest

from doe_core import DesignSpec, FactorSpec, restore_design_result
from doe_taguchi import create_taguchi
from doe_taguchi_arrays import ARRAYS
from doe_taguchi_sn import analyze_static, signal_to_noise


def factor(factor_id, levels):
    return FactorSpec(factor_id, factor_id, None, None, factor_type="categorical",
                      levels=tuple(levels), level_type="text")


def l8_spec(noise=None, noise_columns=None):
    array = ARRAYS["L8(2^7)"]
    noise_array = ARRAYS[noise] if noise else None
    return DesignSpec(
        "TG", tuple(factor(chr(65 + index), ("低", "高")) for index in range(4)),
        ("Y",), seed=5, design_type="taguchi",
        taguchi={"kind": "static", "array_id": "L8(2^7)",
                 "matrix_sha256": array.sha256,
                 "columns": {"A": 1, "B": 2, "C": 5, "D": 6},
                 "noise_array_id": noise,
                 "noise_matrix_sha256": None if noise_array is None else noise_array.sha256,
                 "noise_columns": noise_columns or {}, "signal_factor": None})


def l4_two_factor_spec():
    array = ARRAYS["L4(2^3)"]
    return DesignSpec(
        "TG", (factor("A", ("低", "高")), factor("B", ("低", "高"))),
        ("Y",), seed=5, design_type="taguchi",
        taguchi={"kind": "static", "array_id": array.array_id,
                 "matrix_sha256": array.sha256, "columns": {"A": 1, "B": 2},
                 "noise_array_id": None, "noise_matrix_sha256": None,
                 "noise_columns": {}, "signal_factor": None})


@pytest.mark.parametrize("kind,expected", [
    ("smaller", -10 * math.log10(2.5)),
    ("larger", -10 * math.log10(0.625)),
    ("nominal", 10 * math.log10(4.5)),
    ("nominal_ii", -10 * math.log10(0.5)),
])
def test_four_static_formulas_match_reference(kind, expected):
    assert signal_to_noise([1, 2], kind) == pytest.approx(expected, abs=1e-12)


def test_adjusted_nominal_formula_matches_reference():
    assert signal_to_noise([1, 2], "nominal", adjusted=True) == pytest.approx(
        10 * math.log10(4.0), abs=1e-12)
    with pytest.raises(ValueError, match="adjusted"):
        signal_to_noise([1, 2], "smaller", adjusted=True)


@pytest.mark.parametrize("values,kind,message", [
    ([], "smaller", "为空"),
    ([1.0, float("inf")], "smaller", "非有限"),
    ([1.0, float("nan")], "larger", "非有限"),
    ([0.0, 1.0], "larger", "不得为 0"),
    ([1.0], "nominal", "至少两个"),
    ([2.0, 2.0], "nominal", "方差为零"),
    ([0.0, 0.0], "smaller", "对数自变量"),
    ([1e308, 1e308], "smaller", "对数自变量"),
    ([1e-320, 1e-320], "larger", "对数自变量"),
])
def test_static_domain_errors_are_reported(values, kind, message):
    with pytest.raises(ValueError, match=message):
        signal_to_noise(values, kind)


def test_negative_response_is_legal_only_where_the_formula_allows_it():
    """smaller/nominal 用平方与方差，负值合法；larger 的倒数平方仍为正，也合法。"""
    assert signal_to_noise([-1, -2], "smaller") == pytest.approx(
        signal_to_noise([1, 2], "smaller"), abs=1e-12)
    assert signal_to_noise([-1, -2], "nominal") == pytest.approx(
        signal_to_noise([1, 2], "nominal"), abs=1e-12)
    assert signal_to_noise([-1, -2], "larger") == pytest.approx(
        signal_to_noise([1, 2], "larger"), abs=1e-12)


def test_l8_static_analysis_reproduces_analytic_main_effects():
    frame, metadata = create_taguchi(l8_spec(), replicates=2)
    design = restore_design_result(frame, metadata)
    values = {run.run_id: 20 + 4 * (-1 if run.settings["A"] == "低" else 1)
              - 3 * (-1 if run.settings["B"] == "低" else 1)
              + 2 * ((-1 if run.settings["A"] == "低" else 1)
                     * (-1 if run.settings["B"] == "低" else 1))
              + (0.5 if run.replicate == 1 else -0.5)
              for run in design.runs}
    frame["响应_Y"] = [values[run_id] for run_id in frame["运行ID"]]
    result = analyze_static(frame, metadata, "Y", "smaller")
    assert result["n_observations"] == 16
    assert len(result["combinations"]) == 8
    means = {}
    for row in result["combinations"]:
        means.setdefault(row["settings"]["A"], []).append(row["mean"])
    assert sum(means["低"]) / len(means["低"]) == pytest.approx(16.0)
    assert sum(means["高"]) / len(means["高"]) == pytest.approx(24.0)
    table = {row["factor_id"]: row for row in result["response_table"]["factors"]}
    c_means = [level["mean"] for level in table["C"]["levels"]]
    assert c_means[0] == pytest.approx(c_means[1])
    assert table["A"]["levels"][0]["mean"] == pytest.approx(16.0)
    assert table["A"]["levels"][1]["mean"] == pytest.approx(24.0)
    assert table["A"]["delta"] > table["B"]["delta"] > 0
    assert result["response_table"]["ranked"][0] == "A"


def test_level_effect_is_level_mean_minus_grand_mean():
    """效应列必须是水平值相对总平均的偏差，且同一因子内相加为零。"""
    frame, metadata = create_taguchi(l8_spec(), replicates=2)
    design = restore_design_result(frame, metadata)
    values = {run.run_id: 20 + 4 * (-1 if run.settings["A"] == "低" else 1)
              + (0.5 if run.replicate == 1 else -0.5)
              for run in design.runs}
    frame["响应_Y"] = [values[run_id] for run_id in frame["运行ID"]]
    result = analyze_static(frame, metadata, "Y", "smaller")
    levels = {row["factor_id"]: row["levels"]
              for row in result["response_table"]["factors"]}
    grand = sum(row["sn"] for row in result["combinations"]) / len(
        result["combinations"])
    for row in levels["A"]:
        assert row["effect"] == pytest.approx(row["sn"] - grand)
    assert sum(row["effect"] for row in levels["A"]) == pytest.approx(0.0, abs=1e-12)
    assert levels["C"][0]["effect"] == pytest.approx(levels["C"][1]["effect"])


def test_missing_response_and_unknown_response_are_rejected():
    frame, metadata = create_taguchi(l8_spec())
    with pytest.raises(ValueError, match="缺失"):
        analyze_static(frame, metadata, "Y")
    with pytest.raises(ValueError, match="不属于"):
        analyze_static(frame, metadata, "Z")


def test_replicate_observations_are_kept_and_averaged_per_combination():
    frame, metadata = create_taguchi(l8_spec(), replicates=2)
    design = restore_design_result(frame, metadata)
    assert len(design.runs) == 16
    frame["响应_Y"] = [1.0 + index * 0.5 for index in range(len(frame))]
    result = analyze_static(frame, metadata, "Y", "smaller")
    assert result["n_observations"] == 16
    assert {row["n"] for row in result["combinations"]} == {2}


@pytest.mark.parametrize("kind,adjusted", [
    ("nominal", False), ("nominal_ii", False), ("nominal", True),
])
def test_single_observation_combination_rejects_sample_variance(kind, adjusted):
    frame, metadata = create_taguchi(l8_spec())
    frame["响应_Y"] = 1.0
    with pytest.raises(ValueError, match="至少两个观测"):
        analyze_static(frame, metadata, "Y", kind, adjusted)


@pytest.mark.parametrize("kind,expected", [
    ("smaller", -10 * math.log10(4)),
    ("larger", -10 * math.log10(1 / 4)),
])
def test_l4_single_observation_sn_keeps_mean_and_marks_sd_unavailable(kind, expected):
    frame, metadata = create_taguchi(l4_two_factor_spec(), replicates=1)
    frame["响应_Y"] = 2.0
    result = analyze_static(frame, metadata, "Y", kind, ln_sd=True)
    assert result["n_observations"] == 4
    assert len(result["combinations"]) == 4
    assert all(row["n"] == 1 and row["mean"] == 2.0
               and row["sd"] is None and row["ln_sd"] is None
               and row["sn"] == pytest.approx(expected, abs=1e-12)
               for row in result["combinations"])
    assert all(level["mean"] == 2.0 and level["sd"] is None
               and level["ln_sd"] is None
               for factor_row in result["response_table"]["factors"]
               for level in factor_row["levels"])


def test_ln_sd_transform_is_explicit_and_keeps_sn_definition():
    frame, metadata = create_taguchi(l8_spec(), replicates=2)
    design = restore_design_result(frame, metadata)
    frame["响应_Y"] = [5.0 + 0.6 * (run.replicate - 1) for run in design.runs]
    plain = analyze_static(frame, metadata, "Y", "smaller")
    logged = analyze_static(frame, metadata, "Y", "smaller", ln_sd=True)
    assert [row["sn"] for row in plain["combinations"]] == [
        row["sn"] for row in logged["combinations"]]
    assert all(row["ln_sd"] is None for row in plain["combinations"])
    assert all(row["ln_sd"] is not None for row in logged["combinations"])
    assert [row["ln_sd"] for row in logged["combinations"]] != [
        row["sd"] for row in logged["combinations"]]
    assert logged["response_table"]["factors"][0]["levels"][0]["ln_sd"] is not None
    assert plain["response_table"]["factors"][0]["levels"][0]["ln_sd"] is None

