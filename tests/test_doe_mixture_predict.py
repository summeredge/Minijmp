import numpy as np
import pytest

from doe_mixture import MixtureSpec, mixture_metadata
from doe_mixture_analysis import analyze_mixture
from doe_mixture_constraints import ComponentSpec, VariableSpec
from doe_mixture_designs import create_mixture_design
from doe_mixture_predict import predict_mixture


def linear_design():
    spec = MixtureSpec('MIX', (ComponentSpec('A', 'A'), ComponentSpec('B', 'B'),
                               ComponentSpec('C', 'C')), ('Y',), 'simplex_lattice',
                       3, seed=1)
    frame, meta = create_mixture_design(spec)
    frame['响应_Y'] = 2 * frame['设定_A'] + 5 * frame['设定_B'] + 3 * frame['设定_C']
    return frame, mixture_metadata(frame, spec)


def test_prediction_matches_analytic_model():
    frame, meta = linear_design()
    result = predict_mixture(frame, meta, 'Y', [0.2, 0.3, 0.5])
    assert result['prediction'] == pytest.approx(3.4)
    assert result['model_range'] == {'A': [0, 1], 'B': [0, 1], 'C': [0, 1]}
    assert result['snapshot_id']


@pytest.mark.parametrize('proportions, message', [
    ([0.2, 0.3, 0.4], '之和'),
    ([1.2, -0.1, -0.1], '0 到 1'),
    ([0.5, 0.5, 0.0], None),
])
def test_invalid_proportions_are_rejected(proportions, message):
    frame, meta = linear_design()
    if message is None:
        assert predict_mixture(frame, meta, 'Y', proportions)['prediction'] == pytest.approx(3.5)
        return
    with pytest.raises(ValueError, match=message):
        predict_mixture(frame, meta, 'Y', proportions)


def test_nonfinite_and_out_of_range_inputs_are_rejected():
    frame, meta = linear_design()
    with pytest.raises(ValueError):
        predict_mixture(frame, meta, 'Y', [float('nan'), 0.5, 0.5])
    changed = frame.copy()
    changed.loc[0, '设定_A'] = 0.5
    changed.loc[0, '设定_B'] = 0.5
    with pytest.raises(ValueError):
        predict_mixture(changed, meta, 'Y', [0.2, 0.3, 0.5])


def test_process_variable_prediction():
    spec = MixtureSpec('MIX', (ComponentSpec('A', 'A'), ComponentSpec('B', 'B'),
                               ComponentSpec('C', 'C')), ('Y',), 'simplex_centroid',
                       None, process_variables=(VariableSpec('P', '温度', 20, 40, 'C'),),
                       seed=2)
    frame, _ = create_mixture_design(spec)
    assert set(frame['设定_P']) == {20, 40}
    z = (frame['设定_P'] - 30) / 10
    frame['响应_Y'] = (2 * frame['设定_A'] + frame['设定_B'] + 3 * frame['设定_C']
                       + 1.5 * frame['设定_A'] * z + 0.5 * z)
    meta = mixture_metadata(frame, spec)
    analysis = analyze_mixture(frame, meta, 'Y', degree=1)
    assert analysis['rank'] == analysis['p'] == 6
    np.testing.assert_allclose(analysis['coefficients'], [2, 1, 3, 2, 0.5, 0.5],
                               rtol=0, atol=1e-9)
    alias = analyze_mixture(frame, meta, 'Y', degree=1,
                            terms=['A', 'B', 'C', 'P', 'A*P', 'B*P', 'C*P'])
    assert alias['rank'] < alias['p'] and alias['inference'] is None
    result = predict_mixture(frame, meta, 'Y', [0.5, 0.3, 0.2], process={'P': 40})
    assert result['prediction'] == pytest.approx(3.15, abs=1e-9)
    with pytest.raises(ValueError, match='过程变量'):
        predict_mixture(frame, meta, 'Y', [0.5, 0.3, 0.2])
    with pytest.raises(ValueError):
        predict_mixture(frame, meta, 'Y', [0.5, 0.3, 0.2], process={'P': 50})


def test_amount_variable_defaults_and_units():
    spec = MixtureSpec('MIX', (ComponentSpec('A', 'A'), ComponentSpec('B', 'B'),
                               ComponentSpec('C', 'C')), ('Y',), 'simplex_lattice',
                       3, amount_variables=(VariableSpec('T', '总量', 100, 300, 'g', 'amount'),),
                       amount_settings=(('T', 250),), seed=3)
    frame, _ = create_mixture_design(spec)
    frame['响应_Y'] = (2 * frame['设定_A'] + 4 * frame['设定_B'] + 6 * frame['设定_C']
                       + 8 * frame['设定_A'] * frame['设定_B']
                       + 2 * frame['设定_A'] * frame['设定_C']
                       - 3 * frame['设定_B'] * frame['设定_C'])
    meta = mixture_metadata(frame, spec)
    result = predict_mixture(frame, meta, 'Y', [0.2, 0.3, 0.5])
    assert result['prediction'] == pytest.approx(2 * .2 + 4 * .3 + 6 * .5 + 8 * .06
                                                 + 2 * .1 - 3 * .15)
    assert result['settings']['T'] == 250
    analysis = analyze_mixture(frame, meta, 'Y', degree=2)
    assert analysis['rank'] == analysis['p']
