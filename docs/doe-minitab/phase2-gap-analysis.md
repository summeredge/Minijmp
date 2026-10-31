# DOE Phase 2 差距分析（重建稿）

> 2026-10-31 P2-6.5 更新：以下保留历史阶段记录；当前状态以 [最终综合验收](../../Out/p2_6_doe_function_completion/p2-6-final-acceptance.md) 和 [80项矩阵](feature-matrix.csv) 为准，历史的“当前/未实现/未提交”不代表本轮结束状态。

日期：2026-10-29
状态：按本地 P2-0 摘要与本轮目标重新建立；**原始** `phase2-gap-analysis.md`、`phase2-roadmap.md`、`phase2-acceptance.md` 在本轮开始时均不存在，未读取或还原其原文。

## 证据边界

本稿基于当前 `roadmap.md` 的 P2-0 审计摘要、`acceptance.md` 与 feature matrix、工作包 E/F/H 收尾记录、本轮目标文件，以及 2026-10-29 查阅的 Minitab 官方帮助页面。官方帮助用于确认存在的工作流和方法定义；没有 Minitab 22 产品输出，因此不构成版本 22 数值或标准序对照。

基线：H 提交 `ed85429ed23c52a6b2a238ad86fc1517ace93ff6` 在 `main` 历史内；DOE Schema v5、Mixture Schema 1；工作包 A–H 为限定范围完成。现有 80 项矩阵为 58 implemented、18 partial、3 unknown、1 excluded。开始本任务时仅 `docs/doe-minitab/roadmap.md` 有未提交 P2-0 摘要修改；三份 Phase 2 原始规划稿缺失。

## 本轮范围

| 缺口 | 当前状态 | 本轮目标 | 边界 |
|---|---|---|---|
| `GEN-004 / ACC-056` 混料最优选点 | 当前 D-optimal 与 Distance-based 只接入自定义 DOE/RSM；混料响应优化是另一条工作流 | Mixture D-optimal 和 Distance-based 选点、约束、模型秩与评价 | 不把 desirability 优化当作实验选点；启发式不宣称全局最优 |
| `GEN-006 / ACC-058` 混料增补 | 通用增补已支持固定父设计的 D-optimal 与 RSM 距离准则 | 保留所有混料父运行并支持两种准则增补 | 首版不实现删除/替换父运行的 improve；父响应不变、新响应为空 |
| `RSM-009` 均值 CI / 单次 PI | 矩阵为 `unknown`；RSM 只有点预测 | CCD、BBD、自定义连续 RSM 的 SE Fit、CI、PI、单侧/双侧区间 | 不扩展到 Logistic、Mixture、Split-Plot 或未经验证的模型 |
| DOE 影响诊断 | 通用诊断合同存在，目标影响量尚未接入连续 RSM 分析结果 | Leverage、标准化/学生化残差、Cook's Distance、DFITS | 使用实际 RSM 设计矩阵、误差自由度和 run ID；不自动删点 |
| GUI、保存恢复和帮助 | Mixture 与 RSM 各有现成窗口、工作表元数据和帮助入口 | 扩展现有工作流，覆盖失效、取消、保存/重开/复制/重分析 | 保持 DOE v5、Mixture Schema 1；如需新增字段先暂停并制定迁移合同 |

## 已复用的先行能力

- 工作包 E：`doe_optimal.select`、`select_distance`、`doe_augment`、`optimal_lineage` / `augmentation_lineage`、组合预算与确定性搜索；父设计增补点固定，不参与交换。
- 工作包 F：`MixtureSpec`、组分约束与伪组分换算、`MixtureTermModel` Scheffé 矩阵、Mixture 工作表/元数据/指纹恢复、Mixture GUI 和 `.dexpl` 生命周期。
- 工作包 H：Logistic 使用独立 grouped-binomial 合同；本轮连续响应公式不得进入 H 的二元分析、预测或诊断。
- 通用 DOE 预测与 RSM：复用实际模型项、编码、预测点构造和当前工作表快照；不另造重复预测入口。

## 官方来源确认范围

- Minitab 的 Mixture Select Optimal Design 同时提供 D-optimal 与 Distance-based；D-optimal 依赖所选模型项，混料组分单位可用 proportions 或 pseudocomponents；Distance-based 要求所有混料组分列，可选择排除过程变量与总量列。增补页面允许选择保留/可离开的父运行，本轮仅承诺保留全部父运行。[Mixture 选点与增补](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/factorial/select-optimal-design/perform-the-analysis/select-optimal-runs-augment-or-improve-a-mixtures-design/)
- 官方 D-optimal 方法页描述初始点顺序选择和交换改进，允许候选点在优化中重复；Distance-based 以最靠近纯组分的混料点开始，后续逐步选取离已选点最远的点，且不复制点。[最优设计方法与公式](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/factorial/select-optimal-design/methods-and-formulas/methods-and-formulas/)
- 官方 Predict 将 SE Fit、均值 CI 与单个未来响应 PI 分开，并提供置信水平和双侧/单侧边界选项。[Predict 方法与公式](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/using-fitted-models/how-to/predict/methods-and-formulas/methods-and-formulas/)；[区间选项](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/using-fitted-models/how-to/predict/perform-the-analysis/specify-the-confidence-and-prediction-intervals/)
- 官方响应面 DOE 诊断帮助列出 leverage、Cook's distance 与 DFITS。[RSM 诊断方法](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/response-surface/analyze-response-surface-design/methods-and-formulas/diagnostic-measures/)

## 原 P2-1/P1 范围边界

原 P2-1/P1 范围排除了 Binary Response Optimizer 与二元概率区间；二者现由独立 Goal `DOE Phase 2 P2-2B` 实施，验收状态见 [P2-2B 验收记录](phase2-p2b-acceptance.md)。未经验证的 Mixture CI/PI、Split-Plot 分层推断、PB Foldover、Taguchi 扩展、Minitab 22 标准序及产品输出 parity 仍不在本 P1/P2-1 范围。

## P2-1 执行状态（2026-10-29）

基线中缺少的 Mixture D-optimal/Distance-based 选点、固定父设计增补、评价及 GUI/工程工作流已在本地完成并通过 `P2-ACC-01/02/03/04`。矩阵仍保留 `GEN-004/006` 的 partial，因为本包不实现父运行删除/替换的 improve 模式，也没有 Minitab 22 输出对照。当前进入 RSM 区间与诊断单元；基线差距其余项目仍按原排除范围处理。
