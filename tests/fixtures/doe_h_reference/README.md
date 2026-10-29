# DOE 工作包 H 独立数学参考

`reference.json` 由 `build_reference.py` 从本目录内手写的小设计矩阵生成；`verify.py` 独立复算并校验 JSON。两者只用 NumPy/SciPy 和标准库，不导入 MiniJMP 生产代码。

- 二项响应：按 grouped-binomial log likelihood 求核验值；解析系数由预先指定的 log-odds 生成，协方差由观测信息矩阵 `(X'WX)^-1` 得到。回归自由度按设计行数减矩阵秩；全模型相对仅截距模型用似然比 χ²。
- Variability：同一组原始测量同时以“每次运行多列”和“同区组内独立运行多行”表示；按样本标准差（`ddof=1`）汇总，再对 `ln(SD)` 做等权最小二乘。等重复数时官方方法确认权重相同；本参考不覆盖不等重复数、正态 MLE 或裂区误差。
- Power：对指定的一自由度两水平主效应，`δ=2β`，`λ=β²/[σ² (X'X)^-1[j,j]/r]`；分母自由度为 `r*n-rank(X)`。拒绝域使用中心 F 的上 α 分位点，功效用非中心 F survival function。样本量逐一搜索整数重复数，并校验前一个重复数不达标及总运行数不超过 10,000。

STD 和 EDGE 案例按 `acceptance_cases` 映射到 ACC。边界案例也覆盖无效计数、全失败/全成功、完全分离、秩亏、零 SD、样本不足及功效不可解。
