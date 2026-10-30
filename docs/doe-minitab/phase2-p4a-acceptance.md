# DOE Phase 2 P2-4A：验收跟踪

日期：2026-10-30
状态：`DSD_STEPWISE_SELECTION` 保持 `APPROVE_SCOPED`；`PB_FOLDOVER_ESTIMABILITY` 为 `READY_FOR_INDEPENDENT_REVIEW`。P4A-ACC-01～06 本地通过；本次不重新开发 DSD，也不为 PB 自行改为 APPROVE。

## 当前 main 联合验收（2026-10-30）

在包含 P2-4BC 提交 `0dcc4acb90d7601962a150182699ddf515adc0a3` 的 main 工作树上，P2-4A 指定组 96 passed，P2-4BC 指定组 113 passed，共享 Schema/持久化组（含 DOE v1–v5 兼容用例）118 passed；Split-Plot 与 Binary 回归合并 146 passed。P4A 真实 Tk 12 passed、正规 Foldover Tk 2 passed；Taguchi/Mixture 与 Split-Plot Tk 分别 14/10/10 passed，均按单文件串行执行。独立 DSD、PB、P4BC verifier 通过；完整命令和限制见 [P2-4A 收尾报告](phase2-p4a-closeout.md) 与 [P2-4BC 收尾报告](phase2-p4bc-closeout.md)。

以上是同一 main 源码快照的本地联合证据，不构成 Minitab 22 parity 或新增的独立 Review 批准；P4A Review 单元状态保持不变。

| 验收 | 状态 | 必需证据 |
|---|---|---|
| P4A-ACC-01 DSD Stepwise F 检验与逐步选择 | LOCAL_PASS | `select_dsd_stepwise()` 按“先移除、后进入”实现；进入用加入后模型的 MSE，移除用完整模型的 MSE。独立参考 `dsd_reference.json` 的 5 条轨迹（S01 主效应、S02 平方、S03 交互、S04 混合+区组、S05 先进入再删除）逐步核对动作、项、F、p、前后 SSE、秩与误差 df。 |
| P4A-ACC-02 DSD 层级、秩、边界与选择状态 | LOCAL_PASS | 强层级在进入与删除两侧同时校验；秩按列正交化判定，不使用 `lstsq` 奇异值截断；8 类停止原因与循环检测均有真实反例；alpha、候选项、初始/强制项冲突、饱和、零残差方差、缺失/非有限响应、来源改变均拒绝；候选项上限 64。 |
| P4A-ACC-03 PB Foldover 矩阵与原运行保留 | LOCAL_PASS | 12/20/24/28/32/36/40/44/48 全部折叠后逐点核对 `new_points_all`、`new_points_one`；原始 `run_id`/标准序/运行序/重复/设定/响应逐值保持不变；新增运行取新 ID、`source_run_id`、批次、空响应，运行序只进入后续区间。响应列保留原 dtype（可空 dtype 与 `object` 原样沿用）；numpy `float64`/`int64`/`uint64` 原本无法表达空值，转为 `Float64`/`Int64`/`UInt64`，并有独立用例逐值核对 dtype 往返与原值不变。 |
| P4A-ACC-04 PB Foldover 混杂/可估计性与谱系 | LOCAL_PASS | 使用实际编码矩阵与伪逆投影，PB32 的 465 个完全混杂在全折叠后归零且联合秩 32→63；单因子折叠按参考保留部分混杂（如 PB12 45 个）。界面分别报告完全混杂、部分混杂、可单独估计与不可估计交互的前后计数。`screening_matrix` 保持原始构造身份，恢复还逐个校验折叠变换和 FOLD1 固定 seed 顺序；损坏输入全部拒绝。 |
| P4A-ACC-05 GUI、生命周期与用户可见结果 | LOCAL_PASS | 真实 Tk 覆盖 Stepwise 勾选、候选项/初始项/强制项与 64 上限提示、选择历史与汇总、α/步骤非法输入、模型/响应/对比变化后清空旧表格、响应改动后禁止绘旧结果、手动模型默认路径不变；PB 折叠预览/创建/取消、单因子折叠、填写响应前后分析、保存重开复制与损坏谱系隔离；既有正规折叠路径非回归。 |
| P4A-ACC-06 `.dexpl`、Schema、帮助及跨模块回归 | LOCAL_PASS | PB 折叠 `.dexpl` 保存、重开、复制、再分析通过；篡改符号、来源、摘要，以及摘要与 fingerprint 同步重绑的非法折叠均拒绝载入且不替换活工作簿。Schema 仍为 v5，未新增字段；帮助正文、搜索索引、菜单本地化与 G12 清单同步。 |

## Review 单元

| Review 单元 | 状态 | 待审范围 |
|---|---|---|
| DSD_STEPWISE_SELECTION | APPROVE_SCOPED | 本次保持既有范围状态，不重新开发。 |
| PB_FOLDOVER_ESTIMABILITY | READY_FOR_INDEPENDENT_REVIEW | 原始 PB 构造、全/单因子符号反转、父运行身份与响应保留、新增运行与批次映射、非正规混杂投影、模型秩与零空间、谱系与 SHA、恢复与损坏拒绝、GUI 与重开、原正规折叠非回归。 |

上述状态不构成 Minitab 22 产品输出一致性的声明。

## P4A-REV-01：摘要自洽但 Foldover 变换语义不合法

状态：`LOCAL_PASS`。

PB12 全因子反例将 F1 恢复为来源水平，PB20 单因子反例改变未指定折叠的 F2；两例均同步重算矩阵摘要与工作表输入 fingerprint。`restore_design_result()` 与 `validate_pb()` 仍按逐运行折叠关系拒绝。REV-01 初期曾用行序约束 BASE 历史顺序；REV-02 已按 Schema v5 可证明范围修正：FOLD1 顺序可由 seed 重建，BASE 每个 Run ID 的历史顺序在摘要重绑后不可独立证明，详见下节。

## P4A-REV-02：PB Foldover 显示重排兼容

状态：`LOCAL_PASS`。

PB12 全因子与 PB20 单因子折叠分别按标准序、运行序显示，恢复、`validate_pb()` 和分析均通过，Run ID 对应的运行序、设定、响应和实测值未改变；重排后的 PB12 工程保存、重开、复制和再分析通过。FOLD1 运行序仍按固定 seed 独立校验，真正改动并重绑摘要/fingerprint 的 FOLD1 顺序继续拒绝。Schema v5 未保存 BASE 历史运行序快照，故只能验证 BASE `run_order` 为 `1..N` 排列，不能独立证明重新绑定摘要后的 BASE Run ID 顺序真实性；物理行序不作为证明。DSD 与正规 Fractional Foldover 状态不变。

## 本地验证记录

- `.venv` Python 3.11.9（pandas 3.0.6、numpy 2.4.6、scipy 1.15.3）。
- 独立参考：`verify_dsd_reference.py` 5 例重建一致，`dsd_reference.json` SHA-256 `ad4713ff3861f5aaffeeba9b17c1ba3979c9b4bb9b0305b1201fa7d6f094164a`；`verify_pb_foldover_reference.py` 9 个运行数一致，`pb_foldover_reference.json` SHA-256 `9ee6b929929a70994c89e8e3d998bcb6def610da9524116dad9c1d4c078fe0ab`。
- `tests/test_doe_pb_foldover.py` 50 passed；PB12/20/24/28/32/36/40/44/48 均覆盖全因子与单因子折叠、标准序/运行序重排、摘要重绑反例及顺序合同。
- `tests/test_doe_modify.py` 16 passed；`tests/test_doe_foldover.py` 12 passed；`tests/test_doe_foldover_gui.py` 2 passed。
- `tests/test_doe_persistence.py` 19 passed，含 PB12 重排后保存、重开、复制、再分析及损坏谱系拒绝；`tests/test_doe_dsd_stepwise.py` 18 passed；`tests/test_doe_p4a_gui.py` 12 passed（真实 Tk，串行执行）。
- REV-01 回归基线：普通 PB 与二元分析 34 passed；Help/Menu/G12 四组 103 passed，见前一轮记录。
- 独立 PB fixture verifier 逐项重建 PB12–PB48 共 9 种设计并通过。此轮未重跑 `test_doe_screening_gui.py` 整套；此前记录的 318 例合并运行解释器级中断仍不作为通过证据。
- `py_compile` 与 `git diff --check` 结果见收尾报告。
- PB 主要用例耗时可重复测量：PB48 全因子折叠由 24 s 降至约 1.5 s（批量投影替代逐对求解）。
