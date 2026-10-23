# MiniJMP — 开源统计分析软件（二次开发版）

> 本仓库基于原作者 G.Du 发布的 [Minijmp](https://github.com/garrydu/Minijmp) 开源项目进行二次开发，并非原作者的官方发布版本。

![原项目主界面截图](docs/images/main.png)

MiniJMP 是使用 Python 开发的桌面统计分析软件，提供电子表格工作区、统计检验、回归分析、过程质量工具和数据可视化。原项目借鉴了 Minitab Express 与 JMP 的部分功能；本版本主要扩展高级统计、中文界面、绘图、工业 PI 数据导入及 Windows 使用体验。

**当前版本标识：** `v0.1.0-beta.1`。本文根据本仓库 **2026 年 10 月**的源码整理；截图可能来自原项目，具体界面以当前版本为准。

## 原始项目、版权与许可证

- **原始项目：** [garrydu/Minijmp](https://github.com/garrydu/Minijmp)，作者 **G.Du**，保留原始署名 `Copyright (C) G.Du 2024-`。
- **基础表格组件：** [PandasTable](https://github.com/dmnfarrell/pandastable) / DataExplore，作者 **Damien Farrell**，保留适用的上游版权与许可信息（程序“关于”页注明 `Copyright (C) Damien Farrell 2014-`）。
- **二次开发项目：** [summeredge/Minijmp](https://github.com/summeredge/Minijmp)。本仓库自 2026 年 10 月起对界面、统计模块、数据操作、绘图和工业数据接入进行修改；这些变更由本仓库维护者负责，不代表原作者为其结果背书。
- **许可协议：** 本项目延续 **GNU GPL v3** 开源许可，完整文本见 [LICENSE](LICENSE)。分发修改版时，应保留适用的原版权及第三方声明、标明修改，并遵守 GPL 对许可证及相应源代码提供的要求。

软件按“现状”提供，不提供任何明示或默示担保。Minitab、JMP 是各自权利人的产品或商标，本项目与其官方厂商无隶属关系。

## 功能概览

### 原项目核心功能

- 多工作表编辑、CSV/Excel 数据处理、变换与图表展示。
- 描述性统计、分布拟合、相关性、t/Z 检验、ANOVA、列联表与卡方检验。
- 线性和正交回归、量具 R&R、Cpk 及常用控制图。

### 本仓库新增与增强的主要功能

| 模块 | 已实现功能 |
| --- | --- |
| 中文界面与交互 | 中文菜单、可搜索的离线中文帮助/F1；常用分析和绘图的列选择记忆；右键表格与工作表操作增强。 |
| 高级回归 | OLS、WLS、二元 Logistic、非线性回归、变量筛选、诊断与预测；新增 Poisson、名义多分类 Logistic、有序 Logistic/Probit 和单/多响应 PLS。 |
| PCA | 主成分得分与载荷、解释方差、Hotelling T²、Q/SPE、变量贡献、模型保存与新样本投影。 |
| 时间序列 | ACF/PACF/CCF、趋势和季节分解、ADF/KPSS、ARIMA/SARIMA 建模与预测。 |
| 过程能力 | 正态及非正态能力分析、Box-Cox/Johnson 变换、正态/非正态 Sixpack。 |
| 高级 SPC | EWMA、CUSUM、Nelson 八规则、多变量 Hotelling T²；保留原有 I-MR、Xbar-R/S、NP/P/C/U 等控制图。 |
| 质量工具 | 帕累托图、运行图、因果（鱼骨）图、多变异图、属性一致性分析。 |
| 绘图 | “通用绘图器”和独立图形入口；扩展条形、区域、矩阵、等值线、三维散点/曲面、气泡、边际、ECDF、区间、概率图等。 |
| 工业数据 | 配合外部 PIReader/PI SDK，通过 Tag 或 Tag Mask 查询 PI 历史数据并导入当前工作表。 |
| 数据与部署 | 改进 CSV/Excel 结果导出、覆盖失败时的文件保护；提供 Windows 64 位 PyInstaller `onedir` 构建方案及内嵌图标。 |

不同软件的算法选择、统计默认值及适用条件可能存在差异；以上功能不表示与 Minitab/JMP 的所有选项或数值逐项一致。部分统计方法具有近似性或特定前提，请阅读对应帮助。

## 安装与运行

### 从源码运行（推荐开发方式）

建议使用 **Windows 64 位和 Python 3.11**；本仓库当前部分专项验证使用 Python 3.11.9。原项目涉及 Linux/macOS，但该二次开发版尚未宣称完成跨平台等效验证。

在项目根目录打开 PowerShell：

~~~powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe start.py
~~~

已有 `.venv` 时无需重复创建，依赖以 [requirements.txt](requirements.txt) 为准。

### Windows 打包程序

仓库提供 [Windows 构建脚本](tools/build_windows_release.ps1) 和锁定依赖文件，采用 PyInstaller **`onedir` 目录模式**。这代表具备构建方案，并不保证每次源码修改都有经过验收的 EXE 发布包。使用打包版本时应完整解压压缩包，保留 `MiniJMP.exe` 及 `_internal` 等依赖文件夹。

企业 Defender、透明加密及其他安全策略可能影响启动或导出，需要在目标终端单独验证。

## PI 历史数据导入（可选）

使用 **文件 → 导入 PI 数据**。需配置可执行的 `PIReader.exe`、`config.txt`、本机 **PI SDK** 以及服务器访问权限；PI SDK 不随本软件分发。可输入 Tag/Mask、历史时间范围及采样间隔。成功导入后会替换当前工作表，请预先保存需要保留的数据。

详细操作、约束与错误处理见 [PI 数据导入文档](docs/PI-data-import.md)。普通统计功能不依赖 PI SDK。

## 帮助与技术文档

- [离线中文帮助](help/index.html)（在软件中按 F1 打开）
- [高级统计分析（回归、PCA、时间序列、SPC）](docs/advanced-statistics.md)
- [扩展回归模型与统计约定](docs/REGRESSION_EXTENSIONS.md)
- [完整过程能力分析](docs/capability-analysis.md)
- [质量工具扩展](docs/quality-tools-extension.md)
- [数据列预选与记忆](docs/column-selection-memory.md)
- [原项目在线文档](https://minijmp.readthedocs.io/)（可能未覆盖本二次开发版）

![原项目菜单截图（仅供参考）](docs/images/menu.gif)

## 开发工具与致谢

本软件使用 **Python**，结合 Tkinter、pandas、NumPy、SciPy、statsmodels、Matplotlib、Seaborn 等库开发。部分代码分析、功能实现、调试、测试和文档维护使用 **ChatGPT、Codex** 等 AI 辅助工具，所有修改由项目维护者审查、整合并决定是否采用。

感谢 **G.Du** 开源 Minijmp，以及 **Damien Farrell** 开源 PandasTable/DataExplore。原项目与第三方组件的版权归各自权利人所有。

---

**[GNU GPL v3 许可](LICENSE)** · **[原始项目](https://github.com/garrydu/Minijmp)** · **[当前二次开发仓库](https://github.com/summeredge/Minijmp)**

