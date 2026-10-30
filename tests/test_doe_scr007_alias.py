"""SCR-007 alias projections checked from fixed PB/DSD matrices."""
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from doe_dsd import create_dsd
from doe_pb import create_pb
from doe_screening_analysis import analyze_dsd, analyze_pb
from test_doe_dsd import dsd_spec
from test_doe_pb import pb_spec


REFERENCE = Path(__file__).parent / 'fixtures' / 'doe_screening_reference'


def _coded(frame, family, columns, filename, cycle=None):
    reference = pd.read_csv(REFERENCE / family / filename).set_index('standard_order')
    order = frame['标准序'] if cycle is None else (frame['标准序'] - 1) % cycle + 1
    return reference.loc[order, columns].to_numpy(dtype=float)


def _cell(result, row, column):
    matrix = result['alias_matrix']
    return matrix['values'][matrix['rows'].index(row)][matrix['columns'].index(column)]


def test_pb12_projection_matrix_matches_independent_minus_one_third():
    frame, metadata = create_pb(pb_spec(12, 3), 12)
    x = _coded(frame, 'pb', ['X1', 'X2', 'X3'], 'pb12.csv')
    frame['响应_Y'] = np.arange(len(frame), dtype=float) ** 2
    result = analyze_pb(frame, metadata, 'Y')

    # The PB12 columns are orthogonal, so the F1 projection is x1'x2x3 / 12.
    exact = int(x[:, 0] @ (x[:, 1] * x[:, 2])) / len(x)
    assert exact == -1/3
    assert _cell(result, 'F1', 'F2*F3') == pytest.approx(exact, abs=1e-14)
    relation = next(row for row in result['alias_relations']
                    if row['main'] == 'F1' and row['effect'] == 'F2*F3')
    assert relation['main'] == 'F1' and relation['effect'] == 'F2*F3'
    assert relation['coefficient'] == pytest.approx(-1/3) and relation['estimable']
    assert result['alias_matrix'].keys() == {'rows', 'columns', 'values'}
    np.testing.assert_array_equal(result['fit_matrix'], np.column_stack((np.ones(12), x)))
    assert result['fit_terms'] == ['截距', 'F1', 'F2', 'F3']


def test_pb_projection_uses_actual_block_dummy_matrix():
    frame, metadata = create_pb(pb_spec(12, 3), 12, replicates=2, block_replicates=True)
    x = _coded(frame, 'pb', ['X1', 'X2', 'X3'], 'pb12.csv', cycle=12)
    block = (frame['区组'].to_numpy() == 2).astype(float)
    base = np.column_stack((np.ones(len(frame)), x, block))
    interaction = x[:, 1] * x[:, 2]
    expected = np.linalg.lstsq(base, interaction, rcond=None)[0]
    frame['响应_Y'] = np.arange(len(frame), dtype=float) ** 2
    result = analyze_pb(frame, metadata, 'Y')

    assert result['fit_terms'] == ['截距', 'F1', 'F2', 'F3', '区组2']
    np.testing.assert_allclose(result['fit_matrix'], base, atol=0, rtol=0)
    actual = np.array([_cell(result, row, 'F2*F3') for row in result['fit_terms']])
    np.testing.assert_allclose(actual, expected, atol=1e-12, rtol=0)


def test_dsd_square_interaction_projection_matches_independent_least_squares():
    frame, metadata = create_dsd(dsd_spec('dsd6', 6))
    x = _coded(frame, 'dsd', [f'X{i}' for i in range(1, 7)], 'dsd_06_cont_13.csv')
    selected = [(f'F{i}',) for i in range(1, 7)] + [('F1', 'F1')]
    base = np.column_stack((np.ones(len(x)), x, x[:, 0]**2))
    interaction = x[:, 1] * x[:, 2]
    expected = np.linalg.lstsq(base, interaction, rcond=None)[0]
    frame['响应_Y'] = np.arange(len(frame), dtype=float)
    result = analyze_dsd(frame, metadata, 'Y', selected)

    assert result['fit_terms'] == ['截距', *[f'F{i}' for i in range(1, 7)], 'F1²']
    np.testing.assert_array_equal(result['fit_matrix'], base)
    assert expected[-1] == pytest.approx(-13/15)
    assert _cell(result, 'F1²', 'F2*F3') == pytest.approx(expected[-1], abs=1e-14)


def test_rank_deficient_dsd_alias_cells_are_none_and_nullspace_is_retained():
    frame, metadata = create_dsd(dsd_spec('dsd6', 6))
    frame['响应_Y'] = np.arange(len(frame), dtype=float)
    mains = [(f'F{i}',) for i in range(1, 7)]
    squares = [(f'F{i}', f'F{i}') for i in range(1, 7)]
    selected = mains + squares + [('F1', 'F2')]
    result = analyze_dsd(frame, metadata, 'Y', selected)

    assert result['rank'] == 13 and result['p'] == 14
    assert result['nullspace'].shape == (1, 14)
    assert result['alias_matrix']['values']
    base = result['fit_matrix']
    rank = np.linalg.matrix_rank(base)
    unique = [rank == np.linalg.matrix_rank(np.delete(base, index, axis=1)) + 1
              for index in range(base.shape[1])]
    for index, row in enumerate(result['alias_matrix']['values']):
        assert all((value is not None) == unique[index] for value in row)
    assert len(result['alias_relations']) == (
        len(result['alias_matrix']['rows']) * len(result['alias_matrix']['columns']))
    for row in result['alias_relations']:
        expected = unique[result['fit_terms'].index(row['main'])]
        assert row['estimable'] == expected
        assert (row['coefficient'] is not None) == expected


def test_complete_alias_is_reported_as_a_numeric_projection():
    frame, metadata = create_pb(pb_spec(32), 32)
    frame['响应_Y'] = np.arange(len(frame), dtype=float)
    result = analyze_pb(frame, metadata, 'Y')
    assert _cell(result, 'F1', 'F2*F3') == pytest.approx(1.0)
    row = next(item for item in result['alias_relations']
               if item['main'] == 'F1' and item['effect'] == 'F2*F3')
    assert row['coefficient'] == pytest.approx(1.0)
    assert row['estimable']


def test_mixed_dsd_block_projection_matches_fixed_coding():
    frame, metadata = create_dsd(dsd_spec('dsd4c1', 5, True), replicates=4, blocks=2)
    x = _coded(frame, 'dsd', [f'X{i}' for i in range(1, 6)],
               'dsd_04_cont_01_cat_14.csv', cycle=14)
    block = (frame['区组'].to_numpy() == 2).astype(float)
    base = np.column_stack((np.ones(len(frame)), x, block))
    square = x[:, 0]**2
    expected = np.linalg.lstsq(base, square, rcond=None)[0]
    frame['响应_Y'] = np.arange(len(frame), dtype=float) + 0.2*np.sin(np.arange(len(frame)))
    result = analyze_dsd(frame, metadata, 'Y')

    assert result['fit_terms'] == ['截距', 'F1', 'F2', 'F3', 'F4', 'F5', '区组2']
    np.testing.assert_allclose(result['fit_matrix'], base, atol=0, rtol=0)
    actual = np.array([_cell(result, row, 'F1²') for row in result['fit_terms']])
    np.testing.assert_allclose(actual, expected, atol=1e-12, rtol=0)
