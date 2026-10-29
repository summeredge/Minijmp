# DOE Phase 2 验收合同（重建稿）

日期：2026-10-29。原始 `phase2-acceptance.md` 在本轮开始时不存在。本稿依据本轮目标、既有 `acceptance.md` 和 P2-0 路线图摘要重建；每项状态只按本地实际证据更新。

当前检查点（2026-10-29）：单元 A、B 的本地验收均通过。首轮 ChatGPT/Local MCP Connector Review 的 A-01/B-01 已修复并完成定向复测；当前 ChatGPT/Local MCP Connector 复审对两个验收单元分别给出 `APPROVE`。没有 Minitab 22 产品输出，因此不声明版本或输出 parity。

## 单元 A：MIXTURE_OPTIMAL

| ID | 验收内容 | 必需证据 |
|---|---|---|
| P2-ACC-01 | Mixture D-optimal 选点 | Scheffé 指定项矩阵；小候选集独立穷举；秩亏/并列/重复候选/候选不足；约束合法性；精确与启发式状态及预算如实报告 |
| P2-ACC-02 | Mixture Distance-based 选点 | 三组分 Simplex 手算距离次序；初始点、最远点和确定性并列；组件坐标、伪组分及过程/总量坐标合同；重复设计点不选；非法混合单位配置拒绝 |
| P2-ACC-03 | Mixture D-optimal/Distance-based 增补 | 固定全部父运行；增补前后秩/点数/logdet/算法；新增 run ID 唯一；响应保留、新响应为空；父点不删除/替换，重复语义有据 |
| P2-ACC-04 | Mixture 工程、GUI 与回归 | 创建/增补/评价/预览/取消；无副作用拒绝；保存关闭重开复制重分析；来源或模型变化失效；坏元数据不替换 live workbook；F 分析/预测/优化/图形保持行为；真实 Tk 生命周期通过 |

### 单元 A 本地验收结果（2026-10-29）

`P2-ACC-01/02`：独立 Fraction 参考核验器 13 项通过；选点、模型秩、约束、候选重复、启发式状态及评价/增补核心组 98 passed。Distance 使用实际组分比例，过程/总量变量仅在显式选择时按声明范围映射至 [0,1]。

`P2-ACC-03/04`：真实 Tk Mixture 工作流 8 passed，覆盖选点/取消、旧预览失效、最小窗口按钮可见、Distance 父锚点增补、评价、响应保留/留空、工程重开、复制和重分析；Mixture Schema 1 持久化 4 passed；DOE schema v2/v3 恢复 33 passed，坏 DOE 元数据载入隔离 6 passed、4 deselected；普通最优设计 GUI 6 passed。帮助中心 13 passed，菜单翻译 66 passed。各测试组彼此有重叠，不相加为独立总数。

独立静态 Review 曾发现整数响应转 Float64 的精度损失及已映射空批次值被改写为 `BASE`；现已移除响应强制浮点转换，缺失父批次值原样保留，并增加精确大整数与空批次反例回归。修复后核心组为 98 passed。

首轮独立 Review 的 A-01 发现重复设计运行未参与最小平方距离计算。现对所有运行计算该指标，并同时报告唯一设计点数及重复点数。`tests/test_doe_mixture_optimal.py tests/test_doe_optimal_evaluation.py -q` 22 passed；真实 Tk `tests/test_doe_mixture_gui.py -q` 8 passed（6 条 `tight_layout` 警告）。

矩阵 `GEN-004/ACC-056` 与 `GEN-006/ACC-058` 保持 `partial`：本地 Mixture 选点与固定父设计增补合同已实现；Mixture replace/improve 工作流和版本明确的 Minitab 产品输出对照仍未实现。官方方法依据见[Mixture 选点与增补](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/factorial/select-optimal-design/perform-the-analysis/select-optimal-runs-augment-or-improve-a-mixtures-design/)与[最优设计方法](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/factorial/select-optimal-design/methods-and-formulas/methods-and-formulas/)；来源不标明 Minitab 22。

## 单元 B：DOE_RSM_INTERVAL_DIAGNOSTICS

| ID | 验收内容 | 必需证据 |
|---|---|---|
| P2-ACC-05 | 连续 RSM SE Fit、均值 CI、单次 PI | 独立二次模型手算 `X, β, MSE, df, h0, SE Fit, CI, PI`；90/95/99 等置信水平、双侧/单侧、多响应；CI 不宽于同条件 PI；秩亏、饱和、非正误差 df、无效点、过期模型及区组不支持边界 |
| P2-ACC-06 | RSM 杠杆与残差 | 按实际 CCD/BBD/custom 模型矩阵和 run ID 对齐；小矩阵独立计算 leverage、standardized/studentized/deleted residual；`h≈1`、零 MSE、饱和和近奇异时不产出 Inf/NaN 或无定义值 |
| P2-ACC-07 | Cook's Distance、DFITS 与生命周期 | 独立公式逐行对照 Cook's D、DFITS；诊断仅提示、不自动删点；图表与表格使用实际运行顺序；修改响应、切换来源、保存/重开/复制后旧诊断失效或正确恢复；真实 Tk 结果窗口与取消通过 |

### 单元 B 本地验收结果（2026-10-29）

`P2-ACC-05/06/07`：独立参考核验器验证 9 种置信度/方向组合及 9 行逐点诊断；参考 `reference.json` SHA-256 为 `d87d1720c24000fec7ebbf42cb2e1f58f8c52d2be8fadfcee7600f3bc4121a72`。连续 RSM 旧分析回归 27 passed；区间与诊断核心测试 37 passed；区间 Tk 窗口 7 passed；诊断 Tk 窗口 12 passed（3 条 Matplotlib `tight_layout` 警告）；保存、重开、复制后的 E/F/G 工程集成 1 passed（3 条既有 `tight_layout` 警告）。工程集成确认复制后的自定义 RSM 诊断表按运行 ID 排列。帮助中心 13 passed，菜单翻译 66 passed。

独立代码审查发现原零方差阈值受响应整体基线影响：将响应整体加 `1e8` 会错误禁用有效区间及 Cook's D。现改为结合响应变化平方和与浮点舍入尺度判定，并新增平移不变性回归；修复后区间/诊断组 37 passed、GUI 与工程集成组复跑通过。

独立复核修复后数值边界无剩余发现：响应平移后 9/9 行 Cook's D 可用，精确拟合和零响应的方差诊断仍标为不可用。首轮独立 Review 的 B-01 发现重算失败或来源切换时旧 CI/PI 结果仍可见；现将清除旧结果提前到预测重算开始，并在真实 Tk 回归中覆盖响应无效与工作表切换。`tests/test_doe_predict_gui.py -q` 7 passed；Connector 复审确认 A、B 两个单元均为 `APPROVE`。

区间从当前拟合模型实际矩阵及残差 `MSE=SSE/df_error` 计算，即使无纯误差但仍有有效残差自由度也可用；秩亏由分析器拒绝，非正残差自由度、零/不可辨方差及含多个区组的区间明确不可用。杠杆、内部标准化残差、删除残差、外部学生化残差、Cook's D 与 DFITS 按当前 RSM 拟合矩阵及实际运行顺序发布；高杠杆、零方差及删除自由度不足时不输出无定义量。响应改变后重新分析可刷新结果，已保存工程不存储旧分析缓存，重开/复制后按当前工作表重新计算。区间不用于区组 RSM、Logistic、Mixture、Split-Plot；诊断不自动删点。完整全量 pytest 未运行。

功能矩阵 `RSM-009` 更新为 `partial`：CCD/BBD/custom 连续 RSM 的 Predict 窗口支持 SE Fit、均值 CI 与单次 PI；多区组、Logistic、Mixture、Split-Plot 区间及优化器候选区间不在此实现范围。官方方法页不标软件版本，且没有 Minitab 22 产品输出对照。

## 跨项判定

- 独立参考生成器与 verifier 不导入 MiniJMP 生产选点/区间/诊断代码；冻结 reference 不为迁就实现而改数值。
- 结果分类：`MATH_PASS`、`LOCAL_PASS`、`OFFICIAL_CONFIRMED`。没有 Minitab 22 产品输出时不声明 `VERSION22_PARITY`。
- Python 测试使用项目 `.venv\Scripts\python.exe`；Tk 生命周期按单进程串行运行。逐项记录 passed/failed/skipped 和限制，不汇总重叠测试组为唯一通过数。
- 需覆盖 F 混料、E 最优/增补、CCD/BBD/custom RSM、H 二元非回归、DOE v1–v5 与 Mixture Schema 1 持久化，以及实际影响到的菜单/帮助/G12。
- 两单元分别报告 `APPROVE / ITERATE / HUMAN_REQUIRED`；一个单元的通过不抵消另一个失败。本轮独立 Review 对 A、B 均为 `APPROVE`；不因本次完成而自动启动下一阶段。
