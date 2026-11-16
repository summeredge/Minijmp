"""Prune development-only artifacts from a bundled pyarrow package.

Only files that pyarrow never loads at runtime are removed: C/C++ headers,
import libraries, Cython sources, tests, and the Flight/Substrait/Dataset
extension modules that MiniJMP does not use. Parquet, Arrow tables, compute,
filesystem and the pandas integration stay intact.
"""
import argparse
import shutil
import sys
from pathlib import Path

DIRS = ('include', 'includes', 'src', 'tests')
FILES = (
    '*.lib', '*.pyx', '*.pxd', '*.pxi', '*.h', '*.hpp',
    'arrow_flight.dll', 'arrow_python_flight.dll',
    'arrow_substrait.dll', 'arrow_dataset.dll', 'arrow_acero.dll',
    '_flight*.pyd', '_substrait*.pyd', '_dataset*.pyd', '_acero*.pyd',
)
REQUIRED = ('parquet.dll', 'arrow.dll', 'arrow_compute.dll', 'arrow_python.dll')


def prune(package):
    files = size = 0
    for name in DIRS:
        target = package / name
        if target.is_dir():
            for item in target.rglob('*'):
                if item.is_file():
                    files += 1
                    size += item.stat().st_size
            shutil.rmtree(target)
    for pattern in FILES:
        for item in package.glob(pattern):
            if item.is_file():
                files += 1
                size += item.stat().st_size
                item.unlink()
    missing = [name for name in REQUIRED if not (package / name).is_file()]
    if missing:
        raise SystemExit(f'prune removed required binaries: {missing}')
    return files, size


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('package', type=Path, help='path to the bundled pyarrow package')
    args = parser.parse_args()
    package = args.package
    if not (package / 'parquet.dll').is_file():
        raise SystemExit(f'{package} does not look like a bundled pyarrow package')
    files, size = prune(package)
    print(f'pyarrow pruned: {files} files, {size / 2**20:.1f} MiB removed')
    return 0


if __name__ == '__main__':
    sys.exit(main())
