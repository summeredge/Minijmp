# MiniJMP V1.0 beta2 — Minitab 19 数值基线

日期：2026-11-02（Asia/Shanghai）

## 源码与环境

- 对应源码 Commit：本记录所在的 beta2 冻结提交；完成构建验收后，本地 annotated Tag `v1.0.0-beta.2` 指向该提交。完整 SHA 同时记录在 Windows 包的 `BUILD-INFO.txt` 和最终验收报告中。
- 冻结起点：`9485e848a09c87ffd3b4056289db18be34a2b65a`（当时 `main` 与 `origin/main` 一致）。
- Minitab：19.1.0.1。第一、二阶段均保存了 COM 版本/路径、Session 命令、原始输出及重复性摘要；未重新运行 Minitab COM。
- Python：项目 `.venv`，Python 3.11.9 x64；复核环境含 NumPy 2.4.6、pandas 3.0.6、SciPy 1.15.3、statsmodels 0.15.0。第三阶段离线脚本使用固定第二阶段输入和归档原始存储数据。
- DOE 数值基线位于既有 `Out/minitab19_parity/` 与 `docs/doe-minitab/`；本任务未重跑或改写该历史结果。

## 固定案例结果

- 第一阶段：8 个案例、43 项指标，40 PASS、2 METHOD_DIFF、1 UNSUPPORTED。
- 第二阶段：10 个固定案例、909 项指标；初次严格比较为 886 PASS、10 FAIL、13 METHOD_DIFF。两次 Minitab 运行、输入、存储结果及比较结果有重复性/SHA 记录。
- 第三阶段：基于独立数值参考复核后最终为 **896 PASS、0 FAIL、13 METHOD_DIFF、0 UNSUPPORTED、0 NOT_RUN**；98 项独立参考验证。离线复核连续运行两次，输出与归档文件 SHA-256 一致，见同目录 `phase3/repeatability_check.txt`。
- 13 项 METHOD_DIFF 保留了方法口径差异：CAP-01/CAP-03 的 `d2(2)` 精确值与 Minitab 表值不同；CAP-04 对数标准差的分母不同（ddof=0 与 ddof=1）。CAP-05 的 9 项初始 FAIL 经 Weibull 独立 MLE 参考复核为数值等价；CAP-03 上尾 PPM 使用独立 `erfc` 参考及该指标专属容差。
- 本次没有修改生产统计算法。以上判断只适用于所列固定输入、Minitab 19.1.0.1 和归档的指标/容差；不表示所有 MiniJMP 统计、DOE、SPC、过程能力或 GRR 场景均通过。

## 离线证据

- 第一阶段：`verify_statistics_minitab19.py`、`case_inputs.json`、`feature_matrix.csv`、`minitab_metadata.json`、`minitab_session_commands.txt`、`minitab_raw_outputs.txt`、`minijmp_results.json`、`minitab_results.json`、`comparison.csv`、`summary.csv`、`repeatability_check.txt`。
- 第二阶段：`phase2/verify_statistics_minitab19_phase2.py`、固定输入、Session 命令、Minitab 原始输出、`comparison.csv`、`summary.csv`、`repeatability_check.txt`。
- 第三阶段：`phase3/verify_statistics_minitab19_phase3.py`、最终 `comparison.csv`、`summary.csv`、`verification.csv`、`repeatability_check.txt`。
- 可离线重算第三阶段最终判定；重取第一、二阶段 Minitab 原始数值需有 Windows、Minitab 19 COM 和相应许可证的环境。
