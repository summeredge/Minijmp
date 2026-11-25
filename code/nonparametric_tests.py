"""Rank, sign and sequence tests used by the nonparametric analysis dialogs."""

from math import comb, prod

import numpy as np
from scipy import stats


def _sample(values):
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if not len(values):
        raise ValueError("每组至少需要一个有限观测值。")
    return values


def _central_interval(values, cdf, alpha):
    """Invert a symmetric discrete null distribution using equal tails."""
    ordered = np.sort(values)
    low, high = 0, len(ordered) // 2
    while low < high:
        middle = (low + high + 1) // 2
        if cdf(middle - 1) <= alpha / 2:
            low = middle
        else:
            high = middle - 1
    if low == 0:
        return -np.inf, np.inf, 1.0
    return ordered[low - 1], ordered[-low], 1 - 2 * cdf(low - 1)


def sign_test(values, target=0, alternative="two-sided", alpha=.05):
    x = _sample(values)
    positive = int(np.count_nonzero(x > target))
    negative = int(np.count_nonzero(x < target))
    n = positive + negative
    return dict(
        n=len(x), positive=positive, negative=negative, zero=len(x) - n,
        estimate=np.median(x), statistic=positive,
        pvalue=stats.binomtest(positive, n, alternative=alternative).pvalue if n else 1.,
        interval=_central_interval(x, lambda k: stats.binom.cdf(k, len(x), .5), alpha),
        method="精确二项；零差从检验中排除",
    )


def signed_rank_test(values, target=0, alternative="two-sided", alpha=.05):
    x = _sample(values)
    d = x[x != target] - target
    ranks = stats.rankdata(abs(d))
    positive = ranks[d > 0].sum()
    negative = ranks[d < 0].sum()
    exact = len(d) <= 50 and len(np.unique(abs(d))) == len(d)
    method = "精确符号秩" if exact else "正态近似（并列修正及连续性修正）"
    statistic = min(positive, negative) if alternative == "two-sided" else positive
    pvalue = 1.
    if len(d):
        pvalue = stats.wilcoxon(
            d, alternative=alternative, method="exact" if exact else "asymptotic",
            correction=not exact,
        ).pvalue
    else:
        method = "全为零差"
    n = len(x)
    if n * (n + 1) // 2 > 2_000_000:
        raise ValueError("Walsh 平均值超过 200 万个，请缩小样本。")
    row, col = np.triu_indices(n)
    walsh = x[row] / 2 + x[col] / 2
    interval = None
    if len(np.unique(x)) == n:
        if n <= 50:
            counts = np.zeros(len(walsh) + 1, dtype=np.int64)
            counts[0] = 1
            for rank in range(1, n + 1):
                counts[rank:] += counts[:-rank].copy()
            cdf = np.cumsum(counts) / 2**n
            interval = _central_interval(walsh, lambda k: cdf[k], alpha)
        else:
            sd = np.sqrt(n * (n + 1) * (2 * n + 1) / 24)
            interval = _central_interval(
                walsh, lambda k: stats.norm.cdf((k + .5 - len(walsh) / 2) / sd), alpha
            )
    return dict(n=n, positive=positive, negative=negative, zero=n - len(d),
                statistic=statistic, pvalue=pvalue, estimate=np.median(walsh),
                interval=interval, method=method)


def mann_whitney_test(first, second, alternative="two-sided", alpha=.05):
    x, y = _sample(first), _sample(second)
    n, m = len(x), len(y)
    if n * m > 2_000_000:
        raise ValueError("配对差值超过 200 万个，请缩小样本。")
    pooled = np.concatenate((x, y))
    untied = len(np.unique(pooled)) == n + m
    exact = untied and min(n, m) <= 8
    result = stats.mannwhitneyu(x, y, alternative=alternative,
                                method="exact" if exact else "asymptotic")
    differences = (x[:, None] - y).ravel()
    interval = None
    if untied:
        if exact and n * m <= 10_000:
            # Under H0, ranks are uniformly sampled without replacement.
            small = min(n, m)
            counts = [dict() for _ in range(small + 1)]
            counts[0][0] = 1
            for rank in range(1, n + m + 1):
                for size in range(min(rank, small), 0, -1):
                    for total, count in counts[size - 1].items():
                        key = total + rank
                        counts[size][key] = counts[size].get(key, 0) + count
            offset = small * (small + 1) // 2
            cdf = np.cumsum([counts[small][k + offset] / comb(n + m, small)
                             for k in range(n * m + 1)])
            interval = _central_interval(differences, lambda k: cdf[k], alpha)
        else:
            sd = np.sqrt(n * m * (n + m + 1) / 12)
            interval = _central_interval(
                differences, lambda k: stats.norm.cdf((k + .5 - n * m / 2) / sd), alpha
            )
    return dict(n=(n, m), statistic=result.statistic, pvalue=result.pvalue,
                estimate=np.median(differences), interval=interval,
                method="精确 U" if exact else "正态近似（并列修正及连续性修正）")


def grouped_rank_test(samples, *, mood=False, alpha=.05):
    groups = [_sample(values) for values in samples]
    if len(groups) < 2:
        raise ValueError("需要至少两个有效组。")
    pooled = np.concatenate(groups)
    median = np.median(pooled)
    if mood:
        statistic, pvalue, _, counts = stats.median_test(
            *groups, ties="below", correction=False
        )
        rows = [
            (len(x), np.median(x), int(above), int(below),
             _central_interval(x, lambda k: stats.binom.cdf(k, len(x), .5), alpha))
            for x, above, below in zip(groups, *counts)
        ]
        return dict(statistic=statistic, pvalue=pvalue, df=len(groups)-1,
                    pooled_median=median, groups=rows,
                    method="Pearson 卡方（等于合并中位数计入下侧，无连续性修正）")
    result = stats.kruskal(*groups)
    ranks = np.split(stats.rankdata(pooled), np.cumsum([len(x) for x in groups[:-1]]))
    return dict(statistic=result.statistic, pvalue=result.pvalue, df=len(groups)-1,
                groups=[(len(x), np.median(x), r.mean()) for x, r in zip(groups, ranks)],
                method="H 统计量（并列修正），卡方近似")


def friedman_test(frame, response, treatment, block):
    data = frame[[response, treatment, block]].dropna(how="all")
    if data.isna().any().any():
        raise ValueError("Friedman 检验需要完整观测、处理及区组。")
    if data.duplicated([block, treatment]).any():
        raise ValueError("每个区组内每种处理必须恰有一条观测。")
    wide = data.pivot(index=block, columns=treatment, values=response)
    matrix = wide.to_numpy(dtype=float)
    n, k = matrix.shape
    if n < 2 or k < 3 or not np.isfinite(matrix).all():
        raise ValueError("需要至少两个完整区组和三种处理，响应必须有限。")
    ranks = stats.rankdata(matrix, axis=1)
    if np.all(ranks == (k + 1) / 2):
        raise ValueError("各区组内响应全部并列，无法计算 Friedman 统计量。")
    result = stats.friedmanchisquare(*matrix.T)
    return dict(statistic=result.statistic, pvalue=result.pvalue, df=k-1, blocks=n,
                groups=list(zip(wide.columns, ranks.sum(axis=0), ranks.mean(axis=0))),
                method="区组内平均秩（并列修正），卡方近似")


def runs_test(values, threshold=None):
    x = _sample(values)
    threshold = np.median(x) if threshold is None else threshold
    sides = x[x != threshold] > threshold
    above = int(sides.sum())
    below = len(sides) - above
    if min(above, below) == 0:
        raise ValueError("阈值两侧均须有观测值。")
    runs = 1 + int(np.count_nonzero(sides[1:] != sides[:-1]))
    if len(sides) <= 100 or min(above, below) <= 10:
        def arrangements(parts, sizes):
            return prod(comb(n - 1, k - 1) if 1 <= k <= n else 0
                        for n, k in zip(sizes, parts))

        weights = []
        for count in range(2, min(2 * min(above, below) + 1, len(sides)) + 1):
            first = (count + 1) // 2
            second = count // 2
            weights.append(arrangements((first, second), (above, below))
                           + arrangements((second, first), (above, below)))
        denominator = comb(len(sides), above)
        pvalue = min(1., 2 * min(sum(weights[:runs-1]), sum(weights[runs-2:])) / denominator)
        method = "精确条件分布（双倍较小尾概率）"
    else:
        n = len(sides)
        pairs = 2 * above * below
        mean = 1 + pairs / n
        sd = np.sqrt(pairs * (pairs - n) / (n * n * (n - 1)))
        pvalue = 2 * stats.norm.sf(max(0, abs(runs - mean) - .5) / sd)
        method = "正态近似（连续性修正）"
    return dict(statistic=runs, pvalue=pvalue, above=above, below=below,
                omitted_ties=len(x)-len(sides), threshold=threshold, method=method)
