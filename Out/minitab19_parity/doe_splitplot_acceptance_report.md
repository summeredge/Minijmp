# MiniJMP × Minitab 19 平衡 Split-Plot 对标

**阶段状态：PASS**

比较计数：PASS 120 / FAIL 0 / N/A 1 / UNSUPPORTED 0。
来源分类（Minitab 侧）：DIRECT 76 / DERIVED 45 / DISPLAY 0。
最大绝对误差：1.136868377e-13，treatment_effect / B / f。

## 方法与范围

- 采用最小两因子结构：A（整区）和 B（子区），完整两水平设计分 3 个区组、6 个整区、12 次运行，使整区/子区误差自由度为 2/4；模型含 A、B、A×B。两层误差均非零且由有理数参考分别核验。
- Minitab 19 原生 `SPDESIGN` 与 `SPFACTORIAL`；WPID 按实际区组和 A 水平标识，核验每整区包含 B 的两个水平。
- Minitab 系数、XMATRIX、拟合值、整区残差和子区残差为 DIRECT。ANOVA 两个误差层 SS/MS、各处理项 F/P 和误差自由度按 Minitab 固定输入、whole-plot 分组及高精度输出 DERIVED，并与 MiniJMP 分层 ANOVA 比较。
- 固定区组模型秩与投影子空间均核对；A 使用 whole-plot error（df=2），B 与 A×B 使用 subplot error（df=4）。不将结果化简为普通 OLS；未比较随机区组方差分量、REML 或非平衡设计。

## 执行结果

Minitab 版本：19.1.0.1
输入行数：12。
实际 Session Command 和原始结果见 `doe_splitplot_minitab_raw.txt`。

## 证据文件

固定输入、两套 JSON、模型空间/误差层比较 CSV、Session Commands 与原始输出均保存在本目录。
