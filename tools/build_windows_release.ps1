param(
    [switch]$SkipSmoke
)

# The only release entry point. It never deletes earlier artifacts and never
# changes Defender, DLP or machine policy settings.

$ErrorActionPreference = 'Stop'
$nl = [Environment]::NewLine

$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $root '.venv\Scripts\python.exe'
$versionInfo = Join-Path $root 'packaging\windows\version_info.txt'
$entry = Join-Path $root 'packaging\windows_entrypoint.py'
$makeZip = Join-Path $root 'tools\make_zip.py'
$smoke = Join-Path $root 'tools\smoke_launch.py'
$releaseVersion = 'V1.0-beta2'
$productVersion = 'v1.0.0-beta.2'

if (!(Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Project Python environment not found: $python"
}
if ($env:OS -ne 'Windows_NT') {
    throw 'Build this Windows package on Windows x64.'
}

$envReport = @(& $python (Join-Path $root 'tools\release_env.py') 2>&1)
$envReport | ForEach-Object { Write-Output $_ }
if ($LASTEXITCODE -ne 0) {
    throw 'The build interpreter does not satisfy the release requirements; see the lines above.'
}
$metadata = @(& $python (Join-Path $root 'tools\release_metadata.py') 2>&1)
$metadata | ForEach-Object { Write-Output $_ }
if ($LASTEXITCODE -ne 0) {
    throw 'Version identifiers disagree; fix them before building.'
}

$sourceBundleInfo = Join-Path $root 'SOURCE-BUNDLE-INFO.txt'
if (Test-Path -LiteralPath $sourceBundleInfo -PathType Leaf) {
    $headLine = Get-Content -LiteralPath $sourceBundleInfo |
        Where-Object { $_ -match '^Base Git HEAD: ([0-9a-f]{40})$' } | Select-Object -First 1
    if (!$headLine) { throw 'SOURCE-BUNDLE-INFO.txt has no valid Base Git HEAD.' }
    $head = [regex]::Match($headLine, '^Base Git HEAD: ([0-9a-f]{40})$').Groups[1].Value
    $branch = 'source bundle'
    $originMain = 'not included in source bundle'
    $dirty = @()
    Write-Warning 'Building from the corresponding source ZIP; Git metadata is not included.'
} else {
    $head = (git -C $root rev-parse HEAD).Trim()
    $branch = (git -C $root branch --show-current).Trim()
    $originMain = (git -C $root rev-parse origin/main).Trim()
    if ($branch -ne 'main') { throw "Release builds must run on main; branch is '$branch'." }
    & git -C $root merge-base --is-ancestor origin/main HEAD
    if ($LASTEXITCODE -ne 0) { throw 'origin/main is not an ancestor of HEAD; reconcile the branch before building.' }

    $dirty = @(git -C $root status --porcelain --untracked-files=normal)
    if ($dirty.Count) {
        throw "Refusing to build from a dirty working tree; commit or remove the $($dirty.Count) changed entries first."
    }
}

$required = @(
    'PIReader\PIReader.exe', 'PIReader\OSIsoft.PISDK.dll', 'PIReader\OSIsoft.PISDKCommon.dll',
    'PIReader\OSIsoft.PITimeServer.dll', 'PIReader\config.example.txt', 'PIReader\tags.example.txt', 'LICENSE',
    'packaging\windows\PI-SDK-NOTICE.txt',
    'packaging\windows\USAGE.txt', 'packaging\windows\version_info.txt',
    'icon\icon_big.ico', 'code\help.json', 'help', 'user_config\default.conf'
)
foreach ($item in $required) {
    if (!(Test-Path -LiteralPath (Join-Path $root $item))) {
        throw "Required build input is missing: $item"
    }
}
$template = (Get-Content -LiteralPath (Join-Path $root 'PIReader\config.example.txt') -Raw).Replace("`r`n", "`n").Trim()
if ($template -cne "Server=`nUser=`nPassword=`nInterval=5m`nBlockDays=7" -or
    [IO.File]::ReadAllText((Join-Path $root 'PIReader\tags.example.txt')).Trim()) {
    throw 'PIReader templates are not the clean release templates.'
}

$distRoot = Join-Path $root 'dist'
$buildRoot = Join-Path $root "build\windows-pkg-$releaseVersion"
$releaseDir = Join-Path $distRoot "MiniJMP-$releaseVersion"
$releaseZip = Join-Path $distRoot "MiniJMP-$releaseVersion.zip"
$sourceZip = Join-Path $distRoot "MiniJMP-$releaseVersion-source.zip"
$hashFile = Join-Path $distRoot "MiniJMP-$releaseVersion-SHA256SUMS.txt"
$recordDir = Join-Path $root 'docs\release'
$buildLog = Join-Path $recordDir "pyinstaller-build-$releaseVersion.txt"
$manifestPath = Join-Path $recordDir "build-inputs-$releaseVersion.txt"

# Beta2 outputs are version-specific and never overwrite or remove earlier artifacts.
$existing = @($releaseDir, $releaseZip, $sourceZip, $hashFile, $buildLog, $manifestPath,
    $buildRoot) | Where-Object { Test-Path -LiteralPath $_ }
if ($existing) {
    throw ('Existing beta2 output is preserved; review it before moving it aside for a separate build:' + $nl + ($existing -join $nl))
}
New-Item -ItemType Directory -Path $distRoot, $recordDir, $buildRoot -Force | Out-Null
$rawDist = Join-Path $buildRoot 'dist'
$workPath = Join-Path $buildRoot 'work'
$specPath = Join-Path $buildRoot 'spec'
New-Item -ItemType Directory -Path $rawDist, $workPath, $specPath -Force | Out-Null

$pyinstallerArgs = @(
    '--noconfirm', '--clean', '--onedir', '--windowed', '--noupx',
    '--contents-directory', '_internal', '--name', 'MiniJMP',
    '--icon', (Join-Path $root 'icon\icon_big.ico'),
    '--version-file', $versionInfo,
    '--specpath', $specPath, '--workpath', $workPath, '--distpath', $rawDist,
    '--paths', (Join-Path $root 'code'),
    '--hidden-import', 'openpyxl', '--hidden-import', 'xlrd',
    '--add-data', ((Join-Path $root 'code\help.json') + ':.' ),
    '--add-data', ((Join-Path $root 'help') + ':help'),
    '--add-data', ((Join-Path $root 'user_config\default.conf') + ':user_config'),
    '--add-data', ((Join-Path $root 'sample_data\coatings.csv') + ':sample_data'),
    '--add-data', ((Join-Path $root 'sample_data\Gasket.xlsx') + ':sample_data'),
    '--add-data', ((Join-Path $root 'sample_data\ctrl_chart_test.pickle') + ':sample_data'),
    '--add-data', ((Join-Path $root 'sample_data\CPK_sample.pickle') + ':sample_data'),
    '--add-data', ((Join-Path $root 'sample_data\GRR_crossed.pickle') + ':sample_data'),
    '--add-data', ((Join-Path $root 'sample_data\fit_sample_data.pickle') + ':sample_data'),
    $entry
)

$envReport | Set-Content -LiteralPath $buildLog -Encoding utf8
"Building MiniJMP $productVersion with PyInstaller" | Add-Content -LiteralPath $buildLog
# PyInstaller writes ordinary progress to stderr; only its exit code decides.
$previous = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
try {
    & $python -m PyInstaller @pyinstallerArgs *>> $buildLog
    $buildExit = $LASTEXITCODE
} finally {
    $ErrorActionPreference = $previous
}
if ($buildExit -ne 0) {
    throw "PyInstaller failed with exit code $buildExit. See $buildLog"
}
Get-Content -LiteralPath $buildLog -Tail 5 | ForEach-Object { Write-Output $_ }

$rawApp = Join-Path $rawDist 'MiniJMP'
if (!(Test-Path -LiteralPath (Join-Path $rawApp 'MiniJMP.exe') -PathType Leaf) -or
    !(Test-Path -LiteralPath (Join-Path $rawApp '_internal') -PathType Container)) {
    throw 'PyInstaller did not produce MiniJMP.exe and _internal.'
}
$externalIcons = Get-ChildItem -LiteralPath $rawApp -File -Recurse -Filter 'icon.png'
if ($externalIcons) {
    throw ('Unexpected external runtime icon.png found: ' + (($externalIcons.FullName) -join ', '))
}

Copy-Item -LiteralPath $rawApp -Destination $releaseDir -Recurse
Copy-Item -LiteralPath (Join-Path $root 'LICENSE') -Destination (Join-Path $releaseDir 'LICENSE')
Copy-Item -LiteralPath (Join-Path $root 'packaging\windows\USAGE.txt') -Destination (Join-Path $releaseDir 'README.txt')
Copy-Item -LiteralPath (Join-Path $root 'packaging\windows\PI-SDK-NOTICE.txt') -Destination (Join-Path $releaseDir 'PI-SDK-NOTICE.txt')

# PIReader sits beside the EXE: frozen modules live in _internal, so the app
# root resolves to the EXE directory. Local config and tags files never ship.
$piTarget = Join-Path $releaseDir 'PIReader'
$piSource = Join-Path $root 'PIReader'
New-Item -ItemType Directory -Path $piTarget -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $piSource 'PIReader.exe') -Destination $piTarget
$piDllNames = @('OSIsoft.PISDK.dll', 'OSIsoft.PISDKCommon.dll', 'OSIsoft.PITimeServer.dll')
$piDllInfo = foreach ($name in $piDllNames) {
    $source = Join-Path $piSource $name
    $target = Join-Path $piTarget $name
    Copy-Item -LiteralPath $source -Destination $target
    $sourceFile = Get-Item -LiteralPath $source
    $targetFile = Get-Item -LiteralPath $target
    $sourceHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $source).Hash
    $targetHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $target).Hash
    if ($sourceFile.Length -ne $targetFile.Length -or $sourceHash -ne $targetHash) {
        throw "PI SDK DLL copy does not match its source: $name"
    }
    $version = [Diagnostics.FileVersionInfo]::GetVersionInfo($source).FileVersion
    "{0}: version {1}; bytes {2}; SHA256 {3}" -f $name, $version, $sourceFile.Length, $sourceHash
}
Copy-Item -LiteralPath (Join-Path $piSource 'config.example.txt') -Destination (Join-Path $piTarget 'config.txt')
Copy-Item -LiteralPath (Join-Path $piSource 'tags.example.txt') -Destination (Join-Path $piTarget 'tags.txt')
& $python (Join-Path $root 'tools\write_third_party_notices.py') $releaseDir
if ($LASTEXITCODE -ne 0) { throw 'Generating third-party notices failed.' }

$os = Get-CimInstance Win32_OperatingSystem
$pythonVersion = (@(& $python -c "import sys; print('.'.join(map(str, sys.version_info[:3])))") -join '').Trim()
$pyinstallerVersion = (@(& $python -m PyInstaller --version) -join '').Trim()
$coreVersions = & $python -c "import importlib.metadata as m; names=['numpy','scipy','pandas','matplotlib','seaborn','statsmodels','openpyxl','xlrd','Pillow','prettytable']; print('; '.join(n+' '+m.version(n) for n in names))"
$treeState = if ($branch -eq 'source bundle') {
    'Built from the corresponding source ZIP; Git metadata is not included, so changes after extraction are not measured.'
} elseif ($dirty.Count) {
    "$($dirty.Count) uncommitted or untracked entries were present; the build used the files on disk, not a clean checkout."
} else {
    'Working tree was clean; build inputs matched Git HEAD.'
}
$buildInfo = @(
    "MiniJMP $productVersion Windows x64",
    "Release name: $releaseVersion",
    "Base Git HEAD: $head",
    "Branch: $branch",
    "Origin/main: $originMain",
    "Working tree: $treeState",
    "Python: $pythonVersion",
    "PyInstaller: $pyinstallerVersion (onedir, windowed, noupx, _internal)",
    "Windows: $($os.Caption), version $($os.Version), build $($os.BuildNumber), $($os.OSArchitecture)",
    "Core dependencies: $coreVersions",
    'PIReader: bundled beside MiniJMP.exe with PIReader.exe, three PI SDK DLLs and clean config.txt/tags.txt templates.',
    ($piDllInfo -join $nl),
    'PI SDK DLLs are proprietary third-party files, not GPL; redistribution rights are unconfirmed. This package is for authorized internal validation only; external distribution is blocked pending written authorization.',
    'The DLLs do not include or register the full PI SDK/PIPC runtime. Target-machine runtime, licensing and PI Server connectivity were not verified.',
    'Defender, TsdEncrypt/DLP and non-admin execution on office machines were not verified by this build.'
) -join $nl
Set-Content -LiteralPath (Join-Path $releaseDir 'BUILD-INFO.txt') -Value $buildInfo -Encoding utf8
@(
    "Corresponding source archive: MiniJMP-$releaseVersion-source.zip",
    "Base Git HEAD: $head",
    'Repository: https://github.com/summeredge/Minijmp',
    'The source ZIP contains the corresponding source files and build scripts; it omits .git, OSIsoft PI SDK assemblies and real PI connection settings.',
    'Build prerequisites for PIReader are listed in PACKAGING.md and SOURCE-BUNDLE-INFO.txt.'
) -join $nl | Set-Content -LiteralPath (Join-Path $releaseDir 'SOURCE-CODE.txt') -Encoding utf8

# Stage the sources actually used from disk, in TEMP so DLP-synced folders
# cannot rewrite them mid-archive.
$sourceStage = Join-Path $env:TEMP ('MiniJMP-source-' + [guid]::NewGuid().ToString('N'))
try {
    New-Item -ItemType Directory -Path $sourceStage -Force | Out-Null
    $staged = & $python $makeZip 'stage-source' $root $sourceStage
    if ($LASTEXITCODE -ne 0) { throw 'Staging corresponding sources failed.' }
    Write-Output $staged

    $sourceInfo = @(
        "MiniJMP $productVersion corresponding source",
        "Release name: $releaseVersion",
        "Base Git HEAD: $head",
        "Release branch: $branch",
        "Working tree: $treeState",
        'This archive holds the on-disk sources and build inputs used for the adjacent binary, including the PIReader project sources and tools/make_zip.py.',
        'SOURCE-MANIFEST.txt lists every staged file except the manifest itself, with its SHA256 at packaging time.',
        'The source ZIP omits .git and OSIsoft PI SDK assemblies; the corresponding SDK and .NET Framework 4.8 build tools must be supplied under their applicable licenses to rebuild PIReader.',
        'Repository origin: https://github.com/summeredge/Minijmp'
    ) -join $nl
    Set-Content -LiteralPath (Join-Path $sourceStage 'SOURCE-BUNDLE-INFO.txt') -Value $sourceInfo -Encoding utf8
    & $python (Join-Path $root 'tools\write_third_party_notices.py') $sourceStage
    if ($LASTEXITCODE -ne 0) { throw 'Generating source bundle third-party notices failed.' }

    & $python $makeZip 'scan' $sourceStage
    if ($LASTEXITCODE -ne 0) { throw 'Encrypted (DLP) files found in the staged sources.' }

    & $python $makeZip 'manifest' $sourceStage (Join-Path $sourceStage 'SOURCE-MANIFEST.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Writing the source manifest failed.' }
    & $python $makeZip 'manifest' $releaseDir $manifestPath
    if ($LASTEXITCODE -ne 0) { throw 'Writing the runtime manifest failed.' }

    & $python $makeZip 'make' $releaseDir $releaseZip
    if ($LASTEXITCODE -ne 0) { throw 'Creating the runtime archive failed.' }
    & $python $makeZip 'make' $sourceStage $sourceZip '--root-name' "MiniJMP-$releaseVersion-source"
    if ($LASTEXITCODE -ne 0) { throw 'Creating the source archive failed.' }
} finally {
    if (Test-Path -LiteralPath $sourceStage) {
        Remove-Item -LiteralPath $sourceStage -Recurse -Force
    }
}

& $python $makeZip 'scan' $releaseDir
if ($LASTEXITCODE -ne 0) { throw 'Encrypted (DLP) files found in the package.' }

# Transparent encryption can rewrite archives after they land, and it changes
# size without touching mtime. Wait, then read full content instead of metadata.
Write-Output 'Waiting 120s for the transparent-encryption rewrite to settle...'
Start-Sleep -Seconds 120
$artifacts = @($releaseZip, $sourceZip)
$digests = @{}
foreach ($artifact in $artifacts) {
    $line = @(& $python $makeZip 'rehash' $artifact '--interval' '15' '--attempts' '3')
    if ($LASTEXITCODE -ne 0) { throw "Hashing $artifact failed: $line" }
    $digests[$artifact] = ($line -join '').Trim() -replace '^SHA256=', ''
}

$exeRelative = "MiniJMP-$releaseVersion/MiniJMP.exe"
$inspect = @(& $python $makeZip 'inspect' $releaseZip '--entry' $exeRelative)
if ($LASTEXITCODE -ne 0) { throw "Runtime archive failed CRC or entry checks: $inspect" }
$inspect | ForEach-Object { Write-Output $_ }
$zipExeHash = @($inspect | Where-Object { $_ -like 'ENTRY-SHA256=*' })[0] -replace '^ENTRY-SHA256=', ''
$exeLine = @(& $python $makeZip 'rehash' (Join-Path $releaseDir 'MiniJMP.exe') '--interval' '5' '--attempts' '2')
if ($LASTEXITCODE -ne 0) { throw "Hashing MiniJMP.exe failed: $exeLine" }
$exeHash = ($exeLine -join '').Trim() -replace '^SHA256=', ''
if ($zipExeHash -ne $exeHash) {
    throw "The EXE inside the archive differs from the built EXE ($zipExeHash vs $exeHash)."
}
foreach ($name in $piDllNames) {
    $entry = "MiniJMP-$releaseVersion/PIReader/$name"
    $dllInspect = @(& $python $makeZip 'inspect' $releaseZip '--entry' $entry)
    if ($LASTEXITCODE -ne 0) { throw "Runtime archive is missing or corrupt: $entry ($dllInspect)" }
    $zipHash = @($dllInspect | Where-Object { $_ -like 'ENTRY-SHA256=*' })[0] -replace '^ENTRY-SHA256=', ''
    $sourceHash = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $piSource $name)).Hash
    if ($zipHash -ne $sourceHash) { throw "The PI SDK DLL inside the runtime ZIP differs from its source: $name" }
}

$hashes = @(
    "$exeHash  $exeRelative",
    "$($digests[$releaseZip])  MiniJMP-$releaseVersion.zip",
    "$($digests[$sourceZip])  MiniJMP-$releaseVersion-source.zip"
) -join $nl
Set-Content -LiteralPath $hashFile -Value $hashes -Encoding ascii

Write-Output 'Re-verifying after SHA256SUMS was written (90s window)...'
Start-Sleep -Seconds 90
foreach ($artifact in $artifacts) {
    $line = @(& $python $makeZip 'rehash' $artifact '--interval' '15' '--attempts' '2')
    if ($LASTEXITCODE -ne 0) { throw "Hashing $artifact failed on re-verification: $line" }
    $current = ($line -join '').Trim() -replace '^SHA256=', ''
    if ($current -ne $digests[$artifact]) {
        throw "Bytes drifted after packaging; recorded $($digests[$artifact]) but read $current. Do not distribute this build."
    }
}
& $python $makeZip 'scan' $hashFile
if ($LASTEXITCODE -ne 0) { throw 'SHA256SUMS was replaced by a DLP container; rewrite it before distributing.' }

if (!$SkipSmoke) {
    & $python $smoke (Join-Path $releaseDir 'MiniJMP.exe') 90
    if ($LASTEXITCODE -ne 0) { throw 'Smoke launch of the dist build failed.' }
    $unzipRoot = Join-Path $env:TEMP ('MiniJMP-unzip-' + [guid]::NewGuid().ToString('N'))
    try {
        & $python -m zipfile -e $releaseZip $unzipRoot
        if ($LASTEXITCODE -ne 0) { throw 'Extracting the runtime archive failed.' }
        & $python $smoke (Join-Path $unzipRoot "MiniJMP-$releaseVersion\MiniJMP.exe") 90
        if ($LASTEXITCODE -ne 0) { throw 'Smoke launch of the unzipped build failed.' }
    } finally {
        if (Test-Path -LiteralPath $unzipRoot) { Remove-Item -LiteralPath $unzipRoot -Recurse -Force }
    }
}

Get-Item -LiteralPath $releaseZip, $sourceZip, (Join-Path $releaseDir 'MiniJMP.exe') |
    Select-Object FullName, Length
Get-Content -LiteralPath $hashFile
Write-Output "Build log: $buildLog"
Write-Output "Runtime manifest: $manifestPath"
