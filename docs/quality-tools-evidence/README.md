# P1 最终验收证据

2026-10-23，本机项目 `.venv`。以下 `final/` 为最终代码生成的证据，其他阶段目录为开发中间产物。

| 工具 | 真实 Tk 窗口 | 图形 | 导出示例 |
| --- | --- | --- | --- |
| Pareto | [截图](final/test_pareto_gui0/dialog.png) | [图窗保存](final/test_pareto_gui0/saved-via-viewer.png) | [CSV](final/test_pareto_gui0/pareto.csv) / [Excel](final/test_pareto_gui0/pareto.xlsx) |
| Run | [截图](final/test_run_gui0/dialog.png) | [图窗保存](final/test_run_gui0/saved-via-viewer.png) | [数据](final/test_run_gui0/运行图数据.xlsx) / [检验](final/test_run_gui0/随机性检验.csv) |
| 鱼骨 | [截图](final/test_cause_editor_gui0/dialog.png) | [图窗保存](final/test_cause_editor_gui0/saved-via-viewer.png) | [结构CSV](final/test_cause_editor_gui0/原因结构.csv) / [Excel](final/test_cause_editor_gui0/原因结构.xlsx) |
| Multi-Vari | [截图](final/test_multivari_gui0/dialog.png) | [图窗保存](final/test_multivari_gui0/saved-via-viewer.png) | [统计CSV](final/test_multivari_gui0/组合统计.csv) / [Excel](final/test_multivari_gui0/组合统计.xlsx) |
| 属性一致性（有标准） | [截图](final/test_attribute_gui_True_0/dialog.png) | [图窗保存](final/test_attribute_gui_True_0/saved-via-viewer.png) | [一致率](final/test_attribute_gui_True_0/完全一致率.xlsx) / [Kappa](final/test_attribute_gui_True_0/Kappa.xlsx) / [Kendall](final/test_attribute_gui_True_0/Kendall.csv) |
| 属性一致性（无标准） | [截图](final/test_attribute_gui_False_0/dialog.png) | [图窗保存](final/test_attribute_gui_False_0/saved-via-viewer.png) | [一致率](final/test_attribute_gui_False_0/完全一致率.csv) |

每个窗口结果中的所有表都实际导出 CSV 和 Excel 并回读检验，未逐个罗列。
PNG 通过 Pillow 回读，窗口截图经人工视觉复核。鱼骨密集分支另见 [中文多分支图](final/test_cause_structure_and_long_0/dense-fishbone.png)，四因子图见 [四因子](final/test_multivari_independent_cel3/multivari4.png)。

完整命令、592项用例结果、逐方法独立参考、与 Minitab 差异和未验证范围见 [阶段报告](../quality-tools-extension.md)。
