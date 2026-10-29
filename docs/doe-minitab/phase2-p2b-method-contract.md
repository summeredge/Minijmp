# DOE Phase 2 P2-2B：二元概率区间与响应优化方法合同

日期：2026-10-29
状态：方法合同已冻结；P1/P3 数学核心、P2/P4 GUI 与 P5 集成均有本地验收证据，等待独立 Review。本文件不表示 Review 通过。
范围：`BINARY_PROBABILITY_INTERVAL`、`BINARY_RESPONSE_OPTIMIZER`。本文件不表示验收通过。

## 1. 产品与数据边界

- 复用 H 工作包的 grouped-binomial Logistic 模型：
  `events_i ~ Binomial(trials_i, p_i)`，`logit(p_i) = x_i β`；dispersion 固定为 1。
- 首版仅开放 CCD、BBD、自定义 RSM。沿用当前分析器的有效项、`TermModel` 分类编码和 `FactorSpec.to_coded()`，不另建 Logistic 拟合流程。
- 拟合系数、协方差、概率区间与优化结果均为运行时结果。模型窗口重开后按当前数据重新分析；不持久化 statsmodels 模型对象，不升级 DOE Schema v5。
- 多区组预测/优化、缺少完整运行映射、过期模型快照、分离/不收敛/秩亏和无效系数协方差均拒绝。不得静默选择参考区组、删模型项或填补响应计数。
- 概率区间描述给定因子设置下事件概率估计的不确定性；不是未来单次 0/1 结果的预测区间，也不用于推断新批次事件总数。

## 2. 二元概率与 Wald 区间（P2B-ACC-01/02）

给定实际因子设定，将连续因子变换为当前 RSM 编码，并按拟合 `TermModel` 的实际列顺序构造 `x0`。该行必须与拟合矩阵列名和宽度一致。使用原 grouped-binomial GLM 的 `fitted.cov_params()`，不另估方差：

```text
eta_hat = x0 @ beta_hat
p_hat   = expit(eta_hat)
var_eta = x0 @ V_beta @ x0.T
SE_eta  = sqrt(var_eta)
SE_p    = p_hat * (1 - p_hat) * SE_eta
```

`var_eta` 若为有限容差内的微小负数，按 0 处理；小于负容差、协方差不对称/非半正定、矩阵尺寸不符或任意非有限输入均报不可用。不得取绝对值掩盖实质性负方差。

双侧置信度 `C` 使用 `z = Φ⁻¹((1+C)/2)`；单侧下限或上限使用 `z = Φ⁻¹(C)`。在 Logit 尺度计算 `eta_hat ± z*SE_eta`，再分别用稳定 `expit` 反变换。只发布用户请求的端点。不得以 `p_hat ± z*SE_p` 代替区间。

方法标注为渐近 Wald 正态近似，不表示有限样本精确覆盖率。概率因浮点饱和达到 0 或 1 时可返回饱和值，但区间标为不可用，避免展示虚假的有限精度。默认 GUI 置信度为 90%、95%、99%，方向为双侧、单侧下限或单侧上限。

预测设置必须覆盖全部因子；分类值必须是 DOE 元数据声明的水平，连续值必须处于声明范围内。结果带有当前数据/元数据 SHA-256 模型快照；来源变化、响应列切换、模型配置变化或窗口关闭后必须清除/拒绝旧结果。

## 3. Binary Response Optimizer（P2B-ACC-03/04）

优化对象始终为当前 grouped-binomial Logistic/RSM 拟合的事件概率：`p(x)=expit(X(x) beta_hat)`。响应因子点使用与拟合相同的 `TermModel` 和编码。概率目标和上下界位于 `[0,1]`。

### 3.1 目标函数必须分开

配置包含 `goal ∈ {maximize, minimize, target}` 和 `criterion ∈ {probability, desirability}`：

- `criterion=probability`：Maximize 直接最大化 `p`；Minimize 直接最小化 `p`；Target 最小化 `(p-T)^2`。目标不可达时返回搜索域内发现的最接近概率，`target_reached=false`，绝不称为达成。Target 的达成容差为绝对概率差 `1e-8`。
- `criterion=desirability`：以单响应 desirability 为主优化目标。Maximize/Minimize 的平台区间可能含多个解；weight=1 以外会改变曲线形状。
- 两种 criterion 均报告预测概率、desirability、目标差值、是否达标和求解状态；不能把概率极值、目标距离和 desirability 最大化混为同一目标。

Desirability 记预测概率为 `y`，weight 为 `w`：

| Goal | 单响应 desirability `d(y)` |
|---|---|
| Maximize | `0 (y≤L)`；`((y-L)/(T-L))^w (L<y<T)`；`1 (y≥T)` |
| Minimize | `1 (y≤T)`；`((U-y)/(U-T))^w (T<y<U)`；`0 (y≥U)` |
| Target | `0 (y≤L 或 y≥U)`；`((y-L)/(T-L))^w (L<y<T)`；`((U-y)/(U-T))^w (T≤y<U)` |

weight 范围为 `[0.1,10]`。Maximize 要求 `0≤L<T≤1`；Minimize 要求 `0≤T<U≤1`；Target 要求 `0≤L<T<U≤1`。不适用边界可留空；若提供则仍须在 `[0,1]` 且与目标关系相容。

Desirability 多解用确定性择优：先选最接近用户约束区域中心的候选，再按分类因子声明水平顺序，最后按连续因子编码坐标字典序。该规则只对实际评价/求解器返回的候选确定并列结果，不代表枚举连续平台或证明全局最优。

### 3.2 决策变量、搜索与结果声明

- 连续变量以物理单位输入；默认域为 DOE 声明的 `low/high`，用户可缩小或固定。内部用 `FactorSpec.to_coded()` 映射。
- 分类因子按用户允许的合法水平组合完整枚举；组合数超过首版搜索预算 32 时拒绝并要求收窄水平，不取任意子集后声称覆盖全部。
- 固定值必须满足用户域。起点必须位于全部约束范围内；相同输入使用确定的起点规则和求解配置。
- 连续搜索使用确定性多起点有界 L-BFGS-B；起点包含中心、边界候选和用户提供的起点，每个起点最多评价 100 次。达到预算时保留已检查的最佳候选并标记未收敛；该局部方法不证明连续域全局最优。
- `global_optimum_proven=true` 仅适用于没有自由连续变量且全部合法分类组合均已精确枚举的有限候选域；否则为 false。
- 返回实际/编码因子设置、概率、desirability、目标达成与偏差、方法、起点数、函数评价数、终止原因、求解成功状态和全局最优证明状态。推荐值只代表拟合模型预测，不是实际设备已验证工艺最优。
- 多区组模型拒绝；没有独立合同前不自动设置参考区组。搜索失败不得修改工作表响应、DOE 元数据或 `.dexpl` 内容。

## 4. GUI 与生命周期

扩展现有 `BinaryAnalysisDialog`，只在 RSM 分析成功后开放点预测和二元优化。点预测提供当前事件/试验列、实际因子设置、合法类别水平、置信度/方向、概率、`SE_eta`、`SE_p`、Wald CI、快照与适用说明，不显示连续响应 PI。

优化界面提供 Maximize/Minimize/Target、probability/desirability 目标、概率边界/目标/weight、连续因子收紧或固定、类别水平筛选、起点、预览、优化和取消。计算结果必须由同一模型行复算。

复用来源工作表、完整帧、DOE 元数据快照。事件/试验列、当前表、响应计数、DOE 设计、拟合项、优化目标/约束或分类设置变化后，立即清除结果。失败、取消、窗口关闭均不写回响应数据。

## 5. 独立参考和官方证据

独立 fixture：`tests/fixtures/doe_phase2_binary_reference/`。参考生成器/验证器不导入 MiniJMP 生产函数；包括手工给定 beta/协方差/预测行的 Wald oracle、statsmodels grouped-binomial GLM 冻结值，以及解析可解的一维二次 Logit 优化例。每个 fixture 固定 SHA-256 并有独立 verifier。

官方帮助只用于确认工作流、统计方法术语、目标输入约束和 weight 范围，不作为 MiniJMP 数值 oracle。页面没有 Minitab 22 明确版本或真实产品结果；不声明版本输出一致，也不推断官方求解器的全局最优保证。

- [Analyze Binary Response for Response Surface Design overview](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/response-surface/analyze-binary-response/before-you-start/overview/)
- [Event predictions methods and formulas](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/response-surface/analyze-binary-response/methods-and-formulas/event-predictions/)
- [Response Optimizer overview](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/using-fitted-models/how-to/response-optimizer/before-you-start/overview/)
- [Setting a target and lower/upper bounds](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/using-fitted-models/supporting-topics/response-optimization/setting-a-target-and-lower-and-upper-bounds/)
- [Specify boundaries, weight, and importance](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/using-fitted-models/how-to/response-optimizer/perform-the-analysis/specify-boundaries-weight-and-importance/)
- [Determining the weight](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/using-fitted-models/supporting-topics/response-optimization/determining-the-weight/)
- [Specify Response Optimizer options and constraints](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/using-fitted-models/how-to/response-optimizer/perform-the-analysis/specify-the-analysis-options/)
