import numpy as np
import pytest
from dataclasses import replace
from scipy import stats

from doe_analysis import analyze_factorial
from doe_core import DesignSpec, FactorSpec, worksheet_metadata
from doe_factorial import create_factorial


def example(replicates=1, center_points=0):
    spec = DesignSpec('example', (FactorSpec('A', '温度', -1, 1),
                                  FactorSpec('B', '压力', -1, 1)), ('Y',),
                      seed=10, design_type='two_level_full')
    frame, meta = create_factorial(spec, replicates=replicates, center_points=center_points)
    return frame, meta


def test_saturated_analytic_reference_and_stale_input():
    frame, meta = example()
    a, b = frame['设定_A'], frame['设定_B']
    frame['响应_Y'] = 50 + 3*a - 2*b + 4*a*b
    result = analyze_factorial(frame, meta, 'Y')
    np.testing.assert_allclose(result['coefficients'], [50, 3, -2, 4], atol=1e-12)
    np.testing.assert_allclose(result['effects'][1:], [6, -4, 8], atol=1e-12)
    assert result['df'] == 0 and result['inference'] is None
    frame.loc[0, '设定_A'] *= -1
    with pytest.raises(ValueError):
        analyze_factorial(frame, meta, 'Y')


def test_repeated_independent_reference():
    frame, meta = example(replicates=2)
    a = frame['设定_A'].to_numpy(dtype=float)
    b = frame['设定_B'].to_numpy(dtype=float)
    noise = np.where(frame['重复'].to_numpy() == 1, -1., 1.)
    frame['响应_Y'] = 50 + 3*a - 2*b + 4*a*b + noise
    result = analyze_factorial(frame, meta, 'Y')
    # Eight orthogonal rows, residuals ±1: SSE=8, df=4, SE=sqrt(2/8).
    assert result['df'] == 4
    assert result['sse'] == pytest.approx(8, abs=1e-11)
    assert result['pure_error_df'] == 4
    assert result['pure_error_sse'] == pytest.approx(8, abs=1e-11)
    assert result['lack_of_fit_df'] == 0
    assert result['lack_of_fit_sse'] == pytest.approx(0, abs=1e-11)
    inf = result['inference']
    np.testing.assert_allclose(inf['se'], .5, atol=1e-12)
    np.testing.assert_allclose(inf['t'], [100, 6, -4, 8], atol=1e-11)
    np.testing.assert_allclose(inf['p'], 2*stats.t.sf([100, 6, 4, 8], 4), atol=1e-12)
    np.testing.assert_allclose(inf['ci_low'], [50, 3, -2, 4]-stats.t.ppf(.975, 4)*.5)
    assert inf['f'] == pytest.approx((8*(3**2+2**2+4**2)/3)/2)
    assert inf['model_p'] == pytest.approx(stats.f.sf(inf['f'], 3, 4))


def test_center_does_not_become_pseudo_error_and_missing_fails():
    frame, meta = example(replicates=2, center_points=2)
    with pytest.raises(ValueError, match='缺失'):
        analyze_factorial(frame, meta, 'Y')
    frame['响应_Y'] = [100 if typ == 'center' else 1 for typ in frame['点类型']]
    result = analyze_factorial(frame, meta, 'Y')
    assert result['inference'] is None
    assert result['coefficients'][-1] == pytest.approx(99)
    assert result['curvature']['f'] is None
    assert '纯误差' in result['status']


def test_replicated_exact_fit_does_not_infer_from_roundoff():
    frame, meta = example(replicates=2)
    a, b = frame['设定_A'], frame['设定_B']
    frame['响应_Y'] = 50 + 3*a - 2*b + 4*a*b
    result = analyze_factorial(frame, meta, 'Y')
    assert result['df'] == 4 and result['inference'] is None


def test_center_with_nonzero_pure_error_enables_model_inference():
    frame, meta = example(replicates=2, center_points=2)
    frame['响应_Y'] = [10 + (1 if rep == 1 else -1)
                       for rep in frame['重复']]
    result = analyze_factorial(frame, meta, 'Y')
    assert result['pure_error_df'] > 0 and result['pure_error_sse'] > 0
    assert result['inference'] is not None
    assert result['lack_of_fit'] is None
    assert result['curvature']['f'] == pytest.approx(0)


def test_center_curvature_uses_factorial_center_mean_contrast():
    frame, meta = example(replicates=2, center_points=2)
    frame['响应_Y'] = [
        (20 if point == 'center' else 10) + (1 if rep == 1 else -1)
        for point, rep in zip(frame['点类型'], frame['重复'])
    ]
    result = analyze_factorial(frame, meta, 'Y')
    # Ten observations: each of four factorial cells and the center has ±1 error.
    assert result['pure_error_sse'] == pytest.approx(10)
    assert result['pure_error_df'] == 5
    curvature = result['curvature']
    assert curvature['difference'] == pytest.approx(10)
    assert curvature['ss'] == pytest.approx(160)
    assert curvature['f'] == pytest.approx(80)
    assert curvature['p'] == pytest.approx(stats.f.sf(80, 1, 5))


def test_three_factor_independent_projection():
    spec = DesignSpec('three', tuple(FactorSpec(x, x, -1, 1) for x in 'ABC'),
                      ('Y',), seed=7, design_type='two_level_full')
    frame, meta = create_factorial(spec)
    a, b, c = (frame[f'设定_{x}'].to_numpy(dtype=float) for x in 'ABC')
    frame['响应_Y'] = 10 + 2*a - 3*b + c + 4*a*b - 2*a*c + 5*b*c + 7*a*b*c
    result = analyze_factorial(frame, meta, 'Y', order=3)
    np.testing.assert_allclose(result['coefficients'], [10, 2, -3, 1, 4, -2, 5, 7], atol=1e-12)
    np.testing.assert_allclose(result['effects'][1:], [4, -6, 2, 8, -4, 10, 14], atol=1e-12)
    assert result['df'] == 0 and result['inference'] is None


def test_rejects_mislabeled_incomplete_design_even_with_fresh_fingerprint():
    frame, meta = example()
    frame['响应_Y'] = [1, 2, 3, 4]
    frame.loc[0, '设定_A'] = -frame.loc[0, '设定_A']
    spec = DesignSpec.from_dict(meta['design'])
    rewritten = worksheet_metadata(frame, spec, meta['column_map'])
    with pytest.raises(ValueError, match='全部两水平组合'):
        analyze_factorial(frame, rewritten, 'Y')


def test_duplicate_dataframe_index_does_not_change_response_alignment():
    frame, meta = example()
    frame.index = [9, 9, 2, 2]
    a, b = frame['设定_A'], frame['设定_B']
    frame['响应_Y'] = 50 + 3*a - 2*b + 4*a*b
    result = analyze_factorial(frame, meta, 'Y')
    np.testing.assert_allclose(result['coefficients'], [50, 3, -2, 4], atol=1e-12)


def test_large_integer_response_is_not_silently_rounded():
    frame, meta = example()
    frame['响应_Y'] = [2**60 + 1] * len(frame)
    with pytest.raises(ValueError, match='无损'):
        analyze_factorial(frame, meta, 'Y')


@pytest.mark.parametrize('k,order,interaction,sse', [(2, 1, 4, 64), (3, 2, 7, 392)])
def test_unreplicated_omitted_interaction_is_not_random_error(k, order, interaction, sse):
    spec = DesignSpec('omitted', tuple(FactorSpec(x, x, -1, 1) for x in 'ABC'[:k]),
                      ('Y',), seed=22, design_type='two_level_full')
    frame, meta = create_factorial(spec)
    factors = [frame[f'设定_{x}'].to_numpy(dtype=float) for x in 'ABC'[:k]]
    frame['响应_Y'] = 10 + sum(factors) + interaction * np.prod(factors, axis=0)
    result = analyze_factorial(frame, meta, 'Y', order=order)
    assert result['df'] == 1 and result['pure_error_df'] == 0
    assert result['sse'] == pytest.approx(sse, abs=1e-10)
    assert result['inference'] is None and '无独立纯误差' in result['status']
    np.testing.assert_allclose(result['coefficients'][:k+1], [10] + [1]*k, atol=1e-12)


def test_replicated_reduced_model_reports_pure_error_and_lack_of_fit():
    frame, meta = example(replicates=2)
    a = frame['设定_A'].to_numpy(dtype=float)
    b = frame['设定_B'].to_numpy(dtype=float)
    frame['响应_Y'] = 50 + 3*a - 2*b + 4*a*b + np.where(frame['重复'] == 1, -1, 1)
    r = analyze_factorial(frame, meta, 'Y', order=1)
    assert r['pure_error_df'] == 4 and r['pure_error_sse'] == pytest.approx(8)
    assert r['lack_of_fit_df'] == 1 and r['lack_of_fit_sse'] == pytest.approx(128)
    assert r['df'] == 5 and r['sse'] == pytest.approx(136)
    inf = r['inference']
    se = np.sqrt((136/5)/8)
    np.testing.assert_allclose(inf['se'], [se]*3)
    np.testing.assert_allclose(inf['t'], np.array([50, 3, -2])/se)
    np.testing.assert_allclose(inf['p'], 2*stats.t.sf(abs(np.array([50, 3, -2])/se), 5))
    np.testing.assert_allclose(inf['ci_high'], np.array([50, 3, -2])+stats.t.ppf(.975, 5)*se)
    assert inf['f'] == pytest.approx((8*(3**2+2**2)/2)/(136/5))
    assert inf['model_p'] == pytest.approx(stats.f.sf(inf['f'], 2, 5))


def test_six_factor_two_responses_and_missing_response():
    spec = DesignSpec('six', tuple(FactorSpec(x, x, -1, 1) for x in 'ABCDEF'),
                      ('Y', 'Z'), seed=8, design_type='two_level_full')
    frame, meta = create_factorial(spec)
    levels = [frame[f'设定_{x}'].to_numpy(dtype=float) for x in 'ABCDEF']
    frame['响应_Y'] = 10 + sum((i+1)*x for i, x in enumerate(levels))
    with pytest.raises(ValueError, match='缺失'):
        analyze_factorial(frame, meta, 'Z')
    frame['响应_Z'] = 2*frame['响应_Y']
    frame.index = [4] * len(frame)
    result = analyze_factorial(frame, meta, 'Z')
    np.testing.assert_allclose(result['coefficients'][:7], [20, 2, 4, 6, 8, 10, 12], atol=1e-12)
    assert result['pure_error_df'] == 0 and result['inference'] is None


def test_wrong_design_type_and_missing_metadata_are_rejected():
    frame, meta = example()
    frame['响应_Y'] = [1, 2, 3, 4]
    spec = replace(DesignSpec.from_dict(meta['design']), design_type='two_level_fractional')
    bad = worksheet_metadata(frame, spec, meta['column_map'])
    with pytest.raises(ValueError, match='全因子'):
        analyze_factorial(frame, bad, 'Y')
    with pytest.raises(ValueError):
        analyze_factorial(frame, None, 'Y')
