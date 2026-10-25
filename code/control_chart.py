import numpy as np
import matplotlib.pyplot as plt
import statistics as stat
from chart_style import style_axes
from stat_table import StatTable
####### Own modules ##########
try: 
    from .ctrl_chart_const import df as Ctrl_Cht_Const
    from .utilities import add_Y_refs, gen_table, c4_values
except ImportError:
    from ctrl_chart_const import df as Ctrl_Cht_Const
    from utilities import add_Y_refs, gen_table, c4_values


def x_mR(x, mr, k=3, sigma=None, mean=None):  # , print_out=True, xLabels=None,max_xlabels=25):

    # Define list variable for moving ranges
    MR = [np.nan] * (mr - 1)
    for i in range(mr - 1, len(x)):
        l = x[i - mr + 1:i + 1]
        MR.append(max(l) - min(l))

    x_bar = stat.mean(x) if mean is None else mean
    #  xbar_bar = stat.mean([j for l in data for j in l]) if mean is None else mean
    R_bar = stat.mean(MR[(mr - 1):])
    if sigma is None:
        sigma = R_bar / Ctrl_Cht_Const["d2"][mr]
    x_UCL = x_bar + k * sigma
    x_LCL = x_bar - k * sigma

    R_UCL = Ctrl_Cht_Const["d2"][mr] * sigma + k * sigma * Ctrl_Cht_Const['d3'][mr]
    R_LCL = max(0, Ctrl_Cht_Const['d2'][mr] * sigma - k * sigma * Ctrl_Cht_Const['d3'][mr])
    #  R_UCL = D4 * R_bar
    #  R_LCL = 0
    x1 = list(range(len(x)))
    #  x2 = x1  # list(range(1, len(x)))
    return {"Y1": x, "Y2": MR, "bar1": x_bar, "ucl1": x_UCL,
            "ucl2": R_UCL, "lcl1": x_LCL, "lcl2": R_LCL,
            "bar2": R_bar, "n": 2, "X": x1,  # "X2": x2,
            "ylabel1": "Individual Values",
            "ylabel2": "Moving Range (n=%d)" % mr}


# the number of samples each day need be consistent over time
# It's a sampling process not all the products each day.
# otherwise can't estimate an A2 value for UCL and LCL

def xBar_R(data,
           k=3, mean=None, sigma=None, pooled=False):  # , print_out=True, max_xlabels=25,xLabels=None):

    xbar = [stat.mean(l) for l in data]
    R = [max(l) - min(l) for l in data]
    n = [len(l) for l in data]
    #  A2 = Ctrl_Cht_Const["A2"][n]
    if sigma is None:
        if pooled:
            sp = (sum(sum((i - stat.mean(l))**2 for i in l) for l in data) / sum(_-1 for _ in n))**.5
            sigma = sp / c4_values(sum(_-1 for _ in n))
        else:
            sigma = sum(Ctrl_Cht_Const['d2'][_] * r / Ctrl_Cht_Const['d3'][_]**2 for r, _ in zip(R, n)) / sum((Ctrl_Cht_Const['d2'][_] / Ctrl_Cht_Const['d3'][_])**2 for _ in n)

    #  R_bar = stat.mean(R)
    xbar_bar = stat.mean([j for l in data for j in l]) if mean is None else mean
    xbar_ucl = [xbar_bar + k * sigma / (_)**.5 for _ in n]
    xbar_lcl = [xbar_bar - k * sigma / (_)**.5 for _ in n]
    #  xbar_lcl = xbar_bar - A2 * R_bar
    #  D4 = Ctrl_Cht_Const["D4"][n]
    #  D3 = Ctrl_Cht_Const["D3"][n]
    #  R_UCL = D4 * R_bar
    #  R_LCL = D3 * R_bar
    R_bar = [Ctrl_Cht_Const['d2'][ni] * sigma for ni in n]
    R_UCL = [Ctrl_Cht_Const["d2"][mr] * sigma + k * sigma * Ctrl_Cht_Const['d3'][mr] for mr in n]
    R_LCL = [max(0, Ctrl_Cht_Const['d2'][mr] * sigma - k * sigma * Ctrl_Cht_Const['d3'][mr]) for mr in n]

    return {"Y1": xbar, "Y2": R, "bar1": xbar_bar, "ucl1": xbar_ucl,
            "ucl2": R_UCL, "lcl1": xbar_lcl, "lcl2": R_LCL, "n": n,
            "bar2": R_bar, "ylabel1": "X Bar", "ylabel2": "Range",
            "X": list(range(len(data)))}


def xBar_S(data,  # , print_out=True, max_xlabels=25,xLabels=None):
           k=3, mean=None, sigma=None, pooled=False):  # , print_out=True, max_xlabels=25,xLabels=None):

    xbar = [stat.mean(l) for l in data]
    S = [stat.stdev(l) for l in data]
    #  S_bar = stat.mean(S)
    n = [len(l) for l in data]
    #  A2 = Ctrl_Cht_Const["A2"][n]

    unbiased = True
    if sigma is None:
        if pooled:
            sp = (sum(sum((i - stat.mean(l))**2 for i in l) for l in data) / sum(_-1 for _ in n))**.5
            sigma = sp / c4_values(sum(_-1 for _ in n))
        else:
            h = [c4_values(_)**2 / (1 - c4_values(_)**2) for _ in n]
            sigma = sum(hi * si / c4_values(ni) for hi, si, ni in zip(h, S, n)) / sum(h)
    else:
        unbiased = False

    #  xbar_bar = stat.mean(xbar) if mean is None else mean
    xbar_bar = stat.mean([j for l in data for j in l]) if mean is None else mean
    xbar_ucl = [xbar_bar + k * sigma / (_)**.5 for _ in n]
    xbar_lcl = [xbar_bar - k * sigma / (_)**.5 for _ in n]
    #  A3 = Ctrl_Cht_Const["A3"][n]
    #  xbar_bar = stat.mean(xbar)
    #  xbar_ucl = xbar_bar + A3 * S_bar
    #  xbar_lcl = xbar_bar - A3 * S_bar
    #  B4 = Ctrl_Cht_Const["B4"][n]
    #  B3 = Ctrl_Cht_Const["B3"][n]
    #  S_UCL = B4 * S_bar
    #  S_LCL = B3 * S_bar

    def c5(n):
        return (1 - c4_values(n)**2)**.5

    if unbiased:
        S_bar = [c4_values(ni) * sigma for ni in n]
        S_LCL = [max(0, c4_values(ni) * sigma - k * sigma * c5(ni)) for ni in n]
        S_UCL = [c4_values(ni) * sigma + k * sigma * c5(ni) for ni in n]
    else:
        S_bar = sigma
        S_LCL = [max(0, sigma * (1 - k * c5(ni) / c4_values(ni))) for ni in n]
        S_UCL = [sigma * (1 + k * c5(ni) / c4_values(ni)) for ni in n]

    return {"Y1": xbar, "Y2": S, "bar1": xbar_bar, "ucl1": xbar_ucl,
            "ucl2": S_UCL, "lcl1": xbar_lcl, "lcl2": S_LCL, "n": n,
            "bar2": S_bar, "ylabel1": "X Bar", "ylabel2": "Std Dev",
            "X": list(range(len(data)))}


def limit_line(ax, y, color='black', **kwargs):
    if isinstance(y, (list)):
        if len(set(y)) == 1:
            y = y[0]
    if isinstance(y, (int, float)):
        ax.axhline(y, color=color, **kwargs)
        value = y
    elif isinstance(y, (list)):
        xs = [-.5]
        for _ in range(len(y)):
            xs.append(xs[-1] + 1)
            xs.append(xs[-1])
        xs = xs[:-1]
        xs[0] += 0.5
        xs[-1] -= 0.5

        ys = []
        for _ in y:
            ys.append(_)
            ys.append(_)
        ax.plot(xs, ys, color=color, **kwargs)
        value = ys[-1]
    else:
        return
    name = kwargs.get("label", "")
    if name:
        ax.annotate(name + " = %.2f" % value,
                    xy=(1, value), xycoords=ax.get_yaxis_transform(),
                    xytext=(4, 0), textcoords="offset points",
                    va="center", color=color)
    return


def additional_SD(ax, sd, cl, ucl=None):
    if ucl is None:
        if isinstance(sd, (int, float)) and isinstance(cl, (int, float)):
            limit_line(ax, cl + (sd - cl) / 3 * 2, color='gray', linestyle='dotted')
            limit_line(ax, cl + (sd - cl) / 3, color='gray', linestyle='dotted')
        else:
            if isinstance(sd, list):
                n = len(sd)
            else:
                n = len(cl)
            if not isinstance(sd, list):
                sd = [sd] * n
            if not isinstance(cl, list):
                cl = [cl] * n
            limit_line(ax, [cli + (sdi - cli) / 3 * 2 for cli, sdi in zip(cl, sd)], color='gray', linestyle='dotted')
            limit_line(ax, [cli + (sdi - cli) / 3 for cli, sdi in zip(cl, sd)], color='gray', linestyle='dotted')
    else:
        if isinstance(ucl, (int, float)) and isinstance(cl, (int, float)):
            limit_line(ax, max(0, cl - (ucl - cl) / 3 * 2), color='gray', linestyle='dotted')
            limit_line(ax, max(0, cl - (ucl - cl) / 3), color='gray', linestyle='dotted')
        else:
            if isinstance(ucl, list):
                n = len(ucl)
            else:
                n = len(cl)
            if not isinstance(ucl, list):
                ucl = [ucl] * n
            if not isinstance(cl, list):
                cl = [cl] * n
            limit_line(ax, [max(0, cli - (sdi - cli) / 3 * 2) for cli, sdi in zip(cl, ucl)], color='gray', linestyle='dotted')
            limit_line(ax, [max(0, cli - (sdi - cli) / 3)for cli, sdi in zip(cl, ucl)], color='gray', linestyle='dotted')

    return


def _at_limit(value, index, default=None):
    if isinstance(value, (list, tuple, np.ndarray)):
        return value[index] if index < len(value) else default
    return value


def _finite_runs(values):
    valid = np.isfinite(np.asarray(values, dtype=float))
    runs, start = [], None
    for i, ok in enumerate(valid):
        if ok and start is None:
            start = i
        elif not ok and start is not None:
            runs.append((start, i - 1))
            start = None
    if start is not None:
        runs.append((start, len(valid) - 1))
    return runs


def _panel_events(values, center, lower, upper, labels, scale,
                  use_rules=True, panel=''):
    """返回实际绘图点的异常记录；主图用 Nelson，极差类图只判越限。"""
    from advanced_spc import NELSON, nelson_events

    values = np.asarray(values, dtype=float)
    events = []
    if use_rules:
        z = np.full(len(values), np.nan)
        for i, value in enumerate(values):
            center_i, scale_i = _at_limit(center, i), _at_limit(scale, i)
            if (np.isfinite(value) and np.isfinite(center_i)
                    and np.isfinite(scale_i) and scale_i > 0):
                z[i] = (value - center_i) / scale_i
        for start, end in _finite_runs(z):
            for point, rule, window in nelson_events(z[start:end + 1]):
                i = start + point
                events.append({
                    'panel': panel, 'x': i, 'point': i + 1,
                    'label': labels[i] if labels is not None and i < len(labels) else i + 1,
                    'value': values[i], 'lower': _at_limit(lower, i),
                    'center': _at_limit(center, i), 'upper': _at_limit(upper, i),
                    'rule': 'Nelson %d' % rule, 'description': NELSON[rule],
                    'window_start': start + window + 1, 'window_end': i + 1})
    else:
        for i, value in enumerate(values):
            if not np.isfinite(value):
                continue
            lo, hi = _at_limit(lower, i), _at_limit(upper, i)
            if (np.isfinite(lo) and value < lo) or (np.isfinite(hi) and value > hi):
                events.append({
                    'panel': panel, 'x': i, 'point': i + 1,
                    'label': labels[i] if labels is not None and i < len(labels) else i + 1,
                    'value': value, 'lower': lo, 'center': _at_limit(center, i),
                    'upper': hi, 'rule': '越限', 'description': '超出控制限',
                    'window_start': i + 1, 'window_end': i + 1})
    return sorted(events, key=lambda event: (event['x'], event['rule']))


def _mark_events(ax, events, panel):
    points = {}
    for event in events:
        if event['panel'] == panel and np.isfinite(event['value']):
            points[event['x']] = event['value']
    if points:
        ax.scatter(list(points), list(points.values()), marker='x', s=48,
                   color='#c62828', linewidths=1.6, zorder=5)


def _x_plot_anomalies(s, chart_two_only, one_chart, limits, labels, k):
    """按实际绘图限计算判定尺度，使调用方覆盖限时也与图上数值一致。"""
    lcl1, bar1, ucl1, lcl2, bar2, ucl2 = limits
    anomalies = []

    def scales(center, upper, values):
        if k == 0 or upper is None or center is None:
            return [np.nan] * len(values)
        result = []
        for i, _ in enumerate(values):
            center_i, upper_i = _at_limit(center, i), _at_limit(upper, i)
            result.append((upper_i - center_i) / k
                          if np.isfinite(center_i) and np.isfinite(upper_i) else np.nan)
        return result

    if not chart_two_only:
        scale = scales(bar1, ucl1, s['Y1'])
        anomalies += _panel_events(s['Y1'], bar1, lcl1, ucl1, labels, scale,
                                   panel='I' if not isinstance(s['n'], list) else 'Xbar')
    if not one_chart:
        scale = scales(bar2, ucl2, s['Y2'])
        name = 'MR' if not isinstance(s['n'], list) else ('R' if s['ylabel2'] == 'Range' else 'S')
        anomalies += _panel_events(s['Y2'], bar2, lcl2, ucl2, labels, scale,
                                   use_rules=False, panel=name)
    return anomalies


def _print_spc_report(title, charts, sizes, size_label, labels, notes, print_port,
                      anomalies=None):
    """只呈现调用方已有的统计量和实际使用的控制限，不执行异常判定。"""
    def at(value, index, missing=None):
        if isinstance(value, (list, tuple, np.ndarray)):
            return value[index] if index < len(value) else missing
        return value

    def number(value):
        return '*' if value is None or np.isnan(value) else '%.6g' % value

    def limit_summary(value):
        value = raw_summary(value)
        return value if isinstance(value, str) else number(value)

    def raw_summary(value):
        if isinstance(value, (list, tuple, np.ndarray)):
            if not all(item == value[0] or (np.isnan(item) and np.isnan(value[0])) for item in value):
                return '逐点变化（见明细）'
            return value[0]
        return value

    print_port('\n---- SPC 控制图报告：%s ----' % title)
    if not charts:
        print_port('未选择可报告的图表。')
        return
    print_port('\n控制图信息')
    print_port('点数/子组数：%d；%s：%s' % (
        len(charts[0][1]), size_label, limit_summary(sizes)))
    for note in notes:
        print_port(note)
    print_port('\n控制限汇总')
    table = gen_table([['图表', 'LCL', 'CL', 'UCL']] + [
        [name, limit_summary(lcl), limit_summary(cl), limit_summary(ucl)]
        for name, values, lcl, cl, ucl in charts])
    for column in ['LCL', 'CL', 'UCL']:
        table.align[column] = 'r'
    print_port(StatTable(table, '控制限汇总', table.field_names,
                         [[name, raw_summary(lcl), raw_summary(cl), raw_summary(ucl)]
                          for name, values, lcl, cl, ucl in charts], display=table.rows,
                         number_formats=['General', '0.00000E+00', '0.00000E+00', '0.00000E+00']))
    print_port('LCL = 下控制限；CL = 中心线；UCL = 上控制限。控制限不是产品规格限。')
    print_port('\n过程统计摘要与逐点明细')
    for name, values, lcl, cl, ucl in charts:
        print_port(name)
        # 与 limit_line 一样将常量列表视为水平线，每张图只归并一次。
        lcl, cl, ucl = [value[0] if isinstance(value, (list, tuple, np.ndarray))
                       and len(set(value)) == 1 else value for value in (lcl, cl, ucl)]
        rows = [[i + 1, labels[i] if labels is not None and i < len(labels) else '*',
                 at(sizes, i), value, at(lcl, i), at(cl, i), at(ucl, i)]
                for i, value in enumerate(values)]
        shown = [[number(item) for item in value] if isinstance(value, (list, tuple, np.ndarray))
                 else number(value) for value in (sizes, lcl, cl, ucl)]
        display = [[str(row[0]), str(row[1]), at(shown[0], i, '*'), number(row[3]),
                    at(shown[1], i, '*'), at(shown[2], i, '*'), at(shown[3], i, '*')]
                   for i, row in enumerate(rows)]
        table = gen_table([['点号', '子组/时间标识', size_label, '统计值', 'LCL', 'CL', 'UCL']])
        for raw, shown_row in zip(rows, display):
            table.add_row(raw[:2] + shown_row[2:])
        for column in ['点号', size_label, '统计值', 'LCL', 'CL', 'UCL']:
            table.align[column] = 'r'
        print_port(StatTable(table, name, table.field_names,
                             rows, display=display,
                             number_formats=['0', 'General', '0.######'] + ['0.00000E+00'] * 4))
    print_port('* 表示缺失、未提供或不适用；点号从 1 开始，按本次输入顺序列示。')
    print_port('\n特殊原因及异常点')
    if anomalies is None:
        print_port('当前实现未执行特殊原因规则判定，未提供异常点索引或规则明细。')
    else:
        points = {(event['panel'], event['point']) for event in anomalies}
        print_port('已检查特殊原因规则；共发现 %d 条规则记录，涉及 %d 个点。'
                   % (len(anomalies), len(points)))
        if anomalies:
            rows = [[event['panel'], event['point'], event['label'], event['value'],
                     event['lower'], event['center'], event['upper'], event['rule'],
                     event['description'], '%d-%d' % (event['window_start'], event['window_end'])]
                    for event in anomalies]
            table = gen_table([['图表', '点号', '来源标识', '统计值', 'LCL', 'CL',
                                'UCL', '触发规则', '规则说明', '窗口点号']])
            for row in rows:
                table.add_row(row)
            for column in ['点号', '统计值', 'LCL', 'CL', 'UCL']:
                table.align[column] = 'r'
            # 来源标识可能是批次名、时间或中文阶段名，按文本输出。
            display = [[str(row[0]), str(row[1]), str(row[2]), number(row[3]),
                        number(row[4]), number(row[5]), number(row[6]), str(row[7]),
                        str(row[8]), str(row[9])] for row in rows]
            print_port(StatTable(table, '异常点记录', table.field_names, rows,
                                 display=display,
                                 number_formats=['General', '0', 'General']
                                 + ['0.00000E+00'] * 4 + ['General'] * 3))
            print_port('规则说明：')
            for rule, description in sorted({(event['rule'], event['description'])
                                             for event in anomalies}):
                print_port('  %s：%s' % (rule, description))
            print_port('Nelson 规则作用于标准化统计量；极差类图只判定控制限越界。'
                       '重叠窗口和多项规则同时命中不等同于彼此独立的异常事件。')
        else:
            print_port('未发现异常点。')
            print_port('主图按所选 Nelson 规则检查；极差类图检查是否超出控制限。')
    print_port('\n结论说明')
    print_port('本报告仅汇总统计量与控制限，不能据此认定过程受控或满足产品规格。')


def x_plot(data, bar1=None, pooled=False,
           mean=None, k=3, sigma=None,
           all_SD_lines=True,
           ucl1=None, lcl1=None, bar2=None,
           ucl2=None, lcl2=None, xLabels=None,
           print_out=False, max_label_num=25,
           ylabel1=None, ylabel2=None,
           xlabel=None, ax=None, print_port=print,
           axs=None, fig=None, refY1=None, refY2=None,
           one_chart=False, show_plot=False,
           chart_two_only=False, mr_range=2,
           filename=None, plot_type="x_mR", detect_rules=False):

    plot_type = plot_type.upper()
    if "BAR" in plot_type and "R" in plot_type.replace("BAR", ""):
        s = xBar_R(data, pooled=pooled, mean=mean, sigma=sigma, k=k)
    elif "BAR" in plot_type and "S" in plot_type:
        s = xBar_S(data, pooled=pooled, mean=mean, sigma=sigma, k=k)
    else:
        if mr_range > len(data) or mr_range < 2:
            mr_range = 2
        s = x_mR(data, mr_range, mean=mean, sigma=sigma, k=k)

    bar1 = bar1 if bar1 is not None else s["bar1"]
    bar2 = bar2 if bar2 is not None else s["bar2"]
    ucl1 = ucl1 if ucl1 is not None else s["ucl1"]
    ucl2 = ucl2 if ucl2 is not None else s["ucl2"]
    lcl1 = lcl1 if lcl1 is not None else s["lcl1"]
    lcl2 = lcl2 if lcl2 is not None else s["lcl2"]
    ylabel1 = ylabel1 if ylabel1 is not None else s["ylabel1"]
    ylabel2 = ylabel2 if ylabel2 is not None else s["ylabel2"]
    n = s["n"]

    if ax is not None:
        #  one_chart = True
        axs = [ax, ax]
    elif one_chart:
        fig, ax = plt.subplots(1, layout='constrained')  # , figsize=(15, 15))
        axs = [ax, ax]
    else:
        if fig is None or axs is None:
            # , figsize=(15, 15), sharex=True)
            fig, axs = plt.subplots(2, layout='constrained')

    min_x = min(s["X"]) - (max(s["X"]) - min(s["X"])) * 0.05
    max_x = max(s["X"]) + (max(s["X"]) - min(s["X"])) * 0.05
    if not chart_two_only:
        axs[0].plot(s["X"], s["Y1"], linestyle='-', marker='o', color='black',
                    linewidth=1, markersize=3)
        #  axs[0].axhline(bar1, color='blue')
        #  axs[0].axhline(ucl1, color='red', linestyle='dashed')
        #  axs[0].axhline(lcl1, color='red', linestyle='dashed')
        limit_line(axs[0], bar1, color='blue', label='CL')
        limit_line(axs[0], ucl1, color='red', linestyle='dashed', label='UCL')
        limit_line(axs[0], lcl1, color='red', linestyle='dashed', label='LCL')
        if all_SD_lines:
            additional_SD(axs[0], ucl1, bar1)
            additional_SD(axs[0], lcl1, bar1)
        add_Y_refs(ax=axs[0], y_values=refY1, label=True)
        axs[0].set(ylabel=ylabel1)
        axs[0].set_xlim(left=min_x, right=max_x)

    if not one_chart:
        axs[1].plot(s["X"], s["Y2"], linestyle='-', marker='o', color='black',
                    linewidth=1, markersize=3)
        #  axs[1].axhline(bar2, color='blue')
        #  axs[1].axhline(ucl2, color='red', linestyle='dashed')
        #  axs[1].axhline(lcl2, color='red', linestyle='dashed')
        limit_line(axs[1], bar2, color='blue', label='CL')
        limit_line(axs[1], ucl2, color='red', linestyle='dashed', label='UCL')
        limit_line(axs[1], lcl2, color='red', linestyle='dashed', label='LCL')
        if all_SD_lines:
            additional_SD(axs[1], ucl2, bar2)
            additional_SD(axs[1], lcl2, bar2, ucl=ucl2)
        axs[1].set_ylim(bottom=0)
        add_Y_refs(ax=axs[1], y_values=refY2, label=True)
        axs[1].set(ylabel=ylabel2)
        axs[1].set_xlim(left=min_x, right=max_x)

    if not one_chart and axs[0] is not axs[1]:
        axs[0].tick_params(axis="x", labelbottom=False)

    if xLabels is not None:
        step = 1
        if len(xLabels) > max_label_num:
            step = len(xLabels) / max_label_num
            if step > int(step):
                step = int(step) + 1
            else:
                step = int(step)
        axs[1].set_xticks(range(len(xLabels)), xLabels,
                          rotation='vertical')
        axs[1].set_xticks(axs[1].get_xticks()[::step])

    if xlabel is not None:
        axs[1].set(xlabel=xlabel)

    for axis in dict.fromkeys(axs):
        style_axes(axis)

    if show_plot:
        plt.show()

    if filename is not None:
        fname = str(filename) + '.png'
        axs[0].figure.savefig(
            fname,
            dpi=200,
            format='png', bbox_inches='tight')

    if print_out:
        anomalies = None
        if detect_rules:
            limits = (lcl1, bar1, ucl1, lcl2, bar2, ucl2)
            anomalies = _x_plot_anomalies(s, chart_two_only, one_chart, limits,
                                          xLabels, k)
            if not chart_two_only:
                _mark_events(axs[0], anomalies,
                             'I' if not isinstance(n, list) else 'Xbar')
            if not one_chart:
                _mark_events(axs[1], anomalies,
                             'MR' if not isinstance(n, list) else
                             ('R' if s['ylabel2'] == 'Range' else 'S'))
        if isinstance(n, list):
            is_range = s['ylabel2'] == 'Range'
            title = 'Xbar-R' if is_range else 'Xbar-S'
            name1, name2 = 'Xbar 图（子组均值）', 'R 图（子组极差）' if is_range else 'S 图（子组标准差）'
            sizes = n
            notes = ['观测总数：%d' % sum(n),
                     '过程标准差来源：' + ('指定 sigma = %.6g' % sigma if sigma is not None else
                     ('合并标准差估计' if pooled else '子组极差估计' if is_range else '子组标准差估计'))]
        else:
            title = 'I' if one_chart else 'MR' if chart_two_only else 'I-MR'
            name1, name2 = 'I 图（单值）', 'MR 图（移动极差）'
            sizes = 1
            notes = ['移动极差跨度：%d；前 %d 个移动极差未定义。' % (mr_range, mr_range - 1),
                     '过程标准差来源：' + ('指定 sigma = %.6g' % sigma if sigma is not None else '移动极差估计')]
        notes += ['控制限计算参数：k = %.6g；均值来源：%s。' % (
            k, '输入数据估计' if mean is None else '指定 mean = %.6g' % mean),
            '控制限汇总及明细使用实际绘图值（含调用方指定的中心线或控制限）。']
        if xlabel is not None:
            notes.append('输入标签（X 轴）：%s' % xlabel)
        charts = []
        if not chart_two_only:
            charts.append((name1, s['Y1'], lcl1, bar1, ucl1))
            notes.append('%s显示标签：%s' % (name1, ylabel1))
        if not one_chart:
            charts.append((name2, s['Y2'], lcl2, bar2, ucl2))
            notes.append('%s显示标签：%s' % (name2, ylabel2))
        _print_spc_report(title, charts, sizes, '子组大小' if isinstance(n, list) else '每点观测数',
                          xLabels, notes, print_port, anomalies=anomalies)

    res = {"lcl1": lcl1, "bar1": bar1, "ucl1": ucl1,
           "lcl2": lcl2, "bar2": bar2, "ucl2": ucl2,
           "n": n}

    return res


def p_np_plot(p=None, n=1,
              bar1=None, ucl1=None, lcl1=None, xLabels=None,
              print_out=False, max_label_num=25, print_port=print,
              ylabel="P", NP=False,
              xlabel=None, ax=None, fig=None, refY=None,
              filename=None):

    if not isinstance(n, list):
        nlist = [n] * len(p)
    else:
        nlist = n

    p_bar = sum([i * j for i, j in zip(p, nlist)]) / sum(nlist)
    ucl_list = [p_bar + 3 * (p_bar * (1 - p_bar) / i)**.5 for i in nlist]
    lcl_list = [max(0, p_bar - 3 * (p_bar * (1 - p_bar) / i)**.5)
                for i in nlist]
    if NP:
        p_bar = [p_bar * ni for ni in nlist]
        p_bar = p_bar[0] if len(set(nlist)) == 1 else p_bar
        ucl_list = np.array(ucl_list) * nlist
        lcl_list = np.array(lcl_list) * nlist
        p = np.array(p) * nlist

    xs = [-.5]
    for _ in range(len(p)):
        xs.append(xs[-1] + 1)
        xs.append(xs[-1])
    xs = xs[:-1]

    lcl_ys, ucl_ys = [], []
    for ucl in ucl_list:
        ucl_ys.append(ucl)
        ucl_ys.append(ucl)
    for lcl in lcl_list:
        lcl_ys.append(lcl)
        lcl_ys.append(lcl)

    if None in [ax, fig]:
        fig, ax = plt.subplots(1, figsize=(15, 15), layout='constrained')

    ax.plot(p, linestyle='-', marker='o', color='black')

    if bar1 is not None:
        p_bar = bar1
    if isinstance(p_bar, list):
        limit_line(ax, p_bar, color='blue', label='CL')
    else:
        ax.axhline(p_bar, color='blue', label='CL')

    if ucl1 is not None:
        ax.axhline(ucl1, color='red', linestyle='dashed', label='UCL')
    else:
        ax.plot(xs, ucl_ys, color='red', linestyle='dashed', label='UCL')
    if lcl1 is not None:
        ax.axhline(lcl1, color='red', linestyle='dashed', label='LCL')
    else:
        ax.plot(xs, lcl_ys, color='red', linestyle='dashed', label='LCL')

    ax.set(ylabel=ylabel)
    add_Y_refs(ax=ax, y_values=refY)

    if xLabels is not None:
        step = 1
        if len(xLabels) > max_label_num:
            step = len(xLabels) / max_label_num
            if step > int(step):
                step = int(step) + 1
            else:
                step = int(step)
        ax.set_xticks(range(len(xLabels)), xLabels,
                      rotation='vertical')
        ax.set_xticks(ax.get_xticks()[::step])
    if xlabel is not None:
        ax.set(xlabel=xlabel)
    ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1), frameon=False)
    style_axes(ax)
    plt.show()

    if print_out:
        name = 'NP 图（不合格品数）' if NP else 'P 图（不合格比例）'
        _print_spc_report('NP' if NP else 'P', [(
            name, p, lcl1 if lcl1 is not None else lcl_list,
            p_bar, ucl1 if ucl1 is not None else ucl_list)], nlist, '检验数量', xLabels,
            ['输入标签（Y 轴）：%s' % ylabel,
             '控制限方法：二项分布的 3 倍标准差；比例中心按检验数量加权；原计算下限截为 0。',
             'NP 图统计值为不合格品数量；按各组检验数量计算中心线与控制限。' if NP else
             'P 图统计值为不合格比例；检验数量不同时逐点列示实际控制限。',
             '中心线与控制限采用实际绘图值（含调用方指定值）。'], print_port)

    return


def cu_plot(c=None, n=1,
            bar1=None, ucl1=None, lcl1=None, xLabels=None,
            print_out=False, max_label_num=25, print_port=print,
            ylabel="P", C=False,
            xlabel=None, ax=None, fig=None, refY=None,
            filename=None):
    # c 为原始缺陷数，n 为检查单位数；U 图只在此处归一化（C 图 n=1）。
    p = c
    if not isinstance(n, list):
        nlist = [n] * len(p)
    else:
        nlist = n

    c_bar = sum(c) / sum(nlist)
    ucl_list = [c_bar + 3 * (c_bar / i)**.5 for i in nlist]
    lcl_list = [max(0, c_bar - 3 * (c_bar / i)**.5) for i in nlist]
    c = [float(i) / float(j) for i, j in zip(c, nlist)]
    xs = [-.5]
    for _ in range(len(p)):
        xs.append(xs[-1] + 1)
        xs.append(xs[-1])
    xs = xs[:-1]

    lcl_ys, ucl_ys = [], []
    for ucl in ucl_list:
        ucl_ys.append(ucl)
        ucl_ys.append(ucl)
    for lcl in lcl_list:
        lcl_ys.append(lcl)
        lcl_ys.append(lcl)

    if None in [ax, fig]:
        fig, ax = plt.subplots(1, figsize=(15, 15), layout='constrained')

    ax.plot(c, linestyle='-', marker='o', color='black')

    if bar1 is not None:
        c_bar = bar1
    ax.axhline(c_bar, color='blue', label='CL')

    if ucl1 is not None:
        ax.axhline(ucl1, color='red', linestyle='dashed', label='UCL')
    else:
        ax.plot(xs, ucl_ys, color='red', linestyle='dashed', label='UCL')
    if lcl1 is not None:
        ax.axhline(lcl1, color='red', linestyle='dashed', label='LCL')
    else:
        ax.plot(xs, lcl_ys, color='red', linestyle='dashed', label='LCL')

    ax.set(ylabel=ylabel)
    add_Y_refs(ax=ax, y_values=refY)

    if xLabels is not None:
        step = 1
        if len(xLabels) > max_label_num:
            step = len(xLabels) / max_label_num
            if step > int(step):
                step = int(step) + 1
            else:
                step = int(step)
        ax.set_xticks(range(len(xLabels)), xLabels,
                      rotation='vertical')
        ax.set_xticks(ax.get_xticks()[::step])
    if xlabel is not None:
        ax.set(xlabel=xlabel)

    ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1), frameon=False)
    style_axes(ax)
    plt.show()

    if print_out:
        name = 'C 图（缺陷数）' if C else 'U 图（单位缺陷数）'
        _print_spc_report('C' if C else 'U', [(
            name, c, lcl1 if lcl1 is not None else lcl_list,
            c_bar, ucl1 if ucl1 is not None else ucl_list)], nlist, '检查单位/机会数', xLabels,
            ['输入标签（Y 轴）：%s' % ylabel,
             '控制限方法：泊松分布的 3 倍标准差；中心线为输入缺陷总数 / 检查单位总数；原计算下限截为 0。',
             'C 图在 GUI 中每次使用一个检查单位；本表按原实现列示输入缺陷数 / 检查单位数，缺陷数不同于不合格品数。' if C else
             'U 图统计值为输入缺陷数 / 检查单位数；单位数不同时逐点列示实际控制限。',
             '中心线与控制限采用实际绘图值（含调用方指定值）。'], print_port)

    return
