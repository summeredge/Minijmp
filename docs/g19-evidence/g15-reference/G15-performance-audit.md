# G15：Minijmp 全模块性能基准审查（只读）

日期：2026-10-21（Asia/Shanghai）。本报告只交付证据和建议，没有实施性能优化。

## 审查结论

计算、完整报告物化和同步导出仍是主要候选改造范围；G14的大表分页与延迟滚动已经存在且本轮真Tk基准完成。常见回归/相关分析中的重复统计值得先处理；不能把大数据表的所有慢操作笼统归因于Tk控件。

全仓递归枚举 **123 个Python文件**，每文件恰好一条审查记录；**71个应用源码全部完整读取并人工核对调用路径**。其余39个测试、10个文档/历史/证据脚本、2个工具、1个启动器也有AST静态审查及用途/副作用分类，未声称对全部测试逐行人工阅读。

独立场景 **153**；状态 {'ok': 138, 'error': 8, 'timeout': 7}。正式阶段统计 **218组**，其中 **210组达到3次测量**。冷积分每个n另有3个独立进程的首次调用。预热和失败/超时记录均保留在原始CSV；未完成阶段无虚构耗时。

## 仓库状态与基线

仓库：`C:\Users\shaoy\Documents\Minijmp`；开始HEAD：`feb9e6f0b3e7095b39d1fe872dedb90c69c5a7c5`。开始时已有 23 条Git状态记录，包括G13/G14未提交实现及其它修改。最终476个既有非缓存文件SHA256全部一致。审查期间检测到其它进程于10:16:24提交既有工作区内容，HEAD变为`38b907f0dcf62f234561838f3cca93ad0a8545ef`，Git状态从23条未提交记录变为干净；本审查未执行Git写操作，未回退该提交。此为Git状态变化例外，不是文件内容变化。详见git-transition.txt与git-state-change.json。

保存 `git-status-before.txt`、`git-status-after.txt`、`file-hashes-before.json`、`file-preservation.json`；另外保存126份源码/声明/所需fixture/UI配置快照在source-snapshot。Git内部元数据、.venv及缓存目录不属于项目源文件清单；未按预设数量或.gitignore截断枚举。

没有安装/升级依赖、连接PI、读取生产数据、操作系统剪贴板、执行完整业务启动器、commit、push或merge。Matplotlib缓存、输入、输出、日志、pytest临时文件均定向本临时目录。

## 测试环境与度量含义

解释器 `C:\Users\shaoy\Documents\Minijmp\.venv\Scripts\python.exe`，Python 3.11.9；Windows-10-10.0.26200-SP0；13th Gen Intel(R) Core(TM) i9-13905H，14核/20逻辑处理器；物理内存31.75 GiB；电源方案“平衡”。

| 库 | 版本 | 实际导入位置 |
| --- | --- | --- |
| numpy | 2.4.6 | C:\Users\shaoy\Documents\Minijmp\.venv\Lib\site-packages\numpy\__init__.py |
| pandas | 3.0.6 | C:\Users\shaoy\Documents\Minijmp\.venv\Lib\site-packages\pandas\__init__.py |
| scipy | 1.15.3 | C:\Users\shaoy\Documents\Minijmp\.venv\Lib\site-packages\scipy\__init__.py |
| matplotlib | 3.11.2 | C:\Users\shaoy\Documents\Minijmp\.venv\Lib\site-packages\matplotlib\__init__.py |
| statsmodels | 0.15.0 | C:\Users\shaoy\Documents\Minijmp\.venv\Lib\site-packages\statsmodels\__init__.py |
| openpyxl | 3.1.5 | C:\Users\shaoy\Documents\Minijmp\.venv\Lib\site-packages\openpyxl\__init__.py |
| PIL | 13.0.0 | C:\Users\shaoy\Documents\Minijmp\.venv\Lib\site-packages\PIL\__init__.py |
| prettytable | 3.18.0 | C:\Users\shaoy\Documents\Minijmp\.venv\Lib\site-packages\prettytable\__init__.py |

完整环境和已安装包见environment.json、installed-packages.txt；不使用Codex bundled runtime。固定种子20261021、PYTHONHASHSEED=0、BLAS/OpenMP线程数1；单场景串行进程，不同时执行多场性能测量。少量读文件/汇总活动及正常桌面后台负载不受控制，结果不是实验室隔离或多机基准。

perf_counter计wall，process_time计CPU；短调用CPU量化粒度较粗。Windows GetProcessMemoryInfo记录当前工作集、截至该阶段的**进程生命周期累计峰值工作集**、当前private commit。它们包含导入、输入、预热和已完成阶段，并非阶段分配峰值；不能将不同阶段峰值相减当作该阶段分配量，也不能从RSS未回落推断泄漏。未启用tracemalloc以免改变主计时。

每场景通常预热1次、正式3次，GC在计时前；数据生成与导入排除，函数自身清洗/格式化仍计入。profile是另一次独立调用，不计入正式计时。冷calculate_d3例外：3个新进程测首次积分，每进程再测3次缓存命中，冷/暖分开。

每场景Windows Job Object限制总提交内存1536 MiB并在关闭时结束子树；普通场景35–75秒，Excel与一次补齐重复的相关场景最高120秒。时限覆盖导入、预热、所有正式阶段和可选profile。超时不等于某一次统计或GUI显示耗时下界；已完成样本可用，未完成样本不推算。

## G12/G13/G14现有能力核对

| 能力 | 状态 | 当前证据/边界 |
| --- | --- | --- |
| G12统计表迁移/兼容TXT | 已实现 | 当前71源码清单与G12 fixture；StatTable→Minijmp.print→txt_viewer→TableBlock。82张逻辑表为既有G12/G13记录口径，本轮未重做表生产位置清点。 |
| G14大表分页 | 已实现 | stat_table.py:164/187/231；单表>1000单元格分页；每页≤100行/约1000单元格；末页内容断言。 |
| G14连续小表控件预算 | 已实现 | txt_output.py:110；累计Label预算2000；20张独立StatTable经真实Minijmp.print，完整TXT逐字符断言。 |
| G14同步输出+合并滚动 | 已实现 | MiniJMP.py:363；txt_output.py:200；唯一after_idle滚动，不是后台统计任务队列。 |
| G14保存/复制/Excel/PNG保护 | 已实现 | _text_chunks重建完整文本；Excel样式对象复用；PNG分配前尺寸/像素上限。PNG/复制本轮主要源码/已有测试核对，未操作真实剪贴板。 |
| SPC逐点报告 | 部分性能约束已实现 | 控制限常量归并已做；完整StatTable/ASCII生产仍随点数增长，本轮独立测量。 |
| G13原始时序 | 已实现 | 稳定排序、重复时间/NaN、原生多轴；prepare/构图/Agg/真实Tk/真实Dialog分测。 |
| pandastable仅画可见单元格 | 已实现但仍有全行/全列元数据 | core_orig.redrawVisible；MTable取消自动列宽；全行rowrange、列位置、网格等候选仍保留。真实100k×20刷新基准完成。 |
| PI读取异步 | 已实现；真实I/O未验证 | pi_import worker/queue/poll；本轮只运行离线协议解析，不能声称服务器响应已测。 |
| 通用后台统计/可取消Excel任务 | 未实现（仅现状） | 统计对话框和表级导出同步执行；本轮不以此自动要求新增通用框架。 |

已阅读docs/G12-table-migration-audit.md、docs/G13-time-series-acceptance.md、docs/G14-report-rendering-performance.md及对应测试/记录。G14文档中的1766 passed是之前的回归结果，本轮不冒充重跑；G12/G13旧启动器4失败也不沿用为当前失败。详见G15-reproduction.md的本轮验证清单。

## 实测瓶颈与优先级

P1指在本次常见交互规模（如1万行回归、千行少量变量相关）已经测得秒级严重停顿；P2指大规模数据/变量下已测得明显成本；P3为未实证、低频或需进一步定位。使用频率来自菜单可达性及操作性质推断，没有用户使用遥测。优先级不是单凭O(N²)决定。

| 编号 | 等级 | 发现 | 实际入口 |
| --- | --- | --- | --- |
| F01 | P1 | 常用线性回归的纯误差/饱和模型重复扫描 | 统计→线性回归→LinearFitDialog.apply→fit_plot(linear=True)→linear_fit；残差诊断还可能再次调用 |
| F02 | P1 | Hoeffding矩阵在常见变量数下阻塞计算 | 统计→多变量相关→MCorDialog.apply，勾选Hoeffding；随后仍进入multi_fit。 |
| F11 | P1 | 多样本方差检验反复计算每组统计量 | 统计→多样本标准差检验→MultiVarDialog.apply→multi_pop_var_test；3组各1000观测为常见可用规模。 |
| F03 | P2 | Pearson相关矩阵和Axes创建随变量数放大 | 当前MCorDialog调用multi_fit；multi_fit_orig无当前生产调用，保留独立公开旧入口和测试。 |
| F04 | P2 | 二项PMF与单比例检验重复标量概率求值 | 概率图→二项分布；统计→单比例检验→Prop1SDialog→prop_test_1sample；LR仅独立旧/诊断函数，不计当前GUI合计。 |
| F05 | P2 | 粘贴合并逐单元格访问pandas | MTable粘贴/合并→df_combine；纯函数基准排除系统剪贴板。 |
| F06 | P2 | 分布拟合的逐点似然与多模型成本 | 统计→分布拟合→FitDistDialog；直方图拟合也使用compare_dist。 |
| F07 | P2 | 报告构建和Excel导出仍按完整数据同步物化 | SPC质量分析→逐点明细→StatTable→Minijmp.print；每表导出Excel菜单。 |
| F08 | P2 | 双因素/GRR中的重复组统计与重复拟合 | 双因素ANOVA、质量→GRR Auto；各自实测，不用单因素结果代替。 |
| F09 | P2 | 全表文本查找和相关分析前处理 | 编辑→查找文本；多变量相关数据清洗；默认CSV导入预览。 |
| F10 | P2 | 时序原始曲线、多表与宽表的绘制边界 | 图形→时间序列图；报告连续小表/宽表。 |

### F01 P1：常用线性回归的纯误差/饱和模型重复扫描

位置：`code/linear_fit.py`，`linear_fit`，行94–123。入口：统计→线性回归→LinearFitDialog.apply→fit_plot(linear=True)→linear_fit；残差诊断还可能再次调用

数据/原始测量（每个场景ID对应raw/<ID>.json；全部单次值在G15-benchmark-results.csv）：
| 场景/原始JSON文件名 | 阶段 | 正式样本数 | 中位秒 | 最小–最大秒 | CPU中位秒 | 进程累计峰值MiB | 场景状态 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| linear_fit-n1000-p1 | compute | 3 | 0.0685 | 0.0630–0.0813 | 0.0625 | 154.9 | ok |
| linear_fit-n10000-p1 | compute | 3 | 4.5988 | 4.3985–4.7089 | 4.3750 | 158.0 | ok |
| linear_fit-n3000-p1 | compute | 3 | 0.4405 | 0.4265–0.5771 | 0.4375 | 155.6 | ok |

定位证据：profiles/linear_fit-n1000-p1.txt 中 statistics.mean 调用2003次；94、120行的内层列表对每个观测重新扫描整列。关闭报告也执行这两段。

建议及预期收益：按X水平一次分组，先求各组计数/均值/组内平方和，再计算SSPE/SSM。减少平方级重复扫描；具体加速比尚未实施验证。

正确性/兼容风险：浮点求和顺序、重复X判等、DFPE/DFLF、零纯误差和不可估计分支必须保持；不能改动失拟检验定义。

可复用实现/验证：沿用现有报告StatTable投影、线性拟合数值/边界测试；字典分组可用标准库，不必新增依赖。

### F02 P1：Hoeffding矩阵在常见变量数下阻塞计算

位置：`code/nonpara_cor.py + code/fit_dialog.py`，`hoeffd_example / print_multi_col_tables`，行45–83 / 467–499。入口：统计→多变量相关→MCorDialog.apply，勾选Hoeffding；随后仍进入multi_fit。

数据/原始测量（每个场景ID对应raw/<ID>.json；全部单次值在G15-benchmark-results.csv）：
| 场景/原始JSON文件名 | 阶段 | 正式样本数 | 中位秒 | 最小–最大秒 | CPU中位秒 | 进程累计峰值MiB | 场景状态 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| hoeffding-n100-p1 | compute | 3 | 0.0041 | 0.0037–0.0041 | 0.000000 | 154.1 | ok |
| hoeffding-n1000-p1 | compute | 3 | 0.2040 | 0.1988–0.2055 | 0.2031 | 154.2 | ok |
| hoeffding-n3000-p1 | compute | 3 | 1.7955 | 1.7771–2.2784 | 1.7500 | 155.3 | ok |
| matrix_hoeffding-n100-p10 | compute | 3 | 0.3675 | 0.3537–0.6491 | 0.3594 | 157.0 | ok |
| matrix_hoeffding-n100-p5 | compute | 3 | 0.0911 | 0.0902–0.0922 | 0.0938 | 156.8 | ok |
| matrix_hoeffding-n1000-p5 | compute | 3 | 5.1397 | 5.1259–5.1471 | 5.1094 | 157.9 | ok |

定位证据：profiles/hoeffding-n1000-p1.txt：4003次Python sum，主要时间在四组逐点整列比较。矩阵又计算K²个有序对及对角。10,000样本单对和1,000样本×10变量被资源时限中止，不能给这些未完成调用编造中位数。

建议及预期收益：先复用无序变量对的标量系数/p值并填充对称矩阵；再单独研究保留并列秩权重的高效Hoeffding算法。前者减少重复对数，后者才针对N²核心。

正确性/兼容风险：并列秩的1/4、1/2权重、对角/常量输入、D及近似p值必须一致；不能拿Spearman或普通散点替代Hoeffding。

可复用实现/验证：复用既有nonpara_cor检验和StatTable矩阵显示；现有Kendall/Spearman可作接口参考，不能作Hoeffding算法替代。

### F11 P1：多样本方差检验反复计算每组统计量

位置：`code/chi_sq.py`，`multi_pop_var_test / OBrien / Levene / Brown_Forsythe / nested one_way_anova`，行264–307。入口：统计→多样本标准差检验→MultiVarDialog.apply→multi_pop_var_test；3组各1000观测为常见可用规模。

数据/原始测量（每个场景ID对应raw/<ID>.json；全部单次值在G15-benchmark-results.csv）：
| 场景/原始JSON文件名 | 阶段 | 正式样本数 | 中位秒 | 最小–最大秒 | CPU中位秒 | 进程累计峰值MiB | 场景状态 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| multi_var-n100-p3 | compute | 3 | 0.0963 | 0.0948–0.0968 | 0.0938 | 142.7 | ok |
| multi_var-n1000-p3 | compute | 3 | 6.0812 | 6.0582–6.4579 | 5.9844 | 143.1 | ok |

定位证据：profiles/multi_var-n1000-p3.txt记录15009次mean、3000次variance、3000次median；profile mean累计13.160秒/总16.360秒，仅用于定位，未插桩正式中位数约6秒。每组3000点在50秒整场景预算内连预热也未完成。

建议及预期收益：每组的均值、方差、中位数计算一次；内部ANOVA也复用组均值。减少组内平方级重复统计，优先级高于已经低于秒级的小规模单因素逐对检验。

正确性/兼容风险：O’Brien修正、Levene/Brown-Forsythe中心量、自由度、缺失处理和原有报告值必须一致；不能只测正态样本就替换检验方法。

可复用实现/验证：现有statistics与按组数据结构足够；复用多方差数值/边界测试与G9统计表契约，无需新依赖。

### F03 P2：Pearson相关矩阵和Axes创建随变量数放大

位置：`code/linear_plot.py`，`multi_fit / multi_fit_orig / create_inset_grid`，行172 / 250 / 280。入口：当前MCorDialog调用multi_fit；multi_fit_orig无当前生产调用，保留独立公开旧入口和测试。

数据/原始测量（每个场景ID对应raw/<ID>.json；全部单次值在G15-benchmark-results.csv）：
| 场景/原始JSON文件名 | 阶段 | 正式样本数 | 中位秒 | 最小–最大秒 | CPU中位秒 | 进程累计峰值MiB | 场景状态 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| multi_fit-n1000-p10 | matrix_and_artists | 3 | 1.0177 | 0.9295–1.5800 | 1.0000 | 190.6 | ok |
| multi_fit-n1000-p10 | agg_first_draw | 3 | 0.5735 | 0.3445–0.6115 | 0.5156 | 190.6 | ok |
| multi_fit-n1000-p10 | agg_redraw | 3 | 0.7891 | 0.3263–1.7151 | 0.7031 | 190.6 | ok |
| multi_fit-n1000-p20 | matrix_and_artists | 3 | 4.3148 | 4.2043–4.3310 | 4.2656 | 288.9 | ok |
| multi_fit-n1000-p20 | agg_first_draw | 3 | 1.0450 | 1.0440–1.0776 | 1.0312 | 289.1 | ok |
| multi_fit-n1000-p20 | agg_redraw | 3 | 0.9944 | 0.9816–1.0442 | 0.9844 | 289.1 | ok |
| multi_fit-n1000-p40 | matrix_and_artists | 1 | 18.3078 | 18.3078–18.3078 | 17.8594 | 686.4 | timeout |
| multi_fit-n1000-p5 | matrix_and_artists | 3 | 0.1835 | 0.1759–0.7410 | 0.1719 | 167.9 | ok |
| multi_fit-n1000-p5 | agg_first_draw | 3 | 0.1086 | 0.1039–0.4848 | 0.1094 | 167.9 | ok |
| multi_fit-n1000-p5 | agg_redraw | 3 | 0.1802 | 0.1043–0.4084 | 0.1406 | 167.9 | ok |
| multi_fit_orig-n1000-p10 | matrix_and_artists | 3 | 0.9312 | 0.9113–0.9599 | 0.9219 | 189.9 | ok |
| multi_fit_orig-n1000-p10 | agg_first_draw | 3 | 0.4018 | 0.3896–0.4204 | 0.4062 | 189.9 | ok |
| multi_fit_orig-n1000-p10 | agg_redraw | 3 | 0.3870 | 0.3787–0.3957 | 0.3750 | 189.9 | ok |
| multi_fit_orig-n1000-p20 | matrix_and_artists | 3 | 4.2259 | 4.2139–4.2802 | 4.1719 | 288.3 | ok |
| multi_fit_orig-n1000-p20 | agg_first_draw | 3 | 2.2918 | 2.2805–2.3093 | 2.2500 | 288.3 | ok |
| multi_fit_orig-n1000-p20 | agg_redraw | 3 | 1.0976 | 1.0861–1.1085 | 1.0781 | 288.5 | ok |
| multi_fit_orig-n1000-p5 | matrix_and_artists | 3 | 0.1863 | 0.1852–0.1967 | 0.1875 | 166.7 | ok |
| multi_fit_orig-n1000-p5 | agg_first_draw | 3 | 0.1165 | 0.1114–0.1318 | 0.1250 | 166.7 | ok |
| multi_fit_orig-n1000-p5 | agg_redraw | 3 | 0.1059 | 0.1054–0.1114 | 0.1094 | 166.7 | ok |

定位证据：两版K²矩阵调用；默认ellipse又对每个无序对重算。独立profile场景在K=5断言Pearson共35次（25+10）。两版都创建(K−1)²子轴；当前版为inset_axes，原版为subplots。旧版40变量同样触发时限。

建议及预期收益：将矩阵统计与绘图消费连接，复用成对统计，按实际可见三角创建Axes；减少重复排名/均值和未使用Artist。

正确性/兼容风险：Pearson字典中的协方差/椭圆方向不是任意可镜像的所有字段；保持p值、CI、标签、轴方向、图形导出和布局。

可复用实现/验证：同文件已有cor_res，fit_plot可消费已算结果；旧版只供对照，不能直接宣布替换当前版。

### F04 P2：二项PMF与单比例检验重复标量概率求值

位置：`code/binomial.py + code/proportion_test.py`，`binomial / p_blaker / p_sterne / prop_test_1sample`，行21–82 / 102–195。入口：概率图→二项分布；统计→单比例检验→Prop1SDialog→prop_test_1sample；LR仅独立旧/诊断函数，不计当前GUI合计。

数据/原始测量（每个场景ID对应raw/<ID>.json；全部单次值在G15-benchmark-results.csv）：
| 场景/原始JSON文件名 | 阶段 | 正式样本数 | 中位秒 | 最小–最大秒 | CPU中位秒 | 进程累计峰值MiB | 场景状态 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| binomial-n10000-p1 | compute | 3 | 1.0530 | 1.0224–1.0765 | 0.9688 | 139.2 | ok |
| binomial-n50000-p1 | compute | 3 | 5.3511 | 5.2035–5.4886 | 5.2500 | 143.4 | ok |
| binomial-noncentral-n1000 | compute | 3 | 0.1018 | 0.0980–0.1025 | 0.0938 | 138.7 | ok |
| binomial-noncentral-n10000 | compute | 3 | 1.1087 | 1.0787–1.1896 | 1.0469 | 140.0 | ok |
| binomial-noncentral-n50000 | compute | 3 | 5.1212 | 4.9453–5.1726 | 5.0000 | 143.0 | ok |
| p_blaker-n1000-p1 | compute | 3 | 0.0310 | 0.0294–0.0319 | 0.0312 | 142.1 | ok |
| p_blaker-n10000-p1 | compute | 3 | 0.2910 | 0.2843–0.2964 | 0.2812 | 142.9 | ok |
| p_blaker-n50000-p1 | compute | 3 | 1.5460 | 1.4896–1.7143 | 1.5000 | 146.0 | ok |
| p_likelihood_ratio-n1000-p1 | compute | 3 | 0.0321 | 0.0319–0.0323 | 0.0312 | 142.1 | ok |
| p_likelihood_ratio-n10000-p1 | compute | 3 | 0.3021 | 0.2986–0.3067 | 0.2969 | 142.2 | ok |
| p_likelihood_ratio-n50000-p1 | compute | 3 | 1.7458 | 1.4903–1.9810 | 1.7031 | 143.7 | ok |
| p_sterne-n1000-p1 | compute | 3 | 0.0589 | 0.0560–0.0653 | 0.0625 | 142.0 | ok |
| p_sterne-n10000-p1 | compute | 3 | 0.6349 | 0.6196–0.6925 | 0.6250 | 142.8 | ok |
| p_sterne-n50000-p1 | compute | 3 | 3.2001 | 3.0397–3.3978 | 3.1250 | 146.8 | ok |
| prop_test_1sample-n10000-p1 | compute | 3 | 2.1106 | 1.9341–2.1748 | 2.0312 | 143.5 | ok |
| prop_test_1sample-n50000-p1 | compute | 3 | 10.4456 | 10.0287–10.6382 | 9.9688 | 148.5 | timeout |
| prop_test_1sample-noncentral-n1000 | compute | 3 | 0.2219 | 0.2046–0.2231 | 0.2344 | 142.7 | ok |
| prop_test_1sample-noncentral-n10000 | compute | 3 | 1.9491 | 1.9403–2.0073 | 1.9375 | 144.1 | ok |
| prop_test_1sample-noncentral-n50000 | compute | 3 | 9.7333 | 9.6534–10.4075 | 9.5156 | 149.4 | ok |

定位证据：profiles/p_blaker-n1000-p1.txt：1001次pmf；Sterne比较/求和重复pmf；单比例同时调用binomial、两种Blaker路径及Sterne。中心点N=1000既有异常单列在未完成验证表，非中心0.49N已正常测量。

建议及预期收益：在不改变尾概率/离散边界定义前提下使用向量化PMF或稳定cdf/sf，复用相同支持集概率。N=50,000仍为秒级，减少Python→SciPy标量开销预期收益高，未提供未测加速比。

正确性/兼容风险：极端尾部下溢、相等比较、全零/全事件、包含端点与离散检验定义；不可把LR、Sterne、Blaker当等价方法。

可复用实现/验证：poisson已有cdf/sf用法；blakerCI已有稳定cdf/sf入口和边界测试，可复用方法而非替换定义。

### F05 P2：粘贴合并逐单元格访问pandas

位置：`code/df_combine.py`，`df_combine`，行5–23。入口：MTable粘贴/合并→df_combine；纯函数基准排除系统剪贴板。

数据/原始测量（每个场景ID对应raw/<ID>.json；全部单次值在G15-benchmark-results.csv）：
| 场景/原始JSON文件名 | 阶段 | 正式样本数 | 中位秒 | 最小–最大秒 | CPU中位秒 | 进程累计峰值MiB | 场景状态 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| df_combine-n1000-p5 | compute | 3 | 0.0457 | 0.0451–0.0458 | 0.0469 | 91.0 | ok |
| df_combine-n10000-p5 | compute | 3 | 0.4438 | 0.4421–0.4477 | 0.4531 | 95.6 | ok |
| df_combine-n100000-p5 | compute | 3 | 4.7710 | 4.7498–4.8572 | 4.5938 | 135.3 | ok |
| df_combine-n50000-p5 | compute | 3 | 2.4602 | 2.3918–2.6977 | 2.4219 | 113.0 | ok |

定位证据：profiles/df_combine-n1000-p5.txt：5500次iloc __getitem__约占累计时间主要部分；100,000×5扫描550,000输入单元格。

建议及预期收益：分配结果后按二维块拷贝/覆盖，减少标量iloc派发。复杂度仍O(单元格数)，收益来自常数。

正确性/兼容风险：混合dtype、NaN、覆盖顺序、行列扩张、重复/生成列名、粘贴偏移与索引语义。

可复用实现/验证：复用现有DataFrame/NumPy块操作、TableModel更新和文件/表格回归测试。

### F06 P2：分布拟合的逐点似然与多模型成本

位置：`code/dist_fit.py`，`ABL / fit_norm / compare_dist`，行15–31 / 112 / 250。入口：统计→分布拟合→FitDistDialog；直方图拟合也使用compare_dist。

数据/原始测量（每个场景ID对应raw/<ID>.json；全部单次值在G15-benchmark-results.csv）：
| 场景/原始JSON文件名 | 阶段 | 正式样本数 | 中位秒 | 最小–最大秒 | CPU中位秒 | 进程累计峰值MiB | 场景状态 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| compare_dist-n1000-p1 | compute | 3 | 0.3015 | 0.2992–0.3059 | 0.2969 | 155.5 | ok |
| compare_dist-n10000-p1 | compute | 3 | 3.0303 | 2.9914–3.1659 | 2.9844 | 156.9 | ok |
| compare_dist-n5000-p1 | compute | 3 | 1.7551 | 1.5773–2.2893 | 1.6562 | 156.7 | ok |
| fit_norm-n1000-p1 | compute | 3 | 0.0303 | 0.0298–0.0309 | 0.0312 | 154.5 | ok |
| fit_norm-n10000-p1 | compute | 3 | 0.2858 | 0.2765–0.2926 | 0.2812 | 155.5 | ok |
| fit_norm-n50000-p1 | compute | 3 | 3.8215 | 1.6278–7.5719 | 3.7656 | 160.3 | ok |

定位证据：profiles/fit_norm-n1000-p1.txt中1000次scalar pdf占绝大多数profile累计时间。compare_dist基准断言六种候选全部成功，防止吞错造成伪快。p_simulation唯一调用被注释，当前不执行10000次模拟。

建议及预期收益：评估向量化pdf/logpdf与一次求和；分别定位t/Weibull优化器，避免把六模型耗时全归因到一个函数。

正确性/兼容风险：原实现ln(pdf)与logpdf在极端尾部可能改变下溢/失败行为；AICc、BIC、参数估计及成功模型集合须回归。

可复用实现/验证：AD已有向量化cdf示例；现有各拟合器/比较报告测试。

### F07 P2：报告构建和Excel导出仍按完整数据同步物化

位置：`code/stat_table.py + code/control_chart.py`，`StatTable.__new__ / _print_spc_report / export_excel`，行39 / 200–270 / 90–119。入口：SPC质量分析→逐点明细→StatTable→Minijmp.print；每表导出Excel菜单。

数据/原始测量（每个场景ID对应raw/<ID>.json；全部单次值在G15-benchmark-results.csv）：
| 场景/原始JSON文件名 | 阶段 | 正式样本数 | 中位秒 | 最小–最大秒 | CPU中位秒 | 进程累计峰值MiB | 场景状态 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| exports-n1000-p7 | export_excel | 3 | 0.1061 | 0.1050–0.1084 | 0.1094 | 106.0 | ok |
| exports-n1000-p7 | txt_write | 3 | 0.000782 | 0.000753–0.000801 | 0.000000 | 106.0 | ok |
| exports-n10000-p7 | export_excel | 3 | 4.3032 | 3.6333–4.5530 | 4.1250 | 143.2 | ok |
| exports-n10000-p7 | txt_write | 3 | 0.0042 | 0.0031–0.0046 | 0.0156 | 143.2 | ok |
| exports-n50000-p7 | export_excel | 3 | 22.8857 | 22.0211–22.9782 | 20.5938 | 316.1 | ok |
| exports-n50000-p7 | txt_write | 3 | 0.0130 | 0.0100–0.0156 | 0.000000 | 316.1 | ok |
| spc_report-n100-p1 | report_build | 3 | 0.0037 | 0.0033–0.0057 | 0.000000 | 156.1 | ok |
| spc_report-n1000-p1 | report_build | 3 | 0.0264 | 0.0258–0.0279 | 0.0312 | 157.6 | ok |
| spc_report-n10000-p1 | report_build | 3 | 0.2460 | 0.2457–0.2541 | 0.2500 | 171.2 | ok |
| spc_report-n50000-p1 | report_build | 3 | 4.5603 | 2.8144–5.6123 | 4.1875 | 229.7 | ok |
| stat_table-n1000-p7 | report_build | 3 | 0.0303 | 0.0291–0.0347 | 0.0312 | 98.3 | ok |
| stat_table-n10000-p7 | report_build | 3 | 0.2961 | 0.2955–0.2982 | 0.2969 | 112.3 | ok |
| stat_table-n100000-p7 | report_build | 3 | 12.4811 | 12.4475–13.7209 | 11.2969 | 252.9 | ok |
| stat_table-n50000-p7 | report_build | 3 | 6.0905 | 4.9854–6.2718 | 5.6250 | 175.1 | ok |

定位证据：profiles/spc_report-n1000-p1.txt中StatTable/PrettyTable字符串生成占主要累计时间；stat_table profile同样显示完整ASCII宽度计算与行字符串化。G14分页只约束Tk呈现，不删除旧str协议。Excel50,000×7的独立导出为秒级同步工作簿处理。

建议及预期收益：先定位并复用报告生产端重复格式化；若需惰性ASCII或流式Excel，单独设计并验证旧str协议/导出能力；必要时再评估任务级可取消导出。

正确性/兼容风险：TXT逐字符、复制选择、Excel原始精度/公式标签防护/格式/列宽；不能仅删必要values/display/text三种表示。

可复用实现/验证：G14已实现分页、样式复用和_text_chunks；复用这些机制及G7–G14协议测试，勿重复建设分页。

### F08 P2：双因素/GRR中的重复组统计与重复拟合

位置：`code/two_way_anova.py + code/GRR.py`，`two_way_anova / grr_master`，行98–105 / 349–402。入口：双因素ANOVA、质量→GRR Auto；各自实测，不用单因素结果代替。

数据/原始测量（每个场景ID对应raw/<ID>.json；全部单次值在G15-benchmark-results.csv）：
| 场景/原始JSON文件名 | 阶段 | 正式样本数 | 中位秒 | 最小–最大秒 | CPU中位秒 | 进程累计峰值MiB | 场景状态 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| anova_pairs-n1000-p20 | compute | 3 | 0.0204 | 0.0202–0.0219 | 0.0156 | 154.8 | ok |
| anova_pairs-n1000-p5 | compute | 3 | 0.0041 | 0.0038–0.0042 | 0.000000 | 154.9 | ok |
| anova_pairs-n1000-p50 | compute | 3 | 0.0940 | 0.0939–0.0961 | 0.0938 | 155.0 | ok |
| anova_pairs-n10000-p20 | compute | 3 | 0.0729 | 0.0719–0.0734 | 0.0781 | 155.1 | ok |
| anova_pairs-n10000-p5 | compute | 3 | 0.0190 | 0.0185–0.0196 | 0.0156 | 155.3 | ok |
| anova_pairs-n10000-p50 | compute | 3 | 0.2319 | 0.2245–0.2339 | 0.2188 | 155.1 | ok |
| anova_pairs-n50000-p20 | compute | 3 | 0.2906 | 0.2818–0.3054 | 0.2812 | 156.4 | ok |
| anova_pairs-n50000-p5 | compute | 3 | 0.0820 | 0.0795–0.0842 | 0.0781 | 156.9 | ok |
| anova_pairs-n50000-p50 | compute | 3 | 0.8042 | 0.7965–0.8587 | 0.8125 | 156.6 | ok |
| grr-n300-p10 | compute | 3 | 0.0377 | 0.0364–0.0435 | 0.0469 | 179.4 | ok |
| grr-n3000-p10 | compute | 3 | 0.3458 | 0.3449–0.3487 | 0.3438 | 184.2 | ok |
| grr-n30000-p10 | compute | 2 | 18.4303 | 18.3414–18.5193 | 18.0156 | 216.2 | timeout |
| two_way-n150-p5 | compute | 3 | 0.0110 | 0.0107–0.0131 | 0.0156 | 178.6 | ok |
| two_way-n1500-p5 | compute | 3 | 0.0839 | 0.0837–0.0855 | 0.0938 | 179.8 | ok |
| two_way-n15000-p5 | compute | 3 | 4.3702 | 4.2740–4.7131 | 4.3281 | 190.2 | ok |

定位证据：two_way_anova交互SSE为每个观测重算cell mean；GRR Auto的小规模profile实际进入two_way_anova三次。ANOVA K=50 profile实际调用嵌套t_test_anova 1225次。

建议及预期收益：缓存当前一次分析中的组均值/中位数和可复用模型结果；优先处理实测更慢的路径，单因素逐对比较当前小中规模无迫切改造理由。

正确性/兼容风险：III型SS、不平衡设计、交互筛选阈值和删交互后的模型不能混用；字母分组与并列均值稳定性需保持。

可复用实现/验证：现有group_by2factors、各模型数值测试和报告投影；分组器本身也需避免重复keys.index。

### F09 P2：全表文本查找和相关分析前处理

位置：`code/dialog.py + code/utilities.py + code/pandastable_local/csv_import.py`，`findRepDialog.find / number_2Dlist / detect_csv / read_csv`，行20–46 / 581–600 / 18–95。入口：编辑→查找文本；多变量相关数据清洗；默认CSV导入预览。

数据/原始测量（每个场景ID对应raw/<ID>.json；全部单次值在G15-benchmark-results.csv）：
| 场景/原始JSON文件名 | 阶段 | 正式样本数 | 中位秒 | 最小–最大秒 | CPU中位秒 | 进程累计峰值MiB | 场景状态 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| csv_import-n1000-p10 | csv_detect | 3 | 0.0076 | 0.0075–0.0081 | 0.0156 | 94.8 | ok |
| csv_import-n1000-p10 | csv_read | 3 | 0.0148 | 0.0146–0.0149 | 0.0156 | 94.8 | ok |
| csv_import-n10000-p10 | csv_detect | 3 | 0.0838 | 0.0831–0.0853 | 0.0781 | 118.6 | ok |
| csv_import-n10000-p10 | csv_read | 3 | 0.1025 | 0.1015–0.1087 | 0.0938 | 118.6 | ok |
| csv_import-n100000-p10 | csv_detect | 3 | 1.0585 | 1.0372–1.1568 | 1.0469 | 348.4 | ok |
| csv_import-n100000-p10 | csv_read | 3 | 1.1517 | 1.1407–1.4301 | 1.1562 | 348.4 | ok |
| csv_import-n50000-p10 | csv_detect | 3 | 0.4900 | 0.4897–0.5424 | 0.4844 | 221.2 | ok |
| csv_import-n50000-p10 | csv_read | 3 | 0.5807 | 0.5440–0.5826 | 0.5469 | 221.2 | ok |
| number_2Dlist-n10000-p20 | compute | 3 | 2.0246 | 2.0237–2.0629 | 2.0000 | 168.1 | ok |
| number_2Dlist-n10000-p40 | compute | 3 | 3.8234 | 3.8232–4.0293 | 3.8125 | 178.3 | ok |
| number_2Dlist-n10000-p5 | compute | 3 | 0.4872 | 0.4842–0.4947 | 0.4844 | 160.0 | ok |

定位证据：查找逐单元格读/写iloc并生成坐标；number_2Dlist逐值取Series.iloc；CSV检测对多个候选分隔符完整解析，预览显示head前也完整读取。查找使用内存表和轻量参数对象，未测真实高亮绘制。

建议及预期收益：在保留完整有效性检查前提下，按列/数组批处理查找和数字转换；复用同一导入操作内的检测/解析结果。

正确性/兼容风险：大小写/空白/缺失值匹配规则、原始样本顺序、只过滤完整有效行；CSV不能牺牲长整数/前导零/编码歧义与整文件行宽校验。

可复用实现/验证：现有CSV严格解析器、数字过滤工具和tests/test_csv_import.py；不另建泛化导入缓存框架。

### F10 P2：时序原始曲线、多表与宽表的绘制边界

位置：`code/time_series.py + code/time_series_dialog.py + code/txt_output.py`，`time_series_plot / TimeSeriesDialog.apply / add_table`，行90 / 137 / 110。入口：图形→时间序列图；报告连续小表/宽表。

数据/原始测量（每个场景ID对应raw/<ID>.json；全部单次值在G15-benchmark-results.csv）：
| 场景/原始JSON文件名 | 阶段 | 正式样本数 | 中位秒 | 最小–最大秒 | CPU中位秒 | 进程累计峰值MiB | 场景状态 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| report_gui-n100-p100 | tk_print_to_updated | 3 | 0.1365 | 0.1310–0.4303 | 0.1094 | 197.2 | ok |
| report_gui-n100-p100 | tk_last_page_to_updated | 3 | 0.0987 | 0.0930–0.1289 | 0.0938 | 197.2 | ok |
| report_gui-n100-p100 | gui_txt_save | 3 | 0.000992 | 0.000934–0.0018 | 0.000000 | 197.2 | ok |
| report_gui-n100-p100 | tk_clear_to_updated | 3 | 0.0229 | 0.0171–0.0304 | 0.000000 | 197.2 | ok |
| report_gui-n100-p7-c20 | tk_print_to_updated | 3 | 3.2968 | 3.1502–3.7812 | 1.4688 | 207.6 | ok |
| report_gui-n100-p7-c20 | tk_last_page_to_updated | 3 | 0.0011 | 0.0010–0.0018 | 0.000000 | 207.6 | ok |
| report_gui-n100-p7-c20 | gui_txt_save | 3 | 0.0021 | 0.0019–0.0023 | 0.000000 | 207.6 | ok |
| report_gui-n100-p7-c20 | tk_clear_to_updated | 3 | 0.8517 | 0.7774–1.0768 | 0.4375 | 207.6 | ok |
| report_gui-n100-p7 | tk_print_to_updated | 3 | 1.7273 | 1.3703–2.0740 | 0.8281 | 197.9 | ok |
| report_gui-n100-p7 | gui_txt_save | 3 | 0.000919 | 0.000918–0.0012 | 0.000000 | 197.9 | ok |
| report_gui-n100-p7 | tk_clear_to_updated | 3 | 0.6804 | 0.4520–0.6838 | 0.3125 | 197.9 | ok |
| report_gui-n1000-p7 | tk_print_to_updated | 3 | 0.0663 | 0.0456–0.4133 | 0.0156 | 197.1 | ok |
| report_gui-n1000-p7 | tk_last_page_to_updated | 3 | 0.0170 | 0.0156–0.0184 | 0.0156 | 197.1 | ok |
| report_gui-n1000-p7 | gui_txt_save | 3 | 0.0010 | 0.000909–0.0011 | 0.000000 | 197.1 | ok |
| report_gui-n1000-p7 | tk_clear_to_updated | 3 | 0.0204 | 0.0184–0.0270 | 0.000000 | 197.1 | ok |
| report_gui-n10000-p7 | tk_print_to_updated | 3 | 0.0980 | 0.0566–0.1162 | 0.0469 | 209.9 | ok |
| report_gui-n10000-p7 | tk_last_page_to_updated | 3 | 0.0214 | 0.0151–0.0371 | 0.000000 | 209.9 | ok |
| report_gui-n10000-p7 | gui_txt_save | 3 | 0.0017 | 0.0016–0.0021 | 0.000000 | 209.9 | ok |
| report_gui-n10000-p7 | tk_clear_to_updated | 3 | 0.0243 | 0.0173–0.0271 | 0.0156 | 209.9 | ok |
| report_gui-n50000-p7 | tk_print_to_updated | 3 | 0.0481 | 0.0465–0.0678 | 0.0312 | 264.1 | ok |
| report_gui-n50000-p7 | tk_last_page_to_updated | 3 | 0.0192 | 0.0185–0.0198 | 0.0156 | 264.1 | ok |
| report_gui-n50000-p7 | gui_txt_save | 3 | 0.0061 | 0.0060–0.0095 | 0.000000 | 264.1 | ok |
| report_gui-n50000-p7 | tk_clear_to_updated | 3 | 0.0265 | 0.0147–0.0287 | 0.000000 | 264.2 | ok |
| time_series-n1000-p3 | data_prepare | 3 | 0.0015 | 0.0013–0.0017 | 0.0156 | 104.1 | ok |
| time_series-n1000-p3 | plot_build_including_prepare | 3 | 0.0365 | 0.0362–0.0370 | 0.0312 | 104.1 | ok |
| time_series-n1000-p3 | agg_first_draw | 3 | 0.0931 | 0.0920–0.0975 | 0.0938 | 104.1 | ok |
| time_series-n1000-p3 | agg_redraw | 3 | 0.0838 | 0.0835–0.0866 | 0.0938 | 104.2 | ok |
| time_series-n10000-p3 | data_prepare | 3 | 0.0058 | 0.0052–0.0179 | 0.000000 | 138.8 | ok |
| time_series-n10000-p3 | plot_build_including_prepare | 3 | 0.0617 | 0.0448–0.1469 | 0.0625 | 138.8 | ok |
| time_series-n10000-p3 | agg_first_draw | 3 | 0.3545 | 0.3443–1.3069 | 0.3438 | 138.8 | ok |
| time_series-n10000-p3 | agg_redraw | 3 | 0.9955 | 0.3198–1.3617 | 0.9219 | 138.8 | ok |
| time_series-n100000-p3 | data_prepare | 3 | 0.0150 | 0.0123–0.0430 | 0.0156 | 250.1 | ok |
| time_series-n100000-p3 | plot_build_including_prepare | 3 | 0.0837 | 0.0757–0.1982 | 0.0781 | 250.1 | ok |
| time_series-n100000-p3 | agg_first_draw | 3 | 1.3779 | 1.3612–2.8348 | 1.3438 | 250.1 | ok |
| time_series-n100000-p3 | agg_redraw | 3 | 1.2943 | 1.2848–1.3211 | 1.2812 | 250.4 | ok |
| time_series-n50000-p3 | data_prepare | 3 | 0.0251 | 0.0082–0.0309 | 0.0156 | 208.2 | ok |
| time_series-n50000-p3 | plot_build_including_prepare | 3 | 0.1667 | 0.0536–0.1687 | 0.1562 | 208.2 | ok |
| time_series-n50000-p3 | agg_first_draw | 3 | 3.4436 | 2.9508–3.4749 | 3.1406 | 208.2 | ok |
| time_series-n50000-p3 | agg_redraw | 3 | 3.2948 | 3.2108–3.5242 | 3.1250 | 208.2 | ok |
| time_series_dialog-n1000-p3 | tk_dialog_apply_to_updated | 3 | 0.3475 | 0.3253–0.8339 | 0.2969 | 232.4 | ok |
| time_series_dialog-n10000-p3 | tk_dialog_apply_to_updated | 3 | 1.0345 | 0.9972–1.5509 | 0.9375 | 346.8 | ok |
| time_series_dialog-n50000-p3 | tk_dialog_apply_to_updated | 3 | 2.7926 | 2.5084–2.9214 | 2.4375 | 586.8 | ok |
| time_series_tk-n1000-p3 | tk_plot_to_updated | 3 | 0.1513 | 0.1473–0.1636 | 0.1562 | 143.9 | ok |
| time_series_tk-n1000-p3 | tk_redraw_to_updated | 3 | 0.1004 | 0.1001–0.1039 | 0.0938 | 143.9 | ok |
| time_series_tk-n10000-p3 | tk_plot_to_updated | 3 | 0.4703 | 0.4626–0.4706 | 0.4688 | 191.1 | ok |
| time_series_tk-n10000-p3 | tk_redraw_to_updated | 3 | 0.4092 | 0.4088–0.4102 | 0.4219 | 191.1 | ok |
| time_series_tk-n50000-p3 | tk_plot_to_updated | 3 | 1.2825 | 1.2658–1.4486 | 1.2656 | 265.8 | ok |
| time_series_tk-n50000-p3 | tk_redraw_to_updated | 3 | 1.4032 | 1.2717–1.4299 | 1.3281 | 265.8 | ok |

定位证据：G13实际Dialog有提前校验，再在time_series_plot准备一次；首次Agg绘制、Tk绘制和真实Dialog分别测量。100×7小表保持Label所以可能比大分页表更慢；20张表仍保留一部分Label预算。

建议及预期收益：仅在交互目标确有需要时定位布局/日期刻度/重复数据准备；保留所有原始点，不默认降采样、聚合或隐藏数据。

正确性/兼容风险：G13原始数值/重复时间/NaN断线/多轴布局和窗口替换契约；G14小表原外观及完整导出。

可复用实现/验证：现有唯一time_series_plot、公共plot_viewer、G13/G14测试。

输入特征补充：六模型compare_dist使用LogNormal(1,0.25)正值样本并断言六模型均成功；回归重复X约每水平5点。GRR为10零件×3操作者的完整交叉标签，n为总重复观测，Y为有限正态噪声；只是可复现计算负载，不将其方差分量解释为真实测量系统质量。

## 增长趋势（非复杂度证明）

| 路径 | 输入规模 | 规模倍数 | 中位秒 | 耗时倍数 |
| --- | --- | --- | --- | --- |
| linear_fit | 1000→10000 | 10.0x | 0.0685→4.5988 | 67.2x |
| binomial | 10000→50000 | 5.0x | 1.0530→5.3511 | 5.1x |
| df_combine | 1000→100000 | 100.0x | 0.0457→4.7710 | 104.5x |
| fit_norm | 1000→50000 | 50.0x | 0.0303→3.8215 | 126.2x |
| stat_table | 1000→100000 | 100.0x | 0.0303→12.4811 | 412.3x |
| spc_report | 100→50000 | 500.0x | 0.0037→4.5603 | 1245.0x |

增长比受本机频率/调度、数据类型、分组结构、内存分配和后端版本影响。线性回归重复X约为每水平5点；ANOVA的n是总观测，p是组数；multi_var的n是每组观测（3组）；calculate_d3的n是子组大小，绝不是总行数。不能把跨场景增长比直接当渐进复杂度证明。

## GUI、绘图与内存的解释边界

报告Tk场景从对已有映射结果窗口调用Minijmp.print开始，到Tk.update完成；表格场景从构造MTable/show/显式redraw到update完成，另测redrawVisible、含statusbar的redraw及滚动。窗口固定尺寸，实际创建Windows Tk控件。Tk时间不是屏幕物理呈现/人工鼠标手感，也没有测其它DPI/主题。

Matplotlib Agg是离屏渲染。time_series_tk使用真实plot_viewer/FigureCanvasTkAgg；time_series_dialog直接构造真实TimeSeriesDialog并调用apply，包含提前校验、窗口替换、工具栏和draw_idle经update完成。尚未测完整Minijmp应用启动、图形历史pickle保存和全部菜单交互。

两版multi_fit分别测了统计+Artist创建、首次Agg绘制、Agg重绘。当前版预建8×7英寸容器/主轴，旧版内部subplots使用默认尺寸；这不是严格相同布局的A/B实验，不能将两版差值当作算法优化收益。两版独立实测满足副本覆盖；旧版不冒充当前用户瓶颈。

真实vendor PlotViewer分别尝试create/replot→plotCurrent→plot2D，当前Matplotlib版本已无cm.get_cmap，旧_doplot抛AttributeError后被plot2D吞掉；曲线存在断言因此失败。三种规模均未取得正式有效绘图样本；CSV将该返回但空图的阶段标为invalid_output。当前plots.plot_viewer的成功不能代表此旧类；未加兼容补丁以凑性能数字。

连续报告clear会检查表格列表已清空；真实GUI/绘图都显式close/destroy。进程生命周期内存峰值不证明长期内存泄漏或其不存在；没有做数小时运行/无限历史图保留的泄漏实验。

## 无需优先优化与未验证候选

当前已测描述统计、单值CPK、x_mR以及固定窗口下MTable可见区域刷新表现相对可接受；不是承诺任意dtype/任意列数或全部业务动作都快。单因素逐对检验在测试的5/20/50组规模需按实测分级，不因有两层循环就列P1。

| 场景/原始JSON文件名 | 阶段 | 正式样本数 | 中位秒 | 最小–最大秒 | CPU中位秒 | 进程累计峰值MiB | 场景状态 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| calculate_d3-n10-trial1 | cold_integral | 1 | 1.8733 | 1.8733–1.8733 | 1.8281 | 154.7 | ok |
| calculate_d3-n10-trial1 | warm_cached_integral | 3 | 0.000006 | 0.000004–0.000007 | 0.000000 | 154.7 | ok |
| calculate_d3-n10-trial2 | cold_integral | 1 | 1.8805 | 1.8805–1.8805 | 1.8438 | 154.2 | ok |
| calculate_d3-n10-trial2 | warm_cached_integral | 3 | 0.000003 | 0.000003–0.000004 | 0.000000 | 154.3 | ok |
| calculate_d3-n10-trial3 | cold_integral | 1 | 1.7217 | 1.7217–1.7217 | 1.6875 | 154.8 | ok |
| calculate_d3-n10-trial3 | warm_cached_integral | 3 | 0.000004 | 0.000003–0.000004 | 0.000000 | 154.8 | ok |
| calculate_d3-n5-trial1 | cold_integral | 1 | 1.6254 | 1.6254–1.6254 | 1.6250 | 154.6 | ok |
| calculate_d3-n5-trial1 | warm_cached_integral | 3 | 0.000006 | 0.000004–0.000006 | 0.000000 | 154.7 | ok |
| calculate_d3-n5-trial2 | cold_integral | 1 | 1.5543 | 1.5543–1.5543 | 1.5469 | 154.7 | ok |
| calculate_d3-n5-trial2 | warm_cached_integral | 3 | 0.000004 | 0.000003–0.000035 | 0.000000 | 154.8 | ok |
| calculate_d3-n5-trial3 | cold_integral | 1 | 1.6435 | 1.6435–1.6435 | 1.6250 | 155.1 | ok |
| calculate_d3-n5-trial3 | warm_cached_integral | 3 | 0.000003 | 0.000003–0.000004 | 0.000000 | 155.1 | ok |
| cpk-n1000-p1 | compute | 3 | 0.0111 | 0.0099–0.0119 | 0.0156 | 154.2 | ok |
| cpk-n10000-p1 | compute | 3 | 0.0213 | 0.0197–0.0224 | 0.0156 | 155.7 | ok |
| cpk-n100000-p1 | compute | 3 | 0.1149 | 0.1104–0.1191 | 0.1094 | 163.6 | ok |
| cpk-n50000-p1 | compute | 3 | 0.0599 | 0.0595–0.0642 | 0.0469 | 159.8 | ok |
| describe-n1000-p1 | compute | 3 | 0.0024 | 0.0020–0.0024 | 0.000000 | 154.8 | ok |
| describe-n10000-p1 | compute | 3 | 0.0202 | 0.0181–0.0226 | 0.0156 | 155.7 | ok |
| describe-n100000-p1 | compute | 3 | 0.1720 | 0.1711–0.1730 | 0.1719 | 168.0 | ok |
| describe-n50000-p1 | compute | 3 | 0.0846 | 0.0825–0.0872 | 0.0781 | 161.8 | ok |
| pi_decode-n1000-p20 | pi_json_decode | 3 | 0.0019 | 0.0019–0.0020 | 0.000000 | 95.5 | ok |
| pi_decode-n1000-p20 | pi_frame_validate | 3 | 0.0022 | 0.0021–0.0023 | 0.000000 | 95.5 | ok |
| pi_decode-n10000-p20 | pi_json_decode | 3 | 0.0201 | 0.0196–0.0211 | 0.0312 | 124.4 | ok |
| pi_decode-n10000-p20 | pi_frame_validate | 3 | 0.0118 | 0.0113–0.0121 | 0.0156 | 124.4 | ok |
| pi_decode-n100000-p20 | pi_json_decode | 3 | 0.2472 | 0.2442–0.2485 | 0.2344 | 408.0 | ok |
| pi_decode-n100000-p20 | pi_frame_validate | 3 | 0.1185 | 0.1135–0.1298 | 0.1094 | 408.0 | ok |
| pi_decode-n50000-p20 | pi_json_decode | 3 | 0.0933 | 0.0932–0.0959 | 0.0938 | 250.6 | ok |
| pi_decode-n50000-p20 | pi_frame_validate | 3 | 0.0554 | 0.0537–0.0658 | 0.0625 | 250.7 | ok |
| table_gui-n1000-p20 | tk_table_first_to_updated | 3 | 0.1062 | 0.0991–0.1091 | 0.0625 | 166.2 | ok |
| table_gui-n1000-p20 | tk_table_redraw_to_updated | 3 | 0.0438 | 0.0405–0.0575 | 0.0312 | 166.3 | ok |
| table_gui-n1000-p20 | tk_table_full_redraw_to_updated | 3 | 0.0428 | 0.0428–0.0553 | 0.0469 | 166.3 | ok |
| table_gui-n1000-p20 | tk_table_scroll_to_updated | 3 | 0.0515 | 0.0428–0.0584 | 0.0312 | 166.3 | ok |
| table_gui-n10000-p20 | tk_table_first_to_updated | 3 | 0.0989 | 0.0954–0.1170 | 0.0625 | 168.7 | ok |
| table_gui-n10000-p20 | tk_table_redraw_to_updated | 3 | 0.0435 | 0.0417–0.0454 | 0.0469 | 169.1 | ok |
| table_gui-n10000-p20 | tk_table_full_redraw_to_updated | 3 | 0.0409 | 0.0399–0.0423 | 0.0469 | 169.1 | ok |
| table_gui-n10000-p20 | tk_table_scroll_to_updated | 3 | 0.0542 | 0.0500–0.0542 | 0.0625 | 169.1 | ok |
| table_gui-n100000-p20 | tk_table_first_to_updated | 3 | 0.6316 | 0.0987–0.6346 | 0.0781 | 200.4 | ok |
| table_gui-n100000-p20 | tk_table_redraw_to_updated | 3 | 0.0532 | 0.0482–0.0644 | 0.0625 | 204.0 | ok |
| table_gui-n100000-p20 | tk_table_full_redraw_to_updated | 3 | 0.0876 | 0.0450–0.0990 | 0.0625 | 204.2 | ok |
| table_gui-n100000-p20 | tk_table_scroll_to_updated | 3 | 0.0608 | 0.0594–0.1397 | 0.0469 | 204.2 | ok |
| table_gui-n50000-p20 | tk_table_first_to_updated | 3 | 0.1312 | 0.1179–0.1318 | 0.0625 | 182.8 | ok |
| table_gui-n50000-p20 | tk_table_redraw_to_updated | 3 | 0.0526 | 0.0430–0.0783 | 0.0625 | 184.7 | ok |
| table_gui-n50000-p20 | tk_table_full_redraw_to_updated | 3 | 0.0469 | 0.0458–0.0508 | 0.0469 | 185.0 | ok |
| table_gui-n50000-p20 | tk_table_scroll_to_updated | 3 | 0.0680 | 0.0642–0.1027 | 0.0312 | 185.0 | ok |
| ti_norm-n1000-p1 | compute | 3 | 0.3863 | 0.3745–0.5761 | 0.3750 | 155.4 | ok |
| ti_norm-n10000-p1 | compute | 3 | 0.3657 | 0.3552–0.3765 | 0.3438 | 156.6 | ok |
| ti_norm-n50000-p1 | compute | 3 | 0.3847 | 0.3662–0.3977 | 0.3750 | 157.4 | ok |
| x_mR-n1000-p1 | compute | 3 | 0.0012 | 0.0010–0.0013 | 0.000000 | 154.8 | ok |
| x_mR-n10000-p1 | compute | 3 | 0.0084 | 0.0080–0.0085 | 0.000000 | 156.1 | ok |
| x_mR-n100000-p1 | compute | 3 | 0.0737 | 0.0712–0.0752 | 0.0625 | 166.4 | ok |
| x_mR-n50000-p1 | compute | 3 | 0.0390 | 0.0381–0.0392 | 0.0312 | 161.4 | ok |

calculate_d3已经有lru_cache，不能再把“缺少缓存”列作待开发功能。冷调用独立进程合并统计如下；暖值是同规模3个进程共9个命中样本，微秒级仅作已命中缓存的证据，不承诺微秒精度。

| 子组大小 | 独立冷样本 | 冷中位秒 | 冷最小–最大秒 | 暖样本 | 暖中位秒 |
| --- | --- | --- | --- | --- | --- |
| 5 | 3 | 1.6254 | 1.5543–1.6435 | 9 | 0.000004 |
| 10 | 3 | 1.8733 | 1.7217–1.8805 | 9 | 0.000004 |

以下仅为P3/未完成验证，不宣称实测瓶颈：密集蜂群、分组线图默认bootstrap、正交拟合重复正态检验、Residual端到端重复OLS、undo全表快照、PI结果Treeview/主表回填、极端长字符串/极宽表、任意多Y轴、无限报告/历史图常驻。每文件具体入口/行号/理由见CSV和static-statistics/static-ui附件。

不可达/历史：p_simulation只在注释中调用，fit_jsu不在当前六模型列表，p_likelihood_ratio没有当前GUI调用，multi_fit_orig保留旧公开入口；tests/fixtures/g14_before是历史快照。core_orig/data_orig通过MRO仍在当前路径，完全不同于这些快照。

## 失败、资源限制与不完整样本

| 场景 | 状态 | 最后阶段 | 进程时限秒 | 已完成阶段样本 | 具体原因 |
| --- | --- | --- | --- | --- | --- |
| binomial-n1000-p1 | error | compute | 45 | 0 |     print(h, t, s, threshold, n, p, x)     ^^^^^ NameError: cannot access free variable 'print' where it is not associated with a value in enclosing scope |
| find_text-n1000-p5 | error | compute | 50 | 0 |   File "C:\Users\shaoy\Documents\Minijmp\.venv\Lib\site-packages\pandas\core\arrays\string_.py", line 838, in _maybe_convert_setitem_value     raise TypeError( TypeError: Invalid value 'False' for dtype 'str'. Value should be a string or missing value, got 'bool' instead. |
| find_text-n10000-p5 | error | compute | 50 | 0 |   File "C:\Users\shaoy\Documents\Minijmp\.venv\Lib\site-packages\pandas\core\arrays\string_.py", line 838, in _maybe_convert_setitem_value     raise TypeError( TypeError: Invalid value 'False' for dtype 'str'. Value should be a string or missing value, got 'bool' instead. |
| find_text-n50000-p5 | error | compute | 50 | 0 |   File "C:\Users\shaoy\Documents\Minijmp\.venv\Lib\site-packages\pandas\core\arrays\string_.py", line 838, in _maybe_convert_setitem_value     raise TypeError( TypeError: Invalid value 'False' for dtype 'str'. Value should be a string or missing value, got 'bool' instead. |
| grr-n30000-p10 | timeout | compute | 70 | 3 | 达到整进程组时限，未完成阶段不推算。 |
| hoeffding-n10000-p1 | timeout | compute | 35 | 0 | 达到整进程组时限，未完成阶段不推算。 |
| matrix_hoeffding-n1000-p10 | timeout | compute | 45 | 0 | 达到整进程组时限，未完成阶段不推算。 |
| multi_fit-n1000-p40 | timeout | agg_first_draw | 70 | 4 | 达到整进程组时限，未完成阶段不推算。 |
| multi_fit_orig-n1000-p40 | timeout | matrix_and_artists | 70 | 3 | 达到整进程组时限，未完成阶段不推算。 |
| multi_var-n3000-p3 | timeout | compute | 50 | 0 | 达到整进程组时限，未完成阶段不推算。 |
| prop_test_1sample-n1000-p1 | error | compute | 45 | 0 |     print(h, t, s, threshold, n, p, x)     ^^^^^ NameError: cannot access free variable 'print' where it is not associated with a value in enclosing scope |
| prop_test_1sample-n50000-p1 | timeout | compute | 45 | 4 | 达到整进程组时限，未完成阶段不推算。3次正式compute均完成；中止发生在后续profile，正式计算数据仍有效。 |
| vendor_plot-n1000-p3 | error | tk_vendor_replot_to_updated | 45 | 2 |     assert len(viewer.ax.lines)==p and not state.get('callback_errors')            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ AssertionError |
| vendor_plot-n10000-p3 | error | tk_vendor_replot_to_updated | 45 | 2 |     assert len(viewer.ax.lines)==p and not state.get('callback_errors')            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ AssertionError |
| vendor_plot-n50000-p3 | error | tk_vendor_replot_to_updated | 45 | 2 |     assert len(viewer.ax.lines)==p and not state.get('callback_errors')            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ AssertionError |

二项中心点N=1000、p=.5、x=500在acc_p末端触发NameError，单比例同样继承此异常；这是既有功能边界，未修改。正常非中心输入x=.49N另行完成；不能将异常短路当性能更好。

文本查找在pandas 3.0.6下把False写入astype(str)得到的字符串列，触发TypeError（Invalid value False for dtype str）；1000/10000/50000行均未完成。vendor绘图在Matplotlib 3.11.2下因cm.get_cmap不存在而失败。这两项是实际兼容阻碍，本轮只记录，不修改环境或业务代码；不能把其失败耗时列作性能瓶颈或收益。

preliminary保留被正式结果替换的试运行：ANOVA最初flat输入违背groups+labels契约；复用同一Frame时Table.show依赖尺寸事件，正式测量补明确redraw；两次线性回归试运行发生重叠；连续表试运行共用同一对象，正式改为20张独立StatTable。它们不计入最终CSV，也不归为产品问题。两项预算补测只增加一次有界重试，40变量/超大Hoeffding不无限重跑。

## 建议G16/G17任务边界

**G16：计算和数据准备。** 优先F01、F02、F11，再按实际大样本需求选择F04/F05/F06/F08/F09。每次限一个明确内核及其消费者，保留固定输入数值结果、退化边界、报告协议。先减少重复扫描/标量派发，单独处理已记录的查找/旧绘图兼容阻碍和二项中心点既有异常；不顺带升级依赖或改统计定义。

**G17：报告与图形交互。** 在G16之后评估F03/F07/F10：复用相关统计、只创建需要的轴、定位完整ASCII和Excel工作簿成本。已有分页/滚动预算继续复用；惰性字符串、流式Excel、取消任务或背景工作只在具体交互验收需要时实施，分别验证TXT/复制/精度/导出/关闭生命周期。

所有收益都是待验证方向；本轮没有实现优化、没有给出未实施方案的加速承诺。

## 全模块风险矩阵

完整函数、所有静态候选、调用入口、归属、是否动态及理由在G15-module-inventory.csv；下表逐文件对账，静态候选只表示待验证。

| 文件（每文件一行） | 类别 | 静态候选/低风险理由摘要 | 审查/实测状态 |
| --- | --- | --- | --- |
| start.py | 应用启动器 | 完整GUI启动包含日志/配置副作用；未独立测启动时间 | 静态审查完成；完整启动未测 |
| code/GRR.py | 量具R&R计算 | Auto 路径2次完整模型，条件成立时再1次加法模型 | 动态分阶段基准 {"ok":2,"timeout":1} |
| code/MiniJMP.py | 项目当前主界面 | 启动加载配置、日志和各统计绘图模块；完整应用构造有文件系统副作用，不适合作为只读微基准最小构造器。 | 动态分阶段基准 {"ok":9} |
| code/Residual.py | 线性拟合残差诊断绘图 | 上游linear_fit O(N²)；resid_test可能再次linear_fit O(N²) | 静态审查完成；未独立动态测量 |
| code/anova_dialog.py | 项目当前ANOVA（含保留旧类） | 堆叠/分组/数值转换/ANOVA/可选组间t，再hash数据建CI字典和interval_plot，同步多次遍历候选。 | 静态审查完成；未独立动态测量 |
| code/basic_dialogs.py | 项目当前描述/分布/正态性入口 | 全列number_list后按选择compare_dist；拟合耗时需另实测。 | 静态审查完成；未独立动态测量 |
| code/binomial.py | 离散分布计算/绘图 | O(n) 次标量 PMF；保留 O(n) 概率列表 | 动态分阶段基准 {"error":1,"ok":5} |
| code/blakerCI.py | 精确比例检验 | O(log(1/tol)) 次二项 CDF/SF；默认 maxiter=10000 为保护上限 | 动态分阶段基准 {"error":1,"ok":4,"timeout":1} |
| code/bonett.py | 单样本方差检验 | O(n log n) 排序、O(n) 复制 | 静态审查完成；未独立动态测量 |
| code/chart_style.py | 共享绘图样式 | 最多 7 次字体名列表查询，导入阶段 | 静态审查完成；未独立动态测量 |
| code/chi2_dialog.py | 项目当前卡方入口 | 二维数值转换/计数后chi_square同步。 | 静态审查完成；未独立动态测量 |
| code/chi_sq.py | 卡方/方差检验 | O(Σ m_g²) | 动态分阶段基准 {"ok":2,"timeout":1} |
| code/cont_plot.py | 连续/离散分布路由与概率图 | 连续分布固定 200 点 PDF 与少量 CDF/PPF | 静态审查完成；未独立动态测量 |
| code/control_chart.py | SPC 统计/绘图/报告 | O(N*mr) 时间与 O(N) 数据；默认 mr=2 则线性 | 动态分阶段基准 {"ok":11} |
| code/cpk.py | 过程能力计算 | 冷调用含双重积分 Q_outer*Q_inner；命中按子组大小缓存 | 动态分阶段基准 {"ok":4} |
| code/cpk_plot.py | 过程能力/残差直方图 | 继承 cpk + O(N) 双直方图；曲线100点 | 静态审查完成；未独立动态测量 |
| code/ctrl_chart_const.py | SPC 固定查表 | 固定24行×11列构建和转换 | 静态审查完成；未独立动态测量 |
| code/ctrlchart_dialog.py | 项目当前控制图入口 | 全列数值/标签遍历后get_axs；图窗成本需分离x_plot。 | 静态审查完成；未独立动态测量 |
| code/describe.py | 描述性统计/报告 | O(N log N) 多次排序+O(N)多遍扫描 | 动态分阶段基准 {"ok":4} |
| code/df_combine.py | 边界：表格数据合并，转交 core UI | O(output_height*output_width + cells(df1)+cells(df2)) 时间/内存候选 | 动态分阶段基准 {"ok":4} |
| code/dialog.py | 项目共享对话框与查找覆盖（激活） | 全表astype字符串+copy，嵌套iloc逐格比较，再第二次全格坐标收集；CPU/内存高优先。 | 动态分阶段基准 {"error":3} |
| code/dist_fit.py | 分布拟合/比较 | O(N) 次标量 rv.pdf 和 log | 动态分阶段基准 {"ok":6} |
| code/dist_plot_dialog.py | 项目当前理论分布图 | 参数概率计算/可选图窗，旧图快照另列。 | 静态审查完成；未独立动态测量 |
| code/fit_dialog.py | 项目当前回归/相关入口 | number_2lists、图窗、fit_plot同一回调，拟合/区间选项影响成本。 | 动态分阶段基准 {"ok":11,"timeout":1} |
| code/freeze.py | 历史vendor打包脚本（非运行入口） | 顶层Executable/setup且排除当前统计依赖；本任务不运行构建或安装cx_Freeze。 | 静态审查完成；未独立动态测量 |
| code/grr_plot.py | GRR 分面绘图 | O(O*N) 布尔筛选候选+O个Axes/分类绘图 | 静态审查完成；未独立动态测量 |
| code/help_link.py | 项目离线帮助/旧映射辅助 | 每个新Dialog读整个help.json，无缓存。 | 静态审查完成；未独立动态测量 |
| code/linear_fit.py | 普通线性拟合 | O(N²)候选（不依赖是否显示失拟表） | 动态分阶段基准 {"ok":3} |
| code/linear_plot.py | 回归/相关矩阵绘图 | O(K²*N)数值处理；K²结果及表构造 | 动态分阶段基准 {"ok":8,"timeout":2} |
| code/modified_app.py | 项目当前应用中间层/关于界面 | 转发help_window读小JSON，已在help_link记录。 | 静态审查完成；未独立动态测量 |
| code/modified_table.py | 项目当前表格覆盖层 | 空实现；当前业务MTable不运行基类自动列宽扫描。 | 动态分阶段基准 {"ok":4} |
| code/nonpara_cor.py | 秩相关/独立性检验 | 数组复制O(N)+后端秩/排序；常见候选O(N log N)，具体依赖后端 | 动态分阶段基准 {"ok":14,"timeout":2} |
| code/one_way_ANOVA.py | 单因素ANOVA/均值逐对比较 | O(N)+K次汇总t区间，不是重复全样本平方扫描 | 动态分阶段基准 {"ok":9} |
| code/ortho_fit.py | 正交回归 | O(N)数组/列表运算+norm_test | 静态审查完成；未独立动态测量 |
| code/pi_import.py | 项目PI模态导入（I/O后台、UI主线程） | 默认PI路径仅文本，grab_set模态不等于同步远程IO，构造本身不连PI。 | 静态审查完成；真实PI与结果回主线程路径未测 |
| code/pi_reader.py | 项目PI协议适配（纯处理与外部查询分离） | worker中subprocess捕获完整输出，再json.loads/DataFrame解析，峰值内存候选；父进程RSS不含子进程工作集。 | 动态分阶段基准 {"ok":4} |
| code/plots.py | 边界：Tk绘图窗口，转交 core UI | 窗口/Canvas/事件处理器生命周期，非统计规模算法 | 动态分阶段基准 {"ok":6} |
| code/poisson.py | 泊松分布概率图 | 固定次数CDF/PPF | 静态审查完成；未独立动态测量 |
| code/proportion_test.py | 单/双比例检验 | O(N)多路标量枚举+Blaker嵌套二分 | 动态分阶段基准 {"error":1,"ok":13,"timeout":1} |
| code/qc_dialog.py | 项目当前质量分析 | 逐行清洗后grr_master与可选grr_plot，模型/绘图分阶段候选。 | 静态审查完成；未独立动态测量 |
| code/sample_test_dialog.py | 项目当前单/双样本检验 | 原始模式number_list，汇总模式跳过；t_test_1sample同步。 | 静态审查完成；未独立动态测量 |
| code/sb_box_dialog.py | 项目当前箱线图 | 堆叠/全列转换后single_boxplot，可选点叠加影响artist数。 | 静态审查完成；未独立动态测量 |
| code/sb_boxplot.py | 箱线/蜂群绘图 | 普通箱图后端分组/排序；蜂群是密度敏感超线性候选 | 静态审查完成；未独立动态测量 |
| code/sb_hist_dialog.py | 项目当前直方图 | 可选compare_dist先拟合，再全列工作表和histo_n_fit，重复清洗候选。 | 静态审查完成；未独立动态测量 |
| code/sb_histo.py | 单/分组/二维直方图 | O(N)预处理/两次分箱；rv曲线100点；bins='auto'另受范围/分箱数影响 | 静态审查完成；未独立动态测量 |
| code/sb_misc.py | 区间/计数/线图/点图 | 默认分组均值+95%CI：重复x时1000次bootstrap，候选O(B*N)+分组排序 | 静态审查完成；未独立动态测量 |
| code/sb_misc_dialog.py | 项目当前计数/线/点图 | stack或复制完整工作表后count_plot。 | 静态审查完成；未独立动态测量 |
| code/sb_palette_dialog.py | 项目保留独立调色板示例（未见当前引用） | 固定6色，与表大小无关。 | 静态审查完成；未独立动态测量 |
| code/sbplot_dialog.py | 项目当前Seaborn共享对话框 | 每次同步apply，完成后才self_to_top，无后台绘图。 | 静态审查完成；未独立动态测量 |
| code/stat_table.py | 统计报告公共模型/分页/导出 | 完整values/display与ASCII物化，构建仍随总单元格数增长。 | 动态分阶段基准 {"ok":13} |
| code/t_test.py | 均值t/Z/配对检验 | 原始数据O(N)；汇总数据为固定次数分布函数 | 静态审查完成；未独立动态测量 |
| code/ti.py | 正态统计容差区间 | 约27次二分 × 自适应积分采样次数 × ncx2.ppf/chi2.cdf | 动态分阶段基准 {"ok":3} |
| code/time_series.py | 时间序列数据准备/原生多轴图 | 每列object数组/校验，时间稳定排序；数据准备独立测量。 | 动态分阶段基准 {"ok":10} |
| code/time_series_dialog.py | 项目当前时间序列入口（并行新增文件） | 提前prepare校验，time_series_plot内部再prepare（已核对time_series.py）；同步转换/构图后draw_idle只排队。 | 动态分阶段基准 {"ok":3} |
| code/two_way_anova.py | 双因素III型ANOVA | N行、交互模型约A*B列的稠密设计；线性代数成本随列数扩大 | 动态分阶段基准 {"ok":3} |
| code/txt_output.py | 结果窗口文本/表格/保存 | 普通Text插入同步；大批文字输出应包含Tk.update。 | 动态分阶段基准 {"ok":9} |
| code/utilities.py | 统计/分组/清洗/报告共享工具 | 双层自适应积分Q_outer*Q_inner，按n LRU缓存 | 动态分阶段基准 {"ok":9} |
| code/pandastable_local/app.py | 第三方vendor应用基类（部分继承，原启动非主路径） | 当前主菜单getCurrentTable/getattr直接同步调用，无线程封装。 | 静态审查完成；未独立动态测量 |
| code/pandastable_local/config.py | 第三方vendor本地配置（激活） | import时user_config缺失即makedirs；默认在仓库user_config/default.conf，非log/default.conf。 | 静态审查完成；未独立动态测量 |
| code/pandastable_local/core.py | 第三方vendor本地适配层（激活） | 仅import也有潜在写入：log缺失时os.mkdir。 | 动态分阶段基准 {"ok":4} |
| code/pandastable_local/core_orig.py | 第三方vendor基类（当前继承激活，局部被覆盖） | loadPrefs在kwargs赋值前执行；传rows/cols/prefs或任意config参数不能关闭配置加载。 | 动态分阶段基准 {"ok":4} |
| code/pandastable_local/csv_import.py | vendor目录内项目本地CSV实现（激活） | 整文件读取/解码，4种delimiter各完整read_records，再最终read_records；表头判断再扫单元格。 | 动态分阶段基准 {"ok":4} |
| code/pandastable_local/data.py | 第三方vendor模型本地覆盖（激活） | 按列名drop(inplace=True)，可能触底层重排/分配，需按dtype/规模测。 | 动态分阶段基准 {"ok":4} |
| code/pandastable_local/data_orig.py | 第三方vendor模型基类（当前继承激活） | 传入df直接引用，无额外copy；默认仅20x5空表。 | 动态分阶段基准 {"ok":4} |
| code/pandastable_local/dialogs.py | 第三方vendor共享对话框/查询（局部覆盖） | 为显示head(10)先完整self.read，每次更改格式重读；确认导入还再读。 | 静态审查完成；未独立动态测量 |
| code/pandastable_local/handlers.py | 第三方vendor图交互（两绘图器激活） | 选中artist更新整图canvas.draw，非blit，高点数图交互候选。 | 静态审查完成；未独立动态测量 |
| code/pandastable_local/headers.py | 第三方vendor本地修改header（激活） | 文本仅可见列，wrap时扫描全部列名求最长；逐可见列Tk测量/重建文字线条。 | 动态分阶段基准 {"ok":4} |
| code/pandastable_local/images.py | 第三方vendor嵌入图标资源（激活） | 每次新PhotoImage，仅固定构造成本；主Minijmp图标用icon.png。 | 静态审查完成；未独立动态测量 |
| code/pandastable_local/plotting.py | 第三方vendor本地绘图（旧向导仍激活） | 一次构造MPLBaseOptions/MPL3DOptions/AnnotationOptions，重复枚举系统字体，冷启动候选。 | 动态分阶段基准 {"error":3,"ok":3} |
| code/pandastable_local/plugin.py | 第三方vendor插件框架（导入但默认未初始化） | 动态import执行插件顶层代码，非当前默认表格基准路径。 | 静态审查完成；未独立动态测量 |
| code/pandastable_local/stats.py | 第三方vendor旧回归界面（非当前主统计菜单） | mod.fit/summary同步，具体后端复杂度未在此证明。 | 静态审查完成；未独立动态测量 |
| code/pandastable_local/util.py | 第三方vendor共享工具（激活） | 每个可见格/列标题Tk文本create/bbox/delete；SCRATCH为进程全局Canvas，推荐独立进程避免跨Tk根生命周期。 | 静态审查完成；未独立动态测量 |
| docs/conf.py | 文档配置 | AST候选0处；独立验收脚本 | 静态检查通过；无需单独基准 |
| docs/g11-evidence/render.py | 验收证据生成脚本 | AST候选1处；独立验收脚本 | 静态检查通过；无需单独基准 |
| docs/g12-evidence/render.py | 验收证据生成脚本 | AST候选0处；独立验收脚本 | 静态检查通过；无需单独基准 |
| docs/g13-evidence/visual_check.py | 验收证据生成脚本 | AST候选1处；独立验收脚本 | 静态检查通过；无需单独基准 |
| docs/g14-evidence/render.py | 验收证据生成脚本 | AST候选3处；独立验收脚本 | 静态检查通过；无需单独基准 |
| tests/fixtures/g14_before/MiniJMP.py | 历史G14修改前快照 | AST候选0处；不作为当前瓶颈 | 历史实现静态记录；不执行 |
| tests/fixtures/g14_before/stat_table.py | 历史G14修改前快照 | AST候选10处；不作为当前瓶颈 | 历史实现静态记录；不执行 |
| tests/fixtures/g14_before/txt_output.py | 历史G14修改前快照 | AST候选0处；不作为当前瓶颈 | 历史实现静态记录；不执行 |
| docs/g7-evidence/render.py | 验收证据生成脚本 | AST候选0处；独立验收脚本 | 静态检查通过；无需单独基准 |
| docs/g8-evidence/render.py | 验收证据生成脚本 | AST候选3处；独立验收脚本 | 静态检查通过；无需单独基准 |
| tests/conftest.py | 测试/fixture辅助 | AST静态候选0处；仅测试执行，非当前用户瓶颈 | 静态检查通过；无需独立性能基准 |
| tests/test_csv_import.py | 测试/fixture辅助 | AST静态候选0处；仅测试执行，非当前用户瓶颈 | 静态检查通过；无需独立性能基准 |
| tests/test_dialog_translation.py | 测试/fixture辅助 | AST静态候选27处；仅测试执行，非当前用户瓶颈 | 静态检查通过；无需独立性能基准 |
| tests/test_file_io.py | 测试/fixture辅助 | AST静态候选0处；仅测试执行，非当前用户瓶颈 | 静态检查通过；无需独立性能基准 |
| tests/test_g10_tables.py | 测试/fixture辅助 | AST静态候选10处；仅测试执行，非当前用户瓶颈 | 静态检查通过；无需独立性能基准 |
| tests/test_g11_quality_tables.py | 测试/fixture辅助 | AST静态候选11处；仅测试执行，非当前用户瓶颈 | 静态检查通过；无需独立性能基准 |
| tests/test_g12_inventory.py | 测试/fixture辅助 | AST静态候选29处；仅测试执行，非当前用户瓶颈 | 静态检查通过；无需独立性能基准 |
| tests/test_g12_tables.py | 测试/fixture辅助 | AST静态候选7处；仅测试执行，非当前用户瓶颈 | 静态检查通过；无需独立性能基准 |
| tests/test_g13_time_series.py | 测试/fixture辅助 | AST静态候选6处；仅测试执行，非当前用户瓶颈 | 静态检查通过；无需独立性能基准 |
| tests/test_g14_rendering.py | 测试/fixture辅助 | AST静态候选2处；仅测试执行，非当前用户瓶颈 | 静态检查通过；无需独立性能基准 |
| tests/test_g1_debug_output.py | 测试/fixture辅助 | AST静态候选0处；仅测试执行，非当前用户瓶颈 | 静态检查通过；无需独立性能基准 |
| tests/test_g1_statistics_output.py | 测试/fixture辅助 | AST静态候选4处；仅测试执行，非当前用户瓶颈 | 静态检查通过；无需独立性能基准 |
| tests/test_g1_text_output.py | 测试/fixture辅助 | AST静态候选1处；仅测试执行，非当前用户瓶颈 | 静态检查通过；无需独立性能基准 |
| tests/test_g2_basic_reports.py | 测试/fixture辅助 | AST静态候选8处；仅测试执行，非当前用户瓶颈 | 静态检查通过；无需独立性能基准 |
| tests/test_g2_hypothesis_reports.py | 测试/fixture辅助 | AST静态候选9处；仅测试执行，非当前用户瓶颈 | 静态检查通过；无需独立性能基准 |
| tests/test_g3_anova_reports.py | 测试/fixture辅助 | AST静态候选12处；仅测试执行，非当前用户瓶颈 | 静态检查通过；无需独立性能基准 |
| tests/test_g3_chi_square_reports.py | 测试/fixture辅助 | AST静态候选8处；仅测试执行，非当前用户瓶颈 | 静态检查通过；无需独立性能基准 |
| tests/test_g3_computation_contracts.py | 测试/fixture辅助 | AST静态候选3处；仅测试执行，非当前用户瓶颈 | 静态检查通过；无需独立性能基准 |
| tests/test_g3_distribution_reports.py | 测试/fixture辅助 | AST静态候选10处；仅测试执行，非当前用户瓶颈 | 静态检查通过；无需独立性能基准 |
| tests/test_g3_regression_reports.py | 测试/fixture辅助 | AST静态候选4处；仅测试执行，非当前用户瓶颈 | 静态检查通过；无需独立性能基准 |
| tests/test_g3_report_display.py | 测试/fixture辅助 | AST静态候选3处；仅测试执行，非当前用户瓶颈 | 静态检查通过；无需独立性能基准 |
| tests/test_g4_quality_reports.py | 测试/fixture辅助 | AST静态候选11处；仅测试执行，非当前用户瓶颈 | 静态检查通过；无需独立性能基准 |
| tests/test_g5_spc_reports.py | 测试/fixture辅助 | AST静态候选6处；仅测试执行，非当前用户瓶颈 | 静态检查通过；无需独立性能基准 |
| tests/test_g6_chart_presentation.py | 测试/fixture辅助 | AST静态候选4处；仅测试执行，非当前用户瓶颈 | 静态检查通过；无需独立性能基准 |
| tests/test_g6_quality_charts.py | 测试/fixture辅助 | AST静态候选9处；仅测试执行，非当前用户瓶颈 | 静态检查通过；无需独立性能基准 |
| tests/test_g7_tables.py | 测试/fixture辅助 | AST静态候选4处；仅测试执行，非当前用户瓶颈 | 静态检查通过；无需独立性能基准 |
| tests/test_g8_tables.py | 测试/fixture辅助 | AST静态候选6处；仅测试执行，非当前用户瓶颈 | 静态检查通过；无需独立性能基准 |
| tests/test_g9_tables.py | 测试/fixture辅助 | AST静态候选6处；仅测试执行，非当前用户瓶颈 | 静态检查通过；无需独立性能基准 |
| tests/test_help_center.py | 测试/fixture辅助 | AST静态候选7处；仅测试执行，非当前用户瓶颈 | 静态检查通过；无需独立性能基准 |
| tests/test_menu_localization.py | 测试/fixture辅助 | AST静态候选7处；仅测试执行，非当前用户瓶颈 | 静态检查通过；无需独立性能基准 |
| tests/test_p1_p2_statistical_fixes.py | 测试/fixture辅助 | AST静态候选10处；仅测试执行，非当前用户瓶颈 | 静态检查通过；无需独立性能基准 |
| tests/test_pi_import.py | 测试/fixture辅助 | AST静态候选0处；仅测试执行，非当前用户瓶颈 | 静态检查通过；无需独立性能基准 |
| tests/test_pi_reader.py | 测试/fixture辅助 | AST静态候选0处；仅测试执行，非当前用户瓶颈 | 静态检查通过；无需独立性能基准 |
| tests/test_result_background.py | 测试/fixture辅助 | AST静态候选0处；仅测试执行，非当前用户瓶颈 | 静态检查通过；无需独立性能基准 |
| tests/test_startup.py | 测试/fixture辅助 | AST静态候选1处；仅测试执行，非当前用户瓶颈 | 静态检查通过；无需独立性能基准 |
| tests/test_statistical_edges.py | 测试/fixture辅助 | AST静态候选0处；仅测试执行，非当前用户瓶颈 | 静态检查通过；无需独立性能基准 |
| tests/test_statistics_regressions.py | 测试/fixture辅助 | AST静态候选5处；仅测试执行，非当前用户瓶颈 | 静态检查通过；无需独立性能基准 |
| tests/test_supplemental_stability.py | 测试/fixture辅助 | AST静态候选0处；仅测试执行，非当前用户瓶颈 | 静态检查通过；无需独立性能基准 |
| tests/test_table_regressions.py | 测试/fixture辅助 | AST静态候选5处；仅测试执行，非当前用户瓶颈 | 静态检查通过；无需独立性能基准 |
| tools/benchmark_report_rendering.py | 开发工具/基准 | AST候选5处；开发操作不作用户热点 | 静态检查通过；无需独立基准 |
| tools/build_help_index.py | 开发工具/基准 | AST候选1处；开发操作不作用户热点 | 静态检查通过；无需独立基准 |

## 交付与验收

- [G15-module-inventory.csv](C:/Users/shaoy/AppData/Local/Temp/Minijmp-G15-20261021-101528/G15-module-inventory.csv)
- [G15-benchmark-results.csv](C:/Users/shaoy/AppData/Local/Temp/Minijmp-G15-20261021-101528/G15-benchmark-results.csv)
- [G15-benchmark-summary.csv](C:/Users/shaoy/AppData/Local/Temp/Minijmp-G15-20261021-101528/G15-benchmark-summary.csv)
- [G15-reproduction.md](C:/Users/shaoy/AppData/Local/Temp/Minijmp-G15-20261021-101528/G15-reproduction.md)
- [static-statistics.md](C:/Users/shaoy/AppData/Local/Temp/Minijmp-G15-20261021-101528/static-statistics.md)
- [static-ui.md](C:/Users/shaoy/AppData/Local/Temp/Minijmp-G15-20261021-101528/static-ui.md)

验收：源码枚举集合与CSV路径集合相等、无重复；重点函数逐项测量或标明不可达/资源阻碍；两版相关实现独立测量；Agg与Tk明确分开；统计/报告/导出/呈现分阶段；原始样本可追溯；全仓文件哈希与Git状态前后核验。保留snapshot和脚本供复现。
