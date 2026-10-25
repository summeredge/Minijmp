import copy
import csv
import io

import pandas as pd
from tkinter import END, BooleanVar, StringVar, Entry, Menu, messagebox
import numpy as np
#  import os
############ pandastable #############
from pandastable_local.core import Table
from pandastable_local.data import TableModel
from pandastable_local.dialogs import MultipleValDialog, applyStyle, filedialog
############## Own Module ###############
#  from modified_header import MColumnHeader as ColumnHeader
#  from modified_header import RowHeader
from df_combine import df_combine
from utilities import grouping_by_labels, verifyNewColName, filter_voids, is_void
from dialog import findRepDialog
from worksheet_formulas import (CalculatorDialog, FormulaError, cycle_message,
                                evaluate, formula_columns, make_formula, signature)


class MTable(Table):
    def _formula_state(self):
        state = self.__dict__.get('_formulas')
        if state is None:
            state = {'items': {}, 'auto': True}
            self._formulas = state
        return state

    @property
    def formulas(self):
        return self._formula_state()['items']

    @property
    def formulas_auto(self):
        return self._formula_state()['auto']

    @formulas_auto.setter
    def formulas_auto(self, value):
        self._formula_state()['auto'] = bool(value)

    def formula_for(self, column):
        return self.formulas.get(column)

    def _formula_columns_selected(self, cols):
        targets = formula_columns(self.formulas)
        return [self.model.df.columns[col] for col in cols
                if 0 <= col < len(self.model.df.columns)
                and self.model.df.columns[col] in targets]

    def _reject_formula_edit(self, columns):
        if not columns:
            return False
        messagebox.showwarning(
            '列公式', '该列由列公式生成。请先解除公式关联，再手工编辑：\n'
            + '、'.join(map(str, columns)), parent=self.parentframe)
        return True

    def _formula_targets_in(self, rows, cols):
        df = self.model.df
        names = {df.columns[col] for col in cols if 0 <= col < len(df.columns)}
        return [name for name in self.formulas if name in names]

    def _formula_auto_var(self):
        var = self.__dict__.get('_formula_auto_checked')
        if var is None:
            var = BooleanVar(self, value=self.formulas_auto)
            self._formula_auto_checked = var
        var.set(self.formulas_auto)
        return var

    def calculator(self):
        CalculatorDialog(self, self.currentcol)

    def assign_column_formula(self):
        CalculatorDialog(self, self.currentcol)

    def edit_column_formula(self):
        name = self.model.df.columns[self.currentcol]
        if name not in self.formulas:
            messagebox.showinfo('列公式', '当前列没有关联公式。', parent=self.parentframe)
            return
        CalculatorDialog(self, self.currentcol)

    def view_column_formula(self):
        name = self.model.df.columns[self.currentcol]
        formula = self.formulas.get(name)
        if formula is None:
            messagebox.showinfo('列公式', '当前列没有关联公式。', parent=self.parentframe)
            return
        from worksheet_formulas import display_expression
        text = f'{name} = {display_expression(formula, self.model.df)}'
        if formula.get('stale'):
            text += '\n待更新'
        if formula.get('error') or formula.get('warning'):
            text += '\n' + (formula.get('error') or formula.get('warning'))
        messagebox.showinfo('列公式', text, parent=self.parentframe)

    def delete_column_formula(self):
        name = self.model.df.columns[self.currentcol]
        if name not in self.formulas:
            messagebox.showinfo('列公式', '当前列没有关联公式。', parent=self.parentframe)
            return
        if not messagebox.askyesno('删除列公式',
                                   f'解除“{name}”的公式关联并保留当前结果？',
                                   parent=self.parentframe):
            return
        self.storeCurrent()
        self.formulas.pop(name)
        self.tableChanged()

    def assign_formula(self, target, expression, link=True):
        """Validate everything before replacing a column; existing data stays on failure."""
        df = self.model.df
        formula = make_formula(target, expression, df)
        if target in formula['sources'].values():
            raise FormulaError(f'公式不能引用目标列“{target}”。')
        candidate = dict(self.formulas) if link else {}
        candidate[target] = formula
        cyclic = cycle_message(candidate)
        if cyclic:
            raise FormulaError(f'存在循环引用：{cyclic}')
        probe = df if target in df.columns else df.assign(**{target: np.nan})
        result = evaluate(candidate, probe)
        problem = (candidate[target].get('error')
                   or candidate[target].get('warning'))
        if candidate[target].get('error'):
            raise FormulaError(problem)
        changed = [name for name in candidate if name in df.columns]
        updated = df.copy(deep=True)
        for name in changed:
            updated[name] = result[name]
        if target in updated.columns:
            updated[target] = result[target]
        else:
            updated.insert(len(updated.columns), target, result[target].to_numpy())
        self.storeCurrent()
        self.model.df = updated
        if link:
            self._formula_state()['items'] = candidate
        else:
            self.formulas.pop(target, None)
        for item in self.formulas.values():
            item['stale'] = False
        self._formula_signature = signature(self.formulas, self.model.df)
        self.redraw()
        self.tableChanged()

    def define_formula(self, target, expression, link=True):
        """One-shot calculator results are plain data and never recalculate."""
        if link:
            self.assign_formula(target, expression, link=True)
            return
        df = self.model.df
        formula = make_formula(target, expression, df)
        if target in formula['sources'].values():
            raise FormulaError(f'公式不能引用目标列“{target}”。')
        probe = df if target in df.columns else df.assign(**{target: np.nan})
        result = evaluate({target: formula}, probe)
        if formula.get('error'):
            raise FormulaError(formula['error'])
        updated = df.copy(deep=True)
        values = result[target].to_numpy()
        if target in updated.columns:
            updated[target] = values
        else:
            updated.insert(len(updated.columns), target, values)
        self.storeCurrent()
        self.model.df = updated
        self.formulas.pop(target, None)
        self.redraw()
        self.tableChanged()
        if formula.get('warning'):
            messagebox.showwarning('公式', formula['warning'], parent=self.parentframe)

    def refresh_formulas(self, force=False):
        """Recalculate in dependency order; manual mode only marks results stale."""
        formulas = self.formulas
        if not formulas or self.filtered or getattr(self, '_formula_busy', False):
            return False
        marks = signature(formulas, self.model.df)
        if not self.formulas_auto and not force:
            previous = getattr(self, '_formula_signature', None)
            stale = previous is not None and marks != previous
            changed = False
            for item in formulas.values():
                if stale and not item['stale']:
                    item['stale'] = True
                    changed = True
            return changed
        self._formula_busy = True
        try:
            result = evaluate(formulas, self.model.df)
        finally:
            self._formula_busy = False
        updated = self.model.df
        for name in formulas:
            if name in updated.columns and not formulas[name]['error']:
                updated[name] = result[name]
        self._formula_signature = marks
        return True

    def formula_column_renamed(self, old, new):
        if old in self.formulas:
            item = self.formulas.pop(old)
            item['target'] = new
            self.formulas[new] = item
        for item in self.formulas.values():
            if old in item['sources'].values():
                item['sources'] = {token: new if name == old else name
                                   for token, name in item['sources'].items()}

    def formula_columns_renamed(self, mapping):
        """Apply positional renames together so swapped names stay attached."""
        targets = {}
        for target, item in self.formulas.items():
            item['target'] = mapping.get(target, target)
            item['sources'] = {token: mapping.get(name, name)
                               for token, name in item['sources'].items()}
            targets[item['target']] = item
        self.formulas.clear()
        self.formulas.update(targets)

    def _drop_missing_formula_targets(self):
        for name, item in self.formulas.items():
            if name not in self.model.df.columns:
                item['error'] = f'目标列“{name}”已不存在。'
                item['stale'] = True

    def _drop_missing_formula_sources(self):
        for item in self.formulas.values():
            for token, name in item['sources'].items():
                if name not in self.model.df.columns and '已不存在' not in item['error']:
                    item['error'] = f'公式引用的列“{name}”已不存在。'
                    item['stale'] = True

    def formula_source_removed(self, name):
        """Keep definitions, but make broken column references explicit."""
        for item in self.formulas.values():
            if name in item['sources'].values():
                item['error'] = f'公式引用的列“{name}”已不存在。'
                item['stale'] = True

    def recalculate_formulas(self):
        if not self.formulas:
            messagebox.showinfo('列公式', '当前工作表没有列公式。', parent=self.parentframe)
            return
        self.refresh_formulas(force=True)
        self.redraw()
        self.tableChanged()

    def set_formula_auto(self):
        self.formulas_auto = not self.formulas_auto
        if self.formulas_auto:
            self.refresh_formulas(force=True)
        self.redraw()
        self.tableChanged()

    def load_formulas(self, items, auto=True):
        if not isinstance(items, dict):
            raise ValueError('无效的列公式定义')
        columns = list(self.model.df.columns)
        clean = {}
        for target, item in items.items():
            if (not isinstance(item, dict)
                    or not isinstance(item.get('expression'), str)
                    or not isinstance(item.get('sources'), dict)):
                raise ValueError('无效的列公式定义')
            target = self._match_column_name(target, columns)
            clean[target] = {'target': target,
                             'expression': item['expression'],
                             'sources': {str(k): self._match_column_name(v, columns)
                                         for k, v in item['sources'].items()},
                             'stale': bool(item.get('stale', False)),
                             'error': '', 'warning': ''}
        self._formula_state().update(items=clean, auto=bool(auto))
        self._formula_signature = signature(clean, self.model.df)
        cyclic = cycle_message(clean)
        if cyclic:
            for item in clean.values():
                item['error'] = f'存在循环引用：{cyclic}'
                item['stale'] = True
        elif auto:
            self.refresh_formulas(force=True)

    def export_formulas(self):
        return {name: {'expression': item['expression'],
                       'sources': dict(item['sources']), 'stale': item.get('stale', False)}
                for name, item in self.formulas.items()}

    @staticmethod
    def _match_column_name(name, columns):
        """Keep numeric labels numeric; strings need no lookup (legacy projects)."""
        if isinstance(name, str):
            return name
        return next((column for column in columns if column == name), name)

    def doExport(self, filename=None):
        """Do a simple export of the cell contents to csv"""

        if filename is None:
            filename = filedialog.asksaveasfilename(parent=self.master,
                                                    defaultextension='.csv',
                                                    initialdir=self.currentdir,
                                                    #  initialdir=os.getcwd(),
                                                    title='Export to CSV',
                                                    filetypes=[("csv", "*.csv"),
                                                               #  ("excel", "*.xls"),
                                                               #  ("html", "*.html"),
                                                               ("All files", "*.*")])
        if filename:
            self.model.save(filename)
        return

    def row1ToHeader(self):
        """
        Put row one contents to header, and have priority
        """
        if not self.requireUnfiltered():
            return
        df = self.model.df
        if len(df) == 0:
            return
        self.storeCurrent()
        cols = list(df)
        old_headers = list(df.columns)
        new_headers = []
        for x in range(len(cols)):
            if is_void(df.iloc[0, x]):
                new_name = cols[x]
            else:
                new_name = df.iloc[0, x]
            new_headers.append(
                verifyNewColName(new_name, new_headers))
        df.columns = new_headers
        # References are keyed by column name; follow each original position.
        self.formula_columns_renamed(dict(zip(old_headers, new_headers)))
        self.tableChanged()
        self.redraw()
        return

    def findText(self, evt=None):
        """Simple text search in whole table"""

        if hasattr(self, 'searchframe') and self.searchframe is not None:
            return
        self.searchframe = findRepDialog(self)
        self.searchframe.grid(
            row=self.queryrow,
            column=0,
            columnspan=3,
            sticky='news')
        return

    def copy(self, rows=None, cols=None):
        """Copy cell contents from clipboard - overwrites table."""

        rows = self.multiplerowlist
        if not rows or self.allrows:
            rows = list(range(len(self.model.df)))
        data = self.model.df.iloc[rows, self.multiplecollist]
        try:
            #  if len(data) == 1 and len(data.columns) == 1:
            data.to_clipboard(index=False, header=False, sep=',')
            #  else:
            #  data.to_clipboard()
        except BaseException:
            messagebox.showwarning("Warning",
                                   "No clipboard software.\nInstall xclip",
                                   parent=self.parentframe)
        return

    def copy_context_selection(self, rows=None, cols=None):
        """Copy selected data as an Excel-compatible, headerless TSV range."""
        df = self.model.df
        rows = list(range(len(df))) if rows is None and self.allrows else rows
        rows = list(rows if rows is not None
                    else self.multiplerowlist or [self.currentrow])
        cols = list(cols if cols is not None
                    else self.multiplecollist or [self.currentcol])
        rows = sorted(set(row for row in rows if isinstance(row, (int, np.integer))
                          and 0 <= row < len(df)))
        cols = sorted(set(col for col in cols if isinstance(col, (int, np.integer))
                          and 0 <= col < len(df.columns)))
        if not rows or not cols:
            return False

        try:
            text = df.iloc[rows, cols].to_csv(
                index=False, header=False, sep='\t', na_rep='', lineterminator='\n')
            self.clipboard_clear()
            self.clipboard_append(text)
        except Exception as error:
            messagebox.showwarning('复制失败', f'无法写入系统剪贴板：{error}',
                                   parent=self.parentframe)
            return False
        return True

    @staticmethod
    def _parse_context_clipboard(text, expected_shape=None):
        def parse(delimiter):
            return list(csv.reader(io.StringIO(text, newline=''), delimiter=delimiter))

        rows = parse('\t') if text else [['']]
        rows = [row or [''] for row in rows]
        # shortcut: a matching selection disambiguates legacy CSV from comma text in one TSV column.
        if '\t' not in text and ',' in text and expected_shape is not None:
            csv_rows = parse(',')
            shape = (len(csv_rows), len(csv_rows[0]) if csv_rows else 0)
            matches = shape[0] == expected_shape[0]
            if (matches and shape[1] == expected_shape[1]
                    and shape != (len(rows), len(rows[0]) if rows else 0)):
                rows = csv_rows
        if not rows or not rows[0] or any(len(row) != len(rows[0]) for row in rows):
            raise ValueError('剪贴板内容不是规则的二维表格。')
        return [[np.nan if value == '' else value for value in row] for row in rows]

    def paste_context_selection(self, axis='cell', rows=None, cols=None):
        """Safely overwrite an existing cell, row, or column range from the clipboard."""
        if not self.editable:
            messagebox.showwarning('无法粘贴', '当前表格为只读状态。', parent=self.parentframe)
            return False
        if self.filtered:
            messagebox.showwarning('无法粘贴', '请先关闭筛选，再粘贴数据。',
                                   parent=self.parentframe)
            return False
        df = self.model.df
        if axis not in ('cell', 'column', 'row'):
            raise ValueError(f'未知粘贴范围：{axis}')
        selected_rows = list(rows if rows is not None
                             else self.multiplerowlist or [self.currentrow])
        selected_cols = list(cols if cols is not None
                             else self.multiplecollist or [self.currentcol])
        if axis == 'column':
            selected_rows = list(range(len(df)))
        elif axis == 'row':
            selected_cols = list(range(len(df.columns)))
        if (any(not isinstance(row, (int, np.integer)) or not 0 <= row < len(df)
                for row in selected_rows)
                or any(not isinstance(col, (int, np.integer)) or not 0 <= col < len(df.columns)
                       for col in selected_cols)):
            messagebox.showwarning('无法粘贴', '粘贴目标行列超出工作表范围。',
                                   parent=self.parentframe)
            return False
        selected_rows = sorted(set(selected_rows))
        selected_cols = sorted(set(selected_cols))
        if not selected_rows or not selected_cols:
            messagebox.showwarning('无法粘贴', '没有有效的粘贴目标。', parent=self.parentframe)
            return False
        if axis == 'cell':
            fixed = len(selected_rows) * len(selected_cols) > 1
            expected = (len(selected_rows), len(selected_cols)) if fixed else None
        elif axis == 'column':
            expected = (len(df), len(selected_cols))
        elif axis == 'row':
            expected = (len(selected_rows), len(df.columns))

        try:
            text = self.clipboard_get().lstrip('\ufeff')
            values = self._parse_context_clipboard(text, expected)
        except Exception as error:
            messagebox.showwarning('无法粘贴', f'剪贴板内容读取失败：{error}',
                                   parent=self.parentframe)
            return False

        height, width = len(values), len(values[0])
        if axis == 'cell':
            if fixed and (height, width) != (len(selected_rows), len(selected_cols)):
                messagebox.showwarning(
                    '无法粘贴', '剪贴板尺寸与所选单元格范围不一致。',
                    parent=self.parentframe)
                return False
            if fixed:
                target_rows, target_cols = selected_rows, selected_cols
            else:
                target_rows = list(range(selected_rows[0], selected_rows[0] + height))
                target_cols = list(range(selected_cols[0], selected_cols[0] + width))
        elif axis == 'column':
            if (height, width) != (len(df), len(selected_cols)):
                messagebox.showwarning(
                    '无法粘贴',
                    f'整列粘贴要求剪贴板为 {len(df)} 行 × {len(selected_cols)} 列。',
                    parent=self.parentframe)
                return False
            target_rows, target_cols = list(range(len(df))), selected_cols
        elif axis == 'row':
            if (height, width) != (len(selected_rows), len(df.columns)):
                messagebox.showwarning(
                    '无法粘贴',
                    f'整行粘贴要求剪贴板为 {len(selected_rows)} 行 × '
                    f'{len(df.columns)} 列。',
                    parent=self.parentframe)
                return False
            target_rows, target_cols = selected_rows, list(range(len(df.columns)))

        if (not target_rows or not target_cols or max(target_rows) >= len(df)
                or max(target_cols) >= len(df.columns)):
            messagebox.showwarning(
                '无法粘贴', '剪贴板尺寸超出工作表范围，未修改数据。',
                parent=self.parentframe)
            return False
        # Only the resolved range is authoritative for cell expansion and whole-row paste.
        if self._reject_formula_edit(self._formula_targets_in(target_rows, target_cols)):
            return False

        updated = df.copy(deep=True)
        try:
            for row_index, target_row in enumerate(target_rows):
                for col_index, target_col in enumerate(target_cols):
                    value = values[row_index][col_index]
                    dtype = df.dtypes.iloc[target_col]
                    if pd.isna(value):
                        value = np.nan
                    elif pd.api.types.is_bool_dtype(dtype):
                        lowered = value.lower()
                        if lowered not in ('true', 'false', '1', '0'):
                            raise ValueError(f'“{value}”不是有效的布尔值。')
                        value = lowered in ('true', '1')
                    elif pd.api.types.is_numeric_dtype(dtype):
                        value = pd.to_numeric(value)
                    elif pd.api.types.is_datetime64_any_dtype(dtype):
                        value = pd.to_datetime(value)
                    updated.iat[target_row, target_col] = value
        except Exception as error:
            messagebox.showwarning(
                '无法粘贴', f'剪贴板数据与单元格类型不兼容：{error}',
                parent=self.parentframe)
            return False

        self.storeCurrent()
        self.model.df = updated
        self.redraw()
        self.tableChanged()
        return True

    def clear_context_selection(self, rows, cols):
        if not self.editable:
            messagebox.showwarning('无法清除', '当前表格为只读状态。', parent=self.parentframe)
            return
        if self.filtered:
            messagebox.showwarning('无法清除', '请先关闭筛选，再清除数据。',
                                   parent=self.parentframe)
            return
        if self._reject_formula_edit(self._formula_targets_in(rows, cols)):
            return
        if not messagebox.askyesno('清除所选', '确定清除选中的单元格内容？',
                                   parent=self.parentframe):
            return
        self.deleteCells(rows, cols, answer=True)
        self.tableChanged()

    def fillColumn(self):
        """Fill a column with a data range"""
        if not self.requireUnfiltered():
            return
        if ('_formulas' in self.__dict__ and
                self._reject_formula_edit(self._formula_columns_selected([self.currentcol]))):
            return

        dists = ['normal', 'gamma', 'uniform', 'random integer', 'logistic']
        d = MultipleValDialog(
            title='New Column',
            initialvalues=(
                0,
                1,
                False,
                False,
                dists,
                1.0,
                1.0),
            labels=(
                'Linear Low',
                'Linear High',
                'Add Random Noise to Linear',
                'Fill Random Numbers',
                'Distribution',
                'Mean',
                'Std'),
            types=(
                'string',
                'string',
                'checkbutton',
                'checkbutton',
                'combobox',
                'float',
                'float'),
            tooltips=(
                'start value if filling with data',
                'end value if filling with data',
                'add random noise upon the linear filling above',
                'create random noise data in the ranges',
                'sampling distribution for noise',
                'mean/scale of distribution',
                'std dev./shape of distribution'),
            parent=self.parentframe)
        if d.result is None:
            return
        else:
            low = d.results[0]
            high = d.results[1]
            add_random = d.results[2]
            random = d.results[3]
            dist = d.results[4]
            param1 = float(d.results[5])
            param2 = float(d.results[6])

        df = self.model.df
        self.storeCurrent()
        if low != '' and high != '':
            try:
                low = float(low)
                high = float(high)
            except BaseException:
                #  logging.error("Exception occurred", exc_info=True)
                return
        #  if random:
        if dist == 'normal':
            data = np.random.normal(param1, param2, len(df))
        elif dist == 'gamma':
            data = np.random.gamma(param1, param2, len(df))
        elif dist == 'uniform':
            data = np.random.uniform(low, high, len(df))
        elif dist == 'random integer':
            data = np.random.randint(low, high, len(df))
        elif dist == 'logistic':
            data = np.random.logistic(low, high, len(df))
        if not random:
            linear = np.linspace(low, high, len(df))
            if add_random:
                data += linear
            else:
                data = linear
        col = df.columns[self.currentcol]
        df[col] = data
        self.redraw()
        self.tableChanged()
        return

    def sortColumnIndex(self):
        """Sort the column header by the current rows values"""
        return super().sortColumnIndex()

    def update_rowcolors(self):
        """Update row colors if present so that it syncs with current dataframe."""
        #
        #  df = self.model.df
        #  rc = self.rowcolors
        #  if len(df) == len(self.rowcolors):
        #      rc.set_index(df.index, inplace=True)
        #  elif len(df) > len(rc):
        #      idx = df.index.difference(rc.index)
        #      # self.rowcolors = rc.append(pd.DataFrame(index=idx))
        #      self.rowcolors = pd.concat([rc, pd.DataFrame(index=idx)])
        #  else:
        #      idx = rc.index.difference(df.index)
        #      rc.drop(idx, inplace=True)
        #  # check columns
        #  cols = list(rc.columns.difference(df.columns))
        #  print(cols)
        #  if len(cols) > 0:
        #      try:
        #          rc.drop(cols, inplace=True)
        #      except BaseException:
        #          pass
        #  cols = list(df.columns.difference(rc.columns))
        #  if len(cols) > 0:
        #      for col in cols:
        #          rc[col] = np.nan
        return

    def setAlignment(self, colnames=None):
        """Set column alignments, overrides global value"""

        cols = self.multiplecollist
        df = self.model.df
        cf = self.columnformats
        cfa = cf['alignment']
        vals = ['Left', 'Right', 'Center']
        conv = {"Left": 'w', "Right": 'e', "Center": 'center'}
        d = MultipleValDialog(title='set alignment',
                              initialvalues=[vals],
                              labels=['Align:'],
                              types=['combobox'],
                              parent=self.parentframe)
        if d.result is None:
            return
        aln = conv[d.results[0]]
        #  print(aln)
        for col in cols:
            colname = df.columns[col]
            cfa[colname] = aln
        self.redraw()
        return

    def handle_right_click(self, event):
        if hasattr(self, 'rightmenu') and self.rightmenu is not None:
            self.rightmenu.destroy()
            self.rightmenu = None
        if not self.enable_menus:
            return

        row = self.get_row_clicked(event)
        col = self.get_col_clicked(event)
        if row is None or col is None or not (0 <= row < self.rows and 0 <= col < self.cols):
            return
        if not ((row in self.multiplerowlist or self.allrows)
                and col in self.multiplecollist):
            self.clearSelected()
            self.rowheader.clearSelected()
            self.allrows = False
            self.setSelectedRow(row)
            self.setSelectedCol(col)
            self.drawSelectedRect(row, col)
            self.drawSelectedRow()

        rows = list(range(self.rows)) if self.allrows else list(self.multiplerowlist or [self.currentrow])
        cols = list(self.multiplecollist or [self.currentcol])
        mutable = self.editable and not self.filtered
        can_undo = mutable and self.prevdf is not None and self.prevdf_end > 0
        menu = Menu(self, tearoff=0)
        menu.add_command(label='复制所选', command=lambda: self.copy_context_selection(rows, cols))
        menu.add_command(label='粘贴', command=lambda: self.paste_context_selection('cell', rows, cols),
                         state='normal' if mutable else 'disabled')
        menu.add_command(label='撤销', command=self.undo,
                         state='normal' if can_undo else 'disabled')
        menu.add_command(label='清除所选', command=lambda: self.clear_context_selection(rows, cols),
                         state='normal' if mutable else 'disabled')
        menu.add_separator()
        formulas = menu.add_cascade(label='公式')
        formula_menu = Menu(menu, tearoff=0)
        for label, command in (
                ('向列分配公式', self.assign_column_formula),
                ('编辑列公式', self.edit_column_formula),
                ('查看列公式', self.view_column_formula),
                ('删除列公式', self.delete_column_formula)):
            formula_menu.add_command(label=label, command=command)
        formula_menu.add_separator()
        formula_menu.add_checkbutton(label='自动计算所有公式', command=self.set_formula_auto,
                                     variable=self._formula_auto_var())
        formula_menu.add_command(label='立即计算所有公式', command=self.recalculate_formulas)
        menu.entryconfigure('公式', menu=formula_menu)
        self.formula_menu = formula_menu
        applyStyle(menu)
        menu.post(event.x_root, event.y_root)
        self.rightmenu = menu
        return

    def drawCellEntry(self, row, col, text=None):
        """When the user single/double clicks on a text/number cell,
          bring up entry window and allow edits."""

        def select_all(event):
            event.widget.select_range(0, END)
            return 'break'

        if not self.editable or not (0 <= row < self.rows and 0 <= col < self.cols):
            return
        h = self.rowheight
        #  model = self.model
        text = self.model.getValueAt(row, col)
        if pd.isnull(text):
            text = ''
        x1, y1, x2, y2 = self.getCellCoords(row, col)
        w = x2 - x1
        self.cellentryvar = txtvar = StringVar()
        txtvar.set(text)

        self.cellentry = Entry(self.parentframe, width=20,
                               textvariable=txtvar,
                               takefocus=1,
                               font=self.thefont)
        self.cellentry.icursor(END)
        self.cellentry.bind(
            '<Return>',
            lambda x: self.handleCellEntry(
                row,
                col))
        self.cellentry.bind("<FocusIn>", select_all)
        self.cellentry.bind("<Tab>",
                            lambda x: self.handleCellEntry(
                                row,
                                col, nxt_col=True))
        self.cellentry.focus_set()
        self.entrywin = self.create_window(x1, y1,
                                           width=w, height=h,
                                           window=self.cellentry, anchor='nw',
                                           tag='entry')
        #  if col == 0:
        #  self.xview_moveto(0)
        #  print(col, row)
        return

    def handleCellEntry(self, row, col, nxt_col=False):
        """Callback for cell entry"""

        if self._reject_formula_edit(self._formula_columns_selected([col])):
            self.delete('entry')
            if hasattr(self, 'cellentry'):
                self.cellentry.destroy()
            return
        value = self.cellentryvar.get()
        self.storeCurrent()
        if self.filtered == 1:
            df = self.dataframe
        else:
            df = None
        try:
            self.model.setValueAt(value, row, col, df=df)
        except ValueError as exc:
            messagebox.showerror('Could not edit data', str(exc), parent=self.parentframe)
            return

        self.refresh_formulas()
        self.redraw()
        self.delete('entry')
        self.gotonextCell(nxt_col=nxt_col)
        return

    def gotonextCell(self, nxt_col=False):
        """Move highlighted cell to next cell in row after enter cell entry"""

        if hasattr(self, 'cellentry'):
            self.cellentry.destroy()
        if nxt_col:
            if self.currentcol + 1 >= self.cols:
                return
            self.setSelectedCol(self.currentcol + 1)
        else:
            if self.currentrow + 1 >= self.rows:
                return
            self.setSelectedRow(self.currentrow + 1)
        #  self.drawSelectedRect(self.currentrow, self.currentcol)
        #  self.xview_moveto(0)
        self.drawCellEntry(self.currentrow, self.currentcol)
        print(self.currentcol, self.currentrow)
        #  if self.currentcol == 0:
        #  self.xview_moveto(0.5)
        #  self.xview_scroll(-1, "unit")
        return

    def handle_double_click(self, event):
        """Do double click stuff. Selected row/cols will already have
           been set with single click binding"""

        row = self.get_row_clicked(event)
        col = self.get_col_clicked(event)
        print(row, col, self.currentrow, self.currentcol)
        self.drawCellEntry(self.currentrow, self.currentcol)
        #  self.xview_scroll(-1, "unit")
        return

    def paste(self, event=None):
        """Paste a new table from the clipboard"""
        if not self.requireUnfiltered():
            return
        if self._reject_formula_edit(self._formula_targets_in(
                self.multiplerowlist, self.multiplecollist)
                if self.multiplerowlist and self.multiplecollist else []):
            return

        self.storeCurrent()
        try:
            df = pd.read_clipboard(sep=',', header=None)
        except Exception as e:
            messagebox.showwarning('Could not paste data', str(e), parent=self.parentframe)
            return
        if len(df) == 0:
            return

        try:
            ins_y = min(self.multiplerowlist)
            ins_x = min(self.multiplecollist)
        except BaseException:
            ins_y = ins_x = 0
        model = TableModel(df_combine(
            self.model.df, df,
            ins_y=ins_y, ins_x=ins_x))
        self.updateModel(model)
        self.redraw()
        self.updateIndex()
        return

    def paste_header(self, event=None):
        """Paste a new table from the clipboard"""
        if not self.requireUnfiltered():
            return
        if self._reject_formula_edit(self._formula_targets_in(
                self.multiplerowlist, self.multiplecollist)):
            return

        self.storeCurrent()
        try:
            df = pd.read_clipboard(sep=',')
        except Exception as e:
            messagebox.showwarning('Could not paste data', str(e), parent=self.parentframe)
            return
        if len(df) == 0:
            return

        try:
            ins_x = min(self.multiplecollist)
        except BaseException:
            ins_x = 0
        new_df = df_combine(
            self.model.df, df,
            ins_y=0,  # min(self.multiplerowlist),
            ins_x=ins_x)
        col_names = new_df.columns.tolist()
        df2_cols = df.columns.tolist()
        for x in range(len(df2_cols)):
            xx = ins_x + x
            col_names[xx] = verifyNewColName(df2_cols[x], col_names)
        new_df.columns = col_names
        model = TableModel(new_df)
        self.updateModel(model)
        self.redraw()
        self.updateIndex(ask=False)
        return

    def splitColumn(self, evt=None):
        """
        Split data column with a categorical column into several
        individual columns.
        """
        if not self.requireUnfiltered():
            return

        df = self.model.df
        cols = list(df)

        d = MultipleValDialog(
            title='Split Column',
            initialvalues=(
                cols,
                cols),
            labels=(
                'Data Column',
                'Grouping ID Column'),
            types=(
                'combobox',
                'combobox'),
            tooltips=(
                'The data to be splitted into seperated columns',
                'Categorical data to group the data'),
            parent=self.parentframe)
        if d.result is None:
            return
        self.storeCurrent()
        data = df[d.results[0]]
        grpList = df[d.results[1]]
        [data, grpList] = filter_voids([data, grpList])
        keys = list(set(grpList))

        resList = grouping_by_labels(data, grpList, keys=keys)

        def insertCol(col1, col2):
            """
            Move col1 next to col2, useful for placing a new column
            made from the first one next to it so user can see it easily
            """
            ind1 = self.model.df.columns.get_loc(col1)
            ind2 = self.model.df.columns.get_loc(col2)
            self.model.moveColumn(ind1, ind2 + 1)

        for i in range(len(resList)):
            key = verifyNewColName(str(keys[i]), cols)
            df[key] = resList[i] + [np.nan] * \
                (df.shape[0] - len(resList[i]))
        self.redraw()
        return

    def stackColumn(self, evt=None):
        """
        Stack selected columns into two colums with data and grouping keys
        keys are the column ids
        """
        if not self.requireUnfiltered():
            return

        self.storeCurrent()
        df = self.model.df
        selected_cols = list(df.columns[self.multiplecollist])
        cols = list(df)

        self.addColumn(newname=verifyNewColName('Stk Keys', cols))
        self.addColumn(newname=verifyNewColName('Stk Data', cols))

        resKeys, resData = [], []
        for col in selected_cols:
            data = list(df[col])
            resKeys = resKeys + [col] * len(data)
            resData = resData + data
        [resKeys, resData] = filter_voids([resKeys, resData])
        ins_y = 0
        ins_x = df.shape[1] - 2
        model = TableModel(df_combine(
            self.model.df,
            pd.DataFrame({'1': resKeys, '2': resData}),
            ins_y=ins_y, ins_x=ins_x))
        self.updateModel(model)

        self.redraw()
        self.updateIndex(ask=False)
        return

    def addColumn(self, newname=None):
        """Add a new column"""
        if not self.requireUnfiltered():
            return

        if newname is None:
            coltypes = ['object', 'float64']
            d = MultipleValDialog(title='New Column',
                                  initialvalues=(coltypes, ''),
                                  labels=('Column Type', 'Name'),
                                  types=('combobox', 'string'),
                                  parent=self.parentframe)
            if d.result is None:
                return
            else:
                dtype = d.results[0]
                newname = d.results[1]
        else:
            dtype = 'object'

        #  df = self.model.df
        if newname is not None:
            if newname in self.model.df.columns:
                messagebox.showwarning("Name exists",
                                       "Name already exists!",
                                       parent=self.parentframe)
            else:
                self.storeCurrent()
                self.model.addColumn(newname, dtype)
                self.parentframe.configure(width=self.width)
                self.update_rowcolors()
                self.redraw()
                self.tableChanged()
        return

    def updateIndex(self, ask=True, drop=True):
        """Reset index and redraw row header"""
        if not self.requireUnfiltered():
            return

        #  self.storeCurrent()
        #  df = self.model.df
        #  if (df.index.name is None or df.index.names[0] is None) and ask == True:
        #      drop = messagebox.askyesno("Reset Index", "Drop the index?",
        #                                parent=self.parentframe)
        self.model.df.reset_index(drop=drop, inplace=True)
        self.update_rowcolors()
        # self.set_rowcolors_index()
        self.redraw()
        # self.drawSelectedCol()
        #  if hasattr(self, 'pf'):
        #      self.pf.updateData()
        self.update_rowcolors()
        self.tableChanged()
        return

    def deleteRow(self, ask=False):
        """Delete a selected row"""
        if not self.requireUnfiltered():
            return

        n = True
        if ask:
            n = messagebox.askyesno("Delete",
                                    "Delete selected rows?",
                                    parent=self.parentframe)

        if len(self.multiplerowlist) > 1:
            if n:
                self.storeCurrent()
                rows = self.multiplerowlist
                self.model.deleteRows(rows)
                self.setSelectedRow(0)
                self.clearSelected()
                self.update_rowcolors()
                self.redraw()
        else:
            if n:
                self.storeCurrent()
                row = self.getSelectedRow()
                self.model.deleteRows([row])
                self.setSelectedRow(row - 1)
                self.clearSelected()
                self.update_rowcolors()
                self.redraw()
        self.updateIndex()
        return

    def deleteCells(self, rows, cols, answer=None):
        """Association must be removed before a formula column is cleared."""
        if self._reject_formula_edit(self._formula_targets_in(rows, cols)):
            return
        return super().deleteCells(rows, cols, answer)

    def colorRows(self):
        return

    def colorColumns(self):
        return

    def sortAll(self, evt=None):
        """
        Sort the entire table by 1-3 cols.
        """
        if not self.requireUnfiltered():
            return

        df = self.model.df
        cols = [""] + list(df)

        d = MultipleValDialog(
            title='Sort All Columns',
            initialvalues=(
                cols,
                True,
                cols, True,
                cols,
                True),
            labels=(
                'Sort By',
                'Ascending',
                'Then By',
                'Ascending',
                'Then By',
                'Ascending'),
            types=(
                'combobox',
                'checkbutton',
                'combobox',
                'checkbutton',
                'combobox',
                'checkbutton'),
            tooltips=(
                '',
                '',
                '', '', '',
                ''),
            parent=self.parentframe)
        if d.result is None:
            return
        self.storeCurrent()
        col_list, a_list = [], []
        for i in [0, 2, 4]:
            if d.results[i] != "":
                col_list.append(d.results[i])
                a_list.append(1 if d.results[i + 1] else 0)
            else:
                break
        if len(col_list) == 0:
            return

        try:
            #  print(col_list, d.results[3])
            df.sort_values(by=col_list, inplace=True, ascending=a_list)
        except BaseException:
            print('could not sort')

        self.updateIndex(ask=False)
        self.redraw()
        return

    def sortSelected(self, evt=None):
        """
        Sort the entire table by 1-3 cols.
        """
        if not self.requireUnfiltered():
            return
        if self._reject_formula_edit(self._formula_targets_in(
                self.multiplerowlist, self.multiplecollist)):
            return

        df = self.model.df
        columnIndex = self.multiplecollist
        if isinstance(columnIndex, int):
            columnIndex = [columnIndex]

        colnames = list(df.columns[columnIndex])
        cols = [""] + colnames

        d = MultipleValDialog(
            title='Sort Selected Columns',
            initialvalues=(
                cols,
                True,
                cols, True,
                cols,
                True),
            labels=(
                'Sort By',
                'Ascending',
                'Then By',
                'Ascending',
                'Then By',
                'Ascending'),
            types=(
                'combobox',
                'checkbutton',
                'combobox',
                'checkbutton',
                'combobox',
                'checkbutton'),
            tooltips=(
                '',
                '',
                '', '', '',
                ''),
            parent=self.parentframe)
        if d.result is None:
            return
        self.storeCurrent()
        col_list, a_list = [], []
        for i in [0, 2, 4]:
            if d.results[i] != "":
                col_list.append(d.results[i])
                a_list.append(1 if d.results[i + 1] else 0)
            else:
                break
        if len(col_list) == 0:
            return

        dfSub = df[colnames].copy()
        dfSub.sort_values(by=col_list, inplace=True, ascending=a_list)
        dfSub.reset_index(drop=True, inplace=True)
        print(dfSub)
        #  for col in list(dfSub):
        #      df[col] = dfSub[col]
        df[colnames] = dfSub.set_axis(df.index)
        self.tableChanged()
        self.redraw()
        return

    def storeCurrent(self):
        """Store current version of the table before a major change is made"""

        #  print(len(self.prevdf),self.prevdf_end)
        prevdf = (self.dataframe if self.filtered else self.model.df).copy()
        snapshot = self._formula_snapshot() if hasattr(self, '_formula_state') else None
        if self.prevdf is None:
            self.prevdf = [prevdf]
            if snapshot is not None:
                self._formula_history = [snapshot]
            self.prevdf_end = 1
        else:
            del self.prevdf[self.prevdf_end:]
            self.prevdf.append(prevdf)
            if snapshot is not None:
                history = self.__dict__.setdefault('_formula_history', [])
                del history[self.prevdf_end:]
                history.append(snapshot)
            self.prevdf_end += 1
            if self.prevdf_end > 5:
                del self.prevdf[0]
                if snapshot is not None:
                    del history[0]
                self.prevdf_end -= 1
        print(len(self.prevdf), self.prevdf_end)
        return

    def _formula_snapshot(self):
        return {'items': copy.deepcopy(self.formulas), 'auto': self.formulas_auto}

    def _restore_formula_snapshot(self, index):
        history = getattr(self, '_formula_history', None)
        if history is None or not 0 <= index < len(history):
            return False
        state = history[index]
        self._formula_state().update(items=copy.deepcopy(state['items']),
                                     auto=state['auto'])
        if self.formulas_auto:
            self.refresh_formulas(force=True)
        else:
            self._formula_signature = signature(self.formulas, self.model.df)
        return True

    def undo(self, event=None):
        """Undo last major table change"""

        if self.prevdf is None:
            return
        if self.prevdf_end == 0:
            return
        if self.prevdf_end == len(self.prevdf):
            self.storeCurrent()
            self.prevdf_end -= 1

        self.prevdf_end -= 1
        prevdf = self.prevdf[self.prevdf_end]
        self.model.df = prevdf.copy()
        if (hasattr(self, 'refresh_formulas')
                and (not getattr(self, '_formula_history', None)
                     or not self._restore_formula_snapshot(self.prevdf_end))):
            self.refresh_formulas(force=True)
        self.updateModel(self.model)
        self.redraw()
        print(len(self.prevdf), self.prevdf_end)
        return

    def redo(self, event=None):
        """Redo tolast major table change"""

        if self.prevdf is None:
            return
        if self.prevdf_end + 2 > len(self.prevdf):
            return
        self.prevdf_end += 1
        prevdf = self.prevdf[self.prevdf_end]
        self.model.df = prevdf.copy()
        if (hasattr(self, 'refresh_formulas')
                and (not getattr(self, '_formula_history', None)
                     or not self._restore_formula_snapshot(self.prevdf_end))):
            self.refresh_formulas(force=True)
        self.updateModel(self.model)
        self.redraw()
        print(len(self.prevdf), self.prevdf_end)
        return

    def tableChanged(self):
        """Callback to be used when dataframe changes so that other
            widgets and data can be updated"""

        self._drop_missing_formula_targets()
        changed = self.refresh_formulas()
        self._drop_missing_formula_sources()
        if changed:
            self.redraw()
        self.updateFunctions()
        self.updateWidgets()
        try:
            if hasattr(self, 'pf'):
                self.pf.updateData()
        except BaseException:
            pass
        return

    def adjustColumnWidths(self, limit=30):
        return

    def clearDataUp(self, evt=None):
        """Delete cells and move cells below up"""
        if not self.requireUnfiltered():
            return
        formulas = getattr(self, '_formulas', None)
        if formulas and formulas['items'] and self._reject_formula_edit(
                self._formula_targets_in(self.multiplerowlist, self.multiplecollist)):
            return

        if self.allrows:
            self.deleteColumn()
            return
        if not self.editable:
            return
        answer = messagebox.askyesno(
            "Clear Confirm",
            "Clear this data and move the cells below up?",
            parent=self.parentframe)
        if not answer:
            return

        rows = self.multiplerowlist
        cols = self.multiplecollist
        df = self.model.df
        self.storeCurrent()
        keep = np.ones(len(df), dtype=bool)
        keep[rows] = False
        for col in cols:
            values = df.iloc[keep, col].reset_index(drop=True)
            df.isetitem(col, values.reindex(range(len(df))).array)

        self.redraw()
        return
