"""两水平全因子的创建、分析和结果展示。"""
import tkinter as tk
from tkinter import messagebox, ttk

import numpy as np
import pandas as pd
from matplotlib import font_manager

from doe_analysis import analyze_factorial
from doe_core import DesignSpec, FactorSpec
from doe_factorial import create_factorial
from sheet_context import SheetApp
from stat_table import StatTable, TableBlock
from help_link import open_help


def number(text):
    text = text.strip()
    try:
        return int(text)
    except ValueError:
        return float(text)


def ccd_number(text):
    from decimal import Decimal, InvalidOperation
    import math
    raw = text.strip()
    try:
        decimal_value = Decimal(raw)
        value = number(raw)
    except (InvalidOperation, OverflowError, ValueError) as exc:
        raise ValueError('因子水平必须是有限数值') from exc
    if not decimal_value.is_finite() or (isinstance(value, float) and not math.isfinite(value)):
        raise ValueError('因子水平必须是有限数值')
    if decimal_value != 0 and value == 0:
        raise ValueError('因子水平过小，不能安全表示为浮点数')
    return value


class CreateDOE:
    def __init__(self, app, fractional=False, ccd=False, bbd=False, pb=False, dsd=False):
        self.app = app
        self.fractional = fractional
        self.ccd = ccd
        self.bbd = bbd
        self.pb = pb
        self.dsd = dsd
        self.main = tk.Toplevel(app.main)
        self.main.title('创建 Definitive Screening 设计' if dsd else '创建 Plackett–Burman 设计' if pb else '创建 Box-Behnken 设计' if bbd else
                        '创建中心复合设计' if ccd else
                        '创建两水平部分因子设计' if fractional else '创建两水平全因子设计')
        help_topic = ('doe.dsd' if dsd else 'doe.pb' if pb else 'doe.bbd' if bbd else 'doe.ccd' if ccd
                      else 'doe.fractional' if fractional else 'doe.full_factorial')
        self.main.bind('<F1>', lambda event: open_help(help_topic, parent=self.main))
        self.fields = []
        self.factor_labels = []
        if ccd or bbd or pb or dsd:
            area = ttk.Frame(self.main)
            area.pack(fill='both', expand=True)
            canvas = tk.Canvas(area, highlightthickness=0, height=500)
            scrollbar = ttk.Scrollbar(area, orient='vertical', command=canvas.yview)
            canvas.configure(yscrollcommand=scrollbar.set)
            scrollbar.pack(side='right', fill='y')
            canvas.pack(side='left', fill='both', expand=True)
            grid = ttk.Frame(canvas, padding=8)
            canvas.create_window((0, 0), window=grid, anchor='nw')
            grid.bind('<Configure>', lambda event: canvas.configure(scrollregion=canvas.bbox('all')))
        else:
            grid = ttk.Frame(self.main, padding=8)
            grid.pack(fill='both', expand=True)
        categorical_column = ccd or bbd or pb or dsd
        headers = ('因子', '名称', '低水平', '高水平', '单位')
        if categorical_column:
            headers += ('分类水平',)
        for col, label in enumerate(headers):
            ttk.Label(grid, text=label).grid(row=0, column=col, padx=3)
        factor_limit = 47 if pb else 48 if dsd else 10 if bbd or ccd else 6
        for i in range(factor_limit):
            label = ttk.Label(grid, text=f'F{i+1}' if pb or dsd else chr(65+i))
            label.grid(row=i+1, column=0)
            self.factor_labels.append(label)
            entries = []
            for col in range(1, 5):
                entry = ttk.Entry(grid, width=15)
                entry.grid(row=i+1, column=col, padx=3, pady=2)
                entries.append(entry)
            if categorical_column:
                levels = ttk.Entry(grid, width=18)
                levels.grid(row=i+1, column=5, padx=3, pady=2)
                entries.append(levels)
            if i < (47 if pb else 48 if dsd else 6 if fractional else 10 if ccd or bbd else 2):
                entries[0].insert(0, f'F{i+1}' if pb or dsd else chr(65+i))
                entries[1].insert(0, '0')
                entries[2].insert(0, '1')
            self.fields.append(entries)
        options_start = factor_limit + 1
        if dsd:
            ttk.Label(grid, text='因子数').grid(row=options_start, column=0, sticky='w')
            self.factor_count = ttk.Combobox(grid, values=tuple(range(2, 49)), state='readonly', width=5)
            self.factor_count.set('6')
            self.factor_count.grid(row=options_start, column=1, sticky='w')
            self.factor_count.bind('<<ComboboxSelected>>', self.update_factor_rows)
            self.update_factor_rows()
            options_start += 1
            ttk.Label(grid, text='区组数').grid(row=options_start, column=0, sticky='w')
            self.dsd_blocks = ttk.Entry(grid, width=5)
            self.dsd_blocks.insert(0, '1')
            self.dsd_blocks.grid(row=options_start, column=1, sticky='w')
            options_start += 1
        if pb:
            ttk.Label(grid, text='因子数').grid(row=options_start, column=0, sticky='w')
            self.factor_count = ttk.Combobox(grid, values=list(range(2, 48)), state='readonly', width=5)
            self.factor_count.set('3')
            self.factor_count.grid(row=options_start, column=1, sticky='w')
            self.factor_count.bind('<<ComboboxSelected>>', self.update_factor_rows)
            self.update_factor_rows()
            options_start += 1
            ttk.Label(grid, text='基础运行数').grid(row=options_start, column=0, sticky='w')
            self.pb_runs = ttk.Combobox(grid, values=(12, 20, 24, 28, 32, 36, 40, 44, 48), state='readonly', width=5)
            self.pb_runs.set('12')
            self.pb_runs.grid(row=options_start, column=1, sticky='w')
            options_start += 1
            self.pb_block_replicates = tk.BooleanVar(value=False)
            ttk.Checkbutton(grid, text='按重复分区组', variable=self.pb_block_replicates).grid(
                row=options_start, column=0, columnspan=2, sticky='w')
            options_start += 1
        if fractional:
            ttk.Label(grid, text='预置方案').grid(row=options_start, column=0, sticky='w')
            self.preset = ttk.Combobox(grid, values=(
                '自定义', '3因子（C=AB）', '4因子（D=ABC）',
                '5因子（E=ABCD）', '5因子（D=AB;E=AC）'),
                state='readonly', width=25)
            self.preset.set('自定义')
            self.preset.grid(row=options_start, column=1, columnspan=2, sticky='w', pady=2)
            self.preset.bind('<<ComboboxSelected>>', self.apply_fractional_preset)
            options_start += 1
            ttk.Label(grid, text='因子数').grid(row=options_start, column=0, sticky='w')
            self.factor_count = ttk.Combobox(
                grid, values=list(range(3, 7)), state='readonly', width=5)
            self.factor_count.set('4')
            self.factor_count.grid(row=options_start, column=1, sticky='w', pady=2)
            self.factor_count.bind('<<ComboboxSelected>>', self.update_factor_rows)
            self.update_factor_rows()
            options_start += 1
        if ccd:
            ttk.Label(grid, text='因子数').grid(row=options_start, column=0, sticky='w')
            self.factor_count = ttk.Combobox(grid, values=list(range(2, 11)), state='readonly', width=5)
            self.factor_count.set('2')
            self.factor_count.grid(row=options_start, column=1, sticky='w')
            self.factor_count.bind('<<ComboboxSelected>>', self.update_factor_rows)
            self.update_factor_rows()
            options_start += 1
            ttk.Label(grid, text='CCD 类型').grid(row=options_start, column=0, sticky='w')
            self.ccd_type = ttk.Combobox(grid, values=('CCF', 'CCC'), state='readonly', width=8)
            self.ccd_type.set('CCF')
            self.ccd_type.grid(row=options_start, column=1, sticky='w')
            options_start += 1
            ttk.Label(grid, text='设计分数').grid(row=options_start, column=0, sticky='w')
            self.ccd_fraction = ttk.Combobox(
                grid, values=('全因子', '1/2 分数', '1/4 分数', '1/8 分数'),
                state='readonly', width=10)
            self.ccd_fraction.set('全因子')
            self.ccd_fraction.grid(row=options_start, column=1, sticky='w')
            options_start += 1
            ttk.Label(grid, text='区组数').grid(row=options_start, column=0, sticky='w')
            self.ccd_blocks = ttk.Combobox(
                grid, values=('无区组', '2', '3', '5'), state='readonly', width=8)
            self.ccd_blocks.set('无区组')
            self.ccd_blocks.grid(row=options_start, column=1, sticky='w')
            options_start += 1
            self.measured = tk.BooleanVar(value=False)
            ttk.Checkbutton(grid, text='添加实测水平列', variable=self.measured).grid(
                row=options_start, column=0, columnspan=2, sticky='w')
            options_start += 1
        if bbd:
            ttk.Label(grid, text='因子数').grid(row=options_start, column=0, sticky='w')
            self.factor_count = ttk.Combobox(grid, values=(3, 4, 5, 6, 7, 9, 10),
                                             state='readonly', width=5)
            self.factor_count.set('3')
            self.factor_count.grid(row=options_start, column=1, sticky='w')
            self.factor_count.bind('<<ComboboxSelected>>', self.update_factor_rows)
            self.update_factor_rows()
            options_start += 1
            ttk.Label(grid, text='区组数').grid(row=options_start, column=0, sticky='w')
            self.block_count = ttk.Combobox(grid, values=('自动', '1'),
                                            state='readonly', width=8)
            self.block_count.set('自动')
            self.block_count.grid(row=options_start, column=1, sticky='w')
            for entries in self.fields:
                entries[4].bind('<KeyRelease>', self.update_factor_rows)
            options_start += 1
            self.measured = tk.BooleanVar(value=False)
            ttk.Checkbutton(grid, text='添加实测水平列', variable=self.measured).grid(
                row=options_start, column=0, columnspan=2, sticky='w')
            options_start += 1
        self.options = {}
        for row, (key, default) in enumerate((('重复数', '1'),
                                               ('中心点数', '默认' if bbd or ccd else '0'),
                                               ('随机 seed', '1'), ('响应名称', 'Y')),
                                             options_start):
            ttk.Label(grid, text='每重复中心点数' if pb and key == '中心点数' else key).grid(row=row, column=0, sticky='w')
            entry = ttk.Entry(grid, width=25)
            entry.insert(0, default)
            entry.grid(row=row, column=1, columnspan=2, sticky='ew', pady=2)
            self.options[key] = entry
        preview_row = options_start + len(self.options)
        if not (ccd or bbd or pb or dsd):
            self.block_replicates = tk.BooleanVar(value=False)
            ttk.Checkbutton(grid, text='每个完整重复作为一个区组',
                            variable=self.block_replicates).grid(
                                row=preview_row, column=0, columnspan=3, sticky='w')
            preview_row += 1
        if fractional:
            ttk.Label(grid, text='生成元（D=AB;E=AC）').grid(
                row=preview_row, column=0, sticky='w')
            self.generators = ttk.Entry(grid, width=25)
            self.generators.grid(row=preview_row, column=1, columnspan=4, sticky='ew', pady=2)
            self.generators.bind('<KeyRelease>',
                                 lambda event: self.preset.set('自定义'))
            preview_row += 1
        self.preview_text = tk.StringVar(value='')
        ttk.Label(grid, textvariable=self.preview_text, wraplength=720).grid(
            row=preview_row, column=0, columnspan=5, sticky='ew')
        bar = ttk.Frame(self.main if ccd or bbd or pb or dsd else grid)
        if ccd or bbd or pb or dsd:
            bar.pack(side='bottom', anchor='e', padx=8, pady=8, before=area)
        else:
            bar.grid(row=preview_row + 1, column=0, columnspan=5, sticky='e')
        ttk.Button(bar, text='预览', command=self.preview).pack(side='left')
        ttk.Button(bar, text='创建', command=self.create).pack(side='left', padx=4)
        ttk.Button(bar, text='取消', command=self.main.destroy).pack(side='left')

    def update_factor_rows(self, event=None):
        if event is not None and self.fractional:
            self.preset.set('自定义')
        count = int(self.factor_count.get())
        if self.bbd and hasattr(self, 'block_count'):
            from doe_bbd import _BLOCK_OPTIONS
            continuous_count = sum(not entries[4].get().strip()
                                   for entries in self.fields[:count])
            choices = ('自动',) + tuple(map(str, _BLOCK_OPTIONS.get(continuous_count, ())))
            self.block_count.configure(values=choices)
            if self.block_count.get() not in choices:
                self.block_count.set('自动')
        for index, entries in enumerate(self.fields):
            if index < count:
                self.factor_labels[index].grid()
            else:
                self.factor_labels[index].grid_remove()
            for widget in entries:
                if index < count:
                    widget.grid()
                else:
                    widget.grid_remove()

    def apply_fractional_preset(self, event=None):
        preset = {
            '3因子（C=AB）': (3, 'C=AB'),
            '4因子（D=ABC）': (4, 'D=ABC'),
            '5因子（E=ABCD）': (5, 'E=ABCD'),
            '5因子（D=AB;E=AC）': (5, 'D=AB;E=AC'),
        }.get(self.preset.get())
        if preset is None:
            return
        count, generators = preset
        self.factor_count.set(str(count))
        self.update_factor_rows()
        self.generators.delete(0, 'end')
        self.generators.insert(0, generators)

    def build(self):
        factors = []
        field_count = (int(self.factor_count.get())
                       if self.fractional or self.ccd or self.bbd or self.pb or self.dsd else len(self.fields))
        for i, entries in enumerate(self.fields[:field_count]):
            name, low, high, unit = (entry.get().strip() for entry in entries[:4])
            if not any((name, low, high, unit)):
                continue
            parse = ccd_number if self.ccd or self.bbd or self.dsd else number
            level_text = (entries[4].get().strip()
                          if (self.ccd or self.bbd or self.pb or self.dsd) and len(entries) > 4 else '')
            if level_text:
                levels = tuple(item.strip() for item in level_text.split(';'))
                if any(not level for level in levels) or len(set(levels)) != len(levels):
                    raise ValueError(f'因子 {chr(65+i)} 的分类水平必须非空且不重复')
                factors.append(FactorSpec(
                    f'F{i+1}' if self.pb or self.dsd else chr(65+i), name, None, None, factor_type='categorical',
                    levels=levels))
                continue
            factors.append(FactorSpec(f'F{i+1}' if self.pb or self.dsd else chr(65+i), name,
                                      parse(low), parse(high), unit or None))
        responses = tuple(s.strip() for s in self.options['响应名称'].get().split(','))
        generator_text = self.generators.get() if self.fractional else ''
        generators = tuple(generator_text.split(';')) if generator_text else ()
        replicates = int(self.options['重复数'].get())
        center_text = self.options['中心点数'].get().strip()
        if self.dsd:
            from doe_dsd import create_dsd
            if int(center_text) != 0:
                raise ValueError('DSD 的中心点由构造确定，额外中心点数请设为 0。')
            mixed_two = [f.factor_type for f in factors] == ['continuous'] * 4 + ['categorical'] * 2
            mixed = (2 <= len(factors) <= 48 and [f.factor_type for f in factors] ==
                     ['continuous'] * (len(factors) - 1) + ['categorical'])
            if not mixed and not mixed_two and (len(factors) not in range(2, 49) or
                              any(f.factor_type != 'continuous' for f in factors)):
                raise ValueError('支持 2–48 连续因子、1–47 连续加 1 分类，或 4 连续加 2 分类。')
            key = 'dsd4c2' if mixed_two else f'dsd{len(factors)-1}c1' if mixed else f'dsd{len(factors)}'
            identity = {'construction_id': key + '.v1', 'source_kind': 'mathematical_construction',
                        'source_id': ('foldover.' if mixed_two else 'jones.' if mixed else 'conference.') + key, 'matrix_sha256': '0' * 64}
            spec = DesignSpec('DOE', tuple(factors), responses, seed=int(self.options['随机 seed'].get()),
                              design_type='definitive_screening', screening_matrix=identity)
            return create_dsd(spec, replicates, blocks=int(self.dsd_blocks.get()))
        if self.pb:
            from doe_pb import create_pb
            n = int(self.pb_runs.get())
            mathematical = n in (32, 40, 44, 48)
            identity = {'construction_id': f'pb{n}.v1',
                        'source_kind': 'mathematical_construction' if mathematical else 'publication',
                        'source_id': f'{"hadamard" if mathematical else "nist"}.pb{n}', 'matrix_sha256': '0' * 64}
            spec = DesignSpec('DOE', tuple(factors), responses,
                              seed=int(self.options['随机 seed'].get()),
                              design_type='plackett_burman', screening_matrix=identity)
            return create_pb(spec, n, replicates, center_points=int(center_text),
                             block_replicates=self.pb_block_replicates.get())
        if self.bbd:
            from doe_bbd import _DEFAULT_CENTERS, create_bbd
            k = len([f for f in factors if f.factor_type == 'continuous'])
            centers = _DEFAULT_CENTERS.get(k) if center_text in ('', '默认') else int(center_text)
            blocks = self.block_count.get()
            block_count = None if blocks == '自动' else int(blocks)
            spec = DesignSpec('DOE', tuple(factors), responses,
                              seed=int(self.options['随机 seed'].get()),
                              design_type='box_behnken', ccd_center_points=centers,
                              block_count=block_count)
            return create_bbd(spec, replicates, measured=self.measured.get())
        if self.ccd:
            from doe_ccd import create_ccd
            continuous = [f for f in factors if f.factor_type == 'continuous']
            k = len(continuous)
            fraction = {'全因子': 'full', '1/2 分数': 'half',
                        '1/4 分数': 'quarter', '1/8 分数': 'eighth'}[
                            self.ccd_fraction.get()]
            cubes = 2 ** (k - {'full': 0, 'half': 1,
                               'quarter': 2, 'eighth': 3}[fraction])
            if self.ccd_type.get() == 'CCF':
                if self.ccd_blocks.get() != '无区组':
                    raise ValueError(
                        '面心设计（alpha = 1）不能保证区组正交；'
                        '请选择 CCC 或取消区组。')
                alpha = 1
            elif self.ccd_blocks.get() == '无区组':
                alpha = cubes ** .25
            else:
                alpha = None  # 由区组布局推导正交 alpha
            blocks = (None if self.ccd_blocks.get() == '无区组'
                      else int(self.ccd_blocks.get()))
            centers = ((5 if blocks is None else None)
                       if center_text in ('', '默认', '自动') else int(center_text))
            spec = DesignSpec('DOE', tuple(factors), responses,
                              seed=int(self.options['随机 seed'].get()),
                              design_type='central_composite', ccd_alpha=alpha,
                              ccd_center_points=centers,
                              ccd_axial_points=2*k*replicates,
                              ccd_fraction=None if fraction == 'full' else fraction,
                              block_count=blocks)
            return create_ccd(spec, replicates, measured=self.measured.get())
        centers = int(center_text)
        blocked = (hasattr(self, 'block_replicates') and self.block_replicates.get())
        spec = DesignSpec('DOE', tuple(factors), responses,
                          seed=int(self.options['随机 seed'].get()),
                          generators=generators,
                          design_type='two_level_fractional' if self.fractional
                          else 'two_level_full',
                          block_count=replicates if blocked else None,
                          randomization_unit='block' if blocked else 'run')
        if self.fractional:
            from doe_fractional import create_fractional
            return create_fractional(spec, replicates, centers)
        return create_factorial(spec, replicates, centers)

    def preview(self):
        try:
            frame, meta = self.build()
            summary = f'{len(frame)} 次运行；前 5 个运行 ID：' + ', '.join(
                frame['运行ID'].head().tolist())
            if '区组' in frame:
                summary += f'；{frame["区组"].nunique()} 个区组，每个完整重复为一区组'
            if self.pb:
                spec = DesignSpec.from_dict(meta['design'])
                summary += '；因子水平：' + '；'.join(
                    f'{f.name} {" / ".join(f.levels) if f.factor_type == "categorical" else f"{f.low} / {f.high}"}' for f in spec.factors)
            if self.dsd:
                spec = DesignSpec.from_dict(meta['design'])
                summary += '；因子水平：' + '；'.join(
                    f'{f.name} {" / ".join(f.levels) if f.factor_type == "categorical" else f"{f.low} / {f.high}"}'
                    for f in spec.factors)
            if self.bbd:
                counts = frame['点类型'].value_counts()
                spec = DesignSpec.from_dict(meta['design'])
                summary += (f"；边点 {counts.get('edge', 0)}，中心点 {counts.get('center', 0)}"
                            f"，区组 {frame['区组'].nunique()}"
                            f"；每个因子取低/中/高三水平，完整二次模型 "
                            f"{1 + 2 * len(spec.factors) + len(spec.factors) * (len(spec.factors) - 1) // 2} 项")
            if self.ccd:
                from doe_ccd import axial_levels
                spec = DesignSpec.from_dict(meta['design'])
                points = [f'{f.name}: {lo!r} / {hi!r} {f.unit or ""}'
                          for f in spec.factors if f.factor_type == 'continuous'
                          for lo, hi in [axial_levels(f, spec.ccd_alpha)]]
                categories = [f'{f.name}: {" / ".join(map(str, f.levels))}'
                              for f in spec.factors if f.factor_type == 'categorical']
                counts = frame['点类型'].value_counts()
                summary += (f"；α={spec.ccd_alpha:.8g}；因子点 {counts.get('factorial', 0)}"
                            f"，轴点 {counts.get('axial', 0)}，中心点 {counts.get('center', 0)}；"
                            + '；'.join(points + categories)
                            + f"；区组 {frame['区组'].nunique() if '区组' in frame else 1}")
                if spec.ccd_alpha > 1:
                    summary += '；警告：轴点超出低高水平'
            if self.fractional:
                design = meta['design']
                relations = design['defining_relations']
                resolution = min(len(item.split('=', 1)[1].lstrip('-'))
                                 for item in relations)
                aliases = design['aliases']
                shown_aliases = '；'.join(aliases[:6]) or '无'
                if len(aliases) > 6:
                    shown_aliases += f'；…（共 {len(aliases)} 项）'
                shown_relations = '；'.join(relations[:6])
                if len(relations) > 6:
                    shown_relations += f'；…（共 {len(relations)} 项）'
                roman = {3: 'III', 4: 'IV', 5: 'V', 6: 'VI'}.get(resolution, resolution)
                summary += (f'；分辨度 {roman}'
                            f"；生成元 {'；'.join(design['generators'])}"
                            f'；定义字 {shown_relations}'
                            f'；别名组（混杂，不能单独估计）{shown_aliases}')
            self.preview_text.set(summary)
            if self.pb or self.dsd:
                preview = tk.Toplevel(self.main)
                preview.title('设计预览')
                preview.geometry('900x460')
                columns = tuple(frame.columns)
                tree = ttk.Treeview(preview, columns=columns, show='headings')
                vertical = ttk.Scrollbar(preview, orient='vertical', command=tree.yview)
                horizontal = ttk.Scrollbar(preview, orient='horizontal', command=tree.xview)
                tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
                vertical.pack(side='right', fill='y')
                horizontal.pack(side='bottom', fill='x')
                tree.pack(fill='both', expand=True)
                for name in columns:
                    tree.heading(name, text=str(name))
                    tree.column(name, width=100, minwidth=60, stretch=False)
                for row in frame.itertuples(index=False, name=None):
                    tree.insert('', 'end', values=tuple('' if pd.isna(value) else value
                                                        for value in row))
        except (ValueError, TypeError, OverflowError) as exc:
            messagebox.showerror('试验设计', str(exc), parent=self.main)

    def create(self):
        try:
            frame, meta = self.build()
            if self.ccd and meta['design']['ccd_alpha'] > 1:
                from doe_ccd import axial_levels
                spec = DesignSpec.from_dict(meta['design'])
                levels = '\n'.join(f'{f.name}: {lo!r} / {hi!r} {f.unit or ""}'
                                   for f in spec.factors if f.factor_type == 'continuous'
                                   for lo, hi in [axial_levels(f, spec.ccd_alpha)])
                if not messagebox.askyesno('轴点超出低高水平',
                        '外接设计的轴点超出低高水平，请确认工艺安全：\n' + levels,
                        parent=self.main):
                    return
            self.app.addSheet('DOE', frame, {'doe': meta})
        except (ValueError, TypeError, OverflowError) as exc:
            messagebox.showerror('试验设计', str(exc), parent=self.main)
            return
        self.main.destroy()


class CreateGeneralFactorial:
    """一般全因子创建、限量预览及确认。"""

    def __init__(self, app):
        self.app = app
        self.main = tk.Toplevel(app.main)
        self.main.title('创建一般全因子设计')
        self.main.geometry('900x680')
        self.main.bind('<F1>', lambda event: open_help('doe.general_factorial', parent=self.main))
        area = ttk.Frame(self.main)
        area.pack(fill='both', expand=True)
        canvas = tk.Canvas(area, highlightthickness=0)
        scrollbar = ttk.Scrollbar(area, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)
        grid = ttk.Frame(canvas, padding=8)
        canvas.create_window((0, 0), window=grid, anchor='nw')
        grid.bind('<Configure>', lambda event: canvas.configure(scrollregion=canvas.bbox('all')))
        ttk.Label(grid, text='因子数').grid(row=0, column=0, sticky='w')
        self.factor_count = ttk.Combobox(grid, values=tuple(range(2, 11)),
                                         state='readonly', width=5)
        self.factor_count.set('2')
        self.factor_count.grid(row=0, column=1, sticky='w')
        self.factor_count.bind('<<ComboboxSelected>>', self.update_factor_rows)
        headers = ('因子', '名称', '标签类型', '水平标签（用 ; 分隔）')
        for col, title in enumerate(headers):
            ttk.Label(grid, text=title).grid(row=1, column=col, padx=4, sticky='w')
        self.labels, self.fields = [], []
        for index in range(10):
            label = ttk.Label(grid, text=chr(65 + index))
            label.grid(row=index + 2, column=0, sticky='w')
            name = ttk.Entry(grid, width=18)
            name.insert(0, chr(65 + index))
            name.grid(row=index + 2, column=1, padx=4, pady=2)
            kind = ttk.Combobox(grid, values=('文字', '数值'), state='readonly', width=8)
            kind.set('文字')
            kind.grid(row=index + 2, column=2, padx=4, pady=2)
            levels = ttk.Entry(grid, width=42)
            levels.insert(0, '低;高')
            levels.grid(row=index + 2, column=3, padx=4, pady=2, sticky='ew')
            self.labels.append(label)
            self.fields.append((name, kind, levels))
        row = 13
        ttk.Label(grid, text='重复数').grid(row=row, column=0, sticky='w')
        self.replicates = ttk.Entry(grid, width=8)
        self.replicates.insert(0, '1')
        self.replicates.grid(row=row, column=1, sticky='w')
        ttk.Label(grid, text='随机 seed').grid(row=row, column=2, sticky='w')
        self.seed = ttk.Entry(grid, width=12)
        self.seed.insert(0, '1')
        self.seed.grid(row=row, column=3, sticky='w')
        row += 1
        ttk.Label(grid, text='响应名称').grid(row=row, column=0, sticky='w')
        self.responses = ttk.Entry(grid, width=42)
        self.responses.insert(0, 'Y')
        self.responses.grid(row=row, column=1, columnspan=3, sticky='ew')
        row += 1
        self.block_replicates = tk.BooleanVar(value=False)
        ttk.Checkbutton(grid, text='每个完整重复作为一个区组',
                        variable=self.block_replicates).grid(
            row=row, column=0, columnspan=3, sticky='w')
        self.preview_text = tk.StringVar(value='')
        ttk.Label(grid, textvariable=self.preview_text, wraplength=780).grid(
            row=row + 1, column=0, columnspan=4, sticky='w', pady=6)
        self.update_factor_rows()
        bar = ttk.Frame(self.main, padding=8)
        bar.pack(fill='x')
        ttk.Button(bar, text='预览', command=self.preview).pack(side='left')
        ttk.Button(bar, text='创建', command=self.create).pack(side='left', padx=4)
        ttk.Button(bar, text='取消', command=self.main.destroy).pack(side='left')

    def update_factor_rows(self, event=None):
        count = int(self.factor_count.get())
        for index, (label, fields) in enumerate(zip(self.labels, self.fields)):
            widgets = (label, *fields)
            for widget in widgets:
                if index < count:
                    widget.grid()
                else:
                    widget.grid_remove()

    def build(self):
        factors = []
        for index, (name_entry, kind_box, levels_entry) in enumerate(
                self.fields[:int(self.factor_count.get())]):
            name = name_entry.get().strip()
            if not name:
                raise ValueError(f'因子 {chr(65+index)} 名称不能为空。')
            raw = [value.strip() for value in levels_entry.get().split(';')]
            if any(not value for value in raw):
                raise ValueError(f'因子 {chr(65+index)} 的水平标签不能为空。')
            level_type = 'text' if kind_box.get() == '文字' else 'numeric'
            levels = tuple(raw) if level_type == 'text' else tuple(ccd_number(value) for value in raw)
            factors.append(FactorSpec(chr(65 + index), name, None, None,
                                      factor_type='categorical', levels=levels,
                                      level_type=level_type))
        response_names = tuple(value.strip() for value in self.responses.get().split(','))
        replicates = int(self.replicates.get())
        seed = int(self.seed.get())
        block_count = replicates if self.block_replicates.get() else None
        spec = DesignSpec('DOE', tuple(factors), response_names, seed=seed,
                          design_type='general_full_factorial', block_count=block_count,
                          randomization_unit='block' if block_count else 'run')
        from doe_general_factorial import create_general_factorial
        return create_general_factorial(spec, replicates=replicates)

    def preview(self):
        try:
            frame, _ = self.build()
            self.preview_text.set(
                f'{len(frame)} 次运行；每因子水平数：' + ' × '.join(
                    str(len(fields[2].get().split(';'))) for fields in
                    self.fields[:int(self.factor_count.get())]))
            preview = tk.Toplevel(self.main)
            preview.title('一般全因子运行预览')
            preview.geometry('900x460')
            shown = min(len(frame), 100)
            ttk.Label(preview, text=f'显示前 {shown} 行（共 {len(frame)} 行）').pack(anchor='w')
            columns = tuple(frame.columns)
            tree = ttk.Treeview(preview, columns=columns, show='headings')
            vertical = ttk.Scrollbar(preview, orient='vertical', command=tree.yview)
            horizontal = ttk.Scrollbar(preview, orient='horizontal', command=tree.xview)
            tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
            vertical.pack(side='right', fill='y')
            horizontal.pack(side='bottom', fill='x')
            tree.pack(fill='both', expand=True)
            for name in columns:
                tree.heading(name, text=str(name))
                tree.column(name, width=100, minwidth=60, stretch=False)
            for row in frame.iloc[:shown].itertuples(index=False, name=None):
                tree.insert('', 'end', values=tuple('' if pd.isna(value) else value
                                                    for value in row))
        except (ValueError, TypeError, OverflowError) as error:
            messagebox.showerror('试验设计', str(error), parent=self.main)

    def create(self):
        try:
            frame, metadata = self.build()
            self.app.addSheet('DOE', frame, {'doe': metadata})
        except (ValueError, TypeError, OverflowError) as error:
            messagebox.showerror('试验设计', str(error), parent=self.main)
            return
        self.main.destroy()


class AnalyzeDOE:
    def __init__(self, app, screening=False):
        self.owner = app
        self.source = app.getCurrentTable()
        self.app = SheetApp(app, self.source)
        metadata = getattr(self.source, 'doe_metadata', None)
        if not metadata:
            messagebox.showerror('试验设计', '当前工作表不是 DOE 设计。', parent=app.main)
            return
        design_type = metadata.get('design', {}).get('design_type')
        if (screening and design_type != 'definitive_screening') or (not screening and design_type == 'definitive_screening'):
            messagebox.showerror('试验设计', '请从对应的设计分析入口打开当前工作表。', parent=app.main)
            return
        if design_type not in ('two_level_full', 'two_level_fractional',
                               'central_composite', 'box_behnken', 'plackett_burman',
                               'definitive_screening', 'general_full_factorial',
                               'split_plot', 'custom_factorial', 'custom_rsm',
                               'custom_screening'):
            messagebox.showerror('试验设计', '当前 DOE 设计类型暂不支持分析。', parent=app.main)
            return
        self.fractional = design_type == 'two_level_fractional'
        self.pb = design_type == 'plackett_burman'
        self.dsd = design_type == 'definitive_screening'
        self.ccd = design_type == 'central_composite'
        self.bbd = design_type == 'box_behnken'
        self.general = design_type == 'general_full_factorial'
        self.splitplot = design_type == 'split_plot'
        self.custom = design_type.startswith('custom_')
        self.custom_factorial = design_type == 'custom_factorial'
        self.custom_rsm = design_type == 'custom_rsm'
        self.custom_screening = design_type == 'custom_screening'
        self.rsm = self.ccd or self.bbd or self.custom_rsm
        self.main = tk.Toplevel(app.main)
        self.main.title('分析 Split-Plot 裂区设计' if self.splitplot else
                        '分析一般全因子设计' if self.general else
                        '分析筛选设计' if self.dsd else '分析 Plackett–Burman 设计' if self.pb else '分析响应面模型' if self.rsm else
                        '分析两水平部分因子设计' if self.fractional else '分析因子设计')
        help_topic = ('doe.custom' if self.custom else
                      'doe.split_plot' if self.splitplot else
                      'doe.general_factorial' if self.general else
                      'doe.dsd' if self.dsd else 'doe.pb' if self.pb else 'doe.bbd' if self.bbd else 'doe.ccd' if self.ccd
                      else 'doe.fractional' if self.fractional else 'doe.full_factorial')
        self.main.bind('<F1>', lambda event: open_help(help_topic, parent=self.main))
        self.result = None
        controls = ttk.Frame(self.main, padding=8)
        controls.pack(fill='x')
        ttk.Label(controls, text='响应').pack(side='left')
        names = metadata['design']['response_names']
        self.response = ttk.Combobox(controls, values=names, state='readonly', width=15)
        self.response.set(names[0])
        self.response.pack(side='left', padx=4)
        ttk.Label(controls, text='模型阶次').pack(side='left')
        self.order = ttk.Combobox(controls, values=list(range(1, len(metadata['design']['factors'])+1)),
                                  state='readonly', width=4)
        self.order.set(str(min(2, len(metadata['design']['factors']))))
        if self.rsm or self.pb or self.dsd or self.splitplot:
            self.order.configure(state='disabled')
        if self.pb or self.dsd:
            self.order.set('1')
        self.order.pack(side='left', padx=4)
        design_factors = metadata['design']['factors']
        factor_ids = [factor['factor_id'] for factor in design_factors]
        plot_factor_ids = ([factor['factor_id'] for factor in design_factors
                            if factor['factor_type'] == 'continuous']
                           if self.rsm else factor_ids)
        ttk.Label(controls, text='绘图因子' if self.rsm else
                  '主效应/交互因子' if self.general else '交互因子').pack(side='left')
        self.factor_x = ttk.Combobox(controls, values=plot_factor_ids,
                                     state='readonly', width=4)
        self.factor_y = ttk.Combobox(controls, values=plot_factor_ids,
                                     state='readonly', width=4)
        if len(plot_factor_ids) >= 2:
            self.factor_x.set(plot_factor_ids[0])
            self.factor_y.set(plot_factor_ids[1])
        self.factor_x.pack(side='left', padx=2)
        self.factor_y.pack(side='left', padx=2)
        if self.pb or self.dsd:
            self.effect_plot = ttk.Combobox(controls, values=('Pareto', '正态', '半正态'),
                                             state='readonly', width=8)
            self.effect_plot.set('Pareto')
            self.effect_plot.pack(side='left', padx=4)
        if self.rsm:
            self.omit_terms = tk.StringVar(value='')
            ttk.Label(controls, text='排除项').pack(side='left', padx=(8, 2))
            self.term_entry = ttk.Entry(controls, textvariable=self.omit_terms, width=22)
            self.term_entry.pack(side='left')
            ttk.Label(controls, text='如 A*B;C²').pack(side='left', padx=2)
            self.use_blocks = tk.BooleanVar(value=True)
            ttk.Checkbutton(controls, text='纳入区组',
                            variable=self.use_blocks).pack(side='left', padx=4)
        if self.dsd:
            model_bar = ttk.Frame(self.main, padding=(8, 0))
            model_bar.pack(fill='x')
            ttk.Label(model_bar, text='模型').pack(side='left')
            self.screening_model = ttk.Combobox(model_bar, values=('主效应', '主效应与平方', '自定义'),
                                                 state='readonly', width=14)
            self.screening_model.set('主效应')
            self.screening_model.pack(side='left', padx=4)
            ttk.Label(model_bar, text='模型项').pack(side='left')
            self.screening_terms = ttk.Entry(model_bar, width=36)
            self.screening_terms.pack(side='left', padx=4)
            contrast_bar = ttk.Frame(self.main, padding=(8, 0))
            contrast_bar.pack(fill='x')
            ttk.Label(contrast_bar, text='对比').pack(side='left')
            self.screening_contrast = ttk.Entry(contrast_bar, width=48)
            self.screening_contrast.pack(side='left', padx=4)
        self.fixed = {}
        if self.rsm:
            fixed_bar = ttk.Frame(self.main, padding=(8, 0))
            fixed_bar.pack(fill='x')
            for factor in design_factors:
                factor_id = factor['factor_id']
                if factor['factor_type'] == 'categorical':
                    ttk.Label(fixed_bar, text=f'{factor_id} 水平').pack(side='left')
                    control = ttk.Combobox(fixed_bar, values=factor['levels'],
                                           state='readonly', width=10)
                    control.set(factor['levels'][0])
                else:
                    ttk.Label(fixed_bar, text=f'{factor_id} 固定值').pack(side='left')
                    control = ttk.Entry(fixed_bar, width=5)
                    control.insert(0, '0')
                control.pack(side='left', padx=2)
                self.fixed[factor_id] = control
            ttk.Label(self.main, text='实际水平 X=(高+低)/2+x×(高−低)/2').pack(anchor='w', padx=8)
        ttk.Button(controls, text='分析', command=self.analyze).pack(side='left')
        ttk.Button(controls, text='图形', command=self.plot).pack(side='left', padx=4)
        ttk.Button(controls, text='关闭', command=self.main.destroy).pack(side='right')
        self.status = tk.StringVar(value='')
        ttk.Label(self.main, textvariable=self.status).pack(fill='x', padx=8)
        self.tabs = ttk.Notebook(self.main)
        self.tabs.pack(fill='both', expand=True, padx=8, pady=8)
        self.main.geometry('900x620')

    def analyze(self):
        try:
            self.app.getCurrentTable()
            if self.owner.getCurrentTable() is not self.source:
                raise ValueError('来源工作表已切换，请切回后重新分析。')
            self.owner._finish_edit()
            frame = self.source.model.df.copy(deep=True)
            if self.rsm and not self.custom:
                from doe_rsm import analyze_rsm
                terms = None
                omitted = self.omit_terms.get().strip()
                if omitted:
                    from doe_rsm_model import TermModel
                    full = TermModel(DesignSpec.from_dict(
                        self.source.doe_metadata['design']).factors).terms
                    excluded = {item.strip() for item in omitted.split(';') if item.strip()}
                    unknown = excluded - set(full)
                    if unknown:
                        raise ValueError('排除项不在完整二次模型中：' + '、'.join(sorted(unknown)))
                    terms = [term for term in full if term not in excluded]
                result = analyze_rsm(frame, self.source.doe_metadata, self.response.get(),
                                     terms, self.use_blocks.get())
            elif self.custom:
                from doe_custom_analysis import analyze_custom
                terms = None
                omitted = self.omit_terms.get().strip() if self.custom_rsm else ''
                if omitted:
                    from doe_rsm_model import TermModel
                    full = TermModel(DesignSpec.from_dict(
                        self.source.doe_metadata['design']).factors,
                        DesignSpec.from_dict(self.source.doe_metadata['design']).model_terms).terms
                    excluded = {item.strip() for item in omitted.split(';') if item.strip()}
                    unknown = excluded - set(full)
                    if unknown:
                        raise ValueError('排除项不在当前模型中：' + '、'.join(sorted(unknown)))
                    terms = [term for term in full if term not in excluded]
                result = analyze_custom(
                    frame, self.source.doe_metadata, self.response.get(),
                    int(self.order.get()), terms, self.use_blocks.get() if self.custom_rsm else True)
            elif self.dsd:
                from doe_screening_analysis import analyze_dsd
                factors = DesignSpec.from_dict(self.source.doe_metadata['design']).factors
                names = [f.factor_id for f in factors]
                choice = self.screening_model.get()
                terms = [(name,) for name in names]
                if choice == '主效应与平方':
                    terms += [(f.factor_id, f.factor_id) for f in factors if f.factor_type == 'continuous']
                elif choice == '自定义':
                    terms = []
                    for text in self.screening_terms.get().split(';'):
                        text = text.strip()
                        if text:
                            terms.append((text[:-2], text[:-2]) if text.endswith('^2') else tuple(text.split('*')))
                elif choice != '主效应':
                    raise ValueError('请选择有效模型')
                result = analyze_dsd(frame, self.source.doe_metadata, self.response.get(), terms)
                contrast_text = self.screening_contrast.get().strip()
                if contrast_text:
                    from doe_screening_analysis import screening_contrast
                    weights = np.zeros(len(result['names']))
                    seen = set()
                    for item in contrast_text.split(';'):
                        name, separator, value = item.partition('=')
                        name = name.strip().replace('^2', '²')
                        if not separator or name not in result['names'] or name in seen:
                            raise ValueError('对比格式为模型项=权重，多个项用分号分隔。')
                        seen.add(name)
                        weights[result['names'].index(name)] = float(value)
                    result['contrast'] = screening_contrast(result, weights)
            elif self.pb:
                from doe_screening_analysis import analyze_pb
                result = analyze_pb(frame, self.source.doe_metadata, self.response.get())
            elif self.general:
                from doe_general_factorial_analysis import analyze_general_factorial
                result = analyze_general_factorial(
                    frame, self.source.doe_metadata, self.response.get(), int(self.order.get()))
            elif self.splitplot:
                from doe_splitplot_analysis import analyze_split_plot
                result = analyze_split_plot(frame, self.source.doe_metadata, self.response.get())
            elif self.fractional:
                from doe_fractional_analysis import analyze_fractional
                result = analyze_fractional(
                    frame, self.source.doe_metadata, self.response.get(),
                    int(self.order.get()))
            else:
                result = analyze_factorial(frame, self.source.doe_metadata,
                                           self.response.get(), int(self.order.get()))
            self.publish(result)
            self.analysis_frame = frame
        except (ValueError, TypeError, RuntimeError, OverflowError) as exc:
            self.result = None
            self.status.set('分析失败：' + str(exc))
            messagebox.showerror('试验设计', str(exc), parent=self.main)

    def publish(self, result):
        for tab in self.tabs.tabs():
            self.tabs.nametowidget(tab).destroy()
        self.show_diagnostics(result)
        self.status.set(f"响应 {result['response']}，{result['n']} 行分析快照；数据修改后需重新分析；" +
                        result['status'] + '；' + result['assumption'])
        if self.splitplot:
            labels = {'block': '区组', 'whole_plot_error': '整区误差',
                      'subplot_error': '子区误差', 'total': '总计'}
            self.show_table('裂区方差分析',
                            ['来源', '平方和', '自由度', '均方', 'F', 'p', '误差层'], [
                [labels.get(row['term'], row['term']), row['ss'], row['df'],
                 row['ms'], row['f'], row['p'],
                 labels.get(row['error_stratum'], row['error_stratum'])]
                for row in result['anova']])
            design = result['design']
            self.show_table('拟合与残差', ['运行ID', '区组', '整区ID', '子区ID',
                                           '运行序', '响应', '拟合值', '残差'], [
                [run.run_id, run.block, run.whole_plot_id, run.subplot_id,
                 run.run_order, run.responses[result['response']],
                 result['fitted'][index], result['residuals'][index]]
                for index, run in enumerate(design.runs)])
            self.result = result
            return
        if self.custom:
            inf = result['inference']
            if self.custom_screening:
                self.show_table('模型', ['运行数', '项数', '秩', '残差自由度', 'SSE'], [[
                    result['n'], result['p'], result['rank'], result['df'],
                    result['sse']]])
                self.show_table('系数与效应', ['项', '系数', '效应'], [
                    [name, result['coefficients'][i], result['effects'][i]]
                    for i, name in enumerate(result['names'])])
            else:
                self.show_table('模型', ['运行数', '项数', '秩', '残差自由度', 'SSE',
                                         '纯误差自由度', '失拟自由度', '条件数'], [[
                    result['n'], result['p'], result['rank'], result['df'],
                    result['sse'], result['pure_error_df'],
                    result['lack_of_fit_df'], result.get('condition')]])
                self.show_table('系数与效应', ['项', '系数', 'SE', 't', 'p'], [
                    [name, result['coefficients'][i],
                     inf['se'][i] if inf else None,
                     inf['t'][i] if inf else None,
                     inf['p'][i] if inf else None]
                    for i, name in enumerate(result['names'])])
                if result['anova']:
                    self.show_table('项平方和', ['来源', '平方和', '自由度', '均方', 'F', 'p'], [
                        [row.get('source', row.get('term')), row['ss'], row['df'], row['ms'],
                         row['f'], row['p']] for row in result['anova']])
            self.show_table('拟合与残差', ['运行ID', '响应', '拟合值', '残差'], [
                [run.run_id, run.responses[result['response']],
                 result['fitted'][index], result['residuals'][index]]
                for index, run in enumerate(result['design'].runs)])
            self.result = result
            return

        self.publish_tables(result)

    def show_diagnostics(self, result):
        """统一诊断字段语义；不同设计仍保留各自的统计模型。"""
        from doe_diagnostics import contract
        design_type = result['design'].spec.design_type
        data = contract(result, design_type)
        self.show_table('诊断合同', ['项目', '值', '说明'], [
            [row['item'], row['value'], row['note']] for row in data['rows']])

    def publish_tables(self, result):
        inf = result['inference']
        if self.pb or self.dsd:
            def available(value):
                return float(value) if value is not None and np.isfinite(value) else None
            self.show_table('系数与效应', ['项', '系数', '效应', 'SE', 't', 'p'], [
                [name, available(result['coefficients'][i]), result['effects'][i],
                 available(inf['se'][i]) if inf else None, available(inf['t'][i]) if inf else None,
                 available(inf['p'][i]) if inf else None]
                for i, name in enumerate(result['names'])])
            self.show_table('模型', ['运行数', '项数', '秩', '残差自由度', 'SSE'],
                            [[result['n'], result['p'], result['rank'], result['df'], result['sse']]])
            if self.pb:
                curvature = result['curvature']
                self.show_table('纯误差与曲率', ['纯误差自由度', '纯误差平方和', '中心点偏差', 'F（残差）', 'p'], [[
                    result['pure_error_df'], result['pure_error_sse'],
                    curvature['difference'] if curvature else None,
                    curvature['f'] if curvature else None, curvature['p'] if curvature else None]])
                if result['lenth']:
                    self.show_table('Lenth PSE', ['PSE', '参考线', '自由度'], [[
                        result['lenth']['pse'], result['lenth']['margin'], result['lenth']['df']]])
            if self.dsd and result['rank'] < result['p']:
                self.show_table('可估计性', ['项', '状态'], [
                    [name, '可估计' if result['estimable'][i] else '不可单独估计']
                    for i, name in enumerate(result['names'])])
                self.show_table('零空间', ['序号', '模型项权重'], [
                    [i + 1, '；'.join(f'{name}={weight:.6g}' for name, weight in zip(result['names'], row)
                                    if abs(weight) > 1e-10)]
                    for i, row in enumerate(result['nullspace'])])
            if self.dsd and 'contrast' in result:
                contrast = result['contrast']
                self.show_table('指定对比', ['状态', '估计值', 'SE', 't', 'p'], [[
                    '可估计' if contrast['estimable'] else '不可估计', contrast['estimate'],
                    contrast['se'], contrast['t'], contrast['p']]])
            if inf and result['rank'] > 1:
                self.show_table('方差分析', ['来源', '平方和', '自由度', '均方', 'F', 'p'], [
                    ['模型', result['ssr'], result['rank'] - 1, result['ssr'] / (result['rank'] - 1), inf['f'], inf['model_p']],
                    ['残差', result['sse'], result['df'], inf['mse'], None, None],
                    ['总计', result['sst'], result['n'] - 1, None, None, None]])
            self.show_table('混杂投影', ['线性项', '二阶项', '投影系数'],
                            [[p['main'], p['interaction'], p['projection']] for p in result['projections']])
            if self.dsd and result['nonlinear_projections']:
                self.show_table('平方与交互投影', ['平方项', '交互项', '投影系数'], [[
                    p['square'], p['interaction'], p['projection']] for p in result['nonlinear_projections']])
            self.show_table('拟合与残差', ['运行ID', '响应', '拟合值', '残差'],
                            [[run.run_id, run.responses[result['response']], result['fitted'][i], result['residuals'][i]]
                             for i, run in enumerate(result['design'].runs)])
            self.result = result
            return
        if self.general:
            self.show_table('模型', ['运行数', '秩', '模型自由度', '残差自由度',
                                     'SSE', '纯误差自由度', '纯误差平方和',
                                     '区组误差自由度', '区组误差平方和'], [[
                result['n'], result['rank'], result['rank'] - 1, result['df'],
                result['sse'], result['pure_error_df'], result['pure_error_sse'],
                result['block_error_df'], result['block_error_sse']]])
            self.show_table('分类因子 ANOVA', ['来源', '偏平方和', '自由度', '均方', 'F', 'p'], [
                [row['term'], row['ss'], row['df'], row['ms'], row['f'], row['p']]
                for row in result['anova']])
            self.show_table('边际均值', ['因子', '水平', '均值', '运行数'], [
                [item['factor_id'], item['level'], item['mean'], item['n']]
                for item in result['marginal_means']])
            self.show_table('组合均值', ['因子水平组合', '均值', '运行数'], [
                ['；'.join(f'{key}={value}' for key, value in item['levels'].items()),
                 item['mean'], item['n']] for item in result['cell_means']])
            lof = result['lack_of_fit']
            diagnostics = [
                ['纯误差', result['pure_error_sse'], result['pure_error_df'], None, None],
                ['区组×处理误差', result['block_error_sse'], result['block_error_df'], None, None],
                ['失拟', result['lack_of_fit_sse'], result['lack_of_fit_df'],
                 lof['f'] if lof else None, lof['p'] if lof else None],
            ]
            self.show_table('纯误差与失拟', ['来源', '平方和', '自由度', 'F', 'p'], diagnostics)
            self.show_table('拟合与残差', ['运行ID', '响应', '拟合值', '残差'], [
                [run.run_id, run.responses[result['response']], result['fitted'][i],
                 result['residuals'][i]] for i, run in enumerate(result['design'].runs)])
            self.result = result
            return
        if self.rsm:
            factors = result['design'].spec.factors
            self.show_table('因子编码', ['因子', '名称', '低水平', '高水平', '单位'], [
                [f.factor_id, f.name, f.low, f.high, f.unit or ''] for f in factors])
        if self.fractional:
            alias_by_representative = {
                group['representative']: group['label']
                for group in result['alias_groups'] if group['representative']
            }
            rows = []
            for i, name in enumerate(result['names']):
                rows.append([name, alias_by_representative.get(name, name),
                             result['coefficients'][i], result['effects'][i]] +
                            ([inf['se'][i], inf['t'][i], inf['p'][i],
                              inf['ci_low'][i], inf['ci_high'][i]] if inf else [None]*5))
            self.show_table('系数与别名组效应',
                            ['代表项', '完整别名组', '系数', '别名组效应',
                             'SE', 't', 'p', 'CI低', 'CI高'], rows)
            self.show_table('别名与代表项', ['当前代表项', '别名组', '状态'], [
                [group['representative'] or '', group['label'],
                 '截距' if group['representative'] == '截距' else
                 '已纳入当前模型' if group['representative'] else '未纳入当前模型']
                for group in result['alias_groups']])
            self.show_table('模型', ['n', '项数', '秩', '模型残差自由度', 'SSE',
                                     '纯误差自由度', '纯误差平方和', '失拟自由度', '失拟平方和',
                                     '区组误差自由度', '区组误差平方和', 'SSR', 'SST',
                                     'R²', '调整R²', 'F', '模型p'], [[
                result['n'], result['p'], result['rank'], result['df'], result['sse'],
                result['pure_error_df'], result['pure_error_sse'], result['lack_of_fit_df'],
                result['lack_of_fit_sse'], result['block_error_df'], result['block_error_sse'],
                result['ssr'],
                result['sst'], result['r2'], result['adjusted_r2'],
                inf['f'] if inf else None, inf['model_p'] if inf else None]])
            self.show_table('项方差分析', ['来源', '平方和', '自由度', '均方', 'F', 'p'], [
                [row['term'], row['ss'], row['df'], row['ms'], row['f'], row['p']]
                for row in result['anova']])
            if result['curvature']:
                curvature = result['curvature']
                self.show_table('中心点曲率', ['中心点偏移', '对比平方和', '自由度', 'F', 'p'], [[
                    curvature['difference'], curvature['ss'], curvature['df'],
                    curvature['f'], curvature['p']]])
            if inf:
                self.show_table('方差分析', ['来源', '平方和', '自由度', '均方', 'F', 'p'],
                                [['模型', result['ssr'], result['p']-1,
                                  result['ssr']/(result['p']-1), inf['f'], inf['model_p']],
                                 ['残差', result['sse'], result['df'], inf['mse'], None, None],
                                 ['总计', result['sst'], result['n']-1, None, None, None]])
            lof = result['lack_of_fit']
            self.show_table('纯误差与失拟', ['来源', '平方和', '自由度', 'F', 'p'], [
                ['纯误差', result['pure_error_sse'], result['pure_error_df'], None, None],
                ['区组×处理误差', result['block_error_sse'], result['block_error_df'], None, None],
                ['失拟', result['lack_of_fit_sse'], result['lack_of_fit_df'],
                 lof['f'] if lof else None, lof['p'] if lof else None],
            ])
            self.show_table('拟合与残差', ['来源行号', '运行ID', '运行序', '响应', '拟合值', '残差'],
                            [[i+1, run.run_id, run.run_order, run.responses[result['response']],
                              result['fitted'][i], result['residuals'][i]]
                             for i, run in enumerate(result['design'].runs)])
            self.result = result
            return
        rows = []
        for i, name in enumerate(result['names']):
            rows.append([name, result['coefficients'][i], result['effects'][i]] +
                        ([inf['se'][i], inf['t'][i], inf['p'][i], inf['ci_low'][i], inf['ci_high'][i]]
                         if inf else [None]*5))
        if self.rsm:
            self.show_table('系数', ['项', '系数', 'SE', 't', 'p', 'CI低', 'CI高'],
                            [row[:2]+row[3:] for row in rows])
            if result['blocks']:
                self.show_table('区组', ['区组', '运行数'], [
                    [block, sum(run.block == block for run in result['design'].runs)]
                    for block in result['blocks']])
            anova = result['anova']
            if anova:
                self.show_table('项平方和', ['来源', '平方和', '自由度', '均方', 'F', 'p'], [
                    [row['source'], row['ss'], row['df'], row['ms'], row['f'], row['p']]
                    for row in anova])
                self.show_table('诊断可用性', ['项目', '状态', '说明'], [
                    ['系数估计', '可用', '基于当前响应快照的普通最小二乘。'],
                    ['系数 SE / t / p / CI', '可用' if result['inference'] else '不可用',
                     ('残差自由度 %d，纯误差自由度 %d。' % (result['df'], result['pure_error_df']))
                     if result['inference'] else
                     '残差自由度或正纯误差不足，不能估计误差均方。'],
                    ['项平方和', '可用', '逐项按完整模型对照的平方和与自由度。'],
                    ['项 F / p', '可用' if result['inference'] else '不可用',
                     '使用模型残差均方；不要求纯误差。' if result['inference']
                     else '缺少可用误差均方。'],
                    ['纯误差', '可用' if result['pure_error_df'] > 0 else '不可用',
                     ('同一设定独立重复 %d 个额外自由度。' % result['pure_error_df'])
                     if result['pure_error_df'] > 0 else '没有相同设定的独立重复。'],
                    ['失拟', '可用' if result['lack_of_fit'] else '不可用',
                     ('失拟 F=%.6g，p=%.6g。' % (result['lack_of_fit']['f'],
                                                  result['lack_of_fit']['p']))
                     if result['lack_of_fit'] else
                     '纯误差或失拟自由度不足，或纯误差为零。'],
                    ['曲率', ('可用' if result['curvature']['f'] is not None else '仅差值')
                     if result['curvature'] else '不可用',
                     ('中心与因子点均值差 %.6g；%s。' % (
                         result['curvature']['difference'],
                         'F=%.6g，p=%.6g。' % (result['curvature']['f'],
                                               result['curvature']['p'])
                         if result['curvature']['f'] is not None
                         else '区组效应未调整或纯误差不可估计，只报告差值。'))
                     if result['curvature'] else '缺少中心点或外圈点。'],
                    ['残差图', '可用', '只辅助诊断，不证明独立、同方差或正态。'],
                ])
        else:
            self.show_table('系数与效应', ['项', '系数', '效应', 'SE', 't', 'p', 'CI低', 'CI高'], rows)
        model_headers = ['n', '项数', '秩', '残差自由度', 'SSE', '纯误差自由度', '纯误差平方和',
                         '失拟自由度', '失拟平方和']
        model_row = [result['n'], result['p'], result['rank'], result['df'], result['sse'],
                     result['pure_error_df'], result['pure_error_sse'],
                     result['lack_of_fit_df'], result['lack_of_fit_sse']]
        if not self.rsm:
            model_headers.extend(['区组误差自由度', '区组误差平方和'])
            model_row.extend([result['block_error_df'], result['block_error_sse']])
        model_headers.extend(['SSR', 'SST', 'R²', '调整R²', 'F', '模型p'])
        model_row.extend([result['ssr'], result['sst'], result['r2'], result['adjusted_r2'],
                          inf['f'] if inf else None, inf['model_p'] if inf else None])
        self.show_table('模型', model_headers, [model_row])
        if not self.rsm:
            self.show_table('项方差分析', ['来源', '平方和', '自由度', '均方', 'F', 'p'], [
                [row['term'], row['ss'], row['df'], row['ms'], row['f'], row['p']]
                for row in result['anova']])
        if inf:
            self.show_table('方差分析', ['来源', '平方和', '自由度', '均方', 'F', 'p'],
                            [['模型', result['ssr'], result['p']-1,
                              result['ssr']/(result['p']-1), inf['f'], inf['model_p']],
                             ['残差', result['sse'], result['df'], inf['mse'], None, None],
                             ['总计', result['sst'], result['n']-1, None, None, None]])
        lof = result['lack_of_fit']
        curvature = result['curvature']
        tests = []
        if not self.rsm:
            tests.extend([
                ['纯误差', result['pure_error_sse'], result['pure_error_df'], None, None,
                 '按相同因子设定及相同区组分组。'],
                ['区组×处理误差', result['block_error_sse'], result['block_error_df'], None, None,
                 '区组模型残差；推断假设无处理×区组交互。'],
            ])
        tests.append(['失拟', result['lack_of_fit_sse'], result['lack_of_fit_df'],
                  lof['f'] if lof else None, lof['p'] if lof else None,
                  '已计算' if lof else '纯误差或失拟自由度不足，或纯误差为零'])
        if curvature:
            tests.append(['曲率（中心−因子均值）', curvature['ss'], 1,
                          curvature['f'], curvature['p'],
                          f"均值差 {curvature['difference']:.6g}；" +
                          ('已计算' if curvature['f'] is not None else '区组效应未调整或纯误差不可估计')])
        self.show_table('失拟与曲率', ['检验', '平方和', '自由度', 'F', 'p', '状态'], tests)
        self.show_table('拟合与残差', ['来源行号', '运行ID', '运行序', '响应', '拟合值', '残差'],
                        [[i+1, run.run_id, run.run_order, run.responses[result['response']],
                          result['fitted'][i], result['residuals'][i]]
                         for i, run in enumerate(result['design'].runs)])
        self.result = result

    def plot_custom_screening(self, result):
        from chart_style import font_families
        font = font_manager.FontProperties(family=font_families('Microsoft YaHei'))
        viewer = self.app.showPlotViewer(deferred=True, figsize=(12, 8))
        try:
            axes = viewer.fig.subplots(2, 3)
            names, values = [], []
            for index, name in enumerate(result['names'][1:], 1):
                effect = result['effects'][index]
                if effect is None:
                    continue
                names.append(name)
                values.append(abs(effect))
            axes[0, 0].barh(names, values)
            axes[0, 0].set_title('主效应绝对值 Pareto 图')
            axes[0, 0].set_xlabel('|效应|')
            properties = result['properties']
            axes[0, 1].axis('off')
            axes[0, 1].text(.02, .98,
                            f"主效应正交：{'是' if properties['main_orthogonal'] else '否'}\n"
                            f"主效应×二因子交互正交："
                            f"{'是' if properties['main_two_factor_orthogonal'] else '否'}\n"
                            f"含中心水平：{'是' if properties['has_zeros'] else '否'}",
                            va='top', fontproperties=font)
            self.plot_factorial_residuals([axes[1, 0], axes[1, 1], axes[1, 2]],
                                          result)
            axes[0, 2].axis('off')
            viewer.fig.suptitle('自定义筛选设计（按实际矩阵）', fontproperties=font)
            viewer.fig.tight_layout()
            viewer.canvas.draw()
            self.app.replacePlotViewer(viewer)
            viewer.main.deiconify()
        except Exception:
            viewer.close()
            raise

    def show_table(self, title, headers, values):
        tab = ttk.Frame(self.tabs)
        self.tabs.add(tab, text=title)
        table = StatTable(title=title, headers=headers, values=values)
        block = TableBlock(tab, table, paginate=True)
        block.pack(fill='both', expand=True)
        self.app.print(table)

    def plot(self):
        try:
            self.app.getCurrentTable()
            if self.owner.getCurrentTable() is not self.source:
                raise ValueError('来源工作表已切换，请切回后查看分析快照。')
            if self.result is None:
                raise ValueError('请先分析。')
            if not hasattr(self, 'analysis_frame') or not self.source.model.df.equals(self.analysis_frame):
                raise ValueError('工作表已更改，请重新分析。')
            from doe_core import restore_design_result
            current = restore_design_result(self.source.model.df, self.source.doe_metadata)
            if current.spec.to_dict() != self.result['design'].spec.to_dict():
                raise ValueError('设计定义已更改，请重新分析。')
            r = self.result
            if self.dsd:
                self.plot_dsd(r)
                return
            if self.custom_screening:
                self.plot_custom_screening(r)
                return
            if self.general:
                self.plot_general_factorial(r)
                return
            if self.splitplot:
                self.plot_split_plot(r)
                return
            factors = r['design'].spec.factors
            fractional = r['design'].spec.design_type == 'two_level_fractional'
            ids = [factor.factor_id for factor in factors]
            first_id, second_id = self.factor_x.get(), self.factor_y.get()
            if first_id not in ids or second_id not in ids or first_id == second_id:
                raise ValueError('请选择两个不同的因子。')
            first_index, second_index = ids.index(first_id), ids.index(second_id)
            if self.rsm:
                self.plot_rsm(r, first_index, second_index)
                return
            viewer = self.app.showPlotViewer(deferred=True, figsize=(10, 8))
            try:
                from chart_style import font_families
                font = font_manager.FontProperties(family=font_families('Microsoft YaHei'))
                axes = viewer.fig.subplots(2, 3)
                factorial = np.array([run.point_type == 'factorial' for run in r['design'].runs])
                coded = r['coded'][factorial]
                y = np.array([run.responses[r['response']] for run in r['design'].runs])[factorial]
                for i, factor in enumerate(factors):
                    if self.pb and len(factors) > 10 and i not in (first_index, second_index):
                        continue
                    means = [y[coded[:, i] == v].mean() for v in (-1, 1)]
                    label = (factor.factor_id + f' ({factor.levels[0]} / {factor.levels[1]})'
                             if factor.factor_type == 'categorical' else factor.factor_id)
                    axes[0, 0].plot([-1, 1], means, marker='o', label=label)
                axes[0, 0].set_title(
                    '主效应条件均值（按别名组解释）' if fractional else
                    '所选因子的主效应图' if self.pb and len(factors) > 10 else '主效应图')
                axes[0, 0].legend(prop=font)
                for v in (-1, 1):
                    means = [y[(coded[:, first_index] == x) &
                               (coded[:, second_index] == v)].mean() for x in (-1, 1)]
                    axes[0, 1].plot([-1, 1], means, marker='o',
                                    label=f'{second_id}={v}')
                axes[0, 1].set_title(
                    f'{first_id} × {second_id} 交互图（描述性；可能混杂）'
                    if fractional or self.pb else f'{first_id} × {second_id} 交互图')
                axes[0, 1].legend(prop=font)
                if self.pb:
                    self.plot_screening_effects(axes[1, 0], r)
                    effects = None
                elif fractional:
                    effect_by_name = dict(zip(r['names'], r['effects']))
                    effects = [(group['label'], abs(effect_by_name[group['representative']]))
                               for group in r['alias_groups']
                               if group['representative'] in effect_by_name and
                               effect_by_name[group['representative']] is not None]
                else:
                    effects = [(name, abs(effect))
                               for name, effect in zip(r['names'], r['effects'])
                               if effect is not None]
                if effects is not None:
                    effects.sort(key=lambda item: item[1])
                    axes[1, 0].barh([x[0] for x in effects], [x[1] for x in effects])
                    axes[1, 0].set_title('可估计别名组效应绝对值 Pareto 图'
                                         if fractional else '效应绝对值 Pareto 图')
                self.plot_factorial_residuals(
                    [axes[1, 1], axes[1, 2], axes[0, 2]], r)
                viewer.fig.suptitle(f"响应 {r['response']}：上次分析快照，数据修改后请重新分析",
                                    fontproperties=font)
                for axis in axes.flat:
                    axis.title.set_fontproperties(font)
                    axis.xaxis.label.set_fontproperties(font)
                    axis.yaxis.label.set_fontproperties(font)
                    for label in axis.texts:
                        label.set_fontproperties(font)
                viewer.fig.tight_layout()
                viewer.canvas.draw()
                self.app.replacePlotViewer(viewer)
                viewer.main.deiconify()
            except Exception:
                viewer.close()
                raise
        except (ValueError, RuntimeError) as exc:
            messagebox.showerror('试验设计', str(exc), parent=self.main)

    def plot_factorial_residuals(self, axes, result):
        from scipy import stats

        residuals = np.asarray(result['residuals'], dtype=float)
        fitted = np.asarray(result['fitted'], dtype=float)
        axes[0].scatter(fitted, residuals)
        axes[0].axhline(0, color='black')
        axes[0].set_title('残差与拟合值')
        axes[0].set_xlabel('拟合值')
        axes[0].set_ylabel('残差')

        if len(residuals) > 1:
            (quantiles, ordered), _ = stats.probplot(residuals, dist='norm')
            axes[1].scatter(quantiles, ordered)
            axes[1].set_xlabel('正态理论分位数')
            axes[1].set_ylabel('残差')
        axes[1].set_title('残差正态概率图')

        runs = result['design'].runs
        run_order = np.asarray([run.run_order for run in runs])
        order = np.argsort(run_order, kind='stable')
        axes[2].scatter(run_order[order], residuals[order])
        axes[2].axhline(0, color='black')
        axes[2].set_title('残差与实际运行顺序')
        axes[2].set_xlabel('运行序')
        axes[2].set_ylabel('残差')

    def plot_general_factorial(self, result):
        factors = result['design'].spec.factors
        factor_by_id = {factor.factor_id: factor for factor in factors}
        first_id, second_id = self.factor_x.get(), self.factor_y.get()
        if first_id not in factor_by_id:
            raise ValueError('请选择主效应因子。')
        if second_id and (second_id not in factor_by_id or second_id == first_id):
            raise ValueError('交互图需要选择两个不同的因子。')
        viewer = self.app.showPlotViewer(deferred=True, figsize=(12, 8))
        try:
            from chart_style import font_families
            font = font_manager.FontProperties(family=font_families('Microsoft YaHei'))
            axes = viewer.fig.subplots(2, 3)
            first = factor_by_id[first_id]
            first_means = [next(item['mean'] for item in result['marginal_means']
                                if item['factor_id'] == first_id and
                                item['level'] == level)
                           for level in first.levels]
            positions = list(range(len(first.levels)))
            axes[0, 0].plot(positions, first_means, marker='o')
            axes[0, 0].set_xticks(positions, [str(level) for level in first.levels])
            axes[0, 0].set_title(f'{first.name} 主效应图')
            axes[0, 0].set_xlabel('分类水平')
            axes[0, 0].set_ylabel('响应边际均值')

            if second_id:
                second = factor_by_id[second_id]
                cell_means = result['cell_means']
                for second_level in second.levels:
                    means = []
                    for first_level in first.levels:
                        selected = [item['mean'] for item in cell_means
                                    if item['levels'][first_id] == first_level
                                    and item['levels'][second_id] == second_level]
                        means.append(float(np.mean(selected)))
                    axes[0, 1].plot(positions, means, marker='o',
                                    label=f'{second.name}={second_level}')
                axes[0, 1].set_xticks(positions, [str(level) for level in first.levels])
                axes[0, 1].set_title(f'{first.name} × {second.name} 交互作用图')
                axes[0, 1].set_xlabel(first.name)
                axes[0, 1].set_ylabel('响应均值')
                axes[0, 1].legend(prop=font)
            else:
                axes[0, 1].axis('off')

            effects = [row for row in result['anova']
                       if row['term'] not in ('区组', '误差', '总计')]
            effects.sort(key=lambda row: row['ss'])
            axes[0, 2].barh([row['term'] for row in effects], [row['ss'] for row in effects])
            axes[0, 2].set_title('模型项偏平方和')
            axes[0, 2].set_xlabel('偏平方和')
            self.plot_factorial_residuals(axes[1], result)
            viewer.fig.suptitle('一般全因子分类模型', fontproperties=font)
            for axis in axes.flat:
                axis.title.set_fontproperties(font)
                axis.xaxis.label.set_fontproperties(font)
                axis.yaxis.label.set_fontproperties(font)
                for label in (*axis.get_xticklabels(), *axis.get_yticklabels()):
                    label.set_fontproperties(font)
            viewer.fig.tight_layout()
            viewer.canvas.draw()
            self.app.replacePlotViewer(viewer)
            viewer.main.deiconify()
        except Exception:
            viewer.close()
            raise

    def plot_screening_effects(self, axis, result):
        from scipy import stats
        inf = result['inference']
        lenth = result.get('lenth')
        if self.dsd and inf is None:
            axis.text(.5, .5, '标准化效应不可用', ha='center')
            return
        values = [(name, float(inf['t'][i]) if inf else float(effect))
                  for i, (name, effect) in enumerate(zip(result['names'], result['effects']))
                  if (self.dsd and i in result['effect_indices'] and inf is not None and np.isfinite(inf['t'][i])) or
                     (not self.dsd and effect is not None)]
        if not values:
            axis.text(.5, .5, '没有可绘制的效应', ha='center')
            return
        margin = (float(stats.t.ppf(.975, result['df'])) if inf else
                  lenth['margin'] if lenth else None)
        scale = '标准化效应' if inf else '效应'
        mode = self.effect_plot.get()
        if mode == 'Pareto':
            values.sort(key=lambda item: abs(item[1]))
            axis.barh([item[0] for item in values], [abs(item[1]) for item in values])
            if len(values) > 20:
                axis.tick_params(axis='y', labelsize=max(4, 220 / len(values)))
            if margin is not None:
                axis.axvline(margin, color='red', linestyle='--')
            axis.set_title(f'{scale} Pareto 图')
        elif mode in ('正态', '半正态'):
            data = sorted(abs(value) if mode == '半正态' else value for _, value in values)
            probabilities = (np.arange(len(data)) + .5) / len(data)
            scores = stats.norm.ppf((1 + probabilities) / 2 if mode == '半正态' else probabilities)
            axis.scatter(data, scores)
            reference_scale = 1 if inf else lenth['pse'] if lenth else None
            if reference_scale:
                limits = [min(data), max(data)]
                axis.plot(limits, np.asarray(limits) / reference_scale, color='black', linewidth=1)
            if margin is not None:
                axis.axvline(margin, color='red', linestyle='--')
                if mode == '正态':
                    axis.axvline(-margin, color='red', linestyle='--')
            axis.set_title(f'{scale}{mode}图')
            axis.set_ylabel('正态分位数')
        else:
            raise ValueError('请选择有效的效应图类型。')

    def plot_dsd(self, result):
        from scipy import stats
        from chart_style import font_families
        font = font_manager.FontProperties(family=font_families('Microsoft YaHei'))
        viewer = self.app.showPlotViewer(deferred=True, figsize=(10, 8))
        try:
            axes = viewer.fig.subplots(2, 2)
            y = np.array([run.responses[result['response']] for run in result['design'].runs], dtype=float)
            selected = {self.factor_x.get(), self.factor_y.get()}
            if (len(result['design'].spec.factors) > 10 and
                    (len(selected) != 2 or not selected <= {f.factor_id for f in result['design'].spec.factors})):
                raise ValueError('请选择两个不同的因子。')
            for i, factor in enumerate(result['design'].spec.factors):
                if len(result['design'].spec.factors) > 10 and factor.factor_id not in selected:
                    continue
                levels = (-1, 1) if factor.factor_type == 'categorical' else (-1, 0, 1)
                means = [y[result['coded'][:, i] == level].mean() for level in levels]
                label = factor.name + (f' ({factor.levels[0]} / {factor.levels[1]})'
                                       if factor.factor_type == 'categorical' else '')
                axes[0, 0].plot(levels, means, marker='o', label=label)
            axes[0, 0].set_title('所选因子的主效应条件均值' if len(result['design'].spec.factors) > 10 else '主效应条件均值')
            axes[0, 0].legend(prop=font)
            self.plot_screening_effects(axes[0, 1], result)
            if result['inference'] is None:
                for axis in axes[1]:
                    axis.text(.5, .5, '残差诊断不可用', ha='center')
            else:
                axes[1, 0].scatter(result['fitted'], result['residuals'])
                axes[1, 0].axhline(0, color='black')
                axes[1, 0].set_title('残差与拟合值')
                (quantiles, ordered), _ = stats.probplot(result['residuals'], dist='norm')
                axes[1, 1].scatter(quantiles, ordered)
                axes[1, 1].set_title('残差正态概率图')
            for axis in axes.flat:
                axis.title.set_fontproperties(font)
                axis.xaxis.label.set_fontproperties(font)
                axis.yaxis.label.set_fontproperties(font)
                for text in axis.texts:
                    text.set_fontproperties(font)
            viewer.fig.tight_layout()
            viewer.canvas.draw()
            self.app.replacePlotViewer(viewer)
            viewer.main.deiconify()
        except Exception:
            viewer.close()
            raise

    def plot_split_plot(self, result):
        design = result['design']
        factors = design.spec.factors
        hard = next(factor for factor in factors
                    if factor.randomization_role == 'hard_to_change')
        easy = next(factor for factor in factors
                    if factor.randomization_role == 'easy_to_change')
        runs = design.runs
        y = np.asarray([run.responses[result['response']] for run in runs], dtype=float)
        coded_hard = np.asarray([hard.to_coded(run.settings[hard.factor_id]) for run in runs])
        coded_easy = np.asarray([easy.to_coded(run.settings[easy.factor_id]) for run in runs])
        viewer = self.app.showPlotViewer(deferred=True, figsize=(10, 7))
        try:
            from chart_style import font_families
            font = font_manager.FontProperties(family=font_families('Microsoft YaHei'))
            axes = viewer.fig.subplots(2, 3)
            hard_means = [float(y[coded_hard == level].mean()) for level in (-1, 1)]
            easy_means = [float(y[coded_easy == level].mean()) for level in (-1, 1)]
            axes[0, 0].plot([hard.low, hard.high], hard_means, marker='o')
            axes[0, 0].set_title(f'{hard.name} 整区主效应')
            axes[0, 0].set_xlabel('Hard-to-change 因子水平')
            axes[0, 1].plot([easy.low, easy.high], easy_means, marker='o')
            axes[0, 1].set_title(f'{easy.name} 子区主效应')
            axes[0, 1].set_xlabel('Easy-to-change 因子水平')
            for easy_level in (-1, 1):
                means = [float(y[(coded_hard == hard_level)
                                 & (coded_easy == easy_level)].mean())
                         for hard_level in (-1, 1)]
                axes[1, 0].plot([hard.low, hard.high], means, marker='o',
                                label=f'{easy.name}={easy.low if easy_level == -1 else easy.high}')
            axes[1, 0].set_title(f'{hard.name} × {easy.name} 交互作用')
            axes[1, 0].legend(prop=font)
            self.plot_factorial_residuals(
                [axes[1, 1], axes[1, 2], axes[0, 2]], result)
            viewer.fig.suptitle(f"响应 {result['response']}：整区/子区描述图",
                                fontproperties=font)
            for axis in axes.flat:
                axis.title.set_fontproperties(font)
                axis.xaxis.label.set_fontproperties(font)
                axis.yaxis.label.set_fontproperties(font)
            viewer.fig.tight_layout()
            viewer.canvas.draw()
            self.app.replacePlotViewer(viewer)
            viewer.main.deiconify()
        except Exception:
            viewer.close()
            raise

    def plot_rsm(self, result, first, second):
        from scipy import stats
        factors = result['design'].spec.factors
        spec = result['design'].spec
        if (first == second or not 0 <= first < len(factors)
                or not 0 <= second < len(factors)
                or factors[first].factor_type != 'continuous'
                or factors[second].factor_type != 'continuous'):
            raise ValueError('响应面绘图需要选择两个不同的连续因子。')
        if spec.design_type == 'central_composite':
            alpha = spec.ccd_alpha
        else:
            # 自定义响应面：轴点范围取实际编码最大值，不使用未声明的 alpha。
            from doe_custom import coded_value
            alpha = max([1.0] + [
                abs(coded_value(factor, run.settings[factor.factor_id],
                                run.point_type))
                for factor in factors if factor.factor_type == 'continuous'
                for run in result['design'].runs if run.point_type == 'axial'])
        axis_ids = {factors[first].factor_id, factors[second].factor_id}
        fixed_continuous = {}
        categorical = {}
        for factor in factors:
            control = self.fixed[factor.factor_id]
            if factor.factor_type == 'categorical':
                level = control.get()
                if level not in factor.levels:
                    raise ValueError(f'分类因子 {factor.factor_id} 必须选择已声明水平。')
                categorical[factor.factor_id] = level
            elif factor.factor_id not in axis_ids:
                try:
                    value = float(control.get())
                except (TypeError, ValueError) as error:
                    raise ValueError(f'因子 {factor.factor_id} 固定值必须是有限数值。') from error
                if not np.isfinite(value) or abs(value) > alpha:
                    raise ValueError('固定编码水平必须位于轴点范围内')
                fixed_continuous[factor.factor_id] = value
        axis = np.linspace(-alpha, alpha, 50)
        xx, yy = np.meshgrid(axis, axis)
        model = result['term_model']
        block = result['blocks'][0] if model.blocks and result['blocks'] else None
        rows = []
        for x_value, y_value in zip(xx.ravel(), yy.ravel()):
            values = dict(fixed_continuous)
            values[factors[first].factor_id] = x_value
            values[factors[second].factor_id] = y_value
            values.update(categorical)
            rows.append(model.row(values, block))
        zz = (np.vstack(rows) @ result['coefficients']).reshape(xx.shape)
        viewer = self.app.showPlotViewer(deferred=True, figsize=(10, 8))
        try:
            contour = viewer.fig.add_subplot(221)
            surface = viewer.fig.add_subplot(222, projection='3d')
            residual = viewer.fig.add_subplot(223)
            normal = viewer.fig.add_subplot(224)
            contour.contourf(xx, yy, zz, levels=15)
            fixed_outside = any(abs(value) > 1 for value in fixed_continuous.values())
            outside = (abs(xx) > 1) | (abs(yy) > 1) | fixed_outside
            if spec.design_type == 'central_composite' and alpha > 1:
                outside |= (xx**2 + yy**2 > alpha**2)
            if outside.any():
                contour.contourf(xx, yy, outside.astype(float), levels=[.5, 1.5],
                                 colors='none', hatches=['///'])
            if alpha > 1:
                from matplotlib.patches import Rectangle
                contour.add_patch(Rectangle((-1, -1), 2, 2, fill=False,
                                            color='white', linestyle='--'))
            contour.set_title('等高线（斜线为因子点范围外）')
            surface.plot_surface(xx, yy, np.where(outside, np.nan, zz), cmap='viridis')
            if outside.any():
                surface.plot_surface(xx, yy, np.where(outside, zz, np.nan),
                                     color='indianred', alpha=.55)
            surface.set_title('响应面（红色为因子点范围外）')
            for ax in (contour, surface):
                ax.set_xlabel(factors[first].factor_id)
                ax.set_ylabel(factors[second].factor_id)
            residual.scatter(result['fitted'], result['residuals'])
            residual.axhline(0, color='black')
            residual.set_title('残差与拟合值')
            stats.probplot(result['residuals'], dist='norm', plot=normal)
            normal.set_title('残差正态概率图')
            normal.set_xlabel('理论分位数')
            normal.set_ylabel('残差分位数')
            fixed_text = ', '.join(
                f'{factor_id}={value:g}'
                for factor_id, value in fixed_continuous.items()) or '无'
            categories_text = ', '.join(
                f'{factor.factor_id}={categorical[factor.factor_id]}'
                for factor in factors if factor.factor_type == 'categorical')
            title = [f"响应 {result['response']}",
                     f'{factors[first].factor_id} × {factors[second].factor_id}',
                     f'固定连续编码 {fixed_text}']
            if categories_text:
                title.append(f'分类水平 {categories_text}')
            if block is not None:
                title.append(f'参考区组={block}')
            title.append('分析快照')
            from chart_style import font_families
            font = font_manager.FontProperties(family=font_families('Microsoft YaHei'))
            viewer.fig.suptitle('；'.join(title), fontproperties=font)
            for ax in (contour, surface, residual, normal):
                ax.title.set_fontproperties(font)
                ax.xaxis.label.set_fontproperties(font)
                ax.yaxis.label.set_fontproperties(font)
            viewer.fig.tight_layout()
            viewer.canvas.draw()
            self.app.replacePlotViewer(viewer)
            viewer.main.deiconify()
        except Exception:
            viewer.close()
            raise
