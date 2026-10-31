# MiniJMP × Minitab 19 三组分二次 Scheffé 混料对标

**阶段状态：PASS**

比较计数：PASS 247 / FAIL 0 / N/A 6 / UNSUPPORTED 0。
来源分类（Minitab 侧）：DIRECT 174 / DERIVED 61 / DISPLAY 18。
最大绝对误差：0.0004470965076，prediction_display / P2 / ci_high。

## 方法与范围

- 固定设计为三组分 7 点 Simplex Centroid：3 个顶点、3 个边中点和 1 个中心点，各重复 2 次；前 6 点对应二次 Simplex Lattice，另加中心点以满足内部点和纯误差要求。响应含 A×B、A×C、B×C 交互和对称重复偏差。
- Minitab 19 原生 `SCDESIGN` 生成比例设计；`MIXREG` 显式列出 A、B、C 及三个二阶交互项，配合 `INUNIT 1` 和零组分下界，拟合完整二次 Scheffé 模型。
- `MIXREG` 可直接保存 XMATRIX、系数、拟合值和残差，并执行 95% `PREDICT`；Minitab 19.1.0.1 拒绝 `PSFITS` 存储子命令。预测表显示到 3 位小数并按显示精度比较；同时以 Minitab 原生高精度模型矩阵、系数和误差项独立重建预测区间。
- 先按三组分比例和重复序号对齐 Minitab 与 MiniJMP 行；Minitab XMATRIX 列按实际值映射到六个 Scheffé 项，避免依赖列顺序假设。
- DIRECT 包含设计、XMATRIX、系数和拟合/残差；DISPLAY 为 Minitab 的舍入预测表；DERIVED 统计量及预测区间由 Minitab 高精度存储、固定响应和 SciPy 公式重建。
- MiniJMP 不为受比例和约束的组分主项报告单项 F/P；这些单项比较记为 N/A。纯误差与失拟由重复点残差重建。

## 执行结果

Minitab 版本：19.1.0.1
输入行数：14。
原始 Session Command 输出见 `doe_mixture_minitab_raw.txt`。

## 证据文件

输入、命令、原始输出、MiniJMP/Minitab JSON 与逐项 CSV 均保存在本目录。
