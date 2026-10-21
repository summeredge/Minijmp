# Minijmp 统计、质量及绘图参数弹窗中文化

## 基线与工作区

- 主项目：`C:\Users\shaoy\Documents\Minijmp`。
- 本次独立 Codex Worktree：`C:\Users\shaoy\.codex\worktrees\6b90\Minijmp`。
- 开始时为 detached HEAD，`git status --short` 为空；随后创建 `codex/dialog-zh-cn`。
- 基线 Commit：`87281643b7fd0caaedb50ff561720b221c489a07`。
- 未执行 commit、push、merge，也未向主工作区或其他 Worktree 写入。

## 覆盖口径

从 `MiniJMP.Minijmp.createMenuBar` 的实际 `Stats`、`Quality`、`Plots` 菜单字典，经绑定方法追踪到构造函数；真实调用 Tk 菜单命令验证了 46 个新式弹窗。另覆盖 1 个通用绘图器（含六个参数页）、卡方假设概率及旧版子图标题的 2 个二次输入框，共 49 个当前可达窗口。已注释菜单的 `JMP_t_test → TtestDialog` 也随公共实现翻译并验证，但不计入 49 个当前可达窗口。

Tools 菜单中的表格变换、聚合等数据操作窗口、文件导入导出、表格右键菜单、结果查看器不属于统计/质量/绘图参数窗口；保持本阶段排除范围。`sb_palette_dialog.py` 没有实际主菜单调用方，不计入清单；实际配色组件位于 `SBDialog.add_palette_selection`。

下表字段来自真实构造后的控件树，长段落列为“功能说明”；说明正文的 30 条 `help.json.window` 已翻译，英文帮助索引和链接保持原样。重复公共参数仍逐窗口核查。全部行的状态均为已翻译、已构造并关闭。

## 实际入口及可见字段

| 菜单入口 | 弹窗类 / 中文标题 | 源码位置 | 实际可见字段（含按钮） | 状态 |
| --- | --- | --- | --- | --- |
| Stats > Linear Regression | `LinearFitDialog` / 线性回归 | `code/fit_dialog.py:15` | 使用最小二乘法拟合响应变量（Y）与预测变量（X）的线性关系，使观测点到拟合直线的残差平方和最小。 ［单击“帮助”了解更多信息。］；X/Y 变量；预测变量（X）；响应变量（Y）；散点图；显示散点；相关椭圆；椭圆轮廓；线性回归；显示拟合曲线；置信区间；预测区间；正交回归；残差表；误差方差比（Y/X）；X 轴；标签；最小值；最大值；Y 轴；绘图设置；显示网格线；显示图例；边距；置信区间等的显著性水平；显著性水平（α）；确定；取消；帮助 | 已完成 |
| Stats > Correlation | `CorrelationDialog` / 相关分析 | `code/fit_dialog.py:144` | 计算两列数据的相关性并绘制散点图。选择 Pearson 相关时可绘制相关椭圆。 ［单击“帮助”了解更多信息。］；X/Y 变量；变量（X）；变量（Y）；相关分析方法；Pearson 相关：线性关系；Spearman 等级相关：单调关系；Kendall 等级相关：单调关系；Hoeffding D：独立性（较慢，O(n²)）；散点图；仅适用于 Pearson 相关；相关椭圆；椭圆轮廓；显著性水平（α）；X 轴；标签；最小值；最大值；Y 轴；绘图设置；显示网格线；显示图例；边距；确定；取消；帮助 | 已完成 |
| Stats > Orthogonal Regression | `OrthoFitDialog` / 正交回归 | `code/fit_dialog.py:287` | 计算正交回归，同时考虑预测变量和响应变量的测量误差。 ［单击“帮助”了解更多信息。］；X/Y 变量；预测变量（X）；响应变量（Y）；散点图；显示散点；相关椭圆；椭圆轮廓；线性回归；显示拟合曲线；置信区间；预测区间；正交回归；残差表；误差方差比（Y/X）；X 轴；标签；最小值；最大值；Y 轴；绘图设置；显示网格线；显示图例；边距；置信区间等的显著性水平；显著性水平（α）；确定；取消；帮助 | 已完成 |
| Stats > Describe | `DescribeDialog` / 描述性统计 | `code/basic_dialogs.py:129` | 为单列数据生成均值、中位数等描述性统计。统计量使用默认设置，可自定义百分位数位置。 ［单击“帮助”了解更多信息。］；描述性统计；百分位数；确定；取消；帮助 | 已完成 |
| Stats > Describe MutliVar | `MultiDescribeDialog` / 多变量描述性统计 | `code/basic_dialogs.py:64` | 为多列数据生成均值、中位数等描述性统计，可选择输出表中包含的统计量。 ［单击“帮助”了解更多信息。］；数据；列；统计量；样本量（N）；均值；标准差；方差；最小值；第一四分位数；中位数；第三四分位数；最大值；均值标准误；变异系数；总和；极差；四分位距；偏度；峰度；众数；众数个数；确定；取消；帮助 | 已完成 |
| Stats > Normality | `NormTestDialog` / 正态性检验 | `code/basic_dialogs.py:168` | 对一列数据执行 Shapiro-Wilk 和 Anderson-Darling 正态性检验。 ［单击“帮助”了解更多信息。］；选择数据列；绘图；显示 QQ 图；确定；取消；帮助 | 已完成 |
| Stats > Residual Plots | `ResidDialog` / 残差图 | `code/fit_dialog.py:294` | 绘制残差与拟合值图、残差与顺序图、残差直方图及正态 QQ 图。 / 请选择线性回归的预测变量（X）和响应变量（Y）。 ［单击“帮助”了解更多信息。］；X/Y 变量；预测变量（X）；响应变量（Y）；确定；取消；帮助 | 已完成 |
| Stats > Confidence Intervals | `CIDialog` / 置信区间 | `code/basic_dialogs.py:202` | 假定总体服从正态分布，根据样本计算总体均值和标准差的置信区间。 ［单击“帮助”了解更多信息。］；选择数据列；置信区间等的显著性水平；显著性水平（α）；确定；取消；帮助 | 已完成 |
| Stats > Correlation Matrix | `MCorDialog` / 多变量相关分析 | `code/fit_dialog.py:336` | 按住 Ctrl 单击选择多个变量，按住 Shift 单击选择连续范围。可选择一种或多种方法同时计算相关性。 ［单击“帮助”了解更多信息。］；变量；仅包含所有所选列均为有效数值的行。；列；相关分析方法；Pearson 相关：线性关系；Spearman 等级相关：单调关系；Kendall 等级相关：单调关系；Hoeffding D：独立性（较慢，O(n²)）；绘图设置；边距（0.1 表示数据范围的 10%）；水平显示 Y 轴标签；X 轴标签旋转 45°；X 轴刻度标签旋转 45°；仅适用于 Pearson 相关；相关椭圆；椭圆轮廓；显著性水平（α）；确定；取消；帮助 | 已完成 |
| Stats > One Sample Mean t-test | `Mean1SampleDialog` / 单样本 t 检验 | `code/sample_test_dialog.py:13` | 检验总体均值是否等于假设值，使用样本均值估计总体均值。 ［单击“帮助”了解更多信息。］；样本值；汇总数据（优先使用）；N；标准差；均值；假设检验；置信区间等的显著性水平；显著性水平（α）；确定；取消；帮助 | 已完成 |
| Stats > One Sample Mean Z-test | `Mean1SampleZDialog` / 单样本 Z 检验 | `code/sample_test_dialog.py:97` | 总体标准差已知时，检验总体均值是否等于假设值。 ［单击“帮助”了解更多信息。］；样本值；汇总数据（优先使用）；N；均值；假设检验；已知参数；标准差；置信区间等的显著性水平；显著性水平（α）；确定；取消；帮助 | 已完成 |
| Stats > One Sample SD | `Var1SampleDialog` / 单样本标准差检验 | `code/sample_test_dialog.py:175` | 检验总体标准差是否等于假设值，同时执行卡方检验和 Bonett 检验。 ［单击“帮助”了解更多信息。］；样本值；汇总数据（优先使用）；N；标准差；假设检验；置信区间等的显著性水平；显著性水平（α）；确定；取消；帮助 | 已完成 |
| Stats > Two Samples t-test | `Mean2SampleDialog` / 双样本 t 检验 | `code/sample_test_dialog.py:239` | 检验两个总体均值的差是否等于假设值。 ［单击“帮助”了解更多信息。］；样本值；样本 1；样本 2；汇总数据（优先使用）；N；标准差；均值（u1）；均值（u2）；假设检验；u2 - u1 =；假定方差相等；置信区间等的显著性水平；显著性水平（α）；确定；取消；帮助 | 已完成 |
| Stats > Paired t-test | `PairedTDialog` / 配对 t 检验 | `code/sample_test_dialog.py:353` | 根据每对观测值的差，检验两组相关测量（如同一对象的前后测量）的均值是否存在显著差异。 ［单击“帮助”了解更多信息。］；样本值；样本 1；样本 2；假设差值均值；样本 1 - 样本 2；置信区间等的显著性水平；显著性水平（α）；确定；取消；帮助 | 已完成 |
| Stats > Multi-Sample SD Test | `MultiVarDialog` / 多样本标准差检验 | `code/sample_test_dialog.py:416` | 功能说明；变量；列；置信区间等的显著性水平；显著性水平（α）；确定；取消；帮助 | 已完成 |
| Stats > One Proportion Test | `Prop1SDialog` / 单比例检验 | `code/sample_test_dialog.py:454` | 估计总体比例并与目标值比较，包括二项精确检验、正态近似检验和卡方检验。 ［单击“帮助”了解更多信息。］；样本值；样本；事件名称；汇总数据（优先使用）；事件数；试验次数；假设检验；假设比例；置信区间等的显著性水平；显著性水平（α）；确定；取消；帮助 | 已完成 |
| Stats > Two Proportions Test | `Prop2SDialog` / 双比例检验 | `code/sample_test_dialog.py:524` | 当数据仅含两个类别（如合格/不合格）时，检验两组的总体比例是否存在差异。 ［单击“帮助”了解更多信息。］；样本 1；数据列；事件名称；样本 2；样本 1 汇总数据（优先使用）；事件数；试验次数；样本 2 汇总数据（优先使用）；置信区间等的显著性水平；显著性水平（α）；确定；取消；帮助 | 已完成 |
| Stats > One-Way ANOVA | `Anova1WayDialog` / 单因子方差分析（ANOVA） | `code/anova_dialog.py:108` | 功能说明；堆叠数据；数据列；分组变量；数据位于不同列；优先使用此处选择 / 按 Esc 取消选择。；列；置信区间等的显著性水平；显著性水平（α）；均值比较；逐对比较（t 检验）；区间图设置；显示图形；显示网格线；X 轴；标签；Y 轴；最小值；最大值；水平参考线（可选）；Y 轴位置（逗号分隔）；显示标签；确定；取消；帮助 | 已完成 |
| Stats > Two-Way ANOVA | `Anova2WayDialog` / 双因子方差分析（ANOVA） | `code/anova_dialog.py:17` | 比较按两个因子划分的组之间的均值差异，研究两个分类因子及其组合对响应变量的影响。 ［单击“帮助”了解更多信息。］；因子；因子 A；因子 B；响应变量；选项；包含交互作用；确定；取消；帮助 | 已完成 |
| Stats > Contingency table & Chi2 | `Chi2TableDialog` / 交叉表与卡方检验 | `code/chi2_dialog.py:23` | 对两个分类变量执行交叉表与卡方分析。可输入两列原始分类数据，或输入各交叉类别计数构成的汇总表。 ［单击“帮助”了解更多信息。］；原始数据（分类值）；行变量；列变量；双向表汇总数据（优先使用）；列；行标签列（可选）；确定；取消；帮助 | 已完成 |
| Stats > Proportion Chi Square | `Chi2PropDialog` / 比例卡方检验 | `code/chi2_dialog.py:86` | 将分类变量各水平的估计概率与指定的假设概率进行比较。 ［单击“帮助”了解更多信息。］；原始数据（分类值）；样本；汇总计数（优先使用）；水平；计数；确定；取消；帮助 | 已完成 |
| Quality > Crossed Gage R&R | `GRRDialog` / 交叉量具 R&R | `code/qc_dialog.py:99` | 功能说明；输入列；测量值；部件编号；可选输入；操作员；分析方法设置；方法；操作员与部件交互作用；AIAG 和 Xbar/R 设置（可选）；规格宽度（USL - LSL）；历史标准差；绘图设置；Y 轴标签；置信区间等的显著性水平；显著性水平（α）；确定；取消；帮助 | 已完成 |
| Quality > Nested Gage R&R | `GRR_Nested_Dialog` / 嵌套量具 R&R | `code/qc_dialog.py:16` | 功能说明；输入列；测量值；部件编号；操作员；可选输入；历史过程标准差（整体）；确定；取消；帮助 | 已完成 |
| Quality > Process Capability (Cpk) | `CpkDialog` / 过程能力分析 | `code/qc_dialog.py:247` | 功能说明；输入列；测量值；输入规格限；规格下限（LSL）；目标值；规格上限（USL）；显示由相邻观测值移动极差估计的组内标准差；绘图设置；X 轴标签；显示规格限；显示图例；置信区间等的显著性水平；显著性水平（α）；确定；取消；帮助 | 已完成 |
| Quality > Cpk with Subgroups | `CpkSubDialog` / 含子组的过程能力分析 | `code/qc_dialog.py:347` | 评估过程持续生产满足规格限的产品的能力。数据须包含批次、班次、设备等子组；无子组数据请使用“过程能力分析”。 ［单击“帮助”了解更多信息。］；输入列；测量值；输入规格限；规格下限（LSL）；目标值；规格上限（USL）；子组；选项；子组标识列；子组大小；子组内变异；平均值的计算依据；绘图设置；X 轴标签；显示规格限；显示图例；置信区间等的显著性水平；显著性水平（α）；确定；取消；帮助 | 已完成 |
| Quality > Tolerance Interval | `TIDialog` / 正态分布公差区间 | `code/qc_dialog.py:508` | 假定总体服从正态分布，以 1−α 的置信水平计算至少覆盖指定总体比例的公差区间上下限。 ［单击“帮助”了解更多信息。］；样本值；汇总数据（优先使用）；N；标准差；均值；比例设置；指定要覆盖的总体比例；置信区间等的显著性水平；显著性水平（α）；确定；取消；帮助 | 已完成 |
| Quality > Control Chart I/MR | `IMRDialog` / 单值-移动极差控制图（I/MR） | `code/ctrlchart_dialog.py:13` | 单值-移动极差控制图适用于每次采集一个观测值的过程。选择要监控的测量值，并指定移动极差长度，以相邻观测值构成移动子组。 ［单击“帮助”了解更多信息。］；输入列；观测值；移动极差长度；X 轴设置（可选）；X 轴标签；坐标轴标签列；最大刻度标签数；Y 轴设置（可选）；Y 轴标签；第二张图的 Y 轴标签；Y 轴参考线（可选）；Y 轴位置（逗号分隔）；第二张图的 Y 轴位置；历史参数（可选）；过程均值；过程标准差；其他设置；合并标准差；显示所有标准差线；确定；取消；帮助 | 已完成 |
| Quality > Control Chart I | `IDialog` / 单值控制图（I） | `code/ctrlchart_dialog.py:227` | 单值控制图适用于每次采集一个观测值的过程。仅绘制单值控制图，不绘制移动极差控制图。请选择要监控的测量值。 ［单击“帮助”了解更多信息。］；输入列；观测值；X 轴设置（可选）；X 轴标签；坐标轴标签列；最大刻度标签数；Y 轴设置（可选）；Y 轴标签；Y 轴参考线（可选）；Y 轴位置（逗号分隔）；历史参数（可选）；过程均值；过程标准差；其他设置；合并标准差；显示所有标准差线；确定；取消；帮助 | 已完成 |
| Quality > Control Chart MR | `MRDialog` / 移动极差控制图（MR） | `code/ctrlchart_dialog.py:257` | 移动极差控制图适用于每次采集一个观测值的过程。选择测量值并指定移动极差长度，以相邻观测值构成移动子组。 ［单击“帮助”了解更多信息。］；输入列；观测值；移动极差长度；X 轴设置（可选）；X 轴标签；坐标轴标签列；最大刻度标签数；Y 轴设置（可选）；Y 轴标签；Y 轴参考线（可选）；Y 轴位置（逗号分隔）；历史参数（可选）；过程均值；过程标准差；其他设置；合并标准差；显示所有标准差线；确定；取消；帮助 | 已完成 |
| Quality > Control Chart xBar/R | `XBRDialog` / 均值-极差控制图（Xbar/R） | `code/ctrlchart_dialog.py:277` | 输入列；观测值；子组划分方式；子组大小；子组标识列；X 轴设置（可选）；X 轴标签；坐标轴标签列；最大刻度标签数；Y 轴设置（可选）；Y 轴标签；第二张图的 Y 轴标签；Y 轴参考线（可选）；Y 轴位置（逗号分隔）；第二张图的 Y 轴位置；历史参数（可选）；过程均值；过程标准差；其他设置；合并标准差；显示所有标准差线；确定；取消；帮助 | 已完成 |
| Quality > Control Chart xBar/S | `XBSDialog` / 均值-标准差控制图（Xbar/S） | `code/ctrlchart_dialog.py:361` | 输入列；观测值；子组划分方式；子组大小；子组标识列；X 轴设置（可选）；X 轴标签；坐标轴标签列；最大刻度标签数；Y 轴设置（可选）；Y 轴标签；第二张图的 Y 轴标签；Y 轴参考线（可选）；Y 轴位置（逗号分隔）；第二张图的 Y 轴位置；历史参数（可选）；过程均值；过程标准差；其他设置；合并标准差；显示所有标准差线；确定；取消；帮助 | 已完成 |
| Quality > Control Chart NP | `NPDialog` / 不合格品数控制图（NP） | `code/ctrlchart_dialog.py:367` | 输入列；不合格品数（Y）；试验次数；X 轴设置（可选）；X 轴标签；坐标轴标签列；最大刻度标签数；Y 轴设置（可选）；Y 轴标签；Y 轴参考线（可选）；Y 轴位置（逗号分隔）；历史参数（可选）；过程均值；过程标准差；其他设置；合并标准差；显示所有标准差线；确定；取消；帮助 | 已完成 |
| Quality > Control Chart P | `PDialog` / 不合格品率控制图（P） | `code/ctrlchart_dialog.py:455` | 输入列；不合格品数（Y）；试验次数；X 轴设置（可选）；X 轴标签；坐标轴标签列；最大刻度标签数；Y 轴设置（可选）；Y 轴标签；Y 轴参考线（可选）；Y 轴位置（逗号分隔）；历史参数（可选）；过程均值；过程标准差；其他设置；合并标准差；显示所有标准差线；确定；取消；帮助 | 已完成 |
| Quality > Control Chart C | `CDialog` / 缺陷数控制图（C） | `code/ctrlchart_dialog.py:506` | 输入列；缺陷数（Y）；X 轴设置（可选）；X 轴标签；坐标轴标签列；最大刻度标签数；Y 轴设置（可选）；Y 轴标签；Y 轴参考线（可选）；Y 轴位置（逗号分隔）；历史参数（可选）；过程均值；过程标准差；其他设置；合并标准差；显示所有标准差线；确定；取消；帮助 | 已完成 |
| Quality > Control Chart U | `UDialog` / 单位缺陷数控制图（U） | `code/ctrlchart_dialog.py:570` | 输入列；缺陷数（Y）；单位大小；X 轴设置（可选）；X 轴标签；坐标轴标签列；最大刻度标签数；Y 轴设置（可选）；Y 轴标签；Y 轴参考线（可选）；Y 轴位置（逗号分隔）；历史参数（可选）；过程均值；过程标准差；其他设置；合并标准差；显示所有标准差线；确定；取消；帮助 | 已完成 |
| Stats > Fit Distributions | `FitDistDialog` / 分布拟合 | `code/basic_dialogs.py:14` | 根据样本估计分布参数并比较分布的拟合效果。若需绘图，请使用“绘图”菜单中的“直方图与分布拟合”；该功能不比较多个分布。 ［单击“帮助”了解更多信息。］；选择数据列；分布模型；正态分布；t 分布；伽马分布 ：输入值 > 0；对数正态分布 ：输入值 > 0；指数分布 ：输入值 >=0；威布尔分布 ：输入值 > 0；确定；取消；帮助 | 已完成 |
| Plots > Histogram & Dist. Fit | `singleHistoDialog` / 直方图与分布拟合 | `code/sb_hist_dialog.py:13` | 数据；数据列；直方图设置；统计量；组数；组距；分布拟合；分布；显示拟合曲线；X 轴；标签；最小值；最大值；绘图设置；显示网格线；显示图例；边距；绘图；关闭；帮助 | 已完成 |
| Plots > Histogram w/ Groups | `multiHistoDialog` / 分组直方图 | `code/sb_hist_dialog.py:130` | 数据位于一列；数据列；分组变量；各组数据位于不同列；优先使用此处选择 / 按 Esc 取消选择。；列；扩展选项；多组显示方式；图形样式；核密度估计（KDE）；仅显示核密度曲线；直方图设置；统计量；组数；组距；X 轴；标签；最小值；最大值；绘图设置；显示网格线；显示图例；边距；配色方案；配色；绘图；关闭；帮助 | 已完成 |
| Plots > Histogram 2D | `xyHistoDialog` / 二维直方图 | `code/sb_hist_dialog.py:256` | 数据；X 数据列；Y 数据列；分组数据（可选）；颜色分组变量；直方图设置；组数；组距；X 轴；标签；最小值；最大值；Y 轴；绘图设置；显示网格线；显示图例；边距；配色方案；配色；绘图；关闭；帮助 | 已完成 |
| Plots > Box Plot Multiple Y | `singleBoxDialog` / 箱线图 | `code/sb_box_dialog.py:13` | 数据位于一列；数据列；分组变量；各组数据位于不同列；优先使用此处选择 / 按 Esc 取消选择。；列；X 轴；标签；Y 轴；最小值；最大值；水平参考线（可选）；Y 轴位置（逗号分隔）；显示标签；绘图设置；显示网格线；显示图例；箱体宽度；扩展选项；显示蜂群散点；仅显示蜂群散点；隐藏异常值；Y 轴使用对数刻度；高级设置；保留 X 轴原始刻度；须长度或百分位数；绘图；关闭；帮助 | 已完成 |
| Plots > Box Plot w/ Groups | `multiBoxDialog` / 分组箱线图 | `code/sb_box_dialog.py:222` | 数据须为堆叠格式；数据列；分组变量；子分组；子分组变量（颜色）；X 轴；标签；Y 轴；最小值；最大值；水平参考线（可选）；Y 轴位置（逗号分隔）；显示标签；绘图设置；显示网格线；显示图例；箱体宽度；扩展选项；显示蜂群散点；隐藏异常值；Y 轴使用对数刻度；蜂群散点设置；仅显示蜂群散点；分开显示各子组；大小；高级设置；保留 X 轴原始刻度；须长度或百分位数；配色方案；配色；绘图；关闭；帮助 | 已完成 |
| Plots > Count Plot w/ Grps | `countPlotDialog` / 分组计数图 | `code/sb_misc_dialog.py:13` | 数据位于一列；数据列；分组变量（可选）；各组数据位于不同列；优先使用此处选择 / 按 Esc 取消选择。；列；绘图设置；标签；统计量；Y 轴；最小值；最大值；水平参考线（可选）；Y 轴位置（逗号分隔）；显示标签；显示网格线；显示图例；配色方案；配色；绘图；关闭；帮助 | 已完成 |
| Plots > Line Plot w/ Grps | `linePlotDialog` / 分组折线图 | `code/sb_misc_dialog.py:137` | Y 数据位于一列；Y 数据列；分组变量（可选）；各组 Y 数据位于不同列；优先使用此处选择 / 按 Esc 取消选择。；列；X 数据；X 数据列；X 轴；标签；最小值；最大值；Y 轴；绘图设置；显示网格线；显示图例；边距；水平参考线（可选）；Y 轴位置（逗号分隔）；显示标签；配色方案；配色；绘图；关闭；帮助 | 已完成 |
| Plots > Dot Plot w/ Groups | `dotPlotDialog` / 分组点图 | `code/sb_misc_dialog.py:239` | Y 数据位于一列；Y 数据列；分组变量（可选）；各组 Y 数据位于不同列；优先使用此处选择 / 按 Esc 取消选择。；列；X 数据；X 数据列；X 轴；标签；最小值；最大值；Y 轴；绘图设置；显示网格线；显示图例；边距；水平参考线（可选）；Y 轴位置（逗号分隔）；显示标签；配色方案；配色；绘图；关闭；帮助 | 已完成 |
| Plots > Display Probability | `displayProbDialog` / 概率分布图 | `code/dist_plot_dialog.py:72` | 分布；均值；标准差；显示以下指定值对应的区域；指定概率；指定 X 值（优先使用）；显示图形；绘图；关闭；帮助 | 已完成 |
| Plots > Prob. Plot Compare | `displayProb2xDialog` / 概率分布比较图 | `code/dist_plot_dialog.py:137` | 分布 1；分布；均值；标准差；分布 2；绘图；关闭；帮助 | 已完成 |

### 非当前菜单入口（额外覆盖）

| 入口 | 弹窗 | 源码 | 可见字段 | 状态 |
| --- | --- | --- | --- | --- |
| 菜单已注释：JMP_t_test | `TtestDialog` / 均值比较（t 检验） | `code/anova_dialog.py:259` | 变量；列；置信区间等的显著性水平；显著性水平（α）；确定；取消；帮助 | 已完成 |

## 补充入口和公共实现

| 入口 | 类 / 源码 | 已完成内容 |
| --- | --- | --- |
| Plots > Plot Wizard (Legacy) | `pandastable_local.plotting.PlotViewer` | 通用绘图器窗口标题、工具按钮与 Tooltip、当前选区摘要；基本选项、注释、网格布局、其他选项、三维选项、动画六页 |
| 基本 / 三维选项 | `MPLBaseOptions`、`MPL3DOptions`、`TkOptions` | 分组、图形类型、分箱、堆叠、子图、索引、误差线、数据分组、点标签/大小、坐标轴、字体、线型、透明度、颜色刻度及色图 |
| 注释页 | `AnnotationOptions` | 标题、X/Y 轴标签、刻度角度、文本框、填充/边线颜色、旋转、字体、字重、对齐、添加对象、坐标系、创建/清除 |
| 网格布局页 | `PlotLayoutOptions` | 行列数、常规/拆分数据/多视图单选框、图形类型列表、子图列表、删除坐标轴、设置标题；单选内部值仍为 `normal/splitdata/multiviews` |
| 其他选项页 | `ExtraOptions` | 坐标范围、主/次刻度位置、数字格式、符号、精度、日期格式、样式与应用/重置 |
| 动画页 | `AnimateOptions` | 数据窗口、增量/窗口大小/起始行/延迟、显示控制、视频编码器/帧率/文件名、开始/停止 |
| 比例卡方检验 > 假设概率 | `chi2_dialog.ProbabilityDialog` | 中文标题及确定/取消；水平名称来自用户数据；继承原有类型、模态、回车/退出键及确认/取消行为 |
| 通用绘图器 > 设置标题 | `plotting.PlotTitleDialog` | 子图标题、输入标签、确定/取消；继承原 Tk 字符串输入框，用户标题原样传给绘图 |
| 公共分析参数 | `dialog.Dialogs` | 标题显示映射、确定/取消/帮助、X/Y 轴、自动范围、网格线/图例、边距、显著性水平 |
| 公共绘图参数 | `sbplot_dialog.SBDialog` | 绘图/关闭/帮助、水平参考线、标签、30 个配色方案；各派生类覆盖实现亦已逐一翻译 |
| 动态分布参数 | `dist_plot_dialog.comboNEntries` | 分布选择、均值、标准差、自由度、分子/分母自由度、尺度、试验次数、事件概率及不适用字段；切换分布后仍更新中文标签并返回英文参数键 |
| 公共变量选择 | `dialog.addListBox` | 调用处统一显示“列”，保留用户原始列名和列表选择行为 |

旧版选项构造沿用原 `dialogFromOptions`，仅在绘图模块调用后调整展示。没有修改该共享构造器或表格首选项、导入等调用方。配色、样式、字体的内部标识均保持原值。

## 术语

术语核对来源：[Minitab 简体中文帮助](https://support.minitab.com/zh-cn/minitab/help-and-how-to/)、[量具 R&R 研究（交叉）](https://support.minitab.com/zh-cn/minitab/help-and-how-to/modules/measurement-system-analysis/destructive-gage-r-and-r-study/perform-crossed-study/gage-r-r-study-crossed/)、[标准差（组内）](https://support.minitab.com/zh-cn/minitab/help-and-how-to/quality-and-process-improvement/capability-analysis/how-to/capability-sixpack/between-within-capability-sixpack/interpret-the-results/all-statistics-and-graphs/standard-deviations/)、[公差区间（正态分布）](https://support.minitab.com/zh-cn/minitab/help-and-how-to/quality-and-process-improvement/quality-tools/how-to/tolerance-intervals-normal-distribution/interpret-the-results/all-statistics-and-graphs/)。

| 英文 | 中文 |
| --- | --- |
| Response / Predictor / Factor | 响应变量 / 预测变量 / 因子 |
| Variables / Grouping Variable | 变量 / 分组变量 |
| Confidence Level / Confidence Interval | 置信水平 / 置信区间 |
| Significance Level / Alpha | 显著性水平（α）；原参数仍为 0.05，未改成置信水平或百分数 |
| Alternative Hypothesis | 备择假设（术语约定；当前弹窗未新增此控件） |
| Standard Deviation / Variance | 标准差 / 方差 |
| Normality Test / Distribution | 正态性检验 / 分布 |
| Subgroup / Subgroup Size | 子组 / 子组大小 |
| Specification Limits / LSL / USL | 规格限 / 规格下限（LSL） / 规格上限（USL） |
| Historical Parameters | 历史参数 |
| Reference Line / X Axis / Y Axis | 参考线 / X 轴 / Y 轴 |
| Plot Settings | 绘图设置 |
| Measurement System Analysis / Gage R&R | 测量系统分析 / 量具 R&R |
| Process Capability / Within-Subgroup Variation | 过程能力 / 子组内变异 |
| Tolerance Interval | 公差区间（按 Minitab 官方命名） |
| Count / Frequency / Proportion / Percent / Density | 计数 / 频率 / 比例 / 百分比 / 密度 |
| Normal / Student's t / Gamma / Lognormal / Exponential / Weibull | 正态分布 / t 分布 / 伽马分布 / 对数正态分布 / 指数分布 / 威布尔分布 |

保留 `P、NP、C、U、Cp、Cpk、Pp、Ppk、LSL、USL、N、ANOVA、GRR、AIAG、EMP、R&R、QQ、KDE、α、σ` 等统计符号、方法缩写和人名（Pearson、Spearman、Kendall、Hoeffding）。旧版字体列表保持系统实际字体名称，日期选项保持格式代码、编码器保持 `h264`；色图和样式以“色图（原标识）”“样式（原标识）”展示，保留库中专名以便精确辨认。用户数据、报告表头及图表结果文字未系统翻译。

## 行为保护与最小宽度调整

- 固定选项仅增加显示变量，原分析变量仍返回原英文值；反向映射限定为各控件的实际选项，避免 `Lognormal/LogNormal` 及 `Student's t/t` 的同译名冲突。用户数据列选择框不接入显示映射。
- `Dialogs.title` 保持原帮助索引，只对实际窗口标题翻译。`help.json` 仅改窗口内说明，不改键或链接。
- 分布参数、统计量选择字典和分析报告仍使用英文键。数值输入、默认值、分支、计算函数、原按钮回调、窗口模态、取消语义均保持；显示变量随所属控件/框架销毁解除双向跟踪。
- 嵌套量具 R&R 的六种后端 `ValueError` 仅在弹窗错误输出处转换为中文，后端异常及计算代码原样保留。
- 像素测量仅发现两处需要扩大：`qc_dialog.GRRDialog` 的方法框宽度 **14 → 18**；`sb_box_dialog.singleBoxDialog.add_misc_plot_settings` 的箱体宽度选项 **5 → 7**，被单箱线图和分组箱线图共同复用。未改变其他控件布局、增删参数或调整统计设置。

## 测试结果

解释器：`C:\Users\shaoy\Documents\PythonEnvs\minijmp\Scripts\python.exe`，Python 3.11.9、pandas 2.2.3、SciPy 1.14.1；未使用 Codex bundled runtime。

```powershell
$python = 'C:\Users\shaoy\Documents\PythonEnvs\minijmp\Scripts\python.exe'
& $python -m pytest tests/test_dialog_translation.py -q
& $python -m pytest tests/test_statistics_regressions.py tests/test_statistical_edges.py -q
& $python -m pytest -q
```

- 本地化专项最终批次：**119 passed、0 failed**，含真实旧版菜单入口、自动占位提示和数值输入。基线默认值、完整控件类型序列、全部旧英文静态文案消失、实际菜单命令、中文固定选项、动态分布标签与英文参数键、取消不计算、实际确认产生统计报告、错误提示、回调名称、显示变量销毁清理均覆盖。
- 六个旧版绘图参数页均真实创建；下拉框逐项选择后原变量返回值及默认值与原选项一致；单选框调用 `invoke()` 后返回原模式标识；真实 `plot_selected → table.plotSelected → PlotViewer` 路径绘图并关闭，无 Tk 回调异常。
- 中文字体：Tk 为汉字实际解析到 `Microsoft YaHei UI`，通过已安装字体字形映射确认核心汉字存在；对全部新式固定选项测量中文宽度，前述两处调整后均通过。未做人眼逐像素验收，也未验证其他 DPI、系统或显示器配置。
- 现有统计与边界回归：**75 passed**；7 条原有常量数据/坐标轴警告。本轮 P2 修复仅改界面标签，复用此前结果；本轮专项中的分析方法 AST 对照仍通过。
- 在同一解释器和正常参考样本上分别执行基线与当前的 `DescribeDialog`、`NormTestDialog`、`Mean1SampleDialog`、`Mean1SampleZDialog`、`Var1SampleDialog`、`PairedTDialog`，**6/6 完整英文报告字符串完全相同**（含全部数值）。参考样本：X = `[1,2,4,5,7,8]`，Y = `[2,3,3,6,8,9]`；假设均值 3、已知/假设标准差 2、其余参数原默认。
- 全量已有测试加当时的专项用例：**431 passed、4 failed**。四项均是 `tests/test_startup.py::test_windows_launchers_resolve_their_directory_and_propagate_exit_code`：临时副本缺 `.venv` 时 BAT 返回 1，VBS 等待超时。启动器和测试文件无 Diff，直接从基线提取 BAT 后复现相同环境缺失错误；未扩大本地化任务修复启动器或弱化断言。
- `tests/fixtures/dialog_baseline.json` 从指定基线真实创建弹窗采集，记录原分析变量默认值、控件类型、原英文文案和原选项；不是从翻译后状态反推。

## Patch Review 与复杂度审查

已检查本 Worktree 的真实 Git Diff、`git -c core.whitespace=cr-at-eol diff --check`、新增文件和改动清单。分析 `apply/ok/preview` 及参数读取方法的 AST 与指定基线一致（仅规范化显示用错误提示及二次弹窗的显示类/标题）；后端统计模块没有改动。未改公式、数值、配置键、数据类型、回调或帮助链接。`help.json` 保留基线的 CRLF，其他文件保留各自换行风格；行尾没有整文件噪声，未引入新依赖、语言切换机制或国际化框架。

按 no-stop-gpt Audit 检查新增映射状态：双向变量是同时支持“界面中文、分析英文”和原程序 `.set()` 更新所必需；仅在目标控件使用，销毁时释放跟踪。旧版参数继续复用现有构造器，无复制参数定义或全局控件替换。两种二次弹窗只覆盖原父类按钮生成后的文字，不改校验、事件和模态逻辑。

## 跨 Worktree 冲突及未完成事项

开始时主工作区已有 `code/MiniJMP.py`、`pandastable_local/core_orig.py`、`headers.py`、`tests/test_csv_import.py` 的改动及主菜单测试；另一个 `034a` Worktree 正在修改 `MiniJMP.py` 和新增 PI 导入模块。完成前再次只读核查，这些文件均未被本任务修改。未合并其他分支，无当前文件交集；`dialog.py`、`help.json`、`plotting.py` 的未来其他任务改动仍需整合 Review。

若主菜单分支未来修改传入弹窗的 `title`，须保留英文帮助索引与窗口显示标题的分离，不应把中文标题作为 `help.json` 的内部键。本任务无需因当前跨 Worktree 改动而暂缓任何目标弹窗翻译。

目标窗口无已知未翻译的静态标签、按钮或固定英文描述选项；保留的库专名、系统字体名、格式代码及统计缩写见上文。未验证项：其他平台/DPI的人眼显示检查、全部参数组合的手工交互；视频实际编码及全部统计算法穷举不属于本次语言改动验证。全量测试的四项既有启动器失败仍保留。

## 修改文件（18 个）

- `code/anova_dialog.py`
- `code/basic_dialogs.py`
- `code/chi2_dialog.py`
- `code/ctrlchart_dialog.py`
- `code/dialog.py`
- `code/dist_plot_dialog.py`
- `code/fit_dialog.py`
- `code/help.json`
- `code/pandastable_local/plotting.py`
- `code/qc_dialog.py`
- `code/sample_test_dialog.py`
- `code/sb_box_dialog.py`
- `code/sb_hist_dialog.py`
- `code/sb_misc_dialog.py`
- `code/sbplot_dialog.py`
- `docs/DIALOG_TRANSLATION.md`
- `tests/fixtures/dialog_baseline.json`
- `tests/test_dialog_translation.py`

## 独立 Review 的 P2 修复

- C/U 参数框的 Y 输入统一为“缺陷数（Y）”；P/NP 保持“不合格品数（Y）”。新增四条真实窗口标签回归，防止两类计数再次混用；未修改控制图计算、变量、默认值或事件绑定。
- 逐弹窗选项回归显式列出 12 类弹窗的原分析变量路径，包括量具方法、全部配色和嵌套分布选择。先核对全部选择控件及固定选项数量，再逐项触发真实选择事件，断言对应原变量返回精确的基线英文值；映射缺失不再跳过检查。
- 修复后执行 `tests/test_dialog_translation.py`：**119 passed、0 failed**，两条既有绘图依赖弃用警告。基线 fixture 未改。
- 在内存中分别模拟量具方法绑定到错误变量、缺失显示映射，两种回归均触发增强测试的断言失败；实验结束即恢复，未修改项目文件。
- 本轮只改 `code/ctrlchart_dialog.py`、`tests/test_dialog_translation.py` 和本文档；未提交、推送或合并。

## main 整合验证

- 用户随后授权合并到 main，本任务变更已提交。先在 `codex/dialog-zh-cn` 整合 main 的 `c3afc9b`（离线帮助与 PI 导入），自动合并公共 `dialog.py`，保留离线帮助入口及 F1 绑定。
- 测试入口收集改为按 `Dialogs` 实际继承关系识别统计参数窗口，避免将新增的 PI 导入窗口误当成本次目标；原有统计参数弹窗覆盖不减少。
- 整合后执行本地化、离线帮助、PI 导入/读取、统计及边界回归六个测试文件：**233 passed、0 failed**，9 条既有警告。
- 合入 main 前记录其主菜单汉化任务的 6 个未提交文件及 SHA-256，本次合并不包含这些修改，不执行远端推送。
