"""Taguchi 分析界面：四类静态 S/N、动态回归、响应表、图形与最佳设置。"""
import tkinter as tk
from tkinter import messagebox, ttk

from doe_core import restore_design_result, validate_worksheet_metadata
from doe_dialog import ccd_number
from help_link import open_help
from sheet_context import SheetApp
from stat_table import StatTable, TableBlock


_STATIC_LABELS = {
    'Smaller is better': 'smaller',
    'Larger is better': 'larger',
    'Nominal is best (I)': 'nominal',
    'Nominal is best (II)': 'nominal_ii',
}


class AnalyzeTaguchi:
    def __init__(self, app):
        self.owner = app
        self.source = app.getCurrentTable()
        self.app = SheetApp(app, self.source)
        try:
            app._finish_edit()
            metadata = getattr(self.source, 'doe_metadata', None)
            if not metadata:
                raise ValueError('当前工作表没有有效的 DOE 元数据。')
            self.metadata = metadata
            self.frame = app._full_frame(self.source).copy(deep=True)
            self.design = restore_design_result(self.frame, metadata)
            if self.design.spec.design_type != 'taguchi':
                raise ValueError('当前工作表不是 Taguchi 设计。')
        except (AttributeError, KeyError, TypeError, ValueError, RuntimeError) as error:
            messagebox.showerror('Taguchi', str(error) or '当前工作表不是 Taguchi 设计。',
                                 parent=app.main)
            return
        self.dynamic = self.design.spec.taguchi['kind'] == 'dynamic'
        self.main = tk.Toplevel(app.main)
        self.main.title('分析 Taguchi 设计')
        self.main.geometry('980x680')
        self.main.bind('<F1>', lambda event: open_help('doe.taguchi', parent=self.main))
        controls = ttk.Frame(self.main, padding=8)
        controls.pack(fill='x')
        ttk.Label(controls, text='响应').pack(side='left')
        self.response = ttk.Combobox(
            controls, values=self.design.spec.response_names, state='readonly', width=14)
        self.response.set(self.design.spec.response_names[0])
        self.response.pack(side='left', padx=4)
        if self.dynamic:
            ttk.Label(controls, text='回归').pack(side='left', padx=(10, 2))
            self.reference_mode = ttk.Combobox(
                controls, values=('固定参考点', '自由截距'),
                state='readonly', width=14)
            self.reference_mode.set('自由截距')
            self.reference_mode.pack(side='left')
            ttk.Label(controls, text='参考信号').pack(side='left', padx=(10, 2))
            self.signal_reference = ttk.Entry(controls, width=8)
            self.signal_reference.pack(side='left')
            ttk.Label(controls, text='参考响应').pack(side='left', padx=(10, 2))
            self.response_reference = ttk.Entry(controls, width=8)
            self.response_reference.pack(side='left')
        else:
            ttk.Label(controls, text='S/N').pack(side='left', padx=(10, 2))
            self.sn_kind = ttk.Combobox(controls, values=tuple(_STATIC_LABELS),
                                        state='readonly', width=20)
            self.sn_kind.set('Smaller is better')
            self.sn_kind.pack(side='left')
        self.adjusted = tk.BooleanVar(value=False)
        ttk.Checkbutton(controls, text='adjusted', variable=self.adjusted).pack(
            side='left', padx=8)
        self.ln_sd = tk.BooleanVar(value=False)
        ttk.Checkbutton(controls, text='ln(s)', variable=self.ln_sd).pack(side='left')
        ttk.Button(controls, text='分析', command=self.analyze).pack(side='left', padx=8)
        ttk.Button(controls, text='图形', command=self.plot).pack(side='left')
        ttk.Button(controls, text='最佳设置', command=self.best).pack(side='left', padx=4)
        if self.design.spec.taguchi['noise_array_id'] is not None:
            ttk.Button(controls, text='噪声稳健性',
                       command=self.noise).pack(side='left')
        ttk.Button(controls, text='关闭', command=self.main.destroy).pack(side='right')
        best_bar = ttk.Frame(self.main, padding=(8, 0))
        best_bar.pack(fill='x')
        ttk.Label(best_bar, text='优化依据').pack(side='left')
        self.best_metric = ttk.Combobox(
            best_bar, state='readonly', width=12,
            values=('最大 S/N',) + (('先稳健后目标',) if not self.dynamic else ())
            + ('目标均值', '最小 SD')
            + (('目标斜率',) if self.dynamic else ()))
        self.best_metric.set('最大 S/N')
        self.best_metric.pack(side='left', padx=4)
        self.best_metric.bind('<<ComboboxSelected>>', self._best_mode_selected)
        ttk.Label(best_bar, text='目标值').pack(side='left', padx=(10, 2))
        self.best_target = ttk.Entry(best_bar, width=10)
        self.best_target.pack(side='left')
        ttk.Label(best_bar, text='最低 S/N').pack(side='left', padx=(10, 2))
        self.best_sn_threshold = ttk.Entry(best_bar, width=10)
        self.best_sn_threshold.pack(side='left')
        self.best_sn_threshold.configure(state='disabled')
        self.model_terms = None
        if not self.dynamic:
            model_bar = ttk.Frame(self.main, padding=(8, 0))
            model_bar.pack(fill='x')
            ttk.Button(model_bar, text='模型项', command=self.edit_model_terms).pack(side='left')
            self.model_terms_label = tk.StringVar(value='默认主效应')
            ttk.Label(model_bar, textvariable=self.model_terms_label).pack(side='left', padx=6)
            ttk.Label(model_bar, text='均值 CI').pack(side='left', padx=(12, 2))
            self.confidence = ttk.Combobox(
                model_bar, values=('90%', '95%', '99%'), state='readonly', width=6)
            self.confidence.set('95%')
            self.confidence.pack(side='left')
        self.status = tk.StringVar(value='')
        ttk.Label(self.main, textvariable=self.status, wraplength=940,
                  anchor='w').pack(fill='x', padx=8)
        self.tabs = ttk.Notebook(self.main)
        self.tabs.pack(fill='both', expand=True, padx=8, pady=8)
        self.result = None
        self._restore_options()

    def _best_mode_selected(self, event=None):
        self.best_sn_threshold.configure(
            state='normal' if self.best_metric.get() == '先稳健后目标' else 'disabled')

    def edit_model_terms(self):
        self.model_terms_dialog = TaguchiTermsDialog(self)

    def _restore_options(self):
        """恢复上次随工程保存的分析选项；缺失时保留界面默认值。"""
        saved = self.metadata.get('analysis')
        if not saved:
            return
        self.adjusted.set(saved['adjusted'])
        if self.dynamic:
            if saved['reference_mode'] == 'fixed':
                self.reference_mode.set('固定参考点')
                for entry, value in ((self.signal_reference, saved['reference'][0]),
                                     (self.response_reference, saved['reference'][1])):
                    entry.delete(0, 'end')
                    entry.insert(0, str(value))
        else:
            self.sn_kind.set(next(label for label, value in _STATIC_LABELS.items()
                                  if value == saved['sn_kind']))
            self.ln_sd.set(saved['ln_sd'])

    def _options(self):
        if self.dynamic:
            mode = 'fixed' if self.reference_mode.get() == '固定参考点' else 'free'
            reference = (None if mode == 'free' else
                         [ccd_number(self.signal_reference.get()),
                          ccd_number(self.response_reference.get())])
            return {'kind': 'dynamic', 'reference_mode': mode,
                    'reference': reference, 'adjusted': self.adjusted.get()}
        return {'kind': 'static', 'sn_kind': _STATIC_LABELS[self.sn_kind.get()],
                'adjusted': self.adjusted.get(), 'ln_sd': self.ln_sd.get()}

    def analyze(self):
        try:
            self.owner._finish_edit()
            if self.owner.getCurrentTable() is not self.source:
                raise ValueError('来源工作表已切换，请切回后重新分析。')
            frame = self.owner._full_frame(self.source).copy(deep=True)
            metadata = self.source.doe_metadata
            if self.dynamic:
                from doe_taguchi_analysis import analyze_dynamic
                reference = None
                mode = self.reference_mode.get()
                if mode != '自由截距':
                    signal = ccd_number(self.signal_reference.get())
                    response = ccd_number(self.response_reference.get())
                    reference = (signal, response)
                result = analyze_dynamic(frame, metadata, self.response.get(),
                                         reference, self.adjusted.get())
            else:
                from doe_taguchi_sn import analyze_static
                result = analyze_static(frame, metadata, self.response.get(),
                                        _STATIC_LABELS[self.sn_kind.get()],
                                        self.adjusted.get(), self.ln_sd.get())
            self.analysis_frame = frame
            self.metadata = validate_worksheet_metadata(frame, {
                **metadata, 'analysis': self._options()})
            self.source.doe_metadata = self.metadata
            self.publish(result)
        except (ValueError, TypeError, RuntimeError, OverflowError) as error:
            self.result = None
            self.status.set('分析失败：' + str(error))
            messagebox.showerror('Taguchi', str(error), parent=self.main)

    def show_table(self, title, headers, values):
        tab = ttk.Frame(self.tabs)
        self.tabs.add(tab, text=title)
        table = StatTable(title=title, headers=headers, values=values)
        TableBlock(tab, table, paginate=True).pack(fill='both', expand=True)
        self.app.print(table)

    def publish(self, result):
        for tab in self.tabs.tabs():
            self.tabs.nametowidget(tab).destroy()
        self.result = result
        self.status.set(f"响应 {result['response']}；{result['n_observations']} 条原始观测；"
                        + result['status'])
        if self.dynamic:
            self.show_table('动态拟合', ['控制设定', 'n', '斜率', '截距', 'MSE', 'df', '动态S/N'], [
                ['、'.join(f'{key}={value}' for key, value in row['settings'].items()),
                 row['n'], row['slope'], row['intercept'], row['mse'], row['df'], row['sn']]
                for row in result['combinations']])
            self._response_tabs(result['slope_table'], '斜率')
            self._response_tabs(result['response_table'], '动态 S/N')
        else:
            headers = (['控制设定', 'n', 'Mean', 'SD', 'ln(SD)', 'S/N']
                       if result['ln_sd'] else ['控制设定', 'n', 'Mean', 'SD', 'S/N'])
            self.show_table('组合统计', headers, [
                ['、'.join(f'{key}={value}' for key, value in row['settings'].items()),
                 row['n'], row['mean'], row['sd'],
                 *([row['ln_sd']] if result['ln_sd'] else []), row['sn']]
                for row in result['combinations']])
            self._response_tabs(result['response_table'], 'S/N')
            self.show_table('设定', ['项目', '值'], [
                ['S/N 类型', self.sn_kind.get()],
                ['adjusted', '是' if result['adjusted'] else '否'],
                ['ln(s)', '是' if result['ln_sd'] else '否'],
                ['原始观测数', result['n_observations']]])

    def _response_tabs(self, table, label):
        ln_sd = bool(self.result and self.result.get('ln_sd'))
        self.show_table(f'{label}响应表', ['因子', '水平', 'Mean',
                                          'ln(SD)' if ln_sd else 'SD', 'S/N', '效应', 'n'], [
            [row['factor_id'], level['level'], level['mean'],
             level.get('ln_sd') if ln_sd else level['sd'],
             level['sn'], level['effect'], level['n']]
            for row in table['factors'] for level in row['levels']])
        self.show_table(f'{label} Delta', ['因子', 'Delta', 'Rank'], [
            [row['factor_id'], row['delta'], row['rank']]
            for row in sorted(table['factors'], key=lambda item: item['rank'])])

    def noise(self):
        """噪声条件稳健性窗口；无噪声因子时不可达。"""
        try:
            from doe_taguchi_analysis import noise_robustness
            self.owner._finish_edit()
            self.app._check_table()
            frame = self.owner._full_frame(self.source).copy(deep=True)
            kind = ('smaller' if self.dynamic
                    else _STATIC_LABELS[self.sn_kind.get()])
            result = noise_robustness(frame, self.source.doe_metadata,
                                      self.response.get(), kind)
        except (ValueError, TypeError, RuntimeError, OverflowError) as error:
            messagebox.showerror('Taguchi', str(error), parent=self.main)
            return
        self.noise_window = NoiseTaguchi(self, result)

    def best(self):
        try:
            if self.result is None:
                raise ValueError('请先分析。')
            from doe_taguchi_analysis import best_settings
            self.owner._finish_edit()
            self.app._check_table()
            frame = self.owner._full_frame(self.source).copy(deep=True)
            choice = self.best_metric.get()
            selection_mode = None
            if choice == '最大 S/N':
                metric, selection_mode, target, threshold = 'sn', 'sn_maximum', None, None
            elif choice == '先稳健后目标':
                metric, selection_mode = 'sn', 'robust_then_target'
                target = ccd_number(self.best_target.get())
                threshold = ccd_number(self.best_sn_threshold.get())
            else:
                metric = {'目标均值': 'mean', '最小 SD': 'sd',
                          '目标斜率': 'slope'}[choice]
                target = (ccd_number(self.best_target.get())
                          if self.best_target.get().strip() else None)
                threshold = None
            result = best_settings(frame, self.source.doe_metadata, self.response.get(),
                                   metric, target, selection_mode=selection_mode,
                                   sn_threshold=threshold, model_terms=self.model_terms,
                                   confidence=(float(self.confidence.get().rstrip('%')) / 100
                                               if not self.dynamic else 0.95))
        except (ValueError, TypeError, RuntimeError, OverflowError) as error:
            messagebox.showerror('Taguchi', str(error), parent=self.main)
            return
        self.best_window = BestTaguchi(self, result)

    def plot(self):
        try:
            if self.result is None:
                raise ValueError('请先分析。')
            self.owner._finish_edit()
            if not self.source.model.df.equals(self.analysis_frame):
                raise ValueError('工作表已更改，请重新分析。')
            result = self.result
            viewer = self.app.showPlotViewer(deferred=True, figsize=(11, 7))
            try:
                from chart_style import font_families
                from matplotlib.font_manager import FontProperties
                font = FontProperties(family=font_families('Microsoft YaHei'))
                if self.dynamic:
                    axes = viewer.fig.subplots(2, 2)
                    for row in result['combinations'][:6]:
                        axes[0, 0].plot(row['signal'], row['response'], marker='o',
                                        linestyle='none')
                        span = [float(row['signal'].min()), float(row['signal'].max())]
                        axes[0, 0].plot(span, [row['intercept'] + row['slope'] * value
                                               for value in span], linewidth=1)
                    axes[0, 0].set_title('Signal vs Response')
                    axes[0, 0].set_xlabel('Signal')
                    axes[0, 0].set_ylabel('Response')
                    self._effect_panel(axes[0, 1], result['slope_table'], '斜率主效应')
                    self._effect_panel(axes[1, 0], result['response_table'], '动态 S/N 主效应')
                    residuals = [value for row in result['combinations']
                                 for value in (row['response'] - row['intercept']
                                               - row['slope'] * row['signal'])]
                    axes[1, 1].scatter(range(1, len(residuals) + 1), residuals)
                    axes[1, 1].axhline(0, color='gray')
                    axes[1, 1].set_title('残差（按观测顺序）')
                else:
                    axes = viewer.fig.subplots(2, 2)
                    self._effect_panel(axes[0, 0], result['response_table'], 'S/N 主效应')
                    self._effect_panel(axes[0, 1], result['response_table'], 'Mean 主效应',
                                       metric='mean')
                    self._effect_panel(axes[1, 0], result['response_table'], 'SD 主效应',
                                       metric='sd')
                    values = [row['sn'] for row in result['combinations']]
                    axes[1, 1].scatter(range(1, len(values) + 1), values)
                    axes[1, 1].set_title('各控制组合 S/N')
                    axes[1, 1].set_xlabel('控制组合')
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
        except (ValueError, RuntimeError) as error:
            messagebox.showerror('Taguchi', str(error), parent=self.main)

    @staticmethod
    def _effect_panel(axis, table, title, metric='sn'):
        for row in table['factors']:
            axis.plot(range(1, len(row['levels']) + 1),
                      [level[metric] for level in row['levels']], marker='o',
                      label=row['factor_id'])
        axis.set_title(title)
        axis.set_xticks(range(1, len(table['factors'][0]['levels']) + 1))
        axis.legend()


class TaguchiTermsDialog:
    """选择分类 OLS 模型中的主效应和可选双因子交互。"""

    def __init__(self, owner):
        self.owner = owner
        self.main = tk.Toplevel(owner.main)
        self.main.title('Taguchi 模型项')
        self.main.transient(owner.main)
        body = ttk.Frame(self.main, padding=8)
        body.pack(fill='both', expand=True)
        controls = [factor.factor_id for factor in owner.design.spec.factors
                    if factor.factor_id in owner.design.spec.taguchi['columns']]
        self.terms = [(factor_id,) for factor_id in controls]
        self.terms.extend((first, second) for index, first in enumerate(controls)
                          for second in controls[index + 1:])
        self.listbox = tk.Listbox(body, selectmode='extended', exportselection=False,
                                  height=16, width=34)
        scrollbar = ttk.Scrollbar(body, orient='vertical', command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=scrollbar.set)
        self.listbox.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        for term in self.terms:
            self.listbox.insert('end', ' × '.join(term))
        if owner.model_terms is None:
            for index in range(len(controls)):
                self.listbox.selection_set(index)
        else:
            selected = set(owner.model_terms)
            for index, term in enumerate(self.terms):
                if term in selected:
                    self.listbox.selection_set(index)
        buttons = ttk.Frame(self.main, padding=(8, 0, 8, 8))
        buttons.pack(fill='x')
        ttk.Button(buttons, text='默认主效应', command=self.default).pack(side='left')
        ttk.Button(buttons, text='应用', command=self.apply).pack(side='right')
        ttk.Button(buttons, text='取消', command=self.main.destroy).pack(side='right', padx=6)

    def default(self):
        self.owner.model_terms = None
        self.owner.model_terms_label.set('默认主效应')
        self.main.destroy()

    def apply(self):
        self.owner.model_terms = tuple(
            self.terms[index] for index in self.listbox.curselection())
        self.owner.model_terms_label.set(
            '仅截距' if not self.owner.model_terms else
            f'已选 {len(self.owner.model_terms)} 项')
        self.main.destroy()


class BestTaguchi:
    """最佳水平与确认实验建议；确认数据不写回原始设计。"""

    def __init__(self, owner, result):
        self.owner = owner
        self.result = result
        self.main = tk.Toplevel(owner.main)
        self.main.title('Taguchi 最佳设置预测')
        self.main.geometry('820x600')
        body = ttk.Frame(self.main, padding=8)
        body.pack(fill='both', expand=True)
        ttk.Label(body, text=f"指标 {result['metric']}；{result['status']}",
                  wraplength=780).pack(anchor='w')
        self.tabs = ttk.Notebook(body)
        self.tabs.pack(fill='both', expand=True, pady=6)
        self._tabs()
        confirm = ttk.Frame(body)
        confirm.pack(fill='x', pady=4)
        ttk.Label(confirm, text='确认实测响应').pack(side='left')
        self.confirm_value = ttk.Entry(confirm, width=12)
        self.confirm_value.pack(side='left', padx=4)
        ttk.Label(confirm, text='判定容差').pack(side='left', padx=(10, 2))
        self.confirm_tolerance = ttk.Entry(confirm, width=10)
        self.confirm_tolerance.pack(side='left')
        self.confirm_button = ttk.Button(confirm, text='计算差值', command=self.confirm)
        self.confirm_button.pack(side='left', padx=6)
        self.predict_button = ttk.Button(
            confirm, text='指定设置预测', command=self.predict_specific)
        self.predict_button.pack(side='left', padx=4)
        self.confirm_sheet_button = ttk.Button(
            confirm, text='创建确认实验工作表', command=self.create_confirmation_sheet)
        self.confirm_sheet_button.pack(side='left', padx=4)
        ttk.Label(body, text=result['assumption'], wraplength=780).pack(anchor='w')
        ttk.Button(body, text='关闭', command=self.main.destroy).pack(anchor='e')
        if result['best'] is None:
            self.confirm_value.configure(state='disabled')
            self.confirm_tolerance.configure(state='disabled')
            self.confirm_button.configure(state='disabled')
            self.confirm_sheet_button.configure(state='disabled')

    def _tab(self, title, headers, values):
        tab = ttk.Frame(self.tabs)
        self.tabs.add(tab, text=title)
        TableBlock(tab, StatTable(title=title, headers=headers, values=values),
                   paginate=True).pack(fill='both', expand=True)

    def _tabs(self):
        for tab in self.tabs.tabs():
            self.tabs.nametowidget(tab).destroy()
        result = self.result
        best = result['best']
        self._tab('推荐水平', ['因子', '推荐水平', '该水平 S/N', '该水平 Mean',
                              '并列水平'], [
            [row['factor_id'], best[row['factor_id']],
             next(level['sn'] for level in row['levels']
                  if level['level'] == best[row['factor_id']]),
             next(level['mean'] for level in row['levels']
                  if level['level'] == best[row['factor_id']]),
             '、'.join(str(value) for value in
                      result['tied'][row['factor_id']]['levels'])]
            for row in result['table']['factors'] if best is not None])
        prediction_rows = [
            ['优化依据', result['selection_mode'] or result['metric']],
            ['目标值', result['target']],
            ['最低 S/N', result['sn_threshold']],
            ['预测 Mean', result['predicted_mean']],
            ['均值 CI', (f"{result['mean_ci']['ci_low']:.6g}–"
                       f"{result['mean_ci']['ci_high']:.6g}"
                       if result['mean_ci']['status'] == '可用' else
                       result['mean_ci'].get('reason', '不可用'))],
            ['模型秩/参数', (f"{result['model']['rank']}/{result['model']['parameter_count']}"
                            if result.get('model') else '不可用')],
            ['残差自由度', result['model']['df'] if result.get('model') else None],
            ['预测 S/N', result['predicted_sn']],
            ['预测 SD', (result['predicted_sd'] if result['predicted_sd'] is not None
                         else '不可用')],
            ['预测斜率', result['predicted_slope']],
            ['已观测组合', {True: '是', False: '否', None: '无可用候选'}
             [result['is_observed']]],
            ['确认试验', ('无可用设置' if best is None else
                          '需要' if not result['is_observed'] else '可直接复核')],
            ['确认实测响应', result['confirmation']['observed']],
            ['实测-预测差', result['confirmation']['difference']],
            ['满足目标', ({True: '是', False: '否', None: '未填写'}
                         [result['confirmation']['meets_target']])]]
        if result['predicted_sd_reason']:
            prediction_rows.append(['SD 说明', result['predicted_sd_reason']])
        if result['search']:
            prediction_rows.extend([
                ['搜索方法', result['search']['method']],
                ['候选组合数', result['search']['candidate_count']],
                ['实际评价数', result['search']['evaluation_count']],
                ['停止原因', result['search']['stop_reason']],
                ['并列最优组合数', len(result['tied_combinations'])],
            ])
        self._tab('预测与确认', ['项目', '值'], prediction_rows)
        if result['search']:
            if result['selection_mode']:
                columns = (['顺序', '控制设置', '预测 Mean', '预测 S/N', '预测 SD']
                           + (['目标均值差'] if result['selection_mode'] ==
                              'robust_then_target' else []))
                values = []
                for index, candidate in enumerate(result['tied_combinations'], 1):
                    row = [index, '；'.join(f'{key}={value}' for key, value
                                            in candidate['settings'].items()),
                           candidate['predicted_mean'], candidate['predicted_sn'],
                           candidate['predicted_sd']]
                    if result['selection_mode'] == 'robust_then_target':
                        row.append(candidate['distance'])
                    values.append(row)
                self._tab('候选最优组合', columns, values)
            else:
                self._tab('目标最优组合', ['顺序', '控制设置', '预测值', '与目标差'], [
                    [index, '；'.join(f'{key}={value}' for key, value
                                      in candidate['settings'].items()),
                     candidate['predicted'], candidate['distance']]
                    for index, candidate in enumerate(result['tied_combinations'], 1)])

    def confirm(self):
        """确认差值与目标判定只在本窗口计算，不写回原始正交表。"""
        try:
            if self.result['best'] is None:
                raise ValueError('没有满足稳健性阈值的候选设置，不能进行确认实验判定')
            observed = ccd_number(self.confirm_value.get())
            text = self.confirm_tolerance.get().strip()
            tolerance = ccd_number(text) if text else None
            if tolerance is not None and tolerance < 0:
                raise ValueError('判定容差不能为负')
            from doe_taguchi_analysis import best_settings
            self.owner.owner._finish_edit()
            self.owner.app._check_table()
            frame = self.owner.owner._full_frame(self.owner.source).copy(deep=True)
            self.result = best_settings(
                frame, self.owner.source.doe_metadata, self.owner.response.get(),
                self.result['metric'], self.result['target'], observed, tolerance,
                selection_mode=self.result['selection_mode'],
                sn_threshold=self.result['sn_threshold'],
                model_terms=self.result.get('model_terms'),
                confidence=self.result.get('confidence', 0.95))
        except (ValueError, TypeError, RuntimeError, OverflowError) as error:
            messagebox.showerror('Taguchi', str(error), parent=self.main)
            return False
        self._tabs()
        return True

    def predict_specific(self):
        if not self.result.get('model'):
            messagebox.showerror('Taguchi', '当前模型没有可用的均值预测。', parent=self.main)
            return
        self.point_prediction = TaguchiPointPrediction(self)

    def create_confirmation_sheet(self):
        try:
            self.owner.owner._finish_edit()
            app = self.owner.owner
            source_name = next((name for name, table in app.sheets.items()
                                if table is self.owner.source), None)
            if source_name is None:
                raise ValueError('来源工作表已关闭，无法创建确认实验工作表')
            frame = app._full_frame(self.owner.source).copy(deep=True)
            from doe_taguchi_analysis import create_confirmation_frame
            plan = create_confirmation_frame(
                frame, self.owner.source.doe_metadata, self.result, source_name)
            app.addSheet(f'{source_name} 确认实验', plan, None)
        except (ValueError, TypeError, RuntimeError, OverflowError) as error:
            messagebox.showerror('Taguchi', str(error), parent=self.main)


class TaguchiPointPrediction:
    """按选定模型预测用户指定的控制水平组合。"""

    def __init__(self, owner):
        self.owner = owner
        self.main = tk.Toplevel(owner.main)
        self.main.title('Taguchi 指定设置预测')
        self.main.transient(owner.main)
        body = ttk.Frame(self.main, padding=8)
        body.pack(fill='both', expand=True)
        spec = owner.owner.design.spec
        best = owner.result['best'] or {}
        self.controls = [factor for factor in spec.factors
                         if factor.factor_id in spec.taguchi['columns']]
        self.levels = {}
        for index, factor in enumerate(self.controls):
            ttk.Label(body, text=factor.factor_id).grid(row=index, column=0, sticky='w', pady=2)
            value = ttk.Combobox(body, values=factor.levels, state='readonly', width=20)
            value.set(best.get(factor.factor_id, factor.levels[0]))
            value.grid(row=index, column=1, sticky='ew', pady=2)
            self.levels[factor.factor_id] = value
        self.output = tk.StringVar(value='')
        row = len(self.controls)
        ttk.Button(body, text='预测', command=self.predict).grid(row=row, column=1, sticky='e', pady=6)
        ttk.Label(body, textvariable=self.output, wraplength=520).grid(
            row=row + 1, column=0, columnspan=2, sticky='w')
        body.columnconfigure(1, weight=1)

    def predict(self):
        try:
            app = self.owner.owner.owner
            app._finish_edit()
            self.owner.owner.app._check_table()
            frame = app._full_frame(self.owner.owner.source).copy(deep=True)
            metadata = self.owner.owner.source.doe_metadata
            from doe_predict import snapshot_id
            expected = self.owner.result.get('source_snapshot_id')
            if expected and snapshot_id(frame, metadata) != expected:
                raise ValueError('来源试验数据已更改；请重新分析并生成最佳设置')
            from doe_taguchi_analysis import predict_taguchi_model
            result = predict_taguchi_model(
                frame, metadata,
                self.owner.owner.response.get(),
                {key: widget.get() for key, widget in self.levels.items()},
                self.owner.result.get('model_terms'), self.owner.result['confidence'])
        except (ValueError, TypeError, RuntimeError, OverflowError) as error:
            messagebox.showerror('Taguchi', str(error), parent=self.main)
            return False
        interval = result['intervals']
        ci = (f"{interval['confidence']:.0%} 均值 CI："
              f"[{interval['ci_low']:.6g}, {interval['ci_high']:.6g}]"
              if interval['status'] == '可用' else interval['reason'])
        self.output.set(f"预测值 {result['prediction']:.8g}；{ci}")
        return True


class NoiseTaguchi:
    """噪声条件稳健性：控制设定间 Mean/SD/S/N 与因子水平响应表。"""

    def __init__(self, owner, result):
        self.owner = owner
        self.result = result
        self.main = tk.Toplevel(owner.main)
        self.main.title('Taguchi 噪声稳健性')
        self.main.geometry('860x560')
        body = ttk.Frame(self.main, padding=8)
        body.pack(fill='both', expand=True)
        ttk.Label(body, text=result['status'], wraplength=780).pack(anchor='w')
        ttk.Button(body, text='响应模型法', command=self.response_model).pack(anchor='w', pady=(4, 0))
        self.tabs = ttk.Notebook(body)
        self.tabs.pack(fill='both', expand=True, pady=6)
        self._tab('控制设定', ['控制运行', '控制设定', '信号', '噪声条件数',
                              '观测数', 'Mean', 'SD', '噪声均值极差', 'S/N'], [
            [row['control_run_id'],
             '、'.join(f'{key}={value}' for key, value in row['settings'].items()),
             row['signal'], row['condition_count'], row['observation_count'],
             row['mean'], row['sd'], row['condition_mean_range'], row['sn']]
            for row in result['rows']])
        self._tab('噪声设置', ['控制运行', '噪声条件', '噪声设定', '重复', '标准序', '运行 ID',
                               '观测数', 'Mean', 'SD', '重复内极差'], [
            [row['control_run_id'], condition['condition_id'],
             '、'.join(f'{key}={value}' for key, value in condition['noise_settings'].items()),
             '、'.join(map(str, condition['replicates'])),
             '、'.join(map(str, condition['standard_orders'])),
             '、'.join(map(str, condition['run_ids'])), condition['n'],
             condition['mean'], condition['sd'], condition['response_range']]
            for row in result['rows'] for condition in row['noise_conditions']])
        table = result['response_table']
        self._tab('因子水平 S/N', ['因子', '水平', 'Mean', 'SD', 'S/N'], [
            [row['factor_id'], level['level'], level['mean'], level['sd'], level['sn']]
            for row in table['factors'] for level in row['levels']])
        self._tab('Delta/Rank', ['因子', 'Delta', 'Rank'], [
            [row['factor_id'], row['delta'], row['rank']]
            for row in sorted(table['factors'], key=lambda item: item['rank'])])
        ttk.Label(body, text=result['assumption'], wraplength=780).pack(anchor='w')
        ttk.Button(body, text='关闭', command=self.main.destroy).pack(anchor='e')

    def _tab(self, title, headers, values):
        tab = ttk.Frame(self.tabs)
        self.tabs.add(tab, text=title)
        TableBlock(tab, StatTable(title=title, headers=headers, values=values),
                   paginate=True).pack(fill='both', expand=True)

    def response_model(self):
        self.model_window = NoiseResponseModelTaguchi(self.owner)


class NoiseResponseModelTaguchi:
    """按所选控制×噪声交互拟合响应模型并搜索稳健设置。"""

    def __init__(self, owner):
        self.owner = owner
        self.main = tk.Toplevel(owner.main)
        self.main.title('Taguchi 噪声响应模型')
        self.main.geometry('820x600')
        body = ttk.Frame(self.main, padding=8)
        body.pack(fill='both', expand=True)
        controls = [factor.factor_id for factor in owner.design.spec.factors
                    if factor.factor_id in owner.design.spec.taguchi['columns']]
        noises = [factor.factor_id for factor in owner.design.spec.factors
                  if factor.factor_id in owner.design.spec.taguchi['noise_columns']]
        ttk.Label(body, text='控制×噪声项').pack(anchor='w')
        choices = ttk.Frame(body)
        choices.pack(fill='x')
        self.interactions = [(control, noise) for control in controls for noise in noises]
        self.listbox = tk.Listbox(choices, selectmode='extended', exportselection=False,
                                  height=7, width=28)
        scrollbar = ttk.Scrollbar(choices, orient='vertical', command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=scrollbar.set)
        self.listbox.pack(side='left', fill='x', expand=True)
        scrollbar.pack(side='left', fill='y')
        for control, noise in self.interactions:
            self.listbox.insert('end', f'{control} × {noise}')

        options = ttk.Frame(body)
        options.pack(fill='x', pady=4)
        ttk.Label(options, text='均值约束').pack(side='left')
        self.constraint_mode = ttk.Combobox(
            options, values=('无', '目标均值±容差', '均值范围'), state='readonly', width=14)
        self.constraint_mode.set('无')
        self.constraint_mode.pack(side='left', padx=4)
        self.constraint_mode.bind('<<ComboboxSelected>>', self._constraint_changed)
        ttk.Label(options, text='目标').pack(side='left', padx=(8, 2))
        self.target = ttk.Entry(options, width=9, state='disabled')
        self.target.pack(side='left')
        ttk.Label(options, text='容差 / 下限').pack(side='left', padx=(8, 2))
        self.lower = ttk.Entry(options, width=9, state='disabled')
        self.lower.pack(side='left')
        ttk.Label(options, text='上限').pack(side='left', padx=(8, 2))
        self.upper = ttk.Entry(options, width=9, state='disabled')
        self.upper.pack(side='left')
        self.fit_button = ttk.Button(options, text='拟合并搜索', command=self.fit)
        self.fit_button.pack(side='left', padx=8)

        self.status = tk.StringVar(value='')
        ttk.Label(body, textvariable=self.status, wraplength=790).pack(anchor='w')
        self.tabs = ttk.Notebook(body)
        self.tabs.pack(fill='both', expand=True, pady=6)
        ttk.Label(body, text='噪声水平组合等权；方差为模型预测均值在这些条件间的方差。',
                  wraplength=790).pack(anchor='w')

    def _constraint_changed(self, event=None):
        mode = self.constraint_mode.get()
        for entry, active in ((self.target, mode == '目标均值±容差'),
                              (self.lower, mode != '无'),
                              (self.upper, mode == '均值范围')):
            entry.configure(state='normal' if active else 'disabled')

    def _tab(self, title, headers, values):
        tab = ttk.Frame(self.tabs)
        self.tabs.add(tab, text=title)
        TableBlock(tab, StatTable(title=title, headers=headers, values=values),
                   paginate=True).pack(fill='both', expand=True)

    def fit(self):
        try:
            app = self.owner.owner
            app._finish_edit()
            self.owner.app._check_table()
            frame = app._full_frame(self.owner.source).copy(deep=True)
            selected = [self.interactions[index] for index in self.listbox.curselection()]
            mode = self.constraint_mode.get()
            if mode == '目标均值±容差':
                target_mean, tolerance = ccd_number(self.target.get()), ccd_number(self.lower.get())
                mean_range = None
            elif mode == '均值范围':
                target_mean, tolerance = None, None
                mean_range = (ccd_number(self.lower.get()), ccd_number(self.upper.get()))
            else:
                target_mean, tolerance, mean_range = None, None, None
            from doe_taguchi_analysis import noise_response_model
            result = noise_response_model(
                frame, self.owner.source.doe_metadata, self.owner.response.get(), selected,
                target_mean, tolerance, mean_range)
        except (ValueError, TypeError, RuntimeError, OverflowError) as error:
            self.status.set('模型分析失败：' + str(error))
            messagebox.showerror('Taguchi', str(error), parent=self.main)
            return False
        self.result = result
        for tab in self.tabs.tabs():
            self.tabs.nametowidget(tab).destroy()
        self.status.set(f"{result['status']}；秩 {result['rank']}/{result['parameter_count']}；"
                        f"残差 df={result['residual_df']}；"
                        f"{result['search'].get('optimality_scope', result['search']['stop_reason'])}")
        self._tab('系数', ['模型项', '估计值', '标准误', 't', 'p', '95% CI'], [
            [term, estimate,
             next((row['se'] for row in result['inference'] or ()
                   if row['term'] == term), None),
             next((row['t'] for row in result['inference'] or ()
                   if row['term'] == term), None),
             next((row['p'] for row in result['inference'] or ()
                   if row['term'] == term), None),
             (None if not result['inference'] else
              f"{next(row['ci_low'] for row in result['inference'] if row['term'] == term):.6g}–"
              f"{next(row['ci_high'] for row in result['inference'] if row['term'] == term):.6g}")]
            for term, estimate in (result['coefficients'] or {}).items()])
        self._tab('交互可估性', ['交互项', '状态'], [
            [row['interaction'], '可估' if row['estimable'] else '不可估/混杂']
            for row in result['interaction_estimability']])
        if result['residuals'] is not None:
            self._tab('残差', ['运行 ID', '拟合值', '残差'], [
                [row['run_id'], row['fitted'], row['residual']]
                for row in result['residuals']])
        self._tab('控制组合', ['最优', '控制设置', '预测 Mean', '预测 SD', '目标偏差', '已观测'], [
            ['✓' if row['settings'] == result['best'] else '',
             '；'.join(f'{key}={value}' for key, value in row['settings'].items()),
             row['predicted_mean'], row['predicted_sd'], row['target_deviation'],
             '是' if row['observed_control_setting'] else '否']
            for row in result['candidates']])
        return True
