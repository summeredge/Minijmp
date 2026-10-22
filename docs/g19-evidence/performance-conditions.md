# G19 性能条件与解释边界

使用项目 `.venv/Scripts/python.exe`，环境和实际库路径见 `environment.json`。种子 `20261021`，`PYTHONHASHSEED=0`，OpenBLAS/OpenMP/MKL/NumExpr 单线程。主任务性能阶段没有并行运行自己的 pytest 或第二组基准；不能保证桌面后台服务、电源与物理显示系统完全隔离。

完整 pytest 的总时长不作为性能基准。每个普通有效场景预热一次，正式三次，输入准备/导入/GC 在指定计时外；具体计算函数自身的清洗或报告工作按原工具边界保留。冷积分例外：三个独立进程各测一次冷调用，进程内暖缓存另列。

## 来源与可比性

| 结果家族 | 本轮来源 | 基线性质与范围 |
| --- | --- | --- |
| 统计 | 六个 `statistics-F*.json`，原 `tools/benchmark_statistics.py` | G16 优化后原三次样本作为**历史参照**。输入规模相同也不能视为同时负载或纯算法 A/B；已核对 `multi_var` 默认非报告模式与 G15 一致。LR 入口耗时有效不意味着其统计定义正确，B-01 单独阻断验收。 |
| 数据 | `data/performance.csv`、`benchmark-environment.json` | 冻结旧函数和当前函数在本轮交替运行，逐次校验结果后写成功记录；每侧三次。旧搜索仅对 pandas 3 的 mask dtype/iteritems 作兼容修正，因此比较名为 before_compat_only，不能写成原失败版本成功。 |
| 报告绘图 | `render-before/`、`render-current/` | 同一 G18 脚本、同输入、同阶段。本轮 before 从仓库 `tests/fixtures/g18_before` 重放 G18 六模块，其余依赖来自当前集成代码，不是整个 G15 环境。vendor 旧版无有效曲线基线，只记录当前实际曲线性能。 |
| 补充 | `supplemental/raw/`，39 个 G15 原场景 | 原参数保留，仅 profile=false、timeout=180。G15 脚本原封复制，输出到 G19；原报告/环境/场景集合归档在 `g15-reference/`。未执行的历史规模只说明代表关系，不伪称三轮完成。 |

数据基准包含 1,000/10,000/50,000/100,000 行，数字清洗在万行时另有 20/40 列。统计工具包含 38 个规模/方法组合。当前版/保留版 20 变量矩阵、50,000×7 完整 Excel、50,000 点 SPC、100,000×3 时序、50,000×3 Tk/对话框、20 张 100×7 表、100×100 宽表均按原工具规模执行；额外 40 变量、大表、vendor 50,000 点等见补充清单。

## 阶段解释

- `compute`：函数本体；不是 GUI 菜单至屏幕延迟。
- `data_prepare`：列清洗/时间排序等准备；时序的 `plot_build_including_prepare` 包含准备，不能与仅 Artist 构建混算。
- `report_build`：完整 StatTable/ASCII/SPC 构建；未声称惰性字符串或恒定内存。
- `matrix_and_artists`：矩阵统计与轴/Artist/报告组织；`pearson_seconds` 是真实 Pearson 调用累计，`axes_artists_and_report_seconds` 为总量减 Pearson，包含小量包装计时开销，不是纯 Matplotlib 内核。
- `agg_first_draw`/`agg_redraw`：离屏 Agg 绘制；不能代表真实 Tk 更新。
- `tk_*_to_updated`：真实窗口操作到 Tk `update()` 返回；不是物理显示延迟、鼠标手感或无限连续交互保证。连续报告最后一块和宽表均为分页 Treeview；单页小表的 last-page 空操作不应计为分页收益。
- `export_excel`/`gui_txt_save`：实际写盘，Excel 包含普通工作簿保存；不包含构建输入 StatTable。CSV 检测与正式读取分开。

## 波动、内存与剩余成本

CSV 保存每次样本、中位数、最小值、最大值、基线类型与证据路径。历史比值只作参照，不能凭其超过 1 判定退化；本轮 before/current 的阶段和输入一致才有比较意义。宽表、小表、Tk 重绘还结合范围、当前代码是否改变与系统呈现波动判断，不预设必须优化。

G18/G15 Windows 工作集字段为截至该阶段的进程生命周期累计峰值，包含导入、输入与预热；不是单次操作独占分配，也不能以 RSS 未回落判断泄漏。未额外承诺长期泄漏、任意规模内存或所有 DPI/主题。

20/40 变量小尺寸图的 constrained_layout 警告保存在原始日志；它反映高密度布局的可见性限制，不能当作统计值错误，也不能声称任意变量数标签都清晰。实际四变量截图与逐点坐标/CI测试另有证据。

普通工作簿同步导出、完整 ASCII、原始时序点全部绘制、连续小表 Label 布局及极宽列管理仍有成本。没有引入后台线程、队列、缓存状态机或流式清理协议；未出现稳定、局部且有明确定义的性能缺陷时保留现有实现。
