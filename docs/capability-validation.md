# P0 过程能力分析验收记录

日期：2026-10-23。工作区：`C:\Users\shaoy\Documents\Minijmp`。

## 本次范围与文件

- 新增 `code/capability.py`：独立过程能力核心、三种正域分布 MLE、重新拟合的参数自举、Box-Cox/Johnson SU 及诊断数值表。
- 新增 `code/capability_dialog.py`：来源快照、后台计算/取消、结果表、报告、CSV/Excel、新工作表及仅作用于能力图窗的标准坐标导航。
- 新增 `code/capability_plots.py`：正态/非正态 Sixpack、变换前后四图、逐点控制限诊断。
- `code/MiniJMP.py` 仅在本任务范围内加入质量菜单和统一入口，保留原有回归扩展改动。
- 新增 `tests/test_capability.py`、`tests/test_capability_plots.py`、`tests/test_capability_dialog.py`；同步菜单/帮助测试及 `tests/fixtures/g12_table_inventory.json` 的文件、生产位置、逻辑表标题审查。
- 新增 `help/pages/capability-analysis.html`、`docs/capability-analysis.md`；同步 `help/help-map.json`、`help/assets/search-index.js`、`docs/MENU_TRANSLATION.md`。

开始时工作区已有回归扩展的未提交源码、测试、清单和文档。本任务未撤销这些改动，未修改旧 `cpk.py`、`cpk_plot.py`、`qc_dialog.py`、`control_chart.py` 或其历史冻结夹具，保留 GPLv3 文件与原作者署名。没有增加依赖，没有创建提交或推送，没有实施下一阶段质量工具。

## 环境与命令

使用项目已有解释器，未使用 Codex bundled runtime，也未安装/升级依赖：

```powershell
$python = 'C:\Users\shaoy\Documents\Minijmp\.venv\Scripts\python.exe'
& $python -c "import sys,scipy,pandas;print(sys.executable,sys.version,scipy.__version__,pandas.__version__)"
```

实际版本：Python 3.11.9、SciPy 1.15.3、pandas 3.0.6。GUI 为真实 Windows Tk，非 mock 渲染；菜单调用使用真实 Tk `Menu.invoke()`，计算使用后台线程。根目录不存在 `DESIGN.md`，窗口沿用项目原生 Tk/ttk 及 `StatTable`、`SheetApp`、`PlotViewer`。

| 实际命令（省略同一 `$python` 前缀） | 结果 | 说明 |
| --- | --- | --- |
| `-m pytest tests/test_capability_dialog.py tests/test_capability.py tests/test_capability_plots.py -q --tb=short --basetemp "$env:TEMP\minijmp-capability-final"` | 83 passed，24.59s | 核心46、图形25、GUI12；此后只补能力图窗导航与表格伸缩，相关GUI另外重跑 |
| `-m pytest tests/test_capability_dialog.py -q --tb=short --basetemp "$env:TEMP\minijmp-capability-final-gui"` | 12 passed，20.46s | 最终GUI：真实鼠标框选缩放、复位与现有 `savePlot` 保存入口；核心/绘图算法未再修改 |
| `tools/build_help_index.py` | 成功 | 根据最终帮助正文生成离线索引 |
| `-m pytest tests/test_menu_localization.py tests/test_help_center.py tests/test_g12_inventory.py -q --tb=short` | 85 passed，14.60s | 菜单顺序、翻译、帮助映射/链接/索引与报告清单 |
| `-m pytest tests/test_capability_plots.py tests/test_windows_packaging.py tests/test_g3_computation_contracts.py -q --tb=short` | 59 passed，7.17s | 当时图形为23项；该组合在 Tk 预初始化后运行，包含旧 Cpk 等计算 AST 契约及打包静态测试，不与83项重复累加 |
| `-m pytest tests/test_g5_spc_reports.py -q --tb=short` | 73 passed，6.75s | Tk 预初始化后运行，旧 SPC 数值/报告/真实对话框 |
| `-m pytest tests/test_regression_dialog.py -q --tb=short` | 16 passed，19.73s | 既有完整回归及广义回归/PLS GUI |
| `-m pytest tests/test_pca_dialog.py tests/test_time_series_analysis_dialog.py -q --tb=short` | 8 passed，13.26s | 既有 PCA 与时间序列 GUI |
| `-m pytest tests/test_statistics_regressions.py tests/test_statistical_edges.py -q --tb=short` | 75 passed，7 warnings，4.72s | 既有统计回归；警告来自常量数据的 Shapiro/AD 和绘图退化尺度 |
| `git diff --check` | 成功 | 仅报告原有文件的 LF/CRLF 提示，无 whitespace error |

上述是分组执行结果，没有将重复运行的测试累加成唯一测试总数，也没有把错误或未执行项计为通过。最终方法与边界对应关系见 [逐方法独立参考](capability-analysis.md#逐方法独立证据矩阵)。

旧 SPC 与打包组合最初在延后初始化 Tk 时出现 Tcl 文件读取错误（113 passed、19 errors），单独复跑 SPC 仍为54 passed、19 errors；解释器、Tcl文件存在且直接初始化 Tk 成功。未修改项目环境，通过在 pytest 收集前初始化 Tk 后，相关组分别全部通过。一次预初始化后再组合运行回归/PCA/时间序列的尝试发生 Windows `0x80000003`，没有将其记为通过；这些功能分开执行后通过。可复现的预初始化命令形式：

```powershell
& $python -c "import tkinter as tk; r=tk.Tk(); r.withdraw(); import pytest; raise SystemExit(pytest.main(['tests/test_g5_spc_reports.py','-q','--tb=short']))"
```

开发联测曾因把来源索引的文本保护误写成数值 dtype 预期而失败，修正了本任务新增测试的预期；保留既有 `export_source_labels` 行为。坐标导航测试初次构造 Matplotlib motion event 时未设置 `buttons={1}`，标准导航按失去鼠标按键取消缩放；修正事件构造后验证真实框选及复位，没有绕开缩放结果断言。

## 实际 GUI 与文件证据

最终 GUI 验证包括五个质量菜单、单/双侧规格、无目标、90%置信水平、K=5、固定大小与子组ID、三种非正态分布、Box-Cox及Johnson SU、取消后保留结果、来源表关闭报错、切换/修改活动表后继续使用原快照。窗口在760×580仍可操作，结果区随宽度伸缩，长表可滚动。

图形与报告均发布至来源工作表。CSV/XLSX重读检查数值精度，并保留带18位前导零的来源索引；新工作表输出与原始工作表隔离。缩放测试发送真实 Matplotlib 鼠标按下/移动/释放事件，检查坐标范围缩小，复位恢复；PNG通过已有图窗保存入口生成并由Pillow重读。

- [结果窗口截图](evidence/capability-p0/result-dialog.png)
- [正态 Sixpack](evidence/capability-p0/normal-sixpack.png)
- [非正态 Sixpack](evidence/capability-p0/nonnormal-sixpack.png)
- [Box-Cox 原始/变换后四图](evidence/capability-p0/boxcox.png)
- [来源观测 CSV](evidence/capability-p0/observations.csv)、[来源观测 Excel](evidence/capability-p0/observations.xlsx)

样本是固定种子生成的合成数据，正态模型失配或超控制限警告在截图中保留，不能将图中能力值当作真实生产验收结论。截图和PNG已打开核对归属及面板内容。

## 适用范围与未验证项

- 非正态主指数为百分位法，另列等价Z；与Minitab默认Z-score法不同。Johnson只支持SU MLE，非SB/SL/SU全族Chou选择；Box-Cox剖面似然/未舍入λ与Minitab子组优化有差异。
- 非正态拟合KS采用199次重新拟合的参数自举，有模拟误差。变换选参后的正态AD只用于诊断，不能当独立正常性证明；不合格变换明确失败。
- 当前提供适用的标准差、Cp/Pp及整体Ppl/Ppu区间；其余能力区间、变换后/非正态区间和PPM区间未提供，报告NA。Q-Q没有概率置信带。
- 非正态I控制限使用0.135%/99.865%拟合分位；MR及非正态子组图采用已披露的正态常数近似，仅标记超控制限点，没有声称执行全部Nelson/Western Electric规则。控制限不是规格限。
- 没有执行全量pytest或完整PyInstaller构建，没有验证打包exe的无管理员启动；`test_windows_packaging.py`只验证onedir配置、静态入口、资源及可写目录等。新源码的导入链可被现有PyInstaller分析，未新增运行时依赖。现有源码ZIP脚本基于`git ls-files`，发布前必须保证新增文件已进入源码归档；本任务按要求保留未提交状态。
- 只验证当前Windows字体/DPI和最小窗口尺寸，没有宣称覆盖全部缩放比例或与商业Minitab逐值、逐像素完全相同。

复杂度审查采用no-stop-gpt Audit：保留直接SciPy拟合与单一结果字典；复用现有表格/来源适配/图窗，删掉五个多余菜单转发方法。后台Future、取消Event和深拷贝分别对应计算状态、迟到结果丢弃及来源快照边界；局部标准导航是现有图窗缺少坐标缩放的必要补充，不引入通用图形编辑器、缓存、兼容层或新依赖。

## 二项属性能力 F2-P0-1

| 生产入口 | 独立参考 | 覆盖范围 |
| --- | --- | --- |
| `capability.analyze_binomial_capability` 的汇总、PPM 和 Process Z | 固定数据手算加权汇总，标准库 NormalDist 反演 | 等长、不等长、全零、全不合格、无穷界 |
| 同入口的 Clopper–Pearson 双侧区间 | 枚举二项概率质量点，验证两尾各等于 α/2；边界用幂方程闭式解 | 90% 一般区间，95% 两端边界；Z 区间反序 |
| 同入口的累计比例 | 固定前缀分别手算 | 原行顺序、不等长按检验数加权 |
| `BinomialCapabilityDialog.fit` | Tk 菜单真实调用与既有 P 图回归 | 当前来源快照、选列、固定样本量、非法计数提示、图和表 |

没有假设检验的 p 值或并列规则。双侧区间等尾，假设检验单位相互独立且具有共同不合格率。P 图沿用现有 3σ 控制限及规则 1–4；规则信号用于检查稳定性，目标达标另行判断。

### Minitab 22 原生命令

2026-11-21 通过独立进程 COM `Mtb.Application` 取得 22.6（文件版本 22.6.0.0）的存储值。输入 C1 为 1、4、2、0，C2 为 20、100、30、50。执行以下命令，使用默认 95% 置信水平。

```text
BCAPA C1 C2;
NOCHART;
PAVERAGE C3;
PALC C4;
PAUC C5;
PPM C6;
PPML C7;
PPMU C8;
ZPROCESS C9;
ZPLC C10;
ZPUC C11.
```

| 指标 | 估计值 | 下限 | 上限 |
| --- | ---: | ---: | ---: |
| 总体不合格率 | 0.035 | 0.0141855258986459 | 0.0707809983509771 |
| PPM | 35000 | 14185.5258986459 | 70780.9983509771 |
| Process Z | 1.81191067274624 | 1.46999910379542 | 2.19211710763098 |

原生案例以相对容差 1e-9 检查。等长及全零、全不合格子组以独立数学参考验收；厂商边界显示、图形和控制规则默认选项尚未逐项对照。MiniJMP 拒绝缺失计数，并保持原分析顺序；Minitab 命令手册描述缺失点留空和其他图跳过的处理。历史不合格率、目标、直方图及样本量诊断图留在本轮范围外。[Minitab 命令与存储字段](https://support.minitab.com/en-us/minitab/session-command-help/)

相关回归命令为 `python -m pytest tests/test_binomial_capability.py tests/test_help_center.py tests/test_g12_inventory.py tests/test_menu_localization.py tests/test_g5_spc_reports.py tests/test_review_proportions.py tests/test_capability.py -k "not computation_plotting_ast_matches_frozen_structure" -q`，使用项目 Python 3.12.3，共 299 项通过。此前直接运行时，8 项 G5 旧 AST 冻结比较失败；对本任务开始前的 0eadb8a 源码和冻结夹具复算，得到同样的 8 项差异。本轮仅在通过的定向命令中排除这些已复现的既有失败，冻结基线、SPC 实现与原比率检验均未修改。

## 泊松属性能力 F2-P0-2（2026-11-23）

「质量 → 泊松过程能力」以来源工作表快照为输入，每行一个子组。总体 DPU 使用总缺陷数除以总暴露量。暴露量可用统一的长度、面积、时间或件数单位。目标差值取 Mean DPU 减去目标，仅作描述性比较。缺失、非法计数和非法暴露量须先修正。

总缺陷数为 D、总暴露量为 N 时，双侧等尾区间下限为 `χ²(α/2, 2D)/(2N)`，上限为 `χ²(1−α/2, 2D+2)/(2N)`。D 为零时下限取零，上限为 `−log(α/2)/N`。区间依赖独立子组和共同泊松缺陷率。诊断及目标比较无正式检验、p 值或并列规则。

| 生产入口 | 独立验证及实际覆盖 |
| --- | --- |
| `analyze_poisson_capability` | `test_poisson_reference` 用固定前缀手算总体及累计率、最小最大值和目标差，并独立求和验证区间两尾各为 0.05。等长和不等长均通过，含缺陷数超过暴露量和正小数暴露量。 |
| 同统计入口的边界 | `test_zero_defects` 用闭式解验证正上限，覆盖单组及多组全零。非零单组、负数/小数计数、非法暴露量、不等列长、缺失和非有限值均通过。 |
| `plot_poisson_capability` | `test_plot_values_and_diagnostics` 独立核对逐组 3σ 控制限、U 图信号、累计图顺序，以及拟合累计概率的零点 `exp(−8)` 和不等长 DPU 散点。规则 1–4 沿用既有 SPC 路径。 |
| `PoissonCapabilityDialog.fit` | `test_poisson_menu_workflow` 在真实 Windows Tk 从菜单打开并选列，切表和改变源表后仍使用原快照，核对汇总及子组表、特殊原因提示、实际显示的 Matplotlib 画布、非法分母及固定小数分母。二项真实 Tk 回归通过。 |

### Minitab 19 原生存储参考

独立 COM `DispatchEx('Mtb.Application')` 返回 `Version=19.1`、`AppPath=D:\Program\Minitab 19\Mtb.exe`，文件版本为 **19.1.0.1**。确认新项目的命令历史为空后用 `SET` 写入 C1 = 1、4、2、0 和 C2 = 20、100、30、50，随后运行以下命令，使用默认 95% 区间。

```text
PCAPA C1 C2;
TARGET 0.04;
NOCHART;
DPU C3;
DPUL C4;
DPUU C5;
DMINIMUM C6;
DMAXIMUM C7;
DTARGET C8.
```

| 存储列 | 指标 | COM 实读值 |
| --- | --- | ---: |
| C3 | Mean DPU | 0.035 |
| C4 | 95% 下限 | 0.014071815257655851 |
| C5 | 95% 上限 | 0.07211337680851168 |
| C6 | 最小 DPU | 0 |
| C7 | 最大 DPU | 0.06666666666666667 |
| C8 | 目标 DPU | 0.04 |

六项均通过 `test_minitab_19_pcapa_fixed_reference` 的相对容差 1e-9 比较。原生取证限于这一组整数暴露量数据及数值存储。零缺陷、小数暴露量和非默认置信水平由独立数学参考验收。保留厂商界面、图形、历史率和选项的对照缺口。等长诊断使用经验/拟合累计概率对照。不含 DPMO 或 S1 泊松率检验。[Minitab 统计量](https://support.minitab.com/en-us/minitab/help-and-how-to/quality-and-process-improvement/capability-analysis/how-to/capability-analysis/poisson-capability-analysis/methods-and-formulas/capability-statistics/) · [Minitab 区间公式](https://support.minitab.com/en-us/minitab/help-and-how-to/quality-and-process-improvement/capability-analysis/how-to/capability-analysis/poisson-capability-analysis/methods-and-formulas/confidence-intervals-and-bounds/) · [PCAPA 命令与存储](https://support.minitab.com/en-us/minitab/media/pdfs/notranslate/session_commands.pdf)

### 回归结果

项目 `.venv\Scripts\python.exe`（Python 3.11.9、SciPy 1.15.3、pandas 3.0.6）运行：

```powershell
& $python tools/build_help_index.py
& $python -m pytest tests/test_poisson_capability.py tests/test_binomial_capability.py tests/test_menu_localization.py tests/test_help_center.py tests/test_g12_inventory.py tests/test_g5_spc_reports.py -q --tb=short -k 'not computation_plotting_ast_matches_frozen_structure'
& $python -m pytest tests/test_poisson_capability.py::test_poisson_menu_workflow tests/test_help_center.py::test_menu_inventory_and_dialog_ids_match_the_source tests/test_help_center.py::test_pi_import_topic_is_unique_searchable_and_available_offline -q --tb=short
```

首次执行 221 通过、3 失败、8 排除。修复有尾随空格的工作表列名选择及帮助清单计数后，单独复测的 3 项均通过，累计覆盖 224 项。8 项排除均为上述已知的 G5 AST 冻结差异，SPC 实现与冻结夹具未改。未运行全量测试。
