"""最优设计选择、评价、修改、增补的 GUI 入口。"""
import tkinter as tk
from tkinter import messagebox, ttk

from doe_augment import augment
from doe_core import DesignSpec, FactorSpec, restore_design_result
from doe_custom import design_matrix, validate_custom
from doe_modify import modify_summary, renumber, replicate, reorder, rerandomize
from doe_optimal import evaluate, select, select_distance
from doe_optimal_design import optimal_from_candidates
from help_link import open_help


_PREVIEW_ROWS = 30


class OptimalDesignDialog:
    """候选工作表 → 模型项/准则 → 目标点数 → 预览 → 确认。"""

    def __init__(self, app):
        self.app = app
        self.main = tk.Toplevel(app.main)
        self.main.title('选择最优设计')
        self.main.transient(app.main)
        self.main.bind('<F1>', lambda event: open_help('doe.custom', parent=self.main))
        body = ttk.Frame(self.main, padding=10)
        body.pack(fill='both', expand=True)
        bar = ttk.Frame(body)
        bar.pack(fill='x')
        ttk.Label(bar, text='候选工作表').pack(side='left')
        self.sheet = ttk.Combobox(bar, values=tuple(app.sheets), state='readonly',
                                  width=22)
        self.sheet.set(app.getCurrentSheet())
        self.sheet.pack(side='left', padx=4)
        ttk.Label(bar, text='设计族').pack(side='left', padx=(10, 2))
        self.kind = ttk.Combobox(bar, values=('自定义因子', '自定义响应面'),
                                 state='readonly', width=12)
        self.kind.set('自定义因子')
        self.kind.pack(side='left')
        ttk.Label(bar, text='准则').pack(side='left', padx=(10, 2))
        self.criterion = ttk.Combobox(bar, values=('D-optimal', 'Distance-based'),
                                      state='readonly', width=14)
        self.criterion.set('D-optimal')
        self.criterion.pack(side='left')
        self.criterion.bind('<<ComboboxSelected>>', lambda event: self._kind_changed())
        self.kind.bind('<<ComboboxSelected>>', lambda event: self._kind_changed())
        ttk.Label(bar, text='目标点数').pack(side='left', padx=(10, 2))
        self.count = ttk.Entry(bar, width=6)
        self.count.insert(0, '8')
        self.count.pack(side='left')
        second = ttk.Frame(body)
        second.pack(fill='x', pady=4)
        ttk.Label(second, text='响应').pack(side='left')
        self.response = ttk.Combobox(second, state='readonly', width=14)
        self.response.pack(side='left', padx=4)
        ttk.Label(second, text='模型项（响应面必填）').pack(side='left', padx=(10, 2))
        self.terms = ttk.Entry(second, width=46)
        self.terms.pack(side='left')
        ttk.Label(second, text='seed').pack(side='left', padx=(10, 2))
        self.seed = ttk.Entry(second, width=6)
        self.seed.insert(0, '1')
        self.seed.pack(side='left')
        buttons = ttk.Frame(body)
        # 先按 side='bottom' 占位：窗口变小时压缩预览，按钮与状态始终可见。
        self.status = tk.StringVar(value='')
        ttk.Label(body, textvariable=self.status).pack(side='bottom', fill='x')
        buttons.pack(side='bottom', fill='x')
        self.preview = tk.Text(body, height=18, wrap='none')
        self.preview.pack(fill='both', expand=True, pady=4)
        ttk.Button(buttons, text='预览', command=self.preview_click).pack(side='left')
        ttk.Button(buttons, text='创建最优设计', command=self.create).pack(side='left', padx=6)
        ttk.Button(buttons, text='取消', command=self.main.destroy).pack(side='left')
        self._kind_changed()
        self.main.geometry('960x600')

    def _kind_changed(self):
        if self.kind.get() == '自定义因子':
            self.criterion.configure(values=('D-optimal',))
            self.criterion.set('D-optimal')
            self.criterion.configure(state='disabled')
        else:
            self.criterion.configure(values=('D-optimal', 'Distance-based'))
            self.criterion.configure(state='readonly')
            if self.criterion.get() == 'D-optimal':
                self.terms.insert(0, '')
        self.preview_click()

    def _data(self):
        table = self.app.sheets.get(self.sheet.get())
        if table is None:
            raise ValueError('候选工作表已关闭')
        metadata = getattr(table, 'doe_metadata', None)
        if not isinstance(metadata, dict):
            raise ValueError('候选工作表必须先定义为自定义设计')
        design = restore_design_result(self.app._full_frame(table), metadata)
        if design.spec.design_type not in ('custom_factorial', 'custom_rsm'):
            raise ValueError('当前最优设计只支持自定义因子或响应面候选工作表')
        return self.app._full_frame(table).copy(deep=True), metadata, design

    def _build(self):
        frame, metadata, design = self._data()
        expected_kind = 'custom_factorial' if self.kind.get() == '自定义因子' else 'custom_rsm'
        if design.spec.design_type != expected_kind:
            raise ValueError('设计族与候选工作表定义不一致')
        criterion = 'd_optimal' if self.criterion.get() == 'D-optimal' else 'distance'
        if criterion == 'distance' and expected_kind != 'custom_rsm':
            raise ValueError('Factorial 设计只支持 D-optimality')
        terms = [item.strip() for item in self.terms.get().split(';') if item.strip()]
        if expected_kind == 'custom_rsm' and not terms:
            terms = list(design.spec.model_terms)
        try:
            count = int(self.count.get())
            seed = int(self.seed.get())
        except ValueError as error:
            raise ValueError('目标点数与 seed 必须是整数') from error
        result, result_metadata, summary = optimal_from_candidates(
            frame, design_type=expected_kind, factors=design.spec.factors,
            responses=design.spec.response_names,
            column_map=metadata['column_map'], count=count,
            model_terms=terms, criterion=criterion, seed=seed,
            block_count=design.spec.block_count)
        return result, result_metadata, summary

    def _show(self, text):
        self.preview.delete('1.0', 'end')
        self.preview.insert('1.0', text)

    def preview_click(self):
        try:
            result, metadata, summary = self._build()
        except (ValueError, TypeError, OverflowError, KeyError) as error:
            self._show(f'预览不可用：{error}')
            self.status.set('预览不可用')
            return False
        lines = [f"候选数：{summary.get('candidates')}",
                 f"已选数：{summary.get('count')}",
                 f"方法：{summary.get('method', 'distance')}",
                 f"logdet：{summary.get('logdet')}",
                 f"矩阵秩：{summary.get('rank')} / {summary.get('p')}",
                 f"选中运行：{summary.get('selected_n')}；参数数："
                 f"{summary.get('selected_p')}；实际秩：{summary.get('selected_rank')}；"
                 + ('模型可估计' if summary.get('estimable') else '秩亏，模型不可估计'),
                 f"搜索预算：{summary.get('exact_budget')}；已评价子集："
                 f"{summary.get('evaluations')}；停止原因：{summary.get('stop_reason', '—')}",
                 '全局最优已证明：' + ('是' if summary.get('global_optimum_proven')
                                      else '否（启发式搜索，不宣称全局最优）'),
                 '']
        lines.append(' | '.join(str(column) for column in result.columns))
        for _, row in result.head(_PREVIEW_ROWS).iterrows():
            lines.append(' | '.join('' if value is None else str(value)
                                    for value in row))
        if len(result) > _PREVIEW_ROWS:
            lines.append(f'… 共 {len(result)} 行')
        self._show('\n'.join(lines))
        self.status.set('预览可用')
        return True

    def create(self):
        try:
            result, metadata, summary = self._build()
        except (ValueError, TypeError, OverflowError, KeyError) as error:
            messagebox.showerror('选择最优设计', str(error), parent=self.main)
            return False
        self.app.addSheet(f'{self.sheet.get()} 最优', result, {'doe': metadata})
        self.main.destroy()
        return True


class EvaluateDesignDialog:
    """固定设计与固定候选集的质量评价。"""

    def __init__(self, app):
        self.app = app
        table = app.getCurrentTable()
        metadata = getattr(table, 'doe_metadata', None)
        self.main = None
        if not isinstance(metadata, dict):
            messagebox.showerror('评价设计', '当前工作表不是 DOE 设计。', parent=app.main)
            return
        self.design = restore_design_result(app._full_frame(table), metadata)
        self.main = tk.Toplevel(app.main)
        self.main.title('评价设计')
        body = ttk.Frame(self.main, padding=10)
        body.pack(fill='both', expand=True)
        self.text = tk.Text(body, width=70, height=18)
        self.text.pack(fill='both', expand=True)
        ttk.Button(body, text='关闭', command=self.main.destroy).pack(anchor='e')
        self._show()

    def _show(self):
        lines = [f"设计：{self.design.spec.design_id}",
                 f"类型：{self.design.spec.design_type}",
                 f"运行数：{len(self.design.runs)}"]
        if self.design.spec.design_type in ('custom_factorial', 'custom_rsm'):
            matrix, model = design_matrix(self.design)
            summary = evaluate(matrix.tolist())
            lines.extend([
                f"模型项：{'; '.join(model.terms)}",
                f"参数数：{summary['p']}",
                f"矩阵秩：{summary['rank']}",
                f"条件数：{summary['condition']}",
                f"logdet(X'X)：{summary['logdet']}",
                f"det(X'X)：{summary['det_xtx']}",
                f"最小平方间距：{summary['min_squared_distance']}",
                '仅可与相同模型项和运行数的设计直接比较。'])
        else:
            lines.append('当前设计族不提供最优性准则评价。')
        self.text.delete('1.0', 'end')
        self.text.insert('1.0', '\n'.join(lines))


class ModifyDesignDialog:
    """修改设计：显示顺序与合法重新随机化。"""

    def __init__(self, app):
        self.app = app
        table = app.getCurrentTable()
        metadata = getattr(table, 'doe_metadata', None)
        if not isinstance(metadata, dict):
            messagebox.showerror('修改设计', '当前工作表不是 DOE 设计。', parent=app.main)
            return
        self.source = table
        self.metadata = metadata
        self.summary = modify_summary(app._full_frame(table), metadata)
        self.main = tk.Toplevel(app.main)
        self.main.title('修改设计')
        body = ttk.Frame(self.main, padding=10)
        body.pack(fill='both', expand=True)
        ttk.Label(body, text=f"类型：{self.summary['design_type']}　"
                             f"运行数：{self.summary['runs']}　"
                             f"seed：{self.summary['seed']}").pack(anchor='w')
        ttk.Label(body, text='seed').pack(anchor='w', pady=(8, 0))
        self.seed = ttk.Entry(body, width=10)
        self.seed.insert(0, str(self.summary['seed'] or 1))
        self.seed.pack(anchor='w')
        self.order = tk.StringVar(value='standard')
        ttk.Radiobutton(body, text='按标准序显示', variable=self.order,
                        value='standard').pack(anchor='w')
        ttk.Radiobutton(body, text='按运行序显示', variable=self.order,
                        value='run').pack(anchor='w')
        self.preview = tk.Text(body, height=8, width=78)
        self.status = tk.StringVar(value='取消不会修改当前工作簿。')
        ttk.Label(body, textvariable=self.status).pack(side='bottom', anchor='w')
        extra = ttk.Frame(body)
        extra.pack(side='bottom', fill='x')
        ttk.Label(extra, text='重复数').pack(side='left')
        self.rep_count = ttk.Entry(extra, width=4)
        self.rep_count.insert(0, '1')
        self.rep_count.pack(side='left', padx=4)
        ttk.Button(extra, text='增加完整重复', command=self.replicate).pack(side='left')
        buttons = ttk.Frame(body)
        buttons.pack(side='bottom', fill='x', pady=8)
        self.preview.pack(fill='both', expand=True, pady=(6, 0))
        ttk.Button(buttons, text='预览对照', command=self.preview_click).pack(side='left')
        ttk.Button(buttons, text='重新随机化', command=self.rerandomize).pack(side='left')
        ttk.Button(buttons, text='仅重排显示', command=self.reorder_only).pack(side='left', padx=6)
        ttk.Button(buttons, text='按标准序重编号', command=self.renumber).pack(side='left')
        ttk.Button(buttons, text='取消', command=self.main.destroy).pack(side='left')

    def _source_data(self):
        if self.app.getCurrentTable() is not self.source:
            raise ValueError('来源工作表已切换，请切回后重试')
        return self.app._full_frame(self.source).copy(deep=True), self.source.doe_metadata

    def preview_click(self):
        """显示修改前后对照；只在对话框内计算，不写入工作簿。"""
        try:
            frame, metadata = self._source_data()
            if self.order.get() == 'run':
                result, _ = reorder(frame, metadata, by='run')
                action = '按运行序重排显示'
            else:
                seed = int(self.seed.get())
                result, _ = rerandomize(frame, metadata, seed)
                action = f'以 seed={seed} 重新随机化'
        except (ValueError, TypeError, OverflowError, KeyError) as error:
            self.status.set('预览不可用：' + str(error))
            return False
        columns = metadata['column_map']
        before = list(zip(frame[columns['run_id']], frame[columns['run_order']]))
        after = list(zip(result[columns['run_id']], result[columns['run_order']]))
        # 按 run_id 对比：行位置会随显示重排改变，只有同一运行的运行序变化才算改动。
        original = {run_id: order for run_id, order in before}
        moved = sum(1 for run_id, order in after
                    if original.get(run_id) != order)
        head = lambda items: '  '.join(f'{run_id}@{order}' for run_id, order in items[:6])
        lines = [f'操作：{action}',
                 f'修改前（前 {min(6, len(before))} 行）：{head(before)}',
                 f'修改后（前 {min(6, len(after))} 行）：{head(after)}',
                 f'运行序变化：{moved}/{len(after)} 行；'
                 f'设定与响应列保持不变；运行数：{len(before)} → {len(after)}']
        self.preview.delete('1.0', 'end')
        self.preview.insert('1.0', '\n'.join(lines))
        self.status.set('预览可用；确认后写入新工作表，来源工作表不变。')
        return True

    def rerandomize(self):
        try:
            frame, metadata = self._source_data()
            seed = int(self.seed.get())
            result, result_metadata = rerandomize(frame, metadata, seed)
        except (ValueError, TypeError, OverflowError, KeyError) as error:
            messagebox.showerror('修改设计', str(error), parent=self.main)
            return False
        self.app.addSheet(f'{self.app.getCurrentSheet()} 重新随机化', result,
                          {'doe': result_metadata})
        self.main.destroy()
        return True

    def reorder_only(self):
        try:
            frame, metadata = self._source_data()
            result, result_metadata = reorder(frame, metadata, by=self.order.get())
        except (ValueError, TypeError, OverflowError, KeyError) as error:
            messagebox.showerror('修改设计', str(error), parent=self.main)
            return False
        self.app.addSheet(f'{self.app.getCurrentSheet()} 重排', result,
                          {'doe': result_metadata})
        self.main.destroy()
        return True

    def renumber(self):
        try:
            frame, metadata = self._source_data()
            result, result_metadata = renumber(frame, metadata)
        except (ValueError, TypeError, OverflowError, KeyError) as error:
            messagebox.showerror('修改设计', str(error), parent=self.main)
            return False
        self.app.addSheet(f'{self.app.getCurrentSheet()} 重编号', result,
                          {'doe': result_metadata})
        self.main.destroy()
        return True

    def replicate(self):
        try:
            frame, metadata = self._source_data()
            result, result_metadata = replicate(
                frame, metadata, count=int(self.rep_count.get()))
        except (ValueError, TypeError, OverflowError, KeyError) as error:
            messagebox.showerror('修改设计', str(error), parent=self.main)
            return False
        self.app.addSheet(f'{self.app.getCurrentSheet()} 完整重复', result,
                          {'doe': result_metadata})
        self.main.destroy()
        return True


class AugmentDesignDialog:
    """增补运行：固定父设计，从候选设置选择新增运行。"""

    def __init__(self, app):
        self.app = app
        table = app.getCurrentTable()
        metadata = getattr(table, 'doe_metadata', None)
        if not isinstance(metadata, dict):
            messagebox.showerror('增加运行', '当前工作表不是 DOE 设计。', parent=app.main)
            return
        self.source = table
        design = restore_design_result(app._full_frame(table), metadata)
        self.main = tk.Toplevel(app.main)
        self.main.title('增加运行')
        body = ttk.Frame(self.main, padding=10)
        body.pack(fill='both', expand=True)
        # 底部状态与按钮条先占位，窄窗口下压缩候选输入区而不隐藏操作。
        self.status = tk.StringVar(value='取消不会修改当前工作簿。')
        ttk.Label(body, textvariable=self.status).pack(side='bottom', anchor='w')
        bar = ttk.Frame(body)
        actions = ttk.Frame(body)
        actions.pack(side='bottom', fill='x', pady=6)
        bar.pack(side='bottom', fill='x')
        ttk.Label(body, text=f"来源：{design.spec.design_id}（{len(design.runs)} 运行）").pack(anchor='w')
        self.entries = {}
        grid = ttk.Frame(body)
        grid.pack(fill='x', pady=6)
        for index, factor in enumerate(design.spec.factors):
            ttk.Label(grid, text=factor.factor_id).grid(row=0, column=index, padx=2)
            widget = ttk.Entry(grid, width=12)
            widget.grid(row=1, column=index, padx=2)
            if factor.factor_type == 'continuous':
                widget.insert(0, str(factor.low))
            elif factor.levels:
                widget.insert(0, str(factor.levels[0]))
            self.entries[factor.factor_id] = (widget, factor)
        ttk.Label(body, text='候选设置（每行一组，逗号分隔；按因子顺序）').pack(anchor='w')
        # 候选输入是唯一可收缩区域：窗口变小时只压缩它，不挤出底部操作。
        self.candidates = tk.Text(body, height=4, width=70)
        self.candidates.pack(fill='both', expand=False)
        ttk.Label(bar, text='新增数量').pack(side='left')
        self.count = ttk.Entry(bar, width=6)
        self.count.insert(0, '1')
        self.count.pack(side='left', padx=4)
        ttk.Label(bar, text='批次 ID').pack(side='left', padx=(10, 2))
        self.batch = ttk.Entry(bar, width=10)
        self.batch.insert(0, 'AUG1')
        self.batch.pack(side='left')
        ttk.Label(bar, text='准则').pack(side='left', padx=(10, 2))
        self.criterion = ttk.Combobox(bar, state='readonly', width=16)
        # 距离准则只在响应面父设计上可用；因子设计仅 D-optimal。
        if design.spec.design_type == 'custom_rsm':
            self.criterion.configure(values=('D-optimal', 'Distance-based',
                                             '按输入顺序'))
        else:
            self.criterion.configure(values=('D-optimal', '按输入顺序'))
        self.criterion.set('D-optimal')
        self.criterion.pack(side='left')
        ttk.Label(bar, text='点类型').pack(side='left', padx=(10, 2))
        self.point_type = ttk.Combobox(
            bar, values=('factorial', 'center', 'axial', 'edge'),
            state='readonly', width=10)
        self.point_type.set('factorial')
        self.point_type.pack(side='left')
        ttk.Button(actions, text='增加运行', command=self.create).pack(side='left', padx=8)
        ttk.Button(actions, text='取消', command=self.main.destroy).pack(side='left')
        self.design = design

    def _candidates(self):
        rows = []
        for line in self.candidates.get('1.0', 'end').splitlines():
            values = [item.strip() for item in line.split(',') if item.strip()]
            if not values:
                continue
            if len(values) != len(self.design.spec.factors):
                raise ValueError('候选设置的数值数量必须与因子数一致')
            settings = {}
            for value, factor in zip(values, self.design.spec.factors):
                if factor.factor_type == 'categorical':
                    if value not in factor.levels:
                        raise ValueError(f'因子 {factor.factor_id} 的水平无效')
                    settings[factor.factor_id] = value
                else:
                    settings[factor.factor_id] = float(value)
            rows.append(settings)
        if not rows:
            raise ValueError('请至少输入一组候选设置')
        return rows

    def create(self):
        try:
            if self.app.getCurrentTable() is not self.source:
                raise ValueError('来源工作表已切换，请切回后重试')
            frame = self.app._full_frame(self.source).copy(deep=True)
            candidates = self._candidates()
            count = int(self.count.get())
            result, metadata, summary = augment(
                frame, self.source.doe_metadata, candidates, count,
                batch_id=self.batch.get().strip() or 'AUG1',
                criterion={'Distance-based': 'distance', '按输入顺序': 'manual'}.get(
                    self.criterion.get(), 'd_optimal'),
                point_types=[self.point_type.get()] * len(candidates))
        except (ValueError, TypeError, OverflowError, KeyError) as error:
            messagebox.showerror('增加运行', str(error), parent=self.main)
            return False
        self.app.addSheet(f'{self.app.getCurrentSheet()} 增补', result,
                          {'doe': metadata})
        self.main.destroy()
        return True
