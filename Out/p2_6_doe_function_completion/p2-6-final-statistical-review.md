# P2-6.5 统计复核：P2-6A/B 13 项

日期：2026-10-30

范围：只读复核生产统计实现、独立数学参考测试及 GUI 调用路径。只新增本报告；并行工作者对其他文件的修改均保留。

## 结论摘要

- 13 项均能从生产计算入口追到 GUI 调用和相应 GUI 测试源码。本复核未启动 GUI。
- **计划内生产统计缺陷：S1 未发现；S2 未发现已确认的错误输出。**
- **前次 S2 证据缺口已闭合：SCR-002。**新增的 Schur 补参考逐一覆盖全部 26 组支持参数，以有效 conference 矩阵 C 为固定输入，独立核对其必要代数性质，并用 Fraction 穷举整族 b/z 候选；再将实际生产矩阵的精确 det(X'X) 与族内最大值及首个并列方案比较。该结论只证明给定有效 C 与指定 b/z 构造族内的穷举最优，不代表跨任意 DSD 矩阵、任意运行点集合或更广设计族的全局最优。未发现生产输出反例。
- feature-matrix.csv 与并行工作者新增的 p2-6-final-feature-audit.csv 已反映 P2-6 范围。SCR-002、FAC-012 在全功能矩阵仍可为 partial，同时限定的 P2-6 范围已完成；不将范围外能力缺口计成本轮未交付。

## P2-6A

### SCR-002 — 多分类 DSD 与分类组合中心点

**生产 → GUI：** `doe_dsd.py::_multi_categorical_dsd_matrix/create_dsd` → `doe_dialog.py::CreateDOE.build/create` → DSD 菜单。GUI 测试：`test_doe_screening_gui.py::test_dsd_multi_categorical_centers_alias_and_ic_gui`。

**独立参考与推导（初审发现 → 闭合）：** 初审时已有 `_reference_max_logdet` 使用生产 MATRICES，并重复候选表装配；其 3 个 D-optimal 代表组合加一个并列案例不足以排除共享构造错误。新增 `test_multi_categorical_schur_reference_covers_every_supported_combination` 不重建候选运行表，而将 C 明确作为声明输入，逐组合验证 CᵀC=qI_(m+c)、单零位、±C 折叠和编码值。由完整信息矩阵分块得到 A=2qI_m、Bᵢⱼ=2zⱼC[rⱼ,i]、Dⱼⱼ=2q+4、Dⱼₖ=2(zⱼC[rⱼ,m+k]+zₖC[rₖ,m+j]+bⱼbₖ)，故 det(X'X)=n(2q)^m det(D−BᵀA⁻¹B)，其中 h 为 C 的行数且 n=2h+2。测试用 Fraction 精确计算 c×c Schur 行列式，枚举全部 2^(2c) 个 b/z 组合，并将最大值、首个并列符号和实际 X'X 精确行列式逐一对照。生产端将 C 复制为 ±C，分类列只改指定零位对为 (z,−z)，再追加 (b,−b)；源码复核确认实际输出属于被枚举的候选族。生产 MATRICES 仍是固定 C 输入；测试的 C 性质断言使证明范围限定在各自的有效输入 C，不声称独立重建全部 Conference 表。

**边界与证据结论：** 新增 4–12 个连续因子、2–4 个二水平分类因子，排除保留旧矩阵的 4+2，共 26 组；分类中心点数须为 2^c 的倍数，完整重复须均分区组，总运行数上限 10,000。新 Schur oracle 逐一覆盖 26 组，并只证明给定有效 C 与 b/z 候选族内的精确最优及枚举顺序首个并列解。Minitab 标准序/伪中心点排列未核验。

**负例断言的精度：** 索引按实际赋值链解析：design 由截距列和 actual 拼成，因此 design 的 m+1 列对应 actual 的 m 列，即第一分类因子列；zero_rows[0] 正是该列的零位。此处确为单个零位单元翻转，保持折叠配对的另一半不变后，精确 det(X'X) 不再等于最优值。该负例由目标函数区分错误候选，但没有调用生产 validator；所以它证明该扰动不属于此族内最优解，不证明生产 validator 会拒绝该工作表。全 26 组 Schur 穷举与实际行列式比较仍独立闭合原 S2 缺口。

### SCR-003 — DSD 前向、后退及 AICc/BIC 选模

**生产 → GUI：** `doe_stepwise.py::select_dsd_stepwise`，拟合复用 `doe_screening_analysis.py::_fit` → `doe_dialog.py::AnalyzeDOE.analyze/publish_tables`。GUI 测试覆盖 Forward IC、Backward 和饱和候选模型提示，见 `test_doe_screening_gui.py::test_dsd_multi_categorical_centers_alias_and_ic_gui` 与 `::test_backward_gui_explains_saturated_default_candidate_model`。

**独立参考与推导：** `test_doe_scr003_stepwise.py` 用固定 DSD coded 矩阵独立建模，以 OLS SSE/rank/残差 df 和显式高斯似然核对路径；AICc 为 −2 log L + 2kn/(n−k−1)，BIC 为 −2 log L + k log(n)，k 计可估计秩。覆盖强层级、强制项、秩亏删除、饱和模型、区组计入 k、BIC 留 1 个残差自由度及准则不可用边界。该测试文件以 NumPy 与手算准则作比较，没有 statsmodels 导入；旧报告提到的 statsmodels 数值对照不作为本次已复核的持久化证据。

**边界：** 最多 64 个候选；AICc 在 n−k−1≤0 时不可用；秩亏项、零误差方差和饱和模型明确停止。选模后的 p 值为未校正的名义推断。

### SCR-007 — PB/DSD 混杂投影与可估性

**生产 → GUI：** `doe_screening_analysis.py::analyze_pb/analyze_dsd/_alias_projection` → `doe_dialog.py::AnalyzeDOE.publish_tables/show_alias_matrix`。GUI 将完整别名矩阵和关系表作为表格输出，并展示热图。

**独立参考与推导：** `test_doe_scr007_alias.py` 使用固定编码矩阵，核对 PB12 精确投影 −1/3、PB32 完全混杂 1、DSD 平方投影 −13/15；秩亏用删列秩差核对单项可估性。区组案例把真实区组虚拟列放进参考矩阵。

**边界：** PB 按实际矩阵分析，不构造正规 defining relation；投影表示矩阵可估性，不是因果结论。热图最多显示 64 项，完整表格仍可导出；DSD 范围受 SCR-002 限制。

### FAC-008 — GF(2) 混杂区组

**生产 → GUI：** `doe_factorial.py::create_factorial/confounded_block_effects` → `doe_dialog.py::CreateDOE` → 因子设计创建菜单。GUI 测试：`test_doe_gui.py::test_confounded_block_preview_type_iii_and_reanalysis`。

**参考与推导：** `test_doe_factorial_confounded_blocks.py` 独立按 coded 因子乘积构造区组签名；多生成元乘积按 GF(2) 对称差闭包计算。核对 2³ 单生成元形成 2 个各 4 次的等大区组、双生成元形成 4 个各 4 次的等大区组，以及生成元非法/重复拒绝。

**边界：** 2–6 个连续二水平全因子，单次、无中心点；区组数为 2^生成元数，生成元须独立。分数/一般全因子、不等大小分区、重复和中心点不支持。

### FAC-010 — 多因子两水平 Split-Plot

**生产 → GUI：** `doe_splitplot.py::create_split_plot/validate_split_plot_design`、`doe_splitplot_analysis.py::analyze_split_plot` → `doe_splitplot_dialog.py::CreateSplitPlot` 与 `doe_dialog.py::AnalyzeDOE`。GUI 节点：`test_doe_splitplot_gui.py::test_splitplot_menu_preview_analysis_save_reopen_copy_and_plot`、`::test_eight_factor_categorical_splitplot_ui_and_project_roundtrip`。

**独立参考与推导：** `tests/fixtures/doe_phase2_splitplot_reference/verify.py` 不导入生产模块，以 Fraction 正规方程分别投影区组/处理、整区均值和副区残差；按独立自由度与误差层得逐项 SS/F/p。`test_doe_splitplot_analysis.py` 比较基准和八因子结果。

**边界：** 2–8 个二水平因子，1–3 个 hard 因子且至少 1 个 easy 因子，至少 2 个完整平衡区组。hard-only 项用整区误差，其余用副区误差；零误差层只停用该层检验。不支持非平衡、部分设计、REML 或一般混合模型。

### FAC-015 — Type III 方差分析及可估性

**生产 → GUI：** `doe_factorial_anova.py::_type_iii_fit` 由 `doe_analysis.py::analyze_factorial` 和 `doe_general_factorial_analysis.py::analyze_general_factorial` 调用；Split-Plot 用 `doe_splitplot_analysis.py` 的分层误差分析 → `doe_dialog.py::AnalyzeDOE`。GUI 节点：`test_doe_gui.py::test_type_iii_gui_accepts_missing_response_and_reanalyzes`、`test_doe_general_factorial_gui.py::test_general_factorial_type_iii_gui_missing_response_roundtrip`。

**独立参考与推导：** 两水平及一般分类因子的缺失响应案例与 statsmodels `anova_lm(..., typ=3)` 对照；秩亏按完整模型和删项模型的秩差检查。Type III SS 是给定其它模型项后删去目标项的模型空间投影差；无残差 df 或有效 MSE 时不输出 F/p。

**边界：** Type III 仅用于本地支持的两水平和一般全因子入口；Split-Plot 没有 Type III 选项。不支持非平衡 Split-Plot/REML；无独立纯误差或有效误差方差时不报告相应失拟 F/p。

### RSM-009 — 连续 RSM 与混料的均值 CI、观测 PI

**生产 → GUI：** 本次核对的混料扩展为 `doe_mixture_predict.py::predict_mixture/_mixture_prediction_intervals` 和 `doe_mixture_optimize.py::optimize_mixture` → `doe_mixture_dialog.py::PredictMixture/OptimizeMixture`。GUI 节点：`test_doe_mixture_gui.py::test_mixture_v2_gui_lifecycle_uses_saved_model_and_actual_amounts`。

**独立参考与推导：** `test_doe_mixture_intervals.py::_reference` 用 Fraction 自写矩阵求逆，独立计算 Scheffé 无截距 OLS、SSE/MSE、杠杆 h0=x0'(X'X)^−1x0、SE_fit=sqrt(MSE·h0)、SE_pred=sqrt(MSE·(1+h0))；用 df=4 的 t 临界值核对 90/95/99% CI/PI 和多响应优化点区间。

**边界：** 区间把给定点当作固定点；优化器不校正选点不确定性。秩亏、零误差方差或无正残差自由度时区间不可用。当前矩阵已将 RSM-009 支持范围扩展至可估混料模型。

## P2-6B

### TAG-005 — L36 混合水平阵列

**生产 → GUI：** `doe_taguchi_arrays.py::ARRAYS/validate_array`、`doe_taguchi.py::create_taguchi` → `doe_taguchi_dialog.py::CreateTaguchi`。GUI 测试：`test_doe_taguchi_gui.py::test_l36_gui_selects_partial_columns_previews_and_creates`。

**独立参考与推导：** `test_doe_taguchi_arrays.py::test_l36_matches_official_matrix_balance_pairs_and_model_rank` 将 36×23 矩阵逐格对照固定官方阵列，另行计数列频数和所有列对频数，并核对编码列秩和主效应模型秩。

**边界：** 本次核对 L36(2^11 3^12)，不推及其他未收录目录配置。全列主效应模型 rank=36，没有残差 df；要做误差推断须重复或缩小模型。

### TAG-008 — 控制×噪声响应模型与稳健搜索

**生产 → GUI：** `doe_taguchi_analysis.py::noise_response_model/noise_robustness` → `doe_taguchi_analysis_dialog.py::AnalyzeTaguchi/NoiseResponseModelTaguchi`。GUI 测试：`test_doe_taguchi_models_gui.py::test_noise_response_model_gui_fits_selected_interaction_and_mean_range`。

**独立参考与推导：** `test_doe_taguchi_response_models.py::test_noise_response_model_matches_independent_ols_and_equal_condition_search` 用 statsmodels OLS 核系数、残差、SE 和 SSE；再直接枚举控制与噪声组合，按等权核条件均值、噪声总体方差，并加残差 MSE 得预测方差。

**边界：** 静态无 signal，控制/噪声因子均二水平，噪声条件等权，最多 20,000 个控制组合。秩亏、饱和或无正误差方差时不推荐最优设置；不支持自定义噪声概率。

### TAG-009 — 模型设定预测、最优设置和确认试验

**生产 → GUI：** `doe_taguchi_analysis.py::_fit_taguchi_model/predict_taguchi_model/_model_target_settings/best_settings/create_confirmation_frame` → `doe_taguchi_analysis_dialog.py::AnalyzeTaguchi/BestTaguchi`。GUI 测试：`test_doe_taguchi_models_gui.py::test_taguchi_model_terms_ci_specified_prediction_and_confirmation_sheet`。

**独立参考与推导：** `test_doe_taguchi_response_models.py` 用 statsmodels Treatment 对比核交互模型拟合、df、均值 CI 和指定设置预测；另测混杂拒绝、饱和模型、枚举搜索与确认表。`test_doe_taguchi_references.py` 用手算边际均值核并列组合和确定性选择。

**边界：** 交互模型搜索只支持静态目标均值；水平组合最多 20,000。CI 是普通 OLS 固定点区间，不校正选择偏差；动态交互、饱和或零误差方差不提供相应推断。

### FAC-012 — 正规分数设计与 PB Foldover

**生产 → GUI：** `doe_foldover.py::create_foldover/foldover_summary`、`doe_pb_foldover.py::create_pb_foldover/pb_foldover_summary` → `doe_foldover_dialog.py::FoldoverDOE`。GUI 节点：`test_doe_foldover_gui.py::test_multi_factor_foldover_preview_create_and_reopen`。

**独立参考与推导：** 正规分数设计以冻结 D=ABC 点集核全因子/单因子翻转后的 defining relation、秩和别名组。PB fixture verifier 不导入生产 DOE 模块，重建 12/20/24/28/32/36/40/44/48 运行矩阵，核全因子与单因子翻转、实际秩及完全/部分混杂变化；另有多因子子集的列变换测试。

**边界：** 正规 3–6 因子分数设计与 PB 12–48；一次追加全因子或任意非空子集。PB 限连续二水平、无中心点/区组、单批次；不支持 Split-Plot 或连续多批 Foldover。PB 按实际投影分析，不报告正规分辨度数字。

### MIX-005 — Mixture v2 总量/过程变量交叉模型

**生产 → GUI：** `doe_mixture_designs.py::create_mixture_design`、`doe_mixture_model.py::MixtureTermModel`、`doe_mixture_analysis.py::analyze_mixture` → `doe_mixture_dialog.py::CreateMixtureDesign/AnalyzeMixtureDesign/PredictMixture/OptimizeMixture`。GUI 测试：`test_doe_mixture_gui.py::test_mixture_v2_gui_lifecycle_uses_saved_model_and_actual_amounts`。

**独立参考与推导：** `tests/fixtures/doe_phase2_p4bc_reference/verify.py` 用标准库构造混料/过程/总量交叉和显式 15 列模型行，独立求秩、拟合与预测；`test_doe_phase2_p4bc_mixture.py` 核对 72×15、rank=15、df=57、条件数、系数、SSE、预测及 actual_amount=T*x。

**边界：** 2–4 组分、最多 3 个过程变量及一个正总量变量；总量支持 2–3 个水平并与声明混料点/过程水平完整交叉。更高阶总量交互和超出 Mixture v2 合同的配置不在范围。

### GEN-006 — 固定运行数 D-optimal Improve

**生产 → GUI：** `doe_augment.py::improve_fixed_size` 调用 `doe_optimal.py::improve_fixed_size` → `doe_optimal_dialog.py::ImproveDesignDialog`。GUI 测试：`test_doe_optimal_improvement_gui.py::test_improve_operation_preview_create_save_reopen_and_analyze`。

**独立参考与推导：** `test_doe_optimal_improvement.py::test_factorial_improvement_matches_independent_exact_candidate_enumeration` 穷举候选替换并用整数 det(X'X) 核最优选择；RSM 案例独立构建六列矩阵核 rank/logdet。其他测试覆盖锁定/已执行行、响应/实测值保护、同 seed 并列、无改善和谱系篡改。

**边界：** 自定义 Factorial/RSM、父设计满秩、无区组；维持运行数，只替换未执行且可替换的运行。属于受限单点局部交换，不保证全局最优；最多 100 轮/200,000 次评价，logdet 比较要求提升超过 1e−12。

## 缺陷分级与验证归属

- **计划内 S1：无。计划内 S2 生产行为缺陷：无已确认项；SCR-002 原 S2 证据缺口已按上述 Schur oracle 闭合。**负例仅未覆盖生产 validator 的拒绝行为，不影响族内 D-optimal 最优性证明。
- **主代理执行结果：**非 GUI 完整批次 1,412 passed、13 warnings、0 failed、0 skipped；GUI 18 个常规文件150节点及Screening 320节点均通过，精确执行清单见最终报告。新增 Schur oracle 的 `final-dsd-independent.log` 记录 26 passed、144 deselected、1.97 秒；XML 记录 26 个用例、0 failures/errors/skips、1.963 秒。完整命令和其余分组仍由主代理最终报告索引。
- 本子任务没有重跑新增节点、GUI 或完整批次。此前发起的窄范围定向尝试未取得最终汇总，不计为通过/失败证据；本报告以主代理日志/XML为执行证据，并独立审阅测试实现与公式。
- 本次 closure 的工作树 diff 仅为 `tests/test_doe_dsd_multi_categorical.py` 中新增参考测试；未改生产源码。
- 并行工作者在本次复核期间更新了 feature-matrix.csv、DOE 帮助和 Out/p2_6_doe_function_completion/ 审计/GUI证据；这些文件均保留未改。
