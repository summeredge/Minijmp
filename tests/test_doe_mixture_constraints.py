import pytest

from doe_mixture_constraints import (
    ComponentSpec, LinearConstraint, MixtureConstraintError, VariableSpec,
    actual_amounts, check_point, from_pseudocomponents, normalize_proportions,
    proportions_from_amounts, to_pseudocomponents,
)


def test_bounds_sum_and_linear_constraints():
    components = (ComponentSpec('A', 'A', 0.2, 0.6), ComponentSpec('B', 'B', 0.1, 0.5),
                  ComponentSpec('C', 'C', 0.2, 0.7))
    constraint = LinearConstraint({'A': 1, 'B': 1}, 0.75)
    assert check_point(components, (constraint,), [0.25, 0.25, 0.5]) <= 1e-12
    with pytest.raises(MixtureConstraintError, match='之和'):
        check_point(components, (), [0.25, 0.25, 0.4])
    with pytest.raises(MixtureConstraintError, match='超出'):
        check_point(components, (), [0.7, 0.1, 0.2])
    with pytest.raises(MixtureConstraintError, match='线性约束'):
        check_point(components, (constraint,), [0.4, 0.4, 0.2])


def test_infeasible_bounds_are_rejected():
    with pytest.raises(MixtureConstraintError, match='不可行'):
        from doe_mixture import MixtureSpec
        MixtureSpec('MIX', (ComponentSpec('A', 'A', 0.8, 1), ComponentSpec('B', 'B', 0.3, 1),
                            ComponentSpec('C', 'C')), ('Y',), 'simplex_centroid', None)
    with pytest.raises(MixtureConstraintError, match='不可行'):
        from doe_mixture import MixtureSpec
        MixtureSpec('MIX', (ComponentSpec('A', 'A', 0, 0.2), ComponentSpec('B', 'B', 0, 0.2),
                            ComponentSpec('C', 'C', 0, 0.2)), ('Y',), 'simplex_centroid', None)


def test_pseudocomponent_and_amount_semantics():
    components = (ComponentSpec('A', 'A', 0.1, 1), ComponentSpec('B', 'B', 0.2, 1),
                  ComponentSpec('C', 'C', 0.2, 1))
    pseudo = to_pseudocomponents(components, [0.3, 0.3, 0.4])
    assert pseudo == pytest.approx((0.2 / 0.5, 0.1 / 0.5, 0.2 / 0.5))
    assert from_pseudocomponents(components, pseudo) == pytest.approx([0.3, 0.3, 0.4])
    amounts = actual_amounts([0.2, 0.3, 0.5], 250)
    assert amounts == pytest.approx((50, 75, 125))
    proportions, total = proportions_from_amounts(amounts)
    assert total == 250 and proportions == pytest.approx((0.2, 0.3, 0.5))
    with pytest.raises(MixtureConstraintError):
        actual_amounts([0.2, 0.3, 0.4], 250)


def test_variable_range_and_encoding():
    process = VariableSpec('P1', '压力', 20, 40, 'kPa')
    assert process.to_coded(20) == -1
    assert process.to_coded(30) == 0
    with pytest.raises(MixtureConstraintError):
        process.to_coded(41)
    with pytest.raises(MixtureConstraintError):
        normalize_proportions((ComponentSpec('A', 'A'), ComponentSpec('B', 'B')),
                              [0.4, 0.4])
