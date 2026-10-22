from stat_table import StatTable
from scipy.stats import norm, gamma, weibull_min, lognorm, johnsonsu, expon
#  from scipy.stats import gamma as gamma
from scipy.stats import t as t_dist
from math import log as ln
from math import exp
from numpy import nan
import statistics as stat
import numpy as np
#  from scipy.optimize import minimize
##### Own Modules #####
from utilities import norm_test, gen_table, format_stat


def ABL(rv, data, k):
    """
    calculate -2*log-likelihood, AICc and BIC
    rv is the frozen dist function
    k is the number of parameters of the dist funciton.
    """
    log_likelihood = sum(
        ln(rv.pdf(i)) for i in data)
    n = len(data)
    if n - k > 1:
        AICc = -2 * log_likelihood + 2 * k * n / (n - k - 1)
    else:
        AICc = nan
    if n > 0:
        BIC = -2 * log_likelihood + ln(n) * k
    else:
        BIC = nan
    return (-2 * log_likelihood, AICc, BIC)


def print_table(fit_name, para_names, paras, abl, a2, p, print_port=print):
    print = print_port
    print("候选分布：" + fit_name)
    t = gen_table([['参数', '估计值']])
    for i, j in zip(para_names, paras):
        t.add_row([i, format_stat(j)])
    t.align['估计值'] = 'r'
    print(StatTable(t, fit_name + ' 参数估计', t.field_names,
        [[name, value] for name, value in zip(para_names, paras)], display=[[str(v) for v in row] for row in t.rows]))
    print("参数置信区间：现有方法未计算。")
    t = gen_table([['-2*LogLikelihood', 'AICc', 'BIC'],
                   [format_stat(value) for value in abl]])
    t.align = 'r'
    print(StatTable(t, fit_name + ' 拟合指标', t.field_names,
        [list(abl)], display=[[str(v) for v in row] for row in t.rows]))
    t = gen_table([['拟合优度方法', 'AD 统计量', '近似 p 值'],
                   ['Anderson-Darling', format_stat(a2), format_stat(p)]])
    t.align['AD 统计量'] = 'r'
    t.align['近似 p 值'] = 'r'
    print(StatTable(t, fit_name + ' 拟合优度', t.field_names,
        [['Anderson-Darling', a2, p]], display=[[str(v) for v in row] for row in t.rows]))
    print("H0：样本来自所拟合的分布；小 p 值提示与该分布不符，未拒绝 H0 不等于证明分布正确。")
    print("p 值不是 H0 成立的概率；p = 0.000 为三位小数舍入结果，不代表概率严格为零。")
    print("AD 的 p 值为近似值；非正态分布沿用现有近似，未进行分布专用校准。")
    print("AICc、BIC 用于同一数据下候选模型的相对比较，值越小越优；它们与 AD 统计量含义不同。")
    print("* 表示不可用或未计算的统计量。")
    return


def AD(rv, data):
    n = len(data)
    data = np.array(data, dtype=float)
    data = np.sort(data)
    cdf = rv.cdf(data)
# Calculate the AD statistic
    ad_stat = -n - np.sum((2 * np.arange(1, n + 1) - 1) * (np.log(cdf) + np.log(1 - cdf[::-1]))) / n
    return ad_stat


def p_simulation(rv, a2, n, TTL=10000):
    cnt = 0
    for i in range(TTL):
        if AD(rv, rv.rvs(size=n)) >= a2:
            cnt += 1
    return cnt / TTL


def approximate_p(ad_adjusted):
    # The approximate p-value for the second test statistic is computed from a set of four interpolating functions
    # R.B. D'Augostino and M.A. Stephens, Eds., 1986, Goodness-of-Fit Techniques, Marcel Dekker.

    #  ad_adjusted = ad_stat * (1 + (0.75/n) + (2.25/n**2))
    # However, I found without adj the p value is closer to the JMP simulated p-value

    if ad_adjusted >= 0.6:
        p = np.exp(1.2937 - 5.709 * ad_adjusted + 0.0186 * ad_adjusted**2)
    elif 0.34 < ad_adjusted < 0.6:
        p = np.exp(0.9177 - 4.279 * ad_adjusted - 1.38 * ad_adjusted**2)
    elif 0.2 < ad_adjusted <= 0.34:
        p = 1 - np.exp(-8.318 + 42.796 * ad_adjusted - 59.938 * ad_adjusted**2)
    else:  # ad_adjusted <= 0.2
        p = 1 - np.exp(-13.436 + 101.14 * ad_adjusted - 223.73 * ad_adjusted**2)

    return p


def goodness_of_fit(rv, data, normal=False):
    if normal:
        res = norm_test(data, print_out=False)
        return res['AD s'], res['AD p']
    else:
        a2 = AD(rv, data)
        #  p = p_simulation(rv, a2, len(data))
        p = approximate_p(a2)
    return a2, p


def fit_norm(data, print_out=True, print_port=print):
    u, s = stat.mean(data), stat.stdev(data)
    #  u, s = norm.fit(data)
    #  print(u, s)
    rv = norm(u, s)
    #  n = len(data)
    abl = ABL(rv, data, 2)
    a2, p = goodness_of_fit(rv, data, normal=True)
    if print_out:
        print_port("\n---- 分布拟合 ----")
        print_port("样本量 N = %d" % len(data))
        print_table("正态 Normal", ("总体均值 mu", "总体标准差 sigma"),
                    (u, s), abl, a2, p, print_port=print_port)
        print_port("正态分布：mu 为均值，sigma 为标准差；沿用样本均值和样本标准差估计。")
    return {"fits": (u, s), "ABL": abl, "rv": rv}

    #  sem = s / n**.5
    #  ses = s / (2 * (n - 1))**.5
    #  print(sem, ses)
    #  print(ll, aicc, bic)
    #  u4 = sum((i - u)**4 for i in data) / n
    #  sess = (1 / n * (u4 - (n - 3) / (n - 1) * s**4))**.5
    #  print(sess / 2 / s)
    #  print(stat.stdev(data))


def fit_t(data, print_out=True, print_port=print):
    #  data = np.array(data)
    df, u, s = t_dist.fit(data)
    #  print(ABL(t_dist(df), (data - u) / s, 3))
    rv = t_dist(df, loc=u, scale=s)
    abl = ABL(rv, data, 3)
    a2, p = goodness_of_fit(rv, data)
    if print_out:
        print_port("\n---- 分布拟合 ----")
        print_port("样本量 N = %d" % len(data))
        print_table("Student's t",
                    ("位置 loc", "尺度 scale", "自由度 df"),
                    (u, s, df), abl, a2, p, print_port=print_port)
        print_port("Student's t 分布：loc 为位置，scale 为尺度，并非标准差；df 为自由度。")
    return {"fits": (u, s, df), "ABL": abl, "rv": rv}

    ##### The minimum fitting gives similar but not same results #####

    #  def lsq(parameters):
    #      u, s = parameters
    #      nd = (data - u) / s
    #      df, _, _ = t_dist.fit(nd)
    #      #  rv=t_dist(df)
    #      osm, osr = probplot(data, dist="t", sparams=(df,))[0]
    #      return np.sum((osm - osr) ** 2)
    #  # Initial guess for the parameters
    #  initial_guess = np.array([stat.mean(data), stat.stdev(data)])
    #
    #  # Perform the minimization
    #  objective_function = lsq
    #  result = minimize(objective_function, initial_guess, method='BFGS')
    #
    #  # Extract the results
    #  optimized_params = result.x
    #  minimum_value = result.fun
    #
    #  print("Optimized Parameters:", optimized_params)
    #  print("Minimum Value of the Function:", minimum_value)
    #


def fit_gamma(data, print_out=True, print_port=print):
    #  data = np.array(data)
    # this replicate JMP 17 with fixed location at zero
    #  print(gamma.fit(data, floc=0))
    u, _, s = gamma.fit(data, floc=0)
    #  print(ABL(t_dist(df), (data - u) / s, 3))
    rv = gamma(u, loc=0, scale=s)
    abl = ABL(rv, data, 2)
    a2, p = goodness_of_fit(rv, data)
    if print_out:
        print_port("\n---- 分布拟合 ----")
        print_port("样本量 N = %d" % len(data))
        print_table("Gamma", ("形状 shape", "尺度 scale"),
                    (u, s), abl, a2, p, print_port=print_port)
        print_port("Gamma 分布：位置固定为 0，shape 为形状，scale 为尺度；输入值须 > 0。")
    return {"fits": (u, s), "ABL": abl, "rv": rv}


def fit_weibull(data,
                print_out=True, print_port=print):
    #  print(weibull_min.fit(data, floc=0))
    u, _, s = weibull_min.fit(data, floc=0)
    rv = weibull_min(u, loc=0, scale=s)
    abl = ABL(rv, data, 2)
    a2, p = goodness_of_fit(rv, data)
    if print_out:
        print_port("\n---- 分布拟合 ----")
        print_port("样本量 N = %d" % len(data))
        print_table("Weibull", ("尺度 scale", "形状 shape"),
                    (s, u), abl, a2, p, print_port=print_port)
        print_port("Weibull 分布：位置固定为 0，scale 为尺度，shape 为形状；输入值须 > 0。")
    return {"fits": (s, u), "ABL": abl, "rv": rv}


def fit_lognorm(data,
                print_out=True, print_port=print):
    #  data = [-i for i in data]
    a, _, s = lognorm.fit(data, floc=0)
    #  print(a, ln(s))
    rv = lognorm(a, loc=0, scale=s)
    abl = ABL(rv, data, 2)
    a2, p = goodness_of_fit(rv, data)
    if print_out:
        print_port("\n---- 分布拟合 ----")
        print_port("样本量 N = %d" % len(data))
        print_table("对数正态 Lognormal", ("对数均值 mu", "对数标准差 sigma"),
                    (ln(s), a), abl, a2, p, print_port=print_port)
        print_port("对数正态分布：位置固定为 0；mu、sigma 分别为 ln(X) 的均值、标准差，SciPy scale = exp(mu)；输入值须 > 0。")
    return {"fits": (s, a), "ABL": abl, "rv": rv}


def fit_jsu(data):
    print(johnsonsu.fit(data))


def fit_expon(data,
              print_out=True, print_port=print):
    #  print(expon.fit(data, floc=0))
    _, s = expon.fit(data, floc=0)
    rv = expon(loc=0, scale=s)
    abl = ABL(rv, data, 1)
    a2, p = goodness_of_fit(rv, data)
    if print_out:
        print_port("\n---- 分布拟合 ----")
        print_port("样本量 N = %d" % len(data))
        print_table("指数 Exponential", ("尺度 scale (均值)", ),
                    (s, ), abl, a2, p, print_port=print_port)
        print_port("指数分布：位置固定为 0，scale 为均值及尺度；输入值须 >= 0。")
    return {"fits": (s,), "ABL": abl, "rv": rv}


def compare_dist(
    data,
    print_out=True,
    print_port=print,
    selected=[
        "Normal",
        "Student's t",
        "Gamma",
        "Lognormal",
        "Exponential",
        "Weibull"]):
    funcs = [fit_norm, fit_t, fit_gamma, fit_lognorm, fit_expon,
             fit_weibull]
    names = ["Normal", "Student's t", "Gamma", "Lognormal", "Exponential",
             "Weibull"]
    aiccs, res = [], []
    for name, func in zip(names, funcs):
        try:
            if name not in selected:
                continue
            r = func(data, print_out=print_out, print_port=print_port)
            res.append([name, r["ABL"], r])
            aiccs.append(r["ABL"][1])
        except BaseException:
            if print_out:
                print = print_port
                print("---- 分布拟合：" + name + " ----")
                print("拟合失败：请检查输入值及所选分布的适用条件。")
            pass
    delta_AICc = [i - min(aiccs) for i in aiccs]
    rel_likelihood = [exp(-.5 * i) for i in delta_AICc]
    AICc_weight = [i / sum(rel_likelihood) for i in rel_likelihood]
    for r, i in zip(res, AICc_weight):
        r.append(i)
    res.sort(key=lambda x: -x[-1])
    if print_out and len(selected) > 1:
        print = print_port
        print("\n---- 分布比较 ----")
        if res:
            t = gen_table([['分布', 'AICc', 'AICc 权重', 'BIC',
                            '-2*LogLikelihood']])
            for r in res:
                t.add_row([r[0], format_stat(r[1][1]), format_stat(r[-1]),
                           format_stat(r[1][2]), format_stat(r[1][0])])
            for column in t.field_names[1:]:
                t.align[column] = 'r'
            print(StatTable(t, '分布比较', t.field_names,
                [[r[0], r[1][1], r[-1], r[1][2], r[1][0]] for r in res],
                display=[[str(v) for v in row] for row in t.rows]))
            print("排序沿用 AICc 权重降序；权重表示当前候选集合中的相对支持度，不是模型为真或必为最佳模型的概率。")
            print("AICc、BIC 在同一数据下越小越优；AD 用于检验分布相容性，不参与此处排序。")
            print("* 表示不可用的统计量；未成功拟合的分布不进入比较。")
            print("AICc 或权重为 * 时，现有排序不提供有效的优劣结论。")
        else:
            print("无法比较：没有成功拟合的候选分布。")
    return res


if __name__ == "__main__":
    data = [
        59,
        61,
        55,
        66,
        52,
        60,
        61,
        51,
        60,
        61,
        56,
        65,
        63,
        58,
        59,
        61,
        62,
        65,
        63,
        62,
        63,
        64,
        65,
        64,
        68,
        64,
        69,
        62,
        64,
        67,
        65,
        66,
        62,
        66,
        65,
        60,
        68,
        62,
        68,
        70]
    data = [1, 2, 3, 4, 2, 12, 3, 12, 3, 2, 14, 3, 2]
    fit_norm(data)
    fit_t(data)
    fit_gamma(data)
    fit_weibull(data)
    fit_lognorm(data)
    fit_jsu(data)
    fit_expon(data)
    compare_dist(data)
