# P2-4B/P2-4C 方法合同

日期：2026-10-30。Goal：`DOE_PHASE2_P4BC_TAGUCHI_MIXTURE_ENHANCEMENT`。本合同冻结本地扩展的数学定义、支持边界和安全停止状态；不声明 Minitab 22 数值或矩阵完全一致。

## 1. Taguchi 固定矩阵与列身份

固定矩阵逐行逐列取自 [Minitab Catalogue of Taguchi designs](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/supporting-topics/taguchi-designs/catalogue-of-taguchi-designs/)：

| 数组 | 运行数 | 官方列号及水平 | 允许的主效应列 |
|---|---:|---|---|
| `L8(4^1 2^4)` | 8 | 第 1 列四水平；第 2–5 列二水平 | 四水平因子仅放第 1 列；二水平因子放第 2–5 列 |
| `L16(4^1 2^12)` | 16 | 第 1 列四水平；第 2–13 列二水平 | 四水平因子仅放第 1 列；二水平因子放第 2–13 列 |
| `L18(2^1 3^7)` | 18 | 官方列号为 1–7、9；第 1 列二水平，其余七列三水平 | 每个声明的列对都须逐格检查，不能由数组名称推定整体正交 |

新增 L8/L16 只冻结目录列出的矩阵与主效应分配；本合同不外推交互作用表。每个矩阵独立核验运行数、水平频数、全部可用列对的组合频数、用户标签映射及完整矩阵 SHA-256。

Minitab 目录概述称各列平衡且正交，但 L18 表格自身不满足该概述。根据目录的 18×8 单元格统计，五个非正交列对为官方列 `(3,9)`、`(4,9)`、`(5,9)`、`(6,9)`、`(7,9)`；各对的 3×3 频数均不等于每格 2 次。当前内部矩阵位置 8 对应官方第 9 列；消息、帮助与界面显示官方列号，内部位置映射须由独立测试核实。继续拒绝上述列对，不改动原始矩阵行序。交互作用可估计性未由这些矩阵合同证明。

## 2. 静态 S/N、噪声条件和权重

响应必须全部为有限数值。每个控制组合单独计算 S/N；`n` 为实际响应观测数，SD 使用样本标准差（分母 `n-1`）。公式如下：

| 类型 | 公式 | 定义域 |
|---|---|---|
| Smaller | `-10 log10(mean(y²))` | 平均平方必须大于 0；响应可正、负或为 0 |
| Larger | `-10 log10(mean(1/y²))` | 每个响应不得为 0；倒数平方均值须为正有限值 |
| Nominal I | `10 log10(mean(y)² / s²)` | `n≥2`、`s²>0`、分子为正 |
| Nominal II | `-10 log10(s²)` | `n≥2`、`s²>0` |

Small/Larger 的非零常量数据允许 `SD=0`；Nominal I/II 的零样本方差按公式拒绝。调整型沿用现有 nominal-I 公式 `10 log10((mean(y)² - s²/n) / s²)`；Minitab 官方方法页在调整型对应的 Nominal I/II 标签上有不一致，来源差异保留，数学 oracle 按上述公式单独计算。

噪声条件以一条运行中声明的所有噪声因子实际水平元组识别；重复编号和 `run_id` 独立保留，重复观测不能增加噪声条件数。对每个“控制组合 × 信号水平（如有）”输出：

- 每个噪声设置的响应均值、可用的组内样本 SD、重复号、运行 ID 和观测数；
- 所有噪声设置与重复观测汇总得到的 Mean、样本 SD、指定公式下的 S/N；
- 各噪声设置响应均值的极差 `max(condition_mean)-min(condition_mean)`。

每个控制组合须至少包含两个不同噪声设置。控制水平响应表对控制组合等权；完整外表的观测数保持平衡。输出同时报告条件数和观测数，不把其中一个当作另一个。模型预测、实际噪声试验和未测组合明确区分。

## 3. 最佳设置选择

候选为所有声明控制因子水平的笛卡尔积。以响应表中每个控制组合的观测特征构造加性主效应预测；不拟合或暗示交互模型。组合数最多 20,000，按因子声明顺序、各因子水平声明顺序精确枚举；超过预算时在枚举前拒绝。

支持两个新增选择模式：

1. `sn_maximum`：最大化加性预测 S/N，保留所有并列组合。
2. `robust_then_target`：仅适用于静态设计；先保留预测 S/N 大于或等于用户阈值的组合，再从中选择预测 Mean 距离目标值最近的全部并列组合。若没有候选达到阈值，返回 `target_unreachable`，不改变目标、不回退成最大 S/N。动态设计保留目标斜率与动态 S/N；本地首版不把动态信号响应均值解释为目标函数。

并列比较只允许按浮点 ULP 与加性运算项数计算的舍入容差合并，不使用经验百分比。候选顺序和预算状态可复核。返回实际是否观测过该控制组合；未观测组合的预测不是试验结果。若加性 SD 预测为负或不可计算，SD 标为不可用。确认实测值只用于差值与目标容差显示，不写回原工作表。既有单指标 API 保留兼容。

## 4. Mixture 联合设计与模型

现有 DOE Schema v5 与 Mixture Schema 1 保持不变。旧 `construction_version=v1` 的 `amount_settings` 仍是所有运行共用的单一总量设定，必须原样恢复。

新增的多总量水平设计使用现有 `construction_version` 字段标记 `v2`，不向 `amount_settings` 写入水平列表：该映射仍保存一个默认预测/优化总量；2–3 个真实总量水平作为普通 DOE 运行设定保存在工作表矩阵并由输入 fingerprint 保护。恢复时从标准序读出总量水平，核验其为 2–3 个互异正数、位于声明范围内、水平间距大于数值校验容差、默认总量与其中一个水平精确相同，且每个混料点都与全部过程水平及总量水平完整交叉。v1 语义不变；不支持 v2 的旧程序会拒绝未知构造版本，不会把它读成固定总量设计。

Mixture v2 多总量范围：2–4 个组分、0–3 个两水平过程变量、一个总量变量、2–3 个正总量水平、完整交叉，最多 10,000 次运行。C1 的 Mixture+Process+Amount 联合组合要求 1–3 个过程变量；仅 Mixture+Amount 可不含过程变量。现有 v1 固定总量设计仍支持已声明的过程变量数量。混料比例 `Σxi=1`；总量 `T>0`；组分实际用量 `Ai=T×xi`。总量不参与混料比例和。固定 seed 可复现运行顺序；seed 不改变设计点集合。

默认联合模型无普通截距：

`Y = Σβi xi + Σβij xi xj + Σγik xi zk + Σδi xi a`

其中 `zk` 是过程变量按声明 low/high 映射到 `[-1,1]` 的编码，`a` 是总量按变量 low/high 映射到 `[-1,1]` 的编码。默认项覆盖组分一次项、所选 Scheffé 组分二/三次项、组分×过程项和组分×总量项；不加过程×总量或更高阶项。预测使用与拟合完全相同的项顺序与编码。

拟合按实际矩阵报告 `n`、项数、rank、条件数、系数可估计性、SSE、MSE、残差 df 和拟合值。秩亏的 v2 联合模型拒绝拟合、预测与优化；不以最小范数系数替代可估计性。优化只在用户明确固定的过程/总量条件下优化混料比例，SLSQP 收敛不构成全局最优证明。

## 5. Replace/Improve 与 Mixture metadata Schema 2

Schema 职责固定如下：

| 数据 | 版本 | 恢复用途 |
|---|---:|---|
| DOE metadata | v5 | 当前工作表 DOE 运行 ID、顺序、设定、行映射和输入摘要；本功能不升级 DOE Schema。 |
| MixtureSpec 内部 `schema_version` | 1 | 组分、过程/总量变量、约束和模型/构造定义；结构未变，不随顶层升级。 |
| Mixture metadata 顶层 | 1 或 2 | 普通设计与普通 append 使用 1；Replace/Improve 结果使用 2。 |
| `construction_version` | v1 或 v2 | 原构造语义不变；不是 Replace/Improve 标记。 |

Schema 1 的顶层字段仍严格为 `schema_version/spec/worksheet`。普通 v1/v2 设计保留既有结构检查；Schema 1 append 若 DOE v5 含有效 `augmentation_lineage`，先恢复 DOE 追加谱系，再逐行核验比例、变量范围和约束，不要求追加后的运行集仍等于原始完整交叉点集。未知版本或多余、缺失、错误类型字段均拒绝。

Schema 2 顶层字段严格为 `schema_version/spec/worksheet/improvement_lineage`。`spec.schema_version` 仍为 1，`construction_version` 保留源设计值。Schema 2 仅用于 Replace/Improve，不自动升级普通设计，也不伪装成 Schema 1。旧读取器遇到顶层版本 2 必须明确拒绝。普通 append 入口拒绝 Schema 2，避免丢失改善谱系；当前不支持连续嵌套多个 Improve。

`improvement_lineage` 的严格字段集合为：

`parent_design_id`、`parent_snapshot`、`parent_snapshot_sha256`、`parent_input_fingerprint`、`parent_response_snapshot`、`parent_response_sha256`、`locked_run_ids`、`replaceable_run_ids`、`retained_run_ids`、`candidate_design_id`、`candidate_snapshot`、`candidate_snapshot_sha256`、`candidate_input_fingerprint`、`candidate_run_ids`、`selected_run_ids`、`candidate_to_replaced_parent`、`criterion`、`model_degree`、`model_terms`、`candidate_matrix_sha256`、`parent_matrix_sha256`、`current_matrix_sha256`、`parent_rank`、`parent_logdet`、`current_rank`、`current_logdet`、`seed`、`evaluation_budget`、`actual_evaluations`、`stop_reason`、`global_optimum_proven`。

父与候选快照均为完整工作表矩阵及其 DOE v5、Mixture Schema 1 元数据；每个单元格以严格类型标签编码，快照随改善结果保存，恢复不依赖父/候选工作表仍存在。响应快照按原 Run ID 保留原响应值和数值类型，并单独校验 SHA-256。SHA-256 用于检测数据不一致，不是防恶意篡改的数字签名。

集合与映射的含义固定为：

- `locked_run_ids` 与 `replaceable_run_ids` 无重叠且恰好覆盖父设计全部 Run ID；默认 GUI 将所有行设为 Locked。有响应或 DOE 实测值的行自动受保护，API 也会拒绝替换。
- `candidate_run_ids` 是候选快照中用户纳入搜索域的源 Run ID；被选候选不能已出现在父设计设定中，搜索域内也不得有重复设定。
- `retained_run_ids` 是原样保留的 Locked Run ID；`selected_run_ids` 是改善后工作表中新增运行的当前 Run ID。改善后当前集合恰为 `retained_run_ids ∪ selected_run_ids`。
- `candidate_to_replaced_parent` 是一一映射记录，每项含 `candidate_run_id`、`selected_run_id`、`replaced_parent_run_id`。每个 Replaceable 父行恰好被替换一次；当前 DOE v5 中新增行占用对应被替换行的标准序/运行序槽位。候选源 ID 可与父 ID 重名；当前新增 Run ID 冲突时生成确定性的独立 ID。

只支持 D-optimal Replace/Improve。模型矩阵使用现有 `MixtureTermModel`，候选子集使用 `doe_augment.select_augment()`。本版对 `C(n,k)` 进行精确穷举，Seed 固定候选顺序及并列择优；评价预算不得超过现有 200,000 子集上限。若组合数超过预算、没有满秩组合、或最优候选的 logdet 低于父设计，则拒绝创建结果，不转入启发式搜索。成功结果的 `actual_evaluations` 等于实际枚举子集数，`stop_reason=exhaustive_candidate_subsets`，`global_optimum_proven=true` 只表示在已保存的有限候选域内达到最大值，不表示整个混料可行域的全局最优。

Schema 2 恢复在 DOE v5 验证当前表后，重建父/候选快照、核对当前 Mixture fingerprint、运行身份、约束和父响应快照，并重算候选穷举、矩阵 SHA、rank/logdet、映射及停止状态。Locked 行的原响应、实测值、Run ID、顺序和设定必须与父快照逐字段一致；新候选初始响应为空，后续填写响应可正常分析。改变受保护历史响应、父/候选快照、映射、当前矩阵或优化评价都会拒绝恢复。普通 v1/v2 完整交叉校验保持原样。

## 6. 独立参考与来源

独立 fixture 位于 `tests/fixtures/doe_phase2_p4bc_reference/`。生成器、验证器不得导入 MiniJMP 生产模块；冻结矩阵与期望值逐文件计算 SHA-256。必须包含 Taguchi L8/L16/L18、四类静态 S/N、噪声条件/重复身份、两阶段选择与预算、Mixture C01–C06 所需矩阵及解析案例。

官方方法来源：

- [Catalogue of Taguchi designs](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/supporting-topics/taguchi-designs/catalogue-of-taguchi-designs/)：固定矩阵、列号与目录范围。
- [Methods and formulas for Analyze Taguchi Design](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/taguchi/analyze-taguchi-design/methods-and-formulas/methods-and-formulas/)：响应表、四类静态 S/N 与动态 S/N。
- [Overview for Analyze Taguchi Design (Static)](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/taguchi/analyze-taguchi-design/before-you-start/overview-for-static-design/)：控制/噪声因子及稳健性目标。
- [Two-step optimization for Taguchi designs](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/supporting-topics/taguchi-designs/two-step-optimization-for-taguchi-designs/)：动态目标函数可能是斜率；本地 `robust_then_target` 仅冻结静态 Mean 目标。
- [Specify the type of design for Create Taguchi Design](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/taguchi/create-taguchi-design/create-the-design/specify-the-type-of-design/)：官方可选水平范围。

上述在线帮助未标明 Minitab 22 产品版本。缺少逐项官方输出时，数学结果以独立解析 oracle 为准，不声明版本等价。
