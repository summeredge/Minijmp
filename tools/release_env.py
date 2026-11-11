"""Report whether the current interpreter can build the Windows release."""

import argparse
import hashlib
import importlib.metadata as metadata
import json
import re
import struct
import subprocess
import sys
import uuid
from pathlib import Path


MIN_PYTHON = (3, 11)
LOCKED_PYINSTALLER = '6.22.3'
ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / 'packaging' / 'windows' / 'requirements-py311.lock'
HASH_LOCK = ROOT / 'packaging' / 'windows' / 'requirements-py311-hashed.lock'


def _key(name):
    return re.sub(r'[-_.]+', '-', name).lower()


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


def hash_lock_mismatches(lock=LOCK, hash_lock=HASH_LOCK):
    """Check that each version pin has at least one well-formed SHA-256 hash."""
    expected = {}
    issues = []
    for number, line in enumerate(Path(lock).read_text(encoding='utf-8').splitlines(), 1):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if '==' not in line:
            issues.append(f'{Path(lock).name}:{number} is not a name==version pin')
            continue
        name, version = (part.strip() for part in line.split('==', 1))
        key = _key(name)
        if key in expected:
            issues.append(f'{Path(lock).name} repeats {name}')
        expected[key] = (name, version)

    try:
        secured = hash_lock_entries(hash_lock)
    except (OSError, ValueError) as error:
        return [*issues, str(error)]

    for key, (name, version) in expected.items():
        actual = secured.get(key)
        if actual is None:
            issues.append(f'{name}=={version} has no hash-lock entry')
        elif actual[1] != version:
            issues.append(f'{name} version differs: requirements lock {version}, hash lock {actual[1]}')
    for key, (name, version, hashes) in secured.items():
        if key not in expected:
            issues.append(f'{name}=={version} is absent from {Path(lock).name}')
    return issues


def hash_lock_entries(hash_lock=HASH_LOCK):
    entries = {}
    for number, line in enumerate(Path(hash_lock).read_text(encoding='utf-8').splitlines(), 1):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        match = re.fullmatch(
            r'([A-Za-z0-9_.-]+)==([^\s;]+)\s+((?:--hash=sha256:[0-9a-fA-F]{64}\s*)+)',
            line)
        if not match:
            raise ValueError(f'{Path(hash_lock).name}:{number} needs an exact pin and SHA-256 hash')
        name, version, hashes = match.groups()
        key = _key(name)
        if key in entries:
            raise ValueError(f'{Path(hash_lock).name} repeats {name}')
        entries[key] = (name, version, re.findall(r'--hash=sha256:([0-9a-fA-F]{64})', hashes))
    return entries


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def verified_install_hashes(lock=LOCK, hash_lock=HASH_LOCK):
    """Return pip-reported wheel hashes from this interpreter's verified install, if present."""
    report_path = Path(sys.prefix) / f'minijmp-hash-install-{_sha256(hash_lock)}.json'
    try:
        report = json.loads(report_path.read_text(encoding='utf-8'))
        if (report.get('python') != str(Path(sys.executable).resolve())
                or report.get('version_lock_sha256') != _sha256(lock)
                or report.get('hash_lock_sha256') != _sha256(hash_lock)):
            return None
        installed = {_key(item['name']): (item['version'], item['sha256'])
                     for item in report['verified_wheels']}
    except (OSError, ValueError, KeyError, TypeError):
        return None
    expected = hash_lock_entries(hash_lock)
    if set(installed) != set(expected):
        return None
    for key, (_, version, hashes) in expected.items():
        if installed[key][0] != version or installed[key][1].lower() not in hashes:
            return None
    return installed


def _write_verified_install_report(lock, hash_lock, wheelhouse):
    report_path = Path(sys.prefix) / f'minijmp-hash-install-{_sha256(hash_lock)}.json'
    temporary = report_path.with_name(report_path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        # A failed reinstall must not leave a previous hash-verified report usable.
        report_path.unlink(missing_ok=True)
        command = [sys.executable, '-m', 'pip', 'install', '--report', str(temporary),
                   '--force-reinstall', '--no-index', '--find-links', str(wheelhouse),
                   '--no-deps', '--only-binary=:all:', '--require-hashes', '-r', str(hash_lock)]
        result = subprocess.run(command)
        if result.returncode:
            return result.returncode
        differences = lock_mismatches(lock)
        pip_ok = _pip_check()
        if differences or not pip_ok:
            for item in differences:
                print(f'BLOCKED: {item}')
            if not pip_ok:
                print('BLOCKED: python -m pip check reported dependency conflicts after installation.')
            return 1
        pip_report = json.loads(temporary.read_text(encoding='utf-8'))
        installed = []
        for item in pip_report.get('install', []):
            info = item['download_info']['archive_info']['hashes']
            name = item['metadata']['name']
            digest = info.get('sha256')
            if not digest:
                raise ValueError(f'pip report has no SHA-256 for {name}')
            installed.append({'name': name, 'version': item['metadata']['version'], 'sha256': digest})
        record = {'python': str(Path(sys.executable).resolve()),
                  'version_lock_sha256': _sha256(lock), 'hash_lock_sha256': _sha256(hash_lock),
                  'verified_wheels': installed}
        temporary.write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
        temporary.replace(report_path)
        if verified_install_hashes(lock, hash_lock) is None:
            print('BLOCKED: pip install completed, but its SHA-256 report did not match the locks.')
            return 1
        print(f'PASS: pip installed {len(installed)} pinned wheels with SHA-256 verification.')
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f'BLOCKED: could not validate pip SHA-256 install report: {error}')
        return 1
    finally:
        temporary.unlink(missing_ok=True)


def _pyinstaller_version():
    try:
        return metadata.version('pyinstaller')
    except metadata.PackageNotFoundError:
        return 'missing'


def _pip_check():
    return subprocess.run([sys.executable, '-m', 'pip', 'check'],
                          capture_output=True).returncode == 0


def assess(version_info=None, lock=LOCK, hash_lock=HASH_LOCK, installed=None,
           pyinstaller=None, pip_ok=None, bits=None):
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

    hash_differences = hash_lock_mismatches(lock, hash_lock)
    if hash_differences:
        levels.extend(('BLOCKED', item) for item in hash_differences)
    else:
        levels.append(('PASS', f'{Path(hash_lock).name} has complete SHA-256 pins matching {Path(lock).name}.'))
    verified = None if hash_differences else verified_install_hashes(lock, hash_lock)
    if verified is None:
        levels.append(('WARNING', 'Installed package versions do not prove the existing environment was installed from hash-verified wheels.'))
    else:
        levels.append(('PASS', 'pip install report confirms the locked wheel SHA-256 hashes for this environment.'))

    pip_ok = _pip_check() if pip_ok is None else pip_ok
    levels.append(('PASS' if pip_ok else 'BLOCKED', 'python -m pip check passed.'
                   if pip_ok else 'python -m pip check reported dependency conflicts.'))

    pyinstaller = _pyinstaller_version() if pyinstaller is None else pyinstaller
    levels.append(('PASS' if pyinstaller == LOCKED_PYINSTALLER else 'BLOCKED',
                   f'PyInstaller {pyinstaller} (expected {LOCKED_PYINSTALLER}).'))
    return levels


def main(argv=None):
    parser = argparse.ArgumentParser(description='Check the Windows release Python environment.')
    parser.add_argument('lock', nargs='?', type=Path, default=LOCK)
    parser.add_argument('--hash-lock', type=Path, default=HASH_LOCK)
    parser.add_argument('--download-wheelhouse', type=Path,
                        help='download Windows wheels and let pip verify their SHA-256 hashes')
    parser.add_argument('--install-wheelhouse', type=Path,
                        help='force-install pinned wheels from a wheelhouse and record pip SHA-256 evidence')
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    if args.download_wheelhouse is not None:
        differences = hash_lock_mismatches(args.lock, args.hash_lock)
        if differences:
            for item in differences:
                print(f'BLOCKED: {item}')
            return 1
        if sys.version_info[:2] != MIN_PYTHON or struct.calcsize('P') * 8 != 64 or sys.platform != 'win32':
            print('BLOCKED: wheelhouse download requires Windows x64 Python 3.11.')
            return 1
        args.download_wheelhouse.mkdir(parents=True, exist_ok=True)
        command = [sys.executable, '-m', 'pip', 'download',
                   '--index-url', 'https://pypi.org/simple', '--dest', str(args.download_wheelhouse),
                   '--no-deps', '--only-binary=:all:', '--require-hashes',
                   '-r', str(args.hash_lock)]
        result = subprocess.run(command)
        if result.returncode:
            print(f'BLOCKED: pip download exited with {result.returncode}.')
            return result.returncode
        print(f'PASS: pip downloaded {len(hash_lock_entries(args.hash_lock))} pinned Windows wheels with SHA-256 verification.')
        return 0
    if args.install_wheelhouse is not None:
        differences = hash_lock_mismatches(args.lock, args.hash_lock)
        if differences:
            for item in differences:
                print(f'BLOCKED: {item}')
            return 1
        if sys.version_info[:2] != MIN_PYTHON or struct.calcsize('P') * 8 != 64 or sys.platform != 'win32':
            print('BLOCKED: verified installation requires Windows x64 Python 3.11.')
            return 1
        if not args.install_wheelhouse.is_dir():
            print(f'BLOCKED: wheelhouse directory does not exist: {args.install_wheelhouse}')
            return 1
        return _write_verified_install_report(args.lock, args.hash_lock,
                                              args.install_wheelhouse.resolve())

    blocked = 0
    for level, message in assess(lock=args.lock, hash_lock=args.hash_lock):
        print(f'{level}: {message}')
        blocked += level == 'BLOCKED'
    return 1 if blocked else 0


if __name__ == '__main__':
    raise SystemExit(main())
