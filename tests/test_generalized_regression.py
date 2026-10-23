"""独立解析/似然参考；不以 statsmodels 自身输出作为唯一基准。"""
from threading import Event

import numpy as np
import pandas as pd
import pytest
from numpy.testing import assert_allclose
from scipy import optimize, stats
from scipy.special import expit, gammaln, xlogy

from advanced_regression import fit_regression


@pytest.mark.parametrize('link', ['log', 'sqrt', 'identity'])
def test_poisson_group_rates_independent_mle_and_information(link):
    y = np.array([1, 2, 3, 2, 2, 4, 5, 3, 4, 4.])
    group = np.repeat(['a', 'b'], 5)
    frame = pd.DataFrame(dict(y=y, group=group))
    result = fit_regression(frame, 'y', ['group'], model='Poisson', categorical=['group'], link=link)
    rates = np.array([y[:5].mean(), y[5:].mean()])
    transform = {'log': np.log, 'sqrt': np.sqrt, 'identity': lambda a: a}[link]
    expected = transform(rates)
    assert_allclose(result.tables['coefficients'].estimate, [expected[0], expected[1]-expected[0]], atol=1e-8)
    fitted = np.repeat(rates, 5)
    ll = np.sum(y*np.log(fitted)-fitted-gammaln(y+1))
    summary = result.tables['summary'].iloc[0]
    assert_allclose(summary.log_likelihood, ll, atol=1e-10)
    assert_allclose(summary.aic, -2*ll+4)
    assert_allclose(summary.bic, -2*ll+2*np.log(len(y)))
    assert_allclose(summary.deviance, 2*np.sum(xlogy(y, y/fitted)-(y-fitted)))
    assert_allclose(summary.pearson_chi2, np.sum((y-fitted)**2/fitted))
    prediction = result.predict(frame)
    assert_allclose(prediction.predicted, fitted)
    assert (prediction.mean_ci_lower < prediction.predicted).all()
    assert (prediction.mean_ci_upper > prediction.predicted).all()
    design = np.column_stack([np.ones(10), np.repeat([0, 1], 5)])
    derivative = {'log': fitted, 'sqrt': 2*np.sqrt(fitted), 'identity': np.ones(10)}[link]
    cov = np.linalg.inv(design.T @ ((derivative**2/fitted)[:, None]*design))
    assert_allclose(result.tables['coefficients'].std_error, np.sqrt(cov.diagonal()), rtol=1e-6)
    margin = stats.norm.ppf(.975)*np.sqrt(np.einsum('ij,jk,ik->i', design, cov, design))
    inverse = {'log': np.exp, 'sqrt': np.square, 'identity': lambda a: a}[link]
    low = transform(fitted)-margin
    if link != 'log':
        low = np.maximum(0, low)
    assert_allclose(prediction.mean_ci_lower, inverse(low), rtol=1e-6)
    assert not {'r_squared', 'sse', 'rmse'} & set(result.tables['summary'])


def test_nominal_group_probabilities_coefficients_and_reordered_prediction():
    counts = [[9, 6, 5], [5, 8, 7]]
    frame = pd.DataFrame([(g, c) for g, row in zip(['b', 'a'], counts)
                          for c, count in zip(['red', 'blue', 'green'], row) for _ in range(count)],
                         columns=['group', 'y'])
    result = fit_regression(frame, 'y', ['group'], model='Nominal', categorical=['group'], reference='blue')
    rates = np.array(counts)[:, [1, 0, 2]]/20
    logs = np.log(rates[:, 1:]/rates[:, :1])
    expected = np.array([logs[0, 0], logs[1, 0]-logs[0, 0], logs[0, 1], logs[1, 1]-logs[0, 1]])
    assert_allclose(result.tables['coefficients'].estimate, expected, atol=2e-6)
    pred = result.predict(pd.DataFrame({'group': ['a', 'b', 'a']}, index=['02', '01', '03']))
    assert_allclose(pred.filter(like='probability_'), rates[[1, 0, 1]], atol=2e-7)
    assert pred.source_index.tolist() == ['02', '01', '03']
    assert result.tables['confusion']['count'].sum() == len(frame)
    ll = np.sum(np.array(counts)[:, [1, 0, 2]] * np.log(rates))
    assert_allclose(result.tables['summary'].log_likelihood.iloc[0], ll, atol=1e-9)
    with pytest.raises(ValueError, match='训练中没有'):
        result.predict(pd.DataFrame({'group': ['unseen']}))


@pytest.mark.parametrize('link', ['logit', 'probit'])
def test_ordinal_against_independent_cumulative_likelihood(link):
    rng = np.random.default_rng(709)
    x = rng.normal(size=450)
    latent = .65*x + (rng.logistic(size=len(x)) if link == 'logit' else rng.normal(size=len(x)))
    codes = np.digitize(latent, [-.7, .9])
    levels = ['小', '中', '大']
    frame = pd.DataFrame({'x': x, 'y': np.array(levels)[codes]})
    result = fit_regression(frame, 'y', ['x'], model='Ordinal', order=levels, link=link)
    cdf = expit if link == 'logit' else stats.norm.cdf

    def probability(par, xx):
        lower, upper = par[1], par[1]+np.exp(par[2])
        cumulative = cdf(np.array([lower, upper])[None, :]-par[0]*xx[:, None])
        return np.diff(np.column_stack([np.zeros(len(xx)), cumulative, np.ones(len(xx))]), axis=1)

    def loss(par):
        return -np.log(np.maximum(probability(par, x)[np.arange(len(x)), codes], 1e-300)).sum()

    reference = optimize.minimize(loss, [.5, -.5, .5], method='Nelder-Mead',
                                  options={'xatol': 1e-10, 'maxiter': 4000})
    assert reference.success
    assert_allclose(result.tables['coefficients'].estimate, reference.x[:1], atol=2e-5)
    assert_allclose(result.tables['thresholds'].estimate,
                    [reference.x[1], reference.x[1]+np.exp(reference.x[2])], atol=2e-5)
    predicted = result.predict(frame).filter(like='probability_').to_numpy()
    assert_allclose(predicted, probability(reference.x, x), atol=5e-6)
    assert_allclose(predicted.sum(axis=1), 1, atol=1e-12)
    assert_allclose(result.tables['summary'].log_likelihood.iloc[0], -reference.fun, atol=1e-7)


def test_poisson_domains_dispersion_and_count_validation():
    rng = np.random.default_rng(317)
    frame = pd.DataFrame({'x': rng.normal(size=180), 'y': rng.negative_binomial(1, .2, 180)})
    result = fit_regression(frame, 'y', ['x'], model='Poisson')
    assert any('过度离散' in note for note in result.notes)
    for value in (-1, .5, np.inf):
        invalid = frame.copy()
        invalid['y'] = invalid.y.astype(float)
        invalid.loc[0, 'y'] = value
        with pytest.raises(ValueError):
            fit_regression(invalid, 'y', ['x'], model='Poisson')
    boundary = pd.DataFrame({'x': [0]*8+[1]*8, 'y': [0]*8+[1, 2]*4})
    with pytest.raises(ValueError, match='分离'):
        fit_regression(boundary, 'y', ['x'], model='Poisson')
    grouped = pd.DataFrame({'x': [0]*5+[1]*5, 'y': [1, 2, 3, 2, 2, 4, 5, 3, 4, 4]})
    for link in ('sqrt', 'identity'):
        model = fit_regression(grouped, 'y', ['x'], model='Poisson', link=link)
        with pytest.raises(ValueError, match='链接定义域'):
            model.predict(pd.DataFrame({'x': [-100]}))


def test_poisson_model_terms_against_independent_likelihood():
    rng = np.random.default_rng(5381)
    x = rng.normal(size=240)
    group = rng.choice(['a', 'b'], len(x))
    # Ensure the training reference is a; construct the independent matrix explicitly.
    group[0] = 'a'
    flag = (group == 'b').astype(float)
    matrix = np.column_stack([np.ones(len(x)), x, x*x, flag, x*flag])
    y = rng.poisson(np.exp(matrix @ [.3, .25, .1, -.2, .15]))
    frame = pd.DataFrame({'x': x, 'group': group, 'y': y})
    result = fit_regression(frame, 'y', ['x', 'group'], model='Poisson',
                            categorical=['group'], degree=2, interactions=True)

    def objective(beta):
        eta = matrix @ beta
        return np.sum(np.exp(eta)-y*eta)

    reference = optimize.minimize(objective, np.zeros(5), method='BFGS',
        jac=lambda beta: matrix.T @ (np.exp(matrix @ beta)-y), options={'gtol': 1e-7})
    assert np.max(abs(reference.jac)) < 1e-6
    assert_allclose(result.tables['coefficients'].estimate, reference.x, atol=1e-7)
    expected_cov = np.linalg.inv(matrix.T @ (np.exp(matrix @ reference.x)[:, None]*matrix))
    assert_allclose(result.tables['coefficients'].std_error, np.sqrt(expected_cov.diagonal()), rtol=1e-6)
    assert_allclose(result.predict(frame).predicted, np.exp(matrix @ reference.x), atol=1e-6)


def test_missing_order_separation_and_invalid_options():
    rng = np.random.default_rng(379)
    frame = pd.DataFrame({'x': rng.normal(size=90), 'y': np.tile(['a', 'b', 'c'], 30)})
    for order in (None, ['a', 'b'], ['a', 'a', 'c'], ['b', 'a', 'unseen']):
        with pytest.raises(ValueError, match='类别顺序'):
            fit_regression(frame, 'y', ['x'], model='Ordinal', order=order)
    with pytest.raises(ValueError, match='参考类别'):
        fit_regression(frame, 'y', ['x'], model='Nominal')
    separated = pd.DataFrame({'x': [-2]*10+[0]*10+[2]*10, 'y': ['a']*10+['b']*10+['c']*10})
    with pytest.raises(ValueError, match='分离'):
        fit_regression(separated, 'y', ['x'], model='Nominal', reference='a')
    with pytest.raises(ValueError, match='分离'):
        fit_regression(separated, 'y', ['x'], model='Ordinal', order=['a', 'b', 'c'])
    frame.loc[4, 'x'] = np.nan
    with pytest.raises(ValueError, match='缺失'):
        fit_regression(frame, 'y', ['x'], model='Nominal', reference='a')
    result = fit_regression(frame, 'y', ['x'], model='Nominal', reference='a', missing='drop')
    assert 5 not in result.tables['observations'].source_row.tolist()
    frame['other'] = frame.x
    with pytest.raises(ValueError, match='奇异'):
        fit_regression(frame.dropna(), 'y', ['x', 'other'], model='Ordinal', order=['a', 'b', 'c'])
    for kwargs in ({'weight': np.ones(90)}, {'selection': 'best'}):
        with pytest.raises(ValueError, match='权重或变量筛选'):
            fit_regression(frame, 'y', ['x'], model='Nominal', reference='a', **kwargs)
    cancelled = Event()
    cancelled.set()
    with pytest.raises(InterruptedError):
        fit_regression(frame, 'y', ['x'], model='Poisson', cancel=cancelled)
