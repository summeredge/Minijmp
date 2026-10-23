"""质量工具纯计算；输入工作表只读，返回原精度结果表。"""
import numpy as np
import pandas as pd
from scipy import stats
import math
from decimal import Decimal, InvalidOperation
from itertools import accumulate
from numbers import Integral, Real


def _numeric(series):
    try:
        values = pd.to_numeric(series, errors='raise').to_numpy(dtype=float)
    except (ValueError, TypeError) as exc:
        raise ValueError('测量数据必须为有限数值。') from exc
    if not len(values) or not np.isfinite(values).all():
        raise ValueError('测量数据不能为空、缺失或包含非有限数值。')
    return values


def cause_effect(data, problem):
    if not str(problem).strip():
        raise ValueError('请输入问题或结果（鱼头）。')
    frame = data[['类别', '原因', '子原因']].fillna('').astype(str).apply(lambda column: column.str.strip())
    if frame.empty or frame['类别'].eq('').any():
        raise ValueError('至少需要一个非空主原因类别。')
    if (frame['原因'].eq('') & frame['子原因'].ne('')).any():
        raise ValueError('子原因必须属于一个原因。')
    frame = frame.drop_duplicates().reset_index(drop=True)
    return {'kind': 'cause_effect', 'problem': str(problem).strip(), 'tables': {'原因结构': frame},
            'warnings': ['因果图用于组织假设，不构成因果证明。']}


def multi_vari(data, response, factors):
    if not 1 <= len(factors) <= 4 or len(set(factors)) != len(factors) or response in factors:
        raise ValueError('请选择 1–4 个不同的分类因子，响应列不能作为因子。')
    frame = data[factors].copy()
    reserved = {'N', 'SD', '均值', '最小值', '最大值', '极差'}
    names = set(factors) | reserved
    mapping = {}
    for factor in factors:
        if factor in reserved:
            name = f'{factor}（因子）'
            while name in names:
                name += '*'
            mapping[factor] = name
            names.add(name)
    frame = frame.rename(columns=mapping)
    factors = [mapping.get(factor, factor) for factor in factors]
    if frame.isna().any().any() or any(frame[c].astype(str).str.strip().eq('').any() for c in factors):
        raise ValueError('因子水平不能为空。')
    response_key = '_y'
    while response_key in factors:
        response_key += '_'
    frame[response_key] = _numeric(data[response])
    levels = [list(frame[c].cat.categories) if isinstance(frame[c].dtype, pd.CategoricalDtype) else list(pd.unique(frame[c])) for c in factors]
    if any(len(v) < 2 for v in levels):
        raise ValueError('每个因子至少需要两个水平。')
    combinations = math.prod(len(v) for v in levels)
    if combinations > 10000:
        raise ValueError('因子组合超过 10000，请筛选水平后分析。')
    grouped = frame.groupby(factors, sort=False, observed=True)[response_key]
    summary = grouped.agg(N='size', 均值='mean', SD='std', 最小值='min', 最大值='max')
    coverage = len(summary)/combinations
    if coverage < .6:
        raise ValueError(f'因子组合覆盖率 {coverage:.1%}，低于 Minitab 要求的 60%。')
    index = pd.MultiIndex.from_product(levels, names=factors) if len(factors) > 1 else pd.Index(levels[0], name=factors[0])
    summary = summary.reindex(index)
    summary['N'] = summary['N'].fillna(0).astype(int)
    summary['极差'] = summary['最大值']-summary['最小值']
    summary = summary.reset_index()
    warnings = ['探索性图形；差异和交互模式未经显著性检验。']
    if coverage < 1:
        warnings.append(f'组合覆盖率 {coverage:.1%}；缺失组合显示 N=0、均值/SD=NA，图中断线。')
    sizes = summary.loc[summary['N'] > 0, 'N']
    if sizes.max() > 10*sizes.min():
        warnings.append('组合样本量比例超过 10，设计极度不平衡；均值按观测加权。')
    if combinations > 100:
        warnings.append('组合较多，建议筛选因子水平以改善图形可读性。')
    return {'kind': 'multi_vari', 'tables': {'组合统计': summary}, 'factors': list(factors), 'levels': levels,
            'observations': frame, 'response_key': response_key, 'coverage': coverage, 'warnings': warnings}


def run_chart(data, measurement, subgroup=None, size=1, statistic='mean', alpha=.05):
    if not np.isfinite(alpha) or not 0 < alpha < .5:
        raise ValueError('显著性水平必须在 0 与 0.5 之间。')
    if statistic not in ('mean', 'median') or int(size) != size or size < 1:
        raise ValueError('请选择均值或中位数，并输入正整数子组大小。')
    values = _numeric(data[measurement])
    frame = pd.DataFrame({'value': values, 'source_index': data.index})
    if subgroup:
        labels = data[subgroup].to_numpy()
        if pd.isna(labels).any():
            raise ValueError('子组 ID 不能为空。')
        # 同一子组必须连续，避免跨时间合并并改变来源顺序。
        blocks = pd.Series(labels).ne(pd.Series(labels).shift()).cumsum()
        if len(pd.unique(labels)) != blocks.nunique():
            raise ValueError('同一子组 ID 必须连续出现。')
        frame['group'] = labels
    else:
        if len(values) % size:
            raise ValueError('观测数必须为子组大小的整数倍。')
        frame['group'] = np.arange(len(values))//int(size)+1
    grouped = frame.groupby('group', sort=False, observed=True)
    table = grouped['value'].agg(['size', statistic]).reset_index()
    table.columns = ['子组', 'N', '统计量']
    y = table['统计量'].to_numpy()
    n = len(y)
    if n < 3:
        raise ValueError('运行图至少需要 3 个观测或子组。')
    center = float(np.median(y))
    below = y <= center
    runs = int(1+np.count_nonzero(below[1:] != below[:-1]))
    m, k = int((~below).sum()), int(below.sum())
    expected = 1+2*m*k/n
    variance = 2*m*k*(2*m*k-n)/(n*n*(n-1))
    direction = np.diff(y) > 0
    updown = int(1+np.count_nonzero(direction[1:] != direction[:-1]))
    expected_ud, variance_ud = (2*n-1)/3, (16*n-29)/90
    rows = []
    # 正态近似的保守适用门槛；计数仍对所有可绘图序列输出。
    reason_m = '两侧至少各 10 点才报告正态近似' if min(m, k) < 10 else ''
    reason_ud = ('至少 10 点才报告正态近似' if n < 10 else
                 '存在相等观测，连续分布零假设下的近似不适用' if len(np.unique(y)) < n else '')
    for name, count, mean, var, reason, low, high in [
        ('围绕中位数', runs, expected, variance, reason_m, '聚集 Clustering', '混合 Mixtures'),
        ('上下运行', updown, expected_ud, variance_ud, reason_ud, '趋势 Trends', '振荡 Oscillation')]:
        z = (count-mean)/np.sqrt(var) if not reason and var > 0 else np.nan
        pl, ph = float(stats.norm.cdf(z)), float(stats.norm.sf(z))
        rows.append([name, count, mean, z, pl, ph, alpha,
                     low if pl < alpha else high if ph < alpha else '未检出' if np.isfinite(z) else '不适用', reason])
    tests = pd.DataFrame(rows, columns=['检验', '运行段数', '期望运行数', 'Z', '左尾 p', '右尾 p', 'alpha', '模式', '适用性'])
    return {'kind': 'run_chart', 'tables': {'运行图数据': table, '随机性检验': tests, '来源观测': frame},
            'center': center, 'warnings': [v for v in (reason_m, reason_ud) if v]}


def pareto_chart(data, category, frequency=None, group=None, threshold=95, max_categories=None):
    """同频保持首次出现顺序；超过累计阈值后合并余项。"""
    if threshold is not None and (not np.isfinite(threshold) or not 1 <= threshold <= 100):
        raise ValueError('合并阈值必须在 1–100% 之间。')
    if max_categories is not None and (int(max_categories) != max_categories or max_categories < 2):
        raise ValueError('显示类别数至少为 2（包含其他）。')
    columns = [category] + ([frequency] if frequency else []) + ([group] if group else [])
    if len(set(columns)) != len(columns):
        raise ValueError('类别、频数和分组必须选择不同列。')
    frame = data[columns].copy().rename(columns={category: '_category', **({frequency: '_frequency'} if frequency else {}),
                                               **({group: '_group'} if group else {})})
    category, frequency, group = '_category', '_frequency' if frequency else None, '_group' if group else None
    if frame.empty or frame.isna().any().any() or frame[category].astype(str).str.strip().eq('').any():
        raise ValueError('类别、频数和分组不能为空；请先处理缺失值。')
    if frequency:
        try:
            counts = []
            for value in frame[frequency]:
                value = (int(value) if isinstance(value, Integral) else
                         Decimal(float(value)) if isinstance(value, Real) else Decimal(str(value)))
                if isinstance(value, Decimal) and (not value.is_finite() or value != value.to_integral_value()):
                    raise ValueError('频数必须为有限非负整数。')
                if value < 0:
                    raise ValueError('频数必须为有限非负整数。')
                counts.append(int(value))
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise ValueError('频数必须为有限非负整数。') from exc
        # object prevents fixed-width overflow before repeated categories are summed.
        frame['_count'] = pd.Series(counts, index=frame.index, dtype=object)
    else:
        frame['_count'] = 1
    tables = {}
    groups = frame.groupby(group, sort=False, observed=True) if group else [('全部', frame)]
    for label, part in groups:
        totals = part.groupby(category, sort=False, observed=True)['_count'].sum().sort_values(ascending=False, kind='stable')
        total = sum(int(v) for v in totals)
        if total == 0:
            raise ValueError('每个分组的总频数必须大于零。')
        keep = len(totals)
        if threshold is not None and threshold < 100:
            numerator, denominator = float(threshold).as_integer_ratio()
            for i, cumulative in enumerate(accumulate(int(v) for v in totals)):
                if cumulative*100*denominator > total*numerator:
                    keep = i+1
                    break
        if max_categories is not None and len(totals) > max_categories:
            keep = min(keep, int(max_categories)-1)
        labels, values = list(totals.index[:keep]), [int(v) for v in totals.iloc[:keep]]
        if keep < len(totals):
            other = '其他（合并）'
            while other in labels:
                other += '*'
            labels.append(other)
            values.append(sum(int(v) for v in totals.iloc[keep:]))
        percentages = [value*100/total for value in values]
        if any(value > 0 and percent == 0 for value, percent in zip(values, percentages)):
            raise ValueError('频数比例超出浮点百分比可表达范围。')
        table = pd.DataFrame({'类别': labels, '频数': pd.Series(values, dtype=object)})
        table['百分比'] = percentages
        table['累计百分比'] = [value*100/total for value in accumulate(values)]
        title = f'分组 {label}'
        while title in tables:
            title += '*'
        tables[title] = table
    return {'kind': 'pareto', 'tables': tables, 'warnings': [], 'grouped': bool(group)}
