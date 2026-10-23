"""fit_pls 的逐方法独立参考与边界。

PLS1 一成分：w ∝ Xᵀy 的协方差闭式解；PLS2 一成分：XᵀY 的最大
左奇异向量（SVD，不使用生产 NIPALS）。满秩多成分：numpy.linalg.lstsq
独立 OLS 基准。多 Y：已知线性映射合成数据。CV：逐折用协方差闭式解
重建一成分预测及训练折标准化 PRESS，同时对照错误的全局预处理反例。
各检验均经生产入口；不是调用生产内部函数建立参考。
"""
from threading import Event

import numpy as np
import pandas as pd
import pytest
from numpy.testing import assert_allclose

from pls_regression import fit_pls


@pytest.fixture
def data():
    rng = np.random.default_rng(827)
    x = rng.normal(size=(45, 4)) * [1., 5., .3, 2.] + [2., -4., 10., 0.]
    y = x @ np.array([[2., -.3], [.4, 1.], [-1., 2.], [.5, .7]])
    y += rng.normal(scale=.15, size=y.shape) + [7., -3.]
    return pd.DataFrame(np.column_stack([x, y]), columns=['a', 'b', 'c', 'd', 'y', 'z'])


def one_component(x, y, scale):
    """SVD covariance optimization, independent of the iterative production algorithm."""
    xm, ym = x.mean(axis=0), y.mean(axis=0)
    xs = x.std(axis=0, ddof=1) if scale else np.ones(x.shape[1])
    ys = y.std(axis=0, ddof=1) if scale else np.ones(y.shape[1])
    xx, yy = (x-xm)/xs, (y-ym)/ys
    w = np.linalg.svd(xx.T @ yy, full_matrices=False)[0][:, 0]
    score = xx @ w
    q = score @ yy / (score @ score)
    beta = np.outer(w, q) * ys / xs[:, None]
    return ym - xm @ beta, beta, w, score, q


@pytest.mark.parametrize('scale', [False, True])
@pytest.mark.parametrize('responses', [['y'], ['y', 'z']])
def test_one_component_covariance_svd_reference(data, scale, responses):
    columns = ['a', 'b', 'c', 'd']
    result = fit_pls(data, responses, columns, n_components=1, cv=0, scale=scale)
    xx, yy = data[columns].to_numpy(), data[responses].to_numpy()
    intercept, beta, w, t, q = one_component(xx, yy, scale)
    prediction = result.predict(data)
    for j, response in enumerate(responses):
        coef = result.tables['coefficients'].query('response == @response')
        assert coef.term.tolist() == ['Intercept'] + columns
        assert_allclose(coef.estimate, np.r_[intercept[j], beta[:, j]], atol=1e-9)
        assert_allclose(prediction.query('response == @response').predicted,
                        xx @ beta[:, j] + intercept[j], atol=1e-9)
    assert_allclose(result.tables['vip'].vip, np.sqrt(len(columns))*np.abs(w), atol=1e-9)
    actual_t = result.tables['x_scores'].component_1.to_numpy()
    sign = np.sign(actual_t @ t)
    assert_allclose(actual_t, t*sign, atol=1e-9)
    yy_scaled = (yy-yy.mean(axis=0))/(yy.std(axis=0, ddof=1) if scale else 1)
    assert_allclose(result.tables['y_scores'].component_1,
                    yy_scaled @ q/(q @ q)*sign, atol=1e-9)
    xx_scaled = (xx-xx.mean(axis=0))/(xx.std(axis=0, ddof=1) if scale else 1)
    px = xx_scaled.T @ t/(t @ t)
    assert_allclose(result.tables['x_loadings'].component_1, px*sign, atol=1e-9)
    assert_allclose(result.tables['y_loadings'].component_1, q*sign, atol=1e-9)
    variance = result.tables['variance']
    assert_allclose(variance.x_variance_ratio, (t @ t)*(px @ px)/np.sum(xx_scaled**2))
    assert_allclose(variance.y_variance_ratio, (t @ t)*q*q/np.sum(yy_scaled**2, axis=0))


@pytest.mark.parametrize('scale', [False, True])
@pytest.mark.parametrize('responses', [['y'], ['y', 'z']])
def test_full_rank_pls_matches_independent_ols(data, scale, responses):
    columns = ['a', 'b', 'c', 'd']
    result = fit_pls(data, responses, columns, n_components=4, cv=0, scale=scale)
    design = np.column_stack([np.ones(len(data)), data[columns]])
    reference = np.linalg.lstsq(design, data[responses], rcond=None)[0]
    for j, response in enumerate(responses):
        coef = result.tables['coefficients'].query('response == @response')
        assert_allclose(coef.estimate, reference[:, j], atol=1e-9)
        obs = result.tables['observations'].query('response == @response')
        fitted = design @ reference[:, j]
        assert_allclose(obs.fitted, fitted, atol=1e-9)
        assert_allclose(obs.residual, data[response]-fitted, atol=1e-9)
        summary = result.tables['summary'].query('response == @response').iloc[0]
        assert_allclose(summary.rmse, np.sqrt(np.mean((data[response]-fitted)**2)))
        assert_allclose(summary.r_squared,
                        1-np.sum((data[response]-fitted)**2)/np.sum((data[response]-data[response].mean())**2))
    scores = result.tables['x_scores'].filter(like='component_').to_numpy()
    gram = scores.T @ scores
    assert_allclose(gram-np.diag(np.diag(gram)), 0, atol=1e-9)
    assert_allclose(result.tables['vip'].vip.to_numpy() @ result.tables['vip'].vip, 4)


def test_multi_y_exact_synthetic_and_original_unit_prediction():
    rng = np.random.default_rng(57)
    x = rng.normal(size=(40, 3))
    beta = np.array([[2., -7.], [.1, .2], [-1., 5.]])
    y = x @ beta + [11., 300.]
    frame = pd.DataFrame(np.column_stack([x, y]), columns=['a', 'b', 'c', 'y', 'z'])
    result = fit_pls(frame, ['y', 'z'], ['a', 'b', 'c'], n_components=3, cv=0)
    new_x = rng.normal(size=(7, 3))
    new = pd.DataFrame(new_x, columns=['a', 'b', 'c'], index=['duplicate']*7)
    predicted = result.predict(new)
    for j, response in enumerate(['y', 'z']):
        rows = predicted.query('response == @response')
        assert rows.source_row.tolist() == list(range(1, 8))
        assert rows.source_index.tolist() == ['duplicate']*7
        assert_allclose(rows.predicted, new_x @ beta[:, j] + [11., 300.][j], atol=1e-9)
    assert_allclose(result.tables['variance'].groupby('response').last().y_cumulative_ratio, 1.)
    assert_allclose(result.tables['variance'].x_cumulative_ratio.iloc[-1], 1.)


@pytest.mark.parametrize('orthogonal', [False, True])
def test_multi_y_initial_direction_does_not_miss_maximum_covariance(orthogonal):
    x1 = np.array([-1., -1., 1., 1.])
    x2 = np.array([-1., 1., -1., 1.])
    if orthogonal:
        xx = np.column_stack([x1, x2])
        yy = np.column_stack([100*x1*x2, x1+2*x2, x1-.5*x2])
    else:
        xx = np.column_stack([2*x1/3, x2])
        yy = np.column_stack([3*x1, 1.5*x2, 1.5*x2])
    frame = pd.DataFrame(np.column_stack([xx, yy]), columns=['a', 'b', 'y', 'z', 'v'])
    result = fit_pls(frame, ['y', 'z', 'v'], ['a', 'b'], n_components=1, cv=0, scale=False)
    intercept, beta, _, _, _ = one_component(xx, yy, False)
    for j, response in enumerate(['y', 'z', 'v']):
        assert_allclose(result.predict(frame).query('response == @response').predicted,
                        xx @ beta[:, j] + intercept[j], atol=1e-9)


def test_holdout_actual_residual_rmsep_with_optional_missing_y(data):
    result = fit_pls(data.iloc[:30], ['y', 'z'], ['a', 'b', 'c'], n_components=2, cv=0)
    holdout = data.iloc[30:].copy()
    holdout.iloc[0, holdout.columns.get_loc('y')] = np.nan
    prediction = result.predict(holdout)
    assert len(prediction) == len(holdout)*2
    for response in ['y', 'z']:
        rows = prediction.query('response == @response')
        assert_allclose(rows.actual, holdout[response], equal_nan=True)
        assert_allclose(rows.residual, holdout[response].to_numpy()-rows.predicted, equal_nan=True)
        assert_allclose(rows.rmsep, np.sqrt(np.nanmean(rows.residual**2)))
    partial = result.predict(holdout.drop(columns='z'))
    assert partial.query('response == "z"').actual.isna().all()
    assert partial.query('response == "z"').residual.isna().all()
    assert partial.query('response == "z"').rmsep.isna().all()
    plain = result.predict(holdout[['a', 'b', 'c']])
    assert 'actual' not in plain and 'residual' not in plain and 'rmsep' not in plain
    all_unknown = holdout.copy()
    all_unknown['y'] = np.nan
    assert result.predict(all_unknown).query('response == "y"').rmsep.isna().all()


@pytest.mark.parametrize('scale', [False, True])
def test_cv_manual_fold_reference_and_leakage_counterexample(scale):
    rng = np.random.default_rng(847)
    x = rng.normal(size=(24, 3)) * [1., 3., 10.]
    x[-8:] += [20., -13., 50.]
    y = (x @ [1., -2., .1] + rng.normal(size=24))[:, None]
    frame = pd.DataFrame(np.column_stack([x, y]), columns=['a', 'b', 'c', 'y'])
    result = fit_pls(frame, 'y', ['a', 'b', 'c'], n_components=1, cv=3, scale=scale)
    reference = np.zeros(24)
    standardized = np.zeros(24)
    leaked = np.zeros(24)
    for fold, test in enumerate(np.array_split(np.arange(24), 3), 1):
        train = np.setdiff1d(np.arange(24), test)
        # PLS1 的协方差方向闭式解，不运行 NIPALS 或生产内部函数。
        xm, ym = x[train].mean(axis=0), y[train].mean(axis=0)
        xs = x[train].std(axis=0, ddof=1) if scale else np.ones(3)
        yy = y[train]-ym
        xx = (x[train]-xm)/xs
        direction = xx.T @ yy[:, 0]
        score = xx @ direction
        beta = direction[:, None] * (score @ yy)/(score @ score) / xs[:, None]
        reference[test] = ((x[test]-xm) @ beta + ym)[:, 0]
        standardized[test] = (y[test, 0]-reference[test])/y[train, 0].std(ddof=1)
        rows = result.tables['cv_predictions'].query('fold == @fold').sort_values('source_row')
        assert_allclose(rows.predicted, reference[test], atol=1e-9)
        assert_allclose(rows.standardized_residual, standardized[test], atol=1e-9)
        # 错误示例：先在全数据中心化/缩放，再交叉验证。
        global_x = (x-x.mean(axis=0))/(x.std(axis=0, ddof=1) if scale else 1)
        global_y = y-y.mean(axis=0)
        direction = global_x[train].T @ global_y[train, 0]
        score = global_x[train] @ direction
        leaked[test] = (global_x[test] @ direction * (score @ global_y[train, 0]) /
                        (score @ score) + y.mean())
    summary = result.tables['cv'].iloc[0]
    assert_allclose(summary.press, np.sum((y[:, 0]-reference)**2))
    assert_allclose(summary.rmsecv, np.sqrt(np.mean((y[:, 0]-reference)**2)))
    assert_allclose(summary.mean_standardized_press, np.mean(standardized**2))
    assert np.max(abs(reference-leaked)) > .1


def test_automatic_selection_uses_all_y_training_scales(data):
    frame = data.copy()
    frame.z *= 100000
    result = fit_pls(frame, ['y', 'z'], ['a', 'b', 'c', 'd'], max_components=4, cv=5)
    predictions = result.tables['cv_predictions']
    scores = predictions.groupby('n_components').standardized_residual.apply(lambda r: np.mean(r**2))
    assert result.n_components == scores.idxmin()
    assert_allclose(result.tables['cv'].groupby('n_components').mean_standardized_press.first(), scores)
    assert result.tables['cv'].query('selected').n_components.unique().tolist() == [result.n_components]
    assert len(predictions) == len(data)*2*4
    # Y 的单位变化不能改变标准化建模或标准化 PRESS 的选择。
    original = fit_pls(data, ['y', 'z'], ['a', 'b', 'c', 'd'], max_components=4, cv=5)
    assert result.n_components == original.n_components
    assert_allclose(result.tables['cv'].mean_standardized_press,
                    original.tables['cv'].mean_standardized_press, atol=1e-9)


def test_p_greater_than_n_and_rank_boundary():
    rng = np.random.default_rng(13)
    latent = rng.normal(size=(18, 2))
    x = latent @ rng.normal(size=(2, 40))
    y = latent @ [2., -1.] + 4
    frame = pd.DataFrame(x, columns=[f'x{i}' for i in range(40)])
    frame['y'] = y
    result = fit_pls(frame, 'y', list(frame.columns[:-1]), n_components=2, cv=0)
    assert_allclose(result.predict(frame).predicted, y, atol=1e-9)
    assert result.tables['summary'].x_rank.iloc[0] == 2
    with pytest.raises(ValueError, match='数值秩'):
        fit_pls(frame, 'y', list(frame.columns[:-1]), n_components=3, cv=0)
    automatic = fit_pls(frame, 'y', list(frame.columns[:-1]), cv=3, max_components=15)
    assert automatic.tables['cv'].n_components.max() == 2


def test_high_dimensional_full_centered_rank_and_loo():
    rng = np.random.default_rng(681)
    x = rng.normal(size=(9, 15))
    y = rng.normal(size=9)
    frame = pd.DataFrame(x, columns=[f'x{i}' for i in range(15)])
    frame['y'] = y
    result = fit_pls(frame, 'y', list(frame.columns[:-1]), n_components=8, cv=0)
    assert_allclose(result.predict(frame).predicted, y, atol=1e-8)
    automatic = fit_pls(frame, 'y', list(frame.columns[:-1]), max_components=20, cv=9)
    assert automatic.tables['cv'].n_components.max() == 7
    assert automatic.tables['cv_predictions'].fold.nunique() == 9
    with pytest.raises(ValueError, match='训练折可提取'):
        fit_pls(frame, 'y', list(frame.columns[:-1]), n_components=8, cv=9)


def test_missing_source_alignment_no_imputation_and_no_mutation(data):
    frame = data.copy()
    frame.index = ['duplicate'] * len(frame)
    frame.loc[:, 'unused'] = np.nan
    frame.iloc[2, frame.columns.get_loc('a')] = np.nan
    frame.iloc[7, frame.columns.get_loc('y')] = np.nan
    untouched = frame.copy(deep=True)
    with pytest.raises(ValueError, match='缺失值'):
        fit_pls(frame, 'y', ['a', 'b'], n_components=1, cv=0)
    result = fit_pls(frame, ['y', 'z'], ['a', 'b'], n_components=1, cv=0, missing='drop')
    obs = result.tables['observations'].query('response == "y"')
    assert obs.source_row.tolist() == [i for i in range(1, 46) if i not in (3, 8)]
    assert obs.source_index.tolist() == ['duplicate']*43
    # 新数据没有 Y 列；只依赖 X 的完整行，与拟合缺失行规则分开。
    predicted = result.predict(frame[['a', 'b']])
    assert predicted.query('response == "y"').source_row.tolist() == [i for i in range(1, 46) if i != 3]
    pd.testing.assert_frame_equal(frame, untouched)


@pytest.mark.parametrize('kwargs', [
    {'n_components': 0}, {'n_components': 1.5}, {'n_components': True},
    {'n_components': 10}, {'max_components': 0}, {'max_components': 1.2},
    {'cv': 1}, {'cv': 100}, {'cv': -1}, {'cv': 2.5}, {'cv': True},
    {'alpha': 0}, {'alpha': 1}, {'alpha': np.nan}, {'alpha': 'bad'},
    {'missing': 'fill'}, {'scale': 'yes'},
])
def test_invalid_options(data, kwargs):
    options = dict(n_components=1, cv=0)
    options.update(kwargs)
    with pytest.raises(ValueError):
        fit_pls(data, 'y', ['a', 'b'], **options)


def test_disabled_cv_and_zero_covariance(data):
    with pytest.raises(ValueError, match='明确指定'):
        fit_pls(data, 'y', ['a', 'b'], cv=0)
    result = fit_pls(data, 'y', ['a', 'b'], n_components=1, cv=0)
    assert result.tables['cv'].empty and result.tables['cv_predictions'].empty
    orthogonal = pd.DataFrame({'x': [-1., -1., 1., 1.], 'y': [-1., 1., -1., 1.]})
    with pytest.raises(ValueError, match='非零协方差'):
        fit_pls(orthogonal, 'y', ['x'], n_components=1, cv=0)


@pytest.mark.parametrize('kind', ['constant_x', 'constant_y', 'string', 'infinite', 'complex',
                                'duplicate', 'overlap', 'missing_column', 'empty_x', 'all_missing'])
def test_invalid_data(data, kind):
    frame, x = data.copy(), ['a', 'b']
    if kind == 'constant_x':
        frame['a'] = 2.
    elif kind == 'constant_y':
        frame['y'] = 2.
    elif kind == 'string':
        frame['a'] = 'text'
    elif kind == 'infinite':
        frame.loc[0, 'a'] = np.inf
    elif kind == 'complex':
        frame['a'] = frame.a + 1j
    elif kind == 'duplicate':
        x = ['a', 'a']
    elif kind == 'overlap':
        x = ['y']
    elif kind == 'missing_column':
        x = ['absent']
    elif kind == 'empty_x':
        x = []
    elif kind == 'all_missing':
        frame['a'] = np.nan
    with pytest.raises(ValueError):
        fit_pls(frame, 'y', x, n_components=1, cv=0, missing='drop')


def test_cv_fold_constant_response_and_predict_validation(data):
    frame = pd.DataFrame({'x': [1., 2., 3., 4., 5., 6.], 'y': [1., 2., 2., 2., 2., 2.]})
    with pytest.raises(ValueError, match='训练响应为常量'):
        fit_pls(frame, 'y', ['x'], n_components=1, cv=3)
    result = fit_pls(data, 'y', ['a', 'b'], n_components=1, cv=0)
    for kwargs in ({'weight': 'a'}, {'alpha': 0}):
        with pytest.raises(ValueError):
            result.predict(data, **kwargs)
    with pytest.raises(ValueError, match='缺少列'):
        result.predict(data[['a']])


def test_result_contract_and_cancellation(data):
    result = fit_pls(data, 'y', ['a', 'b'], n_components=1, cv=0)
    assert result.model == 'PLS'
    assert result.equation.startswith('y = ')
    assert result.notes
    assert set(result.tables) == {'summary', 'coefficients', 'observations', 'x_scores', 'y_scores',
                                  'x_loadings', 'y_loadings', 'variance', 'vip', 'cv', 'cv_predictions'}
    event = Event()
    event.set()
    with pytest.raises(InterruptedError):
        fit_pls(data, 'y', ['a', 'b'], cancel=event)
    calls = 0

    def cancel():
        nonlocal calls
        calls += 1
        return calls > 9

    original = data.copy(deep=True)
    with pytest.raises(InterruptedError):
        fit_pls(data, ['y', 'z'], ['a', 'b'], cancel=cancel)
    pd.testing.assert_frame_equal(data, original)
    assert_allclose(result.predict(data).predicted, result.tables['observations'].fitted)
