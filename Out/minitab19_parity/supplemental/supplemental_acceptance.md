# MiniJMP × Minitab 19 supplemental DOE 数值对标验收

日期：2026-10-31；Minitab 版本：19.1.0.1。结论：七项任务均已执行，记录保留真实差异与版本限制。

所有 supplemental 比较按 (case_id, section, term, statistic) 去重：原始行 2941，唯一项 2935，重复键 6；重复行取值一致，冲突 0。
唯一项 PASS/FAIL/N/A/UNSUPPORTED：2891/16/23/5。Minitab DIRECT/DERIVED/DISPLAY 来源标记：1441/1328/0（来源标记可能重叠）。

## 七项任务状态

|任务|状态|唯一项|PASS|FAIL|N/A|UNSUPPORTED|
|---|---:|---:|---:|---:|---:|---:|
|任务 1：DSD 筛选设计与逐步选模|**PASS**|1341|1341|0|0|0|
|任务 2：一般全因子与多水平 ANOVA|**PASS**|319|318|0|1|0|
|任务 3：正规部分因子与 PB Foldover|**PASS**|587|584|0|3|0|
|任务 4：DOE 二元响应|**FAIL**|195|177|16|2|0|
|任务 5：D-optimal、Distance-based 与增补|**PASS**|18|18|0|0|0|
|任务 6：动态 Taguchi 与控制×噪声稳健分析|**PASS**|57|57|0|0|0|
|任务 7：Mixture 过程变量与总量变量|**PARTIAL**|418|396|0|17|5|

### 任务 7 的两类证据

- 按目标要求的独立案例：MIX-PROCESS 34 PASS；MIX-AMOUNT 1 UNSUPPORTED。独立案例共 35 项，0 FAIL。
- 另有 72 行联合 v2 压力案例，不替代上述两案：22 项 MiniJMP/独立夹具 PASS；SLDESIGN 146 PASS/1 UNSUPPORTED；MIXREG_NATIVE 4 PASS/2 UNSUPPORTED；REGRESS_EQUIVALENT 190 PASS/17 N/A/1 UNSUPPORTED。

## 真实差异与 Minitab 19 限制

- Binary Logistic 保留 16 项 FAIL：BIN-FACTORIAL 12 项，BIN-RSM 4 项。前者的标准误有约 2.12e-7 的最大绝对差；后者 4 个 Wald z 最大绝对差约 2.72e-8。未改算法或放宽容差。
- MIX-PROCESS 原生 MIXREG 与 MiniJMP 6 项模型空间一致，34 项比较全通过；ANOVA 项统计由 Minitab 高精度 XMATRIX/系数派生，预测值及 CI/PI 由高精度矩阵派生。
- 独立 MIX-AMOUNT 中，Minitab 19 MIXREG AMOUNT 生成 36×6、秩6矩阵；MiniJMP v2 总量交叉模型为 36×9、秩9。未把不同模型算作 FAIL，记录为 UNSUPPORTED。
- 联合案中，SLDESIGN 拒绝 PROC 加多个 TOTAL；MIXREG 拒绝 PROC 与 AMOUNT 同时使用。将 MiniJMP 15 列矩阵显式交给 Minitab REGRESS NOCONSTANT 后，72×15 等价模型比较为 190 PASS、17 N/A、1 UNSUPPORTED；N/A 来自无 pure-error df，1 项为 Minitab 直接预测值存储限制。

## 最终批量重放与冻结基线

- 成功案例最终重放：DSD、General Factorial、Foldover、Optimal、Dynamic Taguchi、Mixture 独立两案及 Mixture 72 行联合案。Task 4 有真实 FAIL，因此按成功案例规则未重放，原始失败证据保留。
- verify_reference_baseline.py 只运行一次离线复验；八案唯一项 2,559 PASS、0 FAIL、44 N/A、2 UNSUPPORTED；DIRECT/DERIVED/DISPLAY 为 1,655/625/61。manifest 与归档证据哈希均核对通过，Minitab COM 未启动。
- 独立重放期间创建的 Minitab 实例均记录退出；联合案最后 PID 11716 已退出、启动前无既有 Minitab PID。本轮后未发现 Mtb.exe。
- 仍保留一次更早的进程观察记录：旧 PID 34528 在独立 worker 执行期间消失，未连接其 COM 对象，原因未知。该既有记录使联合案脚本保守返回退出码 1；本次重放的 PID 检查为通过。详见 mixture_extended/mixture_v2_process_lifecycle_observation.md。

## 尚未覆盖的已实现范围

- 本轮每个功能只做固定代表案例，不覆盖 80 项矩阵中全部支持范围与参数组合。一般全因子、RSM、Split-Plot、PB、Taguchi、最优设计、Mixture 的其他因子数、模型项、水平、约束、区组和设计配置仍需按 docs/doe-minitab/feature-matrix.csv 分批补测。
- SCR-002 标记为 partial：已测六连续因子 DSD；其他有效多分类/连续因子组合及标准序/伪中心点顺序仍未对标。
- FAC-012 标记为 partial：本轮覆盖一个正规分数设计子集 Foldover 和 PB12 全折叠；其他已支持 PB 尺寸、正规因子数/折叠子集尚未逐项数值对标。Split-Plot Foldover、PB 分类/中心点/区组和连续多批次属于矩阵列明的扩展边界，不冒充已实现。
- TAG-005/010/011 的混合水平、四水平及五水平 Taguchi 阵列，FAC-005/FAC-018 的更高维混合水平组合和因子均值/标准差/ln(SD)分析，仍未由本轮代表案例覆盖。
- GEN-007/008 功效与样本量、RSM-012/013/014 与 MIX-009/013 多响应可行域/优化/期望度数值，以及 SCR-005/FAC-011/RSM-005 自定义设计重建路径，仍需后续逐项对标。
- GEN-013 为 unknown，不计作已实现功能；当前诊断不能证明已实现自动删除或替换 DOE 异常值。

## 范围

未修改 code/ 生产算法、正式 DOE 功能矩阵、docs/CHANGELOG_DEV.md、冻结八案 manifest/原始证据；未提交或推送。逐案例命令与 raw/JSON/CSV 位于各子目录，行级汇总见 supplemental_summary.csv。

