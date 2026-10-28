# 工作包 C0 收尾（2026-10-28）

> 历史阶段记录：后续已实施限定范围的 C，且 SCR-005 已确认是官方功能；当前状态见 [C 收尾](work-package-c-closeout.md) 与 [来源](sources.md)。

状态：**C0_READY_FOR_REVIEW**。PB、全连续 DSD 及单分类混合 DSD 已有可追溯的代表性数学参考；其他分类组合及 Minitab 逐点一致性仍需对应参考，不能据此推定已完成或缩减正式范围。本文不代表工作包 C 功能验收，也不是工作包 B 的 Review APPROVE。按本次目标，停止于 C0，等待网页端独立 Review。

## 基线与范围

- 开始时 `main`，HEAD `886a0311164f691aba4c96093013f645107cb128`，工作区干净；未提交、推送、创建标签或启动 C1–C3。
- 范围为 SCR-001/002/003/006/007，正式编号保持 ACC-001/002/003/005/006。二元响应留在 H，SCR-005 未确认，General Full Factorial、foldover、D-optimal、混料和 Taguchi 不属于 C0。
- SCR-001/002/003 仍为 missing，SCR-006/007 仍为 partial；本轮未修改生产代码、工作包 B 的数学算法及原有测试基线。
- PB 在 Factorial 里创建与分析；DSD 在 Screening 里创建与分析。PB 部分混杂按实际矩阵投影，不能使用正规部分因子完整别名等式代替。

## 证据与方案

PB：官方支持 12–48 之间指定的 4 倍数运行数、最多 47 因子，8/16 次在该产品中作为其他两水平设计处理；28 次特殊构造。NIST 12/20/28 次固定矩阵及数学审计、部分混杂方向见 [参考核验](screening-reference-validation.md)。

DSD：官方支持 2–48 因子，连续三级、分类二级；全连续各运行数完整对应表见 [C0 规格](work-package-c0-spec.md)，含分类因子每重复增加一次运行。已构造 6/7/8/10 连续因子及 4 连续加 1 分类的固定矩阵并独立核验；均不是 Minitab 导出。产品标准序、seed、区组及其他规模和分类组合未获得逐点证据。

[Schema 方案](screening-schema-plan.md) 提议 v3：新增两个设计类型、筛选点类和矩阵身份，严格校验；保留 v1/v2 原合同读取并先验证原指纹、正常保存时升级；旧版无法读取 v3。响应/实测值变化与设计设定、运行映射和模型失效分别处理。C1–C3 的接口、GUI 和五个 ACC 的 STD/EDGE/GUI/PERSIST 完成判据见 [规格](work-package-c0-spec.md) 和 [验收规范](acceptance.md)。

## 本次运行的验证

项目环境 `.venv` Python 3.11.9，numpy 2.4.6、pandas 3.0.6、scipy 1.15.3、pytest 9.1.1。

```powershell
& .\.venv\Scripts\python.exe -m pytest tests/test_doe_schema_v2.py tests/test_doe_persistence.py tests/test_doe_fractional.py tests/test_doe_fractional_analysis.py -q
# 52 passed，0 failed，0 skipped，0 warnings
& .\.venv\Scripts\python.exe -m pytest tests/test_doe_screening_references.py -q
# 9 passed，0 failed，0 skipped，0 warnings
& .\.venv\Scripts\python.exe tests\fixtures\doe_screening_reference\dsd\verify.py
# 4 个连续 DSD 矩阵构造和精确算术审计通过，退出码 0
```

整合中一次测试因 CSV 表头约定不一致产生 4 failed、4 passed；修正测试读取格式后重跑通过，随后增加混合参考，最终 9 passed。该失败不是生产算法测试。以上分组是本次结果，不把与历史工作包 B 重叠的结果相加，也没有运行全量 pytest。

额外只读结构检查通过：功能矩阵 80 行、每行 20 列、五项状态和编号未变、C0 文档及参考 README 的本地链接和行尾空白有效。`git diff --check` 通过，Git 提示 feature-matrix.csv 和 sources.md 的 CRLF 将被规范化为 LF；未对未跟踪文件执行 Git diff 检查，已单独检查 C0 文档与 README。

## 外部参考与后续顺序

需要的 Minitab 版本、PB/DSD 因子、区组、重复及导出列详见 [参考核验](screening-reference-validation.md)。优先获得 4 连续加 1 分类以及至少 3 分类因子的 DSD 基础工作表，并补重复/区组与固定 seed 运行序；同时取得 PB12/20/28、DSD6/7/8/10 标准序用于产品一致性比较。保留实际产品不允许的设置记录。

下一步先由网页端进行 C0 独立 Review；经 Review 后冻结 Schema 接口，再并行开展 C1 和有参考的 C2 子范围；其他混合分类配置待独立证据齐备，C3 在 C2 稳定矩阵与模型接口之后开展。未核实的配置保持受阻，不能报告为已实现。
