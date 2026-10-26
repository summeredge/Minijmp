"""Conservative CSV detection and lossless text parsing for the default import."""
import codecs
import csv
import io
import math
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pandas as pd


DELIMITERS = {"Comma": ",", "Tab": "\t", "Semicolon": ";", "Pipe": "|"}
NUMBER = re.compile(r"[+-]?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?\Z")


def read_records(text, delimiter):
    if '\x00' in text:
        raise ValueError("文件包含 NUL 字符，请检查编码或使用 Advanced Import。")
    rows = [row for row in csv.reader(io.StringIO(text, newline=""),
                                     delimiter=delimiter, strict=True) if row]
    if not rows or not rows[0]:
        raise ValueError("文件为空。")
    width = len(rows[0])
    for line, row in enumerate(rows, 1):
        if len(row) != width:
            raise ValueError(f"第 {line} 条记录有 {len(row)} 列，预期 {width} 列。请检查分隔符或使用 Advanced Import。")
    return rows


def _safe_number(value, decimal="."):
    if not isinstance(value, str):
        return False
    normalized = value.replace(decimal, ".") if decimal and decimal != "." else value
    if not NUMBER.fullmatch(normalized):
        return False
    mantissa = re.split("[eE]", normalized, maxsplit=1)[0]
    integer = mantissa.partition(".")[0].lstrip("+-")
    if len(integer) > 1 and integer.startswith("0"):
        return False
    if "." not in normalized and "e" not in normalized.lower() \
            and len(normalized.lstrip("+-")) > 15:
        return False
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
        raw = values.tolist()
        present = [(i, value) for i, value in enumerate(raw)
                   if not pd.isna(value) and not (isinstance(value, str) and value == "")]
        tokens = {value for _, value in present}
        if present and all(_safe_number(value, decimal) for value in tokens):
            cleaned = pd.Series([
                float("nan") if pd.isna(value) or value == "" else
                value.replace(decimal, ".") if isinstance(value, str) and decimal != "." else value
                for value in raw
            ], index=values.index, dtype=object)
            converted = pd.to_numeric(cleaned, errors="coerce")
            parsed = converted.iloc[[i for i, _ in present]]
            if parsed.notna().all() and not converted.isin([float("inf"), -float("inf")]).any():
                frame.isetitem(position, converted)
                continue
        frame.isetitem(position, values.map(
            lambda value: float("nan") if pd.isna(value) or
            (isinstance(value, str) and value == "") else value))
    return frame


def detect_csv(filename):
    raw = Path(filename).read_bytes()
    uncertain_encoding = False
    if raw.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        encoding = "utf-16"
        text = raw.decode(encoding)
    else:
        encoding = "utf-8-sig"
        try:
            text = raw.decode(encoding)
        except UnicodeDecodeError:
            uncertain_encoding = True
            try:
                text = raw.decode("gb18030")
                encoding = "gb18030"
            except UnicodeDecodeError:
                encoding = "cp1252"
                text = raw.decode(encoding)
    candidates = []
    rows = None
    for delimiter in DELIMITERS.values():
        try:
            records = read_records(text, delimiter)
        except (ValueError, csv.Error):
            continue
        if delimiter == ",":
            rows = records
        if len(records[0]) > 1:
            if not candidates:
                rows = records
            candidates.append(delimiter)
    delimiter = candidates[0] if candidates else ","
    # Validate the entire file before a worksheet can be replaced.
    if rows is None:
        rows = read_records(text, delimiter)
    header = None
    if len(rows) > 1:
        first = rows[0]
        numeric = [bool(NUMBER.fullmatch(value)) for value in first]
        body = rows[1:]
        if all(numeric):
            if all(all(NUMBER.fullmatch(value) for value in
                       {row[col] for row in body})
                   for col in range(len(first))):
                header = False
        elif (all(first) and len(set(first)) == len(first)
              and not any(numeric)):
            for col in range(len(first)):
                present = {row[col] for row in body if row[col]}
                if present and all(NUMBER.fullmatch(value) for value in present):
                    header = True
                    break
    return dict(encoding=encoding, delimiter=delimiter, header=header,
                confirm=uncertain_encoding or len(candidates) != 1 or header is None)


def read_csv(filename, encoding, delimiter, header):
    text = Path(filename).read_bytes().decode(encoding)
    rows = read_records(text, delimiter)
    names = rows.pop(0) if header else list(range(len(rows[0])))
    if header and (not all(names) or len(set(names)) != len(names)):
        raise ValueError("表头包含空名称或重复名称，请取消首行表头选项或使用 Advanced Import。")
    frame = pd.DataFrame(rows, columns=names)
    return infer_numeric_columns(frame)
