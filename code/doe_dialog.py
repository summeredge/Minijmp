"""两水平全因子的创建、分析和结果展示。"""
import tkinter as tk
from tkinter import messagebox, ttk

import numpy as np
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
    def __init__(self, app, fractional=False, ccd=False):
        self.app = app
        self.fractional = fractional
        self.ccd = ccd
        self.main = tk.Toplevel(app.main)
        self.main.title('创建中心复合设计' if ccd else '创建两水平部分因子设计' if fractional else '创建两水平全因子设计')
        help_topic = 'doe.ccd' if ccd else 'doe.fractional' if fractional else 'doe.full_factorial'
        self.main.bind('<F1>', lambda event: open_help(help_topic, parent=self.main))
        self.fields = []
        self.factor_labels = []
        grid = ttk.Frame(self.main, padding=8)
        grid.pack(fill='both', expand=True)
        for col, label in enumerate(('因子', '名称', '低水平', '高水平', '单位')):
            ttk.Label(grid, text=label).grid(row=0, column=col, padx=3)
        factor_limit = 5 if ccd else 6
        for i in range(factor_limit):
            label = ttk.Label(grid, text=chr(65+i))
            label.grid(row=i+1, column=0)
            self.factor_labels.append(label)
            entries = []
            for col in range(1, 5):
                entry = ttk.Entry(grid, width=15)
                entry.grid(row=i+1, column=col, padx=3, pady=2)
                entries.append(entry)
            if i < (6 if fractional else 5 if ccd else 2):
                entries[0].insert(0, chr(65+i))
                entries[1].insert(0, '0')
                entries[2].insert(0, '1')
            self.fields.append(entries)
        options_start = factor_limit + 1
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
            self.factor_count = ttk.Combobox(grid, values=list(range(2, 6)), state='readonly', width=5)
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
            self.measured = tk.BooleanVar(value=False)
            ttk.Checkbutton(grid, text='添加实测水平列', variable=self.measured).grid(
                row=options_start, column=0, columnspan=2, sticky='w')
            options_start += 1
        self.options = {}
        for row, (key, default) in enumerate((('重复数', '1'), ('中心点数', '5' if ccd else '0'),
                                               ('随机 seed', '1'), ('响应名称', 'Y')),
                                             options_start):
            ttk.Label(grid, text=key).grid(row=row, column=0, sticky='w')
            entry = ttk.Entry(grid, width=25)
            entry.insert(0, default)
            entry.grid(row=row, column=1, columnspan=2, sticky='ew', pady=2)
            self.options[key] = entry
        preview_row = options_start + len(self.options)
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
        bar = ttk.Frame(grid)
        bar.grid(row=preview_row + 1, column=0, columnspan=5, sticky='e')
        ttk.Button(bar, text='预览', command=self.preview).pack(side='left')
        ttk.Button(bar, text='创建', command=self.create).pack(side='left', padx=4)
        ttk.Button(bar, text='取消', command=self.main.destroy).pack(side='left')

    def update_factor_rows(self, event=None):
        if event is not None and self.fractional:
            self.preset.set('自定义')
        count = int(self.factor_count.get())
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
        field_count = int(self.factor_count.get()) if self.fractional or self.ccd else len(self.fields)
        for i, entries in enumerate(self.fields[:field_count]):
            name, low, high, unit = (entry.get().strip() for entry in entries)
            if not any((name, low, high, unit)):
                continue
            parse = ccd_number if self.ccd else number
            factors.append(FactorSpec(chr(65+i), name, parse(low), parse(high), unit or None))
        responses = tuple(s.strip() for s in self.options['响应名称'].get().split(','))
        generator_text = self.generators.get() if self.fractional else ''
        generators = tuple(generator_text.split(';')) if generator_text else ()
        replicates = int(self.options['重复数'].get())
        centers = int(self.options['中心点数'].get())
        if self.ccd:
            from doe_ccd import create_ccd
            k = len(factors)
            alpha = 1 if self.ccd_type.get() == 'CCF' else (2**k)**.25
            spec = DesignSpec('DOE', tuple(factors), responses,
                              seed=int(self.options['随机 seed'].get()),
                              design_type='central_composite', ccd_alpha=alpha,
                              ccd_center_points=centers, ccd_axial_points=2*k*replicates)
            return create_ccd(spec, replicates, measured=self.measured.get())
        spec = DesignSpec('DOE', tuple(factors), responses,
                          seed=int(self.options['随机 seed'].get()),
                          generators=generators,
                          design_type='two_level_fractional' if self.fractional
                          else 'two_level_full')
        if self.fractional:
            if centers:
                raise ValueError('正规部分因子设计当前不支持中心点，请将中心点数设为 0。')
            from doe_fractional import create_fractional
            return create_fractional(spec, replicates, centers)
        return create_factorial(spec, replicates, centers)

    def preview(self):
        try:
            frame, meta = self.build()
            summary = f'{len(frame)} 次运行；前 5 个运行 ID：' + ', '.join(
                frame['运行ID'].head().tolist())
            if self.ccd:
                from doe_ccd import axial_levels
                spec = DesignSpec.from_dict(meta['design'])
                points = [f'{f.name}: {lo!r} / {hi!r} {f.unit or ""}'
                          for f in spec.factors for lo, hi in [axial_levels(f, spec.ccd_alpha)]]
                counts = frame['点类型'].value_counts()
                summary += (f"；α={spec.ccd_alpha:.8g}；因子点 {counts.get('factorial', 0)}"
                            f"，轴点 {counts.get('axial', 0)}，中心点 {counts.get('center', 0)}；"
                            + '；'.join(points))
                if spec.ccd_alpha > 1:
                    summary += '；警告：轴点超出低高水平'
            if self.fractional:
                design = meta['design']
                relations = design['defining_relations']
                resolution = min(len(item.split('=', 1)[1]) for item in relations)
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
        except (ValueError, TypeError, OverflowError) as exc:
            messagebox.showerror('试验设计', str(exc), parent=self.main)

    def create(self):
        try:
            frame, meta = self.build()
            if self.ccd and meta['design']['ccd_alpha'] > 1:
                from doe_ccd import axial_levels
                spec = DesignSpec.from_dict(meta['design'])
                levels = '\n'.join(f'{f.name}: {lo!r} / {hi!r} {f.unit or ""}'
                                   for f in spec.factors for lo, hi in [axial_levels(f, spec.ccd_alpha)])
                if not messagebox.askyesno('轴点超出低高水平',
                        '外接设计的轴点超出低高水平，请确认工艺安全：\n' + levels,
                        parent=self.main):
                    return
            self.app.addSheet('DOE', frame, {'doe': meta})
        except (ValueError, TypeError, OverflowError) as exc:
            messagebox.showerror('试验设计', str(exc), parent=self.main)
            return
        self.main.destroy()


class AnalyzeDOE:
    def __init__(self, app):
        self.owner = app
        self.source = app.getCurrentTable()
        self.app = SheetApp(app, self.source)
        metadata = getattr(self.source, 'doe_metadata', None)
        if not metadata:
            messagebox.showerror('试验设计', '当前工作表不是 DOE 设计。', parent=app.main)
            return
        design_type = metadata.get('design', {}).get('design_type')
        if design_type not in ('two_level_full', 'two_level_fractional', 'central_composite'):
            messagebox.showerror('试验设计', '当前 DOE 设计类型暂不支持分析。', parent=app.main)
            return
        self.fractional = design_type == 'two_level_fractional'
        self.ccd = design_type == 'central_composite'
        self.main = tk.Toplevel(app.main)
        self.main.title('分析响应面模型' if self.ccd else '分析两水平部分因子设计' if self.fractional else '分析因子设计')
        help_topic = 'doe.ccd' if self.ccd else 'doe.fractional' if self.fractional else 'doe.full_factorial'
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
        self.order.set('2')
        if self.ccd:
            self.order.configure(state='disabled')
        self.order.pack(side='left', padx=4)
        factor_ids = [factor['factor_id'] for factor in metadata['design']['factors']]
        ttk.Label(controls, text='绘图因子' if self.ccd else '交互因子').pack(side='left')
        self.factor_x = ttk.Combobox(controls, values=factor_ids, state='readonly', width=4)
        self.factor_y = ttk.Combobox(controls, values=factor_ids, state='readonly', width=4)
        if len(factor_ids) >= 2:
            self.factor_x.set(factor_ids[0])
            self.factor_y.set(factor_ids[1])
        self.factor_x.pack(side='left', padx=2)
        self.factor_y.pack(side='left', padx=2)
        self.fixed = {}
        if self.ccd:
            fixed_bar = ttk.Frame(self.main, padding=(8, 0))
            fixed_bar.pack(fill='x')
            for factor_id in factor_ids:
                ttk.Label(fixed_bar, text=f'{factor_id} 固定值').pack(side='left')
                entry = ttk.Entry(fixed_bar, width=5)
                entry.insert(0, '0')
                entry.pack(side='left', padx=2)
                self.fixed[factor_id] = entry
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
            if self.ccd:
                from doe_rsm import analyze_rsm
                result = analyze_rsm(frame, self.source.doe_metadata, self.response.get())
            elif self.fractional:
                from doe_fractional_analysis import analyze_fractional
                result = analyze_fractional(
                    frame, self.source.doe_metadata, self.response.get(),
                    int(self.order.get()))
            else:
                result = analyze_factorial(frame, self.source.doe_metadata,
                                           self.response.get(), int(self.order.get()))
            self.publish(result)
        except (ValueError, TypeError, RuntimeError, OverflowError) as exc:
            self.result = None
            self.status.set('分析失败：' + str(exc))
            messagebox.showerror('试验设计', str(exc), parent=self.main)

    def publish(self, result):
        for tab in self.tabs.tabs():
            self.tabs.nametowidget(tab).destroy()
        self.status.set(f"响应 {result['response']}，{result['n']} 行分析快照；数据修改后需重新分析；" +
                        result['status'] + '；' + result['assumption'])
        inf = result['inference']
        if self.ccd:
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
                                     '纯误差自由度', '纯误差平方和', '失拟自由度', '失拟平方和', 'SSR', 'SST',
                                     'R²', '调整R²', 'F', '模型p'], [[
                result['n'], result['p'], result['rank'], result['df'], result['sse'],
                result['pure_error_df'], result['pure_error_sse'], result['lack_of_fit_df'],
                result['lack_of_fit_sse'], result['ssr'],
                result['sst'], result['r2'], result['adjusted_r2'],
                inf['f'] if inf else None, inf['model_p'] if inf else None]])
            if inf:
                self.show_table('方差分析', ['来源', '平方和', '自由度', '均方', 'F', 'p'],
                                [['模型', result['ssr'], result['p']-1,
                                  result['ssr']/(result['p']-1), inf['f'], inf['model_p']],
                                 ['残差', result['sse'], result['df'], inf['mse'], None, None],
                                 ['总计', result['sst'], result['n']-1, None, None, None]])
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
        if self.ccd:
            self.show_table('系数', ['项', '系数', 'SE', 't', 'p', 'CI低', 'CI高'],
                            [row[:2]+row[3:] for row in rows])
        else:
            self.show_table('系数与效应', ['项', '系数', '效应', 'SE', 't', 'p', 'CI低', 'CI高'], rows)
        self.show_table('模型', ['n', '项数', '秩', '残差自由度', 'SSE', '纯误差自由度', '纯误差平方和',
                              '失拟自由度', '失拟平方和', 'SSR', 'SST', 'R²', '调整R²', 'F', '模型p'],
                        [[result['n'], result['p'], result['rank'], result['df'], result['sse'],
                          result['pure_error_df'], result['pure_error_sse'],
                          result['lack_of_fit_df'], result['lack_of_fit_sse'],
                          result['ssr'], result['sst'], result['r2'], result['adjusted_r2'],
                          inf['f'] if inf else None, inf['model_p'] if inf else None]])
        if inf:
            self.show_table('方差分析', ['来源', '平方和', '自由度', '均方', 'F', 'p'],
                            [['模型', result['ssr'], result['p']-1,
                              result['ssr']/(result['p']-1), inf['f'], inf['model_p']],
                             ['残差', result['sse'], result['df'], inf['mse'], None, None],
                             ['总计', result['sst'], result['n']-1, None, None, None]])
        lof = result['lack_of_fit']
        curvature = result['curvature']
        tests = [['失拟', result['lack_of_fit_sse'], result['lack_of_fit_df'],
                  lof['f'] if lof else None, lof['p'] if lof else None,
                  '已计算' if lof else '纯误差或失拟自由度不足，或纯误差为零']]
        if curvature:
            tests.append(['曲率（中心−因子均值）', curvature['ss'], 1,
                          curvature['f'], curvature['p'],
                          f"均值差 {curvature['difference']:.6g}；" +
                          ('已计算' if curvature['f'] is not None else '纯误差不可估计')])
        self.show_table('失拟与曲率', ['检验', '平方和', '自由度', 'F', 'p', '状态'], tests)
        self.show_table('拟合与残差', ['来源行号', '运行ID', '运行序', '响应', '拟合值', '残差'],
                        [[i+1, run.run_id, run.run_order, run.responses[result['response']],
                          result['fitted'][i], result['residuals'][i]]
                         for i, run in enumerate(result['design'].runs)])
        self.result = result

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
            r = self.result
            factors = r['design'].spec.factors
            fractional = r['design'].spec.design_type == 'two_level_fractional'
            ids = [factor.factor_id for factor in factors]
            first_id, second_id = self.factor_x.get(), self.factor_y.get()
            if first_id not in ids or second_id not in ids or first_id == second_id:
                raise ValueError('请选择两个不同的因子。')
            first_index, second_index = ids.index(first_id), ids.index(second_id)
            if self.ccd:
                self.plot_rsm(r, first_index, second_index)
                return
            viewer = self.app.showPlotViewer(deferred=True, figsize=(10, 8))
            try:
                axes = viewer.fig.subplots(2, 2)
                factorial = np.array([run.point_type == 'factorial' for run in r['design'].runs])
                coded = r['coded'][factorial]
                y = np.array([run.responses[r['response']] for run in r['design'].runs])[factorial]
                for i, factor in enumerate(factors):
                    means = [y[coded[:, i] == v].mean() for v in (-1, 1)]
                    axes[0, 0].plot([-1, 1], means, marker='o', label=factor.factor_id)
                axes[0, 0].set_title(
                    '主效应条件均值（按别名组解释）' if fractional else '主效应图')
                axes[0, 0].legend()
                for v in (-1, 1):
                    means = [y[(coded[:, first_index] == x) &
                               (coded[:, second_index] == v)].mean() for x in (-1, 1)]
                    axes[0, 1].plot([-1, 1], means, marker='o',
                                    label=f'{second_id}={v}')
                axes[0, 1].set_title(
                    f'{first_id} × {second_id} 交互图（描述性；可能混杂）'
                    if fractional else f'{first_id} × {second_id} 交互图')
                axes[0, 1].legend()
                if fractional:
                    effect_by_name = dict(zip(r['names'], r['effects']))
                    effects = [(group['label'], abs(effect_by_name[group['representative']]))
                               for group in r['alias_groups']
                               if group['representative'] in effect_by_name and
                               effect_by_name[group['representative']] is not None]
                else:
                    effects = [(name, abs(effect))
                               for name, effect in zip(r['names'], r['effects'])
                               if effect is not None]
                effects.sort(key=lambda item: item[1])
                axes[1, 0].barh([x[0] for x in effects], [x[1] for x in effects])
                axes[1, 0].set_title('可估计别名组效应绝对值 Pareto 图'
                                     if fractional else '效应绝对值 Pareto 图')
                if r['inference'] is None:
                    axes[1, 1].text(.5, .5, '残差诊断不可用', ha='center')
                else:
                    axes[1, 1].scatter(r['fitted'], r['residuals'])
                    axes[1, 1].axhline(0, color='black')
                    axes[1, 1].set_title('残差与拟合值')
                from chart_style import font_families
                font = font_manager.FontProperties(family=font_families('Microsoft YaHei'))
                viewer.fig.suptitle(f"响应 {r['response']}：上次分析快照，数据修改后请重新分析",
                                    fontproperties=font)
                for axis in axes.flat:
                    axis.title.set_fontproperties(font)
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

    def plot_rsm(self, result, first, second):
        from scipy import stats
        from doe_rsm import model_matrix
        factors = result['design'].spec.factors
        alpha = result['design'].spec.ccd_alpha
        fixed = np.array([float(self.fixed[f.factor_id].get()) for f in factors])
        if not np.isfinite(fixed).all() or np.any(abs(fixed) > alpha):
            raise ValueError('固定编码水平必须位于轴点范围内')
        axis = np.linspace(-alpha, alpha, 50)
        xx, yy = np.meshgrid(axis, axis)
        coded = np.tile(fixed, (xx.size, 1))
        coded[:, first], coded[:, second] = xx.ravel(), yy.ravel()
        zz = (model_matrix(coded) @ result['coefficients']).reshape(xx.shape)
        viewer = self.app.showPlotViewer(deferred=True, figsize=(10, 8))
        try:
            contour = viewer.fig.add_subplot(221)
            surface = viewer.fig.add_subplot(222, projection='3d')
            residual = viewer.fig.add_subplot(223)
            normal = viewer.fig.add_subplot(224)
            contour.contourf(xx, yy, zz, levels=15)
            fixed_outside = any(abs(fixed[i]) > 1 for i in range(len(factors))
                                if i not in (first, second))
            outside = (abs(xx) > 1) | (abs(yy) > 1) | fixed_outside
            if outside.any():
                contour.contourf(xx, yy, outside.astype(float), levels=[.5, 1.5],
                                 colors='none', hatches=['///'])
            if alpha > 1:
                from matplotlib.patches import Rectangle
                contour.add_patch(Rectangle((-1, -1), 2, 2, fill=False, color='white', linestyle='--'))
            contour.set_title('等高线（斜线为因子点范围外）')
            surface.plot_surface(xx, yy, np.where(outside, np.nan, zz), cmap='viridis')
            if outside.any():
                surface.plot_surface(xx, yy, np.where(outside, zz, np.nan), color='indianred', alpha=.55)
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
            fixed_text = ', '.join(f'{f.factor_id}={fixed[i]:g}' for i, f in enumerate(factors)
                                   if i not in (first, second)) or '无'
            from chart_style import font_families
            font = font_manager.FontProperties(family=font_families('Microsoft YaHei'))
            viewer.fig.suptitle(f"响应 {result['response']}；{factors[first].factor_id} × {factors[second].factor_id}；固定编码水平 {fixed_text}；分析快照",
                                fontproperties=font)
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
