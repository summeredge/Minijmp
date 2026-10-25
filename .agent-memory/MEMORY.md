# MiniJMP 工作记忆

## 当前状态（2026-10-25）

工作表列公式功能已实现并验证：计算器、一次性/关联计算、依赖重算、循环检测、只读编辑规则、工程持久化、右键“公式”子菜单与计算菜单。

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

## 验证基线

- `tests/test_worksheet_formulas.py` 20 项通过；`tests/test_worksheet_context_menu.py`、`tests/test_sheet_context.py`、`tests/test_file_io.py`、`tests/test_table_regressions.py` 相关用例通过；计算器真实 Tk 交互验证 25→50 自动更新。
- `tests/test_g12_inventory.py` 仅`python_files`计数与本任务新增文件相关；当前工作区另有并行任务文件（`improvement_*`）未纳入本任务清单。
- 阶段对比：`tests/test_improvement_chart.py` 33 项、`test_g5_spc_reports.py` 74 项（`-s`，与前者合并 107 项通过）。结果窗口在后端 `limit_details` 为空时不建标签页，有明细时显示并支持导出当前页；两个方向均有真实 Tk 断言。多套 Tk 测试合并偶发 Tcl 初始化错误，单独运行均通过；`test_dialog_translation.py::test_original_analysis_code_is_unchanged` 因已提交的 `fit_dialog.py` 差异失败，与本次改动无关。

## 当前限制

- 只支持工作表内 C 列引用，不支持跨表、Excel 语法、宏或完整 Minitab 函数库。
- 公式结果为浮点列；部分溢出或除零写为空值并提示。
- `.venv` 的 Tk 缺少运行时脚本，项目 Tk 测试改用 `C:\Users\shaoy\Documents\PythonEnvs\minijmp`。
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
