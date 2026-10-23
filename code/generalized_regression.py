"""计数与多类别回归。复用训练设计编码；不使用 Gaussian 拟合指标。"""
from dataclasses import dataclass
from itertools import combinations
import warnings

import numpy as np
import pandas as pd
from scipy import optimize, stats
from scipy.special import xlogy
import statsmodels.api as sm
from statsmodels.miscmodels.ordinal_model import OrderedModel
from statsmodels.tools.sm_exceptions import ConvergenceWarning, PerfectSeparationWarning

from advanced_regression import (_Design, _prepare, _numeric, _rank, _alpha,
                                 _cancel, _coefficient_table)


def _probabilities(values):
    values = np.asarray(values)
    if (not np.isfinite(values).all() or np.any(values < 0) or
            not np.allclose(values.sum(axis=1), 1, atol=1e-10, rtol=0)):
        raise ValueError('类别概率无效：必须非负、有限且逐行和为 1。')
    return values


def _separation(matrix, response, classes, cancel):
    """多项模型有限 MLE 条件：不存在提高至少一个类别对比的衰退方向。"""
    _cancel(cancel)
    n, p = matrix.shape
    rows = []
    for i in range(n):
        for j in range(classes):
            if j == response[i]:
                continue
            row = np.zeros((classes-1, p))
            if response[i]:
                row[response[i]-1] += matrix[i]
            if j:
                row[j-1] -= matrix[i]
            rows.append(row.ravel())
    margins = np.asarray(rows)
    solution = optimize.linprog(-margins.sum(axis=0), A_ub=-margins,
                               b_ub=np.zeros(len(margins)), bounds=(-1, 1), method='highs')
    _cancel(cancel)
    if not solution.success:
        raise ValueError('无法检查类别分离，请检查数据尺度。')
    if -solution.fun > 1e-7:
        raise ValueError('响应存在完全或准完全分离，没有有限的极大似然估计。')


def _ordinal_separation(matrix, response, classes, cancel):
    """累积阈值模型的非负衰退方向，含阈值排序约束。"""
    _cancel(cancel)
    p = matrix.shape[1]
    rows = []
    for values, category in zip(matrix, response):
        if category:
            row = np.r_[values, np.zeros(classes-1)]
            row[p+category-1] = -1
            rows.append(row)
        if category < classes-1:
            row = np.r_[-values, np.zeros(classes-1)]
            row[p+category] = 1
            rows.append(row)
    for k in range(classes-2):
        row = np.zeros(p+classes-1)
        row[p+k], row[p+k+1] = -1, 1
        rows.append(row)
    margins = np.asarray(rows)
    solution = optimize.linprog(-margins.sum(axis=0), A_ub=-margins,
        b_ub=np.zeros(len(margins)), bounds=(-1, 1), method='highs')
    _cancel(cancel)
    if not solution.success:
        raise ValueError('无法检查有序类别分离，请检查数据尺度。')
    if -solution.fun > 1e-7:
        raise ValueError('有序响应存在完全或准完全分离，没有有限的极大似然估计。')


@dataclass
class GeneralizedResult:
    tables: dict
    notes: list
    equation: str
    model: str
    _fit: object
    _design: object
    _missing: str
    _levels: list
    _link: str

    def predict(self, df, alpha=.05, weight=None):
        _alpha(alpha)
        if weight is not None:
            raise ValueError('此模型不接受预测权重。')
        design = self._design
        data, source, _ = _prepare(df, design.variables,
            [c for c in design.variables if c not in design.categorical], None, self._missing)
        matrix, _ = design.matrix(data, design.groups)
        if self.model == 'Poisson':
            eta = matrix @ self._fit.params
            variance = np.einsum('ij,jk,ik->i', matrix, self._fit.cov_params(), matrix)
            margin = stats.norm.ppf(1-alpha/2)*np.sqrt(np.maximum(variance, 0))
            if self._link != 'log' and np.any(eta <= 0):
                raise ValueError('预测超出链接定义域：identity/sqrt 的线性预测量必须为正。')
            inverse = self._fit.model.family.link.inverse
            mean = inverse(eta)
            lower_eta = eta-margin if self._link == 'log' else np.maximum(0, eta-margin)
            source['predicted'] = mean
            source['mean_ci_lower'] = inverse(lower_eta)
            source['mean_ci_upper'] = inverse(eta+margin)
            if not np.isfinite(source.iloc[:, 2:].to_numpy(dtype=float)).all():
                raise ValueError('预测溢出，请检查数据尺度。')
            # Conditional Poisson quantiles omit parameter uncertainty; do not label them PI.
            source['conditional_lower'] = stats.poisson.ppf(alpha/2, mean)
            source['conditional_upper'] = stats.poisson.ppf(1-alpha/2, mean)
        else:
            probability = _probabilities(self._fit.predict(matrix[:, 1:] if self.model == 'Ordinal' else matrix))
            source['predicted_class'] = [self._levels[i] for i in probability.argmax(axis=1)]
            for i in range(len(self._levels)):
                source[f'probability_{i}'] = probability[:, i]
        return source


def fit_generalized(df, y, x, model, *, categorical=(), degree=1, interactions=False,
                    missing='error', alpha=.05, link=None, reference=None, order=None,
                    weight=None, selection='none', cancel=None):
    _alpha(alpha)
    _cancel(cancel)
    x = [x] if isinstance(x, str) else list(x)
    if not x or len(set(x)) != len(x) or y in x:
        raise ValueError('请选择不重复、且不包含 Y 的解释变量 X。')
    if not set(categorical).issubset(x):
        raise ValueError('分类变量必须属于所选 X。')
    if type(degree) is not int or degree not in (1, 2, 3):
        raise ValueError('degree 必须为 1、2 或 3。')
    if missing not in ('error', 'drop'):
        raise ValueError('missing 必须为 error 或 drop。')
    if weight is not None or selection != 'none':
        raise ValueError('计数/多类别模型暂不支持权重或变量筛选；请清空权重并选择不筛选。')
    numeric = [c for c in x if c not in categorical] + ([y] if model == 'Poisson' else [])
    data, source, _ = _prepare(df, [y]+x, numeric, None, missing)
    if isinstance(interactions, (bool, np.bool_)):
        pairs = list(combinations(x, 2)) if interactions else []
    else:
        pairs = []
        for pair in interactions:
            if len(pair) != 2 or pair[0] == pair[1] or not set(pair).issubset(x):
                raise ValueError('交互项必须为所选 X 中不同变量的二元组。')
            canonical = tuple(c for c in x if c in pair)
            if canonical not in pairs:
                pairs.append(canonical)
    design = _Design(x, tuple(categorical), degree, pairs)
    design.learn(data)
    matrix, names = design.matrix(data, design.groups)
    _rank(matrix)
    notes = [f'缺失策略：{missing}；保留 {len(data)}/{len(df)} 行；无自动填补。',
             '分类预测量采用 0/1 哑变量，基准为训练中首次出现的水平；新数据固定使用训练编码。',
             '系数为渐近 Wald 双侧零假设检验及区间；拟合统计量不使用 OLS R²、ANOVA 或正态残差检验。']
    for c, levels in design.levels.items():
        notes.append(f'{c!r}：基准 {levels[0]!r}；水平 {levels!r}。')
    tables = {}
    levels = []
    response = _numeric(data[y]) if model == 'Poisson' else None
    if model == 'Poisson':
        link = link or 'log'
        links = {'log': sm.families.links.Log, 'sqrt': sm.families.links.Sqrt,
                 'identity': sm.families.links.Identity}
        if link not in links:
            raise ValueError('Poisson 链接必须为 log、sqrt 或 identity。')
        if np.any(response < 0) or np.any(response != np.floor(response)) or not response.sum():
            raise ValueError('Poisson 响应必须为非负整数，且至少有一个正计数。')
        # All-zero patterns produce a boundary estimate, even when other counts are positive.
        zero = response == 0
        boundary = optimize.linprog(matrix[zero].sum(axis=0), A_ub=matrix[zero],
            b_ub=np.zeros(zero.sum()), A_eq=matrix[~zero], b_eq=np.zeros((~zero).sum()),
            bounds=(-1, 1), method='highs') if zero.any() else None
        if boundary is not None and boundary.success and boundary.fun < -1e-7:
            raise ValueError('Poisson 存在零计数分离，参数没有有限极大似然估计。')
        estimator = sm.GLM(response, matrix, family=sm.families.Poisson(link=links[link](), check_link=False))
    else:
        present = list(pd.unique(data[y]))
        if len(present) < 3:
            raise ValueError('名义/有序 Logistic 响应必须至少包含 3 个类别。')
        if model == 'Nominal':
            if reference is None or reference not in present:
                raise ValueError('请明确指定响应的参考类别，且该类别须存在于训练数据。')
            if link not in (None, 'logit'):
                raise ValueError('名义 Logistic 仅支持基准类别 logit 链接。')
            levels = [reference] + [c for c in present if c != reference]
            link = 'logit'
        else:
            if order is None or len(order) != len(present) or len(set(order)) != len(order) or set(order) != set(present):
                raise ValueError('有序响应必须明确提供每个类别恰好一次的完整类别顺序。')
            levels = list(order)
            link = link or 'logit'
            if link not in ('logit', 'probit'):
                raise ValueError('有序模型链接必须为 logit 或 probit。')
        response = pd.Categorical(data[y], categories=levels, ordered=True).codes
        if model == 'Nominal':
            _separation(matrix, response, len(levels), cancel)
            estimator = sm.MNLogit(response, matrix)
        else:
            _ordinal_separation(matrix[:, 1:], response, len(levels), cancel)
            estimator = OrderedModel(response, matrix[:, 1:], distr=link)
        tables['response_levels'] = pd.DataFrame({'category_code': np.arange(len(levels)),
            'category': levels, 'reference': [model == 'Nominal' and i == 0 for i in range(len(levels))]})
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', ConvergenceWarning)
            # Poisson 正计数完美拟合仍可具有有限 MLE；零计数边界已在拟合前检查。
            warnings.simplefilter('ignore' if model == 'Poisson' else 'error', PerfectSeparationWarning)
            warnings.simplefilter('error', RuntimeWarning)
            if model == 'Poisson':
                fit = estimator.fit(maxiter=200, tol=1e-10)
                converged = fit.converged
            else:
                fit = estimator.fit(method='bfgs', disp=False, maxiter=1000,
                    gtol=1e-8, callback=lambda params: _cancel(cancel))
                converged = fit.mle_retvals['converged']
            covariance = np.asarray(fit.cov_params())
    except (np.linalg.LinAlgError, ConvergenceWarning, PerfectSeparationWarning, RuntimeWarning) as exc:
        raise ValueError('模型未收敛或不可识别；请检查类别分离、共线性及数据尺度。') from exc
    _cancel(cancel)
    if not converged or not np.isfinite(fit.params).all() or not np.isfinite(covariance).all():
        raise ValueError('模型未收敛或参数协方差无效；请检查分离与可识别性。')
    n = len(data)
    parameter_count = np.asarray(fit.params).size
    if n <= parameter_count:
        raise ValueError('样本量必须大于待估参数数目。')
    metrics = dict(model=model, n_obs=n, n_parameters=parameter_count,
        df_resid=n-parameter_count, log_likelihood=float(fit.llf),
        aic=-2*fit.llf+2*parameter_count, bic=-2*fit.llf+np.log(n)*parameter_count)
    if model == 'Poisson':
        fitted = fit.predict()
        eta = matrix @ fit.params
        if np.any(fitted <= 0) or (link != 'log' and np.any(eta <= 0)):
            raise ValueError('Poisson 拟合超出链接定义域，均值和 identity/sqrt 线性预测量须为正。')
        p = parameter_count
        pearson = (response-fitted)/np.sqrt(fitted)
        deviance = np.sign(response-fitted)*np.sqrt(np.maximum(0,
            2*(xlogy(response, response/fitted)-(response-fitted))))
        influence = fit.get_influence()
        source['actual'], source['fitted'], source['residual'] = response, fitted, response-fitted
        source['pearson_residual'], source['deviance_residual'] = pearson, deviance
        source['standardized_residual'] = influence.resid_studentized
        source['leverage'], source['cooks_distance'] = influence.hat_matrix_diag, influence.cooks_distance[0]
        dispersion = float(pearson @ pearson/(n-p))
        metrics.update(deviance=float(fit.deviance), pearson_chi2=float(pearson @ pearson), dispersion=dispersion)
        diagnostics = [('Deviance', fit.deviance, stats.chi2.sf(fit.deviance, n-p), '渐近 χ² 上尾；稀疏计数近似可能不准。'),
            ('Pearson', pearson @ pearson, stats.chi2.sf(pearson @ pearson, n-p), 'H0: Poisson 方差等于均值；渐近 χ² 上尾。')]
        tables['coefficients'] = _coefficient_table(names, np.asarray(fit.params), covariance, n-p, alpha, True)
        if dispersion > 1.5 or diagnostics[1][2] < alpha:
            notes.append(f'模型适用性警告：Pearson χ²/df={dispersion:.5g}，可能过度离散或模型失配；未自动调整标准误。')
        notes.append('deviance/Pearson 残差不假定正态；计数条件分位数 conditional_lower/upper 不含参数估计不确定性，不能视为完整观测预测区间。')
        if link != 'log':
            notes.append('sqrt/identity 的均值 Wald 区间先与非负链接域闭包求交再反变换，下限可为 0；预测点本身仍要求严格正的线性预测量。')
        equation = f'{link}(E[{y}]) = ' + ' + '.join(f'({v:.10g})*{k}' for k, v in zip(names, fit.params))
    else:
        probability = _probabilities(fit.predict())
        predicted = probability.argmax(axis=1)
        chosen = probability[np.arange(n), response]
        source['actual'], source['fitted'] = data[y].to_numpy(), [levels[i] for i in predicted]
        source['predicted_class'] = source['fitted']
        source['negative_log_probability'] = -np.log(np.maximum(chosen, np.finfo(float).tiny))
        source['probability_actual'] = chosen
        source['misclassified'] = response != predicted
        probs = source[['source_row', 'source_index']].copy()
        for i in range(len(levels)):
            probs[f'probability_{i}'] = probability[:, i]
        tables['probabilities'] = probs
        tables['confusion'] = pd.DataFrame([(a, b, int(np.sum((response == i)&(predicted == j))))
            for i, a in enumerate(levels) for j, b in enumerate(levels)], columns=['actual', 'predicted_class', 'count'])
        null_ll = np.sum(xlogy(np.bincount(response), np.bincount(response)/n))
        lr = max(0., 2*(fit.llf-null_ll))
        diagnostics = [('Likelihood ratio', lr, stats.chi2.sf(lr, parameter_count-(len(levels)-1)),
            'H0: 全部斜率为零；相对相同类别的仅阈值/截距模型，渐近 χ² 上尾。')]
        metrics.update(pseudo_r_squared=1-fit.llf/null_ll, accuracy=float(np.mean(response == predicted)),
                       log_loss=float(-fit.llf/n), brier_score=float(np.mean(np.sum((np.eye(len(levels))[response]-probability)**2, axis=1))))
        if model == 'Nominal':
            flat = np.asarray(fit.params).ravel(order='F')
            labels = [f'{level!r} vs {levels[0]!r}: {name}' for level in levels[1:] for name in names]
            tables['coefficients'] = _coefficient_table(labels, flat, covariance, n-parameter_count, alpha, True)
            equation = f'log(P({y}=类别)/P({y}={levels[0]!r})) = Xβ；系数按非参考类别分组。'
        else:
            slopes = len(names)-1
            tables['coefficients'] = _coefficient_table(names[1:], np.asarray(fit.params[:slopes]),
                covariance[:slopes, :slopes], n-parameter_count, alpha, True)
            raw = np.asarray(fit.params[slopes:])
            thresholds = fit.model.transform_threshold_params(fit.params)[1:-1]
            jac = np.zeros((len(raw), parameter_count))
            for i in range(len(raw)):
                jac[i, slopes] = 1
                jac[i, slopes+1:slopes+i+1] = np.exp(raw[1:i+1])
            threshold_cov = jac @ covariance @ jac.T
            tables['thresholds'] = _coefficient_table([f'{levels[i]!r} | {levels[i+1]!r}' for i in range(len(raw))],
                thresholds, threshold_cov, n-parameter_count, alpha, True)
            cumulative = probability.cumsum(axis=1)
            if np.any(np.diff(thresholds) <= 0) or np.any(np.diff(cumulative, axis=1) < -1e-12):
                raise ValueError('有序阈值或累积概率不单调。')
            notes.append('累积模型 g(P(Y≤类别k))=阈值k−Xβ；与采用 +Xβ 的软件斜率符号相反。logit 为比例优势，probit 为平行正态累积模型；本次未执行比例优势假设检验。')
            equation = f'{link}(P({y}≤类别k)) = 阈值k − Xβ；类别顺序：{levels!r}'
        notes.append('分类矩阵、准确率、Brier 和对数损失为训练集描述，不能作为泛化能力证据。')
    tables['summary'] = pd.DataFrame([metrics])
    tables['diagnostics'] = pd.DataFrame(diagnostics, columns=['test', 'statistic', 'p_value', 'definition'])
    tables['observations'] = source
    return GeneralizedResult(tables, notes, equation, model, fit, design, missing, levels, link)
