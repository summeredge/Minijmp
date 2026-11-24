# MiniJMP 功能覆盖与阶段验收

F0 审计日期为 2026-11-21。仓库为 `D:\MyTools\Minijmp`，分支 `main`，源码基线 `0eadb8a`。本轮以 Minitab 22 为功能参考，历史固定数值案例仍使用 19.1.0.1。

## F0 实机核验（历史基线）

- 本机 COM 注册指向 `C:\Program Files\Minitab\Minitab 22\Mtb.exe`，文件版本 **22.6.0.0**。沙箱内激活返回 `0x80080005`，沙箱外 PowerShell COM 激活成功，返回 `Version=22.6`，`AppPath` 与注册路径一致。
- COM 的 Project 暴露 ExecuteCommand、Commands 和 Worksheets。UserInterface 公开成员为 DisplayAlerts、Interactive、UserControl、Visible，未发现菜单或对话框枚举接口。独立空白项目检查未通过，未执行写入命令。本轮完成了实机安装、版本和接口核验，尚未取得逐项原生命令结果或菜单与对话框证据。
- Stat 优先比较了官方 GLM、泊松率、功效、Type 1 量具、属性能力及 G 图的功能范围。Graph 新增 Graph Builder 实时预览。Data 核对了堆叠和逆堆叠。Calc 核对了随机数据及分布计算。矩阵的目标证据、22 实机证据、MiniJMP 源码及数值证据分别记录。[官方 GLM](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/anova/how-to/fit-general-linear-model/before-you-start/overview/) · [逆堆叠](https://support.minitab.com/en-us/minitab/help-and-how-to/manipulate-data-in-worksheets-columns-and-rows/supporting-topics/data-types-and-arrangements/stacked-and-unstacked-data/) · [Graph Builder](https://support.minitab.com/en-us/minitab/help-and-how-to/graphs/graph-builder/overview/)
- **F0 未完整验收。** Stat、Graph、Data、Calc 的 22.6 实际菜单、默认参数、输入模式和许可差异仍待现场确认。优先补 Q1、S1、M1 对话框和矩阵中的待核实项，包括 Calculator、工作表合并、独立子组图、Additional Tools 和 DOE GEN-013。若继续限定 COM，只能在安全的独立项目中补命令与结果；菜单位置及对话框选项需由用户在 22.6 界面提供观察记录。

## 当前状态与去重（F3-1，2026-11-25）

| 状态 | 数量 |
| --- | ---: |
| 已实现 | 148 |
| 部分实现 | 10 |
| 未实现 | 6 |
| 待核实 | 1 |
| 不适用 | 2 |
| DOE 交叉引用 | 36 |
| 功能别名 | 5 |

[覆盖矩阵](coverage-matrix.csv) 共 208 行，新增 F0-NEW-038，原有 ID 保留。扣除 36 条 DOE 交叉引用、5 条别名后，有 167 条独立审计记录；再扣除 2 条不适用后为 165 条有效记录，其中 1 条待核实，164 条已有功能判定。按 165 条为分母，已实现率为 89.70%，已实现或部分实现为 95.76%，已有判定为 99.39%。DOE 的 80 个专项 ID 保留原有范围和证据，包含已实现、待核实及不适用项。部分记录为功能组，记录数量不等于厂商菜单命令总数。

## F1 结论

F1 将 16 条开发缺口分入 10 个工作包。七个工作包交付后仍有 **4 条 F2 部分实现记录**，其中 P1 和 P2 各 2 条。F2 当时另有 14 条待核实记录，后续由 F3-1 补证。历史 19.1 数值覆盖不足及已知方法差异单独跟踪。双因子 ANOVA 按现有范围计已实现，GLM 扩展用独立 ID；容差区间保留实现状态，G07 继续验证。E01、G08、G03、E02 保留现有结论。

2026-11-23，Q1 属性过程能力完成，F0-NEW-029 标记为已实现。二项通过 22.6 原生 BCAPA 固定案例，泊松通过 19.1.0.1 原生 PCAPA 固定案例。该条记录仅描述 Q1 的验收范围。交付范围和原生证据见[能力验证](../capability-validation.md)和[开发待办](development-backlog.md)。

## 验证

复用 F0 已记录的 382 项回归通过结果。F0/F1 审计轮仅变更审计文档，核对 CSV 解析、功能 ID、DOE 引用、源码与测试文件链接、去重计数及任务映射。

## F2 已验收范围

- **Q3 · F0-NEW-031**：G 图以独立几何 CDF 插值核对控制限，并验证 until 比 between 整体多 1、日期来源行及零间隔。T 图以解析分位数和 Weibull 似然得分核对，含零时长拒绝。真实 Tk 菜单验证两个图形、来源报告及 PNG/Excel 导出。Minitab 19 `GCHART C1; P .1.`（[0,1,12,48,200]）原生图限 0/5.6/61.7、报警点 5；`TCHART C2; WSHAPE 1; WSCALE 3.`（[.25,1.5,3,20,.02]）图限 0.00/2.08/19.82、报警点 4；两例匹配显示精度。本地覆盖严格单点越限规则。[G 图方法](https://support.minitab.com/en-us/minitab/help-and-how-to/quality-and-process-improvement/control-charts/how-to/rare-event-charts/g-chart/methods-and-formulas/methods-and-formulas/) · [T 图方法](https://support.minitab.com/en-us/minitab/help-and-how-to/quality-and-process-improvement/control-charts/how-to/rare-event-charts/t-chart/methods-and-formulas/methods-and-formulas/)

- **T1 剩余扩展 · F0-BASE-017**：奇偶居中窗直接求和、历史原点和末窗预测区间按独立公式核对；SES 创新区间按闭式增益验证。自动 ARIMA 在固定差分阶数内用 BIC 与独立 SARIMAX 候选排序比对。真实 Tk 验证时间索引、平滑区间和图形导出。Minitab 19 `MA C1 4; CENTER; SMOOTHED C2.` 的首个居中值 14.75；同数据尾随 MA 原点 10 时三个预测均为 23.75。本地加法回归初始化与 19.1 `TSWINT C1 6; ADDITIVE; FORECASTS 3; FSTORE C2.` 预测 [32.1551917555, 36.7700126128, 36.7222673910] 一致，绝对误差小于 1e-12。Minitab 19 固定权重 0.2 另验证周期 2、3、4 的加法 Winters，三步预测误差小于 1e-12。零权重探针在两组数据中复核短周期前四点初始化。乘法季节初值未确认，仍保留两周期初始化，区间按 19.1 固定案例反推出的原量纲残差 MAD 与步长放大系数计算。两组序列、五组权重、周期 2、3、4、6 的原生报告六步半宽误差不超过 0.0002。Minitab 当前公开页的季节调整绝对误差及放大系数线性项与 19.1 实测不同。自动 ARIMA 新增固定 λ 及 Guerrero 搜索、常数／漂移选项，独立用白噪声与随机游走闭式结果核对。拟合仍采用高斯状态空间极大似然，平滑权重为固定输入。Minitab 19.1.0.1 执行 `ATARIMA C1; BMODEL 1 0 1 0 1.` 返回未知命令 ATAR，未取得该版本 Box–Cox 与常数搜索端到端输出。乘法区间仅核验宽度公式；本地与原生的季节初值仍然不同。[Winters 初始化](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/time-series/how-to/winters-method/methods-and-formulas/methods-and-formulas/) · [自动 ARIMA 方法](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/time-series/how-to/forecast-with-best-arima-model/methods-and-formulas/methods/)

- **S2 · F0-BASE-003 / BASE-025 / NEW-026**：Ryan–Joiner 的 Blom 正态分数相关以独立 Pearson 计算核对，KS 以经验 CDF 两侧距离核对。Minitab 19 固定输入 [1,2,2,3,4,6,12,24] 的 RJ/KS p 为 .011/.049，本地 .011398/.049668，校准方式有差异。Banga–Fox 等样本量 MC 的全局 p=0.965541768，与冻结 VARTEST 的 .966 一致；MC 指多重比较，区间与 Bonferroni 置信区间分别报告。不等组 MC 按论文 §3.2 计算全局 p 和比较区间图。公开资料两处的区间宽度与临界值记法有差异，本实现按 §3.2 反演统一不等组区间的修正项与临界值，宽度从 §2 的对数方差拒绝式换算，与等量既有宽度一致。独立最小二乘、正态极差积分和区间接触点验证通过。Minitab 19 用列长不同及尾端缺失补齐分别试运行 VARTEST，返回列长不等或无法计算，未取得相应原生参照。功效由 statsmodels、正态概率直接积分和最小整数前后边界核对。Minitab 19 `POWER; TONE; SIGMA 1; DIFFERENCE .4; SAMPLE 52; SPOWER C3.` 返回 0.807787808891，本地 0.807787808876。真实 Tk 功效菜单、来源表报告和 PNG 已验收。[正态性手册](https://support.minitab.com/en-us/minitab/help-and-how-to/statistics/basic-statistics/how-to/normality-test/methods-and-formulas/methods-and-formulas/) · [Banga–Fox 论文](https://support.minitab.com/en-us/minitab/media/pdfs/translate/Multiple_Comparisons_Method_Test_for_Equal_Variances.pdf)

- **Q2 · F0-NEW-028 / F0-BASE-051**：量具 1 型按公差比例和研究倍数手算 Cg/Cgk 及偏倚 t，覆盖零变差和公差边界。线性与偏倚用独立 OLS 及分组单样本 t 核对系数、p 值与置信带。EWMA 子组以显式权重核对中心及逐点限，CUSUM 以所有后缀的累积和直接求最大值，另检查加权历史效应及非法大小。真实 Tk 验证量具报告与 PNG 导出、子组 SPC 结果与控制图；既有个体图回归通过。Minitab 19 执行 TOGAGE（30 次）和 LNGAGE 各生成图形，COM 文本未返回图内数值，原生数值一致性未确认。[Type 1 方法](https://support.minitab.com/en-us/minitab/help-and-how-to/quality-and-process-improvement/measurement-system-analysis/how-to/gage-study/type-1-gage-study/methods-and-formulas/methods-and-formulas/) · [偏倚回归](https://support.minitab.com/en-us/minitab/help-and-how-to/quality-and-process-improvement/measurement-system-analysis/how-to/gage-study/gage-linearity-and-bias-study/methods-and-formulas/gage-linearity/)

- **M1 · F0-NEW-027**：statsmodels 公式模型与 III 型 ANOVA 核对单因子、双因子、三因子交互、非平衡设计及协变量，逐行删除重拟合核对 PRESS。真实 Tk 菜单验证拟合、方差表、预测、来源表图形、Excel 导出和报告。直接相关回归 275 项通过，含既有双因子 ANOVA。Minitab 19.1 原生 GLM 使用响应 [4,6,7,8,10,12,15]、因子 [1,1,1,2,2,2,2] 和协变量 [1,2,3,1,2,3,4]，两项 Adj SS、残差自由度与预测 R² 匹配报告精度，七个拟合值绝对误差小于 1e-12。MiniJMP 使用首水平 0/1 参考编码，原生默认效果编码；有交互时低阶项的检验约定依编码。[Minitab 因子编码](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/anova/how-to/fit-general-linear-model/perform-the-analysis/specify-the-coding-scheme/)

- **S1 · F0-NEW-025**：单样本精确尾概率以泊松质量直接求和核对，零事件上界用闭式结果核对。双样本固定总事件数，用二项质量枚举和区间端点的尾概率校验，覆盖等率、不同暴露量及零事件。正态近似以正态积分和手算标准误核对。真实 Tk 菜单验证双入口、输入错误后可重试及来源表报告。Minitab 19.1 原生 `ONERATE 10 30; TEST 2; ALTERNATIVE 1.` 的样本率 3、95% 下限 2.15940、p 0.022 与 MiniJMP 一致到报告精度。`TWORATE 10 30 20 30; TEST 0; ALTERNATIVE 1.` 的样本率 3.0/1.5、率差 1.5、条件精确 p 0.006 和率差正态下限 0.492737 同样一致。双侧精确 p 使用等尾定义，厂商单样本使用似然比。MiniJMP 双样本近似检验采用对数率比 Wald，原生以率差计算 Z。[单样本方法](https://support.minitab.com/en-us/minitab/help-and-how-to/statistics/basic-statistics/how-to/1-sample-poisson-rate/methods-and-formulas/methods-and-formulas/) · [双样本方法](https://support.minitab.com/en-us/minitab/help-and-how-to/statistics/basic-statistics/how-to/2-sample-poisson-rate/methods-and-formulas/methods-and-formulas/)

- **T1 · F0-BASE-017**：移动平均以直接窗口求和、简单指数平滑以闭式加权和、双指数平滑以精确线性序列、加法及乘法 Winters 以逐期独立标量计算核对。共 263 项时间序列测试通过，含真实 Tk 分析、绘图、新表与导出流程。Minitab 19.1 原生 MA / SES / DES 在同一组 12 个观测上，一期拟合和三步预测一致（绝对误差小于 1e-12）；MA 与 SES 残差按相同拟合计算。加法 Winters 原生预测 34.826519、36.426928、41.001028，MiniJMP 为 31.869948、34.641288、40.037308，初始化约定不同。原生乘法及 22 实机未测。[Winters 递推与厂商初始化](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/time-series/how-to/winters-method/methods-and-formulas/methods-and-formulas/)
- **D1 · F0-NEW-006 / 008 / 009**：逆堆叠以独立 pandas 切片与对齐验收，含标签冲突、缺失和大整数；抽样和生成检查固定种子、逐行配对及无放回约束；三类分布和边界以 SciPy 核对。相关测试共 188 项通过（含修订帮助主题数量后复验）。真实 Tk 经菜单写新表及当前表新列，源列保持原值。19.1 原生验证不等长逆堆叠、两种抽样和正态生成的固定种子复现，以及正态 PDF 和二项 CDF 数值。泊松逆 CDF 在 p=0/0.5/1 的原生结果是 0/2/缺失，SciPy 口径是 −1/2/+∞。[厂商逆 CDF 约定](https://support.minitab.com/en-us/minitab/help-and-how-to/probability-distributions-random-data-and-resampling-analyses/supporting-topics/data/why-the-icdf-may-not-exist/)
- **G1 · F0-NEW-038**：通用绘图器支持实时预览，验证真实 Tk 菜单、类型与变量更新、导出、确认与取消、切换来源表和鼠标交互。三组绘图测试合跑 61 项通过，动画停止与重启测试触发 3 秒超时；该动画测试在本次代码和改前基线单独运行均通过。帮助测试 14 项通过。变量推荐、拖放配置和多图候选布局保留为厂商功能差异。

- **G1 增强 · F0-NEW-038**：通用绘图器新增散点、折线、条形及直方图的 Plotly 试验引擎。Matplotlib 默认、来源绑定、正式图形确认及厂商功能差异沿用 G1。

- **DOE · SCR-002 / FAC-012**：DSD 新增 187 种混合配置；PB、正规部分因子、完整裂区支持连续 Foldover。分数裂区基础构造尚未建立。原生、独立参考及真实 Tk 工程往返见 [DOE 验收](../doe-minitab/acceptance.md)。两条均保留部分实现。


## F2 收尾核对（2026-11-24）

208 条综合记录和 80 条 DOE 专项记录均可解析，ID 无重复，DOE 引用有效。此次目标的 11 条记录中，7 条已实现，4 条保留部分实现。其余 14 条综合待核实记录仍沿用审计状态。

DOE 最终定向检查包含 Foldover、PB、裂区、帮助和报告清单，119 项通过。扩展 DSD 与项目持久化专项通过；F2 按工作包执行定向回归和实际 Tk 操作。Minitab 19 结果以固定案例为限。


## F2-Closure 独立验收（2026-11-25）

- FAC-012 完成正规部分因子和完整裂区连续两批往返。裂区两次折叠后的处理模型依次为 24、48 行，交叉积均为 nI，秩 4，无处理别名。保留分数裂区构造缺口。
- F0-BASE-025 图形多重比较支持不等组量，用独立最小二乘和正态极差积分验证。图形在 Tk 中随来源工作表发布。保留原生不等组校准缺口。
- F0-BASE-017 验证短周期加法初始化及乘法区间宽度，新增 Box–Cox 和常数／漂移搜索。乘法季节初值和原生自动 ARIMA 仍有证据缺口。
- SCR-002 覆盖 187 种新增混合配置，并冻结 11 组 19.1 编码点，详情见 [DOE 验收](../doe-minitab/acceptance.md#f2-closure--scr-0022026-11-25)。
- 208 条综合记录和 80 条 DOE 专项记录字段宽度一致、ID 唯一，已有 DOE 引用有效。四条覆盖状态仍为 partial。额外运行的 G9 冻结报告检查中出现 5 项失败，均用本轮开始时的 `89ab4b7` 源码重现。
- 项目 `.venv` 的收尾联合回归 741 项通过，覆盖多批折叠、方差检验、时间序列、扩展 DSD、真实 Tk 流程、帮助及报告清单。另有 DSD 既有设计、筛选分析和冻结参考组合 120 项通过。
- 更广的 PB／DSD 图形回归在 PB 参数化工程重开时遇到 Windows Tk 异常 `0x80000003`，该批次未完成。相邻三项 PB 40 运行数配置在独立进程中复跑通过。定向联合回归中的两项 DSD 工程往返和多批 Foldover 往返均已通过。

## F3-1 审计（2026-11-25）

从干净的 `e3ac3431b573804c3826a13ad0fb612299e154f5` 基线核查全部 14 条。Calculator 确认为已实现。工程、导航/命令/历史、集成、双样本方差、独立子组图、工作表合并共六项部分实现。Assistant、非参数检验、等效性、可靠性/生存、多变量四类分析、图形布局共六项未实现。GEN-013 的厂商自动排除并重拟合范围仍待核，DOE 专项范围及四条 F2 partial 保持原判定。

定向测试 318 项通过，真实 Tk 合并固定案例通过。补充 Minitab 19.1.0.1 的工程往返、列计算、方差比、独立控制图、多种推断、右删失拟合及两种合并方式。文档、原生证据和仍有缺证的分支见 [F3-1 审计](f3-1-feature-audit.md)。
