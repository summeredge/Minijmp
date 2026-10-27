from collections import Counter
from dataclasses import replace
from itertools import product

import numpy as np
import pytest

from doe_ccd import create_ccd, validate_ccd
from doe_core import DesignSpec, FactorSpec, restore_design_result, worksheet_metadata


@pytest.mark.parametrize('k', range(2, 6))
@pytest.mark.parametrize('face', [True, False])
def test_design_counts_rank_and_randomization(k, face):
    alpha = 1 if face else (2 ** k) ** .25
    spec = DesignSpec('ccd', tuple(FactorSpec(x, x, -1, 1) for x in 'ABCDE'[:k]),
                      ('Y',), seed=13, design_type='central_composite',
                      ccd_alpha=alpha, ccd_center_points=5, ccd_axial_points=2*k)
    frame, meta = create_ccd(spec)
    frame2, _ = create_ccd(spec)
    assert frame['运行ID'].tolist() == frame2['运行ID'].tolist()
    assert Counter(frame['点类型']) == {'factorial': 2**k, 'axial': 2*k, 'center': 5}
    rows = np.array(validate_ccd(restore_design_result(frame, meta)))
    actual_factorial = {tuple(row) for row in rows[np.array(frame['点类型']) == 'factorial']}
    assert actual_factorial == set(product((-1, 1), repeat=k))
    axial = rows[np.array(frame['点类型']) == 'axial']
    expected = {tuple(sign*alpha if j == i else 0 for j in range(k))
                for i in range(k) for sign in (-1, 1)}
    assert {tuple(row) for row in axial} == expected
    matrix = np.column_stack([np.ones(len(rows)), rows, rows**2] +
                             [rows[:, i]*rows[:, j] for i in range(k) for j in range(i+1, k)])
    assert np.linalg.matrix_rank(matrix) == matrix.shape[1]
    frame.loc[0, '设定_A'] = 123
    with pytest.raises(ValueError):
        restore_design_result(frame, meta)


def test_bad_axis_rejected_even_with_new_fingerprint():
    spec = DesignSpec('ccd', (FactorSpec('A', 'A', -1, 1), FactorSpec('B', 'B', -1, 1)),
                      ('Y',), seed=1, design_type='central_composite', ccd_alpha=1,
                      ccd_center_points=5, ccd_axial_points=4)
    frame, meta = create_ccd(spec)
    index = frame.index[frame['点类型'] == 'axial'][0]
    frame.loc[index, '设定_A'] = .5
    with pytest.raises(ValueError, match='轴点'):
        worksheet_metadata(frame, spec, meta['column_map'])
    with pytest.raises(ValueError):
        create_ccd(replace(spec, ccd_alpha=1.1))


def test_coded_levels_tampering_rejected():
    spec = DesignSpec('ccd', (FactorSpec('A', 'A', -1, 1), FactorSpec('B', 'B', -1, 1)),
                      ('Y',), seed=1, design_type='central_composite', ccd_alpha=1,
                      ccd_center_points=5, ccd_axial_points=4)
    frame, meta = create_ccd(spec)
    frame.loc[0, '编码_A'] = 99
    with pytest.raises(ValueError, match='编码水平'):
        restore_design_result(frame, meta)


def test_large_integer_and_invalid_alpha_are_rejected():
    factors = (FactorSpec('A', 'A', 2**60+1, 2**60+1025), FactorSpec('B', 'B', -1, 1))
    spec = DesignSpec('ccd', factors, ('Y',), seed=1, design_type='central_composite',
                      ccd_alpha=1, ccd_center_points=5, ccd_axial_points=4)
    with pytest.raises(ValueError, match='无损'):
        create_ccd(spec)
    with pytest.raises(ValueError):
        replace(spec, ccd_alpha=float('inf'))


def test_randomization_does_not_change_global_prng():
    import random
    spec = DesignSpec('ccd', (FactorSpec('A', 'A', -1, 1), FactorSpec('B', 'B', -1, 1)),
                      ('Y',), seed=1, design_type='central_composite', ccd_alpha=1,
                      ccd_center_points=5, ccd_axial_points=4)
    state = random.getstate()
    create_ccd(spec)
    assert random.getstate() == state


@pytest.mark.parametrize('k', range(2, 6))
def test_rotatable_ccc_has_equal_prediction_variance_at_equal_radius(k):
    alpha = (2**k)**.25
    spec = DesignSpec('ccd', tuple(FactorSpec(x, x, -1, 1) for x in 'ABCDE'[:k]),
                      ('Y',), seed=4, design_type='central_composite',
                      ccd_alpha=alpha, ccd_center_points=5, ccd_axial_points=2*k)
    frame, meta = create_ccd(spec)
    rows = np.array(validate_ccd(restore_design_result(frame, meta)), float)
    def basis(row):
        return np.array([1, *row, *(row**2),
                         *(row[i]*row[j] for i in range(k) for j in range(i+1, k))])
    matrix = np.array([basis(row) for row in rows])
    covariance = np.linalg.inv(matrix.T @ matrix)
    axial = np.zeros(k)
    axial[0] = 1
    diagonal = np.zeros(k)
    diagonal[:2] = 1/np.sqrt(2)
    assert basis(axial) @ covariance @ basis(axial) == pytest.approx(
        basis(diagonal) @ covariance @ basis(diagonal), abs=1e-12)


def test_actual_levels_follow_coded_conversion():
    factors = (FactorSpec('A', 'A', 10, 20), FactorSpec('B', 'B', -2, 2))
    spec = DesignSpec('ccd', factors, ('Y',), seed=5, design_type='central_composite',
                      ccd_alpha=2**.5, ccd_center_points=5, ccd_axial_points=4)
    frame, _ = create_ccd(spec)
    for factor in factors:
        actual = frame[f'设定_{factor.factor_id}'].to_numpy(float)
        coded = frame[f'编码_{factor.factor_id}'].to_numpy(float)
        np.testing.assert_allclose(actual, (factor.low+factor.high)/2 +
                                   coded*(factor.high-factor.low)/2, rtol=1e-15)
        np.testing.assert_allclose((actual-(factor.low+factor.high)/2) /
                                   ((factor.high-factor.low)/2), coded, atol=1e-15)
