"""PB 点集与 NIST 参考比较，参考不调用生成器。"""
from pathlib import Path
from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from doe_core import DesignSpec, FactorSpec, restore_design_result, screening_matrix_sha256
from doe_pb import create_pb, validate_pb
from scipy.linalg import hadamard


def pb_spec(n, factors=3, seed=7):
    mathematical = n in (32, 40, 44, 48)
    identity = {'construction_id': f'pb{n}.v1',
                'source_kind': 'mathematical_construction' if mathematical else 'publication',
                'source_id': f'{"hadamard" if mathematical else "nist"}.pb{n}', 'matrix_sha256': '0' * 64}
    return DesignSpec('pb', tuple(FactorSpec(f'F{i}', f'F{i}', -1, 1)
                                  for i in range(1, factors + 1)), ('Y',), seed=seed,
                      design_type='plackett_burman', screening_matrix=identity)


@pytest.mark.parametrize('n', [12, 20, 24, 28, 36])
def test_nist_standard_matrix_and_repeated_seeded_run_order(n):
    spec = pb_spec(n, n - 1)
    frame, metadata = create_pb(spec, n, replicates=2)
    expected = pd.read_csv(Path(__file__).parent / f'fixtures/doe_screening_reference/pb/pb{n}.csv')
    for rep in (1, 2):
        actual = frame[frame['重复'] == rep].sort_values('标准序')
        matrix = actual[[f'设定_F{i}' for i in range(1, n)]].to_numpy(dtype=int)
        np.testing.assert_array_equal(matrix, expected.iloc[:, 1:].to_numpy())
        np.testing.assert_array_equal(matrix.T @ matrix, n * np.eye(n - 1, dtype=int))
        np.testing.assert_array_equal(matrix.sum(axis=0), np.zeros(n - 1, dtype=int))
    assert frame['运行ID'].tolist() == create_pb(spec, n, replicates=2)[0]['运行ID'].tolist()
    assert frame['运行ID'].tolist() != create_pb(pb_spec(n, n - 1, seed=8), n, replicates=2)[0]['运行ID'].tolist()
    validate_pb(restore_design_result(frame, metadata))


@pytest.mark.parametrize('n,reps', [(12.0, 1), (16, 1), (12, 0), (12, True), (12, 1000)])
def test_invalid_settings_rejected(n, reps):
    with pytest.raises(ValueError):
        create_pb(pb_spec(12), n, reps)


@pytest.mark.parametrize('n', [32, 40, 44, 48])
def test_hadamard_construction_and_seeded_recovery(n):
    if n == 32:
        reference = hadamard(32)[:, 1:]
    elif n == 40:
        base = pd.read_csv(Path(__file__).parent / 'fixtures/doe_screening_reference/pb/pb20.csv').iloc[:, 1:].to_numpy()
        reference = np.kron(hadamard(2), np.column_stack((np.ones(20, dtype=int), base)))[:, 1:]
    else:
        q = n - 1
        character = lambda v: 0 if v % q == 0 else (1 if pow(v % q, (q - 1) // 2, q) == 1 else -1)
        core = np.array([[character(i - j) - int(i == j) for j in range(q)] for i in range(q)])
        reference = np.vstack((np.ones(q, dtype=int), core))
    frame, metadata = create_pb(pb_spec(n, n - 1), n, replicates=2)
    for rep in (1, 2):
        actual = frame[frame['重复'] == rep].sort_values('标准序')
        x = actual[[f'设定_F{i}' for i in range(1, n)]].to_numpy(dtype=int)
        np.testing.assert_array_equal(x, reference)
        np.testing.assert_array_equal(x.T @ x, n * np.eye(n - 1, dtype=int))
        np.testing.assert_array_equal(x.sum(axis=0), np.zeros(n - 1, dtype=int))
        assert np.linalg.matrix_rank(np.column_stack((np.ones(n), x))) == n
        expected = {32: (2, 32), 40: (2, -8), 44: (5, 12), 48: (3, 8)}
        k, dot = expected[n]
        assert x[:, 0] @ (x[:, 1] * x[:, k]) == dot
    assert frame['运行ID'].tolist() == create_pb(pb_spec(n, n - 1), n, 2)[0]['运行ID'].tolist()
    assert frame['运行ID'].tolist() != create_pb(pb_spec(n, n - 1, seed=8), n, 2)[0]['运行ID'].tolist()
    validate_pb(restore_design_result(frame, metadata))
    short, _ = create_pb(pb_spec(n, 3), n)
    x_short = short.sort_values('标准序')[[f'设定_F{i}' for i in range(1, 4)]].to_numpy(dtype=int)
    np.testing.assert_array_equal(x_short, reference[:, :3])


def test_screening_measured_values_and_response_may_be_entered_later():
    frame, metadata = create_pb(pb_spec(12), 12, measured=True)
    frame.loc[0, '实测_F1'] = 0.25
    frame.loc[0, '响应_Y'] = 7.5
    result = restore_design_result(frame, metadata)
    assert result.runs[0].measured_levels['F1'] == 0.25
    assert result.runs[0].responses['Y'] == 7.5


def test_centers_blocks_and_limit_restore():
    frame, metadata = create_pb(pb_spec(12), 12, replicates=2, center_points=2, block_replicates=True)
    assert len(frame) == 28 and frame['区组'].tolist() == [1] * 14 + [2] * 14
    for block in (1, 2):
        rows = frame[frame['区组'] == block].sort_values('标准序')
        assert rows['重复'].tolist() == [block] * 14
        assert rows['点类型'].tolist() == ['factorial'] * 12 + ['center'] * 2
        assert rows.iloc[-2:][['设定_F1', '设定_F2', '设定_F3']].to_numpy().tolist() == [[0, 0, 0], [0, 0, 0]]
    assert metadata['design']['block_count'] == 2
    validate_pb(restore_design_result(frame, metadata))
    assert frame['运行ID'].tolist() == create_pb(pb_spec(12), 12, 2, center_points=2, block_replicates=True)[0]['运行ID'].tolist()
    result = restore_design_result(frame, metadata)
    bad_runs = list(result.runs)
    bad_runs[0] = replace(bad_runs[0], block=2)
    bad = replace(result, runs=tuple(bad_runs))
    identity = dict(bad.spec.screening_matrix)
    identity['matrix_sha256'] = screening_matrix_sha256(bad)
    bad = replace(bad, spec=replace(bad.spec, screening_matrix=identity))
    with pytest.raises(ValueError, match='区组'):
        validate_pb(bad)
    for kwargs in ({'center_points': -1}, {'center_points': True}, {'block_replicates': 1},
                   {'center_points': 5000, 'replicates': 2}):
        with pytest.raises(ValueError):
            create_pb(pb_spec(12), 12, **kwargs)


def test_text_factors_expand_each_center_combination_and_check_limit():
    factors = (FactorSpec('F1', '温度', -1, 1),
               FactorSpec('F2', '类型', None, None, factor_type='categorical', levels=('甲', '乙')),
               FactorSpec('F3', '开关', None, None, factor_type='categorical', levels=('关', '开')))
    spec = replace(pb_spec(12), factors=factors)
    frame, metadata = create_pb(spec, 12, 2, measured=True, center_points=2, block_replicates=True)
    assert len(frame) == 40
    assert '实测_F1' in frame and '实测_F2' not in frame
    for rep in (1, 2):
        centers = frame[(frame['重复'] == rep) & (frame['点类型'] == 'pseudo_center')]
        assert len(centers) == 8 and set(centers['设定_F1']) == {0}
        assert centers.groupby(['设定_F2', '设定_F3']).size().to_dict() == {
            ('甲', '关'): 2, ('甲', '开'): 2, ('乙', '关'): 2, ('乙', '开'): 2}
        assert set(centers['区组']) == {rep}
    validate_pb(restore_design_result(frame, metadata))
    all_text = replace(spec, factors=tuple(FactorSpec(f'F{i}', f'F{i}', None, None,
                       factor_type='categorical', levels=('a', 'b')) for i in range(1, 4)))
    with pytest.raises(ValueError, match='全部因子'):
        create_pb(all_text, 12, center_points=1)
    many = replace(pb_spec(20, 15), factors=(FactorSpec('F1', 'F1', -1, 1),) + tuple(
        FactorSpec(f'F{i}', f'F{i}', None, None, factor_type='categorical', levels=('a', 'b'))
        for i in range(2, 16)))
    with pytest.raises(ValueError, match='10000'):
        create_pb(many, 20, center_points=1)
