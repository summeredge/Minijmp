# F3-4/F3-5 Windows 候选包验收

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
