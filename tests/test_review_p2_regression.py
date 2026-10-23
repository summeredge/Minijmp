"""P2 回归反例：组均值解析 MLE、已知正交主方向、SciPy 曲线参考。"""
import numpy as np
import pandas as pd
import pytest
from numpy.testing import assert_allclose
from scipy.optimize import curve_fit
from scipy.special import gammaln

from advanced_regression import fit_regression


@pytest.mark.parametrize('link', ['log', 'sqrt', 'identity'])
def test_poisson_positive_perfect_fit_and_zero_boundary(link):
    frame = pd.DataFrame({'x': [0, 0, 1, 1], 'y': [1, 1, 2, 2]})
    result = fit_regression(frame, 'y', ['x'], model='Poisson', link=link)
    mu = frame.y.to_numpy(dtype=float)
    transform = {'log': np.log, 'sqrt': np.sqrt, 'identity': lambda a: a}[link]
    eta = transform(np.array([1., 2.]))
    coefficients = result.tables['coefficients']
    assert_allclose(coefficients.estimate, [eta[0], eta[1]-eta[0]], atol=1e-9)
    design = np.column_stack([np.ones(4), frame.x])
    derivative = {'log': mu, 'sqrt': 2*np.sqrt(mu), 'identity': np.ones(4)}[link]
    information = design.T @ ((derivative**2/mu)[:, None]*design)
    assert_allclose(coefficients.std_error, np.sqrt(np.diag(np.linalg.inv(information))), rtol=1e-6)
    assert_allclose(result.predict(frame).predicted, mu, atol=1e-9)
    assert_allclose(result.tables['observations'].fitted, mu, atol=1e-9)
    summary = result.tables['summary'].iloc[0]
    assert_allclose(summary.deviance, 0, atol=1e-12)
    assert_allclose(summary.log_likelihood, np.sum(mu*np.log(mu)-mu-gammaln(mu+1)), atol=1e-10)
    with pytest.raises(ValueError, match='零计数分离'):
        fit_regression(frame.assign(y=[0, 0, 2, 2]), 'y', ['x'], model='Poisson', link=link)


def test_pls_nearby_weak_singular_values_keep_dominant_direction():
    x = np.array([[-1., -1., 1.], [-1., 1., -1.],
                  [1., -1., -1.], [1., 1., 1.]])
    y = np.column_stack([10*x[:, 0], x[:, 1]+.999*x[:, 2], x[:, 1]-.999*x[:, 2]])
    frame = pd.DataFrame(np.column_stack([x, y]), columns=['a', 'b', 'c', 'y', 'z', 'v'])
    result = fit_regression(frame, ['y', 'z', 'v'], ['a', 'b', 'c'],
                            model='PLS', n_components=1, cv=0, scale=False)
    # X 正交：协方差第一方向的强度 40，另两方向均小于 6。
    singular_values = np.linalg.svd(x.T @ y, compute_uv=False)
    assert_allclose(singular_values, [40, 4*np.sqrt(2), .999*4*np.sqrt(2)])
    expected = np.column_stack([10*x[:, 0], np.zeros((4, 2))])
    assert_allclose(result.tables['observations'].fitted.to_numpy().reshape(3, 4).T, expected, atol=1e-12)
    assert_allclose(result.tables['x_scores'].component_1, x[:, 0], atol=1e-12)
    assert_allclose(result.tables['x_loadings'].component_1, [1, 0, 0], atol=1e-12)
    assert_allclose(result.tables['y_loadings'].component_1, [10, 0, 0], atol=1e-12)
    assert_allclose(result.tables['vip'].vip, [np.sqrt(3), 0, 0], atol=1e-12)


@pytest.mark.parametrize('column', ['x', 'a', 'b', 'c', '测量 值'])
@pytest.mark.parametrize('model,function,initial', [
    ('power', lambda x, a, b: a*x**b, [2., 2.]),
    ('exponential', lambda x, a, b, c: a*np.exp(b*x)+c, [2., .3, .5]),
    ('logistic_curve', lambda x, a, b, c: a/(1+np.exp(-b*(x-c))), [8., 1., 2.]),
])
def test_builtin_curve_parameter_names_are_independent_of_column(column, model, function, initial):
    x = np.array([1., 2., 3., 4.])
    y = (np.array([2.1, 7.9, 18.2, 31.8]) if model == 'power'
         else function(x, *initial)+np.array([.02, -.03, .04, -.01]))
    frame = pd.DataFrame({column: x, 'y': y})
    original = frame.copy(deep=True)
    reference, _ = curve_fit(function, x, y, p0=initial)
    result = fit_regression(frame, 'y', [column], model=model, initial=initial)
    assert_allclose(result.tables['coefficients'].estimate, reference, rtol=2e-5, atol=1e-6)
    new_x = np.array([1.5, 2.5, 3.5])
    assert_allclose(result.predict(pd.DataFrame({column: new_x})).predicted,
                    function(new_x, *reference), rtol=2e-6, atol=1e-6)
    pd.testing.assert_frame_equal(frame, original)
