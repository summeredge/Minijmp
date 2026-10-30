# DOE Phase 2 P4BC 独立参考夹具

本目录是独立数学参考数据，不导入 MiniJMP `code/`、生产模块或其他 verifier。生成器和 verifier 仅使用 Python 标准库。矩阵、输入行、期望统计量和完整来源说明冻结在 `reference.json` 与 `manifest.json`。

## 范围

- Taguchi：L8 mixed、官方 L16 mixed、L18 mixed 的矩阵、逐列频数、所有列对频数、平衡标记、规范矩阵 SHA-256 及数值/文本水平映射。
- 静态 S/N：smaller、larger、nominal-I、nominal-II 和 adjusted nominal-I；方差使用样本方差 `ddof=1`。零标准差对 smaller/larger 合法，对 nominal 及 adjusted nominal 无定义；larger 拒绝零响应，但负的非零响应仍在公式定义域内。
- 噪声试验：2 个两水平控制因子、一个两水平和一个三水平噪声因子、每个噪声条件 2 次重复。48 行对应 4 个控制组合 × 6 个真实噪声条件 × 2 次重复；每个控制组合有 12 个观测，并独立核验噪声条件均值极差与响应身份频数。
- 两阶段选择：加性主效应预测 S/N；先按阈值筛选，再按目标均值距离选出全部并列最优。不可达阈值拒绝且不降级；枚举预算为 20,000。
- Mixture：三组分 degree-2 lattice 的完整 Cartesian cross。C1 为两个两水平 process 因子（24 runs）；C2 为三个总量水平（18 runs）；C3 为两个两水平 process 因子 × 一个两水平总量因子（48 runs）。各行均保存 `T`、比例及实际组分量 `T*x`。
- 联合模型：72 行 × 15 项矩阵、已知系数、无噪声和解析噪声响应、拟合值、SSE、残差自由度、矩阵秩/条件数及独立预测。
- D-optimal 替换：锁定 A/B 顶点，枚举一个可替换父点对应的全部候选；保留锁定行及其已测响应，并冻结唯一最佳候选。
- 无效边界：比例和、非正总量、秩亏、锁定/已有响应行、候选不足、超预算、不可达阈值、Run ID 与 batch lineage 不匹配。

## 来源

- Taguchi 官方目录及逐行矩阵：[Minitab Catalogue of Taguchi designs](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/supporting-topics/taguchi-designs/catalogue-of-taguchi-designs/)。L16 mixed 逐行抄录 `L16 (2^12), (4^1)` 的 16×13 表。L18 官方表头为 `1..7,9`；本夹具内部第 8 个列位置对应官方标题 9。其 18×8 行值独立复制自已有冻结 CSV `tests/fixtures/doe_taguchi_reference/l18_2_1_3_7.csv`，并逐行对照官方表；非正交内部位置对 `(3,8),(4,8),(5,8),(6,8),(7,8)` 对应官方列号 `(3,9),(4,9),(5,9),(6,9),(7,9)`。
- S/N 定义：[Minitab methods and formulas](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/taguchi/analyze-taguchi-design/methods-and-formulas/methods-and-formulas/)；两阶段稳健优化背景：[What is the signal-to-noise ratio?](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/supporting-topics/taguchi-designs/what-is-the-signal-to-noise-ratio/)。

L8 mixed 的行值按本任务给定表冻结。L18 的表头保留官方缺列编号 8，不把显示标题 9 改写成官方列 8；非正交对同时记录“本地列位置”和“官方标题”。

## 重建与核验

在 MiniJMP 项目 Python 3.11 环境中，从本目录运行：

```powershell
& $python build_reference.py
& $python verify.py
```

生成器离线重建 `reference.json`，并刷新 manifest 中完整字节的 SHA-256 和字节数。Verifier 单独实现复核逻辑，不导入生成器；它检查官方矩阵逐行值、冻结统计量、身份/计数、全交叉覆盖、模型矩阵与拟合、D-optimal 全枚举及 manifest 哈希。

## 本次实际自检输出

```text
> & $python -m py_compile tests/fixtures/doe_phase2_p4bc_reference/build_reference.py tests/fixtures/doe_phase2_p4bc_reference/verify.py
> & $python tests/fixtures/doe_phase2_p4bc_reference/build_reference.py
built reference.json sha256=f23cad153fd383bfef6be5b0bdb88d37009e338b89e19a3e92935464ba68ebd7
updated manifest.json byte hashes for README.md, reference.json, build_reference.py, verify.py
> & $python tests/fixtures/doe_phase2_p4bc_reference/verify.py
P4BC reference verified: 3 arrays; 48 noise runs; 4 controls/6 noise conditions/24 condition groups; 90 mixture runs; 72x15 model; 4 D-opt candidates; 11 invalid boundaries
```
