# DOE Phase 2 P2-2B 验收跟踪

日期：2026-10-29
状态：本地验收完成，等待两个独立 Review；未运行全量 pytest。用户于 2026-10-29 明确授权在 Review verdict 产生前提交并推送；这不代表 Review 通过。

| 编号 | 验收范围 | 当前结论 | 本地证据 |
|---|---|---|---|
| P2B-ACC-01 | RSM 预测 Logit/概率、TermModel 行与拟合矩阵一致、GLM 系数协方差 | `LOCAL_PASS` | `predict_binary_probability()` 使用原 `fitted.cov_params()`；独立三因子手算 beta/V/x0；303 行 Star98 grouped GLM；verifier SHA-256 `9f421b5f7ba175af1a54c2cf98ce5714707b72220da21c9a84e0ba6893e41fda`；概率预测真实 Tk 路径通过。 |
| P2B-ACC-02 | 90/95/99 双侧与单侧 Wald CI、Delta SE、边界与错误协方差 | `LOCAL_PASS` | 独立手算 oracle 覆盖正/负 Logit、概率近 0/0.5/1、非对称区间、Logit 反变换与饱和；负方差容差/实质负方差分别验证；核心测试 70 passed，真实 Tk 下限显示与设置失效通过。 |
| P2B-ACC-03 | Maximize/Minimize/Target、概率与 desirability 语义、weight | `LOCAL_PASS` | `tests/test_doe_binary_optimize.py` 的解析 `eta=0.2+A-A²` 独立 oracle 覆盖极值/双目标根、三类 desirability 与 weight；Target 平方概率误差与 `1e-8` 达标判定。 |
| P2B-ACC-04 | 因子/类别约束、起点、搜索预算、不可达目标和全局最优声明 | `LOCAL_PASS` | 连续物理范围/固定值、非法起点、类别组合穷举/预算上限、矩阵一致性、区组拒绝、预算耗尽保留最佳点、未收敛状态、确定性并列和搜索中取消用例。每起点上限 100 次评价；多起点 L-BFGS-B 不声明连续域全局最优。 |
| P2B-ACC-05 | 点预测与 optimizer GUI、响应切换、快照失效、取消/关闭 | `LOCAL_PASS` | 真实 Tk 独立进程：概率窗口 5 条；优化窗口 10 条，覆盖预览/真实候选回算、不写回、数字类别水平、取消、子/父窗关闭、数据/元数据/响应列/工作表/源表删除时的清理，以及 `.dexpl` 重开复制后重新优化。P2B-REV-01 另验证两个入口随输入/来源失效同步禁用、合法重分析后恢复。H 原有 RSM 概率图与响应变化清理各 1 条通过。 |
| P2B-ACC-06 | `.dexpl` 保存重开复制、旧工作流/Schema/帮助集成 | `LOCAL_PASS` | 真实 Tk `.dexpl` 保存/重开/复制后重新分析与优化，预测概率、设置和快照一致；DOE Schema v5 未变。v1–v5 相关 schema/持久化、坏元数据加载隔离、帮助索引、RSM 连续 CI/PI、普通响应/混料优化及 G12 清单回归通过。 |

## 当前已执行验证

所有 Python 命令使用 `C:\Users\shaoy\Documents\Minijmp\.venv\Scripts\python.exe`（Python 3.11.9、NumPy 2.4.6、SciPy 1.15.3、statsmodels 0.15.0）。

- `tests/fixtures/doe_phase2_binary_reference/verify.py`：**931 项通过**；含独立 Newton scoring、手算 Wald、解析 optimizer 参考；GLM 303 行。
- `python -m pytest tests/test_doe_binary_probability.py tests/test_doe_binary_analysis.py -q --tb=short`：**70 passed**。
- `python -m pytest tests/test_doe_binary_optimize.py -q --tb=short`：**26 passed**；连续极值、目标根和分类固定设置分别与独立解析 oracle 比较。
- 本地核心交叉回归：`tests/test_doe_binary_analysis.py tests/test_doe_binary_probability.py tests/test_doe_binary_optimize.py tests/test_doe_h_reference.py tests/test_doe_predict.py tests/test_doe_rsm.py tests/test_doe_rsm_categorical.py tests/test_doe_rsm_diagnostics.py tests/test_doe_optimize.py tests/test_doe_mixture_optimize.py`：**206 passed, 9 warnings**（SciPy SLSQP 边界裁剪警告来自 Mixture 最优化）。
- `.dexpl`/Schema/文件保护：`tests/test_doe_persistence.py` **10 passed**；`tests/test_doe_schema_v2.py tests/test_doe_schema_e.py tests/test_doe_factorial_schema.py` **29 passed**；`tests/test_doe_schema_v3.py` **19 passed**；`tests/test_file_io.py` **45 passed**；`tests/test_doe_taguchi_persistence.py` **20 passed**。
- Help/矩阵：`tests/test_help_center.py` **13 passed**；`test_translation_inventory_matches_live_menus` **1 passed**；`test_help_operation_paths_match_live_menu_labels` **14 passed**；`tests/test_g12_inventory.py` **15 passed**。G12 首轮指出二元概率/优化 `StatTable` 位置缺失，登记两处后复测通过。
- 既有 GUI 回归另以独立进程执行：连续 optimizer BBD/CCD/来源/区组用例 **5 passed**；Mixture 完整 GUI lifecycle **1 passed, 4 warnings**；连续预测 CI/PI **1 passed**；H Factorial/DSD/RSM 二元与概率图相关用例 **3 passed**。
- `python -m pytest tests/test_doe_h_reference.py -q --tb=short`：**1 passed**。
- `python -m pytest tests/test_doe_h_lifecycle.py::test_h_binary_dsd_terms_and_rsm_probability_plot -q --tb=short`：**1 passed**。
- `python -m pytest tests/test_doe_h_lifecycle.py::test_h_binary_results_clear_after_source_response_changes -q --tb=short`：**1 passed**。
- 二元概率窗口真实 Tk 单用例/单进程：输入变化与来源失效、关闭和响应切换、元数据变化、工作表切换、数字类别水平 **5 × 1 passed**；H 已有 RSM 图形与响应变更测试分别再次运行 **1 passed**。
- 二元优化 GUI 真实 Tk 单用例/单进程：约束预览/实际候选回算/响应不写回、数字类别水平保型、取消与关闭、计算期间元数据/工作表/响应列/数据变化、删除来源表、关闭父分析窗、`.dexpl` 保存重开复制后重新分析/优化 **10 × 1 passed**。
- `python -m py_compile code/doe_binary_analysis.py code/doe_binary_dialog.py code/doe_optimize.py tests/test_doe_binary_probability.py tests/test_doe_binary_optimize.py tests/test_doe_h_lifecycle.py tests/fixtures/doe_phase2_binary_reference/build_reference.py tests/fixtures/doe_phase2_binary_reference/verify.py`：通过。
- `git diff --check` 对本轮代码、测试、fixture 与方法合同路径：通过。

这些是彼此独立运行的定向结果；没有运行全量 pytest。DOE Schema 保持 v5；不声明 Minitab 22 数值一致、连续域全局最优或新批次计数预测区间。两个验收单元本地证据已齐，但 Connector Review Goal 因 `pending_identity_expired` 未启动；不得将本地 `LOCAL_PASS` 当作独立 Review `APPROVE`。

## P2B-REV-01 Review ITERATE 修复（2026-10-29）

- 原因/修复：`code/doe_binary_dialog.py::BinaryAnalysisDialog._inputs_changed()` 清除拟合结果时遗漏禁用 `optimizer_button`。现与 `probability_button` 一起禁用；`analyze()` 的成功路径负责恢复两个按钮。优化子窗口原有 close/cancel/线程清理保持不变。
- 新增/扩展的真实 Tk 用例：`test_h_binary_rsm_buttons_follow_response_selection[events|trials]`；`test_h_binary_probability_window_invalidates_on_source_change[data|metadata|sheet]`。它们验证禁用、恢复来源并成功重分析；另对 optimizer 来源变化取消、DSD/Factorial 无优化按钮路径补充断言。
- 实际执行：上述 Tk 回归及 19 个直接相关既有 H/P2B Tk 节点按单节点独立进程串行运行，**24/24 passed**；`& '.venv\Scripts\python.exe' -m pytest tests/test_doe_binary_analysis.py tests/test_doe_binary_probability.py tests/test_doe_binary_optimize.py tests/test_doe_h_reference.py -q --tb=short` **97 passed**；`.venv` 下 `py_compile` 通过，`git diff --check` exit 0（仅 CRLF→LF 转换提示）。没有运行全量 pytest。
- 验收状态不变：P2B-ACC-01–06 为 `LOCAL_PASS`；`BINARY_PROBABILITY_INTERVAL` 与 `BINARY_RESPONSE_OPTIMIZER` 均保持 `READY_FOR_INDEPENDENT_REVIEW`，没有独立 APPROVE。未重提此前身份超时的 LRM Review Goal。
