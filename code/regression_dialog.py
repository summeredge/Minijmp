"""完整回归分析窗口；计算在线程中执行，输出绑定来源工作表。"""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import pandas as pd

from pandastable_local.dialogs import apply_dialog_theme
from sheet_context import SheetApp, export_source_labels
from stat_table import StatTable, TableBlock


TABLE_TITLES = {
    'summary': '模型摘要', 'coefficients': '系数', 'anova': '方差分析',
    'diagnostics': '残差诊断', 'vif': '共线性诊断', 'observations': '观测诊断',
    'comparison': '模型比较', 'classification': '分类评估', 'roc': 'ROC',
    'prediction': '新数据预测',
}
PLOTS = {'实测与预测': 'observed', '残差与拟合值': 'residual', '残差 QQ': 'qq',
         '残差序列': 'sequence', '影响点诊断': 'influence', '系数置信区间': 'coefficients',
         '模型比较': 'comparison', '预测图': 'prediction', 'ROC 曲线': 'roc'}
HEADERS = {'model': '模型', 'n_obs': '有效样本数', 'n_parameters': '参数数',
           'df_resid': '残差自由度', 'log_likelihood': '对数似然', 'aic': 'AIC', 'bic': 'BIC',
           'sse': '残差平方和', 'rmse': '均方根误差', 'residual_std': '残差标准差',
           'r_squared': 'R²', 'adj_r_squared': '调整 R²', 'pseudo_r_squared': 'McFadden 伪 R²',
           'auc': 'AUC', 'term': '模型项', 'estimate': '估计值', 'std_error': '标准误',
           'statistic': '统计量', 'statistic_type': '统计量类型', 'p_value': 'p 值',
           'ci_lower': '置信下限', 'ci_upper': '置信上限', 'source': '变异来源',
           'sum_sq': '平方和', 'df': '自由度', 'mean_sq': '均方', 'test': '检验',
           'definition': '定义', 'vif': 'VIF', 'source_row': '来源行号', 'source_index': '来源索引',
           'actual': '实测值', 'fitted': '拟合值', 'residual': '残差', 'whitened_residual': '白化残差',
           'standardized_residual': '标准化残差', 'leverage': '杠杆值', 'cooks_distance': 'Cook 距离',
           'outlier': '残差异常', 'high_leverage': '高杠杆', 'influential': '强影响',
           'terms': '模型项组合', 'score': '筛选评分（越小越好）', 'selected': '选中模型',
           'status': '状态', 'threshold': '分类阈值', 'tn': '真阴性', 'fp': '假阳性',
           'fn': '假阴性', 'tp': '真阳性', 'accuracy': '准确率', 'precision': '精确率',
           'recall': '召回率', 'specificity': '特异度', 'f1': 'F1', 'fpr': '假阳性率',
           'tpr': '真阳性率', 'predicted': '预测值', 'mean_ci_lower': '均值置信下限',
           'mean_ci_upper': '均值置信上限', 'pi_lower': '观测预测下限', 'pi_upper': '观测预测上限',
           'probability': '事件概率', 'predicted_class': '预测类别'}


class RegressionDialog:
    def __init__(self, parent=None, df=None, app=None):
        self.app = SheetApp(app, app.getCurrentTable())
        self.df = df.copy(deep=True)
        self.result = None
        self.future = None
        self.cancel_event = Event()
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='regression')
        self.main = tk.Toplevel(parent)
        self.main.title('完整回归分析')
        self.main.geometry('1120x760')
        self.main.minsize(880, 620)
        apply_dialog_theme(self.main)
        self.main.protocol('WM_DELETE_WINDOW', self.close)
        self.main.bind('<F1>', self.help)
        self.main.bind('<Escape>', lambda event: self.cancel())
        controls = ttk.Frame(self.main, padding=6)
        controls.pack(fill='x')
        controls.columnconfigure(1, weight=1)
        controls.columnconfigure(3, weight=1)
        self.fields = {}
        cols = list(self.df.columns)
        for row, (left, right) in enumerate([
                (('y', '响应 Y', '', cols), ('model', '模型类型', 'OLS', ['OLS', 'WLS', 'Logistic', '非线性'])),
                (('weight', '权重列（WLS）', '', ['']+cols), ('missing', '缺失值', '报错', ['报错', '删除不完整行'])),
                (('degree', '多项式次数', '1', ['1', '2', '3']), ('selection', '变量筛选', '不筛选', ['不筛选', '前进', '后退', '双向', '最佳子集'])),
                (('criterion', '筛选准则', 'AIC', ['AIC', 'BIC', '调整 R²']), ('confidence', '置信水平（%）', '95', None)),
                (('formula', '曲线 / 自定义公式', 'a*exp(b*x)+c', ['a*exp(b*x)+c', 'a*x**b', 'a/(1+exp(-b*(x-c)))']),
                 ('initial', '参数初值（如 a=1,b=.1,c=0）', 'a=1,b=0.1,c=0', None)),
        ]):
            self.field(controls, row, 0, *left)
            self.field(controls, row, 2, *right)
        variables = ttk.Frame(controls)
        variables.grid(row=5, column=0, columnspan=4, sticky='ew', pady=4)
        variables.columnconfigure(0, weight=1)
        variables.columnconfigure(1, weight=1)
        self.x_list = self.listbox(variables, 0, '解释变量 X（Ctrl / Shift 多选）', cols)
        self.c_list = self.listbox(variables, 1, '其中作为分类变量编码的列', cols)
        options = ttk.Frame(controls)
        options.grid(row=6, column=0, columnspan=4, sticky='ew')
        self.interactions = tk.BooleanVar(self.main, False)
        self.diagnostics = tk.BooleanVar(self.main, True)
        ttk.Checkbutton(options, text='添加两两交互项', variable=self.interactions).pack(side='left')
        ttk.Checkbutton(options, text='输出诊断页面', variable=self.diagnostics).pack(side='left')
        self.fit_button = ttk.Button(options, text='建立模型', command=self.fit)
        self.fit_button.pack(side='left', padx=8)
        self.cancel_button = ttk.Button(options, text='取消计算', command=self.cancel, state='disabled')
        self.cancel_button.pack(side='left')
        ttk.Button(options, text='帮助', command=self.help).pack(side='right')
        self.progress = ttk.Progressbar(options, mode='indeterminate', length=100)
        self.progress.pack(side='right', padx=8)
        self.status = tk.StringVar(self.main, '请选择 Y 和 X；源数据按打开窗口时的快照分析。')
        ttk.Label(self.main, textvariable=self.status, wraplength=1050).pack(fill='x', padx=8)
        self.notebook = ttk.Notebook(self.main)
        self.notebook.pack(fill='both', expand=True, padx=6, pady=4)
        self.tabs = {}
        self.tables = {}
        self.prediction = None
        self.plot_tab = ttk.Frame(self.notebook, padding=8)
        self.notebook.add(self.plot_tab, text='图形')
        self.plot_kind = tk.StringVar(self.main, next(iter(PLOTS)))
        ttk.Label(self.plot_tab, text='图形类型').pack(side='left', anchor='n')
        ttk.Combobox(self.plot_tab, textvariable=self.plot_kind, values=list(PLOTS),
                     state='readonly', width=22).pack(side='left', anchor='n', padx=6)
        ttk.Button(self.plot_tab, text='打开图形', command=self.plot).pack(side='left', anchor='n')
        actions = ttk.Frame(self.main, padding=6)
        actions.pack(side='bottom', fill='x', before=self.notebook)
        prediction_actions = ttk.Frame(actions)
        prediction_actions.pack(fill='x')
        output_actions = ttk.Frame(actions)
        output_actions.pack(fill='x', pady=(4, 0))
        self.sheet_name = tk.StringVar(self.main)
        ttk.Label(prediction_actions, text='预测数据工作表').pack(side='left')
        self.sheet_box = ttk.Combobox(prediction_actions, textvariable=self.sheet_name, state='readonly',
                                     postcommand=self.refresh_sheets, width=18)
        self.sheet_box.pack(side='left', padx=4)
        self.refresh_sheets()
        self.pred_button = ttk.Button(prediction_actions, text='预测', command=self.predict, state='disabled')
        self.pred_button.pack(side='left')
        ttk.Button(output_actions, text='当前表写入新工作表', command=self.to_sheet).pack(side='left')
        ttk.Button(output_actions, text='导出当前表', command=self.export).pack(side='left', padx=4)
        ttk.Button(output_actions, text='输出完整报告', command=self.report).pack(side='left')
        ttk.Button(prediction_actions, text='关闭', command=self.close).pack(side='right')
        self.poll_id = self.main.after(100, self.poll)

    def field(self, parent, row, col, key, label, default, choices):
        ttk.Label(parent, text=label).grid(row=row, column=col, sticky='w', padx=(0, 5), pady=2)
        var = self.fields[key] = tk.StringVar(self.main, default)
        widget = (ttk.Entry(parent, textvariable=var) if choices is None else
                  ttk.Combobox(parent, textvariable=var, values=choices,
                               state='normal' if key == 'formula' else 'readonly'))
        widget.grid(row=row, column=col+1, sticky='ew', padx=(0, 12), pady=2)
        if key == 'formula':
            widget.bind('<<ComboboxSelected>>', lambda event: self.fields['initial'].set({
                'a*exp(b*x)+c': 'a=1,b=0.1,c=0', 'a*x**b': 'a=1,b=1',
                'a/(1+exp(-b*(x-c)))': 'a=1,b=1,c=0'}[var.get()]))

    def listbox(self, parent, col, label, values):
        frame = ttk.LabelFrame(parent, text=label, padding=3)
        frame.grid(row=0, column=col, sticky='nsew', padx=(0, 6))
        box = tk.Listbox(frame, height=4, selectmode='extended', exportselection=False)
        scrollbar = ttk.Scrollbar(frame, command=box.yview)
        box.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y')
        box.pack(fill='both', expand=True)
        for value in values:
            box.insert('end', value)
        return box

    def options(self):
        f = {k: v.get().strip() for k, v in self.fields.items()}
        x = [self.df.columns[i] for i in self.x_list.curselection()]
        categorical = [self.df.columns[i] for i in self.c_list.curselection()]
        initial = {}
        if f['model'] == '非线性':
            for item in f['initial'].split(','):
                key, value = item.split('=')
                initial[key.strip()] = float(value)
        return dict(y=f['y'], x=x, model='nonlinear' if f['model'] == '非线性' else f['model'],
                    weight=(f['weight'] or None) if f['model'] == 'WLS' else None,
                    categorical=categorical, degree=int(f['degree']),
                    interactions=self.interactions.get(),
                    selection={'不筛选': 'none', '前进': 'forward', '后退': 'backward',
                               '双向': 'both', '最佳子集': 'best'}[f['selection']],
                    criterion='adjR2' if f['criterion'] == '调整 R²' else f['criterion'],
                    alpha=1-float(f['confidence'])/100,
                    missing='error' if f['missing'] == '报错' else 'drop',
                    formula=f['formula'], initial=initial or None)

    def fit(self):
        try:
            self.app.getCurrentTable()
            options = self.options()
            from advanced_regression import fit_regression
            self.start(lambda: fit_regression(self.df, **options, cancel=self.cancel_event), 'fit')
        except Exception as exc:
            self.error(exc)

    def start(self, operation, task):
        if self.future is not None:
            return
        self.cancel_event.clear()
        self.task = task
        self.future = self.executor.submit(operation)
        self.fit_button.configure(state='disabled')
        self.pred_button.configure(state='disabled')
        self.cancel_button.configure(state='normal')
        self.progress.start()
        self.status.set('正在拟合…' if task == 'fit' else '正在预测…')

    def cancel(self):
        if self.future is not None:
            self.cancel_event.set()
            self.status.set('正在取消；等待当前计算返回后丢弃结果。')

    def poll(self):
        if self.future is not None and self.future.done():
            future, self.future = self.future, None
            self.progress.stop()
            self.fit_button.configure(state='normal')
            self.cancel_button.configure(state='disabled')
            try:
                if self.cancel_event.is_set():
                    self.status.set('已取消，上次结果保留。')
                else:
                    self.app.getCurrentTable()
                    result = future.result()
                    if self.task == 'fit':
                        self.publish(result)
                    else:
                        self.prediction = result
                        self.show_table('prediction', result)
                        self.status.set('预测完成；行号对应预测数据工作表快照。')
            except Exception as exc:
                self.error(exc)
            self.pred_button.configure(state='normal' if self.result is not None else 'disabled')
        self.poll_id = self.main.after(100, self.poll)

    def publish(self, result):
        self.result = result
        self.prediction = None
        for tab in self.tabs.values():
            tab.destroy()
        self.tabs.clear()
        self.tables.clear()
        for key, frame in result.tables.items():
            if not self.diagnostics.get() and key in ('diagnostics', 'vif', 'observations'):
                continue
            if not frame.empty:
                self.show_table(key, frame)
        self.status.set('建模完成；点击图中样本可定位来源行，表格保留原始数值精度。')
        if 'summary' in self.tabs:
            notes = tk.Text(self.tabs['summary'], height=4, wrap='word')
            notes.insert('1.0', result.equation + '\n' + '\n'.join(result.notes))
            notes.configure(state='disabled')
            notes.pack(side='top', fill='x', before=self.tabs['summary'].winfo_children()[0])
        if self.tabs:
            self.notebook.insert('end', self.plot_tab)
            self.notebook.select(next(iter(self.tabs.values())))

    def show_table(self, key, frame):
        if key in self.tabs:
            self.tabs[key].destroy()
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=TABLE_TITLES.get(key, key))
        shown = export_source_labels(frame)
        table = StatTable(title=TABLE_TITLES.get(key, key), headers=[HEADERS.get(c, str(c)) for c in frame.columns],
                          values=shown.astype(object).where(pd.notna(shown), None).values.tolist())
        block = TableBlock(tab, table, paginate=True)
        block.pack(fill='both', expand=True)
        block.rowconfigure(1, weight=1)
        block.columnconfigure(0, weight=1)
        block.tree.master.grid(sticky='nsew')
        tab.bind('<Configure>', lambda event: block.fit_titlebar(event.width))
        self.tabs[key], self.tables[key] = tab, frame
        self.notebook.select(tab)

    def current_table(self):
        self.app.getCurrentTable()
        selected = self.notebook.select()
        key = next((k for k, tab in self.tabs.items() if str(tab) == selected), None)
        if key is None or key not in self.tables:
            raise ValueError('请先建立模型并选择结果表。')
        return key, self.tables[key]

    def refresh_sheets(self):
        names = list(self.app.sheets)
        self.sheet_box.configure(values=names)
        if self.sheet_name.get() not in names:
            self.sheet_name.set(names[0] if names else '')

    def predict(self):
        try:
            self.app.getCurrentTable()
            if self.result is None:
                raise ValueError('请先建立模型。')
            table = self.app.sheets.get(self.sheet_name.get())
            if table is None:
                raise ValueError('请选择有效的预测数据工作表。')
            data = table.model.df.copy(deep=True)
            alpha = 1-float(self.fields['confidence'].get())/100
            weight = (self.fields['weight'].get().strip() or None) if self.result.model == 'WLS' else None
            self.start(lambda: self.result.predict(data, alpha=alpha, weight=weight), 'predict')
        except Exception as exc:
            self.error(exc)

    def to_sheet(self):
        try:
            key, frame = self.current_table()
            self.app.addSheet(name='回归_' + TABLE_TITLES.get(key, key), dataframe=frame.rename(columns=HEADERS).copy(deep=True))
        except Exception as exc:
            self.error(exc)

    def export(self):
        try:
            _, frame = self.current_table()
            frame = export_source_labels(frame).rename(columns=HEADERS)
            filename = filedialog.asksaveasfilename(parent=self.main, defaultextension='.xlsx',
                filetypes=[('Excel', '*.xlsx'), ('CSV', '*.csv')])
            if filename:
                if filename.lower().endswith('.csv'):
                    frame.to_csv(filename, index=False, encoding='utf-8-sig')
                else:
                    frame.to_excel(filename, index=False)
        except Exception as exc:
            self.error(exc)

    def report(self):
        try:
            self.app.getCurrentTable()
            if self.result is None:
                raise ValueError('请先建立模型。')
            self.app.print(self.result.equation)
            for note in self.result.notes:
                self.app.print(note)
            for key, frame in self.result.tables.items():
                if not frame.empty:
                    shown = export_source_labels(frame)
                    self.app.print(StatTable(title=TABLE_TITLES.get(key, key),
                        headers=[HEADERS.get(c, str(c)) for c in frame.columns],
                        values=shown.astype(object).where(pd.notna(shown), None).values.tolist()))
        except Exception as exc:
            self.error(exc)

    def plot(self):
        try:
            self.app.getCurrentTable()
            if self.result is None:
                raise ValueError('请先建立模型。')
            from regression_plots import regression_plot
            viewer = self.app.showPlotViewer(deferred=True)
            try:
                regression_plot(self.result, PLOTS[self.plot_kind.get()], viewer.fig,
                                prediction=self.prediction, on_pick=self.select_row)
                viewer.canvas.draw()
                self.app.replacePlotViewer(viewer)
                viewer.main.deiconify()
            except Exception:
                viewer.close()
                raise
        except Exception as exc:
            self.error(exc)

    def select_row(self, row):
        try:
            table = self.app.getCurrentTable()
            if not table.model.df.equals(self.df):
                raise ValueError('来源工作表已更改；请重新打开分析后定位样本。')
            table.setSelectedRow(int(row)-1)
            table.redraw()
            self.status.set(f'已选中来源工作表第 {row} 行。')
        except Exception as exc:
            self.error(exc)

    def error(self, exc):
        self.status.set('失败：' + str(exc))
        messagebox.showerror('回归分析', str(exc), parent=self.main)

    def help(self, event=None):
        from help_link import open_help
        open_help('stats.advanced_regression', parent=self.main)
        return 'break'

    def close(self):
        self.cancel_event.set()
        self.main.after_cancel(self.poll_id)
        self.executor.shutdown(wait=False, cancel_futures=True)
        self.main.destroy()
