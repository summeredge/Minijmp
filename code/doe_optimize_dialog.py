"""CCD 响应优化的工作表绑定界面。"""
from copy import deepcopy
from fractions import Fraction
import math
import tkinter as tk
from tkinter import messagebox, ttk

import numpy as np
from matplotlib import font_manager

from doe_core import restore_design_result
from doe_dialog import ccd_number
from help_link import open_help
from sheet_context import SheetApp
from stat_table import StatTable, TableBlock


_MODE = {'最大化': 'maximize', '最小化': 'minimize', '逼近目标': 'target'}


def _finite(text, label):
    try:
        value = float(_actual(text, label))
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f'{label}必须是有限数值') from exc
    if not math.isfinite(value):
        raise ValueError(f'{label}必须是有限数值')
    return value


def _actual(text, label):
    value = ccd_number(text)
    try:
        converted = float(value)
    except (TypeError, OverflowError, ValueError) as exc:
        raise ValueError(f'{label}超出可表示范围') from exc
    if not math.isfinite(converted) or (isinstance(value, int) and int(converted) != value):
        raise ValueError(f'{label}必须可安全表示为有限数值')
    return value


def _shown(value):
    return str(value) if not isinstance(value, float) else repr(value)


def _actual_for_code(factor, coded):
    actual = float(factor.from_coded(coded))
    if not math.isfinite(actual) or abs(float(factor.to_coded(actual)) - coded) > 1e-8:
        raise ValueError(f'{factor.name} 的编码与实际水平不能按 DOE 精度往返。')
    return actual


class OptimizeRSM:
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
            self.design = restore_design_result(frame, self.metadata)
            if self.design.spec.design_type != 'central_composite':
                raise ValueError('DOE-4 仅支持完整中心复合设计（CCD）。')
            from doe_ccd import validate_ccd
            validate_ccd(self.design)
        except (AttributeError, KeyError, TypeError, ValueError, RuntimeError) as exc:
            messagebox.showerror('DOE-4 优化', str(exc) or '当前工作表不是有效 CCD。',
                                 parent=app.main)
            return

        self.factors = self.design.spec.factors
        self.responses = self.design.spec.response_names
        self.active_response = self.responses[0]
        self.response_settings = {
            name: {'mode': '最大化', 'low': '', 'target': '', 'high': '',
                   'power_low': '1', 'power_high': '1', 'weight': '1'}
            for name in self.responses
        }
        self.last = None
        self.viewer = None

        self.main = tk.Toplevel(app.main)
        self.main.title('优化响应面（DOE-4）')
        self.main.geometry('1080x740')
        self.main.minsize(900, 620)
        self.main.protocol('WM_DELETE_WINDOW', self.close)
        self.main.bind('<F1>', lambda event: open_help('doe.ccd', parent=self.main))

        self.source_info = tk.StringVar(
            value=f'来源：{app.getCurrentSheet()}，完整 CCD，{len(self.factors)} 个因子')
        ttk.Label(self.main, textvariable=self.source_info).pack(fill='x', padx=8, pady=(8, 2))
        ttk.Label(self.main, text='模型预测候选，须现场安全审核并进行确认试验。').pack(
            anchor='w', padx=8)

        bounds = ttk.LabelFrame(self.main, text='实际可行边界', padding=6)
        bounds.pack(fill='x', padx=8, pady=4)
        for col, label in enumerate(('因子', '实际下限', '实际上限', '编码范围')):
            ttk.Label(bounds, text=label).grid(row=0, column=col, sticky='w', padx=4)
        self.bound_entries = {}
        for row, factor in enumerate(self.factors, 1):
            label = f'{factor.factor_id}  {factor.name}' + (f'（{factor.unit}）' if factor.unit else '')
            ttk.Label(bounds, text=label).grid(row=row, column=0, sticky='w', padx=4, pady=2)
            lower = ttk.Entry(bounds, width=18)
            upper = ttk.Entry(bounds, width=18)
            lower.insert(0, _shown(factor.low))
            upper.insert(0, _shown(factor.high))
            lower.grid(row=row, column=1, sticky='w', padx=4, pady=2)
            upper.grid(row=row, column=2, sticky='w', padx=4, pady=2)
            coded = tk.StringVar(value='−1 至 +1')
            ttk.Label(bounds, textvariable=coded).grid(row=row, column=3, sticky='w', padx=4)
            self.bound_entries[factor.factor_id] = (lower, upper, coded)
            lower.bind('<KeyRelease>', self._bounds_changed)
            upper.bind('<KeyRelease>', self._bounds_changed)
        bounds.columnconfigure(3, weight=1)

        settings = ttk.LabelFrame(self.main, text='响应目标', padding=6)
        settings.pack(fill='x', padx=8, pady=4)
        left = ttk.Frame(settings)
        left.pack(side='left', fill='y', padx=(0, 10))
        ttk.Label(left, text='响应（Ctrl/Shift 多选）').pack(anchor='w')
        self.response_list = tk.Listbox(left, selectmode='extended', exportselection=False,
                                        height=min(5, max(2, len(self.responses))), width=20)
        for name in self.responses:
            self.response_list.insert('end', name)
        self.response_list.selection_set(0)
        self.response_list.pack(fill='y', expand=True)
        self.response_list.bind('<<ListboxSelect>>', self._select_response)

        form = ttk.Frame(settings)
        form.pack(side='left', fill='x', expand=True)
        self.mode = tk.StringVar(value='最大化')
        self.low = tk.StringVar()
        self.target = tk.StringVar()
        self.high = tk.StringVar()
        self.power_low = tk.StringVar(value='1')
        self.power_high = tk.StringVar(value='1')
        self.weight = tk.StringVar(value='1')
        self.power_low_label = tk.StringVar(value='低侧指数')
        self.power_high_label = tk.StringVar(value='高侧指数')
        ttk.Label(form, text='目标').grid(row=0, column=0, sticky='w', padx=3, pady=2)
        mode = ttk.Combobox(form, textvariable=self.mode, values=tuple(_MODE),
                            state='readonly', width=12)
        mode.grid(row=0, column=1, sticky='w', padx=3, pady=2)
        mode.bind('<<ComboboxSelected>>', self._mode_changed)
        entries = (('低阈值', self.low), ('目标值', self.target), ('高阈值', self.high),
                   (self.power_low_label, self.power_low),
                   (self.power_high_label, self.power_high), ('权重', self.weight))
        self.response_entries = []
        for index, (label, variable) in enumerate(entries):
            row, col = 1 + index // 3, (index % 3) * 2
            label_widget = (ttk.Label(form, textvariable=label) if isinstance(label, tk.StringVar)
                            else ttk.Label(form, text=label))
            label_widget.grid(row=row, column=col, sticky='w', padx=3, pady=2)
            entry = ttk.Entry(form, textvariable=variable, width=14)
            entry.grid(row=row, column=col + 1, sticky='w', padx=3, pady=2)
            entry.bind('<KeyRelease>', self._response_changed)
            self.response_entries.append(entry)
        for col in range(6):
            form.columnconfigure(col, weight=1 if col % 2 else 0)

        bar = ttk.Frame(self.main, padding=(8, 4))
        bar.pack(fill='x')
        self.status = tk.StringVar(value='')
        self.run_button = ttk.Button(bar, text='开始优化', command=self.optimize, state='disabled')
        self.run_button.pack(side='left')
        ttk.Label(bar, text='响应').pack(side='left', padx=(12, 3))
        self.plot_response = ttk.Combobox(bar, values=self.responses, state='readonly', width=14)
        self.plot_response.set(self.responses[0])
        self.plot_response.pack(side='left')
        ttk.Label(bar, text='因子').pack(side='left', padx=(8, 3))
        self.factor_x = ttk.Combobox(bar, values=[f.factor_id for f in self.factors],
                                     state='readonly', width=6)
        self.factor_y = ttk.Combobox(bar, values=[f.factor_id for f in self.factors],
                                     state='readonly', width=6)
        self.factor_x.set(self.factors[0].factor_id)
        self.factor_y.set(self.factors[1].factor_id)
        self.factor_x.pack(side='left')
        self.factor_y.pack(side='left', padx=(3, 0))
        self.plot_button = ttk.Button(bar, text='等高线', command=self.plot, state='disabled')
        self.plot_button.pack(side='left', padx=6)
        ttk.Button(bar, text='关闭', command=self.close).pack(side='right')
        ttk.Label(bar, textvariable=self.status, anchor='w').pack(side='left', fill='x', expand=True, padx=8)

        self.tabs = ttk.Notebook(self.main)
        self.tabs.pack(fill='both', expand=True, padx=8, pady=(0, 8))
        self.result_tab = ttk.Frame(self.tabs)
        self.tabs.add(self.result_tab, text='建议点')
        self.result_block = None
        candidate_tab = ttk.Frame(self.tabs)
        self.tabs.add(candidate_tab, text='候选记录')
        self.candidate_tab = candidate_tab
        self.candidate_block = None

        self._load_response(self.active_response)
        self._bounds_changed()
        self._update_run_state()

    def _load_response(self, name):
        values = self.response_settings[name]
        self.mode.set(values['mode'])
        self.low.set(values['low'])
        self.target.set(values['target'])
        self.high.set(values['high'])
        self.power_low.set(values['power_low'])
        self.power_high.set(values['power_high'])
        self.weight.set(values['weight'])
        self._update_shape_controls()

    def _mode_changed(self, event=None):
        self._update_shape_controls()
        self._response_changed(event)

    def _update_shape_controls(self):
        mode = self.mode.get()
        if mode == '最大化':
            self.power_low_label.set('指数')
            self.power_high_label.set('不使用')
            self.power_high.set(self.power_low.get())
            self.response_entries[4].configure(state='disabled')
            self.response_entries[3].configure(state='normal')
        elif mode == '最小化':
            self.power_low_label.set('不使用')
            self.power_high_label.set('指数')
            self.power_low.set(self.power_high.get())
            self.response_entries[3].configure(state='disabled')
            self.response_entries[4].configure(state='normal')
        else:
            self.power_low_label.set('低侧指数')
            self.power_high_label.set('高侧指数')
            self.response_entries[3].configure(state='normal')
            self.response_entries[4].configure(state='normal')

    def _save_response(self):
        if not getattr(self, 'active_response', None):
            return
        self.response_settings[self.active_response] = {
            'mode': self.mode.get(), 'low': self.low.get(), 'target': self.target.get(),
            'high': self.high.get(), 'power_low': self.power_low.get(),
            'power_high': self.power_high.get(), 'weight': self.weight.get(),
        }

    def _select_response(self, event=None):
        selected = self.response_list.curselection()
        if not selected:
            self._update_run_state()
            return
        self._save_response()
        current = self.response_list.index('active')
        self.active_response = self.response_list.get(current)
        self._load_response(self.active_response)
        self._update_run_state()
        self._invalidate('响应选择已更改，请重新优化。')

    def _response_changed(self, event=None):
        self._save_response()
        self._update_run_state()
        self._invalidate('目标参数已更改，请重新优化。')

    def _bounds_changed(self, event=None):
        for factor in self.factors:
            lower, upper, coded_text = self.bound_entries[factor.factor_id]
            try:
                lo, hi = _actual(lower.get(), '实际下限'), _actual(upper.get(), '实际上限')
                if lo > hi:
                    raise ValueError
                coded_lo, coded_hi = factor.to_coded(lo), factor.to_coded(hi)
                coded_text.set(f'{float(coded_lo):.8g} 至 {float(coded_hi):.8g}')
            except (ValueError, OverflowError, TypeError):
                coded_text.set('不可用')
        self._update_run_state()
        self._invalidate('边界已更改，请重新优化。')

    def _read_bounds(self):
        result, actual = {}, {}
        for factor in self.factors:
            lower, upper, _ = self.bound_entries[factor.factor_id]
            low, high = _actual(lower.get(), f'{factor.factor_id} 实际下限'), _actual(
                upper.get(), f'{factor.factor_id} 实际上限')
            if low > high:
                raise ValueError(f'{factor.name} 的实际下限不能大于上限。')
            coded_low, coded_high = factor.to_coded(low), factor.to_coded(high)
            low_exact, high_exact = Fraction(coded_low), Fraction(coded_high)
            lo, hi = float(coded_low), float(coded_high)
            if low == high:
                if _actual_for_code(factor, lo) != float(low):
                    raise ValueError(f'{factor.name} 的固定水平不能由编码值精确往返。')
                hi = lo
            else:
                if Fraction.from_float(lo) < low_exact:
                    lo = float(np.nextafter(lo, math.inf))
                if Fraction.from_float(hi) > high_exact:
                    hi = float(np.nextafter(hi, -math.inf))
                if lo >= hi or hi - lo <= 8 * math.ulp(max(1.0, abs(lo), abs(hi))):
                    raise ValueError(f'{factor.name} 的优化区间小于编码可分辨范围。')
                if _actual_for_code(factor, lo) < float(low):
                    raise ValueError(f'{factor.name} 的实际下限无法安全转换为编码值。')
                if _actual_for_code(factor, hi) > float(high):
                    raise ValueError(f'{factor.name} 的实际上限无法安全转换为编码值。')
            if not math.isfinite(lo) or not math.isfinite(hi) or lo > hi:
                raise ValueError(f'{factor.name} 的编码范围不可表示。')
            result[factor.factor_id] = (lo, hi)
            actual[factor.factor_id] = (low, high)
        return result, actual

    def _read_objective(self, name):
        value = self.response_settings[name]
        mode = _MODE.get(value['mode'])
        if mode is None:
            raise ValueError(f'{name} 的目标类型无效。')
        low = _finite(value['low'], f'{name} 低阈值')
        high = _finite(value['high'], f'{name} 高阈值')
        if low >= high:
            raise ValueError(f'{name} 的低阈值必须小于高阈值。')
        target = None
        if mode == 'target':
            target = _finite(value['target'], f'{name} 目标值')
            if not low < target < high:
                raise ValueError(f'{name} 的目标值须严格位于低、高阈值之间。')
        power_low = _finite(value['power_low'], f'{name} 低侧指数')
        power_high = _finite(value['power_high'], f'{name} 高侧指数')
        if mode == 'maximize':
            power_high = power_low
        elif mode == 'minimize':
            power_low = power_high
        weight = _finite(value['weight'], f'{name} 权重')
        if min(power_low, power_high, weight) <= 0:
            raise ValueError(f'{name} 的形状指数和权重必须大于零。')
        return {'mode': mode, 'low': low, 'high': high, 'target': target,
                'power_low': power_low, 'power_high': power_high, 'weight': weight}

    def _read_objectives(self):
        self._save_response()
        names = [self.response_list.get(i) for i in self.response_list.curselection()]
        if not names:
            raise ValueError('请选择至少一个响应。')
        return {name: self._read_objective(name) for name in names}

    def _update_run_state(self):
        self._save_response()
        try:
            self._read_bounds()
            self._read_objectives()
        except (ValueError, TypeError, OverflowError) as exc:
            self.run_button.configure(state='disabled')
            self.status.set('待修正：' + str(exc))
        else:
            self.run_button.configure(state='normal')
            if self.status.get().startswith('待修正：'):
                self.status.set('')

    def _invalidate(self, message):
        if not hasattr(self, 'status'):
            return
        if self.last is not None:
            self.last = None
            self._clear_tables()
            self.plot_button.configure(state='disabled')
            self.source_info.set('来源：结果已清除，等待重新计算')
            self.status.set(message)

    def _clear_tables(self):
        for name in ('result_block', 'candidate_block'):
            block = getattr(self, name, None)
            if block is not None:
                block.destroy()
                setattr(self, name, None)

    def _capture_current(self):
        self.app.getCurrentTable()
        if self.owner.getCurrentTable() is not self.source:
            raise ValueError('来源工作表已切换，请切回来源表后重新优化。')
        self.owner._finish_edit()
        frame = self.owner._full_frame(self.source).copy(deep=True)
        metadata = deepcopy(self.source.doe_metadata)
        if metadata != self.metadata:
            raise ValueError('CCD 定义已更改，请关闭并重新打开优化窗口。')
        return frame, metadata

    def _verify_best(self, best, result, actual_bounds, coded_bounds):
        if not best.get('feasible'):
            raise ValueError('求解器返回的最佳候选不满足可行性要求。')
        codes = best['coded']
        levels = best['factor_levels']
        for factor in self.factors:
            code = float(codes[factor.factor_id])
            low, high = coded_bounds[factor.factor_id]
            actual = float(levels[factor.factor_id])
            actual_low, actual_high = map(Fraction, actual_bounds[factor.factor_id])
            if not math.isfinite(code) or not low <= code <= high:
                raise ValueError(f'{factor.name} 的编码建议超出用户边界。')
            if not math.isfinite(actual) or abs(float(factor.to_coded(actual)) - code) > 1e-8:
                raise ValueError(f'{factor.name} 的编码与实际建议值不一致。')
            if not actual_low <= Fraction.from_float(actual) <= actual_high:
                raise ValueError(f'{factor.name} 的实际建议超出用户边界。')
        from doe_rsm import model_matrix
        coded = np.asarray([[float(best['coded'][factor.factor_id]) for factor in self.factors]])
        design_row = model_matrix(coded)
        for name, model in result['models'].items():
            prediction = float((design_row @ model['coefficients'])[0])
            reported = float(best['predictions'][name])
            if not math.isfinite(prediction) or not math.isfinite(reported) or not np.isclose(
                    prediction, reported, rtol=1e-12, atol=np.finfo(float).eps * max(1., abs(prediction)) * 8):
                raise ValueError(f'{name} 的候选预测与完整二次模型不一致。')

    def optimize(self):
        self._save_response()
        self._clear_tables()
        self.last = None
        self.plot_button.configure(state='disabled')
        self.source_info.set('来源：正在读取绑定工作表快照')
        try:
            frame, metadata = self._capture_current()
            coded_bounds, actual_bounds = self._read_bounds()
            objectives = self._read_objectives()
            from doe_optimize import optimize_rsm
            result = optimize_rsm(frame, metadata, objectives, coded_bounds)
            candidates = result['candidates']
            candidate_headers = ('序号', '候选来源', '可行', '目标函数值', 'D', '编码点', '状态')
            candidate_values = [[
                index, candidate['candidate_type'], candidate['feasible'],
                candidate['objective_value'], candidate['composite_desirability'],
                ', '.join(f'{key}={_shown(value)}' for key, value in candidate['coded'].items()),
                candidate['status'],
            ]
                                for index, candidate in enumerate(candidates, 1)]
            candidate_display = [[
                str(index), candidate['candidate_type'],
                '是' if candidate['feasible'] else '否',
                '' if candidate['objective_value'] is None else _shown(candidate['objective_value']),
                '' if candidate['composite_desirability'] is None else
                _shown(candidate['composite_desirability']),
                ', '.join(f'{key}={_shown(value)}' for key, value in candidate['coded'].items()),
                candidate['status'],
            ]
                                 for index, candidate in enumerate(candidates, 1)]
            self.candidate_block = TableBlock(self.candidate_tab, StatTable(
                title='搜索候选', headers=candidate_headers, values=candidate_values,
                display=candidate_display,
                number_formats=['0', '@', '@', '0.0000000000000000',
                                '0.0000000000000000', '@', '@']), paginate=True)
            self.candidate_block.pack(fill='both', expand=True)
            if result['best'] is None or result['status'] == 'solver_failure':
                self.status.set('优化失败：' + (result.get('reason') or '求解器未返回候选。'))
                return
            best = result['best']
            self._verify_best(best, result, actual_bounds, coded_bounds)
            if result['status'] not in (
                    'success', 'infeasible', 'zero_desirability', 'numerical_underflow'):
                self.status.set('优化失败：' + result['status'])
                return
            self.last = {'result': result, 'frame': frame, 'metadata': metadata,
                         'actual_bounds': actual_bounds, 'coded_bounds': coded_bounds,
                         'objectives': objectives}
            self._show_best(best, actual_bounds, coded_bounds, objectives)
            method = ('确定性多起点 L-BFGS-B' if 'L-BFGS-B' in result['method']
                      else result['method'])
            failures = (f'，未收敛起点 {len(result["solver_failures"])}'
                        if result['solver_failures'] else '')
            self.source_info.set(
                f'来源：{self.owner.getCurrentSheet()}，快照 {result["snapshot_id"]}，'
                f'{method}，函数评价 {result["solver_evaluations"]}，'
                f'单起点上限 {result["evaluation_limit_per_start"]}，全局最优保证：'
                f'{"是" if result["global_optimum_guaranteed"] else "否"}{failures}')
            self.plot_response.configure(values=list(objectives))
            self.plot_response.set(next(iter(objectives)))
            self.plot_button.configure(
                state='normal' if result['status'] in ('success', 'infeasible') else 'disabled')
            self.status.set(result.get('reason') or '候选已就绪。')
        except (AttributeError, KeyError, TypeError, ValueError, RuntimeError,
                OverflowError, FloatingPointError) as exc:
            self.status.set('优化失败：' + str(exc))

    def _show_best(self, best, actual_bounds, coded_bounds, objectives):
        headers = ('类型', '名称', '编码建议', '实际值 / 预测', '实际边界 / 阈值',
                   '目标差值 / 极值', 'dᵢ', 'D', '边界状态')
        values, display = [], []
        for factor in self.factors:
            factor_id = factor.factor_id
            code = float(best['coded'][factor_id])
            lower, upper = coded_bounds[factor_id]
            tol = 8 * np.finfo(float).eps * max(1., abs(lower), abs(upper))
            side = '下限' if abs(code - lower) <= tol else '上限' if abs(code - upper) <= tol else '内部'
            unit = f' {factor.unit}' if factor.unit else ''
            values.append([
                '因子', f'{factor.factor_id} {factor.name}', code,
                _shown(best['factor_levels'][factor_id]) + unit,
                f'{_shown(actual_bounds[factor_id][0])} 至 {_shown(actual_bounds[factor_id][1])}{unit}',
                '', None, None, side])
            display.append([
                '因子', f'{factor.factor_id} {factor.name}', _shown(code),
                _shown(best['factor_levels'][factor_id]) + unit,
                f'{_shown(actual_bounds[factor_id][0])} 至 {_shown(actual_bounds[factor_id][1])}{unit}',
                '', '', '', side])
        for name, objective in objectives.items():
            mode_name = {'maximize': '最大化', 'minimize': '最小化', 'target': '逼近目标'}[
                objective['mode']]
            thresholds = f"{mode_name}：{_shown(objective['low'])} 至 {_shown(objective['high'])}"
            if objective['target'] is not None:
                thresholds += f"，目标 {_shown(objective['target'])}"
                difference = abs(best['predictions'][name] - objective['target'])
                shown_difference = (_shown(difference) if math.isfinite(difference)
                                    else '超出有限表示范围')
                if not math.isfinite(difference):
                    difference = None
            else:
                difference = '极大候选' if objective['mode'] == 'maximize' else '极小候选'
                shown_difference = difference
            values.append([
                '响应', name, None, best['predictions'][name], thresholds, difference,
                best['desirabilities'][name], best['composite_desirability'], '可行'])
            display.append([
                '响应', name, '', _shown(best['predictions'][name]), thresholds, shown_difference,
                _shown(best['desirabilities'][name]),
                _shown(best['composite_desirability']), '可行'])
        self.result_block = TableBlock(self.result_tab, StatTable(
            title='优化建议与响应预测', headers=headers, values=values, display=display,
            number_formats=['@', '@', '0.################', '@', '@',
                            '0.################', '0.################',
                            '0.################', '@']), paginate=True)
        self.result_block.pack(fill='both', expand=True)

    def _check_last(self):
        if self.last is None:
            raise ValueError('请先完成优化。')
        frame, metadata = self._capture_current()
        if not frame.equals(self.last['frame']) or metadata != self.last['metadata']:
            self._invalidate('来源数据已更新，请重新优化。')
            raise ValueError('来源数据已更新，请重新优化。')
        return self.last['result']

    def plot(self):
        try:
            result = self._check_last()
            response = self.plot_response.get()
            first_id, second_id = self.factor_x.get(), self.factor_y.get()
            ids = [factor.factor_id for factor in self.factors]
            if first_id == second_id or first_id not in ids or second_id not in ids:
                raise ValueError('请选择两个不同的因子。')
            first, second = ids.index(first_id), ids.index(second_id)
            best = result['best']
            bounds = self.last['coded_bounds']
            if (bounds[first_id][0] == bounds[first_id][1] or
                    bounds[second_id][0] == bounds[second_id][1]):
                raise ValueError('等高线需要两个未固定的因子。')
            x = np.linspace(*bounds[first_id], 60)
            y = np.linspace(*bounds[second_id], 60)
            xx, yy = np.meshgrid(x, y)
            coded = np.tile(np.asarray([[best['coded'][fid] for fid in ids]], dtype=float),
                            (xx.size, 1))
            coded[:, first], coded[:, second] = xx.ravel(), yy.ravel()
            from doe_rsm import model_matrix
            coefficients = result['models'][response]['coefficients']
            zz = (model_matrix(coded) @ coefficients).reshape(xx.shape)
            if self.viewer is not None:
                try:
                    if self.viewer.main.winfo_exists():
                        self.viewer.close()
                except tk.TclError:
                    pass
            viewer = self.app.showPlotViewer(deferred=True, figsize=(8, 6))
            self.viewer = viewer
            try:
                axis = viewer.fig.add_subplot(111)
                contour = axis.contourf(xx, yy, zz, levels=16, cmap='viridis')
                colorbar = viewer.fig.colorbar(contour, ax=axis)
                colorbar.set_label(response)
                axis.scatter([best['coded'][first_id]], [best['coded'][second_id]],
                             marker='*', s=130, color='red', edgecolor='white',
                             label='建议点')
                axis.set_xlabel(f'{first_id} 编码值')
                axis.set_ylabel(f'{second_id} 编码值')
                axis.legend()
                fixed = ', '.join(
                    f'{fid}={float(best["coded"][fid]):.6g}' for fid in ids
                    if fid not in (first_id, second_id)) or '无'
                viewer.fig.suptitle(
                    f'{response} 预测等高线，固定其余因子：{fixed}，快照 {result["snapshot_id"]}')
                from chart_style import font_families
                font = font_manager.FontProperties(family=font_families('Microsoft YaHei'))
                viewer.fig._suptitle.set_fontproperties(font)
                axis.xaxis.label.set_fontproperties(font)
                axis.yaxis.label.set_fontproperties(font)
                for label in axis.get_xticklabels() + axis.get_yticklabels():
                    label.set_fontproperties(font)
                for label in colorbar.ax.get_yticklabels():
                    label.set_fontproperties(font)
                colorbar.ax.yaxis.label.set_fontproperties(font)
                legend = axis.get_legend()
                if legend is not None:
                    for label in legend.get_texts():
                        label.set_fontproperties(font)
                viewer.canvas.draw()
                self.app.replacePlotViewer(viewer)
                viewer.main.deiconify()
            except Exception:
                viewer.close()
                self.viewer = None
                raise
        except (KeyError, TypeError, ValueError, RuntimeError, FloatingPointError) as exc:
            self.status.set('等高线不可用：' + str(exc))

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
