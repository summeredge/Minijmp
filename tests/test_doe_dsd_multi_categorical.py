"""DSD 多二水平分类构造：独立行列式参考、结构和附加中心点。"""
from dataclasses import replace
from fractions import Fraction
from itertools import product

import numpy as np
import pandas as pd
import pytest

from doe_core import DesignSpec, FactorSpec, restore_design_result
from doe_dsd import _dsd_matrix_for_key, create_dsd, validate_dsd
from doe_screening_matrices import MATRICES


MULTI_CASES = tuple((m, c) for m in range(4, 13) for c in range(2, 5)
                    if (m, c) != (4, 2))


def _spec(continuous_count, categorical_count=0):
    factors = tuple(
        FactorSpec(f'X{i}', f'X{i}', -1, 1)
        for i in range(1, continuous_count + 1)
    ) + tuple(
        FactorSpec(f'C{i}', f'C{i}', None, None,
                   factor_type='categorical', levels=(f'低{i}', f'高{i}'))
        for i in range(1, categorical_count + 1)
    )
    if (continuous_count, categorical_count) == (4, 2):
        key, source = 'dsd4c2', 'foldover.dsd4c2'
    elif categorical_count:
        key = f'dsd{continuous_count}c{categorical_count}'
        source = f'jones.{key}'
    else:
        key, source = f'dsd{continuous_count}', f'conference.dsd{continuous_count}'
    identity = {'construction_id': key + '.v1', 'source_kind': 'mathematical_construction',
                'source_id': source, 'matrix_sha256': '0' * 64}
    return DesignSpec('dsd', factors, ('Y',), seed=41, design_type='definitive_screening',
                      screening_matrix=identity, schema_version=5)


def _reference_max_logdet(continuous_count, categorical_count):
    """从基础 MATRICES 穷举候选，以 LAPACK slogdet 独立核对最优值。"""
    factor_count = continuous_count + categorical_count
    base = [list(row) for row in MATRICES[f'dsd{factor_count}'] if any(row)]
    zero_pairs = [
        [row for row, values in enumerate(base) if values[column] == 0]
        for column in range(continuous_count, factor_count)
    ]
    best_logdet = -np.inf
    for signs in product((-1, 1), repeat=2 * categorical_count):
        b, z = signs[:categorical_count], signs[categorical_count:]
        rows = [row[:] for row in base]
        for column, pair, level in zip(range(continuous_count, factor_count), zero_pairs, z):
            rows[pair[0]][column], rows[pair[1]][column] = level, -level
        rows.extend(([0] * continuous_count + list(b),
                     [0] * continuous_count + [-level for level in b]))
        design = np.asarray([[1, *row] for row in rows], dtype=float)
        sign, logdet = np.linalg.slogdet(design.T @ design)
        if sign > 0:
            best_logdet = max(best_logdet, logdet)
    return best_logdet


def _exact_determinant(matrix):
    work = [[Fraction(value) for value in row] for row in matrix]
    determinant = Fraction(1)
    for column in range(len(work)):
        pivot_row = next((row for row in range(column, len(work))
                          if work[row][column]), None)
        if pivot_row is None:
            return Fraction(0)
        if pivot_row != column:
            work[column], work[pivot_row] = work[pivot_row], work[column]
            determinant = -determinant
        pivot = work[column][column]
        determinant *= pivot
        for row in range(column + 1, len(work)):
            scale = work[row][column] / pivot
            for index in range(column + 1, len(work)):
                work[row][index] -= scale * work[column][index]
            work[row][column] = 0
    return determinant


def _exact_reference_first_max(continuous_count, categorical_count):
    factor_count = continuous_count + categorical_count
    base = [list(row) for row in MATRICES[f'dsd{factor_count}'] if any(row)]
    zero_pairs = [[row for row, values in enumerate(base) if values[column] == 0]
                  for column in range(continuous_count, factor_count)]
    best_determinant, best_rows, maximum_count = None, None, 0
    for signs in product((-1, 1), repeat=2 * categorical_count):
        b, z = signs[:categorical_count], signs[categorical_count:]
        rows = [row[:] for row in base]
        for column, pair, level in zip(range(continuous_count, factor_count), zero_pairs, z):
            rows[pair[0]][column], rows[pair[1]][column] = level, -level
        rows.extend(([0] * continuous_count + list(b),
                     [0] * continuous_count + [-level for level in b]))
        design = [[1, *row] for row in rows]
        information = [[sum(row[i] * row[j] for row in design)
                        for j in range(factor_count + 1)]
                       for i in range(factor_count + 1)]
        determinant = _exact_determinant(information)
        if best_determinant is None or determinant > best_determinant:
            best_determinant, best_rows, maximum_count = determinant, rows, 1
        elif determinant == best_determinant:
            maximum_count += 1
    return tuple(tuple(row) for row in best_rows), maximum_count


def _coded_matrix(frame, factors):
    rows = frame.sort_values('标准序')
    columns = []
    for factor in factors:
        values = rows[f'设定_{factor.factor_id}']
        if factor.factor_type == 'categorical':
            lookup = {factor.levels[0]: -1, factor.levels[1]: 1}
        else:
            lookup = {factor.low: -1, (factor.low + factor.high) / 2: 0, factor.high: 1}
        columns.append(values.map(lookup).to_numpy(dtype=int))
    return np.column_stack(columns)


@pytest.mark.parametrize('key', sorted(key for key in MATRICES if key.startswith('dsd')))
def test_existing_dsd_keys_still_return_the_fixed_matrix(key):
    assert _dsd_matrix_for_key(key) is MATRICES[key]


@pytest.mark.parametrize('continuous_count,categorical_count', MULTI_CASES)
def test_multi_categorical_matrix_preserves_foldover_and_dsd_properties(
        continuous_count, categorical_count):
    key = f'dsd{continuous_count}c{categorical_count}'
    matrix = _dsd_matrix_for_key(key)
    base = MATRICES[f'dsd{continuous_count + categorical_count}']
    coded = np.asarray(matrix, dtype=int)
    foldover_pairs = (len(base) - 1) // 2

    assert len(matrix) == len(base) + 1
    assert coded.shape[1] == continuous_count + categorical_count
    assert set(np.unique(coded)) <= {-1, 0, 1}
    np.testing.assert_array_equal(coded[foldover_pairs:2 * foldover_pairs],
                                  -coded[:foldover_pairs])
    np.testing.assert_array_equal(coded[-1], -coded[-2])
    np.testing.assert_array_equal(coded.sum(axis=0), 0)
    assert all(np.count_nonzero(coded[:, column] == 0) == 4
               for column in range(continuous_count))
    assert all(set(coded[:, column]) == {-1, 1}
               for column in range(continuous_count, coded.shape[1]))

    main = np.column_stack((np.ones(len(coded), dtype=int), coded))
    assert np.linalg.matrix_rank(main) == coded.shape[1] + 1
    second_order = np.column_stack([
        coded[:, i] * coded[:, j]
        for i in range(coded.shape[1])
        for j in range(i, coded.shape[1])
        if i != j or i < continuous_count
    ])
    np.testing.assert_array_equal(coded.T @ second_order, 0)


@pytest.mark.parametrize(('continuous_count', 'categorical_count'), [(4, 3), (8, 2), (12, 4)])
def test_multi_categorical_matrix_matches_independent_exhaustive_d_optimum(
        continuous_count, categorical_count):
    key = f'dsd{continuous_count}c{categorical_count}'
    matrix = np.asarray(_dsd_matrix_for_key(key), dtype=float)
    design = np.column_stack((np.ones(len(matrix)), matrix))
    sign, logdet = np.linalg.slogdet(design.T @ design)
    assert sign > 0
    assert logdet == pytest.approx(
        _reference_max_logdet(continuous_count, categorical_count), abs=1e-10)


def test_d_optimal_tie_uses_first_configuration_in_b_then_z_order():
    expected, maximum_count = _exact_reference_first_max(5, 2)
    assert maximum_count >= 4
    assert _dsd_matrix_for_key('dsd5c2') == expected


@pytest.mark.parametrize('continuous_count,categorical_count', MULTI_CASES)
def test_multi_categorical_schur_reference_covers_every_supported_combination(
        continuous_count, categorical_count):
    """直接推导信息矩阵的 Schur 补，不重建生产候选运行矩阵。"""
    m, c = continuous_count, categorical_count
    base = np.asarray(MATRICES[f'dsd{m + c}'], dtype=int)
    half = (len(base) - 1) // 2
    conference = base[:half]
    q = half - 1
    # 固定 conference 列子集是输入；独立核验其数学性质，不能假设常量正确。
    np.testing.assert_array_equal(base[half:-1], -conference)
    np.testing.assert_array_equal(base[-1], 0)
    np.testing.assert_array_equal(conference.T @ conference, q * np.eye(m + c))
    assert np.count_nonzero(conference == 0, axis=0).tolist() == [1] * (m + c)
    assert np.isin(conference, (-1, 0, 1)).all()
    zero_rows = [int(np.flatnonzero(conference[:, m + j] == 0)[0]) for j in range(c)]
    assert len(set(zero_rows)) == c

    best, first_signs = Fraction(-1), None
    for signs in product((-1, 1), repeat=2 * c):
        b, z = signs[:c], signs[c:]
        # A=2q I_m；B_ij=2 z_j C[r_j,i]；det(X'X)=n det(A) det(D-B'A^-1B)。
        schur = []
        for j in range(c):
            row = []
            for k in range(c):
                category_gram = (2 * q + 4 if j == k else 2 * (
                    z[j] * int(conference[zero_rows[j], m + k])
                    + z[k] * int(conference[zero_rows[k], m + j]) + b[j] * b[k]))
                projection = Fraction(2 * z[j] * z[k] * sum(
                    int(conference[zero_rows[j], i]) * int(conference[zero_rows[k], i])
                    for i in range(m)), q)
                row.append(category_gram - projection)
            schur.append(row)
        determinant = (2 * half + 2) * (2 * q) ** m * _exact_determinant(schur)
        if determinant > best:
            best, first_signs = determinant, signs

    actual = np.asarray(_dsd_matrix_for_key(f'dsd{m}c{c}'), dtype=int)
    design = np.column_stack((np.ones(len(actual), dtype=int), actual))
    actual_determinant = _exact_determinant((design.T @ design).tolist())
    assert actual_determinant == best > 0
    chosen_signs = tuple(int(value) for value in actual[-2, m:]) + tuple(
        int(actual[zero_rows[j], m + j]) for j in range(c))
    assert chosen_signs == first_signs

    # 一次分类零位翻转会破坏折叠平衡；独立 oracle 必须拒绝此错误运行表。
    wrong = design.copy()
    wrong[zero_rows[0], m + 1] *= -1
    assert _exact_determinant((wrong.T @ wrong).tolist()) != best


def test_four_continuous_two_categorical_uses_the_legacy_matrix():
    spec = _spec(4, 2)
    frame, metadata = create_dsd(spec)
    coded = _coded_matrix(frame, spec.factors)
    np.testing.assert_array_equal(coded, MATRICES['dsd4c2'])
    assert metadata['design']['screening_matrix']['construction_id'] == 'dsd4c2.v1'


@pytest.mark.parametrize(('continuous_count', 'categorical_count'), [(6, 0), (4, 1), (4, 2)])
def test_zero_or_none_extra_centers_preserve_legacy_output(continuous_count, categorical_count):
    spec = _spec(continuous_count, categorical_count)
    expected_frame, expected_metadata = create_dsd(spec)
    for value in (None, 0):
        frame, metadata = create_dsd(spec, center_points=value)
        pd.testing.assert_frame_equal(frame, expected_frame)
        assert metadata == expected_metadata


def test_multi_categorical_extra_centers_cycle_through_every_level_combination():
    spec = _spec(4, 3)
    center_count = 16
    frame, metadata = create_dsd(spec, replicates=2, blocks=2, center_points=center_count)
    restored = restore_design_result(frame, metadata)
    validate_dsd(restored)
    assert restored.spec.center_point_count == center_count
    assert restored.spec.screening_matrix['construction_id'] == 'dsd4c3.v1'

    expected_centers = tuple((0,) * 4 + combination
                             for combination in product((-1, 1), repeat=3)) * 2
    for replicate in (1, 2):
        runs = frame[frame['重复'] == replicate].sort_values('标准序')
        coded = _coded_matrix(runs, spec.factors)
        np.testing.assert_array_equal(coded[-center_count:], expected_centers)
        assert runs['点类型'].iloc[-center_count:].eq('pseudo_center').all()
        second_order = np.column_stack([
            coded[:, i] ** 2 for i in range(4)
        ] + [
            coded[:, i] * coded[:, j]
            for i in range(coded.shape[1])
            for j in range(i + 1, coded.shape[1])
        ])
        np.testing.assert_array_equal(coded.T @ second_order, 0)


def test_center_points_default_inherits_spec_and_explicit_value_overrides_it():
    spec = replace(_spec(4, 2), center_point_count=4)
    inherited_frame, inherited_metadata = create_dsd(spec)
    inherited = restore_design_result(inherited_frame, inherited_metadata)
    assert inherited.spec.center_point_count == 4
    assert len(inherited_frame) == len(_dsd_matrix_for_key('dsd4c2')) + 4

    overridden_frame, overridden_metadata = create_dsd(spec, center_points=8)
    overridden = restore_design_result(overridden_frame, overridden_metadata)
    assert overridden.spec.center_point_count == 8
    assert len(overridden_frame) == len(_dsd_matrix_for_key('dsd4c2')) + 8

    disabled_frame, disabled_metadata = create_dsd(spec, center_points=0)
    baseline_frame, baseline_metadata = create_dsd(_spec(4, 2))
    pd.testing.assert_frame_equal(disabled_frame, baseline_frame)
    assert disabled_metadata == baseline_metadata


def test_continuous_extra_centers_accept_any_nonnegative_count():
    spec = _spec(5)
    frame, metadata = create_dsd(spec, center_points=3)
    restored = restore_design_result(frame, metadata)
    validate_dsd(restored)
    assert restored.spec.center_point_count == 3
    assert frame['点类型'].value_counts()['center'] == 4
    coded = _coded_matrix(frame, spec.factors)
    np.testing.assert_array_equal(coded[-3:], np.zeros((3, 5), dtype=int))


@pytest.mark.parametrize('center_points', [-1, True, 1.5, '4'])
def test_invalid_extra_center_count_is_rejected(center_points):
    with pytest.raises(ValueError, match='额外中心点数'):
        create_dsd(_spec(6), center_points=center_points)


@pytest.mark.parametrize(('continuous_count', 'categorical_count', 'center_points'),
                         [(4, 2, 2), (4, 3, 4), (12, 4, 8)])
def test_mixed_extra_centers_must_cover_all_category_combinations(
        continuous_count, categorical_count, center_points):
    with pytest.raises(ValueError, match='分类组合数'):
        create_dsd(_spec(continuous_count, categorical_count), center_points=center_points)


@pytest.mark.parametrize('key', ['dsd3c2', 'dsd13c2', 'dsd4c5', 'dsd4c02', 'pb12'])
def test_unknown_or_out_of_scope_dsd_matrix_keys_are_rejected(key):
    with pytest.raises(KeyError):
        _dsd_matrix_for_key(key)
