param(
    [switch]$SkipSmoke,
    [switch]$InternalReview,
    [string]$CertificateThumbprint = $env:MINIJMP_SIGNING_THUMBPRINT,
    [ValidateSet('CurrentUser', 'LocalMachine')]
    [string]$CertificateStore = 'CurrentUser',
    [string]$PiSdkDirectory,
    [string]$FrameworkReferenceDirectory,
    [string]$SignToolPath
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
$releaseVersion = 'V1.1'
$productVersion = 'v1.1.0'
if ($root.Length -gt 80) {
    throw 'Build path is too long. Place the repository in a local path of at most 80 characters, for example C:\src\MiniJMP.'
}

if (!(Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Project Python environment not found: $python"
}
if ($env:OS -ne 'Windows_NT') {
    throw 'Build this Windows package on Windows x64.'
}
if (!$InternalReview) {
$CertificateThumbprint = ($CertificateThumbprint -replace '\s', '').ToUpperInvariant()
if ($CertificateThumbprint -notmatch '^[0-9A-F]{40}$') {
    throw 'Provide a code-signing certificate thumbprint with -CertificateThumbprint or MINIJMP_SIGNING_THUMBPRINT.'
}
$certificate = Get-Item -LiteralPath "Cert:\$CertificateStore\My\$CertificateThumbprint" -ErrorAction SilentlyContinue
if (!$certificate -or !$certificate.HasPrivateKey) {
    throw "Code-signing certificate with private key not found in $CertificateStore/My."
}
}
if (!$PiSdkDirectory) { $PiSdkDirectory = Join-Path $root 'PIReader' }
$piSdkNames = @('OSIsoft.PISDK.dll', 'OSIsoft.PISDKCommon.dll', 'OSIsoft.PITimeServer.dll')
if (!$FrameworkReferenceDirectory) {
    $FrameworkReferenceDirectory = Join-Path ${env:ProgramFiles(x86)} 'Reference Assemblies\Microsoft\Framework\.NETFramework\v4.8'
}
$msbuild = Join-Path $env:WINDIR 'Microsoft.NET\Framework\v4.0.30319\MSBuild.exe'
if (!(Test-Path -LiteralPath $msbuild -PathType Leaf)) {
    throw 'The .NET Framework MSBuild tool was not found.'
}
$frameworkRelease = (Get-ItemProperty -Path 'HKLM:\SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full' -Name Release -ErrorAction SilentlyContinue).Release
if (!$frameworkRelease -or $frameworkRelease -lt 528040) {
    throw '.NET Framework 4.8 or newer is required to build PIReader.'
}
foreach ($sdkName in $piSdkNames) {
    if (!(Test-Path -LiteralPath (Join-Path $PiSdkDirectory $sdkName) -PathType Leaf)) {
        throw "PI SDK build reference missing: $sdkName in $PiSdkDirectory"
    }
}
foreach ($frameworkName in @('mscorlib.dll', 'System.dll', 'System.Core.dll', 'System.Web.Extensions.dll')) {
    if (!(Test-Path -LiteralPath (Join-Path $FrameworkReferenceDirectory $frameworkName) -PathType Leaf)) {
        throw ".NET Framework 4.8 reference assembly missing: $frameworkName in $FrameworkReferenceDirectory"
    }
}
$FrameworkReferenceDirectory = (Resolve-Path -LiteralPath $FrameworkReferenceDirectory).Path
if ((Split-Path -Leaf $FrameworkReferenceDirectory) -ne 'v4.8' -or
    (Split-Path -Leaf (Split-Path -Parent $FrameworkReferenceDirectory)) -ne '.NETFramework' -or
    !(Test-Path -LiteralPath (Join-Path $FrameworkReferenceDirectory 'RedistList\FrameworkList.xml') -PathType Leaf)) {
    throw 'FrameworkReferenceDirectory must be a complete .NETFramework/v4.8 reference assembly directory.'
}
$PiSdkDirectory = (Resolve-Path -LiteralPath $PiSdkDirectory).Path
$piSdkBuildInputs = foreach ($sdkName in $piSdkNames) {
    $sdkPath = Join-Path $PiSdkDirectory $sdkName
    $assemblyVersion = [Reflection.AssemblyName]::GetAssemblyName($sdkPath).Version
    $file = Get-Item -LiteralPath $sdkPath
    $fileVersion = $file.VersionInfo.FileVersion
    $sha256 = (Get-FileHash -LiteralPath $sdkPath -Algorithm SHA256).Hash
    "$sdkName (AssemblyVersion=$assemblyVersion; FileVersion=$fileVersion; SHA256=$sha256)"
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

    $tagCommit = (git -C $root rev-parse "$productVersion^{}").Trim()
    if ($LASTEXITCODE -ne 0 -or $tagCommit -ne $head) { throw 'The release tag must identify HEAD.' }

    $dirty = @(git -C $root status --porcelain --untracked-files=normal)
    if ($dirty.Count) {
        throw "Refusing to build from a dirty working tree; commit or remove the $($dirty.Count) changed entries first."
    }
}

$required = @(
    'PIReader\config.example.txt', 'PIReader\tags.example.txt', 'LICENSE',
    'PIReader\PIReader.csproj', 'PIReader\Program.cs', 'PIReader\TimeExpressionParser.cs',
    'PIReader\Properties\AssemblyInfo.cs', 'tools\sign_minijmp_executables.ps1',
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
$auditDir = Join-Path $distRoot "MiniJMP-$releaseVersion-Release"
$releaseZip = Join-Path $auditDir "MiniJMP-$releaseVersion-Windows-x64.zip"
$sourceZip = Join-Path $auditDir "MiniJMP-$releaseVersion-Source.zip"
$hashFile = Join-Path $distRoot "MiniJMP-$releaseVersion-SHA256SUMS.txt"
$recordDir = Join-Path $root 'docs\release'
$buildLog = Join-Path $recordDir "pyinstaller-build-$releaseVersion.txt"
$manifestPath = Join-Path $recordDir "build-inputs-$releaseVersion.txt"

# Never overwrite or remove earlier artifacts.
$existing = @($auditDir, $releaseDir, $releaseZip, $sourceZip, $hashFile, $buildLog, $manifestPath,
    $buildRoot) | Where-Object { Test-Path -LiteralPath $_ }
if ($existing) {
    throw ('Existing release output is preserved; review it before moving it aside for a separate build:' + $nl + ($existing -join $nl))
}
New-Item -ItemType Directory -Path $distRoot, $auditDir, $recordDir, $buildRoot -Force | Out-Null
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
    '--hidden-import', 'openpyxl', '--hidden-import', 'xlrd', '--hidden-import', 'pyarrow.parquet',
    # appdirs uses its ctypes path lookup without optional Python COM automation.
    '--exclude-module', 'win32com', '--exclude-module', 'pythoncom',
    '--add-data', ((Join-Path $root 'code\help.json') + ':.' ),
    '--add-data', ((Join-Path $root 'help') + ':help'),
    '--add-data', ((Join-Path $root 'user_config\default.conf') + ':user_config'),
    '--add-data', ((Join-Path $root 'sample_data\coatings.csv') + ':sample_data'),
    '--add-data', ((Join-Path $root 'sample_data\Gasket.xlsx') + ':sample_data'),
    '--add-data', ((Join-Path $root 'sample_data\ctrl_chart_test.dexpl') + ':sample_data'),
    '--add-data', ((Join-Path $root 'sample_data\CPK_sample.dexpl') + ':sample_data'),
    '--add-data', ((Join-Path $root 'sample_data\GRR_crossed.dexpl') + ':sample_data'),
    '--add-data', ((Join-Path $root 'sample_data\fit_sample_data.dexpl') + ':sample_data'),
    '--add-data', ((Join-Path $root 'sample_data\gasket.dexpl') + ':sample_data'),
    '--add-data', ((Join-Path $root 'sample_data\car_poll.dexpl') + ':sample_data'),
    '--add-data', ((Join-Path $root 'sample_data\correlation.dexpl') + ':sample_data'),
    '--add-data', ((Join-Path $root 'sample_data\Nested_GRR.dexpl') + ':sample_data'),
    '--add-data', ((Join-Path $root 'sample_data\dists.dexpl') + ':sample_data'),
    $entry
)

$envReport | Set-Content -LiteralPath $buildLog -Encoding utf8
Write-Output 'Building PIReader from project source...'
$piBuild = Join-Path $buildRoot 'pireader'
New-Item -ItemType Directory -Path $piBuild | Out-Null
$compiledReader = Join-Path $piBuild 'PIReader.exe'
$frameworkRoot = (Split-Path -Parent (Split-Path -Parent $FrameworkReferenceDirectory)) + '/'
$piIntermediate = (Join-Path $buildRoot 'pireader-obj') + '/'
# A forward trailing slash also survives Windows PowerShell 5.1 argument quoting.
$readerArgs = @(
    (Join-Path $root 'PIReader\PIReader.csproj'),
    '/nologo', '/t:Build', '/p:Configuration=Release', '/p:Platform=AnyCPU',
    "/p:TargetFrameworkRootPath=$frameworkRoot", "/p:ReferencePath=$PiSdkDirectory",
    "/p:OutputPath=$piBuild/", "/p:IntermediateOutputPath=$piIntermediate", '/verbosity:minimal'
)
& $msbuild @readerArgs *>> $buildLog
if ($LASTEXITCODE -ne 0 -or !(Test-Path -LiteralPath $compiledReader -PathType Leaf)) {
    throw "Compiling PIReader from source failed; see $buildLog"
}
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
$mainInfo = [System.Diagnostics.FileVersionInfo]::GetVersionInfo((Join-Path $rawApp 'MiniJMP.exe'))
$readerInfo = [System.Diagnostics.FileVersionInfo]::GetVersionInfo($compiledReader)
if ($readerInfo.ProductName -ne 'MiniJMP PI Reader' -or $readerInfo.FileVersion -ne $mainInfo.FileVersion) {
    throw 'PIReader product name or file version does not match the MiniJMP build.'
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
Copy-Item -LiteralPath $compiledReader -Destination (Join-Path $piTarget 'PIReader.exe')
Copy-Item -LiteralPath (Join-Path $piSource 'config.example.txt') -Destination (Join-Path $piTarget 'config.txt')
Copy-Item -LiteralPath (Join-Path $piSource 'tags.example.txt') -Destination (Join-Path $piTarget 'tags.txt')
foreach ($sdkName in $piSdkNames) {
    $sdkInput = Join-Path $PiSdkDirectory $sdkName
    $sdkOutput = Join-Path $piTarget $sdkName
    Copy-Item -LiteralPath $sdkInput -Destination $sdkOutput
    if ((Get-FileHash -LiteralPath $sdkInput -Algorithm SHA256).Hash -ne
        (Get-FileHash -LiteralPath $sdkOutput -Algorithm SHA256).Hash) {
        throw "PI SDK copy hash mismatch: $sdkName"
    }
}
$sdkComponents = @(foreach ($sdkName in $piSdkNames) {
    $sdkPath = Join-Path $piTarget $sdkName
    [pscustomobject][ordered]@{
        File = $sdkName
        AssemblyVersion = [Reflection.AssemblyName]::GetAssemblyName($sdkPath).Version.ToString()
        FileVersion = (Get-Item -LiteralPath $sdkPath).VersionInfo.FileVersion
        SHA256 = (Get-FileHash -LiteralPath $sdkPath -Algorithm SHA256).Hash
        SourceCategory = 'Supplied proprietary OSIsoft/AVEVA PI SDK; compilation reference and bundled runtime component'
    }
})
$sdkComponents | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $releaseDir 'SDK-COMPONENTS.json') -Encoding utf8
$buildMode = if ($InternalReview) { 'InternalReview (not approved for deployment)' } else { 'Formal trusted signature' }
if ($InternalReview) {
    $signatureInfo = @('代码签名状态：暂未实施，企业审批及替代控制说明由申请人另行提供。')
    foreach ($exe in @((Join-Path $releaseDir 'MiniJMP.exe'), (Join-Path $piTarget 'PIReader.exe'))) {
        if ((Get-AuthenticodeSignature -FilePath $exe).Status -ne 'NotSigned') {
            throw "Internal review expects an unsigned source-built executable: $exe"
        }
    }
} else {
$signArgs = @{
    Thumbprint = $CertificateThumbprint
    StoreLocation = $CertificateStore
    MiniJMPExe = (Join-Path $releaseDir 'MiniJMP.exe')
    PIReaderExe = (Join-Path $piTarget 'PIReader.exe')
}
if ($SignToolPath) { $signArgs.SignTool = $SignToolPath }
$signatureInfo = @(& (Join-Path $root 'tools\sign_minijmp_executables.ps1') @signArgs)
$signatureInfo | ForEach-Object { Write-Output $_ }
if ($signatureInfo.Count -ne 2 -or @($signatureInfo | Where-Object {
    !$_.Trusted -or !$_.IntegrityVerified -or $_.Status -ne 'Valid'
}).Count) {
    throw 'Formal release requires valid, trusted Authenticode signatures on both executables.'
}
}
& $python (Join-Path $root 'tools\write_third_party_notices.py') $releaseDir
if ($LASTEXITCODE -ne 0) { throw 'Generating third-party notices failed.' }

$os = Get-CimInstance Win32_OperatingSystem
$pythonVersion = (@(& $python -c "import sys; print('.'.join(map(str, sys.version_info[:3])))") -join '').Trim()
$pyinstallerVersion = (@(& $python -m PyInstaller --version) -join '').Trim()
$coreVersions = & $python -c "import importlib.metadata as m; names=['numpy','scipy','pandas','pyarrow','matplotlib','seaborn','statsmodels','openpyxl','xlrd','Pillow','prettytable']; print('; '.join(n+' '+m.version(n) for n in names))"
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
    "Build mode: $buildMode",
    'MiniJMP V1.1 Windows 发布包随附三个 PI SDK 相关组件，用于支持 PI 数据访问。PI 数据导入功能须在已取得相应授权、安装并正确配置 PI SDK/PIPC 运行环境，且具有 PI Server 访问权限的企业办公终端上使用。随包组件无法构成完整的 PI System 运行环境，也不代表授予额外的软件使用或再分发许可。',
    "Base Git HEAD: $head",
    "Git Tag: $productVersion",
    "Build time: $([DateTimeOffset]::Now.ToString('o'))",
    "Branch: $branch",
    "Origin/main: $originMain",
    "Working tree: $treeState",
    "Python: $pythonVersion",
    "PyInstaller: $pyinstallerVersion (onedir, windowed, noupx, _internal)",
    "Windows: $($os.Caption), version $($os.Version), build $($os.BuildNumber), $($os.OSArchitecture)",
    "Core dependencies: $coreVersions",
    ("PI SDK build references and bundled proprietary runtime files: " + ($piSdkBuildInputs -join '; ')),
    'PIReader: built from project source for .NET Framework 4.8, x86; three proprietary OSIsoft DLLs are distributed in PIReader/.',
    ("Authenticode: " + ($signatureInfo -join '; ')),
    'The DLLs do not include or register the full PI SDK/PIPC runtime. Target-machine runtime, licensing and PI Server connectivity were not verified.',
    'Defender, TsdEncrypt/DLP and non-admin execution on office machines were not verified by this build.'
) -join $nl
Set-Content -LiteralPath (Join-Path $releaseDir 'BUILD-INFO.txt') -Value $buildInfo -Encoding utf8
@(
    "Corresponding source archive: MiniJMP-$releaseVersion-Source.zip",
    "Base Git HEAD: $head",
    'Repository: https://github.com/summeredge/Minijmp',
    'The source ZIP contains the corresponding source files and build scripts; it omits .git, OSIsoft PI SDK assemblies and real PI connection settings.',
    'Build prerequisites for PIReader are listed in PACKAGING.md and SOURCE-BUNDLE-INFO.txt.'
) -join $nl | Set-Content -LiteralPath (Join-Path $releaseDir 'SOURCE-CODE.txt') -Encoding utf8

& $python (Join-Path $root 'tools\write_release_sbom.py') $releaseDir $auditDir (Join-Path $workPath 'MiniJMP')
if ($LASTEXITCODE -ne 0) { throw 'SBOM generation failed.' }

# Stage the sources actually used from disk, in TEMP so DLP-synced folders
# cannot rewrite them mid-archive.
foreach ($file in Get-ChildItem -LiteralPath $releaseDir -File -Recurse) {
    if ($file.FullName.Substring($releaseDir.Length).Length + 80 -gt 240) {
        throw "Runtime entry exceeds the supported installation path budget: $($file.FullName)"
    }
}
$sourceStage = Join-Path $env:TEMP ('MiniJMP-source-' + [guid]::NewGuid().ToString('N'))
try {
    New-Item -ItemType Directory -Path $sourceStage -Force | Out-Null
    $staged = & $python $makeZip 'stage-source' $root $sourceStage
    if ($LASTEXITCODE -ne 0) { throw 'Staging corresponding sources failed.' }
    Write-Output $staged

    $sourceInfo = @(
        "MiniJMP $productVersion corresponding source",
        "Release name: $releaseVersion",
    "Build mode: $buildMode",
    'MiniJMP V1.1 Windows 发布包随附三个 PI SDK 相关组件，用于支持 PI 数据访问。PI 数据导入功能须在已取得相应授权、安装并正确配置 PI SDK/PIPC 运行环境，且具有 PI Server 访问权限的企业办公终端上使用。随包组件无法构成完整的 PI System 运行环境，也不代表授予额外的软件使用或再分发许可。',
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
1..4 | ForEach-Object { Start-Sleep -Seconds 30 }
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
$piRelative = "MiniJMP-$releaseVersion/PIReader/PIReader.exe"
$piInspect = @(& $python $makeZip 'inspect' $releaseZip '--entry' $piRelative)
if ($LASTEXITCODE -ne 0) { throw "PIReader archive entry failed CRC or entry checks: $piInspect" }
$zipPiHash = @($piInspect | Where-Object { $_ -like 'ENTRY-SHA256=*' })[0] -replace '^ENTRY-SHA256=', ''
$piLine = @(& $python $makeZip 'rehash' (Join-Path $piTarget 'PIReader.exe') '--interval' '5' '--attempts' '2')
if ($LASTEXITCODE -ne 0) { throw "Hashing PIReader.exe failed: $piLine" }
$piHash = ($piLine -join '').Trim() -replace '^SHA256=', ''
if ($zipPiHash -ne $piHash) {
    throw "The PIReader inside the archive differs from the built EXE ($zipPiHash vs $piHash)."
}
$hashes = @(
    "$exeHash  $exeRelative",
    "$piHash  $piRelative",
    "$($digests[$releaseZip])  MiniJMP-$releaseVersion-Windows-x64.zip",
    "$($digests[$sourceZip])  MiniJMP-$releaseVersion-Source.zip"
) -join $nl
Set-Content -LiteralPath $hashFile -Value $hashes -Encoding ascii

Write-Output 'Re-verifying after SHA256SUMS was written (90s window)...'
1..3 | ForEach-Object { Start-Sleep -Seconds 30 }
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
    $unzipRoot = Join-Path $env:TEMP ('MJ-' + [guid]::NewGuid().ToString('N').Substring(0, 8))
    try {
        & $python -m zipfile -e $releaseZip $unzipRoot
        if ($LASTEXITCODE -ne 0) { throw 'Extracting the runtime archive failed.' }
        & $python $smoke (Join-Path $unzipRoot "MiniJMP-$releaseVersion\MiniJMP.exe") 90
        if ($LASTEXITCODE -ne 0) { throw 'Smoke launch of the unzipped build failed.' }
    } finally {
        if (Test-Path -LiteralPath $unzipRoot) { Remove-Item -LiteralPath $unzipRoot -Recurse -Force }
    }
}

Get-Item -LiteralPath $releaseZip, $sourceZip, (Join-Path $releaseDir 'MiniJMP.exe'), (Join-Path $piTarget 'PIReader.exe') |
    Select-Object FullName, Length
Get-Content -LiteralPath $hashFile
Write-Output "Build log: $buildLog"
Write-Output "Runtime manifest: $manifestPath"

& $python (Join-Path $root 'tools\release_metadata.py') '--finalize' $releaseDir $auditDir
if ($LASTEXITCODE -ne 0) { throw 'Review package finalization failed.' }
