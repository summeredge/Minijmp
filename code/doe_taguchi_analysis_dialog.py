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
            values=('最大 S/N', '目标均值', '最小 SD') + (('目标斜率',) if self.dynamic else ()))
        self.best_metric.set('最大 S/N')
        self.best_metric.pack(side='left', padx=4)
        ttk.Label(best_bar, text='目标值').pack(side='left', padx=(10, 2))
        self.best_target = ttk.Entry(best_bar, width=10)
        self.best_target.pack(side='left')
        self.status = tk.StringVar(value='')
        ttk.Label(self.main, textvariable=self.status, wraplength=940,
                  anchor='w').pack(fill='x', padx=8)
        self.tabs = ttk.Notebook(self.main)
        self.tabs.pack(fill='both', expand=True, padx=8, pady=8)
        self.result = None
        self._restore_options()

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
            frame = self.owner._full_frame(self.source).copy(deep=True)
            choice = self.best_metric.get()
            metric = {'最大 S/N': 'sn', '目标均值': 'mean',
                      '最小 SD': 'sd', '目标斜率': 'slope'}[choice]
            target = (ccd_number(self.best_target.get())
                      if self.best_target.get().strip() else None)
            result = best_settings(frame, self.source.doe_metadata, self.response.get(),
                                   metric, target)
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
        ttk.Button(confirm, text='计算差值',
                   command=self.confirm).pack(side='left', padx=6)
        ttk.Label(body, text=result['assumption'], wraplength=780).pack(anchor='w')
        ttk.Button(body, text='关闭', command=self.main.destroy).pack(anchor='e')

    def _tab(self, title, headers, values):
        tab = ttk.Frame(self.tabs)
        self.tabs.add(tab, text=title)
        TableBlock(tab, StatTable(title=title, headers=headers, values=values),
                   paginate=True).pack(fill='both', expand=True)

    def _tabs(self):
        for tab in self.tabs.tabs():
            self.tabs.nametowidget(tab).destroy()
        result = self.result
        self._tab('推荐水平', ['因子', '推荐水平', '该水平 S/N', '该水平 Mean',
                              '并列水平'], [
            [row['factor_id'], result['best'][row['factor_id']],
             next(level['sn'] for level in row['levels']
                  if level['level'] == result['best'][row['factor_id']]),
             next(level['mean'] for level in row['levels']
                  if level['level'] == result['best'][row['factor_id']]),
             '、'.join(str(value) for value in
                      result['tied'][row['factor_id']]['levels'])]
            for row in result['table']['factors']])
        prediction_rows = [
            ['优化依据', result['metric']],
            ['目标值', result['target']],
            ['预测 Mean', result['predicted_mean']],
            ['预测 S/N', result['predicted_sn']],
            ['预测 SD', (result['predicted_sd'] if result['predicted_sd'] is not None
                         else '不可用')],
            ['预测斜率', result['predicted_slope']],
            ['已观测组合', '是' if result['is_observed'] else '否'],
            ['确认试验', '需要' if not result['is_observed'] else '可直接复核'],
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
                ['并列最优组合数', len(result['tied_combinations'])],
            ])
        self._tab('预测与确认', ['项目', '值'], prediction_rows)
        if result['search']:
            self._tab('目标最优组合', ['顺序', '控制设置', '预测值', '与目标差'], [
                [index, '；'.join(f'{key}={value}' for key, value
                                  in candidate['settings'].items()),
                 candidate['predicted'], candidate['distance']]
                for index, candidate in enumerate(result['tied_combinations'], 1)])

    def confirm(self):
        """确认差值与目标判定只在本窗口计算，不写回原始正交表。"""
        try:
            observed = ccd_number(self.confirm_value.get())
            text = self.confirm_tolerance.get().strip()
            tolerance = ccd_number(text) if text else None
            if tolerance is not None and tolerance < 0:
                raise ValueError('判定容差不能为负')
            from doe_taguchi_analysis import best_settings
            self.owner.owner._finish_edit()
            frame = self.owner.owner._full_frame(self.owner.source).copy(deep=True)
            self.result = best_settings(
                frame, self.owner.source.doe_metadata, self.owner.response.get(),
                self.result['metric'], self.result['target'], observed, tolerance)
        except (ValueError, TypeError, RuntimeError, OverflowError) as error:
            messagebox.showerror('Taguchi', str(error), parent=self.main)
            return False
        self._tabs()
        return True


class NoiseTaguchi:
    """噪声条件稳健性：控制设定间 Mean/SD/S/N 与因子水平响应表。"""

    def __init__(self, owner, result):
        self.result = result
        self.main = tk.Toplevel(owner.main)
        self.main.title('Taguchi 噪声稳健性')
        self.main.geometry('860x560')
        body = ttk.Frame(self.main, padding=8)
        body.pack(fill='both', expand=True)
        ttk.Label(body, text=result['status'], wraplength=780).pack(anchor='w')
        self.tabs = ttk.Notebook(body)
        self.tabs.pack(fill='both', expand=True, pady=6)
        self._tab('控制设定', ['控制设定', '信号', '噪声条件数', 'Mean', 'SD', 'S/N'], [
            ['、'.join(f'{key}={value}' for key, value in row['settings'].items()),
             row['signal'], row['noise_count'], row['mean'], row['sd'], row['sn']]
            for row in result['rows']])
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
