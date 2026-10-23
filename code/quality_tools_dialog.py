"""质量工具窗口；后台只做纯计算，结果绑定打开时的工作表快照。"""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from numbers import Integral
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import pandas as pd
from pandastable_local.dialogs import apply_dialog_theme
from pandastable_local.util import atomic_output
from sheet_context import SheetApp, export_source_labels
from stat_table import StatTable, TableBlock
from capability_dialog import CapabilityToolbar


class QualityToolsDialog:
    def __init__(self, parent, df, app, kind='pareto'):
        self.kind = kind
        self.app = SheetApp(app, parent)
        self.df = df.copy(deep=True)
        self.result = self.future = None
        self.tables, self.blocks = {}, {}
        self.cancel_event = Event()
        self._closed = False
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='quality')
        self.main = tk.Toplevel(parent)
        self.main.title({'pareto': '帕累托图', 'run_chart': '运行图', 'cause_effect': '因果图', 'multi_vari': '多变异图', 'attribute_agreement': '属性一致性分析'}[kind])
        self.main.geometry('880x680')
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
        cols = list(self.df.columns)
        specs = [('category', '缺陷类别列', '', cols), ('frequency', '频数列（原始数据留空）', '', ['']+cols),
                 ('group', '分组列（可空）', '', ['']+cols), ('threshold', '合并阈值 %（空白不合并）', '95', None),
                 ('max_categories', '显示类别数（空白不限）', '', None)]
        if kind == 'run_chart':
            specs = [('measurement', '测量列（原始时间顺序）', '', cols), ('subgroup', '子组 ID 列（可空）', '', ['']+cols),
                     ('size', '固定子组大小（不用 ID 时）', '1', None), ('statistic', '子组统计量', '均值', ['均值', '中位数']),
                     ('alpha', '显著性水平', '0.05', None)]
        if kind == 'cause_effect':
            specs = [('problem', '问题 / 结果（鱼头）', '', None), ('category_col', '导入：类别列', '', ['']+cols),
                     ('cause_col', '导入：原因列', '', ['']+cols), ('subcause_col', '导入：子原因列（可空）', '', ['']+cols)]
        if kind == 'multi_vari':
            specs = [('response', '连续响应 Y', '', cols)] + [(f'factor{i}', f'因子 {i}（按层级顺序，可空）', '', ['']+cols) for i in range(1, 5)]
        if kind == 'attribute_agreement':
            specs = [(key, label, '', ['']+cols) for key, label in [('sample', '样本编号列'), ('appraiser', '评价员列'),
                     ('response', '评价结果列'), ('trial', '试次列（空白按行序推断）'), ('standard', '标准答案列（可空）')]]
            specs += [('scale', '类别尺度', '名义', ['名义', '有序']), ('order', '有序类别顺序（逗号分隔）', '', None), ('confidence', '置信水平 %', '95', None)]
        specs += [('title', '图形标题', '', None), ('xlabel', 'X 轴标签', '', None), ('ylabel', 'Y 轴标签', '', None)]
        for index, (key, label, default, choices) in enumerate(specs):
            row, col = index//2, (index % 2)*2
            ttk.Label(controls, text=label).grid(row=row, column=col, sticky='w', padx=4, pady=2)
            var = self.fields[key] = tk.StringVar(self.main, default)
            widget = (ttk.Entry(controls, textvariable=var) if choices is None else
                      ttk.Combobox(controls, textvariable=var, values=choices, state='readonly'))
            widget.grid(row=row, column=col+1, sticky='ew', padx=4, pady=2)
        if kind == 'cause_effect':
            self.create_cause_editor(controls)
        self.reference = tk.BooleanVar(self.main, True)
        self.raw = tk.BooleanVar(self.main, True)
        self.legend = tk.BooleanVar(self.main, True)
        if kind == 'multi_vari':
            ttk.Checkbutton(controls, text='显示原始观测', variable=self.raw).grid(column=1, sticky='w')
            ttk.Checkbutton(controls, text='显示图例', variable=self.legend).grid(column=1, sticky='w')
        if kind == 'pareto':
            ttk.Checkbutton(controls, text='显示 80% 参考线', variable=self.reference).grid(column=1, sticky='w')
        actions = ttk.Frame(self.main, padding=6)
        actions.pack(fill='x')
        self.fit_button = ttk.Button(actions, text='分析 / 生成', command=self.fit)
        self.fit_button.pack(side='left')
        self.cancel_button = ttk.Button(actions, text='取消计算', command=self.cancel, state='disabled')
        self.cancel_button.pack(side='left', padx=4)
        for label, command in [('打开图形', self.plot), ('完整报告', self.report), ('帮助', self.help), ('关闭', self.close)]:
            ttk.Button(actions, text=label, command=command).pack(side='left', padx=3)
        self.progress = ttk.Progressbar(self.main, mode='indeterminate')
        self.progress.pack(fill='x', padx=6)
        self.status = tk.StringVar(self.main, '请选择输入列。')
        ttk.Label(self.main, textvariable=self.status, wraplength=740).pack(fill='x', padx=6)
        outputs = ttk.Frame(self.main, padding=6)
        outputs.pack(side='bottom', fill='x')
        ttk.Button(outputs, text='当前表写入新工作表', command=self.to_sheet).pack(side='left')
        ttk.Button(outputs, text='导出当前表 CSV / Excel', command=self.export).pack(side='left', padx=4)
        self.notebook = ttk.Notebook(self.main)
        self.notebook.pack(fill='both', expand=True, padx=6, pady=4)
        self.poll_id = self.main.after(100, self.poll)

    def options(self):
        from quality_tools import pareto_chart
        f = {key: var.get().strip() for key, var in self.fields.items()}
        if self.kind == 'cause_effect':
            from quality_tools import cause_effect
            return cause_effect, dict(problem=f['problem'])
        if self.kind == 'multi_vari':
            from quality_tools import multi_vari
            if f['response'] not in self.df:
                raise ValueError('请选择连续响应列。')
            return multi_vari, dict(response=f['response'], factors=[f[f'factor{i}'] for i in range(1, 5) if f[f'factor{i}']])
        if self.kind == 'attribute_agreement':
            from attribute_agreement import attribute_agreement
            if any(f[k] not in self.df for k in ('sample', 'appraiser', 'response')):
                raise ValueError('请选择样本、评价员和评价结果列。')
            if f['scale'] == '有序' and not f['order']:
                raise ValueError('有序类别必须明确填写类别顺序。')
            return attribute_agreement, dict(sample=f['sample'], appraiser=f['appraiser'], response=f['response'],
                        trial=f['trial'] or None, standard=f['standard'] or None,
                        order=[v.strip() for v in f['order'].replace('，', ',').split(',')] if f['scale'] == '有序' else None,
                        confidence=float(f['confidence'])/100, cancel_event=self.cancel_event)
        if self.kind == 'run_chart':
            from quality_tools import run_chart
            if f['measurement'] not in self.df:
                raise ValueError('请选择测量列。')
            return run_chart, dict(measurement=f['measurement'], subgroup=f['subgroup'] or None,
                                  size=1 if f['subgroup'] else int(f['size']),
                                  statistic='mean' if f['statistic'] == '均值' else 'median', alpha=float(f['alpha']))
        if f['category'] not in self.df:
            raise ValueError('请选择缺陷类别列。')
        options = dict(category=f['category'], frequency=f['frequency'] or None, group=f['group'] or None,
                       threshold=float(f['threshold']) if f['threshold'] else None,
                       max_categories=int(f['max_categories']) if f['max_categories'] else None)
        return pareto_chart, options

    def fit(self):
        if self.future is not None:
            return
        try:
            self.app.getCurrentTable()
            function, options = self.options()
            data = self.cause_frame() if self.kind == 'cause_effect' else self.df
            self.pending_plot = {key: self.fields[key].get() for key in ('title', 'xlabel', 'ylabel')}
            self.pending_plot['reference'] = self.reference.get()
            self.pending_plot.update(raw=self.raw.get(), legend=self.legend.get())
            self.cancel_event.clear()
            self.future = self.executor.submit(function, data, **options)
            self.fit_button.configure(state='disabled')
            self.cancel_button.configure(state='normal')
            self.progress.start()
            self.status.set('正在分析…')
        except (ValueError, KeyError, RuntimeError) as exc:
            self.error(exc)

    def cancel(self):
        if self.future is not None:
            self.cancel_event.set()
            self.future.cancel()
            self.status.set('正在取消；计算结束后丢弃结果。')

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
                    self.publish(future.result())
            except Exception as exc:
                self.error(exc)
        self.poll_id = self.main.after(100, self.poll)

    @staticmethod
    def stat_table(title, frame):
        frame = export_source_labels(frame)
        if '频数' in frame:
            frame['频数'] = frame['频数'].map(lambda v: str(v) if isinstance(v, Integral) and v > 2**53-1 else v)
        values = frame.astype(object).where(pd.notna(frame), None).values.tolist()
        return StatTable(title=title, headers=[str(c) for c in frame.columns], values=values,
                         display=[['NA' if v is None else str(v) for v in row] for row in values],
                         number_formats=['General']*len(frame.columns))

    def publish(self, result):
        self.result, self.plot_options = result, self.pending_plot
        for tab in self.notebook.winfo_children():
            tab.destroy()
        self.tables, self.blocks = {}, {}
        for title, frame in result['tables'].items():
            self.tables[title] = frame.copy(deep=True)
            tab = ttk.Frame(self.notebook)
            self.notebook.add(tab, text=title)
            block = TableBlock(tab, self.stat_table(title, frame), paginate=True)
            block.pack(fill='both', expand=True)
            block.rowconfigure(1, weight=1)
            block.columnconfigure(0, weight=1)
            block.tree.master.grid(sticky='nsew')
            self.blocks[str(tab)] = title
        self.status.set('分析完成。' + '；'.join(result['warnings']))

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
                if '频数' in frame:
                    frame['频数'] = frame['频数'].map(lambda v: str(v) if isinstance(v, Integral) and v > 2**53-1 else v)
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
            self.app.addSheet(name='质量_'+title, dataframe=export_source_labels(frame))
        except Exception as exc:
            self.error(exc)

    def report(self):
        try:
            self.app.getCurrentTable()
            if self.result is None:
                raise ValueError('请先分析。')
            self.app.print(self.main.title()+'（来源工作表快照）')
            for note in self.result['warnings']:
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
            from quality_tools_plots import plot_quality
            viewer = self.app.showPlotViewer(deferred=True, figsize=(12, 8))
            try:
                plot_quality(self.result, figure=viewer.fig, **self.plot_options)
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
        self.status.set('失败：'+str(exc))
        messagebox.showerror(self.main.title(), '操作失败：'+str(exc), parent=self.main)

    def help(self, event=None):
        from help_link import open_help
        open_help('quality.'+self.kind, parent=self.main)
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

    def create_cause_editor(self, parent):
        editor = ttk.Frame(parent)
        editor.grid(row=20, column=0, columnspan=4, sticky='ew')
        editor.columnconfigure(0, weight=1)
        self.causes = ttk.Treeview(editor, show='tree', height=5, selectmode='browse')
        self.causes.grid(row=0, column=0, sticky='ew')
        scrollbar = ttk.Scrollbar(editor, command=self.causes.yview)
        scrollbar.grid(row=0, column=1, sticky='ns')
        self.causes.configure(yscrollcommand=scrollbar.set)
        for label in ['人（Personnel）', '机（Machines）', '料（Materials）', '法（Methods）', '测（Measurements）', '环（Environment）']:
            self.causes.insert('', 'end', text=label, open=True)
        self.node_text = tk.StringVar(self.main)
        self.causes.bind('<<TreeviewSelect>>', lambda event: self.node_text.set(self.causes.item(self.causes.selection()[0], 'text')) if self.causes.selection() else None)
        ttk.Entry(editor, textvariable=self.node_text).grid(row=1, column=0, sticky='ew', pady=2)
        actions = ttk.Frame(editor)
        actions.grid(row=2, column=0, columnspan=2, sticky='w')
        for label, command in [('新增类别', lambda: self.add_cause(True)), ('新增下级', self.add_cause),
                               ('修改选中', self.rename_cause), ('删除选中', self.delete_cause), ('从列导入', self.import_causes)]:
            ttk.Button(actions, text=label, command=command).pack(side='left', padx=2)

    def add_cause(self, root=False):
        text = self.node_text.get().strip()
        selection = self.causes.selection()
        parent = '' if root else selection[0] if selection else None
        if not text or parent is None:
            self.error(ValueError('请输入名称；新增下级前请选择父原因。'))
            return
        if parent and self.causes.parent(parent) and self.causes.parent(self.causes.parent(parent)):
            self.error(ValueError('最多支持类别、原因、子原因三级。'))
            return
        self.causes.insert(parent, 'end', text=text, open=True)
        if parent:
            self.causes.item(parent, open=True)

    def rename_cause(self):
        if self.causes.selection() and self.node_text.get().strip():
            self.causes.item(self.causes.selection()[0], text=self.node_text.get().strip())

    def delete_cause(self):
        for item in self.causes.selection():
            self.causes.delete(item)

    def cause_frame(self):
        rows = []
        for category in self.causes.get_children(''):
            name = self.causes.item(category, 'text')
            causes = self.causes.get_children(category)
            if not causes:
                rows.append([name, '', ''])
            for cause in causes:
                text = self.causes.item(cause, 'text')
                children = self.causes.get_children(cause)
                for child in children or ['']:
                    rows.append([name, text, self.causes.item(child, 'text') if child else ''])
        return pd.DataFrame(rows, columns=['类别', '原因', '子原因'])

    def import_causes(self):
        try:
            from quality_tools import cause_effect
            category, cause, sub = [self.fields[k].get() for k in ('category_col', 'cause_col', 'subcause_col')]
            if not category or not cause:
                raise ValueError('请选择类别列和原因列。')
            frame = pd.DataFrame({'类别': self.df[category], '原因': self.df[cause],
                                  '子原因': self.df[sub] if sub else ''})
            frame = cause_effect(frame, '导入')['tables']['原因结构']
            for name, part in frame.groupby('类别', sort=False):
                roots = [n for n in self.causes.get_children('') if self.causes.item(n, 'text') == name]
                root = roots[0] if roots else self.causes.insert('', 'end', text=name, open=True)
                for text, children in part.groupby('原因', sort=False):
                    if text:
                        node = self.causes.insert(root, 'end', text=text, open=True)
                        for child in children['子原因']:
                            if child:
                                self.causes.insert(node, 'end', text=child)
        except (KeyError, ValueError) as exc:
            self.error(exc)
