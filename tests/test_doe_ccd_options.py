"""CCD 设计分数、区组与分类因子；矩阵由独立构造核对。"""
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
