# DOE Phase 2 P2-5：Minitab 22 对照准备

日期：2026-10-30

状态：准备材料完成；P2-5 产品运行与统计实现修改均未开始。

## 基线与边界

- `main` HEAD：`512f03a1e4fb8554748633fec086024375e4e4de`（`Record P2-4A/P2-4BC integration status and verification`）；开始时工作区干净。
- `.agent-memory/MEMORY.md` 与 `.agent-memory/logs/` 仅作只读保护，本任务没有修改。
- DOE Schema v5、MiniJMP 统计实现、现有 P4A/P4BC 参考及 feature matrix 均未修改。未运行 Minitab，未生成或伪造产品输出。
- P4A 与 P4BC 本地方法及测试证据见 [P4A 收尾](phase2-p4a-closeout.md)、[P4BC 收尾](phase2-p4bc-closeout.md)；其独立数学参考不等于 Minitab 22 输出。

## Feature ID 证据分层

按当前仓库可复核的来源分为三类；“是否有 Minitab 22 产品文件”另列状态，避免把官方帮助或数学 oracle 混成产品证据。

| 证据层 | Feature ID 数 | 当前判断 |
|---|---:|---|
| 有真实 Minitab 22 输出（范围有限） | 1 | `RSM-002` 有用户提供的 5 份 BBD 设计表，只覆盖 9/10 因子的五种配置。 |
| 只有官方文档或数学参考 | 78 | 有官方帮助、目录或独立解析/文献参考；这些来源没有提供对应的 Minitab 22 数值导出。 |
| 无可复核参考基线 | 1 | `GEN-013`：官方文档审查未确认 DOE 自动异常值处理工作流，矩阵也标记 `not_verified`。 |

因此，除 `RSM-002` 的有限 BBD 配置外，其余 **79 个 Feature ID 的 Minitab 22 产品输出状态均为 `REFERENCE_MISSING`**。逐项证据分类、官方 URL、现有测试/数学参考及范围备注见 [80 项证据清单](phase2-p5-feature-evidence.csv)。

### 已有 Minitab 22 文件

`tests/fixtures/doe_bbd_reference/original/` 中有 5 份 BBD CSV，配置均为连续因子、低/高水平 −1/+1、10 个中心点、单重复、无分类因子且未随机化。版本 22 来自用户提供记录；CSV 本身不能证明软件来源，且未记录具体 22.x build。

| 文件 | 因子 | 区组 | 运行数 | SHA-256 |
|---|---:|---:|---:|---|
| `bbd9-unblocked.csv` | 9 | 1（无区组） | 130 | `a12d3877b72a111501880e9c386be5425eeb106f3a7880103047b17758897781` |
| `bbd9-block5.csv` | 9 | 5 | 130 | `c0d5c95828b57769a60d08d60f6e9c681415f7e4558a80622e614b75d0cb02a1` |
| `bbd9-block10.csv` | 9 | 10 | 130 | `5496845699f0d3f65cd8c9a6701553bb62c139467e493b244bc594e43d5bafaa` |
| `bbd10-unblocked.csv` | 10 | 1（无区组） | 170 | `32dfa3ac8b0610f9babcbe77e0a1e045fca8e6eafd77dd118189110bf423def9` |
| `bbd10-block2.csv` | 10 | 2 | 170 | `f9406c49440c590f5be3f6fbe52a39ee4bb8273b436af4163a64646ffa727bcc` |

已核对的点多重集和重映射区组多重集完全相同；标准序逐行差异分别为 60、116、123、120、163 行。此证据仅覆盖表中配置，不等于完整标准序一致，也不证明输出来源。其他 DOE 相关目录未发现额外 Minitab 22 导出；P2-4A、Taguchi、Mixture 联合模型与 Replace/Improve 均无产品文件。

## P2-5 优先对照案例

每个待采集案例均已在 [案例登记表](phase2-p5-case-register.csv) 中标为 `REFERENCE_MISSING`，并列出输入 fixture、设计设置、随机种子、字段、容差与 Minitab 22 输出来源。

| 优先级 | 案例组 | 输入与设置概要 | 主要对照字段 | Minitab 22 输出状态 |
|---|---|---|---|---|
| P0 校准 | BBD-9/10 | 现有五份 9/10 因子 CSV；未随机化 | 点多重集、中心点、因子映射、区组映射；保留标准序差异 | `PARTIAL_REFERENCE` |
| P1 | DSD Stepwise S01–S05 | 现有 6 因子 13 行与 4 连续+1 分类 14 行参考；显式 alpha、候选项、层级和区组设置 | 每步进入/移除项、F/p、SSE、秩/df，最终模型与系数 | `REFERENCE_MISSING` |
| P1 | PB 全因子/单因子 Foldover | PB12、PB20 先做；再扩到 PB24–PB48；连续两水平、无中心点/区组、单重复 | 新旧行符号变换、追加数量、来源映射、响应列处理 | `REFERENCE_MISSING` |
| P1 | Taguchi 混合阵列 | L8(4¹2⁴)、L16(4¹2¹²)、L18(2¹3⁷)；固定列身份 | 运行×列水平矩阵、官方列号映射、列频数/列对频数 | `REFERENCE_MISSING` |
| P1 | Mixture 联合模型 | 3 组分、degree-2 lattice × 2 个两水平过程因子 × 总量 100/150/200；72 行、15 项 | 同一响应与项定义下的 rank/df、系数、拟合、SSE、预测 | `REFERENCE_MISSING` |
| P1 | Mixture Replace/Improve C05 | 3 组分线性模型；2 个 Locked 点、1 个 Replaceable 点、4 个候选、selection seed 23 | 选中点、rank/logdet、Locked 身份与响应、候选映射 | `REFERENCE_MISSING` |

DSD、PB 与 Mixture 案例在 MiniJMP 独立 fixture 中有可复算的数学预期；这些 fixture 只作为设计和输入数据来源，不能填入 Minitab 22 输出列或冒充产品结果。Taguchi 官方目录矩阵也不是已导出的 Minitab 22 工作表。

Mixture Replace/Improve 案例同时覆盖 `GEN-003`（D 最优候选选择）、`GEN-006`（增补/改进操作）与 `MIX-006`（混料模型项）。四水平 `L16(4^5)` 与五水平 `L25(5^6)` 属于 `TAG-010/011`，列为 P5-3 扩展；本轮优先采集的 mixed-level 案例覆盖 `TAG-005`。

**Mixture 联合模型有额外产品范围门槛：**当前在线的 Minitab 帮助将 mixture-process 与 mixture-amount 作为不同设计类型；自定义混料设计说明还写明，指定 process variable 时不能选 `Mixture Amount: In Column`。这些页面未注明版本，不能推断 Minitab 22 的行为。P5-0 必须先实测 22.x 是否可定义同一设计并拟合组件×process 与组件×amount 的 15 项模型；若不支持，只能分别比较 process-only 与 amount-only 子案，72×15 联合模型继续标为 `REFERENCE_MISSING` / `PRODUCT_SCOPE_UNVERIFIED`。

## 对照合同

### 来源与输入锁定

1. 每次产品采集记录 `Help > About` 中的产品名称、22.x 版本/build、位数、操作系统和工作表来源；保存创建/分析设置截图或文本、产品会话输出及原始工作表导出。
2. 原始 Minitab 22 文件只读保存，登记字节数、SHA-256、编码、列名/列序、单位、种子、随机化设置、缺失值与因子映射。版本仅由用户记录支持时标注为“用户确认”，不写成文件自身证明。
3. 逐项核对设计矩阵和响应输入一致。若 Minitab 22 不能导入或定义同一设计，或不能按 P4A/P4BC 合同配置同一模型，则该项标记为 `REFERENCE_MISSING` / `PRODUCT_SCOPE_UNVERIFIED`，不得拿两个不同矩阵上的结果作数值 parity。
4. 区分标准序、随机运行序和显示行序。除非验收项明确比较同一产品的可复现运行序，否则先按运行 ID/因子映射比较矩阵多重集；不得将 MiniJMP 与 Minitab 的随机数算法差异误报为统计差异，也不得把标准序差异静默当作一致。

### 比较字段与容差

- **离散/结构字段**：运行数、因子数、水平、列映射、设计点多重集、区组/中心点计数、模型项、选择项/步骤顺序、rank/df、运行映射和 Locked 响应均按合同精确比较；允许的因子置换、区组重编号或运行行重排必须逐案显式登记。
- **完整精度数值导出**：初始判定建议 `abs(Δ) <= max(1e-8, 1e-8 × abs(Minitab值))`，适用于系数、拟合、SSE、预测、S/N 与 logdet 等同定义字段；先确认两端使用相同编码、模型、自由度和统计定义。
- **只有格式化报告**：容差取最后显示位的一半（例如显示到 0.001 时为 0.0005），并且只记“显示精度一致”；该结果不能提升为全精度数值 parity。若显示精度或统计定义不明，标记 `NOT_COMPARABLE`，不放宽容差追求通过。
- **秩与唯一最优候选**：rank、df、最终模型项/候选点身份必须精确一致；Replace 的 logdet 使用上面的全精度比较规则。Minitab 不输出搜索次数时，将其记为“产品未显示”，不得从最终设计反推并宣称为产品输出。

以上容差是采集前的比较规则，不是现有产品测试结果；取得带精度的实际导出后，先核对字段和显示精度，再冻结最终容差。

## 分阶段验收计划

| 阶段 | 内容 | 通过条件 | 停止条件 |
|---|---|---|---|
| P5-0 来源与产品范围 | 确认 22.x build、原始文件及导出流程；确认每类设计可创建/定义、可输出目标字段 | 原始来源、设置、seed、编码、字节哈希可复核；无版本猜测 | 无真实输出则登记 `REFERENCE_MISSING`；产品不能表达合同则登记 `PRODUCT_SCOPE_UNVERIFIED` |
| P5-1 已有控制案例 | 复核 BBD 五配置的来源/哈希，并用同一产品版本做重复导出 | 既有点集/区组结论可重复，标准序差异单独报告 | 来源或 build 无法确认时保留用户陈述等级，不升级为完整 parity |
| P5-2 P4A/P4BC 核心 | 按案例登记表采集 DSD、PB、Taguchi、Mixture 联合模型和 Replace/Improve 输出 | 每项通过输入一致性、结构比较、数值容差及来源审计；每项独立报告 | 任何输入/模型字段不一致，或产品输出不可取得时，该案例保持缺口，不使用数学 oracle/生产输出替代 |
| P5-3 扩展范围 | 扩展 PB 所有 run size、Taguchi 其他混合阵列及四水平 `L16(4^5)` / 五水平 `L25(5^6)`、Mixture 过程/总量组合及现有功能矩阵未覆盖字段 | 有逐案例 Minitab 22 输出和 fixture manifest；范围外不外推 | 选项不可用、输出未保留或证据只来自未注明版本网页时，维持缺口 |
| P5-4 结果归档 | 更新 80 项证据清单及正式对照报告 | 每个结论指向原始产品文件、设置、哈希、字段和容差 | 不因局部通过批量改写矩阵 `partial/unknown`，不自动启动功能实现 |

### 官方工作流参考（页面未标明 Minitab 22 版本）

- [DSD Stepwise 设置与逐步详情](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/screening/analyze-screening-design/perform-the-analysis/perform-stepwise-regression/)
- [PB/因子 Fold Design](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/factorial/display-and-modify-design/perform-the-analysis/fold-design/)；[Foldover 追加行和符号翻转说明](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/supporting-topics/factorial-and-screening-designs/what-is-folding/)
- [Taguchi 混合水平阵列设置](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/taguchi/create-taguchi-design/create-the-design/specify-the-design/)；[Taguchi 官方阵列目录](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/supporting-topics/taguchi-designs/catalogue-of-taguchi-designs/)；[Analyze Taguchi 方法与 S/N](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/taguchi/analyze-taguchi-design/methods-and-formulas/methods-and-formulas/)
- [Analyze Mixture Design 工作流](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/mixtures/analyze-mixture-design/before-you-start/overview/)；[Mixture D-optimal Augment/Improve](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/factorial/select-optimal-design/perform-the-analysis/select-optimal-runs-augment-or-improve-a-mixtures-design/)

## 与 P4A/P4BC 现有数学参考的关系

- DSD 输入/预期轨迹：`tests/fixtures/doe_phase2_p4a_reference/dsd_reference.json`，SHA-256 `ad4713ff3861f5aaffeeba9b17c1ba3979c9b4bb9b0305b1201fa7d6f094164a`。
- PB 输入/折叠点集：`tests/fixtures/doe_phase2_p4a_reference/pb_foldover_reference.json`，SHA-256 `9ee6b929929a70994c89e8e3d998bcb6def610da9524116dad9c1d4c078fe0ab`。
- Taguchi、48 行噪声、72×15 Mixture 模型和 C05 D-optimal Replace：`tests/fixtures/doe_phase2_p4bc_reference/reference.json`，SHA-256 `f23cad153fd383bfef6be5b0bdb88d37009e338b89e19a3e92935464ba68ebd7`。

这些是独立数学/官方矩阵核验值，不是 Minitab 22 产品输出；除 BBD 五份用户提供文件外，所有优先案例维持 `REFERENCE_MISSING`，直到取得并验证实际产品文件。
