"""最优设计选择、评价、修改、增补的 GUI 入口。"""
import tkinter as tk
from copy import deepcopy
from tkinter import messagebox, ttk

from doe_augment import augment, improve_fixed_size
from doe_core import DesignSpec, FactorSpec, _run_id_key as _run_key, restore_design_result
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
        operation_bar = ttk.Frame(body)
        operation_bar.pack(fill='x', pady=(0, 4))
        ttk.Label(operation_bar, text='操作').pack(side='left')
        self.operation = ttk.Combobox(
            operation_bar, values=('Select', 'Augment', 'Improve'),
            state='readonly', width=12)
        self.operation.set('Select')
        self.operation.pack(side='left', padx=4)
        self.operation.bind('<<ComboboxSelected>>', self._operation_changed)
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

    def _operation_changed(self, _event=None):
        if self.operation.get() == 'Select':
            return None
        dialog = (AugmentDesignDialog(self.app) if self.operation.get() == 'Augment'
                  else ImproveDesignDialog(self.app))
        if not hasattr(dialog, 'main'):
            return None
        self.operation_dialog = dialog
        self.main.destroy()
        return dialog

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


class ImproveDesignDialog:
    """在自定义因子或响应面父设计上做固定运行数 D-optimal 交换。"""

    def __init__(self, app):
        self.app = app
        self.sheet_names = tuple(
            name for name, table in app.sheets.items()
            if isinstance(getattr(table, 'doe_metadata', None), dict)
            and getattr(table, 'doe_metadata', {}).get('design', {}).get(
                'design_type') in ('custom_factorial', 'custom_rsm'))
        if len(self.sheet_names) < 2:
            messagebox.showerror(
                'Improve', '需要至少两个自定义因子或响应面工作表：一个父设计和一个候选设计。',
                parent=app.main)
            return
        self.main = tk.Toplevel(app.main)
        self.main.title('Improve D-optimal 设计')
        self.main.transient(app.main)
        self.main.minsize(760, 520)
        body = ttk.Frame(self.main, padding=10)
        body.pack(fill='both', expand=True)

        sources = ttk.Frame(body)
        sources.pack(fill='x')
        ttk.Label(sources, text='父设计').pack(side='left')
        self.parent_sheet = ttk.Combobox(
            sources, values=self.sheet_names, state='readonly', width=24)
        current = app.getCurrentSheet()
        parent_default = current if current in self.sheet_names else self.sheet_names[0]
        self.parent_sheet.set(parent_default)
        self.parent_sheet.pack(side='left', padx=4)
        ttk.Label(sources, text='候选设计').pack(side='left', padx=(12, 0))
        self.candidate_sheet = ttk.Combobox(
            sources, values=self.sheet_names, state='readonly', width=24)
        candidate_default = next(
            (name for name in self.sheet_names if name != parent_default), '')
        self.candidate_sheet.set(candidate_default)
        self.candidate_sheet.pack(side='left', padx=4)
        self.parent_sheet.bind('<<ComboboxSelected>>', self._parent_changed)
        self.candidate_sheet.bind('<<ComboboxSelected>>', self._candidate_changed)

        lists = ttk.Frame(body)
        lists.pack(fill='both', expand=True, pady=6)
        parent_box = ttk.LabelFrame(lists, text='父运行')
        parent_box.pack(side='left', fill='both', expand=True, padx=(0, 6))
        self.run_tree = ttk.Treeview(
            parent_box, columns=('run_id', 'state', 'response'), show='headings',
            selectmode='extended', height=8)
        for key, title, width in (('run_id', 'Run ID', 120),
                                  ('state', '状态', 85),
                                  ('response', '响应', 150)):
            self.run_tree.heading(key, text=title)
            self.run_tree.column(key, width=width, stretch=key == 'response')
        self.run_tree.pack(fill='both', expand=True, padx=4, pady=4)
        ttk.Button(parent_box, text='切换锁定/可替换',
                   command=self._toggle_runs).pack(anchor='w', padx=4, pady=(0, 4))

        candidate_box = ttk.LabelFrame(lists, text='未执行候选运行')
        candidate_box.pack(side='left', fill='both', expand=True)
        candidate_list = ttk.Frame(candidate_box)
        candidate_list.pack(fill='both', expand=True, padx=4, pady=4)
        self.candidate_runs = tk.Listbox(
            candidate_list, selectmode='extended', exportselection=False, height=8)
        candidate_scroll = ttk.Scrollbar(
            candidate_list, orient='vertical', command=self.candidate_runs.yview)
        self.candidate_runs.configure(yscrollcommand=candidate_scroll.set)
        self.candidate_runs.pack(side='left', fill='both', expand=True)
        candidate_scroll.pack(side='right', fill='y')

        search = ttk.Frame(body)
        search.pack(side='bottom', fill='x', pady=(4, 0))
        ttk.Label(search, text='Seed').pack(side='left')
        self.seed = ttk.Entry(search, width=8)
        self.seed.insert(0, '0')
        self.seed.pack(side='left', padx=(4, 14))
        ttk.Label(search, text='评价预算').pack(side='left')
        self.budget = ttk.Entry(search, width=10)
        self.budget.insert(0, '200000')
        self.budget.pack(side='left', padx=4)

        self.status = tk.StringVar(value='')
        ttk.Label(body, textvariable=self.status).pack(side='bottom', anchor='w')
        actions = ttk.Frame(body)
        actions.pack(side='bottom', fill='x', pady=5)
        ttk.Button(actions, text='预览', command=self.preview).pack(side='left')
        ttk.Button(actions, text='创建新工作表', command=self.create).pack(
            side='left', padx=6)
        ttk.Button(actions, text='取消', command=self.main.destroy).pack(side='left')
        self.preview_text = tk.Text(body, height=10, wrap='word', state='disabled')
        self.preview_text.pack(fill='both', expand=True, pady=(4, 0))

        self._parent_states = {}
        self._protected_parent_ids = set()
        self._parent_run_ids = {}
        self._candidate_run_ids = []
        self._loaded_parent = None
        self._parent_changed()
        self._candidate_changed()
        self.main.geometry('940x620')

    def _snapshot(self, sheet_name):
        table = self.app.sheets.get(sheet_name)
        if table is None:
            raise ValueError('父设计或候选工作表已关闭')
        self.app._finish_edit()
        frame = self.app._full_frame(table).copy(deep=True)
        metadata = deepcopy(getattr(table, 'doe_metadata', None))
        if not isinstance(metadata, dict):
            raise ValueError('所选工作表不是有效 DOE 设计')
        design = restore_design_result(frame, metadata)
        return table, frame, metadata, design

    @staticmethod
    def _has_experiment_data(run):
        return (any(value is not None for value in run.responses.values())
                or any(value is not None for value in run.measured_levels.values()))

    def _parent_changed(self, _event=None):
        self.run_tree.delete(*self.run_tree.get_children())
        self._parent_run_ids.clear()
        self._protected_parent_ids.clear()
        name = self.parent_sheet.get()
        if name != self._loaded_parent:
            self._parent_states = {}
            self._loaded_parent = name
        try:
            _, _, _, design = self._snapshot(name)
            for index, run in enumerate(sorted(
                    design.runs, key=lambda item: item.standard_order)):
                key = _run_key(run.run_id)
                protected = self._has_experiment_data(run)
                if protected:
                    self._protected_parent_ids.add(key)
                locked = protected or self._parent_states.get(key, False)
                self._parent_states[key] = locked
                iid = str(index)
                self._parent_run_ids[iid] = run.run_id
                response = '; '.join(
                    f'{name}={value}' for name, value in run.responses.items()
                    if value is not None) or '空'
                self.run_tree.insert(
                    '', 'end', iid=iid,
                    values=(run.run_id, '锁定' if locked else '可替换', response))
            self.status.set('已执行运行自动锁定；其他运行可切换为锁定。')
        except (ValueError, TypeError, KeyError) as error:
            self.status.set(str(error))

    def _candidate_changed(self, _event=None):
        self.candidate_runs.delete(0, 'end')
        self._candidate_run_ids = []
        try:
            _, _, _, design = self._snapshot(self.candidate_sheet.get())
            for run in sorted(design.runs, key=lambda item: item.standard_order):
                if self._has_experiment_data(run):
                    continue
                self._candidate_run_ids.append(run.run_id)
                self.candidate_runs.insert('end', str(run.run_id))
        except (ValueError, TypeError, KeyError) as error:
            self.status.set(str(error))

    def _toggle_runs(self):
        for iid in self.run_tree.selection():
            run_id = self._parent_run_ids[iid]
            key = _run_key(run_id)
            if key in self._protected_parent_ids:
                self.status.set(f'已执行运行 {run_id} 保持锁定，不可替换。')
                continue
            values = list(self.run_tree.item(iid, 'values'))
            locked = values[1] != '锁定'
            values[1] = '锁定' if locked else '可替换'
            self.run_tree.item(iid, values=values)
            self._parent_states[key] = locked

    def _partitions(self):
        locked, replaceable = [], []
        for iid, run_id in self._parent_run_ids.items():
            state = self.run_tree.item(iid, 'values')[1]
            (locked if state == '锁定' else replaceable).append(run_id)
        candidate_ids = tuple(
            self._candidate_run_ids[index]
            for index in self.candidate_runs.curselection())
        return tuple(locked), tuple(replaceable), candidate_ids

    def _build(self):
        if not self.parent_sheet.get() or not self.candidate_sheet.get():
            raise ValueError('请选择父设计和候选设计')
        if self.parent_sheet.get() == self.candidate_sheet.get():
            raise ValueError('父设计与候选设计必须是不同工作表')
        _, frame, metadata, _ = self._snapshot(self.parent_sheet.get())
        _, candidate_frame, candidate_metadata, _ = self._snapshot(
            self.candidate_sheet.get())
        locked, replaceable, candidate_ids = self._partitions()
        try:
            seed, budget = int(self.seed.get()), int(self.budget.get())
        except ValueError as error:
            raise ValueError('Seed 和评价预算必须是整数') from error
        return improve_fixed_size(
            frame, metadata, candidate_frame, candidate_metadata,
            locked, replaceable, candidate_ids, seed=seed,
            evaluation_budget=budget)

    def _show(self, value):
        self.preview_text.configure(state='normal')
        self.preview_text.delete('1.0', 'end')
        self.preview_text.insert('1.0', value)
        self.preview_text.configure(state='disabled')

    def preview(self):
        try:
            _, _, summary = self._build()
        except (ValueError, TypeError, OverflowError, KeyError) as error:
            self._show(f'预览不可用：{error}')
            self.status.set('预览不可用')
            return False
        stop_reason = {
            'no_improving_exchange': '无进一步改善交换',
            'evaluation_budget': '达到评价预算',
            'sweep_limit': '达到交换轮数上限',
            'no_replaceable_runs': '没有可替换运行',
        }.get(summary['stop_reason'], summary['stop_reason'])
        lines = [
            f"父设计：{summary['parent_design_id']}；候选设计："
            f"{summary['candidate_design_id']}",
            f"运行数：{summary['parent_n']} → {summary['current_n']}",
            f"Locked：{summary['locked_n']}；Replaceable：{summary['replaceable_n']}；"
            f"实际替换：{summary['replaced_n']}",
            f"模型秩：{summary['parent_rank']}/{summary['p']} → "
            f"{summary['rank']}/{summary['p']}；logdet："
            f"{summary['parent_logdet']:.12g} → {summary['current_logdet']:.12g}",
            f"方法：{summary['method']}；Seed：{summary['seed']}；评价："
            f"{summary['evaluations']}/{summary['evaluation_budget']}",
            f"停止原因：{stop_reason}；不保证全局最优。",
            '候选运行 → 新 Run ID → 被替换运行：',
        ]
        lines.extend(' → '.join(map(str, item))
                     for item in summary['candidate_to_replaced_parent'])
        if not summary['replaced_n']:
            lines.append('没有改善交换；新工作表保留父设计运行。')
        self._show('\n'.join(lines))
        self.status.set('预览可用')
        return True

    def create(self):
        try:
            result, metadata, _ = self._build()
        except (ValueError, TypeError, OverflowError, KeyError) as error:
            messagebox.showerror('Improve', str(error), parent=self.main)
            return False
        self.app.addSheet(f'{self.parent_sheet.get()} Improve', result,
                          {'doe': metadata})
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
        split_plot = self.summary['design_type'] == 'split_plot'
        ttk.Label(extra, text='新增完整区组数' if split_plot else '重复数').pack(side='left')
        self.rep_count = ttk.Entry(extra, width=4)
        self.rep_count.insert(0, '1')
        self.rep_count.pack(side='left', padx=4)
        self.replicate_button = ttk.Button(
            extra, text='增加完整区组' if split_plot else '增加完整重复',
            command=self.replicate)
        self.replicate_button.pack(side='left')
        if not self.summary['can_replicate']:
            self.replicate_button.configure(state='disabled')
            if self.summary.get('unavailable_reason'):
                self.status.set(self.summary['unavailable_reason'])
        buttons = ttk.Frame(body)
        buttons.pack(side='bottom', fill='x', pady=8)
        self.preview.pack(fill='both', expand=True, pady=(6, 0))
        ttk.Button(buttons, text='预览对照', command=self.preview_click).pack(side='left')
        self.rerandomize_button = ttk.Button(
            buttons, text='重新随机化', command=self.rerandomize)
        self.rerandomize_button.pack(side='left')
        if not self.summary['can_rerandomize']:
            self.rerandomize_button.configure(state='disabled')
        ttk.Button(buttons, text='仅重排显示', command=self.reorder_only).pack(side='left', padx=6)
        self.renumber_button = ttk.Button(buttons, text='按标准序重编号', command=self.renumber)
        self.renumber_button.pack(side='left')
        if not self.summary['can_renumber']:
            self.renumber_button.configure(state='disabled')
        self.cancel_button = ttk.Button(buttons, text='取消', command=self.main.destroy)
        self.cancel_button.pack(side='left')

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
        label = ('增加完整区组' if self.summary['design_type'] == 'split_plot'
                 else '完整重复')
        self.app.addSheet(f'{self.app.getCurrentSheet()} {label}', result,
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
        if design.spec.design_type == 'mixture':
            messagebox.showerror(
                '增加运行', 'Mixture 请使用“混料最优设计”窗口，避免按普通 DOE 矩阵增补。',
                parent=app.main)
            return
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
