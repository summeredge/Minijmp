# MiniJMP Windows Beta 发布准备检查（2026-10-23）

> **后续修订（2026-10-25）**：本节之后的 2026-10-23 检查结果保留原样，仅作历史记录。
> 发布工具链已按办公环境最终方案同步：Python 需要 3.11 及以上、PIReader 与
> config.txt 随包分发、ZIP 改由 `tools/make_zip.py` 生成、加入 `tools/smoke_launch.py`
> 与 TsdEncrypt 沉降复验。工作区不再是构建门禁，只输出 WARNING。
> 当前规则与验收步骤见仓库根的 `PACKAGING.md` 和
> `docs/release/windows-enterprise-packaging-alignment.md`。

本报告只覆盖发布前的代码、脚本、资源与许可准备。**未执行 PyInstaller，未生成 EXE，未生成任何 ZIP，未运行全项目 pytest，未提交或推送 Git。**

## 1. 发布准备状态

| 项目 | 状态 | 依据 |
|---|---|---|
| Git HEAD | PASS | `8f84dfbd8be9c05664fa4d1488ac788d8b432e00`，分支 `main`，与 `origin/main` 一致 |
| 工作区状态 | BLOCKED | 450 个已跟踪文件被删除且未暂存：`docs/quality-tools-evidence/` 243 项、`quality-evidence/` 201 项、`docs/review-*.md` 6 项；开始时无未跟踪文件，`git diff --check` 通过，无换行符整体改写 |
| 发布脚本加固 | PASS | 干净工作区门禁、构建输入纳入 Git 校验、版本号一致性校验已加入 `tools/build_windows_release.ps1` |
| 构建环境 | PASS | 项目 `.venv`：Python 3.11.9（64 位）、PyInstaller 6.22.3、`requirements-py311.lock` 全部一致、`python -m pip check` 通过 |
| 源码清单 | PASS | 清单内 20 个路径全部存在且已纳入版本管理（319 个已跟踪文件，含 `packaging/windows/licenses/` 两份图标许可原文） |
| 许可证准备 | PASS | `LICENSE` 为 GPLv3 全文；“关于”窗口保留 `Copyright (C) G.Du 2024-` 与二次开发说明；`tools/write_third_party_notices.py` 仍按运行依赖闭包收集原件，覆盖 formulaic、interface-meta、narwhals、wrapt、et_xmlfile；解释器自带 `LICENSE.txt` 与 `tcl/tk8.6/license.terms` 存在，可被声明脚本收录 |
| 正式构建 | BLOCKED | 由工作区状态决定；预检查输出 `BLOCKED: Git 工作区尚未整理，正式构建前需要完成版本归档（450 项未提交或未跟踪变更）。` |

## 2. 修改与验证

修改文件：

- `tools/build_windows_release.ps1`
  - 在任何目录创建、清理或构建命令之前拒绝脏工作区（`git status --porcelain --untracked-files=normal` 非空即报错，含已暂存、未暂存和未跟踪变更）。
  - `$sourcePaths` 与两份图标许可必须已纳入 Git，否则直接报错，避免 `git ls-files` 静默漏收构建输入。
  - `version_info.txt` 必须声明脚本中的 `$version`，防止 EXE 版本属性与包名／源码 ZIP 版本漂移。
  - `BUILD-INFO.txt`／`SOURCE-BUNDLE-INFO.txt` 由“来自工作区”改为“与 Git HEAD 一致”。
- `tools/check_windows_release_ready.ps1`（新增，只读预检查）
  - 检查工作区状态、分支与 `origin/main` 基准、Python/PyInstaller/锁定依赖、必要资源与许可证路径、源码清单是否纳入 Git、版本号一致性；输出 `PASS`／`BLOCKED`／`WARNING`，存在阻断时退出码 1。
  - 不含构建、删除、压缩、复制、安装依赖或 Git 写操作；`-GitOnly` 仅用于隔离仓库测试。
- `tests/test_windows_packaging.py`
  - 更新 `BUILD-INFO` 文本断言；新增脚本门禁静态断言（含门禁位于 `build` 目录创建与 `Remove-GeneratedPath` 之前）。
  - 新增预检查行为测试：临时 Git 仓库（含裸远端）干净时 `RESULT: PASS`、退出码 0；加入未跟踪文件或修改已跟踪文件后 `RESULT: BLOCKED`、退出码 1。
- `docs/release/windows-beta-readiness-20261023.md`（本报告）。
- 版本标识由 `v0.1.0-beta.1` 升为 `v0.1.0-beta.2`：`tools/build_windows_release.ps1`、`packaging/windows/version_info.txt`（含 `filevers`/`prodvers` 0.1.0.2 与 `Comments`）、`packaging/windows/USAGE.txt`、`README.md`、`code/modified_app.py` 的“关于”窗口版本标签、`CHANGES`。

定向验证（解释器 `.venv/Scripts/python.exe`）：

- `python -m pytest tests/test_windows_packaging.py -q -p no:cacheprovider --tb=short` → **16 passed**（原 14 项 + 新增 2 项），退出码 0。
- PowerShell 语法检查：`[Parser]::ParseFile` 对两个脚本均无错误。
- 当前仓库预检查实跑：`PASS` 分支、HEAD 基准、Python 3.11.9/64 位、锁文件一致、`pip check`、PyInstaller 6.22.3、资源与许可路径、源码清单、版本一致性；`BLOCKED` 仅来自工作区删除项；退出码 1。
- 发布脚本门禁隔离验证（临时目录 + 桩 `git`，未触碰本仓库）：脏状态在创建 `build`／`dist` 前抛出 `Refusing to build from a dirty working tree (1 entries)`；干净状态通过 Git 与版本校验后停于环境检查 `Project Python 3.11 environment not found`，两例均未生成 `build` 或 `dist`。临时目录已删除。
- `git diff --check` 通过；本次改动为 2 个修改文件、1 个新增工具、1 份报告，无统计计算、GUI 业务逻辑或依赖变更。

## 3. 尚待处理的发布前条件

- 完成 450 项删除的版本归档（提交删除或在需要时恢复文件），使工作区变为干净状态；未跟踪的 `tools/check_windows_release_ready.ps1` 与两个修改文件同样需要版本归档。未执行任何 `git add`、提交或推送。
- `docs/quality-tools-extension.md` 第 107 行仍链接 `docs/quality-tools-evidence/` 证据目录，该目录已随本轮删除消失；需随归档决定一并修订或恢复。
- 发布脚本会把 PyInstaller 日志写入 `docs/release/pyinstaller-build-<sha>.txt`；该文件在构建后成为未跟踪文件，会阻断下一次正式构建。发布流程需在构建后提交既有日志或明确移除。
- 正式构建仍须在 Windows x64、Python 3.11.9 与 PyInstaller 6.22.3 的锁定环境实际执行，产物内容、ZIP 完整性、签名与 GUI 验收均未验证。
