"""个体高级 SPC 纯计算；历史基线固定，不修改数据或自动排除异常。

EWMA/CUSUM 为独立个体观测，不把子组均值的标准差当个体标准差。
T² 复用 PCA 已验证的公共计算，但监控全部原变量，未做 PCA 降维。
参考 NIST handbook pmc324.htm / pmc313.htm；Dataplot HOTELLING。
"""
from dataclasses import dataclass
import json

import numpy as np
import pandas as pd
from scipy.signal import lfilter

from pca_analysis import hotelling_statistics, t2_limits


NELSON = {
    1: '单点超出 3σ', 2: '连续9点在中心同侧', 3: '连续6点严格递增或递减',
    4: '连续14点严格交替升降', 5: '连续3点中至少2点及当前点超2σ且同侧',
    6: '连续5点中至少4点及当前点超1σ且同侧', 7: '连续15点均在1σ内（含边界）',
    8: '连续8点均在1σ外且分布两侧',
}


@dataclass
class SPCResult:
    kind: str
    tables: dict
    notes: list


def _cancel(event):
    if event is not None and event.is_set():
        raise InterruptedError('分析已取消。')


def _number(value, name, positive=False):
    if isinstance(value, (bool, complex, np.complexfloating)) or not isinstance(value, (int, float, np.number)):
        raise ValueError(name+'须为有限实数。')
    value = float(value)
    if not np.isfinite(value) or (positive and value <= 0):
        raise ValueError(name+('须为正的有限实数。' if positive else '须为有限实数。'))
    return value


def _prepare(df, columns, missing):
    if not isinstance(df, pd.DataFrame) or not df.columns.is_unique:
        raise ValueError('输入须为列名唯一的工作表。')
    if any(c not in df for c in columns):
        raise ValueError('工作表缺少所选变量。')
    for c in columns:
        if (not pd.api.types.is_numeric_dtype(df[c]) or pd.api.types.is_bool_dtype(df[c])
                or pd.api.types.is_complex_dtype(df[c])):
            raise ValueError('变量须为实数数值列：'+str(c))
    values = df.loc[:, columns].to_numpy(dtype=float, na_value=np.nan)
    if np.isinf(values).any():
        raise ValueError('观测包含无穷大。')
    valid = ~np.isnan(values).any(axis=1)
    if not valid.all() and missing == 'error':
        raise ValueError('存在缺失值；可显式选择删除不完整行。')
    if not valid.any():
        raise ValueError('没有有效观测。')
    positions = np.flatnonzero(valid)
    source = pd.DataFrame({'source_row': positions+1,
                           'source_index': pd.Series([df.index[i] for i in positions], dtype=object),
                           'sequence': np.arange(1, len(positions)+1)})
    return values[valid], source


def nelson_events(z, rules=tuple(NELSON), cancel=None):
    """返回 (窗口末端0基位置,规则编号,窗口起点0基位置)。严格界限；相等打断。

    标记检测时刻而不是追溯涂红整段；报告另存完整窗口来源行供追踪。
    """
    z = np.asarray(z, dtype=float)
    if z.ndim != 1 or not np.isfinite(z).all():
        raise ValueError('Nelson 输入须为有限的一维标准化序列。')
    rules = tuple(rules)
    if any(isinstance(r, bool) or not isinstance(r, (int, np.integer)) or r not in NELSON for r in rules):
        raise ValueError('Nelson 规则须从 1～8 选择。')
    if len(set(rules)) != len(rules):
        raise ValueError('Nelson 规则不可重复。')
    events = []
    lengths = {1: 1, 2: 9, 3: 6, 4: 14, 5: 3, 6: 5, 7: 15, 8: 8}
    # 固定小窗口向量化；避免逐样本创建 DataFrame 或 O(n²) 运行段扫描。
    for rule in sorted(rules):
        _cancel(cancel)
        length = lengths[rule]
        if len(z) < length:
            continue
        w = np.lib.stride_tricks.sliding_window_view(z, length)
        if rule == 1:
            hit = np.abs(w[:, 0]) > 3
        elif rule == 2:
            hit = (w > 0).all(axis=1) | (w < 0).all(axis=1)
        elif rule == 3:
            diff = np.diff(w, axis=1)
            hit = (diff > 0).all(axis=1) | (diff < 0).all(axis=1)
        elif rule == 4:
            diff = np.sign(np.diff(w, axis=1))
            hit = (diff[:, 1:]*diff[:, :-1] == -1).all(axis=1)
        elif rule in (5, 6):
            threshold, count = (2, 2) if rule == 5 else (1, 4)
            hit = (((w > threshold).sum(axis=1) >= count) & (w[:, -1] > threshold)
                   | ((w < -threshold).sum(axis=1) >= count) & (w[:, -1] < -threshold))
        elif rule == 7:
            hit = (np.abs(w) <= 1).all(axis=1)
        else:
            hit = (np.abs(w) > 1).all(axis=1) & (w > 0).any(axis=1) & (w < 0).any(axis=1)
        events.extend((int(start+length-1), rule, int(start)) for start in np.flatnonzero(hit))
    return sorted(events)


def _univariate(values, source, kind, mean, sigma, lam, width, k, h, rules, cancel):
    out = source.copy()
    x = values[:, 0]
    z = (x-mean)/sigma
    if not np.isfinite(z).all():
        raise ValueError('标准化溢出；请检查尺度。')
    out['value'], out['z'] = x, z
    out['center'] = mean
    events = []
    if kind == 'EWMA':
        # Z_t = mu + lambda * sum((1-lambda)^(t-j) * (x_j-mu))。
        out['statistic'] = mean+lfilter([lam], [1, -(1-lam)], x-mean)
        t = np.arange(1, len(x)+1)
        spread = width*sigma*np.sqrt(lam/(2-lam)*(-np.expm1(2*t*np.log1p(-lam)))) if lam < 1 else np.full(len(x), width*sigma)
        out['lower'], out['upper'] = mean-spread, mean+spread
        for i in np.flatnonzero((out.statistic < out.lower) | (out.statistic > out.upper)):
            events.append((int(i), 'EWMA', int(i), float(out.statistic.iloc[i])))
    elif kind == 'CUSUM':
        plus, minus = np.empty(len(x)), np.empty(len(x))
        cp = cm = 0.
        for i, value in enumerate(z):
            if i % 2048 == 0:
                _cancel(cancel)
            cp, cm = max(0., cp+value-k), max(0., cm-value-k)
            plus[i], minus[i] = cp, -cm
            if cp > h:
                events.append((i, 'CUSUM+', i, cp))
            if cm > h:
                events.append((i, 'CUSUM-', i, -cm))
        out['statistic'], out['negative'] = plus, minus
        out['lower'], out['center'], out['upper'] = -h, 0., h
    else:
        out['statistic'], out['lower'], out['upper'] = x, mean-3*sigma, mean+3*sigma
        events = [(i, 'Nelson '+str(r), start, float(x[i])) for i, r, start in nelson_events(z, rules, cancel)]
    return out, events


def _attach_events(out, events, descriptions):
    labels = [[] for _ in range(len(out))]
    records = []
    rows, indices = out.source_row.to_numpy(), out.source_index.to_numpy()
    for end, rule, start, value in events:
        labels[end].append(rule)
        records.append({'source_row': rows[end], 'source_index': indices[end], 'sequence': end+1,
                        'rule': rule, 'description': descriptions.get(rule, rule), 'statistic': value,
                        'lower': out.lower.iloc[end], 'upper': out.upper.iloc[end],
                        'window_start': start+1, 'window_end': end+1,
                        'members': json.dumps(rows[start:end+1].tolist())})
    out['alarm'] = [bool(v) for v in labels]
    out['rules'] = ['; '.join(v) for v in labels]
    return pd.DataFrame(records, columns=['source_row', 'source_index', 'sequence', 'rule',
        'description', 'statistic', 'lower', 'upper', 'window_start', 'window_end', 'members'])


def analyze_spc(df, columns, kind='EWMA', baseline=None, mean=None, sigma=None,
                ewma_lambda=.2, ewma_width=3., cusum_k=.5, cusum_h=5.,
                rules=tuple(NELSON), confidence=.95, missing='error', cancel=None):
    """历史 baseline 是独立工作表；None 为当前数据 Phase I 回顾。

    mean/sigma 同时给出时为已知参数，仅用于单变量且不能与 baseline 混用。
    缺失默认报错；显式 drop 保留来源位置但按剩余顺序连续监控。
    """
    _cancel(cancel)
    if kind not in ('EWMA', 'CUSUM', 'Nelson', 'T2'):
        raise ValueError('未知控制图类型。')
    columns = list(columns)
    if not columns or len(set(columns)) != len(columns):
        raise ValueError('请选择不重复的变量。')
    if kind != 'T2' and len(columns) != 1:
        raise ValueError('单变量控制图须只选择一列。')
    rules = tuple(rules)
    if missing not in ('error', 'drop'):
        raise ValueError('缺失策略须为 error 或 drop。')
    confidence = _number(confidence, '置信度')
    if confidence not in (.95, .99):
        raise ValueError('控制限置信度须为 95% 或 99%。')
    if (mean is None) != (sigma is None):
        raise ValueError('已知均值和标准差必须同时填写。')
    known = mean is not None
    if known and (baseline is not None or kind == 'T2'):
        raise ValueError('已知单变量参数不可与历史基线或多变量 T² 混用。')
    current, source = _prepare(df, columns, missing)
    base, base_source = _prepare(baseline, columns, missing) if baseline is not None else (current, source)
    if not known and len(base) < 2:
        raise ValueError('估计基线参数至少需要两个有效观测。')
    mu = np.array([_number(mean, '已知均值')]) if known else base.mean(axis=0)
    sd = np.array([_number(sigma, '已知标准差', True)]) if known else base.std(axis=0, ddof=1)
    if not np.isfinite(mu).all() or not np.isfinite(sd).all() or (sd <= 0).any():
        raise ValueError('基线包含常量列或尺度溢出；标准差须为正。')
    phase = 'known' if known else 'phase2' if baseline is not None else 'phase1'
    notes = ['个体观测按工作表当前行序分析，假设过程稳定且观测独立；默认不补值、不排除异常。',
             '当前监控阶段：'+phase+'；历史基线参数在监控期间固定。',
             '报警标记表示检测时刻；Nelson 窗口成员另存于 members，不将整窗误作逐点越限。',
             '多个时刻/多个规则的联合误报率不等于单点显著性水平。']
    if phase == 'phase1':
        notes.append('当前数据用于估计自身基线；单变量采用样本标准差 ddof=1，EWMA/CUSUM 限为代入估计的回顾性近似。应先确认基线稳定，再监控独立新样本。')
    if missing == 'drop':
        notes.append('显式删除不完整行后，按剩余观测连续计算；来源行不重编号，间隔与运行段语义可能改变。')
    comparison = []
    for j, c in enumerate(columns):
        comparison.append([c, 0 if known else len(base), mu[j], sd[j], len(current), current[:, j].mean(),
                           current[:, j].std(ddof=1) if len(current) > 1 else np.nan,
                           current[:, j].mean()-mu[j]])
    tables = {'parameters': pd.DataFrame({'variable': columns, 'mean': mu, 'std': sd}),
              'comparison': pd.DataFrame(comparison, columns=['variable','baseline_n','baseline_mean','baseline_std',
                  'current_n','current_mean','current_std','difference'])}
    descriptions = {'Nelson '+str(r): text for r, text in NELSON.items()}
    if kind == 'T2':
        p, n = len(columns), len(base)
        if n <= p+1:
            raise ValueError('T² 个体 Phase I 基线要求样本量大于变量数+1。')
        covariance = np.atleast_2d(np.cov(base, rowvar=False, ddof=1))
        def monitor(values, origin, stage):
            frame = origin.copy()
            frame['statistic'] = hotelling_statistics(values, mu, covariance)
            frame['lower'], frame['center'] = 0., 0.
            frame['upper'] = t2_limits(n, p, confidence, stage)
            frame['phase'] = stage
            return frame
        out = monitor(current, source, phase)
        events = [(int(i), 'T2', int(i), float(out.statistic.iloc[i])) for i in np.flatnonzero(out.statistic > out.upper)]
        tables['covariance'] = pd.DataFrame([(a,b,covariance[i,j]) for i,a in enumerate(columns)
            for j,b in enumerate(columns)], columns=['row_variable','column_variable','covariance'])
        tables['limits'] = pd.DataFrame([[stage, conf, 0., t2_limits(n,p,conf,stage),
            '((n-1)^2/n) Beta(p/2,(n-p-1)/2)' if stage == 'phase1' else 'p(n+1)(n-1)/(n(n-p)) F(p,n-p)']
            for stage in ('phase1','phase2') for conf in (.95,.99)], columns=['phase','confidence','lower','upper','method'])
        if baseline is not None:
            historical = monitor(base, base_source, 'phase1')
            _attach_events(historical, [(int(i),'T2',int(i),float(historical.statistic.iloc[i])) for i in np.flatnonzero(historical.statistic > historical.upper)], {})
            tables['baseline'] = historical
        notes.append('T²=(x−μ)ᵀS⁻¹(x−μ)，全部原变量、样本协方差 ddof=1；拒绝奇异矩阵，不降维或伪逆。假设独立同分布多元正态。')
        notes.append('Phase I 自身基线用 Beta，Phase II 独立新观测用 F；95%/99% 为单侧上覆盖率，零为统计量边界，不检验低值异常。未自动剔除历史异常。')
    else:
        lam = _number(ewma_lambda, 'EWMA λ', True) if kind == 'EWMA' else .2
        if lam > 1:
            raise ValueError('EWMA λ 须不超过 1。')
        width = _number(ewma_width, 'EWMA 限宽 L', True) if kind == 'EWMA' else 3.
        k = _number(cusum_k, 'CUSUM k') if kind == 'CUSUM' else .5
        h = _number(cusum_h, 'CUSUM h', True) if kind == 'CUSUM' else 5.
        if k < 0:
            raise ValueError('CUSUM k 须非负。')
        out, events = _univariate(current, source, kind, mu[0], sd[0], lam, width, k, h, rules, cancel)
        out['phase'] = phase
        if baseline is not None:
            historical, historical_events = _univariate(base, base_source, kind, mu[0], sd[0], lam, width, k, h, rules, cancel)
            historical['phase'] = 'phase1'
            _attach_events(historical, historical_events, descriptions)
            tables['baseline'] = historical
        if kind == 'EWMA':
            notes.append('Z₀=μ；Z_t=λx_t+(1−λ)Z_(t−1)，上下限 μ±Lσ√[λ/(2−λ)·(1−(1−λ)^(2t))]。监控从 t=1 重新启动，不延续历史末端状态。')
            settings = [('lambda',lam),('L',width)]
        elif kind == 'CUSUM':
            notes.append('z=(x−μ)/σ；C⁺=max(0,C⁺前+z−k)，C⁻=max(0,C⁻前−z−k)，初值零。图上负支画 −C⁻；严格超过 h 报警，报警后不自动复位。新监控独立从零启动。')
            settings = [('k',k),('h',h)]
        else:
            notes.append('Nelson 规则仅作用原始观测；区界点归内区（规则7含±1σ），超区用严格不等式。等于中心打断同侧，相同观测打断趋势/交替。规则5/6当前点也须位于相应同侧超区；规则8要求两侧均有点。')
            settings = [('rules',','.join(str(r) for r in rules))]
        tables['limits'] = out[['sequence','lower','center','upper']].copy()
        tables['settings'] = pd.DataFrame(settings, columns=['parameter','value'])
    tables['alarms'] = _attach_events(out, events, descriptions)
    tables['observations'] = out
    if not np.isfinite(out[['statistic','lower','upper']].to_numpy()).all() or ('negative' in out and not np.isfinite(out.negative).all()):
        raise ValueError('控制图计算溢出；请检查输入尺度。')
    tables['summary'] = pd.DataFrame([['chart',kind],['phase',phase],['n',len(current)],['baseline_n',0 if known else len(base)],
        ['variables',', '.join(map(str,columns))],['alarm_points',int(out.alarm.sum())],['alarm_records',len(events)],
        ['confidence',confidence if kind == 'T2' else np.nan]], columns=['parameter','value'])
    _cancel(cancel)
    return SPCResult(kind, tables, notes)
