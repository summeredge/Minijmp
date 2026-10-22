"""Copy installed runtime dependency license texts into a Windows package."""

from importlib import metadata
from pathlib import Path, PurePosixPath
import re
import shutil
import sys

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name


ROOT = Path(__file__).resolve().parents[1]


def _license_files(distribution):
    files = []
    for item in distribution.files or ():
        relative = PurePosixPath(str(item))
        name = relative.name.lower()
        if name.startswith(('license', 'copying', 'notice')):
            path = Path(distribution.locate_file(item))
            if path.is_file():
                files.append((relative, path))
    return files


def _license_summary(distribution):
    metadata = distribution.metadata
    expression = metadata.get('License-Expression')
    if expression:
        return expression
    classifiers = [item.split(' :: ')[-1] for item in metadata.get_all('Classifier', ())
                   if item.startswith('License ::')]
    if classifiers:
        return '; '.join(classifiers)
    license_text = (metadata.get('License') or '').strip()
    if license_text and len(license_text) < 100 and '\n' not in license_text:
        return license_text
    return 'See the included upstream license text.'


def generate(destination):
    destination = Path(destination)
    license_dir = destination / 'THIRD-PARTY-LICENSES'
    license_dir.mkdir(parents=True, exist_ok=True)

    requirements = [Requirement(line).name for line in
                    (ROOT / 'requirements.txt').read_text(encoding='utf-8').splitlines()
                    if line.strip() and not line.lstrip().startswith('#')]
    requirements.extend(('numpy', 'pyinstaller'))
    names = sorted(set(requirements), key=canonicalize_name)
    rows = []
    for name in names:
        distribution = metadata.distribution(name)
        package = distribution.metadata.get('Name', name)
        version = distribution.version
        copied = []
        for relative, source in _license_files(distribution):
            safe_name = re.sub(r'[^A-Za-z0-9._-]+', '_', package)
            license_name = re.sub(r'[^A-Za-z0-9._-]+', '_', str(relative))
            target = license_dir / f'{safe_name}-{version}-{license_name}'
            shutil.copyfile(source, target)
            copied.append(target.name)
        files = ', '.join(copied) if copied else 'No license file shipped in installed metadata.'
        rows.append(f'- {package} {version} — {_license_summary(distribution)}; {files}')

    python_license = Path(sys.base_prefix) / 'LICENSE.txt'
    if python_license.is_file():
        shutil.copyfile(python_license, license_dir / 'Python-LICENSE.txt')
        rows.append(f'- Python {sys.version.split()[0]} — Python Software Foundation License; Python-LICENSE.txt')
    tk_license = Path(sys.base_prefix) / 'tcl' / 'tk8.6' / 'license.terms'
    if tk_license.is_file():
        shutil.copyfile(tk_license, license_dir / 'Tcl-Tk-license.terms')
        rows.append('- Tcl/Tk 8.6 — license terms shipped with the Python runtime; Tcl-Tk-license.terms')

    notice = (
        'THIRD-PARTY NOTICES\n\n'
        'MiniJMP is licensed under GNU GPL version 3 or later; see the adjacent LICENSE file.\n'
        'The following runtime dependencies and PyInstaller bootloader were used for this build.\n'
        'License metadata and upstream license files are copied from the locked build environment.\n\n'
        + '\n'.join(rows) + '\n'
    )
    (destination / 'THIRD-PARTY-NOTICES.txt').write_text(notice, encoding='utf-8')
    return notice


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('Usage: write_third_party_notices.py DESTINATION')
    generate(sys.argv[1])
