# Minitab 19 Mixture 过程与总量补充对标

唯一比较项：35（PASS 34 / FAIL 0 / N/A 0 / UNSUPPORTED 1）。
Minitab 来源：DIRECT 2、DERIVED 32、DISPLAY 0。

- MIX-PROCESS: PASS 34 / FAIL 0 / N/A 0 / UNSUPPORTED 0。
- MIX-AMOUNT: PASS 0 / FAIL 0 / N/A 0 / UNSUPPORTED 1。

## Minitab 19 实际命令

- MIX-PROCESS:

```text
MIXREG C5 = C1 C2 C3 C1*C4 C2*C4 C3*C4; PROC C4; INUNIT 1; LOWER 0 0 0; COEFFICIENTS C6; FITS C7; RESIDUALS C8; XMATRIX M1; BRIEF 3.
```

- MIX-AMOUNT:

```text
MIXREG C5 = C1 C2 C3 C1*C2 C1*C3 C2*C3; AMOUNT C4; INUNIT 1; LOWER 0 0 0; COEFFICIENTS C6; FITS C7; RESIDUALS C8; XMATRIX M1; BRIEF 3.
```

## 口径与限制

- 两案均使用三组分二阶 Simplex Lattice 固定输入；组件比例、过程/总量实际水平、Minitab 模型矩阵与两侧响应逐行保存。
- MIX-PROCESS 的 Minitab `PROC` 子命令指定过程列，模型显式包含组分×过程项。
- MIX-AMOUNT 的 Minitab `MIXREG` 得到 36×6、秩6模型，而 MiniJMP 总量交叉模型为36×9、秩9；Minitab 19 的原生 MIXREG 未生成三个组分×总量项，按实际 XMATRIX 结构标记 UNSUPPORTED。
- MIX-PROCESS 在项基底一致时比较逐项 ANOVA；预测值、SE、CI/PI 由 Minitab 高精度系数与 XMATRIX 派生，不使用舍入报表值。
- 联合过程×总量 72 行的等价 REGRESS 证据另见 `mixture_v2_acceptance_report.md`；本报告保留两个独立案例。
- 官方 Session Commands 第 374–381 页定义 `MIXREG`、`PROC`、`AMOUNT`、`LOWER` 及 `PREDICT`；完整输出见 `minitab_raw.txt`。
