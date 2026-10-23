# P0 修复后全量测试失败对照（2026-10-23）

基线 JUnit：3444 个用例，3369 个无异常，73 个 failure、2 个 error。
当前 JUnit：3519 个用例，3444 个无异常，73 个 failure、2 个 error。
保留异常 ID 75，新增 0，消失 0。计数以 (测试 ID, failure/error) 对照；同一用例可能在调用通过后出现 teardown error。

完整堆栈及基线消息保存在临时证据目录 `failure-comparison.json`、`full.log`、`full.xml`。本表不将既有失败归因于本轮修复。

| 对照 | 类型 | 测试 ID | 当前异常摘要 |
|---|---|---|---|
| 保留 | failure | `tests/test_g10_tables.py::test_correlation_dialogs_reach_all_four_methods[False]` | AttributeError: 'types.SimpleNamespace' object has no attribute 'remember_columns' |
| 保留 | failure | `tests/test_g10_tables.py::test_correlation_dialogs_reach_all_four_methods[True]` | AttributeError: 'types.SimpleNamespace' object has no attribute 'remember_columns' |
| 保留 | failure | `tests/test_g11_quality_tables.py::test_plot_dialog_and_statistical_dependencies_unchanged` | AssertionError: assert 'from dialog ...     return\n' == 'from dialog ...     return\n'      Skipping 508 identical leading characters in diff, use -v to show     ogs):   +     column_roles = (('xvar', True), ('yvar', False), ('ovar', False))   +          def  |
| 保留 | failure | `tests/test_g12_tables.py::test_ci_dialog_routes_structured_table_and_keeps_original_text` | AttributeError: 'types.SimpleNamespace' object has no attribute 'remember_columns' |
| 保留 | failure | `tests/test_g1_debug_output.py::test_both_fit_apply_implementations_keep_results_reports_and_axis_labels[CorrelationDialog]` | AttributeError: 'types.SimpleNamespace' object has no attribute 'remember_columns' |
| 保留 | failure | `tests/test_g1_debug_output.py::test_both_fit_apply_implementations_keep_results_reports_and_axis_labels[LinearFitDialog]` | AttributeError: 'types.SimpleNamespace' object has no attribute 'remember_columns' |
| 保留 | failure | `tests/test_g1_debug_output.py::test_describe_apply_keeps_report_without_printing_column` | AttributeError: 'types.SimpleNamespace' object has no attribute 'remember_columns' |
| 保留 | failure | `tests/test_g1_debug_output.py::test_np_p_apply_keeps_plot_data_labels_and_report[NPDialog-100]` | AttributeError: 'types.SimpleNamespace' object has no attribute 'remember_columns' |
| 保留 | failure | `tests/test_g1_debug_output.py::test_np_p_apply_keeps_plot_data_labels_and_report[PDialog-n1]` | AttributeError: 'types.SimpleNamespace' object has no attribute 'remember_columns' |
| 保留 | failure | `tests/test_g2_basic_reports.py::test_dialog_rows_bind_original_columns_and_cleaning_counts[False]` | AttributeError: 'types.SimpleNamespace' object has no attribute 'remember_columns' |
| 保留 | failure | `tests/test_g2_basic_reports.py::test_dialog_rows_bind_original_columns_and_cleaning_counts[True]` | AttributeError: 'types.SimpleNamespace' object has no attribute 'remember_columns' |
| 保留 | failure | `tests/test_g2_basic_reports.py::test_hypothesis_dialog_raw_and_summary_routes_reach_g2_reports[False-Mean1SampleDialog-\u5355\u6837\u672c t \u68c0\u9a8c]` | AttributeError: 'types.SimpleNamespace' object has no attribute 'remember_columns' |
| 保留 | failure | `tests/test_g2_basic_reports.py::test_hypothesis_dialog_raw_and_summary_routes_reach_g2_reports[False-Mean1SampleZDialog-\u5355\u6837\u672c Z \u68c0\u9a8c]` | AttributeError: 'types.SimpleNamespace' object has no attribute 'remember_columns' |
| 保留 | failure | `tests/test_g2_basic_reports.py::test_hypothesis_dialog_raw_and_summary_routes_reach_g2_reports[False-Mean2SampleDialog-\u4e24\u72ec\u7acb\u6837\u672c t \u68c0\u9a8c]` | AttributeError: 'types.SimpleNamespace' object has no attribute 'remember_columns' |
| 保留 | failure | `tests/test_g2_basic_reports.py::test_hypothesis_dialog_raw_and_summary_routes_reach_g2_reports[False-Var1SampleDialog-\u5355\u6837\u672c\u6807\u51c6\u5dee\u68c0\u9a8c]` | AttributeError: 'types.SimpleNamespace' object has no attribute 'remember_columns' |
| 保留 | failure | `tests/test_g2_basic_reports.py::test_hypothesis_dialog_raw_and_summary_routes_reach_g2_reports[True-Mean2SampleDialog-\u4e24\u72ec\u7acb\u6837\u672c t \u68c0\u9a8c]` | AttributeError: 'types.SimpleNamespace' object has no attribute 'remember_columns' |
| 保留 | failure | `tests/test_g2_basic_reports.py::test_mean_sd_interval_rows_match_parameter_tail_and_level[True-0.05]` | AttributeError: 'types.SimpleNamespace' object has no attribute 'remember_columns' |
| 保留 | failure | `tests/test_g2_basic_reports.py::test_mean_sd_interval_rows_match_parameter_tail_and_level[True-0.1]` | AttributeError: 'types.SimpleNamespace' object has no attribute 'remember_columns' |
| 保留 | failure | `tests/test_g2_basic_reports.py::test_multi_correlation_dialog_reaches_all_four_matrix_reports` | AttributeError: 'types.SimpleNamespace' object has no attribute 'remember_columns' |
| 保留 | failure | `tests/test_g2_basic_reports.py::test_multidescribe_selected_statistics_still_control_columns` | AttributeError: 'types.SimpleNamespace' object has no attribute 'remember_columns' |
| 保留 | failure | `tests/test_g2_basic_reports.py::test_normality_table_direct_and_dialog[True]` | AttributeError: 'types.SimpleNamespace' object has no attribute 'remember_columns' |
| 保留 | failure | `tests/test_g2_basic_reports.py::test_paired_dialog_cleans_pairs_and_labels_difference` | AttributeError: 'types.SimpleNamespace' object has no attribute 'remember_columns' |
| 保留 | failure | `tests/test_g3_anova_reports.py::test_old_one_way_and_standalone_comparison_apply[TtestDialog-\u5747\u503c\u9010\u5bf9\u6bd4\u8f83]` | AttributeError: 'types.SimpleNamespace' object has no attribute 'remember_columns' |
| 保留 | failure | `tests/test_g3_anova_reports.py::test_real_nested_apply_cleans_and_preserves_validation` | AttributeError: 'types.SimpleNamespace' object has no attribute 'remember_columns' |
| 保留 | failure | `tests/test_g3_anova_reports.py::test_real_two_way_apply_cleans_and_routes_model[False]` | AttributeError: 'types.SimpleNamespace' object has no attribute 'remember_columns' |
| 保留 | failure | `tests/test_g3_anova_reports.py::test_real_two_way_apply_cleans_and_routes_model[True]` | AttributeError: 'types.SimpleNamespace' object has no attribute 'remember_columns' |
| 保留 | failure | `tests/test_g3_distribution_reports.py::test_fit_dialog_apply_cleans_selected_data_and_routes_actual_reports` | AttributeError: 'types.SimpleNamespace' object has no attribute 'remember_columns' |
| 保留 | failure | `tests/test_g4_quality_reports.py::test_all_dialog_apply_entries_keep_plots_and_variable_identity[CpkDialog-None]` | AttributeError: 'types.SimpleNamespace' object has no attribute 'remember_columns' |
| 保留 | failure | `tests/test_g4_quality_reports.py::test_all_dialog_apply_entries_keep_plots_and_variable_identity[CpkSubDialog-Use Subgrp ID Col.]` | AttributeError: 'types.SimpleNamespace' object has no attribute 'remember_columns' |
| 保留 | failure | `tests/test_g4_quality_reports.py::test_all_dialog_apply_entries_keep_plots_and_variable_identity[CpkSubDialog-Use Subgrp Size]` | AttributeError: 'types.SimpleNamespace' object has no attribute 'remember_columns' |
| 保留 | failure | `tests/test_g4_quality_reports.py::test_all_dialog_apply_entries_keep_plots_and_variable_identity[GRRDialog-AIAG (ANOVA)]` | AttributeError: 'types.SimpleNamespace' object has no attribute 'remember_columns' |
| 保留 | failure | `tests/test_g4_quality_reports.py::test_all_dialog_apply_entries_keep_plots_and_variable_identity[GRRDialog-EMP (ANOVA)]` | AttributeError: 'types.SimpleNamespace' object has no attribute 'remember_columns' |
| 保留 | failure | `tests/test_g4_quality_reports.py::test_all_dialog_apply_entries_keep_plots_and_variable_identity[GRRDialog-XBAR/R]` | AttributeError: 'types.SimpleNamespace' object has no attribute 'remember_columns' |
| 保留 | failure | `tests/test_g4_quality_reports.py::test_all_dialog_apply_entries_keep_plots_and_variable_identity[GRR_Nested_Dialog-None]` | AttributeError: 'types.SimpleNamespace' object has no attribute 'remember_columns' |
| 保留 | failure | `tests/test_g4_quality_reports.py::test_all_dialog_apply_entries_keep_plots_and_variable_identity[TIDialog-None]` | AttributeError: 'types.SimpleNamespace' object has no attribute 'remember_columns' |
| 保留 | failure | `tests/test_g4_quality_reports.py::test_quality_dialog_changes_are_only_output_statements` | AssertionError: assert 'Module(body=...e_ignores=[])' == 'Module(body=...e_ignores=[])'      Skipping 972 identical leading characters in diff, use -v to show   - [], body=[FunctionDef(name='createWidgets', args=arguments(posonlyargs=[], args=[arg(arg='self'), |
| 保留 | failure | `tests/test_g4_quality_reports.py::test_shared_modules_and_plot_implementations_remain_at_baseline` | AssertionError: assert 'Module(body=...e_ignores=[])' == 'Module(body=...e_ignores=[])'      Skipping 747 identical leading characters in diff, use -v to show   - ]), Import(names=[alias(name='json')]), Import(names=[alias(name='os')]), ImportFrom(module='path |
| 保留 | failure | `tests/test_g6_chart_presentation.py::test_normal_qq_and_residual_dialogs_reach_styled_plot_and_keep_reports` | AttributeError: 'types.SimpleNamespace' object has no attribute 'remember_columns' |
| 保留 | failure | `tests/test_g6_quality_charts.py::test_attribute_dialog_reuses_actual_plot[CDialog-C-1]` | AttributeError: 'types.SimpleNamespace' object has no attribute 'remember_columns' |
| 保留 | failure | `tests/test_g6_quality_charts.py::test_attribute_dialog_reuses_actual_plot[NPDialog-NP-100]` | AttributeError: 'types.SimpleNamespace' object has no attribute 'remember_columns' |
| 保留 | failure | `tests/test_g6_quality_charts.py::test_attribute_dialog_reuses_actual_plot[PDialog-P-n1]` | AttributeError: 'types.SimpleNamespace' object has no attribute 'remember_columns' |
| 保留 | failure | `tests/test_g6_quality_charts.py::test_attribute_dialog_reuses_actual_plot[UDialog-U-n3]` | AttributeError: 'types.SimpleNamespace' object has no attribute 'remember_columns' |
| 保留 | failure | `tests/test_g6_quality_charts.py::test_capability_dialog_uses_same_specification_plot[False]` | AttributeError: 'types.SimpleNamespace' object has no attribute 'remember_columns' |
| 保留 | failure | `tests/test_g6_quality_charts.py::test_capability_dialog_uses_same_specification_plot[True]` | AttributeError: 'types.SimpleNamespace' object has no attribute 'remember_columns' |
| 保留 | failure | `tests/test_g6_quality_charts.py::test_control_chart_direct_and_gui_preserve_limits_and_observations[True-XBAR_R-options3]` | AttributeError: 'types.SimpleNamespace' object has no attribute 'remember_columns' |
| 保留 | failure | `tests/test_g6_quality_charts.py::test_control_chart_direct_and_gui_preserve_limits_and_observations[True-XBAR_R-options5]` | AttributeError: 'types.SimpleNamespace' object has no attribute 'remember_columns' |
| 保留 | failure | `tests/test_g6_quality_charts.py::test_control_chart_direct_and_gui_preserve_limits_and_observations[True-XBAR_S-options4]` | AttributeError: 'types.SimpleNamespace' object has no attribute 'remember_columns' |
| 保留 | failure | `tests/test_g6_quality_charts.py::test_control_chart_direct_and_gui_preserve_limits_and_observations[True-XBAR_S-options6]` | AttributeError: 'types.SimpleNamespace' object has no attribute 'remember_columns' |
| 保留 | failure | `tests/test_g6_quality_charts.py::test_control_chart_direct_and_gui_preserve_limits_and_observations[True-x_mR-options0]` | AttributeError: 'types.SimpleNamespace' object has no attribute 'remember_columns' |
| 保留 | failure | `tests/test_g6_quality_charts.py::test_control_chart_direct_and_gui_preserve_limits_and_observations[True-x_mR-options1]` | AttributeError: 'types.SimpleNamespace' object has no attribute 'remember_columns' |
| 保留 | failure | `tests/test_g6_quality_charts.py::test_control_chart_direct_and_gui_preserve_limits_and_observations[True-x_mR-options2]` | AttributeError: 'types.SimpleNamespace' object has no attribute 'remember_columns' |
| 保留 | failure | `tests/test_g6_quality_charts.py::test_grr_dialog_passes_measurement_label_and_operator_facets[False]` | AttributeError: 'types.SimpleNamespace' object has no attribute 'remember_columns' |
| 保留 | failure | `tests/test_g6_quality_charts.py::test_grr_dialog_passes_measurement_label_and_operator_facets[True]` | AttributeError: 'types.SimpleNamespace' object has no attribute 'remember_columns' |
| 保留 | failure | `tests/test_g7_tables.py::test_dialog_structured_route[False]` | AttributeError: 'types.SimpleNamespace' object has no attribute 'remember_columns' |
| 保留 | failure | `tests/test_g7_tables.py::test_dialog_structured_route[True]` | AttributeError: 'types.SimpleNamespace' object has no attribute 'remember_columns' |
| 保留 | failure | `tests/test_g8_tables.py::test_g7_text_baseline_and_visible_headings[multi_dialog]` | AttributeError: 'types.SimpleNamespace' object has no attribute 'remember_columns' |
| 保留 | failure | `tests/test_g8_tables.py::test_g7_text_baseline_and_visible_headings[single_dialog]` | AttributeError: 'types.SimpleNamespace' object has no attribute 'remember_columns' |
| 保留 | failure | `tests/test_g9_tables.py::test_fixed_txt_and_every_table_reaches_viewer[Mean1SampleDialog:raw]` | AttributeError: 'types.SimpleNamespace' object has no attribute 'remember_columns' |
| 保留 | failure | `tests/test_g9_tables.py::test_fixed_txt_and_every_table_reaches_viewer[Mean1SampleZDialog:raw]` | AttributeError: 'types.SimpleNamespace' object has no attribute 'remember_columns' |
| 保留 | failure | `tests/test_g9_tables.py::test_fixed_txt_and_every_table_reaches_viewer[Mean2SampleDialog:raw]` | AttributeError: 'types.SimpleNamespace' object has no attribute 'remember_columns' |
| 保留 | failure | `tests/test_g9_tables.py::test_fixed_txt_and_every_table_reaches_viewer[Mean2SampleDialog:summary]` | AttributeError: 'types.SimpleNamespace' object has no attribute 'remember_columns' |
| 保留 | failure | `tests/test_g9_tables.py::test_fixed_txt_and_every_table_reaches_viewer[MultiVarDialog]` | AttributeError: 'types.SimpleNamespace' object has no attribute 'remember_columns' |
| 保留 | failure | `tests/test_g9_tables.py::test_fixed_txt_and_every_table_reaches_viewer[PairedTDialog]` | AttributeError: 'types.SimpleNamespace' object has no attribute 'remember_columns' |
| 保留 | failure | `tests/test_g9_tables.py::test_fixed_txt_and_every_table_reaches_viewer[TtestDialog]` | AttributeError: 'types.SimpleNamespace' object has no attribute 'remember_columns' |
| 保留 | failure | `tests/test_g9_tables.py::test_fixed_txt_and_every_table_reaches_viewer[Var1SampleDialog:raw]` | AttributeError: 'types.SimpleNamespace' object has no attribute 'remember_columns' |
| 保留 | failure | `tests/test_g9_tables.py::test_fixed_txt_and_every_table_reaches_viewer[anova_two_additive]` | AttributeError: 'types.SimpleNamespace' object has no attribute 'remember_columns' |
| 保留 | failure | `tests/test_g9_tables.py::test_fixed_txt_and_every_table_reaches_viewer[anova_two_inter]` | AttributeError: 'types.SimpleNamespace' object has no attribute 'remember_columns' |
| 保留 | failure | `tests/test_g9_tables.py::test_fixed_txt_and_every_table_reaches_viewer[ti_dialog_raw]` | AttributeError: 'types.SimpleNamespace' object has no attribute 'remember_columns' |
| 保留 | failure | `tests/test_p1_p2_statistical_fixes.py::test_real_pearson_dialog_consumers_use_correct_interval[CorrelationDialog]` | AttributeError: 'types.SimpleNamespace' object has no attribute 'remember_columns' |
| 保留 | failure | `tests/test_p1_p2_statistical_fixes.py::test_real_pearson_dialog_consumers_use_correct_interval[LinearFitDialog]` | AttributeError: 'types.SimpleNamespace' object has no attribute 'remember_columns' |
| 保留 | failure | `tests/test_p1_p2_statistical_fixes.py::test_real_pearson_dialog_consumers_use_correct_interval[MCorDialog]` | AttributeError: 'types.SimpleNamespace' object has no attribute 'remember_columns' |
| 保留 | error | `tests/test_pi_import.py::test_pi_negative_measurements_with_status_gap_are_selectable` | failed on teardown with "AssertionError: [(<class '_tkinter.TclError'>, TclError('invalid command name ".!frame200.!mtable"'), <traceback object at 0x000001EA326C0880>)] assert not [(<class '_tkinter.TclError'>, TclError('invalid command name ".!frame200.!mtab |
| 保留 | error | `tests/test_pi_import.py::test_timestamp_tag_through_reader_and_real_menu[tags0-Timestamp (time 1)]` | failed on teardown with "AssertionError: [(<class '_tkinter.TclError'>, TclError('invalid command name ".!frame200.!mtable"'), <traceback object at 0x000001EA2FFA4300>)] assert not [(<class '_tkinter.TclError'>, TclError('invalid command name ".!frame200.!mtab |
| 保留 | failure | `tests/test_result_background.py::test_report_backgrounds[multi_dialog]` | AttributeError: 'types.SimpleNamespace' object has no attribute 'remember_columns' |
| 保留 | failure | `tests/test_result_background.py::test_report_backgrounds[single_dialog]` | AttributeError: 'types.SimpleNamespace' object has no attribute 'remember_columns' |
