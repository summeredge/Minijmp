# G1–G5 遗留 P1/P2 定向修复

## 工作基线与执行边界

- 日期：2026-10-20；基线：本地 `main` 的 `5b68df06ce3892eace5f43f2c142df4d1b273eeb`。
- 开始时主仓库为 `main`，工作区干净。该提交已包含 G1–G5 及 G6 合并成果。
- 独立 Worktree：`C:\Users\shaoy\.codex\worktrees\g1-g5-p1-p2-fixes\Minijmp`。
- 修复分支：`codex/g1-g5-p1-p2-fixes`；未操作 G6 独立 Worktree，未修改主仓库，未 commit/push/merge。
- 已读取 G1–G5 验收文档、所列专项测试、实际源码、直接调用方和重复矩阵入口。
- 使用项目原解释器 `C:\Users\shaoy\Documents\Minijmp\.venv\Scripts\python.exe`：Python 3.11.9、pandas 3.0.6、SciPy 1.15.3、pytest 9.1.1。未安装、升级或降级包。
- pandas 2 对照只使用已存在的 `C:\Users\shaoy\Documents\PythonEnvs\minijmp\Scripts\python.exe`（Python 3.11.9、pandas 2.2.3），未更改环境。
- 修改按 U → Fisher → Pearson → P1 回归/Review → NP → Blaker → pandas → P2 回归/Review 顺序执行。

## 1. U 控制图：已修复

**原因/范围：** `ctrlchart_dialog.py::UDialog.get_data()` 无标识分支先除单位数，`control_chart.py::cu_plot()` 再除一次。有标识分支原本传原始计数。

**修复：** 无标识分支改为追加 `float(i)`；缺陷数与单位数的配对清洗、标识顺序、参数、图形入口均保持。`cu_plot` 增加输入契约注释：`c` 为原始缺陷数，`n` 为检查单位数；C 图继续由入口传 `n=1`。未改公式、控制限、返回值或增加开关。

**失败/参考：** 原始计数 1、单位数 10，原无标识取数为 0.1，最终绘图为 0.01；修复后两入口均传 1，最终 U=0.1、CL=0.1、UCL=0.4、LCL=0。

**验证：** 独立公式与有/无标识四条实际曲线逐点对照；不同单位数、零缺陷、缺失/非数值配对、标识顺序、缺列异常。正确的直接 U 路径和 C 图与 Git 基线的返回、报告及曲线完全一致。G5 真实 Tk 确认按钮覆盖两条 U 入口。源码断言禁止 UDialog 的旧提前除法。

## 2. Fisher 右尾：已修复

**原因/范围：** `proportion_test.py::prop_2sample()` 将 `e1-1` 截断为 0，漏算左边界的右尾质量。

**修复：** `pu_f = rv.sf(e1 - 1)`，保持右尾 `p1 > p2` 语义。左尾、双侧及其他方法、返回键和报告编排不变。

**失败/参考：** `(n1,n2,e1,e2)=(10,10,0,5)` 原结果为 `0.9837461300309598`，独立 `hypergeom.sf(-1,20,5,10)` 和 `fisher_exact(..., alternative='greater')` 均为 1。

**验证：** 左/右边界、中间值、不等样本量与两种 SciPy 参考一致；除右尾字段外所有返回项与 Git 基线精确相同。非边界右尾改用 sf 可能产生末位舍入差异，例如 e1=10 时约 3.5e-17，未改变方法。真实 `Prop2SDialog.apply()` 原始列与汇总数据两条路径均报告右尾 `1.000`；源码断言禁止旧 cdf/max 模式。

## 3. Pearson 完全负相关区间：已修复

**原因/范围：** `utilities.py::pearson_correlation()` 对正负完全相关均使用 `r_z=10000`。

**修复：** 将舍入后的 r 截至 [-1,1]；完全相关的 Fisher z 使用带符号无穷。非完全相关仍沿用原 arctanh、标准误与反变换。p 值、协方差、椭圆和返回键不变；舍入超界样本按完全相关边界处理。

**失败/参考：** `[1,2,3,4,5]` 与其相反数原返回 r=-1、区间 (1,1)，修复后为 (-1,-1)；正相关仍为 (1,1)。这是 Fisher z 在相关边界的带方向极限。

**验证：** ±1、接近 ±1、常规正负相关、不同 alpha；非完全相关全字典与基线精确相同，完美相关的非区间字段精确相同。真实舍入超界样本原 r 约 `-1.0000000000000013`，修复后 r/区间均为 -1、p=0。`fit_plot`、`multi_fit`、`multi_fit_orig`、`LinearFitDialog`、`CorrelationDialog`、`MCorDialog` 均覆盖。没有修改秩相关或把零相关解释为独立。

## 4. 可变样本量 NP：已修复

**契约：** `control_chart.py::p_np_plot(p,n,NP=True)` 的 p 是逐组不合格比例，n 为固定数或逐组列表。GUI 的 NP 固定 n 输入方式不变，PDialog 仍传配对清洗后的比例与 n 列表。

**修复：** 统计值、CL、UCL、LCL 分别乘每组 n_i。固定 n 中心仍使用原水平线；变化中心复用已有 `limit_line()` 序列机制。G5 报告消费同一中心及上下限，不增加返回结构；函数仍返回 None。仅纠正 NP 原“按首组数量缩放”的报告说明，P 图报告不变。

**失败/参考：** p=[0.1,0.2,0.05]、n=[50,100,80]，加权 p_bar=29/230。

| 项目 | 原实现 | 修复后独立参考 |
| --- | --- | --- |
| NP 点 | [5,10,2.5] | [5,20,4] |
| CL | 6.30434782609（全部） | [6.30434782609,12.6086956522,10.0869565217] |
| UCL | [13.3460142597,11.2835579122,11.8712739394] | [13.3460142597,22.5671158243,18.9940383031] |
| LCL | [0,1.32513774001,0.737421712727] | [0,2.65027548002,1.17987474036] |

参考公式：CL_i=n_i*p_bar；UCL_i=n_i*(p_bar+3*sqrt(p_bar*(1-p_bar)/n_i))；LCL_i=n_i*max(0,p_bar-3*sqrt(p_bar*(1-p_bar)/n_i))。保留原算法的下限截零，未引入新的上限截断。

**验证：** 固定标量及固定列表 n、变化 n、零缺陷和 p 边界；绘图与报告表格逐点一致。固定 NP 及固定/变化 P 的原始曲线与 Git 基线精确一致，P 报告精确一致。保留 n=0、空输入的原异常；源码断言禁止 NP 的 nlist[0] 缩放。

## 5. Blaker 全事件边界：已修复

**准确定位：** `p_blaker()` 计算的是原 Blaker p 值；区间由另一模块 `blakerCI.py::binom_blaker_limits()` 计算。`prop_test_1sample(20,20,.4)` 在区间已算出后，计算 p 值时找不到匹配的左尾，因此 `max([])` 抛异常。全失败端存在对称的 `min([])` 路径。

**可复核定义：** 对 X~Bin(n,p)，gamma(i)=min(P(X<=i),P(X>=i))，Blaker p 值为 P(gamma(X)<=gamma(k))。无可匹配的对侧尾就是空事件，其概率为零，而不是替换方法或异常兜底。

**最小边界修复：** max 的空集合端点设为 -1，min 的空集合端点设为 n+1；尾函数对超出上支持域的空事件返回零。全成功/全失败使用 SciPy cdf/sf 求尾，避免累计求和误差把数学上相等的对侧尾漏掉；无匹配左尾的路径直接以 sf 返回实际右尾，避免极小尾概率被 `1-cdf` 消去。内部非边界样本保留原累计及匹配算法。没有捕获统计异常、切换区间方法或返回人为的 NaN/CP 区间。

**失败/参考：**

- `prop_test_1sample(20,20,.4)` 修复后 p Blaker=`1.0995116277760024e-08`，调整 Blaker CI=`(0.8398685648391055,1)`。
- 全失败 `prop_test_1sample(0,20,.4)` 可完成，p Blaker=`4.160284521398273e-05`，调整 Blaker CI=`(0,0.16013143516089445)`。
- n=5,p=.5,k=0 原先 min 空集合；修复后 p=0.0625，包含两个相等的边界概率质量。
- n=20,p=.5,k=0 或 20 均为 `1.9073486328125e-06`；n=50,p=.4,k=50 的约 1.27e-20 右尾不消失。

**验证：** 测试用 `math.comb` 显式枚举全部二项概率质量与 gamma，独立于生产的匹配尾算法；覆盖全成功、全失败、单成功、单失败、不同 n/p/alpha，以及极小尾与对称等尾。已有内部点返回与修改前精确相同；单比例正常样本的所有返回项精确相同。原调整 Blaker 区间源码不变，检查端点次序、包含点估计、反演接受/拒绝及 n=5/10 多个参数点的有限分布覆盖率。覆盖率检查是列明参数点的验证，不声称穷尽全部参数空间。

**范围外事项：** 原内部点的等尾浮点匹配偏差仍保留，例如 `p_blaker(5,.5,1)` 返回约 0.2187500000000004，有限分布数学定义为 0.375。此项不是全事件边界，也不是本次异常根因；遵守“不改变正常内部点”的要求，仅记录并精确保护其现状。原 Clopper–Pearson 在 k=0 的下限、k=n 的上限仍有 NaN，未修改该独立方法。

## 6. pandas 3 旧面板：已修复

**原因/范围：** `pandastable_local/plotting.py::PlotViewer._checkNumeric()` 使用 pandas 3 不接受的 errors='ignore'。真实调用链为菜单 `plot_selected → Table.plotSelected → PlotViewer.replot → plot2D → _checkNumeric`。

**修复：** 逐列调用受支持的 `pd.to_numeric(...,downcast='float')`；只在 ValueError/TypeError 时保留完整原列。pandas 2 的对应源码正是在这两类转换异常下保留输入；不使用 coerce、不静默抹除文本。函数原 None/False 返回及不回写输入的行为保留。

**对照：** 用现成 pandas 2.2.3 的旧表达式实际生成 `tests/fixtures/pandas2_numeric_baseline.json`，列明输入、输出值和 dtype。在 pandas 3 中捕获实际 DataFrame.apply 结果逐列比较：数值、数字字符串、混合文本、纯文本、全缺失及数值含缺失。为对照原 object 列，两环境使用显式 object 输入。可转换列为 float32，混合/文本列保留 object 和原内容。

**验证：** 原失败菜单测试 `tests/test_dialog_translation.py::test_real_legacy_menu_entry_opens_all_six_panels` 在修复前抛 `ValueError: invalid error value specified`，修复后真实 Tk 六个面板均可打开。源码断言禁止目标方法的旧参数。未调整其他 pandastable 功能或依赖。

## 历史守卫调整及 Patch Review

新增专项：`tests/test_p1_p2_statistical_fixes.py`。`before()` 从固定 Git 提交 5b68df0 装载原源码，保护完整返回字典、报告与曲线；不依赖外部临时源码快照。

旧守卫仅调整三类明确授权内容：

1. `test_g5_spc_reports.py`：U 无标识入口原断言 `0.01` 改为两入口均 `0.1`；NP 原按首组数缩放的 expected_points 改为逐组缩放，CL 读取改为逐点读取实际绘制序列。其余控制图、标识、缺失值、覆盖值、报告编排、返回和 Tk 检查全部保留。
2. `test_g4_quality_reports.py`：仍进行共享模块整文件相等比较；仅在历史 utilities 文本上应用两处明确替换：插入 r 截断、将 10000 改为带符号无穷。每处检查历史语句唯一，未跳过整个 Pearson 或 utilities。
3. `g5_spc_algorithm_ast.json`：只更新 p_np_plot 一个摘要。原值 `b21b878359c1aea32d3f814a35199d1be5c13a6955f9225759430e2b6732bd7d`；新值 `4d9276a2d72ac59d98355e2fcd56c5d02a113a5ee2b636ea7200926e4ebbe4c1`。实际计算 Diff 是 NP 的四个首组缩放替换为逐点缩放（固定 n 中心折回标量），以及中心绘制增加现有 limit_line 序列路径；报告分支按原测试规则不参与摘要。cu_plot 仅增加注释，不影响 AST。其余摘要逐字保持，`g3_computation_baseline.json` 未修改。

P1 Review 审查 U 取数的两条分支、Fisher 双侧/左尾和返回字典、Pearson p 值/协方差/椭圆及全部真实消费者；P1 首轮相关回归 322 通过。P2 Review 审查 NP 加权、逐点控制限、覆盖值和报告数据，Blaker 两侧空支持域与微小/相等概率质量，pandas 异常类型及整列保留。早期 P2 回归 152 通过；后续扩大边界检查针对等尾另加先失败测试，修复仅限定全事件边界，未放开内部点算法。

已按 no-stop-gpt Audit 审查必要性：保留 Pearson 截断以处理实际浮点超界；保留 NP 固定 n 标量路径以维持旧水平线；复用 limit_line，不引入新的控制线模型；Blaker 端点代表空事件，稳定尾只用于所需边界；pandas 局部转换函数复现已验证的旧 API 语义。无新增依赖、配置、缓存、归一化开关、报告层或通用异常处理。

## 验证记录

- 修复前 P1：8 failed、15 passed，含三项根因的失败及源码旧模式断言。
- 修复前 P2：18 failed、12 passed、23 deselected，含 NP 逐点、Blaker 两侧空集合及 pandas 实际菜单失败。
- P1 首轮相关回归：322 passed。
- P2 首轮相关回归：152 passed。
- 新增专项扩充中间状态：70 passed；随后删除重复的转换自实现对照，以真实 pandas 2 fixture 对照替代，并补齐固定 n 列表、等尾边界与内部算法不变性。
- G1–G5 全部专项及旧 Dialog 整组：795 passed、5 条既有警告，162.07 秒。该轮在最后增加 Blaker 等尾边界测试和限定修复前开始；最终状态由后续专项和完整测试集验证。
- Blaker 最后边界专项：17 passed（后续新增的四项内部等尾不变性另纳入完整集）。
- 最终 P1/P2 专项：**78 passed，16.07 秒**。
- 最终完整测试集：**1334 passed、5 failed、48 warnings，295.58 秒**；无排除项，不能宣称全量通过。其中最终 78 项专项全部通过，G6 已合入 main 的绘图测试也在完整集中执行。
- 四个失败来自 `test_startup.py::test_windows_launchers_resolve_their_directory_and_propagate_exit_code`：BAT 的两个临时项目未创建启动器要求的 `.venv`，实际返回 1；VBS 的两个案例各超过 20 秒。启动器/测试与基线完全相同，G1–G3 文档已记录同类失败，未修改或跳过。
- 另一个失败为 `test_g3_regression_reports.py::test_statsviewer_reuses_complete_native_model_summary[Logit]`：摘要时间从 21:37:46 跨至 21:37:47，其余内容相同。已从未修改的 main 加载实际 StatsViewer/Logit，间隔 1.1 秒确定性复核，证实差异仅为 Time 行。此测试及生产文件均与 5b68df0 一致；未通过重复跑到绿色来掩盖该失败。
- 最终 `git diff --check`、新增文件空白检查及逐文件 Diff 审查通过；主仓库仍为干净 main，修复 Worktree 保留未提交修改。没有新增生产阻塞项，完整测试集的五项既有测试缺陷仍未解决。
- 原始复现及阶段测试日志保存于 `C:\Users\shaoy\AppData\Local\Temp\minijmp-p1-p2-20261020-01a15978`，含 `p1-before.txt`、`p2-before.txt`、`g1-g5-final.txt`、`full-regression.txt` 等；测试自身的 Git 基线和 pandas 2 fixture 在仓库中，不依赖该临时目录。

运行命令（均使用上述项目解释器）：

```powershell
$python = 'C:\Users\shaoy\Documents\Minijmp\.venv\Scripts\python.exe'
& $python -m pytest tests/test_p1_p2_statistical_fixes.py -q --tb=short
& $python -m pytest tests/test_g1_statistics_output.py tests/test_g1_debug_output.py tests/test_g1_text_output.py tests/test_g2_basic_reports.py tests/test_g2_hypothesis_reports.py tests/test_g3_computation_contracts.py tests/test_g3_report_display.py tests/test_g3_regression_reports.py tests/test_g3_distribution_reports.py tests/test_g3_chi_square_reports.py tests/test_g3_anova_reports.py tests/test_g4_quality_reports.py tests/test_g5_spc_reports.py tests/test_dialog_translation.py tests/test_p1_p2_statistical_fixes.py -q --tb=short
& $python -m pytest tests -q --tb=short
```

## 最终状态及未验证范围

六项缺陷均在当前基线复现并完成定向修复；没有“原本已修复”“未复现”或算法依据阻塞项。完整集有上述五项范围外测试失败，不影响已单独通过的 78 项缺陷专项，但阻止宣称全仓库验收全绿。

保留上文列明的 Blaker 内部等尾偏差、Clopper–Pearson 边界 NaN 及其他原有方法限制。真实 Tk 路由已自动验证，未做人工桌面点击或跨平台验证。没有修改 GUI 设计或菜单结构，因此无需修改 DESIGN.md；未处理 Git 换行配置或做整文件换行转换。


最终 Patch Review 结论：逐文件核对五份生产源码、两份既有测试的限定守卫调整、单项 AST fixture、新专项、pandas 2 fixture 和本记录；未发现需要继续修改的本次补丁问题。生产代码增量严格对应六个授权缺陷，G1–G5/G6 已有报告与绘图成果保留。未改动历史测试的其他算法约束，未新增依赖或做换行配置调整。任务到此停止，保留修复分支等待用户审查。

## 后续：用户授权合并到 main

上述“未提交/未合并”描述定向修复验收时的状态。用户随后明确要求“合并到 main”，授权提交本次全部修复、专项测试、fixture 及记录，并在本地主仓库快进合并；未授权远程 push。

合并前 main 和修复分支均仍基于 `5b68df06ce3892eace5f43f2c142df4d1b273eeb`，main 工作区干净，无新增分歧或需解决的冲突。已重新核对实际 Diff 与空白检查，修复算法保持已验收状态；此前完整集 1334 通过、5 失败的证据及范围外限制继续保留，不宣称全量通过。合并后执行 78 项缺陷专项，最终结果以本轮回复为准。
