"""过程能力核心：固定估计方法，原序来源追溯，未提供的区间使用 NA。

非正态主指数采用百分位法；Johnson 仅为 SU MLE，不是 Minitab 全族择优。
"""
from numbers import Real
import warnings as python_warnings

import numpy as np
import pandas as pd
from scipy import optimize, special, stats


def transform_values(values, parameters, inverse=False):
    """按结果中的变换参数正/逆变换；域外与溢出均明确失败。"""
    x = np.asarray(values, dtype=float)
    method = parameters['method']
    with np.errstate(over='ignore', invalid='ignore', divide='ignore'):
        if method == 'boxcox':
            lam = parameters['lambda']
            if not np.isfinite(lam):
                raise ValueError('Box-Cox λ 必须有限')
            if inverse:
                if lam != 0 and np.any(1 + lam*x <= 0):
                    raise ValueError('Box-Cox 逆变换超出像域：要求 1+λy>0')
                y = special.inv_boxcox(x, lam)
            else:
                if np.any(x <= 0):
                    raise ValueError('Box-Cox 数据、规格与目标必须严格为正')
                y = special.boxcox(x, lam)
        elif method == 'johnson':
            a, b, loc, scale = [parameters[key] for key in ('a', 'b', 'loc', 'scale')]
            if not np.isfinite([a, b, loc, scale]).all() or b <= 0 or scale <= 0:
                raise ValueError('Johnson SU 参数要求有限且 b、scale>0')
            y = loc + scale*np.sinh((x-a)/b) if inverse else a+b*np.arcsinh((x-loc)/scale)
        else:
            raise ValueError('未知变换方法')
    if not np.isfinite(x).all() or not np.isfinite(y).all():
        raise ValueError('变换产生非有限结果或溢出')
    return y


def _mle_optimizer(func, initial, args=(), disp=0):
    fit = optimize.minimize(func, initial, args=args, method='Nelder-Mead',
                            options={'maxiter': 6000, 'xatol': 1e-8, 'fatol': 1e-8})
    if not fit.success:
        raise ValueError('MLE 未收敛：' + str(fit.message))
    return fit.x


def _fit_positive(x, distribution):
    dist = {'weibull': stats.weibull_min, 'lognormal': stats.lognorm,
            'gamma': stats.gamma}[distribution]
    try:
        with python_warnings.catch_warnings():
            python_warnings.simplefilter('error', RuntimeWarning)
            parameters = dist.fit(x, floc=0, optimizer=_mle_optimizer)
        model = dist(*parameters)
        if (not np.isfinite(parameters).all() or parameters[0] <= 0 or
                parameters[-1] <= 0 or parameters[-2] != 0 or
                not np.isfinite(model.logpdf(x)).all()):
            raise ValueError('非法拟合参数')
    except (ValueError, RuntimeError, FloatingPointError, RuntimeWarning) as exc:
        raise ValueError('正域分布 MLE 拟合失败或未收敛：' + str(exc)) from exc
    return model, parameters


def _diagnose(x, model, distribution):
    ordered = np.sort(x)
    n = len(x)
    ad = -n - np.sum((2*np.arange(1, n+1)-1) *
                     (model.logcdf(ordered) + model.logsf(ordered[::-1]))) / n
    fit = {'AD': float(ad), 'p_value': None, 'converged': True}
    if distribution == 'normal':
        test = stats.anderson(x, dist='norm')
        fit.update(AD=float(test.statistic), critical_5pct=float(test.critical_values[2]),
                   critical_10pct=float(test.critical_values[1]),
                   mismatch=bool(test.statistic > test.critical_values[2]),
                   method='正态估参 AD 临界值；未提供 p 值')
    else:
        # Refit each simulated sample: a fixed-parameter KS p value is invalid here.
        observed = float(stats.kstest(x, model.cdf).statistic)
        rng = np.random.default_rng(20261023)
        exceed = 0
        for _ in range(199):
            sample = model.rvs(size=n, random_state=rng)
            refit, _ = _fit_positive(sample, distribution)
            exceed += stats.kstest(sample, refit.cdf).statistic >= observed
        p = (exceed+1)/200
        fit.update(KS=observed, p_value=p, bootstrap_replicates=199,
                   mismatch=p < .05,
                   method='估参 KS 参数自举（每次重拟合，199次）；AD 仅统计量、无 p 值')
    return fit


def _side_interval(t, n, h, confidence):
    """独立正态样本单侧 Ppl/Ppu：非中心 t 参数的等尾反演。"""
    # Symmetry avoids SciPy nct.cdf NaN at negative t and large positive delta.
    if t < 0:
        lower, upper = _side_interval(-t, n, h, confidence)
        return -upper, -lower
    alpha = 1-confidence
    bound = max(10., 2*abs(t))
    endpoints = []
    for probability in (1-alpha/2, alpha/2):
        def equation(delta):
            return stats.nct.cdf(t, n-1, delta)-probability
        while equation(-bound) < 0 or equation(bound) > 0:
            bound *= 2
            if not np.isfinite(bound):
                raise ValueError('非中心 t 区间无法括住根')
        endpoints.append(optimize.brentq(equation, -bound, bound)/(h*np.sqrt(n)))
    return tuple(endpoints)


def _prepare(data, subgroup_size, subgroup_ids, missing):
    raw = pd.Series(data, copy=True) if not isinstance(data, pd.Series) else data.copy(deep=True)
    values = raw.to_numpy(dtype=object)
    if missing not in ('error', 'drop'):
        raise ValueError('missing 必须为 error 或 drop')
    if isinstance(subgroup_size, bool) or not isinstance(subgroup_size, (int, np.integer)) or subgroup_size < 1:
        raise ValueError('子组大小必须为正整数')
    if subgroup_ids is None:
        if len(raw) % subgroup_size:
            raise ValueError('固定子组存在余数；不能丢弃未满子组')
        ids = np.arange(len(raw)) // subgroup_size
    else:
        if isinstance(subgroup_ids, pd.Series) and not subgroup_ids.index.equals(raw.index):
            raise ValueError('子组 ID 与测量列的来源索引必须一致')
        ids = pd.Series(subgroup_ids, dtype=object).to_numpy()
        if len(ids) != len(raw):
            raise ValueError('子组 ID 长度须与测量列一致')
    absent = pd.isna(values) | pd.isna(ids)
    if np.any(absent) and missing == 'error':
        raise ValueError('数据或子组 ID 存在缺失；仅 missing=drop 可删除')
    present_ids = ids[~pd.isna(ids)]
    seen = set()
    previous = None
    for i, label in enumerate(present_ids):
        try:
            if i == 0 or label != previous:
                if label in seen:
                    raise ValueError('子组 ID 不连续重复；不能排序合并')
                seen.add(label)
            previous = label
        except TypeError as exc:
            raise ValueError('子组 ID 必须为可比较的标量标识符') from exc
    keep = ~absent
    valid = values[keep]
    if any(not isinstance(v, Real) or isinstance(v, (bool, np.bool_)) for v in valid):
        raise ValueError('测量列必须为实数；不自动转换文本或复数')
    x = np.asarray(valid, dtype=float)
    if len(x) < 3:
        raise ValueError('有效观测不足：至少需要三个观测值')
    if not np.isfinite(x).all():
        raise ValueError('测量列必须为有限实数；无穷值不能按缺失删除')
    if np.ptp(x) == 0:
        raise ValueError('常数数据无法估计过程能力')
    ids = ids[keep]
    cuts = np.flatnonzero(ids[1:] != ids[:-1]) + 1
    positions = np.split(np.arange(len(x)), cuts)
    sizes = [len(g) for g in positions]
    if min(sizes) == 1 and max(sizes) > 1:
        raise ValueError('混合单值与多观测子组无法统一估计；每个子组至少两个观测值')
    return x, ids, positions, raw.index.to_numpy()[keep], np.flatnonzero(keep)+1, int(absent.sum())


def analyze_capability(data, lsl=None, usl=None, target=None, subgroup_size=1,
                       subgroup_ids=None, distribution='normal', confidence=.95,
                       k=6, transform=None, fixed_lambda=None, missing='error',
                       allow_no_specs=False):
    """返回绘图/报告共享的快照字典；所有能力量和规格均在分析尺度。

    source_row 是原输入位置（1起），source_index 保留 Series 原索引。
    groups 按原序；固定分组在缺失删除之前确定，不跨缺失重排子组。
    """
    if distribution not in ('normal', 'weibull', 'lognormal', 'gamma'):
        raise ValueError('不支持的分布')
    if transform not in (None, 'boxcox', 'johnson'):
        raise ValueError('不支持的变换')
    if transform is not None and distribution != 'normal':
        raise ValueError('非正态分布必须使用原尺度，不能同时变换')
    if fixed_lambda is not None and transform != 'boxcox':
        raise ValueError('固定 λ 仅适用于 Box-Cox')
    for name, value in [('LSL', lsl), ('USL', usl), ('Target', target),
                        ('confidence', confidence), ('K', k), ('λ', fixed_lambda)]:
        if value is not None and (not isinstance(value, Real) or isinstance(value, (bool, np.bool_)) or not np.isfinite(value)):
            raise ValueError(name+' 必须为有限实数')
    if confidence is None or k is None or not 0 < confidence < 1 or k <= 0:
        raise ValueError('置信水平须在0和1之间，K须为正数')
    if lsl is None and usl is None and not (allow_no_specs and transform is not None):
        raise ValueError('过程能力至少需要一侧规格；纯变换诊断可无规格')
    if lsl is not None and usl is not None and lsl >= usl:
        raise ValueError('规格要求 LSL < USL；不自动排序')
    x, ids, positions, source_index, source_row, dropped = _prepare(
        data, subgroup_size, subgroup_ids, missing)
    original = x.copy()
    original_specs = dict(lsl=lsl, usl=usl, target=target)
    notes = []
    if dropped:
        notes.append(f'显式删除 {dropped} 行不完整观测；子组边界按原始行保留。')
    if len(x) < 30:
        notes.append('小样本（n<30）：拟合、能力及极端尾部 PPM 不可靠。')
    parameters = None
    if transform == 'boxcox':
        if np.any(x <= 0):
            raise ValueError('Box-Cox 数据必须严格为正')
        try:
            lam = float(stats.boxcox_normmax(x, method='mle')) if fixed_lambda is None else float(fixed_lambda)
        except (ValueError, RuntimeError, FloatingPointError) as exc:
            raise ValueError('Box-Cox λ MLE 未收敛') from exc
        parameters = {'method': transform, 'lambda': lam,
                      'estimation': '正态剖面似然 MLE，未舍入' if fixed_lambda is None else '固定 λ'}
        notes.append('Box-Cox 使用 (x^λ−1)/λ（λ=0 为 log）；不是 Minitab 子组优化/舍入约定。')
    elif transform == 'johnson':
        try:
            with python_warnings.catch_warnings():
                python_warnings.simplefilter('error', RuntimeWarning)
                a, b, loc, scale = stats.johnsonsu.fit(x, optimizer=_mle_optimizer)
        except (ValueError, RuntimeError, RuntimeWarning) as exc:
            raise ValueError('Johnson SU MLE 拟合失败或未收敛：'+str(exc)) from exc
        parameters = dict(method=transform, a=a, b=b, loc=loc, scale=scale,
                          estimation='仅 Johnson SU MLE；非 Minitab SB/SL/SU Chou 择族算法')
        notes.append('Johnson 仅实现 SU MLE；未实现 Minitab 全族 Chou 算法。')
    if parameters is not None:
        x = transform_values(x, parameters)
        lsl, usl, target = [None if v is None else float(transform_values(v, parameters))
                            for v in (lsl, usl, target)]
    groups = [x[p].copy() for p in positions]
    mean, overall = float(np.mean(x)), float(np.std(x, ddof=1))
    if not np.isfinite([mean, overall]).all() or overall <= 0:
        raise ValueError('变换后为常数或方差溢出，无法估计能力')
    df = sum(len(g)-1 for g in groups)
    c4 = None
    if df == 0:
        within = float(np.mean(np.abs(np.diff(x))) / (2/np.sqrt(np.pi)))
        within_method = '相邻 MR(2)均值/d2(2)，d2=2/√π；重叠 MR 无精确卡方区间'
    else:
        sp = np.sqrt(sum(np.sum((g-np.mean(g))**2) for g in groups)/df)
        c4 = np.sqrt(2/df)*np.exp(special.gammaln((df+1)/2)-special.gammaln(df/2))
        within = float(sp/c4)
        within_method = '合并组内标准差 sp/c4(df+1)；要求独立正态、组内同方差'
    if not np.isfinite(within) or within <= 0:
        raise ValueError('组内波动为零或非有限，无法估计组内能力')
    if distribution == 'normal':
        model = stats.norm(mean, overall)
        model_parameters = {'loc': mean, 'scale': overall}
    else:
        if np.any(x <= 0):
            raise ValueError('Weibull/Lognormal/Gamma 观测必须严格为正；不自动平移')
        model, fitted = _fit_positive(x, distribution)
        model_parameters = dict(shape=fitted[0], loc=fitted[1], scale=fitted[2])
        notes.append('非正态主指数采用百分位法；不是 Minitab 默认 Z-score 法。')
        notes.append('非正态 MR/子组标准差仅供近似控制图；不定义原尺度 Cp/Cpk。')
    fit = _diagnose(x, model, distribution)
    fit.update(distribution=distribution, parameters=model_parameters,
               support='实数域' if distribution == 'normal' else '(0,+∞)，位置参数固定0')
    if parameters is not None:
        fit['method'] += '；变换选参后有选择偏差，不是独立正态性验证'
        if fit['AD'] > fit['critical_10pct']:
            raise ValueError('无合格变换：变换后正态 AD 超过10%临界值（选参后诊断，非独立检验）')
        notes.append('变换后 AD 使用估参正态临界值作诊断，选参后有选择偏差；未提供校准 p 值。')
    elif fit['mismatch']:
        notes.append('拟合失配：拒绝指定分布（5%水平），能力与预计 PPM 仅供诊断。')
    names = ('Cp', 'Cpl', 'Cpu', 'Cpk', 'Pp', 'Ppl', 'Ppu', 'Ppk', 'Cpm')
    indices = dict.fromkeys(names)
    h = k/2
    if distribution == 'normal':
        for prefix, sigma in [('C', within), ('P', overall)]:
            if lsl is not None and usl is not None:
                indices[prefix+'p'] = (usl-lsl)/(k*sigma)
            indices[prefix+'pl'] = None if lsl is None else (mean-lsl)/(h*sigma)
            indices[prefix+'pu'] = None if usl is None else (usl-mean)/(h*sigma)
            sides = [indices[prefix+suffix] for suffix in ('pl', 'pu') if indices[prefix+suffix] is not None]
            indices[prefix+'pk'] = min(sides) if sides else None
        if lsl is not None and usl is not None and target is not None:
            indices['Cpm'] = (usl-lsl)/(k*np.hypot(overall, mean-target))
        if transform == 'johnson':
            for name in ('Cp', 'Cpl', 'Cpu', 'Cpk', 'Cpm'):
                indices[name] = None
            notes.append('Johnson SU 能力仅报告整体指标；组内标准差仅供控制图诊断。')
    tail = stats.norm.sf(h)
    # isf retains the upper tail when 1-tail rounds to 1.
    ql, qm, qu = model.ppf(tail), model.ppf(.5), model.isf(tail)
    if not np.isfinite([ql, qm, qu]).all() or not ql < qm < qu:
        raise ValueError('K 对应的模型分位数不可计算或超出数值范围')
    if distribution != 'normal':
        indices['Pp'] = None if lsl is None or usl is None else (usl-lsl)/(qu-ql)
        indices['Ppl'] = None if lsl is None else (qm-lsl)/(qm-ql)
        indices['Ppu'] = None if usl is None else (usl-qm)/(qu-qm)
        sides = [indices[key] for key in ('Ppl', 'Ppu') if indices[key] is not None]
        indices['Ppk'] = min(sides) if sides else None
    observed_counts = {'lower': 0 if original_specs['lsl'] is None else int(np.count_nonzero(original < original_specs['lsl'])),
                       'upper': 0 if original_specs['usl'] is None else int(np.count_nonzero(original > original_specs['usl']))}
    observed_counts['total'] = observed_counts['lower']+observed_counts['upper']
    observed = {key: count/len(original)*1e6 for key, count in observed_counts.items()}
    ppm = {'observed': observed}
    for label, fitted_model in [('overall', model), ('within', stats.norm(mean, within))]:
        if label == 'within' and (distribution != 'normal' or transform == 'johnson'):
            continue
        lower = 0. if lsl is None else float(fitted_model.cdf(lsl))
        upper = 0. if usl is None else float(fitted_model.sf(usl))
        ppm[label] = dict(lower=lower*1e6, upper=upper*1e6, total=(lower+upper)*1e6)
    lower_log = -np.inf if lsl is None else model.logcdf(lsl)
    upper_log = -np.inf if usl is None else model.logsf(usl)
    z = dict(Z_lower=None if lsl is None else float(-special.ndtri_exp(lower_log)),
             Z_upper=None if usl is None else float(-special.ndtri_exp(upper_log)),
             Z_bench=None if lsl is None and usl is None else float(-special.ndtri_exp(np.logaddexp(lower_log, upper_log))))
    if lsl is None and usl is None:
        notes.append('未提供规格：仅变换诊断，不评估能力、超规风险或等价 Z。')
        ppm = {key: dict.fromkeys(('lower', 'upper', 'total')) for key in ppm}
    elif any(value is not None and not np.isfinite(value) for value in z.values()):
        notes.append('规格达到或超出分布支持域/数值尾域，等价 Z 可为无限；不能解释为有限能力保证。')
    intervals = {key: (None, None) for key in names}
    interval_methods = dict.fromkeys(names, '未提供：无本方法实现依据')
    alpha = 1-confidence
    if distribution == 'normal' and parameters is None:
        for key, dof, correction in [('Pp', len(x)-1, 1.), ('Cp', df, c4)]:
            if indices[key] is not None and dof > 0:
                factors = np.sqrt(stats.chi2.ppf([alpha/2, 1-alpha/2], dof)/dof)/correction
                intervals[key] = tuple(indices[key]*factors)
                interval_methods[key] = '卡方区间；独立正态' + ('、同方差子组，基于未修正sp' if key == 'Cp' else '')
        for key in ('Ppl', 'Ppu'):
            if indices[key] is not None:
                try:
                    intervals[key] = _side_interval(indices[key]*h*np.sqrt(len(x)), len(x), h, confidence)
                    interval_methods[key] = '非中心t等尾反演；独立正态样本'
                except (ValueError, RuntimeError, FloatingPointError) as exc:
                    notes.append(f'{key} 非中心t区间未收敛，返回 NA：{exc}')
    sigma_ci = {'overall': (None, None), 'within': (None, None)}
    if distribution == 'normal' and parameters is None:
        sigma_ci['overall'] = tuple(overall*np.sqrt((len(x)-1)/stats.chi2.ppf([1-alpha/2, alpha/2], len(x)-1)))
        if df > 0:
            sigma_ci['within'] = tuple(sp*np.sqrt(df/stats.chi2.ppf([1-alpha/2, alpha/2], df)))
    original_quantiles = None
    if parameters is not None:
        if transform == 'boxcox' and parameters['lambda'] != 0:
            lam = parameters['lambda']
            bound = -1/lam
            outside = model.cdf(bound) if lam > 0 else model.sf(bound)
            fit['outside_transform_domain_probability'] = float(outside)
            notes.append(f'Box-Cox 像域外正态概率={outside:.6g}；尾部是变换尺度正态外推，不能视为完整原尺度分布。')
        quantiles = []
        for value in (ql, qm, qu):
            try:
                quantiles.append(float(transform_values(value, parameters, inverse=True)))
            except ValueError:
                quantiles.append(None)
                notes.append('模型尾部分位超出变换逆域，原尺度对应分位为 NA。')
        original_quantiles = dict(zip(('lower', 'median', 'upper'), quantiles))
    observations = pd.DataFrame({'source_row': source_row, 'source_index': source_index,
                                 '原始观测': original, '分析观测': x,
                                 'subgroup_id': [str(label) for label in ids]})
    summary = pd.DataFrame([{'观测数': len(x), '子组数': len(groups), '均值': mean,
                            '组内标准差': within, '整体标准差': overall,
                            '组内自由度': df if df else None, '组内方法': within_method,
                            'LSL': lsl, 'USL': usl, 'Target': target, 'K': k,
                            '置信水平': confidence, '分析尺度': '变换后' if parameters else '原始'}])
    index_table = pd.DataFrame([{'指标': name, '估计值': indices[name], '置信下限': intervals[name][0],
                                '置信上限': intervals[name][1], '区间方法': interval_methods[name]}
                               for name in names])
    ppm_table = pd.DataFrame([{'类型': {'observed': '实测', 'overall': '预计（整体）', 'within': '预计（组内）'}[key],
                              '下侧PPM': value['lower'], '上侧PPM': value['upper'], '合计PPM': value['total'],
                              '置信下限': None, '置信上限': None} for key, value in ppm.items()])
    for side, label in [('lower', '下侧'), ('upper', '上侧'), ('total', '合计')]:
        ppm_table[label+'超规率'] = ppm_table[label+'PPM']/1e6
        ppm_table[label+'实测计数'] = [observed_counts[side] if key == 'observed' and value[side] is not None else None
                                          for key, value in ppm.items()]
    tables = {'摘要': summary, '能力指数': index_table, 'PPM': ppm_table,
              '拟合诊断': pd.DataFrame([{'项目': key, '值': str(value) if isinstance(value, dict) else value}
                                       for key, value in fit.items()]),
              '变换参数': pd.DataFrame([{'参数': key, '值': value} for key, value in
                                        (parameters or {'method': '无'}).items()]),
              '来源观测': observations,
              '拟合参数': pd.DataFrame([{'参数': key, '估计值': value}
                                        for key, value in model_parameters.items()]),
              '标准差区间': pd.DataFrame([{'标准差': label, '估计值': estimate,
                                           '置信下限': sigma_ci[key][0], '置信上限': sigma_ci[key][1],
                                           '区间方法': '未提供' if sigma_ci[key][0] is None else
                                           '独立正态卡方区间；组内另要求同方差，基于未修正sp'}
                                          for key, label, estimate in [('within', '组内', within), ('overall', '整体', overall)]]),
              '等价Z': pd.DataFrame([{'指标': key, '值': value} for key, value in z.items()])}
    if original_quantiles is not None:
        tables['原尺度分位数'] = pd.DataFrame([original_quantiles])
    if parameters is not None:
        raw_fit = _diagnose(original, stats.norm(np.mean(original), np.std(original, ddof=1)), 'normal')
        tables['原始正态性诊断'] = pd.DataFrame([{'项目': key, '值': value} for key, value in raw_fit.items()])
        fit['original_normality'] = raw_fit
    return dict(data=x.copy(), groups=groups, lsl=lsl, usl=usl, target=target,
                model=model, mean=mean, within_sigma=within, overall_sigma=overall,
                indices=indices, ppm=ppm, fit=fit, warnings=notes, transform=parameters,
                original=original, original_specs=original_specs, original_quantiles=original_quantiles,
                source_index=source_index, source_row=source_row, subgroup_ids=ids,
                tables=tables, k=k, confidence=confidence, intervals=intervals,
                sigma_ci=sigma_ci, z=z)
