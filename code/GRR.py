import pandas as pd
import statistics as stats
from collections import Counter
from math import isfinite
from scipy.stats import f as f_dist
# ############# Own Modules ############
from utilities import d2_2D as d2
from utilities import gen_table, format_stat
from stat_table import StatTable
from two_way_anova import two_way_anova
from one_way_ANOVA import one_way_anova
from utilities import grouping_by_labels


def _grr_design(y, part, op, print_port):
    counts = Counter(zip(op if op is not None else [0] * len(y), part))
    repeats = sorted(set(counts.values()))
    print_port("研究设计：N = %d；零件数 = %d；操作者数 = %d；每个操作者-零件组合的重复次数 = %s。" %
               (len(y), len(set(part)), 1 if op is None else len(set(op)),
                ", ".join(str(n) for n in repeats)))
    if op is None:
        print_port("未提供操作者列；再现性未单独估计。")


def _grr_tables(components, total, print_port, hist_std=None, spec_gap=None, study=True):
    # 四种 GRR 方法只共用呈现；分量及总方差由各自原算法提供。
    print_port("\n方差分量")
    rows = [['来源', '方差分量', '方差贡献率 (%)']]
    values = []
    for name, variance in components:
        rows.append([name, format_stat(variance),
                     format_stat(100 * variance / total if total > 0 else None)])
        values.append([name, variance, 100 * variance / total if total > 0 else None])
    table = gen_table(rows)
    for col in table.field_names[1:]:
        table.align[col] = 'r'
    print_port(StatTable(table, '方差分量', table.field_names, values,
                         display=[[str(cell) for cell in row] for row in table.rows]))
    print_port("\n研究变异" if study else "\n分量标准差")
    rows = [['来源', '标准差 SD']]
    values = []
    if study:
        rows[0] += ['研究变异 (6 x SD)', '研究变异占比 (%)']
        if hist_std is not None:
            rows[0].append('历史过程占比 (%)')
            print_port("历史过程标准差 = " + format_stat(hist_std))
        if spec_gap is not None:
            rows[0].append('公差占比 (%)')
            print_port("规格公差 (USL - LSL) = " + format_stat(spec_gap))
    for name, variance in components:
        sd = variance**.5
        row = [name, format_stat(sd)]
        raw_row = [name, sd]
        if study:
            row += [format_stat(6 * sd), format_stat(100 * sd / total**.5 if total > 0 else None)]
            raw_row += [6 * sd, 100 * sd / total**.5 if total > 0 else None]
            if hist_std is not None:
                row.append(format_stat(100 * sd / hist_std if hist_std > 0 else None))
                raw_row.append(100 * sd / hist_std if hist_std > 0 else None)
            if spec_gap is not None:
                row.append(format_stat(600 * sd / spec_gap if spec_gap > 0 else None))
                raw_row.append(600 * sd / spec_gap if spec_gap > 0 else None)
        rows.append(row)
        values.append(raw_row)
    table = gen_table(rows)
    for col in table.field_names[1:]:
        table.align[col] = 'r'
    print_port(StatTable(table, '研究变异' if study else '分量标准差', table.field_names, values,
                         display=[[str(cell) for cell in row] for row in table.rows]))
    print_port("方差贡献率基于方差；标准差单位与输入测量值一致，方差单位为其平方。")
    if study:
        print_port("研究变异占比基于 SD / 总 SD；公差占比为 6 x SD / 规格公差，历史过程占比为 SD / 历史 SD。")
    print_port("百分比不是测量误差概率；* 表示不可估计或不适用 (not estimable)。")


def GRR_xbar(data, op_key="Operator", pt_key="Part", y_key="Y",
             hist_std=None, use_hist=False, spec_gap=None,
             print_out=True, has_op_col=True, print_port=print):

    def EV_stdev(d, op_key="Operator", pt_key="Part", y_key="Y"):
        ranges = []
        n = 0
        for op in d[op_key].unique():
            for part in d[pt_key].unique():
                tmp = d[(d[op_key] == op) & (d[pt_key] == part)]
                n = len(tmp)
                if len(tmp) > 0:
                    ranges.append(max(tmp[y_key] - min(tmp[y_key])))

        rBar = sum(ranges) / len(ranges)
        k = len(ranges)
    #     print(n,k)
    #     print(d2(n,k))
        return rBar / d2(n, k)

    def AV_stdev(d, op_key="Operator", pt_key="Part", y_key="Y"):
        num_of_parts = len(d[pt_key].unique())
        num_of_op = len(d[op_key].unique())
        num_of_tests = len(d) / num_of_parts / num_of_op

        op_avgs = []
        for op in d[op_key].unique():
            tmp = d[d[op_key] == op]
            op_avgs.append(sum(tmp[y_key]) / len(tmp))
        R0 = max(op_avgs) - min(op_avgs)
        # Negative variance components are zero, as in the ANOVA methods below.
        return max(0, (R0 / d2(num_of_op, 1))**2 - EV_stdev(d, op_key=op_key,
                                                      pt_key=pt_key, y_key=y_key
                                                      )**2 / num_of_parts / num_of_tests)**.5

    def Part2Part(d, op_key="Operator", pt_key="Part", y_key="Y"):
        part_avgs = []
        for pt in d[pt_key].unique():
            tmp = d[d[pt_key] == pt]
            part_avgs.append(sum(tmp[y_key]) / len(tmp))
        R_part = max(part_avgs) - min(part_avgs)
        return R_part / d2(len(part_avgs), 1)

    if not has_op_col:
        data.insert(1, "Operator", [0] * len(data), True)
        op_key = "Operator"

    EV = EV_stdev(data, op_key=op_key, pt_key=pt_key, y_key=y_key)
    if has_op_col:
        AV = AV_stdev(data, op_key=op_key, pt_key=pt_key, y_key=y_key)
    else:
        AV = 0
    PV = Part2Part(data, op_key=op_key, pt_key=pt_key, y_key=y_key)
    GRR = (EV**2 + AV**2)**.5
    TTL = (GRR**2 + PV**2)**.5

    if print_out:
        print = print_port
        print("\n---- 交叉型量具 R&R（均值极差法 Xbar/R） ----")
        _grr_design(data[y_key], data[pt_key], data[op_key] if has_op_col else None, print_port)
        components = [('总量具 R&R (GRR)', GRR**2), ('重复性 (EV)', EV**2)]
        if has_op_col:
            components.append(('再现性 (AV)', AV**2))
        components += [('零件间 (PV)', PV**2), ('总变异', TTL**2)]
        _grr_tables(components, TTL**2, print_port, hist_std=hist_std, spec_gap=spec_gap)
        ndc = int(PV / GRR * 2**.5) if GRR > 0 else None
        print("可区分类别数 ndc = " + (str(ndc) if ndc is not None else '*'))
        print("ndc 描述可区分的零件类别数，不是样本量。")

    res = {"EV": EV**2, "AV": AV**2, "PV": PV**2, "RR": GRR**2, "TV": TTL**2,
           "INT": 0}
    return res


def grr_xbar_r(y=None, op=None, part=None,
               hist_std=None, use_hist=False, spec_gap=None,
               print_out=False, print_port=print):
    """
    input in 1d list, op input is optional
    """

    d = {"Y": y, "Part": part}
    if op is None:
        has_op = False
    else:
        has_op = True
        d["Operator"] = op
    return GRR_xbar(pd.DataFrame(d), has_op_col=has_op,
                    hist_std=hist_std, use_hist=use_hist, spec_gap=spec_gap,
                    print_out=print_out, print_port=print_port)


def grr_inter(y, op, part, *, _anova=None):
    res = _anova
    if res is None:
        res = two_way_anova(y, factor_listA=part, factor_listB=op,
                            print_out=False)

    a = len(set(part))  # number of parts
    b = len(set(op))  # number of operators
    n = len(y) / a / b   # number of replicates
    Rept = res["MSE"]  # Repeatibility of equipment
    OP = max((res['MSB'] - res['MSAB']) / a / n, 0)  # operator variance
    OPP = max(0, (res['MSAB'] - Rept) / n)
    PP = max(0, (res['MSA'] - res['MSAB']) / b / n)  # part to part var
    return Rept, OP, OPP, PP


def grr_simple(y, op, part):
    res = two_way_anova(y, factor_listA=part, factor_listB=op,
                        interaction=False, print_out=False)

    a = len(set(part))  # number of parts
    b = len(set(op))  # number of operators
    n = len(y) / a / b   # number of replicates
    Rept = res["MSE"]  # Repeatibility of equipment
    OP = max((res['MSB'] - res['MSE']) / a / n, 0)  # operator variance
    PP = max(0, (res['MSA'] - res['MSE']) / b / n)  # part to part var
    return Rept, OP, 0, PP


def grr_no_op(y, part):
    data = grouping_by_labels(y, part)
    part_list = list(set(part))
    res = one_way_anova(data, part_list, print_out=False)
    a = len(part_list)
    n = len(y) / a
    Rept = res['MSE']
    PP = max(0, (res['MSA'] - Rept) / n)
    return Rept, 0, 0, PP


def grr_anova_EMP(y=None, op=None, part=None, inter=True,
                  print_out=False, print_port=print, *, _full_anova=None):
    if op is None:
        inter = False
        Rept, OP, OPP, PP = grr_no_op(y, part)
    else:
        Rept, OP, OPP, PP = grr_inter(y, op, part, _anova=_full_anova)
        if OPP == 0 or not inter:
            Rept, OP, OPP, PP = grr_simple(y, op, part)

    # OPP: operator x part variance, e.g. someone is bad at small parts
    Repd = OP   # reproducibility by human
    GRR = Repd + Rept  # total var introduced by human and equipment
    TTL = GRR + PP + OPP

#  Without the interaction, the analysis uses the following formula:
#  DF = (abn – 1) – (a – 1) – (b – 1)
#  With the interaction, the analysis uses the following formula:
#  DF = (abn – 1) – (a – 1) – (b – 1) – [(a – 1) × (b – 1)]

    a = len(set(part))
    b = 1 if op is None else len(set(op))
    #  n = len(y) / a / b
    DF = (len(y) - 1) - (a - 1) - (b - 1)
    if inter:
        DF = DF - (a - 1) * (b - 1)

#  Intraclass correlation (no bias)
#  Part / (Part + Test re-test error)
#  Intraclass correlation (with bias)
#  Part / (Part + Test re-test error + Operator)
#  Intraclass correlation (with bias and interaction)
#  Part / (Part + Test re-test error + Operator + Part*Operator)
#  Bias impact
#  Intraclass correlation (no bias) – Intraclass correlation (with bias)
#  Bias and interaction impact
#  Intraclass correlation (no bias) – Intraclass correlation (with bias and interaction)

    intraclass_no_bias = PP / (PP + Rept)
    intraclass_w_bias = PP / (PP + Rept + Repd)
    intraclass_bias_inter = PP / (PP + OPP + Rept + Repd)
    bias_impact = intraclass_no_bias - intraclass_w_bias
    bias_inter_impact = intraclass_no_bias - intraclass_bias_inter

    def classification(rho):
        if rho > 0.8:
            return "First"
        if rho > .5:
            return "Second"
        if rho > .2:
            return "Third"
        return "Fourth"

    if print_out:
        print = print_port
        print("\n---- 交叉型量具 R&R（EMP ANOVA 法） ----")
        _grr_design(y, part, op, print_port)
        components = [('总量具 R&R (GRR)', GRR), ('重复性 (EV)', Rept)]
        if op is not None:
            components.append(('再现性（操作者）', Repd))
        components.append(('零件间 (PV)', PP))
        if inter:
            components.append(('零件 x 操作者', OPP))
        components.append(('总变异', TTL))
        _grr_tables(components, TTL, print_port, study=False)
        print("EMP 的 GRR 为重复性与操作者分量之和；交互分量单独计入总方差。")
        print("\nEMP 补充统计")
        rows = [['统计量', '结果', '原有 EMP 分类'],
                ['自由度', str(DF), '*'],
                ['可能误差', format_stat(.674490 * Rept**.5), '*'],
                ['组内相关（无偏倚）', format_stat(intraclass_no_bias), classification(intraclass_no_bias) + ' Class']]
        values = [['自由度', DF, '*'], ['可能误差', .674490 * Rept**.5, '*'],
                  ['组内相关（无偏倚）', intraclass_no_bias, classification(intraclass_no_bias) + ' Class']]
        if op is not None:
            rows += [['组内相关（含偏倚）', format_stat(intraclass_w_bias), classification(intraclass_w_bias) + ' Class'],
                     ['偏倚影响', format_stat(bias_impact), '*']]
            values += [['组内相关（含偏倚）', intraclass_w_bias, classification(intraclass_w_bias) + ' Class'],
                       ['偏倚影响', bias_impact, '*']]
        if inter:
            rows += [['组内相关（含偏倚及交互）', format_stat(intraclass_bias_inter), classification(intraclass_bias_inter) + ' Class'],
                     ['偏倚及交互影响', format_stat(bias_inter_impact), '*']]
            values += [['组内相关（含偏倚及交互）', intraclass_bias_inter, classification(intraclass_bias_inter) + ' Class'],
                       ['偏倚及交互影响', bias_inter_impact, '*']]
        table = gen_table(rows)
        table.align['结果'] = 'r'
        print(StatTable(table, 'EMP 补充统计', table.field_names, values,
                        display=[[str(cell) for cell in row] for row in table.rows]))
        print("重测误差为重复性标准差，见分量标准差表。")
        print("\n原有 EMP 分类参考（不新增 GRR 接受阈值）")
        table = gen_table([
            ['类别', '组内相关', '过程信号衰减', '检验 1 检出概率', '检验 1/5/6/8 检出概率'],
            ['First', '0.80 - 1.00', '< 11%', '0.99 - 1.00', '1.00'],
            ['Second', '0.50 - 0.80', '11 - 29%', '0.88 - 0.99', '1.00'],
            ['Third', '0.20 - 0.50', '29 - 55%', '0.40 - 0.88', '0.92 - 1.00'],
            ['Fourth', '0.00 - 0.20', '> 55%', '0.03 - 0.40', '0.08 - 0.92']])
        for col in table.field_names[1:]:
            table.align[col] = 'r'
        print(StatTable(table, '原有 EMP 分类参考（不新增 GRR 接受阈值）',
                        table.field_names, table.rows,
                        display=[[str(cell) for cell in row] for row in table.rows]))
        print("检出概率指使用 Nelson 控制图规则，在 10 个子组内检出 3 个标准差偏移的概率，详见帮助。")

    res = {"EV": Rept, "AV": Repd, "PV": PP, "RR": GRR, "TV": TTL,
           "INT": OPP}
    return res


def grr_anova_AIAG(y=None, op=None, part=None, inter=True,
                   hist_std=None, use_hist=False, spec_gap=None,
                   print_out=False, print_port=print, *, _full_anova=None):
    if op is None:
        inter = False
        Rept, OP, OPP, PP = grr_no_op(y, part)
    else:
        Rept, OP, OPP, PP = grr_inter(y, op, part, _anova=_full_anova)
        if OPP == 0 or not inter:
            Rept, OP, OPP, PP = grr_simple(y, op, part)

    # OPP: operator x part variance, e.g. someone is bad at small parts
    Repd = OP + OPP  # reproducibility by human
    GRR = Repd + Rept  # total var introduced by human and equipment
    TTL = GRR + PP

    if print_out:
        print = print_port
        print("\n---- 交叉型量具 R&R（AIAG ANOVA 法） ----")
        _grr_design(y, part, op, print_port)
        components = [('总量具 R&R (GRR)', GRR), ('重复性 (EV)', Rept)]
        if op is not None:
            components += [('再现性 (AV)', Repd), ('操作者', OP)]
            if inter:
                components.append(('零件 x 操作者', OPP))
        components += [('零件间 (PV)', PP), ('总变异', TTL)]
        _grr_tables(components, TTL, print_port, hist_std=hist_std, spec_gap=spec_gap)
        ndc = int((2 * PP / GRR)**.5) if GRR > 0 else None
        print("可区分类别数 ndc = " + (str(ndc) if ndc is not None else '*'))
        print("再现性包含操作者及保留的交互分量；细分行不应与再现性重复相加。ndc 不是样本量。")

    res = {"EV": Rept, "AV": Repd, "PV": PP, "RR": GRR, "TV": TTL,
           "INT": OPP}
    return res


def grr_master(y=None, op=None, part=None, mode="aiag", alpha=0.05,
               hist_std=None, use_hist=False, spec_gap=None,
               inter="auto", print_out=False, print_port=print):
    mode = mode.upper()
    if "XBAR" in mode:
        return grr_xbar_r(y=y, op=op, part=part,
                          hist_std=hist_std, use_hist=use_hist, spec_gap=spec_gap,
                          print_out=print_out, print_port=print_port)

    full_anova = None
    if op is not None and inter.upper() == "AUTO":
        res = two_way_anova(y, factor_listA=part, factor_listB=op,
                            print_port=print_port, interaction=True,
                            print_out=False, name_a="Part",
                            name_b="Operator")
        full_anova = res
        inter = (res['p AB'] <= alpha)
        if print_out:
            print = print_port
            print("\n---- GRR 交互项筛选：完整模型 ANOVA ----")
            print("筛选显著性水平 alpha = " + format_stat(alpha) +
                  ("；交互项达到保留条件。" if inter else "；交互项未达到保留条件。"))
            rows = [['来源', '自由度', '平方和 SS', '均方 MS', 'F 值', 'p 值']]
            values = []
            for key, label in [('A', '零件'), ('B', '操作者'), ('AB', '零件 x 操作者')]:
                rows.append([label, res['DF ' + key], format_stat(res['SS' + key]),
                             format_stat(res['MS' + key]), format_stat(res['F ' + key]),
                             format_stat(res['p ' + key])])
                values.append([label, res['DF ' + key], res['SS' + key],
                               res['MS' + key], res['F ' + key], res['p ' + key]])
            grand_mean = stats.mean(y)
            rows += [['误差', res['N'] - 1 - res['DF A'] - res['DF B'] - res['DF AB'],
                      format_stat(res['SSE']), format_stat(res['MSE']), '*', '*'],
                     ['合计', res['N'] - 1, format_stat(sum((value - grand_mean)**2 for value in y)), '*', '*', '*']]
            values += [['误差', res['N'] - 1 - res['DF A'] - res['DF B'] - res['DF AB'],
                        res['SSE'], res['MSE'], '*', '*'],
                       ['合计', res['N'] - 1, sum((value - grand_mean)**2 for value in y), '*', '*', '*']]
            table = gen_table(rows)
            for col in table.field_names[1:]:
                table.align[col] = 'r'
            print(StatTable(table, 'GRR 交互项筛选：完整模型 ANOVA', table.field_names, values,
                            display=[[str(cell) for cell in row] for row in table.rows],
                            number_formats=['General', '0', '0.000', '0.000', '0.000', '0.000']))
            print("此表用于交互项筛选；后续分量仍按原方法及其交互项处理规则估计。")
    elif op is None:
        inter = False
    else:
        inter = (inter.upper() == "ON")

    if "EMP" in mode:
        return grr_anova_EMP(y=y, op=op, part=part, inter=inter,
                             print_out=print_out, print_port=print_port,
                             _full_anova=full_anova)
    if "AIAG" in mode:
        return grr_anova_AIAG(y=y, op=op, part=part, inter=inter,
                              hist_std=hist_std, use_hist=use_hist, spec_gap=spec_gap,
                              print_out=print_out, print_port=print_port,
                              _full_anova=full_anova)


def grr_nested(y=None, op=None, part=None, print_out=False, print_port=print,
               hist_std=None):
    if y is None or op is None or part is None or not len(y) or not (len(y) == len(op) == len(part)):
        raise ValueError("Measurements, parts and operators must have equal nonzero lengths.")
    if not all(isfinite(v) for v in y):
        raise ValueError("Measurements must be finite numbers.")
    if hist_std is not None and (not isfinite(hist_std) or hist_std <= 0):
        raise ValueError("Historical standard deviation must be finite and positive.")
    counts = Counter(part)
    b = len(set(op))
    n = next(iter(counts.values()))
    if len(set(counts.values())) != 1 or any(
            len({o for p, o in zip(part, op) if p == label}) != 1 for label in counts):
        raise ValueError("Each part must have equal replicates and belong to only one operator.")
    parts_per_op = [len({p for p, operator in zip(part, op) if operator == o}) for o in set(op)]
    if len(set(parts_per_op)) != 1:
        raise ValueError("The experiment design is not balanced.")
    a = parts_per_op[0]
    if b < 2 or a < 2 or n < 2:
        raise ValueError("Nested GRR requires at least two operators, two parts per operator and two replicates per part.")

    # calc anova table
    # https://support.minitab.com/en-us/minitab/help-and-how-to/quality-and-process-improvement/measurement-system-analysis/how-to/gage-study/nested-gage-r-r-study/methods-and-formulas/anova-table/
    # SS operator, the formulation in the webpage is inconsitant with Minitab 22 result, the one below is
    grand_mean = stats.mean(y)
    SSO = sum((stats.mean(i for i, j in zip(y, op) if j == o) - grand_mean)**2 * len([i for i, j in zip(y, op) if j == o]) for o in set(op))
    #  print(a, n, SSO)
    ## SS part by operator
    SSPO = n * sum(sum((stats.mean(i for i, k in zip(y, part) if k == p) -
                        stats.mean(i for i, j in zip(y, op) if j == o))**2 for p in set(
        [i for i, j in zip(part, op) if j == o]
    )) for o in set(op))
    # SS repeatability

    def square_sum(l):
        return sum((i - stats.mean(l))**2 for i in l)

    SSR = sum(sum(square_sum([i for i, j, k in zip(y, op, part) if j == o and k == p]) for p in set(part))
              for o in set(op))
    SST = SSR + SSPO + SSO

    #  print(SSO, SSPO, SSR)
    DFO = b - 1
    DFPO = b * (a - 1)
    DFR = a * b * (n - 1)
    DFTTL = a * b * n - 1

    MSO = SSO / DFO
    MSPO = SSPO / DFPO
    MSR = SSR / DFR

    FO = MSO / MSPO if MSPO > 0 else float('nan')
    FPO = MSPO / MSR if MSR > 0 else float('nan')

    p_o = 1 - f_dist.cdf(FO, DFO, DFPO)
    p_po = 1 - f_dist.cdf(FPO, DFPO, DFR)

    Repeatability = MSR
    Reproducibility = max(0, (MSO - MSPO) / a / n)
    GRR_var_comp = Repeatability + Reproducibility
    std_grr = GRR_var_comp**.5
    std_repeat = Repeatability**.5
    std_reproduce = Reproducibility**.5

    part_var_comp = max(0, (MSPO - MSR) / n)
    std_part = part_var_comp**.5
    hist_std_used = False
    if hist_std is not None:
        if hist_std >= std_grr:
            std_part = (hist_std**2 - GRR_var_comp)**.5
            part_var_comp = std_part**2
            hist_std_used = True

    ttl_var_comp = part_var_comp + GRR_var_comp
    std_ttl = ttl_var_comp**.5

    distinct = max(1, int(1.41 * std_part / std_grr)) if std_grr > 0 else float('nan')

    if print_out:
        print = print_port
        print("\n---- 嵌套型量具 R&R（ANOVA 法） ----")
        _grr_design(y, part, op, print_port)
        print("每名操作者的零件数 = %d；零件嵌套于操作者。" % a)
        print("\n方差分析 ANOVA")
        table = gen_table([
            ['来源', '自由度', '平方和 SS', '均方 MS', 'F 值', 'p 值'],
            ['操作者', DFO, format_stat(SSO), format_stat(MSO), format_stat(FO), format_stat(p_o)],
            ['零件（操作者内）', DFPO, format_stat(SSPO), format_stat(MSPO), format_stat(FPO), format_stat(p_po)],
            ['重复性', DFR, format_stat(SSR), format_stat(MSR), '*', '*'],
            ['合计', DFTTL, format_stat(SST), '*', '*', '*']])
        for col in table.field_names[1:]:
            table.align[col] = 'r'
        print(StatTable(table, '方差分析 ANOVA', table.field_names,
                        [['操作者', DFO, SSO, MSO, FO, p_o],
                         ['零件（操作者内）', DFPO, SSPO, MSPO, FPO, p_po],
                         ['重复性', DFR, SSR, MSR, '*', '*'],
                         ['合计', DFTTL, SST, '*', '*', '*']],
                        display=[[str(cell) for cell in row] for row in table.rows],
                        number_formats=['General', '0', '0.000', '0.000', '0.000', '0.000']))
        print("操作员 F 值 = 操作员均方 / 操作员内零件均方；零件 F 值 = 操作员内零件均方 / 误差均方。")
        print("H0：相应随机效应的方差分量为零；模型要求平衡嵌套设计、独立正态随机效应及等方差误差。")
        print("p 值显示为 0.000 是舍入结果，不代表概率严格为零。")
        components = [('总量具 R&R (GRR)', GRR_var_comp), ('重复性 (EV)', Repeatability),
                      ('再现性 (AV)', Reproducibility), ('零件间 (PV)', part_var_comp),
                      ('总变异', ttl_var_comp)]
        _grr_tables(components, ttl_var_comp, print_port)
        if hist_std is not None:
            print("历史过程标准差 = " + format_stat(hist_std))
            print("历史标准差已用于估计零件分量及总方差。" if hist_std_used else
                  "历史标准差小于 GRR 标准差，原方法未使用该历史值。")
        print("可区分类别数 ndc = " + (str(distinct) if isfinite(distinct) else '*'))
        print("ndc 描述可区分的零件类别数，不是样本量。")

    return {"Distinct Categories": distinct, "P value operator": p_o,
            "P value part": p_po, "GRR%": (100 * std_grr / std_ttl if std_ttl > 0 else float("nan")),
            "GRR STD": std_grr, "Repeatability STD": std_repeat,
            "Reproducibility STD": std_reproduce}


if __name__ == "__main__":
    c1 = ['A', 'A', 'A', 'A', 'A', 'A', 'A', 'A', 'A', 'A',
          'B', 'B', 'B', 'B', 'B', 'B', 'B', 'B', 'B', 'B',
          'C', 'C', 'C', 'C', 'C', 'C', 'C', 'C', 'C', 'C']

    c2 = [1, 1, 2, 2, 3, 3, 4, 4, 5, 5,
          1, 1, 2, 2, 3, 3, 4, 4, 5, 5,
          1, 1, 2, 2, 3, 3, 4, 4, 5, 5]

    c3 = [167, 162, 210, 213, 187, 183, 189, 196, 156, 147,
          155, 157, 206, 199, 182, 179, 184, 178, 143, 142,
          152, 155, 206, 203, 180, 181, 180, 182, 146, 154]
    grr_anova_EMP(y=c3, op=c1, part=c2, print_out=True)
    grr_anova_EMP(y=c3[:-10], op=c1[:-10], part=c2[:-10], print_out=True)
    #  print(c2[:-10])
    grr_anova_AIAG(y=c3, op=c1, part=c2, print_out=True)
    grr_anova_AIAG(y=c3[:-10], op=c1[:-10], part=c2[:-10], print_out=True)
    grr_anova_EMP(y=c3, part=c2, print_out=True)
    grr_master(y=c3, part=c2, print_out=True, mode="xbar")
    grr_master(y=c3, part=c2, print_out=True, mode="aiag")
    grr_xbar_r(y=c3, op=c1, part=c2, print_out=True)
    grr_master(y=c3, part=c2, op=c1, print_out=True, mode="aiag", inter=False)
    Part = [
        5, 4, 7, 7, 2, 3, 6, 10, 1, 1, 10, 6, 8, 2, 8, 3, 9, 9, 5, 4,
        16, 13, 20, 20, 13, 15, 11, 14, 12, 19, 11, 16, 19, 12, 18, 18, 17, 14, 17, 15,
        21, 23, 22, 26, 21, 23, 30, 24, 25, 28, 26, 22, 24, 27, 29, 28, 25, 29, 27, 30
    ]
    Operator = [
        3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3,
        2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
        1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1
    ]
    Response = [
        120.78, 121.55, 121.33, 121.99, 118.14, 119.35, 122.87, 121.00, 118.03, 117.92, 121.11, 122.87, 119.68, 117.70, 119.90, 119.57, 120.12, 119.68, 120.67, 121.00,
        121.33, 119.68, 120.12, 119.68, 119.24, 115.94, 122.21, 119.90, 119.24, 118.58, 121.88, 121.33, 118.69, 119.46, 119.13, 119.02, 121.33, 120.89, 121.00, 116.49,
        117.92, 121.11, 122.87, 119.68, 117.70, 119.90, 119.57, 120.12, 119.68, 120.67, 121.00, 122.43, 119.68, 117.37, 121.55, 120.56, 119.24, 121.33, 118.03, 118.47
    ]
    #  print([i for i,j,k in zip(Response, Operator, Part) if j==1 and k
    grr_nested(y=Response, op=Operator, part=Part, print_out=True, hist_std=0.5393)
