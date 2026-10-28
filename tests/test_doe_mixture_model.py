import numpy as np
import pytest

from doe_mixture import MixtureSpec
from doe_mixture_constraints import ComponentSpec, VariableSpec
from doe_mixture_model import MixtureTermModel


def base_spec(**kwargs):
    return MixtureSpec('MIX', (ComponentSpec('A', 'A'), ComponentSpec('B', 'B'),
                               ComponentSpec('C', 'C')), ('Y',), 'simplex_centroid',
                       None, **kwargs)


def test_scheffe_terms_have_no_intercept():
    model = MixtureTermModel(base_spec(), degree=2)
    assert model.names == ['A', 'B', 'C', 'A*B', 'A*C', 'B*C']
    assert model.row({'A': 1, 'B': 0, 'C': 0}).tolist() == [1, 0, 0, 0, 0, 0]
    assert MixtureTermModel(base_spec(), degree=1).names == ['A', 'B', 'C']
    cubic = MixtureTermModel(base_spec(), degree=3)
    assert 'A*B*C' in cubic.names
    lattice = MixtureSpec('MIX', (ComponentSpec('A', 'A'), ComponentSpec('B', 'B'),
                                  ComponentSpec('C', 'C')), ('Y',), 'simplex_lattice', 3)
    from doe_mixture_designs import design_points
    points = [dict(zip(('A', 'B', 'C'), point))
              for point, _, _ in design_points(lattice)]
    assert np.linalg.matrix_rank(MixtureTermModel(lattice, degree=3).matrix(points)) == 7


def test_process_and_amount_terms_use_coded_variables():
    spec = base_spec(process_variables=(VariableSpec('P', '压力', 20, 40, 'kPa'),),
                     amount_variables=(VariableSpec('T', '总量', 100, 300, 'g', 'amount'),),
                     amount_settings=(('T', 200),))
    model = MixtureTermModel(spec, terms=['A', 'B', 'C', 'P', 'T', 'A*P', 'A*T'])
    row = model.row({'A': 0.5, 'B': 0.3, 'C': 0.2, 'P': 40, 'T': 300})
    assert row.tolist() == pytest.approx([0.5, 0.3, 0.2, 1, 1, 0.5, 0.5])
    assert not np.any(model.row({'A': 0.5, 'B': 0.3, 'C': 0.2, 'P': 20, 'T': 100})[:4] == 0)


@pytest.mark.parametrize('terms', [
    ['A', 'A'], ['A', 'Z'], ['A*A'], ['A*B*C*D'], ['A*P*Q'], ['A*T*T'],
    ['A*B*P'], ['A', 'B', 'C', 'P', 'Q'],
])
def test_invalid_terms_are_rejected(terms):
    spec = base_spec(process_variables=(VariableSpec('P', 'P', 0, 1),),
                     amount_variables=(VariableSpec('T', 'T', 0, 1, role='amount'),),
                     amount_settings=(('T', 0.5),))
    with pytest.raises(ValueError):
        MixtureTermModel(spec, terms=terms)
