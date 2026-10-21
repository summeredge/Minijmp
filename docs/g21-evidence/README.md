# 通用绘图器界面验收记录（G21）

## 现有功能与已确认问题

- 实际入口为 `MiniJMP.plot_selected → Table.plotSelected → pandastable_local.plotting.PlotViewer`，保留原有 `plot2D/plot3D`、六类图形选项页、网格布局、动画、注释及保存格式。
- 已实现但不易理解：窗口标题为“绘图查看器”；工具栏只有“绘制所选数据 / 应用选项”，未说明前者重新取选区、后者沿用已载入数据。
- 已实现但不可见：任何时刻都没有显示当前绘图数据的行列数与列名。
- 实测缺陷：选项页固定高度 210，六个页面的实际需求高于该高度，复选框第二行被裁切；窗口缩至 800×700 时更明显。
- 实测缺陷：隐藏参数区按钮文字为 `Hide`，Tooltip 为英文；隐藏后按钮不变文字。
- 工具栏的缩小、放大、清除、保存保留原有图标按钮形态，未把图标换成文字；本次新增/重命名的主操作按钮同时显示图标和中文文字。
- 审查发现的初始化缺陷已真实复现：`PlotViewer(table=table, showoptions=False)` 在摘要标签使用 `pack(before=self.nb)` 时抛出 `TclError: window ... isn't packed`；且该模式按钮仍显示“隐藏参数区”。修复前未对该模式做界面截图，复现以真实 Tk 异常为准。

## 本次优化

1. 菜单与帮助标题统一为“通用绘图器”，保留 `plots.plot_wizard` 锚点和 `plot_selected` 回调。
2. 工具栏下方增加当前输入摘要：数据来源为工作表选区，显示行数 × 列数及最多 6 个列名，超出时标注总列数；空选区、尚未绘图分别提示。
3. 两个重绘按钮改为“从选区重新绘图”（重新调用 `getSelectedDataFrame`）和“应用设置并重绘”（沿用 `self.data`），并补充 Tooltip。
4. 参数区改为按内容高度排布，优先分配空间给设置区，避免短窗口裁掉复选框；绘图区保留剩余空间。
5. 隐藏/显示按钮中文化，并随状态切换“隐藏参数区 / 显示参数区”。
6. 默认窗口调整为 900×720，并设置 640×480 最小尺寸；六个选项页及高级功能保持原状。工具栏的缩小、放大、清除、保存仍是原有纯图标按钮。
7. 摘要标签在 Notebook 创建前打包，移除 `before=self.nb`；参数区用显式 `options_visible` 状态控制和切换按钮文字，初始文字与 `showoptions` 一致。

## 截图与手工检查

均来自真实 Windows Tk 窗口，用窗口句柄 `ImageGrab.grab(window=...)` 抓取并逐张打开检查。`capture.py` 是当前的优化后抓图脚本；优化前两张图由改动前的同一抓图入口生成，未覆盖或重绘：

- `before-1000x750.png`、`before-800x700.png`：优化前；可见固定高度导致的复选框裁切、英文 `Hide` 与缺失输入摘要。
- `after-1000x750.png`：优化后 1000×750，工具栏、摘要与完整两组设置均可见。
- `after-800x700.png`：优化后 800×700，参数未被裁切，图形区约 279 px 高。
- `after-150pct.png`：Tk 缩放 1.5 下 800×700，控件文字完整、无横向溢出。
- `after-640x480.png`：640×480 最小窗口，设置区可完整使用，图形区被压缩至约 59 px；这是有意优先保证设置可达，但此时不适合精细读图。
- `after-options-hidden.png`：隐藏参数区后图形扩展，按钮文字为“显示参数区”。

审查修复未单独新增截图；`showoptions=False` 的修复证据为真实 Tk 初始化/切换测试及 `after-options-hidden.png` 的隐藏态检查。

## 验证

- `tests/test_g21_plotter.py`：6 项通过，覆盖选区重新取数与仅应用设置的数据差异、摘要截断/空数据、显示隐藏、隐藏状态下 PNG 保存与关闭、帮助锚点和 `plot_selected` 回调；新增 `showoptions=False/True` 初始化、按钮初始文字及连续切换检查。
- `tests/test_phase1_plots.py tests/test_phase2_plots.py tests/test_g18_performance.py tests/test_menu_localization.py tests/test_dialog_translation.py tests/test_help_center.py`：326 项通过、0 失败、0 跳过。此环境中既有 `{}` 临时路径问题未复现。
- 上一轮修复前的记录：阶段 1/2 + G18 + 界面用例 153 项、翻译/菜单 170 项、专用窗口 110 项均通过；当时 `test_help_center` 因临时目录 `{}` 被 URL 编码失败 1 项，本轮该环境问题未复现。

## 未验证与限制

- 只验证 100% 与 Tk scaling=1.5；未在真实高 DPI 显示缩放（如 Windows 150% 系统缩放）下独立验收。
- 640×480 时图表高度很小，读图需隐藏参数区或放大窗口；未新增滚动式设置区。
- 嵌入式 `parent` 与独立窗口两种模式均做过初始化及连续切换的真实 Tk 检查。离屏测试窗口中按钮 `winfo_ismapped()` 可能为假，故用 `winfo_manager()` 验证 pack 状态；摘要标签在容器实际映射后可见。
- 未改第一/二阶段专用图形对话框、工作表、PI、CSV、SPC 或数值算法；未新增 `code/` 文件，无需更新 G12 清单。
- 共用 `addButton` 现在返回按钮对象；原调用方的返回值均未被使用，行为不变。
- 换行符检查：`code/pandastable_local/dialogs.py` 工作区曾变为 LF，已恢复原 CRLF（1876 处），仅保留 `return b` 单行真实修改。其余差异经 `git diff --ignore-cr-at-eol --stat` 核对为实际内容修改，无整文件换行符改写。
