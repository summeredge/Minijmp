import json
from dataclasses import replace
from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest

from doe_augment import augment_mixture
from doe_mixture import MixtureSpec, mixture_metadata, restore_mixture
from doe_mixture_analysis import analyze_mixture
from doe_mixture_constraints import ComponentSpec, VariableSpec
from doe_mixture_designs import create_mixture_design, validate_mixture_design
from doe_mixture_model import MixtureTermModel
from doe_mixture_optimize import optimize_mixture
from doe_mixture_predict import predict_mixture


REFERENCE = json.loads((Path(__file__).parent / "fixtures"
                        / "doe_phase2_p4bc_reference" / "reference.json").read_text(
                            encoding="utf-8"))
COMPONENTS = tuple(ComponentSpec(key, key) for key in ("A", "B", "C"))


def cross_spec(case_id):
    process = ()
    amount_levels = None
    if case_id in ("C1", "C3"):
        process = tuple(VariableSpec(key, key, 1, 2)
                        for key in ("P1", "P2"))
    if case_id == "C1":
        amount = (VariableSpec("T", "T", 50, 200, role="amount"),)
        settings = (("T", 120),)
        version = "v1"
    elif case_id == "C2":
        amount = (VariableSpec("T", "T", 50, 150, role="amount"),)
        settings = (("T", 100),)
        amount_levels = (50, 100, 150)
        version = "v2"
    else:
        amount = (VariableSpec("T", "T", 80, 120, role="amount"),)
        settings = (("T", 80),)
        amount_levels = (80, 120)
        version = "v2"
    return (MixtureSpec(
        f"MIX-{case_id}", COMPONENTS, ("Y",), "simplex_lattice", 2,
        process_variables=process, amount_variables=amount,
        amount_settings=settings, seed=9, construction_version=version), amount_levels)


def _point(row):
    return tuple(round(float(row[f"设定_{key}"]), 12) for key in ("A", "B", "C"))


def _expected_cross(case_id):
    case = REFERENCE["mixture_lattice_crosses"][case_id]
    return {
        (_point_from_fraction(row["proportions"]),
         tuple(sorted(row["process"].items())), row.get("amount_level"))
        for row in case["runs"]
    }


def _point_from_fraction(values):
    return tuple(round(float(Fraction(value)), 12) for value in values)


@pytest.mark.parametrize("case_id,expected_runs", [("C1", 24), ("C2", 18), ("C3", 48)])
def test_designs_match_independent_mixture_process_amount_cross(case_id, expected_runs):
    spec, amount_levels = cross_spec(case_id)
    frame, metadata = create_mixture_design(spec, amount_levels=amount_levels)
    assert len(frame) == expected_runs
    assert frame["运行ID"].is_unique
    actual = {
        (_point(row), tuple(sorted(
            (key, row[f"设定_{key}"]) for key in ("P1", "P2")
            if f"设定_{key}" in row.index)),
         row["设定_T"] if case_id in ("C2", "C3") else None)
        for _, row in frame.iterrows()
    }
    assert actual == _expected_cross(case_id)
    assert validate_mixture_design(spec, frame)["runs"] == expected_runs
    restored, rows = restore_mixture(frame, metadata["mixture"])
    assert restored.construction_version == spec.construction_version
    assert len(rows) == expected_runs

    if case_id in ("C2", "C3"):
        assert set(frame["设定_T"]) == set(amount_levels)
        assert dict(spec.amount_settings)["T"] in set(amount_levels)
        for _, row in frame.iterrows():
            total = row["设定_T"]
            assert sum(row[f"设定_{key}"] * total for key in ("A", "B", "C")) \
                == pytest.approx(total)


def test_mixture_v1_keeps_existing_four_process_variable_support():
    processes = tuple(VariableSpec(f"P{index}", f"P{index}", 0, 1)
                      for index in range(1, 5))
    spec = MixtureSpec("MIX-V1", COMPONENTS[:2], ("Y",), "simplex_lattice", 1,
                       process_variables=processes)
    frame, metadata = create_mixture_design(spec)
    assert spec.construction_version == "v1"
    assert len(frame) == 2 * 2 ** 4
    assert restore_mixture(frame, metadata["mixture"])[0] == spec


def test_mixture_v2_seed_changes_run_order_not_joint_design_points():
    spec, amount_levels = cross_spec("C3")
    first, _ = create_mixture_design(spec, amount_levels=amount_levels)
    second, _ = create_mixture_design(
        replace(spec, seed=spec.seed + 1), amount_levels=amount_levels)
    columns = [f"设定_{key}" for key in ("A", "B", "C", "P1", "P2", "T")]
    first_order = [tuple(row) for row in first[columns].itertuples(index=False, name=None)]
    second_order = [tuple(row) for row in second[columns].itertuples(index=False, name=None)]
    first_points, second_points = sorted(first_order), sorted(second_order)
    assert first_points == second_points
    assert first_order != second_order


def joint_model_data():
    section = REFERENCE["joint_mixture_process_amount_model"]
    spec = MixtureSpec(
        "MIX-JOINT", COMPONENTS, ("Y",), "simplex_lattice", 2,
        process_variables=tuple(VariableSpec(key, key, 1, 2)
                                for key in ("P1", "P2")),
        amount_variables=(VariableSpec("T", "T", 100, 200, role="amount"),),
        amount_settings=(("T", 150),), seed=17, construction_version="v2")
    frame, _ = create_mixture_design(spec, amount_levels=(100, 150, 200))
    rows = {(
        tuple(round(float(value), 12) for value in item["proportions"]),
        tuple(item["process_codes"]), item["amount_code"]): index
        for index, item in enumerate(section["rows"])}

    def key(row):
        proportions = tuple(round(float(row[f"设定_{key}"]), 12)
                            for key in ("A", "B", "C"))
        process_codes = tuple(-1 if row[f"设定_P{index}"] == 1 else 1
                              for index in (1, 2))
        amount_code = 2 * (row["设定_T"] - 100) / 100 - 1
        return proportions, process_codes, amount_code

    response_by_key = {row_key: section["responses"][index]
                       for row_key, index in rows.items()}
    frame["响应_Y"] = [response_by_key[key(row)] for _, row in frame.iterrows()]
    return spec, frame, mixture_metadata(frame, spec), section


def test_joint_model_matches_independent_matrix_rank_condition_and_prediction():
    spec, frame, metadata, reference = joint_model_data()
    ordered = frame.sort_values("标准序")
    model = MixtureTermModel(spec, degree=2)
    actual_rows = [
        {component.component_id: row[f"设定_{component.component_id}"]
         for component in spec.components}
        | {variable.variable_id: row[f"设定_{variable.variable_id}"]
           for variable in (*spec.process_variables, *spec.amount_variables)}
        for _, row in ordered.iterrows()]
    matrix = model.matrix(actual_rows)
    reference_rows = {
        (tuple(round(float(value), 12) for value in item["proportions"]),
         tuple(item["process_codes"]), item["amount_code"]): row
        for item, row in zip(reference["rows"], reference["matrix"])}
    expected_matrix = [reference_rows[(
        tuple(round(float(row[key]), 12) for key in ("A", "B", "C")),
        tuple(-1 if row[f"P{index}"] == 1 else 1 for index in (1, 2)),
        2 * (row["T"] - 100) / 100 - 1)] for row in actual_rows]
    np.testing.assert_allclose(matrix, expected_matrix, rtol=0, atol=1e-12)
    expected_terms = [term.replace("x1", "A").replace("x2", "B").replace("x3", "C")
                      .replace("p1", "P1").replace("p2", "P2")
                      .replace("amount", "T") for term in reference["terms"]]
    assert model.names == expected_terms

    result = analyze_mixture(frame, metadata, "Y")
    assert (result["n"], result["p"], result["rank"], result["df"]) == (72, 15, 15, 57)
    assert result["condition_number"] == pytest.approx(
        reference["expected"]["condition_number_2"], rel=1e-10)
    np.testing.assert_allclose(result["coefficients"], reference["estimated_beta"],
                               rtol=0, atol=1e-9)
    assert result["sse"] == pytest.approx(reference["expected"]["sse"], abs=1e-9)
    assert all(result["estimable"])

    target = reference["expected"]["prediction"]
    prediction = predict_mixture(
        frame, metadata, "Y",
        [float(Fraction(value)) for value in target["input"]["proportions"]],
        {"P1": 1, "P2": 2}, {"T": 175})
    assert prediction["prediction"] == pytest.approx(target["value"], abs=1e-9)
    assert prediction["proportions"] == {"A": 1 / 3, "B": 1 / 3, "C": 1 / 3}
    assert prediction["actual_amounts"] == pytest.approx(
        {"A": 175 / 3, "B": 175 / 3, "C": 175 / 3})
    assert sum(prediction["actual_amounts"].values()) == pytest.approx(175)

    optimized = optimize_mixture(
        frame, metadata,
        [{"response": "Y", "goal": "maximize", "lower": -1000, "upper": 1000}],
        {"P1": 1, "P2": 2, "T": 175})
    assert optimized["settings"]["P1"] == 1
    assert optimized["settings"]["P2"] == 2
    assert optimized["settings"]["T"] == 175
    assert sum(optimized["actual_amounts"].values()) == pytest.approx(175)


def test_joint_model_rejects_rank_deficiency_and_invalid_amount_cross():
    spec, frame, metadata, _ = joint_model_data()
    collinear_terms = ["A", "B", "C", "A*P1", "B*P1", "C*P1", "P1"]
    with pytest.raises(ValueError, match="模型不可估计（秩"):
        analyze_mixture(frame, metadata, "Y", terms=collinear_terms, degree=1)

    broken = frame.copy(deep=True)
    index = broken.index[0]
    broken.loc[index, "设定_T"] = (150 if broken.loc[index, "设定_T"] != 150 else 100)
    broken_metadata = mixture_metadata(broken, spec)
    with pytest.raises(ValueError, match="总量设定与设计定义不一致"):
        restore_mixture(broken, broken_metadata)

    with pytest.raises(ValueError, match="2–3 个总量水平"):
        create_mixture_design(spec, amount_levels=(150,))
    with pytest.raises(ValueError, match="有限正数"):
        create_mixture_design(spec, amount_levels=(0, 150))
    close_spec = replace(spec, amount_settings=(("T", 100),))
    with pytest.raises(ValueError, match="间距必须大于"):
        create_mixture_design(close_spec, amount_levels=(100, 100 + 5e-10, 200))


def test_improvement_uses_metadata_schema2_without_upgrading_mixture_spec_or_doe():
    from test_doe_mixture_improve import _improve

    _, _, _, (frame, doe, mixture, _, _) = _improve()
    assert mixture['schema_version'] == 2
    assert mixture['spec']['schema_version'] == 1
    assert doe['schema_version'] == 5
    restored, rows = restore_mixture(frame, mixture, doe)
    assert restored.construction_version == 'v1'
    assert len(rows) == 3
    with pytest.raises(ValueError, match='必须关联 DOE Schema v5'):
        restore_mixture(frame, mixture)


def test_v2_append_uses_doe_v5_lineage_without_changing_schema1():
    spec, amount_levels = cross_spec('C3')
    parent, parent_meta = create_mixture_design(spec, amount_levels=amount_levels)
    candidate_spec = replace(spec, design_id='MIX-C3-CANDIDATES')
    candidates, candidate_meta = create_mixture_design(
        candidate_spec, amount_levels=amount_levels)
    result, result_doe, result_mixture, _, report = augment_mixture(
        parent, parent_meta['mixture'], parent_meta['doe'],
        candidates, candidate_meta['mixture'], candidate_meta['doe'], 1,
        degree=1, terms=('A', 'B', 'C'), allow_repeats=True,
        batch_id='P4BC-AUG')

    assert report['added_n'] == 1
    assert result_mixture['schema_version'] == 1
    assert result_mixture['spec']['schema_version'] == 1
    assert restore_mixture(result, result_mixture, result_doe)[0].construction_version == 'v2'
    with pytest.raises(ValueError, match='运行数|交叉'):
        restore_mixture(result, result_mixture)
