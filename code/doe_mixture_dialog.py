"""混料设计创建、分析、预测、优化与图形界面。"""
from __future__ import annotations

import math
import re
import tkinter as tk
from copy import deepcopy
from tkinter import messagebox, ttk

import numpy as np
import pandas as pd
from matplotlib import font_manager

from doe_mixture import MixtureSpec, mixture_model_config, restore_mixture_model
from doe_mixture_analysis import analyze_mixture
from doe_mixture_constraints import (
    ComponentSpec, LinearConstraint, MixtureConstraintError, VariableSpec,
)
from doe_mixture_designs import create_mixture_design
from doe_mixture_optimize import optimize_mixture
from doe_mixture_plots import (grid_triangulation, overlay_grid, simplex_grid,
                               ternary_xy, trace_series)
from doe_mixture_predict import predict_mixture
from doe_augment import augment_mixture
from doe_mixture_improvement import improve_mixture_design
from help_link import open_help
from doe_optimal_design import evaluate_mixture_design, select_mixture_optimal
from sheet_context import SheetApp
from stat_table import StatTable, TableBlock


_TYPES = {'Simplex Lattice': 'simplex_lattice',
          'Simplex Centroid': 'simplex_centroid',
          'Extreme Vertices': 'extreme_vertices'}


def _number(text, label):
    try:
        value = float(str(text).strip())
    except (TypeError, ValueError) as error:
        raise ValueError(f'{label} 必须是有限数值') from error
    if not math.isfinite(value):
        raise ValueError(f'{label} 必须是有限数值')
    return value


def _scrollable(main, height=520):
    area = ttk.Frame(main)
    area.pack(fill='both', expand=True)
    canvas = tk.Canvas(area, highlightthickness=0, height=height)
    scrollbar = ttk.Scrollbar(area, orient='vertical', command=canvas.yview)
    canvas.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side='right', fill='y')
    canvas.pack(side='left', fill='both', expand=True)
    grid = ttk.Frame(canvas, padding=8)
    window = canvas.create_window((0, 0), window=grid, anchor='nw')
    grid.bind('<Configure>', lambda event: canvas.configure(scrollregion=canvas.bbox('all')))
    canvas.bind('<Configure>', lambda event: canvas.itemconfigure(window, width=event.width))
    return area, grid


def _equal_proportions(count):
    values = [1 / count] * (count - 1)
    values.append(1 - sum(values))
    return [f'{value:.17g}' for value in values]


def _parse_constraints(text, component_ids):
    result = []
    for item in text.split(';'):
        item = item.strip()
        if not item:
            continue
        if '<=' not in item:
            raise ValueError('线性约束格式为 系数*组分+...<=数值，用分号分隔')
        left, right = item.split('<=', 1)
        try:
            bound = float(right.strip())
        except ValueError as error:
            raise ValueError('线性约束右端必须是数值') from error
        if not math.isfinite(bound):
            raise ValueError('线性约束右端必须是有限数值')
        coefficients = {}
        position = 0
        normalized = left.replace(' ', '')
        for match in re.finditer(r'([+-]?)(\d*\.?\d*)\*?([A-Za-z][A-Za-z0-9_.-]*)', normalized):
            if match.start() != position:
                raise ValueError('线性约束含无法解析的部分')
            position = match.end()
            sign = -1 if match.group(1) == '-' else 1
            coefficient = float(match.group(2)) if match.group(2) else 1.0
            component_id = match.group(3)
            if component_id not in component_ids:
                raise ValueError(f'线性约束含未知组分：{component_id}')
            coefficients[component_id] = coefficients.get(component_id, 0.0) + sign * coefficient
        if position != len(normalized) or not coefficients:
            raise ValueError('线性约束含无法解析的部分')
        result.append(LinearConstraint(coefficients, bound))
    return tuple(result)


class CreateMixtureDesign:
    """创建三类混料设计；预览不写工作簿，取消不产生副作用。"""

    def __init__(self, app):
        self.app = app
        self.main = tk.Toplevel(app.main)
        self.main.title('创建混料设计')
        self.main.bind('<F1>', lambda event: open_help('doe.mixture', parent=self.main))
        area, grid = _scrollable(self.main)
        self.grid = grid
        ttk.Label(grid, text='设计类型').grid(row=0, column=0, sticky='w')
        self.kind = ttk.Combobox(grid, values=tuple(_TYPES), state='readonly', width=20)
        self.kind.set('Simplex Lattice')
        self.kind.grid(row=0, column=1, columnspan=2, sticky='w')
        self.kind.bind('<<ComboboxSelected>>', self.update_rows)
        ttk.Label(grid, text='组分数').grid(row=0, column=3, sticky='w')
        self.count = ttk.Combobox(grid, values=tuple(range(2, 13)), state='readonly', width=4)
        self.count.set('3')
        self.count.grid(row=0, column=4, sticky='w')
        self.count.bind('<<ComboboxSelected>>', self.update_rows)
        ttk.Label(grid, text='阶数').grid(row=0, column=5, sticky='w')
        self.degree = ttk.Combobox(grid, values=tuple(range(1, 11)), state='readonly', width=4)
        self.degree.set('2')
        self.degree.grid(row=0, column=6, sticky='w')
        headers = ('组分', '名称', '下界', '上界')
        for column, label in enumerate(headers):
            ttk.Label(grid, text=label).grid(row=1, column=column, padx=3)
        self.components = []
        for index in range(12):
            component_id = chr(65 + index)
            ttk.Label(grid, text=component_id).grid(row=index + 2, column=0)
            fields = []
            for column, value in enumerate((component_id, '0', '1'), start=1):
                entry = ttk.Entry(grid, width=14)
                entry.insert(0, value)
                entry.grid(row=index + 2, column=column, padx=3, pady=2)
                fields.append(entry)
            self.components.append(fields)
        row = 2 + len(self.components)
        ttk.Label(grid, text='线性约束').grid(row=row, column=0, sticky='w')
        self.constraints = ttk.Entry(grid, width=52)
        self.constraints.grid(row=row, column=1, columnspan=6, sticky='ew', pady=2)
        ttk.Label(grid, text='如 A+B<=0.75; A-B<=0.2').grid(row=row + 1, column=1, columnspan=6, sticky='w')
        row += 2
        ttk.Label(grid, text='过程变量数').grid(row=row, column=0, sticky='w')
        self.process_count = ttk.Combobox(grid, values=(0, 1, 2, 3), state='readonly', width=4)
        self.process_count.set('0')
        self.process_count.grid(row=row, column=1, sticky='w')
        self.process_count.bind('<<ComboboxSelected>>', self.update_rows)
        row += 1
        for column, label in enumerate(('过程变量', '名称', '低水平', '高水平', '单位')):
            ttk.Label(grid, text=label).grid(row=row, column=column, padx=3)
        self.processes = []
        for index in range(3):
            ttk.Label(grid, text=f'P{index + 1}').grid(row=row + index + 1, column=0)
            fields = []
            for column in range(1, 5):
                entry = ttk.Entry(grid, width=12)
                entry.grid(row=row + index + 1, column=column, padx=3, pady=2)
                fields.append(entry)
            self.processes.append(fields)
        row += 4
        self.amount_enabled = tk.BooleanVar(value=False)
        ttk.Checkbutton(grid, text='总量变量', variable=self.amount_enabled,
                        command=self.update_rows).grid(row=row, column=0, columnspan=2, sticky='w')
        self.amount = {}
        fields = (('name', '名称'), ('low', '低水平'), ('high', '高水平'),
                  ('fixed', '默认设定'), ('level_1', '实际水平 1'),
                  ('level_2', '实际水平 2'), ('level_3', '实际水平 3'), ('unit', '单位'))
        for column, (key, label) in enumerate(fields):
            ttk.Label(grid, text=label).grid(row=row, column=column + 2)
            entry = ttk.Entry(grid, width=10)
            entry.grid(row=row + 1, column=column + 2, padx=3, pady=2)
            if key.startswith('level_'):
                self.amount.setdefault('levels', []).append(entry)
            else:
                self.amount[key] = entry
        self.amount['low'].insert(0, '0')
        self.amount['high'].insert(0, '1')
        self.amount['fixed'].insert(0, '1')
        row += 2
        self.options = {}
        for key, default in (('重复数', '1'), ('随机 seed', '1'), ('响应名称', 'Y')):
            ttk.Label(grid, text=key).grid(row=row, column=0, sticky='w')
            entry = ttk.Entry(grid, width=28)
            entry.insert(0, default)
            entry.grid(row=row, column=1, columnspan=3, sticky='w', pady=2)
            self.options[key] = entry
            row += 1
        self.preview_text = tk.StringVar(value='')
        ttk.Label(grid, textvariable=self.preview_text, wraplength=760).grid(
            row=row, column=0, columnspan=7, sticky='ew')
        bar = ttk.Frame(self.main)
        bar.pack(side='bottom', fill='x', padx=8, pady=8, before=area)
        ttk.Button(bar, text='预览', command=self.preview).pack(side='left')
        ttk.Button(bar, text='创建', command=self.create).pack(side='left', padx=4)
        ttk.Button(bar, text='取消', command=self.main.destroy).pack(side='left')
        self.main.geometry('900x620')
        self.update_rows()

    def update_rows(self, event=None):
        count = int(self.count.get())
        for index, fields in enumerate(self.components):
            for field in fields:
                field.grid() if index < count else field.grid_remove()
        self.degree.configure(state='readonly' if self.kind.get() == 'Simplex Lattice' else 'disabled')
        process_count = int(self.process_count.get())
        for index, fields in enumerate(self.processes):
            for field in fields:
                field.grid() if index < process_count else field.grid_remove()
        for field in (field for value in self.amount.values()
                      for field in (value if isinstance(value, list) else [value])):
            field.configure(state='normal' if self.amount_enabled.get() else 'disabled')

    def build(self):
        design_type = _TYPES[self.kind.get()]
        count = int(self.count.get())
        components = []
        for index, fields in enumerate(self.components[:count]):
            name, lower, upper = (field.get().strip() for field in fields)
            if not name:
                raise ValueError(f'组分 {chr(65 + index)} 名称不能为空')
            components.append(ComponentSpec(chr(65 + index), name,
                                            _number(lower, '组分下界'),
                                            _number(upper, '组分上界')))
        process = []
        for index, fields in enumerate(self.processes[:int(self.process_count.get())]):
            name, low, high, unit = (field.get().strip() for field in fields)
            if not name:
                raise ValueError(f'过程变量 P{index + 1} 名称不能为空')
            process.append(VariableSpec(f'P{index + 1}', name,
                                        _number(low, '过程变量低水平'),
                                        _number(high, '过程变量高水平'), unit or None))
        amount = []
        settings = ()
        if self.amount_enabled.get():
            name = self.amount['name'].get().strip()
            if not name:
                raise ValueError('总量变量名称不能为空')
            low = _number(self.amount['low'].get(), '总量低水平')
            high = _number(self.amount['high'].get(), '总量高水平')
            fixed = _number(self.amount['fixed'].get(), '总量设计设定')
            level_text = [field.get().strip() for field in self.amount['levels']]
            filled = [index for index, value in enumerate(level_text) if value]
            if filled and filled != list(range(filled[-1] + 1)):
                raise ValueError('实际总量水平请从水平 1 起连续填写')
            amount_levels = (None if not filled else
                             tuple(_number(level_text[index], '总量水平')
                                   for index in filled))
            amount = [VariableSpec('T', name, low, high,
                                   self.amount['unit'].get().strip() or None, 'amount')]
            if not low <= fixed <= high:
                raise ValueError('总量设计设定必须位于低水平与高水平之间')
            settings = (('T', fixed),)
        else:
            amount_levels = None
        constraints = _parse_constraints(self.constraints.get(),
                                         tuple(item.component_id for item in components))
        responses = tuple(item.strip() for item in self.options['响应名称'].get().split(','))
        spec = MixtureSpec('MIX', tuple(components), responses, design_type,
                           int(self.degree.get()) if design_type == 'simplex_lattice' else None,
                           tuple(process), tuple(amount), settings, constraints,
                           int(self.options['随机 seed'].get()),
                           construction_version='v2' if amount_levels is not None else 'v1')
        return spec, int(self.options['重复数'].get()), amount_levels

    def preview(self):
        try:
            spec, replicates, amount_levels = self.build()
            frame, _ = create_mixture_design(spec, replicates,
                                             amount_levels=amount_levels)
            counts = frame['点类型'].value_counts()
            self.preview_text.set(
                f'{len(frame)} 次运行；点类型 ' +
                '，'.join(f'{key} {value}' for key, value in counts.items()) +
                '；每个点总和为 1')
            window = tk.Toplevel(self.main)
            window.title('混料设计预览')
            window.geometry('900x460')
            tree = ttk.Treeview(window, columns=tuple(frame.columns), show='headings')
            vertical = ttk.Scrollbar(window, orient='vertical', command=tree.yview)
            horizontal = ttk.Scrollbar(window, orient='horizontal', command=tree.xview)
            tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
            vertical.pack(side='right', fill='y')
            horizontal.pack(side='bottom', fill='x')
            tree.pack(fill='both', expand=True)
            for name in frame.columns:
                tree.heading(name, text=str(name))
                tree.column(name, width=90, minwidth=60, stretch=False)
            for row in frame.head(100).itertuples(index=False, name=None):
                tree.insert('', 'end', values=tuple('' if pd.isna(value) else value
                                                    for value in row))
        except (ValueError, TypeError, OverflowError) as exc:
            messagebox.showerror('混料设计', str(exc), parent=self.main)

    def create(self):
        try:
            spec, replicates, amount_levels = self.build()
            frame, meta = create_mixture_design(spec, replicates,
                                                amount_levels=amount_levels)
            self.app.addSheet('混料设计', frame, meta)
        except (ValueError, TypeError, OverflowError) as exc:
            messagebox.showerror('混料设计', str(exc), parent=self.main)
            return
        self.main.destroy()


def _source(app):
    source = app.getCurrentTable()
    metadata = getattr(source, 'mixture_metadata', None)
    if not metadata:
        raise MixtureConstraintError('当前工作表不是混料设计。')
    return source, metadata


def _saved_model(source, frame, metadata):
    config = getattr(source, 'mixture_model', None)
    if config is None:
        return 2, None
    _, degree, terms = restore_mixture_model(
        frame, metadata, config, getattr(source, 'doe_metadata', None))
    return degree, terms


class _ResultWindow:
    def __init__(self, app, source, title):
        self.owner = app
        self.source = source
        self.metadata = getattr(source, 'mixture_metadata', None)
        self.app = SheetApp(app, source)
        self.main = tk.Toplevel(app.main)
        self.main.title(title)
        self.tabs = ttk.Notebook(self.main)
        self.tabs.pack(fill='both', expand=True, padx=8, pady=8)
        self.main.geometry('920x620')

    def show_table(self, title, headers, values):
        tab = ttk.Frame(self.tabs)
        self.tabs.add(tab, text=title)
        table = StatTable(title=title, headers=headers, values=values)
        TableBlock(tab, table, paginate=True).pack(fill='both', expand=True)
        self.app.print(table)

    def clear(self):
        for tab in self.tabs.tabs():
            self.tabs.nametowidget(tab).destroy()

    def verify_source(self):
        self.owner._finish_edit()
        if self.owner.getCurrentTable() is not self.source:
            raise ValueError('来源工作表已切换，请切回后重试。')
        return self.owner._full_frame(self.source).copy(deep=True)


class AnalyzeMixtureDesign(_ResultWindow):
    def __init__(self, app):
        try:
            source, metadata = _source(app)
        except MixtureConstraintError as exc:
            messagebox.showerror('混料分析', str(exc), parent=app.main)
            return
        self.metadata = metadata
        super().__init__(app, source, '分析混料设计')
        self.main.bind('<F1>', lambda event: open_help('doe.mixture.analysis', parent=self.main))
        controls = ttk.Frame(self.main)
        controls.pack(fill='x', padx=8, before=self.tabs)
        ttk.Label(controls, text='响应').pack(side='left')
        names = metadata['spec']['response_names']
        self.response = ttk.Combobox(controls, values=names, state='readonly', width=14)
        self.response.set(names[0])
        self.response.pack(side='left', padx=4)
        ttk.Label(controls, text='模型阶次').pack(side='left')
        self.degree = ttk.Combobox(controls, values=(1, 2, 3), state='readonly', width=4)
        self.degree.set('2')
        self.degree.pack(side='left', padx=4)
        ttk.Label(controls, text='模型项').pack(side='left')
        self.terms = ttk.Entry(controls, width=30)
        self.terms.pack(side='left', padx=4)
        ttk.Button(controls, text='分析', command=self.analyze).pack(side='left')
        ttk.Button(controls, text='关闭', command=self.main.destroy).pack(side='right')
        self.status = tk.StringVar(value='')
        ttk.Label(self.main, textvariable=self.status).pack(fill='x', padx=8)
        self.result = None
        saved = getattr(source, 'mixture_model', None)
        if saved is not None:
            try:
                response, degree, terms = restore_mixture_model(
                    self.owner._full_frame(source), self.metadata, saved,
                    source.doe_metadata)
            except ValueError:
                saved = None
            else:
                self.response.set(response)
                self.degree.set(str(degree))
                self.terms.insert(0, ';'.join(terms))

    def analyze(self):
        try:
            frame = self.verify_source()
            terms = tuple(item.strip() for item in self.terms.get().split(';')
                          if item.strip()) or None
            result = analyze_mixture(frame, self.metadata, self.response.get(),
                                     terms, int(self.degree.get()),
                                     doe_metadata=self.source.doe_metadata)
            self.publish(result)
            self.analysis_frame = frame
            self.source.mixture_model = mixture_model_config(
                frame, self.metadata, self.response.get(), int(self.degree.get()),
                result['terms'], self.source.doe_metadata)
        except (ValueError, TypeError, OverflowError) as exc:
            self.status.set('分析失败：' + str(exc))
            messagebox.showerror('混料分析', str(exc), parent=self.main)

    def publish(self, result):
        self.clear()
        self.status.set(f"响应 {result['response']}，{result['n']} 行；{result['status']}；"
                        '项平方和为删除项条件检验，混料组分主项不报告独立主效应 p 值；'
                        + result['assumption'])
        inf = result['inference']
        rows = []
        for index, name in enumerate(result['names']):
            p_value = (None if inf is None or inf['p'][index] is None
                       or not np.isfinite(inf['p'][index]) else float(inf['p'][index]))
            rows.append([name, result['coefficients'][index],
                         inf['se'][index] if inf else None,
                         inf['t'][index] if inf else None, p_value,
                         inf['ci_low'][index] if inf else None,
                         inf['ci_high'][index] if inf else None])
        self.show_table('系数（组分主项 p 不报告）',
                        ['项', '系数', 'SE', 't', 'p', 'CI低', 'CI高'], rows)
        self.show_table('模型', ['n', '项数', '秩', '条件数', '模型自由度', '残差自由度', 'SSE', 'SST', 'SSR',
                                '纯误差自由度', '纯误差平方和', '失拟自由度',
                                '失拟平方和', 'R²', '调整R²', 'F', '模型p'], [[
            result['n'], result['p'], result['rank'], result['condition_number'],
            result['model_df'], result['df'],
            result['sse'],
            result['sst'], result['ssr'], result['pure_error_df'],
            result['pure_error_sse'], result['lack_of_fit_df'],
            result['lack_of_fit_sse'], result['r2'], result['adjusted_r2'],
            inf['f'] if inf else None, inf['model_p'] if inf else None]])
        self.show_table('删除项条件平方和', ['来源', '平方和', '自由度', '均方', 'F', 'p'], [
            [row['source'], row['ss'], row['df'], row['ms'], row['f'], row['p']]
            for row in result['anova']])
        lof = result['lack_of_fit']
        self.show_table('纯误差与失拟', ['来源', '平方和', '自由度', 'F', 'p'], [
            ['纯误差', result['pure_error_sse'], result['pure_error_df'], None, None],
            ['失拟', result['lack_of_fit_sse'], result['lack_of_fit_df'],
             lof['f'] if lof else None, lof['p'] if lof else None]])
        self.show_table('拟合与残差', ['运行ID', '响应', '拟合值', '残差'], [
            [item['run_id'], item['row'][f'响应_{result["response"]}'],
             result['fitted'][index], result['residuals'][index]]
            for index, item in enumerate(result['rows'])])
        if result['rank'] < result['p']:
            self.show_table('可估计性', ['项', '状态'], [
                [name, '可估计' if result['estimable'][index] else '不可单独估计']
                for index, name in enumerate(result['names'])])
        self.result = result


class PredictMixture(_ResultWindow):
    def __init__(self, app):
        try:
            source, metadata = _source(app)
        except MixtureConstraintError as exc:
            messagebox.showerror('混料预测', str(exc), parent=app.main)
            return
        super().__init__(app, source, '混料预测')
        self.main.bind('<F1>', lambda event: open_help('doe.mixture.predict', parent=self.main))
        controls = ttk.Frame(self.main)
        controls.pack(fill='x', padx=8, before=self.tabs)
        names = metadata['spec']['response_names']
        self.response = ttk.Combobox(controls, values=names, state='readonly', width=12)
        self.response.set(names[0])
        self.response.pack(side='left')
        ttk.Label(controls, text='置信度').pack(side='left', padx=(10, 3))
        self.confidence = ttk.Combobox(
            controls, values=('90%', '95%', '99%'), state='readonly', width=6)
        self.confidence.set('95%')
        self.confidence.pack(side='left')
        ttk.Button(controls, text='预测', command=self.predict).pack(side='left', padx=8)
        ttk.Button(controls, text='关闭', command=self.main.destroy).pack(side='right')
        inputs = ttk.Frame(self.main)
        inputs.pack(fill='x', padx=8, pady=4, before=self.tabs)
        self.entries = {}
        q = len(metadata['spec']['components'])
        starting = _equal_proportions(q)
        for component, value in zip(metadata['spec']['components'], starting):
            ttk.Label(inputs, text=component['component_id']).pack(side='left')
            entry = ttk.Entry(inputs, width=7)
            entry.insert(0, value)
            entry.pack(side='left', padx=2)
            self.entries[component['component_id']] = entry
        for variable in metadata['spec']['process_variables']:
            ttk.Label(inputs, text=variable['variable_id']).pack(side='left')
            entry = ttk.Entry(inputs, width=7)
            entry.insert(0, f'{(variable["low"] + variable["high"]) / 2:.6g}')
            entry.pack(side='left', padx=2)
            self.entries[variable['variable_id']] = entry
        for variable in metadata['spec']['amount_variables']:
            ttk.Label(inputs, text=variable['variable_id']).pack(side='left')
            entry = ttk.Entry(inputs, width=8)
            entry.insert(0, f'{metadata["spec"]["amount_settings"][variable["variable_id"]]:.6g}')
            entry.pack(side='left', padx=2)
            self.entries[variable['variable_id']] = entry
        self.status = tk.StringVar(value='')
        ttk.Label(self.main, textvariable=self.status).pack(fill='x', padx=8)

    def predict(self):
        try:
            frame = self.verify_source()
            spec = self.metadata['spec']
            proportions = {item['component_id']:
                           _number(self.entries[item['component_id']].get(), '组分比例')
                           for item in spec['components']}
            process = {item['variable_id']:
                       _number(self.entries[item['variable_id']].get(), '过程变量')
                       for item in spec['process_variables']}
            amount = {item['variable_id']:
                      _number(self.entries[item['variable_id']].get(), '总量')
                      for item in spec['amount_variables']}
            degree, terms = _saved_model(self.source, frame, self.metadata)
            result = predict_mixture(frame, self.metadata, self.response.get(),
                                     proportions, process, amount, terms, degree,
                                     doe_metadata=self.source.doe_metadata,
                                     confidence=float(self.confidence.get().rstrip('%')) / 100)
            self.clear()
            self.status.set(result['note'] + '；' + result['status'])
            self.show_table('预测', ['响应', '预测值', '模型快照', '状态'], [[
                result['response'], result['prediction'], result['snapshot_id'],
                result['status']]])
            interval = result['intervals']
            fmt = lambda value: '—' if value is None else f'{value:.10g}'
            bounds = lambda low, high: (f'[{fmt(low)}, {fmt(high)}]'
                                        if interval['status'] == '可用' else '—')
            self.show_table('预测区间', ['区间', '结果'], [
                [f"{interval['confidence']:.0%} 均值 CI",
                 bounds(interval['ci_low'], interval['ci_high'])],
                [f"{interval['confidence']:.0%} 单次观测 PI",
                 bounds(interval['pi_low'], interval['pi_high'])],
                ['状态', interval['reason'] or
                 f"可用；df={interval['df']}；置信度={interval['confidence']:.0%}；"
                 + interval['assumption']],
            ])
            self.show_table('实际条件', ['项', '值'], [
                [key, value] for key, value in result['settings'].items()])
            if result['actual_amounts'] is not None:
                self.show_table('实际组分用量', ['组分', '用量'], [
                    [key, value] for key, value in result['actual_amounts'].items()])
            self.show_table('模型范围', ['组分', '下界', '上界'], [
                [key, bounds[0], bounds[1]] for key, bounds in result['model_range'].items()])
        except (ValueError, TypeError, OverflowError) as exc:
            messagebox.showerror('混料预测', str(exc), parent=self.main)


class OptimizeMixture(_ResultWindow):
    def __init__(self, app):
        try:
            source, metadata = _source(app)
        except MixtureConstraintError as exc:
            messagebox.showerror('混料优化', str(exc), parent=app.main)
            return
        super().__init__(app, source, '优化混料响应')
        self.main.bind('<F1>', lambda event: open_help('doe.mixture.optimize', parent=self.main))
        controls = ttk.Frame(self.main)
        controls.pack(fill='x', padx=8, before=self.tabs)
        self.rows = []
        frame = app._full_frame(source)
        ttk.Label(controls, text='响应').grid(row=0, column=0, sticky='w')
        for column, label in enumerate(('目标', '下限', '上限', '目标值', '权重'), start=1):
            ttk.Label(controls, text=label).grid(row=0, column=column, padx=2)
        for index, name in enumerate(metadata['spec']['response_names']):
            column = f'响应_{name}'
            values = pd.to_numeric(frame[column], errors='coerce').dropna()
            low = float(values.min()) if len(values) else 0.0
            high = float(values.max()) if len(values) else 1.0
            if low == high:
                low, high = low - 1, high + 1
            ttk.Label(controls, text=name).grid(row=index + 1, column=0, sticky='w')
            goal = ttk.Combobox(controls, values=('不优化', '最大化', '最小化', '逼近目标'),
                                state='readonly', width=10)
            goal.set('最大化' if index == 0 else '不优化')
            goal.grid(row=index + 1, column=1, padx=2)
            entries = {}
            for column_index, (key, value) in enumerate((('lower', low), ('upper', high),
                                                         ('target', (low + high) / 2),
                                                         ('weight', 1)), start=2):
                entry = ttk.Entry(controls, width=9)
                entry.insert(0, f'{value:.6g}')
                entry.grid(row=index + 1, column=column_index, padx=2)
                entries[key] = entry
            self.rows.append((name, goal, entries))
        conditions = ttk.Frame(self.main)
        conditions.pack(fill='x', padx=8, pady=4, before=self.tabs)
        self.conditions = {}
        for variable in metadata['spec']['process_variables']:
            ttk.Label(conditions, text=variable['variable_id']).pack(side='left')
            entry = ttk.Entry(conditions, width=8)
            entry.insert(0, f'{(variable["low"] + variable["high"]) / 2:.6g}')
            entry.pack(side='left', padx=3)
            self.conditions[variable['variable_id']] = entry
        for variable in metadata['spec']['amount_variables']:
            ttk.Label(conditions, text=variable['variable_id']).pack(side='left')
            entry = ttk.Entry(conditions, width=8)
            entry.insert(0, f'{metadata["spec"]["amount_settings"][variable["variable_id"]]:.6g}')
            entry.pack(side='left', padx=3)
            self.conditions[variable['variable_id']] = entry
        ttk.Label(conditions, text='置信度').pack(side='left', padx=(8, 3))
        self.confidence = ttk.Combobox(
            conditions, values=('90%', '95%', '99%'), state='readonly', width=6)
        self.confidence.set('95%')
        self.confidence.pack(side='left')
        ttk.Button(conditions, text='优化', command=self.optimize).pack(side='left', padx=8)
        self.status = tk.StringVar(value='')
        ttk.Label(self.main, textvariable=self.status).pack(fill='x', padx=8)

    def optimize(self):
        try:
            frame = self.verify_source()
            goals = {'最大化': 'maximize', '最小化': 'minimize', '逼近目标': 'target'}
            objectives = []
            for name, goal, entries in self.rows:
                if goal.get() == '不优化':
                    continue
                item = {'response': name, 'goal': goals[goal.get()],
                        'lower': _number(entries['lower'].get(), '下限'),
                        'upper': _number(entries['upper'].get(), '上限'),
                        'weight': _number(entries['weight'].get(), '权重')}
                if goal.get() == '逼近目标':
                    item['target'] = _number(entries['target'].get(), '目标值')
                objectives.append(item)
            if not objectives:
                raise ValueError('至少选择一个响应目标')
            conditions = {key: _number(entry.get(), key)
                          for key, entry in self.conditions.items()}
            degree, terms = _saved_model(self.source, frame, self.metadata)
            result = optimize_mixture(frame, self.metadata, objectives, conditions,
                                      terms=terms, degree=degree,
                                      doe_metadata=self.source.doe_metadata,
                                      confidence=float(self.confidence.get().rstrip('%')) / 100)
            self.clear()
            self.status.set(result['status'] + '；' + result['interval_note'])
            self.show_table('优化结果', ['状态', '可行', '目标函数', '约束残差', '起点数',
                                         '综合期望', '停止原因'], [[
                result['status'], result['feasible'], result['objective'],
                result['constraint_residual'],
                result['starts'], result['aggregate_desirability'], result['message']]])
            self.show_table('最优组分', ['组分', '比例'], [
                [key, value] for key, value in result['components'].items()])
            if result['actual_amounts'] is not None:
                self.show_table('实际组分用量', ['组分', '用量'], [
                    [key, value] for key, value in result['actual_amounts'].items()])
            if result['settings'] is not None:
                self.show_table('固定条件', ['变量', '设定'], [
                    [key, value] for key, value in result['settings'].items()
                    if key not in result['components']])
            def format_interval(interval, low, high):
                if interval['status'] != '可用':
                    return '—'
                return f'[{interval[low]:.10g}, {interval[high]:.10g}]'

            self.show_table('响应预测', [
                '响应', '目标', '目标值', '预测值', '期望值', '均值 CI', '单次观测 PI',
                '残差 df', '置信度', '区间状态'], [
                [item['response'], item['goal'], item.get('target'), item.get('prediction'),
                 item.get('desirability'),
                 format_interval(item['intervals'], 'ci_low', 'ci_high'),
                 format_interval(item['intervals'], 'pi_low', 'pi_high'),
                 item['intervals']['df'], f"{item['intervals']['confidence']:.0%}",
                 item['intervals']['reason'] or '可用']
                for item in result['objectives']])
        except (ValueError, TypeError, OverflowError) as exc:
            messagebox.showerror('混料优化', str(exc), parent=self.main)


class MixturePlots(_ResultWindow):
    def __init__(self, app):
        try:
            source, metadata = _source(app)
        except MixtureConstraintError as exc:
            messagebox.showerror('混料图形', str(exc), parent=app.main)
            return
        super().__init__(app, source, '混料图形')
        self.main.bind('<F1>', lambda event: open_help('doe.mixture.plots', parent=self.main))
        controls = ttk.Frame(self.main)
        controls.pack(fill='x', padx=8, before=self.tabs)
        self.kind = ttk.Combobox(controls, values=('Trace', '等高线', '曲面', '叠加等高线'),
                                 state='readonly', width=12)
        self.kind.set('Trace')
        self.kind.pack(side='left')
        self.kind.bind('<<ComboboxSelected>>', lambda event: self.build_limits())
        names = metadata['spec']['response_names']
        self.response = ttk.Combobox(controls, values=names, state='readonly', width=10)
        self.response.set(names[0])
        self.response.pack(side='left', padx=4)
        self.component = ttk.Combobox(controls, values=metadata['spec']['components'] and
                                      [item['component_id'] for item in metadata['spec']['components']],
                                      state='readonly', width=4)
        self.component.set(metadata['spec']['components'][0]['component_id'])
        self.component.pack(side='left', padx=4)
        self.axis_first = ttk.Combobox(controls, values=[item['component_id']
                                                         for item in metadata['spec']['components']],
                                       state='readonly', width=4)
        self.axis_second = ttk.Combobox(controls, values=[item['component_id']
                                                          for item in metadata['spec']['components']],
                                        state='readonly', width=4)
        self.axis_first.set(metadata['spec']['components'][0]['component_id'])
        self.axis_second.set(metadata['spec']['components'][1]['component_id'])
        if len(metadata['spec']['components']) < 4:
            self.axis_first.configure(state='disabled')
            self.axis_second.configure(state='disabled')
        self.axis_first.pack(side='left', padx=2)
        self.axis_second.pack(side='left', padx=2)
        ttk.Button(controls, text='绘制', command=self.draw).pack(side='left', padx=8)
        ttk.Button(controls, text='关闭', command=self.main.destroy).pack(side='right')
        inputs = ttk.Frame(self.main)
        inputs.pack(fill='x', padx=8, pady=4, before=self.tabs)
        self.entries = {}
        q = len(metadata['spec']['components'])
        starting = _equal_proportions(q)
        for item, value in zip(metadata['spec']['components'], starting):
            ttk.Label(inputs, text=item['component_id']).pack(side='left')
            entry = ttk.Entry(inputs, width=6)
            entry.insert(0, value)
            entry.pack(side='left', padx=2)
            self.entries[item['component_id']] = entry
        for item in metadata['spec']['process_variables']:
            entry = ttk.Entry(inputs, width=7)
            entry.insert(0, f'{(item["low"] + item["high"]) / 2:.6g}')
            entry.pack(side='left', padx=2)
            self.entries[item['variable_id']] = entry
        for item in metadata['spec']['amount_variables']:
            entry = ttk.Entry(inputs, width=8)
            entry.insert(0, f'{metadata["spec"]["amount_settings"][item["variable_id"]]:.6g}')
            entry.pack(side='left', padx=2)
            self.entries[item['variable_id']] = entry
        self.limits = ttk.Frame(self.main)
        self.limits.pack(fill='x', padx=8, pady=4, before=self.tabs)
        self.limit_entries = {}
        self.build_limits()
        self.status = tk.StringVar(value='')
        ttk.Label(self.main, textvariable=self.status).pack(fill='x', padx=8)

    def build_limits(self):
        for child in self.limits.winfo_children():
            child.destroy()
        self.limit_entries = {}
        if self.kind.get() != '叠加等高线':
            return
        frame = self.owner._full_frame(self.source)
        for item in self.metadata['spec']['response_names']:
            column = f'响应_{item}'
            values = pd.to_numeric(frame[column], errors='coerce').dropna()
            low = float(values.min()) if len(values) else 0.0
            high = float(values.max()) if len(values) else 1.0
            ttk.Label(self.limits, text=item).pack(side='left')
            first = ttk.Entry(self.limits, width=8)
            first.insert(0, f'{low:.6g}')
            first.pack(side='left', padx=2)
            second = ttk.Entry(self.limits, width=8)
            second.insert(0, f'{high:.6g}')
            second.pack(side='left', padx=2)
            self.limit_entries[item] = (first, second)

    def _conditions(self):
        spec = self.metadata['spec']
        return {item['variable_id']: _number(self.entries[item['variable_id']].get(), item['variable_id'])
                for item in (*spec['process_variables'], *spec['amount_variables'])}

    def _reference(self):
        spec = self.metadata['spec']
        return {item['component_id']: _number(self.entries[item['component_id']].get(), '组分比例')
                for item in spec['components']}

    def draw(self):
        try:
            frame = self.verify_source()
            spec = self.metadata['spec']
            conditions = self._conditions()
            reference = self._reference()
            degree, terms = _saved_model(self.source, frame, self.metadata)
            kind = self.kind.get()
            if len(spec['components']) < 3 and kind != 'Trace':
                raise MixtureConstraintError(
                    '双组分混料只有一维可行曲线；请使用 Trace 图，'
                    '等高线、曲面和叠加等高线需要至少三个组分。')
            axes = ((spec['components'][0]['component_id'],
                     spec['components'][1]['component_id'])
                    if len(spec['components']) == 3
                    else (self.axis_first.get(), self.axis_second.get()))
            viewer = self.app.showPlotViewer(deferred=True, figsize=(11, 8))
            try:
                from chart_style import font_families
                font = font_manager.FontProperties(family=font_families('Microsoft YaHei'))
                if kind == 'Trace':
                    result = analyze_mixture(frame, self.metadata, self.response.get(),
                                             terms=terms, degree=degree,
                                             doe_metadata=self.source.doe_metadata)
                    trace = trace_series(result['spec'], result['model'], result['coefficients'],
                                         reference, self.component.get(), steps=41,
                                         conditions=conditions)
                    axis = viewer.fig.add_subplot(111)
                    values = [point[self.component.get()] for point in trace['points']]
                    axis.plot(values, trace['values'], marker='o')
                    axis.axvline(reference[self.component.get()], color='gray', ls='--')
                    axis.set_xlabel(f'{self.component.get()} 实际比例')
                    axis.set_ylabel(f"响应 {self.response.get()}")
                    axis.set_title(f"Trace Plot：{trace['rule']}；跳过 {trace['skipped']} 个不可行点")
                    self._apply_font(axis, font)
                elif kind == '叠加等高线':
                    analyses = [analyze_mixture(frame, self.metadata, name,
                                                terms=terms, degree=degree,
                                                doe_metadata=self.source.doe_metadata)
                                for name in spec['response_names']]
                    limits = [(_number(first.get(), '下限'), _number(second.get(), '上限'))
                              for first, second in self.limit_entries.values()]
                    overlay = overlay_grid(analyses[0]['spec'],
                                           [item['model'] for item in analyses],
                                           [item['coefficients'] for item in analyses],
                                           limits, axes=axes,
                                           reference=reference, steps=31,
                                           conditions=conditions)
                    axis = viewer.fig.add_subplot(111)
                    grid = overlay['grid']
                    values = overlay['intersection'].astype(float)
                    if overlay['empty']:
                        axis.text(0.5, 0.5, '可行交集为空', ha='center', va='center',
                                  fontproperties=font, transform=axis.transAxes)
                        self.status.set('多个响应区间没有共同可行区域')
                    else:
                        triangulation = grid_triangulation(grid)
                        triangulation.set_mask(triangulation.mask |
                                               ~overlay['intersection'][triangulation.triangles].all(axis=1))
                        axis.tricontourf(triangulation, values, levels=[0.5, 1.5],
                                         colors=['#8fb8a8'])
                        self.status.set(f"可行交集包含 {overlay['count']} 个网格点；"
                                        + '；'.join(f'{key}={value:g}'
                                                   for key, value in conditions.items()))
                    axis.set_title('叠加等高线可行交集', fontproperties=font)
                    if len(spec['components']) == 3:
                        axis.set_aspect('equal')
                        axis.axis('off')
                        self._ternary_frame(axis, grid, font)
                    else:
                        axis.set_xlabel(f"{self.axis_first.get()} 比例", fontproperties=font)
                        axis.set_ylabel(f"{self.axis_second.get()} 比例", fontproperties=font)
                else:
                    result = analyze_mixture(frame, self.metadata, self.response.get(),
                                             terms=terms, degree=degree,
                                             doe_metadata=self.source.doe_metadata)
                    grid = simplex_grid(result['spec'], result['model'], result['coefficients'],
                                        axes=axes,
                                        reference=reference, steps=31, conditions=conditions)
                    values = np.where(grid['feasible'], grid['values'], np.nan)
                    if kind == '等高线':
                        axis = viewer.fig.add_subplot(111)
                        axis.tricontourf(grid_triangulation(grid), values, levels=20)
                        axis.set_title(f"混料等高线：响应 {self.response.get()}", fontproperties=font)
                        if len(spec['components']) == 3:
                            axis.set_aspect('equal')
                            axis.axis('off')
                            self._ternary_frame(axis, grid, font)
                        else:
                            axis.set_xlabel(f"{self.axis_first.get()} 比例", fontproperties=font)
                            axis.set_ylabel(f"{self.axis_second.get()} 比例", fontproperties=font)
                    else:
                        axis = viewer.fig.add_subplot(111, projection='3d')
                        axis.plot_trisurf(grid_triangulation(grid),
                                          np.nan_to_num(values), cmap='viridis')
                        axis.set_title(f"混料曲面：响应 {self.response.get()}", fontproperties=font)
                        axis.set_xlabel('B + 0.5C' if len(spec['components']) == 3
                                        else f"{self.axis_first.get()} 比例")
                        axis.set_ylabel('0.866C' if len(spec['components']) == 3
                                        else f"{self.axis_second.get()} 比例")
                        self._apply_font(axis, font)
                        axis.set_zlabel('预测响应')
                    self.status.set(f"合法切片步数 {grid['steps']}；剩余比例 {grid['remaining']:.6g}")
                viewer.fig.tight_layout()
                viewer.canvas.draw()
                self.app.replacePlotViewer(viewer)
                viewer.main.deiconify()
            except Exception:
                viewer.close()
                raise
        except (ValueError, TypeError, RuntimeError, OverflowError) as exc:
            messagebox.showerror('混料图形', str(exc), parent=self.main)

    @staticmethod
    def _apply_font(axis, font):
        for label in (*axis.get_xticklabels(), *axis.get_yticklabels()):
            label.set_fontproperties(font)
        if hasattr(axis, 'get_zticks'):
            for label in axis.get_zticklabels():
                label.set_fontproperties(font)
            axis.zaxis.label.set_fontproperties(font)
        axis.xaxis.label.set_fontproperties(font)
        axis.yaxis.label.set_fontproperties(font)
        axis.title.set_fontproperties(font)

    @staticmethod
    def _ternary_frame(axis, grid, font):
        for point, label in zip(([1, 0, 0], [0, 1, 0], [0, 0, 1]), ('A', 'B', 'C')):
            x, y = ternary_xy(point)
            axis.text(x, y, label, fontproperties=font, ha='center', va='center')
        corners = [ternary_xy(point) for point in ([1, 0, 0], [0, 1, 0], [0, 0, 1], [1, 0, 0])]
        axis.plot([item[0] for item in corners], [item[1] for item in corners], color='black')


class MixtureOptimalDesignDialog:
    """混料选点、增补、改善和评价；预览不会修改来源工作表。"""

    def __init__(self, app):
        self.app = app
        self.sheet_names = tuple(
            name for name, table in app.sheets.items()
            if getattr(table, 'mixture_metadata', None))
        if not self.sheet_names:
            messagebox.showerror('混料最优设计', '请先创建混料候选工作表。',
                                 parent=app.main)
            return
        self.main = tk.Toplevel(app.main)
        self.main.title('混料最优设计')
        self.main.transient(app.main)
        self.main.bind('<F1>', lambda event: open_help(
            'doe.mixture.optimal', parent=self.main))
        self.main.minsize(780, 560)
        self.last_config = None
        self.last_sources = None

        body = ttk.Frame(self.main, padding=10)
        body.pack(fill='both', expand=True)
        controls = ttk.Frame(body)
        controls.pack(fill='x')
        ttk.Label(controls, text='操作').grid(row=0, column=0, sticky='w')
        self.operation = ttk.Combobox(
            controls, values=('选点', '增补', '改善', '评价'), state='readonly', width=8)
        self.operation.set('选点')
        self.operation.grid(row=0, column=1, padx=4, sticky='w')
        ttk.Label(controls, text='候选工作表').grid(
            row=0, column=2, padx=(8, 0), sticky='w')
        self.candidate = ttk.Combobox(
            controls, values=self.sheet_names, state='readonly', width=22)
        current = app.getCurrentSheet()
        self.candidate.set(current if current in self.sheet_names else self.sheet_names[0])
        self.candidate.grid(row=0, column=3, padx=4, sticky='w')

        self.parent_row = ttk.Frame(controls)
        ttk.Label(self.parent_row, text='父设计').pack(side='left')
        self.parent_sheet = ttk.Combobox(
            self.parent_row, values=self.sheet_names, state='readonly', width=22)
        self.parent_sheet.set(self.candidate.get())
        self.parent_sheet.pack(side='left', padx=4)
        self.parent_row.grid(row=1, column=2, columnspan=2, sticky='w', pady=3)
        self.parent_sheet.bind('<<ComboboxSelected>>', self._parent_changed)

        ttk.Label(controls, text='准则').grid(row=1, column=0, sticky='w', pady=3)
        self.criterion = ttk.Combobox(
            controls, values=('D-optimal', 'Distance-based'),
            state='readonly', width=14)
        self.criterion.set('D-optimal')
        self.criterion.grid(row=1, column=1, padx=4, sticky='w')
        self.count_label = ttk.Label(controls, text='选点数')
        self.count_label.grid(row=2, column=0, sticky='w', pady=3)
        self.count = ttk.Entry(controls, width=8)
        self.count.insert(0, '6')
        self.count.grid(row=2, column=1, padx=4, sticky='w')
        ttk.Label(controls, text='阶次').grid(row=2, column=2, sticky='w')
        self.degree = ttk.Combobox(
            controls, values=(1, 2, 3), state='readonly', width=5)
        self.degree.set('2')
        self.degree.grid(row=2, column=3, padx=4, sticky='w')

        ttk.Label(controls, text='模型项（; 分隔）').grid(
            row=3, column=0, sticky='w', pady=3)
        self.terms = ttk.Entry(controls, width=78)
        self.terms.grid(row=3, column=1, columnspan=3, padx=4, sticky='ew')

        options = ttk.Frame(controls)
        options.grid(row=4, column=0, columnspan=4, sticky='ew', pady=3)
        self.allow_repeats = tk.BooleanVar(value=False)
        self.repeat_box = ttk.Checkbutton(
            options, text='允许重复设定', variable=self.allow_repeats)
        self.repeat_box.pack(side='left')
        ttk.Label(options, text='批次 ID').pack(side='left', padx=(14, 3))
        self.batch_id = ttk.Entry(options, width=10)
        self.batch_id.insert(0, 'AUG1')
        self.batch_id.pack(side='left')
        ttk.Label(options, text='距离变量（组分始终全选）').pack(
            side='left', padx=(14, 3))

        self.variable_list = tk.Listbox(
            controls, selectmode='multiple', exportselection=False,
            height=3, width=28)
        self.variable_list.grid(row=5, column=1, columnspan=3,
                                padx=4, sticky='w')
        self.distance_variable_ids = ()
        self.design_summary = tk.StringVar()
        ttk.Label(controls, textvariable=self.design_summary, wraplength=850,
                  justify='left').grid(row=6, column=0, columnspan=4,
                                       sticky='w', pady=(2, 4))

        self.improve_panel = ttk.LabelFrame(body, text='Improve', padding=6)
        run_frame = ttk.LabelFrame(self.improve_panel, text='父运行')
        run_frame.pack(side='left', fill='both', expand=True, padx=(0, 6))
        self.run_tree = ttk.Treeview(
            run_frame, columns=('run_id', 'state', 'response'),
            show='headings', selectmode='extended', height=6)
        for key, title, width in (('run_id', 'Run ID', 140),
                                  ('state', '状态', 80),
                                  ('response', '响应', 180)):
            self.run_tree.heading(key, text=title)
            self.run_tree.column(key, width=width, stretch=key == 'response')
        self.run_tree.pack(fill='both', expand=True, padx=4, pady=4)
        ttk.Button(run_frame, text='切换锁定/可替换',
                   command=self._toggle_run_state).pack(anchor='w', padx=4, pady=(0, 4))

        candidate_frame = ttk.LabelFrame(self.improve_panel, text='候选运行')
        candidate_frame.pack(side='left', fill='both', expand=True)
        candidate_body = ttk.Frame(candidate_frame)
        candidate_body.pack(fill='both', expand=True, padx=4, pady=4)
        self.candidate_runs = tk.Listbox(
            candidate_body, selectmode='extended', exportselection=False, height=6)
        candidate_scroll = ttk.Scrollbar(
            candidate_body, orient='vertical', command=self.candidate_runs.yview)
        self.candidate_runs.configure(yscrollcommand=candidate_scroll.set)
        self.candidate_runs.pack(side='left', fill='both', expand=True)
        candidate_scroll.pack(side='right', fill='y')
        candidate_actions = ttk.Frame(candidate_frame)
        candidate_actions.pack(fill='x', padx=4, pady=(0, 4))
        ttk.Button(candidate_actions, text='全选',
                   command=self._select_all_candidates).pack(side='left')
        ttk.Button(candidate_actions, text='清空',
                   command=lambda: self.candidate_runs.selection_clear(0, 'end')).pack(
                       side='left', padx=4)
        search = ttk.Frame(self.improve_panel)
        search.pack(side='bottom', fill='x', pady=(6, 0))
        ttk.Label(search, text='Seed').pack(side='left')
        self.improve_seed = ttk.Entry(search, width=8)
        self.improve_seed.insert(0, '0')
        self.improve_seed.pack(side='left', padx=(3, 12))
        ttk.Label(search, text='评价预算').pack(side='left')
        self.improve_budget = ttk.Entry(search, width=10)
        self.improve_budget.insert(0, '200000')
        self.improve_budget.pack(side='left', padx=3)
        self._parent_run_ids = {}
        self._candidate_run_ids = []
        self._protected_parent_ids = set()
        self.improve_source_status = tk.StringVar(value='')
        ttk.Label(self.improve_panel, textvariable=self.improve_source_status).pack(
            side='bottom', anchor='w')

        bottom = ttk.Frame(body)
        bottom.pack(side='bottom', fill='x')
        self.status = tk.StringVar(value='')
        ttk.Label(bottom, textvariable=self.status).pack(side='left', fill='x', expand=True)
        actions = ttk.Frame(bottom)
        actions.pack(side='right')
        ttk.Button(actions, text='预览', command=self.preview).pack(side='left')
        self.execute_button = ttk.Button(actions, text='创建', command=self.create)
        self.execute_button.pack(side='left', padx=5)
        ttk.Button(actions, text='关闭', command=self.main.destroy).pack(side='left')
        self.preview_text = tk.Text(body, height=12, wrap='word', state='disabled')
        self.preview_text.pack(fill='both', expand=True, pady=(8, 0))

        self.operation.bind('<<ComboboxSelected>>', self._operation_changed)
        self.criterion.bind('<<ComboboxSelected>>', self._criterion_changed)
        self.candidate.bind('<<ComboboxSelected>>', self._candidate_changed)
        self.degree.bind('<<ComboboxSelected>>', self._default_terms)
        self._candidate_changed()
        self._operation_changed()
        self._criterion_changed()
        self.main.geometry('1000x680')

    def _table(self, name):
        table = self.app.sheets.get(name)
        if table is None or not getattr(table, 'mixture_metadata', None):
            raise ValueError('请选择带有效 Mixture 元数据的工作表')
        self.app._finish_edit()
        frame = self.app._full_frame(table).copy(deep=True)
        return (table, frame, deepcopy(table.mixture_metadata),
                deepcopy(getattr(table, 'doe_metadata', None)))

    def _candidate_changed(self, _event=None):
        self._distance_variables()
        self._default_terms()
        try:
            table = self.app.sheets.get(self.candidate.get())
            metadata = getattr(table, 'mixture_metadata', None)
            spec = MixtureSpec.from_dict(metadata['spec'])
            components = '；'.join(
                f'{item.name} ({item.component_id}) [{item.lower:g}, {item.upper:g}]'
                for item in spec.components)
            constraints = '；'.join(
                ' + '.join(f'{value:g}·{key}' for key, value in rule.coefficients.items())
                + f' ≤ {rule.bound:g}'
                for rule in spec.linear_constraints) or '无额外线性约束'
            self.design_summary.set(
                f'组分（比例和=1）：{components}；线性约束：{constraints}')
        except (ValueError, KeyError, TypeError, AttributeError):
            self.design_summary.set('')
        if self.operation.get() == '改善':
            self._refresh_improve_inputs()

    @staticmethod
    def _run_key(run_id):
        if isinstance(run_id, (int, np.integer)) and not isinstance(run_id, bool):
            return 'int', int(run_id)
        return 'str', run_id

    @staticmethod
    def _run_is_protected(run):
        return (any(value is not None for value in run.responses.values())
                or any(value is not None for value in run.measured_levels.values()))

    @staticmethod
    def _run_label(run_id):
        return f'{type(run_id).__name__}: {run_id!r}'

    def _parent_changed(self, _event=None):
        if self.operation.get() == '改善':
            self._refresh_improve_inputs()

    def _refresh_improve_inputs(self):
        from doe_core import restore_design_result
        from doe_mixture import restore_mixture

        for item in self.run_tree.get_children():
            self.run_tree.delete(item)
        self._parent_run_ids.clear()
        self._protected_parent_ids.clear()
        self.candidate_runs.delete(0, 'end')
        self._candidate_run_ids.clear()
        try:
            parent_table, parent_frame, parent_meta, parent_doe = self._table(
                self.parent_sheet.get())
            candidate_table, candidate_frame, candidate_meta, candidate_doe = self._table(
                self.candidate.get())
            if (not isinstance(parent_doe, dict) or not isinstance(candidate_doe, dict)
                    or parent_meta.get('schema_version') != 1
                    or candidate_meta.get('schema_version') != 1):
                raise ValueError('Improve 需要普通 Mixture Schema 1 父设计与候选设计')
            _, parent_rows = restore_mixture(parent_frame, parent_meta, parent_doe)
            _, candidate_rows = restore_mixture(candidate_frame, candidate_meta,
                                                candidate_doe)
            parent_design = restore_design_result(parent_frame, parent_doe)
            candidate_design = restore_design_result(candidate_frame, candidate_doe)
            parent_runs = {self._run_key(run.run_id): run for run in parent_design.runs}
            for index, row in enumerate(parent_rows):
                run_id = row['run_id']
                run = parent_runs[self._run_key(run_id)]
                protected = self._run_is_protected(run)
                iid = f'p{index}'
                self._parent_run_ids[iid] = run_id
                if protected:
                    self._protected_parent_ids.add(iid)
                responses = '; '.join(
                    f'{name}={value}' for name, value in run.responses.items()
                    if value is not None)
                self.run_tree.insert(
                    '', 'end', iid=iid,
                    values=(self._run_label(run_id),
                            '已保护' if protected else '锁定', responses))
            candidate_runs = {
                self._run_key(run.run_id): run for run in candidate_design.runs}
            for row in candidate_rows:
                run = candidate_runs[self._run_key(row['run_id'])]
                if self._run_is_protected(run):
                    continue
                self._candidate_run_ids.append(row['run_id'])
                self.candidate_runs.insert('end', self._run_label(row['run_id']))
            if self._candidate_run_ids:
                self.candidate_runs.selection_set(0, 'end')
            self.improve_source_status.set('')
        except (ValueError, TypeError, KeyError, AttributeError) as error:
            self.improve_source_status.set(str(error))

    def _toggle_run_state(self):
        for iid in self.run_tree.selection():
            if iid in self._protected_parent_ids:
                continue
            values = list(self.run_tree.item(iid, 'values'))
            values[1] = '可替换' if values[1] == '锁定' else '锁定'
            self.run_tree.item(iid, values=values)

    def _select_all_candidates(self):
        if self._candidate_run_ids:
            self.candidate_runs.selection_set(0, 'end')

    def _improve_partitions(self):
        locked, replaceable = [], []
        for iid, run_id in self._parent_run_ids.items():
            state = self.run_tree.item(iid, 'values')[1]
            if state == '可替换':
                replaceable.append(run_id)
            else:
                locked.append(run_id)
        candidate_ids = tuple(self._candidate_run_ids[index]
                              for index in self.candidate_runs.curselection())
        return tuple(locked), tuple(replaceable), candidate_ids

    def _distance_variables(self):
        self.variable_list.delete(0, 'end')
        try:
            table = self.app.sheets.get(self.candidate.get())
            metadata = getattr(table, 'mixture_metadata', None)
            spec = MixtureSpec.from_dict(metadata['spec'])
            self.distance_variable_ids = spec.variable_ids
        except (ValueError, KeyError, TypeError, AttributeError):
            self.distance_variable_ids = ()
        for name in self.distance_variable_ids:
            self.variable_list.insert('end', name)
        self.variable_list.configure(
            height=max(1, min(3, len(self.distance_variable_ids))))

    def _default_terms(self, _event=None):
        try:
            table = self.app.sheets.get(self.candidate.get())
            metadata = getattr(table, 'mixture_metadata', None)
            spec = MixtureSpec.from_dict(metadata['spec'])
            from doe_mixture_model import MixtureTermModel
            model = MixtureTermModel(spec, degree=int(self.degree.get()))
        except (ValueError, KeyError, TypeError, AttributeError):
            return
        self.terms.delete(0, 'end')
        self.terms.insert(0, ';'.join(model.terms))

    def _operation_changed(self, _event=None):
        operation = self.operation.get()
        if operation in ('增补', '改善'):
            self.parent_row.grid()
            self.count_label.configure(text='替换数' if operation == '改善' else '新增数')
            self.count.configure(state='disabled' if operation == '改善' else 'normal')
            self.batch_id.configure(state='disabled' if operation == '改善' else 'normal')
            self.execute_button.configure(state='normal')
            if operation == '改善':
                self.improve_panel.pack(fill='both', expand=True, pady=(4, 0),
                                        before=self.preview_text)
                self.criterion.set('D-optimal')
                self.criterion.configure(state='disabled')
                self.allow_repeats.set(False)
                self.repeat_box.configure(state='disabled')
                self.variable_list.configure(state='disabled')
                self._refresh_improve_inputs()
            else:
                self.improve_panel.pack_forget()
                self.criterion.configure(state='readonly')
                self._criterion_changed()
        elif operation == '评价':
            self.improve_panel.pack_forget()
            self.parent_row.grid_remove()
            self.count_label.configure(text='运行数')
            self.count.configure(state='normal')
            self.batch_id.configure(state='disabled')
            self.criterion.configure(state='readonly')
            self.execute_button.configure(state='disabled')
            self._criterion_changed()
        else:
            self.improve_panel.pack_forget()
            self.parent_row.grid_remove()
            self.count_label.configure(text='选点数')
            self.count.configure(state='normal')
            self.batch_id.configure(state='disabled')
            self.criterion.configure(state='readonly')
            self.execute_button.configure(state='normal')
            self._criterion_changed()

    def _criterion_changed(self, _event=None):
        if self.operation.get() == '改善':
            self.criterion.set('D-optimal')
            self.repeat_box.configure(state='disabled')
            self.variable_list.configure(state='disabled')
            return
        distance = self.criterion.get() == 'Distance-based'
        self.repeat_box.configure(state='disabled' if distance else 'normal')
        if distance:
            self.allow_repeats.set(False)
            self.variable_list.configure(state='normal')
        else:
            self.variable_list.configure(state='disabled')

    def _config(self):
        return (self.operation.get(), self.candidate.get(), self.parent_sheet.get(),
                self.criterion.get(), self.count.get(), self.degree.get(),
                self.terms.get(), self.allow_repeats.get(), self.batch_id.get(),
                self._selected_distance_variables(),
                tuple((iid, tuple(self.run_tree.item(iid, 'values')))
                      for iid in self.run_tree.get_children()),
                tuple(self.candidate_runs.curselection()),
                self.improve_seed.get(), self.improve_budget.get())

    def _selected_distance_variables(self):
        if self.criterion.get() != 'Distance-based':
            return ()
        return tuple(self.distance_variable_ids[index]
                     for index in self.variable_list.curselection())

    def _capture_sources(self):
        names = [self.candidate.get()]
        if self.operation.get() in ('增补', '改善'):
            names.append(self.parent_sheet.get())
        snapshots = {}
        for name in dict.fromkeys(names):
            table, frame, mixture, doe = self._table(name)
            if not isinstance(doe, dict):
                raise ValueError('Mixture 工作表缺少 DOE 元数据')
            snapshots[name] = (table, frame, mixture, doe)
        return snapshots

    def _sources_unchanged(self):
        if not self.last_sources:
            return False
        for name, (table, frame, mixture, doe) in self.last_sources.items():
            if (self.app.sheets.get(name) is not table
                    or not self.app._full_frame(table).equals(frame)
                    or getattr(table, 'mixture_metadata', None) != mixture
                    or getattr(table, 'doe_metadata', None) != doe):
                return False
        return True

    def _calculate(self, snapshots):
        operation = self.operation.get()
        _, candidate_frame, candidate_mixture, candidate_doe = \
            snapshots[self.candidate.get()]
        criterion = 'd_optimal' if self.criterion.get() == 'D-optimal' else 'distance'
        degree = int(self.degree.get())
        terms = tuple(item.strip() for item in self.terms.get().split(';')
                      if item.strip()) or None
        variables = self._selected_distance_variables()
        if operation == '评价':
            summary = evaluate_mixture_design(
                candidate_frame, candidate_mixture, candidate_doe,
                criterion=criterion, degree=degree, terms=terms,
                distance_variables=variables)
            return None, None, None, None, summary
        if operation == '改善':
            if self.parent_sheet.get() == self.candidate.get():
                raise ValueError('父设计与候选设计必须是不同工作表')
            _, parent_frame, parent_mixture, parent_doe = snapshots[self.parent_sheet.get()]
            locked_ids, replaceable_ids, candidate_ids = self._improve_partitions()
            try:
                seed = int(self.improve_seed.get())
                budget = int(self.improve_budget.get())
            except ValueError as error:
                raise ValueError('Seed 和评价预算必须是整数') from error
            return improve_mixture_design(
                parent_frame, parent_mixture, parent_doe,
                candidate_frame, candidate_mixture, candidate_doe,
                locked_ids, replaceable_ids, candidate_ids,
                degree=degree, terms=terms, seed=seed,
                evaluation_budget=budget)
        try:
            count = int(self.count.get())
        except ValueError as error:
            raise ValueError('运行数必须是整数') from error
        if operation == '选点':
            return select_mixture_optimal(
                candidate_frame, candidate_mixture, candidate_doe, count,
                criterion=criterion, degree=degree, terms=terms,
                allow_repeats=self.allow_repeats.get(),
                distance_variables=variables)
        _, parent_frame, parent_mixture, parent_doe = snapshots[self.parent_sheet.get()]
        return augment_mixture(
            parent_frame, parent_mixture, parent_doe,
            candidate_frame, candidate_mixture, candidate_doe, count,
            criterion=criterion, degree=degree, terms=terms,
            allow_repeats=self.allow_repeats.get(),
            distance_variables=variables, batch_id=self.batch_id.get())

    def _render(self, result):
        summary = result[4]
        if self.operation.get() == '改善':
            lines = [f"父设计：rank {summary['parent_rank']}，logdet {summary['parent_logdet']}",
                     f"改善后：rank {summary['current_rank']}，logdet {summary['current_logdet']}",
                     f"候选 {summary['candidate_count']}；替换 {summary['replaced_n']}；"
                     f"评价 {summary['evaluations']}/{summary['evaluation_budget']}",
                     f"Seed {summary['seed']}；停止原因：{summary['stop_reason']}",
                     f"候选域全局最优已穷举证明：{summary['global_optimum_proven']}",
                     '新增运行响应为空。', '', '候选 → 新运行 → 被替换父运行：']
            lines.extend(' → '.join(map(str, pair))
                         for pair in summary['candidate_to_replaced_parent'])
        else:
            lines = [f'{key}: {summary[key]}' for key in (
            'criterion', 'method', 'n', 'candidate_count', 'selected_n',
            'initial_n', 'added_n', 'rank', 'p', 'selected_rank',
            'condition', 'logdet', 'min_squared_distance', 'evaluations',
            'subsets', 'exact_budget', 'global_optimum_proven',
                'allow_repeats', 'distance_variables', 'stop_reason',
                'multiplicities') if key in summary]
        if result[0] is not None:
            frame, doe = result[0], result[1]
            if self.operation.get() == '增补':
                frame = frame.tail(summary['added_n'])
            columns = doe['column_map']
            labels = [columns['run_id']]
            if columns.get('source_run_id'):
                labels.append(columns['source_run_id'])
            labels.extend(columns['factors'].values())
            lines.extend(('', '运行预览：'))
            for _, row in frame[labels].head(12).iterrows():
                lines.append(' | '.join(str(row[name]) for name in labels))
            if len(frame) > 12:
                lines.append(f'共 {len(frame)} 行')
        self.preview_text.configure(state='normal')
        self.preview_text.delete('1.0', 'end')
        self.preview_text.insert('1.0', '\n'.join(lines))
        self.preview_text.configure(state='disabled')

    def preview(self):
        try:
            snapshots = self._capture_sources()
            result = self._calculate(snapshots)
            self.last_config = self._config()
            self.last_sources = snapshots
            self._render(result)
            self.status.set('预览完成，来源工作表未修改。')
        except (ValueError, TypeError, OverflowError, KeyError) as error:
            self.last_config = None
            self.last_sources = None
            messagebox.showerror('混料最优设计', str(error), parent=self.main)

    def create(self):
        if self.operation.get() == '评价':
            return
        if (self.last_config != self._config() or not self._sources_unchanged()):
            messagebox.showerror('混料最优设计',
                                 '预览参数或来源数据已变化，请重新预览。',
                                 parent=self.main)
            return
        try:
            frame, doe, mixture, model, _ = self._calculate(self.last_sources)
            metadata = {'doe': doe, 'mixture': mixture, 'mixture_model': model}
            name = {'增补': '混料增补设计', '改善': '混料改善设计'}.get(
                self.operation.get(), '混料最优设计')
            self.app.addSheet(name, frame, metadata)
            self.main.destroy()
        except (ValueError, TypeError, OverflowError, KeyError) as error:
            messagebox.showerror('混料最优设计', str(error), parent=self.main)
