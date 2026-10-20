from stat_table import StatTable
from tkinter import ttk
import tkinter as tk
from tkinter import TOP, LEFT, X, BOTH
###################################
from pandastable_local.dialogs import MultipleValDialog
########### Own Modules ###########
from dialog import Dialogs, addListBox
from utilities import count_2factors, number_2Dlist, transpose_2D_list, filter_voids, count_1factor, number_list
from chi_sq import chi_square
from utilities import gen_table, format_stat


class ProbabilityDialog(MultipleValDialog):
    def buttonbox(self):
        super().buttonbox()
        for frame in self.winfo_children():
            for widget in frame.winfo_children():
                if isinstance(widget, tk.Button):
                    widget.configure(text={'OK': '确定', 'Cancel': '取消'}.get(
                        widget.cget('text'), widget.cget('text')))


class Chi2TableDialog(Dialogs):
    def createWidgets(self, m):
        f = tk.LabelFrame(m, text='原始数据（分类值）')
        f.pack(side=TOP, fill=BOTH, padx=2, pady=2)
        self.xvar = tk.StringVar(value="")
        self.yvar = tk.StringVar(value="")
        w = tk.Label(f, text='行变量')
        w.pack(side=LEFT, fill=X, padx=2, pady=2)
        w = ttk.Combobox(
            f, values=self.cols, textvariable=self.xvar,
            width=14)
        w.pack(side=LEFT, padx=2, pady=2)
        w = tk.Label(f, text='列变量')
        w.pack(side=LEFT, fill=X, padx=2, pady=2)
        w = ttk.Combobox(
            f, values=self.cols, textvariable=self.yvar,
            width=14)
        w.pack(side=LEFT, padx=2, pady=2)

        f = tk.LabelFrame(m, text='双向表汇总数据（优先使用）')
        f.pack(side=TOP, fill=BOTH, padx=2)
        w, self.grpvar = addListBox(
            f, values=self.cols, width=20, label='列')
        w.pack(side=LEFT, fill=X, padx=10)
        self.rvar = tk.StringVar(value="")
        w = tk.Label(f, text='行标签列（可选）')
        w.pack(side=LEFT, fill=X, padx=2)
        w = ttk.Combobox(
            f, values=self.cols, textvariable=self.rvar,
            width=14)
        w.pack(side=LEFT, padx=2)

        return

    def ok(self):
        self.grpcols = self.grpvar.getSelectedItem()
        self.quit()
        self.apply()
        return

    def apply(self):

        if len(self.grpcols) > 0:
            data = number_2Dlist(df=self.df, cols=self.grpcols,
                                 print_out=True, print_port=self.app.print)
            cKeys = self.grpcols
            data = transpose_2D_list(data)
            if len(self.rvar.get()) > 0:
                [rKeys] = filter_voids([list(self.df[self.rvar.get()])])
            else:
                rKeys = [chr(65 + i) for i in range(len(data))]
        else:
            data, rKeys, cKeys = count_2factors(
                self.df[self.xvar.get()],
                self.df[self.yvar.get()])

        chi_square(data, print_out=True,
                   print_port=self.app.print,
                   print_table=True,
                   cKeys=cKeys, rKeys=rKeys)
        return


class Chi2PropDialog(Dialogs):
    def createWidgets(self, m):
        f = tk.LabelFrame(m, text='原始数据（分类值）')
        f.pack(side=TOP, fill=BOTH, padx=2, pady=2)
        self.xvar = tk.StringVar(value="")
        w = tk.Label(f, text='样本')
        w.pack(side=LEFT, fill=X, padx=2, pady=2)
        w = ttk.Combobox(
            f, values=self.cols, textvariable=self.xvar,
            width=14)
        w.pack(side=LEFT, padx=2, pady=2)

        f = tk.LabelFrame(m, text='汇总计数（优先使用）')
        f.pack(side=TOP, fill=BOTH, padx=2, pady=2)
        self.rvar = tk.StringVar(value="")
        w = tk.Label(f, text='水平')
        w.pack(side=LEFT, fill=X, padx=2, pady=2)
        w = ttk.Combobox(
            f, values=self.cols, textvariable=self.rvar,
            width=14)
        w.pack(side=LEFT, padx=2, pady=2)
        self.cnt = tk.StringVar(value="")
        w = tk.Label(f, text='计数')
        w.pack(side=LEFT, fill=X, padx=2, pady=2)
        w = ttk.Combobox(
            f, values=self.cols, textvariable=self.cnt,
            width=14)
        w.pack(side=LEFT, padx=2, pady=2)

        return

    def apply(self):

        rvar = self.rvar.get()
        cnt = self.cnt.get()
        if len(rvar) > 0 and len(cnt) > 0:
            [rKeys, cnts] = filter_voids([list(self.df[rvar]),
                                          list(self.df[cnt])])
            cnts = number_list(cnts)
        else:
            cnts, rKeys = count_1factor(
                self.df[self.xvar.get()])

        d = ProbabilityDialog(title='假设概率（总和须为 1）',
                              labels=rKeys,
                              initialvalues=[0] * len(rKeys),
                              types=["float"] * len(rKeys),
                              parent=self.parent)
        if d.result is None:
            return
        #  print(d.results)
        res = number_list(d.results)
        #  print(res, sum(res), cnts)
        if len(res) != len(cnts):
            self.error('输入无效。')
            return
        if any(_ <= 0 for _ in res):
            self.error('假设概率必须大于 0 且小于 1。')
            return
        if sum(res) != 1:
            self.error('假设概率总和不为 1，已按比例重新调整。')
            res = [x / sum(res) for x in res]

        ratio = sum(cnts) * 1e9
        pseudo_data = [_ * ratio for _ in res]

        result = chi_square([cnts, pseudo_data], print_out=False,
                            print_port=self.app.print,
                            print_table=False)
        self.app.print("\n---- 卡方拟合优度检验 ----")
        self.app.print('原假设 H0：各水平的总体概率等于指定的假设概率。')
        self.app.print('备择假设 H1：至少一个水平的总体概率不同于假设概率。')
        self.app.print('方法：沿用观测频数与大样本参考行构成的列联表近似，未作连续性校正。')
        rows = [['水平', '观测频数', '估计概率', '假设概率']]
        values = []
        for i in range(len(cnts)):
            values.append([rKeys[i], cnts[i], cnts[i] / sum(cnts), res[i]])
            rows.append([rKeys[i], cnts[i], format_stat(cnts[i] / sum(cnts)),
                         format_stat(res[i])])
        table = gen_table(rows)
        table.align = 'r'
        table.align[table.field_names[0]] = 'l'
        self.app.print(StatTable(table, '各水平概率', table.field_names, values,
            display=[[str(cell) for cell in row] for row in table.rows],
            number_formats=['General', 'General', '0.000', '0.000']))
        self.app.print('当前返回结果未提供各水平的期望频数；不另行推算。')
        self.app.print('检验结果')
        values = [['Pearson', result['chi sq Pearson'], result['df'], result['p Pearson']],
                  ['似然比', result['chi sq LR'], result['df'], result['p LR']]]
        table = gen_table([['方法', '卡方统计量', '自由度', 'p 值'],
                           ['Pearson', format_stat(result['chi sq Pearson']), result['df'], format_stat(result['p Pearson'])],
                           ['似然比', format_stat(result['chi sq LR']), result['df'], format_stat(result['p LR'])]])
        table.align = 'r'
        table.align[table.field_names[0]] = 'l'
        self.app.print(StatTable(table, '检验结果', table.field_names, values,
            display=[[str(cell) for cell in row] for row in table.rows]))
        self.app.print('适用条件：观测独立，期望频数应足够大；本报告未对小期望频数作自动判断。')
        self.app.print('p 值是在 H0 及检验模型成立时，得到当前或更极端统计量的概率，不是 H0 成立的概率。')
        self.app.print('p 值保留三位小数，0.000 为舍入显示，不代表概率严格为零；* 表示不可用。')
        return
