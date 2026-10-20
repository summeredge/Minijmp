# G9 假设检验、列联表及方差分析表格迁移

2026-10-20。在已通过 Review 的 G8 工作区上增量修改；不提交、推送或合并。

## 范围与接口

生产代码只改动 `t_test.py`、`proportion_test.py`、`chi_sq.py`、`chi2_dialog.py`、
`one_way_ANOVA.py`、`two_way_anova.py`、`ti.py` 的报告生成。
复用 `StatTable(旧表, title, headers, values, display=..., number_formats=...)`，
经原有 `print_port` / `self.app.print` → `Minijmp.print` → `txt_viewer.add_table` 路由。
每个载体生成一张独立 TableBlock，沿用 G8 的 Excel / PNG 菜单。

任务开始时上述表均未迁移，没有已迁移或部分迁移的生产位置；完成后以下 42 张逻辑表全部迁移。
按函数静态统计逻辑表，循环内的不同标题分别计数；别名、不同参数和 Dialog 调用复用逻辑表，不重复计数。

## 逐文件、逐函数清单与测试

表内 case 均对应 `tests/test_g9_tables.py` 的真实报告调用。
所有 case 运行固定 TXT / 实际 Tk 路由检查；直接函数 case 及 `gof_summary` 逐表实际生成 Excel / PNG 后读取验证。

| 文件 / 表格生产函数 | 逻辑表及数量 | 入口及 G9 case | 原有专项 |
| --- | --- | --- | --- |
| `t_test.py::t_test_1sample` | 样本统计、检验结果、总体均值置信区间（3） | `t`、`t_summary`；Mean1SampleDialog raw / summary | G2 hypothesis / basic |
| `t_test.py::z_test_1sample` | 样本统计、检验结果、总体均值置信区间（3） | `z`、`z_summary`；Mean1SampleZDialog raw / summary | G2 hypothesis / basic |
| `t_test.py::paired_t_test` | 配对样本统计、检验结果、配对差值置信区间（3） | `paired`（不同长度）、PairedTDialog | G2 hypothesis / basic |
| `t_test.py::t_test_2samples` 及内部 `tTest` | 外层样本统计；内层检验结果、均值差置信区间（3） | `welch`、`pooled`、`two_t_summary`；Mean2SampleDialog raw / summary | G2 hypothesis 的 pooled / Welch × raw / summary |
| `proportion_test.py::prop_2sample` | 样本统计、Fisher / 非合并 / 合并检验、比例差置信区间（3） | `prop2`；Prop2SDialog raw / summary | G2 hypothesis / basic |
| `proportion_test.py::prop_test_1sample` | 样本统计、各方法检验结果、各方法比例区间、JMP 列联表检验（4） | `prop1`、`prop_zero`、`prop_all`；Prop1SDialog raw / summary | G2 hypothesis；G3 chi-square 的嵌套静默路由 |
| `chi_sq.py::chi2_test_stdev` | 样本统计、右尾检验、标准差区间、抽样分布参考（4） | `sd_legacy`、`sd_alias`；别名 `single_pop_var_test` 直接复用；multi_pop_var_test 内部调用保持静默 | G2 hypothesis |
| `chi_sq.py::chi2_var_1sample` | 样本统计、三种尾部检验、标准差区间（3） | `sd_chi`、`sd_chi_summary`；var_1sample 内部静默调用 | G2 hypothesis |
| `chi_sq.py::var_1sample` | 样本统计、卡方 / Bonett 检验、两方法标准差区间（3） | `sd`、`sd_summary`；Var1SampleDialog raw / summary | G2 hypothesis / basic |
| `chi_sq.py::chi_square` | 可选观测 / 期望列联表、Pearson / 似然比检验（2） | `chi`、`contingency`、`chi_missing`；Chi2TableDialog raw / summary；比例检验与拟合优度内部静默调用 | G3 chi-square 全部真实 apply、开关、零频数、分数频数 |
| `chi_sq.py::multi_pop_var_test` | 组别 N / SD / SD 区间 / 两种 MAD 汇总（1） | `multi_sd`、`two_sd`、MultiVarDialog | G9 固定 TXT、拆列数值断言和真实导出 |
| `chi2_dialog.py::Chi2PropDialog.apply` | 各水平观测频数 / 估计概率 / 假设概率、Pearson / 似然比检验（2） | `gof_raw`、`gof_summary`、`gof_normalized` | G3 chi-square 的取消、校验、归一化、清洗及报告断言 |
| `one_way_ANOVA.py::one_way_anova` | 各组均值摘要、ANOVA 表（2） | `one`；Anova1WayDialog_old、`anova_columns`、`anova_stacked` | G3 ANOVA：两种数据布局、比较开关、绘图开关、异常输入 |
| `one_way_ANOVA.py::JMP_ANOVA_t_test` | 逐对 p 值、按均值降序的字母分组（2） | `pairwise`；TtestDialog；Anova1WayDialog 的 comp_mean 分支 | G3 ANOVA：分组字母、重叠组、不平衡数据 |
| `two_way_anova.py::two_way_anova` | 因子水平、III 型 ANOVA 表（2） | `two_inter`、`two_additive`；`anova_two_inter`、`anova_two_additive` | G3 ANOVA：交互作用、无交互作用、不平衡设计；G4 共享计算守卫 |
| `ti.py::ti_norm` | 样本统计、双侧与两个单侧容差限（2） | `ti`、`ti_summary`；`ti_dialog_raw`、`ti_dialog_summary` | G4 quality：原始 / 汇总 × alpha / P、真实 TIDialog |

`anova_dialog.py`、`sample_test_dialog.py`、`qc_dialog.py` 没有另外生成上述统计表；
各 apply 将原始输出端口传入这些生产函数，未将 StatTable 转为字符串。
`Chi2PropDialog.apply` 是单独的报告副本，已独立迁移两张表。
`prop_test_1sample` 自行输出的 JMP 检验表也独立迁移，没有依赖嵌套 chi_square 的静默报告。
`GRR.py` 调用 one_way_anova 时使用 `print_out=False`，不产生额外共享表；G4 的 GRR 自有报告不属于本次迁移。

## 内容保留和非标准表格

- 旧 PrettyTable 保留作为 `StatTable.text`，用于终端输出、TXT、原生复制及既有布局契约。
  范围内不再执行 `print(str(table))` 或 `self.app.print(str(table))`。
  `gen_table` / `PT` 本身继续存在，作用是生成兼容文本，不是未迁移的输出端口。
- 普通表同时传入原始数值与原来的显示字符串。没有解析 ASCII 或从三位小数反算原值。
  样本量和事件数使用整数格式；容差区间的覆盖比例及置信水平为原始比例数值，Excel 使用 `0.0%`。
- 列联表 TXT 仍显示“观测 / 期望”；结构化表为每个动态列名生成观测、期望两列，保留行总计、列总计与总样本量。
  合计行的期望列使用 `*`，不虚构新的统计结果。观测值使用 General，保留现有非整数频数支持。
- 多组标准差 TXT 仍显示合并的 `(下限, 上限)`；结构化表拆为带原置信水平的 CI lower / CI upper 两列。
  两端使用原始数值，其余 N、SD 和两种 MAD 均保留。
- 字母分组中的空格、动态因子名称与交互作用 `*`、中文和特殊符号均沿用原值。
  不修改分组算法、自由度、p 值、置信区间、数据清洗、缺失语义或统计函数返回值。
- 原有解释、显著性说明、正态假设、警告、方法限制均保留为普通文本。
  multi_pop_var_test 的 O'Brien / Levene / Brown-Forsythe / F 单行结果、
  several_tests_stdev_2sided 的诊断行原本不是表格，不强行转表。
  `two_pop_var_test` 是没有 GUI 调用者的旧转发函数，没有自己的 PrettyTable；未修复其既有缺参行为。

没有因布局限制保留旧显示的统计表，没有静默丢弃内容的例外项。

## 验证与证据

使用项目有效环境 `C:\Users\shaoy\Documents\Minijmp\.venv\Scripts\python.exe`，
Python 3.11.9、SciPy 1.15.3、pandas 3.0.6、openpyxl 3.1.5、Pillow 13.0.0；未安装或升级依赖。

- 修改前采集 `tests/fixtures/g9_reports.json`：56 个入口、149 次表格输出的完整 TXT，测试不动态重建预期文本。
  同时记录剔除报告分支后的源码 AST 摘要，防止迁移改动统计算法或函数签名。
- 首轮 G9 [93 项通过](g9-evidence/first-pass.txt)。真实 Tk、Text 保存、独立导出菜单和表格数量全部验证。
- [相关回归 797 项通过，7 条既有警告](g9-evidence/regression-tests.txt)，281.33 秒；包含 G9 首轮用例、G7/G8、
  G1 Text / statistics、G2 hypothesis / basic、G3 ANOVA / chi-square、完整 G4 quality、统计 / 表格 / 边界 / 稳定性回归。
- [补充原值精度与非标准布局断言 18 项通过](g9-evidence/raw-values-tests.txt)，12.94 秒。
  与上述回归合计覆盖 815 个不同用例，G9 自身 111 个用例。
- Audit 删除 JMP 副表上与 G8 默认值完全相同的逐列格式设置后，
  [受影响单比例路径复测 10 项通过](g9-evidence/final-proportion-check.txt)，19.38 秒；没有重跑不受影响的完整回归。
- Excel 实际保存后以 openpyxl 重开，逐单元格验证标题、中文列名、完整行列、数值类型、完整浮点精度、缺失显示及数字格式。
  PNG 实际保存后以 Pillow 重开，逐行检查含末行内容；宽表和逐列布局继续由 G7/G8 覆盖。
- [导出清单](g9-evidence/exports.json)保留 7 对真实 Excel / PNG：列联表及检验、多组标准差、逐对比较和字母分组、容差区间及样本统计。
  可直接查看[结果窗口](g9-evidence/window.png)、[列联表](g9-evidence/contingency-0.png)、
  [多组标准差](g9-evidence/multi_sd-0.png)、[容差区间](g9-evidence/ti_summary-1.png)。
  已目视核对这些 PNG 及实际窗口，中文、拆分列、底栏和末行均完整。

复现命令（当前 G9 文件包含后补的 18 项，因此合并运行会收集 815 项）：

```powershell
$python = 'C:\Users\shaoy\Documents\Minijmp\.venv\Scripts\python.exe'
& $python -m pytest tests/test_g9_tables.py tests/test_g7_tables.py tests/test_g8_tables.py tests/test_g2_hypothesis_reports.py tests/test_g2_basic_reports.py tests/test_g3_anova_reports.py tests/test_g3_chi_square_reports.py tests/test_g4_quality_reports.py tests/test_g1_text_output.py tests/test_g1_statistics_output.py tests/test_statistics_regressions.py tests/test_statistical_edges.py tests/test_table_regressions.py tests/test_supplemental_stability.py -q
```

未运行无关全仓测试；没有将专项及相关回归结果表述为全仓全绿。

## Patch Review 与复杂度审查

[G9 增量 Patch](g9-evidence/g9-increment.patch)只包含本次七个生产文件与 G4 守卫变更，
不包含原有 G7/G8 未提交修改；新测试和固定夹具同时按当前文件逐项审查。
`git diff --check` 通过；新文件没有混合换行或新增行尾空白。
已核对 `describe.py` / `MiniJMP.py` 与 G8 文档记录的 SHA256 完全相同。

| 文件 | 逐文件审查结论 |
| --- | --- |
| `t_test.py` | 三个单样本 / 配对报告及两样本外层、内部 tTest 均保留原文本；pooled 和 Welch 共用迁移，保留小数自由度和原始区间。 |
| `proportion_test.py` | 两比例、单比例三张主表与单比例 JMP 副表分别迁移；没有改动精确算法、边界或静默嵌套调用。 |
| `chi_sq.py` | 两套标准差卡方报告均处理；Bonett 组合、多组汇总、列联表及结果均处理；仅在报告分支内增加载体数据。 |
| `chi2_dialog.py` | 原输入清洗、取消及归一化保留；两张独立报告副本迁移；没有改动概率计算路径。 |
| `one_way_ANOVA.py` | 两张 ANOVA 表及两张比较表逐一处理；原字母字符串保留；均值和 CI 使用原值。 |
| `two_way_anova.py` | 因子水平和 ANOVA 两表；交互作用条件同时控制显示行与数值行，避免遗漏或行错位。 |
| `ti.py` | 样本统计及区间两表；上下单侧限、双侧 k 保持分开；百分比按数值导出。 |
| `tests/test_g4_quality_reports.py` | 保留任务开始时 G7/G8 的修改；G9 只将两个 ANOVA 文件的整文件守卫调整为非报告 AST 比较，其余文件原守卫不变。 |
| G9 测试、夹具及文档 | 固定文本在修改前保存；入口清单按源码调用链建立；原值与计算结果另做精确比较，不仅验证导出器读取自己的输入。 |

no-stop-gpt Audit：两份数据各有实际消费者（旧 PrettyTable 文本与 G8 数值导出），保留有必要；
拆列仅针对两种合并数值布局。没有增加表格适配层、全局状态、缓存、fallback、配置或依赖；G8 公共组件未改动。

未逐项人工点击主程序所有菜单，也未验证其他操作系统；真实 apply、Tk 载体及导出流程由自动化覆盖。
