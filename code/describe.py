import statistics as stat
import numpy as np
from stat_table import StatTable
########### Own Modules ########
try:
    from .utilities import quantiles, is_number, gen_table, format_stat
except BaseException:
    from utilities import quantiles, is_number, gen_table, format_stat


STAT_LABELS = {
    'N': 'N', 'Mean': '均值', 'SE of Mean': '均值标准误',
    'Standard Deviation': '标准差', 'Minimum': '最小值',
    'First Quartile': 'Q1', 'Median': '中位数', 'Third Quartile': 'Q3',
    'Maximum': '最大值', 'Variance': '方差', 'Coefficient of Variation': '变异系数 (%)',
    'Sum': '总和', 'Range': '极差', 'Interquartile Range': '四分位距',
    'Skewness': '偏度', 'Kurtosis': '峰度', 'Mode': '众数', 'N of Mode': '众数频数',
}
CORE_STATS = ['N', 'Mean', 'SE of Mean', 'Standard Deviation', 'Minimum',
              'First Quartile', 'Median', 'Third Quartile', 'Maximum']


def print_descriptive(results, print_port=print, missing=None, selected=None):
    """函数及两种弹窗共用同一套报告列，保留选中的补充统计量。"""
    selected = list(STAT_LABELS) if selected is None else selected
    print_port('\n---- 描述性统计 ----')
    for names, title in [(CORE_STATS, None),
                         ([key for key in STAT_LABELS if key not in CORE_STATS], '补充统计')]:
        names = [key for key in names if key in selected]
        show_missing = title is None and missing is not None and 'N' in names
        if not names and not show_missing:
            continue
        if title:
            print_port(title)
        headers = ['变量'] + [STAT_LABELS[key] for key in names]
        if show_missing:
            headers.insert(1 + ('N' in names), 'N*')
        rows = [headers]
        for label, values in results.items():
            row = [str(label)] + [str(values[key]) if key in ('N', 'N of Mode')
                                 else format_stat(values[key]) for key in names]
            if show_missing:
                row.insert(1 + ('N' in names), missing[label])
            rows.append(row)
        table = gen_table(rows)
        table.align = 'r'
        table.align['变量'] = 'l'
        values = []
        for label, stats in results.items():
            row = [str(label)] + [stats[key] for key in names]
            if show_missing:
                row.insert(1 + ('N' in names), missing[label])
            values.append(row)
        print_port(StatTable(str(table), title or '描述性统计', headers, values))
    if missing is not None:
        print_port('N 为有效观测数；N* 为按当前清洗规则排除的缺失或无效观测数。')


def print_percentiles(percentiles, values, print_port=print):
    print_port('百分位数')
    table = gen_table([['百分位数', '数值']] + [
        ['%.2f%%' % pct, format_stat(value)] for pct, value in zip(percentiles, values)])
    table.align = 'r'
    print_port(StatTable(str(table), '百分位数', ['百分位数', '数值'],
                         [['%.2f%%' % pct, value] for pct, value in zip(percentiles, values)]))


def describe(data, print_port=print,
             print_out=False, percentiles=[100, 99.5, 97.5, 90, 75, 50,
                                           25, 10, 2.5, 0.5, 0]):
    input_count = len(data) if hasattr(data, '__len__') else None
    data = [float(i) for i in data if is_number(i)]
    N = len(data)
    if N < 2:
        return
    mean = stat.mean(data)
    R = max(data) - min(data)
    mode = stat.mode(data)
    N_mode = len([i for i in data if i == mode])
    median = stat.median(data)
    qnt = quantiles(data, percentiles=[25, 75])
    IQR = max(qnt) - min(qnt)
    qnt2 = quantiles(data, percentiles=percentiles)

    std = stat.stdev(data)
    SEM = std / N**.5
    var = stat.variance(data)
    coefvar = 100 * std / mean if mean != 0 else np.nan
    try:
        kurt = N * (N + 1) / (N - 1) / (N - 2) / (N - 3) * sum(
            ((i - mean) / std)**4 for i in data
        ) - 3 * (N - 1)**2 / (N - 2) / (N - 3)
    except BaseException:
        kurt = np.nan
    try:
        skew = N / (N - 1) / (N - 2) * sum(((i - mean) / std)**3
                                           for i in data)
    except BaseException:
        skew = np.nan

    result = {
        "N": N,
        "mean": mean,
        "stdev": std,
        "SEM": SEM,
        "var": var,
        "coefvar": coefvar,
        "sum": sum(data),
        "min": min(data),
        "max": max(data),
        "Q1": qnt[0],
        "Q3": qnt[1],
        "median": median,
        "range": R,
        "IQR": IQR,
        "mode": mode,
        "n mode": N_mode,
        "skew": skew,
        "kurt": kurt,
        "quantiles": qnt2,
        "Mean": mean,
        "Standard Deviation": std,
        "Variance": var,
        "Maximum": max(data),
        "Median": median,
        "First Quartile": qnt[0],
        "Third Quartile": qnt[1],
        "SE of Mean": SEM,
        "Coefficient of Variation": coefvar,
        "Sum": sum(data),
        "Minimum": min(data),
        "Range": R,
        "Skewness": skew,
        "Kurtosis": kurt,
        "Mode": mode,
        "N of Mode": N_mode,
        "Interquartile Range": IQR}
    if print_out:
        missing = None if input_count is None else {'数据': input_count - N}
        print_descriptive({'数据': result}, print_port=print_port, missing=missing)
        print_percentiles(percentiles, qnt2, print_port=print_port)
    return result


if __name__ == "__main__":
    describe([1, 1, 2, 2, 3, 4, 1], print_out=True)
    describe([1, 1, 2, 3, 3, 3, 3, 4, 1, 1, 1, 1, 1, 1], print_out=True)
    from scipy.stats import skew
    print(skew([1, 1, 2, 3, 3, 3, 3, 4, 1, 1, 1, 1, 1, 1]))
