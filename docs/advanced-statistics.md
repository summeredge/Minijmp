# MiniJMP 高级统计分析阶段记录

P0-1 完整回归、P0-2 PCA、P1-1 时间序列及 P1-2 高级 SPC 均已完成各阶段专项验收（2026-10-22 至 2026-10-23）。这不代表全项目所有测试通过或发布验证完成；完整 PyInstaller 构建及全部 DPI 人工检查尚未执行。

## P0-1 入口与职责

统计菜单新增“完整回归分析”，回调 `Minijmp.advanced_regression` 延迟导入 `RegressionDialog`，传入打开时的 `self.table`、`self.table.model.df` 和应用对象。保留原有线性回归、残差图、正交回归等入口及其行为。

| 位置 | 职责 |
| --- | --- |
| `code/advanced_regression.py` | OLS/WLS/二元 Logistic/非线性计算、模型项、筛选、诊断与预测；不依赖 Tk GUI |
| `code/regression_dialog.py` | 来源表快照、选列及参数、后台任务和取消、结果页、工作表/Excel/CSV 输出 |
| `code/regression_plots.py` | 图形绘制、样本源行号关联；复用现有图窗 |
| `code/MiniJMP.py` | 统计菜单及延迟回调 |
| `help/pages/advanced-regression.html` | 中文操作和统计定义；主题 `stats.advanced_regression`，与 GUI 帮助及 F1 一致 |
| `help/help-map.json`、`help/assets/search-index.js` | 帮助主题映射和生成的离线正文检索索引 |
| `tests/fixtures/g12_table_inventory.json` | 新文件及实际 StatTable 生产位置人工审计；不刷新旧报告位置 |

## 统计定义与解释边界

- OLS 在设计矩阵上最小化残差平方和，残差自由度为 n−rank(X)。有截距时报告中心化 R²、调整 R²、RMSE=√(SSE/n)、残差标准差 S=√(SSE/(n−p))、系数 t 推断和适用 ANOVA。
- WLS 权重是误差方差的倒数，必须正且有限；用 `sqrt(w)` 白化 X、Y、残差。协方差、杠杆值、Cook 距离及残差诊断基于白化空间，原始残差保留数据单位。新观测预测区间需要新样本权重。
- Logistic 建模事件概率及 logit；采用 z/Wald 推断、二项似然、适用的 AIC/BIC、注明定义的伪 R²、分类评估与 ROC/AUC。不得套用 OLS R²、调整 R²、ANOVA 或连续响应的预测区间。
- 非线性最小二乘的参数协方差与区间依赖局部 Jacobian 和渐近近似；不能称为精确区间。自定义公式应为受限数学表达式，参数初值须与公式对应；收敛并不保证全局最优。
- 多项式、交互项和分类编码必须与预测复用同一设计定义；保留层级并将分类变量作为完整项筛选。前进、后退、双向和最佳子集在同一有效样本集合比较候选模型；最佳子集必须限制搜索规模并明确提示超限。
- AIC/BIC 越小越好，调整 R²越大越好。不同响应尺度、数据行集合、权重/似然约定之间不直接比较。筛选后的常规 p 值和区间未修正选择偏差。
- **CV 不在本阶段。** 训练集指标、分类和 ROC/AUC 不表示独立预测性能；没有新增交叉验证入口或宣传。
- VIF、残差正态性/异方差/自相关和影响点统计需说明适用模型及阈值；异常点仅标记，不自动删除。

详细统计公式、假设、诊断解释和操作说明见中文帮助。具体检验名称、阈值、筛选范围及模型限制须与最终计算文件核对，不能仅按通用统计定义宣称已有实现。

## 数据与交互约定

分析以打开窗口时的来源工作表快照为准。缺失默认报错，显式选择后才联合删除当前模型所需列的缺失行；不自动插值或填补。非有限数据、常量列、共线性、奇异矩阵、无效权重及自由度不足明确提示。训练与预测保留各自快照的从 1 开始的位置行号，不将 DataFrame 标签索引当作工作表位置；缺失删行后保持原位置。

预测使用训练变量、类别水平、模型项及参数。未知类别、缺列或不合法数值不静默转换。切换工作表后输出和图形仍关联来源表；源表改变后不按旧快照盲目定位，源表删除后拒绝继续输出。新预测行号属于预测表，不能拾取成训练表同号行。

GUI 选项与当前实现对应：Y、多个 X、其中的分类列，OLS/WLS/Logistic/非线性，多项式次数、两两交互，筛选与准则、置信水平、缺失策略、曲线/公式和初值。结果使用 Notebook 表页；独立的“图形”页提供图形类型选择和“打开图形”按钮。“输出诊断页面”控制页面展示，“输出完整报告”输出训练结果；预测结果从“新数据预测”页单独导出或写入新表。

取消为协作式取消：设置取消请求，等待当前数值调用返回并丢弃该次结果，保留上次有效结果。关闭窗口取消待执行任务；不能保证中断底层求解器正在执行的单次调用。

结果 DataFrame 经 StatTable 展示/报告，原始数值用于工作表、Excel 和 CSV；不按显示精度预先舍入。图窗复用现有保存功能。新增结果表使用原有工程机制，不改旧工程结构，也不引入本阶段没有要求的模型保存格式。

## P0-1 验收记录（2026-10-22）

项目解释器：`.venv/Scripts/python.exe`，Python 3.11.9；NumPy 2.4.6、pandas 3.0.6、SciPy 1.15.3、statsmodels 0.15.0、Matplotlib 3.11.2。未安装新依赖。

| 生产入口 / 方法 | 独立参考及测试 | 已验证边界与结果 |
| --- | --- | --- |
| `fit_regression` OLS/WLS | `test_linear_report_prediction_and_influence_independent`：正规方程独立求解、加权投影、Student-t/F 分布、Gaussian 似然 | 系数/SE/p/CI、R²、调整R²、RMSE、ANOVA、AIC/BIC、杠杆/Cook、预测CI/PI；权重为列或数组，保留输入 |
| 白化诊断与 VIF | `test_wls_diagnostics_whitened_and_vif_reference`：DW定义、残差平方辅助回归 nR²、加权辅助回归 VIF | WLS白化、Shapiro、Koenker BP、DW；未将近似诊断称为精确检验 |
| 分类、多项式、交互设计 | `test_design_categorical_cubic_interaction_and_fixed_training_encoding`：手工构建设计列，独立正规方程 | 三次项、哑变量、交互、固定训练类别、未知类别拒绝、强层级整组筛选 |
| 二元 Logistic | `test_logistic_independent_likelihood_hessian_auc_and_intervals`：独立最小化 Bernoulli 负对数似然及解析 Hessian；AUC为正负样本对胜率并列计半 | Wald z、协方差、McFadden、AIC/BIC、概率CI、GLM影响近似、混淆矩阵、ROC并列；完全分离/单类别拒绝 |
| 前进/后退/双向/最佳子集 | `test_selection_against_independent_enumeration`、`test_logistic_selection_independent_likelihood`：独立穷举评分、Bernoulli优化 | OLS/WLS的AIC/BIC/调整R²、Logistic的AIC/BIC；固定有效样本、强层级、仅截距、4096上限和取消；逐步法不保证全局最佳 |
| 指数、幂、S形非线性 | `test_nonlinear_analytic_reference_parameters_covariance_prediction`：已知参数加与解析Jacobian正交的扰动，独立解析协方差/区间 | 参数、SE、均值CI/观测PI、Gaussian AIC；局部近似明确标注，奇异和定义域错误拒绝 |
| 自定义公式 | `test_custom_formula_multivariate_and_no_input_mutation`：线性特例的独立正规方程；`test_formula_rejects_unsafe_ast` | 多X公式、初值/定义域、AST安全白名单、不可识别、取消、输入不变 |
| Tk GUI、工作表归属、导出 | `test_regression_dialog.py` 6项 | 四类模型建模/预测、取消保留旧模型、变更/关闭源表、切表后源表输出；真实Excel重读、PNG重开 |
| 图形与行关联 | `test_regression_plots.py` 11项 | 九类图渲染保存/重开；鼠标点击映射缺失删行前位置；不支持的模型图形明确报错 |

最终合并检查：

```powershell
& .\.venv\Scripts\python.exe -m pytest tests/test_advanced_regression.py tests/test_regression_dialog.py tests/test_regression_plots.py tests/test_g12_inventory.py tests/test_menu_localization.py tests/test_help_center.py tests/test_sheet_context.py tests/test_worksheets.py tests/test_file_io.py tests/test_g3_computation_contracts.py tests/test_column_selection.py -q
```

**298 passed**，含新计算模块93项独立参考及关键边界用例。G12补齐新文件及既有`icon_resource.py`历史漏登；两处StatTable构造分别保留，同一训练结果的完整报告转发不重复计入逻辑表。菜单、帮助映射及离线检索索引已同步。

实际验收产物：`advanced-evidence/regression-window.png`、`regression-window-compact.png`（1120×760和880×620真实Tk窗口，已打开核对）、`regression-observed.png`、`regression-coefficients.xlsx`（已重读3×8原精度系数表）。小窗口中的预测/导出按钮和表格滚动已检查。

复杂度检查按 no-stop-gpt Audit：复用statsmodels、SciPy、原有SheetApp/StatTable/图窗；安全AST解释器对应自定义公式的安全边界，来源快照和取消事件对应异步归属；筛选只存标量摘要，最终重新拟合所选模型，避免保留最多4096份设计矩阵。未引入通用分析框架或新依赖。

明确限制：非线性为局部最小二乘及一阶近似区间；筛选后的常规推断未校正选择偏差；分类评估为训练集结果。单次底层数值调用不能强制中断，取消后不接收其结果。未执行完整PyInstaller构建（现有脚本可静态跟踪新增普通导入），未做全量测试或所有DPI下人工验收。源工程结构未变，结果表沿用原有持久化。

另跑旧 `test_g3_regression_reports.py` 时，3项旧Dialog替身缺少既有列记忆功能新增的 `remember_columns` 而失败；本次没有修改这些旧生产入口或掩盖该失败。这与本次新模块专项通过分开记录。图标菜单并行改动曾短暂缺少导入函数，函数落盘后上述最终合并检查通过；相关图标源码及许可证不归本任务修改。

## P0-2 PCA 验收记录（2026-10-22）

已完成 `pca_analysis.py`、`pca_dialog.py`、`pca_plots.py`，统计菜单“主成分分析”及中文帮助 `stats.pca`。沿用前述项目环境，无新增依赖，不改变工程格式。

| 生产入口 / 方法 | 独立参考与关键验证 | 结果 |
| --- | --- | --- |
| `fit_pca` SVD、预处理、谱、投影 | `test_svd_pca_independent_eigh_and_projection` 用独立二阶矩/协方差 eigh，与样本SD ddof=1、手工rank1、宽矩阵、零空间偏离、固定训练预处理 | 数值通过；autoscale/center/none、手动及累计贡献率选维 |
| `t2_limits` 训练/投影控制限 | `test_t2_limits_inverted_distribution_definition` 用不完全Beta函数逆验CDF，区分 n/k/95/99/Phase I/II | 单侧上限；训练内Beta、新独立样本F；none模式不中心化，T²限不可用并标记未知 |
| Q / SPE 与控制限 | `test_model_limits_flags_and_q_moment_definition` 以独立eigh谱及不完全Gamma函数验CDF，遗漏单PC可化成缩放chi²1 | 95/99限、异常flags、零残差方差及新零空间偏差；近似假设明确 |
| T² / Q变量贡献 | `test_signed_t2_and_q_variable_contributions` 独立矩阵公式并逐样本验证可加和性 | T²采用 z_j·(PΛ⁻¹Pᵀz)_j 有正负；Q采用预处理残差平方非负 |
| CV辅助 | `test_cv_independent_fold_preprocessing_eigh_and_no_automatic_selection`、`test_cv_does_not_use_global_scale_or_leak_holdout` | 每折训练独立预处理；只显示留出行重构MSE，不以其单调下降自动选维 |
| 原变量A/B统计、选区与公共T² | `test_group_comparison_raw_units_independent`、`test_selection_geometry_including_boundary`、`test_hotelling_fixed_baseline_independent_inverse` | 原单位n/均值/样本std/均值差；矩形/椭圆边界包含；固定基线协方差，不静默伪逆 |
| 安全模型保存加载 | `test_pca_analysis.py` 模型往返和非法JSON/版本/形状/谱/参数测试 | 版本化JSON无pickle；保存训练值及预处理，复杂索引仅还原带类型显示标签，source_row保留 |
| 11类图形与真实模型、交互 | `test_pca_plots.py` 手工坐标/椭圆/χ²轮廓、MouseEvent、真实PCA结果、PNG重开 | 83项通过；任意PC、类别颜色、异常/未知、A/B独立选择、点击、贡献和对比图 |
| GUI集成与导出 | `test_pca_dialog.py` | 4项通过；建模/模型存取/新样本投影、来源绑定、取消、A/B对比、Excel重读、PNG重开、分类缺失、旧对比失效及回调断开 |

PCA计算专项 **145 passed**；合并回归采用以下最终批次，不把重叠结果相加：

```powershell
& .\.venv\Scripts\python.exe -m pytest tests/test_pca_analysis.py tests/test_pca_dialog.py tests/test_pca_plots.py tests/test_advanced_regression.py tests/test_regression_dialog.py tests/test_regression_plots.py tests/test_g12_inventory.py tests/test_menu_localization.py tests/test_help_center.py tests/test_sheet_context.py tests/test_worksheets.py tests/test_file_io.py -q
```

**486 passed，27.98 秒**。菜单、中文帮助/离线检索和G12清单同步通过。统计控制限公式参考 [NIST Hotelling control chart](https://itl.nist.gov/div898/software/dataplot/refman1/auxillar/hotell.htm) 的个体 Phase I/II 场景；本实现取指定覆盖率的单侧上限，不采用该页面默认双侧α/2。PCA估计子空间使T²限为近似；Q用遗漏谱前两矩匹配缩放卡方近似，训练和投影同用训练谱。T²/Q联合OR异常不代表全局误报率仍是5%/1%。

已打开核对真实Tk窗口截图 `advanced-evidence/pca-window.png` 和 `pca-window-compact.png`（1160×800、900×640），含类别图例、异常点、A/B高亮和样本T²贡献；另有 `pca-score.png`、`pca-contribution.png`、`pca-group-comparison.xlsx`（已重读4×8原单位统计）、`pca-model.json`（安全模型示例）。

按 no-stop-gpt 复查：沿用NumPy/SciPy/Matplotlib及原有SheetApp/StatTable；只增加请求所需的训练/投影、选区与后台任务状态。选区几何复用计算层helper，单变量/分组贡献直接向量化消费既有结果，避免逐行DataFrame构造；每次重绘断开旧selector和点击连接，清除选区时作废旧对比。后台加载保存及SVD取消不向Tk跨线程写入。

限制：控制限及得分χ²覆盖轮廓依赖近似正态/独立假设，不是均值得分区间；CV仅辅助；单次底层SVD不可强制中断。加载模型的训练结果没有自动绑定当前工程表；新样本投影后才可定位投影源表。未做全量PyInstaller构建或所有DPI人工验收。

## P1-1 时间序列验收记录（2026-10-23）

已完成 `time_series_analysis.py`、`advanced_time_series_dialog.py`、`time_series_analysis_plots.py`，统计菜单“时间序列分析”及中文帮助、离线索引、G12 文件和报告清单。无新增依赖；既有时间序列绘图入口和工程格式保持兼容。

| 能力 | 独立参考与验证 |
| --- | --- |
| ACF / PACF / 正负滞后 CCF | 独立自协方差公式、Yule-Walker 方程、已知延迟信号；CCF(k)=corr(Y_t,X_(t-k))，k>0 为 X 领先 Y |
| 趋势、季节分解 | 手工 OLS 及已知趋势季节信号；加法/乘法、周期与端点缺失 |
| ADF / KPSS | 辅助回归与手工 Bartlett HAC；原假设、左右尾和 KPSS 有界 p 值分别报告 |
| ARIMA / SARIMA | 白噪声、AR(1)、随机游走和季节 AR(1) 的解析预测及区间；Gaussian 似然 AIC/BIC、初始残差扣除、Ljung-Box 自由度 |
| 采样和来源 | 实际时间/固定周期、时区、缺失删行后间隔、重复时间戳首/末/均值与全部来源集合；默认均报错，不插值 |
| 图形、GUI、导出 | 九类图、鼠标来源映射和 PNG 重开；相关/分解/检验/ARIMA/SARIMA 的真实 Tk 操作、取消、切表、源表更改/关闭、Excel 重读和写入新工作表 |

实际验证（项目 `.venv`，Python 3.11.9）：

```powershell
& .\.venv\Scripts\python.exe -m pytest tests/test_time_series_analysis.py tests/test_time_series_analysis_plots.py -q
# 251 passed，15.00 秒
& .\.venv\Scripts\python.exe -m pytest tests/test_time_series_analysis_dialog.py -q
# 4 passed，7.58 秒
& .\.venv\Scripts\python.exe -m pytest tests/test_g12_inventory.py tests/test_help_center.py tests/test_menu_localization.py tests/test_sheet_context.py tests/test_worksheets.py tests/test_file_io.py -q
# 146 passed，10.86 秒
```

导出保留原精度数值；时区、时长及来源索引显式文本化，来源集合为 JSON，未来预测没有历史行号。已保存并检查 `advanced-evidence/time-series-window.png`、`time-series-window-compact.png`（1080×760 / 880×640）、`time-series-forecast.png`、`time-series-forecast.csv`。窗口截图显式按物理像素捕获，检查最小窗口中的底部导出操作。

按 no-stop-gpt Audit 复查：复用 statsmodels 与既有 SheetApp、StatTable、图窗；独立计算/绘图/GUI 边界对应现有架构，没有新增通用框架。快照、来源集合和取消事件分别服务切表归属、重复时间戳追踪和后台任务生命周期。

限制：相关区间为点态近似；趋势 OLS 假设独立误差。预测区间为给定参数的未来观测区间，不含参数估计不确定性。按观测顺序处理不规则采样会放弃真实时间间隔，须明确选择。单次底层拟合不能强制中断。未做全量测试、完整 PyInstaller 构建或全部 DPI 人工验收。

## P1-2 高级 SPC 验收记录（2026-10-23）

已完成 `advanced_spc.py`、`advanced_spc_dialog.py`、`advanced_spc_plots.py`，质量菜单“高级 SPC 控制图”、中文帮助 `quality.advanced_spc`、离线索引及 G12 清单。计算与 GUI 分离，复用 PCA 公共 T² 计算和控制限，不改 `control_chart.py` 的既有算法。

| 生产入口 / 方法 | 独立参考测试与定义 | 已验证范围 |
| --- | --- | --- |
| `analyze_spc` EWMA | `test_ewma_nist_example_and_independent_weighted_sum`：NIST 示例、独立有限权重和与权重平方和方差 | 参数估计/已知参数，Z₀=μ，动态启动限、λ=1、严格越限、异常行号 |
| `analyze_spc` CUSUM | `test_cusum_nist_detection_and_suffix_sum_reference`：NIST 第14点报警示例，穷举后缀和独立于生产递推 | 标准化双侧，k/h，负支取−C⁻，等于h不报警，报警后不复位 |
| `nelson_events` 八规则 | `test_each_nelson_rule_known_minimal_pattern`、边界/同侧/并列反例；JMP Table 3.8 | 规则勾选、最短窗口、末端报警与来源成员；R5/6 当前点须同侧超区，区界归内区、R7包含±1σ、R8须两侧 |
| `analyze_spc` 原变量 T² | `test_t2_independent_covariance_quadratic_forms_and_distribution_cdf`：独立协方差/矩阵逆二次型，以不完全 Beta 函数验两阶段分布 CDF | Phase I Beta、Phase II F，95%/99%单侧上限，固定历史参数、协方差长表、奇异拒绝、单变量特例 |
| 输入与来源 | `test_fixed_baseline_source_provenance_missing_and_comparison` 及边界测试 | 不同来源索引、显式删除缺失行、原位置不重编号、当前/历史不变、取消、常量/非有限/样本量不足 |
| `spc_plot` | `test_advanced_spc_plots.py`：独立表坐标、MouseEvent、真实后端和 PNG 重开 | 四类图、历史独立轴、阶段限、CUSUM仅标实际报警分支；T²零界不称下控制限；历史点不误定位当前行 |
| `AdvancedSPCDialog` | `test_advanced_spc_dialog.py`：真实 Tk、Excel/CSV 重读、来源与后台线程检查 | 四类建模、历史快照、已知参数、规则选择、报告/新表/图形、取消保留旧结果、来源更改/关闭、绘图失败保留旧图 |

方法来源：[NIST EWMA](https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc324.htm)、[NIST CUSUM](https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc313.htm)、[NIST 个体 Hotelling](https://itl.nist.gov/div898/software/dataplot/refman1/auxillar/hotell.htm)、[JMP 特殊原因规则 Table 3.8](https://www.jmp.com/support/help/en/19.2/jmp/options-panel-and-rightclick-chart-options.shtml)。EWMA启动方差由有限几何级数推得；T²采用指定覆盖率的单侧上限。Nelson R7不另外要求两侧都有点，R8要求两侧；所有约定在界面帮助明确，不暗示各软件所有默认设置相同。

实际验证命令与结果：

```powershell
& .\.venv\Scripts\python.exe -m pytest tests/test_advanced_spc.py tests/test_advanced_spc_plots.py tests/test_advanced_spc_dialog.py tests/test_g12_inventory.py tests/test_help_center.py tests/test_menu_localization.py -q
# 223 passed，27.13 秒；63计算、69图形、10GUI以及清单/菜单/帮助检查。
& .\.venv\Scripts\python.exe -m pytest tests/test_g5_spc_reports.py tests/test_statistics_regressions.py tests/test_statistical_edges.py tests/test_g3_computation_contracts.py -q
# 174 passed，5.99 秒，7条既有常量残差/坐标警告；原SPC AST冻结及统计行为通过。
& .\.venv\Scripts\python.exe -m pytest tests/test_help_center.py tests/test_menu_localization.py tests/test_windows_packaging.py -q
# 76 passed，8.60 秒，含现有Windows打包配置检查。
```

合并运行曾暴露旧 Tk 对象在后续数值线程触发循环 GC 时析构，产生2项GUI超时；单独GUI并未覆盖该顺序问题。已在 `tests/conftest.py` 对使用共享 `tk_root` 的测试，于测试结束后在主线程收集已关闭窗口对象；保持生产计算、取消和超时时间不变。上述同序合并批次复验223通过，无该析构警告，不将首次失败隐藏为通过。

10万行本机有界耗时检查：EWMA 0.109秒、CUSUM 0.144秒、Nelson 0.188秒（固定种子普通正态、已知μ=0/σ=1，包含结果及报警表构建；非通用性能承诺）。计算在线程中运行，Nelson固定窗口向量化；单次底层矩阵调用仍不可强制中断。

实际验收产物：`advanced-evidence/spc-window.png`、`spc-window-compact.png`（1120×780 / 900×640，已打开核对底部操作及结果滚动）、`spc-t2.png`、`spc-cusum.png`、`spc-alarms.xlsx`（重读24×11报警表）、`spc-t2-limits.csv`（4×5阶段/置信度/控制限/定义）。

no-stop-gpt Audit：复用公共 T² 和既有图窗/表格，没有加入新的分析框架、持久化格式或依赖。历史/当前快照、取消事件和图形回调对应明确的来源与生命周期边界。去掉了以“数据值相同”推断历史不独立的检查，只阻止使用同一来源表；独立数据可能恰好同值。绘图要求真实后端合约中的 CUSUM 规则列，未保留只为手工测试数据添加的猜测式报警兼容。

限制：个体控制图不替代子组均值图；历史基线应稳定、观测应独立，T²限依赖多元正态。自身数据估计单变量限仅为 Phase I 回顾近似。当前监控从初值重新启动，未实现跨运行在线状态续接；报警不自动剔除或重估参数。所有规则/时刻联合误报不能按单点α解释。未执行完整 PyInstaller 构建或全部DPI人工检查。

## 四阶段最终复核

P0-1、P0-2、P1-1、P1-2 专项验收均已完成，工程结构保持不变，无新增依赖，保留本地未提交修改。

最后复查发现，直接导出保护来源索引还不足以覆盖 TableBlock 内建导出及完整报告。已在既有 `sheet_context.py` 增加 `export_source_labels`，由四个新分析 GUI 复用，只在报告/外部导出边界将来源索引文本化，保护超过15位整数、前导零和缺失标签；数值统计量不舍入，写入新工作表仍保留原类型。`test_analysis_source_exports.py` 覆盖回归/PCA/时间序列的三个路径；高级SPC GUI专项覆盖相同路径。未修改公共 StatTable 或其他统计模块行为。

```powershell
& .\.venv\Scripts\python.exe -m pytest tests/test_advanced_regression.py tests/test_regression_dialog.py tests/test_regression_plots.py tests/test_pca_analysis.py tests/test_pca_dialog.py tests/test_pca_plots.py tests/test_time_series_analysis.py tests/test_time_series_analysis_plots.py tests/test_time_series_analysis_dialog.py tests/test_analysis_source_exports.py tests/test_sheet_context.py tests/test_worksheets.py tests/test_file_io.py -q
# 667 passed，70.11 秒；当时有2条上述Tk析构警告，随后同一测试清理边界修复。
```

该批次的算法未在随后修改；受清理边界和来源导出影响的GUI/工作表用例另行复验：

```powershell
& .\.venv\Scripts\python.exe -m pytest tests/test_regression_dialog.py tests/test_pca_dialog.py tests/test_time_series_analysis_dialog.py tests/test_analysis_source_exports.py tests/test_sheet_context.py tests/test_worksheets.py tests/test_file_io.py -q
# 84 passed，20.35 秒，无上述Tk析构警告。
& .\.venv\Scripts\python.exe -m pytest tests/test_advanced_spc_plots.py tests/test_g12_inventory.py -q
# 84 passed，9.41 秒，最终冻结的绘图合约及88个Python文件清单复核。
```

旧 `test_g3_regression_reports.py` 中3项替身缺少既有列记忆接口的历史失败保留在 P0-1 记录内；当前修复状态见下方收尾记录。本任务未将全项目所有测试声称通过。`git diff --check` 通过（仅提示既有文件CRLF换行转换），未提交或推送。

## 审查收尾（2026-10-23）

已为旧回归报告测试的 `SimpleNamespace` 替身补齐 `remember_columns=Mock()`，并断言三个旧对话框在成功完成分析后均恰好调用一次。保留原有数据清理、报告和绘图断言，不修改生产算法或列记忆实现。文档首段统一为四阶段专项验收完成，明确区分专项验收与发布验证。

```powershell
& .\.venv\Scripts\python.exe -m pytest tests/test_g3_regression_reports.py tests/test_column_selection.py -q
# 43 passed，5 warnings，5.31 秒；包含原先失败的三个参数化用例。
```

5条警告分别涉及完全拟合时常量残差的正态性计算、Matplotlib接口待弃用及12个样本下的峰度检验近似。本次仅修改测试替身和阶段文档，未重复运行此前853项通过的专项，也未执行全量测试、完整 PyInstaller 构建或全部 DPI 人工检查。
