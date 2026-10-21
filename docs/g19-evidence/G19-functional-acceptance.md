# G19 功能证据审查与验收报告

日期：2026-10-21。工作区：`C:\Users\shaoy\Documents\Minijmp`。

**整体功能结论：FAIL。** 已确认 B-01 独立 `p_likelihood_ratio` 入口存在未解决的统计结果问题，不能因回归全绿给出 PASS。baseline、Fisher 修复相关回归、最终完整 pytest、既有真实 Tk/导出脚本验收及本轮性能记录均已完成；最终完整回归为 **2098 passed，0 failed/error/skipped，112 warnings，436.19 秒**。增加严格时序断言后的 GUI 脚本复跑已成功，主任务确认进程 exit 0；最新 JSON 记录三轴各 1,000 点、完整导出和清理成功，Tk 回调错误为空。

本子任务只读核查源码、测试、G12–G18 文档及主任务已生成的 XML/JSON/日志，没有自行运行任何测试、GUI、导出或基准。下表“断言”说明测试设计；动态完成范围按下方当前证据表区分 baseline、修复后局部回归和独立脚本，不把 baseline 当作修复后全套验证。

本子任务仅维护本文件，不修改生产代码、测试、fixture、其它证据或他人改动，不提出没有复现证据的统计语义修改。功能范围按主任务执行记录、G12 表清单及 G13–G18 的实际用户入口组织；模块逐项登记另见 `G19-module-acceptance.csv`，本文不把静态调用关联当作分支覆盖率。

## 当前动态证据与未解决问题

| 证据 | 已核对的结果 | 结论边界 |
| --- | --- | --- |
| [baseline-pytest.xml](baseline-pytest.xml)、[baseline-pytest.txt](baseline-pytest.txt) | XML 含 2096 个 testcase，failures=0、errors=0、skipped=0；日志尾部为 **2096 passed、112 warnings** | G19 修改前完整回归已通过；没有 `tests.test_g19_integration`，不能证明 Fisher 修复后最终全套状态 |
| [fisher-related-final.xml](fisher-related-final.xml)、[fisher-related-final.txt](fisher-related-final.txt) | XML 含 308 个 testcase，failures=0、errors=0、skipped=0；日志为 **308 passed、59 warnings** | 修复后局部回归通过：G16 117 项、G9 111 项、P1/P2 78 项及 G19 2 项；这些集合与 baseline 重叠，不能累加成唯一通过数，也不能据 112→59 推断警告减少 |
| [gui-export-acceptance.json](gui-export-acceptance.json)、[acceptance.py](acceptance.py) | `report.rows=1003`，TXT/copy 精确、Excel 全行核对、关闭清理均为 true；三轴各 1000 点，稳定排序/NaN=true；vendor 三曲线；Tk 回调错误为空；大表 PNG 因预计高度 36,216 超过 32,768 明确拒绝 | 主任务真实 Tk/导出脚本验收已成功；copy 写入仍被拦截。两版矩阵 axes 记录为 before/after 10/7 和 9/6，计数含布局对象，不能解释成缺失数据曲线 |
| 八张截图复核 | 主任务已确认共 8 张截图目视复核；其中记录的四张为 `report-first-page.png`、`report-small-window.png`、`small-report.png`、`multi_fit_orig-after.png`。与 G18 同名文件 SHA-256 完全一致；清理后保留的图像原件为 [首页](../g18-evidence/report-first-page.png)、[小窗口](../g18-evidence/report-small-window.png)、[小表](../g18-evidence/small-report.png)、[矩阵图](../g18-evidence/multi_fit_orig-after.png) | 本子任务按主任务确认记录，没有重复打开截图；此前四张未在通知中逐一列名，不擅自把全部生成图片标为已目视复核。G19 中字节相同的截图副本已去重；相同的完整 TXT 输出见 [G18 原件](../g18-evidence/full-report.txt) |
| [performance-summary.json](performance-summary.json)、[G19-performance-results.csv](G19-performance-results.csv) | **性能记录完成：165 个有效阶段、495 个阶段样本，failures 为空**；CSV 165 行、repeats 合计 495，与 JSON 一致 | 包含实测累计计时及拆分派生阶段；不是 495 个独立分析调用，也不是所有功能达到统一延迟门槛 |
| [performance-integrity.json](performance-integrity.json) | **严格完整性检查通过**：38 统计、26 数据配对、12 render current、11 render before、39 supplemental；exact_repeat_ids、finite_samples、planned_phases_complete 均为 true；冷场景两规模 5/10 各 3 个独立 PID | 这些是场景类别计数，不与 165 阶段或 495 阶段样本混加；没有缺失计划阶段，不代表样本相互独立或每项功能均有有效前后基线 |
| [gui-acceptance-final.log](gui-acceptance-final.log)、最新 [gui-export-acceptance.json](gui-export-acceptance.json)、更新后的 `acceptance.py` | **严格三轴复跑已通过**：断言 3 个选中变量对应 3 个轴、每轴恰好 1 条线；主任务通过 write_stdin session 70542 确认 exit 0，最新 JSON 记录三轴各 1,000 点、稳定排序/NaN、完整导出及清理成功，Tk 回调错误为空 | 本子任务读取日志/JSON，退出码来自主任务明确确认；日志正文没有单独打印退出码。八图目视复核记录保留，真实剪贴板/PI/全平台仍按既有限制披露 |
| [final-pytest.xml](final-pytest.xml)、[final-pytest.txt](final-pytest.txt) | **已完成：2098 passed，0 failed/error/skipped，112 warnings，436.19 秒**；XML 实际 2098 个 testcase，无失败/错误/跳过节点 | XML testsuite time 为 435.594 秒；436.19 秒来自 pytest 日志总耗时，两种口径分别保留。最终全绿不消除 B-01 |

baseline XML 中本文主要功能的实际收集项包括：描述/假设报告 67/74、ANOVA/卡方/分布/回归报告 49/36/30/23、质量/SPC 报告 144/73、G12 清单/报告 15/9、G13 时序 37、G14 渲染 15、G16 统计 117、G17 CSV/处理 71/123、G18 17、PI 导入/协议 17/12、数据文件 43、表格回归 130；这些项均无 failure/error/skipped。该列表只便于功能定位，不替代完整 XML，也不将结构冻结项计为独立数值验证。

**A-01 已修复并有局部通过证据：** `Prop2SDialog.apply → prop_2sample` 在 `n1=n2=10000，e1=1，e2=9999` 及对调输入下，PMF 下溢为零导致旧搜索越出支持集后不终止。按 [G19-issues.md](G19-issues.md) 和 [defect-reproduction.json](defect-reproduction.json)，修改前子进程 10 秒超时；主任务把左右搜索限制在真实支持集，保留原 `>=` 极端性比较和 CDF 组合。已阅读 `tests/test_g19_integration.py::test_fisher_underflow_search_stays_in_support`：使用真实 hypergeom、在任何越界 PMF 请求时失败，检查有限调用数、p Fisher 与 SciPy 均为 0、报告原值；XML 中 `[1]`、`[9999]` 两项均通过。仅证明该终止缺陷已覆盖，不承诺所有极小概率精度、CDF 相减或并列概率定义问题已解决。

**B-01 未解决，决定整体 FAIL：** 独立 `p_likelihood_ratio(10, .5, 8)` 返回 `0.9785156249999998`（约 `0.978515625`），通常二项 LR 定义按各支持点自身极大似然取极端集合 `{0,1,2,8,9,10}`，概率为 `2*(1+10+45)/1024 = 0.109375`。问题与独立参考见上述 issues/复现 JSON；本子任务没有重新计算或运行函数。旧 G16 差分回归保留了旧定义，相关测试通过不能推翻此数值问题。当前 GUI 正式单比例报告无该入口的生产调用者，但公开直接调用仍可能返回不符合通常 LR 定义的结果；依用户决定不改定义、不刷新基线、不添加证明错误值正确的断言。最终完整 pytest 即使全绿，也不能据此将整体结论改为 PASS。

B-02 同步导出/完整 ASCII/原始点成本已由本轮性能记录量化，见下节；B-03 真实 PI、剪贴板和人工体验保留为验证限制。它们与已确认的 B-01 数值缺陷分开记录。

## 本轮性能证据回填（已完成）

已读取上述汇总与 CSV，未重新运行任何性能脚本。165 阶段各记录 3 个阶段样本，共 495；矩阵含 `pearson_seconds` 的调用内累计实测，以及总构建减 Pearson 得到的 `axes_artists_and_report_seconds`，后者包含轴、Artist、报告和计时包装成本。这些记录存在同次分析内的累计/拆分关系，不能作为 495 次独立分析、相加推导总运行次数或统计独立样本量。

| 功能/计时阶段 | 本轮旧实现重放中位数（秒） | 当前中位数（秒） | 可支持的结论 |
| --- | ---: | ---: | --- |
| Excel 50,000×7，`export_excel` | 8.7222 | 6.2119 | 本轮该阶段观测耗时降低；当前三样本范围 6.0496–6.3235 秒，旧重放 8.0866–9.1874 秒。不外推任意规模、整套分析或全部机器 |
| 100×100 宽表，`tk_print_to_updated` | 0.2082 | 0.2081 | 基本相当，不宣称提速 |
| 50,000 点×3 时序，`tk_redraw_to_updated` | 1.6249 | 1.7742 | 当前中位数略高，但当前范围 1.3268–1.8162 与旧重放 1.5903–1.7421 秒重叠；不据此认定稳定退化，也不宣称提速 |
| 连续 20 张 100×7 报告，`tk_print_to_updated` | 5.1188 | 5.0067 | 不将小幅观测差异认定为稳定提速 |

上述四项基线均标注“本轮 G18 修改前重放”：同输入、同脚本串行比较，before 仅覆盖 G18 六模块，其余依赖仍使用当前集成代码，不能称为完整历史环境重现。CSV 中另有 G16/G17 历史优化后参照与“无有效基线”记录，不能与本轮前后比较混用，也不以不同规模代替缺失基线。当前证据没有形成稳定性能退化的结论；这不等于每个细分阶段都更快。后面三项不宣称提速，Tk update 阶段也不等于物理显示/人工输入延迟。同步 Excel、完整 ASCII 及原始点绘制的既有等待/内存成本仍保留，不由本次验收扩展架构修改。

## 证据口径及历史衔接

| 证据类型 | 能证明的范围 | 不能据此宣称 |
| --- | --- | --- |
| 独立数值参考 | 对具体输入，使用 SciPy、显式公式或已知结果核对指定统计量 | 所有分布、样本规模和统计假设都正确；所有返回字段都有独立参考 |
| 执行旧版代码、固定结果或文本 fixture 对照 | 指定案例的返回值、类型、顺序、格式及既有行为兼容 | 旧版算法本身正确；固定代表值自动成为独立数学验证 |
| AST/hash/签名、源码模式及调用次数约束 | 保护指定源码边界、公开协议和重复工作数量 | 数值独立验证、实际耗时达标或用户操作已通过 |
| 真实 Tk / Artist / 文件回读 | 控件状态、路由、曲线坐标、指定格式文件内容与清理行为 | 人工鼠标手感、物理显示延迟、外部应用兼容或跨平台全部可用 |
| monkeypatch / Mock / SimpleNamespace | 真实方法在替代依赖下的调用参数、分发及错误处理 | 完整 GUI 构造、真实剪贴板、PI SDK/服务器或浏览器打开成功 |

下表仅记录已阅读历史文档的用途，不复用其中通过数作为 G19 结果，也不累加重叠专项用例数。

| 历史材料 | 本次采用的功能约束 | 本轮限制 |
| --- | --- | --- |
| `docs/G12-table-migration-audit.md`、`tests/fixtures/g12_table_inventory.json` | 统计表、普通文本、错误框、内部矩阵分开；逻辑表模板不按构造次数或运行次数重复计数；区间报告经统一组件 | 清单完整性不代替逐表数值/导出验收；源码集合随后续新增模块变化，以当前清单核对为准 |
| `docs/G13-time-series-acceptance.md` | 原始点、稳定排序、重复时间、NaN 断线、多轴及原生导航 | 不聚合、重采样、插值或平滑；多轴布局不保证任意轴数/长标题 |
| `docs/G14-report-rendering-performance.md` | 小表 Label、大表分页、累计控件预算、完整 TXT/Excel、PNG 分配前保护、清理 | 分页不代表完整数据/ASCII 惰性物化；性能历史测量不代表本轮测得 |
| G15 临时目录中的 `G15-performance-audit.md` | F01–F11 对应的实际入口及同步计算/导出、真实 PI/剪贴板未验证的边界 | 位置：`C:\Users\shaoy\AppData\Local\Temp\Minijmp-G15-20261021-101528`；临时路径有生命周期限制，不作为仓库内永久证据或当前性能结论 |
| `docs/G16-performance-correctness.md` | 回归、方差检验、非参数相关、二项/比例、分布拟合、双因素/GRR 的旧版数值/文本对照与部分独立参考 | AST 更新和调用次数约束不能替代独立公式；旧源码依赖对应 Git 对象可用 |
| `docs/G17-data-processing-compatibility.md` | 合并、清洗、查找、CSV 的类型/索引/异常兼容；区分 MTable 和 vendor 继承入口 | pandas 3 环境的比较不等于已运行 pandas 2 环境；粘贴替代输入不是系统剪贴板验证 |
| `docs/G18-report-plot-performance.md` | 有向 Pearson 矩阵、SPC 原值/文本、Excel 样式、时序单次准备及 vendor 曲线 | 同源 Pearson 参考不是独立公式；历史截图、JUnit 和基准不替代 G19 当前结果 |

## 统计功能：入口、断言和未覆盖范围

以下定位使用 `tests/文件名.py::函数名`；参数化子项必须由主任务 JUnit 逐项确认，不能只按函数数计数。表内入口是已有测试调用的生产函数或方法；带 `apply` 的测试有一部分采用替代对话框对象，不能统称为真实菜单端到端验收。

| 用户功能 | 实际调用入口 | 已阅读的测试函数与真实断言 | 边界、异常与限制 |
| --- | --- | --- | --- |
| 描述性统计、百分位数、数据清洗说明 | `DescribeDialog.apply` / `MultiDescribeDialog.apply → describe.describe`；`Table.describe` / `DataExplore.describe` 的 DataFrame 子表路径 | `test_g2_basic_reports.py::test_describe_core_supplement_and_custom_percentiles` 核对 N/N*、表头、自定义百分位数顺序、NumPy 均值和样本 SD；`test_dialog_rows_bind_original_columns_and_cleaning_counts` 核对所选列身份、缺失计数及均值；`test_dataframe_child_table_entry_preserves_pandas_statistics` 与 `df.describe()` 比较；`test_statistics_regressions.py::test_describe_correlation_regression_known_results_smoke` 固定均值 3、方差 2.5、Q1=1.5、Q3=4.5 | 生成器不虚构 N*；空、全无效、单点返回 None 并由对话框报错（`test_insufficient_description_keeps_no_result_and_dialog_error`）。子表保留 pandas 分位数口径，不能强行统一为另一算法 |
| 正态性、均值/标准差区间 | `NormTestDialog.apply → utilities.norm_test`；`CIDialog.apply → number_list → mean_std_CIs` | `test_g2_basic_reports.py::test_normality_table_direct_and_dialog`、`test_normality_keeps_small_sample_warning_and_missing_marker`；`test_g12_tables.py::test_interval_report_keeps_txt_computation_and_exports` 比较旧实现返回值/TXT，点估计对 NumPy，并回读 Excel 数值、格式和 PNG 尾行；`test_ci_dialog_routes_structured_table_and_keeps_original_text` 走真实报告窗口 | alpha=.05/.1、尺度 1/1e-80/1e80；区间端点与旧实现对照属于回归证据，不能全部称独立公式验证；正态性小样本警告、缺失标记保留 |
| 单样本 t/Z、配对和双样本 t | 对应 `sample_test_dialog.*.apply`，直接 `t_test_1sample` / `z_test_1sample` / `paired_t_test` / `t_test_2samples` | `test_g2_hypothesis_reports.py::test_mean_reports_tail_statistics_and_intervals` 显式计算 SE、统计量、左右尾/双侧概率和区间并对照 SciPy 分布；`test_summarized_mean_paths_and_custom_df` 核对汇总输入与自定 DF；`test_two_sample_t_methods_direction_and_only_provided_ci` 核对 pooled/Welch、差值方向及区间列；`test_g2_basic_reports.py::test_hypothesis_dialog_raw_and_summary_routes_reach_g2_reports` 核对原始/汇总路由 | `test_paired_unequal_lengths_report_only_actual_pairs` 明确按 zip 的实际配对长度保留既有语义；不擅改为拒绝不等长。`test_statistics_regressions.py::test_mean_test_dialog_rejects_invalid_summary_parameters` 检查非法汇总输入报错；不能从有限 alpha/样本推断所有尾部精度 |
| 泊松分布概率与图形（不包含新增检验） | `dist_plot_dialog.displayProbDialog.apply` / `displayProb2xDialog.apply → cont_plot.cont_dist` 的 `poi` 分支 → `code/poisson.py::poisson` | `tests/test_g6_chart_presentation.py::test_probability_plot_paths_keep_existing_values_and_semantics[Poisson]` 直接调用 `poisson(5, x=3, ax=ax)`，用 `scipy.stats.poisson(5).pmf(3)` 核对返回 `px`，断言存在柱形 patch、Y 轴为 `Probability` 并完成 canvas draw；baseline 与 final XML 中该参数化项均已通过 | 此项只有 mu=5、x=3、提供 ax 的定向概率/绘图覆盖；测试未通过概率对话框或 cont_dist 的泊松分支执行，调用链来自源码核对。未独立验证累积/等尾概率、pvalue 反求分支、mu=0/非法或极端参数、非整数 x 转 int、无 ax 的返回行为；源码示例不算测试。这里是分布计算/展示，不声称有泊松均值、率或拟合优度检验功能；最终完整 XML 已确认该项通过 |
| 标准差/多样本方差检验 | `chi2_test_stdev` / `chi2_var_1sample` / `var_1sample`；`MultiVarDialog.apply → multi_pop_var_test` | `test_g2_hypothesis_reports.py::test_chi_square_sd_tails_and_legacy_reference_ranges`、`test_combined_sd_methods_and_unavailable_bonett`；`test_g16_statistics.py::test_f11_numerical_report_and_scipy` 比较旧版结果/TXT，并用 `stats.levene` 核对 Levene/Brown-Forsythe F/p，等组长时用 O’Brien transform + f_oneway 核对 F | `test_f11_degenerate` 覆盖空组集合、过小组、常数组并保持旧异常/结果；`test_f11_statistics_count` 是工作量约束。O’Brien 独立检查有等组长条件，不能泛化到全部不等长输入 |
| 单/双比例及离散检验 | `Prop1SDialog.apply → prop_test_1sample`；`Prop2SDialog.apply → prop_2sample`；直接 `p_sterne` / `p_blaker` / `binomial` | `test_g2_hypothesis_reports.py::test_single_proportion_all_methods_intervals_and_nested_chi`、`test_two_proportion_methods_difference_and_tail_columns`；`test_p1_p2_statistical_fixes.py::test_fisher_right_tail_and_other_results` 对照 hypergeom.sf 和 fisher_exact；`test_blaker_boundary_pvalues_definition_and_normal_baseline` 用组合数定义独立求和；`test_blaker_interval_coverage` 穷举指定小 n/alpha/theta 网格核对覆盖率 | `test_g16_statistics.py::test_f04_binomial_center_and_boundaries` 覆盖中心点、p=0/1、N=0 等；`test_f04_one_support_evaluation_for_entire_single_proportion` 只约束 PMF 次数。Blaker 小网格检查不是所有 n/theta 的覆盖率证明；保留 `test_blaker_internal_tie_behavior_is_outside_boundary_fix` 的既有内部并列值行为 |
| Pearson、Spearman、Kendall、Hoeffding 及矩阵 | `CorrelationDialog.apply` / `MCorDialog.apply`；`pearson_correlation` / `print_multi_col_tables`；`multi_fit` 与公开旧入口 `multi_fit_orig` | `test_g2_basic_reports.py::test_rank_single_reports_keep_raw_coefficients_and_p_values`、`test_rank_and_hoeffding_matrices_preserve_method_and_variable_mapping`；`test_p1_p2_statistical_fixes.py::test_pearson_perfect_direction`、`test_pearson_nonperfect_unchanged` 对照 Fisher-z 区间公式；`test_real_pearson_dialog_consumers_use_correct_interval`；`test_g18_performance.py::test_matrix_reuses_directional_pearson_and_only_builds_used_axes` 检查 r/p/CI/cov/N、六个有效轴、散点与逐点椭圆坐标 | G16 `test_f02_scalar_ties_constants_small_and_nonfinite` 覆盖并列秩、常量、短样本、NaN/Inf 的旧版兼容；矩阵期望调用同一个 Pearson 函数，只证明映射/复用，不是 Pearson 独立验证；`multi_fit_orig` 不据此称当前菜单调用入口 |
| OLS、正交回归、失拟及残差 | `LinearFitDialog.apply` / `OrthoFitDialog` 经 `fit_plot`；`linear_fit` / `orthogonal_fit`；Residual 路径 | `test_g3_regression_reports.py::test_ols_summary_coefficients_anova_and_diagnostics` 对照 `stats.linregress` 的斜率/截距/p，并检查 ANOVA/诊断表映射；`test_lack_of_fit_decomposes_error_not_total`；`test_orthogonal_parameter_intervals_and_residual_rows`；`test_g16_statistics.py::test_f01_numerical_and_report` 旧版全结果/TXT及显式 SSPE 求和；`test_g6_chart_presentation.py::test_regression_intervals_are_distinct_and_match_original_equations` | `test_f01_degenerate_errors`、`test_f01_mismatched_lengths` 保留旧异常类型；重复/两水平 X、大偏移、NaN/Inf、完美拟合、常量残差由专项约束。不可估计统计量的旧返回哨兵与报告 `*` 分开（`test_perfect_fit_unestimable_tests_are_not_negative_statistics`）；不把正交旧版比较说成独立数值证明 |
| 单因素、均值比较、双因素及嵌套 ANOVA | `Anova1WayDialog.apply`（多列/堆叠）、`TtestDialog.apply`、`Anova2WayDialog.apply`，对应 ANOVA 函数及 nested 路径 | `test_g3_anova_reports.py::test_one_way_values_intervals_types_and_summary` 核对结果类型、SciPy 参考及具体 SS/F/DF；`test_pairwise_p_values_letter_order_and_contract`、`test_unbalanced_letter_grouping_does_not_override_significant_pair`；`test_two_way_models_exact_fields_values_and_absent_interaction`；`test_real_two_way_apply_cleans_and_routes_model`；G16 `test_f08_two_way_balanced_and_unbalanced` 比较旧结果 | 缺单元、不平衡、NumPy 单元、退化设计及交互开关由 G16 专项；字母分组不能替代逐对显著性结果；`test_statistics_regressions.py::test_anova_dialog_rejects_insufficient_or_zero_variance_groups` 拦截不足数据；固定结果与旧模型对照不是全部设计的独立推导 |
| 列联/拟合优度卡方 | `Chi2TableDialog.apply` / `Chi2PropDialog.apply`；`chi_square` | `test_g3_chi_square_reports.py::test_fixed_before_values_types_keys_and_print_switch` 核对原值、类型、键顺序；`test_contingency_cells_expected_totals_order_and_hypotheses` 对照 `chi2_contingency(..., correction=False)` 的期望频数、行列总计及表映射；`test_statistical_edges.py::test_likelihood_ratio_including_zero_counts_matches_scipy` 核对含零计数的 LR/ Pearson | 全零边际返回 NaN 的既有语义与报告缺失标记保留；大计数、非整数代表值有回归输入，不能因此承诺所有计数均符合检验前提；不擅加连续性校正 |
| 六类分布拟合、比较及直方图拟合 | `FitDistDialog.apply → compare_dist / fit_*`；`singleHistoDialog.apply` | `test_g3_distribution_reports.py::test_all_fits_values_fields_parameter_order_and_output_switch` 检查固定参数/ABL、返回类型、frozen rv/pdf、报告说明；`test_comparison_actual_order_weights_fields_and_selection`；`test_fit_dialog_apply_cleans_selected_data_and_routes_actual_reports`；G16 `test_f06_all_fits_and_model_selection` 比较旧版六模型结果 | `test_failed_candidates_are_reported_and_excluded_without_altering_valid_fits`、`test_all_failed_candidates_explain_no_comparison_without_building_empty_table`；`test_f06_zero_density_still_raises` 保留 ValueError；小样本 AICc/权重缺失保留。拟合优度近似 p 未作分布专用校准，参数 CI 未计算，不由本审查补造 |
| 过程能力、不合格率及容忍区间 | `qc_dialog` 的 apply → `cpk` / `cpk_plot` / `ti`；分组/单值、原始/汇总路径 | `test_g4_quality_reports.py::test_capability_exact_returns`、`test_nonconformance_observed_within_overall_are_distinct`、`test_tolerance_exact_returns_and_factors`、`test_all_dialog_apply_entries_keep_plots_and_variable_identity`；`test_statistical_edges.py::test_zero_cpk_and_one_sided_intervals_are_defined` 用正态分位数公式核对零 Cpk CI；`test_negative_cpk_interval_keeps_lower_and_upper_in_order` | 组内/整体 sigma、观测不合格率与模型预期不合格率不能混同；零分母显示不可用；保留规格与控制限区别。容忍区间主要旧版/因子回归，不声称全部置信/覆盖组合有独立验证 |
| 交叉/嵌套 GRR，AIAG/EMP/Xbar-R | `qc_dialog` 对应 apply → `grr_master` / 直接 GRR 入口 | `test_g4_quality_reports.py::test_master_dispatch_interaction_and_screening_table`、`test_grr_components_and_percentage_denominators`、`test_nested_components_anova_and_history_semantics`；G16 `test_f08_grr_all_decisions_reports_and_variance_clamps`、`test_f08_retained_interaction_and_exact_threshold` 对照旧版及阈值上下相邻浮点/恰等情形；`test_statistics_regressions.py::test_two_way_anova_grr_and_spc_known_results_smoke` 固定方差分量 | Auto/On/Off、无操作者、零方差、历史值和退化设计有定向案例；完整模型/简化模型最多各一次是工作量约束；历史标准差及方差分量/百分比口径按原实现，不能用审查重新定义 |
| I/MR、Xbar-R/S、P/NP、C/U 控制图及报告 | `ctrlchart_dialog` 的取数/apply → `x_plot` / `p_np_plot` / `cu_plot` | `test_g5_spc_reports.py::test_variable_charts_report_actual_statistics_limits_and_selected_panels`、`test_attribute_reports_show_every_actual_point_and_limit`；`test_g6_quality_charts.py::test_control_chart_direct_and_gui_preserve_limits_and_observations`；`test_p1_p2_statistical_fixes.py::test_np_p_per_point_counts_limits_and_reports` 显式算各点控制限；`test_u_raw_counts_with_and_without_labels` 核对原计数、分母与标签 | 变样本量、覆盖控制限、短限值列表、缺失限值和单面板由测试约束；`test_control_chart_existing_invalid_input_failures` 保留异常类型。报告明确“当前实现未执行特殊原因规则判定”，不能把限值显示、无异常列或测试通过解释为过程受控 |

## 数据、GUI、报告及导出功能

| 用户功能 | 实际调用入口 | 已阅读的测试函数与真实断言 | 边界、异常与未覆盖限制 |
| --- | --- | --- | --- |
| 智能/高级 CSV 导入 | 文件菜单 → `MTable.importCSV`；`csv_import.detect_csv/read_csv`；原 ImportDialog 高级入口 | `test_csv_import.py::test_real_file_menu_imports_samples_without_parameter_window`、`test_real_file_menu_confirmation_advanced_and_protection`；`test_g17_csv.py::test_detection_contract_and_no_selected_reparse` 检查 delimiter/header/confirm；`test_encodings_decode_each_attempt_once` 检查 UTF-8/BOM/UTF-16/GB18030/CP1252 与解码次数；`test_file_io.py::test_import_preview_and_full_use_same_options` | `test_strict_validation_reaches_file_tail` 在 12,000 行之后放短行、长行、未闭引号/NUL，要求 detect/read 报错；`test_calls_reread_changed_files_and_choices` 防止沿用过时内容；长 ID/前导零/本地化数字需保留文本；失败、取消、无效确认选项不应部分写入。有限编码/分隔符案例不保证任意文件识别正确 |
| 数据工程保存/读取与 CSV/Excel 导出 | `TableModel.save/load`，应用/表格 `saveAs/load` | `test_file_io.py::test_pickle_chinese_mixed_roundtrip`、`test_export_chinese_mixed_roundtrip` 用 pandas 回读并 `assert_frame_equal`（中文、引号、逗号、换行、缺失和日期）；`test_table_regressions.py::test_original_project_save_open_uses_directory_and_clears_old_history` 核对 currentdir/filename、清空旧历史与数据恢复 | `test_unsupported_save_fails_without_overwriting` 检查不支持后缀抛错且旧文件字节不变。只覆盖指定文件类型/读写器；不等于断电原子性、磁盘满/网络盘恢复或任意不可信工程安全性验收 |
| 编辑、过滤、撤销/重做及选区 | `TableModel.setValueAt`；真实表格 `handleCellEntry` / `undo` / `redo` / `copy` | `test_file_io.py::test_filtered_reordered_columns_edit_correct_source_cell`；`test_table_regressions.py::test_filtered_edit_and_undo_keep_hidden_rows`、`test_undo_redo_and_history_are_independent`、`test_arrow_selection_matches_copied_cell` | 重复索引/列歧义拒绝且源数据不变；`test_filtered_bulk_changes_and_project_save_are_rejected_before_writes` 覆盖删除/粘贴/排序/改类型/保存等拦截、警告次数及不生成文件；复制替换 to_clipboard，不证明 OS 粘贴 |
| 合并、粘贴、堆叠、数字清洗 | `MTable.paste/paste_header/stackColumn → df_combine`；`utilities.number_2Dlist` | `test_g17_data_processing.py::test_combine_preserves_g15_values_dtypes_axes_and_inputs` 比较旧实现、dtype/轴及输入不变；`test_combine_preserves_numpy_scalar_dtype`；`test_real_mtable_paste_path_preserves_offset_headers_and_undo` 核对位置、表头去重及 storeCurrent；`test_real_mtable_stack_routes_shared_combine` 使用真实 Tk 表格；`test_number_cleaning_preserves_float_semantics_and_complete_rows` 比较完整行清洗与日志 | 空/零列、重复列、可空类型、带时区日期、超大整数、负偏移有定向输入；complex 转 float 的值/警告按旧语义保留。粘贴用 read_clipboard 桩；`test_paste_rejects_malformed_rows_without_partial_write` 检查畸形行不写入。不是所有 vendor 合并入口端到端测试 |
| 查找与高亮 | `MTable.findText → findRepDialog`；vendor `Table.findText → FindReplaceDialog` | `test_g17_data_processing.py::test_exact_find_matches_g15_rules_with_boolean_mask` 用逐格规则计算坐标/布尔掩码；`test_base_find_keeps_regex_and_row_column_coordinates` 核对 vendor 正则；`test_real_search_dialog_dispatch_and_highlight_redraw` 构造三类真实表格，检查对话框类型、高亮与清除；`test_pandas3_legacy_assignment_failure_is_fixed` | 空形状、缺失/空白、Unicode 大小写、重复索引/列；应用精确匹配与 vendor 正则/坐标顺序分别保留。完整搜索/替换所有交互不由 find 的断言自动覆盖 |
| PI 搜索与导入 | 文件菜单 → `PIImportDialog` 的 search/query/import；`pi_reader.search_pi_tags/read_pi_data → subprocess.run` | `test_pi_reader.py::test_read_pi_data_uses_pi_reader_json` 核对 stdin Tags、命令参数、UTF-8 strict、timeout、时间索引与缺失；`test_search_pi_tags_preserves_truncated_results`；`test_pi_import.py::test_menu_import_updates_real_table_and_statistics` 用真实表格核对列序、数字清洗、状态重置及 pickle；`test_timestamp_tag_through_reader_and_real_menu` 检查 Timestamp 名称冲突重命名 | `test_failed_or_canceled_query_preserves_sheet` 检查 error/timeout/empty/cancel/missing 后原表/filename/history 不变；`test_invalid_protocol`、`test_read_pi_data_rejects_invalid_json`、`test_read_pi_data_converts_timeout_to_user_error`；`test_large_range_requires_confirmation`；`test_long_error_keeps_buttons_visible_and_details_scrollable`。外部进程/读取器被替换或伪造，无真实 SDK、认证、服务器、Tag 权限、时区/DST 和生产容量证据 |
| 时间序列、多轴及原始曲线 | 图形菜单 → `TimeSeriesDialog.apply → prepare_time_series/time_series_plot → PlotViewer` | `test_g13_time_series.py::test_menu_entry_reaches_real_dialog` 调用真实菜单；`test_raw_values_stable_duplicates_missing_and_immutable` 逐点比对 Y、X 长度/样本序号、重复时间、NaN 断线及源表不变；`test_modes_ownership_shared_x_independent_y`、`test_many_axes_layout`；`test_real_viewer_replot_navigation_and_save` 检查工具栏、pan/zoom MouseEvent、共享 X、back、保存及旧窗口销毁 | `test_validation_preserves_previous_figure` 覆盖空选择、全 NaN、无穷、复数/布尔、非法时间/缺列/重复名；`test_integer_values_not_rounded_and_only_used_right_axes` 核对 2**60 级整数、可空大整数及稀疏右轴；G18 `test_dialog_prepares_once_and_revalidates_next_apply` 验证再次 apply 重校验。原始点保留不等于任意规模交互无延迟 |
| 基本/质量图形、矩阵及 vendor 绘图 | 现有绘图函数与 PlotViewer `replot → plotCurrent → _initFigure/plot2D` | `test_g6_chart_presentation.py::test_basic_chart_objects_and_chinese_exports`、`test_probability_plot_paths_keep_existing_values_and_semantics`、`test_both_matrix_entries_keep_pair_data_and_full_variable_names`；G6 quality 的控制限/能力/GRR 曲线测试；`test_g18_performance.py::test_vendor_viewer_creates_real_curves_all_current_paths` 检查两条曲线原始 Y、NaN 断线及色图 fallback | Artist/Agg 的轴与文字检查不等于屏幕截图逐像素一致；虚拟事件不等于物理输入。G13 `test_grouped_line_existing_behavior` 单独保护原分组线图，不将其与原始时序入口混为一项 |
| 统一统计报告、小表/大表与连续多表 | 生产者 → `StatTable → Minijmp.print → txt_viewer.add_table → TableBlock` | `test_g12_tables.py::test_all_modules_mixed_report_copy_save_scroll_clear_close_reopen` 混合 >50 表，检查对象身份、菜单/标题位置、滚动、逐表真实导出、TXT、关闭重开；`test_g14_rendering.py::test_small_100_by_7_keeps_labels_and_text` 检查 707 个原有 Label；`test_bounded_tree_reaches_last_row_and_column` 检查 1k/10k/50k×7 和 100×100 的有界条目、末行/末列 | `test_pages_keyboard_spinbox_scroll_and_no_loss` 遍历 1,003 行所有页并逐格对 display，检查快捷键、非法/越界页码；`test_twenty_tables_budget_scroll_clear_close_reopen` 检查引用释放和 idle 回调。没有长期 soak/内存泄漏或全机器性能保证；清单扫描器不是运行全部逻辑表的替代 |
| 报告 TXT 保存与复制/选区 | `txt_viewer._text_chunks/select_all/copy/save`，分页树快捷键 | G14 `test_mixed_txt_save_and_copy_preserve_legacy_text_and_selection` 普通文字/小表/分页混合，TXT 逐字符一致、Treeview 全选、分页窗口选区和普通局部选区；G12 混合报告经 Tcl 复制入口检查完整字符串 | clipboard_clear/append 或 Tcl clipboard 被拦截；G17/表格复制也替换 pandas 剪贴板入口。系统剪贴板锁定、外部 Excel/记事本粘贴、分隔符/多行转义均需人工验收；保存不存在目录时错误对话框且报告不变已有断言 |
| 报告 Excel 导出 | 表级菜单 → `stat_table.export_excel` | `test_g14_rendering.py::test_large_excel_full_precision_formats_and_menu` 回读全部 1,003 行，核对原始比例精度、整数 N、`*`、字符串公式标签、数字格式、表头、冻结窗格；G18 `test_excel_preserves_original_cells_styles_widths_and_precision` 逐单元格比较旧版值/type/format/font/alignment 与列宽；G11 逐表数值回读 | `test_excel_save_error_does_not_leave_streaming_temp_files` 检查不存在目录抛 OSError 且临时 XML 清单不变；G11 `test_export_cancel_and_failure_stay_with_shared_component` 检查共享菜单错误/取消。openpyxl 回读不是 Microsoft Excel/LibreOffice 实际显示；同步写出及完整数据内存仍存在 |
| 表格 PNG、图形 PNG/SVG/PDF | `TableBlock` 菜单 → `export_png`；PlotViewer `savePlot` | G14 `test_small_png_complete_and_huge_png_guard_before_allocation`、`test_wide_png_guard_before_allocation`、`test_png_pixel_budget_before_allocation` 验证正常文件/分配前拒绝；G13 `test_multi_axis_layout_and_native_save` 检查标签边界、三格式保存；`test_statistics_regressions.py::test_export_saves_target_axes_figure_not_current_pyplot_figure` 保护目标 Figure | PNG 有单边 32,768 像素/总量 32,000,000 像素限制，超限建议 Excel；文件大小/尺寸/非空像素不证明每个汉字视觉可读。不能要求超大 PNG 在拒绝后仍生成完整图片 |
| 菜单、对话框、帮助、主题与生命周期 | `Minijmp` 菜单回调、统计对话框构造、`help_center.open_help`、`PlotViewer.close` | `test_table_regressions.py::test_all_statistics_menu_dialogs_construct_and_close` 只验证构造/关闭；`test_menu_localization.py::test_translated_item_invokes_its_original_command` 核对回调；`test_help_center.py::test_local_html_assets_links_and_anchors_are_valid`、`test_open_help_reports_missing_topic_and_browser_failure`、`test_open_help_rejects_targets_outside_the_help_directory`；`test_statistics_regressions.py::test_plot_viewer_close_releases_owned_references_and_figure` / `test_closing_previous_plot_keeps_new_plot_reference` | 对话框能打开不等于统计 apply 成功。帮助链接静态有效、替代 browser 调用不证明当前系统浏览器实际展示；真实 Windows 主题/DPI/高对比度需人工。关闭清理有局部断言，无无限次重开/长时间泄漏验证 |
| 启动、中文路径与错误提示 | `start_minijmp`，BAT/VBS 入口、资源相对模块路径 | `test_startup.py::test_real_launcher_with_chinese_path_and_unrelated_cwd`、`test_windows_launchers_resolve_their_directory_and_propagate_exit_code`；`test_child_failure_returns_code_and_reports_error`、`test_os_error_is_visible_and_does_not_retry_another_interpreter` | 启动器测试的替代临时工程及平台条件须由 XML 确认。G12/G13 历史四失败不能预判本轮失败，后期历史通过也不能预判本轮通过；本子任务未执行真实业务启动器 |

## 不可夸大的覆盖与现有语义

1. `test_g3_computation_contracts.py::test_computation_return_and_plot_ast_matches_g3_start` 是剔除部分报告节点后的 AST/hash 比较；G5 算法冻结、G12 清单扫描、签名/旧模式检查也是结构保护。它们不得被计为数值独立验证。G16 更新过授权优化对应基线，G18 更新过三条绘图基线，哈希相等并不证明推导正确。
2. G16 的 `same_call/equal` 主要执行不可变旧 Git 源码，逐键/类型/文本比较，数值通常使用 `rel=2e-12, abs=1e-12, nan_ok=True`；这能发现兼容回归，但双方可共享缺陷。独立参考仅在明确写有 SciPy/公式/已知值断言的字段和输入上成立。
3. G17 合并旧函数快照在当前 pandas 环境执行；并非切到历史依赖环境重跑。数字清洗保留逐值 `float()` 的语义、完整行配对和现有 complex 警告，查找保留精确/正则差别；不因统一外观而更改数值或匹配规则。
4. `print_out=False` 静默与返回值、原始值/显示值/文本、Excel 数字格式、尾部方向、控制限/规格限、方差分量/百分比各有不同契约；不能用报告三位小数一致替代原始精度验证。`p=0.000` 是舍入显示，不表示严格概率为零；不可估计项维持既有缺失/哨兵处理。
5. 真实 Tk 测试也可能通过 `SimpleNamespace`、patch 文件对话框/错误框或替代外部依赖调用生产方法；逐条区分。`tests/conftest.py::tk_root` 确实创建并 withdraw Tk root，需要可用显示环境，不是全套纯无头测试。
6. 本文不是 coverage/trace 报告，也未逐行审查所有测试文件。列出的是已读真实断言及其功能映射，不保证每个 UI 选项、异常、模块内部辅助函数或第三方依赖分支均被覆盖。泛化的 `raises(Exception)`/同旧异常类型断言，只证明异常兼容，不证明用户错误文案和统计有效性。
7. G14/G17 测试中存在会启动基准子进程的测试函数；本次没有执行这些函数、collect、脚本自检或任何应用导入。性能结论完全留给主任务串行测量，不能从调用次数或历史耗时推断本轮加速。
8. `test_g8_tables.py::test_public_interface_rejects_truncated_data` 对不一致的 values/display 形状和 number_formats 要求抛出 ValueError/TypeError；这是统一表格输入边界的保护，不是统计输入有效性的完整校验。
9. 审查期间主任务新增 `tests/test_g19_integration.py` 并修复 `code/proportion_test.py`；本次已读取新增 Fisher 测试并核对两个参数化项在局部 XML 中通过，本子任务均未修改或撤销。完整生产 diff/最终源码状态仍由主任务审查，不能将 baseline 的完整通过直接归给修复后的状态。

## 已完成脚本验收与剩余人工体验清单

上面的 baseline 与局部 XML 已确认对应测试执行完成；真实 Tk/导出脚本及八图目视复核也已完成，不要求为勾选清单而重做。下列保留的是后续可选择的人工体验/外部环境清单，**未勾选不自动成为本轮阻断条件，也不要求全部实做**；本轮整体 FAIL 的明确依据是 B-01。若后续实际执行，可记录执行者、时间、环境、输入与证据路径；未做则保留限制。使用副本与非生产数据，避免覆盖用户工程或真实剪贴板内容。

- [x] 主任务真实 Tk 脚本：1,003 行报告完整 TXT 回读、拦截后的完整 copy 字符串、Excel 全行原值/格式核对、末页/小窗口截图生成、小表 PNG 导出和超大 PNG 拒绝、清空/关闭清理。
- [x] 主任务真实 Tk 脚本：三轴时序各 1,000 原始点、重复时间稳定排序/NaN 保留、窗口及图形保存；vendor 三条真实曲线和保存；未记录 Tk 回调异常。
- [x] 主任务已累计打开 8 张截图目视复核；记录的四张为 `report-first-page.png`、`report-small-window.png`、`small-report.png`、`multi_fit_orig-after.png`。对应图像原件及 G19/G18 内容相同的 TXT 输出保留在 [G18 证据目录](../g18-evidence/)。G19 的重复副本已删除；不将其扩展为所有图片、DPI/主题或物理交互验收。

- [ ] 从中文路径和无关当前目录运行实际入口，确认主窗口、资源图标、中文菜单和退出；异常应可见且返回码符合现有协议。
- [ ] 真实导入 UTF-8/GB18030/UTF-16、引号内逗号/换行、无表头、长 ID CSV；检查歧义确认/高级入口。损坏尾行、取消和无效选项应保留原工程及标题/历史。
- [ ] 完成编辑→过滤→可见单元格修改→显示全部→撤销/重做，核对隐藏行未丢失；重复标签歧义和受限批量操作应明确拦截。
- [ ] 用可追溯的小样本从菜单执行描述统计、t/Z/配对、比例、方差、卡方、回归/相关、ANOVA、分布、能力/GRR/SPC；逐项核对变量、样本数、尾部、置信水平、报告原值与已有独立参考，不凭表格外观判断计算正确。
- [ ] 检查不可估计统计量、全缺失/常量、小样本、失败模型及 SPC 未执行特殊原因规则的提示；不把“未拒绝”解读为证明假设或过程受控。
- [ ] 实际鼠标操作时序变量选择、轴模式/归属、标题、图例，保留重复时间及 NaN 断线；多轴拖动/缩放/back、重绘替换、关闭重开，观察工具栏和标签是否被遮挡。
- [ ] 用小表、宽表、大分页表、连续多表检查首页/末页/页码/键盘、横纵滚动；缩小窗口后仍能访问末行末列，清空/关闭后无回调错误。
- [ ] 备份剪贴板后，在真实系统中检查普通选区、整报告、单个分页表和数据单元格的复制；粘贴到记事本与实际 Excel，核对中文、换行、前导零及完整数据；再从外部应用粘回，核对分隔符、表头、偏移和撤销。本项不能由拦截函数的测试代签。
- [ ] 剩余外部应用体验：实际 Excel/LibreOffice 打开文件，观察精度/格式/冻结窗格和公式标签的展示；对未列入八图复核的导出图片或 SVG/PDF 做目视复核。TXT 精确回读、openpyxl 全行检查、小表 PNG 和超限拒绝已由脚本完成；相关取消/失败分支已有 baseline 测试证据，无需将其全部重新列为人工必做项。
- [ ] 在具备真实 PIReader、PI SDK、配置与授权服务器的环境，搜索/截断/Tag 选择、查询/导入、坏值/空结果、错误/超时和取消；核对时区/DST、Timestamp 同名 Tag、原工程保护、长错误可滚动。记录 SDK/reader 版本与服务器条件，不在证据中记录凭据；没有可用环境即保持未验证。
- [ ] 本机不同 Windows DPI/缩放/字体/主题下检查中文与标题、按钮、表级菜单、列宽拖动、离线帮助和浏览器打开；如交付包含其它平台，分别安排原生测试，不能由 Windows 结果代替。
- [ ] 较长使用周期内重复分析、导出、清空/关闭/重开，检查响应与资源趋势；短时对象释放断言不能代替长期泄漏验收。同步统计/Excel 的等待成本和完整 ASCII/原始时序点的内存成本按实测记录。

## 主任务结果回填与闭合条件

| 项目 | 当前状态 | 回填要求 |
| --- | --- | --- |
| G19 baseline 完整 pytest | **已完成：2096 passed，0 failed/error/skipped，112 warnings** | 已读取 baseline XML 并核对日志尾部；仅对应修复前状态 |
| Fisher 修复相关回归 | **已完成：308 passed，0 failed/error/skipped，59 warnings** | 已核对局部 XML/日志，包含两项新增下溢回归；不能替代最终完整 pytest |
| 最终完整 pytest | **已完成：2098 passed，0 failed/error/skipped，112 warnings，436.19 秒** | 已读取最终 XML/日志；之后如再改生产代码/测试，需另标证据状态，不把本结果自动外推 |
| 本文各功能对应的参数化用例 | **最终全套已完成** | 按 classname/name 对比 baseline/final：2096 个既有 ID 全部保留，仅新增两项 Fisher 下溢参数，均通过；泊松项在最终 XML 中亦通过 |
| 失败与警告比较 | **已完成：baseline/final 均无失败/错误/跳过；均 112 warnings、42 个输出分组，完整 warnings summary 正文逐字相同** | 无丢失既有 ID、无新增失败；[test-summary-final.json](test-summary-final.json) 中 warning_sections_equal=true，两侧 warning_section_sha256 均为 `9375139e1f05f13f9c9b4b9f09e19a13f7b27de6f718146ed8eca181c8826fcb`。42 为输出分组数，不等同于 42 种独立警告；局部 59 warnings 不与全套直接相减 |
| 真实 Tk/导出及截图复核 | **脚本验收及严格三轴复跑通过，主任务八图复核完成** | 已读取 JSON/脚本；剩余人工体验单列为限制，不要求重做已验收项 |
| PI / 系统剪贴板 / 其它平台 | 真实集成未验证 | 不把离线/拦截测试升级为真实外部验证；这些限制不自动等价于本轮新增缺陷或必做阻断 |
| 统计语义与数值正确性 | **B-01 未解决，整体 FAIL**；A-01 局部回归通过 | 旧 LR 公式兼容不等于正确，不修改定义；最终全绿也不覆盖此独立数值反例 |
| 本轮性能 | **已完成：165 阶段、495 阶段样本，汇总无失败** | 已读取 JSON/CSV；明确矩阵累计/派生拆分，不当作 495 次独立分析；无稳定退化证据，不宣称宽表/时序重绘/20 表提速 |

最终完整回归 XML 已解析，2098 个用例均无失败/错误/跳过，与日志完成摘要相符；baseline 的所有既有 ID 保留，仅新增两项 Fisher 下溢参数。运行源码与最终交付的固定状态归档仍由主任务掌握；共享工作区后续若修改相关代码，应另标该证据边界。GUI 脚本新增严格三轴/每轴一线断言的复跑已由主任务确认 exit 0，并有最新 JSON 成功结果；baseline/final 的完整警告摘要正文相同已由汇总哈希确认。剩余纯人工体验项目按未验证范围披露，不统一提升为交付前必须实做的条件。

本轮已经确认 baseline、Fisher 局部回归、最终完整 pytest、既有脚本 GUI/导出及性能完整性证据；新增严格时序断言的 GUI 复跑已通过，完整警告摘要一致，剩余纯人工项目保留待人工。整体功能结论为 FAIL，原因是 B-01 的公开独立 LR 入口数值问题，不能被回归通过、已完成脚本验收、性能记录无失败或未执行人工体验项掩盖。
