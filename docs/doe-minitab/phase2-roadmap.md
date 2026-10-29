# DOE Phase 2 路线图（重建稿）

日期：2026-10-29。原始 `phase2-roadmap.md` 在本轮开始时不存在。本稿根据 `roadmap.md` 中 P2-0 摘要、工作包收尾证据和本轮目标重建，不声称复原缺失原文。详细缺口见 [差距分析](phase2-gap-analysis.md)，验收号见 [验收合同](phase2-acceptance.md)。

## 阶段与关口

| 阶段 | 内容 | 进入条件 | 通过条件 / 状态 |
|---|---|---|---|
| P0 | 基线、用户改动、Schema、环境与合同盘点 | 目标启动 | `main` 含 H 基线；保留已有 roadmap 修改；缺失 P2-0 原稿如实标注；完成 |
| P1 | Mixture 选点方法合同与独立数学参考 | P0 完成 | `P2-ACC-01/02` 的参考和方法自检通过，方可修改选点生产路径 |
| P2 | Mixture D-optimal/Distance-based 选点、保留父设计增补、持久化与 GUI | P1 通过 | 本地 `P2-ACC-01/02/03/04` 通过；`MIXTURE_OPTIMAL_READY_FOR_REVIEW` |
| P3 | 连续 CCD/BBD/custom RSM SE Fit、CI 和 PI | Mixture P1/P2 关口通过 | `P2-ACC-05` 独立解析参考与边界通过；完成 |
| P4 | 连续 RSM 诊断指标 | P3 通过 | `P2-ACC-06/07` 独立矩阵、结果发布与工程生命周期通过；完成 |
| P5 | 两单元的 Tk、帮助、工程集成、矩阵及回归收尾 | P2 与 P4 均通过 | 本地验收与独立 Review 完成；A、B 均为限定范围 `APPROVE`；`COMPLETE_SCOPED`，不启动后续包 |

P2 内有强制子关口：先实现 Mixture D-optimal 与 Distance-based 选点，并以独立参考通过 `P2-ACC-01/02`；**通过前不得开始任何 Mixture 增补实现**。增补和工程生命周期另按 `P2-ACC-03/04` 验收。

### 历史检查点：2026-10-29 P2a/P2b

独立参考 verifier 13 项通过，SHA-256 `29bd937eae7415579c9992afe780b9546708653d604cfe939afffcdcf749a4ed`；Mixture/optimal/schema 核心回归 98 passed，Mixture 真实 Tk 生命周期 8 passed，普通最优设计 GUI 6 passed，Mixture 持久化 4 passed，DOE schema v2/v3 33 passed，坏 DOE 元数据载入隔离 6 passed、4 deselected，帮助中心 13 passed，菜单 66 passed。静态 Review 指出的响应整数精度与父空批次值改写已修复并有反例。单元 A 曾达到 `MIXTURE_OPTIMAL_READY_FOR_REVIEW`，随后进入 P3；未支持的 replace/improve 与版本明确输出对照仍按 partial 记录。

### 历史检查点：2026-10-29 P3/P4 首轮 Review 前

独立 RSM verifier 覆盖 9 个区间组合和 9 行影响诊断；RSM 模型回归 27 passed、区间/诊断核心 37 passed、Predict Tk 7 passed、Analyze Tk 12 passed、工程保存/重开/复制集成 1 passed，帮助 13 passed、菜单 66 passed。独立代码审查发现并修复响应基线改变时误判零方差；全部受影响组复跑通过。P3/P4 本地通过；单元 B 达到 `LOCAL_PASS`。随后首次独立 Review 对 A-01/B-01 给出 ITERATE，修复细节见下方最终检查点。

## 最终检查点：2026-10-29

- `MIXTURE_OPTIMAL` 的 P2-ACC-01/02/03/04 与 `DOE_RSM_INTERVAL_DIAGNOSTICS` 的 P2-ACC-05/06/07 均通过本地验收；ChatGPT 经 Local MCP Connector 复审分别给出限定范围 `APPROVE`。
- A-01 已修复：Mixture 设计评价对所有运行配对计算最小平方距离，重复设定报告 0，并同时报告唯一点数和重复点数。B-01 已修复：Predict 重算开始时清除旧结果；真实 Tk 回归覆盖响应失效及来源工作表切换。
- 修复后的定向回归：Mixture 核心 22 passed、Mixture Tk 8 passed（6 条 `tight_layout` 警告）、Predict Tk 7 passed。此前独立参考及其他本地验收结果见 [P1 收尾记录](phase2-p1-closeout.md)；本次收尾未重跑 pytest，全量 pytest 未运行。
- 本地功能矩阵保持 80 项：58 implemented、19 partial、2 unknown、1 excluded。DOE Schema v5、Mixture Schema 1 不变。没有 Minitab 22 产品输出，不声明 `VERSION22_PARITY`。
- Goal 已完成并停止；不自动启动 P2-2B、P2-3、P2-4 或 P2-5。

## 实施顺序

1. 不改 DOE Schema v5 或 Mixture Schema 1；先检查 v5 的现有 `optimal_lineage` / `augmentation_lineage` 能否表达混料身份与恢复验证。
2. 先独立构造 Mixture 选点参考，再接入 `MixtureTermModel` 和既有搜索器。距离空间需固定组分坐标、伪组分处理、过程/总量归一化、并列顺序与重复语义；未经合同支持的坐标组合明确拒绝。
3. 先完成 Mixture 创建选点，再完成以全部父运行作为固定锚点的增补；父响应保留、新响应为空、run ID 唯一，取消/失败无副作用。
4. Mixture 独立关口通过后，复用现有 Predict 模型与实际分析矩阵实现连续 RSM 区间，再接入诊断输出。
5. 最后复核菜单/帮助/搜索索引、功能矩阵、`.dexpl` 保存重开复制、响应变更失效和 E/F/G/H 回归。

## 停止边界

任何验收关口未通过时记录阻断和证据，不越级开始后续阶段。完成本路线图不自动启动 P2-2B、P2-3、P2-4、P2-5，不提交、不推送、不打 tag、不发布、不打包 EXE。两个验收单元都可交独立 Review 且本地测试无阻断时停止，保留工作区。
