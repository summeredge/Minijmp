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

    $dirty = (Invoke-Git @('status', '--porcelain', '--untracked-files=normal')).Lines
    if ($dirty.Count) {
        Add-Result 'BLOCKED' ("Git 工作区尚未整理，正式构建前需要完成版本归档（{0} 项未提交或未跟踪变更）。" -f $dirty.Count)
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
        Add-Result 'BLOCKED' "项目 Python 3.11 环境缺失：$python"
    } else {
        $pythonVersion = (& $python -c "import sys; print('.'.join(map(str, sys.version_info[:3])))" 2>$null)
        if ($pythonVersion -ne '3.11.9') { Add-Result 'BLOCKED' "构建解释器应为 Python 3.11.9，实际 $pythonVersion。" }
        else { Add-Result 'PASS' '构建解释器为 Python 3.11.9。' }

        $bits = (& $python -c "import struct; print(struct.calcsize('P') * 8)" 2>$null)
        if ($bits -ne '64') { Add-Result 'BLOCKED' "构建解释器应为 64 位，实际 $bits 位。" }
        else { Add-Result 'PASS' '构建解释器为 64 位。' }

        $lock = Join-Path $root 'packaging\windows\requirements-py311.lock'
        if (!(Test-Path -LiteralPath $lock -PathType Leaf)) {
            Add-Result 'BLOCKED' '缺少 packaging\windows\requirements-py311.lock。'
        } else {
            $pins = @"
import importlib.metadata as m, pathlib, sys
bad = []
for name, version in [line.strip().split('==') for line in pathlib.Path(sys.argv[1]).read_text().splitlines() if '==' in line]:
    try:
        have = m.version(name)
    except m.PackageNotFoundError:
        have = 'missing'
    if have != version:
        bad.append(f'{name}=={version} (have {have})')
print(', '.join(bad))
"@
            $mismatch = (& $python -c $pins $lock 2>$null)
            if ($LASTEXITCODE -ne 0) { Add-Result 'BLOCKED' '无法核对锁定依赖版本。' }
            elseif ($mismatch) { Add-Result 'BLOCKED' "已安装依赖与锁定文件不一致：$mismatch" }
            else { Add-Result 'PASS' '已安装依赖与 requirements-py311.lock 一致。' }
        }

        & $python -m pip check 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) { Add-Result 'BLOCKED' '构建环境存在依赖冲突（python -m pip check 未通过）。' }
        else { Add-Result 'PASS' 'python -m pip check 通过。' }

        $pyinstallerVersion = (& $python -m PyInstaller --version 2>$null)
        if ($pyinstallerVersion -ne '6.22.3') { Add-Result 'BLOCKED' "PyInstaller 应为 6.22.3，实际 $pyinstallerVersion。" }
        else { Add-Result 'PASS' 'PyInstaller 版本为 6.22.3。' }
    }

    $runtimeInputs = @(
        'packaging/windows_entrypoint.py', 'packaging/windows/requirements-py311.lock',
        'packaging/windows/version_info.txt', 'packaging/windows/USAGE.txt',
        'packaging/windows/licenses/Carbon-Icons-Apache-2.0.txt',
        'packaging/windows/licenses/Tabler-Icons-MIT.txt',
        'icon/icon_big.ico', 'code/help.json', 'help', 'user_config/default.conf',
        'sample_data/coatings.csv', 'sample_data/Gasket.xlsx', 'sample_data/ctrl_chart_test.pickle',
        'sample_data/CPK_sample.pickle', 'sample_data/GRR_crossed.pickle', 'sample_data/fit_sample_data.pickle',
        'LICENSE', 'tools/build_windows_release.ps1', 'tools/write_third_party_notices.py'
    )
    $missing = @($runtimeInputs | Where-Object { !(Test-Path -LiteralPath (Join-Path $root $_)) })
    if ($missing) { $missing | ForEach-Object { Add-Result 'BLOCKED' "缺少构建输入：$_" } }
    else { Add-Result 'PASS' '入口、运行资源、许可证与发布脚本均已存在。' }

    # shortcut: source list mirrors $sourcePaths in build_windows_release.ps1, update both together.
    $sourcePaths = @('code', 'help', 'icon', 'user_config/default.conf', 'sample_data', 'tests', 'tools',
        'packaging', 'docs/MENU_TRANSLATION.md', 'LICENSE', 'README.md', 'AGENTS.md', 'CODING_STANDARDS.md',
        'CONTRIBUTING.md', 'CHANGES', 'requirements.txt', 'setup_env.bat', 'start.py', 'win_start.bat',
        'win_start_no_cmd_win.vbs', 'packaging/windows/licenses/Carbon-Icons-Apache-2.0.txt',
        'packaging/windows/licenses/Tabler-Icons-MIT.txt')
    if ($inside -and $inside.Ok) {
        $untracked = @($sourcePaths | Where-Object { !((Invoke-Git @('ls-files', '--', $_)).Lines) })
        if ($untracked) { $untracked | ForEach-Object { Add-Result 'BLOCKED' "发布清单输入未纳入 Git：$_" } }
        else { Add-Result 'PASS' '发布清单输入均已纳入版本管理。' }
    }

    $buildScript = Get-Content -LiteralPath (Join-Path $root 'tools\build_windows_release.ps1') -Raw
    $match = [regex]::Match($buildScript, '\$version = ''([^'']+)''')
    if (!$match.Success) {
        Add-Result 'WARNING' '无法从发布脚本读取版本号，跳过版本一致性核对。'
    } else {
        $version = $match.Groups[1].Value
        $versionInfo = Get-Content -LiteralPath (Join-Path $root 'packaging\windows\version_info.txt') -Raw
        $usage = Get-Content -LiteralPath (Join-Path $root 'packaging\windows\USAGE.txt') -Raw
        if (!$versionInfo.Contains($version)) { Add-Result 'BLOCKED' "version_info.txt 未声明版本 $version。" }
        elseif (!$usage.Contains($version)) { Add-Result 'BLOCKED' "USAGE.txt 未声明版本 $version。" }
        else { Add-Result 'PASS' "版本 $version 在发布脚本、version_info.txt 与 USAGE.txt 中一致。" }
    }
}

Write-Output ''
if ($blocked) {
    Write-Output "RESULT: BLOCKED（$blocked 项阻断，$warnings 项警告）"
    exit 1
}
if ($warnings) { Write-Output "RESULT: PASS（$warnings 项警告）" } else { Write-Output 'RESULT: PASS' }
exit 0
