# 工作包 B+C 联合独立 Review 收尾（2026-10-28）

状态：**BC_READY_FOR_INDEPENDENT_REVIEW**。限定范围的本地联合回归通过；本地证据与独立 LRM Review 分开记录，尚无独立 Review APPROVE。C 五项官方完整范围仍为 partial。

## 快照与范围

HEAD `886a0311164f691aba4c96093013f645107cb128`；工作区包含此前 B、C0、C 的未提交修改及新增文件，具体清单以 `git status --short` 为准。未 reset、clean、stash、commit、push 或 tag。此快照不包括未来工作包 D 的开发。

- B：CCD 2–10 连续因子按支持的全因子/分数及区组表生成，可含分类因子；BBD 支持 3–7、9、10 连续因子，8 因子未支持。支持响应面模型、点预测、叠加图和 CCD/BBD 单/多响应优化；优化不保证全局最优。受支持布局、模型层级及推断条件见 [B 收尾](work-package-b-closeout.md)。
- C：PB 基础运行数 12/20/24/28/32/36/40/44/48，2 至运行数减 1 个连续或两水平分类因子；支持重复、中心/伪中心及按重复分区组。DSD 支持 2–48 连续、1–47 连续加 1 分类、4 连续加 2 分类；支持均分完整重复的区组。其余多分类、额外中心点及产品选项未覆盖，见 [C 收尾](work-package-c-closeout.md)。
- 双分类 DSD 的连续与分类主效应交叉积为 ±2，分类主效应之间为 6，故主效应并非两两正交；反向配对使主效应与二阶项交叉积为零。带截距主效应秩为 7，加四个连续平方项秩为 11；完整模型仍需按实际秩判断可估计性。

当前工作区状态（含既有与本轮修改）：

```text
 M .agent-memory/MEMORY.md
 M .agent-memory/logs/2026-10-28.md
 M code/MiniJMP.py
 M code/doe_bbd.py
 M code/doe_ccd.py
 M code/doe_core.py
 M code/doe_dialog.py
 M docs/CHANGELOG_DEV.md
 M docs/MENU_TRANSLATION.md
 M docs/doe-minitab/README.md
 M docs/doe-minitab/acceptance.md
 M docs/doe-minitab/bbd-reference-validation.md
 M docs/doe-minitab/feature-matrix.csv
 M docs/doe-minitab/roadmap.md
 M docs/doe-minitab/sources.md
 M docs/doe-minitab/work-package-b-closeout.md
 M help/assets/search-index.js
 M help/help-map.json
 M help/pages/doe.html
 M tests/fixtures/doe_bbd_reference/README.md
 M tests/fixtures/g12_table_inventory.json
 M tests/test_doe_bbd.py
 M tests/test_doe_bbd_gui.py
 M tests/test_doe_bbd_minitab_parity.py
 M tests/test_doe_ccd_options.py
 M tests/test_doe_ccd_options_gui.py
 M tests/test_doe_optimize.py
 M tests/test_doe_predict.py
 M tests/test_doe_rsm_gui.py
 M tests/test_doe_schema_v2.py
 M tests/test_help_center.py
 M tests/test_menu_localization.py
?? code/doe_dsd.py
?? code/doe_pb.py
?? code/doe_screening_analysis.py
?? code/doe_screening_matrices.py
?? docs/doe-minitab/screening-reference-validation.md
?? docs/doe-minitab/screening-schema-plan.md
?? docs/doe-minitab/work-package-bc-review-closeout.md
?? docs/doe-minitab/work-package-c-closeout.md
?? docs/doe-minitab/work-package-c0-closeout.md
?? docs/doe-minitab/work-package-c0-spec.md
?? tests/fixtures/doe_screening_reference/
?? tests/test_doe_dsd.py
?? tests/test_doe_pb.py
?? tests/test_doe_schema_v3.py
?? tests/test_doe_screening_analysis.py
?? tests/test_doe_screening_gui.py
?? tests/test_doe_screening_references.py
```

## B 阻断修复与限定验收

四项修复：CCD 由非中心结构正确校验重复；区组 CCD 的默认中心点按当前布局计算且显式值必须等于布局所需值；CCD/BBD 展开前检查 10000 行上限；分类响应面图仅允许连续因子作 X/Y，分类固定水平可切换并通过模型计算，区组使用参考水平。对应独立/GUI 回归见下方命令与 [B 收尾](work-package-b-closeout.md)。

本次回归中，重复结构由 `test_doe_ccd_options.py` 的重复/元数据案例核验；默认及显式中心点由 `test_doe_ccd_options_gui.py` 验证预览和拒绝；行数边界及展开前拒绝由 `test_doe_ccd_options.py`、`test_doe_bbd.py` 验证；分类曲面由 `test_doe_rsm_gui.py::test_categorical_rsm_plot_uses_selected_level_and_continuous_axes` 核验实际水平、网格与轴选择。上述测试包含在 274 项核心与 69 项 Tk 回归中。

ACC-021～030 在矩阵中均为 implemented，限定于实际支持配置和模型条件：021 CCD，022 BBD（022A 数学与工程；022B 下述五份设置的数学等价），023 区组，024 分类，025 模型项，026 预测，027 叠加图，028 单响应优化，029 多响应优化，030 诊断。并非声称全部 Minitab 选项或独立 Review 已通过。

## C 限定验收

| 验收 | 状态 | 已验证与剩余边界 |
|---|---|---|
| ACC-001 | partial | 九种 PB 基础运行数、因子列、中心点、重复与区组；Minitab 点序和其他产品选项待核对。 |
| ACC-002 | partial | 上述 DSD 配置、构造和可估计性；其他多分类、额外中心点及产品伪中心待核对。 |
| ACC-003 | partial | 连续响应、指定模型、秩/零空间/可估对比及适用推断；自动选模、权重和产品输出未对标。 |
| ACC-005 | partial | Pareto、正态/半正态及饱和 PB Lenth；完整产品画法与选项未对标。 |
| ACC-006 | partial | PB 投影及 DSD 二阶投影、零空间与可估对比；产品 alias 表和其他分类组合未对标。 |

零残差方差、饱和、秩亏及缺失响应的处理由筛选分析测试覆盖；Lenth PSE 属探索性分析，选模后名义 p 值不代表独立确认。

## 独立参考与兼容性

C0 八份原始矩阵和 SHA-256 保留：NIST PB12/20/28、conference 构造的 DSD 6/7/8/10 连续因子、Jones–Nachtsheim 构造的 4 连续加 1 分类；另有 NIST PB24/36 原表及转换参考。逐项哈希与链接见 [筛选参考核验](screening-reference-validation.md) 和 [manifest](../../tests/fixtures/doe_screening_reference/manifest.json)，本次十项矩阵哈希均通过。连续 DSD 的 conference matrix、单分类与双分类反向配对是独立数学构造，不是 Minitab 导出。五份用户声明来自 Minitab 22 的 BBD 原始 CSV 的原始哈希、设置、行尾还原及点集/区组比较见 [BBD 参考核验](bbd-reference-validation.md) 和 [manifest](../../tests/fixtures/doe_bbd_reference/manifest.json)：仅 9 因子无区组/5/10 区组、10 因子无区组/2 区组，10 中心点、单重复、无分类、标准序、无随机化；点多重集和重编号后区组分配等价，逐行标准序不同。用户所述版本不能由 CSV 单独证明。

Schema v3 保存筛选构造身份与输入摘要，v1/v2 先按原格式校验后升级；旧软件读取 v3 不作保证。工程测试检查保存、重开、复制和无效元数据保护。

尚需 Minitab 22 对照：PB 九种满容量及 PB24/40 分类中心点与区组；各 DSD conference 阶数、列子集、单分类/双分类、其他多分类和区组 seed；逐项导出条件见 [筛选参考核验](screening-reference-validation.md)。BBD 其他中心点、重复、分类、版本和标准序也未对标。

已确认而尚未实现的官方功能包括筛选二元响应和自定义筛选定义（SCR-004/005）、General Full Factorial、split-plot/foldover 等因子设计、RSM 自定义设计和二元分析、Mixture、Taguchi、最优设计选点与功效；完整逐项缺口和编号见 [功能矩阵](feature-matrix.csv)。SCR-005 官方证据见 [来源](sources.md)，追加 ACC-067，计划后续 E，本轮未实现。

## 实际测试

以下命令均在主工作区使用 `.venv\Scripts\python.exe`（Python 3.11.9）；测试组有重叠，不合计唯一用例数。未运行全量 pytest。

```powershell
& .\.venv\Scripts\python.exe -m pytest tests/test_doe_ccd.py tests/test_doe_ccd_options.py tests/test_doe_bbd.py tests/test_doe_bbd_minitab_parity.py tests/test_doe_rsm.py tests/test_doe_rsm_categorical.py tests/test_doe_rsm_diagnostics.py tests/test_doe_predict.py tests/test_doe_optimize.py tests/test_doe_overlay.py tests/test_doe_core.py tests/test_doe_schema_v2.py tests/test_doe_persistence.py -q --tb=short
# 274 passed
& .\.venv\Scripts\python.exe -m pytest tests/test_doe_screening_references.py tests/test_doe_pb.py tests/test_doe_dsd.py tests/test_doe_screening_analysis.py tests/test_doe_schema_v3.py -q --tb=short
# 156 passed
& .\.venv\Scripts\python.exe -m pytest tests/test_doe_dsd.py::test_two_category_foldover_is_independently_estimable -q --tb=short
# 1 passed；新增独立固定交叉积断言
& .\.venv\Scripts\python.exe -m pytest tests/test_doe_factorial.py tests/test_doe_analysis.py tests/test_doe_fractional.py tests/test_doe_fractional_analysis.py -q --tb=short
# 52 passed
& .\.venv\Scripts\python.exe tests/fixtures/doe_screening_reference/dsd/verify.py
# 4 个连续 C0 参考哈希、整数交叉积和有理秩核验通过；混合参考由上级 manifest 测试覆盖
& .\.venv\Scripts\python.exe -m pytest tests/test_doe_bbd_gui.py tests/test_doe_ccd_options_gui.py tests/test_doe_rsm_gui.py tests/test_doe_optimize_gui.py tests/test_doe_gui.py tests/test_doe_fractional_gui.py tests/test_doe_predict_gui.py tests/test_doe_overlay_gui.py -q --tb=short
# 69 passed，11 tight_layout warnings
& .\.venv\Scripts\python.exe -m pytest tests/test_doe_screening_gui.py -q --tb=short -k 'not test_pb_new_run_counts_all_factor_counts_gui'
# 118 passed，200 deselected，107 tight_layout warnings
& .\.venv\Scripts\python.exe -m pytest tests/test_help_center.py tests/test_menu_localization.py tests/test_g12_inventory.py tests/test_worksheets.py tests/test_sheet_context.py tests/test_file_io.py -q --tb=short
# 163 passed
& .\.venv\Scripts\python.exe tools/build_help_index.py
# 完成
```

帮助测试验证生成索引与当前正文一致，菜单和帮助映射、G12 清单与工作表/工程基础测试通过。

先前 C 阶段对 PB24/32/36/40/44/48 的 200 个中间连续因子数真实 Tk 工程路径按运行数分别开进程，得到 20/28/32/36/40/44 passed，命令见 [C 收尾](work-package-c-closeout.md)；本轮未重新运行这些中间因子数，历史记录没有冻结本联合快照的全部文件哈希，因此不能将其当成本次快照的重新验证。此前单进程 200 案例出现 Tk 原生 `0x80000003` 且无 pytest 汇总，不计通过。

## Review 条件和限制

独立 Review 必须审查当前未提交的完整工作区快照、独立 fixture 和上述限定范围；本地通过不等于 LRM 协议级 APPROVE。产品逐点一致性与官方完整覆盖仍待上述参考及实现；本轮真实 Tk 出现布局调整提示，测试未报告实际裁切，但未对每个绘图窗口逐一截图检查。
