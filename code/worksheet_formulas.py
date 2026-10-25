"""Restricted worksheet column formulas with dependency-aware recalculation."""
import ast
import re
from tkinter import BooleanVar, END, Listbox, StringVar, Toplevel, messagebox, ttk

import numpy as np
import pandas as pd
from pandas.api.types import is_bool_dtype, is_numeric_dtype

from pandastable_local.dialogs import apply_dialog_theme
from utilities import verifyNewColName


class FormulaError(ValueError):
    """A formula problem the user can correct."""


FUNCTIONS = {
    'ABS': np.abs, 'SQRT': np.sqrt, 'LOG': np.log, 'LOG10': np.log10,
    'EXP': np.exp, 'ROUND': np.round, 'FLOOR': np.floor,
    'CEIL': np.ceil, 'TRUNC': np.trunc,
}
SYMBOLS = {'Add': np.add, 'Sub': np.subtract, 'Mult': np.multiply,
           'Div': np.divide, 'Mod': np.mod, 'Pow': np.power}
TOKEN = re.compile(r'(?<![\w.])[Cc](\d+)(?![\w])')
ALLOWED_NODES = (
    ast.Expression, ast.Constant, ast.Name, ast.Load, ast.UnaryOp, ast.UAdd,
    ast.USub, ast.BinOp, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod,
    ast.Pow, ast.Call,
)


def column_labels(df):
    """Column picker entries; positions follow the worksheet display."""
    return [f'C{i + 1}  {name}' for i, name in enumerate(df.columns)]


def _tree(expression):
    if not isinstance(expression, str) or not expression.strip():
        raise FormulaError('表达式不能为空。')
    try:
        tree = ast.parse(expression, mode='eval')
    except SyntaxError as error:
        raise FormulaError(f'表达式语法错误：{error.msg}') from None
    if any(not isinstance(node, ALLOWED_NODES) for node in ast.walk(tree)):
        raise FormulaError('表达式包含不支持的语法。')
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if (not isinstance(node.func, ast.Name)
                    or node.func.id.upper() not in FUNCTIONS):
                raise FormulaError(f'不支持的函数“{ast.unparse(node.func)}”。')
        elif (isinstance(node, ast.Name) and _token(node) is None
              and node.id.upper() not in FUNCTIONS):
            raise FormulaError(f'无法识别的名称“{node.id}”；列请写作 C1、C2。')
    return tree


def _token(node):
    if isinstance(node, ast.Name) and node.id[:1] in 'Cc' and node.id[1:].isdigit():
        return 'C' + node.id[1:]
    return None


def _arguments(node):
    if node.keywords:
        raise FormulaError('函数不支持关键字参数。')
    return node.args


def _scalar(value, digits=False):
    if isinstance(value, np.ndarray) or hasattr(value, 'shape'):
        raise FormulaError('ROUND 的位数必须是常量。')
    value = float(value)
    if digits:
        if not value.is_integer():
            raise FormulaError('ROUND 的位数必须是整数。')
        return int(value)
    return value


def _eval(node, series):
    if isinstance(node, ast.Expression):
        return _eval(node.body, series)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise FormulaError('只支持数值常量。')
        return float(node.value)
    if isinstance(node, ast.Name):
        token = _token(node)
        if token is None:
            raise FormulaError(f'无法识别的名称“{node.id}”；列请写作 C1、C2。')
        if token not in series:
            raise FormulaError(f'公式引用了不可用的列 {token}。')
        return series[token]
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = _eval(node.operand, series)
        return -value if isinstance(node.op, ast.USub) else value
    if isinstance(node, ast.BinOp) and type(node.op).__name__ in SYMBOLS:
        return SYMBOLS[type(node.op).__name__](
            _eval(node.left, series), _eval(node.right, series))
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        name = node.func.id.upper()
        if name not in FUNCTIONS:
            raise FormulaError(f'不支持的函数“{node.func.id}”。')
        args = _arguments(node)
        if name == 'ROUND':
            if len(args) not in (1, 2):
                raise FormulaError('ROUND 需要 1 或 2 个参数。')
            digits = _scalar(_eval(args[1], series), digits=True) if len(args) == 2 else 0
            return FUNCTIONS[name](_eval(args[0], series), digits)
        if len(args) != 1:
            raise FormulaError(f'{name} 需要 1 个参数。')
        return FUNCTIONS[name](_eval(args[0], series))
    raise FormulaError('表达式包含不支持的语法。')


def _references(tree):
    refs = []
    for node in ast.walk(tree):
        token = _token(node)
        if token is not None and token not in refs:
            refs.append(token)
        elif isinstance(node, ast.Attribute):
            raise FormulaError('表达式不支持属性访问。')
        elif isinstance(node, (ast.Subscript, ast.Lambda, ast.Dict, ast.List, ast.Tuple,
                               ast.Compare, ast.BoolOp, ast.IfExp)):
            raise FormulaError('表达式包含不支持的语法。')
    if not refs and not any(isinstance(n, ast.Constant) for n in ast.walk(tree)):
        raise FormulaError('表达式没有可计算的内容。')
    return refs


def _numeric(series, name):
    if not is_numeric_dtype(series) or is_bool_dtype(series):
        raise FormulaError(f'列“{name}”不是数值列。')
    return series


def make_formula(target, expression, df):
    """Resolve C-references to stable column names after validation."""
    tree = _tree(expression)
    refs = _references(tree)
    resolved = {}
    columns = list(df.columns)
    for token in refs:
        index = int(token[1:]) - 1
        if not 0 <= index < len(columns):
            raise FormulaError(f'引用列 {token} 超出工作表范围。')
        name = columns[index]
        if name not in columns:
            raise FormulaError(f'公式引用的列“{name}”已不存在。')
        resolved[token] = name
        _numeric(df[name], name)
    return {'target': target, 'expression': expression.strip(), 'sources': resolved,
            'stale': False, 'error': '', 'warning': ''}


def display_expression(formula, df):
    """Show C positions for the current column order without losing sources."""
    columns = list(df.columns)
    positions = {token: f'C{columns.index(name) + 1}'
                 for token, name in formula['sources'].items() if name in columns}
    return TOKEN.sub(lambda match: positions.get('C' + match.group(1), match.group(0)),
                     formula['expression'])


def _dependency_graph(formulas):
    return {target: [name for name in formula['sources'].values() if name in formulas]
            for target, formula in formulas.items()}


def cycle_message(formulas):
    graph = _dependency_graph(formulas)
    state = {}

    def visit(node, path):
        state[node] = 1
        for dependency in graph.get(node, ()):
            if state.get(dependency) == 1:
                start = path.index(dependency) if dependency in path else -1
                cycle = path[start:] + [dependency] if start >= 0 else [node, dependency]
                return ' → '.join(str(name) for name in cycle)
            if state.get(dependency) is None:
                found = visit(dependency, path + [dependency])
                if found:
                    return found
        state[node] = 2
        return None

    for target in formulas:
        if state.get(target) is None:
            found = visit(target, [target])
            if found:
                return found
    return ''


def formula_order(formulas):
    """Sources before dependants; unterminated cycles are appended last."""
    graph = _dependency_graph(formulas)
    order = []
    while len(order) < len(formulas):
        ready = [name for name in formulas
                 if name not in order and all(dep in order for dep in graph[name])]
        if not ready:
            return order + [name for name in formulas if name not in order]
        order.extend(sorted(ready, key=str))
    return order


def _evaluate(formula, target, df):
    if target not in df.columns:
        raise FormulaError(f'目标列“{target}”已不存在。')
    tree = _tree(formula['expression'])
    refs = _references(tree)
    columns = list(df.columns)
    series = {}
    for token in refs:
        name = formula['sources'].get(token)
        if name is None or name not in columns:
            raise FormulaError(f'公式引用的列“{name or token}”已不存在。')
        series[token] = _numeric(df[name], name)
    with np.errstate(divide='ignore', invalid='ignore', over='ignore'):
        values = _eval(tree, series)
    values = np.asarray(values, dtype=float)
    if values.ndim == 0:
        values = np.full(len(df), float(values))
    elif values.shape != (len(df),):
        raise FormulaError('表达式结果的行数与工作表不一致。')
    finite = np.isfinite(values)
    return np.where(finite, values, np.nan), bool(np.isinf(values).any())


def evaluate(formulas, df):
    """Return a recalculated copy; per-formula problems become column notes."""
    result = df.copy(deep=True)
    cycle = cycle_message(formulas)
    if cycle:
        for formula in formulas.values():
            formula['error'] = f'存在循环引用：{cycle}'
            formula['stale'] = True
        return result
    for target in formula_order(formulas):
        formula = formulas[target]
        try:
            values, overflow = _evaluate(formula, target, result)
        except FormulaError as error:
            formula['error'] = str(error)
            formula['stale'] = True
            continue
        formula['error'] = ''
        formula['warning'] = '部分结果溢出或被零除，已写为空值。' if overflow else ''
        formula['stale'] = False
        result[target] = values
    return result


def signature(formulas, df):
    """Cheap change detector for manual mode; result columns are excluded."""
    marks = []
    for target, formula in formulas.items():
        for name in formula['sources'].values():
            if name in df.columns and name not in formulas:
                marks.append((target, name,
                              pd.util.hash_pandas_object(df[name], index=False)
                              .to_numpy().tobytes()))
    return marks


def formula_columns(formulas):
    return set(formulas)


def new_column_name(columns, name):
    if name in columns:
        raise FormulaError(f'列“{name}”已存在，请直接选择该列。')
    return verifyNewColName(name, list(columns))


class CalculatorDialog:
    """Target column, expression, column picker and auto association."""

    def __init__(self, table, target_index=None):
        self.table = table
        self.df = table.model.df
        self.labels = column_labels(self.df)
        self.main = Toplevel(table.winfo_toplevel())
        self.main.title('计算器')
        self.main.transient(table.winfo_toplevel())
        self.main.resizable(False, False)
        self.main.protocol('WM_DELETE_WINDOW', self.quit)
        apply_dialog_theme(self.main, table.winfo_toplevel())
        body = ttk.Frame(self.main, padding=6)
        body.pack(fill='both', expand=True)

        target = self.df.columns[target_index] if target_index is not None else None
        self.formula = table.formula_for(target)
        if self.formula is not None:
            target_index = list(self.df.columns).index(target)

        frame = ttk.LabelFrame(body, text='目标列')
        frame.pack(fill='x', pady=(0, 6))
        self.target = StringVar()
        self.target_combo = ttk.Combobox(frame, textvariable=self.target, values=self.labels,
                                         state='readonly', width=22)
        self.target_combo.pack(side='left', padx=2, pady=2)
        if target_index is not None and self.labels:
            self.target_combo.current(target_index)
        ttk.Label(frame, text='或新建列').pack(side='left', padx=(10, 2))
        self.new_name = StringVar()
        ttk.Entry(frame, textvariable=self.new_name, width=12).pack(side='left', padx=2)

        frame = ttk.LabelFrame(body, text='表达式')
        frame.pack(fill='x', pady=(0, 6))
        self.expression = StringVar(
            value=display_expression(self.formula, self.df) if self.formula else '')
        self.entry = ttk.Entry(frame, textvariable=self.expression, width=48)
        self.entry.pack(fill='x', padx=2, pady=2)
        buttons = ttk.Frame(frame)
        buttons.pack(fill='x', padx=2, pady=(0, 2))
        for name in ('ABS', 'SQRT', 'LOG', 'LOG10', 'EXP', 'ROUND', 'FLOOR', 'CEIL', 'TRUNC'):
            ttk.Button(buttons, text=name, width=7,
                       command=lambda name=name: self.insert(name + '(')).pack(side='left')

        frame = ttk.LabelFrame(body, text='列')
        frame.pack(fill='both', pady=(0, 6))
        self.columns = Listbox(frame, height=5, width=40, exportselection=False)
        for label in self.labels:
            self.columns.insert(END, label)
        self.columns.pack(side='left', padx=2, pady=2)
        self.columns.bind('<Double-Button-1>', self.pick_column)

        self.auto = BooleanVar(value=self.formula is not None)
        ttk.Checkbutton(body, text='关联公式，源数据变化时自动计算',
                        variable=self.auto).pack(anchor='w')
        buttons = ttk.Frame(body)
        buttons.pack(fill='x', pady=(6, 0))
        ttk.Button(buttons, text='确定', command=self.ok).pack(side='left', expand=True, fill='x')
        ttk.Button(buttons, text='取消', command=self.quit).pack(side='left', expand=True, fill='x')
        self.main.grab_set()
        self.entry.focus_set()
        self.main.wait_window()

    def insert(self, text):
        self.entry.insert('insert', text)
        self.entry.focus_set()

    def pick_column(self, event=None):
        selection = self.columns.curselection()
        if selection:
            self.insert(f'C{selection[0] + 1}')
        return 'break'

    def ok(self):
        expression = self.expression.get().strip()
        new_name = self.new_name.get().strip()
        if new_name:
            try:
                target = new_column_name(self.df.columns, new_name)
            except FormulaError as error:
                messagebox.showwarning('列名无效', str(error), parent=self.main)
                return
        elif self.target.get() in self.labels:
            target = self.df.columns[self.labels.index(self.target.get())]
        else:
            messagebox.showwarning('无法计算', '请选择目标列或输入新列名。', parent=self.main)
            return
        try:
            self.table.define_formula(target, expression, link=self.auto.get())
        except FormulaError as error:
            messagebox.showerror('公式错误', str(error), parent=self.main)
            return
        self.main.destroy()

    def quit(self):
        self.main.destroy()
