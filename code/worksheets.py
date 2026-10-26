"""MTable worksheets and transactional Minijmp project files."""
import gzip
import os
import pickle
import posixpath
import tempfile
import zipfile
from decimal import Decimal, InvalidOperation
from numbers import Number
from pathlib import Path
from tkinter import Menu, TclError, ttk, filedialog, messagebox, simpledialog
from xml.etree import ElementTree as ET

import pandas as pd

from modified_table import MTable
from pandastable_local import config


def _restore_excel_precision(filename, frames):
    main_ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    relation_id = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
    with zipfile.ZipFile(filename) as workbook:
        relationships = ET.fromstring(workbook.read("xl/_rels/workbook.xml.rels"))
        targets = {item.get("Id"): item.get("Target") for item in relationships}
        sheets = ET.fromstring(workbook.read("xl/workbook.xml"))
        for sheet in sheets.iter(main_ns + "sheet"):
            frame = frames.get(sheet.get("name"))
            if frame is None:
                continue
            target = targets[sheet.get(relation_id)]
            path = (target.lstrip("/") if target.startswith("/") else
                    posixpath.normpath(posixpath.join("xl", target)))
            root = ET.fromstring(workbook.read(path))
            replacements = {}
            for cell in root.iter(main_ns + "c"):
                if cell.get("t") not in (None, "n"):
                    continue
                value = cell.find(main_ns + "v")
                reference = cell.get("r", "")
                split = next((i for i, char in enumerate(reference) if not char.isalpha()), 0)
                if value is None or not value.text or split == 0:
                    continue
                column = 0
                for char in reference[:split].upper():
                    column = column * 26 + ord(char) - ord("A") + 1
                row, column = int(reference[split:]) - 2, column - 1
                if row < 0 or row >= len(frame) or column < 0 or column >= frame.shape[1]:
                    continue
                current = frame.iat[row, column]
                if pd.isna(current) or not isinstance(current, Number):
                    continue
                try:
                    if Decimal(value.text) == Decimal(str(current)):
                        continue
                except InvalidOperation:
                    continue
                replacements.setdefault(column, {})[row] = value.text
            for column, cells in replacements.items():
                values = frame.iloc[:, column].astype(object)
                for row, value in cells.items():
                    values.iloc[row] = value
                frame.isetitem(column, values)


class Worksheets:
    @property
    def table(self):
        return self.getCurrentTable() if getattr(self, 'sheets', None) else self._table

    @table.setter
    def table(self, table):
        self._table = table

    def sheet_app(self, table):
        from sheet_context import SheetApp
        return SheetApp(self, table)

    def init_worksheets(self):
        self.nb = ttk.Notebook(self.main)
        self.nb.pack(fill='both', expand=True)
        self.nb.enable_traversal()
        self.sheets = {}
        self.sheetframes = {}
        self.filename = None
        self.addSheet('工作表1')
        self.nb.bind('<<NotebookTabChanged>>', self._sheet_changed)
        self._sheet_context_menu = Menu(self.nb, tearoff=0)
        self.nb.bind('<Button-3>', self._show_sheet_context_menu)
        self._saved_state = self._state()

    @staticmethod
    def _valid_name(name):
        return (isinstance(name, str) and bool(name.strip()) and len(name) <= 80
                and name == name.strip() and name != 'meta'
                and not any(ord(c) < 32 or c in '[]:*?/\\' for c in name))

    def _unique_name(self, name, names=None):
        names = self.sheets if names is None else names
        name = ''.join(c for c in str(name) if ord(c) >= 32 and c not in '[]:*?/\\').strip()[:70]
        if not name or name == 'meta':
            name = '工作表'
        candidate, i = name, 2
        while candidate in names:
            candidate = f'{name} ({i})'
            i += 1
        return candidate

    def _make_sheet(self, df=None, meta=None):
        frame = ttk.Frame(self.nb)
        try:
            table = MTable(frame, dataframe=df, showtoolbar=False,
                           showstatusbar=True, enable_menus=True)
            config.apply_options({'colheadercolor': 'green', 'floatprecision': 3,
                                  'rowheaderfgcolor': 'black', 'rowheaderbgcolor': 'gray'}, table)
            table.tOut = None
            table.show()
            table.load = self.load_file
            table.save = self.save_file
            table.importCSV = lambda filename=None, dialog=False, **kw: self.import_csv(
                advanced=dialog, filename=filename, **kw)
            table.loadExcel = self.load_excel
            self.loadMeta(table, meta)
        except Exception:
            frame.destroy()
            raise
        return frame, table

    def _sheet_changed(self, event=None):
        if self.sheets:
            previous = getattr(self, '_table', None)
            if previous is not None and previous.winfo_exists():
                self._finish_edit(previous)
            self.table = self.getCurrentTable()
            self.table.focus_set()
            self.update_title()

    def _show_sheet_context_menu(self, event):
        try:
            index = self.nb.index(f'@{event.x},{event.y}')
        except TclError:
            return
        tabs = self.nb.tabs()
        if not 0 <= index < len(tabs):
            return
        frame = next((f for f in self.sheetframes.values() if str(f) == tabs[index]), None)
        if frame is None:
            return
        menu = self._sheet_context_menu
        menu.delete(0, 'end')
        for label, action in (('新增工作表', self.addSheet), ('复制工作表', self.copySheet),
                              ('重命名工作表', self.renameSheet), ('删除工作表', self.deleteSheet),
                              ('导出当前工作表', self.export_sheet)):
            menu.add_command(label=label, command=lambda action=action:
                             self._run_sheet_context_action(frame, action))
        menu.tk_popup(event.x_root, event.y_root)
        return 'break'

    def _run_sheet_context_action(self, frame, action):
        if frame not in self.sheetframes.values():
            return
        if self.nb.select() != str(frame):
            self.nb.select(frame)
            self._sheet_changed()
        action()

    def getCurrentSheet(self):
        selected = self.nb.select()
        return next((n for n, f in self.sheetframes.items() if str(f) == selected),
                    next(iter(self.sheets), None))

    def getCurrentTable(self):
        return self.sheets[self.getCurrentSheet()]

    def addSheet(self, name=None, dataframe=None, meta=None):
        if self.sheets:
            self._finish_edit()
        name = self._unique_name(name or '工作表')
        frame, table = self._make_sheet(dataframe, meta)
        self.sheets[name], self.sheetframes[name] = table, frame
        self.nb.add(frame, text=name)
        self.nb.select(frame)
        self.table = table
        return table

    def copySheet(self):
        self._finish_edit()
        table = self.getCurrentTable()
        return self.addSheet(self.getCurrentSheet() + ' 副本',
                             self._full_frame(table).copy(deep=True), self.saveMeta(table))

    def renameSheet(self, name=None):
        old = self.getCurrentSheet()
        if name is None:
            name = simpledialog.askstring('重命名工作表', '工作表名称：',
                                          initialvalue=old, parent=self.main)
        if name is None or name == old:
            return False
        if not self._valid_name(name) or name in self.sheets:
            messagebox.showerror('名称无效', '名称须唯一，长度为 1–80，不能包含 []:*?/\\ 或首尾空格。', parent=self.main)
            return False
        self.sheets = {name if n == old else n: t for n, t in self.sheets.items()}
        self.sheetframes = {name if n == old else n: f for n, f in self.sheetframes.items()}
        self.nb.tab(self.sheetframes[name], text=name)
        self.update_title()
        return True

    def deleteSheet(self):
        name = self.getCurrentSheet()
        if not messagebox.askyesno('删除工作表', f'删除“{name}”？此操作无法撤销。', parent=self.main):
            return False
        # Create the replacement before discarding the last sheet.
        if len(self.sheets) == 1:
            self.addSheet('工作表')
        table, frame = self.sheets.pop(name), self.sheetframes.pop(name)
        self._dispose_sheet(table, frame)
        self._sheet_changed()
        return True

    def _dispose_sheet(self, table, frame):
        child_viewer = getattr(getattr(table, 'child', None), 'pf', None)
        if child_viewer is not None and child_viewer is not getattr(table, 'pf', None):
            child_viewer.close()
        for attr in ('tOut', 'pf'):
            viewer = getattr(table, attr, None)
            if viewer is not None:
                viewer.close()
        self.nb.forget(frame)
        frame.destroy()

    @staticmethod
    def _full_frame(table):
        return table.dataframe if table.filtered else table.model.df

    def saveMeta(self, table):
        return {'minijmp': 1, 'columnwidths': dict(table.columnwidths),
                'formulas': table.export_formulas(), 'formula_auto': table.formulas_auto,
                'options': {k: getattr(table, k) for k in
                            ('floatprecision', 'cellwidth', 'rowheight', 'showindex',
                             'cellbackgr', 'textcolor', 'grid_color', 'thefont')}}

    def loadMeta(self, table, meta):
        if not isinstance(meta, dict):
            return
        if 'formulas' in meta and not isinstance(meta['formulas'], dict):
            raise ValueError('无效的列公式定义')
        if 'formula_auto' in meta and meta['formula_auto'] not in (True, False):
            raise ValueError('无效的列公式计算设置')
        if 'formulas' in meta or 'formula_auto' in meta:
            table.load_formulas(meta.get('formulas', {}), meta.get('formula_auto', True))
        if meta.get('minijmp') != 1:
            return
        widths = meta.get('columnwidths', {})
        if not isinstance(widths, dict) or not all(isinstance(v, (int, float)) and 1 <= v <= 10000 for v in widths.values()):
            raise ValueError('无效的列宽设置')
        options = meta.get('options', {})
        allowed = self.saveMeta(table)['options']
        if not isinstance(options, dict) or any(k not in allowed for k in options):
            raise ValueError('无效的显示设置')
        for key in ('floatprecision', 'cellwidth', 'rowheight'):
            if key in options and (not isinstance(options[key], int)
                                   or options[key] < (0 if key == 'floatprecision' else 1)):
                raise ValueError('无效的显示尺寸或精度')
        if 'showindex' in options and options['showindex'] not in (True, False):
            raise ValueError('无效的索引显示设置')
        for key in ('cellbackgr', 'textcolor', 'grid_color'):
            if key in options:
                self.main.winfo_rgb(options[key])
        config.apply_options(options, table)
        table.columnwidths = dict(widths)
        table.redraw()

    def _payload(self):
        data = {n: {'table': self._full_frame(t), 'meta': self.saveMeta(t)}
                for n, t in self.sheets.items()}
        data['meta'] = {'active': self.getCurrentSheet(), 'minijmp': 1}
        return data

    def _state(self):
        data = self._payload()
        # Selecting a tab alone is not a data change.
        data.pop('meta')
        return pickle.dumps(data, protocol=pickle.HIGHEST_PROTOCOL)

    def _confirm_discard(self):
        self._finish_edit()
        if self._state() == self._saved_state:
            return True
        answer = messagebox.askyesnocancel('未保存的项目', '保存当前项目的更改？', parent=self.main)
        return self.save_file() if answer is True else answer is False

    def _finish_edit(self, table=None):
        if table is None:
            for item in self.sheets.values():
                self._finish_edit(item)
            return
        entry = getattr(table, 'cellentry', None)
        if entry is not None and entry.winfo_exists():
            table.handleCellEntry(table.currentrow, table.currentcol)
            entry = getattr(table, 'cellentry', None)
            if entry is not None and entry.winfo_exists():
                entry.destroy()

    def update_title(self):
        self.pickle_fname = None
        title = os.path.basename(self.filename) if self.filename else '未命名项目'
        self.main.title(f'{title} — {self.getCurrentSheet()} - Minijmp')

    def new_file(self):
        if self._confirm_discard():
            self._replace({'工作表1': {'table': None}}, None)
            return True
        return False

    def _replace(self, data, filename):
        active = data.get('meta', {}).get('active')
        if active is not None and (not isinstance(active, str) or active not in data or active == 'meta'):
            raise ValueError('无效的活动工作表')
        staged = {}
        try:
            for name, record in data.items():
                if name != 'meta':
                    staged[name] = self._make_sheet(record['table'], record.get('meta'))
        except Exception:
            for frame, table in staged.values():
                frame.destroy()
            raise
        old = [(self.sheets[n], self.sheetframes[n]) for n in self.sheets]
        self.sheets, self.sheetframes = {}, {}
        for name, (frame, table) in staged.items():
            self.sheets[name], self.sheetframes[name] = table, frame
            self.nb.add(frame, text=name)
        self.nb.select(self.sheetframes.get(active, next(iter(self.sheetframes.values()))))
        self.table = self.getCurrentTable()
        for table, frame in old:
            self._dispose_sheet(table, frame)
        self.updatePlotsMenu()
        self.filename = filename
        if filename:
            self.defaultsavedir = os.path.dirname(os.path.abspath(filename))
        self._saved_state = self._state()
        self.update_title()

    def load_file(self, filename=None):
        filename = filename or filedialog.askopenfilename(parent=self.main,
                    initialdir=self.defaultsavedir,
                    filetypes=[('项目 / 单表', '*.dexpl *.pickle')])
        if not filename:
            return False
        if not messagebox.askyesno('可信文件', '工程文件使用 pickle，仅打开您信任的文件。继续打开？', parent=self.main):
            return False
        try:
            suffix = Path(filename).suffix.lower()
            if suffix == '.dexpl':
                with gzip.open(filename, 'rb') as stream:
                    data = pickle.load(stream)
                if not isinstance(data, dict) or not any(n != 'meta' for n in data):
                    raise ValueError('工程中没有工作表')
                for name, record in data.items():
                    if name == 'meta':
                        if not isinstance(record, dict):
                            raise ValueError('无效的工程信息')
                    elif (not self._valid_name(name) or not isinstance(record, dict)
                          or not isinstance(record.get('table'), pd.DataFrame)):
                        raise ValueError('无效的工作表数据')
            elif suffix == '.pickle':
                df = pd.read_pickle(filename)
                if not isinstance(df, pd.DataFrame):
                    raise ValueError('单表文件必须包含 DataFrame')
                data = {self._unique_name(Path(filename).stem, {}): {'table': df}}
            else:
                raise ValueError('请选择 .dexpl 或 .pickle 文件')
            if not self._confirm_discard():
                return False
            self._replace(data, os.fspath(filename) if suffix == '.dexpl' else None)
            return True
        except Exception as error:
            messagebox.showerror('打开失败', str(error), parent=self.main)
            return False

    def save_file(self):
        return self._save_project(self.filename) if self.filename else self.save_as_file()

    def save_as_file(self):
        filename = filedialog.asksaveasfilename(parent=self.main, defaultextension='.dexpl',
                                               initialdir=self.defaultsavedir,
                                               filetypes=[('Minijmp 项目', '*.dexpl')])
        return self._save_project(filename) if filename else False

    def _save_project(self, filename):
        temporary = None
        try:
            if Path(filename).suffix.lower() != '.dexpl':
                raise ValueError('项目请保存为 .dexpl；单表请使用“导出当前表”。')
            self._finish_edit()
            fd, temporary = tempfile.mkstemp(dir=Path(filename).resolve().parent, suffix='.tmp')
            with os.fdopen(fd, 'wb') as raw:
                with gzip.GzipFile(fileobj=raw, mode='wb') as stream:
                    pickle.dump(self._payload(), stream, protocol=pickle.HIGHEST_PROTOCOL)
                raw.flush()
                os.fsync(raw.fileno())
            os.replace(temporary, filename)
            self.filename = os.fspath(filename)
            self.defaultsavedir = os.path.dirname(os.path.abspath(filename))
            self._saved_state = self._state()
            self.update_title()
            return True
        except Exception as error:
            messagebox.showerror('保存失败', str(error), parent=self.main)
            return False
        finally:
            if temporary and os.path.exists(temporary):
                os.unlink(temporary)

    def _import_frames(self, frames, directory=None):
        # Build every widget before touching the live notebook.
        self._finish_edit()
        staged = {}
        try:
            for name, df in frames.items():
                name = self._unique_name(name, dict(self.sheets, **staged))
                staged[name] = self._make_sheet(df)
                if directory is not None:
                    staged[name][1].currentdir = directory
                    staged[name][1].importpath = directory
        except Exception:
            for frame, table in staged.values():
                frame.destroy()
            raise
        for name, (frame, table) in staged.items():
            self.sheets[name], self.sheetframes[name] = table, frame
            self.nb.add(frame, text=name)
            self.nb.select(frame)
        self._sheet_changed()

    def import_csv(self, advanced=False, filename=None, **kwargs):
        from pandastable_local import core_orig
        table = self.getCurrentTable()
        filename = filename or filedialog.askopenfilename(parent=self.main,
                    initialdir=table.importpath or table.currentdir,
                    filetypes=[('CSV / 文本', '*.csv *.tsv *.txt')])
        if not filename:
            return False
        try:
            if advanced:
                df = core_orig.ImportDialog(table, filename=filename).df
            elif kwargs:
                if kwargs.get('dtype') is None and 'converters' not in kwargs:
                    from pandastable_local.csv_import import infer_numeric_columns
                    options = {**kwargs, 'dtype': object}
                    df = infer_numeric_columns(pd.read_csv(filename, **options),
                                              decimal=kwargs.get('decimal', '.'))
                else:
                    df = pd.read_csv(filename, **kwargs)
            else:
                options = core_orig.detect_csv(filename)
                confirm = options.pop('confirm')
                df = (core_orig.CSVPreviewDialog(table, filename, options).df if confirm
                      else core_orig.read_csv(filename, **options))
            if df is None:
                return False
            self._import_frames({Path(filename).stem: df}, os.path.dirname(os.path.abspath(filename)))
            return True
        except Exception as error:
            messagebox.showerror('CSV 导入失败', str(error), parent=self.main)
            return False

    def load_excel(self, filename=None):
        filename = filename or filedialog.askopenfilename(parent=self.main,
                    initialdir=self.getCurrentTable().currentdir,
                    filetypes=[('Excel', '*.xlsx *.xls')])
        if not filename:
            return False
        try:
            frames = pd.read_excel(filename, sheet_name=None, dtype=object)
            for df in frames.values():
                for position in range(df.shape[1]):
                    values = df.iloc[:, position]
                    large_integer = any(isinstance(value, int) and abs(value) > 2**53
                                        for value in values if not pd.isna(value))
                    # A nullable large-integer column would become float64 here.
                    if not large_integer:
                        df.isetitem(position, values.infer_objects())
            if Path(filename).suffix.lower() == '.xlsx':
                # shortcut: XML token recovery is .xlsx-only; legacy .xls stores numeric cells as doubles.
                # Recover numeric tokens rounded by the Excel engine from the source XML.
                _restore_excel_precision(filename, frames)
            self._import_frames(frames, os.path.dirname(os.path.abspath(filename)))
            return True
        except Exception as error:
            messagebox.showerror('Excel 导入失败', str(error), parent=self.main)
            return False

    def import_pi_data(self):
        from pi_import import PIImportDialog
        dialog = PIImportDialog(self.main)
        self.main.wait_window(dialog)
        if dialog.df is not None:
            try:
                self._import_frames({'PI 数据': dialog.df})
                return True
            except Exception as error:
                messagebox.showerror('PI 导入失败', str(error), parent=self.main)
        return False

    def export_sheet(self):
        self._finish_edit()
        filename = filedialog.asksaveasfilename(parent=self.main, defaultextension='.pickle',
                     filetypes=[('单表 pickle', '*.pickle'), ('Excel', '*.xlsx'), ('CSV', '*.csv')])
        if filename:
            try:
                self.getCurrentTable().saveAs(filename)
            except Exception as error:
                messagebox.showerror('导出失败', str(error), parent=self.main)

    def quit(self):
        if self._confirm_discard():
            for name in list(self.sheets):
                self._dispose_sheet(self.sheets[name], self.sheetframes[name])
            self.main.destroy()
