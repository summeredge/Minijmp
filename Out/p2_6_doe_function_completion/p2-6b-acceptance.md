# DOE Phase 2 P2-6B 验收报告

> 历史阶段报告：P2-6A/B 代码与测试已包含于本轮开始的 `71520c2`。原文“未提交”指编写时状态；2026-10-31 当前验收、独立参考补强和提交状态见 [最终验收](p2-6-final-acceptance.md)。

日期：2026-10-30  
工作区：`C:\Users\shaoy\Documents\Minijmp`  
结论：本地实现和限定范围验证完成；DOE Schema 保持 v5。未提交、推送、打标签或发布。

## 功能状态

| ID | 状态 | 本轮核实的实现 | 支持边界 |
|---|---|---|---|
| TAG-005 | `IMPLEMENTED` | 增加标准 `L36(2^11 3^12)`，36 行、23 列；支持列分配、可滚动因子选择、预览、设计建立、分析与工程持久化。固定矩阵及列/因子模型秩均有独立断言。 | 按标准阵的声明水平与列容量分配因子。L36 表参考 [Minitab Taguchi designs catalogue](https://support.minitab.com/en-us/minitab/help-and-how-to/statistical-modeling/doe/supporting-topics/taguchi-designs/catalogue-of-taguchi-designs/)。此来源用于阵列表核对，不代表 Minitab 22 输出 parity。 |
| TAG-009 | `IMPLEMENTED_SCOPED` | 静态分类响应支持选择主效应及双因子交互，做可估性检查、OLS 拟合/残差/系数推断、指定设定预测与均值置信区间；最佳目标均值搜索使用声明水平的完整枚举；可将原运行和各声明噪声/信号条件的确认试验行复制到独立工作表，并检测来源快照过期。 | 新响应模型限无信号的静态设计。候选搜索最多 20,000 个控制设定；置信区间使用普通 OLS 推断，不校正选点偏差。动态交互、零误差方差或不足的残差自由度不提供相应推断/区间。 |
| TAG-008 | `IMPLEMENTED_SCOPED` | 静态无信号内外表支持二水平控制×噪声模型及指定交互；按已声明噪声组合等权计算各控制设定的条件均值和总预测方差，并精确枚举控制组合，支持目标均值/范围约束。 | 控制因子和噪声因子均须二水平；最多 20,000 个控制组合；噪声概率固定等权。模型秩亏、饱和或误差方差不可估时不输出最优设定。多水平、动态信号和自定义噪声概率不支持。 |
| FAC-012 | `IMPLEMENTED` | 正规分数因子与 Plackett–Burman Foldover 支持在一次操作中选择任意非空因子子集；预览说明被翻转和保持不变的因子，新增运行保留空响应及来源谱系，原始运行不变。保存/重开、复制和重新分析有覆盖。 | 本轮覆盖一次多因子折叠操作；没有扩展为连续串接多次 Foldover 的工作流。 |
| MIX-005 | `IMPLEMENTED_SCOPED` | 复核现有 Mixture v2：2–3 个总量水平与混料点完整交叉，联合模型包含 Scheffé×总量项；保留现有 GUI、工程保存/重开、分析、预测和优化路径。 | 现有 72×15 独立验证覆盖声明范围；更宽的总量二次交互模型及交互图不在当前实现范围。本轮未更改此功能。 |
| GEN-006 | `IMPLEMENTED_SCOPED` | 自定义因子与响应面设计新增固定运行数 D-optimal Improve：从选定候选运行中交换未执行的可替换运行，锁定运行及已填写响应/实测值的运行不变。只接受满秩且 logdet 严格增加的交换；无改善时保留运行并报告原因。新工作表记录父/候选设计、候选运行、替换映射、模型、矩阵摘要、seed 和前后秩/logdet。 | 限 `custom_factorial`、`custom_rsm`，且父模型初始须满秩、无区组。采用 seed 决定并列顺序的受限单点交换，最多 100 轮/200,000 次评价；是局部搜索，不保证全局最优。Distance-based 仍仅用于追加增补；Mixture Improve 保持原实现。 |

## 验证

- 项目解释器：`.venv\Scripts\python.exe`，Python 3.11.9。
- 最终合并非 GUI 回归：Taguchi 响应模型、噪声与动态分析、P4B/C Taguchi、标准阵列、持久化、常规 Foldover 和 PB Foldover 共 8 个测试文件，**183 passed**。运行命令：

  ```powershell
  & '.venv\Scripts\python.exe' -m pytest -q --tb=short tests/test_doe_taguchi_response_models.py tests/test_doe_taguchi_noise.py tests/test_doe_taguchi_dynamic.py tests/test_doe_phase2_p4bc_taguchi.py tests/test_doe_taguchi_arrays.py tests/test_doe_taguchi_persistence.py tests/test_doe_foldover.py tests/test_doe_pb_foldover.py
  ```

- 最新快照变更后，TAG-009/008 响应模型单测 **6 passed**；真实 Tk 的指定设定/确认表、来源过期拒绝、噪声交互模型三个隔离流程各 **1 passed**。
- 定向 GUI 证据：L36 建立/分析 **1 passed**；正规 Foldover GUI **3 passed**；PB 多因子 Foldover 新流程 **1 passed**；L36 工程往返测试 **2 passed**。Taguchi 完整 GUI 文件先前 **15 passed**（2 个既有 Matplotlib `tight_layout` 警告）。
- 所有已修改 Python 文件经项目解释器 `py_compile`；`git diff --check` 退出码为 0。Git 显示 `code/doe_screening_analysis.py` 的 CRLF→LF 提示。

### GEN-006 完成验证

- 项目 `.venv` 定向非 GUI 回归：`tests/test_doe_optimal_improvement.py`、`test_doe_optimal.py`、`test_doe_augment.py`、`test_doe_optimal_augmentation.py`、`test_doe_mixture_improve.py`、`test_doe_core.py` 共 **88 passed**。
- 新 GUI 流程 `tests/test_doe_optimal_improvement_gui.py` **1 passed**，覆盖 Select/Augment/Improve 入口、父/候选运行预览、创建、保存重开及重新分析。既有 Select、Augment、Mixture Improve GUI 回归各隔离运行 **1 passed**。
- 独立数学参考：小型两因子自定义因子设计枚举所有候选替换，以整数计算 `det(X'X)` 并核对选择结果（logdet 由 `ln(24)` 改善至 `ln(64)`）；两因子完整二次 RSM 以独立矩阵构造核对 rank=6 和替换后 logdet。另覆盖同 seed 并列可重复、锁定响应/实测值保护、候选已执行拒绝、无改善及保存谱系矩阵摘要校验。

## 保留事项

- 未执行 Minitab 22 的产品输出/数值 parity 验证；L36 只按公开目录固定表核对。
- TAG-009/008 的统计推断边界、候选预算和固定等权噪声假设如上；GEN-006 不支持全局最优证明、区组设计或固定运行数 Distance-based 改善。
- 保留 P2-6A、既有用户工作区改动及 `Out/p5_function_gap_closure/`。本轮没有更新正式功能矩阵或帮助目录，没有提交、推送或发布。
