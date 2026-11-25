import tkinter as tk
from tkinter import TOP, BOTH, LEFT, X, ttk
from math import isfinite
###################################
#  from pandastable_local.dialogs import addListBox
########### Own Modules ###########
from dialog import Dialogs, addListBox
from utilities import number_list, get_number, event_count, number_2lists
from t_test import t_test_1sample, z_test_1sample, t_test_2samples, paired_t_test
from chi_sq import var_1sample, multi_pop_var_test
from proportion_test import prop_test_1sample, prop_2sample, integer_count


class Mean1SampleDialog(Dialogs):
    column_roles = (('xvar', True),)

    def createWidgets(self, m):
        """Create a set of grp-agg-func options together"""
        #  w = tk.Label(
        #      m, anchor="e", justify=LEFT, wraplength=300,
        #      text="Calculated probability of the population where the samples came " +
        #      "from has its mean equal to the hypothesized mean. When hypothesized " +
        #      "standard deviation given, Z-test will be performed, otherwise, " +
        #      "t-test will be performed.")
        #  w.pack(side=TOP, fill=BOTH, padx=2)
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

        master = tk.LabelFrame(m, text='假设检验')
        master.pack(side=TOP, fill=BOTH, padx=2)
        self.u0 = tk.StringVar(value="")
        w = tk.Label(master, text='均值')
        w.pack(side=LEFT, fill=X, padx=2)
        w = tk.Entry(master, textvariable=self.u0,
                     bg='white', width=5)
        w.pack(side=LEFT, padx=2, pady=2)
        self.add_alpha(m)
        return

    def apply(self):
        if len(self.xvar.get()) > 0:
            x = number_list(self.df[self.xvar.get()],
                            col_name=self.xvar.get(),
                            print_out=True, print_port=self.app.print)
        else:
            x = None

        mean = get_number(self.sample_mean)
        std = get_number(self.sample_std)
        n = get_number(self.sample_n)
        u0 = get_number(self.u0)
        alpha = get_number(self.alpha)

        if mean is None or std is None or n is None:
            if x is None:
                return
            mean = std = n = None
        else:
            x = []
        if u0 is None:
            return
        if ((n is None and (len(x) < 2 or len(set(x)) < 2))
                or (n is not None and (not isfinite(n) or not n.is_integer()
                                      or n < 2 or not isfinite(mean)
                                      or not isfinite(std) or std <= 0))
                or not isfinite(u0) or alpha is None
                or not isfinite(alpha) or not 0 < alpha < 1):
            self.error('t 检验要求整数 N ≥ 2、有限正标准差且 0 < α < 1。')
            return
        t_test_1sample(x, u0, print_out=True,
                       sample_mean=mean, sample_n=n,
                       sample_std=std, alpha=alpha,
                       print_port=self.app.print)
        if x:
            self.remember_columns()
        return


class Mean1SampleZDialog(Dialogs):
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
        self.sample_n = tk.StringVar(value="")
        w = tk.Label(master, text="N")
        w.pack(side=LEFT, fill=X, padx=2)
        w = tk.Entry(master, textvariable=self.sample_n,
                     bg='white', width=5)
        w.pack(side=LEFT, padx=2, pady=2)
        w = tk.Label(master, text='均值')
        w.pack(side=LEFT, fill=X, padx=2)
        w = tk.Entry(master, textvariable=self.sample_mean,
                     bg='white', width=5)
        w.pack(side=LEFT, padx=2, pady=2)

        master = tk.LabelFrame(m, text='假设检验')
        master.pack(side=TOP, fill=BOTH, padx=2)
        self.u0 = tk.StringVar(value="")
        self.s0 = tk.StringVar(value="")
        w = tk.Label(master, text='均值')
        w.pack(side=LEFT, fill=X, padx=2)
        w = tk.Entry(master, textvariable=self.u0,
                     bg='white', width=5)
        w.pack(side=LEFT, padx=2, pady=2)
        master = tk.LabelFrame(m, text='已知参数')
        master.pack(side=TOP, fill=BOTH, padx=2)
        w = tk.Label(master, text='标准差')
        w.pack(side=LEFT, fill=X, padx=2)
        w = tk.Entry(master, textvariable=self.s0,
                     bg='white', width=5)
        w.pack(side=LEFT, padx=2, pady=2)

        self.add_alpha(m)
        return

    def apply(self):
        if len(self.xvar.get()) > 0:
            x = number_list(self.df[self.xvar.get()],
                            col_name=self.xvar.get(),
                            print_out=True, print_port=self.app.print)
        else:
            x = None

        mean = get_number(self.sample_mean)
        n = get_number(self.sample_n)
        u0 = get_number(self.u0)
        s0 = get_number(self.s0)

        if mean is None or n is None:
            if x is None:
                return
            mean = n = None
        else:
            x = []
        if u0 is None or s0 is None:
            return
        alpha = get_number(self.alpha)
        if (not isfinite(u0) or not isfinite(s0) or s0 <= 0
                or (n is None and not x)
                or (n is not None and (not isfinite(n) or not n.is_integer()
                                       or n < 1 or not isfinite(mean)))
                or alpha is None or not isfinite(alpha) or not 0 < alpha < 1):
            self.error('Z 检验要求整数 N ≥ 1、有限正已知标准差且 0 < α < 1。')
            return
        z_test_1sample(x, u0, s0, print_out=True,
                       sample_mean=mean, sample_n=n,
                       alpha=alpha,
                       print_port=self.app.print)
        if x:
            self.remember_columns()
        return


class Var1SampleDialog(Dialogs):
    column_roles = (('xvar', True),)

    def createWidgets(self, m):
        """Create a set of grp-agg-func options together"""
        f = tk.LabelFrame(m, text='样本值')
        f.pack(side=TOP, fill=BOTH, padx=2)
        self.xvar = tk.StringVar(value="")
        w = ttk.Combobox(
            f, values=self.cols, textvariable=self.xvar,
            width=14)
        w.pack(side=LEFT, padx=2)

        master = tk.LabelFrame(m, text='汇总数据（优先使用）')
        master.pack(side=TOP, fill=BOTH, padx=2)
        self.sample_n = tk.StringVar(value="")
        self.sample_std = tk.StringVar(value="")
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

        master = tk.LabelFrame(m, text='假设检验')
        master.pack(side=TOP, fill=BOTH, padx=2)
        self.s0 = tk.StringVar(value="")
        w = tk.Label(master, text='标准差')
        w.pack(side=LEFT, fill=X, padx=2)
        w = tk.Entry(master, textvariable=self.s0,
                     bg='white', width=5)
        w.pack(side=LEFT, padx=2, pady=2)
        self.add_alpha(m)
        return

    def apply(self):
        if len(self.xvar.get()) > 0:
            x = number_list(self.df[self.xvar.get()],
                            col_name=self.xvar.get(),
                            print_out=True, print_port=self.app.print)
        else:
            x = None

        std = get_number(self.sample_std)
        n = get_number(self.sample_n)
        s0 = get_number(self.s0)
        alpha = get_number(self.alpha)

        if std is None or n is None:
            if x is None:
                return
            std = n = None
        else:
            x = None
        if s0 is None:
            return
        var_1sample(data=x, s0=s0, print_out=True,
                    sample_n=n, sample_std=std, alpha=alpha,
                    print_port=self.app.print)
        if x:
            self.remember_columns()
        return


class Mean2SampleDialog(Dialogs):
    column_roles = (('xvar', True), ('yvar', True))

    def createWidgets(self, m):
        """Create a set of grp-agg-func options together"""
        master = tk.LabelFrame(m, text='样本值')
        master.pack(side=TOP, fill=BOTH, padx=2)
        self.xvar = tk.StringVar(value="")
        self.yvar = tk.StringVar(value="")
        w = tk.Label(master, text='样本 1')
        w.pack(side=LEFT, fill=X, padx=2)
        w = ttk.Combobox(
            master, values=self.cols, textvariable=self.xvar,
            width=14)
        w.pack(side=LEFT, padx=2)
        w = tk.Label(master, text='样本 2')
        w.pack(side=LEFT, fill=X, padx=2)
        w = ttk.Combobox(
            master, values=self.cols, textvariable=self.yvar,
            width=14)
        w.pack(side=LEFT, padx=2)

        f = tk.LabelFrame(m, text='汇总数据（优先使用）')
        f.pack(side=TOP, fill=BOTH, padx=2)
        master = tk.LabelFrame(f, text='样本 1')
        master.pack(side=TOP, fill=BOTH, padx=2)
        self.u1 = tk.StringVar(value="")
        self.s1 = tk.StringVar(value="")
        self.n1 = tk.StringVar(value="")
        w = tk.Label(master, text="N")
        w.pack(side=LEFT, fill=X, padx=2)
        w = tk.Entry(master, textvariable=self.n1,
                     bg='white', width=5)
        w.pack(side=LEFT, padx=2, pady=2)
        w = tk.Label(master, text='标准差')
        w.pack(side=LEFT, fill=X, padx=2)
        w = tk.Entry(master, textvariable=self.s1,
                     bg='white', width=5)
        w.pack(side=LEFT, padx=2, pady=2)
        w = tk.Label(master, text='均值（u1）')
        w.pack(side=LEFT, fill=X, padx=2)
        w = tk.Entry(master, textvariable=self.u1,
                     bg='white', width=5)
        w.pack(side=LEFT, padx=2, pady=2)
        master = tk.LabelFrame(f, text='样本 2')
        master.pack(side=TOP, fill=BOTH, padx=2)
        self.u2 = tk.StringVar(value="")
        self.s2 = tk.StringVar(value="")
        self.n2 = tk.StringVar(value="")
        w = tk.Label(master, text="N")
        w.pack(side=LEFT, fill=X, padx=2)
        w = tk.Entry(master, textvariable=self.n2,
                     bg='white', width=5)
        w.pack(side=LEFT, padx=2, pady=2)
        w = tk.Label(master, text='标准差')
        w.pack(side=LEFT, fill=X, padx=2)
        w = tk.Entry(master, textvariable=self.s2,
                     bg='white', width=5)
        w.pack(side=LEFT, padx=2, pady=2)
        w = tk.Label(master, text='均值（u2）')
        w.pack(side=LEFT, fill=X, padx=2)
        w = tk.Entry(master, textvariable=self.u2,
                     bg='white', width=5)
        w.pack(side=LEFT, padx=2, pady=2)

        master = tk.LabelFrame(m, text='假设检验')
        master.pack(side=TOP, fill=BOTH, padx=2)
        self.d0 = tk.StringVar(value="0")
        w = tk.Label(master, text="u2 - u1 = ")
        w.pack(side=LEFT, fill=X, padx=2)
        w = tk.Entry(master, textvariable=self.d0,
                     bg='white', width=5)
        w.pack(side=LEFT, padx=2, pady=2)
        self.pooled = tk.BooleanVar(value=False)
        w = tk.Checkbutton(master, text='假定方差相等',
                           variable=self.pooled)
        w.pack(side=LEFT, padx=2, pady=2)

        self.add_alpha(m)
        return

    def apply(self):
        if len(self.xvar.get()) > 0:
            x = number_list(self.df[self.xvar.get()],
                            col_name=self.xvar.get(),
                            print_out=True, print_port=self.app.print)
        else:
            x = None

        if len(self.yvar.get()) > 0:
            y = number_list(self.df[self.yvar.get()],
                            col_name=self.yvar.get(),
                            print_out=True, print_port=self.app.print)
        else:
            y = None

        u1 = get_number(self.u1)
        s1 = get_number(self.s1)
        n1 = get_number(self.n1)
        u2 = get_number(self.u2)
        s2 = get_number(self.s2)
        n2 = get_number(self.n2)
        d0 = get_number(self.d0)

        alpha = get_number(self.alpha)
        pooled = self.pooled.get()

        t_test_2samples(l1=x, l2=y, print_out=True,
                        u1=u1, u2=u2, s1=s1, s2=s2,
                        n1=n1, n2=n2,
                        d0=d0 if d0 is not None else 0,
                        alpha=alpha, pooled=pooled,
                        print_port=self.app.print)
        self.remember_columns(roles=[name for name, raw in (
            ('xvar', None in [u1, s1, n1]), ('yvar', None in [u2, s2, n2])) if raw])
        return


class PairedTDialog(Dialogs):
    column_roles = (('xvar', True), ('yvar', True))

    def createWidgets(self, m):
        master = tk.LabelFrame(m, text='样本值')
        master.pack(side=TOP, fill=BOTH, padx=2)
        self.xvar = tk.StringVar(value="")
        self.yvar = tk.StringVar(value="")
        w = tk.Label(master, text='样本 1')
        w.pack(side=LEFT, fill=X, padx=2)
        w = ttk.Combobox(
            master, values=self.cols, textvariable=self.xvar,
            width=14)
        w.pack(side=LEFT, padx=2)
        w = tk.Label(master, text='样本 2')
        w.pack(side=LEFT, fill=X, padx=2)
        w = ttk.Combobox(
            master, values=self.cols, textvariable=self.yvar,
            width=14)
        w.pack(side=LEFT, padx=2)

        master = tk.LabelFrame(
            m, text='假设差值均值')
        master.pack(side=TOP, fill=BOTH, padx=2)
        self.d0 = tk.StringVar(value="0")
        w = tk.Label(master, text='样本 1 - 样本 2')
        w.pack(side=LEFT, fill=X, padx=2)
        w = tk.Entry(master, textvariable=self.d0,
                     bg='white', width=5)
        w.pack(side=LEFT, padx=2, pady=2)

        self.add_alpha(m)
        return

    def apply(self):
        if len(self.xvar.get()) > 0 and len(self.yvar.get()) > 0:
            x, y = number_2lists(self.df[self.xvar.get()], self.df[self.yvar.get()],
                                 col_name2=self.yvar.get(),
                                 col_name1=self.xvar.get(),
                                 print_out=True, print_port=self.app.print)
        else:
            self.error(msg='输入的样本值无效。')
            return
        #      x = number_list(self.df[self.xvar.get()],
        #                      col_name=self.xvar.get(),
        #                      print_out=True, print_port=self.app.print)
        #  else:
        #      x = None
        #
        #  if len(self.yvar.get()) > 0:
        #      y = number_list(self.df[self.yvar.get()],
        #                      col_name=self.yvar.get(),
        #                      print_out=True, print_port=self.app.print)
        #  else:
        #      y = None

        alpha = get_number(self.alpha)
        u0 = get_number(self.d0)

        paired_t_test(l1=x, l2=y, print_out=True,
                      alpha=alpha, u0=u0,
                      print_port=self.app.print)
        self.remember_columns()
        return


class MultiVarDialog(Dialogs):
    column_roles = (('grpvar', True),)

    def createWidgets(self, m):
        f = tk.LabelFrame(m, text='变量')
        f.pack(side=TOP, fill=BOTH, padx=2)
        w, self.grpvar = addListBox(
            f, values=self.cols, width=20, label='列')
        w.pack(side=LEFT, fill=X, padx=10)

        self.bartlett = tk.BooleanVar(m, False)
        ttk.Checkbutton(m, text='附加 Bartlett 全局检验（正态总体）',
                        variable=self.bartlett).pack(anchor='w')
        self.mc = tk.BooleanVar(m, False)
        ttk.Checkbutton(m, text='附加图形多重比较（至少三组）', variable=self.mc).pack(anchor='w')
        self.add_alpha(m)
        return

    def ok(self):
        self.grpcols = self.grpvar.getSelectedItem()
        self.quit()
        self.apply()
        return

    def apply(self):

        data = []
        for col in self.grpcols:
            data.append(
                number_list(
                    self.df[col],
                    col_name=col,
                    print_out=True,
                    print_port=self.app.print))
        try:
            alpha = self.alpha.get()
        except BaseException:
            alpha = 0.05

        if len(data) < 2 or any(len(group) < 3 for group in data):
            self.error('请选择至少两组，每组至少三个有效观测。')
            return
        if self.bartlett.get():
            from scipy.stats import bartlett
            from statistics import variance
            if any(variance(group) <= 0 for group in data):
                self.error('Bartlett 检验需要所有组的样本方差均为正。')
                return
            result = bartlett(*data)
            self.app.print(f'Bartlett 全局方差检验（假设独立正态总体）\n'
                           f'χ² = {result.statistic:.6g}，df = {len(data)-1}，p = {result.pvalue:.6g}')
        if self.mc.get():
            from chi_sq import equal_variances_mc
            from stat_table import StatTable
            try:
                pvalue, intervals = equal_variances_mc(data, alpha)
            except ValueError as exc:
                self.error(str(exc))
                return
            self.app.print(f'Banga–Fox 图形多重比较的全局 p = {pvalue:.6g}。区间用于组间比较。')
            self.app.print(StatTable(title='标准差多重比较区间',
                                    headers=['组别', '下界', '上界'],
                                    values=[(label, *bounds) for label,bounds in zip(self.grpcols,intervals)]))
            self._plot_mc(intervals)
        multi_pop_var_test(data, self.grpcols, print_out=True,
                           print_port=self.app.print,
                           alpha=alpha)
        self.remember_columns()
        return

    def _plot_mc(self, intervals):
        from chart_style import style_axes

        viewer = self.app.showPlotViewer(deferred=True)
        try:
            ax = viewer.fig.add_subplot(111)
            positions = range(len(self.grpcols))
            ax.hlines(positions, intervals[:, 0], intervals[:, 1])
            ax.plot(intervals.ravel(), [i for i in positions for _ in range(2)], '|')
            ax.set(yticks=list(positions), yticklabels=self.grpcols,
                   xlabel='标准差', title='标准差多重比较区间')
            ax.invert_yaxis()
            style_axes(ax)
            viewer.canvas.draw()
            self.app.replacePlotViewer(viewer)
            viewer.main.deiconify()
        except Exception:
            viewer.close()
            raise


class Prop1SDialog(Dialogs):
    def createWidgets(self, m):
        f = tk.LabelFrame(m, text='样本值')
        f.pack(side=TOP, fill=BOTH, padx=2)
        w = tk.Label(f, text='样本')
        w.pack(side=LEFT, fill=X, padx=2)
        self.xvar = tk.StringVar(value="")
        w = ttk.Combobox(
            f, values=self.cols, textvariable=self.xvar,
            width=14)
        w.pack(side=LEFT, padx=2)
        w = tk.Label(f, text='事件名称')
        w.pack(side=LEFT, fill=X, padx=2)
        self.event_name = tk.StringVar(value="")
        w = tk.Entry(f, textvariable=self.event_name,
                     bg='white', width=15)
        w.pack(side=LEFT, padx=2, pady=2)

        master = tk.LabelFrame(m, text='汇总数据（优先使用）')
        master.pack(side=TOP, fill=BOTH, padx=2)
        self.ttl_cnt = tk.StringVar(value="")
        self.event_cnt = tk.StringVar(value="")
        w = tk.Label(master, text='事件数')
        w.pack(side=LEFT, fill=X, padx=2)
        w = tk.Entry(master, textvariable=self.event_cnt,
                     bg='white', width=5)
        w.pack(side=LEFT, padx=2, pady=2)
        w = tk.Label(master, text='试验次数')
        w.pack(side=LEFT, fill=X, padx=2)
        w = tk.Entry(master, textvariable=self.ttl_cnt,
                     bg='white', width=5)
        w.pack(side=LEFT, padx=2, pady=2)

        master = tk.LabelFrame(m, text='假设检验')
        master.pack(side=TOP, fill=BOTH, padx=2)
        self.p0 = tk.DoubleVar(value=0.5)
        w = tk.Label(master, text='假设比例')
        w.pack(side=LEFT, fill=X, padx=2)
        w = tk.Entry(master, textvariable=self.p0,
                     bg='white', width=5)
        w.pack(side=LEFT, padx=2, pady=2)
        self.add_alpha(m)
        return

    def apply(self):
        if len(self.xvar.get()) > 0:
            x = list(self.df[self.xvar.get()])
        else:
            x = None

        p0 = get_number(self.p0)
        event_cnt = get_number(self.event_cnt)
        ttl_cnt = get_number(self.ttl_cnt)
        event_name = self.event_name.get()
        alpha = get_number(self.alpha)

        if event_cnt is None or ttl_cnt is None:
            if x is None:
                return
            ttl_cnt, event_cnt = event_count(x, event_name)

        if p0 is None:
            return

        if not 0 < p0 < 1:
            self.error('假设比例 p0 必须大于 0 且小于 1。')
            return
        N, events = integer_count(ttl_cnt), integer_count(event_cnt)
        if N is None or events is None or N < 1 or not 0 <= events <= N:
            self.error('试验次数必须为正整数，事件数必须是不超过试验次数的非负整数。')
            return

        prop_test_1sample(N=N, events=events,
                          p0=p0, alpha=alpha, print_out=True,
                          print_port=self.app.print)
        return


class Prop2SDialog(Dialogs):
    def createWidgets(self, m):
        f = tk.LabelFrame(m, text='样本 1')
        f.pack(side=TOP, fill=BOTH, padx=2)
        self.xvar = tk.StringVar(value="")
        w = tk.Label(f, text='数据列')
        w.pack(side=LEFT, fill=X, padx=2)
        w = ttk.Combobox(
            f, values=self.cols, textvariable=self.xvar,
            width=14)
        w.pack(side=LEFT, padx=2)
        self.event_name = tk.StringVar(value="")
        w = tk.Label(f, text='事件名称')
        w.pack(side=LEFT, fill=X, padx=2)
        w = tk.Entry(f, textvariable=self.event_name,
                     bg='white', width=15)
        w.pack(side=LEFT, padx=2, pady=2)

        f = tk.LabelFrame(m, text='样本 2')
        f.pack(side=TOP, fill=BOTH, padx=2)
        w = tk.Label(f, text='数据列')
        w.pack(side=LEFT, fill=X, padx=2)
        self.yvar = tk.StringVar(value="")
        w = ttk.Combobox(
            f, values=self.cols, textvariable=self.yvar,
            width=14)
        w.pack(side=LEFT, padx=2)
        self.event_name2 = tk.StringVar(value="")
        w = tk.Label(f, text='事件名称')
        w.pack(side=LEFT, fill=X, padx=2)
        w = tk.Entry(f, textvariable=self.event_name2,
                     bg='white', width=15)
        w.pack(side=LEFT, padx=2, pady=2)

        master = tk.LabelFrame(m, text='样本 1 汇总数据（优先使用）')
        master.pack(side=TOP, fill=BOTH, padx=2)
        self.ttl_cnt = tk.StringVar(value="")
        self.event_cnt = tk.StringVar(value="")
        w = tk.Label(master, text='事件数')
        w.pack(side=LEFT, fill=X, padx=2)
        w = tk.Entry(master, textvariable=self.event_cnt,
                     bg='white', width=5)
        w.pack(side=LEFT, padx=2, pady=2)
        w = tk.Label(master, text='试验次数')
        w.pack(side=LEFT, fill=X, padx=2)
        w = tk.Entry(master, textvariable=self.ttl_cnt,
                     bg='white', width=5)
        w.pack(side=LEFT, padx=2, pady=2)

        master = tk.LabelFrame(m, text='样本 2 汇总数据（优先使用）')
        master.pack(side=TOP, fill=BOTH, padx=2)
        self.ttl_cnt2 = tk.StringVar(value="")
        self.event_cnt2 = tk.StringVar(value="")
        w = tk.Label(master, text='事件数')
        w.pack(side=LEFT, fill=X, padx=2)
        w = tk.Entry(master, textvariable=self.event_cnt2,
                     bg='white', width=5)
        w.pack(side=LEFT, padx=2, pady=2)
        w = tk.Label(master, text='试验次数')
        w.pack(side=LEFT, fill=X, padx=2)
        w = tk.Entry(master, textvariable=self.ttl_cnt2,
                     bg='white', width=5)
        w.pack(side=LEFT, padx=2, pady=2)

        self.add_alpha(m)
        return

    def apply(self):
        if len(self.xvar.get()) > 0:
            x = list(self.df[self.xvar.get()])
        else:
            x = None
        if len(self.yvar.get()) > 0:
            y = list(self.df[self.yvar.get()])
        else:
            y = None
        event_cnt = get_number(self.event_cnt)
        ttl_cnt = get_number(self.ttl_cnt)
        event_cnt2 = get_number(self.event_cnt2)
        ttl_cnt2 = get_number(self.ttl_cnt2)
        event_name = self.event_name.get()
        event_name2 = self.event_name2.get()
        alpha = get_number(self.alpha)

        if event_cnt is None or ttl_cnt is None:
            if x is None:
                return
            ttl_cnt, event_cnt = event_count(x, event_name)

        if event_cnt2 is None or ttl_cnt2 is None:
            if y is None:
                return
            ttl_cnt2, event_cnt2 = event_count(y, event_name2)

        counts = [(integer_count(ttl_cnt), integer_count(event_cnt)),
                  (integer_count(ttl_cnt2), integer_count(event_cnt2))]
        if any(n is None or e is None or n < 1 or not 0 <= e <= n for n, e in counts):
            self.error('试验次数必须为正整数，事件数必须是不超过试验次数的非负整数。')
            return

        (n1, e1), (n2, e2) = counts
        prop_2sample(n1=n1, e1=e1, n2=n2, e2=e2,
                     alpha=alpha, print_out=True,
                     print_port=self.app.print)
        return

class PoissonRateDialog(Dialogs):
    groups = 1

    def createWidgets(self, master):
        self.counts, self.exposures = [], []
        for i in range(self.groups):
            row = ttk.LabelFrame(master, text=f'样本 {i+1}')
            row.pack(fill=X, padx=4, pady=3)
            for label, variables in (('事件数', self.counts), ('暴露量', self.exposures)):
                value = tk.StringVar(master)
                variables.append(value)
                ttk.Label(row, text=label).pack(side=LEFT, padx=4)
                ttk.Entry(row, textvariable=value, width=12).pack(side=LEFT)
        self.unit, self.null = tk.StringVar(master), tk.StringVar(master, value='1')
        self.direction = tk.StringVar(master, value='双侧')
        self.method = tk.StringVar(master, value='精确')
        fields = (
            ('暴露量单位', self.unit, ()),
            ('假设率' if self.groups == 1 else '假设率比（样本 1 / 样本 2）', self.null, ()),
            ('备择方向', self.direction, ('双侧', '小于', '大于')),
            ('检验方法', self.method, ('精确', '正态近似')),
        )
        for label, variable, values in fields:
            row = ttk.Frame(master)
            row.pack(fill=X, padx=4, pady=3)
            ttk.Label(row, text=label).pack(side=LEFT, padx=4)
            if values:
                ttk.Combobox(row, textvariable=variable, values=values,
                             state='readonly', width=12).pack(side=LEFT)
            else:
                ttk.Entry(row, textvariable=variable, width=14).pack(side=LEFT)
        self.add_alpha(master)

    def ok(self):
        from proportion_test import poisson_rate
        try:
            null = float(self.null.get())
            alpha = float(self.alpha.get())
            result = poisson_rate(
                [v.get() for v in self.counts], [v.get() for v in self.exposures],
                null, alpha, {'双侧': 'two-sided', '小于': 'less', '大于': 'greater'}[self.direction.get()],
                'exact' if self.method.get() == '精确' else 'normal',
            )
        except (ValueError, OverflowError, tk.TclError) as exc:
            self.error(f'请检查输入。{exc}')
            return

        def interval_text(interval):
            return '不可估计' if interval is None else f'[{interval[0]:.6g}, {interval[1]:.6g}]'

        unit = self.unit.get().strip() or '暴露单位'
        lines = [f'泊松率检验（{self.method.get()}，{self.direction.get()}）']
        for i, rate in enumerate(result['rates'], 1):
            lines.append(f'样本 {i} 率：{rate:.6g} 事件/{unit}')
            if self.groups == 2:
                lines.append(f'精确率区间：{interval_text(result["rate_intervals"][i-1])}')
        if self.groups == 2:
            ratio = result['ratio']
            lines.append('率比：不可估计（两组均无事件）' if ratio is None else f'率比：{ratio:.6g}')
            lines.append(f'率差：{result["difference"]:.6g} 事件/{unit}')
            lines.append(f'率差正态近似区间：{interval_text(result["difference_ci"])}')
        label = '率' if self.groups == 1 else '率比'
        lines.append(f'{1-alpha:.1%} {label}区间：{interval_text(result["interval"])}')
        statistic = '事件数' if self.method.get() == '精确' else 'Z'
        lines.append(f'假设{label} = {null:.6g}，{statistic} = {result["statistic"]:.6g}，p = {result["pvalue"]:.6g}')
        self.app.print('\n'.join(lines))
        self.quit()


class PoissonRate2Dialog(PoissonRateDialog):
    groups = 2

class BasicPowerDialog(Dialogs):
    methods = {'单样本 t':'t1', '双样本 t':'t2', '单样本 Z':'z1', '双样本 Z':'z2',
               '单样本比例':'p1', '双样本比例':'p2', '单因子方差分析':'anova'}

    def createWidgets(self, master):
        form = ttk.Frame(master)
        form.pack(fill=X)
        self.fields = {}
        specs = [('method','检验','单样本 t',list(self.methods)),
                 ('alternative','备择方向','双侧',['双侧','大于','小于']),
                 ('n','每组样本量','',None), ('target','目标功效','',None),
                 ('effect','效应（均值差或组均值偏差 RMS）','',None),
                 ('sigma','总体标准差','1',None),
                 ('p0','假设比例／组 2 比例','',None),
                 ('p1','备择比例／组 1 比例','',None),
                 ('groups','方差分析组数','2',None)]
        for row, (key, label, default, choices) in enumerate(specs):
            ttk.Label(form,text=label).grid(row=row,column=0,sticky='w',padx=4,pady=2)
            self.fields[key] = var = tk.StringVar(master,value=default)
            widget = (ttk.Entry(form,textvariable=var,width=18) if choices is None else
                      ttk.Combobox(form,textvariable=var,values=choices,state='readonly',width=16))
            widget.grid(row=row,column=1,sticky='ew',padx=4,pady=2)
        alpha_row = ttk.Frame(form)
        alpha_row.grid(row=len(specs),columnspan=2,sticky='ew')
        self.add_alpha(alpha_row)

    def ok(self):
        from basic_power import basic_power
        from chart_style import style_axes
        from stat_table import StatTable
        try:
            f = {key: var.get().strip() for key,var in self.fields.items()}
            method = self.methods[f['method']]
            alternative = {'双侧':'two-sided','大于':'greater','小于':'less'}[f['alternative']]
            options = dict(alpha=float(self.alpha.get()),alternative=alternative)
            if method.startswith('p'):
                options.update(p0=float(f['p0']),p1=float(f['p1']))
            else:
                options.update(sigma=float(f['sigma']))
                if method == 'anova':
                    options['groups'] = int(f['groups'])
            inputs = dict(n=int(f['n']) if f['n'] else None,
                          target=float(f['target']) if f['target'] else None,
                          effect=float(f['effect']) if f['effect'] else None)
            result = basic_power(method, **options, **inputs)
        except (ValueError, tk.TclError) as exc:
            self.error(f'请检查输入。{exc}')
            return
        n, effect, power = (result[key] for key in ('n','effect','power'))
        rows = [[f['method'],f['alternative'],options['alpha'],n,effect,power]]
        self.app.print(StatTable(title='基础功效与样本量',
                                headers=['检验','方向','α','每组样本量','效应','功效'],values=rows))
        if method.startswith('p'):
            self.app.print(f'比例正态近似，比例为 {options["p1"]:.6g} 和 {options["p0"]:.6g}。')
        else:
            self.app.print(f'采用共同标准差 {options["sigma"]:.6g}；方差分析为等组样本量。'
                           if method == 'anova' else f'标准差为 {options["sigma"]:.6g}。')
        minimum = 2 if method in ('t1','t2','anova') else 1
        sizes = sorted({minimum,n, *(max(minimum,round(n*step/20)) for step in range(1,31))})
        if not method.startswith('p'):
            options['effect'] = effect
        powers = [basic_power(method,n=size,**options)['power'] for size in sizes]
        viewer = self.app.showPlotViewer(deferred=True)
        try:
            ax = viewer.fig.add_subplot(111)
            ax.plot(sizes,powers)
            ax.plot(n,power,'o')
            ax.set(xlabel='每组样本量',ylabel='功效',ylim=(0,1),title=f['method']+' 功效曲线')
            style_axes(ax)
            viewer.canvas.draw()
            self.app.replacePlotViewer(viewer)
            viewer.main.deiconify()
        except Exception:
            viewer.close()
            raise
        self.quit()

NONPARAMETRIC_TITLES = {
    "sign": "单样本符号检验",
    "wilcoxon": "单样本 Wilcoxon 符号秩检验",
    "mann": "Mann–Whitney 检验",
    "kruskal": "Kruskal–Wallis 检验",
    "mood": "Mood 中位数检验",
    "friedman": "Friedman 检验",
    "runs": "游程检验",
}


class NonparametricDialog(Dialogs):
    analysis_parameters = (('target', '假设位置或阈值'), ('direction', '备择方向'))
    def __init__(self, parent, df, app, kind):
        self.kind = kind
        self.column_roles = (("samples", True),)
        if kind in ("mann", "kruskal", "mood", "friedman"):
            self.column_roles += (("group", False),)
        if kind == "friedman":
            self.column_roles += (("block", False),)
        super().__init__(parent, df, NONPARAMETRIC_TITLES[kind], app)

    def createWidgets(self, master):
        grouped = self.kind in ("mann", "kruskal", "mood")
        frame, self.samples = addListBox(
            master, [c for c in self.cols if self._column_valid(c, True)],
            width=24, label="样本列（可多选）" if grouped else "观测列",
        )
        if not grouped:
            self.samples.configure(selectmode=tk.BROWSE)
        frame.pack(side=TOP, fill=X)
        if grouped or self.kind == "friedman":
            self.group = self._field(
                master, "分组列（可选）" if grouped else "处理列", values=["", *self.cols]
            )
        if self.kind == "friedman":
            self.block = self._field(master, "区组列", values=self.cols)
        if self.kind in ("sign", "wilcoxon", "runs"):
            self.target = self._field(
                master, "阈值（留空使用中位数）" if self.kind == "runs" else "假设位置",
                default="" if self.kind == "runs" else "0",
            )
        if self.kind in ("sign", "wilcoxon", "mann"):
            self.direction = self._field(master, "备择方向", "双侧", ("双侧", "左侧", "右侧"))
        self.add_alpha(master)

    @staticmethod
    def _field(master, label, default="", values=None):
        row = ttk.Frame(master)
        row.pack(side=TOP, fill=X, padx=3, pady=2)
        ttk.Label(row, text=label).pack(side=LEFT)
        var = tk.StringVar(value=default)
        if values is None:
            widget = ttk.Entry(row, textvariable=var, width=17)
        else:
            widget = ttk.Combobox(row, textvariable=var, values=values,
                                  state="readonly", width=15)
        widget.pack(side=tk.RIGHT)
        return var

    def ok(self):
        if self.apply():
            self.quit()

    def apply(self):
        import math

        from nonparametric_tests import (
            friedman_test, grouped_rank_test, mann_whitney_test, runs_test,
            sign_test, signed_rank_test,
        )
        from stat_table import StatTable

        cols = [self.samples.get(i) for i in self.samples.curselection()]
        alpha = get_number(self.alpha)
        if alpha is None or not 0 < alpha < 1:
            self.error("显著性水平必须介于 0 和 1 之间。")
            return
        kind = self.kind
        grouped = kind in ("mann", "kruskal", "mood")
        if not cols or (not grouped and len(cols) != 1):
            self.error("请选择所需样本列。")
            return
        names = cols
        direction = getattr(self, "direction", None)
        alternative = {"双侧": "two-sided", "左侧": "less", "右侧": "greater"}[
            direction.get() if direction is not None else "双侧"
        ]
        notes = []
        groups = None
        try:
            if grouped:
                group = self.group.get()
                if group:
                    if len(cols) != 1 or group in cols:
                        raise ValueError("分组输入需要一个数值列和一个独立分组列。")
                    entries = list(self.df.groupby(group, sort=False, observed=True)[cols[0]])
                    names = [str(label) for label, _ in entries]
                    samples = [values.to_numpy(dtype=float, na_value=float("nan"))
                               for _, values in entries]
                else:
                    samples = [self.df[col].to_numpy(dtype=float, na_value=float("nan"))
                               for col in cols]
                if kind == "mann":
                    if len(samples) != 2:
                        raise ValueError("Mann–Whitney 检验需要两个独立样本。")
                    result = mann_whitney_test(*samples, alternative=alternative, alpha=alpha)
                    notes.append("估计值采用第一组减第二组。位置差解释要求两组分布仅相差平移。")
                else:
                    result = grouped_rank_test(samples, mood=kind == "mood", alpha=alpha)
                    if kind == "mood":
                        rows = [(name, n, median, above, below, self._interval(interval))
                                for name, (n, median, above, below, interval)
                                in zip(names, result.pop("groups"))]
                        headers = ("组", "N", "中位数", "上侧", "下侧", "中位数置信区间")
                    else:
                        rows = [(name, *row) for name, row in zip(names, result.pop("groups"))]
                        headers = ("组", "N", "中位数", "平均秩")
                    groups = StatTable(title="各组统计", headers=headers, values=rows)
            elif kind == "friedman":
                names = [cols[0], self.group.get(), self.block.get()]
                if len(set(names)) != 3 or not all(names):
                    raise ValueError("请选择三个不同的响应、处理及区组列。")
                result = friedman_test(self.df, *names)
                groups = StatTable(title="处理秩统计", headers=("处理", "秩和", "平均秩"),
                                   values=result.pop("groups"))
            else:
                target = self.target.get().strip()
                target = None if kind == "runs" and not target else float(target)
                if target is not None and not math.isfinite(target):
                    raise ValueError("假设位置或阈值必须为有限数。")
                values = self.df[cols[0]].to_numpy(dtype=float, na_value=float("nan"))
                if kind == "runs":
                    result = runs_test(values, target)
                    notes.append("保留观测顺序，排除阈值相等项。")
                    notes.append("拒绝随机游程假设。" if result["pvalue"] < alpha
                                 else "证据不足以拒绝随机游程假设。")
                else:
                    test = sign_test if kind == "sign" else signed_rank_test
                    result = test(values, target, alternative, alpha)
                    result["target"] = target
                    if kind == "wilcoxon":
                        notes.append("位置推断要求分布对称；排除零差，绝对差并列取平均秩。")
        except (ValueError, TypeError, KeyError) as error:
            self.error(str(error))
            return

        labels = {
            "n": "样本量", "positive": "正差数" if kind == "sign" else "正秩和",
            "negative": "负差数" if kind == "sign" else "负秩和", "zero": "零差数",
            "estimate": "位置估计", "statistic": "检验统计量", "pvalue": "p 值",
            "interval": f"{1-alpha:.1%} 双侧区间", "method": "方法", "df": "自由度",
            "blocks": "区组数", "pooled_median": "合并中位数", "above": "上侧观测数",
            "below": "下侧观测数", "omitted_ties": "排除的相等观测数", "threshold": "阈值",
            "target": "假设位置",
        }
        rows = [(labels[key], self._interval(value) if key == "interval" else value)
                for key, value in result.items()]
        if direction is not None:
            rows.append(("备择方向", direction.get()))
        rows.append(("α", alpha))
        display = [[label, f"{value:.8g}" if isinstance(value, float) else str(value)]
                   for label, value in rows]
        self.app.print(f"\n---- {self.title} ----\n" + "、".join(names))
        for note in notes:
            self.app.print(note)
        self.app.print(StatTable(title=self.title, headers=("项目", "结果"),
                                 values=rows, display=display))
        if groups is not None:
            self.app.print(groups)
        self.remember_columns()
        return True

    @staticmethod
    def _interval(interval):
        if interval is None:
            return "有并列，区间不可用"
        low, high, coverage = interval
        return f"[{low:.8g}, {high:.8g}]（覆盖率 {coverage:.3%}）"


class VarianceRatioDialog(Dialogs):
    column_roles = (("first", True), ("second", True), ("group", False))
    analysis_parameters = (('input_mode', '输入方式'), ('method', '方法'), ('scale', '比值尺度'),
                           ('target', '假设比值'), ('direction', '备择方向'))

    def createWidgets(self, master):
        field = NonparametricDialog._field
        self.input_mode = field(master, "输入", "两个样本列", ("两个样本列", "数值列和分组列", "汇总"))
        self.first = field(master, "第一样本／数值列", values=["", *self.cols])
        self.second = field(master, "第二样本列", values=["", *self.cols])
        self.group = field(master, "分组列", values=["", *self.cols])
        self.summary_scale = field(master, "汇总离散度", "标准差", ("标准差", "方差"))
        self.summary_n = [field(master, f"样本 {i} 数量") for i in (1, 2)]
        self.summary_value = [field(master, f"样本 {i} 离散度") for i in (1, 2)]
        self.method = field(master, "方法", "经典 F", ("经典 F", "Bonett", "Levene"))
        self.scale = field(master, "比较尺度", "方差比", ("方差比", "标准差比"))
        self.target = field(master, "假设比值", "1")
        self.direction = field(master, "备择方向", "双侧", ("双侧", "左侧", "右侧"))
        self.add_alpha(master)

    def ok(self):
        if self.apply():
            self.quit()

    def analysis_column_selection(self):
        if self.input_mode.get() == "汇总":
            return {}
        selection = super().analysis_column_selection()
        key = "group" if self.input_mode.get() == "数值列和分组列" else "second"
        return {"first": selection["first"], key: selection[key]}

    def apply(self):
        from chi_sq import variance_ratio_test
        from stat_table import StatTable

        mode = self.input_mode.get()
        method = self.method.get().replace("经典 ", "")
        alternative = {"双侧": "two-sided", "左侧": "less", "右侧": "greater"}[self.direction.get()]
        scale = "std" if self.scale.get() == "标准差比" else "variance"
        target = get_number(self.target)
        alpha = get_number(self.alpha)
        names = [self.first.get(), self.second.get()]
        samples = summary = None
        try:
            if target is None or alpha is None:
                raise ValueError("请输入假设比值及显著性水平。")
            if mode == "汇总":
                values = [float(v.get()) for v in self.summary_value]
                if any(v <= 0 for v in values):
                    raise ValueError("汇总离散度须为正数。")
                if self.summary_scale.get() == "标准差":
                    values = [v*v for v in values]
                summary = [(float(n.get()), v) for n, v in zip(self.summary_n, values)]
                names = ["样本 1", "样本 2"]
            elif mode == "数值列和分组列":
                response, group = names[0], self.group.get()
                if response == group or not self._column_valid(response, True) or group not in self.cols:
                    raise ValueError("请选择不同的数值列和分组列。")
                rows = list(self.df.groupby(group, sort=False, observed=True)[response])
                if len(rows) != 2:
                    raise ValueError("分组列必须恰有两个组。")
                names = [str(label) for label, _ in rows]
                samples = [x.to_numpy(dtype=float, na_value=float("nan")) for _, x in rows]
            else:
                if len(set(names)) != 2 or not all(self._column_valid(c, True) for c in names):
                    raise ValueError("请选择两个不同的数值列。")
                samples = [self.df[c].to_numpy(dtype=float, na_value=float("nan")) for c in names]
            res = variance_ratio_test(samples, summary=summary, method=method, target=target,
                                      scale=scale, alternative=alternative, alpha=alpha)
        except (ValueError, TypeError, OverflowError) as error:
            self.error(str(error))
            return False
        self.app.print("\n---- 双样本离散度检验 ----")
        notes = {
            "F": "经典 F 检验假设两总体正态且样本独立。",
            "Bonett": "Bonett 使用假设比值下的合并峰度，适用于等样本量、分布形状相近的独立样本。",
            "Levene": "Levene 使用组中位数绝对偏差并按假设比调整；比值推断要求组分布形状相近。",
        }
        self.app.print(notes[method])
        self.app.print(StatTable(title="样本离散度", headers=("样本", "N", "方差", "标准差"),
                                 values=[(name, n, v, v**.5)
                                         for name, n, v in zip(names, res["n"], res["variances"])]))
        low, high = res["interval"]
        self.app.print(StatTable(
            title="双样本离散度检验",
            headers=("方法", "尺度", "备择", "估计比值", "假设比值", "统计量", "p 值", "置信区间"),
            values=[(method, self.scale.get(), self.direction.get(), res["estimate"], target,
                     res["statistic"], res["pvalue"], f"{1-alpha:.1%} [{low:.6g}, {high:.6g}]")],
        ))
        self.remember_columns()
        return True


EQUIVALENCE_TITLES = {
    "one": "单样本等效性检验",
    "independent": "双独立样本等效性检验",
    "paired": "配对样本等效性检验",
}


class EquivalenceDialog(Dialogs):
    analysis_parameters = (('target', '目标'), ('lower', '等效下限'), ('upper', '等效上限'),
                           ('method', '方法'), ('direction', '差值方向'))
    def __init__(self, parent, df, app, kind):
        self.kind = kind
        self.column_roles = (("first", True),)
        if kind != "one":
            self.column_roles += (("second", True),)
        super().__init__(parent, df, EQUIVALENCE_TITLES[kind], app)

    def createWidgets(self, master):
        field = NonparametricDialog._field
        self.first = field(master, "样本列" if self.kind == "one" else "第一样本列", values=self.cols)
        if self.kind == "one":
            self.target = field(master, "目标值", "0")
        else:
            self.second = field(master, "第二样本列", values=self.cols)
            self.direction = field(master, "差值方向", "第二列减第一列", ("第二列减第一列", "第一列减第二列"))
        if self.kind == "independent":
            self.method = field(master, "方法", "Welch", ("Welch", "等方差"))
        self.lower = field(master, "等效下限")
        self.upper = field(master, "等效上限")
        self.add_alpha(master)

    def ok(self):
        if self.apply():
            self.quit()

    def apply(self):
        from chart_style import style_axes
        from stat_table import StatTable
        from t_test import equivalence_tost

        names = [self.first.get()]
        if self.kind != "one":
            names.append(self.second.get())
            if self.direction.get() == "第一列减第二列":
                names.reverse()
        lower, upper, alpha = map(get_number, (self.lower, self.upper, self.alpha))
        target = get_number(self.target) if self.kind == "one" else 0.
        if len(set(names)) != len(names) or not all(self._column_valid(c, True) for c in names):
            self.error("请选择所需的不同数值列。")
            return False
        if None in (lower, upper, alpha, target):
            self.error("请输入目标值、等效界限和显著性水平。")
            return False
        pooled = self.kind == "independent" and self.method.get() == "等方差"
        try:
            res = equivalence_tost(
                *(self.df[c].to_numpy(dtype=float, na_value=float("nan")) for c in names),
                lower=lower, upper=upper, alpha=alpha, target=target,
                paired=self.kind == "paired", pooled=pooled,
            )
        except (ValueError, OverflowError) as error:
            self.error(str(error))
            return False

        lo, hi = res["interval"]
        estimate = res["estimate"]
        viewer = self.app.showPlotViewer(deferred=True)
        try:
            ax = viewer.fig.add_subplot(111)
            ax.axvspan(lower, upper, alpha=.15, color="tab:green")
            ax.axvline(lower, color="tab:green", linestyle="--")
            ax.axvline(upper, color="tab:green", linestyle="--")
            ax.errorbar(estimate, 0, xerr=([estimate-lo], [hi-estimate]),
                        fmt="o", capsize=6)
            ax.set(xlabel="均值偏差" if self.kind == "one" else "均值差",
                   title=f"{self.title} · {1-2*alpha:.1%} 区间", yticks=[])
            style_axes(ax)
            viewer.canvas.draw()
            self.app.replacePlotViewer(viewer)
            viewer.main.deiconify()
        except Exception:
            viewer.close()
            raise
        comparison = f"{names[0]} − {target:.8g}" if len(names) == 1 else f"{names[1]} − {names[0]}"
        method = self.method.get() if self.kind == "independent" else "单样本 t（配对差）" if self.kind == "paired" else "单样本 t"
        self.app.print(f"\n---- {self.title} ----\n{comparison} · {method} · α={alpha:.8g}")
        self.app.print("等效界限须在分析前确定。差异检验不显著不能证明等效，两项单侧检验均须显著。")
        self.app.print(StatTable(
            title="等效性单侧检验", headers=("备择", "界限", "t", "自由度", "p 值"),
            values=[("大于下限", lower, res["t_lower"], res["df"], res["p_lower"]),
                    ("小于上限", upper, res["t_upper"], res["df"], res["p_upper"])],
        ))
        if res["equivalent"]:
            conclusion = "达到统计等效"
        elif hi < lower or lo > upper:
            conclusion = "区间完全位于等效界限之外"
        else:
            conclusion = "证据不足以判定等效"
        self.app.print(StatTable(
            title="等效性区间及结论", headers=("估计值", "置信水平", "区间下限", "区间上限", "结论"),
            values=[(estimate, f"{1-2*alpha:.1%}", lo, hi, conclusion)],
        ))
        self.remember_columns()
        return True
