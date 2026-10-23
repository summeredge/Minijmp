"""纯计算时间序列 API；不导入 Tk/绘图库，不修改工作表，不自动排序或填补。

analyze_time_series(df, y, time=None, other=None, interval='1s', missing='error',
    duplicates='error', irregular='error', lags=20, period=None,
    decomposition='additive', order=(1,0,0), seasonal_order=(0,0,0,0),
    forecast_steps=10, alpha=.05, cancel=None, analysis='all') -> TimeSeriesResult
analysis: correlation/decomposition/stationarity/ARIMA/SARIMA/all。

tables schema（英文列名为 GUI/plots 合约，按选择生成；无选择无对应表）：
  data: source_row, source_index, source_rows, source_indices, sequence, time,
        elapsed, value, other（other 仅选择配对列时存在）。
  status: analysis, status('ok'/'unavailable'), message。
  acf/pacf/residual_acf: lag, correlation, ci_lower, ci_upper, n_pairs。
  ccf: lag, correlation, n_pairs（无伪精确 CI；重叠段常量时 NaN）。
  trend: data 全列 + fitted, residual。
  trend_coefficients: term, coefficient, std_error, statistic, p_value,
                      ci_lower, ci_upper（term=intercept/slope）。
  decomposition: data 全列 + trend, seasonal, residual（端点 NaN 不外推）。
  stationarity: test, statistic, p_value, lags, nobs, null, alternative,
      regression, reject, critical_1pct, critical_5pct, critical_10pct,
      p_value_bound（exact/less_than/greater_than；KPSS 插值范围 .01~.1）。
  model_summary: model, order, seasonal_order, nobs, effective_nobs,
      log_likelihood, aic, bic, rmse, converged, burn, alpha。
  model_coefficients: 同 trend_coefficients，统计量为渐近 z。
  diagnostics: lag, statistic, p_value, df, null（Ljung-Box）。
  residuals: data 全列 + fitted, residual, diagnostic_used。
  forecast: step, sequence, time, elapsed, predicted, ci_lower, ci_upper,
      source_row, source_index, source_rows, source_indices。
source_row 为输入表从 1 起算的位置；source_index 为原始索引标签；重复时间
聚合保留全部 source_rows/source_indices 成员（first/last 代表被选行，mean
代表首行）。预测来源为空，不虚构原行号。lag/系数/检验表是总体统计量，
来源集合为 data，不是逐行观测。series 是建模 Y，model 是可选 ARIMAResults。

真实日期保留 pandas datetime dtype（含统一时区）；非日期模式 time=NaT，
elapsed 为从首个输入位置起算的 Timedelta，不虚构日期。interval 仅用于无
日期列时，必须是正的固定 pd.to_timedelta 字符串。真实日期从相邻差值确定
固定间隔，拒绝乱序。删除缺失行造成的内部断点也检查不规则。sequence
策略显式按观测序号重新解释；保留 data 中实际时间以追溯，但 series 用
RangeIndex，未来 time/elapsed 均为空，仅预测 sequence，绝不猜实际时间。

定义/参考（statsmodels 官方实现；独立公式证据在 test_time_series_analysis）：
ACF: 去全局均值，gamma(k)=sum(z[t]z[t-k])/n，biased；Bartlett 点态 CI。
PACF: Yule-Walker MLE（相同 /n 自协方差），正态点态 CI；按 n//2-1 限制。
CCF: 每个滞后独立重叠段 Pearson corr(Y_t, X_{t-k})，k>0 是 X 领先 Y，
至少 3 对；不混用全样本中心或全样本归一化，不作因果解释。
趋势: Y=intercept+slope*(sequence-1)，OLS t 检验/双侧 CI；斜率单位为每步。
季节分解: 双侧经典移动平均，至少两周期；乘法必须全正，端点不外推。
ADF: regression='c', autolag=None，lags 上限 min(请求, n//2-2)，H0 单位根，
左尾；MacKinnon p/临界值。KPSS: regression='c'，Bartlett HAC，带宽
min(请求,n-1)，H0 水平平稳，右尾；p 为临界表插值且须报告超界方向。
ARIMA/SARIMA: statsmodels ARIMA 状态空间高斯极大似然，无自动搜参；不差分
默认常数，差分默认无趋势。固定参数条件下的未来观测预测区间（不是均值
置信区间，未含参数估计不确定性）。Ljung-Box 使用去 burn 的创新残差，
df=lag-(p+q+P+Q)；df<=0 的 p 值不可用，不解释为通过。rmse 同样去 burn。
all 逐功能记录不可用原因；有季节配置时拟合 SARIMA，否则拟合 ARIMA，
不重复拟合两模型。单选失败报 ValueError；period=None 时只做趋势。
cancel 支持 Event 或布尔回调，在各阶段、CCF 循环及拟合前后检查；一次
底层拟合/分解不可即时中断。警告保存在 notes，不把未收敛报告为可靠结果。

官方定义：
https://www.statsmodels.org/stable/generated/statsmodels.tsa.stattools.acf.html
https://www.statsmodels.org/stable/generated/statsmodels.tsa.stattools.pacf.html
https://www.statsmodels.org/stable/generated/statsmodels.tsa.stattools.adfuller.html
https://www.statsmodels.org/stable/generated/statsmodels.tsa.stattools.kpss.html
https://www.statsmodels.org/stable/generated/statsmodels.tsa.seasonal.seasonal_decompose.html
https://www.statsmodels.org/stable/generated/statsmodels.tsa.arima.model.ARIMA.html
https://www.statsmodels.org/stable/generated/statsmodels.stats.diagnostic.acorr_ljungbox.html
"""
from dataclasses import dataclass
import warnings

import numpy as np
import pandas as pd
from pandas.api.types import (is_numeric_dtype, is_bool_dtype, is_complex_dtype,
                              is_datetime64_any_dtype)
from statsmodels.regression.linear_model import OLS
from statsmodels.stats.diagnostic import acorr_ljungbox
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.seasonal import seasonal_decompose
from statsmodels.tsa.stattools import acf, pacf, adfuller, kpss


@dataclass
class TimeSeriesResult:
    tables: dict[str, pd.DataFrame]
    notes: list[str]
    series: pd.Series
    model: object = None


def _check_cancel(cancel):
    if cancel is not None and (cancel.is_set() if hasattr(cancel, 'is_set') else cancel()):
        raise InterruptedError('时间序列分析已取消。')


def _integer(value, name, minimum=0):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer)) or value < minimum:
        raise ValueError(f'{name} 必须为不小于 {minimum} 的整数。')
    return int(value)


def _prepare(df, y, time, other, interval, missing, duplicates, irregular, notes):
    if not isinstance(df, pd.DataFrame) or df.empty:
        raise ValueError('没有可分析的数据。')
    if not df.columns.is_unique:
        raise ValueError('列名重复，请先使用唯一列名。')
    for option, value, choices in (
            ('missing', missing, ('error', 'drop')),
            ('duplicates', duplicates, ('error', 'first', 'last', 'mean')),
            ('irregular', irregular, ('error', 'sequence'))):
        if value not in choices:
            raise ValueError(f'{option} 必须为 {choices}。')
    values = {}
    for column, name in ((y, 'value'), (other, 'other')):
        if name == 'other' and column is None:
            continue
        if column not in df:
            raise ValueError(f'找不到数值列：{column}。')
        s = df[column]
        if not is_numeric_dtype(s.dtype) or is_bool_dtype(s.dtype) or is_complex_dtype(s.dtype):
            raise ValueError(f'变量“{column}”必须为实数数值列。')
        values[name] = s.to_numpy(dtype=float, na_value=np.nan)
        if np.isinf(values[name]).any():
            raise ValueError(f'变量“{column}”包含非有限无穷值。')
    data = pd.DataFrame(values)
    data['source_row'] = np.arange(1, len(df) + 1)
    data['source_index'] = pd.Series(list(df.index), dtype=object)
    if time is None:
        if not isinstance(interval, str):
            raise ValueError('固定采样 interval 必须为 timedelta 字符串，如 1min。')
        try:
            step = pd.to_timedelta(interval)
        except (ValueError, TypeError, OverflowError) as exc:
            raise ValueError('interval 必须为固定时间间隔；不支持月/年等日历频率。') from exc
        if pd.isna(step) or step <= pd.Timedelta(0):
            raise ValueError('interval 必须为正的固定时间间隔。')
        data['time'] = pd.NaT
        try:
            data['elapsed'] = pd.timedelta_range(start='0s', periods=len(df), freq=step)
        except (ValueError, OverflowError) as exc:
            raise ValueError('固定时间间隔超出 timedelta 范围。') from exc
    else:
        if time not in df or is_numeric_dtype(df[time].dtype):
            raise ValueError('时间列必须为日期时间；数值时间请使用固定采样间隔。')
        try:
            times = pd.to_datetime(df[time], format='mixed', errors='coerce')
        except (ValueError, TypeError, OverflowError) as exc:
            raise ValueError('时间列无法解析为统一日期时间。') from exc
        if not is_datetime64_any_dtype(times.dtype):
            raise ValueError('时间列时区不一致，请先统一时区。')
        if (times.isna() & df[time].notna()).any():
            raise ValueError('时间列包含无效日期时间，请修正后分析。')
        data['time'] = times.reset_index(drop=True)
        data['elapsed'] = pd.NaT
        step = None
        raw_differences = times.dropna().diff().dropna()
        positive_differences = raw_differences[raw_differences > pd.Timedelta(0)]
        if len(positive_differences) and (positive_differences == positive_differences.iloc[0]).all():
            step = positive_differences.iloc[0]
    required = list(values) + (['time'] if time is not None else [])
    bad = data[required].isna().any(axis=1)
    if bad.any():
        if missing == 'error':
            raise ValueError(f'配对分析列包含 {bad.sum()} 行缺失值；可显式选择 missing=drop。')
        notes.append(f'完整 case 删除 {bad.sum()} 行缺失数据，Y 与 other 使用同一行集合。')
        data = data.loc[~bad].reset_index(drop=True)
    if len(data) < 3:
        raise ValueError('有效配对样本量不足，至少需要 3 行。')
    data['source_rows'] = [[int(row)] for row in data.source_row]
    data['source_indices'] = [[label] for label in data.source_index]
    if time is not None:
        if not data.time.is_monotonic_increasing:
            raise ValueError('时间列乱序；统计分析不自动排序，请先明确排序工作表。')
        if data.time.duplicated().any():
            if duplicates == 'error':
                raise ValueError('时间列存在重复时间戳，请显式选择 first/last/mean。')
            rows = []
            for _, group in data.groupby('time', sort=False):
                representative = group.iloc[-1 if duplicates == 'last' else 0].copy()
                if duplicates == 'mean':
                    for col in values:
                        representative[col] = group[col].mean()
                representative['source_rows'] = group.source_row.tolist()
                representative['source_indices'] = group.source_index.tolist()
                rows.append(representative)
            notes.append(f'重复时间戳按 {duplicates} 处理；聚合成员保存在 source_rows/source_indices。')
            data = pd.DataFrame(rows).reset_index(drop=True)
        data['elapsed'] = data.time - data.time.iloc[0]
    if len(data) < 3:
        raise ValueError('重复时间处理后有效样本量不足，至少需要 3 行。')
    differences = data.elapsed.diff().iloc[1:]
    regular = bool((differences == (step if step is not None else differences.iloc[0])).all())
    if not regular and irregular == 'error':
        raise ValueError('采样不规则（可能由删除缺失行产生）；可显式选择 irregular=sequence。')
    sequence_mode = irregular == 'sequence'
    if sequence_mode:
        step = None
        notes.append('irregular=sequence：按观测顺序等间隔重新解释，丢失实际时间尺度；未来仅输出序号。')
    elif time is not None:
        step = differences.iloc[0]
    data['sequence'] = np.arange(1, len(data) + 1)
    data = data[['source_row', 'source_index', 'source_rows', 'source_indices',
                 'sequence', 'time', 'elapsed', *values]]
    index = pd.DatetimeIndex(data.time) if time is not None and not sequence_mode else pd.RangeIndex(1, len(data) + 1, name='sequence')
    series = pd.Series(data.value.to_numpy(copy=True), index=index, name=y)
    return data, series, step


def _nonconstant(values):
    if np.ptp(values) == 0:
        raise ValueError('常量序列不支持此统计方法。')
    with np.errstate(over='ignore', invalid='ignore', under='ignore'):
        variance = np.mean((values - np.mean(values)) ** 2)
    if not np.isfinite(variance) or variance <= 0:
        raise ValueError('序列数值尺度导致方差溢出或下溢，请先明确调整量纲。')


def _correlations(values, lags, alpha, partial=False):
    _nonconstant(values)
    n = len(values)
    count = min(lags, n // 2 - 1 if partial else n - 1)
    if count == 0:
        return pd.DataFrame({'lag': [0], 'correlation': [1.], 'ci_lower': [1.],
                             'ci_upper': [1.], 'n_pairs': [n]})
    if partial:
        correlations, ci = pacf(values, nlags=count, method='ywm', alpha=alpha, result_object=False)
    else:
        correlations, ci = acf(values, nlags=count, fft=True, adjusted=False,
                               alpha=alpha, bartlett_confint=True, result_object=False)
    return pd.DataFrame({'lag': np.arange(len(correlations)), 'correlation': correlations,
                         'ci_lower': ci[:, 0], 'ci_upper': ci[:, 1],
                         'n_pairs': n - np.arange(len(correlations))})


def _correlation_tables(data, lags, alpha, cancel, notes):
    values = data.value.to_numpy()
    tables = {'acf': _correlations(values, lags, alpha),
              'pacf': _correlations(values, lags, alpha, partial=True)}
    notes.append(f'ACF biased/Bartlett CI；PACF Yule-Walker MLE；实际最大滞后 {len(tables["acf"])-1}/{len(tables["pacf"])-1}（请求 {lags}）。')
    if 'other' in data:
        x = data.other.to_numpy()
        _nonconstant(x)
        count = min(lags, len(values) - 3)
        rows = []
        for k in range(-count, count + 1):
            _check_cancel(cancel)
            a, b = (values[k:], x[:len(x)-k]) if k >= 0 else (values[:len(values)+k], x[-k:])
            correlation = np.nan if np.ptp(a) == 0 or np.ptp(b) == 0 else float(np.corrcoef(a, b)[0, 1])
            rows.append((k, correlation, len(a)))
        tables['ccf'] = pd.DataFrame(rows, columns=['lag', 'correlation', 'n_pairs'])
        notes.append('CCF=corr(Y_t,X_{t-k})；k>0 表示 X 领先 Y；每滞后重叠段 Pearson，至少3对，常量重叠段为 NaN。')
    return tables


def _coefficient_table(fit, terms, alpha):
    ci = np.asarray(fit.conf_int(alpha=alpha))
    return pd.DataFrame({'term': terms, 'coefficient': np.asarray(fit.params),
                         'std_error': np.asarray(fit.bse), 'statistic': np.asarray(fit.tvalues),
                         'p_value': np.asarray(fit.pvalues), 'ci_lower': ci[:, 0],
                         'ci_upper': ci[:, 1]})


def _trend(data, alpha):
    design = np.column_stack([np.ones(len(data)), data.sequence.to_numpy() - 1])
    fit = OLS(data.value.to_numpy(), design).fit()
    table = data.assign(fitted=np.asarray(fit.fittedvalues), residual=np.asarray(fit.resid))
    return {'trend': table, 'trend_coefficients': _coefficient_table(fit, ['intercept', 'slope'], alpha)}


def _stationarity(values, lags, alpha, notes):
    _nonconstant(values)
    if len(values) < 5:
        raise ValueError('ADF/KPSS 至少需要 5 个有效样本。')
    lag_adf = min(lags, len(values) // 2 - 2)
    adf = adfuller(values, maxlag=lag_adf, regression='c', autolag=None, result_object=False)
    kp = kpss(values, regression='c', nlags=min(lags, len(values) - 1), result_object=False)
    if not np.isfinite(adf[0]) or not np.isfinite(kp[0]):
        raise ValueError('平稳性统计量不可计算；序列可能为确定性趋势或长期方差退化。')
    rows = []
    for test, statistic, pvalue, used_lags, nobs, critical, null, alternative in (
            ('ADF', adf[0], adf[1], adf[2], adf[3], adf[4], '单位根', '无单位根'),
            ('KPSS', kp[0], kp[1], kp[2], len(values), kp[3], '水平平稳', '非水平平稳')):
        bound = 'exact'
        if test == 'KPSS':
            bound = 'less_than' if statistic > critical['1%'] else 'greater_than' if statistic < critical['10%'] else 'exact'
        # 超出插值范围时只给出能够由界限推出的结论。
        reject = (True if pvalue <= alpha else pd.NA) if bound == 'less_than' else (False if pvalue >= alpha else pd.NA) if bound == 'greater_than' else bool(pvalue < alpha)
        rows.append({'test': test, 'statistic': statistic, 'p_value': pvalue,
                     'lags': used_lags, 'nobs': nobs, 'null': null, 'alternative': alternative,
                     'regression': 'c', 'reject': reject, 'p_value_bound': bound,
                     'critical_1pct': critical['1%'], 'critical_5pct': critical['5%'],
                     'critical_10pct': critical['10%']})
    notes.append('ADF：H0 单位根，左尾，固定滞后；KPSS：H0 水平平稳，右尾，Bartlett HAC；p 值超界方向见 p_value_bound。')
    return {'stationarity': pd.DataFrame(rows)}


def _orders(order, seasonal_order, seasonal):
    if not isinstance(order, (tuple, list)) or len(order) != 3:
        raise ValueError('order 必须是 (p,d,q)。')
    order = tuple(_integer(v, 'order') for v in order)
    if not seasonal:
        return order, (0, 0, 0, 0)
    if not isinstance(seasonal_order, (tuple, list)) or len(seasonal_order) != 4:
        raise ValueError('seasonal_order 必须是 (P,D,Q,s)。')
    seasonal_order = tuple(_integer(v, 'seasonal_order') for v in seasonal_order)
    if seasonal_order[3] < 2 or not any(seasonal_order[:3]):
        raise ValueError('SARIMA 需要 s>=2 且至少一个非零季节阶数。')
    return order, seasonal_order


def _fit_model(data, series, step, lags, order, seasonal_order, seasonal,
               forecast_steps, alpha, cancel, notes):
    _nonconstant(series.to_numpy())
    order, seasonal_order = _orders(order, seasonal_order, seasonal)
    p, d, q = order
    P, D, Q, s = seasonal_order
    if len(data) - d - D * s <= p + q + P + Q + 3 or (seasonal and len(data) < 2 * s):
        raise ValueError('样本量不足以估计指定 ARIMA/SARIMA 阶数及差分。')
    _check_cancel(cancel)
    fit = ARIMA(series.to_numpy(), order=order, seasonal_order=seasonal_order).fit()
    _check_cancel(cancel)
    converged = bool(fit.mle_retvals.get('converged', False))
    if not converged:
        raise ValueError('ARIMA/SARIMA 模型未收敛，请降低阶数或检查数据；未输出不可靠预测。')
    if not np.isfinite(np.r_[fit.params, fit.llf, fit.aic, fit.bic]).all():
        raise ValueError('模型估计得到非有限参数/似然值，请检查数据或阶数。')
    burn = max(int(fit.loglikelihood_burn), int(fit.filter_results.nobs_diffuse))
    residual = np.asarray(fit.resid)
    diagnostic = residual[burn:]
    if len(diagnostic) < 3 or not np.isfinite(diagnostic).all() or np.ptp(diagnostic) == 0:
        raise ValueError('可用创新残差不足或方差为零，无法诊断此模型。')
    count = min(lags, len(diagnostic) - 1)
    dof = p + q + P + Q
    if count:
        lb = acorr_ljungbox(diagnostic, lags=np.arange(1, count + 1), model_df=dof, return_df=True)
        diagnostics = pd.DataFrame({'lag': lb.index, 'statistic': lb.lb_stat.to_numpy(),
                                     'p_value': lb.lb_pvalue.to_numpy(),
                                     'df': np.arange(1, count + 1) - dof,
                                     'null': '截至该滞后残差无自相关'})
    else:
        diagnostics = pd.DataFrame(columns=['lag', 'statistic', 'p_value', 'df', 'null'])
    prediction = fit.get_forecast(steps=forecast_steps)
    ci = np.asarray(prediction.conf_int(alpha=alpha))
    predicted = np.asarray(prediction.predicted_mean)
    if not np.isfinite(np.r_[predicted, ci.ravel()]).all():
        raise ValueError('预测或区间包含非有限值，请检查模型阶数。')
    future = pd.DataFrame({'step': np.arange(1, forecast_steps + 1),
                           'sequence': np.arange(len(data) + 1, len(data) + forecast_steps + 1),
                           'time': pd.NaT, 'elapsed': pd.NaT, 'predicted': predicted,
                           'ci_lower': ci[:, 0], 'ci_upper': ci[:, 1]})
    if step is not None:
        try:
            delta = pd.timedelta_range(start=step, periods=forecast_steps, freq=step)
            future['elapsed'] = data.elapsed.iloc[-1] + delta
            if data.time.notna().any():
                future['time'] = data.time.iloc[-1] + delta
        except (ValueError, OverflowError) as exc:
            raise ValueError('预测时间超出日期/时间间隔范围，请缩短预测步数。') from exc
    future['source_row'] = pd.array([pd.NA] * forecast_steps, dtype='Int64')
    future['source_index'] = None
    future['source_rows'] = [[] for _ in range(forecast_steps)]
    future['source_indices'] = [[] for _ in range(forecast_steps)]
    summary = pd.DataFrame([{'model': 'SARIMA' if seasonal else 'ARIMA', 'order': order,
                            'seasonal_order': seasonal_order, 'nobs': len(data),
                            'effective_nobs': fit.nobs_effective,
                            'log_likelihood': fit.llf, 'aic': fit.aic, 'bic': fit.bic,
                            'rmse': np.sqrt(np.mean(diagnostic ** 2)), 'converged': converged,
                            'burn': burn, 'alpha': alpha}])
    notes.append('模型为高斯状态空间极大似然；预测区间为给定估计参数的未来观测区间，不含参数估计不确定性。')
    notes.append(f'Ljung-Box 使用去 burn={burn} 的创新残差，df=lag-{dof}；df<=0 的 p 值不可用。')
    tables = {'model_summary': summary,
              'model_coefficients': _coefficient_table(fit, fit.param_names, alpha),
              'diagnostics': diagnostics,
              'residuals': data.assign(fitted=np.asarray(fit.fittedvalues), residual=residual,
                                      diagnostic_used=np.arange(len(data)) >= burn),
              'residual_acf': _correlations(diagnostic, lags, alpha), 'forecast': future}
    return tables, fit


def analyze_time_series(df, y, time=None, other=None, interval='1s', missing='error',
                        duplicates='error', irregular='error', lags=20, period=None,
                        decomposition='additive', order=(1, 0, 0),
                        seasonal_order=(0, 0, 0, 0), forecast_steps=10, alpha=.05,
                        cancel=None, analysis='all'):
    """按模块顶部合约返回纯计算结果；all 的部分失败见 status/notes。"""
    _check_cancel(cancel)
    choices = ('correlation', 'decomposition', 'stationarity', 'ARIMA', 'SARIMA', 'all')
    if analysis not in choices:
        raise ValueError(f'analysis 必须为 {choices}。')
    lags = _integer(lags, 'lags')
    if isinstance(alpha, (bool, np.bool_)) or not np.isscalar(alpha):
        raise ValueError('alpha 必须为 0 与 1 之间的实数。')
    try:
        alpha = float(alpha)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError('alpha 必须为 0 与 1 之间的实数。') from exc
    if not 0 < alpha < 1:
        raise ValueError('alpha 必须为 0 与 1 之间的实数。')
    notes = []
    data, series, step = _prepare(df, y, time, other, interval, missing, duplicates, irregular, notes)
    result = TimeSeriesResult({'data': data}, notes, series)
    status = []

    def run(name, function):
        _check_cancel(cancel)
        try:
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter('always')
                tables = function()
            result.tables.update(tables)
            status.append((name, 'ok', ''))
        except (ValueError, np.linalg.LinAlgError) as exc:
            if analysis != 'all':
                raise ValueError(f'{name}：{exc}') from exc
            status.append((name, 'unavailable', str(exc)))
            notes.append(f'{name} 不可用：{exc}')
        finally:
            for warning in caught:
                notes.append(f'{name}：{warning.message}')
        _check_cancel(cancel)

    values = series.to_numpy()
    if analysis in ('correlation', 'all'):
        run('correlation', lambda: _correlation_tables(data, lags, alpha, cancel, notes))
    if analysis in ('decomposition', 'all'):
        run('trend', lambda: _trend(data, alpha))
        notes.append('趋势 OLS：斜率单位为每个观测步，t 检验/区间假设独立同方差误差；序列相关时推断应谨慎。')
        if period is not None:
            def decompose():
                cycle = _integer(period, 'period', 2)
                if decomposition not in ('additive', 'multiplicative'):
                    raise ValueError('decomposition 必须为 additive/multiplicative。')
                if len(values) < 2 * cycle:
                    raise ValueError('季节分解至少需要两个完整周期。')
                if decomposition == 'multiplicative' and np.any(values <= 0):
                    raise ValueError('乘法季节分解要求所有观测严格为正。')
                fit = seasonal_decompose(values, model=decomposition, period=cycle,
                                         two_sided=True, extrapolate_trend=0)
                return {'decomposition': data.assign(trend=fit.trend, seasonal=fit.seasonal,
                                                      residual=fit.resid)}
            run('decomposition', decompose)
        else:
            status.append(('decomposition', 'unavailable', '未指定 period，仅输出趋势。'))
            notes.append('未指定 period，未推断季节周期，仅输出趋势 OLS。')
    if analysis in ('stationarity', 'all'):
        run('stationarity', lambda: _stationarity(values, lags, alpha, notes))
    if analysis in ('ARIMA', 'SARIMA', 'all'):
        def model():
            steps = _integer(forecast_steps, 'forecast_steps', 1)
            seasonal = analysis == 'SARIMA'
            if analysis == 'all':
                if not isinstance(seasonal_order, (tuple, list)) or len(seasonal_order) != 4:
                    raise ValueError('seasonal_order 必须是 (P,D,Q,s)。')
                spec = tuple(_integer(v, 'seasonal_order') for v in seasonal_order)
                seasonal = spec != (0, 0, 0, 0)
            tables, fit = _fit_model(data, series, step, lags, order, seasonal_order,
                                      seasonal, steps, alpha, cancel, notes)
            result.model = fit
            return tables
        run('model', model)
    result.tables['status'] = pd.DataFrame(status, columns=['analysis', 'status', 'message'])
    return result
