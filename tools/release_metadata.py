"""Verify the intentional display, product and file version identifiers stay aligned."""

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PRODUCT = re.compile('v([0-9]+)[.]([0-9]+)[.]([0-9]+)(?:-beta[.]([0-9]+))?')


def read(root, name):
    return (Path(root) / name).read_text(encoding='utf-8', errors='replace')


def _assignment(text, name='releaseVersion'):
    for line in text.splitlines():
        if line.startswith(f'${name} = '):
            return line.split('=', 1)[1].strip().strip(chr(39))
    return None


def _between(text, start, end):
    begin = text.find(start)
    if begin < 0:
        return None
    begin += len(start)
    stop = text.find(end, begin)
    return text[begin:stop].strip() if stop >= 0 else None


def _first_product_version(text):
    for line in text.splitlines():
        if PRODUCT.fullmatch(line.strip()):
            return line.strip()
    return ''


def identifiers(root=ROOT):
    """Return the version text each release-facing file declares."""
    info = read(root, 'packaging/windows/version_info.txt')
    about = read(root, 'code/modified_app.py')
    readme = read(root, 'README.md')
    assembly = read(root, 'PIReader/Properties/AssemblyInfo.cs')
    return {
        'release': _assignment(read(root, 'tools/build_windows_release.ps1')),
        'product:build': _assignment(read(root, 'tools/build_windows_release.ps1'), 'productVersion'),
        'product:version_info': _between(info, "'ProductVersion', '", chr(39)),
        'product:fileversion': _between(info, "'FileVersion', '", chr(39)),
        'numeric:filevers': _between(info, 'filevers=(', ')'),
        'numeric:prodvers': _between(info, 'prodvers=(', ')'),
        'product:USAGE': read(root, 'packaging/windows/USAGE.txt').split()[1],
        'product:README': _between(readme, '产品版本标识：** ' + chr(96), chr(96)),
        'display:about': _between(about, '版本 ', chr(39)),
        'product:CHANGES': _first_product_version(read(root, 'CHANGES')),
        'product:PIReader': _between(assembly, 'AssemblyInformationalVersion("', '"'),
        'file:PIReader': _between(assembly, 'AssemblyFileVersion("', '"'),
        'assembly:PIReader': _between(assembly, 'AssemblyVersion("', '"'),
    }


def expected(groups):
    major, minor, patch, beta = groups
    numbers = ', '.join((*groups[:3], beta or '0'))
    return {
        'release': f'V{major}.{minor}' + (f'-beta{beta}' if beta else ''),
        'display:about': f'V{major}.{minor}' + (f' beta{beta}' if beta else ''),
        'product:fileversion': f'{major}.{minor}.{patch}.{beta or 0}',
        'numeric:filevers': numbers,
        'numeric:prodvers': numbers,
    }


def check(root=ROOT):
    found = identifiers(root)
    match = PRODUCT.fullmatch(found['product:version_info'] or '')
    if not match:
        return [('BLOCKED', 'version_info.txt ProductVersion is not vX.Y.Z or vX.Y.Z-beta.N.')]
    wanted = expected(match.groups())
    for name in ('product:USAGE', 'product:README', 'product:build', 'product:CHANGES', 'product:PIReader'):
        wanted[name] = found['product:version_info']
    wanted['file:PIReader'] = wanted['assembly:PIReader'] = wanted['product:fileversion']

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


def finalize(runtime, destination):
    """Collect review documents and hash the actual deliverables without self-hashing."""
    import shutil
    import subprocess
    from make_zip import sha256_file, stable_sha256

    commit = subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip()
    tag_commit = subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'v1.1.0^{}'], text=True).strip()
    if commit != tag_commit:
        raise ValueError('v1.1.0 does not identify the build commit')
    build_info = (runtime / 'BUILD-INFO.txt').read_text(encoding='utf-8-sig')
    if f'Base Git HEAD: {commit}' not in build_info:
        raise ValueError('Build commit differs from HEAD')
    binaries = sorted(destination.glob('*.zip'))
    if len(binaries) != 2:
        raise ValueError('Expected runtime and source archives')
    hashes = {path.name: stable_sha256(path, interval=15, attempts=2) for path in binaries}
    hashes['MiniJMP.exe (Windows ZIP/MiniJMP-V1.1/MiniJMP.exe)'] = sha256_file(runtime / 'MiniJMP.exe')
    hashes['PIReader.exe (Windows ZIP/MiniJMP-V1.1/PIReader/PIReader.exe)'] = sha256_file(
        runtime / 'PIReader' / 'PIReader.exe')
    hash_text = '\n'.join(f'{value}  {name}' for name, value in hashes.items())
    for name in ('VERSION-INFO.md', 'INSTALL-USAGE.md', 'SOURCE-PROVENANCE.md', 'SOURCE-PROVENANCE.csv'):
        source = ROOT / 'docs' / 'release' / name
        text = source.read_text(encoding='utf-8-sig').replace('{{COMMIT}}', commit).replace('{{TAG}}', 'v1.1.0').replace('{{SHA256}}', hash_text)
        (destination / name).write_text(text, encoding='utf-8')
    for name in ('THIRD-PARTY-NOTICES.txt', 'LICENSE', 'PI-SDK-NOTICE.txt'):
        shutil.copyfile(runtime / name, destination / name)
    shutil.copytree(runtime / 'THIRD-PARTY-LICENSES', destination / 'THIRD-PARTY-LICENSES')
    info = build_info
    lock = ROOT / 'packaging/windows/requirements-py311.lock'
    info += '\nDependency lock: packaging/windows/requirements-py311.lock; SHA256 ' + sha256_file(lock)
    info += '\nRelease files SHA256:\n' + hash_text + '\n'
    (destination / 'BUILD-INFO.txt').write_text(info, encoding='utf-8')
    entries = sorted(path for path in destination.rglob('*') if path.is_file() and path.name != 'SHA256SUMS.txt')
    lines = [f'{sha256_file(path)}  {path.relative_to(destination).as_posix()}' for path in entries]
    lines.append(f"{sha256_file(runtime / 'MiniJMP.exe')}  ../MiniJMP-V1.1/MiniJMP.exe")
    lines.append(f"{sha256_file(runtime / 'PIReader' / 'PIReader.exe')}  ../MiniJMP-V1.1/PIReader/PIReader.exe")
    (destination / 'SHA256SUMS.txt').write_text('\n'.join(lines) + '\n', encoding='ascii')
    for line in lines:
        digest, relative = line.split('  ', 1)
        if sha256_file(destination / relative) != digest:
            raise ValueError(f'Artifact changed: {relative}')
    print(f'PASS: review package finalized for {commit}: {destination}')


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == '--finalize':
        finalize(Path(argv[1]), Path(argv[2]))
        return 0
    levels = check(Path(argv[0]) if argv else ROOT)
    for level, message in levels:
        print(f'{level}: {message}')
    return 1 if any(level == 'BLOCKED' for level, _ in levels) else 0


if __name__ == '__main__':
    raise SystemExit(main())
