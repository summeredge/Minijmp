# G19 Fisher 补丁独立 Patch Review

日期：2026-10-21，Asia/Shanghai。工作区：`C:\Users\shaoy\Documents\Minijmp`；读取时 HEAD：`b430f8c7c4e4870f1dc3a9242e8f2d50ba9ba231`。

**结论：当前三文件补丁未发现需要阻止本次局部修复的代码问题；G9 的必要守卫适配已纳入审查。此结论仅为静态 Patch Review，不是测试通过。G19 总体验收不能写 PASS：独立 LR 辅助入口的已知统计问题仍未解决，按主任务要求列为 B 类。**

仅新增本审查文件，保留其他文件和并行工作者的改动。未运行测试、基准、Python 探针、GUI 或子进程复现；未修改生产、测试或夹具。采用 ponytail-review 的调用链审查及 no-stop-gpt Audit 的必要保护检查。

## 1. 实际补丁范围

| 文件 | 读取到的变更 | 审查判断 |
| --- | --- | --- |
| `code/proportion_test.py:48-60` | 增加 `lower, upper = rv.support()`；右搜条件增加 `y <= upper`，左搜条件增加 `y >= lower` | 在共享统计实现一次修复，覆盖 GUI 和直接调用；没有改统计排序、尾概率公式、参数或返回键 |
| `tests/test_g19_integration.py:11-34` | 一个测试用 `events=1/9999` 参数化为两个用例；真实超几何分布加越界 PMF 守卫；核对 Fisher 参考和报告原值 | 能在旧实现首次越界时立即失败，避免回归测试自身无限循环；分别覆盖右搜与左搜 |
| `tests/test_g9_tables.py:146-162` | 仅对 proportion_test 中 prop_2sample 的精确赋值与精确 while 条件做 AST 归一化 | 保留原计算哈希、夹具和数值/输出精度；与 G19 行为回归一起承担新的终止保护 |

其余生产代码没有纳入修复授权。没有改 `p_likelihood_ratio` 的定义，也没有把嵌套 list/ndarray 合并当作缺陷。

## 2. 生产逻辑与终止性

输入仍由 `prop_2sample` 原路径计算样本比例、两类标准误、正态检验和区间，随后创建 `hypergeom(n1+n2, e1+e2, n1)`。新的支持集来自本次同一个 frozen 分布，没有硬编码为 `0..n1`，因此也适用于非零下界及小于 n1 的上界。

- **右搜**：先检查 `y <= upper`，仅在支持集内调用 PMF。若走完 upper，下一次 y 为 upper+1，短路退出；原 `cdf(y-1)` 正好为 `cdf(upper)`。没有跳过 upper 这个有效支持点。
- **左搜**：先检查 `y >= lower`。若走完 lower，下一次 y 为 lower-1，短路退出；原 `cdf(y)` 对应支持集外的零左尾。没有跳过 lower。
- **普通非零阈值**：若旧实现本已在支持集内找到停止点，新增条件为真，原比较和结果保持不变。若直到支持集外才停止，非零观测概率下原实现会在第一个越界点以 PMF=0 停止；新实现在相同 y 停止，尾概率公式不变。
- **零阈值**：旧实现越界后继续比较 `0 >= 0`；新实现最多走完该方向的有限支持集。左右单侧 `cdf(e1)`、`sf(e1-1)`、mode 相等分支和双侧计算式均未更改。

这证明源码控制流有有限界限，不能解释为任意极端概率的相对精度保证。补丁仍使用原 PMF 比较与 CDF 相减；没有新增 log-PMF 排序或超小概率表示。零标准误、无效计数等已有输入语义也未改变，本修复不承诺覆盖这些既有边界。

## 3. 全部当前消费者及相关保护

有界检索覆盖 `code/`、`tests/` 内的函数名称、Fisher 返回键及相关基线。

| 消费者 / 测试 | 已核对的关系与契约 | 对补丁的影响 |
| --- | --- | --- |
| `code/MiniJMP.py:490 prop_2samples` | 菜单创建 `Prop2SDialog` | 无参数或路由修改 |
| `code/sample_test_dialog.py:591-623 Prop2SDialog.apply` | 原始列经 event_count 或直接输入计数，均调用共享 `prop_2sample`；输出到 `self.app.print` | 两种输入模式都获得终止保护，不需要在 GUI 复制 while 边界 |
| `code/proportion_test.py` 直接入口 | 相同公开函数、签名、返回字典；文件末尾两比例示例只是注释 | 没有第二份 Fisher 搜索实现需要同步修改 |
| `tests/test_p1_p2_statistical_fixes.py:94 test_fisher_right_tail_and_other_results` | 0/全事件及普通计数；右尾与 hypergeom SF、SciPy greater 比较；其他结果与旧实现比较 | 原右尾修复、返回键及非报告结果保护仍在 |
| 同文件 `:280 test_fisher_real_dialog_reports_correct_zero_tail` | 原始/汇总两种输入调用真实 apply 方法，检查 Fisher 报告尾列 | 覆盖 GUI 派发正文；这是测试正文的覆盖范围描述，不代表本次创建或验证了真实 Tk 窗口 |
| `tests/test_g1_statistics_output.py:183 test_two_proportion_table_columns_match_alternatives` | 两方向计数、左右尾、文本列及区间 | 输出协议未改 |
| `tests/test_g2_hypothesis_reports.py:290 test_two_proportion_methods_difference_and_tail_columns` | 不同样本量、两方向及 alpha；Fisher 双侧/左右侧与独立 SciPy 参考比较 | 为普通输入保留独立正确性检查，不只比较旧实现 |
| 同文件 `test_print_out_false_is_silent_and_does_not_build_tables`、`test_signatures_and_defaults_preserved` | 非报告入口和公开签名 | 新增 support 查询位于统计段；没有额外输出或新参数 |
| `tests/test_g2_basic_reports.py:354` 的 prop_2sample 参数项 | 真实报告字体/对齐测试的生产报告调用 | 报告构建代码没有变化 |
| `tests/test_g9_tables.py:47` 的 prop2 以及 Prop2SDialog raw/summary 参数项 | 固定 TXT、结构表数量、viewer 转发、Excel/PNG、精确原值和格式 | 全部报告/导出测试保留；Excel 原值断言仍为 `rel=1e-14, abs=0`，没有放宽 |
| `tests/test_g16_statistics.py` F04 | 主要覆盖单比例、独立离散检验和 PMF 工作量 | 不能把它当 Fisher 循环终止回归；本次 G19 用例补这个缺口 |
| G3 计算夹具 | 检索未发现 prop_2sample/proportion_test 条目 | 本补丁涉及的是 G9 整模块计算守卫，不需要借机刷新 G3 基线 |

没有发现调用者替换 frozen hypergeom 的生产协议。新 `support()` 方法直接由现有 SciPy 分布提供；新测试的 SimpleNamespace 也显式提供该方法，不增加依赖。

## 4. G19 新回归的充分性与限度

`test_fisher_underflow_search_stays_in_support` 使用真实 `hypergeom(20000,10000,10000)`；断言观测 PMF 为 0。monkeypatch 只替换生产分布的取得方式，CDF/SF/support 以及每次 PMF 的数值仍由真实分布提供。PMF 包装器先断言支持集，再记录并求值。

`events=1` 进入右搜，`events=9999` 进入左搜。旧实现在该方向走出支持集时会触发断言，避免在测试进程内继续无限循环。新版即使计算阈值仍为 0，也必须在 PMF 越界调用之前退出。

测试同时核对：

1. 返回双侧 p 值等于独立 `fisher_exact` 参考，并在这个特定下溢输入中严格等于 0；没有用宽容差遮住零值。
2. PMF 调用总数不超过支持集宽度加初始观测调用所需余量；不是硬编码当前精确循环次数。
3. `StatTable` 的“检验结果”首行三个 p 值对应真实返回字典，覆盖新增极端输入的报告原值交接。

限度：这两个用例支持集都是 0..10000，没有动态证明非零 lower 的输入；源码使用实际 `rv.support()`，当前未见因此需要扩大本局部补丁的理由。测试没有单独给极端输入的两个单侧 p 值建立独立参考，但已有普通/边界尾概率保护，且单侧公式没有改动。无须为本次三个局部保护表达式增加通用测试框架或超时设施。

## 5. G9 AST 适配独立审查

首次读取时 G9 尚未适配，本审查指出其整模块哈希会因新增 AST 改变；随后主任务补入当前版本，已重新读取实际 diff。最终判断以补入版本为准，该联动不再列为未解决项。

当前 `computation_hash` 只在 `module == 'proportion_test'` 时选中顶层 `prop_2sample`：

- 仅删除 `ast.unparse(n) == 'lower, upper = rv.support()'` 的顶层语句；不是删除所有 support 调用、赋值或整个函数。
- 仅把精确条件 `y <= upper and rv.pmf(y) >= observed_probability`、`y >= lower and rv.pmf(y) >= observed_probability` 还原为其第二项。`>`/`<`、错误边界名、or、不同 PMF 比较等不会命中此豁免。
- 循环体、y 步进、CDF/SF、统计公式、返回值及其他函数仍参与原哈希计算。现有 `ComputationOnly` 的报告剥离规则没有扩大。
- `tests/fixtures/g9_reports.json` 未在当前 diff 中修改；代码仍比较 `baseline['computation'][module]`，没有通过刷新全部夹具吞掉变更。
- TXT、数值精度、导出格式等断言都没有改变。

该归一化有意允许授权 guard 存在或不存在，**单靠 G9 不能证明 guard 没被删除**；两项 G19 越界回归负责这个行为不变量。若删除任一边界，所对应参数用例应在首次越界 PMF 调用失败。此“旧计算冻结 + 新行为回归”的保护转移范围足够小，无需增加一层 AST 匹配框架，也没有理由删除整个比例模块守卫。

## 6. no-stop-gpt Audit

保留三项生产新增表达式：实际支持集用于限制真实已确认的不终止路径；两侧各有消费者及各自回归；短路顺序确保不调用越界 PMF。不存在新增缓存、状态机、兼容层、fallback、依赖或后台线程。

G9 的局部归一化是现有源码冻结与获授权修复之间的必要适配，新增 G19 测试有能力区分旧缺陷与修复，不属于只复述赋值的无效测试。未发现有依据应删除的代码，也未发现需要扩大生产补丁的理由。

## 7. 历史证据、未解决 B 类与最终口径

主任务向本审查提供以下动态信息：A1 真实子进程 10 秒超时、观测 PMF=0；两个新增回归修改前均失败；首轮相关运行 307 项通过，仅 G9 AST 冻结失败；最终相关回归仍在运行。以上均为**主任务提供的信息，本审查没有运行或独立核验日志**，不能写成独立验证通过。

主任务另确认 `p_likelihood_ratio(10,.5,8)` 的实际值约 `.9785156249999998`，通常二项 LR 双侧参考为 `.109375`。依照本轮明确决策，该问题列为 **B 类未解决统计辅助入口问题**，不在 Fisher 修复中改定义；现有 GUI 单比例报告不调用该 LR 辅助入口。当前补丁未改这个函数。最终整体结论不能用 PASS 掩盖该问题。

主任务的嵌套 list/ndarray 合并探针均成功，本次不列生产缺陷。原 `source-review.md` 的分类与探针前证据状态属于早先时点，本次不改写他人的既有审查文件；最终交付应采用这里明确的最新分类和限制。

## 8. 审查版本标识

| 文件 | SHA256 |
| --- | --- |
| `code/proportion_test.py` | `F7E68A0301642CEF57F5B7954953B6E97AB354F7C0E44675717DA4215B01B846` |
| `tests/test_g19_integration.py` | `E7EDB198ADC721D1F98EC8E4B85A7DE1A0E6698C0B38C630C1CC9BA2EAA9476F` |
| `tests/test_g9_tables.py` | `08A8F8E8304499B7653AD406FFD6E1D15755CB5BAC24E1DD501458777CA0E8B5` |

**局部静态裁定：未发现未处理的补丁阻塞项；当前 G9 适配合理。整体裁定：保留 B 类 LR 问题，不能标记 PASS。**

未检查：动态回归、基准、GUI、运行中最终结果；本审查不替代主任务的最终验证记录。对旧统计比较遗漏终止性、随后需要联动源码冻结的流程问题，建议主任务结束后运行 `$retro`。
