"""多响应叠加等高线界面：两个绘图因子、其余固定、各自可接受范围。"""
from copy import deepcopy
import math
import tkinter as tk
from tkinter import messagebox, ttk

from matplotlib import font_manager

from doe_core import restore_design_result
from doe_dialog import ccd_number
from doe_overlay import overlay_contours
from help_link import open_help
from sheet_context import SheetApp


class OverlayContours:
    def __init__(self, app):
        self.owner = app
        self.source = app.getCurrentTable()
        self.app = SheetApp(app, self.source)
        try:
            app._finish_edit()
            metadata = getattr(self.source, 'doe_metadata', None)
            if not metadata:
                raise ValueError('当前工作表没有有效的 DOE 元数据。')
            self.metadata = deepcopy(metadata)
            frame = app._full_frame(self.source).copy(deep=True)
            self.design = restore_design_result(frame, metadata)
            if self.design.spec.design_type not in ('central_composite',
                                                    'box_behnken'):
                raise ValueError('叠加等高线仅支持中心复合设计或 Box-Behnken 设计。')
        except (AttributeError, KeyError, TypeError, ValueError, RuntimeError) as exc:
            messagebox.showerror('叠加等高线', str(exc) or '当前工作表不是有效响应面设计。',
                                 parent=app.main)
            return
        self.factors = [factor for factor in self.design.spec.factors
                        if factor.factor_type == 'continuous']
        self.categorical = [factor for factor in self.design.spec.factors
                            if factor.factor_type == 'categorical']
        self.responses = list(self.design.spec.response_names)
        self.last = None
        self.viewer = None

        self.main = tk.Toplevel(app.main)
        self.main.title('叠加等高线')
        self.main.geometry('760x420')
        self.main.protocol('WM_DELETE_WINDOW', self.close)
        self.main.bind('<F1>', lambda event: open_help(
            'doe.bbd' if self.design.spec.design_type == 'box_behnken'
            else 'doe.ccd.overlay', parent=self.main))

        bar = ttk.Frame(self.main, padding=8)
        bar.pack(fill='x')
        ttk.Label(bar, text='横轴').pack(side='left')
        self.factor_x = ttk.Combobox(bar, values=[f.factor_id for f in self.factors],
                                     state='readonly', width=6)
        self.factor_x.set(self.factors[0].factor_id)
        self.factor_x.pack(side='left', padx=(2, 10))
        ttk.Label(bar, text='纵轴').pack(side='left')
        self.factor_y = ttk.Combobox(bar, values=[f.factor_id for f in self.factors],
                                     state='readonly', width=6)
        self.factor_y.set((self.factors[1] if len(self.factors) > 1
                           else self.factors[0]).factor_id)
        self.factor_y.pack(side='left', padx=(2, 10))
        self.draw_button = ttk.Button(bar, text='绘图', command=self.draw,
                                      state='disabled')
        self.draw_button.pack(side='left')
        ttk.Button(bar, text='关闭', command=self.close).pack(side='right')

        ranges = ttk.LabelFrame(self.main, text='响应可接受范围', padding=6)
        ranges.pack(fill='x', padx=8)
        for col, label in enumerate(('响应', '下限', '上限', '纳入')):
            ttk.Label(ranges, text=label).grid(row=0, column=col, sticky='w', padx=4)
        self.rows = {}
        observed = {}
        for name in self.responses:
            values = [run.responses.get(name) for run in self.design.runs]
            values = [float(value) for value in values
                      if isinstance(value, (int, float)) and not isinstance(value, bool)
                      and math.isfinite(float(value))]
            observed[name] = ((min(values), max(values))
                              if values and min(values) < max(values) else None)
        for row, name in enumerate(self.responses, 1):
            selected = row <= 2
            chosen = tk.BooleanVar(value=selected)
            ttk.Checkbutton(ranges, variable=chosen,
                            command=self._update_state).grid(row=row, column=3,
                                                             sticky='w', padx=4)
            ttk.Label(ranges, text=name).grid(row=row, column=0, sticky='w', padx=4, pady=2)
            low, high = ttk.Entry(ranges, width=14), ttk.Entry(ranges, width=14)
            if observed[name] is not None:
                low.insert(0, repr(observed[name][0]))
                high.insert(0, repr(observed[name][1]))
            for entry in (low, high):
                entry.bind('<KeyRelease>', lambda event: self._update_state())
            low.grid(row=row, column=1, sticky='w', padx=4, pady=2)
            high.grid(row=row, column=2, sticky='w', padx=4, pady=2)
            self.rows[name] = (chosen, low, high)
        ranges.columnconfigure(2, weight=1)

        fixed = ttk.LabelFrame(self.main, text='其余因子固定值（编码）', padding=6)
        fixed.pack(fill='x', padx=8, pady=6)
        self.fixed = {}
        for factor in self.factors:
            ttk.Label(fixed, text=f'{factor.factor_id} {factor.name}').pack(side='left')
            entry = ttk.Entry(fixed, width=7)
            entry.insert(0, '0')
            entry.pack(side='left', padx=(2, 10))
            entry.bind('<KeyRelease>', lambda event: self._update_state())
            self.fixed[factor.factor_id] = entry
        self.categories = {}
        for factor in self.categorical:
            ttk.Label(fixed, text=f'{factor.factor_id} {factor.name}').pack(side='left')
            choice = ttk.Combobox(fixed, values=factor.levels, state='readonly', width=10)
            choice.set(factor.levels[0])
            choice.pack(side='left', padx=(2, 10))
            choice.bind('<<ComboboxSelected>>',
                        lambda event: self._update_state())
            self.categories[factor.factor_id] = choice

        self.status = tk.StringVar(value='')
        ttk.Label(self.main, textvariable=self.status, wraplength=720,
                  justify='left').pack(fill='x', padx=8, pady=(0, 8))
        self.factor_x.bind('<<ComboboxSelected>>', lambda event: self._update_state())
        self.factor_y.bind('<<ComboboxSelected>>', lambda event: self._update_state())
        self._update_state()

    def _read(self):
        ranges = {}
        for name, (chosen, low, high) in self.rows.items():
            if not chosen.get():
                continue
            try:
                lower, upper = ccd_number(low.get()), ccd_number(high.get())
            except ValueError as exc:
                raise ValueError(f'{name} 的可接受范围必须是有限数值') from exc
            if not float(lower) < float(upper):
                raise ValueError(f'{name} 的可接受下限必须小于上限')
            ranges[name] = (lower, upper)
        if len(ranges) < 2:
            raise ValueError('至少需要两个响应的可接受范围')
        fixed = {factor_id: ccd_number(entry.get())
                 for factor_id, entry in self.fixed.items()
                 if factor_id not in (self.factor_x.get(), self.factor_y.get())}
        for factor_id, value in fixed.items():
            if not math.isfinite(float(value)) or not -1 <= float(value) <= 1:
                raise ValueError(f'因子 {factor_id} 的固定编码水平必须位于 −1 至 1')
        categories = {key: choice.get() for key, choice in self.categories.items()}
        return ranges, fixed, categories

    def _update_state(self):
        if self.last is not None:
            self._invalidate()
        try:
            if self.factor_x.get() == self.factor_y.get():
                raise ValueError('横轴和纵轴必须是两个不同的因子')
            self._read()
        except (ValueError, TypeError, OverflowError) as exc:
            self.draw_button.configure(state='disabled')
            self.status.set('待修正：' + str(exc))
            return
        self.draw_button.configure(state='normal')
        if self.status.get().startswith('待修正：'):
            self.status.set('')

    def _invalidate(self):
        if self.last is not None:
            self.last = None
            if self.viewer is not None:
                try:
                    if self.viewer.main.winfo_exists():
                        self.viewer.close()
                except tk.TclError:
                    pass
                self.viewer = None
            self.status.set('设置已更改，请重新绘图。')

    def draw(self):
        self.last = None
        try:
            self.owner._finish_edit()
            if self.owner.getCurrentTable() is not self.source:
                raise ValueError('来源工作表已切换，请切回后重新绘图。')
            frame = self.owner._full_frame(self.source).copy(deep=True)
            metadata = deepcopy(self.source.doe_metadata)
            if metadata != self.metadata:
                raise ValueError('DOE 设计已更改，请关闭并重新打开叠加等高线。')
            ranges, fixed, categories = self._read()
            result = overlay_contours(frame, metadata, ranges,
                                      self.factor_x.get(), self.factor_y.get(),
                                      fixed, categories)
        except (KeyError, TypeError, ValueError, RuntimeError, OverflowError) as exc:
            self.status.set('绘图失败：' + str(exc))
            return
        self.last = {'result': result, 'frame': frame, 'metadata': metadata,
                     'ranges': ranges}
        self._plot(result, ranges)
        fraction = result['feasible_fraction']
        self.status.set(
            f"快照 {result['snapshot_id']}；可行网格占比 {fraction:.1%}；"
            + ('可行区域为空：没有一个网格点同时满足全部响应范围。' if fraction == 0
               else '阴影为全部响应同时可接受的区域（含端点）。'))

    def _plot(self, result, ranges):
        if self.viewer is not None:
            try:
                if self.viewer.main.winfo_exists():
                    self.viewer.close()
            except tk.TclError:
                pass
            self.viewer = None
        viewer = self.app.showPlotViewer(deferred=True, figsize=(8, 6.5))
        self.viewer = viewer
        try:
            axis = viewer.fig.add_subplot(111)
            xx, yy = result['xx'], result['yy']
            colors_cycle = ['#1f77b4', '#d62728', '#2ca02c', '#9467bd']
            for index, (name, values) in enumerate(result['z'].items()):
                color = colors_cycle[index % len(colors_cycle)]
                low, high = ranges[name]
                axis.contour(xx, yy, values, levels=[low, high], colors=color,
                             linestyles='dashed', linewidths=1.1)
                axis.plot([], [], color=color, linestyle='dashed',
                          label=f'{name}：{low:g} 至 {high:g}')
            if result['feasible'].any():
                axis.contourf(xx, yy, result['feasible'].astype(float),
                              levels=[0.5, 1.5], colors=['#4c9f70'], alpha=.28)
            axis.set_xlim(float(xx.min()), float(xx.max()))
            axis.set_ylim(float(yy.min()), float(yy.max()))
            axis.set_xlabel(f'{self.factor_x.get()} 编码值')
            axis.set_ylabel(f'{self.factor_y.get()} 编码值')
            fixed_text = ', '.join(
                f'{name}={value:g}' for name, value in result['fixed'].items()
                if name not in result['factors']) or '无'
            axis.set_title(f'叠加等高线；虚线为各响应界限，绿色为可行交集；固定 {fixed_text}')
            axis.legend(loc='upper right', fontsize=8)
            from chart_style import font_families
            font = font_manager.FontProperties(
                family=font_families('Microsoft YaHei'))
            viewer.fig.suptitle(f'快照 {result["snapshot_id"]}；模型预测，非确认试验结果',
                                fontproperties=font)
            for text in (axis.title, axis.xaxis.label, axis.yaxis.label):
                text.set_fontproperties(font)
            for label in axis.get_xticklabels() + axis.get_yticklabels():
                label.set_fontproperties(font)
            for label in axis.get_legend().get_texts():
                label.set_fontproperties(font)
            viewer.fig.tight_layout()
            viewer.canvas.draw()
            self.app.replacePlotViewer(viewer)
            viewer.main.deiconify()
        except Exception:
            viewer.close()
            self.viewer = None
            raise

    def close(self):
        if self.viewer is not None:
            try:
                if self.viewer.main.winfo_exists():
                    self.viewer.close()
            except tk.TclError:
                pass
            self.viewer = None
        if getattr(self, 'main', None) is not None:
            self.main.destroy()

