"""Launch a packaged EXE and wait until the real MiniJMP window appears."""

import subprocess
import sys
import time
from pathlib import Path


def is_app_window(title):
    """Ignore the placeholder Tk window (literal title tk) shown before naming."""
    title = (title or '').strip()
    return 'minijmp' in title.lower() and title.lower() != 'tk'


def process_tree(process_id):
    import ctypes
    from ctypes import wintypes

    class ProcessEntry(ctypes.Structure):
        _fields_ = [('dwSize', wintypes.DWORD), ('cntUsage', wintypes.DWORD),
                    ('th32ProcessID', wintypes.DWORD), ('th32DefaultHeapID', ctypes.c_size_t),
                    ('th32ModuleID', wintypes.DWORD), ('cntThreads', wintypes.DWORD),
                    ('th32ParentProcessID', wintypes.DWORD), ('pcPriClassBase', wintypes.LONG),
                    ('dwFlags', wintypes.DWORD), ('szExeFile', wintypes.WCHAR * 260)]

    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateToolhelp32Snapshot.argtypes = (wintypes.DWORD, wintypes.DWORD)
    kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel.Process32FirstW.argtypes = kernel.Process32NextW.argtypes = (
        wintypes.HANDLE, ctypes.POINTER(ProcessEntry))
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    snapshot = kernel.CreateToolhelp32Snapshot(2, 0)
    if snapshot == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    parents = {}
    try:
        entry = ProcessEntry()
        entry.dwSize = ctypes.sizeof(entry)
        more = kernel.Process32FirstW(snapshot, ctypes.byref(entry))
        while more:
            parents[entry.th32ProcessID] = entry.th32ParentProcessID
            more = kernel.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel.CloseHandle(snapshot)
    result = {process_id}
    while True:
        children = {pid for pid, parent in parents.items() if parent in result}
        if children <= result:
            return result
        result.update(children)


def window_titles(process_id):
    if sys.platform != 'win32':
        raise RuntimeError('smoke_launch.py requires Windows')
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL('user32', use_last_error=True)
    titles = []
    process_ids = process_tree(process_id)

    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows.argtypes = (callback_type, wintypes.LPARAM)
    user32.EnumWindows.restype = wintypes.BOOL
    user32.GetWindowTextLengthW.argtypes = (wintypes.HWND,)
    user32.GetWindowTextLengthW.restype = ctypes.c_int
    user32.GetWindowTextW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
    user32.GetWindowTextW.restype = ctypes.c_int
    user32.IsWindowVisible.argtypes = (wintypes.HWND,)
    user32.IsWindowVisible.restype = wintypes.BOOL
    user32.GetWindowThreadProcessId.argtypes = (
        wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD

    def collect(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            owner = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
            if owner.value not in process_ids:
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            if not length:
                return True
            buffer = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buffer, length + 1)
            titles.append(buffer.value)
        return True

    callback = callback_type(collect)
    user32.EnumWindows(callback, 0)
    return titles


def wait_for_window(process, timeout, titles=window_titles, sleep=time.sleep):
    started = time.monotonic()
    seen = []
    while time.monotonic() - started < timeout:
        if process.poll() is not None:
            raise RuntimeError(
                f'Process exited with code {process.returncode} before showing a window')
        seen = titles(process.pid)
        found = [title for title in seen if is_app_window(title)]
        if found:
            if process.poll() is not None:
                raise RuntimeError(
                    f'Process exited with code {process.returncode} before showing a window')
            return found, time.monotonic() - started, seen
        sleep(1)
    return [], time.monotonic() - started, seen


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) not in (1, 2):
        print('Usage: smoke_launch.py EXE [TIMEOUT_SECONDS]', file=sys.stderr)
        return 2
    executable = Path(argv[0])
    timeout = float(argv[1]) if len(argv) == 2 else 90.0
    if not executable.is_file():
        print(f'ERROR: not found: {executable}', file=sys.stderr)
        return 2

    process = subprocess.Popen([str(executable)], cwd=executable.parent)
    try:
        found, elapsed, seen = wait_for_window(process, timeout)
    except RuntimeError as error:
        print(f'ERROR: {error}', file=sys.stderr)
        return 1
    finally:
        if process.poll() is None:
            subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            if process.poll() is None:
                process.terminate()
        try:
            process.wait(10)
        except subprocess.TimeoutExpired:
            process.kill()

    if not found:
        print(f'no MiniJMP window after {elapsed:.0f}s: {seen}')
        return 1
    print(f'window after {elapsed:.0f}s: {found}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
