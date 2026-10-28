# 工作包 E 收尾记录（自定义、最优设计、增补与跨设计诊断）

## 状态

- 结论：`WORK_PACKAGE_E_READY_FOR_REVIEW`（限定范围）
- 基线：BASE = HEAD = `c3720d2737f44ad130d8b61cd07ae31073073c2d`，分支 `main`，开始时工作区干净；结束时 E 的全部修改与新增文件仍未提交
- Schema：DOE v5；v1–v4 先按原字段与原输入摘要校验，再迁移
- 未执行：git commit / push / tag / reset / clean / stash；未启动 F/G/H

## 各阶段

| 阶段 | 内容 | 结果 |
|---|---|---|
| E0 | 独立参考、Schema 与技术合同 | `tests/fixtures/doe_optimal_reference/`，见 [参考核验](optimal-reference-validation.md) |
| E1 | 自定义 Factorial / RSM / Screening | `code/doe_custom.py`、`doe_custom_dialog.py`、`doe_custom_analysis.py` |
| E2 | 修改与通用增补 | `code/doe_modify.py`、`doe_augment.py` |
| E3 | D-optimal 选点 | `code/doe_optimal.py` |
| E4 | Distance-based、评价、最优增补 | `select_distance`、`evaluate`、`select_augment`、`doe_optimal_design.py` |
| E5 | 跨设计诊断与 Schema 兼容 | `code/doe_diagnostics.py`、Schema v5 |
| E6 | GUI、工程生命周期、回归、文档 | `doe_optimal_dialog.py`、菜单/帮助、本记录 |

## 支持范围

- 自定义 Factorial：两水平（数值或文本）因子、因子点与中心点；报告完整性、唯一点数、中心行、重复、实际秩与条件数；不把非正规矩阵称为正规分数。
- 自定义 RSM：2–10 连续因子（可含已验证分类因子），显式模型项，按实际矩阵重建；轴点允许位于声明 low/high 之外；秩亏模型拒绝分析。分析默认使用设计声明的模型项（不再退回完整二次模型）；带区组的自定义设计在分析模型中加入区组项。
- 自定义 Screening：2–48 因子；连续低/中/高与两水平文本分类；要求主效应与二因子交互正交且存在中心水平；主效应之间相关仅报告，不拒绝。
- 修改：显示重排、按族合法重新随机化（含 Split-Plot 整区/子区嵌套）、按标准序重编号、增加完整重复（复制全部设计点、新重复编号、新运行 ID、响应留空、运行总数上限 10000，折叠/增补设计不叠加重复）；不修改因子设定或已填响应。
- 增补：固定父设计运行，从候选设置选择新增运行；准则为 D-optimal（默认）、distance（仅响应面）或按输入顺序；D-optimal 最大化 logdet，distance 以父设计点为固定锚点按最远点规则补点且不复制候选，按输入顺序则严格取用户给定前 count 行、不做任何准则搜索；批次、父设计、前后矩阵摘要持久化；新响应留空；目标模型未满秩时拒绝。父设计行永不参与交换或删除。
- D-optimal：是否穷举由候选行数与组合数预算共同决定（≤40 行且 `comb(n,count) ≤ 200000`）；超预算自动降级为多起点贪婪+交换，返回实际方法、预算、已评价子集数与停止原因，仅真正完成穷举才标记全局最优已证明。
- 增补搜索：同样按组合数预算判定（30 选 15 的 155117520 个子集直接降级），启发式只交换新增位置与未选候选之间的点。
- Distance-based：仅响应面编码空间；Factorial 拒绝。选点后按真正选中的运行重建模型矩阵，满秩才生成设计，秩亏明确拒绝并报告秩/参数数。Mixture 距离合同依赖 F，GUI 未开放（partial）。
- 轴点编码：增补矩阵统一使用 `coded_value(factor, value, point_type)`，父设计按各自 point_type、候选按传入 point_types；轴点允许位于 low/high 之外，factorial/center/edge 仍严格校验范围。
- 诊断：n、p、秩、残差自由度、SSE/SST、纯误差、失拟、曲率、条件数、可估计性、假设状态；各设计保留自身统计模型与误差层。
- Schema：v5 新增 `model_terms`、`optimal_lineage`、`augmentation_lineage` 与自定义类型；坏元数据不替换当前工作簿。

## ACC 状态

| 编号 | 状态 | 说明 |
|---|---|---|
| ACC-014 | 限定范围通过 | 自定义两水平设计定义、分析、GUI、工程往返 |
| ACC-016 | 限定范围通过 | 通用增补、批次、唯一 ID、响应保留 |
| ACC-054 | 限定范围通过 | 显示重排、按族重新随机化、按标准序重编号、增加完整重复 |
| ACC-055 | 通过 | 独立穷举 det=4；20 选 10 可穷举、21 选 10 自动降级；大候选集不宣称全局最优 |
| ACC-056 | partial | RSM 通过（含选中设计可估计性校验）；Mixture 距离合同未建立 |
| ACC-057 | 通过 | 固定模型/候选集的秩、条件数、logdet、受保护 det |
| ACC-058 | 限定范围通过 | D-optimal、响应面 Distance-based 与按输入顺序三种增补；组合数预算降级；Mixture 增补仍缺 |
| ACC-061 | 限定范围通过 | 统一字段语义；未自动检验假设 |
| ACC-062 | 限定范围通过 | v1–v4 读取迁移；旧版 MiniJMP 不保证读 v5 |
| ACC-063 | 限定范围通过 | 自定义 RSM 模型项、秩与范围校验 |
| ACC-067 | 限定范围通过 | 自定义 DSD 构造性质、GUI、工程往返 |

## 验证命令与结果

全部在 `.venv` 下执行（`$python = .venv\\Scripts\\python.exe`）：

- `& $python tests\\fixtures\\doe_optimal_reference\\verify.py` → 通过
- `& $python -m pytest tests\\test_doe_optimal_references.py tests\\test_doe_optimal.py tests\\test_doe_optimal_evaluation.py tests\\test_doe_distance_optimal.py tests\\test_doe_optimal_augmentation.py -q` → 33 passed
- `& $python -m pytest tests\\test_doe_custom_factorial.py tests\\test_doe_custom_rsm.py tests\\test_doe_custom_screening.py tests\\test_doe_modify.py tests\\test_doe_augment.py tests\\test_doe_diagnostics_contract.py tests\\test_doe_schema_e.py -q` → 42 passed（含前一组重叠，见下）
- `& $python -m pytest tests\\test_doe_custom_gui.py tests\\test_doe_optimal_gui.py tests\\test_doe_e_lifecycle.py -q` → 9 passed
- `& $python -m pytest tests\\test_doe_core.py tests\\test_doe_persistence.py tests\\test_doe_schema_v2.py tests\\test_doe_schema_v3.py tests\\test_doe_factorial_schema.py tests\\test_doe_foldover.py tests\\test_doe_splitplot.py -q` → 95 passed
- `& $python -m pytest tests\\test_doe_rsm.py tests\\test_doe_bbd.py tests\\test_doe_ccd.py -q` → 96 passed
- `& $python -m pytest tests\\test_doe_fractional.py tests\\test_doe_general_factorial.py tests\\test_doe_factorial.py tests\\test_doe_screening_analysis.py tests\\test_doe_analysis.py tests\\test_doe_rsm_diagnostics.py tests\\test_doe_rsm_categorical.py -q` → 83 passed
- `& $python -m pytest tests\\test_help_center.py tests\\test_menu_localization.py tests\\test_g12_inventory.py -q` → 94 passed
- 收尾合并复核（文档定稿后、代码未再变化）：E 非 GUI 十二文件 → 68 passed；`test_doe_custom_gui.py test_doe_optimal_gui.py test_doe_e_lifecycle.py test_help_center.py test_menu_localization.py test_g12_inventory.py` → 103 passed
- Distance-based 增补补齐后复跑（当前快照）：E 非 GUI 十二文件 → 78 passed；`test_doe_custom_gui.py test_doe_optimal_gui.py test_doe_e_lifecycle.py test_help_center.py test_menu_localization.py test_g12_inventory.py` → 110 passed；B/C/D 冻结参考与分析与优化（15 文件）→ 278 passed；B/C/D/D0 GUI 与 Schema v1–v4（18 文件）→ 192 passed；工作表与工程基础 → 69 passed；帮助/菜单/G12/参考核验 → 95 passed
- 帮助索引：`& $python tools\\build_help_index.py` 成功，主题数 98

### 收尾回归修复（同日）

#### 独立 Review ITERATE 定向修复（四项阻断）

1. **D-optimal 预算自动降级**（`code/doe_optimal.py`）：`select()` 现要求候选行数 ≤ `exact_limit` **且** `comb(n, count) ≤ _MAX_EXACT_SUBSETS(200000)` 才走穷举；否则调用新的 `_search()`（多起点贪婪 + 交换）并返回 `method`、`exact_budget`、`subsets`、`evaluations`、`stop_reason`。`global_optimum_proven` 只在真正完成穷举时为真。显式 `exact_select()` 仍按超预算报错，公共 `select()` 不再因此失败。实测 20 选 10 = 184756 子集走穷举；21 选 10 = 352716 子集自动降级，评价值 2558 次、无异常。
2. **增补搜索预算**（`code/doe_augment.py`）：`select_augment()` 改按 `comb(len(candidates), count)` 判定，超预算走 `_greedy_augment()`（只交换新增位置与未选候选，父设计行固定不参与）。30 选 15（155117520 子集）降级且评价次数远小于组合数。`criterion='manual'` 不再偷偷执行 D-optimal：严格按用户给定顺序取前 `count` 行，`method='manual'`、`global_optimum_proven=False`，谱系如实记录 `criterion='manual'`；GUI 增补窗口新增“按输入顺序”选项。
3. **RSM 轴点编码统一**（`code/doe_augment.py`、`code/doe_optimal_design.py`）：增补矩阵构造改走 `coded_value(factor, value, point_type)`，父设计行用各自 `point_type`、候选用传入 `point_types`，中心点判定与因子点校验同步改用该语义；distance 选点的编码也改为 `coded_value`。轴点 (1.682, 0) 等可正常编码，标为 `factorial` 的同一数值仍被拒绝。
4. **Distance-based 选中设计可估计性**（`code/doe_optimal_design.py`、`code/doe_optimal_dialog.py`）：选点后按真正选中的运行重建模型矩阵，回填 `selected_n`/`selected_p`/`selected_rank`/`estimable`/`rank`/`p`/`logdet`，秩亏时抛“不能估计目标模型”并给出秩/参数数；与 D-optimal 使用同一 `matrix_summary` 口径。GUI 预览显示选中运行数、参数数、实际秩、状态、搜索预算、已评价子集与停止原因。

新增独立反例：`test_exact_budget_allows_20_choose_10_when_subsets_fit`、`test_select_auto_degrades_past_subset_budget_instead_of_failing`、`test_200_candidate_search_records_budget_and_reproducible_seed`、`test_select_rejects_candidate_set_without_full_rank_subset`、`test_select_augment_budget_uses_combination_count_not_row_count`、`test_augment_keeps_parent_runs_fixed_and_never_swaps_them`、`test_augment_manual_criterion_uses_given_order_not_d_optimal`、`test_axial_augmentation_encodes_beyond_declared_range_for_both_criteria`、`test_out_of_range_candidate_marked_factorial_is_rejected`、`test_distance_selection_rejects_rank_deficient_three_point_design`、`test_distance_selection_accepts_full_rank_six_point_design`、`test_optimal_gui_distance_preview_reports_rank_and_rejects_deficient`。

- 修复 `code/doe_dialog.py` 的方法嵌套缺陷：新增的 `plot_custom_screening` 与后续发布分支曾被并进 `show_diagnostics`，导致 PB/DSD/一般全因子/RSM/两水平设计分析完成后 `self.result` 不再赋值。现拆为 `publish` → `show_diagnostics`（仅诊断页）→ `publish_tables`（各族原发布分支），`plot_custom_screening` 独立置于发布方法之后。
- `code/doe_diagnostics.py` 的“模型 F / p”改为按 `inference` 是否含 `f` 判定；一般全因子只提供 `mse`、Split-Plot 不提供 `inference` 时显示“不适用/该分析器不提供模型 F 检验”，不再抛 `KeyError`。
- 自定义 RSM 的“项平方和”读取 `source`、自定义 Factorial 的相同表格读取 `term`，现统一为 `row.get('source', row.get('term'))`；缺少 `coded` 与 `effects` 导致交互图崩溃的问题在 `analyze_custom_factorial` 补齐这两个字段（效应按 2×系数，与既有因子设计语义一致）。
- 同步既有测试期望：两水平与裂区分析页首项为“诊断合同”；BBD/CCD/一般全因子工程的 `schema_version` 断言更新为 5。
- 新增三条真实 Tk 回归：自定义 Factorial 分析后交互图（6 子图）、自定义 RSM 项平方和与响应面图（4 子图、轴点范围外提示）、自定义 Screening 分析与 Pareto 图（6 子图）。
- 补 E2 增补边界：父设计行内容改变、行顺序调换、run_id 改写与父来源空表均按“输入摘要/映射失效”拒绝；`_MAX_RUNS=10000` 超限在写入前拒绝且来源表不变；父设计已满秩（3/3）时增补不谎报秩提升。
- 修改设计窗口新增“预览对照”：显示操作、修改前后前 6 行（`run_id@运行序`）与运行序变化行数，并明确设定/响应列不变。变化数按 `run_id` 对比，因此只重排显示时为 0、重新随机化时为真实改动数；预览在对话框内计算，不写工作簿。
- 补齐 Distance-based 增补：`select_distance` 增加 `initial` 固定锚点参数（增补时父设计运行参与最远点判定，并排除与固定点或已选点重复的候选），`doe_augment._distance_augment` 以连续因子编码坐标复用它，`AugmentDesignDialog` 仅在响应面父设计上开放该准则并新增点类型选择。独立参考 `distance_augment` 由构建器/核验器各自手算复算（选点顺序 [0,1]、增补后最小平方间距 1）。
- 修复目标 8.1 的底部按钮可见性：修改、增加运行、选择最优设计三个窗口原本把按钮条顺序打包在伸展区之后，缩到 420×260 时按钮被挤出可视区。现统一按 `side='bottom'` 先占位，候选输入区可收缩。真实 Tk 在 960×600、420×260、360×200 下按钮全部可见。
- 修复自定义 RSM 的模型项回退缺陷：`analyze_custom_rsm` 在 `terms=None` 时把 `None` 传给 `fit_rsm`，后者按“完整二次模型”建模，于是任何只声明部分项的合法自定义设计（如仅主效应+交互）都会被判为秩亏。现默认取 `DesignSpec.model_terms`；带区组设计在分析矩阵中加入区组项。

### 旧功能回归快照（本轮实际执行）

- 冻结参考：`test_doe_bbd_minitab_parity.py test_doe_factorial_references.py test_doe_screening_references.py` → 31 passed
- `test_doe_pb.py` → 17 passed；`test_doe_dsd.py` → 93 passed
- B/C/D 非 GUI 分析与优化（`test_doe_analysis.py test_doe_factorial_anova.py test_doe_factorial_blocks.py test_doe_fractional_analysis.py test_doe_general_factorial_analysis.py test_doe_splitplot_analysis.py test_doe_optimize.py test_doe_predict.py test_doe_overlay.py test_doe_ccd_options.py`）→ 137 passed
- DOE 基础/CCD 选项/RSM/一般全因子/裂区 GUI → 14 + 24 passed；筛选 GUI 排除 200 个 PB 参数案例 → 118 passed（200 deselected）
- PB 参数案例按运行数拆进程：24→20、32→28、36→32、40→36、44→40、48→44 passed（共 200 个互不重叠案例）；整文件单进程在 `test_pb_new_run_counts_all_factor_counts_gui` 处触发 Windows Tk 原生 `0x80000003`，无汇总，不计通过
- 优化/预测/叠加 GUI → 19 passed；分数与 Foldover GUI → 17 passed
- E 非 GUI 十二文件 → 68 passed；E GUI 与生命周期 → 9 passed；帮助/菜单/G12 → 94 passed
- 工作表/工程基础（`test_worksheets.py test_sheet_context.py test_file_io.py`）→ 69 passed
- 绘图与发布修复后复跑：E 自定义三族 GUI + 自定义分析 + 最优 GUI + E 生命周期 → 30 passed；B/C/D GUI（DOE 基础、BBD、RSM、一般全因子、裂区、CCD 选项）→ 48 passed；E 非 GUI 十二文件 → 68 passed
- 测试组有重叠，不能相加；全量 pytest 未运行
- ITERATE 修复后快照：指定八文件（`test_doe_optimal.py test_doe_distance_optimal.py test_doe_optimal_augmentation.py test_doe_augment.py test_doe_optimal_gui.py test_doe_e_lifecycle.py test_doe_schema_e.py test_doe_optimal_references.py`）→ 63 passed；E 非 GUI + GUI + 工程与 Schema（22 文件）→ 204 passed（30 warnings）；B/C/D 冻结参考 + 分析与优化 + 帮助/菜单/G12 + 工作表工程基础（19 文件）→ 489 passed（8 分 38 秒）；`verify.py` 通过，`reference.json` SHA-256 仍为 `499fd66c…`

测试组有重叠，不能相加；全量 pytest 未运行。

## 回归影响

- 分析对话框的重构缺陷已修复：非自定义设计的分析结果、状态与图形恢复原行为；诊断页只统一字段语义，不改变各族统计模型。
- Schema v5 使既有 `DOE_SCHEMA_VERSION == 4` 断言更新为 5；v1–v4 工程读取路径保持原字段校验。
- Split-Plot 的 `_layout` 版本检查改为 `>= 4`，避免 v5 设计被误拒。
- 自定义设计列映射自动补 `batch_id`/`source_run_id`，供增补谱系使用。
- 自定义 RSM 允许保存欠秩候选集，但分析明确拒绝；避免候选集与最终设计混淆。

## 仍需

- 独立技术 Review（本记录不构成 APPROVE）。
- Minitab 22 对自定义/最优/增补的导出案例；当前只验证数学与工程合同。
- Mixture 距离坐标与组件约束（F）及 Mixture 增补。
- 旧版 MiniJMP 读取 v5 工程的产品行为说明。
