# Minitab 官方来源与核查记录

## 产品范围与版本

- 调查对象：Minitab Statistical Software 在线帮助中以 DOE / Statistical Modeling 为路径的功能页。
- 核查日期：2026-10-27。
- 产品版本：官方页面未标明具体版本，均记录为 unknown；没有从页面外观或搜索发布日期推断版本。
- 官方入口：[Minitab DOE 标准设计目录](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/supporting-topics/basics/which-standard-designs-can-minitab-create/)。在线帮助列出 screening、factorial、response surface、mixture 和 Taguchi 类别。
- 产品边界：[Overview of Quick Designs](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/quick-designs/overview/) 将 Quick Designs 说明为 Minitab Statistical Software 中设计实验功能的一个子集。本对标不把 Quick Designs 子集以外的独立产品功能推定为通用命令，也不纳入 Minitab Workspace 功能。
- 资料访问方式：使用 agent-reach 网页搜索及网页阅读，沿 Minitab 官方 DOE 帮助导航核对。来源事实仅取自 support.minitab.com 官方页面。搜索受限时不从第三方摘要补齐缺失功能。

## 来源目录

| source_id | 官方页面 | 官方页面能支持的事实 | 相关 feature_id |
|---|---|---|---|
| M-01 | [Which standard designs can Minitab create?](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/supporting-topics/basics/which-standard-designs-can-minitab-create/) | 设计类别目录，覆盖五类 DOE 设计与各类标准设计入口。 | 全部类别 |
| M-02 | [Phases of a designed experiment](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/supporting-topics/basics/phases-of-a-designed-experiment/) | 说明规划、筛选、优化和验证等实验阶段；本页不单独证明存在同名软件命令。 | GEN-012 |
| M-03 | [Overview for Display Design and Modify Design](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/factorial/display-and-modify-design/before-you-start/overview/) | 设计显示、随机化、复制、重编号等可用操作因设计类型而异。 | FAC-008/009/013/019; GEN-001/002 |
| M-04 | [How Minitab stores design information in the worksheet](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/supporting-topics/basics/how-minitab-stores-design-information/) | 设计信息存于工作表，供 DOE 分析和绘图使用。 | GEN-010/011 |
| S-01 | [Overview for Create Definitive Screening Design](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/screening/create-definitive-screening-design/before-you-start/overview/) | 该页说明 DSD 因子范围为 2–48；连续因子三水平、分类因子两水平；具体适用的软件版本未标明。 | SCR-002 |
| S-02 | [Overview for Analyze Definitive Screening Design](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/screening/analyze-screening-design/before-you-start/overview/) | 确认筛选设计分析入口及其用途。 | SCR-003/006/007 |
| S-03 | [Screening designs](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/supporting-topics/factorial-and-screening-designs/screening-designs/)；[Definitive screening designs](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/supporting-topics/factorial-and-screening-designs/definitive-screening-designs/) | 讨论 DSD 与 Plackett–Burman 的筛选用途；没有据此推断所有筛选命令或自定义筛选功能。 | SCR-001/002/005/006 |
| F-01 | [Choose a factorial design](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/supporting-topics/factorial-and-screening-designs/choose-a-factorial-design/)；[Overview for Analyze Factorial Design](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/factorial/analyze-factorial-design/before-you-start/overview/) | 列出两水平全/部分因子、split-plot、Plackett–Burman、general full factorial；Factorial 分析页给出设计类型范围与菜单归属。 | SCR-001/007; FAC-001–010/014–017/019 |
| F-02 | [Overview for Define Custom 2-Level Factorial Design](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/factorial/define-custom-factorial-design/define-custom-2-level-factorial/before-you-start/overview/) | 定义工作表中已存在的两水平因子设计；此页面不是任意类型自定义生成器证据。 | FAC-011 |
| F-03 | [Fold design](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/factorial/display-and-modify-design/perform-the-analysis/fold-design/) | Foldover 可用于 factorial、PB 和 split-plot；折叠全部或单个因子的定义不同，有些情况只增加重复。 | FAC-012 |
| R-01 | [What are response surface designs, central composite designs, and Box-Behnken designs?](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/supporting-topics/response-surface-designs/response-surface-central-composite-and-box-behnken-designs/) | 把 CCD 与 Box-Behnken 列为主要响应面设计。 | RSM-001/002 |
| R-02 | [Select a response surface design](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/response-surface/create-response-surface-design/select-a-response-surface-design/)；[Specify the design for Create Central Composite Design](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/response-surface/create-response-surface-design/create-central-composite-design/create-the-design/specify-the-design/) | 前者用于选择响应面设计；后者说明 CCD 的设计设置。具体未在页面核实的选项仍留给对应 feature 的范围复查。 | RSM-001/003/004 |
| R-03 | [Overview for Analyze Response Surface Design](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/response-surface/analyze-response-surface-design/before-you-start/overview/) | 确认响应面分析、曲率建模、预测/绘图/优化工作流；创建设计可选 CCD、BBD 或定义自定义响应面设计。 | RSM-005/006–008/010/011/013/014/015 |
| R-04 | [Overview for Overlaid Contour Plot](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/using-fitted-models/how-to/overlaid-contour-plot/before-you-start/overview/) | 列出 Response Surface、Screening、Factorial 和 Mixture 等模型/菜单；用途是多个响应可接受范围的可视化交集，并说明 contour/surface plot 等替代图形。 | SCR-006; RSM-010–012; MIX-013 |
| M-05 | [Overview for Create Mixture Design](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/mixtures/create-mixture-design/before-you-start/overview/)；[Overview for Analyze Mixture Design](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/mixtures/analyze-mixture-design/before-you-start/overview/) | 创建页列出 simplex centroid、simplex lattice、extreme vertices，可含 process/amount variables；分析页针对混合比例变化，可纳入过程变量与总量。 | MIX-001–009 |
| M-06 | [Perform a mixtures experiment](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/supporting-topics/mixture-designs/perform-a-mixtures-experiment/)；[Overlaid Contour Plot for Mixture Design](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/mixtures/overlaid-contour-plot/) | 混料实验流程列出 trace、contour/surface、Response Optimizer 和 Overlaid Contour 工作流。 | MIX-009–013 |
| T-01 | [Overview for Create Taguchi Design](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/taguchi/create-taguchi-design/before-you-start/overview/) | 区分静态设计、含 signal factor 的动态设计以及 control/noise factors。 | TAG-001–005/010/011 |
| T-02 | [Overview for Analyze Taguchi Design (Static)](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/taguchi/analyze-taguchi-design/before-you-start/overview-for-static-design/)；[Overview for Analyze Taguchi Design (Dynamic)](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/taguchi/analyze-taguchi-design/before-you-start/overview-for-dynamic-design/) | 确认静态与动态分析分别存在。 | TAG-002/006–009 |
| T-03 | [Methods and formulas for Analyze Taguchi Design](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/taguchi/analyze-taguchi-design/methods-and-formulas/methods-and-formulas/) | 列出 mean、signal-to-noise ratio、standard deviation 的方法说明。 | TAG-006/007/009 |
| B-01 | [Analyze Binary Response for Definitive Screening Design](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/screening/analyze-binary-response/before-you-start/overview/) | Screening 菜单下的 DSD 二元响应，输入事件数与试验数；PB 分析指向 Factorial 菜单。 | SCR-004 |
| B-02 | [Analyze Binary Response for Factorial Design](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/factorial/analyze-binary-response/before-you-start/overview/) | Factorial 二元响应分析覆盖两水平、general full 和 PB 设计。 | FAC-017 |
| B-03 | [Analyze Binary Response for Response Surface Design](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/response-surface/analyze-binary-response/before-you-start/overview/) | Response Surface 菜单的二元响应使用事件/试验数并支持曲率建模。 | RSM-016 |
| V-01 | [Overview for Analyze Variability](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/factorial/analyze-variability/before-you-start/overview/) | Factorial 菜单的 variability 分析针对重复或复制测量；需先预处理响应得到标准差。 | FAC-018 |
| O-01 | [Overview for Select Optimal Design](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/factorial/select-optimal-design/before-you-start/overview/)；[What is an optimal design?](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/supporting-topics/basics/what-is-an-optimal-design/) | 从候选运行中选择、添加、交换或评估设计；Factorial、Response Surface 和 Mixture 支持 D-optimality，distance-based 仅用于 Response Surface 和 Mixture。 | GEN-003–006 |
| O-02 | [Methods and formulas for Select Optimal Design](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/factorial/select-optimal-design/methods-and-formulas/methods-and-formulas/) | 说明 D-optimal 目标、初始化/改进流程、随机种子、交换/Federov 等选项；distance-based 的家族范围与选点步骤另见 O-03/O-04。 | GEN-003–006 |
| P-01 | [Overview for Power and Sample Size for 2-Level Factorial Design](https://support.minitab.com/en-us/minitab/help-and-how-to/statistics/power-and-sample-size/how-to/linear-models/power-and-sample-size-for-2-level-factorial-design/before-you-start/overview/) | 功效分析位于 Stat > Power and Sample Size；页面说明 2-level 输入，并列 PB 和 general full factorial 为替代分析。该功能不在 DOE 子菜单下。 | GEN-007/008 |
| P-02 | [Methods and formulas for Power and Sample Size for General Full Factorial Design](https://support.minitab.com/en-us/minitab/help-and-how-to/statistics/power-and-sample-size/how-to/linear-models/power-and-sample-size-for-general-full-factorial-design/methods-and-formulas/methods-and-formulas/) | 说明非中心 F 方法及重复数/目标功效的迭代求解。 | GEN-008 |

以上网页访问日期均为 2026-10-27，版本均未在对应页面标明。矩阵中的 reference URL 直接链接到相关页面；本表按 source_id 聚合功能映射。

## 补充的官方方法页

| source_id | 官方页面 | 追加确认内容 | 相关 feature_id |
|---|---|---|---|
| R-05 | [Blocks in a central composite design](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/supporting-topics/response-surface-designs/blocks-in-a-central-composite-design/) | CCD 可按 factorial/axial 点分区组；可用区组数取决于因子数、运行数与设计分数；重复与区组组合有不同语义。 | RSM-001/003 |
| R-06 | [Specify the design for Create Box-Behnken Design](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/response-surface/create-response-surface-design/create-box-behnken-design/create-the-design/specify-the-design/) | BBD 设置页涵盖中心点、区组、分类因子水平与重复等参数。 | RSM-002/003/004 |
| M-07 | [Methods and formulas for design information in Analyze Mixture Design](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/mixtures/analyze-mixture-design/methods-and-formulas/design-information/) | 给出 simplex centroid 点数和构造、simplex lattice 阶数/组分数表、extreme-vertex 算法名称、mixture/process/amount 类型及模型项；混料模型无普通常数项。 | MIX-001–006 |
| M-08 | [Coefficients table for Analyze Mixture Design](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/mixtures/analyze-mixture-design/interpret-the-results/all-statistics-and-graphs/coefficients-table/) | 由于组分比例依赖，总效应受约束；Minitab 不显示 mixture 模型主效应的 p 值。 | MIX-006/007 |

## Review 补充核查（2026-10-27）

| source_id | 官方页面 | 核实结论 | feature_id |
|---|---|---|---|
| F-04 | [Which standard designs can Minitab create?](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/supporting-topics/basics/which-standard-designs-can-minitab-create/)；[Specify the factors for Create General Full Factorial Design](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/factorial/create-factorial-design/create-general-full-factorial/create-the-design/specify-the-factors/)；[All statistics for Create General Full Factorial Design](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/factorial/create-factorial-design/create-general-full-factorial/examine-the-design/all-statistics/) | General Full Factorial 的 factors 是 categorical；可输入 text 或 numeric level labels。数值标签表示离散因子水平，不能据此把该设计描述为连续多项式/响应面模型。 | FAC-003/004/005 |
| T-04 | [Specify the type of design for Create Taguchi Design](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/taguchi/create-taguchi-design/create-the-design/specify-the-type-of-design/)；[Catalogue of Taguchi designs](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/supporting-topics/taguchi-designs/catalogue-of-taguchi-designs/) | 官方页面列出 2-level 2–31 factors、3-level 2–13、4-level 2–5、5-level 2–6、mixed-level 2–26（取决于 level mix）；具体可用数组以官方目录为准。 | TAG-003/004/005/010/011 |
| T-05 | [Methods and formulas for Analyze Taguchi Design](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/taguchi/analyze-taguchi-design/methods-and-formulas/methods-and-formulas/)；[What is the signal-to-noise ratio in a Taguchi design?](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/supporting-topics/taguchi-designs/what-is-the-signal-to-noise-ratio/)；[Select the options for Analyze Taguchi Design (Static)](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/taguchi/analyze-taguchi-design/perform-the-analysis/select-the-options-static-design/) | 静态四类为 smaller-is-better、larger-is-better、nominal-is-best (I)、nominal-is-best (II)。详细 formula 页面把 adjusted formula 放在 (I) 小节：S/N = 10 log10((mean² − s²/n)/s²)；(I) 基式为 10 log10(mean²/s²)，(II) 为 −10 log10(s²)。Methods 页概述句的 (II) 括号标注与其详细小节/其他官方页不一致，保留此来源冲突。 | TAG-006 |
| O-03 | [Design details for Select Optimal Design](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/factorial/select-optimal-design/interpret-the-results/design-details/) | 明确 Factorial 仅提供 D-optimality；Response Surface 和 Mixture 可以使用 distance-based。Mixture 距离设计需纳入全部 components，process variables 可选。 | GEN-003/004/005/006 |
| O-04 | [Methods and formulas for Select Optimal Design](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/factorial/select-optimal-design/methods-and-formulas/methods-and-formulas/) | Distance-based 初点：RSM 取距编码原点最远的候选点，Mixture 取距 pure component 最近的候选点；之后逐步加入距已选点集最远的点。该规则不使用 exchange method，且不复制选点。 | GEN-004/006 |

Minitab RSM overview 确认优化因子设置的工作流，但核查过的官方页面未作全局最优保证。因此矩阵不把全局保证列为待弥补功能；MiniJMP 应准确报告自身优化器的算法与搜索限制。

## 证据空缺与处理

工作包 B 实施期间按 R-01、R-02、R-03 与官方 BBD/CCD 页复核了本次落地范围，未新增未访问页面。实现与官方页面存在两处需要在验收报告写明的事实：官方 CCD 数据表中 3 因子单区组行内部不自洽（自报 14 个运行，但 8 个因子点加 6 个轴点为 14，而 alpha 列 1.682 与轴点数 0 互相矛盾），MiniJMP 保留既有 DOE-3 语义 2^k+2k+中心点；官方 BBD 数据表还列出 9、10 因子运行数，本实现只支持 3–7 因子。二者都作为范围限制记录，不据此扩展或删减验收。

- **未确认的软件版本：** 页面未注明适用版本；本次报告只能称为 Minitab Statistical Software 在线帮助基准，不能归属到某具体版本或本机安装。
- **未确认的命令/选项：** 独立的 custom screening design、预测区间、自动 DOE 异常值处理、通用 sequential-design 命令均未从已访问页面确认。矩阵使用 not_verified/unknown，禁止据此补造功能。自定义响应面定义已由 R-03 官方页确认。
- **筛选细节：** DSD 设计范围与因子水平在 overview 中有说明；本次没有固定完整 DSD 点阵算法、别名显示或全部模型项规则的官方方法页。后续要先锁定独立矩阵和页面。
- **自定义设计边界：** 已确认的 Define Custom 2-Level Factorial Design 是定义工作表中的既有设计，不代表所有设计类型都支持任意自定义生成。
- **最优准则：** D-optimal 适用于 Factorial、Response Surface 和 Mixture；Factorial 仅 D-optimal，distance-based 只适用于 Response Surface/Mixture。A/G/I-optimality 不作为选点准则；结果页可显示 A/G/V 等评估统计量，但这不代表支持用它们作为选点准则。O-04 记录 distance-based 起点和逐步选点方法，验收仍需独立小候选集复算。
- **搜索限制：** 定向搜索后 Exa 免费 MCP 返回 rate-limit 错误。已使用当时返回的 Minitab 官方页面和官方帮助导航继续核对；未用第三方摘要填补限制，因此未确认项保持 unknown。
- **Taguchi 数组目录：** 官方页给出 2/3/4/5/mixed-level 的因子数量范围；具体数组及 level mix 依官方目录，实施时按选定条目验收。
- **Taguchi adjusted 公式标记：** Methods page 概述句把 adjusted formula 标为 Nominal (II)，但详细公式和 What is S/N 页面将 adjusted mean/SD 公式放在 Nominal (I/default)；矩阵按详细公式行记录并保留文字不一致。
- **统计独立参考：** Minitab 帮助用于产品功能、输入和菜单范围，不作为 MiniJMP 数值正确性的唯一 oracle。现有 2×2 fixture tests/fixtures/doe_2x2_reference.json 可用于 DOE-1 解析检查；未来 PB/DSD、BBD、mixture、Taguchi、power 和 optimal design 需要在对应验收前新增可独立复核 fixture 或推导。
- **代码/文档冲突：** 当前全因子分析器存在失拟 F/p 输出路径，而 help/pages/doe.html 与开发合同写明失拟显著性未核验。DOE-1 失拟推断在独立复核并同步文档前不列为已验收能力。

## 重要产品归属差异

- Plackett–Burman 被 Minitab 的因子设计选择页列于 Factorial；DSD 则有 Screening 创建/分析路径。
- DSD、Factorial、Response Surface 各有二元响应分析入口；Variability 属于 Factorial 菜单，且输入依赖预处理标准差。
- DOE 功效/样本量位于 Power and Sample Size 菜单，而非 DOE 子菜单；它仍纳入本次 DOE 相关能力调查。
- Overlaid Contour 是可用于多个 DOE 模型类型的工作流，不等同于单响应等高线，也不等同于数值优化器。

# 2026-10-28：Box–Behnken 范围复核

- [Minitab Box–Behnken 设计汇总](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/supporting-topics/response-surface-designs/summary-of-box-behnken-designs/) 列出 9 因子 130 次和 10 因子 170 次，默认中心点均为 10；该汇总未给出点阵。
- [Minitab Box–Behnken 区组](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/supporting-topics/response-surface-designs/blocks-in-a-box-behnken-design/) 列出 9 因子 5 或 10 区组、10 因子 2 区组并声明区组正交；页面未给出区组分配矩阵。不能仅凭这些数量构造或验收标准设计。

