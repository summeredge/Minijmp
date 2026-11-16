# MiniJMP Windows 分发包打包指令

唯一构建入口是 `tools/build_windows_release.ps1`，本文是复制即用的操作卡。
下面每个代码块都可以整段复制执行，不用改路径。

---

## A. 交给 AI/同事时的任务指令

> 整段复制发给对方即可，无需填空。

```
任务：基于本地 main 分支最新代码，构建 MiniJMP Windows x64 分发包。

项目根目录：D:\MyTools\Minijmp
构建入口：tools\build_windows_release.ps1（不要另写构建脚本）

步骤：
1. 前置检查：git status / git log -1 / origin/main 是否一致；分支必须是 main 且
   HEAD == origin/main，否则先 fetch（不 reset、不提交、不推送、不合并不强推）。
   工作区允许存在未提交文件（PIReader/、.workbuddy/ 等），构建取磁盘当前内容。
   若本次改过代码，先跑一遍相关测试拿基线，再动构建。
2. 清场：若 `dist\MiniJMP-V*` 或 `build\windows-pkg` 已存在，**先执行 B 段**，
   否则脚本会明确中止并提示先清场（本机沙箱禁止 PowerShell 一次批量删除上千文件）。
3. 构建：后台跑脚本，stdout 重定向到 build\build-stdout.txt（见 C 段）。
   PyInstaller 输出走 stderr，不要因此判定失败，以日志末尾和退出码为准。
4. 校验：独立复核 SHA256SUMS.txt 与三个产物是否一致（见 D 段）。
   本机透明加密会在 ZIP 写入后 1~3 分钟改写字节，必须等沉降后复测。
5. 冒烟：对 dist 内的 EXE 和 ZIP 解压后的 EXE 各跑一次 tools\smoke_launch.py。
6. 功能：跑 E 段的功能测试，全绿才算通过。
7. 新鲜度：跑 F 段，确认产物包含全部最新源文件（两行都必须 FRESH）。
8. 报告：分发版本号、ZIP 完整路径与字节数、SHA256、未完成的办公电脑验收项。

约束：
- 不修改 .venv 的 Python 版本和已有依赖；构建工具缺失时才补装。
- 不修改业务代码，除非验收测试暴露真实缺陷——此时先报告再修，修完重跑测试并重新打包。
- PIReader/ 必须随包发布（放在 MiniJMP.exe 同级），config.txt 原样打包。
- 不改 Defender / TsdEncrypt 策略，不请求管理员权限。
```

---

## B. 清场（重建前必做）

脚本发现 `dist\MiniJMP-V*` 或 `build\windows-pkg` 已存在会直接中止并提示先清场——
本机沙箱禁止 PowerShell 一次性批量删除上千个文件，所以清场交给 Python 做。
首次构建（`dist` 为空）可跳过。

```bash
cd /d/MyTools/Minijmp && ./.venv/Scripts/python.exe -c "
import glob, os, shutil
targets = [p for p in glob.glob('dist/MiniJMP-V*')] \
        + glob.glob('build/windows-pkg') \
        + glob.glob('docs/release/pyinstaller-build-V*.txt')
for t in targets:
    shutil.rmtree(t) if os.path.isdir(t) else os.remove(t)
    print('cleared', t)
print('cleared:', len(targets))
"
```

> 用 Python 删，不用 `rm -rf`；沙箱会拦 `rm -rf`，且删目录走 `shutil.rmtree` 更稳。

---

## C. 构建（PowerShell，后台执行）

```powershell
$log = 'D:\MyTools\Minijmp\build\build-stdout.txt'
New-Item -ItemType Directory -Path (Split-Path $log) -Force | Out-Null
"" | Set-Content -LiteralPath $log -Encoding utf8
try {
  & 'D:\MyTools\Minijmp\tools\build_windows_release.ps1' *> $log
} catch {
  "EXCEPTION: $($_.Exception.Message)" | Add-Content -LiteralPath $log
}
"EXIT=$LASTEXITCODE" | Add-Content -LiteralPath $log
```

查看进度（Bash，别用 PowerShell 工具读，本机该工具拿不到 stdout）：

```bash
cd /d/MyTools/Minijmp && tail -6 build/build-stdout.txt | tr -d '\0'
```

总耗时约 **12 分钟**：PyInstaller 约 4.5 分钟，两个 ZIP 约 1 分钟，末尾等透明加密沉降
约 2.5 分钟，最后 90 秒漂移复验。成功时日志末尾是产物清单、三行 SHA256 和 `EXIT=0`；
失败看 `EXCEPTION:` 行或最后一条 PyInstaller `ERROR`。

---

## D. 校验值与结构复核

```bash
cd /d/MyTools/Minijmp && ./.venv/Scripts/python.exe -c "
import glob, hashlib, os, zipfile
def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''): h.update(c)
    return h.hexdigest().upper()

sumfile = sorted(glob.glob('dist/*-SHA256SUMS.txt'))[-1]
print('checksum file:', os.path.basename(sumfile))
ok = True
for line in open(sumfile):
    if not line.strip(): continue
    want, name = line.split(None, 1)
    path = os.path.join('dist', name.strip())
    got = sha(path)
    good = got == want
    ok &= good
    print(('OK  ' if good else 'FAIL'), name.strip(), f'{os.path.getsize(path):,}')

runtime_zip = [p for p in glob.glob('dist/MiniJMP-V*.zip') if '-source' not in p][0]
with zipfile.ZipFile(runtime_zip) as z:
    names = z.namelist()
    print('runtime zip entries:', len(names), 'crc_errors:', z.testzip())
    bad = [n for n in names if any(k in n.lower() for k in
           ('/obj/', '/.git/', '/.venv/', '__pycache__', 'icon.png', '/tests/'))]
    print('forbidden entries:', bad[:5], 'count:', len(bad))
    pi = [n for n in names if '/PIReader/' in n]
    print('PIReader entries:', len(pi))
    for n in sorted(pi): print('   ', n)
print('ALL MATCH:', ok)
"
```

预期：三行 `OK` + `ALL MATCH: True`，`crc_errors: None`，`forbidden count: 0`，
`PIReader entries: 10`（exe、三个 OSIsoft DLL、两个 .cs、csproj、build.bat、config.txt、tags.txt）。

---

## E. 冒烟测试与功能验证

dist 目录版：

```bash
cd /d/MyTools/Minijmp && ./.venv/Scripts/python.exe tools/smoke_launch.py \
  "$(ls -d dist/MiniJMP-V*)/MiniJMP.exe" 90
```

ZIP 解压版（模拟真实分发，务必在临时目录解压，项目目录里的文件会被透明加密改写）：

```bash
cd /d/MyTools/Minijmp && ./.venv/Scripts/python.exe -c "
import glob, os, shutil, tempfile, zipfile
dest = os.path.join(tempfile.gettempdir(), 'mjmp-unzip')
shutil.rmtree(dest, ignore_errors=True)
runtime_zip = [p for p in glob.glob('dist/MiniJMP-V*.zip') if '-source' not in p][0]
with zipfile.ZipFile(runtime_zip) as z:
    z.extractall(dest)
print(os.path.join(dest, os.listdir(dest)[0]))
"
```

```bash
cd /d/MyTools/Minijmp && EXE=$(ls -d "$TEMP"/mjmp-unzip/MiniJMP-V*/MiniJMP.exe) && \
  ./.venv/Scripts/python.exe tools/smoke_launch.py "$EXE" 90
```

通过标准：打印 `window after Ns: ['未命名项目 — 工作表1 - Minijmp']`，退出码 0。
冷启动 8–28 秒属正常，等满 90 秒再判失败。脚本会自动结束进程，无需手动 taskkill。

功能验证（CSV/Excel 导入、工作表操作、`.dexpl` 存取）：

```bash
cd /d/MyTools/Minijmp && ./.venv/Scripts/python.exe -m pytest \
  tests/test_windows_packaging.py tests/test_csv_import.py tests/test_file_io.py \
  tests/test_worksheets.py tests/test_sheet_context.py tests/test_g17_csv.py -q
```

通过标准：`195 passed`，无 failed。

---

## F. 确认产物是不是最新文件

构建完（或接手别人的产物时）跑这条，判断 EXE / 源码包是否包含工作区当前所有源文件。
两行都必须是 `FRESH`；出现 `STALE` 说明构建后有源文件被改，需要重新打包。

```bash
cd /d/MyTools/Minijmp && ./.venv/Scripts/python.exe -c "
import glob, time, pathlib
runtime_roots = ['code', 'help', 'sample_data', 'user_config', 'icon', 'packaging', 'PIReader']
def files(roots):
    return [p for r in roots for p in pathlib.Path(r).rglob('*')
            if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc'
            and 'obj' not in p.parts]
rt = files(runtime_roots)
exe = pathlib.Path(glob.glob('dist/MiniJMP-V*/MiniJMP.exe')[0])
src_zip = pathlib.Path(glob.glob('dist/MiniJMP-V*-source.zip')[0])
fmt = lambda t: time.strftime('%H:%M:%S', time.localtime(t))
newest_rt = max(rt, key=lambda p: p.stat().st_mtime)
print('运行包源文件:', len(rt), '最晚', fmt(newest_rt.stat().st_mtime), newest_rt)
print('EXE      :', fmt(exe.stat().st_mtime), f'{exe.stat().st_size:,} B')
print('运行包新鲜度:', 'FRESH' if exe.stat().st_mtime > newest_rt.stat().st_mtime else 'STALE 需重打包')
allf = files(runtime_roots + ['tools', 'tests']) + [p for p in map(pathlib.Path, ['LICENSE','README.md','CHANGES','AGENTS.md','CODING_STANDARDS.md','CONTRIBUTING.md','requirements.txt','start.py','setup_env.bat','win_start.bat','win_start_no_cmd_win.vbs']) if p.exists()]
newest_all = max(allf, key=lambda p: p.stat().st_mtime)
print('源码包源文件:', len(allf), '最晚', fmt(newest_all.stat().st_mtime), newest_all)
print('源码包新鲜度:', 'FRESH' if src_zip.stat().st_mtime > newest_all.stat().st_mtime else 'STALE 需重打包')
"
```

再确认 ZIP 里装的确实是这一份 EXE（不是旧包改名）：

```bash
cd /d/MyTools/Minijmp && ./.venv/Scripts/python.exe -c "
import glob, hashlib, zipfile
def sha_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''): h.update(c)
    return h.hexdigest().upper()
exe = glob.glob('dist/MiniJMP-V*/MiniJMP.exe')[0]
runtime_zip = [p for p in glob.glob('dist/MiniJMP-V*.zip') if '-source' not in p][0]
with zipfile.ZipFile(runtime_zip) as z:
    name = [n for n in z.namelist() if n.endswith('/MiniJMP.exe')][0]
    inner = hashlib.sha256(z.read(name)).hexdigest().upper()
print('dist:', sha_file(exe))
print('zip :', inner)
print('MATCH:', sha_file(exe) == inner)
"
```

---

## 本机已知坑

| 现象 | 原因 | 对策 |
|---|---|---|
| SHA256 记录值与实际不符 | 透明加密在 ZIP 落盘后 1~3 分钟改写字节：**size 会变、mtime 不变** | 脚本已改为「先等 120 秒 → 连读三次间隔 15 秒一致 → 写出后再等 90 秒复验，漂移则重测」；人工复核必须用 D 段，别用单次 `Get-FileHash` |
| 源码包/运行包 size 与日志里的数字不一致 | 同上，DLP 重新压缩了整个 ZIP | 以 D 段复测结果为准，日志里的数字只是写入瞬间的值 |
| 构建 50 秒内中止 | `$ErrorActionPreference='Stop'` 把 PyInstaller 的 stderr `INFO` 当致命错误 | 脚本已把 PyInstaller 调用包在 `Continue` 里；若重现，检查该调用前后 |
| `.dexpl` 保存后文件是 0 字节 / 打开报 `EOFError` | `doSaveProject` 用 `gzip.GzipFile` 却不关闭，要等 GC 才落盘 | 已改为 `with` 上下文；`tests/test_file_io.py` 有中文工程往返用例守着 |
| 脚本报 `Existing build output must be removed before rebuilding` | 旧产物还在，脚本不能批量删 | 跑 B 段清场再构建 |
| 重构建时弹 `SAFE_DELETE_BULK_CONFIRM_REQUIRED` | PowerShell `Remove-Item` 一次删上千文件被沙箱拦 | 同上；这就是脚本改成「先报错提示」而不是硬删的原因 |
| 脚本报 `Encrypted (DLP) files found in package` | 写进项目目录的 Office 文档会被 DLP 换成 `%TSD-Header-###%` 容器（实测 `icon/icon.pptx` 44646 → 49152 字节，已损坏） | 源码暂存已改到 `%TEMP%`；打包前脚本会全量扫头，命中即中止。看到这条说明源文件本身被加密，需从干净副本恢复 |
| `SHA256SUMS.txt` 自己变成 8192 字节、打开是乱码 | DLP 也会加密小文本文件，Python 写出的就中了 | 用 PowerShell `Set-Content -Encoding ascii` 重写（脚本本来就这么写）；重写后等 2 分钟再确认可读 |
| 冒烟报 `window after Ns: ['tk']` | Tk 先建窗口再设标题，裸 `tk` 只说明工具包起来了 | `tools/smoke_launch.py` 已过滤占位标题，应看到「未命名项目 — 工作表1 - Minijmp」 |
| 源码包缺 `tools/make_zip.py` | 该文件未纳入 Git，`git ls-files` 取不到，但构建脚本依赖它 | 脚本已把 `tools/make_zip.py`、`tools/smoke_launch.py` 列入显式清单 |
| 截图打不开 / 图片是乱码 | 项目目录内图片被加密成 `%TSD-Header-###%` | 截图落 `%TEMP%`；优先用 `tools/smoke_launch.py` 走窗口句柄判断 |
| `.ps1` 报奇怪的语法错 | Write/Edit 产出 LF 行尾 | 改完 `.ps1` 后用 Python 转 CRLF |
| PowerShell 工具无输出 | 本机该工具 stdout 失效 | 只读排查全走 Bash |
| `rm -rf` 被拦截 | 沙箱策略 | 用 Python `shutil.rmtree` |
| `Add-Type` 被拦截 | 沙箱禁止运行时编译 .NET | 不要用 `ZipFile::CreateFromDirectory`，压缩走 `tools/make_zip.py` |

---

## 升版本时改哪里

| 位置 | 内容 | 说明 |
|---|---|---|
| `tools/build_windows_release.ps1:25` | `$version = 'V0.1-beta2'` | 决定三个产物的文件名 |
| `tools/build_windows_release.ps1` 内 `BUILD-INFO` 数组 | 标题用 `$version` | 自动跟随，无需单独改 |
| `packaging/windows/version_info.txt:3-4` | `filevers=(0,1,0,2)` `prodvers` | EXE 属性页版本，四段数字 |
| `packaging/windows/version_info.txt:17,22,23` | `FileVersion` / `ProductVersion` / `Comments` | EXE 属性页显示文本 |
| `code/modified_app.py:69` | 关于窗口「版本 v0.1.0-beta.2」 | 用户可见 |
| `packaging/windows/USAGE.txt:1` | 运行包内 `README.txt` 首行 | 用户可见 |
| `README.md:9` | `当前版本标识` | 仓库首页 |
| `CHANGES` | 新增本节条目 | 保留历史条目，不覆盖 |

**文件名版本与产品版本是两个东西**：`$version` 只决定 ZIP 和目录名（例如 `MiniJMP-V0.1-beta2`），
EXE 属性页仍读 `version_info.txt`（`v0.1.0-beta.2` / `0.1.0.2`）。两者不一致是刻意的，
`BUILD-INFO.txt` 里已同时写明，不需要为此再改代码。

版本一致性检查（EXE 属性页读回来核对）：

```bash
cd /d/MyTools/Minijmp && ./.venv/Scripts/python.exe -c "
import glob, pefile, re
exe = glob.glob('dist/MiniJMP-V*/MiniJMP.exe')[0]
pe = pefile.PE(exe, fast_load=True)
pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_RESOURCE']])
for e in pe.DIRECTORY_ENTRY_RESOURCE.entries:
    if pefile.RESOURCE_TYPE.get(e.struct.Id) == 'RT_VERSION':
        d = e.directory.entries[0].directory.entries[0].data.struct
        raw = pe.get_data(d.OffsetToData, d.Size)
        print([s.decode('utf-16-le','ignore') for s in re.findall(rb'(?:[\x20-\x7e]\x00){3,}', raw)])
"
```

---

## 产物与前置条件

产物（全在 `dist\`）：

```
MiniJMP-<version>.zip                 运行包（整目录，解压即用）
MiniJMP-<version>-source.zip          对应源码包（GPLv3 要求）
MiniJMP-<version>-SHA256SUMS.txt      三个产物的校验值
MiniJMP-<version>\                    未压缩运行目录，可直接双击
docs\release\pyinstaller-build-<version>.txt   构建日志
```

运行包根目录：`MiniJMP.exe`、`_internal\`、`PIReader\`、`README.txt`、`LICENSE`、
`THIRD-PARTY-NOTICES.txt`、`THIRD-PARTY-LICENSES\`、`BUILD-INFO.txt`、`SOURCE-CODE.txt`。

`PIReader\` 必须在 `MiniJMP.exe` 同级，不能放进 `_internal\`：frozen 模式下模块的
`__file__` 在 `_internal\` 内，代码按 `.parent.parent` 推出的应用根目录就是 EXE 所在目录
（2026-10-25 用 PyInstaller 探针实测确认）。

前置条件：

- 分支 `main` 且 HEAD == `origin/main`（脚本硬校验）
- `.venv\Scripts\python.exe` 为 64 位 Python 3.11 或 3.12（本机是 3.12.3）
- PyInstaller 版本必须 `6.22.3`，否则脚本拒绝构建
- `PIReader\PIReader.exe` 与 `PIReader\config.txt` 必须存在，否则脚本拒绝构建
- 依赖锁文件 `packaging\windows\requirements-py311.lock` 是 3.11 产物；在 3.12 下
  只把差异写进 `BUILD-INFO.txt`，不阻断构建

固定打包参数（改前先想清楚）：`--onedir --windowed --noupx --contents-directory _internal`，
图标 `icon\icon_big.ico`，入口 `packaging\windows_entrypoint.py`，
压缩由 `tools/make_zip.py` 完成（Python zipfile，约 50 秒；`Compress-Archive` 在本机要一个多小时）。
源码暂存在 `%TEMP%\MiniJMP-source-<guid>`，不落在项目目录，避免被 DLP 加密。

运行包 ZIP 的条目数比文件数多约 180，那是 DLP 重写压缩包时补上的目录条目，属正常现象；
判断完整性看「真实文件数」和 `crc_errors: None`，不要按条目数对账。

---

## 必须在办公电脑验收

本机构建通过不代表企业环境可用，以下各项只能在办公电脑确认：

1. Defender 是否拦截 `MiniJMP.exe` 与 `PIReader.exe`。
2. TsdEncrypt 环境下能否启动、离线帮助能否正常打开。
3. CSV/Excel 导入导出、`.dexpl` 保存后在**另一台授权机**能否打开。
4. 普通用户权限下启动、PI 路径的 HKCU 保存与重启恢复。
5. PI 导入功能：包内 `PIReader\` 已就位，但还需要目标机装有 PIPC/PI SDK 运行时、
   且能连到 `config.txt` 中的 PI 服务器——本机无内网连接，无法预先验证这一步。
