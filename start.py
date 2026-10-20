import ctypes
import os
from pathlib import Path
import subprocess
import sys


def main():
    code_dir = Path(__file__).resolve().parent / 'code'
    try:
        result = subprocess.run(
            [sys.executable, str(code_dir / 'MiniJMP.py')],
            cwd=code_dir, stderr=subprocess.PIPE, text=True, errors='replace')
        returncode, error = result.returncode, result.stderr
    except OSError as exc:
        returncode, error = 1, str(exc)

    if error and sys.stderr is not None:
        print(error, file=sys.stderr, end='')
    if returncode:
        message = f'Minijmp exited with code {returncode}.\nPython: {sys.executable}\n\n{error}'
        if os.name == 'nt':
            # The VBS launcher hides the console, including stderr.
            ctypes.windll.user32.MessageBoxW(None, message, 'Minijmp startup error', 0x10)
        elif sys.stderr is not None:
            print(message, file=sys.stderr)
    return returncode


if __name__ == '__main__':
    sys.exit(main())
