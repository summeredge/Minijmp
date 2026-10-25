"""Launch a packaged EXE and wait until the real MiniJMP window appears."""

import subprocess
import sys
import time
from pathlib import Path


def is_app_window(title):
    """Ignore the placeholder Tk window (literal title tk) shown before naming."""
    title = (title or '').strip()
    return 'minijmp' in title.lower() and title.lower() != 'tk'


def window_titles():
    if sys.platform != 'win32':
        raise RuntimeError('smoke_launch.py requires Windows')
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    titles = []

    callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

    def collect(hwnd, _):
        length = user32.GetWindowTextLengthW(hwnd)
        if length and user32.IsWindowVisible(hwnd):
            buffer = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buffer, length + 1)
            titles.append(buffer.value)
        return True

    user32.EnumWindows(callback_type(collect), 0)
    return titles


def wait_for_window(process, timeout, titles=window_titles, sleep=time.sleep):
    started = time.monotonic()
    seen = []
    while time.monotonic() - started < timeout:
        seen = titles()
        found = [title for title in seen if is_app_window(title)]
        if found:
            return found, time.monotonic() - started, seen
        if process.poll() is not None:
            raise RuntimeError(
                f'Process exited with code {process.returncode} before showing a window')
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
