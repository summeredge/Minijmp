"""PCA 建模、状态探索与 A/B 选区统计。"""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import numpy as np
import pandas as pd
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

from pandastable_local.dialogs import apply_dialog_theme
from sheet_context import SheetApp, export_source_labels
from stat_table import StatTable, TableBlock


TITLES = {'variance': '特征值与贡献率', 'loadings': '载荷', 'limits': '控制限及方法',
          'preprocessing': '预处理参数', 'cv': '交叉验证辅助', 'scores': '得分',
          'monitoring': '统计监控', 'residuals': '模型残差', 'reconstructed': '重构值',
          'contribution': '样本贡献', 'groups': 'A/B 变量统计', 'selection': '选区样本'}
HEADERS = {'source_row': '来源行号', 'source_index': '来源索引', 'variable': '变量',
           'contribution': '贡献', 'n_a': 'A 样本数', 'mean_a': 'A 均值', 'std_a': 'A 标准差',
           'n_b': 'B 样本数', 'mean_b': 'B 均值', 'std_b': 'B 标准差', 'difference': '均值差 A−B',
           'group': '选区', 'component': '主成分', 'eigenvalue': '特征值',
           'explained_variance_ratio': '解释方差比例', 'cumulative_variance_ratio': '累计解释方差',
           'mean': '均值', 'scale': '缩放因子', 't2': 'T²', 'q': 'Q / SPE',
           'phase': '监控阶段', 'confidence': '覆盖率', 'theta1': '遗漏谱一阶矩', 'theta2': '遗漏谱二阶矩',
           't2_method': 'T² 限方法', 'q_method': 'Q 限方法', 'selected': '保留主成分',
           't2_flag_95': 'T² 超95%限', 't2_flag_99': 'T² 超99%限',
           'q_flag_95': 'Q 超95%限', 'q_flag_99': 'Q 超99%限',
           'abnormal_95': '95%异常', 'abnormal_99': '99%异常',
           'n_components': '主成分数', 'mse': '重构均方误差', 'n_values': '验证单元数',
           't2_limit_95': 'T² 95%限', 't2_limit_99': 'T² 99%限',
           'q_limit_95': 'Q 95%限', 'q_limit_99': 'Q 99%限'}
PLOTS = {'得分图': 'score', '载荷图': 'loading', '双标图': 'biplot', '碎石图': 'scree',
         '累计贡献率': 'cumulative', 'T² 统计量': 't2', 'Q 统计量': 'q',
         '单变量贡献': 'single_variable', 'A/B 贡献对比': 'compare_contribution'}


class PCADialog:
    def __init__(self, parent=None, df=None, app=None):
        self.app = SheetApp(app, app.getCurrentTable())
        self.df = df.copy(deep=True)
        self.model = self.projection = None
        self.future = None
        self.cancel_event = Event()
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='pca')
        self.groups = {'A': [], 'B': []}
        self.active_row = 0
        self.plot_handles = None
        self.redraw_id = None
        self.active_table, self.active_snapshot = self.app.table, self.df
        self.main = tk.Toplevel(parent)
        self.main.title('主成分分析')
        self.main.geometry('1160x800')
        self.main.minsize(900, 640)
        apply_dialog_theme(self.main)
        self.main.protocol('WM_DELETE_WINDOW', self.close)
        self.main.bind('<F1>', self.help)
        self.main.bind('<Escape>', lambda event: self.cancel())
        controls = ttk.Frame(self.main, padding=6)
        controls.pack(fill='x')
        selector = ttk.LabelFrame(controls, text='建模变量（Ctrl / Shift 多选）', padding=3)
        selector.pack(side='left', fill='both', expand=True, padx=(0, 8))
        self.columns = tk.Listbox(selector, height=5, selectmode='extended', exportselection=False)
        scrollbar = ttk.Scrollbar(selector, command=self.columns.yview)
        self.columns.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y')
        self.columns.pack(fill='both', expand=True)
        for col in self.df.columns:
            self.columns.insert('end', col)
        settings = ttk.Frame(controls)
        settings.pack(side='left', fill='both', expand=True)
        settings.columnconfigure(1, weight=1)
        self.fields = {}
        self.field(settings, 0, 'scaling', '预处理', '自动标准化', ['自动标准化', '均值中心化', '不缩放'])
        self.field(settings, 1, 'components', '主成分数（自动留空）', '', None)
        self.field(settings, 2, 'variance', '累计解释方差（%）', '95', None)
        self.field(settings, 3, 'cv', '交叉验证折数（0 关闭）', '0', None)
        self.field(settings, 4, 'missing', '缺失值', '报错', ['报错', '删除不完整行'])
        commands = ttk.Frame(self.main, padding=(6, 0))
        commands.pack(fill='x')
        self.fit_button = ttk.Button(commands, text='建立模型', command=self.fit)
        self.fit_button.pack(side='left')
        self.cancel_button = ttk.Button(commands, text='取消计算', command=self.cancel, state='disabled')
        self.cancel_button.pack(side='left', padx=4)
        ttk.Button(commands, text='保存模型', command=self.save_model).pack(side='left')
        ttk.Button(commands, text='加载模型', command=self.load_model).pack(side='left', padx=4)
        self.sheet_name = tk.StringVar(self.main)
        ttk.Label(commands, text='投影数据表').pack(side='left', padx=(8, 2))
        self.sheet_box = ttk.Combobox(commands, textvariable=self.sheet_name, state='readonly',
                                     postcommand=self.refresh_sheets, width=18)
        self.sheet_box.pack(side='left')
        self.refresh_sheets()
        self.project_button = ttk.Button(commands, text='投影新样本', command=self.project, state='disabled')
        self.project_button.pack(side='left', padx=4)
        ttk.Button(commands, text='训练样本', command=self.use_training).pack(side='left')
        ttk.Button(commands, text='帮助', command=self.help).pack(side='right')
        self.progress = ttk.Progressbar(commands, mode='indeterminate', length=65)
        self.progress.pack(side='right', padx=4)
        self.status = tk.StringVar(self.main, '请选择至少两列数值变量。')
        ttk.Label(self.main, textvariable=self.status, wraplength=1100).pack(fill='x', padx=8, pady=3)
        self.notebook = ttk.Notebook(self.main)
        self.notebook.pack(fill='both', expand=True, padx=6, pady=4)
        self.tables, self.tabs = {}, {}
        self.explore_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.explore_tab, text='状态探索与选区')
        self.make_exploration()
        self.notes_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.notes_tab, text='模型说明')
        self.notes = tk.Text(self.notes_tab, wrap='word', state='disabled')
        notes_scroll = ttk.Scrollbar(self.notes_tab, command=self.notes.yview)
        self.notes.configure(yscrollcommand=notes_scroll.set)
        notes_scroll.pack(side='right', fill='y')
        self.notes.pack(fill='both', expand=True)
        outputs = ttk.Frame(self.main, padding=6)
        outputs.pack(side='bottom', fill='x', before=self.notebook)
        ttk.Button(outputs, text='当前表写入新工作表', command=self.to_sheet).pack(side='left')
        ttk.Button(outputs, text='导出当前表', command=self.export).pack(side='left', padx=4)
        ttk.Button(outputs, text='输出统计报告', command=self.report).pack(side='left')
        ttk.Button(outputs, text='保存当前图形', command=self.save_plot).pack(side='left', padx=4)
        ttk.Button(outputs, text='保存贡献图', command=lambda: self.save_plot(contribution=True)).pack(side='left')
        ttk.Button(outputs, text='关闭', command=self.close).pack(side='right')
        self.poll_id = self.main.after(100, self.poll)

    def field(self, parent, row, key, label, default, choices):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky='w', padx=(0, 6), pady=2)
        var = self.fields[key] = tk.StringVar(self.main, default)
        widget = (ttk.Entry(parent, textvariable=var) if choices is None else
                  ttk.Combobox(parent, textvariable=var, values=choices, state='readonly'))
        widget.grid(row=row, column=1, sticky='ew', pady=2)

    def make_exploration(self):
        controls = ttk.Frame(self.explore_tab, padding=4)
        controls.pack(fill='x')
        self.plot_kind = tk.StringVar(self.main, '得分图')
        self.pc_x, self.pc_y = tk.StringVar(self.main, '1'), tk.StringVar(self.main, '2')
        self.color_column = tk.StringVar(self.main, '')
        self.active_group = tk.StringVar(self.main, 'A')
        self.shape = tk.StringVar(self.main, '矩形')
        self.contribution_kind = tk.StringVar(self.main, 'T²')
        self.ellipse_confidence = tk.StringVar(self.main, '95')
        self.variable = tk.StringVar(self.main, '')
        specs = [('图形', self.plot_kind, list(PLOTS), 16), ('PC X', self.pc_x, [], 4),
                 ('PC Y', self.pc_y, [], 4), ('分类上色', self.color_column, ['']+list(self.df.columns), 12),
                 ('选区', self.active_group, ['A', 'B'], 3), ('形状', self.shape, ['矩形', '椭圆'], 6)]
        self.pc_boxes = []
        for label, var, values, width in specs:
            ttk.Label(controls, text=label).pack(side='left', padx=(4, 2))
            box = ttk.Combobox(controls, textvariable=var, values=values, state='readonly', width=width)
            box.pack(side='left')
            box.bind('<<ComboboxSelected>>', lambda event: self.draw())
            if label in ('PC X', 'PC Y'):
                self.pc_boxes.append(box)
        actions = ttk.Frame(self.explore_tab, padding=4)
        actions.pack(fill='x')
        ttk.Label(actions, text='轮廓覆盖率（%）').pack(side='left')
        box = ttk.Combobox(actions, textvariable=self.ellipse_confidence, values=['95', '99'], state='readonly', width=4)
        box.pack(side='left')
        box.bind('<<ComboboxSelected>>', lambda event: self.draw())
        ttk.Label(actions, text='贡献').pack(side='left', padx=(6, 2))
        box = ttk.Combobox(actions, textvariable=self.contribution_kind, values=['T²', 'Q'], state='readonly', width=4)
        box.pack(side='left')
        box.bind('<<ComboboxSelected>>', lambda event: self.update_contribution())
        ttk.Label(actions, text='单变量').pack(side='left', padx=(6, 2))
        self.variable_box = ttk.Combobox(actions, textvariable=self.variable, state='readonly', width=14)
        self.variable_box.pack(side='left')
        self.variable_box.bind('<<ComboboxSelected>>', lambda event: self.draw())
        ttk.Button(actions, text='对比 A/B', command=self.compare).pack(side='left', padx=6)
        ttk.Button(actions, text='清空选区', command=self.clear_groups).pack(side='left')
        self.group_status = tk.StringVar(self.main, 'A：0；B：0')
        ttk.Label(actions, textvariable=self.group_status).pack(side='left', padx=6)
        panes = ttk.Panedwindow(self.explore_tab, orient='horizontal')
        panes.pack(fill='both', expand=True)
        left, right = ttk.Frame(panes), ttk.Frame(panes)
        panes.add(left, weight=3)
        panes.add(right, weight=2)
        self.figure = Figure(figsize=(6, 4), layout='constrained')
        self.canvas = FigureCanvasTkAgg(self.figure, master=left)
        toolbar = NavigationToolbar2Tk(self.canvas, left, pack_toolbar=False)
        toolbar.pack(side='bottom', fill='x')
        self.canvas.get_tk_widget().pack(fill='both', expand=True)
        self.contribution_figure = Figure(figsize=(4, 4), layout='constrained')
        self.contribution_canvas = FigureCanvasTkAgg(self.contribution_figure, master=right)
        self.contribution_canvas.get_tk_widget().pack(fill='both', expand=True)

    @property
    def data(self):
        return self.projection if self.projection is not None else self.model.training

    def fit(self):
        try:
            self.app.getCurrentTable()
            from pca_analysis import fit_pca
            columns = [self.df.columns[i] for i in self.columns.curselection()]
            count = self.fields['components'].get().strip()
            kwargs = dict(columns=columns, n_components=int(count) if count else None,
                          scaling={'自动标准化': 'autoscale', '均值中心化': 'center', '不缩放': 'none'}[self.fields['scaling'].get()],
                          variance=float(self.fields['variance'].get())/100,
                          cv_folds=int(self.fields['cv'].get()),
                          missing='error' if self.fields['missing'].get() == '报错' else 'drop')
            self.start(lambda: fit_pca(self.df, **kwargs, cancel=self.cancel_event), 'fit')
        except Exception as exc:
            self.error(exc)

    def start(self, operation, task):
        if self.future is not None:
            return
        self.task = task
        self.cancel_event.clear()
        self.future = self.executor.submit(operation)
        self.fit_button.configure(state='disabled')
        self.project_button.configure(state='disabled')
        self.cancel_button.configure(state='normal')
        self.progress.start()
        self.status.set({'fit': '正在建立 PCA 模型…', 'project': '正在投影新样本…',
                         'load': '正在加载模型…', 'save': '正在保存模型…'}[task])

    def cancel(self):
        if self.future is not None:
            self.cancel_event.set()
            self.status.set('正在取消；当前计算返回后丢弃结果。')

    def poll(self):
        if self.future is not None and self.future.done():
            future, self.future = self.future, None
            self.progress.stop()
            self.fit_button.configure(state='normal')
            self.cancel_button.configure(state='disabled')
            try:
                if self.cancel_event.is_set():
                    self.status.set('已取消，上次模型保留。')
                else:
                    self.app.getCurrentTable()
                    result = future.result()
                    if self.task in ('fit', 'load'):
                        self.model, self.projection = result, None
                        self.loaded_model = self.task == 'load'
                        self.active_table, self.active_snapshot = ((None, None) if self.loaded_model else (self.app.table, self.df))
                        if self.loaded_model:
                            self.color_column.set('')
                    elif self.task == 'project':
                        self.projection = result
                        self.active_table, self.active_snapshot = self.pending_table, self.pending_snapshot
                    if self.task == 'save':
                        self.status.set('模型已保存，包含训练预处理和模型参数。')
                    else:
                        self.publish()
            except Exception as exc:
                self.error(exc)
            self.project_button.configure(state='normal' if self.model is not None else 'disabled')
        self.poll_id = self.main.after(100, self.poll)

    def publish(self):
        self.clear_groups(redraw=False)
        self.active_row = 0
        for tab in self.tabs.values():
            tab.destroy()
        self.tables, self.tabs = {}, {}
        for key, frame in {**self.model.tables, **self.data.tables}.items():
            if not frame.empty:
                self.show_table(key, frame)
        count = self.model.n_components
        for box in self.pc_boxes:
            box.configure(values=[str(i) for i in range(1, count+1)])
        self.pc_x.set('1')
        self.pc_y.set('2' if count > 1 else '1')
        self.plot_kind.set('得分图' if count > 1 else '碎石图')
        self.variable_box.configure(values=list(self.model.columns))
        self.variable.set(str(self.model.columns[0]))
        self.notes.configure(state='normal')
        self.notes.delete('1.0', 'end')
        self.notes.insert('1.0', '\n'.join(self.data.notes))
        self.notes.configure(state='disabled')
        self.draw()
        self.show_contribution(0)
        self.notebook.select(self.explore_tab)
        self.status.set(f'主成分数：{count}；当前为'+('新样本投影' if self.projection is not None else '建模样本')+'。')
        if getattr(self, 'loaded_model', False) and self.projection is None:
            self.status.set(self.status.get()+'加载的训练结果不关联当前工作表。')

    def show_table(self, key, frame):
        if key in self.tabs:
            self.tabs[key].destroy()
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=TITLES.get(key, key))
        shown = export_source_labels(frame)
        table = StatTable(title=TITLES.get(key, key), headers=[HEADERS.get(c, str(c)) for c in frame.columns],
                          values=shown.astype(object).where(pd.notna(shown), None).values.tolist())
        block = TableBlock(tab, table, paginate=True)
        block.pack(fill='both', expand=True)
        block.rowconfigure(1, weight=1)
        block.columnconfigure(0, weight=1)
        block.tree.master.grid(sticky='nsew')
        tab.bind('<Configure>', lambda event: block.fit_titlebar(event.width))
        self.tabs[key], self.tables[key] = tab, frame

    def refresh_sheets(self):
        names = list(self.app.sheets)
        self.sheet_box.configure(values=names)
        if self.sheet_name.get() not in names:
            self.sheet_name.set(names[0] if names else '')

    def project(self):
        try:
            self.app.getCurrentTable()
            if self.model is None:
                raise ValueError('请先建立或加载模型。')
            table = self.app.sheets.get(self.sheet_name.get())
            if table is None:
                raise ValueError('请选择有效的投影数据表。')
            self.pending_table = table
            self.pending_snapshot = table.model.df.copy(deep=True)
            missing = 'error' if self.fields['missing'].get() == '报错' else 'drop'
            self.start(lambda: self.model.project(self.pending_snapshot, missing=missing), 'project')
        except Exception as exc:
            self.error(exc)

    def use_training(self):
        if self.future is not None or self.model is None:
            return
        self.projection = None
        self.active_table, self.active_snapshot = ((self.app.table, self.df) if not getattr(self, 'loaded_model', False) else (None, None))
        self.publish()

    def draw(self):
        if self.model is None:
            return
        try:
            from pca_plots import pca_plot
            if self.plot_handles:
                for selector in self.plot_handles.get('selectors', []):
                    selector.disconnect_events()
                for connection in self.plot_handles.get('connections', []):
                    self.canvas.mpl_disconnect(connection)
            self.figure.clear()
            labels = None
            color = self.color_column.get()
            if color:
                if self.active_snapshot is None or color not in self.active_snapshot:
                    raise ValueError('当前数据没有所选分类列，请取消分类上色。')
                positions = self.data.source.source_row.to_numpy(dtype=int)-1
                series = self.active_snapshot.iloc[positions][color].astype(object)
                labels = series.where(series.notna(), '（缺失类别）').astype(str).to_numpy()
            self.plot_handles = pca_plot(self.model, PLOTS[self.plot_kind.get()], self.figure,
                projection=self.data, components=(int(self.pc_x.get()), int(self.pc_y.get())),
                labels=labels, groups=self.groups, on_pick=self.pick, on_select=self.select,
                selection_shape='ellipse' if self.shape.get() == '椭圆' else 'rectangle',
                active_group=self.active_group.get(), confidence=float(self.ellipse_confidence.get())/100,
                contribution_row=self.active_row,
                variable=('t2' if self.contribution_kind.get() == 'T²' else 'q') if self.plot_kind.get() == 'A/B 贡献对比' else self.variable.get() or None)
            self.canvas.draw()
        except Exception as exc:
            self.error(exc)

    def pick(self, row):
        self.active_row = int(row)
        self.show_contribution(row)
        try:
            if self.active_table is not None:
                if not self.active_table.winfo_exists() or not self.active_table.model.df.equals(self.active_snapshot):
                    raise ValueError('对应工作表已关闭或更改，请重新建模 / 投影后定位。')
                source_row = int(self.data.source.iloc[row].source_row)
                self.active_table.setSelectedRow(source_row-1)
                self.active_table.redraw()
                self.status.set(f'当前样本来源行：{source_row}。')
        except Exception as exc:
            self.error(exc)

    def show_contribution(self, row):
        if self.model is None:
            return
        try:
            from pca_plots import pca_plot
            kind = 't2' if self.contribution_kind.get() == 'T²' else 'q'
            table = self.model.contributions(int(row), kind=kind, projection=self.data)
            self.show_table('contribution', table)
            self.contribution_figure.clear()
            pca_plot(self.model, 'contribution_'+kind, self.contribution_figure,
                     projection=self.data, contribution_row=int(row))
            self.contribution_canvas.draw()
        except Exception as exc:
            self.error(exc)

    def update_contribution(self):
        self.show_contribution(self.active_row)
        if self.plot_kind.get() == 'A/B 贡献对比':
            self.draw()

    def select(self, indices, group):
        self.groups[group] = sorted(set(int(i) for i in indices))
        if 'groups' in self.tabs:
            self.tabs.pop('groups').destroy()
            self.tables.pop('groups')
        self.group_status.set(f'A：{len(self.groups["A"])}；B：{len(self.groups["B"])}')
        rows = []
        for name, members in self.groups.items():
            for i in members:
                rows.append([name, int(self.data.source.iloc[i].source_row), self.data.source.iloc[i].source_index])
        self.show_table('selection', pd.DataFrame(rows, columns=['group', 'source_row', 'source_index']))
        if self.redraw_id is not None:
            self.main.after_cancel(self.redraw_id)
        self.redraw_id = self.main.after_idle(self.redraw)

    def redraw(self):
        self.redraw_id = None
        self.draw()

    def clear_groups(self, redraw=True):
        self.groups = {'A': [], 'B': []}
        self.group_status.set('A：0；B：0')
        if 'groups' in self.tabs:
            self.tabs.pop('groups').destroy()
            self.tables.pop('groups')
        if 'selection' in self.tables:
            self.show_table('selection', pd.DataFrame(columns=['group', 'source_row', 'source_index']))
        if redraw:
            self.draw()

    def compare(self):
        try:
            if self.model is None:
                raise ValueError('请先建立模型。')
            table = self.model.compare_groups(self.groups['A'], self.groups['B'], projection=self.data)
            self.show_table('groups', table)
            self.notebook.select(self.tabs['groups'])
        except Exception as exc:
            self.error(exc)

    def current_table(self):
        self.app.getCurrentTable()
        selected = self.notebook.select()
        key = next((key for key, tab in self.tabs.items() if str(tab) == selected), None)
        if key is None:
            raise ValueError('请先选择要导出的结果表页。')
        return key, self.tables[key]

    def to_sheet(self):
        try:
            key, frame = self.current_table()
            self.app.addSheet(name='PCA_'+TITLES.get(key, key), dataframe=frame.rename(columns=HEADERS).copy())
        except Exception as exc:
            self.error(exc)

    def export(self):
        try:
            _, frame = self.current_table()
            filename = filedialog.asksaveasfilename(parent=self.main, defaultextension='.xlsx',
                filetypes=[('Excel', '*.xlsx'), ('CSV', '*.csv')])
            if filename:
                frame = export_source_labels(frame).rename(columns=HEADERS)
                if filename.lower().endswith('.csv'):
                    frame.to_csv(filename, index=False, encoding='utf-8-sig')
                else:
                    frame.to_excel(filename, index=False)
        except Exception as exc:
            self.error(exc)

    def report(self):
        try:
            self.app.getCurrentTable()
            if self.model is None:
                raise ValueError('请先建立模型。')
            for note in self.data.notes:
                self.app.print(note)
            for key, frame in self.tables.items():
                if not frame.empty:
                    shown = export_source_labels(frame)
                    self.app.print(StatTable(title=TITLES.get(key, key), headers=[HEADERS.get(c, str(c)) for c in frame.columns],
                        values=shown.astype(object).where(pd.notna(shown), None).values.tolist()))
        except Exception as exc:
            self.error(exc)

    def save_model(self):
        if self.future is not None:
            return
        try:
            self.app.getCurrentTable()
            if self.model is None:
                raise ValueError('请先建立或加载模型。')
            filename = filedialog.asksaveasfilename(parent=self.main, defaultextension='.json', filetypes=[('PCA 模型', '*.json')])
            if filename:
                self.start(lambda: self.model.save(filename), 'save')
        except Exception as exc:
            self.error(exc)

    def load_model(self):
        if self.future is not None:
            return
        try:
            self.app.getCurrentTable()
            filename = filedialog.askopenfilename(parent=self.main, filetypes=[('PCA 模型', '*.json')])
            if filename:
                from pca_analysis import load_pca
                self.start(lambda: load_pca(filename), 'load')
        except Exception as exc:
            self.error(exc)

    def save_plot(self, contribution=False):
        try:
            if self.model is None:
                raise ValueError('请先建立模型。')
            filename = filedialog.asksaveasfilename(parent=self.main, defaultextension='.png',
                filetypes=[('PNG', '*.png'), ('PDF', '*.pdf'), ('SVG', '*.svg')])
            if filename:
                (self.contribution_figure if contribution else self.figure).savefig(filename, dpi=150)
        except Exception as exc:
            self.error(exc)

    def error(self, exc):
        self.status.set('失败：'+str(exc))
        messagebox.showerror('主成分分析', str(exc), parent=self.main)

    def help(self, event=None):
        from help_link import open_help
        open_help('stats.pca', parent=self.main)
        return 'break'

    def close(self):
        self.cancel_event.set()
        self.main.after_cancel(self.poll_id)
        if self.redraw_id is not None:
            self.main.after_cancel(self.redraw_id)
        self.executor.shutdown(wait=False, cancel_futures=True)
        self.main.destroy()
