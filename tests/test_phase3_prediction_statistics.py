import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from advanced_regression import fit_regression
from one_way_ANOVA import one_way_anova
from two_way_anova import two_way_anova
from utilities import prediction_statistics


@pytest.mark.parametrize('case_id,display', [
    ('ols_multiple', 99.60), ('ols_categorical', 82.71),
    ('one_way_anova', 71.64), ('two_way_anova', 76.12),
    ('two_way_additive', None),
])
def test_press_against_deleted_row_fits(case_id, display):
    source = Path(__file__).resolve().parents[1] / 'Out/statistics_minitab19_parity/phase4/case_inputs.json'
    cases = json.loads(source.read_text(encoding='utf-8'))['cases']
    if case_id.startswith('ols'):
        case = cases[case_id]
        categorical = case.get('categorical', [])
        columns = categorical or case['terms']
        y = case['y']
        x = (np.asarray(case['group'])[:, None] == ['B', 'C']) if categorical else [case[c] for c in columns]
        if not categorical:
            x = np.transpose(x)
        summary = fit_regression(pd.DataFrame({c: case[c] for c in ['y', *columns]}),
                                 'y', columns, categorical=categorical).tables['summary'].iloc[0]
    elif case_id == 'one_way_anova':
        groups = cases[case_id]['groups']
        y = [value for group in groups.values() for value in group]
        labels = np.repeat(list(groups), [len(group) for group in groups.values()])
        x = labels[:, None] == ['B', 'C']
        lines = []
        summary = one_way_anova(list(groups.values()), list(groups), print_out=True, print_port=lines.append)
    else:
        case = cases['two_way_anova']
        y, a, b = (case[c] for c in ('response', 'factor_a', 'factor_b'))
        a_dummy, b_dummy = np.array(a) == 'B', np.array(b) == 'Y'
        interaction = case_id == 'two_way_anova'
        columns = [a_dummy, b_dummy]
        if interaction:
            columns.append(a_dummy & b_dummy)
        x = np.column_stack(columns)
        lines = []
        summary = two_way_anova(y, a, factor_listB=b, interaction=interaction,
                                print_out=True, print_port=lines.append)
    y = np.asarray(y)
    x = np.column_stack([np.ones(len(y)), x])
    press = 0.
    for i in range(len(y)):
        keep = np.arange(len(y)) != i
        params, _, rank, _ = np.linalg.lstsq(x[keep], y[keep], rcond=None)
        assert rank == x.shape[1]
        press += (y[i] - x[i] @ params)**2
    prediction_r2 = 1 - press / np.sum((y-y.mean())**2)
    assert summary['press'] == pytest.approx(press)
    assert summary['pred_r_squared'] == pytest.approx(prediction_r2)
    if display is not None:
        assert prediction_r2 * 100 == pytest.approx(display, abs=.005)
    if not case_id.startswith('ols'):
        assert any('PRESS' in line and '预测 R²' in line for line in lines)


def test_ols_prediction_statistics_boundaries():
    single = pd.DataFrame({'g': ['a', 'a', 'b', 'b', 'c'], 'y': [1, 2, 3, 4, 5]})
    summary = fit_regression(single, 'y', ['g'], categorical=['g']).tables['summary'].iloc[0]
    assert np.isnan(summary['press']) and np.isnan(summary['pred_r_squared'])

    noisy = pd.DataFrame({'x': [0, 1, 2, 3, 4], 'y': [0, 1, 0, 1, 0]})
    summary = fit_regression(noisy, 'y', ['x']).tables['summary'].iloc[0]
    assert summary['pred_r_squared'] < 0
    noisy['y'] = 2
    with pytest.raises(ValueError, match='常量'):
        fit_regression(noisy, 'y', ['x'])
    assert np.isnan(prediction_statistics([0, 0], [.5, .5], 0)[1])
