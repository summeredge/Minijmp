# DOE Phase 2 P2-4B/P2-4C：验收跟踪

日期：2026-10-30

当前快照：隔离 worktree，detached HEAD `a9210a21083c3789a99c3033c40b2c884b9d0208`。主工作树中的 P2-4A 未提交修改保留且单独验证。

总体状态：ACC-01～08 的本地验收完成；两个独立 Review 单元均为 `READY_FOR_INDEPENDENT_REVIEW`。此状态不等于 `APPROVE`。

| 验收 | 状态 | 证据与限制 |
|---|---|---|
| P4BC-ACC-01 Taguchi 新混合水平矩阵 | LOCAL_PASS | 独立 verifier 核对 L8、L16、L18 的行值、列频数、列对频数和列身份；数组哈希见收尾报告。L18 内部第 8 列正确映射官方第 9 列，五个非正交列对继续拒绝。 |
| P4BC-ACC-02 Taguchi 噪声稳健性与 S/N | LOCAL_PASS | 独立 48 行参考区分 4 个控制组合、每组 6 个噪声设置及 2 次重复；核对条件均值、样本 SD、S/N、极差和运行身份。四类静态公式及有效/无效零方差边界通过。 |
| P4BC-ACC-03 Taguchi 最佳设置及确认实验 | LOCAL_PASS | 独立参考核对主效应加性预测、阈值与目标两阶段筛选、并列、预算和不可达状态。动态设计保留目标斜率语义；新 `robust_then_target` 仅对静态设计开放。 |
| P4BC-ACC-04 Mixture 过程/总量联合设计 | LOCAL_PASS | v2 完整交叉、2–3 个总量水平、默认总量精确命中真实水平、间距容差、运行预算、Seed 点集稳定性及 v1 多过程变量兼容通过；真实 Tk 生命周期通过。 |
| P4BC-ACC-05 Mixture 联合模型与预测 | LOCAL_PASS | 独立参考的 72×15 矩阵 rank=15、残差 df=57；核对条件数、系数、SSE、拟合、预测和优化。秩亏 v2 模型被拒绝；预测区分比例与实际用量。 |
| P4BC-ACC-06 Mixture Replace/Improve | LOCAL_PASS | 使用现有 `select_augment()` 对有限候选集精确穷举。独立 C05：LOCK-A/LOCK-B 响应 11/22 保留，PARENT-003→CAND-C，rank 3 保持 3，logdet −4.605170185988→0，4 个子集全评估。预算不足、秩亏、已响应/实测行、候选重叠及映射/摘要篡改均拒绝；冲突的候选源 ID 会映射为新唯一运行 ID，来源表不变。 |
| P4BC-ACC-07 GUI、帮助与工作表生命周期 | LOCAL_PASS | 现有“混料最优设计”窗口增加 Improve、运行锁定/可替换选择、候选范围、Seed/预算、rank/logdet 和替换映射预览。真实 Tk 覆盖响应行自动保护、预览/创建、来源表不变、父/候选表删除后保存重开及单表复制。帮助正文和搜索索引已更新。 |
| P4BC-ACC-08 Schema、`.dexpl` 与跨模块回归 | LOCAL_PASS | DOE Schema v5、MixtureSpec 内部 schema_version 1 和原构造语义未升级；普通设计/append 保留顶层 Mixture metadata Schema 1，Improve 使用严格 Schema 2。Schema 1/v2 append/Schema 2 各走对应恢复验证；受损 Schema 2 `.dexpl` 在替换工作簿前失败。DOE、Split-Plot、Binary、表格、Help/Menu/G12 回归通过。 |

## 独立 Review 单元

| Review 单元 | 状态 | 范围 |
|---|---|---|
| `TAGUCHI_EXTENDED_ROBUST_DESIGN` | `READY_FOR_INDEPENDENT_REVIEW` | ACC-01/02/03 及 ACC-07/08 中的 Taguchi 范围通过；本地评审意见已修复并复验，不等于独立 Review 批准。 |
| `MIXTURE_PROCESS_AMOUNT_IMPROVEMENT` | `READY_FOR_INDEPENDENT_REVIEW` | ACC-04～08 本地通过；Schema 2 字段/兼容矩阵、独立 fixture SHA 与真实测试结果见收尾报告。 |

## 本轮验证

- Taguchi 专项全套（含 `tests/test_doe_phase2_p4bc_taguchi.py`）：169 passed，2 条既有 `tight_layout` 警告。
- Mixture 专项与 Improve/Schema 2（含真实 Tk、`.dexpl`、复制、测量值保护和 append 回归）：102 passed，16 条既有 SciPy clipping / Matplotlib layout 警告。
- DOE 持久化、EFG 工作簿、Split-Plot、Binary、Modify/PB、表格、Help/Menu/G12 共享回归：405 passed，3 条既有 `tight_layout` 警告。
- Taguchi 169 项和主工作树 P2-4A 109 项为本次批准前的既有证据；本轮未重跑 Taguchi，也未修改或测试写入主工作树。
- 独立 Replace fixture 由生产实现外部固定；C05 生产路径结果与 fixture 对应。Fixture SHA 与独立 verifier 本轮结果见收尾报告。
- 最终静态检查、fixture verifier 及准确命令见 [收尾报告](phase2-p4bc-closeout.md)。全量 pytest 未运行；未提交或推送。
