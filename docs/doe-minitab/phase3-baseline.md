# MiniJMP × Minitab Phase 3 基线与差距清单

2026-11-19 · MiniJMP 源码基线 `3dc862d` · 历史产品案例以 Minitab 19.1.0.1 为主。

## 基线与证据

- [90 项菜单矩阵](../../Out/statistics_minitab19_parity/feature_matrix.csv)对应当前「统计」30 项、「质量」25 项、「试验设计」35 项。2026-11-19 基线为 58 项有相关产品案例、32 项待取证。本轮为其中的非参数容差区间和 13+3 DSD 新增直接原生证据。共享实现的分量、模型或统计量只继承相应字段证据。本轮 `phase3-followup` 指向 [补验比较表](../../Out/statistics_minitab19_parity/phase3/comparison_followup.csv)。历史 `phaseN:case_id` 指向相邻 `phaseN/comparison.csv`、输入与原始输出；相关案例的选择只限定已比较字段。
- [DOE 80 项矩阵](feature-matrix.csv)以 Feature ID 与菜单矩阵关联，包括 75 项限定范围已实现、2 项部分实现、1 项未知、2 项排除。局部测试、独立解析参考、官方说明、原生产品输出分别保留。混料预测与优化的点位 CI/PI 已在 [生产路径](../../code/doe_mixture_predict.py)和[独立分数参考测试](../../tests/test_doe_mixture_intervals.py)核实，历史区间缺口关闭。[MIX-SL2 预测对照](../../Out/minitab19_parity/doe_mixture_comparison.csv)包括 P1–P3 的原生三位小数 CI/PI，以及从高精度原生矩阵与误差项独立重建的区间。
- DOE [八案冻结基线](../../Out/minitab19_parity/reference_baseline_acceptance.md)为 2559 PASS、0 FAIL、44 N/A、2 UNSUPPORTED。[补充修复后归档](../../Out/minitab19_parity/supplemental/supplemental_postrepair_acceptance.md)为 2903 PASS、4 FAIL、23 N/A、5 UNSUPPORTED。补充归档使用冻结输出与历史 MiniJMP 重放。混料总量/过程联合结果按[专项报告](../../Out/minitab19_parity/supplemental/mixture_extended/mixture_v2_acceptance_report.md)的模型空间和原生命令限制解读。Minitab 22.6 的少数样本另见 [P2-5 证据索引](phase2-p5-feature-evidence.csv)，由版本、配置和输出精度限定。
- 通用统计的 [Phase 3 历史修复汇总](../../Out/statistics_minitab19_parity/phase3/summary.csv)已将 CAP-05 Weibull 超差收敛为 12 PASS，CAP-03 的总体上尾 PPM 已通过，其余方法差异保留。[Phase 8](../../Out/statistics_minitab19_parity/phase8/summary.csv)的 118 项中有 109 PASS、8 METHOD_DIFF、1 UNSUPPORTED。属性图 Test 3/4 的重叠窗口标记时点与 Minitab 19 不同，MiniJMP 保留首次满足规则即报告的行为。Welch 使用分数自由度，Kendall p 值对应自身检验，Shapiro–Wilk 和 Ryan–Joiner 各用其自身定义。

## 开发队列

P1 优先补影响结论或常用报告的缺口，由低侵入且参考已就绪的项目先做。P2 涉及使用范围较窄、专用模型或较高实现成本的能力。按表内顺序推进。同一缺口关联多个菜单时共享结果定义，各菜单仍须经过生产入口验收。

| ID | 优先级与依据 | Minitab 能力 | MiniJMP 当前差距 | 独立验收案例与通过条件 |
|---|---|---|---|---|
| G01 | P1 · 单侧决策常用，计算与报告改动小 | 双样本 t 支持方向一致的单侧置信界 | `t_test_2samples` 输出双侧 CI 与单侧 p，已补齐两种单侧界 | 重用 [phase4](../../Out/statistics_minitab19_parity/phase4/case_inputs.json) `two_sample_pooled_t`，同数据双向分别用 t 分位数和存档 Minitab 下界核对；交换样本后上界等于原下界取负。另用 [phase5](../../Out/statistics_minitab19_parity/phase5/case_inputs.json) Welch 缺失样本按分数自由度独立计算；冻结原双侧结果。 |
| G02 | P1 · 预测诊断常用，现有线性模型可复用 | 回归及验收用 ANOVA 配置报告预测 R²，可由 PRESS 导出 | 完整 OLS、单/双因子 ANOVA 对应报告已补齐两项指标；PLS 已有其自身 CV/PRESS | 用 [phase4](../../Out/statistics_minitab19_parity/phase4/comparison.csv) `ols_multiple`、`ols_categorical`、`one_way_anova`、`two_way_anova`，使用同一模型矩阵逐行留一独立重拟合，计算 PRESS 及 1−PRESS/SST，核对原生字段显示精度。留一后不可估或 SST 为零时输出不可用。 |
| G03 | P1 · 尾部规格决策价值高，区间需逐分布验证 | Individual Distribution Identification 提供拟合参数点估计及百分位数不确定性 | 正态、对数正态已输出参数与百分位数 SE/CI；两案参数点估计与百分位数 SE/CI 原生 PASS | 目标版本 DCAPA 未取得参数 SE/CI，保留 NOT_RUN；详见下方补验。 |
| G04 | P1 · 计数回归选模，改动集中于报告 | Poisson 模型摘要提供偏差 R²、调整偏差 R² 和 AICc | `generalized_regression` 提供偏差、AIC/BIC 及三项选模统计 | 用 [phase4](../../Out/statistics_minitab19_parity/phase4/comparison.csv) `poisson`，按相同有效 N、参数数目及截距/offset 设定独立拟合空模型与全模型，并按 Minitab 定义算三项，与原生摘要比对。样本不足使 AICc 分母非正时须显示不可用。 |
| G07 | P1 · 非正态过程的覆盖判断，低至中成本 | 正态容差区间入口同时提供非参数次序统计量法 | 已核对 Minitab 19 的非参数容差区间输出 | 输入 1–100、90% 覆盖、95% 置信，单侧端点与实际置信度 PASS；双侧取秩和小样本端点策略为 METHOD_DIFF。 |
| G05 | P2 · 专用单侧方差推断，需单独验证尾概率 | 单标准差检验提供单侧 Bonett 检验 | 左右尾分别反解对应置信界；已修复错误互补逻辑 | σ₀=3、90% 的左右尾 p、上下限及既有双侧原生结果 PASS；补充 σ₀=4、12 的右尾。 |
| G06 | P2 · 方差差异定位，需控制多重性 | 等方差检验提供多重比较输出及 Bonferroni 标记的区间 | 联合区间原生 PASS；MiniJMP 保留自选 Bonett 对数成对比较 | 按官方图形 MC 检验复算全局 p=0.965542，与原生 0.966 一致；与 MiniJMP 成对法为 METHOD_DIFF。 |
| G09 | P2 · 二元回归选模与拟合检查，先补可解释的统计量 | Minitab 二元 Logistic 摘要和拟合优度表提供调整偏差 R²、AICc、偏差与 Pearson 检验及 Hosmer–Lemeshow | 模型摘要和 HL 原生 PASS；聚合偏差/Pearson 继续按真实协变量模式 | 逐行 Bernoulli 的偏差、Pearson、df 和 p 复算通过；与六模式聚合为 METHOD_DIFF。 |
| G08 | P2 · SCR-002，多分类筛选有价值，设计构造和可估性成本高 | DSD 接受二水平分类因子，分类设计每复制用两个伪中心点 | 13 连续 + 3 分类取得 Minitab 19 原生设计矩阵 | 1 重复、无随机化、无额外中心点。水平、34 行、2 个伪中心、秩 17 PASS；固定编码点集为 METHOD_DIFF。 |

## 本轮验收

- G01：双样本 t 检验报告按 μ₂−μ₁ 同时显示左尾上界和右尾下界，使用单侧 t 分位数。Phase 4 pooled 交换组别后与原生 90% 下界 1.374 一致。Phase 5 Welch 用 SciPy 独立检验确认分数自由度和两种单侧界，保留与 Minitab 19 整数自由度的历史方法差异。样本交换、原双侧统计和报告导出通过定向验证。

- G05：修正 Bonett 单侧 p 的计算，左右尾分别反解上限和下限。σ₀=3、90% 时左尾 0.709、右尾 0.203 原生 PASS。保留原双侧 Bonett 与卡方计算。

- G03：正态与两参数对数正态新增参数、5%/50%/95% 百分位数的标准误与 95% 置信区间。参数区间为均值 t 区间、标准差卡方区间；百分位数方差取 sigma²/n + z²sigma²(1−c4²)，区间沿正态分位数对称展开，属渐近近似。Phase 6 `normal_ties` 正态百分位数 55.5720/62.55/69.5280 与 SE 1.03448/0.670773 完全复现，对数正态 55.6147/62.4039/70.022 与 SE 0.94964/0.69093/1.1956 一致。对数正态参数仍在对数尺度报告，区间按 exp() 换回原尺度。其他分布输出未变。两组冻结输入的参数点估计和百分位数 SE/CI 均原生 PASS，参数 SE/CI 原生字段仍待取证。

- G04：Phase 4 Poisson 摘要三项与原生显示一致（64.11%、59.48%、72.12）。独立斜率 score 求根及 Poisson 对数似然复算通过。偏差 R² 为 1−D/D₀，调整值为 max(0, 1−(D+k−1)/D₀)，AICc 为 AIC+2k(k+1)/(n−k−1)。k 含截距，n 为有效行数，分母无效时留空。广义回归定向 11 项通过。[Minitab 定义](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/regression/how-to/fit-poisson-model/methods-and-formulas/model-summary/)

- G06：多样本方差检验新增两张表。其一为每组标准差的 95% Bonferroni 联合区间，按 Bonett 区间在 alpha/k 计算；phase4 `multi_variance` 三组得 (1.98865, 8.61111)、(2.34825, 8.41017)、(2.06587, 8.37558)，与原生完全一致。其二为 Bonett 对数尺度正态近似的成对标准差比，逐行给出原始 p、Bonferroni 调整 p、联合区间与显著差异判定，属自选方法，与原生“多重比较”全局 p 口径不同，未标记为已对标。原始 p 为单次对数比正态检验的双侧 p，调整 p 取 min(1, m·原始 p)，m 为成对比较数；phase4 `multi_variance` 三对得 0.886/0.544/0.766，调整后均为 1.000，与区间不跨 1 的结论一致。O'Brien/Levene/Brown–Forsythe 与两样本 F 结果不变。

- G09：二元 Logistic 摘要新增偏差 R²、调整偏差 R² 与 AICc，公式为 1−D/D₀、max(0, 1−(D+k−1)/D₀)、AIC+2k(k+1)/(n−k−1)，k 含截距。phase4 `binary_logistic` 得 19.03%、17.01%、44.41，与原生显示一致。拟合优度按设计矩阵的重复协变量模式聚合偏差与 Pearson χ²（df=模式数−k），本案例 0.2354/0.2437、df=4；HL 按拟合概率排序就近等分十组、相同概率不拆分，实际 6 组、χ²=0.2437、df=4、p=0.993，与原生 0.24/0.993 一致。聚合仅认设计行重复：无重复模式、零期望计数或 df≤0 时该两行标记不可用，不用未分组残差平方和代填；HL 不要求重复模式，自行判定可用性。保留原未分组 Pearson 行。

- G02：完整 OLS、分类 OLS、单因子 ANOVA、含交互双因子 ANOVA 的预测 R² 分别与 Phase 4 原生值 99.60%、82.71%、71.64%、76.12% 一致。四案 PRESS 及无交互双因子分支均通过独立逐行留一重拟合。PRESS 无直接原生字段，采用逐行留一作为数值依据。保留负预测 R²；不可留一估计时两项留空。

- G07：连续总体次序统计量法。选择使 Bin(n, 1−P) 的上尾概率 Pr(Y≥r)（单侧）或 Pr(Y≥2r)（对称双侧）达到目标置信水平的最大秩 r。用精确有理数二项尾和独立验证。1–100 样本、90% 覆盖、95% 目标置信，双侧 [2, 99]（实际 99.22%），单侧下限 5、上限 96（各 97.63%）。1–10 无可用端点，双侧和单侧最高分别为 26.39% 和 65.13%。真实 Tk 菜单确认与既有正态报告测试通过。Minitab 19 单侧端点及置信度 PASS；双侧 [2, 98]（97.6%）与小样本是否给端点的差异均已记录。

- G08：13 连续 + 3 分类沿用 Jones–Nachtsheim 多分类构造（基础 dsd16、折叠配对、伪中心点与 D-最优）。1 重复得 34 行（32 screening + 2 pseudo_center），主效应矩阵秩 17，logdet 与独立穷举 LAPACK 参考一致，主效应正交于二阶交互列；2 重复 68 行、4 个伪中心点。生产入口经 create_dsd 生成工作表并往返元数据通过。4–12 × 2–4 原有组合不变；Minitab 19 原生矩阵已归档，运行数、伪中心数、主效应秩相同，固定编码点集不同。

- 统一 Minitab 对标（2026-11-20）：已恢复 Minitab 19 COM 取证。G05 缺陷已修复，G03 参数 SE/CI 字段待取证，G06、G07、G08、G09 的方法差异以逐字段证据为准。见 [原生对标补验](phase3-g05-g08-parity.md)。

- G09 定向修复（2026-11-20）：聚合 GOF 原按四舍五入后的拟合概率分组，无重复模式时也会用一个近似唯一概率值撑出 df>0 的假检验（12 个不同 x 的案例得到 df=10、p=0.439）。现改为按设计矩阵行识别重复协变量模式，并按可用性分别判定：无重复模式、零期望计数或 df≤0 时聚合两行标记不可用，HL 仍独立给出 7.5159（df 8、p 0.482）。phase4 `binary_logistic` 六模式案例聚合值保持 0.2354/0.2437、df=4，HL 与摘要指标均未变。

## 产品证据待办

| ID | 优先级 | 产品能力与本地现状 | 独立案例与完成条件 |
|---|---|---|---|
| E01 | P1 · 二元响应面 Wald z | 未解决的数值差异。A、A²、B²、A*C 在原 1e-9 规则下仍超差，现有证据不足以唯一归因 | Minitab 19 的 `CTOLERANCE 1e-10` 和 `1e-12` 均回读相同的 β、FITS、SE 和 M2。M2 与终点 Fisher 的最大元素差均为 1.536e-10。MiniJMP 保留最终 Fisher 实现。见 [E01 原生对照](../../Out/minitab19_parity/supplemental/binary/fisher_diagnosis/m2_investigation/e01_convergence.md)。 |
| E02 | P2 · FAC-012 扩展边界 | Minitab FOLD 文档列两水平部分因子与 PB。本地已支持限定正规/PB 一次折叠，分类、中心点或区组 PB 及再次折叠仍受限。裂区 Foldover 的产品支持未证实 | 先以 PB12（一个二水平分类因子、配置中心点）尝试对该因子执行 FOLD，获取实际命令与输出。若该配置受支持，再按原生点集核验折叠水平、中心点/区组处理、响应保留与新增行空值。以 FOLD-REG 和 FOLD-PB 回归已有范围。 [Minitab Session Commands](https://support.minitab.com/en-us/minitab/session-command-help/) |

取证时冻结输入、产品版本、界面选项或原生命令、原始输出、字段与精度。整数、标签和秩精确比较；复用历史案例沿用其字段容差，新显示型参考按单字段最后一位的半单位判断。新取证先确定口径与容差，再比较。矩阵中其余待取证项及 DOE 行内其余范围限制作为调查入口，厂商选项、实际用途和验收案例充分后再定开发优先级。GEN-012/013/014 保持既有状态。

历史统计验证脚本可写回同名菜单矩阵。重放历史结果时，应先保留本轮矩阵，并按案例字段合并新的验证证据。
