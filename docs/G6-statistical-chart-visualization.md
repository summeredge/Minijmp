# G6 统计图表视觉、交互与导出验收

日期：2026-10-20。范围为当前 `c5be/Minijmp` 独立 Worktree 的展示层。
参考目标文件的工程统计图表原则，继续使用 Matplotlib、Seaborn 和 Tkinter。
不修改统计公式、数据清洗、文本报告、返回字典、公共函数签名或 Dialog 流程。

## 检查清单与实际能力

执行前工作树干净；已读取 G1/G2 验收文档、依赖、相关测试及实际 GUI 调用链。
仓库没有 `DESIGN.md`，采用目标文件中的简洁、紧凑、数据优先规范及现有桌面控件约定。

| 图表/入口 | 原有能力与检查结论 | G6 结果 |
| --- | --- | --- |
| 单变量/分组/二维直方图 | `sb_histo.histo_n_fit/histo_full/histo_xy`；已有分箱、KDE、分组及拟合曲线 | 统一字体、轴框及布局；拟合曲线标明实际分布名；保留频数/密度双轴，图例置于图外 |
| 单/多变量箱线图、叠加散点 | `sb_boxplot.single_boxplot/multi_boxplot`，各自 Dialog 调用 | 共享排版，长类别名自动旋转；保留 `whis`、异常值、swarm、palette 和分组规则 |
| 区间、计数、散点、线图 | `sb_misc.interval_plot/count_plot/dot_plot/line_plot`；ANOVA 区间图复用该入口 | 统一排版；不改 Seaborn 区间估计、聚合、随机抽样或自定义区间逻辑 |
| 正态概率/Q-Q 图 | `NormTestDialog.apply` 调用 SciPy `probplot` | Y 轴保留实际变量名，中文与数学符号可显示；分位数和检验不变 |
| 普通/正交回归、相关椭圆 | `fit_plot` 供 `LinearFitDialog`、继承它的 `OrthoFitDialog`、`CorrelationDialog` 复用 | CI 使用绿色点线，PI 使用紫色虚线，图例明确中文名称；保留数据/普通红线/正交黑线等原语义 |
| 两份相关散点矩阵 | `multi_fit` 的 inset 三角矩阵与 `multi_fit_orig` 的 subplot 三角矩阵 | 两入口均覆盖；保留变量完整名称、顺序和统计配对；旧入口修复两变量时单 Axes 无法二维索引的问题 |
| 四联残差图 | `linear_fit_resid_test` → `resid_test`；另有 `ResidDialog.apply` | 四个子图分别命名；保留 QQ、直方图双轴、残差顺序控制图、拟合值散点及原有拟合线 |
| 连续/离散分布显示 | `cont_dist`、`binomial`、`poisson`，单/双分布 Dialog | 接入统一字体与轴框；保留 PDF/PMF、尾部标记、原有颜色与数值 |
| 分布拟合与比较 | `FitDistDialog` / `compare_dist` 原本输出报告；直方图可叠加所选分布的拟合曲线 | 保留现有拟合与排序。没有自动多分布拟合比较图、非正态拟合概率图，不在 G6 新增 |
| I、MR、I-MR、Xbar-R、Xbar-S | 共用 `x_plot`，以及 `limit_line/additional_SD` | CL/UCL/LCL 命名；辅助 σ 线降低权重且不重复打印重合数字；双图主图隐藏重复 X 刻度，保留原有抽稀及上下图数据 |
| P/NP、C/U | `p_np_plot/cu_plot`，四种 Dialog 复用 | 固定/可变控制限均保留；控制限使用虚线，图例外置，不遮盖数据 |
| SPC 异常点 | 当前没有独立特殊原因算法或异常索引绘图入口 | 不新增判定或虚构异常点，已有观测点数量、顺序与坐标保留 |
| 能力图与正态直方图 | `cpk_plot/hist_norm`；普通/子组能力 Dialog 复用 | Overall/Within 保留虚线/实线和双轴；LSL/USL 点划线、Target 点线；关闭 Within 后仍可显示 Overall 图例 |
| GRR | `grr_plot` 为部件测量散点及操作员分面，没有方差分量/百分比图 | 单图补 Y 标签，操作员面板留窄间隔，长部件名旋转；不新增未计算的分量或百分比 |
| 旧 pandas 绘图面板、StatsViewer | 现有六类配置面板，统计诊断仍由 statsmodels 绘制；`StatsViewer.showPlot` 已调用 `mplopts.applyOptions` 与 `tight_layout` | 尊重用户原有样式及字号，仅复用字体 fallback 和现有保存路径，不重写旧面板 |

## 修改位置与前后差异

| 文件/函数 | 修改 |
| --- | --- |
| `code/chart_style.py::font_families/style_axes`（新增） | 复用已安装字体，集中字号、淡轴框、已有网格的低干扰颜色；不修改数据、比例、locator、网格开关或统计颜色 |
| `code/sb_histo.py` 三种直方图及 `add_fig_legend_best_loc` | 使用真正的图外图例，删除先建临时轴图例再搬移位置的重复步骤；拟合分布名和右轴 Density 明确 |
| `code/sb_boxplot.py` 两函数、`code/sb_misc.py` 四函数 | 仅接入样式和自主创建 Figure 的 constrained layout |
| `code/linear_plot.py::fit_plot/multi_fit/multi_fit_orig` | CI/PI 名称与线型；各 PNG 保存包含外部文本；旧矩阵 `squeeze=False`，已有布局引擎时不再强行 `subplots_adjust` |
| `code/Residual.py::resid_test` | 子图标题、样式、整体布局与 PNG 边界；`linear_fit_resid_test` 的计算委托不变 |
| `code/basic_dialogs.py::NormTestDialog.apply` | 只改图轴变量标签和字体；统计调用及报告不变 |
| `code/cont_plot.py::cont_dist`、`code/binomial.py::binomial`、`code/poisson.py::poisson` | 仅在实际绘图分支应用样式 |
| `code/control_chart.py::limit_line/additional_SD/x_plot/p_np_plot/cu_plot` | 仅线型、命名、标注变换、图例、布局和导出边界；三个 SPC 计算函数未修改 |
| `code/cpk_plot.py::cpk_plot/hist_norm` | 规格线展示、图例开关修复、双轴样式及 PNG 边界 |
| `code/grr_plot.py::create_inset_grid/grr_plot` | 面板间距、单图 Y 标签和共享样式；原类别顺序及共同 Y 范围保留 |
| `code/plots.py::plot_viewer.setupGUI/close` | 保留 Figure 初始大小和 100 屏幕 DPI，启用 constrained layout；操作栏只横向填充；窗口持有鼠标处理器并在关闭时解除引用 |
| `code/pandastable_local/plotting.py::addFigure/PlotViewer.savePlot/MPLBaseOptions.applyOptions` | 不覆盖活动布局引擎；保存完整边界；在用户选定字体后追加中文字体，不重置其选择和字号 |
| `code/pandastable_local/handlers.py::DragHandler.on_release_event/key_press_event` | 仅真正拖动 Annotation 时读取单 Axes；移除普通释放的调试输出；仅 Delete 删除后重绘，避免处理器恢复生效后普通按键引用未赋值 Figure |
| `tests/test_dialog_translation.py` | 旧 AST 守卫仅精确规范化正态 Q-Q 图新加的两行展示代码，仍比较完整分析方法及统计调用 |

已确认长中文类别在 640px 箱线图中会重叠，因此共享样式只对分类/固定刻度且尚未旋转的
长名称（超过 10 个字符）或较多类别（超过 8 个）作 60° 右对齐。
不裁短名称，也不覆盖原有 45°/90° 设置；普通数值 AutoLocator 不受影响。
长变量名、单位仍原样呈现，不猜测或生成原数据没有的单位。

## 中文、负号与数学符号

保留已选字体优先级，追加 DejaVu Sans 及实际安装的中文字体。
当前 Windows 检出 `Microsoft YaHei`、`SimHei`、`SimSun`；其他平台只使用本机已安装候选，
没有字体文件、下载、缓存系统或新依赖。DejaVu 覆盖负号、希腊字母及数学符号，中文按字形 fallback。
不以 `axes.unicode_minus=False` 把数学负号替换为连字符。

测试渲染中文标题、坐标轴、图例、`α β μ σ χ² −1` 和 MathText `$R^2$`，
PNG/JPG/TIF/PDF/EPS/SVG 均无缺字警告，SVG 保留可核对的中文内容。
没有中文字体的其他系统不能保证中文完整显示；本次没有下载字体或声称跨系统实测通过。

## 保存与输出契约

- 保留 `PlotViewer.savePlot` 原文件类型列表、传入文件名、扩展名、默认目录及取消/失败行为。
- 直接函数仍以 `str(filename) + '.png'` 保存到调用者指定位置，格式 PNG、200 DPI；
  `cpk_plot` 的 `transparent` 参数保留。共享窗口仍默认 100 DPI，并使用已有 DPI 输入框。
- 仅增加 `bbox_inches='tight'`，完整包含图外控制限、规格标注、坐标轴和图例。
  文件像素尺寸因完整边界和留白调整而改变，**不承诺固定像素宽高**；Figure 英寸大小和屏幕 DPI 不因保存改变。
  测试检查实际文件格式、非空、合理宽高、DPI 元数据、透明角落与文本边界，不能只用 savefig mock 证明导出成功。
- 临时目录验证六种现有格式；直接回归/两份矩阵/残差/I/I-MR/能力/正态直方图逐一实际导出 PNG。
- `p_np_plot/cu_plot` 原 `filename` 参数没有保存实现，GUI 仍通过共享保存按钮导出。
  本阶段未把这个闲置参数扩展为新功能。

## 数据与统计不变性

对执行前原字节源码副本与修改后源码分别运行 **37 组**图表调用。
递归检查 **1770 个叶子值**，涵盖绘图曲线、集合路径、散点偏移、直方图矩形及其数据变换、
返回键及结构、数值和 `print_port` 报告文本。绘图数据、返回值与报告精确一致。
仅 I-MR 自动 Y 边界有约 `3.55e-15` / `1.78e-15` 的浮点末位差异，
符合标注创建与自动范围求值时机变化；没有修正、舍入或缩放绘图数据。

另验证所有已改绘图公共函数参数 AST 完全相同；`x_mR/xBar_R/xBar_S` 计算 AST 完全相同。
`utilities.py`、`txt_output.py`、`dialog.py`、`linear_fit.py`、`ortho_fit.py`、
`dist_fit.py`、`cpk.py`、`GRR.py` 的字节与执行前一致。
回归 CI/PI 逐点与原方程对照，QQ 与 SciPy 分位数对照；SPC 标量、常量列表、变控制限与
固定/不等子组、已有覆盖值逐一对照；异常索引算法未新增或修改。

## 专项与相关回归

项目解释器：`C:\Users\shaoy\Documents\PythonEnvs\minijmp\Scripts\python.exe`。
已验证 Python 3.11.9、Matplotlib 3.9.2、SciPy 1.14.1、pandas 2.2.3、Seaborn 0.13.2、
PrettyTable 3.11.0。符合项目 requirements；没有安装依赖，也没有使用 Codex bundled runtime。

新增 `tests/test_g6_chart_presentation.py` 与 `tests/test_g6_quality_charts.py`。
覆盖修改的各图类型、直接与实际 Dialog apply、普通/正交、两份矩阵、全部 SPC 类型、
长变量/类别名、中文/符号、导出格式、保存取消/异常、共享字体配置与 Figure 生命周期。
针对导出接收 Figure、格式、DPI、完整边界及 `addFigure` 布局守卫作精确 AST 检查，
并辅以实际对象与文件验证，没有仅靠关键词断言验收。

执行记录：

- 第一轮全量：749 通过、13 失败；失败随后在执行前原字节副本中全部复现。
- 排除上述已确认的旧失败后的完整回归：847 通过、13 deselected。
- 最终 G6 专项共 **102 项**（49 项通用图表、53 项质量图表）。
- 最后分类标签、鼠标释放/键盘回调及处理器清理修改后，G6 + 现有统计/生命周期 + G1 debug 功能复验：**178 通过，8 项旧 LF 断言 deselected，32 条上述数值/弃用警告**。没有新增失败。

完整回归与末次相关复验命令（PowerShell）：

```powershell
$python = 'C:\Users\shaoy\Documents\PythonEnvs\minijmp\Scripts\python.exe'
& $python -m pytest tests -q --tb=short -k 'not test_g1_files_keep_verified_head_lf_style and not test_scoped_old_report_builders_removed_and_lf_preserved and not test_windows_launchers_resolve_their_directory_and_propagate_exit_code'
& $python -m pytest tests/test_g6_chart_presentation.py tests/test_g6_quality_charts.py tests/test_statistics_regressions.py tests/test_g1_debug_output.py -k 'not test_g1_files_keep_verified_head_lf_style' -q --tb=short
```

未改动或豁免旧测试本身。13 项旧失败分别为：

1. `test_g1_files_keep_verified_head_lf_style` 的 8 例，以及
   `test_scoped_old_report_builders_removed_and_lf_preserved` 的 1 例：
   测试硬断言 LF，而本 Worktree 检出文件原为 CRLF。依任务要求保留换行，未批量转换文件。
2. `test_windows_launchers_resolve_their_directory_and_propagate_exit_code` 的 4 例：
   BAT 测试缺少它期待的 `.venv` 返回 1；VBS 同一环境提示窗口导致 20 秒超时。
   不属于图表范围，未改启动器。

矩阵完全相关导致的旧椭圆特征值警告、常量残差的正态检验/坐标警告、
旧绘图面板和 `ResidDialog.set_tight_layout` 的弃用警告均保留。
完整回归还记录过一次 Tk Variable 在非主线程析构的警告；本次持有的鼠标处理器在关闭时显式解除引用，
相关弱引用释放及重复开关窗口测试通过，不以这一局部处理宣称消除其他窗口的所有 Tk 警告。

## GUI、渲染与资源

真实 Windows Tk 测试创建并调整 1000×750 / 640×480 窗口，覆盖 Tk scaling 1 和 2。
检查图例/轴标签处于画布内，操作栏可见，DPI 输入影响实际保存文件。
通过画布事件系统分发真实 `MouseEvent`，确认鼠标处理器在 GC 后仍存在、多图普通释放不访问缺失单 Axes；`a`/`delete` 的真实 KeyEvent 分发不报错。
关闭窗口后处理器弱引用释放，table 引用清除；原有三次创建/关闭、Figure 弱引用和序列化副本回归保留。
自主绘图每次仅新增一个 Figure；双轴与 inset 数量保持原有语义。

已逐图查看回归、矩阵、残差、能力、拟合直方图、GRR、属性图和 I-MR 的实际渲染；
检查出 MR 零下限重合数字后只移除辅助线数字，保留控制线及辅助线全部坐标。
自定义统计窗口原有保存/DPI 操作，没有 Matplotlib NavigationToolbar；本次没有新增工具栏、后台线程或重绘监听。
旧绘图面板的平移/缩放配置、菜单流程、保存和关闭方式保持。
未由人工逐项点击文件对话框、拖动 Annotation 或测试其他操作系统。

## Worktree 隔离、Review 与冲突

仅操作当前 `C:\Users\shaoy\.codex\worktrees\c5be\Minijmp`。
未切换或清理其他 Worktree，未读取 G3/G4/G5 未合并源码，未 cherry-pick/rebase/reset，未 commit/push/merge。
执行前无未提交修改；修改保留原文件换行，新增文件使用 LF，没有整文件格式化。
已逐文件审查完整 diff、独立只读 Patch Review 和 no-stop-gpt Audit。
共享样式直接服务实际重复入口，长类别旋转复用于 GRR；保活引用有真实事件消费者且关闭即释放，
没有新增主题管理器、计算缓存、异常判定、兼容层或依赖。

潜在后续合并冲突按函数限定：

- **G3**：`linear_plot.py::fit_plot/multi_fit/multi_fit_orig`、`Residual.py::resid_test`；
  `basic_dialogs.py::NormTestDialog.apply` 只有末端图轴标签/样式修改，合并时不能覆盖其他报告代码。
- **G4**：`cpk_plot.py::cpk_plot/hist_norm`、`grr_plot.py::create_inset_grid/grr_plot`；
  `qc_dialog.py`、能力/GRR 计算文件未修改。
- **G5**：`control_chart.py::limit_line/additional_SD/x_plot/p_np_plot/cu_plot`；
  保留同文件前三个计算函数及报告分支；`ctrlchart_dialog.py` 未修改。
- 通用保存/字体位于 `plots.py`、`pandastable_local/plotting.py`、`handlers.py`，
  后续 GUI 分支合并时应保留本次布局守卫和处理器引用生命周期。

## 留在本阶段之外的问题

- U 图无标签列的数据路径先除以样本量，随后 `cu_plot` 再除；有标签路径传原计数，两者不一致。
  这是数据/算法边界问题，留给 G5，不在 G6 修正。
- NP 直接函数按首个样本量缩放；GUI 当前固定样本量。`additional_SD` 的除以 3 也保持原计算。
- 两个能力 Dialog 的位置参数顺序与 `cpk_plot` 规格签名相反，目前依赖 `cpk` 排序规格值。
  G4 如果修改校验需一起核对；G6 保留已验证的当前结果。
- 极多变量/极长类别名称超过有限画布时仍需要使用已有窗口调整及导出；不新增分页或标签折叠系统。
- 没有特殊原因判定、自动多分布比较图或 GRR 方差分量图时，不虚构统计量或新增算法。

**G6 展示层验收完成，保留上述已复现的环境测试失败和算法边界。**
最终源码及测试 diff 已审查，独立 Patch Review 无阻塞；`git diff --check` 通过，
16 份已改既有文件的换行风格与执行前一致，受保护模块字节不变。
临时基线、导出图和测试副本保留于未跟踪的 `.g6-baseline/`：删除操作被执行策略拒绝，
没有绕过限制。这些是本次验证产物，不属于生产补丁；专项测试和本验收文档为正式交付。
没有自动 commit、push 或 merge。


## 后续：用户授权合并到 main

以上为独立 G6 实施记录。随后用户明确要求“合并到 main 分支”，授权提交及本地合并。

- 正式 G6 修改提交为 `0320b7b`，分支 `codex/g6-statistical-chart-visualization`。
  `.g6-baseline/` 仍只留在 G6 Worktree，没有纳入提交或复制到 main。
- 合并前 main 为 `1320c68`，工作树干净，已包含 G3/G4/G5；采用非快进合并。
  `Residual.py`、`control_chart.py`、`linear_plot.py` 和 Dialog AST 测试自动合并，无文本冲突。
  已确认 main 的 SPC 计算函数、G5 报告 helper 及八份受保护统计/公共模块保持原样。
- 使用 main 项目既有 `.venv`：Python 3.11.9、Matplotlib 3.11.2、SciPy 1.15.3、pandas 3.0.6、
  pytest 9.1.1；未安装依赖或修改环境。
- 首轮合并回归为 **584 通过，10 项旧阶段展示基线守卫失败**。10 项均因 G3/G4/G5 曾冻结
  整个绘图实现，而 G6 明确获准调整展示。只更新四个 G3 绘图 AST、五个 G5 绘图 AST 及
  两份 G4 绘图源码的基线引用；计算函数原有基线不变，未删除或跳过测试。
- 基线相关 **35 项全部复验通过**。与此前 584 项功能/数值/GUI/导出结果合计覆盖本轮
  **594 个不同用例，最终均通过（分批验证）**，包括 G6 全部 102 项、G3 回归/计算守卫、
  G4 质量报告、G5 SPC 报告、G1/G2、统计与生命周期回归及 Dialog 分析源码守卫。
  main 的换行测试正常，本轮未排除任何测试；保留 39 条原数值/弃用警告。
- 合并增量及基线更新已逐项审查，`git diff --check` 通过；保留 G3/G4/G5 已合入的报告。
  没有运行无关的全仓库测试，没有推送远程，也没有修改另外两个独立开发 Worktree。
