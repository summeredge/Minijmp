import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'tools' / 'sign_minijmp_executables.ps1'
POWERSHELL = shutil.which('powershell.exe') or shutil.which('powershell')


pytestmark = pytest.mark.skipif(
    sys.platform != 'win32' or not POWERSHELL,
    reason='Windows PowerShell is required',
)


def _ps_quote(value):
    return "'" + str(value).replace("'", "''") + "'"


def _run_script(tmp_path, *, status='Valid', verify_mode='success', store='CurrentUser'):
    thumbprint = uuid.uuid4().hex.upper() + 'A' * 8
    mini = tmp_path / 'MiniJMP.exe'
    pi_reader = tmp_path / 'PIReader.exe'
    mini.write_bytes(b'MZ test MiniJMP')
    pi_reader.write_bytes(b'MZ test PIReader')
    tool_log = tmp_path / 'signtool.jsonl'
    cert_log = tmp_path / 'certificate-store.txt'
    tool = tmp_path / 'mock-signtool.ps1'
    tool.write_text(
        r'''$toolArgs = @($args | ForEach-Object { [string]$_ })
$line = ConvertTo-Json -InputObject $toolArgs -Compress
[IO.File]::AppendAllText($env:MOCK_TOOL_LOG, $line + "`n", [Text.UTF8Encoding]::new($false))
if ($toolArgs[0] -eq 'verify' -and $env:MOCK_VERIFY_MODE -eq 'untrusted') {
    Write-Error 'SignTool Error: 0x800B0109 CERT_E_UNTRUSTEDROOT'
    $global:LASTEXITCODE = 1
} elseif ($toolArgs[0] -eq 'verify' -and $env:MOCK_VERIFY_MODE -eq 'digest-error') {
    Write-Output 'SignTool Error: 0x80096010 TRUST_E_BAD_DIGEST'
    $global:LASTEXITCODE = 1
} else {
    $global:LASTEXITCODE = 0
}
''',
        encoding='utf-8',
    )
    harness = tmp_path / 'invoke.ps1'
    harness.write_text(
        r'''$eku = [pscustomobject]@{
    Oid = [pscustomobject]@{ Value = '2.5.29.37' }
    EnhancedKeyUsages = @([pscustomobject]@{ Value = '1.3.6.1.5.5.7.3.3' })
}
$mockCert = [pscustomobject]@{
    Thumbprint = $env:TEST_THUMBPRINT
    HasPrivateKey = $true
    NotBefore = (Get-Date).AddDays(-1)
    NotAfter = (Get-Date).AddDays(30)
    Extensions = @($eku)
}
function Get-Item {
    [CmdletBinding()]
    param([string]$LiteralPath)
    [IO.File]::WriteAllText($env:MOCK_CERT_LOG, $LiteralPath)
    $mockCert
}
function Get-AuthenticodeSignature {
    [CmdletBinding()]
    param([string]$FilePath)
    [pscustomobject]@{
        Status = $env:MOCK_AUTH_STATUS
        StatusMessage = 'mocked'
        SignerCertificate = $mockCert
    }
}
try {
    [Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
    $arguments = @{
        Thumbprint = $env:TEST_THUMBPRINT
        MiniJMPExe = $env:TEST_MINI
        PIReaderExe = $env:TEST_PI_READER
        StoreLocation = $env:TEST_STORE
        SignTool = $env:MOCK_SIGNTOOL
    }
    $result = @(& $env:SIGN_SCRIPT @arguments)
    ConvertTo-Json -InputObject $result -Compress -Depth 4
} catch {
    [Console]::Error.WriteLine($_.Exception.Message)
    exit 1
}
''',
        encoding='utf-8',
    )
    env = os.environ.copy()
    env.update({
        'SIGN_SCRIPT': str(SCRIPT),
        'TEST_THUMBPRINT': thumbprint,
        'TEST_MINI': str(mini),
        'TEST_PI_READER': str(pi_reader),
        'TEST_STORE': store,
        'MOCK_SIGNTOOL': str(tool),
        'MOCK_TOOL_LOG': str(tool_log),
        'MOCK_CERT_LOG': str(cert_log),
        'MOCK_AUTH_STATUS': status,
        'MOCK_VERIFY_MODE': verify_mode,
    })
    result = subprocess.run(
        [POWERSHELL, '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(harness)],
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace',
        timeout=30,
        env=env,
    )
    calls = [json.loads(line) for line in tool_log.read_text(encoding='utf-8').splitlines()] if tool_log.exists() else []
    return result, calls, cert_log.read_text(encoding='utf-8') if cert_log.exists() else '', thumbprint


def test_powershell_script_parses():
    command = (
        "$tokens = $null; $errors = $null; "
        f"[void][System.Management.Automation.Language.Parser]::ParseFile({_ps_quote(SCRIPT)}, [ref]$tokens, [ref]$errors); "
        "if ($errors) { $errors | ForEach-Object { Write-Error $_ }; exit 1 }"
    )
    result = subprocess.run(
        [POWERSHELL, '-NoProfile', '-Command', command],
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace',
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize(('store', 'machine_store'), [('CurrentUser', False), ('LocalMachine', True)])
def test_signs_and_verifies_both_files_with_one_sha256_certificate(tmp_path, store, machine_store):
    result, calls, cert_path, thumbprint = _run_script(tmp_path, store=store)
    assert result.returncode == 0, result.stdout + result.stderr
    records = json.loads(result.stdout.strip().splitlines()[-1])
    assert len(records) == 2
    assert {Path(record['File']).name for record in records} == {'MiniJMP.exe', 'PIReader.exe'}
    assert all(record['Status'] == 'Valid' for record in records)
    assert all(record['CertificateThumbprint'] == thumbprint for record in records)
    assert all(record['Trusted'] is True and record['IntegrityVerified'] is True for record in records)
    assert cert_path == f'Cert:\\{store}\\My\\{thumbprint}'

    assert len(calls) == 4
    for args in calls[:2]:
        assert args[:5] == ['sign', '/sha1', thumbprint, '/fd', 'SHA256']
        assert args[5:7] == ['/s', 'My']
        assert ('/sm' in args) is machine_store
    for args in calls[2:]:
        assert args[:3] == ['verify', '/pa', '/v']


@pytest.mark.parametrize('status', ['NotTrusted', 'UnknownError'])
def test_untrusted_self_signed_result_warns_and_requires_signtool_root_error(tmp_path, status):
    result, calls, _cert_path, _thumbprint = _run_script(
        tmp_path, status=status, verify_mode='untrusted')
    assert result.returncode == 0, result.stdout + result.stderr
    records = json.loads(result.stdout.strip().splitlines()[-1])
    assert len(records) == 2
    assert all(record['Status'] == status for record in records)
    assert all(record['Trusted'] is False and record['IntegrityVerified'] is False for record in records)
    assert all(record['Assessment'] == '已签名，未受信任，完整性无法确认' for record in records)
    assert 'integrity could not be independently confirmed' in (result.stdout + result.stderr).lower()
    assert len(calls) == 4


def test_hash_mismatch_fails_even_when_the_signer_thumbprint_matches(tmp_path):
    result, _calls, _cert_path, _thumbprint = _run_script(tmp_path, status='HashMismatch')
    assert result.returncode != 0
    assert 'HashMismatch' in result.stderr


def test_untrusted_status_does_not_override_signtool_digest_error(tmp_path):
    result, _calls, _cert_path, _thumbprint = _run_script(
        tmp_path, status='NotTrusted', verify_mode='digest-error')
    assert result.returncode != 0
    assert 'hash verification failed' in result.stderr


def test_unknown_error_without_untrusted_root_is_not_accepted(tmp_path):
    result, _calls, _cert_path, _thumbprint = _run_script(
        tmp_path, status='UnknownError', verify_mode='success')
    assert result.returncode != 0
    assert 'Authenticode verification failed' in result.stderr


def test_untrusted_signature_never_claims_verified_integrity():
    source = SCRIPT.read_text(encoding='utf-8-sig')
    assert "'已签名，未受信任，完整性无法确认'" in source
    assert "$integrityVerified = $false" in source


def test_default_sign_tool_search_finds_installed_windows_sdk_before_certificate_lookup(tmp_path):
    sdk_root = Path(os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)')) / 'Windows Kits' / '10' / 'bin'
    if not any(sdk_root.glob('*/x64/signtool.exe')):
        pytest.skip('No Windows SDK SignTool is installed in the standard location')

    mini = tmp_path / 'MiniJMP.exe'
    pi_reader = tmp_path / 'PIReader.exe'
    mini.write_bytes(b'MZ test MiniJMP')
    pi_reader.write_bytes(b'MZ test PIReader')
    missing_thumbprint = uuid.uuid4().hex.upper() + 'B' * 8
    result = subprocess.run(
        [POWERSHELL, '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(SCRIPT),
         '-Thumbprint', missing_thumbprint, '-MiniJMPExe', str(mini), '-PIReaderExe', str(pi_reader)],
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace',
        timeout=30,
    )
    assert result.returncode != 0
    assert r'not found in CurrentUser\My' in result.stderr
    assert 'SignTool.exe was not found' not in result.stderr
