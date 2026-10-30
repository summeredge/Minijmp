"""SCR-003 selection methods checked against an independent matrix reference."""
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from doe_core import DesignSpec, FactorSpec
from doe_dsd import create_dsd
from doe_stepwise import select_dsd_stepwise


REFERENCE = Path(__file__).parent / 'fixtures' / 'doe_screening_reference' / 'dsd'


def _spec(count):
    identity = {'construction_id': f'dsd{count}.v1',
                'source_kind': 'mathematical_construction',
                'source_id': f'conference.dsd{count}', 'matrix_sha256': '0' * 64}
    return DesignSpec('dsd', tuple(FactorSpec(f'F{i}', f'F{i}', 0.1, 0.3)
                                   for i in range(1, count + 1)), ('Y',), seed=7,
                      design_type='definitive_screening', screening_matrix=identity)


def _reference_coded(frame, count, filename, cycle=None):
    reference = pd.read_csv(REFERENCE / filename).set_index('standard_order')
    order = frame['标准序'] if cycle is None else (frame['标准序'] - 1) % cycle + 1
    return reference.loc[order, [f'X{i}' for i in range(1, count + 1)]].to_numpy(float)


def _orthogonal_noise(base):
    raw = np.arange(len(base), dtype=float) ** 2
    noise = raw - base @ np.linalg.lstsq(base, raw, rcond=None)[0]
    return noise / np.linalg.norm(noise)


def test_forward_keeps_forced_terms_and_waits_for_hierarchy():
    frame, metadata = create_dsd(_spec(6))
    x = _reference_coded(frame, 6, 'dsd_06_cont_13.csv')
    noise = _orthogonal_noise(np.column_stack((np.ones(len(x)), x)))
    frame['响应_Y'] = 4 + 3*x[:, 0] + 2*x[:, 1] + 5*x[:, 0]*x[:, 1] + noise
    result = select_dsd_stepwise(
        frame, metadata, 'Y', method='forward', alpha_enter=0.99,
        candidates=[('F1', 'F2'), ('F1',), ('F2',), ('F3',)], forced=[('F3',)])

    assert result['method'] == 'forward' and result['criterion'] == 'p_value'
    assert ('F3',) in result['selected_terms']
    assert all(step['action'] == 'enter' for step in result['selection_steps'])
    seen = set(result['forced_terms'])
    for step in result['selection_steps']:
        if step['term'] == ('F1', 'F2'):
            assert {('F1',), ('F2',)} <= seen
        assert any(row['p_value'] is not None for row in step['candidate_evaluations'])
        seen.add(step['term'])
    assert result['selected_terms'][-1] == ('F1', 'F2')


def test_backward_starts_full_and_never_removes_forced_terms():
    frame, metadata = create_dsd(_spec(6))
    x = _reference_coded(frame, 6, 'dsd_06_cont_13.csv')
    noise = _orthogonal_noise(np.column_stack((np.ones(len(x)), x)))
    frame['响应_Y'] = 6 + 4*x[:, 0] + noise
    candidates = [('F1',), ('F2',), ('F3',)]
    result = select_dsd_stepwise(frame, metadata, 'Y', method='backward',
                                 candidates=candidates, forced=[('F1',)])

    assert result['method'] == 'backward'
    assert result['candidate_path'][0]['current_terms'] == tuple(candidates)
    assert all(step['action'] == 'remove' for step in result['selection_steps'])
    assert all(step['term'] != ('F1',) for step in result['selection_steps'])
    assert result['selected_terms'] == (('F1',),)


def test_backward_default_candidate_model_reports_when_saturated():
    frame, metadata = create_dsd(_spec(6))
    frame['响应_Y'] = np.arange(len(frame), dtype=float) ** 2
    result = select_dsd_stepwise(frame, metadata, 'Y', method='backward')

    assert result['stop_reason'] == 'initial_model_saturated'
    assert result['selection_steps'] == []
    assert result['final_residual_df'] == 0


def test_backward_rank_deficient_initial_model_stops_only_without_estimable_removals():
    frame, metadata = create_dsd(_spec(6))
    x = _reference_coded(frame, 6, 'dsd_06_cont_13.csv')
    names = [f'F{i}' for i in range(1, 7)]
    mains = [(name,) for name in names]
    squares = [(name, name) for name in names]
    candidates = mains + squares[:5] + [('F1', 'F6')]

    def column(term):
        return np.prod(x[:, [names.index(name) for name in term]], axis=1)

    matrix = np.column_stack((np.ones(len(x)), *(column(term) for term in candidates)))
    assert np.linalg.matrix_rank(matrix) == 12 < len(x)
    frame['响应_Y'] = 3 + 2*x[:, 0] + _orthogonal_noise(matrix)

    redundant = ('F2', 'F2')
    removable = ('F1', 'F1')
    blocked = select_dsd_stepwise(
        frame, metadata, 'Y', method='backward', candidates=candidates,
        forced=[term for term in candidates if term != redundant])
    assert blocked['stop_reason'] == 'initial_model_rank_deficient'
    assert blocked['selection_steps'] == []
    assert blocked['final_residual_df'] == 1
    blocked_rows = {row['term']: row['status']
                    for row in blocked['candidate_path'][0]['candidates']}
    assert blocked_rows[redundant] == 'rank_deficient'
    assert all(status == 'forced' for term, status in blocked_rows.items()
               if term != redundant)

    reducible = select_dsd_stepwise(
        frame, metadata, 'Y', method='backward', candidates=candidates,
        forced=[term for term in candidates if term not in (redundant, removable)],
        alpha_remove=0.05)
    first_rows = {row['term']: row for row in reducible['candidate_path'][0]['candidates']}
    assert first_rows[redundant]['status'] == 'rank_deficient'
    assert first_rows[removable]['status'] == 'eligible'
    assert first_rows[removable]['p_value'] > 0.99
    assert reducible['selection_steps'][0]['term'] == removable
    assert reducible['stop_reason'] == 'rank_deficiency'
    assert reducible['stop_reason'] != 'initial_model_rank_deficient'
    assert reducible['final_residual_df'] == 2


@pytest.mark.parametrize('criterion', ['aicc', 'bic'])
def test_information_criteria_tracks_path_minimum_to_full_model_and_counts_blocks(criterion):
    frame, metadata = create_dsd(_spec(10), replicates=2, blocks=2)
    x = _reference_coded(frame, 10, 'dsd_10_cont_21.csv', cycle=21)
    block = (frame['区组'].to_numpy() == 2).astype(float)
    base = np.column_stack((np.ones(len(x)), x, block))
    noise = _orthogonal_noise(base)
    frame['响应_Y'] = 12 + 4*x[:, 0] - 3*x[:, 1] + 2*block + noise
    candidates = [(f'F{i}',) for i in range(1, 11)]
    result = select_dsd_stepwise(frame, metadata, 'Y', method='information_criteria',
                                 criterion=criterion, candidates=candidates)

    assert result['method'] == 'information_criteria'
    assert result['criterion'] == criterion
    assert result['stop_reason'] == 'full_model'
    assert len(result['selection_steps']) == 10
    assert len(result['criterion_path']) == 11
    assert result['selected_terms'] == (('F1',), ('F2',))
    assert result['best_criterion'] == min(row['value'] for row in result['criterion_path'])
    assert result['final_residual_df'] == len(frame) - 4
    assert result['criterion_path'][0]['k'] == 2  # intercept and block coefficient
    assert result['criterion_path'][-1]['k'] == 12
    assert all(step['criterion_before'] is not None and step['criterion_after'] is not None
               for step in result['selection_steps'])
    assert all(all(candidate['criterion_value'] is not None
                   for candidate in step['candidate_evaluations']
                   if candidate['status'] == 'eligible')
               for step in result['selection_steps'])

    fit = np.column_stack((np.ones(len(x)), block, x[:, 0], x[:, 1]))
    beta = np.linalg.lstsq(fit, frame['响应_Y'].to_numpy(float), rcond=None)[0]
    residual = frame['响应_Y'].to_numpy(float) - fit @ beta
    sse = residual @ residual
    rank = np.linalg.matrix_rank(fit)
    k = rank
    deviance = len(x) * (np.log(2*np.pi) + 1 + np.log(sse / len(x)))
    expected = (deviance + 2*k*len(x)/(len(x)-k-1) if criterion == 'aicc'
                else deviance + k*np.log(len(x)))
    assert result['best_criterion'] == pytest.approx(expected, rel=1e-11)
    assert 'k = rank(X)' in result['criterion_definition']


def test_bic_forward_selects_model_at_one_residual_degree_of_freedom():
    frame, metadata = create_dsd(_spec(6))
    x = _reference_coded(frame, 6, 'dsd_06_cont_13.csv')
    names = [f'F{i}' for i in range(1, 7)]
    mains = [(name,) for name in names]
    squares = [(name, name) for name in names]
    initial = mains + squares[:4]
    candidate = squares[4]
    alternative = squares[5]

    def design_matrix(terms):
        return np.column_stack((np.ones(len(x)), *[
            np.prod(x[:, [names.index(name) for name in term]], axis=1)
            for term in terms]))

    initial_matrix = design_matrix(initial)
    final_matrix = design_matrix(initial + [candidate])
    alternative_matrix = design_matrix(initial + [alternative])
    assert np.linalg.matrix_rank(initial_matrix) == 11
    assert np.linalg.matrix_rank(final_matrix) == 12
    assert np.linalg.matrix_rank(alternative_matrix) == 12
    assert len(x) - np.linalg.matrix_rank(final_matrix) == 1

    candidate_column = final_matrix[:, -1]
    frame['响应_Y'] = 7 + 2*x[:, 0] + 25*candidate_column + _orthogonal_noise(final_matrix)
    y = frame['响应_Y'].to_numpy(float)

    def bic_ols(matrix):
        beta = np.linalg.lstsq(matrix, y, rcond=None)[0]
        residual = y - matrix @ beta
        sse = float(residual @ residual)
        rank = int(np.linalg.matrix_rank(matrix))
        value = len(y) * (np.log(2*np.pi) + 1 + np.log(sse / len(y)))
        return value + rank*np.log(len(y)), sse, rank

    initial_bic, _, _ = bic_ols(initial_matrix)
    expected_bic, expected_sse, expected_rank = bic_ols(final_matrix)
    alternative_bic, _, _ = bic_ols(alternative_matrix)
    assert expected_bic < initial_bic
    assert expected_bic < alternative_bic

    result = select_dsd_stepwise(
        frame, metadata, 'Y', method='information_criteria', criterion='bic',
        candidates=initial + [candidate, alternative], initial=initial)

    assert result['stop_reason'] == 'residual_df_limit'
    assert result['selected_terms'] == tuple(initial + [candidate])
    assert result['selection_steps'][-1]['term'] == candidate
    assert result['selection_steps'][-1]['error_df'] == 1
    assert result['selection_steps'][-1]['criterion_before'] == pytest.approx(initial_bic)
    assert result['selection_steps'][-1]['criterion_after'] == pytest.approx(expected_bic)
    candidate_rows = {row['term']: row for row in result['candidate_path'][0]['candidates'][-2:]}
    assert candidate_rows[candidate]['status'] == candidate_rows[alternative]['status'] == 'eligible'
    assert candidate_rows[candidate]['criterion_value'] == pytest.approx(expected_bic)
    assert candidate_rows[alternative]['criterion_value'] == pytest.approx(alternative_bic)
    assert candidate_rows[candidate]['p_value'] < candidate_rows[alternative]['p_value']
    assert result['criterion_path'][-1]['k'] == expected_rank == 12
    assert result['criterion_path'][-1]['error_df'] == 1
    assert result['best_criterion'] == pytest.approx(expected_bic)
    assert result['analysis']['sse'] == pytest.approx(expected_sse)
    assert result['final_residual_df'] == 1


def test_information_criteria_do_not_report_undefined_values():
    frame, metadata = create_dsd(_spec(6))
    frame['响应_Y'] = np.arange(len(frame), dtype=float)
    mains = [(f'F{i}',) for i in range(1, 7)]
    squares = [(f'F{i}', f'F{i}') for i in range(1, 7)]
    forced = mains + squares[:5]
    result = select_dsd_stepwise(frame, metadata, 'Y', method='information_criteria',
                                 criterion='aicc', candidates=mains + squares,
                                 initial=forced, forced=forced)
    assert result['stop_reason'] == 'information_criterion_unavailable'
    assert result['best_criterion'] is None and result['criterion_path'] == []
    assert result['final_residual_df'] == 1

    exact = create_dsd(_spec(6))
    exact[0]['响应_Y'] = 2 + 3*exact[0]['设定_F1'].to_numpy(float)
    zero = select_dsd_stepwise(exact[0], exact[1], 'Y', method='information_criteria',
                               criterion='bic', candidates=[('F1',)])
    assert zero['stop_reason'] == 'zero_error_variance'
    assert zero['selected_terms'] == ()
    assert zero['best_criterion'] is not None
    assert zero['candidate_path'][-1]['candidates'][0]['criterion_value'] is None
