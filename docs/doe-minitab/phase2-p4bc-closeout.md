# DOE Phase 2 P2-4B/P2-4C 收尾报告

日期：2026-10-30

状态：ACC-01～08 本地验收完成，Taguchi 与 Mixture 两个单元均为 `READY_FOR_INDEPENDENT_REVIEW`。没有将本地通过改写为独立 `APPROVE`。未提交、推送、打标签或启动 P2-5。

## 工作树边界

- P2-4B/P2-4C 在 `C:\Users\shaoy\.codex\worktrees\16af\Minijmp` 的 detached HEAD `a9210a21083c3789a99c3033c40b2c884b9d0208` 完成。该 worktree 的源代码、帮助、测试与验收文档保持未提交。
- P2-4A 保留在 `C:\Users\shaoy\Documents\Minijmp` 的原有未提交状态；本任务没有修改、撤销或整理其文件。另在该目录使用项目 `.venv` 运行 109 项定向回归并通过。
- Python：`C:\Users\shaoy\Documents\Minijmp\.venv\Scripts\python.exe`，Python 3.11.9。

## 已完成范围

### Taguchi

- 增加 L8(4^1 2^4) 与 L16(4^1 2^12) 标准混合水平表；L18 保留原矩阵行序，将内部第 8 列映射为官方第 9 列。已验证的矩阵 SHA-256：

| 数组 | 矩阵 SHA-256 |
|---|---|
| L8(4^1 2^4) | `256220af19c32211b310270f374eb0d1bdfb66c54a0dfc4980decd4bc7646543` |
| L16(4^1 2^12) | `736cf2f6d54c2f5556781c06bbdb6364fe8994e57ff247a1f59f8110c35d41b0` |
| L18(2^1 3^7) | `767f1ad05d8f96ba082346c8bd4c06bad848e7e82a88438d1756f6d6c3b99a76` |

- L18 的五个非正交列对按官方列号 3/4/5/6/7 与 9 记录并拒绝。L8/L16 的水平分配、正交性和列标签均由独立 verifier 逐项核对。
- 噪声分析按全部噪声因子的实际水平元组识别条件，并分别保留 condition count、observation count、重复号和 Run ID；保留有效的零方差 Smaller/Larger S/N。
- 新增静态 `sn_maximum` 与 `robust_then_target` 精确枚举；阈值无候选时返回 `target_unreachable`，不切换优化目标。动态设计继续使用原目标斜率/动态 S/N。

### Mixture

- DOE Schema v5 与 Mixture Schema 1 未升级。使用已有 `construction_version=v2` 区分新构造；多总量水平作为普通运行设定保存，`amount_settings` 仍只表示默认值。v1 固定总量恢复语义未变，旧读者会拒绝未知 v2 构造而不会将其误读为 v1。
- v2 支持 2–4 个组分、0–3 个过程变量和 2–3 个正总量水平；Mixture+Process+Amount 联合场景要求 1–3 个过程变量。设计完整交叉，按比例单独验证 `Σxi=1`，并以 `Ai=T×xi` 返回实际用量。
- 默认联合模型含组分主项、所选 Scheffé 二/三次项、组分×过程和组分×总量项，不自动加入过程×总量。独立参考核对 72×15 设计矩阵，rank=15、df=57、条件数、系数、SSE、拟合及预测。
- 预测、优化与图形使用保存的分析项和编码；秩亏 v2 矩阵被拒绝。真实 Tk 覆盖 v2 创建、预览、保存、重开、复制、再分析、预测、优化调用和图形调用。

## 独立参考

生成器和 verifier 仅依赖 Python 标准库，不导入生产代码。最终 verifier 输出：

```text
P4BC reference verified: 3 arrays; 48 noise runs; 4 controls/6 noise conditions/24 condition groups; 90 mixture runs; 72x15 model; 4 D-opt candidates; 11 invalid boundaries
```

冻结 `reference.json` SHA-256：`f23cad153fd383bfef6be5b0bdb88d37009e338b89e19a3e92935464ba68ebd7`。README 中的生成记录已同步此值；manifest 由生成器重建并由 verifier 校验。夹具也包含 D-optimal Replace 的独立枚举结果，但生产 Replace/Improve 因下述安全边界未实现。

独立 Replace oracle 的生产路径复核通过：`LOCK-A`/`LOCK-B` 的响应 11/22 保持不变；`PARENT-003` 被 `CAND-C` 取代。rank 均为 3，logdet 从 -4.605170185988 升至 0，4 个候选子集全部评估；结果与固定参考一致。该全局最优结论只限该离散候选域。

## Replace/Improve 与恢复合同

实现位于 `code/doe_mixture_improvement.py`，通过现有混料最优设计窗口调用。父设计和候选设计必须各自通过 DOE v5、Mixture Schema 1 恢复；结果保留完整父/候选快照、类型保真的响应快照及 SHA、Locked/Replaceable/Candidate/Selected 身份、三方替换映射、模型定义和矩阵 SHA/rank/logdet。恢复时独立重算所有有限候选子集，核对搜索次数、映射、停止原因及最优标志。

响应或 DOE 实测值非空的父行自动保护且 API 拒绝替换。Replaceable 由用户明确选择，默认所有父行 Locked。候选点不得已存在于父设计设定中，搜索域不得有重复设定。新增行继承被替换父行的标准序/运行序位置，响应初始化为空；后续填入响应不使谱系失效。Locked 行的运行 ID、顺序、设定、响应和实测值与父快照逐字段一致。

| 工作表状态 | Mixture 顶层 Schema | MixtureSpec schema | DOE Schema | 恢复路径 |
|---|---:|---:|---:|---|
| 普通 v1/v2 Mixture 设计 | 1 | 1 | 当前 DOE v5 | 原严格字段与 v1/v2 构造校验。 |
| 普通 append-only 增补 | 1 | 1 | v5 `augmentation_lineage` | DOE v5 先重建并核对父/新增矩阵，再逐行检查 Mixture 约束；v2 追加结果不再按完整交叉点集误判。 |
| Replace/Improve | 2 | 1 | v5，无当前 DOE append/optimal lineage | 验证完整 `improvement_lineage` 快照、SHA、身份、约束与重算优化评价；不使用原始完整交叉构造器。 |

Mixture metadata Schema 1 字段和 `MixtureSpec.schema_version=1` 保持不变；Schema 2 只给 Replace/Improve 使用。DOE Schema v5 不变。旧读取器会因未知顶层版本明确拒绝 Schema 2。普通 append/选点入口拒绝 Schema 2，当前不支持连续嵌套多次 Improve。SHA-256 用于数据一致性，不是防恶意篡改的数字签名。详细字段合同见[方法合同第 5 节](phase2-p4bc-method-contract.md)。

## 实际验证

所有命令均使用项目 `.venv` Python，Tk 测试按单进程串行运行。

1. Taguchi 专项全套为 Schema 2 批准前的既有基线；本轮未重跑 Taguchi 生产测试：

```powershell
& $python -m pytest tests\test_doe_taguchi_arrays.py tests\test_doe_taguchi_sn.py tests\test_doe_taguchi_dynamic.py tests\test_doe_taguchi_noise.py tests\test_doe_taguchi_gui.py tests\test_doe_taguchi_persistence.py tests\test_doe_taguchi_references.py tests\test_doe_phase2_p4bc_taguchi.py -q
```

既有结果：169 passed，2 warnings。Taguchi 相关源文件本轮未改。

2. 当前隔离 worktree，Mixture 全套（包含 Improve、Schema 2、持久化和真实 Tk GUI）：

```powershell
& $python -m pytest tests\test_doe_mixture_constraints.py tests\test_doe_mixture_lattice.py tests\test_doe_mixture_centroid.py tests\test_doe_mixture_vertices.py tests\test_doe_mixture_model.py tests\test_doe_mixture_anova.py tests\test_doe_mixture_predict.py tests\test_doe_mixture_optimize.py tests\test_doe_mixture_optimal.py tests\test_doe_mixture_plots.py tests\test_doe_mixture_gui.py tests\test_doe_mixture_persistence.py tests\test_doe_mixture_references.py tests\test_doe_mixture_improve.py tests\test_doe_phase2_p4bc_mixture.py -q
```

结果：102 passed，16 warnings。

3. 当前隔离 worktree，DOE 持久化、Split-Plot、Binary、表格、Help/Menu/G12 和共享回归：

```powershell
& $python -m pytest tests\test_doe_persistence.py tests\test_doe_efg_workbook_integration.py tests\test_doe_splitplot.py tests\test_doe_splitplot_analysis.py tests\test_doe_phase2_splitplot_references.py tests\test_doe_binary_analysis.py tests\test_doe_binary_probability.py tests\test_doe_binary_optimize.py tests\test_doe_modify.py tests\test_doe_pb.py tests\test_doe_schema_v2.py tests\test_doe_schema_v3.py tests\test_doe_schema_e.py tests\test_doe_factorial_schema.py tests\test_worksheets.py tests\test_file_io.py tests\test_sheet_context.py tests\test_help_center.py tests\test_menu_localization.py tests\test_g12_inventory.py -q
```

结果：405 passed，3 warnings。

4. 主工作树 `C:\Users\shaoy\Documents\Minijmp` 中的 P2-4A 定向回归是批准前的既有证据；本轮未改动、未重测主工作树：

```powershell
& $python -m pytest tests\test_doe_dsd_stepwise.py tests\test_doe_pb_foldover.py tests\test_doe_p4a_gui.py tests\test_doe_core.py tests\test_doe_modify.py tests\test_doe_pb.py -q
```

既有结果：109 passed。当前隔离工作树的共享测试见第 3 项；不将两次、不同工作树的结果合并成一次覆盖证明。

5. 独立参考 verifier 与最终静态检查：

```powershell
$python = 'C:\Users\shaoy\Documents\Minijmp\.venv\Scripts\python.exe'
& $python -m py_compile code\doe_mixture.py code\doe_mixture_analysis.py code\doe_mixture_predict.py code\doe_mixture_optimize.py code\doe_mixture_dialog.py code\doe_mixture_improvement.py code\doe_optimal_design.py code\doe_augment.py code\worksheets.py tests\test_doe_mixture_improve.py tests\test_doe_mixture_persistence.py tests\test_doe_phase2_p4bc_mixture.py
& $python tests\fixtures\doe_phase2_p4bc_reference\verify.py
git diff --check
```

Fixture `reference.json` SHA-256：`f23cad153fd383bfef6be5b0bdb88d37009e338b89e19a3e92935464ba68ebd7`。全量 pytest 未运行。`tight_layout` 和 SLSQP 越界裁剪警告来自绘图/优化器路径；相关测试通过。未验证 Minitab 22 输出逐项等价。Improve 仅证明保存候选子集内的精确最优，不声称连续可行域全局最优。

## Review 与结论

| Review 单元 | 本地状态 |
|---|---|
| `TAGUCHI_EXTENDED_ROBUST_DESIGN` | `READY_FOR_INDEPENDENT_REVIEW` |
| `MIXTURE_PROCESS_AMOUNT_IMPROVEMENT` | `READY_FOR_INDEPENDENT_REVIEW` |

没有把本地测试通过改写成独立 Review `APPROVE`。下一步交由 ChatGPT Web 通过 Local MCP Connector 独立 Review；保留当前未提交工作树。

## 复杂度复核

按实际 diff 复核：Improve 复用现有 D-optimal `select_augment()` 和当前 Mixture 对话框；新模块仅承载严格快照编码、谱系恢复与精确搜索合同。保存/加载/复制各验证一次，避免在同一边界重复重跑谱系；没有新增依赖、DOE Schema 字段或旁路列。完整快照、矩阵 SHA、受保护行比较及恢复时重算均有明确的持久化/审计消费者，未发现可删而不损失合同的检查。
