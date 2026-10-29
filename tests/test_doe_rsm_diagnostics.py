"""RSM 统计诊断：独立投影平方和、纯误差/失拟/曲率与不可用状态。"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy import stats

from doe_core import FactorSpec
from doe_custom import define_custom
from doe_custom_analysis import analyze_custom_rsm
from doe_bbd import create_bbd
from doe_ccd import create_ccd
from doe_core import DesignSpec, FactorSpec
from doe_rsm import analyze_rsm
from doe_rsm_model import TermModel


INTERVAL_REFERENCE = json.loads((Path(__file__).parent / "fixtures"
                                 / "doe_phase2_interval_reference" / "reference.json")
                                .read_text(encoding="utf-8"))


def custom_reference_design(points=None, responses=None):
    if points is None:
        points = INTERVAL_REFERENCE['points']
    if responses is None:
        responses = {'Y': INTERVAL_REFERENCE['responses']}
    frame = pd.DataFrame({
        '运行ID': [f"R{index:05d}" for index in range(1, len(points)+1)],
        '标准序': list(range(1, len(points)+1)),
        '运行序': list(range(1, len(points)+1)),
        '点类型': ['center' if tuple(point) == (0.0, 0.0) else 'edge'
                   for point in points],
        '重复': [1] * len(points),
        'A': [point[0] for point in points],
        'B': [point[1] for point in points],
    })
    for name, values in responses.items():
        frame[name] = values
    names = tuple(responses)
    frame, metadata, _ = define_custom(
        frame, design_type='custom_rsm',
        factors=(FactorSpec('A', 'A', -1, 1), FactorSpec('B', 'B', -1, 1)),
        responses=names, model_terms=('A', 'B', 'A²', 'B²', 'A*B'),
        column_map={
            'run_id': '运行ID', 'standard_order': '标准序', 'run_order': '运行序',
            'point_type': '点类型', 'replicate': '重复',
            'factors': {'A': 'A', 'B': 'B'},
            'responses': {name: name for name in names},
        })
    return frame, metadata


def ccd(replicates=2, centers=3):
    spec = DesignSpec('diag', (FactorSpec('A', 'A', -1, 1), FactorSpec('B', 'B', -1, 1)),
                      ('Y',), seed=7, design_type='central_composite',
                      ccd_alpha=2**.5, ccd_center_points=centers,
                      ccd_axial_points=4*replicates)
    return create_ccd(spec, replicates)


def projection_sums(matrix, y, terms):
    """独立参考：逐项用投影差计算平方和与自由度。"""
    x = np.asarray(matrix, dtype=float)
    y = np.asarray(y, dtype=float)
    beta = np.linalg.lstsq(x, y, rcond=None)[0]
    sse = float(np.sum((y - x @ beta)**2))
    rows = []
    for index, term in enumerate(terms, 1):
        reduced = np.delete(x, index, axis=1)
        other = np.linalg.lstsq(reduced, y, rcond=None)[0]
        rows.append(float(np.sum((y - reduced @ other)**2) - sse))
    return rows, sse


def test_item_sums_of_squares_match_independent_projection_reference():
    frame, metadata = ccd()
    rng = np.random.default_rng(11)
    frame['响应_Y'] = (5 + 2*frame['编码_A'] - frame['编码_B'] + 3*frame['编码_A']*frame['编码_B']
                   + frame['编码_A']**2 + rng.normal(0, .3, len(frame)))
    result = analyze_rsm(frame, metadata, 'Y')
    coded = frame[['编码_A', '编码_B']].to_numpy(float)
    model = TermModel(result['design'].spec.factors)
    x = model.matrix([{'A': a, 'B': b} for a, b in coded])
    expected, sse = projection_sums(x, frame['响应_Y'].to_numpy(float), model.terms)
    assert [row['ss'] for row in result['anova']] == pytest.approx(expected, abs=1e-9)
    assert result['sse'] == pytest.approx(sse, abs=1e-9)
    assert sum(row['df'] for row in result['anova']) == result['p'] - 1


def test_pure_error_and_lack_of_fit_use_independent_group_formulas():
    frame, metadata = ccd(replicates=2)
    rng = np.random.default_rng(3)
    frame['响应_Y'] = 10 + 2*frame['编码_A'] - frame['编码_B'] + rng.normal(0, .5, len(frame))
    result = analyze_rsm(frame, metadata, 'Y')
    groups = {}
    for (a, b), value in zip(frame[['编码_A', '编码_B']].to_numpy(float),
                             frame['响应_Y'].to_numpy(float)):
        groups.setdefault((a, b), []).append(value)
    pure_sse = sum(float(np.sum((np.asarray(values) - np.mean(values))**2))
                   for values in groups.values())
    pure_df = sum(len(values) - 1 for values in groups.values())
    assert result['pure_error_sse'] == pytest.approx(pure_sse, abs=1e-9)
    assert result['pure_error_df'] == pure_df > 0
    assert result['lack_of_fit_df'] == result['df'] - pure_df
    assert result['lack_of_fit_sse'] == pytest.approx(
        result['sse'] - pure_sse, abs=1e-9)
    lof = result['lack_of_fit']
    f = (result['lack_of_fit_sse']/result['lack_of_fit_df']) / (pure_sse/pure_df)
    assert lof['f'] == pytest.approx(f, rel=1e-12)
    assert lof['p'] == pytest.approx(stats.f.sf(f, result['lack_of_fit_df'], pure_df),
                                     rel=1e-12)
    assert result['inference'] is not None
    assert result['status'] == '可推断'


def test_design_without_repeated_settings_reports_no_pure_error_or_inference():
    spec = DesignSpec('diag3', tuple(FactorSpec(chr(65+i), chr(65+i), -1, 1)
                                     for i in range(3)), ('Y',), seed=7,
                      design_type='central_composite', ccd_alpha=2**.75,
                      ccd_center_points=0, ccd_axial_points=6)
    frame, metadata = create_ccd(spec)
    frame['响应_Y'] = np.arange(len(frame), dtype=float)
    result = analyze_rsm(frame, metadata, 'Y')
    assert result['pure_error_df'] == 0
    assert result['lack_of_fit'] is None
    assert result['inference'] is None
    assert '不可用' in result['status']
    assert all(row['f'] is None and row['p'] is None for row in result['anova'])
    assert all(row['ss'] is not None for row in result['anova'])


def test_zero_pure_error_suppresses_lack_of_fit_but_keeps_item_sums():
    frame, metadata = ccd(replicates=1, centers=1)
    frame['响应_Y'] = np.arange(len(frame), dtype=float)
    result = analyze_rsm(frame, metadata, 'Y')
    assert result['pure_error_df'] == 0
    assert result['lack_of_fit'] is None
    assert result['inference'] is None
    assert result['df'] > 0
    assert all(row['ss'] is not None for row in result['anova'])
    assert all(row['f'] is None for row in result['anova'])


def test_curvature_uses_center_against_outer_points():
    frame, metadata = ccd(replicates=2)
    center = (frame['点类型'] == 'center').to_numpy()
    frame['响应_Y'] = np.where(center, 5.0, 3.0)
    result = analyze_rsm(frame, metadata, 'Y')
    curvature = result['curvature']
    expected = (frame.loc[center, '响应_Y'].mean() -
                frame.loc[~center & (frame['点类型'] == 'factorial'), '响应_Y'].mean())
    assert curvature['difference'] == pytest.approx(expected, abs=1e-12)
    assert curvature['df'] == 1
    assert curvature['p'] is None
    assert curvature['f'] is None


def test_bbd_curvature_uses_edge_points_as_reference():
    spec = DesignSpec('bbd', tuple(FactorSpec(chr(65+i), chr(65+i), -1, 1)
                                   for i in range(3)), ('Y',), seed=5,
                      design_type='box_behnken', ccd_center_points=3)
    frame, metadata = create_bbd(spec)
    center = (frame['点类型'] == 'center').to_numpy()
    frame['响应_Y'] = np.where(center, 8.0, 2.0)
    result = analyze_rsm(frame, metadata, 'Y')
    assert result['curvature']['difference'] == pytest.approx(6.0, abs=1e-12)
    assert set(frame['点类型']) == {'edge', 'center'}


def test_residuals_are_zero_for_an_exact_quadratic_model():
    frame, metadata = ccd(replicates=1)
    a, b = frame['编码_A'].to_numpy(float), frame['编码_B'].to_numpy(float)
    frame['响应_Y'] = 40 + 3*a - 2*b + 4*a*b + 5*a**2 - 1.5*b**2
    result = analyze_rsm(frame, metadata, 'Y')
    assert np.max(np.abs(result['residuals'])) < 1e-10
    assert result['pure_error_sse'] == pytest.approx(0, abs=1e-18)
    assert result['lack_of_fit'] is None
    assert result['inference'] is None
    assert result['r2'] == pytest.approx(1, abs=1e-12)


def test_custom_rsm_diagnostics_match_independent_reference_in_run_order():
    frame, metadata = custom_reference_design()
    result = analyze_custom_rsm(frame, metadata, 'Y')
    assert result['n'] == INTERVAL_REFERENCE['n']
    assert result['p'] == INTERVAL_REFERENCE['p']
    assert result['df'] == INTERVAL_REFERENCE['df']
    assert result['pure_error_df'] == 0
    assert result['inference'] is None
    assert len(result['diagnostics']) == len(INTERVAL_REFERENCE['diagnostics'])
    fields = ('leverage', 'standardized_residual', 'deleted_residual',
              'studentized_residual', 'cooks_distance', 'dfits')
    for actual, expected in zip(result['diagnostics'],
                                INTERVAL_REFERENCE['diagnostics']):
        assert actual['run_id'] == expected['run_id']
        assert actual['run_order'] == expected['run_order']
        for field in fields:
            value = expected[field]
            if value is None:
                assert actual[field] is None
            else:
                assert actual[field] == pytest.approx(value, rel=2e-12, abs=2e-12)


def test_intervals_and_influence_survive_large_response_offset():
    from doe_predict import predict_point

    frame, metadata = custom_reference_design()
    settings = {'A': 0.5, 'B': 0.25}
    baseline = predict_point(frame, metadata, 'Y', settings, confidence=.95)
    shifted_frame = frame.copy(deep=True)
    shifted_frame['Y'] += 1e8
    shifted = predict_point(shifted_frame, metadata, 'Y', settings, confidence=.95)

    assert baseline['intervals']['status'] == shifted['intervals']['status'] == '可用'
    assert shifted['prediction'] == pytest.approx(baseline['prediction'] + 1e8, abs=2e-7)
    assert shifted['intervals']['se_fit'] == pytest.approx(
        baseline['intervals']['se_fit'], rel=1e-5)
    for lower, upper in (('ci_low', 'ci_high'), ('pi_low', 'pi_high')):
        assert shifted['intervals'][upper] - shifted['intervals'][lower] == pytest.approx(
            baseline['intervals'][upper] - baseline['intervals'][lower], rel=1e-5)

    base_diagnostics = analyze_custom_rsm(frame, metadata, 'Y')['diagnostics']
    shifted_diagnostics = analyze_custom_rsm(
        shifted_frame, metadata, 'Y')['diagnostics']
    assert all(row['cooks_distance'] is not None for row in shifted_diagnostics)
    np.testing.assert_allclose(
        [row['cooks_distance'] for row in shifted_diagnostics],
        [row['cooks_distance'] for row in base_diagnostics], rtol=1e-5, atol=1e-8)


def test_rsm_influence_metrics_are_unavailable_when_saturated_or_zero_mse():
    points = INTERVAL_REFERENCE['points']
    responses = INTERVAL_REFERENCE['responses']
    saturated_indices = (0, 1, 2, 3, 4, 6)
    saturated, metadata = custom_reference_design(
        [points[i] for i in saturated_indices],
        {'Y': [responses[i] for i in saturated_indices]})
    result = analyze_custom_rsm(saturated, metadata, 'Y')
    assert result['df'] == 0
    for row in result['diagnostics']:
        assert row['leverage'] == pytest.approx(1.0, abs=1e-12)
        assert row['standardized_residual'] is None
        assert row['studentized_residual'] is None
        assert row['cooks_distance'] is None
        assert row['dfits'] is None
        assert '自由度' in row['note'] or '杠杆' in row['note']

    exact_y = [10 + 2*a - b + 3*a*a + 4*b*b + a*b for a, b in points]
    exact, metadata = custom_reference_design(points, {'Y': exact_y})
    result = analyze_custom_rsm(exact, metadata, 'Y')
    assert result['df'] > 0
    assert all(np.isfinite(row['leverage']) for row in result['diagnostics'])
    assert all(row['standardized_residual'] is None
               and row['studentized_residual'] is None
               and row['cooks_distance'] is None and row['dfits'] is None
               for row in result['diagnostics'])

