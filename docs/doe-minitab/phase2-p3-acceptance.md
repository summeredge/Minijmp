# DOE Phase 2 P2-3：验收跟踪

日期：2026-10-29
状态：两个独立 Review 单元均为 `APPROVE_SCOPED`；P3-ACC-01～06 本地通过，P3-REV-01 修复通过。审批只覆盖下表范围。

| 验收 | 状态 | 必需证据 |
|---|---|---|
| P3-ACC-01 多因子完整平衡设计矩阵及实验单位 | LOCAL_PASS | 生产路径与独立参考覆盖 2–6 因子、1–3 hard、完整 Cartesian 组合、嵌套身份、seed、角色边界及 10,000 次预算前拒绝。 |
| P3-ACC-02 受限随机化、身份及构造版本兼容 | LOCAL_PASS | v2 同 seed 完全复现，不同 seed 保持点集和单位；冻结 v1 seed 运行 ID 序；Schema v1–v5 迁移与 `.dexpl` 重开/复制/再分析回归通过。 |
| P3-ACC-03 Whole-plot 层平方和及推断 | LOCAL_PASS | 既有 D 与独立有理数/投影参考一致；多个 hard-only 项用整区 MSE；极大 hard 效应保留有效误差，零整区误差只关闭该层 F/p。 |
| P3-ACC-04 Subplot 层平方和、交互及推断 | LOCAL_PASS | 全部含 easy 项与独立参考一致；残差两层分解与总 SS/df 闭合；零子区误差只关闭该层 F/p。 |
| P3-ACC-05 GUI、诊断与失效生命周期 | LOCAL_PASS | 真实 Tk 覆盖动态输入/预览、创建/取消、误差 df、分层结果、残差图、响应变化后阻止旧结果绘图、完整区组修改及重编号禁用。 |
| P3-ACC-06 `.dexpl`、旧 Schema、帮助及跨模块回归 | LOCAL_PASS | Schema v1–v4 迁移与 v5 校验通过；v5 `.dexpl` 往返、裂区 v1 构造兼容、v2 裂区保存/重开/复制/再分析和损坏工程隔离通过；帮助、菜单、G12、Factorial/GFF 共享路径回归通过。 |
| P3-REV-01 增加完整区组保留历史运行顺序 | LOCAL_PASS；Review 修复通过 | v1 seed=1 1 hard+1 easy 与 v2 seed=1 2 hard+2 easy 反例逐 run_id 核对旧身份、三层顺序、设定、响应值和 dtype；追加 lineage 与随机化重建校验、重复增补拒绝、损坏工程恢复拒绝及真实 Tk 流程通过。核心/Schema/持久化 164 passed；真实 Tk 16 passed。 |

## Review 单元

| Review 单元 | 状态 | 范围 |
|---|---|---|
| SPLIT_PLOT_DESIGN_RANDOMIZATION | APPROVE_SCOPED | Local MCP Connector 独立只读 Review 批准的限定范围：角色、单位完整性、seed、运行预算、v1 兼容、Schema v5、GUI 取消和工程往返。 |
| SPLIT_PLOT_STRATIFIED_INFERENCE | APPROVE_SCOPED | Local MCP Connector 独立只读 Review 批准的限定范围：实际模型秩、全部效应、分层 SS/df/MS/F/p、零误差/大信号/单位与偏移边界、独立参考、GUI 和工程重分析。 |

上述 `APPROVE_SCOPED` 只适用于两个列明的 Review 单元，不扩展为 Minitab parity 或范围外能力的批准。全量 pytest 未运行；Minitab 22 parity 未验证；非平衡/部分实施和 REML/ML 不在本包范围。

## 本地验证记录

- `.venv` Python 3.11.9：Split-Plot/Schema/工程/Factorial/General Factorial/诊断/最优设计核心组 222 passed；包含六因子 `1e15*A` 下独立参考整区/子区 SS 128/1920 回归；完整命令见 [P2-3 收尾](phase2-p3-closeout.md)。
- 真实 Tk：`tests/test_doe_splitplot_gui.py` 10 passed、2 条 `tight_layout` 警告；`tests/test_doe_optimal_gui.py` 6 passed。
- P3-REV-01 本轮：核心/Schema/持久化/通用增补 164 passed；真实 Tk Split-Plot 与修改窗口 16 passed、2 条 `tight_layout` 警告；修改文件 `py_compile` 与 `git diff --check` 通过。未运行全量 pytest。
- Help/Menu/G12：94 passed。`py_compile` 和 `git diff --check` 在最终静态检查中复核。全量 pytest 未运行。
