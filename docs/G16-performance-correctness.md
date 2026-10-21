# G16：统计计算性能与正确性优化

日期：2026-10-21（Asia/Shanghai）。本任务不执行 commit、push、merge，不升级依赖。

## 范围、来源与工作区

开始 HEAD：`38b907f0dcf62f234561838f3cca93ad0a8545ef`，开始工作区干净。已读取 G15 报告、复现步骤、基准脚本、原始测量及对应 profile，实际位置：

`C:\Users\shaoy\AppData\Local\Temp\Minijmp-G15-20261021-101528`

9 个目标源码文件逐一 SHA256 核对，均与 G15 `source-snapshot/code` 一致；未因 HEAD 不同而假定实现相同。记录见 [source-baseline.json](g16-evidence/source-baseline.json)。G15 的 `two_way` profile 实际保留的是 `two_way-n150-p5.txt`，没有 `two_way-n1500-p5.txt`；使用已有 150 点 profile 定位，并重新测量全部指定规模。其余必要证据可访问。

执行期间 G17 等其他任务在相同工作区修改数据处理代码及相关测试。本任务保留这些改动，不将其归为 G16 修复。特别是 `utilities.py`、`df_combine.py`、`dialog.py`、CSV 导入相关实现不属于 G16。共享的 G4/G11 测试仅修改 G16 对应约束，保留 G17 已有适配。

## 修复清单与实际调用覆盖

按 F01 → F11 → F02 → F04 → F06 → F08 顺序实施，每项先有旧实现数值基线，再验证并复测性能。

| 项目 | 修改 | 调用覆盖与保留的行为 |
| --- | --- | --- |
| F01 | `linear_fit.py::linear_fit` 按 X 水平一次分组，每组均值只计算一次；纯误差与饱和模型复用组数据和均值，X 水平集合也只构建一次。 | `linear_plot.fit_plot`、`Residual.linear_fit_resid_test` 均走共享实现；保留 SSPE/SSM 的原求和顺序、DFPE/DFLF、零纯误差及失拟不可用分支。NaN 不匹配任何 X 水平，沿用原 `==` 语义。 |
| F11 | `chi_sq.py::multi_pop_var_test` 的 O’Brien、Levene、Brown-Forsythe 复用原始组均值/方差/中位数；内部 ANOVA 复用各变换组均值；报告的 SD 不再重复求三次。 | `sample_test_dialog.MultiVarDialog.apply` 和直接调用共享同一实现。O’Brien 修正、变换定义、F 检验自由度、CI 和两组时追加 F 检验保留。 |
| F02 | `nonpara_cor.py::hoeffd_example` 每点复用四个比较掩码，以 `count_nonzero` 替代 Python 布尔逐项求和；`fit_dialog.print_multi_col_tables` 填充对称结果。 | 标量 `hoeffding`、单对相关对话框、多变量相关对话框均覆盖；Spearman/Kendall 同一矩阵入口也复用无序对。保留 1/4、1/2 并列秩权重、原 D/p 公式；实际计算对角线，不强制写 1/0。 |
| F04 | `binomial.py` 一次向量 PMF 供点概率、两尾、等尾、返回 PMF、绘图共用；累计未超过阈值时返回最后支持点，修复中心点 `NameError`；绘图阈值 `max(pmf)` 移出循环。`proportion_test.py` 的 Sterne、Blaker 和 LR 批量求 PMF；单比例共用同一支持集；两比例 Fisher 循环复用观测点 PMF。 | `cont_plot.cont_dist`、概率图、`Prop1SDialog`、`Prop2SDialog`、直接调用均保留现有参数。`p_sterne`、`p_blaker` 的独立入口与单比例入口共用私有计算函数，没有维护第二份检验公式。`blakerCI.py` 使用已有稳定 CDF/SF 路径，无需修改。 |
| F06 | `dist_fit.py::ABL` 一次批量 `pdf`，继续逐值 `math.log` 和原顺序求和；`compare_dist` 的最小 AICc 和相对似然总和各计算一次。 | `fit_norm`、t/Gamma/Lognormal/Exponential/Weibull 六个拟合器、`compare_dist`、`FitDistDialog` 和直方图拟合路径均走共同 ABL。保留样本标准差估计、AICc/BIC 定义、候选失败处理、排序和权重。 |
| F08 | `two_way_anova.py` 交互模型每个非空单元均值只计算一次；`GRR.py` 在 Auto 筛选和后续 AIAG/EMP 分量估计间复用同一完整模型结果。 | `Anova2WayDialog`、`grr_master`、直接 AIAG/EMP、`grr_inter`、`grr_simple`、无操作者路径均验证。原参数和默认值保留；三个内部调用入口增加私有 keyword-only 结果参数。删交互后仍独立拟合简化模型，保留 III 型 SS、不平衡设计、阈值 `p AB <= alpha`、零分量钳制和原报告协议。 |

对 `code/` 的定义和调用做有界检索，未发现需要同步替换的第二份目标实现；历史文档快照不是当前业务实现。未扩展到 G15 的 F03/F05/F07/F09/F10，也未重构 GUI、报告框架、分组公共工具或建立通用缓存。

## 正确性及重复工作约束

新增 [test_g16_statistics.py](../tests/test_g16_statistics.py)，固定从上述修改前 Git 提交读取旧源码作为数值/文本对照。旧 GRR 绑定旧双因素 ANOVA，旧单比例绑定旧二项实现，避免比较双方共同使用新实现而掩盖回归。

比较原始统计结果、返回类型/键、NaN、异常类型、报告文本及矩阵原始值；通用浮点容差为 `rel=2e-12, abs=1e-12`。还使用 SciPy 的 Levene、O’Brien 等作为独立公式参考。原有报告、GUI 路由与导出测试继续验证用户契约。

| 项目 | 数值、边界和退化输入 | 重复工作及保护测试 |
| --- | --- | --- |
| F01 | 重复/不重复 X、两水平、完美拟合、大偏移、空输入、常量 X/Y、长度不等、NaN/Inf X。 | 60 点、3 水平时 `statistics.mean` 仅 6 次（3 个总体均值加 3 个组均值）。 |
| F11 | 三组/两组、不等组长、偏态/重复值、每组最小有效大小、空组集合、单点/两点组、常数组。 | 三组各 20 点时 mean=12、variance=3、median=3；内部三次 ANOVA 各自的三组均值计入 12。 |
| F02 | 独立序列、并列秩、常量列、双常量、最小/不足样本、NaN/Inf、三个方法的矩阵文本与原始值。 | 每点恰好四个秩比较，循环内无 Python `sum`；三列矩阵调用标量方法 6 次而非 9 次，包含真实对角线。 |
| F04 | 0/全事件、p=0/1、N=0、中心点与两侧、概率输入 0/1、极端 p、三种离散检验及单比例报告。 | 整次单比例支持集 PMF 仅一次向量调用；独立 Sterne/Blaker/LR 各一次；Blaker 空尾 `min/max default` 保护仍在。旧 N=1000、p=.5、x=500 明确复现 NameError，新实现完成。 |
| F06 | 正常/空/小样本、NaN、零密度、负值、常量、部分/全部候选失败、六模型集合及排序。 | ABL 一次 PDF 调用，禁止借优化改用 `logpdf`；零密度仍为 ValueError。六模型性能样本断言六个拟合全部成功。 |
| F08 | 平衡/不平衡、空单元、NumPy 单元、退化设计、直接入口、无操作者、AIAG/EMP 的 Auto/On/Off、强交互、阈值上下相邻浮点及恰好相等。 | 单元均值次数=单元数+总体均值；完整模型最多一次、简化模型最多一次，不能用完整模型替代简化模型。 |

117 项 G16 测试连同 26 项 G3 计算约束测试，**143 passed**，见 [g16-tests.txt](g16-evidence/g16-tests.txt)。分项日志在 `g16-evidence/Fxx*-tests.txt`。各轮计数有重叠，不能相加当唯一测试数量。

G3/G9 的计算 hash 仅更新实际授权变更项；G4 对相关 GRR 函数保留旧参数及默认值检查，并检查新增参数只能是指定私有 keyword-only 参数；G11 仅放开单元 SSE 优化区，其余双因素实现继续冻结。相应数值、异常、报告及调用次数由新增测试接管，不删除计算保护而只更新快照。 一轮完整测试曾得到 2078 passed、1 failed：遗漏了 G4 另一个双因素 SSE 源码冻结位置。已按同样的最小范围适配该位置，相关 54 项检查通过，再重新运行完整套件；记录见 `full-pytest-before-last-guard-update.txt` 与 `last-guard-tests.txt`。

修改前完整 pytest：**1765 passed, 3 failed, 53 warnings**，见 [baseline-pytest.txt](g16-evidence/baseline-pytest.txt)。三项失败是执行中其他任务修改 `utilities.py` 后触发 G4/G11/G12 的旧源码冻结约束，发生在 G16 修改生产源码之前；本次没有沿用历史的启动器四失败结论。

最终完整 pytest：**2079 passed, 112 warnings in 397.33s (0:06:37)**，见 [final-pytest.txt](g16-evidence/final-pytest.txt)。`final-pytest-initial.txt` 是补丁审查发现 NaN 分组兼容性后主动中止的早期运行，不作为最终完整验证。

## 性能测量

工具：[benchmark_statistics.py](../tools/benchmark_statistics.py)。固定种子 `20261021`，`PYTHONHASHSEED=0`，BLAS/OpenMP 线程数为 1。每个热点独立启动进程，同进程按场景串行运行；每场景排除导入及输入生成，预热一次，再在 GC 后以 `perf_counter` 测三次。与 G15 每场景新进程的组织方式有所不同，不将进程启动时间计入函数耗时。

修改前使用已逐文件核对一致的 G15 源码快照重新实测，修改后使用当前实现；原始 JSON 保留三个正式样本和源码哈希。不是把 G15 的历史耗时直接当本轮基线。共 **38 个场景，228 个正式测量值**，全部满足每侧三次完成；未用失败、超时或缺失样本计算中位数。尤其 G15 的 30,000 点 GRR 只有两次，本轮已补足双方三次。

输入严格沿用 G15：先消耗一组 Normal(10,1) 数据；回归每 X 水平约 5 次重复；方差检验的 N 是**每组**点数；相关矩阵为独立正态变量；二项/单比例选 G15 正常完成的 `events=int(.49*N)`，独立 Blaker/Sterne/LR 使用中心点；六模型比较采用 lognormal(1,.25)；双因素为 5×3 水平，GRR 为 10×3 水平。中心点功能错误单独做正确性测试，不以异常耗时充当性能样本。

当前桌面同期有其他任务的测试/数据处理负载，不能声称机器负载隔离；前后与 G15 的绝对时间存在明显波动。本表只给本轮观测中位数，调用次数约束独立证明重复工作被消除，不把全部加速差异归因于硬件恒定条件。未额外测进程内存峰值，向量化仅分配支持集或逐点掩码，没有构造 N×N 样本矩阵。

完整明细见 [performance.csv](g16-evidence/performance.csv)，单位秒：

| 项目/函数 | N | 变量/组/因子口径 P | 修改前中位数 | 修改后中位数 | 观测加速比 |
| --- | ---: | ---: | ---: | ---: | ---: |
| F01 `linear_fit` | 1000 | 1 | 0.127758 | 0.004839 | 26.4× |
| F01 `linear_fit` | 3000 | 1 | 0.670895 | 0.012564 | 53.4× |
| F01 `linear_fit` | 10000 | 1 | 5.101569 | 0.038456 | 132.7× |
| F11 `multi_var` | 100 | 3 | 0.121505 | 0.002005 | 60.6× |
| F11 `multi_var` | 1000 | 3 | 7.719572 | 0.010103 | 764.1× |
| F02 `hoeffding` | 100 | 1 | 0.006177 | 0.001500 | 4.1× |
| F02 `hoeffding` | 1000 | 1 | 0.375265 | 0.014054 | 26.7× |
| F02 `hoeffding` | 3000 | 1 | 2.534112 | 0.046297 | 54.7× |
| F02 `matrix_hoeffding` | 100 | 5 | 0.118818 | 0.018221 | 6.5× |
| F02 `matrix_hoeffding` | 100 | 10 | 0.495204 | 0.076668 | 6.5× |
| F02 `matrix_hoeffding` | 1000 | 5 | 7.342153 | 0.224052 | 32.8× |
| F04 `binomial` | 1000 | 1 | 0.143568 | 0.001107 | 129.7× |
| F04 `binomial` | 10000 | 1 | 1.293535 | 0.004530 | 285.5× |
| F04 `binomial` | 50000 | 1 | 8.353895 | 0.018809 | 444.1× |
| F04 `p_blaker` | 1000 | 1 | 0.050634 | 0.000803 | 63.1× |
| F04 `p_blaker` | 10000 | 1 | 0.541603 | 0.006051 | 89.5× |
| F04 `p_blaker` | 50000 | 1 | 2.350363 | 0.028723 | 81.8× |
| F04 `p_sterne` | 1000 | 1 | 0.079137 | 0.000893 | 88.7× |
| F04 `p_sterne` | 10000 | 1 | 0.972259 | 0.003611 | 269.2× |
| F04 `p_sterne` | 50000 | 1 | 5.476385 | 0.015752 | 347.7× |
| F04 `p_likelihood_ratio` | 1000 | 1 | 0.088117 | 0.001184 | 74.4× |
| F04 `p_likelihood_ratio` | 10000 | 1 | 0.669506 | 0.008207 | 81.6× |
| F04 `p_likelihood_ratio` | 50000 | 1 | 3.638427 | 0.040360 | 90.2× |
| F04 `prop_test_1sample` | 1000 | 1 | 0.400457 | 0.050243 | 8.0× |
| F04 `prop_test_1sample` | 10000 | 1 | 3.312469 | 0.054359 | 60.9× |
| F04 `prop_test_1sample` | 50000 | 1 | 16.479264 | 0.075830 | 217.3× |
| F06 `fit_norm` | 1000 | 1 | 0.048993 | 0.002470 | 19.8× |
| F06 `fit_norm` | 10000 | 1 | 0.791396 | 0.011334 | 69.8× |
| F06 `fit_norm` | 50000 | 1 | 4.129696 | 0.054102 | 76.3× |
| F06 `compare_dist` | 1000 | 1 | 0.878546 | 0.095044 | 9.2× |
| F06 `compare_dist` | 5000 | 1 | 3.732860 | 0.580449 | 6.4× |
| F06 `compare_dist` | 10000 | 1 | 7.003509 | 1.310799 | 5.3× |
| F08 `two_way` | 150 | 5 | 0.016903 | 0.009376 | 1.8× |
| F08 `two_way` | 1500 | 5 | 0.132281 | 0.020979 | 6.3× |
| F08 `two_way` | 15000 | 5 | 6.346443 | 0.138878 | 45.7× |
| F08 `grr` | 300 | 10 | 0.060426 | 0.019452 | 3.1× |
| F08 `grr` | 3000 | 10 | 0.477256 | 0.068076 | 7.0× |
| F08 `grr` | 30000 | 10 | 23.915759 | 0.595489 | 40.2× |

环境及导入路径见 [environment.json](g16-evidence/environment.json)：项目 `.venv` Python 3.11.9、NumPy 2.4.6、SciPy 1.15.3、pandas 3.0.6、statsmodels 0.15.0。未使用 Codex bundled runtime。

复现示例（在仓库根目录使用新输出目录，避免覆盖本次证据）：

```powershell
$python = 'C:\Users\shaoy\Documents\Minijmp\.venv\Scripts\python.exe'
$env:PYTHONHASHSEED = '0'
$env:OPENBLAS_NUM_THREADS = '1'
$env:OMP_NUM_THREADS = '1'
$env:MKL_NUM_THREADS = '1'
$env:NUMEXPR_NUM_THREADS = '1'
$baselineCode = 'C:\Users\shaoy\AppData\Local\Temp\Minijmp-G15-20261021-101528\source-snapshot\code'
# 对 F01、F11、F02、F04、F06、F08 分别启动，以下为示例。
& $python tools/benchmark_statistics.py F01 --code-dir $baselineCode --output '<已有目录>\F01-before.json'
& $python tools/benchmark_statistics.py F01 --output '<已有目录>\F01-after.json'
& $python -m pytest tests/test_g16_statistics.py tests/test_g3_computation_contracts.py -q
& $python -m pytest -q --tb=short -o faulthandler_timeout=180
```

G15 临时目录今后可能被清理；修改前代码仍可从固定 Git 提交恢复到独立临时目录供 `--code-dir` 使用，不需要切换或回退当前工作区。数值测试直接读取该固定提交，不依赖临时目录。

## 实际 Patch Review 与复杂度审查

逐文件检查实际 diff、函数定义及调用位置，结合 `no-stop-gpt` Audit 复核以下新增复用机制：

- F01/F11 的组数据与统计量只在一次分析内存在；有当前消费者，不需要缓存失效、全局状态、统一分组框架或新依赖。
- F02 复用已生成矩阵行，未增加持久缓存；保留真实对角线和并列秩定义，不以其它相关方法替换 Hoeffding。
- F04 两个私有函数由独立入口和单比例入口共同使用，避免复制检验公式；继续保留端点稳定尾概率、空尾默认值及比较方向。
- F06 采用已有 SciPy 向量 PDF 和标准库 log，未改用下溢行为不同的 logpdf，也未放松候选失败保护。
- F08 借用本次分析已有完整模型结果；AIAG/EMP 都接通复用，未只修一个分支；简化模型仍实际拟合。未给外部结果建立通用缓存接口或省略必要的模型区别。
- 审查发现 F01 的 NaN 判等回归，已修正并补充混合 NaN、全 NaN 和 Inf 测试，再重新测量 F01 并重跑完整验证。空单元与 NumPy 单元也已有针对性检查。

G16 生产补丁限于 9 个目标文件；`fit_dialog.py` 只改矩阵计算，不改窗口布局、状态或交互。其余变更为本任务测试、必要计算快照、基准工具及交付证据。保留共享测试中的 G17 修改。`git diff --check` 已通过。 可直接审阅 [G16.patch](g16-evidence/G16.patch)：包含 15 个生产代码/测试/基准工具文件，仅包含 G16 改动，不含共享测试内的 G17 修改。已用 `git apply --reverse --check` 对当前文件做只读校验；未应用补丁或暂存文件。报告和原始性能数据单独交付。

最终审查结论：未发现未处理的 G16 阻断问题；没有遗漏已确认的目标实现副本，没有扩大到无关 GUI/报告/依赖改造。此结论针对 G16 改动，不是对同时进行的其他任务做全面验收。

## 保留限制与数值风险

1. Hoeffding 标量仍为 O(N²)，当前优化减少比较与 Python 循环成本，未引入并列秩敏感的排序树算法。没有把本次有限规模结果外推为无限大数据性能保证；矩阵之后的 Pearson 散点图构建也不属于本次测量。
2. 保留原统计定义和错误语义。`ln(pdf)` 在极端尾部下溢仍可能使候选拟合失败；未改变非正态分布 AD 近似 p 值校准、LR 原公式或其它既有定义。
3. `binomial` 的旧辅助字段 `not equal p` 保留原双尾相加定义，中心点可能重复计入中心概率；它不是单比例正式报告使用的 Blaker p 值。本次仅修 G15 指定的中心点异常，未擅自换检验定义。
4. 浮点数兼容性由固定旧实现、独立参考、原报告/导出回归和明确容差支持；未声称不同平台、不同库版本逐位一致。没有为追求最短代码改用 `SST-SSPE`、不同方差自由度或不同拟合估计器。
5. 未额外进行手工 GUI 点选、跨平台/全部 DPI 或长期内存验证；GUI 调用与导出协议由相关测试及完整 pytest 覆盖。完整工作区同时存在其他任务改动，不能将所有 Git diff 或测试增长归功于 G16。
