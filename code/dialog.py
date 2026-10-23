from pandastable_local.dialogs import (
    BaseDialog, EasyListbox, FindReplaceDialog,
    apply_dialog_theme, dialog_style, listbox_colors)
from tkinter import Frame, TOP, LEFT, X, BOTH, Listbox, Scrollbar, VERTICAL, N, S, E, W, END, EXTENDED
from tkinter import ttk
import tkinter as tk
import numpy as np
import json
import os
from pathlib import Path
from numbers import Integral
import warnings
from pandas.api.types import is_numeric_dtype, is_bool_dtype
from inspect import getattr_static
from prettytable import PrettyTable as PT
#  import pandas as pd
############### Own Modules ############
from utilities import is_void, get_number
from help_link import open_help


class findRepDialog(FindReplaceDialog):

    def find(self):
        """Do string search. Creates a masked dataframe for results and then stores each cell
        coordinate in a list."""

        table = self.table
        df = table.model.df
        df = df.astype('object').astype('str')
        s = self.searchvar.get()
        case = self.casevar.get()
        self.search_changed = False
        self.clear()
        if s == '':
            return
        s = s if case else s.upper()
        # Build a boolean mask rather than assigning booleans into string columns.
        found = (df if case else df.apply(lambda col: col.str.upper())).eq(s)
        found = found.fillna(False).astype(bool)
        if not s.replace(' ', ''):
            found[:] = False

        table.highlighted = found
        rows, cols = np.nonzero(found.to_numpy())
        self.coords = list(zip(cols.tolist(), rows.tolist()))
        self.current = 0
        return

    def replace(self):
        """Replace all instances of search text"""

        table = self.table
        if not table.requireUnfiltered():
            return
        table.storeCurrent()
        df = table.model.df
        self.find()
        r = self.replacevar.get()
        for x, y in self.coords:
            df.iloc[y, x] = r
        table.redraw()
        self.search_changed = True
        return

    def findNext(self):
        return


# These labels are confined to dialog presentation; analysis variables stay English.
OPTION_LABELS = {'Distribution': '分布',
 'Normal': '正态分布',
 "Student's t": 't 分布',
 'Gamma': '伽马分布',
 'Lognormal': '对数正态分布',
 'LogNormal': '对数正态分布',
 'Exponential': '指数分布',
 'Weibull': '威布尔分布',
 'Chi Square': '卡方分布',
 'F': 'F 分布',
 't': 't 分布',
 'Binomial': '二项分布',
 'Poisson': '泊松分布',
 'Auto': '自动',
 'On': '开启',
 'Off': '关闭',
 'Use Subgrp ID Col.': '使用子组标识列',
 'Use Subgrp Size': '使用子组大小',
 'Unbiased Std Dev': '无偏标准差',
 'Ranges': '极差',
 'count': '计数',
 'frequency': '频率',
 'proportion': '比例',
 'probability': '概率',
 'percent': '百分比',
 'density': '密度',
 'layer': '叠加',
 'dodge': '并排',
 'stack': '堆叠',
 'fill': '填充',
 'bars': '条形',
 'step': '阶梯线',
 'poly': '多边形',
 'Half': '一半',
 'Full': '全部',
 '1/4': '四分之一',
 'deep': '深色',
 'muted': '柔和',
 'pastel': '粉彩',
 'bright': '明亮',
 'dark': '暗色',
 'colorblind': '色觉友好',
 'Blues': '蓝色',
 'BuGn': '蓝绿',
 'BuPu': '蓝紫',
 'GnBu': '绿蓝',
 'Greens': '绿色',
 'Greys': '灰色',
 'Oranges': '橙色',
 'Purples': '紫色',
 'Reds': '红色',
 'YlGn': '黄绿',
 'YlGnBu': '黄绿蓝',
 'YlOrBr': '黄橙棕',
 'YlOrRd': '黄橙红',
 'BrBG': '棕蓝绿',
 'PiYG': '粉黄绿',
 'PRGn': '紫绿',
 'PuOr': '紫橙',
 'RdBu': '红蓝',
 'RdGy': '红灰',
 'RdYlBu': '红黄蓝',
 'RdYlGn': '红黄绿',
 'Spectral': '光谱',
 'N': '样本量（N）',
 'Mean': '均值',
 'Standard Deviation': '标准差',
 'Standard deviation': '标准差',
 'Variance': '方差',
 'Minimum': '最小值',
 'First Quartile': '第一四分位数',
 'Median': '中位数',
 'Third Quartile': '第三四分位数',
 'Maximum': '最大值',
 'SE of Mean': '均值标准误',
 'Coefficient of Variation': '变异系数',
 'Sum': '总和',
 'Range': '极差',
 'Interquartile Range': '四分位距',
 'Skewness': '偏度',
 'Kurtosis': '峰度',
 'Mode': '众数',
 'N of Mode': '众数个数',
 'Degrees of freedom': '自由度',
 'Numerator degrees of freedom': '分子自由度',
 'Denominator degrees of freedom': '分母自由度',
 'Scale': '尺度',
 'Number of trials': '试验次数',
 'Event probability': '事件概率',
 'NA': '不适用',
 'AIAG (ANOVA)': 'AIAG（ANOVA）',
 'EMP (ANOVA)': 'EMP（ANOVA）',
 'XBAR/R': '均值-极差（XBAR/R）'}
DIALOG_TITLES = {'Linear Regression': '线性回归',
 'Correlation': '相关分析',
 'Orthogonal Regression': '正交回归',
 'Stats Summary': '描述性统计',
 'Stats Summary Multi Datasets': '多变量描述性统计',
 'Normality Test': '正态性检验',
 'Residual Plots': '残差图',
 'Confidence Intervals': '置信区间',
 'Multi Column Correlation': '多变量相关分析',
 'One sample mean t-test': '单样本 t 检验',
 'One sample mean Z-test': '单样本 Z 检验',
 'One sample Std Dev test': '单样本标准差检验',
 'Two samples t-test': '双样本 t 检验',
 'Paired t-test': '配对 t 检验',
 'Mutli-sample Std Dev Test': '多样本标准差检验',
 'One Proportion Test': '单比例检验',
 'Two Proportions Test': '双比例检验',
 'One-Way ANOVA': '单因子方差分析（ANOVA）',
 "Mean Comparison Student's t": '均值比较（t 检验）',
 'Two-Way ANOVA': '双因子方差分析（ANOVA）',
 'Contingency Table and Chi SQ Test': '交叉表与卡方检验',
 'Propabilities Chi SQ Test': '比例卡方检验',
 'Crossed Gage R&R': '交叉量具 R&R',
 'Nested Gage R&R': '嵌套量具 R&R',
 'Process Capability': '过程能力分析',
 'Process Capability with Subgroups': '含子组的过程能力分析',
 'Normal Dist TI': '正态分布公差区间',
 'Control Chart I/MR': '单值-移动极差控制图（I/MR）',
 'Control Chart I': '单值控制图（I）',
 'Control Chart MR': '移动极差控制图（MR）',
 'Control Chart X Bar/R': '均值-极差控制图（Xbar/R）',
 'Control Chart X Bar/S': '均值-标准差控制图（Xbar/S）',
 'Control Chart NP': '不合格品数控制图（NP）',
 'Control Chart P': '不合格品率控制图（P）',
 'Control Chart C': '缺陷数控制图（C）',
 'Control Chart U': '单位缺陷数控制图（U）',
 'Fit Distributions': '分布拟合',
 'Histogram + Distribution Fit': '直方图与分布拟合',
 'Histogram with Groups': '分组直方图',
 '2D Histogram': '二维直方图',
 'Box Plot': '箱线图',
 'Box Plot with Groups': '分组箱线图',
 'Count Plot with Groups': '分组计数图',
 'Line Plot with Groups': '分组折线图',
 'Dot Plot with Groups': '分组点图',
 'Distribution Plot': '概率分布图',
 'Distribution Plot Compare': '概率分布比较图'}


def display_text(value):
    return OPTION_LABELS.get(value, value)


def display_variable(variable, values=("Auto",), labels=OPTION_LABELS, *, owner):
    """Bind Chinese widget text to the original, unchanged analysis variable."""
    shown = tk.StringVar(master=owner, value=labels.get(variable.get(), variable.get()))
    reverse = {labels.get(value, value): value for value in values}

    def show(*_):
        value = labels.get(variable.get(), variable.get())
        if shown.get() != value:
            shown.set(value)

    def store(*_):
        value = reverse.get(shown.get(), shown.get())
        if variable.get() != value:
            variable.set(value)

    source_trace = variable.trace_add('write', show)
    display_trace = shown.trace_add('write', store)

    def cleanup(event):
        if event.widget == owner:
            variable.trace_remove('write', source_trace)
            shown.trace_remove('write', display_trace)

    owner.bind('<Destroy>', cleanup, add='+')
    return shown


def option_combobox(master, *, values, textvariable, labels=OPTION_LABELS, **kwargs):
    shown = display_variable(textvariable, values, labels, owner=master)
    widget = ttk.Combobox(master, values=[labels.get(v, v) for v in values],
                          textvariable=shown, **kwargs)
    widget.display_variable = shown
    return widget


_COLUMN_SETTINGS_KEY = r'Software\MiniJMP\ColumnSelections'


def _column_settings_file():
    return Path.home() / '.config' / 'MiniJMP' / 'column_selections.json'


def _read_column_history(key):
    try:
        if os.name == 'nt':
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _COLUMN_SETTINGS_KEY) as registry:
                raw, _ = winreg.QueryValueEx(registry, key)
            value = json.loads(raw)
        else:
            value = json.loads(_column_settings_file().read_text(encoding='utf-8')).get(key, {})
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, TypeError, AttributeError):
        return {}


def _write_column_history(key, values):
    try:
        if os.name == 'nt':
            import winreg
            with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, _COLUMN_SETTINGS_KEY,
                                    0, winreg.KEY_SET_VALUE) as registry:
                winreg.SetValueEx(registry, key, 0, winreg.REG_SZ,
                                  json.dumps(values, ensure_ascii=False))
        else:
            dest = _column_settings_file()
            try:
                data = json.loads(dest.read_text(encoding='utf-8'))
            except (OSError, ValueError):
                data = {}
            if not isinstance(data, dict):
                data = {}
            data[key] = values
            dest.parent.mkdir(parents=True, exist_ok=True)
            temp = dest.with_suffix('.tmp')
            try:
                temp.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
                os.replace(temp, dest)
            finally:
                temp.unlink(missing_ok=True)
    except (OSError, ValueError) as exc:
        warnings.warn('无法保存列选择偏好：' + str(exc), RuntimeWarning)


class Dialogs(BaseDialog):
    def __init__(self, parent=None, df=None, title='', app=None):

        BaseDialog.__init__(self, parent, df, DIALOG_TITLES.get(title, title))
        # Mock dynamically invents attributes; only use an explicitly defined hook.
        self.app = (app.sheet_app(parent)
                    if callable(getattr_static(app, 'sheet_app', None)) else app)
        m = ttk.Frame(self.main)
        m.pack(side=TOP)

        self.cols = list(self.df.columns)
        self.valcols = list(
            self.df.select_dtypes(
                include=[
                    np.float64,
                    np.int32,
                    np.int64]))
        #  self.vars = OrderedDict()
        self.title = title
        self.add_window_help(m)
        self.createWidgets(m)
        self._init_column_selection(parent)
        self.buttonsFrame()
        self.main.bind('<F1>', self.help)
        apply_dialog_theme(self.main)
        return

    # Explicit roles only: ordinary option controls must never receive column names.
    column_roles = ()

    def _init_column_selection(self, source):
        self._column_key = type(self).__module__ + '.' + type(self).__name__ + ':' + str(getattr(self, 'kind', ''))
        roles = list(self.column_roles)
        if type(self).__name__ in ('BasicPlotDialog', 'StatPlotDialog'):
            roles = ([(f'xyz.{i}', True) for i in range(len(self.xyz))]
                     if hasattr(self, 'xyz') else [('variables', True)])
            for name in ('labels', 'group'):
                if hasattr(self, name):
                    roles.append((name, False))
        self._column_fields = []
        for name, numeric in roles:
            if name.startswith('xyz.'):
                field = self.xyz[int(name.split('.')[1])]
            else:
                field = getattr(self, name)
            self._column_fields.append((name, field, numeric))
        self._column_snapshot = None
        history = _read_column_history(self._column_key) if roles else {}
        indices = getattr_static(source, 'multiplecollist', [])
        indices = indices if isinstance(indices, (list, tuple)) else []
        selected = [self.cols[i] for i in sorted(set(
            i for i in indices if isinstance(i, Integral) and not isinstance(i, bool)
            and 0 <= i < len(self.cols)))]
        used = set()
        for name, field, numeric in self._column_fields:
            previous = history.get(name, [])
            previous = previous if isinstance(previous, list) else []
            current = [c for c in selected if self._column_valid(c, numeric) and c not in used]
            picks = current or [c for c in previous if self._column_valid(c, numeric) and c not in used]
            if (not isinstance(field, Listbox)
                    or getattr(self, 'kind', None) in ('pie', 'stem', 'probability')):
                picks = picks[:1]
            if isinstance(field, Listbox):
                for i in range(field.size()):
                    if field.get(i) in picks:
                        field.selection_set(i)
            elif picks:
                field.set(picks[0])
            used.update(picks)

    def _column_valid(self, name, numeric):
        if (not isinstance(name, str) or not name or self.cols.count(name) != 1
                or name not in self.df.columns):
            return False
        dtype = self.df[name].dtype
        return not numeric or (is_numeric_dtype(dtype) and not is_bool_dtype(dtype))

    def _collect_column_selection(self):
        values = {}
        for name, field, numeric in getattr(self, '_column_fields', ()):
            picks = (list(field.getSelectedItem()) if isinstance(field, Listbox)
                     else [field.get()])
            values[name] = [c for c in picks if self._column_valid(c, numeric)]
        return values

    def quit(self):
        self._column_snapshot = self._collect_column_selection()
        super().quit()

    def remember_columns(self, roles=None):
        """Called only after the analysis succeeds; preview commits after rendering."""
        values = getattr(self, '_column_snapshot', None)
        if values is None:
            values = self._collect_column_selection()
        if roles is not None:
            values = {name: picks for name, picks in values.items() if name in roles}
        if not values or not any(values.values()):
            return
        values = {**_read_column_history(self._column_key), **values}
        if getattr(self, '_previewing', False):
            self._column_pending = values
        else:
            _write_column_history(self._column_key, values)

    def add_window_help(self, m):
        f = ttk.LabelFrame(m, text='')
        f.pack(side=TOP, fill=BOTH, padx=2)
        txt = self.app.dialog_help_msg(key=self.title)
        #  print("Receive txt", txt)
        if len(txt) == 0:
            return
        txt = txt + " ［单击“帮助”了解更多信息。］"
        w = ttk.Label(
            f,
            anchor="w",
            justify=LEFT,
            wraplength=400,
            text=txt)
        w.pack(side=TOP, fill=BOTH, padx=3, pady=3)
        return

    def help(self, event=None):
        open_help(self.__class__.__name__, parent=self.main)
        return 'break'

    def buttonsFrame(self):
        bf = ttk.Frame(self.main)
        bf.pack(side=TOP, fill=BOTH)
        ttk.Button(bf, text='确定', command=self.ok).pack(
            side=LEFT, fill=X, expand=1, pady=2)
        ttk.Button(bf, text='取消', command=self.quit).pack(
            side=LEFT, fill=X, expand=1, pady=2)
        ttk.Button(bf, text='帮助', command=self.help).pack(
            side=LEFT, fill=X, expand=1, pady=2)
        return

    def ok(self):
        self.quit()
        self.apply()
        return

    def add_xy_plot_settings(self, m):
        self.add_x_plot_settings(m)
        self.add_y_plot_settings(m)
        self.add_misc_plot_settings(m)
        return

    def add_x_plot_settings(self, m):
        self.xlabel = tk.StringVar(value="")
        self.x_min = tk.StringVar(value="Auto")
        self.x_max = tk.StringVar(value="Auto")

        master = ttk.LabelFrame(m, text='X 轴')
        master.pack(side=TOP, fill=BOTH, padx=2)
        ttk.Label(master, text='标签').pack(side=LEFT, fill=X, padx=2)
        ttk.Entry(master, textvariable=self.xlabel, width=15).pack(
            side=LEFT, padx=2, pady=2)
        ttk.Label(master, text='最小值').pack(side=LEFT, fill=X, padx=2)
        ttk.Entry(master, textvariable=display_variable(self.x_min, owner=master), width=5).pack(
            side=LEFT, padx=2, pady=2)
        ttk.Label(master, text='最大值').pack(side=LEFT, fill=X, padx=2)
        ttk.Entry(master, textvariable=display_variable(self.x_max, owner=master), width=5).pack(
            side=LEFT, padx=2, pady=2)
        return

    def add_y_plot_settings(self, m):
        self.ylabel = tk.StringVar(value="")
        self.y_min = tk.StringVar(value="Auto")
        self.y_max = tk.StringVar(value="Auto")

        master = ttk.LabelFrame(m, text='Y 轴')
        master.pack(side=TOP, fill=BOTH, padx=2)
        ttk.Label(master, text='标签').pack(side=LEFT, fill=X, padx=2)
        ttk.Entry(master, textvariable=self.ylabel, width=15).pack(
            side=LEFT, padx=2, pady=2)
        ttk.Label(master, text='最小值').pack(side=LEFT, fill=X, padx=2)
        ttk.Entry(master, textvariable=display_variable(self.y_min, owner=master), width=5).pack(
            side=LEFT, padx=2, pady=2)
        ttk.Label(master, text='最大值').pack(side=LEFT, fill=X, padx=2)
        ttk.Entry(master, textvariable=display_variable(self.y_max, owner=master), width=5).pack(
            side=LEFT, padx=2, pady=2)
        return

    def add_misc_plot_settings(self, m):
        self.grid = tk.BooleanVar(value=False)
        self.show_legend = tk.BooleanVar(value=False)
        self.ax_margin = tk.DoubleVar(value=0.1)

        master = ttk.LabelFrame(m, text='绘图设置')
        master.pack(side=TOP, fill=BOTH, padx=2)
        ttk.Checkbutton(master, text='显示网格线',
                        variable=self.grid).pack(side=LEFT, padx=2, pady=2)
        ttk.Checkbutton(master, text='显示图例',
                        variable=self.show_legend).pack(side=LEFT, padx=2, pady=2)
        ttk.Label(master, text='边距').pack(side=LEFT, fill=X, padx=2)
        ttk.Entry(master, textvariable=self.ax_margin, width=5).pack(
            side=LEFT, padx=2, pady=2)
        return

    def add_alpha(self, m):
        self.alpha = tk.DoubleVar(value=0.05)
        master = ttk.LabelFrame(m, text='置信区间等的显著性水平')
        master.pack(side=TOP, fill=BOTH, padx=2)
        ttk.Label(master, text='显著性水平（α）').pack(side=LEFT, fill=X, padx=2)
        ttk.Entry(master, textvariable=self.alpha, width=5).pack(
            side=LEFT, padx=2, pady=2)
        return

    def get_plot_settings(self):
        self.get_x_plot_settings()
        self.get_y_plot_settings()
        self.get_misc_plot_settings()
        return

    def get_x_plot_settings(self):
        self.x_max = get_number(self.x_max)
        self.x_min = get_number(self.x_min)
        self.xlabel = None if self.xlabel.get() == "" else self.xlabel.get()
        return

    def get_y_plot_settings(self):
        self.y_max = get_number(self.y_max)
        self.y_min = get_number(self.y_min)
        self.ylabel = None if self.ylabel.get() == "" else self.ylabel.get()
        return

    def get_misc_plot_settings(self):
        self.ax_margin = self.ax_margin.get()
        self.show_legend = self.show_legend.get()
        self.grid = self.grid.get()
        return

    def update_vars(self):
        """ Do nothing, can be updated """
        return

    def error(self, msg=None):
        if msg is None:
            return
        t = PT()
        t.field_names = ["ERROR"]
        t.add_row([msg])
        self.app.print("\n" + str(t))
        return


class superEasyListbox(EasyListbox):
    def __init__(
            self,
            parent,
            width,
            height,
            yscrollcommand,
            listItemSelected):
        self._listItemSelected = listItemSelected
        Listbox.__init__(self, parent,
                         width=width, height=height,
                         yscrollcommand=yscrollcommand,
                         selectmode=EXTENDED, exportselection=0)
        self.bind("<<ListboxSelect>>", self.triggerListItemSelected)
        try:
            style = dialog_style(self.winfo_toplevel())
            self.configure(**listbox_colors(style))
        except Exception:
            self.configure(background='white', foreground='black',
                           selectbackground='#0174DF',
                           selectforeground='white')
        return


def addListBox(parent, values=[], width=10, height=6, label=''):
    """Add an EasyListBox"""

    frame = ttk.Frame(parent)
    ttk.Label(frame, text=label).grid(row=0)
    yScroll = ttk.Scrollbar(frame, orient=VERTICAL)
    yScroll.grid(row=1, column=1, sticky=N + S)

    def listItemSelected(index):
        return index
    lbx = superEasyListbox(frame, width, height, yScroll.set, listItemSelected)
    lbx.grid(row=1, column=0, sticky=N + S + E + W)
    frame.columnconfigure(0, weight=1)
    frame.rowconfigure(0, weight=1)
    yScroll["command"] = lbx.yview
    for i in values:
        lbx.insert(END, i)
    return frame, lbx
