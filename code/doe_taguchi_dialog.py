"""Taguchi 设计创建界面：数组、因子角色、列分配与运行预览。"""
import tkinter as tk
from tkinter import messagebox, ttk

from doe_core import DesignSpec, FactorSpec
from doe_dialog import ccd_number
from doe_taguchi import create_taguchi
from doe_taguchi_arrays import ARRAYS, ARRAY_IDS, validate_independent_columns
from help_link import open_help


_PREVIEW_ROWS = 100
_MAX_FACTORS = max(array.factor_capacity for array in ARRAYS.values())
_ROLES = ('控制', '噪声', '信号')


class CreateTaguchi:
    def __init__(self, app, dynamic=False):
        self.app = app
        self.main = tk.Toplevel(app.main)
        self.main.title('创建 Taguchi 设计')
        self.main.geometry('980x720')
        self.main.bind('<F1>', lambda event: open_help('doe.taguchi', parent=self.main))
        top = ttk.Frame(self.main, padding=8)
        top.pack(fill='x')
        self.kind = tk.StringVar(value='dynamic' if dynamic else 'static')
        ttk.Radiobutton(top, text='静态', value='static', variable=self.kind,
                        command=self.update_rows).pack(side='left')
        ttk.Radiobutton(top, text='动态（含信号因子）', value='dynamic',
                        variable=self.kind, command=self.update_rows).pack(side='left', padx=6)
        ttk.Label(top, text='正交表').pack(side='left', padx=(12, 2))
        self.array = ttk.Combobox(top, values=ARRAY_IDS, state='readonly', width=16)
        self.array.set('L9(3^4)')
        self.array.pack(side='left')
        self.array.bind('<<ComboboxSelected>>', self.update_rows)
        ttk.Label(top, text='噪声表').pack(side='left', padx=(12, 2))
        self.noise_array = ttk.Combobox(top, values=('（无）',) + ARRAY_IDS,
                                        state='readonly', width=16)
        self.noise_array.set('（无）')
        self.noise_array.pack(side='left')
        ttk.Label(top, text='因子数').pack(side='left', padx=(12, 2))
        self.factor_count = ttk.Combobox(top, values=tuple(range(2, _MAX_FACTORS + 1)),
                                         state='readonly', width=4)
        self.factor_count.set('3')
        self.factor_count.pack(side='left')
        self.factor_count.bind('<<ComboboxSelected>>', self.update_rows)

        grid = ttk.Frame(self.main, padding=(8, 0))
        grid.pack(fill='x')
        for column, title in enumerate(('因子', '名称', '标签类型', '水平（; 分隔）',
                                        '列', '角色')):
            ttk.Label(grid, text=title).grid(row=0, column=column, padx=4, sticky='w')
        self.rows = []
        for index in range(_MAX_FACTORS):
            factor_id = chr(65 + index)
            ttk.Label(grid, text=factor_id).grid(row=index + 1, column=0, sticky='w')
            name = ttk.Entry(grid, width=16)
            name.insert(0, factor_id)
            name.grid(row=index + 1, column=1, padx=4, pady=2, sticky='ew')
            label_type = ttk.Combobox(grid, values=('文字', '数值'), state='readonly',
                                      width=7)
            label_type.set('文字')
            label_type.grid(row=index + 1, column=2, padx=4, pady=2)
            levels = ttk.Entry(grid, width=34)
            levels.insert(0, '低;中;高')
            levels.grid(row=index + 1, column=3, padx=4, pady=2, sticky='ew')
            column = ttk.Combobox(grid, values=(), state='readonly', width=5)
            column.grid(row=index + 1, column=4, padx=4, pady=2)
            role = ttk.Combobox(grid, values=_ROLES, state='readonly', width=7)
            role.set('控制')
            role.grid(row=index + 1, column=5, padx=4, pady=2)
            self.rows.append((name, label_type, levels, column, role))
        grid.columnconfigure(3, weight=1)

        settings = ttk.Frame(self.main, padding=(8, 6))
        settings.pack(fill='x')
        self.replicates = self._entry(settings, '重复数', '1')
        self.seed = self._entry(settings, '随机 seed', '1')
        ttk.Label(settings, text='响应名称').pack(side='left', padx=(12, 2))
        self.responses = ttk.Entry(settings, width=22)
        self.responses.insert(0, 'Y')
        self.responses.pack(side='left')

        body = ttk.Frame(self.main, padding=(8, 0))
        body.pack(fill='both', expand=True)
        self.preview_text = tk.Text(body, height=12, wrap='none', state='disabled')
        scrollbar = ttk.Scrollbar(body, orient='vertical', command=self.preview_text.yview)
        horizontal = ttk.Scrollbar(body, orient='horizontal',
                                   command=self.preview_text.xview)
        self.preview_text.configure(yscrollcommand=scrollbar.set,
                                    xscrollcommand=horizontal.set)
        horizontal.pack(side='bottom', fill='x')
        scrollbar.pack(side='right', fill='y')
        self.preview_text.pack(side='left', fill='both', expand=True)
        bar = ttk.Frame(self.main, padding=8)
        bar.pack(fill='x')
        ttk.Button(bar, text='预览', command=self.preview).pack(side='left')
        ttk.Button(bar, text='创建', command=self.create).pack(side='left', padx=4)
        self.cancel_button = ttk.Button(bar, text='取消', command=self.main.destroy)
        self.cancel_button.pack(side='left')
        self.update_rows()

    @staticmethod
    def _entry(parent, label, default):
        ttk.Label(parent, text=label).pack(side='left', padx=(12, 2))
        entry = ttk.Entry(parent, width=8)
        entry.insert(0, default)
        entry.pack(side='left')
        return entry

    def update_rows(self, event=None):
        array = ARRAYS[self.array.get()]
        dynamic = self.kind.get() == 'dynamic'
        capacity = min(_MAX_FACTORS, int(self.factor_count.get()))
        columns = [str(value) for value in range(1, array.factor_capacity + 1)]
        used = set()
        for index, (_, _, _, column, role) in enumerate(self.rows):
            visible = index < capacity
            for widget in self.rows[index]:
                if visible:
                    widget.grid()
                else:
                    widget.grid_remove()
            if not visible:
                continue
            column.configure(values=columns)
            if index >= capacity - (1 if dynamic else 0):
                role.set('信号' if dynamic else '控制')
                column.set('')
                continue
            if column.get() not in columns or column.get() in used:
                free = next((value for value in columns if value not in used), '')
                column.set(free)
            used.add(column.get())

    def _parse_levels(self, entry, label_type):
        raw = [value.strip() for value in entry.get().split(';')]
        if len(raw) < 2 or any(not value for value in raw):
            raise ValueError('每个因子至少需要两个非空水平')
        return (tuple(raw) if label_type == '文字'
                else tuple(ccd_number(value) for value in raw))

    def build(self):
        array = ARRAYS[self.array.get()]
        noise_id = None if self.noise_array.get() == '（无）' else self.noise_array.get()
        noise = ARRAYS[noise_id] if noise_id else None
        dynamic = self.kind.get() == 'dynamic'
        count = int(self.factor_count.get())
        if not 2 <= count <= array.factor_capacity:
            raise ValueError(f'{array.array_id} 最多支持 {array.factor_capacity} 个因子')
        factors, columns, noise_columns, signal = [], {}, {}, None
        for index, (name, label_type, levels, column, role) in enumerate(self.rows[:count]):
            factor_id = chr(65 + index)
            values = self._parse_levels(levels, label_type.get())
            factors.append(FactorSpec(
                factor_id, name.get().strip() or factor_id, None, None,
                factor_type='categorical', levels=values,
                level_type='text' if label_type.get() == '文字' else 'numeric'))
            choice = role.get()
            if choice == '信号':
                if not dynamic:
                    raise ValueError('只有动态设计才能分配信号因子')
                if signal is not None:
                    raise ValueError('动态设计只能有一个信号因子')
                if label_type.get() != '数值' or list(values) != sorted(values):
                    raise ValueError('信号因子必须是升序数值水平')
                signal = factor_id
            elif choice == '噪声':
                if noise is None:
                    raise ValueError('分配噪声因子前请选择噪声正交表')
                noise_columns[factor_id] = int(column.get())
            elif choice == '控制':
                columns[factor_id] = int(column.get())
            else:
                raise ValueError('未知因子角色')
        if dynamic and signal is None:
            raise ValueError('动态设计必须有一个信号因子')
        validate_independent_columns(array, columns, '控制')
        if noise is not None:
            validate_independent_columns(noise, noise_columns, '噪声')
        spec = DesignSpec(
            'Taguchi', tuple(factors),
            tuple(value.strip() for value in self.responses.get().split(',')),
            seed=int(self.seed.get()), design_type='taguchi',
            taguchi={
                'kind': self.kind.get(), 'array_id': array.array_id,
                'matrix_sha256': array.sha256, 'columns': columns,
                'noise_array_id': noise_id,
                'noise_matrix_sha256': None if noise is None else noise.sha256,
                'noise_columns': noise_columns, 'signal_factor': signal})
        return create_taguchi(spec, replicates=int(self.replicates.get()))

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
            messagebox.showerror('Taguchi', str(error), parent=self.main)
            return False
        columns = metadata['column_map']
        views = [columns['run_id'], columns['standard_order'], columns['run_order'],
                 columns['replicate'], columns['control_run_id'],
                 columns['noise_condition_id'], *columns['factors'].values()]
        total = len(frame)
        lines = [f"运行 {total} 次；{metadata['design']['taguchi']['array_id']}；"
                 f"控制运行 {frame[columns['control_run_id']].nunique()}",
                 '\t'.join(views)]
        lines.extend('\t'.join(map(str, row)) for row in
                     frame[views].head(_PREVIEW_ROWS).itertuples(index=False, name=None))
        if total > _PREVIEW_ROWS:
            lines.append(f"仅显示前 {_PREVIEW_ROWS} 行，共 {total} 行")
        self._show('\n'.join(lines))
        return True

    def create(self):
        try:
            frame, metadata = self.build()
            self.app.addSheet('Taguchi', frame, {'doe': metadata})
        except (ValueError, TypeError, OverflowError) as error:
            messagebox.showerror('Taguchi', str(error), parent=self.main)
            return False
        self.main.destroy()
        return True

