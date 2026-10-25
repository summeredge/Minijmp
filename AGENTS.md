# MiniJMP 项目协作规则

## 项目定位与目录

MiniJMP 是基于 Python 的桌面统计分析软件，主要使用 Tkinter、pandas、Matplotlib、Seaborn、SciPy 和 statsmodels。

- `start.py`：应用启动入口。
- `code/`：应用代码、统计计算、图形、数据处理和表格组件。
- `tests/`：自动化测试。
- `docs/`、`help/`：项目文档、帮助页面及其索引。
- `tools/`：开发和文档生成工具。
- `sample_data/`：示例数据。

以当前源码、测试和实际调用路径为准。README 或旧文档可能落后于当前实现；发现差异时先核实，不要按过时描述推断功能缺失。

## 开始修改前

1. 检查 Git 状态，识别用户已有的未提交修改；只修改当前任务需要的文件，不覆盖、撤销或顺手整理其他改动。
2. 沿真实调用路径检查相关菜单/按钮、业务实现、状态管理、输出及测试，确认目标功能是已实现、部分实现还是未实现，并判断能否复用现有实现。
3. 阅读与改动直接相关的文档和测试，不必无差别通读整个仓库。
4. 修改统计计算、数值算法或性能路径前，必须阅读根目录的 [CODING_STANDARDS.md](CODING_STANDARDS.md)；涉及关联测试、菜单、帮助文档或文件清单时，参考 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 修改原则

- 优先完成目标所需的最小改动，保持现有模块边界、接口、数据结构和用户行为；不借任务进行无关重构或整文件格式化。
- 修改前确认现有功能和约束。不要仅凭名称、注释或单个调用点推断行为，也不要新增与已有功能重复的入口。
- 保持统计方法定义、计算结果、报告字段及格式。除非任务明确要求，否则不改变公式、默认检验方法、缺失值语义或边界约定。
- 保持数据导入导出的列顺序、列名、标识符精度、缺失值、时间索引和文件格式语义。不要擅自插值、填补或将标识符强制转换为数值。
- 修改 Tkinter 界面时，检查事件绑定、窗口关闭/取消、错误提示和状态更新；涉及多工作表时，确认操作作用于当前工作表，统计对话框及图形仍关联正确的数据来源。
- 修改菜单、帮助主题或帮助正文时，同步维护关联文档、映射、搜索索引和测试预期。
- 修改 `code/pandastable_local/` 等内置或基于上游项目修改的代码时，先确认本项目的定制点，只调整必要范围并保留适用的上游署名、版权和许可证声明。
- 不无故增加依赖。未经用户明确要求，不执行破坏性清理、Git reset/checkout、提交或推送操作。

## 正确性与验证

### 统计计算和性能

- 统计正确性不能仅以“新旧结果一致”或性能提升作为依据。按照 [CODING_STANDARDS.md](CODING_STANDARDS.md)，为每个受影响的方法使用独立参考，覆盖适用的边界条件，并记录实际验证结果。
- 修复已知缺陷时，优先增加能复现旧错误的最小测试；不要通过删除冻结测试、扩大豁免或刷新错误基线来使测试通过。
- 性能优化应保留方法定义和边界行为；使用与改动规模匹配的基准或测试验证，不因微小修改无条件执行全部基准。

### 按变更范围选择测试

在 Windows PowerShell 中优先使用项目现有虚拟环境。先确认解释器存在且可用：

```powershell
$python = (Resolve-Path ".venv\Scripts\python.exe").Path
& $python -c "import sys; print(sys.executable); print(sys.version)"
```

根据实际改动选择最小充分验证：

- 多工作表、工作表状态或项目文件：`tests/test_worksheets.py`、`tests/test_sheet_context.py`、必要时 `tests/test_file_io.py`。
- 表格编辑、键盘事件或导入后的交互：`tests/test_table_regressions.py` 及对应专项测试。
- CSV、文本或 Excel 导入导出：`tests/test_csv_import.py`、`tests/test_g17_csv.py`、`tests/test_file_io.py` 中与变更相关的部分。
- PI 查询或导入：`tests/test_pi_reader.py`、`tests/test_pi_import.py`。
- 统计计算、统计报告或图形：运行受影响方法对应的测试，并根据需要补充 `tests/test_statistical_edges.py`、`tests/test_statistics_regressions.py`、`tests/test_g3_computation_contracts.py` 等相关测试。
- 菜单、帮助或帮助索引：`tests/test_menu_localization.py`、`tests/test_help_center.py`；若新增或删除 `code/` 下的 Python 文件，或修改统计报告生产位置，还需检查 `tests/test_g12_inventory.py` 及其清单。
- 涉及多个模块、共享状态、公共接口或高风险行为时，再扩大到相关回归测试或全量测试。

测试命令示例：

```powershell
& $python -m pytest tests/test_worksheets.py tests/test_sheet_context.py -q
```

不要把未执行、因环境问题无法执行或被跳过的测试描述为通过。若 Tk 图形环境、依赖或其他环境限制阻止验证，应明确报告实际限制；不要为通过测试而修改无关代码或环境配置。

## 交付要求

完成后简要说明：

1. 修改了哪些文件，以及用户可观察到的行为变化。
2. 实际执行的验证命令和结果。
3. 尚未验证的范围、已知风险或需要用户决策的事项。

结论应与实际证据一致。达到任务验收标准后停止，不追加无关重构或非必要优化。

## 更新记录
每次完成新功能开发、已有功能优化、Bug 修复或用户可见的行为调整后，必须同步更新 docs/CHANGELOG_DEV.md。

记录使用中文，以软件使用者能理解的方式描述实际变化，并按日期分类。

仅记录已经完成并经过必要验证的事项，不记录尚未实现的计划。

修改时检查已有条目，避免重复记录。

记录文件始终保留“未发布”区域，供后续版本发布时整理正式更新日志。

纯内部重构、测试调整及不影响用户行为的维护工作不要求记录。