"""CCD 设计分数、区组与分类因子；矩阵由独立构造核对。"""
import copy
from itertools import product

import numpy as np
import pytest

from doe_ccd import create_ccd, validate_ccd
from doe_core import DesignSpec, FactorSpec, restore_design_result


def spec(k, fraction='full', blocks=None, centers=None, alpha=None):
    return DesignSpec('ccd', tuple(FactorSpec(chr(65+i), chr(65+i), -1, 1)
                                   for i in range(k)), ('Y',), seed=9,
                      design_type='central_composite', ccd_alpha=alpha,
                      ccd_center_points=centers, ccd_axial_points=2*k,
                      ccd_fraction=None if fraction == 'full' else fraction,
                      block_count=blocks)


def test_half_fraction_has_16_cube_points_and_odd_defined_relation():
    frame, metadata = create_ccd(spec(5, 'half', centers=6))
    result = restore_design_result(frame, metadata)
    coded = np.asarray(validate_ccd(result), float)
    cube = coded[[run.point_type == 'factorial' for run in result.runs]]
    assert len(cube) == 16
    # 独立核对：第 5 因子由前两因子乘积生成（生成元 A*B）。
    np.testing.assert_array_equal(cube[:, 4], cube[:, 0] * cube[:, 1])
    assert sum(run.point_type == 'axial' for run in result.runs) == 10
    assert sum(run.point_type == 'center' for run in result.runs) == 6


@pytest.mark.parametrize('k, runs', [(5, 54), (6, 90), (7, 160)])
def test_blocked_full_ccd_run_counts_match_official_table(k, runs):
    frame, metadata = create_ccd(spec(k, 'full', blocks=2))
    assert len(frame) == runs
    assert frame['区组'].nunique() == 2
    result = restore_design_result(frame, metadata)
    alpha = result.spec.ccd_alpha
    cube = len([r for r in result.runs if r.point_type == 'factorial'])
    # 只从运行数据判定块内中心点数，不引用生产常量。
    cc = len([r for r in result.runs
              if r.point_type == 'center' and r.block == 1])
    ac = len([r for r in result.runs
              if r.point_type == 'center' and r.block == 2])
    # 独立核对正交式：alpha² = F(2k+ac) / (2(F+cc))。
    expected = np.sqrt(cube * (2 * k + ac) / (2 * (cube + cc)))
    assert alpha == pytest.approx(expected, rel=1e-9)


def test_block_columns_are_orthogonal_to_the_full_quadratic_model():
    frame, metadata = create_ccd(spec(6, 'full', blocks=2))
    result = restore_design_result(frame, metadata)
    coded = np.asarray(validate_ccd(result), float)
    model = np.column_stack(
        [np.ones(len(coded)), coded, coded**2] +
        [coded[:, i]*coded[:, j] for i in range(6) for j in range(i+1, 6)])
    block = np.array([run.block for run in result.runs], float).reshape(-1, 1)
    cross = (model - model.mean(0)).T @ (block - block.mean(0))
    assert np.max(np.abs(cross)) < 1e-8


def test_unsupported_block_count_is_rejected():
    with pytest.raises(ValueError, match='区组'):
        create_ccd(spec(3, 'full', blocks=5))
    with pytest.raises(ValueError, match='区组'):
        create_ccd(spec(2, 'full', blocks=3))


def test_custom_alpha_cannot_be_claimed_as_orthogonal_when_blocked():
    with pytest.raises(ValueError, match='正交 alpha'):
        create_ccd(spec(5, 'full', blocks=2, alpha=1.0))


def test_custom_alpha_for_single_block_is_preserved_and_not_called_rotatable():
    frame, metadata = create_ccd(spec(3, alpha=1.3, centers=5))
    result = restore_design_result(frame, metadata)
    assert result.spec.ccd_alpha == 1.3
    assert sum(run.point_type == 'axial' for run in result.runs) == 6


def test_fraction_and_factor_count_must_match_official_range():
    with pytest.raises(ValueError, match='连续因子'):
        create_ccd(spec(4, 'half', centers=6))
    with pytest.raises(ValueError, match='连续因子'):
        create_ccd(spec(8, 'full', centers=10))


def test_two_factor_split_uses_second_order_model():
    frame, metadata = create_ccd(spec(2, centers=5))
    result = restore_design_result(frame, metadata)
    coded = np.asarray(validate_ccd(result), float)
    model = np.column_stack([np.ones(len(coded)), coded, coded**2,
                             coded[:, 0]*coded[:, 1]])
    assert np.linalg.matrix_rank(model) == 6


@pytest.mark.parametrize(('replicates', 'runs'), [(1, 32), (2, 58), (3, 84)])
def test_fractional_ccd_repeats_keep_explicit_center_count(
        replicates, runs):
    frame, metadata = create_ccd(
        spec(5, 'half', centers=6), replicates=replicates)

    assert len(frame) == runs
    assert (frame['点类型'] == 'factorial').sum() == 16 * replicates
    assert (frame['点类型'] == 'axial').sum() == 10 * replicates
    assert (frame['点类型'] == 'center').sum() == 6
    assert sorted(frame.loc[frame['点类型'] == 'center', '重复']) == list(range(1, 7))

    result = restore_design_result(frame, metadata)
    coded = validate_ccd(result)
    actual = frame[[f'编码_{chr(65+i)}' for i in range(5)]].to_numpy(float)
    np.testing.assert_allclose(coded, actual)


def test_blocked_ccd_repeats_keep_layout_centers():
    frame, metadata = create_ccd(
        spec(5, 'full', blocks=2, centers=12), replicates=2)

    assert len(frame) == 96
    assert (frame['点类型'] == 'center').sum() == 12
    assert set(frame.loc[frame['点类型'] == 'center', '重复']) == {1}
    result = restore_design_result(frame, metadata)
    np.testing.assert_allclose(
        validate_ccd(result),
        frame[[f'编码_{chr(65+i)}' for i in range(5)]].to_numpy(float))


def test_categorical_ccd_repeats_are_validated_per_level():
    factors = tuple(FactorSpec(chr(65+i), chr(65+i), -1, 1)
                    for i in range(5)) + (
        FactorSpec('L', 'lot', None, None, factor_type='categorical',
                   levels=('low', 'high')),
    )
    design = DesignSpec(
        'ccd-categories', factors, ('Y',), seed=9,
        design_type='central_composite', ccd_center_points=6,
        ccd_axial_points=10, ccd_fraction='half')
    frame, metadata = create_ccd(design, replicates=2)

    assert len(frame) == 116
    for level in ('low', 'high'):
        subset = frame.loc[frame['设定_L'] == level]
        assert (subset['点类型'] == 'factorial').sum() == 32
        assert (subset['点类型'] == 'axial').sum() == 20
        assert (subset['点类型'] == 'center').sum() == 6
    result = restore_design_result(frame, metadata)
    np.testing.assert_allclose(
        validate_ccd(result),
        frame[[f'编码_{chr(65+i)}' for i in range(5)]].to_numpy(float))


@pytest.mark.parametrize('corruption', [
    'missing_axial', 'repeat_number', 'coded_level', 'center_count', 'duplicate_id',
])
def test_repeated_extended_ccd_recovery_rejects_corruption(corruption):
    frame, metadata = create_ccd(spec(5, 'half', centers=6), replicates=2)
    metadata = copy.deepcopy(metadata)

    if corruption == 'missing_axial':
        row = frame.index[frame['点类型'] == 'axial'][0]
        frame = frame.drop(index=row).reset_index(drop=True)
    elif corruption == 'repeat_number':
        row = frame.index[(frame['点类型'] == 'factorial') & (frame['重复'] == 2)][0]
        frame.loc[row, '重复'] = 1
    elif corruption == 'coded_level':
        row = frame.index[frame['点类型'] == 'factorial'][0]
        frame.loc[row, '编码_A'] = -float(frame.loc[row, '编码_A'])
    elif corruption == 'center_count':
        metadata['design']['ccd_center_points'] = 5
    elif corruption == 'duplicate_id':
        frame.loc[1, '运行ID'] = frame.loc[0, '运行ID']

    with pytest.raises(ValueError):
        restore_design_result(frame, metadata)


def test_blocked_ccd_requires_matching_center_count():
    with pytest.raises(ValueError, match='需要 12 个中心点.*当前输入为 5'):
        create_ccd(spec(5, 'full', blocks=2, centers=5))

    explicit, explicit_meta = create_ccd(
        spec(5, 'full', blocks=2, centers=12))
    automatic, automatic_meta = create_ccd(
        spec(5, 'full', blocks=2, centers=None))
    assert (explicit['点类型'] == 'center').sum() == 12
    assert (automatic['点类型'] == 'center').sum() == 12
    assert explicit_meta['design']['ccd_center_points'] == 12
    assert automatic_meta['design']['ccd_center_points'] == 12


def test_extended_ccd_run_limit_precedes_category_expansion(monkeypatch):
    def no_expansion(*_args, **_kwargs):
        pytest.fail('oversized CCD expanded rows or categorical combinations')

    monkeypatch.setattr('doe_ccd.category_combinations', no_expansion)
    monkeypatch.setattr('doe_ccd.cube_rows', no_expansion)
    with pytest.raises(ValueError, match='10000'):
        create_ccd(spec(5, 'half', centers=6), replicates=1_000_000)

    factors = (FactorSpec('A', 'A', -1, 1), FactorSpec('B', 'B', -1, 1)) + tuple(
        FactorSpec(f'C{i}', f'C{i}', None, None, factor_type='categorical',
                   levels=tuple(str(level) for level in range(10)))
        for i in range(4))
    design = DesignSpec('many-categories', factors, ('Y',), seed=9,
                        design_type='central_composite', ccd_center_points=5,
                        ccd_axial_points=4)
    with pytest.raises(ValueError, match='10000'):
        create_ccd(design)


def test_extended_ccd_allows_exactly_10000_runs():
    factors = (FactorSpec('A', 'A', -1, 1), FactorSpec('B', 'B', -1, 1),
               FactorSpec('L', 'lot', None, None, factor_type='categorical',
                          levels=('low', 'high')))
    design = DesignSpec('ccd-limit', factors, ('Y',), seed=9,
                        design_type='central_composite', ccd_center_points=8,
                        ccd_axial_points=2496)
    frame, _ = create_ccd(design, replicates=624)
    assert len(frame) == 10000
