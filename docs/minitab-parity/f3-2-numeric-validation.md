# F3-2 全功能数值验证与统计准确性验收

## 当前状态：F3-2A、F3-2B、F3-2C 完成；F3-2D 至 F3-2G 进行中

本报告按 F3-2A 至 F3-2G 的工作包持续更新。阶段结束条件是所有适用的数值功能均有证据状态、确定缺陷已修复并验收、方法差异和原生证据缺口已说明。当前结论仅对应已完成的工作包，不代表全产品数值验收完成。

## 基线与口径

| 项目 | 基线 |
|---|---|
| Git | `main`，HEAD `e9e836d`（F3-1A A7）；开始时工作区干净，未推送 |
| F3-2B 续接 | 从 F3-2A 提交 `6cc4bff` 续接；开始时保留 6 个生产文件和 7 个测试文件的未提交改动；未重做 F3-2A |
| Python | 项目 `.venv`，Python 3.11.9 x64 |
| 数值依赖 | NumPy 2.4.6；SciPy 1.15.3；pandas 3.0.6；statsmodels 0.15.0 |
| 历史原生对标 | Minitab 19.1.0.1，路径 `D:\Program\Minitab 19\Mtb.exe`；逐案例版本沿用矩阵原记录 |
| 当前 Minitab 22 | `C:\Program Files\Minitab\Minitab 22\Mtb.exe`，文件版本 `22.3.0.0`，产品版本 `22.3.0.0.c154fe3f-20250506.2`；COM 已注册但当前用户未登录，无法执行命令 |
| 已归档 Minitab 22 证据 | 个别历史固定案例来自 22.6；继续保留各自实际版本，不改标为 22.3 |
| 覆盖总表 | `docs/minitab-parity/coverage-matrix.csv` 208 行 |
| DOE 专项总表 | `docs/doe-minitab/feature-matrix.csv` 80 个唯一 DOE 功能 ID |

新增数值验证矩阵为 `docs/minitab-parity/numeric-validation-matrix.csv`。它按功能 ID 合并综合覆盖矩阵和 DOE 专项矩阵：共 167 个唯一 ID，其中 165 个属于现有有效功能记录，另 2 个是明确排除的 DOE 范围并标为“不适用”。80 个 DOE 专项 ID 均映射一次；综合表中的 36 个 DOE 交叉引用和 5 个功能别名不另建数值记录。其余两条产品范围排除也保留为“不适用”。

矩阵中 142 条功能记录适用数值验收，25 条标为“不适用”。这是功能记录数，不是算法总数；同一功能包含的统计子方法、关键输出字段和已知限制列在对应记录中。将纯界面、文件/工作表操作和未实现功能标成“不适用”，不将它们计入统计正确性通过率。

矩阵分开记录独立数学参考和 Minitab 原生数值状态。标记“独立数学参考已通过”只适用于相应专项证据明确覆盖的支持范围；现有测试路径本身不自动视为独立 oracle。Minitab 原生通过也仅限指定版本、输入及字段，不外推为全选项一致。

### Minitab 22.3 当前可用性核验（2026-11-26）

- 目标程序存在，`Mtb.Application` CLSID `{6265486C-4A08-4B4E-9713-C2CD85F1F515}` 的 `LocalServer32` 指向上述 Minitab 22 路径。独立 COM `DispatchEx` 返回 `Version=22.3`、`AppPath=C:\Program Files\Minitab\Minitab 22\Mtb.exe`。
- GUI 显示“需要身份验证 / 您已注销”。调用 `app.New()` 返回 `IApplication: 未授权在此机器上运行 COM 库`。因此当前许可证未能在本用户会话中验证，独立空白工程及统计命令也未能通过；窗口后方显示的空白工作表不作为工程可用证据。
- 本轮没有在 Minitab 22.3 执行统计命令或生成新原生数值。按独立数学参考继续验收；矩阵中的 Minitab 19 与已归档 22.6 证据均保留原版本标识。

## F3-2A：数值验证矩阵与证据缺口

### 已复用的证据入口

- F3-1A 非参数检验、等效性检验、双样本离散度检验及独立子组控制图：`docs/minitab-parity/f3-1a-validation.md`。
- F2 基础检验、功效、泊松率、GLM、SPC、能力和时间序列固定案例：`docs/minitab-parity/coverage-summary.md`。
- 过程能力独立数学参考、二项/泊松精确区间和 Minitab 19/22 存储值：`docs/capability-validation.md`、`docs/capability-analysis.md`。
- DOE 专项设计和分析参考：`docs/doe-minitab/acceptance.md`、各专项 reference-validation 文档、`tests/fixtures/doe_*_reference/` 及对应测试。
- Minitab 19.1.0.1 的阶段 3–8 原始比较仍位于 `Out/statistics_minitab19_parity/`；DOE G05–G08 的补验在 `docs/doe-minitab/phase3-g05-g08-parity.md`。

### F3-2A 矩阵初始状态

| 口径 | 条目数 |
|---|---:|
| 唯一功能 ID（含 2 条显式范围排除） | 167 |
| 适用数值验收的功能记录 | 142 |
| 不适用数值验收 | 25 |
| DOE 专项 ID，均已映射 | 80 |
| 独立参考状态：已通过 | 39 |
| 独立参考状态：部分验证 | 38 |
| 独立参考状态：尚未验证 | 64 |
| 独立参考状态：统计方法不同但正确 | 1 |
| 原生状态：固定范围已通过 | 3 |
| 原生状态：部分验证 | 40 |
| 原生状态：统计方法不同但正确 | 3 |
| 原生状态：证据不足 | 96 |

状态类别允许重叠解释差异，但每项功能只按唯一 ID 计一次。上表是 F3-2A 建表时的状态快照；后续工作包核实并更新矩阵，不能将这些数简单相加为独立功能总数。

### 按优先级排列的证据缺口

1. **P0——先确认可能改变用户结论的输入与工业统计边界。** 基础统计核查发现数值清洗可能把正负无穷当作有效值，以及单样本 t/Z 汇总输入可能接受非整数样本量；当前尚未复现其下游结果，不能先记为已确认缺陷。过程能力、SPC、MSA 的历史证据覆盖固定案例，仍须逐字段区分组内/整体变差、能力区间、报警点和估计方法。
2. **P1——补齐关键模型与推断字段。** 正交回归的区间端点、名义/有序 Logistic 的厂商数值字段、单样本 Z 与 TOST、功效的多个检验类型、分布拟合的参数区间和原生拟合优度字段尚无完整证据。
3. **P1——复核有已知算法口径差异的 SPC/MSA。** 交叉 GRR 平均极差常数的精度、Nelson 规则报警行和属性控制图重叠窗口的标记规则已有可复现差异；先确认各自方法定义及实际影响，不预先归类为计算错误。
4. **P1——DOE 设计等价性和模型可估性。** 复用 DSD、BBD、裂区、筛选、混料、最优设计、Taguchi 与功效参考。已有 DSD 固定编码点集差异及一个混合 DSD 二阶秩差异应保留到具体配置，不据此外推全设计族。
5. **P2——图形派生数值。** 仅核对直方图分箱、箱线图分位数、概率图位置、区间/边际图及经验分布等直接派生统计值；纯图形布局和绘制行为不进入本矩阵。

以上为证据优先级，不是缺陷严重度结论。尚未复现或尚无独立参考的项目保持未验证状态。

## 缺陷与差异清单

| 编号 | 功能 ID | 复现与正确参考 | 修复 | 验证 |
|---|---|---|---|---|
| F3-2B-DEF-001 | F0-BASE-001、003、006；共享清洗调用方 | `X=[1,+∞,-∞,2]` 旧清洗保留无穷；描述统计得到无效均值。有限实数观测的参考为 `[1,2]`，`N=2`、均值 `1.5`。配对输入按同一行成对保留；多变量输入只保留所有选列均有限的完整行。 | `is_number`、`number_list`、`number_2lists`、`number_2Dlist` 统一排除非有限值，保留配对及完整行对应关系。 | `test_g17_data_processing.py`、`test_statistics_regressions.py`、`test_g2_basic_reports.py`；共享调用方回归见后续包记录。 |
| F3-2B-DEF-002 | F0-BASE-018、019 | 汇总输入 `N=2.5` 先前可进入 t/Z 计算并产生非整数自由度。样本量是计数，t 要求整数 `N≥2`，Z 要求整数 `N≥1`。 | 对话框与统计函数都拒绝非有限或非整数汇总样本量，并验证均值、标准差、假设值和 α。 | `test_g2_hypothesis_reports.py`、`test_statistics_regressions.py`。 |
| F3-2B-DEF-003 | F0-BASE-018–025、029–030；F0-NEW-024 | 多个双侧/右尾 p 值用 `1-CDF`：Z=10 的正确 p 为 `1.5239706e-23`，旧值为 0；χ²=200、df=31 的 p 为 `1.2969168e-26`，旧值为 0；760/1000 对 0.5 的正态近似 p 为 `9.2839166e-61`，旧值为 0；32 个点的 Bonett 比值案例 p 为 `3.4778628e-82`，旧值为 0。t、χ²、F 与比例例由不完全 Beta/Gamma 函数或 `erfc` 独立核对。 | 右尾计算改用分布 `sf`；Bonett 正态尾与双侧检验统一用稳定尾函数。结构化结果仍保存未格式化概率，显示列保留三位小数语义。 | `test_g2_hypothesis_reports.py`、`test_g3_chi_square_reports.py`、`test_review_proportions.py`、`test_variance_ratio.py`。极端 t 报告还核对 `StatTable.values` 与原始 p 值一致，显示 `0.000` 仅为舍入。 |
| F3-2B-DEF-004 | F0-BASE-003、005 | 常数样本 `[5,5,5,5,5,5]` 使 Shapiro–Wilk 返回带零范围警告的占位值 `(W=1,p=1)`，Anderson–Darling 统计量为 NaN 而依赖库返回 `p=0`。零方差下两项检验均不可计算。 | 常数样本的两种检验统计量与 p 值都返回 NaN；报告用 `*` 标示并说明样本无变异。非有限 Anderson–Darling 统计量也不再保留伪 p 值。 | `test_g2_basic_reports.py::test_constant_sample_normality_tests_are_unavailable`；`test_g3_distribution_reports.py`、`test_g3_regression_reports.py`。 |

F3-2B 这些修复不改变合理的方法差异。单侧/双侧定义、离散检验排序与区间、非参数并列约定、Bonett 近似及功效算法仍按矩阵和历史参考保留各自边界。

## F3-2B：基础统计与推断（已完成）

本包核对矩阵中 23 条功能记录：`F0-BASE-001、003–006、018–025、029–030` 及 `F0-NEW-007–009、020–021、024–026`。其余能力状态保持逐字段判定；“部分验证”或“原生证据不足”表示相关输出/选项仍有明确缺口，不代表整项通过。矩阵中单、双因子 ANOVA 已按本报告原定的 C 包范围从 F3-2B 移到 F3-2C（`F0-BASE-026/027`）。

### 核对范围与数学参考

- 描述统计、置信区间、分布拟合、相关、t/Z、方差、比例、列联表/比率卡方、Poisson 率、功效与样本量：复用对应的 SciPy 闭式分布、正则不完全 Beta/Gamma 函数、独立频数/均值计算及现有 `test_review_*` 参考；不把历史实现当作唯一正确 oracle。
- 配对 t 与多列完整案例按输入行号保留观测对应；非参数方法的精确/渐近 p、并列秩、区间与游程差异沿用 F3-1A 已核证的定义。
- Calculator、随机数据和分布概率列按现有固定表达式、NumPy/SciPy 参考及端点测试核对；随机数流与 Minitab 不要求逐值一致。
- 单样本 Z、三种 TOST、多种功效选项、分布拟合区间/信息准则以及部分厂商校准仍保持矩阵中的部分/缺证状态，不据此扩写为全选项一致。

### 实际验证

- 项目解释器为 `.venv\\Scripts\\python.exe`，Python 3.11.9；NumPy 2.4.6、SciPy 1.15.3、pandas 3.0.6、statsmodels 0.15.0。
- 首轮 17 个定向测试文件共 **752 passed、12 failed**。其中 6 项是 χ² 旧浮点快照对 `CDF` 与 `sf` 等价实现使用精确相等；将该快照改为相对 `1e-12`、绝对 `1e-14` 比较，`value=0` 仍要求精确为零。独立 `gammaincc` 极端尾参考继续约束精度。
- G3 计算结构冻结中，因本包改动尾概率而更新的仅是 `chi_square`、`chi2_test_stdev`、`chi2_var_1sample`、`var_1sample` 四个函数的哈希；对应正确性由独立数学断言接管。四个受影响冻结用例复验 **4 passed**，其他函数冻结不变。
- 首轮另有 1 项 G15 字符串搜索用例失败（本轮未改的 `ß`/`SS` 大小写展开行为）、1 项直方图 UI 用例因 Tcl `init.tcl` 不在当前 Python 安装路径失败，以及 4 项 `test_g16_statistics.py::test_f06_all_fits_and_model_selection` 与较早 `source_baselines` 输出不一致。`code/dist_fit.py` 未在本包修改；当前分布拟合独立公式/参数/报告测试通过。旧源代码比较不是独立数学 oracle，这 4 项仍列为未裁定的历史比较差异，不据此认定统计缺陷。
- χ² 固定输出与分布拟合复核：`test_g3_chi_square_reports.py::test_fixed_before_values_types_keys_and_print_switch` + `test_g3_distribution_reports.py`，**45 passed**。
- 常数样本修复及共享正态性调用路径复核：`test_g2_basic_reports.py`、`test_g3_distribution_reports.py`、`test_g3_regression_reports.py`、`test_g16_statistics.py::test_f01_numerical_and_report`，**136 passed**。

Minitab 22.3 未能执行命令，故本包没有新增 22 原生案例。Minitab 19.1.0.1 的既有固定值和 22.6 已归档案例保留原版本，不改作当前实测结果。

## F3-2C：回归、ANOVA、GLM 与 PCA（已完成）

本包核对矩阵中的 11 条记录：`F0-BASE-007/008/011–016/026/027` 与 `F0-NEW-027`。矩阵原生/独立状态保留逐字段结论；缺少的厂商数值证据不以不同库的相同实现代替。

### 独立参考及结果

- **正交与线性回归**：线性回归用独立设计矩阵、闭式最小二乘、协方差矩阵、残差和逐行删除重拟合核对系数推断及 PRESS。正交回归用测量误差加权协方差主方向核对斜率/截距，并以固定真值、独立正态 X/Y 测量误差的生成模型作 3,000 次覆盖仿真（`n=100`、误差方差比 1.5）：斜率和截距 95% 区间覆盖率分别为 95.17% 与 94.90%，区间平均标准误与重复拟合的经验标准差相符。该模拟核对推断近似，不替代 Minitab 同口径原生案例。[Minitab 正交回归方法与近似协方差定义](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/regression/how-to/orthogonal-regression/methods-and-formulas/methods-and-formulas/)
- **OLS/WLS、二元 Logistic、非线性与预测**：用显式矩阵、闭式系数/协方差、独立似然与梯度/ Hessian，及新数据预测和逐点残差核对。已归档的 Minitab 19 phase4/5 结果继续按各自输入和输出字段保留。
- **Poisson、名义/有序 Logistic**：Poisson 用独立 Poisson 对数似然优化与 Fisher 信息复算系数、协方差、偏差、预测；名义模型按指定参考类别直接构造类别概率与似然；有序模型独立优化累积链接似然并复核阈值、斜率和类别概率。非典范 Poisson 链接使用的协方差近似与厂商定义不同；名义基准类别及有序阈值/斜率符号按显式类别顺序解读。均未取得 Minitab 同口径的新原生字段。
- **PLS 与 PCA**：PLS 用 SVD/协方差方向、满秩 OLS 及手工逐折预处理/预测复核 NIPALS 输出、系数与 PRESS/RMSECV；自动成分按本地最小平均标准化 PRESS 规则，不能外推为厂商选择规则。PCA 用独立 `eigh`、投影矩阵、重构和 Hotelling 统计量核对特征值、解释率、载荷/得分及监控输出；等价解按特征向量符号对齐。Minitab 19 phase7/8 固定记录沿用各自字段范围。
- **单/双因子 ANOVA 与固定效应 GLM**：ANOVA 用受限和对比矩阵分别拟合完整/约束模型并以 SS 差核对 Type III、模型秩和可估性；GLM 用独立公式模型/III 型 ANOVA 核对系数、SS、df、预测与 PRESS。历史 Minitab 19 GLM 固定案例的两项 Adj SS、残差 df、预测 R²及七个拟合值继续保留；首水平参考编码与厂商效果编码在含交互项的低阶检验上属于参数化差异。

### 定向验证与遗留差异

- 定向命令覆盖 11 个回归/模型测试文件，合计 **556 passed、8 failed**：

  ```powershell
  & $python -m pytest tests/test_statistics_regressions.py tests/test_advanced_regression.py tests/test_generalized_regression.py tests/test_pls_regression.py tests/test_pca_analysis.py tests/test_pca_plots.py tests/test_g3_anova_reports.py tests/test_review003_anova.py tests/test_regression_dialog.py tests/test_phase3_prediction_statistics.py tests/test_g3_computation_contracts.py -q
  ```
- 其中 4 项是 F3-2B 尾概率改动影响的 `chi_sq.py` G3 源结构哈希。仅更新对应四个函数的冻结哈希；独立数学用例已由 F3-2B 的 Beta/Gamma/正态尾部断言接管。四项单独复验 **4 passed**。另 4 项是 `dist_fit.py` 的旧 G3 源结构哈希；该生产文件本轮未改，独立分布拟合测试 `test_g3_distribution_reports.py` 已通过。冻结差异保留，不刷新未授权的分布拟合基线。
- 本包未发现需修改生产统计代码的新缺陷。正交区间的模拟覆盖是大样本近似核验；Minitab 22.3 当前登录受阻，未取得正交、名义/有序 Logistic、PLS 等新原生数值。历史 Minitab 19/22.6 案例不改版本标签。

## F3-2D：过程能力、SPC、MSA 与质量工具（已完成）

本包核对 26 条矩阵记录：`F0-BASE-031/032/034–037/040–055` 与 `F0-NEW-028–031`。同步修正四条质量工具记录的独立参考状态，并把 `F0-BASE-051` 的历史 Nelson 原生值从“无直接案例”更正为 phase7 `TRESULTS` 部分验证。

### 数值参考对账与差异

- **过程能力**：复核正态指数、组内/整体变差、区间、PPM、非正态 MLE、变换、Sixpack 与属性能力精确区间。Minitab 19 CAP-01–05 共 41 个比较字段中 28 个匹配、13 个为方法差异：CAP-01 4/7、CAP-02 6/6、CAP-03 2/4、CAP-04 4/12、CAP-05 12/12。主要差异为正态能力 `d2(2)` 精度（精确值与 Minitab 表值 1.128）及 CAP-04 Lognormal 的 `n`/`n−1` 标准差估计；不归类为实现缺陷。已归档的 Minitab 22.6 `BCAPA` 和 Minitab 19.1 `PCAPA` 均保留其真实版本与字段范围。Box-Cox/Johnson 的变换、似然与域边界，以及 Sixpack 的正态常数/非正态 PPF 有独立公式测试；完整厂商变换和 Sixpack 数值字段仍缺。
- **SPC**：独立参考核对 I/MR/Xbar-R/S、属性图、EWMA/CUSUM、Nelson 和 T² 的控制限或递推定义。Minitab 19 基础图固定案例 846 个字段通过，Xbar-R 变组量另有 8 个字段通过；NP/P/C/U 边界和主控制限有对应固定比较。重叠窗口规则中属性图 Test 3/4 的 8 个标记字段与原生不同，属于首次触发点/重叠标记约定差异。Nelson `TRESULTS` 规则 1、2、5–8 与历史值一致；规则 3/4 本地在第 6/14 点标记，Minitab 19.1 从下一行第 7/15 点标记。保留这两个明示的单行差异，不延迟本地报警。EWMA/CUSUM/T² 和若干报警规则无新增原生字段。
- **MSA**：属性一致性用手工列联表、二项尾概率反演、Fleiss 评分枚举与 Friedman/Kendall 公式独立核对；交叉 GRR Minitab 19 ANOVA 固定案例 22/22 字段通过，嵌套 GRR 5/5 通过。交叉平均极差法另有 5 个 `d2` 精度字段差异。Type 1、线性与偏倚的 Cg/Cgk、t/OLS 和区间独立参考通过；Minitab 19 `TOGAGE`/`LNGAGE` 仅留下图，COM 文本没有可读数值，原生统计字段仍缺。
- **关联质量工具**：Pareto 计数/累计率/阈值与合并边界、运行图游程及正态近似、Multi-Vari 组合均值/标准差/范围/缺失组合、属性一致性各方法已有具名独立参考测试。原矩阵把这些存在的参考标为“尚未验证”，现已按 `docs/quality-tools-extension.md` 和相应测试改为“独立数学参考已通过”；没有匹配的 Minitab 原生值仍标证据不足。容差区间用 Beta 覆盖率验证；本地最大对称可用秩与 Minitab 可用的非对称秩不同，已按实际覆盖率判定为方法不同但正确。

### 定向验证与限制

- 运行能力、SPC、MSA、质量工具的 14 个定向测试文件：**670 passed、2 failed、8 deselected**。命令使用 `-k 'not computation_plotting_ast_matches_frozen_structure'`，排除的是项目已有的 8 项 G5 AST 冻结差异；对应既有基线核对见 `docs/capability-validation.md`。
- 两项剩余失败均为与本包数值无关的 G4 历史结构比较：`test_shared_modules_and_plot_implementations_remain_at_baseline` 的 Pearson 结构哈希在 F3-2A 基线 `6cc4bff` 与当前均为 `8bf03a0c…`，旧 G4 fixture 仍要求 `c54f6fd4…`；`test_quality_dialog_changes_are_only_output_statements` 将当前 Type1GageDialog 与旧 G4 对话框文件结构比较，而该文件在 F3-2A 基线至今未改。本轮保留这两条未裁定的历史测试差异，不改统计输出或重写旧基线。
- 本包未确认需要修复的新生产计算缺陷。Minitab 22.3 登录受阻，未执行新原生案例；所有 Minitab 19/22.6 字段仍只在各自历史输入范围内成立。

## 工作包状态

| 工作包 | 范围 | 状态 | 本阶段结果 |
|---|---|---|---|
| F3-2A | 功能 ID 映射、数值适用性、已有证据和缺口排序 | 已完成 | 165 条有效功能记录与 2 条显式排除均唯一映射；142 条适用，25 条不适用 |
| F3-2B | 基础统计与推断 | 已完成 | 23 条矩阵记录已核对；4 项可复现计算/输入缺陷修复；有限值、样本量、尾概率和结构化报告定向回归通过。原生 Minitab 22.3 因当前登录状态不可用 |
| F3-2C | 回归、ANOVA、GLM、PCA | 已完成 | 11 条矩阵记录；闭式矩阵、独立似然、SVD/eigh、受限 ANOVA 和正交区间覆盖核对；保留原生缺证与 4 项旧 `dist_fit.py` 结构哈希差异 |
| F3-2D | 过程能力、SPC、MSA | 已完成 | 26 条矩阵记录已对账；补回历史 Nelson 原生字段及质量工具独立参考；保留 D2 精度、报警行、非对称秩方法差异与 Minitab 22.3 登录限制 |
| F3-2E | 时间序列与预测 | 进行中 | 1 条矩阵记录；复用历史 MA/平滑/Winters/ARIMA 数值，核对初值、区间和模型选择边界 |
| F3-2F | DOE 数值与模型可估性 | 待开始 | — |
| F3-2G | 缺陷闭合及最终验收 | 待开始 | — |

