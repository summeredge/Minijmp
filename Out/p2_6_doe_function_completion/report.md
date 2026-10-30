# DOE Phase 2 P2-6 核心功能完成报告

日期：2026-10-30  
状态：本地实现与验证完成；当前分支 `main`，未提交、未推送、未发布。DOE Schema 保持 v5。

## 功能范围与保留边界

| ID | 完成内容 | 保留边界 |
|---|---|---|
| SCR-003 | DSD 逐步选模保留默认 F 选择，增加 Forward、Backward、Forward AICc/BIC；显示完整选择路径、每步统计量和停止原因，强层级与秩/自由度检查生效。 | Backward 初始候选模型饱和或秩亏时提示缩小候选集；选后推断仍是未校正模型选择偏差的名义结果。 |
| SCR-007 | PB/DSD 别名分析使用实际编码矩阵投影/SVD，提供完整可导出别名矩阵与关系表；热图仅显示最多 64 个非零项。 | 结果描述矩阵可估计性，不扩展为因果结论。 |
| RSM-009 | 混料预测与已选最优点显示 90%、95%、99% 均值置信区间和单次观测预测区间。 | 区间不校正搜索最优点造成的选择不确定性；模型不可估、无正误差自由度或无有效误差方差时区间不可用。 |
| FAC-008 | 两水平全因子新增单次平衡混杂区组设计，验证 GF(2) 生成元并展示区组与效应混杂。 | 2–6 个连续因子；无中心点、重复区组或增补。 |
| FAC-015 | 两水平及一般全因子可选 Type III 平方和；Type I 仍为默认。非平衡/缺失响应按可估计性标注。 | Split-Plot 不提供 Type III 选项；不可估项不产生可误读的检验。 |
| SCR-002 | DSD 增加 2–4 个二水平分类因子与按分类组合添加的中心点；保留旧设计范围和 Schema v5。 | 新增范围为 4–12 个连续因子、2–4 个分类因子；分类中心点数须为 `2^c` 的倍数。旧 1 分类因子路径与旧 4+2 案例保留。 |
| FAC-010 | Split-Plot 从既有范围扩展至 2–8 个因子；可含 1–3 个整区因子和二水平分类因子，并维持完整平衡区组分析。 | 至少 1 个子区因子；不支持非平衡分析或 REML。 |

## 验证证据

- 使用项目 `.venv` 的非 GUI DOE 测试：1389 passed、12 warnings、0 failed。命令按 `rg --files tests` 收集 `test_doe_*.py`，排除 `_gui`/`gui` 后运行 `pytest -q --tb=short`。
- 独立统计核对：SCR-003 的 AICc/BIC 与 statsmodels OLS `info_criteria` 最大绝对差均为 0（AICc 45.7621140342059，BIC 45.39859400044857）；SCR-007 覆盖 PB 精确别名 −1/3 与 PB32 完全别名 1；RSM-009 使用独立有理数/高斯消元参考核对区间；FAC-008 覆盖生成元、平衡分区与效应混杂；FAC-015 以 SVD 投影和删项秩差计算 Type III 并保持平衡情形 Type I 行为；SCR-002 精确枚举以 Bareiss 整数行列式选取，与独立 slogdet 和 Fraction 并列参考核对；FAC-010 的 8 因子裂区使用独立 NumPy 投影核对。
- GUI 定向验证：筛选 GUI DSD 过滤组 97 passed，PB 过滤组 17 passed、容量组 5 passed。运行数/因子数过滤命令跨六个进程报告 215 passed；过滤器按节点 ID 中的数字子串匹配，存在重叠，去重后覆盖该参数网格的 200 个用例。其余如 `test_doe_gui.py` 7、混料 GUI 10、一般全因子 Type III GUI 1、裂区相关 GUI/测试 62 passed 均为既有同快照证据。
- 所有改动的 Python 源码与测试通过项目解释器 `py_compile`；`git diff --check` 通过。保留 `doe_screening_analysis.py` 的既有 CRLF 转换警告。

## S1/S2 与尚未验证事项

- S1：本次实现与审查未发现已知 S1 缺陷。
- SCR-003 最终定向：`tests/test_doe_scr003_stepwise.py` 8 passed，相关 DSD Stepwise 回归 `tests/test_doe_dsd_stepwise.py` 18 passed。新增 Backward 秩亏案例以 13 行、rank=12、残差 df=1 的矩阵验证停止：当唯一非强制项是零新增秩别名时返回 `initial_model_rank_deficient`；放开可估计的 F1² 后先以 p>0.99 删除该项，再因仅剩秩亏别名而返回 `rank_deficiency`。另以独立 OLS 比较两个 BIC 候选：初始 rank=11/df=2 的 BIC 为 125.6563132448，F5² 选项为 34.3274525059，F6² 选项为 128.1743618354；两候选各自均可在 rank=12/df=1 计算，F5² 被选并成为最终模型，随后以 `residual_df_limit` 停止。BIC 未套用 AICc 的 df 限制。
- Screening GUI 共收集 320 个节点。此前成功的 DSD/PB/容量/参数网格分组按节点 ID 去重覆盖 319 个；唯一未覆盖项 `test_backward_gui_explains_saturated_default_candidate_model` 已在独立 pytest 进程中 1 passed。现 320/320 个唯一节点均有成功的分组或独立执行结果，无需整文件聚合重跑。
- 原聚合运行的两项失败没有保存节点名或 traceback；`.pytest_cache/v/cache/lastfailed` 中也没有 Screening GUI 条目，因此不能把那两项准确归因或原样复现。当前所有 320 个节点均在分组/单项进程中通过，没有复现确定的 GUI 行为失败。已记录的 `0x80000003` 是 Windows Tk 原生进程异常，与 pytest assertion 失败不同；由于缺少失败节点及崩溃前完整日志，无法证明原两项失败属于状态污染，也无法确定原生异常的触发条件。
- P2-6A 最终验收：七项功能的实现与既有测试证据仍有效；本次补修只增加 SCR-003 定向测试并更新记录，没有改生产代码。Schema v5、默认 F 选择和设计保存/重开兼容未变；同代码快照的原有 1389 项非 GUI DOE 回归结果予以复用，本次未重跑。无确定统计计算错误，也无未解决的可复现 GUI 功能失败。
- 未与 Minitab 22 输出做本轮数值 parity 验证。混料最优点区间、非平衡/REML Split-Plot 及范围外 DSD 配置均不在本次支持范围。

## 方法依据

- [Minitab 逐步回归方法](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/regression/how-to/fit-regression-model/perform-the-analysis/perform-stepwise-regression/)；[Minitab 拟合优度公式](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/regression/how-to/fit-regression-model/methods-and-formulas/goodness-of-fit-statistics/)；[statsmodels OLS 信息准则](https://www.statsmodels.org/dev/generated/statsmodels.regression.linear_model.OLSResults.info_criteria.html)。这些用于方法/参数约定核对，不构成本轮 Minitab 22 产品输出 parity。
- 多分类 DSD 增补范围参考 [Jones & Nachtsheim (2013)](https://www.jmp.com/content/dam/jmp/documents/en/white-papers/dsd-with-added-two-level-categorical-factors.pdf)，本实现对支持范围内的分类水平组合穷举并以独立行列式计算核对。

## Git 与文件边界

- 分支仍为 `main`；P2-6 代码、测试、记忆和报告修改保持未提交。本补修未改生产代码，也没有创建提交、推送或发布。
- `Out/p5_function_gap_closure/` 是已有用户未跟踪材料，本次保持未修改。
