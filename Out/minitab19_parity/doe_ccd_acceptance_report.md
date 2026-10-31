# MiniJMP x Minitab 19 面心 CCD 二次响应面对标

## 验收结果

**PASS**：两次独立 Minitab COM 会话与 MiniJMP 生产入口均已完成。
比较 CSV 共 897 行，PASS 883、N/A 14、FAIL 0。
容差沿用 2x2 对标：绝对 1e-09、相对 1e-09，未做任何放宽。

## 数据与方法

- 固定输入 doe_ccd_input.csv：标准序 13 次运行，4 个因子点、4 个轴点、5 个中心点，面心 alpha=1，不分区组。
- 响应为确定性构造：外点按二次曲面加固定小偏差，5 个中心点响应 10.10、9.94、10.06、9.98、10.12，使纯误差为 0.024、SSE 为 0.04338、残差 df=7、失拟 df=3。
- 两边都使用完全相同的编码因子，同一模型项（A、B、A*B、A^2、B^2），同一截距约定，95% 置信水平。
- MiniJMP 生产入口：code/doe_ccd.py::create_ccd、code/doe_rsm.py::analyze_rsm、code/doe_predict.py::predict_point；未修改任何统计生产代码。

## 已完成的 Minitab 原生一致性验证（DIRECT）

- CCDESIGN 2; ALPHA 1; CENTER 5; DESIGN. 生成的 13 个运行，其标准序、点类型、A/B 编码与固定 CSV 逐行一致。
- RSREG 的存储量经 COM 直接回读且为全精度：XMATRIX M1（13x6）、COEFFICIENTS C10、FITS C8、RESIDUALS C9。比较使用的正是这些值，不是报表舍入值。
- 模型矩阵秩、6 个系数、13 个拟合值、13 个残差全部 DIRECT 比较。
- 三个预测点使用 PREDICT + KPREDICTORS 原生执行，PFITS、PSEFITS、CLIMITS、PLIMITS 存列后全精度回读；拟合值、SE Fit、95% 均值置信区间、95% 单次观测预测区间共 18 项均为 DIRECT。

## 由 Minitab 高精度数据重建的统计量（DERIVED）

ANOVA 的 Model/线性/交互/平方/误差/失拟/纯误差/合计各行，以及 S、R2、调整 R2、SSE、SST、MSE，均由 Minitab 的 M1、C10、C8、C9 与固定 Y 独立重建（P 值用 scipy.stats.f.sf）。
这些是派生量，用于与 MiniJMP 的对应定义比较；Minitab 原生报表的舍入表同时保留在两个 raw 文件中，未宣称报表级逐位 parity。

| 项目 | Minitab（DERIVED，全精度） | MiniJMP |
| --- | --- | --- |
| Model SS / df | 97.90761954 / 5 | 97.90761954 / 5 |
| Error SS / df | 0.04338045977 / 7 | 0.04338045977 / 7 |
| Total SS / df | 97.951 / 12 | 97.951 / 12 |
| 失拟 SS / df | 0.01938045977 / 3 | 0.01938045977 / 3 |
| 纯误差 SS / df | 0.024 / 4 | 0.024 / 4 |
| S | 0.07872235095 | 0.07872235095 |
| R2 | 0.9995571208 | 0.9995571208 |
| 调整 R2 | 0.9992407785 | 0.9992407785 |

## 三个预测点（DIRECT）

| 点 | 编码设置 | 预测均值 | SE Fit | 95% 均值区间 | 95% 预测区间 |
| --- | --- | --- | --- | --- | --- |
| 中心点 | (0, 0) | 10.02896552 | 0.03268767705 | [9.951671443, 10.10625959] | [9.827407232, 10.2305238] |
| 轴点 | (1, 0) | 9.974252874 | 0.05534426915 | [9.843384473, 10.10512127] | [9.746705281, 10.20180047] |
| 内部非设计点 | (0.5, 0.5) | 9.593275862 | 0.03484663267 | [9.510876669, 9.675675055] | [9.389705247, 9.796846477] |

## 未获得直接产品证据的内容

- Minitab 19 的 PREDICT 文档只提供 PFITS/PSEFITS/CLIMITS/PLIMITS，没有逐项 SS/F/P 的机器精度存储；因此逐项 SS/F/P 属于 DERIVED。
- 未验证其他 CCD 布局（CCC、旋转、分区组、分数立方、3 个以上因子），未验证 BBD 或其他 DOE 类型。
- 不更新正式 DOE 功能矩阵，不代表全部统计输出的 parity。

## 文件

- verify_doe_ccd.py、doe_ccd_input.csv、doe_ccd_session_commands.txt
- doe_ccd_minitab_raw_run1.txt、doe_ccd_minitab_raw_run2.txt
- doe_ccd_minitab_run1.json、doe_ccd_minitab_run2.json
- doe_ccd_comparison.csv、doe_ccd_run.log
