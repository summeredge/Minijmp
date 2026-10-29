# DOE Phase 2 P1 方法合同

日期：2026-10-29
状态：合同与两套独立参考已冻结；P2-ACC-01/02/03/04 与 P2-ACC-05/06/07 均已完成本地验收，并经独立 Review 在限定范围内 APPROVE。首轮 A-01/B-01 修复已验证；Mixture 增补、真实 Tk 与完整工程生命周期均已覆盖。没有 Minitab 22 产品输出，不声明版本 parity。

## 证据与现状

本合同重建自本轮目标、现有 `roadmap.md` / `acceptance.md`、E/F/H 收尾材料及官方帮助。目标文件列出的三份原始 Phase 2 规划稿在开始时缺失，具体证据边界见 [差距分析](phase2-gap-analysis.md)。这里的“官方确认”仅为公开帮助确认工作流存在和规则文字，不代表 Minitab 22 实测。

现成矩阵与接口：`MixtureTermModel` 使用无截距 Scheffé 组分项；过程/总量变量编码到 `[-1,1]`。`doe_optimal.select()` 最大化 `logdet(X'X)`，预算内穷举，超预算多起点贪婪加交换。`select_distance()` 当前只接受 RSM。Mixture 元数据由 DOE v5 `doe` 和 Mixture Schema 1 `mixture` 两部分保存；DOE v5 已有最优/增补 lineage 字段，但 `optimal_lineage` 尚不允许 `design_type='mixture'`。

## P2-ACC-01：Mixture D-optimal

### 模型矩阵

对候选运行 `i`，令 `x_i` 为经约束验证的实际组分比例，过程/总量设定按现有 `VariableSpec.to_coded()` 编码。目标矩阵为：

`X[i, :] = MixtureTermModel(spec, terms, degree).row(settings_i)`

该矩阵必须使用 Scheffé 组分项，不加普通回归截距。默认项沿用 `MixtureTermModel.default_terms()`；用户可明确选择该模型支持的合法项。过程/总量项仅在所选项中出现；过程交互遵从现有 `xi*z` 规则。候选点必须通过组分总和、上下界、线性约束和变量范围校验。当前首版的 D-optimal 组件建模单位固定为 proportions，以保持与 MiniJMP 混料分析实际矩阵一致；不声称覆盖 Minitab 的全部单位选项。

### 目标、重复与搜索状态

对选中运行矩阵 `X_s` 最大化 `log det(X_s'X_s)`。设计必须满列秩；欠秩时不生成设计。以“完整组件/过程/总量设定”识别物理候选点：相同设定的候选行先合并，防止重复候选行改变搜索权重；若选中多次，则每一次是独立实验重复，需有独立 run ID、重复次数记录和空响应。

`允许重复`是显式选项。关闭时，每个不同物理设定最多选一次；开启时按候选点有放回选择，精确搜索按多重组合预算计数，超预算使用确定性多起点贪婪/交换。摘要必须列出每个设定的 multiplicity、目标运行数、rank/p、logdet、算法、预算、评价次数与停止原因；只有实际穷举全部允许组合才标记 `global_optimum_proven=true`。不允许重复的选点也不得从重复候选行中重复计权。

## P2-ACC-02：Mixture Distance-based

### 坐标

- 每个距离向量必须包含全部组分列，且组分统一使用实际比例 `x_i`。若输入提供伪组分，先用现有 `from_pseudocomponents()` 还原实际比例并重新验证约束；不直接把伪组分值与实际比例混用。本合同选择物理比例作为 Mixture 距离坐标，记录此 MiniJMP 口径，不宣称 Minitab 22 的精确缩放规则。
- 过程变量或总量变量可逐列明确纳入/排除。纳入时使用声明的 `[low, high]` 映射到 `[0,1]`；不得把原始单位直接拼入组成比例坐标。零跨度、非有限或无声明范围的变量拒绝纳入。
- 首个候选按组件坐标到任一纯组分顶点的最小欧氏距离选取；并列取候选输入顺序最早者。该起点只需是已验证的可行候选，纯组分顶点本身可以不满足约束。后续每一步在全部已配置坐标上，选择到已选/固定锚点集合的最小平方欧氏距离最大的可行候选；并列同样取输入顺序最早者。
- 距离准则不重复同一个配置坐标点。对选点，精确坐标重复候选折叠为首次出现；对增补，与父设计等价的候选也排除。候选不足时在写入前报错。

## P2-ACC-03：增补

- 父设计每一行固定保留；不得删除、替换或交换。父响应和其他原始列逐值保留。新增运行有新的唯一 run ID，响应为空，标准序/运行序连续，重复号和批次映射有效。
- D-optimal 将父设计 Scheffé 信息矩阵固定加入候选子集目标；`允许重复`关闭时不得重复候选或复制父设定，开启时可在父设定上增加新的独立重复并单独报告。
- Distance-based 将父设计坐标作为固定锚点，后续按 ACC-02 规则增补，且不能复制父设计已有的同一设计空间点。
- 摘要至少给出增补前后 `n`、`p`、rank、logdet、最小平方距离（适用时）、准则、算法、预算和停止原因。目标模型增补后仍秩亏时拒绝写入。

## 持久化、边界与独立验证

优先复用 DOE v5 的 `optimal_lineage` / `augmentation_lineage` 和 Mixture Schema 1 的设计指纹，不新增持久化字段或提高版本号。P2a 需将 DOE v5 已有 `optimal_lineage` 的允许设计族扩展为包含 `mixture`；谱系字段不变，`DesignSpec` 仍使用 `design_type='mixture'`。这会增加当前 v5 可接受的一个组合，旧程序对该新组合的读取不作保证；必须用现有 v1–v5 恢复测试和 Mixture Schema 1 往返/坏元数据隔离测试覆盖。若实现发现必须增加字段，则先暂停该改动，补写 schema 迁移合同与旧工程恢复测试，再决定是否升级版本。保存/重开/复制/再分析必须同时恢复 DOE 与 Mixture 元数据；损坏元数据不能替换 live workbook。

独立 oracle 位于 `tests/fixtures/doe_phase2_optimal_reference/`，只允许标准库精确分数/独立线性代数，不导入生产选点代码。它覆盖三组分手算距离顺序、小候选 D-opt 穷举、有约束可行点、混料×过程矩阵、并列、秩亏、重复候选、无可行点、候选不足、有/无放回、固定父设计 D-opt 增补、Distance 父锚点不重复及精确/启发式状态。参考生成器与 verifier 分别计算。

## P3/P4 统计边界（独立验收单元 B）

- 仅连续 CCD、BBD、自定义 RSM；使用当前分析器实际模型行与误差单位。满列秩且 `df_error=n-rank(X)>0`、残差方差有效时，`SE_fit=sqrt(MSE*h0)`、均值 CI 使用 t 分位数乘 `SE_fit`，单次 PI 使用 t 分位数乘 `sqrt(MSE*(1+h0))`。用 QR/SVD/稳定方程解，不显式求逆。
- 双侧临界值为 `t(1-alpha/2, df_error)`；单侧边界用 `t(1-alpha, df_error)`。只为单次未来观测计算 PI；均值 CI 与 PI 分栏显示。无效区间原因明确返回，不输出无穷值或 NaN。
- 杠杆为 `diag(H)`；标准化/删除学生化残差、Cook's D、DFITS 按实际 OLS 设计矩阵与残差 MSE 定义，仅在其自由度/方差条件成立时计算。`h≈1`、饱和、秩亏、零 MSE 或非正删除误差自由度使相应指标不可用。诊断仅提示，不删点。
- 不将这些连续 OLS 公式用于 H 的 grouped-binomial Logistic、Mixture Scheffé、Split-Plot 或未经验证的其他模型。区组 RSM 只有预测行、区组方差合同由独立参考核实后才开放；否则显式拒绝。

2026-10-29 P2a/P2b 本地验收通过：独立 verifier 13 项通过，SHA-256 `29bd937eae7415579c9992afe780b9546708653d604cfe939afffcdcf749a4ed`；核心统计/工程回归 98 passed，真实 Tk Mixture 生命周期 8 passed，Mixture 持久化 4 passed，帮助中心 13 passed，菜单 66 passed。增补保留整数响应精度与映射为空的父批次值。选点与增补输出复用 DOE v5 谱系和 Mixture Schema 1，不新增字段或提高版本。官方帮助未声明版本，本地没有 Minitab 22 产品输出，因此不作版本特定 parity 声明。

P3/P4 本地验收通过：`tests/fixtures/doe_phase2_interval_reference/` 的独立 verifier 覆盖 9 个区间组合和 9 行影响诊断，reference SHA-256 `d87d1720c24000fec7ebbf42cb2e1f58f8c52d2be8fadfcee7600f3bc4121a72`。当前区间按实际满秩连续 RSM 矩阵计算 `h0` 和 `MSE=SSE/df_error`；残差 MSE 阈值结合中心化响应变化与原始响应的浮点舍入尺度，避免常数平移改变有效性。真实 Tk 与保存/重开/复制集成通过；仅 CCD/BBD/custom 连续 RSM 开放，不覆盖多区组、Logistic、Mixture、Split-Plot 或自动删点。
