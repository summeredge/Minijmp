# G18 报告、绘图与交互性能优化

日期：2026-10-21。工作树：`C:\Users\shaoy\.codex\worktrees\2878\Minijmp`。
基线 HEAD：`38b907f0dcf62f234561838f3cca93ad0a8545ef`，任务开始时工作树干净。
所有变更保持未提交；未 commit、push、merge，未安装或升级依赖。

## 现有能力核对与变更清单

已阅读 G12/G13/G14 验收记录、G15 原始报告、原始 JSON 和 profile，并逐项核对当前源码。
G15 原交付位于 `%TEMP%/Minijmp-G15-20261021-101528`；本次使用的输入、环境和原始样本已复制到 [g18-evidence/g15](g18-evidence/g15/)。

| 能力 | 开始时状态 | G18 处理 |
| --- | --- | --- |
| G12 StatTable 原值、显示值、旧字符串协议及真实报告清单 | 已实现 | 完整复用；未新增生产模块或报告生产位置，清单不变。 |
| G13 原始时间序列、稳定排序、重复时间、NaN、多轴及原生工具栏 | 已实现 | 只改准备和同一次应用的数据交接；保留全部原始点和轴契约。 |
| G14 大表分页、页容量、累计 Label 预算、完整 TXT/复制、合并滚动与关闭清理 | 已实现 | 原样复用；未修改 `txt_output.py` 或 `MiniJMP.py`。 |
| G14 Excel 样式对象复用、PNG 分配前尺寸/像素保护 | 已实现 | 保留 PNG；Excel 进一步消除逐单元格的重复样式绑定和第二遍工作表遍历。 |
| SPC 常量控制限归并 | 部分优化已实现 | 复用归并结果，一次准备原始行和显示行，常量只格式化一次。 |
| StatTable 惰性 ASCII、通用后台导出/取消框架 | 未实现 | 本次未引入；现有 `str` 消费者和同步错误边界需要保留。 |

生产改动只有以下六个文件。

| 文件 / 入口 | 最终变化及消费者 |
| --- | --- |
| `code/linear_plot.py`：`fit_plot`、`multi_fit`、`multi_fit_orig`、`create_inset_grid` | 两版矩阵都把已计算、方向相同的 Pearson 结果交给椭圆绘制；矩阵统计使用传入的 α，修正非默认 α 时返回 CI 与图形水平不一致的问题。未输出报告时不构建两个 PrettyTable。当前版不创建空白上三角 inset；保留版内部创建时只建有效 GridSpec 单元，外部传入的完整轴数组仍按原方式隐藏空白轴。 |
| `code/control_chart.py`：`_print_spc_report` | 保留逐点原值、标签、缺失标记、显示精度及控制限；减少常量格式化，复用准备好的行。没有新增特殊原因规则或改变统计公式。 |
| `code/stat_table.py`：`export_excel` | 沿用普通 Workbook。每列建立只读的表头/文本/数值样式原型，浅拷贝 Cell、赋值后一次 append，消除每个单元格重新绑定字体、对齐及格式的成本。字体、对齐、原值、公式字符串防护、列宽和 B3 冻结保持一致。 |
| `code/time_series.py`：`prepare_time_series`、`time_series_plot` | 原生 NumPy 数值列不再装箱为 object；可空扩展类型仍保持 object，防止大整数与缺失值混合时浮点舍入。绘图接受本次调用刚验证的 `prepared` 元组，没有跨次缓存。 |
| `code/time_series_dialog.py`：`apply` | 替换旧窗口前只校验/排序一次，再使用相同结果绘图；下次应用仍重新校验，错误输入保留旧窗口。 |
| `code/pandastable_local/plotting.py` | 全部 8 处 `plt.cm.get_cmap` 改用 `mpl.colormaps.get_cmap`；保留原有色图语义和 `getcmap` 的 Spectral 回退，不增加版本探测或兼容包装层。 |

没有采用镜像方向的椭圆缓存：矩阵仍计算全部有序变量组合，避免把 X/Y 交换后直接复用同一个椭圆方向。20 变量的 Pearson 调用已从 590 降为 400；当前版轴数从 362 降为 191，保留版从 361 降为 190（含当前版容器主轴）。

## 测量方法与性能

解释器：`C:/Users/shaoy/Documents/Minijmp/.venv/Scripts/python.exe`，Python 3.11.9；NumPy 2.4.6、pandas 3.0.6、SciPy 1.15.3、Matplotlib 3.11.2、openpyxl 3.1.5。环境与 G15 一致，未使用 Codex bundled runtime。

[tools/benchmark_g18.py](../tools/benchmark_g18.py) 采用 G15 相同随机种子 20261021、输入生成顺序、尺寸和布局；每个场景独立子进程，预热一次，正式三次。数据生成、导入和 GC 排除在计时外；设置 BLAS 线程数为 1。每条原始记录含 wall/CPU 时间、重复编号、是否预热和 Windows 进程工作集，统计前验证完整输出。

矩阵同时记录总构建时间、每次真实 Pearson 调用的计时总和及剩余 Axes/Artist/调用组织时间；后者包含很小的返回矩阵组织和包装计时开销，不是纯 Matplotlib 内核。时序分别测准备、包含准备的构图、注入同一份已验证数据后的 Artist 构建、Agg 首绘/重绘、真实 Tk 显示和对话框应用。Tk 指标计至 `update()` 返回，不是物理屏幕延迟。Excel/TXT 在独立导出阶段测量。

原始 JSON 在 [baseline](g18-evidence/baseline/) 和 [after](g18-evidence/after/)，完整三轮范围、G15 中位值和所有阶段见 [performance.md](g18-evidence/performance.md) 与 [performance.csv](g18-evidence/performance.csv)。下列为正式样本的中位秒。

| 场景 / 阶段 | G15 | 本轮修改前 | 最终修改后 |
| --- | ---: | ---: | ---: |
| 当前矩阵，1000 点 × 20 变量，统计与构图 | 4.3148 | 6.9409 | 5.0086 |
| 保留矩阵，同规模，统计与构图 | 4.2259 | 6.3219 | 3.8919 |
| 当前矩阵，Pearson 累计计算 | 未分测 | 1.4110 | 0.7512 |
| 当前矩阵，Agg 首绘 | 1.0450 | 1.7205 | 1.3611 |
| 当前矩阵，1000 点 × 10 变量，真实 Tk 首绘 | 未分测 | 0.4976 | 0.4220 |
| 同规模，真实 Tk 重绘 | 未分测 | 0.4778 | 0.3741 |
| 50,000 点 SPC 完整报告 | 4.5603 | 2.6368 | 2.1186 |
| 50,000 × 7 Excel 完整导出 | 22.8857 | 8.8449 | 4.9365 |
| 100,000 点 × 3 时序变量，数据准备 | 0.0150 | 0.0166 | 0.0063 |
| 同规模，仅 Artist 构建（数据已准备） | 未分测 | 0.0794 | 0.0550 |
| 同规模，Agg 首绘 | 1.3779 | 1.6414 | 1.4960 |

Excel 导出进程累计峰值工作集由约 325.4 MiB 降到 282.2 MiB，包含导入、预热和完整 StatTable，不能解释为单次导出独占内存。普通工作簿仍随全部单元格增长，未宣称 O(列数) 内存。

`StatTable.__new__` 未改：50,000×7 构建观测 2.1779→1.7754 秒属于环境波动，不归因于 G18。完整 ASCII、原值和显示值仍随总数据量物化。

连续小表 profile 见 [layout-profile.txt](g18-evidence/layout-profile.txt)：一次 20 张 100×7 报告耗时 3.463 秒，其中真实 Tk update 2.326 秒、Label 构建约 0.926 秒，21 次 `configure_result_styles` 合计约 0.002 秒。为保留 G14 小表外观，不增加批处理队列、调整控件预算或重写布局。

本轮同机 G16/G17 也在运行完整测试，GUI/CPU 负载未完全隔离。GUI 场景曾出现明显波动，因此不把 Tk 时间变化或与 G15 的绝对差值当作纯算法收益；G15 是同输入历史参考，主要结论由本轮前后测量、调用次数和源码约束共同支持。

为核实波动，在本任务没有其它基准/pytest 并发时，按场景相邻执行修改前和修改后的时序 Tk、连续报告、宽表三轮测量；初轮样本保存在 `preliminary/*-initial.json`，汇总只采用补测结果。50,000 点时序 Tk 重绘为 1.6368→1.6759 秒，100×100 宽表呈现为 0.1932→0.4690 秒；这两条路径没有减少原始点或重写布局，不宣称改善。宽表区间分别为 [0.1659, 0.3929] 和 [0.1951, 0.6836] 秒，包含系统呈现波动。连续 20 表呈现为 4.7704→4.3093 秒；其实现 AST 相同，同样不将差值归为代码收益。

### 未保留的试验

`preliminary/named-style-excel.json` 是 NamedStyle 流式试验，增加了逐单元格查找开销；`preliminary/streaming-excel.json` 是改用只读 Cell 样式原型的流式试验，内存更低，但最终未采用。openpyxl 3.1.5 的 write-only 模式会在保存前创建临时工作表 XML，`Workbook.close()` 不负责清理这类失败中间文件；普通工作簿加样式复用更简单，也保留了原有保存失败窗口和工作表维度协议。这两份试验均不计入最终 after 或性能汇总。缺失值必须使用 General 格式的回归已加入逐单元格对照测试。

首轮相关回归发现 25 项 G5 类型断言失败：TXT/StatTable 原值相同，但内部 PrettyTable 点号被转为字符串。已恢复其整数和标签原始类型，并增加对修改前后构造表的值/类型比较；最终 SPC 计时对应修复后的 2.1186 秒，早期 1.5635 秒不作为交付收益。完整回归随后发现三项旧绘图 AST 冻结哈希未随授权优化更新：只刷新 `fit_plot`、`multi_fit`、`multi_fit_orig` 三条基线，保留检查机制和其它所有基线，数值和协议由 G18/G6 专项测试继续约束。

## GUI 与导出验收

[acceptance.py](g18-evidence/acceptance.py) 使用真实 Windows Tk 窗口和 `ImageGrab.grab(window=...)`；截图均已打开目视复核。结果见 [gui-export-acceptance.json](g18-evidence/gui-export-acceptance.json)，无 Tk 回调异常。

| 验收项 | 证据 |
| --- | --- |
| 两版矩阵布局、椭圆方向、中文标签 | `multi_fit-before/after.png`、`multi_fit_orig-before/after.png`；六个有效单元的布局、散点和正负方向椭圆一致。自动测试另核对 r、p、CI、cov、N 及逐点椭圆坐标。 |
| 分页末行与小窗口 | `report-first-page.png`、`report-last-page.png`、`report-small-window.png`；1,003 行末页的最后行/列一致，小窗口继续由外层滚动访问完整区域。 |
| 小表与 PNG | `small-report.png`、`small-report-export.png`；沿用 Label 外观；1,003 行 PNG 在分配前明确拒绝，完整数据可用 TXT/Excel。像素与宽度限制由 G14 测试覆盖。 |
| 完整 TXT / 复制 | `full-report.txt` 与原报告逐字符比较；真实 Text 全选/复制走生产函数，拦截剪贴板写入以保护用户剪贴板。选区与分页窗口契约继续由 G14 测试覆盖。 |
| Excel | `full-report.xlsx` 重新打开并检查全部 1,003 行、精度、格式、公式标签文本、末行和冻结窗格；新增测试与修改前逐单元格比较标题/空白单元格、字体、对齐、数字格式和列宽。 |
| 时间序列 | `time-series-window.png`、`time-series.png`；每条 1,000 原始点、重复时间稳定排序、NaN 断线、三轴和工具栏。G13 回归覆盖稀疏右轴、共享 X、可空大整数、导航及 PNG/SVG/PDF。 |
| vendor 真实曲线 | `vendor-real-curves.png`、`vendor-real-curves-export.png`；真实 PlotViewer 生成三条曲线，另测试 `replot → plotCurrent → _initFigure/plot2D` 的实际调用协议、两条曲线的原始值和 NaN 断线。G15 旧版是空图失败，无有效绘图基线，未把吞掉异常当作成功计时。 |
| 关闭清理 | 清空/关闭后释放原表引用并取消 idle 滚动；保存到不存在目录时传播 OSError，未遗留流式临时 XML。 |

## 测试、源码保护与 Patch Review

修改前完整 pytest：**1768 passed，53 warnings，488.51 秒**，见 [baseline-pytest.txt](g18-evidence/baseline-pytest.txt)。

最终局部契约测试：**92 passed**，见 [g3-g18-contract-tests.txt](g18-evidence/g3-g18-contract-tests.txt)；SPC 类型修复后的 G5/G11/G12/G18 **227 passed**，见 [spc-type-fix-tests.txt](g18-evidence/spc-type-fix-tests.txt)。F03/F07/F10 加完整 G13 的阶段回归 **52 passed**。

最终完整 pytest：**1785 passed，0 failed，53 warnings，258.74 秒**，见 [final-pytest.txt](g18-evidence/final-pytest.txt) 和 [final-pytest.xml](g18-evidence/final-pytest.xml)。其中 G7–G14 **394 项全部通过**，按最终 JUnit 逐项提取，见 [g7-g14-final-verification.txt](g18-evidence/g7-g14-final-verification.txt)。基线与最终均无既有失败或未解决失败，53 项警告一致；新增 17 项测试均通过。全套耗时差值受同机负载影响，不作为性能优化结论。

[baseline-source-check.json](g18-evidence/baseline-source-check.json) 确认六份修改前快照与基线 HEAD 一致（只归一化 CRLF/LF 进行对照）。[preserved-rendering-ast.json](g18-evidence/preserved-rendering-ast.json) 证明 `StatTable`、`TableBlock`、`configure_result_styles`、`export_png` 和完整 `txt_viewer` 的 AST 与修改前一致。

已逐个审查实际六文件 diff，并阅读新增回归、基准与验收脚本。`no-stop-gpt` Audit 的结论：

- 保留同调用内的 Pearson / prepared 数据交接：生产调用方已拥有同一输入和参数，不需要跨次缓存、失效标记或第二次校验；下次应用仍走输入边界。
- 保留有序 Pearson 矩阵和独立的旧入口：保证椭圆方向及公开返回结构；不为进一步减少对称计算引入转置规则或新结果类型。
- 保留每列三种只读 Cell 样式原型：数值、文本/缺失值和表头确实有不同格式消费者；克隆后只赋值，不修改共享样式。布尔值保持原 Excel 布尔类型及 General 格式。
- 保留完整 ASCII 和 G14 机制：旧字符串/TXT/选区复制和现有小表外观都有实际消费者；不增加惰性 str 兼容层、通用任务队列、后台导出或新的控件状态。
- 不采用流式工作簿和 NamedStyle 路径：前者扩大失败清理边界，后者实测增加开销；普通工作簿的一次写入已解决本次有证据的重复工作。

最终人工 Review 未发现阻塞项。详见 [patch-review.md](g18-evidence/patch-review.md)；[final-production.patch](g18-evidence/final-production.patch) 为六模块生产 diff，[final-source.patch](g18-evidence/final-source.patch) 另外包含测试、三条冻结基线、基准/验收脚本及测试所需旧源码快照。截图、三轮 JSON 和导出文件单独保存在证据目录，未塞入源码补丁。两个补丁均通过针对当前工作树的反向 `git apply --check --whitespace=error`；未执行实际 apply。最终测试后又核实六个生产文件 SHA256 与审查时一致、HEAD 未变化，见 [final-verification.json](g18-evidence/final-verification.json)。

非生产改动为 `tests/test_g18_performance.py`、基准/验收/汇总脚本和证据；另更新 `tests/fixtures/g3_computation_baseline.json` 的三条授权绘图哈希，以及 `tests/test_g3_computation_contracts.py` 的说明。哈希断言代码和其它计算基线完全保留。[review-self-checks.json](g18-evidence/review-self-checks.json) 另外核对布尔 Excel 值/General 格式，以及色图 None 和 Colormap 对象语义。

## 复现

```powershell
$python = 'C:\Users\shaoy\Documents\Minijmp\.venv\Scripts\python.exe'
# 各场景顺序运行；避免同时运行其它 GUI/基准/pytest。
& $python tools/benchmark_g18.py --source-dir tests/fixtures/g18_before --output <baseline目录> --scenario matrix --scenario matrix-orig --scenario matrix-tk --scenario table --scenario spc --scenario excel --scenario series --scenario series-tk --scenario dialog --scenario reports --scenario wide
& $python tools/benchmark_g18.py --output <after目录>
& $python docs/g18-evidence/acceptance.py
& $python docs/g18-evidence/summarize.py
& $python -m pytest tests/test_g18_performance.py tests/test_g13_time_series.py tests/test_g14_rendering.py -q --tb=short
& $python -m pytest -q --tb=short
git diff --check
```

实际证据目录已含 before/after，重跑请使用其它目录以保留本轮样本。GUI 验收是脚本驱动的真实 Tk 和截图复核，未覆盖所有 Windows DPI、主题、人工鼠标手感、物理显示延迟或长时间内存泄漏。Excel 仍同步、完整 ASCII 仍物化、所有原始时序点仍绘制；大数据下这些成本仍存在。
