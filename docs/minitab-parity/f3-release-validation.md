# MiniJMP V1.3.0 Windows 发布验收

## V1.3.0 最终候选（2026-11-26）

- 产品 v1.3.0，软件显示 V1.3.0，Windows EXE 文件版本 1.3.0.0，PIReader 独立版本 1.0.0.0。关于窗口的更新月份改为 2026 年 11 月。
- 维护者确认 PI-Data-Viewer、Python 适配器、PIReader C# 程序及编译产物均为自研，纳入 MiniJMP GPL v3，无须另行取得第三方授权。固定 PIReader 历史构建记录不足不阻塞本次发布，继续复用现有文件。公开包排除三个 OSIsoft/AVEVA 专有 SDK DLL。
- 复用此前通过的定向测试及 F3-2、F3-3 结果。实际 EXE 代表性操作通过后，为最终候选的构建源码提交创建本地 annotated tag v1.3.0。

## 历史候选 V1.3.0-ea0af89（2026-11-26）

以下记录保留该候选构建时的状态。

- 产品版本 v1.3.0，软件显示 V1.3.0，Windows EXE 文件版本 1.3.0.0。PIReader 保持独立版本 1.0.0.0。
- 构建命令为 `./tools/build_windows_release.ps1 -UnreleasedCandidate -PlotlyPilot`。实际源码提交、版本和摘要以该次候选的 BUILD-INFO、SOURCE-BUNDLE-INFO 和 SHA256SUMS 为准。
- Hoeffding D 依据数学定义重新实现。旧测试快照中的复制片段也已替换为直接按观测对计算的整数权重参考。定向检查涵盖并列秩、常数、非有限值、最小样本边界、正反完全顺序与报告。Hmisc p 值移植与固定的 5.1-3 源码匹配，历史取用版本未确认。
- 正式发布待取得 PI-Data-Viewer 适配器的权属及分发依据，以及固定 PIReader 的对应源码和构建关系。PIReader 的版本、摘要和 Git 字节来源已登记，详见 [源码来源](../release/SOURCE-PROVENANCE.md)。
- 实际 EXE 交互验收以当前候选为准。历史 EXE 的启动证据见下方。通过实际交互及来源核查后再创建本地 annotated tag v1.3.0。
- F3-2、F3-3 沿用阶段报告及原功能覆盖矩阵。本轮仅执行相关定向检查。

### 历史候选构建证据

- 干净源码提交为 ea0af89af007b757860c8eafe64178754a3f25ba。候选名 V1.3.0-ea0af89。输出复制到 D:\Download\MiniJMP-v1.3.0-candidate-ea0af89，并从该目录重新计算 ZIP 摘要。
- 使用项目 .venv 的 Python 3.11.9、PyInstaller 6.22.3，在 Windows 11 x64 26300 构建。构建日志和打包清单位于 docs/release 下，文件名包含 V1.3.0-ea0af89。现有环境的依赖版本与锁文件匹配，缺少其历史 wheel 安装摘要。
- 23 项 Hoeffding、报告和版本定向测试及 41 项公开包校验器测试通过。Hmisc p 值查表的 86 项与固定上游逐项一致。运行包 2,281 项、源码包 1,051 项，SBOM 366 个组件。公开包校验和 ZIP CRC 通过；两个 ZIP 的版本及源码提交一致，均无三个专有 SDK DLL。
- Windows 文件资源实测为 1.3.0.0 / v1.3.0。独立解压目录启动在 3 秒内识别到主窗口。通过桌面截图点击“帮助 → 关于”，实屏确认 V1.3.0 及中文说明；关于正文的更新日期仍显示 2026 年 10 月。
- 当前桌面工具可以列出主窗口并截图，但无法可靠地向“关于”子窗口发送关闭操作。辅助功能点击缺少坐标，弹窗关闭按钮超出主窗口的输入范围，键盘关闭也未奏效。中文帮助正文、导入、分析、图形、工程恢复及导出仍待手工验收。
- 本地 PIReader/bin 与 obj 中的实验构建摘要和固定 EXE 不同。三个参考 DLL 在本机存在，缺少能确认此次重建与后续公开分发范围的授权依据，且没有关联固定摘要的 PI Server 现场记录。候选继续复用现有固定输入。

| 资产 | 文件名 | 字节 | SHA-256 |
| --- | --- | ---: | --- |
| Windows x64 便携包 | MiniJMP-V1.3.0-ea0af89-Windows-x64-portable.zip | 130,742,360 | B43C2F02E915A8C63864F5C51B35624DBA66F3C51A7E349051868BA322197988 |
| 对应源码包 | MiniJMP-V1.3.0-ea0af89-Source.zip | 17,898,668 | D4784091703D6B3FD61BF0B42F30C8E56AA9DB742737F1A0223701A0B1048A99 |

## 实际 EXE 手工验收步骤

1. 解压候选 ZIP 至独立可写目录，启动 MiniJMP.exe。打开“帮助 → 关于”核对 V1.3.0 与 2026 年 11 月，再通过 F1 打开中文离线帮助。
2. 在同一工程导入仓库中的 `sample_data/coatings.csv` 与 `sample_data/Gasket.xlsx`，核对列名、行数和工作表，编辑一个数值并验证撤销与重做。
3. 用有足够数据行和数值列的工作表各做一次描述性统计、线性回归、PCA、过程能力及控制图。记录成功生成的报告或图形。
4. 在该工程新建两因子两水平全因子 DOE，填入非恒定响应，运行对应分析并查看结果。使用同一数据各生成一个 Matplotlib 图和 Plotly 试验图，确认 Plotly 窗口实际呈现且可交互。
5. 保存为新的 .dexpl，退出程序，从同一 EXE 重新启动并打开工程。确认编辑后的数据、DOE 表、历史报告和图形可从分析导航打开。
6. 导出 XLSX、PNG 和 PDF，逐个打开检查内容。记录候选提交、每项通过或失败、有问题时的错误和截图。

## 历史候选 V1.2.2.3-a949db2

以下为上一候选的历史记录，范围和结论均对应旧包。

## 版本与构建

- 产品版本保持 `v1.2.2.3`，本地候选标识为 `V1.2.2.3-a949db2`。构建源码提交：`a949db23e49c8ccf25e738c5ebe1a0beb95cc567`。本机现有 `v1.2.2.3` 标签仍指向旧提交 `06e459350acfeb6695cd1ccca3cc76781276c5f9`；未改动该标签，也未创建新标签。
- 环境：Windows 11 专业版 x64（build 26300）、项目 `.venv` Python 3.11.9、Tk/Tcl 8.6、PyInstaller 6.22.3。锁定核心版本为 NumPy 2.4.6、SciPy 1.15.3、pandas 3.0.6、statsmodels 0.15.0、Matplotlib 3.11.2、pyarrow 23.0.1、openpyxl 3.1.5、xlrd 2.0.2；Plotly 7.1.0、tkwry 0.1.9。锁定依赖版本匹配，`pip check` 通过。现有环境缺少 pip 哈希安装报告，因此不能证明原安装 wheel 的 SHA-256 来源。
- 构建命令：`.\tools\build_windows_release.ps1 -UnreleasedCandidate -PlotlyPilot`。构建时工作区干净；PyInstaller 为 `onedir`，Plotly 7.1.0 与 tkwry 0.1.9 已收集。
- 构建日志与输入清单：`docs/release/pyinstaller-build-V1.2.2.3-a949db2.txt`、`docs/release/build-inputs-V1.2.2.3-a949db2.txt`。

| 资产 | 路径 | 大小 | SHA-256 |
| --- | --- | ---: | --- |
| Windows x64 便携候选包 | `D:\Download\MiniJMP-v1.2.2.3-candidate-a949db2\MiniJMP-V1.2.2.3-a949db2-Windows-x64-portable.zip` | 130,752,719 字节（124.70 MiB） | `308E042B39B0E9CA790AFCDD324A3C66B9F0AA3907B071190D9ABEF0C34700FF` |
| 对应源码包 | `D:\Download\MiniJMP-v1.2.2.3-candidate-a949db2\MiniJMP-V1.2.2.3-a949db2-Source.zip` | 17,898,636 字节（17.07 MiB） | `66561827C021A7D3126C8BD279ED21AD25F307CAC614BE839C135152BD897F0E` |

## 验收结果

- 构建脚本在构建目录和临时解压目录启动 EXE 均通过。另从上述 `D:\Download` 独立解压目录运行 `tools/smoke_launch.py`，3 秒内识别到 MiniJMP 窗口；未依赖源码目录或项目 `.venv`。
- `release_metadata.py` 版本检查通过，产品版本、About 源码标识和 EXE 文件版本资源仍对应 `v1.2.2.3 / V1.2.2.3 / 1.2.2.3`。离线帮助索引与页面已打入包内；因桌面控制失败，About 和帮助窗口未实屏检查。
- 公开包验证通过：运行 ZIP 2,281 个文件、CRC 正常、EXE 版本与构建信息一致、SBOM 记录 367 个组件；含 `LICENSE`、`THIRD-PARTY-NOTICES.txt`、114 个第三方许可证文件、中文帮助页及帮助索引。EXE 归档检查确认含 openpyxl、xlrd、pyarrow.parquet、NumPy、SciPy、pandas、statsmodels、Matplotlib、Plotly、tkwry 模块，且包含 Tcl/Tk 和 Matplotlib 字体资源。未发现 `tests/`、缓存、`.pyc`、临时日志或签名密钥；保留项目随包示例工程及 Matplotlib 自带样例资源。
- 代表性工作表编辑、CSV/Excel 导入、统计、回归、PCA、Cpk/SPC、DOE、Matplotlib/Plotly 操作、工程保存重开、结果导出、帮助/关于窗口**没有在该 EXE 中完成交互验收**。Computer Use 在读取桌面和启动窗口时持续返回 `GetCursorPos failed: Access denied (0x80070005)`；外部目录启动冒烟通过不等同于这些功能流程通过。大文件导入也未在该 EXE 中复测。
- Plotly 和 tkwry 已进入包；本机检测到 Microsoft Edge WebView2 Runtime 158.0.4370.33。候选包不捆绑该运行时，目标机仍须安装兼容版本。因桌面控制失败，Plotly 窗口仍未在 EXE 中实测。

## 复用证据与限制

- 复用 [F3-2 数值验收](f3-2-numeric-validation.md)中的独立参考、DOE 固定案例及既有缺陷修复；本轮未重复 Minitab 对标或全量 pytest。
- 复用 [F3-3 性能稳定性验收](f3-3-performance-stability.md)：461 passed、3 skipped，及 15 项跨包联测、工程往返和资源生命周期结果。3 项跳过均为缺少可选 `numexpr` 的一个参数化集成测试，原因已在 F3-3 报告注明。
- 保留 F3-3 已记录的限制：Excel 100k × 20 导入约 26 秒、250k 散点同步首帧约 0.73 秒、接近 1 GiB 工程及多小时运行未验收。覆盖矩阵仍为 151 已实现、9 部分实现、4 未实现、1 待核实，共 165 条有效功能记录；不据此宣称全面兼容 Minitab。

## 本轮修复与许可证核查

- 增加 `-UnreleasedCandidate`，允许在不改产品版本、不挪动旧标签的前提下，以当前提交短 SHA 构建可复现候选包；BUILD-INFO 和 SBOM 明确标为未发布。首个试构建的第三方声明误写“由 GitHub Actions 自动构建”，已修正并从 `a949db2` 重建。首个 `aee9753` 产物已被本候选替代，请勿分发首个产物。
- 运行包和源码包均含完整 GPL v3 文本；README、关于信息、发布说明保留原作者及二次开发说明，源码归档保留源码、依赖锁和构建材料。公开候选包未包含三个 OSIsoft/AVEVA 专有 PI SDK DLL；PI 数据功能仍要求目标机合法安装匹配的 PI SDK/PIPC 并有服务器权限。
- 原始 MiniJMP 仓库标注 GPL-3.0；CRAN 的 Hmisc 元数据列为 GPL-2/GPL-3。[原始项目](https://github.com/garrydu/Minijmp) · [CRAN Hmisc](https://cran.r-project.org/web/packages/Hmisc/index.html)
- **许可证尚未完成正式放行。** 项目来源记录仍将 `code/nonpara_cor.py::hoeffd_example` 的 README 复制片段标为授权未确认，并将 `code/pi_reader.py` 的 PI-Data-Viewer adapter 独立许可标为待核实；Hmisc 移植版本也未记录。详见 [源码来源与许可记录](../release/SOURCE-PROVENANCE.md)。包内列出这些状态并不构成授权。固定 PIReader 二进制有版本和 SHA-256，但现有记录未将它绑定到明确源码提交。

## 最终状态

- 候选包对应源码提交 `a949db23e49c8ccf25e738c5ebe1a0beb95cc567`；后续验收文档和构建记录提交不修改该包的运行时代码。最终仓库提交后，`main` 工作区干净且未推送；本轮未创建正式版本标签。
- **不具备正式发布条件。** 候选包构建、内容校验和脱离源码目录启动已通过；桌面交互验收受 `0x80070005` 阻断，且上述第三方源码授权尚未确认。
