# P0 过程能力分析验收记录

日期：2026-10-23。工作区：`C:\Users\shaoy\Documents\Minijmp`。

## 本次范围与文件

- 新增 `code/capability.py`：独立过程能力核心、三种正域分布 MLE、重新拟合的参数自举、Box-Cox/Johnson SU 及诊断数值表。
- 新增 `code/capability_dialog.py`：来源快照、后台计算/取消、结果表、报告、CSV/Excel、新工作表及仅作用于能力图窗的标准坐标导航。
- 新增 `code/capability_plots.py`：正态/非正态 Sixpack、变换前后四图、逐点控制限诊断。
- `code/MiniJMP.py` 仅在本任务范围内加入质量菜单和统一入口，保留原有回归扩展改动。
- 新增 `tests/test_capability.py`、`tests/test_capability_plots.py`、`tests/test_capability_dialog.py`；同步菜单/帮助测试及 `tests/fixtures/g12_table_inventory.json` 的文件、生产位置、逻辑表标题审查。
- 新增 `help/pages/capability-analysis.html`、`docs/capability-analysis.md`；同步 `help/help-map.json`、`help/assets/search-index.js`、`docs/MENU_TRANSLATION.md`。

开始时工作区已有回归扩展的未提交源码、测试、清单和文档。本任务未撤销这些改动，未修改旧 `cpk.py`、`cpk_plot.py`、`qc_dialog.py`、`control_chart.py` 或其历史冻结夹具，保留 GPLv3 文件与原作者署名。没有增加依赖，没有创建提交或推送，没有实施下一阶段质量工具。

## 环境与命令

使用项目已有解释器，未使用 Codex bundled runtime，也未安装/升级依赖：

```powershell
$python = 'C:\Users\shaoy\Documents\Minijmp\.venv\Scripts\python.exe'
& $python -c "import sys,scipy,pandas;print(sys.executable,sys.version,scipy.__version__,pandas.__version__)"
```

实际版本：Python 3.11.9、SciPy 1.15.3、pandas 3.0.6。GUI 为真实 Windows Tk，非 mock 渲染；菜单调用使用真实 Tk `Menu.invoke()`，计算使用后台线程。根目录不存在 `DESIGN.md`，窗口沿用项目原生 Tk/ttk 及 `StatTable`、`SheetApp`、`PlotViewer`。

| 实际命令（省略同一 `$python` 前缀） | 结果 | 说明 |
| --- | --- | --- |
| `-m pytest tests/test_capability_dialog.py tests/test_capability.py tests/test_capability_plots.py -q --tb=short --basetemp "$env:TEMP\minijmp-capability-final"` | 83 passed，24.59s | 核心46、图形25、GUI12；此后只补能力图窗导航与表格伸缩，相关GUI另外重跑 |
| `-m pytest tests/test_capability_dialog.py -q --tb=short --basetemp "$env:TEMP\minijmp-capability-final-gui"` | 12 passed，20.46s | 最终GUI：真实鼠标框选缩放、复位与现有 `savePlot` 保存入口；核心/绘图算法未再修改 |
| `tools/build_help_index.py` | 成功 | 根据最终帮助正文生成离线索引 |
| `-m pytest tests/test_menu_localization.py tests/test_help_center.py tests/test_g12_inventory.py -q --tb=short` | 85 passed，14.60s | 菜单顺序、翻译、帮助映射/链接/索引与报告清单 |
| `-m pytest tests/test_capability_plots.py tests/test_windows_packaging.py tests/test_g3_computation_contracts.py -q --tb=short` | 59 passed，7.17s | 当时图形为23项；该组合在 Tk 预初始化后运行，包含旧 Cpk 等计算 AST 契约及打包静态测试，不与83项重复累加 |
| `-m pytest tests/test_g5_spc_reports.py -q --tb=short` | 73 passed，6.75s | Tk 预初始化后运行，旧 SPC 数值/报告/真实对话框 |
| `-m pytest tests/test_regression_dialog.py -q --tb=short` | 16 passed，19.73s | 既有完整回归及广义回归/PLS GUI |
| `-m pytest tests/test_pca_dialog.py tests/test_time_series_analysis_dialog.py -q --tb=short` | 8 passed，13.26s | 既有 PCA 与时间序列 GUI |
| `-m pytest tests/test_statistics_regressions.py tests/test_statistical_edges.py -q --tb=short` | 75 passed，7 warnings，4.72s | 既有统计回归；警告来自常量数据的 Shapiro/AD 和绘图退化尺度 |
| `git diff --check` | 成功 | 仅报告原有文件的 LF/CRLF 提示，无 whitespace error |

上述是分组执行结果，没有将重复运行的测试累加成唯一测试总数，也没有把错误或未执行项计为通过。最终方法与边界对应关系见 [逐方法独立参考](capability-analysis.md#逐方法独立证据矩阵)。

旧 SPC 与打包组合最初在延后初始化 Tk 时出现 Tcl 文件读取错误（113 passed、19 errors），单独复跑 SPC 仍为54 passed、19 errors；解释器、Tcl文件存在且直接初始化 Tk 成功。未修改项目环境，通过在 pytest 收集前初始化 Tk 后，相关组分别全部通过。一次预初始化后再组合运行回归/PCA/时间序列的尝试发生 Windows `0x80000003`，没有将其记为通过；这些功能分开执行后通过。可复现的预初始化命令形式：

```powershell
& $python -c "import tkinter as tk; r=tk.Tk(); r.withdraw(); import pytest; raise SystemExit(pytest.main(['tests/test_g5_spc_reports.py','-q','--tb=short']))"
```

开发联测曾因把来源索引的文本保护误写成数值 dtype 预期而失败，修正了本任务新增测试的预期；保留既有 `export_source_labels` 行为。坐标导航测试初次构造 Matplotlib motion event 时未设置 `buttons={1}`，标准导航按失去鼠标按键取消缩放；修正事件构造后验证真实框选及复位，没有绕开缩放结果断言。

## 实际 GUI 与文件证据

最终 GUI 验证包括五个质量菜单、单/双侧规格、无目标、90%置信水平、K=5、固定大小与子组ID、三种非正态分布、Box-Cox及Johnson SU、取消后保留结果、来源表关闭报错、切换/修改活动表后继续使用原快照。窗口在760×580仍可操作，结果区随宽度伸缩，长表可滚动。

图形与报告均发布至来源工作表。CSV/XLSX重读检查数值精度，并保留带18位前导零的来源索引；新工作表输出与原始工作表隔离。缩放测试发送真实 Matplotlib 鼠标按下/移动/释放事件，检查坐标范围缩小，复位恢复；PNG通过已有图窗保存入口生成并由Pillow重读。

- [结果窗口截图](evidence/capability-p0/result-dialog.png)
- [正态 Sixpack](evidence/capability-p0/normal-sixpack.png)
- [非正态 Sixpack](evidence/capability-p0/nonnormal-sixpack.png)
- [Box-Cox 原始/变换后四图](evidence/capability-p0/boxcox.png)
- [来源观测 CSV](evidence/capability-p0/observations.csv)、[来源观测 Excel](evidence/capability-p0/observations.xlsx)

样本是固定种子生成的合成数据，正态模型失配或超控制限警告在截图中保留，不能将图中能力值当作真实生产验收结论。截图和PNG已打开核对归属及面板内容。

## 适用范围与未验证项

- 非正态主指数为百分位法，另列等价Z；与Minitab默认Z-score法不同。Johnson只支持SU MLE，非SB/SL/SU全族Chou选择；Box-Cox剖面似然/未舍入λ与Minitab子组优化有差异。
- 非正态拟合KS采用199次重新拟合的参数自举，有模拟误差。变换选参后的正态AD只用于诊断，不能当独立正常性证明；不合格变换明确失败。
- 当前提供适用的标准差、Cp/Pp及整体Ppl/Ppu区间；其余能力区间、变换后/非正态区间和PPM区间未提供，报告NA。Q-Q没有概率置信带。
- 非正态I控制限使用0.135%/99.865%拟合分位；MR及非正态子组图采用已披露的正态常数近似，仅标记超控制限点，没有声称执行全部Nelson/Western Electric规则。控制限不是规格限。
- 没有执行全量pytest或完整PyInstaller构建，没有验证打包exe的无管理员启动；`test_windows_packaging.py`只验证onedir配置、静态入口、资源及可写目录等。新源码的导入链可被现有PyInstaller分析，未新增运行时依赖。现有源码ZIP脚本基于`git ls-files`，发布前必须保证新增文件已进入源码归档；本任务按要求保留未提交状态。
- 只验证当前Windows字体/DPI和最小窗口尺寸，没有宣称覆盖全部缩放比例或与商业Minitab逐值、逐像素完全相同。

复杂度审查采用no-stop-gpt Audit：保留直接SciPy拟合与单一结果字典；复用现有表格/来源适配/图窗，删掉五个多余菜单转发方法。后台Future、取消Event和深拷贝分别对应计算状态、迟到结果丢弃及来源快照边界；局部标准导航是现有图窗缺少坐标缩放的必要补充，不引入通用图形编辑器、缓存、兼容层或新依赖。
