# MiniJMP 工作记忆

## 当前状态（2026-10-27）

beta.4 版本准备：beta.3 基线 `d21a924abf6f437f82e2736ac09c5a38dc636d5f`；pandas 迁移提交 `d321c59806230572bc6d7ba2c752ad8c80a62891`。版本提交可由 `git log -1 --format=%H` 在提交后读取；产品/包/EXE 版本分别为 `v0.1.0-beta.4`、`V0.1-beta4`、`0.1.0.4`。迁移全量历史结果 3810 passed；本轮发布工具 25 passed、启动测试 17 passed。Windows EXE/ZIP 已在版本文件未提交状态构建，资源版本和按进程 ID 的两次窗口冒烟已核实；原冒烟脚本误识别 Edge。版本提交 `e770bb9b22bca9aad2de3e167f77407a5608dff5` 已推送；标签待最终干净源码的构建和验收后创建。办公终端与实际 PI Server 未验收。详见当日日志。

beta.3 已冻结在提交 `d21a924abf6f437f82e2736ac09c5a38dc636d5f`；迁移开始时 `main`、`origin/main` 相同且工作区干净，未创建标签。pandas 3.0.6 迁移已完成并由提交 `d321c59806230572bc6d7ba2c752ad8c80a62891` 固化，正式依赖 `requirements.txt` 与 Windows Python 3.11 锁文件一致。数据安全写入、CSV/Excel 精度、旧 API、类别/日期时间绘图、分组语义及绘图 DPI 全局状态已修复；统计计算定义未改。

验证：`.venv` Python 3.11.9、pandas 3.0.6 及锁依赖检查通过，`tools/release_env.py` 五项 PASS；第一层 473、第二层 70、第三层 202、绘图 DPI/图片导出专项 180 项通过。收尾后全量 `pytest -q --tb=short` 为 **3,810 passed、0 failed、0 skipped、120 warnings**（978.26 秒）。历史 AST 守卫已修：`CorrelationDialog.apply` 的 `pearson=self.cor_p.get()` 按严格形态断言归一化后仍完整比较快照；同一函数内 `CpkSubDialog.apply` 的 REVIEW-018/019 差异复用整函数 SHA256 守卫还原。快照未改、测试未跳过；新增 Pearson 开/关运行时测试。详见 `docs/release/pandas3-migration-report.md` 与 `logs/2026-10-27.md`。限制：`.xls` 超精度原始 token 不可恢复；未接实际 PI Server、未做 EXE/ZIP 构建与办公终端安全策略验收。

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
