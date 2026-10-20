import numpy as np
from scipy.stats import norm
###### own modules #####
try:
    from .utilities import norm_test, gen_table, format_stat
except ImportError:
    from utilities import norm_test, gen_table, format_stat


def orthogonal_fit(x, y, error_ratio=1.0, alpha=0.05,
                   print_port=print, print_out=True,
                   print_residual=False):
    """
    Perform orthogonal regression with unequal variances.

    Parameters:
    x, y: arrays of data points
    error_ratio: ratio of error variances (var_y / var_x)
    Ratio here is the ratio of measurement variance not the
    data variance itself. So setting the ratio is 1 as default

    Returns:
    slope, intercept
    and the CI of them
    All the results are same to Minitab 20
    slope and int have same 3~4 digits with JMP, CIs are different w/JMP
    """
    print = print_port
    x_mean = np.mean(x)
    y_mean = np.mean(y)

    x_centered = x - x_mean
    y_centered = y - y_mean

    n = len(x)
    Sxx = np.sum(x_centered**2) / (n - 1)
    Syy = np.sum(y_centered**2) / (n - 1)
    Sxy = np.sum(x_centered * y_centered) / (n - 1)

    # Modified slope calculation incorporating error_ratio
    w = error_ratio
    b1 = slope = ((Syy - w * Sxx) + np.sqrt((Syy - w * Sxx)
                                            ** 2 + 4 * w * Sxy**2)) / (2 * Sxy)

    b0 = intercept = y_mean - slope * x_mean

# Confidence Intervals
#   Source: https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/regression/how-to/orthogonal-regression/methods-and-formulas/methods-and-formulas/
# The code below replicated the minitab math,
# the confidence interval outputs are not same to JMP but MiniTab 20

    # u for x, e for y
    var_u = (Syy + w * Sxx - ((Syy - w * Sxx)**2 + 4 * w * Sxy**2)**.5) / 2 / w
    var_e = w * var_u
    # above noted as est. delta ^2 u and est. delta ^2 e
    if Sxy == 0 and Syy < w * Sxx:
        var_u = Syy / w

    var_xx = (((Syy - w * Sxx)**2 + 4 * w * Sxy**2)
              ** .5 - (Syy - w * Sxx)) / 2 / w
    if Sxy == 0 and Syy < w * Sxx:
        var_xx = Sxx - Syy / w

    Svv = (n - 1) * (w + slope**2) * var_u / (n - 2)

    v_slope = (var_xx * Svv + var_u * Svv - slope **
               2 * var_u**2) / (n - 1) / var_xx**2

    z = norm.ppf(1 - alpha / 2)
    slope_l = slope - z * (v_slope)**.5
    slope_u = slope + z * (v_slope)**.5

    v_int = Svv / n + x_mean**2 * v_slope
    int_l = intercept - z * (v_int)**.5
    int_u = intercept + z * (v_int)**.5

    ######### Fitted values ############
    x_est = [(w * xt + (yt - b0) * b1) / (b1 * b1 + w)
             for xt, yt in zip(x, y)]
    y_est = [b0 + b1 * xt for xt in x_est]
    # Residuals
    vt_est = [yt - b0 - xt * b1 for xt, yt in zip(x, y)]
    ######### Std. Residuals
    std_vt_est = [vt / ((w + b1 * b1) * var_u)**.5
                  for vt in vt_est]
    # Normalitiy of the residuals
    ntest_resid = norm_test(vt_est)
#     ntest_st_resid=norm_test(std_vt_est)
# They are propotionally same values

    if print_out:
        print("\n---- 正交回归 ----")
        print("响应变量：Y；预测变量：X；X 和 Y 均存在测量误差。")
        print(f"回归方程：Y = {format_stat(b0)} {b1:+.3f} * X")
        print(f"样本量 N = {n}；测量误差方差比 Var(Y误差) / Var(X误差) = {format_stat(w)}")
        print(f"系数的 {(1-alpha)*100:.1f}% 双侧置信区间（正态近似）")
        for title, rows in [
            ('参数估计', [['参数', '系数', '置信下限', '置信上限'],
                ['截距', format_stat(b0), format_stat(int_l), format_stat(int_u)],
                ['X（斜率）', format_stat(b1), format_stat(slope_l), format_stat(slope_u)]]),
            ('测量误差方差估计', [['变量', '误差方差'],
                ['X', format_stat(var_u)], ['Y', format_stat(var_e)]])]:
            print("\n" + title)
            table = gen_table(rows)
            table.align = 'r'
            table.align[rows[0][0]] = 'l'
            print(str(table))
        print("系数置信区间用于总体截距与斜率，不是单次观测的预测区间。")
        print("本方法不报告普通最小二乘的 R²、t 检验或 ANOVA F 检验。")
        print("推断依赖所指定的测量误差方差比及模型假设；相关关系不代表因果关系。")
        print("\n残差正态性诊断（Y - 截距 - 斜率 * X）")
        print("p 值显示 0.000 是舍入结果，不代表概率严格为零。")
    # Normalitiy of the residuals
    ntest_resid = norm_test(vt_est, print_out=print_out, print_port=print_port)

    if print_residual:
        t = gen_table([['观测', 'X', '拟合 X', 'Y', '拟合 Y', '残差', '标准化残差']])
        t.align = 'r'
        for i, xx in enumerate(x):
            t.add_row([i + 1, format_stat(xx), format_stat(x_est[i]),
                       format_stat(y[i]), format_stat(y_est[i]), format_stat(vt_est[i]),
                       format_stat(std_vt_est[i])])
        print("\n逐观测诊断")
        print(str(t))

    return {"slope": slope, "intercept": intercept,
            "slope_l": slope_l, "slope_u": slope_u,
            "int_l": int_l, "int_u": int_u,
            "Fitted Y": y_est, "Fitted X": x_est,
            "Residuals": vt_est, "St Resid": std_vt_est,
            "Normal test Resid": ntest_resid,
            "Var U": var_u, "Var E": var_e}


if __name__ == "__main__":
    x = [0.27605, 0.08993, 0.23165, 0.03308, 0.36766, 0.13048, 0.78341, 0.66737, 0.64194, 3.61725,
         0.21866, 0.94511, 1.16029, 0.83957, 0.66793, 0.49791, 0.63187, 1.26930, 2.03622, 2.31915]
    y = [0.78557, 1.94455, 2.18364, 1.00715, 0.71009, 0.32651, 1.01881, 1.21348, 2.24900, -0.50332,
         1.17126, -0.01074, 1.88280, 1.39863, 0.44323, 2.01868, 1.98543, 1.39951, 0.28374, 3.26509]
    orthogonal_fit(x, y, print_residual=True, error_ratio=1.3)
