"""高级 SPC 独立窗口；计算和来源快照不随活动工作表切换。"""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import pandas as pd

from advanced_spc import NELSON
from pandastable_local.dialogs import apply_dialog_theme
from pandastable_local.util import atomic_output
from sheet_context import SheetApp, export_source_labels
from stat_table import StatTable, TableBlock


CURRENT = '当前数据（Phase I / 已知参数）'
KINDS = {'EWMA': 'EWMA', 'CUSUM': 'CUSUM', 'Nelson': 'Nelson', 'Hotelling T²': 'T2'}
TITLES = {'summary': '模型摘要', 'parameters': '基线参数', 'comparison': '基线与当前对比',
          'limits': '控制限', 'settings': '控制图设置', 'covariance': '基线协方差',
          'observations': '当前监控观测', 'baseline': '历史基线观测', 'alarms': '异常记录'}
HEADERS = {'parameter': '项目', 'value': '数值', 'variable': '变量', 'mean': '均值', 'std': '标准差',
           'baseline_n': '基线样本数', 'baseline_mean': '基线均值', 'baseline_std': '基线标准差',
           'current_n': '当前样本数', 'current_mean': '当前均值', 'current_std': '当前标准差',
           'difference': '均值差（当前−基线）', 'phase': '阶段', 'confidence': '控制限置信度',
           'lower': '下控制限', 'upper': '上控制限', 'center': '中心线', 'method': '计算方法',
           'source_row': '来源行号', 'source_index': '来源索引', 'sequence': '分析序号',
           'z': '标准化观测', 'statistic': '统计量', 'negative': 'CUSUM 负支',
           'alarm': '异常标记', 'rules': '触发规则', 'rule': '规则', 'description': '规则说明',
           'window_start': '窗口起始序号', 'window_end': '窗口末端序号', 'members': '窗口来源行号',
           'row_variable': '行变量', 'column_variable': '列变量', 'covariance': '协方差'}
ITEMS = {'chart': '控制图', 'phase': '监控阶段', 'n': '当前样本数', 'baseline_n': '基线样本数',
         'variables': '变量', 'alarm_points': '异常观测数', 'alarm_records': '异常记录数',
         'confidence': '控制限置信度', 'lambda': 'EWMA λ', 'L': 'EWMA 限宽 L',
         'k': 'CUSUM 参考值 k', 'h': 'CUSUM 阈值 h', 'rules': '启用规则'}
PHASES = {'phase1': 'Phase I（自身基线）', 'phase2': 'Phase II（独立监控）', 'known': '已知参数'}


def display_frame(frame):
    """仅翻译报告标签；计算结果和工作表列值不在后端改写。"""
    result = frame.copy()
    if 'parameter' in result:
        if 'value' in result:
            mask = result['parameter'].eq('phase')
            result.loc[mask, 'value'] = result.loc[mask, 'value'].replace(PHASES)
            mask = result['parameter'].eq('chart') & result['value'].eq('T2')
            if mask.any():
                result.loc[mask, 'value'] = 'Hotelling T²'
        result['parameter'] = result['parameter'].replace(ITEMS)
    if 'phase' in result:
        result['phase'] = result['phase'].replace(PHASES)
    return result.rename(columns=HEADERS)


def export_frame(frame):
    """来源索引按文本导出，避免 Excel 损失大整数或前导零。"""
    return display_frame(export_source_labels(frame))


class AdvancedSPCDialog:
    def __init__(self, parent=None, df=None, app=None):
        source = parent if hasattr(parent, 'model') else app.getCurrentTable()
        self.app = SheetApp(app, source)
        self.df = df.copy(deep=True)
        self.result = self.future = None
        self.cancel_event = Event()
        self._closed = False
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='advanced-spc')
        self.main = tk.Toplevel(parent)
        self.main.title('高级 SPC 控制图')
        self.main.geometry('1120x780')
        self.main.minsize(900, 640)
        apply_dialog_theme(self.main)
        self.main.protocol('WM_DELETE_WINDOW', self.close)
        self.main.bind('<Destroy>', self.close, add='+')
        self.main.bind('<Escape>', lambda event: self.cancel())
        self.main.bind('<F1>', self.help)
        self.fields = {}
        controls = ttk.Frame(self.main, padding=6)
        controls.pack(fill='x')
        selection = ttk.LabelFrame(controls, text='分析变量', padding=4)
        selection.pack(side='left', fill='y', padx=(0, 8))
        self.columns = list(self.df.columns)
        self.x_list = tk.Listbox(selection, selectmode='extended', exportselection=False, height=7, width=20)
        for column in self.columns:
            self.x_list.insert('end', str(column))
        scrollbar = ttk.Scrollbar(selection, command=self.x_list.yview)
        scrollbar.pack(side='right', fill='y')
        self.x_list.configure(yscrollcommand=scrollbar.set)
        self.x_list.pack(fill='both', expand=True)
        parameters = ttk.Frame(controls)
        parameters.pack(side='left', fill='both', expand=True)
        parameters.columnconfigure(1, weight=1)
        parameters.columnconfigure(3, weight=1)
        specs = [
            (('kind', '控制图', 'EWMA', list(KINDS)), ('baseline', '历史基线', CURRENT, [CURRENT])),
            (('mean', '已知均值（可选）', '', None), ('sigma', '已知标准差（可选）', '', None)),
            (('ewma_lambda', 'EWMA λ', '0.2', None), ('ewma_width', 'EWMA 限宽 L', '3', None)),
            (('cusum_k', 'CUSUM 参考值 k', '0.5', None), ('cusum_h', 'CUSUM 阈值 h', '5', None)),
            (('confidence', 'T² 置信度（%）', '95', ['95', '99']), ('missing', '缺失值', '报错', ['报错', '删除不完整行'])),
        ]
        for row, pair in enumerate(specs):
            for col, spec in zip((0, 2), pair):
                widget = self.field(parameters, row, col, *spec)
                if spec[0] == 'baseline':
                    self.baseline_box = widget
                    widget.configure(postcommand=self.refresh_baselines)
        self.refresh_baselines()
        rules = ttk.LabelFrame(self.main, text='Nelson 判异规则（仅用于 Nelson 图）', padding=4)
        rules.pack(fill='x', padx=6)
        self.rules = {}
        for i, (rule, text) in enumerate(NELSON.items()):
            variable = self.rules[rule] = tk.BooleanVar(self.main, True)
            ttk.Checkbutton(rules, text=f'{rule}. {text}', variable=variable).grid(
                row=i//2, column=i % 2, sticky='w', padx=(0, 12))
        rules.columnconfigure(0, weight=1)
        rules.columnconfigure(1, weight=1)
        commands = ttk.Frame(self.main, padding=(6, 4))
        commands.pack(fill='x')
        self.run_button = ttk.Button(commands, text='开始分析', command=self.analyze)
        self.run_button.pack(side='left')
        self.cancel_button = ttk.Button(commands, text='取消计算', command=self.cancel, state='disabled')
        self.cancel_button.pack(side='left', padx=4)
        ttk.Button(commands, text='打开控制图', command=self.plot).pack(side='left')
        ttk.Button(commands, text='帮助', command=self.help).pack(side='right')
        self.progress = ttk.Progressbar(commands, mode='indeterminate', length=100)
        self.progress.pack(side='right', padx=6)
        self.status = tk.StringVar(self.main, 'T² 可选多个变量；其余图选一列。已知均值和标准差需同时填写，且不与历史基线混用。')
        ttk.Label(self.main, textvariable=self.status, wraplength=850).pack(fill='x', padx=8, pady=4)
        self.notebook = ttk.Notebook(self.main)
        self.notebook.pack(fill='both', expand=True, padx=6, pady=4)
        self.tables, self.tabs = {}, {}
        notes_tab = ttk.Frame(self.notebook)
        self.notebook.add(notes_tab, text='方法与来源说明')
        self.notes = tk.Text(notes_tab, wrap='word', state='disabled')
        scrollbar = ttk.Scrollbar(notes_tab, command=self.notes.yview)
        scrollbar.pack(side='right', fill='y')
        self.notes.configure(yscrollcommand=scrollbar.set)
        self.notes.pack(fill='both', expand=True)
        self.outputs = ttk.Frame(self.main, padding=6)
        self.outputs.pack(side='bottom', fill='x', before=self.notebook)
        ttk.Button(self.outputs, text='当前表写入新工作表', command=self.to_sheet).pack(side='left')
        ttk.Button(self.outputs, text='导出当前表', command=self.export).pack(side='left', padx=4)
        ttk.Button(self.outputs, text='输出统计报告', command=self.report).pack(side='left')
        ttk.Button(self.outputs, text='关闭', command=self.close).pack(side='right')
        self.poll_id = self.main.after(100, self.poll)

    def field(self, parent, row, col, key, label, default, choices):
        ttk.Label(parent, text=label).grid(row=row, column=col, sticky='w', padx=(0, 5), pady=2)
        var = self.fields[key] = tk.StringVar(self.main, default)
        widget = (ttk.Entry(parent, textvariable=var, width=16) if choices is None else
                  ttk.Combobox(parent, textvariable=var, values=choices, state='readonly', width=20))
        widget.grid(row=row, column=col+1, sticky='ew', padx=(0, 8), pady=2)
        return widget

    def refresh_baselines(self):
        self.baseline_tables = {'历史：'+name: table for name, table in self.app.sheets.items()
                                if table is not self.app.table}
        self.baseline_box.configure(values=[CURRENT]+list(self.baseline_tables))

    def options(self):
        fields = {key: value.get().strip() for key, value in self.fields.items()}
        columns = [self.columns[i] for i in self.x_list.curselection()]
        kind = KINDS[fields['kind']]
        if not columns or (kind != 'T2' and len(columns) != 1):
            raise ValueError('T² 至少选择一列，其余控制图须只选择一列。')
        mean = float(fields['mean']) if fields['mean'] else None
        sigma = float(fields['sigma']) if fields['sigma'] else None
        if (mean is None) != (sigma is None):
            raise ValueError('已知均值和标准差必须同时填写。')
        baseline = None
        if fields['baseline'] != CURRENT:
            if mean is not None:
                raise ValueError('已知参数不可与历史基线混用。')
            table = self.baseline_tables.get(fields['baseline'])
            if (table is None or table is self.app.table or
                    not any(table is item for item in self.app.sheets.values()) or not table.winfo_exists()):
                raise ValueError('请选择仍打开的其他工作表作为独立历史基线。')
            baseline = table.model.df.copy(deep=True)
        return dict(columns=columns, kind=kind, baseline=baseline, mean=mean, sigma=sigma,
                    ewma_lambda=float(fields['ewma_lambda']) if kind == 'EWMA' else .2,
                    ewma_width=float(fields['ewma_width']) if kind == 'EWMA' else 3.,
                    cusum_k=float(fields['cusum_k']) if kind == 'CUSUM' else .5,
                    cusum_h=float(fields['cusum_h']) if kind == 'CUSUM' else 5.,
                    confidence=float(fields['confidence'])/100,
                    missing='error' if fields['missing'] == '报错' else 'drop',
                    rules=tuple(rule for rule, var in self.rules.items() if var.get()))

    def analyze(self):
        if self.future is not None:
            return
        try:
            self.app.getCurrentTable()
            from advanced_spc import analyze_spc
            options = self.options()
            self.pending_origin = '当前数据为窗口打开时的来源快照；基线：'+self.fields['baseline'].get()+'（计算启动时快照）。'
            self.cancel_event.clear()
            self.future = self.executor.submit(analyze_spc, self.df, **options, cancel=self.cancel_event)
            self.run_button.configure(state='disabled')
            self.cancel_button.configure(state='normal')
            self.progress.start()
            self.status.set('正在分析…')
        except Exception as exc:
            self.error(exc)

    def cancel(self):
        if self.future is not None:
            self.cancel_event.set()
            self.status.set('正在取消；当前计算返回后丢弃结果。')

    def poll(self):
        if self._closed:
            return
        self.poll_id = None
        if self.future is not None and self.future.done():
            future, self.future = self.future, None
            self.progress.stop()
            self.run_button.configure(state='normal')
            self.cancel_button.configure(state='disabled')
            try:
                if self.cancel_event.is_set():
                    self.status.set('已取消，上次分析结果保留。')
                else:
                    self.app.getCurrentTable()
                    result = future.result()
                    result.notes.append(self.pending_origin)
                    self.publish(result)
            except Exception as exc:
                self.error(exc)
        self.poll_id = self.main.after(100, self.poll)

    def publish(self, result):
        self.result = result
        for tab in self.tabs.values():
            tab.destroy()
        self.tables, self.tabs = {}, {}
        for key, frame in result.tables.items():
            self.show_table(key, frame)
        self.notes.configure(state='normal')
        self.notes.delete('1.0', 'end')
        self.notes.insert('1.0', '\n'.join(result.notes))
        self.notes.configure(state='disabled')
        self.notebook.select(self.tabs['summary'])
        count = int(result.tables['observations']['alarm'].sum())
        self.status.set(f'分析完成，异常观测 {count} 个；判异定义和控制限假设见方法说明。')

    def show_table(self, key, frame):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=TITLES.get(key, key))
        display = export_frame(frame)
        table = StatTable(title=TITLES.get(key, key), headers=list(display.columns),
                          values=display.astype(object).where(pd.notna(display), None).values.tolist())
        block = TableBlock(tab, table, paginate=True)
        block.pack(fill='both', expand=True)
        block.rowconfigure(1, weight=1)
        block.columnconfigure(0, weight=1)
        block.tree.master.grid(sticky='nsew')
        tab.bind('<Configure>', lambda event: block.fit_titlebar(event.width))
        self.tables[key], self.tabs[key] = frame, tab

    def current_table(self):
        self.app.getCurrentTable()
        selected = self.notebook.select()
        key = next((key for key, tab in self.tabs.items() if str(tab) == selected), None)
        if key is None:
            raise ValueError('请先分析并选择结果表。')
        return key, self.tables[key]

    def to_sheet(self):
        try:
            key, frame = self.current_table()
            self.app.addSheet(name='SPC_'+TITLES.get(key, key), dataframe=display_frame(frame))
        except Exception as exc:
            self.error(exc)

    def export(self):
        try:
            _, frame = self.current_table()
            filename = filedialog.asksaveasfilename(parent=self.main, defaultextension='.xlsx',
                filetypes=[('Excel', '*.xlsx'), ('CSV', '*.csv')])
            if filename:
                frame = export_frame(frame)
                with atomic_output(filename) as temporary:
                    if filename.lower().endswith('.csv'):
                        frame.to_csv(temporary, index=False, encoding='utf-8-sig')
                    else:
                        frame.to_excel(temporary, index=False)
        except Exception as exc:
            self.error(exc)

    def report(self):
        try:
            self.app.getCurrentTable()
            if self.result is None:
                raise ValueError('请先执行分析。')
            for note in self.result.notes:
                self.app.print(note)
            for key, frame in self.result.tables.items():
                display = export_frame(frame)
                self.app.print(StatTable(title=TITLES.get(key, key), headers=list(display.columns),
                    values=display.astype(object).where(pd.notna(display), None).values.tolist()))
        except Exception as exc:
            self.error(exc)

    def plot(self):
        try:
            self.app.getCurrentTable()
            if self.result is None:
                raise ValueError('请先执行分析。')
            from advanced_spc_plots import spc_plot
            viewer = self.app.showPlotViewer(deferred=True)
            try:
                spc_plot(self.result, viewer.fig, on_pick=self.pick)
                viewer.canvas.draw()
                self.app.replacePlotViewer(viewer)
                viewer.main.deiconify()
            except Exception:
                viewer.close()
                raise
        except Exception as exc:
            self.error(exc)

    def pick(self, row):
        try:
            table = self.app.getCurrentTable()
            if not table.model.df.equals(self.df):
                raise ValueError('来源工作表已更改，请重新打开分析窗口后定位观测。')
            table.setSelectedRows([int(row)-1])
            table.redraw()
            self.status.set('选中来源行：'+str(row))
        except Exception as exc:
            self.error(exc)

    def error(self, exc):
        self.status.set('失败：'+str(exc))
        messagebox.showerror('高级 SPC 控制图', str(exc), parent=self.main)

    def help(self, event=None):
        from help_link import open_help
        open_help('quality.advanced_spc', parent=self.main)
        return 'break'

    def close(self, event=None):
        if event is not None and event.widget is not self.main:
            return
        if self._closed:
            return
        self._closed = True
        self.cancel_event.set()
        if self.future is not None:
            self.future.cancel()
        if self.poll_id is not None:
            try:
                self.main.after_cancel(self.poll_id)
            except tk.TclError:
                pass
            self.poll_id = None
        self.executor.shutdown(wait=False, cancel_futures=True)
        if event is None:
            self.main.destroy()
