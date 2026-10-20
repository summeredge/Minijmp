# G11 质量分析表格与独立导出

2026-10-20，工作树 `C:\Users\shaoy\.codex\worktrees\b28a\Minijmp`，
基线 `63f2191`，开始时工作树干净。没有提交、推送或合并。

## 公共组件来源

本工作树基线尚无 G7/G8。复用 `C:\Users\shaoy\Documents\Minijmp` 中已有、未提交的
G7/G8 `stat_table.py`、`txt_output.py`，原样复制到本工作树；仅将该工作区
`Minijmp.print` 的 StatTable 分流应用到当前同名方法，没有复制其他主程序改动。
没有改动来源工作区，也没有迁移描述性统计或合并其他任务。

复制时及验证后的 SHA256：

| 文件 | SHA256 |
| --- | --- |
| `code/stat_table.py` | `CAD9D9B7EDD1BC915F6E56FAAB876E6A9E52B76139A76B09884ECE9A169AE3EC` |
| `code/txt_output.py` | `CDA0489237FC557E725F60E6154668377BBAF134A2E21BD632A2DF33FFF51BAF` |

沿用公共接口 `StatTable(text, title, headers, values, display=..., number_formats=...)`、
`export_excel`、`export_png`、`TableBlock`。没有质量分析专用导出器、适配框架或新依赖。
后续整合 G7/G8 时，这两份相同文件是公共前置实现，不应另保留一套副本。
本仓库及上级目录未找到适用的 `DESIGN.md`；本任务没有重新设计控件，原样沿用 G8 组件。

## 报告生产清单与迁移状态

所有表均经原 `print_port` 传递 StatTable 对象到 `Minijmp.print → txt_viewer.add_table`。
命令行 `print`、`list.append`、TXT 保存和普通文本消费者继续使用原字符串协议。

| 具体文件 / 生产函数 | 实际调用入口 | 表格、结构与状态 |
| --- | --- | --- |
| `code/GRR.py::_grr_tables` 第一出口 | `GRR_xbar`、`grr_anova_AIAG`、`grr_anova_EMP`、`grr_nested` | 方差分量；3 列，行数由各方法原 components 决定；已迁移 |
| `code/GRR.py::_grr_tables` 第二出口 | 同上四个方法 | 研究变异/分量标准差；EMP 2 列，其余基础 4 列，历史 SD 与规格公差各增加 1 列；已迁移 |
| `code/GRR.py::GRR_xbar` | 直接 DataFrame、自定义列名；`grr_xbar_r → GRR_xbar`；`grr_master(mode=Xbar)`；`GRRDialog.apply` | 两张表全部使用上述共享出口，保留有/无操作者差异；已迁移，无遗漏副本 |
| `code/GRR.py::grr_anova_AIAG` | 直接调用；`grr_master → GRRDialog.apply` | 两张共享表，含总 GRR、EV、AV、操作者、保留交互、PV、总变异；已迁移 |
| `code/GRR.py::grr_anova_EMP` 第一独立出口 | 直接调用；`grr_master(mode=EMP) → GRRDialog.apply` | EMP 补充统计；3 列，基础 3 行，有操作者/交互分别增加 2 行；已迁移 |
| `code/GRR.py::grr_anova_EMP` 第二独立出口 | 同上 | 原有 EMP 分类参考；5 列 × 4 行，范围与概率均保留原字符串；已迁移 |
| `code/GRR.py::grr_master` | `GRRDialog.apply` 及直接调用 | Auto 且有操作者时的完整模型交互筛选 ANOVA；6 列 × 5 行；On/Off 不新增该表；已迁移 |
| `code/GRR.py::grr_nested` | `GRR_Nested_Dialog.apply` 及直接调用 | 嵌套 ANOVA；6 列 × 4 行，加上两张共享表；历史 SD 的使用/拒绝路径均保留；已迁移 |
| `code/GRR.py::grr_xbar_r` | `grr_master` 及直接调用 | 仅整理 DataFrame 并转交 GRR_xbar，没有独立表格副本 |
| `code/GRR.py::grr_inter / grr_simple / grr_no_op` | AIAG/EMP 计算路径 | 调用公共 ANOVA 时 `print_out=False`，无独立报告表，不新增输出 |
| `code/cpk.py::cpk` | `CpkDialog.apply / CpkSubDialog.apply → cpk_plot → cpk`，亦可直接调用 | 样本/规格/波动汇总；1 行、7 或 9 列；已迁移 |
| `code/cpk.py::cpk_calc` | `cpk` 的组内/整体路径及直接调用 | Cp/Cpk/Cpl/Cpu/Cpm 或 Pp/Ppk/Ppl/Ppu/Cpm，含原置信上下限；4 列 × 5 行；已迁移 |
| `code/cpk.py::nonconformance` | `cpk` 及直接调用 | 实际观测/组内正态预测/整体正态预测；4 列 × 2 或 3 行，单位为百分数；已迁移 |
| `code/control_chart.py::_print_spc_report` 汇总出口 | `x_plot / p_np_plot / cu_plot` 三条实际输出路径 | 图表、LCL、CL、UCL；4 列，每个实际显示面板 1 行；已迁移 |
| `code/control_chart.py::_print_spc_report` 明细出口 | 同上，每个面板分别调用 | 点号、原标签、原样本量/检查单位数、统计值、LCL、CL、UCL；7 列，每个原观测 1 行；全部已迁移 |
| `code/control_chart.py::x_plot` | `IMRDialog / IDialog / MRDialog / XBRDialog / XBSDialog.apply` | I-MR、I、MR、Xbar-R、Xbar-S；汇总和每个选中面板明细全部转交上述出口 |
| `code/control_chart.py::p_np_plot` | `PDialog / NPDialog.apply` | P、NP；固定/可变样本量，估计/指定控制限均转交上述出口；P1/P2 的逐点缩放保持 |
| `code/control_chart.py::cu_plot` | `CDialog / UDialog.apply` | C、U；固定/可变检查单位数，估计/指定控制限均转交上述出口；U 只在原位置归一化一次 |
| `code/control_chart.py` 异常点 | 三类图表报告的“特殊原因及异常点”节 | 当前没有规则判定、异常索引或明细表；保留原说明文本，不补造异常标记、阈值或“无异常”结论 |
| `code/qc_dialog.py` | 能力、GRR 及容差对话框 | 本次只读；标签、警告、数据清洗和参数透传保持，不存在独立质量表格副本；容差区间不在此次清单内 |
| `code/ctrlchart_dialog.py` | 上述全部 SPC 对话框 | 本次只读；没有独立表格生产函数，继续传 `self.app.print` |
| `code/cpk_plot.py / grr_plot.py` | 两类质量绘图入口 | 本次只读；能力图透传 print_port，GRR 图本身不生产报告表 |

合计迁移 11 个实际表格构造位置：GRR 6 处、能力分析 3 处、SPC 2 处。
共享出口的所有实际消费者均覆盖，未按函数名只选择一个方法或副本。

## 数值与文本契约

- 原 PrettyTable 构造与格式保持，作为 StatTable 的 `text`；旧章节、说明、警告、分类、ndc、
  假设及结论仍是普通文本。TXT 的表格边框与数值舍入逐字符对照固定 Git 基线。
- `values` 明确使用原计算的未舍入值，不从 ASCII 或格式化字符串反解析。
  `display` 与原表逐格一致；表头、百分数单位、6 x SD、分类字符串及 `*` 均保留。
- Excel 真实数值单元格保存原浮点数，不先截为三位小数或六位有效数字；
  浮点写入按 Excel/openpyxl 原有约 15 位有效数字能力处理，不承诺超出 Excel 精度。
  已按百分数缩放的表使用普通数值格式，避免 Excel 再乘 100。
- PNG 沿用公共组件的显示精度，以完整标题、全部行列生成整张图片，不截取可见窗口。
  SPC 在 GUI/PNG/TXT 沿用原六位有效数字，GRR/能力沿用原三位小数。
- 方差、标准差、比例、控制限、规格限、置信区间、返回键/类型、样本量及判异状态均不改变。
  控制限变化摘要仍写“逐点变化（见明细）”；常量列表、短变化列表及移动极差前导缺失的原语义保留。
- 没有新增物理单位输入或推断：标准差仍继承输入单位、方差仍为其平方。

## 逐文件旧输出检查与保留原因

限定搜索七个目标文件的 `gen_table`、`PrettyTable`、`print(str(...))`、`print_port(str(...))`：

| 文件 | 遗留模式与原因 |
| --- | --- |
| `GRR.py` | 6 个 `gen_table` 保留以生成完全相同的 TXT，出口均包装 StatTable；无直接 `print(str(table))` |
| `cpk.py` | 3 个 `gen_table` 同上；无遗漏文本表出口 |
| `control_chart.py` | 2 个 `gen_table` 同上；三个调用路径共用已迁移出口；异常说明保留普通文本 |
| `qc_dialog.py` | 无该类独立表；分析变量、警告仍为普通文本 |
| `ctrlchart_dialog.py` | 无独立表；输入提示和清洗消息不迁移 |
| `cpk_plot.py` | 无独立表；只保留原绘图及报告透传 |
| `grr_plot.py` | 无独立表；仅有原图形逻辑 |

没有删除 gen_table 来破坏 TXT 兼容，也没有增加 ASCII 自动识别路由。
统计容差区间 `ti.py`、公共 ANOVA 及其他统计模块均保持原样。

## 验证与证据

项目已有共享环境 `C:\Users\shaoy\Documents\PythonEnvs\minijmp\Scripts\python.exe`：
Python 3.11.9、NumPy 2.1.2、SciPy 1.14.1、pandas 2.2.3、openpyxl 3.1.5、
Pillow 11.0.0、pytest 9.1.1，满足 requirements。已确认解释器及 SciPy 实际导入路径，
没有使用 Codex bundled runtime，没有安装、升级或迁移依赖。

G11 新专项包含：

1. 56 组真实报告对照固定 `63f2191` 原函数，递归比较返回值和完整 TXT；
   每张表实际写 Excel/PNG，再读取行列、表头、全部数值单元格、格式和末行图像内容。
2. 47 组 GRR/能力原值对照：从原提交的表格构造表达式中移除显示舍入，
   逐格比较原值与新增 `values`；不从当前实现重算预期值。
3. 9 类 SPC 对照原提交实际送入报告的所有点值、原标签、样本量及三条控制限。
4. 短/常量控制限、缺失、中文和原精度；GRR 零总方差、零历史 SD、零规格公差。
5. 四类真实 Tk 报告经过 `Minijmp.print`、内嵌表格、真实导出菜单、完整 TXT 保存、窄窗操作栏和清空；
   Excel/PNG 的取消和失败仍走同一公共组件。
6. 两份对话框、两份质量绘图、chart_style、utilities、公共 ANOVA 与当前基线全文一致。

首轮组合回归：513 passed、6 failed、25 warnings。
6 项均来自新测试解包原报告时漏处理 `rows[1] += ...`，误将两列预期原值保留为字符串；
修正测试 AST 提取范围，没有为该失败改动生产代码，也没有放宽浮点数或返回类型比较。
其余 G4、G5、G6、P1/P2、G1 检查全部通过。

最终 G11 专项：**122 passed，51.47 秒**，无警告。
与首轮已通过、其后生产代码和相关测试均未改变的 **410 项既有回归**合计，
分批累计 **532 个不同用例通过**，没有遗留失败。没有重复运行无变化的既有回归或无关全仓库测试。
首轮 25 条警告来自 G6 矩阵图的原特征值平方根数值路径，以及 fit_dialog 的 tight_layout 弃用；
本次未修改这些代码。

原始日志：[首轮组合](g11-evidence/first-regression-tests.txt)、
[最终 G11 专项](g11-evidence/final-g11-tests.txt)。
最终专项已包含补强后的全部表头/显示字符串逐格对照、9 类 SPC 原值对照和两种导出的取消/失败。
真实导出 PNG 已目视核对宽列 GRR 评价表和可变样本量 NP 明细：中文、首末列与全部行完整可读。
`git diff --check` 通过；新文件另做语法和尾随空白检查。

```powershell
$python = 'C:\Users\shaoy\Documents\PythonEnvs\minijmp\Scripts\python.exe'
& $python -m pytest tests/test_g11_quality_tables.py tests/test_g4_quality_reports.py tests/test_g5_spc_reports.py tests/test_p1_p2_statistical_fixes.py tests/test_g6_quality_charts.py tests/test_g6_chart_presentation.py tests/test_g1_text_output.py -q --tb=short
& $python docs/g11-evidence/render.py
```

`g11-evidence` 提供 7 份可复查 Excel、7 份 PNG 和对应完整 TXT，以及可重跑生成脚本。
分别覆盖 GRR 方差分量、测量系统评价、EMP、嵌套 ANOVA、能力指数、U 和 NP。

## 复杂度审查与边界

使用 no-stop-gpt Audit 核对实际 diff 和消费者：

- 复用已有公共组件；没有新框架、注册表、缓存、fallback、依赖或导出系统。
- 旧显示行与新原值行分别保留，用于 TXT 逐字符兼容及 Excel 原精度；
  不通过字符串解析猜测数值。全部映射有原提交表达式及真实文件对照。
- SPC 原控制限摘要拆出 `raw_summary`，由旧文本摘要和新原值摘要两个实际消费者共用，
  避免另复制控制限变化判定；未增加新的统计/判异算法。
- G4 旧共享源码守卫仅移除已授权替换的 txt_output；其他守卫不变，
  输出行为由 G1/G11 的真实 Tk/TXT/菜单检查覆盖。

没有逐菜单人工操作完整主程序，也没有验证其他操作系统字体。
沿用公共组件的逐单元格控件与完整 PNG，超大表仍受 Tk/图像内存限制。
没有虚拟化、分页、额外判异规则或新增统计方法。

## 后续：用户授权合并到 main

用户随后明确要求“合并到main”，授权提交与本地合并；本节更新前文独立开发阶段的未提交状态。

- G11 原始实现提交为 `0265ee0`，分支 `codex/g11-quality-table-export`。
- 合并前 main 为 `fc9215e0b7bb58d560754ff65607b2241d7ff7dc`，工作区干净，已包含 G7–G10。
  公共 stat_table、txt_output 及 Minijmp.print 与 G11 所用版本一致，无生产冲突或重复实现。
- 唯一文本冲突位于 G4 测试的一行注释；合并后的注释同时列出 G1/G10/G11，
  完整保留 main 已有的 G9 ANOVA、G10 utilities 计算守卫。
- G11 全文保护测试对 utilities、两份公共 ANOVA 采用该 main 提交作为固定基线，
  其余质量对话框与绘图文件仍对照原基线；没有放宽为忽略这些共享文件。
- 相对 main 的生产改动仅为 GRR.py、cpk.py、control_chart.py；公共输出组件没有变化。
- 在 main 的项目指定环境 `.venv/Scripts/python.exe` 验证：Python 3.11.9、NumPy 2.4.6、
  SciPy 1.15.3、pandas 3.0.6、openpyxl 3.1.5、Pillow 13.0.0；核实实际解释器及依赖路径，
  没有安装或调整依赖。
- 合并内容完整回归：**728 passed、32 warnings，244.14 秒**，覆盖 G11、G4/G5/G6、P1/P2、
  G1 文本窗口及 G7/G8/G9/G10；包含真实 Excel/PNG、TXT、Tk 与 U/NP 保护。
  警告来自已有统计边界、常量数据及弃用路径，没有失败。
- [合并回归原始日志](g11-evidence/main-merge-tests.txt)。`git diff --check` 通过。
  没有运行无关全仓库测试，没有推送远程。

```powershell
$python = 'C:\Users\shaoy\Documents\Minijmp\.venv\Scripts\python.exe'
& $python -m pytest tests/test_g11_quality_tables.py tests/test_g4_quality_reports.py tests/test_g5_spc_reports.py tests/test_p1_p2_statistical_fixes.py tests/test_g6_quality_charts.py tests/test_g6_chart_presentation.py tests/test_g1_text_output.py tests/test_g7_tables.py tests/test_g8_tables.py tests/test_g9_tables.py tests/test_g10_tables.py -q --tb=short
```
