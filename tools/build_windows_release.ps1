$ErrorActionPreference = 'Stop'

$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $root '.venv\Scripts\python.exe'
$lock = Join-Path $root 'packaging\windows\requirements-py311.lock'
$entry = Join-Path $root 'packaging\windows_entrypoint.py'
$versionInfo = Join-Path $root 'packaging\windows\version_info.txt'
$packageName = 'MiniJMP-v0.1.0-beta.1-win64'
$sourceName = 'MiniJMP-v0.1.0-beta.1-source'
$buildRoot = Join-Path $root 'build\windows-beta1'
$distRoot = Join-Path $root 'dist'
$releaseDir = Join-Path $distRoot $packageName
$releaseZip = Join-Path $distRoot ($packageName + '.zip')
$sourceZip = Join-Path $distRoot ($sourceName + '.zip')
$hashFile = Join-Path $distRoot 'MiniJMP-v0.1.0-beta.1-SHA256SUMS.txt'
$recordDir = Join-Path $root 'docs\release'
$buildLog = Join-Path $recordDir 'pyinstaller-build-20261022.txt'

function Assert-WorkspacePath([string]$path) {
    $full = [IO.Path]::GetFullPath($path)
    $rootFull = [IO.Path]::GetFullPath($root).TrimEnd('\') + '\'
    if (Test-Path -LiteralPath $full) {
        $resolved = (Resolve-Path -LiteralPath $full).Path
    } else {
        $ancestor = Split-Path -Parent $full
        while (!(Test-Path -LiteralPath $ancestor)) {
            $ancestor = Split-Path -Parent $ancestor
        }
        $resolvedAncestor = (Resolve-Path -LiteralPath $ancestor).Path.TrimEnd('\')
        $suffix = $full.Substring([IO.Path]::GetFullPath($ancestor).Length).TrimStart('\')
        $resolved = Join-Path $resolvedAncestor $suffix
    }
    if (!$resolved.StartsWith($rootFull, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove or write outside the workspace: $resolved"
    }
    return $full
}

function Remove-GeneratedPath([string]$path) {
    $full = Assert-WorkspacePath $path
    if (Test-Path -LiteralPath $full) {
        Remove-Item -LiteralPath $full -Recurse -Force
    }
}

if (!(Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Project Python 3.11 environment not found: $python"
}
if ($env:OS -ne 'Windows_NT') {
    throw 'Build this Windows package on Windows with the project Python 3.11 environment.'
}
$pythonVersion = & $python -c "import sys; print('.'.join(map(str, sys.version_info[:3])))"
if ($pythonVersion -ne '3.11.9') {
    throw "Expected the locked build interpreter Python 3.11.9; found $pythonVersion"
}
$pythonBits = & $python -c "import struct; print(struct.calcsize('P') * 8)"
if ($pythonBits -ne '64') { throw "Expected 64-bit Python; found $pythonBits-bit." }

& $python -m pip install --disable-pip-version-check -r $lock
if ($LASTEXITCODE -ne 0) { throw 'Installing the locked build environment failed.' }
& $python -m pip check
if ($LASTEXITCODE -ne 0) { throw 'The locked build environment has dependency conflicts.' }
$pyinstallerVersion = (& $python -m PyInstaller --version).Trim()
if ($pyinstallerVersion -ne '6.22.3') {
    throw "Expected PyInstaller 6.22.3; found $pyinstallerVersion"
}

New-Item -ItemType Directory -Path (Join-Path $root 'build') -Force | Out-Null
New-Item -ItemType Directory -Path $distRoot -Force | Out-Null
New-Item -ItemType Directory -Path $recordDir -Force | Out-Null
foreach ($path in @($buildRoot, $releaseDir, $releaseZip, $sourceZip, $hashFile, $buildLog)) {
    Remove-GeneratedPath $path
}

$rawDist = Join-Path $buildRoot 'dist'
$workPath = Join-Path $buildRoot 'work'
$specPath = Join-Path $buildRoot 'spec'
New-Item -ItemType Directory -Path $rawDist,$workPath,$specPath -Force | Out-Null

$pyinstallerArgs = @(
    '--noconfirm', '--clean', '--onedir', '--windowed', '--noupx',
    '--contents-directory', '_internal', '--name', 'MiniJMP',
    '--icon', (Join-Path $root 'icon\icon_big.ico'),
    '--version-file', $versionInfo,
    '--specpath', $specPath, '--workpath', $workPath, '--distpath', $rawDist,
    '--paths', (Join-Path $root 'code'),
    '--hidden-import', 'openpyxl', '--hidden-import', 'xlrd',
    '--add-data', ((Join-Path $root 'code\help.json') + ':.'),
    '--add-data', ((Join-Path $root 'help') + ':help'),
    '--add-data', ((Join-Path $root 'user_config') + ':user_config'),
    '--add-data', ((Join-Path $root 'sample_data\coatings.csv') + ':sample_data'),
    '--add-data', ((Join-Path $root 'sample_data\Gasket.xlsx') + ':sample_data'),
    '--add-data', ((Join-Path $root 'sample_data\ctrl_chart_test.pickle') + ':sample_data'),
    '--add-data', ((Join-Path $root 'sample_data\CPK_sample.pickle') + ':sample_data'),
    '--add-data', ((Join-Path $root 'sample_data\GRR_crossed.pickle') + ':sample_data'),
    '--add-data', ((Join-Path $root 'sample_data\fit_sample_data.pickle') + ':sample_data'),
    $entry
)

"Building with Python $pythonVersion and PyInstaller $pyinstallerVersion" | Set-Content -LiteralPath $buildLog -Encoding utf8
& $python -m PyInstaller @pyinstallerArgs 2>&1 | Tee-Object -FilePath $buildLog -Append
$buildExit = $LASTEXITCODE
if ($buildExit -ne 0) { throw "PyInstaller failed with exit code $buildExit. See $buildLog" }

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
& $python (Join-Path $root 'tools\write_third_party_notices.py') $releaseDir
if ($LASTEXITCODE -ne 0) { throw 'Generating third-party notices failed.' }

$head = (git -C $root rev-parse HEAD).Trim()
$branch = (git -C $root branch --show-current).Trim()
$os = Get-CimInstance Win32_OperatingSystem
$coreVersions = & $python -c "import importlib.metadata as m; names=['numpy','scipy','pandas','matplotlib','seaborn','statsmodels','openpyxl','xlrd','Pillow','prettytable']; print('; '.join(n+' '+m.version(n) for n in names))"
$buildInfo = @(
    'MiniJMP v0.1.0-beta.1 Windows x64',
    "Base Git HEAD: $head",
    "Branch: $branch",
    'The package includes the current working-tree changes; no commit or push was made.',
    "Build interpreter: Python $pythonVersion",
    "Builder: PyInstaller $pyinstallerVersion (onedir, windowed, noupx)",
    "Windows: $($os.Caption), version $($os.Version), build $($os.BuildNumber), $($os.OSArchitecture)",
    "Core dependencies: $coreVersions",
    'PIReader.exe, PI SDK, PI configuration, and credentials are not included.'
) -join "`r`n"
Set-Content -LiteralPath (Join-Path $releaseDir 'BUILD-INFO.txt') -Value $buildInfo -Encoding utf8

$sourceStage = Join-Path $buildRoot 'source'
New-Item -ItemType Directory -Path $sourceStage -Force | Out-Null
foreach ($name in @('code','help','icon','user_config','sample_data','tests','tools','packaging')) {
    Copy-Item -LiteralPath (Join-Path $root $name) -Destination $sourceStage -Recurse
}
New-Item -ItemType Directory -Path (Join-Path $sourceStage 'docs') -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $root 'docs\MENU_TRANSLATION.md') -Destination (Join-Path $sourceStage 'docs\MENU_TRANSLATION.md')
foreach ($name in @('LICENSE','README.md','AGENTS.md','CODING_STANDARDS.md','CONTRIBUTING.md','CHANGES','requirements.txt','setup_env.bat','start.py','win_start.bat','win_start_no_cmd_win.vbs')) {
    Copy-Item -LiteralPath (Join-Path $root $name) -Destination $sourceStage
}
$cacheDirs = Get-ChildItem -LiteralPath $sourceStage -Directory -Force -Recurse |
    Where-Object { $_.Name -in @('__pycache__','.pytest_cache') } |
    Sort-Object { $_.FullName.Length } -Descending
foreach ($directory in $cacheDirs) { Remove-Item -LiteralPath $directory.FullName -Recurse -Force }
foreach ($file in (Get-ChildItem -LiteralPath $sourceStage -File -Force -Recurse -Filter '*.pyc')) {
    Remove-Item -LiteralPath $file.FullName -Force
}
$sourceInfo = @(
    'MiniJMP v0.1.0-beta.1 corresponding source bundle',
    "Base Git HEAD: $head",
    "Release branch: $branch",
    'This source archive contains the working-tree sources and build inputs used for the adjacent binary.',
    'The release changes were not committed or pushed; this archive is the exact source handoff for the binary.'
) -join "`r`n"
Set-Content -LiteralPath (Join-Path $sourceStage 'SOURCE-BUNDLE-INFO.txt') -Value $sourceInfo -Encoding utf8
Compress-Archive -Path (Join-Path $sourceStage '*') -DestinationPath $sourceZip -CompressionLevel Optimal

$sourceHash = (Get-FileHash -LiteralPath $sourceZip -Algorithm SHA256).Hash
$sourceNotice = @(
    'Exact corresponding source is provided next to this folder as MiniJMP-v0.1.0-beta.1-source.zip.',
    "Source archive SHA256: $sourceHash",
    "Base Git HEAD: $head",
    "Release branch: $branch",
    'The working-tree release changes are included in the source archive and were not pushed to GitHub.',
    'The source bundle contains the Windows build script and locked Python 3.11 dependency list.',
    'Repository origin: https://github.com/summeredge/Minijmp'
) -join "`r`n"
Set-Content -LiteralPath (Join-Path $releaseDir 'SOURCE-CODE.txt') -Value $sourceNotice -Encoding utf8

$forbiddenDirectories = Get-ChildItem -LiteralPath $releaseDir -Directory -Force -Recurse |
    Where-Object { $_.Name -in @('.git','.venv','tests','docs','.pytest_cache','__pycache__') }
if ($forbiddenDirectories) {
    throw ('Forbidden development directories found in package: ' + (($forbiddenDirectories.FullName) -join ', '))
}
$sensitivePiFiles = Get-ChildItem -LiteralPath $releaseDir -File -Force -Recurse |
    Where-Object { $_.Name -in @('PIReader.exe','config.txt') }
if ($sensitivePiFiles) {
    throw ('Unexpected PI files found in package: ' + (($sensitivePiFiles.FullName) -join ', '))
}

Compress-Archive -Path (Join-Path $releaseDir '*') -DestinationPath $releaseZip -CompressionLevel Optimal
$exeHash = (Get-FileHash -LiteralPath (Join-Path $releaseDir 'MiniJMP.exe') -Algorithm SHA256).Hash
$zipHash = (Get-FileHash -LiteralPath $releaseZip -Algorithm SHA256).Hash
$hashes = @(
    "$exeHash  $packageName/MiniJMP.exe",
    "$zipHash  $packageName.zip",
    "$sourceHash  $sourceName.zip"
) -join "`r`n"
Set-Content -LiteralPath $hashFile -Value $hashes -Encoding ascii

Get-Item -LiteralPath $releaseZip,$sourceZip,(Join-Path $releaseDir 'MiniJMP.exe') |
    Select-Object FullName,Length
Get-Content -LiteralPath $hashFile
Write-Output "Build log: $buildLog"
