"""两水平部分因子与 Plackett–Burman 的 Foldover 工作表操作。"""
import tkinter as tk
from tkinter import messagebox, ttk

from doe_foldover import create_foldover, foldover_summary
from doe_pb_foldover import create_pb_foldover, pb_foldover_summary
from help_link import open_help


class FoldoverDOE:
    def __init__(self, app):
        self.app = app
        self.sources = {}
        for name, table in app.sheets.items():
            metadata = getattr(table, 'doe_metadata', None)
            if not isinstance(metadata, dict) or not isinstance(metadata.get('design'), dict):
                continue
            design = metadata['design']
            design_type = design.get('design_type')
            if design_type not in ('two_level_fractional', 'plackett_burman'):
                continue
            if design.get('foldover_lineage') is not None:
                continue
            try:
                frame = app._full_frame(table)
                if design_type == 'plackett_burman':
                    pb_foldover_summary(frame, metadata)
                else:
                    foldover_summary(frame, metadata)
            except (ValueError, TypeError, OverflowError, KeyError):
                continue
            self.sources[name] = table

        if not self.sources:
            self.main = None
            messagebox.showerror(
                'Foldover', '当前工作簿没有可折叠的正规两水平部分因子或 PB 设计。',
                parent=app.main)
            return

        self.main = tk.Toplevel(app.main)
        self.main.title('折叠两水平部分因子设计')
        self.main.transient(app.main)
        self.main.bind('<F1>', lambda event: open_help(self.help_topic(), parent=self.main))
        body = ttk.Frame(self.main, padding=10)
        body.pack(fill='both', expand=True)

        ttk.Label(body, text='来源工作表').grid(row=0, column=0, sticky='w', padx=(0, 6), pady=4)
        self.source = ttk.Combobox(body, values=tuple(self.sources), state='readonly', width=28)
        current = app.getCurrentSheet()
        self.source.set(current if current in self.sources else next(iter(self.sources)))
        self.source.grid(row=0, column=1, sticky='ew', pady=4)
        self.source.bind('<<ComboboxSelected>>', self._source_changed)

        ttk.Label(body, text='折叠因子').grid(row=1, column=0, sticky='w', padx=(0, 6), pady=4)
        self.folded = ttk.Combobox(body, state='readonly', width=28)
        self.folded.grid(row=1, column=1, sticky='ew', pady=4)
        self.folded.bind('<<ComboboxSelected>>', self._selection_changed)

        self.limits = tk.StringVar(value='')
        ttk.Label(body, textvariable=self.limits, wraplength=420,
                  justify='left').grid(row=3, column=0, columnspan=2, sticky='w')

        ttk.Label(body, text='预览').grid(row=2, column=0, sticky='nw', padx=(0, 6), pady=4)
        preview_frame = ttk.Frame(body)
        preview_frame.grid(row=2, column=1, sticky='nsew', pady=4)
        self.preview_text = tk.Text(preview_frame, width=72, height=12, wrap='word',
                                    state='disabled')
        scrollbar = ttk.Scrollbar(preview_frame, orient='vertical',
                                  command=self.preview_text.yview)
        self.preview_text.configure(yscrollcommand=scrollbar.set)
        self.preview_text.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        buttons = ttk.Frame(body)
        buttons.grid(row=4, column=1, sticky='e', pady=(8, 0))
        self.preview_button = ttk.Button(buttons, text='预览', command=self.preview)
        self.preview_button.pack(side='left', padx=(0, 6))
        self.create_button = ttk.Button(buttons, text='创建折叠工作表', command=self.create)
        self.create_button.pack(side='left', padx=(0, 6))
        self.cancel_button = ttk.Button(buttons, text='取消', command=self.cancel)
        self.cancel_button.pack(side='left')
        body.columnconfigure(1, weight=1)
        body.rowconfigure(2, weight=1)

        self._update_factors()
        self._update_limits()
        self.preview()

    def _update_factors(self):
        design = self.sources[self.source.get()].doe_metadata['design']
        factor_ids = [factor['factor_id'] for factor in design['factors']]
        choices = ('全部', *factor_ids)
        previous = self.folded.get()
        self.folded.configure(values=choices)
        self.folded.set(previous if previous in choices else '全部')

    def help_topic(self):
        table = self.sources.get(self.source.get())
        design = None if table is None else table.doe_metadata['design']
        return 'doe.pb' if design and design.get('design_type') == 'plackett_burman' \
            else 'doe.fractional'

    def _source_changed(self, event=None):
        self._update_factors()
        self._update_limits()
        self.preview()

    def _update_limits(self):
        table = self.sources.get(self.source.get())
        design = None if table is None else table.doe_metadata['design']
        if design and design.get('design_type') == 'plackett_burman':
            count = len(table.model.df)
            self.limits.set(f'来源设计：Plackett–Burman，{count} 次运行。'
                            '仅支持连续两水平因子、无中心点、无区组、单批次、一次折叠。')
        else:
            self.limits.set('来源设计：正规两水平部分因子。')

    def _selection_changed(self, event=None):
        self._update_limits()
        self.preview()

    def _source_data(self):
        name = self.source.get()
        table = self.app.sheets.get(name)
        if table is None:
            raise ValueError('来源工作表已关闭，请重新选择工作表。')
        return name, self.app._full_frame(table), table.doe_metadata

    @staticmethod
    def _resolution(value):
        if value is None:
            return '无非平凡定义关系'
        return {3: 'III', 4: 'IV', 5: 'V', 6: 'VI'}.get(value, str(value))

    def _show_preview(self, text):
        self.preview_text.configure(state='normal')
        self.preview_text.delete('1.0', 'end')
        self.preview_text.insert('1.0', text)
        self.preview_text.configure(state='disabled')

    def preview(self):
        table = self.sources.get(self.source.get())
        if table is not None and table.doe_metadata['design']['design_type'] == 'plackett_burman':
            return self._preview_pb()
        try:
            _, frame, metadata = self._source_data()
            before = foldover_summary(frame, metadata)
            folded_frame, folded_metadata = create_foldover(
                frame, metadata, None if self.folded.get() == '全部' else self.folded.get())
            after = foldover_summary(folded_frame, folded_metadata)
        except (ValueError, TypeError, OverflowError, KeyError) as error:
            self._show_preview('预览不可用。')
            messagebox.showerror('Foldover', str(error), parent=self.main)
            return False

        before_aliases = {group['label'] for group in before['alias_groups']}
        after_aliases = {group['label'] for group in after['alias_groups']}
        changes = ([f'− {label}' for label in sorted(before_aliases - after_aliases)]
                   + [f'+ {label}' for label in sorted(after_aliases - before_aliases)])
        if not changes:
            changes = ['别名组无变化。']
        self._show_preview(
            f'运行数：{len(frame)} → {len(folded_frame)}（新增 {len(folded_frame) - len(frame)}）\n'
            f'分辨度：{self._resolution(before["resolution"])} → '
            f'{self._resolution(after["resolution"])}\n'
            f'全模型秩：{before["model_rank"]} → {after["model_rank"]}\n'
            '别名变化：\n' + '\n'.join(changes))
        return True

    def _preview_pb(self):
        """PB 预览只报告实际矩阵的秩与混杂，不使用正规定义关系。"""
        try:
            name, frame, metadata = self._source_data()
            folded_frame, folded_metadata, summary = create_pb_foldover(
                frame, metadata, None if self.folded.get() == '全部' else self.folded.get())
        except (ValueError, TypeError, OverflowError, KeyError) as error:
            self._show_preview('预览不可用。')
            messagebox.showerror('Foldover', str(error), parent=self.main)
            return False
        before, after = summary['before'], summary['after']
        folded = '全部因子' if summary['folded_factors'] and len(
            summary['folded_factors']) > 1 else summary['folded_factors'][0]
        effect = ('折叠未减少混杂，只增加重复点。'
                  if not summary['confounding_reduced'] else
                  '折叠按实际矩阵减少了混杂。')
        self._show_preview(
            f'来源：Plackett–Burman {before["runs"]} 次运行；折叠：{folded}\n'
            f'运行数：{before["runs"]} → {summary["total_runs"]}'
            f'（新增 {summary["added_runs"]}，批次 {summary["batch_id"]}）\n'
            f'主效应模型秩：{before["main_rank"]} → {after["main_rank"]}\n'
            f'主效应+二阶交互秩：{before["joint_rank"]} → {after["joint_rank"]}'
            f'（参数 {before["joint_parameter_count"]}）\n'
            f'完全混杂交互：{len(before["complete"])} → {len(after["complete"])}；'
            f'部分混杂交互：{len(before["partial"])} → {len(after["partial"])}\n'
            f'可单独估计交互：{len(before["estimable"])} → {len(after["estimable"])}；'
            f'不可估计交互：{len(before["unestimable"])} → {len(after["unestimable"])}\n'
            f'{effect}\n'
            'PB 无正规定义关系；以上为实际编码矩阵的投影结果。\n'
            '限制：仅连续两水平因子、无中心点、无区组、单批次、一次折叠。')
        return True

    def create(self):
        table = self.sources.get(self.source.get())
        if table is not None and table.doe_metadata['design']['design_type'] == 'plackett_burman':
            return self._create_pb()
        try:
            name, frame, metadata = self._source_data()
            folded_frame, folded_metadata = create_foldover(
                frame, metadata, None if self.folded.get() == '全部' else self.folded.get())
            self.app.addSheet(f'{name} Foldover', folded_frame, {'doe': folded_metadata})
        except (ValueError, TypeError, OverflowError, KeyError) as error:
            messagebox.showerror('Foldover', str(error), parent=self.main)
            return False
        self.main.destroy()
        return True

    def _create_pb(self):
        try:
            name, frame, metadata = self._source_data()
            folded_frame, folded_metadata, _ = create_pb_foldover(
                frame, metadata, None if self.folded.get() == '全部' else self.folded.get())
            self.app.addSheet(f'{name} Foldover', folded_frame, {'doe': folded_metadata})
        except (ValueError, TypeError, OverflowError, KeyError) as error:
            messagebox.showerror('Foldover', str(error), parent=self.main)
            return False
        self.main.destroy()
        return True

    def cancel(self):
        self.main.destroy()
