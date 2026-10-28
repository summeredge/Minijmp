# 工作包 B 收尾报告（B1～B4）

> 联合工作区的当前状态与本轮回归见 [B+C 联合收尾](work-package-bc-review-closeout.md)。以下隔离 worktree 记录是历史执行环境；四项修复已进入当前工作区。本地测试通过不等于独立 LRM Review 通过。

## 2026-10-28 最终 Review 阻断修复（当前）

本轮只在隔离 worktree 修复 B 的代码与测试，未触碰主工作区 C0 文件；未提交、未推送、未重置历史。修复四项确定性问题：

- CCD 重复校验从每个分类组合的非中心点数推导重复数，再按完整预期结构核验点类型、轴点、编码、区组、中心点编号及元数据。5 因子 half、6 中心点在 1/2/3 次重复时分别有 32/58/84 行设计；移除轴点、改重复号、编码或中心点元数据均被拒绝。
- 区组 CCD 中心点默认值为自动计算并在预览/元数据展示；显式整数只接受布局要求的数量，错误输入不创建工作表。连续因子数、分数和区组切换后自动值按当前布局重算。
- CCD/BBD 在分类组合或运行列表展开前估算总行数；超过 10,000 拒绝，恰好 10,000 允许。
- 分类响应面图仅提供连续 X/Y 轴；分类水平使用只读下拉框并传入 TermModel.row，标题显示真实水平及参考区组。真实 Tk 测试用独立解析模型核对网格预测与水平切换后的曲面变化。

ACC-021 与 ACC-024 已按本轮相关的创建/分析范围恢复本地验收；ACC-022A/B、ACC-023、ACC-025～030 的既有结论在本轮回归中保持。ACC-022B 仅限五份用户提供并确认版本为 Minitab 22 的配置：点多重集及区组重编号后的点–区组多重集相同，标准序不同 60/116/123/120/163 行，不外推。正式完成仍需网页端独立 Review 的可验证通过记录。

五份 CSV 的表格内容未改。仓库 .gitattributes 将行尾规范为 LF；对标测试在需要时从 LF 还原原始 CRLF 字节并按 manifest 的原始字节数与 SHA-256 校验。

### 本轮回归

解释器为主工作区项目 .venv（Python 3.11.9），当前目录为 B 隔离 worktree。各组存在重叠，不合计。

```powershell
& 'C:\Users\shaoy\Documents\Minijmp\.venv\Scripts\python.exe' -m pytest tests/test_doe_core.py tests/test_doe_factorial.py tests/test_doe_analysis.py tests/test_doe_fractional.py tests/test_doe_fractional_analysis.py tests/test_doe_ccd.py tests/test_doe_ccd_options.py tests/test_doe_rsm.py tests/test_doe_rsm_categorical.py tests/test_doe_rsm_diagnostics.py tests/test_doe_predict.py tests/test_doe_overlay.py tests/test_doe_optimize.py tests/test_doe_bbd.py tests/test_doe_schema_v2.py tests/test_doe_persistence.py -q --tb=short
# 308 passed；0 failed，0 skipped，0 warnings

& 'C:\Users\shaoy\Documents\Minijmp\.venv\Scripts\python.exe' -m pytest tests/test_doe_bbd_minitab_parity.py tests/test_doe_bbd.py -q --tb=short
# 62 passed；0 failed，0 skipped，0 warnings

& 'C:\Users\shaoy\Documents\Minijmp\.venv\Scripts\python.exe' -m pytest tests/test_doe_bbd_gui.py tests/test_doe_ccd_options_gui.py tests/test_doe_rsm_gui.py tests/test_doe_optimize_gui.py tests/test_doe_gui.py tests/test_doe_fractional_gui.py tests/test_doe_predict_gui.py tests/test_doe_overlay_gui.py -q --tb=short
# 69 passed；0 failed，0 skipped，11 个 Matplotlib tight_layout 警告

& 'C:\Users\shaoy\Documents\Minijmp\.venv\Scripts\python.exe' -m pytest tests/test_menu_localization.py tests/test_help_center.py -q --tb=short
# 79 passed；0 failed，0 skipped，0 warnings

为确保编码输入与实际低/高水平不同，该分类响应面 Tk 用例改用 A=10..20、B=100..200，并再次运行：
& 'C:\Users\shaoy\Documents\Minijmp\.venv\Scripts\python.exe' -m pytest tests/test_doe_rsm_gui.py -q --tb=short -k categorical_rsm_plot_uses_selected_level_and_continuous_axes
# 1 passed，10 deselected，1 个 Matplotlib tight_layout 警告
```

未运行全量 pytest（既有 Windows Tk 原生崩溃风险）；开发日志已合入 CCD 中心点、分类响应面绘图和运行数上限条目。本轮未修改帮助页或索引；help/pages/doe.html 与 help/assets/search-index.js 仍由 C0 更新，需协调合并 B 规则说明后统一重建帮助索引。


## 2026-10-28 Minitab 22 五份参考审计

用户提供并确认版本为 Minitab 22 的 9 因子无区组/5/10 区组和 10 因子无区组/2 区组 CSV 表格内容已纳入 fixture；manifest 记录原始 SHA-256 和字节数，测试对 Git 行尾规范化作还原后校验。独立审计及逐项比较见 [BBD 参考核验](bbd-reference-validation.md)：五份点多重集和映射后的逐点区组分配均相同；标准序不同。ACC-022A 本地通过；ACC-022B 对这些特定参考及设置的数学等价通过，不能宣称标准序精确一致或推及其他版本。CSV 软件来源来自用户陈述。独立 Review 尚未提交或通过，不进入工作包 C。

本轮实际命令（项目 `.venv` Python 3.11.9，测试组重叠）：

```powershell
& .\.venv\Scripts\python.exe -m pytest tests/test_doe_bbd_minitab_parity.py -q --tb=short
# 12 passed
& .\.venv\Scripts\python.exe -m pytest tests/test_doe_bbd_minitab_parity.py tests/test_doe_bbd.py tests/test_doe_rsm_categorical.py tests/test_doe_optimize.py tests/test_doe_schema_v2.py tests/test_doe_persistence.py -q --tb=short
# 140 passed
& .\.venv\Scripts\python.exe -m pytest tests/test_doe_bbd_gui.py tests/test_doe_optimize_gui.py -q --tb=short
# 19 passed, 1 warning (Matplotlib tight_layout)
& .\.venv\Scripts\python.exe -m pytest tests/test_menu_localization.py tests/test_help_center.py -q --tb=short
# 79 passed
& .\.venv\Scripts\python.exe tools/build_help_index.py
& .\.venv\Scripts\python.exe -m pytest tests/test_doe_bbd_minitab_parity.py tests/test_menu_localization.py tests/test_help_center.py -q --tb=short
# 91 passed（帮助更新及索引重建后）
& .\.venv\Scripts\python.exe -m pytest tests/test_doe_bbd_minitab_parity.py -q --tb=short
# 13 passed（新增英文表头及无区组列兼容测试后）
```

以下双层验收实施阶段中的 ACC-022B 待外部参考描述为历史状态，由本节取代。

> 本页首部记录最终修复与当前验收状态。下方旧阶段报告、ACC 状态表、测试结果及 C 启动条件均为历史记录；其中“BBD 未实现”“ACC-022B pending”等旧结论已被本页首部和 BBD 参考核验当前结果取代。

## 历史记录：2026-10-28 双层验收实现进展（取得参考前）

用户批准 ACC-022A 数学及工程验收与 ACC-022B Minitab 逐点一致性分开；前者为 Level 1 功能 Review 条件，后者 `pending_external_reference`，父编号不变。9/10 因子 BBD 已按 Box–Behnken (1960) 表 4 构造，支持 9 因子 1/5/10 区组、10 因子 1/2 区组；8 因子拒绝。参考及独立构造见 [BBD 参考核验](bbd-reference-validation.md)。ACC-022A 本地验证通过，RSM-002 为 implemented；独立 Review 尚未提交或通过，ACC-022B 未证实，不进入工作包 C。

当前实测：9/10 因子各 55/66 列完整二次矩阵满秩、条件数分别约 7.076/8.299；5/10/2 区组中心化指示列与完整二次模型正交。独立解析响应验证系数、预测、区组偏移及带独立重复的纯误差分解；高维单/多响应优化与真实 Tk 优化图通过。五种高维配置真实 Tk 完成预览、创建、保存、关闭、重开、复制、分析与预测；640×480 按钮和非法区组拒绝通过。

本轮命令与结果（各组有重叠，不相加；`deselected` 不计通过）：

```powershell
& .\.venv\Scripts\python.exe -m pytest tests/test_doe_bbd.py tests/test_doe_ccd.py tests/test_doe_ccd_options.py tests/test_doe_rsm.py tests/test_doe_rsm_categorical.py tests/test_doe_rsm_diagnostics.py tests/test_doe_predict.py tests/test_doe_optimize.py tests/test_doe_schema_v2.py tests/test_doe_persistence.py -q --tb=short
# 193 passed；此后增加测试，未改核心数值实现
& .\.venv\Scripts\python.exe -m pytest tests/test_doe_bbd.py tests/test_doe_optimize.py tests/test_doe_rsm_categorical.py tests/test_doe_rsm_diagnostics.py tests/test_doe_schema_v2.py tests/test_doe_persistence.py -q --tb=short
# 132 passed；其后扩展现有系数断言，专项 3 passed
& .\.venv\Scripts\python.exe -m pytest tests/test_doe_bbd_gui.py tests/test_doe_ccd_options_gui.py tests/test_doe_optimize_gui.py -q --tb=short
# 30 passed, 1 warning
& .\.venv\Scripts\python.exe -m pytest tests/test_doe_core.py tests/test_doe_factorial.py tests/test_doe_analysis.py tests/test_doe_fractional.py tests/test_doe_ccd.py tests/test_doe_ccd_options.py tests/test_doe_rsm.py tests/test_doe_predict.py tests/test_doe_overlay.py -q --tb=short
# 147 passed
& .\.venv\Scripts\python.exe -m pytest tests/test_menu_localization.py tests/test_help_center.py tests/test_g12_inventory.py tests/test_worksheets.py tests/test_sheet_context.py tests/test_file_io.py -q --tb=short
# 163 passed
```

首次 GUI 预测测试误将实际水平 0.5 作为编码值 0.5，五项失败；将实际输入改为 0.75 后重跑通过。全部结果均为本次运行，无未解释失败；未运行全量 pytest。

补充验证发现 BBD 显式中心点与重复/分类组合的公共合同不一致，旧实现对新测试 3 项失败；修复后以下套件通过。分类组合下每次重复保留单独中心点，旧版 schema 的字段名称和数据形态不变。

```powershell
& .\.venv\Scripts\python.exe -m pytest tests/test_doe_bbd.py tests/test_doe_schema_v2.py tests/test_doe_core.py tests/test_doe_persistence.py -q --tb=short
# 95 passed
& .\.venv\Scripts\python.exe -m pytest tests/test_doe_bbd.py -k categorical_pure_error -q --tb=short
# 1 passed, 41 deselected
& .\.venv\Scripts\python.exe -m pytest tests/test_doe_bbd_gui.py tests/test_doe_ccd_options_gui.py tests/test_doe_optimize_gui.py tests/test_doe_rsm_gui.py -q --tb=short
# 39 passed, 3 warnings
```

按双层合同，本地 ACC-021、022A、023–030 的已支持范围通过，ACC-022B pending_external_reference；软件功能验收结论不等于独立 Review APPROVE。当前可用连接器没有发起网页端 Review 的接口；检查可用网页端会话时 computer-use 初始化失败（`failed to write kernel assets: 系统找不到指定的路径。 (os error 3)`），因此尚未提交，需由网页端发起独立 Review。

公共 DOE 合同修复后补跑受影响的旧功能回归：

```powershell
& .\.venv\Scripts\python.exe -m pytest tests/test_doe_factorial.py tests/test_doe_analysis.py tests/test_doe_fractional.py tests/test_doe_ccd.py tests/test_doe_ccd_options.py tests/test_doe_rsm.py tests/test_doe_rsm_categorical.py tests/test_doe_rsm_diagnostics.py tests/test_doe_predict.py tests/test_doe_overlay.py tests/test_doe_optimize.py -q --tb=short
# 187 passed，0 failed，0 skipped，0 warnings
```

后续再次检查 computer-use 的另一初始化入口，仍返回同一 `failed to write kernel assets` 路径错误；没有创建 Review 请求。

## 历史记录：高维 CCD 工程验收与 BBD 参考（2026-10-28）

本节保留双层验收合同修订前的状态及证据，其中关于 9/10 因子 BBD 未实现、ACC-022 partial 和不提交 Review 的描述已被本文开头的“双层验收实现进展”取代。

本次是原工作包 B 的后续补全。原关联：Goal `goal-712216c8-e5ed-4b5b-8aab-a2ea89a84047`，Task `task-d2937ac6-7867-4014-bedc-67e5e850defc`，Execution `goal-execution-ed824efd458bad14970af66ee773e8b6`，Review Request `auto-review-84217312dbf50b498200551a29bb7fcf`，Review Result `result-78832f8a-a61f-480c-a010-822732698c7c`。原执行 passed，但 Review 的协议确认超时；本次没有修改或重启原 Goal。新任务所在 Codex chat 为 `01a17fa7-e815-74f2-a784-e5fe6bde23e7`；本地 Goal 工具未提供独立的新 Task/Execution 标识。

`tests/test_doe_rsm_gui.py::test_high_dimension_ccd_project_lifecycle` 通过真实 Tk 创建 6 全因子、8 half、9 quarter、10 eighth 的 CCF；预览不创建表，填写解析二次响应，保存 `.dexpl`，以新建工程关闭原表，重开后核对 schema、完整表数据、设计元数据、输入指纹、响应映射、无区组、编码往返，复制工作表并从副本重新分析，拟合值与解析响应一致。高维 CCD 的这部分缺口已补齐，ACC-021 在当前实现范围内通过；未证明未列出的设计组合。

Box 与 Behnken 原始论文提供 9/10 因子正交区组构造，另找到 Crosier 10 因子两区组公开矩阵；这些资料未能证明 Minitab 的逐点设计及分组等价。五份所需导出、实际来源、数学边界见 [BBD 参考核验](bbd-reference-validation.md)。9/10 因子 BBD 均未实现，ACC-022 仍 partial；其余 ACC-023–030 在现有支持范围内通过，9/10 因子 BBD 范围仍无法验收。不进入工作包 C，不提交最终 Review。

本轮指定解释器 `.venv` Python 3.11.9；实际命令与结果（各组不相加）：

```powershell
& .\.venv\Scripts\python.exe -m pytest tests/test_doe_rsm_gui.py -k high_dimension_ccd_project_lifecycle -q --tb=short
# 4 passed, 5 deselected
& .\.venv\Scripts\python.exe -m pytest tests/test_doe_bbd.py tests/test_doe_ccd.py tests/test_doe_ccd_options.py tests/test_doe_rsm.py tests/test_doe_rsm_categorical.py tests/test_doe_rsm_diagnostics.py tests/test_doe_predict.py tests/test_doe_optimize.py tests/test_doe_schema_v2.py tests/test_doe_persistence.py -q --tb=short
# 181 passed
& .\.venv\Scripts\python.exe -m pytest tests/test_doe_bbd_gui.py tests/test_doe_ccd_options_gui.py tests/test_doe_rsm_gui.py tests/test_doe_optimize_gui.py -q --tb=short
# 30 passed, 3 warnings (Matplotlib tight_layout)
& .\.venv\Scripts\python.exe -m pytest tests/test_menu_localization.py tests/test_help_center.py tests/test_g12_inventory.py tests/test_worksheets.py tests/test_sheet_context.py tests/test_file_io.py -q --tb=short
# 163 passed
```

以上运行均无失败、无跳过；`deselected` 指过滤而非通过。全量 pytest 未运行。

## 历史记录：2026-10-28 第二轮修复（五份参考与最终修复前）

当前基线 main b60c6eaca57495690b0c65ed500b97d4ffd87533。CCD 窗口可选至 10 因子；分类 CCD 预览及 CCC 轴点确认只对连续因子计算轴点。超过 5 个自由因子的优化使用中心、两个对角边界及逐轴边界起点，9/10 因子分别 21/23 起点，单起点函数评价上限 200。解析二次响应的 CCD 9/10 因子测试核对最优点、预测及重现性。无全局最优保证。

| 验收 | 本轮状态及范围 |
| --- | --- |
| ACC-021 | partial：6/8/9/10 因子真实 Tk 创建与预览通过；高维保存重开及窗口尺寸交互未独立验证。 |
| ACC-022 | partial：3–7 因子原回归通过；未获 9/10 因子官方矩阵和区组分配，不生成且不宣称等价。 |
| ACC-023、024、030 | partial：原分类与区组回归通过；新 BBD 因子类型不存在，未能验收该范围。 |
| ACC-025、026、027 | partial：现有核心与 GUI 回归通过；9/10 因子 BBD 范围无法验证。 |
| ACC-028、029 | partial：低维原回归及高维 CCD 解析案例通过；高维 BBD 尚不可用。 |

本轮 .venv 验证：DOE 核心/统计/schema/持久化 14 文件 241 passed；DOE GUI 8 文件 51 passed、10 warnings；菜单、帮助、G12、工作表和文件 6 文件 163 passed。帮助索引更新后菜单、帮助、G12 94 passed；补充的 640×480 按钮及非法分数 GUI 文件 11 passed；补充函数评价硬上限后优化文件 50 passed。各组有重叠，不能相加为独立测试数。所有结果均为本轮运行，未运行全量 pytest。具体命令以最终交付说明为准。下一步取得 Minitab 9/10 因子实际设计表及各区组分配后，建立独立 fixture 并完成缺失验收，不进入工作包 C。

实际命令（PowerShell，仓库根目录；无失败或跳过，警告如上）：

```powershell
& .\.venv\Scripts\python.exe -m pytest tests/test_doe_core.py tests/test_doe_factorial.py tests/test_doe_fractional.py tests/test_doe_ccd.py tests/test_doe_ccd_options.py tests/test_doe_bbd.py tests/test_doe_rsm.py tests/test_doe_rsm_categorical.py tests/test_doe_rsm_diagnostics.py tests/test_doe_predict.py tests/test_doe_overlay.py tests/test_doe_optimize.py tests/test_doe_schema_v2.py tests/test_doe_persistence.py -q --tb=short
& .\.venv\Scripts\python.exe -m pytest tests/test_doe_gui.py tests/test_doe_rsm_gui.py tests/test_doe_bbd_gui.py tests/test_doe_ccd_options_gui.py tests/test_doe_predict_gui.py tests/test_doe_overlay_gui.py tests/test_doe_optimize_gui.py tests/test_doe_fractional_gui.py -q --tb=short
& .\.venv\Scripts\python.exe -m pytest tests/test_menu_localization.py tests/test_help_center.py tests/test_g12_inventory.py tests/test_worksheets.py tests/test_sheet_context.py tests/test_file_io.py -q --tb=short
& .\.venv\Scripts\python.exe tools/build_help_index.py
& .\.venv\Scripts\python.exe -m pytest tests/test_help_center.py tests/test_menu_localization.py tests/test_g12_inventory.py -q --tb=short
& .\.venv\Scripts\python.exe -m pytest tests/test_doe_ccd_options_gui.py -q --tb=short
& .\.venv\Scripts\python.exe -m pytest tests/test_doe_optimize.py -q --tb=short
```

> 2026-10-28 Review 修复及当前验收状态见文末；本报告原有结论为历史记录。

## 历史记录：一、基线与范围

- 仓库 `C:\Users\shaoy\Documents\Minijmp`，分支 `main`，起始 HEAD `8c126ba`；工作区保持未提交，未推送、未打标签。
- 解释器 `.venv\Scripts\python.exe`（Python 3.11.9、pandas 3.0.6、NumPy 2.4.6、SciPy 1.15.3）。
- 内部分阶段：B1 schema 兼容与 BBD，B2 CCD 选项/区组/分类因子，B3 模型项/预测/叠加等高线，B4 优化扩展、诊断与 GUI 回归。
- 不进入工作包 C；未实现 PB、DSD、split-plot、自定义 RSM、D-optimal、混料、Taguchi、二元响应与预测区间。

## 历史记录：二、阶段完成情况

### B1 Schema v2 与 Box–Behnken

- `DOE_SCHEMA_VERSION = 2`，可读版本 `{1, 2}`；v1 工程读取后在校验时升级为 v2，摘要按实际存储的设计字典核对，旧工程不因新增字段失配。
- 新增 `box_behnken` 设计类型与 `edge` 点类型，新增 `ccd_fraction`、`block_count` 字段；分类因子与区组仅允许出现在 CCD/BBD。
- `code/doe_bbd.py`：3–7 因子、每对因子 ±1 的边点加中心点、官方运行数（15/27/46/54/62）、区组划分、分类组合展开、设定/编码/点类型/重复/区组一致性与满秩校验。
- 旧版软件不能读取 v2 工程；本次不做双向兼容承诺。

### B2 CCD 选项、区组与分类因子

- CCD 支持全因子/1/2/1/4/1/8 分数、区组与自定义 alpha；单区组默认 `F^(1/4)`，多区组使用官方正交 alpha 公式，结果与官方三位小数一致。
- CCF 与区组不兼容、无法复现正交性的区组组合（7 half 5 区组、8 quarter 3/5 区组、9 quarter 5 区组、10 eighth 3/5 区组）显式拒绝，不生成。
- 区组进入模型作为参考水平哑变量（列名自“区组2”），区组项与因子项分开报告；区组分配改变模型与自由度，不只是标签。
- 分类因子使用 k−1 参考水平哑变量，每个水平各有中心点；分类平方项与分类间交互拒绝，分类×连续交互支持。

### B3 模型项、点预测与叠加等高线

- `code/doe_rsm_model.py::TermModel` 统一编译模型项、分类哑变量与区组列，供拟合、预测、绘图、优化共用。
- 模型项层级强制：平方项需一阶项、交互项需两个主效应；未知项、重复项、越层级与秩亏拒绝，不自动删项。
- `code/doe_predict.py::predict_point` 与 `code/doe_predict_dialog.py::PredictRSM`（菜单“08响应面预测”）：实际水平输入、分类水平选择、参考区组、快照标识；缺因子、未知因子、越界、缺失响应、元数据变化均拒绝。
- `code/doe_overlay.py::overlay_contours` 与 `code/doe_overlay_dialog.py::OverlayContours`（菜单“09叠加等高线”）：至少两个响应各自上下限、两个绘图因子、其余固定、分类切片、可行交集与无交集提示。
- 可行区域是各响应范围的网格交集，不使用优化候选点冒充。

### B4 优化扩展、诊断与 GUI 回归

- `optimize_rsm` 接受 CCD 与 BBD，分类水平固定切片，区组按参考区组评估；候选复核使用与拟合相同的 `TermModel` 与系数。
- 项平方和改为对所有可拟合模型计算（不再依赖推断），并新增“诊断可用性”结果页：系数推断、项平方和、项 F、纯误差、失拟、曲率、残差图逐项给出可用状态与原因。
- 未重复或纯误差为零时不给失拟、曲率 F/p 或系数推断，不虚构显著性。
- 菜单、帮助、帮助索引、G12 清单与变更日志同步。

## 历史记录：三、ACC-021～030 验收表

| 验收编号 | 能力 | 证据 | 结论 |
| --- | --- | --- | --- |
| ACC-021 | CCD 扩展 | `tests/test_doe_ccd_options.py`（10）、`tests/test_doe_ccd_options_gui.py`（4）、`tests/test_doe_ccd.py`（41） | 通过（实现范围内） |
| ACC-022 | Box–Behnken | `tests/test_doe_bbd.py`（21）、`tests/test_doe_bbd_gui.py`（3） | 通过（3–7 因子） |
| ACC-023 | 区组 RSM | `tests/test_doe_rsm_categorical.py`（6）、`tests/test_doe_ccd_options.py`、`tests/test_doe_bbd.py` 区组用例 | 通过（实现范围内） |
| ACC-024 | 分类因子 RSM | `tests/test_doe_rsm_categorical.py`（6）、`tests/test_doe_ccd_options_gui.py` | 通过（参考水平哑变量） |
| ACC-025 | 模型项选择 | `tests/test_doe_bbd.py` 项选择/层级/秩亏用例 | 通过 |
| ACC-026 | 点预测 | `tests/test_doe_predict.py`（9）、`tests/test_doe_predict_gui.py`（6） | 通过；无区间（RSM-009 仍 unknown） |
| ACC-027 | 多响应叠加等高线 | `tests/test_doe_overlay.py`（6）、`tests/test_doe_overlay_gui.py`（4） | 通过 |
| ACC-028 | 单响应优化 | `tests/test_doe_optimize.py`（47）、`tests/test_doe_optimize_gui.py`（5） | 通过；无全局最优声明 |
| ACC-029 | 多响应优化 | 同上，多响应期望/权重/零期望/下溢用例 | 通过 |
| ACC-030 | 统计诊断 | `tests/test_doe_rsm_diagnostics.py`（7）、`tests/test_doe_bbd_gui.py` 诊断页断言 | 通过；残差图不作假设证明 |

## 历史记录：四、实际执行的验证

| 命令 | 结果 |
| --- | --- |
| 核心专项 16 个文件（core/persistence/schema_v2/factorial/analysis/fractional/ccd/ccd_options/bbd/rsm/rsm_categorical/rsm_diagnostics/predict/overlay/optimize） | 263 passed |
| GUI：doe/rsm/bbd/ccd_options/predict | 22 passed，5 个既有 tight-layout warning |
| GUI：overlay/optimize/fractional | 21 passed，5 个既有 tight-layout warning |
| `tests/test_menu_localization.py` | 66 passed |
| `tests/test_help_center.py` | 13 passed |
| `tests/test_g12_inventory.py` | 15 passed |
| `tests/test_worksheets.py`、`test_sheet_context.py`、`test_file_io.py` | 69 passed |
| 合计 | 469 passed、0 failed、0 skipped；仅既有 matplotlib tight-layout 警告 |

未执行：全量 pytest（历史曾在 Windows Tk `Menu.add` 触发原生退出）；手动鼠标逐项验收；真实设备/工艺确认试验。

## 历史记录：五、兼容性与限制

- v1 工程照常读取并在校验时升级；v2 工程旧版软件不可读。
- 官方 BBD 表还列 9、10 因子，本实现只支持 3–7 因子；6 因子三联组存在个别因子对覆盖两次，运行数、满秩与官方表一致。
- 官方 CCD 表中 3 因子单区组行自相矛盾（14 个运行、alpha 1.682、轴点 0），保留既有 DOE-3 语义 2^k+2k+中心点，已在 `sources.md` 记录。
- 部分区组组合因无法复现正交性被拒绝，属明确范围限制。
- 优化为确定性多起点 L-BFGS-B，不保证全局最优；预测与等高线为模型预测，不是确认试验结果。
- 未实现 RSM-005（自定义响应面定义）、RSM-009（预测/置信区间，官方范围未核实）、RSM-016（响应面二元响应）。

## 历史记录：六、工作包 C 启动条件（C0 开始前）

本次未验证 PB 与 DSD 的官方点阵、别名规则与二元响应合同，也未新增对应 fixture。工作包 C 需先补齐这些独立参考与官方范围核对，不能以本报告作为其前置验收。
# 2026-10-28 Review ITERATE 修复记录

本节取代下方 2026-10-27 收尾时对完整验收的判断。工作包 B 仍未全部完成：官方 9、10 因子 Box–Behnken 设计及区组矩阵尚待可靠参考，RSM-002 为 partial，ACC-022 未通过完整范围验收。不进入工作包 C。

| 验收 | 当前状态 |
| --- | --- |
| ACC-021 | 已支持范围内通过 |
| ACC-022 | 部分通过：3–7 因子；9、10 因子未实现 |
| ACC-023 | 已支持范围内通过；带区组曲率 F/p 不可用 |
| ACC-024 | 已支持范围内通过 |
| ACC-025 | 已支持范围内通过 |
| ACC-026 | 已支持范围内通过；不包含预测区间 |
| ACC-027 | 已支持范围内通过 |
| ACC-028、029 | 已支持范围内通过；不保证全局最优 |
| ACC-030 | 已支持范围内通过；带区组曲率只报告均值差 |

纯误差按连续编码水平、分类真实水平与区组分组。三连续因子 BBD 加两水平分类因子，Y=10+100I(L=high)：旧实现纯误差 SSE 为 75000，正确参考为 0；新的测试同时核对残差、自由度和推断不可用。带分类因子与区组的 CCD 重复噪声例，独立分组纯误差 SSE=8，旧实现为 351；独立构建二次模型矩阵并以最小二乘投影验证 SSE、失拟、自由度和 F/p。负失拟平方和仅在浮点误差界内归零，超界时显式报错。带区组中心点和外点均值未经区组调整，因此不报告曲率 F/p。

优化等高线使用优化结果的参考区组及原模型，图题显示该区组。真实 Tk 测试核对区组偏移为 11 和 23 的解析响应面与候选预测；旧版本因缺少区组值无法绘图。来源数据修改后的旧结果仍按既有测试失效。

本次参考与结果：`tests/test_doe_rsm_categorical.py` 新增两项独立参考，旧实现失败、新实现 8 项通过；RSM/诊断/BBD 核心 47 项通过；分类/诊断/CCD 选项/schema/工程持久化/优化核心 96 项通过；BBD 与 CCD 选项 GUI/schema 21 项通过；优化 GUI 7 项通过。Python 为项目 `.venv` 3.11.9。更多测试见项目当日日志。

