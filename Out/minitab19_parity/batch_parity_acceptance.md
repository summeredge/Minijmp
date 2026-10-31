# MiniJMP × Minitab 19 DOE 批量数值对标验收

**总状态：PARTIAL**

最终批量复现按 Taguchi → Mixture → BBD → PB → Split-Plot 顺序执行；不重跑既有 2² 全因子及 CCD 案例。

Minitab：19.1.0.1；解释器：C:\Users\shaoy\Documents\Minijmp\.venv\Scripts\python.exe。

## 五阶段及逐案例结果

| 阶段 | 案例 | 状态 | 唯一比较项 / 原始行 | PASS / FAIL / N/A / UNSUPPORTED（唯一） | DIRECT / DERIVED / DISPLAY（唯一） | 最大绝对误差及指标 |
|---|---|---:|---:|---:|---:|---|
| Taguchi | TAG-L8 | PARTIAL | 254 / 302 | 228 / 0 / 25 / 1 | 189 / 38 / 20 | 1.136868377e-13 (anova / 合计 / SS, run l8) |
| Taguchi | TAG-L9 | PARTIAL | 246 / 300 | 245 / 0 / 0 / 1 | 207 / 32 / 23 | 0.003846153846 (anova / P_C / f, run l9) |
| Mixture | MIX-3COMP | PASS | 253 / 253 | 247 / 0 / 6 / 0 | 174 / 61 / 18 | 0.0004470965076 (prediction_display / P2 / ci_high, run MIX-SL2) |
| BBD | BBD-3FACT | PASS | 356 / 356 | 356 / 0 / 0 / 0 | 268 / 88 / 0 | 2.667945864e-10 (prediction / P3 / pi_low, run 1) |
| PB | PB-12RUN | PASS | 475 / 475 | 475 / 0 / 0 / 0 | 224 / 251 / 0 | 1.98951966e-13 (main_effect / A / f, run 1) |
| Split-Plot | SP-2FACT-3BLOCK | PASS | 121 / 121 | 120 / 0 / 1 / 0 | 76 / 45 / 0 | 1.136868377e-13 (treatment_effect / B / f, run 1) |

## 汇总

- 案例数：6；批次状态：PARTIAL。
- 汇总：唯一比较项 1705，明细原始行 1807；Taguchi 中 102 条相同的均值比较按 `(case, section, term, statistic)` 去重后只计一次。
- 比较结果：PASS 1671 / FAIL 0 / N/A 32 / UNSUPPORTED 2。
- Minitab 证据来源（唯一比较项）：DIRECT 1138 / DERIVED 515 / DISPLAY 61。
- 上一版 1636 PASS 的批次总数含上述 102 条重复均值项；按本轮唯一键口径折算为 1534 PASS，再由本轮 Taguchi 证据更新。
- 全批最大绝对误差：0.003846153846，Taguchi / TAG-L9 / anova / P_C / f。
- COM 清理：每个阶段退出后均检查 Mtb.exe；逐案结果和 PID 见 summary CSV，执行输出见 batch_parity_rerun.log。

## 统计差异与方法边界

- 数值 FAIL 为 0。Taguchi 调整型 Nominal-is-best 已由 Minitab 19.1.0.1 `ROBUST NOMTWO; ADJUSTED` 直接输出并通过；目前两项 UNSUPPORTED 仅说明 `OAPREDICT` 不提供 CI/PI 存储。等价分类模型经 `REGRESS` + `PREDICT` 直接比较通过；L8 的 MSE 为零，区间数值比较为 N/A。具体命令和回传见 Taguchi 阶段报告及 raw 文件。
- Taguchi 与 Mixture 的最大误差来自 Minitab 报表显示精度；其余阶段最大误差处于浮点计算精度范围。Mixture 的预测区间高精度值按报告记录为 DERIVED。
- PB 未把别名结果冒称 Minitab 原生输出；设计列相关与交互投影按固定矩阵独立核验。
- Split-Plot 采用两因子、3 区组的平衡最小结构；A 使用整区误差（df=2），B 与 A×B 使用子区误差（df=4）。Minitab WRESIDUALS 与 RESIDUALS 分别读取整区、子区残差；分层平方和和 F/P 依据高精度固定响应独立重建。未比较随机区组方差分量、REML 或非平衡设计。
- 本轮修正的脚本兼容点：Minitab 19 实际接受 WPREPLICATES；自动生成的整区因子列名包含 [HTC]；裂区残差需要分别读取 WRESIDUALS 与 RESIDUALS。已纳入最终复现脚本和命令。

## 验收结论

本批次 0 项 FAIL。调整型 Nominal-is-best 已获 Minitab DIRECT 输出；Taguchi L9 的等价分类均值模型 95% CI/PI 通过 DIRECT 比较，L8 因 MSE 为 0 标 N/A。两项 UNSUPPORTED 只表示 Taguchi 专用 `OAPREDICT` 不存储 CI/PI；其余等价模型区间有原生 Minitab 结果。其余四个 DOE 家族保持 PASS。

## 证据位置

- 各阶段输入、Session Commands、Minitab 原始输出、MiniJMP/Minitab JSON、比较 CSV 与阶段报告均保存在本目录。
- 批量复现命令输出：batch_parity_rerun.log。
- 批量逐案例汇总：batch_parity_summary.csv。
