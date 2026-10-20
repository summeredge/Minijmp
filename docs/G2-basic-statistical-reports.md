# G2 基础统计报告结构与中文输出

## 范围与结果

2026-10-20，以执行开始时的本地最新工作树为基线，完成五类基础统计报告的呈现层优化。
没有拉取并覆盖工作树，没有 commit、push、merge，没有启动 G3。
保留计算公式、返回键及原始数值、签名、默认参数、清洗规则和已有有效性检查。

执行前已检查 Git 状态、目标列出的十份源码、G1 文档及相关测试，
并在 `%TEMP%\minijmp-g2-before-20261020` 保存源码、测试和初始 diff。
数值对照使用这份包含未提交 G1 的工作树快照，没有用旧 Git HEAD 代替基线。

## 入口清单与修改文件/函数

| 类别 | 入口、重复实现及已有指标 | 本次调整 |
| --- | --- | --- |
| 描述性统计 | `describe.py::describe()`：N、均值、标准误、标准差、最小值、Q1、中位数、Q3、最大值，以及方差、变异系数、总和、极差、四分位距、偏度、峰度、众数、众数频数、自定义百分位数 | 原来的六列项目/数值拼接表改为核心横表、补充横表和百分位表，所有原指标及别名返回键保留 |
| 单/多变量描述 | `basic_dialogs.py::DescribeDialog.apply()`、`MultiDescribeDialog.apply()` | 共用 `describe.py::print_descriptive()` / `print_percentiles()`；单变量与多变量使用相同核心列，多变量一变量一行；保留统计量勾选、百分位输入及不足样本错误 |
| DataFrame 描述 | `pandastable_local/core_orig.py::Table.describe()`、`pandastable_local/app.py::DataExplore.describe()` | 逐一核查并测试；这两处输出 pandas DataFrame 子表，不是文本报告，保留原 pandas 指标、分位数及子表结构，避免换用另一套计算。应用菜单的 `MiniJMP.describe()` 实际进入上述单变量弹窗 |
| 正态性 | `utilities.py::norm_test()`；`NormTestDialog.apply()`，以及 Residual / ortho_fit 等对共享函数的调用 | 两条已有检验 Shapiro-Wilk、Anderson-Darling 整理为方法/统计量/p 值表，显示 N，保留正态模型 H0、p 值解释及底层警告；明确未拒绝不等于证明正态 |
| 均值/标准差区间 | `utilities.py::mean_std_CIs()`、`CIDialog.apply()` | 原散文上下限改为参数/点估计/双侧上下限/单侧置信下限/单侧置信上限表，水平写在表前；点估计直接取现有计算结果，保留 t/卡方方法及正态总体条件 |
| Pearson 单组 | `utilities.py::pearson_correlation()`，`linear_plot.py::fit_plot()` 及 `CorrelationDialog.apply()` | 变量组合/方法/N/系数/p 值核心表，协方差及系数双侧置信限另表保留；公开函数无变量名参数时使用 X / Y，弹窗原有列名/配对清洗信息仍在表前 |
| 秩相关及 Hoeffding | `nonpara_cor.py::spearman()`、`kendall()`、`hoeffding()` | 共用窄范围的 `print_correlation()`；保留不同 H0，Spearman/Kendall 的零秩相关不等于独立，Hoeffding 的 H0 为独立 |
| 相关矩阵 | `linear_plot.py::multi_fit()`、`multi_fit_orig()`；`fit_dialog.py::print_multi_col_tables()` 及 `MCorDialog.apply()` | 两份 Pearson 实现及其他三种矩阵均保留矩阵布局、标签顺序和单元格对应，系数表与 p 值表分别命名，数字右对齐，显示实际 N |
| 均值检验 | `t_test.py::t_test_1sample()`、`z_test_1sample()`、`paired_t_test()`、`t_test_2samples()` 及其内部 `tTest()` | 样本统计、检验结果、区间分段；保留双侧/左尾/右尾，配对差值明确为样本 1 - 样本 2，两独立样本仍为 μ2 - μ1；保留 Welch/合并方差方法及汇总数据路径 |
| 标准差检验 | `chi_sq.py::chi2_test_stdev()`、`chi2_var_1sample()`、`var_1sample()` | 卡方、Bonett 方法分列；旧右尾入口仍只报告原有右尾，保留卡方分位点及抽样分布中央区间，并与参数置信区间区分 |
| 比例检验 | `proportion_test.py::prop_test_1sample()`、`prop_2sample()` | 样本统计、按方法/方向区分的 p 值、区间表；保留正态近似、合并/非合并、Fisher、Sterne、Blaker、调整 Blaker、二项尾概率及 Clopper-Pearson 区间；两比例方向仍为 p1 - p2 |
| 比例嵌套检验 | 单比例入口内部的 `chi_square()` 返回结果 | 仍调用同一计算函数；关闭其旧报告后，在单比例报告中呈现原有 Pearson/似然比统计量、自由度及 p 值，没有改动通用列联表报告 |

生产修改限定九个文件：`describe.py`、`basic_dialogs.py`、`utilities.py`、`nonpara_cor.py`、
`linear_plot.py`、`fit_dialog.py`、`t_test.py`、`chi_sq.py`、`proportion_test.py`。
没有更改菜单、参数弹窗创建、控制图、GRR、Cpk、ANOVA 或高级回归报告源码。
共享正态性/Pearson 函数的消费者自然获得同一基础统计表；其计算结果未变。

## 公共输出约定与边界

- 继续使用 `print_port`、`txt_viewer`、`utilities.gen_table()`，不新增报告引擎或依赖。
  `gen_table()` 的 G1 实现没有修改；只新增 `format_stat()` 统一三位小数和不可用值 `*`。
- 表格数字列右对齐，变量/方法/项目标识列左对齐；中文标题先说明对象与参数，再呈现统计表。
- 显著性水平为 `α = 0.050`，置信水平为 `95.0%`；没有 alpha 参数的正态性/秩相关函数
  不编造显著性水平或自动作出拒绝决定。p 值按三位小数显示，`0.000` 是舍入结果，不代表概率精确为零。
- 核心描述列为变量、N、N*、均值、均值标准误、标准差、最小值、Q1、中位数、Q3、最大值。
  `number_list()` 与 `is_number()` 的源码规则已核对：NaN、不能转换为数值的输入被排除，
  并非新增有限值过滤器。弹窗 N* 来自原列长度减实际清洗后 N；直接 `describe()` 对有长度的输入同样计数。
  一次性生成器无法回溯输入总数，不显示 N*，不声称其为零。原有不足两个有效观测返回 None 的行为不变。
- 表中 `*` 也用于不适用/原方法未计算的单元格；不会填入另行推算的检验结果。
  两样本 t 原函数只计算双侧区间，因此没有新增单侧置信限。不可用的 Bonett 仍保留原 NaN 返回值。
- 单侧置信限与双侧区间分列或分行，未把固定参数解释为随机落在本次观测区间内。
  不把 p 值解释为 H0 为真的概率；各方法的假设与适用性说明保留。
- 配对报告 N 改为实际 `zip` 差值数量；不改变原有配对计算、截断行为和返回结果。
  Z 原输出的自由度仍保留，并说明它仅为样本信息，不参与标准正态 p 值或区间计算。

### 实际中文字体对齐

测试发现 Windows 新宋体中 `μ/σ/ρ/χ/≠` 宽度为 14px，ASCII 数字为 7px；
PrettyTable 默认将这些模糊宽度字符计为一个字符，原先只比较 `wcswidth()` 会漏掉窗口错列。
因此系统生成的表格内使用 `mu/mu_d/sigma/rho/!=` 或中文“卡方统计量”，表外 H0 等说明保留希腊符号。
没有修改 G1 字体选择器、文本窗口或 PrettyTable 公共实现。
新增测试在真实 `txt_viewer` 字体下逐一比较 16 类报告所有表头/数据行分隔线的像素位置。

## 测试与数值证据

使用已验证的项目解释器 `C:\Users\shaoy\Documents\Minijmp\.venv\Scripts\python.exe`：
Python 3.11.9、SciPy 1.15.3、pandas 3.0.6、PrettyTable 3.18.0。
没有安装依赖，也没有使用 Codex bundled runtime。

- 新增 `tests/test_g2_basic_reports.py`：**67 项**。覆盖函数/单变量/多变量、可靠 N*、
  生成器、空/无效数据、勾选指标、自定义百分位数、两处 DataFrame 子表、正态性和区间的直接/弹窗入口、
  三种单组相关及 Hoeffding、两份 Pearson 矩阵、三种非参数矩阵、真实多变量相关 apply、
  六类假设检验弹窗的原始/汇总数据和配对清洗路径、宽表显示保存、16 类报告真实字体像素对齐及旧模式约束。
- 新增 `tests/test_g2_hypothesis_reports.py`：**74 项**。覆盖各尾部、方法、两种 alpha、
  假设值正反方向、原始/汇总数据、合并/非合并方差、配对长度不等、标准差区间、
  单/两比例全部已提供结果、嵌套列联表、不可用值、输出开关、签名和有界源码约束。
- G1 旧输出断言更新于 `test_g1_statistics_output.py`、`test_g1_debug_output.py`、
  `test_dialog_translation.py`；改为核对新的表格行/尾部/区间，不删除独立 SciPy 数值参考。
  弹窗 AST 守卫仅将两个已由 G2 逐入口覆盖的描述 apply 移出旧原样比较，其他方法继续完整比较。
- 最终相关测试：**327 通过，7 条原有数值/绘图警告**；其中 G2 141 项，其余相关回归 186 项。

```powershell
$python = 'C:\Users\shaoy\Documents\Minijmp\.venv\Scripts\python.exe'
& $python -m pytest tests/test_g2_basic_reports.py tests/test_g2_hypothesis_reports.py tests/test_g1_statistics_output.py tests/test_g1_text_output.py tests/test_g1_debug_output.py tests/test_statistics_regressions.py tests/test_statistical_edges.py tests/test_supplemental_stability.py tests/test_dialog_translation.py::test_original_analysis_code_is_unchanged tests/test_dialog_translation.py::test_real_confirm_calls_statistics_and_invalid_input_is_chinese -q --tb=short
```

另对执行前源码快照与当前实现进行 **178 次**精确返回值对照：18 个函数，174 次正常结果及 4 次相同异常。
递归比较字典键及顺序、原始浮点值、列表/元组/数组、NaN；未用格式化字符串证明数值一致。
覆盖输出开关、不同 alpha/假设值、汇总参数、自定义自由度、正负完全相关、比例边界及新旧矩阵。
全部签名和默认参数相同。
18 个函数在限定移除 `print_out` 报告分支、矩阵组表语句，并规范化描述函数的原字典返回位置后，
计算 AST 完全一致。对照脚本保存在上述临时快照旁，仅用于本次验收，不成为项目运行依赖。

真实 Tk 回归复用了 G1 fixture 和测试：宽表横向滚动、中文与数字像素对齐、完整 UTF-8 保存、
清空、复制事件、全选、主题、窗口关闭及不同 scaling 均通过。复制测试截获原生复制事件，未覆盖用户剪贴板。
没有要求人工打开文件对话框，也没有验证其他操作系统字体或剪贴板接收端。

## 实际 Diff、Review 与遗留问题

- 已对执行前快照逐文件审查 G2 增量，九份源码原有换行风格均保留：
  `describe.py`、`linear_plot.py` 为工作树原有 CRLF，其余七份为 LF；没有整文件换行转换。
  常规 `git diff` 无整文件增删噪声，`git diff --check` 通过。
- `core_orig.py`、`headers.py`、`test_table_regressions.py`、`txt_output.py` 的 SHA256 与执行前完全一致；
  原有 G1、列宽和其他未提交改动保留，没有修改其他统计模块或 G1 文档。
- 已完成主审及交叉只读 Patch Review，并按 no-stop-gpt Audit 检查新增复杂度。
  `format_stat()` 有多个真实消费者；描述报告辅助函数分别供函数/单变量/多变量入口复用；
  秩相关辅助函数供三种方法复用。没有报告模型层、配置系统、缓存、fallback 或新增依赖。
  像素检查发现的问题已在报告单元格修正并加入自动回归；最终无阻塞项。

保留以下已确认的算法问题，没有在 G2 修复：

1. G1 已记录的 Fisher 零频数右尾：`prop_2sample(n1=10,n2=10,e1=0,e2=5)`
   中 `cdf(max(e1-1,0))` 边界错误，右尾应为 1，而旧实现返回约 0.983746。
2. G1 已记录的 Pearson 完全负相关：`[1,2,3,4,5]` 与 `[5,4,3,2,1]` 的 r 为 -1，
   旧区间却为 `(1,1)`；G2 保留并显示原值，没有更改 Fisher z 分支。
3. 本次数值对照确认的 Blaker 全事件边界：`prop_test_1sample(20,20,.4)`
   在 `p_blaker()` 的 `max()` 空序列处抛出 `ValueError`；执行前源码与当前行为一致。

扩大弹窗回归仍复现 G1 已记录的 `test_real_legacy_menu_entry_opens_all_six_panels` 失败，
位置为未修改的 `pandastable_local/plotting.py:720` 对 pandas 使用 `errors='ignore'`。
旧散文断言导致的测试失败已更新并复验通过；没有宣称全量测试通过。
G1 文档中的启动器/其他环境限制保留，未将其纳入本阶段修复。

**G2 验收完成**：五类文本报告、实际重复路径及原有子表契约均有覆盖；指标保留、
计算/返回契约不变、专项与直接相关回归通过、工作树受保护、Patch Review 无阻塞项。
