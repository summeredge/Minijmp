"""执行 Workflow 的实际 Tag/Commit 检查块；不构建、不联网。"""
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / '.github/workflows/release.yml'


def step(name):
    text = WORKFLOW.read_text(encoding='utf-8')
    block = text.split('      - name: ' + name + '\n', 1)[1].split('\n      - name:', 1)[0]
    return '\n'.join(line[10:] for line in block.split('        run: |\n', 1)[1].splitlines())


@pytest.mark.parametrize('scenario', [
    'tag_push', 'manual_same', 'manual_main_ahead', 'invalid_tag',
    'version_mismatch', 'identifier_mismatch', 'tag_head_mismatch',
    'preflight_sha', 'preflight_sha_mismatch',
])
def test_checkout_commit_validation(tmp_path, scenario):
    repo = tmp_path / 'repo'
    repo.mkdir()
    for name in ('tools/release_metadata.py', 'tools/build_windows_release.ps1',
                 'packaging/windows/version_info.txt', 'code/modified_app.py', 'README.md',
                 'PIReader/Properties/AssemblyInfo.cs', 'packaging/windows/USAGE.txt', 'CHANGES'):
        target = repo / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)

    def git(*args):
        return subprocess.check_output(['git', '-C', str(repo), *args], text=True,
                                       stderr=subprocess.PIPE).strip()

    git('init', '--initial-branch=main')
    git('config', 'user.name', 'Workflow test')
    git('config', 'user.email', 'workflow@example.invalid')
    if scenario == 'identifier_mismatch':
        about = repo / 'code/modified_app.py'
        source = about.read_text(encoding='utf-8')
        source, count = re.subn(r'版本 V[0-9.]+', '版本 V999.0', source)
        assert count == 1
        about.write_text(source, encoding='utf-8')
    git('add', '.')
    git('commit', '-m', 'version under test')
    target_commit = git('rev-parse', 'HEAD')
    tag = subprocess.check_output([sys.executable, str(repo / 'tools/release_metadata.py'),
                                   '--print-product'], text=True).strip()
    if not scenario.startswith('preflight_'):
        git('tag', '-a', tag, '-m', 'release tag')
    event_commit = target_commit
    if scenario in ('manual_main_ahead', 'tag_head_mismatch'):
        (repo / 'later.txt').write_text('main advanced', encoding='utf-8')
        git('add', '.')
        git('commit', '-m', 'main advances')
        event_commit = git('rev-parse', 'HEAD')
    if scenario != 'tag_head_mismatch':
        git('checkout', '--detach', target_commit if scenario.startswith('preflight_') else tag)
    if scenario == 'invalid_tag':
        tag = 'main'
    elif scenario == 'version_mismatch':
        tag = 'v999.0.0'
        git('tag', tag)
    output = tmp_path / 'outputs.txt'
    script = tmp_path / 'validate.ps1'
    script.write_text(step('Check the tag, the version identifiers and the build commit'),
                      encoding='utf-8-sig')
    env = dict(os.environ, TAG=tag, GITHUB_SHA=event_commit, GITHUB_OUTPUT=str(output))
    env['PREFLIGHT_COMMIT'] = {
        'preflight_sha': target_commit,
        'preflight_sha_mismatch': '0' * 40,
    }.get(scenario, '')
    env['PATH'] = str(Path(sys.executable).parent) + os.pathsep + env['PATH']
    result = subprocess.run(['powershell', '-NoProfile', '-File', str(script)], cwd=repo,
                            env=env, capture_output=True, text=True, timeout=30)
    if scenario in ('invalid_tag', 'version_mismatch', 'identifier_mismatch', 'tag_head_mismatch',
                    'preflight_sha_mismatch'):
        assert result.returncode != 0, result.stdout
        assert not output.exists()
    else:
        assert result.returncode == 0, result.stdout + result.stderr
        assert output.read_text(encoding='utf-8-sig').strip() == 'commit=' + target_commit
        if scenario == 'manual_main_ahead':
            assert event_commit != target_commit


def test_commit_wiring_and_publish_permissions_stay_restricted():
    text = WORKFLOW.read_text(encoding='utf-8')
    assert 'ref: ${{ github.event_name == \'workflow_dispatch\' && (inputs.commit || inputs.tag) || github.ref }}' in text
    assert re.search(r'id: checkout\s', text)
    assert 'BUILD_COMMIT: ${{ steps.checkout.outputs.commit }}' in text
    verify = step('Verify the candidate and write the job summary')
    assert '--commit $env:BUILD_COMMIT' in verify and 'GITHUB_SHA' not in verify
    assert 'permissions:\n  contents: read' in text
    publish = text.split('\n  publish:', 1)[1]
    assert "github.event_name == 'push' && !github.event.deleted &&" in publish
    assert 'inputs.publish' not in text
    assert "vars.MINIJMP_ENABLE_PUBLISH == 'true'" in publish
    assert 'environment: release' in publish
    assert 'permissions:\n      contents: write' in publish
    assert 'gh release create $env:TAG --verify-tag' in publish
    checks = step('Run packaging, data and targeted statistical tests')
    for regression in ('tests/test_mj_a01_a06_numerics.py',
                       'tests/test_g11_quality_tables.py::test_plot_dialog_and_statistical_dependencies_unchanged',
                       'tests/test_g12_tables.py::test_utilities_change_is_only_interval_report_output'):
        assert regression in checks


def test_public_build_requires_fixed_reader_and_no_sdk_settings():
    script = (ROOT / 'tools/build_windows_release.ps1').read_text(encoding='utf-8-sig')
    assert '--check-reader-input' in script
    build = step('Build the public candidate')
    assert '-UnreleasedCandidate -PreflightCommit' in build
    assert '-PlotlyPilot' not in build
    assert '-PiSdkDirectory' not in build and '-FrameworkReferenceDirectory' not in build
    text = WORKFLOW.read_text(encoding='utf-8')
    assert 'runs-on: windows-2022' in text
    assert not any(name in text for name in ('MINIJMP_BUILD_RUNNER', 'MINIJMP_PI_SDK_DIRECTORY',
                                             'MINIJMP_FRAMEWORK_REFERENCE_DIRECTORY'))


def test_public_staging_keeps_reader_and_clean_templates_without_sdk(tmp_path):
    source = (ROOT / 'tools/build_windows_release.ps1').read_text(encoding='utf-8-sig')
    block = source.split("Copy-Item -LiteralPath (Join-Path $root 'packaging\\windows\\PI-SDK-NOTICE.txt')", 1)
    assert len(block) == 2
    block = "Copy-Item -LiteralPath (Join-Path $root 'packaging\\windows\\PI-SDK-NOTICE.txt')" + block[1].split('$buildMode =', 1)[0]
    target = tmp_path / 'runtime'
    target.mkdir()
    compiled = tmp_path / 'fixed.exe'
    compiled.write_bytes(b'verified reader fixture')
    script = tmp_path / 'stage.ps1'
    script.write_text("$ErrorActionPreference = 'Stop'\n$Public = $true\n" +
                      "$root = $env:TEST_ROOT\n$releaseDir = $env:TEST_TARGET\n" +
                      "$compiledReader = $env:TEST_COMPILED\n" + block, encoding='utf-8-sig')
    result = subprocess.run(['powershell', '-NoProfile', '-File', str(script)],
                            env=dict(os.environ, TEST_ROOT=str(ROOT), TEST_TARGET=str(target),
                                     TEST_COMPILED=str(compiled)), capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert sorted(p.name for p in (target / 'PIReader').iterdir()) == ['PIReader.exe', 'config.txt', 'tags.txt']
    assert (target / 'PIReader/PIReader.exe').read_bytes() == compiled.read_bytes()
    assert (target / 'PIReader/config.txt').read_bytes() == (ROOT / 'PIReader/config.example.txt').read_bytes()
    assert not (target / 'PIReader/tags.txt').read_text(encoding='utf-8').strip()
