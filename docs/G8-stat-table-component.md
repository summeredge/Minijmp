# G8 统计表格公共组件

2026-10-20，增量修改当前未提交的 G7 工作区；未提交、推送或合并。

本次生产代码仅改动 `code/stat_table.py` 和 `code/txt_output.py`。原有 G7 改动及证据均保留。
`code/describe.py`、`code/MiniJMP.py`、两个描述性统计对话框相对任务开始时未改变，未迁移其他统计模块。

## 显示及文本兼容

- `txt_viewer.add_table` 只隐藏紧邻表格、与其标题相同的普通文本行，支持 G7 的 `---- 标题 ----` 章节样式及中间空行。不跨越说明、不同章节或前一张内嵌表格。
- 隐藏使用独立的 `table_heading` 标签；原字符没有删除。`table_ascii` 继续保留并隐藏 PrettyTable 文本。普通输出显式使用空标签。
- Text、TXT 保存和原生复制仍包含完整原报告；全选、清空、横纵滚动、关闭和重新打开沿用 G7。清空删除全部文本及内嵌表格。
- 每张表使用轻量 ttk 标题栏和数据网格。原生“导出”菜单固定在标题栏左侧，标题位于其右侧；不按列数定位菜单。菜单仍只有 Excel、PNG 两项，保留取消及错误提示。

调用关系已核对：`describe(print_out=True)`、`DescribeDialog.apply`、`MultiDescribeDialog.apply` 共用 `print_descriptive`；前两者还调用 `print_percentiles`。所有表继续通过 `print_port(StatTable(...))` → `Minijmp.print` → `txt_viewer.add_table` 输出，未新增转发层。

## 公共接口

```python
from stat_table import StatTable

def output_report(print_port=print):
    print_port('命中率')
    print_port(StatTable(
        title='命中率',
        headers=['变量', '比例', 'N'],
        values=[['温度', 0.12345678, 12]],
        display=[['温度', '12.35%', '12']],
        number_formats=['General', '0.00%', '0'],
    ))
```

`print_port` 可为 `app.print`、`print`、`list.append` 等原有单参数输出端口。传给 GUI 时保留 StatTable 对象，不能提前转换为普通字符串。

完整签名：

```python
StatTable(text=None, title='', headers=(), values=(), *,
          display=None, number_formats=None)
```

| 参数/属性 | 契约 |
| --- | --- |
| `text` / `str(table)` | 可传旧 PrettyTable 字符串或对象，字符串原样保留；省略时从列名及显示字符串生成 PrettyTable，不解析 ASCII。标题独立于文本，需要 TXT 章节标题时仍由调用者照常打印。 |
| `title` | 字符串，供 GUI 和文件导出使用。 |
| `headers` | 至少一个字符串列名；自动生成 PrettyTable 时遵循其列名唯一要求。 |
| `values` | 二维原值，每行与列名等长；支持零行空表。沿用 G7 的实数、字符串和缺失值语义。 |
| `display` | 可选的二维字符串，每个单元格与原值对应；省略时使用 G7 的三位小数/计数整数格式。 |
| `number_formats` | 可选的逐列 Excel 格式字符串；默认 N、N*、众数频数为 `0`，其余为 `0.000`。不改变原值精度。 |

旧的 `StatTable(text, title, headers, values)` 调用保持兼容。无列名、行宽不符、显示数据形状不符、非字符串显示单元格或数字格式数量不符时抛出 `ValueError` / `TypeError`，避免 `zip` 静默截断。构造器复制输入序列；构造完成后调用者应将这些属性作为只读数据使用。

`export_excel(table, filename)`、`export_png(table, filename)` 可独立使用，不依赖 GUI 窗口。Excel 保留有限实数原值，None/NaN/Inf 显示为 `*`，等号开头标签保持文本；PNG 使用全部列宽和全部行绘制标题及数据，不使用窗口截图。已有项目依赖没有变化。

## 验证结果

使用项目启动器指定且有效的 `.venv/Scripts/python.exe`：Python 3.11.9，pandas 3.0.6，SciPy 1.15.3，openpyxl 3.1.5，Pillow 13.0.0；均符合当前 requirements。未创建环境、安装或升级依赖，未使用 Codex bundled runtime。此环境与 G7 文档中使用的共享环境不同，G8 基线在本次修改之前用当前项目环境采集。

1. 修改前 G7 表格及 G1 Text 专项：25 passed。
2. 六组完整 G7 文本在修改前保存至 `tests/fixtures/g8_g7_text.json`：直接函数、多变量、仅补充统计、百分位数、单变量对话框、多变量对话框。新增标题测试先复现失败；最终 Text 内容与 TXT 保存内容逐字符匹配此固定基线，不在测试中重建预期值。
3. [受影响回归](g8-evidence/regression-tests.txt)：399 passed，7 warnings，79.10 秒。包括 G7、G8、G1 文本及统计输出、G2 基础报告、表格/统计回归、统计边界、补充稳定性和 G4 共享模块守卫。警告来自既有常数数据的统计/坐标轴检查。
4. 首轮布局检查在 480×320 窗口将不可见宽表当作当前横向滚动范围，出现 1 项失败，见 [首轮记录](g8-evidence/first-pass-tests.txt)。Tk 的横向范围随可见行变化，已改为先滚到宽表再验证横向滚动；上述 399 项已包含修正后的检查。
5. 视觉复核移除原生菜单的重复箭头后，[最终检查](g8-evidence/final-checks.txt)：7 passed，9.69 秒。包含 2/10/31 列位置、最小/大窗口、双倍 DPI、菜单实际生成 Excel/PNG 和取消/异常。这 7 项中 3 项为回归收集后新增，4 项为受按钮文字变更影响的复测；合计覆盖 402 个不同用例。
6. Excel 实际写入再用 openpyxl 读取，检查完整行列、中文、数值类型及原精度、整数/三位小数/百分比格式、缺失值及公式标签。PNG 实际写入再用 Pillow 读取，覆盖标题区域、100 行末单元格和 G7 的 31 列×100 行宽长表。菜单成功路径仅替换文件选择对话框，执行真实导出函数。
7. 原生复制调用真实 `tk_textCopy` 并截获其 clipboard 参数，确认隐藏的 ASCII 和章节标题均保留；没有覆盖用户系统剪贴板。
8. 实际生成并目视核对 [完整结果窗口](g8-evidence/window.png)、[480 像素窄窗的不同列数菜单](g8-evidence/menus-narrow.png) 及三张导出 PNG。菜单位置记录为 `[48, 48, 48]`；底栏、滚动条均可见。GUI 技能使用 design 子技能及 desktop-ui、better-interface、better-layout、better-ui、accessibility 参考；未找到项目 DESIGN.md，沿用现有 ttk 主题。
9. `git diff --check` 及新增文件空白检查通过。未重新运行无关的整个 tests 套件，不将本次结果表述为全仓库全绿。G7 文档中的历史全量失败不作为当前环境的已复现结论。

复现本次回归：

```powershell
$python = 'C:\Users\shaoy\Documents\Minijmp\.venv\Scripts\python.exe'
& $python -m pytest tests/test_g8_tables.py tests/test_g7_tables.py tests/test_g1_text_output.py tests/test_g1_statistics_output.py tests/test_g2_basic_reports.py tests/test_table_regressions.py tests/test_statistics_regressions.py tests/test_statistical_edges.py tests/test_supplemental_stability.py tests/test_g4_quality_reports.py::test_shared_modules_and_plot_implementations_remain_at_baseline -q
& $python docs/g8-evidence/render.py
```

现在执行上面的完整命令会包含后补的 3 项。证据脚本在此 Windows/Pillow 13 环境用原生窗口捕获，避免 DPI 虚拟坐标裁切截图。

## 完整 Patch Review 与复杂度审查

[G8 生产代码增量](g8-evidence/g8-increment.patch) 以任务开始时的未提交 G7 实现为比较基准。审查同时覆盖当前 tracked diff 和相关 untracked 源码/测试，未把原有 G7 改动当作本次新增。

| 范围 | 结论 |
| --- | --- |
| `stat_table.py` | 保留单一字符串载体，增加显示字符串/逐列格式和必要形状校验。Excel 只改为读取载体格式；PNG 绘制逻辑未改。两个原生 Frame 分离标题栏与数据网格，修复共享列布局根因。 |
| `txt_output.py` | 仅增加紧邻标题隐藏。使用 Text 当前内容，无报告缓存、标题登记状态或全局 ASCII 推断；窗口检查防止连续输出时隐藏上一表。保存/选择/清空/关闭代码没有 G8 修改。 |
| `describe.py`、`MiniJMP.py` | 与 G8 开始时字节完全相同；G7 的原有路由改动保留。SHA256 分别为 `710ab0b75930752aa72160da52df926ab017cd494d1b19f52d0198797ab69852` 和 `bb56e2bfd79ec1f4e8e7cda36948b0390dd2231cc2a97de1142fd8049df8d77c`。 |
| 对话框及全部调用点 | 现有入口均复用组件，未更改选项、清洗、计算或返回值；没有只修复单一入口。 |
| G7 测试及 G4 守卫 | 本次未修改，均保留；G4 旧守卫的既有 G7 调整也保持。 |
| G8 测试、固定文本夹具、证据脚本及文档 | 覆盖独立 API、异常、零行空表、缺失、中文、连续输出、复制、真实文件和几何位置；原有 G7 已覆盖的故障测试直接复用。 |

no-stop-gpt Audit 结论：逐列格式有百分比导出的实际消费者；形状检查保护公共输入不丢数据；两个 Frame 各自承担标题/数据布局。未增加适配器、注册表、配置、fallback、缓存、后台任务或大型依赖，没有需保留的冗余层。

## 未解决问题及验证边界

未发现本次 G8 范围内尚未解决的失败。未逐项人工点击完整主程序菜单；两个真实 Dialog.apply 入口、应用路由和实际 Tk 控件均已自动验证。未在其他操作系统/缺少中文字体的设备上验证。

沿用 G7 的每单元格 Label 和整张 PNG：极大表仍受 Tk 控件数量及内存限制。本次验证到 31 列×100 行，不添加虚拟化、分页或其他统计模块迁移。
