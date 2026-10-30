from itertools import product

import numpy as np
import pandas as pd
import pytest
import statsmodels.api as sm
import statsmodels.formula.api as smf

from doe_core import DesignSpec, FactorSpec, restore_design_result
from doe_taguchi import create_taguchi
from doe_taguchi_analysis import (best_settings, create_confirmation_frame,
                                  noise_response_model, predict_taguchi_model)
from doe_taguchi_arrays import ARRAYS


def factor(factor_id, levels):
    return FactorSpec(factor_id, factor_id, None, None, factor_type='categorical',
                      levels=tuple(levels), level_type='text')


def l9_data():
    spec = DesignSpec(
        'TG', tuple(factor(key, ('low', 'mid', 'high')) for key in 'AB'), ('Y',),
        seed=12, design_type='taguchi',
        taguchi={'kind': 'static', 'array_id': 'L9(3^4)',
                 'matrix_sha256': ARRAYS['L9(3^4)'].sha256,
                 'columns': {'A': 1, 'B': 2},
                 'noise_array_id': None, 'noise_matrix_sha256': None,
                 'noise_columns': {}, 'signal_factor': None})
    frame, metadata = create_taguchi(spec, replicates=2)
    design = restore_design_result(frame, metadata)
    code = {'low': -1, 'mid': 0, 'high': 1}
    values = {}
    for run in design.runs:
        a, b = (code[run.settings[key]] for key in 'AB')
        values[run.run_id] = 52 + 3*a - 2*b + 4*a*b + (
            0.25 if run.replicate == 1 else -0.25)
    frame['响应_Y'] = [values[run_id] for run_id in frame['运行ID']]
    return frame, metadata


def independent_l9_ols(frame):
    data = pd.DataFrame({
        'y': frame['响应_Y'], 'fa': frame['设定_A'],
        'fb': frame['设定_B']})
    return smf.ols(
        "y ~ C(fa, Treatment(reference='low')) * "
        "C(fb, Treatment(reference='low'))", data=data).fit()


def test_taguchi_selected_interaction_search_and_mean_ci_match_statsmodels():
    frame, metadata = l9_data()
    terms = (('A',), ('B',), ('A', 'B'))
    reference = independent_l9_ols(frame)
    result = best_settings(frame, metadata, 'Y', 'mean', target=54,
                           model_terms=terms, confidence=0.90)
    settings = result['best']
    point = pd.DataFrame([{'fa': settings['A'], 'fb': settings['B']}])
    prediction = reference.get_prediction(point).summary_frame(alpha=0.10).iloc[0]
    assert result['model']['rank'] == np.linalg.matrix_rank(reference.model.exog)
    assert result['model']['df'] == reference.df_resid
    assert result['model']['sse'] == pytest.approx(reference.ssr, abs=1e-12)
    assert result['predicted_mean'] == pytest.approx(prediction['mean'], abs=1e-11)
    assert result['mean_ci']['ci_low'] == pytest.approx(prediction['mean_ci_lower'], abs=1e-10)
    assert result['mean_ci']['ci_high'] == pytest.approx(prediction['mean_ci_upper'], abs=1e-10)
    assert result['search']['candidate_count'] == 9
    assert '不校正' in result['assumption']

    specified = {'A': 'high', 'B': 'low'}
    predicted = predict_taguchi_model(frame, metadata, 'Y', specified,
                                      terms=terms, confidence=0.99)
    point = pd.DataFrame([{'fa': 'high', 'fb': 'low'}])
    interval = reference.get_prediction(point).summary_frame(alpha=0.01).iloc[0]
    assert predicted['prediction'] == pytest.approx(interval['mean'], abs=1e-11)
    assert predicted['intervals']['ci_low'] == pytest.approx(
        interval['mean_ci_lower'], abs=1e-10)
    assert predicted['intervals']['ci_high'] == pytest.approx(
        interval['mean_ci_upper'], abs=1e-10)

    shifted = frame.copy(deep=True)
    shifted['响应_Y'] += 1e9
    shifted_result = best_settings(
        shifted, metadata, 'Y', 'mean', target=1e9 + 54,
        model_terms=terms, confidence=0.90)
    assert shifted_result['mean_ci']['status'] == '可用'
    assert shifted_result['best'] == result['best']
    assert (shifted_result['mean_ci']['ci_high'] - shifted_result['mean_ci']['ci_low']) \
        == pytest.approx(result['mean_ci']['ci_high'] - result['mean_ci']['ci_low'],
                         rel=1e-6, abs=1e-7)


def test_taguchi_interaction_aliased_with_main_effect_is_rejected():
    spec = DesignSpec(
        'TG', tuple(factor(key, ('low', 'high')) for key in 'ABC'), ('Y',),
        seed=4, design_type='taguchi',
        taguchi={'kind': 'static', 'array_id': 'L4(2^3)',
                 'matrix_sha256': ARRAYS['L4(2^3)'].sha256,
                 'columns': {'A': 1, 'B': 2, 'C': 3},
                 'noise_array_id': None, 'noise_matrix_sha256': None,
                 'noise_columns': {}, 'signal_factor': None})
    frame, metadata = create_taguchi(spec)
    frame['响应_Y'] = [1.0, 2.0, 3.0, 5.0]
    with pytest.raises(ValueError, match='混杂或不可估计'):
        predict_taguchi_model(
            frame, metadata, 'Y', {'A': 'low', 'B': 'high', 'C': 'low'},
            terms=(('A',), ('B',), ('C',), ('A', 'B')))


def test_saturated_taguchi_main_effect_model_marks_mean_ci_unavailable():
    spec = DesignSpec(
        'TG', tuple(factor(key, ('low', 'high')) for key in 'ABC'), ('Y',),
        seed=5, design_type='taguchi',
        taguchi={'kind': 'static', 'array_id': 'L4(2^3)',
                 'matrix_sha256': ARRAYS['L4(2^3)'].sha256,
                 'columns': {'A': 1, 'B': 2, 'C': 3},
                 'noise_array_id': None, 'noise_matrix_sha256': None,
                 'noise_columns': {}, 'signal_factor': None})
    frame, metadata = create_taguchi(spec)
    frame['响应_Y'] = [4.0, 5.0, 8.0, 10.0]
    result = best_settings(frame, metadata, 'Y', 'sn')
    assert result['model']['rank'] == 4
    assert result['model']['df'] == 0
    assert result['mean_ci']['status'] == '不可用'
    assert '残差自由度' in result['mean_ci']['reason']


def inner_outer_data(control_count=2, noise_count=2):
    controls = 'ABC'[:control_count]
    noises = ('N1', 'N2', 'N3')[:noise_count]
    spec = DesignSpec(
        'TG', tuple(factor(key, ('low', 'high')) for key in (*controls, *noises)),
        ('Y',), seed=9, design_type='taguchi',
        taguchi={'kind': 'static', 'array_id': 'L4(2^3)',
                 'matrix_sha256': ARRAYS['L4(2^3)'].sha256,
                 'columns': {key: index + 1 for index, key in enumerate(controls)},
                 'noise_array_id': 'L4(2^3)',
                 'noise_matrix_sha256': ARRAYS['L4(2^3)'].sha256,
                 'noise_columns': {key: index + 1 for index, key in enumerate(noises)},
                 'signal_factor': None})
    return create_taguchi(spec)


def binary_code(run, factor_id):
    return -1 if run.settings[factor_id] == 'low' else 1


def test_noise_response_model_matches_independent_ols_and_equal_condition_search():
    frame, metadata = inner_outer_data()
    design = restore_design_result(frame, metadata)
    values, matrix = {}, []
    for run in sorted(design.runs, key=lambda item: item.standard_order):
        a, b, n1, n2 = (binary_code(run, key) for key in ('A', 'B', 'N1', 'N2'))
        row = [1, a, b, n1, n2, a*n1, b*n2]
        matrix.append(row)
        values[run.run_id] = 30 + 2*a - 3*b + 4*n1 + 5*n2 + 6*a*n1 - 2*b*n2 \
            + 1.25*a*b*n1
    frame['响应_Y'] = [values[run_id] for run_id in frame['运行ID']]
    ordered_runs = sorted(design.runs, key=lambda item: item.standard_order)
    y = np.asarray([values[run.run_id] for run in ordered_runs])
    reference = sm.OLS(y, np.asarray(matrix, dtype=float)).fit()
    result = noise_response_model(
        frame, metadata, 'Y', interactions=(('A', 'N1'), ('B', 'N2')))
    assert result['estimable'] is True
    assert result['rank'] == np.linalg.matrix_rank(matrix)
    assert result['residual_df'] == reference.df_resid
    assert result['sse'] == pytest.approx(reference.ssr, abs=1e-11)
    np.testing.assert_allclose(list(result['coefficients'].values()), reference.params, atol=1e-11)
    np.testing.assert_allclose([row['residual'] for row in result['residuals']],
                               reference.resid, atol=1e-11)
    assert result['inference'][0]['se'] == pytest.approx(reference.bse[0], abs=1e-11)
    assert len(result['candidates']) == 4

    ref_candidates = []
    for a, b in product((-1, 1), repeat=2):
        predictions = [float(np.asarray([1, a, b, n1, n2, a*n1, b*n2]) @ reference.params)
                       for n1, n2 in product((-1, 1), repeat=2)]
        mean = sum(predictions) / 4
        variance = sum((value - mean) ** 2 for value in predictions) / 4
        sd = (variance + reference.mse_resid) ** 0.5
        levels = {'A': 'high' if a == 1 else 'low', 'B': 'high' if b == 1 else 'low'}
        ref_candidates.append((levels, mean, sd))
    for candidate in result['candidates']:
        reference_candidate = next(row for row in ref_candidates
                                   if row[0] == candidate['settings'])
        assert candidate['predicted_mean'] == pytest.approx(reference_candidate[1], abs=1e-11)
        assert candidate['predicted_sd'] == pytest.approx(reference_candidate[2], abs=1e-11)
        assert candidate['predicted_variance'] == pytest.approx(
            candidate['noise_variance'] + reference.mse_resid, abs=1e-11)
    best_sd = min(row[2] for row in ref_candidates)
    assert result['candidates'][0]['settings'] in [row[0] for row in ref_candidates]
    assert result['best'] in [row[0] for row in ref_candidates if row[2] == pytest.approx(best_sd)]

    shifted = frame.copy(deep=True)
    shifted['响应_Y'] += 1e9
    shifted_result = noise_response_model(
        shifted, metadata, 'Y', interactions=(('A', 'N1'), ('B', 'N2')))
    assert shifted_result['inference'] is not None
    assert shifted_result['sse'] == pytest.approx(result['sse'], rel=1e-5, abs=1e-5)
    np.testing.assert_allclose(
        [row['predicted_sd'] for row in shifted_result['candidates']],
        [row['predicted_sd'] for row in result['candidates']], rtol=1e-6, atol=1e-7)

    constrained = noise_response_model(
        frame, metadata, 'Y', interactions=(('A', 'N1'), ('B', 'N2')),
        target_mean=30, target_tolerance=1)
    eligible = [row for row in constrained['candidates']
                if abs(row['target_deviation']) <= 1]
    assert constrained['best'] in [row['settings'] for row in eligible]
    assert constrained['search']['eligible_count'] == len(eligible)


def test_noise_response_model_does_not_recommend_saturated_fit():
    frame, metadata = inner_outer_data(control_count=3, noise_count=3)
    frame['响应_Y'] = np.arange(1, len(frame) + 1, dtype=float)
    interactions = tuple((control, noise) for control in 'ABC'
                         for noise in ('N1', 'N2', 'N3'))
    result = noise_response_model(frame, metadata, 'Y', interactions=interactions)
    assert result['estimable'] is True
    assert result['rank'] == result['parameter_count'] == 16
    assert result['residual_df'] == 0
    assert result['best'] is None
    assert result['search']['stop_reason'] == 'no_estimable_error_variance'


def test_confirmation_plan_preserves_original_trials_and_crosses_noise_conditions():
    frame, metadata = inner_outer_data()
    design = restore_design_result(frame, metadata)
    values = {run.run_id: 20 + binary_code(run, 'A') + 2*binary_code(run, 'B')
              + binary_code(run, 'N1') for run in design.runs}
    frame['响应_Y'] = [values[run_id] for run_id in frame['运行ID']]
    original = frame.copy(deep=True)
    result = best_settings(frame, metadata, 'Y', 'mean', target=20)
    plan = create_confirmation_frame(frame, metadata, result, '原始 Taguchi')
    additions = plan.iloc[len(frame):]
    pd.testing.assert_frame_equal(
        plan.loc[:len(frame)-1, frame.columns].reset_index(drop=True),
        original.reset_index(drop=True), check_dtype=False)
    assert plan['响应_Y'].dtype == 'Int64'
    assert len(additions) == 4
    assert set(additions['点类型']) == {'confirmation'}
    assert set(additions['设定_A']) == {result['best']['A']}
    assert set(additions['设定_B']) == {result['best']['B']}
    assert set(additions['设定_N1']) == {'low', 'high'}
    assert set(additions['设定_N2']) == {'low', 'high'}
    assert set(additions['控制运行']) == {'CONF00001'}
    assert additions['响应_Y'].isna().all()
    assert list(additions['标准序']) == list(range(len(frame) + 1, len(frame) + 5))
    assert set(plan['DOE 来源设计ID']) == {'TG'}
    assert set(plan['DOE 来源工作表']) == {'原始 Taguchi'}
    assert set(additions['DOE 试验类型']) == {'确认试验'}
    changed = frame.copy(deep=True)
    changed.loc[0, '响应_Y'] += 1
    with pytest.raises(ValueError, match='来源试验数据已更改'):
        create_confirmation_frame(changed, metadata, result, '原始 Taguchi')

