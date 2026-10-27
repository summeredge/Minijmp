from dataclasses import replace
from fractions import Fraction
import numpy as np
import pytest
from scipy import stats

from doe_ccd import create_ccd
from doe_core import DesignSpec, FactorSpec
from doe_rsm import analyze_rsm


def example(replicates=1):
    spec = DesignSpec('ccd', (FactorSpec('A', 'A', -1, 1), FactorSpec('B', 'B', -1, 1)),
                      ('Y',), seed=3, design_type='central_composite', ccd_alpha=2**.5,
                      ccd_center_points=5, ccd_axial_points=4*replicates)
    return create_ccd(spec, replicates)


def test_analytic_polynomial():
    frame, meta = example()
    a, b = frame['设定_A'].to_numpy(float), frame['设定_B'].to_numpy(float)
    frame['响应_Y'] = 40+3*a-2*b+4*a*b+5*a*a-1.5*b*b
    result = analyze_rsm(frame, meta, 'Y')
    np.testing.assert_allclose(result['coefficients'], [40, 3, -2, 5, -1.5, 4], atol=1e-12, rtol=0)
    assert result['sse'] < 1e-24
    assert result['inference'] is None


def test_decimal_levels_roundtrip_into_the_complete_quadratic_model():
    factors = (FactorSpec('A', '温度', 0.1, 0.2),
               FactorSpec('B', '压力', 65.3, 68.3))
    spec = DesignSpec('decimal-ccd', factors, ('Y',), seed=17,
                      design_type='central_composite', ccd_alpha=2**.5,
                      ccd_center_points=5, ccd_axial_points=4)
    frame, metadata = create_ccd(spec)
    coded = np.array([
        [float(2*(Fraction(row[f'设定_{factor.factor_id}']) - Fraction(factor.low)) /
                  (Fraction(factor.high) - Fraction(factor.low)) - 1)
         for factor in factors]
        for _, row in frame.iterrows()
    ])
    np.testing.assert_allclose(frame[['编码_A', '编码_B']].to_numpy(float), coded,
                               rtol=0, atol=1e-14)
    a, b = coded.T
    frame['响应_Y'] = 40 + 3*a - 2*b + 4*a*b + 5*a*a - 1.5*b*b
    result = analyze_rsm(frame, metadata, 'Y')
    np.testing.assert_allclose(result['coefficients'], [40, 3, -2, 5, -1.5, 4],
                               atol=1e-11, rtol=0)
    assert result['sse'] < 1e-24


def test_independent_noisy_reference():
    frame, meta = example(2)
    a, b = frame['设定_A'].to_numpy(float), frame['设定_B'].to_numpy(float)
    noise = np.where(frame['重复'] % 2, 1., -1.)
    y = 40+3*a-2*b+4*a*b+5*a*a-1.5*b*b+noise
    frame['响应_Y'] = y
    result = analyze_rsm(frame, meta, 'Y')
    x = np.array([[1, aa, bb, aa*aa, bb*bb, aa*bb] for aa, bb in zip(a, b)])
    beta = np.linalg.lstsq(x, y, rcond=None)[0]
    residual = y-x@beta
    sse = residual@residual
    df = len(y)-6
    se = np.sqrt(np.diag(np.linalg.inv(x.T@x))*sse/df)
    np.testing.assert_allclose(result['coefficients'], beta, atol=1e-12)
    assert result['sse'] == pytest.approx(sse)
    assert result['df'] == df
    np.testing.assert_allclose(result['inference']['se'], se)
    np.testing.assert_allclose(result['inference']['p'], 2*stats.t.sf(abs(beta/se), df))
    np.testing.assert_allclose(result['inference']['ci_low'], beta-stats.t.ppf(.975, df)*se)
    assert result['r2'] == pytest.approx(1-sse/np.sum((y-y.mean())**2))
    groups = {}
    for row, value in zip(zip(a, b), y):
        groups.setdefault(row, []).append(value)
    pe = sum(sum((np.asarray(v)-np.mean(v))**2) for v in groups.values())
    assert result['pure_error_sse'] == pytest.approx(pe)
    assert result['pure_error_df'] == sum(len(v)-1 for v in groups.values())
    assert result['lack_of_fit_df'] == df-result['pure_error_df']
    ssr = np.sum((y-y.mean())**2)-sse
    f = (ssr/5)/(sse/df)
    assert result['inference']['f'] == pytest.approx(f)
    assert result['inference']['model_p'] == pytest.approx(stats.f.sf(f, 5, df))
    assert result['adjusted_r2'] == pytest.approx(1-(sse/df)/(np.sum((y-y.mean())**2)/(len(y)-1)))
    center = y[frame['点类型'] == 'center']
    factorial = y[frame['点类型'] == 'factorial']
    diff = np.mean(center)-np.mean(factorial)
    ss = diff**2/(1/len(center)+1/len(factorial))
    assert result['curvature']['difference'] == pytest.approx(diff)
    assert result['curvature']['ss'] == pytest.approx(ss)
    assert result['curvature']['f'] == pytest.approx(ss/(pe/result['pure_error_df']))
    lof_f = ((sse-pe)/result['lack_of_fit_df'])/(pe/result['pure_error_df'])
    assert result['lack_of_fit']['f'] == pytest.approx(lof_f)
    assert result['lack_of_fit']['p'] == pytest.approx(stats.f.sf(lof_f, result['lack_of_fit_df'], result['pure_error_df']))


def test_missing_response_rejected():
    frame, meta = example()
    with pytest.raises(ValueError, match='缺失'):
        analyze_rsm(frame, meta, 'Y')


def test_unreplicated_design_has_no_pure_error_inference():
    spec = DesignSpec('ccd', (FactorSpec('A', 'A', -1, 1), FactorSpec('B', 'B', -1, 1)),
                      ('Y',), seed=3, design_type='central_composite', ccd_alpha=2**.5,
                      ccd_center_points=1, ccd_axial_points=4)
    frame, meta = create_ccd(spec)
    a, b = frame['设定_A'].to_numpy(float), frame['设定_B'].to_numpy(float)
    frame['响应_Y'] = 3 + a + b + a*a*b
    result = analyze_rsm(frame, meta, 'Y')
    assert result['df'] > 0 and result['pure_error_df'] == 0
    assert result['inference'] is None and result['lack_of_fit'] is None


@pytest.mark.parametrize('k', range(2, 6))
def test_quadratic_recovery_for_each_factor_count(k):
    factors = tuple(FactorSpec(x, x, -1, 1) for x in 'ABCDE'[:k])
    spec = DesignSpec('ccd', factors, ('Y',), seed=9, design_type='central_composite',
                      ccd_alpha=(2**k)**.25, ccd_center_points=5, ccd_axial_points=2*k)
    frame, meta = create_ccd(spec)
    values = np.array([frame[f'编码_{f.factor_id}'].to_numpy(float) for f in factors])
    expected = [8] + list(range(1, k+1)) + list(range(2, k+2))
    expected += [i+j+1 for i in range(k) for j in range(i+1, k)]
    y = np.full(len(frame), 8.)
    for i in range(k):
        y += (i+1)*values[i] + (i+2)*values[i]**2
    for i in range(k):
        for j in range(i+1, k):
            y += (i+j+1)*values[i]*values[j]
    frame['响应_Y'] = y
    result = analyze_rsm(frame, meta, 'Y')
    np.testing.assert_allclose(result['coefficients'], expected, atol=1e-12, rtol=0)


@pytest.mark.parametrize('scale, message', [(0, '秩亏'), (1e-11, '病态')])
def test_rejects_rank_deficient_and_ill_conditioned_matrices(monkeypatch, scale, message):
    import doe_rsm
    frame, meta = example()
    frame['响应_Y'] = np.arange(len(frame), dtype=float)
    original = doe_rsm.model_matrix
    def changed(coded):
        matrix = original(coded)
        matrix[:, -1] *= scale
        return matrix
    monkeypatch.setattr(doe_rsm, 'model_matrix', changed)
    with pytest.raises(ValueError, match=message):
        analyze_rsm(frame, meta, 'Y')
