# G12 全部统计报告表格迁移审计

2026-10-20；工作区 `C:\Users\shaoy\Documents\Minijmp`，起点提交
`c0c2c2aa316e7e0f236e551bf4cd2f60f2e30df3`，任务开始时工作区干净。
没有提交、推送、合并、安装依赖或改动统计算法。

## 审计结论与计数口径

有界审计覆盖 `code/**/*.py` 的 **69 个 Python 文件**。其中 23 个文件、46 个限定函数
含表格构造、原生表转换或表格输出位置；39 个函数属于实际统计报告，分布于 **19 个模块**。
确认 **56 个 StatTable 生产位置、82 张逻辑统计表**，均已使用统一组件。
唯一遗漏是 `utilities.mean_std_CIs`，本次已迁移；没有为矩阵、错误框或普通文字新增统计表。

计数不等同于一次运行出现的表数：固定章节循环按标题展开，可选章节计入；
分布名、方法名、置信水平、组内/整体或面板名等参数化模板只计一次。
例如 `t_test_1sample` 一个构造位置产生三种固定章节；SPC 明细模板按实际面板重复；
原生 OLS/GLS/Logit 摘要按三种表模板计数，Logit 实际只输出前两张。
`gen_table` 的兼容 ASCII 与包裹它的 StatTable 是同一张逻辑表。

审计共定位 114 个构造调用：54 个 `gen_table`、4 个 PrettyTable/PT、56 个 StatTable。
兼容文本、通用工厂和错误框的构造不另算统计报告。
完整机器清单见 [g12_table_inventory.json](../tests/fixtures/g12_table_inventory.json)：
包含全部 69 个文件的审阅结论、具体函数、逐类生产序号、标题、入口、状态、测试和例外原因。

## 全量统计生产清单

以下全部为“已迁移 StatTable”。普通报告经 `print_port` / `app.print`（包括函数内别名 `print`）
到 `Minijmp.print → txt_viewer.add_table → TableBlock`；
原生模型经 `StatsViewer.summary → model_summary_tables → txt_viewer.add_table`。
`Residual`、各分析对话框、绘图入口及 GRR 内部静默调用不另算表格副本。
对应测试列为清单中的主测试；完整回归还包含这些模块原有的计算、GUI 和边界测试。

| 文件 / 函数 | 逻辑表数及标题 | 实际入口 | 对应测试 |
| --- | --- | --- | --- |
| `GRR.py::_grr_tables` | 2：方差分量；研究变异 / 分量标准差 | GRR_xbar；grr_anova_AIAG；grr_anova_EMP；grr_nested；GRRDialog.apply；GRR_Nested_Dialog.apply | `tests/test_g11_quality_tables.py::test_all_report_producers_keep_txt_results_and_export_real_files` |
| `GRR.py::grr_anova_EMP` | 2：EMP 补充统计；原有 EMP 分类参考（不新增 GRR 接受阈值） | grr_master(mode=EMP) → GRRDialog.apply；grr_anova_EMP | `tests/test_g11_quality_tables.py::test_all_report_producers_keep_txt_results_and_export_real_files` |
| `GRR.py::grr_master` | 1：GRR 交互项筛选：完整模型 ANOVA | GRRDialog.apply；grr_master(inter=Auto 且有操作者) | `tests/test_g11_quality_tables.py::test_all_report_producers_keep_txt_results_and_export_real_files` |
| `GRR.py::grr_nested` | 1：方差分析 ANOVA | GRR_Nested_Dialog.apply；grr_nested | `tests/test_g11_quality_tables.py::test_all_report_producers_keep_txt_results_and_export_real_files` |
| `chi2_dialog.py::Chi2PropDialog.apply` | 2：各水平概率；检验结果 | Chi2PropDialog.apply（原始/汇总/归一化） | `tests/test_g9_tables.py::test_fixed_txt_and_every_table_reaches_viewer` |
| `chi_sq.py::chi2_test_stdev` | 4：样本统计；检验结果；总体标准差的置信区间；抽样分布参考（不是总体参数的置信区间） | chi2_test_stdev；single_pop_var_test 别名；直接调用 | `tests/test_g9_tables.py::test_fixed_txt_and_every_table_reaches_viewer` |
| `chi_sq.py::chi2_var_1sample` | 3：样本统计；检验结果；总体标准差的置信区间 | chi2_var_1sample；var_1sample 内部静默调用；直接调用 | `tests/test_g9_tables.py::test_fixed_txt_and_every_table_reaches_viewer` |
| `chi_sq.py::chi_square` | 2：列联表（观测频数 / 期望频数）；检验结果 | Chi2TableDialog.apply（原始/汇总）；chi_square；比例/拟合优度内部静默调用 | `tests/test_g9_tables.py::test_fixed_txt_and_every_table_reaches_viewer` |
| `chi_sq.py::multi_pop_var_test` | 1：Multi Sample Standard Deviation Test | MultiVarDialog.apply；multi_pop_var_test；two_pop_var_test 旧转发入口 | `tests/test_g9_tables.py::test_fixed_txt_and_every_table_reaches_viewer` |
| `chi_sq.py::var_1sample` | 3：样本统计；检验结果（双侧）；总体标准差的置信区间 | var_1sample；Var1SampleDialog.apply（原始/汇总） | `tests/test_g9_tables.py::test_fixed_txt_and_every_table_reaches_viewer` |
| `control_chart.py::_print_spc_report` | 2：控制限汇总；{面板名称} 逐点明细 | x_plot → IMRDialog/IDialog/MRDialog/XBRDialog/XBSDialog.apply；p_np_plot → PDialog/NPDialog.apply；cu_plot → CDialog/UDialog.apply | `tests/test_g11_quality_tables.py::test_all_report_producers_keep_txt_results_and_export_real_files` |
| `cpk.py::cpk` | 1：正态过程能力分析 | CpkDialog.apply / CpkSubDialog.apply → cpk_plot → cpk；cpk | `tests/test_g11_quality_tables.py::test_all_report_producers_keep_txt_results_and_export_real_files` |
| `cpk.py::cpk_calc` | 1：{section}（正态模型，置信水平 {confidence}%） | cpk（组内/整体）；cpk_calc | `tests/test_g11_quality_tables.py::test_all_report_producers_keep_txt_results_and_export_real_files` |
| `cpk.py::nonconformance` | 1：不合格比例（单位：%） | cpk；nonconformance | `tests/test_g11_quality_tables.py::test_all_report_producers_keep_txt_results_and_export_real_files` |
| `describe.py::print_descriptive` | 2：描述性统计；补充统计 | describe(print_out=True)；DescribeDialog.apply；MultiDescribeDialog.apply | `tests/test_g7_tables.py::test_structured_fallback` |
| `describe.py::print_percentiles` | 1：百分位数 | describe(print_out=True)；DescribeDialog.apply | `tests/test_g7_tables.py::test_structured_fallback` |
| `dist_fit.py::compare_dist` | 1：分布比较 | FitDistDialog.apply；compare_dist（多模型成功分支） | `tests/test_g10_tables.py::test_text_values_and_real_exports` |
| `dist_fit.py::print_table` | 3：{fit_name} 参数估计；{fit_name} 拟合指标；{fit_name} 拟合优度 | fit_norm/fit_t/fit_gamma/fit_lognorm/fit_expon/fit_weibull；FitDistDialog.apply；singleHistoDialog.apply | `tests/test_g10_tables.py::test_text_values_and_real_exports` |
| `fit_dialog.py::print_multi_col_tables` | 2：{name} 相关系数矩阵（N = {N}）；{name} p 值矩阵 | MCorDialog.apply 的 Spearman/Kendall/Hoeffding 分支；print_multi_col_tables | `tests/test_g10_tables.py::test_text_values_and_real_exports` |
| `linear_fit.py::linear_fit` | 5：模型摘要；回归系数；方差分析（ANOVA）；失拟检验（有重复 X 且可估计时）；残差正态性诊断 | LinearFitDialog.apply → fit_plot；linear_fit | `tests/test_g10_tables.py::test_text_values_and_real_exports` |
| `linear_plot.py::multi_fit` | 2：Pearson 相关系数矩阵（N = {N}）；Pearson p 值矩阵 | multi_fit；MCorDialog.apply → multi_fit | `tests/test_g10_tables.py::test_text_values_and_real_exports` |
| `linear_plot.py::multi_fit_orig` | 2：Pearson 相关系数矩阵（N = {N}）；Pearson p 值矩阵 | multi_fit_orig；公开旧直接入口，独立报告副本 | `tests/test_g10_tables.py::test_text_values_and_real_exports` |
| `nonpara_cor.py::print_correlation` | 1：{method} 相关分析 | spearman/kendall/hoeffding；CorrelationDialog.apply | `tests/test_g10_tables.py::test_text_values_and_real_exports` |
| `one_way_ANOVA.py::JMP_ANOVA_t_test` | 2：均值逐对比较；字母分组（按均值降序） | TtestDialog.apply；Anova1WayDialog.apply(comp_mean=True)；JMP_ANOVA_t_test | `tests/test_g9_tables.py::test_fixed_txt_and_every_table_reaches_viewer` |
| `one_way_ANOVA.py::one_way_anova` | 2：各组均值摘要；方差分析表 | Anova1WayDialog.apply（列/堆叠）；Anova1WayDialog_old.apply；one_way_anova；GRR 内部静默调用 | `tests/test_g9_tables.py::test_fixed_txt_and_every_table_reaches_viewer` |
| `ortho_fit.py::orthogonal_fit` | 3：参数估计；测量误差方差估计；逐观测诊断（print_residual 独立开关） | OrthoFitDialog → LinearFitDialog.apply → fit_plot；orthogonal_fit | `tests/test_g10_tables.py::test_text_values_and_real_exports` |
| `pandastable_local/stats.py::model_summary_tables` | 3：原生模型摘要（native.title）；回归系数；残差诊断（OLS/GLS） | StatsViewer.doFit → StatsViewer.summary → model_summary_tables；Summary 按钮；OLS/GLS 三表，Logit 两表 | `tests/test_g10_tables.py::test_native_models_keep_text_and_unrounded_values` |
| `proportion_test.py::prop_2sample` | 3：样本统计；检验结果；总体比例差 p1 - p2 的置信区间（非合并正态近似） | prop_2sample；Prop2SDialog.apply（原始/汇总） | `tests/test_g9_tables.py::test_fixed_txt_and_every_table_reaches_viewer` |
| `proportion_test.py::prop_test_1sample` | 4：样本统计；检验结果；总体比例的置信区间；检验结果（JMP 列联表；备择假设 H1: p ≠ p0） | prop_test_1sample；Prop1SDialog.apply（原始/汇总） | `tests/test_g9_tables.py::test_fixed_txt_and_every_table_reaches_viewer` |
| `t_test.py::paired_t_test` | 3：样本统计；检验结果；配对差值总体均值的置信区间 | paired_t_test；PairedTDialog.apply | `tests/test_g9_tables.py::test_fixed_txt_and_every_table_reaches_viewer` |
| `t_test.py::t_test_1sample` | 3：样本统计；检验结果；总体均值的置信区间 | t_test_1sample；Mean1SampleDialog.apply | `tests/test_g9_tables.py::test_fixed_txt_and_every_table_reaches_viewer` |
| `t_test.py::t_test_2samples` | 1：样本统计 | Mean2SampleDialog.apply（原始/汇总）；t_test_2samples | `tests/test_g9_tables.py::test_fixed_txt_and_every_table_reaches_viewer` |
| `t_test.py::t_test_2samples.tTest` | 2：检验结果；总体均值差 μ2 - μ1 的置信区间 | t_test_2samples.tTest；Mean2SampleDialog.apply → t_test_2samples（pooled/Welch） | `tests/test_g9_tables.py::test_fixed_txt_and_every_table_reaches_viewer` |
| `t_test.py::z_test_1sample` | 3：样本统计；检验结果；总体均值的置信区间 | z_test_1sample；Mean1SampleZDialog.apply | `tests/test_g9_tables.py::test_fixed_txt_and_every_table_reaches_viewer` |
| `ti.py::ti_norm` | 2：样本统计；统计容差区间（正态方法） | TIDialog.apply（原始/汇总）；ti_norm | `tests/test_g9_tables.py::test_fixed_txt_and_every_table_reaches_viewer` |
| `two_way_anova.py::two_way_anova` | 2：因子水平；方差分析表 | Anova2WayDialog.apply（交互/加法）；two_way_anova | `tests/test_g9_tables.py::test_fixed_txt_and_every_table_reaches_viewer` |
| `utilities.py::mean_std_CIs` | 1：置信区间 | CIDialog.apply；mean_std_CIs | `tests/test_g12_tables.py::test_interval_report_keeps_txt_computation_and_exports` |
| `utilities.py::norm_test` | 1：正态性检验 | NormTestDialog.apply；orthogonal_fit；Residual.resid_test；Residual.linear_fit_resid_test；ResidDialog.apply；norm_test | `tests/test_g10_tables.py::test_text_values_and_real_exports` |
| `utilities.py::pearson_correlation` | 2：Pearson 相关分析；Pearson 协方差及置信区间 | CorrelationDialog.apply → fit_plot；pearson_correlation | `tests/test_g10_tables.py::test_text_values_and_real_exports` |

G7–G11 已有 81 张逻辑表，本次补齐 1 张。
所有位置沿用同一个 `stat_table.py`，没有另一套统计组件或导出实现。

## 遗漏修复与保留内容

`utilities.mean_std_CIs` 由 `CIDialog.apply` 及直接函数调用进入，原来执行 `print(str(table))`。
修复只把该出口替换为 `StatTable(table, '置信区间', ...)`，
传入原均值、标准差、双侧区间及两个单侧置信限作为原值；显示字符串来自原 PrettyTable 行。
所有统计调用、alpha、返回值、章节、样本量说明和 TXT 字符均保持原样。
函数默认静默行为不变，未给其他模块增加报告、数据清洗或统计功能。

下面四处非结构化出口是明确的非报告例外，不是未迁移的分析表：

| 文件 / 函数 | 保留原因 |
| --- | --- |
| `dialog.py::Dialogs.error` | 单格 ERROR 消息框，属于输入/执行错误说明。 |
| `pandastable_local/core_orig.py::Table.showasText` | 用户选择的原始 DataFrame 转文本工具，不是统计摘要。 |
| `pandastable_local/dialogs.py::CSVPreviewDialog.update_preview` | `head(10).to_string()` 是 CSV 导入预览，写入专用文本框。 |
| `pandastable_local/stats.py::StatsViewer.plotLogit` | `pred_table(0.5)` 为绘图方法的控制台诊断矩阵，不走统计报告窗口。 |

另有三类构造/转换只服务兼容文本：`utilities.gen_table`、`StatTable.__new__` 的 PrettyTable
构造，以及 `StatsViewer.summary` 取得原生摘要后逐表包装的路径。
`txt_output.add_table` 将 `str(table)` 写入隐藏 Text 标签以保持 TXT/复制，属于已迁移表的文本镜像。
这些位置没有重复统计实现，也不会阻断每张表的独立导出。

逐文件人工复核还确认以下内容应保持原样，完整理由也已列入 JSON：

- `Minijmp.printDF`、排序片段、DataFrame 合并示例、数据流和拾取坐标输出为调试/内部数据。
- `linear_plot` 的相关结果字典、残差/拟合值向量是计算或绘图数据；相应报告投影已迁移。
- O'Brien、Levene、Brown-Forsythe、F/Bonett 的原有单行诊断，以及二项/泊松/连续分布的标量说明，
  不因包含数值或 tab 就强制转表。
- 分布拟合参数元组示例、`__main__` 演示、版本、URL、PI 请求/错误详情和插件帮助是普通文本。
  演示若调用真实报告函数，其表仍计入对应生产函数，不另保留旧副本。

## 源码级防遗漏检查

[test_g12_inventory.py](../tests/test_g12_inventory.py) 只读取 `code/**/*.py`，
约束文件集合、限定函数中的构造事件和表格出口；清单须人工更新，不自动接受新生产位置。
检查覆盖 `gen_table`、PrettyTable/PT、StatTable、原生 summary、`to_string/as_text/get_string`、
显式别名、局部表格变量的字符串包装，以及多行 ASCII/tab 表字面量。
统计报告分类不允许未经说明的 legacy/native/literal 输出。
章节标题、p 值说明、普通字符串和单行 tab 有反例测试，不能一律视作表格。

测试不冻结行号、整文件 hash、普通 `print` 次数或普通文本内容。
扫描器只追踪显式源码关系；不声称推断任意跨函数动态对象流。
这类静态边界由本次 69 文件人工分类和真实入口回归补充。

## GUI、TXT 与独立导出验收

复用 G7–G11 的真实 Tk、固定 TXT、原始数值及真实文件测试，并新增 G12 混合场景：

- 77 张实际报告表混合普通文字连续输出；逐表滚入视口后核对导出菜单位于标题左侧，
  中文字体配置、列对齐和表格对象身份均保持。
- 每张混合表实际调用自己的 Excel、PNG 菜单，读取文件标题、完整行列及 PNG 有效性；
  原有各模块专项逐格核对 Excel 原值、数值类型、显示格式及 PNG 完整数据行。
- 新区间表对照固定 Git 起点源码验证完整 TXT、返回值和原值，覆盖两种 alpha 与
  `1`、`1e-80`、`1e80` 三种数据尺度；每张表独立生成真实 Excel/PNG。
- 科学计数、百分比、计数、三位小数、None/NaN/Inf、零行、中文和特殊符号、等号开头标签、
  宽/长表的完整行列、取消和导出失败，继续由 G7/G8/G9/G10/G11 专项验证。
  Excel 保留未舍入数值和逐列格式；PNG 使用 display 字符串，不截图导出。
- 混合报告的 TXT 保存和原生 `tk_textCopy` 输出与完整原字符逐字一致；全选、保存失败、
  横纵滚动、清空后控件销毁、WM_DELETE_WINDOW 关闭及下一次输出重建窗口均实际执行。
  复制检查拦截 clipboard 命令，避免覆盖用户剪贴板。

GUI review 使用 `GUI/review`、`desktop-ui` 和 `break` 场景参考。
未找到适用的 `DESIGN.md`；沿用已整合的 ttk/Minitab 组件，没有重新设计界面。
已实际生成并目视核对 [大窗口](g12-evidence/mixed-window.png)、
[480×320 窄窗口](g12-evidence/mixed-narrow.png)、
[置信区间 PNG](g12-evidence/置信区间.png)、[中文/科学计数/缺失 PNG](g12-evidence/导出边界.png)。
菜单、数值、中文、横纵滚动条及底部操作栏可读；窄窗宽表通过横向滚动访问。
[生成脚本](g12-evidence/render.py) 额外在混合报告开头重复一次新区间表供视觉检查，
所以证据窗口有 **78 张表**；逐表映射后菜单 x 坐标均为 **48**。
对应 [完整 TXT](g12-evidence/混合报告.txt)、[区间 Excel](g12-evidence/置信区间.xlsx)、
[边界 Excel](g12-evidence/导出边界.xlsx) 可直接复查。

## 环境与测试结果

沿用项目启动器指定的 `.venv/Scripts/python.exe`，不新建环境：
Python 3.11.9、NumPy 2.4.6、pandas 3.0.6、SciPy 1.15.3、openpyxl 3.1.5、
Pillow 13.0.0、pytest 9.1.1、Tk 8.6.12。
已核对实际解释器与依赖导入路径，均来自项目环境；未使用 Codex bundled runtime。

| 验证 | 结果及证据 |
| --- | --- |
| 修改前完整 pytest | **1688 passed、4 failed、53 warnings，300.12 秒**；[原始日志](g12-evidence/baseline-pytest.txt)。 |
| 遗漏复现 | 两种 alpha 均没有 StatTable，**2 failed**；[先失败记录](g12-evidence/missing-entry-before.txt)。 |
| G12 首轮及旧守卫 | **10 passed、1 failed**；新测试读取屏幕外窗口坐标造成误报；[日志](g12-evidence/g12-first-tests.txt)。 |
| 混合用例校正 | 已改为逐表映射；随后将 Tk `Tcl_Obj` anchor 转成字符串再比较，生产代码未变；[中间日志](g12-evidence/mixed-tests.txt)。 |
| 混合报告最终专项 | **1 passed，13.95 秒**；77 表逐菜单导出和窗口行为全部完成；[日志](g12-evidence/mixed-final-tests.txt)。 |
| 源码清单测试 | **15 passed**；[主线程复核日志](g12-evidence/inventory-tests.txt)。 |
| 修改后完整 pytest | **1712 passed、4 failed、53 warnings，336.64 秒**；新增 24 个用例全部通过，失败节点与基线完全一致；[原始日志](g12-evidence/final-pytest.txt)、[前后对比](g12-evidence/failure-comparison.txt)。 |
| Patch / 空白检查 | **通过，无阻断项**；[逐文件审查](g12-evidence/patch-review.txt)、[清单计数/真实文件/新源码检查](g12-evidence/static-and-artifacts.txt)。 |

完整套件包含全部已迁移模块的结构化数据、GUI、TXT、Excel、PNG 和计算/绘图回归，
没有用只跑新增用例来代替全量验收。首轮出现的两类 GUI 断言问题只修正测试，
没有为了测试调整布局或统计实现。

### 已证实的既有失败

起点源码已经失败的四个节点：

```text
tests/test_startup.py::test_windows_launchers_resolve_their_directory_and_propagate_exit_code[0-win_start.bat]
tests/test_startup.py::test_windows_launchers_resolve_their_directory_and_propagate_exit_code[0-win_start_no_cmd_win.vbs]
tests/test_startup.py::test_windows_launchers_resolve_their_directory_and_propagate_exit_code[7-win_start.bat]
tests/test_startup.py::test_windows_launchers_resolve_their_directory_and_propagate_exit_code[7-win_start_no_cmd_win.vbs]
```

测试复制 BAT/VBS 和假的 `start.py` 到临时目录，却未准备启动器明确要求的
`.venv/Scripts/python.exe`；BAT 因环境不存在返回 1，VBS 等待隐藏 BAT 的 pause 导致 20 秒超时。
这说明旧测试夹具与当前启动器契约不一致，不能据此认定本次表格迁移破坏实际启动。
`test_startup.py` 与两个启动器均未修改，保留失败证据，不扩大 G12 范围。

53 条基线警告来自已有常量数据统计/坐标轴、相关椭圆特征值、tight_layout 弃用和
PI 的小写时间单位等路径；没有为消除警告修改计算、绘图或无关依赖。
最终运行仍为相同的四个失败、53 条警告；没有新增失败，没有隐藏、跳过或 xfail 这些既有失败。

## 逐文件 Patch Review 与复杂度审查

审查包含 tracked diff 和新增文件，独立 reviewer 另审查了生产改动、两个旧守卫、G12 混合测试与生成脚本。
未仅依据 pytest 通过下结论。

| 文件 | 审查结论 |
| --- | --- |
| `code/utilities.py` | 仅原区间报告的一个输出语句替换；从原计算局部变量取得原值，保留旧表作 TXT；无算法、签名、默认值或返回值变化。 |
| `tests/test_g4_quality_reports.py` | 仅给 mean_std_CIs 的 print_out 分支增加授权例外；其计算及其余文件 AST 守卫保留。 |
| `tests/test_g11_quality_tables.py` | utilities 仅略去该函数的报告分支再比较完整 AST；其他共享文件继续逐字比较。 |
| `tests/test_g12_inventory.py` | 有界静态扫描及分类约束，覆盖别名/旧出口与普通字符串反例；不增加生产注册表或文本解析。 |
| `tests/fixtures/g12_table_inventory.json` | 逐一审阅 39 个报告函数、7 个基础/非报告生产范围及其余文件；计数区分构造位置、固定逻辑表和参数化模板，例外均给理由。 |
| `tests/test_g12_tables.py` | 固定 Git 基线、原值和 TXT 比较、实际区间对话框及混合报告；复用已有报告生成器，导出执行生产菜单。另以 AST 保护 utilities 中所有非目标内容。 |
| `docs/g12-evidence/render.py` | 只生成证据；复用生产窗口和导出函数，逐表映射后才采集菜单坐标，所有窗口在 finally 关闭。 |
| 本文及 `docs/g12-evidence/` | 保存基线、失败复现、修正过程、最终回归、真实 TXT/Excel/PNG/截图，区分已验证与边界。 |

no-stop-gpt Audit：新增清单和扫描器有用户明确要求的防遗漏消费者；固定基线、形状/数值比较保护
TXT 和原精度；混合菜单与生命周期测试覆盖跨模块整合边界。
没有新生产抽象、缓存、fallback、配置、依赖、分页、虚拟化或全局重构。
公共组件、所有绘图文件、其他统计模块和启动器相对起点均无生产 diff。

## 验收边界与结论

**G12 迁移范围验收通过，全仓库回归保留四项已证实的既有启动器测试失败。**

82 张已确认的逻辑统计表均采用统一组件，56 个结构化生产位置纳入清单测试；
每表保留独立 Excel/PNG 菜单，混合报告与所有迁移模块专项回归通过。
原统计结果、完整 TXT 和绘图回归无新增失败，旧表格输出仅保留本文明确列出的非报告或兼容文本用途。
逐文件 Patch Review、复杂度检查及 Git Diff 检查无阻断性问题。
四项既有失败不属于本次迁移范围，证据完整保留；本次没有将完整套件描述为全绿。

未逐项人工点击完整主程序全部菜单；使用真实 apply/报告入口、原生 Tk 控件和实际导出文件验证。
未改写系统剪贴板，未在其他操作系统或缺少中文字体的设备验证。
沿用逐单元格 Label 和整张 PNG，超出已测宽长表的极大结果仍受 Tk 控件数与图像内存限制。
这些是现有组件边界，本次不增加分页或虚拟化。

复现命令：

```powershell
$python = 'C:\Users\shaoy\Documents\Minijmp\.venv\Scripts\python.exe'
$env:PYTHONIOENCODING = 'utf-8'
& $python -m pytest -q --tb=short
& $python docs/g12-evidence/render.py
```
