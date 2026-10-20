from stat_table import StatTable
import statistics as stat
import numpy as np
from scipy.stats import f as f_dist
from scipy.stats import t as t_test
########### Own Modules ############
from utilities import make_dict, gen_table, format_stat
from t_test import t_test_1sample


def one_way_anova(data, labels, print_out=False, print_port=print,
                  alpha=0.05):
    dict_data = make_dict(data, labels)
    groups = list(dict_data.keys())
    k = len(groups)
    ns = [len(dict_data[key]) for key in groups]
    N = sum(ns)
    means = [stat.mean(dict_data[key]) for key in groups]
    pooled_variance = sum([stat.stdev(l)**2 * (len(l) - 1)
                           for l in dict_data.values()]) / (N - k)
    CIs = [t_test_1sample([], 0, sample_mean=means[i],
                          sample_n=ns[i], df=N - k,
                          sample_std=pooled_variance**.5,
                          alpha=alpha)["u0_95range"]
           for i in range(k)]
    mean = np.concatenate(list(dict_data.values())).mean()
    stds = [(pooled_variance)**.5 / (len(dict_data[key]))**.5
            for key in groups]
#    SSB = Σ(n_j * (X̄_j - X̄)^2)
    SSB = sum([n * (x - mean)**2 for n, x in zip(ns, means)])
#        SSW = Σ(X_ij - X̄_j)^2
    SSW = sum([sum([(v - means[i])**2
                    for v in dict_data[groups[i]]])
               for i in range(k)])
    SST = SSB + SSW

    df_between = k - 1
    df_within = N - k
    df_total = N - 1

    MSB = SSB / df_between
    MSW = SSW / df_within
    F = MSB / MSW

    p = 1 - f_dist.cdf(F, df_between, df_within)

    if print_out:
        print = print_port
        print("\n---- 单因素方差分析 ----")
        print("组数 = %d；总样本量 N = %d；显著性水平 alpha = %s" %
              (k, N, format_stat(alpha)))
        print("原假设 H0：各组总体均值相等；备择假设 H1：至少一组总体均值不同。")
        print("\n各组均值摘要（%.1f%% 总体均值双侧置信区间）" % ((1 - alpha) * 100))
        values = []
        t = gen_table([["组别", "N", "均值", "均值标准误", "置信下限", "置信上限"]])
        for i in range(k):
            values.append([groups[i], ns[i], means[i], stds[i], CIs[i][0], CIs[i][1]])
            t.add_row([groups[i], ns[i], format_stat(means[i]),
                       format_stat(stds[i]), format_stat(CIs[i][0]),
                       format_stat(CIs[i][1])])
        for column in t.field_names[1:]:
            t.align[column] = "r"
        print(StatTable(t, '各组均值摘要', t.field_names, values,
            display=[[str(cell) for cell in row] for row in t.rows]))
        print("均值标准误及置信区间使用合并误差方差 = %s；区间为各组单独区间，非同时置信区间。" %
              format_stat(pooled_variance))
        print("\n方差分析表")
        values = [['组间', df_between, SSB, MSB, F, p],
                  ['组内（误差）', df_within, SSW, MSW, '*', '*'],
                  ['总计', df_total, SST, '*', '*', '*']]
        t = gen_table([
            ["来源", "自由度", "平方和", "均方", "F 值", "p 值"],
            ["组间", df_between, format_stat(SSB), format_stat(MSB),
             format_stat(F), format_stat(p)],
            ["组内（误差）", df_within, format_stat(SSW), format_stat(MSW), "*", "*"],
            ["总计", df_total, format_stat(SST), "*", "*", "*"]])
        for column in t.field_names[1:]:
            t.align[column] = "r"
        print(StatTable(t, '方差分析表', t.field_names, values,
            display=[[str(cell) for cell in row] for row in t.rows]))
        print("模型假设：观测独立，组内误差近似正态且方差相等；本报告未检验这些条件。")
        print("* 表示不适用或不可用；p 值显示为 0.000 是舍入结果，不代表概率严格为零。")

    return {"F": F, "p": p,
            "df B": df_between, "df W": df_within, "df TTL": df_total,
            "MSB": MSB, "MSW": MSW, "MSE": MSW, "MSA": MSB, "CI": CIs
            }

# The means compare each pair in JMP uses pooled t-test
# while the pool includes all the keys, not only the two keys under testing
# If using unpooled t-test the p-value will be bigger than this "fully"
# pooled test

# The total pooled variance is (Sum of [(ni - 1) × si²]) / (N - k)
#     Where:
#     ni is the sample size of each group
#     si² is the variance of each group
#     N is the total sample size across all keys
#     k is the number of keys

# The standard error (SE) is calculated as:
# SE = sqrt(Sp_squared * (1/n1 + 1/n2))

# The t-statistic (t) is calculated as:
# t = (X1_bar - X2_bar) / SE

# in JMP, df is N-1 the total sample number not only the two keys


def JMP_ANOVA_t_test(data, labels, print_out=False, print_port=print,
                     alpha=0.05):
    # data come in as a dict
    # e.g. dict_data={"A":[2,1,3],"B":[3,4]}

    dict_data = make_dict(data, labels)
    keys = list(dict_data.keys())
    k = len(keys)
    ns = [len(dict_data[key]) for key in keys]
    N = sum(ns)
    df = N - 1
    means = [(stat.mean(dict_data[keys[i]]), i) for i in range(k)]

    pooled_variance = sum([stat.stdev(l)**2 * (len(l) - 1)
                           for l in dict_data.values()]) / (N - k)

    def t_test_anova(l1, l2, print_out=False):
        u1 = stat.mean(l1)
        u2 = stat.mean(l2)
        #  s1 = stat.stdev(l1)
        #  s2 = stat.stdev(l2)
        n1 = len(l1)
        n2 = len(l2)

        SE = (pooled_variance * (1 / n1 + 1 / n2))**.5
        t = (u1 - u2) / SE
        t = t if t > 0 else -t
        p = (1 - t_test.cdf(t, df)) * 2
        if print_out:
            print("SE=%.3f t=%.3f p=%.3f" % (SE, t, p))
        return {"t": t, "p": p, "SE": SE}

    ps = np.ones((k, k))
    for a in range(k):
        for b in range(a + 1, k):
            res = t_test_anova(
                dict_data[keys[a]], dict_data[keys[b]])
            ps[a][b] = ps[b][a] = res["p"]
            #  if print_out:
            #      print(
            #          "t-test means",
            #          keys[a],
            #          keys[b],
            #          "\tp = %.2f" %
            #          ps[a][b])

    means.sort(key=lambda x: x[0])
    means = means[::-1]
    groups = []
    start = 0
    while start < k:
        cmp = start_i = means[start][1]
        new_grp = [start_i]
        one_step = new_start = start + 1
        # First add the mean right below the starting point
        if one_step < k:
            one_step_i = means[one_step][1]
            if ps[one_step_i][cmp] > alpha:
                new_grp.append(one_step_i)
                cmp = one_step_i
                # Switch the comparing point to the newly added group
                # start to added the means above the starting point with
                # the new cmp point
                for p in range(start - 1, -1, -1):
                    pi = means[p][1]
                    if ps[pi][cmp] > alpha:
                        new_grp.append(pi)
                    else:
                        break
                if cmp == new_grp[-1]:  # add no new points
                    cmp = start_i      # go back start point to compare downwards
                else:
                    # new the highest point to compare downwards
                    cmp = new_grp[-1]

                for nxt in range(start + 2, k):
                    nxt_i = means[nxt][1]
                    if ps[nxt_i][cmp] > alpha:
                        new_grp.append(nxt_i)
                        new_start = nxt
                    else:
                        break
        if len(new_grp) > 1 or len(groups) == 0:
            groups.append(new_grp)
        else:
            if start_i not in groups[-1]:
                groups.append(new_grp)
        start = new_start

    if print_out:
        print = print_port
        print("\n---- 均值逐对比较（合并方差 t 检验）----")
        print("显著性水平 alpha = %s；自由度 = %d；合并方差 = %s" %
              (format_stat(alpha), df, format_stat(pooled_variance)))
        print("各对比较 H0：两组总体均值相等；H1：两组总体均值不同（双侧）。")
        print("所有组共用合并方差；以下 p 值未作多重比较校正，不控制整组比较的错误率。")
        values = []
        t = gen_table([["组别 1", "组别 2", "p 值"]])
        for i in range(1, k):
            for j in range(i):
                values.append([keys[i], keys[j], ps[i][j]])
                t.add_row([keys[i], keys[j], format_stat(ps[i][j])])
        t.align["p 值"] = "r"
        print(StatTable(t, '均值逐对比较', t.field_names, values,
            display=[[str(cell) for cell in row] for row in t.rows]))
        print("\n字母分组（按均值降序）")
        values = []
        t = gen_table([["字母分组", "组别", "均值"]])
        for i in range(k):
            key_i = means[i][1]
            gt = ""
            for j, grp in enumerate(groups):
                if key_i in grp:
                    gt += chr(65 + j) + " "
                else:
                    gt += "  "
            values.append([gt, keys[key_i], means[i][0]])
            t.add_row([gt, keys[key_i], format_stat(means[i][0])])
        t.align["均值"] = "r"
        print(StatTable(t, '字母分组（按均值降序）', t.field_names, values,
            display=[[str(cell) for cell in row] for row in t.rows]))
        print("字母分组沿用现有算法，具体差异以逐对 p 值为准；共享字母不代表总体均值相等。")
        print("模型假设：观测独立，组内误差近似正态且方差相等；本报告未检验这些条件。")
        print("p 值显示为 0.000 是舍入结果，不代表概率严格为零。")

    return {"p": ps, "keys": keys, "groups": groups}


if __name__ == "__main__":
    labels = ['small', 'medium', 'big']
    data = [[31.0, 153.0, 454.0, 333.3, 41.4, -
             680.4, 89.0, -
             119.7, 79.5, 227.4, 86.5, 20.9, 0.3, 47.7, 60.8, 118.3], [939.5, 1495.4, 252.8, 471.3, 176.0, -
                                                                       424.3, 412.7], [859.8, 1102.2, 747.0, 829.0, 1082.0, 412.0, 681.1, -
                                                                                       639.3, 3758.0]]

    one_way_anova(data, labels, print_out=True)
    JMP_ANOVA_t_test(data, labels, print_out=True)
