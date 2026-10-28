# 工作包 D 收尾记录

**状态：`WORK_PACKAGE_D_READY_FOR_REVIEW`**  
本地限定实现、独立数学、Tk 和工程闭环已完成；仍有未覆盖的 Minitab 产品选项，因此矩阵的相关 feature 保持 `partial`。本记录不是独立 Review APPROVE。

## Git 与边界

- 项目：`C:\Users\shaoy\Documents\Minijmp`
- BASE：`e7a46737612cf5b56cd7d02911c4d13ec4753087`
- HEAD：`e7a46737612cf5b56cd7d02911c4d13ec4753087`（本任务未提交）
- 当前分支：`main`。本任务不提交、推送、打标签、清理或启动 E/F/G/H。

## D0–D5 完成范围

| 阶段 | 实际完成 |
|---|---|
| D0 | 固定独立 factorial fixture、来源、SHA-256 与不导入生产模块的核验器；核对组合、signed aliases、Foldover、区组和裂区平方和。 |
| D1 | DOE Schema v4；General Full Factorial 2–10 个分类因子、文字/数值标签、完整笛卡尔积、重复、seed、完整重复区组与工程往返；核心创建和工程恢复共用因子数边界。v1/v2/v3 先按旧字段和摘要校验再迁移。 |
| D2 | 正/负生成元、带符号 alias、中心点和完整分数区组；未分区组的 3–6 因子正规分数支持全部因子或单因子单批次 Foldover，响应、运行映射、父设计与矩阵摘要持久化，折叠后从实际点阵重算 alias/秩/分辨率。 |
| D3 | 全因子、正规分数和一般全因子支持每个完整重复作为一区组；seed 不跨区组打散运行。Split-Plot 限两个连续两水平因子，一个 hard-to-change、一个 easy-to-change，至少两个完整平衡区组。 |
| D4 | 两水平全因子、正规分数、一般全因子、区组、Foldover 后矩阵和 Split-Plot 按各自模型分析；逐项 ANOVA、中心点和残差诊断已接入。Pure Error 按相同因子设置及相同区组分组；无独立纯误差时不输出 LOF F/p。区组模型单列区组调整残差，并说明无处理×区组交互假设。 |
| D5 | 菜单、预览、取消、响应编辑、分析、图形、`.dexpl` 保存、关闭、重开、复制和再分析均有真实 Tk 覆盖；非法输入/来源变更及 v1/v2/v3 工程恢复有专项回归。 |

## Schema 与本地支持界限

- DOE Schema 当前为 v4；v1/v2/v3 迁移边界由 `tests/test_doe_schema_v2.py`、`tests/test_doe_schema_v3.py` 和 `tests/test_doe_factorial_schema.py` 覆盖。旧版 MiniJMP 不保证读取 v4 工程。
- General Full Factorial：2–10 个因子，每个因子 2 个以上文字或数值分类水平，完整组合；最多 10,000 次运行，模型矩阵最多 10,000,000 个单元。
- 普通区组：只按完整独立重复分区组；不支持用户任意切分区组。区组效应纳入模型并检查可估计性。
- Split-Plot：只支持完整平衡 2×2 两水平因子与经典两层误差；不支持多 hard/easy 因子、不平衡结构、REML 或其他自由度近似。
- Foldover：3–6 因子正规两水平分数；全部或单因子折叠、未分区组、一次新增批次。PB、Split-Plot、重复折叠及 Minitab 标准序/输出 parity 均未核实。
- ANOVA：项 F/p 依赖适用误差层、正残差方差及模型充分假设；独立 pure error 按相同设置且相同区组识别。当前完整区组误差以处理×区组残差估计，假设无处理×区组交互。单独 LOF 检验只在有独立纯误差时提供 F/p。

独立参考说明见 [Factorial DOE 独立参考核验](factorial-reference-validation.md)。官方页面确定功能和误差分组语义，但未取得 Minitab 22 导出数据；不宣称逐点、标准序或统计表数值等价。

## ACC 状态

| ACC / Feature | 状态 | 本地已核验范围 | 未覆盖内容 |
|---|---|---|---|
| ACC-007 / FAC-002 | partial | 正/负正规生成元、带符号别名、中心点、受限完整重复区组。 | 其他产品选项和 Minitab 标准序。 |
| ACC-008 / FAC-003 | implemented（限定范围） | 一般全因子完整组合、文字/数值水平、seed、重复、区组、GUI 和工程生命周期。 | 标准序及产品专属设置。 |
| ACC-009 / FAC-004 | implemented（限定范围） | 100/150/200 等数值水平按分类因子分析，报告 df、边际均值和组合均值。 | Minitab 参数化/输出格式逐项一致性。 |
| ACC-010 / FAC-005 | implemented（限定范围） | 混合水平 2×3、2×3×4 及分类项 ANOVA。 | Minitab 点位分配和标准序。 |
| ACC-011 / FAC-008 | partial | 两水平全因子、正规分数及一般全因子的完整重复区组与区组调整。 | 自定义不完整分块和产品布局 parity。 |
| ACC-013 / FAC-010 | partial | 两因子平衡 Split-Plot，整区/子区自由度和误差项。 | 多因子、不平衡和 REML。 |
| ACC-015 / FAC-012 | partial | 正规分数全部/单因子 Foldover、实际 alias/秩/分辨率、响应保留和 lineage。 | PB/Split-Plot、重复增补、Minitab 22 parity。 |
| ACC-017 / FAC-014 | partial | 两水平项效应、一般分类项、别名组、区组/裂区和 Foldover 后矩阵分派。 | PB 的 Factorial 项分析 parity 和完整产品选项。 |
| ACC-018 / FAC-015 | partial | SST/SSR/SSE、项 SS/df/MS/F/p、pure error、中心点和 LOF 的有效性边界。 | 不平衡/替代模型与 Minitab 输出 parity。 |
| ACC-066 / FAC-019 | partial | 完整重复区组和嵌套 split-plot 随机化，seed 与执行顺序可复现。 | 自定义区组分割及其他产品随机化模式。 |

ACC-012 对既有总体 seed 随机化作回归；未据此重复开发 FAC-009。FAC-006/007/009 的既有实现保持为回归基线。

## 验证记录

所有项目 Python 命令均使用 `C:\Users\shaoy\Documents\Minijmp\.venv\Scripts\python.exe`。重叠测试组不累加为唯一测试数。

### D 数学、Schema、设计与工程（非 GUI）

```powershell
& .\.venv\Scripts\python.exe -m pytest tests\test_doe_factorial_anova.py tests\test_doe_factorial_references.py tests\test_doe_factorial.py tests\test_doe_factorial_blocks.py tests\test_doe_general_factorial.py tests\test_doe_general_factorial_analysis.py tests\test_doe_fractional.py tests\test_doe_fractional_analysis.py tests\test_doe_foldover.py tests\test_doe_splitplot.py tests\test_doe_splitplot_analysis.py tests\test_doe_core.py tests\test_doe_factorial_schema.py tests\test_doe_schema_v2.py tests\test_doe_schema_v3.py tests\test_doe_persistence.py tests\test_doe_analysis.py -q --tb=short
```

**182 passed**（审查修复新增 6 项边界/工程用例）。包括独立误差分解、正/负 alias、Foldover、中心点、区组、裂区、Schema v1/v2/v3 恢复与分析回归。

### 独立 Review 遗留修复（当前快照）

- General Full Factorial 的 `create_general_factorial` 与 `validate_general_factorial` 统一限制 2–10 个分类因子；1 个和 11 个均明确拒绝，10 因子仍受 10,000 次运行上限约束。测试直接构造核心定义并伪造保存元数据，确认无法绕过界面进入工程。
- Split-Plot 预览在核心生成成功后显示总运行、区组和整区数，仅向 Tk Text 插入前 100 行，截断时追加“仅显示前 100 行，共 M 行”，并提供水平滚动条；实际创建仍使用完整结果。默认 12 行完整预览、104 行、10,000 行上限、超过上限拒绝、切换设置刷新、取消/无效输入不改工作簿均有真实 Tk 覆盖。
- 专项八文件 **42 passed**、2 个既有 `tight_layout` warnings；D 非 GUI 组 **182 passed**；B/C 非 GUI 组 **358 passed**；原 Factorial/Fractional/Foldover Tk **22 passed**；菜单、帮助与 G12 **94 passed**；独立 factorial 参考核验通过。测试组重叠，不相加。

### B/C 设计、分析和独立参考（非 GUI）

```powershell
& .\.venv\Scripts\python.exe -m pytest tests\test_doe_bbd.py tests\test_doe_bbd_minitab_parity.py tests\test_doe_ccd.py tests\test_doe_ccd_options.py tests\test_doe_rsm.py tests\test_doe_rsm_diagnostics.py tests\test_doe_rsm_categorical.py tests\test_doe_optimize.py tests\test_doe_predict.py tests\test_doe_overlay.py tests\test_doe_pb.py tests\test_doe_dsd.py tests\test_doe_screening_analysis.py tests\test_doe_screening_references.py -q --tb=short
```

**358 passed**，310.15 秒。覆盖 BBD 用户参考、CCD/RSM/优化及 PB/DSD 数学参考。

### Tk 与工程生命周期

| 命令 | 结果 |
|---|---|
| `pytest tests\test_doe_gui.py -q --tb=short` | 5 passed，3 个 `tight_layout` warnings |
| `pytest tests\test_doe_fractional_gui.py -q --tb=short` | 15 passed，1 个 warning |
| `pytest tests\test_doe_general_factorial_gui.py -q --tb=short` | 3 passed，1 个 warning |
| `pytest tests\test_doe_splitplot_gui.py -q --tb=short` | 2 passed，1 个 warning |
| `pytest tests\test_doe_foldover_gui.py -q --tb=short` | 2 passed |
| `pytest tests\test_doe_bbd_gui.py -q --tb=short` | 10 passed，1 个 warning；覆盖新 Schema v4 保存重开 |
| `pytest tests\test_doe_rsm_gui.py -q --tb=short` | 11 passed，3 个 warnings；覆盖新 Schema v4 CCD 生命周期 |
| `pytest tests\test_doe_ccd_options_gui.py -q --tb=short` | 13 passed |
| `pytest tests\test_doe_optimize_gui.py -q --tb=short` | 9 passed |
| `pytest tests\test_doe_predict_gui.py -q --tb=short` | 6 passed |
| `pytest tests\test_doe_overlay_gui.py -q --tb=short` | 4 passed，4 个 warnings |
| PB 共享绘图：创建/存盘、中心与区组、Lenth/Pareto、最大容量、24–44 runs capacity nodeids | 1 + 4 + 5 passed；均为单文件串行进程 |
| DSD 当前代表性 mixed 与区组 GUI nodeids | 2 passed，2 个 warnings |
| `pytest tests\test_worksheets.py -q --tb=short` | 18 passed |
| `pytest tests\test_sheet_context.py -q --tb=short` | 6 passed |
| `pytest tests\test_file_io.py -q --tb=short` | 45 passed |

PB/DSD 完整高因子参数化 GUI 文件没有在本快照中一次跑完：该文件合并了约 200 个 PB 因子数场景及高因子 DSD 场景；本轮运行到 22% 后被终止以按类别拆分。首项暴露的 PB 正态图标题断言已同步为新标题，孤立复跑通过。此前 C 第二轮已按独立进程完成 118 项筛选 GUI 和 200 个 PB 中间因子数案例（20/28/32/36/40/44 runs 分组通过）；本轮另复核了所有被 D4 共享绘图路径触及的代表性 PB 用例及两个 DSD 工程路径。此处不把历史分组写成本轮全文件通过。

### 帮助、菜单与报告清单

- `& .\.venv\Scripts\python.exe tools\build_help_index.py`：成功。
- `& .\.venv\Scripts\python.exe -m pytest tests\test_help_center.py -q --tb=short`：13 passed。
- `& .\.venv\Scripts\python.exe -m pytest tests\test_menu_localization.py -q --tb=short`：66 passed。
- `& .\.venv\Scripts\python.exe -m pytest tests\test_help_center.py tests\test_g12_inventory.py -q --tb=short`：28 passed（帮助与 G12 组；各文件结果重叠，不与上面相加）。
- `& .\.venv\Scripts\python.exe tests\fixtures\doe_factorial_reference\verify.py`：`factorial independent references verified`；参考 JSON 与 manifest SHA-256 一致。
- `& .\.venv\Scripts\python.exe tests\fixtures\doe_screening_reference\dsd\verify.py`：固定 DSD 矩阵秩/投影参考核验输出完成。

全量 `pytest` 未运行。最终审查前应查看本文与工作区差异；本任务未提交、未推送，也未执行独立 LRM Review。
