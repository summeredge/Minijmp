# MiniJMP 工作记忆

## DOE Phase 2 P1 核心对标（2026-10-29，限定范围 Review APPROVE）

- 当前阶段 P5 完成：Mixture 单元 A 与 RSM 区间/诊断单元 B 本地验收通过。ChatGPT/Local MCP Connector 首轮 Review 对 A-01 重复点间距与 B-01 预测失败后旧 CI/PI 残留给出 ITERATE；两项修复及定向核心/Tk 回归通过。复审经 Connector 读取当前工作树后分别给出 `MIXTURE_OPTIMAL: APPROVE`、`DOE_RSM_INTERVAL_DIAGNOSTICS: APPROVE`；无新增阻断。方法合同顶部状态已按非阻断文档发现更新。本地收尾提交 `e702079fbe840ced0a0039e0b3a917c74b114d52` 已创建；记忆文件按规则保留在工作区，不纳入提交；不启动后续包。
- 基线复核：`main` 含 H 基线 `ed85429ed23c52a6b2a238ad86fc1517ace93ff6`；DOE v5、Mixture Schema 1；开始时仅已有 `docs/doe-minitab/roadmap.md` P2-0 内容未提交，完整 Phase 2 gap/roadmap/acceptance 原稿缺失。
- 根据 P2-0 摘要、现有 E/F/H 收尾、目标文件和 Minitab 官方帮助重建 `phase2-gap-analysis.md`、`phase2-roadmap.md`、`phase2-acceptance.md`；缺失原稿未被伪称读取。P1 方法合同见 `docs/doe-minitab/phase2-p1-method-contract.md`。
- 已冻结 Mixture 合同：D-opt 用实际比例与 `MixtureTermModel` Scheffé 项；Distance 全含组分，可选过程/总量并归一到 [0,1]；纯组分最近点起始，后续确定性最远点；父设计固定，D-opt 有放回语义显式化。
- `.venv` 已核实 Python 3.11.9、NumPy 2.4.6、SciPy 1.15.3、statsmodels 0.15.0、Tk 8.6。P2-0 原始规划稿在本地开始时确实缺失；对应 reconstruction 标记已保留。
- 独立 Mixture fixture `tests/fixtures/doe_phase2_optimal_reference/` SHA-256 `29bd937eae7415579c9992afe780b9546708653d604cfe939afffcdcf749a4ed`，verifier 13 项通过。最新 P2 核心组 98 passed；Mixture Tk 8、Mixture persistence 4、schema v2/v3 33、bad DOE metadata 6 passed/4 deselected、optimal GUI 6、Help 13、Menu 66 均通过，详细分组在 `logs/2026-10-29.md`。
- 独立静态 P2 审查曾发现增补将大整数响应强制转 Float64 并把已有空 batch 改成 BASE；已移除强制浮点转换与父批次填充值，新增 `9007199254740993`/空批次反例并通过核心回归。原样保留父数据是后续验收不变合同。
- RSM fixture `tests/fixtures/doe_phase2_interval_reference/` SHA-256 `d87d1720c24000fec7ebbf42cb2e1f58f8c52d2be8fadfcee7600f3bc4121a72`；独立 verifier 覆盖 9 个置信度/方向组合及 9 行影响诊断。RSM 模型回归 27、区间/诊断 37、Predict Tk 7、Analyze Tk 12、E/F/G 保存重开复制集成 1、Help 13、Menu 66 均通过。全量 pytest 未运行；Matplotlib `tight_layout` 只有 3+3 条警告。
- 独立代码审查发现误差方差阈值按未中心化响应平方和缩放，基线加 1e8 会误禁用有效 CI/PI 与 Cook's D；现阈值改为依赖响应变化和舍入尺度，平移不变性回归及全部受影响测试通过。独立复核确认平移后影响值 9/9 可用、精确拟合仍不可用，无剩余发现。
- 首轮 Review 修复验证：混料最小平方距离对重复运行报告 0，`test_doe_mixture_optimal.py` + `test_doe_optimal_evaluation.py` 22 passed，Mixture Tk 8 passed；预测重算一开始清除旧表，响应失败及来源切换 Tk 回归，Predict Tk 7 passed；`git diff --check` 通过。独立复审 A/B 均 APPROVE。
- 当前界限：仅连续 CCD/BBD/custom RSM；多区组区间、Logistic、Mixture、Split-Plot 与优化器候选区间不支持；官方方法页未标版本且本地无 Minitab 22 输出，不声明版本 parity。最终复审后停止。

## 工作包 H 最终收尾（2026-10-29）

- 状态 `WORK_PACKAGE_H_APPROVED_SCOPED`：H0–H6 限定范围完成，用户提供上一轮 ChatGPT 独立 Review 结论 APPROVE（限定范围）。ACC-004/019/020/031/059/060 均在限定范围 implemented；Schema v5 不变。
- 本轮 H 专项 59 passed，独立参考 verifier 通过；负向 δ 功效窗口和 v5 工程往返各 1 passed，Help/Menu/G12 共 94 passed。矩阵 80 项为 58 implemented、18 partial、3 unknown、1 excluded；完整命令、历史结果和限制见 `docs/doe-minitab/work-package-h-closeout.md`。
- 未覆盖二元 RSM 优化器、分离修正、Variability MLE/复杂不等权/Split-Plot，功效限支持的两水平主效应 1 df F；不声明 Minitab 22 全功能或输出一致。下一步仅为建立 Minitab DOE 功能对标二期规划，二期尚未开始开发。

## 工作包 H H0–H6 本地集成（2026-10-29）

- 当时状态 `WORK_PACKAGE_H_READY_FOR_INDEPENDENT_REVIEW`（已被上方最终收尾取代）；H 代码与文档当时保留在未提交工作区，不 push/发布。此前 E/F/G Review 修正的 32 个代码/测试/产品文档文件按本轮授权提交为 `b8d64e0 Close out EFG integration fixes`；`.agent-memory` 未纳入提交。
- DOE Schema v5 足够：事件/试验与重复测量使用已在 `response_names`/`column_map.responses` 声明的响应列；元数据生成后新增列会失效。即时分析不增字段、不覆盖原响应；v1–v5 迁移合同不变。
- H 独立参考 `tests/fixtures/doe_h_reference/` 覆盖六项 ACC 的 STD/EDGE；生成器和 verifier 不导入生产模块。reference SHA-256 `f5f4ee2246b03b3c6ee1140bd3de9f67f4911a94416bc87520969e2f2baf5c78`。
- H 实现 grouped-binomial Logistic、两种 Factorial Variability 实验单位、以及两水平/PB/两水平 GFF 的非中心 F 功效。RSM-016 按明确 H4 范围（分析、预测、概率图）完成；官方 post-fit binary Response Optimizer 属于另一个未实现工作流，已在矩阵/方法合同中列出，不宣称功能具备。
- 验证：H 数学/核心 59 passed；本轮 Power+独立 H 参考 30 passed，负向 δ 真实 Tk 1 passed，Help Center 13 passed；真实 Tk 生命周期共 7 个单进程用例通过；跨族纯统计/Schema 328 passed；E/F/G 联合工程 1 passed；菜单/G12 既有记录分别 15 passed。全量 pytest 未运行，Windows Tk 原生检查按进程分开执行。
- 80 项矩阵：58 implemented、18 partial、3 unknown、1 excluded。未提升既有 partial/unknown/excluded；TAG-009、GEN-006、MIX-006 的旧证据字段错链已修正。Minitab 页面未声明版本，产品输出 parity 尚未做独立逐项对照。
- 首轮与 ITERATE 修复后的 Local MCP Connector 请求均因网页身份未匹配而 `pending_identity_expired`，两次 Review Execution 均未启动。修复 ACC-059/060 有符号 δ 输入后，状态为 `WORK_PACKAGE_H_READY_FOR_INDEPENDENT_REVIEW`；不自动重投，需匹配 ChatGPT Web 身份凭据。当时尚无最终 APPROVE，后续结论见上方最终收尾；不 push/发布，不启动 A–H 以外工作包。

## Taguchi 零方差 S/N Review 修复（2026-10-29）

- 状态 `READY_FOR_INDEPENDENT_REVIEW`；在已有 E/F/G 未提交工作区上定向修复 `noise_robustness()`，仅移除无条件 SD=0 拒绝，S/N 的公式与数据域仍由 `signal_to_noise()` 校验；Nominal 零方差仍拒绝，噪声因子和观测数校验未改。
- 独立反例 `[2, 2]`：Smaller = −10 log10(4) = −6.020599913279624 dB，Larger = −10 log10(1/4) = +6.020599913279624 dB，SD = 0；旧实现两种均错误拒绝。噪声及静态 S/N 两测试文件 50 passed，真实 Tk 噪声窗口 3 passed；未重复全量测试。验收矩阵、更新日志已按新合同修正。
- 保留先前未提交改动；未提交、推送或启动 H。待独立差异 Review，过程见 `.agent-memory/logs/2026-10-29.md`。


## E+F+G 合并后 Full Review ITERATE（2026-10-29）

- 状态 `EFG_INTEGRATION_READY_FOR_REVIEW`；本地 main HEAD `7392ac9cef74ea84c9dfb1d44485d36137ed6631`，开始时工作区干净，所有本次修改未提交；独立 Review 尚未执行，未推送或启动 H。完整报告见 `docs/doe-minitab/efg-integration-review.md`。
- P1 轴点：`DesignResult` 校验所有分类设定、限制轴点设计族并检查有限编码；`TermModel.row` 拒绝未知分类水平。混合自定义 RSM 反例在旧实现未报错，新实现包括重算摘要后的恢复路径均拒绝。
- P1 区组选点：GUI 传递来源 `block_count`；最优选点拒绝声明或映射区组的候选，避免输出无区组设计；两连续因子、二区组独立矩阵秩 4，仅一区组秩 3。
- Taguchi L8 两列投影数学上平衡但每组合重复两次；当前合同不支持重复设定的控制列投影，保留全部标准行与摘要，GUI 选择时提示。自定义 RSM 预测复用既有模型与参考区组，补充独立解析与真实 Tk 测试；更新帮助和搜索索引。
- 完整单进程 pytest 约 26% 在 Tk `Menu.add` 发生 `0x80000003`，无总汇总。替代的 174 组文件/PB 分进程清单覆盖最终收集的 5073 个不同节点，无遗漏、重复或跳过；首轮 G12 文件排序及帮助主题数共 2 失败，修正后相关组通过；预测变更后直接相关组已复测。不能称为单次全量通过。PB 六组 200 参数均通过；分组详细命令、警告和首轮失败见报告。
- 同一工程 E 自定义 RSM 增补、F 混料、G 静态/动态 Taguchi 保存/重开/复制/再分析/预测/绘图和坏元数据隔离 1 passed、3 warnings；菜单 66 passed，帮助 13 passed，G12 15 passed。F 参考数值不变，清单已改为实际文件字节摘要 `cfc482999750eafac2bd8bc89b469e628c405cce23e25c00c010f2695184b0de`；E/F/G verifier 均通过。
- feature matrix 修正 5 行 CSV 引号错位，80 行、ACC-001–067 唯一；18 个 partial 及范围见报告。必要过程见 `.agent-memory/logs/2026-10-29.md`。

## 工作包 E E0–E6（2026-10-28，本地收尾）

- 状态 `WORK_PACKAGE_E_READY_FOR_REVIEW`（限定范围）；BASE/HEAD `c3720d2737f44ad130d8b61cd07ae31073073c2d`，分支 `main`，开始时工作区干净；E 全部修改未提交，未启动 F/G/H。独立 Review 尚未执行。
- 新增 `code/doe_custom.py`（定义/校验/矩阵摘要/DSD 结构）、`doe_custom_analysis.py`、`doe_custom_dialog.py`、`doe_modify.py`、`doe_augment.py`、`doe_optimal.py`（select/exact_select/select_distance/evaluate）、`doe_optimal_design.py`、`doe_optimal_dialog.py`、`doe_diagnostics.py`；`doe_rsm.py` 拆出 `fit_rsm` 供自定义 RSM 复用。
- DOE Schema v5：新增 `model_terms`、`optimal_lineage`、`augmentation_lineage` 与自定义 Factorial/RSM/Screening 类型；v1–v4 按原字段与原输入摘要校验后迁移，坏元数据不替换当前工作簿。`doe_splitplot` 版本检查改为 `>= 4`。
- D-optimal 用 `logdet(XᵀX)`；候选 ≤40 穷举并标记 `global_optimum_proven`，更大候选集为确定性贪婪+交换且不宣称全局最优。Distance-based 仅响应面编码空间，Factorial 拒绝；增补同样支持：父设计运行作为固定锚点（`select_distance(initial=…)` / `doe_augment._distance_augment`），GUI 仅在响应面父设计开放。Mixture 距离合同依赖 F，GUI 未开放。
- 独立参考 `tests/fixtures/doe_optimal_reference/`（含 `verify.py`、`reference.json`、`manifest.json`），不导入生产模块；D-optimal 最低案例 x∈{-1,0,1}、截距+x、选 2 点，最优 -1/+1，det=4。自定义 DSD 参考为 6 因子会议矩阵 foldover+中心行与 4 连续+1 文本分类。
- 旧功能回归修复（同轮）：`doe_dialog.AnalyzeDOE` 曾把 `plot_custom_screening` 及各族发布分支并入 `show_diagnostics`，导致 PB/DSD/一般全因子/RSM/两水平设计分析后 `self.result` 不赋值；现拆为 `publish`→`show_diagnostics`（仅诊断页）→`publish_tables`（各族原分支），`plot_custom_screening` 独立其后。`doe_diagnostics` 的模型 F/p 改为按 `inference` 是否含 `f` 判定，一般全因子/裂区不再 `KeyError`。相关既有测试期望同步：诊断合同页首项、schema v5。
- 绘图路径修复：自定义 RSM 项平方和的行键为 `source`、自定义 Factorial 为 `term`，统一用 `row.get('source', row.get('term'))`；`analyze_custom_factorial` 补齐 `coded` 与 `effects`（2×系数），修复交互图与发布表崩溃。新增三条真实 Tk 绘图回归（Factorial 6 子图、RSM 4 子图、Screening 6 子图）。
- 自定义 RSM 模型项回退缺陷：`analyze_custom_rsm` 在 `terms=None` 时把 None 传给 `fit_rsm`，后者按完整二次模型建模，导致只声明部分项的合法自定义设计（主效应+交互）被判秩亏。现默认取 `DesignSpec.model_terms`；带区组的自定义设计在分析矩阵中加入区组项（`区组2` 列），独立核对系数 X1=1、X2=2、区组2=3。
- `docs/doe-minitab/sources.md` 补写 E 实施证据（自定义定义只描述既有运行、DSD 构造按官方页、D/distance 家族范围、无 Minitab 22 导出），并把 A 阶段“SCR-005 missing”条目标注为历史。矩阵的代码/测试证据路径与 acceptance 验收号映射经脚本核对：0 条失效路径、0 个未映射编号。
- 增补边界补测（`test_doe_augment.py` 6→9 项）：父设计行内容改变、行顺序调换、run_id 改写、父来源空表均按摘要/映射失效拒绝；`_MAX_RUNS=10000` 超限在写入前拒绝且来源表不变；父设计已满秩 3/3 时增补如实报告 `rank_improved=False`。
- ACC-054 补齐修改类型：`doe_modify.renumber`（按标准序重写运行序，保留设定/响应/重复）、`doe_modify.replicate`（完整重复：新重复编号与新运行 ID、新响应留空、上限 10000、折叠/增补设计拒绝、拼接后恢复响应列 dtype）；`doe_custom._validate_factorial` 改为按 `(重复编号, 因子点)` 查重，允许独立重复。GUI 修改窗口新增“按标准序重编号”“增加完整重复”与重复数输入。
- GUI（目标 8.1/8.2）：修改设计窗口新增“预览对照”（前 6 行 `run_id@运行序`、按 run_id 统计运行序变化、明示设定/响应不变，预览不写工作簿）；修改/增补/最优三个窗口的按钮条改为 `side='bottom'` 先占位，420×260 与 360×200 下按钮全部可见。
- 验证快照（2026-10-28 ITERATE 修复后，各组重叠不可相加；全量 pytest 未运行）：指定八文件 63、E 非 GUI+GUI+工程与 Schema 22 文件 204（30 warnings）、B/C/D 冻结参考+分析优化+help/menu/G12+工作表 19 文件 489（8:38）、help/menu/G12 94。筛选 GUI 排除 PB 参数组 118（200 deselected），PB 200 案例按运行数拆进程 20/28/32/36/40/44 全通过（整文件单进程在 PB 参数案例触发 Tk 原生 `0x80000003`，不计通过）。帮助索引 98 主题。
- ITERATE 四项阻断修复：`select()` 精确搜索改按 `comb(n,count) ≤ 200000` 预算（20 选 10 穷举、21 选 10 降级），返回 method/exact_budget/subsets/evaluations/stop_reason；`select_augment()` 同样按组合数判定，启发式只换新增位置；`manual` 准则改为严格按输入顺序（GUI 增「按输入顺序」）；增补矩阵与 distance 选点统一 `coded_value(factor,value,point_type)`，轴点可越界、标 factorial 仍拒绝；Distance 选点后按选中运行重建矩阵，秩亏拒绝并回填 selected_n/p/rank/estimable。参考 fixture 未改，SHA-256 `499fd66c…`。
- 参考集新增 `distance_augment`（四角固定 + 中心/边中点，选点顺序 [0,1]、增补后最小平方间距 1），构建器与核验器各自手算；`reference.json` SHA-256 重建后为 `499fd66c8…`（manifest 同步）。ACC-056、ACC-058 仍标 partial，但原因只剩 Mixture 距离合同与 Mixture 增补；响应面 distance-based 选点与增补已在限定范围通过。文档：`work-package-e-closeout.md`、`optimal-reference-validation.md`、acceptance/roadmap/README/CHANGELOG_DEV/MENU_TRANSLATION/help。
- 遗留：Minitab 22 对自定义/最优/增补的导出案例缺失；旧版 MiniJMP 读取 v5 工程的产品行为未验证；矩阵统计已按 CSV 更新为 32 implemented / 14 partial / 30 missing / 3 unknown / 1 excluded。
## 工作包 F 混料设计（2026-10-28，隔离 worktree）

- 状态 `WORK_PACKAGE_F_READY_FOR_REVIEW`；分支 `codex/f-mixture`（提交 `34946c5`，BASE `c3720d2`）已合入 `main`（E 的 `18070e4` 之上），冲突按 E+F 双方内容解决；未推送、未启动 G/H。E+F 联合回归（因用户要求未执行测试）和独立 Review 仍未完成。
- 新增 `code/doe_mixture*.py` 九个模块：约束、专属合同、三类设计、Scheffé 模型/ANOVA、预测、优化、图形、GUI。菜单新增创建/分析/预测/优化/图形五项；帮助新增 `doe.mixture*` 并重建索引。
- 混料语义存 `table.mixture_metadata`（schema 1），最近分析模型存 `table.mixture_model`（响应/阶次/模型项/输入摘要），DOE v4 仅新增 `design_type='mixture'`，不改 v4 字段集；`worksheets.saveMeta/loadMeta` 先验证后赋值。总量目前固定一个设计设定，MIX-005/ACC-036 为 partial。
- 独立参考 `tests/fixtures/doe_mixture_reference/`（Fraction + 自写高斯消元），`reference.json` SHA-256 `8ae2c0712fdb423a0570336ebf96cca0dd8366e56c7dddf1be007ad36099c913`；覆盖格点/重心/5 顶点/ANOVA/优化网格/Trace/叠加 11 点。
- 独立 Review ITERATE 五项已修复：默认 Mixture×Process 去掉过程主项 `P`（保留 `xi*P` 与秩检查）、模型 F/df 改用增量秩（校正/未校正平方和分流）、可估计性改判行空间、组分主项只报删除项条件平方和、双组分图形改为拒绝二维并提示 Trace。closeout 文档含“Review ITERATE 修正”段。
- 验证快照（最终状态）：混料 12 文件 64 passed（24.01s）；DOE 非 GUI 427 passed（348.77s）；既有 DOE GUI 15/11/9/13/10 passed；菜单/帮助/G12/工作表/文件/工程 173（菜单单项 66）。测试组重叠，全量 pytest 未运行。
- ACC-032/033/034/035/037/038/039/040/041/042/043/044 implemented（限定范围），ACC-036 partial；Minitab 标准序、XVERT/CONAEV 顺序、图形布局与预测区间未核实。详见 `docs/doe-minitab/work-package-f-closeout.md` 与 `work-package-f-integration-plan.md`。

## 工作包 D D0–D5（2026-10-28，本地收尾）

- 独立 Review 遗留两项已修复：General Full Factorial 创建与恢复统一限制 2–10 因子（1/11 拒绝，10 因子仍受 10,000 行上限）；Split-Plot 预览显示运行/区组/整区数，仅插入前 100 行并提示总数，增加水平滚动，实际创建保持完整。专项八文件 42 passed、D 非 GUI 182、B/C 非 GUI 358、Factorial Tk 22、菜单帮助/G12 94 passed；测试组重叠，全量 pytest 未运行。ACC 状态未变，工作区仍未提交。
- 状态 `WORK_PACKAGE_D_READY_FOR_REVIEW`；BASE/HEAD `e7a46737612cf5b56cd7d02911c4d13ec4753087`，分支 `main`，开始时工作区干净。D0–D5 限定范围已完成；独立网页端 LRM Review 尚未执行，未提交/推送，不启动 E/F/G/H。
- D0 独立参考位于 `tests/fixtures/doe_factorial_reference/`，`reference.json` SHA-256 `0c3e379a6962efe224695ba79a21d101319d4298d1ed6962c9a8a9b6dfef37ba`；包含一般全因子、正负定义关系、Foldover 完整别名/精确秩、完整区组和 3-block 2×2 Split-Plot SS/df/F/p。核验器不导入生产模块。
- DOE Schema 当前 v4；v1/v2/v3 按旧字段与原输入摘要校验后迁移。D1 一般全因子范围为 2–10 分类因子、文本/数值标签、完整笛卡尔积和完整重复区组；分析密集矩阵上限 10,000,000 个单元。旧版 MiniJMP 不保证读取 v4 工程。
- D2 正规分数支持 signed generators、中心点和每个完整重复一区组；Foldover 只支持未分区组正规分数的全因子或单因子单批次，保留响应并存 parent/run map/batch 和原始/当前矩阵 SHA-256。PB、Split-Plot、重复折叠和 Minitab 输出/标准序未覆盖；FAC-012 维持 partial。
- D3 区组仅按完整重复分配，适用于两水平全因子、正规部分因子和 General Full Factorial；中心点须平均分配。Split-Plot 限两个连续两水平因子、一个 hard-to-change 与一个 easy-to-change、至少两个平衡区组；A 用整区误差，B/AB 用子区误差。自定义区组分割、更大/不平衡裂区和 REML 未覆盖，FAC-008/010/019 为 partial。
- D3 验证快照：数学/Schema/区组/Split-Plot 专项 140 passed；Foldover+独立参考 13 passed；普通 DOE GUI 5 passed（2 warnings）、Fractional GUI 15 passed（1 warning）、Split-Plot GUI 2 passed（1 warning）、Foldover GUI 2 passed、menu 66 passed、help/G12 28 passed；帮助索引成功重建。测试组有重叠，未运行全量 pytest。
- D4 统一三类 factorial 分析器的 pure-error/区组误差分解；无独立纯误差时不输出 LOF F/p。中心曲率使用独立纯误差；分层 ANOVA 与真实水平诊断图有独立参考验证。ACC-007/011/013/015/017/018/066 及未核实产品范围维持 partial。
- 验证快照：factorial 分析/误差分解 45 passed；D 非 GUI 设计/Schema/分析组 176 passed；B/C 非 GUI 回归 358 passed（310.15 秒）。GUI 分组、帮助、菜单、工作表和文件测试明细见 `docs/doe-minitab/work-package-d-closeout.md`；各组重叠，不相加，全量 pytest 未运行。
- D5 的创建、预览、响应填写、分析、图形、保存/重开/复制/再分析和旧 Schema 回归已覆盖。帮助索引重建成功；Help/G12 28 passed、menu 66 passed；独立 factorial verifier 通过。
- 筛选 Tk 大文件本轮未完整执行：约 22% 时停止长进程；D4 影响的 PB 绘图和代表性 DSD 工程用例分组复跑通过，但该整文件未在最终快照重跑。独立网页端 LRM Review 尚未执行，未提交/推送。

## 工作包 B/C 收尾（2026-10-28，细节见当日日志归档）

- 状态：B+C 联合收尾 `BC_READY_FOR_INDEPENDENT_REVIEW`；C 最终 `WORK_PACKAGE_C_PARTIAL`（ACC-001/002/003/005/006 partial）。B 的核心/对标/旧工程 274、DOE-1/2 52、C 核心/schema 156、B Tk 69、C Tk 118（200 deselected）、帮助/菜单/G12/工程基础 163 passed 均为该轮快照。
- C 已实现 PB 全部官方基础运行数、文本因子/伪中心/重复区组，DSD 2–48 连续、混合 1 分类与 4+2 分类、均分区组，Lenth PSE/标准化效应图/零空间/对比；PB 200 案例按运行数拆进程 20/28/32/36/40/44 全通过（单进程触发 Tk 原生 0x80000003）。
- B 五份 Minitab 22 导出：点集与区组重编号后一致，标准序分别差 60/116/123/120/163 行；ACC-022B 仅限这五种设置。C0 的 NIST PB 与 conference-matrix DSD 参考与 SHA-256 有效。
- 上述过程的完整数字、命令与 C0 构造细节见 `.agent-memory/logs/2026-10-28.md` 的“归档”两节。

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
