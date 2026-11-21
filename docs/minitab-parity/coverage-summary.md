# MiniJMP 功能覆盖基线与 F1 分级

审计日期为 2026-11-21。仓库为 `D:\MyTools\Minijmp`，分支 `main`，源码基线 `0eadb8a`。本轮以 Minitab 22 为功能参考，历史固定数值案例仍使用 19.1.0.1。

## F0 实机核验

- 本机 COM 注册指向 `C:\Program Files\Minitab\Minitab 22\Mtb.exe`，文件版本 **22.6.0.0**。沙箱内激活返回 `0x80080005`，沙箱外 PowerShell COM 激活成功，返回 `Version=22.6`，`AppPath` 与注册路径一致。
- COM 的 Project 暴露 ExecuteCommand、Commands 和 Worksheets。UserInterface 公开成员为 DisplayAlerts、Interactive、UserControl、Visible，未发现菜单或对话框枚举接口。独立空白项目检查未通过，未执行写入命令。本轮完成了实机安装、版本和接口核验，尚未取得逐项原生命令结果或菜单与对话框证据。
- Stat 优先比较了官方 GLM、泊松率、功效、Type 1 量具、属性能力及 G 图的功能范围。Graph 新增 Graph Builder 实时预览。Data 核对了堆叠和逆堆叠。Calc 核对了随机数据及分布计算。矩阵的目标证据、22 实机证据、MiniJMP 源码及数值证据分别记录。[官方 GLM](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/anova/how-to/fit-general-linear-model/before-you-start/overview/) · [逆堆叠](https://support.minitab.com/en-us/minitab/help-and-how-to/manipulate-data-in-worksheets-columns-and-rows/supporting-topics/data-types-and-arrangements/stacked-and-unstacked-data/) · [Graph Builder](https://support.minitab.com/en-us/minitab/help-and-how-to/graphs/graph-builder/overview/)
- **F0 未完整验收。** Stat、Graph、Data、Calc 的 22.6 实际菜单、默认参数、输入模式和许可差异仍待现场确认。优先补 Q1、S1、M1 对话框和矩阵中的待核实项，包括 Calculator、工作表合并、独立子组图、Additional Tools 和 DOE GEN-013。若继续限定 COM，只能在安全的独立项目中补命令与结果；菜单位置及对话框选项需由用户在 22.6 界面提供观察记录。

## 状态与去重

| 状态 | 数量 |
| --- | ---: |
| 已实现 | 135 |
| 部分实现 | 10 |
| 未实现 | 6 |
| 待核实 | 14 |
| 不适用 | 2 |
| DOE 交叉引用 | 36 |
| 功能别名 | 5 |

[覆盖矩阵](coverage-matrix.csv) 共 208 行，新增 F0-NEW-038，原有 ID 保留。扣除 36 条 DOE 交叉引用、5 条别名后，有 167 条独立审计记录；再扣除 2 条不适用后为 165 条有效记录，其中 14 条待核实，151 条已有功能判定。DOE 的 80 个专项 ID 保留原有范围和证据，包含已实现、待核实及不适用项。部分记录为功能组，记录数量不等于厂商菜单命令总数。

## F1 结论

已将 **16 条开发缺口**分入 10 个工作包。P0 为 3 条、P1 为 9 条、P2 为 4 条。14 条待核实记录先补证。历史 19.1 数值覆盖不足及已知方法差异单独跟踪。双因子 ANOVA 按现有范围计已实现，GLM 扩展用独立 ID；容差区间保留实现状态，G07 继续验证。E01、G08、G03、E02 保留现有结论。

优先顺序为属性过程能力、泊松率推断、固定效应 GLM。F2 首包已交付二项属性能力并通过 22.6 原生 BCAPA 固定案例，Q1 中的泊松分支继续列为开发缺口。最小交付范围及独立验收见 [开发待办](development-backlog.md)。

## 验证

复用 F0 已记录的 382 项回归通过结果。F0/F1 审计轮仅变更审计文档，核对 CSV 解析、功能 ID、DOE 引用、源码与测试文件链接、去重计数及任务映射。
