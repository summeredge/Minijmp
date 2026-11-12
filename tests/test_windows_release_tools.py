"""Focused checks for the Windows release tooling; builds and packages nothing."""

import json
import subprocess
import sys
import zipfile
from xml.etree import ElementTree
from pathlib import Path

import pytest

import pi_import
import pi_reader


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
    (source / 'PIReader' / 'config.txt').write_text('Server=192.0.2.1\n', encoding='utf-8')
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


def test_manifest_covers_current_files_but_not_itself(tmp_path):
    source = tmp_path / 'source'
    source.mkdir()
    (source / 'SOURCE-BUNDLE-INFO.txt').write_text('bundle', encoding='utf-8')
    (source / 'THIRD-PARTY-NOTICES.txt').write_text('notices', encoding='utf-8')
    manifest = source / 'SOURCE-MANIFEST.txt'

    assert make_zip.write_manifest(source, manifest) == 2
    first = manifest.read_text(encoding='utf-8')
    assert 'SOURCE-BUNDLE-INFO.txt' in first
    assert 'THIRD-PARTY-NOTICES.txt' in first
    assert 'SOURCE-MANIFEST.txt' not in first

    assert make_zip.write_manifest(source, manifest) == 2
    assert manifest.read_text(encoding='utf-8') == first


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

    keep = ('code/app.py', 'PIReader/Program.cs', 'PIReader/config.example.txt',
            'PIReader/tags.example.txt', 'docs/accepted.png', 'tests/fixtures/kept.csv')
    exclude = (
        'code/.env.local', 'code/local_settings.py', 'code/backup.bak',
        'code/output.orig', 'code/.temp.swp', 'PIReader/config.txt', 'PIReader/tags.txt',
        'PIReader/OSIsoft.PISDK.dll', 'PIReader/OSIsoft.PISDKCommon.dll',
        'PIReader/OSIsoft.PITimeServer.dll', 'docs/run.log', 'tests/result.tmp',
        'docs/draft-chart.png', 'docs/chart.draft.png', 'docs/chart_draft.png',
        'docs/~$slide.xlsx', 'docs/.DS_Store', 'docs/Thumbs.db',
        'docs/release/pyinstaller-build-V0.1-beta4.txt',
        'docs/release/build-inputs-V0.1-beta4.txt',
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
        pid = 123

        def poll(self):
            return None

    seen = iter([['tk'], ['tk', '未命名项目 — 工作表1 - Minijmp']])
    found, _elapsed, _all = smoke_launch.wait_for_window(
        Alive(), 90, titles=lambda _pid: next(seen), sleep=lambda _seconds: None)
    assert found == ['未命名项目 — 工作表1 - Minijmp']


def test_smoke_launch_uses_pointer_sized_win32_signatures(monkeypatch):
    import ctypes
    from ctypes import wintypes
    from types import SimpleNamespace

    class ApiFunction:
        def __init__(self, function):
            self.function = function

        def __call__(self, *args):
            return self.function(*args)

    handle = 0x1_0000_1234
    unrelated_handle = 0x2_0000_5678
    process_id = 0x1234
    titles = {handle: 'MiniJMP smoke', unrelated_handle: 'MiniJMP unrelated'}
    owners = {handle: process_id, unrelated_handle: process_id + 1}
    user32 = SimpleNamespace()
    user32.EnumWindows = ApiFunction(
        lambda callback, _param: (callback(handle, 0), callback(unrelated_handle, 0))[-1])
    user32.GetWindowTextLengthW = ApiFunction(lambda hwnd: len(titles[hwnd]))
    user32.GetWindowTextW = ApiFunction(
        lambda hwnd, buffer, _size: (setattr(buffer, 'value', titles[hwnd]), len(titles[hwnd]))[1])
    user32.IsWindowVisible = ApiFunction(lambda _hwnd: True)
    user32.GetWindowThreadProcessId = ApiFunction(
        lambda hwnd, owner: (setattr(owner._obj, 'value', owners[hwnd]), 1)[1])
    monkeypatch.setattr(ctypes, 'WinDLL', lambda *_args, **_kwargs: user32)
    monkeypatch.setattr(smoke_launch, 'process_tree', lambda pid: {pid})

    assert smoke_launch.window_titles(process_id) == ['MiniJMP smoke']
    assert user32.EnumWindows.argtypes[0]._restype_ is wintypes.BOOL
    assert user32.EnumWindows.argtypes[0]._argtypes_ == (wintypes.HWND, wintypes.LPARAM)
    assert user32.GetWindowTextLengthW.argtypes == (wintypes.HWND,)
    assert user32.GetWindowTextW.argtypes == (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
    assert user32.IsWindowVisible.argtypes == (wintypes.HWND,)
    assert user32.GetWindowThreadProcessId.argtypes == (
        wintypes.HWND, ctypes.POINTER(wintypes.DWORD))


def test_smoke_launch_fails_if_process_exits_before_window(monkeypatch):
    class Exited:
        pid = 123
        returncode = 7

        def poll(self):
            return self.returncode

    with pytest.raises(RuntimeError, match='exited with code 7'):
        smoke_launch.wait_for_window(
            Exited(), 90, titles=lambda _pid: pytest.fail('window scan after exit'))

    process = subprocess.Popen([sys._base_executable, '-c', 'raise SystemExit(7)'])
    assert process.wait(timeout=10) == 7
    with pytest.raises(RuntimeError, match='exited with code 7'):
        smoke_launch.wait_for_window(process, 10)


def test_smoke_launch_scans_windows_for_started_process(monkeypatch):
    class Alive:
        pid = 456
        returncode = None

        def poll(self):
            return None

    pids = []
    found, _elapsed, _seen = smoke_launch.wait_for_window(
        Alive(), 90, titles=lambda pid: (pids.append(pid), ['MiniJMP smoke'])[1],
        sleep=lambda _seconds: None)
    assert found == ['MiniJMP smoke']
    assert pids == [456]


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows windows')
def test_smoke_launch_real_owned_and_unrelated_windows(tk_root):
    tk_root.title('MiniJMP unrelated')
    tk_root.deiconify()
    tk_root.update()
    process = subprocess.Popen([sys.executable, '-c',
        "import tkinter as tk; w=tk.Tk(); w.title('MiniJMP child'); w.mainloop()"])
    try:
        found, _, _ = smoke_launch.wait_for_window(process, 20)
        assert found == ['MiniJMP child']
        assert 'MiniJMP unrelated' not in smoke_launch.window_titles(process.pid)
    finally:
        subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                       capture_output=True, check=False)
        process.wait(timeout=10)
        tk_root.withdraw()


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows windows')
def test_smoke_launch_real_unrelated_window_cannot_pass(tk_root):
    tk_root.title('MiniJMP unrelated')
    tk_root.deiconify()
    tk_root.update()
    process = subprocess.Popen([sys._base_executable, '-c', 'import time; time.sleep(10)'])
    try:
        found, _, _ = smoke_launch.wait_for_window(process, 2)
        assert found == []
    finally:
        process.terminate()
        process.wait(timeout=10)
        tk_root.withdraw()


def test_release_uses_only_clean_pireader_templates():
    script = (ROOT / 'tools' / 'build_windows_release.ps1').read_text(encoding='utf-8')
    precheck = (ROOT / 'tools' / 'check_windows_release_ready.ps1').read_text(encoding='utf-8')

    assert "'PIReader\\config.example.txt', 'PIReader\\tags.example.txt'" in script
    assert "Copy-Item -LiteralPath (Join-Path $piSource 'PIReader.exe')" not in script
    assert "Join-Path $piSource 'config.example.txt'" in script
    assert "Join-Path $piSource 'tags.example.txt'" in script
    assert 'Get-ChildItem -LiteralPath $piSource' not in script
    assert "'PIReader/config.example.txt'" in precheck
    assert "'PIReader/tags.example.txt'" in precheck
    assert "'PIReader\\PIReader.csproj'" in script
    assert '/p:TargetFrameworkRootPath=' in script and '/p:ReferencePath=' in script
    assert 'FrameworkReferenceDirectory' in script and 'FrameworkReferenceDirectory' in precheck
    assert '[Reflection.AssemblyName]::GetAssemblyName($sdkPath).Version' in script
    assert 'Get-FileHash -LiteralPath $sdkPath -Algorithm SHA256' in script
    assert 'PI SDK build references (build-only; not distributed)' in script
    assert "PIReader\\Program.cs" in script and "PIReader\\TimeExpressionParser.cs" in script
    assert "Copy-Item -LiteralPath $compiledReader" in script
    sign = script.index("'tools\\sign_minijmp_executables.ps1') @signArgs")
    assert sign < script.index("'tools\\write_release_sbom.py'")
    assert sign < script.index("'manifest' $releaseDir") < script.index("'make' $releaseDir")
    assert '"$piHash  $piRelative"' in script
    assert not any('Copy-Item' in line and 'OSIsoft.' in line for line in script.splitlines())
    assert script.index('SOURCE-CODE.txt') < script.index("'manifest' $releaseDir")
    assert script.index("'SOURCE-BUNDLE-INFO.txt'") < script.index("'manifest' $sourceStage")
    assert script.index('write_third_party_notices.py') < script.index("'manifest' $sourceStage")


def test_pireader_project_identity_matches_release_version():
    namespace = {'msbuild': 'http://schemas.microsoft.com/developer/msbuild/2003'}
    project = ElementTree.parse(ROOT / 'PIReader' / 'PIReader.csproj')
    assert project.find('.//msbuild:TargetFrameworkVersion', namespace).text == 'v4.8'
    assert project.find('.//msbuild:PlatformTarget', namespace).text == 'x86'
    assert project.find('.//msbuild:AssemblyName', namespace).text == 'PIReader'
    includes = [item.attrib['Include'] for item in project.findall('.//msbuild:Compile', namespace)]
    assert r'Properties\AssemblyInfo.cs' in includes
    assembly = (ROOT / 'PIReader' / 'Properties' / 'AssemblyInfo.cs').read_text(encoding='utf-8')
    versions = release_metadata.identifiers()
    assert 'AssemblyProduct("MiniJMP PI Reader")' in assembly
    assert f'AssemblyFileVersion("{versions["product:fileversion"]}")' in assembly
    assert f'AssemblyInformationalVersion("{versions["product:version_info"]}")' in assembly


def test_packaging_describes_sdk_as_compile_only():
    usage = (ROOT / 'packaging' / 'windows' / 'USAGE.txt').read_text(encoding='utf-8')
    notice = (ROOT / 'packaging' / 'windows' / 'PI-SDK-NOTICE.txt').read_text(encoding='utf-8')
    assert '不包含 OSIsoft PI SDK DLL' in usage
    assert '不将其复制进运行包' in notice


def test_release_bundles_documented_safe_sample_projects_and_keeps_legacy_sources():
    from worksheets import read_project_file

    script = (ROOT / 'tools' / 'build_windows_release.ps1').read_text(encoding='utf-8')
    precheck = (ROOT / 'tools' / 'check_windows_release_ready.ps1').read_text(encoding='utf-8')
    usage = '\n'.join(path.read_text(encoding='utf-8') for path in (ROOT / 'docs' / 'usage').glob('*.rst'))
    windows_usage = (ROOT / 'packaging' / 'windows' / 'USAGE.txt').read_text(encoding='utf-8')
    changelog = (ROOT / 'docs' / 'CHANGELOG_DEV.md').read_text(encoding='utf-8')

    for name in ('ctrl_chart_test', 'CPK_sample', 'GRR_crossed', 'fit_sample_data',
                 'gasket', 'car_poll', 'correlation', 'Nested_GRR', 'dists'):
        assert f"sample_data\\{name}.dexpl" in script
        assert f"'sample_data/{name}.dexpl'" in precheck
        assert f"sample_data\\{name}.pickle" not in script
        assert f"'sample_data/{name}.pickle'" not in precheck
        assert (ROOT / 'sample_data' / f'{name}.dexpl').is_file()
        assert (ROOT / 'sample_data' / f'{name}.pickle').is_file()
        project = read_project_file(ROOT / 'sample_data' / f'{name}.dexpl')
        sheets = [record['table'] for key, record in project.items() if key != 'meta']
        assert sheets and any(not sheet.empty for sheet in sheets)
    for name in ('gasket', 'car_poll', 'correlation', 'CPK_sample', 'Nested_GRR', 'dists'):
        assert f'{name}.dexpl' in usage
        assert f'{name}.pickle' not in usage
    assert 'ctrl_chart_imr.pickle' not in usage
    assert 'ctrl_chart_test.dexpl' in usage and 'may not exactly match this sample' in usage
    assert '随包提供的 .dexpl 示例工程' in windows_usage
    assert '四个 .dexpl 示例工程' not in windows_usage
    assert '使用手册示例' in changelog
    assert '四个内置表格示例' not in changelog


def test_source_bundle_precheck_does_not_require_git(tmp_path):
    (tmp_path / 'SOURCE-BUNDLE-INFO.txt').write_text(
        'MiniJMP corresponding source\n', encoding='utf-8')
    result = subprocess.run(
        ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
         str(TOOLS / 'check_windows_release_ready.ps1'), '-RepoRoot', str(tmp_path),
         '-GitOnly'], capture_output=True, text=True, encoding='utf-8',
        errors='replace', timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr
    assert '源码包' in result.stdout


def test_python_version_gate_accepts_311_and_newer(tmp_path):
    lock = tmp_path / 'lock.txt'
    lock.write_text('numpy==2.4.6\n', encoding='utf-8')
    hash_lock = tmp_path / 'hashes.txt'
    hash_lock.write_text('numpy==2.4.6 --hash=sha256:' + 'a' * 64 + '\n', encoding='utf-8')
    installed = {'numpy': '2.4.6'}.__getitem__
    kwargs = dict(lock=lock, hash_lock=hash_lock, installed=installed, pip_ok=True,
                  pyinstaller='6.22.3', bits=64)

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


def test_hash_lock_must_exactly_cover_version_pins(tmp_path):
    lock = tmp_path / 'requirements.lock'
    hashes = tmp_path / 'requirements-hashed.lock'
    lock.write_text('numpy==2.4.6\nPygments==2.21.0\n', encoding='utf-8')
    hashes.write_text('numpy==2.4.6 --hash=sha256:' + 'a' * 64 + '\n'
                      'Pygments==2.21.0 --hash=sha256:' + 'b' * 64 + '\n', encoding='utf-8')

    assert release_env.hash_lock_mismatches(lock, hashes) == []
    hashes.write_text('numpy==2.4.5 --hash=sha256:' + 'a' * 64 + '\n', encoding='utf-8')
    issues = release_env.hash_lock_mismatches(lock, hashes)
    assert any('version differs' in issue for issue in issues)
    assert any('Pygments==2.21.0 has no hash-lock entry' in issue for issue in issues)


def test_verified_install_report_must_match_all_wheel_hashes(tmp_path, monkeypatch):
    lock = tmp_path / 'requirements.lock'
    hashes = tmp_path / 'requirements-hashed.lock'
    lock.write_text('numpy==2.4.6\n', encoding='utf-8')
    digest = 'a' * 64
    hashes.write_text(f'numpy==2.4.6 --hash=sha256:{digest}\n', encoding='utf-8')
    monkeypatch.setattr(release_env.sys, 'prefix', str(tmp_path / 'venv'))
    monkeypatch.setattr(release_env.sys, 'executable', str(tmp_path / 'venv' / 'Scripts' / 'python.exe'))
    report = Path(release_env.sys.prefix) / f'minijmp-hash-install-{release_env._sha256(hashes)}.json'
    report.parent.mkdir(parents=True)
    report.write_text(json.dumps({
        'python': str(Path(release_env.sys.executable).resolve()),
        'version_lock_sha256': release_env._sha256(lock),
        'hash_lock_sha256': release_env._sha256(hashes),
        'verified_wheels': [{'name': 'NumPy', 'version': '2.4.6', 'sha256': digest}],
    }), encoding='utf-8')

    assert release_env.verified_install_hashes(lock, hashes) == {'numpy': ('2.4.6', digest)}
    report.write_text(report.read_text(encoding='utf-8').replace(digest, 'b' * 64), encoding='utf-8')
    assert release_env.verified_install_hashes(lock, hashes) is None


def test_release_precheck_includes_hash_lock():
    script = (TOOLS / 'check_windows_release_ready.ps1').read_text(encoding='utf-8')
    assert "'packaging/windows/requirements-py311-hashed.lock'" in script


def test_version_identifiers_and_build_info_agree():
    levels = release_metadata.check()
    assert [level for level, _ in levels] == ['PASS'], levels
    assert 'V1.1' in levels[0][1] and '1.1.0.0' in levels[0][1]
    script = (ROOT / 'tools' / 'build_windows_release.ps1').read_text(encoding='utf-8')
    assert '$releaseVersion = ' + "'V1.1'" in script
    assert '$productVersion = ' + "'v1.1.0'" in script
    assert 'Release name: $releaseVersion' in script
    assert 'PIReader: built from project source' in script
    assert 'PI SDK/PIPC runtime' in script
    assert "'--hidden-import', 'pyarrow.parquet'" in script
    assert "names=['numpy','scipy','pandas','pyarrow'" in script
    version_info = (ROOT / 'packaging' / 'windows' / 'version_info.txt').read_text(encoding='utf-8')
    assert "StringStruct('Comments', 'MiniJMP V1.1 source baseline')" in version_info
    usage = (ROOT / 'packaging' / 'windows' / 'USAGE.txt').read_text(encoding='utf-8')
    assert '不包含 OSIsoft PI SDK DLL' in usage
    assert '许可和再分发授权不因打包或代码签名而改变' in usage
    assert 'HDF5 暂不可导入' in usage


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
    stored['executable_path'] = str(tmp_path / 'legacy-rogue.exe')
    monkeypatch.setenv('PI_READER_EXE', str(tmp_path / 'env-rogue.exe'))
    monkeypatch.delenv('PI_CONFIG', raising=False)
    monkeypatch.setattr(pi_import, '__file__', str(internal / 'pi_import.py'))
    monkeypatch.setattr(pi_reader, 'application_root', lambda: install)
    window = pi_import.PIImportDialog(tk_root)
    try:
        assert window.config.get() == pi_import.normalize_pi_path(install / 'PIReader' / 'config.txt')
        assert pi_reader._executable_path() == (install / 'PIReader' / 'PIReader.exe').resolve()
        assert set(window.paths()) == {'config_path'}
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


@pytest.mark.parametrize('latest', ['v1.1.0', 'v2.3.4-beta.12'])
def test_changes_reads_latest_version_across_major_versions(monkeypatch, latest):
    original_read = release_metadata.read

    def read(root, name):
        if name == 'CHANGES':
            return f'CHANGES\n{latest}\nnotes\nv0.1.0-beta.4\n'
        return original_read(root, name)

    monkeypatch.setattr(release_metadata, 'read', read)
    assert release_metadata.identifiers()['product:CHANGES'] == latest
    levels = release_metadata.check()
    assert levels[0][0] == ('PASS' if latest == 'v1.1.0' else 'BLOCKED')


def test_version_check_rejects_build_product_drift(monkeypatch):
    found = release_metadata.identifiers()
    found['product:build'] = 'v0.1.0-beta.4'
    monkeypatch.setattr(release_metadata, 'identifiers', lambda root: found)
    assert any(level == 'BLOCKED' and 'product:build' in message
               for level, message in release_metadata.check())


def test_finalize_review_materials_binds_tag_commit_and_deliverable_hashes(tmp_path, monkeypatch):
    import shutil
    repo = tmp_path / 'repo'
    docs = repo / 'docs/release'
    docs.mkdir(parents=True)
    for name in ('VERSION-INFO.md', 'INSTALL-USAGE.md', 'SOURCE-PROVENANCE.md', 'SOURCE-PROVENANCE.csv'):
        (docs / name).write_text('{{COMMIT}} {{TAG}} {{SHA256}}', encoding='utf-8')
    lock = repo / 'packaging/windows/requirements-py311.lock'
    lock.parent.mkdir(parents=True)
    lock.write_text('numpy==2.4.6', encoding='utf-8')
    runtime = tmp_path / 'MiniJMP-V1.1'
    runtime.mkdir()
    for name in ('MiniJMP.exe', 'BUILD-INFO.txt', 'THIRD-PARTY-NOTICES.txt', 'LICENSE', 'PI-SDK-NOTICE.txt'):
        (runtime / name).write_text('test', encoding='utf-8')
    (runtime / 'PIReader').mkdir()
    (runtime / 'PIReader' / 'PIReader.exe').write_bytes(b'signed reader fixture')
    (runtime / 'BUILD-INFO.txt').write_text('Base Git HEAD: ' + 'a' * 40, encoding='utf-8')
    (runtime / 'THIRD-PARTY-LICENSES').mkdir()
    destination = tmp_path / 'review'
    destination.mkdir()
    for name in ('MiniJMP-V1.1-Windows-x64.zip', 'MiniJMP-V1.1-Source.zip'):
        (destination / name).write_bytes(b'archive')
    monkeypatch.setattr(release_metadata, 'ROOT', repo)
    monkeypatch.setattr(subprocess, 'check_output', lambda *a, **k: 'a' * 40)
    monkeypatch.setattr(make_zip, 'stable_sha256', lambda path, **k: make_zip.sha256_file(path))
    release_metadata.finalize(runtime, destination)
    info = (destination / 'VERSION-INFO.md').read_text(encoding='utf-8')
    assert 'a' * 40 in info and 'v1.1.0' in info and '{{' not in info
    sums = (destination / 'SHA256SUMS.txt').read_text(encoding='ascii')
    assert '  SHA256SUMS.txt' not in sums
    assert '../MiniJMP-V1.1/MiniJMP.exe' in sums
    assert '../MiniJMP-V1.1/PIReader/PIReader.exe' in sums
    assert make_zip.sha256_file(runtime / 'PIReader' / 'PIReader.exe') in info
    for line in sums.splitlines():
        digest, relative = line.split('  ', 1)
        assert make_zip.sha256_file(destination / relative) == digest
    shutil.rmtree(destination / 'THIRD-PARTY-LICENSES')
    monkeypatch.setattr(subprocess, 'check_output', lambda args, **k: 'b' * 40 if '^{}' in args[-1] else 'a' * 40)
    with pytest.raises(ValueError, match='does not identify'):
        release_metadata.finalize(runtime, destination)
