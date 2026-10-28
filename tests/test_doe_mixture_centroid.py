import numpy as np

from doe_mixture import MixtureSpec, restore_mixture
from doe_mixture_constraints import ComponentSpec
from doe_mixture_designs import create_mixture_design, design_points, validate_mixture_design
from doe_mixture_model import MixtureTermModel


def test_centroid_standard_points_and_rank():
    spec = MixtureSpec('MIX', (ComponentSpec('A', 'A'), ComponentSpec('B', 'B'),
                               ComponentSpec('C', 'C')), ('Y',), 'simplex_centroid',
                       None, seed=5)
    points = [point for point, _, _ in design_points(spec)]
    assert len(points) == 7
    assert sum(1 for point in points if point.count(0) == 2) == 3
    assert sum(1 for point in points if point.count(1 / 2) == 2) == 3
    assert points.count((1 / 3, 1 / 3, 1 / 3)) == 1
    matrix = MixtureTermModel(spec, degree=2).matrix(
        [dict(zip(('A', 'B', 'C'), point)) for point in points])
    assert np.linalg.matrix_rank(matrix) == 6
    frame, meta = create_mixture_design(spec, 2)
    assert len(frame) == 14
    assert validate_mixture_design(spec, frame)['replicates'] == 2
    assert set(frame['点类型']) == {'factorial', 'edge', 'center'}
    assert np.allclose(frame[['设定_A', '设定_B', '设定_C']].sum(axis=1), 1)
    restored, rows = restore_mixture(frame, meta['mixture'])
    assert restored.design_type == 'simplex_centroid' and len(rows) == 14
