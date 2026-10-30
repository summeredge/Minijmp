# MiniJMP P2-5 DOE 自动化功能覆盖与统计正确性综合验收

日期：2026-10-30  
仓库：C:\Users\shaoy\Documents\Minijmp  
代码基线：main / 512f03a1e4fb8554748633fec086024375e4e4de

## 验收结论

**本地自动化验收：通过（存在已知范围缺口）。Minitab 22 全功能 parity：未验证，未达到全功能产品对照验收。**

本轮取消新增人工逐案例导出，改用独立统计参考与已有 BBD、DSD-S01、PB12 产品文件。DOE 自动化 1201 项、Tk DOE 工作流 141 项、菜单 66 项，共 **1408 passed、69 warnings、0 failed**。没有测试证实的计算错误或 GUI 工作流缺陷。

不得将 partial 提升为完整支持。功能矩阵的当前状态：

| 家族 | 总数 | implemented | partial | unknown | excluded |
|---|---:|---:|---:|---:|---:|
| screening | 7 | 2 | 5 | 0 | 0 |
| factorial | 19 | 12 | 7 | 0 | 0 |
| response_surface | 16 | 15 | 1 | 0 | 0 |
| mixture | 13 | 12 | 1 | 0 | 0 |
| taguchi | 11 | 8 | 3 | 0 | 0 |
| general | 14 | 9 | 2 | 2 | 1 |
| **总计** | **80** | **58** | **19** | **2** | **1** |

19 项 partial：SCR-001/002/003/006/007、FAC-002/008/010/012/014/015/019、RSM-009、MIX-005、TAG-005/008/009、GEN-004/006。未知：GEN-012/013。GEN-014 保持 excluded。

## 功能与测试判定

- **本地支持范围通过**：当前矩阵标为 implemented 的功能，其引用自动化测试在本轮通过；逐 Feature ID 的菜单入口族、实现路径、参数范围、输出/分析项、测试结果和未覆盖项见 feature-coverage-matrix.csv。
- **部分实现**：19 项仍为 partial；关联测试仅证明其已实现子范围，缺少范围见矩阵和缺陷登记表。
- **未知**：GEN-012/013 不计入通过；GEN-014 为显式排除。
- **筛选 GUI**：PB 生成/分析和 DSD mixed 生成/预览/持久化代表用例通过；test_doe_screening_gui.py 全套没有运行到有效汇总。
- **范围需复核**：SCR-005、FAC-016、RSM-001/006/010/011、TAG-003/004、GEN-002/010 的矩阵范围是有限家族/选项；本轮不据局部测试称其完整覆盖 Minitab。
- **证据表问题**：feature-matrix.csv 的 GEN-004 行字段粘连；审计副本恢复映射，源 CSV 未修改。TAG-005 的矩阵范围与案例清单不一致，仍保持 partial。

## 统计误差摘要

- 2² 重复因子模型：statsmodels OLS 与 MiniJMP 最大绝对误差约 1.42e−14；解析残差逐项一致；rank=4、残差 df=4、SSE=8 精确一致。
- 五类静态 Taguchi S/N：独立公式最大误差 0 dB。
- DSD 五条选择轨迹：enter/remove、最终秩/df 精确一致；F 最大绝对差 1.18e−8（该点相对 3.97e−14；全批 F 最大相对差 1.14e−13）；p 最大绝对差 1.78e−15；最终系数最大差 2.13e−14。
- Mixture 72×15：rank/df=15/57；系数最大差 2.13e−14、SSE 差 8.06e−12、条件数相对差 5.86e−14。
- mixture max/min/target 固定目标误差 4.44e−16、8.88e−16、5.22e−9；约束残差最大 2.78e−17。没有证明连续可行域全局最优。
- 详细误差、独立性边界、边界输入和产品哈希见 independent-statistical-validation.md。

## Minitab 产品证据状态

已有产品输出对应 4 个 Feature ID：SCR-001、SCR-003、FAC-012、RSM-002。其余 **76/80 项没有对应产品输出**。

- PB12 的 12×11 点矩阵和 24 行全因子折叠符号变化与固定参考精确一致。
- DSD-S01 RTF 显示 F1→F2 与格式化系数一致；仅有显示精度，不能证明内部全精度。
- BBD 五个设置的点/区组多重集一致；标准序差异分类为 CONVENTION_DIFFERENCE。
- 其他 DSD 轨迹、PB 其他运行数/单因子折叠、Taguchi/Mixture 输出以及大多数 Feature 的产品数值 parity 未验证。

## 分类及严重度

S1 表示结果正确性/数据完整性风险；S2 为重要功能/parity 缺口；S3 为边界、约定、展示或范围记录问题；INFO 为已知限制/证据说明。

- CALCULATION_DEFECT：0 条。
- FUNCTION_MISSING：0 条已确认；不包含 partial 中明确列出的缺失子范围。
- FUNCTION_PARTIAL：19 条，逐项列出。
- GUI_DEFECT：0 条已确认。
- CONVENTION_DIFFERENCE：1 条，BBD 标准序不同。
- PRESENTATION_DIFFERENCE：1 条，测试环境中文 glyph 警告。
- UNVERIFIED：9 条；缺陷登记表共 30 条记录，其中 19 条为已知 partial，另含差异及范围记录。

本轮确认计算缺陷 0、功能缺失 0、GUI 流程缺陷 0；不等于证明范围外功能正确。其余差异和证据不足逐项见 defect-register.csv。

## GUI 自动化边界

真实 Tk widget/workbook 集成已自动验证；没有 OS 键鼠桌面级 E2E、可见屏幕布局检查或人工抽检。抽检清单见 gui-workflow-test-results.md，本轮未执行。

## 范围与交付

- 未修改统计源码、测试、正式 P2-5 文档、feature-matrix.csv 或原始产品证据。
- 未生成新的 Minitab 输出；未提交、推送、调用 LRM 或自动 Handoff。
- 交付：feature-coverage-matrix.csv、independent-statistical-validation.md、gui-workflow-test-results.md、defect-register.csv、本报告和两份原始 pytest 日志。