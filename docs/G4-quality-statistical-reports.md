# G4 过程能力、测量系统与统计容差区间报告

2026-10-20，仅在 `C:\Users\shaoy\.codex\worktrees\02e1\Minijmp` 实施。
执行开始时工作区干净，Git 基线为 `191c3b7b245ff40f600d442bbf18ea7e523a28df`。
先阅读当前源码、G1/G2 验收文档、测试和依赖，再修改呈现层。
没有修改统计估计、返回键、类型、签名、默认参数、参数控件、数据清洗或图形算法。

## 功能现状及全部调用路径

| 功能 | 当前实现与入口 | G4 范围及限制 |
| --- | --- | --- |
| 无子组正态过程能力 | `MiniJMP.cpk → CpkDialog.apply → cpk_plot → cpk → cpk_calc / nonconformance` | 已实现；组内标准差使用相邻两个观测的移动极差，整体使用样本标准差；显示开关保留 |
| 含子组正态过程能力 | `MiniJMP.cpksub → CpkSubDialog.apply → cpk_plot → cpk` | 已实现；按子组大小及 ID 两种入口，组内估计支持无偏标准差平均值或极差/d2 平均值，平衡/非平衡路径均保留 |
| 能力指数与不合格率直接调用 | `cpk_calc`、`nonconformance`，以及 `cpk.py` 演示入口 | 已实现；Cp/Cpk/Cpl/Cpu/Cpm、各已有置信限及观测/组内预测/整体预测比例；整体报告使用 Pp/Ppk/Ppl/Ppu 标签，返回字典仍用原 `cp` 等键 |
| 单侧规格、非正态能力、Z/PPM 独立报告 | 当前能力入口要求 LSL、Target、USL；没有专门的单侧规格或非正态算法 | 未实现，不属于 G4；已有不合格比例仍完整呈现，不另行推算 PPM/Z |
| 交叉型 AIAG ANOVA | `MiniJMP.grr → GRRDialog.apply → grr_master → grr_anova_AIAG` | 已实现；Auto/On/Off 及可选操作者列；Auto 先执行原来的完整模型交互筛选 |
| 交叉型 EMP ANOVA | 同一 Dialog/master，进入 `grr_anova_EMP` | 已实现；保留相关系数、可能误差、自由度、偏倚影响及已有分类参考；不套用 AIAG 的 GRR 定义 |
| 交叉型均值极差 | 同一 Dialog/master，进入 `grr_xbar_r → GRR_xbar`；也支持直接 DataFrame 和自定义列名 | 已实现；保留 EV/AV/PV/GRR/总变异、ndc、历史过程及规格公差百分比 |
| ANOVA 分量计算 | `grr_inter / grr_simple → two_way_anova`，无操作者时 `grr_no_op → one_way_anova` | 已实现，只读复用；未修改公共 ANOVA 报告；原来仅在 Auto 输出筛选 ANOVA，G4 不新增 On/Off 的 ANOVA 拟合/报告 |
| 嵌套型 GRR | `MiniJMP.grr_nst → GRR_Nested_Dialog.apply → grr_nested`，也有直接及演示入口 | 已实现；ANOVA、方差/标准差/6SD、研究变异比例、ndc、历史标准差是否实际使用均保留 |
| 正态统计容差区间 | `MiniJMP.ti_norm → TIDialog.apply → ti_norm`，直接及演示入口 | 已实现；原始样本与优先覆盖的汇总数据；双侧区间、独立单侧上限和下限；展示原计算的 k |
| 非参数/其他分布容差区间 | 当前仅有 `ti_norm` | 未实现，不属于 G4；没有增加新方法 |
| 物理测量单位 | 所有上述统计函数均无独立单位参数；绘图允许自定义轴标签 | 部分实现：保留轴标签，报告说明单位继承输入，方差单位为平方；不将自定义轴标签猜测为物理单位，不编造 mm 等单位 |

通过限定 `code/`、`tests/` 的调用搜索，核对每个实际函数及 Dialog，未按文件名推断功能。
`cpk_plot` 的直方图/正态曲线和 `grr_plot` 的零件/操作者子图继续使用原实现。

## 修改文件和函数

| 文件 | 实际修改 |
| --- | --- |
| `code/cpk.py` | `cpk` 的样本/规格/波动汇总，`cpk_calc` 的能力表，`nonconformance` 的观测及模型预测表 |
| `code/GRR.py` | `GRR_xbar`、`grr_anova_AIAG`、`grr_anova_EMP`、`grr_master`、`grr_nested` 的报告；局部 `_grr_design`、`_grr_tables` 只负责重复呈现 |
| `code/ti.py` | `ti_norm` 的样本、方法、限类型、覆盖比例、置信水平及因子表 |
| `code/qc_dialog.py` | 五个质量 Dialog 的 `apply` 只新增变量/列标签，翻译子组两条原有消息；汇总容差数据不错误标为所选原始变量 |
| `tests/test_g4_quality_reports.py` | 专项真实返回值对照、表格语义、所有输出入口、真实 Tk 显示/保存/复制、固定基线 AST 和公共模块只读守卫 |
| `tests/test_dialog_translation.py` | 仅在质量 Dialog 的原 AST 守卫中排除五条新增变量标签、统一两条已翻译消息；不移除任何分析方法的比较 |
| `tests/test_g1_debug_output.py`、`tests/test_g2_hypothesis_reports.py` | 两处旧换行检查适配 Git 的 CRLF 检出，接受一致 LF/CRLF，仍拒绝混合换行和孤立 CR；保留原统计/源码断言 |
| `docs/G4-quality-statistical-reports.md` | 本验收记录 |

## 报告变化及统计语义

- 所有表继续使用 `gen_table()` 与 `format_stat()`，数值三位小数，不可用/不适用为 `*`；
  名称列左对齐，数值列右对齐。表内用 ASCII `%`、`x`、`/`，避免等宽中文字体的模糊字符宽度错列。
- 能力分析由英文逐行散文改为样本与规格横表、组内/整体两节能力表、不合格率表。
  各节保留 Cpm，明确使用本节标准差；沿用原报告不展示 Cpm 置信限的选择，未删除返回中的限值。
  Cp/Pp 表示规格宽度相对波动，Cpk/Ppk 另考虑均值偏离；标准差比不作为稳定性证明，不加合格阈值。
  `cpk_calc` 未指定来源名称时只称“过程能力指标”，不推断标准差来源；自定义名称仍显示。
- 不合格率逐行区分实际观测、正态预测（组内）、正态预测（整体），逐列区分低于 LSL、高于 USL、合计，单位为百分比。
- GRR 先给出真实零件、操作者、每个操作者-零件组合的重复次数，嵌套额外给出每名操作者零件数。
  未提供操作者列时不把占位零再现性显示为已估计分量。
- GRR 方差贡献率为 `100 × 分量方差 / 总方差`；研究变异占比为 `100 × 分量SD / 总SD`；
  公差占比为 `600 × 分量SD / 规格公差`；历史过程占比为 `100 × 分量SD / 历史SD`。
  研究变异为 `6 × SD`，ndc 为可区分的零件类别数，不是样本量；这些百分比不是测量误差概率。
- **修正一项报告表达式错误**：旧 AIAG 操作者/交互两行 `%Tolerance` 使用 `100 × SD / 公差`，
  同列其余行使用 `600 × SD / 公差`。现统一为该列定义的 `6 × SD / 公差` 百分比。
  变化仅在原 `print_out` 分支的报告表达式，没有修改任何方差、标准差估计或返回值。
- AIAG 再现性保留操作者与交互分量的原组合；EMP 的 GRR 仍只含重复性和操作者分量，
  交互单独计入总方差。EMP 不新增研究变异占比、公差占比或 ndc。
  旧重测误差与重复性 SD 为同一统计量，只保留一个数值并说明对应关系；原分类规则及参考数值不变。
- Auto 原来由共享 `two_way_anova` 输出的完整模型表，改为在 `grr_master` 局部呈现同一次计算的结果。
  F、p、SS、MS、DF 保留；合计 SS 使用原观测离差平方和，不把非平衡数据的 Type III 调整 SS 相加当成总 SS。
  明确其用途为交互项筛选，后续分量仍由各方法原有重拟合/交互处理规则产生。
- 嵌套原有有限值、平衡、每件独属一人、最少重复、历史标准差等保护全部不变。
  历史值是否实际用于替换零件/总方差按原 `hist_std_used` 报告；零分母保持返回 NaN，报告显示 `*`。
  Xbar/AIAG 的报告分母为零时同样显示 `*`，避免只因打印报告触发除零；不改计算核心的异常行为。
- 容差结果改为同表三行，明确“正态/双侧区间/单侧下限/单侧上限”。
  覆盖比例与置信水平分列；单侧两行不能拼成双侧区间，空侧为 `*`。
  在覆盖双侧因子变量之前，仅在输出打开时保存原单侧 k 供显示；求根、分位点、精度及返回值不变。
  说明容差区间覆盖总体个体，与参数置信区间、未来观测预测区间不同。

## 验证环境和证据

使用 G1/G2 文档指定且已验证可用的现有解释器：
`C:\Users\shaoy\Documents\Minijmp\.venv\Scripts\python.exe`。
Python 3.11.9、SciPy 1.15.3、pandas 3.0.6、PrettyTable 3.18.0、pytest 9.1.1。
已核对实际导入位置均属于该项目环境；没有安装、升级依赖或使用 Codex bundled runtime。

执行前将目标及受保护模块的原始字节复制至
`%TEMP%\minijmp-g4-before-20261020`，保护对照不依赖其他 Worktree。
初始现有统计回归为 **114 通过，7 条原有警告**；完成第一轮报告修改后同组仍为 **114 通过**。

专项测试从上面的固定提交编译原始函数，以 **102 组调用对照** 和当前函数递归比较真实返回值：
字典键及顺序、类型、列表/元组、原始浮点数、NaN 均严格比较，不用报告字符串替代数值不变性验证。
覆盖输出开关、不同 alpha、组内开关、无子组/平衡/非平衡及两种子组估计，
GRR 三种方法/有无操作者/Auto-On-Off/嵌套历史值和零分量，以及容差原始/汇总数据和两组覆盖设置。
分量的方差、SD、6SD 及全部比例逐行核对；容差原计算 k 与上下限对应关系单独核对。

计算 AST 守卫逐个比较三份统计模块所有原有函数及其签名/默认参数：只去除显式 `print_out` 分支、
原固定分类参考字符串，并统一 Auto ANOVA 的打印开关。其余计算、保护、返回和控制流完整比较。
质量 Dialog 另做整模块 AST 比较，仅忽略精确指定的五条输出与两条翻译。
旧错误模式检查限定到具体文件和函数，包含全部重复 GRR 表格和容差入口。

首次专项为 **131 通过、4 失败**：三项错误地在 GRR 父坐标轴而非实际子图检查标签；
一项在测试过程中读取变化中的源码行号而取错函数。修正测试为检查实际子图及按函数名读取 AST，
相关 **26 项复验通过**；没有为这些失败更改图形实现或放宽计算比较。

最终组合测试首次为 **462 通过、9 失败，7 条原有警告**，其中 **G4 全部 144 项通过**。
9 项失败全部来自旧 G1/G2 的硬编码 LF 断言，与功能或数值无关：
本机系统 Git 配置 `core.autocrlf=true`，`git ls-files --eol` 确认这些文件原已为 `i/lf w/crlf`。
没有转换公共源码；只将两处旧测试改为接受一致 LF 或 CRLF，并继续拒绝混合换行和孤立 CR。
原统计源码、函数和旧模式断言完整保留。

仅复验发生变化的 9 项换行测试及加强后的 9 项 G4 旧模式测试：**18 通过**。
其他已通过案例的生产代码及测试无变化，复用上述结果，不重复执行整组。
因此组合测试分批累计为 **471 个案例通过**，包含 **144 项 G4、141 项 G2**，没有遗留失败。

```powershell
$python = 'C:\Users\shaoy\Documents\Minijmp\.venv\Scripts\python.exe'
& $python -m pytest tests/test_g4_quality_reports.py tests/test_g2_basic_reports.py tests/test_g2_hypothesis_reports.py tests/test_g1_statistics_output.py tests/test_g1_text_output.py tests/test_g1_debug_output.py tests/test_statistics_regressions.py tests/test_statistical_edges.py tests/test_supplemental_stability.py tests/test_dialog_translation.py::test_original_analysis_code_is_unchanged tests/test_dialog_translation.py::test_real_confirm_calls_statistics_and_invalid_input_is_chinese -q --tb=short
& $python -m pytest tests/test_g1_debug_output.py::test_g1_files_keep_consistent_line_endings tests/test_g2_hypothesis_reports.py::test_scoped_old_report_builders_removed_and_line_endings_consistent tests/test_g4_quality_reports.py::test_specific_replaced_output_patterns -q --tb=short
& $python -m pytest tests/test_dialog_translation.py::test_menu_dialog_lifecycle_and_translation tests/test_dialog_translation.py::test_original_defaults_structure_and_english_removed -k 'Cpk or GRR or TIDialog' -q --tb=short
```

GUI 使用 G1 的真实 `txt_viewer`/Tk fixture：六类实际报告逐表测量中文与数字列分隔线像素位置，
窄窗宽表水平滚动、操作栏、完整 UTF-8 保存、全选及原生复制事件均在专项中检查。
复制事件在绑定处截获，避免改动用户剪贴板；G1 测试继续覆盖复制按钮、清空、取消保存、失败反馈、主题和 DPI。
五个 Dialog 的 apply 实际调用原统计与绘图；检查能力曲线数据、返回值和 GRR 子图轴标签。
参数控件/default/菜单生命周期另行验证五个真实质量弹窗：**10 通过，84 个无关案例排除**。
连同上述组合测试，分批累计 **481 个不同案例通过**。

## 并行隔离、Patch Review 和复杂度审查

1. 实际修改共九个文件：上表四份质量源码、一份专项测试、三份旧测试及本验收文档。
2. `utilities.py`、`txt_output.py`、`dialog.py`、两份 ANOVA 和 `cpk_plot.py` 与开始快照逐字节一致，
   专项另对公共模块及两份绘图源码和固定基线作全文比较；没有修改 G1/G2 公共实现。
3. 没有读取、进入或修改 G3 Worktree，没有拉取、cherry-pick、rebase、reset、清理或覆盖其他工作区。
   G3 若优化 ANOVA，可能同样触及旧 `tests/test_dialog_translation.py` 的守卫位置；该文件为潜在文本冲突点。
   生产 ANOVA 模块保持只读，无法在不检查 G3 的情况下保证它未来实际修改的文件集合。
4. 未引入任何 G3 未合并依赖；测试、计算与呈现均以本 Worktree 的固定基线为依据。
5. 本阶段保留四份源码及原测试文件初始 CRLF 风格，没有整文件换行转换。
   标准 Git diff 逐文件为局部修改；初始工作区干净，不存在需要覆盖或回退的用户修改。
6. 最终 Patch Review 涵盖四份源码、四份测试和本记录，核对全部消费者、重复路径、
   数值保护、报告含义、图形保留、公共模块边界和真实 diff，不仅依据 pytest。
7. 按 `no-stop-gpt` Audit 检查两个局部助手、`study` 分支、零分母显示保护及单侧 k：
   设计信息和表格各有四个真实方法消费者；EMP 只显示原支持的 SD，故需要区分；
   嵌套已有零方差、交叉 Dialog 允许零公差/历史 SD，是显示保护的实际入口。
   没有报告框架、缓存、兼容层、新配置、依赖或复制公共组件。

最终 `git diff --check` 通过；逐文件实际 diff 为局部修改，无整文件换行变化、调试输出、
无关重构或 G3 代码。新增文件另做尾随空白与语法检查。
Patch Review 无阻塞项，**G4 验收完成，可基于上述 Git 基线独立合并**。
G3 若也改动旧测试，需要正常解决测试文件的文本冲突，不需要先合并 G3 才能运行 G4。
没有 commit、push、merge。

## 已知限制

- 没有实施单侧规格、非正态能力、非参数容差、单位输入或新统计方法。
- 保留能力函数原来的规格/目标排序、单变量 Dialog 的默认目标处理、子组清洗及边界行为；
  未将其作为“报告优化”悄然修复。直接能力函数的无变异或不足样本，交叉 GRR 的退化 ANOVA，
  容差函数的非法 P/N 等原算法输入边界仍需独立任务处理。
- `cpl_cpu_95` 原来在数值求根异常时返回 `-1`，负置信限本身也可能合法；G4 不凭数值猜测失败状态，
  不更改返回契约。该问题需要独立提供可辨识求根失败状态后再处理。
- `use_hist` 在交叉型原实现中未控制分量替换；历史 SD 仅用于原有历史过程占比。
  嵌套则按原方法选择是否使用历史值，两者没有混用。
- 未验证其他操作系统字体、系统剪贴板接收端或原生文件选择器人工交互；
  未执行全仓库无关测试/启动器，G1/G2 已记录的旧 pandas 绘图面板及启动器问题不属于 G4。

## 后续：用户授权合并到 main

以上记录描述独立 G4 开发阶段。随后用户明确要求“合并到 main 分支”，授权本次提交和合并；
仍未请求远程 push。

- G4 原始修改已提交为 `cec3ae8`，分支 `codex/g4-quality-statistical-reports`。
- 合并前 main 为 `da54ca1bdc1e5e9d197d5a31308b94754a6d0a9f`，已包含 G3；main 工作区干净。
  在 G4 分支整合该 main，没有访问或改写其他独立任务的 Worktree。
- 唯一生产冲突位于 `GRR.py::grr_nested` 的报告块。采用 G4 三表布局，保留 G3 的
  F 分母、随机效应零方差 H0、平衡/独立正态/等方差假设及 p 值舍入说明。
  统计计算、校验、返回和绘图均未改动，公共模块保持 main 原样。
- `test_dialog_translation.py` 自动合并后同时保留 G3 和 G4 的限定守卫。
  G3 ANOVA 测试更新为 G4 标签、三张表、局部 Auto 筛选报告，不删除原数值、类型、校验或调用次数断言。
- G4 公共源码只读测试的比较基线更新为合并前 main `da54ca1`，避免将 main 已有 G3 报告当作 G4 越界修改；
  数值及计算 AST 对照仍保留原始 `191c3b7` 基线。
- G3 冻结摘要仅更新 EMP 一项：原摘要包含现已移除的固定英文 `guideline` 报告字符串赋值。
  新摘要不再包含该静态文本；G4 针对同一函数的计算 AST 精确对照与实际数值对照均通过，
  没有借更新摘要放行算法变化，其余 25 项冻结摘要不变。
- 首轮整合验证 **234 通过、2 失败**；失败分别为旧嵌套标题断言和上述报告字符串摘要。
  修复后只复验受影响测试，其余通过结果复用。

复验及扩展相关回归 **441 通过，12 条原有数值/绘图警告**；上述两项失败均已通过，
26 项 G3 冻结计算约束全部通过。与首轮未受后续修改影响的通过结果合计，
本次 main/G4 整合共 **650 个不同案例分批通过**，其中 G4 专项 144 项全部通过。
最终未暂存/已暂存的 `git diff --check` 均通过，实际冲突差异审查无阻塞项。

```powershell
$python = 'C:\Users\shaoy\Documents\Minijmp\.venv\Scripts\python.exe'
& $python -m pytest tests/test_g4_quality_reports.py tests/test_g3_anova_reports.py tests/test_g3_computation_contracts.py tests/test_g3_report_display.py tests/test_dialog_translation.py::test_original_analysis_code_is_unchanged -q --tb=short
& $python -m pytest tests/test_g3_anova_reports.py::test_real_nested_apply_cleans_and_preserves_validation tests/test_g3_computation_contracts.py tests/test_g2_basic_reports.py tests/test_g2_hypothesis_reports.py tests/test_g1_statistics_output.py tests/test_g1_text_output.py tests/test_g1_debug_output.py tests/test_statistics_regressions.py tests/test_statistical_edges.py tests/test_supplemental_stability.py tests/test_g3_chi_square_reports.py tests/test_g3_distribution_reports.py tests/test_g3_regression_reports.py -q --tb=short
```

main 通过 `--ff-only` 更新到验证后的 G4 整合提交；若 main 在验证期间变化，快进会拒绝，
不会覆盖新提交。未推送远程、未清理其他 Worktree，未执行无关启动器或跨平台人工验证。
