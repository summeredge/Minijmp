# Phase 3 Minitab 19 原生对标补验

2026-11-20 · 固定案例 · Minitab 19.1.0.1

## 环境与证据

- 已访问 `D:\Program\Minitab 19\Mtb.exe`，文件版本为 19.1.0.1，与 Phase 4 和 Phase 6 冻结版本一致。注册项 `Mtb.Application` 的 CLSID 为 `{6265486C-4A08-4B4E-9713-C2CD85F1F515}`，LocalServer32 为 `"D:\Program\Minitab 19\Mtb.exe" /19_1`。
- 项目 `.venv\Scripts\python.exe` 为 Python 3.11.9 x64，pywin32 312、`pythoncom` 和 `win32com.client` 可用。现有 COM 探针用 `DispatchEx` 新建工作簿，核实 AppPath 和进程映像，执行 `DESCRIBE C1.` 并从 `OutputDocument.Text` 回读 N=6、均值 3.500、标准差 1.871。启动前和释放后均无 Mtb.exe，未重注册 COM。
- 本轮只采集缺失案例，复用了项目的独立 COM worker、输出捕获及 Phase 6 缺失值加载。归档版本、原生命令、输出、输入及 DSD 工作表列见 [原生记录](../../Out/statistics_minitab19_parity/phase3/native_followup_20261120.json)。[逐字段比较](../../Out/statistics_minitab19_parity/phase3/comparison_followup.csv)按原生单字段显示精度核验。Phase 4–6 历史原始输出和历史判定均保留。

## G05 单标准差 Bonett · PASS

Phase 4 `one_variance_right` 已以同一组八个样本、σ₀=3、90% 置信记录 Bonett 右尾 p=0.203 和 90% 下限 2.72。新执行 `ONEV`、`STEST 3`、`ALTERNATIVE -1` 得左尾 p=0.709、90% 上限 5.24。旧实现用另一尾取补，得到 0.796680，超出显示容差。修复后左右尾分别反解上界和下界，p 为 0.709132 与 0.203322。补充原生右尾试验在 σ₀=4 和 12 时分别得到 0.866 和 1.000，修复后同样通过。原双侧 p=0.406641、双侧区间 (2.492784, 6.059838)、单侧界和卡方计算保持原口径。用四个原生 p 值做回归，覆盖跨侧、反向和无下界交点。 [Phase 4 冻结参考](../../Out/statistics_minitab19_parity/phase4/minitab_reference.csv) · [Minitab Bonett 公式](https://support.minitab.com/en-us/minitab/help-and-how-to/statistics/basic-statistics/how-to/1-variance/methods-and-formulas/methods-and-formulas/)

## G03 分布拟合 · PASS / NOT_RUN

Phase 6 的 `normal_ties` 和 `right_skew_ties_missing` 有正态与对数正态的参数点估计和百分位数记录。本轮在两个冻结输入上分别用 `DCAPA`、`RESTIMATE`、`RPTILE 5 50 95`、`CONFIDENCE 95` 核对，去掉旧命令的 `NOCI` 后仍只输出位置、尺度点估计及百分位数表。四种拟合的参数点估计、5%／50%／95% 百分位数及其 SE、95% 上下界均通过。正态采用均值及样本标准差，原生表标记尺度为调整后的 MLE。两参数对数正态在 ln(X) 上估计位置与尺度，百分位、Delta 法 SE 及置信界均以原尺度输出。含缺失案例保留了原工作表位置，纳入 13 个有效值。

| 冻结输入 | 原生正态位置 / 尺度 | 原生对数正态位置 / 尺度 |
|---|---|---|
| normal_ties | 62.55000 / 4.24234 | 4.13363 / 0.07002 |
| right_skew_ties_missing | 6.84615 / 10.59753 | 1.32400 / 0.99331 |

目标版本未取得原生参数 SE/CI 字段。已核对两种分布的 `DCAPA RESTIMATE` 参数表和 `RPTILE` 表，后者的 SE/CI 对应百分位数。其他原生入口能否提供同口径的拟合参数 SE/CI 尚无证据，因此保留 NOT_RUN。 [Phase 6 原生输出](../../Out/statistics_minitab19_parity/phase6/minitab_raw_outputs.txt) · [会话命令参考](https://support.minitab.com/en-us/minitab/session-command-help/)

## G07 非参数容差区间 · PASS / METHOD_DIFF

原生入口为「统计 → 质量工具 → 公差区间（正态分布）」。`TOLINTERVALS` 同时报两种方法，本轮比较独立的「非参数方法」列和「取得的置信度」。`ITYPE 0/-1/1` 分别为双侧、单侧下限、单侧上限。

| 1–100，覆盖 90%，目标置信 95% | Minitab | MiniJMP | 状态 |
|---|---|---|---|
| 双侧 | [2, 98]，97.6% | [2, 99]，99.216% | METHOD_DIFF |
| 单侧下限 | 5，97.6% | 5，97.629% | PASS |
| 单侧上限 | 96，97.6% | 96，97.629% | PASS |

Minitab 双侧允许分位秩向下取整后形成非对称秩，MiniJMP 选满足目标的最大对称秩。对原生秩 (2, 98) 的覆盖用独立 Beta 间距分布复算得 97.629%，与原生显示一致。样本量 2–10 时两边最高可达置信度相符。Minitab 返回样本极值并显示不足 95% 的实际置信度，MiniJMP 留空端点并显示最高可达置信度。样本量 1 时原生提示数据不足，MiniJMP 同样不给出端点。 [Minitab 容差区间公式](https://support.minitab.com/en-us/minitab/help-and-how-to/quality-and-process-improvement/quality-tools/how-to/tolerance-intervals-normal-distribution/methods-and-formulas/methods-and-formulas/)

## G08 13 连续 + 3 分类 DSD · PASS / METHOD_DIFF

Minitab 19 用 `DSDESIGN 16` 创建 13 个连续及 3 个文本二水平因子，完整重复 1 次，无额外中心点，未指定 `RANDOMIZE`。工作表标准序等于运行序 1–34。与 MiniJMP 生产入口 `create_dsd` 的标准序比较，两边均有 32 个筛选点和 2 个伪中心点（标准序 33、34），连续水平 −1/0/1、分类水平 Low/High 一致。含截距主效应秩均为 17，主效应与两因子交互列交叉积均为 0，加入全部两因子交互后秩均为 33，因此主效应满秩，交互整体不可同时独立估计。

按同名因子和固定水平编码比较，原生与 MiniJMP 的逐行序列及点集不同，34 个点中精确重合为 0。这是固定编码下的构造差异，未验证重新标记因子或反转水平后是否等价。保留已独立验证的 MiniJMP 构造。

## G06 多样本方差 · PASS / METHOD_DIFF

Phase 4 `VARTEST` 的三组标准差 95% Bonferroni 联合区间共六个端点通过。Minitab 全局多重比较是图形 MC 检验。它用样本对合并峰度计算 Bonett 对数方差比的标准误，以最小二乘拟合各组区间宽度，对各对使用标准正态极差分布调整，最后取最小的成对 MC p 为全局值。冻结输入为三个等量组（各 8 个观测），独立复算 0.965541768，与原生 0.966 一致。MiniJMP 的自选 Bonett 对数尺度成对检验使用各组峰度和 Bonferroni 调整，仍按原方法报告。 [Minitab 技术论文，§2–3.2](https://support.minitab.com/en-us/minitab/media/pdfs/translate/Multiple_Comparisons_Method_Test_for_Equal_Variances.pdf) · [Phase 4 原生输出](../../Out/statistics_minitab19_parity/phase4/minitab_raw_outputs.txt)

## G09 二元 Logistic · PASS / METHOD_DIFF

冻结原生 `GZLM` 输入以每行一个 Bernoulli 试验表示。36 行、2 个参数，残差 df=34。该表示的饱和模型对数似然为 0，所以 GOF 偏差与模型偏差都等于 −2lnL=40.049663。独立用拟合概率复算 Pearson χ²=36.570667，代入 χ²(34) 得 p=0.219475 和 0.350240，符合原生报告。稀疏 Bernoulli 数据的渐近 GOF p 受每行试验次数影响；这些数值作为口径复算证据。

| 字段 | 原生 | MiniJMP 或用其拟合概率独立复算 | 状态 |
|---|---|---|---|
| 偏差 R² / 调整偏差 R² / AICc | 19.03% / 17.01% / 44.41 | 19.028% / 17.006% / 44.4133 | PASS |
| 逐行 Bernoulli 偏差 / Pearson | 40.05 / 36.57，df 34，p 0.219 / 0.350 | 40.0497 / 36.5707，df 34，p 0.219475 / 0.350240 | PASS |
| 按六个协变量模式聚合 | 冻结原生逐行口径 | 0.2354 / 0.2437，df 4，p 0.993596 / 0.993151 | METHOD_DIFF |
| Hosmer–Lemeshow | χ² 0.24，df 4，p 0.993 | χ² 0.2437，df 4，p 0.993151 | PASS |

HL 独立按概率排序尝试分十组，并列保留在同一组，此例实际六组。聚合 GOF 继续按真实设计矩阵行识别重复，无重复模式时不给有效 p。 [Minitab 数据格式与 GOF](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/regression/supporting-topics/logistic-regression/how-data-formats-affect-goodness-of-fit-in-binary-logistic-regression/) · [Minitab GOF 公式](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/regression/how-to/fit-binary-logistic-model/methods-and-formulas/goodness-of-fit-statistics/) · [Phase 4 原生输出](../../Out/statistics_minitab19_parity/phase4/minitab_raw_outputs.txt)

## 重放与范围

```powershell
$python = (Resolve-Path '.venv\Scripts\python.exe').Path
& $python Out/minitab19_parity/verify_minitab19_com.py
& $python -X utf8 Out/statistics_minitab19_parity/phase3/verify_phase3_native_followup.py "$env:TEMP\minijmp-phase3-native-replay.json"
& $python -X utf8 Out/statistics_minitab19_parity/phase3/compare_phase3_native_followup.py
& $python -m pytest tests/test_g2_hypothesis_reports.py -q
```

采集脚本要求新的输出路径。比较脚本读取仓库冻结的新证据，仅更新本轮比较 CSV。比较共 124 PASS、37 METHOD_DIFF、4 NOT_RUN、0 FAIL。G05 定向回归 82 项通过。比较范围限于固定案例和所列字段。
