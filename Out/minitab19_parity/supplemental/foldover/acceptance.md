# 正规部分因子与 PB Foldover 对标验收

状态：**PASS**

## 案例

- `FOLD-REG`：3 因子、4-run 正规分数设计，C=AB；2 次重复后单因子 A 折叠，运行数 8→16。
- `FOLD-PB`：PB12、11 个因子，全因子折叠，运行数 12→24。
- 行序按因子设置、重复号及 BASE/FOLD1 批次映射；新增运行按翻转因子回链至来源运行。
- Minitab 以 `FFDESIGN`/`PBDESIGN` 生成原设计，以 `MDESIGN; FOLD` 执行折叠；模型使用 `FFACTORIAL` 或 `SCREEN` 主效应项。
- PB 的主效应模型不含二因子交互；其误差项包含未建模交互，结果按固定模型解释。PB12 基线饱和，常规推断 N/A。

## 比较结果

唯一比较项：587；PASS/FAIL/N/A/UNSUPPORTED：584/0/3/0。
N/A 项为 PB12 基线无残差自由度，以及两个案例中的截距效应（截距不是因子效应）。
Minitab 来源计数（可重叠）：DIRECT/DERIVED/DISPLAY：416/130/0。

## 证据

- 固定响应与运行映射见两份 `*_input.csv`；实际命令、COM 输出及工作表值分别见 `session_commands.txt`、`minitab_raw.txt` 和两侧 JSON。
- 逐项数值比较见 `comparison.csv`。
