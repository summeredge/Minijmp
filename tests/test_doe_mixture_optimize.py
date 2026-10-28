import json
from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest
import pandas as pd

from doe_mixture import MixtureSpec, mixture_metadata
from doe_mixture_constraints import ComponentSpec
from doe_mixture_designs import create_mixture_design
from doe_mixture_optimize import optimize_mixture


ROOT = Path(__file__).resolve().parent / 'fixtures' / 'doe_mixture_reference'


def optimization_design():
    data = json.loads((ROOT / 'reference.json').read_text(encoding='utf-8'))['optimization']
    coefficients = [float(Fraction(value)) for value in data['model']]
    spec = MixtureSpec('MIX', (ComponentSpec('A', 'A', 0.1, 0.8),
                               ComponentSpec('B', 'B', 0.1, 0.8),
                               ComponentSpec('C', 'C', 0.1, 0.8)), ('Y',),
                       'simplex_centroid', None, seed=7)
    vertices = [(0.8, 0.1, 0.1), (0.1, 0.8, 0.1), (0.1, 0.1, 0.8)]
    edges = [(0.5, 0.25, 0.25), (0.25, 0.5, 0.25), (0.25, 0.25, 0.5)]
    rows = vertices + edges + [(1 / 3, 1 / 3, 1 / 3)]
    frame = pd.DataFrame([{'运行ID': f'R{index + 1:05d}', '标准序': index + 1,
                           '运行序': index + 1, '点类型': 'center' if index == 6 else 'edge',
                           '重复': 1, '设定_A': point[0], '设定_B': point[1],
                           '设定_C': point[2], '响应_Y': None}
                          for index, point in enumerate(rows)])

    def predict(a, b, c):
        return (coefficients[0] * a + coefficients[1] * b + coefficients[2] * c
                + coefficients[3] * a * b + coefficients[4] * a * c
                + coefficients[5] * b * c)

    frame['响应_Y'] = [predict(row['设定_A'], row['设定_B'], row['设定_C'])
                       for _, row in frame.iterrows()]
    return data, frame, mixture_metadata(frame, spec)


def test_single_response_max_min_and_target_match_grid_reference():
    data, frame, meta = optimization_design()
    maximum = optimize_mixture(frame, meta, [{'response': 'Y', 'goal': 'maximize',
                                              'lower': 0, 'upper': 3}])
    expected = float(Fraction(data['max']['value']))
    assert maximum['success'] and maximum['feasible']
    assert maximum['predictions'][0] >= expected - 1e-6
    assert maximum['constraint_residual'] <= 1e-8
    assert all(0.1 - 1e-9 <= value <= 0.8 + 1e-9 for value in maximum['components'].values())

    minimum = optimize_mixture(frame, meta, [{'response': 'Y', 'goal': 'minimize',
                                              'lower': 0, 'upper': 3}])
    expected = float(Fraction(data['min']['value']))
    assert minimum['predictions'][0] <= expected + 1e-6

    target = optimize_mixture(frame, meta, [{'response': 'Y', 'goal': 'target',
                                             'lower': 0, 'upper': 3, 'target': 2}])
    expected = float(Fraction(data['target']['value']))
    assert abs(target['predictions'][0] - 2) <= abs(expected - 2) + 1e-6
    assert target['objective'] == pytest.approx(abs(target['predictions'][0] - 2))
    assert target['global_claim'] is False


def test_multi_response_desirability_and_zero_state():
    spec = MixtureSpec('MIX', (ComponentSpec('A', 'A'), ComponentSpec('B', 'B'),
                               ComponentSpec('C', 'C')), ('Y1', 'Y2'),
                       'simplex_lattice', 3, seed=2)
    frame, _ = create_mixture_design(spec)
    frame['响应_Y1'] = frame['设定_A'] + 2 * frame['设定_B'] + 4 * frame['设定_C']
    frame['响应_Y2'] = 4 * frame['设定_A'] + frame['设定_B'] + 2 * frame['设定_C']
    meta = mixture_metadata(frame, spec)
    objectives = [{'response': 'Y1', 'goal': 'target', 'lower': 2, 'upper': 4,
                   'target': 3, 'weight': 1},
                  {'response': 'Y2', 'goal': 'maximize', 'lower': 1, 'upper': 4}]
    result = optimize_mixture(frame, meta, objectives)
    assert result['feasible'] and result['aggregate_desirability'] > 0
    assert result['constraint_residual'] <= 1e-8
    assert set(result['components']) == {'A', 'B', 'C'}
    impossible = [dict(objectives[0], lower=5, upper=6, target=5.5),
                  dict(objectives[1], lower=5, upper=6)]
    empty = optimize_mixture(frame, meta, impossible)
    assert empty['aggregate_desirability'] == 0
    assert '综合期望为 0' in empty['status']


def test_objective_validation_and_missing_conditions():
    data, frame, meta = optimization_design()
    with pytest.raises(ValueError, match='响应'):
        optimize_mixture(frame, meta, [{'response': 'Z', 'goal': 'maximize',
                                        'lower': 0, 'upper': 1}])
    with pytest.raises(ValueError, match='lower < upper'):
        optimize_mixture(frame, meta, [{'response': 'Y', 'goal': 'maximize',
                                        'lower': 2, 'upper': 1}])
    with pytest.raises(ValueError, match='逼近目标'):
        optimize_mixture(frame, meta, [{'response': 'Y', 'goal': 'target',
                                        'lower': 0, 'upper': 3, 'target': 4}])
