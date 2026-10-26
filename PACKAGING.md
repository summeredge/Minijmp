# MiniJMP Windows 分发包打包指令

唯一构建入口是 **tools/build_windows_release.ps1**，本文是复制即用的操作卡。
所有命令都在仓库根目录执行；脚本按自身位置解析项目根，不依赖盘符。

本轮只同步工具链与文档：未执行 PyInstaller，未生成 EXE 或 ZIP。

---

## 前置条件

- Windows x64，Python **>= 3.11**。3.11 必须与锁定环境一致；3.12 及更新版本只把锁文件差异写入 BUILD-INFO.txt。
- 正式 pandas 版本为 **3.0.6**；Python 3.11 发布环境须匹配完整锁文件。
- 项目解释器：**.venv\Scripts\python.exe**（64 位）。
- PyInstaller 6.22.3。
- 分支 main 且 HEAD == origin/main；工作区可以脏，构建取磁盘内容并记录在 BUILD-INFO.txt。
- **PIReader\PIReader.exe** 与 **PIReader\config.txt** 必须存在。
- **packaging\windows\requirements-py311.lock** 保留原名，它是 Python 3.11 的产物。

只读预检查（不构建、不删除、不安装）：

    powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\check_windows_release_ready.ps1

退出码 0 为 PASS，1 为 BLOCKED。未提交文件只报 WARNING 与数量，不阻断办公环境分发。

---

## A. 清场（重建前必做，需人工执行）

构建脚本发现 dist\MiniJMP-V*、build\windows-pkg 或上一次的日志与清单仍在时，
直接报错 Existing build output must be removed before rebuilding，不会自己删。
PowerShell 一次批量删除上千文件会被企业沙箱拦截，所以清场交给 Python：

    $python = (Resolve-Path ".venv\Scripts\python.exe").Path
    & $python -c "import glob, os, shutil
    targets = glob.glob('dist/MiniJMP-V*') + glob.glob('build/windows-pkg') + glob.glob('docs/release/pyinstaller-build-V*.txt') + glob.glob('docs/release/build-inputs-V*.txt')
    for t in targets:
        shutil.rmtree(t) if os.path.isdir(t) else os.remove(t)
        print('cleared', t)
    print('cleared:', len(targets))"

首次构建（dist 为空）可跳过。

---

## B. 构建

    powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\build_windows_release.ps1

仅排错时可加 -SkipSmoke 跳过 EXE 冒烟；正式产物必须跑冒烟。

耗时约 12 分钟：PyInstaller 约 4.5 分钟，两个 ZIP 约 1 分钟，末尾等待透明加密沉降
约 2.5 分钟，写出 SHA256SUMS 后再复验 90 秒。

PyInstaller 的普通 INFO 走 stderr，脚本已把它包在 Continue 作用域内，
只看退出码与日志末尾的 ERROR，不会把进度信息当失败。

产物（均在 dist\）：

    MiniJMP-V0.1-beta3.zip                        运行包（整目录，解压即用）
    MiniJMP-V0.1-beta3-source.zip                 对应源码包（GPLv3 要求）
    MiniJMP-V0.1-beta3-SHA256SUMS.txt             三个产物的校验值
    MiniJMP-V0.1-beta3\                           未压缩运行目录
    docs\release\pyinstaller-build-V0.1-beta3.txt 构建日志
    docs\release\build-inputs-V0.1-beta3.txt      运行包输入清单与摘要

运行包根目录：MiniJMP.exe、_internal\、PIReader\、README.txt、LICENSE、
THIRD-PARTY-NOTICES.txt、THIRD-PARTY-LICENSES\、BUILD-INFO.txt、SOURCE-CODE.txt。

PIReader 必须与 MiniJMP.exe 同级：frozen onedir 的程序模块在 _internal 内，
代码显式以 sys.executable 所在目录作为应用根，不会去 _internal\PIReader 查找。

---

## C. 版本标识

三者刻意不同，不要强行改成同一字符串：

| 用途 | 位置 | 值 |
|---|---|---|
| 发布文件名 | tools\build_windows_release.ps1 的 $releaseVersion | V0.1-beta3 |
| 产品展示 | version_info.txt 的 ProductVersion、USAGE.txt、README.md、关于窗口、CHANGES | v0.1.0-beta.3 |
| EXE 四段数值 | version_info.txt 的 filevers / prodvers / FileVersion | 0.1.0.3 |

预检查用 tools/release_metadata.py 分别核对这三层，不要求彼此字符串相同。

对应源码 ZIP 保留 MiniJMP 与 PIReader 源码及构建材料。`tools/make_zip.py stage-source` 会排除本机 `PIReader/config.txt`、被 Git 忽略的 OSIsoft SDK DLL、测试/临时日志、草稿截图和版本化构建日志；这些排除仅作用于源码暂存，本机运行包仍使用授权的 PIReader 配置与依赖。

---

## D. 校验值与结构复核

    $python = (Resolve-Path ".venv\Scripts\python.exe").Path
    Get-Content .\dist\MiniJMP-V0.1-beta3-SHA256SUMS.txt
    & $python .\tools\make_zip.py rehash .\dist\MiniJMP-V0.1-beta3.zip --interval 15 --attempts 3
    & $python .\tools\make_zip.py rehash .\dist\MiniJMP-V0.1-beta3-source.zip --interval 15 --attempts 3
    & $python .\tools\make_zip.py inspect .\dist\MiniJMP-V0.1-beta3.zip --entry MiniJMP-V0.1-beta3/MiniJMP.exe

预期：两次 rehash 与 SHA256SUMS 三行一致；CRC=ok；ENTRY-SHA256 等于
dist\MiniJMP-V0.1-beta3\MiniJMP.exe 的摘要；PIReader 条目与该目录实际文件数一致
（exe、两个 .cs、csproj、build.bat、config.txt、tags.txt，以及组织授权的 OSIsoft DLL）。

build-inputs-V0.1-beta3.txt 是打包瞬间的运行包文件清单与摘要；
SHA256SUMS.txt 是沉降复验后的最终交付值。

---

## E. 冒烟

    $python = (Resolve-Path ".venv\Scripts\python.exe").Path
    & $python .\tools\smoke_launch.py .\dist\MiniJMP-V0.1-beta3\MiniJMP.exe 90

ZIP 解压版（解压到 %TEMP%，公司目录里的文件可能被透明加密改写）：

    $python = (Resolve-Path ".venv\Scripts\python.exe").Path
    $dest = Join-Path $env:TEMP 'mjmp-unzip'
    Remove-Item -LiteralPath $dest -Recurse -Force -ErrorAction SilentlyContinue
    & $python -m zipfile -e .\dist\MiniJMP-V0.1-beta3.zip $dest
    & $python .\tools\smoke_launch.py (Join-Path $dest 'MiniJMP-V0.1-beta3\MiniJMP.exe') 90

通过标准：打印 window after Ns: ['未命名项目 — 工作表1 - Minijmp']，退出码 0。
裸 tk 占位标题不算成功。冷启动 8–28 秒属正常，等满 90 秒再判失败。

---

## F. 功能抽样（正式构建后）

    $python = (Resolve-Path ".venv\Scripts\python.exe").Path
    & $python -m pytest tests\test_windows_packaging.py tests\test_windows_release_tools.py tests\test_csv_import.py tests\test_file_io.py tests\test_worksheets.py tests\test_sheet_context.py tests\test_pi_import.py -q

GUI 抽样：CSV/Excel 导入导出、工作表操作、.dexpl 保存与重开、离线帮助、
普通统计与图形、PI 导入入口的路径发现。

PI 服务器连接测试只能在具备授权的企业终端进行。

---

## 本机已知坑

| 现象 | 原因 | 对策 |
|---|---|---|
| SHA256 记录值与实际不符 | 透明加密在 ZIP 落盘后 1–3 分钟改写字节：size 会变、mtime 不变 | 脚本先等 120 秒，连读三次间隔 15 秒一致才记录；写出后再等 90 秒复验，漂移即失败 |
| 日志里的字节数与实际不同 | 同上，DLP 重新压缩整个 ZIP | 以 rehash 与 D 段复测为准 |
| 构建几十秒内中止 | $ErrorActionPreference='Stop' 把 PyInstaller 的 stderr INFO 当致命错误 | 脚本已把 PyInstaller 调用包在 Continue 作用域内 |
| 报 Existing build output must be removed | 旧产物还在，脚本不批量删 | 跑 A 段清场 |
| 报 Encrypted (DLP) files found | 输入文件本身已被换成 %TSD-Header- 容器 | 从干净副本恢复该文件；源码暂存已改到 %TEMP% |
| 冒烟只看到 tk | Tk 先建窗口再设标题 | smoke_launch.py 过滤占位标题 |
| .ps1 报中文引号错乱 | Windows PowerShell 5.1 把无 BOM 的 UTF-8 当 ANSI | 两个发布脚本必须保存为 UTF-8 BOM |
| 源码包缺新工具 | 仅用 git ls-files 会漏掉未跟踪文件 | 源码包按磁盘内容暂存，未跟踪工具同样收录 |

---

## 企业安全环境

### TsdEncrypt / DLP

- 源码暂存放在 %TEMP%\MiniJMP-source-<guid>，不落在同步目录或项目输出目录。
- 打包前全量扫描 %TSD-Header- 文件头，命中即中止。
- 稳定性判断只读文件内容（三次 SHA256），不看 size 或 mtime。
- ZIP 校验 CRC 与关键条目摘要；写出 SHA256SUMS 后再复验一轮。
- 持续漂移时脚本明确失败，不宣称校验通过。
- 不绕过、不暂停、不卸载、不修改 TsdEncrypt/DLP。

### Defender 与权限

- 不关闭 Defender、不加防火墙规则、不请求管理员权限。
- Defender 可能拦截 MiniJMP.exe 或 PIReader.exe；构建成功不代表目标机可执行。
- 被拦截时保留进程、路径、签名与告警信息供人工判断。
- 普通用户权限运行只能由办公电脑验收确认。

---

## 必须在办公电脑验收

本机构建通过不代表企业环境可用。以下各项保留为 NOT VERIFIED：

1. Defender 是否拦截 MiniJMP.exe 与 PIReader.exe。
2. TsdEncrypt 环境下能否启动，输出文件是否完整。
3. 离线帮助能否打开。
4. 普通用户权限下能否启动。
5. HKCU 中 PI 路径保存与重启恢复。
6. 在另一台授权办公电脑打开 .dexpl。
7. 目标机是否安装 PI SDK / PIPC 运行时。
8. PI Server 是否可访问、能否正常导入数据。
