# DOE Phase 2 P2-3：多因子平衡 Split-Plot 收尾

日期：2026-10-29
状态：`APPROVE_SCOPED`（两个独立 Review 单元获限定范围批准；P3-ACC-01～06 本地通过，P3-REV-01 修复通过）

## 交付范围

- 支持 2–6 个连续两水平因子、1–3 个 hard-to-change 因子、至少 1 个 easy-to-change 因子、至少 2 个完整重复区组；设计运行数上限 10,000，预算在 factorial 展开和 DataFrame 分配前检查。
- 旧 v1 两因子身份、整区 ID 和 seed 派生运行序保持原样。新多因子构造使用 `construction_version=v2`，不修改 DOE Schema v5。
- 创建窗口按因子数动态显示名称、水平与角色，变更后刷新有限行预览，并显示区组、整区、子区及两层误差 df。无效输入和取消不增加工作表。
- 分析覆盖全部 `2^k−1` 因子项，先验证实际固定模型秩，再分别计算整区和子区 SS/df/MSE/F/p；结果提供拟合、两层残差贡献和整体残差。零误差层不会输出该层显著性，另一层可独立推断。
- “修改设计”可增加完整区组并按 run ID 保留旧响应；裂区运行序重编号已禁用。P3-REV-01 进一步要求区组追加保留历史运行、整区和子区顺序。工程支持保存、重开、复制和再分析，损坏裂区工程不会替换当前工作簿。

## 独立参考

参考目录：`tests/fixtures/doe_phase2_splitplot_reference/`。生成器使用精确有理数构造响应，独立验证器以精确正规方程投影和正交列 SS 增量复算，均不导入 MiniJMP 生产模块。参考覆盖旧 D 工作包、1 hard + 2 easy、2 hard + 2 easy、3 hard + 1 easy、六因子边界、误差层零方差及身份/结构拒绝。

`reference.json` SHA-256：`8c4ccc639a44954582290a3e49cb85695b25a46f29a5fd0c575b8efb74e3f32f`。独立参考审查结论为 CLEAR；该结论核验 fixture，不等同于产品行为 Review。

数值回归覆盖响应单位缩放、`+1e14` 共同偏移、`1e14` hard 主效应和两种单层零误差边界。六因子 `1e15*A` hard 效应下，整区/子区误差 SS 仍为 128/1920。系数采用已验证正交矩阵的直接投影与 `math.fsum`，稳定中心化避免大共同偏移损失小误差；零误差阈值与 SS 闭合容差分开。

分层推断的本地独立代码复核最终为 CLEAR：模型秩、列范数、自由度、平方和闭合及大效应两层误差通过只读复算。该本地复核不是用户指定的正式独立 Review。

## 验证

项目解释器：`.venv\Scripts\python.exe`，Python 3.11.9。

| 范围 | 结果 |
|---|---:|
| Split-Plot、独立参考、Schema、持久化、Factorial/General Factorial、诊断与最优设计核心回归 | 222 passed |
| Split-Plot 真实 Tk 创建、预览、分析、图形、工程往返与修改流程 | 10 passed；2 条 Matplotlib `tight_layout` 警告 |
| 共享“修改设计”最优设计 GUI 回归 | 6 passed |
| 帮助中心、菜单本地化、G12 清单 | 94 passed |
| 修改 Python 文件 `py_compile` | 通过 |
| `git diff --check` | 通过 |

核心回归命令：

```powershell
$python = (Resolve-Path '.venv\Scripts\python.exe').Path
& $python -m pytest tests/test_doe_splitplot.py tests/test_doe_splitplot_analysis.py tests/test_doe_phase2_splitplot_references.py tests/test_doe_modify.py tests/test_doe_core.py tests/test_doe_factorial_schema.py tests/test_doe_schema_v2.py tests/test_doe_schema_v3.py tests/test_doe_schema_e.py tests/test_doe_persistence.py tests/test_doe_factorial.py tests/test_doe_factorial_anova.py tests/test_doe_factorial_blocks.py tests/test_doe_factorial_references.py tests/test_doe_general_factorial.py tests/test_doe_general_factorial_analysis.py tests/test_doe_diagnostics_contract.py tests/test_doe_optimal.py tests/test_doe_optimal_augmentation.py tests/test_doe_optimal_evaluation.py -q
```

帮助/菜单/清单回归 94 passed；全量 pytest 未运行。最终限定范围独立 Review 结论见下节。

## 厂商对标与边界

官方帮助确认 hard-to-change 因子在整区内保持不变，并分别随机化整区和子区；该页面未注明 Minitab 22 版本，也不定义此处固定区组模型的完整平方和/检验约定。[Minitab Support — Split-plot designs](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/supporting-topics/factorial-and-screening-designs/split-plot-designs-in-design-of-experiments/)。没有 Minitab 22 设计导出或数值对照，不声明版本 parity。功能矩阵 80 个 feature ID 与既有状态保持稳定；裂区相关条目仍为 `partial`。

## 独立 Review 结论与范围限制

2026-10-29，用户报告 Local MCP Connector 已完成 P2-3 最终只读 Review：

- `SPLIT_PLOT_DESIGN_RANDOMIZATION: APPROVE_SCOPED`
- `SPLIT_PLOT_STRATIFIED_INFERENCE: APPROVE_SCOPED`
- `P3-REV-01` 历史运行顺序保留修复通过。
- `P3-ACC-01～06` 本地验收通过；不将其另行表述为独立逐项批准。

全量 pytest 未运行；Minitab 22 parity 未验证；非平衡/部分实施、REML/ML、Kenward–Roger/Satterthwaite、多水平因子、额外子区重复、自定义整区、Split-Plot 预测区间与优化均不在本包范围。P2-4/P2-5 未启动。

## P3-REV-01：历史运行顺序保留修复

根因是旧 `replicate()` 增加 `block_count` 后调用 `create_split_plot()` 重建全部区组；随机数消耗随区组数变化，导致历史 run_order、whole_plot_order 和 subplot_order 被静默改写。独立反例固定为 v1（1 hard+1 easy、seed=1、2→3 区组）和 v2（2 hard+2 easy、seed=1、2→3 区组），新增前为每个 run_id 写入不同响应，以逐行比较身份、顺序和数据类型。

修复复用 Schema v5 现有 `augmentation_lineage` 与矩阵 SHA；沿用已允许的 `criterion=manual`，以 `batch_id=SPLITPLOT_APPEND_V1` 标记确定性追加算法。恢复时从未增补行重建父 block 数，以原 v1/v2 `_layout()` 校验旧前缀，再以 seed 和追加版本校验新后缀；因此矩阵 SHA 对顺序字段的覆盖不足由 Split-Plot 专用校验补足。响应值从原工作表按 run_id 原样复制，无法在原 dtype 下为空时拒绝操作。第二次追加、追加后重随机化和通用候选点增补均拒绝；Schema v4 不自动升级。

### P3-REV-01 本轮验证

项目解释器：`.venv\Scripts\python.exe`，Python 3.11.9。

| 范围 | 实际结果 |
|---|---:|
| Split-Plot、ANOVA、独立参考、Factorial Schema、DOE 持久化、核心 Schema 与通用增补 | 164 passed |
| 真实 Tk Split-Plot 修改与共享修改设计 GUI | 16 passed；2 条 Matplotlib `tight_layout` 警告 |
| 修改 Python 文件 `py_compile` | 通过 |
| `git diff --check` | 通过 |

核心命令：

```powershell
$python = (Resolve-Path '.venv\Scripts\python.exe').Path
& $python -m pytest tests\test_doe_modify.py tests\test_doe_splitplot.py tests\test_doe_splitplot_analysis.py tests\test_doe_phase2_splitplot_references.py tests\test_doe_factorial_schema.py tests\test_doe_persistence.py tests\test_doe_augment.py tests\test_doe_core.py tests\test_doe_schema_v2.py tests\test_doe_schema_v3.py tests\test_doe_schema_e.py -q
```

真实 Tk 命令：

```powershell
& $python -m pytest tests\test_doe_splitplot_gui.py tests\test_doe_optimal_gui.py -q
```

上述结果只覆盖本表列出的测试文件；全量 pytest 未运行。首次回归发现父 lineage 的 `block_count` 必须按原始区组数重建，已修正后全组通过。
