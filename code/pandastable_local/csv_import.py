"""Conservative CSV detection and lossless text parsing for the default import."""
import codecs
import csv
import io
import re
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
    for col in frame:
        values = frame[col]
        present = values[values != ""]
        cleaned = values.replace("", float("nan"))
        # Preserve identifiers and long integers instead of rounding them as floats.
        if len(present) and NUMBER.fullmatch(next(iter(present))) and all(NUMBER.fullmatch(v) and
                                ("." in v or "e" in v.lower() or
                                 len(v.lstrip("+-")) <= 15) for v in pd.unique(present.to_numpy())):
            converted = pd.to_numeric(cleaned, errors="coerce")
            if converted[present.index].notna().all() and not converted.isin([float("inf"), -float("inf")]).any():
                frame[col] = converted
                continue
        frame[col] = cleaned
    return frame
