import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from statsmodels.formula.api import ols
from statsmodels.stats.anova import anova_lm

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
    type_iii = analyze_general_factorial(frame, metadata, "Y", order=2, ss_type="III")
    type_iii_terms = {row["term"]: row for row in type_iii["anova"]}
    for name in ("A", "B", "A*B"):
        assert type_iii_terms[name]["ss"] == pytest.approx(terms[name]["ss"])
        assert type_iii_terms[name]["df"] == terms[name]["df"]
        assert type_iii_terms[name]["f"] == pytest.approx(terms[name]["f"])
        assert type_iii_terms[name]["p"] == pytest.approx(terms[name]["p"])
        assert type_iii_terms[name]["estimable"] is True
    assert type_iii["ss_type"] == "III"
    assert len(type_iii["inference"]["se"]) == len(type_iii["coefficients"])
    assert "基准水平列为 -1" in type_iii["assumption"]

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
    type_iii = analyze_general_factorial(frame, metadata, "Y", order=2, ss_type="III")
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
    reference_data = pd.DataFrame({
        "Y": frame["响应_Y"], "A": frame["设定_A"], "B": frame["设定_B"],
        "block": frame["区组"],
    })
    expected = anova_lm(
        ols("Y ~ C(block, Sum) + C(A, Sum) * C(B, Sum)",
            data=reference_data).fit(), typ=3)
    type_iii_terms = {row["term"]: row for row in type_iii["anova"]}
    for name, reference_name in (
            ("区组", "C(block, Sum)"), ("A", "C(A, Sum)"),
            ("B", "C(B, Sum)"), ("A*B", "C(A, Sum):C(B, Sum)")):
        assert type_iii_terms[name]["ss"] == pytest.approx(expected.loc[reference_name, "sum_sq"])
        assert type_iii_terms[name]["df"] == expected.loc[reference_name, "df"]
        assert type_iii_terms[name]["f"] == pytest.approx(expected.loc[reference_name, "F"])
        assert type_iii_terms[name]["p"] == pytest.approx(expected.loc[reference_name, "PR(>F)"])


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
    saturated = analyze_general_factorial(frame, metadata, "Y", order=2, ss_type="III")
    assert saturated["df"] == 0 and saturated["inference"] is None
    assert all(row["f"] is None and row["p"] is None
               for row in saturated["anova"] if row["term"] not in ("误差", "总计"))


def test_type_iii_missing_run_matches_statsmodels_anova_lm():
    factors = (
        FactorSpec("A", "开关", None, None, factor_type="categorical",
                   levels=("off", "on")),
        FactorSpec("B", "温度", None, None, factor_type="categorical",
                   levels=(100, 150, 200), level_type="numeric"),
    )
    frame, metadata = create_general_factorial(
        DesignSpec("unbalanced", factors, ("Y",), seed=19,
                   design_type="general_full_factorial"), replicates=3)
    a = frame["设定_A"].tolist()
    b = frame["设定_B"].tolist()
    replicate = frame["重复"].to_numpy(dtype=int)
    a_code = np.asarray([1 if value == "on" else -1 for value in a])
    b_code = np.asarray([{100: -1, 150: 0, 200: 1}[value] for value in b])
    noise = np.choose(replicate - 1, [-1.2, .35, 1.4]) * (1 + .1*a_code - .08*b_code)
    y = 25 + 2*a_code + b_code - 1.5*a_code*b_code + noise
    frame["响应_Y"] = y
    frame.loc[frame.index[0], "响应_Y"] = None
    reference = pd.DataFrame({"Y": y, "A": a, "B": b})
    reference.loc[reference.index[0], "Y"] = np.nan
    expected = anova_lm(
        ols("Y ~ C(A, Sum) * C(B, Sum)", data=reference).fit(), typ=3)

    result = analyze_general_factorial(frame, metadata, "Y", order=2, ss_type="III")
    rows = {row["term"]: row for row in result["anova"]}
    for name, reference_name in (
            ("A", "C(A, Sum)"), ("B", "C(B, Sum)"),
            ("A*B", "C(A, Sum):C(B, Sum)")):
        assert rows[name]["ss"] == pytest.approx(expected.loc[reference_name, "sum_sq"])
        assert rows[name]["df"] == expected.loc[reference_name, "df"]
        assert rows[name]["f"] == pytest.approx(expected.loc[reference_name, "F"])
        assert rows[name]["p"] == pytest.approx(expected.loc[reference_name, "PR(>F)"])
        assert rows[name]["estimable"] is True
    assert result["n"] == len(frame) - 1
    assert len(result["design"].runs) == len(frame)
    assert result["observed_runs"] == tuple(
        run for run in result["design"].runs if run.responses["Y"] is not None)
    assert len(result["fitted"]) == len(result["residuals"]) == result["n"]
    assert all("estimable" in row and "status" in row for row in result["anova"])
    with pytest.raises(ValueError, match="缺失值"):
        analyze_general_factorial(frame, metadata, "Y", order=2)


def test_type_iii_missing_cell_keeps_empty_cell_mean_and_marks_rank_deficiency():
    factors = (
        FactorSpec("A", "A", None, None, factor_type="categorical", levels=("off", "on")),
        FactorSpec("B", "B", None, None, factor_type="categorical",
                   levels=(100, 150, 200), level_type="numeric"),
    )
    frame, metadata = create_general_factorial(
        DesignSpec("empty-cell", factors, ("Y",), seed=23,
                   design_type="general_full_factorial"), replicates=2)
    replicate = frame["重复"].to_numpy(dtype=int)
    y = []
    for a, b, rep in zip(frame["设定_A"], frame["设定_B"], replicate):
        a_code = 1 if a == "on" else -1
        b_code = {100: -1, 150: 0, 200: 1}[b]
        y.append(None if a == "on" and b == 200 else
                 12 + 2*a_code - b_code + a_code*b_code + (rep - 1.5))
    frame["响应_Y"] = y

    result = analyze_general_factorial(frame, metadata, "Y", order=2, ss_type="III")
    missing_cell = next(item for item in result["cell_means"]
                        if item["levels"] == {"A": "on", "B": 200})
    assert missing_cell["mean"] is None and missing_cell["n"] == 0
    observed_on = [value for a, value in zip(frame["设定_A"], frame["响应_Y"])
                   if a == "on" and not pd.isna(value)]
    on_mean = next(item for item in result["marginal_means"]
                   if item["factor_id"] == "A" and item["level"] == "on")
    assert on_mean["n"] == 4
    assert on_mean["mean"] == pytest.approx(np.mean(observed_on))
    absent_ids = {run.run_id for run in result["design"].runs
                  if run.settings["A"] == "on" and run.settings["B"] == 200}
    assert not absent_ids.intersection(run.run_id for run in result["observed_runs"])
    assert result["design"].runs and len(result["design"].runs) == len(frame)
    assert result["n"] == len(frame) - 2
    assert len(result["fitted"]) == len(result["residuals"]) == result["n"]
    assert result["rank"] < result["p"] and result["df"] > 0
    assert result["inference"] is not None
    coefficient_ranges = {"A": range(1, 2), "B": range(2, 4), "A*B": range(4, 6)}
    unestimable = [row for row in result["anova"]
                   if row["term"] in coefficient_ranges and not row["estimable"]]
    assert unestimable
    for row in result["anova"]:
        assert "estimable" in row and "status" in row
        if row["term"] in coefficient_ranges and not row["estimable"]:
            assert all(row[key] is None for key in ("ss", "ms", "f", "p"))
            assert row["df"] >= 0
            assert all(result["coefficients"][index] is None
                       for index in coefficient_ranges[row["term"]])


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
