"""Unstack, random sampling/generation, and probability distribution tools."""
import tkinter as tk
from tkinter import messagebox, ttk

import numpy as np
import pandas as pd
from scipy import stats

from df_combine import _extend
from pandastable_local.dialogs import apply_dialog_theme
from worksheet_formulas import column_labels


DISTRIBUTIONS = {
    '正态': ('normal', stats.norm, ('均值', '标准差'), ('0', '1')),
    '均匀': ('uniform', None, ('下限', '上限'), ('0', '1')),
    '二项': ('binomial', stats.binom, ('试验次数', '成功概率'), ('10', '0.5')),
    '泊松': ('poisson', stats.poisson, ('平均发生次数',), ('1',)),
}
OPERATIONS = {
    '概率密度 / 质量（PDF / PMF）': 'density',
    '累积概率（CDF）': 'cdf',
    '逆累积概率（逆 CDF）': 'ppf',
}


def unstack_columns(values, groups):
    if len(values) != len(groups) or not len(values):
        raise ValueError('数据列和分组列必须具有相同的非零行数。')
    codes, labels = pd.factorize(groups, sort=False, use_na_sentinel=False)
    positions = pd.Series(codes).groupby(codes, sort=False).indices
    height = max(map(len, positions.values()))
    columns = {}
    for code, rows in positions.items():
        label = labels[code]
        base = '（缺失）' if pd.isna(label) else str(label) or '（空文本）'
        name = base
        suffix = 2
        while name in columns:
            name = f'{base} ({suffix})'
            suffix += 1
        columns[name] = _extend(values.iloc[rows], height)
    return pd.DataFrame(columns)


def sample_rows(data, count, seed=None, replace=False):
    if count < 1 or data.empty:
        raise ValueError('样本量必须为正整数，且源列须有数据行。')
    if not replace and count > len(data):
        raise ValueError('无放回抽样的样本量不能大于可用行数。')
    rows = np.random.default_rng(seed).choice(len(data), size=count, replace=replace)
    return data.iloc[rows].reset_index(drop=True)


def distribution_parameters(distribution, fields):
    label = next(name for name, spec in DISTRIBUTIONS.items() if spec[0] == distribution)
    spec = DISTRIBUTIONS[label]
    pars = tuple((int if distribution == 'binomial' and index == 0 else float)(value)
                 for index, value in enumerate(fields[:len(spec[2])]))
    if not all(np.isfinite(pars)):
        raise ValueError('分布参数必须为有限值。')
    if distribution == 'normal' and pars[1] <= 0:
        raise ValueError('标准差必须大于 0。')
    if distribution == 'uniform' and pars[1] <= pars[0]:
        raise ValueError('上限必须大于下限。')
    if distribution == 'binomial' and (pars[0] < 0 or not 0 <= pars[1] <= 1):
        raise ValueError('试验次数须为非负整数，成功概率须在 0 至 1 之间。')
    if distribution == 'poisson' and pars[0] < 0:
        raise ValueError('平均发生次数必须非负。')
    return pars


def random_values(distribution, parameters, count, seed=None):
    if count < 1:
        raise ValueError('样本量必须为正整数。')
    rng = np.random.default_rng(seed)
    return getattr(rng, distribution)(*parameters, size=count)


def distribution_values(distribution, parameters, operation, values):
    rv = next(spec[1] for spec in DISTRIBUTIONS.values() if spec[0] == distribution)
    values = np.asarray(values, dtype=float)
    if operation == 'ppf' and np.any((values < 0) | (values > 1)):
        raise ValueError('逆累积概率输入必须在 0 至 1 之间。')
    method = ('pdf' if distribution == 'normal' else 'pmf') if operation == 'density' else operation
    return getattr(rv, method)(values, *parameters)


class WorksheetCalculationDialog:
    def __init__(self, app, mode):
        self.app = app
        self.table = app.getCurrentTable()
        self.df = self.table.model.df
        self.mode = mode
        self.main = tk.Toplevel(app.main)
        self.main.transient(app.main)
        self.main.title(mode)
        self.main.resizable(False, False)
        apply_dialog_theme(self.main, app.main)
        self.body = ttk.Frame(self.main, padding=10)
        self.body.pack(fill='both', expand=True)
        self.body.columnconfigure(1, weight=1)
        self.fields = {}
        self.columns = column_labels(self.df)
        self.row = 0

        if mode == '逆堆叠列':
            self.field('data', '数据列', '', self.columns)
            self.field('group', '分组列', '', self.columns)
        elif mode == '从列随机抽样':
            ttk.Label(self.body, text='抽样列').grid(row=self.row, column=0, sticky='nw')
            self.selection = tk.Listbox(self.body, height=6, selectmode='extended',
                                        exportselection=False)
            self.selection.insert('end', *self.columns)
            self.selection.grid(row=self.row, column=1, sticky='ew')
            self.row += 1
            self.field('replace', '抽样方式', '无放回', ('无放回', '有放回'))
        else:
            choices = [name for name, spec in DISTRIBUTIONS.items() if mode == '生成随机数据' or spec[1] is not None]
            distribution = self.field('distribution', '分布', choices[0], choices)
            distribution.bind('<<ComboboxSelected>>', self.set_parameters)
            self.parameters = [self.field(f'p{i}', '', '') for i in range(2)]
            self.set_parameters()
        if mode in ('生成随机数据', '从列随机抽样'):
            self.field('count', '样本量', '10')
            self.field('seed', '随机种子（可选）', '')
        if mode == '概率分布':
            self.field('operation', '计算', next(iter(OPERATIONS)), tuple(OPERATIONS))
            self.field('input', '输入', '常数', ['常数', *self.columns])
            self.field('constant', '常数值', '0')
            self.field('output', '输出位置', '新工作表', ('新工作表', '当前工作表新列'))
            self.field('name', '结果列名', '概率分布结果')
        buttons = ttk.Frame(self.body)
        buttons.grid(row=self.row, column=0, columnspan=2, sticky='e', pady=(8, 0))
        ttk.Button(buttons, text='确定', command=self.apply).pack(side='left', padx=(0, 4))
        ttk.Button(buttons, text='取消', command=self.main.destroy).pack(side='left')
        self.main.bind('<Escape>', lambda event: self.main.destroy())
        self.main.grab_set()

    def field(self, key, label, value, choices=None):
        caption = ttk.Label(self.body, text=label)
        caption.grid(row=self.row, column=0, sticky='w', padx=(0, 8), pady=2)
        var = self.fields[key] = tk.StringVar(self.main, value)
        widget = (ttk.Entry(self.body, textvariable=var, width=27) if choices is None else
                  ttk.Combobox(self.body, textvariable=var, values=choices, state='readonly', width=25))
        widget.grid(row=self.row, column=1, sticky='ew', pady=2)
        widget.caption = caption
        self.row += 1
        return widget

    def set_parameters(self, event=None):
        spec = DISTRIBUTIONS[self.fields['distribution'].get()]
        for i, widget in enumerate(self.parameters):
            if i < len(spec[2]):
                widget.caption.configure(text=spec[2][i])
                self.fields[f'p{i}'].set(spec[3][i])
                widget.caption.grid()
                widget.grid()
            else:
                widget.caption.grid_remove()
                widget.grid_remove()

    def result(self, fields):
        if self.mode == '逆堆叠列':
            if not fields['data'] or not fields['group'] or fields['data'] == fields['group']:
                raise ValueError('请选择不同的数据列和分组列。')
            return unstack_columns(*(self.df.iloc[:, self.columns.index(fields[key])] for key in ('data', 'group')))
        if self.mode != '从列随机抽样':
            distribution = DISTRIBUTIONS[fields['distribution']][0]
            pars = distribution_parameters(distribution, [fields['p0'], fields['p1']])
        if self.mode == '概率分布':
            name = fields['name'].strip()
            if not name:
                raise ValueError('请输入结果列名。')
            constant = fields['input'] == '常数'
            if constant:
                values = [float(fields['constant'])]
            else:
                col = self.df.iloc[:, self.columns.index(fields['input'])]
                if (pd.api.types.is_datetime64_any_dtype(col.dtype) or
                        pd.api.types.is_timedelta64_dtype(col.dtype) or
                        pd.api.types.is_complex_dtype(col.dtype)):
                    raise ValueError('请输入实数列。')
                values = pd.to_numeric(col, errors='raise').to_numpy(dtype=float, na_value=np.nan)
            output = distribution_values(distribution, pars, OPERATIONS[fields['operation']], values)
            if fields['output'] == '新工作表':
                return pd.DataFrame({name: output})
            self.table.add_calculation_column(name, output, broadcast=constant)
            return None
        count = int(fields['count'])
        seed = int(fields['seed']) if fields['seed'] else None
        if seed is not None and seed < 0:
            raise ValueError('随机种子须为非负整数。')
        if self.mode == '生成随机数据':
            return pd.DataFrame({fields['distribution']: random_values(distribution, pars, count, seed)})
        selection = list(self.selection.curselection())
        if not selection:
            raise ValueError('请至少选择一列。')
        return sample_rows(self.df.iloc[:, selection], count, seed, fields['replace'] == '有放回')

    def apply(self):
        try:
            if self.app.getCurrentTable() is not self.table or self.table.model.df is not self.df:
                raise ValueError('来源工作表已变化，请重新打开工具。')
            frame = self.result({key: value.get() for key, value in self.fields.items()})
            if frame is not None:
                self.app.addSheet(self.mode, frame, finish_edits=False)
        except (ValueError, TypeError, OverflowError, MemoryError) as exc:
            messagebox.showerror(self.mode, f'无法计算，请检查输入。\n{exc}', parent=self.main)
            return
        self.main.destroy()
