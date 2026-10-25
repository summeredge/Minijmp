"""Verify the three intentional version identifiers stay aligned."""

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PRODUCT = re.compile('v([0-9]+)[.]([0-9]+)[.]([0-9]+)-beta[.]([0-9]+)')


def read(root, name):
    return (Path(root) / name).read_text(encoding='utf-8', errors='replace')


def _assignment(text):
    for line in text.splitlines():
        if line.startswith('$releaseVersion = '):
            return line.split('=', 1)[1].strip().strip(chr(39))
    return None


def _between(text, start, end):
    begin = text.find(start)
    if begin < 0:
        return None
    begin += len(start)
    stop = text.find(end, begin)
    return text[begin:stop].strip() if stop >= 0 else None


def _first_line_starting(text, prefix):
    for line in text.splitlines():
        if line.startswith(prefix):
            return line.strip()
    return ''


def identifiers(root=ROOT):
    """Return the version text each release-facing file declares."""
    info = read(root, 'packaging/windows/version_info.txt')
    about = read(root, 'code/modified_app.py')
    readme = read(root, 'README.md')
    return {
        'release': _assignment(read(root, 'tools/build_windows_release.ps1')),
        'product:version_info': _between(info, "'ProductVersion', '", chr(39)),
        'product:fileversion': _between(info, "'FileVersion', '", chr(39)),
        'numeric:filevers': _between(info, 'filevers=(', ')'),
        'numeric:prodvers': _between(info, 'prodvers=(', ')'),
        'product:USAGE': read(root, 'packaging/windows/USAGE.txt').split()[1],
        'product:README': _between(readme, '当前版本标识：** ' + chr(96), chr(96)),
        'product:about': 'v' + _between(about, '版本 v', chr(39)),
        'product:CHANGES': _first_line_starting(read(root, 'CHANGES'), 'v0.'),
    }


def expected(groups):
    major, minor, patch, beta = groups
    numbers = ', '.join(groups)
    return {
        'release': f'V{major}.{minor}-beta{beta}',
        'product:fileversion': f'{major}.{minor}.{patch}.{beta}',
        'numeric:filevers': numbers,
        'numeric:prodvers': numbers,
    }


def check(root=ROOT):
    found = identifiers(root)
    match = PRODUCT.fullmatch(found['product:version_info'] or '')
    if not match:
        return [('BLOCKED', 'version_info.txt ProductVersion is not vX.Y.Z-beta.N.')]
    wanted = expected(match.groups())
    for name in ('product:USAGE', 'product:README', 'product:about', 'product:CHANGES'):
        wanted[name] = found['product:version_info']

    problems = []
    for name, value in wanted.items():
        actual = found[name] or ''
        if name.startswith('numeric'):
            actual = ', '.join(part.strip() for part in actual.split(','))
        if actual != value:
            problems.append(('BLOCKED',
                             f'{name}: expected {value}, found {actual or "nothing"}.'))
    if problems:
        return problems
    return [('PASS', f'Version identifiers agree: {wanted["release"]} / '
                     f'{found["product:version_info"]} / {wanted["product:fileversion"]}.')]


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    levels = check(Path(argv[0]) if argv else ROOT)
    for level, message in levels:
        print(f'{level}: {message}')
    return 1 if any(level == 'BLOCKED' for level, _ in levels) else 0


if __name__ == '__main__':
    raise SystemExit(main())
