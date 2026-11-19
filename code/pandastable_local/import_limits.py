"""Resource checks at local file import boundaries; never modify live tables."""
from pathlib import Path
from time import monotonic
import zipfile
from xml.parsers import expat

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
    parse_dates = options.get('parse_dates')
    fixed_types = (options.get('dtype') is object and options.get('converters') is None
                   and (parse_dates is None or parse_dates is False
                        or (parse_dates is True and options.get('index_col') is None)))
    with pd.read_csv(filename, chunksize=1000, **options) as reader:
        chunk_size = 1000
        while True:
            try:
                frame = reader.get_chunk(chunk_size)
            except StopIteration:
                break
            check_deadline(start)
            rows += len(frame)
            check_shape(rows, frame.shape[1])
            memory += int(frame.memory_usage(index=True, deep=True).sum())
            if memory > MAX_MEMORY_BYTES:
                raise ValueError('CSV 超过 1 GiB 解析内存上限，请拆分后重试。')
            frames.append(frame)
            if fixed_types:
                chunk_size = max(1000, min(20000, 200000 // max(1, frame.shape[1])))
    if len(frames) == 1:
        return frames[0]
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
            def check_cell(tag, attrs):
                nonlocal rows, columns
                if tag != 'c' and not tag.endswith('}c'):
                    return
                reference = attrs.get('r', '')
                row_text = reference.lstrip('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz')
                row = int(row_text or 0)
                column = 0
                for letter in reference[:len(reference) - len(row_text)]:
                    column = column * 26 + ord(letter.upper()) - ord('A') + 1
                if row > rows or column > columns:
                    rows = max(rows, row)
                    columns = max(columns, column)
                    check_shape(rows, columns, cells=cells + rows * columns)

            parser = expat.ParserCreate(namespace_separator='}')
            parser.StartElementHandler = check_cell
            with archive.open(name) as stream:
                while block := stream.read(64 * 1024):
                    check_deadline(start)
                    parser.Parse(block, False)
                parser.Parse(b'', True)
                check_deadline(start)
            cells += rows * columns
