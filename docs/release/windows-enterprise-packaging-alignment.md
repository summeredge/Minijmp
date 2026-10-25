# Windows 企业环境分发流程对齐核对（2026-10-25）

范围：只同步发布工具链与文档。**未运行 PyInstaller，未生成 EXE 或 ZIP，未删除旧产物，
未运行全项目 pytest，未修改安全策略，未提交或推送 Git。**

## 1. GitHub 原实现与办公环境最终版本的差异

| 项目 | 原仓库实现 | 办公环境最终方案 |
|---|---|---|
| Python | 硬性要求 3.11.9 | Windows x64、Python >= 3.11，数值比较 |
| 锁文件不一致 | 直接阻断 | 3.11 仍阻断；3.12+ 只写入 BUILD-INFO |
| 工作区 | 脏工作区阻断构建 | 只输出 WARNING 与数量，取磁盘内容并记录 |
| PIReader | 显式从包中剔除，config.txt 视为敏感文件 | PIReader 与 config.txt 随包，位于 EXE 同级 |
| 压缩 | Compress-Archive | tools/make_zip.py（zipfile） |
| 启动检查 | 无 | tools/smoke_launch.py，过滤 tk 占位标题 |
| 源码清单 | 仅 git ls-files（漏未跟踪文件） | 按磁盘内容暂存 + SHA256 清单 |
| 哈希 | 单次 Get-FileHash | 沉降 120s、三读一致、写后 90s 复验 |
| 版本 | $version 同时当发布名与产品名 | $releaseVersion、ProductVersion、四段数值分层核对 |
| 旧产物 | 脚本内删除 build 目录 | 明确拒绝，清场留给人工 Python 操作 |
| 日志 | docs/release/pyinstaller-build-<sha>.txt 会阻断下次构建 | 以发布名命名，清场清单内一并处理 |

## 2. 已同步的文件与行为

- tools/build_windows_release.ps1：唯一入口。main 与 origin/main 校验；脏工作区 WARNING；
  Python/PyInstaller/版本预检；旧产物拒覆盖；onedir、windowed、noupx、_internal、ICO
  与版本资源保持；PIReader 复制到 EXE 同级；PyInstaller 调用置于 Continue 作用域；
  源码暂存到 %TEMP%；ZIP 由 make_zip.py 生成；CRC 与 EXE 摘要比对；沉降与复验；
  dist/ZIP 两种冒烟。
- tools/check_windows_release_ready.ps1：只读预检查，未提交文件记 WARNING；调用
  release_env.py 与 release_metadata.py，分别核对环境与三层版本标识；检查 PI 随包文件。
- tools/make_zip.py（新增）：make、inspect、rehash、scan、manifest、stage-source。
  中文名按 UTF-8 写入，跳过 obj/bin/缓存，拒绝覆盖已有输出，失败非零退出。
- tools/smoke_launch.py（新增）：仅当窗口标题含 Minijmp 且不是 tk 时判定启动成功，
  超时或提前退出返回非零。
- tools/release_env.py（新增）、tools/release_metadata.py（新增）：共享的版本与依赖判定。
- code/pi_import.py：新增 application_root()，frozen 时以 sys.executable 目录为应用根，
  不再从 _internal 推导；源码运行行为不变。
- PACKAGING.md（新增）、README.md、docs/PI-data-import.md、packaging/windows/USAGE.txt、
  help/pages/operations.html 与 help/assets/search-index.js、CHANGES。
- docs/release/windows-beta-readiness-20261023.md：保留 2026-10-23 原始结果，只加后续修订说明。

## 3. Python 3.11+ 兼容策略

- 版本判定使用 sys.version_info，最低 (3, 11)；3.11.9、3.12.3、3.13 均放行，3.10 拒绝。
- requirements-py311.lock 保留原名。3.11 不一致为 BLOCKED；3.12+ 为 WARNING 并写进
  BUILD-INFO，但 pip check 冲突、缺失运行依赖、PyInstaller 非 6.22.3 仍为 BLOCKED。
- 第三方声明按实际安装版本生成（write_third_party_notices.py 读 importlib.metadata），
  未使用锁文件版本冒充。

## 4. PIReader 分发边界

- 随包：PIReader 目录与 MiniJMP.exe 同级，含 PIReader.exe、config.txt（原样）、
  Program.cs、TimeExpressionParser.cs、PIReader.csproj、build.bat、tags.txt，
  以及办公环境已确认的 OSIsoft DLL；obj/、bin/、.vs/ 排除。
- 不在包内：PI SDK/PIPC 运行时安装程序。目标机需自行具备；PI Server 连接只能在企业内网验证。
- 源码包包含 PIReader 工程文件与构建说明，可复现 x86 / .NET Framework 4.8 构建。
- 当前仓库 PIReader 目录没有随包 OSIsoft DLL，脚本按实际文件复制并记录数量；
  办公环境若补齐 DLL，无需改脚本。

## 5. TsdEncrypt、Defender、权限、DLP

- 源码暂存在 %TEMP%\MiniJMP-source-<guid>，不写项目输出目录。
- 打包前后扫描 %TSD-Header- 文件头，命中即失败。
- 稳定性只用内容读取：120s 沉降 + 三次 15s 间隔 SHA256 一致；写 SHA256SUMS 后再 90s
  复验，漂移则失败并提示不要分发。
- ZIP 校验 CRC，并比对包内 EXE 与 dist EXE 的 SHA256。
- 不关闭 Defender、不加防火墙规则、不请求管理员权限、不修改安全策略。
- 构建成功不等于目标机能运行；两项 EXE 是否被拦截只能现场判断。

## 6. 定向测试结果

解释器：.venv\Scripts\python.exe（Python 3.11.9，64 位）。

| 检查 | 命令 | 结果 |
|---|---|---|
| 定向测试 | pytest tests\test_windows_packaging.py tests\test_windows_release_tools.py | 23 passed |
| PI 导入路径 | pytest tests\test_pi_import.py | 32 passed |
| 帮助中心 | pytest tests\test_help_center.py | 12 passed |
| 只读预检查 | check_windows_release_ready.ps1 | RESULT: PASS（工作区变更等 12 项 WARNING） |
| 版本核对 | release_metadata.py | PASS：V0.1-beta2 / v0.1.0-beta.2 / 0.1.0.2 |
| 环境核对 | release_env.py | 5 项 PASS |
| 脚本语法 | PowerShell Parser | 两个脚本 0 错误（UTF-8 BOM） |
| 旧产物拒覆盖 | 实跑发布脚本 | 报 Existing build output must be removed，未创建 build\ |
| 源码暂存 | make_zip.py stage-source + manifest + scan | 579 个文件，无 DLP 命中 |

以上运行未触发 PyInstaller；make_zip 与 smoke_launch 的判定逻辑由新增单测覆盖。

## 7. 仍需企业真实机器验收（NOT VERIFIED）

1. Defender 是否拦截 MiniJMP.exe 与 PIReader.exe。
2. TsdEncrypt 环境下启动与输出文件完整性。
3. 离线帮助能否打开。
4. 普通用户权限下启动。
5. HKCU 中 PI 路径保存与重启恢复。
6. 另一台授权办公电脑能否打开 .dexpl。
7. 目标机 PI SDK/PIPC 运行时是否存在。
8. PI Server 是否可访问、能否正常导入数据。

另外未执行：正式打包、ZIP 生成、EXE 冒烟、全量 pytest、多轮回归。

