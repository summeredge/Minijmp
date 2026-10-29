"""响应面点预测界面：独立于优化器，使用当前工作表的拟合模型。"""
from copy import deepcopy
import tkinter as tk
from tkinter import messagebox, ttk

from doe_core import restore_design_result
from doe_dialog import ccd_number
from help_link import open_help
from sheet_context import SheetApp
from stat_table import StatTable, TableBlock


class PredictRSM:
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
            self.frame = frame
            self.design = restore_design_result(frame, metadata)
            if self.design.spec.design_type not in ('central_composite',
                                                    'box_behnken', 'custom_rsm'):
                raise ValueError('预测仅支持中心复合、Box-Behnken 或自定义响应面设计。')
        except (AttributeError, KeyError, TypeError, ValueError, RuntimeError) as exc:
            messagebox.showerror('响应预测', str(exc) or '当前工作表不是有效响应面设计。',
                                 parent=app.main)
            return
        self.factors = self.design.spec.factors
        self.responses = self.design.spec.response_names
        self.entries = {}
        self.main = tk.Toplevel(app.main)
        self.main.title('响应面预测')
        self.main.geometry('720x520')
        self.main.bind('<F1>', lambda event: open_help(
            {'box_behnken': 'doe.bbd', 'custom_rsm': 'doe.predict'}.get(
                self.design.spec.design_type, 'doe.ccd'), parent=self.main))
        self.status = tk.StringVar(value='')
        bar = ttk.Frame(self.main, padding=8)
        bar.pack(fill='x')
        ttk.Label(bar, text='响应').pack(side='left')
        self.response = ttk.Combobox(bar, values=self.responses, state='readonly',
                                     width=18)
        self.response.set(self.responses[0])
        self.response.pack(side='left', padx=4)
        self.use_blocks = tk.BooleanVar(value=True)
        ttk.Checkbutton(bar, text='纳入区组', variable=self.use_blocks).pack(
            side='left', padx=6)
        self.show_intervals = tk.BooleanVar(value=True)
        interval_bar = ttk.Frame(self.main, padding=(8, 0))
        interval_bar.pack(fill='x')
        ttk.Checkbutton(interval_bar, text='CI/PI', variable=self.show_intervals).pack(
            side='left')
        ttk.Label(interval_bar, text='置信度').pack(side='left', padx=(10, 3))
        self.confidence = ttk.Combobox(
            interval_bar, values=('90%', '95%', '99%'), state='readonly', width=6)
        self.confidence.set('95%')
        self.confidence.pack(side='left')
        ttk.Label(interval_bar, text='方向').pack(side='left', padx=(10, 3))
        self.interval_side = ttk.Combobox(
            interval_bar, values=('双侧', '单侧下限', '单侧上限'),
            state='readonly', width=10)
        self.interval_side.set('双侧')
        self.interval_side.pack(side='left')

        form = ttk.LabelFrame(self.main, text='因子设置', padding=8)
        form.pack(fill='x', padx=8, pady=4)
        for row, factor in enumerate(self.factors):
            label = f'{factor.factor_id} {factor.name}'
            if factor.unit:
                label += f'（{factor.unit}）'
            ttk.Label(form, text=label).grid(row=row, column=0, sticky='w', pady=2)
            if factor.factor_type == 'categorical':
                widget = ttk.Combobox(form, values=factor.levels, state='readonly',
                                      width=18)
                widget.set(factor.levels[0])
            else:
                widget = ttk.Entry(form, width=20)
                widget.insert(0, str((factor.low + factor.high) / 2))
            widget.grid(row=row, column=1, sticky='w', padx=6, pady=2)
            self.entries[factor.factor_id] = widget

        ttk.Button(bar, text='预测', command=self.predict).pack(side='left', padx=6)
        ttk.Button(bar, text='关闭', command=self.main.destroy).pack(side='right')
        ttk.Label(self.main, textvariable=self.status, anchor='w',
                  wraplength=680).pack(fill='x', padx=8)
        self.result_frame = ttk.Frame(self.main, padding=8)
        self.result_frame.pack(fill='both', expand=True)
        self.block = None

    def _read(self):
        settings = {}
        for factor in self.factors:
            widget = self.entries[factor.factor_id]
            if factor.factor_type == 'categorical':
                settings[factor.factor_id] = widget.get()
            else:
                value = ccd_number(widget.get())
                if not factor.low <= value <= factor.high:
                    raise ValueError(f'{factor.name} 超出设计低/高水平')
                settings[factor.factor_id] = value
        return settings

    def predict(self):
        if self.block is not None:
            self.block.destroy()
            self.block = None
        try:
            self.owner._finish_edit()
            if self.owner.getCurrentTable() is not self.source:
                raise ValueError('来源工作表已切换，请切回后重新预测。')
            frame = self.owner._full_frame(self.source).copy(deep=True)
            metadata = deepcopy(self.source.doe_metadata)
            if metadata != self.metadata:
                raise ValueError('DOE 设计已更改，请关闭并重新打开预测窗口。')
            settings = self._read()
            from doe_predict import predict_point
            confidence = (float(self.confidence.get().rstrip('%')) / 100
                          if self.show_intervals.get() else None)
            side = {'双侧': 'two_sided', '单侧下限': 'lower',
                    '单侧上限': 'upper'}[self.interval_side.get()]
            result = predict_point(frame, metadata, self.response.get(), settings,
                                   blocks=self.use_blocks.get(), confidence=confidence,
                                   side=side)
        except (KeyError, TypeError, ValueError, RuntimeError, OverflowError) as exc:
            self.status.set('预测失败：' + str(exc))
            return
        headers = ('项目', '值')
        values = [[f'{factor.factor_id} {factor.name}',
                   result['settings'][factor.factor_id]] for factor in self.factors]
        values.append(['预测响应', result['prediction']])
        intervals = result.get('intervals')
        if intervals is not None:
            fmt = lambda value: '—' if value is None else f'{value:.10g}'
            ci_label = '拟合均值 CI' if intervals['side'] != 'lower' else '拟合均值 CI 下限'
            if intervals['side'] == 'upper':
                ci_label = '拟合均值 CI 上限'
            pi_label = '单次观测 PI' if intervals['side'] != 'lower' else '单次观测 PI 下限'
            if intervals['side'] == 'upper':
                pi_label = '单次观测 PI 上限'
            ci = (f"[{fmt(intervals['ci_low'])}, {fmt(intervals['ci_high'])}]"
                  if intervals['side'] == 'two_sided' else
                  fmt(intervals['ci_low'] if intervals['side'] == 'lower'
                      else intervals['ci_high']))
            pi = (f"[{fmt(intervals['pi_low'])}, {fmt(intervals['pi_high'])}]"
                  if intervals['side'] == 'two_sided' else
                  fmt(intervals['pi_low'] if intervals['side'] == 'lower'
                      else intervals['pi_high']))
            values.extend([
                ['SE Fit', fmt(intervals['se_fit'])],
                [ci_label, ci], [pi_label, pi],
                ['区间状态', intervals['reason'] or
                 f"可用；df={intervals['df']}，置信度={intervals['confidence']:.0%}；"
                 + intervals['assumption']],
            ])
        values.append(['模型项', '、'.join(result['terms'])])
        values.append(['快照', result['snapshot_id']])
        values.append(['外推状态', result['extrapolation_note']])
        values.append(['说明', result['note']])
        self.block = TableBlock(self.result_frame, StatTable(
            title='点预测', headers=headers, values=values), paginate=True)
        self.block.pack(fill='both', expand=True)
        self.status.set(
            f'预测 {result["response"]} = {result["prediction"]:.10g}；'
            f'模型快照 {result["snapshot_id"]}'
            + (f'；区组参考 {result["block"]}' if result['block'] is not None else ''))
