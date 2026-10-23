"""PLS1/PLS2 的 NIPALS 计算，不导入 GUI，也不修改输入数据。

fit_pls 为生产入口。始终中心化；scale=True 时 X/Y 均除以样本标准差。
CV 为按输入顺序连续分组的确定性 K 折（cv=n 为 LOO），每折独立预处理。
自动选择最小平均标准化 PRESS：每个留出残差除以相应训练折 Y 的样本
标准差，再对全部观测和响应取平方均值；并列时选择较少的成分。
系数为原始单位，VIP 按建模尺度上各响应合计的解释平方和加权。
PLS 不提供 OLS 的自由度、参数检验或预测区间；alpha 仅作接口校验。
"""
from dataclasses import dataclass
from numbers import Integral

import numpy as np
import pandas as pd


def _cancelled(cancel):
    if cancel is not None and (cancel.is_set() if hasattr(cancel, 'is_set') else cancel()):
        raise InterruptedError('PLS 回归已取消。')


def _alpha(alpha):
    try:
        valid = np.isscalar(alpha) and np.isfinite(alpha) and 0 < alpha < 1
    except TypeError:
        valid = False
    if not valid:
        raise ValueError('alpha 必须在 0 和 1 之间。')


def _integer(value, name, minimum):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral) or value < minimum:
        raise ValueError(f'{name} 必须为不小于 {minimum} 的整数。')


def _numeric(series):
    try:
        values = pd.to_numeric(series, errors='raise')
        if np.iscomplexobj(values):
            raise ValueError('不支持复数。')
        values = values.to_numpy(dtype=float, na_value=np.nan)
    except (TypeError, ValueError) as exc:
        raise ValueError(f'列 {series.name!r} 必须为实数数值。') from exc
    if np.isinf(values).any():
        raise ValueError(f'列 {series.name!r} 含无穷值。')
    return values


def _data(df, columns, missing):
    if not isinstance(df, pd.DataFrame) or not df.columns.is_unique:
        raise ValueError('输入必须为列名唯一的 DataFrame。')
    absent = [c for c in columns if c not in df.columns]
    if absent:
        raise ValueError(f'缺少列：{absent}')
    matrix = np.column_stack([_numeric(df[column]) for column in columns])
    incomplete = np.isnan(matrix).any(axis=1)
    if incomplete.any() and missing == 'error':
        raise ValueError('数据含缺失值；请明确选择 missing="drop" 删除不完整行。')
    keep = np.flatnonzero(~incomplete)
    if not len(keep):
        raise ValueError('没有可用于分析的完整样本。')
    source = pd.DataFrame({'source_row': keep + 1,
                           'source_index': [df.index[i] for i in keep]})
    return matrix[keep], source


@dataclass
class _Nipals:
    x_mean: np.ndarray
    y_mean: np.ndarray
    x_scale: np.ndarray
    y_scale: np.ndarray
    weights: np.ndarray
    x_loadings: np.ndarray
    y_loadings: np.ndarray
    x_scores: np.ndarray
    y_scores: np.ndarray
    x_variance: np.ndarray
    y_variance: np.ndarray

    @property
    def n_components(self):
        return self.weights.shape[1]

    def coefficients(self, count):
        w, p, q = (a[:, :count] for a in
                   (self.weights, self.x_loadings, self.y_loadings))
        beta = (w @ np.linalg.solve(p.T @ w, q.T)) * self.y_scale / self.x_scale[:, None]
        return self.y_mean - self.x_mean @ beta, beta

    def predict(self, x, count):
        intercept, beta = self.coefficients(count)
        return x @ beta + intercept


def _nipals(x, y, count, scale, cancel):
    _cancelled(cancel)
    if len(x) < 2:
        raise ValueError('PLS 训练折至少需要 2 个观测。')
    xm, ym = x.mean(axis=0), y.mean(axis=0)
    xs = x.std(axis=0, ddof=1) if scale else np.ones(x.shape[1])
    ys = y.std(axis=0, ddof=1) if scale else np.ones(y.shape[1])
    # 折内常量列中心化后为零，不借用全数据的尺度或均值。
    xs[xs == 0], ys[ys == 0] = 1., 1.
    e, f = (x - xm) / xs, (y - ym) / ys
    if not np.isfinite(e).all() or not np.isfinite(f).all():
        raise ValueError('数据范围导致预处理溢出。')
    rank = np.linalg.matrix_rank(e)
    threshold = np.finfo(float).eps * max(e.shape) * np.linalg.norm(e) * np.linalg.norm(f)
    weights, px, qy, tx, uy, vx, vy = [], [], [], [], [], [], []
    for _ in range(min(count, rank)):
        _cancelled(cancel)
        covariance = e.T @ f
        if np.max(np.linalg.norm(covariance, axis=0)) <= threshold:
            break
        best, best_norm = None, -1.
        # 从每个非零响应方向启动，避免正交多 Y 使幂迭代停在次大奇异方向。
        for initial in covariance.T:
            norm = np.linalg.norm(initial)
            if norm <= threshold:
                continue
            w = initial / norm
            for iteration in range(10000):
                _cancelled(cancel)
                c = covariance.T @ w
                c /= np.linalg.norm(c)
                updated = covariance @ c
                norm = np.linalg.norm(updated)
                if norm == 0 or not np.isfinite(norm):
                    raise ValueError('NIPALS 无法获得有限的成分权重。')
                updated /= norm
                converged = np.linalg.norm(updated - w) < 1e-12
                w = updated
                if converged:
                    break
            else:
                raise ValueError('NIPALS 在 10000 次迭代内未收敛。')
            strength = np.linalg.norm(covariance.T @ w)
            if strength > best_norm:
                best, best_norm = w, strength
        w = best
        t = e @ w
        tt = t @ t
        q = f.T @ t / tt
        u = f @ q / (q @ q)
        sign = 1. if w[np.argmax(np.abs(w))] >= 0 else -1.
        w, t, q, u = w*sign, t*sign, q*sign, u*sign
        p = e.T @ t / tt
        weights.append(w)
        px.append(p)
        qy.append(q)
        tx.append(t)
        uy.append(u)
        vx.append(tt * (p @ p))
        vy.append(tt * q*q)
        e -= np.outer(t, p)
        f -= np.outer(t, q)
    if not weights:
        raise ValueError('X 与 Y 无可提取的非零协方差成分。')
    return _Nipals(xm, ym, xs, ys, np.column_stack(weights), np.column_stack(px),
                   np.column_stack(qy), np.column_stack(tx), np.column_stack(uy),
                   np.asarray(vx), np.asarray(vy))


@dataclass
class PLSResult:
    tables: dict
    notes: list
    equation: str
    predictors: list
    responses: list
    missing: str
    n_components: int
    _fit: _Nipals
    model = 'PLS'

    def predict(self, df, alpha=.05, weight=None):
        """长表点预测；可用 Y 附 actual/residual/rmsep，缺失 Y 不丢弃预测。"""
        _alpha(alpha)
        if weight is not None:
            raise ValueError('PLS 不支持观测权重。')
        x, source = _data(df, self.predictors, self.missing)
        predicted = self._fit.predict(x, self.n_components)
        if not np.isfinite(predicted).all():
            raise ValueError('预测值非有限，请检查数据范围。')
        tables = []
        for j, response in enumerate(self.responses):
            table = source.assign(predicted=predicted[:, j], response=response)
            if response in df.columns:
                actual = _numeric(df[response])[source.source_row.to_numpy()-1]
                residual = actual-predicted[:, j]
                valid = np.isfinite(actual)
                rmsep = np.sqrt(np.mean(residual[valid]**2)) if valid.any() else np.nan
                table = table.assign(actual=actual, residual=residual, rmsep=rmsep)
            tables.append(table)
        return pd.concat(tables, ignore_index=True)


def fit_pls(df, y, x, *, n_components=None, max_components=5, scale=True,
            cv=5, missing='error', alpha=.05, cancel=None):
    """拟合数值 PLS；返回 PLSResult，tables 中的表可直接用于报告与导出。"""
    _cancelled(cancel)
    _alpha(alpha)
    if missing not in ('error', 'drop'):
        raise ValueError('missing 必须为 error 或 drop。')
    if not isinstance(scale, (bool, np.bool_)):
        raise ValueError('scale 必须为布尔值。')
    _integer(max_components, 'max_components', 1)
    _integer(cv, 'cv', 0)
    if n_components is not None:
        _integer(n_components, 'n_components', 1)
    if cv == 0 and n_components is None:
        raise ValueError('cv=0 时必须明确指定 n_components。')
    if cv == 1:
        raise ValueError('cv 必须为 0 或 2..n；cv=n 为留一法。')
    responses = [y] if isinstance(y, str) else list(y)
    predictors = [x] if isinstance(x, str) else list(x)
    if not responses or not predictors:
        raise ValueError('至少需要一个响应和一个预测变量。')
    columns = predictors + responses
    if len(set(columns)) != len(columns):
        raise ValueError('预测变量与响应不得重复或重叠。')
    values, source = _data(df, columns, missing)
    n, p, m = len(values), len(predictors), len(responses)
    if n < 2 or cv > n:
        raise ValueError('至少需要 2 个完整观测，且 cv 不得超过完整观测数。')
    constants = [c for j, c in enumerate(columns) if np.ptp(values[:, j]) == 0]
    if constants:
        raise ValueError(f'变量为常量，无法提取成分：{constants}')
    xx, yy = values[:, :p], values[:, p:]
    rank_x = xx - xx.mean(axis=0)
    if scale:
        rank_x = rank_x / xx.std(axis=0, ddof=1)
    rank = np.linalg.matrix_rank(rank_x)
    if n_components is not None and n_components > rank:
        raise ValueError(f'n_components 超过中心化 X 的数值秩 {rank}。')
    limit = min(rank, max_components) if n_components is None else n_components
    fitted = _nipals(xx, yy, limit, scale, cancel)
    available = fitted.n_components
    folds = []
    if cv:
        for fold, test in enumerate(np.array_split(np.arange(n), cv), 1):
            _cancelled(cancel)
            train = np.setdiff1d(np.arange(n), test, assume_unique=True)
            y_sd = yy[train].std(axis=0, ddof=1)
            if not np.isfinite(y_sd).all() or np.any(y_sd == 0):
                raise ValueError(f'CV 第 {fold} 折训练响应为常量或样本不足，标准化 PRESS 无定义。')
            model = _nipals(xx[train], yy[train], limit, scale, cancel)
            available = min(available, model.n_components)
            folds.append((fold, test, y_sd, model))
    if n_components is not None and n_components > available:
        raise ValueError(f'n_components 超过全数据或训练折可提取的成分数 {available}。')
    cv_rows, cv_predictions = [], []
    scores = []
    for count in range(1, available + 1) if cv else []:
        press, standardized = np.zeros(m), np.zeros(m)
        for fold, test, y_sd, model in folds:
            _cancelled(cancel)
            predicted = model.predict(xx[test], count)
            residual = yy[test] - predicted
            press += np.sum(residual**2, axis=0)
            standardized += np.sum((residual / y_sd)**2, axis=0)
            for j, response in enumerate(responses):
                cv_predictions.append(source.iloc[test].assign(
                    n_components=count, fold=fold, response=response,
                    actual=yy[test, j], predicted=predicted[:, j], residual=residual[:, j],
                    standardized_residual=residual[:, j]/y_sd[j]))
        score = standardized.sum() / (n*m)
        scores.append(score)
        cv_rows.extend(dict(n_components=count, response=response, press=press[j],
                            rmsecv=np.sqrt(press[j]/n), standardized_press=standardized[j],
                            mean_standardized_press=score)
                       for j, response in enumerate(responses))
    count = int(np.argmin(scores)) + 1 if n_components is None else n_components
    intercept, beta = fitted.coefficients(count)
    predicted = fitted.predict(xx, count)
    residual = yy - predicted
    coefficients, observations, summary = [], [], []
    for j, response in enumerate(responses):
        coefficients.extend(dict(term=term, estimate=value, response=response)
                            for term, value in zip(['Intercept'] + predictors,
                                                   np.r_[intercept[j], beta[:, j]]))
        observations.append(source.assign(actual=yy[:, j], fitted=predicted[:, j],
                                          residual=residual[:, j], response=response))
        sse = residual[:, j] @ residual[:, j]
        total = np.sum((yy[:, j] - yy[:, j].mean())**2)
        summary.append(dict(model='PLS', response=response, n_obs=n, n_predictors=p,
                            n_components=count, x_rank=rank, scaled=bool(scale),
                            cv_folds=cv, sse=sse, rmse=np.sqrt(sse/n), r_squared=1-sse/total))
    labels = [f'component_{i+1}' for i in range(count)]
    tables = {'summary': pd.DataFrame(summary), 'coefficients': pd.DataFrame(coefficients),
              'observations': pd.concat(observations, ignore_index=True)}
    for name, matrix, identity in (
            ('x_scores', fitted.x_scores, source), ('y_scores', fitted.y_scores, source),
            ('x_loadings', fitted.x_loadings, pd.DataFrame({'term': predictors})),
            ('y_loadings', fitted.y_loadings, pd.DataFrame({'response': responses}))):
        tables[name] = pd.concat([identity.reset_index(drop=True),
                                 pd.DataFrame(matrix[:, :count], columns=labels)], axis=1)
    x_fraction = fitted.x_variance[:count] / np.sum(((xx-fitted.x_mean)/fitted.x_scale)**2)
    y_fraction = fitted.y_variance[:count] / np.sum(((yy-fitted.y_mean)/fitted.y_scale)**2, axis=0)
    tables['variance'] = pd.DataFrame([
        dict(component=i+1, response=response, x_variance_ratio=x_fraction[i],
             x_cumulative_ratio=x_fraction[:i+1].sum(), y_variance_ratio=y_fraction[i, j],
             y_cumulative_ratio=y_fraction[:i+1, j].sum())
        for i in range(count) for j, response in enumerate(responses)])
    explained_y = fitted.y_variance[:count].sum(axis=1)
    vip = np.sqrt(p * (fitted.weights[:, :count]**2 @ explained_y) / explained_y.sum())
    tables['vip'] = pd.DataFrame({'term': predictors, 'vip': vip})
    tables['cv'] = pd.DataFrame(cv_rows, columns=[
        'n_components', 'response', 'press', 'rmsecv', 'standardized_press', 'mean_standardized_press'])
    tables['cv']['selected'] = tables['cv']['n_components'] == count
    tables['cv_predictions'] = (pd.concat(cv_predictions, ignore_index=True) if cv_predictions else
                               pd.DataFrame(columns=['source_row', 'source_index', 'n_components',
                                                     'fold', 'response', 'actual', 'predicted',
                                                     'residual', 'standardized_residual']))
    equations = [f'{response} = {intercept[j]:.10g}' + ''.join(
        f' {beta[i, j]:+.10g}*{term}' for i, term in enumerate(predictors))
        for j, response in enumerate(responses)]
    notes = ['始终中心化；标准化使用训练样本标准差（ddof=1）。',
             'CV 按输入顺序连续分折，每折独立预处理；按各训练折 Y 标准差计算平均标准化 PRESS。',
             'RMSE 为训练 SSE/N 的平方根；不提供 OLS 参数检验、自由度或预测区间。',
             'scores/loadings 为建模尺度；系数和预测为原始单位；VIP 合计所有响应解释平方和。']
    if n_components is None:
        notes.append(f'自动成分候选限制为所有训练折均可提取的 1..{available}，最小 CV 分数选 {count}。')
    if len(values) != len(df):
        notes.append(f'删除 {len(df)-len(values)} 个不完整观测，未填补缺失值。')
    _cancelled(cancel)
    return PLSResult(tables, notes, '\n'.join(equations), predictors, responses,
                     missing, count, fitted)
