# Minitab 19 Taguchi Session Command 依据

来源：Minitab 官方 Session Commands PDF，第 414–419 页；官方入口：
https://support.minitab.com/zh-cn/minitab/media/pdfs/notranslate/session_commands.pdf

- 第 414–415 页：`OADESIGN` 创建正交表；`SNAME`/`SLEVEL` 指定动态信号因子与数值水平，设计会在每个控制组合上展开各信号水平。
- 第 416–419 页：`ROBUST` 分析 Taguchi 设计；`DYNAMIC C` 指定信号因子；`NOREF` 表示每个控制组合自由估计回归截距；`TSN`、`TSLOPES`、`TSTDS` 与 `ASN`、`ASLOPES`、`ASTDS` 分别输出响应表/ANOVA；`SNRATIO`、`SLOPES`、`INTERCEPTS`、`STDEVS` 存储结果。
- 本机 19.1.0.1 动态结果：每组 S/N、斜率、截距和残差标准差仅写在该控制组合首个信号行；后续行的 `1.23456e30` 是 Minitab 缺失哨兵。存储结果与信号行按 A/B 映射。
- 控制×噪声结果：固定 16 行覆盖 L4 控制阵列×L4 噪声阵列。`ROBUST` 以 A/B 为控制项，N1/N2 四种噪声条件各提供一个响应观测；`LOWER`、`SNRATIO`、`MEANS`、`STDEVS` 的 DIRECT 列值与 MiniJMP 的控制组汇总逐组比较。
- Minitab 输出的主要效应预测来自 `ROBUST` 响应表；本轮对最佳设置的响应预测按高精度直接存储值派生，没有把噪声因子并入控制模型。

实际 Session Commands、输出及逐行存储 JSON 见同目录 `session_commands.txt`、`minitab_raw.txt` 和 `minitab_results.json`。
