# Factorial DOE 独立参考核验

## 固定参考

`tests/fixtures/doe_factorial_reference/reference.json` 的 SHA-256 为
`0c3e379a6962efe224695ba79a21d101319d4298d1ed6962c9a8a9b6dfef37ba`。
`manifest.json` 记录该摘要和不导入生产模块的来源。`verify.py` 用标准库重建组合、对比、别名、秩及平方和；生产代码变化不得通过改写参考文件适配。

## 分析方法与证据

| 生产入口 | 独立参考 | 核验内容 | 当前边界 |
|---|---|---|---|
| `doe_analysis.analyze_factorial` | `Y=50+3A−2B+4AB` 解析合同，`test_doe_factorial_anova.py` | 系数 `[50,3,-2,4]`，效应 `[6,-4,8]`，项 SS `36/16/64`，SST=SSR=116，饱和时不输出 F/p。 | 两水平全因子 2–6 因子；中心点整体曲率单独使用纯误差分母。 |
| `doe_analysis.analyze_factorial` | 三个完整区组的 2×2 fixture，`block_factorial` | 区组 SS=8、df=2；A/B/AB SS=108/48/192、误差 SS=8、df=6；逐项 F/p 与 fixture 一致。 | 区组只按一个完整重复分配；处理×区组残差作误差项时假设模型充分且无处理×区组交互。 |
| `doe_factorial_anova.partition_factorial_error` | 同一 2×2、3 区组 fixture | 同一设定跨区组不计为纯误差；纯误差 df/SS=0，区组调整残差 SS/df=8/6。相同无区组设定的重复按单元内平方和计纯误差。 | 只接受完整、平衡区组；不支持非平衡投影。 |
| `doe_analysis.analyze_factorial` | 独立解析 2×2、两次独立重复，阶次 1 | Pure Error SS/df=8/4；遗漏 AB 的 Lack of Fit SS/df=128/1；F=64，p 按 `F(1,4)` 计算。旧版按跨区组/不正确单元分组会被反例识别。 | 无纯误差时不输出失拟 F/p；零方差或自由度不足时不提供显著性。 |
| `doe_general_factorial_analysis.analyze_general_factorial` | 完整 2×3、两次重复及三完整区组 fixture | 2×3 分类项 df/SS/F/p、数值水平标签、边际/组合均值；完整区组模型失拟 df=0，区组间重复不冒充纯误差。 | 2–10 个分类因子；每因子 2+ 水平；最多 10,000 次运行和 10,000,000 个密集模型矩阵单元。 |
| `doe_fractional_analysis.analyze_fractional` | 正/负生成元、signed aliases、折叠前后点集 fixture | 代表系数按完整别名组解释；区组和中心点参与误差分层；Foldover 后根据当前矩阵重算 alias、秩和分辨率。 | 正规两水平分数；Foldover 仅全部因子或单因子、未分区组、单一新增批次。 |
| `doe_splitplot_analysis.analyze_split_plot` | 2×2、3 区组、12 运行独立分层 fixture | 总 df=11；区组 2；A 1、whole-plot error 2；B 1、A×B 1、subplot error 4；各层 SS/MS/F/p 与 fixture 核对。 | 两个连续两水平因子、一个 hard-to-change、一个 easy-to-change、完整平衡；不实现 REML 或不平衡裂区。 |

`tests/fixtures/doe_factorial_reference/verify.py` 的最终执行输出为 `factorial independent references verified`。对应生产分析专项在当前快照中为 45 passed；完整命令与其他测试组见 [工作包 D 收尾记录](work-package-d-closeout.md)。

## 官方范围来源

- [Minitab Support：2-level factorial 中 Pure Error、Curvature 与 Lack-of-Fit 的划分](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/supporting-topics/factorial-and-screening-designs/how-error-is-partitioned/)
- [Minitab Support：Factorial ANOVA 表](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/factorial/analyze-factorial-design/interpret-the-results/all-statistics-and-graphs/analysis-of-variance-table/)
- [Minitab Support：方差分析与 pure-error lack-of-fit 方法](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/factorial/analyze-variability/methods-and-formulas/analysis-of-variance/)

以上官方页面用于核定重复点和产品功能定义，不替代独立计算，也不证明 MiniJMP 与任何 Minitab 版本的结果表、标准序或随机序一致。当前未取得相应 Minitab 22 导出文件。
