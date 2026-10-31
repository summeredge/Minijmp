# 一般全因子与多水平 ANOVA 对标验收

状态：**PASS**

## 案例与方法

- `GFF-2X3`：2×3 分类全因子、每个组合两次独立重复；Minitab 使用 `FDESIGN`/`GFACTORIAL`。
- `GFF-TYPEIII`：2×3 全因子三次重复，固定一个缺失响应；使用完整 A、B、A×B 效应组。
- MiniJMP sum-to-zero contrast basis 与 Minitab `XMATRIX` 先求线性变换，再比较对应系数和模型空间。
- Minitab 输出称 Adjusted SS；Type III parity 按删去完整效应列组重拟合核算。
- Minitab 存储残差为 Y−Fit，与 MiniJMP 定义一致；原生工作表值直接比较。

## 数值结果

唯一比较项：319；PASS/FAIL/N/A/UNSUPPORTED：318/0/1/0。
来源计数（可重叠）：DIRECT/DERIVED/DISPLAY：120/97/0。

## Minitab 19 Session Commands

实际命令见 `session_commands.txt`，原始 Outputs/OutputDocument 见 `minitab_raw.txt`。

## 证据文件

- `gff_2x3_input.csv`、`gff_typeiii_input.csv`：设计点、水平映射、重复和响应。
- `minijmp_results.json`、`minitab_results.json`：生产 API 与原生高精度结果。
- `comparison.csv`：稳定键去重的逐项数值比较。
