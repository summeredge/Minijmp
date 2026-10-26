"""Compact raw-trend dialog using the existing plotting window."""

import tkinter as tk
from tkinter import ttk

import pandas as pd
from pandas.api.types import is_numeric_dtype

from matplotlib.backends.backend_tkagg import NavigationToolbar2Tk

from dialog import addListBox
from sbplot_dialog import SBDialog
from time_series import (AXIS_MODES, default_time_column, axis_assignments,
                         is_numeric_y_candidate,
                         prepare_time_series, time_series_plot)


class TimeSeriesDialog(SBDialog):
    def createWidgets(self, master):
        self.main.resizable(True, True)
        master.pack_configure(fill=tk.BOTH, expand=True)
        default = default_time_column(self.df) if self.df.columns.is_unique else None
        self.sample_mode = tk.BooleanVar(value=default is None)
        self.xvar = tk.StringVar(value='' if default is None else default)
        self.mode = tk.StringVar(value=AXIS_MODES[0])
        self.assignments = {}
        self.ylabels = {}
        self.titlevar = tk.StringVar()
        self.xlabel = tk.StringVar()
        self.show_legend = tk.BooleanVar(value=True)
        self.grid = tk.BooleanVar(value=True)
        self.statusvar = tk.StringVar(value='')

        frame = ttk.LabelFrame(master, text='X 轴')
        frame.pack(fill=tk.X, padx=4, pady=2)
        ttk.Checkbutton(frame, text='样本序号', variable=self.sample_mode,
                        command=self.update_x_mode).pack(side=tk.LEFT)
        ttk.Label(frame, text='时间列').pack(side=tk.LEFT, padx=4)
        self.time_combo = ttk.Combobox(frame, values=self.cols, textvariable=self.xvar,
                                       state='readonly', width=24)
        self.time_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.update_x_mode()

        frame = ttk.LabelFrame(master, text='Y 变量与坐标轴')
        frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)
        numeric = [c for c in self.cols if self.df.columns.is_unique
                   and is_numeric_y_candidate(self.df[c])]

        box, self.ylist = addListBox(frame, values=numeric, width=24, height=7, label='数值列（多选）')
        box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.ylist.bind('<<ListboxSelect>>', self.update_variables)
        right = ttk.Frame(frame)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4)
        self.mode_combo = ttk.Combobox(right, values=AXIS_MODES, textvariable=self.mode,
                                       state='readonly', width=14)
        self.mode_combo.pack(fill=tk.X)
        self.mode_combo.bind('<<ComboboxSelected>>', self.update_variables)
        self.axis_table = ttk.Treeview(right, columns=('variable', 'axis'), show='headings', height=7,
                                       selectmode='browse')
        self.axis_table.heading('variable', text='变量')
        self.axis_table.heading('axis', text='Y 轴')
        self.axis_table.column('variable', width=180)
        self.axis_table.column('axis', width=60, stretch=False)
        scroll = ttk.Scrollbar(right, orient=tk.VERTICAL, command=self.axis_table.yview)
        self.axis_table.configure(yscrollcommand=scroll.set)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.axis_table.pack(fill=tk.BOTH, expand=True)
        self.axis_table.bind('<<TreeviewSelect>>', self.select_variable)
        edit = ttk.Frame(master)
        edit.pack(fill=tk.X, padx=4, pady=2)
        ttk.Label(edit, text='选中变量所属 Y 轴').pack(side=tk.LEFT)
        self.axisvar = tk.StringVar(value='Y1')
        self.axis_combo = ttk.Combobox(edit, textvariable=self.axisvar, values=('Y1',),
                                       state='disabled', width=6)
        self.axis_combo.pack(side=tk.LEFT, padx=4)
        self.axis_combo.bind('<<ComboboxSelected>>', self.assign_axis)

        settings = ttk.LabelFrame(master, text='绘图设置')
        settings.pack(fill=tk.X, padx=4, pady=2)
        for row, (label, variable) in enumerate((('图形标题', self.titlevar), ('X 轴标题', self.xlabel))):
            ttk.Label(settings, text=label).grid(row=row, column=0, sticky='w')
            ttk.Entry(settings, textvariable=variable).grid(row=row, column=1, sticky='ew')
        self.label_axis = tk.StringVar(value='Y1')
        self.label_axis_combo = ttk.Combobox(settings, textvariable=self.label_axis, values=('Y1',),
                                             state='readonly', width=6)
        self.label_axis_combo.grid(row=2, column=0, sticky='w')
        self.label_axis_combo.bind('<<ComboboxSelected>>', self.select_axis_title)
        self.ylabel = tk.StringVar()
        self.ylabel_entry = ttk.Entry(settings, textvariable=self.ylabel)
        self.ylabel_entry.grid(row=2, column=1, sticky='ew')
        self.ylabel_entry.bind('<KeyRelease>', self.save_axis_title)
        self.ylabel_entry.bind('<FocusOut>', self.save_axis_title)
        ttk.Label(settings, text='Y 轴标题（留空自动生成）').grid(row=2, column=2, padx=4)
        ttk.Checkbutton(settings, text='显示图例', variable=self.show_legend).grid(row=0, column=2)
        ttk.Checkbutton(settings, text='显示网格', variable=self.grid).grid(row=1, column=2)
        settings.columnconfigure(1, weight=1)
        ttk.Label(master, textvariable=self.statusvar, wraplength=420).pack(
            anchor=tk.W, padx=4)

    def update_x_mode(self):
        self.time_combo.configure(state='disabled' if self.sample_mode.get() else 'readonly')

    def selected_columns(self):
        return [self.ylist.get(i) for i in self.ylist.curselection()]

    def update_variables(self, event=None):
        columns = self.selected_columns()
        self.assignments = axis_assignments(columns, self.assignments, self.mode.get())
        selected = self.axis_table.selection()
        self.axis_table.delete(*self.axis_table.get_children())
        for i, column in enumerate(columns):
            self.axis_table.insert('', 'end', iid=str(i), values=(column, f'Y{self.assignments[column]}'))
        limit = {AXIS_MODES[0]: 1, AXIS_MODES[1]: 2}.get(self.mode.get(), max(1, len(columns)))
        self.axis_combo.configure(values=[f'Y{i}' for i in range(1, limit + 1)], state='disabled')
        used = [f'Y{i}' for i in sorted(set(self.assignments.values()))] or ['Y1']
        self.label_axis_combo.configure(values=used)
        if self.label_axis.get() not in used:
            self.label_axis.set(used[0])
        self.select_axis_title()
        if columns:
            self.axis_table.selection_set(selected[0] if selected and int(selected[0]) < len(columns) else '0')
            self.select_variable()

    def select_variable(self, event=None):
        selected = self.axis_table.selection()
        if selected:
            column = self.selected_columns()[int(selected[0])]
            self.axisvar.set(f'Y{self.assignments[column]}')
            self.axis_combo.configure(state='readonly')

    def assign_axis(self, event=None):
        selected = self.axis_table.selection()
        if selected:
            column = self.selected_columns()[int(selected[0])]
            self.assignments[column] = int(self.axisvar.get()[1:])
            self.update_variables()

    def select_axis_title(self, event=None):
        self.ylabel.set(self.ylabels.get(int(self.label_axis.get()[1:]), ''))

    def save_axis_title(self, event=None):
        self.ylabels[int(self.label_axis.get()[1:])] = self.ylabel.get()

    def apply(self):
        columns = self.selected_columns()
        time_column = None if self.sample_mode.get() else self.xvar.get()
        self.save_axis_title()
        try:
            # Validate before replacing the user's previous plot window.
            prepared = prepare_time_series(self.df, columns, time_column)
            gaps = sum(int(pd.isna(prepared[1][column]).sum()) for column in columns
                       if not is_numeric_dtype(self.df[column].dtype))
            self.statusvar.set(f'{gaps} 个状态/缺失点仅在曲线中留空（原表保留）'
                               if gaps else '')
        except ValueError as exc:
            self.error(str(exc))
            return
        viewer = self.showPlotViewer()
        axes = time_series_plot(viewer.fig, self.df, columns, time_column,
                                self.assignments, self.mode.get(), self.titlevar.get(),
                                self.xlabel.get(), self.ylabels, self.show_legend.get(), self.grid.get(),
                                prepared=prepared)
        viewer.ax = next(iter(axes.values()))
        #the navigation bar belongs to the figure, not to the options dock
        viewer.toolbar = NavigationToolbar2Tk(viewer.canvas, viewer.plot_tools)
        viewer.toolbar.update()
        viewer.canvas.draw_idle()
