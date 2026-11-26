"""Conservative CSV detection and lossless text parsing for the default import."""
import codecs
import csv
import io
import math
import re
from decimal import Decimal, InvalidOperation
from itertools import chain

import pandas as pd
from .import_limits import check_file, check_shape
from . import import_limits


DELIMITERS = {"Comma": ",", "Tab": "\t", "Semicolon": ";", "Pipe": "|"}
NUMBER = re.compile(r"[+-]?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?\Z")
SAMPLE_BYTES = 64 * 1024


def read_records(text, delimiter):
    return _read_records(io.StringIO(text, newline=""), delimiter)


def _read_records(lines, delimiter, partial=False, header_rows=0):
    def checked_lines():
        for line in lines:
            if '\x00' in line:
                raise ValueError("文件包含 NUL 字符，请检查编码或使用 Advanced Import。")
            yield line

    rows = []
    start = import_limits.monotonic()
    width = 0
    reader = csv.reader(checked_lines(), delimiter=delimiter, strict=True)
    while True:
        try:
            row = next(reader)
        except StopIteration:
            break
        except csv.Error as error:
            if partial and str(error) == "unexpected end of data":
                break
            raise
        if not row:
            continue
        import_limits.check_deadline(start)
        width = width or len(row)
        check_shape(max(0, len(rows) + 1 - header_rows), len(row))
        if len(row) != width:
            raise ValueError(f"第 {len(rows) + 1} 条记录有 {len(row)} 列，预期 {width} 列。请检查分隔符或使用 Advanced Import。")
        rows.append(row)
    if not rows and not partial:
        raise ValueError("文件为空。")
    return rows


def _safe_number(value, decimal="."):
    if not isinstance(value, str):
        return False
    normalized = value.replace(decimal, ".") if decimal and decimal != "." else value
    if not NUMBER.fullmatch(normalized):
        return False
    if "." not in normalized and "e" not in normalized.lower():
        return len(normalized.lstrip("+-")) <= 15
    try:
        exact = Decimal(normalized)
        number = float(normalized)
    except (InvalidOperation, OverflowError, ValueError):
        return False
    return math.isfinite(number) and Decimal(str(number)) == exact


def infer_numeric_columns(frame, decimal="."):
    """Infer only numeric columns whose source tokens survive float parsing."""
    for position in range(frame.shape[1]):
        values = frame.iloc[:, position]
        present = values.notna() & values.ne("")
        tokens = values[present].unique()
        if len(tokens) and all(_safe_number(value, decimal) for value in tokens):
            cleaned = values.where(present).astype(object)
            if decimal and decimal != ".":
                cleaned = cleaned.str.replace(decimal, ".", regex=False)
            converted = pd.to_numeric(cleaned, errors="coerce")
            if converted[present].notna().all() and not converted.isin([float("inf"), -float("inf")]).any():
                frame.isetitem(position, converted)
                continue
        frame.isetitem(position, values.map(
            lambda value: float("nan") if pd.isna(value) or
            (isinstance(value, str) and value == "") else value))
    return frame


def csv_sample(filename):
    check_file(filename)
    with open(filename, "rb") as stream:
        raw = stream.read(SAMPLE_BYTES + 1)
    return raw[:SAMPLE_BYTES], len(raw) > SAMPLE_BYTES


def _decode_sample(raw, encoding, partial):
    text = codecs.getincrementaldecoder(encoding)().decode(raw, final=not partial)
    if partial:
        text = text[:max(text.rfind("\n"), text.rfind("\r")) + 1]
    return text


def _decode_file(filename, encoding):
    start = import_limits.monotonic()
    with open(filename, encoding=encoding) as stream:
        while stream.read(SAMPLE_BYTES):
            import_limits.check_deadline(start)


def detect_csv(filename, *, retry_encoding=False):
    raw, partial = csv_sample(filename)
    uncertain_encoding = False
    if raw.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        if retry_encoding:
            _decode_file(filename, "utf-16")
        encoding = "utf-16"
        text = _decode_sample(raw, encoding, partial)
    else:
        encodings = ("gb18030", "cp1252") if retry_encoding else ("utf-8-sig", "gb18030", "cp1252")
        for encoding in encodings:
            try:
                if retry_encoding:
                    _decode_file(filename, encoding)
                text = _decode_sample(raw, encoding, partial)
                break
            except UnicodeDecodeError:
                if encoding == "cp1252":
                    raise
        uncertain_encoding = encoding != "utf-8-sig"
    candidates = []
    rows = None
    for delimiter in DELIMITERS.values():
        try:
            records = (_read_records(io.StringIO(text, newline=""), delimiter, partial=True)
                       if partial else read_records(text, delimiter))
        except (ValueError, csv.Error):
            continue
        if not records:
            continue
        if delimiter == ",":
            rows = records
        if len(records[0]) > 1:
            if not candidates:
                rows = records
            candidates.append(delimiter)
    delimiter = candidates[0] if candidates else ","
    if rows is None:
        if partial:
            return dict(encoding=encoding, delimiter=delimiter, header=None, confirm=True)
        rows = read_records(text, delimiter)
    header = _infer_header(rows)
    return dict(encoding=encoding, delimiter=delimiter, header=header,
                confirm=uncertain_encoding or len(candidates) != 1 or header is None)


def _infer_header(rows):
    if len(rows) > 1:
        first = rows[0]
        numeric = [bool(NUMBER.fullmatch(value)) for value in first]
        body = rows[1:]
        if all(numeric):
            if all(all(NUMBER.fullmatch(value) for value in
                       {row[col] for row in body})
                   for col in range(len(first))):
                return False
        elif (all(first) and len(set(first)) == len(first)
              and not any(numeric)):
            for col in range(len(first)):
                present = {row[col] for row in body if row[col]}
                if present and all(NUMBER.fullmatch(value) for value in present):
                    return True


def _make_frame(rows, header):
    names = rows.pop(0) if header else list(range(len(rows[0])))
    if header and (not all(names) or len(set(names)) != len(names)):
        raise ValueError("表头包含空名称或重复名称，请取消首行表头选项或使用 Advanced Import。")
    frame = pd.DataFrame(rows, columns=names)
    rows.clear()
    return infer_numeric_columns(frame)


def preview_csv(raw, partial, encoding, delimiter, header):
    text = _decode_sample(raw, encoding, partial)
    rows = _read_records(io.StringIO(text, newline=""), delimiter, partial)
    return _make_frame(rows, header) if rows else pd.DataFrame()


def read_csv(filename, encoding, delimiter, header, *, phase=None, verify_header=False):
    check_file(filename)
    with open(filename, encoding=encoding, newline="") as stream:
        rows = _read_records(stream, delimiter, header_rows=int(header is True))
    if phase is not None:
        phase('正在转换列类型…')
    if verify_header and _infer_header(rows) is not header:
        return None
    return _make_frame(rows, header)
