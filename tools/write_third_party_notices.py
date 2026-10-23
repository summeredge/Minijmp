"""Copy installed runtime dependency license texts into a Windows package."""

from importlib import metadata
from pathlib import Path, PurePosixPath
import re
import shutil
import sys

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name


ROOT = Path(__file__).resolve().parents[1]

ICON_LICENSES = (
    ('Carbon-Icons-Apache-2.0.txt', '@carbon/icons 11.91.0', 'Apache-2.0'),
    ('Tabler-Icons-MIT.txt', 'Tabler Icons', 'MIT'),
)
CARBON_ICON_FILES = (
    'chart--custom.svg', 'chart--histogram.svg', 'chart--cluster-bar.svg',
    'chart--treemap.svg', 'chart--candlestick.svg', 'chart--violin-plot.svg',
    'chart--bar.svg', 'chart--pie.svg', 'chart--line.svg', 'chart--line--data.svg',
    'chart--multi-line.svg', 'chart--scatter.svg', 'chart--area-smooth.svg',
    'chart--lollipop.svg', 'chart--3D.svg', 'chart--bubble.svg', 'chart--point.svg',
    'chart--error-bar.svg', 'chart--multitype.svg', 'chart--logistic-regression.svg',
)
TABLER_ICON_FILES = (
    'chart-area-line.svg', 'chart-arcs-3.svg', 'chart-dots-3.svg',
    'chart-scatter-3d.svg', 'grid-dots.svg',
)


def _license_files(distribution):
    files = []
    seen = set()
    installed = [PurePosixPath(str(item)) for item in distribution.files or ()]
    metadata_dirs = [item.parent for item in installed
                     if item.name in ('METADATA', 'PKG-INFO')]
    for declared in distribution.metadata.get_all('License-File', ()):
        relative = PurePosixPath(declared)
        candidates = [directory / prefix / relative
                      for directory in metadata_dirs for prefix in ('licenses', '')]
        for candidate in candidates:
            path = Path(distribution.locate_file(candidate))
            if path.is_file():
                if path.resolve() not in seen:
                    files.append((candidate, path))
                    seen.add(path.resolve())
                break
        else:
            raise FileNotFoundError(
                f"{distribution.metadata['Name']}: missing License-File {declared}")
    for item in distribution.files or ():
        relative = PurePosixPath(str(item))
        name = relative.name.lower()
        if name.startswith(('license', 'licence', 'copying', 'notice')):
            path = Path(distribution.locate_file(item))
            if path.is_file() and path.resolve() not in seen:
                files.append((relative, path))
                seen.add(path.resolve())
    if not files:
        raise FileNotFoundError(
            f"{distribution.metadata['Name']}: no upstream license file installed")
    return files


def _runtime_dependencies():
    pending = [Requirement(line) for line in
               (ROOT / 'requirements.txt').read_text(encoding='utf-8').splitlines()
               if line.strip() and not line.lstrip().startswith('#')]
    distributions = {}
    while pending:
        requirement = pending.pop()
        if requirement.marker and not requirement.marker.evaluate({'extra': ''}):
            continue
        name = canonicalize_name(requirement.name)
        if name in distributions:
            continue
        distribution = metadata.distribution(name)
        distributions[name] = distribution
        pending.extend(Requirement(item) for item in distribution.requires or ())
    # Only the bootloader is distributed, not PyInstaller's build-time dependencies.
    distributions['pyinstaller'] = metadata.distribution('pyinstaller')
    return [distributions[name] for name in sorted(distributions)]


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

    rows = []
    for distribution in _runtime_dependencies():
        package = distribution.metadata['Name']
        version = distribution.version
        copied = []
        for relative, source in _license_files(distribution):
            safe_name = re.sub(r'[^A-Za-z0-9._-]+', '_', package)
            license_name = re.sub(r'[^A-Za-z0-9._-]+', '_', str(relative))
            target = license_dir / f'{safe_name}-{version}-{license_name}'
            shutil.copyfile(source, target)
            copied.append(target.name)
        files = ', '.join(copied)
        rows.append(f'- {package} {version} — {_license_summary(distribution)}; {files}')

    python_license = Path(sys.base_prefix) / 'LICENSE.txt'
    if python_license.is_file():
        shutil.copyfile(python_license, license_dir / 'Python-LICENSE.txt')
        rows.append(f'- Python {sys.version.split()[0]} — Python Software Foundation License; Python-LICENSE.txt')
    tk_license = Path(sys.base_prefix) / 'tcl' / 'tk8.6' / 'license.terms'
    if tk_license.is_file():
        shutil.copyfile(tk_license, license_dir / 'Tcl-Tk-license.terms')
        rows.append('- Tcl/Tk 8.6 — license terms shipped with the Python runtime; Tcl-Tk-license.terms')

    for filename, package, license_name in ICON_LICENSES:
        source = ROOT / 'packaging' / 'windows' / 'licenses' / filename
        shutil.copyfile(source, license_dir / filename)
        rows.append(f'- {package} — {license_name}; {filename}')

    notice = (
        'THIRD-PARTY NOTICES\n\n'
        'MiniJMP is licensed under GNU GPL version 3 or later; see the adjacent LICENSE file.\n'
        'The following runtime dependencies and PyInstaller bootloader were used for this build.\n'
        'License metadata and upstream license files are copied from the locked build environment.\n\n'
        + '\n'.join(rows)
        + '\n\nGRAPH MENU ICON ATTRIBUTION\n'
        + 'Menu PNGs are 16x16 conversions of official upstream SVG assets embedded in code/icon_resource.py.\n'
        + 'Carbon: IBM Carbon Design System, @carbon/icons 11.91.0, Apache-2.0; source commit '
        + '45b0fc1b328ffdc4a784560f7983210b2e20596e; '
        + 'https://github.com/carbon-design-system/carbon/tree/45b0fc1b328ffdc4a784560f7983210b2e20596e/packages/icons/src/svg/32\n'
        + '  SVG files: ' + ', '.join(CARBON_ICON_FILES) + '\n'
        + 'Tabler: Tabler Icons, Copyright (c) 2020-2026 Paweł Kuna, MIT; source commit '
        + 'a4ce1404bc6d24d3c365afe7b258d6bf6f48d62d; '
        + 'https://github.com/tabler/tabler-icons/tree/a4ce1404bc6d24d3c365afe7b258d6bf6f48d62d/icons/outline\n'
        + '  SVG files: ' + ', '.join(TABLER_ICON_FILES) + '\n'
        + 'Neither pinned revision has a repository-root NOTICE file; both complete license texts are included.\n'
    )
    (destination / 'THIRD-PARTY-NOTICES.txt').write_text(notice, encoding='utf-8')
    return notice


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('Usage: write_third_party_notices.py DESTINATION')
    generate(sys.argv[1])
