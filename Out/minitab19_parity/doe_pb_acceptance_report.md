# MiniJMP × Minitab 19 Plackett–Burman 12-run 对标

**阶段状态：PASS**

比较计数：PASS 475 / FAIL 0 / N/A 0 / UNSUPPORTED 0。
来源分类（Minitab 侧）：DIRECT 224 / DERIVED 251 / DISPLAY 0。
最大绝对误差：1.98951966e-13，main_effect / A / f。

## 方法与范围

- 固定设计为 12 次运行、7 个连续两水平因子，-1/+1 编码，无中心点、重复或区组；MiniJMP 点集另与冻结 NIST PB12 独立 fixture 核对。响应包含主效应与多个二阶交互，主效应模型不完全拟合。
- Minitab 19 原生 `PBDESIGN 7 12` 与 `SCREEN` 拟合七个主效应；Minitab 的系数按 coded level 存储，效果值按 2×系数换算。
- DIRECT 包含设计矩阵、SCREEN XMATRIX、系数、拟合值与残差；ANOVA、标准误、t/F/P、效果排序及 2FI→主效应投影由 Minitab 高精度矩阵和固定数据 DERIVED。
- PB 不提供独立纯误差：12 个设置均唯一，误差自由度为 4，SSE 用于主效应模型推断。完整 8×21 截距/主效应对二因子交互投影由 Minitab 原生矩阵重建，不称为 SCREEN 原生别名表。
- 2FI 部分混杂按实际矩阵投影比较；不采用正规分数因子的 defining relation 或完整别名等式。效果排名并列时按因子 ID 升序打破并列。

## 执行结果

Minitab 版本：19.1.0.1
输入行数：12。
固定响应、原生命令和完整输出见 `doe_pb_input.csv`、`doe_pb_session_commands.txt`、`doe_pb_minitab_raw.txt`。

## 证据文件

两侧模型 JSON、数值比较 CSV、独立 PB12 fixture 映射与本报告均保存在项目证据目录。
