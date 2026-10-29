# DOE 与 Minitab 对标验收规范

> 2026-10-28 工作包 G（Taguchi）状态见本节；独立 Review 尚未执行。

### 工作包 G Taguchi 状态（2026-10-28，限定范围）

工作包 G 完成 G0–G6 的限定范围实现：官方六个数组、静态四类 S/N 与 adjusted nominal (I)、动态 signal-response 回归与动态 S/N、噪声条件描述性稳健性、最佳设置与确认建议、schema v5 与真实 Tk 工程闭环。独立参考位于 `tests/fixtures/doe_taguchi_reference/`，核验器 `tests/test_doe_taguchi_references.py` 不导入生产 Taguchi 模块。

| 验收 | 状态 | 已核验范围 | 未覆盖 |
|---|---|---|---|
| ACC-045 | implemented（限定范围） | 静态设计网格、控制/噪声角色、重复、seed、运行预览、保存重开复制再分析 | 其余目录数组、区组、Minitab 标准序 |
| ACC-046 | implemented（限定范围） | 升序数值信号因子；自由截距/固定参考点回归；斜率、MSE、df、动态 S/N 与 adjusted | 动态 ANOVA F/p、平均响应参考点及其他产品参考选项 |
| ACC-047 | implemented（限定范围） | L4(2³)、L8(2⁷) 官方矩阵、水平平衡与全部列对频数、SHA-256 | L12(2¹¹)、L16(2¹⁵) 等其余两水平数组 |
| ACC-048 | implemented（限定范围） | L9(3⁴) 官方矩阵与解析主效应 | L27(3¹³) 等其余三水平数组 |
| ACC-049 | partial | L18(2¹3⁷) 官方矩阵和 SHA-256 保持不变；控制/噪声各自的实际分配列对按矩阵频数校验，5 对不平衡组合拒绝，平衡子集可用 | 其余混合水平数组；官方页自身平衡声明与该表不符，不宣称完整 L18 两两正交 |
| ACC-050 | implemented（限定范围） | 四类静态 S/N 与 adjusted nominal (I)；Y=[1,2] 五个解析值；定义域拒绝 | 静态 ANOVA 推断、产品表格格式 |
| ACC-051 | implemented（限定范围） | 组合与因子水平 Mean/SD/S/N、水平效应（水平值减总平均）、Delta/Rank/最优水平、观测数、可选 ln(s) 变换；Smaller/Larger 支持 n=1 并将 SD 标为不可用 | 回归/ANOVA 响应表；Nominal/adjusted 仍需样本方差 |
| ACC-052 | partial（限定范围） | 内外表噪声条件间 Mean/SD/S/N、控制因子水平响应表与 Delta/Rank、专用 Tk 窗口；无噪声因子或噪声条件少于两个时明确拒绝；零 SD 按所选 S/N 公式的数据域判断 | 经核验的控制×噪声交互与稳健性优化 |
| ACC-053 | partial（限定范围） | 最大 S/N/最小 SD 保持逐因子选择；目标均值/斜率枚举全部控制水平组合（预算 20,000），稳定报告全部并列组合；加性预测 SD 为负时标为不可用；未观测组合仍提示确认，确认实测不写回原表 | 超预算不报告全局最优；交互修正最优与置信/预测区间；目标型判定容差由用户指定，不是产品等价承诺 |
| ACC-064 | implemented（限定范围） | L16(4⁵) 官方矩阵与平衡/列对审计 | 其他四水平组合 |
| ACC-065 | implemented（限定范围） | L25(5⁶) 官方矩阵与平衡/列对审计 | 其他五水平组合 |

> 2026-10-28 工作包 C 的五项结果及未验证条件见 [工作包 C 收尾记录](work-package-c-closeout.md)。有限构造的本地证据不代表整个官方功能范围或 Minitab 标准序通过。

SCR-005 已由官方页面确认；A 阶段追加 **MTB-DOE-ACC-067**，在工作包 E 为已有工作表因子列与设计列的定义、非法输入、分析和工程往返建立独立验收（当时尚未实现）。

ACC-067 已在工作包 E 完成限定范围：独立构造 6 因子会议矩阵 foldover 加中心行与 4 连续加 1 文本分类矩阵；核对主效应与二因子交互正交、中心水平存在、主效应平方和；无效/冲突列、重复点、非三水平矩阵拒绝且不更改工作簿；真实 GUI 覆盖预览、取消、定义、分析；工程保存、重开、复制保持映射。混合 DSD 主效应之间可以相关，报告而不拒绝；PB 不能冒充 DSD。

### 工作包 D D0–D5 状态（2026-10-28）

限定范围的 D0–D5 实现、独立数学证据、真实 Tk 工作流和工程生命周期已完成，状态为 **WORK_PACKAGE_D_READY_FOR_REVIEW**。功能矩阵中保留 partial 的项目没有被扩张成全量 Minitab 实现声明；完整测试快照见 [工作包 D 收尾记录](work-package-d-closeout.md)。独立 Review 尚未执行。

| 验收 | 状态 | 当前支持及已核验证据 | 未覆盖范围 |
|---|---|---|---|
| ACC-008 | implemented（限定范围） | 2×3 与 2×3×4 完整笛卡尔积；文字/数值标签类型往返；重复、seed、10,000 行前拒绝；真实 Tk 预览/取消/创建；.dexpl 保存、重开、复制和再分析。 | Minitab 标准序、上限和所有产品专属选项未由导出验证。 |
| ACC-009 | implemented（限定范围） | 100/150/200 用 2 df 分类对比，输出边际均值、组合均值、ANOVA；独立非线性 cell-mean 参考确认不产生自动连续趋势项。 | Minitab 参数编码与调整均值表的逐项格式/数值一致性未核实。 |
| ACC-010 | implemented（限定范围） | 混合水平 2×3 与 2×3×4 及独立分类对比；每重复完整区组的 block-adjusted ANOVA 已核验。 | 任意不完整区组划分和 Minitab 标准序/分配未支持或未核实。 |
| ACC-007 | partial（限定范围） | D=ABC 与 D=−ABC 正规分数；符号别名、中心点与解析效应由独立矩阵核验。 | 其他正规分数选项和产品标准序未导出验证。 |
| ACC-015 | partial（限定范围） | 3–6 因子未分区组正规分数支持全因子或单因子单批次 Foldover；源响应保留、实际 alias/秩/分辨度重算，谱系随工程保存。 | PB/Split-Plot、重复折叠及 Minitab 22 输出一致性未覆盖。 |
| ACC-011 / 066 | partial（限定范围） | 两水平全、正规分数及一般全因子只按完整重复成区组；区组随机化、估计性和 ANOVA 已核验。 | 自定义不完整分块和其他随机化模式未支持。 |
| ACC-013 | partial（限定范围） | 两连续两水平因子、至少两个平衡区组；A 使用整区误差，B 与 AB 使用子区误差。 | 更多因子、不平衡配置和 REML 未支持。 |
| ACC-017 / 018 | partial（限定范围） | 系数/效应、逐项 SS/df/F/p、中心对比、按区组修正纯误差和失拟；没有独立纯误差时不显示 LOF F/p。 | 更广产品选项及 Minitab 表格逐项一致性未验证。 |

独立参考位于 `tests/fixtures/doe_factorial_reference/`，当前 `reference.json` SHA-256 为 `0c3e379a6962efe224695ba79a21d101319d4298d1ed6962c9a8a9b6dfef37ba`。Schema v4 严格字段与 v1/v2/v3 旧摘要校验由 `tests/test_doe_factorial_schema.py`、`tests/test_doe_schema_v2.py`、`tests/test_doe_schema_v3.py` 覆盖。真实工程生命周期由各创建 GUI 专项覆盖。

截至 D1，专项命令 `pytest tests/test_doe_factorial_schema.py tests/test_doe_general_factorial.py tests/test_doe_general_factorial_analysis.py tests/test_doe_general_factorial_gui.py tests/test_doe_core.py tests/test_doe_schema_v2.py tests/test_doe_schema_v3.py tests/test_doe_factorial_references.py -q --tb=short` 为 **83 passed、1 tight_layout warning**；`tests/test_help_center.py` 为 **13 passed**；`tests/test_menu_localization.py` 为 **66 passed**。帮助索引已重建。测试按组记录，不相加为唯一总数。

### 工作包 F 逐项状态（2026-10-28）

工作包 F 在隔离 worktree 完成混料合同、三类设计、Scheffé 模型、ANOVA、预测、优化、图形、GUI 与 v4 适配。独立参考位于 `tests/fixtures/doe_mixture_reference/`，`reference.json` SHA-256 为 `8ae2c0712fdb423a0570336ebf96cca0dd8366e56c7dddf1be007ad36099c913`。Minitab 官方页只用于产品范围，不作为数值 oracle；E 的工作表/公共 Schema 联合回归与独立 Review 尚未完成。

| 验收 | 状态 | 当前支持及已核验证据 | 未覆盖范围 |
|---|---|---|---|
| ACC-032 | implemented（限定范围） | 三组分 2/3 阶格点与独立枚举一致；q 2–12、阶数 1–10、10,000 行上限、seed 与标准序；真实 Tk 创建/预览/取消。 | Minitab 标准序及按阶数的组分数上限未由导出核实。 |
| ACC-033 | implemented（限定范围） | 2^q−1 点、三组分 7 点结构（3 顶点/3 边中点/1 重心）、重复与模型秩；保存重开复制。 | 未核对产品标准序。 |
| ACC-034 | implemented（限定范围） | 活动约束枚举三组分 5 顶点与独立参考一致；去重、可行性、质心、点来源；无解/退化显式报告。 | 2–8 组分范围；不声称复制 XVERT/CONAEV 顺序或增补目录。 |
| ACC-035 | implemented（限定范围） | 总和、上下界、线性不等式、伪组分、总量换算；非法点拒绝且不归一化；不可行创建不写工作簿。 | 仅显式数值容差。 |
| ACC-036 | partial（限定范围） | 混料/过程/总量角色分离；过程变量完整低/高水平组合；一个固定总量设定；实际量=总量×比例；xi*z 项独立核验。 | 总量随运行变化、复杂交叉设计及全部产品选项。 |
| ACC-037 | implemented（限定范围） | 无截距线性/二次/三次 Scheffé；自定义合法项；过程/总量编码；秩与可估计性。 | 1–3 阶混料结构外的项被拒绝。 |
| ACC-038 | implemented（限定范围） | 独立参考核对系数、拟合、残差、SSE/SST、项 SS、纯误差、失拟、R²；饱和/秩亏/无纯误差禁用推断；组分主效应不显示 p。 | 产品表格格式与其他推断选项未核实。 |
| ACC-039 | implemented（限定范围） | 解析线性/二次点预测；总和、越界、非有限、缺项、设计快照变化拒绝；模型范围与快照标识。 | 不提供预测/置信区间。 |
| ACC-040 | implemented（限定范围） | SLSQP 单/多响应最大化、最小化、目标与期望；不劣于独立网格界；约束残差、状态与零综合期望报告。 | 局部多起点，不宣称全局最优。 |
| ACC-041 | implemented（限定范围） | Trace 参考混合物、其余比例缩放、逐点总和与预测独立核验；不可行点跳过计数。 | 未比较产品图形布局。 |
| ACC-042 | implemented（限定范围） | 三组分三元图与高维合法切片；不可行网格以掩码保持空值；总和与轴映射核验。 | 产品样式/标签位置未比较。 |
| ACC-043 | implemented（限定范围） | 曲面复用同一合法切片；顶点、边界、重心、总和与三元轴映射独立核验。 | 未比较产品布局。 |
| ACC-044 | implemented（限定范围） | 多响应上下限交集 11 个独立网格点；空交集状态；固定工艺条件；与期望优化分离。 | 未比较产品样式。 |

专项测试按组记录于 [工作包 F 收尾记录](work-package-f-closeout.md)，测试组存在重叠，不相加为唯一总数。

### 工作包 C 第二轮逐项状态（2026-10-28）

以下均为 **partial**。最终快照筛选 GUI、DOE 回归和工程测试已完成，独立 Review 尚未提交；独立数学依据及测试详情见 [参考核验](screening-reference-validation.md) 和 [收尾记录](work-package-c-closeout.md)。产品标准序及随机序均未由 Minitab 22 导出核实。

4 连续加 2 分类的 DSD 主效应并非两两正交：连续与分类列的交叉积为 ±2，两个分类列交叉积为 6；反向配对保证主效应与二阶项交叉积为零。带截距主效应秩为 7，加四个连续平方项秩为 11。

| 验收 | 已支持范围 | 未支持及阻断项 | 数学依据与实际测试 | GUI / 工程及产品一致性 |
|---|---|---|---|---|
| ACC-001 | PB 12/20/24/28/32/36/40/44/48；2 至运行数减 1 的连续或两水平分类因子；重复、每重复中心/伪中心点及按重复分区组 | 其他产品选项及产品标准序未核实 | NIST 原表、Hadamard/Sylvester/Paley 独立构造及中心点规则；筛选非 Tk 136 passed | 各新增运行数的所有连续因子数、分类中心点的 Tk 工程流程已测；筛选 GUI 118 passed，另有 200 个互不重叠的中间因子数案例分组通过；产品点序未核实 |
| ACC-002 | 2–48 连续；1–47 连续加 1 分类；4 连续加 2 分类；完整重复均分区组 | 其他多分类组合、额外中心点及产品伪中心选择 | conference/有限域/反向配对；筛选非 Tk 136 passed | 全部新增高因子连续/单分类及双分类、区组 Tk 工程流程已测；筛选 GUI 118 passed；Minitab 点序与伪中心未核实 |
| ACC-003 | 数值响应，手选主效应、连续平方和交互、区组，秩、零空间、可估系数和对比及适用推断 | 自动选模、权重及其他官方分析选项 | 独立模型矩阵、伪逆和解析响应；筛选非 Tk 136 passed | GUI 可选项与指定对比、重开再分析已测；筛选 GUI 118 passed；产品输出未对标 |
| ACC-005 | 标准化 Pareto、正态和半正态效应图；饱和 PB 主效应 Lenth PSE | 产品完整绘图选项及画法一致性 | Lenth 独立公式、数值及严格截断边界；筛选非 Tk 136 passed | 两族图形及参考线已通过 Tk；筛选 GUI 118 passed；产品图形未对标 |
| ACC-006 | PB 部分/完全混杂投影；DSD 主效应及选定平方/交互投影、模型零空间与指定对比 | PB 一般指定对比、其余多分类配置及产品 alias 表 | 独立交叉积、秩、零空间和对比参考；筛选非 Tk 136 passed | 零空间、对比和投影已有 Tk 专项，筛选 GUI 118 passed；产品 alias 语义未对标 |

## 目的与范围

本规范将 [功能矩阵](feature-matrix.csv) 中所有纳入后续开发的 partial / missing 能力映射到唯一验收编号。原编号 MTB-DOE-ACC-001 至 066 保持不变；自定义筛选定义追加 067。ACC-012 保留为已实现 FAC-009 的基线回归验收，不安排重复开发。每项由标准案例、边界案例和 GUI/工程案例组成。unknown 行须先完成官方范围确认；excluded 行不进入开发验收。

对标产品是 Minitab Statistical Software 在线帮助所描述的 DOE 功能，核查日期为 2026-10-27。官方页面没有标出软件版本，因此不归属到某个发行版。来源和未确认事项见 [sources.md](sources.md)。

## 通用验收合同

### 历史规划：C0 筛选设计细化合同（C1–C3）

以下是 C0 阶段拟定的合同；当前实现与测试状态以上方第二轮表格及联合收尾为准。独立参考的覆盖范围及缺口见 [参考核验](screening-reference-validation.md)，具体接口见 [C0 规格](work-package-c0-spec.md) 与 [Schema 方案](screening-schema-plan.md)。

| 编号 / 责任 / 预计文件 | STD：独立 oracle | EDGE：拒绝或不可用 | GUI：真实窗口 | PERSIST：工程生命周期 | 完成判据及参考缺口 |
|---|---|---|---|---|---|
| ACC-001 / C1 / `doe_pb.py`, `test_doe_pb.py` | 已核验 PB fixture 的水平、正交、容量、矩阵及固定种子；标准序另核产品导出 | 因子超容量、无效水平、重复、区组或种子不得创建 | Factorial 下预览、取消、创建；控件不裁切 | 保存、重开、复制、列改名/重排、损坏与随机序恢复 | 已核验配置全部通过；未核实的规模、中心点、区组及 Minitab 标准序须保留外部参考缺口 |
| ACC-002 / C2 / `doe_dsd.py`, `test_doe_dsd.py` | 已核验 DSD fixture 的点数、水平、秩、主效应对二阶项投影 | 非法类型/水平/区组、超因子数、混合设计无依据配置须拒绝 | Screening 下预览、取消和创建；连续/分类输入滚动可达 | 同 ACC-001，并验证分类映射、伪中心与标准/运行序 | 每个声称支持的配置有独立矩阵和真实工程证据；混合设计分配及精确产品顺序若无参考保持未验证 |
| ACC-003 / C3 / `doe_screening_analysis.py`, `test_doe_screening_analysis.py` | 固定矩阵上的解析响应与独立最小二乘投影核对系数、预测、SSE、df 和适用推断 | 缺失/非法响应拒绝；秩亏仅输出可估结果；饱和或无有效误差时常规推断不可用 | 选择响应与主效应、平方项、交互项并检查输出、诊断 | 重开与复制后再分析；响应修改、设计损坏及来源删除使旧结果过期 | 各模型项、有效行、秩和误差条件均有独立证据；不承诺无参考的自动选模一致性 |
| ACC-005 / C1+C3 / `doe_dialog.py`, `test_doe_screening_gui.py` | 已固定编码和模型的系数、效应及 Pareto 大小和方向由独立代数计算 | 零误差、饱和或不可估计效应不伪造标准化统计量 | PB 走 Factorial 分析；DSD 走 Screening；核对图轴、顺序、标签及缺失推断 | 保存重开后重分析；响应或设计修改后不展示过期效应 | 两家族数据、图形与状态均匹配对应 oracle；产品画法差异须单独核验 |
| ACC-006 / C1+C3 / `doe_screening_analysis.py`, `test_doe_screening_alias.py` | 独立计算模型矩阵秩、交叉积及投影，核对混杂系数和符号 | 完全/部分混杂、秩亏及数值容差分别报告；不把部分混杂当完全别名 | 显示具体项、方向、可估计性与限制 | 复制、重开及因子列重排后保持映射，损坏时拒绝 | PB 不使用正规分数设计等式替代投影；DSD 模型按所选项判秩；产品专属输出语义另核 |

各项通过要求对应 STD、EDGE、GUI、PERSIST 全部完成并经独立 Review；C0 的数学参考通过不等于生产验收通过。

### 输入和结果合同

- 用设计类型、连续/分类因子、实际水平、响应类型、区组/裂区结构、重复定义、随机种子、缺失响应和约束显式描述每个用例。只有官方资料明确的范围才可作为产品上限；未说明的参数范围须由后续实施者核实。
- 设定值、实测因子值和响应值分别处理。缺失/非有限响应、非法水平、重复/重排行、不可行约束、过时工作表映射和来源工作表删除必须得到明确结果，不能猜测或静默修补。
- 设计矩阵检查运行数、水平分布、每列定义、秩、别名/混杂、区组或随机化单位；涉及模型时检查系数、自由度、平方和、检验统计量及推断不可用条件。
- 适用时检验数学不可估计、秩亏、无独立重复、无纯误差自由度、二元响应完全分离、零/全成功事件、精度边界和不可行区域。对方法不适用的检验，验收要求是明确标记“不适用”。
- 数值容差按量纲、公式、矩阵条件数及浮点误差设定。不得对不同统计量套一个固定绝对容差，也不得把 MiniJMP 自身输出作为唯一 oracle。
- 单响应和多响应分开验收。优化必须报告目标、约束、可行性和预测值；只有证明算法保证时才能声明全局最优。

### 独立数学依据

每个标准案例在实现前固定一份独立 fixture 或解析推导，写明出处、变量定义和版本。优先采用官方示例原始数据、教材标准例题或独立代数推导；设计选择算法可用独立穷举的小候选集。不得从 MiniJMP 运行结果反向生成“参考答案”。

推荐的共享 oracle：

- 两水平全因子使用完整 Cartesian product；对编码矩阵 X 检查截距与因子列的正交关系。解析响应例可用 Y=50+3A−2B+4AB，独立计算四个组合的响应与效应。
- 正规部分因子可用 2^(4−1)、生成元 D=ABC；独立重建定义关系与别名组，并验证各系数只解释到别名组。
- 全二次响应面可用解析多项式 Y=40+3A−2B+4AB+5A²−1.5B²，按独立解析值核对系数、残差和矩阵秩。
- 两因子 CCD 用因子点、轴点和中心点显式构造矩阵；CCF 轴距为 1。旋转 CCC 的 alpha 与因子数关系按官方明确支持的设计选项及独立公式核对。设计点数、轴点编码与完整二次模型秩分别验证。
- 三因子 BBD 用每次仅一对因子取 ±1、其余为 0 的独立构造；验证运行数、各因子/因子对水平分布及完整二次模型秩。
- 三组分混料的线性 Scheffé 模型以 sum(x_i)=1 为约束，预测式为各组分线性项之和；二次模型再加入成对乘积项。格点、质心和极端顶点都从独立 simplex/约束多面体构造。
- Taguchi 使用固定的官方正交表矩阵并独立计算列平衡与两两正交；S/N 分析的公式按官方 methods 页面逐类复核，再用手算小样本核对 mean、standard deviation 和 S/N。
- D-optimal 小候选集可枚举所有子集：截距加线性项、候选 x∈{-1,0,1}、选择 2 点时，端点组合的 det(X'X)=4 为最优值。距离型准则必须先固定官方 methods 页面中的精确定义，再独立穷举同一候选集。
- 功效与样本量以独立非中心 F 分布计算为参考；固定 alpha、自由度、效应及噪声参数，逐个核对功效，再核对整数重复数的反解。

### 公共 GUI、异常和持久化案例

每项均需关联以下场景；如某场景对特定功能不适用，验收记录须说明原因。

- STD：合法的标准设计/响应案例及独立数学或设计矩阵 oracle。
- EDGE：至少一个功能相关边界案例，以及非法输入、秩亏/不可估计、缺失/非有限数据或不可行约束中的适用项。
- GUI：从真实菜单进入，输入并预览；取消后不留下工作表；确认后创建；分析、图形/结果、重复操作和来源失效状态正确。二元模型、变异性分析及功效工具按各自输入合同验收。
- PERSIST：保存 .dexpl、关闭、重新打开、复制工作表后重算；验证响应后填/编辑、当前工作表关联、旧工程没有 DOE 元数据时的兼容，以及坏 DOE 元数据不能替换已有工作簿。
- 设计增补另测增补前后的父子关系、行 ID、顺序、列映射、可估计性及重复增补行为。不得把新增行当作旧指纹仍有效。
- 全新统计模型须明确适用性前提。残差图不是正态/独立/等方差假设通过证明；有模型项或纯误差歧义时必须显式限制推断。
- 项目当前已记录的 DOE 专项测试是开发基线证据，不代表本规范的所有未来验收已通过。此工作包没有运行产品测试，也没有改变 DOE-0～DOE-4 APPROVE 基线。

## 待开发能力及唯一验收编号

每行的案例编号由验收编号加 -STD、-EDGE、-GUI、-PERSIST 构成。共用 GUI 和工程合同见上节；每项的“独立核对”列指定该项的数学 oracle 与必须检查的边界。

| 验收编号 | feature_id | 范围与输入合同 | 独立核对与关键边界 |
|---|---|---|---|
| MTB-DOE-ACC-001 | SCR-001 | Plackett–Burman；只接受官方核实的因子数、运行数、生成元与 seed 范围。 | 固定公开 PB 矩阵；独立核对每列水平平衡、列间内积、截距/主效应秩和已知混杂；检查最小有效设计与非法因子数。 |
| MTB-DOE-ACC-002 | SCR-002 | DSD 连续因子和分类因子按官方页区分，官方页范围为 2–48 因子、连续 3 水平、分类 2 水平。 | 固定独立 DSD 矩阵参考；核对水平数、主效应矩阵性质、指定模型项秩及交互/平方项可估计性；检查因子数端点和混合因子情形。 |
| MTB-DOE-ACC-003 | SCR-003 | 对已定义 DSD 拟合连续响应；响应列、模型项和遗漏值处理明确。 | 用独立设计矩阵及解析模型求系数/残差；核对项选择、自由度、推断不可用条件及当前 DSD 分析菜单。 |
| MTB-DOE-ACC-004 | SCR-004 | DSD 二元响应按事件数/试验数输入，不接收伪装为连续响应的 0/1 单次观测替代合同。 | 与独立二项似然/logistic 拟合核对系数与预测；检查 0/全事件、完全分离、非整数计数及零试验数。 |
| MTB-DOE-ACC-005 | SCR-006 | 统一验证 PB、DSD 与正规分数筛选的主效应/候选交互展示。 | 用已知信号因子和无信号因子的独立模型，核对效应/Pareto 输入与排序；混杂效应不得标成单一因子真效应。 |
| MTB-DOE-ACC-006 | SCR-007 | 输出设计混杂关系和指定模型可估计项；不要默认别名组系数代表唯一效应。 | 从独立 X 矩阵精确求秩/零空间及别名关系；检查用户模型含混杂项、矩阵秩亏和不支持项。 |
| MTB-DOE-ACC-007 | FAC-002 | 两水平正规分数：生成元符号、分辨率、seed、重复及中心点需校验；尚不支持的区组输入明确拒绝。 | 独立重建 D=ABC 与 D=-ABC，核对 8 个运行、带符号定义关系/别名；覆盖循环生成元、重复因子、中心点及秩边界。 |
| MTB-DOE-ACC-008 | FAC-003 | General Full Factorial；每个分类因子的 text/numeric level labels 单独输入。 | 以 2×3 完整 Cartesian product 独立重建 6 行；核对每个组合一次、标签保留、模型矩阵秩及水平缺失。 |
| MTB-DOE-ACC-009 | FAC-004 | 数值型水平标签仍按分类因子建模；需与连续变量的多项式响应面建模明确区分。 | 对 100/150/200 三水平和两类配方用独立 contrasts/ANOVA 核对类别均值；确认不自动加入线性或平方项。另用独立 RSM 多项式证明两种模型合同不同。 |
| MTB-DOE-ACC-010 | FAC-005 | 至少两个因子具有不同的类别水平数；每个水平标签保持原值。 | 独立构造 2×3 混合水平 Cartesian product；核对 6 个组合、两因子 contrasts、秩及缺水平边界。 |
| MTB-DOE-ACC-011 | FAC-008 | 区组设计声明区组数、区组运行分配、区组效应及可限制随机化的规则。 | 用独立区组指示矩阵验证秩、处理与区组混杂及自由度；检查空区组、单运行区组和不可估计处理效应。 |
| MTB-DOE-ACC-012 | FAC-009 | 对当前支持的全因子、正规部分因子和 CCD 保持 seeded overall run order。此项是已有基线回归，不安排重复开发。 | 固定 seed 独立重算排列，核对运行集合不变、不同 seed 仍为同一设计点集合；在保存/重开后保持记录的实际顺序。Block/whole-plot 约束由 ACC-066 单独验收。 |
| MTB-DOE-ACC-013 | FAC-010 | Split-plot 指定 hard-to-change 因子、whole plot/subplot 随机化和各自误差项。 | 采用独立 2×2 因子 A/B、3 个区组的 12 行构造；逐项核对总 df、whole-plot error df=2、subplot error df=4 及 A/B/AB 分母。 |
| MTB-DOE-ACC-014 | FAC-011 | 从用户已有两水平工作表定义设计；列映射、因子名、运行次序、响应列显式选择。 | 独立重建用户矩阵与生成元/alias；核对定义-分析往返、列缺失/重排、非 ±1 水平和重复 run ID。 |
| MTB-DOE-ACC-015 | FAC-012 | 正规两水平部分因子支持全因子或单因子 Foldover；记录父设计、原/新增 run ID、折叠因子及批次，并保留原响应、将新增响应留空。PB、Split-Plot、多因子子集及重复折叠仍未支持。 | 独立构造 D=ABC 点集；对比全因子折叠不提升分辨率的 8 点反例与单因子 A 折叠的完整 16 点；核验完整 alias、精确模型秩、lineage 和工程往返。 |
| MTB-DOE-ACC-016 | FAC-013 | 增补运行声明原设计、目标模型、候选新运行、批次和种子。 | 独立计算增补前后矩阵秩、信息矩阵与目标项估计性；检查重复增补、父工程未保存、同名 run ID 和 stale fingerprint。 |
| MTB-DOE-ACC-017 | FAC-014 | 两水平全因子、正规部分因子、一般全因子、完整重复区组、裂区和 Foldover 按各自模型报告主效应/交互；部分因子结果明确为别名组效应。 | `Y=50+3A−2B+4AB` 核对系数、效应与逐项 SS；2×3 分类 contrasts 和平衡裂区用独立 fixture；检查选项阶次、数值标签、别名与真实折叠后矩阵。 |
| MTB-DOE-ACC-018 | FAC-015 | 支持的平衡模型报告 SST/SSR/SSE、项 SS/df/MS/F/p；纯误差按同一因子设定与同一区组分组；区组与裂区使用各自残差层。 | `test_doe_factorial_anova.py` 用手算系数、投影和 3 区组独立 fixture 核验；重算中心偏移、LOF SS/df/F/p。无独立纯误差时不显示 LOF F/p；零方差、饱和、秩亏或不可用误差层不伪造显著性。 |
| MTB-DOE-ACC-019 | FAC-017 | Factorial 二元响应按事件/试验计数及可支持的设计类型输入。 | 独立二项似然拟合；检查 0/全事件、分离、无效计数、模型秩和预测边界。 |
| MTB-DOE-ACC-020 | FAC-018 | Variability 分析需先按官方预处理合同从重复/重复测量得到标准差。 | 以小型重复数组独立计算 mean 与 SD，分母严格按官方方法；核对样本数不足、零方差和预处理响应缺失。 |
| MTB-DOE-ACC-021 | RSM-001 | CCD 每种新增选项单独记录因子数、因子点类型、alpha、中心点、轴点、区组与 seed。 | 独立重建 2 因子、4 个因子点、4 个轴点及中心点的 CCF/CCC 矩阵；核对点数、轴距、编码回算、旋转性声明及矩阵秩。 |
| MTB-DOE-ACC-022 | RSM-002 | 3 因子 BBD 以 ±1 成对点和中心点生成；支持水平与中心数按官方来源核实。 | 独立构造 12 个非中心点加中心点；验证 3 因子完整二次模型秩为 10、点分布与重复中心数。 |
| MTB-DOE-ACC-022A | ACC-022 子项：数学与工程 | 依据标准文献构造并验证 9/10 因子的点阵、正交区组、GUI、分析、预测、优化及工程持久化。 | 本地功能验收通过；独立 Review 尚未完成。 |
| MTB-DOE-ACC-022B | ACC-022 子项：Minitab 一致性 | 使用版本明确的 Minitab 点阵和区组分配，检验允许的等价变换。 | 用户提供的 Minitab 22 五种配置数学等价通过；标准序不精确一致，不外推其他版本及设置。 |
| | 当前状态（2026-10-28） | 3–7、9、10 因子文献构造已实现；8 因子拒绝。 | ACC-022A 本地通过；ACC-022B 对用户提供的 Minitab 22 五种配置数学等价通过，标准序不一致。 |
| MTB-DOE-ACC-023 | RSM-003 | 仅实现官方证实的 blocked CCD/BBD 选项；区组变量输入与模型项需明确。 | 独立构造区组指示/设计矩阵，核对区组与模型项的混杂、rank、df 和输出；区组与 alpha/点类型不兼容时明确拒绝。 |
| MTB-DOE-ACC-024 | RSM-004 | 先逐项确认 Minitab 响应面设计允许的类别因子组合，再固定输入合同。 | 独立 contrasts 和完整模型矩阵对照；检查类别缺水平、单水平、响应面项不可估计和实际水平展示。 |
| MTB-DOE-ACC-025 | RSM-007 | 用户选择线性、平方、交互项及层级规则；不隐式删项。 | 对已知二次解析多项式比较候选模型 SSE/df 和嵌套项；检查违反层级、秩亏、别名与选项遗漏。 |
| MTB-DOE-ACC-026 | RSM-008 | 输入任意可行因子设置，输出当前响应的点预测和明确编码/实际单位。 | 用 Y=40+3A−2B+4AB+5A²−1.5B² 直接代入独立计算；检查边界外预测标示、未拟合响应和模型过期。 |
| MTB-DOE-ACC-027 | RSM-012 | 多响应叠加等高线输入至少两个有效模型及各自可接受范围。 | 用两个可解析二次模型独立计算各响应等值线和可行区域交集；无交集、模型来源不同和模型过期须有明确状态。 |
| MTB-DOE-ACC-028 | RSM-013 | 单响应最大化、最小化或目标逼近；实际可行域和编码 bounds 明示。 | 对预先构造的严格凹二次标准案例用梯度/KKT 与边界枚举核对结果；这只是确定性案例的正确性检查，不构成一般全局保证。对非凸案例验收报告搜索方法、边界和已知限制，不要求超出 Minitab 承诺的保证。 |
| MTB-DOE-ACC-029 | RSM-014 | 多响应目标、阈值、权重、可行域和综合准则逐项输入。 | 独立逐响应重算预测/期望与综合目标；核对权重等价、单响应退化、零期望、下溢。报告求解器搜索范围与局限，不声称一般全局最优或将其当成 Minitab parity gap。 |
| MTB-DOE-ACC-030 | RSM-015 | 纯误差、失拟、曲率、系数推断和残差图分别报告适用条件。 | 独立用投影/分组公式重算 SSE、df、F/p；无重复、无纯误差、零残差 df 时必须标不可用，并核对文档冲突。 |
| MTB-DOE-ACC-031 | RSM-016 | 二元响应的事件/试验输入、响应面项和模型选择需按官方页面确认。 | 独立二项似然/Logistic 模型对照；检查 separation、全部事件相同、无效试验数及预测概率 [0,1]。 |
| MTB-DOE-ACC-032 | MIX-001 | Simplex lattice 的组分数、阶数、界限和总和约束显式输入。 | 独立按 lattice 阶数枚举组分分数；检查每行总和、边界和点数及设计矩阵秩。 |
| MTB-DOE-ACC-033 | MIX-002 | Simplex centroid 的组分集合、重心点层级和重复数显式输入。 | 三组分案例独立列出顶点、边中点和重心；核对重心均值、总和约束、重复及模型秩。 |
| MTB-DOE-ACC-034 | MIX-003 | Extreme vertices 从用户上下限/线性约束定义的可行混料区域生成。 | 独立求解小型线性约束多面体全部顶点并比对；无解、退化面、重复顶点及精度边界须明确处理。 |
| MTB-DOE-ACC-035 | MIX-004 | 组分和、上下界及线性约束具物理意义并明确单位。 | 每个候选点独立检查所有约束；验证边界可行、恰等式、冲突约束和不可行时不创建工作表。 |
| MTB-DOE-ACC-036 | MIX-005 | 混料组分、process variable 与 amount variable 分角色输入。 | 独立构造混料总和约束加过程因子模型矩阵；amount 变化时核对组分比例和绝对量语义。 |
| MTB-DOE-ACC-037 | MIX-006 | Scheffé 模型阶次显式选择，组分约束纳入模型定义。 | 三组分线性/二次解析系数代入；独立比较基矩阵、拟合值及 sum(x)=1，核对不含普通回归截距的约束解释。 |
| MTB-DOE-ACC-038 | MIX-007 | 混料 ANOVA 和系数解释随拟合项、独立重复与可估计性报告。 | 用独立矩阵投影重算 SS、df、残差及纯误差；饱和、不可估计或无纯误差时限制推断。 |
| MTB-DOE-ACC-039 | MIX-008 | 混料预测输入满足所有组分约束，报告实际组成、预测响应和模型范围。 | 将标准三组分模型代入独立解析值；检查越界预测、总和不为 1、非有限响应和模型过期。 |
| MTB-DOE-ACC-040 | MIX-009 | 单/多响应优化使用 mixture 模型并受可行组成约束。 | 独立枚举小型 simplex 网格并比较目标值/边界解；无可行点、目标冲突、零综合期望明确报告。 |
| MTB-DOE-ACC-041 | MIX-010 | Trace plot 指明基准混合物、改变组分及响应。 | 用解析 Scheffé 模型独立采样 trace 曲线；每个点总和固定、其余比例规则明确。 |
| MTB-DOE-ACC-042 | MIX-011 | 选定三组分可视切片并标注可行 simplex 区域。 | 独立求每个网格点的模型预测及约束掩码；图形不得在不可行区域展示为可行结果。 |
| MTB-DOE-ACC-043 | MIX-012 | Surface plot 只展示可行的组分面及响应尺度。 | 对三组分二次模型逐网格独立计算；核对总和、顶点/边界值和图轴坐标映射。 |
| MTB-DOE-ACC-044 | MIX-013 | 多响应可行范围与 mix/process 轴配置显式输入。 | 独立求多个解析模型的可行交集；空交集、响应范围相切及模型失效状态有独立案例。 |
| MTB-DOE-ACC-045 | TAG-001 | 静态设计区分 control factors、noise factors 与响应列。 | 以固定官方正交表独立核对水平平衡/列内积；检查缺因子、超出表容量、重复/空列分配。 |
| MTB-DOE-ACC-046 | TAG-002 | 动态设计显式定义 signal factor、控制/噪声因子及重复响应。 | 用已知线性 signal-response 数据独立回归斜率和误差；检查零/常量 signal、缺组合与缺失响应。 |
| MTB-DOE-ACC-047 | TAG-003 | 两水平 Taguchi 设计按官方页面的 2–31 因子总范围，再从官方可用数组目录选择具体设计。 | 独立检查选定数组每列平衡与任意列对正交；固定标准矩阵逐行核对而非只比较运行数。 |
| MTB-DOE-ACC-048 | TAG-004 | 三水平 Taguchi 设计按官方页面的 2–13 因子总范围，再从官方可用数组目录选择具体设计。 | L9 等固定案例核对每列三水平计数和列对组合；不完整行、错水平和重复编码作为边界。 |
| MTB-DOE-ACC-049 | TAG-005 | 混合水平设计限于官方数组目录；总因子数 2–26，具体上限依 level mix 而异。 | 固定一个官方 mixed array，独立核对各列水平频次及列对组合；未收录数组须明确拒绝。 |
| MTB-DOE-ACC-050 | TAG-006 | 静态 S/N 明确支持 smaller-is-better、larger-is-better、nominal-is-best (I)、nominal-is-best (II)；adjusted nominal-is-best (I) 使用官方公式 S/N = 10 log10((mean² − s²/n)/s²)（s² 为样本方差、n 为观测数；依据详细公式页归于 (I)，来源标签差异见 sources.md）。 | 独立手算 Y=[1,2]，n=2、均值 1.5、样本方差 s²=0.5：smaller = −10log10(2.5)；larger = −10log10(0.625)；nominal (I) = 10log10(4.5)；nominal (II) = −10log10(0.5)；adjusted nominal (I) = 10log10((1.5²−0.5/2)/0.5)=10log10(4)。另测各目标的零/负值、s=0 和 adjusted 对数定义域；独立代码不得调用生产 S/N 函数。 |
| MTB-DOE-ACC-051 | TAG-007 | mean、standard deviation 和 S/N 响应表按因子水平输出。 | 独立逐组计算 mean/SD 与自由度；核对小样本、单次测量、零方差及缺失重复。 |
| MTB-DOE-ACC-052 | TAG-008 | 稳健性分析显式保留噪声因子和控制因子结构。 | 设计控制因子×噪声因子的独立小表，手算响应差/SN；检查无噪声因子时不得宣称已验证稳健性。 |
| MTB-DOE-ACC-053 | TAG-009 | 最佳设置从已声明的 Taguchi 响应指标选择，并区分预测与确认。 | 由独立水平响应表重建设置和预测；并列设置、未出现的组合与确认运行结果分开报告。 |
| MTB-DOE-ACC-054 | GEN-002 | 修改现有设计前显式选择支持的修改类型；seed/run order/replicate/renumber 更新保留来源。 | 独立比较修改前后设计矩阵与统计语义；取消无副作用，非法修改不刷新指纹。 |
| MTB-DOE-ACC-055 | GEN-003 | D-optimal 输入候选矩阵、模型项与目标运行数。 | 在 x∈{-1,0,1}、截距+线性、选 2 点的 oracle 中穷举子集；端点组合 det(X'X)=4。检查奇异候选集。 |
| MTB-DOE-ACC-056 | GEN-004 | Distance-based 只适用于 Response Surface 和 Mixture；Factorial 设计仅提供 D-optimality，不得显示或接受 distance-based 选项。 | 独立按官方规则模拟：RSM 候选起点取离 coded origin 最远点，Mixture 起点取最接近 pure component 的点，随后逐步加入距离已选集合最远的点；以小候选集穷举/手算验证，且检查不重复点。Factorial 请求应明确拒绝或不提供该准则。 |
| MTB-DOE-ACC-057 | GEN-005 | 用相同模型/候选集评估最优性。 | 独立计算目标值；检查不同模型、候选集或运行数不可直接比较。 |
| MTB-DOE-ACC-058 | GEN-006 | 增补时声明父设计、候选点、准则和新批次；Factorial 用 D-optimality，RSM/Mixture 可按已选 D 或 distance-based 准则增补。 | 独立计算增补前后目标变化和矩阵秩；检查准则/设计家族不匹配、无新增独立点、父设计映射过期及增补可重现性。 |
| MTB-DOE-ACC-059 | GEN-007 | 两水平 DOE 功效输入 alpha、噪声、带符号效应差 δ=mean(high)-mean(low)、目标功效和重复数。 | 用独立非中心 F 分布计算功效；逐一改变整数重复数验证目标交叉点和报告值。当前 1 df 非方向性检验，正负等幅 δ 结果应相同，零值拒绝。 |
| MTB-DOE-ACC-060 | GEN-008 | PB 与 general full factorial 的功效算法分别声明适用输入。 | 根据各自官方公式由独立 SciPy 非中心 F 计算核对；错误设计/缺少方差/不可解重复数明确拒绝；带符号 δ 的方向不改变 1 df F 功效。 |
| MTB-DOE-ACC-061 | GEN-009 | 当前各分析器分别列出 rank、残差、纯误差、失拟、曲率和假设诊断。 | 对每项输出指定独立矩阵或残差 oracle；假设未自动检验时标为未验证；不能把图形当作统计检验结论。 |
| MTB-DOE-ACC-062 | GEN-011 | 新设计持久化前先明确 schema 版本、枚举、点类型、约束和旧文件读取策略。 | 旧 DOE schema v1 fixture 必须原样读回；未知版本/字段拒绝时原工作簿保持不变；新旧设计保存/重开/复制/重算一致。 |
| MTB-DOE-ACC-063 | RSM-005 | 从已有工作表定义自定义响应面设计；设计列、连续/分类因子、响应、列映射和设计模型显式声明。 | 从独立输入矩阵重建模型项和 rank；核对数据行顺序、缺列、重排行、超出设计范围的水平及无法估计的自定义项。 |
| MTB-DOE-ACC-064 | TAG-010 | 4-level Taguchi array；官方范围为 2–5 个因子，并选择明确列出的 array。 | 固定一个官方 4-level array，独立核对运行数、每列四水平频数和任意列对的 balance/orthogonality；非法列数和未列出的 array 拒绝。 |
| MTB-DOE-ACC-065 | TAG-011 | 5-level Taguchi array；官方范围为 2–6 个因子，并选择明确列出的 array。 | 固定一个官方 5-level array（如目录中的 L25(5^6)），独立核对运行数、每列五水平频数和列对正交；超出因子数或未列出的 array 拒绝。 |
| MTB-DOE-ACC-066 | FAC-019 | 区组/裂区设计声明 block、whole-plot/subplot 随机化单元及每层 seed/order。 | 用 2×2 因子、3 个区组的 12-run split-plot 独立重建随机化；固定 seed 检查每区组完整 whole plots 与 subplot 顺序，禁止 whole-plot 标签交叉置换，并核对持久化。 |

## 工作包 E 本地验收证据（2026-10-28）

独立参考位于 `tests/fixtures/doe_optimal_reference/`，`reference.json` 的 SHA-256 由 `manifest.json` 固定；核验器只使用标准库与精确有理数，不导入生产模块。

| 编号 | 本地实现与证据 | 未支持配置 |
|---|---|---|
| ACC-014 | `code/doe_custom.py`、`doe_custom_dialog.py`、`doe_custom_analysis.py`；`tests/test_doe_custom_factorial.py`、`test_doe_custom_gui.py`、`test_doe_e_lifecycle.py`。文本水平、行顺序、运行映射、重复 run ID、非法顺序和列冲突均覆盖。 | 非正规矩阵的生成元/别名自动恢复；产品输出一致性 |
| ACC-016 | `code/doe_augment.py::augment`；`tests/test_doe_augment.py`、`test_doe_optimal_augmentation.py`、`test_doe_e_lifecycle.py`。父设计、批次、唯一 run ID、响应保留与空响应覆盖。 | 全部标准设计族的增补；Minitab 对照 |
| ACC-054 | `code/doe_modify.py`；`tests/test_doe_modify.py`。显示重排、按族重新随机化、Split-Plot 整区/子区顺序、按标准序重编号、增加完整重复、取消无副作用。 | 修改因子设定；折叠/增补设计上加重复 |
| ACC-055 | `code/doe_optimal.py::select`；`tests/test_doe_optimal.py`。x∈{-1,0,1} 选 2 点穷举 det=4；并列、奇异、候选不足、全选及大候选启发式均覆盖。 | Mixture 候选合同；A/G/I 准则 |
| ACC-056 | `code/doe_optimal.py::select_distance`；`tests/test_doe_distance_optimal.py`。RSM 起点离编码原点最远、随后最远点、稳定并列；Factorial 明确拒绝。 | Mixture 距离坐标与约束（partial） |
| ACC-057 | `code/doe_optimal.py::evaluate`；`tests/test_doe_optimal_evaluation.py`。秩、条件数、logdet、受保护 det、最小间距；跨模型/运行数不作比较。 | A/G/V 统计量 |
| ACC-058 | `code/doe_augment.py::select_augment`（D-optimal）与 `code/doe_augment.py::_distance_augment`（distance，RSM）；`tests/test_doe_optimal_augmentation.py`、`tests/test_doe_optimal_gui.py`、`tests/test_doe_e_lifecycle.py`。父设计运行固定为距离锚点，按最远点规则补点、不复制候选，增补前后秩与 logdet 报告，谱系保存 criterion。 | Mixture 增补（partial） |
| ACC-061 | `code/doe_diagnostics.py::contract`；`tests/test_doe_diagnostics_contract.py`。统一字段语义，各设计保留独立误差层；假设标为未自动检验。 | 杠杆值、自动假设检验 |
| ACC-062 | `code/doe_core.py` v5；`tests/test_doe_schema_e.py`、`test_doe_schema_v2.py`、`test_doe_schema_v3.py`、`test_doe_e_lifecycle.py`。v1–v4 按原字段/摘要校验后迁移；坏元数据不替换当前工作簿。 | 旧版 MiniJMP 读取 v5 |
| ACC-063 | `code/doe_custom.py`、`doe_custom_analysis.py`；`tests/test_doe_custom_rsm.py`、`test_doe_optimal_evaluation.py`。按实际矩阵重建模型项与秩，拒绝超出范围与不可估计项。 | Scheffé/Mixture；产品输出一致性 |
| ACC-067 | `code/doe_custom.py::screening_properties`；`tests/test_doe_custom_screening.py`。6 因子与 4+1 文本分类构造、重复点、非三水平、非法水平拒绝。 | 其他多分类组合与产品标准序 |

## 工作包 H 限定范围验收证据（2026-10-29）

状态 `WORK_PACKAGE_H_APPROVED_SCOPED`：H0–H6 完成，上一轮独立 Review 为 APPROVE（限定范围）；具体 Review 来源、最终本轮测试和历史验证区分见 [H 收尾记录](work-package-h-closeout.md)。DOE Schema v5 不变，二期尚未开始开发。

独立参考位于 `tests/fixtures/doe_h_reference/`；manifest SHA-256 为 `f5f4ee2246b03b3c6ee1140bd3de9f67f4911a94416bc87520969e2f2baf5c78`。参考生成器与核验器只依赖 NumPy/SciPy/标准库，不导入生产分析代码；每项 H ACC 都映射 STD 与 EDGE。Schema v5 不变，事件/试验/重复测量列须在创建设计时预先声明。

| ACC / feature | 本地状态 | 数学与实现证据 | 验收边界 |
|---|---|---|---|
| MTB-DOE-ACC-004 / SCR-004 | implemented | `doe_binary_analysis.py`；`test_doe_binary_analysis.py` 独立 grouped-binomial likelihood、Wald/LR、概率和 DSD 选项；显著负模型 LR 故障回归；`test_doe_h_lifecycle.py` 真 Tk DSD 平方模型。 | DSD 实际矩阵；分离、全事件/全非事件、秩亏、不收敛或不稳定似然比较不伪造推断。 |
| MTB-DOE-ACC-019 / FAC-017 | implemented | 全因子、正规分数、PB、数值标签 GFF 的独立案例；真实 Tk 对照分数别名组、PB 主效应及 GFF。 | PB 仅主效应；分数效应按别名组解释；未验证高阶/裂区结构不开放。 |
| MTB-DOE-ACC-020 / FAC-018 | implemented | `test_doe_variability.py` 核对 Mean、样本 SD、N、ln(SD) 及推断；真实 Tk 验证同次多列、独立运行多行和主效应图。 | 等组样本数且无缺失才做 ln(SD) 推断；Split-Plot、MLE 和未经验证变换不支持。 |
| MTB-DOE-ACC-031 / RSM-016 | implemented（H4 范围） | 独立 BBD 二项参考、实际 RSM `TermModel`、自定义 RSM Schema v5 核对；真实 Tk 绘制 BBD 概率图并验证来源切换失效。 | 二元 Response Optimizer 属于官方拟合后工作流，但未列入 H4 概率图验收，MiniJMP 未实现；矩阵已明确此限制。 |
| MTB-DOE-ACC-059 / GEN-007 | implemented | 两水平全因子/正规分数独立非中心 F 与最小整数重复数参考；真实 Tk 验证负向 δ 的固定重复和目标功效输入。 | 当前为单个两水平主效应、全设计等次数重复；无中心、区组和裂区。非方向性 1 df F，±δ 功效对称，δ=0 拒绝。 |
| MTB-DOE-ACC-060 / GEN-008 | implemented | PB、两水平 GFF 独立非中心 F 参考；真实 Tk 验证 PB、GFF，并按完整重复组而非相同设定去重构建基础矩阵。 | GFF 仅所有因子两水平；PB/分数解释受别名和未拟合交互假设约束。效应方向不改变当前 1 df F 功效。 |

H 数学与 Tk 生命周期专项共 66 项通过（59 项独立/核心测试 + 7 个单进程真实 Tk 场景）。本轮功效与 H 独立参考测试 30 passed；真实 Tk 负向 δ 功效场景 1 passed；帮助中心 13 passed。跨设计族纯统计与 Schema 回归 328 项通过；另执行 E/F/G 工程集成、已有连续响应优化、RSM 绘图、旧工程往返/坏元数据隔离、帮助索引和菜单映射检查。全量 pytest 未执行；实际节点与结果记录在 [H 收尾记录](work-package-h-closeout.md)。

## 验收完成规则

- 每一项须有独立 fixture/解析结果、标准/边界/GUI/持久化场景，并在对应验收记录中附实际运行结果。
- 验收前发现官方功能范围不同，先更新功能矩阵、sources 和路线图，再调整本规范；不能用代码更改反向扩大产品目标。
- 统计差异必须可追溯到公式、参数化或设计约束；界面差异不能用来掩盖模型、推断或适用性差异。
- 未完成所有纳入 Level 1 的验收编号，不得声明核心对标完成。Level 2 同理；允许的显式排除见 README。

