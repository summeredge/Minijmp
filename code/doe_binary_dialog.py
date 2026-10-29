"""事件/试验格式的 DOE 二元响应分析窗口。"""
import copy
import tkinter as tk
from tkinter import messagebox, ttk

import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from chart_style import style_axes
from doe_binary_analysis import analyze_binary_doe, response_surface_probability_grid
from doe_core import restore_design_result
from help_link import open_help
from sheet_context import SheetApp
from stat_table import StatTable, TableBlock


_FAMILIES = {
    "screening": {"definitive_screening"},
    "factorial": {"two_level_full", "two_level_fractional",
                  "general_full_factorial", "plackett_burman"},
    "rsm": {"central_composite", "box_behnken", "custom_rsm"},
}


class BinaryAnalysisDialog:
    def __init__(self, app, family):
        self.owner = app
        self.family = family
        self.source = app.getCurrentTable()
        self.app = SheetApp(app, self.source)
        try:
            self.owner._finish_edit()
            frame = self.owner._full_frame(self.source).copy(deep=True)
            metadata = getattr(self.source, "doe_metadata", None)
            if not metadata:
                raise ValueError("当前工作表没有 DOE 元数据")
            design = restore_design_result(frame, metadata)
            if family not in _FAMILIES or design.spec.design_type not in _FAMILIES[family]:
                raise ValueError("当前 DOE 设计类型与分析入口不匹配")
            response_map = metadata["column_map"]["responses"]
            self.response_columns = list(response_map.values())
            if len(self.response_columns) < 2:
                raise ValueError("请在创建设计时声明事件数和试验数两个响应列")
        except (AttributeError, KeyError, TypeError, ValueError, RuntimeError) as error:
            messagebox.showerror("DOE 二元响应", str(error), parent=app.main)
            return

        self.design = design
        self.metadata = metadata
        self.main = tk.Toplevel(app.main)
        self.main.title({"screening": "DSD 二元响应分析",
                         "factorial": "Factorial 二元响应分析",
                         "rsm": "响应面二元响应分析"}[family])
        self.main.transient(app.main)
        self.main.resizable(True, True)
        self.main.protocol("WM_DELETE_WINDOW", self.close)
        self.main.bind("<F1>", lambda event: open_help("doe.binary", parent=self.main))

        controls = ttk.Frame(self.main, padding=8)
        controls.pack(side="top", fill="x")
        ttk.Label(controls, text="事件数").pack(side="left")
        self.events = ttk.Combobox(controls, values=self.response_columns,
                                   state="readonly", width=16)
        self.events.pack(side="left", padx=(4, 10))
        ttk.Label(controls, text="试验数").pack(side="left")
        self.trials = ttk.Combobox(controls, values=self.response_columns,
                                   state="readonly", width=16)
        self.trials.pack(side="left", padx=(4, 10))

        self.model_order = None
        self.screening_model = None
        self.screening_terms = None
        if family == "factorial":
            ttk.Label(controls, text="模型阶次").pack(side="left")
            self.model_order = ttk.Combobox(controls, values=("1", "2"),
                                            state="readonly", width=4)
            self.model_order.set("2")
            if self.design.spec.design_type in ("two_level_fractional", "plackett_burman"):
                self.model_order.set("1")
                self.model_order.configure(state="disabled")
            self.model_order.pack(side="left", padx=4)
            self.model_order.bind("<<ComboboxSelected>>", lambda event: self._inputs_changed())
        if family == "screening":
            bar = ttk.Frame(self.main, padding=(8, 0))
            bar.pack(side="top", fill="x")
            ttk.Label(bar, text="模型").pack(side="left")
            self.screening_model = ttk.Combobox(
                bar, values=("主效应", "主效应与平方", "自定义"),
                state="readonly", width=14)
            self.screening_model.set("主效应")
            self.screening_model.pack(side="left", padx=4)
            ttk.Label(bar, text="模型项").pack(side="left", padx=(8, 2))
            self.screening_terms = ttk.Entry(bar, width=36)
            self.screening_terms.pack(side="left")
            self.screening_model.bind("<<ComboboxSelected>>", lambda event: self._inputs_changed())
            self.screening_terms.bind("<KeyRelease>", lambda event: self._inputs_changed())
        elif family == "rsm" and self.design.spec.design_type != "custom_rsm":
            bar = ttk.Frame(self.main, padding=(8, 0))
            bar.pack(side="top", fill="x")
            ttk.Label(bar, text="模型").pack(side="left")
            self.model_order = ttk.Combobox(bar, values=("1", "2"),
                                            state="readonly", width=5)
            self.model_order.set("2")
            self.model_order.pack(side="left", padx=4)
            self.model_order.bind("<<ComboboxSelected>>", lambda event: self._inputs_changed())

        self.plot_factors = None
        if family == "rsm":
            continuous = [factor.factor_id for factor in design.spec.factors
                          if factor.factor_type == "continuous"]
            if len(continuous) >= 2:
                plot_bar = ttk.Frame(self.main, padding=(8, 0))
                plot_bar.pack(side="top", fill="x")
                ttk.Label(plot_bar, text="概率图因子").pack(side="left")
                self.factor_x = ttk.Combobox(plot_bar, values=continuous,
                                             state="readonly", width=8)
                self.factor_y = ttk.Combobox(plot_bar, values=continuous,
                                             state="readonly", width=8)
                self.factor_x.set(continuous[0])
                self.factor_y.set(continuous[1])
                self.factor_x.pack(side="left", padx=4)
                self.factor_y.pack(side="left")
                self.factor_x.bind("<<ComboboxSelected>>", lambda event: self._inputs_changed())
                self.factor_y.bind("<<ComboboxSelected>>", lambda event: self._inputs_changed())
                self.plot_factors = (self.factor_x, self.factor_y)

        buttons = ttk.Frame(self.main, padding=8)
        buttons.pack(side="bottom", fill="x")
        self.status = tk.StringVar(value="")
        ttk.Label(self.main, textvariable=self.status, anchor="w").pack(
            side="bottom", fill="x", padx=8)
        ttk.Button(buttons, text="分析", command=self.analyze).pack(side="left")
        ttk.Button(buttons, text="概率图", command=self.plot,
                   state="normal" if self.plot_factors else "disabled").pack(
                       side="left", padx=4)
        ttk.Button(buttons, text="取消", command=self.close).pack(side="right")
        self.tabs = ttk.Notebook(self.main)
        self.tabs.pack(side="top", fill="both", expand=True, padx=8, pady=8)
        self.result = None
        self.source_snapshot = None
        self.metadata_snapshot = None
        self.figure_canvas = None
        self.plot_tab = None
        self.events.bind("<<ComboboxSelected>>", lambda event: self._inputs_changed())
        self.trials.bind("<<ComboboxSelected>>", lambda event: self._inputs_changed())
        self._source_check_after = None
        self.main.geometry("900x610")
        self.main.grab_set()
        self._source_check_after = self.main.after(750, self._check_source)

    def _inputs_changed(self):
        self.result = None
        self.source_snapshot = None
        self.metadata_snapshot = None
        self.status.set("")
        self._clear_tabs()

    def _snapshot_is_current(self):
        return (
            self.owner.getCurrentTable() is self.source
            and getattr(self.source, "doe_metadata", None) == self.metadata_snapshot
            and self.owner._full_frame(self.source).equals(self.source_snapshot)
        )

    def _check_source(self):
        self._source_check_after = None
        try:
            if not self.main.winfo_exists():
                return
            if self.result is not None and not self._snapshot_is_current():
                self._inputs_changed()
                self.status.set("来源工作表或数据已变化；旧结果已清除，请重新分析。")
            self._source_check_after = self.main.after(750, self._check_source)
        except tk.TclError:
            return

    def _clear_tabs(self):
        if self.figure_canvas is not None:
            self.figure_canvas.get_tk_widget().destroy()
            self.figure_canvas = None
        for tab in self.tabs.tabs():
            widget = self.tabs.nametowidget(tab)
            self.tabs.forget(tab)
            widget.destroy()
        self.plot_tab = None

    def _selected_terms(self):
        if self.family != "screening":
            return None
        factors = self.design.spec.factors
        names = [factor.factor_id for factor in factors]
        choice = self.screening_model.get()
        if choice == "主效应":
            return [(name,) for name in names]
        if choice == "主效应与平方":
            return ([(name,) for name in names]
                    + [(factor.factor_id, factor.factor_id) for factor in factors
                       if factor.factor_type == "continuous"])
        if choice != "自定义":
            raise ValueError("请选择有效的 DSD 模型")
        terms = []
        for token in self.screening_terms.get().split(";"):
            token = token.strip().replace("²", "^2")
            if not token:
                continue
            if token.endswith("^2"):
                terms.append((token[:-2], token[:-2]))
            else:
                terms.append(tuple(part.strip() for part in token.split("*")))
        if not terms:
            raise ValueError("自定义模型至少需要一个模型项")
        return terms

    def analyze(self):
        self._inputs_changed()
        try:
            if self.owner.getCurrentTable() is not self.source:
                raise ValueError("来源工作表已切换；请重新打开分析窗口。")
            self.owner._finish_edit()
            frame = self.owner._full_frame(self.source).copy(deep=True)
            order = int(self.model_order.get()) if self.model_order is not None else 1
            result = analyze_binary_doe(
                frame, self.metadata, self.events.get(), self.trials.get(),
                self.family, model_order=order, selected_terms=self._selected_terms())
            self.result = result
            self.source_snapshot = frame.copy(deep=True)
            self.metadata_snapshot = copy.deepcopy(self.metadata)
            self._show_result(result)
            self.status.set(
                f"{result['fit_status']}；{result['n_runs']} 个运行，{result['n_trials']} 次试验；"
                f"模型 df={result['model_df']}，残差 df={result['residual_df']}。"
            )
        except (AttributeError, KeyError, TypeError, ValueError, RuntimeError) as error:
            self.result = None
            self._clear_tabs()
            self.status.set(str(error))
            messagebox.showerror("DOE 二元响应", str(error), parent=self.main)

    def _add_table(self, title, headers, rows):
        tab = ttk.Frame(self.tabs)
        self.tabs.add(tab, text=title)
        TableBlock(tab, StatTable(title=title, headers=headers, values=rows),
                   paginate=True).pack(fill="both", expand=True)

    def _show_result(self, result):
        self._clear_tabs()
        self._add_table("模型", ["统计量", "值"], [
            ["方法", "二项 Logistic（logit）"],
            ["设计行数", result["n_runs"]], ["总试验数", result["n_trials"]],
            ["模型自由度", result["model_df"]], ["残差自由度", result["residual_df"]],
            ["模型 LR χ²", result["model_lr"]], ["模型 p", result["model_p"]],
            ["Deviance", result["deviance"]], ["Deviance p", result["deviance_p"]],
            ["Pearson χ²", result["pearson_chi_square"]],
            ["Pearson p", result["pearson_p"]],
        ])
        self._add_table("系数", ["项", "估计", "标准误", "Wald z", "p"], [
            [row["term"], row["coefficient"], row["se"], row["z"], row["p"]]
            for row in result["coefficients"]
        ])
        self._add_table("项检验", ["项", "df", "LR χ²", "p", "状态"], [
            [row["term"], row["df"], row["lr"], row["p"], row["status"]]
            for row in result["terms"]
        ])
        self._add_table("运行概率", ["运行ID", "事件数", "试验数", "观测概率",
                                     "拟合概率", "Pearson 残差"], [
            [row["run_id"], row["events"], row["trials"],
             row["observed_probability"], row["predicted_probability"],
             row["pearson_residual"]]
            for row in result["rows"]
        ])

    def plot(self):
        if self.result is None or self.plot_factors is None:
            return
        try:
            if not self._snapshot_is_current():
                self._inputs_changed()
                self.status.set("来源工作表或数据已变化；旧结果已清除，请重新分析。")
                return
            if self.plot_tab is not None:
                if self.figure_canvas is not None:
                    self.figure_canvas.get_tk_widget().destroy()
                    self.figure_canvas = None
                self.tabs.forget(self.plot_tab)
                self.plot_tab.destroy()
            factor_x, factor_y = self.factor_x.get(), self.factor_y.get()
            x_values, y_values, probability = response_surface_probability_grid(
                self.result, factor_x, factor_y)
            tab = ttk.Frame(self.tabs)
            self.tabs.add(tab, text="概率图")
            self.plot_tab = tab
            figure = Figure(figsize=(6, 4), dpi=100)
            axis = figure.add_subplot(111)
            filled = axis.contourf(x_values, y_values, probability,
                                   levels=np.linspace(0, 1, 11), cmap="cividis",
                                   vmin=0, vmax=1)
            colorbar = figure.colorbar(filled, ax=axis, label="事件概率")
            axis.set_xlabel(f"{factor_x} 编码值")
            axis.set_ylabel(f"{factor_y} 编码值")
            axis.set_title("二元响应概率")
            style_axes(axis)
            style_axes(colorbar.ax)
            figure.tight_layout()
            self.figure_canvas = FigureCanvasTkAgg(figure, master=tab)
            self.figure_canvas.draw()
            self.figure_canvas.get_tk_widget().pack(fill="both", expand=True)
            self.tabs.select(tab)
        except (ValueError, TypeError, RuntimeError) as error:
            self.status.set(str(error))
            messagebox.showerror("概率图", str(error), parent=self.main)

    def close(self):
        if self._source_check_after is not None:
            try:
                self.main.after_cancel(self._source_check_after)
            except tk.TclError:
                pass
        self._source_check_after = None
        self.main.destroy()


def AnalyzeBinaryDOE(app, family):
    return BinaryAnalysisDialog(app, family)
