# MiniJMP × Minitab 19 Taguchi L8/L9 对标

**阶段状态：PARTIAL**

比较计数：PASS 575 / FAIL 0 / N/A 25 / UNSUPPORTED 2。
来源分类（Minitab 侧）：DIRECT 498 / DERIVED 70 / DISPLAY 43。
最大绝对误差：0.003846153846，l9 / anova / P_C / f。

逐项 CSV 保留 602 条按 S/N 分析展开的结果；批次汇总按 `(case, section, term, statistic)` 去重，移除 102 条重复均值项后，Taguchi 唯一计数为 PASS 473 / FAIL 0 / N/A 25 / UNSUPPORTED 2，来源 DIRECT 396 / DERIVED 70 / DISPLAY 43。

| 案例 | 状态 | 比较项 | FAIL | UNSUPPORTED |
| --- | --- | ---: | ---: | ---: |
| L8 | PARTIAL | 302 | 0 | 1 |
| L9 | PARTIAL | 300 | 0 | 1 |

## 方法与限制

- 固定输入为每个 Taguchi 组合 3 个正值响应观测；Minitab 设计矩阵由 OADESIGN 生成，并按因子组合与 MiniJMP 标准序映射。
- NOMONE 是只基于标准差的 Nominal-is-best (II)，NOMTWO 是均值/标准差型 Nominal-is-best (I)；调整型 I 为 `10*log10((x̄² - s²/n)/s²)`，其中 `s²` 是重复观测的样本方差。Minitab 19.1.0.1 实际接受 `ROBUST ... NOMTWO; ADJUSTED; SNRATIO`，输出表显示该公式且 SNRATIO 列可直接 COM 回读；L8/L9 共 17 个 S/N 与独立公式及 MiniJMP API 相符。水平响应均值、Delta、Rank 和最佳水平由 Minitab DIRECT SNRATIO 聚合后 DERIVED 比较。定义见 [Minitab Taguchi Methods and formulas](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/taguchi/analyze-taguchi-design/methods-and-formulas/methods-and-formulas/)；命令依据 [官方 Session Commands](https://support.minitab.com/zh-cn/minitab/media/pdfs/notranslate/session_commands.pdf)。
- `OAPREDICT` 的均值 CI/观测 PI 存储尝试被 Minitab 19 拒绝。相同聚合均值、因子项和 treatment 编码由 Minitab `REGRESS` + `PREDICT` 直接拟合并回读模型矩阵、拟合/残差及 95% 均值 CI/单次观测 PI；该路径是等价分类回归模型输出，不称为 OAPREDICT 原生区间。L8 的 SSE/MSE 为 0，Minitab 给出零宽区间而 MiniJMP API 将区间标不可用，因此区间数值比较为 N/A；L9 有正残差方差，观察点、非设计可估点及最佳 S/N 设置的 CI/PI 通过直接比较。
- ROBUST 的均值系数和 ANOVA 仍只能从 Minitab 报表 DISPLAY 读取；系数先按 Minitab 效应编码转换到 MiniJMP 的 treatment 编码，再按报表显示精度比较。L8 的均值模型误差平方和为零，相关 F/P 在两边均不可用。
- SNRATIO 与 MEANS 直接存储值只落在每组三个重复行的首行；其余两行是 Minitab 的缺失值标记。Delta/Rank 由这些 DIRECT 值聚合后 DERIVED。
- 本机版本 Minitab 19.1.0.1；新命令及其完整回传保留在逐案例 Session Commands、raw 与 Minitab JSON。

## 证据文件

输入、命令、原始输出、JSON 和逐项 CSV 分 L8/L9 保存；合并比较见 `doe_taguchi_comparison.csv`。
