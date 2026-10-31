from __future__ import annotations

import csv
import ctypes
import math
import os
import re
import struct
import subprocess
import sys
import traceback
from pathlib import Path
import winreg

import pythoncom
import win32api
import win32process
import win32com
import win32com.client


MTB_EXE = Path(r"D:\Program\Minitab 19\Mtb.exe")
DATA = (1.0, 2.0, 3.0, 4.0, 5.0, 6.0)
COMMAND = "DESCRIBE C1."


def canonical(path: str | Path) -> str:
    return os.path.normcase(os.path.realpath(os.path.abspath(path)))


def registered_server() -> tuple[str, str, str]:
    with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r"Mtb.Application\CLSID") as key:
        clsid = winreg.QueryValueEx(key, "")[0]
    with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, rf"CLSID\{clsid}\LocalServer32") as key:
        command_line = winreg.QueryValueEx(key, "")[0]
    match = re.match(r'^\s*"([^"]+)"|^\s*(\S+)', command_line)
    server_path = match.group(1) or match.group(2) if match else ""
    return clsid, server_path, command_line


def running_minitab_pids() -> list[int]:
    result = subprocess.run(
        ["tasklist.exe", "/FI", "IMAGENAME eq Mtb.exe", "/FO", "CSV", "/NH"],
        check=True,
        capture_output=True,
        text=True,
        encoding="mbcs",
        errors="replace",
    )
    return [int(row[1]) for row in csv.reader(result.stdout.splitlines())
            if len(row) >= 2 and row[0].casefold() == "mtb.exe" and row[1].isdigit()]


def file_version(path: Path) -> str:
    info = win32api.GetFileVersionInfo(str(path), "\\")
    ms, ls = info["FileVersionMS"], info["FileVersionLS"]
    return ".".join(str(part) for part in (
        win32api.HIWORD(ms), win32api.LOWORD(ms),
        win32api.HIWORD(ls), win32api.LOWORD(ls),
    ))


def process_image_path(hwnd: int) -> tuple[int, str]:
    _, pid = win32process.GetWindowThreadProcessId(hwnd)
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        raise ctypes.WinError()
    try:
        size = ctypes.c_ulong(32768)
        buffer = ctypes.create_unicode_buffer(size.value)
        if not kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            raise ctypes.WinError()
        return pid, buffer.value
    finally:
        kernel32.CloseHandle(handle)


def numeric_values(text: str) -> list[float]:
    values = []
    for token in re.findall(r"(?<![\w.])[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][-+]?\d+)?", text):
        try:
            values.append(float(token))
        except ValueError:
            pass
    return values


def nearest(values: list[float], expected: float, tolerance: float) -> float:
    matches = [value for value in values if math.isclose(value, expected, rel_tol=0, abs_tol=tolerance)]
    if not matches:
        raise AssertionError(f"Minitab 输出中未找到期望统计值 {expected} ± {tolerance}; 数值={values}")
    return min(matches, key=lambda value: abs(value - expected))


def main() -> int:
    print("=== Minitab 19 COM 自动化验证 ===")
    print(f"Python: {sys.executable}")
    print(f"Python 版本: {sys.version.split()[0]} ({struct.calcsize('P') * 8}-bit)")
    print(f"pywin32: {win32com.__file__}; pythoncom={pythoncom.__file__}")

    if not MTB_EXE.is_file():
        raise FileNotFoundError(f"指定的 Minitab 程序不存在: {MTB_EXE}")
    clsid, server_path, server_command = registered_server()
    print(f"ProgID: Mtb.Application; CLSID: {clsid}")
    print(f"COM LocalServer32: {server_command}")
    if canonical(server_path) != canonical(MTB_EXE):
        raise RuntimeError(f"Mtb.Application 注册服务器与目标程序不符: {server_path}")

    version = file_version(MTB_EXE)
    print(f"Minitab: Minitab 19 Statistical Software {version}")
    pids = running_minitab_pids()
    print(f"启动前运行中的 Mtb.exe PID: {pids or '无'}")
    if pids:
        raise RuntimeError("检测到已有 Minitab 进程。为保护用户项目，本次未连接或修改任何现有会话。")

    app = None
    project = None
    ui = None
    try:
        app = win32com.client.DispatchEx("Mtb.Application")
        pythoncom.PumpWaitingMessages()
        ui = app.UserInterface
        ui.Visible = False
        ui.UserControl = False
        ui.DisplayAlerts = False
        app_path = str(app.AppPath)
        hwnd = int(app.Handle)
        pid, image_path = process_image_path(hwnd)
        print(f"COM AppPath: {app_path}")
        print(f"COM 窗口句柄/PID: {hwnd}/{pid}")
        print(f"COM 进程映像: {image_path}")
        if canonical(app_path) != canonical(MTB_EXE) or canonical(image_path) != canonical(MTB_EXE):
            raise RuntimeError(f"COM 实例未连接到指定 Minitab 19: AppPath={app_path}; process={image_path}")

        app.New()
        project = app.ActiveProject
        if project is None:
            raise RuntimeError("Mtb.Application.ActiveProject 返回空对象")
        print(f"ActiveProject: {project.Name!r}; ActiveWorksheet: {project.ActiveWorksheet.Name!r}")

        print("访问 ActiveWorksheet.Columns ...", flush=True)
        columns = project.ActiveWorksheet.Columns
        print(f"新工作表初始 Columns.Count={int(columns.Count)}; 新建一列 ...", flush=True)
        column = columns.Add(None, None, 1)
        print(f"列对象已创建: {column.Name!r}; 设置列名 ...", flush=True)
        column.Name = "ParityProbe"
        print("设置数据 ...", flush=True)
        column.SetData(DATA, 1, len(DATA))
        print("回读数据 ...", flush=True)
        loaded = tuple(float(value) for value in column.GetData())
        print(f"写入并回读 C1: {loaded}")
        if loaded != DATA:
            raise AssertionError(f"测试数据回读不一致: {loaded}")

        project.ExecuteCommand(COMMAND)
        commands = project.Commands
        command_count = int(commands.Count)
        if command_count < 1:
            raise RuntimeError("ExecuteCommand 返回后 Commands 集合为空")
        result_command = commands.Item(command_count)
        outputs = result_command.Outputs
        output_texts = [str(outputs.Item(i).Text or "") for i in range(1, int(outputs.Count) + 1)]
        try:
            document_text = str(result_command.OutputDocument.Text or "")
            document_api = "available"
        except Exception as exc:
            document_text = ""
            document_api = f"unavailable: {type(exc).__name__}: {exc}"
        output_text = "\n".join([document_text, *output_texts]).strip()
        print(f"ExecuteCommand: {COMMAND}")
        print(f"命令对象: {result_command.Name!r}; Outputs.Count={int(outputs.Count)}")
        print(f"OutputDocument.Text: {document_api}; Output.Text 项数={len(output_texts)}")
        print("--- Minitab OutputDocument.Text / Output.Text ---")
        print(output_text or "(空)")
        if not output_text:
            raise RuntimeError("统计命令已执行，但 Minitab 返回的统计输出为空")

        numbers = numeric_values(output_text)
        expected = {
            "N": (float(len(DATA)), 1e-9),
            "Mean": (sum(DATA) / len(DATA), 0.005),
            "StDev": (math.sqrt(sum((x - sum(DATA) / len(DATA)) ** 2 for x in DATA) / (len(DATA) - 1)), 0.005),
            "Minimum": (min(DATA), 1e-9),
            "Maximum": (max(DATA), 1e-9),
        }
        extracted = {name: nearest(numbers, value, tolerance)
                     for name, (value, tolerance) in expected.items()}
        print(f"提取并核对的统计结果: {extracted}")
        print(f"独立 Python 参考: {expected}")
        print("PASS: COM 连接、统计命令、非空输出及统计值核对均通过。")
        return 0
    finally:
        column = None
        columns = None
        commands = None
        outputs = None
        result_command = None
        project = None
        app = None
        ui = None
        print("已释放独立测试项目的 COM 引用。", flush=True)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        print("FAIL: Minitab 19 COM 验证未通过。")
        traceback.print_exc()
        raise SystemExit(1)
