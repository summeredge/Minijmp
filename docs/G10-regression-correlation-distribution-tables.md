# G10 回归、相关分析和分布拟合表格迁移

## 基线和依赖

工作树基线为 `63f2191`。开始时工作树无本地改动，尚不包含 G8。
读取主工作目录的现有 G8 实现后，同步 `code/stat_table.py`、`code/txt_output.py`
及 `code/MiniJMP.py` 的必要应用路由；没有改动主工作目录，没有提交、推送或合并。
`stat_table.py` 与读取的 G8 源码完全一致，SHA256 为
`cad9d9b7edd1bc915f6e56faab876e6a9e52b76139a76b09884ece9a169ae3ec`。
未同步无关的描述统计或其他分析迁移。

环境：`C:\Users\shaoy\Documents\PythonEnvs\minijmp\Scripts\python.exe`，
Python 3.11.9、SciPy 1.14.1、pandas 2.2.3、openpyxl 3.1.5、Pillow 11.0.0。
已核对 requirements，未安装/升级依赖，未使用 Codex bundled Python。

## 按调用关系建立的报告清单

| 报告生产函数 | 实际入口和复用关系 | 已有表格及处理 |
| --- | --- | --- |
| `linear_fit.linear_fit` | `LinearFitDialog.apply → fit_plot`，以及直接调用 | 模型摘要、回归系数、回归 ANOVA、条件性失拟检验、残差正态性；全部迁移 |
| `ortho_fit.orthogonal_fit` | `OrthoFitDialog` 继承 `LinearFitDialog.apply → fit_plot` | 参数估计及 CI、测量误差方差、可选逐观测残差明细；全部迁移；`print_residual` 独立于 `print_out` 的行为保留 |
| `utilities.norm_test` | 正交回归、`Residual.resid_test`、`linear_fit_resid_test`、`ResidDialog`，以及基础正态性入口 | Shapiro-Wilk / Anderson-Darling 的共享表格迁移；OLS 自己的重复实现也单独迁移，没有漏掉 |
| `utilities.pearson_correlation` | `CorrelationDialog.apply → fit_plot`，以及直接调用 | Pearson 系数/N/p 表、协方差/总体相关系数 CI 表；全部迁移 |
| `nonpara_cor.print_correlation` | `spearman`、`kendall`、`hoeffding`；`CorrelationDialog.apply` | 三种方法复用同一个系数/N/p 表；共同迁移 |
| `linear_plot.multi_fit` | `MCorDialog.apply` | Pearson 系数矩阵和 p 值矩阵；迁移报告层 |
| `linear_plot.multi_fit_orig` | 保留的公开旧入口和直接调用 | 重复的 Pearson 系数矩阵和 p 值矩阵；单独迁移、单独测试 |
| `fit_dialog.print_multi_col_tables` | `MCorDialog.apply` 的 Spearman/Kendall/Hoeffding 分支 | 每种方法各一张系数矩阵、一张 p 值矩阵；迁移报告层 |
| `dist_fit.print_table` | `fit_norm`、`fit_t`、`fit_gamma`、`fit_lognorm`、`fit_expon`、`fit_weibull` | 分布参数、-2LogLikelihood/AICc/BIC、AD 拟合优度三表；六个生产函数均覆盖 |
| `dist_fit.compare_dist` | `FitDistDialog.apply`；`singleHistoDialog.apply` 复用单个分布拟合；直接调用 | 条件性分布比较表：AICc、权重、BIC、-2LogLikelihood；排序/失败/单模型行为保留 |
| `pandastable_local.stats.StatsViewer.summary` | `core.Table` 继承 `core_orig.Table` 的模型拟合入口，`doFit → summary`，摘要按钮 | 原生 OLS/GLS 的模型摘要、系数/SE/t/p/CI、残差诊断；Logit 的摘要、系数/SE/z/p/CI；全部迁移 |

`Residual.py`、`basic_dialogs.py` 和 `sb_hist_dialog.py` 自身不另建这些表格，
沿调用链获得统一组件，不增加转发适配层。独立 ANOVA 分析模块不属于本次回归 ANOVA 迁移范围。
未新增 OLS 系数 CI、分布参数 CI、新的拟合方法或其他统计分析项目。

## 数据、显示和文本契约

- 所有报告通过 `StatTable → Minijmp.print → txt_viewer.add_table`，复用 G8 的 `TableBlock`、Excel/PNG 导出。
- StatsViewer 的独立摘要窗口也直接使用 `txt_viewer`。原生摘要按 statsmodels 原有表间分隔规则输出，保留附注、警告及完整原文；支持保存、关闭和重新打开。
- 原 PrettyTable 负责兼容文本和显示字符串，原始数值另传 `values`；不从 ASCII、三位小数字符串或科学计数法显示文本反推估计值。
- `format_stat`、统计公式、返回结果、置信水平、变量标签、比较排序和所有绘图代码均保留。
- N/自由度/观测序号在 Excel 中采用整数格式；普通报告保留三位小数显示规则，底层数值不舍入。
- 原生 statsmodels 摘要沿用其科学计数法、宽度、有效数字及列标签。系数及摘要原值取自模型结果，残差诊断取自原生 `diagn`；Durbin-Watson 沿用同一个 statsmodels 函数和 `wresid`。Excel 使用 General，保留数值及其完整精度。
- 显式传入原显示字符串，保留 `*`、`inf`、`-inf`、缺失、极小 p 值的原文本语义；Excel 对有限实数保留原值，其他单元格保留显示标记。
- 主工作目录 G8 公共组件未修改；没有引入第二套表格控件、导出器或依赖。

## 源码遗留输出审计

| 遗留形式 | 判断和处理 |
| --- | --- |
| 范围内的 `gen_table`、`add_row`、`format_stat` | 保留，用于生成与旧 TXT 一致的 PrettyTable 文本；实际报告端口已经接收 `StatTable`，并非遗留的普通字符串报告 |
| `multi_fit` / `multi_fit_orig` 的 `cor_res` | 保留的内部相关结果字典矩阵，含相关椭圆参数；仅将已有报告的系数/p 值投影为表格，未更改此矩阵 |
| `create_inset_grid` 的 `inset_axes`、`axs`，`fit_plot` 的椭圆坐标、CI/PI 线条 | 绘图辅助对象/矩阵，保留；没有作为统计报告迁移 |
| `Residual.py` 的残差、拟合值向量 | 内部计算和绘图输入；没有新增原代码不存在的 OLS 逐行残差报告 |
| `StatsViewer.plotLogit` 中的 `print(fit.pred_table(0.5))` | 原绘图方法的控制台辅助矩阵，不走报告窗口或摘要入口；保留，未改绘图行为 |
| `dist_fit.fit_jsu` 的 `print(johnsonsu.fit(data))` | 独立调试用参数元组；没有表格、`print_port` 或 Dialog 分析入口，未包装为新报告项目 |
| `linear_plot.py` 两处注释掉的 `print(str(ax.get_position()))` | 未执行的绘图调试注释，保留 |
| 模型公式、假设、统计说明、变量清洗信息、失败提示 | 普通文本，全部保留 |

新增 AST 检查对 10 个实际表格生产函数验证：报告端口存在 `StatTable`，
没有 `print(str(table))` / `print_port(str(table))`。StatsViewer 的原生表格转文本
仅用于保留原始 TXT 载体，传入结果窗口的对象仍为 `StatTable`。

## 验证

迁移前先执行 25 组报告，写入固定夹具 `tests/fixtures/g10_before.json`；
迁移后逐字符比对，不在测试中重新生成预期文本。

- G10 专项覆盖 41 个用例：25 组固定文本、每张实际报告的真实 Excel/PNG 文件读回、三种原生模型、应用路由/TXT、两种相关 Dialog、科学计数法与特殊标记、100 行残差、原生窗口关闭重开及七组源码审计。
- Excel 验证所有行列、数值类型、未舍入精度、逐列格式、`1e-100` 级 p 值、公式样式变量标签及非有限值显示；PNG 验证真实解码、全表高度及末行区域。100 行残差表检查 Excel 的第 102 行和 PNG 底部。
- 真实 Tk 窗口接收全部 25 组报告，逐字符验证 Text 内容及实际保存的 TXT，并调用原生菜单执行真实 Excel/PNG 导出；原生摘要另作实际 TXT 保存验证。
- G3 已有 OLS/正交回归/残差、分布拟合、直方图入口和固定统计结果测试继续通过；增强真实 Dialog 测试，断言其输出对象确为 G8 表格。
- G3 计算/返回/绘图 AST 基线检查通过。G4 原守卫仅放行 G10 的两处报告块和 G8 窗口集成，继续比较其余共享源码及统计计算。
- 共享统计、边界、G2、G4、G5、G6 专项合计 **408 passed**，32 条既有常量数据、椭圆数值和弃用警告。
- G1 文本、G1 统计、G3 显示/计算/回归/分布测试在关联批次验证，修正新增测试夹具的参数类型/类名及原生摘要时间戳跨秒误报后，失败用例复测通过。没有更改产品计算来适配夹具。
- `git diff --check` 通过。没有提交、推送、合并，未修改主工作目录。

复现主要验收：

```powershell
$python = 'C:\Users\shaoy\Documents\PythonEnvs\minijmp\Scripts\python.exe'
& $python -m pytest tests/test_g10_tables.py tests/test_g3_regression_reports.py tests/test_g3_distribution_reports.py tests/test_g3_computation_contracts.py tests/test_g1_text_output.py -q
& $python -m pytest tests/test_g2_basic_reports.py tests/test_statistics_regressions.py tests/test_statistical_edges.py tests/test_g4_quality_reports.py tests/test_g5_spc_reports.py tests/test_g6_chart_presentation.py -q
```

## 复杂度审查及边界

no-stop-gpt Audit：G8 组件直接复用；原值和显示字符串分别承担 Excel 精度与旧 TXT
兼容的必要职责。新增的 `model_summary_tables` 只对接原生摘要的现有表格，
避免从舍入文本解析数字；没有注册表、缓存、配置、后台任务或兼容框架。
清除了正交回归中不适用于其列名的格式分支；保留所有原有统计说明和错误行为。

未逐项人工点击完整主程序菜单，也未运行整个仓库全部测试；实际 Dialog.apply、
真实 Tk、导出菜单和文件已经自动验证。沿用 G8 的整表控件/整张 PNG，
不增加分页或虚拟化；极大表仍受 Tk 控件数量和内存限制。原生适配范围为
现有 StatsViewer 可选的 OLS、GLS、Logit，没有扩展其他模型摘要格式。
