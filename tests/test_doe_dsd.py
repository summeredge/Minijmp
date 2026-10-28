"""DSD 固定点阵、重复与实际水平的独立参考。"""
from pathlib import Path
from fractions import Fraction
from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from doe_core import DesignSpec, FactorSpec, restore_design_result, screening_matrix_sha256
from doe_dsd import create_dsd, validate_dsd


CASES = [('dsd6', 6, False, 'dsd_06_cont_13.csv'),
         ('dsd7', 7, False, 'dsd_07_cont_17.csv'),
         ('dsd8', 8, False, 'dsd_08_cont_17.csv'),
         ('dsd10', 10, False, 'dsd_10_cont_21.csv'),
         ('dsd4c1', 5, True, 'dsd_04_cont_01_cat_14.csv')]


def dsd_spec(key, count, mixed=False):
    factors = tuple(FactorSpec(f'F{i}', f'F{i}', 0.1, 0.3)
                    for i in range(1, count + (0 if mixed else 1)))
    if mixed:
        factors += (FactorSpec(f'F{count}', f'F{count}', None, None,
                               factor_type='categorical', levels=('甲', '乙')),)
    identity = {'construction_id': key + '.v1', 'source_kind': 'mathematical_construction',
                'source_id': ('jones.' if mixed else 'conference.') + key, 'matrix_sha256': '0' * 64}
    return DesignSpec('dsd', factors, ('Y',), seed=7,
                      design_type='definitive_screening', screening_matrix=identity)


@pytest.mark.parametrize('key,count,mixed,filename', CASES)
def test_dsd_against_fixed_reference_and_roundtrip(key, count, mixed, filename):
    spec = dsd_spec(key, count, mixed)
    frame, metadata = create_dsd(spec, replicates=2)
    expected = pd.read_csv(Path(__file__).parent / 'fixtures/doe_screening_reference/dsd' / filename)
    for rep in (1, 2):
        actual = frame[frame['重复'] == rep].sort_values('标准序')
        def independent_code(factor, value):
            if factor.factor_type == 'categorical':
                return {'甲': -1, '乙': 1}[value]
            return {factor.low: -1, float((Fraction(factor.low) + Fraction(factor.high)) / 2): 0,
                    factor.high: 1}[value]
        matrix = np.array([[independent_code(factor, row[f'设定_{factor.factor_id}'])
                            for factor in spec.factors] for _, row in actual.iterrows()])
        np.testing.assert_array_equal(matrix, expected.iloc[:, 1:].to_numpy())
    result = restore_design_result(frame, metadata)
    validate_dsd(result)
    assert frame['运行ID'].tolist() == create_dsd(spec, replicates=2)[0]['运行ID'].tolist()
    assert sum(run.point_type == ('pseudo_center' if mixed else 'center') for run in result.runs) == (4 if mixed else 2)


def test_invalid_dsd_configuration_rejected():
    spec = dsd_spec('dsd6', 6)
    for reps in (0, True, 2000):
        with pytest.raises(ValueError):
            create_dsd(spec, reps)


@pytest.mark.parametrize('count,mixed', [(k, False) for k in (2, 3, 4, 5, 9)] +
                         [(k + 1, True) for k in (1, 2, 3, 5)])
def test_dsd_column_subset_and_single_category(count, mixed):
    continuous = count - int(mixed)
    key = f'dsd{continuous}c1' if mixed else f'dsd{count}'
    source = 'dsd_06_cont_13.csv' if count <= 6 else 'dsd_10_cont_21.csv'
    reference = pd.read_csv(Path(__file__).parent / 'fixtures/doe_screening_reference/dsd' / source).iloc[:, 1:count + 1].to_numpy()
    if mixed:
        reference = reference[:-1].copy()
        zeros = np.flatnonzero(reference[:, -1] == 0)
        reference[zeros, -1] = [1, -1]
        reference = np.vstack((reference, [0]*continuous + [1], [0]*continuous + [-1]))
    spec = dsd_spec(key, count, mixed)
    frame, metadata = create_dsd(spec, replicates=2)
    for rep in (1, 2):
        rows = frame[frame['重复'] == rep].sort_values('标准序')
        x = np.empty((len(rows), count), dtype=int)
        for i, factor in enumerate(spec.factors):
            values = rows[f'设定_{factor.factor_id}']
            mapping = ({'甲': -1, '乙': 1} if factor.factor_type == 'categorical' else
                       {factor.low: -1, float((Fraction(factor.low) + Fraction(factor.high))/2): 0, factor.high: 1})
            x[:, i] = [mapping[v] for v in values]
        np.testing.assert_array_equal(x, reference)
        main = np.column_stack((np.ones(len(x)), x))
        assert np.linalg.matrix_rank(main) == count + 1
        squares = x[:, :continuous] ** 2
        assert np.linalg.matrix_rank(np.column_stack((main, squares))) == count + 1 + continuous
        second = [x[:, i] * x[:, j] for i in range(count) for j in range(i, count)
                  if i != j or i < continuous]
        np.testing.assert_array_equal(x.T @ np.column_stack(second), 0)
        assert set(np.unique(x[:, -1])) == ({-1, 1} if mixed else {-1, 0, 1})
    validate_dsd(restore_design_result(frame, metadata))
    assert frame['运行ID'].tolist() == create_dsd(spec, 2)[0]['运行ID'].tolist()


@pytest.mark.parametrize('count', range(11, 49))
@pytest.mark.parametrize('mixed', [False, True])
def test_large_conference_designs_properties(count, mixed):
    continuous = count - int(mixed)
    key = f'dsd{continuous}c1' if mixed else f'dsd{count}'
    spec = dsd_spec(key, count, mixed)
    frame, metadata = create_dsd(spec, replicates=2)
    expected_runs = next(runs for upper, runs in ((12, 25), (14, 29), (16, 33), (18, 37),
                                                   (20, 41), (24, 49), (26, 53), (30, 61),
                                                   (32, 65), (38, 77), (42, 85), (44, 89), (48, 97))
                         if count <= upper) + int(mixed)
    for rep in (1, 2):
        rows = frame[frame['重复'] == rep].sort_values('标准序')
        assert len(rows) == expected_runs
        x = np.empty((len(rows), count), dtype=int)
        for i, factor in enumerate(spec.factors):
            mapping = ({'甲': -1, '乙': 1} if factor.factor_type == 'categorical' else
                       {factor.low: -1, float((Fraction(factor.low) + Fraction(factor.high))/2): 0, factor.high: 1})
            x[:, i] = [mapping[v] for v in rows[f'设定_{factor.factor_id}']]
        main = np.column_stack((np.ones(len(x), dtype=int), x))
        assert np.linalg.matrix_rank(main) == 1 + count
        assert np.linalg.matrix_rank(np.column_stack((main, x[:, :continuous] ** 2))) == 1 + count + continuous
        np.testing.assert_array_equal(x.sum(axis=0), 0)
        second = np.column_stack([x[:, i]*x[:, j] for i in range(count) for j in range(i, count)
                                  if i != j or i < continuous])
        np.testing.assert_array_equal(x.T @ second, 0)
        conference_order = (expected_runs - int(mixed) - 1) // 2
        assert np.linalg.matrix_rank(np.column_stack((main, second))) == 1 + conference_order + count
        assert all(set(x[:, i]) == {-1, 0, 1} for i in range(continuous))
        if mixed:
            assert set(x[:, -1]) == {-1, 1}
            assert (rows['点类型'] == 'pseudo_center').sum() == 2
        else:
            assert (rows['点类型'] == 'center').sum() == 1
            np.testing.assert_array_equal(x.T @ x, (expected_runs-3) * np.eye(count, dtype=int))
    validate_dsd(restore_design_result(frame, metadata))
    assert frame['运行ID'].tolist() == create_dsd(spec, 2)[0]['运行ID'].tolist()


def test_two_category_foldover_is_independently_estimable():
    factors = tuple(FactorSpec(f'F{i}', f'F{i}', -1, 1) for i in range(1, 5)) + (
        FactorSpec('F5', 'F5', None, None, factor_type='categorical', levels=('甲', '乙')),
        FactorSpec('F6', 'F6', None, None, factor_type='categorical', levels=('低', '高')))
    identity = {'construction_id': 'dsd4c2.v1', 'source_kind': 'mathematical_construction',
                'source_id': 'foldover.dsd4c2', 'matrix_sha256': '0' * 64}
    spec = DesignSpec('dsd', factors, ('Y',), seed=7, design_type='definitive_screening', screening_matrix=identity)
    base = pd.read_csv(Path(__file__).parent / 'fixtures/doe_screening_reference/dsd/dsd_06_cont_13.csv').iloc[:12, 1:].to_numpy()
    # 替换每分类列的反向零点对，再添加互为反向的两个伪中心。
    for column in (4, 5):
        zeros = np.flatnonzero(base[:, column] == 0)
        base[zeros, column] = (1, -1)
    reference = np.vstack((base, [0, 0, 0, 0, 1, 1], [0, 0, 0, 0, -1, -1]))
    frame, metadata = create_dsd(spec, 2)
    for rep in (1, 2):
        rows = frame[frame['重复'] == rep].sort_values('标准序')
        x = rows[[f'设定_F{i}' for i in range(1, 5)]].to_numpy(dtype=int)
        cats = np.column_stack((rows['设定_F5'].map({'甲': -1, '乙': 1}),
                                rows['设定_F6'].map({'低': -1, '高': 1})))
        x = np.column_stack((x, cats))
        np.testing.assert_array_equal(x, reference)
        np.testing.assert_array_equal(x[6:12], -x[:6])
        np.testing.assert_array_equal(x[13], -x[12])
        # 这组混合设计的主效应并非两两正交；反向配对只保证与二阶项正交。
        np.testing.assert_array_equal(x.T @ x, [
            [10, 0, 0, 0, 2, 2], [0, 10, 0, 0, -2, 2],
            [0, 0, 10, 0, -2, -2], [0, 0, 0, 10, 2, -2],
            [2, -2, -2, 2, 14, 6], [2, 2, -2, -2, 6, 14],
        ])
        assert np.linalg.matrix_rank(np.column_stack((np.ones(14), x))) == 7
        assert np.linalg.matrix_rank(np.column_stack((np.ones(14), x, x[:, :4]**2))) == 11
        second = np.column_stack([x[:, i]*x[:, j] for i in range(6) for j in range(i, 6)
                                  if i != j or i < 4])
        np.testing.assert_array_equal(x.T @ second, 0)
        assert (rows['点类型'] == 'pseudo_center').sum() == 2
    validate_dsd(restore_design_result(frame, metadata))
    assert frame['运行ID'].tolist() == create_dsd(spec, 2)[0]['运行ID'].tolist()
    assert frame['运行ID'].tolist() != create_dsd(replace(spec, seed=8), 2)[0]['运行ID'].tolist()


def test_dsd_blocks_evenly_partition_full_replicates():
    spec = dsd_spec('dsd6', 6)
    frame, metadata = create_dsd(spec, replicates=4, blocks=2)
    assert len(frame) == 52 and frame['区组'].tolist() == [1]*26 + [2]*26
    assert frame.groupby('重复')['区组'].unique().map(list).to_dict() == {1: [1], 2: [1], 3: [2], 4: [2]}
    result = restore_design_result(frame, metadata)
    validate_dsd(result)
    assert frame['运行ID'].tolist() == create_dsd(spec, 4, blocks=2)[0]['运行ID'].tolist()
    assert frame['运行ID'].tolist() != create_dsd(replace(spec, seed=8), 4, blocks=2)[0]['运行ID'].tolist()
    bad_runs = list(result.runs)
    bad_runs[0] = replace(bad_runs[0], block=2)
    bad = replace(result, runs=tuple(bad_runs))
    identity = dict(bad.spec.screening_matrix)
    identity['matrix_sha256'] = screening_matrix_sha256(bad)
    bad = replace(bad, spec=replace(bad.spec, screening_matrix=identity))
    with pytest.raises(ValueError, match='区组'):
        validate_dsd(bad)
    for blocks in (0, True, 3, 5):
        with pytest.raises(ValueError, match='区组'):
            create_dsd(spec, replicates=4, blocks=blocks)
