param(
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path,
    [switch]$GitOnly,
    [switch]$InternalReview,
    [string]$CertificateThumbprint = $env:MINIJMP_SIGNING_THUMBPRINT,
    [ValidateSet('CurrentUser', 'LocalMachine')]
    [string]$CertificateStore = 'CurrentUser',
    [string]$PiSdkDirectory,
    [string]$FrameworkReferenceDirectory,
    [string]$SignToolPath
)

# Read-only Windows release precheck: never cleans, builds, installs, or commits.

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path -LiteralPath $RepoRoot).Path
$blocked = 0
$warnings = 0
$sourceBundle = Test-Path -LiteralPath (Join-Path $root 'SOURCE-BUNDLE-INFO.txt') -PathType Leaf

function Add-Result([string]$Level, [string]$Message) {
    Write-Output ("{0}: {1}" -f $Level, $Message)
    if ($Level -eq 'BLOCKED') { $script:blocked++ }
    if ($Level -eq 'WARNING') { $script:warnings++ }
}

function Invoke-Git([string[]]$Arguments) {
    $output = & git -C $root @Arguments 2>$null
    [pscustomobject]@{ Ok = ($LASTEXITCODE -eq 0); Lines = @($output) }
}

$inside = $null
if ($sourceBundle -and !(Test-Path -LiteralPath (Join-Path $root '.git'))) {
    Add-Result 'PASS' '识别到源码包；该包不含 .git，跳过分支与 origin/main 检查。'
} elseif (!(Get-Command git -ErrorAction SilentlyContinue)) {
    Add-Result 'BLOCKED' '未找到 git 命令，无法核对工作区与发布基准。'
} else {
    $inside = Invoke-Git @('rev-parse', '--is-inside-work-tree')
}

if ($inside -and $inside.Ok -and $inside.Lines -contains 'true') {
    $branch = (Invoke-Git @('branch', '--show-current')).Lines -join ''
    if ($branch -ne 'main') { Add-Result 'BLOCKED' "发布分支必须是 main，当前为 '$branch'。" }
    else { Add-Result 'PASS' '发布分支为 main。' }

    $dirty = (Invoke-Git @('status', '--porcelain', '--untracked-files=normal')).Lines
    if ($dirty.Count) {
        Add-Result 'BLOCKED' ("Git 工作区有 {0} 项未提交或未跟踪变更；发布包必须与冻结 Commit 完全一致。" -f $dirty.Count)
        $dirty | Select-Object -First 10 | ForEach-Object { Add-Result 'BLOCKED' "工作区变更：$_" }
    } else {
        Add-Result 'PASS' 'Git 工作区干净，无已暂存、未暂存或未跟踪变更。'
    }

    $head = (Invoke-Git @('rev-parse', 'HEAD')).Lines -join ''
    $origin = Invoke-Git @('rev-parse', 'origin/main')
    if (!$origin.Ok) { Add-Result 'BLOCKED' 'origin/main 不可用，请先 git fetch origin。' }
    else {
        $ancestor = Invoke-Git @('merge-base', '--is-ancestor', 'origin/main', 'HEAD')
        if (!$ancestor.Ok) { Add-Result 'BLOCKED' "HEAD $head 不是 origin/main $($origin.Lines[0]) 的快进后继；分支存在分叉或远端领先。" }
        else { Add-Result 'PASS' "origin/main $($origin.Lines[0]) 是 HEAD $head 的祖先；允许从本地冻结 Commit 构建。" }
    }
} elseif ($inside) {
    Add-Result 'BLOCKED' "不是 Git 工作区：$root"
}

if (!$GitOnly) {
    $python = Join-Path $root '.venv\Scripts\python.exe'
    if (!(Test-Path -LiteralPath $python -PathType Leaf)) {
        Add-Result 'BLOCKED' "项目 Python 环境缺失：$python（需要 Windows x64、Python >= 3.11）"
    } else {
        # Python >= 3.11 x64, dependency drift and PyInstaller are judged by
        # numeric sys.version_info and metadata, never by string comparison.
        & $python (Join-Path $root 'tools\release_env.py') 2>&1 | ForEach-Object {
            $text = "$_"
            if ($text -match '^(PASS|WARNING|BLOCKED): (.*)$') {
                Add-Result $Matches[1] $Matches[2]
            } elseif ($text.Trim()) {
                Add-Result 'BLOCKED' "环境检查失败：$text"
            }
        }

        & $python (Join-Path $root 'tools\release_metadata.py') 2>&1 | ForEach-Object {
            $text = "$_"
            if ($text -match '^(PASS|WARNING|BLOCKED): (.*)$') {
                Add-Result $Matches[1] $Matches[2]
            } elseif ($text.Trim()) {
                Add-Result 'BLOCKED' "版本检查失败：$text"
            }
        }
    }

    $runtimeInputs = @(
        'packaging/windows_entrypoint.py', 'packaging/windows/requirements-py311.lock',
        'packaging/windows/requirements-py311-hashed.lock',
        'packaging/windows/version_info.txt', 'packaging/windows/USAGE.txt',
        'packaging/windows/PI-SDK-NOTICE.txt',
        'packaging/windows/licenses/Carbon-Icons-Apache-2.0.txt',
        'packaging/windows/licenses/Tabler-Icons-MIT.txt',
        'icon/icon_big.ico', 'code/help.json', 'help', 'user_config/default.conf',
        'sample_data/coatings.csv', 'sample_data/Gasket.xlsx', 'sample_data/ctrl_chart_test.dexpl',
        'sample_data/CPK_sample.dexpl', 'sample_data/GRR_crossed.dexpl', 'sample_data/fit_sample_data.dexpl',
        'sample_data/gasket.dexpl', 'sample_data/car_poll.dexpl', 'sample_data/correlation.dexpl',
        'sample_data/Nested_GRR.dexpl', 'sample_data/dists.dexpl',
        'LICENSE', 'tools/build_windows_release.ps1', 'tools/check_windows_release_ready.ps1',
        'tools/make_zip.py', 'tools/smoke_launch.py', 'tools/release_env.py',
        'tools/sign_minijmp_executables.ps1',
        'tools/release_metadata.py', 'tools/write_third_party_notices.py', 'tools/write_release_sbom.py',
        'docs/release/VERSION-INFO.md', 'docs/release/INSTALL-USAGE.md',
        'docs/release/SOURCE-PROVENANCE.md', 'docs/release/SOURCE-PROVENANCE.csv',
        'packaging/windows/licenses/BlakerCI-DESCRIPTION.txt', 'packaging/windows/licenses/Hmisc-DESCRIPTION.txt'
    )
    $missing = @($runtimeInputs | Where-Object { !(Test-Path -LiteralPath (Join-Path $root $_)) })
    if ($missing) { $missing | ForEach-Object { Add-Result 'BLOCKED' "缺少构建输入：$_" } }
    else { Add-Result 'PASS' '入口、运行资源、许可证与发布脚本均已存在。' }

    # The release generates clean runtime files from these source templates.
    $piInputs = @('PIReader/config.example.txt', 'PIReader/tags.example.txt',
        'PIReader/PIReader.csproj', 'PIReader/Program.cs', 'PIReader/TimeExpressionParser.cs',
        'PIReader/Properties/AssemblyInfo.cs')
    foreach ($item in $piInputs) {
        if (!(Test-Path -LiteralPath (Join-Path $root $item))) { Add-Result 'BLOCKED' "PI template missing: $item" }
    }
    if (!$PiSdkDirectory) { $PiSdkDirectory = Join-Path $root 'PIReader' }
    foreach ($name in @('OSIsoft.PISDK.dll', 'OSIsoft.PISDKCommon.dll', 'OSIsoft.PITimeServer.dll')) {
        if (!(Test-Path -LiteralPath (Join-Path $PiSdkDirectory $name) -PathType Leaf)) {
            Add-Result 'BLOCKED' "缺少 PI SDK 编译引用：$name（$PiSdkDirectory）"
        }
    }
    $msbuild = Join-Path $env:WINDIR 'Microsoft.NET\Framework\v4.0.30319\MSBuild.exe'
    if (!(Test-Path -LiteralPath $msbuild -PathType Leaf)) { Add-Result 'BLOCKED' '缺少 .NET Framework MSBuild 工具。' }
    else { Add-Result 'PASS' 'PIReader 将从源码编译；三个 PI SDK DLL 随运行包提供，源码包排除。' }
    $frameworkRelease = (Get-ItemProperty -Path 'HKLM:\SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full' -Name Release -ErrorAction SilentlyContinue).Release
    if (!$frameworkRelease -or $frameworkRelease -lt 528040) { Add-Result 'BLOCKED' '编译 PIReader 需要 .NET Framework 4.8 或更高版本。' }
    if (!$FrameworkReferenceDirectory) {
        $FrameworkReferenceDirectory = Join-Path ${env:ProgramFiles(x86)} 'Reference Assemblies\Microsoft\Framework\.NETFramework\v4.8'
    }
    foreach ($name in @('mscorlib.dll', 'System.dll', 'System.Core.dll', 'System.Web.Extensions.dll')) {
        if (!(Test-Path -LiteralPath (Join-Path $FrameworkReferenceDirectory $name) -PathType Leaf)) {
            Add-Result 'BLOCKED' "缺少 .NET Framework 4.8 参考程序集：$name（$FrameworkReferenceDirectory）"
        }
    }
    if (!(Test-Path -LiteralPath (Join-Path $FrameworkReferenceDirectory 'RedistList\FrameworkList.xml') -PathType Leaf)) {
        Add-Result 'BLOCKED' '缺少 .NET Framework 4.8 参考程序集清单。'
    }

    if ($InternalReview) {
        Add-Result 'WARNING' '内部送审模式：代码签名状态：暂未实施，企业审批及替代控制说明由申请人另行提供。'
    } else {
    $thumbprint = ($CertificateThumbprint -replace '\s', '').ToUpperInvariant()
    if ($thumbprint -notmatch '^[0-9A-F]{40}$') {
        Add-Result 'BLOCKED' '需提供代码签名证书指纹：-CertificateThumbprint 或 MINIJMP_SIGNING_THUMBPRINT。'
    } else {
        $certificate = Get-Item -LiteralPath "Cert:\$CertificateStore\My\$thumbprint" -ErrorAction SilentlyContinue
        if (!$certificate -or !$certificate.HasPrivateKey) {
            Add-Result 'BLOCKED' "在 $CertificateStore/My 中找不到包含私钥的指定证书。"
        } else {
            Add-Result 'PASS' "找到指定签名证书；信任状态须在签名后核验：$thumbprint"
        }
    }
    if (!$SignToolPath) {
        $signToolCommand = Get-Command signtool.exe -ErrorAction SilentlyContinue
        if ($signToolCommand) { $SignToolPath = $signToolCommand.Source }
        else {
            $kitRoot = Join-Path ${env:ProgramFiles(x86)} 'Windows Kits\10\bin'
            $kitDirs = @(Get-ChildItem -LiteralPath $kitRoot -Directory -ErrorAction SilentlyContinue |
                Where-Object { $_.Name -match '^\d+(\.\d+)+$' } |
                Sort-Object { [version]$_.Name } -Descending)
            foreach ($directory in $kitDirs) {
                $candidate = Join-Path $directory.FullName 'x64\signtool.exe'
                if (Test-Path -LiteralPath $candidate -PathType Leaf) { $SignToolPath = $candidate; break }
            }
        }
    }
    if (!$SignToolPath -or !(Test-Path -LiteralPath $SignToolPath -PathType Leaf)) {
        Add-Result 'BLOCKED' '未找到 Windows SignTool；请安装 Windows SDK 或指定 -SignToolPath。'
    } else {
        Add-Result 'PASS' "找到 Windows SignTool：$SignToolPath"
    }

    }

    # The source bundle is built from disk, so untracked sources are included by
    # design. Tracked build inputs are listed only to document ownership.
    if ($inside -and $inside.Ok) {
        $tracked = @(Invoke-Git @('ls-files', '--', 'tools/make_zip.py', 'tools/smoke_launch.py')).Lines
        if ($tracked.Count -lt 2) {
            Add-Result 'WARNING' 'tools/make_zip.py 或 tools/smoke_launch.py 尚未纳入 Git；源码包仍按磁盘内容收录。'
        } else {
            Add-Result 'PASS' '压缩与冒烟工具已纳入版本管理。'
        }
    }
}

Write-Output ''
if ($blocked) {
    Write-Output "RESULT: BLOCKED（$blocked 项阻断，$warnings 项警告）"
    exit 1
}
if ($warnings) { Write-Output "RESULT: PASS（$warnings 项警告）" } else { Write-Output 'RESULT: PASS' }
exit 0
