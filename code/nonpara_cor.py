from stat_table import StatTable
import numpy as np
from scipy import stats
from scipy.stats import rankdata
from utilities import gen_table, format_stat


def print_correlation(method, n, coefficient, p, print_port):
    print_port(f'\n---- {method} 相关分析 ----')
    table = gen_table([['变量组合', '方法', 'N', '相关系数', 'p 值'],
                       ['X / Y', method, n, format_stat(coefficient), format_stat(p)]])
    table.align = 'r'
    table.align['变量组合'] = table.align['方法'] = 'l'
    print_port(StatTable(table, method + ' 相关分析', table.field_names,
        [['X / Y', method, n, coefficient, p]], display=[[str(v) for v in row] for row in table.rows]))


def spearman(x, y, print_out=False, print_port=print):
    x = np.array(x, dtype=float)
    y = np.array(y, dtype=float)
    spearman_result = stats.spearmanr(x, y)
    if print_out:
        print = print_port
        print_correlation('Spearman', len(x), spearman_result.correlation,
                          spearman_result.pvalue, print_port)
        print("原假设 H0：总体 Spearman 秩相关系数 ρs = 0；备择假设 H1：ρs ≠ 0。秩相关系数为零不等同于变量独立。")
    return {"cor": spearman_result.correlation, "p": spearman_result.pvalue}


def kendall(x, y, print_out=False, print_port=print):
    x = np.array(x, dtype=float)
    y = np.array(y, dtype=float)
    # Kendall
    kendall_result = stats.kendalltau(x, y)
    if print_out:
        print = print_port
        print_correlation('Kendall', len(x), kendall_result.correlation,
                          kendall_result.pvalue, print_port)
        print("原假设 H0：总体 Kendall 秩相关系数 τ = 0；备择假设 H1：τ ≠ 0。秩相关系数为零不等同于变量独立。")
    return {"cor": kendall_result.correlation, "p": kendall_result.pvalue}


#  def pearson_correlation(x, y, alpha=0.05, print_out=True, print_port=print):

def hoeffd_example(X, Y):
    """Return Hoeffding's D on the scale where perfect untied agreement is 1."""
    # Hoeffding (1948), doi:10.1214/aoms/1177730150.
    x_rank = rankdata(np.asarray(X, dtype=float))
    y_rank = rankdata(np.asarray(Y, dtype=float))
    n = len(x_rank)

    # Midrank comparison weights: 1 below the point, 1/2 at a tie, 0 above.
    # Remove the point's own 1/4 contribution from the joint count.
    joint = np.empty(n)
    for i, x in enumerate(x_rank):
        y = y_rank[i]
        x_weight = (x_rank < x) + 0.5 * (x_rank == x)
        y_weight = (y_rank < y) + 0.5 * (y_rank == y)
        joint[i] = np.sum(x_weight * y_weight) - 0.25

    pairs = sum(joint * (joint - 1))
    marginals = sum((x_rank - 1) * (x_rank - 2) * (y_rank - 1) * (y_rank - 2))
    mixed = sum((x_rank - 2) * (y_rank - 2) * joint)
    scale = n * (n - 1) * (n - 2) * (n - 3) * (n - 4)
    return 30 * (marginals + (n - 2) * ((n - 3) * pairs - 2 * mixed)) / scale


def phoeffd(D, n):
    # Scalar Python adaptation of Hmisc R/hoeffd.s (GPL-2.0-or-later).
    # Frank E Harrell Jr and contributors. Verified reference: Hmisc 5.1-3,
    # CRAN mirror commit 1dd1751850d080156ac8152ec6de54f049dff659.

    # Ensure inputs are floats
    d = float(D) / 30
    n = float(n)

    # Calculate b and z
    b = d + 1 / (36 * n)
    z = 0.5 * (np.pi ** 4) * n * b
    #  print(b, z)

    # Handle NaN values
    if np.isnan(z):
        z = 1e50  # Set to a large value if z is NaN

    # Define tabvals as in the R code
    tabvals = np.array([
        5297, 4918, 4565, 4236, 3930,
        3648, 3387, 3146, 2924, 2719,
        2530, 2355, 2194, 2045, 1908,
        1781, 1663, 1554, 1453, 1359,
        1273, 1192, 1117, 1047, 982,
        921, 864, 812, 762, 716,
        673, 633, 595, 560, 527,
        496, 467, 440, 414, 390,
        368, 347, 327, 308, 291,
        274, 259, 244, 230, 217,
        205, 194, 183, 173, 163,
        154, 145, 137, 130, 123,
        116, 110, 104, 98, 93,
        87, 83, 78, 74, 70,
        66, 63, 59, 56, 53,
        50, 47, 45, 42, 25,
        14, 8, 5, 3, 2,
        1
    ]) / 10000

    # Calculate P based on the conditions
    if z < 1.1 or z > 8.5:
        P = max(1e-8, min(1.0, np.exp(0.3885037 - (1.164879 * z))))
    else:
        # Interpolation for z in [1.1,8.5]
        x_values = np.concatenate((np.arange(1.1, 5.05, .05), np.arange(5.5, 8.55, .5)))

        # Interpolating using numpy's interpolation
        P = np.interp(z, x_values, tabvals)

    return P


def hoeffding(x, y, print_out=False, print_port=print):
    D = hoeffd_example(x, y)
    p = phoeffd(D, len(x))
    if print_out:
        print = print_port
        print_correlation("Hoeffding's D", len(x), D, p, print_port)
        print("原假设 H0：两变量独立；备择假设 H1：两变量不独立。")
        #  print("
    return {"cor": D, "p": p}


if __name__ == "__main__":
    l1 = [0.276054974090457, 0.0899289063522398, 0.231651196339091, 0.0330764279084449, 0.367658351155205, 0.130477153153308, 0.783413726366693, 0.667374723260036, 0.641938575216257, 3.61724714184063, 0.218655991783686, 0.945107232675843, 1.16028890958127, 0.839573829832848, 0.667927943621081, 0.497905771893942, 0.63186521899019, 1.2693032394988, 2.03622385034504, 2.31914810376975]
    l2 = [2.0, 1.0, 3.0, 1.0, 24.0, 5.0, 3.0, 10.0, 4.0, 3.0, 2.0, 12.0, 4.0, 3.0, 23.0, 1.0, 23.0, 2.0, 12.0, 3.0]
    spearman(l1, l2, print_out=True)
    kendall(l1, l2, print_out=True)
    hoeffding(l1, l2, print_out=True)
