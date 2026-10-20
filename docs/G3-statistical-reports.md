# G3 回归、ANOVA、分布拟合与卡方报告验收

日期：2026-10-20。以执行开始时的干净工作树为基线，先读取最新源码、现有测试及 G1/G2 验收文档。
源码及测试快照保存在 `%TEMP%\minijmp-g3-before-20261020`；没有使用早于 G1/G2 的 Git 版本替代基线。
本阶段只调整报告内容、表格、格式和说明；不升级依赖，不 commit、push 或 merge。

## 入口核对与修改前后差异

| 类别 | 原有计算与 G1/G2 基础 | G3 报告改动及边界 |
| --- | --- | --- |
| 普通线性回归 | 截距、斜率、标准误、绝对 t 值及 p 值，R²/调整 R²、S、响应均值、ANOVA、失拟与残差正态性；G1 已纠正检验解释 | 增加方程和 X/Y 对象说明；模型摘要、系数、ANOVA 与诊断分表。F/p 纳入对应来源行；t 明确为绝对值。失拟表原“总计”的 SST/总自由度改为现有 SSE/误差自由度，正确表示失拟加纯误差；无可用失拟检验时说明条件。原算法用 -1 表示不可估计的 t/F 时，报告显示 `*`，不修改原返回值。未计算的系数 CI 不补算 |
| 正交回归 | 斜率/截距及正态近似 CI、测量误差方差、拟合 X/Y、残差、标准化残差；共享 G2 正态性报告 | 明确 Var(Y误差)/Var(X误差)、样本量、系数 CI 的参数与水平；不套用 OLS 的 R²/t/F 解释；逐观测表统一精度。保留独立 `print_residual` 开关，即 `print_out=False, print_residual=True` 仍输出逐观测表 |
| 单因素 ANOVA | 各组 N、均值、合并误差方差下的均值标准误/CI，以及组间/组内/总计 SS、DF、MS、F/p | 组摘要在前，区间上下限分列，明确为各组总体均值的单独双侧 CI；主表正确区分组间、组内误差和总计，保留所有数值 |
| 均值逐对比较 | 全部组共用合并方差、逐对 p 值、均值降序字母分组；原自由度为 N−1 | 原低精度三角矩阵改为组别 1/组别 2/p 值列表，保留全部配对和字母顺序；明确双侧、未作多重比较校正及共享字母不等于证明均值相等。字母分组沿用旧算法，具体差异以逐对 p 值为准。保留 N−1 算法，不改成 ANOVA 的误差自由度 |
| 双因素 ANOVA | III 型调整平方和，含/不含交互作用两条路径，因子水平数和主表；未实际计算各组均值摘要（源码中只有注释） | 因子信息、N、III 型说明与中文主表；无交互模型不伪造交互行或显著性参数；不新增组均值或事后检验 |
| 嵌套 ANOVA | GRR 独立平衡嵌套模型，操作员、操作员内零件、重复性、总计及不同 F 分母 | 只优化 ANOVA 主表、嵌套设计及假设说明；保留后续 GRR 方差分量/计量评估报告。EMP 交互分量单列、AIAG 并入再现性的区别保持原样 |
| 分布拟合 | 六种分布：Normal、Student's t、Gamma、Lognormal、Exponential、Weibull；原参数、冻结 rv、-2LogLikelihood/AICc/BIC、AD/近似 p | 补充 N，中文参数/估计值表、似然指标表、AD 表；说明位置/尺度/形状/自由度以及对数正态的 mu/sigma；区分 scale 与标准差。CI 未计算则明示，不增加 KS 或其他指标 |
| 分布比较 | 原 AICc 权重计算与降序排序，失败候选跳过，小样本 AICc/权重可能为 NaN | 保留选择、顺序和权重；纠正“权重是最佳模型概率”的旧表述；区分 AICc/BIC 与 AD；不可用值显示 `*` 且不据此给出优劣结论；全部候选失败时说明无法比较，不生成空表 |
| 列联表卡方 | 未校正 Pearson 和似然比、DF、p，以及内部已有观测/期望频数；G2 单比例静默嵌套使用该计算 | 独立性 H0/H1、观测/期望频数、合计、方法/统计量/DF/p 表；按已有期望频数提醒小于 5 的单元格。保留 `print_table` 和标签条件，不增加 Yates/Fisher 算法 |
| 分类概率拟合优度 | 原始或汇总计数、假设概率、原有大样本参考行列联表近似 | 独立命名为拟合优度，明确其 H0；观测计数、估计概率、假设概率与原 Pearson/似然比结果分表；不再误用独立性标题。返回结果没有提供期望频数，不另行推算，报告说明限制；保留概率校验/按比例调整与取消行为 |

所有报告复用 `utilities.gen_table()`、`format_stat()` 和原 `print_port`。
文本标识左对齐，数值右对齐；常规统计量三位小数，整数计数保留原精度；`*` 表示不可用或不适用。
报告表头采用 ASCII 统计缩写及中文，避免东亚字体模糊宽度字符错列；表外保留标准数学符号。
新增适用的 H0/H1、模型条件、p=0.000 舍入说明；未将 p 值解释为 H0 为真的概率。
区分平均响应 CI、单次新观测 PI、回归系数 CI；不把相关当因果或把高 R² 当模型正确。

## 实际修改文件与重复入口

生产源码共十份：

| 文件 | 修改函数/范围 | 已核对的消费者与重复实现 |
| --- | --- | --- |
| `code/linear_fit.py` | `linear_fit()` 的打印分支及报告导入 | `fit_plot()`、残差分析内部静默拟合 |
| `code/ortho_fit.py` | `orthogonal_fit()` 两种打印开关及报告导入 | `fit_plot(ortho=True)`、独立调用及逐观测诊断 |
| `code/linear_plot.py` | `fit_plot()` 新增纯打印说明 | `LinearFitDialog`、继承其 apply 的 `OrthoFitDialog`；原 CI/PI 曲线代码不变；G2 的 `multi_fit()` 与 `multi_fit_orig()` 保留 |
| `code/Residual.py` | `resid_test()` 增加对象与解释 | `linear_fit_resid_test()`、`ResidDialog.apply()` 及直接残差入口均覆盖 |
| `code/one_way_ANOVA.py` | `one_way_anova()`、`JMP_ANOVA_t_test()` 打印分支 | `Anova1WayDialog` 分组/堆叠路径、旧 `Anova1WayDialog_old`、独立 `TtestDialog`、GRR 静默消费者 |
| `code/two_way_anova.py` | `two_way_anova()` 打印分支 | 嵌套列表/平铺因子输入，含/不含交互，`Anova2WayDialog` 及 GRR 自动交互选择 |
| `code/GRR.py` | `grr_nested()` 中 ANOVA 主表与说明、格式导入 | `GRRNestedDialog.apply()`；核对 `grr_anova_EMP()`、`grr_anova_AIAG()` 与 `grr_master()`，保留计量系统分析模型与其专项报告 |
| `code/dist_fit.py` | 共享 `print_table()`、六份 `fit_*()` 与 `compare_dist()` 的报告 | `basic_dialogs.FitDistDialog.apply()`、`sb_hist_dialog.singleHistoDialog.apply()`；六种候选与比较均覆盖；`fit_dialog.py` 中无分布拟合实现。`fit_jsu()` 是无报告的拟合包装，原样保留 |
| `code/chi_sq.py` | 仅 `chi_square()` 打印分支 | `Chi2TableDialog.apply()` 原始/汇总计数/行标签路径；G2 `prop_test_1sample()` 的静默嵌套路径；其余标准差/比例计算报告不变 |
| `code/chi2_dialog.py` | `Chi2PropDialog.apply()` 的纯报告部分、格式导入 | 分类原始数据/汇总数据、概率归一化、取消/无效输入路径；未改控件、布局、交互或概率算法 |

另核对 `pandastable_local.stats.StatsViewer` 的 OLS/GLS/Logit：直接显示 statsmodels 自带完整 summary，
已含模型方法、样本数、系数/SE/t或z/p/CI及各自摘要和诊断。继续复用现有实现，未改其返回、编辑器及绘图。
新增测试用三种真实拟合结果验证 summary 原样传递，避免漏掉其他回归类型或将 Logit 套用 OLS 表。

## 测试与数值不变性证据

使用项目原有解释器 `C:\Users\shaoy\Documents\Minijmp\.venv\Scripts\python.exe`：
Python 3.11.9、SciPy 1.15.3、pandas 3.0.6、PrettyTable 3.18.0、statsmodels 0.15.0。
已验证实际解释器和依赖导入路径；未安装依赖，未使用 Codex bundled runtime 执行项目测试。

- 修改前 G1/G2 与统计相关基线：**325 passed，7 warnings**。
- 对执行前快照与当前实现完成 **104 次精确返回值对照，0 次异常**：
  递归比较原始 Python/NumPy 类型、字典键及顺序、列表/元组/数组、NaN；冻结分布比较分布名、args/kwds及固定点 CDF/PDF。
  覆盖负斜率/重复 X/完美拟合、不同 alpha/误差比/输出开关，重复标签/两种 ANOVA 模型，零频数/零边际，
  六种拟合/候选子集/空集合，以及 GRR 嵌套和 EMP/AIAG；返回完全相同。
  `fit_plot()` 的线条数据、标签、轴范围和 Residual 两入口的图形数据同时精确一致。
  对照脚本位于快照目录 `verify_g3.py`，只用于本次验收，不成为项目依赖。
- 仓库内 `tests/fixtures/g3_computation_baseline.json` 固定执行前 **26 个函数/方法**的计算 AST 摘要。
  测试仅剔除明确报告分支/语句，保留计算、签名、默认值、返回和绘图。
  卡方 Dialog 专门规范化一次相同的 `chi_square()` 调用及已识别的表格语句，仍检查清洗、校验、归一化、大样本参考行及参数。
  旧 Dialog 完整守卫只将这一份接管的报告入口交给新约束，其他方法继续原样检查。
- `tests/test_g3_regression_reports.py`：系数/摘要/ANOVA/失拟/正态性各单元格、完美拟合不可估计值、正交 CI/误差比/逐观测行、开关、实际 Dialog、旧 StatsViewer 三种模型及曲线契约。
- `tests/test_g3_anova_reports.py`：单因素/逐对比较/字母分组/双因素含或不含交互/非平衡设计/嵌套 GRR，原始类型和固定值、实际及旧 Dialog、输入保护、GRR 路由。
- `tests/test_g3_distribution_reports.py`：六份重复拟合和共享表格、参数对应、AD/ABL/排序、不可用值/失败候选/空比较、真实分布及直方图 apply、原数据保护与拟合曲线。
- `tests/test_g3_chi_square_reports.py`：Pearson/似然比区分、期望频数/合计/小频数、大整数不截断、固定原值/类型/键序、两类 Dialog 与 G2 静默嵌套入口。
- `tests/test_g3_report_display.py` 及各类专项：在真实 G1 `txt_viewer.output_font` 中比较中文/英文/长标签表格分隔线像素位置；覆盖四类报告和嵌套表。
- `tests/test_dialog_translation.py` 只适配上述被接管报告的 AST 守卫；其完整清洗/计算约束由新测试接续，没有移除输入保护验证。

具体最终命令及实际结果见下方最终验证记录。

## Diff 与复杂度审查

已实际阅读十份生产源码的最终 patch，以及新增测试和旧守卫调整。
主审和独立只读交叉审查同时检查统计语义、字段映射、重复入口和越界修改。
交叉审查发现旧字母分组在极不平衡样本量下可能将显著不同的配对标为同一字母，
因此将新增说明收窄为“沿用现有算法，具体差异以逐对 p 值为准”，增加反例回归，保持原分组算法和结果。
按 no-stop-gpt Audit 核对：只复用原有表格/格式工具和局部行列表，没有增加报告对象层、配置、状态、缓存、fallback 或第三方依赖。
新增 AST/显示测试服务于本任务明确要求的计算不变、限定源码检查及实际中文对齐验收。

原有 LF：`linear_fit.py`、`chi_sq.py`、`GRR.py`；其余七份生产文件原有 CRLF 保留。
`tests/test_dialog_translation.py` 原有 LF 保留；无整文件换行转换、无关重构或意外删除。
执行前快照中其余源码与测试均逐字节未变；工作区初始没有需要保留的并行未提交改动。

## 已知问题及范围限制

- G1/G2 记录的 Fisher 零频数右尾、Pearson 完全负相关区间、Blaker 全事件边界均未修改。
- 非正态 AD 的 p 值沿用原近似且没有分布专用校准；小样本 AICc/权重 NaN 的原排序行为保留，只补充解释。
- 分类拟合优度沿用大样本参考行近似，未提供期望频数且不自动作小期望频数判断；没有改为新的拟合优度算法。
- 均值逐对比较原 N−1 自由度和未校正 p 值保留；双因素 III 型平方和及原误差算法原样保留。
- 旧字母分组算法不能保证共享字母的每一对均不显著：`[[-20,42],[10]*100,[9]*100]`
  三组均可标为 A，但后两组的逐对 p 值约 0.023944。报告不再作此保证，原算法不在 G3 修复。
- 没有补算 OLS 系数 CI、分布参数 CI、双因素各组均值或新的多重比较/拟合优度指标。
- StatsViewer 原生完整 summary 和 GRR 方差分量/计量评估部分保留，避免在呈现任务中替换其统计模型。
- 自动验证真实 Tk 字体和 Dialog/Figure 路由；未进行人工桌面点击验收或跨操作系统字体验证。

## 最终验证记录

四类综合复验时 G3 专项 **179 项全部通过**，加上旧 Dialog AST 守卫共 **180 passed、5 warnings**：
回归 23、ANOVA 48、分布 30、卡方 36、显示 16、计算契约 26。
警告来自完美拟合残差零极差/AD 的原边界、原 `set_tight_layout` 调用及小样本 statsmodels 摘要。

```powershell
$python = 'C:\Users\shaoy\Documents\Minijmp\.venv\Scripts\python.exe'
& $python -m pytest tests/test_g3_regression_reports.py tests/test_g3_anova_reports.py tests/test_g3_distribution_reports.py tests/test_g3_chi_square_reports.py tests/test_g3_report_display.py tests/test_g3_computation_contracts.py tests/test_dialog_translation.py::test_original_analysis_code_is_unchanged -q --tb=short
```

随后交叉审查补充字母分组极不平衡反例，并只收窄相关说明。ANOVA 专项增至 49 项，
与 26 项计算契约一起复验：**75 passed**。其他未变化范围复用上述结果，
最终新增 G3 专项合计 **180 项**，均已验证；加上旧 Dialog 守卫共 181 项独立验收用例。

```powershell
& $python -m pytest tests/test_g3_anova_reports.py tests/test_g3_computation_contracts.py -q --tb=short
```

扩大回归覆盖 G1/G2、统计功能、GUI/Dialog、文本窗口、文件/导入、帮助中心、菜单与启动等：
**935 passed、1 failed、4 deselected、21 warnings**，耗时 205.75 秒。
此轮收集发生在最后补充两个非平衡用例与一个全部拟合失败用例之前；这些用例及最终报告状态已由上面的 180 项最终复验覆盖。
G1/G2 在本轮没有新增失败，没有以重复运行排除失败后宣称全量通过。

```powershell
& $python -m pytest tests -q --tb=short -k 'not test_windows_launchers_resolve_their_directory_and_propagate_exit_code'
```

唯一失败是 G1/G2 已记录的
`test_dialog_translation.py::test_real_legacy_menu_entry_opens_all_six_panels`，
未修改的 `pandastable_local/plotting.py:720` 使用 `pd.to_numeric(errors='ignore')`，
与当前 pandas 不兼容，抛出 `ValueError: invalid error value specified`。
已另用本次修改前源码快照执行同一测试，**1 failed**，复现相同位置与异常，确认不是 G3 引入。

```powershell
& $python -m pytest "$env:TEMP\minijmp-g3-before-20261020\tests\test_dialog_translation.py::test_real_legacy_menu_entry_opens_all_six_panels" -q --tb=short
```

排除的四项是 G1/G2 已记录的 Windows 启动器临时项目测试（BAT 缺 `.venv` / VBS 超时），本轮未重新执行，不能视为通过。
完整新增测试可以直接在仓库运行，不依赖本机临时快照；快照只用于额外的改前/改后验收对照及已有失败复现。

`git diff --check` 通过；已审查实际 patch 与新增文件，没有整文件换行转换或范围外代码修改。
**G3 验收完成**：四类入口及重复路径完成核对，纯报告优化完成，数值/接口/图形契约保持，专项与相关回归无新增失败，
已记录真实测试限制并保留独立算法/环境问题，未提交、推送或合并。
