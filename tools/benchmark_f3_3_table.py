"""Measure large worksheet display, edits, filtering, sorting, and history in Tk."""

from __future__ import annotations

import argparse
import gc
import json
from pathlib import Path
import sys
from threading import Event, Thread
from time import perf_counter


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "code"))
sys.path.insert(0, str(ROOT / "tools"))

from benchmark_f3_3 import _memory_bytes


def make_frame(rows: int, columns: int):
    import numpy as np
    import pandas as pd

    values = np.random.default_rng(20261126).permutation(rows).astype("int64")
    return pd.DataFrame({f"C{column + 1}": values + column * rows
                         for column in range(columns)})


def run(rows: int, columns: int, visible: bool) -> dict:
    import tkinter as tk
    import pandas as pd
    from MiniJMP import Minijmp

    callback_errors = []
    measurements = []
    Minijmp.start_logging = lambda self: None
    root = tk.Tk()
    if not visible:
        root.withdraw()
    root.report_callback_exception = lambda *args: callback_errors.append(str(args[1]))
    app = Minijmp(parent=root)
    frame = make_frame(rows, columns)
    small = pd.DataFrame({"小表": [1, 2, 3]})
    frame_bytes = int(frame.memory_usage(index=True, deep=True).sum())
    root.update_idletasks()
    root.update()

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

    sampler = Thread(target=sample_memory, name="f3-3-table-memory", daemon=True)
    sampler.start()
    snapshot_depth = 0
    store_times = []
    loaded_shape = None
    final_shape = None
    history_count = 0
    table = None

    def measure(name, operation):
        gc.collect()
        working_before, private_before = _memory_bytes()
        start = perf_counter()
        result = operation()
        root.update_idletasks()
        root.update()
        elapsed = (perf_counter() - start) * 1000
        working_after, private_after = _memory_bytes()
        peak["working_set"] = max(peak["working_set"], working_after)
        peak["private"] = max(peak["private"], private_after)
        measurements.append({
            "operation": name,
            "milliseconds": round(elapsed, 2),
            "working_set_change_bytes": working_after - working_before,
            "private_change_bytes": private_after - private_before,
        })
        if callback_errors:
            raise RuntimeError("Tk callback error: " + "; ".join(callback_errors))
        return result

    try:
        measure("first_show_and_publish", lambda: app._import_frames(
            {"切换表": small, "大型表": frame}))
        table = app.getCurrentTable()
        loaded_shape = list(table.model.df.shape)

        measure("vertical_scroll", lambda: table.yview_moveto(0.75))
        measure("horizontal_scroll", lambda: table.xview_moveto(0.75))
        measure("locate_last_cell", lambda: table.movetoSelection(
            row=rows - 1, col=columns - 1))
        measure("visible_redraw", table.redraw)
        measure("switch_to_small_sheet", lambda: app.nb.select(app.sheetframes["切换表"]))
        measure("switch_to_large_sheet", lambda: app.nb.select(app.sheetframes["大型表"]))

        store = table.storeCurrent

        def timed_store():
            start = perf_counter()
            result = store()
            store_times.append((perf_counter() - start) * 1000)
            return result

        table.storeCurrent = timed_store
        measure("undo_snapshot", table.storeCurrent)
        snapshot_depth = len(table.prevdf)
        table.prevdf = None
        table.prevdf_end = 0
        gc.collect()

        def edit_cell():
            table.yview_moveto(0)
            table.xview_moveto(0)
            table.redraw()
            table.drawCellEntry(0, 0)
            table.cellentryvar.set(str(int(table.model.df.iat[0, 0]) + 1))
            table.handleCellEntry(0, 0)

        measure("single_cell_edit", edit_cell)
        measure("undo", table.undo)
        measure("redo", table.redo)

        def sort_table():
            table.sortTable(columnIndex=0, ascending=True)

        measure("sort", sort_table)

        def filter_table():
            table.queryBar()
            query = table.qframe
            query.queryvar.set(f"C1 >= {rows // 2}")
            query.query()
            return query

        query = measure("filter", filter_table)
        measure("clear_filter", query.close)

        clipboard = {"text": ""}
        table.clipboard_clear = lambda: clipboard.update(text="")
        table.clipboard_append = lambda value: clipboard.update(text=value)
        table.clipboard_get = lambda: clipboard["text"]

        def copy_paste_small_range():
            assert table.copy_context_selection([0, 1], [0, 1])
            assert table.paste_context_selection("cell", [3, 4], [3, 4])

        measure("copy_paste_2x2", copy_paste_small_range)

        def formula_recompute():
            table.assign_formula("Derived", "C1 * 2")
            table.drawCellEntry(0, 0)
            table.cellentryvar.set(str(int(table.model.df.iat[0, 0]) + 1))
            table.handleCellEntry(0, 0)
            if table.model.df["Derived"].iloc[0] != table.model.df["C1"].iloc[0] * 2:
                raise AssertionError("公式重算结果不正确")

        measure("formula_assign_and_recompute", formula_recompute)
    finally:
        stop.set()
        sampler.join(timeout=1)
        if tick_id is not None:
            try:
                root.after_cancel(tick_id)
            except tk.TclError:
                pass
        if app.sheets:
            table = app.getCurrentTable()
            final_shape = list(table.model.df.shape)
            history_count = len(table.prevdf or [])
        if root.winfo_exists():
            root.destroy()

    return {
        "rows": rows,
        "columns": columns,
        "seed": 20261126,
        "dataframe_bytes": frame_bytes,
        "import_shape": loaded_shape,
        "final_shape": final_shape,
        "max_main_thread_gap_ms": round(max_gap_ms, 2),
        "baseline_working_set_bytes": base_working_set,
        "peak_working_set_bytes": peak["working_set"],
        "peak_working_set_increase_bytes": max(0, peak["working_set"] - base_working_set),
        "baseline_private_bytes": base_private,
        "peak_private_bytes": peak["private"],
        "peak_private_increase_bytes": max(0, peak["private"] - base_private),
        "undo_snapshot_depth": snapshot_depth,
        "final_undo_history_count": history_count,
        "store_current_ms": [round(value, 2) for value in store_times],
        "operations": measurements,
        "callback_errors": callback_errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=100_000)
    parser.add_argument("--columns", type=int, default=20)
    parser.add_argument("--visible", action="store_true")
    args = parser.parse_args()
    if (args.rows < 1 or not 1 <= args.columns <= 16_384
            or args.rows * args.columns > 10_000_000):
        parser.error("需要正行数、1–16384 列，且总单元格数不超过 1000 万。")
    print(json.dumps(run(args.rows, args.columns, args.visible), ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
