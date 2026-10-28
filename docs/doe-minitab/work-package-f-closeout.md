# 工作包 F 收尾记录

日期：2026-10-28

状态：**WORK_PACKAGE_F_READY_FOR_REVIEW**

F 的数学、模型、预测、优化、图形和隔离工作区 GUI/工程流程已在本地验证；与工作包 E 的最终 Schema/公共工作表实现合并、跨 E 联合回归和独立 Review 尚未完成。未提交、未推送、未合并，未启动 G/H。

### Review ITERATE 修正（2026-10-28）

独立 Review 指出的统计正确性和图形边界问题已修复：

- 默认 Mixture×Process 模型不再同时包含 `P` 与全部 `xi*P`。完整交互项已张成过程主效应；默认参数化为组分主项加单组分×过程变量项，避免 `Σxi=1` 造成的结构性完全共线。显式加入 `P` 与全部交互项时仍由秩检查报告别名，不删除用户列。
- 整体模型 F 的分子自由度改为设计矩阵相对常数模型的增量秩：完整 Scheffé 含隐含常数时为 `rank-1`；不含量向量的自定义模型使用未校正 SST/SSR 和 `rank` 自由度。
- 可估计性改为检查单位系数向量是否位于 `X` 的行空间；零列和完全共线的非零列均不会被标为可单独估计，并增加线性对比的可估计性函数。
- 删除项平方和明确标为条件检验；混料组分主项不报告独立 F/p，交互项仅在满秩且误差适用时提供推断。GUI 表格、帮助和测试同步。
- 双组分混料不再进入二维网格；等高线/曲面/叠加等高线在创建绘图窗口前拒绝并提示使用 Trace，Trace 的一维曲线保持可用。

## 基线与环境

- F BASE SHA：`c3720d2`（`Fix DOE blocked optimization and response surface analysis`）。
- Worktree：`C:\Users\shaoy\.codex\worktrees\e9e5\Minijmp`；F 以 `codex/f-mixture`（`34946c5`）合入 `main`（E 提交 `18070e4` 之上），冲突按 E、F 双方内容合并；合并提交未推送。
- 解释器：`C:\Users\shaoy\Documents\Minijmp\.venv\Scripts\python.exe`（Python 3.11.9）。
- 开始时工作区干净；未修改主项目 `C:\Users\shaoy\Documents\Minijmp` 或 E 的工作目录。

## 实现范围

### F0 独立参考

`tests/fixtures/doe_mixture_reference/` 包含 `build_reference.py`、`verify.py`、`reference.json`、`manifest.json`。参考只用标准库 `Fraction`、自写高斯消元和确定性网格，不导入生产模块。

- 三组分 Simplex Lattice 2/3 阶：6/10 点。
- 三组分 Centroid：7 点（3 顶点、3 边中点、1 重心）。
- 上下界 + 两条线性约束的可行多边形：5 个顶点；不可行与退化区域各一例。
- 线性/二次 Scheffé 解析预测；11 行含纯误差的二次模型 ANOVA（SSE、项 SS、纯误差 0.5、失拟）。
- 过程变量与单个过程变量交互；总量与组分量换算。
- 单响应优化 max/min/target 的独立稠密网格界。
- Trace、10 阶三元网格、双响应叠加可行交集（11 点）与空交集。
- 当时记录的 `8ae2c0712fdb423a0570336ebf96cca0dd8366e56c7dddf1be007ad36099c913` 是去掉末尾换行的内容摘要；合并后实测文件字节 SHA-256 为 `cfc482999750eafac2bd8bc89b469e628c405cce23e25c00c010f2695184b0de`。

### F1 约束与设计

- `code/doe_mixture_constraints.py`：组分/变量/线性约束合同、总和与边界核验、显式容差、伪组分、实际量与总量换算。
- `code/doe_mixture.py`：`MixtureSpec`、过程/总量角色、总量固定设定、混料工作表行读取、输入摘要与独立持久化合同；映射到现有 DOE v4 `DesignSpec`。
- `code/doe_mixture_designs.py`：Lattice、Centroid、Extreme Vertices（活动约束枚举）、去重、可行性、质心、点来源、运行上限、标准/运行顺序与结构核验。
- 组分数范围：Lattice/Centroid 2–12（Centroid 最多 13 由合同限制）、Extreme Vertices 2–8；Lattice 阶数 1–10；运行总数上限 10,000。
- 带真实约束的 Lattice/Centroid 若产生不可行点会拒绝并提示改用 Extreme Vertices；不做任意归一化。

### F2 模型与分析

- `code/doe_mixture_model.py`：无截距 Scheffé 1–3 阶、自定义合法项、过程/总量编码及 `xi*z` 项；拒绝未知、重复或超范围项。
- `code/doe_mixture_analysis.py`：SVD 最小二乘、秩/可估计性、系数/拟合/残差、SSE/SST/SSR、逐项 SS、纯误差按完整工况分组、失拟、R²/调整 R²。
- 推断门：秩亏、饱和、无正纯误差或残差方差为零时不输出 F/p；混料组分主效应 p 值不显示（数组为 NaN，界面显示空）。

### F3 预测与优化

- `code/doe_mixture_predict.py`：总和/边界/线性约束、过程与总量检查、解析点预测、模型范围、快照标识。
- `code/doe_mixture_optimize.py`：SLSQP、多起点（设计点 + 质心）、max/min/target、单项与几何平均期望、状态/可行性/约束残差/停止原因；不宣称全局最优；零综合期望显式报告。

### F4 图形

- `code/doe_mixture_plots.py`：Trace（其余组分按参考比例缩放、跳过不可行点）、三元网格、高维合法切片、曲面上采样、叠加可行交集与空交集。
- `code/doe_mixture_dialog.py::MixturePlots`：真实 Tk 图形窗口、三组分三角边框与高维轴标签。

### F5 GUI / Schema / 工程

- `code/doe_mixture_dialog.py`：创建（含约束/过程/总量/预览/取消）、分析、预测、优化和图形五类入口；紧凑输入区、滚动组件表和受控预览（前 100 行）。
- 菜单：`创建混料设计`、`分析混料设计`、`混料预测`、`优化混料响应`、`混料图形`。
- 帮助：`doe.mixture`、`doe.mixture.analysis`、`doe.mixture.predict`、`doe.mixture.optimize`、`doe.mixture.plots`，索引已重建。
- 持久化：工作表同时保存 DOE v4 结构、独立 mixture 合同和最近一次分析模型（响应、阶次、模型项、输入摘要）；保存、重开、复制、再分析保留角色、约束、seed、总量设定、运行 ID、模型项和输入摘要。非法/过期元数据拒绝，验证前不覆盖当前工作簿。

## ACC-032～044 状态

逐项支持与限制见 [验收规范](acceptance.md)。摘要：ACC-032、033、034、035、037、038、039、040、041、042、043、044 为 implemented（限定范围）；ACC-036 为 partial（过程变量完整低/高组合、一个固定总量设定，总量随运行变化与复杂交叉设计未实现）。功能状态不代表已获独立 Review APPROVE。

## 验证证据

命令均从 F worktree 根目录运行。

- 混料专项（12 文件，含真实 Tk 生命周期、模型项恢复、极端顶点/过程/总量、双组分与高维切片）：`64 passed`（Review ITERATE 最终快照）。
- DOE 非 GUI 回归（core/schema v2/v3/factorial/persistence/fractional/CCD/BBD/PB/DSD/RSM/predict/overlay/optimize）：`427 passed in 348.77s`。
- 既有 DOE GUI：`test_doe_gui.py + predict_gui + overlay_gui` 15 passed；`test_doe_rsm_gui.py` 11 passed；`test_doe_optimize_gui.py` 9 passed；`test_doe_ccd_options_gui.py` 13 passed；`test_doe_bbd_gui.py` 10 passed。
- 菜单/帮助/G12/工作表/工程：`test_menu_localization.py + test_help_center.py + test_g12_inventory.py + test_worksheets.py + test_sheet_context.py + test_file_io.py + test_doe_persistence.py` 173 passed（菜单单项仍为 66）。
- 独立参考核验：`tests/fixtures/doe_mixture_reference/verify.py` 通过。

以上测试组存在重叠；不合并为唯一通过总数。全量 pytest 未运行。

## 未覆盖与风险

- 与 E 最终 Schema/公共工作表实现的合并和联合回归未执行；E 若产生新 Schema，F 必须以其为基线重新验证。
- 独立网页端 Review 尚未提交。
- Minitab 产品标准序、XVERT/CONAEV 输出顺序、图形布局和表格格式未比较。
- 总量随运行变化、复杂 cross-design、超过 8 组分的 Extreme Vertices、预测/置信区间、全量产品选项未支持或未核实。
- 优化为局部多起点，不证明全局最优；图形为模型预测，不是确认试验。
