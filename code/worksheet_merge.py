"""Merge two project worksheets without copying their analysis metadata."""

import tkinter as tk
from tkinter import messagebox, ttk

import numpy as np
import pandas as pd

from pandastable_local.dialogs import apply_dialog_theme


JOIN_TYPES = {"全外连接": "outer", "内连接": "inner", "左连接": "left", "右连接": "right"}


def _take_rows(frame, positions, columns):
    data = frame.iloc[:, columns].reset_index(drop=True)
    if positions.hasnans:
        # Reindexing a NumPy integer column would otherwise cast IDs to float.
        for i, dtype in enumerate(data.dtypes):
            if isinstance(dtype, np.dtype) and dtype.kind in "iub":
                name = "boolean" if dtype.kind == "b" else dtype.name.capitalize()
                data.isetitem(i, data.iloc[:, i].astype(name))
    data = data.reindex(positions).reset_index(drop=True)
    data.attrs.clear()
    return data


def merge_worksheets(left, right, left_columns, right_columns, *, keys=None, how="outer"):
    if not left_columns and not right_columns:
        raise ValueError("请至少选择一个输出列。")
    if keys is None:
        size = max(len(left), len(right))
        row_map = pd.DataFrame({"L": pd.RangeIndex(size), "R": pd.RangeIndex(size)})
        row_map.loc[row_map.L >= len(left), "L"] = pd.NA
        row_map.loc[row_map.R >= len(right), "R"] = pd.NA
    else:
        left_keys, right_keys = keys
        if not left_keys or len(left_keys) != len(right_keys):
            raise ValueError("两侧必须选择相同数量的匹配键。")
        key_names = list(range(len(left_keys)))
        lkeys = left.iloc[:, left_keys].reset_index(drop=True)
        rkeys = right.iloc[:, right_keys].reset_index(drop=True)
        lkeys.columns = rkeys.columns = key_names
        for key in key_names:
            left_dtype, right_dtype = lkeys[key].dtype, rkeys[key].dtype
            if (left_dtype != right_dtype and pd.api.types.is_numeric_dtype(left_dtype)
                    and pd.api.types.is_numeric_dtype(right_dtype)):
                # Compare boxed numbers without rounding integer keys to a common float dtype.
                lkeys[key] = lkeys[key].astype(object)
                rkeys[key] = rkeys[key].astype(object)
        # A null in any component prevents the composite key from matching.
        lkeys["missing"] = lkeys.isna().any(axis=1).astype("int8")
        rkeys["missing"] = rkeys.isna().any(axis=1).astype("int8") * 2
        lkeys["L"] = pd.array(range(len(left)), dtype="Int64")
        rkeys["R"] = pd.array(range(len(right)), dtype="Int64")
        row_map = lkeys.merge(rkeys, on=[*key_names, "missing"], how=how, sort=False)

    output = [_take_rows(frame, row_map[side], columns)
              for frame, side, columns in [(left, "L", left_columns), (right, "R", right_columns)]]
    used = set()
    for frame, side in zip(output, ("左", "右")):
        names = []
        for column in frame.columns:
            name = column
            if name in used:
                base = f"{column}（{side}）"
                name = base
                suffix = 2
                while name in used:
                    name = f"{base}{suffix}"
                    suffix += 1
            names.append(name)
            used.add(name)
        frame.columns = names

    left_present, right_present = row_map.L.notna(), row_map.R.notna()
    counts = (int((left_present & right_present).sum()), int((left_present & ~right_present).sum()),
              int((~left_present & right_present).sum()))
    return pd.concat(output, axis=1), counts


class WorksheetMergeDialog:
    def __init__(self, app):
        self.app = app
        self.main = tk.Toplevel(app.main)
        self.main.title("合并项目工作表")
        names = list(app.sheets)
        self.source = [tk.StringVar(self.main, value) for value in names[:2]]
        self.mode = tk.StringVar(self.main, "按键匹配")
        self.join = tk.StringVar(self.main, "全外连接")
        self.preview_frame = None

        options = ttk.Frame(self.main, padding=8)
        options.pack(fill="x")
        self.mode_box = self._selector(options, self.mode, ("按键匹配", "按行并列"))
        self.join_box = self._selector(options, self.join, tuple(JOIN_TYPES))
        self.column_boxes = []
        self.key_boxes = []
        for i, side in enumerate(("左表", "右表")):
            panel = ttk.LabelFrame(self.main, text=side, padding=8)
            panel.pack(side="top", fill="x")
            selector = self._selector(panel, self.source[i], names)
            selector.bind("<<ComboboxSelected>>", lambda event, index=i: self._source_changed(index))
            self.key_boxes.append(self._list(panel, "匹配键（按列顺序配对）"))
            self.column_boxes.append(self._list(panel, "输出列"))
            self._source_changed(i)

        self.status = ttk.Label(self.main)
        self.status.pack(fill="x", padx=8)
        self.grid = ttk.Treeview(self.main, show="headings", height=7)
        self.grid.pack(fill="both", expand=True, padx=8)
        scroll = ttk.Scrollbar(self.main, orient="horizontal", command=self.grid.xview)
        scroll.pack(fill="x", padx=8)
        self.grid.configure(xscrollcommand=scroll.set)
        buttons = ttk.Frame(self.main, padding=8)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="预览", command=self.preview).pack(side="left")
        self.confirm_button = ttk.Button(buttons, text="创建工作表", state="disabled", command=self.confirm)
        self.confirm_button.pack(side="right", padx=4)
        ttk.Button(buttons, text="取消", command=self.main.destroy).pack(side="right")
        for var in [*self.source, self.mode, self.join]:
            var.trace_add("write", self._invalidate)
        self.mode_box.bind("<<ComboboxSelected>>", self._mode_changed)
        self.main.bind("<Escape>", lambda event: self.main.destroy())
        apply_dialog_theme(self.main, app.main)
        self.main.grab_set()

    @staticmethod
    def _selector(parent, var, values):
        box = ttk.Combobox(parent, textvariable=var, values=values, state="readonly", width=20)
        box.pack(side="left", padx=4)
        return box

    def _list(self, parent, caption):
        frame = ttk.Frame(parent)
        frame.pack(side="left", fill="both", expand=True, padx=4)
        ttk.Label(frame, text=caption).pack(anchor="w")
        box = tk.Listbox(frame, selectmode="extended", exportselection=False, height=5)
        bar = ttk.Scrollbar(frame, command=box.yview)
        box.configure(yscrollcommand=bar.set)
        bar.pack(side="right", fill="y")
        box.pack(side="left", fill="both", expand=True)
        box.bind("<<ListboxSelect>>", self._invalidate)
        return box

    def _source_changed(self, side):
        table = self.app.sheets[self.source[side].get()]
        labels = [f"{i + 1}  {name}" for i, name in enumerate(self.app._full_frame(table).columns)]
        for box in (self.key_boxes[side], self.column_boxes[side]):
            box.configure(state="normal")
            box.delete(0, "end")
            box.insert("end", *labels)
        self.column_boxes[side].selection_set(0, "end")
        if self.mode.get() == "按行并列":
            self.key_boxes[side].configure(state="disabled")

    def _mode_changed(self, event=None):
        by_key = self.mode.get() == "按键匹配"
        self.join_box.configure(state="readonly" if by_key else "disabled")
        for box in self.key_boxes:
            box.configure(state="normal" if by_key else "disabled")

    def _invalidate(self, *args):
        self.preview_frame = None
        self.confirm_button.configure(state="disabled")
        self.status.configure(text="")
        self.grid.delete(*self.grid.get_children())

    def preview(self):
        self._invalidate()
        try:
            names = [var.get() for var in self.source]
            if names[0] == names[1]:
                raise ValueError("请选择两张不同的工作表。")
            frames = [self.app._full_frame(self.app.sheets[name]) for name in names]
            keys = [list(box.curselection()) for box in self.key_boxes] if self.mode.get() == "按键匹配" else None
            picks = [list(box.curselection()) for box in self.column_boxes]
            frame, (matched, left_only, right_only) = merge_worksheets(
                *frames, *picks, keys=keys, how=JOIN_TYPES[self.join.get()]
            )
        except (ValueError, TypeError, KeyError, MemoryError) as error:
            messagebox.showerror("合并项目工作表", str(error), parent=self.main)
            return
        counts = f"左表 {len(frames[0])} 行，右表 {len(frames[1])} 行，结果 {len(frame)} 行"
        self.status.configure(text=f"{counts}（匹配 {matched}、仅左 {left_only}、仅右 {right_only}）")
        self.grid.configure(columns=list(range(len(frame.columns))))
        for i, column in enumerate(frame.columns):
            self.grid.heading(i, text=str(column))
            self.grid.column(i, width=110, stretch=False)
        for row in frame.head(20).itertuples(index=False, name=None):
            self.grid.insert("", "end", values=tuple(
                "" if pd.api.types.is_scalar(value) and pd.isna(value) else str(value)
                for value in row
            ))
        self.preview_frame = frame
        self.confirm_button.configure(state="normal")

    def confirm(self):
        if self.preview_frame is not None:
            self.app.addSheet("合并结果", self.preview_frame, finish_edits=False)
            self.main.destroy()
