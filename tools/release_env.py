"""Report whether the current interpreter can build the Windows release."""

import importlib.metadata as metadata
import struct
import subprocess
import sys
from pathlib import Path


MIN_PYTHON = (3, 11)
LOCKED_PYINSTALLER = '6.22.3'
ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / 'packaging' / 'windows' / 'requirements-py311.lock'


def lock_mismatches(lock=LOCK, installed=None):
    installed = installed or metadata.version
    differences = []
    for line in Path(lock).read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if '==' not in line or line.startswith('#'):
            continue
        name, version = (part.strip() for part in line.split('==', 1))
        try:
            have = installed(name)
        except metadata.PackageNotFoundError:
            have = 'missing'
        if have != version:
            differences.append(f'{name}=={version} (have {have})')
    return differences


def _pyinstaller_version():
    try:
        return metadata.version('pyinstaller')
    except metadata.PackageNotFoundError:
        return 'missing'


def _pip_check():
    return subprocess.run([sys.executable, '-m', 'pip', 'check'],
                          capture_output=True).returncode == 0


def assess(version_info=None, lock=LOCK, installed=None, pyinstaller=None,
           pip_ok=None, bits=None):
    version_info = tuple(version_info or sys.version_info)
    display = '.'.join(str(item) for item in version_info[:3])
    # ASCII output keeps PowerShell 5.1 pipes readable; the PS scripts add Chinese.
    if version_info[:2] < MIN_PYTHON:
        return [('BLOCKED', f'Python {display} is below the required 3.11.')]
    levels = [('PASS', f'Python {display} satisfies >= 3.11.')]

    bits = struct.calcsize('P') * 8 if bits is None else bits
    levels.append(('PASS' if bits == 64 else 'BLOCKED', f'Interpreter is {bits}-bit.'))

    differences = lock_mismatches(lock, installed)
    if not differences:
        levels.append(('PASS', f'Installed dependencies match {Path(lock).name}.'))
    elif version_info[:2] == MIN_PYTHON:
        levels.append(('BLOCKED',
                       f'Python {display} does not match the lock file: '
                       + '; '.join(differences)))
    else:
        # The lock pins a Python 3.11 environment; newer interpreters record drift.
        levels.append(('WARNING', f'Lock file is a Python 3.11 artifact; Python {display} '
                                  'differences recorded only: ' + '; '.join(differences)))

    pip_ok = _pip_check() if pip_ok is None else pip_ok
    levels.append(('PASS' if pip_ok else 'BLOCKED', 'python -m pip check passed.'
                   if pip_ok else 'python -m pip check reported dependency conflicts.'))

    pyinstaller = _pyinstaller_version() if pyinstaller is None else pyinstaller
    levels.append(('PASS' if pyinstaller == LOCKED_PYINSTALLER else 'BLOCKED',
                   f'PyInstaller {pyinstaller} (expected {LOCKED_PYINSTALLER}).'))
    return levels


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    lock = Path(argv[0]) if argv else LOCK
    blocked = 0
    for level, message in assess(lock=lock):
        print(f'{level}: {message}')
        blocked += level == 'BLOCKED'
    return 1 if blocked else 0


if __name__ == '__main__':
    raise SystemExit(main())
