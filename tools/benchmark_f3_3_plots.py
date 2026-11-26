"""Measure large plot rendering and repeated Tk plot-window lifecycles."""

from __future__ import annotations

import argparse
import gc
import json
import statistics
import sys
import time
import weakref
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

import matplotlib

matplotlib.use("TkAgg")

import numpy as np
import pandas as pd

from modified_table import MTable
from pandastable_local.plotting import PlotViewer
from plots import plot_viewer


SEED = 20261126
PLOT_CASES = (("scatter", 250_000), ("line", 250_000), ("histogram", 500_000))


def make_data(kind: str, count: int, rng: np.random.Generator) -> pd.DataFrame:
    if kind == "histogram":
        return pd.DataFrame({"值": rng.normal(size=count)})
    y = rng.normal(size=count)
    if kind == "line":
        y[count // 2] = 10.0
    return pd.DataFrame({"X": np.arange(count, dtype="float64"), "Y": y})


def summarize(values: list[float]) -> dict[str, float]:
    return {"median": round(statistics.median(values), 2),
            "min": round(min(values), 2), "max": round(max(values), 2)}


def run(repeats: int, lifecycle_cycles: int, visible: bool) -> dict:
    import tkinter as tk

    rng = np.random.default_rng(SEED)
    data = {kind: make_data(kind, rows, rng) for kind, rows in PLOT_CASES}
    root = tk.Tk()
    root.geometry("1000x700+20+20")
    if not visible:
        root.withdraw()
    callback_errors: list[str] = []

    def report_callback_exception(_widget, _exception, error, _traceback) -> None:
        callback_errors.append(str(error))
        root.quit()

    root.report_callback_exception = report_callback_exception
    measurements: dict[str, list[dict[str, float]]] = {kind: [] for kind, _ in PLOT_CASES}
    lifecycle = {"output_window": [], "general_plotter": []}
    weak_figures = []
    weak_canvases = []
    weak_windows = []
    max_main_gap_ms = 0.0
    last_tick = time.perf_counter()
    heartbeat_id = None
    progress = {"plot": 0, "cycle": 0}
    total_plots = len(PLOT_CASES) * (repeats + 1)

    frame = tk.Frame(root)
    frame.pack(fill="both", expand=True)
    table = MTable(frame, dataframe=pd.DataFrame({"临时列": [0]}),
                   showtoolbar=False, showstatusbar=False)
    table.show()
    root.update_idletasks()
    plot_tables = {}
    for kind, _ in PLOT_CASES:
        plot_frame = tk.Frame(root)
        current = MTable(plot_frame, dataframe=data[kind],
                         showtoolbar=False, showstatusbar=False)
        current.show()
        plot_tables[kind] = current
    root.update_idletasks()

    def heartbeat() -> None:
        nonlocal last_tick, max_main_gap_ms, heartbeat_id
        now = time.perf_counter()
        max_main_gap_ms = max(max_main_gap_ms, (now - last_tick) * 1000)
        last_tick = now
        if root.winfo_exists():
            heartbeat_id = root.after(10, heartbeat)

    def measure_plot(kind: str, count: int, trial: int) -> None:
        current = plot_tables[kind]
        open_start = time.perf_counter()
        viewer = PlotViewer(table=current)
        viewer.main.update_idletasks()
        opened = time.perf_counter()
        viewer.mplopts.tkvars["kind"].set(kind)
        viewer.mplopts.tkvars["use_index"].set(False)
        draw_times: list[float] = []
        draw = viewer.canvas.draw

        def timed_draw() -> None:
            start = time.perf_counter()
            draw()
            draw_times.append((time.perf_counter() - start) * 1000)

        viewer.canvas.draw = timed_draw
        start = time.perf_counter()
        viewer.replot(data=data[kind])
        plotted = time.perf_counter()
        if not draw_times:
            raise AssertionError(f"{kind}: expected a full TkAgg draw")
        if kind == "scatter":
            plotted_rows = len(viewer.ax.collections[0].get_offsets())
        elif kind == "line":
            line = viewer.ax.lines[0]
            plotted_rows = len(line.get_xdata())
            if line.get_ydata()[count // 2] != 10.0:
                raise AssertionError("line peak was changed")
        else:
            plotted_rows = round(sum(patch.get_height() for patch in viewer.ax.patches))
        if plotted_rows != count:
            raise AssertionError(f"{kind}: plotted {plotted_rows} rows, expected {count}")


        def refresh_and_close() -> None:
            viewer.labelopts.tkvars["title"].set(f"Refresh {trial}")
            refresh_start = time.perf_counter()
            viewer.updatePlot()
            refreshed = time.perf_counter()
            if len(draw_times) < 2:
                raise AssertionError(f"{kind}: expected a parameter refresh draw")
            if trial:
                measurements[kind].append({
                    "viewer_open_ms": (opened - open_start) * 1000,
                    "open_to_plot_ms": (plotted - open_start) * 1000,
                    "plot_to_updated_ms": (plotted - start) * 1000,
                    "artist_build_ms": max(0.0, (plotted - start) * 1000 - draw_times[0]),
                    "first_draw_ms": draw_times[0],
                    "parameter_refresh_to_updated_ms": (refreshed - refresh_start) * 1000,
                    "parameter_refresh_draw_ms": draw_times[1],
                    "full_samples": float(count),
                })
            weak_figures.append(weakref.ref(viewer.fig))
            weak_canvases.append(weakref.ref(viewer.canvas))
            weak_windows.append(weakref.ref(viewer.main))
            viewer.close()
            root.update_idletasks()
            progress["plot"] += 1
            root.after(0, next_plot)

        root.after(15, refresh_and_close)

    def measure_lifecycle() -> None:
        index = progress["cycle"]
        kind = "output_window" if index % 2 == 0 else "general_plotter"
        start = time.perf_counter()
        viewer = (plot_viewer(table=None, register=False) if kind == "output_window"
                  else PlotViewer(table=table))
        viewer.main.update_idletasks()
        opened = time.perf_counter()
        viewer.close()
        root.update_idletasks()
        closed = time.perf_counter()
        lifecycle[kind].append({"open_ms": (opened - start) * 1000,
                                "close_ms": (closed - opened) * 1000})
        weak_figures.append(weakref.ref(viewer.fig))
        weak_canvases.append(weakref.ref(viewer.canvas))
        weak_windows.append(weakref.ref(viewer.main))
        progress["cycle"] += 1
        del viewer
        if progress["cycle"] < lifecycle_cycles * 2:
            root.after(0, measure_lifecycle)
        else:
            root.after(20, finish)

    def finish() -> None:
        nonlocal heartbeat_id
        if heartbeat_id is not None:
            try:
                root.after_cancel(heartbeat_id)
            except tk.TclError:
                pass
            heartbeat_id = None
        gc.collect()
        result["resources"] = {
            "remaining_toplevels": sum(isinstance(widget, tk.Toplevel)
                                       for widget in root.winfo_children()),
            "pending_after_callbacks": len(root.tk.call("after", "info")),
            "live_figures_canvases_windows": [
                sum(ref() is not None for ref in refs)
                for refs in (weak_figures, weak_canvases, weak_windows)],
        }
        root.quit()

    def next_plot() -> None:
        if progress["plot"] >= total_plots:
            root.after(0, measure_lifecycle)
            return
        case, trial = divmod(progress["plot"], repeats + 1)
        kind, count = PLOT_CASES[case]
        measure_plot(kind, count, trial)
        return

    result: dict = {}
    root.after(0, heartbeat)
    root.after(0, next_plot)
    root.mainloop()
    if callback_errors:
        root.destroy()
        raise RuntimeError("Tk callback errors: " + "; ".join(callback_errors))
    root.destroy()

    result.update({
        "seed": SEED,
        "python": sys.version.split()[0],
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "matplotlib": matplotlib.__version__,
        "visible": visible,
        "repeats_after_warmup": repeats,
        "main_thread_max_gap_ms": round(max_main_gap_ms, 2),
        "plots": {
            kind: {
                "rows": rows,
                **{metric: summarize([sample[metric] for sample in values])
                   for metric in ("viewer_open_ms", "open_to_plot_ms", "plot_to_updated_ms",
                                  "artist_build_ms", "first_draw_ms",
                                  "parameter_refresh_to_updated_ms", "parameter_refresh_draw_ms")},
            }
            for (kind, rows), values in zip(PLOT_CASES, measurements.values())
        },
        "lifecycle": {
            kind: {
                "cycles": len(values),
                "open_ms": summarize([sample["open_ms"] for sample in values]),
                "close_ms": summarize([sample["close_ms"] for sample in values]),
            }
            for kind, values in lifecycle.items()
        },
    })
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=3,
                        help="measured repetitions after one warmup")
    parser.add_argument("--lifecycle-cycles", type=int, default=25,
                        help="open/close cycles per plot window type")
    parser.add_argument("--visible", action="store_true")
    args = parser.parse_args()
    if args.repeats < 1 or args.lifecycle_cycles < 1:
        parser.error("repeats and lifecycle-cycles must be positive")
    print(json.dumps(run(args.repeats, args.lifecycle_cycles, args.visible),
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
