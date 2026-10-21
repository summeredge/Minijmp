# G19：G16/G17/G18 独立源码审查

审查日期：2026-10-21，Asia/Shanghai。目录：`C:\Users\shaoy\Documents\Minijmp`。读取时 HEAD 为 `b430f8c7c4e4870f1dc3a9242e8f2d50ba9ba231`（G18 已合入当前 main）。本审查只写本文件；不运行 Python、pytest、基准、GUI 或数值探针，不修改生产代码、测试、夹具或他人的证据文件，不执行提交、合并或回退。

## 结论与证据等级

当前代码能找到三轮报告列出的生产修复及实际消费者。未确认 G16/G17/G18 新增的生产回归；确认两项仍存在的旧统计实现问题，分别为 Fisher 搜索没有支持集终止条件、独立 LR 入口的极端性排序错误。不能把“优化保留旧行为”解释为统计方法已独立验证正确。

本文件使用以下局部分类，避免把字母误当作已执行验收：

- **A：具体生产问题**，给出输入、控制流或数学推导；另标注是否旧问题、是否触达 GUI。仍未动态复现。
- **B：保护或证据遗漏**，说明当前测试究竟断言什么，以及不能由其推断什么；不把未验证猜测列为已确认缺陷。
- **C：重复入口与保留成本**，区分真实第二实现、必要不同语义和明确范围外路径；不因代码相似就建议合并。

静态结论来自当前文件、调用位置、测试正文及固定基线源码。历史报告的 passed 数和性能比仅是原任务的记录，本次不认证当前合并工作树动态通过，也不认证分支覆盖率。

## A：生产问题

### A1 / P1：两比例 Fisher 极端输入可能使主线程搜索永不结束（旧问题）

- **位置与函数**：`code/proportion_test.py:42-60`，`prop_2sample`。第 47 行缓存观测点 PMF；第 53、58 行的两个 `while` 只比较 PMF，没有检查 `y` 是否仍在超几何支持集。
- **调用者**：`code/sample_test_dialog.py:618`，`Prop2SDialog.apply` 同步调用；用户输入计数和总数后直接进入此函数，没有后台隔离或循环取消路径。
- **具体输入与推导**：`n1=n2=10000, e1=1, e2=9999`。两组比例均非 0/1，前面的两个标准误非零，能到达 Fisher 分支。观测概率为 `10000**2 / C(20000,10000)`，远低于 float64 最小正数；浮点 PMF 下溢为 0 时，循环向右走出支持集后 PMF 仍为 0，`0 >= observed_probability` 永远成立。互换事件数对应左侧循环。同样的问题不限于这个输入。
- **影响**：大样本强差异的合法数据可卡住同步统计/GUI；不是单纯少一点性能收益。
- **归因**：已只读查看 `38b907f:code/proportion_test.py`，旧循环为 `while rv.pmf(y) >= rv.pmf(e1)`，同样没有界限。G16 缓存观测概率没有引入此问题，也没有修复它。
- **保护测试与遗漏**：`tests/test_g16_statistics.py:220-248` 的 F04 数值和 PMF 调用次数循环只检查 `p_blaker`、`p_sterne`、`p_likelihood_ratio` 以及单比例入口，不包含 `prop_2sample` 的下溢或循环界限。不能用“一次向量 PMF”断言覆盖 Fisher；Fisher 本身仍逐点调用超几何 PMF。
- **最小修复方向（未实施）**：搜索必须受真实支持集约束；随后用稳定的概率比较/尾概率保留双侧定义。只加界限可以避免挂死，但不自动证明下溢区间的 p 值精度正确。应有独立参考及有界完成的回归。
- **验证状态**：数学及源码推导；本次没有调用该输入，没有实测卡死或 SciPy 下溢输出。

### A2 / P2：独立 LR 入口在上半支持集返回中心区域概率（旧问题）

- **位置与函数**：`code/proportion_test.py:148-159`，`p_likelihood_ratio`。`p=x/n` 在所有候选点固定；`LR(i)` 使用 `min(i,n-i)`；最后选择 `LR(y) >= LR(x)`。
- **具体输入与可手算证据**：`n=10, p0=.5, x=8`，此时 `p=.8`，源码中的 `LR(i)=.4**10 * 4**min(i,10-i)`。阈值取 `min(8,2)=2`，因此选中的支持点是 `2..8`，其二项概率和为 `1-2*(1+10)/1024 = .978515625`。按每个候选点相对其自身极大似然的二项双侧 LR 排序，应选 `0,1,2,8,9,10`，概率为 `2*(1+10+45)/1024 = .109375`。这两个有理数由公式手算，未执行函数。
- **调用者与影响范围**：当前 `code/` 检索只找到定义和文件末尾注释示例，没有 GUI 生产调用者。G16 测试及统计基准是实际使用方；`prop_test_1sample` 的正式报告没有调用此 LR 函数，不能声称单比例报告的 Blaker 行受此问题影响。
- **归因**：G16 报告“保留限制与数值风险”已经声明保留 LR 原公式；这是遗留方法问题，不是向量 PMF 新回归，也不是本次可以擅自变更定义的授权。
- **保护测试与遗漏**：`test_f04_proportion_functions` 对比固定旧实现；`test_f04_individual_pmf_call_counts` 只约束调用次数。这两类检查均可保留错误公式，没有二项 LR 的独立数值预期。
- **最小修复方向（未实施）**：先明确该公开入口要承诺的 LR 定义，再按每个候选点计算统计量；用独立可手算上尾样例保护。不能只刷新旧结果夹具。
- **验证状态**：公式推导；无动态输出、无运行时间结论。

## 逐项生产修复、调用者与保护测试

下表中的“存在”均为源码存在或断言存在，不代表本次测试通过。测试简称：G16=`tests/test_g16_statistics.py`，G17-data=`tests/test_g17_data_processing.py`，G17-csv=`tests/test_g17_csv.py`，G18=`tests/test_g18_performance.py`。

### G16：统计路径

| 项目 | 当前文件/函数及调用者 | 当前实现与保护逻辑 | 保护测试及遗漏 |
| --- | --- | --- | --- |
| F01 | `code/linear_fit.py:12 linear_fit`；`linear_plot.fit_plot`、`Residual.linear_fit_resid_test` | X 水平集合、组数据和组均值各构造一次；SSPE/SSM 继续按原分组次序累加；`xi == xi` 排除 NaN 与自身的字典身份匹配；失拟自由度、零纯误差分支仍在 | G16 `test_f01_numerical_and_report`、`test_f01_degenerate_errors`、`test_f01_group_mean_work`、`test_f01_mismatched_lengths`；保留空输入/常量等旧异常，不等于新增输入有效性保证 |
| F11 | `code/chi_sq.py:264 multi_pop_var_test`；`sample_test_dialog.MultiVarDialog.apply` | 原组 mean/variance/median 复用；变换后 ANOVA 重新计算各变换组均值；报告 SD 局部复用；两组额外 F 检验路径保留 | G16 `test_f11_numerical_report_and_scipy`、`test_f11_degenerate`、`test_f11_statistics_count`；有 SciPy 独立参照，调用次数测试使用非报告路径，不能解释为全部报告依赖总调用数 |
| F02 标量 | `code/nonpara_cor.py:46 hoeffd_example`、`hoeffding`；单对相关对话框、矩阵报告入口 | 每点四个比较 mask，`count_nonzero` 计数；并列秩 1/4、1/2 权重及原 D/p 公式仍在；仍是逐点比较 N 个样本 | G16 `test_f02_scalar_ties_constants_small_and_nonfinite`、`test_f02_no_python_boolean_sum_or_repeated_comparison`；没有降为次二次算法，报告已披露 |
| F02 矩阵 | `code/fit_dialog.py:467 print_multi_col_tables`；`MCorDialog.apply` 的 Spearman/Kendall/Hoeffding 分支 | 只调用无序对加真实对角线；从已有原始 `values/p_values` 读取对称值，不从格式化文本反解 | G16 `test_f02_matrix_values_reports_and_unordered_pairs`；三方法都参数化。Pearson 不走这个共享函数，见 C1 |
| F04 二项 | `code/binomial.py:5 binomial`；`cont_plot.cont_dist`、`proportion_test.prop_test_1sample` | 一次 PMF；累计扫描耗尽有返回值；点概率支持集判断；绘图 cutoff 移出循环；保留原 `not equal p` 双尾相加含义 | G16 `test_f04_binomial_legacy`、`test_f04_binomial_center_and_boundaries`、`test_f04_binomial_probability_mode`。中心修复不是把所有旧辅助字段改为正式双侧检验 |
| F04 比例 | `code/proportion_test.py:103-203 p_blaker/_p_blaker/p_sterne/_p_sterne/p_likelihood_ratio/prop_test_1sample`；`Prop1SDialog.apply`，直接函数调用 | 独立入口与单比例共用私有计算；Blaker 空左/右尾 `default=-1/n+1` 保留；边界用 CDF/SF；单比例复用二项 PMF；调整 Blaker 仍单独走 `blakerCI.py` | G16 `test_f04_proportion_functions`、`test_f04_one_support_evaluation_for_entire_single_proportion`、`test_f04_individual_pmf_call_counts`、`test_f04_empty_tail_guards_remain`、`test_f04_sterne_and_blaker_extreme_tails`。保护 AST 只证明两个 default 存在；LR 独立正确性遗漏见 A2 |
| F04 两比例 | `code/proportion_test.py:12 prop_2sample`；`Prop2SDialog.apply` | Fisher 观测 PMF 缓存在循环外，CDF/SF 单侧路径仍在 | G16 专项未直接覆盖该循环；实际缺陷见 A1 |
| F06 | `code/dist_fit.py:15 ABL`、`:250 compare_dist`；六个拟合器，直方图 `sb_hist_dialog.apply` 等分布调用路径 | PDF 批量求值，逐值 `math.log`；AICc 最小值和相对似然总和只求一次；候选拟合异常仍捕获；全部失败使用 `min(..., default=nan)`，空权重列表不除零 | G16 `test_f06_abl_numeric_small_empty_and_nan`、`test_f06_zero_density_still_raises`、`test_f06_pdf_dispatch_count`、`test_f06_all_fits_and_model_selection`；ln(pdf) 下溢失败是明确保留行为 |
| F08 ANOVA | `code/two_way_anova.py:66 two_way_anova`；`anova_dialog.Anova2WayDialog.apply`、GRR 各入口 | 非空单元均值局部复用；完整模型仍 `SSA_SSB`，删交互仍 `SSA_SSB_simple`；空单元用长度判断，NumPy 单元不做真值判断 | G16 `test_f08_two_way_balanced_and_unbalanced`、`test_f08_cell_means_count`、`test_f08_degenerate_errors`；退化设计测试保护旧错误类型，不承诺所有设计可估计 |
| F08 GRR | `code/GRR.py:168 grr_inter`、`:184 grr_simple`、`:208 grr_anova_EMP`、`:315 grr_anova_AIAG`、`:351 grr_master`；`qc_dialog.apply`、直接入口 | Auto 的完整模型通过私有 keyword-only 参数交接；简化模型仍独立拟合；`p AB <= alpha`、零方差钳制、无操作者分支保留；显式 On/Off 仍保留原方法的完整模型/分量决策 | G16 `test_f08_grr_all_decisions_reports_and_variance_clamps`、`test_f08_grr_full_model_never_refitted`、`test_f08_direct_entrypoints`、`test_f08_no_operator`、`test_f08_retained_interaction_and_exact_threshold`；有两模式、三开关及相等阈值，不仅检查 Auto |

### G17：数据处理与 CSV

| 项目 | 当前文件/函数及调用者 | 当前实现与保护逻辑 | 保护测试及遗漏 |
| --- | --- | --- | --- |
| 合并 | `code/df_combine.py:5 df_combine`；`code/modified_table.py:349 paste`、`:375 paste_header`、`:467 stackColumn` | 按列 `Series.array` 转列表后写 object 矩阵，最终 `res.tolist()` 交给原 DataFrame 推断；df2 后写；空补丁不访问未使用的负列偏移；重新生成 RangeIndex | G17-data `test_combine_preserves_g15_values_dtypes_axes_and_inputs`、`test_combine_empty_blocks`、`test_empty_patch_does_not_validate_unused_negative_column_offset`、`test_combine_preserves_numpy_scalar_dtype`、三个真实消费者路由测试；嵌套对象证据缺口见 B1 |
| 主表查找 | `code/dialog.py:15 findRepDialog.find`；`MTable.findText` | 独立 bool mask，不向字符串列写 bool；case=False 使用 Unicode upper；纯 ASCII 空格搜索禁用；`np.nonzero` 后输出 `(列,行)` | G17-data `test_exact_find_matches_g15_rules_with_boolean_mask`、`test_pandas3_legacy_assignment_failure_is_fixed`、`test_real_search_dialog_dispatch_and_highlight_redraw`；空形状另外参数化 |
| vendor 查找 | `code/pandastable_local/dialogs.py:1404 FindReplaceDialog.find`；`core_orig.Table.findText`，由 `core.Table` 继承，包含合并预览表 | 逐列 `str.contains` 保留正则和 case 语义，按位置输出 `(行,列)`；移除 `iteritems`，不能与主表整格查找交换使用 | G17-data `test_base_find_keeps_regex_and_row_column_coordinates`、`test_find_empty_shapes`、真实查找重绘测试。无效正则的友好错误处理不在本轮声明修复内 |
| 数字清洗 | `code/utilities.py:581 number_2Dlist`；`fit_dialog.MCorDialog.apply`、`chi2_dialog.Chi2TableDialog.apply` | 每列取一次；逐标量 float；失败转 NaN；按完整有效行过滤；重复标签选择 DataFrame 时延续拒绝；Inf 和 NumPy 复数的旧语义保留 | G17-data `test_number_cleaning_preserves_float_semantics_and_complete_rows`、`test_number_cleaning_empty_and_invalid_selection`、`test_number_cleaning_keeps_numpy_complex_conversion_and_warning`；并非普适的有限实数输入校验器 |
| CSV 检测 | `code/pandastable_local/csv_import.py:34 detect_csv`；`core_orig.Table.importCSV` | 编码尝试各解码一次；四分隔符严格读取；选中记录复用；不确定编码/表头/分隔符进入确认；`read_records` 全文件行宽、NUL、引号校验仍在 | G17-csv `test_encodings_decode_each_attempt_once`、`test_detection_contract_and_no_selected_reparse`、`test_strict_validation_reaches_file_tail`、`test_empty_and_invalid_encoding_rejected`；不是只读文件头 |
| CSV 正式读取 | 同文件 `read_csv`；自动导入、`CSVPreviewDialog` 预览/确认 | 每次重新读文件并严格解析；非法表头拒绝；空串清洗一次；首值文本短路及不同文本数字资格判断；`pd.to_numeric` 后检查有效值/Inf，保留标识符和长整数 | G17-csv `test_numeric_precision_and_identifier_contract`、`test_numeric_checks_scale_with_distinct_values_per_column`、`test_invalid_confirmed_headers_still_rejected`、`test_calls_reread_changed_files_and_choices`；没有跨预览/导入缓存，符合文件可变化边界 |

### G18：报告、绘图与导出

| 项目 | 当前文件/函数及调用者 | 当前实现与保护逻辑 | 保护测试及遗漏 |
| --- | --- | --- | --- |
| Pearson 复用 | `code/linear_plot.py:18 fit_plot`、`:172 multi_fit_orig`、`:285 multi_fit`；主表 `MCorDialog.apply → multi_fit`，旧版另有直接入口 | 全有序矩阵带 alpha；`cor_res[y][x]` 与散点 X/Y 方向一致交给 fit_plot；未报告时不构建表；没有将反方向椭圆直接复用 | G18 `test_matrix_reuses_directional_pearson_and_only_builds_used_axes` 参数化两版/椭圆，比较 r/p/CI/cov/N 和椭圆逐点坐标；`test_matrix_reports_keep_original_txt` 比文本与结构 |
| 三角轴 | `code/linear_plot.py:251 create_inset_grid`；当前 multi_fit；旧版用 GridSpec，外部完整 axs 仍单独隐藏 | 当前版上三角返回 None；`multi_fit:333-354` 的绘图及轴访问均嵌在 `if x < y` 内，因此只访问有效轴；旧版显式判断 None | G18 `test_inset_grid_keeps_triangle_positions`、四变量矩阵测试；未发现空轴访问缺陷。审查中曾误读缩进，已用逐行缩进复核排除，不列为缺陷 |
| SPC | `code/control_chart.py:200 _print_spc_report`；`x_plot/p_np_plot/cu_plot` | 常量控制限归并、原始 rows 与 display 分开；点号/标签原类型仍用于 PrettyTable；统计值和控制限由调用者提供，不新增异常判定 | G18 `test_spc_report_keeps_full_text_values_and_formats`、`test_spc_formats_scalar_limits_once`；G11 的实际 chart values/limits 及原始值测试继续存在 |
| Excel | `code/stat_table.py:90 export_excel`；`TableBlock.export`，TXT viewer 的表格导出路由 | 普通 Workbook，每列三类 Cell 样式原型，copy 后赋值；公式标签强制文本；逐列宽度、B3、全部行、非有限显示值保留；没有 write-only 临时 XML 路径 | G18 `test_excel_preserves_original_cells_styles_widths_and_precision` 逐单元格比较值/类型/格式/字体/对齐；`test_excel_save_error_does_not_leave_streaming_temp_files`；布尔专项持久化缺口见 B2 |
| 时序 | `code/time_series.py:55 prepare_time_series`、`:88 time_series_plot`；`code/time_series_dialog.py:137 apply` | 原生 NumPy dtype 不装箱，扩展 dtype 走 object；重复列/重复 Y、无效时间、全缺失、Inf/complex/bool Y 校验仍在；stable 时间排序；apply 在换窗口前校验，同次 prepared 交接；下次重验 | G18 `test_prepare_keeps_native_arrays_and_exact_nullable_values`、`test_dialog_prepares_once_and_revalidates_next_apply`；G13 原始点、NaN 断线、右轴、导航和多格式导出测试继续存在。prepared 是同次内部消费者约定，非通用外部结果验证接口 |
| vendor 色图 | `code/pandastable_local/plotting.py` 八处 `mpl.colormaps.get_cmap`，包括 `getcmap:1549`；PlotViewer 重绘/直接绘图及各图种 | 已替换移除的旧 API；`getcmap` 的 Spectral 回退保留；不加版本探测包装层 | G18 `test_vendor_viewer_creates_real_curves_all_current_paths` 覆盖 replot/plotCurrent/plot2D 及有效/无效名称；八处替换不等于八类图均动态覆盖，见 B3 |
| G12/G14 保护 | `StatTable.__new__`、`export_png`、`TableBlock`、`txt_output.py` | 保留完整原值/display/str 协议、分页和 Label 预算、PNG 分配前上限；未看到新增第二套报告或导出实现 | G12 inventory/混合报告测试、G14 分页末行/完整 TXT 复制/Excel/PNG 分配前拒绝/关闭清理测试存在；本轮未执行 |

## B：保护与报告证据的遗漏

### B1：嵌套对象兼容的报告证据不足以审计具体输入

G17 报告提到额外 Categorical、Decimal、Period、Interval、嵌套对象与偏移差分；`docs/g17-evidence/extra-dtype-probe.txt` 实际只有一行 `12 additional extension/object/offset comparisons passed`，没有输入、对象形状、断言或执行源码。G17-data 的合并 kind 清单包含 mixed/nullable/dates/empty/zero_columns/duplicates/large_int，窄 dtype 另有参数化，但没有同形嵌套 list/ndarray 的明确用例。

因此无法仅凭这行日志认证 object 列中任意序列对象的赋值兼容性；`df_combine:13,16` 的列表到 NumPy object 切片转换应在需要该能力时补明确用例。**本次没有执行 NumPy 探针，不能据此宣布嵌套对象会广播失败，也不将它列为已确认回归。** 最小补充是保留有具体输入的两侧差分测试，而不是增加通用 object 转换框架。

### B2：Excel 布尔及 None/Colormap 对象检查主要是一次性证据

G18 报告把 Excel 布尔值/General 格式和色图 None/Colormap 对象列在 `review-self-checks.json`。已读的持久 G18 Excel 参数只含字符串、整数、浮点、None/NaN/Inf；vendor 专项显式断言 viridis 和无效字符串。故不能把这两项一次性自检等同于当前持久测试覆盖，更不能从 JSON 声明推断本次通过。

当前代码已有 `bool` 排除数值样式的逻辑，无足够证据认定生产错误；若这些类型是后续验收重点，最小补充应加入已有测试的数据参数。

### B3：方法比较/AST 守卫与独立正确性不能互相替代

- G16 `old()` 从固定提交加载九模块，且重新绑定旧 GRR→旧 ANOVA、旧单比例→旧 binomial，这比双方共用新实现可靠；但保留 A2 原公式也会通过旧实现差分。
- G4 `test_original_computations_signatures_and_defaults_are_unchanged` 对四个 GRR 优化函数放开函数体冻结，继续校验原参数/默认值和新增私有 keyword-only 参数；G16 数值、报告和调用次数测试接管。这是显式转移保护，不是删除全部守卫。
- G4/G11 对 `two_way_anova` 只剥除 interaction 分支的 SSE 优化块再比较其余 AST；G4/G11/G12 对 `number_2Dlist`、G4 对主表 find 有明确豁免，分别由 G17 数据/路由测试接管。不能把被豁免函数称为仍受整文件冻结保护。
- G3 继续计算 AST 哈希并与夹具比较；G18 刷新三条绘图基线不构成绘图正确性的独立证明，方向、布局及 CI 由 G18 专项承担。
- vendor 测试真实创建两条曲线并检查 NaN，但没有逐一进入八个色图调用点；不能从 API 名称已替换推断所有图种当前运行正常。

### B4：原任务完整通过记录不能相加或直接移植到 G19

G16 报告最终 2079 passed；G17 为隔离 G17 补丁快照的 1962 passed；G18 为其独立工作树的 1785 passed。三者的源码集合、测试集合和时点不同，数字有重叠。G16 报告中的共享目录 1765/3 也被 G17 明确解释为运行期间读到并行修改，而非可信旧基线。

当前 HEAD 已合入 G18，不能沿用 G18 的 `head_unchanged` 或“反向 patch check 通过”来宣称合并后的当前源码已动态通过。本文件不读取/接管其他工作者正在生成的 G19 测试结果。G19 主任务可以另行建立该证据，但不属于本审查的执行权限。

## C：重复入口核对及明确保留成本

| 入口组 | 核对结果 | 是否遗漏同类修复 |
| --- | --- | --- |
| `multi_fit` / `multi_fit_orig` | 两套布局入口均保留，统计都带 alpha，绘图均接同方向 Pearson 结果；当前 GUI 走 multi_fit。原版兼容完整外部轴数组，不能直接用 inset 布局替换 | 未发现仅修一版的遗漏；全有序 Pearson 与非参数无序对不是同一个可直接合并的实现 |
| `p_sterne` / `_p_sterne`，`p_blaker` / `_p_blaker` | 独立入口创建支持集，单比例入口交接已有支持集；实际公式在私有函数共用 | 未发现生产公式复制；`blakerCI.binom_blaker_p/limits` 是另一既有调整方法及区间路径，正式报告单列，不能因同名 Blaker 强行替换 |
| `grr_master` / AIAG / EMP / `grr_inter` / `grr_simple` | Auto 结果沿两种方法交接；直接入口 `_full_anova=None` 仍自行计算；简化模型单独拟合 | 未发现遗漏 EMP 或直接调用；GRR_xbar 和 grr_nested 算法不同，其中重复分组/均值不属于本次 crossed-ANOVA 复用承诺 |
| `MTable` / `core.Table` / `core_orig.Table` | 主表覆盖 paste/查找；vendor 基类查找仍服务预览等表。主表按偏移合并，基类 paste 替换整表 | 修复已到两个实际查找实现；不同坐标/正则语义应保留，不新增统一 helper |
| `df_combine` / 菜单 Combine / `Table.merge` | 主表三个覆盖消费者都调用共享 df_combine；菜单 `doCombine → CombineDialog.apply` 使用 pd.merge/concat，属于关系合并；继承 merge 不是该菜单路径 | 没有证据将菜单路径视为漏改的逐格实现；不因名称 merge 相同扩大范围 |
| CSV detect / preview / read / Advanced Import | 默认检测与正式导入共用严格 records；preview/read 每次重读，Advanced Import 的 pandas 路径保留单独选项语义 | 两次读是跨用户确认边界的必要重验，不是遗漏跨调用缓存 |
| `ABL` / 六拟合器 | 六种模型都用 ABL，保留各自参数估计与 AD 路径；`fit_jsu` 是非当前六模型集合的独立路径 | 未发现六模型中的标量 PDF 第二实现；不能把 AD、分布估计或其它模型推断为已优化 |
| StatTable / Excel / PNG / TXT | 结构表和字符串协议是不同消费者；Excel 仍普通工作簿，TXT/复制仍完整物化，PNG 仍尺寸保护 | 保留同步导出、全量 ASCII、所有时序原始点和 O(单元格数) 工作簿内存；这些是报告披露的成本，不是本次新增缺陷 |

## 当前源码标识与范围限制

下列是本次只读 `Get-FileHash -Algorithm SHA256` 的关键文件标识，供后续工作者核对，不是测试或内容正确性证明。共享目录可能继续变化，结论仅覆盖实际读到的版本。

| 文件（相对 code/） | SHA256 |
| --- | --- |
| proportion_test.py | `2C4CC7848FCF41BCA35248B7E500D8884DE90E6515E5AE888ABB4C42795F1C49` |
| df_combine.py | `8B14898FE94E09EFDECD669342424529A5FA12365EE83E43C52005984D52D0B3` |
| linear_plot.py | `6CE30D5B8D38182E82D4C9C441A2D85DCBE8068C5ED73EDF2E83C445FB093A9A` |
| GRR.py | `499735D9CF9DC7E9DEC41C3D5A836D67ED6088B9211580036A8B9B17B2763F20` |
| stat_table.py | `1FEB1B79F86BA3CE8B9D4630A2B0F3EA19D251EC62F8DB5B1DCA808945E2D602` |
| time_series.py | `93F589DD0C8C84DEF75CBC4D41DE0BBB81B4F5498FCF80C2B2A58C3D65A772A8` |

已做：阅读三轮报告、当前目标函数及实际消费者、专项测试正文、保护守卫及相关固定旧源码；核对重复入口；给出两项旧缺陷的具体证据。未做：测试、基准、GUI、剪贴板、Excel 实际读写、Python/NumPy 探针、coverage、数值动态复现；没有修复上述问题。

审查中对三角轴的初步判断因缩进误读被撤回；嵌套对象仅保留为输入证据遗漏。最终缺陷清单不包含这两项猜测。对于“旧实现差分通过但缺少独立统计正确性样例”的流程缺口，建议在主任务结束后运行 `$retro`。
