"""Generate repeatable F3-3 import data and measure the real Tk import path."""

from __future__ import annotations

import argparse
import csv
import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from threading import Event, Thread
from time import perf_counter
import zipfile


ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "code"
CASES = {
    "csv-10k": ("csv", 10_000, 20),
    "csv-100k": ("csv", 100_000, 20),
    "csv-500k": ("csv", 500_000, 20),
    "csv-1m": ("csv", 1_000_000, 10),
    "excel-10k": ("excel", 10_000, 20),
    "excel-100k": ("excel", 100_000, 20),
}


def _row(index: int, columns: int, *, excel: bool) -> list[object]:
    from datetime import datetime, timedelta

    values = []
    for column in range(columns):
        kind = column % 5
        if kind == 0:
            value = index + 1
        elif kind == 1:
            value = datetime(2020, 1, 1) + timedelta(days=index % 365) if excel else (
                datetime(2020, 1, 1) + timedelta(days=index % 365)
            ).strftime("%Y-%m-%d")
        elif kind == 2:
            value = f"类别{index % 8}"
        elif kind == 3:
            value = None if index % 97 == 0 else round((index % 1000) / 10, 1)
        else:
            value = None if index % 113 == 0 else f"样本-{index % 100}"
        values.append(value if excel or value is not None else "")
    return values


def generate_csv(path: Path, rows: int, columns: int) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow([f"列{i + 1}" for i in range(columns)])
        for index in range(rows):
            writer.writerow(_row(index, columns, excel=False))


def generate_excel(path: Path, rows: int, columns: int) -> None:
    from datetime import datetime
    from openpyxl import Workbook

    workbook = Workbook(write_only=True)
    workbook.properties.created = datetime(2020, 1, 1)
    workbook.properties.modified = datetime(2020, 1, 1)
    sheet = workbook.create_sheet("数据")
    sheet.append([f"列{i + 1}" for i in range(columns)])
    for index in range(rows):
        sheet.append(_row(index, columns, excel=True))
    raw = path.with_name(path.name + ".raw")
    workbook.save(raw)
    with zipfile.ZipFile(raw) as source, zipfile.ZipFile(
        path, "w", compression=zipfile.ZIP_DEFLATED
    ) as target:
        for item in source.infolist():
            stable = zipfile.ZipInfo(item.filename, date_time=(2020, 1, 1, 0, 0, 0))
            stable.compress_type = zipfile.ZIP_DEFLATED
            stable.create_system = item.create_system
            stable.external_attr = item.external_attr
            stable.internal_attr = item.internal_attr
            stable.flag_bits = item.flag_bits
            contents = source.read(item.filename)
            if item.filename == "docProps/core.xml":
                contents = re.sub(
                    rb"(<dcterms:modified[^>]*>).*?(</dcterms:modified>)",
                    rb"\g<1>2020-01-01T00:00:00Z\g<2>", contents
                )
            target.writestr(stable, contents)
    raw.unlink()


class _MemorySample(ctypes.Structure):
    _fields_ = [
        ("cb", ctypes.c_ulong),
        ("PageFaultCount", ctypes.c_ulong),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
        ("PrivateUsage", ctypes.c_size_t),
    ]


def _memory_bytes() -> tuple[int, int]:
    if os.name != "nt":
        raise RuntimeError("此基准需要 Windows 进程内存指标。")
    sample = _MemorySample()
    sample.cb = ctypes.sizeof(sample)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    kernel32.GetCurrentProcess.restype = ctypes.c_void_p
    get_memory = psapi.GetProcessMemoryInfo
    get_memory.argtypes = [ctypes.c_void_p, ctypes.POINTER(_MemorySample), ctypes.c_ulong]
    get_memory.restype = ctypes.c_int
    ok = get_memory(kernel32.GetCurrentProcess(), ctypes.byref(sample), sample.cb)
    if not ok:
        raise ctypes.WinError(ctypes.get_last_error())
    return sample.WorkingSetSize, sample.PrivateUsage


def run_worker(path: Path, kind: str, rows: int, columns: int, visible: bool) -> dict:
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(CODE))

    import tkinter as tk
    import worksheets
    from MiniJMP import Minijmp
    from pandastable_local import core_orig, csv_import, import_limits

    timings: dict[str, float] = {}
    context = {"csv": None}

    def measured(name, operation):
        def call(*args, **kwargs):
            start = perf_counter()
            try:
                return operation(*args, **kwargs)
            finally:
                timings[name] = timings.get(name, 0.0) + (perf_counter() - start) * 1000
        return call

    original_task = worksheets.run_import_task

    def timed_task(parent, phase, operation, title=None):
        start = perf_counter()
        try:
            if title is None:
                return original_task(parent, phase, operation)
            return original_task(parent, phase, operation, title=title)
        finally:
            timings["background_task_wall_ms"] = timings.get("background_task_wall_ms", 0.0) + (
                perf_counter() - start
            ) * 1000

    worksheets.run_import_task = timed_task

    original_check_excel = worksheets.import_limits.check_excel
    worksheets.import_limits.check_excel = measured("excel_preflight_ms", original_check_excel)
    original_read_excel = worksheets.pd.read_excel
    worksheets.pd.read_excel = measured("excel_pandas_read_ms", original_read_excel)
    original_restore = worksheets._restore_excel_precision
    worksheets._restore_excel_precision = measured("excel_precision_restore_ms", original_restore)
    original_excel = worksheets._read_excel
    worksheets._read_excel = measured("excel_prepare_total_ms", original_excel)

    original_records = csv_import._read_records

    def timed_records(*args, **kwargs):
        stage = context["csv"] or "csv_other"
        start = perf_counter()
        try:
            return original_records(*args, **kwargs)
        finally:
            key = "csv_detect_parse_ms" if stage == "detect" else "csv_full_parse_ms"
            timings[key] = timings.get(key, 0.0) + (perf_counter() - start) * 1000

    csv_import._read_records = timed_records
    original_make_frame = csv_import._make_frame
    csv_import._make_frame = measured("csv_dataframe_and_inference_ms", original_make_frame)
    original_bounded_read = import_limits.read_csv_bounded
    import_limits.read_csv_bounded = measured("csv_chunk_read_total_ms", original_bounded_read)
    original_inference = csv_import.infer_numeric_columns
    csv_import.infer_numeric_columns = measured("csv_numeric_inference_ms", original_inference)
    from pandas.io.parsers.readers import TextFileReader
    original_get_chunk = TextFileReader.get_chunk
    TextFileReader.get_chunk = measured("csv_pandas_chunk_parse_ms", original_get_chunk)
    original_detect = core_orig.detect_csv

    def timed_detect(*args, **kwargs):
        context["csv"] = "detect"
        try:
            return measured("csv_detection_total_ms", original_detect)(*args, **kwargs)
        finally:
            context["csv"] = None

    core_orig.detect_csv = timed_detect
    original_read_csv = core_orig.read_csv

    def timed_read_csv(*args, **kwargs):
        context["csv"] = "full"
        try:
            return measured("csv_read_total_ms", original_read_csv)(*args, **kwargs)
        finally:
            context["csv"] = None

    core_orig.read_csv = timed_read_csv

    original_publish = worksheets.Worksheets._import_frames

    def timed_publish(self, *args, **kwargs):
        return measured("worksheet_publish_ms", original_publish)(self, *args, **kwargs)

    worksheets.Worksheets._import_frames = timed_publish
    errors: list[str] = []
    worksheets.messagebox.showerror = lambda title, message, **kwargs: errors.append(str(message))
    Minijmp.start_logging = lambda self: None

    root = tk.Tk()
    if not visible:
        root.withdraw()
    app = Minijmp(parent=root)
    root.update_idletasks()
    root.update()

    file_hash = _file_hash(path)
    last_tick = perf_counter()
    max_gap_ms = 0.0
    tick_id = None

    def heartbeat():
        nonlocal last_tick, max_gap_ms, tick_id
        now = perf_counter()
        max_gap_ms = max(max_gap_ms, (now - last_tick) * 1000)
        last_tick = now
        if root.winfo_exists():
            tick_id = root.after(10, heartbeat)

    tick_id = root.after(10, heartbeat)
    base_working_set, base_private = _memory_bytes()
    peak = {"working_set": base_working_set, "private": base_private}
    stop = Event()

    def sample_memory():
        while not stop.is_set():
            try:
                working_set, private = _memory_bytes()
                peak["working_set"] = max(peak["working_set"], working_set)
                peak["private"] = max(peak["private"], private)
            except Exception:
                pass
            stop.wait(0.02)

    sampler = Thread(target=sample_memory, name="f3-3-memory-sampler", daemon=True)
    sampler.start()
    start = perf_counter()
    imported = False
    shape = None
    try:
        imported = app.import_csv(filename=str(path)) if kind == "csv" else app.load_excel(str(path))
        root.update_idletasks()
        root.update()
        if imported:
            frame = app.getCurrentTable().model.df
            shape = list(frame.shape)
    finally:
        elapsed_ms = (perf_counter() - start) * 1000
        stop.set()
        sampler.join(timeout=1)
        if tick_id is not None:
            try:
                root.after_cancel(tick_id)
            except tk.TclError:
                pass
        root.destroy()

    ws_after, private_after = _memory_bytes()
    result = {
        "format": kind,
        "rows": rows,
        "columns": columns,
        "file_bytes": path.stat().st_size,
        "file_sha256": file_hash,
        "success": imported,
        "import_shape": shape,
        "first_interactive_ms": elapsed_ms,
        "main_thread_max_gap_ms": round(max_gap_ms, 2),
        "baseline_working_set_bytes": base_working_set,
        "peak_working_set_bytes": peak["working_set"],
        "working_set_increase_bytes": max(0, peak["working_set"] - base_working_set),
        "baseline_private_bytes": base_private,
        "peak_private_bytes": peak["private"],
        "private_increase_bytes": max(0, peak["private"] - base_private),
        "working_set_after_bytes": ws_after,
        "private_after_bytes": private_after,
        "errors": errors,
        "timings_ms": {key: round(value, 2) for key, value in timings.items()},
    }
    return result


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run_case(name: str, spec: tuple[str, int, int], output: Path, label: str,
             visible: bool) -> dict:
    kind, rows, columns = spec
    path = output / f"{name}.{ 'xlsx' if kind == 'excel' else 'csv' }"
    if kind == "csv":
        generate_csv(path, rows, columns)
    else:
        generate_excel(path, rows, columns)
    command = [
        sys.executable, str(Path(__file__).resolve()), "--worker", str(path),
        "--format", kind, "--rows", str(rows), "--columns", str(columns),
    ]
    if visible:
        command.append("--visible")
    proc = subprocess.run(command, capture_output=True, text=True, cwd=ROOT)
    result_line = next((line for line in reversed(proc.stdout.splitlines())
                        if line.startswith("RESULT ")), None)
    if proc.returncode or result_line is None:
        raise RuntimeError(
            f"{name} 导入进程失败（{proc.returncode}）。\n"
            f"stdout:\n{proc.stdout[-4000:]}\nstderr:\n{proc.stderr[-4000:]}"
        )
    result = json.loads(result_line[7:])
    result.update({"case": name, "label": label})
    print(json.dumps(result, ensure_ascii=False), flush=True)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=["all", *CASES], default="all")
    parser.add_argument("--output-dir", type=Path,
                        default=Path(os.environ.get("TEMP", ".")) / "minijmp-f3-3-benchmark")
    parser.add_argument("--label", default="baseline")
    parser.add_argument("--visible", action="store_true",
                        help="显示 Tk 主窗口，供一次人工观察响应")
    parser.add_argument("--worker", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--format", choices=["csv", "excel"])
    parser.add_argument("--rows", type=int)
    parser.add_argument("--columns", type=int)
    args = parser.parse_args()

    if args.worker:
        print("RESULT " + json.dumps(run_worker(
            args.worker, args.format, args.rows, args.columns, args.visible
        ), ensure_ascii=False), flush=True)
        return 0

    args.output_dir.mkdir(parents=True, exist_ok=True)
    names = list(CASES) if args.case == "all" else [args.case]
    results_path = args.output_dir / "results.jsonl"
    for name in names:
        result = run_case(name, CASES[name], args.output_dir, args.label, args.visible)
        with results_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(result, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
