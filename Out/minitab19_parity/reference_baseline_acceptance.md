# MiniJMP × Minitab 19 固定 DOE 参考基线验收

**状态：完成；Minitab 19 DOE 自动对标阶段关闭。** 本轮使用本机 Minitab 19.1.0.1；未启动或验证 Minitab 22。未修改 MiniJMP 生产统计代码。

## 八个固定案例

| 案例 | 唯一比较 PASS / FAIL / N/A / UNSUPPORTED | 结果 |
|---|---:|---|
| DOE-2X2 | 263 / 0 / 5 / 0 | PASS |
| DOE-CCD | 625 / 0 / 7 / 0 | PASS |
| TAG-L8 | 228 / 0 / 25 / 1 | PARTIAL |
| TAG-L9 | 245 / 0 / 0 / 1 | PARTIAL |
| MIX-3COMP | 247 / 0 / 6 / 0 | PASS |
| BBD-3FACT | 356 / 0 / 0 / 0 | PASS |
| PB-12RUN | 475 / 0 / 0 / 0 | PASS |
| SP-2FACT-3BLOCK | 120 / 0 / 1 / 0 | PASS |

离线结果共 3,070 条明细，按 `(case_id, section, term, statistic)` 去重后为 **2,605 项：2,559 PASS、0 FAIL、44 N/A、2 UNSUPPORTED**。重复项包括两次 Minitab 运行中重复的统计比较，以及 L8/L9 按四类 S/N 展开的相同均值比较；所有明细仍保存在离线结果 CSV 中。

六案例批次不含独立的 2² 和 CCD 案例，唯一统计量为 **1,705 项：1,671 PASS、0 FAIL、32 N/A、2 UNSUPPORTED**。Minitab 来源标签（按唯一统计量计）为 DIRECT 1,138、DERIVED 515、DISPLAY 61；这三类是非互斥标签。2² 与 CCD 的两次原生运行另行去重报告。

八案例离线结果中，DIRECT / DERIVED / DISPLAY 标签计数为 **1,655 / 625 / 61**（非互斥）；共享输入与 MiniJMP 复跑一致性行保留为各自来源，不混入这三类。

原批次汇总的 1,636 PASS 包含 102 条重复的 Taguchi 均值行。按唯一统计量口径，旧基线为 1,534 PASS；本轮加入 Taguchi 证据后，六案例批次为 1,671 PASS。

## Taguchi 两项遗留核查

### 调整型 Nominal-is-best

Minitab 定义中，`NOMONE` 仅使用标准差；`NOMTWO` 使用均值与标准差。调整型 Nominal-is-best (I) 为 `10*log10((x̄² - s²/n)/s²)`，其中 `s²` 是重复观测的样本方差。

本机 Minitab 19.1.0.1 接受 `ROBUST ... NOMTWO; ADJUSTED; SNRATIO C...`。COM 回读 L8 的 8 个、L9 的 9 个 S/N 值；17 项均与独立公式和 MiniJMP `analyze_static(adjusted=True)` 在 1e-9 容差内一致。因子水平响应均值、Delta、Rank 及最佳水平也通过比较。公式定义见 [Minitab Taguchi Methods and formulas](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/taguchi/analyze-taguchi-design/methods-and-formulas/methods-and-formulas/)；实际命令与输出保存在 Taguchi Session Commands、raw 和 JSON 中。

### 95% 均值置信区间

本机 `OAPREDICT` 不接受 `PSEFITS` / `CLIMITS` / `PLIMITS` 存储；原始返回提示 `PSEF` 子命令无效。随后对相同组合均值拟合相同分类模型，使用 Minitab `REGRESS` 的 BINARY treatment coding、相同参考水平及模型项，并由 `PREDICT C...` 直接回读 SE Fit、95% 均值 CI 和单次观测 PI。Minitab 回读矩阵与 MiniJMP model matrix 完全一致，误差自由度也一致。

L9 模型误差自由度为 2、MSE 为 3.25。观察组合 `(1,1,1)`、可估计的非设计组合 `(1,1,2)` 和最佳 S/N 设置 `(2,1,2)` 的均值、SE Fit、95% 均值 CI 与 PI 均通过 DIRECT 比较；最大绝对误差为 `4.79190021e-11`。均值 CI 与观测 PI 分别保存及比较。

L8 的误差自由度为 2，但 SSE/MSE 为 0。Minitab 输出零宽区间，MiniJMP 将区间标为不可用；因此三个预测点的 SE/CI/PI 比较标 N/A，均值预测仍通过。两项 UNSUPPORTED 只记录 Taguchi 专用 `OAPREDICT` 的区间存储限制，等价回归模型路径已通过 L9 原生比较。

## 离线基线与完整性

- [reference_baseline_manifest.csv](reference_baseline_manifest.csv) 为八个案例索引，记录模型、版本、容差、逐案预期原始行数与唯一状态计数，以及逐案证据、批次汇总/报告、离线结果和本验收报告的 SHA-256。
- [verify_reference_baseline.py](verify_reference_baseline.py) 校验 manifest 哈希、逐案原始行数和唯一状态计数，调用已有 MiniJMP API 与比较函数，并将新计算生成的离线 CSV 与已归档结果摘要比对；不覆盖固定结果。默认运行不会启动 Minitab；2²/CCD 两次原生结果及 MiniJMP 快照仍进行复跑一致性核对。
- [reference_baseline_offline_results.csv](reference_baseline_offline_results.csv) 保存 3,070 条离线明细；唯一统计量 2,605 项。八案例运行成功，0 项 FAIL；运行期间 Minitab COM 未启动，输入及参考文件哈希保持不变。
- 六案例汇总与 Taguchi 明细见 [batch_parity_acceptance.md](batch_parity_acceptance.md)、[batch_parity_summary.csv](batch_parity_summary.csv) 和 [doe_taguchi_acceptance_report.md](doe_taguchi_acceptance_report.md)。

验证命令（项目 `.venv` Python 3.11.9）：

```powershell
$python = (Resolve-Path ".venv\Scripts\python.exe").Path
& $python -X utf8 "Out\minitab19_parity\verify_reference_baseline.py" --self-check
& $python -X utf8 "Out\minitab19_parity\verify_reference_baseline.py"
```

## 版本边界与交付

所有本地原生数值证据来自 Minitab 19.1.0.1。Minitab 22 未在本机运行，本基线不对 22 的 COM、Session Commands 或结果格式作兼容性声明。DOE 生产算法未修改；固定参考不依赖后续启动 Minitab。

Minitab 19 的两项 Taguchi 遗留均有明确结论：调整型 Nominal-is-best 为 DIRECT PASS；均值 CI 在 L9 为 DIRECT PASS，在 L8 因零 MSE 为 N/A。无数值 FAIL，基线可离线复验，满足本轮关闭条件。
