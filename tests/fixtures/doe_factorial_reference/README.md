# Factorial DOE 独立参考

`reference.json` 保存 General Full Factorial 的 2×3 与 2×3×4 矩阵、数值分类标签、带符号正规部分因子、全因子/单因子 Foldover、区组全因子和 2×2、3 区组、12 运行 Split-Plot 的静态参考。模型期望值由平衡设计的对比、投影与误差层分解得到；脚本不导入 MiniJMP 生产模块。

- `build_reference.py` 使用首因子最快变化的混合进制笛卡尔积和显式 ±1 乘积关系生成参考文件。
- `verify.py` 使用独立边际均值、组内平方和及正交对比复算 df、SS、F、p；从折叠前后点集重算带符号 alias、最短定义字和完整效应矩阵的精确有理数秩，并枚举全部 16 种全因子翻转掩码核对奇偶折叠结果。
- `manifest.json` 固定参考文件 SHA-256。生产代码变化不能通过重建或改写参考文件来适配。

Split-Plot 固定样例中 A 为 hard-to-change，B 为 easy-to-change；A 使用 Block×A 的 whole-plot 误差，B 和 A×B 使用 pooled subplot 误差。自由度合同是总计 11、区组 2、A 1、whole-plot error 2、B 1、A×B 1、subplot error 4。推断假设完整平衡、区组模型正确、各层独立且方差同质；超出该合同的设计不能复用这些 F/p 参考。

## 来源

- General Full Factorial 因子的文本/数值标签及水平设定：[Minitab Support — Specify the factors](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/factorial/create-factorial-design/create-general-full-factorial/create-the-design/specify-the-factors/)
- Split-Plot 随机化单位及误差项：[Minitab Support — Split-plot designs](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/supporting-topics/factorial-and-screening-designs/split-plot-designs-in-design-of-experiments/)
- 正规 Foldover 消除奇数长度定义字、单因子折叠消除含该因子的定义字，以及不增加分辨率的情况：[Minitab Support — Fold design](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/factorial/display-and-modify-design/perform-the-analysis/fold-design/)

