# 混料设计独立参考

本目录为工作包 F 的独立数学参考，使用标准库 `Fraction`、自写高斯消元与网格穷举，不导入 MiniJMP 生产模块。`build_reference.py` 重建 `reference.json` 与 SHA-256 `manifest.json`；`verify.py` 独立复核点集、约束顶点、Scheffé 预测、ANOVA 残差、叠加可行域及清单哈希。

覆盖 ACC-032～044：三组分 2/3 阶格点、7 点重心、约束多面体 5 个顶点、不可行与退化区域、线性/二次 Scheffé、过程变量与总量语义、纯误差/失拟 ANOVA、单/多响应优化网格界、Trace/等高线/曲面/叠加可行域。Minitab 官方页面仅用于确认产品功能边界，不作为数值正确性证明。

重建命令（项目 `.venv`）：

```powershell
& 'C:\Users\shaoy\Documents\Minijmp\.venv\Scripts\python.exe' tests/fixtures/doe_mixture_reference/build_reference.py
```
