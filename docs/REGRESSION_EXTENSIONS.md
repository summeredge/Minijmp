# 回归扩展：官方对标、统计约定与验收证据

范围：Poisson、名义多分类 Logistic、有序 Logistic、单/多响应 PLS。保留原有 OLS/WLS/二元 Logistic/非线性功能；不启动过程能力、质量工具或其他后续阶段。官方网页核对日期：2026-10-23，通过 agent-reach Exa 搜索及 web 原文交叉核对。

本文记录本次统计约定、独立参考和实际验收结果。数值与真实工作表 GUI 专项已通过；未执行完整 Windows 发布构建或 Minitab 桌面程序逐值复算。

## 官方对标与实现差异

| 模块 | Minitab 官方定义与来源 | MiniJMP 本次约定及差异 |
| --- | --- | --- |
| Poisson 链接 | 自然对数为默认典范链接；另有平方根和恒等链接。[Methods in Fit Poisson Model](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/regression/how-to/fit-poisson-model/methods-and-formulas/methods/) | 实现 log/sqrt/identity，拟合及预测严格校验正均值和链接域；支持连续/分类、多项式和交互项。权重、变量筛选明确拒绝。 |
| Poisson 推断 | 官方 SE/协方差使用观察 Hessian；典范链接下与 Fisher 信息相同。[Estimated equation](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/regression/how-to/fit-poisson-model/methods-and-formulas/estimated-equation/) | 生产使用 statsmodels GLM 默认协方差和渐近 Wald 推断。因此非典范 sqrt/identity 下不能承诺 SE、p、CI 与 Minitab 完全一致；这是计算约定差异的推论。 |
| Poisson 拟合优度 | Deviance 与 Pearson 衡量观测和拟合的偏离；Poisson 下 Pearson 的 χ²分布为渐近性质。[Goodness-of-fit formulas](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/regression/how-to/fit-poisson-model/methods-and-formulas/goodness-of-fit-statistics/) | 明确 χ²上尾近似、自由度和过度离散警示，不套用 OLS R²、ANOVA 或正态残差检验。 |
| 名义基准类别 | 建立 K−1 个相对响应参考类别的 logit。[Nominal methods and formulas](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/regression/how-to/nominal-logistic-regression/methods-and-formulas/methods-and-formulas/)；默认响应参考为数值最大、日期最新或文本字母序最后，允许更改；自定义文本顺序有例外。[Reference options](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/regression/how-to/nominal-logistic-regression/perform-the-analysis/select-the-analysis-options/) | 至少 3 类且必须显式指定 reference，不模仿默认猜测。分类 X 的参考水平与响应 reference 分开；X 采用训练中首次出现水平为基准的 0/1 编码，预测固定全部训练水平。 |
| 有序链接与假设 | 提供 logit、normit/probit、gompit/complementary log-log；gompit 为 log[−log(1−p)]。[Ordinal methods and formulas](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/regression/how-to/ordinal-logistic-regression/methods-and-formulas/methods-and-formulas/)；probit 对应潜在正态解释，gompit 不对称。[Ordinal options](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/regression/how-to/ordinal-logistic-regression/perform-the-analysis/select-the-analysis-options/) | 仅 logit/probit，必须显式给出完整类别顺序；不支持 gompit，也不将 log-log 与 complementary log-log 混称。logit 为比例优势；probit 为共享斜率的累积正态模型。没有比例优势假设检验。 |
| PLS 计算与 CV | NIPALS 同时分解预测量与响应，按逐步增加的成分拟合；通过留出再拟合计算 PRESS，响应联合验证。[PLS methods](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/regression/how-to/partial-least-squares/methods-and-formulas/methods/) | 数值 X、单/多 Y；始终中心化，可关闭标准化。每折独立预处理；自动成分采用最小平均标准化 PRESS，而非声称逐项复制官方自动选择结果。 |
| PLS 验证方式 | 官方可留一、留组或按列指定组别。[Cross-validation in PLS](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/regression/supporting-topics/partial-least-squares-regression/cross-validation-in-pls-regression/) | 确定性的连续 K-fold 或 LOO；本次不提供用户组别列、随机重复 CV 或嵌套 CV。外部工作表用于独立留出预测，有对应 Y 时评估误差。 |

## 统计约定

### 共同数据与结果契约

- 打开窗口时复制来源工作表，模型、报告和训练图形绑定该来源；切换当前工作表不重绑。源行号为快照中从 1 开始的位置，与 DataFrame 索引标签分开；预测行号属于预测表。
- 缺失默认报错；用户显式选择删除时，对本模型所需列联合删除并记录数量，不插值、不填补、不补零。非有限值、缺列、无效参数、未知类别、不可识别和未收敛明确报错。保留用户数据和上次有效模型。
- 新模型不接受权重或变量筛选，PLS 另不接受分类 X 或模型项展开；不可静默忽略设置。分类预测量使用固定训练水平，遇到未见水平报错。
- 后台拟合/预测，取消后丢弃迟到结果；底层单步求解器可能返回后才响应取消。结果页可导出 CSV/Excel、写入新工作表及输出完整报告；不覆盖原数据。
- AIC = −2ℓ + 2k，BIC = −2ℓ + k log n；本次计数/分类模型 k 为实际估计参数数。仅比较同响应、同有效样本及可比似然的模型。PLS 不输出似然型 AIC/BIC。

### Poisson

`Y|X ~ Poisson(μ)`，`g(μ)=Xβ`，条件方差等于均值；Y 为非负整数且至少存在一个正计数。全零或零计数分离可能无有限极大似然估计，不能作为正常收敛报告。

| 链接 | 定义 | 域约束与解释 |
| --- | --- | --- |
| log | η = log μ，μ = exp η | μ 必须有限且严格为正；exp β 为条件均值倍数。 |
| sqrt | η = √μ，μ = η² | η 必须严格为正，负 η 不能通过平方伪装成有效链接。 |
| identity | η = μ | η 必须严格为正；β 为条件均值尺度效应。 |

系数检验 `H0: βj=0`，双侧 Wald `z=βj/SEj`，区间 `βj ± z(1−α/2)SEj`，均为渐近推断。均值区间由线性预测量区间反变换；sqrt/identity 先将 `η ± z(1−α/2)SE(η)` 与 `[0,∞)` 取交集，再分别平方或作恒等变换。区间下界允许为 0，表示均值区间的闭包边界；拟合与预测点本身的 η 仍必须严格为正。报告 notes 显式说明此交集及边界约定。固定 μ̂ 的 Poisson 条件分位数 `conditional_lower/upper` 不包含参数估计不确定性，不能标为完整的新观测预测区间。

偏差 `D=2Σ[y log(y/μ̂)−(y−μ̂)]`，约定 `0 log 0=0`；Pearson `X²=Σ(y−μ̂)²/μ̂`；`df=n−rank(X)`。拟合优度以正确指定的 Poisson 均值/方差模型为原假设，用 `χ²(df)` 上尾近似，稀疏计数和小均值下应谨慎。离散度估计 `X²/df`；超过 1.5 或 Pearson p 小于 α 时提示失配/过度离散，不自动估计负二项模型或改变标准误。诊断采用 Pearson、偏差残差及适用的 GLM 影响量。

### 名义多分类 Logistic

至少 3 类，参考类别 r 的参数固定为零，其余 `ηk=Xβk`；`pk=exp(ηk)/Σ exp(ηh)`（含 ηr=0）。报告保存所有类别的固定编码，输出 K−1 组系数、概率、混淆矩阵、似然比检验、McFadden 伪 R²、准确率、对数损失和多类 Brier 分数。系数 z/Wald 区间为渐近结果，不能把 exp β 解释为概率比。

`log loss=−Σ log(p实际类别)/n`；预测取最大概率类别，并列按固定编码顺序。混淆矩阵行是实际类别、列义为预测类别；训练矩阵只是描述。似然比检验 `H0: 全部斜率为零`，相对同类别集合的仅截距模型，χ²上尾近似。概率须有限、在 [0,1] 内且每行和为 1；不使用类别编号作 OLS 残差，不把二元 0.5 阈值或 ROC 直接扩展为多类别模型。

### 有序 Logistic / probit

类别从低到高显式排序，至少 3 类；重复、遗漏、额外类别或错误顺序均拒绝。采用 `P(Y≤k)=F(ck−Xβ)`，实际切点严格递增，分类概率为相邻累积概率之差；边界累积概率为 0、1。每行校验概率范围/行和及累积概率单调。

logit 下 `logit P(Y≤k)=ck−Xβ`，共享 β 为比例优势假设；`exp(−β)` 才是本符号约定下较低类别累积优势的倍数。Minitab 官方公式采用 `θk+Xβ`，跨软件比较需对齐类别顺序、累积事件及斜率符号。probit 使用标准正态 F，共享斜率不解释为优势比。

statsmodels 的内部阈值变换参数必须还原成实际切点；切点协方差通过变换 Jacobian 的 delta 方法获得，不能直接套内部参数的 SE。拟合评估以似然比、对数损失、概率和分类诊断为主。**没有执行比例优势假设检验**；收敛、显著性、概率合法均不验证该假设。

### PLS

数值 X，单 Y 或多 Y；NIPALS，中心化始终开启。标准化采用各训练样本的样本标准差（ddof=1），同时作用于 X/Y；预测使用训练均值、尺度，系数/预测还原为原始单位，scores/loadings 为建模尺度。可处理 p>n 和高度共线；成分数受中心化 X 的有效秩及训练折可提取成分数限制，常量列、无效数据及固定成分超限报错。

CV `cv=2..n` 按输入顺序连续分折，`cv=n` 为 LOO；`cv=0` 必须固定成分。每折独立拟合预处理与 NIPALS；训练响应为常量或样本不足以定义尺度时拒绝。候选成分必须在全训练集及每折均可提取。

对成分数 a，原始单位 `PRESSj(a)=Σi[yij−ŷ(−fold(i),a)ij]²`；`RMSECVj=√(PRESSj/n)`。自动选成分的分数为：

`score(a) = (1/(n m)) Σi Σj [(yij−ŷ(−fold(i),a)ij) / sY(−fold(i),j)]²`

其中 m 为响应数，分母是对应训练折的 Y 样本标准差，即使关闭建模标准化也按此计算 CV 分数；最小分数选成分，精确并列取较少成分。该规则防止大尺度响应支配，但与 Minitab 文档描述的平均 PRESS/预测 R²准则不保证等价。不进行 CV 时无 PRESS/选成分误差曲线；训练 RMSE 不是 PRESS。

输出 X/Y scores/loadings、原单位系数、X/Y 解释方差、VIP、训练/CV 预测及误差曲线。VIP 按建模尺度上多响应合计的解释平方和加权；VIP>1 不代表显著。无 PLS 系数 CI、p 值、VIP 显著性、OLS 自由度推断或新观测预测区间。使用同一 CV 选参并报告最小 CV 误差可能乐观。

外部预测表只需训练要求的 X；若带对应响应 Y，才计算误差，不能把训练 Y 与外部行按位置拼接。留出表须未参与训练/选参才可称独立留出验证。缺失按用户策略处理，无自动填补。连续分折不等于时序外推或按主体分组验证。

## 生产入口到独立参考的证据表

全部模型均从 `RegressionDialog.fit → advanced_regression.fit_regression` 进入。计算模块只返回原始精度 DataFrame，由既有 StatTable、SheetApp 和绘图窗口展示。以下参考不调用生产拟合函数建立期望值。

| 方法 / 生产入口 | 独立参考测试节点 | 参考来源或推导 | 已覆盖边界 | 实际结果 |
| --- | --- | --- | --- | --- |
| Poisson / `generalized_regression.fit_generalized` | `test_generalized_regression.py::test_poisson_group_rates_independent_mle_and_information`、`test_poisson_model_terms_against_independent_likelihood` | 三链接分组解析 MLE；独立 Fisher 信息、SE、均值 CI、似然、D/Pearson/AIC/BIC；多项式/分类交互的独立 SciPy 似然优化 | 非整数/负数/无穷、零计数分离、链接预测域、过度离散；固定训练编码 | 通过；计入该文件 9 项 |
| 名义多分类 / 同上 | `test_generalized_regression.py::test_nominal_group_probabilities_coefficients_and_reordered_prediction` | 分类组频率与 K−1 组相对参考系数的解析解；独立似然与概率公式 | 显式参考类别、类别概率和、混淆频数、重排行、未见因子、完全/准分离、NA、权重/筛选拒绝 | 通过；共同边界另见 `test_missing_order_separation_and_invalid_options` |
| 有序 logit/probit / 同上 | `test_generalized_regression.py::test_ordinal_against_independent_cumulative_likelihood` | 独立 Nelder-Mead 累积类别似然最大化；两种分布的合成数据，直接比较实际切点、斜率、对数似然和预测 | 顺序缺失/重复/遗漏/额外类别、实际切点、概率行和/单调性、有序分离、秩亏和取消 | 通过；不把此结果解释为比例优势假设已验证 |
| PLS / `pls_regression.fit_pls` | `test_pls_regression.py::test_one_component_covariance_svd_reference`、`test_full_rank_pls_matches_independent_ols`、`test_cv_manual_fold_reference_and_leakage_counterexample` | 一成分协方差 SVD、足成分独立 OLS、多 Y 已知线性映射；手工逐折协方差闭式预测、PRESS 与错误全局预处理反例 | 单/多 Y、中心化/标准化、p>n、秩限制、超量成分、NA/常量、折内处理、LOO、自动选择、留出 RMSEP、取消；正交多 Y 初始化反例 | `tests/test_pls_regression.py` 48 项通过 |
| GUI / `RegressionDialog` | `test_regression_dialog.py::test_extended_models_real_sheet_workflow`、`test_cancel_discards_late_result_and_preserves_last_model`、`test_parameter_pages_keep_actions_visible_at_minimum_size` | 真实 Tk 应用工作表；拟合、外部表预测、报告、CSV/Excel 导出对照、写入新表；按窗口句柄截图 | 4 新模型、旧模型、来源切换/删除/修改、取消迟到结果保留旧模型、880×620 关键动作可见 | GUI 与菜单合计 74 项通过；实际查看 PLS、有序窗口截图 |
| 图形 / `regression_plots.regression_plot` | `test_regression_plots.py::test_multicategory_probability_and_confusion_plots`、`test_poisson_plot_uses_deviance_residuals`、`test_pls_multiresponse_plots_render_with_separate_response_labels` | 绘制已拟合结果，不重拟合；对照概率曲线条数、分类矩阵合计、Poisson 残差及多 Y 分组 | 旧图形、拾取来源行、多类不适用图拒绝、PLS 得分/载荷/VIP/CV/预测 | 当前该文件 23 项通过 |

参考中的系数零假设为双侧 H0: β=0；模型 LR 为全斜率零假设、χ²上尾近似；PLS 的假设检验不适用。Poisson 三链接 SE 参考是 Fisher 信息；有序阈值区间采用 delta 近似，未用 Minitab 软件独立复算。

## 实际验证记录

解释器为项目 `.venv\Scripts\python.exe`，Python 3.11.9；已确认 NumPy 2.4.6、pandas 3.0.6、SciPy 1.15.3、statsmodels 0.15.0。未使用 Codex bundled runtime，未新增运行依赖。

下列命令均在仓库根目录通过 PowerShell 执行。前两项有交集，不直接把数量相加。

| 实际命令（前缀均为 `& .venv\Scripts\python.exe`） | 结果 |
| --- | --- |
| `-m pytest tests/test_generalized_regression.py tests/test_advanced_regression.py -q` | 101 passed（当时新增模型 8 + 原有回归 93） |
| `-m pytest tests/test_pls_regression.py tests/test_generalized_regression.py tests/test_regression_plots.py -q` | 70 passed（随后继续补充了 1 个模型项参考和 9 个 PLS 绘图用例） |
| `-m pytest tests/test_generalized_regression.py tests/test_regression_plots.py -q` | 最终 32 passed（新增广义模型 9 + 图形 23）；4 条 sqrt/identity DomainWarning 为非典范链接域警告，拟合和预测仍显式检查实际定义域 |
| `-m pytest tests/test_regression_dialog.py tests/test_menu_localization.py -q --basetemp "$env:TEMP\minijmp-regression-gui-20261023"` | 74 passed（GUI 16 + 菜单 58） |
| `-m pytest tests/test_g12_inventory.py tests/test_help_center.py tests/test_sheet_context.py tests/test_g3_regression_reports.py tests/test_windows_packaging.py -q` | 66 passed；5 条既有极端数据/旧绘图警告，无失败或跳过 |
| `tools/build_help_index.py` | 成功生成离线搜索索引，帮助一致性检查通过 |
| `git diff --check` | 通过 |

按测试文件去重覆盖 313 项：原有回归 93、新增广义回归 9、PLS 48、图形 23、GUI/菜单 74、其余关联检查 66。上表记录的是分批运行结果，没有声称一次性运行了全项目测试。

截图由 `ImageGrab.grab(window=dialog.main.winfo_id())` 从真实 Tk 窗口生成，位于系统临时目录 `minijmp-regression-gui-20261023/test_extended_models_real_shee0..3/`。已打开查看 PLS 与有序模型截图，确认是目标窗口；另以控件几何测试检查最小尺寸。未执行多显示器/DPI 全组合验收。

## 实际修改文件

- 计算：`code/advanced_regression.py`、新增 `code/generalized_regression.py`、新增 `code/pls_regression.py`。
- 界面与图形：`code/MiniJMP.py`、`code/regression_dialog.py`、`code/regression_plots.py`。
- 文档与帮助：`docs/MENU_TRANSLATION.md`、`docs/REGRESSION_EXTENSIONS.md`、`help/pages/advanced-regression.html`、生成的 `help/assets/search-index.js`。
- 验证：新增 `tests/test_generalized_regression.py`、新增 `tests/test_pls_regression.py`、`tests/test_regression_dialog.py`、`tests/test_regression_plots.py`、`tests/test_menu_localization.py`、`tests/fixtures/g12_table_inventory.json`。

## 复杂度复核与剩余限制

按 no-stop-gpt Audit 复核实际 diff：保留原工作表/线程取消/报告/图窗架构，旧回归只增加路由，新增两个纯计算模块；没有额外依赖、缓存、通用框架或兼容层。分类编码复用既有 `_Design`；线性规划分离检查保护有限 MLE，PLS 折内预处理保护 CV，均对应实际边界测试。PLS 多响应初始化遍历各非零协方差方向有独立正交反例支持，不能当成无依据的 fallback 删除。PLS 多 Y 图形分组显示，不混画正态 QQ。

新模型不支持权重/变量筛选；PLS 只接受数值 X；有序只支持 logit/probit，无比例优势假设检验。Poisson 非典范链接协方差、PLS 自动选成分等与 Minitab 的差异见前文。新数据类别概率区间、PLS 参数推断和完整观测预测区间不在本次实现中。

Windows 打包相关静态/资源/冻结入口测试通过，新增模块均由显式 import 可达，无新增运行依赖；**完整 PyInstaller 发布构建未执行**。**未运行全项目测试或 Minitab 桌面软件逐值复算**。本次不提交、不推送、不启动过程能力和质量工具阶段；后续阶段应另行开展。
