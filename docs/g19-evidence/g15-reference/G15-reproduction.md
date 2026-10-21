# G15 复现步骤

日期：2026-10-21。所有项目文件保持只读；输出根目录 `C:\Users\shaoy\AppData\Local\Temp\Minijmp-G15-20261021-101528`。

## 环境

- 项目解释器：`C:\Users\shaoy\Documents\Minijmp\.venv\Scripts\python.exe`（Python 3.11.9）。
- 具体依赖版本/路径：environment.json；完整已安装包：installed-packages.txt；CPU/RAM/电源：cpu.json、machine.json、power-scheme.txt。
- 固定种子20261021、PYTHONHASHSEED=0、OMP/OPENBLAS/MKL/NUMEXPR线程1。controller按场景启动独立venv Python子进程，串行运行。
- 不安装/升级依赖，不使用Codex bundled runtime。当前会话先确认解释器/依赖；不能仅用PATH裸python。
- 源码来自当前含未提交修改的工作区，Git HEAD不足以单独复现。source-snapshot保留123份Python及requirements.txt、G12 fixture、UI default.conf，共126文件；SHA以file-hashes-before.json为准。

## 输入与规模语义

所有数据在计时前创建，不连接PI。NumPy default_rng(20261021)；常规数据Normal(10,1)，相关矩阵各变量独立标准正态，线性X每水平约5次重复、Y=2X+正态噪声；统计组按切片或两因子标签生成。描述统计/质量/合并覆盖1k、10k、50k，适用处100k行；回归1k/3k/10k避免平方扫描的危险组合。变量5/10/20/40，ANOVA组5/20/50；SPC100/1k/10k/50k。

时间序列3条曲线/3轴、倒序datetime秒时间，分测prepare/plot/Agg/Tk/Dialog。多表20张独立100×7报告；宽表100×100。二项中心x=N/2，另有x=.49N的有效非中心测试。PI为Timestamp+20个数值tag的离线JSON，json.loads和_reader_json分阶段；CSV由本地合成DataFrame写UTF-8，仅临时输入。multi_var的n是每组大小（3组）；calculate_d3的n是子组大小5或10，每规模3个独立cold进程。

精确参数由scenarios.json、scenarios-extra.json、scenarios-refine.json及每个raw JSON的scenario字段保存；benchmark.py保存全部数据构造逻辑。首次完整批次后执行补测和两项有界预算调整，同名正式结果覆盖前会复制旧结果到preliminary。

## 命令

为保护本次交付，先将整个输出目录复制到新的临时目录再复现；脚本以自身目录存放结果，会覆盖同ID测量和临时导出。以下以复制后的目录作为$out，不要直接覆盖原证据。

```powershell
$python = "C:\Users\shaoy\Documents\Minijmp\.venv\Scripts\python.exe"
$out = "<复制后的G15临时输出目录>"
$env:PYTHONDONTWRITEBYTECODE = "1"
$env:PYTHONIOENCODING = "utf-8"
$env:MPLCONFIGDIR = Join-Path $out "mplconfig"

# 推荐用保留源码快照，避免以后工作区改动影响结果。
& $python -B "$out\benchmark.py" --repo "$out\source-snapshot" --scenarios "$out\scenarios.json"
& $python -B "$out\benchmark.py" --repo "$out\source-snapshot" --scenarios "$out\scenarios-extra.json"
& $python -B "$out\benchmark.py" --repo "$out\source-snapshot" --scenarios "$out\scenarios-refine.json"

# 单个场景ID或整个函数族，--filter采用精确匹配。
& $python -B "$out\benchmark.py" --repo "$out\source-snapshot" --filter "linear_fit-n1000-p1"
& $python -B "$out\benchmark.py" --repo "$out\source-snapshot" --filter "df_combine"
```

--resume跳过已有同名JSON（包括失败/不完整记录）；只用于知道哪些场景应跳过的受控续跑。默认不跳过。每个worker用Windows Job Object限制1536 MiB总提交量，kill-on-close结束整个子树，包含venv重定向器；命令时限35–120秒是整场景预算。超时后保留已完成阶段/重复及日志，状态timeout优先于venv wrapper可能给出的0退出码。

## 计时与内存

measure在GC之后计perf_counter/process_time，数据生成/导入排除；函数内部准备、计算和格式化仍计入。report_gui从现有真实结果窗口插入到update结束；table_gui为MTable、statusbar=True、toolbar=False，构造/show/显式redraw；scroll和redraw分别测。time_series_tk为真实TkAgg；time_series_dialog通过真实Dialog.apply验证双次prepare/toolbar/替换流程；Agg指标完全独立。

process_peak_rss_mib为Windows生命周期累计峰值工作集，不是阶段分配峰值；rss_before/after与private_commit是瞬时读数。预热、导入、输入/上阶段均在进程峰值范围内。profile单独调用且不加入正式计时；高规模通常跳过profile，仅保留小/中规模定位证据。

普通场景repeat=0为预热、1/2/3正式；冷积分没有预热，cold_integral是新进程首次调用，warm_cached_integral为后续缓存命中。中位数/最小/最大由summarize.py计算，原CSV保留所有单次值。失败行耗时空白，绝不填0；profile超时但先前3次compute完成时，可使用完整compute样本，不能称profile也完成。

## 结果文件

- G15-benchmark-results.csv：每次阶段/重复的wall/CPU/工作集/提交量、输入、状态、环境、原JSON和日志路径。
- G15-benchmark-summary.csv：各场景/阶段正式样本的中位数、范围、样本数及累计峰值；不足3次明确保留样本数。
- raw/*.json：完整参数、stage、worker PID、正式/预热记录、分页/曲线/缓存等断言证据。
- profiles/*.prof 与 *.txt：独立cProfile调用；不可将其绝对时间当无插桩基准。
- exports/：临时CSV/TXT/Excel；mplconfig/：隔离Matplotlib缓存；logs/：子进程输出；preliminary/：被替换的试运行，排除最终CSV。
- static-ast.json：全123源码的SHA、函数、调用、循环候选；static-statistics/ui.json：人工逐文件来源核对。build_inventory.py保证一文件一条记录。

summarize.py/build_inventory.py/write_report.py用于本次汇总，包含原工作区定位与基线校验信息；复制目录后若要重新生成汇总，先审查其中ROOT/绝对证据路径，不能把旧路径当新目录测量。本次报告本身保留最终原始数据，不依赖重新执行这些汇总脚本才能阅读。

## 本轮验证与限制

verification.json记录清单集合/重复项、所有脚本AST、结果样本完整性、源码snapshot和文件保护核验；inventory-pytest.txt记录本轮G12清单专项。没有重跑完整pytest，没有把G14历史1766 passed当本轮测试结果。真实PI、生产数据、剪贴板、完整应用启动/日志/图形历史、所有DPI/主题及长时间泄漏未测。

临时基准脚本按no-stop-gpt Audit复核：场景表、独立进程、Job内存/超时、阶段增量落盘和来源快照分别满足可复现/资源保护/不可修改仓库要求；没有新增性能测试框架、依赖、项目配置、后台业务功能或优化实现。生成器与断言只服务本次审查，不回写仓库。
