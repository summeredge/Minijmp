"""共享的 Minitab 19 会话与补充对标表格工具。"""
from __future__ import annotations

import csv
import math
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

PARITY = Path(__file__).resolve().parents[1]
ROOT = PARITY.parents[1]
MTB_EXE = Path(r"D:\Program\Minitab 19\Mtb.exe")
PROJECT_PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
RESULT_FIELDS = (
    "case_id", "comparison_run", "section", "term", "statistic",
    "minitab_value", "minijmp_value", "absolute_error", "relative_error",
    "absolute_tolerance", "relative_tolerance", "minitab_value_source",
    "minijmp_value_source", "status",
)

if str(PARITY) not in sys.path:
    sys.path.insert(0, str(PARITY))

from verify_doe_ccd import (  # noqa: E402
    canonical,
    capture_command_output,
    compare_values as _compare_values,
    running_minitab_pids,
)


def compare_numeric(case_id, section, term, statistic, minitab_value, minijmp_value,
                    minitab_source, minijmp_source, run="1"):
    row = _compare_values(run, section, term, statistic, minitab_value, minijmp_value,
                          minitab_source, minijmp_source)
    row["case_id"] = case_id
    row["comparison_run"] = str(row.pop("run"))
    return row


def compare_text(case_id, section, term, statistic, minitab_value, minijmp_value,
                 minitab_source, minijmp_source, run="1"):
    left, right = str(minitab_value), str(minijmp_value)
    return {
        "case_id": case_id, "comparison_run": str(run), "section": section,
        "term": term, "statistic": statistic,
        "minitab_value": left, "minijmp_value": right,
        "absolute_error": "", "relative_error": "",
        "absolute_tolerance": "", "relative_tolerance": "",
        "minitab_value_source": minitab_source,
        "minijmp_value_source": minijmp_source,
        "status": "PASS" if left == right else "FAIL",
    }


def unique_rows(rows):
    grouped = {}
    for row in rows:
        key = (row["case_id"], row["section"], row["term"], row["statistic"])
        previous = grouped.get(key)
        if previous is None:
            grouped[key] = row
            continue
        if previous["status"] != row["status"]:
            raise ValueError(f"重复比较项状态不一致: {key}")
        for field in ("minitab_value", "minijmp_value"):
            left, right = previous[field], row[field]
            try:
                left, right = float(left), float(right)
            except (TypeError, ValueError):
                if left != right:
                    raise ValueError(f"重复比较项的值不一致: {key}")
            else:
                tolerance = (
                    max(float(previous["absolute_tolerance"] or 0),
                        float(row["absolute_tolerance"] or 0))
                    + max(float(previous["relative_tolerance"] or 0),
                          float(row["relative_tolerance"] or 0))
                    * max(abs(left), abs(right))
                )
                if not math.isclose(left, right, rel_tol=0, abs_tol=tolerance):
                    raise ValueError(f"重复比较项的数值不一致: {key}")
    return list(grouped.values())


def status_counts(rows):
    counts = Counter(row["status"] for row in unique_rows(rows))
    return {name: counts[name] for name in ("PASS", "FAIL", "N/A", "UNSUPPORTED")}


def write_comparison(path, rows):
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=RESULT_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path, value):
    import json

    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                    encoding="utf-8")


class MinitabSession:
    """一个独立隐藏的 19.1.0.1 COM 项目；worker 退出时释放进程。"""

    def __init__(self):
        import ctypes
        import pythoncom
        import win32api
        import win32process
        import win32com.client

        if running_minitab_pids():
            raise RuntimeError("检测到现有 Mtb.exe；为保护用户会话，本轮不启动新实例")
        if not MTB_EXE.is_file():
            raise FileNotFoundError(MTB_EXE)
        info = win32api.GetFileVersionInfo(str(MTB_EXE), "\\")
        ms, ls = info["FileVersionMS"], info["FileVersionLS"]
        version = ".".join(str(value) for value in (
            win32api.HIWORD(ms), win32api.LOWORD(ms),
            win32api.HIWORD(ls), win32api.LOWORD(ls)))
        if version != "19.1.0.1":
            raise RuntimeError(f"要求 Minitab 19.1.0.1，实际版本 {version}")

        self.raw = []
        self.app = win32com.client.DispatchEx("Mtb.Application")
        pythoncom.PumpWaitingMessages()
        self.ui = self.app.UserInterface
        self.ui.Visible = False
        self.ui.UserControl = False
        self.ui.DisplayAlerts = False
        self.app_path = str(self.app.AppPath)
        handle = ctypes.windll.kernel32.OpenProcess(
            0x1000, False,
            win32process.GetWindowThreadProcessId(int(self.app.Handle))[1],
        )
        if not handle:
            raise ctypes.WinError()
        try:
            size = ctypes.c_ulong(32768)
            buffer = ctypes.create_unicode_buffer(size.value)
            if not ctypes.windll.kernel32.QueryFullProcessImageNameW(
                    handle, 0, buffer, ctypes.byref(size)):
                raise ctypes.WinError()
            self.process_path = buffer.value
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
        if (canonical(self.app_path) != canonical(MTB_EXE)
                or canonical(self.process_path) != canonical(MTB_EXE)):
            raise RuntimeError(
                f"COM 实例路径不符: AppPath={self.app_path}, process={self.process_path}")
        self.version = version
        self.app.New()
        self.project = self.app.ActiveProject
        self.worksheet = self.project.ActiveWorksheet

    @property
    def columns(self):
        return self.worksheet.Columns

    def new_project(self):
        self.worksheet = self.project = None
        self.app.New()
        self.project = self.app.ActiveProject
        self.worksheet = self.project.ActiveWorksheet

    def execute(self, command, label):
        before = int(self.project.Commands.Count)
        self.project.ExecuteCommand(command)
        deadline = time.monotonic() + 12
        while int(self.project.Commands.Count) <= before and time.monotonic() < deadline:
            time.sleep(.1)
        after = int(self.project.Commands.Count)
        output = (capture_command_output(self.project, after)
                  if after > before else "command object not created")
        error = str(self.app.LastError or "")
        self.raw.append(
            f"===== {label} actual command =====\n{command}\n"
            f"===== {label} OutputDocument/Outputs =====\n{output}\n"
            f"===== LastError =====\n{error}")
        if after <= before:
            raise RuntimeError(f"{label} 未创建 Minitab 命令对象: {error!r}")
        if "* ERROR *" in output.upper() or "* 错误 *" in output:
            raise RuntimeError(f"{label} 返回 Minitab 错误: {error!r}")
        return output

    def find_column(self, names, required=True):
        targets = {str(value).replace(" ", "").casefold() for value in names}
        for index in range(1, int(self.columns.Count) + 1):
            name = str(self.columns.Item(index).Name).replace(" ", "").casefold()
            if name in targets:
                return index
        if required:
            actual = [str(self.columns.Item(i).Name)
                      for i in range(1, int(self.columns.Count) + 1)]
            raise RuntimeError(f"Minitab 缺少列 {tuple(names)}；实际列={actual}")
        return None

    def column_values(self, column):
        value = self.columns.Item(column).GetData()
        values = [value] if isinstance(value, (int, float)) else list(value)
        return [None if item is None or (isinstance(item, str) and item.strip() in ("", "*"))
                else float(item) for item in values]

    def add_column(self, name, values=None):
        column = self.columns.Add(None, None, 1)
        column.Name = name
        index = int(self.columns.Count)
        if values is not None:
            column.SetData(tuple(values), 1, len(values))
        return index

    def read_matrix(self, name):
        matrices = self.worksheet.Matrices
        index = next((i for i in range(1, int(matrices.Count) + 1)
                      if str(matrices.Item(i).Name).casefold() == name.casefold()), None)
        if index is None:
            raise RuntimeError(f"Minitab 未存储矩阵 {name}")
        matrix = matrices.Item(index)
        n, p = int(matrix.RowCount), int(matrix.ColumnCount)
        flat = [float(value) for value in matrix.GetData()]
        if len(flat) != n * p:
            raise RuntimeError(f"矩阵 {name} 数据数与维度不符")
        return [[flat[column * n + row] for column in range(p)] for row in range(n)]

    def release(self):
        self.worksheet = self.project = self.ui = self.app = None


def run_worker(script, mode, timeout=360):
    if (not PROJECT_PYTHON.is_file()
            or Path(sys.executable).resolve() != PROJECT_PYTHON.resolve()):
        raise RuntimeError(f"请使用项目解释器运行: {PROJECT_PYTHON}")
    process = subprocess.run(
        [str(PROJECT_PYTHON), "-X", "utf8", str(script), mode],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
    )
    if process.stdout.strip():
        print(process.stdout.rstrip(), flush=True)
    if process.stderr.strip():
        print(process.stderr.rstrip(), file=sys.stderr, flush=True)
    if mode == "--com-worker":
        for _ in range(40):
            if not running_minitab_pids():
                break
            time.sleep(.5)
        pids = running_minitab_pids()
        if pids:
            raise RuntimeError(f"Minitab worker 结束后仍有 Mtb.exe: {pids}")
    if process.returncode:
        raise RuntimeError(f"worker {mode} 退出码 {process.returncode}")
    return process
