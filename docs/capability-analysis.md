# 完整过程能力分析与 Sixpack

本阶段只覆盖正态/非正态能力、Box-Cox/Johnson 正态化和两种 Sixpack。旧 `cpk.py`、旧 Cpk 菜单与冻结测试保留；新入口不得继承将 LSL、Target、USL 排序的旧行为。本文件记录方法合同和官方对标，不能替代运行证据。官方文档核对日期：2026-10-23；已读 GUI 与绘图代码，核心 `code/capability.py` 在本次文档核对时尚未落盘，其数值、校准与边界行为仍待主任务验证。

## 输入、结果与适用性

质量菜单新增“正态过程能力（完整）”“非正态过程能力”“Box-Cox / Johnson 变换”“正态能力 Sixpack”“非正态能力 Sixpack”，共用 `CapabilityDialog`，帮助键为 `quality.capability_analysis`。

| 菜单入口 | 初始分析类型 | 方法选择 |
| --- | --- | --- |
| 正态过程能力（完整） | 正态能力 | 原尺度正态；可选 Box-Cox / Johnson SU |
| 非正态过程能力 | 非正态能力 | Weibull / Lognormal / Gamma；变换须选“无” |
| Box-Cox / Johnson 变换 | 变换诊断 | 默认 Box-Cox；可改 Johnson SU；可不填规格 |
| 正态能力 Sixpack | 正态 Sixpack | 原尺度或变换后的正态六格诊断 |
| 非正态能力 Sixpack | 非正态 Sixpack | 原尺度非正态六格诊断 |

窗口允许切换分析类型。置信水平默认 95%，K 默认 6，连续子组大小默认 1，最近子组数量默认 25。固定 λ 留空时估计；仅 Box-Cox 使用该参数。子组 ID 列优先于固定大小。操作为选择测量列、填写适用规格与方法后点击“分析”；选结果页后可“当前表写入新工作表”或“导出当前表 CSV / Excel”。“完整报告”输出所有结果表；“打开图形”才建立图窗，非 Sixpack 模式显示直方图与 Q-Q，变换时另显示变换前诊断。帮助按钮和 F1 打开同一离线主题。

测量列须为有限实数；默认拒绝缺失，只有显式选择才删除不完整行，不插值。保留输入顺序、原索引及来源位置；子组 ID 是标识符，不转换成测量数值。按连续行分组，固定子组大小不能静默截掉余数；ID 的不连续复现应显式处理或拒绝，不能隐式排序拼接。能力至少指定一侧规格；双侧必须 LSL < USL，Target 不自动填充或参与规格排序。纯变换诊断可不设规格。

结果绑定打开对话框时的工作表快照，数值表供 CSV/Excel 或新工作表输出；图形通过现有图窗保存。输出操作、取消、关闭和切换工作表仍需真实 GUI 验证，不能仅凭帮助登记判断通过。

拟合在后台运行。“取消计算”或 Escape 仅标记丢弃当前结果，等待拟合结束后恢复可分析状态，保留上次结果；并非立即中断优化器。关闭窗口后丢弃待返回结果。错误通过状态栏和消息框显示；结果表的缺失项显示为 NA。控制图诊断表在 GUI 发布结果时添加；第一条 MR 无定义，其“超控制限”标记为 NA。发现超控制限点时追加过程可能不稳定的警告，不能据其余点未报警推断所有稳定性检验通过。

过程稳定、分布拟合适用、能力达到工程要求是三个不同条件。p 值较大只表示未拒绝指定模型，不能证明模型正确；零实测超规不等于零总体风险。小样本、相关数据、失控和不良拟合都使外推 PPM 不可靠。

## 正态方法合同

令 K 为能力总宽倍数，默认 6；h=K/2。总体均值为全部观测均值，整体标准差 s 使用 n−1 分母，默认不作 c4 无偏修正。

单值组内标准差采用相邻两点移动极差均值：`sigma_within = mean(abs(diff(x)))/d2(2)`，`d2(2)=2/sqrt(pi)`。顺序有统计意义，不得排序后计算。多观测子组的方法合同为合并组内方差 `sp²=ΣΣ(xij−mean_i)²/df`，`df=Σ(ni−1)`，再用 `sigma_within=sp/c4(df+1)` 修正；`c4(m)=sqrt(2/(m−1))*Gamma(m/2)/Gamma((m−1)/2)`。报告应记录此选择。当前窗口未提供 Rbar/d2、Sbar/c4 或无修正的选择开关。Minitab 提供多种估计和修正选项，本阶段固定方法不代表实现了全部选项 [R1,R2]。

| 指标 | 定义与不可用条件 |
| --- | --- |
| Cp | `(USL−LSL)/(K*sigma_within)`；须双侧规格 |
| Cpl、Cpu | `(mean−LSL)/(h*sigma_within)`、`(USL−mean)/(h*sigma_within)`；缺侧 NA |
| Cpk | 取已定义侧指数最小值；仅一侧时取该侧，可为负 |
| Pp、Ppl、Ppu、Ppk | 上述公式以整体 s 代替 sigma_within |
| Cpm | 双侧且明确 Target 时为 `(USL−LSL)/(K*sqrt(s²+(mean−Target)²))`；否则 NA |

实测下/上超规分别按 `x<LSL`、`x>USL` 计数除以有效 n；等于规格限视为合格。预计下尾为 `Phi((LSL−mean)/sigma)`，上尾使用正态 survival function；分别按组内及整体 sigma 报告，PPM=概率×10⁶。缺侧不计超规，缺侧指数仍为 NA。不得把模型预计值写成实测。

本实现为原尺度正态整体 Ppl/Ppu 提供非中心 t 参数等尾反演区间；Cp/Pp 与整体/合并组内标准差提供适用的卡方区间，Cp 以未修正 sp 推导，不能再次乘 c4。Cpl/Cpu/Cpk/Ppk/Cpm、变换后及非正态指数区间未提供（NA）。置信水平仅对实际实现的区间生效。正态独立样本下 s 的卡方区间和 Pp 的相应区间有明确定义；合并方差在正态同方差子组假设下使用其自由度。重叠 MR 的相关性使其不能套用 n−1 自由度卡方精确区间；Cpk/Ppk 的正态近似不是精确区间。未实现或无可靠依据的 Cpm、变换后、非正态指数和尾部 PPM 区间必须标 NA/未提供，不因窗口有置信水平而宣称覆盖全部指标。

## 非正态方法及定义差异

Weibull、Lognormal、Gamma 均采用 SciPy 对应连续分布、`floc=0` 固定位置参数的极大似然估计，数据严格为正。分别报告 shape/scale（Lognormal 的 shape 为对数标准差，scale=exp(对数均值)）、支持域、拟合诊断和收敛异常。不能自动平移负值，也不能用三参数自由位置估计冒充本方法。支持域外规格的 CDF/SF 可合法等于 0/1；这与支持域外观测导致模型无效不同。

令 `a=Phi(−K/2)`，`qL=F⁻¹(a)`、`qM=F⁻¹(0.5)`、`qU=F⁻¹(1−a)`。本阶段主指数为百分位法：

`Pp=(USL−LSL)/(qU−qL)`；`Ppl=(qM−LSL)/(qM−qL)`；`Ppu=(USL−qM)/(qU−qM)`；`Ppk=min(已定义侧)`。

缺侧 Pp 为 NA；仅有一侧时 Ppk 使用该侧。K=6 时分位接近 0.00135 和 0.99865，对应 Minitab 所述 ISO 百分位思路 [R3,R4]，不得把该 Ppk 标作 Minitab 默认 Z-score Ppk。

等价 Z 独立列示：`Z_lower=−Phi⁻¹(F(LSL))`、`Z_upper=Phi⁻¹(F(USL))`，总超规 `p=F(LSL)+SF(USL)`，`Z_bench=Phi⁻¹(1−p)`。Minitab 默认 Z-score 法则是 `Pp_Z=(Phi⁻¹(F(USL))−Phi⁻¹(F(LSL)))/K`，`Ppk_Z=min(Z_lower,Z_upper)/(K/2)`。对于偏态模型，这些值通常与百分位法不同。支持域边界的无限 Z 不得伪装成有限能力保证；Minitab 默认法对支持域外规格存在不可计算条件，应明确差异。无任何默认 1.5σ 漂移补偿。

实测 PPM 仍来自原始观测计数，模型预计 PPM 来自 F/SF。非正态模型只有整体分布能力，不在原数据上直接套正态 Cp/Cpk。若使用估参后 KS 统计量，普通固定参数 KS p 值不具正确校准；应使用重新拟合的参数自举或明确未提供校准 p 值。AD 统计量也不能搭配未经验证的通用 p 值。当前 GUI 无自举次数、随机种子或拟合优度阈值控件；绘图只显示核心结果中已有的有限数值诊断，不执行校准。本次不宣称已实现或验证参数自举。实际拟合优度采用 KS 参数自举：每次从拟合分布采样、重新 MLE 拟合，固定种子 20261023、199 次，p=(超过次数+1)/200，分辨率0.005；AD 仅给统计量而无通用 p 值。该 Monte Carlo p 值有模拟误差，不能当作精确概率。拟合参数、分布检验和能力区间各自需要独立证据。

## 变换定义、反变换与限制

Box-Cox：`g(x)=(x^lambda−1)/lambda`，λ=0 时 `log(x)`，严格正域；估计 λ 使用正态剖面似然 MLE，亦可固定 λ。零附近应连续稳定计算，逆为 `exp(y)` 或 `(1+lambda*y)^(1/lambda)`，逆变换须满足 `1+lambda*y>0`。该定义对所有 λ 都单调递增，数据、LSL、USL、Target 同用 g，不交换尾部。原尺度分位由逆变换取得；不能直接将变换后 sigma 当作原尺度 sigma。

Minitab 文档以 `x^lambda`（λ=0 为 log）描述 Box-Cox，并通过标准化变换变量标准差优化；可将最优 λ 四舍五入为 0.5 或整数 [R5,R6]。本阶段 SciPy 剖面似然 MLE 和未舍入 λ，以及 `(x^lambda−1)/lambda` 的尺度约定，必须披露，不承诺在子组优化及负 λ 下与官方界面逐值一致。

Johnson 仅支持 SU：`z=a+b*asinh((x−loc)/scale)`，b>0、scale>0、x 可为任意有限实数；逆为 `x=loc+scale*sinh((z−a)/b)`，参数按 Johnson SU MLE 拟合。规格用同一递增变换。参数估计失败、非有限结果、变换后正态 AD 超过10%临界值时明确失败，不自动改族或返回“已正态化”。Johnson 只报告整体能力，组内指数与组内预计 PPM 不提供；变换前后的 AD 诊断分别输出。

Minitab 在 SB/SL/SU 三族中按 Chou 等方法估参，再选择 AD p 值满足阈值且最大的变换，默认准入阈值 0.10；其 Johnson 能力只报告整体能力 [R5,R6]。SU MLE 不是该择族算法。经过同一批数据拟合和选参后的正态性 p 值有选择偏差，不能当作独立验证；本阶段不承诺实现官方 AD 置信带、全族择优或全部能力区间。

## Sixpack 六格及控制限

官方示例采用三行两列，按“行、列”记录，而不是误把第一个行内第二格当 MR 图 [R7–R10]：

| 行 | 左列 | 右列 |
| --- | --- | --- |
| 1 | I 或 Xbar 图 | 能力直方图 |
| 2 | MR 或 R/S 图 | 正态/拟合分布概率图 |
| 3 | 最近 25 个子组（单值时为观测） | 能力比较图 |

最近数量可配置。**正态与非正态均允许子组 >1**：当前绘图对全部单值子组使用 I-MR；全部子组至少含 2 个观测且最大子组大小≤8 时使用 Xbar-R，否则使用 Xbar-S。单值与多观测子组混用会报错；可变大小按实际 ni 计算限值。官方非正态图形方法页确认子组>1 时有 Xbar 配合 R/S [R8,R9]；图形解释页对 R 的文字写为“>2 且<9”，本项目 n=2 的约定以实现为准，不将该网页文字当作边界逐值对齐证据。

正态 I 图限值为均值±3*sigma_within；MR 使用长度 2 的标准控制图常数。Xbar 图使用组内 sigma/sqrt(ni)，R/S 图使用相应控制图常数，不混用整体 s。非正态 **I 图** 的下/上限为拟合 F 的 `PPF(0.00135)`、`PPF(0.99865)` [R8,R9]；该规定不能无依据扩展为 MR 差值分布的分位限。控制图 ±3σ/固定分位与能力 K 是不同设置，改变 K 不应静默改变 SPC 控制限。

正态直方图叠加组内和整体正态曲线；非正态叠加所选模型密度。官方正态能力比较图包含组内、整体和规格三个区间；官方非正态比较图使用标准正态 Z 尺度表示过程区间与转换后的规格 [R7,R9]。当前正态比较图以分析尺度绘制过程区间、用竖线表示规格和目标；非正态比较图采用官方对应的标准正态尺度 `Z=Phi⁻¹(F(x))`，整体区间为 `[-K/2,K/2]`，LSL、USL、Target 用同一映射。边界或浮点尾概率饱和导致 Z 无穷时，用文字注释，不画成有限规格线；图中的主 Pp/Ppk 仍按百分位法，Z 尺度显示不会改变指标定义。正态双侧规格另绘规格区间，并标记过程中心；最近子组格显示观测散点及整体均值线。当前概率图为模型理论分位数对样本分位数的 Q-Q，使用中位秩绘图位置；没有概率置信带，不在绘图层计算 AD p 值。以上显示差异不影响六格位置约定。

非正态 I 图使用拟合分位限；MR 仍使用正态 MR(2) 常数近似，非正态多观测子组采用正态 3σ 近似，均不保证非正态过程的实际误报概率。这些方法会写入“控制图诊断”表。正态化后的图在变换尺度绘制；原始观测和原尺度规格需结合变换报告解释。

规格限表达客户要求，SPC 控制限表达过程预期波动；需区别线型和图例。异常点须明显标注，未执行的 Nelson/Western Electric 规则不能被称为已通过。单侧规格不画虚构的另一侧边界。

## 逐方法独立证据矩阵
## 改善前后能力对比（原尺度）

`CapabilityDialog` 底部新增“启用阶段对比（改善前/改善后）”，默认关闭。适用正态能力、非正态能力及两者 Sixpack；变换诊断不适用。阶段划分复用 `improvement_chart.split_phases`（阶段列按实际出现顺序，只接受两个连续段；时间列必须非递减，不隐式重排）。测量列、LSL/USL/Target、子组、分布族、置信水平与 K 沿用窗口字段，两阶段共用同一规格与 K。

`code/capability_compare.py` 对每阶段独立调用 `capability.analyze_capability`，子组只在该阶段行内划分，跨阶段重复的子组 ID 直接拒绝；`source_row` 映射回整张工作表位置。对比只提供差值，不提供 Cp/Cpk/Pp/Ppk 差值区间或检验，理由与单阶段区间不足相同；显著性检验仅 Welch 均值差异、Levene 波动差异与 Ljung-Box 自相关。

| 输出表 | 主要字段 | 不可计算时的处理 |
| --- | --- | --- |
| 数据与规格摘要 | 阶段定义、共用规格与 K、分布族、尺度、样本量、来源行、缺失删除、子组口径 | 规格缺失直接拒绝 |
| 能力指数对比 | Cp/Cpl/Cpu/Cpk、Pp/Ppl/Ppu/Ppk（非正态仅 P 类）、等价 Z；差值、变化率 | 显示“不适用”及原因 |
| 波动与超规对比 | 均值、组内/整体标准差与波动比、实测超规数与超规率、预计 PPM（整体；正态未变换另含组内） | 零基准不写变化率 |
| 稳定性与分布诊断 | 各阶段控制图图型、Nelson 异常点数、越限点数、AD/KS/p、有效 n 与缺失行 | 拟合失配标注预测 PPM 不可靠 |
| 统计检验 | Welch、Levene、各阶段 Ljung-Box | 自相关无法评价时标注显著性未评价 |
| 分析结论 | 能力指数前后值、规格外比例、解释限制、改善结论边界 | 有限制时不输出显著改善结论 |

对比图 `capability_plots.plot_capability_comparison` 由两阶段直方图（共用横轴与规格）、能力指数柱状图和实测/预计 PPM 对数面板组成，仍在原 PlotViewer 中缩放、保存与导出；Sixpack 与普通能力图未改动。报告由 `capability_compare.print_report` 生成，顺序为摘要、稳定性与分布、能力指数、波动与超规、统计检验、结论边界。

变换组合当前不支持：两阶段分别拟合 Box-Cox/Johnson 后的能力指数不在同一尺度，窗口明确提示并保持单阶段变换分析可用。


生产入口均为 `capability.analyze_capability`（变换运算为 `transform_values`），GUI 生产入口为 `Minijmp.capability_analysis → CapabilityDialog`。下表列实际独立参考测试；完整命令及数量见 [验收记录](capability-validation.md)。

| 方法 | 独立参考测试（tests/） | 参考与边界 | 结果 |
| --- | --- | --- | --- |
| 正态 MR2 | test_capability.py::test_normal_mr_order_indices_ppm_and_no_target | 手算相邻差、2/√π、总体样本方差；顺序、无 Target、实测与预计 | 通过 |
| 合并子组与 Cp/Pp 区间 | test_capability.py::test_pooled_c4_and_exact_ci_uses_uncorrected_sp | 手算SS=12、df=3、c4(4)及独立卡方分位；拒绝错误c4区间因子 | 通过 |
| 单侧负指数、极端尾 | test_capability.py::test_one_sided_negative_index_and_extreme_normal_tail | 独立正态CDF/SF，单侧NA、均值越界、有限对数尾Z | 通过 |
| 整体 Ppl/Ppu 区间 | test_capability.py::test_exact_one_sided_nct_intervals | 非中心t定义的CDF端点分别0.95/0.05；正负统计量、K=5 | 通过 |
| Lognormal MLE/能力/Z | test_capability.py::test_lognormal_closed_mle_percentile_and_z_are_distinct | 对数均值/方差闭式MLE、解析CDF/PPF、百分位与Z不等 | 通过 |
| Weibull MLE/尾部 | test_capability.py::test_weibull_score_and_analytic_tails | 独立shape得分方程及解析F/PPF | 通过 |
| Gamma MLE/尾部 | test_capability.py::test_gamma_score_and_independent_integral | 独立shape方程、Gamma密度积分/PPF | 通过 |
| 正域/失配/校准 | test_capability.py::test_nonnormal_support_domain_extreme_tails_and_failure；test_bad_nonnormal_fit_is_flagged_and_bootstrap_is_repeatable | 支持域外规格、非法拟合、混合模型失配及参数自举复现 | 通过 |
| Box-Cox | test_capability.py::test_boxcox_analytic_forward_inverse；test_boxcox_mle_matches_profile_likelihood_and_domain_extrapolation | λ=0、1、接近0、负λ；独立剖面似然优化、逆域/像域外推警告 | 通过 |
| Johnson SU | test_capability.py::test_johnson_analytic_parameters_and_mle_score；test_transform_domain_bad_parameters_and_no_qualified_transform | 独立asinh/sinh、Jacobian似然数值导数、失败域及不合格变换 | 通过 |
| 数据合同/异常 | test_capability.py::test_source_missing_and_ids_preserved_without_regrouping；test_invalid_inputs | 来源索引/行号、显式删除、常数/不足/反向规格/重复ID/未满组 | 通过 |
| Sixpack 控制限/图形 | test_capability_plots.py | 正态I/MR常数、Xbar-R/S解析公式、非正态PPF、六格顺序、Z尺度、PNG重读 | 通过 |
| GUI/导出 | test_capability_dialog.py | 五菜单、3非正态分布、2变换、单侧/子组、取消/关闭、来源快照、长索引CSV/XLSX重读、原表不变 | 通过 |
| 改善前后对比 | test_capability_compare.py::test_two_phases_match_independent_reference_and_share_specs | 手算两阶段 MR2/样本方差/Cp/Cpk/Pp/Ppk、正态 PPM 与超规计数；共用规格 | 通过 |
| 阶段与子组边界 | test_capability_compare.py::test_stage_order_subgroups_and_source_rows_stay_within_phase；test_subgroup_crossing_phase_boundary_is_rejected | 实际出现顺序、来源行回映射、阶段内合并子组、跨阶段子组拒绝 | 通过 |
| 单侧/零超规/非正态 | test_capability_compare.py::test_one_sided_specs_zero_defects_and_not_applicable；test_nonnormal_mode_never_mixes_normal_indices | 单侧 Cp 不适用而 Cpk 可用、零超规不平滑、非正态仅百分位指数 | 通过 |
| 适用性限制 | test_capability_compare.py::test_autocorrelation_and_fit_mismatch_limit_conclusions | 强自相关与拟合失配时标注限制、不输出显著改善结论 | 通过 |
| GUI/图形/导出 | test_capability_dialog.py::test_stage_comparison_defaults_off_then_switches_result | 默认关闭、勾选展开、结果页与对比图切换、报告与 Excel、变换组合拦截 | 通过 |

静态 PyInstaller onedir 审查不代表成功打包；本阶段未创建提交或推送，也未实施下一阶段质量工具。

## 官方参考

- [R1 正态标准差估计选项](https://support.minitab.com/en-us/minitab/help-and-how-to/quality-and-process-improvement/capability-analysis/how-to/capability-analysis/normal-capability-analysis/perform-the-analysis/specify-the-estimation-method/)
- [R2 正态方法与公式](https://support.minitab.com/en-us/minitab/help-and-how-to/quality-and-process-improvement/capability-analysis/how-to/capability-analysis/normal-capability-analysis/methods-and-formulas/methods/)
- [R3 非正态整体能力公式](https://support.minitab.com/en-us/minitab/help-and-how-to/quality-and-process-improvement/capability-analysis/how-to/capability-analysis/nonnormal-capability-analysis/methods-and-formulas/overall-capability/)
- [R4 非正态指数与默认 Z-score/ISO 方法](https://support.minitab.com/en-us/minitab/help-and-how-to/quality-and-process-improvement/capability-analysis/supporting-topics/capability-metrics/capability-indices-and-nonnormal-data/)
- [R5 Box-Cox 与 Johnson 算法](https://support.minitab.com/en-us/minitab/help-and-how-to/quality-and-process-improvement/capability-analysis/how-to/capability-sixpack/normal-capability-sixpack/methods-and-formulas/methods/)
- [R6 变换选项、舍入和 Johnson 整体限制](https://support.minitab.com/en-us/minitab/help-and-how-to/quality-and-process-improvement/capability-analysis/how-to/capability-sixpack/normal-capability-sixpack/perform-the-analysis/specify-a-transformation/)
- [R7 正态 Sixpack 图形解释](https://support.minitab.com/en-us/minitab/help-and-how-to/quality-and-process-improvement/capability-analysis/how-to/capability-sixpack/normal-capability-sixpack/interpret-the-results/all-statistics-and-graphs/graphs/)
- [R8 非正态 Sixpack 图形方法](https://support.minitab.com/en-us/minitab/help-and-how-to/quality-and-process-improvement/capability-analysis/how-to/capability-sixpack/nonnormal-capability-sixpack/methods-and-formulas/graphs/)
- [R9 非正态 Sixpack 图形解释](https://support.minitab.com/en-us/minitab/help-and-how-to/quality-and-process-improvement/capability-analysis/how-to/capability-sixpack/nonnormal-capability-sixpack/interpret-the-results/all-statistics-and-graphs/graphs/)
- [R10 最近子组数量选项（左下，默认25）](https://support.minitab.com/en-us/minitab/help-and-how-to/quality-and-process-improvement/capability-analysis/how-to/capability-sixpack/normal-capability-sixpack/perform-the-analysis/select-the-analysis-options/)
