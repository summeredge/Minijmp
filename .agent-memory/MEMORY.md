# MiniJMP 工作记忆

## DOE Phase 2 P2-6B 验收（2026-10-30）

- TAG-005 L36、TAG-009 分类交互/预测/确认表、TAG-008 二水平控制×噪声响应模型与稳健搜索、FAC-012 多因子 Foldover 已完成限定范围验收；DOE Schema v5 不变。
- MIX-005 按现有 Mixture v2 范围为 `IMPLEMENTED_SCOPED`；GEN-006 已补为 `IMPLEMENTED_SCOPED`：自定义因子/RSM 固定运行数 D-optimal Improve，保留 Mixture Improve 且未重写全 Fedorov 算法。
- P2-6B 原 DOE 合并回归 183 passed；GEN-006 定向非 GUI 回归 88 passed，新 Improve GUI 与 Select/Augment/Mixture GUI 节点各 1 passed；py_compile 与 diff check 通过。改善采用有界局部交换，不保证全局最优；未验证 Minitab 22 parity。
- 验收与状态清单：`Out/p2_6_doe_function_completion/p2-6b-acceptance.md`、`p2-6b-feature-status.csv`；未提交/推送/发布。

## DOE Phase 2 P2-6 核心功能（2026-10-30）

- SCR-003、SCR-007、RSM-009、FAC-008、FAC-015、SCR-002、FAC-010 已在本地实现；DOE Schema v5 不变，未提交/推送/发布。详细范围和证据见 `Out/p2_6_doe_function_completion/report.md`。
- `.venv` 非 GUI `test_doe_*.py`：1389 passed、12 warnings；后续 SCR-003 定向 8 passed、DSD Stepwise 18 passed。Screening GUI 320 个收集节点去重后均由分组/独立进程通过；历史整文件 Tk 中断的两项节点名未留存。
- 独立 OLS 已覆盖 Backward 秩亏初始模型与可估计项删除，以及 BIC 恰留 1 个残差自由度；不需改生产实现。多分类 DSD 仍限 c=2–4、连续因子 4–12；裂区完整平衡且不做 REML；混料最优点区间不校正选点偏差。未验证 Minitab 22 parity。

## DOE Phase 2 P2-5 自动化验收（2026-10-30）

- 状态：本地自动化综合验收完成，不代表 Minitab 22 全功能 parity；未改统计源码、测试、正式 P2-5 文档、feature-matrix.csv 或原始产品证据；未生成新 Minitab 输出、未提交/推送。
- 测试：1201 DOE 测试 + 141 Tk DOE 工作流 + 66 菜单测试 = 1408 passed、69 warnings、0 failed；筛选 GUI 全套未运行，PB/DSD 两个隔离 node 通过。
- 独立误差：statsmodels 2² OLS 最大绝对误差 1.42e-14；五类静态 S/N 误差 0；DSD 五条逐步路径/秩/df 精确一致；Mixture 72×15 系数误差 2.13e-14、SSE 8.06e-12；连续全局最优未验证。
- 覆盖：80 项仍为 58 implemented、19 partial、2 unknown、1 excluded；已有 Minitab 输出覆盖 SCR-001/SCR-003/FAC-012/RSM-002，其余 76 项无对应产品输出。
- 观察：GEN-004 feature-matrix 行字段错位；TAG-005 范围描述与混合阵列案例不一致；BBD 仅运行序差异；测试环境有 CJK glyph 警告。验收材料见 Out/p5_automated_validation/。

## DOE Phase 2 P2-4A/P2-4BC 最终本地集成（2026-10-30）

- 状态：本地提交 `f77c746`（父提交 `0dcc4ac`），未推送、未打标签，P2-5 当时未启动；当前状态见前节。`DSD_STEPWISE_SELECTION=APPROVE_SCOPED`；PB Foldover、Taguchi、Mixture 保持 `READY_FOR_INDEPENDENT_REVIEW`；本地联合测试不等同独立批准。DOE Schema v5 未变。
- P4BC 提交 `0dcc4ac` 已确认在 main 历史，包含 Taguchi 与 Mixture Schema 2/Improve。Mixture Schema 1 普通/append-only 与 Schema 2 Improve 恢复路径均经同快照测试。
- DSD：`code/doe_stepwise.py::select_dsd_stepwise`，先移除后进入、强层级、8 类停止原因、候选项上限 64、参数变化即失效。秩按列修正 Gram–Schmidt 判定（`_fit` 奇异值截断在饱和边界会误判），参考端同步。
- PB：`code/doe_pb_foldover.py` 支持 12–48 全部运行数、全部/单因子一次折叠；`screening_matrix.matrix_sha256` 仍表示 BASE 身份。REV-01 逐对校验折叠语义；REV-02 令 `restore_design_result()`/`validate_pb()` 与工作表物理行序解耦，BASE/FOLD1 运行序集合分段验证，FOLD1 逐 ID 按 seed 重建，标准序映射与因子关系继续验证。Schema v5 没有 BASE 父运行序快照，无法独立认证摘要重绑后的逐 ID 历史顺序；只验证其为 `1..N` 排列，不以显示行序作为证据。正规 Fractional Foldover 路径不变；PB 混杂按实际矩阵投影，不使用 PB defining relation。
- 参考 SHA-256：DSD `ad4713ff3861f5aaffeeba9b17c1ba3979c9b4bb9b0305b1201fa7d6f094164a`；PB `9ee6b929929a70994c89e8e3d998bcb6def610da9524116dad9c1d4c078fe0ab`。
- 最终同快照验证：P2-4A 96、P2-4BC 113、共享 Schema/持久化及 DOE v1–v5 118、Split-Plot/Binary 146 passed；真实 Tk 单文件串行 12/2/14/10/10 passed，Help/Menu/G12 13/66/15 passed。三套独立 DSD/PB/P4BC verifier 通过；fixture SHA 未变。`.venv` py_compile 与 `git diff --check` 通过，只有 feature-matrix/search-index 的既有 CRLF 提示。
- 集成修复：显式 `doe: null` 不再被当成缺少 DOE 元数据；损坏工程安全拒绝且不替换活工作簿。功能矩阵保留 80 个 Feature ID（58 implemented、19 partial、2 unknown、1 excluded）。
- 未运行全量 pytest 或整套 `test_doe_screening_gui.py`；其历史解释器级中断仍属稳定性风险。未验证 Minitab 22 数值一致性，连续 Mixture 可行域全局最优未证明。交接见 `docs/doe-minitab/phase2-p4a-closeout.md`、`phase2-p4bc-closeout.md`、`phase2-roadmap.md` 及 `logs/2026-10-30.md`。
- 证据：`docs/doe-minitab/phase2-p4a-{method-contract,acceptance,closeout}.md`；功能矩阵仍 80 项（58 implemented、19 partial、2 unknown、1 excluded）。

## DOE Phase 2 P2-3（2026-10-29，已完成，限定范围 APPROVE）

- 状态 APPROVE_SCOPED：Local MCP Connector 对设计/随机化及分层推断两个单元均限定范围批准；P3-ACC-01～06 本地通过，P3-REV-01 修复通过。最终本地 commit a5496adc6d3e7b09657290922074e5ad8024437c；Schema v5 不变，未 push，P2-4/P2-5 未启动。
- 范围为完整平衡 2–6 个连续两水平因子、1–3 个 hard、至少 1 个 easy、完整区组、最多 10,000 runs；v1 seed 运行身份冻结，新多因子用 construction v2。
- 独立参考 SHA-256 8c4ccc639a44954582290a3e49cb85695b25a46f29a5fd0c575b8efb74e3f32f，fixture 与最终分析静态复核均 CLEAR。平衡正交矩阵以稳定直接投影求系数；六因子 `1e15*A` 保留误差 SS 128/1920，另覆盖零方差、单位缩放及 `+1e14` 偏移。
- `.venv` Python 3.11.9：核心/跨模块 222 passed；Split-Plot Tk 10 passed/2 tight_layout warnings；共享最优 GUI 6 passed；Help/Menu/G12 94 passed。全量 pytest 未运行。
- P3-REV-01 追加顺序修复在最终快照验证：DOE/Schema/持久化/通用增补 164 passed；真实 Tk Split-Plot 与修改设计 GUI 16 passed、2 条 tight_layout warnings；py_compile 与 diff check 通过。旧 v1/v2 前缀按 seed 重建，使用 v5 现有 lineage；每个设计仅允许一次追加批次。
- 矩阵保持 80 项（58 implemented、19 partial、2 unknown、1 excluded），Split-Plot 相关行仍 partial。Minitab 22 parity 未验证；全量 pytest 未运行。工程 commit 后工作树只留 MEMORY.md 和当日日志本地修改。
- 交接与方法证据：docs/doe-minitab/phase2-p3-closeout.md、phase2-p3-acceptance.md；过程见 logs/2026-10-29.md。

## DOE Phase 2 P2-2B 历史（2026-10-29）

- P2B-ACC-01–06 本地通过，DOE Schema v5；网页身份未就绪时正式 Review 未执行。用户随后明确授权提交推送，commit b6cd31fbc78083317d2618a34fefbbd6e79b30f6 已推送，不代表独立 APPROVE。
- 概率/优化实现、测试和范围详情见 docs/doe-minitab/phase2-p2b-acceptance.md 与当日日志。
## DOE Phase 2 P1 核心对标（2026-10-29，限定范围 Review APPROVE）

- Mixture 最优设计与连续 RSM 区间/诊断限定范围本地通过，Local Connector 分别给出 APPROVE；DOE Schema v5 不变。
- Mixture、RSM 的独立参考、修复记录及精确验证见 docs/doe-minitab/phase2-p1-closeout.md 和当日日志；全量 pytest 未运行。
- Minitab 页面未标产品版本；不宣称 Minitab 22 parity。
## 工作包 H 最终收尾（2026-10-29）

- WORK_PACKAGE_H_APPROVED_SCOPED；ACC-004/019/020/031/059/060 限定范围验收，DOE Schema v5；matrix 80 项为 58/18/3/1。
- 功效仅覆盖合同中的两水平主效应 1 df F；完整证据与限制见 docs/doe-minitab/work-package-h-closeout.md。
## 工作包 H H0–H6 本地集成（历史状态，2026-10-29）

- 本地 H0–H6 实现及 Schema v5 边界见 docs/doe-minitab/work-package-h-closeout.md；后来完成限定范围验收，结论见上节。
- H 参考和历史 Review 身份问题记录于 .agent-memory/logs/2026-10-29.md。
## Taguchi 零方差 S/N Review 修复（2026-10-29）

- 状态 `READY_FOR_INDEPENDENT_REVIEW`；在已有 E/F/G 未提交工作区上定向修复 `noise_robustness()`，仅移除无条件 SD=0 拒绝，S/N 的公式与数据域仍由 `signal_to_noise()` 校验；Nominal 零方差仍拒绝，噪声因子和观测数校验未改。
- 独立反例 `[2, 2]`：Smaller = −10 log10(4) = −6.020599913279624 dB，Larger = −10 log10(1/4) = +6.020599913279624 dB，SD = 0；旧实现两种均错误拒绝。噪声及静态 S/N 两测试文件 50 passed，真实 Tk 噪声窗口 3 passed；未重复全量测试。验收矩阵、更新日志已按新合同修正。
- 保留先前未提交改动；未提交、推送或启动 H。待独立差异 Review，过程见 `.agent-memory/logs/2026-10-29.md`。


## E+F+G 合并后 Full Review ITERATE（历史，2026-10-29）

- 当时 5 项 Review 发现已修复；Taguchi L8 投影限制及 E/F/G 集成边界见 docs/doe-minitab/efg-integration-review.md 和 logs/2026-10-29.md。
- 该阶段独立 Review 未启动；后续工作包状态见各自 closeout，不把本地测试表述为 APPROVE。
## 工作包 E E0–E6（2026-10-28，本地收尾）

- 自定义 DOE、最优设计、增补与 Schema v5 限定范围实现；旧 Schema 迁移及工程隔离证据见 docs/doe-minitab/work-package-e-closeout.md。
- 后续 P2-3 复用 doe_modify.py 与 doe_diagnostics.py；历史 E 细节见 logs/2026-10-28.md。
## 工作包 F 混料设计（2026-10-28，隔离 worktree）

- Mixture 设计、建模、约束、图形和工程范围见 docs/doe-minitab/work-package-f-closeout.md；partial 状态和数值证据见该报告与 logs/2026-10-28.md。
## 工作包 D D0–D5（2026-10-28，本地收尾）

- 一般全因子、区组、正规分数、Foldover 与当时 2×2 Split-Plot 基线证据见 docs/doe-minitab/work-package-d-closeout.md。
- 当时裂区仅两因子、A 用整区误差、B/AB 用子区误差；现由上方 P2-3 扩展。旧 Schema v4/Review 历史仅供追溯。
- D/PB/Tk 分组验证和未跑全量 pytest 的记录见 logs/2026-10-28.md。
## 工作包 B/C 收尾（2026-10-28，细节见当日日志归档）

- B/C 限定范围、Minitab 22 导出差异、PB/DSD 参考与 Tk 中断边界见 logs/2026-10-28.md；本地测试不等同产品 parity 或独立 APPROVE。
## 当前状态（2026-10-27）

DOE-3 已实现 CCD 和二次响应面：支持 2–5 因子 CCF/旋转 CCC、越界预览确认、编码与设定矩阵校验、纯误差/失拟/曲率和图形，工程可保存、重开、复制。DOE-1 含中心点时禁用模型 t/F 推断的前置修复已完成。CCD 允许十进制/指数文本按最近 binary64 保存；纯整数文本保持精确整数，无法无损转 binary64 的端点拒绝；中心和 CCC 轴点采用有界舍入，轴点必须仍在 low/high 外且反算编码误差不超过 1e-8。DOE schema v1 与 DOE-0/1/2 语义未变。DOE-4 已实现：完整 CCD 上单响应最大化/最小化/逼近目标，多响应期望函数权重优化；默认编码 bounds 为 [-1,1]，可收紧或固定。GUI 每次从当前表快照重拟合，候选含编码/实际水平、预测、期望、可行与 solver 状态；确定性多起点 L-BFGS-B 不保证全局最优，零期望/数值下溢/评价上限会明示。优化不写回响应、设定或 `.dexpl` schema v1。当前验收按范围合计 456 passed、14 warnings、0 failed、0 skipped；全量 pytest 未运行，DOE-3 之前的全量历史曾两次于 Tk `Menu.add` 原生 `0x80000003` 中断且无 summary。见 `docs/doe-development.md`、`docs/doe3-closeout-report.md` 与 `logs/2026-10-27.md`。

DOE-4 最小修复（2026-10-27）：目标型多响应在目标高侧改用 `power_high`；GUI 按各响应分别计算目标差值，保留单响应显示语义。独立解析最优点、左右侧期望/有限差分和真实 Tk 多响应显示均覆盖。指定四文件回归 64 passed、2 个既有 tight-layout warnings；py_compile 与 diff check 通过。详见 `logs/2026-10-27.md`。

DOE-2 正规部分因子支持 3–6 连续因子、正生成元、独立重复、定义字及别名组、DOE 元数据保存恢复；拒绝中心点、负生成元和派生因子循环。模型按别名组解释，只有独立重复且纯误差可辨时才在模型充分等假设下提供 OLS 推断。历史关联测试中的两项 DOE-1 失败已在 DOE-3 修复；历史证据见 `logs/2026-10-27.md`。

beta.4 已固化：beta.3 基线 `d21a924abf6f437f82e2736ac09c5a38dc636d5f`；pandas 迁移提交 `d321c59806230572bc6d7ba2c752ad8c80a62891`；版本提交 `e770bb9b22bca9aad2de3e167f77407a5608dff5`；本地 annotated 标签 `v0.1.0-beta.4` 指向实际构建基线 `0d9f5730029905745856d6bda1f4e7a24fc97b50`，标签未推送。产品/包/EXE 版本分别为 `v0.1.0-beta.4`、`V0.1-beta4`、`0.1.0.4`。迁移全量历史结果 3810 passed、0 failed、0 skipped；发布工具 25 passed、启动测试 17 passed。干净基线 Windows EXE/ZIP 构建、哈希和按进程 ID 的运行目录与解压版窗口冒烟通过。原冒烟脚本此前曾误识别 Edge，办公终端与实际 PI Server 未验收。详见当日日志。

beta.3 已冻结在提交 `d21a924abf6f437f82e2736ac09c5a38dc636d5f`；迁移开始时 `main`、`origin/main` 相同且工作区干净，未创建标签。pandas 3.0.6 迁移已完成并由提交 `d321c59806230572bc6d7ba2c752ad8c80a62891` 固化，正式依赖 `requirements.txt` 与 Windows Python 3.11 锁文件一致。数据安全写入、CSV/Excel 精度、旧 API、类别/日期时间绘图、分组语义及绘图 DPI 全局状态已修复；统计计算定义未改。

验证：`.venv` Python 3.11.9、pandas 3.0.6 及锁依赖检查通过，`tools/release_env.py` 五项 PASS；第一层 473、第二层 70、第三层 202、绘图 DPI/图片导出专项 180 项通过。收尾后全量 `pytest -q --tb=short` 为 **3,810 passed、0 failed、0 skipped、120 warnings**（978.26 秒）。历史 AST 守卫已修：`CorrelationDialog.apply` 的 `pearson=self.cor_p.get()` 按严格形态断言归一化后仍完整比较快照；同一函数内 `CpkSubDialog.apply` 的 REVIEW-018/019 差异复用整函数 SHA256 守卫还原。快照未改、测试未跳过；新增 Pearson 开/关运行时测试。详见 `docs/release/pandas3-migration-report.md` 与 `logs/2026-10-27.md`。限制：`.xls` 超精度原始 token 不可恢复；未接实际 PI Server；该迁移阶段未做 EXE/ZIP 构建与办公终端安全策略验收，后续构建状态见上文。

通用绘图器事件绑定最终验收已完成：`PlotViewer.setupGUI()` 创建并保留唯一 `self._drag_handler`，移除 `_flow_panelhead()` 中不可达绑定，`close()` 释放引用；专用 `code/plots.py` 未在本任务修改。普通查看器真实 Tk 覆盖四类事件各一次、GC 后存活、标注选择/拖动/释放/Delete、参数显隐/重绘/缩放/调整大小后不重复监听、关闭后监听消失及重开。指定三组测试分别 16/54/39 项通过（`PythonEnvs/minijmp`），普通查看器额外真实 Tk 交互及 900×720 窗口截图复核通过；画布 576×663。截图：`docs/gui-evidence/plotter/event-fix-900x720-{visible,hidden}.png`，导出图 `event-fix-saved-line.png`。本次未重做多 DPI/全页面布局矩阵，未跑全量测试。详见当日日志。

通用绘图器界面已重排为“顶部动作栏 + 右侧参数坞 + 画布主区”：参数页改为可滚动、按分组自适应列数的紧凑行式布局，绘图数据摘要移到画布下方，图形类型只在数据配置页出现一次；时间序列与过程能力的导航工具条改挂画布顶部。900×720 下画布高度 204→664 像素，640×480 至 1600×1000、125%/200% 缩放均逐页测量无裁切。见 2026-10-26 日志。

pandas 3 兼容性定向修复已完成：`core_orig.py` 的 `getRowsFromMask()`（按标签对齐布尔掩码，整数按行位置）与 `transform()`（按列重建 + `isetitem` 写回、`df.map` 替换 `applymap`），以及 `handlers.py` 散点拾取的 `df.iloc[ind]`；`plotting.py` 两处 `drop(columns=...)` 已是新写法，未改动。见 2026-10-26 日志。

通用绘图器新增“数据配置”页：X/Y/分组列显式配置、数据范围选择，折线/散点/条形/面积图按角色取数，不再依赖工作表列顺序；选区绘图、PLOT 高级选项与专用 PlotViewer 调用保持原行为。角色绘图的空分组跳过但按 Y 整体校验、序列按源列位置区分（`1` 与 `"1"` 不合并）、切到其他类型或三维必须退出角色模式，见 2026-10-26 日志。

工作表列公式功能已实现并验证：计算器、一次性/关联计算、依赖重算、循环检测、只读编辑规则、工程持久化、右键“公式”子菜单与计算菜单。

工作表、剪贴板、公式与绘图器集成验收（2026-10-26）完成：清除/上移单元格会同步公式状态；Ctrl+C/V 复用 TSV 列表解析和最终范围保护，行头选区不沿用旧列；列粘贴后恢复列头选中标记；验证公式结果经手动/自动重算后绘图、多表公式工程往返、行增删与公式只读保护。5 个相关测试文件 246 项通过，pandas 3.0.6 移位专项另 3 项通过。真实 Tk 窗口由自动化测试驱动，未做人工鼠标逐项验收。详见 2026-10-26 日志。

改善前后过程能力对比已并入原能力分析窗口（默认不勾选“启用阶段对比”）：复用 `analyze_capability` 分阶段估计，输出 6 张对比表、对比图与统一报告；原单阶段分析与 Sixpack 流程不变。

阶段对比已并入 I-MR/Xbar-R/Xbar-S 原窗口（默认关闭，勾选后展开设置），不再有独立菜单；阶段列/时间分界划分、独立控制限与改善前固定基线、改善指标、自相关适用性检查、统一报告与阶段图。普通 I/I-MR/Xbar 图同步启用 Nelson 判异，MR/R/S 只判越限。

## 关键实现

- `code/worksheet_formulas.py`：AST 白名单表达式求值、列引用解析、依赖排序、循环检测、`CalculatorDialog`；列引用按列名稳定关联，C 序号只在展示与新建公式时解析。
- `code/modified_table.py:MTable`：公式状态（`items`/`auto`）随工作表对象存放；`define_formula` 负责一次性/关联写入，`refresh_formulas` 由 `tableChanged` 触发；拒绝手工编辑、粘贴和清除关联结果列。
- `code/pandastable_local/headers.py`：关联结果列头追加 `[公式]`，待更新追加 `*`；重命名同步公式目标与来源。
- `code/worksheets.py`：`saveMeta`/`loadMeta` 保存并恢复公式定义和自动计算开关，旧工程无公式字段时保持原行为。
- 菜单：`code/MiniJMP.py` 顶层“计算”→“计算器”；单元格右键“公式”子菜单（分配/编辑/查看/删除/自动切换/立即计算）。
- `code/improvement_chart.py`：阶段划分、指标、Ljung-Box/Welch/Levene、统一报告、`phase_control_plot`；结果表含 `limits`（常量限标量，变化时标注“逐子组变化”）与 `limit_details`（逐子组 LCL/CL/UCL）；`code/stage_compare.py` 在三种变量图原窗口添加折叠设置并调用 `analyze_improvement`；`code/improvement_dialog.py` 仅展示结果（StatTable、TableBlock、PlotViewer、SheetApp）。
- 异常统计：`alarms` 按 stage 内 point 去重（两面板同一子组只计一次），分母 `points` 为实际绘制点数（I-MR 观测数、Xbar 子组数）；`records` 保留逐规则记录。指标行按图型显示“异常观测比例”或“异常子组比例”。
- Xbar 阶段数据：`_subgroups` 返回阶段内下标，`_chart` 只接收该阶段有效观测；阶段图横轴 I-MR 用观测序号、Xbar 用子组序号，分界取实际点位数。
- `code/control_chart.py`：`_panel_events`/`_mark_events`/`_x_plot_anomalies` 复用 `advanced_spc.nelson_events`；`x_plot` 仅在 `detect_rules=True` 时判定并标记；普通控制图对话框已启用。

## 改善前后能力对比（2026-10-26）

- `code/capability_compare.py`：`analyze_capability_comparison()` 复用 `improvement_chart.split_phases` 划分阶段、每阶段独立调用 `capability.analyze_capability`；输出「数据与规格摘要 / 能力指数对比 / 波动与超规对比 / 稳定性与分布诊断 / 统计检验 / 分析结论」6 张表与 `print_report`；`source_row` 映射回整张工作表，跨阶段重复子组 ID 直接拒绝。
- 指标列名跟随实际阶段标签（`_columns(names)`）；非正态只输出 Pp/Ppl/Ppu/Ppk 与等价 Z；`_row()` 两侧都有限才给差值，否则“不适用”及原因。
- 稳定性复用 `capability_plots._charts` + `control_chart._panel_events`（主图 Nelson、极差类图越限）；自相关/Welch/Levene 复用 `improvement_chart._differences`，阶段名替换为实际标签；有限制时不输出显著改善结论。
- `code/capability_plots.py:plot_capability_comparison()`：两阶段直方图共用横轴与规格、能力指数柱状图、实测/预计 PPM 对数面板；`plot_capability` 与原 Sixpack 未改动。
- `code/capability_dialog.py`：`compare_frame` 构造后仅在勾选时 pack；`comparison()` 拦截变换组合与缺规格；`publish_comparison`/`sync_tabs` 复用表格页、导出、写工作表；`report()`/`plot()` 以 `result_settings[1] == '阶段对比'` 分支。
- 帮助 `help/pages/capability-analysis.html#improvement` 与重建的 `help/assets/search-index.js`；`docs/capability-analysis.md` 增方法合同与证据矩阵；`docs/CHANGELOG_DEV.md` 已记 2026-10-26。
- `tests/fixtures/g12_table_inventory.json` 增 `capability_compare.py` 与说明（不新增 StatTable 生产位置）。

（该项为收尾前基线，已被下方 2026-10-26 最终验收记录取代）验证基线：`.venv` 下 `test_capability_compare.py` 9 项、`test_capability_dialog.py` 13 项（含真实 Tk 阶段对比）、`test_capability.py`+`test_capability_plots.py` 合计 93 项通过；`test_g12_inventory.py`+`test_g12_tables.py` 24 项、`test_help_center.py` 13 项、`test_improvement_chart.py`+`test_review_p2_legacy.py`+`test_review_data_safety.py` 69 项、`test_menu_localization.py`+`test_plot_window_lifecycle.py` 104 项通过。

未实现：两阶段分别 Box-Cox/Johnson 后比较能力指数（窗口明确提示，单阶段变换仍可用）；能力指数差值区间/检验。

## 验证基线

- 通用绘图器布局：`tests/test_g21_plotter.py`+`test_plotter_roles.py` 14 项、`test_dialog_translation.py -k 'plot or legacy'` 10 项、`test_phase1_plots.py` 63 项、`test_g6_chart_presentation.py` 54 项、`test_plot_window_lifecycle.py` 39 项通过（`PythonEnvs/minijmp`）。几何测量脚本 `tools/_plot_shot.py`；证据图在 `docs/gui-evidence/plotter/`。`test_g13_time_series.py::test_real_viewer_replot_navigation_and_save` 因测试用 `MouseEvent(buttons=...)` 与本环境 matplotlib 3.9 签名不符而失败，与本次布局改动无关。

### 2026-10-26 改善前后能力对比收尾修复

- `code/capability_dialog.py`：阶段划分下拉框原用 `list(SPLITS)` 填入内部键 `stage`/`time`，与按“阶段列”判断的启用逻辑不匹配。现改为 `SPLIT_LABELS`（显示“阶段列”/“时间分界点” → 内部 `stage`/`time`），默认“阶段列”，未知选项由 `split_mode()` 明确报错，不再隐式当作时间模式。
- `code/capability_plots.py:_ppm_panel()`：原 `rows` 为 (标签, 键)，解包写成 `for key, _ in rows` 后用中文标签查 `ppm`，导致全部被判定缺失；现严格用 `observed`/`overall`/`within` 取值，统一换算为 PPM，实测行标为“实测超规 PPM”，0 只标注不画条形、缺失显示 NA，`set_yticks` 也改用真实行标签。
- `code/capability_compare.py:_special_causes()`：原对非正态 I 图也用 `(UCL-CL)/3` 作公共尺度跑全部 Nelson 规则。现正态主图仍跑 Nelson，非正态主图只判拟合分位限越界，并在诊断表/对比图标注“未执行 Nelson 连续模式”。

验证（最终验收，`.venv` Python 3.11.9）：`test_capability_compare.py` 收集 14 项、14 项通过；`test_capability_dialog.py` 14 项通过；`test_capability.py`+`test_capability_plots.py` 71 项通过。合计 99 项。

重复测试名已修复：原第 279/304 行为同名 `test_nonnormal_asymmetric_limits_flag_both_sides`，前者从未被收集；现分别为 `test_nonnormal_in_limit_sequence_does_not_trigger_nelson`（限内连续点不触发 Nelson，旧做法命中 Nelson 2/3/7、新做法 0 异常，断言改为命中规则集合而非固定 `== 9` 条）与 `test_nonnormal_two_sided_limit_crossings`（上下越界预期数按重拟合后的实际分位限计算，`below>=1 and above>=1`，`alarms == below + above`）。

此前方案：`test_improvement_chart.py`/帮助/清单/旧 Cpk 守卫等共 176 项通过。Tk 套件合并运行仍偶发 `tcl_findLibrary` / `tk.tcl` 环境错误，单独运行通过（既有问题）。

遗留：非正态主图未实现经统计验证的连续点判异规则，目前只报告越界。

- pandas 3 兼容：`.venv`（Python 3.11.9、pandas 3.0.6）下 `test_table_regressions.py`、`test_g17_data_processing.py`、`test_g6_chart_presentation.py`、`test_phase1_plots.py` 合并 387 项通过。既有无关失败：paste 4 项、工程保存 3 项（沙箱临时目录权限）、便携存储 1 项、绘图器 `toggle_options` 3 项（并行 GUI 任务）。

- 通用绘图器列角色：`tests/test_plotter_roles.py` 8 项（真实 Tk，`PythonEnvs/minijmp`）与 `test_g21_plotter.py`、`test_phase1_plots.py` 合并 74 项通过；`test_dialog_translation.py` 相关 48 项、`test_g12_*`+`test_menu_localization.py` 89 项、`test_help_center.py` 13 项通过。`test_dialog_translation.py::test_original_analysis_code_is_unchanged` 仍因既有 `fit_dialog.py` 差异失败；`test_g18_performance.py` 的 `int64` 用例为 pandas 3.0 兼容问题、Excel 用例受沙箱临时目录权限限制，均与本次绘图改动无关。

- `tests/test_worksheet_formulas.py` 20 项通过；`tests/test_worksheet_context_menu.py`、`tests/test_sheet_context.py`、`tests/test_file_io.py`、`tests/test_table_regressions.py` 相关用例通过；计算器真实 Tk 交互验证 25→50 自动更新。
- `tests/test_g12_inventory.py` 仅`python_files`计数与本任务新增文件相关；当前工作区另有并行任务文件（`improvement_*`）未纳入本任务清单。
- 阶段对比：`tests/test_improvement_chart.py` 33 项、`test_g5_spc_reports.py` 74 项（`-s`，与前者合并 107 项通过）。结果窗口在后端 `limit_details` 为空时不建标签页，有明细时显示并支持导出当前页；两个方向均有真实 Tk 断言。多套 Tk 测试合并偶发 Tcl 初始化错误，单独运行均通过；`test_dialog_translation.py::test_original_analysis_code_is_unchanged` 因已提交的 `fit_dialog.py` 差异失败，与本次改动无关。

## DOE-0 工程基础（2026-10-27）

- DOE-1 推断及交互图修复：无独立重复的简化全因子模型禁用推断；独立重复按相同组合计算纯误差 SSE/df，无中心点时拆分失拟 SSE/df，但不检验失拟显著性。OLS 推断使用模型残差均方，明确要求模型充分、误差独立同方差且正态；中心点推断仍禁用。交互图可选择任意两个因子并标示上次分析快照。真实 Tk 已覆盖三因子各因子对、多响应、非法创建、两个独立工作表、删除和重开后旧来源失效。`.venv` DOE 专项 26 passed、2 warnings；关联 DOE-0/工作表/工程/公式/G12/菜单/帮助/绘图生命周期 278 passed、9 warnings。见当日日志。

- DOE-1 基础：`doe_factorial.py` 生成 2–6 因子的完整组合、独立重复和中心点；`doe_analysis.py` 验证 DOE-0 摘要及组合并拟合层级模型；`doe_dialog.py` 和菜单支持创建、响应后填、分析、StatTable 与基础图。饱和模型不推断；中心点单独建模且推断暂不可用。先前 19 项专项和 278 项回归为历史结果，当前修复及验证见上条；未做 LRM 评审。

- 基于 beta.4 后的当前 HEAD e61d43c0bc21 增加纯数据模块 code/doe_core.py；beta.4 tag、版本文件和发布产物未修改。
- 公共类型/API：FactorSpec、DesignSpec（含受控 design_type）、RunRecord、DesignResult、ModelResult、OptimizationResult、randomized_run_order()、design_from_worksheet()、worksheet_metadata()、restore_design_result()。design_type 区分 two_level_full、two_level_fractional、central_composite 与明确的 unspecified，进入 schema v1 序列化和输入摘要；缺失/未知值拒绝。连续因子编码保持精确，必要时返回 Fraction；分类因子仅有结构占位，不允许混合水平设计或设计生成。
- Worksheets.saveMeta/loadMeta 增加可选每表 doe schema；列名保留原类型，run_id 映射到 iloc 行，不用 DataFrame.index。列顺序用 SHA-256 指纹校验，未映射列名不重复进入元数据；设计定义、映射、行 ID 和输入摘要仍保留，不复制 X/Y 原值。实测水平与响应是观察字段，可晚填/修正；设计设定或行映射变化会让保存/恢复失败。摘要不是匿名化；映射列名和 run_id 必须使用非敏感值，通用代码不具备 PII 语义检测；.dexpl 仍是原有可信 pickle 边界。
- 记录合同区分 standard/run order、点类型、重复、区组、设定与实测水平及可空多响应；轴点必须匹配 CCD alpha/轴点数声明。residual_df == 0 的 ModelResult 禁止 t/p/F 字段。独立 2² 解析参考得到 Y=(53,41,51,55)、效应 A=6、B=-4、AB=8；未实现 DOE-1 分析器。
- 最终验证：项目 .venv Python 3.11.9、pandas 3.0.6；py_compile 通过；DOE 核心/持久化、worksheets、sheet context、file I/O、公式及 G12 inventory 合并 160 passed、0 failed、0 skipped。G12 已核对 103 个 code/**/*.py 文件。
- 下一步继续 DOE-1 验收与缺口处理；部分因子、生成元和别名不在当前范围内。

## 当前限制

- 只支持工作表内 C 列引用，不支持跨表、Excel 语法、宏或完整 Minitab 函数库。
- 公式结果为浮点列；部分溢出或除零写为空值并提示。
- 环境状态（2026-10-27）：旧 `C:\Users\shaoy\Documents\PythonEnvs\minijmp`（Python 3.11.9、pandas 2.2.3）已停用并列入退役；递归删除被执行策略拒绝，目录目前仍存在。后续 MiniJMP 仅使用项目 `.venv`（Python 3.11.9、pandas 3.0.6）。此前 Tk 测试改用旧环境的记录及 beta.3 基线均保留为历史事实；若 `.venv` 的 Tcl/Tk 运行时脚本问题影响后续测试，应在 `.venv` 内处理，不复用旧环境。
- 改善前后分析未实现 P/NP/C/U 图、复杂时间序列模型、规则 1～8 以外的判异规则；固定基线模式的 Xbar-S 为获得可绘制 S 限，保留原算法对 bar2 的已知口径差异并单独校正（子组大小取改善后各组的 n）。

## 公式收尾修复（2026-10-25）

- 粘贴保护改为在最终 `target_rows`/`target_cols` 解析后校验；单元格扩展或整行粘贴覆盖公式列时整次拒绝，无部分写入与撤销记录。
- `load_formulas` 恢复保存的 `stale`，手动模式重开后仍显示 `*`；`export_formulas` 原样保存该状态；自动模式仍重算。
- `row1ToHeader` 使用 `formula_columns_renamed()` 按列位置成批改名；`sortSelected` 走 `tableChanged()` 刷新公式，并拒绝单独排序公式结果列。
- 撤销历史中每个 `prevdf` 快照并列保存公式定义（`_formula_history`），`delete_column_formula` 也先记录快照。
- 验证基线：`tests/test_worksheet_formulas.py` 26 项，加上下文剪贴板、表格、工作表、数据安全、CSV 与工程相关共 324 项通过。

## 数值列名公式持久化（2026-10-25）

- `row1ToHeader()` 可产生数值列名；公式目标与来源必须保持 DataFrame 实际列名类型。
- `load_formulas()` 不再要求目标是 `str`，也不对所有来源执行 `str()`；`_match_column_name()` 仅对非字符串列名按当前 DataFrame 列匹配，字符串保持原样以兼容旧工程。
- `export_formulas()` 返回原类型，pickle 工程往返后可正常重算。`C1`、`C2` 表达式语法未变。
- 验证：`tests/test_worksheet_formulas.py` 27 项（新增数值列名保存/加载/重算）及上下文剪贴板、表格、工作表、工作表右键菜单共 207 项通过。

## DOE Minitab 功能对标工作包 A（2026-10-27）

- 基线：main HEAD fd76b69b59f98d11751074a2d68e1b396f11773a；开始时工作区干净。DOE-0～DOE-4 APPROVE 未变。
- 只读调查 Minitab Statistical Software 官方在线帮助及 MiniJMP 源码/测试；产品版本未由官方页面注明。已新增 docs/doe-minitab/README.md、feature-matrix.csv、acceptance.md、roadmap.md、sources.md。
- Review 修正后矩阵 80 项（10 implemented、13 partial、52 missing、4 unknown、1 excluded），66 个唯一验收号；原 001–063 稳定，新增 TAG-010/011、FAC-019 与 ACC-064–066。P0 与 Level 1 完全一致；已实现 P0 项复用 DOE-0～4 基线，不重复安排开发，FAC-009 的 ACC-012 保留为回归验收。
- Review 修正官方定义：General Full Factorial 的数值水平仍是分类水平；Taguchi 覆盖 4/5/mixed-level 与四类静态 S/N、adjusted 公式及独立数值参考；D-optimality 与 distance-based 按设计家族限定；不要求无官方承诺的全局最优保证。B/D/E 完成 Level 1 ANOVA、诊断和 schema 前置验收，H 保留最终跨类别验收。
- 最终自动检查：项目 .venv Python 3.11.9 下验证 CSV 80×20 结构、状态计数、66 个连续且一一映射的验收编号、P0/Level 1、A–H 路线映射、UTF-8/Markdown 本地链接/尾随空白；`git diff --check` 通过。未跑 pytest、未改产品代码/schema/菜单/测试/CHANGELOG_DEV；待用户最终审查。详见当日日志。
