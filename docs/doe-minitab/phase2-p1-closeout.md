# DOE Phase 2 P1 核心对标收尾

日期：2026-10-29。状态：**本地验收及独立 Review 完成；A、B 均为限定范围 APPROVE**。本记录只覆盖本 Goal 的两个验收单元，不启动后续工作包。

## 验收 A：MIXTURE_OPTIMAL

状态：P2-ACC-01/02/03/04 本地通过；首轮 Review 的 A-01 已修复，独立复审为 `APPROVE`。

- 独立 Fraction 参考 verifier 13 项通过，参考 SHA-256：`29bd937eae7415579c9992afe780b9546708653d604cfe939afffcdcf749a4ed`。
- Mixture/optimal/schema 核心回归 98 passed；真实 Tk Mixture 生命周期 8 passed；Mixture 持久化 4 passed；DOE schema v2/v3 恢复 33 passed；坏元数据隔离 6 passed、4 deselected；普通最优设计 GUI 6 passed。
- 覆盖 D-optimal/Distance-based 选点和固定父设计增补、约束/秩/评价、取消与旧预览失效、响应与 run/batch lineage 保留、保存重开复制重分析。
- `GEN-004/ACC-056` 与 `GEN-006/ACC-058` 保持 partial：未实现父运行 replace/improve，未取得版本明确的 Minitab 产品输出。

## 验收 B：DOE_RSM_INTERVAL_DIAGNOSTICS

状态：P2-ACC-05/06/07 本地通过；首轮 Review 的 B-01 已修复，独立复审为 `APPROVE`。

- 独立 Fraction 参考核验 9 种置信度/方向组合和 9 行逐点诊断通过；`reference.json` SHA-256：`d87d1720c24000fec7ebbf42cb2e1f58f8c52d2be8fadfcee7600f3bc4121a72`。
- `.venv` Python 3.11.9 下 RSM 分析/自定义/类别回归 27 passed；预测/区间/诊断核心 37 passed；Predict Tk 7 passed；Analyze Tk 12 passed，3 条 Matplotlib `tight_layout` 警告；E/F/G 保存重开复制集成 1 passed，3 条同类警告；帮助 13 passed；菜单 66 passed。
- 真实 GUI 覆盖响应变更后的重新计算和过期结果阻止、来源切换、保存重开复制后的诊断发布；逐点结果按运行 ID 对齐。
- 独立代码审查发现方差阈值受响应基线影响；修复后 +1e8 平移测试确认区间可用、Cook's D 9/9 可用，精确拟合及零响应仍不可用。独立复核无剩余发现。
- 适用范围仅连续 CCD/BBD/custom RSM。多区组区间、Logistic、Mixture、Split-Plot、优化器候选区间和自动删点不支持。

## 统计方法与官方范围

区间使用当前实际满秩设计矩阵和 `MSE=SSE/df_error`；无纯误差但残差自由度及方差有效时仍可计算。Minitab 官方响应面方法页列出 SE Fit、均值置信区间与预测区间，诊断页列出 leverage、Cook's Distance 与 DFITS；网页没有标注产品版本。没有 Minitab 22 产品输出，不声明 `VERSION22_PARITY`。

参考：[RSM 方法来源](sources.md)、[Phase 2 验收合同](phase2-acceptance.md)、[P1 方法合同](phase2-p1-method-contract.md)。

## 功能矩阵与 Schema

- 矩阵 80 项。P2-0 基线：58 implemented、18 partial、3 unknown、1 excluded；当前：58 implemented、19 partial、2 unknown、1 excluded。`RSM-009` 从 unknown 调整为 partial；RSM-015 与 GEN-009 的实现状态不变，补充本地诊断证据。Mixture replace/improve 的 partial 保持不变。
- DOE Schema 仍为 v5；Mixture Schema 仍为 1；未新增字段或迁移。

## Review 与 Git

| 验收单元 | 独立 Review 结论 |
|---|---|
| MIXTURE_OPTIMAL | 首轮 `ITERATE`；修复后复审 `APPROVE` |
| DOE_RSM_INTERVAL_DIAGNOSTICS | 首轮 `ITERATE`；修复后复审 `APPROVE` |

首轮 ChatGPT/Local MCP Connector Review 的 A-01 指出重复 Mixture 运行被排除在最小平方距离计算之外；现按全部运行计算，并保留唯一点数和重复点数。`tests/test_doe_mixture_optimal.py tests/test_doe_optimal_evaluation.py -q` 为 22 passed，真实 Tk Mixture 测试 `tests/test_doe_mixture_gui.py -q` 为 8 passed（6 条 `tight_layout` 警告）。B-01 指出预测失败/切换来源后旧 CI/PI 仍可见；现于重算开始时清除旧表，并增加两条真实 Tk 失败路径回归。`tests/test_doe_predict_gui.py -q` 为 7 passed。ChatGPT 经 Local MCP Connector 复读当前工作树、源码、测试和收尾文档后，确认两项修复，A/B 均为 `APPROVE`，无新增阻断；其指出方法合同开头的历史状态过期，已更新为与最终验收一致。`git diff --check` 通过。复审未重跑 pytest；全量 pytest 未运行。

- Review 基线分支：`main`
- Review 基线 HEAD：`c110ca9a48beebbbd69b8ec1a2a1bf2c353693e2`（`Record final scoped approval for work package H`）。本收尾报告与 P2-0/P1 相关实现、测试和文档由用户授权的本地提交一并固化；提交 SHA 记录于 Git 历史。
- `.agent-memory` 按仓库规则保留在本机且不纳入该提交；没有推送、打 tag、发布或打包。
- 全量 pytest 未运行；聚焦命令与结果见上文及 [Phase 2 验收合同](phase2-acceptance.md)。

## 下一步

本 Goal 已完成。后续是否启动路线图中的其他阶段由用户决定；本 Goal 不自动启动 P2-2B、P2-3、P2-4 或 P2-5。
