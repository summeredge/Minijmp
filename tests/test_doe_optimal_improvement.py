import math

import numpy as np
import pandas as pd
import pytest

from doe_augment import improve_fixed_size
from doe_core import FactorSpec, restore_design_result, worksheet_metadata
from doe_custom import define_custom


_FACTORIAL_POINTS = ((-1, -1), (-1, 1), (1, -1), (0, 0))
_FACTORIAL_CANDIDATES = ((-1, -1), (-1, 1), (1, -1), (1, 1))


def make_design(design_id, design_type, points, *, point_types=None, responses=None,
                measured=None, model_terms=(), replicates=None):
    point_types = point_types or tuple(
        "center" if point == (0, 0) else "factorial" for point in points)
    responses = [None] * len(points) if responses is None else responses
    frame = pd.DataFrame({
        "运行ID": [f"{design_id}-{index + 1}" for index in range(len(points))],
        "标准序": list(range(1, len(points) + 1)),
        "运行序": list(range(1, len(points) + 1)),
        "点类型": point_types,
        "重复": [1] * len(points) if replicates is None else replicates,
        "批次": ["BASE"] * len(points),
        "来源": [None] * len(points),
        "A": [point[0] for point in points],
        "B": [point[1] for point in points],
        "Y": responses,
    })
    measured_map = {}
    if measured is not None:
        frame["A实测"] = measured
        measured_map = {"A": "A实测"}
    column_map = {
        "run_id": "运行ID", "standard_order": "标准序", "run_order": "运行序",
        "point_type": "点类型", "replicate": "重复", "block": None,
        "batch_id": "批次", "source_run_id": "来源",
        "factors": {"A": "A", "B": "B"},
        "measured_levels": measured_map, "responses": {"Y": "Y"},
    }
    factors = (FactorSpec("A", "A", -1, 1), FactorSpec("B", "B", -1, 1))
    return define_custom(
        frame, design_type=design_type, factors=factors, responses=("Y",),
        column_map=column_map, design_id=design_id, model_terms=model_terms,
        require_estimable=False)[:2]


def _integer_det(matrix):
    gram = np.asarray(matrix, dtype=np.int64).T @ np.asarray(matrix, dtype=np.int64)
    a, b, c = gram[0]
    d, e, f = gram[1]
    g, h, i = gram[2]
    return int(a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g))


def _main_effect_matrix(points):
    return [[1, a, b] for a, b in points]


def test_factorial_improvement_matches_independent_exact_candidate_enumeration():
    parent, parent_meta = make_design(
        "factorial-parent", "custom_factorial", _FACTORIAL_POINTS)
    candidate_points = _FACTORIAL_CANDIDATES
    candidates, candidate_meta = make_design(
        "factorial-candidates", "custom_factorial", candidate_points)
    expected = []
    for index, point in enumerate(candidate_points):
        trial = list(_FACTORIAL_POINTS)
        trial[-1] = point
        determinant = _integer_det(_main_effect_matrix(trial))
        if determinant > 0:
            expected.append((determinant, index))
    best_determinant, best_index = max(expected)

    improved, metadata, summary = improve_fixed_size(
        parent, parent_meta, candidates, candidate_meta,
        locked_run_ids=tuple(parent["运行ID"][:3]),
        replaceable_run_ids=(parent.loc[3, "运行ID"],),
        candidate_run_ids=tuple(candidates["运行ID"]), seed=12)

    assert summary["candidate_to_replaced_parent"][0][0] == candidates.loc[
        best_index, "运行ID"]
    assert summary["parent_logdet"] == pytest.approx(
        math.log(_integer_det(_main_effect_matrix(_FACTORIAL_POINTS))))
    assert summary["current_logdet"] == pytest.approx(math.log(best_determinant))
    assert summary["current_n"] == summary["parent_n"] == len(parent)
    assert summary["rank"] == 3
    assert summary["global_optimum_proven"] is False
    assert parent["运行ID"].tolist() == [f"factorial-parent-{i}" for i in range(1, 5)]
    assert improved.loc[:2, "运行ID"].tolist() == parent.loc[:2, "运行ID"].tolist()
    assert improved.loc[3, "运行ID"] != parent.loc[3, "运行ID"]
    assert pd.isna(improved.loc[3, "Y"])

    restored = restore_design_result(improved, metadata)
    lineage = restored.spec.improvement_lineage
    assert lineage["criterion"] == "d_optimal"
    assert lineage["candidate_design_id"] == "factorial-candidates"
    assert lineage["run_map"][0][2] == parent.loc[3, "运行ID"]


def test_seeded_tie_order_is_repeatable():
    parent, parent_meta = make_design(
        "tie-parent", "custom_factorial", _FACTORIAL_POINTS)
    candidates, candidate_meta = make_design(
        "tie-candidates", "custom_factorial", ((1, 1), (1, 1)),
        point_types=("factorial", "factorial"), replicates=(1, 2))
    args = (parent, parent_meta, candidates, candidate_meta,
            tuple(parent["运行ID"][:3]), (parent.loc[3, "运行ID"],),
            tuple(candidates["运行ID"]))

    first = improve_fixed_size(*args, seed=31)
    second = improve_fixed_size(*args, seed=31)

    assert first[2]["candidate_to_replaced_parent"] == \
        second[2]["candidate_to_replaced_parent"]
    assert first[2]["current_logdet"] == second[2]["current_logdet"]


def test_rsm_improvement_keeps_run_count_and_model_rank():
    points = ((-1, -1), (-1, 0), (-1, 1), (0, -1),
              (0, 0), (0, 1), (1, -1))
    terms = ("A", "B", "A²", "B²", "A*B")
    parent, parent_meta = make_design(
        "rsm-parent", "custom_rsm", points, model_terms=terms)
    candidates, candidate_meta = make_design(
        "rsm-candidates", "custom_rsm", ((1, 1),),
        point_types=("factorial",), model_terms=terms)
    matrix = lambda rows: np.asarray(
        [[1, a, b, a * a, b * b, a * b] for a, b in rows], dtype=float)
    before = matrix(points)
    trial_points = ((1, 1),) + points[1:]
    _, expected_logdet = np.linalg.slogdet(matrix(trial_points).T @ matrix(trial_points))

    improved, metadata, summary = improve_fixed_size(
        parent, parent_meta, candidates, candidate_meta,
        locked_run_ids=tuple(parent["运行ID"][1:]),
        replaceable_run_ids=(parent.loc[0, "运行ID"],),
        candidate_run_ids=(candidates.loc[0, "运行ID"],), seed=4)

    actual_points = tuple(zip(improved["A"], improved["B"]))
    _, actual_logdet = np.linalg.slogdet(matrix(actual_points).T @ matrix(actual_points))
    assert len(improved) == len(parent) == 7
    assert summary["rank"] == np.linalg.matrix_rank(matrix(actual_points)) == 6
    assert summary["current_logdet"] == pytest.approx(expected_logdet)
    assert summary["current_logdet"] == pytest.approx(actual_logdet)
    assert summary["current_logdet"] > summary["parent_logdet"]
    assert summary["current_matrix_sha256"] != summary["parent_matrix_sha256"]
    assert restore_design_result(improved, metadata).spec.design_type == "custom_rsm"
    assert np.linalg.matrix_rank(before) == 6


def test_executed_or_measured_runs_are_protected_and_locked_data_survives():
    parent, parent_meta = make_design(
        "protected-parent", "custom_factorial", _FACTORIAL_POINTS,
        responses=[72, None, None, None], measured=[None, -1, None, None])
    candidates, candidate_meta = make_design(
        "protected-candidates", "custom_factorial", _FACTORIAL_CANDIDATES)
    original = parent.copy(deep=True)
    locked = tuple(parent["运行ID"][:3])
    result, _, _ = improve_fixed_size(
        parent, parent_meta, candidates, candidate_meta, locked,
        (parent.loc[3, "运行ID"],), tuple(candidates["运行ID"]))
    pd.testing.assert_frame_equal(parent, original)
    for row in range(3):
        for column in ("运行ID", "A", "B", "Y", "A实测"):
            left, right = result.loc[row, column], original.loc[row, column]
            assert (pd.isna(left) and pd.isna(right)) or left == right
    assert pd.isna(result.loc[3, "A实测"])
    assert pd.isna(result.loc[3, "Y"])

    for executed_id in parent.loc[:1, "运行ID"]:
        with pytest.raises(ValueError, match="已执行运行不可替换"):
            improve_fixed_size(
                parent, parent_meta, candidates, candidate_meta,
                tuple(run_id for run_id in locked if run_id != executed_id),
                (executed_id, parent.loc[3, "运行ID"]),
                tuple(candidates["运行ID"]))


def test_no_improving_exchange_keeps_all_runs_and_records_reason():
    parent, parent_meta = make_design(
        "unchanged-parent", "custom_factorial", _FACTORIAL_POINTS)
    candidates, candidate_meta = make_design(
        "same-point-candidate", "custom_factorial", ((0, 0), (-1, -1)),
        point_types=("center", "factorial"))
    before = parent.copy(deep=True)
    result, metadata, summary = improve_fixed_size(
        parent, parent_meta, candidates, candidate_meta,
        tuple(parent["运行ID"][:3]), (parent.loc[3, "运行ID"],),
        (candidates.loc[0, "运行ID"],))

    pd.testing.assert_frame_equal(result, before)
    assert summary["replaced_count"] == 0
    assert summary["stop_reason"] == "no_improving_exchange"
    assert summary["current_logdet"] == summary["parent_logdet"]
    assert restore_design_result(result, metadata).spec.improvement_lineage["run_map"] == ()


def test_completed_candidate_cannot_be_used_for_replacement():
    parent, parent_meta = make_design(
        "candidate-protect-parent", "custom_factorial", _FACTORIAL_POINTS)
    candidates, candidate_meta = make_design(
        "candidate-protect-source", "custom_factorial", ((1, 1),),
        responses=[99])
    with pytest.raises(ValueError, match="已执行的候选运行不可选择"):
        improve_fixed_size(
            parent, parent_meta, candidates, candidate_meta,
            tuple(parent["运行ID"][:3]), (parent.loc[3, "运行ID"],),
            (candidates.loc[0, "运行ID"],))


def test_saved_improvement_lineage_detects_matrix_changes():
    parent, parent_meta = make_design(
        "tamper-parent", "custom_factorial", _FACTORIAL_POINTS)
    candidates, candidate_meta = make_design(
        "tamper-candidates", "custom_factorial", ((1, 1),))
    result, metadata, _ = improve_fixed_size(
        parent, parent_meta, candidates, candidate_meta,
        tuple(parent["运行ID"][:3]), (parent.loc[3, "运行ID"],),
        (candidates.loc[0, "运行ID"],))
    spec = restore_design_result(result, metadata).spec
    changed = result.copy(deep=True)
    changed.loc[0, "标准序"], changed.loc[1, "标准序"] = 2, 1

    with pytest.raises(ValueError, match="改善后模型矩阵摘要"):
        worksheet_metadata(changed, spec, metadata["column_map"])
