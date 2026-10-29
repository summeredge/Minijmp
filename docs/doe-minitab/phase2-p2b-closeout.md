# DOE Phase 2 P2-2B 收尾记录

日期：2026-10-29
状态：`READY_FOR_INDEPENDENT_REVIEW`；本地六项验收均通过，两个 Local MCP Connector 独立 Review 尚待执行。用户于 2026-10-29 明确授权在 Review verdict 产生前提交并推送；本地验收不代表独立 Review 通过。

## 验收单元

| 单元 | 本地结论 | Review 状态 |
|---|---|---|
| `BINARY_PROBABILITY_INTERVAL` | `P2B-ACC-01/02` `LOCAL_PASS` | `READY_FOR_REVIEW` |
| `BINARY_RESPONSE_OPTIMIZER` | `P2B-ACC-03/04/05/06` `LOCAL_PASS` | `READY_FOR_REVIEW` |

## 统计合同与独立参考

- 复用 grouped-binomial Logit 拟合协方差及同一 `TermModel` 行。概率 SE 使用 Delta method；CI 在 Logit 尺度计算 Wald 正态限后以稳定 `expit` 反变换，不显示连续响应 PI。
- `optimize_binary_rsm()` 支持 Maximize/Minimize/Target 与概率/单响应 desirability，weight 为 0.1–10。连续因子按实际单位收紧/固定，类别水平完整枚举；目标概率达到容差为 `1e-8`。连续搜索使用确定性多起点有界 L-BFGS-B，每起点最多 100 次评价；预算耗尽仍保留当前最佳候选。只有固定连续因子且类别组合穷尽时才证明有限候选全局最优。
- 独立 fixture `tests/fixtures/doe_phase2_binary_reference/` 的 SHA-256 为 `9f421b5f7ba175af1a54c2cf98ce5714707b72220da21c9a84e0ba6893e41fda`；独立 verifier 931 项通过，覆盖 Newton grouped-binomial GLM、Wald 数学和解析优化器参考。GLM 数据为 303 行。
- 未取得 Minitab 22 的实际数值结果；不声明版本数值一致、连续区域全局最优或新批次事件计数预测区间。

## 工程与回归证据

- 二元概率与分析、二元 optimizer、H 参考、连续点预测/RSM、普通响应 optimizer 和 Mixture optimizer 合并定向回归：**206 passed，9 warnings**；9 条为既有 SciPy SLSQP 边界裁剪警告。
- 二元分析与概率区间单独组合：**70 passed**；二元 optimizer 独立解析/边界/取消测试：**26 passed**。
- 真实 Tk 单进程用例：概率窗口 **5 × 1 passed**；二元优化窗口 **10 × 1 passed**，包括约束预览、模型行回算、数字类别保型、取消/子父窗关闭、计算中数据/元数据/响应列/工作表失效、源表删除、`.dexpl` 重开复制后重新拟合与优化。H Factorial、DSD/RSM 概率图及响应失效回归 **3 × 1 passed**。
- 普通连续 optimizer GUI 相关用例 **5 passed**；Mixture GUI 生命周期 **1 passed，4 条 Matplotlib `tight_layout` 警告**；连续预测 CI/PI GUI **1 passed**。
- 工程/兼容回归：DOE 持久化 **10 passed**；Schema v2/e/factorial **29 passed**；Schema v3 **19 passed**；文件 I/O **45 passed**；Taguchi 持久化 **20 passed**。
- Help **13 passed**；菜单翻译清单 **1 passed**、Help 与菜单路径 **14 passed**；G12 StatTable 清单 **15 passed**。G12 首轮发现并登记了二元概率和优化窗口两处表格生产位置，复测通过。
- `py_compile` 对二元分析、二元对话框、优化器、相关测试和 fixture 脚本通过；最终 `git diff --check` 通过。没有运行全量 pytest。

## P2B-REV-01 独立 Review 定向修复（2026-10-29）

- Review 发现：`BinaryAnalysisDialog._inputs_changed()` 清除模型快照并关闭子窗口时只禁用了概率按钮，响应优化按钮仍显示可用。现于同一流程对非空 `optimizer_button` 同步设为 disabled；只有分析成功路径会重新启用两个按钮。未改 `optimizer_dialog.close()`、取消事件或 executor 清理逻辑，也未改 Logistic、优化目标或 Schema。
- 真实 Tk 回归扩展 `tests/test_doe_h_lifecycle.py`：事件列/试验列切换后禁用并重新分析恢复；来源响应数据、DOE 元数据、工作表变化经 `_check_source()` 后禁用，再恢复合法来源并重分析；运行中的优化器在来源变化时仍关闭并取消；DSD/Factorial 无优化按钮的入口正常。
- 使用项目 `.venv` 串行、每个节点独立进程执行 24 个直接相关 H/P2B Tk 节点，**24 passed**。其中新增按钮列选择 2 个节点、数据/元数据/工作表失效与恢复 3 个参数节点均通过；优化预览、取消、来源失效、父子窗口关闭、DSD/Factorial 及概率窗口回归也通过。
- `& '.venv\Scripts\python.exe' -m pytest tests/test_doe_binary_analysis.py tests/test_doe_binary_probability.py tests/test_doe_binary_optimize.py tests/test_doe_h_reference.py -q --tb=short`：**97 passed**。`& '.venv\Scripts\python.exe' -m py_compile code/doe_binary_dialog.py tests/test_doe_h_lifecycle.py` 通过；`git diff --check` exit 0（Git 仅提示若干已有文件的 CRLF→LF 转换）。
- P2B-ACC-01–06 本地结论保持 `LOCAL_PASS`；两个验收单元仍为 `READY_FOR_INDEPENDENT_REVIEW`，未改成 APPROVE。此前身份超时的 LRM Review Goal 未自动重提；用户随后明确要求提交并推送，独立 Review 仍待完成。

## P2B-REV-02 Desirability 零梯度平台修复（2026-10-29）

- 根因：正式 desirability 在不可接受区域为 0，概率尺度梯度也是 0；仅以该梯度启动 L-BFGS-B 时，零平台上的默认起点会立即被判为收敛。
- 独立反例位于 `tests/test_doe_binary_optimize.py`：Case A `eta=20x`、目标概率 0.95，旧实现停在 `A=0`（`p=0.5`），正确根为 `A=logit(0.95)/20=0.147221948958...`；Case B `eta=5-100(x-0.27)^2` 的默认起点 desirability 均为 0，而内部存在最大化有效区；Case C `eta=-5+100(x-0.27)^2` 同样验证最小化方向。三项新增用例在旧实现下均失败，修复后通过。
- 修复只改变搜索过程：Desirability=0 的起点先用单调 Logit 辅助目标离开平台（Maximize 优化 `-eta`，Minimize 优化 `eta`，Target 优化 `sqrt((eta-logit(T))^2+1)-1`）；辅助目标不参与结果排名，候选与最终 desirability 始终由原分段公式计算。若候选进入 0 到 1 之间的正 desirability 区域，再从该点运行原正式评分阶段；两阶段共享每起点 100 次函数评价上限。取消仍在每次评价前检查，分类水平仍完整枚举，连续域全局最优仍不作证明。
- `solver_converged` 按该起点实际执行的全部阶段收敛状态汇总；`target_reached` 仍按最终候选概率判定。预算耗尽时保留已评估的正式评分最佳候选，并在 `termination_counts` 与 `termination_reason` 中写明对应阶段和预算原因。
- 使用项目 `.venv`：`tests/test_doe_binary_optimize.py` **33 passed**；二元概率/分析/H 参考 **71 passed**；连续 RSM 与 Mixture optimizer **57 passed，9 条既有 SciPy SLSQP 边界裁剪警告**。真实 Tk optimizer 预览/结果、取消/关闭及普通 BBD optimizer 三个节点按单节点独立进程执行，**3 × 1 passed**。`py_compile` 与最终 `git diff --check` 通过；未运行全量 pytest。
- Schema v5 不变；未改 GUI 生命周期、普通连续优化器或 Mixture 生产代码。P2B-ACC-01–06 仍 `LOCAL_PASS`，两个验收单元保持 `READY_FOR_INDEPENDENT_REVIEW`，没有独立 APPROVE。本次不提交/推送。

## 功能矩阵、Schema 与 Git

- `feature-matrix.csv` 对照 HEAD 前后均为 80 行，feature ID、顺序及状态计数不变：58 `implemented`、19 `partial`、2 `unknown`、1 `excluded`。
- `RSM-016` 仍为 `implemented`、验收号仍为 `MTB-DOE-ACC-031`；H4 历史范围与 P2-2B 新范围分别记录。
- DOE Schema 保持 v5；无新生产模块或依赖。优化不改写工作表响应。
- 开发基线分支为 `main`，起始 HEAD `5c37c286ee86fff4d5b82ed3ddad0d06880ae347`；本次按用户明确指示提交并推送。没有打 tag、release 或 EXE 打包。

## Review 与下一步

概率区间与二元响应优化器的实现、独立数学参考、本地 Tk/工程/跨模块证据已整理。提交前 `workspace_list` 成功解析 `Minijmp` workspace `1e490ba5641d`，Connector 只读状态确认 `main` dirty 且 HEAD 与当时本地一致。只读 Review Goal `0ac8812c-0ca1-4c3e-be01-3812efcb8021` 因 `pending_identity_expired` 终止，证据轨迹为空，没有 execution ID 或 Review verdict。Computer Use 也因无法可靠识别当前 Windows 浏览器 URL 而停止。未自动重提该 Goal；用户后来明确授权提交推送。A/B 仍待独立 Review，不能将本地 readiness 记作独立 `APPROVE`。全量 pytest 未运行。
