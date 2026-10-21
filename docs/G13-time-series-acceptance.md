# G13 时间序列图验收记录

日期：2026-10-21。变更保留在当前工作区，未 commit、push 或 merge。

## 功能与实现范围

- `code/MiniJMP.py`：新增“图形 → 时间序列图”菜单及唯一对话框入口。
- `code/time_series_dialog.py`：继承 `SBDialog`，复用 `addListBox`、公共主题、错误输出、绘图按钮与图形窗口；提供时间/样本序号、多选数值列、变量轴归属、三种轴模式、各轴标题、图例和网格设置。
- `code/time_series.py`：集中处理输入校验、时间识别、稳定排序和原生 Matplotlib 绘图。全模块只有一处 `twinx()`，没有 Seaborn 聚合路径。
- `tests/test_g13_time_series.py`：37 项参数化用例，检查真实曲线数据、坐标轴、图例、导出和 Tk 控件。
- `tests/test_menu_localization.py`、`tests/test_help_center.py`：更新新增菜单与帮助主题的预期。
- `tests/fixtures/g12_table_inventory.json`：人工复核两个新增模块，不产生统计报告表；源码文件数从 69 更新为 71，统计表生产位置和 82 张逻辑表的计数不变。
- `docs/MENU_TRANSLATION.md`、`help/help-map.json`、`help/pages/graphs.html`、`help/assets/search-index.js`：同步菜单、离线帮助和搜索；索引用已有 `tools/build_help_index.py` 生成。

检查了 `sb_misc_dialog.py`、`sb_misc.py`、`plots.py`、`SBDialog`、`Dialogs`、公共画布/保存与事件处理。前三个文件没有修改，分组线图的计算与绘图路径保持原样。没有新增依赖或改动统计算法。

## 数据与轴归属规则

- 优先选择有效原生 datetime 列，其次尝试完整可解析的日期时间字符串列；没有有效列时默认样本序号。
- 时间模式升序稳定排序，重复时间戳全部保留；样本序号从 1 开始并保持原行顺序。
- 无效/缺失时间、非实数数值列、空数据、全缺失 Y、无穷值和重复列名均明确报错。布尔列不作为实数 Y 列。
- 不修改原 DataFrame；不聚合、重采样、插值、填充或平滑。Y 缺失值保留 NaN，曲线断开。
- 单轴模式所有变量归 Y1；双轴模式将 Y3 及以上归 Y2；多轴模式保留有效归属，轴编号范围为 1 至选中变量数。无效编号回到 Y1，超出上限的编号归当前最大可用轴。切换不会丢失变量选择。
- 只创建实际使用的轴。Y1 在左，右侧实际使用的轴依次外移 70 point；仅使用右侧轴时不创建空 Y1。
- 单曲线轴使用曲线颜色标注，多曲线轴使用统一深灰色；图例汇总所有轴。约束布局自动为外侧轴保留空间。
- 原图窗口的保存机制保持不变；此入口接入 `NavigationToolbar2Tk`，保留底部工具栏空间。重新绘图使用公共窗口替换流程，不累积旧轴。

## 自动化验收对应关系

| 验收范围 | 测试证据 |
| --- | --- |
| 菜单、变量选择、模式切换、非法归属、保留选择 | `test_menu_entry_reaches_real_dialog`、`test_real_dialog_selection_modes_assignments_and_titles`、`test_invalid_assignments` |
| datetime、字符串、时区、样本序号、乱序和重复时间 | `test_raw_values_stable_duplicates_missing_and_immutable` |
| 原始值、NaN、DataFrame 不变、各类无效输入 | 上述原始数据测试、`test_validation_preserves_previous_figure`、`test_integer_values_not_rounded_and_only_used_right_axes` |
| 三种轴模式、同轴多变量、共享 X、独立 Y、偏移与图例 | `test_modes_ownership_shared_x_independent_y`、`test_same_axis_sparse_axes_and_replot`、`test_many_axes_layout` |
| 多轴 PNG/SVG/PDF 保存及可见文字边界 | `test_multi_axis_layout_and_native_save` |
| 真实窗口平移、框选缩放、导航历史、保存、重复绘图和小窗口工具栏 | `test_real_viewer_replot_navigation_and_save` |
| 分组线图回归、生产路径无聚合、唯一多轴实现 | `test_grouped_line_existing_behavior`、`test_production_path_has_no_aggregation_and_single_axes_implementation` |
| 原公共窗口、菜单、对话框和离线帮助 | 相关 G6、菜单本地化、对话框翻译、帮助中心回归 |

## 环境与验证记录

使用项目 `.venv/Scripts/python.exe`：Python 3.11.9、pandas 3.0.6、Matplotlib 3.11.2；未使用 Codex bundled runtime，未修改依赖。

- 修改前完整基线：1712 passed、4 failed、53 warnings，见 `g13-evidence/baseline-pytest.txt`。
- 最终目标测试：52 passed（G13 新增 37 项，G12 清单 15 项），见 `g13-evidence/targeted-final-pytest.txt`。
- 相关绘图/菜单/对话框/帮助回归：316 passed，见 `g13-evidence/related-pytest.txt`；随后的小窗口工具栏、右侧刻度和原始数值表示调整由最终目标测试及完整回归覆盖。
- G12 清单专项：15 passed，见 `g13-evidence/inventory-pytest.txt`。
- 最终完整回归：1749 passed、4 failed、53 warnings，耗时 409.95 秒；见 `g13-evidence/final-state-pytest.txt`。与基线逐项比对失败 ID 完全一致，新增失败为 0，见 `g13-evidence/failure-comparison.txt`。
- 5 万行、3 条曲线、3 个轴：准备和绘图约 0.075 秒，首次 Agg 渲染约 0.168 秒；仅代表本机一次测量，不是 GUI 延迟保证，见 `g13-evidence/performance.txt`。
- `git diff --check` 以及实际 tracked/untracked 文件人工审查；统计算法与原分组线图无 diff。

四个已有失败均为 `tests/test_startup.py::test_windows_launchers_resolve_their_directory_and_propagate_exit_code` 的 BAT/VBS、返回码 0/7 组合。测试临时项目缺少启动器要求的 `.venv/Scripts/python.exe`；BAT 返回缺少环境错误，VBS 等待后超时。未修改无关启动器或它们的测试。

开发中曾遗漏 G12 对新增源码的清单登记，现已补齐；中间完整运行还与源码修改重叠，导致 `inspect.getsource` 读取位置错位。相关中间日志保留为 `development-full*.txt`；以上最终完整结果来自生产代码、测试和清单固定后的独立运行。

## 界面复核与复杂度审查

仓库没有 `DESIGN.md`，沿用项目 Tk/ttk 控件、主题和紧凑布局。使用 GUI 技能的原生桌面参考；真实 Windows 对话框和 1000×750、760×560 图形窗口已渲染复核，底部导航工具栏保持可见。截图及复现脚本位于 `g13-evidence/`，其中 `three-axes.png` 是现有保存接口的实际导出结果。

按 `no-stop-gpt` Audit 复核新增状态和边界：轴归属及各轴标题字典直接对应用户设置；没有缓存、后台刷新、兼容层或额外配置页。输入校验在替换窗口前执行，公共绘图函数也独立校验，分别保护已有图和直接调用入口；没有复制多轴创建代码。仅保留实现所需的两个模块，不向既有分组绘图模块加入新分支。

未验证其他操作系统、全部 Windows DPI/字体组合和任意数量的 Y 轴；实际验证包含六轴绘图布局、三轴窗口与多格式保存。轴很多或标题很长时仍需要合适的窗口尺寸。
