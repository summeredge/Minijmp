"""Measure real .dexpl saves and opens across separate MiniJMP processes."""

from __future__ import annotations

import argparse
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
from threading import Event, Thread
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "code"), str(ROOT / "tools")]

SEED = 20261126
LARGE_ROWS = 150_000


def make_large_frame(rows: int):
    import numpy as np
    import pandas as pd

    rng = np.random.default_rng(SEED)
    positions = np.arange(rows)
    columns = {
        "C1": positions.astype("int64"),
        "C2": rng.normal(size=rows),
        "C3": pd.Categorical([f"组{i % 12}" for i in range(rows)]),
        "C4": pd.date_range("2025-01-01", periods=rows, freq="min"),
        "C5": pd.Series([None if i % 997 == 0 else f"样本-{i % 1000}"
                          for i in range(rows)], dtype=object),
        "C6": pd.array([None if i % 211 == 0 else i % 10000
                        for i in range(rows)], dtype="Int64"),
    }
    for column in range(7, 21):
        if column % 2:
            columns[f"C{column}"] = rng.integers(0, 100_000, size=rows, dtype="int64")
        else:
            columns[f"C{column}"] = rng.normal(size=rows)
    return pd.DataFrame(columns)


def make_doe():
    from doe_core import DesignSpec, FactorSpec
    from doe_taguchi import create_taguchi
    from doe_taguchi_arrays import ARRAYS

    array = ARRAYS["L4(2^3)"]
    factors = tuple(FactorSpec(
        key, key, None, None, factor_type="categorical",
        levels=("低", "高"), level_type="text") for key in "ABC")
    spec = DesignSpec(
        "F3-3-project-benchmark", factors, ("Y",), seed=SEED,
        design_type="taguchi",
        taguchi={"kind": "static", "array_id": array.array_id,
                 "matrix_sha256": array.sha256,
                 "columns": {key: index for index, key in enumerate("ABC", 1)},
                 "noise_array_id": None, "noise_matrix_sha256": None,
                 "noise_columns": {}, "signal_factor": None})
    frame, metadata = create_taguchi(spec, replicates=2)
    signs = {"低": -1, "高": 1}
    frame["响应_Y"] = [
        sum(signs[row[f"设定_{key}"]] * (i + 1)
            for i, key in enumerate("ABC"))
        for _, row in frame.iterrows()]
    return frame, metadata


def make_results(source: str, count: int) -> list[dict]:
    import numpy as np
    from matplotlib.figure import Figure

    from project_results import figure_png, report_block
    from stat_table import StatTable

    x = np.arange(1000)
    records = []
    for index in range(count):
        figure = Figure(figsize=(6, 4), dpi=90)
        axis = figure.add_subplot(111)
        axis.plot(x, np.sin(x / (20 + index)) + index)
        axis.set_title(f"历史图形 {index + 1}")
        png = figure_png(figure)
        table = StatTable(
            title=f"描述性统计 {index + 1}",
            headers=["列", "样本数", "均值", "标准差"],
            values=[[f"C{column}", LARGE_ROWS, column / 10, column / 100]
                    for column in range(1, 25)])
        records.append({
            "source": source,
            "source_label": source,
            "title": f"分析记录 {index + 1}",
            "time": f"2026-11-26 12:{index:02d}:00",
            "columns": ["C1", "C2"],
            "parameters": {"样本量": str(LARGE_ROWS), "固定种子": str(SEED)},
            "blocks": [
                {"text": f"分析摘要 {index + 1}\n" + "结果说明。" * 80},
                report_block(table, "\n"),
                {"text": "附加诊断。" * 120},
            ],
            "png": png,
        })
    return records


def _memory_bytes() -> tuple[int, int]:
    from benchmark_f3_3 import _memory_bytes as read_memory

    return read_memory()


def _start_memory_sampler():
    baseline = _memory_bytes()
    peak = [baseline[0], baseline[1]]
    stop = Event()

    def sample() -> None:
        while not stop.is_set():
            working, private = _memory_bytes()
            peak[0] = max(peak[0], working)
            peak[1] = max(peak[1], private)
            stop.wait(0.02)

    sampler = Thread(target=sample, name="f3-3-project-memory", daemon=True)
    sampler.start()
    return baseline, peak, stop, sampler


def _timed(target, name: str, key: str, timings: dict[str, float]) -> None:
    original = getattr(target, name)

    def call(*args, **kwargs):
        start = perf_counter()
        try:
            return original(*args, **kwargs)
        finally:
            timings[key] = timings.get(key, 0.0) + (perf_counter() - start) * 1000

    setattr(target, name, call)


def _instrument(worksheets, timings: dict[str, float]) -> None:
    for name, key in (
        ("_write_frame", "write_frame_ms"), ("_read_frame", "read_frame_ms"),
        ("write_project_file", "zip_write_ms"), ("read_project_file", "archive_read_ms"),
        ("write_results", "results_write_ms"), ("read_results", "results_read_ms"),
    ):
        _timed(worksheets, name, key, timings)
    for name, key in (
        ("_state", "saved_state_pickle_ms"), ("_payload", "payload_ms"),
        ("_replace", "widget_replace_ms"), ("_make_sheet", "sheet_widget_ms"),
    ):
        _timed(worksheets.Worksheets, name, key, timings)


def _new_app(visible: bool):
    import tkinter as tk

    from MiniJMP import Minijmp

    Minijmp.start_logging = lambda self: None
    root = tk.Tk()
    if not visible:
        root.withdraw()
    errors = []
    root.report_callback_exception = lambda _type, error, _trace: errors.append(str(error))
    app = Minijmp(parent=root)
    root.update_idletasks()
    root.update()
    return root, app, errors


def save_worker(filename: Path, visible: bool) -> dict:
    import numpy as np
    import pandas as pd
    import worksheets
    from result_navigation import ResultNavigation

    with redirect_stdout(io.StringIO()):
        root, app, gui_errors = _new_app(visible)
        main = make_large_frame(LARGE_ROWS)
        app.table.model.df = main
        app.table.redraw()
        assert app.renameSheet("大型数据")
        app.table.define_formula("计算列", "C1 * 2")
        app.addSheet("普通工作表一", pd.DataFrame({
            "序号": np.arange(30_000, dtype="int64"),
            "测量值": np.linspace(0, 1, 30_000),
            "分组": pd.Categorical([f"批次{i % 6}" for i in range(30_000)]),
        }))
        app.addSheet("普通工作表二", pd.DataFrame({
            "样本": [f"项目-{i % 500}" for i in range(20_000)],
            "计数": np.arange(20_000, dtype="int64"),
        }))
        doe_frame, doe_meta = make_doe()
        app.addSheet("Taguchi DOE", doe_frame, meta={"doe": doe_meta})
        app.project_results = make_results("大型数据", 8)
        app.nb.select(app.sheetframes["大型数据"])
        app._sheet_changed()
        nav = app.result_navigation = ResultNavigation(app)
        nav.pack(side="left", fill="y", before=app.nb)
        nav.selected = app.project_results[2]
        nav.refresh()
        root.update_idletasks()

        timings: dict[str, float] = {}
        _instrument(worksheets, timings)
        baseline, peak, stop, sampler = _start_memory_sampler()
        outcome = {"saved": False}

        def save() -> None:
            start = perf_counter()
            outcome["saved"] = app._save_project(filename)
            outcome["save_total_ms"] = (perf_counter() - start) * 1000
            outcome["file_bytes"] = filename.stat().st_size if filename.exists() else 0
            root.after_idle(root.quit)

        root.after(0, save)
        root.mainloop()
        stop.set()
        sampler.join(timeout=1)
        result = {
            **outcome,
            "timings": timings,
            "working_set_increase_bytes": max(0, peak[0] - baseline[0]),
            "private_increase_bytes": max(0, peak[1] - baseline[1]),
            "data_shapes": {name: list(table.model.df.shape)
                            for name, table in app.sheets.items()},
            "results": len(app.project_results),
            "gui_errors": gui_errors,
        }
        root.destroy()
        return result


def open_worker(filename: Path, export_path: Path, visible: bool) -> dict:
    import worksheets
    from result_navigation import ResultNavigation

    with redirect_stdout(io.StringIO()):
        root, app, gui_errors = _new_app(visible)
        timings: dict[str, float] = {}
        _instrument(worksheets, timings)
        baseline, peak, stop, sampler = _start_memory_sampler()
        outcome = {"opened": False}
        started = perf_counter()

        def finish_open() -> None:
            try:
                root.update_idletasks()
                outcome["first_interactive_ms"] = (perf_counter() - started) * 1000
                working, private = _memory_bytes()
                outcome["open_peak_working_set_increase_bytes"] = max(
                    0, max(peak[0], working) - baseline[0])
                outcome["open_peak_private_increase_bytes"] = max(
                    0, max(peak[1], private) - baseline[1])
                large = app.sheets["大型数据"]
                normal_one = app.sheets["普通工作表一"]
                normal_two = app.sheets["普通工作表二"]
                doe = app.sheets["Taguchi DOE"]
                outcome["large_shape"] = list(large.model.df.shape)
                outcome["large_dtypes"] = {
                    name: str(large.model.df[name].dtype)
                    for name in ("C1", "C3", "C4", "C5", "C6")}
                outcome["formula"] = large.formulas["计算列"]["expression"]
                outcome["formula_value"] = int(large.model.df["计算列"].iloc[1])
                outcome["doe_type"] = doe.doe_metadata["design"]["design_type"]
                outcome["doe_array"] = doe.doe_metadata["design"]["taguchi"]["array_id"]
                outcome["doe_response_count"] = int(doe.model.df["响应_Y"].notna().sum())
                outcome["normal_shapes"] = [list(normal_one.model.df.shape),
                                             list(normal_two.model.df.shape)]
                outcome["normal_last_values"] = [
                    int(normal_one.model.df["序号"].iloc[-1]),
                    int(normal_two.model.df["计数"].iloc[-1])]
                outcome["normal_category_dtype"] = str(normal_one.model.df["分组"].dtype)
                outcome["active_sheet"] = app.getCurrentSheet()
                outcome["results"] = len(app.project_results)
                outcome["plot_snapshots"] = sum("png" in record for record in app.project_results)
                outcome["sources_match"] = all(
                    record["source"] == "大型数据" for record in app.project_results)
                nav = app.result_navigation
                outcome["navigation_visible"] = bool(nav.winfo_manager())
                outcome["navigation_selection"] = app.project_results.index(nav.selected)

                report_item = next(item for item, (record, kind) in nav.by_item.items()
                                   if record is app.project_results[2] and kind is None)
                nav.tree.selection_set(report_item)
                nav._selection_changed()
                report = nav.open_selected()
                try:
                    outcome["report_table_values"] = report.table_blocks[0].table.values[0]
                    outcome["report_table_display"] = report.table_blocks[0].table.display[0]
                    report_path = export_path.with_suffix(".txt")
                    report.save(report_path)
                    outcome["report_export_bytes"] = report_path.stat().st_size
                    outcome["report_export_contains_display"] = (
                        "150000.000" in report_path.read_text(encoding="utf-8"))
                finally:
                    report.close()

                plot_item = next(item for item, (record, kind) in nav.by_item.items()
                                 if record is app.project_results[2] and kind == "plot")
                nav.tree.selection_set(plot_item)
                nav._selection_changed()
                history_plot = nav.open_selected()
                try:
                    history_plot.savePlot(export_path)
                    outcome["history_export_bytes"] = export_path.stat().st_size
                    outcome["history_export_png"] = export_path.read_bytes().startswith(b"\x89PNG")
                finally:
                    history_plot.close()

                checks = {
                    "sheet_count": len(app.sheets) == 4,
                    "large_shape": outcome["large_shape"] == [LARGE_ROWS, 21],
                    "dtypes": outcome["large_dtypes"] == {
                        "C1": "int64", "C3": "category", "C4": "datetime64[us]",
                        "C5": "object", "C6": "Int64"},
                    "formula": outcome["formula"] == "C1 * 2" and outcome["formula_value"] == 2,
                    "normal_sheets": outcome["normal_shapes"] == [[30_000, 3], [20_000, 2]]
                    and outcome["normal_last_values"] == [29_999, 19_999]
                    and outcome["normal_category_dtype"] == "category",
                    "doe": outcome["doe_type"] == "taguchi"
                    and outcome["doe_array"] == "L4(2^3)"
                    and outcome["doe_response_count"] == 8,
                    "active_sheet": outcome["active_sheet"] == "大型数据",
                    "results": outcome["results"] == 8 and outcome["sources_match"],
                    "plots": outcome["plot_snapshots"] == 8 and outcome["history_export_png"],
                    "navigation": outcome["navigation_visible"]
                    and outcome["navigation_selection"] == 2,
                    "report": outcome["report_table_values"] == ["C1", LARGE_ROWS, 0.1, 0.01]
                    and outcome["report_table_display"] == [
                        "C1", "150000.000", "0.100", "0.010"]
                    and outcome["report_export_bytes"] > 0
                    and outcome["report_export_contains_display"],
                }
                outcome["semantic_checks"] = checks
                outcome["opened"] = all(checks.values()) and not gui_errors
            except Exception as error:
                outcome["validation_error"] = repr(error)
            finally:
                root.after_idle(root.quit)

        def load() -> None:
            load_started = perf_counter()
            outcome["load_ok"] = app.load_file(filename)
            outcome["open_total_ms"] = (perf_counter() - load_started) * 1000
            root.after_idle(finish_open)

        root.after(0, load)
        root.mainloop()
        stop.set()
        sampler.join(timeout=1)
        result = {
            **outcome,
            "timings": timings,
            "working_set_increase_bytes": outcome.get(
                "open_peak_working_set_increase_bytes", max(0, peak[0] - baseline[0])),
            "private_increase_bytes": outcome.get(
                "open_peak_private_increase_bytes", max(0, peak[1] - baseline[1])),
            "gui_errors": gui_errors,
        }
        root.destroy()
        return result


def _worker(args) -> None:
    filename = args.file.resolve()
    if args.phase == "save":
        result = save_worker(filename, args.visible)
    else:
        result = open_worker(filename, args.export.resolve(), args.visible)
    print(json.dumps(result, ensure_ascii=False))


def _invoke_worker(phase: str, filename: Path, export: Path, visible: bool) -> dict:
    command = [sys.executable, str(Path(__file__).resolve()), "--worker",
               "--phase", phase, "--file", str(filename), "--export", str(export)]
    if visible:
        command.append("--visible")
    completed = subprocess.run(command, cwd=ROOT, capture_output=True,
                               text=True, timeout=300)
    if completed.returncode:
        raise RuntimeError(
            f"{phase} worker failed ({completed.returncode}):\n{completed.stderr}\n{completed.stdout}")
    output_lines = [line for line in completed.stdout.splitlines() if line.strip()]
    try:
        return json.loads(output_lines[-1])
    except (IndexError, json.JSONDecodeError) as error:
        raise RuntimeError(
            f"{phase} worker returned invalid output:\n{completed.stdout}\n{completed.stderr}") from error


def _summary(values: list[float]) -> dict[str, float]:
    return {"median": round(statistics.median(values), 2),
            "min": round(min(values), 2), "max": round(max(values), 2)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--phase", choices=("save", "open"))
    parser.add_argument("--file", type=Path)
    parser.add_argument("--export", type=Path, default=Path("history.png"))
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--visible", action="store_true")
    args = parser.parse_args()
    if args.worker:
        if args.phase is None or args.file is None:
            parser.error("worker mode requires --phase and --file")
        _worker(args)
        return
    if args.repeats < 1:
        parser.error("repeats must be positive")
    runs = []
    for _ in range(args.repeats):
        with tempfile.TemporaryDirectory(prefix="minijmp-f3-3-project-") as directory:
            target = Path(directory) / "large-project.dexpl"
            export_path = Path(directory) / "history.png"
            save = _invoke_worker("save", target, export_path, args.visible)
            opened = _invoke_worker("open", target, export_path, args.visible)
            if not save["saved"] or not opened.get("load_ok") or not opened["opened"]:
                raise RuntimeError(json.dumps({"save": save, "open": opened}, ensure_ascii=False))
            runs.append({"save": save, "open": opened})

    print(json.dumps({
        "seed": SEED,
        "python": sys.version.split()[0],
        "pandas": __import__("pandas").__version__,
        "repeats": args.repeats,
        "runs": runs,
        "summary": {
            "file_mib": _summary([run["save"]["file_bytes"] / 1024**2 for run in runs]),
            "save_ms": _summary([run["save"]["save_total_ms"] for run in runs]),
            "open_ms": _summary([run["open"]["open_total_ms"] for run in runs]),
            "open_to_first_interactive_ms": _summary([
                run["open"]["first_interactive_ms"] for run in runs]),
            "save_peak_working_set_mib": _summary([
                run["save"]["working_set_increase_bytes"] / 1024**2 for run in runs]),
            "open_peak_working_set_mib": _summary([
                run["open"]["working_set_increase_bytes"] / 1024**2 for run in runs]),
        },
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
