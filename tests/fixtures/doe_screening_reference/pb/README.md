# Plackett–Burman 独立参考矩阵

这三个文件是冻结的独立 PB 矩阵 oracle；数据取自 NIST Dataplot 发布的设计表，不是 Minitab 导出，也不是 MiniJMP 生成器的输出。表序作为 standard_order，不代表实际执行顺序。

## 矩阵格式与来源

CSV 为 UTF-8（无 BOM）、LF 换行；首列 standard_order 从 1 起，随后是 X1…Xk，水平为 -1 和 +1。无中心点、重复或区组。矩阵直接按 NIST 表行序冻结；PB28 的原始 1/2 水平映射为 +1/-1。原始来源哈希针对下载响应正文；CSV 哈希针对本目录中的最终字节。

| 文件 | runs | factors | 来源正文 bytes | 来源 SHA-256 | CSV bytes | CSV SHA-256 |
|---|---:|---:|---:|---|---:|---|
| pb12.csv | 12 | 11 | 2151 | dafc0a50171602d8710aeeb45af910e344d1dca762862d1667066f553d36c529 | 407 | 0266e0d7967a61119ddd1849fe380032c3421987cec9f4a8387e686db2bb728e |
| pb20.csv | 20 | 19 | 2916 | 50280b8f010bf830f2e4fddb43d512b829233d48be0bf32262254696d153ba4c | 1083 | 4b052486041ac0d59a8e572f4e0f8bfb1bc7273af4d7871033a780dc020c4f24 |
| pb28.csv | 28 | 27 | 3095 | 3d510c7e8a099cbdde8ec29c14046103de87555ec2eed71f5f6237bb635a01b6 | 2079 | cdd99044bfb7210b2a6a4c7e10bd7fd8e58f3cc364a904c630bd59edc67162fa |

## 数学预期与本地审计结果

每个设计都应满足：所有因子值属于 {-1,+1}；每列各有 n/2 个高、低水平；X^T X = nI；截距列与因子列正交。因此 [1 X] 的秩为 n（这里 k=n-1，是饱和主效应设计）。这些精确整数性质不依赖生产代码。

部分混杂按实际矩阵计算。对目标主效应 j 和不含 j 的二因子项 (a,b)，投影系数为 x_j^T (x_a ⊙ x_b)/n；⊙ 是逐点乘积。下表汇总绝对交叉积；|dot|=n 计为单个主效应的单位相关投影。结果显示这些交互对主效应有非零但小于 1 的投影，不能解释为正规分数因子的完整别名等式。此计数只检查单个主效应投影是否为 ±1，不表示多项共同混杂不存在。对包含目标因子的交互，交叉积应为零（由其他因子列平衡得到）。

| runs | factors | 非自含主效应/2FI 投影数 | abs(dot):count | 单位相关投影数 | X1 对 X2×X3 |
|---:|---:|---:|---|---:|---|
| 12 | 11 | 495 | 4:495 | 0 | -4/12 = −1/3 |
| 20 | 19 | 2907 | 4:2736, 12:171 | 0 | -4/20 = −1/5 |
| 28 | 27 | 8775 | 4:7800, 12:936, 20:39 | 0 | -20/28 = −5/7 |

来源中 28-run 的设计列存在一处文档注记不一致：文件声明 27 因子，数据表为 28×27，但 Dataplot 读取示例写作 X1 TO X23。本 fixture 以 27 列数据表为准，并由尺寸、列平衡和 Gram 矩阵审计确认。

## 来源与适用边界

- Minitab 官方 [Plackett–Burman designs](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/supporting-topics/factorial-and-screening-designs/plackett-burman-designs/)：规定 12–48 runs、因子数小于 runs；通常构造方式及 28-run 特殊分块规则；说明 12/20/24-run 主效应与多个二因子交互部分混杂，并将分析导向 Analyze Factorial Design。
- Minitab 官方 [Specify the design](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/how-to/factorial/create-factorial-design/create-plackett-burman/create-the-design/specify-the-design/)：说明中心点、重复及按重复分区组。本参考固定单次、无中心点、单区组基础矩阵。
- NIST Dataplot [PB 表索引](https://www.itl.nist.gov/div898/software/dataplot/designs.htm) 与 [PB12](https://www.itl.nist.gov/div898/software/dataplot/dex/PB12.DAT)、[PB20](https://www.itl.nist.gov/div898/software/dataplot/dex/PB20.DAT)、[PB28](https://www.itl.nist.gov/div898/software/dataplot/dex/PB28.DAT)：本地矩阵的直接来源。
- NIST/SEMATECH e-Handbook [Plackett–Burman designs](https://www.itl.nist.gov/div898/handbook/pri/section3/pri335.htm)：独立说明 PB 的运行数与筛选用途，并展示 12/20-run 设计。
- Box & Hunter (1961), “The 2^k-p Fractional Factorial Designs,” Technometrics, 3(3), 311–351，[公开论文 PDF](https://www.stat.cmu.edu/technometrics/59-69/VOL-03-03/v0303311.pdf)，Table 14A/14B：给出标准种子行和 28-run 特殊构造的独立文献依据。

允许用于数学等价比较的变换是运行行置换、因子列置换及单列反号；它们保留上述设计性质。这里未验证 Minitab 与 NIST 的逐行或逐列精确对应，也不表示随机运行序一致。

访问日期：2026-10-28。
