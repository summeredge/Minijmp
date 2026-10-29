# DOE Phase 2 P2-3 Split-Plot 独立参考

该 fixture 由纯 Python 参考脚本构造，不导入 `code/` 或 MiniJMP 的生产模块。生成器以 Fraction 有理数计算平衡对比和嵌套误差投影；`verify.py` 则从完整模型矩阵的精确正规方程投影计算系数，并利用已核对的正交列投影增量复算项 SS。F 分布右尾概率使用 SciPy `stats.f.sf`。

运行（项目解释器）：

```powershell
& .\.venv\Scripts\python.exe tests\fixtures\doe_phase2_splitplot_reference\verify.py
```

`build_reference.py` 读取既有 `doe_factorial_reference/reference.json` 作为 Case 1 的 D 工作包来源；其余案例独立生成。生成脚本写入新的 `reference.json` 和 SHA-256 `manifest.json`。除非参考方法合同发生经审查的更正，不要为适配生产结果重建 fixture。

| 案例 | 结构与核验内容 |
|---|---|
| Case 1 | 原 2 因子、1 hard + 1 easy、3 blocks、12 runs；原 D 工作包 SS/df/F/p 保持不变。 |
| Case 2 | 1 hard + 2 easy、3 blocks；24 runs、6 整区及 A/B/C/AB/AC/BC/ABC 全部效应。 |
| Case 3 | 2 hard + 2 easy、3 blocks；48 runs、12 整区、整区误差 df=6、子区误差 df=24。 |
| Case 4 | 3 hard + 1 easy、2 blocks；多个 hard-only 交互用整区误差，所有 easy-containing 项用子区误差。 |
| Case 5 | `Y=50+3A−2B+4C+5AB−3AC+2BCD+WP_error+SP_error`，逐整区/子区给定确定性误差并用精确有理数复算。 |
| Case 6 | 6 因子设计全数值复核覆盖上限；整区或子区零方差逐项核验 F/p 可用性；实际构造缺失/非有限响应、秩亏、缺子区组合、整区身份错配、hard 水平变化和重复身份边界。 |

每个数值行还固定 run、whole-plot、subplot ID 和嵌套顺序；独立核验器会检查全局唯一性、每区组全部 hard 组合、每个整区完整 easy 组合、运行顺序连续以及模型秩。Manifest 同时绑定参考 JSON、生成/核验脚本及原 D fixture 的 SHA-256，并记录 SciPy 版本。

该 fixture 是统计和实验单位参考，不是 Minitab 产品运行序或输出格式的导出。Split-Plot 的单位和两层随机化定义参考 [Minitab Support](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/supporting-topics/factorial-and-screening-designs/split-plot-designs-in-design-of-experiments/)；本包的固定区组平衡推断范围由 `docs/doe-minitab/phase2-p3-method-contract.md` 冻结。
