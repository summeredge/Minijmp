"""Release inventory tests: no statistical computation or package build."""

import importlib.util
from importlib.metadata import PathDistribution
import csv
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

TOOLS = Path(__file__).resolve().parents[1] / 'tools'
sys.path.insert(0, str(TOOLS))
import write_release_sbom as sbom


def test_toc_inventory_excludes_available_but_uncollected_modules(tmp_path):
    shipped = str((tmp_path / 'shipped.py').resolve())
    available = str((tmp_path / 'uncollected.py').resolve())
    native = str((tmp_path / 'vendor.dll').resolve())
    (tmp_path / 'PYZ-00.toc').write_text(repr(('out.pyz', [('module', shipped, 'PYMODULE')])), encoding='utf-8')
    (tmp_path / 'COLLECT-00.toc').write_text(repr([('vendor.dll', native, 'BINARY')]), encoding='utf-8')
    (tmp_path / 'Analysis-00.toc').write_text(repr([('available', available, 'PYMODULE')]), encoding='utf-8')
    assert sbom.toc_sources(tmp_path) == {shipped.lower(), native.lower()}
    (tmp_path / 'COLLECT-00.toc').unlink()
    with pytest.raises(FileNotFoundError):
        sbom.toc_sources(tmp_path)


def test_unknown_license_is_preserved_without_inventing_spdx():
    item = sbom.component('copied snippet', '', 'https://example.com/', '授权待确认', shipped=True)
    assert item['version'] == 'unknown'
    assert item['licenses'] == [{'license': {'name': '授权待确认'}}]
    props = {p['name']: p['value'] for p in item['properties']}
    assert props['minijmp:distributed'] == 'true'
    assert props['minijmp:license_status'] == 'review-required'


def test_declared_license_without_spdx_is_not_marked_unlicensed():
    item = sbom.component('sample', '1.0', '', 'MIT License', shipped=True)
    props = {p['name']: p['value'] for p in item['properties']}
    assert item['licenses'] == [{'license': {'name': 'MIT License'}}]
    assert props['minijmp:license_status'] == 'declared-no-SPDX'


def test_pinned_sbom_package_hash_is_the_approved_windows_wheel_hash():
    entries = sbom.hash_lock_entries()
    assert len(entries) == 43
    assert entries['numpy'][0:2] == ('numpy', '2.4.6')
    assert len(entries['numpy'][2]) == 1
    assert len(entries['numpy'][2][0]) == 64


def test_dependency_closure_respects_extra_markers_and_cycles():
    distributions = {
        'pytest': SimpleNamespace(requires=['pluggy>=1', 'optional; extra == "test"']),
        'pluggy': SimpleNamespace(requires=['pytest>=8']),
    }
    assert sbom.dependency_closure(('pytest',), distributions) == {'pytest', 'pluggy'}


def test_minijmp_runtime_executable_keeps_project_identity_and_hash(tmp_path, monkeypatch):
    executable = tmp_path / 'MiniJMP.exe'
    executable.write_bytes(b'signed MiniJMP')
    monkeypatch.setattr(sbom, 'file_version', lambda path: '1.0.0.0')

    item = sbom.minijmp_runtime_component(executable)

    assert item['name'] == 'MiniJMP.exe'
    assert item['version'] == '1.0.0.0'
    assert item['hashes'] == [{'alg': 'SHA-256', 'content': sbom.sha256_file(executable)}]
    assert item['licenses'] == [{'license': {'id': 'GPL-3.0-or-later'}}]
    props = {p['name']: p['value'] for p in item['properties']}
    assert props['minijmp:distributed'] == 'true'
    assert props['minijmp:source'] == 'actual signed runtime file; MiniJMP-developed source'


def test_generated_sbom_classifies_runtime_dependency_and_signed_executable(tmp_path, monkeypatch):
    project = tmp_path / 'project'
    site = project / 'site-packages'
    dist_info = site / 'sample-1.0.dist-info'
    license_file = dist_info / 'licenses' / 'LICENSE.txt'
    package_file = site / 'sample' / '__init__.py'
    license_file.parent.mkdir(parents=True)
    package_file.parent.mkdir()
    (dist_info / 'METADATA').write_text(
        'Metadata-Version: 2.1\nName: sample\nVersion: 1.0\nLicense: MIT\n'
        'License-File: LICENSE.txt\nHome-page: https://example.com/sample\n', encoding='utf-8')
    license_file.write_text('MIT License text', encoding='utf-8')
    package_file.write_text('# runtime package', encoding='utf-8')
    (dist_info / 'RECORD').write_text(
        'sample-1.0.dist-info/METADATA,,\n'
        'sample-1.0.dist-info/licenses/LICENSE.txt,,\n'
        'sample/__init__.py,,\n', encoding='utf-8')
    distribution = PathDistribution(dist_info)
    pyinstaller_info = site / 'pyinstaller-6.22.3.dist-info'
    pyinstaller_info.mkdir()
    (pyinstaller_info / 'METADATA').write_text(
        'Metadata-Version: 2.1\nName: PyInstaller\nVersion: 6.22.3\n'
        'License: GPL-2.0-or-later with bootloader exception\n', encoding='utf-8')
    pyinstaller = PathDistribution(pyinstaller_info)

    packaging = project / 'packaging' / 'windows'
    packaging.mkdir(parents=True)
    (packaging / 'requirements-py311.lock').write_text(
        'sample==1.0\npyinstaller==6.22.3\n', encoding='utf-8')
    digest = 'a' * 64
    pyinstaller_digest = 'b' * 64
    hash_lock = packaging / 'requirements-py311-hashed.lock'
    hash_lock.write_text(f'sample==1.0 --hash=sha256:{digest}\n'
                         f'pyinstaller==6.22.3 --hash=sha256:{pyinstaller_digest}\n', encoding='utf-8')
    (project / 'requirements.txt').write_text('sample\n', encoding='utf-8')
    licenses = packaging / 'licenses'
    licenses.mkdir()
    (licenses / 'BlakerCI-DESCRIPTION.txt').write_text('BlakerCI', encoding='utf-8')
    (licenses / 'Hmisc-DESCRIPTION.txt').write_text('Hmisc', encoding='utf-8')

    build = tmp_path / 'build'
    build.mkdir()
    (build / 'PYZ-00.toc').write_text(
        repr(('out.pyz', [('sample', str(package_file.resolve()), 'PYMODULE')])), encoding='utf-8')
    (build / 'COLLECT-00.toc').write_text('[]', encoding='utf-8')
    (build / 'Analysis-00.toc').write_text('[]', encoding='utf-8')
    runtime = tmp_path / 'runtime'
    runtime.mkdir()
    (runtime / 'MiniJMP.exe').write_bytes(b'signed executable')

    monkeypatch.setattr(sbom, 'ROOT', project)
    monkeypatch.setattr(sbom, 'HASH_LOCK', hash_lock)
    monkeypatch.setattr(sbom.subprocess, 'check_output', lambda *args, **kwargs: 'a' * 40)
    monkeypatch.setattr(sbom.metadata, 'distributions', lambda: [distribution, pyinstaller])
    monkeypatch.setattr(sbom, '_runtime_dependencies', lambda: [distribution])
    monkeypatch.setattr(sbom, 'file_version', lambda path: '1.0.0.0')

    bom = sbom.generate(runtime, tmp_path / 'audit', build)
    package = next(item for item in bom['components'] if item['name'] == 'sample')
    props = {item['name']: item['value'] for item in package['properties']}
    assert props['minijmp:distributed'] == 'true'
    assert props['minijmp:usage'] == 'runtime-direct'
    assert props['minijmp:license_status'] == 'declared-no-SPDX'
    assert props['minijmp:hash_scope'] == 'approved wheel artifact; existing installation not verified'
    assert package['hashes'] == [{'alg': 'SHA-256', 'content': digest}]
    executable = next(item for item in bom['components'] if item['name'] == 'MiniJMP.exe')
    assert executable['hashes'][0]['content'] == sbom.sha256_file(runtime / 'MiniJMP.exe')
    pyinstaller_package = next(item for item in bom['components'] if item['name'] == 'PyInstaller')
    pyinstaller_props = {item['name']: item['value'] for item in pyinstaller_package['properties']}
    assert pyinstaller_props['minijmp:distributed'] == 'false'
    assert pyinstaller_props['minijmp:usage'] == 'build-only'
    bootloader = next(item for item in bom['components'] if item['name'] == 'PyInstaller bootloader')
    bootloader_props = {item['name']: item['value'] for item in bootloader['properties']}
    assert bootloader_props['minijmp:distributed'] == 'true'
    assert bootloader_props['minijmp:source_distribution'] == 'pkg:pypi/pyinstaller@6.22.3'
    assert 'hashes' not in bootloader
    with (tmp_path / 'audit' / 'SBOM.csv').open(encoding='utf-8-sig', newline='') as handle:
        rows = list(csv.DictReader(handle))
    assert next(row for row in rows if row['名称'] == 'sample')['SHA256'] == digest


def test_pi_executable_hash_comes_from_runtime_copy(tmp_path, monkeypatch):
    repo_exe = tmp_path / 'repo' / 'PIReader' / 'PIReader.exe'
    runtime_exe = tmp_path / 'runtime' / 'PIReader' / 'PIReader.exe'
    repo_exe.parent.mkdir(parents=True)
    runtime_exe.parent.mkdir(parents=True)
    repo_exe.write_bytes(b'old unsigned repository copy')
    runtime_exe.write_bytes(b'signed runtime copy')
    monkeypatch.setattr(sbom, 'file_version', lambda path: '2.4.0.0')

    components = sbom.pi_runtime_components(runtime_exe.parents[1])
    executable = next(item for item in components if item['name'] == 'PIReader.exe')
    properties = {p['name']: p['value'] for p in executable['properties']}

    assert executable['version'] == '2.4.0.0'
    assert executable['hashes'] == [{'alg': 'SHA-256', 'content': sbom.sha256_file(runtime_exe)}]
    assert executable['hashes'][0]['content'] != sbom.sha256_file(repo_exe)
    assert properties['minijmp:distributed'] == 'true'
    assert properties['minijmp:source'] == 'signed runtime artifact: PIReader/PIReader.exe; MiniJMP-developed source'
