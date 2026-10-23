# REVIEW-015：原 70 项替身失配清单

来源：上一轮 `minijmp-p0-fix-20261023/full.xml`，按 failure 消息筛选 `remember_columns`。
本轮 `phase1.xml` 逐项运行，70 passed、0 failed、0 errors；原核心断言未删除。

| 文件 | 原失败数 |
|---|---:|
| `tests/test_g10_tables.py` | 2 |
| `tests/test_g12_tables.py` | 1 |
| `tests/test_g1_debug_output.py` | 5 |
| `tests/test_g2_basic_reports.py` | 13 |
| `tests/test_g3_anova_reports.py` | 4 |
| `tests/test_g3_distribution_reports.py` | 1 |
| `tests/test_g4_quality_reports.py` | 8 |
| `tests/test_g6_chart_presentation.py` | 1 |
| `tests/test_g6_quality_charts.py` | 15 |
| `tests/test_g7_tables.py` | 2 |
| `tests/test_g8_tables.py` | 2 |
| `tests/test_g9_tables.py` | 11 |
| `tests/test_p1_p2_statistical_fixes.py` | 3 |
| `tests/test_result_background.py` | 2 |

## 完整测试 ID

- `tests/test_g10_tables.py::test_correlation_dialogs_reach_all_four_methods[False]`
- `tests/test_g10_tables.py::test_correlation_dialogs_reach_all_four_methods[True]`
- `tests/test_g12_tables.py::test_ci_dialog_routes_structured_table_and_keeps_original_text`
- `tests/test_g1_debug_output.py::test_describe_apply_keeps_report_without_printing_column`
- `tests/test_g1_debug_output.py::test_np_p_apply_keeps_plot_data_labels_and_report[NPDialog-100]`
- `tests/test_g1_debug_output.py::test_np_p_apply_keeps_plot_data_labels_and_report[PDialog-n1]`
- `tests/test_g1_debug_output.py::test_both_fit_apply_implementations_keep_results_reports_and_axis_labels[LinearFitDialog]`
- `tests/test_g1_debug_output.py::test_both_fit_apply_implementations_keep_results_reports_and_axis_labels[CorrelationDialog]`
- `tests/test_g2_basic_reports.py::test_dialog_rows_bind_original_columns_and_cleaning_counts[False]`
- `tests/test_g2_basic_reports.py::test_dialog_rows_bind_original_columns_and_cleaning_counts[True]`
- `tests/test_g2_basic_reports.py::test_multidescribe_selected_statistics_still_control_columns`
- `tests/test_g2_basic_reports.py::test_normality_table_direct_and_dialog[True]`
- `tests/test_g2_basic_reports.py::test_mean_sd_interval_rows_match_parameter_tail_and_level[True-0.05]`
- `tests/test_g2_basic_reports.py::test_mean_sd_interval_rows_match_parameter_tail_and_level[True-0.1]`
- `tests/test_g2_basic_reports.py::test_hypothesis_dialog_raw_and_summary_routes_reach_g2_reports[False-Mean1SampleDialog-\u5355\u6837\u672c t \u68c0\u9a8c]`
- `tests/test_g2_basic_reports.py::test_hypothesis_dialog_raw_and_summary_routes_reach_g2_reports[False-Mean1SampleZDialog-\u5355\u6837\u672c Z \u68c0\u9a8c]`
- `tests/test_g2_basic_reports.py::test_hypothesis_dialog_raw_and_summary_routes_reach_g2_reports[False-Var1SampleDialog-\u5355\u6837\u672c\u6807\u51c6\u5dee\u68c0\u9a8c]`
- `tests/test_g2_basic_reports.py::test_hypothesis_dialog_raw_and_summary_routes_reach_g2_reports[False-Mean2SampleDialog-\u4e24\u72ec\u7acb\u6837\u672c t \u68c0\u9a8c]`
- `tests/test_g2_basic_reports.py::test_hypothesis_dialog_raw_and_summary_routes_reach_g2_reports[True-Mean2SampleDialog-\u4e24\u72ec\u7acb\u6837\u672c t \u68c0\u9a8c]`
- `tests/test_g2_basic_reports.py::test_paired_dialog_cleans_pairs_and_labels_difference`
- `tests/test_g2_basic_reports.py::test_multi_correlation_dialog_reaches_all_four_matrix_reports`
- `tests/test_g3_anova_reports.py::test_old_one_way_and_standalone_comparison_apply[TtestDialog-\u5747\u503c\u9010\u5bf9\u6bd4\u8f83]`
- `tests/test_g3_anova_reports.py::test_real_two_way_apply_cleans_and_routes_model[False]`
- `tests/test_g3_anova_reports.py::test_real_two_way_apply_cleans_and_routes_model[True]`
- `tests/test_g3_anova_reports.py::test_real_nested_apply_cleans_and_preserves_validation`
- `tests/test_g3_distribution_reports.py::test_fit_dialog_apply_cleans_selected_data_and_routes_actual_reports`
- `tests/test_g4_quality_reports.py::test_all_dialog_apply_entries_keep_plots_and_variable_identity[CpkDialog-None]`
- `tests/test_g4_quality_reports.py::test_all_dialog_apply_entries_keep_plots_and_variable_identity[CpkSubDialog-Use Subgrp Size]`
- `tests/test_g4_quality_reports.py::test_all_dialog_apply_entries_keep_plots_and_variable_identity[CpkSubDialog-Use Subgrp ID Col.]`
- `tests/test_g4_quality_reports.py::test_all_dialog_apply_entries_keep_plots_and_variable_identity[GRRDialog-AIAG (ANOVA)]`
- `tests/test_g4_quality_reports.py::test_all_dialog_apply_entries_keep_plots_and_variable_identity[GRRDialog-EMP (ANOVA)]`
- `tests/test_g4_quality_reports.py::test_all_dialog_apply_entries_keep_plots_and_variable_identity[GRRDialog-XBAR/R]`
- `tests/test_g4_quality_reports.py::test_all_dialog_apply_entries_keep_plots_and_variable_identity[GRR_Nested_Dialog-None]`
- `tests/test_g4_quality_reports.py::test_all_dialog_apply_entries_keep_plots_and_variable_identity[TIDialog-None]`
- `tests/test_g6_chart_presentation.py::test_normal_qq_and_residual_dialogs_reach_styled_plot_and_keep_reports`
- `tests/test_g6_quality_charts.py::test_control_chart_direct_and_gui_preserve_limits_and_observations[True-x_mR-options0]`
- `tests/test_g6_quality_charts.py::test_control_chart_direct_and_gui_preserve_limits_and_observations[True-x_mR-options1]`
- `tests/test_g6_quality_charts.py::test_control_chart_direct_and_gui_preserve_limits_and_observations[True-x_mR-options2]`
- `tests/test_g6_quality_charts.py::test_control_chart_direct_and_gui_preserve_limits_and_observations[True-XBAR_R-options3]`
- `tests/test_g6_quality_charts.py::test_control_chart_direct_and_gui_preserve_limits_and_observations[True-XBAR_S-options4]`
- `tests/test_g6_quality_charts.py::test_control_chart_direct_and_gui_preserve_limits_and_observations[True-XBAR_R-options5]`
- `tests/test_g6_quality_charts.py::test_control_chart_direct_and_gui_preserve_limits_and_observations[True-XBAR_S-options6]`
- `tests/test_g6_quality_charts.py::test_attribute_dialog_reuses_actual_plot[NPDialog-NP-100]`
- `tests/test_g6_quality_charts.py::test_attribute_dialog_reuses_actual_plot[PDialog-P-n1]`
- `tests/test_g6_quality_charts.py::test_attribute_dialog_reuses_actual_plot[CDialog-C-1]`
- `tests/test_g6_quality_charts.py::test_attribute_dialog_reuses_actual_plot[UDialog-U-n3]`
- `tests/test_g6_quality_charts.py::test_capability_dialog_uses_same_specification_plot[False]`
- `tests/test_g6_quality_charts.py::test_capability_dialog_uses_same_specification_plot[True]`
- `tests/test_g6_quality_charts.py::test_grr_dialog_passes_measurement_label_and_operator_facets[False]`
- `tests/test_g6_quality_charts.py::test_grr_dialog_passes_measurement_label_and_operator_facets[True]`
- `tests/test_g7_tables.py::test_dialog_structured_route[False]`
- `tests/test_g7_tables.py::test_dialog_structured_route[True]`
- `tests/test_g8_tables.py::test_g7_text_baseline_and_visible_headings[single_dialog]`
- `tests/test_g8_tables.py::test_g7_text_baseline_and_visible_headings[multi_dialog]`
- `tests/test_g9_tables.py::test_fixed_txt_and_every_table_reaches_viewer[Mean1SampleDialog:raw]`
- `tests/test_g9_tables.py::test_fixed_txt_and_every_table_reaches_viewer[Mean1SampleZDialog:raw]`
- `tests/test_g9_tables.py::test_fixed_txt_and_every_table_reaches_viewer[Var1SampleDialog:raw]`
- `tests/test_g9_tables.py::test_fixed_txt_and_every_table_reaches_viewer[Mean2SampleDialog:raw]`
- `tests/test_g9_tables.py::test_fixed_txt_and_every_table_reaches_viewer[Mean2SampleDialog:summary]`
- `tests/test_g9_tables.py::test_fixed_txt_and_every_table_reaches_viewer[PairedTDialog]`
- `tests/test_g9_tables.py::test_fixed_txt_and_every_table_reaches_viewer[MultiVarDialog]`
- `tests/test_g9_tables.py::test_fixed_txt_and_every_table_reaches_viewer[TtestDialog]`
- `tests/test_g9_tables.py::test_fixed_txt_and_every_table_reaches_viewer[anova_two_inter]`
- `tests/test_g9_tables.py::test_fixed_txt_and_every_table_reaches_viewer[anova_two_additive]`
- `tests/test_g9_tables.py::test_fixed_txt_and_every_table_reaches_viewer[ti_dialog_raw]`
- `tests/test_p1_p2_statistical_fixes.py::test_real_pearson_dialog_consumers_use_correct_interval[LinearFitDialog]`
- `tests/test_p1_p2_statistical_fixes.py::test_real_pearson_dialog_consumers_use_correct_interval[CorrelationDialog]`
- `tests/test_p1_p2_statistical_fixes.py::test_real_pearson_dialog_consumers_use_correct_interval[MCorDialog]`
- `tests/test_result_background.py::test_report_backgrounds[single_dialog]`
- `tests/test_result_background.py::test_report_backgrounds[multi_dialog]`
