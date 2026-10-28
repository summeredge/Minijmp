# 工作包 C0 规格：Plackett–Burman 与 Definitive Screening Design

> 历史规格：SCR-005 后来已由官方页面确认，现为 missing 并规划后续 E，详见 [来源](sources.md)；本文保留当时的未确认记录。

> 后续实施状态见 [工作包 C 收尾记录](work-package-c-closeout.md)。本 C0 文件保留实施前规格和来源，不将原规划中的全部配置视为已实现。

> 状态：实施前规格。官方事实核查日期为 2026-10-28；Minitab 在线帮助未注明适用的软件版本。本文规定后续 C1–C3 的范围、接口、GUI 和验收，不代表 PB/DSD 已实现，也不单独构成 C0_READY。

## 1. 目标与边界

为 PB 生成、DSD 生成、DSD 连续响应分析、筛选效应图和混杂解释建立独立可验证的合同。工作包 C 只覆盖：

| Feature | 正式验收 | C 阶段 | 范围 |
|---|---|---|---|
| SCR-001 | ACC-001 | C1 | Plackett–Burman 设计生成及 PB 专属主效应/混杂解释 |
| SCR-002 | ACC-002 | C2 | Definitive Screening Design 生成 |
| SCR-003 | ACC-003 | C3 | DSD 连续响应分析 |
| SCR-006 | ACC-005 | C1、C3 | PB/DSD 筛选效应与图形 |
| SCR-007 | ACC-006 | C1、C3 | 混杂、别名和模型可估计性解释 |

SCR-004（二元响应）留在工作包 H；SCR-005 的官方范围尚未确认。工作包 C 不实现 General Full Factorial、foldover/增补、D-optimal、混料或 Taguchi。PB 的分析沿 Factorial 路径；不能把正规部分因子设计的完整别名组语义套到 PB 的部分混杂上。

本文件与 [Schema v3 方案](screening-schema-plan.md)、[验收规范](acceptance.md) 及独立参考目录配套。功能矩阵状态保持原样；规划和 fixture 不等于生产实现或最终 Review。

## 2. Minitab 官方支持范围

### 2.1 Plackett–Burman

Minitab Statistical Software 的 PB 创建支持 2–47 个两水平因子；基础设计运行数为 12–48 之间的特定 4 的倍数。可用 PB 运行数为 **12、20、24、28、32、36、40、44、48**。8 和 16 次不作为 PB 创建项，因为 Minitab 将对应两水平因子设计作为分辨率相同或更高的选择。因子数小于基础运行数，最多为 `runs−1`。[PB 设计说明](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/supporting-topics/factorial-and-screening-designs/plackett-burman-designs/)；[PB 创建概览](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/factorial/create-factorial-design/create-plackett-burman/before-you-start/overview/)

官方给出的构造说明：除 28-run 外，设计可由一列通过循环置换形成，再附加一行全负号；28-run 采用特殊的三块构造。40-run 设计由 20-run 设计重复得到。不得把 28-run 套入其他运行数的单列循环规则。12、20、24-run 设计中，每个主效应会与多个二因子交互部分混杂。官方表格是构造证据，不等于某个 Minitab 版本的完整工作表导出。[PB 设计矩阵表与构造说明](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/supporting-topics/factorial-and-screening-designs/plackett-burman-designs/)

PB 创建设计对话框提供基础运行数、每重复中心点数、重复数，以及是否将各重复分区组。中心点可用于检查总体曲率或估计重复中心的变异；两水平设计的中心点不能分别识别各平方项，平方效应仍彼此混杂。若含文本因子，中心点会按文本因子水平扩展。创建示例说明默认随机化；随机数种子的有效范围与完整 PRNG 复现合同仍需核实。[指定 PB 设计](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/factorial/create-factorial-design/create-plackett-burman/create-the-design/specify-the-design/)；[PB 创建示例](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/factorial/create-factorial-design/create-plackett-burman/before-you-start/example/)；[两水平筛选设计比较](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/supporting-topics/factorial-and-screening-designs/screening-designs/)

### 2.2 Definitive Screening Design（DSD）

Minitab DSD 支持 **2–48 个因子**；连续因子取低、中、高三个水平，分类因子限两个水平。设计用于筛选线性效应，并可考察平方项和部分二因子交互。连续因子单重复运行数完整映射见下一节。官方注明：设计含分类因子时，每个重复增加一次运行。[DSD 创建概览](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/screening/create-definitive-screening-design/before-you-start/overview/)；[可用 DSD 运行数表](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/supporting-topics/factorial-and-screening-designs/available-definitive-screening-designs/)

运行数表给出**全连续、单重复**的基础设计。若含分类因子，官方规则为每个重复增加 1 次；实现不得把全连续的运行数直接当成混合设计总运行数。全连续设计每重复含 1 个中心点；含文本因子时设计含 2 个中心/伪中心点。一个分类因子时两个可能的伪中心组合都会纳入；超过两个分类因子时，Minitab 使用迭代算法选择两个伪中心点，以降低线性系数方差。官方未公开该算法的完整构造、搜索顺序或平局处理。[DSD 创建统计量](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/screening/create-definitive-screening-design/examine-the-design/all-statistics/)；[DSD 模型矩阵方法](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/screening/analyze-screening-design/methods-and-formulas/model-information/)

创建选项包括重复数和区组数；随机化可设为区组内随机或标准序，并可指定随机数生成器 base 以复现运行序。结果表包含标准序、运行序、点类型、区组和因子列。已确认“有这些选项”，不据此推断全部区组数与设计族组合都有效。[指定 DSD 设计](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/screening/create-definitive-screening-design/create-the-design/specify-the-design/)；[指定随机化选项](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/screening/create-definitive-screening-design/create-the-design/specify-the-design-options/)

### 2.3 DSD 2–48 因子完整运行数表

下表逐个列出官方范围内的每个因子数；数值来自 Minitab 官方“可用 DSD”表，不由 `2k+1` 等经验公式外推。列中每个运行数均指全连续、单重复基础设计。

| 因子数 | 运行数 | 因子数 | 运行数 | 因子数 | 运行数 |
|---:|---:|---:|---:|---:|---:|
| 2 | 13 | 18 | 37 | 34 | 77 |
| 3 | 13 | 19 | 41 | 35 | 77 |
| 4 | 13 | 20 | 41 | 36 | 77 |
| 5 | 13 | 21 | 49 | 37 | 77 |
| 6 | 13 | 22 | 49 | 38 | 77 |
| 7 | 17 | 23 | 49 | 39 | 85 |
| 8 | 17 | 24 | 49 | 40 | 85 |
| 9 | 21 | 25 | 53 | 41 | 85 |
| 10 | 21 | 26 | 53 | 42 | 85 |
| 11 | 25 | 27 | 61 | 43 | 89 |
| 12 | 25 | 28 | 61 | 44 | 89 |
| 13 | 29 | 29 | 61 | 45 | 97 |
| 14 | 29 | 30 | 61 | 46 | 97 |
| 15 | 33 | 31 | 65 | 47 | 97 |
| 16 | 33 | 32 | 65 | 48 | 97 |
| 17 | 37 | 33 | 77 | — | — |

含分类因子的单重复基础运行数按官方说明为表中数值加 1；增加重复时以每重复基础运行数计算。应以实际生成矩阵复核中心/伪中心点、区组及运行序，不仅校验总行数。[官方完整分段表](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/supporting-topics/factorial-and-screening-designs/available-definitive-screening-designs/)

## 3. 官方分析入口与选项

### 3.1 PB：Analyze Factorial Design

Minitab 将 PB 分析归入 `Stat > DOE > Factorial > Analyze Factorial Design`；该分析器支持两水平因子、一般全因子、PB 和 split-plot。用户选择数值响应列、模型项、区组以及（有中心点时）中心点是否进入模型。项可按模型阶次选取，也可逐项指定；官方也提供协变量和逐步模型选择选项。[PB 分析路径](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/supporting-topics/factorial-and-screening-designs/plackett-burman-designs/)；[Analyze Factorial Design 概览](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/factorial/analyze-factorial-design/before-you-start/overview/)；[指定因子模型项](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/factorial/analyze-factorial-design/perform-the-analysis/specify-the-model-terms/)

官方结果选项包括 ANOVA、模型摘要、系数/效应、回归方程、alias 表、拟合与诊断及均值。图形包括 Pareto、正态/半正态效应图和残差图；残差图可选原始、标准化或删除残差，以及直方图、正态概率图、残差对拟合值/顺序/变量和 Four-in-one。分析选项含权重、置信区间水平/类型、Box–Cox 和均值表。PB 主效应与二因子交互存在混杂，结果必须结合实际矩阵解释；不能把系数标签当作单一因果效应。[Factorial 结果](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/factorial/analyze-factorial-design/perform-the-analysis/select-the-results-to-display/)；[Factorial 图形](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/factorial/analyze-factorial-design/perform-the-analysis/select-the-graphs-to-display/)；[Factorial 分析选项](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/factorial/analyze-factorial-design/perform-the-analysis/specify-the-analysis-options/)

两水平模型若饱和，常规残差标准化效应无法计算；Minitab 的 Factorial 效应图改用 Lenth PSE 参考线。MiniJMP 若实现该路径，须将它与基于残差自由度的 t/F/p 推断区分，并用独立公式和边界案例验收。[Factorial 效应图方法](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/factorial/analyze-factorial-design/perform-the-analysis/select-the-graphs-to-display/)

### 3.2 DSD：Analyze Screening Design

入口为 `Stat > DOE > Screening > Analyze Screening Design`。响应为数值列；选入多个响应时，Minitab 对每个响应分别拟合模型。Terms 对话框提供线性、线性加平方项等阶次预设，也允许逐项选择二因子交互；存在多个区组时可选择把区组纳入模型。[输入响应](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/screening/analyze-screening-design/perform-the-analysis/enter-your-data/)；[指定 DSD 模型项](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/screening/analyze-screening-design/perform-the-analysis/specify-the-model-terms/)

可选自动选模为 None、Forward information criteria（AICc 或 BIC）、Stepwise、Forward selection 和 Backward elimination；还能设定候选项、强制项、进入/移除 alpha、模型层级规则并显示每一步细节。自动选模属于探索流程；应显示最终模型及选模设置，不把选模后的名义 p 值表述为独立确认结论。[DSD stepwise 选项](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/screening/analyze-screening-design/perform-the-analysis/perform-stepwise-regression/)；[Minitab stepwise 注意事项](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/regression/supporting-topics/basics/using-stepwise-regression-and-best-subsets-regression/)

DSD 结果可显示 ANOVA、系数及 p 值、模型摘要（扩展表含 PRESS、AICc、BIC）、回归方程、alias 表、全体或异常观测的拟合/诊断和最小二乘均值。alias 表默认列二阶项关系，也可限定显示阶次。图形包括标准化效应 Pareto/正态/半正态图，以及残差诊断；当模型没有误差自由度时不绘制效应图。Options 含非负权重列、置信区间水平/类型、Box–Cox 和均值表。[DSD 结果选项](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/screening/analyze-screening-design/perform-the-analysis/select-the-results-to-display/)；[DSD 图形选项](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/screening/analyze-screening-design/perform-the-analysis/select-the-graphs-to-display/)；[DSD 分析选项](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/screening/analyze-screening-design/perform-the-analysis/specify-the-analysis-options/)

官方方法页说明 DSD 以设计矩阵拟合所选项，矩阵含常数、区组、平方和交互列；连续 DSD 基于 conference matrix。主效应不与二因子交互混杂，平方项不与主效应混杂；平方项与交互通常彼此部分混杂，具体可估计性仍取决于实际设计矩阵和所选模型。混合分类设计中，多个分类因子的伪中心构造会影响矩阵，必须针对实际矩阵重新计算秩和混杂。[DSD 模型矩阵与系数方法](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/screening/analyze-screening-design/methods-and-formulas/model-information/)；[DSD 设计性质](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/supporting-topics/factorial-and-screening-designs/definitive-screening-designs/)

## 4. C1–C3 分阶段交付与稳定接口

现有 DOE v2 的 `DesignSpec`、`FactorSpec`、`RunRecord`、`DesignResult`、工作表映射和指纹可作为公共结构起点；v2 的设计类型/点类型/字段集合是严格枚举，且当前生成与分析分发没有 PB/DSD 路由。具体 v3 字段、迁移和拒绝规则以[Schema 方案](screening-schema-plan.md)为准。不得因为已有正规部分因子分析而复用其完整 alias-group 估计语义。[当前数据合同](../../code/doe_core.py)；[现有生成/分析入口](../../code/doe_fractional.py)、[部分因子分析](../../code/doe_fractional_analysis.py)、[DOE 对话框](../../code/doe_dialog.py)

每个生成器采用现有函数式边界：输入经验证的设计定义及显式生成设置，返回 `(DataFrame, metadata)`；配套 validator 从工作表重建并核对完整矩阵、因子水平、点类型、运行顺序、重复/区组与矩阵身份。分析器只接受已恢复且验证通过的 `DesignResult`、响应列和模型/选模设置；分析输出至少包含模型项、秩、系数、拟合/残差、SSE、误差自由度、推断可用状态、混杂/可估计性及图形数据。响应统计量不回写为设计矩阵字段。

| 阶段 | 交付接口与职责 | 依赖及退出条件 |
|---|---|---|
| **C1 — PB** | `code/doe_pb.py`：`create_pb`、`validate_pb`、PB 主效应与基于实际矩阵的部分混杂；连接现有 Factorial 分析入口。设计类型稳定名 `plackett_burman`。 | 依赖冻结的 v3 公共元数据及已核验 PB fixture。PB 模型矩阵/投影独立于 DOE-2 完整别名组；ACC-001，并承担 ACC-005/006 中的 PB 案例。 |
| **C2 — DSD** | `code/doe_dsd.py`：`create_dsd`、`validate_dsd`；设计类型稳定名 `definitive_screening`。按官方范围生成连续三水平及有独立依据的两水平分类配置。 | 与 C1 可并行，前提是 v3 字段、矩阵身份、列映射和恢复接口先冻结。每个公开支持配置必须有独立矩阵/构造证据；ACC-002。 |
| **C3 — 连续响应与图形** | `code/doe_screening_analysis.py`：`analyze_pb` 与 `analyze_dsd` 分家族处理；DSD 提供模型项选择、效应/残差图、ANOVA、诊断和 alias/可估计性说明。 | 依赖 C2 稳定的恢复后矩阵与模型项编码；PB 分支消费 C1 的矩阵接口。C3 不实现二元响应；ACC-003、ACC-005/006。 |

C1 和 C2 可在公共 Schema/运行记录合同冻结、接口签名确认后独立开发；不能各自定义互不兼容的 metadata。C3 依赖稳定的行序、实际/编码因子值、分类水平顺序、点类型、区组/重复、响应列映射和矩阵摘要。别名/投影、模型秩、可估计性及推断可用状态从已验证矩阵和所选模型重算，不缓存为生产生成器自证的数据。

分析数值合同：令 `X` 为含截距、适用区组及选定项的真实设计矩阵，`n` 为有效完整响应行数，`r=rank(X)`。满列秩时估计系数；残差可由投影计算；误差自由度 `n−r` 为正、目标项可估、误差方差及统计量有效且模型误差假设成立时，才可提供基于残差方差的 t/F/p 与区间。零残差方差导致分母退化时须按具体统计量说明不可用，不伪造有限结果。饱和/零误差自由度时可报告可估系数和拟合，但不得伪造残差标准误或常规推断；PB 的 Lenth PSE 若实现，应作为单独方法标签。秩亏时拒绝完整系数解释，或只报告被证明可估的对比。缺失/非有限响应不得静默填补或删行；若后续支持删行，必须按剩余矩阵重新验证秩、别名和自由度。

## 5. GUI 与验收接口

当前 MiniJMP 使用单一“试验设计（DOE）”菜单，已有项目为 01–09 项；C 阶段保留现有顺序，按现有样式追加入口，不重排菜单或改造整体导航。PB 创建入口标明 Factorial/PB；PB 分析由现有“03 分析因子设计”按 `design_type` 分派到 PB 专属分析。DSD 创建入口标明 Screening/DSD，并新增“分析筛选设计”入口；不可误入 CCD/BBD 响应面预测、优化或等高线路径。[当前菜单](../../code/MiniJMP.py)

创建窗口需满足：

- **PB**：因子数与名称、两水平实际设定、允许的基础运行数、seed/随机化、重复、中心点及按重复区组（仅在官方确认并有矩阵证据时启用）。预览显示因子设置、StdOrder/RunOrder、点类型、重复、区组和总运行数。
- **DSD**：2–48 因子及连续/分类类型；连续 low/high（mid 由编码定义），分类恰好两个水平；根据因子类型显示对应基础运行数；重复、区组、随机化和 seed。混合分类配置在构造证据不足时禁用创建并说明缺少的配置，不按运行数猜矩阵。
- 两者均需先预览，确认后一次性创建工作表；取消不留半成品。动态因子编辑区可滚动，窄窗口下预览、创建、取消等主要操作始终可达。
- **分析窗口**：选择数值响应；显示设计族和可用项；DSD 允许主效应、平方、交互和区组按实际秩检查；显示系数/效应、模型摘要、混杂说明、图形与推断状态。PB 与 DSD 使用各自模型语义。响应或设计变化后重拟合，不展示过期分析。

下表细化正式验收编号；每项均需 STD、EDGE、GUI、PERSIST 四类证据。建议测试文件名与[验收规范](acceptance.md)保持一致。

| 验收 | 独立标准与边界案例 | GUI / 持久化完成条件 |
|---|---|---|
| **ACC-001 / C1** | PB12、PB20、PB28 等已固定矩阵：独立校验 ±1 平衡、截距/主效应正交、秩、容量和部分混杂投影；边界涵盖非法因子数/运行数/水平、seed 与不支持的中心点/区组组合。 | `test_doe_pb.py`；Factorial 创建预览/取消/创建和 PB 分析路由；保存、关闭、重开、复制及列名/顺序变更不误绑矩阵。 |
| **ACC-002 / C2** | 全连续 DSD 代表矩阵覆盖不同运行数段及低/高因子边界；核对水平、运行数、秩、主效应与平方/交互投影。混合分类只验已取得独立构造或导出证据的配置。 | `test_doe_dsd.py`；Screening 创建窗口连续/分类输入可滚动；预览、取消、创建；重开/复制保留标准序、随机运行序、类别映射、伪中心和区组。 |
| **ACC-003 / C3** | 固定 X 与解析响应核对系数、拟合、残差、SSE、rank、df 和适用推断；覆盖多响应、缺失/非法值、秩亏、饱和、模型项不可估和无误差方差。 | `test_doe_screening_analysis.py`；真实 Tk 选响应与模型项，检查结果/诊断状态；保存重开及复制后可重算，响应修改更新分析，设计/映射损坏时拒绝旧结果。 |
| **ACC-005 / C1+C3** | 人工解析响应核对 PB/DSD 效应大小、方向、图形数据及排序；零误差自由度时不伪造标准化效应，PB Lenth（若支持）单独验算。 | `test_doe_screening_gui.py`；核对 PB/DSD 分派、图轴/标签/排序、缺失推断提示；持久化后重分析且不使用过期响应。 |
| **ACC-006 / C1+C3** | 独立构造矩阵计算秩、交叉积/投影和零空间；检查 PB 部分混杂、DSD 所选模型平方/交互项、完全混杂、秩亏和符号。 | `test_doe_screening_alias.py`；按具体效应列明方向、混杂对象与可估计状态；重开/复制/安全列重排后映射一致，矩阵损坏即拒绝。 |

真实 GUI 验收必须由目标窗口和实际工作表完成，不能仅凭纯函数测试或菜单存在判通过。PERSIST 至少覆盖保存 `.dexpl`、关闭、重开、复制、响应后填/修改、列改名/重排、运行行顺序改变和损坏元数据。响应值变化只使分析结果过期；因子设定、矩阵摘要、点类型、区组或运行映射变化必须使设计验证失败或触发明确重建，不得静默改绑。坏元数据须在替换/覆盖工程文件前拒绝。

## 6. 尚未核实的事项与外部导出要求

以下均为未知/待验证，不得转成默认支持承诺：

1. **产品版本**：在线帮助未标明版本；不能把帮助内容归属到 Minitab 22 或某一当前发行版。
2. **PB 完整随机化合同**：创建示例说明默认随机化，但 PB 专属页面未明确随机 seed 的有效范围、随机算法版本及标准序逐因子列排列在不同版本间是否固定。
3. **PB 运行数/因子数与附加选项组合**：基础运行数及因子上限已核实；不是每个中心点数、重复数和分区组组合均有独立设计表。未核实组合先拒绝，不套用 2-level factorial 的限制猜测。
4. **DSD 混合分类矩阵**：额外运行数、两水平分类变量及伪中心规则已确认；超过两个分类因子的迭代分配细节、分类因子排列对点集的影响及精确矩阵未公开。官方运行数表不能充当该矩阵的 oracle。
5. **DSD 区组构造边界**：创建页面存在区组/重复设置，但每种因子数、混合类型下的合法区组数、区组点数及与矩阵正交性的逐项条件尚未完整核实。
6. **种子复现范围**：DSD 支持指定 random-generator base 并复现运行序；有效范围、不同版本 PRNG 是否一致及 PB 是否使用完全相同设置仍待确认。
7. **精确产品序**：公开示例展示标准序/运行序，但不能证明所有因子列次序、块内排序和随机运行序与未来 MiniJMP 逐点相同。
8. **统计细节**：官方说明所选 DSD 项可形成设计矩阵并给出估计/诊断，但 MiniJMP 仍须独立确定 rank tolerance、缺失值策略、秩亏时可估对比和各类模型项的推断可用条件；不得用 Minitab 输出代替独立 oracle。
9. **SCR-005**：官方筛选功能范围尚未确认，保持 unknown；需另行研究后才可纳入实现。

若要验收 Minitab 逐点或混合类别一致性，请导出原始工作表或提供可复现工程，并注明 Minitab 版本、PB/DSD 菜单、因子数及顺序、每个因子的类型与实际水平、运行数、重复数、区组数、中心/伪中心点设置、随机化开关和 seed。导出列至少包括 `StdOrder`、`RunOrder`、`PtType`、`Blocks`、全部因子列；混合 DSD 还需保留类别水平原文。未取得这些信息时，只报告已验证的数学性质，不声称 Minitab 点阵或运行序完全一致。

## 7. 官方来源索引

本文产品范围、菜单和分析选项均来自 Minitab 官方帮助：

- [Plackett–Burman designs](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/supporting-topics/factorial-and-screening-designs/plackett-burman-designs/)
- [Available definitive screening designs](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/supporting-topics/factorial-and-screening-designs/available-definitive-screening-designs/)
- [Definitive screening designs](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/supporting-topics/factorial-and-screening-designs/definitive-screening-designs/)
- [Screening designs](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/supporting-topics/factorial-and-screening-designs/screening-designs/)
- [Create DSD overview](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/screening/create-definitive-screening-design/before-you-start/overview/)
- [Analyze DSD model information and formulas](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/screening/analyze-screening-design/methods-and-formulas/model-information/)
- [Analyze Factorial Design overview](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/factorial/analyze-factorial-design/before-you-start/overview/)
