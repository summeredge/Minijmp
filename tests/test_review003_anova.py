"""Independent sum-contrast least-squares references for REVIEW-003.

H0: each selected term's coefficients are zero, conditional on all other
terms (Type III); F uses the fitted model's residual variance, upper tail.
"""
import numpy as np
import pytest
from scipy.stats import f

from two_way_anova import two_way_anova


def matrix_reference(data, interaction):
    a, b = len(data), len(data[0])
    # Last level is minus the sum of all preceding levels.
    ca = np.vstack([np.eye(a - 1), -np.ones(a - 1)])
    cb = np.vstack([np.eye(b - 1), -np.ones(b - 1)])
    rows, y = [], []
    for i, row in enumerate(data):
        for j, cell in enumerate(row):
            for value in cell:
                terms = [1., *ca[i], *cb[j]]
                if interaction:
                    terms.extend(np.outer(ca[i], cb[j]).ravel())
                rows.append(terms)
                y.append(value)
    x, y = np.asarray(rows), np.asarray(y)
    beta, _, rank, _ = np.linalg.lstsq(x, y, rcond=None)
    assert rank == x.shape[1]
    sse = np.sum((y - x @ beta) ** 2)
    dfe = len(y) - rank
    expected = {'SSE': sse, 'MSE': sse / dfe}
    terms = [('A', range(1, a)), ('B', range(a, a + b - 1))]
    if interaction:
        terms.append(('AB', range(a + b - 1, x.shape[1])))
    for term, columns in terms:
        # Restricted fit sets this term to zero, retaining every other term.
        reduced = np.delete(x, list(columns), axis=1)
        fitted = reduced @ np.linalg.lstsq(reduced, y, rcond=None)[0]
        ss = np.sum((y - fitted) ** 2) - sse
        df = len(columns)
        statistic = ss / df / expected['MSE']
        expected['SS' + term] = ss
        expected['F ' + term] = statistic
        expected['p ' + term] = f.sf(statistic, df, dfe)
    return expected


@pytest.mark.parametrize('interaction', [False, True])
@pytest.mark.parametrize('data', [
    [[[1., 2., 4.], [3., 4., 8.]], [[2., 4., 5.], [5., 8., 9.]]],
    [[[0., 1., 2.], [10., 11.]], [[4., 5.], [14., 15., 16.]]],
    [[[1., 2.], [3., 4.]], [[2., 4.], [5., 8., 10.]]],
    [[[1., 2.], [3., 5.], [4., 8.]],
     [[2., 5.], [7., 9.], [6., 11.]],
     [[4., 6.], [8., 12.], [9., 13., 15.]]],
])
def test_type_iii_against_restricted_matrix_fits(data, interaction):
    expected = matrix_reference(data, interaction)
    actual = two_way_anova(data, interaction=interaction)
    for key, value in expected.items():
        assert actual[key] == pytest.approx(value, rel=1e-9, abs=1e-10), key


def test_review_counterexample_flat_input_and_report():
    reports = []
    actual = two_way_anova(
        [0., 1., 2., 10., 11., 4., 5., 14., 15., 16.],
        factor_listA=[0] * 5 + [1] * 5,
        factor_listB=[0] * 3 + [1] * 2 + [0] * 2 + [1] * 3,
        interaction=False, print_out=True, print_port=reports.append)
    for key, value in {'SSE': 5.6, 'MSE': .8, 'SSA': 38.4,
                       'F A': 48., 'p A': .0002255491334}.items():
        assert actual[key] == pytest.approx(value, rel=1e-9)
    assert any('III' in str(line) for line in reports)


def test_missing_cell_additive_model_is_identifiable():
    data = [[[1., 2., 3.], []], [[2., 4.], [5., 8.]]]
    actual = two_way_anova(data, interaction=False)
    for key, value in matrix_reference(data, False).items():
        assert actual[key] == pytest.approx(value, abs=1e-10)


@pytest.mark.parametrize('data,interaction', [
    ([[[1., 2., 3.], []], [[2., 4.], [5., 8.]]], True),
    ([[[1., 2.], []], [[], [5., 8.]]], False),
    ([[[1., 2.], []], [[], [5., 8.]]], True),
])
def test_rank_deficient_effects_are_rejected(data, interaction):
    rows = []
    for i, row in enumerate(data):
        for j, cell in enumerate(row):
            terms = [1., 1 - 2 * i, 1 - 2 * j]
            if interaction:
                terms.append(terms[1] * terms[2])
            rows.extend([terms] * len(cell))
    design = np.asarray(rows)
    assert np.linalg.matrix_rank(design) < design.shape[1]
    with pytest.raises(ValueError, match='秩亏'):
        two_way_anova(data, interaction=interaction)


@pytest.mark.parametrize('unbalanced', [False, True])
def test_grr_additive_components_use_matrix_residual(unbalanced):
    from GRR import grr_simple

    part = [p for p in 'ABC' for op in 'XY' for _ in range(3)]
    ops = [op for p in 'ABC' for op in 'XY' for _ in range(3)]
    y = np.random.default_rng(81).normal(size=len(part)).tolist()
    if unbalanced:
        y, part, ops = y[:-1], part[:-1], ops[:-1]
    data = [[[v for v, p, op in zip(y, part, ops) if p == a and op == b]
             for b in 'XY'] for a in 'ABC']
    reference = matrix_reference(data, False)
    # Existing GRR convention uses average replicates for an unbalanced design.
    replicates = len(y) / (3 * 2)
    expected = (reference['MSE'],
                max(0., (reference['SSB'] - reference['MSE']) / (3 * replicates)),
                0,
                max(0., (reference['SSA'] / 2 - reference['MSE']) / (2 * replicates)))
    assert grr_simple(y, ops, part) == pytest.approx(expected, rel=1e-9, abs=1e-10)
