"""逐方法独立参考及边界验证，全部经公共生产接口调用。

fit_pca/project → 协方差 eigh、手工秩一投影、原单位还原；不调用 SVD 作参考。
t2_limits → Beta/F 定义的正则不完全 Beta CDF 反查分位数；Q → 不完全 Gamma
CDF 及单遗漏特征值的精确 chi²_1 特例。分布参数定义参考 SciPy stats 的
beta/f/chi2 官方说明。hotelling_statistics → 直接逆矩阵二次型。
contributions → 手工 signed z*(PΛ^-1P'z)、逐变量残差平方及加和恒等式。
compare_groups → 原始样本手工均值/样本方差；selection_mask → 手工几何。
CV → 每折仅从训练行协方差 eigh 推导，留出误差不能用于自动选维。
save/load_pca → 保存前后训练及新样本投影一致；损坏格式、谱、形状、非有限
值、来源及预处理不一致均拒绝。边界包含常量、缺失、秩亏、少样本、宽矩阵、
固定缩放、未知 T² 限、零残差退化及取消。实际执行结果见任务交付报告。
"""
import json
from threading import Event

import numpy as np
import pandas as pd
import pytest
from numpy.testing import assert_allclose
from scipy import special, stats

from pca_analysis import (PCAProjection, fit_pca, hotelling_statistics, load_pca,
                          selection_mask, t2_limits)


@pytest.fixture
def frame():
    rng = np.random.default_rng(572)
    z = rng.normal(size=(60, 4))
    z[:, 1] = .7*z[:, 0]+.5*z[:, 1]
    z[:, 2] = -.2*z[:, 0]+1.1*z[:, 2]
    return pd.DataFrame(z*[2., 7., .8, 3.]+[10., -20., 1., 100.],
                        columns=['温度', '压力', '流量', '浓度'],
                        index=[f'样本-{i}' for i in range(60)])


def reference(frame, scaling, k):
    """从协方差 eigh 推导，与生产 SVD 实现独立。"""
    raw = frame.to_numpy(float)
    mean = np.zeros(raw.shape[1]) if scaling == 'none' else np.mean(raw, axis=0)
    scale = np.std(raw, axis=0, ddof=1) if scaling == 'autoscale' else np.ones(raw.shape[1])
    z = (raw-mean)/scale
    cov = z.T @ z/(len(z)-1) if scaling == 'none' else np.cov(z, rowvar=False)
    eigen, vectors = np.linalg.eigh(cov)
    eigen, vectors = eigen[::-1], vectors[:, ::-1]
    # 比较子空间而非任意特征向量符号。
    projection = vectors[:, :k] @ vectors[:, :k].T
    reconstructed = z @ projection
    inverse = vectors[:, :k] @ np.diag(1/eigen[:k]) @ vectors[:, :k].T
    return mean, scale, z, eigen, projection, reconstructed, inverse


@pytest.mark.parametrize('scaling', ['autoscale', 'center', 'none'])
@pytest.mark.parametrize('k', [1, 2, 4])
def test_svd_pca_independent_eigh_and_projection(frame, scaling, k):
    original = frame.copy(deep=True)
    model = fit_pca(frame, list(frame), n_components=k, scaling=scaling)
    mean, scale, z, eigen, projector, fit, inverse = reference(frame, scaling, k)
    result = model.training
    assert isinstance(result, PCAProjection)
    assert result.phase == 'phase1'
    assert model.n_components == k
    assert model.n_samples == len(frame)
    assert model.columns == list(frame)
    assert_allclose(model.mean, mean)
    assert_allclose(model.scale, scale)
    assert_allclose(model.eigenvalues, eigen, rtol=1e-10)
    assert_allclose(model.loadings @ model.loadings.T, projector, atol=1e-12)
    assert_allclose(model.loadings.T @ model.loadings, np.eye(k), atol=1e-12)
    assert_allclose(result.scaled, z)
    assert_allclose(result.scores, z @ model.loadings, atol=1e-12)
    assert_allclose(result.reconstructed, fit*scale+mean, atol=1e-12)
    assert_allclose(result.residuals, z-fit, atol=1e-12)
    assert_allclose(result.q, np.sum((z-fit)**2, axis=1), atol=1e-24)
    assert_allclose(result.t2, np.einsum('ij,jk,ik->i', z, inverse, z), rtol=1e-10)
    assert_allclose(model.explained_variance_ratio, eigen/eigen.sum())
    assert_allclose(model.tables['variance'].cumulative_variance_ratio, np.cumsum(eigen)/eigen.sum())
    assert list(model.tables) == ['variance', 'loadings', 'limits', 'preprocessing', 'cv']
    assert list(result.tables) == ['scores', 'monitoring', 'residuals', 'reconstructed']
    assert result.source.source_row.tolist() == list(range(1, len(frame)+1))
    assert result.source.source_index.tolist() == frame.index.tolist()
    pd.testing.assert_frame_equal(frame, original)
    pd.testing.assert_frame_equal(result.data, frame.reset_index(drop=True))
    assert model.scores is result.scores
    for key in result.tables:
        assert result.tables[key].source_row.tolist() == list(range(1, len(frame)+1))


@pytest.mark.parametrize('variance', [.01, .6, .95, 1.])
def test_cumulative_selection_and_manual_override(frame, variance):
    eigen = reference(frame, 'autoscale', 1)[3]
    expected = next((i+1 for i, v in enumerate(np.cumsum(eigen)/sum(eigen)) if v >= variance), len(eigen))
    assert fit_pca(frame, list(frame), variance=variance).n_components == expected
    assert fit_pca(frame, list(frame), n_components=1, variance=variance).n_components == 1


def test_rank_one_hand_computed_and_zero_q_projection():
    t = np.arange(-3., 4.)
    df = pd.DataFrame({'a': t+5, 'b': 2*t-1})
    model = fit_pca(df, ['a', 'b'], n_components=1, scaling='center')
    assert_allclose(model.eigenvalues, [5*np.dot(t, t)/(len(t)-1), 0], atol=1e-12)
    assert_allclose(model.loadings[:, 0], np.array([1, 2])/np.sqrt(5))
    assert_allclose(model.training.t2, t*t/np.var(t, ddof=1))
    assert_allclose(model.training.reconstructed, df, atol=1e-14)
    assert model.tables['limits'].q.eq(0).all()
    assert not model.training.flags.q_flag_95.any()
    new = model.project(pd.DataFrame({'a': [5., 7.], 'b': [0., 3.]}))
    assert_allclose(new.q, [.2, 0], atol=1e-28)
    assert new.flags.q_flag_95.tolist() == [True, False]
    with pytest.raises(ValueError, match='数值秩'):
        fit_pca(df, ['a', 'b'], n_components=2)


def test_wide_singular_data_all_eigenvalues():
    t = np.linspace(-2, 2, 5)
    frame = pd.DataFrame(np.column_stack([t, t**2, 2*t, -t, t**2+3, 4*t+1]), columns=list('abcdef'))
    model = fit_pca(frame, list(frame), variance=1, scaling='center')
    assert model.eigenvalues.shape == (6,)
    assert model.n_components == 2
    assert_allclose(model.eigenvalues[2:], 0)
    assert_allclose(model.training.reconstructed, frame, atol=1e-13)


@pytest.mark.parametrize('scaling', ['center', 'autoscale', 'none'])
def test_projection_freezes_training_preprocessing_and_keeps_column_order(frame, scaling):
    model = fit_pca(frame, list(frame), n_components=2, scaling=scaling)
    future = frame.iloc[[7, 3]].copy()*30+200
    future = future[list(reversed(frame.columns))]
    future['无关列'] = ['x', 'y']
    before_mean, before_scale = model.mean.copy(), model.scale.copy()
    result = model.project(future)
    raw = future[model.columns].to_numpy()
    assert result.phase == 'phase2'
    assert_allclose(result.scaled, (raw-before_mean)/before_scale)
    assert_allclose(result.scores, (raw-before_mean)/before_scale @ model.loadings)
    assert_allclose(model.mean, before_mean)
    assert_allclose(model.scale, before_scale)
    assert result.source.source_index.tolist() == ['样本-7', '样本-3']
    assert result.source.source_row.tolist() == [1, 2]
    # 单个新样本合法，不得要求重新估计方差。
    assert model.project(future.iloc[:1]).scores.shape == (1, 2)


@pytest.mark.parametrize('phase', ['phase1', 'phase2'])
@pytest.mark.parametrize('confidence', [.95, .99])
@pytest.mark.parametrize('n,k', [(20, 1), (100, 3), (8, 5)])
def test_t2_limits_inverted_distribution_definition(n, k, confidence, phase):
    upper = t2_limits(n, k, confidence, phase)
    if phase == 'phase1':
        probability = special.betainc(k/2, (n-k-1)/2, upper/((n-1)**2/n))
    else:
        f = upper/(k*(n+1)*(n-1)/(n*(n-k)))
        probability = special.betainc(k/2, (n-k)/2, k*f/(k*f+n-k))
    assert_allclose(probability, confidence, atol=1e-13)


def test_model_limits_flags_and_q_moment_definition(frame):
    model = fit_pca(frame, list(frame), n_components=2)
    eigen = reference(frame, 'autoscale', 2)[3]
    theta1, theta2 = sum(eigen[2:]), sum(eigen[2:]**2)
    limits = model.tables['limits']
    for row in limits.itertuples():
        assert_allclose(row.theta1, theta1)
        assert_allclose(row.theta2, theta2)
        g, h = theta2/theta1, theta1**2/theta2
        assert_allclose(special.gammainc(h/2, row.q/(2*g)), row.confidence)
    assert_allclose(limits.loc[limits.phase == 'phase1', 'q'], limits.loc[limits.phase == 'phase2', 'q'])
    projected = model.project(frame.iloc[[0, 4, 8]]*100)
    for result in (model.training, projected):
        for confidence, tag in ((.95, '95'), (.99, '99')):
            lim = limits[(limits.phase == result.phase) & (limits.confidence == confidence)].iloc[0]
            assert result.flags[f't2_flag_{tag}'].tolist() == (result.t2 > lim.t2).tolist()
            assert result.flags[f'q_flag_{tag}'].tolist() == (result.q > lim.q).tolist()
            assert result.flags[f'abnormal_{tag}'].tolist() == ((result.t2 > lim.t2) | (result.q > lim.q)).tolist()
    assert limits.iloc[0].t2 < limits.iloc[2].t2


def test_q_single_discarded_component_exact_chisquare(frame):
    model = fit_pca(frame[['温度', '压力']], ['温度', '压力'], 1, scaling='center')
    tail = model.eigenvalues[1]
    for row in model.tables['limits'].itertuples():
        assert_allclose(row.q, tail*stats.chi2.ppf(row.confidence, 1))


def test_none_mode_t2_limits_unavailable_not_false_normal(frame):
    model = fit_pca(frame, list(frame), 2, scaling='none')
    assert model.tables['limits'].t2.isna().all()
    assert model.training.flags.t2_flag_95.isna().all()
    assert model.training.flags.abnormal_95[~model.training.flags.q_flag_95].isna().all()
    assert any('不中心化' in note for note in model.notes)


def test_small_sample_unknown_phase1_but_valid_projection_limit():
    df = pd.DataFrame({'a': [1., 3.], 'b': [3., 1.]})
    model = fit_pca(df, list(df), 1)
    assert model.training.flags.t2_flag_95.isna().all()
    assert model.training.flags.abnormal_95.isna().all()
    assert np.isfinite(model.tables['limits'].query("phase == 'phase2'").t2).all()
    assert not model.project(df).flags.t2_flag_95.isna().any()


@pytest.mark.parametrize('projection', [False, True])
def test_signed_t2_and_q_variable_contributions(frame, projection):
    model = fit_pca(frame, list(frame), 2)
    result = model.project(frame*1.5) if projection else model.training
    kwargs = {'projection': result} if projection else {}
    for i in [0, 3, 10]:
        t2 = model.contributions(i, 't2', **kwargs)
        q = model.contributions(i, 'q', **kwargs)
        z = result.scaled[i]
        inverse = model.loadings @ np.diag(1/model.eigenvalues[:2]) @ model.loadings.T
        assert t2.variable.tolist() == model.columns
        assert_allclose(t2.contribution, z*(inverse @ z), atol=1e-12)
        assert_allclose(t2.contribution.sum(), result.t2[i], atol=1e-12)
        assert_allclose(q.contribution, result.residuals[i]**2)
        assert_allclose(q.contribution.sum(), result.q[i])
    assert any((model.contributions(i).contribution < 0).any() for i in range(len(frame)))


def test_contribution_validation(frame):
    model = fit_pca(frame, list(frame), 2)
    other = fit_pca(frame, list(frame), 2).training
    for row in [-1, len(frame), 1.5, True]:
        with pytest.raises(ValueError):
            model.contributions(row)
    with pytest.raises(ValueError):
        model.contributions(0, 'unknown')
    with pytest.raises(ValueError):
        model.contributions(0, projection=other)


@pytest.mark.parametrize('project', [False, True])
def test_group_comparison_raw_units_independent(frame, project):
    model = fit_pca(frame, list(frame), 2)
    result = model.project(frame+100) if project else model.training
    comparison = model.compare_groups([0, 2, 8], [1, 3, 9, 12], projection=result)
    assert comparison.variable.tolist() == list(frame)
    for j, row in enumerate(comparison.itertuples()):
        a, b = result.data.iloc[[0, 2, 8], j].tolist(), result.data.iloc[[1, 3, 9, 12], j].tolist()
        ma, mb = sum(a)/len(a), sum(b)/len(b)
        sa, sb = (sum((v-ma)**2 for v in a)/(len(a)-1))**.5, (sum((v-mb)**2 for v in b)/(len(b)-1))**.5
        assert row.n_a == 3 and row.n_b == 4
        assert_allclose([row.mean_a, row.mean_b, row.std_a, row.std_b, row.difference], [ma, mb, sa, sb, ma-mb])
    empty = model.compare_groups([], [1])
    assert empty.n_a.eq(0).all() and empty.n_b.eq(1).all()
    assert empty[['mean_a', 'std_a', 'std_b', 'difference']].isna().all().all()


@pytest.mark.parametrize('a,b', [([0, 0], [1]), ([-1], [1]), ([500], []), ([True], [1]), ([.2], [1])])
def test_group_invalid_indices(frame, a, b):
    with pytest.raises(ValueError):
        fit_pca(frame, list(frame), 2).compare_groups(a, b)


def test_selection_geometry_including_boundary():
    points = np.array([[0, 0], [1, 0], [0, 2], [1, 2], [2, 3], [-1, -2], [0, -2]])
    assert selection_mask(points, [-1, 1, -2, 2]).tolist() == [True, True, True, True, False, True, True]
    assert selection_mask(points, [-1, 1, -2, 2], 'ellipse').tolist() == [True, True, True, False, False, False, True]


@pytest.mark.parametrize('points,bounds,geometry', [([[1]], [0, 1, 0, 1], 'rectangle'),
    ([[0, np.nan]], [0, 1, 0, 1], 'rectangle'), ([[0, 0]], [0, 0, 0, 1], 'ellipse'),
    ([[0, 0]], [0, 1, 2, 1], 'rectangle'), ([[0, 0]], [0, 1, 0, np.inf], 'rectangle'),
    ([[0, 0]], [0, 1, 0, 1], 'lasso')])
def test_selection_invalid(points, bounds, geometry):
    with pytest.raises(ValueError):
        selection_mask(points, bounds, geometry)


def test_hotelling_fixed_baseline_independent_inverse(frame):
    x = frame.to_numpy()
    mu, cov = x.mean(0), np.cov(x, rowvar=False)
    future = x[:5]+10
    expected = [(v-mu) @ np.linalg.inv(cov) @ (v-mu) for v in future]
    assert_allclose(hotelling_statistics(future, mu, cov), expected)
    assert hotelling_statistics(np.empty((0, 4)), mu, cov).shape == (0,)


@pytest.mark.parametrize('x,mu,cov', [([[1, 2]], [0], [[1]]), ([[1, 2]], [0, 0], [[1, 1], [1, 1]]),
    ([[1, 2]], [0, 0], [[1, 2], [0, 1]]), ([[1, 2]], [0, 0], [[-1, 0], [0, 1]]),
    ([[np.inf]], [0], [[1]]), ([[1]], [np.nan], [[1]])])
def test_hotelling_rejects_invalid_and_singular(x, mu, cov):
    with pytest.raises(ValueError):
        hotelling_statistics(x, mu, cov)


def test_cv_independent_fold_preprocessing_eigh_and_no_automatic_selection(frame):
    model = fit_pca(frame, list(frame), variance=.6, cv_folds=3)
    without_cv = fit_pca(frame, list(frame), variance=.6)
    assert model.n_components == without_cv.n_components
    assert_allclose(model.mean, without_cv.mean)
    sums = np.zeros(4)
    for hold in np.array_split(np.arange(len(frame)), 3):
        train = frame.drop(frame.index[hold])
        mu, scale = train.mean().to_numpy(), train.std(ddof=1).to_numpy()
        eigen, vectors = np.linalg.eigh(np.cov((train-mu)/scale, rowvar=False))
        vectors = vectors[:, np.argsort(eigen)[::-1]]
        z = (frame.iloc[hold].to_numpy()-mu)/scale
        for k in range(1, 5):
            operator = np.eye(4)-vectors[:, :k] @ vectors[:, :k].T
            sums[k-1] += np.trace(z @ operator @ operator.T @ z.T)
    assert_allclose(model.cv.mse, sums/frame.size, atol=1e-12)
    assert model.cv.n_values.eq(frame.size).all()
    assert model.cv.n_components.tolist() == [1, 2, 3, 4]
    assert model.cv.mse.iloc[-1] < 1e-25
    assert model.n_components < 4
    assert any('不自动选维' in s for s in model.notes)


def test_cv_does_not_use_global_scale_or_leak_holdout(frame):
    shifted = frame.copy()
    shifted.iloc[:20, 0] += 1000
    result = fit_pca(shifted, list(frame), 1, cv_folds=3)
    # 第一个折在局部训练尺度下有巨大重构误差；全数据缩放会掩盖该偏移。
    global_scaled = (shifted-shifted.mean())/shifted.std(ddof=1)
    assert result.cv.mse.iloc[0] > np.mean(global_scaled.to_numpy()**2)*10


def test_missing_drop_keeps_original_positions_and_indices(frame):
    dirty = frame.iloc[:6].copy()
    dirty.iloc[1, 0] = np.nan
    dirty.iloc[4, 2] = np.nan
    original = dirty.copy()
    with pytest.raises(ValueError, match='缺失'):
        fit_pca(dirty, list(frame))
    model = fit_pca(dirty, list(frame), 2, missing='drop')
    assert model.training.source.source_row.tolist() == [1, 3, 4, 6]
    assert model.training.source.source_index.tolist() == ['样本-0', '样本-2', '样本-3', '样本-5']
    assert any('2 行' in note for note in model.training.notes)
    with pytest.raises(ValueError, match='缺失'):
        model.project(dirty)
    result = model.project(dirty, missing='drop')
    pd.testing.assert_frame_equal(result.source, model.training.source)
    pd.testing.assert_frame_equal(dirty, original)


@pytest.mark.parametrize('df', [pd.DataFrame({'x': [1, 1]}), pd.DataFrame({'x': [1.]}),
    pd.DataFrame({'x': [np.nan, np.nan]}), pd.DataFrame({'x': [1., np.inf]}),
    pd.DataFrame({'x': [1+1j, 2+0j]}), pd.DataFrame({'x': ['a', 'b']}),
    pd.DataFrame([[1, 2], [3, 4]], columns=['x', 'x'])])
def test_invalid_training_data(df):
    with pytest.raises(ValueError):
        fit_pca(df, ['x'])


@pytest.mark.parametrize('kwargs', [{'scaling': 'bad'}, {'variance': 0}, {'variance': 1.1},
    {'variance': float('nan')}, {'variance': '0.95'}, {'n_components': 0}, {'n_components': 5},
    {'n_components': True}, {'n_components': 1.2}, {'cv_folds': 1}, {'cv_folds': 61},
    {'cv_folds': True}, {'cv_folds': 2.5}, {'missing': 'fill'}])
def test_invalid_parameters(frame, kwargs):
    with pytest.raises(ValueError):
        fit_pca(frame, list(frame), **kwargs)


@pytest.mark.parametrize('columns', [[], ['温度', '温度'], ['不存在'], '温度', [1]])
def test_invalid_columns(frame, columns):
    with pytest.raises(ValueError):
        fit_pca(frame, columns)


@pytest.mark.parametrize('n,k,confidence,phase', [(2, 1, .95, 'phase1'), (3, 3, .95, 'phase2'),
    (10, 1, 1, 'phase2'), (10, 1, float('nan'), 'phase2'), (10, 1, .95, 'unknown'),
    (10., 1, .95, 'phase2'), (10, True, .95, 'phase2'), (10, 1, 'x', 'phase2')])
def test_t2_invalid_parameters(n, k, confidence, phase):
    with pytest.raises(ValueError):
        t2_limits(n, k, confidence, phase)


def test_cv_constant_training_fold_rejected():
    frame = pd.DataFrame({'a': [1, 2, 3, 3, 3, 3], 'b': [3, 2, 1, 2, 3, 4]})
    with pytest.raises(ValueError, match='训练折'):
        fit_pca(frame, list(frame), cv_folds=3)


def test_cancel_event_and_during_cv(frame):
    event = Event()
    event.set()
    with pytest.raises(InterruptedError, match='取消'):
        fit_pca(frame, list(frame), cancel=event)
    calls = []
    def cancelled():
        calls.append(1)
        return len(calls) >= 4
    with pytest.raises(InterruptedError, match='取消'):
        fit_pca(frame, list(frame), cv_folds=3, cancel=cancelled)


@pytest.mark.parametrize('scaling', ['center', 'autoscale', 'none'])
def test_save_load_training_projection_and_contributions_without_source(frame, tmp_path, scaling):
    model = fit_pca(frame, list(frame), 2, scaling=scaling, cv_folds=3)
    file = tmp_path/'模型.json'
    model.save(file)
    decoded = json.loads(file.read_text(encoding='utf-8'))
    assert decoded['format'] == 'MiniJMP-PCA' and decoded['version'] == 1
    loaded = load_pca(file)
    assert loaded is not model
    assert loaded.columns == model.columns
    assert loaded.n_components == model.n_components
    for attr in ['scores', 't2', 'q', 'scaled', 'residuals', 'reconstructed']:
        assert_allclose(getattr(loaded.training, attr), getattr(model.training, attr))
    pd.testing.assert_frame_equal(loaded.training.source, model.training.source)
    pd.testing.assert_frame_equal(loaded.training.data, model.training.data)
    pd.testing.assert_frame_equal(loaded.cv, model.cv)
    for key in model.tables:
        pd.testing.assert_frame_equal(loaded.tables[key], model.tables[key])
    for key in model.training.tables:
        pd.testing.assert_frame_equal(loaded.training.tables[key], model.training.tables[key])
    pd.testing.assert_frame_equal(loaded.contributions(3), model.contributions(3))
    pd.testing.assert_frame_equal(loaded.compare_groups([0, 1], [4, 5]), model.compare_groups([0, 1], [4, 5]))
    new = frame.iloc[[1, 3]].copy()*3
    assert_allclose(loaded.project(new).scores, model.project(new).scores)
    assert_allclose(loaded.project(new).q, model.project(new).q)


def test_save_drop_positions_and_complex_source_labels(frame, tmp_path):
    df = frame.iloc[:8].copy()
    df.index = pd.MultiIndex.from_tuples([('批次', i) for i in range(8)])
    df.iloc[1, 0] = np.nan
    model = fit_pca(df, list(df), 2, missing='drop')
    path = tmp_path/'index.json'
    model.save(path)
    raw = json.loads(path.read_text(encoding='utf-8'))
    assert raw['source_index'][0] == {'type': 'tuple', 'value': str(df.index[0])}
    loaded = load_pca(path)
    assert loaded.training.source.source_row.tolist() == [1, 3, 4, 5, 6, 7, 8]
    assert loaded.training.source.source_index.iloc[0] == f'[tuple] {df.index[0]}'
    assert_allclose(loaded.scores, model.scores)


@pytest.mark.parametrize('index', [[1, 2, 3, 4], ['a', 'b', 'c', 'd'], [1.2, 2.3, 3.4, 4.5],
    [True, False, True, False], [None, 'b', 'c', 'd'], pd.date_range('2020-01-01', periods=4)])
def test_safe_index_storage(frame, tmp_path, index):
    df = frame.iloc[:4].copy()
    df.index = index
    model = fit_pca(df, list(df), 1)
    path = tmp_path/'source.json'
    model.save(path)
    result = load_pca(path)
    assert result.training.source.source_row.tolist() == [1, 2, 3, 4]
    assert len(result.training.source.source_index) == 4


@pytest.mark.parametrize('field,value', [('version', 2), ('version', True), ('format', 'unknown'),
    ('columns', ['x', 'x']), ('columns', [1]), ('columns', []), ('mean', [0]),
    ('mean', [float('nan')]*4), ('scale', [0]*4), ('scale', [-1]*4),
    ('eigenvalues', [1, 2, 3, 4]), ('eigenvalues', [-1]*4), ('eigenvalues', [float('inf')]*4),
    ('loadings', [[1, 2]]), ('loadings', [[0, 0]]*4), ('data', [[1, 2, 3, 4]]),
    ('n_components', 5), ('n_components', 0), ('n_samples', 2), ('scaling', 'unknown'),
    ('variance', 0), ('source_row', [0]*60), ('source_row', list(range(60, 0, -1))),
    ('source_index', ['bad']*60), ('source_index', [{'type': 'scalar', 'value': []}]*60),
    ('source_index', [{'type': 'tuple', 'value': []}]*60), ('cv', {}),
    ('cv', [{'n_components': 1, 'mse': -1, 'n_values': 240}]),
    ('cv', [{'n_components': 2, 'mse': 1, 'n_values': 240}]),
    ('cv', [{'n_components': 1, 'mse': 1, 'n_values': 2}])])
def test_load_rejects_corrupt_models(frame, tmp_path, field, value):
    path = tmp_path/'corrupt.json'
    fit_pca(frame, list(frame), 2).save(path)
    record = json.loads(path.read_text(encoding='utf-8'))
    record[field] = value
    path.write_text(json.dumps(record), encoding='utf-8')
    with pytest.raises(ValueError, match='读取失败'):
        load_pca(path)


def test_load_rejects_finite_but_inconsistent_training_parameters(frame, tmp_path):
    path = tmp_path/'parameters.json'
    fit_pca(frame, list(frame), 2).save(path)
    saved = json.loads(path.read_text(encoding='utf-8'))
    for key in ['mean', 'scale', 'eigenvalues', 'loadings', 'data']:
        corrupted = json.loads(json.dumps(saved))
        if key in ['data', 'loadings']:
            corrupted[key][0][0] += .1
        else:
            corrupted[key][0] += .1
        path.write_text(json.dumps(corrupted), encoding='utf-8')
        with pytest.raises(ValueError, match='读取失败'):
            load_pca(path)


@pytest.mark.parametrize('contents', ['[]', '{}', '{', 'null'])
def test_bad_json_models(tmp_path, contents):
    path = tmp_path/'broken.json'
    path.write_text(contents, encoding='utf-8')
    with pytest.raises(ValueError, match='读取失败'):
        load_pca(path)


def test_overflow_training_projection_and_hotelling_fail_explicitly(frame):
    huge = pd.DataFrame({'x': [1e308, -1e308, 0.], 'y': [2., 3., 4.]})
    with np.errstate(over='ignore', invalid='ignore', divide='ignore'):
        with pytest.raises(ValueError):
            fit_pca(huge, list(huge), scaling='center')
        model = fit_pca(frame, list(frame), 2)
        with pytest.raises(ValueError, match='溢出'):
            model.project(pd.DataFrame(np.full((1, 4), 1e308), columns=frame.columns))
        with pytest.raises(ValueError, match='溢出'):
            hotelling_statistics([[1e308]], [0], [[1]])


def test_save_failure_preserves_existing_file_and_cleans_temporary(frame, tmp_path, monkeypatch):
    from pathlib import Path
    path = tmp_path/'已保存.json'
    path.write_text('已有模型', encoding='utf-8')
    model = fit_pca(frame, list(frame), 2)
    def fail_replace(self, target):
        raise OSError('模拟写盘失败')
    monkeypatch.setattr(Path, 'replace', fail_replace)
    with pytest.raises(OSError, match='写盘失败'):
        model.save(path)
    assert path.read_text(encoding='utf-8') == '已有模型'
    assert list(tmp_path.iterdir()) == [path]


def test_overflow_q_moments_explicit_error(frame):
    with np.errstate(over='ignore', invalid='ignore'):
        with pytest.raises(ValueError, match='Q 控制限'):
            fit_pca(frame*1e90, list(frame), 1, scaling='center')
