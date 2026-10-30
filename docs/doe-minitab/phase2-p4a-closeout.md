# DOE Phase 2 P2-4A 收尾：筛选设计增强

日期：2026-10-30
状态：`DSD_STEPWISE_SELECTION` 保持 `APPROVE_SCOPED`；`PB_FOLDOVER_ESTIMABILITY` 为 `READY_FOR_INDEPENDENT_REVIEW`。

## 最终联合集成验收（2026-10-30）

- 验收基线为 `main` HEAD `0dcc4acb90d7601962a150182699ddf515adc0a3`，包含 P2-4BC；P2-4A 改动在同一工作树中完成最终验收。DOE Schema 仍为 v5。
- 指定回归：P2-4A 96 passed；P2-4BC 113 passed；共享 Schema/持久化及 `test_doe_schema_e.py` 合计 118 passed；Split-Plot 与 Binary 合并 146 passed。
- 真实 Tk 按单文件串行：`test_doe_p4a_gui.py` 12、`test_doe_foldover_gui.py` 2、`test_doe_taguchi_gui.py` 14（2 条既有 `tight_layout` 警告）、`test_doe_mixture_gui.py` 10（7 条既有 `tight_layout` 警告）、`test_doe_splitplot_gui.py` 10（2 条既有 `tight_layout` 警告）。
- 帮助/菜单/清单回归：`test_help_center.py` 13、`test_menu_localization.py` 66、`test_g12_inventory.py` 15 passed。
- 独立 fixture：DSD verifier 5 条轨迹、PB verifier 9 种运行数、P4BC verifier 3 个数组及其余噪声/Mixture 边界均通过；DSD、PB 与 P4BC reference SHA 分别为 `ad4713ff3861f5aaffeeba9b17c1ba3979c9b4bb9b0305b1201fa7d6f094164a`、`9ee6b929929a70994c89e8e3d998bcb6def610da9524116dad9c1d4c078fe0ab`、`f23cad153fd383bfef6be5b0bdb88d37009e338b89e19a3e92935464ba68ebd7`。
- 联合覆盖了 DOE v1–v5、Mixture Schema 1/2、PB/DSD 与 Taguchi/Mixture 的创建分析、修改、损坏元数据隔离，以及 `.dexpl` 保存、重开、复制和再分析。修复了 `doe: null` 被当成缺少 DOE 元数据的问题；显式损坏值现在会拒绝载入且不替换活工作簿。
- 本轮未运行全量 pytest，也未运行整套 `test_doe_screening_gui.py`；该套件既有解释器级中断仍属测试稳定性风险。未验证 Minitab 22 数值一致性；连续 Mixture 可行域全局最优未证明。两个 P4A 单元及两个 P4BC Review 单元的既有范围状态不因本地联合通过而改变。

## 1. P4A 开发基线（历史：P4BC 合入前）

- 当时分支 `main`，HEAD `a9210a2`（P2-3 收尾提交），起始工作区干净；该记录早于 P4BC 合入及上方联合验收。
- `.venv` Python 3.11.9、pandas 3.0.6、numpy 2.4.6、scipy 1.15.3。
- 未升级 DOE Schema：仍为 v5，未新增字段。

## 2. 范围与方法

方法合同见 [P2-4A 方法合同](phase2-p4a-method-contract.md)。要点：

1. DSD Stepwise 按官方描述实现“先移除、后进入”：进入检验的 F 使用加入后模型的 MSE，移除检验使用完整模型 MSE；每一步保持强层级；秩与残差自由度按列正交化判定，避免 `lstsq` 奇异值截断在饱和边界误判可估计性。
2. PB Foldover 只做全部或单因子符号翻转，全部评估基于实际编码矩阵；不生成正规 defining relation，不使用 Roman Numeral Resolution。
3. `screening_matrix.matrix_sha256` 语义固定为**原始 BASE 批次**身份；完整折叠矩阵由 `foldover_lineage` 的前后摘要校验。
4. P4A-REV-01/02 后，恢复逐对验证折叠关系和身份，不依赖工作表物理行顺序；FOLD1 执行序按固定 seed 重建。BASE `run_order` 验证为 `1..N` 排列，显示重排不改字段。Schema v5 无 BASE 创建时的运行序快照，摘要与 fingerprint 重绑后无法独立证明每个 BASE Run ID 的历史运行序；不以显示行序充当证据。正规 Fractional Foldover 路径不套用 PB 专用规则。

## 3. 独立参考

目录 `tests/fixtures/doe_phase2_p4a_reference/`：

| 文件 | 作用 | SHA-256 |
|---|---|---|
| `dsd_reference.json` | 5 条 Stepwise 轨迹（主效应、平方、交互、混合+区组、进入后删除） | `ad4713ff3861f5aaffeeba9b17c1ba3979c9b4bb9b0305b1201fa7d6f094164a` |
| `pb_foldover_reference.json` | 9 个 PB 运行数的点集、符号、秩、混杂计数 | `9ee6b929929a70994c89e8e3d998bcb6def610da9524116dad9c1d4c078fe0ab` |
| `build_dsd_reference.py` / `build_pb_foldover_reference.py` | 独立构建（不导入生产模块） | — |
| `verify_dsd_reference.py` / `verify_pb_foldover_reference.py` | 重建并逐步复核 | — |
| `exact_linear.py` | 标准库精确有理数线代 | — |

DSD 参考采用精确有理数 F 与 p（`scipy.stats.f.sf` 仅做尾部换算），响应由解析模型加整数扰动构造。

### DSD 选择轨迹

| 案例 | 轨迹（动作/项/p） | 最终秩 / 残差 df |
|---|---|---|
| S01 主效应 | 进入 F1（1.79e-4）、进入 F2（4.17e-21） | 3 / 10 |
| S02 平方 | 进入 F1（1.85e-2）、进入 F1²（2.25e-21） | 3 / 10 |
| S03 交互 | 进入 F1（1.87e-2）、F2（8.24e-4）、F1*F2（1.21e-21） | 4 / 9 |
| S04 混合+区组 | 进入 F5、F1、F1*F5（2.245e-2） | 5 / 23 |
| S05 进入后删除 | 10 步：8 次进入、1 次移除 F4*F5（p=0.572）、再进入 F2*F5 | 9 / 5 |

S05 是本轮要求的“真实出现先进入、再删除”的确定性案例。

### PB 折叠前后（全因子折叠）

| 运行数 | 主效应秩 | 联合秩（前→后） | 完全混杂（前→后） |
|---|---|---|---|
| 12 | 12 → 12 | 12 → 23 | 55 → 0 |
| 20 | 20 → 20 | 20 → 39 | 171 → 0 |
| 24 | 24 → 24 | 24 → 47 | 253 → 0 |
| 28 | 28 → 28 | 28 → 55 | 351 → 0 |
| 32 | 32 → 32 | 32 → 63 | 465 → 0 |
| 36 | 36 → 36 | 36 → 71 | 595 → 0 |
| 40 | 40 → 40 | 40 → 79 | 741 → 0 |
| 44 | 44 → 44 | 44 → 87 | 903 → 0 |
| 48 | 48 → 48 | 48 → 95 | 1081 → 0 |

单因子折叠只移除与折叠因子相关的混杂：PB12 折叠 F1 后为 0 个完全混杂 + 45 个部分混杂；PB32 折叠 F1 后仍余 420 个完全混杂，因此不会被描述为全模型去混杂。

## 4. 实现范围

- `code/doe_stepwise.py`：Stepwise 状态机、层级、秩/df、停止原因与最终重分析。
- `code/doe_pb_foldover.py`：PB 折叠矩阵、批次/运行映射、谱系摘要与实际矩阵秩/投影。
- `code/doe_core.py`：`screening_matrix_sha256(base_only=)`；PB 折叠的构造校验只核对 BASE 批次；谱系允许 `plackett_burman` 并强制 construction v2、无区组、保留构本身份。
- `code/doe_pb.py`：折叠设计按 BASE 批次校验摘要。
- `code/doe_modify.py`：已折叠 PB 禁止重新随机化、重编号；`modify_summary` 明示原因。
- `code/doe_augment.py`：任何折叠设计禁止通用增补。
- `code/doe_dialog.py`：DSD 分析新增“逐步选模”设置（α、最大步骤、候选项/初始项/强制项文本）、64 候选项提示、选择历史/汇总表、参数变化失效、名义推断提示。
- `code/doe_foldover_dialog.py`：来源列表纳入 PB，PB 专用预览与限制说明，帮助路由按来源切换。
- 帮助、搜索索引、CHANGELOG、功能矩阵（SCR-003、FAC-012）、G12 清单同步。

## 5. 验证

实际执行（Windows PowerShell、`.venv`）：

- `tests/test_doe_pb_foldover.py`：50 passed；覆盖 PB12/20/24/28/32/36/40/44/48 的全因子和单因子折叠、REV-01 摘要重绑、REV-02 标准序/运行序显示及顺序篡改。
- `tests/test_doe_modify.py`：16 passed；`tests/test_doe_foldover.py`：12 passed；`tests/test_doe_foldover_gui.py`：2 passed，正规 Fractional Foldover 未回归。
- `tests/test_doe_persistence.py`：19 passed，包含标准序显示下保存、重开、复制和再分析，以及损坏谱系拒绝。
- `tests/test_doe_dsd_stepwise.py`：18 passed；`tests/test_doe_p4a_gui.py`：12 passed（真实 Tk，串行执行）。
- 独立 `verify_pb_foldover_reference.py` 重建 PB12–PB48 共 9 种设计并通过；参考 fixture SHA-256 为 `9ee6b929929a70994c89e8e3d998bcb6def610da9524116dad9c1d4c078fe0ab`。
- 此轮未重跑 `test_doe_screening_gui.py` 整套；此前记录的 318 例合并运行解释器级中断仍不作为通过证据。本 Goal 未扩展为 Tk 崩溃排查。
- BASE `run_order` 在 Schema v5 中没有独立的父设计快照；只验证 `1..N` 排列，不宣称可认证重绑摘要后的逐 ID 历史顺序。FOLD1 顺序可由 seed 重建且篡改仍拒绝。
- `.venv` Python 3.11.9 下，改动模块 `py_compile` 通过；`git diff --check` 通过。

未执行：全量 pytest、`test_doe_screening_gui.py` 整套。

## 6. 已知限制

- 未获得 Minitab 22 产品输出，不声明版本 parity 或标准序一致。
- Stepwise 仅实现合同范围；AICc/BIC、独立 forward/backward、LASSO、best subsets 等未实现。
- PB 折叠不支持中心点、分类因子、重复批次、分区组或二次折叠；这些原始 PB 设计仍可创建与分析。
- 界面在 Tk 主线程内完成选模；候选上限 64 与步数上限共同约束运行时长，未引入后台线程框架。

## 7. 交接

正式独立 Review 未包含在本次集成收尾中：`DSD_STEPWISE_SELECTION` 保持 `APPROVE_SCOPED`，`PB_FOLDOVER_ESTIMABILITY` 仍为 `READY_FOR_INDEPENDENT_REVIEW`。本次本地提交不推送。
