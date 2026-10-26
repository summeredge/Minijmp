"""Focused checks for the Windows release tooling; builds and packages nothing."""

import json
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

import pi_import


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / 'tools'
sys.path.insert(0, str(TOOLS))

import make_zip
import release_env
import release_metadata
import smoke_launch


def test_make_zip_writes_chinese_names_without_caches_and_refuses_overwrite(tmp_path):
    source = tmp_path / 'MiniJMP-V0.1-beta2'
    (source / 'help' / 'pages').mkdir(parents=True)
    (source / 'help' / 'pages' / '操作说明.html').write_text('中文帮助', encoding='utf-8')
    (source / 'PIReader').mkdir()
    (source / 'PIReader' / 'config.txt').write_text('Server=172.31.0.10\n', encoding='utf-8')
    (source / '__pycache__').mkdir()
    (source / '__pycache__' / 'stale.pyc').write_bytes(b'\0')
    (source / 'PIReader' / 'obj').mkdir()
    (source / 'PIReader' / 'obj' / 'Debug.cache').write_text('cache', encoding='utf-8')
    destination = tmp_path / 'out.zip'

    assert make_zip.zip_directory(source, destination) == 2
    with zipfile.ZipFile(destination) as archive:
        names = archive.namelist()
        assert 'MiniJMP-V0.1-beta2/help/pages/操作说明.html' in names
        assert archive.testzip() is None
    assert not [name for name in names if '__pycache__' in name or '/obj/' in name]
    assert make_zip.archive_entry_sha256(destination, names[0]) == make_zip.sha256_file(
        source / 'help' / 'pages' / '操作说明.html')
    with pytest.raises(FileExistsError):
        make_zip.zip_directory(source, destination)


def test_stable_sha256_requires_three_equal_content_reads(tmp_path):
    target = tmp_path / 'MiniJMP.zip'
    target.write_bytes(b'first')
    sleeps = []
    reads = iter([
        ('A', b'first'), ('B', b'second'), ('C', b'second'), ('D', b'second')])

    def digest(_path):
        return next(reads)[0]

    with pytest.raises(RuntimeError, match='changed after it was written'):
        make_zip.stable_sha256(target, settle=0, interval=15, attempts=3,
                               sleep=sleeps.append, digest=digest)
    assert sleeps == [15]

    reads = iter(['X', 'X', 'X'])
    sleeps.clear()
    assert make_zip.stable_sha256(target, settle=0, interval=15, attempts=3,
                                  sleep=sleeps.append, digest=lambda _: next(reads)) == 'X'
    assert sleeps == [15, 15]


def test_dlp_container_and_source_layout_rules(tmp_path):
    encrypted = tmp_path / 'doc.xlsx'
    encrypted.write_bytes(b'%TSD-Header-###% rest')
    (tmp_path / 'plain.txt').write_text('ok', encoding='utf-8')
    assert make_zip.find_encrypted_containers(tmp_path) == [encrypted]
    assert make_zip.find_encrypted_containers(encrypted) == [encrypted]

    repo = tmp_path / 'repo'
    (repo / 'code').mkdir(parents=True)
    (repo / 'code' / 'kept.py').write_text('x = 1\n', encoding='utf-8')
    (repo / 'code' / '__pycache__').mkdir()
    (repo / 'code' / '__pycache__' / 'x.pyc').write_bytes(b'\0')
    (repo / 'PIReader' / 'obj').mkdir(parents=True)
    (repo / 'PIReader' / 'obj' / 'cache.bin').write_text('cache', encoding='utf-8')
    (repo / 'untracked_tool.py').write_text('print(1)\n', encoding='utf-8')
    for name in make_zip.SOURCE_FILES:
        (repo / name).write_text('x', encoding='utf-8')
    for name in make_zip.SOURCE_DIRS:
        (repo / name).mkdir(exist_ok=True)
    (repo / 'tools' / 'make_zip.py').write_text('# untracked tool\n', encoding='utf-8')
    staged = make_zip.stage_source(repo, tmp_path / 'stage')
    staged_names = sorted(path.relative_to(tmp_path / 'stage').as_posix() for path in staged)
    assert staged_names == sorted(['code/kept.py', 'tools/make_zip.py', *make_zip.SOURCE_FILES])


def test_source_stage_excludes_local_configs_and_temporary_outputs(tmp_path):
    repo = tmp_path / 'repo'
    repo.mkdir()
    for name in make_zip.SOURCE_FILES:
        (repo / name).write_text('x', encoding='utf-8')
    for name in make_zip.SOURCE_DIRS:
        (repo / name).mkdir(parents=True, exist_ok=True)

    keep = ('code/app.py', 'PIReader/Program.cs', 'docs/accepted.png',
            'tests/fixtures/kept.csv')
    exclude = (
        'code/.env.local', 'code/local_settings.py', 'code/backup.bak',
        'code/output.orig', 'code/.temp.swp', 'PIReader/config.txt',
        'PIReader/OSIsoft.PISDK.dll', 'PIReader/OSIsoft.PISDKCommon.dll',
        'PIReader/OSIsoft.PITimeServer.dll', 'docs/run.log', 'tests/result.tmp',
        'docs/draft-chart.png', 'docs/chart.draft.png', 'docs/chart_draft.png',
        'docs/~$slide.xlsx', 'docs/.DS_Store', 'docs/Thumbs.db',
        'docs/release/pyinstaller-build-V0.1-beta3.txt',
        'docs/release/build-inputs-V0.1-beta3.txt',
        'docs/_build/nested/index.html', 'PIReader/.vs/Project/cache.bin',
    )
    for relative in keep + exclude:
        path = repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('test fixture', encoding='utf-8')

    stage = tmp_path / 'stage'
    staged = make_zip.stage_source(repo, stage)
    names = {path.relative_to(stage).as_posix() for path in staged}

    assert set(keep) <= names
    assert not set(exclude) & names, sorted(set(exclude) & names)
    assert set(make_zip.SOURCE_FILES) <= names

    archive = tmp_path / 'source.zip'
    make_zip.zip_directory(stage, archive, root_name='MiniJMP-source')
    with zipfile.ZipFile(archive) as source_zip:
        archive_names = set(source_zip.namelist())
    assert {f'MiniJMP-source/{name}' for name in keep} <= archive_names
    assert not {f'MiniJMP-source/{name}' for name in exclude} & archive_names


def test_smoke_launch_ignores_placeholder_tk_window(monkeypatch):
    assert smoke_launch.is_app_window('未命名项目 — 工作表1 - Minijmp')
    assert smoke_launch.is_app_window('C:/data/a.dexpl — 工作表2 - Minijmp')
    assert not smoke_launch.is_app_window('tk')
    assert not smoke_launch.is_app_window('')
    assert not smoke_launch.is_app_window('Notepad')

    class Alive:
        returncode = None

        def poll(self):
            return None

    seen = iter([['tk'], ['tk', '未命名项目 — 工作表1 - Minijmp']])
    found, _elapsed, _all = smoke_launch.wait_for_window(
        Alive(), 90, titles=lambda: next(seen), sleep=lambda _seconds: None)
    assert found == ['未命名项目 — 工作表1 - Minijmp']


def test_python_version_gate_accepts_311_and_newer(tmp_path):
    lock = tmp_path / 'lock.txt'
    lock.write_text('numpy==2.4.6\n', encoding='utf-8')
    installed = {'numpy': '2.4.6'}.__getitem__
    kwargs = dict(lock=lock, installed=installed, pip_ok=True, pyinstaller='6.22.3', bits=64)

    for version in ((3, 11, 9), (3, 12, 3), (3, 13, 0)):
        levels = release_env.assess(version_info=version, **kwargs)
        assert ('BLOCKED', ) not in levels
        assert levels[0][0] == 'PASS'

    # Python 3.11 must still match the lock; newer interpreters only record drift.
    installed = {'numpy': '1.0.0'}.__getitem__
    old = release_env.assess((3, 11, 9), lock=lock, installed=installed, pip_ok=True,
                             pyinstaller='6.22.3', bits=64)
    new = release_env.assess((3, 12, 3), lock=lock, installed=installed, pip_ok=True,
                             pyinstaller='6.22.3', bits=64)
    assert any(level == 'BLOCKED' for level, _ in old)
    assert any(level == 'WARNING' and 'Python 3.12.3' in text for level, text in new)
    assert any(level == 'BLOCKED' for level, _ in release_env.assess(
        (3, 10, 14), **kwargs))


def test_version_identifiers_and_build_info_agree():
    levels = release_metadata.check()
    assert [level for level, _ in levels] == ['PASS'], levels
    assert 'V0.1-beta3' in levels[0][1] and '0.1.0.3' in levels[0][1]
    script = (ROOT / 'tools' / 'build_windows_release.ps1').read_text(encoding='utf-8')
    assert '$productVersion = ' + "'v0.1.0-beta.3'" in script
    assert 'Release name: $releaseVersion' in script
    assert 'PIReader: bundled beside MiniJMP.exe' in script
    assert 'PI SDK/PIPC runtime and PI Server connectivity' in script
    version_info = (ROOT / 'packaging' / 'windows' / 'version_info.txt').read_text(encoding='utf-8')
    assert "StringStruct('Comments', 'Windows beta release 3')" in version_info


def test_pireader_paths_resolve_beside_frozen_exe(monkeypatch, tmp_path, tk_root):
    install = tmp_path / 'MiniJMP-V0.1-beta2'
    (install / 'PIReader').mkdir(parents=True)
    internal = install / '_internal' / 'code'
    internal.mkdir(parents=True)
    (install / 'PIReader' / 'PIReader.exe').write_bytes(b'MZ')
    (install / 'PIReader' / 'config.txt').write_text('Server=1\n', encoding='utf-8')

    stored = {}
    monkeypatch.setattr(pi_import, 'load_pi_paths', lambda: dict(stored))
    monkeypatch.setattr(pi_import, 'save_pi_paths', lambda paths: stored.update(paths))
    monkeypatch.delenv('PI_READER_EXE', raising=False)
    monkeypatch.delenv('PI_CONFIG', raising=False)
    monkeypatch.setattr(pi_import, '__file__', str(internal / 'pi_import.py'))
    monkeypatch.setattr(pi_import.sys, 'frozen', True, raising=False)
    monkeypatch.setattr(pi_import.sys, 'executable', str(install / 'MiniJMP.exe'))
    window = pi_import.PIImportDialog(tk_root)
    try:
        assert window.exe.get() == pi_import.normalize_pi_path(install / 'PIReader' / 'PIReader.exe')
        assert window.config.get() == pi_import.normalize_pi_path(install / 'PIReader' / 'config.txt')
        assert '_internal' not in window.exe.get()
    finally:
        window.cancel()


def test_powershell_scripts_parse_and_avoid_bulk_deletion():
    for name in ('build_windows_release.ps1', 'check_windows_release_ready.ps1'):
        script = TOOLS / name
        # Windows PowerShell 5.1 reads UTF-8 without a BOM as ANSI text.
        assert script.read_bytes().startswith(b'\xef\xbb\xbf')
        result = subprocess.run(
            ['powershell', '-NoProfile', '-Command',
             "$errors = $null; [void][System.Management.Automation.Language.Parser]::ParseFile("
             f"'{script}', [ref]$null, [ref]$errors); if ($errors) {{ $errors; exit 1 }}"],
            capture_output=True, text=True, timeout=120)
        assert result.returncode == 0, result.stdout + result.stderr
        text = script.read_text(encoding='utf-8')
        assert 'Remove-Item -Recurse -Force (Join-Path $root' not in text
        assert '-Confirm:$false' not in text
