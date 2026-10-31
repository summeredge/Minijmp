# Minitab 19 动态 Taguchi 与控制×噪声稳健对标

## 结果

唯一比较项：57（PASS 57 / FAIL 0 / N/A 0 / UNSUPPORTED 0）。
Minitab 来源：DIRECT 31、DERIVED 26、DISPLAY 0。

- TAG-DYNAMIC: PASS 28 / FAIL 0 / N/A 0 / UNSUPPORTED 0。
- TAG-ROBUST: PASS 29 / FAIL 0 / N/A 0 / UNSUPPORTED 0。

- TAG-DYNAMIC：4 个控制组合斜率为 8、20、20、32；目标斜率 20 有两组并列，Minitab 与 MiniJMP 推荐一致。
- TAG-ROBUST：16 个运行覆盖 4 个控制组合×4 个噪声条件；较小为优 S/N 的推荐设置为 A=low、B=high。

## Minitab 19 实际命令

- TAG-DYNAMIC:

```text
OADESIGN 4 2 2; DESIGN; SNAME "S"; SLEVEL 1 2 3.
ROBUST C4 = C1 C2; DYNAMIC C3; NOREF; TSN; TSLOPES; TSTDS; ASN; ASLOPES; ASTDS; SNRATIO C5; SLOPES C6; INTERCEPTS C7; STDEVS C8.
```

- TAG-ROBUST:

```text
ROBUST C5 = C1 C2; LOWER; TSN; TMEANS; TSTDS; ASN; AMEANS; ASTDS; SNRATIO C6; MEANS C7; STDEVS C8.
```

## 口径与限制

- TAG-DYNAMIC 使用 `NOREF`，双方均在每个控制组合内估计自由截距；比较斜率、截距、`sqrt(MSE)` 与动态 S/N。Minitab `STDEVS` 对应回归残差标准差，不是三个信号响应的样本标准差。
- 动态 S/N 使用 `10*log10(slope^2/MSE)`；未使用 Minitab 未提供的 MiniJMP adjusted 设定。最佳目标斜率从同一 `TSLOPES` 数据派生，不称为自动目标优化命令。
- TAG-ROBUST 以 A/B 为控制因子，N1/N2 是四个外表噪声组合；每个控制设置的四个响应值进入 `ROBUST ... LOWER`，按较小为优计算 S/N。噪声列保留用于条件映射，没有当作控制因子拟合。
- 不把控制×噪声 OLS 响应模型与 `ROBUST` 的组内噪声稳健统计混为一谈；本轮只对齐均值、样本 SD、较小为优 S/N 及基于主效应响应表的推荐设置。
- Minitab COM 存储列中的 `1.23456e30` 是缺失哨兵；其余直接值按控制组合映射。
- 官方 Session Commands 第 414–419 页定义 `SNAME/SLEVEL`、`DYNAMIC/NOREF`、`TSLOPES`、`SLOPES` 与 `STDEVS`；完整运行回传见 `minitab_raw.txt`。
