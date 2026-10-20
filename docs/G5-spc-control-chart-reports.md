# G5 SPC 控制图统计报告验收

2026-10-20，在 `C:\Users\shaoy\.codex\worktrees\d4c3\Minijmp` 完成统计结果展示层优化。
开始时工作树干净，基线为 `191c3b7b245ff40f600d442bbf18ea7e523a28df`。
执行前读取了实际源码、调用方、相关测试以及 G1/G2 验收文档。
没有新增控制图或特殊原因规则，没有 commit、push、merge 或启动 G6。

## 功能与重复入口清单

| 类型 | 实现与输出入口 | Dialog/其他调用方 | 原报告与本次覆盖 |
| --- | --- | --- | --- |
| I-MR | `x_mR()` 计算，`x_plot()` 输出 | `IMRDialog.apply()` | 原为两份控制限小表，列表仅写 Multiple；现在分清 I 单值与 MR 移动极差，显示实际跨度、MR 初始缺失位置及两图明细 |
| I 单图 | 同上，`one_chart=True` | `IDialog` 继承 apply；`Residual.py::resid_test()` 关闭控制图文本输出 | 只报告 I 图；残差消费者保持无控制图文本输出 |
| MR 单图 | 同上，`chart_two_only=True` | `MRDialog` 继承 apply | 只报告 MR 图，不混入单值统计量 |
| Xbar-R | `xBar_R()` 计算，`x_plot()` 输出 | `XBRDialog.get_data()`、继承 apply | 展示子组大小、观测总数、子组均值/极差和实际控制限；固定与可变子组均覆盖 |
| Xbar-S | `xBar_S()` 计算，`x_plot()` 输出 | `XBSDialog.r_or_s()`、继承分组和 apply | 展示子组标准差，区分 S 与 R；覆盖指定 sigma、合并与非合并估计路径 |
| P | `p_np_plot(NP=False)` | `PDialog.get_data()`、继承 `NPDialog.apply()` | 原只报告中心值；现在展示每组检验数量、比例及逐点控制限 |
| NP | `p_np_plot(NP=True)` | `NPDialog.get_data()/apply()` | 原只报告首组限值；现在逐点报告原实现的计数和控制限，并说明按首组检验数量缩放 |
| C | `cu_plot(C=True)` | `CDialog.get_data()/apply()` | 明确为缺陷数，GUI 每次一个检查单位；逐点报告实际值及控制限 |
| U | `cu_plot(C=False)` | `UDialog.get_data()`、继承 `CDialog.apply()` | 原只报告中心值；现在展示检查单位/机会数、实际单位缺陷数与逐点控制限 |

七类目标图全部已有实现，没有未实现的目标图类型。三份计算函数本身没有文本报告，
三份绘图函数承接全部直接及 Dialog 报告入口；没有找到另一份 SPC 文本报告实现。
P/NP 和 C/U 的共享实现以及 I/MR、Xbar-R/S 的共享出口均逐一覆盖。

**特殊原因判定尚未实现**：上述计算、绘图和 Dialog 路径没有规则计算、异常点索引、
规则编号或多规则结果。因此不存在可格式化的既有异常记录；没有新增算法补算越限、
同侧或趋势信号，也没有输出“没有异常”“过程完全受控”。GRR 说明文字引用 Nelson 规则，
不是本模块的异常判定实现，未将其当作可用结果。
没有阶段或规则开关参数，报告不推断这些设置。

## 实际修改

生产文件仅 `code/control_chart.py`：

- 新增局部 `_print_spc_report()`，由三个真实输出入口复用 `utilities.gen_table()`。
- 仅替换 `x_plot()`、`p_np_plot()`、`cu_plot()` 的顶层 `if print_out` 内容。
- 其余函数、所有签名/默认值、返回键及返回值、绘图调用、控制图常数、
  下限截断、缺失值处理和 Dialog 参数/交互完全保留。
- `tests/test_g1_debug_output.py` 仅更新两条旧文本断言，保留取数、数值和图形断言。
- 新增 `tests/test_g5_spc_reports.py` 和 `tests/fixtures/g5_spc_algorithm_ast.json`。

报告按控制图信息、控制限汇总、过程统计摘要与逐点明细、特殊原因及异常点、结论组织。
汇总表为 `图表 / LCL / CL / UCL`；实际变化的序列标注“逐点变化（见明细）”，
数值相同的序列显示固定值；全 NaN 中心线/上限显示 `*`，不冒充变化的有效控制限。
明细逐点列出序号、已有子组/时间标识、样本量/单位数、统计值及对应三条线。
没有用一个首组控制限代替整组结果，也没有重新计算均值、sigma 或异常点。

报告取实际绘图使用的线值，包含调用方覆盖的 `bar/lcl/ucl`，保留原计算允许的负下限；
没有新增截断。明确控制限和产品规格限不同，统计值按图种区分。
数值使用六位有效数字，保留小比例的量级；只是显示舍入，不改变返回或绘图精度。
数字列右对齐，表格继续使用已有 PrettyTable；没有新增依赖、报告模型、缓存或配置。

I/MR 展示移动极差实际有效跨度，MR 前 `跨度 - 1` 项显示缺失。
Xbar 报告已有加权总均值/实际中心线、每组均值与极差或标准差，不把 R/S 中心线误称为
样本极差/标准差的简单平均。估计 sigma 没有从控制限倒算，只说明原估计来源；
显式传入的 mean/sigma、k 则忠实展示。输入仅提供坐标轴标签时按“显示标签”说明，
不将任意自定义轴名冒充原始分析变量。标识未提供显示 `*`；点号按本次输入顺序从 1 列示，
不伪装为原 DataFrame 行号或异常点索引。

## 数值、源码和图形不变性

修改前的当前工作树源码、受保护文件摘要和对照脚本保存于
`%TEMP%\minijmp-g5-before-01a1594b`，不成为应用运行依赖。
永久 AST 基线摘要来自这份修改前源码，未从修改后实现反向生成：

- 对 `x_mR`、`xBar_R`、`xBar_S`、`limit_line`、`additional_SD`、`x_plot`、
  `p_np_plot`、`cu_plot` 逐函数比较 AST SHA256。
- 只从后三个函数移除顶层、条件恰为 `print_out` 的报告分支；保留所有计算、
  绘图、返回、参数和默认值进行比较。八个摘要全部一致。
- 有界源码守卫分别定位三个函数的旧 `Multiple`、旧 mean 输出和旧标题，
  确认旧模式已消失，没有用全仓库宽泛字符串排除替代算法检查。
- 修改前后执行 100 组精确对照：93 组返回结果相同，7 组保留相同类型及消息的既有异常。
  字典顺序、键、原始浮点值、数组、列表、NaN 均精确比较，不以格式化文字证明一致。
- 其中 62 组绘图成功：原统计曲线、CL/UCL/LCL、附加标准差线、颜色/线型、标签、
  刻度、坐标范围及整张图 RGBA 像素完全一致。
- 覆盖正常、明显越限、控制限边界、常量、NaN、MR 跨度、可变子组、
  历史 mean/sigma、pooled、调用方覆盖控制限、P/NP/C/U、输出开关及原有错误输入。
- 当前没有异常索引/规则返回，二者“未计算”的状态保持不变；越限测试不构造虚假的规则结果。

## Python 环境与实际测试

当前 Worktree 没有 `.venv`，使用符合项目声明的现有专用环境：
`C:\Users\shaoy\Documents\PythonEnvs\minijmp\Scripts\python.exe`。
Python 3.11.9、NumPy 2.1.2、SciPy 1.14.1、pandas 2.2.3、Matplotlib 3.9.2、
PrettyTable 3.11.0、pytest 9.1.1；没有安装/升级依赖，没有使用 Codex bundled runtime。

修改前基线：相关旧回归 **130 通过、8 失败**。
八项均为 `test_g1_files_keep_verified_head_lf_style`：当前 Git 自动换行检出为 CRLF，
与旧测试要求公共文件必须含 LF 的断言不符。这不是 G5 引入的失败，未改公共源码消除它们。

实际命令与结果：

```powershell
$python = 'C:\Users\shaoy\Documents\PythonEnvs\minijmp\Scripts\python.exe'
& $python -m pytest tests/test_g5_spc_reports.py -q --tb=short
& $python -m pytest tests/test_g5_spc_reports.py tests/test_g1_text_output.py tests/test_g1_debug_output.py tests/test_statistics_regressions.py tests/test_statistical_edges.py tests/test_supplemental_stability.py -q --tb=short -k 'not test_g1_files_keep_verified_head_lf_style'
& $python -m pytest tests/test_dialog_translation.py -q --tb=short
& $python "$env:TEMP\minijmp-g5-before-01a1594b\verify_g5_invariance.py"
```

- 最终 G5 整组专项：**73 通过，12.41 秒**。包括全部直接/真实 Dialog 报告、
  控制限列表覆盖、NaN、边界、数值/源码约束与中文窗口输出。
- G5 + G1 文本窗口/控制图及直接相关统计回归 **204 通过、8 项上述基线失败被排除**，
  7 条原有常量数据数值/绘图警告；此组运行后补充的 NaN 和控制限列表测试，
  已包含在最终 73 项专项内，其余既有回归复用本次通过结果。
- 弹窗回归 **119 通过**，细节见收尾记录。
- 首次专项运行曾 **40 通过、19 项 Tk 初始化错误**，提示无法读取已存在的
  `ttk/menubutton.tcl`。随后的文件读取与独立 `Tk()` 初始化成功，未修改系统文件或测试 fixture，
  整组复验通过；不能将这一偶发环境错误宣称为已修复。
  后续也曾在同一环境复现 `init.tcl` 读取失败（46 通过、19 项初始化错误）；
  逐一确认 Tcl 文件存在且可读、无 Tcl/Python 路径环境变量干扰、独立 Tk 初始化成功后，
  仅重跑受影响的 GUI 测试：**19 通过、46 项不相关非 GUI 测试排除**。

真实 Tk 测试覆盖九种 Dialog 的两条标识列分支，使用实际 `get_data()`、真实确定按钮及 apply，
校验全部报告、子图数量和原有取数；覆盖数值缺失清洗，保留分组有效性约束。
文本窗口复用 G1 fixture，验证中文字体分隔线的实际像素位置、480×320 窄窗双向滚动、
操作栏可见、完整文本选择、原生复制事件及 UTF-8 保存。没有修改 GUI 生产源码。
复制测试截获事件，没有覆盖用户剪贴板，未验证系统剪贴板接收端或文件选择器人工交互。

## 隔离、复杂度和 Patch Review

只操作本 G5 Worktree；不切换/清理其他 Worktree，不读取其他分支实现，不合并 G3/G4，
不执行 cherry-pick、rebase、reset，不依赖并行阶段尚未合入的代码。
开始时没有用户未提交修改。公共 `utilities.py`、`txt_output.py`、`dialog.py`，
以及 `ctrlchart_dialog.py`、`ctrl_chart_const.py` 的 SHA256 与执行前完全相同。

现有两份被修改文件保留检出时的 CRLF，新增文件采用 LF；普通 Git Diff 为局部变更。
本机 `core.autocrlf=true`，原始字节 Diff 在禁用换行转换时会把既有 CRLF 与仓库 LF 的差异计入，
不能将这项既有检出差异归因于 G5。已按工作树修改前快照核对换行，没有批量转换无关文件。
已检查 `git status`、实际 Diff 和新增文件；`git diff --check` 通过。

按 no-stop-gpt Audit 检查 helper、格式化和索引分支：三个真实调用方使用同一结构，
标量/逐点数组兼容来自现有计算契约，NaN 处理避免伪造控制限变化；
面板空集分支保留原有两个标志同时开启时的成功返回。没有报告引擎或新增算法。
常量列表按现有水平线语义每图归并一次，不在每行重复扫描，避免明细构建退化为平方级复杂度。
保留独立的类型专属说明，避免用通用模板掩盖比例、数量和单位缺陷数的差别。
最终独立只读 Patch Review 及修复复核通过，细节见收尾记录。

没有检查其他 Worktree 的未提交内容，无法确认并行分支是否触及相同文件。
未来合并时应注意 `control_chart.py` 的三个输出分支，以及 G1 文本断言的两行变更；
公共输出组件未修改，降低与 G3/G4 的交叉修改风险。

## 已有问题和范围外事项

1. `UDialog.get_data()` 无标识列时先做 `count / n`，`cu_plot()` 再除 n；有标识列时传原始 count。
   计数 1、单位数 10 时，两条分支分别绘制 0.01 和 0.1；报告忠实展示实际绘图值。
   两条实际 Dialog 路径均有测试保护，G5 没有修改该算法/取数问题。
2. NP 的直接调用可传可变 n，但原实现固定用 `nlist[0]` 缩放中心线、计数和控制限。
   GUI 仍只输入固定样本量；保留直接调用行为，并在报告明确原缩放方式，没有新增约束或修正。
3. `x_mR()` 返回 `n=2`，即使移动极差跨度不是 2。保留该返回契约，
   报告从已有生效的 `mr_range` 显示跨度，不误用 `n` 作跨度。
4. NaN、单点或空输入等原有数值失败及 Matplotlib 非有限坐标诊断均保持，未扩展清洗或容错。
5. 没有新增或运行特殊原因规则，没有验证不存在的阶段切换功能；未做其他统计模块的算法修复、
   依赖升级、启动器重构或跨操作系统 GUI 验证。

## 收尾验证与独立审查

- 修复列表覆盖后的非 GUI 专项 **54 通过、19 项 GUI 排除**；包括后来新增的八项控制限列表覆盖测试。
  常量列表归并移到逐图处理后，仅重验受影响的覆盖值和 AST：**17 通过、56 项不相关案例排除**。
  此前已通过的数值、文本窗口和 Dialog 证据按实际影响范围复用。
- 旧 `tests/test_dialog_translation.py` 完整运行：**119 通过、2 条原有弃用警告**。
  在本次 pandas 2.2.3 环境，旧 `errors='ignore'` 路径只是警告，不能视为修复了 G1/G2 在
  pandas 3.0.6 下记录的失败。
- 独立只读 Patch Review 找到一项报告兼容性问题：`lcl1=[-5.]` 等单元素列表在原绘图中
  是整条水平线，新报告原先越界。已在报告层沿用 `limit_line()` 的常量列表语义，
  覆盖两图六条线及短重复列表；短变化列表超出自身覆盖点的单元格显示 `*`，不编造控制限。
  计算、绘图和返回列表本身保持不变。
- 对该修复另做 **8 组**修改前后对照：返回结果、绘图数据及 RGBA 像素全部一致。
  合计 **108 组**对照、101 组相同结果、7 组相同既有异常、**70 张图像素完全一致**。
- 最后以实际 Tk 预检查成功的同一解释器运行整组 G5：**73 通过**，
  不仅依据分批通过结果报告完成。未改动共享环境或通过跳过测试掩盖 Tk 错误。
- 独立审查者复核八个覆盖值案例、算法 AST、实际 Diff 和本文；确认原阻塞项解决，
  没有新的阻塞问题。审查者没有重复运行完整 pytest、真实 Tk 或像素测试，
  这些证据来自主执行的上述真实验证，已区分审查与测试职责。

G5 验收完成。原有算法、异常判定缺口及环境限制保留为明确记录，未扩展为下一阶段工作。

## 后续：用户授权合并到 main

以上记录描述独立 G5 开发阶段。随后用户明确要求“合并到 main 分支”，授权提交和本地合并。

- G5 修改提交为 `0f9a766`，分支 `codex/g5-spc-control-chart-reports`。
- 合并前 main 为 `785fe297696d90fc46c432a38ec1271f5fe79fde`，工作树干净，已包含 G3/G4。
- 在 main 工作树执行非快进合并，提交 `91e649d`。没有冲突；唯一自动合并的文件为
  `tests/test_g1_debug_output.py`，同时保留 G5 两条新报告断言和 main 已有的换行一致性守卫。
  没有覆盖其他阶段内容，没有修改其他独立开发 Worktree。
- 合并后的控制图源码、G5 专项测试和 AST 基线与 G5 提交完全相同。
- 采用 main 项目配置指定的 `C:\Users\shaoy\Documents\Minijmp\.venv\Scripts\python.exe`：
  Python 3.11.9、NumPy 2.4.6、SciPy 1.15.3、pandas 3.0.6、Matplotlib 3.11.2、
  PrettyTable 3.18.0、pytest 9.1.1；没有修改环境或安装依赖。
- 合并后相关回归 **225 通过、7 条原有常量数据数值/绘图警告**，含 G5 全部 73 项、
  G1 输出窗口及控制图、直接相关统计回归和 Dialog 分析源码守卫。
  main 已有的八项换行守卫全部通过，本次没有排除测试。
- 已检查合并差异、`git diff --check` 和工作树状态。未推送远程，未运行无关全仓库测试，
  未修改已记录的 U 图取数或 NP 可变样本量算法问题。

```powershell
$python = 'C:\Users\shaoy\Documents\Minijmp\.venv\Scripts\python.exe'
& $python -m pytest tests/test_g5_spc_reports.py tests/test_g1_text_output.py tests/test_g1_debug_output.py tests/test_statistics_regressions.py tests/test_statistical_edges.py tests/test_supplemental_stability.py tests/test_dialog_translation.py::test_original_analysis_code_is_unchanged -q --tb=short
```
