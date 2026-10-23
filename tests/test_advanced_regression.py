"""逐方法独立参考（均经 fit_regression 生产入口）：

OLS/WLS → 正规方程/投影矩阵与 Student/F 分布公式；白化诊断 → 残差平方
辅助回归 nR²、DW 定义。Logistic → 独立 Bernoulli 负对数似然优化及其解析
Hessian，AUC → 全部正负样本对的胜率（并列计半）。筛选 → 独立最小二乘
穷举 Gaussian AIC/BIC/调整 R²。非线性 → 带已知参数且正交于 Jacobian 的
扰动，独立解析 Jacobian 和二次近似区间。边界见参数化异常输入测试。
不调用被测代码的内部函数，不以同一 statsmodels 拟合函数作参考。
"""
from itertools import combinations
from threading import Event

import numpy as np
import pandas as pd
import pytest
from numpy.testing import assert_allclose
from scipy import optimize, stats
from scipy.special import expit

from advanced_regression import fit_regression


@pytest.fixture
def data():
    rng = np.random.default_rng(421)
    x = rng.normal(size=(100, 3))
    return pd.DataFrame(dict(y=2+1.8*x[:, 0]-.7*x[:, 1]+rng.normal(scale=.45, size=100),
                             x=x[:, 0], z=x[:, 1], noise=x[:, 2]),
                        index=[f'样本{i}' for i in range(100)])


def reference_linear(frame, columns, weights=None):
    matrix = np.column_stack([np.ones(len(frame)), frame[columns]])
    response = frame.y.to_numpy()
    w = np.ones(len(frame)) if weights is None else np.asarray(weights)
    gram = matrix.T @ (w[:, None]*matrix)
    inverse = np.linalg.inv(gram)
    params = np.linalg.solve(gram, matrix.T @ (w*response))
    residual = response-matrix @ params
    sse = np.sum(w*residual**2)
    n, p = matrix.shape
    scale = sse/(n-p)
    ll = -.5*n*(np.log(2*np.pi)+1+np.log(sse/n))+.5*np.log(w).sum()
    return matrix, params, inverse, residual, scale, ll


@pytest.mark.parametrize('model', ['OLS', 'WLS'])
def test_linear_report_prediction_and_influence_independent(data, model):
    frame = data.copy()
    frame['weight'] = np.linspace(.3, 3, len(frame))
    w = frame.weight.to_numpy() if model == 'WLS' else np.ones(len(frame))
    result = fit_regression(frame, 'y', ['x', 'z'], model=model,
                            weight='weight' if model == 'WLS' else None)
    matrix, params, inverse, residual, scale, ll = reference_linear(frame, ['x', 'z'], w)
    n, p = matrix.shape
    coef = result.tables['coefficients']
    se = np.sqrt(np.diag(inverse)*scale)
    assert_allclose(coef.estimate, params, rtol=1e-12)
    assert_allclose(coef.std_error, se, rtol=1e-12)
    assert_allclose(coef.statistic, params/se, rtol=1e-12)
    assert_allclose(coef.p_value, 2*stats.t.sf(abs(params/se), n-p), rtol=1e-10)
    assert_allclose(coef.ci_lower, params-stats.t.ppf(.975, n-p)*se)
    summary = result.tables['summary'].iloc[0]
    assert_allclose(summary.log_likelihood, ll)
    assert_allclose(summary.aic, -2*ll+2*(p+1))
    assert_allclose(summary.bic, -2*ll+np.log(n)*(p+1))
    sse = np.sum(w*residual**2)
    sst = np.sum(w*(frame.y-np.average(frame.y, weights=w))**2)
    assert_allclose(summary.r_squared, 1-sse/sst)
    assert_allclose(summary.adj_r_squared, 1-(sse/(n-p))/(sst/(n-1)))
    assert_allclose(summary.rmse, np.sqrt(sse/n))
    anova = result.tables['anova'].set_index('source')
    f_value = (sst-sse)/(p-1)/scale
    assert_allclose(anova.loc['Regression', ['sum_sq', 'statistic', 'p_value']].to_numpy(float),
                    [sst-sse, f_value, stats.f.sf(f_value, p-1, n-p)])
    obs = result.tables['observations']
    white = np.sqrt(w)*residual
    h = w*np.diag(matrix @ inverse @ matrix.T)
    std = white/np.sqrt(scale*(1-h))
    cooks = std**2*h/(p*(1-h))
    assert_allclose(obs.leverage, h)
    assert_allclose(obs.standardized_residual, std, atol=1e-12)
    assert_allclose(obs.cooks_distance, cooks, atol=1e-12)
    assert_allclose(obs.whitened_residual, white, atol=1e-12)
    assert obs.source_index.tolist() == frame.index.tolist()
    assert obs.source_row.tolist() == list(range(1, n+1))
    prediction = result.predict(frame.iloc[[5, 20]], .1, weight='weight' if model == 'WLS' else None)
    new_matrix = matrix[[5, 20]]
    mean = new_matrix @ params
    variance = np.diag(new_matrix @ (inverse*scale) @ new_matrix.T)
    critical = stats.t.ppf(.95, n-p)
    assert_allclose(prediction.predicted, mean)
    assert_allclose(prediction.mean_ci_lower, mean-critical*np.sqrt(variance))
    assert_allclose(prediction.pi_upper, mean+critical*np.sqrt(variance+scale/w[[5, 20]]))
    assert prediction.source_row.tolist() == [1, 2]


def test_wls_diagnostics_whitened_and_vif_reference(data):
    data['w'] = np.linspace(.1, 4., len(data))
    result = fit_regression(data, 'y', ['x', 'z'], model='WLS', weight='w')
    matrix, _, inverse, residual, scale, _ = reference_linear(data, ['x', 'z'], data.w)
    white = residual*np.sqrt(data.w)
    diagnostic = result.tables['diagnostics'].set_index('test')
    assert_allclose(diagnostic.loc['Durbin-Watson', 'statistic'], np.diff(white) @ np.diff(white)/(white @ white))
    shapiro = stats.shapiro(white)
    assert_allclose(diagnostic.loc['Shapiro-Wilk', ['statistic', 'p_value']].to_numpy(float), shapiro)
    # Independent centered projection of squared whitened residuals onto auxiliary regressors.
    z = np.column_stack([np.ones(len(data)), np.sqrt(data.w).to_numpy()[:, None]*matrix])
    aux_beta = np.linalg.solve(z.T @ z, z.T @ (white.to_numpy()**2))
    fitted_squares = z @ aux_beta
    lm = len(data)*np.sum((fitted_squares-np.mean(white**2))**2)/np.sum((white**2-np.mean(white**2))**2)
    assert_allclose(diagnostic.loc['Breusch-Pagan (Koenker)', 'statistic'], lm)
    assert_allclose(diagnostic.loc['Breusch-Pagan (Koenker)', 'p_value'], stats.chi2.sf(lm, 3))
    centered = data[['x', 'z']].to_numpy()-np.average(data[['x', 'z']], axis=0, weights=data.w)
    gram = centered.T @ (data.w.to_numpy()[:, None]*centered)
    assert_allclose(result.tables['vif'].vif, np.diag(gram)*np.diag(np.linalg.inv(gram)))
    no_w = result.predict(data.iloc[:3])
    assert no_w.pi_lower.isna().all()
    assert no_w.mean_ci_lower.notna().all()
    # Reweighting changes the observation interval but not the fitted mean or its CI.
    pred1, pred2 = result.predict(data, weight=data.w), result.predict(data, weight=data.w*10)
    assert_allclose(pred1.mean_ci_lower, pred2.mean_ci_lower)
    assert np.all(pred2.pi_upper < pred1.pi_upper)


def test_design_categorical_cubic_interaction_and_fixed_training_encoding():
    rng = np.random.default_rng(4)
    x = np.linspace(-2, 2, 90)
    category = np.tile(['b', 'a', 'c'], 30)
    a, c = (category == 'a').astype(float), (category == 'c').astype(float)
    matrix = np.column_stack([np.ones(90), x, x*x, x**3, a, c, x*a, x*c])
    beta = np.array([1, 2, .4, -.2, 1.5, -.3, .7, -.8])
    frame = pd.DataFrame(dict(y=matrix @ beta+rng.normal(scale=.05, size=90), x=x, group=category))
    result = fit_regression(frame, 'y', ['x', 'group'], categorical=['group'], degree=3, interactions=True)
    expected = np.linalg.solve(matrix.T @ matrix, matrix.T @ frame.y)
    assert result.tables['coefficients'].term.tolist() == [
        'Intercept', 'x', 'x^2', 'x^3', "group['a']", "group['c']", "x:group['a']", "x:group['c']"]
    assert_allclose(result.tables['coefficients'].estimate, expected)
    new = frame.iloc[[2, 1, 0]].drop(columns='y')
    assert_allclose(result.predict(new).predicted, matrix[[2, 1, 0]] @ expected)
    with pytest.raises(ValueError, match='分类水平'):
        result.predict(pd.DataFrame({'x': [1.], 'group': ['unseen']}))


@pytest.fixture
def logistic_data():
    x = np.tile(np.linspace(-2., 2., 9), 12)
    rng = np.random.default_rng(42)
    return pd.DataFrame({'y': rng.binomial(1, expit(-.3+.75*x)), 'x': x})


def test_logistic_independent_likelihood_hessian_auc_and_intervals(logistic_data):
    frame = logistic_data
    result = fit_regression(frame, 'y', ['x'], model='Logistic')
    matrix = np.column_stack([np.ones(len(frame)), frame.x])
    y = frame.y.to_numpy()

    def loss(beta):
        eta = matrix @ beta
        return np.sum(np.logaddexp(0, eta)-y*eta)

    def gradient(beta):
        return matrix.T @ (expit(matrix @ beta)-y)

    reference = optimize.minimize(loss, [0., 0.], jac=gradient, method='BFGS', tol=1e-10)
    beta = reference.x
    probability = expit(matrix @ beta)
    covariance = np.linalg.inv(matrix.T @ ((probability*(1-probability))[:, None]*matrix))
    coef = result.tables['coefficients']
    assert_allclose(coef.estimate, beta, atol=1e-8)
    assert_allclose(coef.std_error, np.sqrt(np.diag(covariance)), atol=1e-8)
    assert set(coef.statistic_type) == {'z'}
    assert_allclose(coef.p_value, 2*stats.norm.sf(abs(beta/np.sqrt(np.diag(covariance)))), atol=1e-8)
    summary = result.tables['summary'].iloc[0]
    assert_allclose(summary.aic, 2*loss(beta)+4)
    assert_allclose(summary.bic, 2*loss(beta)+2*np.log(len(frame)))
    assert not {'r_squared', 'adj_r_squared', 'rmse', 'sse', 'residual_std'} & set(summary.index)
    assert result.tables['anova'].empty
    positive, negative = probability[y == 1], probability[y == 0]
    auc = np.mean((positive[:, None] > negative)+.5*(positive[:, None] == negative))
    assert_allclose(summary.auc, auc)
    null_ll = np.sum(y*np.log(y.mean())+(1-y)*np.log(1-y.mean()))
    assert_allclose(summary.pseudo_r_squared, 1-(-loss(beta))/null_ll)
    diagnostic = result.tables['diagnostics'].set_index('test')
    lr = 2*(-loss(beta)-null_ll)
    assert_allclose(diagnostic.loc['Likelihood ratio', ['statistic', 'p_value']].to_numpy(float),
                    [lr, stats.chi2.sf(lr, 1)])
    prediction = result.predict(frame, alpha=.1)
    eta = matrix @ beta
    se = np.sqrt(np.diag(matrix @ covariance @ matrix.T))
    assert_allclose(prediction.mean_ci_lower, expit(eta-stats.norm.ppf(.95)*se), atol=1e-8)
    assert_allclose(prediction.mean_ci_upper, expit(eta+stats.norm.ppf(.95)*se), atol=1e-8)
    assert prediction.pi_lower.isna().all()
    assert_allclose(prediction.predicted, probability, atol=1e-8)
    roc = result.tables['roc']
    for row in roc.itertuples():
        pred = probability >= row.threshold-1e-8 if np.isfinite(row.threshold) else np.zeros(len(y), bool)
        assert_allclose(row.fpr, np.mean(pred[y == 0]))
        assert_allclose(row.tpr, np.mean(pred[y == 1]))
    pred = probability >= .5
    classification = result.tables['classification'].iloc[0]
    assert classification.tp == np.sum(pred & (y == 1))
    assert classification.tn == np.sum(~pred & (y == 0))
    assert_allclose(classification.accuracy, np.mean(pred == y))
    # GLM first-order influence defined using Pearson residuals, not OLS residual scale.
    variance = probability*(1-probability)
    h = variance*np.diag(matrix @ covariance @ matrix.T)
    cook = (y-probability)**2/variance*h/(2*(1-h)**2)
    assert_allclose(result.tables['observations'].cooks_distance, cook, atol=1e-8)


def test_roc_ties_are_grouped(logistic_data):
    result = fit_regression(logistic_data, 'y', ['x'], model='Logistic')
    roc = result.tables['roc']
    assert len(roc) == logistic_data.x.nunique()+1
    assert np.all(np.diff(roc.fpr) >= 0)
    assert np.all(np.diff(roc.tpr) >= 0)
    assert_allclose(roc.iloc[-1][['fpr', 'tpr']], [1, 1])


@pytest.mark.parametrize('selection', ['forward', 'backward', 'both', 'best'])
@pytest.mark.parametrize('criterion', ['AIC', 'BIC', 'adjR2'])
@pytest.mark.parametrize('model', ['OLS', 'WLS'])
def test_selection_against_independent_enumeration(data, selection, criterion, model):
    columns = ['x', 'z', 'noise']
    weights = np.linspace(.3, 2, len(data)) if model == 'WLS' else None
    result = fit_regression(data, 'y', columns, selection=selection, criterion=criterion,
                            model=model, weight=weights)
    scores = {}
    for size in range(4):
        for subset in combinations(columns, size):
            _, _, _, residual, scale, ll = reference_linear(data, list(subset), weights)
            p = size+1
            if criterion == 'AIC':
                score = -2*ll+2*(p+1)
            elif criterion == 'BIC':
                score = -2*ll+np.log(len(data))*(p+1)
            else:
                w = np.ones(len(data)) if weights is None else weights
                sst = np.sum(w*(data.y-np.average(data.y, weights=w))**2)
                score = -(1-scale/(sst/(len(data)-1)))
            scores[subset] = score
    expected = min(scores, key=scores.get)
    assert result.selected_terms == tuple((c,) for c in expected)
    comparison = result.tables['comparison']
    assert comparison.selected.sum() == 1
    assert_allclose(comparison.loc[comparison.selected, 'score'].iloc[0], scores[expected])
    # A selected subset's discarded variables are not required for prediction.
    assert result.predict(data[list(expected)]).shape[0] == len(data)


@pytest.mark.parametrize('selection', ['forward', 'backward', 'both', 'best'])
@pytest.mark.parametrize('criterion', ['AIC', 'BIC'])
def test_logistic_selection_independent_likelihood(selection, criterion):
    rng = np.random.default_rng(815)
    x = rng.normal(size=(240, 3))
    y = rng.binomial(1, expit(-.4+1.2*x[:, 0]+.9*x[:, 1]))
    frame = pd.DataFrame({'y': y, 'x': x[:, 0], 'z': x[:, 1], 'noise': x[:, 2]})
    scores = {}
    columns = ['x', 'z', 'noise']
    for size in range(4):
        for chosen in combinations(columns, size):
            matrix = np.column_stack([np.ones(len(y)), frame[list(chosen)]])

            def loss(beta):
                eta = matrix @ beta
                return np.sum(np.logaddexp(0, eta)-y*eta)

            def gradient(beta):
                return matrix.T @ (expit(matrix @ beta)-y)

            fit = optimize.minimize(loss, np.zeros(size+1), jac=gradient, method='BFGS')
            penalty = 2 if criterion == 'AIC' else np.log(len(y))
            scores[chosen] = 2*fit.fun+penalty*(size+1)
    result = fit_regression(frame, 'y', columns, model='Logistic', selection=selection, criterion=criterion)
    expected = min(scores, key=scores.get)
    assert result.selected_terms == tuple((c,) for c in expected)
    row = result.tables['comparison'].loc[lambda t: t.selected].iloc[0]
    assert_allclose(row.score, scores[expected], rtol=1e-9)


@pytest.mark.parametrize('selection', ['forward', 'backward', 'both', 'best'])
def test_selection_preserves_variable_groups_and_strong_hierarchy(selection):
    rng = np.random.default_rng(100)
    x, z = rng.normal(size=(2, 100))
    group = np.tile(['base', 'red', 'blue', 'green'], 25)
    effect = np.select([group == 'red', group == 'blue', group == 'green'], [3., -2., 1.])
    frame = pd.DataFrame({'y': 1+4*x+2*z+3*x*z+.4*x*x+effect+rng.normal(scale=.03, size=100),
                          'x': x, 'z': z, 'group': group})
    result = fit_regression(frame, 'y', ['x', 'z', 'group'], categorical=['group'], degree=2,
                            interactions=[('x', 'z')], selection=selection)
    for candidate in result.tables['comparison'].terms:
        for term in candidate:
            if len(term) == 2:
                assert all((c,) in candidate for c in term)
    terms = result.tables['coefficients'].term.tolist()
    assert all(name in terms for name in ["group['red']", "group['blue']", "group['green']"])
    assert 'x^2' in terms and 'x' in terms


@pytest.mark.parametrize('model,initial,function,jacobian', [
    ('exponential', {'a': 2., 'b': .4, 'c': .7},
     lambda x, a, b, c: a*np.exp(b*x)+c,
     lambda x, a, b, c: np.column_stack([np.exp(b*x), a*x*np.exp(b*x), np.ones(len(x))])),
    ('power', {'a': 1.8, 'b': 1.3},
     lambda x, a, b: a*x**b,
     lambda x, a, b: np.column_stack([x**b, a*x**b*np.log(x)])),
    ('logistic_curve', {'a': 5., 'b': 1.2, 'c': 1.5},
     lambda x, a, b, c: a*expit(b*(x-c)),
     lambda x, a, b, c: np.column_stack([expit(b*(x-c)), a*expit(b*(x-c))*(1-expit(b*(x-c)))*(x-c),
                                          -a*b*expit(b*(x-c))*(1-expit(b*(x-c)))])),
])
def test_nonlinear_analytic_reference_parameters_covariance_prediction(model, initial, function, jacobian):
    x = np.linspace(.2, 3.2, 100)
    beta = np.array(list(initial.values()))
    j = jacobian(x, *beta)
    # An independent disturbance orthogonal to the analytic tangent space gives J'e=0.
    raw_error = .004*np.sin(27*x)
    error = raw_error-j @ np.linalg.lstsq(j, raw_error, rcond=None)[0]
    frame = pd.DataFrame(dict(y=function(x, *beta)+error, x=x))
    result = fit_regression(frame, 'y', ['x'], model=model, initial=initial)
    estimate = result.tables['coefficients'].estimate.to_numpy()
    assert_allclose(estimate, beta, atol=1e-7)
    n, p = j.shape
    scale = error @ error/(n-p)
    cov = np.linalg.inv(j.T @ j)*scale
    assert_allclose(result.tables['coefficients'].std_error, np.sqrt(np.diag(cov)), rtol=1e-5)
    prediction = result.predict(frame.iloc[:4])
    mean = function(x[:4], *beta)
    variance = np.diag(j[:4] @ cov @ j[:4].T)
    critical = stats.t.ppf(.975, n-p)
    assert_allclose(prediction.mean_ci_lower, mean-critical*np.sqrt(variance), rtol=1e-6)
    assert_allclose(prediction.pi_upper, mean+critical*np.sqrt(variance+scale), rtol=1e-6)
    assert result.tables['anova'].empty
    assert result.tables['vif'].empty
    assert 'r_squared' not in result.tables['summary']
    ll = -n/2*(np.log(2*np.pi)+1+np.log((error @ error)/n))
    assert_allclose(result.tables['summary'].aic, [-2*ll+2*(p+1)], atol=1e-6)
    assert any('一阶近似' in note for note in result.notes)


def test_custom_formula_multivariate_and_no_input_mutation(data):
    before = data.copy(deep=True)
    result = fit_regression(data, 'y', ['x', 'z'], model='nonlinear', formula='a+b*x+c*z',
                            initial={'a': 0., 'b': 0., 'c': 0.})
    matrix, beta, _, _, _, _ = reference_linear(data, ['x', 'z'])
    assert_allclose(result.tables['coefficients'].estimate, beta, atol=1e-7)
    assert_allclose(result.predict(data).predicted, matrix @ beta, atol=1e-7)
    pd.testing.assert_frame_equal(before, data)


@pytest.mark.parametrize('formula', [
    '__import__("os").system("echo bad")', 'x.__class__', 'x[0]+a',
    '[a for a in x]', '(lambda: a)()', 'open(x)', 'exp(x, a)', 'exp(x, out=a)',
    'a if x else b', 'a and x', '(a := x)', 'a+"bad"', 'a+True',
    'a+float("inf")', 'np.exp(x)+a',
])
def test_formula_rejects_unsafe_ast(formula):
    frame = pd.DataFrame({'x': [1., 2., 3., 4.], 'y': [1., 4., 8., 15.]})
    with pytest.raises(ValueError):
        fit_regression(frame, 'y', ['x'], model='nonlinear', formula=formula, initial={'a': 1.})


def test_source_rows_missing_duplicate_indices_and_prediction(data):
    frame = data.iloc[:10].copy()
    frame.index = ['duplicate']*len(frame)
    frame.iloc[2, frame.columns.get_loc('x')] = np.nan
    frame.iloc[5, frame.columns.get_loc('y')] = np.nan
    with pytest.raises(ValueError, match='缺失'):
        fit_regression(frame, 'y', ['x', 'z'])
    result = fit_regression(frame, 'y', ['x', 'z'], missing='drop')
    assert result.tables['observations'].source_row.tolist() == [1, 2, 4, 5, 7, 8, 9, 10]
    assert result.tables['observations'].source_index.tolist() == ['duplicate']*8
    prediction = result.predict(frame)
    # Y is not needed for prediction; its missing value must not discard a row.
    assert prediction.source_row.tolist() == [1, 2, 4, 5, 6, 7, 8, 9, 10]
    assert len(result.predict(frame[['x', 'z']])) == 9


@pytest.mark.parametrize('change,kwargs,message', [
    (lambda f: f.assign(x=1.), {}, '常量'),
    (lambda f: f.assign(y=1.), {}, '常量'),
    (lambda f: f.assign(z=f.x), {}, '奇异'),
    (lambda f: f.iloc[:3], {}, '样本量'),
    (lambda f: f.assign(x=np.inf), {}, '无穷'),
    (lambda f: f.assign(x='invalid'), {}, '实数'),
    (lambda f: f, {'degree': 4}, 'degree'),
    (lambda f: f, {'degree': True}, 'degree'),
    (lambda f: f, {'missing': 'fill'}, 'missing'),
    (lambda f: f, {'alpha': 0.}, 'alpha'),
    (lambda f: f, {'alpha': np.nan}, 'alpha'),
    (lambda f: f, {'selection': 'wrong'}, '筛选'),
    (lambda f: f, {'criterion': 'wrong'}, 'criterion'),
    (lambda f: f, {'categorical': ['unknown']}, '分类'),
    (lambda f: f, {'weight': 'noise'}, '仅 WLS'),
    (lambda f: f, {'model': 'WLS'}, '权重'),
    (lambda f: f.assign(w=0.), {'model': 'WLS', 'weight': 'w'}, '正数'),
    (lambda f: f.assign(w=-1.), {'model': 'WLS', 'weight': 'w'}, '正数'),
    (lambda f: f, {'model': 'WLS', 'weight': [1.]}, '等长'),
    (lambda f: f.assign(y=2.), {'model': 'Logistic'}, '0、1'),
    (lambda f: f, {'model': 'Logistic', 'criterion': 'adjR2'}, '不适用'),
    (lambda f: f, {'model': 'nonlinear', 'degree': 2}, '不支持'),
    (lambda f: f, {'interactions': [('x', 'unknown')]}, '交互'),
])
def test_invalid_inputs(data, change, kwargs, message):
    with pytest.raises(ValueError, match=message):
        fit_regression(change(data), 'y', ['x', 'z'], **kwargs)


def test_best_subset_limit_and_cancellation():
    rng = np.random.default_rng(44)
    frame = pd.DataFrame(rng.normal(size=(80, 14)), columns=['y']+[f'x{i}' for i in range(13)])
    with pytest.raises(ValueError, match='搜索超限'):
        fit_regression(frame, 'y', list(frame.columns[1:]), selection='best')
    event = Event()
    event.set()
    with pytest.raises(InterruptedError, match='取消'):
        fit_regression(frame, 'y', ['x0'], cancel=event)
    calls = []

    def cancel():
        calls.append(1)
        return len(calls) > 8

    with pytest.raises(InterruptedError):
        fit_regression(frame, 'y', ['x0', 'x1', 'x2'], selection='best', cancel=cancel)


def test_logistic_complete_separation_is_explicit():
    x = np.linspace(-3, 3, 100)
    frame = pd.DataFrame({'x': x, 'y': (x > 0).astype(int)})
    with pytest.raises(ValueError, match='分离|收敛|识别'):
        fit_regression(frame, 'y', ['x'], model='Logistic')


def test_prediction_validation(data):
    result = fit_regression(data, 'y', ['x', 'z'])
    for bad in [data.assign(x=np.inf), data.assign(x=np.nan), data.drop(columns='z')]:
        with pytest.raises(ValueError):
            result.predict(bad)
    with pytest.raises(ValueError, match='alpha'):
        result.predict(data, alpha=1)
    with pytest.raises(ValueError, match='仅 WLS'):
        result.predict(data, weight='noise')


def test_no_gui_imports_and_table_schema(data):
    result = fit_regression(data, 'y', ['x', 'z'])
    assert set(result.tables) == {'summary', 'coefficients', 'anova', 'diagnostics', 'vif',
                                  'observations', 'comparison', 'classification', 'roc'}
    assert all(isinstance(table, pd.DataFrame) for table in result.tables.values())
    assert result.tables['roc'].columns.tolist() == ['threshold', 'fpr', 'tpr']
    assert not result.tables['observations'].isna().any().any()
    assert result.equation.startswith('y = ')


def test_nonlinear_domain_initial_identifiability_and_cancel():
    frame = pd.DataFrame({'x': np.linspace(-1, 1, 30), 'y': np.linspace(1, 4, 30)})
    with pytest.raises(ValueError, match='初值'):
        fit_regression(frame, 'y', ['x'], model='nonlinear', formula='a*x+b', initial={'a': 1.})
    with pytest.raises(ValueError, match='非有限'):
        fit_regression(frame, 'y', ['x'], model='nonlinear', formula='a*log(x)', initial={'a': 1.})
    with pytest.raises(ValueError, match='奇异'):
        fit_regression(frame, 'y', ['x'], model='nonlinear', formula='(a+b)*x', initial={'a': 1., 'b': 1.})
    count = []

    def cancel():
        count.append(1)
        return len(count) > 4

    with pytest.raises(InterruptedError):
        fit_regression(frame, 'y', ['x'], model='exponential', cancel=cancel)


def test_column_weights_as_predictor_are_borrowed_without_mutation(data):
    frame = data.assign(weight=data.z-data.z.min()+.5)
    original = frame.copy(deep=True)
    weights = frame.weight.to_numpy()
    before = weights.copy()
    result = fit_regression(frame, 'y', ['x', 'weight'], model='WLS', weight='weight')
    predicted = result.predict(frame, weight='weight')
    assert np.isfinite(predicted.pi_upper).all()
    pd.testing.assert_frame_equal(frame, original)
    assert_allclose(weights, before)


def test_builtin_curve_uses_x_alias_for_arbitrary_column_names():
    x = np.linspace(.2, 3, 40)
    frame = pd.DataFrame({'测量 值': x, 'y': 2*x**1.5+.002*np.sin(30*x)})
    result = fit_regression(frame, 'y', ['测量 值'], model='power', initial=[2., 1.5])
    assert_allclose(result.tables['coefficients'].estimate, [2., 1.5], atol=.002)
    assert np.isfinite(result.predict(frame).predicted).all()


def test_intercept_only_selection_and_multiindex_source():
    x = np.tile([-1., 0., 1.], 20)
    y = np.repeat(np.linspace(-1, 2, 20), 3)
    index = pd.MultiIndex.from_arrays([np.arange(len(x))//2, np.arange(len(x))%2])
    frame = pd.DataFrame({'y': y, 'x': x}, index=index)
    result = fit_regression(frame, 'y', ['x'], selection='best', criterion='BIC')
    assert result.selected_terms == ()
    assert result.tables['observations'].source_index.tolist() == list(index)
    prediction = result.predict(pd.DataFrame(index=index[:3]))
    assert_allclose(prediction.predicted, y.mean())
    assert prediction.source_index.tolist() == list(index[:3])
