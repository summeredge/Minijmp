# Minijmp 源码审查与稳定性修复记录

审查日期：2026-10-20。基准提交：`c684c7d`。交付形式为本地工作区 Diff，未提交、推送或合并。

本次按单用户 Windows 桌面统计工具的实际负载审查。保留 Tkinter、PandasTable 继承关系、菜单布局、DataFrame 和工程格式；未进行架构重写或新增统计功能。

## 1. 审查范围及调用关系

| 范围 | 关键源码及真实路径 |
|---|---|
| 启动 | `win_start.bat` / `win_start_no_cmd_win.vbs` → `start.main()` → `code/MiniJMP.main()` |
| 表格 | `MTable` → `pandastable_local.core.Table` → `core_orig.Table`；鼠标、选择、模型切换、筛选、编辑、复制粘贴、排序、增删列和撤销 |
| 数据模型 | `data.TableModel` → `data_orig.TableModel`；修改版未覆盖的方法直接继承修复，不重复实现 |
| 文件 | `MiniJMP` 文件菜单 → 表格 `importCSV/loadExcel/saveAs/load/doExport` → pandas；另检查原 DataExplore 工程保存/加载方法 |
| 统计 | `describe`、`utilities` 相关、`linear_fit`、`t_test`、`one_way_ANOVA`、`two_way_anova`、`chi_sq`、`cpk`、`GRR`、`control_chart` 及实际菜单对话框 |
| 绘图 | `linear_plot`、`Residual`、`cpk_plot`、`grr_plot`、`sb_histo`、`sbplot_dialog`、`plots.plot_viewer`；图与 Figure 所属关系、导出和关闭 |
| 资源与依赖 | `config.py`、`core.py`、`help_link.py`、主窗口和 About 图标路径；两份依赖清单 |

入口、表格、文件和重点统计路径做了源码追踪及定向运行。不是每个统计选项组合、每条遗留 DataExplore 路径都做了穷举验证。

## 2. 问题清单及处理状态

以下 P0/P1 均已修复或在原写入入口建立了明确的安全边界。P2 只修改与本次稳定化直接相关的部分。

| 编号 | 级别 | 文件 / 函数 | 触发条件与原错误 | 处理状态及原因 |
|---|---|---|---|---|
| 01 | P0 | `data_orig.TableModel.setValueAt`；两版 `handleCellEntry` | 筛选显示第三行，编辑第一个可见单元格却写入原表第一行；列重排也可能写错列 | 已按可见行列标签映射源表，并同步显示副本；重复源行/列标签不能唯一定位时在写入前拒绝并显示错误。普通重复标签表按位置编辑单个单元格 |
| 02 | P0 | `core_orig.requireUnfiltered`、表格批量写入口、`dialogs.CombineDialog.replaceTable`、两版查找替换和列重命名 | 筛选副本清空/删除后取消筛选，修改被旧备份覆盖；粘贴、堆叠、合并替换可能永久丢弃隐藏行 | 已阻止不能安全回写的批量修改及工程保存，并提示先关闭筛选；单格编辑、分类编辑、分析、复制和显式数据导出仍可使用。未增加全表合并器或额外行映射状态 |
| 03 | P0 | 两版 `copy/paste`、`MTable.paste_header` | 混合文本列经绘图用数值转换后复制会丢文本；坏行被跳过造成部分粘贴；复制默认 Tab 与粘贴逗号口径不一致 | 复制直接读取原始所选值，统一现有内部逗号格式；解析坏行明确失败，不写入部分结果；原版粘贴不再二次读取剪贴板 |
| 04 | P0 | `core_orig.convertNumeric` | 去文本正则把 `-1.5`、`($2.5)` 转成正值 | 保留负号，保持既有货币清理和数值转换流程 |
| 05 | P0 | `core_orig.cleanData` | 用户在最终确认中选择 No，数据仍被替换 | 按布尔确认结果返回，不再把 False 当作继续 |
| 06 | P0 | `MiniJMP.import_csv`、`dialogs.ImportDialog` | 菜单改走已有导入对话框后，原默认 `comment='#'` 会截断 `lot#A,1`，空行默认值也与原菜单不同 | Patch Review 中发现并修复：默认无注释符、跳过空行，与原普通 CSV 解析一致；实际 Tk 对话框回归验证完整保留字段 |
| 07 | P1 | `start.main`、BAT、VBS | `pythonw` 使用不同解释器，错误不可见、退出码丢失；启动自动 `git pull` 改动源码 | 使用 `sys.executable` 和明确子进程 cwd；传播退出码，失败输出错误并在 Windows 弹窗；移除自动更新。VBS 仍可隐藏控制台，无提权 |
| 08 | P1 | `core_orig.updateModel/redrawVisible/handle_left_release/handle_arrow_keys`、`headers.redraw`、两版编辑导航 | 五列表换成一列表后遗留列索引；空表/末格编辑越界；方向键框到 B1 但复制/删除仍针对 A1；空列开启换行后 `max([])` | 重置模型相关选择、过滤副本、编辑控件和高亮；重绘剔除失效索引；事件只作用于有效单元格；键盘同步当前行列与实际操作选择；补空表表头边界 |
| 09 | P1 | `MTable.storeCurrent/undo/redo`、原版 `undo`、文件载入入口 | 首次撤销对 None 调用 len；撤销结果与历史共用对象；筛选撤销只保留可见子集；打开其他文件仍可能使用旧历史 | 先检查历史、复制恢复帧、先更新模型再重绘；筛选快照保留完整原表；新建、导入和打开文件清除旧历史 |
| 10 | P1 | `data_orig.save/autoAddRows`、`core_orig.saveAs/load/loadExcel`、依赖文件 | `.xlsx` / 大写 / 未知后缀静默不保存；空表增行丢列；保存无扩展名；最近目录变成文件名；Excel 句柄未关闭且引擎未声明 | 支持 `.xlsx` 和扩展名大小写，未知格式明确报错；保留空表列；默认 `.pickle` 扩展名和正确目录；Excel 用上下文关闭；补声明 `openpyxl/xlrd` |
| 11 | P1 | `dialogs.ImportDialog.update/doImport`、`core_orig.importCSV` | pandas 已删除 `warn_bad_lines`；预览跳过坏行而完整导入不一致；官方 `coatings.csv` 被误当逗号且有表头 | 改用当前 API、共用预览/完整解析参数、失败保持对话框；主菜单开放原有导入选项，Tab 转义正确处理。分隔符和是否有表头由用户明确指定 |
| 12 | P1 | `core_orig.sortTable/sortColumnIndex/createCategorical/applyStringMethod/fillColumn`、`MTable.sortSelected/fillColumn/row1ToHeader` | 旧 pandas API；原版排序调用不存在的 `updateIndex`；非连续行索引被误作位置；所选列排序按标签错位；单行/空表/等端点填充失败 | 复用当前 pandas 和 NumPy API；排序保留行对应关系并可撤销；修改版复用基础列排序；线性填充保留各实现原有是否包含终点的口径；空表首行转表头返回 |
| 13 | P1 | `describe`、`linear_fit`、统计对话框 | 零均值变异系数除零；无有效样本时先求均值；两个 X 水平导致失拟自由度为零；明显不足或恒定输入继续进入推断 | 未定义 CV 返回 NaN，保留其他结果；提前检查样本；不可估计失拟继续采用原有 -1 标记；为已复现的回归、相关、ANOVA、t/Z、Cpk、SPC 输入增加局部检查 |
| 14 | P1 | `cpk_calc/cpl_cpu_95` | Cpk=0 时区间除零，单侧区间根搜索退化为 `[0,0]`；负 Cpk 时区间上下界颠倒 | 将原标准误差展开为非负形式，并避免退化根区间；正 Cpk 与原公式比对一致。证据见第 4 节 |
| 15 | P1 | `chi_sq.chi_square`、`chi2_dialog.Chi2TableDialog.apply` | 真实计数为零时 `log(0)` 导致 LR 为 NaN；非方形列联表按列数生成行标签，遗漏显示行 | 使用 SciPy `xlogy` 的零项定义；按数据行数生成标签；Pearson 算法保持不变 |
| 16 | P1 | `GRR.GRR_xbar` | 两操作员均值相同，校正后的再现性方差估计为负，开方产生复数，打印 TypeError | 与本文件其他 GRR 实现一致，将负方差分量截为零。正分量计算保留 |
| 17 | P1 | `SBDialog.make_working_df`、`singleHistoDialog`、`histo_n_fit`、`Residual.resid_test` | 数值列独立删除缺失值导致分组行错位；混合文本/全空直方图失败；提供轴时 Figure 变量未定义；恒定残差或拟合值又做不可估计回归 | 保持每行对应关系并以 NaN 标记无效数值；在绘图边界清理数值，空数据明确提示；绑定轴所属 Figure；恒定残差仍画散点，跳过不可估计的辅助回归 |
| 18 | P1 | `linear_plot`、`cpk_plot`、`control_chart`、`Residual`、`plots.plot_viewer.close` | 多图并存时 `plt.savefig` 保存其他当前图；关闭后 Tcl DPI trace 留住窗口和 Figure | 保存目标轴所属 Figure；释放本窗口的 trace、表格引用及 pyplot Figure；已存储 Figure 副本仍可使用 |
| 19 | P2 | `core_orig.redrawVisible`、`config.py`、`core.py`、`help_link.py`、图标路径 | 显示用 fillna 产生降类型 FutureWarning；资源/配置依赖调用 cwd；配置文件未及时关闭 | 显示用 object/where，不修改源 dtype；路径相对源码，UTF-8 帮助/配置，关闭文件；不增加 fallback 或迁移层 |
| 20 | P2 | `grr_plot`、`ctrlchart_dialog`；常量残差警告 | 操作员子图零件顺序不一致，SPC 分组标签被序号覆盖；常量数据仍触发统计警告 | 图中顺序/标签已修复；7 条常量数据相关警告有意保留，原因见第 6 节 |

## 3. 官方数据核查

| 文件 | 实际编码 / 格式 | 正确结果 |
|---|---|---|
| `sample_data/coatings.csv` | ASCII（也可 UTF-8 解码），Tab，无表头，末尾有空行 | 32×2，首条为 `1,18.5`，类型 int64/float64 |
| `sample_data/ElectricCarData_Clean-kaggle.csv` | ASCII，逗号，有表头 | 103×14；8 object、5 int64、1 float64 |
| `sample_data/human_age_prediction-Kaggle.csv` | UTF-8，逗号，有表头 | 3000×25；13 object、12 float64 |
| `sample_data/Gasket.xlsx` | 工作表 `Gasket` | 30×3，Operator 文本，Part/Y 整数 |

`coatings.csv` 确有两个独立问题：默认逗号解析得到 31×1；导入后旧表格选择还可能导致 IndexError。没有修改示例内容，也没有自动猜测表头。

导入 `coatings.csv`：在现有 Text Import 窗口选择 `\t`，清空 `header`，保持跳过空行，再更新预览并导入。预览和完整数据均已验证为 32×2。中文旧编码文件可明确选择 `gb18030`。

所有官方 pickle 均做了读取核查，工程格式未迁移。中文路径、中文字段、逗号、Tab、引号、换行、缺失值及日期已覆盖 CSV/XLSX/pickle 往返；CSV 重新读取测试显式指定索引和日期列，不能据此声称 CSV 本身保存了 dtype 元数据。

## 4. 统计边界修复前的样本、预期及证据

### Cpk 和单侧置信区间

输入 `data=[-2,-1,0,1,2]`、`target=5`、`lsl=0`、`usl=10`。均值为 0，因此 Cpl 和 Cpk 都应为 0；原实现在区间部分除以 Cpk² 而崩溃。

原区间半宽在正 Cpk 时可代数展开为 `z * sqrt(1/(9*N) + Cpk**2/(2*df))`。采用展开式，保留估计量和自由度；零值处区间半宽为 `z/(3*sqrt(N))`。正值代表样本与原公式相同，负值区间上下界按正确顺序输出。单侧区间仍解原非中心 t 方程，只修复数值根区间。

参考项目原本采用的 [JMP 正态能力指数说明](https://www.jmp.com/support/help/en/19.2/jmp/statistical-details-for-capability-indices-for-normal-distributions.shtml)。该页面的文字已获取，公式图片未通过网页阅读工具完整展示；本次等价性证据以原源码的代数展开、正值回归和零值极限为准。

### 零计数列联表

输入 `[[0,10],[5,5]]`，原 LR 为 NaN；同环境 SciPy `chi2_contingency(..., correction=False, lambda_='log-likelihood')` 得到统计量 `8.630462173553425`、p 值 `0.003305876912189953`。替换单个乘对数项的求值函数后，与 SciPy 一致。

依据 [SciPy xlogy](https://docs.scipy.org/doc/scipy/reference/generated/scipy.special.xlogy.html)：x 为零时乘对数项为零。未加入连续性校正，未改变 Pearson 公式。

### GRR XBAR/R 的负再现性分量

输入 `y=[1,2,3,4,1,2,3,4]`，`part=['A','A','B','B']*2`，操作员为前四个 one、后四个 two。两操作员均值相同，原式产生负校正方差并开方成复数。预期 AV=0，其余分量保持实数。

本项目 `grr_inter/grr_simple/grr_no_op` 已采用负分量截零；[Minitab 官方方差分量说明](https://support.minitab.com/en-us/minitab/help-and-how-to/quality-and-process-improvement/measurement-system-analysis/how-to/gage-study/crossed-gage-r-r-study/methods-and-formulas/gage-r-r-table/) 说明了负方差分量的零值处理。XBAR/R 此处与既有口径保持一致，不改为其他 GRR 方法。

## 5. 验证环境及结果

独立环境：`C:\Users\shaoy\Documents\PythonEnvs\minijmp\Scripts\python.exe`，Python 3.11.9。未使用 Codex bundled runtime，未升级其他项目的共享环境。

| 依赖 | 已验证版本 |
|---|---|
| NumPy / pandas / SciPy | 2.1.2 / 2.2.3 / 1.14.1 |
| Matplotlib / Seaborn / statsmodels | 3.9.2 / 0.13.2 / 0.14.4 |
| openpyxl / xlrd | 3.1.5 / 2.0.1 |

执行命令：

```powershell
$python = 'C:\Users\shaoy\Documents\PythonEnvs\minijmp\Scripts\python.exe'
& $python -m pytest tests -q --tb=short
& $python -m compileall -q code start.py
uv pip check --python $python
git -c core.whitespace=cr-at-eol diff --check
```

`tests/` 是本次新增的定向回归集，不是对项目所有模块执行全量测试。测试包括：

- `test_startup.py`：当前解释器、退出码、中文路径及不同 cwd；真实 BAT/VBS 子进程；失败错误内容。原生错误弹窗使用桩以避免等待点击。
- `test_table_regressions.py`：三层实际 Tk 表格；官方 CSV 导入、点击与编辑；空表/单行/多列；末格导航、方向键、排序、撤销重做、分类编辑、过滤切换及写入边界；真实 ImportDialog 默认选项；40 多个菜单分析对话框实际创建关闭。
- `test_file_io.py`：模型继承位置、源行列映射、重复标签、官方数据结构、中文混合内容往返、真实工程保存/加载方法、坏行与编码。
- `test_statistics_regressions.py`：描述、相关、回归、t 检验、ANOVA、Cpk、GRR、SPC 的代表性已知结果；图表数据、导出所属 Figure；真实 Tk 图窗重复创建/关闭和 Figure 回收。
- `test_statistical_edges.py`：Cpk 零/正/负边界、单侧根区间、零计数 LR、GRR 负分量及非方形列联表显示。

此外，直接 `MiniJMP.main()` 和标准 `start.py` 均在真实环境完成 Tk 初始化、事件更新和定时退出，退出码 0、无 traceback；About 窗口实际打开成功。`uv pip check` 检查 33 个包，依赖兼容。

最终合并运行：**243 passed，7 warnings，8.31 秒**；编译检查及按 CRLF 规则执行的 Diff 检查通过。测试整合时曾出现同进程多次创建、销毁 Tcl/Tk 根解释器后的初始化错误，已将测试夹具改成与应用一致的单根解释器；表格和图窗仍分别创建、关闭并检查回收，没有跳过失败测试。

## 6. 尚存限制及基线评价

- **P2，保留**：常量残差没有可解释的正态性统计量，SciPy/statsmodels 会产生范围为零或除零警告、部分结果为 NaN；坐标范围为零时 Matplotlib 自动扩展。绘图可完成，不为隐藏警告而伪造统计结果或更换算法。
- **已明确限制**：筛选时的批量数据/结构修改和工程保存需先关闭筛选；非唯一源行列标签的筛选编辑需先恢复完整表。未实现通用筛选事务或新映射层。
- CSV 保留原有索引导出习惯，类型/日期推断仍需导入参数；剪贴板使用既有逗号格式，未声称支持所有外部应用剪贴板格式。工程 pickle 用于完整 dtype 保留。
- `.xlsx` 往返已验证；当前 pandas 不提供旧 `.xls` 写引擎，旧 `.xls` 导出会明确失败。未增加不受维护的写入依赖或更改扩展名伪装格式。
- 启动 stderr 由父进程捕获，GUI 回调错误的 stderr 仍可能在程序退出后才输出；本次保障了启动失败提示和退出状态，未新增日志框架。
- 未执行完整人工菜单遍历、不同 Windows DPI/系统主题、交互式鼠标长时间拖拽、大数据性能压力、所有旧平台、科学依赖最新版本或所有统计参数组合的验证。中文数据和路径已验证，中文图形字体的实际显示未做人工验收。

**评价：可以作为固定 Python 3.11 和已验证依赖版本下继续二次开发的稳定化起点。不能把本轮定向验证等同于所有统计模块的长期校准认证。** 后续开发应保留这些回归测试，并将实际使用的统计模型加入相应参考样本验证。

## 7. Patch Review 与复杂度检查

独立审查发现的 CSV `#` 截断、筛选去重删除、合并替换和方向键选择遗漏，均已在本次补齐并由原入口回归覆盖。再检查原始/修改版的重复实现，修复基础排序和线性填充边界，保留各实现原有终点规则。

最终只读复核未发现本轮收尾 Diff 新增的 P0/P1 或已知部分修复遗漏；测试整合后的结果以上述实际合并运行为准。

no-stop-gpt Audit 保留了有明确消费者的模型状态重置、历史复制、错误提示和资源释放；筛选防护集中为一个小检查方法，并在可绕过菜单的真实写入口调用。没有新增兼容层、缓存、后台线程、数据格式或统计框架。Excel 引擎为现有 Excel 功能所需依赖。

正常统计输入的口径通过参考数值与原公式对比保留；第 4 节明确列出了必须修复的数值边界，没有隐瞒这些差异。官方样例、已有用户配置和已有数据文件未修改。


## 8. 补充修复（2026-10-20）

本节在上述未提交补丁上追加，不替代原有修复和验证记录。

- **P1-01**：复现 `TableModel(columns=50)` 仅生成 26 列。`data_orig.TableModel.setup` 改为按请求数量生成名称，前 26 列仍为 a-z，第 27 列起为 col27、col28……。`data.TableModel` 继承该方法；`core_orig.Table` 构造和 `new` 两处入口，以及 `core.Table` / `MTable` 均共用修复，没有增加重复实现。
- **P1-02**：复现常量输入在 `MSO / MSPO` 处抛出 ZeroDivisionError。`grr_nested` 检查输入长度、有限数值、各零件重复数、零件唯一所属操作员、平衡设计和正自由度；历史标准差必须有限且为正。零分母 F/P、Distinct Categories、总变异比例返回 NaN，并在输出中说明 `nan = not estimable (zero denominator)`。保留可估计的方差和标准差，负零件间方差分量按本文件 GRR 既有口径截零，不输出复数。返回字典键不变。`GRR_Nested_Dialog.apply` 原有 ValueError 提示和输出通道已足够，真实 Tk 对话框验证通过，无需重复修改 UI。
- 正常参考设计：2 操作员、每人 2 个不同零件、每零件 2 次测量，响应 `[1,3,5,7,9,11,13,15]`。MSO=128、MSPO=16、MSR=2；重复性方差=2、再现性方差=28、零件间方差=7，GRR%=100×sqrt(30/37)。F/P 与原公式及 SciPy F 分布核对一致。
- **行尾**：仅将 `GRR.py`、`modified_table.py`、`data_orig.py` 的 CRLF 字节恢复为索引采用的 LF；修改前已在系统临时目录保存原字节。`modified_table.py` 经归一化前后逐字节一致；另两文件仅有上述定向改动，原补丁保留。仓库 `core.autocrlf=true` 原本已让 Git 自动忽略这批行尾差异，因此不能声称 Git 统计减少了数千行；未修改用户 Git 配置，Git 将来可能再次转换工作区行尾。
- 同类模式检索：新建表的旧切片已消失；另有 `core_orig.createCategorical` 的 `ascii_uppercase[:bins]` 用于分类分箱标签，不属于新建列入口，本次按限定范围未修改。插件闭包中的 `new` 与建表无关。
- 新增 `tests/test_supplemental_stability.py`：39 项通过；涵盖两层实际模型、三层 Tk 表格构造及实际 `new` 方法的 26/27/50 列、正常参考值、常量、零重复性、零零件间方差、负方差分量、历史标准差、退化设计及真实 Nested GRR 对话框 apply。新建参数对话框以返回指定尺寸的桩代替人工输入。
- 相关已有回归 `test_statistical_edges.py`、`test_table_regressions.py`、`test_file_io.py`：166 项通过。补充测试首轮的两个失败来自测试应用桩缺少帮助方法、清理时未使用既有 `dialog.main.destroy()` 约定，已修正并重新通过全部 39 项；产品代码未因测试夹具失败改变。合计 205 项相关用例通过，未重复无关全量测试。
- 对修改文件执行 compileall 和 `git -c core.whitespace=cr-at-eol diff --check`，均通过。Patch Review 确认已有 XBAR/R 修复、筛选写入和历史操作补丁保留；新增逻辑局限于基础列名生成及 Nested GRR 的数学边界。no-stop-gpt Audit 保留有实际失败证据的边界校验，无新增抽象、缓存、状态或依赖。
- 未执行完整人工桌面验收、全部统计参数组合或极端浮点溢出压力测试。NaN 表示不可估计，调用方不得将其当作有效统计值。全部改动保留为未提交工作区 Patch；未 commit、push 或 merge。
