"""两水平平衡 Split-Plot 创建界面。"""
import tkinter as tk
from tkinter import messagebox, ttk

from doe_core import DesignSpec, FactorSpec
from doe_dialog import ccd_number
from doe_splitplot import create_split_plot
from help_link import open_help


_MAX_FACTORS = 8
_ROLE_LABELS = {"hard_to_change": "整区因子", "easy_to_change": "子区因子"}
_ROLE_BY_LABEL = {label: role for role, label in _ROLE_LABELS.items()}
_FACTOR_TYPE_LABELS = {"continuous": "连续", "categorical": "分类"}
_FACTOR_TYPE_BY_LABEL = {label: factor_type
                         for factor_type, label in _FACTOR_TYPE_LABELS.items()}
_PREVIEW_ROWS = 100


class CreateSplitPlot:
    def __init__(self, app):
        self.app = app
        self.main = tk.Toplevel(app.main)
        self.main.title("创建 Split-Plot 裂区设计")
        self.main.bind("<F1>", lambda event: open_help("doe.split_plot", parent=self.main))
        self.main.bind("<Destroy>", self._destroyed, add="+")
        self._preview_after = None
        body = ttk.Frame(self.main, padding=10)
        body.pack(fill="both", expand=True)

        settings = ttk.Frame(body)
        settings.grid(row=0, column=0, sticky="ew")
        ttk.Label(settings, text="因子数").pack(side="left")
        self.factor_count_var = tk.StringVar(value="2")
        self.factor_count = ttk.Combobox(
            settings, textvariable=self.factor_count_var,
            values=tuple(str(value) for value in range(2, _MAX_FACTORS + 1)),
            state="readonly", width=4)
        self.factor_count.pack(side="left", padx=(4, 12))
        self.blocks, self.blocks_var = self._entry(settings, "完整重复区组", "3")
        self.seed, self.seed_var = self._entry(settings, "随机 seed", "1")
        self.responses, self.responses_var = self._entry(settings, "响应名称", "Y")

        self.factor_frame = ttk.Frame(body)
        self.factor_frame.grid(row=1, column=0, sticky="nsew", pady=(8, 4))
        for column, label in enumerate(("因子", "名称", "类型", "水平 1", "水平 2", "角色")):
            ttk.Label(self.factor_frame, text=label).grid(row=0, column=column, padx=3)
        self.factor_values = []
        for index in range(_MAX_FACTORS):
            letter = chr(ord("A") + index)
            self.factor_values.append({
                "name": tk.StringVar(value=letter),
                "factor_type": tk.StringVar(value=_FACTOR_TYPE_LABELS["continuous"]),
                "low": tk.StringVar(value="0"),
                "high": tk.StringVar(value="1"),
                "role": tk.StringVar(value=_ROLE_LABELS[
                    "hard_to_change" if index == 0 else "easy_to_change"]),
            })
        self.factor_rows = []
        self._render_factor_rows()

        self.summary = ttk.Label(body, text="")
        self.summary.grid(row=2, column=0, sticky="w", pady=(2, 4))
        preview_frame = ttk.Frame(body)
        preview_frame.grid(row=3, column=0, sticky="nsew")
        self.preview_text = tk.Text(preview_frame, width=88, height=9, wrap="none",
                                    state="disabled")
        scrollbar = ttk.Scrollbar(preview_frame, orient="vertical",
                                  command=self.preview_text.yview)
        horizontal = ttk.Scrollbar(preview_frame, orient="horizontal",
                                   command=self.preview_text.xview)
        self.preview_text.configure(yscrollcommand=scrollbar.set,
                                    xscrollcommand=horizontal.set)
        horizontal.pack(side="bottom", fill="x")
        self.preview_text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.preview_horizontal = horizontal

        buttons = ttk.Frame(body)
        buttons.grid(row=4, column=0, sticky="e", pady=(8, 0))
        self.preview_button = ttk.Button(buttons, text="预览", command=self.preview)
        self.preview_button.pack(side="left")
        self.create_button = ttk.Button(buttons, text="创建", command=self.create)
        self.create_button.pack(side="left", padx=4)
        self.cancel_button = ttk.Button(buttons, text="取消", command=self.close)
        self.cancel_button.pack(side="left")
        body.columnconfigure(0, weight=1)
        body.rowconfigure(3, weight=1)

        self.factor_count_var.trace_add("write", self._factor_count_changed)
        for variable in (self.blocks_var, self.seed_var, self.responses_var):
            variable.trace_add("write", self._schedule_preview)
        for fields in self.factor_values:
            for variable in fields.values():
                variable.trace_add("write", self._schedule_preview)
        self.preview()

    @staticmethod
    def _entry(parent, label, default):
        ttk.Label(parent, text=label).pack(side="left", padx=(4, 2))
        value = tk.StringVar(value=default)
        entry = ttk.Entry(parent, textvariable=value, width=8)
        entry.pack(side="left", padx=(0, 8))
        return entry, value

    def _render_factor_rows(self):
        for row in self.factor_rows:
            row.destroy()
        self.factor_rows = []
        try:
            count = int(self.factor_count_var.get())
        except ValueError:
            self._show("")
            self.summary.configure(text="")
            return
        if not 2 <= count <= _MAX_FACTORS:
            self._show("")
            self.summary.configure(text="")
            return
        for index, fields in enumerate(self.factor_values[:count], 1):
            row = ttk.Frame(self.factor_frame)
            row.grid(row=index, column=0, columnspan=6, sticky="ew")
            ttk.Label(row, text=chr(ord("A") + index - 1), width=7).grid(row=0, column=0)
            ttk.Entry(row, textvariable=fields["name"], width=16).grid(
                row=0, column=1, padx=3, pady=2)
            ttk.Combobox(
                row, textvariable=fields["factor_type"],
                values=tuple(_FACTOR_TYPE_LABELS.values()), state="readonly",
                width=8).grid(row=0, column=2, padx=3)
            for column, key in enumerate(("low", "high"), 3):
                ttk.Entry(row, textvariable=fields[key], width=16).grid(
                    row=0, column=column, padx=3, pady=2)
            ttk.Combobox(
                row, textvariable=fields["role"], values=tuple(_ROLE_LABELS.values()),
                state="readonly", width=12).grid(row=0, column=5, padx=3)
            self.factor_rows.append(row)

    def _factor_count_changed(self, *_):
        self._render_factor_rows()
        self._schedule_preview()

    def _schedule_preview(self, *_):
        if not self.main.winfo_exists():
            return
        self._cancel_preview()
        try:
            self._preview_after = self.main.after(120, self._refresh_preview)
        except tk.TclError:
            self._preview_after = None

    def _cancel_preview(self):
        if self._preview_after is not None:
            try:
                self.main.after_cancel(self._preview_after)
            except tk.TclError:
                pass
            self._preview_after = None

    def _destroyed(self, event):
        if event.widget is self.main:
            self._cancel_preview()

    def _refresh_preview(self):
        self._preview_after = None
        try:
            frame, metadata = self.build()
        except (ValueError, TypeError, OverflowError):
            self._show("")
            self.summary.configure(text="")
            return
        self._display_preview(frame, metadata)

    def build(self):
        try:
            count = int(self.factor_count_var.get())
        except ValueError as error:
            raise ValueError("因子数必须是 2–8") from error
        if not 2 <= count <= _MAX_FACTORS:
            raise ValueError("因子数必须是 2–8")
        factors = []
        for index, fields in enumerate(self.factor_values[:count]):
            factor_id = chr(ord("A") + index)
            role = _ROLE_BY_LABEL.get(fields["role"].get(), fields["role"].get())
            name = fields["name"].get().strip()
            if not name:
                raise ValueError("因子名称不能为空")
            factor_type = _FACTOR_TYPE_BY_LABEL.get(fields["factor_type"].get())
            if factor_type == "continuous":
                factors.append(FactorSpec(
                    factor_id, name, ccd_number(fields["low"].get()),
                    ccd_number(fields["high"].get()), randomization_role=role))
            elif factor_type == "categorical":
                levels = tuple(fields[key].get().strip() for key in ("low", "high"))
                if not all(levels) or levels[0] == levels[1]:
                    raise ValueError("分类因子需填写两个不同的非空水平")
                factors.append(FactorSpec(
                    factor_id, name, None, None, factor_type="categorical",
                    levels=levels, level_type="text", randomization_role=role))
            else:
                raise ValueError("因子类型无效")
        hard_count = sum(factor.randomization_role == "hard_to_change" for factor in factors)
        easy_count = len(factors) - hard_count
        categorical = any(factor.factor_type == "categorical" for factor in factors)
        construction = ("v1" if count == 2 and hard_count == 1 and not categorical
                        else "v2" if count <= 6 and not categorical else "v3")
        responses = tuple(value.strip() for value in self.responses_var.get().split(","))
        spec = DesignSpec(
            "DOE", tuple(factors), responses, seed=int(self.seed_var.get()),
            design_type="split_plot", block_count=int(self.blocks_var.get()),
            construction_version=construction, randomization_unit="whole_plot",
            error_structure="split_plot")
        if not hard_count or not easy_count:
            raise ValueError("至少需要一个整区因子和一个子区因子")
        return create_split_plot(spec)

    def _display_preview(self, frame, metadata):
        columns = metadata["column_map"]
        factors = list(columns["factors"].values())
        views = [columns["run_id"], columns["standard_order"], columns["run_order"],
                 columns["block"], columns["whole_plot_id"], columns["subplot_id"],
                 *factors, columns["whole_plot_order"], columns["subplot_order"]]
        spec = metadata["design"]
        hard = sum(item["randomization_role"] == "hard_to_change"
                   for item in spec["factors"])
        easy = len(spec["factors"]) - hard
        hard_count, easy_count = 1 << hard, 1 << easy
        blocks = spec["block_count"]
        whole_plots = blocks * hard_count
        df_wp = (blocks - 1) * (hard_count - 1)
        df_sp = hard_count * (blocks - 1) * (easy_count - 1)
        self.summary.configure(text=(
            f"运行 {len(frame)} 次；区组 {blocks}；整区 {whole_plots}；"
            f"每整区子区 {easy_count}；整区误差 df {df_wp}；"
            f"子区误差 df {df_sp}；因子 {len(spec['factors'])}（hard {hard}，easy {easy}）"))
        lines = [self.summary.cget("text"), "\t".join(views)]
        shown = frame[views].head(_PREVIEW_ROWS)
        lines.extend("\t".join(map(str, row))
                     for row in shown.itertuples(index=False, name=None))
        if len(frame) > _PREVIEW_ROWS:
            lines.append(f"仅显示前 {_PREVIEW_ROWS} 行，共 {len(frame)} 行")
        self._show("\n".join(lines))

    def _show(self, text):
        self.preview_text.configure(state="normal")
        self.preview_text.delete("1.0", "end")
        self.preview_text.insert("1.0", text)
        self.preview_text.configure(state="disabled")

    def preview(self):
        self._cancel_preview()
        try:
            frame, metadata = self.build()
        except (ValueError, TypeError, OverflowError) as error:
            self._show("")
            self.summary.configure(text="")
            messagebox.showerror("Split-Plot", str(error), parent=self.main)
            return False
        self._display_preview(frame, metadata)
        return True

    def create(self):
        self._cancel_preview()
        try:
            frame, metadata = self.build()
            self.app.addSheet("DOE Split-Plot", frame, {"doe": metadata})
        except (ValueError, TypeError, OverflowError) as error:
            messagebox.showerror("Split-Plot", str(error), parent=self.main)
            return False
        self.close()
        return True

    def close(self):
        self._cancel_preview()
        self.main.destroy()
