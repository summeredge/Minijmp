"""响应面分类因子与区组模型：解析系数、对比编码与自由度。"""
import numpy as np
import pytest
from scipy import stats

from doe_bbd import create_bbd
from doe_ccd import create_ccd
from doe_core import DesignSpec, FactorSpec, restore_design_result
from doe_rsm import analyze_rsm


def ccd_spec(levels=('low', 'high'), blocks=None):
    return DesignSpec('cat-ccd',
                      (FactorSpec('A', 'A', -1, 1), FactorSpec('B', 'B', -1, 1),
                       FactorSpec('L', 'lot', None, None, factor_type='categorical',
                                  levels=levels)),
                      ('Y',), seed=3, design_type='central_composite',
                      ccd_alpha=None,
                      ccd_center_points=None if blocks else 5,
                      ccd_axial_points=4,
                      block_count=blocks)


def test_categorical_ccd_uses_reference_coding_not_numeric_levels():
    frame, metadata = create_ccd(ccd_spec())
    a = frame['编码_A'].to_numpy(float)
    b = frame['编码_B'].to_numpy(float)
    high = (frame['设定_L'] == 'high').to_numpy(float)
    frame['响应_Y'] = 10 + 2*a + 3*b + 5*high + 4*a*high
    result = analyze_rsm(frame, metadata, 'Y')
    coefficients = dict(zip(result['names'], result['coefficients']))
    assert coefficients['L[high]'] == pytest.approx(5, abs=1e-9)
    assert coefficients['A*L[high]'] == pytest.approx(4, abs=1e-9)
    assert result['sse'] < 1e-20
    # 参考水平 low 不产生独立列；分类因子只有 k-1 个哑变量列。
    assert 'L[low]' not in coefficients
    assert sum(name.startswith('L') for name in result['names']) == 1


def test_categorical_ccd_run_count_includes_center_points_per_level():
    frame, metadata = create_ccd(ccd_spec(levels=('a', 'b', 'c')))
    exact = restore_design_result(frame, metadata)
    centers = [run for run in exact.runs if run.point_type == 'center']
    assert len(centers) == 15  # 每个分类水平各 5 个中心点
    assert len(frame) == 3 * (4 + 4) + 15


def test_categorical_effect_is_not_smuggled_as_a_continuous_slope():
    frame, metadata = create_ccd(ccd_spec())
    a = frame['编码_A'].to_numpy(float)
    b = frame['编码_B'].to_numpy(float)
    frame['响应_Y'] = 10 + 2*a + 3*b
    result = analyze_rsm(frame, metadata, 'Y')
    coefficients = dict(zip(result['names'], result['coefficients']))
    # 无分类差异时哑变量系数必须为 0，不应拟合出虚构斜率。
    assert coefficients['L[high]'] == pytest.approx(0, abs=1e-9)


def test_invalid_category_level_is_rejected():
    frame, metadata = create_ccd(ccd_spec())
    frame['响应_Y'] = np.arange(len(frame), dtype=float)
    frame.loc[0, '设定_L'] = 'third'
    with pytest.raises(ValueError):
        analyze_rsm(frame, metadata, 'Y')


def test_bbd_categorical_levels_each_get_their_own_center_points():
    spec = DesignSpec('cat-bbd',
                      (FactorSpec('A', 'A', -1, 1), FactorSpec('B', 'B', -1, 1),
                       FactorSpec('C', 'C', -1, 1),
                       FactorSpec('L', 'lot', None, None,
                                  factor_type='categorical', levels=('x', 'y'))),
                      ('Y',), seed=4, design_type='box_behnken')
    frame, metadata = create_bbd(spec)
    result = restore_design_result(frame, metadata)
    assert len(frame) == 30
    centers = [run for run in result.runs if run.point_type == 'center']
    assert len(centers) == 6
    assert sum(run.settings['L'] == 'x' for run in centers) == 3


def test_block_term_is_reported_separately_from_factor_terms():
    frame, metadata = create_ccd(ccd_spec(blocks=2))
    coded = frame[['编码_A', '编码_B']].to_numpy(float)
    block = (frame['区组'] == 2).to_numpy(float)
    frame['响应_Y'] = 10 + 2*coded[:, 0] + 3*coded[:, 1] + 7*block
    result = analyze_rsm(frame, metadata, 'Y')
    coefficients = dict(zip(result['names'], result['coefficients']))
    assert coefficients['区组2'] == pytest.approx(7, abs=1e-9)
    assert result['blocks'] == [1, 2]
    assert all(row['source'] != '区组1' for row in result['anova'])


def test_bbd_pure_error_does_not_mix_categorical_levels():
    spec = DesignSpec('cat-bbd-error',
                      tuple(FactorSpec(c, c, -1, 1) for c in 'ABC') +
                      (FactorSpec('L', 'lot', None, None, factor_type='categorical',
                                  levels=('low', 'high')),),
                      ('Y',), seed=4, design_type='box_behnken')
    frame, metadata = create_bbd(spec)
    frame['响应_Y'] = 10 + 100*(frame['设定_L'] == 'high').astype(float)
    result = analyze_rsm(frame, metadata, 'Y')
    assert result['sse'] == pytest.approx(0, abs=1e-20)
    assert result['pure_error_sse'] == pytest.approx(0, abs=1e-20)
    assert result['pure_error_df'] == 4
    assert result['lack_of_fit_sse'] == pytest.approx(0, abs=1e-20)
    assert result['lack_of_fit'] is None
    assert result['curvature']['f'] is None and result['curvature']['p'] is None
    assert result['inference'] is None
    assert all(row['f'] is None and row['p'] is None for row in result['anova'])


def test_categorical_blocked_replicates_match_independent_projection():
    frame, metadata = create_ccd(ccd_spec(blocks=2))
    a, b = (frame['编码_' + c].to_numpy(float) for c in 'AB')
    high = (frame['设定_L'] == 'high').to_numpy(float)
    block = (frame['区组'] == 2).to_numpy(float)
    noise = frame.groupby(['编码_A', '编码_B', '设定_L', '区组']).cumcount().to_numpy(float)
    y = 10 + 2*a - b + 7*high + 4*block + noise
    frame['响应_Y'] = y
    result = analyze_rsm(frame, metadata, 'Y')
    # Independently construct the complete two-factor quadratic and category interactions.
    x = np.column_stack((np.ones(len(y)), a, b, a*a, b*b, a*b,
                         high, a*high, b*high, block))
    residual = y - x @ np.linalg.lstsq(x, y, rcond=None)[0]
    sse = float(residual @ residual)
    groups = {}
    for key, value in zip(zip(a, b, high, block), y):
        groups.setdefault(key, []).append(value)
    pure_sse = sum(sum((v - np.mean(values))**2 for v in values)
                   for values in groups.values())
    pure_df = sum(len(values)-1 for values in groups.values())
    assert pure_sse > 0 and pure_df > 0
    assert result['sse'] == pytest.approx(sse, abs=1e-9)
    assert result['pure_error_sse'] == pytest.approx(pure_sse, abs=1e-9)
    assert result['pure_error_df'] == pure_df
    assert result['lack_of_fit_sse'] == pytest.approx(sse-pure_sse, abs=1e-9)
    assert result['lack_of_fit_df'] == len(y)-np.linalg.matrix_rank(x)-pure_df
    expected_f = ((sse-pure_sse)/result['lack_of_fit_df']) / (pure_sse/pure_df)
    assert result['lack_of_fit']['f'] == pytest.approx(expected_f, abs=1e-9)
    assert result['lack_of_fit']['p'] == pytest.approx(
        stats.f.sf(expected_f, result['lack_of_fit_df'], pure_df), abs=1e-9)
    assert result['inference'] is not None
    assert result['curvature']['f'] is None and result['curvature']['p'] is None
