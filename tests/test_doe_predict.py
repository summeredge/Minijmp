"""响应面点预测：独立解析值、区间、分类水平、区组与过期快照。"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy import stats

from doe_core import FactorSpec
from doe_custom import define_custom
from doe_bbd import create_bbd
from doe_ccd import create_ccd
from doe_core import DesignSpec, restore_design_result
from doe_predict import predict_point, snapshot_id
from doe_rsm_model import TermModel


INTERVAL_REFERENCE = json.loads((Path(__file__).parent / "fixtures"
                                 / "doe_phase2_interval_reference" / "reference.json")
                                .read_text(encoding="utf-8"))


def _custom_interval_design(points=None, responses=None):
    if points is None:
        points = INTERVAL_REFERENCE["points"]
    if responses is None:
        responses = {"Y": INTERVAL_REFERENCE["responses"]}
    frame = pd.DataFrame({
        "运行ID": [f"R{index:05d}" for index in range(1, len(points)+1)],
        "标准序": list(range(1, len(points)+1)),
        "运行序": list(range(1, len(points)+1)),
        "点类型": ["center" if tuple(point) == (0.0, 0.0) else "edge"
                   for point in points],
        "重复": [1] * len(points),
        "A": [point[0] for point in points],
        "B": [point[1] for point in points],
    })
    names = tuple(responses)
    for name, values in responses.items():
        frame[name] = values
    response_map = {name: name for name in names}
    factors = (FactorSpec("A", "A", -1, 1), FactorSpec("B", "B", -1, 1))
    terms = ("A", "B", "A²", "B²", "A*B")
    frame, metadata, _ = define_custom(
        frame, design_type="custom_rsm", factors=factors, responses=names,
        model_terms=terms, column_map={
            "run_id": "运行ID", "standard_order": "标准序", "run_order": "运行序",
            "point_type": "点类型", "replicate": "重复",
            "factors": {"A": "A", "B": "B"}, "responses": response_map,
        })
    return frame, metadata


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
    blocked_intervals = predict_point(
        frame, metadata, 'Y', {'A': 1, 'B': 0}, confidence=.95)
    assert blocked_intervals['prediction'] == pytest.approx(12, abs=1e-9)
    assert blocked_intervals['intervals']['status'] == '不可用'
    assert '区组' in blocked_intervals['intervals']['reason']
    ignored_blocks = predict_point(
        frame, metadata, 'Y', {'A': 1, 'B': 0}, blocks=False, confidence=.95)
    assert ignored_blocks['intervals']['status'] == '不可用'


@pytest.mark.parametrize('confidence,side', [
    (0.90, 'two_sided'), (0.95, 'two_sided'), (0.99, 'two_sided'),
    (0.90, 'lower'), (0.95, 'lower'), (0.99, 'lower'),
    (0.90, 'upper'), (0.95, 'upper'), (0.99, 'upper'),
])
def test_prediction_intervals_match_independent_reference(confidence, side):
    frame, metadata = _custom_interval_design()
    result = predict_point(
        frame, metadata, 'Y', {'A': 0.5, 'B': 0.25},
        confidence=confidence, side=side)
    expected = INTERVAL_REFERENCE['intervals'][f'{confidence:.2f}'][side]
    interval = result['intervals']
    assert result['prediction'] == pytest.approx(INTERVAL_REFERENCE['prediction'])
    assert result['inference'] is None  # no pure error; residual MSE is still valid
    assert interval['status'] == '可用'
    assert interval['df'] == INTERVAL_REFERENCE['df']
    assert interval['h0'] == pytest.approx(INTERVAL_REFERENCE['h0'])
    assert interval['se_fit'] == pytest.approx(INTERVAL_REFERENCE['se_fit'])
    assert interval['critical_value'] == pytest.approx(expected['critical_value'])
    for actual, target in zip((interval['ci_low'], interval['ci_high']),
                              expected['ci']):
        if target is None:
            assert actual is None
        else:
            assert actual == pytest.approx(target)
    for actual, target in zip((interval['pi_low'], interval['pi_high']),
                              expected['pi']):
        if target is None:
            assert actual is None
        else:
            assert actual == pytest.approx(target)
    if side == 'two_sided':
        assert interval['ci_high']-interval['ci_low'] <= \
            interval['pi_high']-interval['pi_low']
    assert result['extrapolation'] is False


@pytest.mark.parametrize('family', ('ccd', 'bbd'))
def test_ccd_and_bbd_intervals_use_the_actual_fitted_matrix(family):
    if family == 'ccd':
        frame, metadata = ccd(two_factors=True)
    else:
        spec = DesignSpec(
            'interval-bbd', tuple(FactorSpec(name, name, -1, 1) for name in 'ABC'),
            ('Y',), seed=17, design_type='box_behnken', ccd_center_points=3)
        frame, metadata = create_bbd(spec)
    coded_columns = [f'编码_{name}' for name in 'ABC']
    coded = frame[coded_columns].to_numpy(dtype=float)
    a, b, c = coded.T
    frame['响应_Y'] = (5 + 2*a - b + .5*c + 1.5*a*b - .7*b*c
                        + .2*a*a + .4*b*b + np.sin(np.arange(len(frame))*.73))
    design = restore_design_result(frame, metadata)
    factor_ids = [factor.factor_id for factor in design.spec.factors
                  if factor.factor_type == 'continuous']
    model = TermModel(design.spec.factors)
    matrix = model.matrix([
        {factor_id: coded[row, column]
         for column, factor_id in enumerate(factor_ids)}
        for row in range(len(coded))])
    y = frame['响应_Y'].to_numpy(dtype=float)
    beta = np.linalg.lstsq(matrix, y, rcond=None)[0]
    residual = y - matrix @ beta
    df = len(y) - matrix.shape[1]
    mse = float(residual @ residual) / df
    settings = {'A': .25, 'B': -.2, 'C': .4}
    prediction_row = model.row(settings)
    h0 = float(prediction_row @ np.linalg.solve(matrix.T @ matrix, prediction_row))
    prediction = float(prediction_row @ beta)
    se_fit = np.sqrt(mse*h0)
    critical = stats.t.ppf(.975, df)

    result = predict_point(frame, metadata, 'Y', settings, confidence=.95)
    intervals = result['intervals']
    assert intervals['status'] == '可用', intervals
    assert intervals['df'] == df
    assert result['prediction'] == pytest.approx(prediction, rel=1e-10)
    assert intervals['h0'] == pytest.approx(h0, rel=1e-10)
    assert intervals['se_fit'] == pytest.approx(se_fit, rel=1e-10)
    assert intervals['ci_low'] == pytest.approx(prediction-critical*se_fit, rel=1e-10)


def test_prediction_intervals_handle_responses_separately_and_unavailable_edges():
    points = INTERVAL_REFERENCE['points']
    response_y = INTERVAL_REFERENCE['responses']
    frame, metadata = _custom_interval_design(
        points, {'Y': response_y, 'Z': [2*value+7 for value in response_y]})
    y_result = predict_point(
        frame, metadata, 'Y', {'A': 0.5, 'B': 0.25}, confidence=.95)
    z_result = predict_point(
        frame, metadata, 'Z', {'A': 0.5, 'B': 0.25}, confidence=.95)
    assert z_result['prediction'] == pytest.approx(2*y_result['prediction']+7)
    assert z_result['intervals']['se_fit'] == pytest.approx(
        2*y_result['intervals']['se_fit'])

    saturated_indices = (0, 1, 2, 3, 4, 6)
    saturated, saturated_meta = _custom_interval_design(
        [points[i] for i in saturated_indices],
        {'Y': [response_y[i] for i in saturated_indices]})
    no_df = predict_point(
        saturated, saturated_meta, 'Y', {'A': 0.5, 'B': 0.25}, confidence=.95)
    assert no_df['intervals']['status'] == '不可用'
    assert '自由度' in no_df['intervals']['reason']

    exact_y = [10+2*a-b+3*a*a+4*b*b+a*b for a, b in points]
    exact, exact_meta = _custom_interval_design(points, {'Y': exact_y})
    zero_mse = predict_point(
        exact, exact_meta, 'Y', {'A': 0.5, 'B': 0.25}, confidence=.95)
    assert zero_mse['intervals']['status'] == '不可用'
    assert '残差方差' in zero_mse['intervals']['reason']

