param(
    [ValidatePattern('^[A-Za-z0-9-]*$')]
    [string]$BuildSuffix = ''
)

$ErrorActionPreference = 'Stop'

$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $root '.venv\Scripts\python.exe'
$lock = Join-Path $root 'packaging\windows\requirements-py311.lock'
$entry = Join-Path $root 'packaging\windows_entrypoint.py'
$versionInfo = Join-Path $root 'packaging\windows\version_info.txt'
$head = (git -C $root rev-parse HEAD).Trim()
$shortHead = (git -C $root rev-parse --short HEAD).Trim()
if ($BuildSuffix) { $shortHead = "$shortHead-$BuildSuffix" }
$branch = (git -C $root branch --show-current).Trim()
$originMain = (git -C $root rev-parse origin/main).Trim()
if ($branch -ne 'main' -or $head -ne $originMain) {
    throw 'Build from main synchronized with origin/main; fetch before building.'
}
$dirty = @(git -C $root status --porcelain --untracked-files=normal)
if ($dirty.Count) {
    throw ("Refusing to build from a dirty working tree ($($dirty.Count) entries); commit or remove them first:`n" + (($dirty | Select-Object -First 10) -join "`n"))
}
$version = 'v0.1.0-beta.2'
if (!(Select-String -LiteralPath $versionInfo -Pattern $version -SimpleMatch -Quiet)) {
    throw "packaging\windows\version_info.txt does not declare $version"
}
$packageName = "MiniJMP-$version-$shortHead-win64"
$sourceName = "MiniJMP-$version-$shortHead-source"
$buildRoot = Join-Path $root "build\windows-$shortHead"
$distRoot = Join-Path $root 'dist'
$releaseDir = Join-Path $distRoot $packageName
$releaseZip = Join-Path $distRoot ($packageName + '.zip')
$sourceZip = Join-Path $distRoot ($sourceName + '.zip')
$hashFile = Join-Path $distRoot "MiniJMP-$version-$shortHead-SHA256SUMS.txt"
$recordDir = Join-Path $root 'docs\release'
$buildLog = Join-Path $recordDir "pyinstaller-build-$shortHead.txt"

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

& $python -c "import importlib.metadata as m, pathlib, sys; pins=[line.strip().split('==') for line in pathlib.Path(sys.argv[1]).read_text().splitlines() if '==' in line]; mismatch=[n+'=='+v for n,v in pins if m.version(n)!=v]; print('Dependency mismatches: '+str(mismatch)); sys.exit(bool(mismatch))" $lock
if ($LASTEXITCODE -ne 0) { throw 'Use a separate Python 3.11.9 environment matching the lock; the development environment was not modified.' }
& $python -m pip check
if ($LASTEXITCODE -ne 0) { throw 'The locked build environment has dependency conflicts.' }
$pyinstallerVersion = (& $python -m PyInstaller --version).Trim()
if ($pyinstallerVersion -ne '6.22.3') {
    throw "Expected PyInstaller 6.22.3; found $pyinstallerVersion"
}

New-Item -ItemType Directory -Path (Join-Path $root 'build') -Force | Out-Null
New-Item -ItemType Directory -Path $distRoot -Force | Out-Null
New-Item -ItemType Directory -Path $recordDir -Force | Out-Null
foreach ($path in @($releaseDir, $releaseZip, $sourceZip, $hashFile, $buildLog)) {
    if (Test-Path -LiteralPath $path) { throw "Preserving existing release artifact: $path" }
}
Remove-GeneratedPath $buildRoot

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
    '--add-data', ((Join-Path $root 'user_config\default.conf') + ':user_config'),
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
    'MiniJMP v0.1.0-beta.2 Windows x64',
    "Build ID: $shortHead",
    "Base Git HEAD: $head",
    "Branch: $branch",
    "Origin/main: $originMain",
    'Tracked working-tree status: clean',
    'Application code and build inputs match Git HEAD; the corresponding source is included.',
    "Build interpreter: Python $pythonVersion",
    "Builder: PyInstaller $pyinstallerVersion (onedir, windowed, noupx)",
    "Windows: $($os.Caption), version $($os.Version), build $($os.BuildNumber), $($os.OSArchitecture)",
    "Core dependencies: $coreVersions",
    'PIReader.exe, PI SDK, PI configuration, and credentials are not included.'
) -join "`r`n"
Set-Content -LiteralPath (Join-Path $releaseDir 'BUILD-INFO.txt') -Value $buildInfo -Encoding utf8

$sourceStage = Join-Path $buildRoot 'source'
New-Item -ItemType Directory -Path $sourceStage -Force | Out-Null
# Copy tracked build inputs and the required icon licenses, excluding local configuration and caches.
$sourcePaths = @('code','help','icon','user_config/default.conf','sample_data','tests','tools','packaging',
    'docs/MENU_TRANSLATION.md','LICENSE','README.md','AGENTS.md','CODING_STANDARDS.md','CONTRIBUTING.md',
    'CHANGES','requirements.txt','setup_env.bat','start.py','win_start.bat','win_start_no_cmd_win.vbs')
$sourceFiles = @(git -C $root ls-files -- @sourcePaths) + @(
    'packaging/windows/licenses/Carbon-Icons-Apache-2.0.txt',
    'packaging/windows/licenses/Tabler-Icons-MIT.txt'
)
$requiredInputs = @($sourcePaths) + @(
    'packaging/windows/licenses/Carbon-Icons-Apache-2.0.txt',
    'packaging/windows/licenses/Tabler-Icons-MIT.txt'
)
foreach ($inputPath in $requiredInputs) {
    if (!(git -C $root ls-files -- $inputPath)) {
        throw "Required build input is not tracked by Git: $inputPath"
    }
}
foreach ($name in ($sourceFiles | Select-Object -Unique)) {
    $destination = Join-Path $sourceStage $name
    New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $root $name) -Destination $destination
}
$sourceInfo = @(
    'MiniJMP v0.1.0-beta.2 corresponding source bundle',
    "Base Git HEAD: $head",
    "Release branch: $branch",
    'This source archive contains the Git-tracked sources and build inputs used for the adjacent binary.',
    "Build ID: $shortHead",
    'Application source and build inputs match Git HEAD; required icon licenses are included.'
) -join "`r`n"
Set-Content -LiteralPath (Join-Path $sourceStage 'SOURCE-BUNDLE-INFO.txt') -Value $sourceInfo -Encoding utf8
& $python (Join-Path $root 'tools\write_third_party_notices.py') $sourceStage
if ($LASTEXITCODE -ne 0) { throw 'Generating source bundle third-party notices failed.' }
Compress-Archive -Path (Join-Path $sourceStage '*') -DestinationPath $sourceZip -CompressionLevel Optimal

$sourceHash = (Get-FileHash -LiteralPath $sourceZip -Algorithm SHA256).Hash
$sourceNotice = @(
    "Exact corresponding source is provided alongside the runtime ZIP as $sourceName.zip.",
    "Source archive SHA256: $sourceHash",
    "Base Git HEAD: $head",
    "Release branch: $branch",
    'The source archive includes the tracked build inputs used for this binary.',
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

Compress-Archive -LiteralPath $releaseDir -DestinationPath $releaseZip -CompressionLevel Optimal
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
