# BIN-RSM 原生 M2 与终点 Fisher 的离线数值溯源

日期：2026-10-31（Asia/Shanghai）  
范围：仅复核冻结 BIN-RSM 归档；未启动 Minitab/COM、未运行 `binary/verify.py`、未调用生产拟合算法。

## 结论

- 原生归档 M2 与终点 Fisher 协方差的最大元素差为 **1.5358653758512641e-10**，位置 **A*C × A*C**；该元素的相对差为 **9.9240531978081704e-09**，以 M2 最大绝对元素归一的矩阵相对差为 **6.911394191330687e-09**。Frobenius 差范数为 `3.2425047659201749e-10`。
- 按同一终点 FITS 信息矩阵，Cholesky/solve/加权 QR/SVD 的协方差最大两两差仅 **5.2041704279304213e-17**，约比 M2 偏差小 **2951220.3666666667** 倍；条件数为 `22.506584608790376`。标准双精度求解器差异不足以解释 M2 偏差。
- 从 beta=0 开始的离线 Newton 轨迹中，前一权重状态 beta_4 的协方差与 M2 最大差为 `5.7018771648653654e-11`，比终点 Fisher 更接近约 `2.6936135792527716` 倍；但仍比求解器间差异大约 `1095636.1333333333` 倍，且没有重现 M2。该轨迹不是 Minitab 内部日志，不能据此认定 Minitab 使用 beta_4 权重。
- 归档中的 4 项 BIN-RSM Wald z 在第二阶段修复结果中仍全部为 **FAIL**，原有 `abs_tol=rel_tol=1e-9` 不变。现有证据排除了普通线性求解舍入作为充分解释；权重取值时点有数值上的接近迹象，但**无法唯一归因 Minitab 内部实现，根因保留未知**。不建议据此修改 MiniJMP 终点 Fisher 生产算法。

## 证据分层与对齐

- **DIRECT（冻结归档）**：Minitab `matrix`（M1）、FITS、系数、SECOEFFICIENTS 与 `xpw_inverse`（M2）；MiniJMP 当前 JSON 的行、拟合概率和矩阵；输入 CSV 的 events/trials/settings；原比较及第二阶段修复比较。Minitab 命令顺序来自同目录 `session_commands.txt` 的 BRSREG `TERMS`。
- **DERIVED（本脚本）**：按 `(point_key, occurrence)` 把 14 行输入、Minitab `design_rows`/M1/FITS 与 MiniJMP 行逐一配对。按 [1,A,B,C,A²,B²,C²,A×B,A×C,B×C] 重构 X，并与两个归档矩阵逐元素核对；counts 也逐行相等。详细行键、三个概率来源和 10 列 M1 见 `aligned_rows.csv`。
- 对齐结果：14 行；X 形状 `14×10`、rank `10`；M1 对重构矩阵最大绝对差为 `0`。重复中心点保留 occurrence 1/2。Minitab FITS 与 `expit(X beta_Minitab)` 最大差 `1.1102230246251565e-16`；Minitab FITS 与 MiniJMP 归档最终 p 最大差 `1.1102230246251565e-16`。每行均使用 grouped-binomial events/trials（合计 trials=`1260`）。
- M2 对称性最大误差 `0`；`sqrt(diag(M2))` 与 10 个直接归档 SE 逐项完全相同（最大差 `0`）。以 M2 对角 SE 派生的原生 z 与冻结 Minitab 比较值最大差不超过 `2e-15`。

## M2 与终点 Fisher 及求解误差

每个概率候选均使用 `wᵢ = trialsᵢ pᵢ(1-pᵢ)`、`I = XᵀWX`、`V = I⁻¹`。默认协方差用 Cholesky 两次三角求解；交叉方法分别对同一信息矩阵使用 `solve`、对加权设计矩阵做 QR 和 SVD。没有用显示舍入值。

| 候选概率 / 权重来源 | 求解 | max_abs(M2−V) | 位置 | 该位置相对差 | max差/max_abs(M2) | Frobenius | solve_residual_inf |
|---|---|---:|---|---:|---:|---:|---:|
| FITS_DIRECT_Cholesky | Minitab FITS (DIRECT) / cholesky | 1.535865375851e-10 | A*C × A*C | 9.924053197808e-09 | 6.911394191331e-09 | 3.242504765920e-10 | 4.367251710181e-15 |
| BETA_EXPIT_Cholesky | expit(M1 × Minitab beta) / cholesky | 1.535865375851e-10 | A*C × A*C | 9.924053197808e-09 | 6.911394191331e-09 | 3.242504773695e-10 | 4.430192801379e-15 |
| MINIJMP_FINAL_P_Cholesky | MiniJMP archived final p / cholesky | 1.535865375851e-10 | A*C × A*C | 9.924053197808e-09 | 6.911394191331e-09 | 3.242504762623e-10 | 3.446822119317e-15 |
| FITS_DIRECT_SOLVE | Minitab FITS (DIRECT) / solve | 1.535865410546e-10 | A*C × A*C | 9.924053421988e-09 | 6.911394347456e-09 | 3.242504777250e-10 | 1.399921845113e-15 |
| FITS_DIRECT_QR | Minitab FITS (DIRECT) / qr | 1.535865445240e-10 | A*C × A*C | 9.924053646167e-09 | 6.911394503581e-09 | 3.242504844765e-10 | 2.380817341653e-15 |
| FITS_DIRECT_SVD | Minitab FITS (DIRECT) / svd | 1.535865531976e-10 | A*C × A*C | 9.924054206617e-09 | 6.911394893894e-09 | 3.242504847463e-10 | 3.415059669208e-15 |
| IRLS_BETA_0 | offline Newton state beta_0 / cholesky | 4.365079211493e-03 | A*C × A*C | 2.820512749263e-01 | 1.964285645172e-01 | 8.489536289504e-03 | 3.663735981263e-15 |
| IRLS_BETA_1 | offline Newton state beta_1 / cholesky | 1.422920271048e-03 | A*C × A*C | 9.194254150324e-02 | 6.403141219716e-02 | 2.962787274608e-03 | 4.081530263627e-15 |
| IRLS_BETA_2 | offline Newton state beta_2 / cholesky | 1.392317430319e-04 | A*C × A*C | 8.996512715956e-03 | 6.265428436434e-03 | 2.953101644475e-04 | 1.391212777231e-15 |
| IRLS_BETA_3 | offline Newton state beta_3 / cholesky | 1.243045042431e-06 | A*C × A*C | 8.031983430805e-05 | 5.593702690941e-05 | 2.619124209902e-06 | 3.827165623869e-15 |
| IRLS_BETA_4 | offline Newton state beta_4 / cholesky | 5.701877164865e-11 | A*C × A*C | 3.684289883364e-09 | 2.565844724189e-09 | 1.211889314808e-10 | 1.859784449802e-15 |
| IRLS_BETA_5 | offline Newton state beta_5 / cholesky | 1.535865306462e-10 | A*C × A*C | 9.924052749449e-09 | 6.911393879080e-09 | 3.242504718331e-10 | 3.939681840606e-15 |

“该位置相对差”以该矩阵元素两边绝对值的较大者作分母；“max差/max|M2|”是整个矩阵按最大 M2 元素归一的相对差，避免近零非对角元导致逐元素相对误差失真。`||IV−I₁₀||∞` 是候选协方差求解残差的无穷范数。

在 Minitab FITS 的同一终点信息矩阵下，native M2 的 `||I M2−I₁₀||∞` 为 **2.3878607319660495e-08**，而各求解器自身残差如下：

| 求解 | 相对 Cholesky 的 max_abs(ΔV) | solve_residual_inf | 协方差非对称 max |
|---|---:|---:|---:|
| cholesky | 0.000000000000e+00 | 4.367251710181e-15 | 3.469446951954e-18 |
| solve | 5.204170427930e-17 | 1.399921845113e-15 | 8.673617379884e-18 |
| qr | 3.469446951954e-17 | 2.380817341653e-15 | 1.734723475977e-18 |
| svd | 3.122502256758e-17 | 3.415059669208e-15 | 1.734723475977e-18 |

四种求解结果最大两两差 `5.2041704279304213e-17`，信息矩阵条件数 `22.506584608790376`（加权设计矩阵条件数 `4.7441105181888821`）。M2 对终点信息矩阵的残差远大于这些解法的残差，因此不能把差额归为常规双精度求解器舍入。

## IRLS 权重状态候选（仅离线重建）

以 beta₀=0 起步，每一状态先计算 p(betaₖ)、Wₖ 和候选协方差，再按 grouped-binomial Newton 步更新 betaₖ₊₁。`irls_trace.csv` 保留每态 beta、更新前后 p/W、步长与 M2 残差；更新后的状态协方差对应 `covariance_comparison.csv` 中下一 beta 状态的完整信息矩阵和协方差。其中 k=4 是收敛前一权重状态，k=5 已到终点。此处是 MiniJMP/离线参考重建，不是 Minitab 迭代日志。

| 权重状态 k | Newton 步 max | max_abs(M2−Vₖ) | Frobenius | Δz A | Δz A² | Δz B² | Δz A*C |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 6.111111111111e-01 | 4.365079211493e-03 | 8.489536289504e-03 | 1.011327200725e+00 | 3.451523753524e-01 | -3.451523753524e-01 | 1.003998332899e+00 |
| 1 | 1.249698569008e-01 | 1.422920271048e-03 | 2.962787274608e-03 | 2.662239305758e-01 | 8.467583870172e-02 | -8.467583870171e-02 | 2.752762274022e-01 |
| 2 | 1.250931379911e-02 | 1.392317430319e-04 | 2.953101644475e-04 | 2.358165221948e-02 | 7.635691029198e-03 | -7.635691029194e-03 | 2.523365361004e-02 |
| 3 | 1.124455392190e-04 | 1.243045042431e-06 | 2.619124209902e-06 | 2.061463885710e-04 | 6.775843155271e-05 | -6.775843155093e-05 | 2.237754304071e-04 |
| 4 | 8.765271080618e-09 | 5.701877164865e-11 | 1.211889314808e-10 | -9.693563285396e-09 | -3.156020333961e-09 | 3.156022998496e-09 | -1.026401275084e-08 |
| 5 | 1.987827891710e-16 | 1.535865306462e-10 | 3.242504718331e-10 | -2.561034051496e-08 | -8.395756090351e-09 | 8.395759643065e-09 | -2.764728534999e-08 |

Δz 定义为该状态协方差配 MiniJMP beta 得到的 z 减去原生 M2 的 Minitab z。前态 k=4 的 p 与 Minitab FITS 最大差为 `2.5003770165454853e-09`；它在 M2 最大元素上更接近，但不等于 M2，残差也远超解法噪声。会话输出只记录 `ITERATION 200`、`CTOLERANCE 1e-10` 等命令/报告设置，没有 beta、逐轮 p 或逐轮 W，故无法验证 Minitab 的起始值、停止态或协方差计算时点。

### 对角方差、SE 与 z 的误差传递

| 项 | M2 方差 | M2−V（终点） | M2 SE−SE终点 | M2−V（IRLS前态） | M2 SE−SE前态 |
|---|---:|---:|---:|---:|---:|
| 截距 | 0.022222222222222227 | -2.428612866368e-17 | -8.326672684689e-17 | 1.734723475977e-17 | 5.551115123126e-17 |
| A | 0.0069940475758248303 | -4.322278819580e-11 | -2.584154557006e-10 | -1.635991082188e-11 | -9.781075949178e-11 |
| B | 0.0062499999924048189 | -7.595181428233e-12 | -4.803614450655e-11 | -3.010684583582e-12 | -1.904124080632e-11 |
| C | 0.0069940475834424053 | -3.560521408957e-11 | -2.128723863848e-10 | -1.334187794966e-11 | -7.976690141742e-11 |
| A² | 0.015674603127063171 | -4.754000665352e-11 | -1.898589063742e-10 | -1.787060777136e-11 | -7.136924384810e-11 |
| B² | 0.015674603127063168 | -4.754001359242e-11 | -1.898589063742e-10 | -1.787060777136e-11 | -7.136921609252e-11 |
| C² | 0.015674603130159545 | -4.444363627121e-11 | -1.774930202814e-10 | -1.666014201596e-11 | -6.653502748755e-11 |
| A*B | 0.012499999972504339 | -2.749566026250e-11 | -1.229643331602e-10 | -1.089663602405e-11 | -4.873124126448e-11 |
| A*C | 0.015476190322603936 | -1.535865375851e-10 | -6.172926753090e-10 | -5.701877164865e-11 | -2.291689754630e-10 |
| B*C | 0.012499999997114951 | -2.885048103196e-12 | -1.290233198059e-11 | -1.146086697768e-12 | -5.125455615484e-12 |

固定 beta 时，`z=beta/SE`，小误差满足 `Δz/z ≈ −0.5·ΔV/V`；因此方差的微小相对差会以约一半幅度传到 z 的相对差，而非证明系数或响应行错位。上表的 signed `M2−V`、SE 差与下表 z 差保留方向；逐项完整值和 10×10 协方差元素见 `covariance_comparison.csv`。

## 原有四项 1e-9 验收状态

| 项 | Minitab 原生 M2 z | MiniJMP 修复后终点 Fisher z | MiniJMP−Minitab | 归档绝对误差 | 归档相对误差 | 原状态 |
|---|---:|---:|---:|---:|---:|---|
| A | 8.288218084140853 | 8.2882180585305125 | -2.561034051496e-08 | 2.5610340514958807e-08 | 3.0899694306986305e-09 | FAIL |
| A² | 5.536396485458897 | 5.5363964770631409 | -8.395756090351e-09 | 8.3957560903513695e-09 | 1.5164658297870203e-09 | FAIL |
| B² | -5.5363964854588987 | -5.5363964770631373 | 8.395761419422e-09 | 8.3957614194218877e-09 | 1.5164667923392021e-09 | FAIL |
| A*C | 5.571773199981684 | 5.5717731723343977 | -2.764728623816e-08 | 2.7647286238163815e-08 | 4.9620264942325181e-09 | FAIL |

第二阶段验收中，原 16 项 FAIL 有 12 项修复通过，BIN-RSM 这 4 项仍为 FAIL。本调查未改冻结比较、第二阶段 CSV/报告、容差或七项 supplemental 汇总。IRLS 候选在某些项上可能满足数值门槛，只说明假设权重态的数值结果，不改变任何已归档验收状态。

## 因果判断与后续

- **已排除到何种程度**：行错配、M1 编码/列序差异、events/trials 错配、FITS 与 beta 响应概率不一致均被逐项核对排除；Cholesky、solve、QR、SVD 的普通双精度解法差异约为 1e-17 量级，远小于 M2 差值。
- **仍未知**：前态权重候选比终点更接近 M2，但不在求解噪声内重现；现有证据不能把差异唯一归因于 Minitab 的权重取值时点，也不能判定其他未导出的内部数值处理。根因置信度：对“普通求解器舍入不足以解释”高；对“前态权重是 Minitab 根因”低/未证实。
- **建议**：不修改当前终点 Fisher 生产实现，不放宽 1e-9；继续保留 4 项 FAIL。只有后续需要对 Minitab 内部来源作唯一归因或要求关闭这 4 项时，才值得另行获取可验证的原生迭代/权重证据；当前归档不能替代该证据。

## 来源完整性与复跑

脚本只读下列归档，并在执行前后核对 SHA-256；自检还断言行键、矩阵、SE、原 z、IRLS 收敛和输出行数。重跑命令（项目 Python）：

```powershell
& (Resolve-Path '.venv\Scripts\python.exe').Path -B 'Out\minitab19_parity\supplemental\binary\fisher_diagnosis\m2_investigation\investigate_m2.py'
```

| 冻结来源 | SHA-256 |
|---|---|
| `Out/minitab19_parity/supplemental/binary/bin_rsm_input.csv` | `a2bc13472b725181d835211a7bee254a38c72ecee78cd59117287f090e78167e` |
| `Out/minitab19_parity/supplemental/binary/minitab_results.json` | `b59c704ca8b5ab6ac1a311cecf157ed613f3c2fca6a974b15db612b263cc62b2` |
| `Out/minitab19_parity/supplemental/binary/minijmp_results.json` | `1ca75908a515fb8760c296c31bc4a1359fb8a210a02914c88135629a39b3a7a1` |
| `Out/minitab19_parity/supplemental/binary/comparison.csv` | `9f780b016002d62f8630db56d2b640ee2751b82e4364d3a7919206697d9e1f52` |
| `Out/minitab19_parity/supplemental/binary/session_commands.txt` | `feabe735483ce9697a1963b07cfd6b36e718a8a1aaded0abd8ffdfee9a291361` |
| `Out/minitab19_parity/supplemental/binary/minitab_raw.txt` | `44896b1a5113a796ba397f834bd3ba312643be9c51098af53d324b85a5e8ef24` |
| `Out/minitab19_parity/supplemental/binary/verify.py` | `6893e2b4d44942dbf6eb00b21d83a9465d63b219cdad6773f9f8dfdd9c8b57e7` |
| `Out/minitab19_parity/supplemental/binary/acceptance.md` | `e1bc39546562587cc7c717cbd6706aab72420536ad2a799119e9309e71271427` |
| `Out/minitab19_parity/supplemental/binary/fisher_diagnosis/fisher_diagnosis.csv` | `e30889d5be38deafdc3cbd18c4036a0a008c4349665f5a3d3212d6caa588ebfd` |
| `Out/minitab19_parity/supplemental/binary/fisher_diagnosis/fisher_diagnosis.py` | `fa7ffed1a325ec846aa599d80ba5b529546f2256f5f41d41d47519dcefa6193a` |
| `Out/minitab19_parity/supplemental/binary/fisher_diagnosis/acceptance.md` | `793a1999984db8b96e6017cf3e7481f061689f69a9673896c56effe878a09f18` |
| `Out/minitab19_parity/supplemental/binary/fisher_diagnosis/repair_acceptance.md` | `6232e72abc4b1b0aa23962be6f1daedc2eae7f08d97f9238ebe1993d73ab18ec` |
| `Out/minitab19_parity/supplemental/binary/fisher_diagnosis/repaired_comparison.csv` | `ed76a17fb7ff24607ba65be55db732d61abd0845cf36ae36dd2893b551e348ca` |
| `Out/minitab19_parity/supplemental/binary/fisher_diagnosis/repaired_comparison.py` | `21042edd439cad8ccfe13a2e7939ed2f1ebd9011d78fb41b8417277910ca1232` |
| `Out/minitab19_parity/supplemental/supplemental_summary.csv` | `f55427be1b80f54eafb33f80e1fc7c1a6f50f0a8c62e95ceee42d04e67328eb0` |
| `Out/minitab19_parity/supplemental/supplemental_acceptance.md` | `77988d410bed880c055545f44d2b994a6f732f1fc88d74bf244fc4ef2c0a9e48` |

输出：`aligned_rows.csv`（14 行键、响应、概率和 M1），`covariance_comparison.csv`（每个候选的完整 10×10 M2−V、求解残差及对角 SE/z），`irls_trace.csv`（更新前后状态）。
