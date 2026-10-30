"""Mixture Replace/Improve 与 Schema 2 谱系恢复。"""
import copy
import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from doe_core import restore_design_result, worksheet_metadata
from doe_mixture import (MixtureSpec, input_fingerprint, mixture_metadata,
                         restore_mixture, validate_mixture_metadata)
from doe_mixture_analysis import analyze_mixture
from doe_mixture_constraints import ComponentSpec, VariableSpec
from doe_mixture_improvement import improve_mixture_design


REFERENCE = json.loads((Path(__file__).parent / 'fixtures'
                        / 'doe_phase2_p4bc_reference' / 'reference.json')
                       .read_text(encoding='utf-8'))


def _source(points, run_ids, design_id, responses=None):
    spec = MixtureSpec(
        design_id, tuple(ComponentSpec(name, name) for name in ('A', 'B', 'C')),
        ('Y',), 'simplex_centroid', None)
    responses = [None] * len(points) if responses is None else responses
    rows = []
    for order, (point, run_id, response) in enumerate(
            zip(points, run_ids, responses), start=1):
        nonzero = sum(value > 1e-12 for value in point)
        point_type = ('factorial' if nonzero == 1 else
                      'center' if all(abs(value - 1 / 3) < 1e-12
                                      for value in point) else 'edge')
        rows.append({
            '运行ID': run_id, '标准序': order, '运行序': order,
            '点类型': point_type, '重复': 1,
            '设定_A': point[0], '设定_B': point[1], '设定_C': point[2],
            '响应_Y': response,
        })
    frame = pd.DataFrame(rows)
    frame['响应_Y'] = pd.Series(responses, dtype=object)
    doe = worksheet_metadata(frame, spec.doe_design_spec(), spec.column_map())
    return frame, mixture_metadata(frame, spec), doe


def _oracle_sources():
    case = REFERENCE['d_optimal_replacement']
    parent_rows = case['locked_rows'] + [case['replaceable_parent']]
    candidates = case['candidates']
    # Parse the frozen rational strings without importing any production helper.
    from fractions import Fraction
    to_point = lambda values: [float(Fraction(value)) for value in values]
    parent, parent_mixture, parent_doe = _source(
        [to_point(row['point']) for row in parent_rows],
        [row['run_id'] for row in parent_rows], 'mixture-parent',
        [row.get('measured_response') for row in parent_rows])
    candidate_frame, candidate_mixture, candidate_doe = _source(
        [to_point(row['point']) for row in candidates],
        [row['candidate_run_id'] for row in candidates], 'mixture-candidates')
    return case, parent, parent_mixture, parent_doe, candidate_frame, \
        candidate_mixture, candidate_doe


def _improve(**overrides):
    case, parent, parent_meta, parent_doe, candidates, candidate_meta, candidate_doe = \
        _oracle_sources()
    args = dict(
        parent_frame=parent, parent_mixture=parent_meta, parent_doe=parent_doe,
        candidate_frame=candidates, candidate_mixture=candidate_meta,
        candidate_doe=candidate_doe,
        locked_run_ids=('LOCK-A', 'LOCK-B'),
        replaceable_run_ids=('PARENT-003',),
        candidate_run_ids=tuple(row['candidate_run_id'] for row in case['candidates']),
        degree=1, terms=('A', 'B', 'C'), seed=case['selection_seed'],
        evaluation_budget=case['enumerated_subsets'])
    args.update(overrides)
    result = improve_mixture_design(**args)
    return case, parent, candidates, result


def test_p4bc_c05_replace_matches_independent_oracle_and_repeats_by_seed():
    case, parent, candidates, result = _improve()
    frame, doe, mixture, model, report = result
    expected = case['after']

    assert list(frame['运行ID']) == expected['run_ids']
    assert list(frame['运行ID']).count('CAND-C') == 1
    assert frame.loc[0, '响应_Y'] == 11.0
    assert frame.loc[1, '响应_Y'] == 22.0
    assert pd.isna(frame.loc[2, '响应_Y'])
    assert report['parent_rank'] == case['before']['rank'] == 3
    assert report['current_rank'] == expected['rank'] == 3
    assert report['parent_logdet'] == pytest.approx(case['before']['logdet_xtx'], abs=1e-12)
    assert report['current_logdet'] == pytest.approx(expected['logdet_xtx'], abs=1e-12)
    assert report['evaluations'] == expected['evaluations'] == 4
    assert report['global_optimum_proven'] is True
    assert report['candidate_to_replaced_parent'] == (
        ('CAND-C', 'CAND-C', 'PARENT-003'),)
    assert model['terms'] == ['A', 'B', 'C']
    assert parent.loc[2, '运行ID'] == 'PARENT-003'
    assert len(candidates) == 4

    restored_doe = restore_design_result(frame, doe)
    restored_spec, restored_rows = restore_mixture(frame, mixture, doe)
    assert restored_doe.spec.schema_version == 5
    assert restored_spec.schema_version == 1
    assert mixture['schema_version'] == 2
    assert restored_rows[-1]['run_id'] == 'CAND-C'
    assert validate_mixture_metadata(frame, mixture, doe) == mixture

    _, _, parent_meta, parent_doe, _, candidate_meta, candidate_doe = \
        _oracle_sources()
    repeated = improve_mixture_design(
        parent, parent_meta, parent_doe,
        candidates, candidate_meta, candidate_doe,
        ('LOCK-A', 'LOCK-B'), ('PARENT-003',),
        tuple(row['candidate_run_id'] for row in case['candidates']),
        degree=1, terms=('A', 'B', 'C'), seed=case['selection_seed'],
        evaluation_budget=case['enumerated_subsets'])
    assert repeated[4]['selected_candidate_run_ids'] == report['selected_candidate_run_ids']
    assert repeated[4]['current_matrix_sha256'] == report['current_matrix_sha256']


def test_schema2_new_response_is_analyzable_but_locked_response_is_immutable():
    _, _, _, (frame, doe, mixture, _, _) = _improve()
    frame.loc[2, '响应_Y'] = 33
    restored, _ = restore_mixture(frame, mixture, doe)
    assert restored.design_id == mixture['spec']['design_id']
    analysis = analyze_mixture(
        frame, mixture, 'Y', terms=('A', 'B', 'C'), degree=1,
        doe_metadata=doe)
    assert analysis['rank'] == 3
    assert analysis['n'] == 3

    frame.loc[0, '响应_Y'] = 12
    with pytest.raises(ValueError, match='Locked|历史响应'):
        restore_mixture(frame, mixture, doe)


def test_locked_integer_response_keeps_exact_value_and_type_in_snapshot():
    case, parent, _, _ = _improve()
    parent_meta, parent_doe, candidates, candidate_meta, candidate_doe = \
        _oracle_sources()[2:]
    parent['响应_Y'] = parent['响应_Y'].astype(object)
    parent.loc[0, '响应_Y'] = 9007199254740993
    output = improve_mixture_design(
        parent, parent_meta, parent_doe, candidates, candidate_meta, candidate_doe,
        ('LOCK-A', 'LOCK-B'), ('PARENT-003',),
        tuple(row['candidate_run_id'] for row in case['candidates']),
        degree=1, terms=('A', 'B', 'C'), seed=23, evaluation_budget=4)
    frame, doe, mixture, _, _ = output
    assert type(frame.loc[0, '响应_Y']) is int
    assert frame.loc[0, '响应_Y'] == 9007199254740993
    restore_mixture(frame, mixture, doe)


def test_locked_measured_setting_cannot_change_after_improve():
    case, parent, _, _ = _improve()
    _, _, parent_spec_meta, parent_doe, candidate_frame, candidate_spec_meta, \
        candidate_doe = _oracle_sources()
    parent_spec = MixtureSpec.from_dict(parent_spec_meta['spec'])
    candidate_spec = MixtureSpec.from_dict(candidate_spec_meta['spec'])
    parent['实测_A'] = pd.Series([1.0, None, None], dtype=object)
    candidate_frame['实测_A'] = pd.Series([None] * len(candidate_frame), dtype=object)
    parent_columns = copy.deepcopy(parent_doe['column_map'])
    candidate_columns = copy.deepcopy(candidate_doe['column_map'])
    parent_columns['measured_levels'] = {'A': '实测_A'}
    candidate_columns['measured_levels'] = {'A': '实测_A'}
    parent_doe = worksheet_metadata(
        parent, parent_spec.doe_design_spec(), parent_columns)
    candidate_doe = worksheet_metadata(
        candidate_frame, candidate_spec.doe_design_spec(), candidate_columns)
    parent_meta = mixture_metadata(parent, parent_spec)
    candidate_meta = mixture_metadata(candidate_frame, candidate_spec)
    improved, improved_doe, improved_meta, _, _ = improve_mixture_design(
        parent, parent_meta, parent_doe, candidate_frame, candidate_meta,
        candidate_doe, ('LOCK-A', 'LOCK-B'), ('PARENT-003',),
        tuple(row['candidate_run_id'] for row in case['candidates']),
        degree=1, terms=('A', 'B', 'C'), seed=23, evaluation_budget=4)
    assert improved.loc[0, '实测_A'] == 1.0
    improved.loc[0, '实测_A'] = 0.9
    with pytest.raises(ValueError, match='实测设定'):
        restore_mixture(improved, improved_meta, improved_doe)


def test_schema2_rejects_parent_snapshot_mapping_sha_and_evaluation_tampering():
    _, _, _, (frame, doe, mixture, _, _) = _improve()
    mutations = (
        lambda item: item['improvement_lineage']['parent_snapshot']['frame']['rows'][0][-1].update(
            value='0x1.8000000000000p+3'),
        lambda item: item['improvement_lineage']['candidate_to_replaced_parent'][0].update(
            replaced_parent_run_id={'type': 'str', 'value': 'LOCK-A'}),
        lambda item: item['improvement_lineage'].update(
            parent_matrix_sha256='0' * 64),
        lambda item: item['improvement_lineage'].update(actual_evaluations=3),
        lambda item: item['improvement_lineage'].update(current_logdet=1.0),
    )
    for mutate in mutations:
        bad = copy.deepcopy(mixture)
        mutate(bad)
        with pytest.raises(ValueError):
            restore_mixture(frame, bad, doe)

    bad = copy.deepcopy(mixture)
    bad['improvement_lineage']['extra'] = True
    with pytest.raises(ValueError, match='字段'):
        restore_mixture(frame, bad, doe)

    design_spec = restore_design_result(frame, doe).spec
    mixture_spec = MixtureSpec.from_dict(mixture['spec'])
    for column, value in (('运行ID', 'TAMPERED-ID'), ('设定_A', 0.1)):
        changed = frame.copy(deep=True)
        changed.loc[2, column] = value
        if column == '设定_A':
            changed.loc[2, '设定_C'] = 0.9
        changed_doe = worksheet_metadata(changed, design_spec, doe['column_map'])
        changed_meta = copy.deepcopy(mixture)
        changed_meta['worksheet'] = {
            'row_count': len(changed),
            'input_fingerprint': input_fingerprint(changed, mixture_spec),
        }
        with pytest.raises(ValueError):
            restore_mixture(changed, changed_meta, changed_doe)


def test_schema2_rejects_bad_ids_measured_rows_rank_and_over_budget():
    case, parent, candidates, _ = _improve()
    args = dict(
        parent_frame=parent, parent_mixture=mixture_metadata(
            parent, MixtureSpec.from_dict(_oracle_sources()[2]['spec'])),
        parent_doe=_oracle_sources()[3],
        candidate_frame=candidates, candidate_mixture=_oracle_sources()[5],
        candidate_doe=_oracle_sources()[6],
        locked_run_ids=('LOCK-A', 'LOCK-B'),
        replaceable_run_ids=('PARENT-003',),
        candidate_run_ids=tuple(row['candidate_run_id'] for row in case['candidates']),
        degree=1, terms=('A', 'B', 'C'), seed=23, evaluation_budget=4)
    with pytest.raises(ValueError, match='超过评价预算'):
        improve_mixture_design(**{**args, 'evaluation_budget': 3})
    with pytest.raises(ValueError, match='Locked|Replaceable'):
        improve_mixture_design(**{**args, 'locked_run_ids': ('LOCK-A',),
                                  'replaceable_run_ids': ('PARENT-003',)})

    completed_candidates = candidates.copy(deep=True)
    completed_candidates.loc[0, '响应_Y'] = 1.0
    with pytest.raises(ValueError, match='实验身份'):
        improve_mixture_design(**{**args, 'candidate_frame': completed_candidates,
                                  'candidate_run_ids': ('CAND-C',)})

    overlapping, overlapping_meta, overlapping_doe = _source(
        [[1, 0, 0]], ['OVERLAP'], 'overlapping-candidates')
    with pytest.raises(ValueError, match='已存在于父设计'):
        improve_mixture_design(**{**args, 'candidate_frame': overlapping,
                                  'candidate_mixture': overlapping_meta,
                                  'candidate_doe': overlapping_doe,
                                  'candidate_run_ids': ('OVERLAP',)})

    measured = parent.copy(deep=True)
    measured['响应_Y'] = pd.Series([None, 22.0, None], dtype=object)
    measured['实测_A'] = pd.Series([1.0, None, None], dtype=object)
    measured_doe = copy.deepcopy(args['parent_doe'])
    measured_map = copy.deepcopy(measured_doe['column_map'])
    measured_map['measured_levels'] = {'A': '实测_A'}
    measured_doe = worksheet_metadata(
        measured, MixtureSpec.from_dict(args['parent_mixture']['spec']).doe_design_spec(),
        measured_map)
    measured_meta = mixture_metadata(
        measured, MixtureSpec.from_dict(args['parent_mixture']['spec']))
    measured_candidates = candidates.copy(deep=True)
    measured_candidates['实测_A'] = pd.Series([None] * len(candidates), dtype=object)
    candidate_map = copy.deepcopy(args['candidate_doe']['column_map'])
    candidate_map['measured_levels'] = {'A': '实测_A'}
    measured_candidate_doe = worksheet_metadata(
        measured_candidates,
        MixtureSpec.from_dict(args['candidate_mixture']['spec']).doe_design_spec(),
        candidate_map)
    measured_candidate_meta = mixture_metadata(
        measured_candidates,
        MixtureSpec.from_dict(args['candidate_mixture']['spec']))
    with pytest.raises(ValueError, match='不可替换'):
        improve_mixture_design(**{**args, 'parent_frame': measured,
                                  'parent_mixture': measured_meta,
                                  'parent_doe': measured_doe,
                                  'candidate_frame': measured_candidates,
                                  'candidate_mixture': measured_candidate_meta,
                                  'candidate_doe': measured_candidate_doe,
                                  'replaceable_run_ids': ('LOCK-A', 'PARENT-003'),
                                  'locked_run_ids': ('LOCK-B',)})

    rank_deficient, rank_meta, rank_doe = _source(
        [[0.5, 0.5, 0], [0.25, 0.75, 0]], ['ONLY-A', 'ONLY-B'],
        'rank-deficient-candidates')
    with pytest.raises(ValueError, match='满秩|秩亏'):
        improve_mixture_design(
            parent, args['parent_mixture'], args['parent_doe'],
            rank_deficient, rank_meta, rank_doe,
            ('LOCK-A', 'LOCK-B'), ('PARENT-003',),
            ('ONLY-A', 'ONLY-B'), degree=1, terms=('A', 'B', 'C'),
            seed=23, evaluation_budget=2)


def test_candidate_run_id_collision_gets_a_distinct_current_id():
    case, parent, _, _ = _improve()
    _, _, parent_meta, parent_doe, _, _, _ = _oracle_sources()
    candidates, candidate_meta, candidate_doe = _source(
        [[0, 0, 1], [0.1, 0.2, 0.7], [0.2, 0.2, 0.6], [0.25, 0.25, 0.5]],
        ['LOCK-A', 'ALT-70', 'ALT-60', 'ALT-50'], 'collision-candidates')
    result = improve_mixture_design(
        parent, parent_meta, parent_doe,
        candidates, candidate_meta, candidate_doe,
        ('LOCK-A', 'LOCK-B'), ('PARENT-003',),
        ('LOCK-A', 'ALT-70', 'ALT-60', 'ALT-50'),
        degree=1, terms=('A', 'B', 'C'), seed=23, evaluation_budget=4)
    frame, doe, mixture, _, report = result
    assert len(frame['运行ID'].unique()) == 3
    assert 'LOCK-A' in frame['运行ID'].tolist()
    assert report['selected_run_ids'][0] != 'LOCK-A'
    restore_mixture(frame, mixture, doe)


def test_improve_rejects_nonpositive_legacy_amount_settings():
    case, parent, _, _ = _improve()
    _, _, parent_meta, _, candidate_frame, candidate_meta, _ = _oracle_sources()
    parent = parent.copy(deep=True)
    candidate_frame = candidate_frame.copy(deep=True)

    def with_amount(frame, metadata):
        spec = replace(
            MixtureSpec.from_dict(metadata['spec']),
            amount_variables=(VariableSpec('T', '总量', 0, 10, role='amount'),),
            amount_settings=(('T', 1),))
        frame['设定_T'] = 1.0
        return (spec, mixture_metadata(frame, spec),
                worksheet_metadata(frame, spec.doe_design_spec(), spec.column_map()))

    parent_spec, parent_meta, parent_doe = with_amount(parent, parent_meta)
    candidate_spec, candidate_meta, candidate_doe = with_amount(
        candidate_frame, candidate_meta)
    parent.loc[2, '设定_T'] = 0.0
    parent_meta = mixture_metadata(parent, parent_spec)
    parent_doe = worksheet_metadata(
        parent, parent_spec.doe_design_spec(), parent_spec.column_map())
    with pytest.raises(ValueError, match='必须大于 0'):
        improve_mixture_design(
            parent, parent_meta, parent_doe,
            candidate_frame, candidate_meta, candidate_doe,
            ('LOCK-A', 'LOCK-B'), ('PARENT-003',),
            tuple(row['candidate_run_id'] for row in case['candidates']),
            degree=1, terms=('A', 'B', 'C'), seed=23, evaluation_budget=4)
