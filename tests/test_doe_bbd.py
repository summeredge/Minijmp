"""Box-Behnken 设计与分析；矩阵由独立构造生成，不调用生产生成器。"""
from collections import Counter
from dataclasses import replace
from itertools import product

import numpy as np
import pytest

from doe_bbd import create_bbd, validate_bbd
from doe_core import DesignSpec, FactorSpec, restore_design_result
from doe_rsm import analyze_rsm
from doe_rsm_model import TermModel


def spec(k=3, seed=11, blocks=None, centers=None):
    return DesignSpec('bbd', tuple(FactorSpec(chr(65+i), chr(65+i), -1, 1)
                                   for i in range(k)), ('Y',), seed=seed,
                      design_type='box_behnken', block_count=blocks,
                      ccd_center_points=centers)


def reference_matrix(pairs, k, centers=0):
    """独立构造：每对因子取 ±1，其余为 0；中心点随后。"""
    rows = []
    for pair in pairs:
        for signs in product((-1, 1), repeat=len(pair)):
            row = [0] * k
            for index, sign in zip(pair, signs):
                row[index] = sign
            rows.append(row)
    rows.extend([0] * k for _ in range(centers))
    return np.asarray(rows, float)


def quadratic(coded):
    coded = np.asarray(coded, float)
    k = coded.shape[1]
    return np.column_stack([np.ones(len(coded)), coded, coded**2] +
                           [coded[:, i]*coded[:, j]
                            for i in range(k) for j in range(i+1, k)])


def test_three_factor_points_match_independent_construction():
    frame, metadata = create_bbd(spec(3))
    result = restore_design_result(frame, metadata)
    coded = np.asarray(validate_bbd(result, frame), float)
    expected = reference_matrix([(0, 1), (0, 2), (1, 2)], 3, 3)
    assert Counter(frame['点类型']) == {'edge': 12, 'center': 3}
    assert len(frame) == 15
    np.testing.assert_array_equal(np.sort(coded, axis=0), np.sort(expected, axis=0))


def test_three_factor_quadratic_model_is_full_rank_with_ten_columns():
    frame, metadata = create_bbd(spec(3))
    result = restore_design_result(frame, metadata)
    coded = np.asarray(validate_bbd(result, frame), float)
    matrix = quadratic(coded)
    assert matrix.shape == (15, 10)
    assert np.linalg.matrix_rank(matrix) == 10
    assert np.linalg.cond(matrix) < 100


@pytest.mark.parametrize('k, runs, centers', [(3, 15, 3), (4, 27, 3), (5, 46, 6),
                                              (6, 54, 6), (7, 62, 6)])
def test_run_counts_and_default_centers_follow_official_summary(k, runs, centers):
    frame, metadata = create_bbd(spec(k))
    result = restore_design_result(frame, metadata)
    coded = np.asarray(validate_bbd(result, frame), float)
    assert len(frame) == runs
    assert sum(run.point_type == 'center' for run in result.runs) == centers
    assert sum(run.point_type == 'edge' for run in result.runs) == runs - centers
    assert np.linalg.matrix_rank(quadratic(coded)) == quadratic(coded).shape[1]


def test_each_factor_and_pair_has_balanced_edge_coverage():
    frame, metadata = create_bbd(spec(5))
    result = restore_design_result(frame, metadata)
    coded = np.asarray(validate_bbd(result, frame), float)
    edges = coded[[run.point_type == 'edge' for run in result.runs]]
    for index in range(5):
        assert Counter(edges[:, index]) == {1.0: 8, 0.0: 24, -1.0: 8}
    for i in range(5):
        for j in range(i+1, 5):
            assert np.sum((edges[:, i] != 0) & (edges[:, j] != 0)) == 4


def test_replicate_and_randomization_are_reproducible():
    first, _ = create_bbd(spec(4), replicates=2)
    second, _ = create_bbd(spec(4), replicates=2)
    assert first['运行ID'].tolist() == second['运行ID'].tolist()
    assert Counter(first['重复']) == {1: 27, 2: 27}
    assert sorted(first['运行序']) == list(range(1, 55))
    other, _ = create_bbd(spec(4, seed=12), replicates=2)
    assert first['标准序'].tolist() != other['标准序'].tolist()
    assert sorted(first['标准序']) == list(range(1, 55))


@pytest.mark.parametrize('k, blocks', [(4, 3), (5, 2), (6, 2), (7, 2)])
def test_blocked_bbd_has_orthogonal_block_columns(k, blocks):
    frame, metadata = create_bbd(spec(k, blocks=blocks))
    result = restore_design_result(frame, metadata)
    coded = np.asarray(validate_bbd(result, frame), float)
    block = np.asarray([run.block for run in result.runs], float).reshape(-1, 1)
    matrix = quadratic(coded)
    cross = (matrix - matrix.mean(0)).T @ (block - block.mean(0))
    assert np.max(np.abs(cross)) < 1e-9
    assert set(frame['区组']) == set(range(1, blocks + 1))


def test_invalid_block_counts_and_factor_counts_are_rejected():
    with pytest.raises(ValueError, match='区组数'):
        create_bbd(spec(3, blocks=2))
    with pytest.raises(ValueError, match='区组数'):
        create_bbd(spec(4, blocks=2))
    with pytest.raises(ValueError, match='3 至 7'):
        create_bbd(spec(2))
    with pytest.raises(ValueError, match='3 至 7'):
        create_bbd(spec(8))


def test_centers_must_split_evenly_across_blocks():
    with pytest.raises(ValueError, match='均分'):
        create_bbd(spec(5, blocks=2, centers=5))


def test_tampered_settings_and_coded_columns_are_rejected():
    frame, metadata = create_bbd(spec(3))
    frame['编码_A'] = frame['编码_A'].astype(float)
    frame.loc[0, '编码_A'] = 0.5
    with pytest.raises(ValueError):
        restore_design_result(frame, metadata)


def test_analytic_quadratic_coefficients_are_recovered():
    frame, metadata = create_bbd(spec(3))
    coded = frame[['编码_A', '编码_B', '编码_C']].to_numpy(float)
    a, b, c = coded.T
    frame['响应_Y'] = (40 + 3*a - 2*b + c + 4*a*b - 1.5*b*c +
                       5*a*a + 2*b*b - 3*c*c)
    result = analyze_rsm(frame, metadata, 'Y')
    model = TermModel(result['design'].spec.factors)
    expected = {}
    for name, value in zip(model.names, result['coefficients']):
        expected[name] = value
    assert expected['截距'] == pytest.approx(40, abs=1e-10)
    assert expected['A'] == pytest.approx(3)
    assert expected['A²'] == pytest.approx(5)
    assert expected['B*C'] == pytest.approx(-1.5)
    assert result['sse'] < 1e-22


def test_term_selection_changes_the_fitted_model_not_just_display():
    frame, metadata = create_bbd(spec(3))
    coded = frame[['编码_A', '编码_B', '编码_C']].to_numpy(float)
    a, b, c = coded.T
    frame['响应_Y'] = 10 + 2*a + 3*b + 4*a*b + a*a
    full = analyze_rsm(frame, metadata, 'Y')
    reduced = analyze_rsm(frame, metadata, 'Y',
                          terms=('A', 'B', 'A*B', 'A²'))
    assert reduced['p'] < full['p']
    assert reduced['sse'] == pytest.approx(full['sse'], abs=1e-18)
    assert reduced['coefficients'][1] == pytest.approx(2)
    assert reduced['terms'] == ('A', 'B', 'A*B', 'A²')


def test_missing_parent_term_is_rejected_by_hierarchy_rule():
    frame, metadata = create_bbd(spec(3))
    frame['响应_Y'] = np.arange(len(frame), dtype=float)
    with pytest.raises(ValueError, match='需要同时包含'):
        analyze_rsm(frame, metadata, 'Y', terms=('B', 'C', 'A²'))


def test_rank_deficient_selection_is_rejected(monkeypatch):
    import doe_rsm
    frame, metadata = create_bbd(spec(3))
    frame['响应_Y'] = np.arange(len(frame), dtype=float)
    original = doe_rsm.model_matrix

    def singular(coded):
        matrix = original(coded)
        matrix[:, -1] = matrix[:, -2]
        return matrix

    monkeypatch.setattr(doe_rsm, 'model_matrix', singular)
    with pytest.raises(ValueError, match='秩亏'):
        analyze_rsm(frame, metadata, 'Y')


def test_block_effect_is_estimated_when_blocks_are_used():
    frame, metadata = create_bbd(spec(4, blocks=3), replicates=2)
    coded = frame[['编码_A', '编码_B', '编码_C', '编码_D']].to_numpy(float)
    response = 20 + 2*coded[:, 0] + 5*(frame['区组'].to_numpy(float) == 2)
    frame['响应_Y'] = response
    with_blocks = analyze_rsm(frame, metadata, 'Y')
    without = analyze_rsm(frame, metadata, 'Y', use_blocks=False)
    assert with_blocks['p'] == without['p'] + 2
    assert with_blocks['sse'] < without['sse']
