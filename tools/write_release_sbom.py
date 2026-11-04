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
from write_third_party_notices import _license_files, _license_summary

ROOT = Path(__file__).resolve().parents[1]


def properties(**values):
    return [{'name': 'minijmp:' + name, 'value': str(value)} for name, value in values.items()]


def component(name, version, url, license_name, spdx='', shipped=False, source='', kind='library', **extra):
    row = {'type': kind, 'bom-ref': 'urn:uuid:' + str(uuid.uuid4()),
           'name': name, 'version': version or 'unknown',
           'licenses': [{'license': {'id': spdx} if spdx else {'name': license_name or '待确认'}}],
           'properties': properties(distributed=str(shipped).lower(), source=source,
                                    license_status='confirmed' if spdx else 'review-required', **extra)}
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
    # Preserve explicit upstream SPDX expressions; do not guess from project names.
    summary = _license_summary(dist)
    if expression:
        return summary, expression
    return summary, ''


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


def generate(runtime, destination):
    runtime, destination = Path(runtime), Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    commit = subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip()
    collected = toc_sources(ROOT / 'build/windows-pkg-V1.0/work/MiniJMP')
    lock = ROOT / 'packaging/windows/requirements-py311.lock'
    locked = dict(line.split('==', 1) for line in lock.read_text().splitlines() if '==' in line and not line.startswith('#'))
    direct = {canonicalize_name(Requirement(line).name) for line in (ROOT / 'requirements.txt').read_text().splitlines()
              if line.strip() and not line.startswith('#')}
    components, owners = [], {}
    license_dir = runtime / 'THIRD-PARTY-LICENSES'
    license_dir.mkdir(exist_ok=True)
    distributions = {canonicalize_name(d.metadata['Name']): d for d in metadata.distributions()}
    for name, version in locked.items():
        if distributions[canonicalize_name(name)].version != version:
            raise ValueError(f'Lock drift: {name}')
    refs = {}
    for key, dist in sorted(distributions.items()):
        installed = {str(Path(dist.locate_file(f)).resolve()).lower() for f in dist.files or ()}
        shipped = bool(installed & collected) or key == 'pyinstaller'
        license_name, expression = license_fields(dist)
        urls = dist.metadata.get_all('Project-URL', [])
        url = dist.metadata.get('Home-page') or (urls[0].split(', ', 1)[-1] if urls else f'https://pypi.org/project/{key}/')
        item = component(dist.metadata['Name'], dist.version, url, license_name, shipped=shipped,
                         source='locked-build-environment' if key in {canonicalize_name(n) for n in locked} else 'actual-build-environment',
                         usage='direct' if key in direct else 'transitive-or-build',
                         license_metadata=dist.metadata.get('License', '') or license_name)
        if expression:
            item['licenses'] = [{'expression': expression}]
            item['properties'] = [p for p in item['properties'] if p['name'] != 'minijmp:license_status'] + properties(license_status='upstream-SPDX')
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
        ('PI-Data-Viewer adapter', 'unknown', 'https://github.com/summeredge/PI-Data-Viewer', '待确认：来源项目未找到独立LICENSE', '', True, 'code/pi_reader.py; PIReader source in source ZIP'),
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
    for name in ('PIReader.exe', 'OSIsoft.PISDK.dll', 'OSIsoft.PISDKCommon.dll', 'OSIsoft.PITimeServer.dll'):
        path = ROOT / 'PIReader' / name
        item = component(name, file_version(path) if path.exists() else 'unknown',
                         'https://www.aveva.com/' if name.endswith('.dll') else 'https://github.com/summeredge/PI-Data-Viewer',
                         '专有组件；再分发授权未确认' if name.endswith('.dll') else '来源许可待确认',
                         source='local optional PI input; excluded from both release ZIPs', kind='file')
        if path.is_file():
            item['hashes'] = [{'alg': 'SHA-256', 'content': sha256_file(path)}]
        components.append(item)
    collect_toc = ast.literal_eval((ROOT / 'build/windows-pkg-V1.0/work/MiniJMP/COLLECT-00.toc').read_text(encoding='utf-8'))
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
        source = source_paths.get(relative.removeprefix('_internal/'), '')
        owner = owners.get(str(Path(source).resolve()).lower()) if source else None
        inventory.append([relative, sha256_file(path), path.stat().st_size, owner['name'] if owner else '', source])
        if path.suffix.lower() in ('.dll', '.pyd', '.exe'):
            version = file_version(path)
            item = component(relative, version or 'unknown',
                             owner['externalReferences'][0]['url'] if owner else 'https://www.python.org/' if source.lower().startswith(sys.base_prefix.lower()) else '',
                             'See parent component license and bundled notices' if owner else '待确认：运行组件独立许可需人工核对',
                             shipped=True, source=source or 'actual release file', kind='file',
                             owner=owner['name'] if owner else 'runtime/vendor; see bundled license texts',
                             version_status='file-version-resource' if version else 'no-file-version-resource')
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
    if len(sys.argv) != 3:
        raise SystemExit('Usage: write_release_sbom.py RUNTIME_DIRECTORY AUDIT_DIRECTORY')
    generate(*sys.argv[1:])
