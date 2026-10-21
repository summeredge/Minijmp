from stat_table import StatTable
import statistics as stat
import numpy as np
from scipy.stats import chi2, norm, kurtosis
from scipy.stats import f as f_dist
from scipy.special import xlogy
from math import log as ln
from prettytable import PrettyTable as PT
########### Own Modules ############
#  from utilities import mean_std_CIs
try:
    from .bonett import var_1sample as bonett_var_1sample
except BaseException:
    from bonett import var_1sample as bonett_var_1sample


def chi2_test_stdev(data_list, s0, print_out=False, alpha=0.05,
                    print_port=print):
    df = len(data_list) - 1
    S = stat.variance(data_list) * df
    stdev = stat.stdev(data_list)
    chi_sq = S / s0 / s0
    p = 1 - chi2.cdf(chi_sq, df)

    chi2_low0025 = chi2.ppf(alpha / 2, df)
    chi2_high0975 = chi2.ppf(1 - alpha / 2, df)
    chi2_low005 = chi2.ppf(alpha, df)
    stdev_range_low = (chi2_low0025 * s0 * s0 / df)**.5
    stdev_range_high = (chi2_high0975 * s0 * s0 / df)**.5

    std_range_from_S = ((S / chi2_high0975)**.5, (S / chi2_low0025)**.5)

    std_from_S_high95 = (S / chi2_low005)**.5

    pct = "%.2f%%" % (100 - alpha * 100)

    if print_out:
        from utilities import gen_table, format_stat
        print = print_port
        print("\n---- 单样本标准差卡方检验 ----")
        print(f'显著性水平 α = {alpha:.3f}；置信水平 = {1-alpha:.1%}')
        print(f'原假设 H0: σ = σ0；σ0 = {format_stat(s0)}；假定总体服从正态分布。')
        for title, rows, values in [
            ('样本统计', [['样本', 'N', '标准差'], ['样本', df + 1, format_stat(stdev)]], [
                ['样本', df + 1, stdev]]),
            ('检验结果', [['检验', '备择假设 H1', '卡方统计量', '自由度', 'p 值'],
                          ['右尾', 'sigma > sigma0', format_stat(chi_sq), df, format_stat(p)]], [
                ['右尾', 'sigma > sigma0', chi_sq, df, p]]),
            ('总体标准差的置信区间', [['区间', '下限', '上限'],
                          ['双侧置信区间', format_stat(std_range_from_S[0]), format_stat(std_range_from_S[1])],
                          ['单侧置信上限', '*', format_stat(std_from_S_high95)]], [
                ['双侧置信区间', std_range_from_S[0], std_range_from_S[1]],
                ['单侧置信上限', '*', std_from_S_high95]]),
            ('抽样分布参考（不是总体参数的置信区间）', [['项目', '下限', '上限'],
                          ['卡方分位点 (alpha/2, 1-alpha/2)', format_stat(chi2_low0025), format_stat(chi2_high0975)],
                          ['样本标准差的抽样分布中央区间', format_stat(stdev_range_low), format_stat(stdev_range_high)]], [
                ['卡方分位点 (alpha/2, 1-alpha/2)', chi2_low0025, chi2_high0975],
                ['样本标准差的抽样分布中央区间', stdev_range_low, stdev_range_high]])]:
            print(title)
            table = gen_table(rows)
            table.align = 'r'
            table.align[table.field_names[0]] = 'l'
            print(StatTable(table, title, table.field_names, values,
                display=[[str(cell) for cell in row] for row in table.rows]))
        print('p 值保留三位小数，0.000 为舍入显示。')

    return {
        "p": p,
        "chi_sq": chi_sq,
        "stdev": stdev,
        "df": df,
        "95_chi2_range": (
            chi2_low0025,
            chi2_high0975),
        "95_range_from_P": (
            stdev_range_low,
            stdev_range_high),
        "n": df + 1,
        "95_range_from_S": std_range_from_S,
        "std_from_S_high95": std_from_S_high95}


def several_tests_stdev_2sided(l1, l2, print_out=True):
    var1 = stat.variance(l1)
    var2 = stat.variance(l2)
    u1 = stat.mean(l1)
    u2 = stat.mean(l2)
    s1 = stat.stdev(l1)
    s2 = stat.stdev(l2)
    n1 = len(l1)
    n2 = len(l2)
    # This replicates Minitab result
    k1 = kurtosis(l1, fisher=True, bias=False)
    k2 = kurtosis(l2, fisher=True, bias=False)
    res = {
        "u1": u1,
        "u2": u2,
        "s1": s1,
        "s2": s2,
        "n1": n1,
        "n2": n2,
        "k1": k1,
        "k2": k2}
#     print(k1,k2)

    f = var1 / var2
    dfn, dfd = n1 - 1, n2 - 1
    p = (1 - f_dist.cdf(f, dfn, dfd)) * 2
    if p > 1:
        f = var2 / var1
        dfn, dfd = n2 - 1, n1 - 1
        p = (1 - f_dist.cdf(f, dfn, dfd)) * 2
    res["F"] = {"f": f, "p": p, "dfn": dfn, "dfd": dfd}

    #  kp = ((n1 - 1) * k1 + (n2 - 1) * k2) / (n1 + n2 - 2)
    #  SE = (kp / 2 / (n1 - 1) + kp / 2 / (n2 - 1))**.5
    z = (ln(var1) - ln(var2)) / (2 / n1 + 2 / n2)**.5
    p2 = 2 * (1 - norm.cdf(abs(z)))
    df = n1 - 1
    res["Bonett"] = {"z": z, "p": p2, "df": df}

    if print_out:
        print("u1 = %.2f\ts1 = %.2f\tn1 = %d" % (u1, s1, n1))
        print("u2 = %.2f\ts2 = %.2f\tn2 = %d" % (u2, s2, n2))
        print("\nTwo-sided F test: (Matches both, but senstive to normality.)")
        print("f ratio = %.2f\tdfn = %d\tdfd = %d" % (f, dfn, dfd))
        print("Two-sided test p=%.2f" % res["F"]["p"])
        print("\nBonett's test (doesn't match Minitab)")
        print("z = %.2f\tp=%.2f" % (z, res["Bonett"]["p"]))

    return res


#####################
#
single_pop_var_test = chi2_test_stdev

# 从一个population取样，测试这个population
# 的波动等于某一波动的可能性
###########################
#
#

# Pearson Chi square
# Expected frequency = (Row total * Column total) / Grand total
# Calculate the chi-square statistic using the formula:
# χ² = Σ [(O - E)² / E]
# Where O is the observed frequency and E is the expected frequency for each cell.
# Determine the degrees of freedom (df). For a contingency table, df =
# (rows - 1) * (columns - 1).


def chi_square(data, print_out=True, print_port=print,
               print_table=False, rKeys=None, cKeys=None):
    a = np.array(data)  # a stores the observed values
    col_sum = np.sum(a, axis=0)
    row_sum = np.sum(a, axis=1)
    ttl_sum = np.sum(col_sum)
    #  print = print_port
    #  print(str(data))
    #  print(str(rKeys) + " rKeys")
    #  print(str(cKeys))
    chi_sq = 0
    e = np.zeros(a.shape)
    try:
        for y in range(a.shape[0]):
            for x in range(a.shape[1]):
                expected = row_sum[y] * col_sum[x] / ttl_sum
                chi_sq += (a[y][x] - expected)**2 / expected
                e[y][x] = expected

        df = (a.shape[0] - 1) * (a.shape[1] - 1)

        p = 1 - chi2.cdf(chi_sq, df)
    except BaseException:
        chi_sq = p = np.nan
    LR = 0
    try:
        for y in range(a.shape[0]):
            for x in range(a.shape[1]):
                expected = row_sum[y] * col_sum[x] / ttl_sum
                LR += 2 * xlogy(a[y][x], a[y][x] / expected)
                e[y][x] = expected

        p_LR = 1 - chi2.cdf(LR, df)
    except BaseException:
        p_LR = LR = np.nan

    if print_out:
        from utilities import gen_table, format_stat
        print = print_port
        print("\n---- 卡方独立性检验 ----")
        print('原假设 H0：行变量与列变量相互独立。')
        print('备择假设 H1：行变量与列变量不独立。')
        print('方法：Pearson 卡方与似然比检验；沿用未作连续性校正的统计量。')
        if print_table and cKeys is not None and rKeys is not None:
            print('列联表（观测频数 / 期望频数）')
            rows = [['行 / 列'] + list(cKeys) + ['合计']]
            for y, rkey in enumerate(rKeys):
                rows.append([rkey] + [f'{str(a[y][x]).removesuffix(".0")} / {format_stat(e[y][x])}'
                                      for x in range(len(cKeys))] + [str(row_sum[y])])
            rows.append(['合计'] + [str(value) for value in col_sum] + [str(ttl_sum)])
            table = gen_table(rows)
            table.align = 'r'
            table.align[table.field_names[0]] = 'l'
            # 拆开观测/期望单元格，Excel 保留两个数值，TXT 仍使用原合并表。
            headers = ['行 / 列'] + [f'{key}（{kind}）' for key in cKeys
                                      for kind in ('观测', '期望')] + ['合计']
            values = [[rkey] + [value for x in range(len(cKeys))
                               for value in (a[y][x], e[y][x])] + [row_sum[y]]
                      for y, rkey in enumerate(rKeys)]
            values.append(['合计'] + [value for total in col_sum for value in (total, '*')]
                          + [ttl_sum])
            display = [[str(rkey)] + [text for x in range(len(cKeys))
                        for text in (str(a[y][x]).removesuffix('.0'), format_stat(e[y][x]))]
                       + [str(row_sum[y])] for y, rkey in enumerate(rKeys)]
            display.append(['合计'] + [text for total in col_sum for text in (str(total), '*')]
                           + [str(ttl_sum)])
            print(StatTable(table, '列联表（观测频数 / 期望频数）', headers, values,
                display=display,
                number_formats=['General'] + ['General', '0.000'] * len(cKeys) + ['General']))

        print('检验结果')
        values = [['Pearson', chi_sq, df, p],
                  ['似然比', LR, df, p_LR]]
        table = gen_table([['方法', '卡方统计量', '自由度', 'p 值'],
                           ['Pearson', format_stat(chi_sq), df, format_stat(p)],
                           ['似然比', format_stat(LR), df, format_stat(p_LR)]])
        table.align = 'r'
        table.align[table.field_names[0]] = 'l'
        print(StatTable(table, '检验结果', table.field_names, values,
            display=[[str(cell) for cell in row] for row in table.rows]))
        if np.all(np.isfinite(e)):
            small = np.count_nonzero(e < 5)
            if small:
                print(f'注意：{small}/{e.size} 个单元格的期望频数小于 5，卡方近似可能不可靠。')
        print('p 值是在 H0 及检验模型成立时，得到当前或更极端统计量的概率，不是 H0 成立的概率。')
        print('p 值保留三位小数，0.000 为舍入显示，不代表概率严格为零；* 表示不可用。')

    return {"p Pearson": p, "chi sq Pearson": chi_sq, "df": df,
            "p LR": p_LR, "chi sq LR": LR}

# Key differences and considerations:
#         Robustness:
#             The Brown-Forsythe and O'Brien tests are generally considered the most robust,
#         followed by Levene's test, with the F-test being the least robust to violations of normality.
#
#         Power:
#             Under normal distributions, the F-test is most powerful, followed by Levene's test,
# then Brown-Forsythe. However, for non-normal distributions, the robust
# tests often outperform the F-test.

#         Underlying distribution:
#             If the data is known to follow a specific distribution, this can guide
#         the choice of test. For example, the Brown-Forsythe test performs well for skewed distributions,
# while Levene's test with squared deviations is better for symmetric,
# moderate-tailed distributions.

#         Sample size:
#             For small samples, the O'Brien and Ramsey conditional tests have shown good Type I
#         error control across different distribution shapes


def multi_pop_var_test(data, labels, print_out=False, print_port=print,
                       alpha=0.05):
    # data in a list of lists
    ns = [len(group) for group in data]
    means = [stat.mean(group) for group in data]
    variances = [stat.variance(group) for group in data]
    medians = [stat.median(group) for group in data]

    def one_way_anova(data):
        ns = [len(l) for l in data]
        k, N = len(data), sum(ns)
        means = [stat.mean(l) for l in data]
        mean = np.concatenate(data).mean()
        SSB = sum([n * (x - mean)**2 for n, x in zip(ns, means)])
        SSW = sum(sum((v - mean)**2 for v in group)
                  for group, mean in zip(data, means))
        F = (SSB / (k - 1)) / (SSW / (N - k))
        p = 1 - f_dist.cdf(F, k - 1, N - k)
        return {"F": F, "p": p}

    def OBrien(data):
        #      uij = [nj(nj - 1.5)(xij - Mj)^2 - 0.5SSj] / [(nj - 1)(nj - 2)]
        #         Where:
        #         uij is the transformed score
        #         nj is the number of observations in group j
        #         xij is the original score
        #         Mj is the mean of group j
        #         SSj is the sum of squared deviations from the mean for group j
        #     Do one way ANOVA to uij
        Zij = [[((n - 1.5) * n * (v - mean)**2 -
                 variance * (n - 1) / 2) / (n - 1) / (n - 2)
                for v in group]
               for group, n, mean, variance in zip(data, ns, means, variances)]
        return one_way_anova(Zij)

    def Levene(data):
        #    Calculate the absolute deviation from the group mean for each data point:
        #   Zij=|X_ij - X̄_i|, where X_ij is the jth observation in the ith group,
        # and X̄_i is the mean of the ith group.
        Zij = [[abs(v - mean) for v in group] for group, mean in zip(data, means)]
        return one_way_anova(Zij)

    def Brown_Forsythe(data):
        #   Zij=|X_ij - median of the group |
        Zij = [[abs(v - median) for v in group] for group, median in zip(data, medians)]
        return one_way_anova(Zij)

    res = {"OBrien": OBrien(data)}
    res["Levene"] = Levene(data)
    res["Brown_Forsythe"] = Brown_Forsythe(data)

    if print_out:
        print = print_port
        print("\n---- Multi Sample Standard Deviation Test ----")
        t = PT()
        pct = "%.2f%%" % (100 - 100 * alpha)
        t.field_names = ["Sample", "N", "SD", pct + " CI of std", "MAD to Mean", "MAD to Median"]
        values, display = [], []
        for i in range(len(data)):
            chi2_r = chi2_test_stdev(
                data[i],
                1,
                alpha=alpha,
                print_out=False,
                print_port=print_port)
            sr = chi2_r["95_range_from_S"]
            #  chi2_r = chi2_test_stdev(data[i], 1,
            #                           alpha=alpha / len(data),
            #                           print_out=False)
            #  sr2 = chi2_r["95_range_from_S"]
            mean = means[i]
            median = medians[i]
            sd = stat.stdev(data[i])
            mad = sum(abs(x - mean) for x in data[i]) / len(data[i])
            mad2 = sum(abs(x - median) for x in data[i]) / len(data[i])
            values.append([labels[i], len(data[i]), sd,
                           sr[0], sr[1], mad, mad2])
            display.append([str(labels[i]), str(len(data[i])), '%.3f' % sd,
                            '%.3f' % sr[0], '%.3f' % sr[1], '%.3f' % mad, '%.3f' % mad2])
            t.add_row([labels[i], len(data[i]),
                       "%.3f" % sd,
                       "(%.3f, %.3f)" % sr,
                       "%.3f" % (mad), "%.3f" % (mad2)
                       ])
        print(StatTable(t, 'Multi Sample Standard Deviation Test',
            ['Sample', 'N', 'SD', pct + ' CI lower', pct + ' CI upper',
             'MAD to Mean', 'MAD to Median'], values, display=display))
        print("Note: MAD to Mean is Mean Absolute Difference to Mean. MAD to Median is Mean Absolute Difference to Median.\n")

        print("H0: All variances are equal. H1: At least one variance is different.\n")
        print("O'Brien[.5]       p = %.3f" % res["OBrien"]["p"])
        print("Levene            p = %.3f" % res["Levene"]["p"])
        print("Brown-Forsythe    p = %.3f" % res["Brown_Forsythe"]["p"])

    if len(data) == 2:
        res2 = several_tests_stdev_2sided(data[0], data[1], print_out=False)
        if print_out:
            print("2 Sided F test    p = %.3f" % res2["F"]["p"])
        res["F"] = res2["F"]
    if print_out:
        print("\nNote: the results were calibrated with JMP17.\n")

    return res

##############
# 从两个population取样，测试这两个population的
# 波动一致的可能性
#######################


def two_pop_var_test(l1, l2, print_out=True):
    res = multi_pop_var_test([l1, l2], print_out=print_out)
    res2 = several_tests_stdev_2sided(l1, l2, print_out=False)
    if print_out:
        print("2 Sided F test    p = %.3f" % res2["F"]["p"])
    res["F"] = res2["F"]

    return res


def chi2_var_1sample(data=None, sample_n=None, sample_std=None,
                     print_port=print, print_out=False, alpha=0.05,
                     s0=None):
    if s0 is None:
        return
    if sample_n is None or sample_std is None:
        if data is None:
            return
        n = len(data)
        std = stat.stdev(data)
    else:
        n = sample_n
        std = sample_std

    df = n - 1

    CIn = (n - 1)**.5 * std  # CI numerator
    CI_95 = (CIn / chi2.ppf(1 - alpha / 2, df)**.5,
             CIn / chi2.ppf(alpha / 2, df)**.5)
    CI_u = CIn / chi2.ppf(alpha, df)**.5
    CI_l = CIn / chi2.ppf(1 - alpha, df)**.5

    chi_sq = (n - 1) * (std / s0)**2
    p_l = chi2.cdf(chi_sq, df)
    p_u = 1 - p_l
    p = 2 * min(p_l, p_u)

    if print_out:
        from utilities import gen_table, format_stat
        print = print_port
        print("\n---- 单样本标准差卡方检验 ----")
        print(f'显著性水平 α = {alpha:.3f}；置信水平 = {1-alpha:.1%}')
        print(f'原假设 H0: σ = σ0；σ0 = {format_stat(s0)}；卡方方法假定总体服从正态分布。')
        for title, rows, values in [
            ('样本统计', [['样本', 'N', '标准差'], ['样本', n, format_stat(std)]], [
                ['样本', n, std]]),
            ('检验结果', [['检验', '备择假设 H1', '卡方统计量', '自由度', 'p 值'],
                          ['双侧', 'sigma != sigma0', format_stat(chi_sq), df, format_stat(p)],
                          ['左尾', 'sigma < sigma0', format_stat(chi_sq), df, format_stat(p_l)],
                          ['右尾', 'sigma > sigma0', format_stat(chi_sq), df, format_stat(p_u)]], [
                ['双侧', 'sigma != sigma0', chi_sq, df, p],
                ['左尾', 'sigma < sigma0', chi_sq, df, p_l],
                ['右尾', 'sigma > sigma0', chi_sq, df, p_u]]),
            ('总体标准差的置信区间', [['区间', '下限', '上限'],
                          ['双侧置信区间', format_stat(CI_95[0]), format_stat(CI_95[1])],
                          ['单侧置信下限', format_stat(CI_l), '*'],
                          ['单侧置信上限', '*', format_stat(CI_u)]], [
                ['双侧置信区间', CI_95[0], CI_95[1]],
                ['单侧置信下限', CI_l, '*'],
                ['单侧置信上限', '*', CI_u]])]:
            print(title)
            table = gen_table(rows)
            table.align = 'r'
            table.align[table.field_names[0]] = 'l'
            print(StatTable(table, title, table.field_names, values,
                display=[[str(cell) for cell in row] for row in table.rows]))
        print('p 值保留三位小数，0.000 为舍入显示。')
    return {
        "p": p, "n": n,
        "df": df,
        "stdev": std,
        "CI 95": CI_95, "p gt": p_u, "p lt": p_l,
        "CI upper": CI_u, "CI lower": CI_l
    }


def var_1sample(data=None, sample_n=None, sample_std=None,
                print_port=print, print_out=False, alpha=0.05,
                s0=None):
    chi2_res = chi2_var_1sample(data=data, sample_n=sample_n, sample_std=sample_std,
                                print_out=False, alpha=alpha, s0=s0)
    bonett_res = {"Bonett p": np.nan,
                  "Bonett CI": (np.nan, np.nan),
                  "One tail lower boundary": np.nan,
                  "One tail upper boundary": np.nan}
    if chi2_res is not None and data is not None:
        b_res = bonett_var_1sample(data, alpha=alpha, s0=s0)
        if b_res is not None:
            bonett_res = b_res
    res = {**chi2_res, **bonett_res}
    if print_out:
        from utilities import gen_table, format_stat
        print = print_port
        print("\n---- 单样本标准差检验 ----")
        print(f'显著性水平 α = {alpha:.3f}；置信水平 = {1-alpha:.1%}')
        print(f'原假设 H0: σ = σ0；σ0 = {format_stat(s0)}；备择假设 H1: σ ≠ σ0')
        for title, rows, values in [
            ('样本统计', [['样本', 'N', '标准差'],
                          ['样本', chi2_res['n'], format_stat(chi2_res['stdev'])]], [
                ['样本', chi2_res['n'], chi2_res['stdev']]]),
            ('检验结果（双侧）', [['方法', 'p 值'],
                          ['卡方', format_stat(chi2_res['p'])],
                          ['Bonett', format_stat(bonett_res['Bonett p'])]], [
                ['卡方', chi2_res['p']],
                ['Bonett', bonett_res['Bonett p']]]),
            ('总体标准差的置信区间', [['方法', '双侧下限', '双侧上限', '单侧置信下限', '单侧置信上限'],
                          ['卡方', format_stat(chi2_res['CI 95'][0]), format_stat(chi2_res['CI 95'][1]),
                           format_stat(chi2_res['CI lower']), format_stat(chi2_res['CI upper'])],
                          ['Bonett', format_stat(bonett_res['Bonett CI'][0]), format_stat(bonett_res['Bonett CI'][1]),
                           format_stat(bonett_res['One tail lower boundary']), format_stat(bonett_res['One tail upper boundary'])]], [
                ['卡方', chi2_res['CI 95'][0], chi2_res['CI 95'][1], chi2_res['CI lower'], chi2_res['CI upper']],
                ['Bonett', bonett_res['Bonett CI'][0], bonett_res['Bonett CI'][1], bonett_res['One tail lower boundary'], bonett_res['One tail upper boundary']]])]:
            print(title)
            table = gen_table(rows)
            table.align = 'r'
            table.align[table.field_names[0]] = 'l'
            print(StatTable(table, title, table.field_names, values,
                display=[[str(cell) for cell in row] for row in table.rows]))
        print("Bonett 方法不要求总体服从正态分布，属于近似推断；小样本或重尾分布需谨慎。")
        print("卡方方法假定总体服从正态分布。")
        print('p 值保留三位小数，0.000 为舍入显示。')
    return res


if __name__ == "__main__":
    print(chi_square([[30, 76, 49], [1, 37, 62], [11, 11, 26]]))
    chi_square([[95, 43], [101, 64]])
    chi2_test_stdev([1, 1, 2, 2, 3, 4, 1], 2, print_out=True)
    var_1sample(data=[1, 2, 3, 1, 1, 2, 2], s0=1, print_out=True)
    multi_pop_var_test([[1, 2, 3, 1, 1, 2, 2], [1, 3, 4, 2, 2, 1, 3],
                       [2, 3, 1]],
                       ["a", "b", 'c'], print_out=True)
    several_tests_stdev_2sided([1, 2, 3, 1, 1, 2, 2], [
        1, 3, 4, 2, 2, 1, 3], print_out=True)
    chi_square([[2, 1], [0, 2], [1, 0]])
    chi_square([[138, 165], [5e9, 5e9]])
