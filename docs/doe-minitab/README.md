2026-10-28 工作包 C 实施：PB 与 DSD 已有有限范围的生成、分析及工程工作流；详细范围、独立验证和未完成验收见 [工作包 C 收尾记录](work-package-c-closeout.md)。这些构造不是 Minitab 导出，尚未验证产品标准序。

2026-10-28 用户批准将 ACC-022 分为数学及工程子验收 ACC-022A（Level 1 必需）和 Minitab 一致性子验收 ACC-022B（不阻断功能 Review），父编号和 CSV 映射不变。022A 本地通过；022B 已在用户提供的 Minitab 22 五种设置下证实数学等价，标准序不同。

> 工作包 B 当前范围：ACC-021、ACC-022A/022B、ACC-023～030 的本地代码、数学及工程回归按本轮 closeout 记录验收；正式完成仍需取得新的独立 Review 通过记录。ACC-022B 只适用于用户提供并确认版本为 Minitab 22 的五种矩阵配置。五种设计点及区组重编号后的点–区组多重集等价，但标准序分别有 60、116、123、120、163 行不同，不表示逐行一致或可外推至其他版本/设置。

> CCD 区组设计的“默认”中心点数随布局自动计算并显示；显式整数只有与布局要求一致时才可创建。响应面图的 X/Y 轴只接受连续因子，分类因子作为可选固定水平传入模型。当前帮助与联合验收见 [B+C 收尾记录](work-package-bc-review-closeout.md)。

2026-10-28 后续补全：6/8/9/10 因子 CCD 的真实 Tk 工程保存、关闭、重开、复制和分析已验证；五份 Minitab 22 参考及数学边界见参考核验页。

## 范围与基线

当前 DOE-3 支持 2–10 连续因子范围内受支持的 CCD 全因子/分数、分类及区组，以及 3–7、9–10 连续因子 BBD；8 因子 BBD 未支持。DOE-4 对校验完整的 CCD/BBD 支持单、多响应优化及分类切片、参考区组；搜索不保证全局最优。具体配置限制以 B 收尾和帮助为准。

本目录记录 MiniJMP 已接受的 DOE-0～DOE-4 基线，与 Minitab Statistical Software 在线帮助所描述功能的逐项对比。官方资料核查日期为 2026-10-27；网页未标明产品版本，因此版本记为 unknown。未使用 Quick Designs、Minitab Workspace 等未确认属于本对标范围的产品专属能力。

> 历史基线（2026-10-27）：main，HEAD fd76b69b59f98d11751074a2d68e1b396f11773a；当时工作区干净，未拉取远端。此快照不代表当前 Git 状态。

## 历史 DOE-0～DOE-4 基线能力

- **DOE-0：设计数据合同。** DOE 定义、运行 ID/顺序、因子设定、响应映射和工作表指纹保存于 .dexpl；旧工程没有 DOE 元数据时维持旧加载行为；复制工作表保留并校验映射。
- **DOE-1：两水平全因子。** 2–6 个连续因子，可含独立重复与中心点；运行总数上限 10,000。支持因子/交互分析和部分推断；无纯误差或模型饱和等情形不能推断。
- **DOE-2：正规部分因子。** 3–6 个连续因子、正生成元、分辨率至少 III、独立重复；按别名组报告效应。没有负生成元、中心点、区组、PB 或非正规分数支持。
- **DOE-3：CCD 与响应面。** 2–5 个连续因子，支持面心 CCF 与旋转 CCC、中心点、完整二次模型、残差/响应面图及现有工程保存恢复；不支持区组或 BBD。
- **DOE-4：响应优化。** 仅接受完整 CCD；单响应最大化/最小化/目标逼近，多响应加权几何期望；在声明的编码 bounds 中确定性多起点搜索。搜索不是全局最优证明，功能不写回试验数据。

除历史正规部分因子路径外，现有 PB 和 DSD 的有限筛选路径见工作包 C 收尾记录。Mixture 和 Taguchi 尚无 DOE 专属入口或模型实现。

## 矩阵统计

以下计数直接来自 feature-matrix.csv，合计 80 项；没有使用功能百分比。

| 类别 | 已实现 | 部分实现 | 缺失 | 未知 | 排除 | 合计 |
|---|---:|---:|---:|---:|---:|---:|
| Screening | 0 | 5 | 2 | 0 | 0 | 7 |
| Factorial | 5 | 4 | 10 | 0 | 0 | 19 |
| Response surface | 13 | 0 | 2 | 1 | 0 | 16 |
| Mixture | 0 | 0 | 13 | 0 | 0 | 13 |
| Taguchi | 0 | 0 | 11 | 0 | 0 | 11 |
| DOE 通用能力 | 2 | 2 | 7 | 2 | 1 | 14 |
| **合计** | **20** | **11** | **45** | **3** | **1** | **80** |

每行都有稳定 feature_id。RSM-002 已实现 9、10 因子 BBD，用户提供的 Minitab 22 五种配置经重排数学等价；RSM-005（自定义响应面定义）、RSM-016 未实现，RSM-009（预测/置信区间）仍未核实官方范围。验收范围与当前证据见工作包 B 收尾报告。

### 矩阵字段解释

- 状态沿用矩阵定义：implemented 表示该行限定范围已有源码、测试等充分证据；partial 表示只实现其中一部分；missing 表示没有对应实现；unknown 表示证据不足；excluded 表示有明确范围排除。implemented 不代表整个 DOE 类别已经对标完成。
- 优先级 P0 对应 Level 1；P1 对应 Level 2；P2 为范围尚未确认或明确不纳入当前对标的候选项。
- 代码证据用相对路径与符号定位；测试证据列出当前专项测试或说明未发现对应测试。verification_status 用于说明本地实现证据、官方来源证据或二者之间的限制。
- gap_type 用分号分隔，可包含设计生成、统计模型/推断、优化、可视化、GUI、持久化、验证、文档或范围限制。

## 已确认缺口与主要技术风险

- **筛选设计：** PB 已覆盖九种官方基础运行数；DSD 的多分类组合、部分选项及产品一致性尚未覆盖。筛选二元响应与自定义筛选设计定义未实现。
- **因子设计：** General Full Factorial、多水平/分类因子、区组、split-plot、foldover、增加运行、二元响应和变异性分析缺失。Minitab General Full Factorial 将所有因子视为 categorical；数值水平只是离散水平标签，不是连续变量的多项式回归。FAC-009 seed 总体顺序随机化已实现；区组/裂区受限随机化另列为 FAC-019。
- **响应面：** 工作包 B 已实现 BBD、CCD 分数/区组、类别因子、模型项选择、点预测、多响应叠加等高线、CCD/BBD 单/多响应优化与逐项诊断。仍缺自定义响应面设计与官方未核实的预测/置信区间。
- **Mixture / Taguchi：** 没有组分和约束、Scheffé 类混料模型、Taguchi 正交表、S/N 或噪声因子分析。
- **实验设计与功效：** 没有 D-optimal 或 distance-based 候选点选择、最优设计评估/增补、DOE 功效与样本量。Minitab 的 D-optimal 适用于 Factorial、Response Surface 和 Mixture；distance-based 只适用于 Response Surface/Mixture。
- **持久化架构：** 工作包 C 将 DOE schema 升到 v3，新增筛选设计族、矩阵身份与点类型；v1/v2 先校验原始摘要再升级，旧版软件不能读取 v3 工程。混料约束、裂区误差层级和增补 lineage 仍需另行定义。
- **统计证据：** 全因子分析器存在失拟 F/p 输出路径，而帮助与开发合同写明该推断尚未核验。通过独立数学案例和文档一致性审查前，不把此项视为已验收能力。
- **项目范围：** DOE-4 多响应搜索不保证全局最优；如实描述 MiniJMP 求解器的方法、可行域和限制即可，不把 Minitab 未承诺的全局保证当作差距。响应预测、统计推断和实验设计选点分别验收，不互相代替。

## Level 1：核心 DOE 对标

待开发能力逐项通过对应 MTB-DOE-ACC 验收。矩阵中已实现的 Level 1 项复用 DOE-0～DOE-4 已接受基线；仅在相关实现变化时做回归确认，不重复安排开发。

- Screening：Plackett–Burman、DSD 生成与连续响应分析、效应/别名解释及基础筛选图；SCR-001、SCR-002、SCR-003、SCR-006、SCR-007。
- Factorial：两水平全因子与部分因子、中心点/独立重复、seed 运行顺序、主效应/交互和可用时的 ANOVA；FAC-001、FAC-002、FAC-006、FAC-007、FAC-009、FAC-014、FAC-015、FAC-016。已实现基线项为 FAC-001、FAC-006、FAC-007、FAC-009、FAC-016、RSM-006、RSM-010、RSM-011、GEN-010。
- Response surface：CCD 与 BBD、完整二次模型、定义自定义响应面、点预测、contour/surface/overlaid contour、单/多响应优化和关键残差诊断；RSM-001、RSM-002、RSM-005、RSM-006、RSM-008、RSM-010、RSM-011、RSM-012、RSM-013、RSM-014、RSM-015。
- 自定义/最优设计：定义自定义两水平设计并进行 D-optimal 选点；FAC-011、GEN-003。
- 通用诊断与工程：跨分析器诊断、当前设计保存恢复和新设计 schema 兼容验收；GEN-009、GEN-010、GEN-011。GEN-010 已实现并纳入上述基线复用；FAC-015、RSM-015、GEN-009、GEN-011 的 Level 1 验收分别在 B/D/E 结束前完成，作为进入 F/G 的前置门槛。

Level 1 通过条件：清单中的每项有独立数值或设计矩阵参考；相关 GUI、异常和工程保存/重开/复制案例通过；所有结果与统计适用性边界一致。不能用“有菜单”“有模型代码”或 DOE-4 能给预测值替代这些验收。

## Level 2：主要 DOE 类别完整对标

在 Level 1 基础上，对矩阵中已由官方帮助确认的 Screening、Factorial、Response Surface、Mixture、Taguchi 与 DOE 通用能力提供完整工作流。至少包括：

- mixture：lattice/centroid/extreme-vertices 设计、比例约束、Scheffé 术语模型、推断、预测、优化及图形。
- Taguchi：静态/动态、官方核实的 2/3/4/5/mixed-level 数组、四类静态 S/N 及 adjusted 公式、均值/标准差、噪声因子稳健性和最佳设置。
- 通用流程：factorial 二元响应、DOE variability、设计显示/修改、foldover/增补、D-optimal 选择，以及仅适用于 Response Surface/Mixture 的 distance-based 选择；Factorial 只支持 D-optimal。还需验收区组/裂区受限随机化、设计功效/样本量、跨类型诊断和持久化。
- 全部纳入功能有对应独立数学参考、边界处理、GUI 流程和工程恢复验收；没有未说明的阻断差异。

**明确排除或待核实：** A/G/I-optimality 不列为 Select Optimal Design 的选点准则；Minitab 结果页可报告 A/G 等诊断统计量。自动 DOE 异常值删除、通用 sequential-design 命令、预测/置信区间的具体适用范围仍未确认。自定义 screening design 已确认是官方功能，MiniJMP 尚未实现，安排后续工作包 E。Quick Designs 或 Workspace 独有功能、复制 Minitab 专有界面/商业算法也不纳入。

## 后续顺序

A 已交付；B 和 C 的本地证据与未完成范围见联合收尾记录。独立 Review 尚待单独发起和通过；本次不启动 D。

## 文件

- [功能矩阵](feature-matrix.csv)
- [验收规范](acceptance.md)
- [路线图](roadmap.md)
- [来源与核查记录](sources.md)

