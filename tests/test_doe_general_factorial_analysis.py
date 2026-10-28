import json
from pathlib import Path

import pytest

from doe_core import DesignSpec, FactorSpec
from doe_general_factorial import create_general_factorial
from doe_general_factorial_analysis import analyze_general_factorial


def reference():
    path = Path(__file__).parent / "fixtures" / "doe_factorial_reference" / "reference.json"
    return json.loads(path.read_text(encoding="utf-8"))


def set_responses(frame, values, keys, target):
    lookup = {tuple(row[key] for key in keys): row["Y"] for row in values}
    for index, row in frame.iterrows():
        key = tuple(row[target[key]] for key in keys)
        frame.loc[index, "响应_Y"] = lookup[key]


def test_2x3_anova_and_lack_of_fit_match_independent_contrasts():
    case = reference()["general_full_factorial"]["two_by_three"]
    factors = (
        FactorSpec("A", "A", None, None, factor_type="categorical", levels=("low", "high")),
        FactorSpec("B", "B", None, None, factor_type="categorical",
                   levels=(100, 150, 200), level_type="numeric"),
    )
    frame, metadata = create_general_factorial(
        DesignSpec("two-by-three", factors, ("Y",), seed=1,
                   design_type="general_full_factorial"), replicates=2)
    set_responses(frame, case["rows"], ("A", "B", "replicate"),
                  {"A": "设定_A", "B": "设定_B", "replicate": "重复"})

    full = analyze_general_factorial(frame, metadata, "Y", order=2)
    terms = {row["term"]: row for row in full["anova"]}
    for name, fixture_name in (("A", "A"), ("B", "B"), ("A*B", "A:B")):
        assert terms[name]["ss"] == pytest.approx(case["expected"]["full_model_ss"][fixture_name])
        assert terms[name]["df"] == case["expected"]["full_model_df"][fixture_name]
        assert terms[name]["f"] == pytest.approx(case["expected"]["full_model_f"][fixture_name])
    assert full["pure_error_df"] == 6
    assert full["pure_error_sse"] == pytest.approx(12)

    additive = analyze_general_factorial(frame, metadata, "Y", order=1)
    assert additive["lack_of_fit_df"] == 2
    assert additive["lack_of_fit_sse"] == pytest.approx(128)
    assert additive["lack_of_fit"]["f"] == pytest.approx(32)
    assert additive["lack_of_fit"]["p"] == pytest.approx(
        case["expected"]["additive_model"]["lack_of_fit_p"])


def test_numeric_labels_are_modeled_as_two_df_categorical_factor():
    case = reference()["general_full_factorial"]["numeric_categorical"]
    factor = FactorSpec("T", "温度", None, None, factor_type="categorical",
                        levels=(100, 150, 200), level_type="numeric")
    # 单因子一般全因子已明确拒绝；第二因子与响应无关，保留同一 T 边际均值。
    second = FactorSpec("S", "批次", None, None, factor_type="categorical",
                        levels=("s1", "s2"))
    frame, metadata = create_general_factorial(
        DesignSpec("numeric-levels", (factor, second), ("Y",), seed=2,
                   design_type="general_full_factorial"), replicates=3)
    by_key = {(row["T"], row["replicate"]): row["Y"] for row in case["rows"]}
    for index, row in frame.iterrows():
        frame.loc[index, "响应_Y"] = by_key[(row["设定_T"], row["重复"])]
    result = analyze_general_factorial(frame, metadata, "Y", order=1)
    row = next(row for row in result["anova"] if row["term"] == "T")
    assert row["df"] == case["categorical_df"] == 2
    assert [item["mean"] for item in result["marginal_means"]
            if item["factor_id"] == "T"] == [10, 20, 50]
    assert result["lack_of_fit"]["df"] == 2


def test_complete_block_general_factorial_adjusts_block_and_treatment_terms():
    case = reference()["block_factorial"]
    factors = tuple(FactorSpec(name, name, None, None, factor_type="categorical",
                               levels=(-1, 1), level_type="numeric") for name in ("A", "B"))
    frame, metadata = create_general_factorial(
        DesignSpec("blocked", factors, ("Y",), seed=7,
                   design_type="general_full_factorial", block_count=3,
                   randomization_unit="block"), replicates=3)
    by_cell = {(row["block"], row["A"], row["B"]): row["Y"] for row in case["rows"]}
    for index, row in frame.iterrows():
        key = (int(row["区组"][1:]), row["设定_A"], row["设定_B"])
        frame.loc[index, "响应_Y"] = by_cell[key]
    result = analyze_general_factorial(frame, metadata, "Y", order=2)
    terms = {row["term"]: row for row in result["anova"]}
    for name, fixture_name in (("A", "A"), ("B", "B"), ("A*B", "A:B")):
        item = terms[name]
        assert item["ss"] == pytest.approx(case["expected"]["ss"][fixture_name])
        assert item["f"] == pytest.approx(case["expected"]["f"][fixture_name])
    assert result["pure_error_df"] == 0
    assert result["pure_error_sse"] == pytest.approx(0)
    assert result["block_error_df"] == 6
    assert result["block_error_sse"] == pytest.approx(8)
    assert result["lack_of_fit_df"] == 0
    assert result["lack_of_fit"] is None


def test_without_independent_error_analysis_does_not_emit_significance():
    factors = (
        FactorSpec("A", "A", None, None, factor_type="categorical", levels=("x", "y")),
        FactorSpec("B", "B", None, None, factor_type="categorical", levels=("x", "y")),
    )
    frame, metadata = create_general_factorial(
        DesignSpec("unreplicated", factors, ("Y",), seed=4,
                   design_type="general_full_factorial"))
    frame["响应_Y"] = [1, 2, 3, 4]
    result = analyze_general_factorial(frame, metadata, "Y", order=1)
    assert result["inference"] is None
    assert all(row["p"] is None for row in result["anova"])


def test_analysis_rejects_oversized_dense_model_before_allocating_contrasts(monkeypatch):
    import doe_general_factorial_analysis as analysis

    factors = (
        FactorSpec("A", "A", None, None, factor_type="categorical",
                   levels=tuple(range(1700)), level_type="numeric"),
        FactorSpec("B", "B", None, None, factor_type="categorical",
                   levels=(0, 1), level_type="numeric"),
    )
    frame, metadata = create_general_factorial(
        DesignSpec("large-model", factors, ("Y",), seed=3,
                   design_type="general_full_factorial"))
    frame["响应_Y"] = 1.0
    monkeypatch.setattr(analysis, "_contrast_basis",
                        lambda *_: pytest.fail("model allocation happened before size guard"))
    with pytest.raises(ValueError, match="1000 万个单元"):
        analysis.analyze_general_factorial(frame, metadata, "Y", order=2)
