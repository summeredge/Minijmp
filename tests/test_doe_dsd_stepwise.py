"""DSD Stepwise：独立参考、边界与真实 GUI 失效路径。"""
import importlib.util
import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from doe_core import DesignSpec, FactorSpec, restore_design_result
from doe_dsd import create_dsd
from doe_stepwise import select_dsd_stepwise


ROOT = Path(__file__).parent / 'fixtures' / 'doe_phase2_p4a_reference'
REFERENCE = json.loads((ROOT / 'dsd_reference.json').read_text(encoding='utf-8'))
CASES = {case['id']: case for case in REFERENCE['cases']}


def dsd_spec(continuous=6, categorical=0, seed=7):
    factors = tuple(FactorSpec(f'F{i}', f'F{i}', 0.1, 0.3)
                    for i in range(1, continuous + 1))
    if categorical:
        factors += tuple(FactorSpec(f'F{i}', f'F{i}', None, None,
                                    factor_type='categorical', levels=('甲', '乙'))
                         for i in range(continuous + 1, continuous + categorical + 1))
    if categorical == 1:
        key, source = f'dsd{continuous}c1', f'jones.dsd{continuous}c1'
    elif categorical == 2:
        key, source = 'dsd4c2', 'foldover.dsd4c2'
    else:
        key, source = f'dsd{continuous}', f'conference.dsd{continuous}'
    identity = {'construction_id': key + '.v1', 'source_kind': 'mathematical_construction',
                'source_id': source, 'matrix_sha256': '0' * 64}
    return DesignSpec('dsd', factors, ('Y',), seed=seed,
                      design_type='definitive_screening', screening_matrix=identity)


def coded_frame(reference_case):
    """按参考案例的设计形状构造 DSD 工作表。"""
    design = reference_case['design']
    spec = dsd_spec(design['continuous'], design['categorical'])
    return create_dsd(spec, replicates=design['replicates'], blocks=design['blocks'])


def response_from_reference(frame, metadata, case):
    """按标准序把参考响应写入工作表（多次重复时逐行重复参考块）。"""
    by_standard = {run.standard_order: run.run_id for run in
                   restore_design_result(frame, metadata).runs}
    expected = case['response']
    values = {by_standard[i + 1]: expected[i % len(expected)]
              for i in range(len(by_standard))}
    run_column = metadata['column_map']['run_id']
    response_column = metadata['column_map']['responses']['Y']
    frame[response_column] = pd.array([values[key] for key in frame[run_column]],
                                      dtype='Float64')
    return values


def test_reference_verifier_rebuilds_without_production_imports():
    spec = importlib.util.spec_from_file_location('p4a_dsd_verifier',
                                                  ROOT / 'verify_dsd_reference.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module.verify()
    assert set(result) == set(CASES)
    assert all(row['stop_reason'] in ('no_eligible_entry', 'selection_stable')
               for row in result.values())


@pytest.mark.parametrize('identifier', ['DSD-S01-main-effects', 'DSD-S02-quadratic',
                                        'DSD-S03-interaction',
                                        'DSD-S04-mixed-blocks',
                                        'DSD-S05-enter-then-remove'])
def test_stepwise_trajectory_matches_independent_reference(identifier):
    case = CASES[identifier]
    frame, metadata = coded_frame(case)
    response_from_reference(frame, metadata, case)
    candidates = [tuple(term) for term in case['candidate_terms']]
    result = select_dsd_stepwise(
        frame, metadata, 'Y', candidates=candidates,
        alpha_enter=case['alpha_enter'], alpha_remove=case['alpha_remove'])
    assert result['method'] == 'stepwise'
    expected = case['selection_steps']
    assert len(result['selection_steps']) == len(expected)
    for want, got in zip(expected, result['selection_steps']):
        assert want['action'] == got['action']
        assert tuple(want['term']) == got['term']
        assert got['f'] == pytest.approx(want['f'], rel=1e-9, abs=1e-12)
        assert got['p'] == pytest.approx(want['p'], rel=1e-7, abs=1e-12)
        assert got['sse_before'] == pytest.approx(want['sse_before'], rel=1e-9)
        assert got['sse_after'] == pytest.approx(want['sse_after'], rel=1e-9)
        assert got['rank_after'] == want['rank_after']
        assert got['error_df'] == want['error_df']
    assert [list(term) for term in result['selected_terms']] == case['selected_terms']
    assert result['stop_reason'] == case['stop_reason']
    assert result['final_rank'] == case['final_rank']
    assert result['final_residual_df'] == case['final_residual_df']
    analysis = result['analysis']
    assert analysis['rank'] == case['final_rank']
    assert np.allclose(analysis['coefficients'], case['coefficients'], atol=1e-9)


def test_quadratic_never_enters_before_its_main_effect():
    case = CASES['DSD-S02-quadratic']
    frame, metadata = coded_frame(case)
    response_from_reference(frame, metadata, case)
    result = select_dsd_stepwise(frame, metadata, 'Y',
                                 candidates=[tuple(term) for term in case['candidate_terms']])
    entered = [step for step in result['selection_steps'] if step['action'] == 'enter']
    assert [tuple(step['term']) for step in entered][:2] == [('F1',), ('F1', 'F1')]
    parent_index = next(i for i, step in enumerate(entered) if tuple(step['term']) == ('F1',))
    assert parent_index < next(i for i, step in enumerate(entered)
                               if tuple(step['term']) == ('F1', 'F1'))


def test_interaction_requires_both_main_effects_first():
    case = CASES['DSD-S03-interaction']
    frame, metadata = coded_frame(case)
    response_from_reference(frame, metadata, case)
    result = select_dsd_stepwise(frame, metadata, 'Y',
                                 candidates=[tuple(term) for term in case['candidate_terms']])
    seen = []
    for step in result['selection_steps']:
        if step['action'] == 'enter' and len(step['term']) == 2:
            assert set(term for term in seen) >= set(step['term'])
        if step['action'] == 'enter':
            seen.extend(step['term'])
    assert tuple(result['selected_terms'][-1]) == ('F1', 'F2')


def test_candidate_limit_and_option_validation_are_explicit():
    frame, metadata = create_dsd(dsd_spec(10))
    frame['响应_Y'] = pd.array(np.arange(len(frame), dtype=float), dtype='Float64')
    candidates = ([(f'F{i}',) for i in range(1, 11)] +
                  [(f'F{i}', f'F{i}') for i in range(1, 11)] +
                  [(f'F{i}', f'F{j}') for i in range(1, 11) for j in range(i + 1, 11)])
    assert len(candidates) == 65
    with pytest.raises(ValueError, match='64'):
        select_dsd_stepwise(frame, metadata, 'Y', candidates=candidates)
    with pytest.raises(ValueError, match='Alpha'):
        select_dsd_stepwise(frame, metadata, 'Y', alpha_enter=0)
    with pytest.raises(ValueError, match='Alpha'):
        select_dsd_stepwise(frame, metadata, 'Y', alpha_remove=1.0)
    with pytest.raises(ValueError, match='最大步骤数'):
        select_dsd_stepwise(frame, metadata, 'Y', max_steps=0)
    with pytest.raises(ValueError, match='重复模型项'):
        select_dsd_stepwise(frame, metadata, 'Y', candidates=[('F1',), ('F1',)])
    with pytest.raises(ValueError, match='无效模型项'):
        select_dsd_stepwise(frame, metadata, 'Y', candidates=[('F1', 'F2', 'F3')])
    with pytest.raises(ValueError, match='层级'):
        select_dsd_stepwise(frame, metadata, 'Y',
                            candidates=[('F1',), ('F1', 'F1')],
                            initial=[('F1', 'F1')], forced=[('F1', 'F1')])
    with pytest.raises(ValueError, match='子集'):
        select_dsd_stepwise(frame, metadata, 'Y', candidates=[('F1',)],
                            forced=[('F2',)])


def test_missing_and_nonfinite_responses_are_rejected():
    frame, metadata = create_dsd(dsd_spec(6))
    frame['响应_Y'] = pd.array([None] * len(frame), dtype='Float64')
    with pytest.raises(ValueError, match='缺失'):
        select_dsd_stepwise(frame, metadata, 'Y')
    values = list(range(len(frame)))
    frame['响应_Y'] = pd.array([np.inf] + values[1:], dtype='Float64')
    with pytest.raises(ValueError, match='有限'):
        select_dsd_stepwise(frame, metadata, 'Y')


def test_saturated_initial_model_reports_residual_df_limit():
    frame, metadata = create_dsd(dsd_spec(6))
    frame['响应_Y'] = pd.array(np.linspace(0, 1, len(frame)), dtype='Float64')
    mains = [(f'F{i}',) for i in range(1, 7)]
    saturated = [('F1', 'F2'), ('F1', 'F3'), ('F1', 'F4'), ('F1', 'F5'),
                 ('F2', 'F3'), ('F1', 'F1')]
    rest = [(f'F{i}', f'F{j}') for i in range(1, 7) for j in range(i + 1, 7)]
    result = select_dsd_stepwise(frame, metadata, 'Y',
                                 candidates=mains + saturated,
                                 initial=mains + saturated, forced=mains + saturated)
    assert result['stop_reason'] == 'residual_df_limit'
    assert result['selection_steps'] == []
    assert result['final_rank'] == len(frame)


def test_zero_variance_response_stops_without_fake_p_values():
    frame, metadata = create_dsd(dsd_spec(6))
    frame['响应_Y'] = pd.array([5.0] * len(frame), dtype='Float64')
    result = select_dsd_stepwise(frame, metadata, 'Y')
    assert result['stop_reason'] == 'zero_error_variance'
    assert result['selection_steps'] == []


def test_cycle_is_detected_instead_of_looping_forever():
    case = CASES['DSD-S03-interaction']
    frame, metadata = coded_frame(case)
    response_from_reference(frame, metadata, case)
    result = select_dsd_stepwise(frame, metadata, 'Y',
                                 candidates=[tuple(term) for term in case['candidate_terms']],
                                 alpha_enter=0.2, alpha_remove=0.01, max_steps=50)
    assert result['stop_reason'] == 'model_cycle_detected'
    assert len(result['selection_steps']) == 2


def test_iteration_budget_is_reported_and_bounded():
    case = CASES['DSD-S05-enter-then-remove']
    frame, metadata = coded_frame(case)
    response_column = metadata['column_map']['responses']['Y']
    run_column = metadata['column_map']['run_id']
    by_standard = {run.standard_order: run.run_id for run in
                   restore_design_result(frame, metadata).runs}
    values = dict(zip((by_standard[i] for i in range(1, len(case['response']) + 1)),
                      case['response']))
    frame[response_column] = pd.array([values[key] for key in frame[run_column]],
                                      dtype='Float64')
    result = select_dsd_stepwise(frame, metadata, 'Y',
                                 candidates=[tuple(term) for term in case['candidate_terms']],
                                 alpha_enter=0.2, alpha_remove=0.2, max_steps=3)
    assert result['stop_reason'] == 'iteration_budget'
    assert len(result['selection_steps']) == 3


def test_exact_p_value_ties_follow_candidate_order():
    """对称响应使 F1 与 F2 的 F 完全相同；并列时按候选项顺序取最早者。

    并列判定不依赖字典顺序、线程或工作表行序，因此交换候选顺序后
    胜出的项必须随之改变。
    """
    frame, metadata = create_dsd(dsd_spec(6))
    a = 2 * frame['设定_F1'].astype(float) - 1
    b = 2 * frame['设定_F2'].astype(float) - 1
    frame['响应_Y'] = pd.array(10 + 5 * a + 5 * b, dtype='Float64')
    forward = select_dsd_stepwise(frame, metadata, 'Y',
                                  candidates=[('F1',), ('F2',), ('F3',)])
    reverse = select_dsd_stepwise(frame, metadata, 'Y',
                                  candidates=[('F2',), ('F1',), ('F3',)])
    first = forward['selection_steps'][0]
    assert first['term'] == ('F1',)
    assert reverse['selection_steps'][0]['term'] == ('F2',)
    # 两次的首步 F 与 p 在数值上完全相同，只有顺序不同。
    assert first['f'] == reverse['selection_steps'][0]['f']
    assert first['p'] == reverse['selection_steps'][0]['p']
    # F3 无效应，两次都不能进入。
    assert all(step['term'] != ('F3',) for step in forward['selection_steps'])


def test_forced_parent_allows_higher_order_term_but_never_removes_it():
    case = CASES['DSD-S02-quadratic']
    frame, metadata = coded_frame(case)
    response_from_reference(frame, metadata, case)
    result = select_dsd_stepwise(frame, metadata, 'Y',
                                 candidates=[tuple(term) for term in case['candidate_terms']],
                                 initial=[('F1',)], forced=[('F1',)])
    assert ('F1',) in result['selected_terms']
    assert all(step['term'] != ('F1',) or step['action'] == 'enter'
               for step in result['selection_steps'])
    assert not any(step['action'] == 'remove' and step['term'] == ('F1',)
                   for step in result['selection_steps'])


def test_rank_deficient_candidates_stop_instead_of_reporting_success():
    # 6 因子 DSD 上强制主效应与 F1²…F5²，剩余自由度不足以区分 F1*F6 等项：
    # 必须报告 rank_deficiency，且不得为不可估计项伪造 p 值。
    frame, metadata = create_dsd(dsd_spec(6))
    frame['响应_Y'] = pd.array(np.linspace(1, 2, len(frame)), dtype='Float64')
    mains = [(f'F{i}',) for i in range(1, 7)]
    squares = [(f'F{i}', f'F{i}') for i in range(1, 7)]
    pairs = [(f'F{i}', f'F{j}') for i in range(1, 7) for j in range(i + 1, 7)]
    forced = mains + squares[:5]
    result = select_dsd_stepwise(frame, metadata, 'Y', candidates=mains + squares + pairs,
                                 initial=forced, forced=forced)
    assert result['stop_reason'] in ('rank_deficiency', 'selection_stable')
    assert result['stop_reason'] == 'rank_deficiency'
    assert result['final_residual_df'] == 1
    assert all(step['p'] is not None and np.isfinite(step['p'])
               for step in result['selection_steps'])


def test_reference_source_change_is_detected():
    frame, metadata = create_dsd(dsd_spec(6))
    frame['响应_Y'] = pd.array(np.arange(len(frame), dtype=float), dtype='Float64')
    changed = frame.copy(deep=True)
    changed.loc[changed.index[0], '设定_F1'] = 0.2
    with pytest.raises(ValueError):
        select_dsd_stepwise(changed, metadata, 'Y')
