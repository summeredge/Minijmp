"""响应面点预测：独立解析值、分类水平、区组、越界与过期快照。"""
import numpy as np
import pytest

from doe_bbd import create_bbd
from doe_ccd import create_ccd
from doe_core import DesignSpec, FactorSpec
from doe_predict import predict_point, snapshot_id


def ccd(two_factors=True):
    factors = (FactorSpec('A', 'A', -1, 1), FactorSpec('B', 'B', -1, 1),
               FactorSpec('C', 'C', -1, 1))
    chosen = factors if two_factors else factors[:2]
    spec = DesignSpec('ccd', chosen, ('Y',),
                      seed=3, design_type='central_composite',
                      ccd_alpha=1, ccd_center_points=5,
                      ccd_axial_points=2 * len(chosen))
    frame, metadata = create_ccd(spec)
    return frame, metadata


def test_quadratic_prediction_matches_independent_polynomial():
    frame, metadata = ccd()
    frame['响应_Y'] = 40 + 3*frame['编码_A'] - 2*frame['编码_B'] + 5*frame['编码_A']**2
    result = predict_point(frame, metadata, 'Y', {'A': 0.5, 'B': -0.25, 'C': 0})
    expected = 40 + 3*0.5 - 2*(-0.25) + 5*0.5**2
    assert result['prediction'] == pytest.approx(expected, abs=1e-9)
    assert result['coded']['A'] == pytest.approx(0.5)
    assert result['settings'] == {'A': 0.5, 'B': -0.25, 'C': 0}


def test_bbd_prediction_uses_the_fitted_model_and_reports_snapshot():
    spec = DesignSpec('bbd', tuple(FactorSpec(chr(65+i), chr(65+i), -1, 1)
                                   for i in range(3)), ('Y',), seed=5,
                      design_type='box_behnken', ccd_center_points=3)
    frame, metadata = create_bbd(spec)
    values = 10 + 2*frame['编码_A'] - frame['编码_B'] + 4*frame['编码_C']
    frame['响应_Y'] = values
    result = predict_point(frame, metadata, 'Y', {'A': 0, 'B': 0, 'C': 1})
    assert result['prediction'] == pytest.approx(14, abs=1e-9)
    assert result['snapshot_id'] == snapshot_id(frame, metadata)
    assert len(result['snapshot_id']) == 16


def test_snapshot_changes_when_a_response_changes():
    frame, metadata = ccd()
    frame['响应_Y'] = 1.0
    before = snapshot_id(frame, metadata)
    frame.loc[frame.index[0], '响应_Y'] = 2.0
    assert snapshot_id(frame, metadata) != before


def test_missing_factor_level_is_rejected():
    frame, metadata = ccd()
    frame['响应_Y'] = 1.0
    with pytest.raises(ValueError, match='缺少因子设置'):
        predict_point(frame, metadata, 'Y', {'A': 0})


def test_unknown_factor_is_rejected():
    frame, metadata = ccd()
    frame['响应_Y'] = 1.0
    with pytest.raises(ValueError, match='未知因子'):
        predict_point(frame, metadata, 'Y', {'A': 0, 'B': 0, 'C': 0, 'D': 0})


def test_level_outside_design_range_is_rejected():
    frame, metadata = ccd()
    frame['响应_Y'] = 1.0
    with pytest.raises(ValueError):
        predict_point(frame, metadata, 'Y', {'A': 1.5, 'B': 0, 'C': 0})


def test_missing_response_is_rejected():
    frame, metadata = ccd()
    frame['响应_Y'] = 1.0
    frame.loc[frame.index[0], '响应_Y'] = np.nan
    with pytest.raises(ValueError):
        predict_point(frame, metadata, 'Y', {'A': 0, 'B': 0, 'C': 0})


def test_categorical_level_is_used_as_a_fixed_slice():
    factors = (FactorSpec('A', 'A', -1, 1), FactorSpec('B', 'B', -1, 1),
               FactorSpec('L', 'lot', None, None, factor_type='categorical',
                          levels=('低', '高')))
    spec = DesignSpec('cat', factors, ('Y',), seed=4,
                      design_type='central_composite', ccd_alpha=1,
                      ccd_center_points=5, ccd_axial_points=4)
    frame, metadata = create_ccd(spec)
    high = (frame['设定_L'] == '高').to_numpy(float)
    frame['响应_Y'] = 10 + 2*frame['编码_A'] + 7*high
    result = predict_point(frame, metadata, 'Y', {'A': 0.5, 'B': 0, 'L': '高'})
    assert result['prediction'] == pytest.approx(18, abs=1e-9)
    with pytest.raises(ValueError, match='水平'):
        predict_point(frame, metadata, 'Y', {'A': 0.5, 'B': 0, 'L': '中'})


def test_block_term_uses_the_reference_block():
    factors = (FactorSpec('A', 'A', -1, 1), FactorSpec('B', 'B', -1, 1))
    spec = DesignSpec('blk', factors, ('Y',), seed=2,
                      design_type='central_composite', ccd_alpha=None,
                      ccd_center_points=5, ccd_axial_points=4, block_count=2)
    frame, metadata = create_ccd(spec)
    block = (frame['区组'] == 2).to_numpy(float)
    frame['响应_Y'] = 10 + 2*frame['编码_A'] + 5*block
    result = predict_point(frame, metadata, 'Y', {'A': 1, 'B': 0})
    assert result['block'] == 1
    assert result['prediction'] == pytest.approx(12, abs=1e-9)
    without = predict_point(frame, metadata, 'Y', {'A': 1, 'B': 0}, blocks=False)
    assert without['block'] is None

