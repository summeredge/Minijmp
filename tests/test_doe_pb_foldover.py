"""PB Foldover：独立参考、原始运行保留、谱系验证与损坏拒绝。"""
import importlib.util
import json
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from doe_core import (DesignSpec, FactorSpec, _fingerprint,
                      foldover_matrix_fingerprint, restore_design_result,
                      screening_matrix_sha256)
from doe_modify import reorder
from doe_pb import create_pb, validate_pb
from doe_pb_foldover import create_pb_foldover, pb_foldover_summary
from doe_screening_analysis import analyze_pb


ROOT = Path(__file__).parent / 'fixtures' / 'doe_phase2_p4a_reference'
REFERENCE = json.loads((ROOT / 'pb_foldover_reference.json').read_text(encoding='utf-8'))
CASES = {case['run_count']: case for case in REFERENCE['cases']}


def pb_spec(run_count, factors=None):
    count = factors if factors is not None else run_count - 1
    mathematical = run_count in (32, 40, 44, 48)
    identity = {'construction_id': f'pb{run_count}.v1',
                'source_kind': 'mathematical_construction' if mathematical else 'publication',
                'source_id': f'{"hadamard" if mathematical else "nist"}.pb{run_count}',
                'matrix_sha256': '0' * 64}
    return DesignSpec('pb', tuple(FactorSpec(f'F{i}', f'F{i}', -1, 1)
                                  for i in range(1, count + 1)), ('Y',), seed=7,
                      design_type='plackett_burman', screening_matrix=identity)


def response(frame, names=('F1', 'F2', 'F3')):
    a, b, c = (frame[f'设定_{name}'].to_numpy(dtype=float) for name in names)
    frame['响应_Y'] = pd.array(10 + 2 * a - 3 * b + 4 * c, dtype='Float64')
    return frame


def coded_rows(frame, metadata, columns):
    return frame[columns].to_numpy(dtype=float)


def test_reference_verifier_rebuilds_without_production_imports():
    spec = importlib.util.spec_from_file_location(
        'p4a_pb_verifier', ROOT / 'verify_pb_foldover_reference.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module.verify()
    assert set(result) == {12, 20, 24, 28, 32, 36, 40, 44, 48}
    assert result[12]['complete_confounding'] == [55, 0, 0]
    assert result[32]['complete_confounding'] == [465, 0, 420]


@pytest.mark.parametrize('run_count', [12, 20, 24, 28, 32, 36, 40, 44, 48])
@pytest.mark.parametrize('folded_factors', [None, 'F1'])
def test_foldover_points_ranks_and_batches_match_reference(run_count, folded_factors):
    case = CASES[run_count]
    frame, metadata = create_pb(pb_spec(run_count), run_count)
    response(frame)
    source = frame.copy(deep=True)
    folded, folded_metadata, summary = create_pb_foldover(
        frame, metadata, folded_factors)
    pd.testing.assert_frame_equal(frame, source)

    names = [f'F{i}' for i in range(1, run_count)]
    case_key = 'all' if folded_factors is None else 'one'
    order = source['标准序'].to_numpy()
    by_standard = sorted(range(len(source)), key=lambda i: order[i])
    base = [[int(source[f'设定_{name}'].iloc[i]) for name in names] for i in by_standard]
    assert base == case['base_points']
    added = folded[folded_metadata['column_map']['batch_id']] == 'FOLD1'
    added_rows = folded[added].sort_values('标准序')
    assert [[int(v) for v in added_rows[f'设定_{name}']] for name in names] == [
        list(column) for column in zip(*case[f'new_points_{case_key}'])]
    assert summary['base_runs'] == run_count
    assert summary['added_runs'] == run_count
    assert summary['total_runs'] == 2 * run_count
    assert summary['before']['joint_rank'] == case['before']['joint_rank']
    assert summary['after']['joint_rank'] == case[f'after_{case_key}']['joint_rank']
    assert len(summary['after']['complete']) == \
        case[f'after_{case_key}']['complete_confounding_count']
    # 原始 PB 构造身份保持不变；折叠后不得伪装成新的官方固定构造。
    identity = folded_metadata['design']['screening_matrix']
    assert identity['construction_id'] == f'pb{run_count}.v1'
    assert identity['source_kind'] == case['source_kind']
    assert identity['matrix_sha256'] == metadata['design']['screening_matrix']['matrix_sha256']
    assert screening_matrix_sha256(restore_design_result(folded, folded_metadata),
                                   base_only=True) == identity['matrix_sha256']
    assert screening_matrix_sha256(restore_design_result(folded, folded_metadata)) \
        != identity['matrix_sha256']
    restored = restore_design_result(folded, folded_metadata)
    validate_pb(restored)
    columns = folded_metadata['column_map']
    base_rows = folded[folded[columns['batch_id']] == 'BASE'].sort_values(
        columns['standard_order'])
    added_rows = folded[folded[columns['batch_id']] == 'FOLD1'].sort_values(
        columns['standard_order'])
    assert tuple(tuple(pair) for pair in
                 folded_metadata['design']['foldover_lineage']['run_map']) == tuple(
                     zip(base_rows[columns['run_id']], added_rows[columns['run_id']]))
    for source_row, added_row in zip(base_rows.to_dict('records'),
                                     added_rows.to_dict('records')):
        assert added_row[columns['source_run_id']] == source_row[columns['run_id']]
        assert added_row[columns['run_order']] > source['运行序'].max()
        for key in ('run_id', 'standard_order', 'run_order', 'replicate', 'point_type'):
            assert source_row[columns[key]] == source[source[columns['run_id']]
                                                       == source_row[columns['run_id']]][
                                                           columns[key]].iloc[0]
        for column in (*columns['factors'].values(), *columns['responses'].values()):
            assert source_row[column] == source[source[columns['run_id']]
                                                 == source_row[columns['run_id']]][column].iloc[0]
    lineage = restored.spec.foldover_lineage
    assert foldover_matrix_fingerprint(restored.runs, restored.spec.factors) \
        == lineage['current_matrix_sha256']


def test_source_response_settings_and_order_survive_foldover():
    frame, metadata = create_pb(pb_spec(12), 12)
    response(frame)
    source = frame.copy(deep=True)
    folded, folded_metadata, summary = create_pb_foldover(frame, metadata)
    columns = folded_metadata['column_map']
    base = folded[folded[columns['batch_id']] == 'BASE'].set_index(columns['run_id'])
    original = source.set_index(metadata['column_map']['run_id'])
    assert list(base.index) == list(original.index)
    assert list(base[columns['run_order']]) == list(original[metadata['column_map']['run_order']])
    assert list(base[columns['standard_order']]) == list(
        original[metadata['column_map']['standard_order']])
    np.testing.assert_allclose(base[columns['responses']['Y']].astype(float),
                               original['响应_Y'].astype(float))
    added = folded[folded[columns['batch_id']] == 'FOLD1']
    assert len(added) == 12
    assert added[columns['responses']['Y']].isna().all()
    assert added[columns['source_run_id']].notna().all()
    # 新增运行只使用新的后续运行序区间。
    assert min(added[columns['run_order']]) > max(base[columns['run_order']])
    assert summary['batch_id'] == 'FOLD1'
    # 未填写新增响应时拒绝完整分析。
    with pytest.raises(ValueError, match='缺失'):
        analyze_pb(folded, folded_metadata, 'Y')


@pytest.mark.parametrize('order_change', ['rerandomize', 'renumber'])
def test_foldover_preserves_supported_source_execution_history(order_change):
    frame, metadata = create_pb(pb_spec(12), 12)
    if order_change == 'rerandomize':
        from doe_modify import rerandomize
        frame, metadata = rerandomize(frame, metadata, 19)
    else:
        from doe_modify import renumber
        frame, metadata = renumber(frame, metadata)
    source_order = dict(zip(frame['运行ID'], frame['运行序']))

    folded, folded_metadata, _ = create_pb_foldover(frame, metadata)
    restored = restore_design_result(folded, folded_metadata)
    base = {run.run_id: run.run_order for run in restored.runs if run.batch_id == 'BASE'}
    assert base == source_order
    assert [run.run_order for run in restored.runs] == list(range(1, 25))
    assert foldover_matrix_fingerprint(
        restored.runs, restored.spec.factors) == \
        restored.spec.foldover_lineage['current_matrix_sha256']


@pytest.mark.parametrize(('run_count', 'folded_factors'), [(12, None), (20, 'F1')])
def test_pb_foldover_display_reorder_preserves_identity(run_count, folded_factors):
    frame, metadata = create_pb(pb_spec(run_count), run_count, measured=True)
    response(frame)
    columns = metadata['column_map']
    for index, column in enumerate(columns['measured_levels'].values()):
        frame[column] = pd.array([100 + index + row / 10 for row in range(run_count)],
                                 dtype='Float64')
    folded, folded_metadata, _ = create_pb_foldover(frame, metadata, folded_factors)
    columns = folded_metadata['column_map']
    design_identity = deepcopy(folded_metadata['design'])
    response(folded)
    added = folded[columns['batch_id']] == 'FOLD1'
    for index, column in enumerate(columns['measured_levels'].values()):
        folded.loc[added, column] = pd.array(
            [500 + index + row / 10 for row in range(int(added.sum()))], dtype='Float64')
    tracked = [columns['run_id'], columns['standard_order'], columns['run_order'],
               columns['point_type'], columns['replicate'], *columns['factors'].values(),
               *columns['measured_levels'].values(), *columns['responses'].values(),
               columns['batch_id'], columns['source_run_id']]
    before = folded.sort_values(columns['run_id'])[tracked].reset_index(drop=True)

    for by, order_key in (('standard', 'standard_order'), ('run', 'run_order')):
        folded, folded_metadata = reorder(folded, folded_metadata, by=by)
        order_column = columns[order_key]
        assert list(folded[order_column]) == sorted(folded[order_column])
        restored = restore_design_result(folded, folded_metadata)
        validate_pb(restored)
        pd.testing.assert_frame_equal(
            folded.sort_values(columns['run_id'])[tracked].reset_index(drop=True), before)
        assert folded_metadata['design'] == design_identity
        assert analyze_pb(folded, folded_metadata, 'Y')['n'] == 2 * run_count


def test_single_factor_foldover_only_flips_that_column():
    frame, metadata = create_pb(pb_spec(12), 12)
    response(frame)
    folded, folded_metadata, summary = create_pb_foldover(frame, metadata, 'F1')
    names = [f'F{i}' for i in range(1, 12)]
    base = frame.sort_values('标准序')
    added = folded[folded_metadata['column_map']['batch_id']] == 'FOLD1'
    added = folded[added].sort_values('标准序')
    assert list(added[f'设定_F1'].astype(float)) == [-v for v in base['设定_F1'].astype(float)]
    for name in names[1:]:
        assert list(added[f'设定_{name}'].astype(float)) == list(base[f'设定_{name}'].astype(float))
    assert summary['folded_factors'] == ('F1',)
    # 单因子折叠不是全模型去混杂：仍有 45 个部分混杂交互。
    assert len(summary['after']['partial']) == 45
    assert summary['confounding_reduced'] is True


def test_estimable_and_unestimable_interaction_changes_are_reported():
    """界面预览使用的可估计/不可估计计数必须与集合大小和秩一致。"""
    frame, metadata = create_pb(pb_spec(12), 12)
    response(frame)
    _, _, summary = create_pb_foldover(frame, metadata)
    for key in ('before', 'after'):
        block = summary[key]
        labels = {row['interaction'] for row in block['complete']}
        assert len(block['estimable']) == (block['interaction_count'] - len(labels)
                                           - len(block['unestimable']))
        assert not labels & set(block['estimable'])
    # PB12 全因子折叠后每个交互都可单独估计。
    assert len(summary['after']['estimable']) == 55
    assert summary['after']['unestimable'] == []


def test_folded_pb_analysis_recovers_analytic_coefficients():
    frame, metadata = create_pb(pb_spec(12), 12)
    response(frame)
    folded, folded_metadata, _ = create_pb_foldover(frame, metadata)
    columns = folded_metadata['column_map']
    added = folded[columns['batch_id']] == 'FOLD1'
    y = (10 + 2 * folded.loc[added, '设定_F1'].to_numpy(dtype=float)
         - 3 * folded.loc[added, '设定_F2'].to_numpy(dtype=float)
         + 4 * folded.loc[added, '设定_F3'].to_numpy(dtype=float))
    folded.loc[added, columns['responses']['Y']] = pd.array(y, dtype='Float64')
    result = analyze_pb(folded, folded_metadata, 'Y')
    assert result['n'] == 24
    np.testing.assert_allclose(result['coefficients'][:4], [10, 2, -3, 4], atol=1e-9)
    assert result['df'] == 24 - result['rank']


def test_folded_pb_analysis_keeps_confounding_warning_and_rejects_bad_effects():
    """折叠后仍须提示混杂投影不代表因果；完全由未建模交互产生的“效应”
    不得被报告为独立显著因子。"""
    frame, metadata = create_pb(pb_spec(12), 12)
    response(frame)
    folded, folded_metadata, summary = create_pb_foldover(frame, metadata, 'F1')
    columns = folded_metadata['column_map']
    added = folded[columns['batch_id']] == 'FOLD1'
    folded.loc[added, columns['responses']['Y']] = pd.array(
        [10 + 2 * row['设定_F1'] - 3 * row['设定_F2'] + 4 * row['设定_F3']
         for _, row in folded.loc[added].iterrows()], dtype='Float64')
    result = analyze_pb(folded, folded_metadata, 'Y')
    assert '混杂' in result['assumption']
    assert '因果' in result['assumption']
    # 单因子折叠后仍有部分混杂交互，分析不能宣称全部主效应已去混杂。
    assert summary['after']['partial']
    assert result['rank'] == 12


def test_unfolded_pb_analysis_baseline_is_unchanged():
    frame, metadata = create_pb(pb_spec(12), 12)
    response(frame)
    result = analyze_pb(frame, metadata, 'Y')
    np.testing.assert_allclose(result['coefficients'], [10, 2, -3, 4, 0, 0, 0, 0,
                                                        0, 0, 0, 0], atol=1e-9)
    assert result['n'] == 12 and result['rank'] == 12
    assert screening_matrix_sha256(restore_design_result(frame, metadata)) == \
        metadata['design']['screening_matrix']['matrix_sha256']


def tampered_pb_pairs():
    frame, metadata = create_pb(pb_spec(12), 12)
    response(frame)
    folded, folded_metadata, _ = create_pb_foldover(frame, metadata)
    return frame, metadata, folded, folded_metadata


def rebound_pb_foldover(frame, metadata, updates, *, sort_rows=False):
    """Apply record edits and rebind every affected saved digest and fingerprint."""
    original = restore_design_result(frame, metadata)
    damaged_metadata = deepcopy(metadata)
    damaged_frame = frame.copy(deep=True)
    updated_runs = []
    for row, run in enumerate(original.runs):
        changes = dict(updates.get(run.run_id, {}))
        if 'settings' in changes:
            changes['settings'] = {**run.settings, **changes['settings']}
        updated = replace(run, **changes)
        updated_runs.append(updated)
        if updated.standard_order != run.standard_order:
            col = damaged_metadata['column_map']['standard_order']
            damaged_frame.iat[row, damaged_frame.columns.get_loc(col)] = updated.standard_order
        if updated.run_order != run.run_order:
            col = damaged_metadata['column_map']['run_order']
            damaged_frame.iat[row, damaged_frame.columns.get_loc(col)] = updated.run_order
        if updated.settings != run.settings:
            for factor_id, column in damaged_metadata['column_map']['factors'].items():
                damaged_frame.iat[row, damaged_frame.columns.get_loc(column)] = \
                    updated.settings[factor_id]

    if sort_rows:
        row_order = sorted(range(len(updated_runs)), key=lambda row: updated_runs[row].run_order)
        updated_runs = [updated_runs[row] for row in row_order]
        damaged_frame = damaged_frame.iloc[row_order].reset_index(drop=True)
    result = replace(original, runs=tuple(updated_runs))
    design = damaged_metadata['design']
    design['screening_matrix']['matrix_sha256'] = screening_matrix_sha256(
        result, base_only=True)
    lineage = design['foldover_lineage']
    base = [run for run in result.runs if run.batch_id == 'BASE']
    lineage['source_matrix_sha256'] = foldover_matrix_fingerprint(
        base, result.spec.factors)
    lineage['current_matrix_sha256'] = foldover_matrix_fingerprint(
        result.runs, result.spec.factors)
    result = replace(result, spec=DesignSpec.from_dict(design))
    if sort_rows:
        damaged_metadata['worksheet']['run_rows'] = [
            {'run_id': run.run_id, 'row': row} for row, run in enumerate(result.runs)
        ]
    damaged_metadata['worksheet']['input_fingerprint'] = _fingerprint(
        design, damaged_metadata['column_map'], result)
    return damaged_frame, damaged_metadata, result


@pytest.mark.parametrize(
    'run_count,folded_factors,changed_factor,change',
    [(12, None, 'F1', 'restore'), (20, 'F1', 'F2', 'flip')],
)
def test_rebound_foldover_digests_do_not_hide_invalid_transform(
        run_count, folded_factors, changed_factor, change):
    frame, metadata = create_pb(pb_spec(run_count), run_count)
    folded, folded_metadata, _ = create_pb_foldover(
        frame, metadata, folded_factors)
    source_id, added_id = folded_metadata['design']['foldover_lineage']['run_map'][0]
    original = restore_design_result(folded, folded_metadata)
    by_id = {run.run_id: run for run in original.runs}
    source_level = by_id[source_id].settings[changed_factor]
    wrong_level = (source_level if change == 'restore'
                   else -source_level)
    damaged, rebound_metadata, rebound_result = rebound_pb_foldover(
        folded, folded_metadata,
        {added_id: {'settings': {changed_factor: wrong_level}}})

    lineage = rebound_metadata['design']['foldover_lineage']
    base_runs = [run for run in rebound_result.runs if run.batch_id == 'BASE']
    assert foldover_matrix_fingerprint(base_runs, rebound_result.spec.factors) \
        == lineage['source_matrix_sha256']
    assert foldover_matrix_fingerprint(rebound_result.runs, rebound_result.spec.factors) \
        == lineage['current_matrix_sha256']
    assert screening_matrix_sha256(rebound_result, base_only=True) \
        == rebound_metadata['design']['screening_matrix']['matrix_sha256']
    assert rebound_metadata['worksheet']['input_fingerprint'] == _fingerprint(
        rebound_metadata['design'], rebound_metadata['column_map'], rebound_result)
    with pytest.raises(ValueError, match='PB Foldover.*折叠变换'):
        restore_design_result(damaged, rebound_metadata)
    with pytest.raises(ValueError, match='PB Foldover.*折叠变换'):
        validate_pb(rebound_result)


@pytest.mark.parametrize('damage', ['base_run_order', 'added_run_order',
                                    'source_standard_order'])
def test_rebound_history_order_checks_distinguish_reconstructible_history(damage):
    _, _, folded, metadata = tampered_pb_pairs()
    lineage = metadata['design']['foldover_lineage']
    pairs = lineage['run_map']
    original = restore_design_result(folded, metadata)
    by_id = {run.run_id: run for run in original.runs}
    if damage == 'base_run_order':
        changes = {
            pairs[0][0]: {'run_order': by_id[pairs[1][0]].run_order},
            pairs[1][0]: {'run_order': by_id[pairs[0][0]].run_order},
        }
    elif damage == 'added_run_order':
        changes = {
            pairs[0][1]: {'run_order': by_id[pairs[1][1]].run_order},
            pairs[1][1]: {'run_order': by_id[pairs[0][1]].run_order},
        }
    else:
        first_source, first_added = pairs[0]
        second_source, second_added = pairs[1]
        changes = {
            first_source: {
                'standard_order': 2,
                'settings': dict(by_id[second_source].settings),
            },
            second_source: {
                'standard_order': 1,
                'settings': dict(by_id[first_source].settings),
            },
            first_added: {
                'standard_order': 14,
                'settings': dict(by_id[second_added].settings),
            },
            second_added: {
                'standard_order': 13,
                'settings': dict(by_id[first_added].settings),
            },
        }
    damaged, rebound_metadata, rebound_result = rebound_pb_foldover(
        folded, metadata, changes, sort_rows=(damage == 'added_run_order'))
    base_runs = [run for run in rebound_result.runs if run.batch_id == 'BASE']
    assert foldover_matrix_fingerprint(base_runs, rebound_result.spec.factors) \
        == rebound_metadata['design']['foldover_lineage']['source_matrix_sha256']
    assert foldover_matrix_fingerprint(rebound_result.runs, rebound_result.spec.factors) \
        == rebound_metadata['design']['foldover_lineage']['current_matrix_sha256']
    assert rebound_metadata['worksheet']['input_fingerprint'] == _fingerprint(
        rebound_metadata['design'], rebound_metadata['column_map'], rebound_result)
    if damage == 'base_run_order':
        # v5 has no stored parent-order snapshot; a rebound BASE permutation is historical data.
        restored = restore_design_result(damaged, rebound_metadata)
        validate_pb(restored)
        assert {run.run_order for run in restored.runs if run.batch_id == 'BASE'} \
            == set(range(1, 13))
    else:
        with pytest.raises(ValueError, match='PB Foldover'):
            restore_design_result(damaged, rebound_metadata)


def test_parent_factor_level_tampering_is_rejected():
    _, _, folded, folded_metadata = tampered_pb_pairs()
    damaged = folded.copy(deep=True)
    damaged.loc[0, '设定_F1'] = -damaged.loc[0, '设定_F1']
    with pytest.raises(ValueError):
        restore_design_result(damaged, folded_metadata)


def test_folded_sign_and_unfolded_column_tampering_is_rejected():
    _, _, folded, folded_metadata = tampered_pb_pairs()
    columns = folded_metadata['column_map']
    added = folded.index[folded[columns['batch_id']] == 'FOLD1']
    for column in ('设定_F1', '设定_F2'):
        damaged = folded.copy(deep=True)
        damaged.loc[added[0], column] = -damaged.loc[added[0], column]
        with pytest.raises(ValueError):
            restore_design_result(damaged, folded_metadata)


def test_source_run_and_batch_mismatch_is_rejected():
    _, _, folded, folded_metadata = tampered_pb_pairs()
    columns = folded_metadata['column_map']
    added = folded.index[folded[columns['batch_id']] == 'FOLD1']
    damaged = folded.copy(deep=True)
    damaged.loc[added[0], columns['source_run_id']] = damaged.loc[added[1],
                                                                   columns['source_run_id']]
    with pytest.raises(ValueError, match='Foldover'):
        restore_design_result(damaged, folded_metadata)
    damaged = folded.copy(deep=True)
    damaged.loc[added[0], columns['batch_id']] = 'BASE'
    with pytest.raises(ValueError):
        restore_design_result(damaged, folded_metadata)


def test_extra_or_missing_added_rows_and_reordered_base_are_rejected():
    _, _, folded, folded_metadata = tampered_pb_pairs()
    columns = folded_metadata['column_map']
    with pytest.raises(ValueError):
        restore_design_result(folded.iloc[:-1].copy(), folded_metadata)
    duplicated = pd.concat([folded, folded.iloc[[-1]]], ignore_index=True)
    with pytest.raises(ValueError):
        restore_design_result(duplicated, folded_metadata)
    swapped = folded.copy(deep=True)
    swapped.loc[:, columns['standard_order']] = swapped[columns['standard_order']][::-1].to_numpy()
    with pytest.raises(ValueError):
        restore_design_result(swapped, folded_metadata)


def test_forged_lineage_digest_is_rejected():
    _, _, folded, folded_metadata = tampered_pb_pairs()
    damaged = json.loads(json.dumps(folded_metadata))
    damaged['design']['foldover_lineage']['current_matrix_sha256'] = 'a' * 64
    with pytest.raises(ValueError):
        restore_design_result(folded, damaged)


def test_response_precision_is_preserved_for_source_rows():
    frame, metadata = create_pb(pb_spec(12), 12)
    values = [0.1 + i / 7 for i in range(12)]
    frame['响应_Y'] = pd.array(values, dtype='Float64')
    folded, folded_metadata, _ = create_pb_foldover(frame, metadata)
    columns = folded_metadata['column_map']
    base = folded[folded[columns['batch_id']] == 'BASE']
    assert list(base[columns['responses']['Y']].astype(float)) == values
    assert str(folded[columns['responses']['Y']].dtype) == 'Float64'


@pytest.mark.parametrize('values,dtype,expected', [
    ([2 ** 53 + 1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144], 'int64', 'Int64'),
    ([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2], 'float64', 'Float64'),
    ([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], 'object', 'object'),
    ([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 2 ** 63], 'uint64', 'UInt64'),
])
def test_response_dtype_round_trip_without_precision_loss(values, dtype, expected):
    """非 Float64 源列：可表达空值时保留，numpy dtype 转同域可空 dtype。"""
    frame, metadata = create_pb(pb_spec(12), 12)
    frame['响应_Y'] = pd.Series(values, dtype=dtype)
    folded, folded_metadata, _ = create_pb_foldover(frame, metadata)
    columns = folded_metadata['column_map']
    column = folded[columns['responses']['Y']]
    assert str(column.dtype) == expected
    base = folded[folded[columns['batch_id']] == 'BASE']
    assert list(base[columns['responses']['Y']]) == values
    restored = restore_design_result(folded, folded_metadata)
    assert [run.responses['Y'] for run in restored.runs[:12]] == values


def test_run_limit_guard_rejects_and_source_is_unchanged(monkeypatch):
    """受支持范围内折叠后最多 96 行，10,000 上限无法自然触发。

    因此把模块常量临时调低，直接证明守卫在超限时拒绝且不修改来源。
    """
    import doe_pb_foldover

    frame, metadata = create_pb(pb_spec(12), 12)
    before = frame.copy(deep=True)
    monkeypatch.setattr(doe_pb_foldover, 'MAX_RUNS', 20)
    with pytest.raises(ValueError, match='不能超过 20'):
        create_pb_foldover(frame, metadata)
    pd.testing.assert_frame_equal(frame, before)


def test_unsupported_pb_sources_are_rejected():
    # 分区组 PB 不允许折叠。
    blocked, blocked_metadata = create_pb(pb_spec(12, 3), 12, replicates=2,
                                          block_replicates=True)
    with pytest.raises(ValueError, match='分区组'):
        create_pb_foldover(blocked, blocked_metadata)
    # 中心点 PB 不允许折叠。
    centered, centered_metadata = create_pb(pb_spec(12, 3), 12, center_points=1)
    with pytest.raises(ValueError, match='中心点'):
        create_pb_foldover(centered, centered_metadata)
    # 多个重复批次不允许折叠。
    repeated, repeated_metadata = create_pb(pb_spec(12, 3), 12, replicates=2)
    with pytest.raises(ValueError, match='重复批次'):
        create_pb_foldover(repeated, repeated_metadata)
    # 分类因子 PB 不允许折叠。
    categorical = DesignSpec('pb', (FactorSpec('F1', 'F1', -1, 1),
                                    FactorSpec('F2', 'F2', -1, 1),
                                    FactorSpec('F3', 'F3', None, None,
                                               factor_type='categorical',
                                               levels=('甲', '乙'))), ('Y',), seed=7,
                            design_type='plackett_burman',
                            screening_matrix={'construction_id': 'pb12.v1',
                                              'source_kind': 'publication',
                                              'source_id': 'nist.pb12',
                                              'matrix_sha256': '0' * 64})
    cat_frame, cat_metadata = create_pb(categorical, 12)
    with pytest.raises(ValueError, match='连续'):
        create_pb_foldover(cat_frame, cat_metadata)


def test_second_foldover_and_non_foldover_metadata_changes_are_rejected():
    _, _, folded, folded_metadata = tampered_pb_pairs()
    with pytest.raises(ValueError, match='再次折叠'):
        create_pb_foldover(folded, folded_metadata)
    damaged = json.loads(json.dumps(folded_metadata))
    damaged['design']['construction_version'] = 'v1'
    with pytest.raises(ValueError, match='v2'):
        restore_design_result(folded, damaged)


def test_generic_modification_operations_are_blocked_for_folded_pb():
    from doe_augment import augment
    from doe_modify import modify_summary, renumber, replicate, rerandomize

    _, _, folded, folded_metadata = tampered_pb_pairs()
    summary = modify_summary(folded, folded_metadata)
    assert summary['can_rerandomize'] is False
    assert summary['can_renumber'] is False
    assert 'Plackett–Burman' in summary['unavailable_reason']
    with pytest.raises(ValueError, match='已折叠'):
        rerandomize(folded, folded_metadata, 5)
    with pytest.raises(ValueError, match='已折叠'):
        renumber(folded, folded_metadata)
    with pytest.raises(ValueError, match='折叠'):
        replicate(folded, folded_metadata, count=1)
    with pytest.raises(ValueError, match='折叠'):
        augment(folded, folded_metadata, [{'F1': -1, 'F2': -1}], 1)


def test_saturated_pb_complete_confounding_shrinks_after_all_factor_fold():
    frame, metadata = create_pb(pb_spec(32), 32)
    response(frame)
    _, _, summary = create_pb_foldover(frame, metadata)
    assert len(summary['before']['complete']) == 465
    assert summary['after']['complete'] == []
    assert summary['before']['joint_rank'] == 32
    assert summary['after']['joint_rank'] == 63


def test_summary_of_unfolded_pb_reports_no_fold():
    frame, metadata = create_pb(pb_spec(12), 12)
    summary = pb_foldover_summary(frame, metadata)
    assert summary['folded'] is False
    assert summary['added_runs'] == 0
    assert summary['confounding_reduced'] is False
