"""Inventory the locked environment and actual PyInstaller onedir contents."""

import ast
import csv
from datetime import datetime, timezone
from importlib import metadata
import json
import re
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

from make_zip import sha256_file
from release_env import (HASH_LOCK, hash_lock_entries, hash_lock_mismatches,
                         verified_install_hashes)
from write_third_party_notices import _license_files, _license_summary, _runtime_dependencies

ROOT = Path(__file__).resolve().parents[1]
PI_RUNTIME_FILES = (
    'PIReader.exe',
    'OSIsoft.PISDK.dll',
    'OSIsoft.PISDKCommon.dll',
    'OSIsoft.PITimeServer.dll',
)


def properties(**values):
    return [{'name': 'minijmp:' + name, 'value': str(value)} for name, value in values.items()]


def component(name, version, url, license_name, spdx='', shipped=False, source='', kind='library',
              license_status=None, **extra):
    if license_status is None:
        license_status = ('upstream-SPDX' if spdx else
                          'review-required' if not license_name or '待确认' in license_name or '未确认' in license_name
                          else 'declared-no-SPDX')
    row = {'type': kind, 'bom-ref': 'urn:uuid:' + str(uuid.uuid4()),
           'name': name, 'version': version or 'unknown',
           'licenses': [{'license': {'id': spdx} if spdx else {'name': license_name or '待确认'}}],
           'properties': properties(distributed=str(shipped).lower(), source=source,
                                    license_status=license_status, **extra)}
    if url:
        row['externalReferences'] = [{'type': 'website', 'url': url}]
    return row


def toc_sources(build):
    """TOCs record both PYZ pure modules and collected native/data source paths."""
    paths = set()

    def visit(value):
        if isinstance(value, (tuple, list)):
            if len(value) == 3 and all(isinstance(v, str) for v in value):
                if Path(value[1]).is_absolute():
                    paths.add(str(Path(value[1]).resolve()).lower())
            for item in value:
                visit(item)
    for name in ('PYZ-00.toc', 'COLLECT-00.toc', 'Analysis-00.toc'):
        path = build / name
        if not path.is_file():
            raise FileNotFoundError(path)
        # Analysis includes available modules, not all of them are shipped.
        if name != 'Analysis-00.toc':
            visit(ast.literal_eval(path.read_text(encoding='utf-8')))
    return paths


def license_fields(dist):
    expression = dist.metadata.get('License-Expression', '')
    summary = _license_summary(dist)
    if expression:
        return summary, expression, 'upstream-SPDX'
    license_text = (dist.metadata.get('License') or '').strip()
    if license_text.lower() in {'unknown', 'none', 'n/a'}:
        license_text = ''
    classifiers = dist.metadata.get_all('Classifier', ())
    declared = bool(license_text or any(item.startswith('License ::') for item in classifiers))
    files = dist.files or ()
    text_present = bool(dist.metadata.get_all('License-File', ())) or any(
        Path(str(item)).name.lower().startswith(('license', 'licence', 'copying')) for item in files)
    status = ('declared-no-SPDX' if declared else
              'license-text-present; classification-unverified' if text_present else
              'review-required')
    return summary, '', status


def dependency_closure(roots, distributions):
    names, pending = set(), list(roots)
    while pending:
        key = canonicalize_name(pending.pop())
        if key in names:
            continue
        names.add(key)
        dist = distributions.get(key)
        if dist:
            for text in dist.requires or ():
                requirement = Requirement(text)
                if not requirement.marker or requirement.marker.evaluate({'extra': ''}):
                    pending.append(requirement.name)
    return names


def file_version(path):
    import pefile
    pe = pefile.PE(str(path), fast_load=True)
    try:
        pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_RESOURCE']])
        for group in getattr(pe, 'FileInfo', []):
            for entry in group:
                for table in getattr(entry, 'StringTable', []):
                    value = table.entries.get(b'FileVersion')
                    if value:
                        return value.decode('utf-8', errors='replace').strip()
        return ''
    finally:
        pe.close()


def pi_runtime_components(runtime):
    components = []
    for name in PI_RUNTIME_FILES:
        path = Path(runtime) / 'PIReader' / name
        present = path.is_file()
        is_program = name == 'PIReader.exe'
        if is_program:
            url = 'https://github.com/summeredge/Minijmp'
            license_name, spdx = 'GNU GPL version 3 or later; see LICENSE', 'GPL-3.0-or-later'
            source = 'signed runtime artifact: PIReader/PIReader.exe; MiniJMP-developed source'
        else:
            url = 'https://www.aveva.com/'
            license_name, spdx = '专有组件；再分发授权未确认', ''
            source = f'actual runtime file: PIReader/{name}; supplied SDK input'
        if not present:
            source = f'not present in actual runtime; no repository fallback: PIReader/{name}'
        item = component(name, file_version(path) if present else 'unknown', url, license_name, spdx,
                         shipped=present, source=source, kind='file')
        if present:
            item['hashes'] = [{'alg': 'SHA-256', 'content': sha256_file(path)}]
        components.append(item)
    return components


def minijmp_runtime_component(path):
    path = Path(path)
    item = component('MiniJMP.exe', file_version(path) or 'unknown',
                     'https://github.com/summeredge/Minijmp',
                     'GNU GPL version 3 or later; see LICENSE', 'GPL-3.0-or-later',
                     shipped=True, source='actual signed runtime file; MiniJMP-developed source',
                     kind='file')
    item['hashes'] = [{'alg': 'SHA-256', 'content': sha256_file(path)}]
    return item


def generate(runtime, destination, build=None):
    runtime, destination = Path(runtime), Path(destination)
    build = Path(build) if build is not None else ROOT / 'build/windows-pkg-V1.0/work/MiniJMP'
    destination.mkdir(parents=True, exist_ok=True)
    commit = subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip()
    collected = toc_sources(build)
    lock = ROOT / 'packaging/windows/requirements-py311.lock'
    hash_issues = hash_lock_mismatches(lock, HASH_LOCK)
    if hash_issues:
        raise ValueError('Invalid dependency hash lock: ' + '; '.join(hash_issues))
    wheel_hashes = hash_lock_entries(HASH_LOCK)
    verified_wheels = verified_install_hashes(lock, HASH_LOCK)
    locked = {canonicalize_name(name): version for name, version in
              (line.split('==', 1) for line in lock.read_text().splitlines()
               if '==' in line and not line.startswith('#'))}
    direct = {canonicalize_name(Requirement(line).name) for line in (ROOT / 'requirements.txt').read_text().splitlines()
              if line.strip() and not line.startswith('#')}
    components, owners = [], {}
    license_dir = runtime / 'THIRD-PARTY-LICENSES'
    license_dir.mkdir(exist_ok=True)
    distributions = {canonicalize_name(d.metadata['Name']): d for d in metadata.distributions()}
    for name, version in locked.items():
        if distributions[name].version != version:
            raise ValueError(f'Lock drift: {name}')
    refs = {}
    runtime_names = {canonicalize_name(d.metadata['Name']) for d in _runtime_dependencies()}
    runtime_names.discard('pyinstaller')
    test_names = dependency_closure(('pytest',), distributions)
    for key, dist in sorted(distributions.items()):
        installed = {str(Path(dist.locate_file(f)).resolve()).lower() for f in dist.files or ()}
        shipped = bool(installed & collected)
        license_name, expression, license_status = license_fields(dist)
        urls = dist.metadata.get_all('Project-URL', [])
        url = dist.metadata.get('Home-page') or ''
        if not url:
            for entry in urls:
                label, separator, value = entry.partition(',')
                if separator and label.strip().lower() in {'homepage', 'repository', 'source', 'source code'}:
                    url = value.strip()
                    break
        url = url or f'https://pypi.org/project/{key}/'
        if key in runtime_names:
            usage = 'runtime-direct' if key in direct else 'runtime-transitive'
        elif key == 'pyinstaller':
            usage = 'build-only'
        elif key in test_names:
            usage = 'test-only'
        else:
            usage = 'build-only' if key in locked else 'additional build-environment package'
        if key == 'pyinstaller':
            source = 'locked PyPI build-tool wheel; bootloader is listed as a separate runtime component'
        elif key in locked and verified_wheels:
            source = 'PyPI Windows CPython 3.11 wheel; installed artifact SHA-256 verified by pip report'
        elif key in locked:
            source = 'approved PyPI Windows CPython 3.11 wheel; existing environment origin unverified'
        else:
            source = 'additional installed build-environment distribution; not in version lock'
        item = component(dist.metadata['Name'], dist.version, url, license_name, shipped=shipped,
                         source=source, usage=usage, license_status=license_status,
                         license_metadata=dist.metadata.get('License', '') or license_name)
        if expression:
            item['licenses'] = [{'expression': expression}]
        if key in wheel_hashes:
            digests = ([verified_wheels[key][1]] if verified_wheels and key in verified_wheels
                       else wheel_hashes[key][2])
            item['hashes'] = [{'alg': 'SHA-256', 'content': digest} for digest in digests]
            item['properties'].append({'name': 'minijmp:hash_scope', 'value':
                                       'pip-verified installed wheel' if verified_wheels else
                                       'approved wheel artifact; existing installation not verified'})
        item['purl'] = f'pkg:pypi/{key}@{dist.version}'
        refs[key] = item['bom-ref']
        components.append(item)
        for path in installed:
            owners[path] = item
        if shipped:
            for relative, source in _license_files(dist):
                target = license_dir / (re.sub(r'[^A-Za-z0-9._-]+', '_', dist.metadata['Name']) + '-' + dist.version + '-' + re.sub(r'[^A-Za-z0-9._-]+', '_', str(relative)))
                shutil.copyfile(source, target)
    embedded = [
        ('PandasTable / DataExplore', '0.13 (DataExplore display; pandastable revision unknown)', 'https://github.com/dmnfarrell/pandastable', 'GNU GPL v3 or later', 'GPL-3.0-or-later', True, 'code/pandastable_local/; Copyright (C) Damien Farrell 2014-'),
        ('BlakerCI translated routines', '1.0-6', 'https://cran.r-project.org/package=BlakerCI', 'GNU GPL v3', 'GPL-3.0-only', True, 'code/blakerCI.py; Jan Klaschka'),
        ('Hmisc hoeffd.s translation', 'unknown', 'https://hbiostat.org/R/Hmisc/', 'GNU GPL v2 or later; copied revision unknown', 'GPL-2.0-or-later', True, 'code/nonpara_cor.py; Frank E Harrell Jr and contributors'),
        ('hoeffdings_d_explainer snippet', 'unknown', 'https://github.com/Dicklesworthstone/hoeffdings_d_explainer', '待确认：未找到授权声明，正式分发阻断', '', True, 'code/nonpara_cor.py::hoeffd_example; Dicklesworthstone'),
        ('PI-Data-Viewer adapter', 'unknown', 'https://github.com/summeredge/PI-Data-Viewer', '待确认：来源项目未找到独立LICENSE', '', True, 'code/pi_reader.py; source comment identifies PI-Data-Viewer/backend/pi_reader.py'),
        ('MiniJMP PIReader', 'unknown', 'https://github.com/summeredge/Minijmp', 'GNU GPL version 3 or later; see LICENSE', 'GPL-3.0-or-later', True, 'PIReader/ source; in-house development confirmed by project owner'),
        ('Carbon Icons', '11.91.0', 'https://github.com/carbon-design-system/carbon', 'Apache License 2.0', 'Apache-2.0', True, 'code/icon_resource.py; IBM Carbon'),
        ('Tabler Icons', 'a4ce1404bc6d24d3c365afe7b258d6bf6f48d62d', 'https://github.com/tabler/tabler-icons', 'MIT License', 'MIT', True, 'code/icon_resource.py; Paweł Kuna'),
        ('Python runtime', sys.version.split()[0], 'https://www.python.org/', 'Python Software Foundation License', 'PSF-2.0', True, 'CPython runtime including standard library; not pip packages'),
    ]
    import tkinter
    tcl = tkinter.Tcl()
    embedded.append(('Tcl/Tk', tcl.call('info', 'patchlevel'), 'https://www.tcl-lang.org/', 'Tcl/Tk license terms', 'TCL', True, 'CPython Tcl/Tk distribution; THIRD-PARTY-LICENSES/Tcl-Tk-license.terms'))
    for args in embedded:
        name, version, url, license_name, spdx, shipped, source = args
        components.append(component(name, version, url, license_name, spdx, shipped, source))
    components.extend(pi_runtime_components(runtime))
    if (runtime / 'MiniJMP.exe').is_file() and 'pyinstaller' in distributions:
        dist = distributions['pyinstaller']
        license_name, expression, license_status = license_fields(dist)
        url = dist.metadata.get('Home-page') or 'https://pypi.org/project/pyinstaller/'
        bootloader = component(
            'PyInstaller bootloader', dist.version, url, license_name, shipped=True,
            source='embedded in MiniJMP.exe; executable SHA-256 is recorded on MiniJMP.exe',
            kind='framework', license_status=license_status, usage='runtime-embedded',
            source_distribution=f'pkg:pypi/pyinstaller@{dist.version}')
        if expression:
            bootloader['licenses'] = [{'expression': expression}]
        components.append(bootloader)
    collect_toc = ast.literal_eval((build / 'COLLECT-00.toc').read_text(encoding='utf-8'))
    source_paths = {}
    def mappings(value):
        if isinstance(value, (tuple, list)):
            if len(value) == 3 and all(isinstance(v, str) for v in value) and Path(value[1]).is_absolute():
                source_paths[value[0].replace('\\', '/')] = value[1]
            for child in value:
                mappings(child)
    mappings(collect_toc)
    for filename in ('BlakerCI-DESCRIPTION.txt', 'Hmisc-DESCRIPTION.txt'):
        shutil.copyfile(ROOT / 'packaging/windows/licenses' / filename, license_dir / filename)
    inventory = []
    for path in sorted(runtime.rglob('*')):
        if not path.is_file():
            continue
        relative = path.relative_to(runtime).as_posix()
        if relative == 'MiniJMP.exe':
            components.append(minijmp_runtime_component(path))
            inventory.append([relative, sha256_file(path), path.stat().st_size,
                              'MiniJMP', 'signed runtime artifact; MiniJMP-developed source'])
            continue
        if relative in {f'PIReader/{name}' for name in PI_RUNTIME_FILES}:
            owner = 'MiniJMP PIReader' if path.name == 'PIReader.exe' else 'OSIsoft PI SDK'
            source = 'signed runtime artifact; project source build' if path.name == 'PIReader.exe' else 'third-party SDK runtime file'
            inventory.append([relative, sha256_file(path), path.stat().st_size, owner, source])
            continue
        source = source_paths.get(relative.removeprefix('_internal/'), '')
        owner = owners.get(str(Path(source).resolve()).lower()) if source else None
        inventory.append([relative, sha256_file(path), path.stat().st_size, owner['name'] if owner else '', source])
        if path.suffix.lower() in ('.dll', '.pyd', '.exe'):
            version = file_version(path)
            owner_props = {p['name'].split(':', 1)[1]: p['value'] for p in owner['properties']} if owner else {}
            item = component(relative, version or 'unknown',
                             owner['externalReferences'][0]['url'] if owner else 'https://www.python.org/' if source.lower().startswith(sys.base_prefix.lower()) else '',
                             'See parent component license and bundled notices' if owner else '待确认：运行组件独立许可需人工核对',
                             shipped=True, source=source or 'actual release file', kind='file',
                             owner=owner['name'] if owner else 'runtime/vendor; see bundled license texts',
                             version_status='file-version-resource' if version else 'no-file-version-resource',
                             license_status=owner_props.get('license_status', 'review-required'))
            if owner:
                item['licenses'] = owner['licenses']
            item['hashes'] = [{'alg': 'SHA-256', 'content': sha256_file(path)}]
            components.append(item)
    dependencies = []
    for key, dist in sorted(distributions.items()):
        targets = []
        for text in dist.requires or ():
            req = Requirement(text)
            if (not req.marker or req.marker.evaluate({'extra': ''})) and canonicalize_name(req.name) in refs:
                targets.append(refs[canonicalize_name(req.name)])
        dependencies.append({'ref': refs[key], 'dependsOn': sorted(set(targets))})
    bom = {'bomFormat': 'CycloneDX', 'specVersion': '1.6', 'serialNumber': 'urn:uuid:' + str(uuid.uuid4()), 'version': 1,
           'metadata': {'timestamp': datetime.now(timezone.utc).isoformat(),
                        'component': {'type': 'application', 'name': 'MiniJMP', 'version': '1.0.0', 'bom-ref': 'MiniJMP'},
                        'properties': properties(commit=commit, tag='v1.0.0', lock_sha256=sha256_file(lock),
                                                 hash_lock_sha256=sha256_file(HASH_LOCK),
                                                 review_status='授权与未知许可未放行；供内部审核')},
           'components': components, 'dependencies': dependencies}
    assert len({c['bom-ref'] for c in components}) == len(components)
    (destination / 'SBOM.cdx.json').write_text(json.dumps(bom, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    with (destination / 'SBOM.csv').open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.writer(handle)
        writer.writerow(['名称', '实际版本', '上游地址', '许可证', '来源与用途', '随包分发', '待确认状态', 'SHA256'])
        for item in components:
            props = {p['name'].split(':', 1)[1]: p['value'] for p in item['properties']}
            writer.writerow([item['name'], item['version'], item.get('externalReferences', [{}])[0].get('url', ''),
                             json.dumps(item['licenses'], ensure_ascii=False), props.get('source', ''), props['distributed'],
                             props['license_status'], item.get('hashes', [{}])[0].get('content', '')])
    with (destination / 'RUNTIME-CONTENTS.csv').open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.writer(handle)
        writer.writerow(['相对路径', 'SHA256', '字节数', '安装包归属', '构建来源'])
        writer.writerows(inventory)
    print(f'PASS: SBOM components={len(components)}; runtime files={len(inventory)}; commit={commit}')
    return bom


if __name__ == '__main__':
    if len(sys.argv) not in (3, 4):
        raise SystemExit('Usage: write_release_sbom.py RUNTIME_DIRECTORY AUDIT_DIRECTORY [PYINSTALLER_WORK_DIRECTORY]')
    generate(*sys.argv[1:])
