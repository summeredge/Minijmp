import json
from fractions import Fraction
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy import stats

from doe_mixture import MixtureSpec, mixture_metadata
from doe_mixture_analysis import analyze_mixture, contrast_estimable
from doe_mixture_constraints import ComponentSpec
from doe_mixture_designs import create_mixture_design


ROOT = Path(__file__).resolve().parent / 'fixtures' / 'doe_mixture_reference'


def reference():
    return json.loads((ROOT / 'reference.json').read_text(encoding='utf-8'))['anova_reference']


def anova_frame():
    data = reference()
    spec = MixtureSpec('MIX', (ComponentSpec('A', 'A'), ComponentSpec('B', 'B'),
                               ComponentSpec('C', 'C')), ('Y',), 'simplex_lattice',
                       3, seed=1)
    rows = []
    for index, (point, value) in enumerate(zip(data['rows'], data['y'])):
        values = [float(Fraction(item)) for item in point]
        rows.append({'运行ID': f'R{index + 1:05d}', '标准序': index + 1,
                     '运行序': index + 1,
                     '点类型': 'center' if values == [1 / 3, 1 / 3, 1 / 3] else 'edge',
                     '重复': 2 if index >= 9 else 1,
                     '设定_A': values[0], '设定_B': values[1], '设定_C': values[2],
                     '响应_Y': float(Fraction(value))})
    frame = pd.DataFrame(rows)
    return spec, frame, mixture_metadata(frame, spec)


def test_scheffe_anova_matches_independent_reference():
    data = reference()
    spec, frame, meta = anova_frame()
    result = analyze_mixture(frame, meta, 'Y', degree=2)
    assert (result['n'], result['p'], result['rank'], result['df']) == \
        (data['n'], data['p'], data['rank'], data['df'])
    np.testing.assert_allclose(result['coefficients'],
                               [float(Fraction(value)) for value in data['coefficients']],
                               rtol=0, atol=1e-10)
    np.testing.assert_allclose(result['fitted'],
                               [float(Fraction(value)) for value in data['fitted']],
                               rtol=0, atol=1e-10)
    assert result['sse'] == pytest.approx(float(Fraction(data['sse'])), abs=1e-10)
    assert result['sst'] == pytest.approx(float(Fraction(data['sst'])), abs=1e-10)
    assert result['ssr'] == pytest.approx(float(Fraction(data['ssr'])), abs=1e-10)
    assert (result['pure_error_df'], result['pure_error_sse']) == \
        (data['pure_error_df'], pytest.approx(float(Fraction(data['pure_error_sse']))))
    assert (result['lack_of_fit_df'], result['lack_of_fit_sse']) == \
        (data['lack_of_fit_df'], pytest.approx(float(Fraction(data['lack_of_fit_sse'])), abs=1e-10))
    for row in result['anova']:
        assert row['ss'] == pytest.approx(float(Fraction(data['term_ss'][row['source']])), abs=1e-9)
    assert result['r2'] == pytest.approx(float(Fraction(data['r2'])), abs=1e-12)
    assert result['inference'] is not None
    assert result['lack_of_fit'] is not None
    assert result['has_constant'] is True
    assert result['model_df'] == data['rank'] - 1 == 5
    assert result['inference']['model_df'] == 5
    assert result['inference']['f'] == pytest.approx(1.7324628174, rel=1e-9)
    assert result['inference']['model_p'] == pytest.approx(
        float(stats.f.sf(1.7324628174, 5, 5)), rel=1e-9)
    assert np.isnan(result['inference']['p'][0])
    assert np.isfinite(result['inference']['p'][3])
    assert all(result['estimable'])
    assert contrast_estimable(result, [1, 0, 0, 0, 0, 0])
    assert contrast_estimable(result, [1, -1, 0, 0, 0, 0])


def test_no_pure_error_disables_inference():
    spec, frame, meta = anova_frame()
    frame = frame.iloc[:9].reset_index(drop=True).copy()
    for column in ('运行ID', '标准序', '运行序'):
        frame[column] = [f'R{index + 1:05d}' if column == '运行ID' else index + 1
                         for index in range(len(frame))]
    meta = mixture_metadata(frame, spec)
    result = analyze_mixture(frame, meta, 'Y', degree=2)
    assert result['pure_error_df'] == 0
    assert result['inference'] is None
    assert '推断不可用' in result['status']


def test_saturated_model_reports_no_inference():
    spec = MixtureSpec('MIX', (ComponentSpec('A', 'A'), ComponentSpec('B', 'B'),
                               ComponentSpec('C', 'C')), ('Y',), 'simplex_lattice',
                       2, seed=1)
    frame, meta = create_mixture_design(spec)
    frame['响应_Y'] = frame['设定_A'] * 2 + frame['设定_B'] * 3
    meta = mixture_metadata(frame, spec)
    result = analyze_mixture(frame, meta, 'Y', degree=2)
    assert result['df'] == 0 and result['inference'] is None
    assert '饱和' in result['status']


def test_rank_deficient_model_reports_estimability():
    spec = MixtureSpec('MIX', (ComponentSpec('A', 'A'), ComponentSpec('B', 'B'),
                               ComponentSpec('C', 'C')), ('Y',), 'simplex_lattice',
                       1, seed=1)
    frame, meta = create_mixture_design(spec)
    frame['响应_Y'] = frame['设定_A'] + frame['设定_B']
    meta = mixture_metadata(frame, spec)
    result = analyze_mixture(frame, meta, 'Y', degree=2)
    assert result['rank'] < result['p'] and result['inference'] is None
    assert '秩亏' in result['status']
    assert result['estimable'].count(False) >= 3
    assert contrast_estimable(result, [1, 0, 0, 0, 0, 0])
    assert contrast_estimable(result, [1, -1, 0, 0, 0, 0])
    assert not contrast_estimable(result, [0, 0, 0, 1, 0, 0])


def test_no_constant_model_uses_uncentered_sums_of_squares():
    spec, frame, meta = anova_frame()
    result = analyze_mixture(frame, meta, 'Y', terms=['A', 'B'])
    assert result['has_constant'] is False
    assert result['total_df'] == result['n']
    assert result['sst'] == pytest.approx(float(np.sum(
        frame['响应_Y'].to_numpy(float) ** 2)), abs=1e-9)
    assert result['ssr'] == pytest.approx(result['sst'] - result['sse'], abs=1e-9)
    assert result['model_df'] == result['rank'] == 2
    assert result['inference']['f'] == pytest.approx(
        (result['ssr'] / 2) / (result['sse'] / result['df']), rel=1e-12)


def test_nonzero_collinear_column_is_not_estimable():
    from doe_mixture_constraints import VariableSpec
    spec = MixtureSpec('MIX', (ComponentSpec('A', 'A'), ComponentSpec('B', 'B')),
                       ('Y',), 'simplex_centroid', None,
                       process_variables=(VariableSpec('P', 'P', 0, 1),), seed=3)
    frame, meta = create_mixture_design(spec)
    frame['响应_Y'] = frame['设定_A'] + frame['设定_B'] + frame['设定_P']
    meta = mixture_metadata(frame, spec)
    result = analyze_mixture(frame, meta, 'Y',
                             terms=['A', 'B', 'P', 'A*P', 'B*P'])
    assert result['rank'] == 4 and result['p'] == 5
    assert result['estimable'][2] is False
    assert not contrast_estimable(result, [0, 0, 1, 0, 0])
