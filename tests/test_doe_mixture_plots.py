import json
from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest

from doe_mixture import MixtureSpec
from doe_mixture_constraints import ComponentSpec, LinearConstraint
from doe_mixture_model import MixtureTermModel
from doe_mixture_plots import (overlay_grid, simplex_grid, surface_data, ternary_xy,
                               trace_series)


ROOT = Path(__file__).resolve().parent / 'fixtures' / 'doe_mixture_reference'


def reference():
    return json.loads((ROOT / 'reference.json').read_text(encoding='utf-8'))


def quadratic():
    full = reference()
    data = full['quadratic_scheffe']
    spec = MixtureSpec('MIX', (ComponentSpec('A', 'A'), ComponentSpec('B', 'B'),
                               ComponentSpec('C', 'C')), ('Y',), 'simplex_lattice', 3)
    return (spec, MixtureTermModel(spec, degree=2),
            [float(Fraction(value)) for value in data['coefficients']], full)


def test_trace_rules_and_predictions():
    spec, model, coefficients, data = quadratic()
    trace = trace_series(spec, model, coefficients,
                         {key: float(Fraction(value)) for key, value
                          in zip(('A', 'B', 'C'), data['trace']['reference'])},
                         'A', steps=41)
    for point in trace['points']:
        assert abs(sum(point.values()) - 1) <= 1e-12
    by_component = {round(point['A'], 10): value
                    for point, value in zip(trace['points'], trace['values'])}
    for point, value in zip(data['trace']['points'], data['trace']['predictions']):
        assert by_component[round(float(Fraction(point[0])), 10)] == \
            pytest.approx(float(Fraction(value)), abs=1e-9)
    assert trace['skipped'] == 0


def test_contour_grid_matches_reference_and_ternary_mapping():
    spec, model, coefficients, data = quadratic()
    grid = simplex_grid(spec, model, coefficients, steps=10)
    points = data['contour_grid']['points']
    expected = [float(Fraction(value)) for value in data['contour_grid']['predictions']]
    assert len(grid['points']) == len(expected)
    expected_by_point = {tuple(round(float(Fraction(value)), 10) for value in point): prediction
                         for point, prediction in zip(points, expected)}
    for point, value in zip(grid['points'], grid['values']):
        key = tuple(round(point[item.component_id], 10) for item in spec.components)
        expected_value = expected_by_point[key]
        assert abs(sum(point.values()) - 1) <= 1e-12
        assert value == pytest.approx(expected_value, abs=1e-10)
    assert ternary_xy([1, 0, 0]) == (0, 0)
    assert ternary_xy([0, 1, 0]) == (1, 0)
    assert ternary_xy([0, 0, 1]) == pytest.approx((0.5, 0.8660254037844386))
    assert grid['feasible'].all()
    surface = surface_data(spec, model, coefficients, steps=10)
    np.testing.assert_allclose(surface['values'], grid['values'])
    assert surface['remaining'] == 1


def test_constrained_grid_masks_infeasible_points():
    spec = MixtureSpec('MIX', (ComponentSpec('A', 'A', 0.2, 1), ComponentSpec('B', 'B'),
                               ComponentSpec('C', 'C')), ('Y',), 'simplex_centroid', None,
                       linear_constraints=(LinearConstraint({'A': 1, 'B': 1}, 0.8),))
    model = MixtureTermModel(spec, degree=1)
    grid = simplex_grid(spec, model, [1, 2, 3], steps=10)
    assert not grid['feasible'].all()
    assert np.isnan(grid['values'][~grid['feasible']]).all()
    assert all(abs(sum(point.values()) - 1) <= 1e-12 for point in grid['points'])


def test_overlay_intersection_and_empty_state():
    data = reference()['overlay']
    spec = MixtureSpec('MIX', (ComponentSpec('A', 'A'), ComponentSpec('B', 'B'),
                               ComponentSpec('C', 'C')), ('Y1', 'Y2'), 'simplex_lattice', 3)
    models = [MixtureTermModel(spec, terms=['A', 'B', 'C']),
              MixtureTermModel(spec, terms=['A', 'B', 'C'])]
    coefficients = [[float(Fraction(value)) for value in item['coefficients']]
                    for item in data['responses']]
    limits = [(float(Fraction(item['low'])), float(Fraction(item['high'])))
              for item in data['responses']]
    overlay = overlay_grid(spec, models, coefficients, limits, steps=10)
    assert overlay['count'] == data['intersection_count'] == 11
    assert not overlay['empty']
    empty_limits = [(float(Fraction(item['low'])), float(Fraction(item['high'])))
                    for item in data['empty_limits']]
    empty = overlay_grid(spec, models, coefficients, empty_limits, steps=10)
    assert empty['empty'] and empty['count'] == 0


def test_high_dimensional_slice_keeps_fixed_components_and_sum():
    spec = MixtureSpec('MIX', tuple(ComponentSpec(chr(65 + i), chr(65 + i))
                                    for i in range(4)), ('Y',),
                       'simplex_centroid', None)
    model = MixtureTermModel(spec, terms=['A', 'B', 'C', 'D'])
    reference = {'A': 0.2, 'B': 0.2, 'C': 0.3, 'D': 0.3}
    grid = simplex_grid(spec, model, [1, 2, 3, 4], axes=('A', 'B'),
                        reference=reference, steps=8)
    assert grid['fixed'] == {'C': 0.3}
    for point in grid['points']:
        assert point['C'] == pytest.approx(0.3)
        assert abs(sum(point.values()) - 1) <= 1e-12


def test_two_component_grid_is_rejected_with_clear_message():
    spec = MixtureSpec('MIX', (ComponentSpec('A', 'A'), ComponentSpec('B', 'B')),
                       ('Y',), 'simplex_centroid', None)
    model = MixtureTermModel(spec, terms=['A', 'B'])
    with pytest.raises(ValueError, match='Trace'):
        simplex_grid(spec, model, [1, 2], steps=5)
