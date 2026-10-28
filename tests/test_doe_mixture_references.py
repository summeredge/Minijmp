import json
import sys
from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest

from doe_mixture import MixtureSpec
from doe_mixture_constraints import ComponentSpec, LinearConstraint
from doe_mixture_designs import design_points, region_dimension, region_vertices
from doe_mixture_model import MixtureTermModel


ROOT = Path(__file__).resolve().parent / 'fixtures' / 'doe_mixture_reference'


def reference():
    return json.loads((ROOT / 'reference.json').read_text(encoding='utf-8'))


def points(rows):
    return [tuple(float(Fraction(value)) for value in row) for row in rows]


def component_specs(bounds=None):
    if bounds is None:
        return (ComponentSpec('A', 'A'), ComponentSpec('B', 'B'), ComponentSpec('C', 'C'))
    return tuple(ComponentSpec(chr(65 + index), chr(65 + index), low, high)
                 for index, (low, high) in enumerate(bounds))


def test_independent_reference_verifies():
    sys.path.insert(0, str(ROOT))
    import verify
    assert verify.main()


def test_lattice_matches_independent_reference():
    data = reference()
    for key, degree in (('simplex_lattice_degree2', 2), ('simplex_lattice_degree3', 3)):
        spec = MixtureSpec('MIX', component_specs(), ('Y',), 'simplex_lattice', degree)
        generated = [point for point, _, _ in design_points(spec)]
        expected = points(data[key]['points'])
        assert len(generated) == data[key]['count']
        assert sorted(round(value, 12) for point in generated for value in point) == \
            sorted(round(value, 12) for point in expected for value in point)
        assert all(abs(sum(point) - 1) <= 1e-15 for point in generated)


def test_centroid_matches_independent_reference():
    data = reference()['simplex_centroid']
    spec = MixtureSpec('MIX', component_specs(), ('Y',), 'simplex_centroid', None)
    generated = [point for point, _, _ in design_points(spec)]
    expected = points(data['points'])
    assert len(generated) == data['count'] == 7
    for point in expected:
        assert any(np.allclose(point, other, rtol=0, atol=1e-12) for other in generated)
    centroid = [point for point, kind, _ in design_points(spec) if kind == 'center']
    assert centroid == [(1 / 3, 1 / 3, 1 / 3)]


def test_constrained_vertices_match_independent_reference():
    data = reference()['constrained_region']
    bounds = [(Fraction(low), Fraction(high)) for low, high in data['bounds']]
    bounds = [(float(low), float(high)) for low, high in bounds]
    constraints = tuple(LinearConstraint(
        {chr(65 + index): float(Fraction(value))
         for index, value in enumerate(item['coefficients']) if float(Fraction(value))},
        float(Fraction(item['bound']))) for item in data['constraints'])
    spec = MixtureSpec('MIX', component_specs(bounds), ('Y',), 'extreme_vertices',
                       None, linear_constraints=constraints)
    vertices = [point for point, _ in region_vertices(spec)]
    expected = points(data['vertices'])
    assert len(vertices) == len(expected) == 5
    for point in expected:
        assert any(np.allclose(point, other, rtol=0, atol=1e-9) for other in vertices)
    assert region_dimension(vertices) == data['dimension']


def test_infeasible_and_degenerate_regions_are_explicit():
    data = reference()
    with pytest.raises(ValueError, match='不可行'):
        MixtureSpec('MIX', component_specs([(0.8, 1), (0.3, 1), (0, 1)]),
                    ('Y',), 'extreme_vertices', None)
    spec = MixtureSpec('MIX', component_specs([(0.5, 0.5), (0.2, 0.2), (0, 1)]),
                       ('Y',), 'extreme_vertices', None)
    vertices = [point for point, _ in region_vertices(spec)]
    assert len(vertices) == 1
    assert region_dimension(vertices) == data['degenerate_region']['dimension']
    assert np.allclose(vertices[0], points(data['degenerate_region']['points'])[0],
                       rtol=0, atol=1e-12)


def test_scheffe_predictions_match_reference():
    data = reference()
    spec = MixtureSpec('MIX', component_specs(), ('Y',), 'simplex_lattice', 3)
    linear = MixtureTermModel(spec, degree=1)
    coefficients = [float(Fraction(value)) for value in data['linear_scheffe']['coefficients']]
    expected = [float(Fraction(value)) for value in data['linear_scheffe']['predictions']]
    values = [float(linear.row(dict(zip(('A', 'B', 'C'), point))) @ coefficients)
              for point in points(data['linear_scheffe']['points'])]
    np.testing.assert_allclose(values, expected, rtol=0, atol=1e-12)
    quadratic = MixtureTermModel(spec, degree=2)
    coefficients = [float(Fraction(value)) for value in data['quadratic_scheffe']['coefficients']]
    expected = [float(Fraction(value)) for value in data['quadratic_scheffe']['predictions']]
    values = [float(quadratic.row(dict(zip(('A', 'B', 'C'), point))) @ coefficients)
              for point in points(data['quadratic_scheffe']['points'])]
    np.testing.assert_allclose(values, expected, rtol=0, atol=1e-12)
    assert '截距' not in quadratic.names
