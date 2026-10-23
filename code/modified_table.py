import csv
import io

import pandas as pd
from tkinter import END, StringVar, Entry, Menu, messagebox
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


class MTable(Table):
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
        new_headers = []
        for x in range(len(cols)):
            if is_void(df.iloc[0, x]):
                new_name = cols[x]
            else:
                new_name = df.iloc[0, x]
            new_headers.append(
                verifyNewColName(new_name, new_headers))
        df.columns = new_headers
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
        if not messagebox.askyesno('清除所选', '确定清除选中的单元格内容？',
                                   parent=self.parentframe):
            return
        self.deleteCells(rows, cols, answer=True)
        self.tableChanged()

    def fillColumn(self):
        """Fill a column with a data range"""
        if not self.requireUnfiltered():
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

        self.drawText(row, col, value, align=self.align)
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
        self.redraw()
        return

    def storeCurrent(self):
        """Store current version of the table before a major change is made"""

        #  print(len(self.prevdf),self.prevdf_end)
        prevdf = (self.dataframe if self.filtered else self.model.df).copy()
        if self.prevdf is None:
            self.prevdf = [prevdf]
            self.prevdf_end = 1
        else:
            del self.prevdf[self.prevdf_end:]
            self.prevdf.append(prevdf)
            self.prevdf_end += 1
            if self.prevdf_end > 5:
                del self.prevdf[0]
                self.prevdf_end -= 1
        print(len(self.prevdf), self.prevdf_end)
        return

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
        self.updateModel(self.model)
        self.redraw()
        print(len(self.prevdf), self.prevdf_end)
        return

    def tableChanged(self):
        """Callback to be used when dataframe changes so that other
            widgets and data can be updated"""

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
