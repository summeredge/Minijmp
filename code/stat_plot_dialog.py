"""独立统计图形：沿用 SBDialog 和工作表绑定的图形窗口。"""
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
from decimal import Decimal, InvalidOperation, localcontext
from collections import defaultdict
from textwrap import wrap

import numpy as np
import pandas as pd
import seaborn as sns
from scipy import stats

from dialog import addListBox
from sbplot_dialog import SBDialog
from chart_style import style_axes
from sb_misc import interval_plot


TITLES = {'bubble': '气泡图', 'ecdf': '经验累积分布函数图',
          'individual': '单值图', 'interval': '区间图',
          'marginal': '边际图', 'stem': '茎叶图', 'probability': '样本概率图'}


def stem_leaf(values, exponent='自动'):
    """十进制叶单位；朝零截断，负零茎保留符号。"""
    numbers = sorted(Decimal(str(v)) for v in values)
    if not numbers:
        raise ValueError('没有可用的有限观测。')
    maximum = max(abs(v) for v in numbers)
    power = maximum.adjusted() - 1 if exponent == '自动' and maximum else 0
    if exponent != '自动':
        power = int(exponent)
    if not -308 <= power <= 308:
        raise ValueError('叶单位指数应在 -308 到 308 之间。')
    unit = Decimal(10) ** power
    rows = defaultdict(list)
    with localcontext() as context:
        context.prec = max(640, max(len(v.as_tuple().digits) for v in numbers) + 620)
        scaled = [int(v / unit) for v in numbers]
    if max(scaled) - min(scaled) > 1000:
        raise ValueError('数值范围过大，请增大叶单位指数。')
    for value, integer in zip(numbers, scaled):
        stem, leaf = divmod(abs(integer), 10)
        key = ('-' if value < 0 else '') + str(stem)
        rows[key].append(str(leaf))
    lines = [f'茎叶图；样本数 N = {len(numbers)}；叶单位 = {unit}',
             '叶单位 = 10^指数；朝零截断，未四舍五入；原值与显示值相差小于一个叶单位。',
             '读法：-1 | 2 表示 -12 × 叶单位；-0 | 2 表示 -2 × 叶单位。',
             '负茎整行均为负数；续行保留相同的茎。']
    for stem, leaves in rows.items():
        lines.extend(f'{stem:>5} | {part}' for part in wrap(' '.join(leaves), width=100))
    return '\n'.join(lines)


class StatPlotDialog(SBDialog):
    def __init__(self, parent=None, df=None, app=None, kind='ecdf'):
        self.kind = kind
        super().__init__(parent, df=df, app=app, title=TITLES[kind])

    def field(self, master, label, default='', choices=None):
        row = ttk.Frame(master)
        row.pack(fill=tk.X, padx=4, pady=2)
        ttk.Label(row, text=label, width=20).pack(side=tk.LEFT)
        var = tk.StringVar(self.main, value=default)
        widget = (ttk.Entry(row, textvariable=var) if choices is None else
                  ttk.Combobox(row, textvariable=var, values=choices, state='readonly'))
        widget.pack(side=tk.LEFT, fill=tk.X, expand=True)
        return var

    def createWidgets(self, m):
        if self.kind in ('bubble', 'marginal'):
            self.xyz = [self.field(m, label, choices=self.cols)
                        for label in (('X 数据列', 'Y 数据列', '面积数据列')
                                      if self.kind == 'bubble' else ('X 数据列', 'Y 数据列'))]
        else:
            frame, self.variables = addListBox(m, values=self.cols,
                                             label='选择一列数值' if self.kind in ('stem', 'probability') else '数值列（可多选）')
            frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)
        if self.kind in ('bubble', 'ecdf', 'individual', 'interval'):
            self.group = self.field(m, '分类列（可选）', choices=[''] + self.cols)
        if self.kind == 'stem':
            self.exponent = self.field(m, '叶单位指数', '自动')
            return
        if self.kind == 'marginal':
            self.bins = self.field(m, '直方图分箱数', '10')
        if self.kind == 'interval':
            self.confidence = self.field(m, '置信水平（%）', '95')
        self.plot_title = self.field(m, '标题', TITLES[self.kind])
        self.xlabel = self.field(m, 'X 轴标签')
        self.ylabel = self.field(m, 'Y 轴标签')
        self.yref = self.field(m, '水平参考值（可选）')
        self.grid = tk.BooleanVar(self.main, value=True)
        self.show_legend = tk.BooleanVar(self.main, value=True)
        ttk.Checkbutton(m, text='显示网格', variable=self.grid).pack(side=tk.LEFT)
        if self.kind in ('bubble', 'ecdf'):
            ttk.Checkbutton(m, text='显示图例', variable=self.show_legend).pack(side=tk.LEFT)

    def help(self, event=None):
        from help_link import open_help
        open_help('plots.' + self.kind, parent=self.main)
        return 'break'

    def prepare(self):
        cols = ([v.get() for v in self.xyz] if self.kind in ('bubble', 'marginal')
                else self.variables.getSelectedItem())
        if not cols or any(c not in self.df.columns for c in cols):
            raise ValueError('请选择有效的数值列。')
        if len(set(cols)) != len(cols):
            raise ValueError('请选择不同的数值列。')
        if self.kind in ('stem', 'probability') and len(cols) != 1:
            raise ValueError('请选择一列数值。')
        group = self.group.get() if hasattr(self, 'group') else ''
        if group and (group not in self.df.columns or group in cols):
            raise ValueError('分类列必须是数值列之外的有效列。')
        if self.kind == 'stem':
            try:
                values = [Decimal(str(v)) for v in self.df[cols[0]] if not pd.isna(v)]
            except (InvalidOperation, ValueError, TypeError):
                raise ValueError('所选列包含非数值数据，请先检查数据。') from None
            values = [v for v in values if v.is_finite()]
            if not values:
                raise ValueError('没有可用的有限观测。')
            return cols, [(str(cols[0]), values)], None
        try:
            data = self.df[cols].apply(pd.to_numeric, errors='raise').astype(float)
        except (ValueError, TypeError):
            raise ValueError('所选列包含非数值数据，请先检查数据。') from None
        data = data.replace([np.inf, -np.inf], np.nan).reset_index(drop=True)
        labels = self.df[group].reset_index(drop=True) if group else None
        groups = []
        if self.kind in ('bubble', 'marginal'):
            valid = data.notna().all(axis=1)
            if group:
                valid &= labels.notna()
            data = data.loc[valid]
            if data.empty:
                raise ValueError('没有完整配对的有限观测。')
            if self.kind == 'bubble' and (data.iloc[:, 2].lt(0).any() or not data.iloc[:, 2].gt(0).any()):
                raise ValueError('气泡面积必须非负，且至少有一个正值；零面积不显示。')
            if group:
                labels = labels.loc[valid]
            return cols, data, labels
        for col in cols:
            valid = data[col].notna()
            if group:
                valid &= labels.notna()
                if not valid.any():
                    raise ValueError('每个数值列至少需要一个带分类的有限观测。')
                for key in pd.unique(labels[valid]):
                    values = data.loc[valid & labels.eq(key), col].to_numpy()
                    groups.append((f'{col} / {key}', values))
            else:
                groups.append((str(col), data.loc[valid, col].to_numpy()))
        if not groups or any(len(v) == 0 for _, v in groups):
            raise ValueError('每个数值列至少需要一个有限观测。')
        if len({label for label, _ in groups}) != len(groups):
            raise ValueError('分类组合的显示名称重复，请统一分类值类型或重命名数值列。')
        return cols, groups, None

    def apply(self):
        try:
            self.app.getCurrentTable()
            cols, data, labels = self.prepare()
            if self.kind == 'stem':
                result = stem_leaf(data[0][1], self.exponent.get().strip())
                self.app.print(result)
                return
            arrays = [data[col].to_numpy() for col in cols] if self.kind in ('bubble', 'marginal') else [v for _, v in data]
            with np.errstate(over='ignore', invalid='ignore'):
                for values in arrays:
                    low, high = np.min(values), np.max(values)
                    span = high - low
                    padding = span * .05 if span else abs(high) * .05 + .05
                    if not np.isfinite([span, low - padding, high + padding]).all():
                        raise ValueError('数据范围过大，无法生成有限坐标，请调整数据尺度。')
            ref = float(self.yref.get()) if self.yref.get().strip() else None
            if ref is not None and not np.isfinite(ref):
                raise ValueError('参考值必须是有限数值。')
            confidence = float(self.confidence.get()) / 100 if self.kind == 'interval' else .95
            if not 0 < confidence < 1:
                raise ValueError('置信水平必须在 0 与 100 之间。')
            if self.kind == 'interval' and any(len(v) < 2 for _, v in data):
                raise ValueError('均值置信区间要求每组至少两个有效观测。')
            def mean_ci(values):
                half = stats.t.ppf((1 + confidence) / 2, len(values) - 1) * stats.sem(values)
                return np.mean(values) - half, np.mean(values) + half
            if self.kind == 'interval' and not all(np.isfinite(mean_ci(v)).all() for _, v in data):
                raise ValueError('数据范围过大，无法计算有限的均值置信区间。')
            if self.kind == 'probability' and len(data[0][1]) < 2:
                raise ValueError('样本概率图至少需要两个有效观测。')
            if self.kind == 'probability':
                (quantiles, ordered), (slope, intercept, _) = stats.probplot(data[0][1], dist='norm')
                fitted = slope * quantiles + intercept
                if not np.isfinite(fitted).all():
                    raise ValueError('数据范围过大，无法计算有限的概率图参考线。')
            bins = int(self.bins.get()) if self.kind == 'marginal' else 10
            if not 1 <= bins <= 200:
                raise ValueError('分箱数必须是 1 到 200 的整数。')
            if self.kind == 'marginal':
                edges = [np.histogram_bin_edges(data[col], bins=bins) for col in cols]
                if not all(np.isfinite(edge).all() and np.all(np.diff(edge) > 0) for edge in edges):
                    raise ValueError('数据范围无法分箱，请调整数据尺度或分箱数。')
        except RuntimeError as error:
            messagebox.showerror('无法绘图', str(error), parent=self.main)
            return
        except (ValueError, TypeError, OverflowError) as error:
            self.error('输入无效：' + str(error))
            return
        pf = self.showPlotViewer()
        if self.kind == 'marginal':
            layout = pf.fig.add_gridspec(2, 2, width_ratios=(4, 1), height_ratios=(1, 4))
            pf.ax = ax = pf.fig.add_subplot(layout[1, 0])
            top = pf.fig.add_subplot(layout[0, 0], sharex=ax)
            right = pf.fig.add_subplot(layout[1, 1], sharey=ax)
            ax.scatter(data.iloc[:, 0], data.iloc[:, 1])
            top.hist(data.iloc[:, 0], bins=edges[0])
            right.hist(data.iloc[:, 1], bins=edges[1], orientation='horizontal')
            top.tick_params(labelbottom=False)
            right.tick_params(labelleft=False)
            top.set_ylabel('频数')
            right.set_xlabel('频数')
            ax.set(xlabel=cols[0], ylabel=cols[1])
        else:
            pf.ax = ax = pf.fig.add_subplot(111)
        if self.kind == 'bubble':
            maximum = data.iloc[:, 2].max()
            masks = [(str(k), labels.eq(k).to_numpy()) for k in pd.unique(labels)] if labels is not None else [('', np.ones(len(data), dtype=bool))]
            for label, mask in masks:
                subset = data.iloc[mask]
                ax.scatter(subset.iloc[:, 0], subset.iloc[:, 1],
                           s=subset.iloc[:, 2] / maximum * 500, alpha=.6, label=label or cols[2])
            ax.text(.01, .99, f'面积 ∝ {cols[2]}；最大值 {maximum:g} = 500 pt²；零值不可见',
                    transform=ax.transAxes, va='top', fontsize=9)
            ax.set(xlabel=cols[0], ylabel=cols[1])
        elif self.kind == 'ecdf':
            for label, values in data:
                sns.ecdfplot(x=values, ax=ax, label=label)
            ax.set(xlabel='观测值', ylabel='累计概率', ylim=(0, 1))
        elif self.kind == 'individual':
            for i, (label, values) in enumerate(data):
                sns.stripplot(x=[label] * len(values), y=values, order=[k for k, _ in data],
                              jitter=.15, ax=ax, color=f'C{i % 10}')
            ax.set(xlabel='数值列 / 分类', ylabel='观测值')
        elif self.kind == 'interval':
            # 只给新入口指定 t 区间，不改变 ANOVA 现有的自定义区间路径。
            frame = pd.concat([pd.DataFrame({'组': label, '值': values}) for label, values in data], ignore_index=True)
            interval_plot(data=frame, x='组', y='值', ax=ax, errorbar=mean_ci, linestyle='none')
            ax.set(xlabel='数值列 / 分类', ylabel=f'均值及 {confidence:.1%} t 置信区间')
        elif self.kind == 'probability':
            ax.plot(quantiles, ordered, 'o')
            ax.plot(quantiles, fitted, '-')
            ax.set(xlabel='标准正态理论分位数', ylabel=cols[0])
        ax.set_title(self.plot_title.get())
        if self.xlabel.get():
            ax.set_xlabel(self.xlabel.get())
        if self.ylabel.get():
            ax.set_ylabel(self.ylabel.get())
        if ref is not None:
            ax.axhline(ref, color='gray', linestyle='--')
        if self.show_legend.get() and self.kind in ('bubble', 'ecdf'):
            ax.legend()
        for axis in pf.fig.axes:
            style_axes(axis)
        ax.grid(self.grid.get())
        pf.canvas.draw()
