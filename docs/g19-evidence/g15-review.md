# G19：G15 场景覆盖回填

日期：2026-10-21。读取已落盘产物回填。153个历史ID中，101项业务输入、规模及所列计时阶段精确匹配，标为本轮重测；52项保持代表替代／未单独重测。未启动任何基准、pytest或性能汇总脚本，最终完整pytest由其他任务执行，此处不推断结果。

仅更新本说明和g15-scenario-coverage.csv，39项补测JSON保持原样。CSV保留历史参数、状态、来源；actual_evidence给出精确文件及phase:正式样本数，actual_phases/unmatched_phases区分已匹配和缺失阶段，representative_evidence给出同家族代表，paired_baseline_evidence单列配对基线。每行均有精确或代表证据；相对路径以本目录为根。

## 本轮产物

- 六份statistics-F*.json：38个方法/规模组合，各3次正式样本。文件无顶层status，以完整三样本及汇总记录确认计时完成。
- data/performance.csv：26组配对，每侧3次正式样本，预热排除；find_text仅匹配find_exact，find_regex_base是额外路径。before_compat_only只对旧搜索作兼容修正。
- render-current/12场景及render-before/11场景均status=ok，同名配对，vendor仅当前版。before重放G18六模块，其余依赖来自当前集成代码，不是完整G15环境。
- supplemental/raw/39个原ID均status=ok且stage=complete，逐字段核对补测JSON一致，全部已精确回填。
- performance-summary.json及G19-performance-results.csv：165个有效阶段条目、495个阶段样本，failures为空。包含矩阵Pearson累计和总量减Pearson的派生拆分，同次构建对应多个度量，不能称495次独立调用，也不是153个历史场景全量重测数。

## 逐行证据索引

下表按家族汇总153行；具体ID、参数、规模、阶段及样本数见CSV对应行。

| 家族 | 历史ID数 | 精确重测 | 代表替代/未单独重测 | 本轮证据位置 |
| --- | ---: | ---: | ---: | --- |
| anova_pairs | 9 | 2 | 7 | [supplemental/raw/anova_pairs-n1000-p5.json](supplemental/raw/anova_pairs-n1000-p5.json)、[supplemental/raw/anova_pairs-n10000-p50.json](supplemental/raw/anova_pairs-n10000-p50.json) |
| binomial | 6 | 4 | 2 | [statistics-F04.json](statistics-F04.json)、[supplemental/raw/binomial-n1000-p1.json](supplemental/raw/binomial-n1000-p1.json) |
| calculate_d3 | 6 | 6 | 0 | [supplemental/raw/calculate_d3-n10-trial1.json](supplemental/raw/calculate_d3-n10-trial1.json)、[supplemental/raw/calculate_d3-n10-trial2.json](supplemental/raw/calculate_d3-n10-trial2.json)、[supplemental/raw/calculate_d3-n10-trial3.json](supplemental/raw/calculate_d3-n10-trial3.json)、[supplemental/raw/calculate_d3-n5-trial1.json](supplemental/raw/calculate_d3-n5-trial1.json)、[supplemental/raw/calculate_d3-n5-trial2.json](supplemental/raw/calculate_d3-n5-trial2.json)、[supplemental/raw/calculate_d3-n5-trial3.json](supplemental/raw/calculate_d3-n5-trial3.json) |
| compare_dist | 3 | 3 | 0 | [statistics-F06.json](statistics-F06.json) |
| cpk | 4 | 2 | 2 | [supplemental/raw/cpk-n1000-p1.json](supplemental/raw/cpk-n1000-p1.json)、[supplemental/raw/cpk-n100000-p1.json](supplemental/raw/cpk-n100000-p1.json) |
| csv_import | 4 | 4 | 0 | [data/performance.csv](data/performance.csv) |
| describe | 4 | 2 | 2 | [supplemental/raw/describe-n1000-p1.json](supplemental/raw/describe-n1000-p1.json)、[supplemental/raw/describe-n100000-p1.json](supplemental/raw/describe-n100000-p1.json) |
| df_combine | 4 | 4 | 0 | [data/performance.csv](data/performance.csv) |
| exports | 3 | 1 | 2 | [render-current/excel.json](render-current/excel.json) |
| find_text | 3 | 3 | 0 | [data/performance.csv](data/performance.csv) |
| fit_norm | 3 | 3 | 0 | [statistics-F06.json](statistics-F06.json) |
| grr | 3 | 3 | 0 | [statistics-F08.json](statistics-F08.json) |
| hoeffding | 4 | 4 | 0 | [statistics-F02.json](statistics-F02.json)、[supplemental/raw/hoeffding-n10000-p1.json](supplemental/raw/hoeffding-n10000-p1.json) |
| linear_fit | 3 | 3 | 0 | [statistics-F01.json](statistics-F01.json) |
| matrix_hoeffding | 4 | 4 | 0 | [statistics-F02.json](statistics-F02.json)、[supplemental/raw/matrix_hoeffding-n1000-p10.json](supplemental/raw/matrix_hoeffding-n1000-p10.json) |
| matrix_kendall | 4 | 2 | 2 | [supplemental/raw/matrix_kendall-n1000-p40.json](supplemental/raw/matrix_kendall-n1000-p40.json)、[supplemental/raw/matrix_kendall-n1000-p5.json](supplemental/raw/matrix_kendall-n1000-p5.json) |
| matrix_spearman | 4 | 2 | 2 | [supplemental/raw/matrix_spearman-n1000-p40.json](supplemental/raw/matrix_spearman-n1000-p40.json)、[supplemental/raw/matrix_spearman-n1000-p5.json](supplemental/raw/matrix_spearman-n1000-p5.json) |
| multi_fit | 5 | 2 | 3 | [render-current/matrix-tk.json](render-current/matrix-tk.json)、[render-current/matrix.json](render-current/matrix.json)、[supplemental/raw/multi_fit-n1000-p40.json](supplemental/raw/multi_fit-n1000-p40.json) |
| multi_fit_orig | 5 | 2 | 3 | [render-current/matrix-orig.json](render-current/matrix-orig.json)、[supplemental/raw/multi_fit_orig-n1000-p40.json](supplemental/raw/multi_fit_orig-n1000-p40.json) |
| multi_var | 3 | 3 | 0 | [statistics-F11.json](statistics-F11.json)、[supplemental/raw/multi_var-n3000-p3.json](supplemental/raw/multi_var-n3000-p3.json) |
| number_2Dlist | 3 | 3 | 0 | [data/performance.csv](data/performance.csv) |
| p_blaker | 3 | 3 | 0 | [statistics-F04.json](statistics-F04.json) |
| p_likelihood_ratio | 3 | 3 | 0 | [statistics-F04.json](statistics-F04.json) |
| p_sterne | 3 | 3 | 0 | [statistics-F04.json](statistics-F04.json) |
| pi_decode | 4 | 2 | 2 | [supplemental/raw/pi_decode-n1000-p20.json](supplemental/raw/pi_decode-n1000-p20.json)、[supplemental/raw/pi_decode-n100000-p20.json](supplemental/raw/pi_decode-n100000-p20.json) |
| prop_test_1sample | 6 | 4 | 2 | [statistics-F04.json](statistics-F04.json)、[supplemental/raw/prop_test_1sample-n1000-p1.json](supplemental/raw/prop_test_1sample-n1000-p1.json) |
| report_gui | 6 | 4 | 2 | [render-current/reports.json](render-current/reports.json)、[render-current/wide.json](render-current/wide.json)、[supplemental/raw/report_gui-n1000-p7.json](supplemental/raw/report_gui-n1000-p7.json)、[supplemental/raw/report_gui-n50000-p7.json](supplemental/raw/report_gui-n50000-p7.json) |
| spc_report | 4 | 1 | 3 | [render-current/spc.json](render-current/spc.json) |
| stat_table | 4 | 2 | 2 | [render-current/table.json](render-current/table.json)、[supplemental/raw/stat_table-n100000-p7.json](supplemental/raw/stat_table-n100000-p7.json) |
| table_gui | 4 | 2 | 2 | [supplemental/raw/table_gui-n1000-p20.json](supplemental/raw/table_gui-n1000-p20.json)、[supplemental/raw/table_gui-n100000-p20.json](supplemental/raw/table_gui-n100000-p20.json) |
| text_gui | 3 | 2 | 1 | [supplemental/raw/text_gui-n1000-p1.json](supplemental/raw/text_gui-n1000-p1.json)、[supplemental/raw/text_gui-n50000-p1.json](supplemental/raw/text_gui-n50000-p1.json) |
| ti_norm | 3 | 2 | 1 | [supplemental/raw/ti_norm-n1000-p1.json](supplemental/raw/ti_norm-n1000-p1.json)、[supplemental/raw/ti_norm-n50000-p1.json](supplemental/raw/ti_norm-n50000-p1.json) |
| time_series | 4 | 1 | 3 | [render-current/series.json](render-current/series.json) |
| time_series_dialog | 3 | 1 | 2 | [render-current/dialog.json](render-current/dialog.json) |
| time_series_tk | 3 | 1 | 2 | [render-current/series-tk.json](render-current/series-tk.json) |
| two_way | 3 | 3 | 0 | [statistics-F08.json](statistics-F08.json) |
| vendor_plot | 3 | 1 | 2 | [render-current/vendor.json](render-current/vendor.json)、[supplemental/raw/vendor_plot-n50000-p3.json](supplemental/raw/vendor_plot-n50000-p3.json) |
| x_mR | 4 | 2 | 2 | [supplemental/raw/x_mR-n1000-p1.json](supplemental/raw/x_mR-n1000-p1.json)、[supplemental/raw/x_mR-n100000-p1.json](supplemental/raw/x_mR-n100000-p1.json) |
| xbar_s_pooled | 3 | 2 | 1 | [supplemental/raw/xbar_s_pooled-n1000-p5.json](supplemental/raw/xbar_s_pooled-n1000-p5.json)、[supplemental/raw/xbar_s_pooled-n50000-p5.json](supplemental/raw/xbar_s_pooled-n50000-p5.json) |

## 匹配与解释边界

- 中心binomial/prop_test_1sample原场景省略event_fraction，G15默认0.5，仅n=1000由补测精确重测；statistics的x=.49N只对应非中心ID，中心n=10000/50000仍未单独重测。
- 当前multi_pop_var_test、multi_fit及multi_fit_orig默认print_out=False，与G15显式False一致；原规划关于默认输出不同的说明已纠正。multi_var的n为每组大小，100/1000匹配统计产物，3000匹配补测。
- G18固定输入仅匹配对应ID：matrix/matrix-orig为1000×20，table/spc/excel为50000行，series为100000×3，series-tk/dialog为50000×3，reports为20张100×7，wide为100×100。matrix-tk是额外Tk路径，不能替代Agg；其他规模保留代表替代。
- G18 vendor将df.copy计入replot，plot2D调用也与G15不同。因此1000×3仅作边界不同的代表，50000×3由原G15补充脚本精确重测，10000×3未单独重测；旧版空图无有效收益基线。
- 报告最后一页仅实际分页时有效，单页空操作不能当分页收益；时序含prepare构图与额外artist_build_prepared分开，不能混算。
- calculate_d3保留5/10各三个独立trial，每ID为1次冷积分及3次暖缓存；汇总同n三个冷样本合为一阶段，CSV仍逐ID引用，不把暖缓存当冷调用。
- profile/timeout为测量控制项，普通计时完成不代表profile诊断完成；两个历史profile专用ID未重采调用次数诊断。39项补测仅profile=false、timeout=180，原业务参数不变。
- G15历史138 ok、8 error、7 timeout仍单列，不是本轮失败。历史grr样本不足、矩阵未完成、单比例profile超时不外推到本轮；未精确重测的历史失败也不凭代表证据宣称修复。
- p_likelihood_ratio三个规模完成计时，但[G19-issues.md](G19-issues.md)的B-01统计定义问题仍保留，性能记录ok不等于统计正确或功能验收通过。
- G16旧样本仅为历史参照；本轮数据配对及G18 before/current只在同输入同阶段下比较，搜索兼容基线不等于原G15失败路径。详见[performance-conditions.md](performance-conditions.md)。

此次只静态核对已有记录，未运行任何基准或pytest；未额外验证真实PI、系统剪贴板、全部DPI/主题、物理显示延迟或长期泄漏。最终完整pytest结论由执行中的主任务回填。
