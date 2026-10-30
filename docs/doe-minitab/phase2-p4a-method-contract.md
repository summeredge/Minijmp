# P2-4A 方法合同：DSD Stepwise 与 PB Foldover

日期：2026-10-29。Goal `DOE_PHASE2_P2-4A_SCREENING_ENHANCEMENT`。本文件冻结支持范围与实现合同；数值标准来自独立参考，不来自 Minitab 产品输出。

## 1. 官方来源与可用性

| 主题 | 官方页面 | 该页面实际支持的内容 | 不宣称的内容 |
|---|---|---|---|
| DSD Stepwise | [Methods and formulas for stepwise](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/screening/analyze-screening-design/methods-and-formulas/stepwise/) | Stepwise 是 forward selection 与 backward elimination 的组合；每一步先计算模型中各项的 F 与 p，若存在 p > Alpha to remove 则删除 p 最大的项，无法删除才尝试加入；加入检验的 F 使用**加入后**模型的 MSE | 页面未标产品版本；未给出 Minitab 22 的逐项数值或默认 alpha |
| DSD Stepwise 选项 | [Perform stepwise regression](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/screening/analyze-screening-design/perform-the-analysis/perform-stepwise-regression/) | 方法分为 None / Forward information criteria / Stepwise / Forward selection / Backward elimination；可选潜在项、初始项（I）与强制项（E）、Alpha to enter/remove、层级约束 | 页面同时描述信息准则与独立 forward/backward 模式；本包**只实现 Stepwise**，其余模式不得据同一代码路径标记为已支持 |
| Fold design | [Fold design](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/factorial/display-and-modify-design/perform-the-analysis/fold-design/) | 可折叠因子设计、PB 设计与裂区设计；全部折叠提升整体分辨度；单因子折叠提升该因子相关分辨度；有时折叠只是增加重复 | 本包只做 PB 的全部/单因子折叠；不实现裂区折叠 |
| What is folding | [What is folding?](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/supporting-topics/factorial-and-screening-designs/what-is-folding/) | 折叠把数据复制到原数据下方，再翻转指定因子符号；PB 与分数因子都可折叠；define relation 缩短的规则针对正规分数设计 | **PB 没有正规 defining relation**，本包不使用该规则推断 PB 别名 |

结论：官方页面提供方法结构与折叠变换定义，未提供 Minitab 22 的逐项数值输出。本包因此以独立数学参考作为验收标准，不声明版本一致。

## 2. DSD Stepwise 合同

### 2.1 入口与参数

新增 `code/doe_stepwise.py::select_dsd_stepwise(frame, metadata, response, ...)`。参数：

- `alpha_enter`、`alpha_remove`：默认 **0.15**（MiniJMP 开发合同默认值，非厂商默认配置）。
- `candidates`：候选项（主效应、连续因子平方项、二因子交互），缺省为「主效应 + 连续平方 + 全部二因子交互」。
- `initial`：初始项；`forced`：强制保留项。两者必须是 `candidates` 的子集。
- `max_steps`：迭代预算，缺省 200。
- 候选项上限 64；超限直接拒绝，不静默丢弃。

截距恒包含；有区组时区组调整列恒包含且不可移除。不纳入三阶及以上交互。

### 2.2 层级与可估计性

每个候选状态都必须满足强层级：`A²` 需 `A`，`A*B` 需 `A`、`B`。实现按「逐步解除层级」处理：

- 加入：仅当加入后整体层级合法（父项已在模型中）才允许。
- 删除：删除后若仍有高阶项失去父项，则该项不可删除。
- 强制项不可删除；若用户需要高阶项，须同时强制其父主效应。

每一步都以**实际模型矩阵**判定：秩、残差自由度、SSE、MSE。候选若只增加 0 维（与已有列线性相关），记为不可估计，不生成 p 值。

### 2.3 状态机

按官方顺序，每一步：

1. 计算当前模型 MSE 与各可删除项的 `F_remove = ((SSE_(M−T) − SSE_M)/df_removed)/MSE_M`。
2. 若存在 `p_remove > alpha_remove`，删除 p 最大者；并列取候选项顺序最早者。
3. 否则计算各候选 `F_enter = ((SSE_M − SSE_(M+T))/df_added)/MSE_(M+T)`，要求 `df_added > 0`、`df_error >= 1`、`MSE > 0`。
4. 若存在 `p_enter < alpha_enter`，加入 p 最小者；并列取候选项顺序最早者。
5. 否则停止。

已访问模型集合用于检测循环（例如 `alpha_remove < alpha_enter` 时同一项反复进出）。

### 2.4 停止原因

`no_eligible_entry`、`selection_stable`、`residual_df_limit`、`rank_deficiency`、`zero_error_variance`、`iteration_budget`、`model_cycle_detected`。全部按真实发生条件报告，数值失败不得伪装成成功完成搜索。

内部状态 `no_eligible_removal`（当前模型没有可删除的合法项）不是终止条件：此时继续尝试进入，最终若也无法进入则报告 `no_eligible_entry`。合并只发生在互斥的内部状态之间，真实数值失败（秩亏、残差 df 不足、零残差方差）始终以自身原因报告。

### 2.5 结果与推断边界

返回 `method`、两个 alpha、`initial_terms`、`forced_terms`、`candidate_terms`、`selected_terms`、`selection_steps`（步号、动作、项、F、p、前后 SSE、前后秩、误差 df、当前项集合）、`stop_reason`、`iterations`、`final_rank`、`final_residual_df`、`selection_status`。

最终项集合再交给现有 `analyze_dsd()` 重新分析，编码完全一致。选择后的系数 p 值与置信区间沿用普通 OLS，属于**未校正模型选择偏差的名义统计量**，不得解释为独立确认性检验。

不实现：AICc/BIC、独立 forward/backward、LASSO、Elastic Net、Best Subsets、Bootstrap、交叉验证、缺失值插补、加权 Stepwise。

## 3. PB Foldover 合同

### 3.1 支持范围

PB12/20/24/28/32/36/40/44/48；连续两水平因子；单个原始批次；无中心点；无区组；无分类因子；一个完整重复；一次折叠；全部因子或一个因子；折叠后不超过 10,000 次运行。

不支持：中心点、分类因子、重复批次、分区组 PB、二次折叠、裂区折叠。原 PB 创建与分析范围不变。

### 3.2 变换

`X` 为原始编码矩阵；全部折叠 `X_fold = -X`；单因子折叠仅翻转该列。新增运行数 N，总运行数 2N。必须保证：每个新增运行对应唯一原始运行；折叠因子符号翻转；未指定因子保持；原始运行身份（`run_id`、`standard_order`、`run_order`、`replicate`、设定、实测与响应）不变；新增运行 `source_run_id`、`batch_id` 完整，响应为空。

响应与实测列优先沿用原 dtype：可空 dtype 与 `object` 原样保留；numpy `float64`/`int64` 无法表达新增空值，转为同域可空 `Float64`/`Int64`，原值逐项相等（整数不经过浮点）。其它无法承载空值的 dtype 直接报错，不静默丢值。

### 3.3 PB 混杂与可估计性

**PB 不是正规分数设计。** 不调用正规 defining relation 生成算法，也不把结果称作 PB 别名表。评估一律基于实际编码矩阵：

- `X_main` 与 `X_interaction` 的秩；
- 主效应调整投影 `P = (X_main'X_main)^+ X_main' X_interaction`（秩亏时报告零空间，并说明伪逆解不唯一）；
- 完全混杂指交互列落在 `span{截距 + 主效应}` 内：能精确等于某主效应列（或其反号，投影 ±1）时记为该主效应，否则记为在主效应空间内可完全解释；部分混杂为投影系数非零但仍有残差，两类分别计数；
- 折叠前后秩、可估计项与混杂变化的真实增减。

不报告「所有折叠都提高分辨度」；当折叠只新增重复点或未减少目标混杂时如实说明。不使用 Roman Numeral Resolution 作为 PB 的统一结论。

### 3.4 谱系与 Schema v5

复用 `DesignSpec.foldover_lineage`（`parent_design_id`、`batch_id`、`folded_factors`、`run_map`、`source_matrix_sha256`、`current_matrix_sha256`），不新增字段、不升级 schema。设计类型仍为 `plackett_burman`，因此谱系合法性由设计类型区分：`two_level_fractional` 为正规折叠，`plackett_burman` 为 PB 折叠。

`screening_matrix` 语义合同（原先含糊，本包固定）：

- `construction_id` / `source_kind` / `source_id` 始终描述**原始 PB 构造**；
- `matrix_sha256` 对 PB 折叠设计表示 **BASE 批次（原始 N 行）** 的身份摘要，等于父设计摘要；
- 折叠后完整 2N 行由 `foldover_lineage.source_matrix_sha256`（父）与 `current_matrix_sha256`（全部 2N 行）验证；
- 2N 行不得被表述为新的官方 PB 固定构造。

恢复时不能把摘要自洽当作折叠关系正确的证明。PB Foldover 必须逐个核对 `run_map`：BASE 来源与 FOLD1 新运行一一对应；所有因子是两水平编码；指定因子翻转，其余因子保持；新增点为 factorial，标准序紧接 BASE，重复、批次和运行 ID 符合构造。运行序字段必须构成 `1..2N` 的唯一排列；BASE 与 FOLD1 分别占 `1..N`、`N+1..2N`，FOLD1 按每个 Run ID 和固定 seed 重建。校验不依赖工作表物理行顺序，因此按标准序或运行序显示不改变设计身份。

Schema v5 未保存 Foldover 创建前的 BASE 运行序快照。对创建时已有的 BASE 顺序，只能验证它仍是 `1..N` 的排列并保留现值；若重算摘要与 fingerprint 后替换 BASE Run ID 的运行序，当前格式无法独立证明该历史改动是否合法。工作表物理行顺序会因显示重排而改变，不能用作历史执行顺序证据。上述限制不影响按固定 seed 独立验证 FOLD1；PB 专用规则不应用于正规 Fractional Foldover。

### 3.5 验证器与修改操作

恢复与分析时必须区分原始 PB、合法 PB 折叠、损坏 PB 折叠与原有正规折叠；拒绝伪造矩阵、批次、Run ID、符号、对应关系及可重建的 FOLD1 顺序。即使按非法矩阵重算 `current_matrix_sha256` 并重绑工作表 fingerprint，PB 逐运行折叠关系仍必须成立。

对已折叠 PB：不允许重新随机化改写照历史顺序的路径、不允许再次折叠、不允许通过通用增补绕开谱系；`replicate`、`augment` 与 `renumber` 一律拒绝。

## 4. 验收映射

| 验收 | 内容 | 主要证据 |
|---|---|---|
| P4A-ACC-01 | DSD Stepwise F 检验与逐步选择 | `tests/fixtures/doe_phase2_p4a_reference/dsd_reference.json`、`tests/test_doe_dsd_stepwise.py` |
| P4A-ACC-02 | DSD 层级、秩、边界与选择状态 | 同上边界用例 |
| P4A-ACC-03 | PB Foldover 矩阵与原始运行保留 | `pb_foldover_reference.json`、`tests/test_doe_pb_foldover.py` |
| P4A-ACC-04 | PB Foldover 混杂/可估计性与谱系 | 同上 + 损坏输入用例 |
| P4A-ACC-05 | GUI、生命周期与用户可见结果 | 真实 Tk 测试 |
| P4A-ACC-06 | `.dexpl`、Schema、帮助与跨模块回归 | 持久化与既有套件 |
