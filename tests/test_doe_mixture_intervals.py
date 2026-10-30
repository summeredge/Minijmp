"""RSM-009 Scheffé interval checks with a separate Fraction-based oracle."""
from fractions import Fraction
from math import sqrt

import pytest

from doe_mixture import MixtureSpec, mixture_metadata
from doe_mixture_analysis import analyze_mixture
from doe_mixture_constraints import ComponentSpec, VariableSpec
from doe_mixture_designs import create_mixture_design
from doe_mixture_optimize import optimize_mixture
from doe_mixture_predict import predict_mixture


CRITICAL_DF4 = {
    0.90: 2.131846786326649,
    0.95: 2.7764451051977987,
    0.99: 4.604094871415897,
}
ERRORS = [1, 1, 1, -2, -2, -2, 3]
POINTS = [(1, 0, 0), (0, 1, 0), (0, 0, 1),
          (Fraction(1, 2), Fraction(1, 2), 0),
          (Fraction(1, 2), 0, Fraction(1, 2)),
          (0, Fraction(1, 2), Fraction(1, 2)),
          (Fraction(1, 3), Fraction(1, 3), Fraction(1, 3))]
POINT_ERRORS = dict(zip(POINTS, ERRORS))


def _inverse(matrix):
    size = len(matrix)
    rows = [list(row) + [Fraction(i == j) for j in range(size)]
            for i, row in enumerate(matrix)]
    for column in range(size):
        pivot = next(row for row in range(column, size) if rows[row][column])
        rows[column], rows[pivot] = rows[pivot], rows[column]
        divisor = rows[column][column]
        rows[column] = [value / divisor for value in rows[column]]
        for row in range(size):
            if row == column:
                continue
            multiple = rows[row][column]
            rows[row] = [value - multiple * base
                         for value, base in zip(rows[row], rows[column])]
    return [row[size:] for row in rows]


def _fraction(value):
    return Fraction(float(value)).limit_denominator(1_000_000)


def _reference(frame, response, point, confidence):
    """Exact normal-equation reference for a no-intercept linear Scheffé fit."""
    matrix = [[_fraction(row[f'设定_{name}']) for name in 'ABC']
              for _, row in frame.iterrows()]
    values = [_fraction(value) for value in frame[f'响应_{response}']]
    xtx = [[sum((row[i] * row[j] for row in matrix), Fraction(0))
            for j in range(3)] for i in range(3)]
    inverse = _inverse(xtx)
    xty = [sum((row[i] * value for row, value in zip(matrix, values)), Fraction(0))
           for i in range(3)]
    beta = [sum((inverse[i][j] * xty[j] for j in range(3)), Fraction(0))
            for i in range(3)]
    residuals = [value - sum((x * b for x, b in zip(row, beta)), Fraction(0))
                 for row, value in zip(matrix, values)]
    df = len(matrix) - 3
    mse = sum((value * value for value in residuals), Fraction(0)) / df
    x0 = [_fraction(point[name]) for name in 'ABC']
    prediction = sum((x * b for x, b in zip(x0, beta)), Fraction(0))
    h0 = sum((x0[i] * inverse[i][j] * x0[j]
              for i in range(3) for j in range(3)), Fraction(0))
    critical = CRITICAL_DF4[confidence]
    se_fit = sqrt(float(mse * h0))
    se_prediction = sqrt(float(mse * (1 + h0)))
    mean_margin = critical * se_fit
    prediction_margin = critical * se_prediction
    return {
        'prediction': float(prediction), 'df': df, 'h0': float(h0),
        'se_fit': se_fit, 'critical_value': critical,
        'ci_low': float(prediction) - mean_margin,
        'ci_high': float(prediction) + mean_margin,
        'pi_low': float(prediction) - prediction_margin,
        'pi_high': float(prediction) + prediction_margin,
    }


def interval_design(responses=('Y',)):
    spec = MixtureSpec(
        'MIX', tuple(ComponentSpec(name, name) for name in 'ABC'), responses,
        'simplex_centroid', None, seed=17)
    frame, _ = create_mixture_design(spec)
    points = [tuple(_fraction(row[f'设定_{name}']) for name in 'ABC')
              for _, row in frame.iterrows()]
    assert set(points) == set(POINTS)
    errors = [POINT_ERRORS[point] for point in points]
    for name, coefficients, multiplier in (
            ('Y', (2, 5, 3), 1),
            ('Y1', (2, 5, 3), 1),
            ('Y2', (4, 2, 6), 2)):
        if name not in responses:
            continue
        frame[f'响应_{name}'] = [
            sum(float(x) * beta for x, beta in zip(point, coefficients))
            + multiplier * error for point, error in zip(points, errors)]
    return frame, mixture_metadata(frame, spec)


@pytest.mark.parametrize('confidence', (0.90, 0.95, 0.99))
def test_mixture_prediction_ci_pi_match_fraction_reference_without_pure_error(confidence):
    frame, metadata = interval_design()
    point = {'A': 0.2, 'B': 0.3, 'C': 0.5}
    result = predict_mixture(frame, metadata, 'Y', point, degree=1,
                             confidence=confidence)
    expected = _reference(frame, 'Y', point, confidence)
    intervals = result['intervals']
    assert result['prediction'] == pytest.approx(expected['prediction'])
    assert intervals['status'] == '可用'
    assert intervals['df'] == expected['df'] == 4
    assert intervals['confidence'] == confidence
    for key in ('h0', 'se_fit', 'critical_value', 'ci_low', 'ci_high',
                'pi_low', 'pi_high'):
        assert intervals[key] == pytest.approx(expected[key], rel=1e-12, abs=1e-12)
    assert intervals['ci_high'] - intervals['ci_low'] < \
        intervals['pi_high'] - intervals['pi_low']
    analysis = analyze_mixture(frame, metadata, 'Y', degree=1)
    assert analysis['pure_error_df'] == 0 and analysis['inference'] is None


def test_prediction_intervals_are_unavailable_for_zero_mse_rank_loss_or_zero_df():
    frame, metadata = interval_design()
    frame['响应_Y'] = [2 * row['设定_A'] + 5 * row['设定_B'] + 3 * row['设定_C']
                        for _, row in frame.iterrows()]
    zero_mse = predict_mixture(frame, metadata, 'Y', [0.2, 0.3, 0.5], degree=1)
    assert zero_mse['intervals']['status'] == '不可用'
    assert '残差方差' in zero_mse['intervals']['reason']
    assert zero_mse['intervals']['ci_low'] is None
    assert zero_mse['intervals']['pi_high'] is None

    rank_spec = MixtureSpec(
        'RANK', tuple(ComponentSpec(name, name) for name in 'ABC'), ('Y',),
        'simplex_centroid', None,
        process_variables=(VariableSpec('P', 'P', 0, 1),), seed=19)
    rank_frame, _ = create_mixture_design(rank_spec)
    rank_frame['响应_Y'] = (rank_frame['设定_A'] + 2 * rank_frame['设定_B']
                             + 3 * rank_frame['设定_C'] + rank_frame['设定_P'])
    rank_meta = mixture_metadata(rank_frame, rank_spec)
    rank_terms = ['A', 'B', 'C', 'P', 'A*P', 'B*P', 'C*P']
    rank_limited = predict_mixture(
        rank_frame, rank_meta, 'Y', [0.2, 0.3, 0.5], process={'P': 0.5},
        terms=rank_terms, degree=1)
    assert rank_limited['intervals']['status'] == '不可用'
    assert '秩亏' in rank_limited['intervals']['reason']

    saturated_spec = MixtureSpec(
        'SAT', tuple(ComponentSpec(name, name) for name in 'ABC'), ('Y',),
        'simplex_lattice', 2, seed=18)
    saturated, _ = create_mixture_design(saturated_spec)
    saturated['响应_Y'] = range(len(saturated))
    saturated_meta = mixture_metadata(saturated, saturated_spec)
    no_df = predict_mixture(saturated, saturated_meta, 'Y', [0.2, 0.3, 0.5], degree=2)
    assert no_df['intervals']['status'] == '不可用'
    assert no_df['intervals']['df'] == 0
    assert '自由度' in no_df['intervals']['reason']


def test_multi_response_optimizer_returns_pointwise_intervals_for_each_response():
    frame, metadata = interval_design(('Y1', 'Y2'))
    confidence = 0.90
    result = optimize_mixture(
        frame, metadata,
        [{'response': name, 'goal': 'maximize', 'lower': -10, 'upper': 20}
         for name in ('Y1', 'Y2')],
        degree=1, confidence=confidence)
    assert result['feasible']
    assert result['interval_note'] == \
        '优化区间把最终点视为固定点；未校正优化选点后的不确定性。'
    point = result['components']
    for item in result['objectives']:
        expected = _reference(frame, item['response'], point, confidence)
        intervals = item['intervals']
        assert intervals['status'] == '可用'
        assert intervals['df'] == expected['df'] == 4
        assert intervals['confidence'] == confidence
        for key in ('h0', 'se_fit', 'ci_low', 'ci_high', 'pi_low', 'pi_high'):
            assert intervals[key] == pytest.approx(expected[key], rel=2e-7, abs=2e-7)


@pytest.mark.parametrize('confidence', (True, 0, 1, '95%'))
def test_invalid_interval_confidence_is_rejected(confidence):
    frame, metadata = interval_design()
    with pytest.raises(ValueError, match='置信水平'):
        predict_mixture(frame, metadata, 'Y', [0.2, 0.3, 0.5], degree=1,
                        confidence=confidence)
