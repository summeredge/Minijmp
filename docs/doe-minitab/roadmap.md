# DOE 对标后续路线图

## 管理规则

工作包固定为 A–H。A 已完成，当前矩阵 80 项、验收编号 001–066；原 001–063 保持稳定，本轮新增 TAG-010、TAG-011、FAC-019 与 ACC-064–066。后续开发只实现矩阵中有官方证据的项目；先更新范围再开发。DOE-0～DOE-4 继续作为已接受基线，不改写成新阶段编号。

推荐顺序：A → B → C → D → E → F/G → H。F 与 G 的模型独立，可在数据合同决定后并行。工作包进入开发前，先将该包全部 MTB-DOE-ACC 编号绑定到具体实现分支与独立数值 fixture。没有数值参考、官方范围或 schema 兼容方案时，不进入实现。

## Schema 与现有代码合同

当前证据来自 code/doe_core.py、DOE 生成/分析模块和 tests/test_doe_core.py、tests/test_doe_persistence.py；本路线图不修改 schema。

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
- 全因子失拟推断存在代码/帮助说明差异，必须先按 MTB-DOE-ACC-018 独立核实，不把当前输出升级为通过依据。

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

### B — 响应面设计扩展（已完成，见 [work-package-b-closeout.md](work-package-b-closeout.md)）

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

- **目标与 feature_id：** SCR-001/002/003/006/007；PB、DSD、连续响应、效应与混杂分析。SCR-004 二元响应归工作包 H；SCR-005 尚未确认官方功能范围。
- **依赖：** A；DOE-2 现有正规 fraction alias 方法；建议先保留现有别名算法，再独立加入 PB/DSD 生成。
- **复用 / 预计文件：** code/doe_fractional.py、code/doe_fractional_analysis.py、code/doe_analysis.py、code/doe_dialog.py、菜单、帮助、测试；PB/DSD 的点生成可分模块。
- **Schema：** 需新增 screening design type 及相应点结构；检查 design_type/point_type enum 和混杂元数据；二元响应不能挤入 continuous responses 语义。
- **关键数学风险：** PB 主效应与交互混杂；DSD 水平与矩阵性质；不把 alias-group effects 解读为单一真实效应；二元响应分离与稀疏事件。
- **GUI / 持久化：** PB 入口与 Factorial 菜单归属要与官方语义一致；DSD 预览、分析项、二元响应事件/试验数；保存和重开时来源设计与 alias 可重建。
- **独立案例：** ACC-001–003、005–006；PB 用独立公开矩阵；DSD 用固定独立矩阵；回归与别名由独立矩阵核对。
- **完成定义：** 设计类型、可估计性、连续/二元分析、图形和帮助限制分别验收；PB/DSD 不互相冒充。
- **进入下一包：** 新 screening 类型稳定保存和恢复；别名组显示和统计推断限制经独立复核。

### D — 因子设计扩展

- **目标与 feature_id：** FAC-002、FAC-003、FAC-004、FAC-005、FAC-008、FAC-010、FAC-012、FAC-014、FAC-015、FAC-019；扩展部分因子、General Full Factorial、分类因子层级分析、区组、split-plot、foldover、受限随机化和因子效应/ANOVA。FAC-006/007/009 属 A 的已实现基线，D 只按需核对回归证据、不安排重复开发；FAC-011/013 属工作包 E；FAC-017/018 属工作包 H。
- **依赖：** A；DOE-1/2；C 可复用别名合同但不要求 PB/DSD 完成后才开始 General Full Factorial。
- **复用 / 预计文件：** code/doe_factorial.py、code/doe_fractional.py、code/doe_analysis.py、code/doe_fractional_analysis.py、code/doe_core.py、code/doe_dialog.py、worksheets.py、菜单/帮助和测试。
- **Schema：** 多水平/分类 contrasts、blocks、whole-plot/subplot error strata、foldover ancestry 要区别建模；不可只设置 block 标签或追加工作表行。
- **关键数学风险：** 设计矩阵与 contrasts、区组 confounding、restricted randomization、裂区分母误差项、重复与重复测量区别、ANOVA/LOF 自由度。
- **GUI / 持久化：** 因子和水平动态输入；随机化受 block 约束；折叠/增补保留 parent run IDs、标准序和新增批次；老工程在取消/失败时不被覆盖。
- **独立案例：** ACC-007–011、013、015、017、018、066；包括 D=ABC 的正规分数、2×3 General Full Factorial、数值水平标签的分类 ANOVA、2×2 且 3 blocks 的 split-plot、解析交互效应与非法水平案例。ACC-012 仅回归核验既有总体 run order。
- **完成定义：** 各设计矩阵和推断按家族验收；诊断声明与帮助保持一致；未支持的条件明确拒绝。
- **进入下一包：** 主流因子设计合同稳定，且不再用无结构的 unspecified 代表任意设计。

### E — 自定义及最优设计

- **目标与 feature_id：** FAC-011/013、RSM-005、GEN-002–006/009/011；自定义因子/响应面设计、增补、修改、候选集选择、D/距离准则、诊断和 schema 兼容。
- **依赖：** A 与设计类型扩展策略；复用 B/C/D 已通过的模型矩阵和候选点验证，不自建平行响应优化接口。
- **复用 / 预计文件：** code/doe_core.py、实际设计 analyzer、worksheet metadata、workbooks 与 GUI；最优设计准则应是独立核心实现，不复用 DOE-4 搜索目标。
- **Schema：** arbitrary candidate rows、模型项、选中点、selection order、parent design 和 augmentation batch 需要清晰的可持久化结构；Level 1 schema 兼容方案须在开始 F/G 前通过。
- **关键数学风险：** rank deficiency；准则依赖所选模型；并列解与随机候选顺序；距离准则的定义需按官方方法固定。
- **GUI / 持久化：** 导入现有矩阵、候选点选择、设计质量展示、修改前后对照；增补后保存/重开/复制不丢父子关系。
- **独立案例：** ACC-014、016、054–058、061–063；小候选集穷举 D-optimal/distance-based oracle，结构化矩阵自定义定义与增补比较。
- **完成定义：** 每个准则明确数学目标、输入范围、并列解和失败状态；不以 solver succeeded 代替最优证明。
- **进入 F/G 的 Level 1 前置门槛：** FAC-015 的 factorial ANOVA（D）、RSM-015 的响应面诊断（B）、GEN-009 的跨类诊断和 GEN-011 的 schema 兼容均通过；GEN-010 的已实现持久化只做基线确认，不重复开发。
- **进入下一包：** 自定义输入与选中设计的 lineage 持久化兼容；上述 Level 1 门槛全部通过后，F/G 才开始开发。

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
- **进入后续：** 只有完成上述门槛后，才可按已更新矩阵提出新的扩展范围；不自动扩大 A–H 以外的对标任务。

## 依赖图

A → B → C → D → E → (F 与 G 可并行) → H

C 与 D 在架构上可并行，因为 DOE-2 已有 alias-group 分析；推荐先完成 C 的 screening 需求定义，再由 D 统一普通 factorial 扩展。进入 F/G 前必须先完成 B、D、E 中列出的 Level 1 ANOVA、诊断与 schema 兼容门槛。H 只负责最终跨类别集成/完整性验收，不再承接这些前置项目。

# 2026-10-28：ACC-022 双层验收合同

RSM-002 的 Level 1 功能完成条件为 ACC-022A 数学和工程要求全部通过、代码及界面和帮助准确说明支持范围；ACC-022B 不阻断工作包 B 功能 Review。现已对用户提供的 Minitab 22 五种配置证实重排后的数学等价，标准序不同；父编号 ACC-022 不变，不外推其他版本与设置。

