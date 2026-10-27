from dataclasses import replace

import numpy as np
import pytest
from scipy import stats

from doe_core import DesignSpec, FactorSpec, worksheet_metadata
from doe_fractional import create_fractional
from doe_fractional_analysis import analyze_fractional, fractional_alias_groups


def example(replicates=1, center_points=0):
    spec = DesignSpec(
        'half_fraction', tuple(FactorSpec(name, name, -1, 1) for name in 'ABC'),
        ('Y',), seed=17, generators=('C=AB',), design_type='two_level_fractional')
    frame, metadata = create_fractional(
        spec, replicates=replicates, center_points=center_points)
    return frame, metadata


def coded(frame):
    return [frame[f'设定_{name}'].to_numpy(dtype=float) for name in 'ABC']


def test_alias_groups_and_default_representatives_match_independent_half_fraction():
    frame, metadata = example()
    groups = fractional_alias_groups(frame, metadata)
    assert [group['terms'] for group in groups] == [
        ('截距', 'A*B*C'), ('A', 'B*C'), ('B', 'A*C'), ('C', 'A*B')]
    selectable = fractional_alias_groups(frame, metadata, order=1)
    assert [group['selectable_terms'] for group in selectable] == [('A',), ('B',), ('C',)]
    a, b, c = coded(frame)
    frame['响应_Y'] = 10 + 3*a + 2*b + 5*c

    result = analyze_fractional(frame, metadata, 'Y', order=1)
    np.testing.assert_allclose(result['coefficients'], [10, 3, 2, 5], atol=1e-12)
    assert result['effects'][0] is None
    np.testing.assert_allclose(result['effects'][1:], [6, 4, 10], atol=1e-12)
    np.testing.assert_allclose(result['fitted'], frame['响应_Y'], atol=1e-12)
    assert result['representatives'] == ('A', 'B', 'C')
    assert result['df'] == 0 and result['inference'] is None
    assert result['alias_groups'][1]['representative'] == 'A'


def test_user_selected_alias_representatives_produce_same_fitted_model():
    frame, metadata = example()
    a, b, c = coded(frame)
    frame['响应_Y'] = 10 + 3*a + 2*b + 5*c
    result = analyze_fractional(
        frame, metadata, 'Y', order=2,
        representatives=('B*C', 'A*C', 'A*B'))
    assert result['names'] == ['截距', 'B*C', 'A*C', 'A*B']
    np.testing.assert_allclose(result['coefficients'], [10, 3, 2, 5], atol=1e-12)
    np.testing.assert_allclose(result['fitted'], frame['响应_Y'], atol=1e-12)
    assert [group['representative'] for group in result['alias_groups'][1:]] == [
        'B*C', 'A*C', 'A*B']


def test_multiple_generators_preserve_complete_alias_classes():
    spec = DesignSpec(
        'quarter_fraction', tuple(FactorSpec(name, name, -1, 1) for name in 'ABCDE'),
        ('Y',), seed=19, generators=('D=AB', 'E=AC'),
        design_type='two_level_fractional')
    frame, metadata = create_fractional(spec)
    levels = [frame[f'设定_{name}'].to_numpy(dtype=float) for name in 'ABCDE']
    frame['响应_Y'] = 10 + sum((i + 1)*column for i, column in enumerate(levels))
    result = analyze_fractional(frame, metadata, 'Y', order=1)

    np.testing.assert_allclose(result['coefficients'], [10, 1, 2, 3, 4, 5], atol=1e-12)
    assert any({'D', 'A*B'} <= set(group['terms']) for group in result['alias_groups'])
    assert any({'E', 'A*C'} <= set(group['terms']) for group in result['alias_groups'])
    assert result['df'] == 2 and result['inference'] is None


def test_repeated_model_inference_uses_residual_mse_and_residual_df():
    frame, metadata = example(replicates=2)
    a, b, c = coded(frame)
    noise = np.where(frame['重复'].to_numpy() == 1, -1., 1.)
    frame['响应_Y'] = 10 + 3*a + 2*b + 5*c + noise
    result = analyze_fractional(frame, metadata, 'Y', order=1, representatives=('A',))

    assert result['pure_error_df'] == 4
    assert result['pure_error_sse'] == pytest.approx(8)
    assert result['df'] == 6
    assert result['sse'] == pytest.approx(240)
    inference = result['inference']
    assert inference['mse'] == pytest.approx(240 / 6)
    assert inference['mse'] != pytest.approx(result['pure_error_sse'] / result['pure_error_df'])
    se = np.sqrt((240 / 6) / 8)
    np.testing.assert_allclose(inference['se'], [se, se], atol=1e-12)
    np.testing.assert_allclose(inference['t'], np.array([10, 3]) / se, atol=1e-12)
    np.testing.assert_allclose(
        inference['p'], 2 * stats.t.sf(abs(np.array([10, 3]) / se), 6), atol=1e-12)
    assert inference['f'] == pytest.approx((72 / 1) / (240 / 6))
    assert inference['model_p'] == pytest.approx(stats.f.sf(inference['f'], 1, 6))
    critical = stats.t.ppf(.975, 6)
    np.testing.assert_allclose(inference['ci_low'], np.array([10, 3]) - critical * se)
    np.testing.assert_allclose(inference['ci_high'], np.array([10, 3]) + critical * se)


def test_four_factor_half_fraction_known_alias_group_coefficients():
    spec = DesignSpec('half-four', tuple(FactorSpec(x, x, -1, 1) for x in 'ABCD'),
                      ('Y',), seed=3, generators=('D=ABC',),
                      design_type='two_level_fractional')
    frame, metadata = create_fractional(spec)
    a, b, c, d = (frame[f'设定_{name}'].to_numpy(dtype=float) for name in 'ABCD')
    frame['响应_Y'] = 30 + 2*a + 3*b + 4*c + 5*d
    result = analyze_fractional(frame, metadata, 'Y', order=1)
    np.testing.assert_allclose(result['coefficients'], [30, 2, 3, 4, 5], atol=1e-12)
    np.testing.assert_allclose(result['effects'][1:], [4, 6, 8, 10], atol=1e-12)
    assert any({'A', 'B*C*D'} <= set(group['terms']) for group in result['alias_groups'])
    assert result['inference'] is None


def test_multiple_responses_with_nonunique_index_preserve_row_binding():
    spec = DesignSpec('multi', tuple(FactorSpec(x, x, -1, 1) for x in 'ABCD'),
                      ('产率', '质量'), seed=9, generators=('D=ABC',),
                      design_type='two_level_fractional')
    frame, metadata = create_fractional(spec, replicates=2)
    frame.index = [7, 2] * 8
    a = frame['设定_A'].to_numpy(dtype=float)
    frame['响应_产率'] = 10 + 2*a
    frame['响应_质量'] = 50 - 3*a
    original = frame.copy(deep=True)
    first = analyze_fractional(frame, metadata, '产率', order=1)
    second = analyze_fractional(frame, metadata, '质量', order=1)
    np.testing.assert_allclose(first['coefficients'][:2], [10, 2], atol=1e-12)
    np.testing.assert_allclose(second['coefficients'][:2], [50, -3], atol=1e-12)
    np.testing.assert_allclose(first['fitted'], frame['响应_产率'], atol=1e-12)
    np.testing.assert_allclose(second['fitted'], frame['响应_质量'], atol=1e-12)
    import pandas as pd
    pd.testing.assert_frame_equal(frame, original)


def test_unreplicated_omitted_aliases_do_not_supply_error_df():
    frame, metadata = example()
    a, b, c = coded(frame)
    frame['响应_Y'] = 10 + 3*a + 2*b + 5*c
    result = analyze_fractional(frame, metadata, 'Y', order=1, representatives=('A',))
    assert result['df'] == 2 and result['pure_error_df'] == 0
    assert result['sse'] == pytest.approx(4 * (2**2 + 5**2))
    assert result['inference'] is None


def test_rejects_duplicate_representatives_from_one_alias_group():
    frame, metadata = example()
    frame['响应_Y'] = 1.
    with pytest.raises(ValueError, match='同一别名组'):
        analyze_fractional(
            frame, metadata, 'Y', order=2, representatives=('A', 'B*C'))


def test_missing_response_and_resigned_invalid_generator_run_are_rejected():
    frame, metadata = example()
    with pytest.raises(ValueError, match='缺失'):
        analyze_fractional(frame, metadata, 'Y')
    frame['响应_Y'] = [1, 2, 3, 4]
    frame.loc[0, '设定_C'] *= -1
    spec = DesignSpec.from_dict(metadata['design'])
    resigned = worksheet_metadata(frame, spec, metadata['column_map'])
    with pytest.raises(ValueError):
        analyze_fractional(frame, resigned, 'Y')


def test_resigned_metadata_with_incomplete_alias_definition_is_rejected():
    frame, metadata = example()
    spec = replace(DesignSpec.from_dict(metadata['design']), defining_relations=())
    incomplete = worksheet_metadata(frame, spec, metadata['column_map'])
    with pytest.raises(ValueError, match='别名定义'):
        fractional_alias_groups(frame, incomplete)


def test_response_integer_precision_and_bad_representative_are_rejected():
    frame, metadata = example()
    frame['响应_Y'] = [2**60 + 1] * len(frame)
    with pytest.raises(ValueError, match='无损'):
        analyze_fractional(frame, metadata, 'Y')
    frame['响应_Y'] = [1, 2, 3, 4]
    with pytest.raises(ValueError, match='模型阶次内'):
        analyze_fractional(frame, metadata, 'Y', order=1, representatives=('A*B',))
