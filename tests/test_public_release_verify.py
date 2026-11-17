"""Checks for the public candidate verifier; nothing is built or downloaded."""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))

import verify_public_release as verify


RUNTIME_OK = [
    'MiniJMP-V1.2.1/MiniJMP.exe',
    'MiniJMP-V1.2.1/LICENSE',
    'MiniJMP-V1.2.1/README.txt',
    'MiniJMP-V1.2.1/THIRD-PARTY-NOTICES.txt',
    'MiniJMP-V1.2.1/_internal/python311.dll',
    'MiniJMP-V1.2.1/_internal/pyarrow/parquet.dll',
]
SOURCE_OK = [f'MiniJMP-V1.2.1-source/{name}' for name in verify.SOURCE_FILES]


def test_public_runtime_archive_needs_its_core_files_only():
    assert verify.archive_problems(RUNTIME_OK, 'MiniJMP-V1.2.1', 'runtime') == []
    without_internal = [name for name in RUNTIME_OK if '/_internal/' not in name]
    problems = verify.archive_problems(without_internal, 'MiniJMP-V1.2.1', 'runtime')
    assert any('_internal is missing' in problem for problem in problems)


@pytest.mark.parametrize('extra, expected', [
    ('MiniJMP-V1.2.1/PIReader/OSIsoft.PISDK.dll', 'proprietary PI SDK component'),
    ('MiniJMP-V1.2.1/PIReader/OSIsoft.PITimeServer.dll', 'proprietary PI SDK component'),
    ('MiniJMP-V1.2.1/PIReader/PIReader.exe', 'PIReader runtime'),
    ('MiniJMP-V1.2.1/PIReader/config.txt', 'PIReader runtime'),
    ('MiniJMP-V1.2.1/SDK-COMPONENTS.json', 'proprietary SDK inventory'),
    ('MiniJMP-V1.2.1/_internal/code/__pycache__/x.pyc', 'build cache'),
    ('MiniJMP-V1.2.1/_internal/tool.pem', 'temporary or signing file'),
    ('MiniJMP-V1.2.1/MiniJMP.spec', 'temporary or signing file'),
])
def test_public_runtime_archive_rejects_leaks(extra, expected):
    problems = verify.archive_problems(RUNTIME_OK + [extra], 'MiniJMP-V1.2.1', 'runtime')
    assert any(expected in problem for problem in problems), problems


def test_archive_must_have_one_top_level_folder():
    problems = verify.archive_problems(
        RUNTIME_OK + ['MiniJMP-V1.2.1-Release/extra.txt'], 'MiniJMP-V1.2.1', 'runtime')
    assert any('only the folder MiniJMP-V1.2.1' in problem for problem in problems)


def test_source_archive_keeps_build_script_and_drops_sdk():
    assert verify.archive_problems(SOURCE_OK, 'MiniJMP-V1.2.1-source', 'source') == []
    missing = [name for name in SOURCE_OK if not name.endswith('release.yml')]
    problems = verify.archive_problems(missing, 'MiniJMP-V1.2.1-source', 'source')
    assert any('.github/workflows/release.yml is missing' in problem for problem in problems)
    with_sdk = SOURCE_OK + ['MiniJMP-V1.2.1-source/PIReader/OSIsoft.PISDK.dll',
                            'MiniJMP-V1.2.1-source/PIReader/PIReader.exe',
                            'MiniJMP-V1.2.1-source/PIReader/config.txt']
    problems = verify.archive_problems(with_sdk, 'MiniJMP-V1.2.1-source', 'source')
    assert len(problems) == 3
    # PIReader sources themselves remain legal in the source archive.
    assert verify.archive_problems(
        SOURCE_OK + ['MiniJMP-V1.2.1-source/PIReader/Program.cs',
                     'MiniJMP-V1.2.1-source/PIReader/config.example.txt'],
        'MiniJMP-V1.2.1-source', 'source') == []


def test_sums_check_matches_digests_and_resolves_sibling_folders(tmp_path):
    from make_zip import sha256_file

    archive = tmp_path / 'MiniJMP-V1.2.1-Windows-x64-portable.zip'
    archive.write_bytes(b'zip')
    runtime = tmp_path / 'MiniJMP-V1.2.1'
    runtime.mkdir()
    (runtime / 'MiniJMP.exe').write_bytes(b'MZ')
    text = (f'{sha256_file(archive)}  {archive.name}\n'
            f'{sha256_file(runtime / "MiniJMP.exe")}  MiniJMP-V1.2.1/MiniJMP.exe\n')
    assert verify.sums_problems(text, tmp_path) == []

    drifted = text.replace(sha256_file(archive), 'A' * 64, 1)
    problems = verify.sums_problems(drifted, tmp_path)
    assert any('digest does not match' in problem for problem in problems)

    missing = text + 'B' * 64 + '  MiniJMP-V1.2.1-Source.zip\n'
    problems = verify.sums_problems(missing, tmp_path)
    assert any('names a missing file' in problem for problem in problems)

    assert verify.sums_problems('not-a-sum\n', tmp_path)


def test_build_info_must_name_release_commit_and_public_mode():
    good = ('MiniJMP v1.2.1 Windows x64\n'
            'Release name: V1.2.1\n'
            'Build mode: Public CI candidate (unsigned, no PI SDK)\n'
            'Base Git HEAD: ' + 'a' * 40 + '\n'
            'Git Tag: v1.2.1\n')
    assert verify.build_info_problems(good, 'V1.2.1', 'a' * 40) == []
    problems = verify.build_info_problems(good, 'V1.2.1', 'b' * 40)
    assert any('Base Git HEAD' in problem for problem in problems)
    problems = verify.build_info_problems(
        good.replace('Public CI candidate', 'InternalReview'), 'V1.2.1', 'a' * 40)
    assert any('Build mode' in problem for problem in problems)


def test_summary_reports_version_commit_and_asset_digests(tmp_path):
    audit = tmp_path / 'MiniJMP-V1.2.2-Release'
    audit.mkdir()
    (audit / 'MiniJMP-V1.2.2-Windows-x64-portable.zip').write_bytes(b'x' * 1024)
    (audit / 'MiniJMP-V1.2.2-Source.zip').write_bytes(b'y' * 2048)
    digest = verify.sha256_file(audit / 'MiniJMP-V1.2.2-Windows-x64-portable.zip')

    text = verify.summary_markdown(audit, 'V1.2.2', 'v1.2.2', 'f' * 40, 'MiniJMP-V1.2.2-candidate')

    assert '| 资产 | 大小 | SHA256 |' in text
    assert 'V1.2.2' in text and 'f' * 40 in text and digest in text
    assert 'MiniJMP-V1.2.2-Source.zip' in text
    assert 'MiniJMP-V1.2.2-candidate' in text
    assert '不会创建 Release' in text


def test_sbom_must_carry_the_product_version_and_no_distributed_sdk():
    document = {
        'metadata': {
            'component': {'name': 'MiniJMP', 'version': '1.2.1'},
            'properties': [{'name': 'minijmp:tag', 'value': 'v1.2.1'},
                           {'name': 'minijmp:commit', 'value': 'a' * 40}],
        },
        'components': [{'name': 'OSIsoft.PISDK.dll',
                        'properties': [{'name': 'minijmp:distributed', 'value': 'false'}]}],
    }
    assert verify.sbom_problems(document, 'v1.2.1') == []
    drifted = json.loads(json.dumps(document))
    drifted['metadata']['component']['version'] = '1.2.0'
    assert any('SBOM version' in problem for problem in verify.sbom_problems(drifted, 'v1.2.1'))
    leaked = json.loads(json.dumps(document))
    leaked['components'][0]['properties'][0]['value'] = 'true'
    assert any('PI SDK component' in problem for problem in verify.sbom_problems(leaked, 'v1.2.1'))
