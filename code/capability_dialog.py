"""完整过程能力窗口；后台拟合，结果固定在来源工作表快照。"""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import pandas as pd
from matplotlib.backends.backend_tkagg import NavigationToolbar2Tk

from pandastable_local.dialogs import apply_dialog_theme
from pandastable_local.util import atomic_output
from sheet_context import SheetApp, export_source_labels
from stat_table import StatTable, TableBlock, display_value


MODES = ['正态能力', '非正态能力', '变换诊断', '正态 Sixpack', '非正态 Sixpack']
DISTRIBUTIONS = {'Weibull': 'weibull', 'Lognormal': 'lognormal', 'Gamma': 'gamma'}
TRANSFORMS = {'无': None, 'Box-Cox': 'boxcox', 'Johnson SU': 'johnson'}


class CapabilityToolbar(NavigationToolbar2Tk):
    toolitems = (
        ('复位', '复位视图', 'home', 'home'),
        ('后退', '返回上个视图', 'back', 'back'),
        ('前进', '前进到下个视图', 'forward', 'forward'),
        ('平移', '拖动平移坐标', 'move', 'pan'),
        ('缩放', '框选区域缩放', 'zoom_to_rect', 'zoom'),
    )


class CapabilityDialog:
    def __init__(self, parent=None, df=None, app=None, mode='正态能力'):
        source = parent if hasattr(parent, 'model') else app.getCurrentTable()
        self.app = SheetApp(app, source)
        self.df = df.copy(deep=True)
        self.result = self.future = None
        self.tables, self.blocks = {}, {}
        self.cancel_event = Event()
        self._closed = False
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='capability')
        self.main = tk.Toplevel(parent)
        self.main.title('过程能力分析与 Sixpack')
        self.main.geometry('900x680')
        self.main.minsize(760, 580)
        apply_dialog_theme(self.main)
        self.main.protocol('WM_DELETE_WINDOW', self.close)
        self.main.bind('<Destroy>', self.close, add='+')
        self.main.bind('<Escape>', lambda event: self.cancel())
        self.main.bind('<F1>', self.help)
        controls = ttk.Frame(self.main, padding=6)
        controls.pack(fill='x')
        controls.columnconfigure(1, weight=1)
        controls.columnconfigure(3, weight=1)
        self.fields = {}
        columns = list(self.df.columns)
        labels = (columns if all(isinstance(c, str) and c for c in columns) else
                  [f'[{i+1}] {c} ({type(c).__name__})' for i, c in enumerate(columns)])
        self.column_map = dict(zip(labels, columns))
        specs = [
            (('measurement', '测量列', '', labels), ('mode', '分析类型', mode, MODES)),
            (('lsl', '规格下限 LSL（可空）', '', None), ('usl', '规格上限 USL（可空）', '', None)),
            (('target', '目标 Target（可空）', '', None), ('confidence', '置信水平（%）', '95', None)),
            (('subgroup', '子组 ID 列（优先）', '', [''] + labels), ('size', '连续子组大小', '1', None)),
            (('distribution', '非正态分布', 'Weibull', list(DISTRIBUTIONS)), ('transform', '正态化变换', 'Box-Cox' if mode == '变换诊断' else '无', list(TRANSFORMS))),
            (('lambda', '固定 λ（空白为估计）', '', None), ('k', '能力总宽 Kσ', '6', None)),
            (('missing', '缺失值', '报错', ['报错', '删除不完整行']), ('recent', '最近子组图数量', '25', None)),
        ]
        for row, pair in enumerate(specs):
            for col, (key, label, default, choices) in zip((0, 2), pair):
                ttk.Label(controls, text=label).grid(row=row, column=col, sticky='w', padx=4, pady=2)
                var = self.fields[key] = tk.StringVar(self.main, default)
                widget = (ttk.Entry(controls, textvariable=var) if choices is None else
                          ttk.Combobox(controls, textvariable=var, values=choices, state='readonly'))
                widget.grid(row=row, column=col+1, sticky='ew', padx=4, pady=2)
        actions = ttk.Frame(self.main, padding=6)
        actions.pack(fill='x')
        self.fit_button = ttk.Button(actions, text='分析', command=self.fit)
        self.fit_button.pack(side='left')
        self.cancel_button = ttk.Button(actions, text='取消计算', command=self.cancel, state='disabled')
        self.cancel_button.pack(side='left', padx=4)
        ttk.Button(actions, text='打开图形', command=self.plot).pack(side='left')
        ttk.Button(actions, text='完整报告', command=self.report).pack(side='left', padx=4)
        ttk.Button(actions, text='帮助', command=self.help).pack(side='right')
        ttk.Button(actions, text='关闭', command=self.close).pack(side='right', padx=4)
        self.progress = ttk.Progressbar(self.main, mode='indeterminate')
        self.progress.pack(fill='x', padx=6)
        self.status = tk.StringVar(self.main, '按打开时快照分析；规格限至少填一侧，变换诊断可不填。')
        ttk.Label(self.main, textvariable=self.status, wraplength=740).pack(fill='x', padx=6)
        outputs = ttk.Frame(self.main, padding=6)
        outputs.pack(side='bottom', fill='x')
        ttk.Button(outputs, text='当前表写入新工作表', command=self.to_sheet).pack(side='left')
        ttk.Button(outputs, text='导出当前表 CSV / Excel', command=self.export).pack(side='left', padx=4)
        self.notebook = ttk.Notebook(self.main)
        self.notebook.pack(fill='both', expand=True, padx=6, pady=4)
        self.poll_id = self.main.after(100, self.poll)

    def options(self):
        fields = {key: var.get().strip() for key, var in self.fields.items()}
        if fields['measurement'] not in self.column_map:
            raise ValueError('请选择测量列。')
        column = self.column_map[fields['measurement']]
        mode = fields['mode']
        nonnormal = mode.startswith('非正态')
        transform = TRANSFORMS[fields['transform']]
        if nonnormal and transform is not None:
            raise ValueError('非正态拟合使用原尺度；请将正态化变换设为“无”。')
        if mode == '变换诊断' and transform is None:
            raise ValueError('请选择 Box-Cox 或 Johnson SU。')
        recent = int(fields['recent'])
        if recent < 1:
            raise ValueError('最近子组数必须为正整数。')
        optional = lambda key: float(fields[key]) if fields[key] else None
        options = dict(lsl=optional('lsl'), usl=optional('usl'), target=optional('target'),
                       confidence=float(fields['confidence'])/100, k=float(fields['k']),
                       subgroup_size=1 if fields['subgroup'] else int(fields['size']),
                       distribution=DISTRIBUTIONS[fields['distribution']] if nonnormal else 'normal',
                       transform=transform, fixed_lambda=optional('lambda'),
                       allow_no_specs=mode == '变换诊断',
                       missing='drop' if fields['missing'] == '删除不完整行' else 'error')
        if fields['subgroup']:
            options['subgroup_ids'] = self.df[self.column_map[fields['subgroup']]].copy()
        return column, mode, recent, options

    def fit(self):
        if self.future is not None:
            return
        try:
            self.app.getCurrentTable()
            column, mode, recent, options = self.options()
            from capability import analyze_capability
            self.pending = (column, mode, recent)
            self.cancel_event.clear()
            self.future = self.executor.submit(analyze_capability, self.df[column].copy(), **options)
            self.fit_button.configure(state='disabled')
            self.cancel_button.configure(state='normal')
            self.progress.start()
            self.status.set('正在估计与诊断…取消将丢弃本次结果，保留上次结果。')
        except Exception as exc:
            self.error(exc)

    def cancel(self):
        if self.future is not None:
            self.cancel_event.set()
            self.status.set('正在取消；等待当前拟合结束后丢弃结果。')

    def poll(self):
        if self._closed:
            return
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
                    self.publish(result)
            except Exception as exc:
                self.error(exc)
        self.poll_id = self.main.after(100, self.poll)

    def publish(self, result):
        from capability_plots import control_diagnostics
        controls = control_diagnostics(result)
        result['tables']['控制图诊断'] = controls.rename(columns={
            'chart': '控制图', 'subgroup': '子组序号', 'size': '子组大小',
            'statistic': '统计量', 'center': '中心线', 'lcl': '下控制限',
            'ucl': '上控制限', 'outside': '超控制限', 'method': '控制限方法'})
        if controls['outside'].fillna(False).any():
            result['warnings'].append('存在超控制限点：过程可能不稳定，能力指数不能替代稳定性诊断。')
        self.result = result
        self.result_settings = self.pending
        for tab in self.notebook.winfo_children():
            tab.destroy()
        self.tables, self.blocks = {}, {}
        for title, frame in result['tables'].items():
            self.tables[title] = frame.copy(deep=True)
            tab = ttk.Frame(self.notebook)
            self.notebook.add(tab, text=title)
            table = self.stat_table(title, frame)
            block = TableBlock(tab, table, paginate=True)
            block.pack(fill='both', expand=True)
            block.rowconfigure(1, weight=1)
            block.columnconfigure(0, weight=1)
            block.tree.master.grid(sticky='nsew')
            tab.bind('<Configure>', lambda event, block=block: block.fit_titlebar(event.width))
            self.blocks[str(tab)] = title
        self.status.set('分析完成。' + '；'.join(result.get('warnings', [])))

    @staticmethod
    def stat_table(title, frame):
        shown = export_source_labels(frame)
        values = shown.astype(object).where(pd.notna(shown), None).values.tolist()
        return StatTable(title=title, headers=[str(c) for c in shown.columns],
                         values=values, display=[['NA' if value is None else display_value(value, str(column))
                             for column, value in zip(shown.columns, row)] for row in values])

    def current_table(self):
        self.app.getCurrentTable()
        title = self.blocks.get(self.notebook.select())
        if title is None:
            raise ValueError('请先分析并选择结果表。')
        return title, self.tables[title]

    def export(self):
        try:
            _, frame = self.current_table()
            path = filedialog.asksaveasfilename(parent=self.main, defaultextension='.xlsx',
                       filetypes=[('Excel', '*.xlsx'), ('CSV', '*.csv')])
            if path:
                frame = export_source_labels(frame)
                with atomic_output(path) as temporary:
                    if path.lower().endswith('.csv'):
                        frame.to_csv(temporary, index=False, encoding='utf-8-sig')
                    else:
                        frame.to_excel(temporary, index=False)
        except Exception as exc:
            self.error(exc)

    def to_sheet(self):
        try:
            title, frame = self.current_table()
            self.app.addSheet(name='能力_' + title, dataframe=export_source_labels(frame))
        except Exception as exc:
            self.error(exc)

    def report(self):
        try:
            self.app.getCurrentTable()
            if self.result is None:
                raise ValueError('请先分析。')
            self.app.print('过程能力分析：' + self.result_settings[0] + '（来源工作表快照）')
            for note in self.result.get('warnings', []):
                self.app.print(note)
            for title, frame in self.tables.items():
                self.app.print(self.stat_table(title, frame))
        except Exception as exc:
            self.error(exc)

    def plot(self):
        try:
            self.app.getCurrentTable()
            if self.result is None:
                raise ValueError('请先分析。')
            from capability_plots import plot_capability
            viewer = self.app.showPlotViewer(deferred=True, figsize=(12, 9))
            try:
                _, mode, recent = self.result_settings
                plot_capability(self.result, figure=viewer.fig, sixpack='Sixpack' in mode, recent=recent)
                viewer.navigation = CapabilityToolbar(viewer.canvas, viewer.ctrlfr)
                viewer.canvas.draw()
                self.app.replacePlotViewer(viewer)
                viewer.main.deiconify()
            except Exception:
                viewer.close()
                raise
        except Exception as exc:
            self.error(exc)

    def error(self, exc):
        self.status.set('失败：' + str(exc))
        messagebox.showerror('过程能力分析', str(exc), parent=self.main)

    def help(self, event=None):
        from help_link import open_help
        open_help('quality.capability_analysis', parent=self.main)
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
