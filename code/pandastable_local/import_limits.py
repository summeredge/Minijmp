"""Resource checks at local file import boundaries; never modify live tables."""
from pathlib import Path
from time import monotonic
import zipfile
from xml.etree import ElementTree as ET

MAX_FILE_BYTES = 256 * 1024**2
MAX_EXPANDED_BYTES = 512 * 1024**2
MAX_MEMORY_BYTES = 1024**3
MAX_METADATA_BYTES = 16 * 1024**2
MAX_ROWS = 2_000_000
MAX_COLUMNS = 16_384
MAX_CELLS = 10_000_000
MAX_SHEETS = 256
MAX_MEMBERS = 4096
MAX_PARSE_SECONDS = 60


def check_deadline(start):
    if monotonic() - start > MAX_PARSE_SECONDS:
        raise ValueError('导入解析超过 60 秒，请拆分文件后重试。')


def check_file(filename):
    if Path(filename).stat().st_size > MAX_FILE_BYTES:
        raise ValueError('文件超过 256 MiB 导入上限，请拆分文件后重试。')


def check_shape(rows, columns, cells=None):
    if (rows > MAX_ROWS or columns > MAX_COLUMNS
            or (rows * columns if cells is None else cells) > MAX_CELLS):
        raise ValueError('数据超过导入上限（200 万行、16384 列或总计 1000 万单元格），请拆分后重试。')


def check_archive(archive):
    entries = archive.infolist()
    if (len(entries) > MAX_MEMBERS
            or sum(item.file_size for item in entries) > MAX_EXPANDED_BYTES):
        raise ValueError('压缩文件超过导入资源上限（4096 项或解压后 512 MiB），请拆分后重试。')


def check_frames(frames):
    cells = memory = 0
    if len(frames) > MAX_SHEETS:
        raise ValueError('文件超过 256 个工作表导入上限。')
    for frame in frames.values():
        cells += frame.shape[0] * frame.shape[1]
        check_shape(*frame.shape, cells=cells)
        memory += int(frame.memory_usage(index=True, deep=True).sum())
        if memory > MAX_MEMORY_BYTES:
            raise ValueError('数据超过 1 GiB 解析内存上限，请拆分后重试。')


def read_csv_bounded(filename, **options):
    import pandas as pd
    check_file(filename)
    frames = []
    rows = memory = 0
    start = monotonic()
    with pd.read_csv(filename, chunksize=1000, **options) as reader:
        for frame in reader:
            check_deadline(start)
            rows += len(frame)
            check_shape(rows, frame.shape[1])
            memory += int(frame.memory_usage(index=True, deep=True).sum())
            if memory > MAX_MEMORY_BYTES:
                raise ValueError('CSV 超过 1 GiB 解析内存上限，请拆分后重试。')
            frames.append(frame)
    return pd.concat(frames) if frames else pd.DataFrame()


def check_excel(filename):
    check_file(filename)
    start = monotonic()
    cells = sheets = 0
    if Path(filename).suffix.lower() == '.xls':
        import xlrd
        with xlrd.open_workbook(filename, on_demand=True) as book:
            if book.nsheets > MAX_SHEETS:
                raise ValueError('文件超过 256 个工作表导入上限。')
            for index in range(book.nsheets):
                sheet = book.sheet_by_index(index)
                check_deadline(start)
                cells += sheet.nrows * sheet.ncols
                check_shape(sheet.nrows, sheet.ncols, cells=cells)
                book.unload_sheet(index)
        return
    with zipfile.ZipFile(filename) as archive:
        check_archive(archive)
        for name in archive.namelist():
            if not (name.startswith('xl/worksheets/') and name.endswith('.xml')):
                continue
            sheets += 1
            if sheets > MAX_SHEETS:
                raise ValueError('文件超过 256 个工作表导入上限。')
            rows = columns = 0
            with archive.open(name) as stream:
                stack = []
                for event, element in ET.iterparse(stream, events=('start', 'end')):
                    if event == 'start':
                        stack.append(element)
                        continue
                    check_deadline(start)
                    if element.tag.rsplit('}', 1)[-1] == 'c':
                        reference = element.get('r', '')
                        column = 0
                        for letter in reference:
                            if not letter.isalpha():
                                break
                            column = column * 26 + ord(letter.upper()) - ord('A') + 1
                        row = reference.lstrip('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz')
                        rows = max(rows, int(row or 0))
                        columns = max(columns, column)
                        check_shape(rows, columns, cells=cells + rows * columns)
                    stack.pop()
                    if stack:
                        stack[-1].remove(element)
                    element.clear()
            cells += rows * columns
