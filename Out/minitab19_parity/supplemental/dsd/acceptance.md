# DSD 连续因子与逐步选模对标验收

状态：**PASS**

## 固定案例

- Minitab：19.1.0.1；官方 Session Commands：`DSDESIGN`、`SCREEN`。
- 设计：6 个连续因子、两次重复、13 个基础点，共 26 行；编码为 -1/0/+1。
- 响应：固定模型含 6 个主效应、F1²/F2²/F3² 和 F1×F2；同一点两次观测加入相反的固定误差，保留非零纯误差。
- 二阶完整候选矩阵有 28 列；其秩与 28 不同表示部分交互不能在同一完整模型中单独估计。
- 选模：STEPWISE，进入/移除 α=0.15，强层级，每步单项进出；候选项 10 个。

## 对标结果

唯一比较项：1341；PASS/FAIL/N/A/UNSUPPORTED：1341/0/0/0。
来源计数（可重叠）：DIRECT/DERIVED/DISPLAY：508/803/0。
MiniJMP 与 Minitab 的运行序允许不同；按因子点和重复出现次序映射。

## 实际 Minitab Session Commands

详见 `session_commands.txt`；原始 Outputs/OutputDocument 见 `minitab_raw.txt`。

## 证据文件

- `dsd_input.csv`：固定响应及其设计点映射。
- `minitab_results.json`、`minijmp_results.json`：原生与生产 API 高精度结果。
- `comparison.csv`：按 (case_id, section, term, statistic) 去重的逐项结果。
