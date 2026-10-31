# DOE 二元响应分析对标验收

状态：**FAIL**

## 案例与定义

- `BIN-FACTORIAL`：2² 两水平全因子，4 个事件/试验分组，完整 A+B+A×B Logistic 模型。
- `BIN-RSM`：3 因子 BBD（12 边点+2 中心点），完整二次 Logistic 模型。
- MiniJMP 与 Minitab 均拟合 grouped binomial-logit；最大迭代 200、收敛容差 1e-10。
- 两案均使用 Minitab DOE 专用原生命令 `BFFACTORIAL`/`BRSREG`，不是通用 GLM 替代。

## 结果

唯一比较项：195；PASS/FAIL/N/A/UNSUPPORTED：177/16/2/0。
Minitab 来源计数（可重叠）：DIRECT/DERIVED/DISPLAY：108/55/0。

## 证据

- 固定数据、Session Commands、Minitab Outputs/OutputDocument、双方高精度 JSON 与逐项比较 CSV 均保存在本目录。
- RSM 预测区间采用 Logit 尺度 95% Wald 区间；Minitab 侧由直接系数和 X'WX 逆矩阵重建。

## 超出默认容差的差异

- `BIN-FACTORIAL` / `minijmp_se_vs_fisher`：4 项；最大绝对差 2.119078151e-07（截距），Minitab=0.35794552658190887，MiniJMP=0.35794531467409374。
- `BIN-FACTORIAL` / `standard_error`：4 项；最大绝对差 2.119030369e-07（截距），Minitab=0.35794552657713063，MiniJMP=0.35794531467409374。
- `BIN-FACTORIAL` / `wald_p`：2 项；最大绝对差 1.402786097e-07（A），Minitab=0.05281139177184483，MiniJMP=0.05281125149323511。
- `BIN-FACTORIAL` / `wald_z`：2 项；最大绝对差 1.146376718e-06（A），Minitab=1.9364599613471773，MiniJMP=1.9364611077238958。
- `BIN-RSM` / `wald_z`：4 项；最大绝对差 2.71666174e-08（A*C），Minitab=5.571773199981684，MiniJMP=5.571773172815067。
- `BIN-FACTORIAL` 的 Minitab SE 与由其直接拟合概率、试验数和编码矩阵构造的 inverse X'WX 参考吻合；MiniJMP SE 与该参考相差约 5.92e-7 相对误差。关联的 Wald z/P 同样超出容差。
- `BIN-RSM` 的系数和 SE 比较通过；4 个由高精度系数/SE 计算的 Wald z 仍超过默认容差，最大绝对差约 2.72e-8。
未修改 MiniJMP 生产算法或放宽容差；逐项值和误差见 `comparison.csv`。
