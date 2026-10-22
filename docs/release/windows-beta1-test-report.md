# MiniJMP v0.1.0-beta.1 Windows 发布验证

状态：Windows x64 onedir 包和对应源码包已构建，静态包审计通过。本机 GUI 部分冒烟通过，但后续操作被 Windows GUI 自动化输入接口拒绝，未完成验收；全量回归仍有 1 个失败和 1 个 teardown error。公司 Defender、透明加密和无 Python 目标机测试尚未完成。

## 冻结基线

- 基线 Tag：`baseline-20261022`（annotated tag object `93052c0c611504282574a4b496b8a0cb797f4dca`）
- Tag 指向 Commit：`3cfb1d3de23a7806c8027cc757d7e9b110c25af3`
- 发布分支：`codex/release-v0.1.0-beta.1`，从该 Commit 建立
- 打包时 HEAD 仍为基线 Commit。发布改动保留在未提交工作树；未提交、推送或创建 GitHub Release。

## 项目清理

- `docs/g*-evidence/` 的正式报告、验证记录和仍被引用的证据均保留。
- 将 G14、G18 的 9 份测试/基准历史源码从 `docs/*-evidence/before/` 移至 `tests/fixtures/g14_before/` 和 `tests/fixtures/g18_before/`；迁移前后按 SHA256 核对。
- 将 10 个仍被测试引用的历史提交中的 46 份源码快照迁至 `tests/fixtures/source_baselines/`。7 个测试文件改为读取固定夹具，不再运行 `git show`；快照以 `.py.txt` 保存，避免 pytest 将其中的 `*_test.py` 误收集为测试。
- 将 10 个未被程序或构建脚本使用的历史输出/依赖文件归档到 `docs/archive/20261022-project-cleanup/`：旧 pytest 日志、重复 G7 日志、6 份多工作表运行日志、旧依赖清单。文件内容已核对；运行中的 `log/error.log` 保留。
- 保留全部有效测试、开发工具、正式许可证、帮助文件和证据目录；未删除整个 `tests/` 或 `docs/`。
- 测试生成的忽略缓存仍留在工作区；递归清理命令被工具策略拦截后未重试。运行包和源码 ZIP 均已检查为不含这些缓存。

## 构建环境与产物

- OS：Microsoft Windows 11 专业版，版本 `10.0.26200`，Build `26200`，64 位
- Python：`3.11.9` x64，解释器 `.venv\Scripts\python.exe`
- PyInstaller：`6.22.3`；构建命令由 `tools/build_windows_release.ps1` 固定为 `--onedir --windowed --noupx`
- 精确依赖清单：`packaging/windows/requirements-py311.lock`（42 个版本固定项）；`pip check`：`No broken requirements found.`
- 关键运行依赖：NumPy 2.4.6、SciPy 1.15.3、pandas 3.0.6、Matplotlib 3.11.2、Seaborn 0.13.2、statsmodels 0.15.0、openpyxl 3.1.5、xlrd 2.0.2、Pillow 13.0.0。
- PyInstaller 成功生成 onedir；日志识别 Tk/Tcl、TkAgg、NumPy、SciPy、pandas、Matplotlib、openpyxl、statsmodels。构建日志有 hidden import `scipy.special._cdflib` 未找到的警告；该模块在锁定的 SciPy 1.15.3 环境中也不存在，仍需运行打包版验证功能路径。完整输出见 `pyinstaller-build-20261022.txt`。
- PE 静态检查：machine `0x8664`（x64），subsystem `2`（Windows GUI）；版本资源为 MiniJMP / `v0.1.0-beta.1`。正式图标已嵌入。
- 运行 ZIP 为 2,164 项、未压缩约 219,127,503 bytes；含 59 个 DLL。未发现 `.git`、`.venv`、`tests/`、`docs/`、pytest/Python 缓存、`PIReader.exe` 或 `config.txt`。
- 配套源码 ZIP 含构建脚本、依赖锁、测试和历史快照；不含 `.git`、`.venv` 或 Python/pytest 缓存。
- ZIP 带 GPLv3、第三方包及许可证清单、Python/Tcl-Tk 许可文本、作者来源说明和使用指南。PIReader、PI SDK、服务器配置与凭据均未打包。

文件位置：

- 运行目录：`dist/MiniJMP-v0.1.0-beta.1-win64/`
- 发布 ZIP：`dist/MiniJMP-v0.1.0-beta.1-win64.zip`（102,839,282 bytes）
- 对应源码 ZIP：`dist/MiniJMP-v0.1.0-beta.1-source.zip`（1,378,475 bytes）
- 构建日志：`docs/release/pyinstaller-build-20261022.txt`
- SHA256 清单：`dist/MiniJMP-v0.1.0-beta.1-SHA256SUMS.txt`

| 文件 | SHA256 |
|---|---|
| `MiniJMP.exe` | `5CFEB400D63E744CD7CEBE1F0E61853BC94A5144FC7EB2658DF1B3FC7CE041A0` |
| 发布 ZIP | `1CEE49783D403D588F150DA02818EB7062DF2ED5F48DBCFE46A86D81559049BC` |
| 源码 ZIP | `0496C30126EDE8AB830AAF255B9A252A9DFE434E49F68536A816A9B50E026DE7` |

## 测试记录

### 冻结前基线

命令：`& .venv\Scripts\python.exe -m pytest -q --tb=short`

结果：`2401 passed, 4 failed, 129 warnings, 1 error`，279.82 秒，退出码 1。原始日志：`beta1-baseline-pytest.txt`。失败是已有冻结断言/测试替身与当前 UI 路由、工作表调用和 Plot Viewer 清理接口不一致，以及一个 PI 导入用例的 Tk 延迟回调 teardown 异常；在清理阶段分别修正了过期断言和替身。

### 历史源码夹具迁移专项

命令：7 个依赖历史源码的测试文件，使用项目 `.venv` 运行。

结果：`700 passed, 59 warnings`，70.86 秒。日志：`beta1-source-baseline-migration-final-pytest.txt`。

### 清理后的全量回归

命令：`& .venv\Scripts\python.exe -m pytest -q --tb=short --junitxml=docs\release\beta1-final-pytest.xml`

结果：`2407 passed, 1 failed, 203 warnings, 1 error`，354.42 秒，退出码 1。文本和 JUnit 日志：`beta1-final-pytest.txt`、`beta1-final-pytest.xml`。

- 失败：`test_embedded_plot_windows_close_and_leave_stored_figure_usable` 的弱引用回收断言。
- Teardown error：PI 时间戳菜单测试结束时，Tk 回调访问已销毁的表格控件。
- 随后用相同解释器筛选运行这两个用例及两个 PI 时间戳参数：`3 passed, 76 deselected, 2 warnings`，2.99 秒。单独通过不能替代全量结果；目前只确认该现象与测试顺序/Tk 生命周期相关，根因未定。

另有一次夹具迁移后的 pytest 收集错误：扩展名 `.py` 的历史快照被误当测试；已改为 `.py.txt` 并重跑专项及全量。错误日志保留为 `beta1-fixture-collection-collision.txt`。

### 构建与静态审计

- 命令：`& .\tools\build_windows_release.ps1`；退出码 0。包含锁依赖安装、`pip check`、PyInstaller 构建、源码 ZIP、运行 ZIP 和 SHA256 生成。
- ZIP 清单审计确认必需 EXE、`_internal/`、离线帮助索引/页面、默认配置、许可证和源码说明齐全；运行 ZIP 禁入目录与 PI 配置计数为 0。
- 静态 PE 检查不替代后续功能与目标机测试。

### 本机 GUI 冒烟（部分完成）

- 通过发布目录中的 `MiniJMP.exe` 启动，主窗口正常显示，未出现控制台窗口。
- 导入包内 `coatings.csv`：界面显示 32 行、2 列。
- 导入包内 `Gasket.xlsx`：界面显示 30 行、3 列；该样例本身只有一个 Excel 工作表。
- 新增和复制工作表成功；用户确认后已删除临时副本“Gasket 副本”。
- 当前 Windows token 非管理员；首次运行后 `%LOCALAPPDATA%\MiniJMP\user_config\default.conf` 与 `%LOCALAPPDATA%\MiniJMP\log\error.log` 已创建。
- 已在 `%TEMP%` 生成含 `First`、`Second` 两张合成工作表的 `MiniJMP-v0.1.0-beta.1-multisheet-smoke.xlsx`，并通过 GUI 导入；两个工作表标签均可见，成功切换到 `Second`。
- 继续操作时 `@oai/sky` 输入调用返回 `GetCursorPos failed: 拒绝访问 (0x80070005)`，截图捕获也返回 monitor capture 错误。重置 Computer Use 会话后问题仍复现，故未继续尝试未知结果的输入。
- `.dexpl` 保存/重开、导出、统计对话框、图形交互、Plot Viewer、离线帮助均未完成 GUI 验收。应用仍在运行（进程 ID `2168`）；无法通过当前 GUI 会话正常退出，因此关闭后无残留进程尚未验证。
- 本机启动、CSV/XLSX 和多工作表导入以及工作表增删操作已验证；其余 Windows GUI 项目不能据此视为通过。

## 尚待验收

- 本机 GUI 待人工完成：CSV/Excel 导出、`.dexpl` 保存重开、统计检验和回归、各类图形、Plot Viewer 前后台切换/缩放/移动/导出、离线帮助、正常退出及无残留进程检查。当前 GUI 自动化输入接口被拒绝，具体命令/错误记录于本报告；已通过的导入与工作表操作不代表这些项目通过。
- 无 Python 安装的 Windows 目标机运行。
- 公司域内 Defender 实时保护/高级云保护是否拦截，以及拦截时的检测名称、时间、路径和哈希记录。
- 企业透明加密环境中的导出与跨电脑读取。
- PIReader 与现场授权/服务器环境未提供，PI 功能未验证。

未修改 Defender、安全排除或企业策略。GUI 输入错误使当前进程仍运行；需要在本机桌面手动完成剩余冒烟并关闭程序，再确认无残留进程。

## icon.png 透明加密修复追加验证（2026-10-22）

- 新增 `code/icon_resource.py`，将原 `code/icon.png` 的 35,564 字节 PNG 内容以 Base64 保存在 Python 模块，并通过 `PhotoImage(data=...)` 创建 Tk 图像。主窗口与“关于”窗口共用 `create_icon_image`；“关于”窗口仍显示原作者版权及原有说明。
- `tools/build_windows_release.ps1` 不再把 `code/icon.png` 加入运行时数据；PyInstaller 仍以 `--onedir --windowed --noupx` 构建，并用 `icon/icon_big.ico` 设置 EXE 图标。构建脚本检查产物中不存在外置 `icon.png`。
- 针对性回归：`tests/test_startup.py tests/test_windows_packaging.py`，`23 passed`。
- 编译：`python -m compileall -q code tests packaging tools`，通过。
- Tk 8.6.12 实际显示内嵌 PNG：主图标 256×256，“关于”页缩略图 128×128；真实“关于 MiniJMP”窗口可见，LOGO 尺寸 128×128。
- 发布 EXE 实际 GUI 启动两次：运行目录没有 `icon.png` 时主窗口可见；在 `_internal\icon.png` 放入 34 字节模拟加密内容时主窗口仍可见。两次实例均正常关闭；模拟文件已移除，未留下 MiniJMP 进程。
- 当前 Windows GUI 输入接口未能通过菜单自动触发打包 EXE 的“关于”窗口；关于页可见性由本机 Tk GUI 直接调用同一 `about()` 实现确认。打包 EXE 的启动与缺失/模拟 PNG 测试均已实际执行。
- `dist/MiniJMP-v0.1.0-beta.1-win64/` 和发布 ZIP 均未发现名为 `icon.png` 的运行时文件；ZIP SHA256 与清单一致。更新后产物：EXE `27,763,098` 字节，运行 ZIP `102,838,025` 字节，源码 ZIP `1,414,106` 字节。

| 文件 | SHA256 |
|---|---|
| `MiniJMP.exe` | `D4A1B2310DB0BC3D2C05DC8D0B74B4B2BCE9C7B1C7F9AD10D35A9F40598B1A2B` |
| 发布 ZIP | `1DB239AB6D0325EB8BC0FFC70DFBA0286488B3AFB1F5ED22F862589624E268CF` |
| 源码 ZIP | `923ACBD6259349E596C1A1B9CDACD07FEE5C7D497CE960A1B94C8C41EF8BCFEB` |

### 其他外置资源风险

- 离线帮助仍以 `help/` 下的 HTML、CSS、JS 和 `help.json` 外置读取；默认配置和六个示例文件也作为 `_internal` 数据文件。PyInstaller hooks 收集的 Matplotlib 图片/字体及 Tk/Tcl 图片资源同样位于运行目录。若透明加密也处理这些资源，帮助页、默认配置、示例或图形功能仍可能受影响；本次没有改动这些资源，也没有在公司透明加密策略下验证它们。
- `pandastable_local/images.py` 的工具栏 GIF 已以内嵌数据提供，不依赖单独图片文件。
- 旧 `DataExplore.__init__` 在 `app.py` 中按路径读取 `dataexplore.gif`，但当前 `Minijmp.__init__` 直接初始化 `Frame`，不调用该构造函数；这不在当前启动路径内。若未来恢复旧初始化路径，应重新检查该 GIF 及其数据集目录。

本追加记录更新本机图标和 EXE 启动证据；既有全量回归记录仍为 `2407 passed, 1 failed, 1 error`，本次没有重跑全量套件。企业 TsdEncrypt 实机环境也未在本机复现。
