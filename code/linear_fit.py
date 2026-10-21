from stat_table import StatTable
import statistics as stat
from scipy.stats import f as f_dist
from scipy.stats import t as t_dist
######## Own Module ###########
try:
    from .utilities import norm_test, gen_table, format_stat
except ImportError:
    from utilities import norm_test, gen_table, format_stat


def linear_fit(x, y, print_out=True, print_port=print):
    print = print_port
    # Source:
    # https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/regression/how-to/fitted-line-plot/methods-and-formulas/methods-and-formulas/
    x_u = stat.mean(x)
    y_u = stat.mean(y)
    n = len(x)
    if n != len(y):
        return

    # Get b1 as slope and b0 as intercept
    b1 = sum([(xi - x_u) * (yi - y_u) for xi, yi in zip(x, y)]) / sum(
        [(xi - x_u)**2 for xi in x])
    b0 = y_u - b1 * x_u

    # Fitted y response
    y_est = [b0 + b1 * xi for xi in x]
    y_est_u = stat.mean(y_est)

    # Residual
    e = [yi - ye for yi, ye in zip(y, y_est)]
    # Normality test
    ntest_e = norm_test(e)

    # sum of square regression
    SSR = sum([(ye - y_u)**2 for ye in y_est])
    # Sum of Square Error
    SSE = sum([(yi - ye)**2 for yi, ye in zip(y, y_est)])
    # Sum of Square Total
    SST = sum([(yi - y_u)**2 for yi in y])

    # Mean Square of the error
    # MSE= SSE / DF_error DF_error=n-p-1
    # where p is the num of coefficient excluding constant
    MSE = SSE / (n - 1 - 1)
#      the standard error of the estimate (s):
    S = MSE**.5
    R_sq = 1 - SSE / SST

    # R-sq is 1 - MSE/(SST/(DF total))
    # DF total is n-1
    R_sq_adj = 1 - MSE / (SST / (n - 1))

    # Adj mean square regression
    MSR = SSR / 1
    # 1 is the dfn two terms in the fit two-1=1

    # Adj Mean square total
    MST = SST / (n - 1)

    # F value
    if MSE != 0:
        F_reg = MSR / MSE
        p_reg = 1 - f_dist.cdf(F_reg, dfn=1, dfd=n - 2)
    else:
        F_reg = -1
        p_reg = 0

#     If p < 0.05 (or your chosen significance level):
# Reject the null hypothesis
# Conclude that your model provides a statistically significantly
# better fit than the intercept-only model ( which is a horizontal
# line at y mean)
# At least one of your independent variables is significantly
# related to the dependent variable
# The p-value is used to test the hypothesis that there is no
# relationship between the predictor and the response. Or,
# stated differently, the p-value is used to test the hypothesis
# that the true slope coefficient is zero.

    # Lack of fit
    # c is number of distinct x values
    x_levels = set(x)
    c = len(x_levels)
    # DF Pure Error
    DFPE = n - c
    # DF lack of fit
    DFLF = c - 2

    # SSPE = Sum of Squares for Pure Error
#     SSPE = Σ Σ (yij - y̅i)²
# Where yij is the jth y value for the ith x value,
# and y̅i is the mean y for the ith x value.
    groups = {xi: [] for xi in x_levels}
    for xi, yi in zip(x, y):
        # NaN never matched a level in the original equality-based grouping.
        if xi == xi:
            groups[xi].append(yi)
    group_means = {xi: stat.mean(values) for xi, values in groups.items() if values}
    SSPE = sum(sum((yi - group_means[xi])**2 for yi in groups[xi])
               for xi in x_levels)

    SSLF = SSE - SSPE

    # Mean square of lack of fit
    MSLF = SSLF / DFLF if DFLF > 0 else -1

    if DFLF > 0 and DFPE > 0 and SSPE != 0:
        # Mean square of Pure Error
        MSPE = SSPE / DFPE

        F_lack = MSLF / MSPE
    #     If p-value < significance level (typically 0.05):
    # Reject the null hypothesis. There is evidence of lack of fit,
    # suggesting the linear model may not be adequate. A more complex
    # model (e.g., polynomial) might be more appropriate.
        p_lack = 1 - f_dist.cdf(F_lack, dfn=DFLF, dfd=DFPE)
    else:
        MSPE = F_lack = p_lack = -1

#     Calculate sum of squares for the saturated model (SSM):
# SSM = Σni(ȳi - ȳ)², where ȳi is the mean of each group and
# ni is the number of observations in each group.
    SSM = sum(sum((y_u - group_means[xi])**2 for _ in groups[xi])
              for xi in x_levels)

    max_r_sq = SSM / SST


# Calculate the standard error of the slope (SEb1):
# SEb1 = s / sqrt(Σ(x - x_bar^2)
# Calculate the standard error of the intercept (SEb0):
# SEb0 = s * sqrt((1/n) + (x_bar^2 / Σ(x - x̄x_bar²))
# Calculate t-ratios:
# For slope: t = b1 / SEb1
# For intercept: t = b0 / SEb0

    SEb1 = S / (sum([(xi - x_u)**2 for xi in x]))**.5
    SEb0 = S * (1 / n + x_u * x_u / sum([(xi - x_u)**2 for xi in x]))**.5

# 双侧检验：各总体回归系数为零。
    if SEb1 != 0:
        slope_t = abs(b1 / SEb1)
        p_slope = (1 - t_dist.cdf(slope_t, n - 2)) * 2
    else:
        slope_t = -1
        p_slope = 0

    if SEb0 != 0:
        int_t = abs(b0 / SEb0)  # two tails test needs abs
        p_int = (1 - t_dist.cdf(int_t, n - 2)) * 2
    else:
        int_t = -1
        p_int = 1 if b0 == 0 else 0

    if print_out:
        print("\n---- 普通最小二乘线性回归 ----")
        print("响应变量：Y；预测变量：X；模型包含截距。")
        print(f"回归方程：Y = {format_stat(b0)} {b1:+.3f} * X")
        sections = [
            ('模型摘要', [['N', 'R-sq', '调整 R-sq', '残差标准误 S', '响应均值'],
                [n, R_sq, R_sq_adj, S, y_est_u]]),
            ('回归系数', [['参数', '系数', '标准误', 't 绝对值', 'p 值'],
                ['截距', b0, SEb0,
                 int_t if int_t >= 0 else '*', p_int if int_t >= 0 else '*'],
                ['X（斜率）', b1, SEb1,
                 slope_t if slope_t >= 0 else '*', p_slope if slope_t >= 0 else '*']]),
            ('方差分析（ANOVA）', [['来源', '自由度', '平方和 SS', '均方 MS', 'F 值', 'p 值'],
                ['回归', 1, SSR, MSR,
                 F_reg if F_reg >= 0 else '*', p_reg if F_reg >= 0 else '*'],
                ['误差', n - 2, SSE, MSE, '*', '*'],
                ['总计', n - 1, SST, '*', '*', '*']])]
        if p_lack >= 0:
            sections.append(('失拟检验', [['来源', '自由度', '平方和 SS', '均方 MS', 'F 值', 'p 值'],
                ['失拟', DFLF, SSLF, MSLF, F_lack, p_lack],
                ['纯误差', DFPE, SSPE, MSPE, '*', '*'],
                ['误差合计', n - 2, SSE, MSE, '*', '*']]))
        sections.append(('残差正态性诊断', [['检验方法', '统计量', 'p 值'],
            ['Shapiro-Wilk', ntest_e['shapiro s'], ntest_e['shapiro p']],
            ['Anderson-Darling', ntest_e['AD s'], ntest_e['AD p']]]))
        for title, rows in sections:
            print("\n" + title)
            display = [[cell if isinstance(cell, str) or header in ('N', '自由度')
                        else format_stat(cell) for header, cell in zip(rows[0], row)]
                       for row in rows[1:]]
            table = gen_table([rows[0]] + display)
            table.align = 'r'
            if title != '模型摘要':
                table.align[rows[0][0]] = 'l'
            print(StatTable(table, title, rows[0], rows[1:], display=[[str(v) for v in row] for row in display],
                            number_formats=['0' if h in ('N', '自由度') else '0.000' for h in rows[0]]))
        print("各项系数检验：原假设 H0：该总体回归系数 = 0；备择假设 H1：该系数 ≠ 0。")
        print("回归 F 检验：原假设 H0：总体斜率 = 0；备择假设 H1：总体斜率 ≠ 0。")
        if p_lack >= 0:
            print(f"最大 R²（重复 X 水平的饱和模型）= {format_stat(max_r_sq)}")
            print("失拟检验：原假设 H0：总体均值与自变量呈线性关系；备择假设 H1：存在失拟。")
        else:
            print("失拟检验不可用：需要足够的不同 X 水平、重复观测及非零纯误差。")
        print("残差正态性检验：原假设 H0：误差服从正态分布；备择假设 H1：误差不服从正态分布。")
        print("推断假定误差独立、方差恒定且服从正态分布；正态性检验未拒绝 H0 不等于证明正态。")
        print("R² 和调整 R² 是不同指标；拟合优度高不保证模型正确，相关关系不代表因果关系。")
        print("本方法未计算系数置信区间；* 表示不适用或无法估计（如标准误为零）。")
        print("p 值是在原假设及检验模型成立时，得到当前或更极端检验统计量的概率。")
        print("p 值显示 0.000 是舍入结果，不代表概率严格为零。")

    return {"slope": b1, "intercept": b0,
            "R Square": R_sq, "R Square Adj": R_sq_adj,
            "MSE": MSE, "Mean of Response": y_est_u,
            "N": len(x), "DF reg": 1, "DF Error": n - 2,
            "DF Total": n - 1, "SSR": SSR, "SSE": SSE,
            "SST": SST, "MSR": MSR, 
            "F Reg": F_reg, "p reg": p_reg,
            "Root MSE": S, "DFPE": DFPE,
            "DFLF": DFLF, "SSPE": SSPE,
            "SSLF": SSLF, "MSPE": MSPE,
            "MSLF": MSLF, "F lack": F_lack,
            "p lack": p_lack, "Max R Square": max_r_sq,
            "Std Error Slope": SEb1,
            "Std Error Int.": SEb0,
            "t slope": slope_t, "t int.": int_t,
            "p slope": p_slope, "p int.": p_int,
            "Normal Test Resid": ntest_e,
            "MST": MST, "Residual": e}


if __name__ == "__main__":
    # From JMP body measure fore and Bicep
    waist = [
        85.0,
        90.5,
        80.5,
        91.5,
        92.0,
        101.0,
        76.0,
        84.0,
        74.0,
        76.0,
        80.0,
        86.0,
        82.0,
        82.0,
        95.5,
        81.0,
        76.0,
        84.0,
        88.0,
        82.0,
        96.0,
        99.5]
    bicep = [
        33.5,
        36.5,
        31.0,
        34.0,
        36.5,
        38.0,
        29.0,
        31.0,
        29.0,
        31.0,
        37.0,
        33.0,
        36.0,
        30.0,
        36.0,
        32.5,
        30.0,
        28.5,
        34.5,
        34.5,
        35.5,
        33.5]
    linear_fit(waist, bicep)
