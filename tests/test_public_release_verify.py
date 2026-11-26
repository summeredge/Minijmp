"""Checks for the public candidate verifier; nothing is built or downloaded."""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))

import verify_public_release as verify


RUNTIME_OK = [
    *[f'MiniJMP-V1.2.1/{name}' for name in verify.RUNTIME_FILES],
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
    ('MiniJMP-V1.2.1/PIReader/OSIsoft.PISDKCommon.dll', 'proprietary PI SDK component'),
    ('MiniJMP-V1.2.1/PIReader/company.ini', 'unexpected PIReader file'),
    ('MiniJMP-V1.2.1/config.txt', 'local PI settings'),
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
    candidate = good.replace('Release name: V1.2.1', 'Release name: V1.2.1-a1b2c3d')
    candidate = candidate.replace('Public CI candidate', 'Unreleased Public candidate')
    candidate = candidate.replace('Git Tag: v1.2.1', 'Git Tag: none (unreleased candidate)')
    assert verify.build_info_problems(candidate, 'V1.2.1-a1b2c3d', 'a' * 40,
                                      unreleased_candidate=True) == []
    assert verify.build_info_problems(candidate.replace('Git Tag: none', 'Git Tag: v1.2.1'),
                                      'V1.2.1-a1b2c3d', 'a' * 40,
                                      unreleased_candidate=True)


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
    unreleased = json.loads(json.dumps(document))
    unreleased['metadata']['properties'][0]['value'] = 'unreleased'
    assert verify.sbom_problems(unreleased, 'v1.2.1', 'unreleased') == []
    assert verify.sbom_problems(unreleased, 'v1.2.1')
    drifted = json.loads(json.dumps(document))
    drifted['metadata']['component']['version'] = '1.2.0'
    assert any('SBOM version' in problem for problem in verify.sbom_problems(drifted, 'v1.2.1'))
    leaked = json.loads(json.dumps(document))
    leaked['components'][0]['properties'][0]['value'] = 'true'
    assert any('PI SDK component' in problem for problem in verify.sbom_problems(leaked, 'v1.2.1'))


@pytest.mark.parametrize('kind', ['runtime', 'source'])
@pytest.mark.parametrize('dirty', ['', 'Server=example.invalid', 'User=test-account', 'Password=test-secret', 'tags'])
def test_pi_templates_reject_nonblank_settings(tmp_path, kind, dirty):
    import zipfile
    archive = tmp_path / 'candidate.zip'
    root = 'candidate'
    config = 'config.txt' if kind == 'runtime' else 'config.example.txt'
    tags = 'tags.txt' if kind == 'runtime' else 'tags.example.txt'
    with zipfile.ZipFile(archive, 'w') as handle:
        content = verify.CLEAN_CONFIG
        if dirty and dirty != 'tags':
            key = dirty.split('=')[0]
            content = content.replace(key + '=', dirty)
        handle.writestr(f'{root}/PIReader/{config}', content)
        handle.writestr(f'{root}/PIReader/{tags}', 'corporate-tag' if dirty == 'tags' else '')
    with zipfile.ZipFile(archive) as handle:
        assert bool(verify.template_problems(handle, root, kind)) == bool(dirty)


def test_runtime_requires_all_pi_files():
    for name in ('PIReader.exe', 'config.txt', 'tags.txt'):
        names = [entry for entry in RUNTIME_OK if not entry.endswith('/' + name)]
        assert any(name + ' is missing' in p for p in verify.archive_problems(names, 'MiniJMP-V1.2.1', 'runtime'))


@pytest.mark.parametrize('fault, expected', [
    ('', ''), ('binary', 'differs from the built EXE'),
    ('source', ''), ('record', 'input record mismatch'), ('fixed_hash', 'approved fixed input'), ('sbom', 'SBOM PIReader'),
    ('credentials', 'PI template is not clean'), ('sdk', 'proprietary PI SDK'),
])
def test_complete_candidate_verification(tmp_path, monkeypatch, fault, expected):
    import zipfile
    from make_zip import zip_directory

    product, release = verify.release_metadata.release_titles()
    root = f'MiniJMP-{release}'
    runtime = tmp_path / root
    audit = tmp_path / (root + '-Release')
    audit.mkdir()
    for name in verify.RUNTIME_FILES:
        path = runtime / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('', encoding='utf-8')
    (runtime / '_internal').mkdir()
    (runtime / '_internal/python311.dll').write_bytes(b'python fixture')
    reader = runtime / 'PIReader/PIReader.exe'
    reader.write_bytes(b'fresh source build fixture')
    digest = verify.sha256_file(reader)
    (runtime / 'PIReader/config.txt').write_text(verify.CLEAN_CONFIG, encoding='utf-8')
    if fault == 'credentials':
        (runtime / 'PIReader/config.txt').write_text('Password=test-secret', encoding='utf-8')
    if fault == 'sdk':
        (runtime / 'PIReader/OSIsoft.PISDK.dll').write_bytes(b'forbidden fixture')
    source_dir = tmp_path / (root + '-source')
    for name in verify.SOURCE_FILES:
        path = source_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((ROOT / name).read_bytes() if (ROOT / name).is_file() else b'')
    record = {'version': '1.0.0.0', 'sha256': 'C' * 64 if fault == 'fixed_hash' else digest}
    source_record = dict(record, version='2.0.0.0') if fault == 'record' else record
    (source_dir / verify.PI_RECORD).write_text(json.dumps(source_record), encoding='utf-8')
    monkeypatch.setattr(verify, 'reader_record', lambda: record)
    lines = ['PIReader: reused verified binary', 'PIReader version: ' + record['version'],
             f'Release name: {release}', f'Git Tag: {product}', 'Base Git HEAD: ' + 'a' * 40,
             'Build mode: Public CI candidate', f'PIReader SHA256: {digest}']
    (runtime / 'BUILD-INFO.txt').write_text('\n'.join(lines), encoding='utf-8')
    if fault == 'source':
        (source_dir / 'PIReader/Program.cs').write_text('changed source', encoding='utf-8')
    archive = audit / (root + '-Windows-x64-portable.zip')
    source = audit / (root + '-Source.zip')
    zip_directory(runtime, archive)
    zip_directory(source_dir, source)
    if fault == 'binary':
        reader.write_bytes(b'stale binary')
    sbom = audit / 'SBOM.cdx.json'
    sbom.write_text(json.dumps({
        'metadata': {'component': {'version': product.lstrip('v')},
                     'properties': [{'name': 'minijmp:tag', 'value': product}]},
        'components': [{'name': 'PIReader.exe',
                        'version': record['version'],
                        'properties': [{'name': 'minijmp:distributed', 'value': 'true'},
                                       {'name': 'minijmp:source', 'value': 'reused verified binary'}],
                        'hashes': [{'alg': 'SHA-256', 'content': 'bad' if fault == 'sbom' else digest}]}],
    }), encoding='utf-8')
    (audit / f'SHA256SUMS-{release}.txt').write_text(
        '\n'.join(f'{verify.sha256_file(p)}  {p.name}' for p in (archive, source, sbom)), encoding='utf-8')
    # Fixture EXEs are not PE files; real PIReader compilation is tested separately.
    monkeypatch.setattr(verify, 'executable_problems', lambda *args, **kwargs: [])
    problems, actual = verify.verify(audit, release, 'a' * 40)
    assert actual == product
    if expected:
        assert any(expected in p for p in problems), problems
    else:
        assert problems == []


def test_public_notices_describe_source_built_reader(tmp_path, monkeypatch):
    import write_third_party_notices as notices
    monkeypatch.setattr(notices, '_runtime_dependencies', lambda: [])
    notices.generate(tmp_path, public=True)
    text = (tmp_path / 'THIRD-PARTY-NOTICES.txt').read_text(encoding='utf-8')
    assert 'PIReader/PIReader.exe' in text and 'PIReader/config.txt' in text
    assert 'PI 数据导入功能不可用' not in text
    assert 'Excluding DLLs does not establish compliance' in text

@pytest.mark.parametrize('fault, expected', [
    ('hash', 'SHA256'), ('missing', 'input missing'), ('pe', 'product name'), ('version', 'version'), ('', ''),
])
def test_fixed_reader_preflight(tmp_path, monkeypatch, fault, expected):
    executable = tmp_path / verify.PI_INPUT
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b'original reader fixture')
    record = {'version': '1.0.0.0', 'sha256': verify.sha256_file(executable)}
    (tmp_path / verify.PI_RECORD).write_text(json.dumps(record), encoding='utf-8')
    if fault == 'hash':
        executable.write_bytes(b'other executable')
    if fault == 'missing':
        executable.unlink()

    def inspect(path, version, *, reader):
        assert (path, version, reader) == (executable, '1.0.0.0', True)
        return {'pe': ['PIReader product name does not match'],
                'version': ['EXE file version mismatch']}.get(fault, [])

    monkeypatch.setattr(verify, 'executable_problems', inspect)
    problems = verify.check_reader_input(tmp_path)
    assert bool(problems) == bool(expected)
    if expected:
        assert expected in problems[0]
