# G17：数据处理与 pandas 3 兼容性优化

日期：2026-10-21（Asia/Shanghai）。基于 G15 的 F05/F09；开始 HEAD 为 `38b907f0dcf62f234561838f3cca93ad0a8545ef`。不升级依赖，不修改文件格式，不提交、推送或合并。

## 变更与实际调用链

| 文件 / 路径 | 调用与原语义 | G17 修改 |
| --- | --- | --- |
| `code/df_combine.py::df_combine` | 主表 `MTable.paste`、`paste_header`、`stackColumn` 共用；按位置覆盖，第二表优先，重置为 RangeIndex，新增列名仍为 C 序号 | 按列读取 `Series.array`，用对象矩阵传输列，最终按原构造器推断各列；保留 NumPy 标量类型、缺口 NaN、重复列名与负偏移的既有索引行为 |
| `code/dialog.py::findRepDialog.find` | `MTable.findText` 创建此覆盖类；整格匹配，非正则；忽略大小写使用 Unicode `upper()`；纯 ASCII 空格单元格不匹配；坐标为 `(列, 行)`，按行排序 | 独立布尔 mask，按列比较，`np.nonzero` 生成坐标；不向 pandas 字符串列写布尔值 |
| `code/pandastable_local/dialogs.py::FindReplaceDialog.find` | `core_orig.Table.findText` 与 `core.Table` 使用此基类；合并预览表也使用 `core.Table`；保留正则包含匹配及 `(行, 列)` 坐标 | 按列生成 mask，删除逐行 `iterrows/iteritems`；修复 pandas 3 已移除 `Series.iteritems()` 的兼容错误；按位置处理重复列名 |
| `code/utilities.py::number_2Dlist` | `fit_dialog.MCorDialog`、`chi2_dialog.Chi2TableDialog` 的多变量数值准备；Python `float()` 规则，完整有效行过滤，原样本顺序，返回转置列表 | 列只选择一次，迭代列数组进行 `float()`，一次构建数值矩阵后过滤 NaN；保留下划线、Unicode 数字、Decimal、布尔、无穷值及 NumPy 复数的既有转换/警告 |
| `code/pandastable_local/csv_import.py::detect_csv` | 主表继承 `core_orig.Table.importCSV`；检测不确定时进入 `CSVPreviewDialog` | 成功解码只做一次；复用本次检测中已完整校验的选中分隔符记录；按列对不同文本做数字判断，复用首行分类 |
| 同文件 `read_csv` | 自动导入、预览与正式导入都调用；每次重新读取文件 | 空串清洗一次；首个非空值保留文本短路；NumPy 对象数组中的不同文本只做一次主体数值资格判断；仍使用原 `pd.to_numeric` 和溢出/缺失检查 |

覆盖层核对：`MTable → pandastable_local.core.Table → core_orig.Table`；`TableModel → data_orig.TableModel`。后者不会再复制或解析传入 DataFrame。基类 `paste` 是整表替换，主表覆盖层 `paste` 才是偏移合并，两者语义不同，未强行统一。菜单“合并”继承 `doCombine → CombineDialog.apply → pd.merge/pd.concat`，已经批量处理，不是 `df_combine` 的重复实现，未改变 join、索引及后缀规则。继承的未使用 `Table.merge` 不是菜单实际入口，本次未扩展修复它。

CSV 仍按 comma/tab/semicolon/pipe 的原优先顺序尝试完整严格解析，保留编码回退、歧义确认、全文件行宽、NUL、坏引号、空文件、非法表头与数字精度保护。检测与正式导入之间可能改文件或选项，预览到点击导入期间也可能改文件，因此没有跨调用缓存；正式读取仍重新校验全文件。

## 一致性与兼容性验证

- `tests/fixtures/g17_before.json` 冻结 G15 的 7 个函数，独立 Review 确认其 AST 与开始 HEAD 一致。参考函数只用于测试/基准，不进入生产调用链。
- `tests/test_g17_data_processing.py`：123 项，覆盖两表覆盖顺序、原索引到 RangeIndex、空表/零列/零行、重复列名、正负偏移、空补丁的越界负列偏移、超长无符号整数、混合/nullable/日期 dtype、10 种窄 NumPy dtype、NumPy 复数清洗及警告；两类查找的空白、Unicode 大小写、缺失值、字面正则符号、坐标；实际 MTable 粘贴/表头路径、Tk 查找高亮重绘与堆叠；基准有效样本及失败记录约束。
- `tests/test_g17_csv.py`：71 项，覆盖 BOM/非 BOM UTF-8、UTF-16 大小端、GB18030、CP1252、四分隔符/歧义、前导零/长整数/指数溢出/本地化数字/空值、尾部损坏、非法编码/空文件/重复表头，以及检测后文件变更时重新读取。原 CSV UI 测试继续验证导入失败和取消时不替换工作表。
- 热点约束：合并、数字清洗及两类查找禁止重新出现 `iloc/iat/iterrows/iteritems`；MTable 三个消费者必须继续调用共享 `df_combine`；CSV 对每次检测的分隔符解析次数、成功解码次数和重复文本数值判断次数设置工作量上限。数字清洗仍逐值执行 `float()`，以保持已有输入规则；消除的是 pandas 逐格选择和重复派发。
- 附加 12 组 Categorical、Decimal、Period、Interval、嵌套对象与偏移差分一致，见 `g17-evidence/extra-dtype-probe.txt`。
- 三个旧整文件 AST 守卫仅放行本次已授权的 `number_2Dlist` / `findRepDialog.find`，其他统计计算、对话框和绘图源码约束继续保留。没有重置统计结果夹具。

项目环境：`C:\Users\shaoy\Documents\Minijmp\.venv\Scripts\python.exe`，Python 3.11.9、pandas 3.0.6、NumPy 2.4.6。未安装或升级任何依赖。

测试证据：

| 验证 | 结果 / 文件 |
| --- | --- |
| 初次相关测试，含旧 CSV 和表格回归 | 275 passed，`g17-evidence/targeted.txt` |
| 最终 G17、原 CSV 及表格回归 | 365 passed，`g17-evidence/final-targeted.txt` |
| dtype 修复后的数据路径复测 | 122 passed，`g17-evidence/final-data-retest.txt` |
| 最终 CSV 与原 CSV 测试 | 112 passed，`g17-evidence/csv-final-targeted.txt` |
| CSV 专项与 G12 清单 | 86 passed，`g17-evidence/csv-inventory-retest.txt` |
| 独立冻结源码的完整修改前 pytest | 1768 passed、53 warnings，`g17-evidence/baseline-frozen-pytest.txt` |
| 最终 G17 隔离补丁完整 pytest | 1962 passed、53 warnings，387.96 秒；`g17-evidence/final-frozen-pytest.txt` |

完整测试使用同一项目解释器。并行 G16 正在主目录修改其他统计模块及共享测试守卫，因此分别用开始 HEAD 的只读源码快照、该快照加明确列出的 G17 文件运行全套，避免把其他任务的结果归给本任务。三份共享测试从 HEAD 仅叠加 G17 守卫调整，不复制 G16 后续修改。`scoped-files.txt` 与 `verification.json` 记录 G17 快照文件集合和 SHA256；5 份生产源码及 G17 独占测试/工具与主目录一致，共享测试文件的并行差异单列记录。快照中的 Git 只读查询通过 `GIT_DIR` 指向原仓库，未建立或移动分支。

最初直接在共享目录启动的全套得到 1765 passed / 3 failed：运行期间源码守卫读到了本次已修改的 `utilities.py`，所以这不是可信的修改前基线，也不被标记为既有失败，保留在 `baseline-pytest.txt`。首次最终快照测试在 Review 修复后主动停止，日志为 `interrupted-first-final-pytest.txt`；不计作通过结果。随后一轮 1961 passed 见 `first-green-final-pytest.txt`，仍早于最后的空补丁边界修复。`interrupted-shared-guards-pytest.txt` 则是重建纯 G17 共享守卫前主动中止的一轮，亦不作为最终结果。

## 性能对比

复用 G15 固定种子 `20261021`、场景开始时消耗的 `normal(10,1,n)` 向量、输入构造、`perf_counter/process_time`、GC 后计时及预热排除口径。合并为 n×5 表加前 10% 行，在 `y=n//2` 覆盖；清洗为 n×5 数值表，并复测 1 万行×20/40 列；查找为 n×5 的 `[0,100)` 整数表，搜索 `42`；CSV 为 n×10 正态数值 UTF-8 文件。

每个前后版本 1 次预热和 3 次正式测量，交替执行顺序；输入构造、文件写入、结果对比不计时。最终汇总只纳入完成完整 DataFrame（含 dtype/轴）或列表/坐标一致性校验的记录。基准工具现已改为每对校验通过才保存成功记录，并通过强制注入不一致结果确认不会留下成功样本；未变查找的首轮原始样本虽较早落盘，但其随后校验及完整场景均成功。

原查找在 pandas 3 无法有效运行，不能以异常退出耗时作分母。整格查找参考版仅把旧 `found` 容器改为 object；基类参考版仅把 `iteritems` 改为 `items`。下表查找收益均相对于这两份**仅修兼容的旧算法**，并非 G15 原查找已成功测量。真实旧代码的 TypeError 另有回归复现。

最终共 **26 个场景、208 条记录，其中 156 条正式样本**，每个前后版本都恰好 3 条有效正式样本；函数 SHA 与最终源码一致。汇总为 `g17-evidence/performance-final-summary.json`；逐次 wall/CPU、预热标记和测量来源为 `performance-final.csv`。G15 历史结果另存 `g15-historical-summary.csv`，未拿历史绝对时间直接计算本轮加速比。

中位数，单位秒；括号为前/后的比值：

| 路径 / 列数 | 1 千行 | 1 万行 | 5 万行 | 10 万行 |
| --- | --- | --- | --- | --- |
| 合并 / 5 | 0.0564 → 0.0024（23.18×） | 0.5897 → 0.0189（31.23×） | 3.4351 → 0.0904（37.98×） | 6.1234 → 0.2053（29.83×） |
| 数字清洗 / 5 | 0.1335 → 0.0033（40.24×） | 1.0259 → 0.0220（46.59×） | 3.4188 → 0.1247（27.42×） | 10.0264 → 0.3137（31.96×） |
| 整格查找 / 5 | 0.4850 → 0.0027（178.61×） | 4.1235 → 0.0082（504.71×） | 29.7727 → 0.0460（646.94×） | 58.5174 → 0.0917（637.82×） |
| 基类正则查找 / 5 | 0.0186 → 0.0056（3.33×） | 0.1379 → 0.0141（9.81×） | 0.7566 → 0.0676（11.19×） | 1.9106 → 0.1746（10.94×） |
| CSV 检测 / 10 | 0.0110 → 0.0082（1.35×） | 0.1157 → 0.0883（1.31×） | 1.2596 → 1.0474（1.20×） | 1.8581 → 1.4803（1.26×） |
| CSV 读取 / 10 | 0.0206 → 0.0197（1.05×） | 0.1432 → 0.1419（1.01×） | 0.8291 → 0.7513（1.10×） | 2.0512 → 1.8194（1.13×） |

1 万行×20 列清洗为 3.9297 → 0.0887 秒（44.31×）；×40 列为 7.6731 → 0.1658 秒（46.29×）。CSV 读取在 1 千/1 万行接近测量噪声，不宣称显著提升。CSV 两阶段分别计时，未把它们直接相加作为真实端到端导入测量。

同一 Windows 桌面存在 G16、完整测试等后台负载，绝对耗时明显高于 G15 的部分历史样本；本轮用前后交替配对降低漂移，但未宣称隔离硬件、统计显著性或精确可迁移倍数。没有把程序内部耗时解释为真实剪贴板、Tk 绘制或磁盘冷启动性能，也没有进行独立峰值内存基准。

首轮 CSV 读取使用 `present.unique()`，高基数数据有回退。探针指出 pandas 3 StringArray 迭代封装开销，最终改为 NumPy 对象数组唯一值扫描并保留首值文本短路；修复后四种规模均复测。首轮结果保留以便追溯，不能替代 `performance-final.csv`。合并/清洗在窄 dtype 与复数修复后也已重新完成三次有效测量；未变的查找测量按函数 SHA 复用。

复现：

```powershell
$python = 'C:\Users\shaoy\Documents\Minijmp\.venv\Scripts\python.exe'
$env:PYTHONHASHSEED = '0'
# 使用新的输出目录，避免覆盖本次验收证据。
& $python tools/benchmark_data_processing.py --output "$env:TEMP\Minijmp-G17-rerun"
# 仅相关代码变化时复测，例如 CSV：
& $python tools/benchmark_data_processing.py --cases csv_detect csv_read --output "$env:TEMP\Minijmp-G17-csv-rerun"
& $python -m pytest tests/test_g17_data_processing.py tests/test_g17_csv.py tests/test_csv_import.py tests/test_table_regressions.py -q --tb=short
& $python -m pytest -q --tb=short
```

## Patch Review 与复杂度审查

已逐文件审查 5 份生产源码、2 份新回归测试、3 份旧守卫调整、冻结函数夹具和基准工具。独立 Review 首轮发现三项：窄 NumPy dtype 装箱、复数清洗行为、基准先落成功记录再校验；已全部修复，并补对应回归。复核另发现空补丁遇越界负列偏移时的 P3 差异，也已修复并通过 3 组差分。最终独立 Review 通过，无未解决项。`g17-evidence/g17.patch` 为相对开始 HEAD 的纯 G17 源码/测试/工具补丁，不包含 G16 的共享文件修改；在原始源码快照上 `git apply --check --whitespace=error` 通过，未应用补丁。

no-stop-gpt Audit：保留对象矩阵与最后 `tolist()`，因为需要按原 DataFrame 构造方式推断 dtype；按列 `Series.array` 是避免标量类型丢失的必要实现。保留逐值 `float()`，不以 `pd.to_numeric` 替换不同的输入语义。CSV 的解码/记录/不同文本复用均在调用内；跨调用重新校验对应文件和用户选项可变化的边界，不删除。未新增缓存框架、泛化 helper、依赖、后台状态或兼容层。

## 验收边界

本次兼容验证环境为 pandas 3.0.6，未另外安装 pandas 2 环境。真实系统剪贴板未读写，粘贴解析入口通过桩验证，查找、高亮与堆叠已经过真实 Tk 控件。完整 pytest 的 G17 结论对应隔离补丁快照，不包含正在并行修改的 G16 统计补丁；没有修改或撤销其他任务文件。
