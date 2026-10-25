param(
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path,
    [switch]$GitOnly
)

# Read-only Windows release precheck: never cleans, builds, installs, or commits.

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path -LiteralPath $RepoRoot).Path
$blocked = 0
$warnings = 0

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
if (!(Get-Command git -ErrorAction SilentlyContinue)) {
    Add-Result 'BLOCKED' '未找到 git 命令，无法核对工作区与发布基准。'
} else {
    $inside = Invoke-Git @('rev-parse', '--is-inside-work-tree')
}

if ($inside -and $inside.Ok -and $inside.Lines -contains 'true') {
    $branch = (Invoke-Git @('branch', '--show-current')).Lines -join ''
    if ($branch -ne 'main') { Add-Result 'BLOCKED' "发布分支必须是 main，当前为 '$branch'。" }
    else { Add-Result 'PASS' '发布分支为 main。' }

    # Uncommitted work is allowed for office distribution; it is recorded, not discarded.
    $dirty = (Invoke-Git @('status', '--porcelain', '--untracked-files=normal')).Lines
    if ($dirty.Count) {
        Add-Result 'WARNING' ("Git 工作区有 {0} 项未提交或未跟踪变更；构建取磁盘当前内容并在 BUILD-INFO 记录该状态。" -f $dirty.Count)
        $dirty | Select-Object -First 10 | ForEach-Object { Add-Result 'WARNING' "工作区变更：$_" }
    } else {
        Add-Result 'PASS' 'Git 工作区干净，无已暂存、未暂存或未跟踪变更。'
    }

    $head = (Invoke-Git @('rev-parse', 'HEAD')).Lines -join ''
    $origin = Invoke-Git @('rev-parse', 'origin/main')
    if (!$origin.Ok) { Add-Result 'BLOCKED' 'origin/main 不可用，请先 git fetch origin。' }
    elseif ($origin.Lines[0] -ne $head) {
        Add-Result 'BLOCKED' "HEAD $head 与发布基准 origin/main $($origin.Lines[0]) 不一致。"
    } else { Add-Result 'PASS' "HEAD 与 origin/main 一致：$head" }
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
        'packaging/windows/version_info.txt', 'packaging/windows/USAGE.txt',
        'packaging/windows/licenses/Carbon-Icons-Apache-2.0.txt',
        'packaging/windows/licenses/Tabler-Icons-MIT.txt',
        'icon/icon_big.ico', 'code/help.json', 'help', 'user_config/default.conf',
        'sample_data/coatings.csv', 'sample_data/Gasket.xlsx', 'sample_data/ctrl_chart_test.pickle',
        'sample_data/CPK_sample.pickle', 'sample_data/GRR_crossed.pickle', 'sample_data/fit_sample_data.pickle',
        'LICENSE', 'tools/build_windows_release.ps1', 'tools/check_windows_release_ready.ps1',
        'tools/make_zip.py', 'tools/smoke_launch.py', 'tools/release_env.py',
        'tools/release_metadata.py', 'tools/write_third_party_notices.py'
    )
    $missing = @($runtimeInputs | Where-Object { !(Test-Path -LiteralPath (Join-Path $root $_)) })
    if ($missing) { $missing | ForEach-Object { Add-Result 'BLOCKED' "缺少构建输入：$_" } }
    else { Add-Result 'PASS' '入口、运行资源、许可证与发布脚本均已存在。' }

    # PIReader ships beside the EXE; config.txt ships verbatim per the office decision.
    foreach ($item in @('PIReader/PIReader.exe', 'PIReader/config.txt')) {
        if (!(Test-Path -LiteralPath (Join-Path $root $item))) {
            Add-Result 'BLOCKED' "PI 随包文件缺失：$item"
        }
    }
    Add-Result 'PASS' 'PIReader 随包文件存在；config.txt 按原样发布。'

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
