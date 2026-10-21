# G19 Python 模块覆盖清单说明

静态枚举时间：2026-10-21T13:50:26；工作区：`C:\Users\shaoy\Documents\Minijmp`。

## 范围与计数

通过 os.walk 递归遍历实际文件系统，不使用 Git 跟踪集合或 rg 默认忽略规则筛选；大小写不敏感计入 .py。隐藏、未跟踪、被忽略文件及 docs 快照、tests、tools、内置 vendor 均在范围内。Git ls-files 仅用于标注跟踪状态。

- 范围内 Python：143；解析成功：143；解析失败：0。
- 范围内非 Git 跟踪 Python：4；带点隐藏路径 Python：0。
- 排除目录内 Python：6272；文件系统递归发现总 Python：6415。
- 只排除下表明确的环境/缓存目录；未将 vendor、docs 或 *_orig.py 当环境排除。无统一忽略 build/dist：若存在 Python 源码同样纳入。

|范围|Python 文件数|
|---|---:|
|code|71|
|docs|22|
|tests|44|
|tools|5|
|仓库根目录|1|

|排除目录名|实际 Python 数|原因|
|---|---:|---|
|.git|0|Git 对象与内部元数据|
|.venv|6272|项目虚拟环境与第三方安装副本|
|venv|0|虚拟环境|
|node_modules|0|Node 依赖|
|__pycache__|0|字节码缓存|
|.pytest_cache|0|pytest 缓存|
|.mypy_cache|0|类型检查缓存|
|.ruff_cache|0|lint 缓存|
|.tox|0|测试环境|
|.nox|0|测试环境|

目录链接（不跟随以避免越界/环）：无。文件系统读取错误：无。解析错误：无。

## 证据与状态口径

- CSV 每个范围内 Python 文件一行；入口保留至多 12 个核心公共函数/类/GUI 方法及行号，优先 main、apply、导出、数据处理及实际消费者使用的入口，其余定义只计数，不另附 JSON。功能结合职责、docstring 和定义。核心入口中未建立 test_ 调用关联者逐名列入剩余风险，不声称其余未列定义已覆盖。
- 调用链基于 AST Call、Import/ImportFrom 别名、本模块限定名称、self/cls 本类方法和 command/func 回调注册；只展示应用 code 内消费者与核心入口调用的至多 6 条代表关系，其余记录数量；docs 历史、tests 和工具调用不混作应用实际消费者。tests/conftest.py 把 code 加入 sys.path，应用短模块名按 code 根解析。嵌套局部导入仅做文件级别别名近似，未做控制流可达性分析。
- 不按字符串搜索命中认定覆盖；测试证据按 test_ 函数去重，保留至多 3 个代表测试及代表终点/断言行号，其余给出数量；fixture 声明明确标识。assert 行号不是断言目标已匹配；参数化、fixture 注入、实例方法、动态工厂和猴补丁可能缺边。import 的存在本身不构成调用或覆盖。
- 入口与未关联核心入口列供聚焦复核；不把标准库/第三方正常调用逐项列作风险。动态类型、继承分派、GUI 事件及第三方调用未完整建模。未解析不能等价于死代码或测试缺口已证实。静态关系本身不证明功能正确；补录的动态记录仅支持其实际执行场景。
- 部分验证：已做静态关联/fixture 定义核对，或有列明的测试/脚本运行证据，但未逐分支验收；未验证：未建立相关静态/动态证据或源解析受阻；不适用：tests、tools、docs 等不是独立应用功能验收对象，仍完整登记；实际运行证据另列，不按应用模块口径判定。状态描述模块验收范围；测试通过仅由具体 XML/日志支持，不能据此提升为模块全部功能通过。
- 当前行状态：{'部分验证': 61, '未验证': 10, '不适用': 72}。
- 未运行 pytest、测试函数、基准或性能检查；未启动 GUI 或导出。使用项目 .venv Python 3.11.9，仅执行标准库清单解析与 CSV 结构自检，未导入应用模块或测试模块。
- baseline-pytest.xml 与日志现已完整：2096 passed、112 warnings；修复后 fisher-related-final.xml/日志：308 passed、59 warnings。两 XML 均已只读解析，无 failure/error/skipped；最终 final-pytest.xml 与日志均已完整：2098 passed、0 failed、0 skipped、112 warnings；日志总耗时 436.19s，XML suite time 为 435.594s（计时边界不同）。

## G12 单独核对

- 口径修正：用户所称 23 个构造模块对应 fixture 的 files_with_production_sites，包含转换/输出；实际直接构造模块 21 个。另两个是 pandastable_local/core_orig.py 与 pandastable_local/dialogs.py，不能伪写成直接构造。
- 实际 fixture：tests/fixtures/g12_table_inventory.json；构造模块 23；统计报告模块 19；逻辑统计表 82；生产限定作用域 46。
- g12-table-check.csv 包含构造模块汇总行、每张逻辑统计表一行、非报告生产位置行。模块汇总的逻辑表数是小计，不能再与逐表行累加。
- 构造模块（含兼容文本、错误框、矩阵及载体）与统计报告模块不是同一集合；原生模型和固定章节按 fixture 模板计数，禁止按运行次数或字符串数量重复计表。
- 每个 producer 核对当前限定定义、直接构造 AST 计数与 fixture sites、所引用测试定义及断言位置；输出/文本事件不声称完整重算 test_g12_inventory.scan_source 的局部赋值固定点模型。仅数量一致也不能证明语义、标题及导出正确。
- 缺失的 fixture 测试引用：无。
- tests/test_g12_inventory.py 包含文件集合/生产位置分类、元数据/引用、扫描器正反例；它验证清单边界，不能替代真实报告运行。tests/test_g12_tables.py 覆盖区间数值/TXT/Excel/PNG、CIDialog 分发及混合报告交互的测试设计；其他逐表引用见 CSV；baseline 与最终 XML 中对应引用均已执行通过。本清单维护者未运行测试，而是读取主任务证据；不能将通用测试通过等同于每张表每个分支都运行。

### 23 个构造/转换/输出模块（其中 21 个含直接构造）

- code/GRR.py
- code/chi2_dialog.py
- code/chi_sq.py
- code/control_chart.py
- code/cpk.py
- code/describe.py
- code/dialog.py
- code/dist_fit.py
- code/fit_dialog.py
- code/linear_fit.py
- code/linear_plot.py
- code/nonpara_cor.py
- code/one_way_ANOVA.py
- code/ortho_fit.py
- code/pandastable_local/core_orig.py
- code/pandastable_local/dialogs.py
- code/pandastable_local/stats.py
- code/proportion_test.py
- code/stat_table.py
- code/t_test.py
- code/ti.py
- code/two_way_anova.py
- code/utilities.py

### 19 个报告模块

- code/GRR.py
- code/chi2_dialog.py
- code/chi_sq.py
- code/control_chart.py
- code/cpk.py
- code/describe.py
- code/dist_fit.py
- code/fit_dialog.py
- code/linear_fit.py
- code/linear_plot.py
- code/nonpara_cor.py
- code/one_way_ANOVA.py
- code/ortho_fit.py
- code/pandastable_local/stats.py
- code/proportion_test.py
- code/t_test.py
- code/ti.py
- code/two_way_anova.py
- code/utilities.py

## 已完成动态证据与剩余限制

- 本次刷新以实际文件系统为准：143 个 Python（HEAD 跟踪 139，新增 G19 文档脚本 3 个、新测试 1 个）。相较首次 140 快照，补入 supplemental/benchmark.py、summarize_performance.py、tests/test_g19_integration.py；acceptance.py 已在首次快照内。未写其他仓库文件。
- baseline：baseline-pytest.xml / baseline-pytest.txt，2096 passed、112 warnings；其中 G12 inventory 15、G12 tables 9、G7 tables 12、G9 tables 111、G10 tables 41、G11 quality tables 122 个参数化实例。它们是实际执行结果，不能分摊为 82 张表逐分支覆盖率。
- baseline 与当前源码 SHA256 比较仅 proportion_test.py、test_g9_tables.py 改变；因此 baseline 是修复前记录。修复后专项 fisher-related-final.xml：308 passed、59 warnings（G16 117、G19 integration 2、G9 111、p1/p2 fixes 78）。旧源码失败重现属于缺陷证据，不混作修复后失败。
- 模块关联实例数只从可解析 test_ 调用及 XML testcase 对照计算；是关联用例的运行结果，不等于各函数或所有分支动态通过。fixture 注入、实例方法与动态分派可能漏关联。未关联核心入口继续具体列出；“未建立关联”不表示已证实缺测。
- GUI：acceptance.py 的 gui-export-acceptance.json 已记录 1,003 行 TXT/复制一致、Excel 全行检查、关闭清理，三轴增强复跑 JSON 写入晚于 acceptance.py 更新；脚本断言 selected_columns 与轴数均为 3、每轴恰好一条线、逐轴 ydata 对照稳定排序后的真实列（含 NaN）且 xdata 长 1,000，vendor 3 曲线，无 Tk callback 错误。PNG 超限为预期拒绝，不能记成完整大 PNG 成功；图像/导出见同目录产物。
- 性能：G19-performance-results.csv / performance-summary.json / performance-summary.log：165 个有效阶段、495 个样本、无不完整场景。新增 check_repeats 入口已纳入清单；performance-integrity.json 记录 38 统计、26 数据配对、12 current、11 before、39 supplemental，repeat ID/样本有限性/计划阶段完整性均通过，冷积分 5/10 两规模各 3 个独立进程。只读核对 CSV 行数、每阶段样本数和汇总一致，未重跑。统计六组 38 个组合、数据配对、12 个报告绘图场景、39 个 supplemental 原场景按实际脚本分支关联；历史 G16 与当前同时负载不等价，before_compat_only 也不等价于旧失败版本成功。解释边界详见 performance-conditions.md。
- B-01：proportion_test.p_likelihood_ratio 的旧 LR 极端性定义问题仍未解决；全绿回归和耗时记录不能证明其统计正确，模块仍部分验证。真实 PI、物理剪贴板往返、办公软件打开、所有 DPI/主题、长期资源趋势等仍未验证，详见 G19-issues.md。
- 最终全量：final-pytest.xml 已只读解析 2098 个 testcase，无 failure/error/skipped；final-pytest.txt 为 2098 passed、112 warnings、436.19s。最终 XML 中 G12 inventory 15、G12 tables 9、G19 integration 2 个实例通过。逐模块/逐表回填其可解析关联实例数；所有应用模块仍仅部分验证或未验证，不升级成全功能/全分支通过。

## 交付和并行工作边界

仅写入 G19-module-acceptance.csv、module-inventory-notes.md、g12-table-check.csv；保留其他工作者基线、环境记录、代码及测试改动。静态源行号是本次快照定位，后续并行编辑可能使行号漂移；本清单不宣称人工逐分支运行验收。
