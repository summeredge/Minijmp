"""PB 分析由 NIST 参考矩阵和解析响应独立验算。"""
import numpy as np
import pytest
from scipy import stats
from dataclasses import replace

from doe_pb import create_pb
from doe_screening_analysis import analyze_pb, analyze_dsd, screening_contrast, _lenth_pse
from doe_dsd import create_dsd
from test_doe_pb import pb_spec
from test_doe_dsd import dsd_spec


def test_pb_partial_confounding_and_analytic_model():
    frame, metadata = create_pb(pb_spec(12), 12)
    a, b, c = [frame[f'设定_F{i}'].to_numpy(dtype=float) for i in (1, 2, 3)]
    frame['响应_Y'] = 10 + 2*a - 3*b + 4*c + 6*b*c
    result = analyze_pb(frame, metadata, 'Y')
    # NIST PB12 上 F1 对 F2*F3 的投影为 -1/3；其余两个投影为零。
    np.testing.assert_allclose(result['coefficients'], [10, 0, -3, 4], atol=1e-12)
    np.testing.assert_allclose(result['effects'][1:], [0, -6, 8], atol=1e-12)
    assert next(p['projection'] for p in result['projections']
                if p['main'] == 'F1' and p['interaction'] == 'F2*F3') == pytest.approx(-1/3)
    assert result['sse'] == pytest.approx(384)
    assert result['df'] == 8 and result['rank'] == 4
    assert result['inference']['mse'] == pytest.approx(48)
    assert result['inference']['p'][2] == pytest.approx(2*stats.t.sf(abs(-3/2), 8))
    np.testing.assert_allclose(result['residuals'], 6*(b*c + a/3), atol=1e-12)


def test_pb_saturation_and_rank_deficiency():
    frame, metadata = create_pb(pb_spec(12, 11), 12)
    frame['响应_Y'] = np.arange(12, dtype=float)
    result = analyze_pb(frame, metadata, 'Y')
    assert result['df'] == 0 and result['inference'] is None
    assert 'Lenth' in result['status']
    terms = [(f'F{i}',) for i in range(1, 12)] + [('F1', 'F2')]
    with pytest.raises(ValueError, match='秩亏'):
        analyze_pb(frame, metadata, 'Y', terms=terms)


def test_lenth_independent_oracle_and_saturated_pb():
    # Lenth: s0=3, 7.5 is excluded by the strict cutoff, leaving median 1.5.
    effects = [1, 1, 1, 2, 2, 2, 7.5, 7.5, 7.5, 7.5, 50]
    result = _lenth_pse(effects, 0)
    assert result['pse'] == 2.25
    assert result['df'] == pytest.approx(11/3)
    assert result['margin'] == pytest.approx(6.4774758669067)
    assert _lenth_pse([0] * 11, 0) is None
    assert _lenth_pse([0] * 6 + [1] * 5, 0) is None

    from pathlib import Path
    import pandas as pd
    reference = pd.read_csv(Path(__file__).parent / 'fixtures/doe_screening_reference/pb/pb12.csv').set_index('standard_order')
    frame, metadata = create_pb(pb_spec(12, 11), 12)
    matrix = reference.loc[frame['标准序']].to_numpy(dtype=float)
    frame['响应_Y'] = 5 + matrix @ (np.array([2] * 10 + [50]) / 2)
    fitted = analyze_pb(frame, metadata, 'Y')
    assert fitted['df'] == 0 and fitted['inference'] is None
    assert fitted['lenth']['pse'] == pytest.approx(3)
    assert fitted['lenth']['margin'] == pytest.approx(8.636634489208934)
    assert '稀疏' in fitted['status']


def test_pb32_complete_alias_is_reported_as_projection():
    frame, metadata = create_pb(pb_spec(32), 32)
    b = frame['设定_F2'].to_numpy(dtype=float)
    c = frame['设定_F3'].to_numpy(dtype=float)
    frame['响应_Y'] = 10 + 3*b*c
    result = analyze_pb(frame, metadata, 'Y')
    assert next(p['projection'] for p in result['projections']
                if p['main'] == 'F1' and p['interaction'] == 'F2*F3') == 1
    assert result['coefficients'][1] == pytest.approx(3)
    assert '完全混杂' in result['assumption']


def test_pb_centers_blocks_curvature_and_pure_error():
    frame, metadata = create_pb(pb_spec(12), 12, 2, center_points=2, block_replicates=True)
    center = (frame['点类型'] == 'center').to_numpy(dtype=float)
    block = (frame['区组'] == 2).to_numpy(dtype=float)
    coded = frame[[f'设定_F{i}' for i in (1, 2, 3)]].to_numpy(dtype=float)
    noise = np.zeros(len(frame))
    for group in (1, 2):
        indices = np.flatnonzero((frame['区组'] == group) & (frame['点类型'] == 'center'))
        noise[indices] = (1, -1)
    y = 10 + coded @ np.array([2, -3, 1]) + 4*center + 5*block + noise
    frame['响应_Y'] = y
    result = analyze_pb(frame, metadata, 'Y')
    x = np.column_stack((np.ones(len(y)), coded, center, block))
    beta = np.linalg.lstsq(x, y, rcond=None)[0]
    residual = y - x @ beta
    mse = residual @ residual / (len(y) - 6)
    se = np.sqrt(np.linalg.inv(x.T @ x)[4, 4] * mse)
    np.testing.assert_allclose(result['coefficients'], beta, atol=1e-12)
    assert result['curvature']['difference'] == pytest.approx(4)
    assert result['curvature']['f'] == pytest.approx((beta[4] / se) ** 2)
    assert result['curvature']['p'] == pytest.approx(2 * stats.t.sf(abs(beta[4] / se), len(y)-6))
    # PB12 的前三列只有八个不同设置；每区组纯误差自由度为 14 - 9。
    assert result['pure_error_df'] == 10 and result['pure_error_sse'] == pytest.approx(4)
    assert next(p['projection'] for p in result['projections']
                if p['main'] == 'F1' and p['interaction'] == 'F2*F3') == pytest.approx(-1/3)


def test_pb_text_centers_curvature_and_pure_error():
    from doe_core import FactorSpec
    factors = (FactorSpec('F1', '温度', -1, 1),
               FactorSpec('F2', '类型', None, None, factor_type='categorical', levels=('甲', '乙')),
               FactorSpec('F3', '开关', None, None, factor_type='categorical', levels=('关', '开')))
    frame, metadata = create_pb(replace(pb_spec(12), factors=factors), 12, 2, center_points=2, block_replicates=True)
    a = frame['设定_F1'].to_numpy(dtype=float)
    b = frame['设定_F2'].map({'甲': -1, '乙': 1}).to_numpy(dtype=float)
    c = frame['设定_F3'].map({'关': -1, '开': 1}).to_numpy(dtype=float)
    center = (frame['点类型'] == 'pseudo_center').to_numpy(dtype=float)
    block = (frame['区组'] == 2).to_numpy(dtype=float)
    noise = np.zeros(len(frame))
    for _, indices in frame[frame['点类型'] == 'pseudo_center'].groupby(['区组', '设定_F2', '设定_F3']).groups.items():
        noise[list(indices)] = [1, -1]
    y = 10 + 2*a - 3*b + c + 4*center + 5*block + noise
    frame['响应_Y'] = y
    result = analyze_pb(frame, metadata, 'Y')
    x = np.column_stack((np.ones(len(y)), a, b, c, center, block))
    expected = np.linalg.lstsq(x, y, rcond=None)[0]
    np.testing.assert_allclose(result['coefficients'], expected, atol=1e-11)
    assert result['curvature']['difference'] == pytest.approx(4)
    assert result['pure_error_df'] == 16 and result['pure_error_sse'] == pytest.approx(16)


def test_pb_missing_response_and_hierarchy_rejected():
    frame, metadata = create_pb(pb_spec(12), 12)
    with pytest.raises(ValueError, match='缺失'):
        analyze_pb(frame, metadata, 'Y')
    frame['响应_Y'] = np.arange(12, dtype=float)
    with pytest.raises(ValueError, match='主效应'):
        analyze_pb(frame, metadata, 'Y', terms=[('F1',), ('F1', 'F2')])


def test_dsd_quadratic_exact_saturated_model():
    frame, metadata = create_dsd(dsd_spec('dsd6', 6))
    # 独立由标准序参考读取设计，避免复用生产编码函数。
    from pathlib import Path
    import pandas as pd
    reference = pd.read_csv(Path(__file__).parent / 'fixtures/doe_screening_reference/dsd/dsd_06_cont_13.csv')
    by_order = reference.set_index('standard_order')
    x = by_order.loc[frame['标准序'], [f'X{i}' for i in range(1, 7)]].to_numpy(dtype=float)
    coefficients = np.arange(1, 7, dtype=float)
    squares = np.arange(7, 13, dtype=float)
    y = 10 + x @ coefficients + (x*x) @ squares
    frame['响应_Y'] = y
    terms = [(f'F{i}',) for i in range(1, 7)] + [(f'F{i}', f'F{i}') for i in range(1, 7)]
    result = analyze_dsd(frame, metadata, 'Y', terms)
    np.testing.assert_allclose(result['coefficients'], [10, *coefficients, *squares], atol=1e-10)
    np.testing.assert_allclose(result['fitted'], y, atol=1e-10)
    assert result['rank'] == 13 and result['df'] == 0 and result['inference'] is None
    deficient = analyze_dsd(frame, metadata, 'Y', terms + [('F1', 'F2')])
    model = np.column_stack((np.ones(len(x)), x, x*x, x[:, 0]*x[:, 1]))
    assert deficient['rank'] == 13 and deficient['p'] == 14 and deficient['df'] == 0
    np.testing.assert_allclose(model @ deficient['nullspace'].T, 0, atol=1e-12)
    np.testing.assert_allclose(deficient['coefficients'][1:7], coefficients, atol=1e-10)
    assert not deficient['estimable'][-1] and np.isnan(deficient['coefficients'][-1])
    contrast = screening_contrast(deficient, model[0])
    assert contrast['estimable'] and contrast['estimate'] == pytest.approx(y[0])
    bad = np.zeros(14); bad[-1] = 1
    assert not screening_contrast(deficient, bad)['estimable']


def test_dsd_interaction_analytic_and_missing_response():
    frame, metadata = create_dsd(dsd_spec('dsd8', 8))
    with pytest.raises(ValueError, match='缺失'):
        analyze_dsd(frame, metadata, 'Y')
    from pathlib import Path
    import pandas as pd
    reference = pd.read_csv(Path(__file__).parent / 'fixtures/doe_screening_reference/dsd/dsd_08_cont_17.csv')
    x = reference.set_index('standard_order').loc[frame['标准序'], [f'X{i}' for i in range(1, 9)]].to_numpy()
    frame['响应_Y'] = 5 + x @ np.arange(1, 9) + 3*x[:, 0]*x[:, 1]
    terms = [(f'F{i}',) for i in range(1, 9)] + [('F1', 'F2')]
    result = analyze_dsd(frame, metadata, 'Y', terms)
    np.testing.assert_allclose(result['coefficients'], [5, *range(1, 9), 3], atol=1e-10)
    assert result['sse'] == pytest.approx(0, abs=1e-20)
    assert result['df'] > 0 and result['inference'] is None and '残差方差' in result['status']


def test_dsd_square_interaction_projection():
    frame, metadata = create_dsd(dsd_spec('dsd6', 6))
    frame['响应_Y'] = np.arange(len(frame), dtype=float)
    terms = [(f'F{i}',) for i in range(1, 7)] + [('F1', 'F1'), ('F2', 'F3')]
    result = analyze_dsd(frame, metadata, 'Y', terms)
    projection = next(p for p in result['nonlinear_projections']
                      if p['square'] == 'F1²' and p['interaction'] == 'F2*F3')
    assert projection['projection'] == pytest.approx(-13/15)


def test_rank_deficient_dsd_estimable_contrast_with_error_df():
    from pathlib import Path
    import pandas as pd
    frame, metadata = create_dsd(dsd_spec('dsd6', 6), replicates=2)
    reference = pd.read_csv(Path(__file__).parent / 'fixtures/doe_screening_reference/dsd/dsd_06_cont_13.csv')
    by_order = reference.set_index('standard_order')
    base_order = (frame['标准序'] - 1) % 13 + 1
    x = by_order.loc[base_order, [f'X{i}' for i in range(1, 7)]].to_numpy(dtype=float)
    model = np.column_stack((np.ones(len(x)), x, x*x, x[:, 0]*x[:, 1]))
    y = 4 + x @ np.arange(1, 7) + np.sin(np.arange(len(x)))
    frame['响应_Y'] = y
    terms = [(f'F{i}',) for i in range(1, 7)] + [(f'F{i}', f'F{i}') for i in range(1, 7)] + [('F1', 'F2')]
    result = analyze_dsd(frame, metadata, 'Y', terms)
    beta = np.linalg.pinv(model) @ y
    residual = y - model @ beta
    mse = residual @ residual / 13
    vector = model[0]
    se = np.sqrt(mse * vector @ np.linalg.pinv(model) @ np.linalg.pinv(model).T @ vector)
    contrast = screening_contrast(result, vector)
    assert result['rank'] == 13 and result['df'] == 13
    assert contrast['estimable'] and contrast['estimate'] == pytest.approx(vector @ beta)
    assert contrast['se'] == pytest.approx(se)
    assert contrast['p'] == pytest.approx(2 * stats.t.sf(abs((vector @ beta)/se), 13))
    assert np.isnan(result['inference']['se'][-1])
    with pytest.raises(ValueError):
        screening_contrast(result, np.zeros(model.shape[1]))
    with pytest.raises(ValueError, match='有限数值范围'):
        screening_contrast(result, model[0] * 1e308)


def test_dsd_multiple_responses_and_nonsaturated_inference():
    from pathlib import Path
    import pandas as pd
    spec = replace(dsd_spec('dsd7', 7), response_names=('Y', 'Z'))
    frame, metadata = create_dsd(spec)
    reference = pd.read_csv(Path(__file__).parent / 'fixtures/doe_screening_reference/dsd/dsd_07_cont_17.csv')
    coded = reference.set_index('standard_order').loc[frame['标准序'], [f'X{i}' for i in range(1, 8)]].to_numpy()
    x = np.column_stack((np.ones(len(coded)), coded))
    noise = np.arange(len(coded), dtype=float) % 4
    y = x @ np.arange(8, dtype=float) + noise
    frame['响应_Y'], frame['响应_Z'] = y, 2*y
    expected, _, _, _ = np.linalg.lstsq(x, y, rcond=None)
    residual = y - x @ expected
    for response, multiplier in [('Y', 1), ('Z', 2)]:
        result = analyze_dsd(frame, metadata, response)
        np.testing.assert_allclose(result['coefficients'], expected * multiplier, atol=1e-10)
        np.testing.assert_allclose(result['residuals'], residual * multiplier, atol=1e-10)
        assert result['sse'] == pytest.approx(float(residual @ residual) * multiplier**2)
        assert result['df'] == len(y) - x.shape[1]
        assert result['inference']['mse'] == pytest.approx(result['sse'] / result['df'])


def test_dsd_block_adjustment_against_independent_linear_model():
    from pathlib import Path
    import pandas as pd
    frame, metadata = create_dsd(dsd_spec('dsd6', 6), replicates=4, blocks=2)
    reference = pd.read_csv(Path(__file__).parent / 'fixtures/doe_screening_reference/dsd/dsd_06_cont_13.csv').set_index('standard_order')
    order = (frame['标准序'] - 1) % 13 + 1
    coded = reference.loc[order, [f'X{i}' for i in range(1, 7)]].to_numpy()
    block = (frame['区组'] == 2).to_numpy(dtype=float)
    x = np.column_stack((np.ones(len(coded)), coded, block))
    y = x @ np.array([5, 1, -2, 3, -4, 5, -6, 7]) + np.sin(np.arange(len(x)))
    frame['响应_Y'] = y
    result = analyze_dsd(frame, metadata, 'Y')
    expected = np.linalg.lstsq(x, y, rcond=None)[0]
    residual = y - x @ expected
    np.testing.assert_allclose(result['coefficients'], expected, atol=1e-11)
    assert result['names'][-1] == '区组2' and result['effects'][-1] is None
    assert result['rank'] == 8 and result['df'] == 44
    assert result['sse'] == pytest.approx(residual @ residual)
    assert result['inference']['mse'] == pytest.approx(residual @ residual / 44)


def test_mixed_dsd_reports_intercept_interaction_projection():
    frame, metadata = create_dsd(dsd_spec('dsd4c1', 5, True))
    frame['响应_Y'] = np.arange(len(frame), dtype=float)
    result = analyze_dsd(frame, metadata, 'Y')
    intercept_interactions = [abs(row['projection']) for row in result['projections']
                              if row['main'] == '截距' and '*' in row['interaction']]
    assert max(intercept_interactions) == pytest.approx(1/7)
    assert any(row['interaction'] == 'F1²' for row in result['projections'])


def test_inconsistent_fit_cannot_be_clipped_to_zero(monkeypatch):
    from doe_screening_analysis import _fit
    # 模拟求解器给出明显错误的满秩结果；SSE 不应被裁剪成零模型平方和。
    monkeypatch.setattr('doe_screening_analysis.np.linalg.lstsq',
                        lambda *args, **kwargs: (np.array([100., 0.]), None, 2, None))
    with pytest.raises(ValueError, match='平方和计算不一致'):
        _fit(np.array([[-1.], [1.], [-1.], [1.]]), np.array([1., 2., 3., 4.]), ['F1'], [('F1',)])
