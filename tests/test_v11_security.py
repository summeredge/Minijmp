"""V1.1 import limits and release gates, without statistical regression."""
import runpy
import sys
import zipfile
from pathlib import Path
from unittest.mock import Mock

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from pandastable_local import import_limits as limits
from pandastable_local.csv_import import read_csv
from test_csv_import import csv_app
from test_file_io import make_import_dialog
from worksheets import read_project_file, write_project_file

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('kind', ['csv', 'advanced', 'xlsx', 'project'])
def test_over_limit_keeps_current_workbook(csv_app, tmp_path, monkeypatch, kind):
    app, error = csv_app
    before = app.table.model.df.copy(deep=True)
    tabs = app.nb.tabs()
    filename = tmp_path / ('data.' + {'csv': 'csv', 'advanced': 'csv',
                                     'xlsx': 'xlsx', 'project': 'dexpl'}[kind])
    frame = pd.DataFrame({'a': [1, 2, 3], 'b': ['甲', '乙', '丙']})
    if kind == 'project':
        write_project_file(filename, {'A': {'table': frame, 'meta': {}}, 'meta': {}})
    elif kind == 'xlsx':
        frame.to_excel(filename, index=False)
    else:
        frame.to_csv(filename, index=False)
    monkeypatch.setattr(limits, 'MAX_CELLS', 4)
    if kind == 'advanced':
        dialog, error = make_import_dialog(filename, monkeypatch)
        dialog.doImport()
        assert dialog.df is None
        dialog.quit.assert_not_called()
    elif kind == 'csv':
        assert app.import_csv(filename=filename) is False
    elif kind == 'xlsx':
        assert app.load_excel(filename) is False
    else:
        assert app.load_file(filename) is False
    assert_frame_equal(app.table.model.df, before)
    assert app.nb.tabs() == tabs
    assert error.called


def test_reject_size_before_reading_or_parsing(tmp_path, monkeypatch):
    path = tmp_path / 'large.csv'
    path.write_bytes(b'a,b\n1,2\n')
    monkeypatch.setattr(limits, 'MAX_FILE_BYTES', 4)
    with pytest.raises(ValueError, match='256 MiB'):
        read_csv(path, 'utf-8', ',', True)
    monkeypatch.setattr(pd, 'read_csv', Mock(side_effect=AssertionError('must not parse')))
    with pytest.raises(ValueError, match='256 MiB'):
        limits.read_csv_bounded(path)


@pytest.mark.parametrize('suffix', ['.xlsx', '.dexpl'])
def test_zip_expansion_rejected_before_payload_parse(tmp_path, monkeypatch, suffix):
    path = tmp_path / ('bomb' + suffix)
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('manifest.json', b'0' * 1024)
    monkeypatch.setattr(limits, 'MAX_EXPANDED_BYTES', 100)
    with pytest.raises(ValueError, match='解压后'):
        (limits.check_excel if suffix == '.xlsx' else read_project_file)(path)


def test_parquet_dimensions_checked_before_arrow_allocation(tmp_path, monkeypatch):
    path = tmp_path / 'data.dexpl'
    write_project_file(path, {'A': {'table': pd.DataFrame({'a': [1, 2]}), 'meta': {}}, 'meta': {}})
    monkeypatch.setattr(limits, 'MAX_ROWS', 1)
    with pytest.raises(ValueError, match='导入上限'):
        read_project_file(path)


def test_csv_chunks_keep_identifiers_dates_and_order(tmp_path):
    path = tmp_path / 'ids.csv'
    path.write_text('id,date\n' + '001234567890123456789,2026-11-12\n' * 1001, encoding='utf-8')
    result = limits.read_csv_bounded(path, dtype=object)
    expected = pd.read_csv(path, dtype=object)
    assert_frame_equal(result, expected)


def test_cooperative_parser_deadline():
    with pytest.raises(ValueError, match='60 秒'):
        limits.check_deadline(limits.monotonic() - 61)


def test_archive_omits_staging_and_private_memory(tmp_path):
    sys.path.insert(0, str(ROOT / 'tools'))
    import make_zip
    for relative in ['.stage/old.txt', '.agent-memory/MEMORY.md', 'code/.stage/old.txt', 'kept.txt']:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('fixture')
    assert [p.relative_to(tmp_path).as_posix() for p in make_zip.package_files(tmp_path)] == ['kept.txt']


def test_long_frozen_install_path_reports_error_before_gui_import(tmp_path, monkeypatch):
    import tkinter
    from tkinter import messagebox
    root = Mock()
    monkeypatch.setattr(tkinter, 'Tk', lambda: root)
    error = Mock()
    monkeypatch.setattr(messagebox, 'showerror', error)
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    monkeypatch.setattr(sys, 'executable', str(tmp_path / ('a' * 81) / 'MiniJMP.exe'))
    with pytest.raises(SystemExit, match='1'):
        runpy.run_path(str(ROOT / 'packaging/windows_entrypoint.py'))
    error.assert_called_once()
    root.destroy.assert_called_once()


def test_formal_release_rejects_untrusted_signatures():
    script = (ROOT / 'tools/build_windows_release.ps1').read_text(encoding='utf-8-sig')
    check = script.index('Formal release requires valid, trusted Authenticode')
    assert check < script.index("$makeZip 'make' $releaseDir")
    assert '!$_.Trusted -or !$_.IntegrityVerified' in script


def test_version_checker_rejects_pireader_drift(monkeypatch):
    sys.path.insert(0, str(ROOT / 'tools'))
    import release_metadata
    found = release_metadata.identifiers()
    found['file:PIReader'] = '1.0.0.0'
    monkeypatch.setattr(release_metadata, 'identifiers', lambda root: found)
    assert any(level == 'BLOCKED' and 'file:PIReader' in msg for level, msg in release_metadata.check())
