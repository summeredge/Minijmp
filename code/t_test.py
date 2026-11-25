from stat_table import StatTable
from scipy.stats import t as t_test
from scipy.stats import norm
import statistics as stat
from math import isfinite
############ Own Module #############
#  from utilities import mean_std_CIs


def t_test_1sample(data_list, u0, print_out=False,
                   sample_mean=None, sample_std=None, sample_n=None,
                   df=None, alpha=0.05, print_port=print):
    # Test if the data has the same mean of u0

    if sample_mean is not None and sample_std is not None and sample_n is not None:
        mean = sample_mean
        stdev = sample_std
        n = sample_n
        n_value = float(n)
        if not isfinite(n_value) or not n_value.is_integer() or n_value < 2:
            raise ValueError("样本量必须为不小于 2 的有限整数。")
    else:
        mean = stat.mean(data_list)
        stdev = stat.stdev(data_list)
        n = len(data_list)

    if (not all(isfinite(float(value)) for value in (mean, stdev, n, u0, alpha))
            or stdev <= 0 or n < 2 or not 0 < alpha < 1):
        raise ValueError("均值、标准差、样本量及显著性水平必须为有限有效数值。")

    t = (mean - u0) / stdev * (n**.5)

    if df is None:
        df = n - 1
    if not isfinite(float(df)) or df <= 0:
        raise ValueError("自由度必须为有限正数。")

    p = 2 * t_test.sf(abs(t), df)
    p_l = t_test.cdf(t, df)
    p_g = t_test.sf(t, df)

    t_0025 = t_test.ppf(alpha / 2, df)
    t_0975 = t_test.ppf(1 - alpha / 2, df)
    t_005 = t_test.ppf(alpha, df)
    t_095 = t_test.ppf(1 - alpha, df)

    u0_95range = (mean - t_0975 * stdev / (n**.5),
                  mean - t_0025 * stdev / (n**.5))
    u0_lower = mean - t_095 * stdev / (n**.5)
    u0_upper = mean - t_005 * stdev / (n**.5)
    pct = "%.2f%%" % (100 - 100 * alpha)

    # 单侧 p 值按备择方向分别取左尾或右尾。
    if print_out:
        from utilities import gen_table, format_stat
        print = print_port
        print("\n---- 单样本 t 检验 ----")
        print(f'显著性水平 α = {alpha:.3f}；置信水平 = {1-alpha:.1%}')
        print(f'原假设 H0: μ = μ0；μ0 = {format_stat(u0)}')
        for title, rows, values in [
            ('样本统计', [['样本', 'N', '均值', '标准差'],
                          ['样本', n, format_stat(mean), format_stat(stdev)]], [
                ['样本', n, mean, stdev]]),
            ('检验结果', [['检验', '备择假设 H1', 't', '自由度', 'p 值'],
                          ['双侧', 'mu != mu0', format_stat(t), format_stat(df), format_stat(p)],
                          ['左尾', 'mu < mu0', format_stat(t), format_stat(df), format_stat(p_l)],
                          ['右尾', 'mu > mu0', format_stat(t), format_stat(df), format_stat(p_g)]], [
                ['双侧', 'mu != mu0', t, df, p],
                ['左尾', 'mu < mu0', t, df, p_l],
                ['右尾', 'mu > mu0', t, df, p_g]]),
            ('总体均值的置信区间', [['区间', '下限', '上限'],
                          ['双侧置信区间', format_stat(u0_95range[0]), format_stat(u0_95range[1])],
                          ['单侧置信下限', format_stat(u0_lower), '*'],
                          ['单侧置信上限', '*', format_stat(u0_upper)]], [
                ['双侧置信区间', u0_95range[0], u0_95range[1]],
                ['单侧置信下限', u0_lower, '*'],
                ['单侧置信上限', '*', u0_upper]])]:
            print(title)
            table = gen_table(rows)
            table.align = 'r'
            table.align[table.field_names[0]] = 'l'
            print(StatTable(table, title, table.field_names, values,
                display=[[str(cell) for cell in row] for row in table.rows]))
        print("p 值是在原假设及检验模型成立时，得到当前或更极端检验统计量的概率。")
        print('p 值保留三位小数，0.000 为舍入显示。')
    return {
        "t": t,
        "p": p,
        "df": df,
        "mean": mean,
        "stdev": stdev,
        "u0_95range": u0_95range,
        "p gt": p_g, "p lt": p_l,
        "u0 lower": u0_lower, "u0 upper": u0_upper
    }


def z_test_1sample(
        data_list,
        u0,
        s0,
        sample_mean=None,
        alpha=0.05,
        sample_n=None,
        print_out=True,
        print_port=print):

    if sample_mean is None or sample_n is None:
        mean = stat.mean(data_list)
        n = len(data_list)
    else:
        n = sample_n
        mean = sample_mean

    n_value = float(n)
    if (not all(isfinite(float(value)) for value in (mean, s0, n, u0, alpha))
            or not n_value.is_integer() or n_value < 1 or s0 <= 0
            or not 0 < alpha < 1):
        raise ValueError("均值、已知标准差、样本量及显著性水平必须为有限有效数值。")

    deno = s0 / (n**.5)
    z = (mean - u0) / deno
    p = 2 * norm.sf(abs(z))
    p_l = norm.cdf(z)
    p_u = norm.sf(z)

    df = n - 1

    za2 = norm.ppf(alpha / 2)
    CI_95 = (mean + za2 * deno, mean - za2 * deno)
    za = norm.ppf(alpha)
    CI_l = mean + za * deno
    CI_u = mean - za * deno

    # 单侧 p 值按备择方向分别取左尾或右尾。
    if print_out:
        from utilities import gen_table, format_stat
        print = print_port
        print("\n---- 单样本 Z 检验 ----")
        print(f'显著性水平 α = {alpha:.3f}；置信水平 = {1-alpha:.1%}')
        print(f'原假设 H0: μ = μ0；μ0 = {format_stat(u0)}')
        for title, rows, values in [
            ('样本统计', [['样本', 'N', '均值', '已知总体标准差'],
                          ['样本', n, format_stat(mean), format_stat(s0)]], [
                ['样本', n, mean, s0]]),
            ('检验结果', [['检验', '备择假设 H1', 'Z', '自由度', 'p 值'],
                          ['双侧', 'mu != mu0', format_stat(z), format_stat(df), format_stat(p)],
                          ['左尾', 'mu < mu0', format_stat(z), format_stat(df), format_stat(p_l)],
                          ['右尾', 'mu > mu0', format_stat(z), format_stat(df), format_stat(p_u)]], [
                ['双侧', 'mu != mu0', z, df, p],
                ['左尾', 'mu < mu0', z, df, p_l],
                ['右尾', 'mu > mu0', z, df, p_u]]),
            ('总体均值的置信区间', [['区间', '下限', '上限'],
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
        print("p 值是在原假设及检验模型成立时，得到当前或更极端检验统计量的概率。")
        print('p 值保留三位小数，0.000 为舍入显示。')

        print('Z 检验使用标准正态分布；自由度为沿用的样本信息，不参与 Z 的 p 值或区间计算。')

    return {"z": z, "p": p, "df": df, "mean": mean,
            "u0_95range": CI_95,
            "p gt": p_u, "p lt": p_l,
            "u0 lower": CI_l, "u0 upper": CI_u}


def paired_t_test(l1, l2, print_out=False, u0=0,
                  alpha=0.05, print_port=print):
    diff = [i - j for i, j in zip(l1, l2)]
    res = t_test_1sample(diff, u0, print_out=False, alpha=alpha)
#     If p < alpha (e.g., p < 0.05): Reject the null hypothesis.
# There is strong evidence of a significant difference between the
# paired measurements.
    pct = "%.2f%%" % (100 - alpha * 100)
    if print_out:
        from utilities import gen_table, format_stat
        print = print_port
        print("\n---- 配对 t 检验 ----")
        print(f'显著性水平 α = {alpha:.3f}；置信水平 = {1-alpha:.1%}')
        print(f'差值 = 样本 1 - 样本 2；原假设 H0: μd = μ0；μ0 = {format_stat(u0)}')
        for title, rows, values in [
            ('样本统计', [['样本', 'N', '均值', '标准差'],
                          ['配对差值', len(diff), format_stat(res['mean']), format_stat(res['stdev'])]], [
                ['配对差值', len(diff), res['mean'], res['stdev']]]),
            ('检验结果', [['检验', '备择假设 H1', 't', '自由度', 'p 值'],
                          ['双侧', 'mu_d != mu0', format_stat(res['t']), format_stat(res['df']), format_stat(res['p'])],
                          ['左尾', 'mu_d < mu0', format_stat(res['t']), format_stat(res['df']), format_stat(res['p lt'])],
                          ['右尾', 'mu_d > mu0', format_stat(res['t']), format_stat(res['df']), format_stat(res['p gt'])]], [
                ['双侧', 'mu_d != mu0', res['t'], res['df'], res['p']],
                ['左尾', 'mu_d < mu0', res['t'], res['df'], res['p lt']],
                ['右尾', 'mu_d > mu0', res['t'], res['df'], res['p gt']]]),
            ('配对差值总体均值的置信区间', [['区间', '下限', '上限'],
                          ['双侧置信区间', format_stat(res['u0_95range'][0]), format_stat(res['u0_95range'][1])],
                          ['单侧置信下限', format_stat(res['u0 lower']), '*'],
                          ['单侧置信上限', '*', format_stat(res['u0 upper'])]], [
                ['双侧置信区间', res['u0_95range'][0], res['u0_95range'][1]],
                ['单侧置信下限', res['u0 lower'], '*'],
                ['单侧置信上限', '*', res['u0 upper']]])]:
            print(title)
            table = gen_table(rows)
            table.align = 'r'
            table.align[table.field_names[0]] = 'l'
            print(StatTable(table, title, table.field_names, values,
                display=[[str(cell) for cell in row] for row in table.rows]))
        print('p 值保留三位小数，0.000 为舍入显示。')
    return res

# Assumptions:
#   Pooled t-test assumes equal population variances between the two groups.
#   Unpooled t-test (Welch's t-test) does not assume equal population variances.
# Degrees of freedom (df) calculation:
#   Pooled t-test: df = n1 + n2 - 2
#   Unpooled t-test: Uses a more complex formula (Welch–Satterthwaite equation)
#   that typically results in non-integer df.
#        df = (s1^2/n1 + s2^2/n2)^2 / [(s1^2/n1)^2/(n1-1) + (s2^2/n2)^2/(n2-1)]
# Variance estimation:
#   Pooled t-test uses a weighted average of the two sample variances (pooled variance).
#   Unpooled t-test uses separate variance estimates for each group.
# Applicability:
#   Pooled t-test is more appropriate when variances are truly equal or sample sizes are equal.
# Unpooled t-test is more robust and generally recommended when unsure
# about variance equality.


def t_test_2samples(l1=None, l2=None,
                    n1=None, n2=None, u1=None, u2=None,
                    s1=None, s2=None,
                    alpha=0.05, d0=0, pooled=False,
                    print_out=False, print_port=print):

    def tTest(dx, d0, s, df, alpha, title,
              print_out=False, print_port=None):
        ta2 = t_test.ppf(alpha / 2, df)
        CI = (dx + ta2 * s, dx - ta2 * s)
        margin = t_test.ppf(1 - alpha, df) * s
        lower, upper = dx - margin, dx + margin
        t = (dx - d0) / s
        pl = t_test.cdf(t, df)
        pu = t_test.sf(t, df)
        p = 2 * t_test.sf(abs(t), df)
        if print_out:
            from utilities import gen_table, format_stat
            print = print_port
            print('方法：合并方差 t（pooled）' if title == 'Equal variances, pooled t'
                  else '方法：Welch t（JMP 17，不等方差）')
            for heading, rows, values in [
                ('检验结果', [['检验', '备择假设 H1', 't', '自由度', 'p 值'],
                              ['双侧', 'mu2 - mu1 != d0', format_stat(t), format_stat(df), format_stat(p)],
                              ['左尾', 'mu2 - mu1 < d0', format_stat(t), format_stat(df), format_stat(pl)],
                              ['右尾', 'mu2 - mu1 > d0', format_stat(t), format_stat(df), format_stat(pu)]], [
                    ['双侧', 'mu2 - mu1 != d0', t, df, p],
                    ['左尾', 'mu2 - mu1 < d0', t, df, pl],
                    ['右尾', 'mu2 - mu1 > d0', t, df, pu]]),
                ('总体均值差 μ2 - μ1 的置信区间', [['区间', '下限', '上限'],
                              ['双侧置信区间', format_stat(CI[0]), format_stat(CI[1])],
                              ['单侧置信上界（左尾）', '', format_stat(upper)],
                              ['单侧置信下界（右尾）', format_stat(lower), '']], [
                    ['双侧置信区间', CI[0], CI[1]],
                    ['单侧置信上界（左尾）', None, upper],
                    ['单侧置信下界（右尾）', lower, None]])]:
                print(heading)
                table = gen_table(rows)
                table.align = 'r'
                table.align[table.field_names[0]] = 'l'
                print(StatTable(table, heading, table.field_names, values,
                    display=[[str(cell) for cell in row] for row in table.rows]))
            print('p 值保留三位小数，0.000 为舍入显示。')
        return {"CI": CI, "p": p, "p lower": pl, "p upper": pu, "t": t,
                "df": df, "CI lower one-sided": lower, "CI upper one-sided": upper}

    #  summarized = False
    #  if n1 is not None and n2 is not None:
    #      if s1 is not None and s2 is not None:
    #          if u1 is not None and u2 is not None:
    #              summarized = True
    #  if not summarized:
    #      if l1 is None or l2 is None:
    #          return
    if n1 is None or s1 is None or u1 is None:
        u1 = stat.mean(l1)
        s1 = stat.stdev(l1)
        n1 = len(l1)

    if n2 is None or s2 is None or u2 is None:
        u2 = stat.mean(l2)
        s2 = stat.stdev(l2)
        n2 = len(l2)

    if print_out:
        from utilities import gen_table, format_stat
        print = print_port
        print("\n---- 两独立样本 t 检验 ----")
        print(f'显著性水平 α = {alpha:.3f}；置信水平 = {1-alpha:.1%}')
        print(f'原假设 H0: μ2 - μ1 = d0；d0 = {format_stat(d0)}；样本均值差 u2 - u1 = {format_stat(u2 - u1)}')
        print('样本统计')
        values = [['样本 1', n1, u1, s1],
                  ['样本 2', n2, u2, s2]]
        table = gen_table([['样本', 'N', '均值', '标准差'],
                           ['样本 1', n1, format_stat(u1), format_stat(s1)],
                           ['样本 2', n2, format_stat(u2), format_stat(s2)]])
        table.align = 'r'
        table.align[table.field_names[0]] = 'l'
        print(StatTable(table, '样本统计', table.field_names, values,
            display=[[str(cell) for cell in row] for row in table.rows]))
    # t = (x̄₁ - x̄₂) / √((s₁²/n₁) + (s₂²/n₂))
    # df = (s1^2/n1 + s2^2/n2)^2 / [(s1^2/n1)^2/(n1-1) + (s2^2/n2)^2/(n2-1)]

    if not pooled:
        # JMP 17 method unequal variances
        s = (s1 * s1 / n1 + s2 * s2 / n2)**.5
        df = (s1 * s1 / n1 + s2 * s2 / n2)**2 / ((s1 * s1 / n1)
                                                 ** 2 / (n1 - 1) + (s2 * s2 / n2)**2 / (n2 - 1))
        res = tTest(u2 - u1, d0, s, df, alpha,
                    "JMP 17 method unequal variances",
                    print_out=print_out, print_port=print_port)
    else:
        #  Minitab unequal variances method
        #  var1 = s1 * s1 / n1
        #  var2 = s2 * s2 / n2
        #  df = (var1 + var2)**2 / (var1**2 / (n1 - 1) + var2**2 / (n2 - 1))
        #  resM = tTest(u2 - u1, d0, s, df, alpha,
        #               "Minitab 20 method unequal variances",
        #               print_out=print_out, print_port=print_port)

        # Equal variances same to both
        sp = (((n1 - 1) * s1 * s1 + s2 * s2 * (n2 - 1)) / (n1 + n2 - 2))**.5
        s = sp * (1 / n1 + 1 / n2)**.5
        df = n1 + n2 - 2
        res = tTest(u2 - u1, d0, s, df, alpha,
                    "Equal variances, pooled t",
                    print_out=print_out, print_port=print_port)

    return res
    #  {"pooled": resP,
    #  #  "minitab": resM,
    #  "jmp": resJ}


if __name__ == "__main__":
    l1 = [1, 2, 3, 1, 1, 2, 2]
    l2 = [1, 3, 4, 2, 2, 1, 3]
    #  t_test_1sample(l1, 1, print_out=True)
    #  paired_t_test(l1, l2, print_out=True)
    #  print(t_test_2samples(l1, l2, print_out=True))
    #  print(t_test_2samples_pooled(l1, l2, print_out=True))
    z_test_1sample(l1, 1, 1, print_out=True)
    t_test_2samples(l1, l2, print_out=True)
    paired_t_test(l1, l2, print_out=True)


def equivalence_tost(first, second=None, *, lower, upper, alpha=.05,
                     target=0., paired=False, pooled=False):
    """Estimate the second-minus-first difference or one-sample target offset."""
    import numpy as np

    if not np.isfinite([lower, upper, target]).all() or not lower < upper or not 0 < alpha < .5:
        raise ValueError("等效下限须小于上限，界限与目标须有限，且 0 < α < 0.5。")
    x = np.asarray(first, dtype=float)
    y = None if second is None else np.asarray(second, dtype=float)
    if paired:
        if y is None or len(x) != len(y):
            raise ValueError("配对样本需按同一行对应。")
        valid = np.isfinite(x) & np.isfinite(y)
        x, y = y[valid] - x[valid], None

    x = x[np.isfinite(x)].tolist()
    if len(x) < 2:
        raise ValueError("每组至少需要两个有效观测或配对差。")

    if y is None:
        if stat.stdev(x) <= 0:
            raise ValueError("样本或配对差的标准差须为正数。")
        estimate = stat.mean(x) - target
        low = t_test_1sample(x, target + lower, alpha=alpha)
        high = t_test_1sample(x, target + upper, alpha=alpha)
        interval = (low["u0 lower"] - target, low["u0 upper"] - target)
        ns = (len(x),)
    else:
        y = y[np.isfinite(y)].tolist()
        if len(y) < 2 or (stat.stdev(x) == 0 and stat.stdev(y) == 0):
            raise ValueError("每组至少需要两个有效观测，且标准误须为正数。")
        estimate = stat.mean(y) - stat.mean(x) - target
        low = t_test_2samples(x, y, d0=target + lower, alpha=alpha, pooled=pooled)
        high = t_test_2samples(x, y, d0=target + upper, alpha=alpha, pooled=pooled)
        interval = (low["CI lower one-sided"] - target, low["CI upper one-sided"] - target)
        ns = (len(x), len(y))
    df = low["df"]
    p_lower = t_test.sf(low["t"], df)
    p_upper = t_test.cdf(high["t"], df)
    return dict(estimate=estimate, n=ns, df=df, t_lower=low["t"], t_upper=high["t"],
                p_lower=p_lower, p_upper=p_upper, interval=interval,
                equivalent=max(p_lower, p_upper) < alpha)
