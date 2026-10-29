"""DOE 因子设计变异性分析窗口。"""
from copy import deepcopy
from math import isfinite, log
from statistics import fmean
import tkinter as tk
from tkinter import messagebox, ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from chart_style import style_axes
from doe_core import restore_design_result
from doe_variability import analyze_variability
from help_link import open_help
from sheet_context import SheetApp
from stat_table import StatTable, TableBlock


_SUPPORTED_DESIGNS = {
    "two_level_full", "two_level_fractional", "general_full_factorial",
}
_STATUS_TEXT = {
    "missing_measurements": "存在缺失测量，不执行等权 ln(SD) 推断",
    "unequal_sample_sizes": "各组有效测量数不等，不执行等权 ln(SD) 推断",
    "insufficient_measurements": "至少一组有效测量少于 2，SD 不可计算",
    "zero_sd": "至少一组 SD 为 0，ln(SD) 模型不可用",
    "rank_deficient": "模型矩阵秩亏；保留拟合值，不报告唯一系数或 F/p",
    "saturated": "模型饱和且没有误差自由度；不报告 F/p",
    "zero_mse": "模型误差均方为 0；不报告 F/p",
}


class VariabilityDialog:
    def __init__(self, app):
        self.owner = app
        self.source = app.getCurrentTable()
        self.app = SheetApp(app, self.source)
        try:
            self.owner._finish_edit()
            frame = self.owner._full_frame(self.app.getCurrentTable()).copy(deep=True)
            metadata = deepcopy(getattr(self.source, "doe_metadata", None))
            if not metadata:
                raise ValueError("当前工作表没有 DOE 元数据")
            self.design = restore_design_result(frame, metadata)
            if self.design.spec.design_type not in _SUPPORTED_DESIGNS:
                raise ValueError("Variability 仅支持两水平全/部分因子及一般全因子的两水平子集")
            if len(self.design.spec.factors) < 2:
                raise ValueError("Variability 至少需要两个因子")
            response_map = metadata["column_map"]["responses"]
            self.responses = [name for name in self.design.spec.response_names
                              if name in response_map and response_map[name] in frame.columns]
            if not self.responses:
                raise ValueError("当前 DOE 设计没有可用的已声明响应列")
        except (AttributeError, KeyError, TypeError, ValueError, RuntimeError) as error:
            messagebox.showerror("DOE 变异性分析", str(error), parent=app.main)
            return

        self.main = tk.Toplevel(app.main)
        self.main.title("因子设计变异性分析")
        self.main.transient(app.main)
        self.main.resizable(True, True)
        self.main.protocol("WM_DELETE_WINDOW", self.close)
        self.main.bind("<F1>", lambda event: open_help("doe.variability", parent=self.main))

        controls = ttk.Frame(self.main, padding=8)
        controls.pack(side="top", fill="x")
        mode_bar = ttk.Frame(controls)
        mode_bar.pack(side="top", fill="x")
        self.mode = tk.StringVar(self.main, value="within_run")
        ttk.Radiobutton(mode_bar, text="同次运行多响应", variable=self.mode,
                        value="within_run", command=self._mode_changed).pack(side="left")
        ttk.Radiobutton(mode_bar, text="独立运行单响应", variable=self.mode,
                        value="independent_runs", command=self._mode_changed).pack(
                            side="left", padx=(12, 0))
        ttk.Label(controls, text="响应列").pack(side="top", anchor="w", pady=(6, 2))
        list_frame = ttk.Frame(controls)
        list_frame.pack(side="top", fill="x")
        self.response_list = tk.Listbox(
            list_frame, selectmode=tk.EXTENDED, exportselection=False,
            height=max(2, min(5, len(self.responses))), width=48)
        for name in self.responses:
            column = response_map[name]
            self.response_list.insert(
                tk.END, column if column == name else f"{column}（{name}）")
        self.response_list.pack(side="left", fill="x", expand=True)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical",
                                  command=self.response_list.yview)
        scrollbar.pack(side="right", fill="y")
        self.response_list.configure(yscrollcommand=scrollbar.set)
        self.response_list.bind("<<ListboxSelect>>", self._inputs_changed)

        self.status = tk.StringVar(value="")
        buttons = ttk.Frame(self.main, padding=8)
        buttons.pack(side="bottom", fill="x")
        ttk.Button(buttons, text="分析", command=self.analyze).pack(side="left")
        self.plot_button = ttk.Button(buttons, text="ln(SD) 主效应图",
                                      command=self.plot, state="disabled")
        self.plot_button.pack(side="left", padx=4)
        ttk.Button(buttons, text="取消", command=self.close).pack(side="right")
        ttk.Label(self.main, textvariable=self.status, anchor="w").pack(
            side="bottom", fill="x", padx=8)
        self.tabs = ttk.Notebook(self.main)
        self.tabs.pack(side="top", fill="both", expand=True, padx=8, pady=8)

        self.result = None
        self.data_snapshot = None
        self.metadata_snapshot = None
        self.analysis_design = None
        self.main_effects = []
        self.omitted_plot_groups = 0
        self.figure_canvas = None
        self.plot_tab = None
        self._poll_id = None
        self._sheet_binding = self.owner.nb.bind(
            "<<NotebookTabChanged>>", self._worksheet_changed, add="+")
        self.main.geometry("800x560")

    def _selected_responses(self):
        return tuple(self.responses[index] for index in self.response_list.curselection())

    def _mode_changed(self):
        selected = self.response_list.curselection()
        if self.mode.get() == "independent_runs":
            self.response_list.configure(selectmode=tk.SINGLE)
            self.response_list.selection_clear(0, tk.END)
            if selected:
                self.response_list.selection_set(selected[0])
        else:
            self.response_list.configure(selectmode=tk.EXTENDED)
        self._inputs_changed()

    def _inputs_changed(self, event=None):
        self._clear_results()
        self.status.set("")

    def _clear_tabs(self):
        if self.figure_canvas is not None:
            self.figure_canvas.get_tk_widget().destroy()
            self.figure_canvas = None
        for tab in self.tabs.tabs():
            widget = self.tabs.nametowidget(tab)
            self.tabs.forget(tab)
            widget.destroy()
        self.plot_tab = None

    def _clear_results(self):
        if self._poll_id is not None:
            try:
                self.main.after_cancel(self._poll_id)
            except tk.TclError:
                pass
            self._poll_id = None
        self.result = None
        self.data_snapshot = None
        self.metadata_snapshot = None
        self.analysis_design = None
        self.main_effects = []
        self.omitted_plot_groups = 0
        self.plot_button.configure(state="disabled")
        self._clear_tabs()

    def _source_matches(self, frame_snapshot, metadata_snapshot):
        try:
            table = self.app.getCurrentTable()
            if self.owner.getCurrentTable() is not table:
                return False
            live_metadata = getattr(table, "doe_metadata", None)
            if live_metadata != metadata_snapshot:
                return False
            live_frame = self.owner._full_frame(table)
            return live_frame.equals(frame_snapshot)
        except (AttributeError, KeyError, TypeError, ValueError, RuntimeError, tk.TclError):
            return False

    def _worksheet_changed(self, event=None):
        if (self.data_snapshot is not None
                and not self._source_matches(self.data_snapshot, self.metadata_snapshot)):
            self._clear_results()
            self.status.set("来源工作表已切换或发生变化；旧结果已清除，请重新分析。")

    def _check_snapshot(self):
        self._poll_id = None
        if not self.main.winfo_exists():
            return
        if self.data_snapshot is not None:
            if not self._source_matches(self.data_snapshot, self.metadata_snapshot):
                self._clear_results()
                self.status.set("来源工作表、数据或 DOE 元数据已变化；旧结果已清除，请重新分析。")
            else:
                self._poll_id = self.main.after(1000, self._check_snapshot)

    def _status_text(self, result):
        reasons = result.get("status_reasons", ())
        if not reasons:
            return result["status_message"]
        return "；".join(_STATUS_TEXT.get(reason, result["status_message"])
                         for reason in reasons)

    def analyze(self):
        self._clear_results()
        self.status.set("")
        try:
            if self.owner.getCurrentTable() is not self.source:
                raise ValueError("来源工作表已切换；请切回来源工作表后重新分析。")
            self.owner._finish_edit()
            if self.owner.getCurrentTable() is not self.source:
                raise ValueError("来源工作表已切换；请切回来源工作表后重新分析。")
            frame = self.owner._full_frame(self.app.getCurrentTable()).copy(deep=True)
            metadata = deepcopy(getattr(self.source, "doe_metadata", None))
            if not metadata:
                raise ValueError("当前工作表没有 DOE 元数据")
            responses = self._selected_responses()
            if not responses:
                raise ValueError("请选择至少一个已声明的响应列")
            mode = self.mode.get()
            if mode == "independent_runs" and len(responses) != 1:
                raise ValueError("独立运行重复只能选择一个响应列")
            design = restore_design_result(frame, metadata)
            result = analyze_variability(frame, metadata, responses, mode=mode)
            if not self._source_matches(frame, metadata):
                self.status.set("分析期间来源工作表、数据或 DOE 元数据已变化；结果未保留。")
                return
            self.data_snapshot = frame
            self.metadata_snapshot = metadata
            self.analysis_design = design
            self.result = result
            self.main_effects, self.omitted_plot_groups = self._calculate_main_effects(result)
            self._show_result(result)
            self.status.set(self._status_text(result))
            if self.main_effects:
                self.plot_button.configure(state="normal")
            self._poll_id = self.main.after(1000, self._check_snapshot)
        except (AttributeError, KeyError, TypeError, ValueError, RuntimeError) as error:
            self._clear_results()
            self.status.set(str(error))
            messagebox.showerror("DOE 变异性分析", str(error), parent=self.main)

    def _calculate_main_effects(self, result):
        effects = []
        omitted = sum(row["sd"] is None or row["sd"] <= 0
                      or not isfinite(row["sd"]) for row in result["summaries"])
        for factor in self.analysis_design.spec.factors:
            logged = {-1: [], 1: []}
            for row in result["summaries"]:
                sd = row["sd"]
                if sd is None or sd <= 0 or not isfinite(sd):
                    continue
                value = row["settings"][factor.factor_id]
                level = (factor.to_coded(value) if factor.factor_type == "continuous"
                         else -1 if value == factor.levels[0] else 1)
                if level in logged:
                    logged[level].append(log(sd))
            if logged[-1] and logged[1]:
                effects.append((factor.factor_id, fmean(logged[-1]), fmean(logged[1])))
        return effects, omitted

    def _add_table(self, title, headers, rows):
        tab = ttk.Frame(self.tabs)
        self.tabs.add(tab, text=title)
        TableBlock(tab, StatTable(title=title, headers=headers, values=rows),
                   paginate=True).pack(fill="both", expand=True)

    def _show_result(self, result):
        self._add_table("摘要", ["因子设定", "区组", "Mean", "SD", "N",
                                "missing", "run IDs"], [
            [", ".join(f"{name}={value}" for name, value in row["settings"].items()),
             row["block"], row["mean"], row["sd"], row["n"], row["missing"],
             ", ".join(map(str, row["run_ids"]))]
            for row in result["summaries"]
        ])

        fit = result["fit"]
        model_rows = [["推断状态", self._status_text(result)]]
        if fit is None:
            model_rows.append(["模型", "未拟合"])
        else:
            model_rows.extend([
                ["截距", fit["intercept"]], ["SSE", fit["sse"]],
                ["模型秩", fit["rank"]], ["误差自由度", fit["df_error"]],
                ["MSE", fit["mse"]],
            ])
            if fit["block_effects"]:
                model_rows.append(["参考区组", fit["block_reference"]])
                model_rows.extend([f"区组 {level} 效应", effect]
                                  for level, effect in fit["block_effects"].items())
        self._add_table("拟合", ["统计量", "值"], model_rows)
        if fit is not None:
            self._add_table("主效应检验", ["因子", "系数", "高-低效应", "SE",
                                         "调整 SS", "F", "p"], [
                [name, term["coefficient"], term["effect_high_minus_low"],
                 term["standard_error"], term["adjusted_ss"], term["f"], term["p"]]
                for name, term in fit["terms"].items()
            ])

    def plot(self):
        if self.result is None:
            return
        if not self._source_matches(self.data_snapshot, self.metadata_snapshot):
            self._clear_results()
            self.status.set("来源工作表、数据或 DOE 元数据已变化；旧结果已清除，请重新分析。")
            return
        if not self.main_effects:
            return
        if self.plot_tab is not None:
            if self.figure_canvas is not None:
                self.figure_canvas.get_tk_widget().destroy()
                self.figure_canvas = None
            self.tabs.forget(self.plot_tab)
            self.plot_tab.destroy()
        tab = ttk.Frame(self.tabs)
        self.tabs.add(tab, text="ln(SD) 主效应图")
        self.plot_tab = tab
        figure = Figure(figsize=(6.5, 4), dpi=100)
        axis = figure.add_subplot(111)
        for factor, low, high in self.main_effects:
            axis.plot(("低", "高"), (low, high), marker="o", label=factor)
        title = "ln(SD) 主效应图（可用组均值）"
        if self.omitted_plot_groups:
            title += f"；排除 {self.omitted_plot_groups} 个 SD 不可用组"
        axis.set_title(title)
        axis.set_xlabel("因子水平")
        axis.set_ylabel("平均 ln(SD)")
        axis.grid(axis="y", alpha=0.25)
        axis.legend(title="因子")
        style_axes(axis)
        figure.tight_layout()
        self.figure_canvas = FigureCanvasTkAgg(figure, master=tab)
        self.figure_canvas.draw()
        self.figure_canvas.get_tk_widget().pack(fill="both", expand=True)
        self.tabs.select(tab)

    def close(self):
        if self._poll_id is not None:
            try:
                self.main.after_cancel(self._poll_id)
            except tk.TclError:
                pass
            self._poll_id = None
        if self._sheet_binding is not None:
            try:
                self.owner.nb.unbind("<<NotebookTabChanged>>", self._sheet_binding)
            except tk.TclError:
                pass
            self._sheet_binding = None
        self.main.destroy()


def AnalyzeVariabilityDOE(app):
    return VariabilityDialog(app)
