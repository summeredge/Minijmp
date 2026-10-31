# MiniJMP P2-6.5 DOE 最终综合验收

完成日期：2026-10-31（测试与首轮复核于2026-10-30启动）。工作区：`C:\Users\shaoy\Documents\Minijmp`。

## 结论

**DOE Phase 2 在本轮约定支持范围内可关闭。**P2-6A/B的13项达到各自支持范围；没有未关闭的已确认计划内S1/S2核心缺陷。80项并非全部实现：75 implemented、2 partial、1 unknown、2 excluded。未取得输出的产品parity、可见桌面抽检、范围外高级能力不写成通过。

本轮开始时 `main` 工作区干净，HEAD为`71520c2`，P2-6A/B代码与测试已包含于该提交。原阶段报告“未提交”属于历史状态。本轮未改生产统计算法、DOE Schema或原始Minitab文件；新增独立参考测试、同步G12清单、帮助、矩阵与正式文档，并归档本次验证。

## 1. P2-6A/B 及80项状态

| Feature ID | 能力 | 正式矩阵状态 | 本轮计划范围 |
|---|---|---|---|
| SCR-002 | 确定性筛选设计生成 | partial | 达到约定范围 |
| SCR-003 | 确定性筛选连续响应分析 | implemented | 达到约定范围 |
| SCR-007 | 筛选设计混杂与可估计性 | implemented | 达到约定范围 |
| FAC-008 | 因子设计区组 | implemented | 达到约定范围 |
| FAC-010 | 两水平裂区设计 | implemented | 达到约定范围 |
| FAC-015 | 因子设计方差分析与推断 | implemented | 达到约定范围 |
| RSM-009 | 响应预测区间与置信区间 | implemented | 达到约定范围 |
| TAG-005 | 混合水平 Taguchi 正交表 | implemented | 达到约定范围 |
| TAG-008 | 噪声因子稳健性分析 | implemented | 达到约定范围 |
| TAG-009 | Taguchi 最优设置预测 | implemented | 达到约定范围 |
| FAC-012 | 因子设计折叠增补 | partial | 达到约定范围 |
| MIX-005 | 混料与过程或总量变量组合 | implemented | 达到约定范围 |
| GEN-006 | 增补最优设计 | implemented | 达到约定范围 |

全部80个Feature ID的官方功能依据、当前能力、GUI入口、参数范围、缺失行为、源码、测试及判定理由见[p2-6-final-feature-audit.csv](p2-6-final-feature-audit.csv)，正式清单为[feature-matrix.csv](../../docs/doe-minitab/feature-matrix.csv)。保持原20字段和验收号，不新增矩阵状态体系。

| 类别 | implemented | partial | unknown | excluded | 合计 |
|---|---:|---:|---:|---:|---:|
| Screening | 6 | 1 | 0 | 0 | 7 |
| Factorial | 18 | 1 | 0 | 0 | 19 |
| Response Surface | 16 | 0 | 0 | 0 | 16 |
| Mixture | 13 | 0 | 0 | 0 | 13 |
| Taguchi | 11 | 0 | 0 | 0 | 11 |
| General | 11 | 0 | 1 | 2 | 14 |
| **总计** | **75** | **2** | **1** | **2** | **80** |

SCR-002仍partial：新增4–12连续×2–4二水平分类的范围已验证，但厂商更宽的连续/分类组合未覆盖。FAC-012仍partial：正规部分因子与限定PB的任意非空因子子集可一次折叠，Split-Plot、分类/区组PB及连续多批折叠不支持。这些不是本轮约定范围内的核心缺交付。

GEN-012按接受的范围边界excluded：没有单独统一序贯规划器，替代流程为Foldover/Augment/Modify及父子谱系。GEN-013自动异常值处理证据不足，保留unknown；现有诊断供用户核实，不自动删值。GEN-014其他选点准则继续excluded。排除项不计入implemented，不由“未发现官方命令”推断厂商不存在。GEN-004原字段错位已修正。

## 2. 回归验证：执行命令与节点

解释器为项目`.venv\Scripts\python.exe`：Python 3.11.9、NumPy 2.4.6、SciPy 1.15.3、statsmodels 0.15.0、pandas 3.0.6、Tk 8.6；没有使用Codex bundled runtime或更改依赖。

| 批次 | passed | failed | skipped | warnings | 结果归属 |
|---|---:|---:|---:|---:|---|
| 完整DOE非`gui`文件集 | 1412 | 0 | 0 | 13 | final-nongui.xml/log，751.19秒 |
| 新增Schur独立参考 | 26 | 0 | 0 | 0 | final-dsd-independent.xml/log；144 deselected不是skipped |
| 18个常规GUI文件 | 150 | 0 | 0 | 54 | 每文件独立进程 |
| Screening精确节点分组 | 320 | 0 | 0 | 308 | 16组×20节点，精确去重 |
| Help/Menu/G12首次 | 93 | 1 | 0 | 0 | 唯一失败为G12输出位置清单过期 |
| 修复后G12 | 15 | 0 | 0 | 0 | final-inventory-fixed.xml/log，3.76秒 |

按JUnit的(classname,name)去重，**最终具有成功证据的唯一测试节点为2002**。首次G12中已成功的14项与复跑15项有重叠，未简单累加。唯一失败节点已在修复后通过；初始失败日志和XML保留，未删除冻结测试或扩大豁免。累计警告375条；汇总及各批次文件名见[final-validation-summary.json](final-validation-summary.json)。

完整非GUI文件批次含既有Tk生命周期/持久化集成测试，不把它称为全纯计算单元。1412为一次完整批次的实际值；随后仅新增26个独立节点，没有将其伪称为同一运行的1438 passed。生产代码不变，故复用已通过的其余节点；未重跑全仓pytest。

```powershell
$python = (Resolve-Path '.venv\Scripts\python.exe').Path
$files = @(rg --files tests | Where-Object { $_ -match 'test_doe_.*\.py$' -and $_ -notmatch 'gui' })
& $python -m pytest @files -q --tb=short --junitxml=Out/p2_6_doe_function_completion/final-nongui.xml
& $python -m pytest tests/test_doe_dsd_multi_categorical.py -k schur_reference -q --tb=short --junitxml=Out/p2_6_doe_function_completion/final-dsd-independent.xml
& $python Out/p2_6_doe_function_completion/run_final_gui.py
& $python -m pytest tests/test_help_center.py tests/test_menu_localization.py tests/test_g12_inventory.py -q --tb=short --junitxml=Out/p2_6_doe_function_completion/final-related.xml
& $python -m pytest tests/test_g12_inventory.py -q --tb=short --junitxml=Out/p2_6_doe_function_completion/final-inventory-fixed.xml
```

当时1412节点的精确收集顺序保存在`final-nongui-collection.log`；当前新增测试后重新运行完整文件集会多收集26项。GUI命令和精确Screening参数节点见[final-gui-manifest.json](final-gui-manifest.json)，脚本仅调用现有pytest，不接入产品路径。

历史P2-5的1408 passed/69 warnings（1201 DOE非GUI文件节点、141 GUI、66菜单）与P2-6A的1389 passed以及B的183/88等定向批次分别保留。1412比1389多23个收集节点是批次数差，不能据此把历史通过数量相加或声称新增了同等数量的独立功能。

## 3. GUI与代表工作流

| 独立进程批次 | passed | warnings |
|---|---:|---:|
| test_doe_bbd_gui | 10 | 1 |
| test_doe_ccd_options_gui | 13 | 0 |
| test_doe_custom_gui | 7 | 30 |
| test_doe_foldover_gui | 3 | 0 |
| test_doe_fractional_gui | 15 | 1 |
| test_doe_general_factorial_gui | 4 | 1 |
| test_doe_gui | 7 | 3 |
| test_doe_mixture_gui | 10 | 7 |
| test_doe_optimal_gui | 6 | 0 |
| test_doe_optimal_improvement_gui | 1 | 0 |
| test_doe_optimize_gui | 9 | 0 |
| test_doe_overlay_gui | 4 | 4 |
| test_doe_p4a_gui | 13 | 0 |
| test_doe_predict_gui | 7 | 0 |
| test_doe_rsm_gui | 12 | 3 |
| test_doe_splitplot_gui | 11 | 2 |
| test_doe_taguchi_gui | 15 | 2 |
| test_doe_taguchi_models_gui | 3 | 0 |
| screening-00 | 20 | 14 |
| screening-01 | 20 | 16 |
| screening-02 | 20 | 20 |
| screening-03 | 20 | 20 |
| screening-04 | 20 | 20 |
| screening-05 | 20 | 18 |
| screening-06 | 20 | 20 |
| screening-07 | 20 | 20 |
| screening-08 | 20 | 20 |
| screening-09 | 20 | 20 |
| screening-10 | 20 | 20 |
| screening-11 | 20 | 20 |
| screening-12 | 20 | 20 |
| screening-13 | 20 | 20 |
| screening-14 | 20 | 20 |
| screening-15 | 20 | 20 |

Screening收集320个节点，16组精确参数ID不重叠且并集等于收集清单，本轮320/320通过。没有使用`-k`数字子串过滤覆盖参数网格。本轮独立组没有重现`0x80000003`；未执行已知有历史原生异常的整文件聚合，也未声称原生异常原因已确定或框架问题已修复。

| 工作流 | 实际自动证据 |
|---|---|
| DSD创建→响应录入→选模→历史/结果 | screening组、test_doe_p4a_gui；包含多分类中心点、IC及Backward饱和提示 |
| 因子→ANOVA→预测/诊断 | test_doe_gui、general_factorial、rsm、predict；Type III缺失响应及混杂区组；来源过期拒绝 |
| Taguchi→S/N/响应模型→推荐/确认表 | taguchi_gui、taguchi_models_gui；L36、控制×噪声、指定设定CI及来源变化拒绝 |
| Mixture→预测/优化 | mixture_gui；v2总量交叉、CI/PI、Improve及来源删除后恢复 |
| Improve→运行替换→保存重开再分析 | optimal_improvement_gui；锁定与已执行行保护、固定运行数、谱系读回 |
| 保存、重开、复制、再分析 | 上述GUI及DOE persistence/schema/lifecycle文件；v1–v5及Mixture 1/2 |

这些是真实Tk控件和工作簿的程序驱动集成测试，涉及创建、取消、结果、图形调用、过期检测、文件保存和重新载入。**没有OS鼠标键盘可见桌面E2E或人工像素抽检**；高DPI、原生文件选择器、焦点快捷键、实际中文字体和图形视觉布局仍属人工抽检范围，不计为已通过。

## 4. 独立统计正确性与边界

[逐方法统计复核](p2-6-final-statistical-review.md)给出13项的生产入口→GUI→独立参考测试→推导→适用边界。原有冻结fixture及产品原件未改写。

本次审查曾发现SCR-002参考复用候选构造路径、仅核3个组合的S2证据缺口。现新增26组合Schur补参考：独立验证固定C的conference代数性质；用Fraction直接推导信息矩阵分块行列式，枚举2^(2c)个b/z符号方案；逐组合核对实际det(X'X)、首个并列方案，并用单个未配对零位翻转反例证明参考可区分错误候选。26 passed，原S2证据缺口关闭，无生产算法修改。

该DSD证明只针对给定有效C及指定b/z候选族，不证明跨所有DSD矩阵/运行点集合的全局最优。其他方法保留以下边界：

- Forward/Backward、AICc/BIC、ANOVA、回归、CI/PI均有独立公式/OLS或有理数投影参考；不可估、秩亏、饱和、零/不可辨误差方差、自由度不足时不生成误导性推断。
- Type III只用于支持的固定效应两水平/一般全因子；裂区使用整区/子区独立误差层，不把普通固定效应ANOVA替代裂区推断。非平衡/REML裂区不支持。
- 选模后p/CI以及混料优化点CI/PI为名义固定点结果，不校正模型选择/选点偏差。
- Taguchi静态交互和二水平等权噪声模型按声明有限组合精确枚举；动态交互、多水平噪声、自定义噪声概率不支持。
- 通用固定运行数Improve采用受保护单点局部交换、严格logdet改善，最多100轮/200000次评价；不是全局Fedorov最优证明。连续混料/RSM多起点搜索亦不证明全局最优。

## 5. 问题、警告及S1/S2去向

| 分类 | 本轮结论 |
|---|---|
| 确定统计计算错误 | 未发现已确认项；不外推到未支持工况 |
| 计划内功能缺失 | 13项约定范围均达到；矩阵仍2 partial/1 unknown/2 excluded |
| 确定核心GUI缺陷 | 本轮470节点未发现；可见桌面方面未验证 |
| 可接受功能边界 | 上述DSD/Foldover工况、非平衡/REML、名义CI与局部搜索限制，逐项保留 |
| 产品输出/呈现差异 | BBD标准序差异；RTF只显示精度；CJK字形及布局警告 |
| 尚未验证 | 76项无对应产品输出、其余配置parity、可见桌面与高DPI抽检、跨任意设计全局最优 |

S1未关闭核心缺陷：0；S2未关闭计划内核心/统计证据缺陷：0。G12初次失败是维护清单缺漏：`AnalyzeDOE.show_table`已移除结构化打印；`NoiseResponseModelTaguchi._tab`新增StatTable输出。按源码分类并保留真实GUI测试引用后15项检查通过，没有修改扫描器或放宽断言。

375条警告包括SciPy SLSQP迭代中越界后裁剪、Matplotlib tight_layout和测试字体CJK缺字。测试中约束及结果断言通过，但没有视觉抽检，不能保证实际字体或布局均正确。无确定数值错误，不为警告推测性改造Tk/统计路径。

P2-5旧登记的19条S2 FUNCTION_PARTIAL包含产品parity及更宽工况。它们不能机械等同本轮计划内生产缺陷；逐项最终范围和理由见审计CSV，原记录不删除：

| 原记录 | Feature | 当前去向 |
|---|---|---|
| PART-01 | SCR-001 | implemented；具体实现与保留缺口见80项审计，不将范围外差异计为本轮核心S2 |
| PART-02 | SCR-002 | partial；具体实现与保留缺口见80项审计，不将范围外差异计为本轮核心S2 |
| PART-03 | SCR-003 | implemented；具体实现与保留缺口见80项审计，不将范围外差异计为本轮核心S2 |
| PART-04 | SCR-006 | implemented；具体实现与保留缺口见80项审计，不将范围外差异计为本轮核心S2 |
| PART-05 | SCR-007 | implemented；具体实现与保留缺口见80项审计，不将范围外差异计为本轮核心S2 |
| PART-06 | FAC-002 | implemented；具体实现与保留缺口见80项审计，不将范围外差异计为本轮核心S2 |
| PART-07 | FAC-008 | implemented；具体实现与保留缺口见80项审计，不将范围外差异计为本轮核心S2 |
| PART-08 | FAC-010 | implemented；具体实现与保留缺口见80项审计，不将范围外差异计为本轮核心S2 |
| PART-09 | FAC-012 | partial；具体实现与保留缺口见80项审计，不将范围外差异计为本轮核心S2 |
| PART-10 | FAC-014 | implemented；具体实现与保留缺口见80项审计，不将范围外差异计为本轮核心S2 |
| PART-11 | FAC-015 | implemented；具体实现与保留缺口见80项审计，不将范围外差异计为本轮核心S2 |
| PART-12 | RSM-009 | implemented；具体实现与保留缺口见80项审计，不将范围外差异计为本轮核心S2 |
| PART-13 | MIX-005 | implemented；具体实现与保留缺口见80项审计，不将范围外差异计为本轮核心S2 |
| PART-14 | TAG-005 | implemented；具体实现与保留缺口见80项审计，不将范围外差异计为本轮核心S2 |
| PART-15 | TAG-008 | implemented；具体实现与保留缺口见80项审计，不将范围外差异计为本轮核心S2 |
| PART-16 | TAG-009 | implemented；具体实现与保留缺口见80项审计，不将范围外差异计为本轮核心S2 |
| PART-17 | GEN-004 | implemented；具体实现与保留缺口见80项审计，不将范围外差异计为本轮核心S2 |
| PART-18 | GEN-006 | implemented；具体实现与保留缺口见80项审计，不将范围外差异计为本轮核心S2 |
| PART-19 | FAC-019 | implemented；具体实现与保留缺口见80项审计，不将范围外差异计为本轮核心S2 |

## 6. 正式文档与帮助更新

- `docs/doe-minitab/feature-matrix.csv`：80项状态、支持范围、缺口、源码测试与GEN-004字段修复。
- `phase2-p5-preparation.md`、`phase2-p5-case-register.csv`、`phase2-p5-feature-evidence.csv`：自动化验收、独立数学验证、有限产品证据分开；DSD-S01/PB12/PB12 Foldover及五个BBD保留真实范围与原始数据。
- `docs/doe-minitab/README.md`、`phase2-roadmap.md`、`roadmap.md`、`phase2-gap-analysis.md`、`phase2-acceptance.md`：当前结论与历史阶段显式分开。
- `docs/doe-development.md`、`docs/CHANGELOG_DEV.md`：开发阶段关闭、下一阶段及用户可理解的帮助变更，保留未发布区域。
- `help/pages/doe.html`、`help/assets/search-index.js`：13项实际入口、必要参数、解释与限制；21个原有DOE锚点与help-map保持一致。已执行`tools/build_help_index.py`；Help 13、菜单66节点通过。
- 原A/B报告新增历史状态说明；本最终报告、80项审计、逐方法复核及原始执行结果保存在本目录。

复杂度Audit：新增测试复用既有Fraction行列式，独立Schur公式所需枚举直接覆盖声明范围；GUI脚本只为已知Tk隔离和精确节点审计服务，无新依赖、缓存、兼容层或产品抽象。未改生产代码、Schema、菜单行为或商业输出样式。

## 7. 产品证据、Git与收尾

已有Minitab文件只涉及SCR-001、SCR-003、FAC-012、RSM-002，共4/80项；其余76无对应输出。本轮核对22.6.0版本文本、DSD-S01 RTF/CSV、PB12原始/折叠CSV哈希，与原对照记录一致；原件及五份BBD未改。22.6.0不能追溯套用到原BBD文件，RTF不证明内部全精度；不宣称Minitab全功能parity。

本地单次验收提交包含本报告、矩阵、正式文档、帮助、清单、新参考测试和本次结果；A/B代码已在父历史中，不重复开发或覆盖。提交可用`git log -1 --format=%H -- Out/p2_6_doe_function_completion/p2-6-final-acceptance.md`定位。准确SHA、提交文件列表、提交后工作区状态保存在本地后置证据`final-git-state.log`（不纳入其自身所描述的提交）。没有推送、打标签或发布。

项目工作记忆按协作规则在提交后更新，独立保留未提交；不无差别暂存。后续阶段为版本需求与范围规划，未自动开展高级DOE、产品导出或发布。

**关闭判定：**算法/约定功能、独立数学参考、核心GUI自动化、工程兼容、80项状态及正式文档均具备本轮证据；已知S2参考缺口与确定性清单失败已闭合。仅在本报告声明的支持范围内结束DOE Phase 2，保留上述partial/unknown/excluded及未验证内容。
