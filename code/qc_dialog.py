from dialog import option_combobox
from tkinter import ttk
import tkinter as tk
from tkinter import TOP, LEFT, X, BOTH
###################################
#  from pandastable_local.dialogs import addListBox
########### Own Modules ###########
from dialog import Dialogs
from GRR import grr_master, grr_nested
from utilities import is_void, is_number, grouping_by_labels, number_list, get_number
from cpk_plot import cpk_plot
from ti import ti_norm
from grr_plot import grr_plot


class GRR_Nested_Dialog(Dialogs):
    column_roles = (('xvar', True), ('yvar', False), ('ovar', False))

    def createWidgets(self, m):
        ff = tk.LabelFrame(m, text='输入列')
        ff.pack(side=TOP, fill=BOTH, padx=2, pady=2)
        f = tk.Frame(ff)
        f.pack(side=TOP, fill=BOTH, padx=2, pady=2)
        self.xvar = tk.StringVar(value="")
        self.yvar = tk.StringVar(value="")
        w = tk.Label(f, text='测量值')
        w.pack(side=LEFT, fill=X, padx=2, pady=2)
        w = ttk.Combobox(
            f, values=self.cols, textvariable=self.xvar,
            width=14)
        w.pack(side=LEFT, padx=2, pady=2)
        w = tk.Label(f, text='部件编号')
        w.pack(side=LEFT, fill=X, padx=2, pady=2)
        w = ttk.Combobox(
            f, values=self.cols, textvariable=self.yvar,
            width=14)
        w.pack(side=LEFT, padx=2, pady=2)

        f = tk.Frame(ff)
        f.pack(side=TOP, fill=BOTH, padx=2, pady=2)
        self.ovar = tk.StringVar(value="")
        w = tk.Label(f, text='操作员')
        w.pack(side=LEFT, fill=X, padx=2, pady=2)
        w = ttk.Combobox(
            f, values=self.cols, textvariable=self.ovar,
            width=14)
        w.pack(side=LEFT, padx=2, pady=2)

        f = tk.LabelFrame(m, text='可选输入')
        f.pack(side=TOP, fill=BOTH, padx=2, pady=2)
        self.hist_std = tk.StringVar(value="")
        w = tk.Label(f, text='历史过程标准差（整体）')
        w.pack(side=LEFT, fill=X, padx=2, pady=2)
        w = tk.Entry(f, textvariable=self.hist_std,
                     bg='white', width=10)
        w.pack(side=LEFT, padx=2, pady=2)

        return

    def apply(self):
        try:
            y = self.df[self.xvar.get()]
            p = self.df[self.yvar.get()]
            o = self.df[self.ovar.get()]
        except BaseException:
            self.error(msg='输入有误或输入项过少。')
            return

        r = [[], [], []]
        for i, j, k in zip(y, p, o):
            if is_void(j) or is_void(k):
                continue
            if is_number(i):
                r[0].append(float(i))
                r[1].append(j)
                r[2].append(k)

        if len(r[0]) < 4:
            self.error(msg='输入有误：数据点过少。')
            return

        try:
            self.app.print(f"分析变量：{self.xvar.get()}；零件列：{self.yvar.get()}；操作者列：{self.ovar.get()}。")
            grr_nested(
                y=r[0], part=r[1],
                op=r[2],  # if has_op else None,
                hist_std=get_number(self.hist_std),
                print_out=True,
                print_port=self.app.print)
            self.remember_columns()
        except ValueError as e:
            self.error(msg={
                'Measurements, parts and operators must have equal nonzero lengths.': '测量值、部件和操作员的数据长度必须相等且不为空。',
                'Measurements must be finite numbers.': '测量值必须为有限数值。',
                'Historical standard deviation must be finite and positive.': '历史标准差必须为有限正数。',
                'Each part must have equal replicates and belong to only one operator.': '每个部件的重复测量次数必须相等，且只能属于一名操作员。',
                'The experiment design is not balanced.': '试验设计不平衡。',
                'Nested GRR requires at least two operators, two parts per operator and two replicates per part.': '嵌套量具 R&R 至少需要两名操作员，每名操作员测量两个部件，每个部件重复测量两次。',
            }.get(str(e), str(e)))
        return


class GRRDialog(Dialogs):
    column_roles = (('xvar', True), ('yvar', False), ('ovar', False))

    def createWidgets(self, m):
        f = tk.LabelFrame(m, text='输入列')
        f.pack(side=TOP, fill=BOTH, padx=2, pady=2)
        self.xvar = tk.StringVar(value="")
        self.yvar = tk.StringVar(value="")
        w = tk.Label(f, text='测量值')
        w.pack(side=LEFT, fill=X, padx=2, pady=2)
        w = ttk.Combobox(
            f, values=self.cols, textvariable=self.xvar,
            width=14)
        w.pack(side=LEFT, padx=2, pady=2)
        w = tk.Label(f, text='部件编号')
        w.pack(side=LEFT, fill=X, padx=2, pady=2)
        w = ttk.Combobox(
            f, values=self.cols, textvariable=self.yvar,
            width=14)
        w.pack(side=LEFT, padx=2, pady=2)

        f = tk.LabelFrame(m, text='可选输入')
        f.pack(side=TOP, fill=BOTH, padx=2, pady=2)
        self.ovar = tk.StringVar(value="")
        w = tk.Label(f, text='操作员')
        w.pack(side=LEFT, fill=X, padx=2, pady=2)
        w = ttk.Combobox(
            f, values=self.cols, textvariable=self.ovar,
            width=14)
        w.pack(side=LEFT, padx=2, pady=2)

        f = tk.LabelFrame(m, text='分析方法设置')
        f.pack(side=TOP, fill=BOTH, padx=2, pady=2)
        self.mvar = tk.StringVar(value="AIAG (ANOVA)")
        w = tk.Label(f, text='方法')
        w.pack(side=LEFT, fill=X, padx=2, pady=2)
        w = option_combobox(
            f,
            values=[
                "AIAG (ANOVA)",
                "EMP (ANOVA)",
                "XBAR/R"],
            textvariable=self.mvar,
            width=18)
        w.pack(side=LEFT, padx=2, pady=2)

        self.inter = tk.StringVar(value="Auto")
        w = tk.Label(f, text='操作员与部件交互作用')
        w.pack(side=LEFT, padx=2, pady=2)
        w = option_combobox(
            f,
            values=["Auto", "On", "Off"],
            textvariable=self.inter,
            width=5)
        w.pack(side=LEFT, padx=2, pady=2)

        f = tk.LabelFrame(m, text='AIAG 和 Xbar/R 设置（可选）')
        f.pack(side=TOP, fill=BOTH, padx=2, pady=2)
        slave = tk.Frame(f)
        slave.pack(side=TOP, fill=BOTH, padx=0, pady=2)

        self.spec_gap = tk.StringVar(value="")
        w = tk.Label(slave, text='规格宽度（USL - LSL）')
        w.pack(side=LEFT, fill=X, padx=2, pady=2)
        w = tk.Entry(slave, textvariable=self.spec_gap,
                     bg='white', width=15)
        w.pack(side=LEFT, padx=2, pady=2)

        self.hist_std = tk.StringVar(value="")
        w = tk.Label(slave, text='历史标准差')
        w.pack(side=LEFT, fill=X, padx=2, pady=2)
        w = tk.Entry(slave, textvariable=self.hist_std,
                     bg='white', width=15)
        w.pack(side=LEFT, padx=2, pady=2)

        #  s1 = "Use historical standard deviation to estimate process variation."
        #  s2 = "Use parts in the study to estimate process variation."
        #  self.hist_std_use = tk.StringVar(value=s1)
        #  w = ttk.Combobox(
        #      f,
        #      values=[s1, s2],
        #      textvariable=self.hist_std_use,
        #      width=50)
        #  w.pack(side=LEFT, padx=10, pady=2)

        self.ylabel = tk.StringVar(value="")
        master = tk.LabelFrame(m, text='绘图设置')
        master.pack(side=TOP, fill=BOTH, padx=2)
        w = tk.Label(master, text='Y 轴标签')
        w.pack(side=LEFT, fill=X, padx=2)
        w = tk.Entry(master, textvariable=self.ylabel,
                     bg='white', width=15)
        w.pack(side=LEFT, padx=2, pady=2)

        self.add_alpha(m)
        return

    def apply(self):
        alpha = self.alpha.get()
        if alpha > 0.5 or alpha <= 0:
            alpha = 0.05
        y = self.df[self.xvar.get()]
        p = self.df[self.yvar.get()]
        try:
            o = self.df[self.ovar.get()]
            has_op = True
        except BaseException:
            o = [1] * len(y)
            has_op = False

        r = [[], [], []]
        for i, j, k in zip(y, p, o):
            if is_void(j) or is_void(k):
                continue
            if is_number(i):
                r[0].append(float(i))
                r[1].append(j)
                r[2].append(k)
        #  print(r)

        hist_std = get_number(self.hist_std)
        if hist_std is not None:
            hist_std = hist_std if hist_std >= 0 else None
        spec_gap = get_number(self.spec_gap)
        if spec_gap is not None:
            spec_gap = spec_gap if spec_gap >= 0 else None
        #  use_hist = ("hist" in self.hist_std_use.get())

        self.app.print(f"分析变量：{self.xvar.get()}；零件列：{self.yvar.get()}；操作者列：{self.ovar.get() or '未提供'}。")
        grr_master(
            y=r[0], part=r[1],
            op=r[2] if has_op else None,
            mode=self.mvar.get(),
            inter=self.inter.get(),
            hist_std=hist_std,
            spec_gap=spec_gap,
            #  use_hist=use_hist,
            print_out=True,
            alpha=alpha,
            print_port=self.app.print)

        pf = self.app.showPlotViewer()
        pf.ax = pf.fig.add_subplot(111)
        grr_plot(
            y=r[0], part=r[1],
            op=r[2] if has_op else None,
            ax=pf.ax,
            ylabel=self.ylabel.get() if self.ylabel.get() != "" else self.xvar.get())
        self.remember_columns()
        return


class CpkDialog(Dialogs):
    column_roles = (('xvar', True),)

    def createWidgets(self, m):
        f = tk.LabelFrame(m, text='输入列')
        f.pack(side=TOP, fill=BOTH, padx=2)
        self.xvar = tk.StringVar(value="")
        w = tk.Label(f, text='测量值')
        w.pack(side=LEFT, fill=X, padx=2, pady=2)
        w = ttk.Combobox(
            f, values=self.cols, textvariable=self.xvar,
            width=14)
        w.pack(side=LEFT, padx=2, pady=2)

        master = tk.LabelFrame(m, text='输入规格限')
        master.pack(side=TOP, fill=BOTH, padx=2)
        self.target = tk.DoubleVar(value=0)
        self.lsl = tk.DoubleVar(value=0)
        self.usl = tk.DoubleVar(value=0)
        w = tk.Label(master, text='规格下限（LSL）')
        w.pack(side=LEFT, fill=X, padx=2)
        w = tk.Entry(master, textvariable=self.lsl,
                     bg='white', width=10)
        w.pack(side=LEFT, padx=2, pady=2)
        w = tk.Label(master, text='目标值')
        w.pack(side=LEFT, fill=X, padx=2)
        w = tk.Entry(master, textvariable=self.target,
                     bg='white', width=10)
        w.pack(side=LEFT, padx=2, pady=2)
        w = tk.Label(master, text='规格上限（USL）')
        w.pack(side=LEFT, fill=X, padx=2)
        w = tk.Entry(master, textvariable=self.usl,
                     bg='white', width=10)
        w.pack(side=LEFT, padx=2, pady=2)

        self.show_within = tk.BooleanVar(value=False)
        w = tk.Checkbutton(
            m,
            text='显示由相邻观测值移动极差估计的组内标准差',
            variable=self.show_within)
        w.pack(side=TOP, fill=BOTH, padx=2, pady=2)

        self.xlabel = tk.StringVar(value="")
        self.show_legend = tk.BooleanVar(value=True)
        self.show_spec = tk.BooleanVar(value=True)
        master = tk.LabelFrame(m, text='绘图设置')
        master.pack(side=TOP, fill=BOTH, padx=2)
        w = tk.Label(master, text='X 轴标签')
        w.pack(side=LEFT, fill=X, padx=2)
        w = tk.Entry(master, textvariable=self.xlabel,
                     bg='white', width=15)
        w.pack(side=LEFT, padx=2, pady=2)
        w = tk.Checkbutton(master, text='显示规格限',
                           variable=self.show_spec)
        w.pack(side=LEFT, padx=2, pady=2)
        w = tk.Checkbutton(master, text='显示图例',
                           variable=self.show_legend)
        w.pack(side=LEFT, padx=2, pady=2)

        self.add_alpha(m)
        return

    def apply(self):
        data = number_list(self.df[self.xvar.get()])
        if len(data) < 2 or len(set(data)) < 2:
            self.error('过程能力分析至少需要两个观测值，且变异大于 0。')
            return

        alpha = self.alpha.get()
        if alpha > 0.5 or alpha <= 0:
            alpha = 0.05

        lsl, tgt, usl = self.lsl.get(), self.target.get(), self.usl.get()
        if lsl < tgt < usl:
            pass
        elif tgt == 0 and lsl < usl:
            self.error('未指定目标值，将使用规格下限与规格上限的平均值。')
            tgt = (lsl + usl) / 2
        else:
            self.error('规格限输入有误。')
            return

        pf = self.app.showPlotViewer()
        pf.ax = pf.fig.add_subplot(111)

        self.app.print(f"分析变量：{self.xvar.get()}。")
        cpk_plot(
            data,
            lsl,
            tgt,
            usl,
            print_out=True,
            print_port=self.app.print,
            xlabel=self.xlabel.get() if self.xlabel.get() != "" else self.xvar.get(),
            alpha=alpha,
            ax=pf.ax,
            show_legend=self.show_legend.get(),
            show_within=self.show_within.get(),
            show_spec=self.show_spec.get())

        self.remember_columns()
        return


class CpkSubDialog(Dialogs):
    column_roles = (('xvar', True), ('subid', False))

    def createWidgets(self, m):
        f = tk.LabelFrame(m, text='输入列')
        f.pack(side=TOP, fill=BOTH, padx=2)
        self.xvar = tk.StringVar(value="")
        w = tk.Label(f, text='测量值')
        w.pack(side=LEFT, fill=X, padx=2, pady=2)
        w = ttk.Combobox(
            f, values=self.cols, textvariable=self.xvar,
            width=14)
        w.pack(side=LEFT, padx=2, pady=2)

        master = tk.LabelFrame(m, text='输入规格限')
        master.pack(side=TOP, fill=BOTH, padx=2)
        self.target = tk.DoubleVar(value=0)
        self.lsl = tk.DoubleVar(value=0)
        self.usl = tk.DoubleVar(value=0)
        w = tk.Label(master, text='规格下限（LSL）')
        w.pack(side=LEFT, fill=X, padx=2)
        w = tk.Entry(master, textvariable=self.lsl,
                     bg='white', width=10)
        w.pack(side=LEFT, padx=2, pady=2)
        w = tk.Label(master, text='目标值')
        w.pack(side=LEFT, fill=X, padx=2)
        w = tk.Entry(master, textvariable=self.target,
                     bg='white', width=10)
        w.pack(side=LEFT, padx=2, pady=2)
        w = tk.Label(master, text='规格上限（USL）')
        w.pack(side=LEFT, fill=X, padx=2)
        w = tk.Entry(master, textvariable=self.usl,
                     bg='white', width=10)
        w.pack(side=LEFT, padx=2, pady=2)

        f = tk.LabelFrame(m, text='子组')
        f.pack(side=TOP, fill=BOTH, padx=2)
        self.mvar = tk.StringVar(value="Use Subgrp Size")
        w = tk.Label(f, text='选项')
        w.pack(side=LEFT, fill=X, padx=2)
        w = option_combobox(
            f,
            values=[
                #  "No Subgroups",
                "Use Subgrp ID Col.",
                "Use Subgrp Size"],
            textvariable=self.mvar,
            width=14)
        w.pack(side=LEFT, padx=2)
        self.subid = tk.StringVar(value="")
        w = tk.Label(f, text='子组标识列')
        w.pack(side=LEFT, fill=X, padx=2)
        w = ttk.Combobox(
            f, values=self.cols, textvariable=self.subid,
            width=14)
        w.pack(side=LEFT, padx=2)
        self.subsize = tk.DoubleVar(value=2)
        w = tk.Label(f, text='子组大小')
        w.pack(side=LEFT, fill=X, padx=2)
        w = tk.Entry(f, textvariable=self.subsize,
                     bg='white', width=5)
        w.pack(side=LEFT, padx=2, pady=2)

        f = tk.LabelFrame(m, text='子组内变异')
        f.pack(side=TOP, fill=BOTH, padx=2)
        self.subm = tk.StringVar(value="Unbiased Std Dev")
        w = tk.Label(f, text='平均值的计算依据')
        w.pack(side=LEFT, fill=X, padx=2)
        w = option_combobox(
            f,
            values=[
                "Unbiased Std Dev",
                "Ranges"],
            textvariable=self.subm,
            width=14)
        w.pack(side=LEFT, padx=2)

        self.xlabel = tk.StringVar(value="")
        self.show_legend = tk.BooleanVar(value=True)
        self.show_spec = tk.BooleanVar(value=True)
        self.show_within = tk.BooleanVar(value=True)
        master = tk.LabelFrame(m, text='绘图设置')
        master.pack(side=TOP, fill=BOTH, padx=2)
        w = tk.Label(master, text='X 轴标签')
        w.pack(side=LEFT, fill=X, padx=2)
        w = tk.Entry(master, textvariable=self.xlabel,
                     bg='white', width=15)
        w.pack(side=LEFT, padx=2, pady=2)
        w = tk.Checkbutton(master, text='显示规格限',
                           variable=self.show_spec)
        w.pack(side=LEFT, padx=2, pady=2)
        #  w = tk.Checkbutton(master, text='Show Within',
        #                     variable=self.show_within)
        #  w.pack(side=LEFT, padx=2, pady=2)
        w = tk.Checkbutton(master, text='显示图例',
                           variable=self.show_legend)
        w.pack(side=LEFT, padx=2, pady=2)

        self.add_alpha(m)
        return

    def apply(self):
        m = self.mvar.get()
        if "ID" in m:
            ids = self.df[self.subid.get()]
            y = self.df[self.xvar.get()]
            id_r, y_r = [], []
            for i, j in zip(ids, y):
                if is_void(i):
                    continue
                if is_number(j):
                    id_r.append(i)
                    y_r.append(float(j))
            self.app.print(
                "子组标识与测量值的有效配对数 = %d。" %
                len(y_r))
            data = grouping_by_labels(y_r, id_r)
        elif "ize" in m:
            y = number_list(self.df[self.xvar.get()])
            size = int(self.subsize.get())
            if size < 2:
                self.error('子组大小输入有误。')
                return
            data = [y[i:i + size] for i in range(0, len(y), size)]
            if len(y) % size > 0:
                self.app.print("警告：子组大小不相等。")
        else:
            data = number_list(self.df[self.xvar.get()])

        alpha = self.alpha.get()
        if alpha > 0.5 or alpha <= 0:
            alpha = 0.05

        use_range = "ange" in self.subm.get()

        lsl, tgt, usl = self.lsl.get(), self.target.get(), self.usl.get()
        if lsl < tgt < usl:
            pass
        else:
            self.error('规格限输入有误。')
            return

        pf = self.app.showPlotViewer()
        pf.ax = pf.fig.add_subplot(111)

        self.app.print(f"分析变量：{self.xvar.get()}。")
        cpk_plot(
            data,
            lsl,
            tgt,
            usl,
            print_out=True,
            print_port=self.app.print,
            xlabel=self.xlabel.get() if self.xlabel.get() != "" else self.xvar.get(),
            use_range=use_range,
            alpha=alpha,
            ax=pf.ax,
            show_legend=self.show_legend.get(),
            show_within=self.show_within.get(),
            show_spec=self.show_spec.get())

        self.remember_columns(roles=None if "ID" in m else ("xvar",))
        return


class TIDialog(Dialogs):
    column_roles = (('xvar', True),)

    def createWidgets(self, m):
        f = tk.LabelFrame(m, text='样本值')
        f.pack(side=TOP, fill=BOTH, padx=2)
        self.xvar = tk.StringVar(value="")
        w = ttk.Combobox(
            f, values=self.cols, textvariable=self.xvar,
            width=14)
        w.pack(side=LEFT, padx=2)

        master = tk.LabelFrame(m, text='汇总数据（优先使用）')
        master.pack(side=TOP, fill=BOTH, padx=2)
        self.sample_mean = tk.StringVar(value="")
        self.sample_std = tk.StringVar(value="")
        self.sample_n = tk.StringVar(value="")
        w = tk.Label(master, text="N")
        w.pack(side=LEFT, fill=X, padx=2)
        w = tk.Entry(master, textvariable=self.sample_n,
                     bg='white', width=5)
        w.pack(side=LEFT, padx=2, pady=2)
        w = tk.Label(master, text='标准差')
        w.pack(side=LEFT, fill=X, padx=2)
        w = tk.Entry(master, textvariable=self.sample_std,
                     bg='white', width=5)
        w.pack(side=LEFT, padx=2, pady=2)
        w = tk.Label(master, text='均值')
        w.pack(side=LEFT, fill=X, padx=2)
        w = tk.Entry(master, textvariable=self.sample_mean,
                     bg='white', width=5)
        w.pack(side=LEFT, padx=2, pady=2)

        #  w = tk.Label(
        #      m,
        #      anchor="e",
        #      justify=LEFT,
        #      wraplength=300,
        #      text="Computes an interval that contains at least the specified" +
        #      " proportion of the population with (1-alpha) confidence, assuming" +
        #      " Normal Distribution.")
        #  w.pack(side=TOP, fill=BOTH, padx=2)

        master = tk.LabelFrame(m, text='比例设置')
        master.pack(side=TOP, fill=BOTH, padx=2)
        self.prop = tk.DoubleVar(value=0.9)
        w = tk.Label(master, text='指定要覆盖的总体比例')
        w.pack(side=LEFT, fill=X, padx=2)
        w = tk.Entry(master, textvariable=self.prop,
                     bg='white', width=5)
        w.pack(side=LEFT, padx=2, pady=2)

        self.add_alpha(m)
        return

    def apply(self):
        try:
            data = number_list(self.df[self.xvar.get()])
        except BaseException:
            data = None

        alpha = self.alpha.get()
        if alpha > 0.5 or alpha <= 0:
            alpha = 0.05
        std = get_number(self.sample_std)
        n = get_number(self.sample_n)
        mean = get_number(self.sample_mean)
        P = self.prop.get()
        if P > 1 or P <= 0:
            P = 0.9

        self.app.print(f"分析变量：{self.xvar.get() if None in [mean, n, std] else '汇总数据（未指定变量名）'}。")
        result = ti_norm(data=data, sample_n=n, sample_std=std,
                sample_mean=mean, alpha=alpha,
                P=P, print_out=True, print_port=self.app.print)

        if result is not None and None in [mean, n, std]:
            self.remember_columns()
        return
