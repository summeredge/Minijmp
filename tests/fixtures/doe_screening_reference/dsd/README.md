# DSD 独立参考

本目录保存按公开设计理论独立构造的连续和混合分类矩阵，用于后续数学验收。它们不是 Minitab 导出，也不声明与 Minitab 的逐点标准序一致。

## 文件与编码

- CSV 使用 UTF-8、LF、逗号分隔、整数编码；首列 `standard_order` 是本构造的 1-based 行号，其余列为 `X1..Xk`。它不是 Minitab 标准序；不含响应、区组或重复列。
- 连续因子编码为 `-1, 0, +1`。
- 行序是本文构造的确定性参考序，不是随机运行序，也不声称等于任何软件的标准序。
- 本目录 `manifest.json` 记录四份全连续 CSV 的 SHA-256、设计设置、来源和验证范围；混合参考另见[统一 manifest](../manifest.json)。哈希覆盖含表头的 CSV 原始 UTF-8 字节，不含 BOM。
- `verify.py` 只使用 Python 标准库：重建并核验本地 manifest 的四个连续矩阵、CSV 哈希、有理数秩和整数交叉积；混合矩阵由父级 manifest 与 `test_doe_screening_references.py` 单独核验。

## 矩阵构造

全连续设计按 conference matrix 构造。对 `q ∈ {5, 7, 9}`，在有限域 `GF(q)` 上取二次特征 `χ(a)=a^((q-1)/2)`；`GF(9)` 明确取 `GF(3)[u]/(u²+1)`。以 `∞` 和域元素为行列索引，矩阵对角为 0，有限元素间为 `χ(a-b)`，并按 `q mod 4` 设置 `∞` 行列。逐一核验 `CᵀC=qI` 后，设计矩阵取 `[C; -C; 0]`。

- 6 因子用 `GF(5)` 的 6 阶 conference matrix。
- 8 因子用 `GF(7)` 的 8 阶矩阵；7 因子设计取同一矩阵的前 7 列。该列子集构造与官方方法对“从更大 conference matrix 取列”的描述相符。
- 10 因子用 `GF(9)` 的 10 阶矩阵。

## 独立预期性质

- 行数分别为 13、17、17、21；每列只含 `-1,0,+1`，中心水平恰有 3 行。
- 若 conference matrix 阶数为 `N`，每个因子有 `N-1` 个低水平、`N-1` 个高水平和 3 个中心水平；`[C;-C]` 的每对行互为相反数，最后一行为整体中心点。
- 含截距的一阶 Gram 矩阵为 `diag(run_count, 2(N-1), …, 2(N-1))`；主效应与任意平方项、两因子交互项的交叉积均为 0。
- 截距 + 主效应 + 全部平方项秩为 `1+2k`；每个三因子投影的完整二次模型秩为 10。
- 全二阶模型不假定可估计：校验器报告每个矩阵的精确秩和剩余维数。交互列存在部分相关，但任意两交互列不完全成比例。

运行 `& .venv\Scripts\python.exe tests\fixtures\doe_screening_reference\dsd\verify.py` 可复核矩阵、哈希、秩和交叉积。脚本是 fixture 审计，不调用 MiniJMP 的 DSD 生成或分析代码。

## 来源与缺口

- Minitab 官方创建说明与可用设计表确认支持 2–48 因子、连续因子三水平、分类因子两水平，并列出各因子数的全连续基础运行数；含分类因子的设计每重复增加一次运行。
- Minitab 官方分析公式页描述全连续矩阵采用同阶 conference matrix 或更大矩阵的列子集；含分类因子时以两个伪中心点替换整体中心点，且多个分类因子的伪中心分配由迭代算法决定。
- Paley (1933) 给出有限域二次特征矩阵构造；Jones & Nachtsheim (2011) 给出 DSD 的 foldover 结构与二阶效应性质；Xiao, Lin & Bai (2012) 给出 conference-matrix DSD 构造；Wang, Liu & Lin (2022) 研究 Paley conference matrices 用于 DSD 的性质。

当前参考覆盖 6/7/8/10 个连续因子，以及按 Jones & Nachtsheim (2013) DSD-augment 独立构造的 4 连续加 1 分类参考；混合参考索引与测试见父级 manifest 和 pytest。该数学参考不证明 Minitab 混合矩阵一致。也未覆盖全部 2–48 因子矩阵、区组/重复/随机化或实际水平映射。若需产品逐点比对，请导出 Minitab 版本/构建号、连续/分类因子数、区组/重复/随机化/seed 设置，以及含 `StdOrder`、`RunOrder`、`PtType`、`Blocks` 和全部因子列的原始工作表。

官方运行数范围、来源链接、fixture SHA-256 和逐设计设置见 [manifest.json](manifest.json)。
