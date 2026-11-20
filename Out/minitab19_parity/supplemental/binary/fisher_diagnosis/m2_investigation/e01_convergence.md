# E01 · Binary RSM Wald z 收敛设置对照

2026-11-20 · Minitab 19.1.0.1 · **未解决的数值差异**

## 原生对照

历史归档只有 `CTOLERANCE 1e-10`。本轮用项目 Python 3.11.9 和现有独立 COM worker，在两个新项目分别执行冻结的 `BBDESIGN` 和 `BRSREG`。唯一改动是将对照组的 `CTOLERANCE` 改为 `1e-12`。两个项目均回读相同的 14 行事件及试验计数、因子编码、运行顺序及 14×10 的 M1，秩为 10。原生报告显示最大迭代次数 200，未给出实际迭代次数、停止条件触发项或逐轮系数与权重。

`CTOLERANCE K` 用于设置迭代收敛准则。19.1.0.1 接受了两条命令，原生方法表分别显示公差 `1e-10` 和 `1e-12`。两份原生报告只有该设置行不同。方法表没有足够信息确定内部具体的判停量、阈值处理或保存 M2 的时点。 [Minitab 会话命令参考](https://support.minitab.com/en-us/minitab/media/pdfs/notranslate/session_commands.pdf)

直接存储的 β、FITS、SECOEFFICIENTS 和 XPWXINVERSE M2，在两次执行间逐元素相同，与历史原生基线也逐元素相同。两组 `sqrt(diag(M2))` 均精确等于存储 SE。全精度 Wald z 由存储 β 除以存储 SE 得出。 [原生命令、输入、矩阵及输出](e01_native_convergence.json)

## 独立 Fisher 检查

用对应原生 FITS 构造 `W = diag(n·p·(1−p))` 和 `I = XᵀWX`，复用现有诊断的 Cholesky 求解求得 `V = I⁻¹`。复用归档的 IRLS 权重候选，保持相同的行键和列顺序。

| 数值诊断 | 1e-10 | 1e-12 |
|---|---:|---:|
| M2 与终点 Fisher 的最大元素绝对差 | 1.535865375851264e-10 | 1.535865375851264e-10 |
| A*C 方差处 M2 − V | −1.535865375851264e-10 | −1.535865375851264e-10 |
| A*C 对应行和列的最大绝对差 | 1.535865375851264e-10 | 1.535865375851264e-10 |
| I·M2 − 单位矩阵的无穷范数 | 2.387860731966050e-8 | 2.387860731966050e-8 |
| 最近离线 IRLS 候选（第 4 权重状态）的最大元素绝对差 | 5.701877164865365e-11 | 5.701877164865365e-11 |

第 4 状态在两组中都比终点更接近 M2，但仍无法复现 M2。这个现象只说明该离线候选较近。现有原生输出不足以确定 Minitab 使用的权重时点、等效停止策略或其他内部实现细节。 [原离线调查](m2_investigation.md) · [两设置比较及全部候选](e01_comparison.csv)

## 固定容差判定

沿用冻结的绝对或相对容差满足其一即通过，`abs_tol = rel_tol = 1e-9`。以下值在两种原生设置下相同，MiniJMP 取自修复后冻结重放结果。

| 项 | MiniJMP z | Minitab z | 绝对误差 | 相对误差 | 状态 |
|---|---:|---:|---:|---:|---|
| A | 8.288218058530513 | 8.288218084140853 | 2.561034e-8 | 3.089969e-9 | FAIL |
| A² | 5.536396477063141 | 5.536396485458897 | 8.395756e-9 | 1.516466e-9 | FAIL |
| B² | −5.536396477063137 | −5.536396485458899 | 8.395761e-9 | 1.516467e-9 | FAIL |
| A*C | 5.571773172334398 | 5.571773199981684 | 2.764729e-8 | 4.962026e-9 | FAIL |

当前 MiniJMP 以最终概率构造 Fisher 协方差，符合分组二项 Logistic 的逆信息矩阵公式。现有证据未发现计算缺陷，生产代码保留。四项冻结判定保持 FAIL，E01 标记为**未解决的数值差异，现有证据不足以唯一归因**。 [生产实现](../../../../../../code/doe_binary_analysis.py) · [Fisher 修复后冻结比较](../repaired_comparison.csv)

## 重放

从仓库根目录运行。默认只读原生 JSON 和冻结证据，重新生成本轮比较 CSV。重新采集时指定一个新输出文件，现有 Minitab 进程会阻止 COM 启动。

```powershell
$python = (Resolve-Path '.venv\Scripts\python.exe').Path
$e01 = 'Out/minitab19_parity/supplemental/binary/fisher_diagnosis/m2_investigation/e01_convergence.py'
& $python -X utf8 $e01
& $python -X utf8 $e01 --capture "$env:TEMP\minijmp-e01-native-replay.json"
```
