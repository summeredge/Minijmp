from itertools import combinations, product
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from doe_analysis import analyze_factorial
from doe_core import DesignSpec, FactorSpec
from doe_factorial import create_factorial, validate_factorial_design
from doe_fractional import create_fractional, validate_fractional_design
from doe_fractional_analysis import analyze_fractional
from doe_foldover import create_foldover
from doe_general_factorial import create_general_factorial
from doe_general_factorial_analysis import analyze_general_factorial


REFERENCE = json.loads((Path(__file__).parent / "fixtures" / "doe_factorial_reference"
                       / "reference.json").read_text(encoding="utf-8"))


def full_spec(*, seed=23, blocks=3):
    return DesignSpec(
        "blocked-full", (FactorSpec("A", "A", -1, 1),
                         FactorSpec("B", "B", -1, 1)), ("Y",), seed=seed,
        design_type="two_level_full", block_count=blocks,
        randomization_unit="block")


def fractional_spec(*, seed=23, blocks=3):
    return DesignSpec(
        "blocked-fraction", tuple(FactorSpec(key, key, -1, 1) for key in "ABC"),
        ("Y",), seed=seed, generators=("C=AB",),
        design_type="two_level_fractional", block_count=blocks,
        randomization_unit="block")


def coded(run, spec):
    return tuple(int(factor.to_coded(run.settings[factor.factor_id]))
                 for factor in spec.factors)


def test_full_factorial_replicates_are_complete_consecutive_blocks_and_randomized():
    spec = full_spec()
    frame, metadata = create_factorial(spec, replicates=3, center_points=3)
    design = validate_factorial_design(frame, metadata)

    assert len(frame) == 15
    assert frame["区组"].nunique() == 3
    assert set(frame.groupby("区组").size()) == {5}
    assert frame.groupby("区组")["点类型"].apply(lambda x: (x == "center").sum()).to_dict() == {
        f"B{i}": 1 for i in range(1, 4)}
    for block in ("B1", "B2", "B3"):
        runs = [run for run in design.runs if run.block == block]
        assert {coded(run, spec) for run in runs if run.point_type == "factorial"} == set(
            product((-1, 1), repeat=2))
        orders = sorted(run.run_order for run in runs)
        assert orders == list(range(orders[0], orders[0] + len(runs)))
    assert set(frame["运行序"]) == set(range(1, 16))
    assert validate_factorial_design(frame, metadata).spec.block_count == 3


def test_full_factorial_block_model_matches_independent_block_reference():
    spec = full_spec()
    frame, metadata = create_factorial(spec, replicates=3)
    reference = REFERENCE["block_factorial"]
    responses = {(row["block"], row["A"], row["B"]): row["Y"]
                 for row in reference["rows"]}
    design = validate_factorial_design(frame, metadata)
    values = []
    for run in design.runs:
        a, b = coded(run, spec)
        values.append(responses[(int(run.block[1:]), a, b)])
    frame["响应_Y"] = pd.array(values, dtype="Float64")

    result = analyze_factorial(frame, metadata, "Y", order=2)
    expected = reference["expected"]
    assert result["block_df"] == expected["df"]["block"]
    assert result["block_ss"] == pytest.approx(expected["ss"]["block"])
    assert result["sse"] == pytest.approx(expected["ss"]["error"])
    assert result["df"] == expected["df"]["error"]
    assert result["pure_error_df"] == 0
    assert result["block_error_df"] == expected["df"]["error"]
    assert result["block_error_sse"] == pytest.approx(expected["ss"]["error"])
    assert result["lack_of_fit_df"] == 0
    assert result["lack_of_fit"] is None


def test_factorial_treatment_contrasts_are_orthogonal_to_complete_blocks():
    frame, metadata = create_factorial(full_spec(), replicates=3)
    design = validate_factorial_design(frame, metadata)
    matrix = np.asarray([coded(run, design.spec) for run in design.runs])
    blocks = np.asarray([run.block for run in design.runs])
    terms = [term for degree in range(1, 3)
             for term in combinations(range(2), degree)]
    for term in terms:
        column = np.prod(matrix[:, term], axis=1)
        assert all(np.sum(column[blocks == block]) == 0 for block in set(blocks))


def test_regular_fraction_blocks_include_complete_fractions_and_adjust_analysis():
    spec = fractional_spec()
    frame, metadata = create_fractional(spec, replicates=3, center_points=3)
    design = validate_fractional_design(frame, metadata)
    assert frame["区组"].nunique() == 3
    assert set(frame.groupby("区组").size()) == {5}
    for block in ("B1", "B2", "B3"):
        runs = [run for run in design.runs if run.block == block]
        assert len([run for run in runs if run.point_type == "factorial"]) == 4
        assert sum(run.point_type == "center" for run in runs) == 1

    values = []
    for run in design.runs:
        a, b, _ = coded(run, spec)
        block_effect = int(run.block[1:]) - 2
        values.append(20 + 2*a - 3*b + block_effect)
    frame["响应_Y"] = pd.array(values, dtype="Float64")
    result = analyze_fractional(frame, metadata, "Y", order=1)
    assert result["block_df"] == 2
    assert result["block_ss"] == pytest.approx(10)
    assert result["pure_error_df"] == 0
    assert result["block_error_df"] == 8
    assert result["lack_of_fit_df"] == 0
    assert result["lack_of_fit"] is None
    assert result["rank"] == result["p"]
    with pytest.raises(ValueError, match="Foldover.*区组"):
        create_foldover(frame, metadata, "A")


def test_fractional_block_treatment_contrasts_are_orthogonal():
    spec = fractional_spec()
    frame, metadata = create_fractional(spec, replicates=3)
    design = validate_fractional_design(frame, metadata)
    matrix = np.asarray([coded(run, spec) for run in design.runs])
    blocks = np.asarray([run.block for run in design.runs])
    for term in ((), (0,), (1,), (2,), (0, 1), (0, 2), (1, 2), (0, 1, 2)):
        column = (np.ones(len(matrix)) if not term else np.prod(matrix[:, term], axis=1))
        assert all(np.sum(column[blocks == block]) == np.sum(column) / 3
                   for block in set(blocks))


def test_block_creation_rejects_unequal_replicates_and_center_allocation():
    with pytest.raises(ValueError, match="完整重复"):
        create_factorial(full_spec(blocks=2), replicates=3)
    with pytest.raises(ValueError, match="平均分配"):
        create_factorial(full_spec(), replicates=3, center_points=2)
    with pytest.raises(ValueError, match="完整重复"):
        create_fractional(fractional_spec(blocks=2), replicates=3)
    with pytest.raises(ValueError, match="平均分配"):
        create_fractional(fractional_spec(), replicates=3, center_points=2)


def test_general_factorial_block_anova_matches_independent_projection():
    factors = (
        FactorSpec("A", "配方", None, None, factor_type="categorical",
                   levels=("low", "high")),
        FactorSpec("B", "温度", None, None, factor_type="categorical",
                   levels=(100, 150, 200), level_type="numeric"),
    )
    spec = DesignSpec("blocked-general", factors, ("Y",), seed=23,
                      design_type="general_full_factorial", block_count=3,
                      randomization_unit="block")
    frame, metadata = create_general_factorial(spec, replicates=3)
    for index, row in frame.iterrows():
        block = int(row["区组"][1:])
        a = -1 if row["设定_A"] == "low" else 1
        b = {100: -1, 150: 0, 200: 1}[row["设定_B"]]
        frame.loc[index, "响应_Y"] = 10 + 2*a + 3*b + 4*a*b + block
    result = analyze_general_factorial(frame, metadata, "Y", order=2)
    expected_block_ss = 6 * sum((i - 2) ** 2 for i in (1, 2, 3))
    row = next(item for item in result["anova"] if item["term"] == "区组")
    assert row["df"] == 2
    assert row["ss"] == pytest.approx(expected_block_ss)
    assert result["rank"] == 8
    assert result["pure_error_df"] == 0
    assert result["block_error_df"] == 10
    assert result["lack_of_fit_df"] == 0
    assert result["lack_of_fit"] is None
