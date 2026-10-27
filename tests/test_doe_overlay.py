"""多响应叠加等高线：独立解析等高线、可行交集与无交集状态。"""
import numpy as np
import pytest

from doe_bbd import create_bbd
from doe_ccd import create_ccd
from doe_core import DesignSpec, FactorSpec
from doe_overlay import overlay_contours


def ccd(levels=(), k=2):
    factors = [FactorSpec(chr(65+i), chr(65+i), -1, 1) for i in range(k)]
    if levels:
        factors.append(FactorSpec('L', 'lot', None, None,
                                  factor_type='categorical', levels=levels))
    spec = DesignSpec('ccd', tuple(factors), ('Y', 'Z'), seed=3,
                      design_type='central_composite', ccd_alpha=1,
                      ccd_center_points=5, ccd_axial_points=2 * len(factors))
    frame, metadata = create_ccd(spec)
    frame['响应_Y'] = 10 + 2*frame['编码_A'] - frame['编码_B']
    frame['响应_Z'] = 20 - frame['编码_A'] + 3*frame['编码_B']
    return frame, metadata


def test_overlay_matches_independent_linear_response_values():
    frame, metadata = ccd()
    result = overlay_contours(frame, metadata, {'Y': (0, 100), 'Z': (0, 100)},
                              'A', 'B', grid=11)
    xx, yy = result['xx'], result['yy']
    np.testing.assert_allclose(result['z']['Y'], 10 + 2*xx - yy, atol=1e-10)
    np.testing.assert_allclose(result['z']['Z'], 20 - xx + 3*yy, atol=1e-10)
    assert result['feasible'].all()
    assert result['feasible_fraction'] == 1.0


def test_feasible_region_is_the_intersection_of_both_responses():
    frame, metadata = ccd()
    result = overlay_contours(frame, metadata, {'Y': (8, 12), 'Z': (16, 24)},
                              'A', 'B', grid=21)
    expected = ((result['z']['Y'] >= 8) & (result['z']['Y'] <= 12) &
                (result['z']['Z'] >= 16) & (result['z']['Z'] <= 24))
    np.testing.assert_array_equal(result['feasible'], expected)
    assert 0 < result['feasible'].mean() < 1
    inside = [result['z']['Y'][result['feasible']], result['z']['Z'][result['feasible']]]
    assert inside[0].min() >= 8 and inside[0].max() <= 12
    assert inside[1].min() >= 16 and inside[1].max() <= 24


def test_disjoint_ranges_report_an_empty_region_without_fake_candidates():
    frame, metadata = ccd()
    result = overlay_contours(frame, metadata, {'Y': (100, 200), 'Z': (0, 100)},
                              'A', 'B', grid=15)
    assert not result['feasible'].any()
    assert result['feasible_fraction'] == 0.0
    assert result['inside_fraction']['Y'] == 0.0
    assert result['inside_fraction']['Z'] == 1.0


def test_fixed_factor_and_categorical_slice_are_applied():
    frame, metadata = ccd(levels=('甲', '乙'))
    high = (frame['设定_L'] == '乙').to_numpy(float)
    frame['响应_Y'] = 10 + 2*frame['编码_A'] - frame['编码_B'] + 5*high
    frame['响应_Z'] = 20 - frame['编码_A'] + 3*frame['编码_B'] - 5*high
    default = overlay_contours(frame, metadata, {'Y': (0, 100), 'Z': (0, 100)},
                               'A', 'B', grid=7)
    sliced = overlay_contours(frame, metadata, {'Y': (0, 100), 'Z': (0, 100)},
                              'A', 'B', grid=7, categories={'L': '乙'})
    np.testing.assert_allclose(sliced['z']['Y'] - default['z']['Y'], 5, atol=1e-9)
    np.testing.assert_allclose(sliced['z']['Z'] - default['z']['Z'], -5, atol=1e-9)
    assert sliced['fixed']['L'] == '乙'
    with pytest.raises(ValueError, match='水平'):
        overlay_contours(frame, metadata, {'Y': (0, 100), 'Z': (0, 100)},
                         'A', 'B', grid=7, categories={'L': '丙'})


def test_fixed_level_outside_coded_range_and_bad_ranges_are_rejected():
    frame, metadata = ccd(k=3)
    with pytest.raises(ValueError, match='−1 至 1'):
        overlay_contours(frame, metadata, {'Y': (0, 1), 'Z': (0, 1)}, 'A', 'B',
                         grid=7, fixed={'C': 2})
    with pytest.raises(ValueError, match='至少需要两个响应'):
        overlay_contours(frame, metadata, {'Y': (0, 1)}, 'A', 'B', grid=7)
    with pytest.raises(ValueError, match='下限必须小于上限'):
        overlay_contours(frame, metadata, {'Y': (1, 1), 'Z': (0, 1)}, 'A', 'B', grid=7)
    with pytest.raises(ValueError, match='两个不同的连续因子'):
        overlay_contours(frame, metadata, {'Y': (0, 1), 'Z': (0, 1)}, 'A', 'A', grid=7)


def test_bbd_overlay_uses_the_same_fitted_model_as_analysis():
    spec = DesignSpec('bbd', tuple(FactorSpec(chr(65+i), chr(65+i), -1, 1)
                                   for i in range(3)), ('Y', 'Z'), seed=5,
                      design_type='box_behnken', ccd_center_points=3)
    frame, metadata = create_bbd(spec)
    a, b, c = (frame[f'编码_{name}'] for name in 'ABC')
    frame['响应_Y'] = 10 + 2*a - b + 4*c
    frame['响应_Z'] = 30 - a + 3*b - 2*c
    result = overlay_contours(frame, metadata, {'Y': (0, 40), 'Z': (0, 40)},
                              'A', 'B', fixed={'C': 0.5}, grid=9)
    np.testing.assert_allclose(result['z']['Y'], 10 + 2*result['xx'] - result['yy'] + 2,
                               atol=1e-9)
    np.testing.assert_allclose(result['z']['Z'], 30 - result['xx'] + 3*result['yy'] - 1,
                               atol=1e-9)
    assert result['fixed']['C'] == 0.5
    assert result['design_type'] == 'box_behnken'

