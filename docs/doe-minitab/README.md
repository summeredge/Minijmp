# MiniJMP DOE 功能与验收

更新：2026-10-31。DOE Phase 2 P2-6.5 在约定范围内完成；生产代码与P2-6A/B测试已在基线 `71520c2`，本轮补齐独立参考、矩阵、帮助、正式文档及验收证据。

## 当前矩阵

| 类别 | implemented | partial | unknown | excluded | 总数 |
|---|---:|---:|---:|---:|---:|
| screening | 6 | 1 | 0 | 0 | 7 |
| factorial | 18 | 1 | 0 | 0 | 19 |
| response_surface | 16 | 0 | 0 | 0 | 16 |
| mixture | 13 | 0 | 0 | 0 | 13 |
| taguchi | 11 | 0 | 0 | 0 | 11 |
| general | 11 | 0 | 1 | 2 | 14 |
| **合计** | **75** | **2** | **1** | **2** | **80** |

implemented 表示该行明确声明的支持范围已有实现和验证，不等于覆盖厂商全部选项或Minitab 22产品输出。partial 表示更宽的目标功能仍有具体缺口；unknown表示证据不足；excluded不计入实现数量。矩阵保持原20字段、80个Feature ID及验收编号体系。

- SCR-002 保留 partial：多分类新增范围为4–12连续因子、2–4二水平分类因子，未覆盖厂商全部连续/分类组合；旧4+2设计保留。
- FAC-012 保留 partial：正规部分因子和限定PB支持一次任意非空因子子集折叠；Split-Plot Foldover、分类/区组PB折叠及连续多批折叠不支持。
- GEN-013 保留 unknown：自动异常值处理的产品范围证据不足；本地提供残差、学生化残差和Cook诊断，不自动删除或替换实验数据。
- GEN-012 excluded：本轮不单独提供统一序贯规划器，可组合Foldover、Augment和Modify保留父子谱系。GEN-014其他选点准则保持excluded；不据此声称厂商不存在相关能力。

## P2-6A/B 范围

A：SCR-002多分类DSD；SCR-003 Forward/Backward及AICc/BIC；SCR-007完整别名矩阵与可估性；FAC-008混杂区组；FAC-010扩展裂区；FAC-015 Type III；RSM-009混料与最优点CI/PI。

B：TAG-005 L36；TAG-008控制×噪声模型与稳健搜索；TAG-009交互预测、CI与确认实验；FAC-012多因子Foldover；MIX-005总量交叉设计；GEN-006固定运行数D-optimal Improve。13项均达到各自合同范围，不能用此结论抹去矩阵partial范围。

## 统计与工程边界

- 裂区限完整平衡二水平设计，2–8因子、1–3整区因子且至少1子区因子；不支持非平衡或REML。固定效应Type III不能替代裂区分层误差分析。
- DSD选择后推断及混料最优点区间是名义固定点结果，不校正选择偏差；秩亏、自由度不足或误差不可估时明确停用相关推断。
- Taguchi交互模型限静态设计；控制×噪声模型限二水平、无signal、噪声组合等权；最多20000控制组合。L36全列主效应模型饱和时无残差推断。
- Improve保护锁定/已执行运行；通用Improve限满秩、无区组的custom Factorial/RSM，采用有界局部交换，不保证全局最优。混料的现有Improve与Schema 1/2恢复路径保留。
- 多分类DSD独立Schur补证明仅针对给定有效conference列子集及声明b/z候选族，不是跨任意DSD矩阵或运行点集合的全局最优证明。
- DOE Schema v5不变，旧v1–v5、Mixture Schema 1/2、工作表复制及工程保存恢复由本轮回归覆盖；损坏元数据拒绝载入，不静默丢弃身份。

## 验收维度与证据

本地功能/GUI、独立统计正确性、产品输出parity分别核定。P2-5历史1408项结果保留，不能与本轮重叠批次相加作为唯一覆盖数。现有Minitab产品输出只涉及SCR-001、SCR-003、FAC-012、RSM-002；其余76项没有对应产品输出。DSD-S01只核对RTF显示精度，BBD存在标准序差异，均不宣称全功能parity。

- [正式80项矩阵](feature-matrix.csv)
- [最终验收及测试命令](../../Out/p2_6_doe_function_completion/p2-6-final-acceptance.md)
- [逐项能力/GUI/参数/缺口与源码测试审计](../../Out/p2_6_doe_function_completion/p2-6-final-feature-audit.csv)
- [13项独立统计参考复核](../../Out/p2_6_doe_function_completion/p2-6-final-statistical-review.md)
- [P2-5证据与产品来源](phase2-p5-preparation.md)、[案例](phase2-p5-case-register.csv)、[80项产品证据分层](phase2-p5-feature-evidence.csv)
- [历史路线图](phase2-roadmap.md)、[方法与验收合同](phase2-acceptance.md)、[官方来源](sources.md)
- 历史A–H和P2-1～P2-4的细节保存在本目录各work-package/phase2 closeout、acceptance及method-contract文档；历史状态不替代当前矩阵。

下一阶段为后续版本需求与范围规划，尚未启动；高级DOE扩展和新增Minitab输出对照需另定范围，不由本轮自动开展。
