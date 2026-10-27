from collections import Counter
from dataclasses import replace
from fractions import Fraction
from itertools import product

import numpy as np
import pytest

from doe_ccd import create_ccd, validate_ccd
from doe_dialog import ccd_number
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
    # B2 起支持自定义 alpha；它只改变轴距，不代表具备旋转性或正交性。
    custom, custom_meta = create_ccd(replace(spec, ccd_alpha=1.1))
    custom_result = restore_design_result(custom, custom_meta)
    assert custom_result.spec.ccd_alpha == 1.1
    custom_coded = np.array(validate_ccd(custom_result), float)
    assert np.max(np.abs(custom_coded)) == pytest.approx(1.1)


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


@pytest.mark.parametrize('low_text, high_text', [
    ('0.1', '0.2'), ('0.2', '0.4'), ('1.1', '2.3'),
    ('65.3', '68.3'), ('65.5', '68.3'), ('-0.1', '0.3'),
    ('1e-300', '2e-300'), ('1e300', '1.1e300'),
])
@pytest.mark.parametrize('face', [True, False])
def test_decimal_levels_keep_ccd_points_distinct_and_coded(low_text, high_text, face):
    low, high = ccd_number(low_text), ccd_number(high_text)
    factors = (FactorSpec('A', 'A', low, high), FactorSpec('B', 'B', -2, 2))
    alpha = 1 if face else (2**2)**.25
    spec = DesignSpec('decimal-ccd', factors, ('Y',), seed=7,
                      design_type='central_composite', ccd_alpha=alpha,
                      ccd_center_points=5, ccd_axial_points=4)
    frame, metadata = create_ccd(spec)
    result = restore_design_result(frame, metadata)
    coded = np.asarray(validate_ccd(result))
    centers = [float((Fraction(f.low) + Fraction(f.high)) / 2) for f in factors]
    axes = []
    for factor in factors:
        if face:
            axes.append((factor.low, factor.high))
        else:
            midpoint = (Fraction(factor.low) + Fraction(factor.high)) / 2
            offset = Fraction(alpha) * (Fraction(factor.high) - Fraction(factor.low)) / 2
            axes.append((float(midpoint-offset), float(midpoint+offset)))

    expected = []
    for run in result.runs:
        row = []
        for i, factor in enumerate(factors):
            actual = run.settings[factor.factor_id]
            if run.point_type == 'factorial':
                assert actual in (factor.low, factor.high)
                value = -1 if actual == factor.low else 1
            elif run.point_type == 'center':
                assert actual == centers[i]
                value = 0
            elif actual == centers[i]:
                value = 0
            else:
                assert actual in axes[i]
                value = -alpha if actual == axes[i][0] else alpha
            recoded = 2 * (Fraction(actual) - Fraction(factor.low)) / (
                Fraction(factor.high) - Fraction(factor.low)) - 1
            assert float(recoded) == pytest.approx(value, abs=1e-14)
            row.append(value)
        expected.append(row)
    np.testing.assert_array_equal(coded, expected)
    for factor in factors:
        values = frame[f'设定_{factor.factor_id}'].tolist()
        assert len(set(values)) >= 3


@pytest.mark.parametrize('text', ['NaN', 'Infinity', '-Infinity', '1e309', '1e-999', 'not-a-number'])
def test_ccd_number_rejects_nonfinite_or_underflowing_input(text):
    with pytest.raises(ValueError):
        ccd_number(text)


def test_ccd_number_preserves_large_integer_and_rejects_float_collisions():
    large = 2**60 + 1
    assert ccd_number(str(large)) == large
    assert ccd_number(f'{large}.0') == float(2**60)
    assert ccd_number('9007199254740993.0') == float(2**53)
    with pytest.raises(ValueError, match='low 必须小于 high'):
        FactorSpec('A', 'A', ccd_number('1.0'), ccd_number('1.0000000000000001'))
    spec = DesignSpec('narrow-ccd', (
        FactorSpec('A', 'A', ccd_number('1.0'), ccd_number('1.0000000000000002')),
        FactorSpec('B', 'B', -1, 1)), ('Y',), seed=1,
        design_type='central_composite', ccd_alpha=1,
        ccd_center_points=5, ccd_axial_points=4)
    with pytest.raises(ValueError, match='中心点'):
        create_ccd(spec)

    coarse_center = replace(spec, factors=(
        FactorSpec('A', 'A', 1.0, 1.0000000000000007), spec.factors[1]))
    with pytest.raises(ValueError, match='中心点'):
        create_ccd(coarse_center)


def test_ccc_axis_that_rounds_to_an_endpoint_is_rejected():
    spec = DesignSpec('narrow-ccc', (
        FactorSpec('A', 'A', 1.0, 1.0000000000000004),
        FactorSpec('B', 'B', -1, 1)), ('Y',), seed=1,
        design_type='central_composite', ccd_alpha=2**.5,
        ccd_center_points=5, ccd_axial_points=4)
    with pytest.raises(ValueError, match='CCC 轴点舍入后未超出'):
        create_ccd(spec)
    assert len(create_ccd(replace(spec, ccd_alpha=1))[0]) == 13
