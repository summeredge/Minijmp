# MiniJMP P1 质量工具扩展

## 实现前输入、输出与测试约定

| 阶段 | 输入 | 输出 | 独立验证与边界 |
| --- | --- | --- | --- |
| Pareto | 原始类别或类别+非负整数频数，可分组 | 降序频数、百分比、累计百分比、Other 末位和双轴图 | 人工计数；同频按首次出现；缺失拒绝；零总数拒绝；超过阈值后合并 |
| Run | 有序连续测量，子组 ID 或连续固定大小，均值/中位数 | 顺序图、中位线、两类运行段和四个单侧 p 值 | 手算和正态分布参考；中位数相等归下侧；相邻相等归向下；小样本提示 |
| 鱼骨 | 问题、类别、原因、子原因；手动及工作表导入 | 层次结构表与鱼骨图 | 结构往返、编辑、长中文、PNG；不作因果证明 |
| Multi-Vari | Y 和有序的 1–4 因子 | 组合 N/均值/SD/极差、分层均值图和原始点 | 人工分组参考；每因子至少两水平、组合覆盖率至少 60%；缺失组合保留空隙 |
| 属性一致性 | Sample/Appraiser/Response/Trial，Standard 可选；有序类别显式顺序 | 四种完全一致率、逐条正确率、CI、适用 Kappa、分类错判和 Kendall | 手工列联表、独立公式/外部库；平衡设计、唯一键、标准一致；退化统计量为 NA 并解释 |

所有分析绑定打开时的来源工作表快照，不修改源表。后台计算可取消，取消后丢弃迟到结果。
表格保留原值精度，可写入新工作表或导出 CSV/Excel；图形沿用现有图窗的缩放、复位、保存。

## 官方参考（2026-10-23 核对）

- [Pareto 输入与 Other 定义](https://support.minitab.com/en-us/minitab/help-and-how-to/quality-and-process-improvement/quality-tools/how-to/pareto-chart/perform-the-analysis/enter-your-data/)
- [Run Chart 公式](https://support.minitab.com/en-us/minitab/help-and-how-to/quality-and-process-improvement/quality-tools/how-to/run-chart/methods-and-formulas/methods-and-formulas/)
- [Multi-Vari 数据要求](https://support.minitab.com/en-us/minitab/help-and-how-to/quality-and-process-improvement/quality-tools/how-to/multi-vari-chart/before-you-start/data-considerations/)
- [属性一致率及 CI](https://support.minitab.com/en-us/minitab/help-and-how-to/quality-and-process-improvement/measurement-system-analysis/how-to/attribute-agreement-analysis/attribute-agreement-analysis/methods-and-formulas/assessment-agreement/)
- [Kappa](https://support.minitab.com/en-us/minitab/help-and-how-to/quality-and-process-improvement/measurement-system-analysis/how-to/attribute-agreement-analysis/attribute-agreement-analysis/methods-and-formulas/kappa-statistics/)
- [Kendall](https://support.minitab.com/en-us/minitab/help-and-how-to/quality-and-process-improvement/measurement-system-analysis/how-to/attribute-agreement-analysis/attribute-agreement-analysis/methods-and-formulas/kendall-s-coefficients/)

## 阶段验证

使用项目 `.venv\Scripts\python.exe`：Python 3.11.9、pandas 3.0.6、SciPy 1.15.3、statsmodels 0.15.0。未使用 Codex bundled runtime，未安装新依赖。

| 门禁 | 实际验证 | 结果 |
| --- | --- | --- |
| Phase 1 | `-m pytest tests/test_quality_tools.py tests/test_quality_tools_dialog.py -q --basetemp=quality-evidence/pareto-verified` | 9 passed |
| Phase 2 | 同两文件，`--basetemp=quality-evidence/phase2` | 12 passed |
| Phase 3 | 同两文件，`--basetemp=quality-evidence/phase3` | 14 passed |
| Phase 4 | 同两文件，`--basetemp=quality-evidence/phase4` | 20 passed |
| Phase 5 | 加入 `tests/test_attribute_agreement.py`，`--basetemp=quality-evidence/phase5` | 32 passed |
| 集成 | 五工具三文件 + `test_menu_localization.py test_help_center.py test_g12_inventory.py` | 最终126 passed，0 failed；另加独立 Kendall 方向验证1 passed |
| 既有回归 | `test_capability.py test_capability_plots.py test_advanced_spc.py test_advanced_spc_plots.py test_advanced_regression.py test_pca_analysis.py test_sheet_context.py test_worksheets.py` | 465 passed，0 failed |

以上路径均位于 `tests/`；命令从仓库根目录运行。最终实际命令如下（592 个不同用例通过；重复复验不累加）：

```powershell
$python = (Resolve-Path '.venv\Scripts\python.exe').Path
& $python -m pytest tests/test_quality_tools.py tests/test_quality_tools_dialog.py tests/test_attribute_agreement.py tests/test_menu_localization.py tests/test_help_center.py tests/test_g12_inventory.py -q --basetemp=docs/quality-tools-evidence/final
# 126 passed in 32.04s；随后新增下述独立方向验证，生产代码未改变
& $python -m pytest tests/test_attribute_agreement.py::test_kendall_tau_asymptotic_direction_against_pair_count_formula -q
# 1 passed in 1.25s
& $python tools/build_help_index.py
& $python -m pytest tests/test_help_center.py tests/test_g12_inventory.py -q
# 27 passed in 3.55s（重复复验，不计入592）
& $python -m pytest tests/test_capability.py tests/test_capability_plots.py tests/test_advanced_spc.py tests/test_advanced_spc_plots.py tests/test_advanced_regression.py tests/test_pca_analysis.py tests/test_sheet_context.py tests/test_worksheets.py -q
# 465 passed in 33.41s
```

开发中曾因临时证据父目录不存在出现2个 setup error，创建目录后修复；菜单翻译清单和帮助主题数量2处旧预期已同步；Fleiss 方差反例1次失败及修正记录见下文。最终上述验证无失败、无跳过。

## 使用与输出

质量菜单末尾依次为 **帕累托图、运行图、因果图、多变异图、属性一致性分析**，原有菜单顺序和分隔保留。具体操作及限制见 [中文帮助](../help/pages/quality-tools.html)。

- Pareto：原始记录仅选类别；汇总数据另选频数列。阈值空白关闭合并，默认 95；累计严格超过阈值后合并其余项。类别数量上限包含 Other。
- Run：原始行序，子组 ID 需连续，固定大小要求完整子组；选择均值或中位数，显著性水平默认 0.05。
- 鱼骨：填写鱼头，选节点编辑名称，新增类别/下级，删除节点及其子树；可按类别/原因/子原因三列导入。修改后重新生成。中文长文本换行，画布随分支及子原因数量增高。
- Multi-Vari：选择 Y 和 1–4 个不同因子，可重排选择顺序；第一因子为横轴，第二为连线颜色，其余分面。竖线给出组合最小/最大值，原始点可关闭。
- 属性一致性：长格式，唯一的 Sample×Appraiser×Trial，Standard 可选且每样本一致；有序类别显式填写完整顺序。置信水平默认 95%。

所有结果使用原值构造 `StatTable`，数值显示不固定截断小数。CSV/Excel 从原精度 DataFrame 导出，而非解析显示字符串。Excel 受其原生双精度精度约束。图窗复用现有保存入口和 `CapabilityToolbar` 导航。

## 逐方法独立正确性证据

| 生产入口 | 独立测试 / 参考 | 样例、边界与结论 |
| --- | --- | --- |
| `quality_tools.pareto_chart` | `test_pareto_counts_threshold_groups_and_order` / 人工计数 | 5,3,1,1 → 50%,80%,90%,100%；阈值恰等于80时保留下一类别再合并；分组、同频、重复类别、零/负/小数/非有限、空值、200类别、内部列名均覆盖 |
| `quality_tools.run_chart` 围绕中位数 | `test_run_counts_order_ties_subgroups`、`test_run_independent_normal_reference_and_patterns`、`test_internal_column_names_and_random_runs_reference` / 手算、SciPy 正态分布、statsmodels 独立 runs test | 手算并列序列为3段；单调40点为2段、交替40点为40段；不排序、不丢中位并列点；随机排列 Z 与外部库在相同定义下相同 |
| 同上，上下运行 | 手算和解析 E=(2N−1)/3、Var=(16N−29)/90，正态 CDF/SF | 并列序列4段；单调为1段、严格交替39段；并列归向下，但含相等值不报告连续分布假设下 p；N<10 不报告近似 p |
| `quality_tools.cause_effect` | `test_cause_structure_and_long_chinese`、`test_cause_editor_gui` / 结构往返 | 三级树增删改、工作表导入、去重、孤立子原因拒绝、中文长文本和密集多分支 PNG。无统计检验 |
| `quality_tools.multi_vari` | `test_multivari_independent_cells_and_plot`、`test_multivari_missing_combinations_and_coverage` / 人工组合 Y=10Σ因子+{0,2} | 1–4因子全部组合均值=10Σ因子+1，N=2、SD=√2、极差=2；75%覆盖保留缺失空格，50%拒绝；单观测SD=NA |
| `attribute_agreement.agreement_interval` | `test_exact_intervals_against_binomial_inversion_and_endpoints` / 独立二项尾概率反演 | 37/50 两尾各0.025；全对下界0.05^(1/50)，全错上界其补数；与 Minitab 端点单侧定义一致 |
| `attribute_agreement._kappa` Cohen | `test_cohen_manual_contingency_and_test_direction`、`test_perfect_opposite_random_agreement` / 手工2×2表及独立 SE0 公式 | [[20,5],[10,15]] → Po=.7、Pe=.5、κ=.4；SE0、Z、右尾检验核对；完美1、反向−1、随机0；稀疏/退化不捏造 p |
| 同上 Fleiss | `test_fleiss_independent_pair_enumeration_multicategory`、`test_fleiss_se_balanced_binary_analytic`、`test_fleiss_se_unequal_margins_independent_multinomial_enumeration` | 独立枚举每行评分对计算 Po；多类别；均衡二分类 Var0=2/[Nm(m−1)]；不均衡 .5/.3/.2 全枚举27种三评价员分配，delta SE0=0.013313373891854833 |
| 标准比较及分层定义 | `test_within_vs_standard_and_correlated_accuracy`、`test_design_validation_and_inferred_trials` | 内部一致1/.75与样本完全正确.5/0明确区分；单试次、单评价员、无标准、试次推断、不平衡、重复、矛盾标准和缺失拒绝 |
| `attribute_agreement.kendall_concordance`、SciPy `kendalltau` | `test_kendall_independent_rank_formula_and_friedman`、`test_kendall_tau_asymptotic_direction_against_pair_count_formula` / 独立 Friedman 及有符号配对计数参考 | Friedman 与 k(N−1)W、df=N−1及p一致，含并列校正；无并列10点 S=±45、Var(S)=125，tau=±1及右尾p与独立正态推导一致 |

属性逐条正确率的样本簇保守 CI：设每样本正确比例为 X，I(全对)≤X≤1−I(全错)，分别对两个二项概率构造单侧 alpha/2 下界，联合覆盖率至少 1−alpha，故界限保守但不要求样本内评价独立。样本之间仍须独立且具代表性。

### Fleiss 方差反例与修正

初版零假设方差表达式在均衡类别特例可通过，但不均衡全枚举反例失败：SE0=0.0152103986191458，独立参考为0.013313373891854833。现使用

`Var0 = 2(S2 + S2² − 2S3) / [N m(m−1)(1−S2)²]`，`S2=Σp²`、`S3=Σp³`。

推导来自独立同分布多项评分下的 delta influence：`[P_i − 2Σ_j p_j X_ij/m + S2]/(1−S2)`。测试独立枚举其平方期望，不复用生产中的合并方差公式。旧表达失败，修正后11个属性统计测试全部通过。

该零假设 SE0 仅用于检验，不用于非零 Kappa 置信区间。参见 [Fleiss / Nee / Landis 1979](https://doi.org/10.1037/0033-2909.86.5.974) 及解释其适用性边界的[原始研究](https://pmc.ncbi.nlm.nih.gov/articles/PMC8243202/)。

## 与 Minitab 的差异及未支持选项

- Pareto 分组为独立排序分面，不提供统一排序；同频按首次出现，保留完整类别名。
- Run 保守限制渐近 p 的适用性：中位两侧各10点，上下至少10点且无相等值；因此部分 Minitab 可报告近似p的数据这里显示 NA。
- 鱼骨支持类别/原因/子原因，不提供任意深度；不复制 Minitab 图形资源。特别密集的图形仍建议筛选或拆图。
- Multi-Vari 使用组合均值/极差和分面，不复刻 Minitab 全部边际均值叠加样式。统计组合最多10000，绘图最多36面板或横轴100水平，超限清楚提示。
- 属性输入仅长格式；宽格式可先用已有堆叠工具。设计必须平衡完整，无缺失插补，不支持加权 Kappa。报告包含各类别二分 Kappa和完整错判列联表。
- 不把相关试次 Kappa 均值套入独立方差，不报告其均值检验；逐条正确率跨试次的区间采用保守样本簇界。Fleiss 零假设方差和渐近门槛明确记录，不保证与 Minitab p 值逐位相同。
- 未生成 Kappa 非零假设区间、Kendall 跨试次平均系数检验；它们不属于本次必需输出。小样本 Kendall W/tau 的 p 标为 NA。

## GUI、文件与生命周期证据

最终图形、真实 Tk 客户区截图、CSV/Excel 位于 `docs/quality-tools-evidence/final/` 的对应测试目录；索引见 [证据目录](quality-tools-evidence/README.md)。PNG 经 Pillow 重新读取，表格数值回读容差 rtol=1e−14 / atol=1e−15（允许 NA 对应）；来源索引导出为字符串。

已检验 760×580 最小窗口中操作按钮可见、结果页至少140像素；图窗真实鼠标框选缩放、复位及现有 savePlot 入口；鱼骨无需数值坐标缩放，其保存仍使用同一入口。五项结果报告、写入新表、来源工作表不变；切换表及关闭来源保护；真实后台等待时 Tk 继续处理事件，取消/关闭后迟到结果不发布。

`no-stop-gpt` Audit 结论：保留一个五工具窗口，不新增框架、持久状态、缓存或项目格式；Future负责在途计算、Event负责取消后的发布抑制及协作中断，二者边界不同，不是重复状态。工作表快照及 SheetApp 绑定保护数据/输出来源；组合/绘图限制保护当前GUI资源。复用 StatTable/TableBlock、图窗和既有导航。未发现有证据可删除的额外抽象。

未验证：全部项目测试、PyInstaller完整发布包、不同操作系统/高DPI、多显示器及与已安装 Minitab 软件的逐图逐值比对。当前结论为源码与本机项目环境验收，不表示发布包验收。

## 文件范围与完成状态

五项必需功能均已实现并通过对应阶段及集成验证，没有阻塞的必需项。

- 新增计算/图形/界面：`code/quality_tools.py`、`code/attribute_agreement.py`、`code/quality_tools_plots.py`、`code/quality_tools_dialog.py`。
- 菜单：`code/MiniJMP.py`；只增加五项回调与菜单，不修改旧统计算法。
- 新增测试：`tests/test_quality_tools.py`、`tests/test_attribute_agreement.py`、`tests/test_quality_tools_dialog.py`。
- 同步预期/清单：`tests/test_menu_localization.py`、`tests/test_help_center.py`、`tests/fixtures/g12_table_inventory.json`；仅增加本次工具对应项，不更新旧算法冻结基线。
- 文档：本文件、`docs/MENU_TRANSLATION.md`、`help/pages/quality-tools.html`、`help/pages/quality.html`、`help/help-map.json`、生成的 `help/assets/search-index.js`、证据目录。

没有新运行依赖，没有提交、推送或 Git 清理；开始时工作区干净。任务没有要求安装或运行 Minitab；所有官方对照来自在线帮助及独立公式验证。
