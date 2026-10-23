"""质量工具图形，复用现有图窗导航和保存。"""
import numpy as np
import textwrap
from itertools import product
from matplotlib.figure import Figure
from chart_style import style_axes


def plot_quality(result, figure=None, title='', xlabel='', ylabel='', reference=True, **options):
    figure = figure if figure is not None else Figure(figsize=(11, 7))
    figure.clear()
    tables = list(result['tables'].items())
    if result['kind'] == 'attribute_agreement':
        agreement = result['tables']['完全一致率']
        scopes = [('评价员内部', '评价员内部一致性')]
        if result['has_standard']:
            scopes.append(('评价员与标准', '评价员与标准一致性'))
        for i, (scope, heading) in enumerate(scopes):
            ax = figure.add_subplot(1, len(scopes), i+1)
            part = agreement[agreement['范围'] == scope]
            x = np.arange(len(part))
            valid = part['一致率'].notna()
            measured = part.loc[valid]
            ax.errorbar(x[valid], measured['一致率']*100,
                        yerr=np.vstack(((measured['一致率']-measured['CI下限'])*100, (measured['CI上限']-measured['一致率'])*100)),
                        fmt='o', capsize=5)
            ax.set_xticks(x, [str(v) for v in part['评价员']])
            ax.set(ylim=(-5, 105), xlabel=xlabel or '评价员', ylabel=ylabel or '完全一致率及置信区间（%）', title=title or heading)
            if not valid.any():
                ax.text(.5, .5, '不适用：单试次', transform=ax.transAxes, ha='center')
    if result['kind'] == 'multi_vari':
        factors, levels = result['factors'], result['levels']
        table, observations = result['tables']['组合统计'], result['observations']
        panels = list(product(*levels[2:]))
        if len(panels) > 36 or len(levels[0]) > 100:
            raise ValueError('图形超过 36 面板或 X 轴 100 水平，请筛选水平后重绘；结果表仍可导出。')
        columns = min(3, len(panels))
        rows = (len(panels)+columns-1)//columns
        figure.set_size_inches(max(10, columns*5), max(6, rows*3.5))
        for panel, values in enumerate(panels):
            ax = figure.add_subplot(rows, columns, panel+1)
            part, raw = table, observations
            for col, value in zip(factors[2:], values):
                part, raw = part[part[col] == value], raw[raw[col] == value]
            for j, second in enumerate(levels[1] if len(factors) > 1 else [None]):
                series = part[part[factors[1]] == second] if second is not None else part
                actual = raw[raw[factors[1]] == second] if second is not None else raw
                series = series.set_index(factors[0]).reindex(levels[0])
                x = np.arange(len(levels[0]))
                color = f'C{j % 10}'
                ax.plot(x, series['均值'], 'o-', color=color, label=f'{factors[1]}={second}' if second is not None else '组合均值')
                ax.vlines(x, series['最小值'], series['最大值'], color=color, alpha=.5)
                if options.get('raw', True):
                    positions = {value: i for i, value in enumerate(levels[0])}
                    ax.scatter([positions[v] for v in actual[factors[0]]], actual[result['response_key']], color=color, s=12, alpha=.4)
            ax.set_xticks(np.arange(len(levels[0])), [str(v) for v in levels[0]])
            ax.set(xlabel=xlabel or factors[0], ylabel=ylabel or '响应',
                   title=(title or '多变异图')+(' — '+', '.join(f'{k}={v}' for k, v in zip(factors[2:], values)) if values else ''))
            if options.get('legend', True):
                ax.legend(fontsize=8)
    if result['kind'] == 'cause_effect':
        table = result['tables']['原因结构']
        groups = list(table.groupby('类别', sort=False, observed=True))
        pairs = (len(groups)+1)//2
        wrap = lambda value: '\n'.join(textwrap.wrap(str(value), width=12))
        def units(part):
            return sum(max(1, len(wrap(cause).splitlines()))+sum(len(wrap(v).splitlines())+1 for v in sub['子原因'].unique() if v)+1
                       for cause, sub in part.groupby('原因', sort=False, observed=True) if cause)
        most = max(units(part) for _, part in groups)
        figure.set_size_inches(max(12, pairs*4.5+2), max(8, most*.65+3))
        ax = figure.add_subplot(111)
        ax.set(xlim=(0, pairs*4+3), ylim=(-1.35, 1.35), title=title or '因果图（原因假设）')
        ax.annotate('', (pairs*4+1, 0), (.2, 0), arrowprops=dict(arrowstyle='->', lw=2))
        ax.text(pairs*4+1.2, 0, wrap(result['problem']), va='center', bbox=dict(boxstyle='round', fc='#e6eff7'))
        for i, (category, part) in enumerate(groups):
            sign, base = (1 if i % 2 == 0 else -1), (i//2)*4+.5
            ax.plot([base, base+2], [sign, 0], color='#4c78a8', lw=1.8)
            ax.text(base, sign*1.08, wrap(category), ha='center', va='bottom' if sign > 0 else 'top', weight='bold')
            causes = [(name, sub) for name, sub in part.groupby('原因', sort=False, observed=True) if name]
            total_units, used = units(part)+2, 0
            for j, (cause, sub) in enumerate(causes):
                children = [v for v in sub['子原因'].unique() if v]
                weight = max(1, len(wrap(cause).splitlines()))+sum(len(wrap(v).splitlines())+1 for v in children)+1
                t = (used+weight)/total_units
                x, y = base+2*t, sign*(1-t)
                ax.plot([x-1.4, x], [y, y], color='#4c78a8')
                ax.text(x-1.45, y, wrap(cause), ha='right', va='center', fontsize=9)
                child_units = max(1, len(wrap(cause).splitlines()))/2+1
                for child in children:
                    sx = x-.65
                    sy = y+sign*child_units/total_units
                    ax.plot([sx-.15, sx], [sy, y], color='gray', lw=.8)
                    ax.text(sx-.2, sy, wrap(child), ha='right', va='bottom' if sign > 0 else 'top', fontsize=8)
                    child_units += len(wrap(child).splitlines())+1
                used += weight
        ax.axis('off')
    if result['kind'] == 'run_chart':
        ax = figure.add_subplot(111)
        table = result['tables']['运行图数据']
        x = np.arange(1, len(table)+1)
        ax.plot(x, table['统计量'], 'o-', markersize=4)
        ax.axhline(result['center'], color='#e45756', linestyle='--', label=f"中位数 {result['center']:.6g}")
        ax.set(xlabel=xlabel or '来源观测 / 子组顺序', ylabel=ylabel or '统计量', title=title or '运行图')
        ax.legend()
    if result['kind'] == 'pareto':
        for i, (name, table) in enumerate(tables):
            ax = figure.add_subplot(len(tables), 1, i+1)
            x = np.arange(len(table))
            ax.bar(x, table['频数'], color='#4c78a8')
            ax.set_xticks(x, [str(v) for v in table['类别']], rotation=35, ha='right')
            ax.set_ylabel(ylabel or '频数')
            ax.set_xlabel(xlabel or '缺陷类别')
            ax.set_title((title or '帕累托图') + (' — '+name if result['grouped'] else ''))
            right = ax.twinx()
            right.plot(x, table['累计百分比'], 'o-', color='#e45756')
            right.set(ylim=(0, 105), ylabel='累计百分比（%）')
            if reference:
                right.axhline(80, color='gray', linestyle='--', label='80%')
            for j, row in enumerate(table.itertuples(index=False, name=None)):
                ax.annotate(f'{row[1]}\n{row[2]:.1f}%', (j, row[1]), ha='center', va='bottom', fontsize=8)
            ax.margins(y=.22)
    for ax in figure.axes:
        style_axes(ax)
    figure.set_layout_engine('tight')
    return figure
