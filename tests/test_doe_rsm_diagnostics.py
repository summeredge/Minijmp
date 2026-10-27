"""RSM 统计诊断：独立投影平方和、纯误差/失拟/曲率与不可用状态。"""
import numpy as np
import pytest
from scipy import stats

from doe_bbd import create_bbd
from doe_ccd import create_ccd
from doe_core import DesignSpec, FactorSpec
from doe_rsm import analyze_rsm
from doe_rsm_model import TermModel


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

