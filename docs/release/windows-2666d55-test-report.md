# MiniJMP 2666d55 Windows 分发验证（2026-10-22）

## 构建来源

- HEAD / 已执行 `git fetch origin main` 后的 origin/main：`2666d55faf04c615bf76976633a774318567e882`，分支 `main`。
- 正式版本：`v0.1.0-beta.1`。业务源码未修改；构建脚本、使用说明和打包测试有本次未提交修改，已收入源码 ZIP。
- 保留原有 `MacOSInstall.md` 删除、未跟踪 `PIReader/`、本地配置和旧版发布文件；未提交、推送、合并或 reset。
- 根目录不存在 `package.txt`；按现有发布说明及实际代码检查内嵌图标、用户配置目录和资源机制。

## 产物（相对仓库根目录）

| 文件 | 字节数 | SHA256 |
|---|---:|---|
| dist/MiniJMP-v0.1.0-beta.1-2666d55-win64/MiniJMP.exe | 27776387 | 5FEFD70CA5D54E8CFD0C837C33EEDF24C8E37A5CE06FA8D720E944C02811033D |
| dist/MiniJMP-v0.1.0-beta.1-2666d55-win64.zip | 103010218 | 44F133DF20AB28625203D62F78E3C4292B094528FBEC7D10EFF7E18DD123D431 |
| dist/MiniJMP-v0.1.0-beta.1-2666d55-source.zip | 1427491 | 88EC687F38C2123813464034F3DD60036D5A924A6B67DD1772351A31B63BA9DD |

校验清单：`dist/MiniJMP-v0.1.0-beta.1-2666d55-SHA256SUMS.txt`。

## 构建与验证

- 命令：`& .\tools\build_windows_release.ps1`，退出码 0。复用 `.venv\Scripts\python.exe`（Python 3.11.9 x64）、PyInstaller 6.22.3；42 项版本与锁一致，`pip check` 通过，未安装或更改依赖。
- 保持 `--onedir --windowed --noupx`、ICO 和原入口；ZIP 现在包含完整顶层运行目录。同名产物存在时拒绝覆盖。
- 命令：`& .\.venv\Scripts\python.exe -m pytest tests/test_windows_packaging.py tests/test_startup.py tests/test_worksheets.py tests/test_file_io.py tests/test_table_regressions.py -q`：**215 passed**，64.66 秒。
- 专项覆盖 CSV/Excel 读取和导入、工作表增删复制及多表导入、真实 `.dexpl` 保存重开、表格事件和右键菜单相关行为；这是源码环境测试，不等同于打包 EXE 的 GUI 操作验收。
- `git diff --check` 通过。按 no-stop-gpt Audit 检查实际 diff，无额外业务抽象、缓存或兼容层。
- 临时审计脚本 `build/audit-release-2666d55.py` 成功；两份 ZIP CRC 完整性通过，运行包解压到 `build/release-2666d55-extracted/`。
- 运行 ZIP 2163 项，含 EXE、完整 `_internal`、Python DLL、Tk/Tcl、帮助首页/JSON、默认配置、精选示例、GPL、第三方许可证、BUILD-INFO 和 SOURCE-CODE。
- PE machine 为 0x8664，subsystem 为 2（GUI），含图标资源。
- 从实际 EXE 的 PYZ 提取 MiniJMP、worksheets、modified_table、pandastable_local.core、core_orig、headers、icon_resource 七个模块，其 code object 与 HEAD 源码编译结果逐一相同。确认单元格、行标题、列标题、工作表标签右键菜单代码进入本次 EXE。
- 源码 ZIP 含实际构建脚本、锁、入口、应用源码及许可；检查对应七个模块与当前源码逐字节一致。只收集选定的 Git 跟踪文件。
- 未发现外置 icon.png、PIReader.exe、PIReader 目录、config.txt、开发虚拟环境、Git 历史或运行日志。默认配置只打包受跟踪的 default.conf。
- 从解压目录 EXE 启动，工作目录为系统 TEMP；主窗口和图标可见，无控制台窗口。通过 GUI Alt+F4 正常退出，随后进程检查无 MiniJMP 残留。
- GUI 文件菜单可显示；后续出现 `point ... is over msedge.exe ... not target window` 和 `element ... is not available in cached app state`。恢复前台后仍发生遮挡/状态变化，未完成打包 EXE 的 CSV/Excel 导入、工作表操作、`.dexpl` 保存重开、关于窗口和离线帮助浏览验收；不将专项测试结果当作这些 GUI 项目通过。
- 历史运行 ZIP SHA256 仍为 1DB239AB6D0325EB8BC0FFC70DFBA0286488B3AFB1F5ED22F862589624E268CF；历史源码 ZIP 仍为 923ACBD6259349E596C1A1B9CDACD07FEE5C7D497CE960A1B94C8C41EF8BCFEB。

## 待验收与限制

- 未重复全量回归；构建日志保留 PyInstaller 可选模块扫描警告，未宣称所有统计路径经过打包版验证。
- 仍须在办公电脑执行上述未完成的 GUI 操作，确认 Windows 10/11 x64、未安装 Python、普通用户权限下运行；本机不是无 Python 的干净目标机。
- 企业 Defender/TsdEncrypt 的拦截、离线帮助资源读取、业务数据保存导出及跨电脑读取必须现场验证。本次未修改安全策略。
- 本次报告在产物验证后生成，保留于仓库 docs/release；不属于已经生成的源码 ZIP。
