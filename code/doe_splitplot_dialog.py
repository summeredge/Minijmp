"""两水平因子 Split-Plot 创建界面。"""
import tkinter as tk
from tkinter import messagebox, ttk

from doe_core import DesignSpec, FactorSpec
from doe_dialog import ccd_number
from doe_splitplot import create_split_plot
from help_link import open_help


_PREVIEW_ROWS = 100


class CreateSplitPlot:
    def __init__(self, app):
        self.app = app
        self.main = tk.Toplevel(app.main)
        self.main.title('创建两水平 Split-Plot 裂区设计')
        self.main.bind('<F1>', lambda event: open_help('doe.split_plot', parent=self.main))
        body = ttk.Frame(self.main, padding=10)
        body.pack(fill='both', expand=True)
        for column, label in enumerate(('因子', '名称', '低水平', '高水平')):
            ttk.Label(body, text=label).grid(row=0, column=column, padx=3)
        self.fields = []
        for index, factor_id in enumerate(('A', 'B'), 1):
            ttk.Label(body, text=factor_id).grid(row=index, column=0)
            entries = []
            for column, value in enumerate((factor_id, '0', '1'), 1):
                entry = ttk.Entry(body, width=16)
                entry.insert(0, value)
                entry.grid(row=index, column=column, padx=3, pady=3)
                entries.append(entry)
            self.fields.append(entries)

        row = 3
        ttk.Label(body, text='Hard-to-change 因子').grid(row=row, column=0, sticky='w')
        self.hard_factor = ttk.Combobox(body, values=('A', 'B'), state='readonly', width=8)
        self.hard_factor.set('A')
        self.hard_factor.grid(row=row, column=1, sticky='w')
        row += 1
        self.blocks = self._entry(body, row, '区组数', '3')
        self.seed = self._entry(body, row + 1, '随机 seed', '1')
        self.responses = self._entry(body, row + 2, '响应名称', 'Y')
        preview_row = row + 3
        ttk.Label(body, text='运行预览').grid(row=preview_row, column=0, sticky='nw')
        preview_frame = ttk.Frame(body)
        preview_frame.grid(row=preview_row, column=1, columnspan=3, sticky='nsew')
        self.preview_text = tk.Text(preview_frame, width=72, height=9, wrap='none',
                                    state='disabled')
        scrollbar = ttk.Scrollbar(preview_frame, orient='vertical',
                                  command=self.preview_text.yview)
        horizontal = ttk.Scrollbar(preview_frame, orient='horizontal',
                                   command=self.preview_text.xview)
        self.preview_text.configure(yscrollcommand=scrollbar.set,
                                    xscrollcommand=horizontal.set)
        horizontal.pack(side='bottom', fill='x')
        self.preview_text.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        self.preview_horizontal = horizontal
        buttons = ttk.Frame(body)
        buttons.grid(row=preview_row + 1, column=1, columnspan=3, sticky='e', pady=(8, 0))
        self.preview_button = ttk.Button(buttons, text='预览', command=self.preview)
        self.preview_button.pack(side='left')
        self.create_button = ttk.Button(buttons, text='创建', command=self.create)
        self.create_button.pack(side='left', padx=4)
        self.cancel_button = ttk.Button(buttons, text='取消', command=self.main.destroy)
        self.cancel_button.pack(side='left')
        body.columnconfigure(3, weight=1)
        body.rowconfigure(preview_row, weight=1)
        self.preview()

    @staticmethod
    def _entry(parent, row, label, default):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky='w', pady=2)
        entry = ttk.Entry(parent, width=18)
        entry.insert(0, default)
        entry.grid(row=row, column=1, sticky='w', pady=2)
        return entry

    def build(self):
        factors = []
        hard_id = self.hard_factor.get()
        for factor_id, entries in zip(('A', 'B'), self.fields):
            name = entries[0].get().strip()
            if not name:
                raise ValueError('因子名称不能为空')
            factors.append(FactorSpec(
                factor_id, name, ccd_number(entries[1].get()),
                ccd_number(entries[2].get()),
                randomization_role='hard_to_change' if factor_id == hard_id
                else 'easy_to_change'))
        responses = tuple(value.strip() for value in self.responses.get().split(','))
        spec = DesignSpec(
            'DOE', tuple(factors), responses, seed=int(self.seed.get()),
            design_type='split_plot', block_count=int(self.blocks.get()),
            randomization_unit='whole_plot', error_structure='split_plot')
        return create_split_plot(spec)

    def _show(self, text):
        self.preview_text.configure(state='normal')
        self.preview_text.delete('1.0', 'end')
        self.preview_text.insert('1.0', text)
        self.preview_text.configure(state='disabled')

    def preview(self):
        try:
            frame, metadata = self.build()
        except (ValueError, TypeError, OverflowError) as error:
            self._show('')
            messagebox.showerror('Split-Plot', str(error), parent=self.main)
            return False
        columns = metadata['column_map']
        views = [columns['run_id'], columns['standard_order'], columns['run_order'],
                 columns['block'], columns['whole_plot_id'],
                 columns['factors']['A'], columns['factors']['B'],
                 columns['whole_plot_order'], columns['subplot_order']]
        total = len(frame)
        lines = [f"运行 {total} 次；区组 {frame[columns['block']].nunique()}；"
                 f"整区 {frame[columns['whole_plot_id']].nunique()}",
                 '\t'.join(views)]
        shown = frame[views].head(_PREVIEW_ROWS)
        lines.extend('\t'.join(map(str, row))
                     for row in shown.itertuples(index=False, name=None))
        if total > _PREVIEW_ROWS:
            lines.append(f"仅显示前 {_PREVIEW_ROWS} 行，共 {total} 行")
        self._show('\n'.join(lines))
        return True

    def create(self):
        try:
            frame, metadata = self.build()
            self.app.addSheet('DOE Split-Plot', frame, {'doe': metadata})
        except (ValueError, TypeError, OverflowError) as error:
            messagebox.showerror('Split-Plot', str(error), parent=self.main)
            return False
        self.main.destroy()
        return True
