"""MTable worksheets and transactional Minijmp project files."""
import io
import json
import math
import os
import pickle
import posixpath
import re
import tempfile
import zipfile
from copy import deepcopy
from decimal import Decimal, InvalidOperation
from numbers import Number
from pathlib import Path
from tkinter import Menu, TclError, ttk, filedialog, messagebox, simpledialog
from xml.etree import ElementTree as ET

import pandas as pd
import numpy as np

from modified_table import MTable
from pandastable_local import config
from pandastable_local.dialogs import SplitWorksheetDialog, SubsetWorksheetDialog, run_import_task
from pandastable_local import import_limits
from doe_core import validate_worksheet_metadata
from project_results import read_results, write_results


_LEGACY_PROJECT = '旧版工程使用不安全的 pickle 格式，当前版本禁止直接打开'
_LEGACY_TABLE = '旧版 pickle 单表格式不安全，当前版本禁止打开或保存'
_NUMPY_DTYPES = {f'{kind}{bits}' for kind in ('int', 'uint', 'float')
                 for bits in (8, 16, 32, 64)} | {'bool', 'object', 'str'}
_PANDAS_DTYPES = _NUMPY_DTYPES | {
    'Int8', 'Int16', 'Int32', 'Int64', 'UInt8', 'UInt16', 'UInt32', 'UInt64',
    'Float32', 'Float64', 'boolean', 'string', 'category'}
_NUMPY_SCALARS = {dtype.__name__: dtype for dtype in (
    np.bool_, np.int8, np.int16, np.int32, np.int64, np.uint8, np.uint16,
    np.uint32, np.uint64, np.float16, np.float32, np.float64, np.str_)}


def _safe_dtype(dtype):
    return (isinstance(dtype, str) and (dtype in _PANDAS_DTYPES
            or re.fullmatch(r'(?:datetime64|timedelta64)\[(?:s|ms|us|ns)(?:, [A-Za-z0-9_./+:-]+)?\]', dtype)))


def _encode_json(value):
    """Encode only supported data, retaining tuple and mapping-key types."""
    if isinstance(value, np.generic):
        name = type(value).__name__
        if name not in _NUMPY_SCALARS:
            raise ValueError(f'工程包含无法安全保存的元数据类型：{name}')
        return {'$numpy': [name, _encode_json(value.item())]}
    if value is None or type(value) in (str, bool, int):
        return value
    if type(value) is float and math.isfinite(value):
        return value
    if type(value) is list:
        return [_encode_json(item) for item in value]
    if type(value) is tuple:
        return {'$tuple': [_encode_json(item) for item in value]}
    if type(value) is dict:
        return {'$map': [[_encode_json(key), _encode_json(item)]
                         for key, item in value.items()]}
    raise ValueError(f'工程包含无法安全保存的元数据类型：{type(value).__name__}')


def _decode_json(value):
    if value is None or type(value) in (str, bool, int):
        return value
    if type(value) is float and math.isfinite(value):
        return value
    if type(value) is list:
        return [_decode_json(item) for item in value]
    if type(value) is dict and set(value) == {'$numpy'}:
        parts = value['$numpy']
        if (type(parts) is not list or len(parts) != 2 or not isinstance(parts[0], str)
                or parts[0] not in _NUMPY_SCALARS):
            raise ValueError('无效的数值元数据')
        item = _decode_json(parts[1])
        if type(item) not in (bool, int, float, str):
            raise ValueError('无效的数值元数据')
        return _NUMPY_SCALARS[parts[0]](item)
    if type(value) is dict and set(value) == {'$tuple'} and type(value['$tuple']) is list:
        return tuple(_decode_json(item) for item in value['$tuple'])
    if type(value) is dict and set(value) == {'$map'} and type(value['$map']) is list:
        result = {}
        for pair in value['$map']:
            if type(pair) is not list or len(pair) != 2:
                raise ValueError('无效的工程元数据')
            key, item = _decode_json(pair[0]), _decode_json(pair[1])
            try:
                if key in result:
                    raise ValueError('重复的工程元数据键')
                result[key] = item
            except TypeError as error:
                raise ValueError('无效的工程元数据键') from error
        return result
    raise ValueError('无效或不支持的工程元数据')


def _column_info(columns):
    if isinstance(columns, pd.MultiIndex):
        return {'kind': 'multi', 'values': _encode_json(columns.tolist()),
                'names': _encode_json(columns.names)}
    if isinstance(columns, pd.RangeIndex):
        return {'kind': 'range', 'start': columns.start, 'stop': columns.stop,
                'step': columns.step, 'name': _encode_json(columns.name)}
    if type(columns) is pd.Index and _safe_dtype(str(columns.dtype)):
        return {'kind': 'index', 'values': _encode_json(columns.tolist()),
                'dtype': str(columns.dtype), 'name': _encode_json(columns.name)}
    raise ValueError(f'不支持安全保存此列索引类型：{type(columns).__name__}')


def _restore_columns(info):
    if not isinstance(info, dict):
        raise ValueError('无效的列索引')
    if info.get('kind') == 'range':
        if any(type(info.get(key)) is not int for key in ('start', 'stop', 'step')):
            raise ValueError('无效的列索引范围')
        return pd.RangeIndex(info['start'], info['stop'], info['step'],
                             name=_decode_json(info.get('name')))
    if info.get('kind') == 'multi':
        return pd.MultiIndex.from_tuples(_decode_json(info['values']),
                                         names=_decode_json(info['names']))
    if info.get('kind') == 'index' and _safe_dtype(info.get('dtype')):
        return pd.Index(_decode_json(info['values']), dtype=info['dtype'],
                        name=_decode_json(info.get('name')), tupleize_cols=False)
    raise ValueError('无效或不支持的列索引')


_OBJECT_NULLS = {'none': None, 'nan': float('nan'), 'na': pd.NA, 'nat': pd.NaT,
                 'float16': np.float16('nan'), 'float32': np.float32('nan'),
                 'float64': np.float64('nan')}


def _read_frame(content, columns, attrs, pandas_metadata, object_nulls):
    import pyarrow as pa
    import pyarrow.parquet as pq

    if len(content) < 12 or content[:4] != b'PAR1' or content[-4:] != b'PAR1':
        raise ValueError('工作表 Parquet 文件无效')
    footer_size = int.from_bytes(content[-8:-4], 'little')
    if footer_size > len(content) - 12:
        raise ValueError('工作表 Parquet 文件已损坏')
    # Even read_metadata can invoke an Arrow extension decoder; check the raw footer first.
    if b'ARROW:schema' in content[-8-footer_size:-8]:
        raise ValueError('不支持包含 Arrow 扩展类型的工作表')
    source = io.BytesIO(content)
    parquet_info = pq.read_metadata(source)
    import_limits.check_shape(parquet_info.num_rows, parquet_info.num_columns)
    if sum(parquet_info.row_group(i).total_byte_size for i in range(parquet_info.num_row_groups)) > import_limits.MAX_EXPANDED_BYTES:
        raise ValueError('工作表超过 512 MiB 解压上限，请拆分后重试。')
    metadata = parquet_info.metadata or {}
    # Arrow's serialized schema may invoke registered Python extension types.
    if metadata:
        raise ValueError('不支持包含 Arrow 扩展类型的工作表')
    if not isinstance(pandas_metadata, dict):
        raise ValueError('无效的工作表类型信息')
    categories = pandas_metadata.get('minijmp_categories', [])
    if not isinstance(categories, list):
        raise ValueError('无效的分类列信息')
    column_metadata = pandas_metadata.get('columns')
    column_indexes = pandas_metadata.get('column_indexes')
    if (not isinstance(column_metadata, list) or not isinstance(column_indexes, list)
            or len(column_indexes) > 1
            or any(not isinstance(c, dict) or not _safe_dtype(c.get('numpy_type'))
                   for c in column_metadata)
            or any(not isinstance(c, dict) or c.get('pandas_type') not in ('unicode', 'string')
                   or c.get('numpy_type') not in ('str', 'object')
                   for c in column_indexes)):
        raise ValueError('工作表包含不支持的数据类型')
    # Attributes are restored from our explicitly typed JSON, never Parquet metadata.
    pandas_metadata = {key: value for key, value in pandas_metadata.items()
                       if key != 'minijmp_categories'}
    pandas_metadata['attributes'] = {}
    source.seek(0)
    batches = []
    memory = 0
    start = import_limits.monotonic()
    for batch in pq.ParquetFile(source, arrow_extensions_enabled=False).iter_batches(batch_size=1024):
        import_limits.check_deadline(start)
        memory += batch.nbytes
        if memory > import_limits.MAX_MEMORY_BYTES:
            raise ValueError('工作表超过 1 GiB 解析内存上限，请拆分后重试。')
        batches.append(batch)
    table = pa.Table.from_batches(batches, schema=pq.read_schema(source))
    table = table.replace_schema_metadata({b'pandas': json.dumps(pandas_metadata).encode('utf-8')})
    frame = table.to_pandas()
    object_fields = {c.get('field_name') for c in column_metadata if c['numpy_type'] == 'object'}
    for index, name in enumerate(frame.columns):
        if name in object_fields:
            frame.isetitem(index, frame.iloc[:, index].astype(object))
    if not isinstance(object_nulls, list):
        raise ValueError('无效的缺失值信息')
    seen = set()
    for item in object_nulls:
        if (not isinstance(item, list) or len(item) != 3 or type(item[0]) is not int
                or type(item[1]) is not int or not isinstance(item[2], str)
                or not 0 <= item[0] < frame.shape[1] or not 0 <= item[1] < len(frame)
                or frame.columns[item[0]] not in object_fields or item[2] not in _OBJECT_NULLS
                or (item[0], item[1]) in seen):
            raise ValueError('无效的缺失值信息')
        seen.add((item[0], item[1]))
        frame.iat[item[1], item[0]] = _OBJECT_NULLS[item[2]]
    restored_categories = set()
    for item in categories:
        if (not isinstance(item, list) or len(item) != 4 or type(item[0]) is not int
                or not 0 <= item[0] < frame.shape[1] or item[0] in restored_categories
                or not _safe_dtype(item[1]) or item[1] == 'category'
                or not isinstance(item[2], list) or type(item[3]) is not bool
                or frame.iloc[:, item[0]].dtype.kind != 'i'):
            raise ValueError('无效的分类列信息')
        position, dtype, values, ordered = item
        labels = pd.Index(_decode_json(values), dtype=dtype, tupleize_cols=False)
        restored = pd.Categorical.from_codes(frame.iloc[:, position], labels, ordered=ordered)
        frame.isetitem(position, restored)
        restored_categories.add(position)
    frame.columns = _restore_columns(columns)
    frame.attrs = _decode_json(attrs)
    if not isinstance(frame.attrs, dict):
        raise ValueError('无效的工作表属性')
    return frame


def _write_frame(frame):
    import pyarrow as pa
    import pyarrow.parquet as pq

    if not isinstance(frame, pd.DataFrame):
        raise ValueError('无效的工作表数据')
    columns, attrs = _column_info(frame.columns), _encode_json(frame.attrs)
    object_nulls = []
    for column, dtype in enumerate(frame.dtypes):
        if dtype != object:
            continue
        for row, value in enumerate(frame.iloc[:, column]):
            if value is None:
                kind = 'none'
            elif value is pd.NA:
                kind = 'na'
            elif value is pd.NaT:
                kind = 'nat'
            elif isinstance(value, (float, np.floating)) and math.isnan(value):
                kind = 'nan' if type(value) is float else type(value).__name__
                if kind not in _OBJECT_NULLS:
                    raise ValueError(f'不支持的缺失值类型：{kind}')
            else:
                continue
            object_nulls.append([column, row, kind])
    normalized = frame.copy(deep=False)
    normalized.attrs = {}
    normalized.columns = [f'column_{index:06d}' for index in range(frame.shape[1])]
    try:
        categories = []
        for index, dtype in enumerate(frame.dtypes):
            if isinstance(dtype, pd.CategoricalDtype):
                labels = dtype.categories
                values = labels.asi8 if isinstance(labels, (pd.DatetimeIndex, pd.TimedeltaIndex)) else labels
                categories.append([index, str(labels.dtype), _encode_json(values.tolist()), dtype.ordered])
                # Parquet omits the Arrow schema in safe projects, so save codes and the full category index.
                normalized.isetitem(index, frame.iloc[:, index].cat.codes)
        table = pa.Table.from_pandas(normalized, preserve_index=None)
        pandas_metadata = json.loads(table.schema.metadata[b'pandas'])
        if categories:
            pandas_metadata['minijmp_categories'] = categories
        output = io.BytesIO()
        # Statistics can copy cell text into the footer checked for extension markers.
        pq.write_table(table, output, store_schema=False, write_statistics=False)
        content = output.getvalue()
        restored = _read_frame(content, columns, attrs, pandas_metadata, object_nulls)
        pd.testing.assert_frame_equal(frame, restored, check_exact=True,
                                      check_index_type=True, check_column_type=True)
        for index, dtype in enumerate(frame.dtypes):
            if dtype == object and any(type(a) is not type(b) for a, b in
                                       zip(frame.iloc[:, index], restored.iloc[:, index])):
                raise ValueError('对象列中的值或缺失值类型发生变化')
    except Exception as error:
        raise ValueError(f'工作表无法使用安全格式无损保存：{error}') from error
    return content, columns, attrs, pandas_metadata, object_nulls


def _reject_legacy_overwrite(filename):
    if os.path.isfile(filename):
        with open(filename, 'rb') as stream:
            if stream.read(2) == b'\x1f\x8b':
                raise ValueError(_LEGACY_PROJECT + '，请另存为新文件')


def write_project_file(filename, data):
    """Write a project atomically, leaving an old project untouched on failure."""
    if not isinstance(data, dict) or not any(name != 'meta' for name in data):
        raise ValueError('工程中没有工作表')
    _reject_legacy_overwrite(filename)
    metadata = dict(data.get('meta', {}))
    results = metadata.pop('results', [])
    manifest = {'format': 'MiniJMP', 'version': 1,
                'metadata': _encode_json(metadata), 'sheets': []}
    temporary = None
    try:
        fd, temporary = tempfile.mkstemp(dir=Path(filename).resolve().parent, suffix='.tmp')
        with os.fdopen(fd, 'w+b') as raw:
            with zipfile.ZipFile(raw, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
                for index, (name, record) in enumerate((item for item in data.items() if item[0] != 'meta'), 1):
                    if not Worksheets._valid_name(name) or not isinstance(record, dict):
                        raise ValueError('无效的工作表信息')
                    content, columns, attrs, pandas_metadata, object_nulls = _write_frame(record.get('table'))
                    path = f'worksheets/sheet_{index:03d}.parquet'
                    archive.writestr(path, content)
                    manifest['sheets'].append({'name': name, 'file': path, 'columns': columns,
                                               'attrs': attrs, 'pandas': pandas_metadata,
                                               'object_nulls': object_nulls,
                                               'metadata': _encode_json(record.get('meta', {}))})
                if results:
                    manifest['results'] = write_results(archive, results)
                content = json.dumps(manifest, ensure_ascii=False, allow_nan=False).encode('utf-8')
                if len(content) > import_limits.MAX_METADATA_BYTES:
                    raise ValueError('工程元数据超过 16 MiB 上限。')
                archive.writestr('manifest.json', content)
                import_limits.check_archive(archive)
            raw.flush()
            os.fsync(raw.fileno())
        _reject_legacy_overwrite(filename)
        import_limits.check_file(temporary)
        os.replace(temporary, filename)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def read_project_file(filename):
    """Read only the versioned JSON/Parquet project format."""
    if Path(filename).suffix.lower() in ('.pickle', '.pkl'):
        raise ValueError(_LEGACY_TABLE)
    import_limits.check_file(filename)
    with open(filename, 'rb') as stream:
        if stream.read(2) == b'\x1f\x8b':
            raise ValueError(_LEGACY_PROJECT)
    try:
        with zipfile.ZipFile(filename) as archive:
            import_limits.check_archive(archive)
            names = archive.namelist()
            if len(names) != len(set(names)) or 'manifest.json' not in names:
                raise ValueError('工程文件结构无效')
            if archive.getinfo('manifest.json').file_size > import_limits.MAX_METADATA_BYTES:
                raise ValueError('工程元数据超过 16 MiB 上限。')
            manifest = json.loads(archive.read('manifest.json'))
            if (not isinstance(manifest, dict) or manifest.get('format') != 'MiniJMP'
                    or type(manifest.get('version')) is not int or manifest['version'] != 1
                    or not isinstance(manifest.get('sheets'), list) or not manifest['sheets']):
                raise ValueError('不支持的工程格式或版本')
            if len(manifest['sheets']) > import_limits.MAX_SHEETS:
                raise ValueError('文件超过 256 个工作表导入上限。')
            data = {'meta': _decode_json(manifest.get('metadata'))}
            if not isinstance(data['meta'], dict):
                raise ValueError('无效的工程信息')
            paths = {'manifest.json'}
            total_cells = total_memory = 0
            for index, entry in enumerate(manifest['sheets'], 1):
                if not isinstance(entry, dict):
                    raise ValueError('无效的工作表信息')
                name, path = entry.get('name'), entry.get('file')
                if (not Worksheets._valid_name(name) or name in data
                        or path != f'worksheets/sheet_{index:03d}.parquet' or path in paths):
                    raise ValueError('无效的工作表名称或文件')
                paths.add(path)
                meta = _decode_json(entry.get('metadata'))
                if not isinstance(meta, dict):
                    raise ValueError('无效的工作表信息')
                data[name] = {'table': _read_frame(archive.read(path), entry.get('columns'),
                                                    entry.get('attrs'), entry.get('pandas'),
                                                    entry.get('object_nulls')), 'meta': meta}
                frame = data[name]['table']
                total_cells += frame.shape[0] * frame.shape[1]
                total_memory += int(frame.memory_usage(index=True, deep=True).sum())
                import_limits.check_shape(*frame.shape, cells=total_cells)
                if total_memory > import_limits.MAX_MEMORY_BYTES:
                    raise ValueError('工程超过 1 GiB 解析内存上限，请拆分后重试。')
            if 'results' in manifest:
                data['meta']['results'] = read_results(archive, manifest['results'], paths,
                                                       set(data) - {'meta'})
            if set(names) != paths:
                raise ValueError('工程文件结构无效')
            active = data['meta'].get('active')
            if active is not None and (not isinstance(active, str) or active not in data or active == 'meta'):
                raise ValueError('无效的活动工作表')
            return data
    except (zipfile.BadZipFile, KeyError, json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ValueError('工程文件无效或已损坏') from error


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
            replacements = {}
            columns = [frame.iloc[:, i].array for i in range(frame.shape[1])]
            column_numbers = {}
            row_tag, cell_tag, value_tag = (main_ns + tag for tag in ("row", "c", "v"))
            with workbook.open(path) as stream:
                sheet_data = None
                for event, element in ET.iterparse(stream, events=("start", "end")):
                    if event == "start":
                        if element.tag == main_ns + "sheetData":
                            sheet_data = element
                        continue
                    if element.tag != row_tag or sheet_data is None:
                        continue
                    for cell in element.iter(cell_tag):
                        if cell.get("t") not in (None, "n"):
                            continue
                        value = cell.findtext(value_tag)
                        reference = cell.get("r", "")
                        letters = reference.rstrip("0123456789")
                        if not value or not letters or letters == reference:
                            continue
                        if letters not in column_numbers:
                            column = 0
                            for char in letters.upper():
                                column = column * 26 + ord(char) - ord("A") + 1
                            column_numbers[letters] = column - 1
                        column = column_numbers[letters]
                        row = int(reference[len(letters):]) - 2
                        if not (0 <= row < len(frame) and 0 <= column < len(columns)):
                            continue
                        current = columns[column][row]
                        if not isinstance(current, Number) or pd.isna(current):
                            continue
                        parsed = str(current)
                        try:
                            if value != parsed and Decimal(value) != Decimal(parsed):
                                replacements.setdefault(column, {})[row] = value
                        except InvalidOperation:
                            continue
                    sheet_data.remove(element)
                    element.clear()
            for column, cells in replacements.items():
                values = frame.iloc[:, column].astype(object)
                for row, value in cells.items():
                    values.iloc[row] = value
                frame.isetitem(column, values)


def _read_excel(filename, phase):
    import_limits.check_excel(filename)
    phase('正在读取 Excel 工作表…')
    frames = pd.read_excel(filename, sheet_name=None, dtype=object)
    import_limits.check_frames(frames)
    phase('正在校验 Excel 数值精度…')
    for df in frames.values():
        for position in range(df.shape[1]):
            values = df.iloc[:, position]
            inferred = values.infer_objects()
            # A nullable large-integer column would become float64 here.
            if inferred.dtype.kind not in 'iuf' or not any(
                    isinstance(value, int) and abs(value) > 2**53 for value in values):
                df.isetitem(position, inferred)
    if Path(filename).suffix.lower() == '.xlsx':
        # shortcut: XML token recovery is .xlsx-only; legacy .xls stores numeric cells as doubles.
        _restore_excel_precision(filename, frames)
    return frames


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
        self.project_results = []
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

    def addSheet(self, name=None, dataframe=None, meta=None, *, finish_edits=True):
        if self.sheets and finish_edits:
            self._finish_edit()
        name = self._unique_name(name or '工作表')
        frame, table = self._make_sheet(dataframe, meta)
        self.sheets[name], self.sheetframes[name] = table, frame
        self.nb.add(frame, text=name)
        self.nb.select(frame)
        self.table = table
        return table

    def merge_project_worksheets(self):
        from worksheet_merge import WorksheetMergeDialog

        if len(self.sheets) < 2:
            messagebox.showinfo('合并项目工作表', '项目中至少需要两张工作表。', parent=self.main)
            return
        return WorksheetMergeDialog(self)

    def worksheet_calculation(self, mode):
        from worksheet_calculations import WorksheetCalculationDialog
        WorksheetCalculationDialog(self, mode)

    def subset_sheet(self):
        dialog = SubsetWorksheetDialog(self.main, self.getCurrentTable().model.df,
                                       self.getCurrentSheet()[:67] + ' 子集', self._valid_name)
        if dialog.result is None:
            return
        name, frame = dialog.result
        # Creating a subset must not commit pending edits in any source sheet.
        self.addSheet(name, frame, finish_edits=False)
        if len(frame) == 0:
            messagebox.showinfo('子集化工作表', '已创建 0 行工作表，保留原有列结构。', parent=self.main)

    def split_worksheet(self):
        source = self.getCurrentSheet()
        frame = self.getCurrentTable().model.df
        dialog = SplitWorksheetDialog(self.main, frame, self.sheets, self._unique_name)
        if dialog.result is None:
            return

        created = []
        try:
            for raw_name, _, positions in dialog.result:
                self.addSheet(raw_name, frame.iloc[positions].copy(deep=True), finish_edits=False)
                created.append(self.getCurrentSheet())
        except Exception as error:
            for name in reversed(created):
                self._dispose_sheet(self.sheets.pop(name), self.sheetframes.pop(name))
            self.nb.select(self.sheetframes[source])
            self.table = self.sheets[source]
            messagebox.showerror('拆分工作表失败', f'无法创建拆分结果：{error}', parent=self.main)
            return

        self.nb.select(self.sheetframes[created[0]])
        self.table = self.sheets[created[0]]

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
        for record in self.project_results:
            if record['source'] == old:
                record['source'] = record['source_label'] = name
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
        for record in self.project_results:
            if record['source'] == name:
                record['source'] = None
        self._dispose_sheet(table, frame)
        self._sheet_changed()
        return True

    def _dispose_sheet(self, table, frame):
        child_viewer = getattr(getattr(table, 'child', None), 'pf', None)
        if child_viewer is not None and child_viewer is not getattr(table, 'pf', None):
            child_viewer.close()
        for attr in ('tOut', '_plot_preview', 'pf'):
            viewer = getattr(table, attr, None)
            if viewer is not None:
                viewer.close()
        self.nb.forget(frame)
        frame.destroy()

    @staticmethod
    def _full_frame(table):
        return table.dataframe if table.filtered else table.model.df

    def saveMeta(self, table, *, validate_doe=True):
        meta = {'minijmp': 1, 'columnwidths': dict(table.columnwidths),
                'formulas': table.export_formulas(), 'formula_auto': table.formulas_auto,
                'options': {k: getattr(table, k) for k in
                            ('floatprecision', 'cellwidth', 'rowheight', 'showindex',
                             'cellbackgr', 'textcolor', 'grid_color', 'thefont')}}
        doe = getattr(table, 'doe_metadata', None)
        if doe is not None:
            # Dirty-state snapshots remain usable after DOE inputs change; saves still validate.
            meta['doe'] = (validate_worksheet_metadata(self._full_frame(table), doe)
                           if validate_doe else doe)
        mixture = getattr(table, 'mixture_metadata', None)
        if mixture is not None:
            model = getattr(table, 'mixture_model', None)
            if validate_doe and model is not None:
                from doe_mixture import restore_mixture_model
                restore_mixture_model(self._full_frame(table), mixture, model, doe)
                meta['mixture'] = deepcopy(mixture)
                meta['mixture_model'] = dict(model)
            elif validate_doe:
                from doe_mixture import validate_mixture_metadata
                meta['mixture'] = validate_mixture_metadata(
                    self._full_frame(table), mixture, doe)
            else:
                meta['mixture'] = mixture
                if model is not None:
                    meta['mixture_model'] = model
        return meta

    def loadMeta(self, table, meta):
        if not isinstance(meta, dict):
            return
        raw_doe = meta.get('doe')
        doe = (validate_worksheet_metadata(self._full_frame(table), raw_doe)
               if 'doe' in meta else None)
        mixture = None
        mixture_model = None
        if 'mixture' in meta:
            from doe_mixture import restore_mixture_model, validate_mixture_metadata
            if 'mixture_model' in meta:
                restore_mixture_model(self._full_frame(table), meta['mixture'],
                                      meta['mixture_model'], raw_doe)
                mixture = deepcopy(meta['mixture'])
                mixture_model = dict(meta['mixture_model'])
            else:
                mixture = validate_mixture_metadata(
                    self._full_frame(table), meta['mixture'], raw_doe)
        table.doe_metadata = doe
        table.mixture_metadata = mixture
        table.mixture_model = mixture_model
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
        allowed = self.saveMeta(table, validate_doe=False)['options']
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

    def _payload(self, *, validate_doe=True):
        data = {n: {'table': self._full_frame(t),
                    'meta': self.saveMeta(t, validate_doe=validate_doe)}
                for n, t in self.sheets.items()}
        data['meta'] = {'active': self.getCurrentSheet(), 'minijmp': 1,
                        'results': self.project_results}
        return data

    def _state(self):
        data = self._payload(validate_doe=False)
        # Selecting a tab alone is not a data change.
        results = data.pop('meta')['results']
        return pickle.dumps((data, results), protocol=pickle.HIGHEST_PROTOCOL)

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
        self.project_results = data.get('meta', {}).get('results', [])
        self.restore_result_plots()
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
        try:
            suffix = Path(filename).suffix.lower()
            if suffix == '.dexpl':
                data = read_project_file(filename)
            elif suffix in ('.pickle', '.pkl'):
                raise ValueError(_LEGACY_TABLE)
            else:
                raise ValueError('请选择 .dexpl 工程文件')
            if not self._confirm_discard():
                return False
            self._replace(data, os.fspath(filename))
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
        try:
            if Path(filename).suffix.lower() != '.dexpl':
                raise ValueError('项目请保存为 .dexpl；单表请使用“导出当前表”。')
            self._finish_edit()
            self.capture_live_result_plots()
            data = self._payload(validate_doe=False)
            downgraded = {}
            for name, table in self.sheets.items():
                doe = getattr(table, 'doe_metadata', None)
                if doe is not None:
                    try:
                        validate_worksheet_metadata(self._full_frame(table), doe)
                    except ValueError as error:
                        downgraded[name] = str(error)
                        for key in ('doe', 'mixture', 'mixture_model'):
                            data[name]['meta'].pop(key, None)
                        continue
                data[name]['meta'] = self.saveMeta(table)
            write_project_file(filename, data)
            for name in downgraded:
                table = self.sheets[name]
                table.doe_metadata = None
                table.mixture_metadata = None
                table.mixture_model = None
            self.filename = os.fspath(filename)
            self.defaultsavedir = os.path.dirname(os.path.abspath(filename))
            self._saved_state = self._state()
            self.update_title()
            if downgraded:
                messagebox.showwarning(
                    'DOE 工作表已按普通工作表保存',
                    '以下工作表的设计定义已失效，已保留全部数据并按普通工作表保存：\n'
                    + '\n'.join(f'{name}：{reason}' for name, reason in downgraded.items()),
                    parent=self.main)
            return True
        except Exception as error:
            messagebox.showerror('保存失败', str(error), parent=self.main)
            return False

    def _import_frames(self, frames, directory=None):
        # Build every widget before touching the live notebook.
        staged = {}
        try:
            for name, df in frames.items():
                name = self._unique_name(name, dict(self.sheets, **staged))
                staged[name] = self._make_sheet(df)
                if directory is not None:
                    staged[name][1].currentdir = directory
                    staged[name][1].importpath = directory
            for name, (frame, table) in staged.items():
                self.nb.add(frame, text=name)
            self._finish_edit()
            if staged:
                self.nb.select(frame)
        except Exception:
            for frame, table in staged.values():
                frame.destroy()
            raise
        for name, (frame, table) in staged.items():
            self.sheets[name], self.sheetframes[name] = table, frame
        if staged:
            self._sheet_changed()

    def _import_file(self, filename, kind, load):
        self._file_import_active = True
        workbook = getattr(self, 'sheets', None)
        try:
            frames = load()
            if frames is None or getattr(self, 'sheets', None) is not workbook:
                return False
            self._import_frames(frames, os.path.dirname(os.path.abspath(filename)))
            return True
        except Exception as error:
            if self.main.winfo_exists():
                messagebox.showerror(f'{kind} 导入失败', str(error), parent=self.main)
            return False
        finally:
            self._file_import_active = False

    def import_csv(self, advanced=False, filename=None, **kwargs):
        from pandastable_local import core_orig
        from pandastable_local.csv_import import infer_numeric_columns
        if getattr(self, '_file_import_active', False):
            return False
        table = self.getCurrentTable()
        filename = filename or filedialog.askopenfilename(parent=self.main,
                    initialdir=table.importpath or table.currentdir,
                    filetypes=[('CSV / 文本', '*.csv *.tsv *.txt')])
        if not filename:
            return False

        def read(phase, options, bounded):
            if bounded:
                if options.get('dtype') is None and 'converters' not in options:
                    df = import_limits.read_csv_bounded(filename, **{**options, 'dtype': object})
                    phase('正在转换列类型…')
                    infer_numeric_columns(df, decimal=options.get('decimal', '.'))
                else:
                    df = import_limits.read_csv_bounded(filename, **options)
            else:
                df = core_orig.read_csv(filename, **options, phase=phase, verify_header=True)
            if df is not None:
                import_limits.check_frames({'CSV': df})
            return df

        def auto_read(phase):
            options = core_orig.detect_csv(filename)
            if options.pop('confirm'):
                return options, None
            phase('正在读取 CSV…')
            try:
                df = read(phase, options, False)
            except UnicodeDecodeError:
                phase('正在检测 CSV 编码…')
                return core_orig.detect_csv(filename, retry_encoding=True), None
            if df is None:
                options['header'] = None
            return options, df

        def load():
            if advanced:
                if run_import_task(self.main, '正在检查 CSV…',
                                   lambda phase: import_limits.check_file(filename) or True) is None:
                    return None
                df = core_orig.ImportDialog(self.main, filename=filename).df
            elif kwargs:
                df = run_import_task(self.main, '正在读取 CSV…',
                                     lambda phase: read(phase, kwargs, True))
            else:
                result = run_import_task(self.main, '正在检测 CSV 格式…', auto_read)
                if result is None:
                    return None
                options, df = result
                if df is None:
                    df = core_orig.CSVPreviewDialog(self.main, filename, options).df
            return None if df is None else {Path(filename).stem: df}

        return self._import_file(filename, 'CSV', load)

    def load_excel(self, filename=None):
        if getattr(self, '_file_import_active', False):
            return False
        filename = filename or filedialog.askopenfilename(parent=self.main,
                    initialdir=self.getCurrentTable().currentdir,
                    filetypes=[('Excel', '*.xlsx *.xls')])
        if not filename:
            return False
        return self._import_file(filename, 'Excel', lambda: run_import_task(
            self.main, '正在检查 Excel 文件…', lambda phase: _read_excel(filename, phase)))

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
        filename = filedialog.asksaveasfilename(parent=self.main, defaultextension='.xlsx',
                     filetypes=[('Excel', '*.xlsx'), ('CSV', '*.csv')])
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
