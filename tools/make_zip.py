"""Create and verify release archives with the Windows-friendly standard library."""

import argparse
from fnmatch import fnmatchcase
import hashlib
import sys
import time
import zipfile
from pathlib import Path


# Build caches never belong in a release archive, including PIReader obj/bin output.
SKIP_DIRS = {'__pycache__', '.pytest_cache', '.mypy_cache', '.git', '.venv', 'obj', 'bin'}
SKIP_SUFFIXES = {'.pyc', '.pyo'}
DLP_HEADER = b'%TSD-Header-'

# Corresponding-source inputs; the release ships the whole tree of these paths.
SOURCE_DIRS = ('code', 'help', 'icon', 'sample_data', 'user_config', 'packaging',
               'PIReader', 'tests', 'tools', 'docs')
SOURCE_FILES = ('LICENSE', 'README.md', 'CHANGES', 'AGENTS.md', 'CODING_STANDARDS.md',
                'CONTRIBUTING.md', 'requirements.txt', 'start.py', 'setup_env.bat',
                'win_start.bat', 'win_start_no_cmd_win.vbs', 'PACKAGING.md')
SOURCE_SKIP_SUFFIXES = {'.log', '.tmp', '.bak', '.orig', '.swp'}
SOURCE_SKIP_NAMES = {'.DS_Store', 'Thumbs.db', 'local_settings.py'}
SOURCE_SKIP_PATHS = {
    'PIReader/config.txt',
    'PIReader/OSIsoft.PISDK.dll',
    'PIReader/OSIsoft.PISDKCommon.dll',
    'PIReader/OSIsoft.PITimeServer.dll',
}
SOURCE_SKIP_PATTERNS = (
    '*.draft.*', '*_draft.*',
    'docs/release/pyinstaller-build-V*.txt',
    'docs/release/build-inputs-V*.txt',
    'docs/_build/*',
    'PIReader/.vs/*',
)


def package_files(source):
    source = Path(source)
    files = []
    for path in sorted(source.rglob('*')):
        relative = path.relative_to(source)
        if not path.is_file() or SKIP_DIRS.intersection(relative.parts):
            continue
        if path.suffix.lower() in SKIP_SUFFIXES:
            continue
        files.append(path)
    return files


def zip_directory(source, destination, root_name=None):
    source, destination = Path(source), Path(destination)
    if not source.is_dir():
        raise NotADirectoryError(f'Not a directory: {source}')
    if destination.exists():
        raise FileExistsError(f'Refusing to overwrite existing archive: {destination}')
    files = package_files(source)
    if not files:
        raise ValueError(f'No files to archive in {source}')
    root_name = root_name or source.name
    # zipfile writes UTF-8 names for non-ASCII entries; keep forward slashes.
    with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, f'{root_name}/{path.relative_to(source).as_posix()}')
    with zipfile.ZipFile(destination) as archive:
        broken = archive.testzip()
    if broken:
        raise RuntimeError(f'Corrupt archive entry: {broken}')
    return len(files)


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest().upper()


def stable_sha256(path, settle=0.0, interval=15.0, attempts=3, sleep=time.sleep,
                  digest=sha256_file):
    """Return the digest once full content reads stop changing.

    shortcut: a DLP rewrite landing between two equal reads still slips through,
    so re-verify after writing SHA256SUMS (PACKAGING.md section A).
    """
    if settle:
        sleep(settle)
    digest_value = digest(path)
    for _ in range(attempts - 1):
        sleep(interval)
        current = digest(path)
        if current != digest_value:
            raise RuntimeError(
                f'{Path(path).name} changed after it was written: '
                f'{digest_value} -> {current}')
        digest_value = current
    return digest_value


def archive_entry_sha256(archive_path, entry):
    with zipfile.ZipFile(archive_path) as archive:
        if entry not in archive.namelist():
            raise KeyError(f'Archive has no entry {entry}')
        return hashlib.sha256(archive.read(entry)).hexdigest().upper()


def find_encrypted_containers(root):
    """Return files DLP replaced with a TsdEncrypt container."""
    root = Path(root)
    candidates = [root] if root.is_file() else root.rglob('*')
    hits = []
    for path in candidates:
        if path.is_file():
            with open(path, 'rb') as handle:
                if handle.read(len(DLP_HEADER)) == DLP_HEADER:
                    hits.append(path)
    return hits


def write_manifest(root, destination):
    """Record the exact build inputs with content digests."""
    root = Path(root)
    lines = ['SHA256  RELATIVE-PATH']
    files = package_files(root)
    for path in files:
        lines.append(f'{sha256_file(path)}  {path.relative_to(root).as_posix()}')
    Path(destination).write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return len(files)


def stage_source(root, destination, dirs=SOURCE_DIRS, files=SOURCE_FILES):
    """Copy the on-disk sources used for the build, tracked or not."""
    root, destination = Path(root), Path(destination)
    missing = [name for name in dirs + files if not (root / name).exists()]
    if missing:
        raise FileNotFoundError('Missing build input: ' + ', '.join(missing))
    staged = []
    for path in package_files(root):
        relative = path.relative_to(root)
        relative_name = relative.as_posix()
        if relative.parts[0] not in dirs and relative_name not in files:
            continue
        if (path.suffix.lower() in SOURCE_SKIP_SUFFIXES
                or path.name in SOURCE_SKIP_NAMES
                or path.name == '.env' or path.name.startswith('.env.')
                or path.name.startswith(('~$', 'draft-'))
                or relative_name in SOURCE_SKIP_PATHS
                or any(fnmatchcase(relative_name, pattern)
                       for pattern in SOURCE_SKIP_PATTERNS)):
            continue
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(path.read_bytes())
        staged.append(target)
    return staged


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)

    make = commands.add_parser('make', help='zip a directory tree')
    make.add_argument('source')
    make.add_argument('destination')
    make.add_argument('--root-name', help='top-level folder inside the archive')

    rehash = commands.add_parser('rehash', help='print a digest that survives rewriting')
    rehash.add_argument('path')
    rehash.add_argument('--settle', type=float, default=0)
    rehash.add_argument('--interval', type=float, default=15)
    rehash.add_argument('--attempts', type=int, default=3)

    inspect = commands.add_parser('inspect', help='report archive CRC and entry digest')
    inspect.add_argument('path')
    inspect.add_argument('--entry', help='entry whose SHA256 is printed')

    scan = commands.add_parser('scan', help='report DLP-encrypted files under a tree')
    scan.add_argument('path')

    manifest = commands.add_parser('manifest', help='write path and SHA256 for a tree')
    manifest.add_argument('path')
    manifest.add_argument('destination')

    stage = commands.add_parser('stage-source', help='stage corresponding sources')
    stage.add_argument('root')
    stage.add_argument('destination')

    args = parser.parse_args(argv)
    try:
        if args.command == 'make':
            count = zip_directory(args.source, args.destination, args.root_name)
            print(f'WROTE {args.destination} files={count}')
        elif args.command == 'rehash':
            print('SHA256=' + stable_sha256(args.path, args.settle, args.interval,
                                            args.attempts))
        elif args.command == 'inspect':
            with zipfile.ZipFile(args.path) as archive:
                entries = archive.namelist()
                print(f'ENTRIES={len(entries)}')
                print('CRC=' + (archive.testzip() or 'ok'))
            if args.entry:
                print('ENTRY-SHA256=' + archive_entry_sha256(args.path, args.entry))
        elif args.command == 'scan':
            hits = find_encrypted_containers(args.path)
            for path in hits:
                print(f'ENCRYPTED {path}')
            print(f'ENCRYPTED-FILES={len(hits)}')
            return 1 if hits else 0
        elif args.command == 'manifest':
            print(f'MANIFESTED={write_manifest(args.path, args.destination)}')
        else:
            staged = stage_source(args.root, args.destination)
            print(f'STAGED={len(staged)}')
    except (OSError, ValueError, RuntimeError, KeyError) as error:
        print(f'ERROR: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
