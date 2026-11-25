"""Project history pane for completed report and plot snapshots."""

from tkinter import messagebox, ttk


class ResultNavigation(ttk.Frame):
    def __init__(self, app):
        super().__init__(app.main, padding=(6, 4))
        self.app = app
        self.by_item = {}
        self.groups = {}
        self.selected = None
        bar = ttk.Frame(self)
        bar.pack(fill="x")
        self.open_button = ttk.Button(bar, text="打开", command=self.open_selected)
        self.open_button.pack(side="left")
        self.delete_button = ttk.Button(bar, text="删除", command=self.delete_selected)
        self.delete_button.pack(side="left", padx=4)
        ttk.Button(bar, text="隐藏", command=app.toggle_result_navigation).pack(side="right")
        content = ttk.Frame(self)
        content.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(content, show="tree", selectmode="browse", height=12)
        self.tree.column("#0", width=260, stretch=True)
        scroll = ttk.Scrollbar(content, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._selection_changed)
        self.tree.bind("<Double-1>", lambda event: self.open_selected())
        self.tree.bind("<Return>", lambda event: self.open_selected())

    def state(self):
        index = next((i for i, record in enumerate(self.app.project_results)
                      if record is self.selected), None)
        return {"visible": bool(self.winfo_manager()), "selected": index}

    def restore(self, state):
        index = state.get("selected")
        records = self.app.project_results
        self.selected = records[index] if type(index) is int and 0 <= index < len(records) else None
        if state.get("visible") is True:
            self.pack(side="left", fill="y", before=self.app.nb)
            self.refresh()
        else:
            self.pack_forget()

    def refresh(self, *, focus_sheet=False):
        if not self.winfo_manager():
            return
        current = self.app.getCurrentSheet()
        expanded = {label for label, item in self.groups.items() if self.tree.item(item, "open")}
        children = self.tree.get_children()
        if children:
            self.tree.delete(*children)
        self.groups = {}
        self.by_item.clear()
        for source in self.app.sheets:
            self.groups[source] = self.tree.insert("", "end", text=source, open=source == current or source in expanded)
        selected_item = None
        for record in self.app.project_results:
            source = record["source"]
            if source is None:
                group = ("deleted", record["source_label"])
                if group not in self.groups:
                    self.groups[group] = self.tree.insert("", "end", text=record["source_label"]+"（已删除）",
                                                         open=group in expanded)
                parent = self.groups[group]
            else:
                parent = self.groups[source]
            time = record["time"]
            title = f"{record['title']}  {time}" if time else record["title"]
            item = self.tree.insert(parent, "end", text=title)
            self.by_item[item] = record, None
            has_history = bool(record["blocks"] or record.get("columns") or record.get("parameters"))
            if has_history and "png" in record:
                label = "统计报告" if record["blocks"] else "分析信息"
                for kind, text in (("report", label), ("plot", "图形快照")):
                    child = self.tree.insert(item, "end", text=text)
                    self.by_item[child] = record, kind
            if record is self.selected:
                selected_item = item
        if focus_sheet and current in self.groups:
            selected_item = self.groups[current]
            self.selected = None
        if selected_item is not None:
            self.tree.selection_set(selected_item)
            self.tree.see(selected_item)
        self._selection_changed()

    def _selection_changed(self, event=None):
        selection = self.tree.selection()
        item = self.by_item.get(selection[0]) if selection else None
        self.selected = item[0] if item else None
        for button in (self.open_button, self.delete_button):
            button.configure(state="normal" if item else "disabled")

    def open_selected(self):
        selection = self.tree.selection()
        item = self.by_item.get(selection[0]) if selection else None
        if item is None:
            return
        record, kind = item
        source = record["source_label"] + ("（已删除）" if record["source"] is None else "")
        title = f"{source} · {record['title']} · 历史快照"
        if kind != "plot" and (record["blocks"] or record.get("columns") or record.get("parameters")):
            return self.app.show_result_report([record], title, show_history=True)
        if "png" in record:
            return self.app.show_result_plot(record["png"], title)

    def delete_selected(self):
        record = self.selected
        if record is not None and messagebox.askyesno(
                "删除分析结果", f"删除“{record['title']}”及其报告和图形？", parent=self.app.main):
            self.app.delete_result(record)
