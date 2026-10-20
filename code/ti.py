    
import numpy as np
from scipy import integrate
from scipy.stats import chi2, ncx2, norm, nct
from statistics import mean, stdev
from utilities import gen_table, format_stat


def ti_norm(data=None, alpha=0.05, P=0.9,
            sample_mean=None, sample_std=None, sample_n=None,
            print_out=False, print_port=print):
    def equation(k):
        # Source:
        # https://support.minitab.com/en-us/minitab/help-and-how-to/quality-and-process-improvement/quality-tools/how-to/tolerance-intervals-normal-distribution/methods-and-formulas/methods-and-formulas/
        def f(x):
            dn = (n - 1) * ncx2.ppf(P, 1, x * x / n)
            return 2 * (1 - chi2.cdf(dn / k / k, n - 1)) * norm.pdf(x)
        result, error = integrate.quad(f, 0, np.inf)
        return result

    def solve(alpha=0.05):
        l, r = 0, 10000
        thd = 0.0001
        while abs(r - l) > thd:
            m = (l + r) / 2
            res = equation(m) - 1 + alpha
            if res > 0:
                r = m
            else:
                l = m
        return l

    if None in [sample_mean, sample_n, sample_std]:
        try:
            n = len(data)
            u = mean(data)
            s = stdev(data)
        except BaseException:
            return
    else:
        n = sample_n
        s = sample_std
        u = sample_mean

    delta = norm.ppf(P) * (n**.5)
    k = nct.ppf(1 - alpha, n - 1, delta) / (n**.5)
    ul = u + k * s
    ll = u - k * s

    if print_out:
        k_one = k
    k = solve(alpha=alpha)
    ti = (u - k * s, u + k * s)

    if print_out:
        print = print_port
        print("\n---- 统计容差区间（正态方法） ----")
        print("数据来源：" + ("原始样本" if None in [sample_mean, sample_n, sample_std] else "汇总数据"))
        table = gen_table([['N', '样本均值', '样本标准差'],
                           [n, format_stat(u), format_stat(s)]])
        table.align = 'r'
        print(str(table))
        pct, confidence = '%.1f%%' % (100 * P), '%.1f%%' % (100 * (1 - alpha))
        table = gen_table([
            ['方法', '限类型', '总体覆盖比例', '置信水平', '下容差限', '上容差限', '容差因子 k'],
            ['正态', '双侧区间', pct, confidence, format_stat(ti[0]), format_stat(ti[1]), format_stat(k)],
            ['正态', '单侧下限', pct, confidence, format_stat(ll), '*', format_stat(k_one)],
            ['正态', '单侧上限', pct, confidence, '*', format_stat(ul), format_stat(k_one)]])
        for col in table.field_names[2:]:
            table.align[col] = 'r'
        print(str(table))
        print("假设总体服从正态分布；限值单位与输入测量值一致，k 无量纲，* 表示不适用。")
        print("总体覆盖比例为至少需覆盖的个体比例，置信水平描述重复抽样时容差限达到该覆盖要求的长期比例。")
        print("单侧下限覆盖其上方总体，单侧上限覆盖其下方总体；两行是分别计算的单侧限，不能拼成双侧区间。")
        print("容差区间针对总体个体的覆盖，不是总体参数的置信区间，也不是未来观测值的预测区间。")

    return {"TI": ti, "Upper Bound": ul, "Lower Bound": ll}


if __name__ == "__main__":
    ti_norm(sample_n=10, sample_std=3.052, sample_mean=5.95, print_out=True)
