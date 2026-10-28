"""定义自定义 DOE 设计的 GUI：来源工作表 → 因子/角色 → 列映射 → 预览 → 确认。"""
import tkinter as tk
from tkinter import messagebox, ttk

from doe_core import FactorSpec
from doe_custom import define_custom
from help_link import open_help


_TITLES = {'custom_factorial': '定义自定义因子设计',
           'custom_rsm': '定义自定义响应面设计',
           'custom_screening': '定义自定义筛选设计'}
_PREVIEW_ROWS = 40


class DefineCustomDOE:
    def __init__(self, app, design_type):
        if design_type not in _TITLES:
            raise ValueError('未知自定义设计类型')
        self.app = app
        self.design_type = design_type
        self.main = tk.Toplevel(app.main)
        self.main.title(_TITLES[design_type])
        self.main.transient(app.main)
        self.main.bind('<F1>', lambda event: open_help('doe.custom', parent=self.main))
        body = ttk.Frame(self.main, padding=10)
        body.pack(fill='both', expand=True)
        top = ttk.Frame(body)
        top.pack(fill='x')
        ttk.Label(top, text='来源工作表').pack(side='left')
        self.sheet = ttk.Combobox(top, values=tuple(app.sheets), state='readonly',
                                  width=24)
        self.sheet.set(app.getCurrentSheet() if app.getCurrentSheet() in app.sheets
                       else next(iter(app.sheets)))
        self.sheet.pack(side='left', padx=4)
        self.sheet.bind('<<ComboboxSelected>>', lambda event: self._refresh())
        ttk.Label(top, text='设计 ID').pack(side='left', padx=(12, 2))
        self.design_id = ttk.Entry(top, width=18)
        self.design_id.insert(0, f'custom-{design_type.split("_", 1)[1]}')
        self.design_id.pack(side='left')
        ttk.Label(top, text='响应').pack(side='left', padx=(12, 2))
        self.response = ttk.Combobox(top, state='readonly', width=16)
        self.response.pack(side='left')

        middle = ttk.Frame(body)
        middle.pack(fill='both', expand=True, pady=6)
        left = ttk.LabelFrame(middle, text='因子与列映射', padding=6)
        left.pack(side='left', fill='both', expand=True)
        self.factor_rows = []
        header = ('ID', '名称', '类型', '低', '高', '分类水平', '设定列')
        for column, label in enumerate(header):
            ttk.Label(left, text=label).grid(row=0, column=column, padx=2)
        for index in range(10):
            row = []
            for column, width in enumerate((6, 10, 10, 8, 8, 14, 12)):
                if column == 2:
                    widget = ttk.Combobox(left, values=('连续', '两水平分类'),
                                          state='readonly', width=width)
                    widget.set('连续' if index < 2 else '')
                else:
                    widget = ttk.Entry(left, width=width)
                widget.grid(row=index + 1, column=column, padx=2, pady=1)
                row.append(widget)
            row[0].insert(0, f'X{index + 1}')
            self.factor_rows.append(row)
        ttk.Label(left, text='设计列（留空则按默认规则生成）').grid(
            row=11, column=0, columnspan=7, sticky='w', pady=(6, 0))
        self.mapping = {}
        for offset, (key, label) in enumerate((
                ('run_id', '运行ID'), ('standard_order', '标准序'),
                ('run_order', '运行序'), ('point_type', '点类型'),
                ('replicate', '重复'), ('block', '区组'))):
            ttk.Label(left, text=label).grid(row=12 + offset // 3, column=(offset % 3) * 2,
                                             sticky='w')
            widget = ttk.Combobox(left, state='readonly', width=14)
            widget.grid(row=12 + offset // 3, column=(offset % 3) * 2 + 1, padx=2)
            self.mapping[key] = widget
        ttk.Label(left, text='模型项（响应面必填，分号分隔）').grid(
            row=14, column=0, columnspan=7, sticky='w')
        self.terms = ttk.Entry(left, width=60)
        self.terms.grid(row=15, column=0, columnspan=7, sticky='we', pady=2)
        right = ttk.LabelFrame(middle, text='预览', padding=6)
        right.pack(side='left', fill='both', expand=True, padx=(6, 0))
        self.preview = tk.Text(right, width=52, height=22, wrap='none')
        scroll = ttk.Scrollbar(right, orient='vertical', command=self.preview.yview)
        scroll_x = ttk.Scrollbar(right, orient='horizontal', command=self.preview.xview)
        self.preview.configure(yscrollcommand=scroll.set, xscrollcommand=scroll_x.set)
        self.preview.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')
        scroll_x.pack(side='bottom', fill='x')

        buttons = ttk.Frame(body)
        buttons.pack(fill='x')
        ttk.Button(buttons, text='预览', command=self.preview_click).pack(side='left')
        ttk.Button(buttons, text='确认定义', command=self.create).pack(side='left', padx=6)
        ttk.Button(buttons, text='取消', command=self.main.destroy).pack(side='left')
        self.status = tk.StringVar(value='')
        ttk.Label(body, textvariable=self.status).pack(fill='x')
        self._refresh()
        self.main.geometry('1080x640')

    def _frame(self):
        table = self.app.sheets.get(self.sheet.get())
        if table is None:
            raise ValueError('来源工作表已关闭')
        return self.app._full_frame(table).copy(deep=True)

    def _refresh(self):
        try:
            frame = self._frame()
        except ValueError:
            return
        columns = tuple(str(column) for column in frame.columns)
        self.response.configure(values=columns)
        if not self.response.get() or self.response.get() not in columns:
            self.response.set(columns[-1] if columns else '')
        for key, widget in self.mapping.items():
            widget.configure(values=('',) + columns)
            if not widget.get():
                guess = {'run_id': '运行ID', 'standard_order': '标准序',
                         'run_order': '运行序', 'point_type': '点类型',
                         'replicate': '重复', 'block': '区组'}[key]
                widget.set(guess if guess in columns else '')
        for row in self.factor_rows:
            factor_id = row[0].get().strip()
            row[6].delete(0, 'end')
            for candidate in (factor_id, f'设定_{factor_id}'):
                if candidate in columns:
                    row[6].insert(0, candidate)
                    break
        self.terms.delete(0, 'end')
        if self.design_type == 'custom_rsm':
            ids = [row[0].get().strip() for row in self.factor_rows
                   if row[0].get().strip()]
            self.terms.insert(0, ';'.join(ids))
        self._show_preview()

    def _factors(self):
        result = []
        for row in self.factor_rows:
            factor_id = row[0].get().strip()
            if not factor_id:
                continue
            name = row[1].get().strip() or factor_id
            kind = row[2].get()
            if kind == '两水平分类':
                levels = [item.strip() for item in row[5].get().split(';') if item.strip()]
                if len(levels) != 2:
                    raise ValueError(f'因子 {factor_id} 需要两个分类水平')
                result.append(FactorSpec(factor_id, name, None, None,
                                         factor_type='categorical',
                                         levels=tuple(levels),
                                         level_type=('text' if all(
                                             not _numeric(level) for level in levels)
                                             else 'numeric')))
            else:
                try:
                    low = float(row[3].get())
                    high = float(row[4].get())
                except ValueError as error:
                    raise ValueError(f'因子 {factor_id} 的低/高水平必须是数值') from error
                result.append(FactorSpec(factor_id, name, low, high))
        if not result:
            raise ValueError('至少需要一个因子')
        return tuple(result)

    def _column_map(self, factors, frame):
        result = {}
        for key, widget in self.mapping.items():
            value = widget.get()
            if key == 'block':
                result[key] = value or None
            elif value:
                result[key] = _column(frame, value)
        missing = [key for key in ('run_id', 'standard_order', 'run_order',
                                   'point_type', 'replicate') if key not in result]
        if missing:
            raise ValueError('缺少设计列：' + '、'.join(missing))
        result['factors'] = {}
        for factor, row in zip(factors, [row for row in self.factor_rows
                                         if row[0].get().strip()]):
            label = row[6].get()
            if not label:
                raise ValueError(f'请选择因子 {factor.factor_id} 的设定列')
            result['factors'][factor.factor_id] = _column(frame, label)
        result['responses'] = {self.response.get(): _column(frame, self.response.get())}
        return result

    def _build(self):
        frame = self._frame()
        factors = self._factors()
        mapping = self._column_map(factors, frame)
        terms = [item.strip() for item in self.terms.get().split(';') if item.strip()]
        if self.design_type == 'custom_rsm' and not terms:
            raise ValueError('自定义响应面设计必须声明模型项')
        result, metadata, summary = define_custom(
            frame, design_type=self.design_type, factors=factors,
            responses=(self.response.get(),), column_map=mapping,
            design_id=self.design_id.get().strip() or None, model_terms=terms)
        return result, metadata, summary

    def _show_preview(self):
        try:
            result, metadata, summary = self._build()
        except (ValueError, TypeError, OverflowError, KeyError) as error:
            self.preview.configure(state='normal')
            self.preview.delete('1.0', 'end')
            self.preview.insert('1.0', f'预览不可用：{error}')
            self.preview.configure(state='disabled')
            self.status.set('预览不可用')
            return False
        lines = [f"设计类型：{summary['design_type']}",
                 f"运行数：{summary['n']}",
                 f"因子数：{summary['factor_count']}",
                 f"矩阵秩：{summary['rank']} / {summary['p']}"]
        for key in ('complete_factorial', 'center_rows', 'replicates',
                    'main_orthogonal', 'main_two_factor_orthogonal', 'has_zeros',
                    'continuous_factors', 'categorical_factors', 'condition'):
            if key in summary:
                lines.append(f'{key}：{summary[key]}')
        if summary.get('terms'):
            lines.append('模型项：' + '; '.join(summary['terms']))
        lines.append('')
        lines.append('前 %d 行：' % min(_PREVIEW_ROWS, len(result)))
        header = ' | '.join(str(column) for column in result.columns)
        lines.append(header)
        for _, row in result.head(_PREVIEW_ROWS).iterrows():
            lines.append(' | '.join('' if value is None else str(value)
                                    for value in row))
        if len(result) > _PREVIEW_ROWS:
            lines.append(f'… 共 {len(result)} 行，仅预览前 {_PREVIEW_ROWS} 行')
        self.preview.configure(state='normal')
        self.preview.delete('1.0', 'end')
        self.preview.insert('1.0', '\n'.join(lines))
        self.preview.configure(state='disabled')
        self.status.set('预览可用')
        return True

    def preview_click(self):
        self._show_preview()

    def create(self):
        try:
            result, metadata, summary = self._build()
        except (ValueError, TypeError, OverflowError, KeyError) as error:
            messagebox.showerror('定义自定义设计', str(error), parent=self.main)
            return False
        self.app.addSheet(f'{self.sheet.get()} 自定义', result, {'doe': metadata})
        self.main.destroy()
        return True


def _numeric(text):
    try:
        float(text)
        return True
    except (TypeError, ValueError):
        return False


def _column(frame, label):
    """下拉框以字符串展示列名；匹配原始标签（含整数列名）。"""
    for column in frame.columns:
        if str(column) == label:
            return column
    raise ValueError(f'列不存在：{label}')
