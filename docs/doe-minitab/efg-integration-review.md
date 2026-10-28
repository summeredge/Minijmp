# E+F+G 合并后集成审查

状态：`EFG_INTEGRATION_READY_FOR_REVIEW`

## 基线与边界

- 本地 `main` HEAD：`7392ac9cef74ea84c9dfb1d44485d36137ed6631`；工作区开始时干净，当前修复尚未提交。
- 未重新执行 E/F/G 合并、未重做先前独立数学 Review；未推送、发布或启动 H。
- 本次代码和验证针对 HEAD 上的工作区修改，并非仅引用 HEAD 历史测试。

## E/F/G 合并文件清单

以下为 `c3720d2737f44ad130d8b61cd07ae31073073c2d` 到当前 HEAD 的实际 Git 变更（A 新增，M 修改）：

- `M	.agent-memory/MEMORY.md`
- `M	.agent-memory/logs/2026-10-28.md`
- `M	code/MiniJMP.py`
- `A	code/doe_augment.py`
- `M	code/doe_core.py`
- `A	code/doe_custom.py`
- `A	code/doe_custom_analysis.py`
- `A	code/doe_custom_dialog.py`
- `A	code/doe_diagnostics.py`
- `M	code/doe_dialog.py`
- `A	code/doe_mixture.py`
- `A	code/doe_mixture_analysis.py`
- `A	code/doe_mixture_constraints.py`
- `A	code/doe_mixture_designs.py`
- `A	code/doe_mixture_dialog.py`
- `A	code/doe_mixture_model.py`
- `A	code/doe_mixture_optimize.py`
- `A	code/doe_mixture_plots.py`
- `A	code/doe_mixture_predict.py`
- `A	code/doe_modify.py`
- `A	code/doe_optimal.py`
- `A	code/doe_optimal_design.py`
- `A	code/doe_optimal_dialog.py`
- `M	code/doe_rsm.py`
- `M	code/doe_splitplot.py`
- `A	code/doe_taguchi.py`
- `A	code/doe_taguchi_analysis.py`
- `A	code/doe_taguchi_analysis_dialog.py`
- `A	code/doe_taguchi_arrays.py`
- `A	code/doe_taguchi_dialog.py`
- `A	code/doe_taguchi_sn.py`
- `M	code/worksheets.py`
- `M	docs/CHANGELOG_DEV.md`
- `M	docs/MENU_TRANSLATION.md`
- `M	docs/doe-minitab/README.md`
- `M	docs/doe-minitab/acceptance.md`
- `M	docs/doe-minitab/feature-matrix.csv`
- `A	docs/doe-minitab/mixture-reference-validation.md`
- `A	docs/doe-minitab/optimal-reference-validation.md`
- `M	docs/doe-minitab/roadmap.md`
- `M	docs/doe-minitab/sources.md`
- `A	docs/doe-minitab/taguchi-reference-validation.md`
- `A	docs/doe-minitab/work-package-e-closeout.md`
- `A	docs/doe-minitab/work-package-f-closeout.md`
- `A	docs/doe-minitab/work-package-f-integration-plan.md`
- `A	docs/doe-minitab/work-package-g-closeout.md`
- `M	help/assets/search-index.js`
- `M	help/help-map.json`
- `M	help/pages/doe.html`
- `A	tests/fixtures/doe_mixture_reference/README.md`
- `A	tests/fixtures/doe_mixture_reference/build_reference.py`
- `A	tests/fixtures/doe_mixture_reference/manifest.json`
- `A	tests/fixtures/doe_mixture_reference/reference.json`
- `A	tests/fixtures/doe_mixture_reference/verify.py`
- `A	tests/fixtures/doe_optimal_reference/build_reference.py`
- `A	tests/fixtures/doe_optimal_reference/manifest.json`
- `A	tests/fixtures/doe_optimal_reference/reference.json`
- `A	tests/fixtures/doe_optimal_reference/verify.py`
- `A	tests/fixtures/doe_taguchi_reference/cases.json`
- `A	tests/fixtures/doe_taguchi_reference/l16_4_5.csv`
- `A	tests/fixtures/doe_taguchi_reference/l18_2_1_3_7.csv`
- `A	tests/fixtures/doe_taguchi_reference/l25_5_6.csv`
- `A	tests/fixtures/doe_taguchi_reference/l4_2_3.csv`
- `A	tests/fixtures/doe_taguchi_reference/l8_2_7.csv`
- `A	tests/fixtures/doe_taguchi_reference/l9_3_4.csv`
- `A	tests/fixtures/doe_taguchi_reference/manifest.json`
- `M	tests/fixtures/g12_table_inventory.json`
- `A	tests/test_doe_augment.py`
- `M	tests/test_doe_bbd_gui.py`
- `A	tests/test_doe_custom_factorial.py`
- `A	tests/test_doe_custom_gui.py`
- `A	tests/test_doe_custom_rsm.py`
- `A	tests/test_doe_custom_screening.py`
- `A	tests/test_doe_diagnostics_contract.py`
- `A	tests/test_doe_distance_optimal.py`
- `A	tests/test_doe_e_lifecycle.py`
- `M	tests/test_doe_factorial_schema.py`
- `M	tests/test_doe_general_factorial_gui.py`
- `M	tests/test_doe_gui.py`
- `A	tests/test_doe_mixture_anova.py`
- `A	tests/test_doe_mixture_centroid.py`
- `A	tests/test_doe_mixture_constraints.py`
- `A	tests/test_doe_mixture_gui.py`
- `A	tests/test_doe_mixture_lattice.py`
- `A	tests/test_doe_mixture_model.py`
- `A	tests/test_doe_mixture_optimize.py`
- `A	tests/test_doe_mixture_persistence.py`
- `A	tests/test_doe_mixture_plots.py`
- `A	tests/test_doe_mixture_predict.py`
- `A	tests/test_doe_mixture_references.py`
- `A	tests/test_doe_mixture_vertices.py`
- `A	tests/test_doe_modify.py`
- `A	tests/test_doe_optimal.py`
- `A	tests/test_doe_optimal_augmentation.py`
- `A	tests/test_doe_optimal_evaluation.py`
- `A	tests/test_doe_optimal_gui.py`
- `A	tests/test_doe_optimal_references.py`
- `M	tests/test_doe_rsm_gui.py`
- `A	tests/test_doe_schema_e.py`
- `M	tests/test_doe_schema_v2.py`
- `M	tests/test_doe_schema_v3.py`
- `M	tests/test_doe_splitplot_gui.py`
- `A	tests/test_doe_taguchi_arrays.py`
- `A	tests/test_doe_taguchi_dynamic.py`
- `A	tests/test_doe_taguchi_gui.py`
- `A	tests/test_doe_taguchi_noise.py`
- `A	tests/test_doe_taguchi_persistence.py`
- `A	tests/test_doe_taguchi_references.py`
- `A	tests/test_doe_taguchi_sn.py`
- `M	tests/test_help_center.py`
- `M	tests/test_menu_localization.py`

## 修复与验证进度

- P1-01：轴点不再绕过分类因子水平验证；仅允许已有 CCD/自定义 RSM 与旧 unspecified CCD 合同下的轴点，连续轴点须可编码为有限数；模型行拒绝未知分类标签。反例在原实现未抛错，新实现拒绝，包括重新计算输入摘要的恢复路径。
- 自定义 RSM 预测：沿用声明的模型项和既有拟合，按参考区组预测；二维二区组解析预测 9.5、文本分类预测 11.5，旧路径因缺编码列失败。预测 GUI 与同工程复制后预测已复测。
- P1-02：选点接收原始 `block_count` 并拒绝带区组合同的输入，GUI 传递原设计声明；两个连续因子、两个区组的独立解析矩阵秩 4，单一区组秩 3，拒绝 D-optimal 和 distance 两种路径。
- P2：L8 任意两列是正交投影，四个组合各出现两次；当前程序不支持所选控制列重复设定。选择阶段提示并拒绝该范围，不删除原表运行；控制列 1/2/4 可区分八行。
- 合并后矩阵有 5 行 CSV 引号缺失，现只修复字段边界；80 行与 ACC-001–067 唯一性通过。

## 独立参考

- `tests/fixtures/doe_optimal_reference/verify.py`：通过；参考文件 SHA-256 `499fd66c8dbcb3f448174549f4474a9c08ee8fac2fc41471fe6c111b7c8b1524`。
- `tests/fixtures/doe_mixture_reference/verify.py`：通过；参考数值未修改。原有清单计算时排除了末尾换行；生成器、清单和核验器现统一校验 16720 个文件字节，SHA-256 `cfc482999750eafac2bd8bc89b469e628c405cce23e25c00c010f2695184b0de`。
- `tests/fixtures/doe_taguchi_reference/verify.py`：23 passed；调用既有不导入生产模块的独立参考测试；6 个矩阵文件字节 SHA-256 匹配 manifest。
- 三组参考测试（部分含生产模块对照）的一次重叠测试命令：`python -m pytest tests/test_doe_optimal_references.py tests/test_doe_mixture_references.py tests/test_doe_taguchi_references.py -q`，30 passed（不是全套产物测试）。实际命令使用项目 `.venv\Scripts\python.exe`。

## 合并后联合工程与兼容性

- `tests/test_doe_efg_workbook_integration.py`：同一 `.dexpl` 中建立自定义 RSM 并最优增补、三组分混料、静态及动态 Taguchi；填响应、分析、保存/重开和复制。核对运行 ID、原响应、模型项、因子角色、批次谱系、分析选项；复制后重新分析、E 和 F 点预测、G 最佳设置预测并绘制 E/F/G 图形。坏 Taguchi 元数据使载入拒绝且已打开的所有工作表数据和元数据保持原样。
- DOE v1–v5：核心、v2、v3、v4 factorial 与 v5 E/Taguchi 的严格字段、摘要和读取迁移测试均在下列分组执行。新版读取旧格式的证据不表示旧版软件能读取 v5。
- GUI 按设计类别和文件独立进程运行，包含 CCD/BBD、Factorial/Fractional、PB/DSD、Split-Plot、自定义/最优、Mixture 和 Taguchi；菜单翻译 66 passed；帮助主题 99 个且帮助测试 13 passed；G12 清单修复排序后 15 passed。PB 六组按运行数分别执行 20/28/32/36/40/44 个参数案例。

## 测试结果与覆盖

- 单进程完整命令：`& $python -m pytest -q --disable-warnings`。约 26% 时 Tk `Menu.add` 报 Windows 原生异常 `0x80000003` 并退出，**无 pytest 总汇总**；该次运行期间工作区亦有改动，不将它视作全量通过。
- 替代方案为下表 174 个串行、互不重叠分组：以文件为边界；GUI 文件、同时含 GUI/非 GUI 的文件、PB 参数组均为独立进程，不与其他组并发。基于最终快照 `pytest --collect-only -q --disable-warnings` 收集 5073 个案例，逐节点对照分组：5073 个不同节点、无遗漏、无重复。首轮 5069 passed、2 failed，修复 G12 和帮助计数后分别复测通过；新增两个预测案例后预测组及相关 BBD/GUI/联合组重新执行。逐组替换后的覆盖为 **5073 个通过、0 失败、0 跳过**；这不是单次 pytest 的汇总，也不累加重叠定向测试。
- 代码在分组运行期间与之后有变更；与预测入口、测试、帮助、G12 清单直接相关的组均在最终变更后重跑，其余未受影响组复用已通过结果。各组起止时均在同一 main HEAD，使用其上的工作区；不是旧 worktree 历史结果。
- 首轮 G12 因相同文件集合的顺序不符合 Python 排序导致 1 failed/14 passed；仅排序清单后 15 passed。帮助主题数原期望 98、实际 99 导致 1 failed/12 passed；更新计数并保留唯一性、正文及索引检查后 13 passed。联合测试首次动态 Taguchi 样本违反行唯一合同导致 1 failed，调整控制/噪声列后通过；Taguchi GUI 首轮 2 failed，修正非正交列错误优先级及文案预期后 10 passed。
- `$python` 指 `C:\Users\shaoy\Documents\Minijmp\.venv\Scripts\python.exe`；下表命令均为 `& $python -m pytest <参数> -q`。PB 参数组的实际参数在表后完整列出；筛选 GUI 非 PB 组有 200 deselected，这 200 项在六个 PB 组单独执行。warning 数为 pytest 报告数；每行未显示的 failed、skipped 或 warning 数均为 0。初轮总计 493 warnings，替换组警告数未增加；常见为布局与缺字形、优化步越界截回、常数/小样本、数值除零/精度、秩亏和依赖弃用等，按测试输入解释，不等于统计结果通过以外的额外证明。
- 独立参考另执行：`tests/fixtures/doe_optimal_reference/verify.py`、`tests/fixtures/doe_mixture_reference/verify.py`、`tests/fixtures/doe_taguchi_reference/verify.py`（依次为脚本通过、脚本通过、23 passed）。`tests/test_doe_optimal_references.py tests/test_doe_mixture_references.py tests/test_doe_taguchi_references.py -q` 30 passed；该组合与下表重叠，不计入不重叠覆盖总数。
- 两次直接相关的组合复测：`tests/test_doe_predict.py tests/test_help_center.py tests/test_g12_inventory.py -q` 39 passed；`tests/test_doe_efg_workbook_integration.py tests/test_doe_predict_gui.py -q --tb=short` 7 passed、3 warnings。上述组合与下表重叠，仅作佐证。

### 逐组实际命令与结果

| 组 | 参数（公共前缀见上） | 结果 |
| --- | --- | --- |
| 1 | `tests/test_doe_screening_gui.py -k not test_pb_new_run_counts_all_factor_counts_gui` | 118 passed, 200 deselected, 107 warnings in 436.07s (0:07:16) |
| 2 | `见 PB 参数附录：PB-24` | 20 passed, 20 warnings in 63.12s (0:01:03) |
| 3 | `见 PB 参数附录：PB-32` | 28 passed, 28 warnings in 101.85s (0:01:41) |
| 4 | `见 PB 参数附录：PB-36` | 32 passed, 32 warnings in 116.96s (0:01:56) |
| 5 | `见 PB 参数附录：PB-40` | 36 passed, 36 warnings in 122.31s (0:02:02) |
| 6 | `见 PB 参数附录：PB-44` | 40 passed, 40 warnings in 150.48s (0:02:30) |
| 7 | `见 PB 参数附录：PB-48` | 44 passed, 44 warnings in 171.56s (0:02:51) |
| 8 | `tests/test_doe_analysis.py` | 15 passed in 1.43s |
| 9 | `tests/test_doe_augment.py` | 12 passed in 1.51s |
| 10 | `tests/test_doe_bbd.py` | 44 passed in 31.13s（最终改动后复测） |
| 11 | `tests/test_doe_bbd_gui.py` | 10 passed, 1 warning in 33.68s（最终改动后复测） |
| 12 | `tests/test_doe_bbd_minitab_parity.py` | 18 passed in 2.91s |
| 13 | `tests/test_doe_ccd.py` | 41 passed in 2.29s |
| 14 | `tests/test_doe_ccd_options.py` | 23 passed in 7.83s |
| 15 | `tests/test_doe_ccd_options_gui.py` | 13 passed in 8.26s |
| 16 | `tests/test_doe_core.py` | 30 passed in 1.33s |
| 17 | `tests/test_doe_custom_factorial.py` | 7 passed in 1.40s |
| 18 | `tests/test_doe_custom_gui.py` | 7 passed, 30 warnings in 6.62s |
| 19 | `tests/test_doe_custom_rsm.py` | 8 passed in 1.46s |
| 20 | `tests/test_doe_custom_screening.py` | 6 passed in 1.54s |
| 21 | `tests/test_doe_diagnostics_contract.py` | 3 passed in 1.82s |
| 22 | `tests/test_doe_distance_optimal.py` | 7 passed in 1.61s |
| 23 | `tests/test_doe_dsd.py` | 93 passed in 54.57s |
| 24 | `tests/test_doe_e_lifecycle.py` | 5 passed in 5.63s |
| 25 | `tests/test_doe_efg_workbook_integration.py` | 1 passed, 3 warnings in 8.00s（最终改动后复测） |
| 26 | `tests/test_doe_factorial.py` | 9 passed in 1.62s |
| 27 | `tests/test_doe_factorial_anova.py` | 5 passed in 1.49s |
| 28 | `tests/test_doe_factorial_blocks.py` | 7 passed in 1.48s |
| 29 | `tests/test_doe_factorial_references.py` | 1 passed in 1.45s |
| 30 | `tests/test_doe_factorial_schema.py` | 7 passed in 1.34s |
| 31 | `tests/test_doe_foldover.py` | 12 passed in 8.80s |
| 32 | `tests/test_doe_foldover_gui.py` | 2 passed in 4.97s |
| 33 | `tests/test_doe_fractional.py` | 18 passed in 1.46s |
| 34 | `tests/test_doe_fractional_analysis.py` | 11 passed in 1.43s |
| 35 | `tests/test_doe_fractional_gui.py` | 15 passed, 1 warning in 9.60s |
| 36 | `tests/test_doe_general_factorial.py` | 11 passed in 10.51s |
| 37 | `tests/test_doe_general_factorial_analysis.py` | 5 passed in 3.08s |
| 38 | `tests/test_doe_general_factorial_gui.py` | 3 passed, 1 warning in 4.45s |
| 39 | `tests/test_doe_gui.py` | 5 passed, 3 warnings in 8.46s |
| 40 | `tests/test_doe_mixture_anova.py` | 6 passed in 1.38s |
| 41 | `tests/test_doe_mixture_centroid.py` | 1 passed in 1.67s |
| 42 | `tests/test_doe_mixture_constraints.py` | 4 passed in 1.34s |
| 43 | `tests/test_doe_mixture_gui.py` | 7 passed, 6 warnings in 7.90s |
| 44 | `tests/test_doe_mixture_lattice.py` | 7 passed in 1.26s |
| 45 | `tests/test_doe_mixture_model.py` | 10 passed in 1.31s |
| 46 | `tests/test_doe_mixture_optimize.py` | 3 passed, 9 warnings in 1.42s |
| 47 | `tests/test_doe_mixture_persistence.py` | 4 passed in 2.54s |
| 48 | `tests/test_doe_mixture_plots.py` | 6 passed in 1.40s |
| 49 | `tests/test_doe_mixture_predict.py` | 7 passed in 1.42s |
| 50 | `tests/test_doe_mixture_references.py` | 6 passed in 1.51s |
| 51 | `tests/test_doe_mixture_vertices.py` | 3 passed in 1.46s |
| 52 | `tests/test_doe_modify.py` | 8 passed in 1.39s |
| 53 | `tests/test_doe_optimal.py` | 16 passed in 14.52s |
| 54 | `tests/test_doe_optimal_augmentation.py` | 10 passed in 1.80s |
| 55 | `tests/test_doe_optimal_evaluation.py` | 7 passed in 1.44s |
| 56 | `tests/test_doe_optimal_gui.py` | 6 passed in 4.98s |
| 57 | `tests/test_doe_optimal_references.py` | 1 passed in 1.27s |
| 58 | `tests/test_doe_optimize.py` | 54 passed in 9.81s |
| 59 | `tests/test_doe_optimize_gui.py` | 9 passed in 11.33s |
| 60 | `tests/test_doe_overlay.py` | 6 passed in 1.66s |
| 61 | `tests/test_doe_overlay_gui.py` | 4 passed, 4 warnings in 4.43s |
| 62 | `tests/test_doe_pb.py` | 17 passed in 5.37s |
| 63 | `tests/test_doe_persistence.py` | 10 passed in 5.97s |
| 64 | `tests/test_doe_predict.py` | 11 passed in 1.39s（新增两个预测用例后复测） |
| 65 | `tests/test_doe_predict_gui.py` | 6 passed in 4.03s（最终改动后复测） |
| 66 | `tests/test_doe_rsm.py` | 11 passed in 1.90s |
| 67 | `tests/test_doe_rsm_categorical.py` | 8 passed in 1.76s |
| 68 | `tests/test_doe_rsm_diagnostics.py` | 7 passed in 1.41s |
| 69 | `tests/test_doe_rsm_gui.py` | 11 passed, 3 warnings in 28.03s |
| 70 | `tests/test_doe_schema_e.py` | 7 passed in 1.37s |
| 71 | `tests/test_doe_schema_v2.py` | 14 passed in 1.40s |
| 72 | `tests/test_doe_schema_v3.py` | 19 passed in 3.42s |
| 73 | `tests/test_doe_screening_analysis.py` | 15 passed in 1.64s |
| 74 | `tests/test_doe_screening_references.py` | 12 passed in 2.15s |
| 75 | `tests/test_doe_splitplot.py` | 7 passed in 1.63s |
| 76 | `tests/test_doe_splitplot_analysis.py` | 2 passed in 1.41s |
| 77 | `tests/test_doe_splitplot_gui.py` | 6 passed, 1 warning in 9.92s |
| 78 | `tests/test_doe_taguchi_arrays.py` | 32 passed in 1.67s |
| 79 | `tests/test_doe_taguchi_dynamic.py` | 12 passed in 1.54s |
| 80 | `tests/test_doe_taguchi_gui.py` | 10 passed, 2 warnings in 9.22s |
| 81 | `tests/test_doe_taguchi_noise.py` | 20 passed in 1.82s |
| 82 | `tests/test_doe_taguchi_persistence.py` | 20 passed in 5.50s |
| 83 | `tests/test_doe_taguchi_references.py` | 23 passed in 1.26s |
| 84 | `tests/test_doe_taguchi_sn.py` | 25 passed in 1.75s |
| 85 | `tests/test_advanced_regression.py` | 93 passed in 3.44s |
| 86 | `tests/test_advanced_spc.py` | 63 passed in 1.87s |
| 87 | `tests/test_advanced_spc_dialog.py` | 10 passed in 14.48s |
| 88 | `tests/test_advanced_spc_plots.py` | 69 passed in 9.51s |
| 89 | `tests/test_analysis_source_exports.py` | 3 passed in 4.40s |
| 90 | `tests/test_attribute_agreement.py` | 13 passed in 1.78s |
| 91 | `tests/test_capability.py` | 46 passed in 4.90s |
| 92 | `tests/test_capability_compare.py` | 14 passed in 4.82s |
| 93 | `tests/test_capability_dialog.py` | 14 passed in 31.66s |
| 94 | `tests/test_capability_plots.py` | 25 passed in 6.86s |
| 95 | `tests/test_column_selection.py` | 21 passed in 7.39s |
| 96 | `tests/test_context_clipboard.py` | 22 passed in 4.07s |
| 97 | `tests/test_csv_import.py` | 41 passed in 6.53s |
| 98 | `tests/test_dialog_translation.py` | 119 passed in 34.78s |
| 99 | `tests/test_file_io.py` | 45 passed in 2.53s |
| 100 | `tests/test_g10_tables.py` | 41 passed, 5 warnings in 10.62s |
| 101 | `tests/test_g11_quality_tables.py` | 123 passed in 15.38s |
| 102 | `tests/test_g12_inventory.py` | 15 passed in 6.28s（首轮 1 failed/14 passed，修复后复测） |
| 103 | `tests/test_g12_tables.py` | 9 passed in 12.97s |
| 104 | `tests/test_g13_time_series.py` | 38 passed in 8.37s |
| 105 | `tests/test_g14_rendering.py` | 15 passed in 36.71s |
| 106 | `tests/test_g16_statistics.py` | 117 passed, 58 warnings in 6.66s |
| 107 | `tests/test_g17_csv.py` | 74 passed in 2.36s |
| 108 | `tests/test_g17_data_processing.py` | 127 passed in 6.08s |
| 109 | `tests/test_g18_performance.py` | 17 passed in 6.68s |
| 110 | `tests/test_g19_integration.py` | 2 passed in 1.69s |
| 111 | `tests/test_g1_debug_output.py` | 24 passed in 1.97s |
| 112 | `tests/test_g1_statistics_output.py` | 33 passed in 1.78s |
| 113 | `tests/test_g1_text_output.py` | 13 passed in 4.80s |
| 114 | `tests/test_g20_likelihood_ratio.py` | 87 passed in 2.56s |
| 115 | `tests/test_g21_plotter.py` | 9 passed in 30.55s |
| 116 | `tests/test_g2_basic_reports.py` | 67 passed in 4.80s |
| 117 | `tests/test_g2_hypothesis_reports.py` | 74 passed in 2.36s |
| 118 | `tests/test_g3_anova_reports.py` | 49 passed in 3.35s |
| 119 | `tests/test_g3_chi_square_reports.py` | 36 passed in 1.97s |
| 120 | `tests/test_g3_computation_contracts.py` | 27 passed in 1.42s |
| 121 | `tests/test_g3_distribution_reports.py` | 30 passed in 2.74s |
| 122 | `tests/test_g3_regression_reports.py` | 26 passed, 5 warnings in 3.12s |
| 123 | `tests/test_g3_report_display.py` | 16 passed in 6.09s |
| 124 | `tests/test_g4_quality_reports.py` | 149 passed in 17.94s |
| 125 | `tests/test_g5_spc_reports.py` | 74 passed in 8.25s |
| 126 | `tests/test_g6_chart_presentation.py` | 54 passed, 3 warnings in 10.47s |
| 127 | `tests/test_g6_quality_charts.py` | 53 passed in 5.66s |
| 128 | `tests/test_g7_tables.py` | 12 passed in 4.85s |
| 129 | `tests/test_g8_tables.py` | 35 passed in 14.38s |
| 130 | `tests/test_g9_tables.py` | 117 passed in 30.75s |
| 131 | `tests/test_generalized_regression.py` | 9 passed, 4 warnings in 1.86s |
| 132 | `tests/test_help_center.py` | 13 passed in 2.92s（首轮 1 failed/12 passed，修复后复测） |
| 133 | `tests/test_improvement_chart.py` | 33 passed in 5.44s |
| 134 | `tests/test_menu_localization.py` | 66 passed in 16.27s |
| 135 | `tests/test_p1_p2_statistical_fixes.py` | 86 passed in 5.37s |
| 136 | `tests/test_pca_analysis.py` | 145 passed in 3.08s |
| 137 | `tests/test_pca_dialog.py` | 4 passed in 10.57s |
| 138 | `tests/test_pca_plots.py` | 83 passed in 8.93s |
| 139 | `tests/test_phase1_plots.py` | 63 passed, 24 warnings in 10.93s |
| 140 | `tests/test_phase2_plots.py` | 73 passed in 22.84s |
| 141 | `tests/test_pi_import.py` | 31 passed in 7.81s |
| 142 | `tests/test_pi_reader.py` | 37 passed in 1.49s |
| 143 | `tests/test_plot_window_lifecycle.py` | 39 passed, 9 warnings in 37.04s |
| 144 | `tests/test_plotter_roles.py` | 9 passed, 1 warning in 22.90s |
| 145 | `tests/test_pls_regression.py` | 48 passed in 1.80s |
| 146 | `tests/test_quality_tools.py` | 17 passed in 2.91s |
| 147 | `tests/test_quality_tools_dialog.py` | 7 passed in 16.94s |
| 148 | `tests/test_regression_dialog.py` | 16 passed in 16.97s |
| 149 | `tests/test_regression_plots.py` | 23 passed in 5.37s |
| 150 | `tests/test_result_background.py` | 35 passed in 30.07s |
| 151 | `tests/test_review003_anova.py` | 15 passed, 3 warnings in 1.95s |
| 152 | `tests/test_review_data_safety.py` | 31 passed in 2.29s |
| 153 | `tests/test_review_p1_lifecycle.py` | 7 passed in 5.55s |
| 154 | `tests/test_review_p1_sources.py` | 3 passed in 3.15s |
| 155 | `tests/test_review_p1_statistics.py` | 12 passed in 2.17s |
| 156 | `tests/test_review_p1_utilities.py` | 13 passed, 1 warning in 1.89s |
| 157 | `tests/test_review_p2_legacy.py` | 8 passed in 5.57s |
| 158 | `tests/test_review_p2_quality.py` | 18 passed in 3.24s |
| 159 | `tests/test_review_p2_regression.py` | 19 passed, 2 warnings in 1.94s |
| 160 | `tests/test_review_proportions.py` | 26 passed in 2.08s |
| 161 | `tests/test_sheet_context.py` | 6 passed in 1.98s |
| 162 | `tests/test_startup.py` | 17 passed in 4.00s |
| 163 | `tests/test_statistical_edges.py` | 15 passed in 2.21s |
| 164 | `tests/test_statistics_regressions.py` | 60 passed, 7 warnings in 3.72s |
| 165 | `tests/test_supplemental_stability.py` | 39 passed in 3.24s |
| 166 | `tests/test_table_regressions.py` | 182 passed in 20.96s |
| 167 | `tests/test_time_series_analysis.py` | 120 passed in 2.79s |
| 168 | `tests/test_time_series_analysis_dialog.py` | 4 passed in 8.94s |
| 169 | `tests/test_time_series_analysis_plots.py` | 131 passed in 16.50s |
| 170 | `tests/test_windows_packaging.py` | 16 passed in 12.53s |
| 171 | `tests/test_windows_release_tools.py` | 9 passed in 2.54s |
| 172 | `tests/test_worksheet_context_menu.py` | 7 passed in 5.24s |
| 173 | `tests/test_worksheet_formulas.py` | 37 passed in 6.96s |
| 174 | `tests/test_worksheets.py` | 18 passed in 6.60s |


### PB 参数附录

下列每个代码块是该组传给 pytest 的全部节点参数；每组单独进程，均另加 `-q`。

**PB-24**

```text
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[24-2]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[24-4]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[24-5]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[24-6]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[24-7]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[24-8]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[24-9]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[24-10]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[24-11]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[24-12]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[24-13]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[24-14]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[24-15]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[24-16]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[24-17]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[24-18]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[24-19]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[24-20]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[24-21]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[24-22]
```

**PB-32**

```text
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[32-2]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[32-4]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[32-5]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[32-6]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[32-7]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[32-8]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[32-9]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[32-10]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[32-11]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[32-12]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[32-13]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[32-14]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[32-15]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[32-16]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[32-17]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[32-18]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[32-19]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[32-20]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[32-21]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[32-22]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[32-23]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[32-24]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[32-25]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[32-26]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[32-27]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[32-28]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[32-29]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[32-30]
```

**PB-36**

```text
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[36-2]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[36-4]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[36-5]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[36-6]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[36-7]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[36-8]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[36-9]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[36-10]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[36-11]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[36-12]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[36-13]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[36-14]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[36-15]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[36-16]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[36-17]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[36-18]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[36-19]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[36-20]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[36-21]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[36-22]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[36-23]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[36-24]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[36-25]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[36-26]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[36-27]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[36-28]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[36-29]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[36-30]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[36-31]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[36-32]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[36-33]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[36-34]
```

**PB-40**

```text
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[40-2]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[40-4]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[40-5]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[40-6]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[40-7]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[40-8]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[40-9]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[40-10]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[40-11]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[40-12]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[40-13]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[40-14]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[40-15]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[40-16]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[40-17]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[40-18]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[40-19]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[40-20]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[40-21]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[40-22]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[40-23]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[40-24]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[40-25]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[40-26]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[40-27]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[40-28]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[40-29]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[40-30]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[40-31]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[40-32]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[40-33]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[40-34]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[40-35]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[40-36]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[40-37]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[40-38]
```

**PB-44**

```text
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[44-2]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[44-4]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[44-5]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[44-6]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[44-7]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[44-8]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[44-9]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[44-10]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[44-11]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[44-12]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[44-13]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[44-14]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[44-15]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[44-16]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[44-17]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[44-18]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[44-19]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[44-20]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[44-21]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[44-22]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[44-23]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[44-24]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[44-25]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[44-26]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[44-27]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[44-28]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[44-29]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[44-30]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[44-31]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[44-32]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[44-33]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[44-34]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[44-35]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[44-36]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[44-37]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[44-38]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[44-39]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[44-40]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[44-41]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[44-42]
```

**PB-48**

```text
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[48-2]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[48-4]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[48-5]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[48-6]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[48-7]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[48-8]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[48-9]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[48-10]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[48-11]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[48-12]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[48-13]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[48-14]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[48-15]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[48-16]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[48-17]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[48-18]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[48-19]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[48-20]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[48-21]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[48-22]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[48-23]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[48-24]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[48-25]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[48-26]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[48-27]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[48-28]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[48-29]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[48-30]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[48-31]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[48-32]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[48-33]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[48-34]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[48-35]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[48-36]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[48-37]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[48-38]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[48-39]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[48-40]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[48-41]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[48-42]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[48-43]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[48-44]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[48-45]
tests/test_doe_screening_gui.py::test_pb_new_run_counts_all_factor_counts_gui[48-46]
```

## 当前 partial ACC

001、002、003、005、006、007、011、013、015、017、018、036、049、052、053、056、058、066（前缀均为 `MTB-DOE-ACC-`）。来源为当前 `feature-matrix.csv`，不等同于本次集成验证结论。

## 阻断与剩余风险

- 以已完成的限定范围判断，未发现尚未处理的统计正确性、数据完整性或工程兼容阻断；结果可交独立 Review，不能替代 Review APPROVE。
- 单进程全套测试存在 Windows Tk `0x80000003` 风险，必须使用上述分进程证据；不能把该异常表述为单进程全量通过。
- L8 两列投影在数学上有效但产品暂不支持；带区组的最优选点明确不支持。旧软件读取 v5、Minitab 输出及仍为 partial 的范围不在本次验证内。
- 检查未引入无消费者的抽象、缓存、fallback 或兼容层；保留分类输入和界面即时投影检查，是因为模型行和设计恢复/创建分别是可独立调用的边界。
