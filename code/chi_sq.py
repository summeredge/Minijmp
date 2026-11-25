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
    from .bonett import var_1sample as bonett_var_1sample, pair_ratio
except BaseException:
    from bonett import var_1sample as bonett_var_1sample, pair_ratio


def chi2_test_stdev(data_list, s0, print_out=False, alpha=0.05,
                    print_port=print):
    df = len(data_list) - 1
    S = stat.variance(data_list) * df
    stdev = stat.stdev(data_list)
    chi_sq = S / s0 / s0
    p = chi2.sf(chi_sq, df)

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
    p = 2 * f_dist.sf(f, dfn, dfd)
    if p > 1:
        f = var2 / var1
        dfn, dfd = n2 - 1, n1 - 1
        p = 2 * f_dist.sf(f, dfn, dfd)
    res["F"] = {"f": f, "p": p, "dfn": dfn, "dfd": dfd}

    #  kp = ((n1 - 1) * k1 + (n2 - 1) * k2) / (n1 + n2 - 2)
    #  SE = (kp / 2 / (n1 - 1) + kp / 2 / (n2 - 1))**.5
    z = (ln(var1) - ln(var2)) / (2 / n1 + 2 / n2)**.5
    p2 = 2 * norm.sf(abs(z))
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

        p = chi2.sf(chi_sq, df)
    except BaseException:
        chi_sq = p = np.nan
    LR = 0
    try:
        for y in range(a.shape[0]):
            for x in range(a.shape[1]):
                expected = row_sum[y] * col_sum[x] / ttl_sum
                LR += 2 * xlogy(a[y][x], a[y][x] / expected)
                e[y][x] = expected

        p_LR = chi2.sf(LR, df)
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
        p = f_dist.sf(F, k - 1, N - k)
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

    # 每组的联合区间：Bonett 区间在 alpha/k 下计算，与目标产品的
    # "95% Bonferroni 标准差置信区间"一致（单组置信水平 1-alpha/k）。
    joint = [bonett_var_1sample(group, alpha=alpha / len(data), s0=stat.stdev(group))
             if len(data) > 1 else None for group in data]
    pair_count = len(data) * (len(data) - 1) / 2
    comparisons = [
        {"groups": (labels[i], labels[j]), **dict(zip(
            ("ratio", "Bonett CI", "p", "adjusted p"),
            pair_ratio(data[i], data[j], m=pair_count, alpha=alpha)))}
        for i in range(len(data)) for j in range(i + 1, len(data))] if len(data) > 1 else []
    for row in comparisons:
        row["significant"] = bool(row["adjusted p"] < alpha)

    if print_out:
        from utilities import gen_table
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

        if comparisons:
            # 联合区间与目标产品 "95% Bonferroni 标准差置信区间"同口径。
            values, display = [], []
            for label, ci in zip(labels, joint):
                lo, hi = ci["Bonett CI"]
                values.append([label, lo, hi])
                display.append([str(label), '%.3f' % lo, '%.3f' % hi])
            t = gen_table([['组别', '联合区间下限', '联合区间上限'], *display])
            t.align = 'r'
            t.align['组别'] = 'l'
            print(StatTable(t, f"标准差 {100 - 100 * alpha:.0f}% Bonferroni 置信区间"
                              f"（单组置信 {100 - 100 * alpha / len(data):.4f}%）",
                t.field_names, values, display=display))

            pct_joint = "%.1f%% Bonferroni" % (100 - 100 * alpha)
            values, display = [], []
            for row in comparisons:
                lo, hi = row["Bonett CI"]
                values.append([row["groups"][0], row["groups"][1], row["ratio"],
                               lo, hi, row["p"], row["adjusted p"],
                               '是' if row["significant"] else '否'])
                display.append([str(row["groups"][0]), str(row["groups"][1]),
                                '%.3f' % row["ratio"], '%.3f' % lo, '%.3f' % hi,
                                '%.3f' % row["p"], '%.3f' % row["adjusted p"],
                                '是' if row["significant"] else '否'])
            t = gen_table([['组别 1', '组别 2', '标准差比', pct_joint + ' 区间下限',
                            pct_joint + ' 区间上限', 'p 值', '调整 p 值', '显著差异'], *display])
            t.align = 'r'
            t.align['组别 1'] = 'l'
            t.align['组别 2'] = 'l'
            t.align['显著差异'] = 'l'
            print(StatTable(t, '标准差比的多重比较（Bonett 对数近似，Bonferroni 调整）',
                t.field_names, values, display=display))
            print("多重比较沿用 Bonett 对数尺度正态近似，按比较数 m 以 Bonferroni 分摊显著性水平；"
                  "区间为成对标准差比的联合区间，与目标产品的全局多重比较 p 口径不同。")

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
    return multi_pop_var_test([l1, l2], ['样本 1', '样本 2'], print_out=print_out)


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
    p_u = chi2.sf(chi_sq, df)
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
                  "Bonett p lt": np.nan,
                  "Bonett p gt": np.nan,
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
        print(f'原假设 H0: σ = σ0；σ0 = {format_stat(s0)}；'
              '备择假设 H1: σ ≠ σ0（左尾 σ < σ0，右尾 σ > σ0）')
        for title, rows, values in [
            ('样本统计', [['样本', 'N', '标准差'],
                          ['样本', chi2_res['n'], format_stat(chi2_res['stdev'])]], [
                ['样本', chi2_res['n'], chi2_res['stdev']]]),
            ('检验结果', [['方法', '双侧 p 值', '左尾 p 值', '右尾 p 值'],
                          ['卡方', format_stat(chi2_res['p']),
                           format_stat(chi2_res['p lt']), format_stat(chi2_res['p gt'])],
                          ['Bonett', format_stat(bonett_res['Bonett p']),
                           format_stat(bonett_res['Bonett p lt']),
                           format_stat(bonett_res['Bonett p gt'])]], [
                ['卡方', chi2_res['p'], chi2_res['p lt'], chi2_res['p gt']],
                ['Bonett', bonett_res['Bonett p'], bonett_res['Bonett p lt'],
                 bonett_res['Bonett p gt']]]),
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

def _mc_directional_root(log_ratio, ni, nj, width):
    """Banga–Fox §3.1 的左根。非正根的正态极差上尾概率为 1。"""
    from scipy.optimize import brentq

    def equation(z):
        return log_ratio + np.log1p(-z/nj) - np.log1p(-z/ni) - z*width

    if ni < nj:
        delta = nj-ni
        # 左根所在的单调区间截止于 L 的唯一极小点。
        upper = ni - (2*delta/width)/(np.sqrt(delta**2+4*delta/width)+delta)
        if equation(upper) > 0:
            return np.inf  # 论文规定该方向的尾概率取 0。
        if upper <= 0:
            return 0.
    else:
        upper = np.nextafter(float(nj), 0.)
        if equation(upper) > 0:
            return upper  # 根与奇点的距离小于浮点分辨率。
    return brentq(equation, 0., upper) if log_ratio > 0 else 0.


def equal_variances_mc(data, alpha=.05):
    """Banga–Fox graphical multiple comparisons for three or more groups."""
    from itertools import combinations
    from scipy.stats import norm, studentized_range, trim_mean

    k = len(data)
    if k < 3 or not 0 < alpha < 1:
        raise ValueError('图形多重比较需要至少三组，且显著性水平须介于 0 和 1。')
    values = [np.asarray(group, dtype=float) for group in data]
    n = np.array([len(group) for group in values])
    if np.any(n < 5) or any(not np.isfinite(group).all() for group in values):
        raise ValueError('各组至少需要五个有限观测。')
    variances = np.array([np.var(group, ddof=1) for group in values])
    if not np.all(np.isfinite(variances) & (variances > 0)):
        raise ValueError('各组必须有正且有限的样本方差。')
    log_var = np.log(variances)
    fourth = np.array([np.sum((group-trim_mean(group, 1/(2*np.sqrt(size-4))))**4)
                       for group, size in zip(values, n)])
    ss = np.array([np.sum((group-group.mean())**2) for group in values])
    i, j = np.asarray(list(combinations(range(k), 2))).T
    ni, nj = n[i], n[j]
    pooled = (ni+nj)*(fourth[i]+fourth[j])/(ss[i]+ss[j])**2
    widths = np.sqrt((pooled-(ni-3)/ni)/(ni-1) + (pooled-(nj-3)/nj)/(nj-1))
    incident = np.bincount(i, weights=widths, minlength=k)+np.bincount(j, weights=widths, minlength=k)
    fitted = (incident-widths.sum()/(k-1))/(k-2)
    if not np.all(np.isfinite(fitted) & (fitted > 0)):
        raise ValueError('无法构造正宽度的图形比较区间。')
    gaps, pair_widths = log_var[i]-log_var[j], fitted[i]+fitted[j]
    roots = np.abs(gaps)/pair_widths
    for index in np.flatnonzero(ni != nj):
        a, b = ni[index], nj[index]
        gap, width = gaps[index], pair_widths[index]
        roots[index] = max(_mc_directional_root(gap, a, b, width),
                           _mc_directional_root(-gap, b, a, width))
    root = np.max(roots)
    p = 0. if np.isinf(root) else studentized_range.sf(np.sqrt(2)*root, k, np.inf)
    critical = studentized_range.isf(alpha, k, np.inf)/np.sqrt(2)
    balanced = np.all(n == n[0])
    # 不等量按 §3.2 反演，修正项和区间宽度使用同一个临界值。
    # 等量修正项仅同比例缩放区间，保留原有显示约定。
    correction = norm.isf(alpha/2) if balanced else critical
    if correction >= min(n):
        raise ValueError('显著性水平过小，无法计算图形比较区间的样本量修正。')
    mid = .5*(log_var-np.log1p(-correction/n))
    margin = critical*fitted/2
    return float(p), np.exp(np.column_stack((mid-margin, mid+margin)))


def variance_ratio_test(samples=None, *, summary=None, method="F", target=1.,
                        scale="variance", alternative="two-sided", alpha=.05):
    from scipy.optimize import brentq
    from scipy.stats import t
    from bonett import trimmed_mean

    if (not np.isfinite(target) or target <= 0 or not 0 < alpha < 1
            or alternative not in ("two-sided", "less", "greater")):
        raise ValueError("比值必须为有限正数，且 0 < α < 1。")
    if samples is not None:
        groups = [np.asarray(group, dtype=float) for group in samples]
        groups = [group[np.isfinite(group)] for group in groups]
        if any(len(group) < 2 for group in groups):
            raise ValueError("每组至少需要两个有限观测。")
        ns = [len(group) for group in groups]
        variances = [group.var(ddof=1) for group in groups]
    elif summary is not None and method == "F":
        ns, variances = map(list, zip(*summary))
    else:
        raise ValueError("Bonett 和 Levene 需要原始观测。")
    if any(not np.isfinite(n) or n < 2 or int(n) != n for n in ns):
        raise ValueError("每组样本量必须是至少为 2 的整数。")
    if any(not np.isfinite(v) or v <= 0 for v in variances):
        raise ValueError("两组样本方差均须为有限正数。")
    n1, n2 = ns
    v1, v2 = variances
    log_estimate = np.log(v1) - np.log(v2)
    log_target = np.log(target) * (2 if scale == "std" else 1)
    a = alpha / 2 if alternative == "two-sided" else alpha
    lower = 0.
    upper = np.inf

    if method == "F":
        statistic = np.exp(log_estimate - log_target)
        df = (n1-1, n2-1)
        p_low, p_high = f_dist.cdf(statistic, *df), f_dist.sf(statistic, *df)
        if alternative != "less":
            lower = np.exp(log_estimate) / f_dist.isf(a, *df)
        if alternative != "greater":
            upper = np.exp(log_estimate) / f_dist.ppf(a, *df)
    elif method == "Bonett":
        if n1 != n2 or n1 < 6:
            raise ValueError("Bonett 当前支持等样本量且每组至少 6 个观测。")
        n = n1
        fourth = [np.sum(((x - trimmed_mean(x.tolist())) / np.sqrt(v))**4)
                  for x, v in zip(groups, variances)]
        from scipy.special import expit

        def se(offset):
            weight = expit(offset)
            kurtosis = 2*n * (fourth[0]*(1-weight)**2 + fourth[1]*weight**2) / (n-1)**2
            return np.sqrt(2 * (kurtosis - (n-3)/n) / (n-1))

        offset = log_target - log_estimate
        statistic = -offset / se(offset)
        p_low, p_high = norm.cdf(statistic), norm.sf(statistic)
        critical = norm.isf(a)
        span = abs(critical) * np.sqrt(4*n*max(fourth)/(n-1)**3) + 1

        if alternative != "less":
            bound = brentq(lambda z: z + critical*se(z), -span, span)
            lower = np.exp(log_estimate + bound)
        if alternative != "greater":
            bound = brentq(lambda z: z - critical*se(z), -span, span)
            upper = np.exp(log_estimate + bound)
    elif method == "Levene":
        first, second = [np.abs(x - np.median(x)) for x in groups]
        m1, m2 = first.mean(), second.mean()
        df = n1 + n2 - 2
        factor = (1/n1 + 1/n2) / df
        w1 = factor * np.sum((first - m1)**2)
        w2 = factor * np.sum((second - m2)**2)
        if w1 + w2 <= 0:
            raise ValueError("中位数绝对偏差没有组内变异，无法进行 Levene 检验。")
        rho = np.exp(log_target / 2)
        statistic = (m1 - rho*m2) / np.sqrt(w1 + rho*rho*w2)
        p_low, p_high = t.cdf(statistic, df), t.sf(statistic, df)
        critical = t.isf(a, df)
        if critical < 0:
            raise ValueError("Levene 单侧置信水平须至少为 50%。")
        if alternative != "less" and m1 > critical*np.sqrt(w1):
            bound = brentq(lambda r: (m1*r - m2) - critical*np.hypot(np.sqrt(w1)*r, np.sqrt(w2)),
                           0., 1 + (m2 + critical*np.sqrt(w2))/(m1 - critical*np.sqrt(w1)))
            lower = 1 / bound**2
        if alternative != "greater" and m2 > critical*np.sqrt(w2):
            bound = brentq(lambda r: (m2*r - m1) - critical*np.hypot(np.sqrt(w2)*r, np.sqrt(w1)),
                           0., 1 + (m1 + critical*np.sqrt(w1))/(m2 - critical*np.sqrt(w2)))
            upper = bound**2
    else:
        raise ValueError("未知离散度检验方法。")
    pvalue = {"two-sided": 2*min(p_low, p_high), "less": p_low, "greater": p_high}[alternative]
    power = .5 if scale == "std" else 1.
    return dict(n=ns, variances=variances, estimate=np.exp(log_estimate*power),
                statistic=statistic, pvalue=pvalue, interval=(lower**power, upper**power))
