# G19 证据脚本独立只读审查

> 本文前六节保留首轮审查时点，第七节为修复后的静态复审；最新落盘证据核验见第八节，以第八节为准。

日期：2026-10-21，Asia/Shanghai。范围：`run-benchmarks.ps1`、`summarize_performance.py`、`acceptance.py`、`supplemental/benchmark.py`（路径均相对本目录）。为确认实际协议，另只读核对三个被调用的 tools 基准脚本、补充场景计划、G15 场景覆盖清单及原脚本。

**结论：未达到可无条件采信为“全部场景完成且每阶段三次有效样本”的脚本验收标准。存在完成标志不传播补充失败、汇总未校验完整场景/阶段集合，以及 acceptance 的三轴记录强于断言三项问题。** 冷积分与暖缓存的设计分离正确；历史参照标注基本克制。以下均为静态审查，没有运行测试、基准、验收或汇总脚本，也没有读取运行中原始样本并宣布完成。

仅写本文件，未改脚本、场景、生产代码或其他证据。性能补充最后几项及 final 尚在主任务流程中，本文件不预认其结果。

## 1. 必须处理的证据缺口

### R1 / P1：补充 worker 失败不能阻止外层写出 Completed

**位置**：`supplemental/benchmark.py:399-417`；`run-benchmarks.ps1:23-25`；`summarize_performance.py:94-118`。

补充控制器将子进程超时/异常标为 `timeout/error`，将退出成功但未到 complete 的记录标为 `worker_incomplete`，这些状态会写回 JSON，原始证据没有被一律改成 ok。问题在于控制器记录后继续循环，末尾没有根据失败状态返回非零。

具体路径：任意一个补充场景超时 → JSON 记 timeout → 控制器继续执行其余场景并正常返回 → PowerShell 的 `$LASTEXITCODE` 为 0 → 写出 `benchmark-complete.txt` 内容 `Completed`。外层只检查控制器退出码，不能区分全部成功和执行到末尾但有失败。

汇总对非 ok 的补充 JSON 会添加 `failures` 后跳过其数据，这是正确的样本筛选；但即使 `failures` 非空仍写结果并正常退出。计划 ID 集合相等也不会阻止此路径，因为失败场景仍有自己的 JSON 文件。若某规模的三个 cold trial 全部失败，该规模不会进入 cold 字典，后面的最少三样本断言也不会执行。

**影响**：不能以完成文件、PowerShell 正常返回或汇总正常返回推断所有性能场景通过。不是说本轮已经发生失败；是脚本存在可到达的错误成功信号。

**最小处理方向（未实施）**：保留失败记录和其余场景继续执行的能力，但控制器结束时汇总失败并返回非零；或在外层验证所有计划场景最终状态后才写成功标志。汇总可以输出部分结果，但必须明确标记整体 incomplete，并让最终验收门禁拒绝它。无需重写调度框架。

### R2 / P2：最少三样本检查不能证明计划场景/阶段完整

**位置**：`summarize_performance.py:16-36,50-69,71-110`。

当前已做的检查有：六个 statistics 文件、十二个 render-current 文件、render-before 文件名集合、补充 JSON 文件名等于计划 ID，以及每个实际进入 add 的 samples 长度至少为三。这些不等于检查计划的全部计算单元。

可构造的遗漏路径：

1. **统计文件逐场景写出**：`tools/benchmark_statistics.py` 每完成一个场景便覆盖写 JSON；没有顶层 complete 状态。若已有六个文件，但某文件中只留下首个场景的三次样本，汇总只遍历这些现有 rows，不会发现同 hotspot 后续场景缺失。正常首轮外层会因进程非零停止，但单独运行汇总、保留旧完成文件或混入旧文件时不能靠这个保护。
2. **数据 CSV 逐对落盘**：`tools/benchmark_data_processing.py` 每对校验后写出；汇总只遍历已经存在的 after 分组。若一个完整场景结束后流程中断，其余场景完全没有记录，所有已存在分组仍可通过三样本检查。
3. **渲染/补充阶段**：汇总按原始 rows 的实际 phase 分组，没有每场景预期 phase 清单。一个缺少 `agg_redraw` 等阶段但保留其他阶段三条样本的记录不会被完整性断言识别。render 顶层 status=ok 能约束正常脚本完成，但不能独立证明文件未缺阶段；补充记录甚至没有再次校验 `stage == complete`。
4. **三条不等于三次独立正式重复**：`add` 用 `len(samples) >= 3`，没有检查 repeat 精确为 1/2/3、是否重复、是否含额外重复；grouped 在 warmup/status 缺省时视作正式/ok。三个 repeat=1 或多余旧记录仍可能形成可汇总组。
5. **before 样本不足不拒绝**：before 少于三条时只留下空中位数/比值，行仍可标成“本轮冻结旧实现配对”或“本轮G18修改前重放”，不能视为完成的三次有效配对。

此外 `all(x >= 0)` 拒绝负数和 NaN，但正无穷满足此条件，不能当作有限有效耗时。

**最小处理方向（未实施）**：按现有场景表校验精确的 `(scenario,n,p,phase,variant)` 集合及正式重复编号，核对有限耗时和双方有效样本；失败与缺失明确列出。复用已有 cases/SCENARIOS 和补充计划即可，不必建立新通用 manifest 框架。若当前不改脚本，最终交付必须另有可审计完整性核对，不能引用现有 add 断言作为全部完成证明。

### R3 / P2：acceptance 记录三轴成功前没有断言实际三轴

**位置**：`acceptance.py:138-143`。

逐轴检查使用 `zip(plot.fig.axes, dlg.selected_columns())`；zip 按较短输入截断。若某次回归只建立前两个正确轴，对已有两轴的数据断言可能都通过，第三条曲线没有被检查；若没有轴，循环甚至为空。随后仍直接写入 `{'points_per_curve':1000,'axes':3,'stable_sort_and_nan':True}`。

**影响**：该 JSON 单独不能证明三轴/三曲线实际完整。相较之下，同脚本 vendor 分支先断言 `len(vendor.ax.lines)==3`，不存在同样的数量遗漏。

**最小处理方向（未实施）**：循环前断言选中变量数、实际轴数均为 3，必要时断言每轴预期一条线，然后按实际数量记录结果。现有 G13/G18 测试可能另有此保护，但不能替代本次 acceptance 对自己声明的检查。本问题继承自 G18 验收脚本，不是 G19 的路径调整新增。

## 2. 四脚本逐项审查

### run-benchmarks.ps1

- 使用项目 `.venv/Scripts/python.exe`，设置固定 hash seed 和四项线程数；依次执行 GUI 验收、六个统计 hotspot、数据、G18 before/current、补充基准。当前编排内部串行，没有自行并发测试或基准。
- GUI/统计/数据/G18 的非零进程退出均会抛错；G18 子控制器本身用 `subprocess.run(check=True, timeout=240)`，能传播普通场景失败。
- render-before 明列 11 场景，current 采用工具默认 12 场景，多出的 vendor 刻意没有旧曲线基线；这不是漏测旧 vendor 的性能收益。
- supplemental `$LASTEXITCODE` 的漏洞见 R1。脚本不调用 summarize 或 final，因此即使 Completed 合法，也只代表该编排结束，不包括最终回归。
- 固定输出目录、固定文件名会覆盖同名结果；开头不清除旧成功标志，也无本轮 run ID。重复执行失败时旧 `benchmark-complete.txt` 可能仍在。当前首轮新目录未必触发，后续不得把标志文件存在本身当作本次成功。最小做法是在开跑时撤掉旧标志、保存本轮版本/时间并于验证后写新标志，或另用新目录。
- before 全部跑完后才跑 current，未交替配对；桌面/CPU/磁盘负载漂移仍可能影响结果。脚本串行不能证明没有其他工作者同时运行负载。

### summarize_performance.py

- grouped 排除 warmup 和非 ok 行；render 当前/before 必须顶层 ok；supplemental 顶层非 ok 的整场景数据全部排除，即使含已完成阶段也不会冒充完整成功。这些筛选方向正确。
- 统计工具的 JSON samples 本身只有三次正式值，预热由工具单独先调用，不是 samples 混有预热。
- 数据读 CSV 后把 warmup 文本转换成 bool；计时工具先做双方一致性校验再写成功行，非仅函数返回就计成功。
- before 数据使用旧实现/仅修兼容的搜索旧算法；该 variant 与 after 分开。渲染 before 使用 G18 六模块快照，其他依赖来自当前集成代码，汇总 note 已说明，不能称为整个 G15 旧项目重放。
- 统计使用 `docs/g16-evidence/performance.csv` 的历史 after_samples，标为“G16历史优化后”并提示负载和边界差异；未把它称为本轮同环境旧代码基线。
- 输出 `current_over_baseline` 是数值比，并没有阈值触发“退化/失败”判断。最终报告仍须保留 baseline_kind，不能把这个统一列中的历史比值直接称作性能退化或本轮加速比。
- LR 行明确标记 B-01“仅记录耗时，LR统计定义未通过验收”；成功计时与方法正确性区分合理，整体不能由该行的 samples 推断统计验收成功。
- 不足见 R1/R2；没有证据支持现在宣布完整汇总有效。

### acceptance.py

与 `docs/g18-evidence/acceptance.py` 的只读文本 diff 仅有两处：模块说明改为 G19；旧 linear_plot 源位置从 `OUT/'before/linear_plot.py'` 改为 `ROOT/'tests/fixtures/g18_before/linear_plot.py'`。OUT 随脚本所在目录自然指向 G19，不需要额外改业务代码。未见 G19 放宽既有数值容差或输出断言。

- TXT 逐字符、拦截剪贴板复制、末页末行、Excel 1003 行与关键原值/格式、公式标签文本、PNG 超限、小表导出、关闭引用与 idle 清理均有实际断言。
- Excel 两个容差仍为原来的 `1e-11/1e-15`；本次没有提高误差容忍度。脚本不是每一种单元格样式的穷尽检查，不要把局部属性断言解释为完整外观相同。
- 时序检查每个实际轴上的 Y 原始顺序、点数和 NaN，三轴数量缺口见 R3；没有完整比较 X 时间坐标，因此 stable_sort_and_nan 的结论边界是 Y 排序预期与缺失保留，不是所有时间轴协议已覆盖。
- 矩阵分支会画 before/after 并记录 axes 数，未断言两版 r/p/CI、逐点椭圆坐标或图片像素相同；这些应来自专项测试或截图人工复核，脚本没有自动“目视通过”的能力。
- Tk 回调错误累积并在末尾拒绝；结果 JSON 在末尾才写。普通未捕获异常会使脚本失败，不会自然走到最后的成功证据。旧 JSON/截图仍可能保留，因此也需按本轮时间/哈希识别。
- 不是三重复性能基准；没有理由要求其每个动作三次，职责是功能验收与留存画面。

### supplemental/benchmark.py

- 已将当前脚本与 G15 临时原件 `C:\Users\shaoy\AppData\Local\Temp\Minijmp-G15-20261021-101528\benchmark.py` 做 SHA256 比较，两者完全相同。没有把“完整拷贝”仅当作口头声明。
- 当前 `supplemental-scenarios.json` 有 **39 个**条目，`profile=true` 数为 **0**。profile 分支内旧 Pearson 次数预期 `p*p+p*(p-1)//2` 与新实现不同，但这些分支当前不运行，不能据此报告本次基准会失败；也不能引用它作为本轮 profile 证明。
- 每个场景启动独立子进程；Job Object 有内存上限与 kill-on-close；超时保留明确 timeout 状态，stage 未 complete 则标 incomplete。必要的隔离和预算不是无依据防御，需保留；控制器退出传播问题另见 R1。
- 常规 `range(4)`，repeat 0 为预热，1/2/3 为正式；GC、memory、输入创建位于计时外；JSON 状态和行在过程中保存。
- measure 的行 status=ok 表示该次调用返回且未记录 Tk 回调错误。有些场景后续才检查结果/数量；若检查失败，controller 最终整体非 ok，汇总按整场景排除，正常链路不会把这些先写的行作为完整成功。
- compare_dist 强制六模型完成；GUI 文本检查全文，vendor 检查线数，PI/CSV 检查形状。这些有效性判断有用，但普通 `fn` 场景并不逐一与独立数值参考对照。性能 ok 表示该场景执行和脚本内断言完成，不自动代表所有统计方法正确。
- `--resume` 只看文件存在，不验证成功状态和源码版本；本轮外层没有传 resume，因此不是当前必经缺陷。后续不能拿它直接恢复失败/旧版本记录并声称完整重测。

## 3. 冷暖分离及三次样本

`calculate_d3` 分支先断言进程内缓存为空，用 repeat=1 记录一次 `cold_integral`，再以 repeat=1/2/3 记录三次 `warm_cached_integral`。两者 phase 不同，重复编号相同不会在当前分组中混淆；cold 的 repeat=1 确保不会被普通 warmup 排除。

计划对 n=5、10 各设置三个不同 trial ID，控制器分别启动独立进程。汇总按 `(name,n,cold_integral)` 汇集三次冷积分；暖缓存按各 trial ID 单独保留三值。冷数据没有与暖缓存或预热混成一个中位数。

限制：当前汇总没有核对三个 cold 样本确实来自三个不同 trial/PID，只有数量下限；全部缺失的规模也会消失，见 R1/R2。必须核对计划和完成记录后才能称为“各规模三次独立冷积分”。这里的 cold 是进程内函数缓存为空，不等于全系统冷磁盘/冷 CPU 缓存。Agg first draw/redraw 也只是各 figure 的首次/再次绘制，不是机器冷启动。

## 4. 场景覆盖与历史参照

只读清单 `g15-scenario-coverage.csv` 含 **153** 个场景定义；其中 61 标为现有工具静态入口覆盖，92 标为建议补测，39 项被选为本轮补测代表。当前 supplemental 计划恰为 39 项；其余条目的“未选本 ID、不宣称此规模已测”说明需要在最终报告保留。

这是计划级覆盖，不是运行完成数。不能把 representative 家族覆盖改写为 G15 全部 153 个 ID 都重跑；也不能因为某家族小规模完成就替代大规模/不同 p/count/event_fraction。

- G16 工具 F04 的 binomial/单比例固定 `.49*n`，G15 中心输入默认 `.5*n` 是不同场景，补充计划单列中心样例有必要；历史中心异常耗时不能充当有效 before。
- 矩阵 20/40 变量、Tk 与 Agg、纯数据准备与包括准备的构图应分别保留。不同阶段耗时不能直接累加为独立端到端测量。
- 当前 vendor 曲线无有效 G15 空图性能基线，summarizer 使用“无有效旧版曲线基线”，符合边界。
- G16 历史 after 与本轮 current 的比值不能独自认定退化；G18 本轮 before/current 也有顺序与负载限制。需要当前同输入重放与结果有效性，再解释是否实际变慢。

## 5. no-stop-gpt 必要性审查

复用既有三个工具、只读源目录重放、39 个补充代表和 G15 完整 worker 拷贝，避免新造测试框架，方向合理。保留串行调度、进程超时/内存上限、暖样本排除、全文/形状检查、失败状态和冷积分独立进程：每项都有具体消费者或已知故障边界。

需要补的是结果门禁，不能以“最少代码”为由省略失败传播和完整性检查；也无需为解决它们引入全局缓存、任务队列、自动重试或通用性能平台。最小充分闭环是：计划对照实际状态/阶段/重复、失败非成功、结果有限、来源时点明确。

acceptance 的路径改动范围足够小；profile=false 使旧插桩断言不影响本轮，不建议因此修改完整历史拷贝。测试/基准执行权仍由主任务持有，本审查没有尝试修复或运行。

## 6. 审查版本标识与交付限制

| 文件 | SHA256 |
| --- | --- |
| run-benchmarks.ps1 | `2A781B9BDF016F2430F69D5674E6838C2436AB28E4914352DF8615F02DA8329B` |
| summarize_performance.py | `8B59FE7CF3838397F45BF462B6E1022C626683D5A475F8459DF06F9D91976D56` |
| acceptance.py | `995023AA30303B3311BB1220C17ECDADDFB1F14EFF5FFFFB9DCE4A9D0F616634` |
| supplemental/benchmark.py（与 G15 原件一致） | `41282B6196923E920E6BE85F38FE14EFCEB038366A7B5B7C452EF293D9906B0E` |

本次没有核验运行中原始样本、最终日志、截图外观或 final 状态；不宣称本轮已有超时、已漏样本或所有结果失败。上述问题是当前脚本可接受错误完成信号的具体路径，应由主任务在最终证据闭环中处理。

建议针对失败状态传播和完整性门禁缺口，在主任务结束后运行 `$retro`。

## 7. 局部修复后的最终跟进

日期：2026-10-21。重新读取当前 summarize、run-benchmarks、acceptance，并与实际被调用工具的 phase/repeat 协议对照。没有运行测试、基准、验收、汇总或其他负载，仅更新本文件。

**最终静态裁定：R1/R2/R3 的原始问题已得到局部处理，未发现本次修复新增的阻塞项。完整性重放尚在执行，不能将本结论写成门禁已动态通过；G19 整体验收仍须保留 B 类 LR 问题，不能判定 PASS。**

### R1：在完成标志前增加统一门禁，闭合本轮成功判定

run-benchmarks 在 supplemental 控制器返回后新增 summarize 调用，检查其退出码，失败即 throw，之后才写 Completed。summarize 现在对补充非 ok 状态累积 failures，并在输出成功汇总前 `assert not failures`。

因此即使原 G15 控制器继续保持“记录 worker 失败但自身正常返回”的历史行为，失败也不能穿过当前外层门禁后新写 Completed。缺少计划 ID、未完成 stage、缺失 phase 或错误重复也会在门禁中拒绝。没有必要为本轮改动完整历史 worker 拷贝；用现有汇总作为外层门禁是充分且较小的修复。

原报告提及的旧标志/旧汇总文件重跑后可能仍残留这一使用限制并未自动消失：应结合本轮门禁退出码及记录时点认定成功，不能单凭旧文件存在。此项不阻止当前修复闭合首轮执行路径，但最终归档需区分旧文件与本轮产物。

### R2：集合、阶段、重复和有效耗时已有精确约束

| 数据族 | 当前验证 | 复审判断 |
| --- | --- | --- |
| 统计 | 每个 F 文件中的 `(name,n,p)` 排序列表必须等于 `benchmark_statistics.cases(hotspot)`；合计 38 组合；每个 samples 必须恰为三条且有限非负 | 不再只凭六个文件存在接受部分 hotspot；列表比较同时拒绝重复场景。统计工具本来就只保存三次正式 samples，未伪造其不存在的 repeat 元数据 |
| 数据 | 显式预期 26 组、before/after 双方共 52 variant 组；CSV 的 p=10、数字清洗额外 p=20/40、查找兼容 variant 均对照工具；每组精确 repeat=0/1/2/3 | 同时拒绝漏组、重复编号、缺预热和错误 variant；warmup/status/有限耗时逐条校验，正式三值单独汇总 |
| 渲染 | 当前文件集合等于 SCENARIOS；before 比 current 少 vendor；n/p 与工具定义匹配；before/current 对应场景一致；每场景精确 phase 集合、每阶段 repeat=0/1/2/3 | 新 phase 清单与工具实际 matrix/Agg/Tk、报告末页、series prepared、vendor 等阶段名称一致；不再依靠已出现阶段来证明完整性 |
| 补充 | 文件 ID 集合等于计划；成功记录必须 stage=complete，scenario 全参数等于对应计划；每家族精确阶段，普通阶段 repeat=0/1/2/3 | 既保留原 G15 输入构造，又拒绝错参数、部分完成与重复样本；失败记录由统一断言阻止成功输出 |
| 冷积分 | 每 trial 一条 cold_integral，repeat=[1]；按规模聚合后恰为三值，计划规模集合匹配；每规模三个不同 PID | 当前计划仍是 n=5/10 各三个 trial，冷暖没有混合；不仅检查有三行，也核对独立进程标识 |
| 暖缓存积分 | warm_cached_integral 精确 repeat=[1,2,3]，没有要求 repeat=0 | 与原 worker 的实际循环一致；首次 validator 误要求预热的修正必要，不能为满足统一模板伪造暖阶段样本 |
| 配对/历史样本 | add 要求 current 恰好三条，before 非空时也恰好三条；所有值使用 math.isfinite 且非负 | 本轮数据/渲染 before 的存在性由前置集合与阶段校验保证，不能以空 before 绕过本轮配对；有历史参照仍保留历史标签，不据比值判退化 |

`check_repeats` 针对 cold/warm 的特殊重复编号仅用于这两种明确 phase，没有放宽其他阶段的四次记录要求；正式值仍经 grouped 排除 repeat=0 对应的 warmup。success summary 和 integrity JSON 在这些断言后才写出，未见为了通过门禁降低数值精度或接受失败样本。

范围限制仍在：矩阵 Pearson/axes 分解字段是主 phase 行的附加计时，不是独立新阶段；完整阶段验证不能扩大为所有数值统计方法的正确性证明。历史覆盖清单仍是代表规模计划，新增门禁没有把未入选的 G15 ID 改成已测。

### R3：三轴与每轴一条线在 zip 前验证，已处理

acceptance 在逐轴循环前增加：

```python
assert len(dlg.selected_columns()) == len(plot.fig.axes) == 3
assert all(len(ax.lines) == 1 for ax in plot.fig.axes)
```

缺轴、空轴、额外轴或一轴多线都会先失败，不能再靠 zip 截断后写三轴成功。后续原有 Y 原始值、稳定排序预期、NaN 和点数比较保留；Excel 容差等既有断言未改。该数量保护有直接消费者与明确失效样例，属于必要局部补充，无需新增抽象。

### 版本固定与动态证据边界

| 文件 | 最终跟进读取时 SHA256 |
| --- | --- |
| run-benchmarks.ps1 | `D3D0DADB63B99405EE44D1B9B8471FC5DBC0BAB76ECFA824CA4E1C11662DEA6F` |
| summarize_performance.py | `BA3694B06043A263757635C2CCB10066DA4C47CD3F8F15393BBECD22EF280BB1` |
| acceptance.py | `63E86ACC524AD0F766F93859321C1941573926097F7CD932B4432C0F95FED009` |
| supplemental/benchmark.py | `41282B6196923E920E6BE85F38FE14EFCEB038366A7B5B7C452EF293D9906B0E`（与首轮及 G15 原件一致） |

另只读重核 Fisher 生产文件、G19 集成测试及 G9 守卫测试的 SHA256，分别仍为前次 fisher-patch-review 所记 `F7E68A…B846`、`E7EDB1…9476F`、`08A8F8…0E8B5`；未发现这三个文件自该审查版本改变。此核对不等于逐文件认证整个工作区所有生产和测试源均未变化。

主任务提供最终 pytest 为 **2098 passed、112 warnings、436.19 秒**；本审查没有运行或独立检查该日志，保留来源标注。完整性门禁正在重放已有样本，其结果尚不能计为通过；未要求重跑基准来验证纯汇总门禁修复。

no-stop 必要性复审：复用现有 cases/SCENARIOS、原 phase 协议及单个 check_repeats，新增逻辑直接覆盖首轮指出的失败窗口，未引入重试、队列、缓存或兼容框架。当前无有据可删的修复代码。首轮暖缓存 validator 的返工也说明应先对照生产者的真实 repeat 协议；主任务结束后建议运行 `$retro`。

## 8. 最终落盘证据核验与动态待办关闭

日期：2026-10-21。按主任务指定范围，只读打开 `performance-integrity.json`、`performance-summary.json`、`gui-export-acceptance.json`、`final-pytest.txt` 和 `final-pytest.xml`，并读取本次 selfcheck/旧 marker 清理改动、更新四脚本哈希。未执行任何测试、基准、验收或汇总重放；以下区分已核对的文件内容与主任务提供的进程信息。

### 已核对的落盘结果

| 证据 | 实际读取结果 | 本次核验边界 |
| --- | --- | --- |
| performance-integrity.json | statistics_cases=38、data_paired_cases=26、render_current=12、render_before=11、supplemental=39；exact_repeat_ids、finite_samples、planned_phases_complete 均为 true；cold n=5/10 各 3 个不同进程标识 | 与第七节所审门禁定义一致；本次读取门禁产物，没有重新遍历所有原始样本 |
| performance-summary.json | valid_phases=165、samples=495、failures=[] | `165×3=495`，与每阶段三正式样本的规则一致；不代表额外未入选场景也执行完毕 |
| gui-export-acceptance.json | time_series 为每曲线 1000 点、axes=3、stable_sort_and_nan=true；vendor_curves=3；tk_callback_errors=[]；1003 行报告 TXT/复制/Excel/清理均记录成功 | 当前 acceptance 哈希与三轴/每轴一线强化版本一致；本次没有重新看图或操作 GUI |
| final-pytest.txt | 最终行 `2098 passed, 112 warnings in 436.19s (0:07:16)` | 已直接读取日志，不再只是复述主任务口头数字 |
| final-pytest.xml | suite tests=2098、failures=0、errors=0、skipped=0；实际 testcase 节点 2098，failure/error 节点均为 0 | 与 TXT 通过数一致；XML suite time=435.594 秒，TXT 为会话总耗时 436.19 秒，保留各自口径，不要求两种计时逐位相同 |

读取时文件最后修改时间：两份 performance JSON 均为 13:50:36；GUI JSON 为 13:47:48；pytest TXT 为 13:45:54、XML 为 13:45:53（本机显示时间）。这些时点使前节的“完整性重放待完成”及“pytest 仅主任务提供”状态得到后续文件证据更新。

主任务另报告强化 GUI 验收进程 **70542 exit 0**、完整性及 selfcheck 重放成功。GUI JSON 本身不含该 PID/退出码，本次未额外查询进程或运行日志，故 PID/exit0 保留为主任务核验声明；不把它伪装成本审查独立观察到的进程事件。

### selfcheck 与旧完成标志清理复核

summarize 的入口现在先对正常四重复样例调用 check_repeats，再分别构造缺一条正式记录、重复 repeat=1、耗时为正无穷三类坏输入；每项必须触发 AssertionError，否则主动失败。上述自检位于 main 之前，与门禁采用同一函数；没有调整生产数值精度或放宽合法样本规则。读取到的成功门禁产物与主任务所述已重放一致，本审查没有自行重跑自检。

runner 开头在设置本目录输出路径后，用 Test-Path 检查并以 `Remove-Item -LiteralPath "$out/benchmark-complete.txt"` 清理旧 marker；没有递归删除，也没有删除其他证据。由此处理第七节保留的旧 Completed 文件存在性风险；后续仍在 summarize 成功后才新写标志。旧 CSV/JSON 继续保留不等于本轮已通过，应以本次门禁结果和版本记录判断，当前已有指定的成功产物。

### 当前四脚本版本

| 文件 | 最新 SHA256 |
| --- | --- |
| run-benchmarks.ps1 | `9D07579B150AAC7AF791694E8D672C955C6DC347C1272A7F42E41A3F7A4B27B1` |
| summarize_performance.py | `52225E099A684BF4C876BC3B4025C072AE3018BDFF01DA3C5C18A37AFDFD45E4` |
| acceptance.py | `63E86ACC524AD0F766F93859321C1941573926097F7CD932B4432C0F95FED009` |
| supplemental/benchmark.py | `41282B6196923E920E6BE85F38FE14EFCEB038366A7B5B7C452EF293D9906B0E`（仍与首轮/G15 原件一致） |

**最终跟进结论：R1/R2/R3 的局部修复及指定落盘动态结果已完成本轮证据核对，原 review 末尾的完整性/GUI/pytest 动态 pending 不再作为未完成项保留。** 本审查确认文件记录与已审脚本协议一致，没有自行执行负载或重新独立复现所有样本。

这不改变整体统计验收边界：LR 辅助入口仍是明确未解决的 B 类问题，最终整体结论仍不能写 PASS；历史比值仍不能单独认定退化，代表规模仍不能写成 G15 全部 ID 重跑。
