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


class CreateDOE:
    def __init__(self, app):
        self.app = app
        self.main = tk.Toplevel(app.main)
        self.main.title('创建两水平全因子设计')
        self.main.bind('<F1>', lambda event: open_help('doe.full_factorial', parent=self.main))
        self.fields = []
        grid = ttk.Frame(self.main, padding=8)
        grid.pack(fill='both', expand=True)
        for col, label in enumerate(('因子', '名称', '低水平', '高水平', '单位')):
            ttk.Label(grid, text=label).grid(row=0, column=col, padx=3)
        for i in range(6):
            ttk.Label(grid, text=chr(65+i)).grid(row=i+1, column=0)
            entries = []
            for col in range(1, 5):
                entry = ttk.Entry(grid, width=15)
                entry.grid(row=i+1, column=col, padx=3, pady=2)
                entries.append(entry)
            if i < 2:
                entries[0].insert(0, chr(65+i))
                entries[1].insert(0, '0')
                entries[2].insert(0, '1')
            self.fields.append(entries)
        self.options = {}
        for row, (key, default) in enumerate((('重复数', '1'), ('中心点数', '0'),
                                               ('随机 seed', '1'), ('响应名称', 'Y')), 7):
            ttk.Label(grid, text=key).grid(row=row, column=0, sticky='w')
            entry = ttk.Entry(grid, width=25)
            entry.insert(0, default)
            entry.grid(row=row, column=1, columnspan=2, sticky='ew', pady=2)
            self.options[key] = entry
        self.preview_text = tk.StringVar(value='')
        ttk.Label(grid, textvariable=self.preview_text).grid(row=11, column=0, columnspan=5)
        bar = ttk.Frame(grid)
        bar.grid(row=12, column=0, columnspan=5, sticky='e')
        ttk.Button(bar, text='预览', command=self.preview).pack(side='left')
        ttk.Button(bar, text='创建', command=self.create).pack(side='left', padx=4)
        ttk.Button(bar, text='取消', command=self.main.destroy).pack(side='left')

    def build(self):
        factors = []
        for i, entries in enumerate(self.fields):
            name, low, high, unit = (entry.get().strip() for entry in entries)
            if not any((name, low, high, unit)):
                continue
            factors.append(FactorSpec(chr(65+i), name, number(low), number(high), unit or None))
        responses = tuple(s.strip() for s in self.options['响应名称'].get().split(','))
        spec = DesignSpec('DOE', tuple(factors), responses,
                          seed=int(self.options['随机 seed'].get()),
                          design_type='two_level_full')
        return create_factorial(spec, int(self.options['重复数'].get()),
                                int(self.options['中心点数'].get()))

    def preview(self):
        try:
            frame, _ = self.build()
            self.preview_text.set(f'{len(frame)} 次运行；前 5 个运行 ID：' +
                                  ', '.join(frame['运行ID'].head().tolist()))
        except (ValueError, TypeError, OverflowError) as exc:
            messagebox.showerror('试验设计', str(exc), parent=self.main)

    def create(self):
        try:
            frame, meta = self.build()
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
        self.main = tk.Toplevel(app.main)
        self.main.title('分析因子设计')
        self.main.bind('<F1>', lambda event: open_help('doe.full_factorial', parent=self.main))
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
        self.order.pack(side='left', padx=4)
        factor_ids = [factor['factor_id'] for factor in metadata['design']['factors']]
        ttk.Label(controls, text='交互因子').pack(side='left')
        self.factor_x = ttk.Combobox(controls, values=factor_ids, state='readonly', width=4)
        self.factor_y = ttk.Combobox(controls, values=factor_ids, state='readonly', width=4)
        if len(factor_ids) >= 2:
            self.factor_x.set(factor_ids[0])
            self.factor_y.set(factor_ids[1])
        self.factor_x.pack(side='left', padx=2)
        self.factor_y.pack(side='left', padx=2)
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
        rows = []
        for i, name in enumerate(result['names']):
            rows.append([name, result['coefficients'][i], result['effects'][i]] +
                        ([inf['se'][i], inf['t'][i], inf['p'][i], inf['ci_low'][i], inf['ci_high'][i]]
                         if inf else [None]*5))
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
            ids = [factor.factor_id for factor in factors]
            first_id, second_id = self.factor_x.get(), self.factor_y.get()
            if first_id not in ids or second_id not in ids or first_id == second_id:
                raise ValueError('请选择两个不同的因子。')
            first_index, second_index = ids.index(first_id), ids.index(second_id)
            viewer = self.app.showPlotViewer(deferred=True, figsize=(10, 8))
            try:
                axes = viewer.fig.subplots(2, 2)
                factorial = np.array([run.point_type == 'factorial' for run in r['design'].runs])
                coded = r['coded'][factorial]
                y = np.array([run.responses[r['response']] for run in r['design'].runs])[factorial]
                for i, factor in enumerate(factors):
                    means = [y[coded[:, i] == v].mean() for v in (-1, 1)]
                    axes[0, 0].plot([-1, 1], means, marker='o', label=factor.factor_id)
                axes[0, 0].set_title('主效应图'); axes[0, 0].legend()
                for v in (-1, 1):
                    means = [y[(coded[:, first_index] == x) &
                               (coded[:, second_index] == v)].mean() for x in (-1, 1)]
                    axes[0, 1].plot([-1, 1], means, marker='o',
                                    label=f'{second_id}={v}')
                axes[0, 1].set_title(f'{first_id} × {second_id} 交互图')
                axes[0, 1].legend()
                effects = [(name, abs(effect)) for name, effect in zip(r['names'], r['effects'])
                           if effect is not None]
                effects.sort(key=lambda item: item[1])
                axes[1, 0].barh([x[0] for x in effects], [x[1] for x in effects])
                axes[1, 0].set_title('效应绝对值 Pareto 图')
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
