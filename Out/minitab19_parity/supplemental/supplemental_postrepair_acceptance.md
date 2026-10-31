# MiniJMP × Minitab 19 supplemental DOE 修复后当前验收归档

日期：2026-10-31（Asia/Shanghai）  
性质：**修复后离线重组归档**。本文件和 `supplemental_postrepair_summary.csv` 读取既有原始比较 CSV，并仅替换 Binary Logistic 原 16 条 FAIL 对应的第二阶段修复后值；没有再次执行 Minitab/COM，也不改写任何原始快照。

## 结论

|范围|唯一比较项|PASS|FAIL|N/A|UNSUPPORTED|
|---|---:|---:|---:|---:|---:|
|七项 supplemental 总计|2935|2903|4|23|5|
|Binary Logistic（原 195 项）|195|189|4|2|0|

原始七项快照为 2891 PASS、16 FAIL、23 N/A、5 UNSUPPORTED；Binary 原始为 177 PASS、16 FAIL、2 N/A。修复后只发生 16 条 Binary FAIL 的值/状态更新：12 条变为 PASS，4 条保留 FAIL。四个真实剩余 FAIL 为 `BIN-RSM` 的 coefficient `wald_z`：`A`、`A²`、`B²`、`A*C`。

稳定键为 `(case_id, section, term, statistic)`。输入总行数 2941，去重后 2935；6 个重复键的值一致，冲突为 0。生成脚本为 [`build_postrepair_archive.py`](build_postrepair_archive.py)，逐案例汇总为 [`supplemental_postrepair_summary.csv`](supplemental_postrepair_summary.csv)，逐项结果为 [`supplemental_postrepair_comparisons.csv`](supplemental_postrepair_comparisons.csv)。

## 证据入口

七项原始输入、命令、Minitab raw、双方 JSON、比较和专项报告仍保留在原目录：

- [DSD](dsd/acceptance.md)、[General Factorial](general_factorial/acceptance.md)、[Foldover](foldover/acceptance.md)
- [Binary Logistic 原始验收](binary/acceptance.md)、[Binary Fisher 修复验收](binary/fisher_diagnosis/repair_acceptance.md)、[M2 调查](binary/fisher_diagnosis/m2_investigation/m2_investigation.md)
- [Optimal](optimal/acceptance.md)、[Dynamic Taguchi](taguchi_dynamic/acceptance.md)、[Mixture 独立案例](mixture_extended/acceptance.md)、[Mixture 联合案例](mixture_extended/mixture_v2_acceptance_report.md)
- [原始总体快照](supplemental_acceptance.md)、[原始逐案例汇总](supplemental_summary.csv)
- [八案冻结基线入口](../reference_baseline_acceptance.md)、[冻结 manifest](../reference_baseline_manifest.csv)

八案冻结基线保持 2559 PASS、0 FAIL、44 N/A、2 UNSUPPORTED。其 manifest、原始 Minitab 输出、比较 CSV 和特征矩阵未被本归档替换。

## Binary 修复与 M2 边界

第二阶段修复让 `fit_grouped_binomial()` 根据最终拟合概率与 trials 计算 Fisher 协方差，并由同一协方差输出 SE、Wald z/p 与 `covariance_array`；生产代码和定向 72 项测试已在父提交中完成。修复后离线结果不是再次运行 Minitab 的结果，修复值来自当前 MiniJMP 重放与冻结 Minitab JSON 的逐项比较。

第三阶段 M2 调查确认 M1/X、FITS 与模型矩阵对齐；四种普通双精度求解器差异约 `5.204170427930421e-17`，不足以解释 M2 与终点 Fisher 的最大差 `1.535865375851264e-10`。前态权重有数值接近迹象，但没有 Minitab 逐轮权重证据，不能归因其内部权重时点；四个 Wald z FAIL 和 `1e-9` 容差保留，根因未知。Minitab 19 的 MIXREG/SLDESIGN 组合限制、Mixture 独立/联合模型空间差异、N/A 与 UNSUPPORTED 边界均沿用原始报告。

## 范围和限制

本归档只覆盖七项代表性案例，不扩展 DOE 功能矩阵，也不声称 GEN-013 unknown 或其他未覆盖功能组合已完成。`supplemental_summary.csv`、`supplemental_acceptance.md`、七项原始证据及 Binary Fisher/M2 历史原件保持原样；本目录新增文件是版本化归档入口、逐项汇总和其生成脚本。

## 验收记录

- 运行 `.venv\Scripts\python.exe Out/minitab19_parity\supplemental\build_postrepair_archive.py`：2935 唯一项，2903/4/23/5；Binary 189/4/2。
- 已检查所有本报告相对链接目标存在、稳定键无冲突、总计与逐案例汇总一致。
- 已核对冻结基线及本报告列出的历史原件 SHA-256 未改变；未启动 Minitab/COM，未重复 pytest。
