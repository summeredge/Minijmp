# DOE 对标后续路线图

> 2026-10-31 P2-6.5 更新：以下保留历史阶段记录；当前状态以 [最终综合验收](../../Out/p2_6_doe_function_completion/p2-6-final-acceptance.md) 和 [80项矩阵](feature-matrix.csv) 为准，历史的“当前/未实现/未提交”不代表本轮结束状态。

## DOE Phase 2 / P2-0 审计结论（2026-10-29，历史）

- A–H 已完成限定范围验收；H 本地收尾状态 `WORK_PACKAGE_H_APPROVED_SCOPED`，基线提交 `ed85429ed23c52a6b2a238ad86fc1517ace93ff6`。DOE Schema v5 不变。
- 以现有 `feature-matrix.csv` 的 **80** 项为审计基数：**58 implemented / 18 partial / 3 unknown / 1 excluded**。这些状态是 MiniJMP 既有功能矩阵的覆盖情况，**不是 Minitab 全产品实现百分比**。
- P2-0 已逐项审计 18 个 partial、3 个 unknown、1 个 excluded；优先考虑官方公开帮助可确认、可用独立数学和 GUI/工程测试验收的缺口。原状态不因审计而自动提升。
- **P2-1（P1）**：Mixture 最优设计选点与增补，重点 `GEN-004/MTB-DOE-ACC-056`、`GEN-006/MTB-DOE-ACC-058`；需区分 Mixture D-optimal 与 Distance-based、组分/过程/总量坐标、模型矩阵和父设计谱系。当前通用 distance 仅支持 RSM，混料响应 desirability 优化不代表最优实验设计。
- **P2-2（P1）**：连续响应 RSM 的均值置信区间、单次预测区间（`RSM-009`，当前 partial）与 DOE 诊断（leverage、Cook、DFITS 等）。CCD/BBD/custom 连续 RSM 已支持；区组区间、二元概率区间和 RSM Binary Response Optimizer 不在此范围，不套连续响应 PI。
- **P2-3（P2，`READY_FOR_INDEPENDENT_REVIEW`）**：多因子 Split-Plot、区组、受限随机化和对应分层推断，关联 `FAC-010/019/008/014/015`；本地验收完成，独立 Review 尚未执行。证据见 [P2-3 收尾](phase2-p3-closeout.md)；非平衡与 REML 保持范围外。
- **P2-4（P2）**：按官方确证配置逐项补 Screening stepwise、PB Foldover、Taguchi mixed array/交互稳健性、Mixture 多总量；不批量实施未知厂商选项。
- **P2-5（P3）**：在取得版本明确的 Minitab 22 设计导出或对照后，审查标准序、输出数值与展示格式；数学等价不等于产品输出一致。
- `GEN-012` 序贯实验策略和 `GEN-013` 异常值自动处理暂维持研究状态；`GEN-014` 其他选择准则维持 excluded，除非取得独立官方依据。
- 公开 Minitab 帮助不一定标明版本；本轮核对只构成**当前官方功能存在性证据**，不构成 Minitab 22 特定配置的实测 parity。
- P2-0 只完成差距审计、工作包规划与验收合同，**未启动 P2-1 实现、未运行新的 DOE 数值试验，也未改动功能矩阵状态**。完整规划稿文件名为 `phase2-gap-analysis.md`、`phase2-roadmap.md`、`phase2-acceptance.md`；本节先在本地既有路线图中固化摘要。

### P2-0 官方关键依据

- [Mixture 最优选点与增补](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/factorial/select-optimal-design/perform-the-analysis/select-optimal-runs-augment-or-improve-a-mixtures-design/)
- [D-optimal 与 Distance-based 方法](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/factorial/select-optimal-design/methods-and-formulas/methods-and-formulas/)
- [后拟合 Predict 区间与置信度选项](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/using-fitted-models/how-to/predict/perform-the-analysis/specify-the-confidence-and-prediction-intervals/)
- [Split-Plot 设计及重复选项](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/factorial/create-factorial-design/create-2-level-split-plot/create-the-design/specify-the-design/)
- [DSD Stepwise](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/screening/analyze-screening-design/perform-the-analysis/perform-stepwise-regression/)

### P2-1 实施文档重建（2026-10-29）

- P2-1 开始检查时，本地不存在 `phase2-gap-analysis.md`、`phase2-roadmap.md`、`phase2-acceptance.md`。依照本轮目标，现依据本节 P2-0 摘要、现有验收/矩阵、E/F/H 收尾材料和官方帮助重建；不声称读过或复原缺失原稿。
- 重建稿：[差距分析](phase2-gap-analysis.md)、[路线图](phase2-roadmap.md)、[验收合同](phase2-acceptance.md)。详细的 Mixture 模型/距离坐标及 RSM 区间、诊断计算合同见后续 `phase2-p1-method-contract.md`。

### P2-1 本地进度（2026-10-29）

- `P2-ACC-01/02/03/04` 的 Mixture 选点、固定父设计增补、GUI 和工程生命周期在本地通过；状态 `MIXTURE_OPTIMAL_READY_FOR_REVIEW`。具体测试分组及未覆盖范围见 [Phase 2 验收](phase2-acceptance.md)。
- D-optimal 使用 Mixture Scheffé 模型矩阵；Distance-based 显示组分边界与线性约束，并按实际组分比例及显式选择、归一化的过程/总量变量选点。增补保留全部父运行与响应，新增响应留空，复用 DOE v5 / Mixture Schema 1。
- P2 两单元均已达到本地验收：Mixture `P2-ACC-01/02/03/04` 与连续 RSM `P2-ACC-05/06/07` 通过，状态 `READY_FOR_INDEPENDENT_REVIEW`。矩阵当前 80 项：58 implemented、19 partial、2 unknown、1 excluded。`GEN-004/ACC-056`、`GEN-006/ACC-058` 仍为 partial：Mixture replace/improve 与版本明确的产品输出对照不在本次实现范围。最终独立 Review 已交给 ChatGPT Web 对话“MiniJMP开发实现2”，verdict 待回传。

---

> 2026-10-28 历史状态（H 当前状态见下方）：工作包 C 的有限 PB/DSD 范围见 [收尾记录](work-package-c-closeout.md)，验收仍为 partial。工作包 D 的限定范围 D0–D5 已完成，可提交独立 Review；部分 feature 仍为 partial，且尚无独立 Review 结论。工作包 G 的 G0–G6 限定范围已完成，schema v5 增加 Taguchi 身份，详见 [工作包 G 收尾记录](work-package-g-closeout.md)；H 仍未启动。下方标注为历史的 schema 审计记录 D 开始前状态。

## 管理规则

工作包固定为 A–H。A 已完成，当前矩阵 80 项；原验收编号保持稳定，自定义筛选设计追加 ACC-067。后续开发只实现矩阵中有官方证据的项目；先更新范围再开发。DOE-0～DOE-4 继续作为已接受基线，不改写成新阶段编号。

推荐顺序：A → B → C → D → E → F/G → H。F 与 G 的模型独立，可在数据合同决定后并行。工作包进入开发前，先将该包全部 MTB-DOE-ACC 编号绑定到具体实现分支与独立数值 fixture。没有数值参考、官方范围或 schema 兼容方案时，不进入实现。

## D 开始前的 Schema 审计（历史快照）

以下条目仅记录 D0 前的代码状态；已被后续 D1 的 schema v4 实现取代，不应作为当前能力描述。

### 可直接复用

- DOE schema v1 的 design_id、seed、response_names、运行 ID、标准/实际顺序、replicate、settings、实测水平和响应。
- worksheet_metadata / restore_design_result 的列映射、行位置、列指纹和输入摘要；worksheets.py 已将可选 DOE 元数据接入工程保存、加载和工作表复制。
- generators、defining_relations、aliases 可继续描述现有正规两水平部分因子；CCD 的 alpha、center_points、axial_points 可继续描述当前 CCD。
- 对没有 DOE 元数据的旧工程保留现有加载语义；坏元数据必须在替换当前工作簿前失败。

### 需要兼容扩展

- 当前 design_type 只接受 unspecified、two_level_full、two_level_fractional、central_composite；point_type 只接受 factorial、center、axial。新增一个枚举值不能默认视为旧版兼容，因为旧代码会拒绝未知值。
- 新字段、类别水平语义、混料约束、Taguchi signal/noise roles、裂区随机化单位、block error strata、设计增补 lineage 等需要明确 schema 版本与迁移策略。保存/重开/复制/重算都要覆盖 v1 旧工程。
- FactorSpec 有 categorical levels 的结构占位，但 DesignSpec 拒绝分类/混合设计；RunRecord 有 block 字段，但现有分析器拒绝非空 block。不要把两个字段当作已实现功能。
- DOE-0 定义了 DesignResult、ModelResult 和 OptimizationResult 数据合同，但当前生产分析/优化调用并不统一经过这些类型。扩展前先核实实际消费者，不能以类型存在推断公共 API 已稳定。

### 独立统计模型或算法

- DOE-1/2 的两水平对比和别名组方法可沿用，但 General Full Factorial、多水平/类别 contrasts、PB/DSD screening、二元响应 logistic、split-plot 误差层级、Scheffé mixture、Taguchi S/N、optimal-design criteria 和 power/sample-size 均是独立数学工作。
- DOE-4 优化响应预测，不是最优实验设计点选择。不可复用 DOE-4 的目标函数来宣称具备 optimal design。
- 历史全因子失拟推断与帮助说明曾不一致；D4 已按独立 pure-error 与区组分层参考修正，并同步更新帮助和验收。未提供独立纯误差时不输出失拟 F/p。

### D1 已交付（2026-10-28）

- DOE schema v4 增加强类型分类水平、设计构造版本、随机化单位、误差结构及严格 Foldover lineage 字段；v1/v2/v3 先按原字段和摘要校验，再迁移到 v4。旧版 MiniJMP 不能保证读取 v4 工程。
- General Full Factorial 支持 2–10 个因子、每因子独立的文字/数值水平、完整笛卡尔积、独立重复、seed、完整重复区组及 10,000 行前置限制。数字水平不被转成连续模型。
- 分类分析使用 sum-to-zero contrasts，输出模型项自由度、ANOVA、边际/组合均值及可用时的失拟 F/p；真实 Tk 创建、预览、取消、图形、保存/重开/复制/再分析已覆盖。
- 本地证据见 `tests/fixtures/doe_factorial_reference/`、`tests/test_doe_general_factorial*.py` 和 `tests/test_doe_factorial_schema.py`。Minitab 标准序与分析表格式尚未由导出核对。

## 工作包

### A — 功能矩阵与验收规范（已完成）

- **目标与 feature_id：** 建立官方功能范围和 MiniJMP 当前真实状态；覆盖矩阵所有 80 个 feature_id。
- **依赖：** 当前 DOE-0～DOE-4 代码、测试与工程基线；Minitab Statistical Software 官方在线帮助。
- **复用 / 文件：** 只读核对 code/doe_*.py、code/doe_core.py、code/doe_dialog.py、code/doe_optimize*.py、code/worksheets.py、help/pages/doe.html 与 DOE 专项测试；产物见本目录。
- **Schema：** 仅做 v1 兼容性分析，不修改。
- **关键风险：** 把“DOE-4 优化响应”误认为最优实验设计；把 schema 字段误认为用户功能；忽略独立数值参考。
- **GUI / 持久化：** 比对菜单、真实创建/分析路径和 .dexpl 保存、重开、复制证据；不只看核心函数。
- **独立案例：** 每项后续验收使用 acceptance.md 中唯一 MTB-DOE-ACC 编号及 STD/EDGE/GUI/PERSIST 案例。
- **完成定义：** README、feature-matrix.csv、acceptance.md、roadmap.md、sources.md 完整；来源范围未知处明确标记；结构检查通过。
- **进入下一包：** 先确定 schema 演进策略，且下一包所需官方来源及独立数学 oracle 已固定。

### B — 响应面设计扩展（限定范围本地验证完成，独立 Review 待完成；见 [收尾](work-package-b-closeout.md)）

- **目标与 feature_id：** RSM-001/002/003/004/007/008/012/013/014/015；补齐官方确认的 CCD 选项、BBD、RSM 预测/优化、多响应图形和 Level 1 诊断。RSM-005 自定义设计归工作包 E；RSM-016 二元分析归工作包 H。
- **依赖：** A；schema 扩展审查；DOE-3/4 通过范围与算法必须保留。
- **复用 / 预计文件：** code/doe_ccd.py、code/doe_rsm.py、code/doe_optimize.py、code/doe_dialog.py、code/doe_optimize_dialog.py、DOE 菜单/帮助/测试；新设计可独立模块，只有确认重复逻辑后再抽象。
- **Schema：** BBD 可复用一般运行行与响应映射，但需明确 design_type/point_type；CCD options 是否要新字段需先核实。类别因子、区组和设计来源若写入工程，需要兼容扩展。
- **关键数学风险：** CCD alpha/点数/旋转性；BBD 运行集和二次项秩；带区组或类别项的模型可估计性；模型项选择；推断 df；非凸优化不能宣称全局最优。
- **GUI / 持久化：** 创建预览/取消/确认、适用图形和预测、原有 CCD 工程保存重开复制、不同 RSM 类型不可误路由到 CCD 分析器。
- **独立案例：** ACC-021–030。特别用解析二次模型、BBD 独立点表、可精确求解的凹二次单响应与边界案例；不得把一般全局最优保证作为 Minitab parity 要求。
- **完成定义：** 每种设计创建矩阵/模型/图形/预测/优化/诊断能力分别满足对应 ACC；不适用状态明确；DOE-0～4 回归未改变旧语义。ACC-030 是进入 F/G 前置门槛。
- **进入下一包：** 新 RSM 类型可正确持久化并由 design_type 分派；模型估计性和输出字段完成审查。

### C — 筛选设计

2026-10-28 C0 技术准备与实施边界见 [C0 规格](work-package-c0-spec.md)、[参考核验](screening-reference-validation.md) 和 [Schema 方案](screening-schema-plan.md)。C1 为 PB，C2 为 DSD 生成，C3 为连续响应与图形；二元响应仍归 H。C0 的参考准备不改变功能实现状态，也不代表工作包 B 已通过独立 Review。

- **目标与 feature_id：** SCR-001/002/003/006/007；PB、DSD、连续响应、效应与混杂分析。SCR-004 二元响应归工作包 H；SCR-005 自定义筛选定义已由工作包 E 实现（ACC-067）。
- **依赖：** A 和 DOE 公共合同；保留 DOE-2 正规 fraction 算法供其原用途，PB/DSD 采用实际矩阵秩及投影，不将正规别名等式直接用于非正规设计。
- **复用 / 预计文件：** code/doe_fractional.py、code/doe_fractional_analysis.py、code/doe_analysis.py、code/doe_dialog.py、菜单、帮助、测试；PB/DSD 的点生成可分模块。
- **Schema：** 需新增 screening design type 及相应点结构；检查 design_type/point_type enum 和混杂元数据；二元响应不能挤入 continuous responses 语义。
- **关键数学风险：** PB 主效应与交互混杂；DSD 水平与矩阵性质；不把 alias-group effects 解读为单一真实效应；二元响应分离与稀疏事件。
- **GUI / 持久化：** PB 入口与 Factorial 菜单归属要与官方语义一致；DSD 预览与连续响应分析；保存和重开时来源设计与混杂关系可重建。二元响应不属于 C。
- **独立案例：** ACC-001–003、005–006；PB 用独立公开矩阵；DSD 用固定独立矩阵；回归与别名由独立矩阵核对。
- **完成定义：** 设计类型、可估计性、连续响应分析、图形和帮助限制分别验收；PB/DSD 不互相冒充。
- **进入下一包：** 新 screening 类型稳定保存和恢复；别名组显示和统计推断限制经独立复核。

### D — 因子设计扩展（D0–D5 本地完成，待独立 Review）

- **阶段进展（2026-10-28）：** D0–D5 的限定实现、独立数学 fixture、真实 GUI 和工程保存/恢复回归均已完成。Schema v4 支持一般全因子、带符号正规分数、中心点、有限 Foldover、完整重复区组和两因子平衡 Split-Plot；D4 已验证逐项 ANOVA、区组/裂区误差分母、纯误差/失拟边界和残差诊断图。区组仅按完整重复分配；Split-Plot 限两个因子；Foldover 未覆盖 PB/Split-Plot、重复批次及 Minitab 输出一致性。逐项范围见 [D 收尾记录](work-package-d-closeout.md)；独立 Review 尚未执行，不表示 APPROVE。
- **目标与 feature_id：** FAC-002、FAC-003、FAC-004、FAC-005、FAC-008、FAC-010、FAC-012、FAC-014、FAC-015、FAC-019；扩展部分因子、General Full Factorial、分类因子层级分析、区组、split-plot、foldover、受限随机化和因子效应/ANOVA。FAC-006/007/009 属 A 的已实现基线，D 只按需核对回归证据、不安排重复开发；FAC-011/013 属工作包 E；FAC-017/018 属工作包 H。
- **依赖：** A；DOE-1/2；C 可复用别名合同但不要求 PB/DSD 完成后才开始 General Full Factorial。
- **复用 / 预计文件：** code/doe_factorial.py、code/doe_fractional.py、code/doe_factorial_anova.py、各设计分析器、code/doe_core.py、code/doe_dialog.py、worksheets.py、菜单/帮助和测试。
- **Schema：** 多水平/分类 contrasts、blocks、whole-plot/subplot error strata、foldover ancestry 要区别建模；不可只设置 block 标签或追加工作表行。
- **关键数学风险：** 设计矩阵与 contrasts、区组 confounding、restricted randomization、裂区分母误差项、重复与重复测量区别、ANOVA/LOF 自由度。
- **GUI / 持久化：** 因子和水平动态输入；随机化受 block 约束；折叠/增补保留 parent run IDs、标准序和新增批次；老工程在取消/失败时不被覆盖。
- **独立案例：** ACC-007–011、013、015、017、018、066；包括 D=ABC 的正规分数、2×3 General Full Factorial、数值水平标签的分类 ANOVA、2×2 且 3 blocks 的 split-plot、解析交互效应与非法水平案例。ACC-012 仅回归核验既有总体 run order。
- **完成定义：** 各设计矩阵和推断按家族验收；诊断声明与帮助保持一致；未支持的条件明确拒绝。
- **本地收尾状态：** `WORK_PACKAGE_D_READY_FOR_REVIEW`。按 D 收尾记录保留 ACC/FAC 的 partial 状态和未验证选项；本路线图不据此自动启动后续工作包。

### E — 自定义及最优设计

- **阶段进展（2026-10-28）：** E0–E6 的限定实现、独立数学参考、真实 Tk GUI 与工程保存/恢复回归已完成。Schema v5 新增自定义 Factorial/RSM/Screening、显式模型项、最优选点与增补谱系；v1–v4 按原字段和原摘要校验后迁移。D-optimal 小候选集穷举、大候选集确定性贪婪+交换；Distance-based 仅响应面，Mixture 距离合同依赖 F 保持 partial。逐项范围见 [E 收尾记录](work-package-e-closeout.md) 与 [参考核验](optimal-reference-validation.md)；独立 Review 尚未执行，不表示 APPROVE。

- **目标与 feature_id：** SCR-005、FAC-011/013、RSM-005、GEN-002–006/009/011；自定义筛选/因子/响应面设计、增补、修改、候选集选择、D/距离准则、诊断和 schema 兼容。SCR-005 的验收合同见 ACC-067。
- **依赖：** A 与设计类型扩展策略；复用 B/C/D 已通过的模型矩阵和候选点验证，不自建平行响应优化接口。
- **复用 / 预计文件：** code/doe_core.py、实际设计 analyzer、worksheet metadata、workbooks 与 GUI；最优设计准则应是独立核心实现，不复用 DOE-4 搜索目标。
- **Schema：** arbitrary candidate rows、模型项、选中点、selection order、parent design 和 augmentation batch 需要清晰的可持久化结构；Level 1 schema 兼容方案须在开始 F/G 前通过。
- **关键数学风险：** rank deficiency；准则依赖所选模型；并列解与随机候选顺序；距离准则的定义需按官方方法固定。
- **GUI / 持久化：** 导入现有矩阵、候选点选择、设计质量展示、修改前后对照；增补后保存/重开/复制不丢父子关系。
- **独立案例：** ACC-014、016、054–058、061–063；小候选集穷举 D-optimal/distance-based oracle，结构化矩阵自定义定义与增补比较。
- **完成定义：** 每个准则明确数学目标、输入范围、并列解和失败状态；不以 solver succeeded 代替最优证明。
- **进入 F/G 的 Level 1 前置门槛：** FAC-015 的 factorial ANOVA（D）、RSM-015 的响应面诊断（B）、GEN-009 的跨类诊断和 GEN-011 的 schema 兼容均通过；GEN-010 的已实现持久化只做基线确认，不重复开发。
- **进入下一包：** 自定义输入与选中设计的 lineage 持久化兼容；上述 Level 1 门槛全部通过后，F/G 才开始开发。
- **本地收尾状态：** `WORK_PACKAGE_E_READY_FOR_REVIEW`。ACC-056/058 因 Mixture 距离合同与 Mixture 增补保留 partial（响应面的 distance-based 选点与增补已实现）；本路线图不据此自动启动 F。

### F — 混料设计

- **目标与 feature_id：** MIX-001–013；simplex lattice/centroid/extreme vertices、比例约束、过程/总量变量、Scheffé、分析、预测、优化和图形。
- **依赖：** A 与 schema 扩展决定；一般 worksheet/run 元数据可复用；不依赖 Taguchi。
- **复用 / 预计文件：** 新 code/doe_mixture.py 或现有架构中等价模块；code/doe_core.py、worksheets.py、菜单/帮助、专属 analysis/plot/dialog 测试。
- **Schema：** mixture components、sum constraint、bounds、amount/process roles、pseudo-component units 和混料点类型需有明确语义。
- **关键数学风险：** Scheffé 无截距的受约束模型、二次/更高阶项秩、极端顶点可行域、比例/总量换算和可行优化。
- **GUI / 持久化：** 组分比例不能被误当独立低/高水平；可行范围、trace/contour/surface/overlay、保存重开复制后约束一致。
- **独立案例：** ACC-032–044；三组分 simplex 标准集合、解析线性/二次 Scheffé 响应、不可行/退化区域。
- **完成定义：** 每类设计、模型、推断、预测、优化、图形独立验收；产品只声称实际实现的组分数/阶数/约束。
- **进入下一包：** mixture 设计合同与数值模型已稳定；Taguchi 使用共享 worksheet 持久化但保留独立模型。

**2026-10-28 实施结果（隔离 worktree）：** MIX-001～004、006～013 按限定范围 implemented，MIX-005 partial（总量固定、不支持总量随运行变化和复杂交叉设计）。新增 `code/doe_mixture*.py` 九个模块、混料菜单/帮助与 v4 适配；独立参考、数学/工程测试和真实 Tk 生命周期已完成。E 的最终 Schema、跨 E 联合回归与独立 Review 仍是集成门槛；未启动 G。

### G — Taguchi 设计

- **目标与 feature_id：** TAG-001–011；静态/动态设计、2/3/4/5/mixed-level arrays、S/N、均值/标准差、噪声稳健性和最佳设置。
- **依赖：** A 与 schema 扩展决定；可与 F 并行，不能复用 DOE-4 desirability 指数作为 S/N。
- **复用 / 预计文件：** 新 Taguchi 设计/分析模块、DOE 菜单/帮助、DOE worksheet save/load；专用 GUI 与独立测试。
- **Schema：** array identity/column allocation、control/noise/signal roles、重复观测结构及计算所得 S/N 响应需要存储而不覆盖原响应。
- **关键数学风险：** 每类 S/N 公式、动态斜率与残差、mixed-level orthogonality、噪声因子作用及重复数。
- **GUI / 持久化：** 只展示核实过的 arrays；响应采集、S/N 目标和噪声角色明确；工程恢复保持原始观测和计算状态一致。
- **独立案例：** ACC-045–053、064–065；固定官方 2/3/4/5/mixed-level arrays 与独立正交检验、手算四种静态 S/N 和 adjusted 公式、已知动态 signal-response。
- **完成定义：** 每种数组、静态/动态模型、汇总和预测分别通过；最终预测明确需要确认试验。
- **进入下一包：** 统计公式、输入 roles、存储结构和帮助范围均稳定；不扩大到未证实 array catalog。

### H — DOE 通用能力与完整性验收

- **目标与 feature_id：** SCR-004、FAC-017/018、RSM-016、GEN-007/008；横切二元/变异分析、功效及跨类别集成。Level 1 ANOVA/诊断/schema 已在 B/D/E 前置验收；GEN-002 的设计修改归 E。
- **依赖：** A 与所有已计划设计包的实际完成项；Schema 兼容策略必须在最早新格式落地前确认。
- **复用 / 预计文件：** code/doe_core.py、worksheets.py、DOE 各 analyzer/dialog、tests/test_doe_*.py、help/pages/doe.html、菜单索引及统计测试清单。
- **Schema：** 在既有字段能表达时复用；否则新增 versioned migration；前置的 GEN-011 策略必须在实现前确定；不得为包装当前结果引入无消费者的公共 ModelResult/OptimizationResult 使用层。
- **关键数学风险：** 功效公式、二元响应、Variability preprocessing、ANOVA/LOF 结论、分布假设和不可用推断边界。
- **GUI / 持久化：** 每种设计覆盖 create/cancel/analyze/plot/edit/source loss/save/reopen/copy；跨工作表绑定、旧工程加载和坏输入保护。
- **独立案例：** ACC-004、019–020、031、059–060；选择相应数学方法，不要求不适用项目通过无关检验。
- **完成定义：** 所有范围内工作包有 ACC 结果；矩阵状态为 implemented 或已明确 excluded；不存在未说明的 unknown/partial；Level 1/2 按 README 规则通过。
- **本地阶段结果（2026-10-29）：** H0–H6 的限定实现、独立 STD/EDGE、真实 Tk、Schema v5 `.dexpl` 往返、G12 清单及跨设计族回归完成；本地记录见 [H 收尾记录](work-package-h-closeout.md)。80 项矩阵当前为 58 implemented、18 partial、3 unknown、1 excluded；已有 partial/unknown/excluded 保留具体理由。H4 明确范围为二元 RSM 拟合/预测/概率图；官方后续 Response Optimizer 不在 H4 验收范围。
- **收尾状态：** `WORK_PACKAGE_H_APPROVED_SCOPED`；H0–H6 限定范围完成，上一轮 ChatGPT 独立 Review 为 APPROVE（限定范围），验证来源与未覆盖边界见 H 收尾记录。DOE Schema v5 不变；下一步建立 Minitab DOE 功能对标二期规划，二期尚未开始开发。
- **进入后续：** 只有完成上述门槛后，才可按已更新矩阵提出新的扩展范围；不自动扩大 A–H 以外的对标任务。

## 依赖图

A → B → C → D → E → (F 与 G 可并行) → H

C 与 D 在架构上可并行，因为 DOE-2 已有 alias-group 分析；推荐先完成 C 的 screening 需求定义，再由 D 统一普通 factorial 扩展。进入 F/G 前必须先完成 B、D、E 中列出的 Level 1 ANOVA、诊断与 schema 兼容门槛。H 只负责最终跨类别集成/完整性验收，不再承接这些前置项目。

# 2026-10-28：ACC-022 双层验收合同

RSM-002 的 Level 1 功能完成条件为 ACC-022A 数学和工程要求全部通过、代码及界面和帮助准确说明支持范围；ACC-022B 不阻断工作包 B 功能 Review。现已对用户提供的 Minitab 22 五种配置证实重排后的数学等价，标准序不同；父编号 ACC-022 不变，不外推其他版本与设置。

