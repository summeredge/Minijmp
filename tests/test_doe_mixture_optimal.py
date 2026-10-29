from fractions import Fraction
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from doe_core import restore_design_result, worksheet_metadata
from doe_augment import augment, augment_mixture
from doe_mixture import MixtureSpec, mixture_metadata, restore_mixture
from doe_mixture_constraints import ComponentSpec, LinearConstraint, VariableSpec
from doe_optimal_design import evaluate_mixture_design, select_mixture_optimal


REFERENCE = json.loads((Path(__file__).parent / "fixtures"
                        / "doe_phase2_optimal_reference" / "reference.json")
                       .read_text(encoding="utf-8"))


def mixture_source(points, *, process_values=None, components=None,
                   process_variables=(), linear_constraints=(),
                   design_id="mixture-candidates"):
    points = [tuple(float(Fraction(value)) for value in point) for point in points]
    components = components or tuple(
        ComponentSpec(name, name) for name in ("A", "B", "C"))
    spec = MixtureSpec(
        design_id, tuple(components), ("Y",), "simplex_centroid", None,
        process_variables=tuple(process_variables),
        linear_constraints=tuple(linear_constraints))
    process_values = process_values or [None] * len(points)
    rows = []
    for index, (point, process) in enumerate(zip(points, process_values), start=1):
        nonzero = sum(value > 1e-12 for value in point)
        point_type = ("factorial" if nonzero == 1 else
                      "center" if all(abs(value - 1 / len(point)) < 1e-12
                                      for value in point) else "edge")
        row = {"运行ID": f"C{index:05d}", "标准序": index,
               "运行序": index, "点类型": point_type, "重复": 1,
               "点来源": "候选"}
        row.update({f"设定_{component.component_id}": value
                    for component, value in zip(spec.components, point)})
        for variable, value in zip(spec.process_variables, process or ()):
            row[f"设定_{variable.variable_id}"] = value
        row["响应_Y"] = float(index)
        rows.append(row)
    columns = ["运行ID", "标准序", "运行序", "点类型", "重复", "点来源"]
    columns.extend(f"设定_{name}" for name in (*spec.component_ids, *spec.variable_ids))
    columns.append("响应_Y")
    frame = pd.DataFrame(rows, columns=columns)
    frame["响应_Y"] = pd.array(frame["响应_Y"], dtype="Float64")
    doe_metadata = worksheet_metadata(
        frame, spec.doe_design_spec(), spec.column_map())
    mixture_meta = mixture_metadata(frame, spec)
    return frame, mixture_meta, doe_metadata


def test_mixture_d_optimal_matches_scheffe_oracle_and_persists_v5_lineage():
    case = REFERENCE["quadratic_scheffe"]
    frame, mixture_meta, doe_meta = mixture_source(case["points"])
    original = frame.copy(deep=True)
    selected, selected_doe, selected_mixture, model, summary = select_mixture_optimal(
        frame, mixture_meta, doe_meta, case["requested"], degree=2,
        terms=case["terms"], criterion="d_optimal", design_id="selected-mixture")

    expected_indices = case["optimal_subsets"][0]
    assert list(summary["selection_order"]) == expected_indices
    assert np.isclose(np.exp(summary["logdet"]),
                      float(Fraction(case["det_xtx"])), rtol=1e-12)
    assert summary["selected_rank"] == summary["selected_p"] == 6
    assert summary["global_optimum_proven"] is True
    assert frame.equals(original)
    assert selected["运行ID"].is_unique
    assert selected["重复"].tolist() == [1] * case["requested"]
    assert selected["响应_Y"].isna().all()
    source_column = selected_doe["column_map"]["source_run_id"]
    assert selected[source_column].tolist() == [f"C{i + 1:05d}" for i in expected_indices]
    design = restore_design_result(selected, selected_doe)
    restored_spec, _ = restore_mixture(selected, selected_mixture)
    assert design.spec.schema_version == 5
    assert design.spec.optimal_lineage["criterion"] == "d_optimal"
    assert design.spec.optimal_lineage["selection_order"] == tuple(selected["运行ID"])
    assert restored_spec.schema_version == 1
    assert model["terms"] == case["terms"]


def test_mixture_d_optimal_repeats_are_new_runs_and_candidate_duplicates_do_not_weight_search():
    case = REFERENCE["repetition"]
    points = list(case["candidate_points"]) + [case["candidate_points"][0]]
    frame, mixture_meta, doe_meta = mixture_source(points)
    selected, selected_doe, selected_mixture, model, summary = select_mixture_optimal(
        frame, mixture_meta, doe_meta, 4, degree=1, terms=case["terms"],
        criterion="d_optimal", allow_repeats=True, design_id="mixture-repeats")

    assert summary["collapsed_duplicate_candidates"] == 1
    assert summary["multiplicities"] == (("C00001", 2), ("C00002", 1),
                                          ("C00003", 1))
    assert len(set(selected["运行ID"])) == 4
    assert selected["重复"].tolist() == [1, 2, 1, 1]
    source_column = selected_doe["column_map"]["source_run_id"]
    assert selected[source_column].tolist() == ["C00001", "C00001", "C00002", "C00003"]
    assert selected["响应_Y"].isna().all()
    assert summary["global_optimum_proven"] is True
    assert restore_design_result(selected, selected_doe).spec.optimal_lineage is not None
    assert restore_mixture(selected, selected_mixture)[0].design_id == "mixture-repeats"

    with pytest.raises(ValueError, match="候选点不足|不能超过候选行数"):
        select_mixture_optimal(frame, mixture_meta, doe_meta, 4, degree=1,
                               terms=case["terms"], criterion="d_optimal",
                               allow_repeats=False)


def test_mixture_d_optimal_process_interactions_match_independent_matrix():
    case = REFERENCE["process_scheffe"]
    process_values = [(float(Fraction(item["process"])),)
                      for item in case["settings"]]
    points = [tuple(float(Fraction(value)) for value in item["components"])
              for item in case["settings"]]
    frame, mixture_meta, doe_meta = mixture_source(
        points, process_values=process_values,
        process_variables=(VariableSpec("P", "过程", 0, 10),))
    selected, _, _, _, summary = select_mixture_optimal(
        frame, mixture_meta, doe_meta, 6, criterion="d_optimal", degree=1,
        terms=case["terms"], design_id="mixture-process")

    assert summary["selected_rank"] == case["rank"] == 6
    assert np.isclose(np.exp(summary["logdet"]), float(case["det_xtx"]), rtol=1e-12)
    assert selected["DOE 源运行ID"].tolist() == [f"C{i:05d}" for i in range(1, 7)]


def test_mixture_d_optimal_selects_only_constraint_feasible_points():
    case = REFERENCE["constrained_selection"]
    points = [case["points"][index] for index in case["feasible_indices"]]
    components = tuple(ComponentSpec(
        name, name, float(Fraction(low)), float(Fraction(high)))
        for name, (low, high) in zip(("A", "B", "C"), case["bounds"]))
    constraint = LinearConstraint(
        {name: float(Fraction(value))
         for name, value in zip(("A", "B", "C"),
                                case["linear_constraints"][0][0])
         if Fraction(value)},
        float(Fraction(case["linear_constraints"][0][1])))
    frame, mixture_meta, doe_meta = mixture_source(
        points, components=components, linear_constraints=(constraint,))
    selected, _, _, _, summary = select_mixture_optimal(
        frame, mixture_meta, doe_meta, 3, degree=1, terms=["A", "B", "C"],
        criterion="d_optimal", design_id="mixture-constrained")

    assert summary["selection_order"] == (0, 2, 3)
    assert summary["selected_rank"] == 3
    assert np.isclose(np.exp(summary["logdet"]),
                      float(Fraction(case["det_xtx"])), rtol=1e-12)


def test_mixture_distance_matches_simplex_order_from_independent_oracle():
    case = REFERENCE["distance_simplex"]
    frame, mixture_meta, doe_meta = mixture_source(case["points"])
    selected, selected_doe, _, _, summary = select_mixture_optimal(
        frame, mixture_meta, doe_meta, 7, criterion="distance", degree=2,
        design_id="mixture-distance-simplex")

    assert list(summary["selection_order"][:case["requested"]]) == case["selected_order"]
    assert summary["criterion"] == "distance"
    assert summary["global_optimum_proven"] is False
    assert summary["selected_rank"] == summary["selected_p"] == 6
    assert restore_design_result(selected, selected_doe).spec.optimal_lineage[
        "criterion"] == "distance"


def test_mixture_distance_normalizes_selected_process_variables_and_matches_oracle():
    points = [(1, 0, 0), (0, 1, 0), (0, 0, 1)]
    variable = VariableSpec("P", "过程", 0, 8)
    process_values = [(0,), (8,), (0,)]
    frame, mixture_meta, doe_meta = mixture_source(
        points, process_values=process_values, process_variables=(variable,))
    selected, _, _, _, summary = select_mixture_optimal(
        frame, mixture_meta, doe_meta, 3, degree=1,
        terms=["A", "B", "C"], criterion="distance",
        distance_variables=("P",), design_id="mixture-distance")

    assert summary["selection_order"] == (0, 1, 2)
    assert summary["distance_variables"] == ("P",)
    assert summary["kind"] == "mixture"
    assert summary["global_optimum_proven"] is False
    assert summary["evaluations"] > 0
    assert summary["selected_source_run_ids"] == ("C00001", "C00002", "C00003")


def test_mixture_evaluation_reports_model_information_and_distance_spacing():
    points = [(1, 0, 0), (0, 1, 0), (0, 0, 1)]
    variable = VariableSpec("P", "过程", 0, 8)
    frame, mixture_meta, doe_meta = mixture_source(
        points, process_values=[(0,), (8,), (0,)], process_variables=(variable,))
    info = evaluate_mixture_design(
        frame, mixture_meta, doe_meta, criterion="d_optimal", degree=1,
        terms=["A", "B", "C"])
    spacing = evaluate_mixture_design(
        frame, mixture_meta, doe_meta, criterion="distance", degree=1,
        terms=["A", "B", "C"], distance_variables=("P",))
    assert info["rank"] == info["p"] == 3
    assert spacing["unique_distance_points"] == 3
    assert spacing["min_squared_distance"] == 2.0


@pytest.mark.parametrize(("points", "unique", "duplicates"), [
    ([(1, 0, 0), (1, 0, 0), (0, 1, 0)], 2, 1),
    ([(1, 0, 0)] * 3, 1, 2),
])
def test_mixture_distance_evaluation_counts_repeated_runs_as_zero_spacing(
        points, unique, duplicates):
    frame, mixture_meta, doe_meta = mixture_source(points)
    summary = evaluate_mixture_design(
        frame, mixture_meta, doe_meta, criterion="distance", degree=1,
        terms=["A", "B", "C"])

    assert summary["unique_distance_points"] == unique
    assert summary["collapsed_duplicate_points"] == duplicates
    assert summary["min_squared_distance"] == 0.0


def test_mixture_optimal_rejects_stale_candidate_snapshot_without_mutation():
    case = REFERENCE["distance_simplex"]
    frame, mixture_meta, doe_meta = mixture_source(case["points"])
    stale = frame.copy(deep=True)
    stale.loc[0, "设定_A"] = 0.9
    original = stale.copy(deep=True)
    with pytest.raises(ValueError):
        select_mixture_optimal(stale, mixture_meta, doe_meta, 5,
                               criterion="distance")
    assert stale.equals(original)


def test_mixture_d_optimal_augmentation_preserves_parent_and_records_lineage():
    parent, parent_mixture, parent_doe = mixture_source(
        [(1, 0, 0)], design_id="mixture-parent")
    candidates, candidate_mixture, candidate_doe = mixture_source(
        [(0, 1, 0), (0, 0, 1)], design_id="mixture-candidates")
    original_parent = parent.copy(deep=True)
    original_responses = parent["响应_Y"].tolist()
    result, result_doe, result_mixture, model, summary = augment_mixture(
        parent, parent_mixture, parent_doe,
        candidates, candidate_mixture, candidate_doe, 2,
        criterion="d_optimal", degree=1, terms=["A", "B", "C"],
        batch_id="AUG1", design_id="mixture-augmented")

    assert parent.equals(original_parent)
    assert result["运行ID"].is_unique
    assert result.iloc[0]["响应_Y"] == original_responses[0]
    assert result.iloc[1:]["响应_Y"].isna().all()
    assert result["DOE 批次"].tolist() == ["BASE", "AUG1", "AUG1"]
    assert result["DOE 源运行ID"].tolist() == [None, "C00001", "C00002"]
    assert summary["initial_n"] == 1 and summary["added_n"] == 2
    assert summary["initial_rank"] == 1 and summary["augmented_rank"] == 3
    assert np.isclose(np.exp(summary["logdet"]), 1.0, rtol=1e-12)
    restored = restore_design_result(result, result_doe)
    assert restored.spec.augmentation_lineage["criterion"] == "d_optimal"
    assert restored.spec.augmentation_lineage["run_map"] == (
        ("C00001", "MA00001"), ("C00002", "MA00002"))
    assert restore_mixture(result, result_mixture)[0].schema_version == 1
    assert model["terms"] == ["A", "B", "C"]


def test_mixture_d_optimal_augmentation_with_replacement_adds_independent_runs():
    parent, parent_mixture, parent_doe = mixture_source(
        [(1, 0, 0)], design_id="mixture-repeat-parent")
    candidates, candidate_mixture, candidate_doe = mixture_source(
        [(0, 1, 0), (0, 0, 1)], design_id="mixture-repeat-candidates")
    result, result_doe, _, _, summary = augment_mixture(
        parent, parent_mixture, parent_doe,
        candidates, candidate_mixture, candidate_doe, 3,
        criterion="d_optimal", degree=1, terms=["A", "B", "C"],
        allow_repeats=True, batch_id="AUGR", design_id="mixture-repeat-aug")

    assert summary["selected_source_run_ids"] == ("C00001", "C00001", "C00002")
    assert summary["multiplicities"] == (("C00001", 2), ("C00002", 1))
    assert result["运行ID"].is_unique
    assert result["重复"].tolist() == [1, 1, 2, 1]
    assert result["DOE 批次"].tolist() == ["BASE", "AUGR", "AUGR", "AUGR"]
    assert result["响应_Y"].iloc[0] == 1.0
    assert result["响应_Y"].iloc[1:].isna().all()
    assert summary["initial_rank"] == 1 and summary["augmented_rank"] == 3
    assert np.isclose(np.exp(summary["logdet"]), 2.0, rtol=1e-12)
    assert restore_design_result(result, result_doe).spec.augmentation_lineage is not None


def test_mixture_augmentation_preserves_large_integer_response_and_empty_batch():
    parent, parent_mixture, parent_doe = mixture_source(
        [(1, 0, 0)], design_id="mixture-exact-parent")
    candidate, candidate_mixture, candidate_doe = mixture_source(
        [(0, 1, 0), (0, 0, 1)], design_id="mixture-exact-candidates")
    parent_spec = restore_mixture(parent, parent_mixture)[0]
    design_spec = restore_design_result(parent, parent_doe).spec
    parent["响应_Y"] = pd.Series([9007199254740993], dtype=object)
    parent["DOE 批次"] = pd.Series([None], dtype=object)
    column_map = dict(parent_doe["column_map"])
    column_map["batch_id"] = "DOE 批次"
    parent_doe = worksheet_metadata(parent, design_spec, column_map)
    parent_mixture = mixture_metadata(parent, parent_spec)

    result, _, _, _, _ = augment_mixture(
        parent, parent_mixture, parent_doe,
        candidate, candidate_mixture, candidate_doe, 2,
        criterion="d_optimal", degree=1, terms=["A", "B", "C"],
        batch_id="EXACT")

    assert result.loc[0, "响应_Y"] == 9007199254740993
    assert result.loc[0, "DOE 批次"] is None
    assert result.loc[1:, "响应_Y"].isna().all()
    assert result.loc[1:, "DOE 批次"].tolist() == ["EXACT", "EXACT"]


def test_mixture_distance_augmentation_uses_parent_as_anchor_and_no_repeats():
    parent, parent_mixture, parent_doe = mixture_source(
        [(1, 0, 0)], design_id="distance-mixture-parent")
    candidates, candidate_mixture, candidate_doe = mixture_source(
        [(1, 0, 0), (0, 1, 0), (0, 0, 1)],
        design_id="distance-mixture-candidates")
    result, result_doe, _, _, summary = augment_mixture(
        parent, parent_mixture, parent_doe,
        candidates, candidate_mixture, candidate_doe, 2,
        criterion="distance", degree=1, terms=["A", "B", "C"],
        batch_id="AUGD", design_id="mixture-distance-aug")

    assert summary["selection_order"] == (0, 1)
    assert summary["selected_source_run_ids"] == ("C00002", "C00003")
    assert summary["method"] == "distance_farthest_point"
    assert summary["global_optimum_proven"] is False
    assert summary["min_squared_distance"] == 2.0
    assert result["响应_Y"].iloc[0] == 1.0
    assert result["响应_Y"].iloc[1:].isna().all()
    assert restore_design_result(result, result_doe).spec.augmentation_lineage[
        "criterion"] == "distance"


def test_generic_augmentation_rejects_mixture_instead_of_using_ordinary_terms():
    parent, parent_mixture, parent_doe = mixture_source(
        [(1, 0, 0)], design_id="generic-guard-parent")
    before = parent.copy(deep=True)
    with pytest.raises(ValueError, match="混料设计必须使用混料最优设计增补"):
        augment(parent, parent_doe,
                [{"A": 0.5, "B": 0.5, "C": 0.0}], 1,
                point_types=["edge"])
    assert parent.equals(before)
