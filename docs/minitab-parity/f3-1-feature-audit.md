# MiniJMP F3-1 剩余功能审计

## 审计基线

- 2026-11-25，`main`，`e3ac3431b573804c3826a13ad0fb612299e154f5`，开始时工作区干净。综合矩阵 208 行，165 条有效记录，本轮复查其中全部 14 条 unknown。四条 F2 partial 保持原样。
- Minitab 19 主参考为本机 Windows 桌面版 19.1.0.1。用 `DispatchEx('Mtb.Application')` 启动独立实例，在零命令的空项目写入固定列，检查命令输出和存储列。COM 的 Commands 提供命令对象，GUI 菜单、对话框及图内标注沿用已知接口限制。正文中「原生」专指本轮实际输出或明确标注的历史原生证据。
- Minitab 22 以既有 22.6 环境基线及下文所链接的桌面帮助为参考。在线帮助会更新，本轮没有重跑 22.6 GUI，也未调查各席位授权。普通统计入口按厂商桌面帮助列示，额外产品和运行时依赖在对应条目单列。版本未锁定的选项仅作当前文档证据。
- MiniJMP 查阅主菜单、表操作与图形入口、帮助主题及搜索映射，沿调用检查实际算法、输出和工程格式。由项目 `.venv` Python 3.11.9 执行下文定向检查。历史参照见 [DOE 验收](../doe-minitab/acceptance.md)、[DOE 原生与差异记录](../doe-minitab/phase3-g05-g08-parity.md)、[此前覆盖汇总](coverage-summary.md)。

## 十四项结果

| 功能 ID | Minitab 功能及版本依据 | MiniJMP 实现 | 原状态 | 新状态 | 证据 | 剩余差距 |
| --- | --- | --- | --- | --- | --- | --- |
| GEN-013 | Stat → DOE → Factorial / Response Surface → Analyze。响应和设计拟合后列出异常点及影响诊断。Assistant 的报告卡也会标记异常。19 系列历史文档与 22 参考帮助支持诊断，自动排除后再拟合的厂商功能范围仍待确认。 | `code/doe_rsm.py::fit_rsm` 计算残差、学生化残差及 Cook 距离，`code/doe_diagnostics.py::contract` 与 `code/doe_dialog.py::AnalyzeDOE` 发布分析。原始运行身份须保留，可经确认修正测量或录入错误后重新分析。RSM 遇到缺失响应会拒绝拟合。 | unknown | unknown | `tests/test_doe_rsm_diagnostics.py`，DOE 专项 GEN-013，厂商 [因子诊断表](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/factorial/analyze-factorial-design/interpret-the-results/all-statistics-and-graphs/fits-and-diagnostics-table/)、[响应面影响统计](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/response-surface/analyze-response-surface-design/methods-and-formulas/diagnostic-measures/) 与 [Assistant DOE](https://support.minitab.com/en-us/minitab/media/pdfs/translate/assistant_doe.pdf)。 | 本地无自动删值或替换响应流程。逐点删除后计算诊断统计和自动删除观测后发布重拟合模型是不同的操作。 |
| F0-NEW-001 | File → Open / Save Project / Save Project As。19 与 22 的 MPX 封装工作表、输出、历史和对话框设置，MWX 为单表文件，MTW 为早期格式。 | `code/worksheets.py::load_file,_save_project,_payload,saveMeta` 往返 .dexpl 多表、活动表、列公式、显示设置及 DOE 元数据，混料模型有专门持久化。单表可另行导出。 | unknown | partial | 原生 SAVE/RETRIEVE 重开 MPX；`tests/test_worksheets.py` 与 `tests/test_worksheet_formulas.py`；[19 指南](https://www.minitab.com/content/dam/www/en/uploadedfiles/documents/getting-started/Minitab19GettingStarted_EN.pdf)、[工程与工作表格式](https://support.minitab.com/en-us/minitab/help-and-how-to/data-input-and-output/save-and-export-data-and-output/save-and-export-minitab-projects-and-worksheets/)。 | 工程不恢复通用报告、图形和分析会话。MPX/MWX/MTW 不互通，CSV/XLSX 可交换表数据。 |
| F0-NEW-007 | Calc → Calculator。列、常量、函数表达式写入列或常量，支持给结果列分配公式。19 指南与原生 LET，22 参考帮助。 | 工具 → 列公式，`code/modified_table.py::calculator`、`code/worksheet_formulas.py::CalculatorDialog,evaluate`。目标可选已有或新列，支持算术、九个数值函数、一次性计算、联动重算和循环依赖检查。 | unknown | implemented | 原生 LET 存储列，`tests/test_worksheet_formulas.py`；[Calculator](https://support.minitab.com/en-us/minitab/help-and-how-to/calculations-data-generation-and-matrices/calculator/overview/)。 | 函数库、存储常量、文本日期及表达式语法有差异，未测跨产品全函数一致性。 |
| F0-NEW-016 | Navigator 选择项目输出，View → Command Line/History 运行会话命令、查看和重放历史，可另存 exec。19 指南及 22 参考帮助均列出三项。 | `code/MiniJMP.py::addPlot,updatePlotsMenu,print` 提供图形回访及来源表结果输出，能覆盖部分结果导航。工作表切换和表编辑撤销各自独立。 | unknown | partial | 原生 COM 的 ExecuteCommand/Commands 仅证明命令层，图形菜单见 `tests/test_plot_window_lifecycle.py` 历史验证；[19 指南](https://www.minitab.com/content/dam/www/en/uploadedfiles/documents/getting-started/Minitab19GettingStarted_EN.pdf)、[会话命令窗](https://support.minitab.com/en-us/minitab/help-and-how-to/minitab-environment/interface/interface-components/command-line-history-pane/)。 | 跨分析的结构化输出导航、命令执行、命令历史和重放均缺。 |
| F0-NEW-018 | Assistant 菜单按目标和数据类型指导选法，运行后提供解释、诊断和报告卡。19 指南以散点报告示范，当前桌面有 Assistant 工具栏与方法资料。 | `code/MiniJMP.py` 的统计菜单为直接选法，`code/help_link.py::help_window` 提供帮助。各分析已有参数校验与局部诊断。 | unknown | missing | 菜单及帮助源码，`tests/test_help_center.py`；[19 指南](https://www.minitab.com/content/dam/www/en/uploadedfiles/documents/getting-started/Minitab19GettingStarted_EN.pdf)、[桌面工具栏](https://support.minitab.com/en-us/minitab/help-and-how-to/minitab-environment/interface/interface-components/toolbars-and-the-status-bar/)、[Assistant DOE 方法](https://support.minitab.com/en-us/minitab/media/pdfs/translate/assistant_doe.pdf)。 | 无按目标分流、自动带入分析及统一的报告卡。 |
| F0-NEW-019 | 19.1 原生确认 Windows COM。19.2020.1 新增 Python 和 Additional Tools（Quality Trainer、Workspace 的入口），20.2 新增 R。22 桌面支持脚本运行并将结果、图表带回项目，需外部环境和配套包，外部产品入口与实际访问权限分别核对。 | `code/pi_import.py`、`code/pi_reader.py` 有专用 PI 集成，另有 Excel/CSV 交换；`code/modified_app.py::discoverPlugins,installPlugin,loadPlugin` 禁用了内置上游插件挂载路径。 | unknown | partial | 原生 COM；`tests/test_pi_import.py`（既有、无现场 PI）；[19 发布说明](https://www.minitab.com/content/dam/www/en/uploadedfiles/documents/readme/Minitab19ReadMe_en.pdf)、[20.2 发布说明](https://www.minitab.com/content/dam/www/en/uploadedfiles/documents/readme/Minitab20ReadMe_en.pdf)、[桌面集成指南](https://support.minitab.com/en-us/minitab/integration/)。 | 无通用外部脚本返回协议、COM 自动化服务或插件生命周期。22.6 具体菜单及外部产品许可未枚举。 |
| F0-NEW-020 | Stat → Nonparametrics。符号、Wilcoxon、Mann–Whitney、Kruskal–Wallis、Mood、Friedman 和游程分别处理中心、区组或序列随机性。19 七种原生命令均产生输出，22 参考帮助分项列示。 | `code/MiniJMP.py` 基础统计、`code/sample_test_dialog.py` 推断、`code/t_test.py` 及现有方差分析不提供这些检验。非参数容差区间已有独立矩阵 ID，目标为总体覆盖率。 | unknown | missing | 19 原生 STEST、WTEST、Mann–Whitney、Kruskal、Mood、Friedman、Runs；[非参数方法目录](https://support.minitab.com/en-us/minitab/help-and-how-to/statistics/nonparametrics/supporting-topics/understanding-nonparametric-methods/)、[会话命令手册](https://support.minitab.com/minitab/session-command-help/)。 | 七种检验均无计算与正常入口。详见下表。 |
| F0-NEW-021 | Stat → Equivalence Tests。给定事前等效界限，用单样本、独立双样本、配对或 2×2 交叉设计数据汇报双单侧推断及区间。19.1 四种 TOST 调用均产生原生命令对象，22 参考帮助列四种。 | `code/sample_test_dialog.py::Mean1SampleDialog,Mean2SampleDialog,PairedTDialog` 与 `code/t_test.py` 提供差异检验及置信界。 | unknown | missing | 19 TOST 命令对象，无可读分析输出；`tests/test_g2_hypothesis_reports.py` 验证现有差异检验；[等效性检验目录](https://support.minitab.com/en-us/minitab/help-and-how-to/statistics/equivalence-tests/supporting-topics/equivalence-tests-in-minitab/)。 | 四种 TOST 均未实现，常规 t 检验的非显著结果无法判定等效。 |
| F0-NEW-022 | Stat → Reliability/Survival。失效时间、删失标记或区间及协变量产生寿命分布、生存曲线、寿命回归等。19 原生 LTEST 确认右删失拟合，发布说明直接提及 Warranty Prediction；Cox 为 21 新增。22 参考帮助列出各分支。 | `code/dist_fit.py::fit_weibull,fit_lognorm,fit_expon` 处理完整观测的通用分布拟合，`code/capability.py` 相关能力分析按规格计算。 | unknown | missing | `tests/test_capability_plots.py` 既有完整数据场景；[可靠性目录](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/reliability/supporting-topics/basics/reliability-analyses-in-minitab/)、[19 发布说明](https://www.minitab.com/content/dam/www/en/uploadedfiles/documents/readme/Minitab19ReadMe_en.pdf)、[21 发布说明](https://www.minitab.com/content/dam/www/en/uploadedfiles/documents/readme/MinitabReadMe_en.pdf)。 | 无删失数据模型、风险集、寿命回归和可靠性专用工作流。完整样本拟合是可复用能力。 |
| F0-NEW-023 | Stat → Multivariate。因子提取和旋转、观测/变量层次聚类及 K-means、判别分类、简单/多重对应分析。19.1 原生确认因子、层次聚类、判别、简单及多重对应分支，22 参考帮助列全。 | `code/MiniJMP.py::pca_analysis` → `code/pca_dialog.py::PCADialog` 提供 PCA，矩阵图和交叉表可作输入检查。 | unknown | missing | 19 原生 FACTOR、CLUOBS、CLUVARS、KMEANS、DISCRIMINANT、CA、MCA；既有 `tests/test_pca_plots.py`；[多变量分析目录](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/multivariate/supporting-topics/basics/multivariate-analyses-in-minitab/)。 | 因子分析、聚类、判别分析、对应分析四类均缺。PCA 独立计数。 |
| F0-NEW-024 | Stat → Basic Statistics → 2 Variances。两列、堆叠及适用的汇总输入，报告方差比或标准差比、假设检验和区间，含 Bonett、Levene 或假设正态的 F。19 原生与 22 参考帮助。 | `code/sample_test_dialog.py::MultiVarDialog` 允许两组原始列，`code/chi_sq.py::multi_pop_var_test` 输出 Bonett 成对标准差比及区间、p，另有经典 Levene、Brown–Forsythe、O’Brien 与可选 Bartlett。 | unknown | partial | 19 原生 TWOVARIANCES；`tests/test_g2_hypothesis_reports.py`；[2 Variances 方法](https://support.minitab.com/en-us/minitab/help-and-how-to/statistics/basic-statistics/how-to/2-variances/methods-and-formulas/methods-and-formulas/)。 | 现有比较有真实推断输出。专用方向及比值假设、比值尺度、汇总输入、完整厂商方法与图表未覆盖。 |
| F0-NEW-030 | Stat → Control Charts → Variables Charts for Subgroups → Xbar / R / S。独立报告子组均值、极差或标准差的时序图及控制限。19 三命令均返回图形，22 参考帮助列出独立及组合图。 | `code/MiniJMP.py::cChartXBR,cChartXBS` → `code/ctrlchart_dialog.py::XBRDialog,XBSDialog` → `code/control_chart.py::x_plot,xBar_R,xBar_S`。组合图能计算和呈现三个面板。 | unknown | partial | 19 XBAR/RCHART/SCHART；`tests/test_g6_quality_charts.py`；[子组变量控制图](https://support.minitab.com/en-us/minitab/help-and-how-to/quality-and-process-improvement/control-charts/supporting-topics/understanding-variables-control-charts/variables-control-charts-in-minitab/)。 | 单图发布与报告、逐图选项及每行一个子组的多列输入未覆盖。原生图内控制限未取数。 |
| F0-NEW-035 | 已有图右键 → Layout Tool。选择若干打开的图、指定行列、排位和注释，生成可编辑的组合图。19 官方指南有完整步骤，22 参考帮助明确仅桌面。 | `code/MiniJMP.py::addPlot` 保存本次会话中的图供回看，`code/pandastable_local/app.py::pdfReport` 按图逐页导出。固定诊断面板由分析器构建。 | unknown | missing | 源码与既有 `tests/test_plot_window_lifecycle.py`；[19 指南第 16–18 页](https://www.minitab.com/content/dam/www/en/uploadedfiles/documents/getting-started/Minitab19GettingStarted_EN.pdf)、[组合已有图](https://support.minitab.com/en-us/minitab/help-and-how-to/graphs/general-graph-options/groups-and-multiple-graphs/displaying-graphs-together-in-a-graph-layout/)。 | 无从已有图选取并在同一页面调整、编辑和导出布局。 |
| F0-NEW-036 | Data → Merge Worksheets → Match Values / Side-by-Side。选两个工作表，按键匹配或按行并列，可配置未匹配项、保留列及结果工作表。22 参考帮助确认选项；19 原生 MERGE 确认并列及按键两种处理逻辑，对话框未现场核验。 | 工具 → 合并/拼接表，`code/pandastable_local/core_orig.py::doCombine` 要求子表，`code/pandastable_local/dialogs.py::CombineDialog` 实际调用 pandas 键连接或纵向拼接，可预览及替换当前表。 | unknown | partial | 19 原生 MERGE、真实 Tk 菜单往返，`tests/test_table_regressions.py::test_filter_boundary_covers_duplicate_removal_merge_and_replace`（既有，过滤保护）；[合并工作表](https://support.minitab.com/en-us/minitab/help-and-how-to/manipulate-data-in-worksheets-columns-and-rows/how-to/merge-worksheets/overview/)、[匹配值](https://support.minitab.com/en-us/minitab/help-and-how-to/manipulate-data-in-worksheets-columns-and-rows/how-to/merge-worksheets/merge-worksheets-by-matching-values/)。 | 无直接选两张项目工作表、多键、按行横拼和独立结果表；重复键及缺失键采用 pandas 语义。粘贴用 `code/df_combine.py::df_combine` 按位置覆写，不能替代关联。 |

## 子功能差距

状态描述针对各独立能力；综合矩阵仍使用原 ID。

| 功能 | 子项与本地状态 | 输入、输出及证据边界 |
| --- | --- | --- |
| GEN-013 | 异常诊断 implemented；经核实的人为响应修正后重跑可用；自动排除／替换／重拟合的厂商依据 unknown | Diagnose 使用残差、杠杆和影响度；RSM 源码拒绝缺失响应；不能把清空响应或删除设计行当作通用排除机制。 |
| NEW-016 | Navigator partial；Command Line missing；History missing | 图形列表可返回已存图，文本输出按来源表路由。没有可编辑重放的分析命令记录。 |
| NEW-019 | PI 专用集成 implemented；脚本与结果回传 missing；通用 COM 与插件 missing；厂商产品入口 missing | 19.1 的 COM 与 19.2020.1 的 Python 分属不同机制。R 在 20.2 新增。授权对照仅覆盖已查文档。 |
| NEW-020 | 单样本符号 missing；单样本 Wilcoxon missing；Mann–Whitney missing；Kruskal–Wallis missing；Mood 中位数 missing；Friedman missing；游程 missing | 符号以相对目标的方向计数，单样本 Wilcoxon 以观测减去目标值后的有符号秩推断；Mann–Whitney 用两独立样本秩，Kruskal–Wallis 用多独立组秩，Mood 用组别 × 中位数两侧计数；Friedman 用区组内秩；游程用有序序列相对阈值的连续段。输出相应计数或秩统计量及 p，适用时含估计或区间。19 的 STEST 和 WTEST 各返回三项文本输出。 |
| NEW-021 | 单样本、独立双样本、配对、2×2 交叉均 missing | 单样本相对目标，独立样本用组统计量，配对用配对差，交叉需序列和周期。共同输出两侧结果及等效区间。19.1 四种调用均没有公开输出对象，未确认原生数值。 |
| NEW-022 | 右删失参数拟合、任意/区间删失拟合、右删失非参数生存、任意删失非参数分布、寿命回归、Cox、Probit、修复系统增长曲线、可靠性试验计划、保修预测均 missing | 参数分支输出分布估计、寿命分位点/可靠度，非参数分支按删失型估生存曲线（右删失例为 Kaplan–Meier），寿命回归用协变量预测分位数，Cox 输出相对风险；Probit 处理应力－响应，增长曲线处理重复故障，试验计划及保修使用专用输入。19 的保修由发布说明确认，右删失拟合已有原生结果，其他可靠性分支未逐一取得 19.1 输出，Cox 明确为 21 新增。 |
| NEW-023 | 因子分析 missing；聚类（观测、变量、K-means）missing；判别 missing；对应分析（简单、多重）missing | 所需输出分别为潜因子载荷及旋转、成员/树图、分类和验证、列联惯量与坐标。19.1 KMEANS 两类案例返回四项文本输出。 |
| NEW-030 | 独立 Xbar partial；独立 R partial；独立 S partial | 均值、极差、样本标准差分别由组合图计算并给出控制限和报警信息。组合图有共用输入，三个独立 GUI 入口和独立图结果仍缺。 |

## 本轮验证记录

- `.venv/Scripts/python.exe -m pytest tests/test_worksheet_formulas.py tests/test_worksheets.py tests/test_g2_hypothesis_reports.py tests/test_g6_quality_charts.py tests/test_help_center.py tests/test_menu_localization.py tests/test_doe_rsm_diagnostics.py -q`，**318 passed**，包含真实 Tk 的项目与列公式往返。没有执行全量回归。
- 原生第一组固定输入 `C1=1…12`，`C2=[2,4,4,6,8,8,9,12,12,15,15,18]`，`C3=[1,1,1,2,2,2,3,3,3,4,4,4]`。`LET C4 = C1 + 2*C2` 读回 `[5,10,11,16,21,22,25,32,33,40,41,48]`。`MANNWHITNEY C1 C2`、`KRUSKAL C1 C3`、`MOOD C1 C3`、`RUNS C1` 分别返回 4、2、2、2 个文本输出。独立图命令为 `XBAR C1 3`、`RCHART C1 3`、`SCHART C1 3`，COM 均返回图形，Xbar 另有结构化输出。属功能存在性验证。
- 第二组 `C1=[1,2,4,3,5,7,2,6,8,4,7,9]`、`C2=[2,3,5,5,7,9,3,7,10,5,9,11]`，治疗列循环 1/2/3，区组每三行递增。`FRIEDMAN C1 C3 C4` 返回三项。默认 `TWOVARIANCES C1 C2` 报告方差比 0.762069，Bonett CI (0.281, 2.042)、p=0.536，Levene CI (0.259, 2.135)、p=0.559。MiniJMP 的成对实现使用标准差比尺度，并按 `pair_ratio` 计算单对修正；其普通 Levene 以均值为中心，p=0.546003；Brown–Forsythe 以中位数为中心，p=0.559034，与原生 Levene 显示值一致。数值比较应先统一尺度、方法和缺失处理。
- 同组在 DESCRIBE 后用 `SAVE "…mpx"; PROJECT.` 生成 15052 字节工程，`RETRIEVE "…mpx"; PROJECT.` 后读回 12 个 C1 值及 4 个命令对象。写入前 COM 对象计数为 9，包含建列及操作命令，不能用于证明完整 GUI History 恢复。临时文件在第一次清理时仍被 COM 占用，往返取数已完成。
- 多变量探针使用同组 C1/C2，加 `C3=[2,1,2,5,6,2,1,8,7,3,9,8]`、六行一组的 C4 和 `C5=[0,1,0,1,0,0,1,0,0,1,0,0]`。CLUOBS、CLUVARS、DISCRIMINANT、CA、MCA 各新增一个带输出的原生命令对象。设置上下界 −3、3 的两次 TOST（独立及加 PAIRED）各新增一个命令对象，均没有可读结果，故不报告数值。寿命回归试探未取到新结果。COM 不返回文本或图内数值时未当作统计验证。

- 同组补跑 `STEST 4 C1`、`WTEST 4 C1` 各新增三项文本输出，`KMEANS C1-C3; NUMBER 2.` 新增四项文本输出。单样本及四列交叉设计 TOST 各新增一条命令对象，均无可读输出。`FACTOR C1-C3; NFACTORS 2.` 新增一条命令和三项输出。对相同 C1/C5 执行 `LTEST C1; CENSOR C5.`，新增十项图表、文本或其他结构化输出。另加 NONPARAMETRIC 的试探没有新增命令对象，非参数分支仍按文档。
- 原生从两个三行 CSV 建表，键分别为 1/1/2 与 1/1/3。`MERGE` 默认并列生成新表四列三行；每张表指定 `BY C1` 后生成新表四列六行（相同键 1 的四种组合、两侧各一条未匹配，COM 缺失哨兵为 1.23456e+30）。仅验证默认值这组输入，未验证其他重复、多键、列选择或缺失选项。MiniJMP 真实 Tk 从「工具 → 合并/拼接表」选择同键外连接，预览后确认替换，得到单键列、四条重复键匹配和两条补缺失记录。两边默认输出列与写入位置有差异。
- 确认 `code/chi_sq.py::two_pop_var_test` 调用 `multi_pop_var_test` 时缺少必填 `labels`，以第二组固定数据调用复现 TypeError。当前菜单调用另一条有效路径，受影响的是该独立函数。若未来复用，应先传入明确的样本标签并核验返回字段。

## 开发候选和顺序

以下条目属于 F3-1 审计结论，优先级根据工业用途、使用频率、增量、维护成本和独立参考可得性排序。

| 优先级 | 功能 | 实际缺口 | 开发价值 | 实现复杂度 | 最小验收条件 |
| --- | --- | --- | --- | --- | --- |
| P0 | NEW-020 常用非参数检验 | 符号、Wilcoxon、Mann–Whitney、Kruskal–Wallis | 小样本、偏态、等级和跨批比较，基础推断高频；SciPy 和手算秩可独立校验 | 中，重点是零差、并列、精确与渐近选择 | 明确假设、双/单侧、缺失与并列；以独立枚举及厂商固定例核对。 |
| P1 | NEW-036 项目工作表合并 | 两个项目表直接选择、组合键、按行并列、新结果表 | 测量值关联批次和主数据，频繁，现有 pandas 内核可复用 | 中，重复与空键、列重名和行数膨胀需明确 | 两张源表不被修改，匹配和未匹配计数清晰，固定夹具覆盖重复键、空键、同名列及取消。 |
| P1 | NEW-024 双样本离散度 | 专用比值推断、方向、适用时汇总输入 | 设备、供应商、变更前后比较；已有两组入口，增量集中在报告与专用选项 | 中，官方公式和 19 原生均可用 | 原始与汇总输入边界，报告尺度、比值、区间、备择及方法；与 19 固定例和独立 F 分布核对。 |
| P1 | NEW-021 等效性 | 单样本、双样本、配对 TOST | 替代供应商、工艺更换和量测方法确认，使用频率取决于行业，闭式 t 参考可得 | 中 | 事先界值，独立/配对缺失处理，双单侧检验及对应区间；覆盖边界和方向。 |
| P1 | NEW-001 携带已完成结果的工程 | 表和部分模型可恢复，缺通用图表和结果快照 | 交接、复审及长期追溯，跨分析可复用 | 中至高，格式迁移和保存失败恢复；避免引入可执行序列化 | 两表各有图及分析表，安全重开恢复来源、顺序与报告，旧工程兼容，失败保护原文件。 |
| P2 | NEW-030 单独发布子组图 | 独立 Xbar、R、S 图和报告 | 单页 SPC 便于呈报，组合图已提供计算核心 | 低至中，复用现有面板，原生图内数值另核 | 三图各自只发布一个面板与对应统计表，相同配置下复用组合限值并覆盖不等组。 |
| P2 | NEW-020 专项非参数 | Mood、Friedman、游程 | 中位数稳健比较、随机区组、时序非随机性，较少使用但有明确用途 | 中，参考明确 | 组内秩、有序输入、并列及零计数边界，各有独立案例。 |
| P2 | NEW-021 2×2 交叉 | 序列与周期建模及等效性 | 专门的交叉实验，典型于生物等效研究 | 中至高 | 两序列均衡及缺失策略、参考/试验方向、独立固定例。 |
| P2 | NEW-022 可靠性第一批候选 | 右删失 Kaplan–Meier 和 Weibull 寿命拟合 | 寿命台架及可靠度评估价值高，面向特定使用者；先确认实际需求 | 中至高，删失似然、风险集及不确定性 | 正确处理同时事件与删失，生成风险集、曲线、区间及分位寿命，与独立参考和 19 案例核对。 |
| P2 | NEW-023 层次聚类候选 | 观测或变量群组 | 可用于工艺批次分群和变量筛选，先确认有代表性的数据 | 中，SciPy 层次聚类参考可得 | 距离与链接方法明确，验证标准化、并列、成员及树图。 |
| P2 | NEW-016 结果导航 | 工作表维度的图与分析输出索引 | 多表、多分析工程，比单个图形菜单更易追溯，依赖工程结果持久化 | 中，主要为状态与索引 | 双表各有多项分析，按表定位并恢复输出。 |
| P2 | NEW-035 固定网格组合 | 多张已有图合到同页 | 提交报告时使用，已有逐图及 PDF 输出 | 中，需测试缩放、输出和布局回读 | 选择两张已有图、交换位置并导出单页，源图保留。 |

执行顺序建议为常用非参数 → 工作表合并 → 双样本比值推断与基础等效性 → 工程结果持久化与索引。独立子组图、专项统计和固定网格在有实际用例时分别立项。

## 暂不建议开发

- **GEN-013 的自动删值**。厂商产品范围未证实，自动改动可能破坏实验设计平衡及审计轨迹。现有残差与影响度诊断配合调查、记录理由及经确认重跑可满足当前决策流程。
- **NEW-001 的 MPX/MWX 互操作、NEW-016 的 Minitab 命令语言兼容、NEW-019 整套插件或外部产品入口**。维护成本与格式、版本、权限和分发耦合。已有 CSV/Excel、图表导出及 PI 专用入口可服务已知交换场景。
- **NEW-018 整套 Assistant**。推荐规则、假设分流和报告维护需随全部方法演进，现有帮助与分析内诊断先覆盖常用路径。
- **NEW-022 可靠性全套、NEW-023 四类模型整体对标、NEW-035 厂商级图元编辑器**。先以具体寿命数据、分群输入或同页图形用例限定范围。完整寿命数据已有分布拟合，降维已有 PCA，常规输出已有逐图导出和 PDF。

## 仍需外部证据

唯一保留 unknown 为 **GEN-013**。已查 DOE 诊断、Assistant 的异常点规则、既有验收及原生命令资料。资料确认自动识别、诊断量和手工调查路径，未定位到自动排除、保留来源并重新拟合的命令或界面。若现场确有该功能，需提供确切版本、菜单/命令、同一设计启用前后的观测数和结果，以及原始表是否被修改。当前审计可闭合，无需用户先补材料。

已判定条目的验证边界包括 19.1 的 Merge 两种对话框、各寿命子菜单及 TOST 数值，以及 22.6 的实际选项和外部产品授权。若后续立项，按拟开发方法补相应实机样例。矩阵的 22 实机栏保留原字段，文档支持记录在目标证据栏。
