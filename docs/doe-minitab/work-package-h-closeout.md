# DOE 工作包 H 收尾记录

日期：2026-10-29。状态：`WORK_PACKAGE_H_APPROVED_SCOPED`。H0–H6 限定范围开发完成；根据用户提供的上一轮 ChatGPT 独立 Review 结果，结论为 APPROVE（限定范围）。该静态 Review 不替代本轮测试，也不声明完整 Minitab 22 功能、标准序、报表格式或数值一致。

## H0 基线、方法合同与独立参考

- 起始分支为 `main`。此前 E/F/G 集成修复经范围核对后按授权提交为 `b8d64e0`（`Close out EFG integration fixes`）；没有 push。H 工作当时保持未提交。
- 读取了项目 `AGENTS.md`、工作记忆和 E/F/G 收尾材料。DOE Schema v5 的现有 `response_names` 与 `column_map.responses` 足以表达事件数、试验数和重复测量列；没有新增字段或 Schema v6。v1–v5 读取合同保持不变。
- 统计假设、自由度、支持设计族和不可用边界先记录在 [H 方法合同](work-package-h-method-contract.md)，随后才编写 H 生产代码。
- 独立参考位于 `tests/fixtures/doe_h_reference/`。`reference.json` SHA-256：`f5f4ee2246b03b3c6ee1140bd3de9f67f4911a94416bc87520969e2f2baf5c78`。生成器和核验器只使用 NumPy、SciPy 与标准库，不导入 MiniJMP 生产分析函数。

## H1–H5 功能与逐项验收

| 验收编号 | 功能 | 状态与证据 | 范围边界 |
|---|---|---|---|
| ACC-004 / SCR-004 | DSD 二元响应 | grouped-binomial logit；实际 DSD 矩阵与合法选择项；系数/模型/项检验、运行概率、诊断。STD/EDGE 由 H fixture 和 `test_doe_binary_analysis.py` 覆盖；真实 Tk DSD 平方模型由 `test_h_binary_dsd_terms_and_rsm_probability_plot` 覆盖。整体似然比较的显著负值由回归用例判为不可用。 | 完全/准完全分离、全事件/全非事件、秩亏、不收敛或不稳定似然比较不提供误导性推断。 |
| ACC-019 / FAC-017 | Factorial 二元响应 | 两水平全因子、正规分数别名组、PB 主效应、GFF 分类对比（数值标签仍为分类）；STD/EDGE 与真实 Tk 分数、PB、GFF 场景均有证据。 | PB 只拟合主效应；分数项按完整别名组解释；不支持未验证的裂区模型。 |
| ACC-020 / FAC-018 | Factorial 变异性 | 同次运行多列与区组内独立运行多行分别计算 Mean、样本 SD、N、缺失数及 run IDs；对 `ln(SD)` 做等权主效应与适用的固定区组推断；真实 Tk 显示摘要和主效应图。 | 不等样本数、缺失、n<2、SD=0 时保留摘要但不推断；不支持 Split-Plot、MLE 或未经验证变换。 |
| ACC-031 / RSM-016 | RSM 二元响应 | H4 范围内完成 CCD、BBD、自定义 RSM 的 grouped logit、模型秩/分离检查、拟合概率和合法编码域内概率图；自定义模型使用 Schema v5 声明项。真实 Tk BBD 图形与来源切换失效已验证。 | 官方拟合后 Response Optimizer 的二元概率目标/desirability 不在 H4 明确验收范围，MiniJMP 未实现；连续 DOE-4 优化器保持原路径。此边界已记录在 sources、帮助与矩阵中。 |
| ACC-059 / GEN-007 | 两水平 DOE 功效与样本量 | 两水平全因子/正规分数，以独立非中心 F 核验固定重复功效和整数重复数反解；真实 Tk 覆盖固定次数、目标功效和负向 δ 输入。 | δ=mean(high)-mean(low) 可为任一有限非零值；当前非方向性一自由度 F 使用 δ²，方向不改功效或样本量，δ=0 拒绝。无区组/中心点/裂区，完整等次数重复；总运行数上限 10,000。 |
| ACC-060 / GEN-008 | PB 与一般因子功效 | PB 与两水平 GFF 的模型秩、非中心参数、自由度和最小重复数均有独立参考；真实 Tk PB/GFF 功效路径通过。适配器按 `replicate` 选择一组基础设计行，保留 PB 因子投影产生的重复设定。 | GFF 仅所有因子均为两水平；PB/分数因子的主效应结论依赖别名和未拟合交互假设；效应符号不改变当前 1 df F 功效。 |

### 二项模型合同

`logit(p_i)=X_i β`，事件数按 grouped-binomial likelihood 拟合。标准误与系数 Wald z 来自 Logistic 模型；模型/项比较用嵌套似然比 χ²；自由度按设计行数与矩阵秩计算。普通连续响应 OLS/ANOVA、失拟 F 和置信区间不套用于二项模型。计数必须是整数且满足 `0 ≤ events ≤ trials`、`trials > 0`。概率使用稳定的逆链接并保持在 `[0,1]`。

### Variability 与功效合同

Variability 对每组原始重复观测使用样本 SD（分母 `n−1`），等测量数情况下对 `ln(SD)` 做等权最小二乘；不覆盖原响应。功效使用给定 DOE 基础设计矩阵、截距与全部主效应模型；`δ` 为高低水平差、回归系数为 `δ/2`，功效使用非中心 F 上尾。样本数反解逐个检查整数重复数，并覆盖前一重复数不达标的边界。

## H6 GUI、工程和项目集成

- 菜单已增加 Factorial、筛选、响应面二元响应，Factorial Variability，以及统计菜单下 DOE Power and Sample Size。参数与结果界面使用当前工作表快照；列/DOE 元数据或来源变化后清除过期结果。
- 图形使用项目 `chart_style` 字体与低饱和度配色；长表使用 `TableBlock` 分页/滚动。各窗口真实 Tk 取消按钮可用。
- 7 个真实 Tk 生命周期用例按单用例、单进程执行，均通过：Factorial 二元/变异性/功效、`.dexpl` 保存重开复制后再分析、响应修改失效、DSD 模型、RSM 概率图、分数别名、PB 与 GFF 功效。
- `test_doe_h_lifecycle.py::test_h_dexpl_copy_and_reanalysis_preserve_v5_run_lineage` 验证保存、重开、复制及重分析保留 run IDs、run order、响应和 DOE 元数据；坏元数据不替换当前工作簿由既有 `test_doe_persistence.py` 用例验证。Schema v2/v3/v5 旧格式测试与其余跨设计族回归通过。
- 已更新 `help/pages/doe.html`、`help/help-map.json`、`help/assets/search-index.js`、`docs/MENU_TRANSLATION.md`、G12 源码清单、feature matrix、acceptance、roadmap 和 changelog。
- `RSM-016` 的 H4 本地矩阵状态表示已完成本包明确范围；官方更广的二元概率 Response Optimizer 被单独标为未实现，不宣称完整产品功能对标。

## 实际验证

所有 Python 命令使用项目 `.venv\Scripts\python.exe`，Python 3.11.9。

- H 数学/核心专项：`test_doe_h_reference.py`、`test_doe_binary_analysis.py`、`test_doe_power.py`、`test_doe_variability.py`：**59 passed**。此前 `tests/test_doe_power.py tests/test_doe_h_reference.py -q`：**30 passed**；负向 δ 对称性、样本量反解、零值及非法输入有专项覆盖。
- H 真实 Tk 生命周期：7 个独立 pytest 进程：**7 passed**。
- 跨设计族纯统计与 Schema（Factorial、fractional、GFF、PB、DSD、RSM、Schema v2–v5、Mixture、Taguchi、optimal）：**328 passed**。
- E/F/G 混合工程生命周期：`test_doe_efg_workbook_integration.py::test_efg_designs_share_project_roundtrip_copy_analysis_and_metadata_isolation`：**1 passed**。
- 连续响应回归：DOE-4 CCD 优化 **1 passed**；CCD RSM 分析/图形 **1 passed**。
- 工程持久化：旧混合工程往返 **1 passed**；损坏元数据保持 live workbook **6 passed**；H v5 新响应往返/复制/再分析 **1 passed**。
- 帮助索引/主题：**13 passed**；中文菜单条目与翻译映射：**15 passed**；G12 源清单：**15 passed**。
- 此前真实 Tk 功效窗口 `tests/test_doe_h_lifecycle.py::test_h_binary_variability_and_power_windows_use_real_tk -q`：**1 passed**，负向 δ 固定重复与目标功效均可计算；帮助中心重跑：**13 passed**。
- 未运行全量 pytest。未执行 Minitab 桌面端逐项对照；本地测试证据不构成 Minitab 输出等价；独立 Review 结论另见下文。

## 80 项功能矩阵审计

矩阵共 **80 个唯一 feature_id**：`implemented 58`、`partial 18`、`unknown 3`、`excluded 1`。本次将六个 H feature_id 按明确验收范围更新为 `implemented`；RSM-016 单列未实现的 post-fit binary Response Optimizer，H4 仅覆盖分析/预测/概率图。原有 18 个 `partial`、3 个 `unknown` 与 1 个 `excluded` 均未提升。每个未完成状态都有证据和具体边界。

矩阵审计同时修正了 TAG-009 已过时的缺口描述、GEN-006 的 `select_augment` 代码定位，以及 MIX-006 指向不存在的测试文件；对混料各行的集成备注也更新为当前 E/F/G/H 本地集成状态。

## 最终独立 Review 与后续方向

`WORK_PACKAGE_H_APPROVED_SCOPED`。用户提供的上一轮 ChatGPT 独立 Review 通过 Local MCP Connector 检查了 H 源码、数学合同、测试和工程范围，结论为 **APPROVE（限定范围）**。本记录依据用户提供的 Review 结果固化，未在本轮重新执行该独立 Review；先前身份匹配失败请求与后续用户提供的成功 Review 是不同记录。

上一轮 ITERATE 的带符号 δ 问题已修复：`calculate_power()` 接受有限非零正负值、拒绝零值；正负等幅的非中心 F 功效和最小整数重复数一致，真实 Tk 支持负向输入，方法合同、帮助和更新日志保持一致。本轮专项与 GUI 复核结果见下方；不能把静态 Review 描述为本轮测试。

二元 RSM 的拟合后 Response Optimizer、未经验证的 Logistic 分离修正、Variability 的 MLE、复杂不等权和 Split-Plot 误差结构不在当前实现范围；功效限支持的两水平主效应 1 df 非中心 F。DOE Schema 保持 v5。下一阶段方向是建立 Minitab DOE 功能对标二期规划；二期尚未开始开发。

## 2026-10-29 最终收尾本轮验证

- `.\.venv\Scripts\python.exe -m pytest tests/test_doe_h_reference.py tests/test_doe_binary_analysis.py tests/test_doe_power.py tests/test_doe_variability.py -q --tb=short`：59 passed，0 failed。
- `.\.venv\Scripts\python.exe tests/fixtures/doe_h_reference/verify.py`：六项 ACC 独立参考核验通过。
- `.\.venv\Scripts\python.exe -m pytest tests/test_doe_h_lifecycle.py::test_h_binary_variability_and_power_windows_use_real_tk -q --tb=short`：1 passed，0 failed，覆盖负向 δ。
- `.\.venv\Scripts\python.exe -m pytest tests/test_doe_h_lifecycle.py::test_h_dexpl_copy_and_reanalysis_preserve_v5_run_lineage -q --tb=short`：1 passed，0 failed；以上两个真实 Tk 案例分别在独立进程串行执行。
- `.\.venv\Scripts\python.exe -m pytest tests/test_help_center.py tests/test_menu_localization.py tests/test_g12_inventory.py -q --tb=short`：94 passed，0 failed。
- 上述以外的 7 项生命周期、328 项跨设计族、E/F/G 集成与其他回归为历史证据，本轮未全部重跑；未运行全量 pytest 或 Minitab 22 桌面逐项对照。
