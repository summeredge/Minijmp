"""事件/试验格式的 DOE 二元响应分析窗口。"""
import copy
from concurrent.futures import ThreadPoolExecutor
from math import prod
from threading import Event
import tkinter as tk
from tkinter import messagebox, ttk

import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from chart_style import style_axes
from doe_binary_analysis import (
    analyze_binary_doe, predict_binary_probability, response_surface_probability_grid,
)
from doe_core import restore_design_result
from doe_dialog import ccd_number
from doe_optimize import optimize_binary_rsm
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
            metadata = copy.deepcopy(metadata)
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
        self.probability_button = None
        self.optimizer_button = None
        if family == "rsm":
            self.probability_button = ttk.Button(
                buttons, text="预测概率", command=self.predict_probability,
                state="disabled")
            self.probability_button.pack(side="left", padx=4)
            self.optimizer_button = ttk.Button(
                buttons, text="响应优化", command=self.optimize_response,
                state="disabled")
            self.optimizer_button.pack(side="left", padx=4)
        ttk.Button(buttons, text="取消", command=self.close).pack(side="right")
        self.tabs = ttk.Notebook(self.main)
        self.tabs.pack(side="top", fill="both", expand=True, padx=8, pady=8)
        self.result = None
        self.source_snapshot = None
        self.metadata_snapshot = None
        self.figure_canvas = None
        self.plot_tab = None
        self.probability_dialog = None
        self.optimizer_dialog = None
        self.events.bind("<<ComboboxSelected>>", lambda event: self._inputs_changed())
        self.trials.bind("<<ComboboxSelected>>", lambda event: self._inputs_changed())
        self._source_check_after = None
        self.main.geometry("900x610")
        self.main.grab_set()
        self._source_check_after = self.main.after(750, self._check_source)

    def _inputs_changed(self):
        if self.probability_dialog is not None:
            self.probability_dialog.close()
        if self.optimizer_dialog is not None:
            self.optimizer_dialog.close()
        self.result = None
        self.source_snapshot = None
        self.metadata_snapshot = None
        if self.probability_button is not None:
            self.probability_button.configure(state="disabled")
        if self.optimizer_button is not None:
            self.optimizer_button.configure(state="disabled")
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
            if getattr(self.source, "doe_metadata", None) != self.metadata:
                raise ValueError("DOE 设计已更改；请关闭并重新打开分析窗口。")
            self.owner._finish_edit()
            frame = self.owner._full_frame(self.source).copy(deep=True)
            order = int(self.model_order.get()) if self.model_order is not None else 1
            result = analyze_binary_doe(
                frame, self.metadata, self.events.get(), self.trials.get(),
                self.family, model_order=order, selected_terms=self._selected_terms())
            self.result = result
            self.source_snapshot = frame.copy(deep=True)
            self.metadata_snapshot = copy.deepcopy(self.metadata)
            if self.probability_button is not None:
                self.probability_button.configure(state="normal")
            if self.optimizer_button is not None:
                self.optimizer_button.configure(state="normal")
            self._show_result(result)
            self.status.set(
                f"{result['fit_status']}；{result['n_runs']} 个运行，{result['n_trials']} 次试验；"
                f"模型 df={result['model_df']}，残差 df={result['residual_df']}。"
            )
        except (AttributeError, KeyError, TypeError, ValueError, RuntimeError) as error:
            self.result = None
            self._clear_tabs()
            if self.probability_button is not None:
                self.probability_button.configure(state="disabled")
            if self.optimizer_button is not None:
                self.optimizer_button.configure(state="disabled")
            self.status.set(str(error))
            messagebox.showerror("DOE 二元响应", str(error), parent=self.main)

    def predict_probability(self):
        if self.result is None or self.probability_button is None:
            return
        if not self._snapshot_is_current():
            self._inputs_changed()
            self.status.set("来源工作表或数据已变化；旧结果已清除，请重新分析。")
            return
        if self.probability_dialog is not None:
            try:
                if self.probability_dialog.main.winfo_exists():
                    self.probability_dialog.main.lift()
                    return
            except tk.TclError:
                pass
        self.probability_dialog = BinaryProbabilityDialog(self)

    def optimize_response(self):
        if self.result is None or self.optimizer_button is None:
            return
        if not self._snapshot_is_current():
            self._inputs_changed()
            self.status.set("来源工作表或数据已变化；旧结果已清除，请重新分析。")
            return
        if self.optimizer_dialog is not None:
            try:
                if self.optimizer_dialog.main.winfo_exists():
                    self.optimizer_dialog.main.lift()
                    return
            except tk.TclError:
                pass
        self.optimizer_dialog = BinaryOptimizerDialog(self)

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
        if self.probability_dialog is not None:
            self.probability_dialog.close()
        if self.optimizer_dialog is not None:
            self.optimizer_dialog.close()
        if self._source_check_after is not None:
            try:
                self.main.after_cancel(self._source_check_after)
            except tk.TclError:
                pass
        self._source_check_after = None
        self.main.destroy()


class BinaryProbabilityDialog:
    def __init__(self, parent):
        self.parent = parent
        self.analysis = parent.result
        self.factors = parent.design.spec.factors
        self.main = tk.Toplevel(parent.main)
        self.main.title("二元响应概率预测")
        self.main.transient(parent.main)
        self.main.resizable(True, True)
        self.main.protocol("WM_DELETE_WINDOW", self.close)
        self.main.bind("<F1>", lambda event: open_help("doe.binary", parent=self.main))

        ttk.Label(
            self.main,
            text=f"事件/试验：{self.analysis['events_column']} / {self.analysis['trials_column']}",
            anchor="w",
        ).pack(fill="x", padx=8, pady=(8, 2))
        options = ttk.Frame(self.main, padding=(8, 4))
        options.pack(fill="x")
        ttk.Label(options, text="置信度").pack(side="left")
        self.confidence = ttk.Combobox(
            options, values=("90%", "95%", "99%"), state="readonly", width=6)
        self.confidence.set("95%")
        self.confidence.pack(side="left", padx=(4, 12))
        ttk.Label(options, text="方向").pack(side="left")
        self.side = ttk.Combobox(
            options, values=("双侧", "单侧下限", "单侧上限"),
            state="readonly", width=10)
        self.side.set("双侧")
        self.side.pack(side="left", padx=4)
        self.confidence.bind("<<ComboboxSelected>>", self._inputs_changed)
        self.side.bind("<<ComboboxSelected>>", self._inputs_changed)

        form = ttk.LabelFrame(self.main, text="因子设置", padding=8)
        form.pack(fill="x", padx=8, pady=4)
        self.entries = {}
        self.input_variables = {}
        for row, factor in enumerate(self.factors):
            label = f"{factor.factor_id} {factor.name}"
            if factor.unit:
                label += f"（{factor.unit}）"
            ttk.Label(form, text=label).grid(row=row, column=0, sticky="w", pady=2)
            variable = tk.StringVar(self.main)
            if factor.factor_type == "categorical":
                widget = ttk.Combobox(
                    form, values=factor.levels, state="readonly", width=20,
                    textvariable=variable)
                widget.current(0)
            else:
                widget = ttk.Entry(form, width=22, textvariable=variable)
                try:
                    variable.set(str(float(factor.from_coded(0))))
                except (OverflowError, TypeError, ValueError):
                    pass
            self.input_variables[factor.factor_id] = variable
            variable.trace_add("write", self._inputs_changed)
            widget.grid(row=row, column=1, sticky="w", padx=6, pady=2)
            self.entries[factor.factor_id] = widget

        buttons = ttk.Frame(self.main, padding=8)
        buttons.pack(fill="x", side="bottom")
        self.predict_button = ttk.Button(buttons, text="预测", command=self.predict)
        self.predict_button.pack(side="left")
        ttk.Button(buttons, text="关闭", command=self.close).pack(side="right")
        self.status = tk.StringVar(value="")
        ttk.Label(self.main, textvariable=self.status, anchor="w").pack(
            fill="x", padx=8, pady=(0, 4))
        self.result_frame = ttk.Frame(self.main, padding=8)
        self.result_frame.pack(fill="both", expand=True)
        self.result = None
        self.result_block = None
        self.main.geometry("700x520")

    def _is_current(self):
        try:
            return (self.parent.result is self.analysis
                    and self.parent._snapshot_is_current())
        except (AttributeError, RuntimeError, tk.TclError):
            return False

    def _clear_result(self):
        self.result = None
        if self.result_block is not None:
            self.result_block.destroy()
            self.result_block = None

    def _inputs_changed(self, *_args):
        self._clear_result()
        self.status.set("")

    def _read_settings(self):
        settings = {}
        for factor in self.factors:
            widget = self.entries[factor.factor_id]
            if factor.factor_type == "categorical":
                index = widget.current()
                if index < 0:
                    raise ValueError(f"请选择因子 {factor.factor_id} 的合法水平")
                settings[factor.factor_id] = factor.levels[index]
            else:
                settings[factor.factor_id] = ccd_number(widget.get())
        return settings

    def predict(self):
        self._clear_result()
        if not self._is_current():
            self.predict_button.configure(state="disabled")
            self.status.set("模型已过期；请返回分析窗口重新分析。")
            return
        try:
            self.parent.owner._finish_edit()
            if not self._is_current():
                raise ValueError("来源工作表或数据已变化；请重新分析。")
            confidence = float(self.confidence.get().rstrip("%")) / 100
            side = {"双侧": "two_sided", "单侧下限": "lower",
                    "单侧上限": "upper"}[self.side.get()]
            self.result = predict_binary_probability(
                self.analysis, self._read_settings(), confidence, side)
            self._show_result(self.result)
        except (AttributeError, KeyError, TypeError, ValueError, RuntimeError,
                OverflowError, FloatingPointError) as error:
            self._clear_result()
            self.status.set("预测失败：" + str(error))

    def _show_result(self, result):
        fmt = lambda value: "—" if value is None else f"{value:.10g}"
        direction = {"two_sided": "双侧", "lower": "单侧下限",
                     "upper": "单侧上限"}[result["side"]]
        values = [[f"{factor.factor_id} {factor.name}", result["settings"][factor.factor_id]]
                  for factor in self.factors]
        values.extend([
            ["Logit 预测值 η̂", fmt(result["eta_hat"])],
            ["SE on Logit scale", fmt(result["se_eta"])],
            ["预测事件概率", fmt(result["p_hat"])],
            ["概率标准误", fmt(result["se_p"])],
            ["置信度 / 方向", f"{result['confidence']:.0%} / {direction}"],
            ["Wald 概率下限", fmt(result["ci_low"])],
            ["Wald 概率上限", fmt(result["ci_high"])],
            ["区间状态", result["interval_status"]],
            ["方法", result["method"]],
            ["模型快照", result["model_snapshot"]],
            ["说明", result["assumption"]],
        ])
        self.result_block = TableBlock(self.result_frame, StatTable(
            title="事件概率估计", headers=("项目", "值"), values=values,
        ), paginate=True)
        self.result_block.pack(fill="both", expand=True)
        self.status.set(
            f"预测事件概率 {result['p_hat']:.10g}；区间状态：{result['interval_status']}"
        )

    def close(self):
        self._clear_result()
        if self.parent.probability_dialog is self:
            self.parent.probability_dialog = None
        try:
            if self.main.winfo_exists():
                self.main.destroy()
        except tk.TclError:
            pass


class BinaryOptimizerDialog:
    def __init__(self, parent):
        self.parent = parent
        self.analysis = parent.result
        self.factors = parent.design.spec.factors
        self.continuous = [factor for factor in self.factors
                           if factor.factor_type == "continuous"]
        self.categorical = [factor for factor in self.factors
                            if factor.factor_type == "categorical"]
        self.main = tk.Toplevel(parent.main)
        self.main.title("二元响应优化")
        self.main.transient(parent.main)
        self.main.resizable(True, True)
        self.main.protocol("WM_DELETE_WINDOW", self.close)
        self.main.bind("<F1>", lambda event: open_help("doe.binary", parent=self.main))
        self.main.geometry("900x700")
        self.main.minsize(720, 560)

        self.status = tk.StringVar(self.main, "")
        self.output_block = None
        self.result = None
        self.input_variables = []
        self.input_widgets = []
        self._closed = False
        self.cancel_event = Event()
        self.future = None
        self.poll_id = None
        self.executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="doe-binary-optimize")

        ttk.Label(
            self.main,
            text=f"事件/试验：{self.analysis['events_column']} / "
                 f"{self.analysis['trials_column']}",
            anchor="w",
        ).pack(fill="x", padx=8, pady=(8, 2))
        options = ttk.LabelFrame(self.main, text="响应概率目标", padding=6)
        options.pack(fill="x", padx=8, pady=4)
        self.goal = self._choice(
            options, "目标", ("最大化", "最小化", "目标值"), "最大化", 0, 0)
        self.criterion = self._choice(
            options, "标准", ("概率", "Desirability"), "概率", 0, 2)
        self.limits = {}
        for column, (key, label, default) in enumerate((
                ("lower", "L 下限", "0"), ("target", "T 目标", "1"),
                ("upper", "U 上限", ""), ("weight", "weight", "1"))):
            self.limits[key] = self._entry(
                options, label, default, 2 * column, row=1)

        bounds = ttk.LabelFrame(self.main, text="连续因子范围与起点（实际单位）", padding=6)
        bounds.pack(fill="x", padx=8, pady=4)
        for column, label in enumerate(("因子", "下限", "上限", "起点")):
            ttk.Label(bounds, text=label).grid(row=0, column=column, sticky="w", padx=4)
        self.bounds_entries = {}
        self.start_entries = {}
        for row, factor in enumerate(self.continuous, 1):
            label = f"{factor.factor_id} {factor.name}"
            if factor.unit:
                label += f"（{factor.unit}）"
            ttk.Label(bounds, text=label).grid(row=row, column=0, sticky="w", padx=4)
            low = self._entry(bounds, None, str(factor.low), 1, row)
            high = self._entry(bounds, None, str(factor.high), 2, row)
            try:
                center = str(float(factor.from_coded(0)))
            except (OverflowError, TypeError, ValueError):
                center = ""
            start = self._entry(bounds, None, center, 3, row)
            self.bounds_entries[factor.factor_id] = (low, high)
            self.start_entries[factor.factor_id] = start
        bounds.columnconfigure(0, weight=1)

        self.category_lists = {}
        if self.categorical:
            categories = ttk.LabelFrame(self.main, text="允许的类别水平", padding=6)
            categories.pack(fill="x", padx=8, pady=4)
            for row, factor in enumerate(self.categorical):
                label = f"{factor.factor_id} {factor.name}"
                ttk.Label(categories, text=label).grid(
                    row=row, column=0, sticky="nw", padx=4, pady=2)
                levels = tk.Listbox(
                    categories, selectmode="multiple", height=min(5, len(factor.levels)),
                    exportselection=False)
                for level in factor.levels:
                    levels.insert("end", str(level))
                levels.selection_set(0, "end")
                levels.grid(row=row, column=1, sticky="w", padx=4, pady=2)
                scrollbar = ttk.Scrollbar(
                    categories, orient="vertical", command=levels.yview)
                scrollbar.grid(row=row, column=2, sticky="ns", pady=2)
                levels.configure(yscrollcommand=scrollbar.set)
                levels.bind("<<ListboxSelect>>", self._inputs_changed)
                self.category_lists[factor.factor_id] = levels
                self.input_widgets.append((levels, "normal"))

        self.preview_frame = ttk.Frame(self.main, padding=6)
        self.preview_frame.pack(fill="both", expand=True, padx=8, pady=4)
        buttons = ttk.Frame(self.main, padding=8)
        buttons.pack(side="bottom", fill="x")
        self.preview_button = ttk.Button(buttons, text="预览", command=self.preview)
        self.preview_button.pack(side="left")
        self.optimize_button = ttk.Button(buttons, text="优化", command=self.optimize)
        self.optimize_button.pack(side="left", padx=4)
        self.cancel_button = ttk.Button(
            buttons, text="取消计算", command=self.cancel, state="disabled")
        self.cancel_button.pack(side="left")
        ttk.Button(buttons, text="关闭", command=self.close).pack(side="right")
        self.progress = ttk.Progressbar(buttons, mode="indeterminate", length=100)
        self.progress.pack(side="right", padx=6)
        ttk.Label(self.main, textvariable=self.status, anchor="w").pack(
            side="bottom", fill="x", padx=8, pady=(0, 4))
        self.poll_id = self.main.after(100, self._poll)

    def _choice(self, parent, label, values, default, row, column):
        ttk.Label(parent, text=label).grid(row=row, column=column, sticky="w", padx=4)
        variable = tk.StringVar(self.main, default)
        widget = ttk.Combobox(
            parent, values=values, state="readonly", width=13, textvariable=variable)
        widget.grid(row=row, column=column + 1, sticky="w", padx=4)
        variable.trace_add("write", self._inputs_changed)
        widget.bind("<<ComboboxSelected>>", self._inputs_changed)
        self.input_variables.append(variable)
        self.input_widgets.append((widget, "readonly"))
        return variable

    def _entry(self, parent, label, default, column, row=0):
        if label is not None:
            ttk.Label(parent, text=label).grid(row=row, column=column, sticky="w", padx=4)
            column += 1
        variable = tk.StringVar(self.main, default)
        widget = ttk.Entry(parent, width=14, textvariable=variable)
        widget.grid(row=row, column=column, sticky="w", padx=4, pady=2)
        variable.trace_add("write", self._inputs_changed)
        self.input_variables.append(variable)
        self.input_widgets.append((widget, "normal"))
        return variable

    def _inputs_changed(self, *_args):
        if self._closed:
            return
        if self.future is not None:
            self.cancel_event.set()
        self.result = None
        if self.output_block is not None:
            self.output_block.destroy()
            self.output_block = None
        self.status.set("")

    def _is_current(self):
        try:
            return (self.parent.result is self.analysis
                    and self.parent._snapshot_is_current())
        except (AttributeError, RuntimeError, tk.TclError):
            return False

    def _read_options(self):
        goals = {"最大化": "maximize", "最小化": "minimize", "目标值": "target"}
        criteria = {"概率": "probability", "Desirability": "desirability"}
        options = {
            "goal": goals[self.goal.get()],
            "criterion": criteria[self.criterion.get()],
            "lower": None, "target": None, "upper": None,
            "weight": ccd_number(self.limits["weight"].get()),
            "bounds": {}, "categories": {}, "start": {},
        }
        for key in ("lower", "target", "upper"):
            text = self.limits[key].get().strip()
            options[key] = None if not text else ccd_number(text)
        for factor in self.continuous:
            low, high = self.bounds_entries[factor.factor_id]
            options["bounds"][factor.factor_id] = (
                ccd_number(low.get()), ccd_number(high.get()))
            text = self.start_entries[factor.factor_id].get().strip()
            if text:
                options["start"][factor.factor_id] = ccd_number(text)
        for factor in self.categorical:
            indexes = self.category_lists[factor.factor_id].curselection()
            options["categories"][factor.factor_id] = [factor.levels[int(i)] for i in indexes]
        if not options["start"]:
            options["start"] = None
        return options

    def _show_rows(self, title, rows):
        if self.output_block is not None:
            self.output_block.destroy()
        self.output_block = TableBlock(
            self.preview_frame,
            StatTable(title=title, headers=("项目", "值"), values=rows),
            paginate=True,
        )
        self.output_block.pack(fill="both", expand=True)

    def preview(self):
        if not self._is_current():
            self.parent._inputs_changed()
            self.parent.status.set("模型来源已变化；旧结果已清除，请重新分析。")
            return
        self._inputs_changed()
        try:
            options = self._read_options()
            rows = [
                ["目标 / 标准", f"{self.goal.get()} / {self.criterion.get()}"],
                ["L / T / U", " / ".join(
                    "—" if options[key] is None else str(options[key])
                    for key in ("lower", "target", "upper"))],
                ["weight", str(options["weight"])],
                ["类别组合数", str(prod(map(len, options["categories"].values()))
                                   if options["categories"] else 1)],
            ]
            for factor in self.continuous:
                low, high = options["bounds"][factor.factor_id]
                start = options["start"]
                rows.append([
                    factor.factor_id,
                    f"{low} 至 {high}；起点 "
                    + (str(start[factor.factor_id]) if start is not None
                       and factor.factor_id in start else "中心"),
                ])
            for factor in self.categorical:
                rows.append([factor.factor_id, ", ".join(
                    str(level) for level in options["categories"][factor.factor_id])])
            self.result = None
            self._show_rows("当前优化条件", rows)
            self.status.set("条件预览已更新。")
        except (KeyError, TypeError, ValueError, OverflowError) as error:
            self.status.set("预览失败：" + str(error))

    def _set_busy(self, busy):
        for widget, state in self.input_widgets:
            widget.configure(state="disabled" if busy else state)
        self.preview_button.configure(state="disabled" if busy else "normal")
        self.optimize_button.configure(state="disabled" if busy else "normal")
        self.cancel_button.configure(state="normal" if busy else "disabled")
        if busy:
            self.progress.start()
        else:
            self.progress.stop()

    def optimize(self):
        if self.future is not None:
            return
        if not self._is_current():
            self.parent._inputs_changed()
            self.parent.status.set("模型来源已变化；旧结果已清除，请重新分析。")
            return
        self._inputs_changed()
        try:
            self.parent.owner._finish_edit()
            if not self._is_current():
                self.parent._inputs_changed()
                self.parent.status.set("来源工作表或数据已变化；旧结果已清除，请重新分析。")
                return
            options = self._read_options()
            self.cancel_event.clear()
            self.future = self.executor.submit(
                optimize_binary_rsm, self.analysis, **options,
                cancel=self.cancel_event)
            self._set_busy(True)
            self.status.set("正在优化；连续搜索不证明全局最优。")
        except (AttributeError, KeyError, TypeError, ValueError, RuntimeError,
                OverflowError) as error:
            self.status.set("优化失败：" + str(error))

    def cancel(self):
        if self.future is not None:
            self.cancel_event.set()
            self.cancel_button.configure(state="disabled")
            self.status.set("正在取消；当前搜索返回后丢弃结果。")

    def _poll(self):
        if self._closed:
            return
        if self.future is not None and self.future.done():
            future, self.future = self.future, None
            self._set_busy(False)
            if self.cancel_event.is_set():
                self.result = None
                self._inputs_changed()
                self.status.set("已取消；没有写回响应数据。")
            elif not self._is_current():
                self.parent._inputs_changed()
                self.parent.status.set("模型来源已变化；旧结果已清除，请重新分析。")
            else:
                try:
                    self.result = future.result()
                    self._show_result(self.result)
                except (InterruptedError, AttributeError, KeyError, TypeError,
                        ValueError, RuntimeError, OverflowError, FloatingPointError) as error:
                    self.result = None
                    self.status.set("优化失败：" + str(error))
        try:
            self.poll_id = self.main.after(100, self._poll)
        except tk.TclError:
            self.poll_id = None

    def _show_result(self, result):
        fmt = lambda value: "—" if value is None else f"{value:.10g}"
        rows = [[f"{factor.factor_id} {factor.name}", result["settings"][factor.factor_id]]
                for factor in self.factors]
        rows.extend([
            ["预测事件概率", fmt(result["probability"])],
            ["Desirability", fmt(result["desirability"])],
            ["目标状态", result["target_status"]],
            ["目标差值（概率 − T）", fmt(result["target_difference"])],
            ["搜索状态", result["status"]],
            ["所有连续起点收敛", "是" if result["solver_converged"] else "否"],
            ["候选可用", "是" if result["candidate_found"] else "否"],
            ["函数评价 / 迭代", f"{result['evaluations']} / {result['solver_iterations']}"],
            ["类别组合数", result["category_combinations_evaluated"]],
            ["全局最优证明", "是" if result["global_optimum_proven"] else "否"],
            ["方法", result["method"]],
            ["终止原因", result["termination_reason"]],
            ["模型快照", result["model_snapshot"]],
            ["说明", result["note"]],
        ])
        self._show_rows("二元响应优化结果", rows)
        self.status.set(
            "优化完成。" if result["success"] else
            "已返回当前最佳候选；至少一个连续起点未收敛。")

    def close(self):
        if self._closed:
            return
        self._closed = True
        self.cancel_event.set()
        if self.future is not None:
            self.future.cancel()
        if self.poll_id is not None:
            try:
                self.main.after_cancel(self.poll_id)
            except tk.TclError:
                pass
            self.poll_id = None
        self.executor.shutdown(wait=False, cancel_futures=True)
        if self.parent.optimizer_dialog is self:
            self.parent.optimizer_dialog = None
        try:
            if self.main.winfo_exists():
                self.main.destroy()
        except tk.TclError:
            pass


def AnalyzeBinaryDOE(app, family):
    return BinaryAnalysisDialog(app, family)
