import json
from itertools import combinations
from math import comb
from pathlib import Path

import numpy as np
import pytest

from doe_optimal import (candidate_digest, evaluate, exact_select, select,
                         select_distance)


def _linear_rows(count, columns=5, seed=11):
    """截距 + (columns-1) 列均匀候选，用于预算边界测试。"""
    rng = np.random.default_rng(seed)
    return np.column_stack((np.ones(count),
                            rng.uniform(-1, 1, (count, columns - 1)))).tolist()


def test_exact_budget_allows_20_choose_10_when_subsets_fit():
    rows = _linear_rows(20)
    result = select(rows, 10)
    assert result["subsets"] == comb(20, 10) == 184756
    assert result["method"] == "exact_enumeration"
    assert result["global_optimum_proven"] is True
    assert result["evaluations"] == result["subsets"]
    assert result["rank"] == result["p"] == 5


def test_select_auto_degrades_past_subset_budget_instead_of_failing():
    rows = _linear_rows(21)
    result = select(rows, 10)
    assert result["subsets"] == comb(21, 10) == 352716
    assert result["method"] == "greedy_exchange"
    assert result["global_optimum_proven"] is False
    assert result["exact_budget"] == 200_000
    assert result["evaluations"] < result["subsets"]
    assert "超过预算" in result["stop_reason"]
    assert result["rank"] == result["p"]
    # 显式穷举仍按超预算报错，公共 select() 不应抛该错误。
    with pytest.raises(ValueError, match="不能精确穷举"):
        exact_select(rows, 10)


def test_200_candidate_search_records_budget_and_reproducible_seed():
    rows = _linear_rows(200, columns=5, seed=17)
    first = select(rows, 12, seed=9)
    second = select(rows, 12, seed=9)
    other = select(rows, 12, seed=1)
    assert first["method"] == "greedy_exchange"
    assert first["global_optimum_proven"] is False
    assert first["seed"] == 9 and first["candidates"] == 200
    assert first["indices"] == second["indices"]
    assert first["logdet"] == second["logdet"]
    # seed 只决定多起点的探索顺序；不同 seed 收敛到同一设计是合法结果，
    # 因此只要求如实记录 seed 并可复现，不强行要求选出不同子集。
    assert other["seed"] == 1
    assert other["indices"] == select(rows, 12, seed=1)["indices"]
    assert other["logdet"] <= first["logdet"] + 1e-9
    assert "候选行数超过精确搜索上限" in first["stop_reason"]


def test_select_rejects_candidate_set_without_full_rank_subset():
    # 所有候选的第 2、3 列成比例：任何子集都不满秩。
    rows = [[1, value, 2 * value] for value in range(-2, 3)]
    with pytest.raises(ValueError, match="满列秩|满秩"):
        select(rows, 2)


REFERENCE = json.loads((Path(__file__).parent / "fixtures" / "doe_optimal_reference"
                        / "reference.json").read_text(encoding="utf-8"))


def test_d_optimal_minimum_oracle_endpoints_have_det_four():
    case = REFERENCE["d_optimal_simple"]
    result = select(case["candidates"], case["select"])
    assert result["method"] == "exact_enumeration"
    assert result["global_optimum_proven"] is True
    assert list(result["indices"]) == case["expected"]["selected"]
    assert np.isclose(np.exp(result["logdet"]), 4, rtol=1e-12)
    assert result["rank"] == 2 == result["p"]
    # 中间点参与的任何两点子集行列式都更小。
    for indices in combinations(range(3), 2):
        value = evaluate([case["candidates"][index] for index in indices])["det_xtx"]
        assert value <= 4


def test_d_optimal_ties_are_reported_stably():
    case = REFERENCE["d_optimal_tie"]
    result = select(case["candidates"], case["select"])
    assert list(result["indices"]) == case["expected"]["selected"]
    assert np.isclose(np.exp(result["logdet"]),
                      float(case["expected"]["det_xtx"]), rtol=1e-12)
    assert select(case["candidates"], case["select"])["indices"] == result["indices"]


def test_categorical_candidate_selection_matches_exhaustive_reference():
    case = REFERENCE["categorical_candidates"]
    result = select(case["candidates"], case["select"])
    assert list(result["indices"]) == case["expected"]["selected"]
    assert result["rank"] == case["expected"]["rank"] == 4
    assert np.isclose(np.exp(result["logdet"]),
                      float(case["expected"]["det_xtx"]), rtol=1e-9)


def test_rsm_candidate_selection_matches_exhaustive_reference():
    case = REFERENCE["rsm_candidates"]
    result = select(case["candidates"], case["select"])
    assert list(result["indices"]) == case["expected"]["selected"]
    assert result["rank"] == case["expected"]["rank"] == 6
    assert np.isclose(np.exp(result["logdet"]),
                      float(case["expected"]["det_xtx"]), rtol=1e-9)


def test_singular_candidate_set_is_rejected():
    with pytest.raises(ValueError, match="候选点不足"):
        select([[1, 1], [1, 1], [1, 1]], 2)
    with pytest.raises(ValueError, match="满列秩"):
        select([[1, 1, 2], [1, 2, 3], [1, 3, 4]], 2)


def test_requested_count_above_distinct_candidates_is_rejected():
    with pytest.raises(ValueError, match="候选点不足"):
        select([[1, -1], [1, 0], [1, 0]], 3)
    with pytest.raises(ValueError, match="不能超过候选行数"):
        select([[1, -1], [1, 1]], 3)
    with pytest.raises(ValueError, match="正整数"):
        select([[1, -1], [1, 1]], 0)


def test_all_candidates_selected_returns_same_information():
    rows = REFERENCE["rsm_candidates"]["candidates"]
    result = select(rows, len(rows))
    assert len(result["indices"]) == len(rows)
    assert np.isclose(result["logdet"], evaluate(rows)["logdet"])


def test_large_candidate_search_is_reproducible_and_not_claimed_global():
    rng = np.random.default_rng(7)
    rows = np.column_stack((np.ones(200), rng.uniform(-1, 1, (200, 3)),
                            rng.uniform(-1, 1, (200, 3)) ** 2))
    first = select(rows.tolist(), 12, seed=5)
    second = select(rows.tolist(), 12, seed=5)
    assert first["method"] == "greedy_exchange"
    assert first["global_optimum_proven"] is False
    assert first["indices"] == second["indices"]
    assert first["rank"] == first["p"]
    assert first["logdet"] > 0


def test_candidate_digest_is_order_independent():
    rows = REFERENCE["rsm_candidates"]["candidates"]
    assert candidate_digest(rows) == candidate_digest(list(reversed(rows)))
    assert candidate_digest(rows) != candidate_digest(rows[:-1])


def test_distance_based_matches_hand_computed_order_and_never_repeats():
    case = REFERENCE["distance_rsm"]
    result = select_distance(case["points"], case["select"])
    assert list(result["selection_order"]) == case["expected"]["order"]
    assert list(result["indices"]) == sorted(case["expected"]["order"])
    assert len(set(result["selection_order"])) == len(result["selection_order"])
    assert result["min_squared_distance"] == 4


def test_distance_based_rejects_factorial_and_mixture_families():
    with pytest.raises(ValueError, match="只支持响应面"):
        select_distance([[1, 1], [-1, 1]], 2, kind="factorial")
    with pytest.raises(ValueError, match="只支持响应面"):
        select_distance([[1, 1], [-1, 1]], 2, kind="mixture")


def test_evaluate_reports_condition_rank_and_guards_det_overflow():
    case = REFERENCE["rank_deficient"]
    summary = evaluate(case["matrix"])
    assert summary["rank"] == case["expected"]["rank"] == 2
    assert summary["singular"] is True
    assert summary["det_xtx"] is None
    full = evaluate([[1, 1], [-1, 1]])
    assert full["det_xtx"] == 4
    guarded = evaluate([[1, 1], [-1, 1]], det_limit=1)
    assert guarded["det_xtx"] is None and guarded["logdet"] is not None
    near_singular = evaluate([[1, 1e60], [1, -1e60]])
    assert near_singular["logdet"] is None and near_singular["condition"] is not None
