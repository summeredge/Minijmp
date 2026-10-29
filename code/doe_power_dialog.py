"""DOE 功效与样本量窗口。"""

from copy import deepcopy
import tkinter as tk
from tkinter import messagebox, ttk

from doe_core import restore_design_result
from doe_power import calculate_power
from help_link import open_help
from sheet_context import SheetApp


_SUPPORTED_DESIGNS = {
    "two_level_full", "two_level_fractional", "plackett_burman",
    "general_full_factorial",
}


def _power_design_matrix(frame, metadata, design):
    spec = design.spec
    if spec.design_type not in _SUPPORTED_DESIGNS:
        raise ValueError("仅支持两水平全因子、正规部分因子、PB 和两水平一般全因子设计。")
    if spec.design_type == "two_level_full":
        from doe_factorial import validate_factorial_design
        validate_factorial_design(frame, metadata)
    elif spec.design_type == "two_level_fractional":
        from doe_fractional import validate_fractional_design
        validate_fractional_design(frame, metadata)
    elif spec.design_type == "plackett_burman":
        from doe_pb import validate_pb
        validate_pb(design)
    else:
        from doe_general_factorial import validate_general_factorial
        validate_general_factorial(frame, metadata)
    if (spec.block_count is not None or spec.center_point_count not in (None, 0)
            or spec.randomization_unit != "run" or spec.error_structure != "fixed"
            or any(run.block is not None or run.point_type != "factorial"
                   for run in design.runs)):
        raise ValueError("功效分析不支持区组、中心点或裂区设计。")

    replicates = {run.replicate for run in design.runs}
    if None in replicates or not replicates:
        raise ValueError("设计快照必须保留完整重复编号")
    base_replicate = min(replicates)
    factors = spec.factors
    names = tuple(factor.factor_id for factor in factors)
    rows = []
    for run in design.runs:
        if run.replicate != base_replicate:
            continue
        row = []
        for factor in factors:
            value = run.settings[factor.factor_id]
            if factor.factor_type == "categorical":
                if len(factor.levels) != 2:
                    raise ValueError("仅支持所有因子均为两水平的设计。")
                coded = (-1.0 if value == factor.levels[0] else
                         1.0 if value == factor.levels[1] else None)
            else:
                coded = factor.to_coded(value)
                coded = -1.0 if coded == -1 else 1.0 if coded == 1 else None
            if coded is None:
                raise ValueError("设计快照包含非两水平的因子设定。")
            row.append(coded)
        rows.append(tuple(row))
    return rows, names


class DOEPowerDialog:
    def __init__(self, app):
        self.owner = app
        self.source = app.getCurrentTable()
        self.app = SheetApp(app, self.source)
        try:
            self.app._finish_edit(self.source)
            metadata = deepcopy(getattr(self.source, "doe_metadata", None))
            if not metadata:
                raise ValueError("当前工作表没有有效的 DOE 元数据。")
            frame = self.app._full_frame(self.source).copy(deep=True)
            design = restore_design_result(frame, metadata)
            _power_design_matrix(frame, metadata, design)
        except (AttributeError, KeyError, TypeError, ValueError, RuntimeError) as error:
            messagebox.showerror("DOE 功效分析", str(error), parent=app.main)
            return

        self.metadata_snapshot = metadata
        self.frame_snapshot = frame
        self.factors = design.spec.factors
        self.result = None
        self._snapshot_issue = ""
        self._snapshot_after = None
        self._sheet_binding = None

        self.main = tk.Toplevel(app.main)
        self.main.title("DOE 功效与样本量")
        self.main.geometry("700x500")
        self.main.transient(app.main)
        self.main.protocol("WM_DELETE_WINDOW", self.close)
        self.main.bind("<F1>", lambda event: open_help("doe.power", parent=self.main))

        inputs = ttk.LabelFrame(self.main, text="分析参数", padding=10)
        inputs.pack(fill="x", padx=10, pady=(10, 6))
        self.alpha = tk.StringVar(master=self.main, value="0.05")
        self.delta = tk.StringVar(master=self.main, value="1")
        self.sigma = tk.StringVar(master=self.main, value="1")
        self.tested_factor = tk.StringVar(
            master=self.main, value=self.factors[0].factor_id)
        for column, (label, variable) in enumerate((
                ("α", self.alpha), ("δ（高－低）", self.delta), ("σ", self.sigma))):
            ttk.Label(inputs, text=label).grid(row=0, column=column * 2,
                                              sticky="w", padx=(0, 4), pady=3)
            ttk.Entry(inputs, textvariable=variable, width=12).grid(
                row=0, column=column * 2 + 1, sticky="w", padx=(0, 14), pady=3)
        ttk.Label(inputs, text="目标因子").grid(row=1, column=0, sticky="w", pady=3)
        factor_choice = ttk.Combobox(
            inputs, textvariable=self.tested_factor,
            values=tuple(factor.factor_id for factor in self.factors),
            state="readonly", width=12)
        factor_choice.grid(row=1, column=1, sticky="w", pady=3)

        repeat_box = ttk.LabelFrame(self.main, text="重复数", padding=10)
        repeat_box.pack(fill="x", padx=10, pady=6)
        self.mode = tk.StringVar(master=self.main, value="fixed")
        self.repeats = tk.StringVar(master=self.main, value="2")
        self.target_power = tk.StringVar(master=self.main, value="0.8")
        ttk.Radiobutton(repeat_box, text="固定重复次数", variable=self.mode,
                        value="fixed").grid(row=0, column=0, sticky="w")
        self.repeats_entry = ttk.Entry(
            repeat_box, textvariable=self.repeats, width=10)
        self.repeats_entry.grid(row=0, column=1, sticky="w", padx=(6, 18))
        ttk.Radiobutton(repeat_box, text="目标功效", variable=self.mode,
                        value="target").grid(row=0, column=2, sticky="w")
        self.power_entry = ttk.Entry(
            repeat_box, textvariable=self.target_power, width=10)
        self.power_entry.grid(row=0, column=3, sticky="w", padx=6)

        actions = ttk.Frame(self.main, padding=(10, 2))
        actions.pack(fill="x")
        self.calculate_button = ttk.Button(actions, text="计算", command=self.calculate)
        self.calculate_button.pack(side="left")
        ttk.Button(actions, text="取消", command=self.close).pack(side="right")

        result_box = ttk.LabelFrame(self.main, text="结果", padding=10)
        result_box.pack(fill="both", expand=True, padx=10, pady=6)
        self.summary = tk.StringVar(master=self.main, value="尚未计算。")
        ttk.Label(result_box, textvariable=self.summary, anchor="nw",
                  justify="left", wraplength=650).pack(fill="x", anchor="nw")
        self.assumptions = tk.StringVar(master=self.main, value="")
        ttk.Label(result_box, textvariable=self.assumptions, anchor="nw",
                  justify="left", wraplength=650).pack(fill="both", expand=True,
                                                        anchor="nw", pady=(8, 0))
        self.status = tk.StringVar(master=self.main, value="")
        ttk.Label(self.main, textvariable=self.status, anchor="w",
                  wraplength=680).pack(fill="x", padx=10, pady=(0, 8))

        for variable in (self.alpha, self.delta, self.sigma, self.tested_factor,
                         self.mode, self.repeats, self.target_power):
            variable.trace_add("write", self._inputs_changed)
        self.mode.trace_add("write", self._update_mode)
        self._update_mode()
        notebook = getattr(app, "nb", None)
        if notebook is not None:
            self._sheet_binding = notebook.bind(
                "<<NotebookTabChanged>>", self._source_changed, add="+")
        self._schedule_snapshot_check()

    def _inputs_changed(self, *_):
        self._clear_result()
        if not self._snapshot_issue:
            self.status.set("参数已更改，旧结果已清除。")

    def _update_mode(self, *_):
        fixed = self.mode.get() == "fixed"
        self.repeats_entry.configure(state="normal" if fixed else "disabled")
        self.power_entry.configure(state="disabled" if fixed else "normal")

    def _clear_result(self):
        self.result = None
        self.summary.set("尚未计算。")
        self.assumptions.set("")

    def _source_changed(self, _event=None):
        self._check_live_snapshot()

    def _check_live_snapshot(self):
        if not self.main.winfo_exists():
            return
        try:
            active = self.owner.getCurrentTable() is self.source
        except (AttributeError, RuntimeError, tk.TclError):
            active = False
        if not active:
            self._clear_result()
            self._snapshot_issue = "source"
            self.status.set("来源工作表已切换；旧结果已清除。切回来源表后可重新计算。")
            self.calculate_button.configure(state="disabled")
            return

        try:
            current_metadata = deepcopy(getattr(self.source, "doe_metadata", None))
            current_frame = self.app._full_frame(self.source)
            metadata_matches = current_metadata == self.metadata_snapshot
            frame_matches = current_frame.equals(self.frame_snapshot)
        except (AttributeError, KeyError, RuntimeError, TypeError, ValueError,
                tk.TclError):
            metadata_matches = frame_matches = False

        if not metadata_matches:
            issue = "metadata"
            message = "DOE 元数据已变化；旧结果已清除，请重新打开功效窗口。"
        elif not frame_matches:
            issue = "data"
            message = "工作表数据已变化；旧结果已清除，重新计算将校验当前快照。"
        else:
            issue = ""
            message = ("来源已恢复；旧结果已清除，请重新计算。"
                       if self._snapshot_issue == "source" else "")

        if issue:
            self._clear_result()
            if issue != self._snapshot_issue:
                self.status.set(message)
        elif self._snapshot_issue:
            self._clear_result()
            self.status.set(message)
        self._snapshot_issue = issue
        self.calculate_button.configure(
            state="normal" if metadata_matches else "disabled")

    def _schedule_snapshot_check(self):
        if self.main.winfo_exists():
            self._snapshot_after = self.main.after(1000, self._snapshot_tick)

    def _snapshot_tick(self):
        self._check_live_snapshot()
        self._schedule_snapshot_check()

    def calculate(self):
        self._clear_result()
        try:
            if self.owner.getCurrentTable() is not self.source:
                raise ValueError("来源工作表已切换，请切回来源表后重新计算。")
            self.app._finish_edit(self.source)
            frame = self.app._full_frame(self.source).copy(deep=True)
            metadata = deepcopy(getattr(self.source, "doe_metadata", None))
            if metadata != self.metadata_snapshot:
                raise ValueError("DOE 元数据已变化，请关闭并重新打开功效窗口。")
            design = restore_design_result(frame, metadata)
            design_points, factor_names = _power_design_matrix(frame, metadata, design)

            kwargs = ({"fixed_replicates": int(self.repeats.get())}
                      if self.mode.get() == "fixed" else
                      {"target_power": float(self.target_power.get())})
            result = calculate_power(
                design_points, factor_names, self.tested_factor.get(),
                float(self.delta.get()), float(self.sigma.get()),
                float(self.alpha.get()), **kwargs)

            if self.owner.getCurrentTable() is not self.source:
                raise ValueError("计算期间来源工作表已切换，结果已清除。")
            latest_frame = self.app._full_frame(self.source)
            latest_metadata = deepcopy(getattr(self.source, "doe_metadata", None))
            if latest_metadata != metadata or not latest_frame.equals(frame):
                raise ValueError("计算期间来源数据或 DOE 元数据已变化，结果已清除。")

            self.frame_snapshot = frame
            self.metadata_snapshot = metadata
            self.result = result
            df = result["df"]
            delta, sigma = float(self.delta.get()), float(self.sigma.get())
            self.summary.set(
                f"功效：{result['power']:.4%}\n"
                f"自由度：模型 {df['model']}，检验 {df['test']}，误差 {df['error']}\n"
                f"设计点：{len(design_points)}；重复次数：{result['replicates']}；"
                f"总运行数：{result['total_runs']}\n"
                f"方法：{result['method']}；目标因子：{self.tested_factor.get()}")
            assumptions = [
                f"效应假设：δ（高－低）={delta:g}；主效应系数 β=δ/2={delta / 2:g}。",
                f"噪声假设：误差标准差 σ={sigma:g}；显著性水平 α={float(self.alpha.get()):g}。",
                *result["assumptions"],
            ]
            self.assumptions.set("\n".join(assumptions))
            self._snapshot_issue = ""
            self.status.set("计算完成。")
        except (AttributeError, KeyError, TypeError, ValueError, RuntimeError,
                OverflowError, tk.TclError) as error:
            self._clear_result()
            self.status.set(f"计算失败：{error}")

    def close(self):
        if self._snapshot_after is not None:
            try:
                self.main.after_cancel(self._snapshot_after)
            except tk.TclError:
                pass
        notebook = getattr(self.owner, "nb", None)
        if notebook is not None and self._sheet_binding:
            try:
                notebook.unbind("<<NotebookTabChanged>>", self._sheet_binding)
            except tk.TclError:
                pass
        self.main.destroy()


def AnalyzeDOEPower(app):
    return DOEPowerDialog(app)
