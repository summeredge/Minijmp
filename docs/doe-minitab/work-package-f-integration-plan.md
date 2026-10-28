# 工作包 F 集成准备

日期：2026-10-28

## 1. F BASE SHA

`c3720d2`（`Fix DOE blocked optimization and response surface analysis`）。

## 2. F 分支与 worktree

- Worktree：`C:\Users\shaoy\.codex\worktrees\e9e5\Minijmp`。
- Git：detached `HEAD (no branch)`，未创建或推送 F 独立分支。
- 主项目与 E 工作目录未被修改；未提交、未推送、未合并。

## 3. F 新增独立生产模块

- `code/doe_mixture_constraints.py`
- `code/doe_mixture.py`
- `code/doe_mixture_designs.py`
- `code/doe_mixture_model.py`
- `code/doe_mixture_analysis.py`
- `code/doe_mixture_predict.py`
- `code/doe_mixture_optimize.py`
- `code/doe_mixture_plots.py`
- `code/doe_mixture_dialog.py`

## 4. F 修改的共享文件

- `code/doe_core.py`：`_DESIGN_TYPES` 增加 `mixture`。
- `code/worksheets.py`：保存/加载可选的 `mixture` 元数据；先验证再赋值。
- `code/MiniJMP.py`：DOE 菜单增加五个混料入口。
- `help/pages/doe.html` 与帮助索引；`docs/MENU_TRANSLATION.md`。
- 测试清单：`tests/fixtures/g12_table_inventory.json`、`tests/test_menu_localization.py`。

## 5. E/F 可能冲突的 Schema 字段

- F 不新增 v5，也不改变 v4 字段集合；仅在设计类型枚举增加 `mixture`。若 E 也扩展该枚举，以 E 的最终枚举合并，保留 `mixture` 值。
- F 的混料语义存放在工作表 `meta['mixture']` 独立对象（schema 1），最近分析模型存放在 `meta['mixture_model']`（响应、阶次、模型项、输入摘要），不写入 DOE v4 的 `design` 字典；DOE v4 只承担因子/运行/列映射和输入摘要。
- 若 E 改为新的工作表元数据容器、重命名 `doe` 键或改变验证顺序，需同步 `worksheets.saveMeta/loadMeta` 与 F 的保存/恢复测试。
- F 依赖 `FactorSpec` 连续因子与 `DesignResult` 对设定范围的校验；E 若改变 `low/high` 或 `run.settings` 语义，需重新运行混料持久化与 GUI 测试。

## 6. 菜单集成变更

新增：创建混料设计、分析混料设计、混料预测、优化混料响应、混料图形。帮助 topic 为 `doe.mixture*`。合并时若 E 调整菜单编号，保持命令与翻译清单、帮助主题的对应关系，不覆盖 E 的新入口。

## 7. 工程保存/恢复适配需求

- 保存时验证 DOE v4 与 mixture 两层元数据；写入响应前列，不把响应值纳入设计输入摘要。
- 重开/复制保留 mixture 元数据；非法元数据在赋值前拒绝，避免覆盖当前工作簿。
- E 的最终版本需重跑创建→预览→确认→填写响应→分析→图形→保存→关闭→重开→复制→再分析。

## 8. 无需等待 E 即可审查的范围

- F0 独立参考与 `verify.py`。
- F1 约束、三类设计、运行上限与不可行/退化处理。
- F2 Scheffé 模型、ANOVA、纯误差/失拟与推断门。
- F3 预测、单/多响应优化及约束残差。
- F4 Trace/三元网格/曲面/叠加可行域采样。
- F 隔离工作区的 Tk 创建、分析、预测、优化、图形与本地保存/重开/复制。

## 9. 必须在 E 最终 HEAD 补跑的测试

- `tests/test_doe_mixture_persistence.py`（元数据容器与验证顺序）。
- `tests/test_doe_mixture_gui.py`（菜单、保存/重开/复制、图形）。
- `tests/test_doe_core.py`、`tests/test_doe_schema_v2.py`、`tests/test_doe_schema_v3.py`（枚举与迁移）。
- `tests/test_menu_localization.py`、`tests/test_help_center.py`、`tests/test_g12_inventory.py`。
- E 最终 Schema 下的全部旧工程读取与 Factorial/CCD/BBD/PB/DSD 基础回归。

## 10. 是否可以安全合并

本地 F 代码不修改 E 工作目录，但 `doe_core.py::_DESIGN_TYPES`、`worksheets.py` 和菜单/帮助存在共享文件级冲突风险。**在 E 的最终 Schema 未冻结并完成上述联合回归前，不建议合并。** E 冻结后可先合并独立混料模块，再按 E 的实际元数据容器适配共享文件并重跑验收；当前状态为 `WORK_PACKAGE_F_READY_FOR_REVIEW`，不是已获 Review APPROVE。
