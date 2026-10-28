import json
from pathlib import Path

import numpy as np
import pytest

from doe_core import DesignSpec, FactorSpec
from doe_splitplot import create_split_plot
from doe_splitplot_analysis import analyze_split_plot


REFERENCE = json.loads((Path(__file__).parent / "fixtures" / "doe_factorial_reference"
                        / "reference.json").read_text(encoding="utf-8"))["split_plot"]


def design():
    factors = (
        FactorSpec("A", "A", -1, 1, randomization_role="hard_to_change"),
        FactorSpec("B", "B", -1, 1, randomization_role="easy_to_change"),
    )
    return DesignSpec(
        "split-analysis", factors, ("Y",), seed=23, design_type="split_plot",
        block_count=3, randomization_unit="whole_plot", error_structure="split_plot",
    )


def reference_frame():
    spec = design()
    frame, metadata = create_split_plot(spec)
    factor_columns = metadata["column_map"]["factors"]
    responses = {(row["block"], row["A"], row["B"]): row["Y"]
                 for row in REFERENCE["rows"]}
    frame["响应_Y"] = [
        responses[(row["区组"],
                   int(spec.factors[0].to_coded(row[factor_columns["A"]])),
                   int(spec.factors[1].to_coded(row[factor_columns["B"]])))]
        for _, row in frame.iterrows()
    ]
    return frame, metadata


def test_anova_matches_independent_balanced_split_plot_reference():
    frame, metadata = reference_frame()
    result = analyze_split_plot(frame, metadata, "Y")
    expected = REFERENCE["expected"]
    anova = {row["term"]: row for row in result["anova"]}

    assert all({"term", "ss", "df", "ms", "f", "p", "error_stratum"} <= row.keys()
               for row in result["anova"])
    assert {name: anova[name]["df"] for name in expected["df"]} == expected["df"]
    for term in ("A", "B", "A:B"):
        assert anova[term]["ss"] == pytest.approx(expected["ss"][term])
        assert anova[term]["f"] == pytest.approx(expected["f"][term])
        assert anova[term]["p"] == pytest.approx(expected["p"][term])
    for term in ("whole_plot_error", "subplot_error"):
        assert anova[term]["ss"] == pytest.approx(expected["ss"][term])
    assert anova["A"]["error_stratum"] == "whole_plot_error"
    assert anova["B"]["error_stratum"] == anova["A:B"]["error_stratum"] == "subplot_error"
    assert anova["whole_plot_error"]["ms"] == pytest.approx(4)
    assert anova["subplot_error"]["ms"] == pytest.approx(14)
    assert result["n"] == 12
    assert len(result["fitted"]) == len(result["residuals"]) == 12
    assert np.isfinite(result["fitted"]).all()
    assert np.isfinite(result["residuals"]).all()
    assert result["status"]
    assert result["assumption"]


def test_analysis_rejects_missing_and_invalid_responses():
    frame, metadata = create_split_plot(design())
    with pytest.raises(ValueError, match="缺失"):
        analyze_split_plot(frame, metadata, "Y")
    with pytest.raises(ValueError, match="不属于"):
        analyze_split_plot(frame, metadata, "other")

    frame["响应_Y"] = ["invalid"] + [1.0] * (len(frame) - 1)
    with pytest.raises(ValueError):
        analyze_split_plot(frame, metadata, "Y")
