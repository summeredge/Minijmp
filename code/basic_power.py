"""Power of basic fixed-design hypothesis tests, with group size as the unit."""
from math import isfinite, sqrt
from numbers import Integral

from scipy import optimize, stats


METHODS = ('t1', 't2', 'z1', 'z2', 'p1', 'p2', 'anova')


def basic_power(method, *, n=None, target=None, effect=None, sigma=1., p0=None, p1=None,
                groups=2, alpha=.05, alternative='two-sided'):
    """Supply two of n, target and effect (proportion tests use p0 and p1).

    n is per group; t2 assumes independent equal-size groups with common variance.
    ANOVA effect is the RMS of the deviations of group means from their grand mean.
    """
    if (method not in METHODS or not 0 < alpha < 1
            or alternative not in ('less', 'greater', 'two-sided')):
        raise ValueError('无效的检验、显著性水平或备择方向。')
    minimum = 2 if method in ('t1','t2','anova') else 1
    if n is not None and (isinstance(n, bool) or not isinstance(n, Integral) or n < minimum):
        raise ValueError(f'每组样本量须为大于等于 {minimum} 的整数。')
    if target is not None and not alpha < target < 1:
        raise ValueError('目标功效必须大于 α 且小于 1。')
    proportion = method in ('p1','p2')
    if proportion:
        if (p0 is None or p1 is None or not 0 < p0 < 1 or not 0 < p1 < 1
                or (n is None) == (target is None) or effect is not None):
            raise ValueError('输入 (0,1) 内的两个比例，并填写样本量或目标功效之一。')
        effect = p1-p0
        pooled = (p0+p1)/2
        v0 = p0*(1-p0) if method == 'p1' else 2*pooled*(1-pooled)
        v1 = p1*(1-p1) if method == 'p1' else p0*(1-p0)+p1*(1-p1)
    elif (sum(v is None for v in (n, target, effect)) != 1 or not isfinite(sigma) or sigma <= 0
          or effect is not None and not isfinite(effect)):
        raise ValueError('请填写样本量、目标功效、效应中的两项及有限的正标准差。')
    if method == 'anova' and (not isinstance(groups, Integral) or groups < 2
                              or alternative != 'two-sided' or effect is not None and effect < 0):
        raise ValueError('ANOVA 至少两组，效应为非负均方根。')
    tail = alpha/2 if alternative == 'two-sided' and method != 'anova' else alpha

    def evaluate(size, delta):
        if delta == 0:
            return alpha
        if method == 'anova':
            df1, df2 = groups-1, groups*(size-1)
            return float(stats.ncf.sf(stats.f.isf(alpha,df1,df2),df1,df2,
                                      size*groups*(delta/sigma)**2))
        if proportion:
            se_ratio = sqrt(v1/v0)
            shift = delta*sqrt(size/v0)
            dist, cutoff = stats.norm(loc=shift,scale=se_ratio), stats.norm.isf(tail)
        else:
            shift = delta/sigma*sqrt(size/(2 if method.endswith('2') else 1))
            if method.startswith('t'):
                df = (size-1)*(2 if method == 't2' else 1)
                dist, cutoff = stats.nct(df,shift), stats.t.isf(tail,df)
            else:
                dist, cutoff = stats.norm(loc=shift), stats.norm.isf(tail)
        lower = dist.cdf(-cutoff) if alternative != 'greater' else 0.
        upper = dist.sf(cutoff) if alternative != 'less' else 0.
        return float(lower+upper)

    if effect is None:
        direction = -1 if alternative == 'less' else 1
        high = sigma
        while evaluate(n, direction*high) < target:
            high *= 2
        effect = direction*optimize.brentq(lambda magnitude: evaluate(n,direction*magnitude)-target, 0, high)
    elif n is None:
        if effect == 0 or alternative == 'less' and effect > 0 or alternative == 'greater' and effect < 0:
            raise ValueError('目标功效需要与备择方向一致的非零效应。')
        n = minimum
        while evaluate(n,effect) < target:
            if n >= 10**8:
                raise ValueError('目标功效超出每组一亿个观测的计算范围。')
            n = min(2*n,10**8)
        lo, hi = minimum, n
        while lo < hi:
            mid = (lo+hi)//2
            if evaluate(mid,effect) >= target:
                hi = mid
            else:
                lo = mid+1
        n = lo
    return dict(n=n, effect=effect, power=evaluate(n,effect))
