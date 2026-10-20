# G1 公共统计输出规范及验收记录

本阶段增强文本结果窗口与现有 PrettyTable，纠正已确认的统计解释。
没有修改统计计算算法、返回字典、已有函数签名、菜单或参数弹窗；没有提交、合并或推送。

## 后续报告采用的公共约定

- 继续通过现有 `print_port` 输出文本，不增加报告引擎。
- 二维表格优先复用 `utilities.gen_table()`，返回值仍是 PrettyTable。
  首行是表头，其余是数据；默认左对齐、多行单元格顶端对齐。
  保留原始数值及文本，调用者负责精度，也可以设置 `table.align[column]` 等原生选项。
- PrettyTable 已按字符显示宽度处理中文，无需手动按字符串长度补空格。
  对齐表格优先使用 ASCII 边框和运算符，避免字体对东亚模糊宽度字符的不同处理。
- 文本窗口禁止自动折行，提供水平和垂直滚动条；操作栏优先分配空间。
  字体优先选用已安装的中英文等宽字体，在当前 Windows 环境使用新宋体。
  偶数像素字号使中文宽度为半角字符的两倍，避免 DPI 取整错位。
  没有中文等宽字体时保留 TkFixedFont，不能保证所有平台的中文像素对齐。
- 保存使用 UTF-8，保留平台换行行为；取消不改动文本，失败显示错误。
  清空、复制、全选和 Ctrl+A 使用现有 Tk 控件机制。
  主题仍复用 `dialog_style`、`apply_dialog_theme`、`text_widget_colors`。
- 使用“原假设 H0”“备择假设 H1”“总体均值”“总体标准差”“总体比例”
  “双侧置信区间”“单侧置信上限/下限”。比例参数 p 与 p 值按上下文区分。
- p 值是在原假设及检验模型成立时，得到当前或更极端检验统计量的概率，
  不能解释为原假设为真的概率，也不能解释为总体正态或参数等于指定值的概率。
- 置信水平描述重复抽样时区间覆盖总体参数的长期比例，
  不能解释为已观测区间内固定参数的概率。单侧上限对应形如 `(-∞, U]` 的置信集合，
  单侧下限对应 `[L, +∞)`；比例和标准差同时受其参数空间限制。
- 单侧检验的 H1、尾概率、单侧置信限必须一起核对。
  继续保留两样本 t 检验的 `μ2 - μ1` 方向及两比例检验的 `p1 - p2` 方向。
  本阶段没有批量调整报告结构、英文标题、数值精度或新增统计指标。

## 修改文件与修复内容

| 文件 | 内容 |
| --- | --- |
| `code/txt_output.py` | 等宽字体、DPI 校正、双向滚动、窄窗工具栏、中文标题、复制/全选、UTF-8 保存及错误反馈、主题事件刷新；删除关闭调试输出 |
| `code/utilities.py` | PrettyTable 公共格式、置信区间及 Pearson/正态性检验解释；删除参考线坐标调试输出 |
| `code/t_test.py` | 单样本 t/Z 的 p 值解释、配对差值 H0 符号、置信区间和单侧检验文字；删除错误的单侧 p 值总是双侧一半的注释 |
| `code/linear_fit.py` | 系数/回归 F 检验、失拟及残差正态性解释 |
| `code/chi_sq.py` | 标准差左尾标签、抽样分布区间与参数置信区间的区分、Bonett 适用性文字 |
| `code/proportion_test.py` | 明确双侧/单侧列及置信限；区分二项精确检验与 Clopper-Pearson 置信限，准确指明调整 Blaker 行 |
| `code/nonpara_cor.py` | Spearman/Kendall 的 H0/H1；不把零秩相关等同于变量独立 |
| `code/plots.py` | 删除创建与关闭窗口的无用调试输出 |
| `tests/test_g1_statistics_output.py` | 统计数值、输出文字、尾概率、置信限、表格显示宽度、源码禁用错误解释的检查 |
| `tests/test_g1_text_output.py` | 真实 Tk 控件的字体像素、窗口滚动、保存/取消/失败、清空、复制事件、主题与生命周期检查 |

工作区原有 `code/pandastable_local/core_orig.py`、`code/pandastable_local/headers.py`
及 `tests/test_table_regressions.py` 的未提交修改未由 G1 改动。

## 实际验证（2026-10-20）

使用项目启动配置指定的现有解释器 `.venv/Scripts/python.exe`：
Python 3.11.9、pandas 3.0.6、SciPy 1.15.3、PrettyTable 3.18.0、wcwidth 0.9.2。
未安装依赖或调整环境。

- 修改前的现有回归：127 通过、4 失败。
  失败均为 `test_startup.py::test_windows_launchers_resolve_their_directory_and_propagate_exit_code`。
  临时项目没有启动器要求的 `.venv`，BAT 返回 1，VBS 两例超时。
- G1 新增测试：46 通过。
- G1 加直接相关现有回归：160 通过、7 条现有数值/绘图警告。
  执行命令：

  ```powershell
  & .\.venv\Scripts\python.exe -m pytest tests/test_g1_statistics_output.py tests/test_g1_text_output.py tests/test_statistics_regressions.py tests/test_statistical_edges.py tests/test_supplemental_stability.py -q --tb=short
  ```

- 扩大到菜单、弹窗、启动回归：337 通过、2 失败、4 项上述已知启动器失败被排除。
  一项为旧绘图面板使用 `pd.to_numeric(errors='ignore')`，当前 pandas 不支持该参数值；
  单独执行同一测试仍失败，位置为 `pandastable_local/plotting.py:720`。
  另一项为 Tk 创建窗口时未找到可用 `tk.tcl` 的初始化失败；直接相关测试组随后独立执行通过，
  尚未定位该环境/测试顺序问题。没有将它报告成全量回归通过。
- 六个统计模块去除打印分支后的 AST 对照一致，确认计算语句、签名及返回契约未变。
  使用修改前源码快照与当前源码执行 70 次对照调用，覆盖正反方向、不同 α、
  合并/非合并方差、输出开关，全部返回键和值精确一致（包括数组及 NaN）。
- 源码禁用检查覆盖已确认错误的每个副本，而非只检查一份输出。
- 在真实 Tk 中验证中文/ASCII 表格分隔线的像素位置相同，
  测试 Tk scaling 为 1、1.33333、2、2.66667；480×320 和 1000×750 均可滚动且工具栏可见。
- 已查看实际窗口截图：普通亮色与窄窗暗色，表格对齐，横向内容通过滚动查看，操作栏可见。
  主题测试使用实际 ttk 浅色/深色主题切换，保留文本、字体与选区。
  原生复制事件已验证；为避免覆盖用户剪贴板，测试在控件绑定处截获复制事件。
- `git diff --check` 通过。未验证 macOS/Linux 实机字体、系统外观自动切换、
  文件选择器人工交互及系统剪贴板接收端。

## 范围外计算问题：只记录，不改算法

1. `proportion_test.py:44`：Fisher 右尾使用 `cdf(max(e1 - 1, 0))`。
   `prop_2sample(n1=10, n2=10, e1=0, e2=5)['p p1>p2 Fisher']`
   返回 `0.9837461300309598`；此时右尾包含全部可行取值，应为 `1.0`。
   `scipy.stats.hypergeom(20, 5, 10).sf(-1)` 可复现参考值。
2. `utilities.py:226`：完全相关分支固定使用 `r_z = 10000`。
   `pearson_correlation([1,2,3,4,5], [5,4,3,2,1], print_out=False)`
   返回 `r = -1`，但置信区间为 `(1, 1)`，与负相关方向矛盾。

## Patch Review 结论

已审查 G1 的全部源码、两份新增测试及本记录，核对输出消费者、计算边界、窗口布局、
主题回调、保存错误和窗口关闭路径；不是仅依据测试通过。
统计改动均为文字与标签，数据和计算语句未变。
调试打印没有业务消费者，保留正常统计报告、数值收敛警告、诊断错误和脚本演示入口。

已按 no-stop-gpt Audit 审查新增字体状态、字体候选、主题绑定、滚动条和全选方法：
各自直接服务中文对齐、主题或操作需求，没有报告抽象层、缓存、依赖、额外配置或兼容框架。
本阶段未发现需要继续修改的 G1 补丁问题；上述既有计算边界和扩大回归失败保留为明确限制。

## G1 收尾修复（2026-10-20）

本次仅补齐上轮验收遗漏，不重新实施 G1，不启动 G2。

### 调试输出与消费者核实

| 文件及具体函数 | 本次删除 |
| --- | --- |
| `code/basic_dialogs.py` / `DescribeDialog.apply()` | `print(x)` |
| `code/control_chart.py` / `x_mR()` | `print("mr", mr)` |
| `code/ctrlchart_dialog.py` / `NPDialog.apply()`（P 图继承此路径） | `print(NP)` |
| `code/fit_dialog.py` / `LinearFitDialog.apply()` | 坐标轴调试打印 |
| `code/fit_dialog.py` / `CorrelationDialog.apply()` | 第二份坐标轴调试打印 |
| `code/dialog.py` / `Dialogs.__init__()` | 有界搜索补查出的 `Gen new dialog` 打印 |

以上六处均直接调用内置 `print`，没有返回值或后续消费；应用报告仍由
`self.app.print` / `print_port` 进入结果窗口，没有读取上述 stdout 的业务路径。
对 `code/` 顶层统计、质量、图形及其弹窗模块进行了 `rg` 和 AST 有界检查，
区分了局部 `print = print_port`、受 `print_out` 控制的正常报告和直接调试打印。
保留二项区间收敛警告、方差检验报告、错误提示和 `__main__` 演示。
`fit_jsu()` 的打印仅由分布拟合模块演示调用；`on_palette_selected()` 的打印仅由
配色模块演示入口调用，均未当作正常功能路径删除。
未改动底层第三方表格组件或列宽任务文件。

### 换行符与实际 Diff

使用 `git show HEAD:<path>` 的原始字节与工作区字节逐文件比较，确认
`chi_sq.py`、`linear_fit.py`、`nonpara_cor.py`、`plots.py`、`proportion_test.py`、
`t_test.py`、`txt_output.py`、`utilities.py` 的 HEAD 均为纯 LF，工作区此前均为 CRLF。
只将这八份工作区内容的 CRLF 转换为 LF，并与收尾开始时的快照验证：
**除换行符以外全部字节一致，保留全部已有 G1 修改**。
本次删除打印的五份源码也沿用各自 HEAD 的 LF。
没有使用 reset、checkout、restore 或回写 HEAD 内容，没有修改 Git 配置。

除常规 Diff 外，额外使用 `git -c core.autocrlf=false diff` 检查原始差异，
避免本机 `core.autocrlf=true` 隐藏换行符问题。八文件的实际增删行如下，均为局部修改：

| 文件 | 新增 / 删除 |
| --- | --- |
| `chi_sq.py` | 13 / 13 |
| `linear_fit.py` | 6 / 6 |
| `nonpara_cor.py` | 2 / 2 |
| `plots.py` | 0 / 2 |
| `proportion_test.py` | 14 / 14 |
| `t_test.py` | 26 / 26 |
| `txt_output.py` | 43 / 16 |
| `utilities.py` | 19 / 12 |

本次五份清理源码的增量严格为六行打印删除，没有其他语句变更；
去掉这六行后，与收尾前快照的全文及 AST 一致。
逐文件检查实际 Diff，未出现整文件删除重加；`git diff --check` 通过。
三个特别保护文件 `headers.py`、`core_orig.py`、`test_table_regressions.py`
在本次操作前后的 SHA-256 完全一致。

### 收尾测试与 Review

- 新增 `tests/test_g1_debug_output.py`：24 项通过。
  逐一定位指定文件、类、函数和两份回归/相关实现，检查旧模式在对应文件中消失；
  执行描述统计 apply、两种移动极差窗口及 sigma 设置、NP/P 两条路径、回归/相关 apply，
  检查完整控制图字典、实际绘图数据、回归结果、坐标轴标签及原有报告输出。
  另外覆盖公共弹窗构造和八份文件的 LF 字节约束。
- 本次新增测试、原 G1 测试和直接相关现有回归：**184 通过，7 条原有警告**。
  仍使用同一项目 `.venv/Scripts/python.exe`，未安装或升级依赖。

  ```powershell
  & .\.venv\Scripts\python.exe -m pytest tests/test_g1_debug_output.py tests/test_g1_statistics_output.py tests/test_g1_text_output.py tests/test_statistics_regressions.py tests/test_statistical_edges.py tests/test_supplemental_stability.py -q --tb=short
  ```

- 扩大回归加入 `test_dialog_translation.py`、`test_menu_localization.py`、`test_startup.py`，
  通过 `-k 'not windows_launchers_resolve_their_directory_and_propagate_exit_code'`
  排除前文已知的四项启动器失败。首次结果为 **361 通过、2 失败、4 排除**。
  一项是已知 pandas 绘图兼容失败，未修改；另一项是旧源码守卫仍要求保留已删除的调试行。
- 更新 `tests/test_dialog_translation.py::test_original_analysis_code_is_unchanged`：
  只在三个指定文件的历史源码基线中移除四条明确的打印，并断言旧行出现次数为 1、1、2。
  当前源码仍进行完整分析方法 AST 比较，没有忽略任意 print 或计算语句。
  该项重新执行 **1 通过**；其余已通过案例复用本次结果，没有重复执行整个扩大回归。
  分批累计为 **362 个案例通过、1 个已知 pandas 失败、4 项已知失败排除**。
  上轮偶发的 Tk 初始化问题本次未复现，不能据此认定其已修复。
- 已审查六行删除、八份换行恢复、新增测试、旧守卫调整及本记录的实际 Patch。
  未发现算法、公共接口、GUI 行为或报告契约变化，没有新增生产抽象或防御机制；
  本次属于局部删除和换行恢复，不另行扩大复杂度审查。

收尾 Review 无阻塞问题。Fisher 零频数和 Pearson 完全负相关区间问题仍仅记录，
没有修改算法。没有 commit、push、merge，也没有覆盖列宽或其他并行任务修改。
