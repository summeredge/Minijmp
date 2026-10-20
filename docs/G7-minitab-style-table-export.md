# G7 描述性统计表格及 Excel / PNG 导出

## 范围与交付

2026-10-20，基于 main `63f2191`。按用户后续要求直接修改 main；未提交、推送或合并，未修改 G6 worktree。最初创建的空 G7 worktree 已停止使用并归档。

已实现单变量和多变量描述性统计主表、补充统计与单变量百分位数表。每表独立 Tk 无边框块，清晰表头、中文字体、数值右对齐，使用原 Text 横纵滚动条查看宽长内容；菜单仅“导出 Excel”和“导出 PNG”。现有多变量对话框原本不输出百分位数，本次不新增该统计入口。

结构化 StatTable 包含标题、列、原始数值和显示字符串，GUI、Excel、PNG 共享该数据。其字符串值仍为原 PrettyTable 输出，普通 print_port（包括 list.append / print）保持兼容，计算、返回值和两 Dialog 的计算清洗流程均未修改。未全局解析 ASCII，其他报告仍走原 Text。

## 输出契约

Text 保留完整 ASCII 内容，仅用 elide 隐藏其显示，同时插入表格控件；表格结尾换行不隐藏。Text.get、TXT 保存、选择与原生 tk_textCopy 仍读取原文本，因此内嵌窗口没有取代表格文字。普通文字插入显式使用空标签，避免继承隐藏标签。清空同步销毁表格控件。原 save/select_all/close/to_end 保持原实现。

Excel 为 openpyxl 真实 xlsx，数值保持原精度并设置三位小数显示；N/N*/众数频数为整数显示。缺失/非有限值为 *，中文标题/标签保留，等号开头的标签强制文本，避免变为公式。

PNG 用 Pillow 根据全部行列测量并绘制，不依赖可视区域截图。标题、中文、负数和完整列已目视核对。保存取消不调用导出函数；两种导出异常均弹出“导出失败”。

## 先失败后实现与测试

使用已有 `C:\Users\shaoy\Documents\PythonEnvs\minijmp\Scripts\python.exe`，Python 3.11.9；openpyxl 3.1.5、Pillow 11.0.0、SciPy 1.14.1、pandas 2.2.3。未安装或升级依赖，未使用 Codex bundled runtime。

1. 首先新增结构化报告测试，在 stat_table 尚不存在时执行，按预期得到 ModuleNotFoundError（收集失败）。
2. 首轮实现及 G1/G2 相邻测试：81 passed。
3. 扩展专项、真实 Tk 与相邻测试：91 passed，65.67 秒，见 [targeted-tests.txt](g7-evidence/targeted-tests.txt)。覆盖 print_descriptive、print_percentiles、两 Dialog.apply、MiniJMP.print、txt_viewer、新增格式化/载体/导出/控件函数；含多变量、N*、负数、空值、补充统计、百分位数、31 列 100 行宽长表、实际读取 xlsx/PNG、菜单、取消/异常、保存、原生复制、全选、清空、关闭、滚动、重复输出与普通报告。
4. 完整 tests 回归（含 G1–G6、P1/P2）：1338 passed、9 failed、40 warnings，345.22 秒，见 [full-tests.txt](g7-evidence/full-tests.txt)。此轮收集时尚未包含最后新增的 3 项测试。
5. 9 项中的 G4 整文件旧基线守卫与本次授权修改冲突；按用户要求移除对 txt_output.py 的旧源码锁定，不增加逐方法兼容守卫。修正后该守卫及两种导出取消/异常参数化测试：3 passed，见 [final-checks.txt](g7-evidence/final-checks.txt)。未重复运行整个完整套件；复用完整回归及专项结果。
6. 其余 8 项在 HEAD 原始源码临时解包副本使用同一解释器重现：8 failed、2 passed、43 deselected，42.93 秒，见 [baseline-tests.txt](g7-evidence/baseline-tests.txt)。没有修改 main 代码来模拟基线。
7. git diff --check 通过。

既有失败精确范围：

- test_g3_chi_square_reports.py：test_independence_real_apply_routing_cleaning_and_return[raw]；test_goodness_of_fit_real_apply_probabilities_route_and_existing_results[raw/summary/normalized]。原始分类包含 None 导致排序 TypeError 或概率路由未发生。
- test_startup.py：test_windows_launchers_resolve_their_directory_and_propagate_exit_code 的 0/7 × BAT/VBS 四例；BAT 报虚拟环境未找到，VBS 超时。

以上不扩展到本次修复范围，不声称完整回归全绿。

## GUI 与导出证据

- [真实窗口截图](g7-evidence/window.png)：实际创建 Tk 结果窗口，显示主表、补充统计和百分位数；已目视检查中文、数值对齐、无网格边框及排列。截图由已有 Pillow ImageGrab 获取。
- [主表 PNG](g7-evidence/描述性统计.png)、[补充统计 PNG](g7-evidence/补充统计.png)、[百分位数 PNG](g7-evidence/百分位数.png)：逐表完整绘制，主表已目视检查。
- 同目录的三份 .xlsx 为实际导出文件；测试用 openpyxl 逐格读取标题、列、数值及类型，用 Pillow 实际读取 PNG 格式/尺寸。宽长表验证 31 列 × 100 行，PNG 高 3708 像素，不受窗口大小约束。
- [render.py](g7-evidence/render.py) 为可重复生成窗口和三个表文件的证据脚本，需从项目根目录用项目解释器执行。

使用 GUI 技能的 design 子技能、desktop-ui 与 better-interface 参考；未找到项目 DESIGN.md，沿用 Tk 现有主题。已真实 Tk 渲染，未做完整应用逐菜单人工点击验收；两 Dialog 用真实 apply 调用加数据夹具验证。

## 逐文件 Patch Review

| 文件 | 审查结论 |
| --- | --- |
| code/describe.py | 仅在两输出函数包装结构化报告，原 PrettyTable 构造、标题、清洗、计算和返回不变；所有调用点为 describe(print_out)、单变量与多变量 Dialog，共用同一出口。 |
| code/MiniJMP.py | 只对明确的 StatTable 分支调用 add_table，其余 txt+end 路径保持；没有 ASCII 正则推断。 |
| code/txt_output.py | 增加表格控件集合及清理，保留 Text 内完整文本；换行/标签继承已修正并测试；save/selection/copy/scroll/close 的原有实现保持。 |
| code/stat_table.py | 单一数据载体、现有依赖导出、原生 ttk 控件；不引入框架、后台任务、缓存、重试或新配置。Excel 标签文本处理和 GUI 异常提示有明确数据/故障边界。 |
| tests/test_g7_tables.py | 覆盖直接打印、两对话框、应用路由、真实 Tk、真实文件、全部新增函数、重复输出、普通 ASCII 与取消失败。无全局 ASCII 解析源码守卫。 |
| tests/test_g4_quality_reports.py | 按用户要求移除 txt_output 旧源码锁定，其余共享模块和算法守卫保持原样；窗口行为由 G1/G7 测试覆盖。 |
| docs/G7-minitab-style-table-export.md 与 g7-evidence | 记录实现、测试、原始失败、后续修正及证据，不把后续专项通过当作完整套件全绿。 |

执行 no-stop-gpt Audit：字符串子类由 print_port 字符串兼容性所需；Text 的 ASCII 和控件共存由保存/复制契约所需；控件集合仅用于清空销毁。删除重复 grid 调用与未用导入，没有新增不必要层次。

## 未实现与限制

仅描述性统计，不扩展其他统计报告或多变量百分位数。无新依赖安装，无统计算法修改。中文字体依赖本机字体；本机 Microsoft YaHei 已验证，其他系统缺少中文字体时需另行验证。表格使用每单元格 ttk.Label，大到数千单元格会增加 Tk 布局与内存开销；PNG 为完整单张图片，也受可用内存限制，本版未引入虚拟化或分页。

修改留在 main 工作区待用户审查，不自动提交、推送、合并。
