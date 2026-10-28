"""响应面点预测：独立解析值、分类水平、区组、越界与过期快照。"""
import numpy as np
import pytest

from doe_bbd import create_bbd
from doe_ccd import create_ccd
from doe_core import DesignSpec, FactorSpec
from doe_predict import predict_point, snapshot_id


def test_custom_rsm_prediction_uses_declared_terms_and_reference_block():
    from doe_custom import define_custom
    from test_doe_custom_rsm import _blocked_columns, _blocked_frame

    frame, metadata, _ = define_custom(
        _blocked_frame(), design_type='custom_rsm',
        factors=(FactorSpec('X1', 'X1', -1, 1), FactorSpec('X2', 'X2', -1, 1)),
        responses=('Y',), column_map=_blocked_columns(), block_count=2,
        model_terms=('X1', 'X2', 'X1*X2'))
    result = predict_point(frame, metadata, 'Y', {'X1': 0.5, 'X2': -0.5})
    assert result['prediction'] == pytest.approx(9.5, abs=1e-9)
    assert result['block'] == 'B1'
    assert result['terms'] == ('X1', 'X2', 'X1*X2')
    with pytest.raises(ValueError):
        predict_point(frame, metadata, 'Y', {'X1': 2, 'X2': 0})


def test_custom_rsm_prediction_preserves_text_category():
    from doe_custom import define_custom
    from test_doe_custom_rsm import columns, reference_frame

    frame = reference_frame().drop(columns='X3')
    frame['C'] = ['低' if i % 2 else '高' for i in range(len(frame))]
    frame['Y'] = 5 + 2 * frame['X1'] + 3 * frame['X2'] + 7 * (frame['C'] == '高')
    mapping = columns()
    mapping['factors'] = {name: name for name in ('X1', 'X2', 'C')}
    factors = (FactorSpec('X1', 'X1', -1, 1), FactorSpec('X2', 'X2', -1, 1),
               FactorSpec('C', 'C', None, None, factor_type='categorical',
                          levels=('低', '高')))
    frame, metadata, _ = define_custom(
        frame, design_type='custom_rsm', factors=factors, responses=('Y',),
        column_map=mapping, model_terms=('X1', 'X2', 'C'))
    result = predict_point(frame, metadata, 'Y', {'X1': 0.5, 'X2': -0.5, 'C': '高'})
    assert result['prediction'] == pytest.approx(11.5, abs=1e-9)
    with pytest.raises(ValueError, match='水平'):
        predict_point(frame, metadata, 'Y', {'X1': 0, 'X2': 0, 'C': '未知'})


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
                      ccd_center_points=None, ccd_axial_points=4, block_count=2)
    frame, metadata = create_ccd(spec)
    block = (frame['区组'] == 2).to_numpy(float)
    frame['响应_Y'] = 10 + 2*frame['编码_A'] + 5*block
    result = predict_point(frame, metadata, 'Y', {'A': 1, 'B': 0})
    assert result['block'] == 1
    assert result['prediction'] == pytest.approx(12, abs=1e-9)
    without = predict_point(frame, metadata, 'Y', {'A': 1, 'B': 0}, blocks=False)
    assert without['block'] is None

