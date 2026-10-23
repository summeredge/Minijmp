"""完整回归分析窗口；计算在线程中执行，输出绑定来源工作表。"""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
import ast
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
    'thresholds': '有序模型阈值', 'response_levels': '响应类别编码',
    'confusion': '分类矩阵', 'probabilities': '类别概率',
    'x_scores': 'X 得分', 'y_scores': 'Y 得分', 'x_loadings': 'X 载荷',
    'y_loadings': 'Y 载荷', 'variance': '解释方差', 'vip': '变量重要性（VIP）',
    'cv': '交叉验证', 'cv_predictions': '交叉验证预测',
}
PLOTS = {'实测与预测': 'observed', '残差与拟合值': 'residual', '残差 QQ': 'qq',
         '残差序列': 'sequence', '影响点诊断': 'influence', '系数置信区间': 'coefficients',
         '模型比较': 'comparison', '预测图': 'prediction', 'ROC 曲线': 'roc',
         '类别概率': 'probabilities', '分类矩阵': 'confusion', '交叉验证误差': 'cv',
         '潜变量得分': 'scores', '潜变量载荷': 'loadings', '变量重要性（VIP）': 'vip',
         '回归系数': 'coefficients'}
MODEL_PLOTS = {
    'Poisson': ('observed', 'residual', 'sequence', 'influence', 'coefficients', 'prediction'),
    'Nominal': ('probabilities', 'confusion', 'coefficients'),
    'Ordinal': ('probabilities', 'confusion', 'coefficients'),
    'PLS': ('observed', 'residual', 'sequence', 'coefficients', 'prediction',
            'cv', 'scores', 'loadings', 'vip'),
}
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
           'probability': '事件概率', 'predicted_class': '预测类别',
           'response': '响应', 'category': '类别', 'level': '类别水平', 'code': '编码',
           'reference': '参考类别', 'actual_class': '实际类别', 'count': '频数',
           'component': '潜变量', 'n_components': '潜变量数', 'variable': '变量',
           'score_x': 'X 得分', 'score_y': 'Y 得分', 'loading': '载荷',
           'vip': 'VIP', 'deviance': '偏差', 'pearson_chi2': 'Pearson 卡方',
           'dispersion': '离散度', 'deviance_residual': '偏差残差',
           'pearson_residual': 'Pearson 残差', 'link': '链接函数',
           'fold': '验证折', 'cv_rmse': '交叉验证 RMSE', 'press': '预测残差平方和',
           'x_variance': 'X 解释方差', 'y_variance': 'Y 解释方差',
           'category_code': '类别编码', 'conditional_lower': '条件计数分位下限',
           'conditional_upper': '条件计数分位上限', 'negative_log_probability': '实际类别负对数概率',
           'probability_actual': '实际类别概率', 'misclassified': '分类错误',
           'log_loss': '对数损失', 'brier_score': 'Brier 分数', 'n_predictors': '预测变量数',
           'x_rank': '中心化 X 秩', 'scaled': '已标准化', 'cv_folds': '交叉验证折数',
           'rmsecv': '交叉验证 RMSE', 'rmsep': '预测 RMSE', 'standardized_press': '标准化 PRESS',
           'mean_standardized_press': '平均标准化 PRESS',
           'x_variance_ratio': 'X 方差解释比例', 'x_cumulative_ratio': 'X 累计解释比例',
           'y_variance_ratio': 'Y 方差解释比例', 'y_cumulative_ratio': 'Y 累计解释比例'}


def column_header(column):
    for prefix, label in [('component_', '潜变量'), ('probability_', '类别概率（编码')]:
        suffix = str(column).removeprefix(prefix)
        if str(column).startswith(prefix) and suffix.isdigit():
            return f'{label} {suffix}' + ('）' if prefix == 'probability_' else '')
    return HEADERS.get(column, str(column))


class RegressionDialog:
    def __init__(self, parent=None, df=None, app=None, model='OLS'):
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
        self.widgets = {}
        cols = list(self.df.columns)
        self.field(controls, 0, 0, 'y', '响应 Y', '', cols)
        self.field(controls, 0, 2, 'model', '模型类型', model,
                   ['OLS', 'WLS', 'Logistic', '非线性', 'Poisson', 'Nominal', 'Ordinal', 'PLS'])
        parameters = ttk.Notebook(controls)
        parameters.grid(row=1, column=0, columnspan=4, sticky='ew', pady=4)
        general = ttk.Frame(parameters, padding=4)
        extended = ttk.Frame(parameters, padding=4)
        parameters.add(general, text='模型项与拟合')
        parameters.add(extended, text='广义模型 / PLS 参数')
        for page in (general, extended):
            page.columnconfigure(1, weight=1)
            page.columnconfigure(3, weight=1)
        for row, (left, right) in enumerate([
                (('weight', '权重列（WLS）', '', ['']+cols), ('missing', '缺失值', '报错', ['报错', '删除不完整行'])),
                (('degree', '多项式次数', '1', ['1', '2', '3']), ('selection', '变量筛选', '不筛选', ['不筛选', '前进', '后退', '双向', '最佳子集'])),
                (('criterion', '筛选准则', 'AIC', ['AIC', 'BIC', '调整 R²']), ('confidence', '置信水平（%）', '95', None)),
                (('formula', '曲线 / 自定义公式', 'a*exp(b*x)+c', ['a*exp(b*x)+c', 'a*x**b', 'a/(1+exp(-b*(x-c)))']),
                 ('initial', '参数初值（如 a=1,b=.1,c=0）', 'a=1,b=0.1,c=0', None)),
        ]):
            self.field(general, row, 0, *left)
            self.field(general, row, 2, *right)
        self.field(extended, 0, 0, 'link', '链接函数', '', [''])
        self.field(extended, 0, 2, 'reference', '名义响应参考类别（必填）', '', None)
        self.field(extended, 1, 0, 'order', '有序响应顺序（低 → 高，逗号分隔）', '', None)
        self.field(extended, 1, 2, 'n_components', 'PLS 成分数（自动或正整数）', '自动', None)
        self.field(extended, 2, 0, 'max_components', 'PLS 自动选择最大成分数', '5', None)
        self.field(extended, 2, 2, 'cv', 'PLS 交叉验证折数（0 禁用）', '5', None)
        self.scale = tk.BooleanVar(self.main, True)
        self.scale_check = ttk.Checkbutton(extended, text='PLS 标准化 X/Y（始终中心化）', variable=self.scale)
        self.scale_check.grid(row=3, column=0, columnspan=2, sticky='w')
        ttk.Label(extended, text="类别按真实响应匹配；同名数字与文本可写 1 与 '1'。",
                  wraplength=430).grid(row=3, column=2, columnspan=2, sticky='w')
        variables = ttk.Frame(controls)
        variables.grid(row=2, column=0, columnspan=4, sticky='ew', pady=4)
        variables.columnconfigure(0, weight=1)
        variables.columnconfigure(1, weight=1)
        variables.columnconfigure(2, weight=1)
        self.x_list = self.listbox(variables, 0, '解释变量 X（Ctrl / Shift 多选）', cols)
        self.c_list = self.listbox(variables, 1, '分类因子（哑变量；首出现水平为基准）', cols)
        self.y_list = self.listbox(variables, 2, 'PLS 额外响应 Y（可多选）', cols)
        options = ttk.Frame(controls)
        options.grid(row=3, column=0, columnspan=4, sticky='ew')
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
        self.plot_box = ttk.Combobox(self.plot_tab, textvariable=self.plot_kind, values=list(PLOTS),
                                     state='readonly', width=22)
        self.plot_box.pack(side='left', anchor='n', padx=6)
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
        self.fields['model'].trace_add('write', self.model_changed)
        self.model_changed()
        if model in MODEL_PLOTS:
            parameters.select(extended)
        self.poll_id = self.main.after(100, self.poll)

    def field(self, parent, row, col, key, label, default, choices):
        ttk.Label(parent, text=label).grid(row=row, column=col, sticky='w', padx=(0, 5), pady=2)
        var = self.fields[key] = tk.StringVar(self.main, default)
        widget = (ttk.Entry(parent, textvariable=var) if choices is None else
                  ttk.Combobox(parent, textvariable=var, values=choices,
                               state='normal' if key == 'formula' else 'readonly'))
        widget.grid(row=row, column=col+1, sticky='ew', padx=(0, 12), pady=2)
        self.widgets[key] = widget
        if key == 'formula':
            widget.bind('<<ComboboxSelected>>', lambda event: self.fields['initial'].set({
                'a*exp(b*x)+c': 'a=1,b=0.1,c=0', 'a*x**b': 'a=1,b=1',
                'a/(1+exp(-b*(x-c)))': 'a=1,b=1,c=0'}[var.get()]))

    def model_changed(self, *args):
        model = self.fields['model'].get()
        links = {'Poisson': ['log', 'sqrt', 'identity'], 'Ordinal': ['logit', 'probit']}.get(model, [''])
        self.widgets['link'].configure(values=links, state='readonly' if links != [''] else 'disabled')
        if self.fields['link'].get() not in links:
            self.fields['link'].set(links[0])
        for key, enabled in [('reference', model == 'Nominal'), ('order', model == 'Ordinal'),
                             ('n_components', model == 'PLS'), ('max_components', model == 'PLS'),
                             ('cv', model == 'PLS')]:
            self.widgets[key].configure(state='normal' if enabled else 'disabled')
        self.y_list.configure(state='normal' if model == 'PLS' else 'disabled')
        self.scale_check.configure(state='normal' if model == 'PLS' else 'disabled')
        self.update_plots(self.result.model if self.result is not None else model)

    def update_plots(self, model):
        kinds = MODEL_PLOTS.get(model, ('observed', 'residual', 'qq', 'sequence', 'influence',
                                       'coefficients', 'comparison', 'prediction', 'roc'))
        names = [label for label, kind in PLOTS.items() if kind in kinds]
        names.remove('系数置信区间' if model == 'PLS' else '回归系数')
        if model == 'Logistic':
            names = [label for label in names if PLOTS[label] != 'qq']
        self.plot_box.configure(values=names)
        if self.plot_kind.get() not in names:
            self.plot_kind.set(names[0])

    def response_levels(self, text):
        y = self.fields['y'].get()
        if y not in self.df:
            raise ValueError('请选择有效的响应 Y。')
        levels = list(pd.unique(self.df[y].dropna()))
        result = []
        for token in text.split(','):
            token = token.strip()
            if not token:
                raise ValueError('请显式填写响应参考类别 / 完整类别顺序。')
            try:
                parsed = ast.literal_eval(token)
            except (ValueError, SyntaxError):
                parsed = token
            matches = [v for v in levels if isinstance(v, str) == isinstance(parsed, str) and v == parsed]
            if not matches:
                matches = [v for v in levels if str(v) == token]
            if len(matches) != 1:
                raise ValueError(f'响应类别 {token!r} 不存在或有歧义；文本类别可加单引号。')
            if matches[0] in result:
                raise ValueError('类别顺序不能重复。')
            result.append(matches[0])
        return result

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
        model = f['model']
        extended = model in MODEL_PLOTS
        if extended and f['weight']:
            raise ValueError(f'{model} 不支持权重；请清空权重列。')
        if extended and f['selection'] != '不筛选':
            raise ValueError(f'{model} 不支持变量筛选；请选择“不筛选”。')
        options = dict(y=f['y'], x=x, model='nonlinear' if model == '非线性' else model,
                    weight=(f['weight'] or None) if f['model'] == 'WLS' else None,
                    categorical=categorical, degree=int(f['degree']),
                    interactions=self.interactions.get(),
                    selection={'不筛选': 'none', '前进': 'forward', '后退': 'backward',
                               '双向': 'both', '最佳子集': 'best'}[f['selection']],
                    criterion='adjR2' if f['criterion'] == '调整 R²' else f['criterion'],
                    alpha=1-float(f['confidence'])/100,
                    missing='error' if f['missing'] == '报错' else 'drop',
                    formula=f['formula'], initial=initial or None)
        if model == 'Poisson':
            options['link'] = f['link'] or 'log'
        elif model in ('Nominal', 'Ordinal'):
            levels = self.response_levels(f['reference'] if model == 'Nominal' else f['order'])
            if model == 'Nominal':
                if len(levels) != 1:
                    raise ValueError('名义 Logistic 只能指定一个参考类别。')
                options['reference'] = levels[0]
            else:
                if len(levels) < 3 or len(levels) != self.df[f['y']].nunique():
                    raise ValueError('有序 Logistic 必须按低到高列出全部类别（至少 3 类）。')
                options.update(order=levels, link=f['link'] or 'logit')
        elif model == 'PLS':
            options.update(y=list(dict.fromkeys([f['y']] + [self.df.columns[i] for i in self.y_list.curselection()])),
                           n_components=None if f['n_components'] in ('', '自动') else int(f['n_components']),
                           max_components=int(f['max_components']), scale=self.scale.get(), cv=int(f['cv']))
        return options

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
        self.update_plots(result.model)
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
        table = StatTable(title=TABLE_TITLES.get(key, key), headers=[column_header(c) for c in frame.columns],
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
            self.app.addSheet(name='回归_' + TABLE_TITLES.get(key, key), dataframe=frame.rename(columns=column_header).copy(deep=True))
        except Exception as exc:
            self.error(exc)

    def export(self):
        try:
            _, frame = self.current_table()
            frame = export_source_labels(frame).rename(columns=column_header)
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
                        headers=[column_header(c) for c in frame.columns],
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
