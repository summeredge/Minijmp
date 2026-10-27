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
$releaseVersion = 'V0.1-beta4'
$productVersion = 'v0.1.0-beta.4'

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

$head = (git -C $root rev-parse HEAD).Trim()
$branch = (git -C $root branch --show-current).Trim()
$originMain = (git -C $root rev-parse origin/main).Trim()
if ($branch -ne 'main') { throw "Release builds must run on main; branch is '$branch'." }
if ($head -ne $originMain) {
    throw 'HEAD differs from origin/main. Fetch and reconcile before building.'
}

# Uncommitted work is allowed; it is recorded instead of being discarded.
$dirty = @(git -C $root status --porcelain --untracked-files=normal)
if ($dirty.Count) {
    Write-Warning "Working tree has $($dirty.Count) uncommitted or untracked entries; the build uses the files on disk and BUILD-INFO records this state."
    $dirty | Select-Object -First 10 | ForEach-Object { Write-Warning "  $_" }
}

$required = @(
    'PIReader\PIReader.exe', 'PIReader\config.txt', 'LICENSE',
    'packaging\windows\USAGE.txt', 'packaging\windows\version_info.txt',
    'icon\icon_big.ico', 'code\help.json', 'help', 'user_config\default.conf'
)
foreach ($item in $required) {
    if (!(Test-Path -LiteralPath (Join-Path $root $item))) {
        throw "Required build input is missing: $item"
    }
}

$distRoot = Join-Path $root 'dist'
$buildRoot = Join-Path $root 'build\windows-pkg'
$releaseDir = Join-Path $distRoot "MiniJMP-$releaseVersion"
$releaseZip = Join-Path $distRoot "MiniJMP-$releaseVersion.zip"
$sourceZip = Join-Path $distRoot "MiniJMP-$releaseVersion-source.zip"
$hashFile = Join-Path $distRoot "MiniJMP-$releaseVersion-SHA256SUMS.txt"
$recordDir = Join-Path $root 'docs\release'
$buildLog = Join-Path $recordDir "pyinstaller-build-$releaseVersion.txt"
$manifestPath = Join-Path $recordDir "build-inputs-$releaseVersion.txt"

# A previous run leaves hundreds of megabytes; clearing it is a deliberate,
# separate action documented in PACKAGING.md.
$existing = @($releaseDir, $releaseZip, $sourceZip, $hashFile, $buildLog, $manifestPath,
    $buildRoot) | Where-Object { Test-Path -LiteralPath $_ }
if ($existing) {
    throw ('Existing build output must be removed before rebuilding; run the cleanup step in PACKAGING.md:' + $nl + ($existing -join $nl))
}
if (Test-Path -LiteralPath $distRoot) {
    $old = @(Get-ChildItem -LiteralPath $distRoot -Force -Filter 'MiniJMP-V*')
    if ($old) {
        throw ('dist already holds earlier MiniJMP releases; remove them deliberately first: ' + (($old.FullName) -join ', '))
    }
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

# PIReader sits beside the EXE: frozen modules live in _internal, so the app
# root resolves to the EXE directory. config.txt ships verbatim.
$piTarget = Join-Path $releaseDir 'PIReader'
$piSource = Join-Path $root 'PIReader'
$piFiles = @(Get-ChildItem -LiteralPath $piSource -File -Recurse | Where-Object {
    $_.FullName.Substring($piSource.Length).TrimStart('\') -notmatch '^(obj|bin|\.vs)\\'
})
foreach ($file in $piFiles) {
    $relative = $file.FullName.Substring($piSource.Length).TrimStart('\')
    $destination = Join-Path $piTarget $relative
    New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
    Copy-Item -LiteralPath $file.FullName -Destination $destination
}
$piDlls = @($piFiles | Where-Object { $_.Extension -eq '.dll' }).Count

& $python (Join-Path $root 'tools\write_third_party_notices.py') $releaseDir
if ($LASTEXITCODE -ne 0) { throw 'Generating third-party notices failed.' }

$os = Get-CimInstance Win32_OperatingSystem
$pythonVersion = (@(& $python -c "import sys; print('.'.join(map(str, sys.version_info[:3])))") -join '').Trim()
$pyinstallerVersion = (@(& $python -m PyInstaller --version) -join '').Trim()
$coreVersions = & $python -c "import importlib.metadata as m; names=['numpy','scipy','pandas','matplotlib','seaborn','statsmodels','openpyxl','xlrd','Pillow','prettytable']; print('; '.join(n+' '+m.version(n) for n in names))"
$treeState = if ($dirty.Count) {
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
    "PIReader: bundled beside MiniJMP.exe with $($piFiles.Count) files, including config.txt as shipped; $piDlls bundled OSIsoft DLLs.",
    'PI SDK/PIPC runtime and PI Server connectivity are target-machine prerequisites; this build did not verify them.',
    'Defender, TsdEncrypt/DLP and non-admin execution on office machines were not verified by this build.'
) -join $nl
Set-Content -LiteralPath (Join-Path $releaseDir 'BUILD-INFO.txt') -Value $buildInfo -Encoding utf8

# Stage the sources actually used from disk, in TEMP so DLP-synced folders
# cannot rewrite them mid-archive.
$sourceStage = Join-Path $env:TEMP ('MiniJMP-source-' + [guid]::NewGuid().ToString('N'))
try {
    New-Item -ItemType Directory -Path $sourceStage -Force | Out-Null
    $staged = & $python $makeZip 'stage-source' $root $sourceStage
    if ($LASTEXITCODE -ne 0) { throw 'Staging corresponding sources failed.' }
    Write-Output $staged

    & $python $makeZip 'manifest' $sourceStage (Join-Path $sourceStage 'SOURCE-MANIFEST.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Writing the source manifest failed.' }
    & $python $makeZip 'manifest' $releaseDir $manifestPath
    if ($LASTEXITCODE -ne 0) { throw 'Writing the runtime manifest failed.' }

    $sourceInfo = @(
        "MiniJMP $productVersion corresponding source",
        "Release name: $releaseVersion",
        "Base Git HEAD: $head",
        "Release branch: $branch",
        "Working tree: $treeState",
        'This archive holds the on-disk sources and build inputs used for the adjacent binary, including the PIReader project sources and tools/make_zip.py.',
        'SOURCE-MANIFEST.txt lists every file with its SHA256 at packaging time.',
        'Repository origin: https://github.com/summeredge/Minijmp'
    ) -join $nl
    Set-Content -LiteralPath (Join-Path $sourceStage 'SOURCE-BUNDLE-INFO.txt') -Value $sourceInfo -Encoding utf8
    & $python (Join-Path $root 'tools\write_third_party_notices.py') $sourceStage
    if ($LASTEXITCODE -ne 0) { throw 'Generating source bundle third-party notices failed.' }

    & $python $makeZip 'scan' $sourceStage
    if ($LASTEXITCODE -ne 0) { throw 'Encrypted (DLP) files found in the staged sources.' }

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
