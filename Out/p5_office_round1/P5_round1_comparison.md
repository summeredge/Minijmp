# MiniJMP P2-5 首轮 Minitab 22 数据转换及独立对照

生成日期：2026-10-30

## 判定摘要

| 核验项 | 状态 | 结论 |
|---|---|---|
| DSD-S01 | PARTIAL | 13 行输入、因子矩阵和 Y 值与参考逐行匹配；RTF 数值只能核对显示精度。 |
| PB12 原始点集 | PASS | 12 × 11 因子点集与参考完全匹配。 |
| PB12 Foldover 变换 | PASS | 24 行；原有 12 点保留，新增 12 点均为原点全因子反号。 |

## Minitab 版本与证据

- 产品版本记录为 **Minitab® 22.6.0 (64-bit)**，来源 Out/p5_office_round1/results/minitab22.6.0.txt；SHA-256：aa6abe3492b59fcf82a0f608e6c046e8b65d2590468abc8b11e73685d49a48eb。
- DSD 统计结果来自 Out/p5_office_round1/results/DSD_S01_output.rtf（104582 字节，SHA-256 0cfd4839c11b8c7cb278bd350411191385a9015dcc36d54486c30fbacba497bc）；RTF 原件未改写。
- DSD 参考：tests/fixtures/doe_phase2_p4a_reference/dsd_reference.json 的 DSD-S01-main-effects；因子矩阵来自 tests/fixtures/doe_screening_reference/dsd/dsd_06_cont_13.csv。
- PB12 数学参考：tests/fixtures/doe_phase2_p4a_reference/pb_foldover_reference.json，12-run / 11-factor publication case。

## CSV 编码、分隔符与原件指纹

编码按原始字节 BOM 识别；分隔符通过逗号、制表符、分号、竖线解析后的列数一致性判定。UTF-8 副本保留原分隔符、列顺序、行顺序和单元格文本；DSD 保留制表符，PB12 保留逗号。

| 原始文件 | 字节 | 编码 | 分隔符 | 数据行 | SHA-256 |
|---|---:|---|---|---:|---|
| DSD_S01_input.csv | 544 | UTF-16 LE BOM | tab | 13 | 4ba344e4f71a7a564f5b6ad39bb7ce1e932dec0df33e66de2f2cfa56b4557124 |
| PB12_original - 副本.csv | 1052 | UTF-16 LE BOM | comma | 12 | ed10f64c72812ef574450c33db7cfb5ea235d0dd33af107984173becef9d7c96 |
| PB12_folded.csv | 1976 | UTF-16 LE BOM | comma | 24 | 274fc4e5ba01807491ba915bb883b1014269b51994723b5e4005da0af1f52d69 |

规范化副本（UTF-8 无 BOM）：

- Out/p5_office_round1/normalized/DSD_S01_input.csv（271 字节，SHA-256 b61c6505b911c9c9c1377098898c97ef69fc4f4cc32b27e5f1b1ef084fbdf143）
- Out/p5_office_round1/normalized/PB12_original - 副本.csv（517 字节，SHA-256 2440edd89849062d77848395bb0f86d6f2e9e627312b323467c0b38d0fdb5a0a）
- Out/p5_office_round1/normalized/PB12_folded.csv（979 字节，SHA-256 12566c3cc7da10a03f7533e97cc5751c94340a0d6437961e58bae31ad181b0b4）

## DSD-S01

- 输入为 13 行、F1–F6 六个因子和 Y 响应列。F1–F6 分别对应参考矩阵 X1–X6，因子矩阵按行完全相同；13 个 Y 值均与 DSD-S01-main-effects 参考一致。
- 选择顺序：**F1 → F2**。RTF 显示系数：常量 40.0000、F1 5.0000、F2 -3.0000。
- RTF 显示误差 SS = 0.010、自由度 = 10、残差标准差 S = 0.0316228。
- **精度限制：**系数、SS 和 S 是 RTF 格式化后的显示值；无法由该 RTF 证明产品内部完整精度，因此完整精度为未验证，不宣称全精度相等。

## PB12 原始点集

- 原始表有 12 个设计点和 11 个数值因子 F1–F11；F1–F11 依次映射到 fixture 第 1–11 列，未发现列重排或符号约定差异。
- 标准序与运行序分别为 1–12；CSV 行序也依这两种顺序排列。按标准序比较的点逐行匹配 fixture，多重集也一致；本案例没有重复点。

## PB12 Foldover 变换

- 折叠后共 24 行；11 个因子的水平仅为 -1/+1。原有点集全部保留；从折叠表减去原点多重集后，剩余 12 点均等于对应原点的 11 个因子逐一反号。
- 标准序、运行序分别为 1–24，CSV 行序都与其一致。运行序、标准序和实际点多重集分别比较，均与参考相符；无行序、因子映射或符号差异。
- 可复核例 1：标准序 1 原点 [1, -1, 1, -1, -1, -1, 1, 1, 1, -1, 1]；标准序 13 新增点 [-1, 1, -1, 1, 1, 1, -1, -1, -1, 1, -1]，11 项逐一反号。
- 可复核例 2：标准序 12 的全 -1 点对应标准序 24 的全 +1 点。

## 差异与完整性

- DSD-S01 的输入数据核对通过，但 Minitab RTF 只保留格式化显示精度，故该项为 PARTIAL。
- PB12 原始点集和 Foldover 变换均未发现差异；标准序、运行序、文件行序分开核验，没有把排序误判为设计点错误。
- 三个原始 CSV 处理前后 SHA-256 一致；原始 Minitab 输出、独立 fixture 和 .agent-memory 均未修改。

## 解码自检

使用 UTF-16 LE、UTF-16 BE、UTF-8 BOM 和 GB18030 构造样例自检解码，并识别 tab、semicolon、comma、pipe；4 种编码/分隔符自检及本次文件的字段数、UTF-8 回读断言均通过。
