# pandas 3.0.6 迁移兼容与验收报告

日期：2026-10-27

## 基线与正式环境

- beta.3 源码基线：`d21a924abf6f437f82e2736ac09c5a38dc636d5f`（`main` 与 `origin/main` 起始时一致，工作区干净）。
- 验收解释器：项目 `.venv`，Python 3.11.9 x64。
- 实际版本：pandas 3.0.6、NumPy 2.4.6、SciPy 1.15.3、Matplotlib 3.11.2、statsmodels 0.15.0。
- `requirements.txt` 现固定 `pandas==3.0.6`；`packaging/windows/requirements-py311.lock` 已固定相同版本，其他锁定依赖未升级。
- `tools/release_env.py` 检查通过：Python/位数、锁文件依赖、`pip check` 与 PyInstaller 版本均匹配。

## 缺陷与修复

### P0：防止数据精度损失和部分写入

- `code/pandastable_local/data_orig.py`、`data.py`、`code/modified_table.py`：pandas 3 对非空数值列写入缺失值或异类型值时可能拒绝赋值，也可能在旧写入路径中把整数列提升为浮点数。现先验证并暂存受影响列，再统一提交；安全转换失败会报错且不留下部分写入。支持整数、无符号整数、可空数值/布尔、文本、类别和日期时间列的明确转换规则，公式结果列继续禁止手动覆盖。
- 清空整型单元格时使用可空整数/布尔 dtype，避免未选中单元格因整列转成 float64 而丢失大整数精度。清除、粘贴、上移、向下填充和替换均使用相同的类型检查与原子写入路径。
- `code/pandastable_local/csv_import.py`、`dialogs.py`、`code/worksheets.py`：CSV 数值推断以十进制精度比较，保留超过 `2^53` 的整数、高精度小数、科学计数文本及带前导零的标识符；预览与完整导入共用规则。Excel 多工作表继续导入；`.xlsx` 会从工作表 XML 恢复读取引擎已舍入的原始数值 token。
- `code/pi_import.py` 将 PI 时间频率的小写日单位规范为 pandas 接受的大写单位。`code/pi_reader.py` 的 object 中间列和 `Decimal` 精度保护保持不变。

### P1/P2：pandas 及绘图依赖兼容

- `code/pandastable_local/core_orig.py`：缺失值前向/后向填充改用 `ffill`/`bfill`；颜色映射按 pandas dtype API 识别字符串、布尔和类别列，类别先编码，空值与常量列保持可绘图；日期转换按 Force 开关保留旧错误处理语义，周序号改用 ISO 周 API；移除无调用私有方法里的 `convert_objects()`。
- `code/pandastable_local/stats.py`：Series 参数遍历改为 `items()`。聚合/透视相关入口显式设置 `observed`，避免 pandas 3 默认值变更意外改变分类分组结果。
- `code/pandastable_local/plotting.py`：类别绘图明确采用已验证的分组口径；使用 Matplotlib 3.11 支持的 colormap API。通用绘图器不再把当前 80 DPI 写入进程级 `savefig.dpi`；自身保存仍显式传入所选 DPI，其他统计图不会继承该设置。

统计公式、检验方法、报告算法和工作表公式定义没有修改。分类聚合输出显式保持既有包含未观测类别的行为；绘图分组保留既有只画观测类别的行为。

## 修改文件

- 运行代码：`code/dialog.py`、`code/modified_table.py`、`code/pi_import.py`、`code/worksheets.py`、`code/pandastable_local/core_orig.py`、`code/pandastable_local/csv_import.py`、`code/pandastable_local/data.py`、`code/pandastable_local/data_orig.py`、`code/pandastable_local/dialogs.py`、`code/pandastable_local/plotting.py`、`code/pandastable_local/stats.py`。
- 依赖与文档：`requirements.txt`、`README.md`、`PACKAGING.md`、`docs/CHANGELOG_DEV.md`、`docs/release/v0.1.0-beta.3-baseline.md`、本报告 `docs/release/pandas3-migration-report.md`。
- 回归测试：`tests/test_context_clipboard.py`、`test_file_io.py`、`test_g17_csv.py`、`test_g17_data_processing.py`、`test_g21_plotter.py`、`test_g3_regression_reports.py`、`test_g4_quality_reports.py`、`test_review_data_safety.py`、`test_table_regressions.py`、`test_worksheet_formulas.py`、`test_dialog_translation.py`（仅收尾归一化）。
- 项目记忆：`.agent-memory/MEMORY.md`、`.agent-memory/logs/2026-10-27.md`。

## 验证记录

所有命令均使用项目 `.venv\Scripts\python.exe` 对应的 Python 3.11.9 / pandas 3.0.6 环境。

| 范围 | 实际命令或文件 | 结果 |
|---|---|---|
| 发布环境 | `python tools/release_env.py` | PASS；锁文件、`pip check`、PyInstaller 均匹配 |
| 大整数性能合同 | `pytest tests/test_g18_performance.py::test_prepare_keeps_native_arrays_and_exact_nullable_values -q` | 4 passed |
| 第一层：表格、剪贴板、CSV/Excel、PI | `pytest tests/test_table_regressions.py tests/test_context_clipboard.py tests/test_review_data_safety.py tests/test_g17_data_processing.py tests/test_file_io.py tests/test_pi_reader.py tests/test_pi_import.py -q` | 473 passed |
| 第二层：工作表与公式 | `pytest tests/test_worksheet_formulas.py tests/test_worksheets.py tests/test_sheet_context.py tests/test_plotter_roles.py -q` | 70 passed，1 warning |
| 第三层：绘图与时间序列 | `pytest tests/test_g21_plotter.py tests/test_phase1_plots.py tests/test_g6_chart_presentation.py tests/test_plot_window_lifecycle.py tests/test_g13_time_series.py -q` | 202 passed，34 warnings |
| DPI 回归及受影响图像输出 | `pytest tests/test_g21_plotter.py tests/test_quality_tools.py tests/test_regression_plots.py tests/test_time_series_analysis_plots.py -q --tb=short` | 180 passed；覆盖通用绘图器、质量图、回归图和时间序列图 |
| 第四层统计专项 | PCA、PLS、回归、ANOVA、时间序列、SPC、能力分析及质量工具对应测试 | 1,800 passed；初次另有 1 项 AST 快照断言失败，调整仅对 `dialog.py` 的既有查找替换变更做归一化后，相关 3 项聚焦测试通过 |
| 冻结 AST 守卫与 Pearson 开关 | `pytest tests/test_dialog_translation.py::test_original_analysis_code_is_unchanged -q`；`pytest tests/test_g2_basic_reports.py tests/test_g3_regression_reports.py tests/test_statistics_regressions.py -q` | 1 passed；153 passed，12 warnings |
| 全量回归（收尾） | `pytest -q --tb=short` | **3,810 passed，0 failed，0 skipped，120 warnings（978.26 秒）** |

收尾前的全量记录为 3,807 passed、1 failed、120 warnings。唯一失败是冻结守卫 `tests/test_dialog_translation.py::test_original_analysis_code_is_unchanged`：它把 `code/fit_dialog.py` 与历史快照 `87281643b7fd0caaedb50ff561720b221c489a07` 比较，而当前 `CorrelationDialog.apply` 含提交 `8f84dfb`（REVIEW-017）加入的 `pearson=self.cor_p.get()`，旧快照没有该关键字。`fit_dialog.py` 相对迁移起点 `d21a924` 无改动，故这是快照滞后，不是 pandas 迁移回归。

修复只在测试侧：为 `CorrelationDialog.apply` 增加定点归一化，先在 `CorrelationDialog` 内断言唯一 `fit_plot` 调用、位置参数为 `x, y`、`pearson` 恰在 `alpha` 与 `ellipse` 之间、值为 `self.cor_p.get()`，再移除该关键字后与冻结 AST 全量比较。归一一经掩盖 `fit_dialog` 后又暴露同一函数内的第二处历史差异：`CpkSubDialog.apply` 的 REVIEW-018（子组元素少于 2 时建图前拒绝）与 REVIEW-019（分组按首次出现顺序）。该处复用既有 `normalize_p1/p2` 守卫的整函数 SHA256（`tests/fixtures/p2_guard_nodes.json`）后还原，属已审查历史修复，无其他统计行为变化。新旧快照未改，测试未删除或跳过。

负向核验：把 `pearson` 改为 `False`、删除该关键字、把分组改为排序、移除子组守卫，守卫均拒绝；临时改动已还原。`tests/test_g3_regression_reports.py` 新增 `test_correlation_dialog_forwards_pearson_switch` 两例，确认 Pearson 开/关时传给 `fit_plot()` 的关键字分别为 `True` / `False`，并同步影响 `ellipse`、`print_out`。

此前全量中的 40 个图像尺寸失败来自绘图器将 80 DPI 写入全局 Matplotlib 配置；移除该副作用后，全量重跑和上述 180 项图像回归均通过。

120 条警告主要来自小样本/退化数据的 SciPy 与 statsmodels 警告、Matplotlib/Seaborn 弃用提示、测试环境缺少中文字体，以及既有绘图布局提示；没有测试因警告被跳过。

## 限制

- `.xls` 使用旧式 Excel 数值存储，底层为双精度数值，无法像 `.xlsx` XML 一样恢复已丢失的超精度原始数字文本；该格式中的标识符应以文本单元格保存。
- PI 测试使用合成数据；未连接实际 PI Server。未构建 EXE/ZIP，也未进行办公终端的 Defender、DLP 或普通用户权限验收。
- 旧 `.dexpl`/`.pickle` 的读取和保存恢复由现有工程与工作表测试覆盖；未对外部用户工程文件做人工抽样验收。
- 未提交、未创建标签、未推送。
