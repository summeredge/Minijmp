[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Thumbprint,
    [Parameter(Mandatory = $true)][string]$MiniJMPExe,
    [Parameter(Mandatory = $true)][string]$PIReaderExe,
    [ValidateSet('CurrentUser', 'LocalMachine')][string]$StoreLocation = 'CurrentUser',
    [string]$SignTool
)

$ErrorActionPreference = 'Stop'

function Resolve-SignToolPath {
    param([string]$RequestedPath)

    if ($RequestedPath) {
        if (!(Test-Path -LiteralPath $RequestedPath -PathType Leaf)) {
            throw "SignTool path does not exist: $RequestedPath"
        }
        return (Resolve-Path -LiteralPath $RequestedPath).Path
    }

    $command = Get-Command signtool.exe -CommandType Application -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($command) {
        return $command.Path
    }

    $sdkRoots = @()
    foreach ($programFiles in @(${env:ProgramFiles(x86)}, $env:ProgramFiles)) {
        if ($programFiles) {
            $sdkRoots += Join-Path $programFiles 'Windows Kits\10\bin'
        }
    }
    foreach ($sdkRoot in $sdkRoots) {
        if (!(Test-Path -LiteralPath $sdkRoot -PathType Container)) { continue }
        $versions = Get-ChildItem -LiteralPath $sdkRoot -Directory -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -match '^\d+(\.\d+)+$' } |
            Sort-Object { [version]$_.Name } -Descending
        foreach ($version in $versions) {
            foreach ($architecture in @('x64', 'x86', 'arm64')) {
                $candidate = Join-Path (Join-Path $version.FullName $architecture) 'signtool.exe'
                if (Test-Path -LiteralPath $candidate -PathType Leaf) {
                    return (Resolve-Path -LiteralPath $candidate).Path
                }
            }
        }
    }

    throw 'SignTool.exe was not found on PATH or under the standard Windows Kits\10\bin paths. Install the Windows SDK or pass -SignTool with its full path.'
}

$signToolPath = Resolve-SignToolPath -RequestedPath $SignTool
$thumbprint = ($Thumbprint -replace '\s', '').ToUpperInvariant()
if ($thumbprint -notmatch '^[0-9A-F]{40}$') {
    throw 'Thumbprint must be a 40-character SHA-1 certificate thumbprint.'
}

$resolvedExes = foreach ($path in @($MiniJMPExe, $PIReaderExe)) {
    if (!(Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Executable does not exist: $path"
    }
    (Resolve-Path -LiteralPath $path).Path
}
if ([string]::Equals($resolvedExes[0], $resolvedExes[1], [StringComparison]::OrdinalIgnoreCase)) {
    throw 'MiniJMPExe and PIReaderExe must be different files.'
}

$certificatePath = "Cert:\$StoreLocation\My\$thumbprint"
try {
    $certificate = Get-Item -LiteralPath $certificatePath -ErrorAction Stop
} catch {
    throw "Code-signing certificate $thumbprint was not found in $StoreLocation\My."
}
if (!$certificate.HasPrivateKey) {
    throw "Certificate $thumbprint has no private key."
}
$now = Get-Date
if ($now -lt $certificate.NotBefore -or $now -gt $certificate.NotAfter) {
    throw "Certificate $thumbprint is outside its validity period."
}
$eku = @($certificate.Extensions | Where-Object { $_.Oid.Value -eq '2.5.29.37' } |
    Select-Object -First 1)
$hasCodeSigningEku = $false
if ($eku.Count) {
    foreach ($usage in $eku[0].EnhancedKeyUsages) {
        if ($usage.Value -eq '1.3.6.1.5.5.7.3.3') { $hasCodeSigningEku = $true }
    }
}
if (!$hasCodeSigningEku) {
    throw "Certificate $thumbprint does not include the Code Signing EKU."
}

$storeArguments = @('/s', 'My')
if ($StoreLocation -eq 'LocalMachine') { $storeArguments += '/sm' }
foreach ($path in $resolvedExes) {
    $signArguments = @('sign', '/sha1', $thumbprint, '/fd', 'SHA256') +
        $storeArguments + @($path)
    $previous = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $signOutput = @(& $signToolPath @signArguments 2>&1)
        $signExitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previous
    }
    if ($signExitCode -ne 0) {
        throw "SignTool failed to sign '$path' (exit code $signExitCode): $($signOutput -join ' ')"
    }
}

$results = foreach ($path in $resolvedExes) {
    $signature = Get-AuthenticodeSignature -FilePath $path
    $status = [string]$signature.Status
    if (!$signature.SignerCertificate) {
        throw "No embedded Authenticode signer certificate was found in '$path' (status: $status)."
    }
    $signerThumbprint = ($signature.SignerCertificate.Thumbprint -replace '\s', '').ToUpperInvariant()
    if ($signerThumbprint -ne $thumbprint) {
        throw "Signer thumbprint for '$path' is $signerThumbprint; expected $thumbprint."
    }

    $verifyArguments = @('verify', '/pa', '/v', $path)
    $previous = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $verifyOutput = @(& $signToolPath @verifyArguments 2>&1)
        $verifyExitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previous
    }
    $verifyText = ($verifyOutput | ForEach-Object { $_.ToString() }) -join "`n"
    $trusted = $false
    $integrityVerified = $false
    $badDigest = $verifyText -match '(?i)(0x80096010|TRUST_E_BAD_DIGEST|bad digest|hash mismatch|file has been tampered)'
    $untrustedRoot = $verifyText -match '(?i)(0x800b0109|0x800b0004|CERT_E_UNTRUSTEDROOT|TRUST_E_SUBJECT_NOT_TRUSTED|not trusted by the trust provider|不受信任)'
    if ($status -eq 'HashMismatch' -or $badDigest) {
        throw "Authenticode hash verification failed for '$path' (status: $status, SignTool exit code: $verifyExitCode): $verifyText"
    } elseif ($status -eq 'Valid' -and $verifyExitCode -eq 0) {
        $trusted = $true
        $integrityVerified = $true
    } elseif ($status -in @('NotTrusted', 'UnknownError') -and $verifyExitCode -ne 0 -and $untrustedRoot) {
        Write-Warning "Signature on '$path' is untrusted, and its integrity could not be independently confirmed. Do not treat it as valid or trusted."
    } else {
        throw "Authenticode verification failed for '$path' (status: $status, SignTool exit code: $verifyExitCode): $verifyText"
    }

    $assessment = if ($integrityVerified) {
        '签名有效，受信任，完整性已确认'
    } else {
        '已签名，未受信任，完整性无法确认'
    }
    [pscustomobject][ordered]@{
        File                  = $path
        Status                = $status
        CertificateThumbprint = $signerThumbprint
        Trusted               = $trusted
        IntegrityVerified     = $integrityVerified
        Assessment            = $assessment
    }
}

$results
