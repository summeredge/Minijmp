import json
from pathlib import Path

import numpy as np
import pytest
from scipy import stats

from doe_core import DesignSpec, FactorSpec
from doe_factorial import create_factorial
from doe_analysis import analyze_factorial
from doe_factorial_anova import partition_factorial_error


REFERENCE = json.loads((Path(__file__).parent / "fixtures" / "doe_factorial_reference"
                       / "reference.json").read_text(encoding="utf-8"))


def test_repeated_cells_are_pure_error_but_different_blocks_are_not():
    case = REFERENCE["block_factorial"]
    rows = case["rows"]
    partition = partition_factorial_error(
        np.asarray([row["Y"] for row in rows]),
        [(row["A"], row["B"]) for row in rows],
        [row["block"] for row in rows],
    )
    assert partition["pure_error_df"] == 0
    assert partition["pure_error_ss"] == pytest.approx(0)
    assert partition["block_error_df"] == case["expected"]["df"]["error"]
    assert partition["block_error_ss"] == pytest.approx(case["expected"]["ss"]["error"])

    repeated = partition_factorial_error([1, 3, 2, 4], ["A", "A", "B", "B"], None)
    assert repeated["pure_error_df"] == 2
    assert repeated["pure_error_ss"] == pytest.approx(4)
    assert repeated["block_error_df"] == 0


def test_two_level_anova_effects_and_terms_match_independent_effect_contract():
    spec = DesignSpec("effect-contract", (FactorSpec("A", "A", -1, 1),
                                           FactorSpec("B", "B", -1, 1)),
                      ("Y",), seed=1, design_type="two_level_full")
    frame, metadata = create_factorial(spec)
    a = frame["设定_A"].to_numpy(dtype=float)
    b = frame["设定_B"].to_numpy(dtype=float)
    frame["响应_Y"] = 50 + 3 * a - 2 * b + 4 * a * b

    result = analyze_factorial(frame, metadata, "Y", order=2)
    np.testing.assert_allclose(result["coefficients"], [50, 3, -2, 4], atol=1e-12)
    np.testing.assert_allclose(result["effects"][1:], [6, -4, 8], atol=1e-12)
    rows = {row["term"]: row for row in result["anova"]}
    assert {name: rows[name]["ss"] for name in ("A", "B", "A*B")} == pytest.approx(
        {"A": 36, "B": 16, "A*B": 64})
    assert {name: rows[name]["df"] for name in ("A", "B", "A*B")} == {
        "A": 1, "B": 1, "A*B": 1}
    assert all(rows[name]["f"] is None and rows[name]["p"] is None
               for name in ("A", "B", "A*B"))
    assert result["ssr"] == pytest.approx(116)
    assert result["sse"] == pytest.approx(0, abs=1e-12)
    assert result["sst"] == pytest.approx(116)


def test_block_factorial_term_tests_use_block_adjusted_error_not_pooled_cells():
    case = REFERENCE["block_factorial"]
    spec = DesignSpec("blocked", (FactorSpec("A", "A", -1, 1),
                                   FactorSpec("B", "B", -1, 1)),
                      ("Y",), seed=1, design_type="two_level_full",
                      block_count=3, randomization_unit="block")
    frame, metadata = create_factorial(spec, replicates=3)
    lookup = {(row["block"], row["A"], row["B"]): row["Y"] for row in case["rows"]}
    frame["响应_Y"] = [lookup[(int(block[1:]), a, b)]
                       for block, a, b in zip(frame["区组"], frame["设定_A"], frame["设定_B"])]

    result = analyze_factorial(frame, metadata, "Y", order=2)
    assert result["pure_error_df"] == 0
    assert result["pure_error_sse"] == pytest.approx(0)
    assert result["block_error_df"] == case["expected"]["df"]["error"]
    assert result["block_error_sse"] == pytest.approx(case["expected"]["ss"]["error"])
    assert result["lack_of_fit"] is None
    rows = {row["term"]: row for row in result["anova"]}
    for term, reference_term in (("A", "A"), ("B", "B"), ("A*B", "A:B")):
        assert rows[term]["ss"] == pytest.approx(case["expected"]["ss"][reference_term])
        assert rows[term]["f"] == pytest.approx(case["expected"]["f"][reference_term])
        assert rows[term]["p"] == pytest.approx(case["expected"]["p"][reference_term])
    assert rows["残差"]["df"] == case["expected"]["df"]["error"]
    assert rows["残差"]["ms"] == pytest.approx(8 / 6)


def test_replicated_reduced_model_lack_of_fit_uses_independent_pure_error():
    spec = DesignSpec("replicated", (FactorSpec("A", "A", -1, 1),
                                     FactorSpec("B", "B", -1, 1)),
                      ("Y",), seed=2, design_type="two_level_full")
    frame, metadata = create_factorial(spec, replicates=2)
    a = frame["设定_A"].to_numpy(dtype=float)
    b = frame["设定_B"].to_numpy(dtype=float)
    noise = np.where(frame["重复"].to_numpy() == 1, -1.0, 1.0)
    frame["响应_Y"] = 50 + 3*a - 2*b + 4*a*b + noise

    result = analyze_factorial(frame, metadata, "Y", order=1)
    assert result["pure_error_df"] == 4
    assert result["pure_error_sse"] == pytest.approx(8)
    assert result["lack_of_fit_df"] == 1
    assert result["lack_of_fit_sse"] == pytest.approx(128)
    assert result["lack_of_fit"]["f"] == pytest.approx(64)
    assert result["lack_of_fit"]["p"] == pytest.approx(stats.f.sf(64, 1, 4))


def test_center_points_in_different_blocks_do_not_supply_curvature_pure_error():
    spec = DesignSpec("blocked-centers", (FactorSpec("A", "A", -1, 1),
                                           FactorSpec("B", "B", -1, 1)),
                      ("Y",), seed=9, design_type="two_level_full", block_count=3,
                      randomization_unit="block")
    frame, metadata = create_factorial(spec, replicates=3, center_points=3)
    values = []
    for _, row in frame.iterrows():
        a, b = float(row["设定_A"]), float(row["设定_B"])
        block = int(row["区组"][1:]) - 2
        base = 20 if row["点类型"] == "center" else 10 + 3*a - 2*b + 4*a*b
        values.append(base + block + block*a)
    frame["响应_Y"] = values

    result = analyze_factorial(frame, metadata, "Y", order=2)
    assert result["pure_error_df"] == 0
    assert result["block_error_df"] == 8
    assert result["block_error_sse"] == pytest.approx(8)
    assert result["lack_of_fit_df"] == 0
    assert result["curvature"]["difference"] == pytest.approx(10)
    assert result["curvature"]["f"] is None
