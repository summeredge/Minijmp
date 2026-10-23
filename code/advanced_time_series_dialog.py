"""时间序列统计分析；保留来源快照和显式采样策略。"""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
import json
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import pandas as pd

from pandastable_local.dialogs import apply_dialog_theme
from pandastable_local.util import atomic_output
from sheet_context import SheetApp, export_source_labels
from stat_table import StatTable, TableBlock


TITLES = {'summary': '模型摘要', 'prepared': '分析数据', 'acf': '自相关', 'pacf': '偏自相关',
          'ccf': '交叉相关', 'stationarity': '平稳性检验', 'decomposition': '季节分解',
          'trend': '趋势分析', 'residuals': '模型残差', 'forecast': '预测', 'diagnostics': '残差诊断',
          'coefficients': '模型参数', 'data': '分析数据', 'status': '各项执行状态',
          'trend_coefficients': '趋势参数', 'model_summary': '模型摘要',
          'model_coefficients': '模型参数', 'residual_acf': '残差自相关'}
HEADERS = {'source_row': '来源行号', 'source_rows': '来源行号集合', 'source_index': '来源索引',
           'timestamp': '时间 / 序号', 'value': '观测值', 'other': '配对观测值',
           'lag': '滞后', 'correlation': '相关系数', 'ci_lower': '区间下限', 'ci_upper': '区间上限',
           'mean': '预测均值', 'fitted': '拟合值', 'observed': '观测值', 'trend': '趋势',
           'seasonal': '季节项', 'residual': '残差', 'statistic': '统计量', 'p_value': 'p 值',
           'test': '检验', 'null': '原假设', 'aic': 'AIC', 'bic': 'BIC', 'n_obs': '样本数',
           'term': '参数', 'estimate': '估计值', 'std_error': '标准误', 'method': '方法',
           'definition': '定义', 'model': '模型', 'n_pairs': '重叠样本数',
           'source_indices': '来源索引集合', 'time': '实际时间', 'elapsed': '经过时间',
           'sequence': '分析序号', 'step': '预测步数', 'predicted': '预测值',
           'analysis': '分析项目', 'status': '状态', 'message': '说明',
           'coefficient': '系数', 'lags': '实际滞后数', 'nobs': '观测数',
           'alternative': '备择假设', 'regression': '确定项', 'reject': '拒绝原假设',
           'critical_1pct': '1% 临界值', 'critical_5pct': '5% 临界值', 'critical_10pct': '10% 临界值',
           'p_value_bound': 'p 值边界说明', 'order': '非季节阶数', 'seasonal_order': '季节阶数',
           'effective_nobs': '有效样本数', 'log_likelihood': '对数似然', 'rmse': '残差均方根',
           'converged': '收敛', 'burn': '诊断起始扣除步数', 'alpha': '显著性水平',
           'diagnostic_used': '用于残差诊断', 'df': '自由度'}
ANALYSES = {'相关分析': 'correlation', '趋势与季节分解': 'decomposition', '平稳性检验': 'stationarity',
            'ARIMA 建模': 'ARIMA', 'SARIMA 建模': 'SARIMA', '全部分析': 'all'}
PLOTS = {'原始序列': 'series', '自相关 ACF': 'acf', '偏自相关 PACF': 'pacf', '交叉相关 CCF': 'ccf',
         '趋势分析': 'trend', '季节分解': 'decomposition', '模型残差': 'residual',
         '残差 QQ': 'residual_qq', '模型预测': 'forecast'}


def export_frame(frame):
    """Excel 以文本保留时长、时区和来源标识，数值结果不舍入。"""
    result = export_source_labels(frame)
    for column in result:
        series = result[column]
        if pd.api.types.is_timedelta64_dtype(series) or isinstance(series.dtype, pd.DatetimeTZDtype):
            result[column] = series.astype(str).where(series.notna(), None)
        elif series.dtype == object:
            result[column] = series.map(lambda value: json.dumps(value, ensure_ascii=False, default=str)
                                        if isinstance(value, (list, tuple)) else value)
    return result.rename(columns=HEADERS)


class TimeSeriesAnalysisDialog:
    def __init__(self, parent=None, df=None, app=None):
        self.app = SheetApp(app, app.getCurrentTable())
        self.df = df.copy(deep=True)
        self.result = self.future = None
        self.cancel_event = Event()
        self._closed = False
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='time-series')
        self.main = tk.Toplevel(parent)
        self.main.title('时间序列分析')
        self.main.geometry('1080x760')
        self.main.minsize(880, 640)
        apply_dialog_theme(self.main)
        self.main.protocol('WM_DELETE_WINDOW', self.close)
        self.main.bind('<Destroy>', self.close, add='+')
        self.main.bind('<F1>', self.help)
        self.main.bind('<Escape>', lambda event: self.cancel())
        self.fields = {}
        controls = ttk.Frame(self.main, padding=6)
        controls.pack(fill='x')
        controls.columnconfigure(1, weight=1)
        controls.columnconfigure(3, weight=1)
        columns = list(self.df.columns)
        specs = [
            (('y', '分析序列 Y', '', columns), ('other', 'CCF 序列 X（可选）', '', ['']+columns)),
            (('time', '时间戳列（留空用固定周期）', '', ['']+columns), ('interval', '固定采样周期', '1min', None)),
            (('analysis', '分析功能', '相关分析', list(ANALYSES)), ('lags', '最大滞后', '20', None)),
            (('missing', '缺失值', '报错', ['报错', '删除不完整行']), ('duplicates', '重复时间戳', '报错', ['报错', '保留首个', '保留末个', '均值聚合'])),
            (('irregular', '不规则采样', '报错', ['报错', '按观测顺序等距']), ('period', '季节周期（样本数）', '12', None)),
            (('decomposition', '季节分解模式', '加法', ['加法', '乘法']), ('forecast_steps', '预测步数', '10', None)),
            (('order', 'ARIMA 阶数 p,d,q', '1,0,0', None), ('seasonal_order', '季节阶数 P,D,Q,s', '0,0,0,0', None)),
            (('confidence', '置信水平（%）', '95', None), None),
        ]
        for row, pair in enumerate(specs):
            for col, spec in zip((0, 2), pair):
                if spec:
                    self.field(controls, row, col, *spec)
        commands = ttk.Frame(self.main, padding=(6, 0))
        commands.pack(fill='x')
        self.run_button = ttk.Button(commands, text='开始分析', command=self.analyze)
        self.run_button.pack(side='left')
        self.cancel_button = ttk.Button(commands, text='取消计算', command=self.cancel, state='disabled')
        self.cancel_button.pack(side='left', padx=4)
        ttk.Button(commands, text='帮助', command=self.help).pack(side='right')
        self.progress = ttk.Progressbar(commands, mode='indeterminate', length=100)
        self.progress.pack(side='right', padx=6)
        self.status = tk.StringVar(self.main, 'CCF(k)=corr(Yₜ,Xₜ₋ₖ)，k>0 表示 X 领先 Y；默认不填补缺失数据。')
        ttk.Label(self.main, textvariable=self.status, wraplength=1000).pack(fill='x', padx=8, pady=4)
        self.notebook = ttk.Notebook(self.main)
        self.notebook.pack(fill='both', expand=True, padx=6, pady=4)
        self.tables, self.tabs = {}, {}
        self.notes_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.notes_tab, text='方法与采样说明')
        self.notes = tk.Text(self.notes_tab, wrap='word', state='disabled')
        scrollbar = ttk.Scrollbar(self.notes_tab, command=self.notes.yview)
        self.notes.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y')
        self.notes.pack(fill='both', expand=True)
        self.plot_tab = ttk.Frame(self.notebook, padding=8)
        self.notebook.add(self.plot_tab, text='图形')
        self.plot_kind = tk.StringVar(self.main, '原始序列')
        ttk.Label(self.plot_tab, text='图形类型').pack(side='left', anchor='n')
        ttk.Combobox(self.plot_tab, textvariable=self.plot_kind, values=list(PLOTS), state='readonly', width=20).pack(side='left', anchor='n', padx=6)
        ttk.Button(self.plot_tab, text='打开图形', command=self.plot).pack(side='left', anchor='n')
        outputs = ttk.Frame(self.main, padding=6)
        outputs.pack(side='bottom', fill='x', before=self.notebook)
        ttk.Button(outputs, text='当前表写入新工作表', command=self.to_sheet).pack(side='left')
        ttk.Button(outputs, text='导出当前表', command=self.export).pack(side='left', padx=4)
        ttk.Button(outputs, text='输出统计报告', command=self.report).pack(side='left')
        ttk.Button(outputs, text='关闭', command=self.close).pack(side='right')
        self.poll_id = self.main.after(100, self.poll)

    def field(self, parent, row, col, key, label, default, choices):
        ttk.Label(parent, text=label).grid(row=row, column=col, sticky='w', padx=(0, 5), pady=2)
        var = self.fields[key] = tk.StringVar(self.main, default)
        widget = (ttk.Entry(parent, textvariable=var) if choices is None else
                  ttk.Combobox(parent, textvariable=var, values=choices, state='readonly'))
        widget.grid(row=row, column=col+1, sticky='ew', padx=(0, 10), pady=2)

    def options(self):
        fields = {key: value.get().strip() for key, value in self.fields.items()}
        analysis = ANALYSES[fields['analysis']]
        model = analysis in ('ARIMA', 'SARIMA', 'all')
        return dict(y=fields['y'], time=fields['time'] or None,
                    other=(fields['other'] or None) if ANALYSES[fields['analysis']] in ('correlation', 'all') else None,
                    interval=fields['interval'], analysis=analysis,
                    missing='error' if fields['missing'] == '报错' else 'drop',
                    duplicates={'报错': 'error', '保留首个': 'first', '保留末个': 'last', '均值聚合': 'mean'}[fields['duplicates']],
                    irregular='error' if fields['irregular'] == '报错' else 'sequence',
                    lags=int(fields['lags']), period=int(fields['period']) if fields['period'] and analysis in ('decomposition', 'all') else None,
                    decomposition='additive' if fields['decomposition'] == '加法' else 'multiplicative',
                    order=tuple(int(x.strip()) for x in fields['order'].split(',')) if model else (1, 0, 0),
                    seasonal_order=tuple(int(x.strip()) for x in fields['seasonal_order'].split(',')) if model else (0, 0, 0, 0),
                    forecast_steps=int(fields['forecast_steps']) if model else 10, alpha=1-float(fields['confidence'])/100)

    def analyze(self):
        if self.future is not None:
            return
        try:
            self.app.getCurrentTable()
            from time_series_analysis import analyze_time_series
            options = self.options()
            self.cancel_event.clear()
            self.future = self.executor.submit(analyze_time_series, self.df, **options, cancel=self.cancel_event)
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
                    self.publish(future.result())
            except Exception as exc:
                self.error(exc)
        self.poll_id = self.main.after(100, self.poll)

    def publish(self, result):
        self.result = result
        for tab in self.tabs.values():
            tab.destroy()
        self.tables, self.tabs = {}, {}
        for key, frame in result.tables.items():
            if not frame.empty:
                self.show_table(key, frame)
        self.notes.configure(state='normal')
        self.notes.delete('1.0', 'end')
        self.notes.insert('1.0', '\n'.join(result.notes))
        self.notes.configure(state='disabled')
        if self.tabs:
            self.notebook.select(next(iter(self.tabs.values())))
        self.status.set('分析完成；采样与方法约定见说明页，预测行不关联历史工作表行号。')
        status = result.tables.get('status')
        if status is not None and status['status'].ne('ok').any():
            self.status.set('部分项目不可用，请查看“各项执行状态”及方法说明。')

    def show_table(self, key, frame):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=TITLES.get(key, key))
        shown = export_frame(frame)
        table = StatTable(title=TITLES.get(key, key), headers=[HEADERS.get(c, str(c)) for c in frame.columns],
                          values=shown.astype(object).where(pd.notna(shown), None).values.tolist())
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
        key = next((k for k, tab in self.tabs.items() if str(tab) == selected), None)
        if key is None:
            raise ValueError('请先分析并选择结果表。')
        return key, self.tables[key]

    def to_sheet(self):
        try:
            key, frame = self.current_table()
            self.app.addSheet(name='时序_'+TITLES.get(key, key), dataframe=frame.rename(columns=HEADERS).copy())
        except Exception as exc:
            self.error(exc)

    def export(self):
        try:
            _, frame = self.current_table()
            filename = filedialog.asksaveasfilename(parent=self.main, defaultextension='.xlsx', filetypes=[('Excel', '*.xlsx'), ('CSV', '*.csv')])
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
                if not frame.empty:
                    shown = export_frame(frame)
                    self.app.print(StatTable(title=TITLES.get(key, key), headers=[HEADERS.get(c, str(c)) for c in frame.columns],
                        values=shown.astype(object).where(pd.notna(shown), None).values.tolist()))
        except Exception as exc:
            self.error(exc)

    def plot(self):
        try:
            self.app.getCurrentTable()
            if self.result is None:
                raise ValueError('请先执行分析。')
            from time_series_analysis_plots import time_series_analysis_plot
            viewer = self.app.showPlotViewer(deferred=True)
            try:
                time_series_analysis_plot(self.result, PLOTS[self.plot_kind.get()], viewer.fig, on_pick=self.pick)
                viewer.canvas.draw()
                self.app.replacePlotViewer(viewer)
                viewer.main.deiconify()
            except Exception:
                viewer.close()
                raise
        except Exception as exc:
            self.error(exc)

    def pick(self, rows):
        try:
            table = self.app.getCurrentTable()
            if not table.model.df.equals(self.df):
                raise ValueError('来源工作表已更改，请重新分析后定位观测。')
            rows = list(rows) if isinstance(rows, (list, tuple)) else [rows]
            table.setSelectedRows([int(row)-1 for row in rows])
            table.redraw()
            self.status.set('选中来源行：'+', '.join(str(row) for row in rows))
        except Exception as exc:
            self.error(exc)

    def error(self, exc):
        self.status.set('失败：'+str(exc))
        messagebox.showerror('时间序列分析', str(exc), parent=self.main)

    def help(self, event=None):
        from help_link import open_help
        open_help('stats.time_series_analysis', parent=self.main)
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
