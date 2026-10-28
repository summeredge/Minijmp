import numpy as np
import pytest

from doe_mixture import MixtureSpec, mixture_metadata, restore_mixture
from doe_mixture_constraints import ComponentSpec, LinearConstraint
from doe_mixture_designs import create_mixture_design, design_points, validate_mixture_design


def spec(degree=2, constraints=()):
    return MixtureSpec('MIX', (ComponentSpec('A', 'A'), ComponentSpec('B', 'B'),
                               ComponentSpec('C', 'C')), ('Y',), 'simplex_lattice',
                       degree, linear_constraints=constraints, seed=17)


@pytest.mark.parametrize(('degree', 'count'), [(1, 3), (2, 6), (3, 10), (4, 15)])
def test_lattice_counts_sums_and_uniqueness(degree, count):
    item = spec(degree)
    points = [point for point, _, _ in design_points(item)]
    assert len(points) == count == len(set(points))
    assert all(abs(sum(point) - 1) < 1e-15 for point in points)
    assert all(all(value >= 0 for value in point) for point in points)


def test_lattice_creation_order_seed_and_metadata():
    item = spec(2)
    frame, meta = create_mixture_design(item, 2)
    assert len(frame) == 12
    assert validate_mixture_design(item, frame)['runs'] == 12
    assert set(frame['运行序']) == set(range(1, 13))
    assert set(frame['标准序']) == set(range(1, 13))
    restored, rows = restore_mixture(frame, meta['mixture'])
    assert restored.to_dict() == item.to_dict()
    assert len(rows) == 12
    assert np.allclose(frame[['设定_A', '设定_B', '设定_C']].sum(axis=1), 1)
    changed = frame.copy()
    changed.loc[0, '设定_A'] += 0.01
    changed.loc[0, '设定_C'] -= 0.01
    with pytest.raises(ValueError, match='已变化|0 到 1|超出'):
        restore_mixture(changed, meta['mixture'])


def test_lattice_with_constraints_is_rejected_instead_of_normalized():
    item = spec(2, (LinearConstraint({'A': 1, 'B': 1}, 0.9),))
    with pytest.raises(ValueError, match='Extreme Vertices'):
        design_points(item)


def test_lattice_run_limit():
    item = MixtureSpec('MIX', tuple(ComponentSpec(chr(65 + i), chr(65 + i))
                                    for i in range(12)), ('Y',), 'simplex_lattice', 10)
    with pytest.raises(ValueError, match='运行总数'):
        create_mixture_design(item)
