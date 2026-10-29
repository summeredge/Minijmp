# DOE Phase 2 P2-3：多因子平衡 Split-Plot 方法合同

日期：2026-10-29
状态：合同冻结；独立参考已独立核验；本地实现验收状态见 [P2-3 验收](phase2-p3-acceptance.md)。

## 1. 范围与存储兼容

- 仅支持 2–6 个连续两水平因子、1–3 个 hard-to-change 因子、至少 1 个 easy-to-change 因子、至少 2 个完整重复区组。每个区组含全部 hard 组合，每个整区含全部 easy 组合。
- 每个完整重复区组是一个独立 block；`block_count=R` 不兼作任意分块数或区组内整区重复数。
- 保持 DOE Schema v5 与现有字段。既有 `construction_version=v1` 仍严格按两因子、1 hard + 1 easy 的旧运行身份、整区 ID 和 seed 顺序构建/校验；新多因子构造用 `v2`。不迁移旧工程、不重排旧运行、不重用旧 ID。
- 输入因子顺序定义标准因子项显示顺序；因子点采用 `(-1,+1)` 编码并映射至 FactorSpec 的 low/high。不得互换因子角色。
- 支持运行预算 10,000。按 `R × 2^h × 2^e` 在分配运行记录或 DataFrame 前校验。
- 官方 Split-Plot 帮助支持难改因子在整区内保持不变，并说明要分别随机化整区及其内子区；本包进一步冻结下述完整平衡结构和固定区组推断合同，不据此声称 Minitab 22 输出等价。

令 `h`、`e` 分别为 hard/easy 因子数，`H=2^h`、`E=2^e`：

```text
整区数 = R × H
每个整区的子区运行数 = E
总运行数 = R × H × E
```

每个 block 恰含 H 个不同 hard 组合；每个整区只含一个 hard 组合和全部 E 个 easy 组合。整区 ID 在区组间唯一，子区 ID 全局唯一；实际运行序连续排列为 block → whole plot → subplot 的嵌套次序。重随机化只改变 seed 派生的顺序与顺序字段，不改变点集、重复数或实验单位身份。

## 2. 模型与实验单位

分析完整、平衡的观测行模型：

```text
y = μ + Block + Σ(hard-only factorial terms)
        + Σ(factorial terms containing ≥1 easy factor)
        + whole-plot error + subplot error
```

模型包含全部 `2^k−1` 个因子主效应和交互项。效应所属误差层只由因子成员决定：完全由 hard 因子组成的主效应/交互项进入整区层；包含任一 easy 因子的项进入子区层。区组为固定效应。区组与处理正交、设计完整且平衡是所有闭式 df 和 F/p 的前提。

使用实际运行矩阵构造 block 指示列与每个因子子集的 ±1 乘积列。先检查模型矩阵的实际秩；秩亏时不得输出相关 F/p，并须给出秩/不可估原因。对完整合同设计，预期固定模型秩为 `R + 2^k − 1`。

## 3. 平方和与自由度

设 `N=RHE`。按正交投影计算 block、每个因子项、整区误差及子区误差平方和；不得对现有 2×2 均值公式按因子数循环扩展。每个因子项 df 为 1；`β` 是 ±1 编码模型系数，效应为 `2β`，项平方和为 `Nβ²`。

```text
df_total             = RHE − 1
df_block             = R − 1
df_hard_effects      = H − 1
df_whole_plot_error  = (R − 1)(H − 1)
df_easy_terms        = H(E − 1)
df_subplot_error     = H(R − 1)(E − 1)
```

整区误差是 whole-plot 均值中、扣除固定 block 与全部 hard-only 项后的 block×hard 残差；子区误差是观测层完整固定效应残差扣除整区残差贡献后的分量。必须验证两层分解及总平方和闭合、自由度闭合；平方和非负，严重浮点抵消报不可用，不取绝对值掩盖负值。

平方和闭合容差为 `τ = 256 × ε × max(N, model_rank) × SS_total`，其中 ε 为 binary64 machine epsilon。误差层的近零阈值单独按 `τ₀ = N × (4 × ε × max_i |y_c,i|)²` 计算；`y_c` 先减去一个观测值再减其均值，以降低大共同响应偏移造成的数值损失。两项分别用于分解闭合和误差层可用性；整体响应乘任意可表示的非零常数不得改变误差层可用状态或 F/p。若 SS 分解差超过 τ，整次推断报不可用；某层 SS ≤ τ₀ 按数值零方差处理，该层对应 F/p 不可用。整体残差与两层贡献的逐行差按 `sqrt(τ)` 校验。

每个 hard-only 项使用整区 MSE 和 `df_whole_plot_error`：

```text
F = MS_term / MS_whole_plot_error
```

每个含 easy 因子的项使用子区 MSE 和 `df_subplot_error`：

```text
F = MS_term / MS_subplot_error
```

各项 p 值取对应 `F(1, df_error)` 的右尾概率。block 行不提供处理 F/p。零 df、零/非有限误差方差、模型秩亏或损坏结构对应的检验必须返回 unavailable 及具体原因；另一层仍可独立有效。不得把两层 MSE 合并，也不得把子区观测当作独立整区重复。

## 4. 拟合、残差和结果字段

按原 `run_id` 与实际运行序返回：固定效应 fitted、整区误差贡献、子区误差贡献及整体 residual，满足 `overall residual = whole-plot contribution + subplot contribution`。每层提供 SS、df、MSE 和可用状态/原因。整体残差图仅描述整体残差，不声称验证两层误差的分布假设。GUI 同时呈现整区/子区身份、分层 ANOVA、效应系数/效应及 F 检验的误差层；较长效应表使用现有可分页 StatTable。

分析只读工作表，不改响应、DOE 元数据或实验单位。响应缺失/非有限/不可表示时拒绝分析。损坏或互相矛盾的 whole-plot/subplot/block/角色/水平映射拒绝分析，不推测修复。

## 5. 独立参考及边界

参考目录 `tests/fixtures/doe_phase2_splitplot_reference/` 不得导入 MiniJMP 生产模块。包含既有 D 工作包 2×2、3 blocks 参考，以及 1 hard + 2 easy、2 hard + 2 easy、3 hard + 1 easy、规定响应方程和分层误差边界案例。精确有理数或独立投影复算项 SS、df、MS、F、p、误差层归属、总和/自由度闭合及实验单位。

| 条件 | 处理合同 |
|---|---|
| hard 因子 0/4+、easy 因子 0、总因子超出 2–6、区组少于 2、非法 seed/角色/水平、超过 10,000 runs | 创建前拒绝 |
| whole_plot_id/subplot_id/run_id 重复或跨层错配、整区内 hard 水平变化、整区缺少 easy 组合、行/顺序/设计点损坏 | 恢复/分析前拒绝 |
| 响应缺失或非有限、实际矩阵秩亏/混杂 | 拒绝或明确将受影响推断标为 unavailable；不得输出显著性 |
| 整区误差为零 | hard-only 项 F/p unavailable；子区项仍按子区层判断 |
| 子区误差为零 | 含 easy 项 F/p unavailable；hard-only 项仍按整区层判断 |

不支持非平衡/部分实施、多水平、额外子区重复、自定义整区、REML/ML、Kenward–Roger/Satterthwaite、Split-Plot 预测区间/优化及未实测 Minitab 22 标准序或输出 parity。

## 6. P3-REV-01：完整区组的历史顺序保留

`replicate()` 对 Split-Plot 代表“增加完整区组”，不得扩大 `block_count` 后重建全部运行。旧运行的 run ID、标准序、区组、整区/子区身份及其运行/整区/子区顺序必须逐项保持；响应值按原始 DataFrame 的 run ID 复制，并保留响应列 dtype。新增运行使用新 run ID，响应留空。

追加沿用 DOE Schema v5 的 `augmentation_lineage`、`batch_id`、运行映射和前后矩阵 SHA，不增加字段或改变 Schema 版本。谱系保留 v5 已允许的 `criterion=manual`；Split-Plot 中它表示用户指定完整区组数，具体随机化算法由 `batch_id=SPLITPLOT_APPEND_V1` 标记。其他设计中的 `manual` 仍表示按候选输入顺序选择。这样不会引入旧 v5 读取器不认识的新准则值。

恢复时先按原 `construction_version`、seed 和原 block 数调用未修改的 v1/v2 `_layout()`，核对每个旧 run 的全部身份、设定及历史顺序。新增区组再按固定的 `SPLITPLOT_APPEND_V1`、原 seed 和新区组范围确定随机化，核对新增 block、whole plot、subplot、标准序及紧接旧运行的 run_order。Schema v5 的矩阵 SHA 另外核对父/当前设计点；工作表 fingerprint 覆盖已保存的身份和顺序。两层校验合起来才能验证整个设计。

目前一次设计只接受一个追加批次；要增加多个区组，应在一次操作中指定总数。追加后禁用再次增加区组和全设计重随机化，避免覆盖历史顺序。不能表示 v5 lineage 的 Schema v4 原始元数据拒绝追加，不自动升级 schema。若响应 dtype 不能表达新空值，操作在返回新表前拒绝。通用候选点 `augment()` 不接受 Split-Plot。
