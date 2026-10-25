"""阶段对比结果窗口：显示表格与图形，复用现有查看器和来源工作表输出。"""
import tkinter as tk
from tkinter import LEFT, filedialog, messagebox, ttk

import pandas as pd

from improvement_chart import phase_control_plot, print_report
from pandastable_local.dialogs import apply_dialog_theme
from pandastable_local.util import atomic_output
from sheet_context import SheetApp
from stat_table import StatTable, TableBlock


TITLES = {'summary': '数据摘要', 'limits': '控制限与控制图',
          'limit_details': '逐子组控制限', 'metrics': '阶段指标对比',
          'ratios': '变化率与波动比', 'anomalies': '异常点明细',
          'tests': '统计检验', 'conclusions': '分析结论'}


class ImprovementChartDialog:
    """由 control chart 窗口传入已算好的 result；不在本窗口重复选项。"""
    def __init__(self, parent=None, app=None, result=None):
        source = parent if hasattr(parent, 'model') else app.getCurrentTable()
        self.app = app if isinstance(app, SheetApp) else SheetApp(app, source)
        self.result = result
        self._closed = False
        self.main = tk.Toplevel(parent)
        self.main.title('阶段对比结果')
        self.main.geometry('1080x700')
        self.main.minsize(880, 600)
        apply_dialog_theme(self.main)
        self.main.protocol('WM_DELETE_WINDOW', self.close)
        self.main.bind('<Destroy>', self.close, add='+')
        self.main.bind('<F1>', self.help)
        self.status = tk.StringVar(self.main, '结果与图形使用同一份计算结果。')
        ttk.Label(self.main, textvariable=self.status, wraplength=1000).pack(
            fill='x', padx=8, pady=4)
        self.notebook = ttk.Notebook(self.main)
        self.notebook.pack(fill='both', expand=True, padx=6, pady=4)
        self.tables, self.tabs = {}, {}
        outputs = ttk.Frame(self.main, padding=6)
        outputs.pack(side='bottom', fill='x', before=self.notebook)
        ttk.Button(outputs, text='打开控制图', command=self.plot).pack(side=LEFT)
        ttk.Button(outputs, text='当前表写入新工作表', command=self.to_sheet).pack(side=LEFT, padx=4)
        ttk.Button(outputs, text='导出当前表', command=self.export).pack(side=LEFT)
        ttk.Button(outputs, text='输出完整报告', command=self.report).pack(side=LEFT, padx=4)
        ttk.Button(outputs, text='关闭', command=self.close).pack(side='right')
        if result is not None:
            self.publish(result)

    def publish(self, result):
        self.result = result
        for tab in self.tabs.values():
            tab.destroy()
        self.tables, self.tabs = {}, {}
        for key, frame in result.tables.items():
            if key == 'limit_details' and not len(frame):
                continue
            self.show_table(key, frame)
        self.notebook.select(self.tabs['summary'])

    def show_table(self, key, frame):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=TITLES.get(key, key))
        table = StatTable(title=TITLES.get(key, key), headers=list(frame.columns),
                          values=frame.astype(object).where(pd.notna(frame), None).values.tolist())
        block = TableBlock(tab, table, paginate=True)
        block.pack(fill='both', expand=True)
        block.rowconfigure(1, weight=1)
        block.columnconfigure(0, weight=1)
        block.tree.master.grid(sticky='nsew')
        tab.bind('<Configure>', lambda event: block.fit_titlebar(event.width))
        self.tables[key], self.tabs[key] = frame, tab

    def current_table(self):
        key = next((key for key, tab in self.tabs.items()
                    if str(tab) == self.notebook.select()), None)
        if key is None:
            raise ValueError('请先执行分析并选择结果表。')
        return key, self.tables[key]

    def to_sheet(self):
        try:
            key, frame = self.current_table()
            self.app.addSheet(name='阶段对比_' + TITLES.get(key, key),
                              dataframe=frame.copy(deep=True))
        except Exception as exc:
            self.error(exc)

    def export(self):
        try:
            _, frame = self.current_table()
            filename = filedialog.asksaveasfilename(parent=self.main, defaultextension='.xlsx',
                filetypes=[('Excel', '*.xlsx'), ('CSV', '*.csv')])
            if filename:
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
                raise ValueError('没有可输出的分析结果。')
            print_report(self.result, self.app.print)
        except Exception as exc:
            self.error(exc)

    def plot(self):
        try:
            self.app.getCurrentTable()
            if self.result is None:
                raise ValueError('没有可绘制的分析结果。')
            viewer = self.app.showPlotViewer(deferred=True, figsize=(11, 8))
            try:
                phase_control_plot(self.result, viewer.fig)
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
        messagebox.showerror('阶段对比结果', str(exc), parent=self.main)

    def help(self, event=None):
        from help_link import open_help
        open_help('quality.improvement_chart', parent=self.main)
        return 'break'

    def close(self, event=None):
        if event is not None and event.widget is not self.main:
            return
        if self._closed:
            return
        self._closed = True
        if event is None:
            self.main.destroy()
