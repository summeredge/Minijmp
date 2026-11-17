"""Verify a public Windows candidate against its version, sources and contents.

The checks here are the ones a reviewer or CI can run without a desktop:
version provenance, archive contents, digests, SBOM and the built executable.
Splash, window focus and keyboard behaviour stay a manual acceptance step.
"""

import argparse
import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path

from make_zip import sha256_file
import release_metadata

PI_SDK_DLLS = frozenset({'OSIsoft.PISDK.dll', 'OSIsoft.PISDKCommon.dll', 'OSIsoft.PITimeServer.dll'})
SKIP_PARTS = frozenset({'__pycache__', '.git', '.pytest_cache', '.mypy_cache', '.venv', '.vs'})
SKIP_SUFFIXES = ('.pyc', '.pyo', '.log', '.tmp', '.spec', '.pfx', '.p12', '.key', '.pem')
RUNTIME_FILES = ('MiniJMP.exe', 'LICENSE', 'README.txt', 'THIRD-PARTY-NOTICES.txt')
SOURCE_FILES = ('start.py', 'LICENSE', 'PACKAGING.md', 'SOURCE-MANIFEST.txt',
                'code/help.json', 'tools/build_windows_release.ps1', 'tools/make_zip.py',
                'packaging/windows/version_info.txt', 'packaging/windows/requirements-py311.lock',
                '.github/workflows/release.yml')


def archive_problems(names, root, kind):
    """Return what disqualifies an archive listing; names use forward slashes."""
    problems = []
    tops = {name.split('/', 1)[0] for name in names}
    if tops != {root}:
        problems.append(f'archive must contain only the folder {root}; found {sorted(tops)}')
    entries = {name.split('/', 1)[1] for name in names if name.startswith(root + '/')}
    required = RUNTIME_FILES if kind == 'runtime' else SOURCE_FILES
    for name in required:
        if name not in entries:
            problems.append(f'{root}/{name} is missing from the {kind} archive')
    if kind == 'runtime' and not any(name.startswith('_internal/') for name in entries):
        problems.append(f'{root}/_internal is missing from the runtime archive')
    for name in sorted(names):
        parts = name.split('/')
        relative = '/'.join(parts[1:])
        base = parts[-1]
        suffix = Path(base).suffix.lower()
        if SKIP_PARTS.intersection(parts):
            problems.append(f'build cache or repository data in the archive: {name}')
        elif suffix in SKIP_SUFFIXES:
            problems.append(f'temporary or signing file in the archive: {name}')
        elif base in PI_SDK_DLLS or base.lower().startswith('osisoft.'):
            problems.append(f'proprietary PI SDK component in the archive: {name}')
        elif base == 'SDK-COMPONENTS.json':
            problems.append(f'proprietary SDK inventory in the archive: {name}')
        elif relative in ('PIReader/PIReader.exe', 'PIReader/config.txt', 'PIReader/tags.txt'):
            problems.append(f'PIReader runtime or local PI settings in the archive: {name}')
        elif kind == 'runtime' and relative.startswith('PIReader/'):
            problems.append(f'PIReader component in a public runtime archive: {name}')
    return problems


def sums_problems(text, base):
    """Return digest mismatches for a SHA256SUMS file inside base."""
    problems = []
    entries = 0
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        digest, separator, relative = line.partition('  ')
        if not separator or not re.fullmatch('[0-9A-F]{64}', digest):
            problems.append(f'SHA256SUMS line is not DIGEST  PATH: {line}')
            continue
        entries += 1
        target = base / relative
        if not target.is_file():
            target = base.parent / relative
        if not target.is_file():
            problems.append(f'SHA256SUMS names a missing file: {relative}')
        elif sha256_file(target) != digest:
            problems.append(f'SHA256SUMS digest does not match {relative}')
    if not entries:
        problems.append('SHA256SUMS lists no files')
    return problems


def build_info_problems(text, release, commit):
    """Return what a BUILD-INFO.txt states wrongly for this candidate."""
    problems = []
    for prefix, expected in (('Release name: ', release), ('Git Tag: ', None),
                             ('Base Git HEAD: ', commit), ('Build mode: ', 'Public')):
        line = next((item for item in text.splitlines() if item.startswith(prefix)), None)
        if line is None:
            problems.append(f'BUILD-INFO.txt has no {prefix.strip()} line')
        elif expected and expected not in line:
            problems.append(f'BUILD-INFO.txt {prefix.strip()} is {line[len(prefix):]!r}, not {expected!r}')
    return problems


def sbom_problems(document, product):
    """Return version or distribution problems in a CycloneDX document."""
    problems = []
    metadata = document.get('metadata', {})
    component = metadata.get('component', {})
    if component.get('version') != product.lstrip('v'):
        problems.append(f"SBOM version {component.get('version')!r} is not {product.lstrip('v')!r}")
    properties = {item['name']: item['value'] for item in metadata.get('properties', [])
                  if isinstance(item, dict) and 'name' in item}
    if properties.get('minijmp:tag') != product:
        problems.append(f"SBOM tag {properties.get('minijmp:tag')!r} is not {product!r}")
    for component in document.get('components', []):
        name = str(component.get('name', ''))
        if name in PI_SDK_DLLS or name.lower().startswith('osisoft.'):
            shipped = {item['name']: item['value'] for item in component.get('properties', [])
                       if isinstance(item, dict) and 'name' in item}
            if shipped.get('minijmp:distributed') != 'false':
                problems.append(f'SBOM still reports the PI SDK component {name}')
    return problems


def executable_problems(executable, expected_file_version):
    """Return problems with the file version, icon and splash payload of an EXE."""
    import pefile

    problems = []
    pe = pefile.PE(str(executable), fast_load=True)
    try:
        pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_RESOURCE']])
        resources = {entry.id for entry in getattr(pe, 'DIRECTORY_ENTRY_RESOURCE', []).entries}
        strings = {}
        for group in getattr(pe, 'FileInfo', []):
            for entry in group:
                for table in getattr(entry, 'StringTable', []):
                    strings.update({key.decode('utf-8', 'replace'): value.decode('utf-8', 'replace')
                                    for key, value in table.entries.items()})
        file_version = strings.get('FileVersion', '')
    finally:
        pe.close()
    if file_version != expected_file_version:
        problems.append(f'EXE file version {file_version!r} is not {expected_file_version!r}')
    if 14 not in resources:  # RT_GROUP_ICON
        problems.append('EXE has no application icon resource')
    from PyInstaller.archive.readers import CArchiveReader
    toc = CArchiveReader(str(executable)).toc
    if not any('splash' in str(name).lower() for name in toc):
        problems.append('EXE embeds no startup splash payload')
    return problems


def verify(audit, release=None, commit=None):
    """Return (problems, product) for the candidate in the audit directory."""
    audit = Path(audit)
    product, display = release_metadata.release_titles()
    release = release or display
    commit = commit or None
    problems = []
    archive = audit / f'MiniJMP-{release}-Windows-x64-portable.zip'
    source = audit / f'MiniJMP-{release}-Source.zip'
    sums = audit / f'SHA256SUMS-{release}.txt'
    sbom = audit / 'SBOM.cdx.json'
    runtime = audit.parent / f'MiniJMP-{release}'
    for path in (archive, source, sums, sbom):
        if not path.is_file():
            problems.append(f'missing candidate file: {path}')
    if problems:
        return problems, product

    with zipfile.ZipFile(archive) as handle:
        broken = handle.testzip()
        if broken:
            problems.append(f'corrupt runtime archive entry: {broken}')
        problems.extend(archive_problems(handle.namelist(), f'MiniJMP-{release}', 'runtime'))
        executable_hash = None
        entry = f'MiniJMP-{release}/MiniJMP.exe'
        if entry in handle.namelist():
            executable_hash = hashlib.sha256(handle.read(entry)).hexdigest().upper()
    with zipfile.ZipFile(source) as handle:
        broken = handle.testzip()
        if broken:
            problems.append(f'corrupt source archive entry: {broken}')
        problems.extend(archive_problems(handle.namelist(), f'MiniJMP-{release}-source', 'source'))
        version_info = f'MiniJMP-{release}-source/packaging/windows/version_info.txt'
        if version_info in handle.namelist():
            declared = re.search(r"'ProductVersion', '([^']+)'",
                                 handle.read(version_info).decode('utf-8', 'replace'))
            if not declared or declared.group(1) != product:
                problems.append(f'source archive declares version '
                                f'{declared.group(1) if declared else "nothing"}, not {product}')

    executable = runtime / 'MiniJMP.exe'
    if not executable.is_file():
        problems.append(f'missing built executable: {executable}')
    else:
        if executable_hash and sha256_file(executable) != executable_hash:
            problems.append('the EXE inside the runtime archive differs from the built EXE')
        expected_file_version = release_metadata.identifiers()['product:fileversion']
        try:
            problems.extend(executable_problems(executable, expected_file_version))
        except Exception as error:  # pefile/PyInstaller refusals are findings, not crashes
            problems.append(f'cannot inspect {executable.name}: {error}')
        build_info = runtime / 'BUILD-INFO.txt'
        if not build_info.is_file():
            problems.append('missing BUILD-INFO.txt beside the built executable')
        else:
            problems.extend(build_info_problems(
                build_info.read_text(encoding='utf-8-sig'), release, commit))

    problems.extend(sums_problems(sums.read_text(encoding='utf-8-sig', errors='replace'), audit))
    sums_text = sums.read_text(encoding='utf-8-sig', errors='replace')
    for name in (archive.name, source.name):
        if name not in sums_text:
            problems.append(f'SHA256SUMS does not list {name}')
    try:
        problems.extend(sbom_problems(json.loads(sbom.read_text(encoding='utf-8')), product))
    except ValueError as error:
        problems.append(f'SBOM.cdx.json is not valid JSON: {error}')
    return problems, product


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('audit', type=Path, help='directory holding the candidate archives')
    parser.add_argument('--release', help='release name, such as V1.2.1; derived from the metadata')
    parser.add_argument('--commit', help='expected Git commit of the build')
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    problems, product = verify(args.audit, args.release, args.commit)
    for problem in problems:
        print(f'BLOCKED: {problem}')
    if problems:
        return 1
    print(f'PASS: public candidate {product} is consistent, complete and free of PI SDK components.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
