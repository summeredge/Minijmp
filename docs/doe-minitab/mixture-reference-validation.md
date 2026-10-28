# 混料独立参考核验

日期：2026-10-28

## 原则与边界

参考实现不导入 MiniJMP 生产模块，不使用 Minitab 输出作为数值 oracle。Minitab 官方页面只用于确认产品菜单和功能范围；本参考用于验证 MiniJMP 的数学实现。

允许并实际使用的工具：标准库 `Fraction`、自写高斯消元、确定性线性代数与有限网格穷举。参考不证明 Minitab 标准序、XVERT/CONAEV 顺序或产品图形布局一致。

## 文件与清单

- `tests/fixtures/doe_mixture_reference/build_reference.py`：重建参考与清单。
- `tests/fixtures/doe_mixture_reference/reference.json`：精确分数参考。
- `tests/fixtures/doe_mixture_reference/verify.py`：独立复核点集、顶点、预测、ANOVA、叠加可行域与 SHA-256。
- `tests/fixtures/doe_mixture_reference/manifest.json`：文件 SHA-256 与字节数。

当前 `reference.json` 文件字节 SHA-256：`cfc482999750eafac2bd8bc89b469e628c405cce23e25c00c010f2695184b0de`（包含末尾换行）；此前记录的 `8ae2c0712fdb423a0570336ebf96cca0dd8366e56c7dddf1be007ad36099c913` 是去掉末尾换行的内容摘要。

## 覆盖矩阵

| 参考 | ACC | 生产证据 |
|---|---|---|
| 三组分 Lattice 2/3 阶 | 032 | `test_doe_mixture_references.py`、`test_doe_mixture_lattice.py` |
| 三组分 Centroid 7 点 | 033 | `test_doe_mixture_references.py`、`test_doe_mixture_centroid.py` |
| 5 顶点约束多边形、不可行、退化 | 034/035 | `test_doe_mixture_references.py`、`test_doe_mixture_vertices.py` |
| 过程变量与 `xi*z` | 036/037 | `test_doe_mixture_model.py`、`test_doe_mixture_predict.py` |
| 线性/二次 Scheffé 系数与预测 | 037 | `test_doe_mixture_references.py` |
| 11 行二次模型 ANOVA、纯误差、失拟 | 038 | `test_doe_mixture_anova.py` |
| 整体模型 F/p 的隐含常数自由度 | 038 | `test_doe_mixture_anova.py`；由既有 SSE/SSR 独立重算 |
| 解析点预测、越界/总和检查 | 039 | `test_doe_mixture_predict.py` |
| max/min/target 独立网格界 | 040 | `test_doe_mixture_optimize.py` |
| Trace 参考缩放 | 041 | `test_doe_mixture_plots.py` |
| 10 阶三元网格与轴映射 | 042/043 | `test_doe_mixture_plots.py` |
| 双响应交集 11 点、空交集 | 044 | `test_doe_mixture_plots.py` |

## 已知限制

- 优化参考是有限网格上的上/下界，不是全局最优证明；生产结果只需不劣于该网格。
- 纯误差参考只覆盖一个独立重复单元；更复杂区组/不平衡结构未构造。
- 参考不覆盖 Minitab 标准序、图形样式、预测区间或其他产品专属选项。

## Review ITERATE 修正（2026-10-28）

参考 JSON 未修改；以下检查直接使用既有 `anova_reference` 的 SSE/SSR 和 p/df，不通过刷新参考掩盖实现错误。

- 完整 Scheffé 模型含隐含常数向量，模型自由度为 `rank-1=5`。以既有 `SSR=419923/40986`、`SSE=7345/1242`、`df=5` 重算：`F=(SSR/5)/(SSE/5)=SSR/SSE≈1.7324628174`；旧实现误用 `SSR/6`，得到 `≈1.4437190145`。
- 不含量向量的自定义模型改用未校正 `SST=y'y`、`SSR=SST-SSE` 和 `rank` 自由度；测试同时覆盖两种定义，避免混用。
- 可估计性由列空间投影改为行空间投影；新增零列、非零完全共线列、满秩项和线性对比测试。
- 默认过程变量模型移除过程主项 `P`，保留 `xi*P`；完整高低过程组合下矩阵满秩，拟合系数与解析预测由测试核对。
- 双组分网格明确拒绝二维等高线/曲面，Trace 仍可用。
