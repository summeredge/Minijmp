"""Release inventory tests: no statistical computation or package build."""

import importlib.util
from pathlib import Path
import sys

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
