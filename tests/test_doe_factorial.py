import itertools
import random

import numpy as np
import pytest

from doe_core import DesignSpec, FactorSpec, restore_design_result
from doe_factorial import create_factorial


def spec(k=2, seed=12, low=0, high=2):
    return DesignSpec('full', tuple(FactorSpec(chr(65+i), f'因子{i}', low, high)
                                    for i in range(k)), ('响应',), seed=seed,
                      design_type='two_level_full')


@pytest.mark.parametrize('k', [2, 3, 6])
def test_combinations_orthogonality_and_doe_contract(k):
    design = spec(k)
    frame, metadata = create_factorial(design, replicates=2, center_points=2)
    restored = restore_design_result(frame, metadata)
    factorial = [run for run in restored.runs if run.point_type == 'factorial']
    levels = [tuple(int(f.to_coded(r.settings[f.factor_id])) for f in design.factors)
              for r in factorial]
    assert sorted(levels) == sorted(list(itertools.product((-1, 1), repeat=k)) * 2)
    matrix = np.column_stack((np.ones(len(levels)), np.array(levels)))
    np.testing.assert_array_equal(matrix.T @ matrix, len(levels) * np.eye(k + 1))
    assert all(r.settings == {f.factor_id: 1 for f in design.factors}
               for r in restored.runs if r.point_type == 'center')
    assert {r.standard_order for r in restored.runs} == set(range(1, len(frame) + 1))
    assert {r.run_order for r in restored.runs} == set(range(1, len(frame) + 1))


def test_seed_is_local_and_responses_are_mutable():
    state = random.getstate()
    frame, metadata = create_factorial(spec())
    same, _ = create_factorial(spec())
    other, _ = create_factorial(spec(seed=13))
    assert random.getstate() == state
    assert frame['运行ID'].tolist() == same['运行ID'].tolist()
    assert frame['运行ID'].tolist() != other['运行ID'].tolist()
    frame['响应_响应'] = [1, 2, 3, 4]
    assert restore_design_result(frame, metadata).runs[0].responses['响应'] == 1
    frame.loc[0, '设定_A'] = 999
    with pytest.raises(ValueError):
        restore_design_result(frame, metadata)


def test_exact_integer_and_unrepresentable_center():
    low = 2**60 + 1
    frame, metadata = create_factorial(spec(low=low, high=low+2), center_points=1)
    assert {r.settings['A'] for r in restore_design_result(frame, metadata).runs} == {
        low, low+1, low+2}
    with pytest.raises(ValueError, match='无损'):
        create_factorial(spec(low=low, high=low+1), center_points=1)


@pytest.mark.parametrize('kwargs', [dict(replicates=0), dict(center_points=-1),
                                    dict(replicates=3000), dict(measured=1)])
def test_bad_parameters_rejected(kwargs):
    with pytest.raises(ValueError):
        create_factorial(spec(), **kwargs)
