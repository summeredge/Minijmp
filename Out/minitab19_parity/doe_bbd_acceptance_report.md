# MiniJMP × Minitab 19 三因子 Box–Behnken 对标

**阶段状态：PASS**

比较计数：PASS 356 / FAIL 0 / N/A 0 / UNSUPPORTED 0。
来源分类（Minitab 侧）：DIRECT 268 / DERIVED 88 / DISPLAY 0。
最大绝对误差：2.667945864e-10，prediction / P3 / pi_low。

## 方法与范围

- 固定设计为 3 个连续两水平因子、12 个 BBD 边点和 3 个中心点，共 15 次运行；无区组。响应含完整二次项、固定三阶偏差与三个中心观测偏差。
- Minitab 19 原生 `BBDESIGN 3` 与 `RSREG` 执行完整二次模型；按实际编码行映射 Minitab 与 MiniJMP 设计，XMATRIX 的十列按数值映射至截距、线性、平方和交互项。
- DIRECT 包含设计、XMATRIX、系数、拟合/残差和三点 PREDICT/SE Fit/95% CI/PI；DERIVED 由 Minitab 高精度输出和固定输入重建 ANOVA、线性/平方/二因子交互效应组、纯误差与失拟。
- 预测点为中心点、内部非设计点 (0.5, -0.25, 0.4) 和边点 (-1, 0, 1)；区间置信水平 95%。

## 执行结果

Minitab 版本：19.1.0.1
输入行数：15。
原始 Session Command 输出见 `doe_bbd_minitab_raw.txt`。

## 证据文件

固定输入、Session Commands、Minitab 原始输出、两侧 JSON、数值比较 CSV 与本报告均保存在本目录。
