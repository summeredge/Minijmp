# MiniJMP 第二阶段统计绘图验收记录

日期：2026-10-21。七类入口已完成；未扩展第三阶段，未提交、推送、合并或执行清理/覆盖命令。

## 开始状态与环境

- 阅读了当前 AGENTS.md、CODING_STANDARDS.md、CONTRIBUTING.md，以及实际菜单、对话框、查看器、统计绘图和理论分布入口。根目录不存在 DESIGN.md，沿用项目原生 Tk 控件和紧凑布局。
- 使用 `C:\Users\shaoy\Documents\Minijmp\.venv\Scripts\python.exe`；Python 3.11.9、pandas 3.0.6、SciPy 1.15.3。未安装或升级依赖，未使用 Codex bundled Python。
- 开始时已有修改：AGENTS.md、code/MiniJMP.py、code/modified_app.py、code/pandastable_local/plotting.py、docs/MENU_TRANSLATION.md、help/assets/search-index.js、help/help-map.json、help/pages/graphs.html、tests/fixtures/g12_table_inventory.json、tests/test_help_center.py、tests/test_menu_localization.py。
- 开始时已有未跟踪文件：code/basic_plot_dialog.py、docs/plot-phase1-acceptance.md、tests/test_phase1_plots.py。以上全部保留；共用菜单和帮助文件仅叠加本阶段内容。
- 执行期间额外出现 code/icon.png 的修改及 code/icon_old.png、根目录 icon.png 未跟踪文件。本任务未写入这些文件，未回退或删除它们。Git diff 包含既有及外部改动，不能全部归于本阶段。

## 实施前核查与最终入口

所有新增菜单均经真实 Tk 菜单 `invoke()` 打开，使用真实 Listbox/Combobox 选择变量并执行。

| 图形 | 实施前 | 实际复用与补全 | 最终菜单与状态 |
| --- | --- | --- | --- |
| 气泡图 | 未实现独立功能；已有 X-Y 散点图 | Matplotlib scatter，以第三列映射面积，沿用查看器 | 图形 → 气泡图，已实现 |
| ECDF | 未实现 | Seaborn ecdfplot，不新增经验分布算法 | 图形 → 经验累积分布函数图，已实现 |
| 单值图 | 部分实现：第一阶段旧点图含摘要，箱线图可叠加 swarm 点，不满足独立纯观测入口 | Seaborn stripplot，水平抖动，不叠加箱线/均值 | 图形 → 单值图，已实现 |
| 区间图 | 部分实现：Anova1WayDialog → sb_misc.interval_plot 使用已有自定义 CI；默认 pointplot 使用 bootstrap CI | 新入口明确提供 Student-t 均值 CI 回调；interval_plot 仅增加可选 errorbar 参数，原默认值和 CIs 优先级不变 | 图形 → 区间图，已实现 |
| 边际图 | 未实现独立功能 | Figure.add_gridspec + scatter/hist，共用原查看器 | 图形 → 边际图，已实现 |
| 茎叶图 | 未实现 | Decimal 精确十进制截断及既有 MiniJMP.print → txt_viewer，纯文本统计图 | 图形 → 茎叶图，已实现 |
| 样本概率图 | 部分实现：NormTestDialog 的可选 QQ 图调用 stats.probplot | 复用同一 SciPy 正态 probplot 定义，增加独立入口和输入校验 | 图形 → 样本概率图，已实现 |

既有“概率图 / 概率图对比”仍调用 distDPPlot/dist2XPlot → dist_plot_dialog，显示理论分布。新增“样本概率图”分析工作表样本，帮助页明确区分。

## 数据、定义和边界

- 所有处理均创建独立数据，不写入原 DataFrame、索引、列名或 dtype。非数值内容报中文错误；数值缺失和无穷值排除，不填补、不插值、不平滑。
- 气泡/边际采用完整配对行；ECDF、单值、区间逐列取有效样本，可选分类缺失行排除。分类按首次出现顺序显示；组的显示名称歧义时明确报错，避免意外合并。重复索引按行位置对齐。
- 每列必须存在有效观测。只有 ECDF、概率图和茎叶图按定义排序；其他图不重排观测。单值图仅水平位置抖动，纵坐标保持原值。
- 校验列、参数、区间/参考线和坐标可表示范围后才调用 showPlotViewer。来源工作表通过现有 SheetApp 绑定；切换后仍输出到原表，来源删除后显示中文提示。无效输入不替换现有图形或茎叶输出。

| 图形 | 明确定义及限制 |
| --- | --- |
| 气泡 | 面积 s = 原大小值 / 有效样本最大大小值 × 500 pt²。拒绝负数或全零；零面积不可见，图内标明比例及单位。比例缩放不改原值。可选分类颜色、图例。 |
| ECDF | F(t)=#{X≤t}/n，右连续阶梯，重复值在同一位置累计跳跃；纵轴固定 0～1，不拟合分布。 |
| 单值 | 每列/分类绘制全部有限观测，不求均值、不聚合。复用 stripplot 的适度水平抖动。 |
| 区间 | 均值 ± t((1+C)/2,n−1)·s/√n；s 为无偏样本标准差。默认 C=.95，可调整；独立同分布正态总体下为精确区间，其他总体需理解其近似性质。每组至少两个观测，常数组区间宽度为零。不连接各组均值。 |
| 边际 | 中心散点及上下边际使用完全相同的有效配对样本。上方 X 直方图、右侧 Y 直方图，共享对应尺度；分箱数为 1～200 整数。预检有限且递增的分箱边界。 |
| 茎叶 | 直接读取原始十进制值，避免 float 转换先舍入大整数或高精度小数。叶单位为 10^k，k 为 -308～308 整数；自动按最大绝对值选取。朝零截断，显示值与原值差小于一个叶单位。保留负零茎、重复叶及负数次序；显示 N、叶单位和读法。细分跨度超过 1000 个叶单位时报错，要求增大单位；长叶行换行。 |
| 概率 | 仅正态 QQ 形式：排序样本对 Filliben 标准正态理论分位数；参考线使用 SciPy probplot 的最小二乘拟合。至少两个观测，常数列为水平线；不报告相关系数 p 值或其他拟合优度检验。 |

六类 Matplotlib 图支持标题、轴标签、网格、水平参考值和原查看器 PNG/SVG/PDF 保存；气泡及 ECDF 提供适用的图例开关。茎叶图使用原文本窗口复制/UTF-8 TXT 保存，不强制转换成图像。

## 独立参考与逐项证据

测试位于 tests/test_phase2_plots.py，未用新旧输出相等代替定义核验。以下各方法不涉及假设检验的 H0/备择或 p 值，均为不适用；区间明确列出覆盖假设。

| 生产路径 | 独立参考/推导 | 覆盖 |
| --- | --- | --- |
| statPlot('bubble') → StatPlotDialog | test_independent_references：手工配对坐标及面积 [0,125,250,500] | 零、负数、全零、分类、缺失、重复索引、不修改源表 |
| statPlot('ecdf') → ecdfplot | test_independent_references：直接按 #{X≤t}/n 计数，与线条同值位置的最右累计概率比较 | 重复值、常数、单样本、多列、分类、无穷值 |
| statPlot('individual') → stripplot | test_independent_references：直接核对 Artist 的纵坐标为 [1,2,2,4] | 原始观测、重复、常数、单样本、水平抖动 |
| statPlot('interval') → interval_plot | test_independent_references：样本 [1,2,2,4] 的均值 2.25、无偏方差 19/12、表值 t(.975,3)=3.182446305284263；test_grouped_columnwise_missing_and_confidence：df=1 时 t(.95)=tan(.45π) | 95%/90%、逐列缺失、分类、常数、n=1 拒绝、非法置信水平 |
| statPlot('marginal') → scatter/hist | test_batch2_reference：明确列举四对有效坐标，并独立核对两个边际频数总和均为 4 | 样本一致、缺失、无穷、常数、单样本、非法分箱 |
| statPlot('stem') → stem_leaf → print | test_stem_signed_decimal_duplicates_and_range：手工十进制负茎/叶、重复值和截断；test_stem_does_not_round_through_binary_float：9007199254740993 的叶应为 3，以及 0.99999999999999999 在单位 .01 下应落于 9\|9 | 正负零、小数、重复、单位、细分跨度、空/文本、大整数精度；原先 float 路径的两个反例均失败，修复后通过 |
| statPlot('probability') → probplot | test_batch2_reference：独立构造 Filliben 概率位置 [1−.5^(1/n), (i−.3175)/(n+.365), .5^(1/n)]，正态逆 CDF 后用 NumPy polyfit 核验参考线 | 排序、重复、常数、n=1 拒绝；未将 r 当 p |

## 验证命令与结果

所有命令在仓库根目录执行，显式使用项目解释器。

1. 第一批完成后、第二批实施前：`& .venv/Scripts/python.exe -m pytest tests/test_phase2_plots.py -q --disable-warnings --maxfail=1`：**25 passed，0 failed**。
2. 组合回归：

```powershell
& .venv/Scripts/python.exe -m pytest tests/test_phase2_plots.py tests/test_phase1_plots.py tests/test_g13_time_series.py tests/test_g6_chart_presentation.py tests/test_menu_localization.py tests/test_help_center.py tests/test_g12_inventory.py tests/test_sheet_context.py tests/test_g12_tables.py -q --junitxml=docs/plot-phase2-evidence/pytest.xml
```

结果：**301 passed，0 failed，33 warnings，126.95 秒**。

| 文件 | 此组合通过数 |
| --- | ---: |
| test_phase2_plots.py | 68 |
| test_phase1_plots.py | 59 |
| test_g13_time_series.py | 37 |
| test_g6_chart_presentation.py | 49 |
| test_menu_localization.py | 47 |
| test_help_center.py | 11 |
| test_g12_inventory.py | 15 |
| test_sheet_context.py | 6 |
| test_g12_tables.py | 9 |

3. 随后补充并修复茎叶精度反例，以及六类图形坐标溢出前校验；仅重跑受影响的阶段二与清单：

```powershell
& .venv/Scripts/python.exe -m pytest tests/test_phase2_plots.py tests/test_g12_inventory.py -q --junitxml=docs/plot-phase2-evidence/final-targeted.xml
```

结果：**88 passed，0 failed，0 warnings，70.78 秒**，其中阶段二最终 **73** 项、清单 **15** 项。其余代码未变化的回归复用上一步结果；这不是一次 306 项的整批执行。

4. 补充最终十进制说明后运行 `& .venv/Scripts/python.exe tools/build_help_index.py` 并复验 `& .venv/Scripts/python.exe -m pytest tests/test_help_center.py -q`：**11 passed，0 failed，0.32 秒**。

过程失败均已闭合：茎叶自动单位的测试预期、尚未生成图形的工作表不存在 pf 属性的测试假设、分组区间的均值线/误差线选择均已修正；翻译清单七项最初位于独立章节，现已放入实际图形菜单表；茎叶浮点精度的两个真实反例先失败、修复后通过。没有放宽数值容差或刷新错误统计基线。

33 条警告均来自既有路径：Pandas 饼图/矩阵清轴提示、Seaborn 箱线 vert 弃用、相关矩阵旧椭圆计算的 invalid scalar power、残差图 set_tight_layout 待弃用。未修改这些无关算法。

## GUI、保存和文档证据

- 阶段二真实 Tk 菜单、变量选择、preview、退出、分组执行均覆盖；不是用 mock 替代菜单或绘图。错误通道和删除工作表的确认弹窗在测试中被捕获，避免自动化等待用户。
- 六类图分别保存 PNG/SVG/PDF；PNG 用 Pillow 重新打开并检查像素非空，SVG/PDF 检查生成且有内容。茎叶 TXT 保存后按 UTF-8 重新读取核验。
- 原生窗口截图位于 [plot-phase2-evidence](plot-phase2-evidence/)，包含七张对话框与七张输出。已打开检查 [overview.png](plot-phase2-evidence/overview.png) 和 interval-dialog.png，图形、中文、图例及三坐标轴正常；截图过程还检查了所有对话框高度小于屏幕高度。
- 帮助主题从 70 增至 77，更新菜单翻译表、主题映射、图形页目录/正文及搜索索引。
- 新 code/stat_plot_dialog.py 已人工分类加入 G12 files/file_reviews/output_entry_review。茎叶为文本统计图，不是新增逻辑统计报告表；保持 **82** 张逻辑表及既有生产位置契约。
- no-stop-gpt Audit：新增 field 辅助仅复用本对话框的紧凑输入行；单独 Decimal 路径有两个精度反例依据；未增加缓存、通用渲染框架或布局抽象。保留必要的输入和工作表生命周期验证。

## 本任务新增/修改范围

新增：code/stat_plot_dialog.py、tests/test_phase2_plots.py、本记录、docs/plot-phase2-evidence/ 的截图及两份 pytest XML。

增量修改：code/MiniJMP.py、code/sb_misc.py、docs/MENU_TRANSLATION.md、help/help-map.json、help/pages/graphs.html、help/assets/search-index.js、tests/test_menu_localization.py、tests/test_help_center.py、tests/fixtures/g12_table_inventory.json。

未更改第一阶段 basic_plot_dialog、通用 PlotViewer、时间序列、控制图、箱线算法、工作表模块、CSV 或 PI 功能。保留既有未提交和未跟踪文件；最终 Git 状态仍有本任务、既有及执行期间外部修改，未执行提交。

## 已知限制与未验证范围

- 样本概率图首版仅正态 QQ；无其他分布、拟合优度检验或概率刻度轴扩展。
- 边际图仅直方图；区间 n<2 明确拒绝；气泡负数/全零拒绝；茎叶精度受用户叶单位和输出跨度限制，均在帮助中说明。
- 未进行人工点击全过程、跨 DPI/多显示器或不同操作系统验收；真实 Tk 自动化与原生截图不能替代这些检查。
- 未使用独立外部应用重新打开 SVG/PDF；PNG 与 TXT 已实际重开。未运行全仓库 pytest，已运行约定回归及直接相关报告/工作表检查。
