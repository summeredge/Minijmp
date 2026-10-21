from stat_table import StatTable
from scipy.stats import norm, binom, hypergeom
from scipy.stats import f as f_dist
#  from functools import lru_cache
import numpy as np
####### Own Modules ########
from binomial import binomial
from chi_sq import chi_square
from blakerCI import binom_blaker_p, binom_blaker_limits


def prop_2sample(n1=None, n2=None, e1=None,
                 e2=None, alpha=0.05, print_out=False,
                 print_port=print):

    if None in [n1, n2, e1, e2] or n1 * n2 == 0:
        return
    n1 = int(n1)
    n2 = int(n2)
    e1 = int(e1)
    e2 = int(e2)
    p1, p2 = e1 / n1, e2 / n2
    p0 = (e1 + e2) / (n1 + n2)
    SE_pooled = (p0 * (1 - p0) * (1 / n1 + 1 / n2))**.5
    SE_sep = (p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2)**.5
    pd = p1 - p2
    CI = (pd + norm.ppf(alpha / 2) * SE_sep,
          pd + norm.ppf(1 - alpha / 2) * SE_sep)
    CI2 = (pd + norm.ppf(alpha) * SE_sep,
           pd + norm.ppf(1 - alpha) * SE_sep)
    pct = "%.2f%%" % (100 - 100 * alpha)
    Zp = pd / SE_pooled
    Zs = pd / SE_sep
    pl = norm.cdf(Zs)
    pu = 1 - pl
    p = 2 * min(pl, pu)

    pl_p = norm.cdf(Zp)
    pu_p = 1 - pl_p
    p_p = 2 * min(pl_p, pu_p)

    rv = hypergeom(n1 + n2, e1 + e2, n1)
    pl_f = rv.cdf(e1)
    pu_f = rv.sf(e1 - 1)

    mode = int((n1 + 1) * (e1 + e2 + 1) / (n1 + n2 + 2))
    observed_probability = rv.pmf(e1)

    if e1 == mode:
        p_f = 1
    elif e1 < mode:
        y = mode
        while rv.pmf(y) >= observed_probability:
            y += 1
        p_f = rv.cdf(e1) + 1 - rv.cdf(y - 1)
    else:
        y = mode
        while rv.pmf(y) >= observed_probability:
            y -= 1
        p_f = 1 - rv.cdf(e1 - 1) + rv.cdf(y)

    if print_out:
        from utilities import gen_table, format_stat
        print = print_port
        print("\n---- 两比例检验 ----")
        print(f'显著性水平 α = {alpha:.3f}；置信水平 = {1-alpha:.1%}')
        print(f'原假设 H0: p1 - p2 = 0；样本比例差 p1 - p2 = {format_stat(pd)}')
        print('备择假设 H1：双侧 p1 - p2 ≠ 0；左尾 p1 - p2 < 0；右尾 p1 - p2 > 0。')
        for title, rows, values in [
            ('样本统计', [['样本', 'N', '事件数', '比例'],
                          ['样本 1', n1, e1, format_stat(p1)],
                          ['样本 2', n2, e2, format_stat(p2)]], [
                ['样本 1', n1, e1, p1],
                ['样本 2', n2, e2, p2]]),
            ('检验结果', [['方法', 'Z', '双侧 p 值', '左尾 p 值', '右尾 p 值'],
                          ['Fisher 精确', '*', format_stat(p_f), format_stat(pl_f), format_stat(pu_f)],
                          ['正态近似（非合并）', format_stat(Zs), format_stat(p), format_stat(pl), format_stat(pu)],
                          ['正态近似（合并）', format_stat(Zp), format_stat(p_p), format_stat(pl_p), format_stat(pu_p)]], [
                ['Fisher 精确', '*', p_f, pl_f, pu_f],
                ['正态近似（非合并）', Zs, p, pl, pu],
                ['正态近似（合并）', Zp, p_p, pl_p, pu_p]]),
            ('总体比例差 p1 - p2 的置信区间（非合并正态近似）', [['区间', '下限', '上限'],
                          ['双侧置信区间', format_stat(CI[0]), format_stat(CI[1])],
                          ['单侧置信下限', format_stat(CI2[0]), '*'],
                          ['单侧置信上限', '*', format_stat(CI2[1])]], [
                ['双侧置信区间', CI[0], CI[1]],
                ['单侧置信下限', CI2[0], '*'],
                ['单侧置信上限', '*', CI2[1]]])]:
            print(title)
            table = gen_table(rows)
            table.align = 'r'
            table.align[table.field_names[0]] = 'l'
            print(StatTable(table, title, table.field_names, values,
                display=[[str(cell) for cell in row] for row in table.rows],
                number_formats=['0' if h in ('N', '事件数') else '0.000' for h in table.field_names]))
        print('p 值保留三位小数，0.000 为舍入显示。')

    return {"p sep": p, "p p1<p2": pl, "p p1>p2": pu,
            "p Fisher": p_f, "p p1<p2 Fisher": pl_f, "p p1>p2 Fisher": pu_f,
            "p Pooled": p_p, "p p1<p2 Pooled": pl_p, "p p1>p2 Pooled": pu_p}


def p_blaker(n, p, k):
    rv = binom(n, p)
    return _p_blaker(n, p, k, rv, rv.pmf(np.arange(n + 1)))


def _p_blaker(n, p, k, rv, probabilities):
    # 全事件边界用稳定尾概率；内部点保留原累计算法。
    psl = rv.cdf(np.arange(n + 1)) if k in (0, n) else np.cumsum(probabilities)
    psr = rv.sf(np.arange(n + 1) - 1) if k in (0, n) else None

    def pt_le_k(n, p, k):
        return psl[k] if k >= 0 else 0

    def pt_ge_k(n, p, i):
        if k in (0, n):
            return psr[i] if i <= n else 0
        return 0 if i > n else 1 - pt_le_k(n, p, i - 1)

    if pt_ge_k(n, p, k) < pt_le_k(n, p, k):
        # 无匹配左尾时取空事件 X <= -1，其概率为 0。
        k_modified = max((i for i in range(n + 1)
                          if pt_le_k(n, p, i) <= pt_ge_k(n, p, k)), default=-1)
        if k_modified == -1:
            return rv.sf(k - 1)
        return pt_ge_k(n, p, k) + pt_le_k(n, p, k_modified)
    elif pt_ge_k(n, p, k) == pt_le_k(n, p, k):
        return 1
    else:
        # 无匹配右尾时取空事件 X >= n+1，其概率为 0。
        k_modified = min((i for i in range(n + 1)
                          if pt_ge_k(n, p, i) <= pt_le_k(n, p, k)), default=n + 1)
        return pt_le_k(n, p, k) + pt_ge_k(n, p, k_modified)


def p_sterne(n, p, k):
    rv = binom(n, p)
    probabilities = rv.pmf(np.arange(n + 1))
    PTK = probabilities[k] if 0 <= k <= n else 0.0
    return _p_sterne(probabilities, PTK)


def _p_sterne(probabilities, PTK):
    return sum(probability for probability in probabilities if probability <= PTK)


def p_likelihood_ratio(n, p0, x):
    p = x / n
    rv = binom(n, p0)

    def LR(i):
        ii = min(i, n - i)
        return (p / p0)**ii * ((1 - p) / (1 - p0))**(n - ii)

    threshold = LR(x)
    probabilities = rv.pmf(np.arange(n + 1))
    return sum(probability for y, probability in enumerate(probabilities)
               if LR(y) >= threshold)


def prop_test_1sample(events=1, N=1, p0=1, print_port=print,
                      print_out=False, alpha=.05):
    p = events / N
    Z = (p - p0) / (p0 * (1 - p0) / N)**.5
    p_norm = (1 - norm.cdf(abs(Z))) * 2
    p_norm_less = norm.cdf(Z)
    b_res = binomial(N, p0, x=events, print_out=False)
    #  print(b_res)
    p_bi = b_res["left_acc_p"]
    p_bi_r = b_res["right_acc_p"]
    #  p_bi_uneq = b_res['not equal p']
    #  rv = binom(N, p0)
    #  x = events
    #  p_bi_uneq = 1 - min(rv.sf(x - 1), rv.cdf(x)) - min(rv.cdf(x - 1), rv.sf(x))
    p_bi_uneq = binom_blaker_p(events, N, p0)

    std = (p * (1 - p) / N)**.5
    CI_l, CI_u = (max(0, p + norm.ppf(alpha / 2) * std),
                  min(1, p + norm.ppf(1 - alpha / 2) * std))
    CI_high = min(1, p + norm.ppf(1 - alpha) * std)
    CI_low = max(0, p + norm.ppf(alpha) * std)

# https://support.minitab.com/en-us/minitab/help-and-how-to/statistics/basic-statistics/how-to/1-proportion/methods-and-formulas/methods-and-formulas/
# Clopper-Pearson exact confidence interval method
    dfn = 2 * events
    dfd = 2 * (N - events + 1)
    F = f_dist.ppf(alpha / 2, dfn, dfd)
    p_exct_l = dfn * F / (dfd + dfn * F)
    F = f_dist.ppf(alpha, dfn, dfd)
    p_exct_low = dfn * F / (dfd + dfn * F)

    b_CI = binom_blaker_limits(events, N, level=1 - alpha, tol=1e-6)

    dfn = 2 * (events + 1)
    dfd = 2 * (N - events)
    F = f_dist.ppf(1 - alpha / 2, dfn, dfd)
    p_exct_u = dfn * F / (dfd + dfn * F)
    F = f_dist.ppf(1 - alpha, dfn, dfd)
    p_exct_high = dfn * F / (dfd + dfn * F)

    p_s = _p_sterne(b_res['pmf'], b_res['px'])
    p_b = _p_blaker(N, p0, events, binom(N, p0), b_res['pmf'])

    if print_out:
        from utilities import gen_table, format_stat
        print = print_port
        print("\n---- 单比例检验 ----")
        print(f'显著性水平 α = {alpha:.3f}；置信水平 = {1-alpha:.1%}')
        print(f'原假设 H0: p = p0；p0 = {format_stat(p0)}')
        print('备择假设 H1：双侧 p ≠ p0；左尾 p < p0；右尾 p > p0。')
        for title, rows, values in [
            ('样本统计', [['样本', 'N', '事件数', '比例'],
                          ['样本', N, events, format_stat(p)]], [
                ['样本', N, events, p]]),
            ('检验结果', [['方法', '双侧 p 值', '左尾 p 值', '右尾 p 值'],
                          ['正态近似', format_stat(p_norm), format_stat(p_norm_less), format_stat(1 - p_norm_less)],
                          ['Sterne 精确', format_stat(p_s), '*', '*'],
                          ['Blaker 精确', format_stat(p_b), '*', '*'],
                          ['调整 Blaker 精确', format_stat(p_bi_uneq), '*', '*'],
                          ['二项精确', '*', format_stat(p_bi), format_stat(p_bi_r)]], [
                ['正态近似', p_norm, p_norm_less, 1 - p_norm_less],
                ['Sterne 精确', p_s, '*', '*'],
                ['Blaker 精确', p_b, '*', '*'],
                ['调整 Blaker 精确', p_bi_uneq, '*', '*'],
                ['二项精确', '*', p_bi, p_bi_r]]),
            ('总体比例的置信区间', [['方法', '双侧下限', '双侧上限', '单侧置信下限', '单侧置信上限'],
                          ['正态近似', format_stat(CI_l), format_stat(CI_u), format_stat(CI_low), format_stat(CI_high)],
                          ['Clopper-Pearson', format_stat(p_exct_l), format_stat(p_exct_u), format_stat(p_exct_low), format_stat(p_exct_high)],
                          ['调整 Blaker', format_stat(b_CI[0]), format_stat(b_CI[1]), '*', '*']], [
                ['正态近似', CI_l, CI_u, CI_low, CI_high],
                ['Clopper-Pearson', p_exct_l, p_exct_u, p_exct_low, p_exct_high],
                ['调整 Blaker', b_CI[0], b_CI[1], '*', '*']])]:
            print(title)
            table = gen_table(rows)
            table.align = 'r'
            table.align[table.field_names[0]] = 'l'
            print(StatTable(table, title, table.field_names, values,
                display=[[str(cell) for cell in row] for row in table.rows],
                number_formats=['0' if h in ('N', '事件数') else '0.000' for h in table.field_names]))
        print("调整 Blaker 行报告双侧精确 p 值；单侧精确检验采用二项分布尾概率，单侧精确置信限采用 Clopper-Pearson 方法。")
        print('p 值保留三位小数，0.000 为舍入显示。')
        #  print("\nJMP Test Probabilities in Distributions")

    chi_res = chi_square([[events, N - events],
                          [10000 * N * p0, 10000 * N * (1 - p0)]],
                         print_out=False, print_port=print_port)
    if print_out:
        print('检验结果（JMP 列联表；备择假设 H1: p ≠ p0）')
        values = [['Pearson', chi_res['chi sq Pearson'], chi_res['df'], chi_res['p Pearson']],
                  ['似然比', chi_res['chi sq LR'], chi_res['df'], chi_res['p LR']]]
        table = gen_table([['方法', '卡方统计量', '自由度', 'p 值'],
                           ['Pearson', format_stat(chi_res['chi sq Pearson']), chi_res['df'], format_stat(chi_res['p Pearson'])],
                           ['似然比', format_stat(chi_res['chi sq LR']), chi_res['df'], format_stat(chi_res['p LR'])]])
        table.align = 'r'
        table.align[table.field_names[0]] = 'l'
        print(StatTable(table, '检验结果（JMP 列联表；备择假设 H1: p ≠ p0）', table.field_names, values,
            display=[[str(cell) for cell in row] for row in table.rows]))

    return {"p norm": p_norm, "p Binomial": p_bi,
            "Z p less": p_norm_less,
            "CI norm": {"CI l": CI_l, "CI u": CI_u,
                        "CI high": CI_high, "CI low": CI_low},
            "p Sterne": p_s, "p Blaker": p_b,
            "CI exact": {"CI l": p_exct_l, "CI u": p_exct_u,
                         "CI high": p_exct_high, "CI low": p_exct_low},
            "JMP chi sq": chi_res, 'Blaker p': p_bi_uneq, 'Blaker CI': b_CI
            }


if __name__ == "__main__":
    print(prop_test_1sample(9, 250, .073, print_out=True))
    #  prop_2sample(n1=250, e1=9, e2=9, n2=350, print_out=True)
    #  prop_2sample(n2=250, e1=9, e2=9, n1=350, print_out=True)
    #  print(p_blaker(250, .073, 9), p_sterne(250, .073, 9))
    #  print(p_likelihood_ratio(250, .073, 9))
    #  print(p_likelihood_ratio(50, .35, 10))
    #  print(p_sterne(50, .35, 10))
