import base64
from importlib import metadata
from io import BytesIO
import runpy
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock

from PIL import Image
import pytest
from packaging.utils import canonicalize_name


ROOT = Path(__file__).resolve().parents[1]


def test_embedded_icon_resource_is_valid_png():
    namespace = runpy.run_path(str(ROOT / 'code' / 'icon_resource.py'))
    payload = base64.b64decode(namespace['ICON_PNG_BASE64'], validate=True)
    assert payload.startswith(b'\x89PNG\r\n\x1a\n')
    Image.open(BytesIO(payload)).verify()


def test_embedded_icon_uses_tk_photoimage_data(monkeypatch):
    namespace = runpy.run_path(str(ROOT / 'code' / 'icon_resource.py'))
    image = object()
    photo_image = Mock(return_value=image)
    monkeypatch.setitem(namespace['create_icon_image'].__globals__, 'PhotoImage', photo_image)
    master = object()

    assert namespace['create_icon_image'](master) is image
    photo_image.assert_called_once_with(data=namespace['ICON_PNG_BASE64'], master=master)


def test_embedded_plot_icons_are_valid_16px_pngs():
    namespace = runpy.run_path(str(ROOT / 'code' / 'icon_resource.py'))
    icons = namespace['PLOT_ICON_PNG_BASE64']

    assert len(icons) == 25
    for encoded in icons.values():
        payload = base64.b64decode(encoded, validate=True)
        image = Image.open(BytesIO(payload))
        assert image.size == (16, 16)
        assert image.mode == 'RGBA'
        image.verify()
        assert Image.open(BytesIO(payload)).getchannel('A').getextrema()[0] == 0


def test_plot_icons_use_tk_photoimage_with_the_application_master(monkeypatch):
    namespace = runpy.run_path(str(ROOT / 'code' / 'icon_resource.py'))
    photo_image = Mock(side_effect=lambda **kwargs: object())
    monkeypatch.setitem(namespace['create_plot_icon_images'].__globals__, 'PhotoImage', photo_image)
    master = object()

    images = namespace['create_plot_icon_images'](master)

    assert set(images) == set(namespace['PLOT_ICON_PNG_BASE64'])
    assert photo_image.call_count == len(images)
    assert all(call.kwargs['master'] is master for call in photo_image.call_args_list)


def test_release_build_keeps_ico_but_does_not_stage_icon_png():
    script = (ROOT / 'tools' / 'build_windows_release.ps1').read_text(encoding='utf-8')
    assert "'--onedir', '--windowed', '--noupx'" in script
    assert "'icon\\icon_big.ico'" in script
    assert "'code\\icon.png'" not in script


def test_frozen_entrypoint_calls_gui_main_without_startup_subprocess(monkeypatch):
    gui = ModuleType('MiniJMP')
    gui.main = Mock()
    monkeypatch.setitem(sys.modules, 'MiniJMP', gui)
    monkeypatch.setattr(sys, 'path', list(sys.path))

    runpy.run_path(str(ROOT / 'packaging/windows_entrypoint.py'))

    gui.main.assert_called_once_with()


def test_release_archives_identify_commit_and_preserve_existing_artifacts():
    script = (ROOT / 'tools' / 'build_windows_release.ps1').read_text(encoding='utf-8')
    assert 'MiniJMP-$version-$shortHead-win64' in script
    assert 'MiniJMP-$version-$shortHead-source' in script
    assert 'Preserving existing release artifact:' in script
    assert 'Compress-Archive -LiteralPath $releaseDir' in script
    assert 'git -C $root ls-files -- @sourcePaths' in script
    assert 'if ($BuildSuffix) { $shortHead = "$shortHead-$BuildSuffix" }' in script
    assert 'Build ID: $shortHead' in script
    assert 'Application code and build inputs match Git HEAD' in script
    assert 'not committed or pushed' not in script


def test_release_script_refuses_dirty_or_incomplete_worktree_before_writing():
    script = (ROOT / 'tools' / 'build_windows_release.ps1').read_text(encoding='utf-8')

    assert 'git -C $root status --porcelain --untracked-files=normal' in script
    assert 'Refusing to build from a dirty working tree' in script
    assert 'version_info.txt does not declare $version' in script
    assert 'Required build input is not tracked by Git: $inputPath' in script
    assert 'git -C $root ls-files -- $inputPath' in script
    clean_check = script.index('git -C $root status --porcelain --untracked-files=normal')
    assert clean_check < script.index("New-Item -ItemType Directory -Path (Join-Path $root 'build')")
    assert clean_check < script.index('Remove-GeneratedPath $buildRoot')


def test_release_precheck_reports_clean_and_dirty_worktrees(tmp_path):
    repo = tmp_path / 'repo'
    remote = tmp_path / 'origin.git'
    subprocess.run(['git', 'init', '-b', 'main', str(repo)], check=True, capture_output=True)
    for key, value in (('user.name', 'Precheck'), ('user.email', 'precheck@example.com')):
        subprocess.run(['git', '-C', str(repo), 'config', key, value], check=True, capture_output=True)
    readme = repo / 'README.md'
    readme.write_text('release precheck\n', encoding='utf-8')
    subprocess.run(['git', '-C', str(repo), 'add', '-A'], check=True, capture_output=True)
    subprocess.run(['git', '-C', str(repo), 'commit', '-m', 'initial'], check=True, capture_output=True)
    subprocess.run(['git', 'init', '--bare', str(remote)], check=True, capture_output=True)
    subprocess.run(['git', '-C', str(repo), 'remote', 'add', 'origin', str(remote)], check=True, capture_output=True)
    subprocess.run(['git', '-C', str(repo), 'push', '-u', 'origin', 'main'], check=True, capture_output=True)

    def precheck():
        return subprocess.run(
            ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
             str(ROOT / 'tools' / 'check_windows_release_ready.ps1'),
             '-RepoRoot', str(repo), '-GitOnly'],
            capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=120)

    clean = precheck()
    assert clean.returncode == 0, clean.stdout
    assert 'RESULT: PASS' in clean.stdout
    assert 'BLOCKED' not in clean.stdout

    (repo / 'untracked.txt').write_text('draft\n', encoding='utf-8')
    untracked = precheck()
    assert untracked.returncode == 1
    assert 'RESULT: BLOCKED' in untracked.stdout

    (repo / 'untracked.txt').unlink()
    readme.write_text('release precheck\nedited\n', encoding='utf-8')
    modified = precheck()
    assert modified.returncode == 1
    assert 'RESULT: BLOCKED' in modified.stdout


def test_frozen_resources_and_user_writable_paths(tmp_path):
    bundle = tmp_path / '_internal'
    (bundle / 'user_config').mkdir(parents=True)
    (bundle / 'sample_data').mkdir()
    (bundle / 'help').mkdir()
    bundled_config = bundle / 'user_config' / 'default.conf'
    bundled_config.write_text('[base]\nfontsize = 12\n', encoding='utf-8')
    local_app_data = tmp_path / 'LocalAppData'

    source = """
import os, sys
from pathlib import Path
root, bundle, local = map(Path, sys.argv[1:])
sys.frozen = True
sys._MEIPASS = str(bundle)
os.environ['LOCALAPPDATA'] = str(local)
sys.path.insert(0, str(root / 'code'))
from help_link import HELP_DIR
from pandastable_local import config, core
assert Path(config.configpath) == local / 'MiniJMP' / 'user_config'
assert Path(config.default_conf).read_text(encoding='utf-8') == '[base]\\nfontsize = 12\\n'
assert Path(core.config_path) == local / 'MiniJMP' / 'log'
assert Path(core.sample_data_path) == bundle / 'sample_data'
assert HELP_DIR == bundle / 'help'
Path(core.logfile).write_text('writable', encoding='utf-8')
"""
    result = subprocess.run(
        [sys.executable, '-c', source, str(ROOT), str(bundle), str(local_app_data)],
        cwd=tmp_path, capture_output=True, text=True, timeout=30)

    assert result.returncode == 0, result.stderr
    assert (local_app_data / 'MiniJMP' / 'log' / 'error.log').read_text() == 'writable'


def test_third_party_notice_generator_copies_dependency_licenses(tmp_path):
    destination = tmp_path / 'notices'
    result = subprocess.run(
        [sys.executable, str(ROOT / 'tools/write_third_party_notices.py'), str(destination)],
        cwd=ROOT, capture_output=True, text=True, timeout=30)

    assert result.returncode == 0, result.stderr
    notice = (destination / 'THIRD-PARTY-NOTICES.txt').read_text(encoding='utf-8')
    assert 'numpy ' in notice.lower()
    assert 'pandas ' in notice.lower()
    assert 'pyinstaller ' in notice.lower()
    assert any((destination / 'THIRD-PARTY-LICENSES').iterdir())
    assert 'IBM Carbon Design System' in notice
    assert 'Copyright (c) 2020-2026 Paweł Kuna' in notice
    assert 'chart--histogram.svg' in notice and 'chart-scatter-3d.svg' in notice
    licenses = destination / 'THIRD-PARTY-LICENSES'
    for name in ('Carbon-Icons-Apache-2.0.txt', 'Tabler-Icons-MIT.txt'):
        assert (licenses / name).read_bytes() == (ROOT / 'packaging' / 'windows' / 'licenses' / name).read_bytes()
    for name in ('formulaic', 'interface-meta', 'narwhals', 'wrapt', 'et_xmlfile'):
        distribution = metadata.distribution(name)
        package = distribution.metadata['Name']
        assert f'{package} {distribution.version}' in notice
        declared = distribution.metadata.get_all('License-File', ())
        assert declared
        for filename in declared:
            sources = [Path(distribution.locate_file(item)) for item in distribution.files
                       if str(item).endswith('/' + filename)]
            assert sources
            copies = list(licenses.glob(f'{package}-{distribution.version}-*'))
            assert any(copy.read_bytes() == sources[0].read_bytes() for copy in copies)
    listed = {canonicalize_name(line.split()[1]) for line in notice.splitlines()
              if line.startswith('- ')}
    assert not listed.intersection({'pytest', 'pip', 'setuptools', 'altgraph', 'pefile',
                                    'pyinstaller-hooks-contrib', 'pywin32-ctypes'})


def test_notice_runtime_closure_respects_markers_and_excludes_build_tools(tmp_path, monkeypatch):
    namespace = runpy.run_path(str(ROOT / 'tools/write_third_party_notices.py'))
    function = namespace['_runtime_dependencies']
    monkeypatch.setitem(function.__globals__, 'ROOT', tmp_path)
    (tmp_path / 'requirements.txt').write_text('app\n', encoding='utf-8')
    distributions = {
        'app': Mock(requires=['dependency', 'optional; extra == "test"',
                              'other-platform; python_version < "2"']),
        'dependency': Mock(requires=['app']),
        'pyinstaller': Mock(requires=['build-only']),
    }
    lookup = Mock(side_effect=distributions.__getitem__)
    monkeypatch.setattr(namespace['metadata'], 'distribution', lookup)

    assert function() == [distributions[name] for name in ('app', 'dependency', 'pyinstaller')]
    assert lookup.call_count == 3


@pytest.mark.parametrize('missing', [None, 'declared', 'all'])
def test_notice_license_metadata_priority_dedup_and_missing_original(tmp_path, missing):
    namespace = runpy.run_path(str(ROOT / 'tools/write_third_party_notices.py'))
    info = tmp_path / 'sample-1.dist-info'
    info.mkdir()
    headers = 'Name: sample\nVersion: 1\n'
    if missing != 'all':
        headers += 'License-File: AUTHORS.txt\nLicense-File: LICENCE.rst\n'
    (info / 'METADATA').write_text(headers, encoding='utf-8')
    paths = ['sample-1.dist-info/METADATA']
    if missing != 'all':
        for filename in ('AUTHORS.txt', 'LICENCE.rst', 'NOTICE'):
            paths.append('sample-1.dist-info/licenses/' + filename)
            source = info / 'licenses' / filename
            source.parent.mkdir(exist_ok=True)
            if missing != 'declared' or filename != 'AUTHORS.txt':
                source.write_bytes(b'upstream original\r\n\xff')
    (info / 'RECORD').write_text(''.join(f'{path},,\n' for path in paths), encoding='utf-8')
    distribution = metadata.PathDistribution(info)
    if missing:
        with pytest.raises(FileNotFoundError, match='sample:'):
            namespace['_license_files'](distribution)
    else:
        files = namespace['_license_files'](distribution)
        assert [path.name for _, path in files] == ['AUTHORS.txt', 'LICENCE.rst', 'NOTICE']
        assert all(path.read_bytes() == b'upstream original\r\n\xff' for _, path in files)


def test_source_bundle_includes_icon_licenses_and_third_party_notices():
    script = (ROOT / 'tools' / 'build_windows_release.ps1').read_text(encoding='utf-8')

    assert 'packaging/windows/licenses/Carbon-Icons-Apache-2.0.txt' in script
    assert 'packaging/windows/licenses/Tabler-Icons-MIT.txt' in script
    assert "'tools\\write_third_party_notices.py') $sourceStage" in script
