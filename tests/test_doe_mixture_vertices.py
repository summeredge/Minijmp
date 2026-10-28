import numpy as np
import pytest

from doe_mixture import MixtureSpec
from doe_mixture_constraints import ComponentSpec, LinearConstraint
from doe_mixture_designs import create_mixture_design, design_points, region_dimension, region_vertices


def constrained():
    return MixtureSpec('MIX', (ComponentSpec('A', 'A', 0.2, 0.6),
                               ComponentSpec('B', 'B', 0.1, 0.5),
                               ComponentSpec('C', 'C', 0.2, 0.7)), ('Y',),
                       'extreme_vertices', None,
                       linear_constraints=(LinearConstraint({'A': 1, 'B': 1}, 0.75),
                                           LinearConstraint({'A': 1, 'B': -1}, 0.2)))


def test_vertices_source_and_design():
    spec = constrained()
    vertices = region_vertices(spec)
    assert len(vertices) == 5 and region_dimension([point for point, _ in vertices]) == 2
    assert all(source for _, source in vertices)
    points = design_points(spec)
    assert len(points) == 6
    assert sum(1 for _, kind, _ in points if kind == 'center') == 1
    frame, _ = create_mixture_design(spec)
    assert set(frame['点来源']) >= {'可行域质心'}
    assert np.allclose(frame[['设定_A', '设定_B', '设定_C']].sum(axis=1), 1)


def test_infeasible_vertices_rejected():
    spec = MixtureSpec('MIX', (ComponentSpec('A', 'A'), ComponentSpec('B', 'B'),
                               ComponentSpec('C', 'C')), ('Y',),
                       'extreme_vertices', None,
                       linear_constraints=(LinearConstraint({'A': 1, 'B': 1}, 0.4),
                                           LinearConstraint({'C': 1}, 0.2)))
    with pytest.raises(ValueError, match='不可行|没有可行点'):
        design_points(spec)


def test_degenerate_region_single_point():
    spec = MixtureSpec('MIX', (ComponentSpec('A', 'A', 0.5, 0.5),
                               ComponentSpec('B', 'B', 0.2, 0.2),
                               ComponentSpec('C', 'C')), ('Y',), 'extreme_vertices', None)
    points = design_points(spec)
    assert len(points) == 1
    assert points[0][0] == pytest.approx((0.5, 0.2, 0.3))
