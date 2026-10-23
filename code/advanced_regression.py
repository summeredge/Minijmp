"""纯计算回归；不导入 Tk、不修改输入，也不保存工作表或全局状态。

fit_regression 是生产入口。OLS/WLS/Logistic 显式构造带截距的设计矩阵：
分类变量按训练数据首次出现的水平作基准；一个变量的全部哑变量/1..degree
次幂为一组。两两交互使用一次项（分类变量使用全部哑变量），强层级要求两个
父变量组均入模。最佳子集最多枚举 4096 个组组合，逐步法也最多拟合 4096 次。
筛选在同一完整案例样本上比较，adjR2 不适用于 Logistic。

非线性 model 可为 exponential/power/logistic_curve，分别为
a*exp(b*x)+c、a*x**b、a/(1+exp(-b*(x-c)))；也可为 nonlinear 并提供
formula 和 initial 参数字典。单一自变量可使用别名 x；多变量使用列名。
公式仅允许数值、变量、四则运算、幂及 exp/log/sqrt/sin/cos/tanh/abs。
AST 逐节点解释，不使用 eval/exec/compile。initial 可为常用模型的有序序列。

预测的 source_row/index 属于传入的预测数据；missing 沿用建模策略。
WLS 新观测 PI 必须显式提供同尺度逆方差权重；否则只提供均值 CI，PI 为 NaN。
异常标记是 |内部标准化残差|>2、杠杆>2p/n、Cook>4/n 的探索性提示。
所有检验 p 值均为上尾（Shapiro 原假设正态、BP 原假设同方差）；系数检验
为双侧零系数检验。Durbin-Watson 仅报告统计量，不附近似 p 值。
"""
from __future__ import annotations

import ast
from dataclasses import dataclass, field
from itertools import combinations
import operator
import warnings

import numpy as np
import pandas as pd
from scipy import optimize, stats
from scipy.special import expit
import statsmodels.api as sm
from statsmodels.tools.sm_exceptions import ConvergenceWarning, PerfectSeparationWarning


MAX_CANDIDATES = 4096
TABLE_COLUMNS = {
    'summary': ['model', 'n_obs', 'n_parameters', 'df_resid', 'log_likelihood',
                'aic', 'bic', 'sse', 'rmse', 'residual_std', 'r_squared',
                'adj_r_squared', 'pseudo_r_squared', 'auc'],
    'coefficients': ['term', 'estimate', 'std_error', 'statistic', 'statistic_type',
                     'p_value', 'ci_lower', 'ci_upper'],
    'anova': ['source', 'sum_sq', 'df', 'mean_sq', 'statistic', 'p_value'],
    'diagnostics': ['test', 'statistic', 'p_value', 'definition'],
    'vif': ['term', 'vif'],
    'observations': ['source_row', 'source_index', 'actual', 'fitted', 'residual',
                     'whitened_residual', 'standardized_residual', 'leverage',
                     'cooks_distance', 'outlier', 'high_leverage', 'influential'],
    'comparison': ['terms', 'n_parameters', 'aic', 'bic', 'adj_r_squared',
                   'score', 'selected', 'status'],
    'classification': ['threshold', 'tn', 'fp', 'fn', 'tp', 'accuracy',
                       'precision', 'recall', 'specificity', 'f1', 'auc'],
    'roc': ['threshold', 'fpr', 'tpr'],
}
PREDICTION_COLUMNS = ['source_row', 'source_index', 'predicted', 'mean_ci_lower',
                      'mean_ci_upper', 'pi_lower', 'pi_upper']


def _cancel(cancel):
    if cancel is not None and (cancel.is_set() if hasattr(cancel, 'is_set') else cancel()):
        raise InterruptedError('回归分析已取消。')


def _alpha(alpha):
    if not np.isscalar(alpha) or not np.isfinite(alpha) or not 0 < alpha < 1:
        raise ValueError('alpha 必须在 0 和 1 之间。')


def _numeric(series):
    try:
        values = pd.to_numeric(series, errors='raise')
        if np.iscomplexobj(values):
            raise ValueError('不支持复数。')
        return values.to_numpy(dtype=float, na_value=np.nan)
    except (TypeError, ValueError) as exc:
        raise ValueError(f'列 {series.name!r} 必须为实数数值。') from exc


def _prepare(df, columns, numeric, weight, missing):
    if not isinstance(df, pd.DataFrame) or not df.columns.is_unique:
        raise ValueError('输入必须为列名唯一的 DataFrame。')
    columns = list(dict.fromkeys(columns))
    if isinstance(weight, str):
        columns = list(dict.fromkeys(columns + [weight]))
    absent = [c for c in columns if c not in df.columns]
    if absent:
        raise ValueError(f'缺少列：{absent}')
    mask = df.loc[:, columns].isna().any(axis=1).to_numpy()
    for c in numeric:
        if np.isinf(_numeric(df[c])).any():
            raise ValueError(f'列 {c!r} 含无穷值。')
    w = np.ones(len(df))
    if weight is not None:
        if isinstance(weight, str):
            w = _numeric(df[weight])
        else:
            try:
                w = np.asarray(weight, dtype=float)
            except (TypeError, ValueError) as exc:
                raise ValueError('权重必须为列名或逐行数值。') from exc
            if w.shape != (len(df),):
                raise ValueError('权重必须与输入数据逐行等长。')
        if np.isinf(w).any() or np.any(w[~np.isnan(w)] <= 0):
            raise ValueError('权重必须为有限正数（逆方差）。')
        mask = mask | np.isnan(w)
    if mask.any() and missing == 'error':
        raise ValueError('数据含缺失值；请明确选择 missing="drop" 删除不完整行。')
    keep = np.flatnonzero(~mask)
    if not len(keep):
        raise ValueError('没有可用于分析的完整样本。')
    source = pd.DataFrame({'source_row': keep + 1,
                           'source_index': [df.index[i] for i in keep]})
    return df.iloc[keep].copy(), source, w[keep]


def _rank(matrix, numerical_jacobian=False):
    n, p = matrix.shape
    if n <= p:
        raise ValueError(f'样本量不足：{n} 行，{p} 个参数；需要正的残差自由度。')
    if not np.isfinite(matrix).all():
        raise ValueError('设计矩阵含非有限值；请检查多项式溢出或公式定义域。')
    # Finite-difference Jacobians carry truncation noise, not machine-precision exactness.
    tolerance = (np.sqrt(np.finfo(float).eps)*np.linalg.norm(matrix, 2)
                 if numerical_jacobian else None)
    if np.linalg.matrix_rank(matrix, tol=tolerance) < p:
        raise ValueError('设计矩阵奇异：存在完全共线性、冗余参数或不可识别的项。')


@dataclass
class _Design:
    variables: list
    categorical: tuple
    degree: int
    pairs: list
    levels: dict = field(default_factory=dict)

    def learn(self, df):
        for c in self.variables:
            if c in self.categorical:
                self.levels[c] = list(pd.unique(df[c]))
                constant = len(self.levels[c]) < 2
            else:
                constant = np.ptp(_numeric(df[c])) == 0
            if constant:
                raise ValueError(f'变量 {c!r} 为常量，无法估计独立效应。')

    @property
    def groups(self):
        return [(c,) for c in self.variables] + self.pairs

    def required(self, groups):
        return [c for c in self.variables if any(c in g for g in groups)]

    def matrix(self, df, groups):
        bases, powers = {}, {}
        for c in self.required(groups):
            if c in self.categorical:
                if not df[c].isin(self.levels[c]).all():
                    raise ValueError(f'列 {c!r} 出现训练中没有的分类水平。')
                bases[c] = [(f'{c}[{level!r}]', (df[c] == level).to_numpy(dtype=float))
                            for level in self.levels[c][1:]]
                powers[c] = bases[c]
            else:
                values = _numeric(df[c])
                bases[c] = [(str(c), values)]
                with np.errstate(over='ignore', invalid='ignore'):
                    powers[c] = [(str(c) if d == 1 else f'{c}^{d}', values ** d)
                                 for d in range(1, self.degree + 1)]
        columns = [('Intercept', np.ones(len(df)))]
        for group in self.groups:
            if group not in groups:
                continue
            if len(group) == 1:
                columns.extend(powers[group[0]])
            else:
                a, b = group
                columns.extend((f'{na}:{nb}', va * vb)
                               for na, va in bases[a] for nb, vb in bases[b])
        names = [c[0] for c in columns]
        if len(set(names)) != len(names):
            raise ValueError('展开后的模型项名称重复，请重命名输入列。')
        matrix = np.column_stack([c[1] for c in columns])
        if not np.isfinite(matrix).all():
            raise ValueError('设计矩阵含非有限值，请检查数据范围。')
        return matrix, names


_FUNCTIONS = {'exp': np.exp, 'log': np.log, 'sqrt': np.sqrt, 'sin': np.sin,
              'cos': np.cos, 'tanh': np.tanh, 'abs': np.abs}
_BINARY = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
           ast.Div: operator.truediv, ast.Pow: operator.pow}


class _Formula:
    def __init__(self, formula, variables, initial, *, builtin=False):
        if not isinstance(formula, str) or len(formula) > 2048:
            raise ValueError('公式必须为不超过 2048 字符的表达式。')
        try:
            self.tree = ast.parse(formula, mode='eval').body
        except (SyntaxError, RecursionError) as exc:
            raise ValueError('自定义公式语法错误。') from exc
        nodes = list(ast.walk(self.tree))
        if len(nodes) > 256:
            raise ValueError('公式过于复杂；最多 256 个 AST 节点。')
        allowed = (ast.BinOp, ast.UnaryOp, ast.Call, ast.Name, ast.Load, ast.Constant,
                   ast.UAdd, ast.USub, *_BINARY)
        for node in nodes:
            if not isinstance(node, allowed):
                raise ValueError('公式仅允许数值、变量、算术和白名单函数。')
            if isinstance(node, ast.Constant) and (
                    type(node.value) not in (int, float) or not np.isfinite(float(node.value))):
                raise ValueError('公式常量必须为有限实数。')
            if isinstance(node, ast.Call) and (
                    not isinstance(node.func, ast.Name) or node.func.id not in _FUNCTIONS
                    or len(node.args) != 1 or node.keywords):
                raise ValueError('公式仅允许单参数白名单函数。')
        aliases = {'x'} if builtin else set(variables) | ({'x'} if len(variables) == 1 else set())
        if len(variables) > 1 and not all(isinstance(c, str) and c.isidentifier() for c in variables):
            raise ValueError('多变量自定义公式的列名必须为有效标识符；单变量可使用 x 别名。')
        if len(variables) > 1 and set(variables) & set(_FUNCTIONS):
            raise ValueError('多变量列名不能与公式函数名重复。')
        names = {n.id for n in nodes if isinstance(n, ast.Name)}
        params = names - aliases - set(_FUNCTIONS)
        if not params or not isinstance(initial, dict) or set(initial) != params:
            raise ValueError(f'initial 必须为每个公式参数提供初值，且无多余参数：{sorted(params)}')
        self.params = list(initial)
        self.initial = np.asarray(list(initial.values()), dtype=float)
        if not np.isfinite(self.initial).all():
            raise ValueError('参数初始值必须为有限实数。')
        self.formula, self.variables = formula, variables

    def __call__(self, df, params):
        env = {c: _numeric(df[c]) for c in self.variables}
        if len(self.variables) == 1:
            env['x'] = env[self.variables[0]]
        env.update(zip(self.params, params))

        def visit(node):
            if isinstance(node, ast.Constant):
                return float(node.value)
            if isinstance(node, ast.Name):
                if node.id not in env:
                    raise ValueError(f'公式中的 {node.id!r} 不是数值变量。')
                return env[node.id]
            if isinstance(node, ast.BinOp):
                return _BINARY[type(node.op)](visit(node.left), visit(node.right))
            if isinstance(node, ast.UnaryOp):
                return -visit(node.operand) if isinstance(node.op, ast.USub) else visit(node.operand)
            return _FUNCTIONS[node.func.id](visit(node.args[0]))

        try:
            with np.errstate(all='ignore'):
                values = np.broadcast_to(np.asarray(visit(self.tree), dtype=float), (len(df),))
        except (ValueError, OverflowError, ZeroDivisionError, TypeError) as exc:
            raise ValueError('公式运算失败，请检查初值及定义域。') from exc
        if not np.isfinite(values).all():
            raise ValueError('公式结果非有限值，请检查初值、数据和定义域。')
        return values

    def jacobian(self, df, params):
        columns = []
        for i, value in enumerate(params):
            step = np.cbrt(np.finfo(float).eps) * max(1, abs(value))
            hi, lo = params.copy(), params.copy()
            hi[i] += step
            lo[i] -= step
            columns.append((self(df, hi) - self(df, lo)) / (2 * step))
        return np.column_stack(columns)


def _linear_fit(y, matrix, w, model, cancel):
    _cancel(cancel)
    _rank(matrix * np.sqrt(w)[:, None])
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', PerfectSeparationWarning)
            warnings.simplefilter('error', ConvergenceWarning)
            if model == 'Logistic':
                warnings.simplefilter('error', RuntimeWarning)
                def callback(_):
                    _cancel(cancel)
                fitted = sm.Logit(y, matrix).fit(disp=False, maxiter=200, callback=callback)
                if not fitted.mle_retvals['converged']:
                    raise ValueError('Logistic 迭代未收敛；请检查完全分离或尺度。')
                probability = fitted.predict()
                # The callback checks cancellation instead of statsmodels' separation callback.
                if np.all(np.abs(probability - y) < 1e-8):
                    raise ValueError('Logistic 数据完全分离，没有有限的极大似然估计。')
            else:
                fitted = (sm.WLS(y, matrix, weights=w) if model == 'WLS'
                          else sm.OLS(y, matrix)).fit()
    except (np.linalg.LinAlgError, PerfectSeparationWarning, ConvergenceWarning, RuntimeWarning) as exc:
        raise ValueError('回归不可识别或未收敛；请检查奇异矩阵及 Logistic 完全分离。') from exc
    _cancel(cancel)
    if not np.isfinite(fitted.params).all() or not np.isfinite(fitted.cov_params()).all():
        raise ValueError('回归参数或协方差非有限值。')
    return fitted


def _metrics(fit, model, y, w):
    n, p = len(y), len(fit.params)
    # Gaussian likelihood estimates a variance in addition to p regression parameters.
    k = p if model == 'Logistic' else p + 1
    result = {'model': model, 'n_obs': n, 'n_parameters': p, 'df_resid': n-p,
              'log_likelihood': float(fit.llf), 'aic': -2*fit.llf + 2*k,
              'bic': -2*fit.llf + np.log(n)*k}
    if model == 'Logistic':
        result['pseudo_r_squared'] = float(fit.prsquared)
    else:
        residual = y - fit.predict()
        sse = np.sum(w * residual**2)
        result.update(sse=sse, rmse=np.sqrt(sse/n), residual_std=np.sqrt(sse/(n-p)),
                      r_squared=float(fit.rsquared), adj_r_squared=float(fit.rsquared_adj))
    return result


def _select(design, data, y, w, model, selection, criterion, cancel):
    groups = design.groups
    if selection == 'best' and 2 ** len(groups) > MAX_CANDIDATES:
        raise ValueError(f'最佳子集搜索超限：{len(groups)} 个变量组；最多 {MAX_CANDIDATES} 个组合。')
    rows = {}

    def evaluate(chosen):
        key = tuple(g for g in groups if g in chosen)
        if key not in rows:
            _cancel(cancel)
            if len(rows) >= MAX_CANDIDATES:
                raise ValueError(f'筛选超过 {MAX_CANDIDATES} 次候选拟合，请减少模型项。')
            matrix, _ = design.matrix(data, key)
            row = dict(terms=key, n_parameters=matrix.shape[1], selected=False)
            try:
                fit = _linear_fit(y, matrix, w, model, cancel)
                metrics = _metrics(fit, model, y, w)
                score = (-metrics['adj_r_squared'] if criterion == 'adjR2'
                         else metrics[criterion.lower()])
                row.update({c: metrics.get(c, np.nan) for c in ('aic', 'bic', 'adj_r_squared')})
                row.update(score=score, status='ok')
            except ValueError as exc:
                if selection == 'none':
                    raise
                row.update(score=np.inf, status=str(exc))
            rows[key] = row
        return rows[key]['score']

    def valid(chosen):
        return all(len(g) == 1 or all((c,) in chosen for c in g) for g in chosen)

    current = tuple(groups) if selection in ('none', 'backward') else ()
    evaluate(current)
    if selection == 'best':
        for size in range(len(groups)+1):
            for chosen in combinations(groups, size):
                if valid(chosen):
                    evaluate(chosen)
        current = min(rows, key=lambda key: rows[key]['score'])
    elif selection != 'none':
        while True:
            candidates = []
            for group in groups:
                if group in current and selection in ('backward', 'both'):
                    candidate = tuple(g for g in current if g != group)
                elif group not in current and selection in ('forward', 'both'):
                    candidate = tuple(g for g in groups if g in current or g == group)
                else:
                    continue
                if valid(candidate):
                    evaluate(candidate)
                    candidates.append(candidate)
            if not candidates:
                break
            best = min(candidates, key=lambda key: rows[key]['score'])
            if rows[best]['score'] >= rows[current]['score'] - 1e-10:
                break
            current = best
    if rows[current]['status'] != 'ok':
        raise ValueError(f'没有可拟合的候选模型：{rows[current]["status"]}')
    rows[current]['selected'] = True
    # Keep only scalar comparisons, not thousands of candidate models and their data matrices.
    matrix, _ = design.matrix(data, current)
    final_fit = _linear_fit(y, matrix, w, model, cancel)
    return final_fit, current, pd.DataFrame(rows.values(), columns=TABLE_COLUMNS['comparison'])


def _coefficient_table(names, params, covariance, df_resid, alpha, logistic=False):
    se = np.sqrt(np.maximum(0, np.diag(covariance)))
    statistic = np.divide(params, se, out=np.full(len(params), np.nan), where=se > 0)
    distribution = stats.norm if logistic else stats.t(df_resid)
    critical = distribution.ppf(1-alpha/2)
    return pd.DataFrame(dict(term=names, estimate=params, std_error=se, statistic=statistic,
                             statistic_type='z' if logistic else 't',
                             p_value=2*distribution.sf(np.abs(statistic)),
                             ci_lower=params-critical*se, ci_upper=params+critical*se))


def _residual_diagnostics(residual, design):
    n = len(residual)
    rows = []
    if n >= 3 and np.ptp(residual) > 0:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', UserWarning)
            test = stats.shapiro(residual)
        rows.append(('Shapiro-Wilk', test.statistic, test.pvalue,
                     'H0: 残差正态；n>5000 时 p 值仅作近似参考。'))
    sse = residual @ residual
    rows.append(('Durbin-Watson', np.sum(np.diff(residual)**2)/sse if sse > 0 else np.nan,
                 np.nan, '按保留的原行序；无自相关时接近 2，不报告 p 值。'))
    # Include a genuine constant even for WLS, whose whitened intercept varies.
    aux = np.column_stack([np.ones(n), design])
    rank = np.linalg.matrix_rank(aux)
    squares = residual**2
    total = np.sum((squares - squares.mean())**2)
    if 1 < rank < n and total > 0:
        errors = squares - aux @ np.linalg.lstsq(aux, squares, rcond=None)[0]
        lm = max(0., n * (1 - errors @ errors / total))
        rows.append(('Breusch-Pagan (Koenker)', lm, stats.chi2.sf(lm, rank-1),
                     f'H0: 同方差；n*R²，辅助回归秩-1={rank-1}，渐近卡方上尾。'))
    return pd.DataFrame(rows, columns=TABLE_COLUMNS['diagnostics'])


def _influence(residual, matrix, covariance_unscaled, scale):
    n, p = matrix.shape
    h = np.einsum('ij,jk,ik->i', matrix, covariance_unscaled, matrix)
    h = np.clip(h, 0, 1)
    denom = scale * (1-h)
    standardized = np.divide(residual, np.sqrt(denom), out=np.full(n, np.nan), where=denom > 0)
    cook = np.divide(standardized**2*h, p*(1-h), out=np.full(n, np.nan), where=h < 1)
    return dict(standardized_residual=standardized, leverage=h, cooks_distance=cook,
                outlier=np.abs(standardized) > 2, high_leverage=h > 2*p/n,
                influential=cook > 4/n)


def _classification(y, probability):
    thresholds = np.r_[np.inf, np.unique(probability)[::-1]]
    order = np.argsort(-probability, kind='stable')
    sorted_p, sorted_y = probability[order], y[order]
    endpoints = np.r_[np.flatnonzero(np.diff(sorted_p)), len(y)-1]
    tp = np.r_[0, np.cumsum(sorted_y)[endpoints]]
    fp = np.r_[0, np.cumsum(1-sorted_y)[endpoints]]
    tpr, fpr = tp / y.sum(), fp / (len(y)-y.sum())
    auc = np.trapezoid(tpr, fpr)
    predicted = probability >= .5
    tn = np.sum((y == 0) & ~predicted)
    fp_count = np.sum((y == 0) & predicted)
    fn = np.sum((y == 1) & ~predicted)
    tp_count = np.sum((y == 1) & predicted)

    def ratio(a, b):
        return a / b if b else np.nan

    classification = pd.DataFrame([dict(threshold=.5, tn=tn, fp=fp_count, fn=fn, tp=tp_count,
                                        accuracy=(tn+tp_count)/len(y),
                                        precision=ratio(tp_count, tp_count+fp_count),
                                        recall=ratio(tp_count, tp_count+fn),
                                        specificity=ratio(tn, tn+fp_count),
                                        f1=ratio(2*tp_count, 2*tp_count+fp_count+fn), auc=auc)])
    return classification, pd.DataFrame(dict(threshold=thresholds, fpr=fpr, tpr=tpr)), auc


@dataclass
class RegressionResult:
    """tables 为原始精度 DataFrame；预测使用训练时的编码及参数，无重新拟合。"""
    tables: dict[str, pd.DataFrame]
    notes: list[str]
    equation: str
    model: str
    selected_terms: tuple
    _design: _Design | None
    _formula: _Formula | None
    _params: np.ndarray
    _covariance: np.ndarray
    _scale: float
    _df_resid: int
    _missing: str

    def predict(self, df, alpha=.05, weight=None):
        _alpha(alpha)
        if self.model != 'WLS' and weight is not None:
            raise ValueError('仅 WLS 新观测预测接受权重。')
        variables = (self._formula.variables if self._formula is not None
                     else self._design.required(self.selected_terms))
        categorical = self._design.categorical if self._design is not None else ()
        data, source, w = _prepare(df, variables, [c for c in variables if c not in categorical],
                                    weight, self._missing)
        if self._formula is not None:
            mean = self._formula(data, self._params)
            matrix = self._formula.jacobian(data, self._params)
        else:
            matrix, _ = self._design.matrix(data, self.selected_terms)
            mean = matrix @ self._params
        variance = np.maximum(0, np.einsum('ij,jk,ik->i', matrix, self._covariance, matrix))
        critical = stats.norm.ppf(1-alpha/2) if self.model == 'Logistic' else stats.t.ppf(1-alpha/2, self._df_resid)
        margin = critical * np.sqrt(variance)
        if self.model == 'Logistic':
            source['predicted'] = expit(mean)
            source['mean_ci_lower'], source['mean_ci_upper'] = expit(mean-margin), expit(mean+margin)
            source['pi_lower'], source['pi_upper'] = np.nan, np.nan
            source['probability'] = source['predicted']
            source['predicted_class'] = (source['probability'] >= .5).astype(int)
        else:
            source['predicted'] = mean
            source['mean_ci_lower'], source['mean_ci_upper'] = mean-margin, mean+margin
            pi = critical * np.sqrt(variance + self._scale/w)
            if self.model == 'WLS' and weight is None:
                pi[:] = np.nan
            source['pi_lower'], source['pi_upper'] = mean-pi, mean+pi
        return source


def fit_regression(df, y, x, model='OLS', categorical=(), degree=1, interactions=False,
                   selection='none', criterion='AIC', weight=None, alpha=.05,
                   missing='error', formula='', initial=None, cancel=None,
                   link=None, reference=None, order=None, n_components=None,
                   max_components=5, scale=True, cv=5):
    """拟合统一回归；cancel 可为无参数布尔回调或 threading.Event。

    Gaussian AIC/BIC 的 k=p+1（包括残差方差），Logistic k=p；与省略尺度参数
    的软件会有固定偏移。comparison.score 总是越小越好，adjR2 使用其负值。
    selection='none' 时只报告指定模型；其余方法也允许选择仅截距模型。
    interactions 可为布尔值或 [(列A, 列B), ...]。二元响应必须为 0/1。
    非线性不接受权重、分类、多项式、交互或变量筛选，以免隐式忽略选项。
    """
    extended = {'poisson': 'Poisson', 'nominal': 'Nominal', 'ordinal': 'Ordinal', 'pls': 'PLS'}
    if str(model).lower() in extended:
        model = extended[str(model).lower()]
        if criterion.lower() == 'adjr2':
            raise ValueError('此模型不适用调整 R² 筛选准则。')
        if model == 'PLS':
            if categorical or degree != 1 or interactions or selection != 'none' or weight is not None:
                raise ValueError('PLS 使用数值 X，不接受分类编码、多项式、交互、筛选或权重。')
            from pls_regression import fit_pls
            return fit_pls(df, y, x, n_components=n_components, max_components=max_components,
                           scale=scale, cv=cv, missing=missing, alpha=alpha, cancel=cancel)
        from generalized_regression import fit_generalized
        return fit_generalized(df, y, x, model, categorical=categorical, degree=degree,
            interactions=interactions, missing=missing, alpha=alpha, link=link,
            reference=reference, order=order, weight=weight, selection=selection, cancel=cancel)
    _cancel(cancel)
    _alpha(alpha)
    x = [x] if isinstance(x, str) else list(x)
    categorical = tuple(categorical)
    if not x or len(set(x)) != len(x) or y in x:
        raise ValueError('请选择不重复、且不包含 Y 的解释变量 X。')
    if not set(categorical).issubset(x):
        raise ValueError('分类变量必须属于所选 X。')
    if type(degree) is not int or degree not in (1, 2, 3):
        raise ValueError('degree 必须为 1、2 或 3。')
    if missing not in ('error', 'drop'):
        raise ValueError('missing 必须为 error 或 drop。')
    if selection not in ('none', 'forward', 'backward', 'both', 'best'):
        raise ValueError('不支持的变量筛选方法。')
    criterion = {'aic': 'AIC', 'bic': 'BIC', 'adjr2': 'adjR2'}.get(str(criterion).lower())
    if criterion is None:
        raise ValueError('criterion 必须为 AIC、BIC 或 adjR2。')
    aliases = {'ols': 'OLS', 'wls': 'WLS', 'logistic': 'Logistic', 'logit': 'Logistic',
               'nonlinear': 'nonlinear', 'exponential': 'exponential', 'power': 'power',
               'logistic_curve': 'logistic_curve'}
    if str(model).lower() not in aliases:
        raise ValueError('不支持的回归模型。')
    model = aliases[str(model).lower()]
    nonlinear = model not in ('OLS', 'WLS', 'Logistic')
    if model == 'WLS' and weight is None:
        raise ValueError('WLS 必须提供逆方差权重列或数组。')
    if model != 'WLS' and weight is not None:
        raise ValueError('仅 WLS 接受权重，请勿向其他模型传递权重。')
    if (model == 'Logistic' or nonlinear) and criterion == 'adjR2':
        raise ValueError('Logistic/非线性不适用调整 R²；请选择 AIC 或 BIC。')
    if nonlinear and (categorical or degree != 1 or interactions or selection != 'none'):
        raise ValueError('非线性模型不支持分类编码、多项式次数、交互项或变量筛选。')
    data, source, w = _prepare(df, [y]+x, [y]+[c for c in x if c not in categorical], weight, missing)
    response = _numeric(data[y])
    if model == 'Logistic':
        if set(response) != {0., 1.}:
            raise ValueError('Logistic 响应必须包含 0、1 两种取值。')
    elif np.ptp(response) == 0:
        raise ValueError('响应 Y 为常量，无法进行回归分析。')
    notes = [f'缺失策略：{missing}；保留 {len(data)}/{len(df)} 行；source_row 是原始位置+1。',
             'Gaussian AIC/BIC: k=p+1（含方差）；Logistic: k=p。系数 p 值为双侧零系数检验。',
             '异常阈值：|标准化残差|>2，杠杆>2p/n，Cook>4/n；仅为探索性提示。']
    tables = {key: pd.DataFrame(columns=cols) for key, cols in TABLE_COLUMNS.items()}
    design, parsed = None, None
    if nonlinear:
        for c in x:
            if np.ptp(_numeric(data[c])) == 0:
                raise ValueError(f'变量 {c!r} 为常量。')
        builtins = {'exponential': ('a*exp(b*x)+c', {'a': 1., 'b': .1, 'c': 0.}),
                    'power': ('a*x**b', {'a': 1., 'b': 1.}),
                    'logistic_curve': ('a/(1+exp(-b*(x-c)))', {'a': 1., 'b': 1., 'c': 0.})}
        if model in builtins:
            if len(x) != 1:
                raise ValueError('内置曲线模型仅支持一个 X；多变量请使用自定义公式。')
            formula, default = builtins[model]
            if initial is None:
                initial = default
            elif not isinstance(initial, dict):
                if len(initial) != len(default):
                    raise ValueError('内置曲线的初值数量不正确。')
                initial = dict(zip(default, initial))
        parsed = _Formula(formula, x, initial, builtin=model in builtins)
        if len(response) <= len(parsed.params):
            raise ValueError('非线性样本量不足，必须多于待估参数数目。')

        def residual_function(params):
            _cancel(cancel)
            return parsed(data, params) - response

        fitted = optimize.least_squares(residual_function, parsed.initial, jac='3-point', max_nfev=3000)
        if not fitted.success:
            raise ValueError(f'非线性回归未收敛：{fitted.message}')
        params = fitted.x
        matrix = parsed.jacobian(data, params)
        _rank(matrix, numerical_jacobian=True)
        fitted_values = parsed(data, params)
        residual = response - fitted_values
        n, p = len(response), len(params)
        sse = residual @ residual
        scale = sse/(n-p)
        if sse <= 0:
            raise ValueError('非线性残差方差为零，不能估计似然及参数区间。')
        covariance_unscaled = np.linalg.inv(matrix.T @ matrix)
        covariance = covariance_unscaled * scale
        log_likelihood = -n/2*(np.log(2*np.pi)+1+np.log(sse/n))
        metrics = dict(model=model, n_obs=n, n_parameters=p, df_resid=n-p, sse=sse,
                       rmse=np.sqrt(sse/n), residual_std=np.sqrt(scale), log_likelihood=log_likelihood,
                       aic=-2*log_likelihood+2*(p+1), bic=-2*log_likelihood+np.log(n)*(p+1))
        selected = tuple((c,) for c in x)
        names = parsed.params
        equation = f'{y} = {formula}; ' + ', '.join(f'{k}={v:.10g}' for k, v in zip(names, params))
        tables['comparison'] = pd.DataFrame([dict(terms=selected, n_parameters=p,
                                                  aic=metrics['aic'], bic=metrics['bic'],
                                                  score=metrics[criterion.lower()] if criterion != 'adjR2' else np.nan,
                                                  selected=True, status='ok')], columns=TABLE_COLUMNS['comparison'])
        notes.append('非线性：最小二乘局部解；系数 t/区间及影响量为雅可比一阶近似；不提供 OLS ANOVA/R²/VIF。')
    else:
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
        design = _Design(x, categorical, degree, pairs)
        design.learn(data)
        full, _ = design.matrix(data, design.groups)
        _rank(full*np.sqrt(w)[:, None])
        fit, selected, tables['comparison'] = _select(design, data, response, w, model,
                                                     selection, criterion, cancel)
        matrix, names = design.matrix(data, selected)
        params, covariance = np.asarray(fit.params), np.asarray(fit.cov_params())
        fitted_values = fit.predict()
        residual = response - fitted_values
        n, p = matrix.shape
        metrics = _metrics(fit, model, response, w)
        scale = float(fit.scale) if model != 'Logistic' else 1.
        covariance_unscaled = np.asarray(fit.normalized_cov_params) if model != 'Logistic' else covariance
        equation = ('logit(P(Y=1))' if model == 'Logistic' else str(y)) + ' = ' + ' + '.join(
            f'({value:.10g})*{name}' for name, value in zip(names, params))
        notes.append('设计矩阵含截距；分类基准=训练中首次出现水平；变量的幂/分类编码整组筛选；交互为一次项乘积并保留双方父组。')
        for c, levels in design.levels.items():
            notes.append(f'{c!r} 的分类基准：{levels[0]!r}；水平：{levels!r}。')
        failed = np.sum(tables['comparison']['status'] != 'ok')
        if failed:
            notes.append(f'{failed} 个候选拟合失败，原因见 comparison.status；未将失败候选视为成功。')
    _cancel(cancel)
    tables['coefficients'] = _coefficient_table(names, params, covariance, n-p, alpha, model == 'Logistic')
    observations = source.copy()
    observations['actual'], observations['fitted'], observations['residual'] = response, fitted_values, residual
    if model == 'Logistic':
        variance = fitted_values*(1-fitted_values)
        if np.any(variance <= np.finfo(float).eps):
            raise ValueError('Logistic 概率到达数值边界，可能完全/近完全分离，无法可靠计算诊断。')
        pearson = residual/np.sqrt(variance)
        influence = _influence(pearson, matrix*np.sqrt(variance)[:, None], covariance, 1.)
        observations['whitened_residual'] = np.nan
        observations['probability'] = fitted_values
        observations['predicted_class'] = (fitted_values >= .5).astype(int)
        tables['classification'], tables['roc'], metrics['auc'] = _classification(response, fitted_values)
        tables['diagnostics'] = pd.DataFrame([
            ('Pearson chi-square', pearson @ pearson, np.nan,
             '二元观测 Pearson χ²；未分组数据不提供拟合优度 p 值。'),
            ('Likelihood ratio', fit.llr, fit.llr_pvalue,
             '相对仅截距模型；H0: 所有斜率为零，渐近卡方上尾。')], columns=TABLE_COLUMNS['diagnostics'])
        notes.append('Logistic：标准化 Pearson 残差；杠杆来自 sqrt(p*(1-p))*X；Cook 为 GLM 一阶近似，非逐点删除重拟合。无 OLS R²/RMSE/ANOVA/观测PI。')
    else:
        whitened = residual*np.sqrt(w)
        white_matrix = matrix*np.sqrt(w)[:, None]
        observations['whitened_residual'] = whitened
        influence = _influence(whitened, white_matrix, covariance_unscaled, scale)
        tables['diagnostics'] = _residual_diagnostics(whitened, white_matrix)
        notes.append('残差诊断基于白化残差 sqrt(w)*(y-fitted)，OLS/非线性 w=1；杠杆为白化设计（非线性为雅可比）的投影对角元；Cook=r_std²*h/[p*(1-h)]。')
        if model == 'WLS':
            notes.append('WLS 权重为正的相对逆方差；RMSE、SSE、ANOVA、R²、VIF、影响量均在加权/白化尺度；新数据未指定权重时不提供观测 PI。')
        if not nonlinear:
            mean = np.average(response, weights=w)
            total = np.sum(w*(response-mean)**2)
            sse = metrics['sse']
            ssr = max(0., total-sse)
            f_stat = ssr/(p-1)/scale if p > 1 and scale > 0 else np.nan
            tables['anova'] = pd.DataFrame([
                ('Regression', ssr, p-1, ssr/(p-1) if p > 1 else np.nan, f_stat,
                 stats.f.sf(f_stat, p-1, n-p) if p > 1 else np.nan),
                ('Residual', sse, n-p, scale, np.nan, np.nan),
                ('Total', total, n-1, np.nan, np.nan, np.nan)], columns=TABLE_COLUMNS['anova'])
    for key, values in influence.items():
        observations[key] = values
    if not nonlinear:
        white = matrix*np.sqrt(w)[:, None]
        vifs = []
        for j in range(1, p):
            others = np.delete(white, j, axis=1)
            error = white[:, j] - others @ np.linalg.lstsq(others, white[:, j], rcond=None)[0]
            total = np.sum(w*(matrix[:, j]-np.average(matrix[:, j], weights=w))**2)
            vifs.append((names[j], total/(error @ error)))
        tables['vif'] = pd.DataFrame(vifs, columns=TABLE_COLUMNS['vif'])
    tables['summary'] = pd.DataFrame([metrics])
    tables['observations'] = observations[TABLE_COLUMNS['observations'] +
                                            (['probability', 'predicted_class'] if model == 'Logistic' else [])]
    return RegressionResult(tables, notes, equation, model, tuple(selected), design, parsed,
                            params.copy(), covariance.copy(), scale, n-p, missing)
