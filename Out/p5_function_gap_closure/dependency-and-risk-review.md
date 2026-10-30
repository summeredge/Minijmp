# MiniJMP DOE 功能缺口补齐依赖与风险审查 (Dependency and Risk Review)

日期：2026-10-30  
审查对象：Out/p5_function_gap_closure/ 实施规划  

---

## 一、模块间架构依赖分析

本次功能缺口补齐涉及 MiniJMP DOE 核心的 5 大子系统，各开发批次与底层模块的依赖关系如下：

### 1. 筛选与步进回归依赖链 (Batch 1)
- code/doe_dsd.py <-> code/doe_screening_analysis.py <-> code/doe_stepwise.py
- 核心契约：DSD 生成的矩阵结构直接决定投影正交性。多分类因子引入后，必须保证主效应与二次项正交的代数性质。
- 影响半径：DSD 生成元数据 (DesignSpec) 扩展分类因子后，下游 analyze_dsd 与 select_dsd_stepwise 必须同步兼容大于 2 个分类因子的哑变量编码，避免下游索引越界。

### 2. 方差分析与误差分层依赖链 (Batch 1 & Batch 2)
- code/doe_splitplot.py <-> code/doe_splitplot_analysis.py <-> code/doe_factorial_anova.py
- 核心契约：整区（Whole-plot）与副区（Sub-plot）双层误差方差分析依赖平衡区组结构。
- 影响半径：引入非平衡 Type III 平方和（FAC-015）时，必须保持平衡数据下与原 Type I 平方和的向后兼容，不得改变现有 1408 项测试中已固化的纯误差（Pure Error）与失拟（LOF）计算。

### 3. 混料模型与区间预测依赖链 (Batch 2)
- code/doe_mixture.py <-> code/doe_mixture_model.py <-> code/doe_predict.py
- 核心契约：混料总量变量（Amount Variable）在数学上打破了常规纯组分比例和为 1 的无截距约束，属于 Scheffe 模型与多项式模型的张量积展开。
- 影响半径：MixtureTermModel 与 predict_row 必须正确解析带有过程变量与总量变量的高阶交叉项，并确保预测区间中的信息矩阵逆 inv(X'X) 条件数稳定。

### 4. 田口分析与稳健优化依赖链 (Batch 3)
- code/doe_taguchi_arrays.py <-> code/doe_taguchi_analysis.py <-> code/doe_taguchi_analysis_dialog.py
- 核心契约：新增 L36 正交表后，必须严格遵循列分配约束，避免将强交互因子放置在非正交列对上。响应模型法新增方差曲面极小化，不影响原静态 S/N 响应表计算。

---

## 二、关键技术风险与应对策略

| 风险编号 | 风险场景与表现 | 影响模块 | 严重度 | 预防与应对策略 |
|---|---|---|---|---|
| RSK-01 | DSD 多分类因子破坏非混杂性：在因子数较少时，直接强行塞入多个分类因子可能导致主效应与双因子交互混杂，丧失 DSD 核心优势。 | code/doe_dsd.py | 高 (High) | 采用文献验证的 Xiao-Lin-Jones 算法，在生成阶段执行代数投影检验；若因自由度不足无法保持完全非混杂，在生成时弹出明确提示并建议运行增补行。 |
| RSK-02 | 非平衡 Type III 方差分析的秩亏与奇异性：当试验存在多处缺失导致某些高阶效应完全不可估计时，反转非正规信息矩阵可能发生奇异。 | code/doe_factorial_anova.py | 高 (High) | 统一采用 SVD 奇异值分解或广义逆计算可估计对比与投影矩阵，对不可估计参数给出 NaN 并标记自由度退化，坚决杜绝除以零崩溃。 |
| RSK-03 | 混料总量交叉模型自由度爆炸：当组分数较多（如 5 个组分）且同时存在多个过程变量和总量二次项时，展开模型项数急剧膨胀，容易超过试验点数。 | code/doe_mixture_model.py | 中 (Medium) | 在生成混料总量设计时，自动计算最小饱和试验次数；在模型拟合界面设置模型项筛选（截断高阶三因子交互），并提供秩检查预警。 |
| RSK-04 | 田口最优预测有效样本量 ne 异常：若自由度饱和或模型方差 Ve 极小，导致置信区间宽度失真或出现负有效样本量。 | code/doe_taguchi_analysis.py | 中 (Medium) | 严格实现 ne = N / (1 + sum(df)) 约束，当无剩余误差自由度时，提示用户需通过合并微弱效应（Pooling）获得误差估计，不可盲目输出未经校正的区间。 |
| RSK-05 | Federov 点交换算法陷入局部最优：D 最优增补交换模式在复杂多维空间可能收敛于局部极值。 | code/doe_augment.py | 低 (Low) | 采用多随机起点（Random Multi-start, 默认 5 次重启）交换策略，确保获得稳定全局最优或极高 D 效率候选集。 |

---

## 三、已有测试与功能向后兼容性保障

1. 零破坏原则：现有的 1408 项自动化测试（涵盖 1201 项 DOE 逻辑测试与 141 项 Tk GUI 工作流测试）作为不可退化的基准线。每次提交新功能必须保证基准线 100% 维持通过。
2. 渐进式接口扩展：新增参数（如 DSD 的中心点数、Stepwise 的 criterion、ANOVA 的 ss_type、Mixture 的 amount_levels）均设置严格的向后兼容默认值，保持调用旧签名或旧工作流时的输出结果完全一致。
3. 数据表与元数据 Schema 兼容：工作表元数据版本维持向上兼容，已有历史保存的 DOE 设计文件（v1/v2/v3 schema）在重新打开、分析与预测时不受影响。

---

## 四、首推实施模块建议与理由

### 推荐首期实施模块：Batch 1（筛选与因子核心扩展）

首推理由：
1. 最高用户使用频次与痛点：筛选设计（DSD 与 PB）以及两水平析因设计是工业工程应用最广泛的入口。多分类因子支持、AICc 步进判据以及混杂不完全区组是工业客户提出频率最高的实际需求。
2. 逻辑紧凑、架构边界清晰：Batch 1 聚焦在筛选（doe_dsd.py, doe_stepwise.py）与因子（doe_factorial.py, doe_splitplot.py）两条清晰主线上，改动集中，不牵涉复杂的混料单纯形约束或田口内外部交叉表，开发风险极低。
3. 验收反馈极速：该批次 5 项功能均有经典的统计学独立理论参考（如 Xiao & Lin 2012 文献矩阵、AICc 闭式解、Montgomery 因子混杂区组标准表），可以构建完全确定性的独立验证测试，能够迅速确立新一轮开发的质量基准。
