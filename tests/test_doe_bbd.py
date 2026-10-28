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


@pytest.mark.parametrize(('k', 'blocks'), [(9, 1), (9, 5), (9, 10), (10, 1), (10, 2)])
def test_high_dimension_literature_points_and_orthogonal_blocks(k, blocks):
    # Independent construction from Box and Behnken (1960), Table 4.
    if k == 9:
        groups = ([tuple(3*r+c for r in range(3)) for c in range(3)] +
                  [tuple(3*r+c for c in range(3)) for r in range(3)] +
                  [tuple(3*r+(c+r)%3 for r in range(3)) for c in range(3)] +
                  [tuple(3*r+(c-r)%3 for r in range(3)) for c in range(3)] +
                  [tuple(3*r+c for r in range(3)) for c in range(3)])
    else:
        groups = [(1,5,6,9), (0,1,4,9), (1,2,6,7), (1,3,5,8),
                  (0,7,8,9), (2,3,4,9), (0,3,6,7), (2,4,6,8),
                  (0,2,5,8), (3,4,5,7)]
    expected = reference_matrix(groups, k, 10)
    frame, metadata = create_bbd(spec(k, blocks=blocks))
    result = restore_design_result(frame, metadata)
    coded = np.asarray(validate_bbd(result, frame))
    assert Counter(map(tuple, coded)) == Counter(map(tuple, expected))
    assert Counter(frame['点类型']) == {'edge': len(expected)-10, 'center': 10}
    model = quadratic(coded)
    p = 55 if k == 9 else 66
    assert model.shape[1] == p and np.linalg.matrix_rank(model) == p
    assert np.linalg.cond(model) < 10
    for i in range(k):
        assert sum(coded[:, i] == -1) == sum(coded[:, i] == 1)
        for j in range(i+1, k):
            assert np.any(coded[:, i] * coded[:, j])
    if blocks > 1:
        indicator = np.column_stack([frame['区组'].to_numpy() == b
                                     for b in range(1, blocks+1)]).astype(float)
        assert set(indicator.sum(axis=0)) == {len(frame) / blocks}
        centered_model = model - model.mean(axis=0)
        centered_blocks = indicator - indicator.mean(axis=0)
        np.testing.assert_allclose(centered_model.T @ centered_blocks, 0, atol=1e-12)
        assert np.linalg.matrix_rank(np.column_stack([model, indicator[:, 1:]])) == p+blocks-1
        assert all(sum((frame['区组'] == b) & (frame['点类型'] == 'center')) == 10//blocks
                   for b in range(1, blocks+1))


@pytest.mark.parametrize(('k', 'blocks'), [(9, 5), (9, 10), (10, 2)])
def test_high_dimension_quadratic_block_fit_and_prediction(k, blocks):
    from doe_predict import predict_point
    frame, metadata = create_bbd(spec(k, blocks=blocks))
    coded = frame[[f'编码_{chr(65+i)}' for i in range(k)]].to_numpy(float)
    frame['响应_Y'] = (7 + coded @ np.arange(1, k+1) +
                       (coded*coded).sum(axis=1) + 3*coded[:, 0]*coded[:, 1] +
                       2*(frame['区组'].to_numpy()-1))
    result = analyze_rsm(frame, metadata, 'Y')
    assert result['sse'] < 1e-20
    assert result['df'] == len(frame) - (1+2*k+k*(k-1)//2+blocks-1)
    coeff = dict(zip(result['names'], result['coefficients']))
    assert coeff['截距'] == pytest.approx(7, abs=1e-9)
    assert coeff['A*B'] == pytest.approx(3, abs=1e-9)
    for i in range(k):
        assert coeff[chr(65+i)] == pytest.approx(i+1, abs=1e-9)
        assert coeff[chr(65+i)+'²'] == pytest.approx(1, abs=1e-9)
        for j in range(i+1, k):
            expected_interaction = 3 if (i, j) == (0, 1) else 0
            assert coeff[f'{chr(65+i)}*{chr(65+j)}'] == pytest.approx(expected_interaction, abs=1e-9)
    for b in range(2, blocks+1):
        assert coeff[f'区组{b}'] == pytest.approx(2*(b-1), abs=1e-9)
    values = {chr(65+i): 0.5 for i in range(k)}
    prediction = predict_point(frame, metadata, 'Y', values)
    expected = 7 + .5*sum(range(1,k+1)) + .25*k + .75
    assert prediction['prediction'] == pytest.approx(expected, abs=1e-8)


@pytest.mark.parametrize(('k', 'blocks'), [(9, 5), (10, 2)])
def test_high_dimension_independent_repeats_and_pure_error(k, blocks):
    frame, metadata = create_bbd(spec(k, blocks=blocks), replicates=2)
    x = frame[[f'编码_{chr(65+i)}' for i in range(k)]].to_numpy(float)
    frame['响应_Y'] = 7 + x.sum(axis=1) + (x*x).sum(axis=1) + np.where(frame['重复'] == 1, -1, 1)
    result = analyze_rsm(frame, metadata, 'Y')
    groups = frame.groupby(['区组'] + [f'编码_{chr(65+i)}' for i in range(k)])['响应_Y']
    pure_sse = sum(((values - values.mean())**2).sum() for _, values in groups)
    distinct = groups.ngroups
    assert result['sse'] == pytest.approx(len(frame), abs=1e-8)
    assert result['pure_error_sse'] == pytest.approx(pure_sse, abs=1e-8)
    assert result['pure_error_df'] == len(frame)-distinct
    assert result['lack_of_fit_df'] == distinct - (1+2*k+k*(k-1)//2+blocks-1)
    assert result['lack_of_fit_sse'] == pytest.approx(0, abs=1e-8)
    assert result['inference'] is not None
    assert result['lack_of_fit']['f'] == pytest.approx(0, abs=1e-8)
    assert result['lack_of_fit']['p'] == pytest.approx(1, abs=1e-8)
    assert result['curvature']['f'] is None and result['curvature']['p'] is None


@pytest.mark.parametrize(('k', 'blocks'), [(9, 5), (9, 10), (10, 2)])
def test_high_dimension_randomization_and_strict_recovery(k, blocks):
    first, meta = create_bbd(spec(k, seed=11, blocks=blocks), replicates=2)
    same, _ = create_bbd(spec(k, seed=11, blocks=blocks), replicates=2)
    other, _ = create_bbd(spec(k, seed=12, blocks=blocks), replicates=2)
    assert first['运行ID'].tolist() == same['运行ID'].tolist()
    assert first['运行ID'].tolist() != other['运行ID'].tolist()
    columns = ['标准序', '区组', '重复'] + [f'编码_{chr(65+i)}' for i in range(k)]
    assert (first.sort_values('标准序')[columns].to_numpy() ==
            other.sort_values('标准序')[columns].to_numpy()).all()
    assert Counter(first['重复']) == {1: len(first)//2, 2: len(first)//2}
    for block in range(1, blocks+1):
        orders = first.loc[first['区组'] == block, '运行序'].tolist()
        assert orders == list(range(min(orders), max(orders)+1))
    restore_design_result(first, meta)
    damaged = first.copy()
    damaged.loc[0, '设定_A'] = 0.3
    with pytest.raises(ValueError):
        restore_design_result(damaged, meta)


@pytest.mark.parametrize(('k', 'blocks'), [(9, 2), (9, 3), (10, 5), (10, 10)])
def test_high_dimension_invalid_block_options(k, blocks):
    with pytest.raises(ValueError, match='区组数'):
        create_bbd(spec(k, blocks=blocks))


def test_high_dimension_bbd_categorical_pure_error_separates_levels():
    factors = spec(9).factors + (FactorSpec('J', 'batch', None, None,
                                           factor_type='categorical', levels=('low', 'high')),)
    design = DesignSpec('high-categorical', factors, ('Y',), seed=11,
                        design_type='box_behnken', block_count=5, ccd_center_points=10)
    frame, metadata = create_bbd(design, replicates=2)
    assert sum(frame['点类型'] == 'center') == 40
    frame['响应_Y'] = np.where(frame['设定_J'] == 'high', 100.0, 0.0)
    result = analyze_rsm(frame, metadata, 'Y')
    assert result['pure_error_sse'] == pytest.approx(0, abs=1e-18)
    assert result['sse'] == pytest.approx(0, abs=1e-18)


@pytest.mark.parametrize(('k', 'blocks', 'centers'), [(9, 5, 15), (9, 10, 20), (10, 2, 12)])
def test_high_dimension_custom_centers_and_replication(k, blocks, centers):
    frame, metadata = create_bbd(spec(k, blocks=blocks, centers=centers), replicates=2)
    assert sum(frame['点类型'] == 'center') == 2*centers
    for block in range(1, blocks+1):
        assert sum((frame['区组'] == block) & (frame['点类型'] == 'center')) == 2*centers//blocks
    validate_bbd(restore_design_result(frame, metadata), frame)
    with pytest.raises(ValueError, match='均分'):
        create_bbd(spec(k, blocks=blocks, centers=centers+1))


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
